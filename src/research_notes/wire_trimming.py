"""Evaluate controlled wires, trimming loops, and face orientation."""

from __future__ import annotations

import hashlib
import importlib.metadata
import math
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from research_notes.geometry_kernel import normalize_ocp_step_bytes


Vector2 = tuple[float, float]
Vector3 = tuple[float, float, float]
UVBounds = tuple[float, float, float, float]
TrimStage = Literal["constructed", "step_imported"]
SurfaceKind = Literal["plane", "cylinder", "sphere"]
WireRole = Literal["outer", "inner"]
ClassificationState = Literal["inside", "outside", "on_boundary"]


@dataclass(frozen=True)
class TrimFaceControl:
    """Independent analytic definition for one trimmed support surface."""

    face_id: str
    surface_type: SurfaceKind
    origin: Vector3
    radius: float | None
    restricted_uv_bounds: UVBounds
    reversed: bool
    natural_restriction: bool
    support_u_finite: bool
    support_v_finite: bool


@dataclass(frozen=True)
class ClassificationControl:
    """Expected point classification in one face parameter domain."""

    face_id: str
    sample_id: str
    uv: Vector2
    expected_state: ClassificationState


@dataclass(frozen=True)
class FaceTrimObservation:
    """One face-level measurement of trimming and support-domain properties."""

    stage: TrimStage
    face_id: str
    surface_type: str
    expected_orientation: str
    observed_orientation: str
    expected_area: float
    observed_area: float
    area_absolute_error: float
    expected_centroid: Vector3
    observed_centroid: Vector3
    centroid_distance: float
    expected_restricted_uv_bounds: UVBounds
    observed_restricted_uv_bounds: UVBounds
    restricted_uv_max_absolute_error: float
    support_uv_bounds: UVBounds
    expected_support_u_finite: bool
    observed_support_u_finite: bool
    expected_support_v_finite: bool
    observed_support_v_finite: bool
    u_periodic: bool
    v_periodic: bool
    expected_natural_restriction: bool
    observed_natural_restriction: bool
    wire_count: int
    outer_wire_count: int
    inner_wire_count: int


@dataclass(frozen=True)
class WireObservation:
    """One ordered boundary loop and its validity evidence."""

    stage: TrimStage
    face_id: str
    wire_index: int
    role: WireRole
    orientation: str
    edge_occurrence_count: int
    unique_edge_count: int
    degenerate_occurrence_count: int
    seam_occurrence_count: int
    expected_signed_uv_area: float
    observed_signed_uv_area: float
    signed_uv_area_absolute_error: float
    max_uv_connection_gap: float
    max_vertex_distance: float
    topologically_closed: bool
    brepcheck_closed_2d_status: str
    brepcheck_orientation_status: str
    order_defect: bool
    connected_defect: bool
    closed_defect: bool
    degenerated_defect: bool


@dataclass(frozen=True)
class EdgeUseObservation:
    """One edge occurrence in connection order around a wire."""

    stage: TrimStage
    face_id: str
    wire_index: int
    wire_role: WireRole
    wire_use_index: int
    edge_index: int
    orientation: str
    degenerated: bool
    seam: bool
    has_curve_3d: bool
    vertex_start_parameter: float
    vertex_end_parameter: float
    uv_start: Vector2
    uv_end: Vector2
    next_uv_gap: float
    next_vertex_distance: float
    next_vertex_is_same: bool


@dataclass(frozen=True)
class ClassificationObservation:
    """Observed in/out/boundary state for one controlled UV sample."""

    stage: TrimStage
    face_id: str
    sample_id: str
    uv: Vector2
    expected_state: ClassificationState
    observed_state: str
    matches: bool


@dataclass(frozen=True)
class WireTrimmingProbe:
    """Construction and STEP round-trip evidence for trimming semantics."""

    platform_label: str
    binding_distribution_version: str
    binding_module_version: str
    step_processor: str
    writer_status: str
    reader_status: str
    transferred_roots: int
    constructed_valid: bool
    imported_valid: bool
    step_advanced_face_count: int
    step_face_outer_bound_count: int
    step_face_bound_count: int
    step_edge_loop_count: int
    step_seam_curve_count: int
    step_degenerate_pcurve_count: int
    source_bytes: bytes
    source_sha256: str
    face_observations: tuple[FaceTrimObservation, ...]
    wire_observations: tuple[WireObservation, ...]
    edge_use_observations: tuple[EdgeUseObservation, ...]
    classification_observations: tuple[ClassificationObservation, ...]


def wire_trimming_controls() -> tuple[TrimFaceControl, ...]:
    """Return the fixed planar-hole, periodic, and singular controls."""
    return (
        TrimFaceControl(
            face_id="planar_frame_forward",
            surface_type="plane",
            origin=(0.0, 0.0, 0.0),
            radius=None,
            restricted_uv_bounds=(-4.0, 4.0, -3.0, 3.0),
            reversed=False,
            natural_restriction=False,
            support_u_finite=False,
            support_v_finite=False,
        ),
        TrimFaceControl(
            face_id="planar_frame_reversed",
            surface_type="plane",
            origin=(12.0, 0.0, 0.0),
            radius=None,
            restricted_uv_bounds=(-4.0, 4.0, -3.0, 3.0),
            reversed=True,
            natural_restriction=False,
            support_u_finite=False,
            support_v_finite=False,
        ),
        TrimFaceControl(
            face_id="closed_cylinder",
            surface_type="cylinder",
            origin=(25.0, 0.0, 0.0),
            radius=2.0,
            restricted_uv_bounds=(0.0, 2.0 * math.pi, -2.0, 2.0),
            reversed=False,
            natural_restriction=False,
            support_u_finite=True,
            support_v_finite=False,
        ),
        TrimFaceControl(
            face_id="natural_sphere",
            surface_type="sphere",
            origin=(40.0, 0.0, 0.0),
            radius=3.0,
            restricted_uv_bounds=(
                0.0,
                2.0 * math.pi,
                -math.pi / 2.0,
                math.pi / 2.0,
            ),
            reversed=False,
            natural_restriction=True,
            support_u_finite=True,
            support_v_finite=True,
        ),
    )


def classification_controls() -> tuple[ClassificationControl, ...]:
    """Return fixed samples covering material, void, exterior, and boundaries."""
    planar = (
        ("material", (-3.0, 0.0), "inside"),
        ("hole", (0.0, 0.0), "outside"),
        ("exterior", (5.0, 0.0), "outside"),
        ("outer_boundary", (4.0, 0.0), "on_boundary"),
        ("inner_boundary", (2.0, 0.0), "on_boundary"),
    )
    samples = [
        ClassificationControl(face_id, sample_id, uv, state)  # type: ignore[arg-type]
        for face_id in ("planar_frame_forward", "planar_frame_reversed")
        for sample_id, uv, state in planar
    ]
    samples.extend(
        (
            ClassificationControl("closed_cylinder", "material", (math.pi, 0.0), "inside"),
            ClassificationControl("closed_cylinder", "exterior_v", (math.pi, 3.0), "outside"),
            ClassificationControl("closed_cylinder", "top_boundary", (math.pi, 2.0), "on_boundary"),
            ClassificationControl("natural_sphere", "material", (math.pi, 0.0), "inside"),
            ClassificationControl("natural_sphere", "south_pole", (math.pi, -math.pi / 2.0), "on_boundary"),
            ClassificationControl("natural_sphere", "north_pole", (math.pi, math.pi / 2.0), "on_boundary"),
        )
    )
    return tuple(samples)


def analytic_face_area(control: TrimFaceControl) -> float:
    """Return the analytic material area without calling the geometry backend."""
    if not isinstance(control, TrimFaceControl):
        raise TypeError("control must be a TrimFaceControl")
    if control.surface_type == "plane":
        return 8.0 * 6.0 - 3.0 * 2.0
    if control.radius is None or control.radius <= 0.0:
        raise ValueError("curved controls require a positive radius")
    if control.surface_type == "cylinder":
        return 2.0 * math.pi * control.radius * 4.0
    if control.surface_type == "sphere":
        return 4.0 * math.pi * control.radius**2
    raise ValueError(f"unsupported surface type: {control.surface_type}")


def analytic_face_centroid(control: TrimFaceControl) -> Vector3:
    """Return the area centroid of one symmetric or subtractive control."""
    if not isinstance(control, TrimFaceControl):
        raise TypeError("control must be a TrimFaceControl")
    if control.surface_type == "plane":
        return (control.origin[0] - 1.0 / 14.0, control.origin[1], control.origin[2])
    return control.origin


def expected_wire_signed_uv_area(
    control: TrimFaceControl, role: WireRole
) -> float:
    """Return the signed parameter-plane area expected for one boundary loop."""
    if not isinstance(control, TrimFaceControl):
        raise TypeError("control must be a TrimFaceControl")
    if role not in {"outer", "inner"}:
        raise ValueError(f"unsupported wire role: {role}")
    sign = -1.0 if control.reversed else 1.0
    if control.surface_type == "plane":
        return sign * (48.0 if role == "outer" else -6.0)
    if role == "inner":
        raise ValueError("curved controls do not contain an inner wire")
    if control.surface_type == "cylinder":
        return 8.0 * math.pi
    if control.surface_type == "sphere":
        return 2.0 * math.pi**2
    raise ValueError(f"unsupported surface type: {control.surface_type}")


def _make_rectangle_wire(origin_x: float, bounds: UVBounds) -> object:
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon
    from OCP.gp import gp_Pnt

    u_min, u_max, v_min, v_max = bounds
    polygon = BRepBuilderAPI_MakePolygon()
    for u, v in (
        (u_min, v_min),
        (u_max, v_min),
        (u_max, v_max),
        (u_min, v_max),
    ):
        polygon.Add(gp_Pnt(origin_x + u, v, 0.0))
    polygon.Close()
    return polygon.Wire()


def _construct_shape() -> object:
    from OCP.BRep import BRep_Builder
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.TopoDS import TopoDS, TopoDS_Compound
    from OCP.gp import gp_Ax3, gp_Cylinder, gp_Dir, gp_Pln, gp_Pnt, gp_Sphere

    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    for control in wire_trimming_controls():
        axis = gp_Ax3(
            gp_Pnt(*control.origin), gp_Dir(0.0, 0.0, 1.0), gp_Dir(1.0, 0.0, 0.0)
        )
        if control.surface_type == "plane":
            outer = _make_rectangle_wire(control.origin[0], control.restricted_uv_bounds)
            maker = BRepBuilderAPI_MakeFace(gp_Pln(axis), outer, True)
            inner = _make_rectangle_wire(control.origin[0], (-1.0, 2.0, -1.0, 1.0))
            maker.Add(TopoDS.Wire_s(inner.Reversed()))
            face = maker.Face()
        elif control.surface_type == "cylinder":
            face = BRepBuilderAPI_MakeFace(
                gp_Cylinder(axis, float(control.radius)), *control.restricted_uv_bounds
            ).Face()
        else:
            face = BRepBuilderAPI_MakeFace(
                gp_Sphere(axis, float(control.radius))
            ).Face()
        if control.reversed:
            face = TopoDS.Face_s(face.Reversed())
        builder.Add(compound, face)
    return compound


def _xyz(value: object) -> Vector3:
    return (float(value.X()), float(value.Y()), float(value.Z()))


def _xy(value: object) -> Vector2:
    return (float(value.X()), float(value.Y()))


def _distance_2d(left: Vector2, right: Vector2) -> float:
    return math.hypot(left[0] - right[0], left[1] - right[1])


def _distance_3d(left: Vector3, right: Vector3) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right, strict=True)))


def _orientation_name(value: object) -> str:
    from OCP.TopAbs import TopAbs_FORWARD, TopAbs_REVERSED

    if value == TopAbs_FORWARD:
        return "forward"
    if value == TopAbs_REVERSED:
        return "reversed"
    return str(value).rsplit(".", 1)[-1].lower()


def _surface_identity(face: object) -> tuple[str, Vector3]:
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane, GeomAbs_Sphere

    surface = BRepAdaptor_Surface(face, False)
    kind = surface.GetType()
    if kind == GeomAbs_Plane:
        return "plane", _xyz(surface.Plane().Position().Location())
    if kind == GeomAbs_Cylinder:
        return "cylinder", _xyz(surface.Cylinder().Position().Location())
    if kind == GeomAbs_Sphere:
        return "sphere", _xyz(surface.Sphere().Position().Location())
    raise RuntimeError(f"unexpected controlled surface type: {kind}")


def _match_control(face: object) -> TrimFaceControl:
    surface_type, origin = _surface_identity(face)
    candidates = [
        control
        for control in wire_trimming_controls()
        if control.surface_type == surface_type
    ]
    return min(candidates, key=lambda item: _distance_3d(origin, item.origin))


def _is_finite_support_value(value: float) -> bool:
    return math.isfinite(value) and abs(value) < 1.0e50


def _status_name(status: object) -> str:
    return str(status).rsplit(".", 1)[-1]


def _classification_name(state: object) -> str:
    from OCP.TopAbs import TopAbs_IN, TopAbs_ON, TopAbs_OUT

    if state == TopAbs_IN:
        return "inside"
    if state == TopAbs_OUT:
        return "outside"
    if state == TopAbs_ON:
        return "on_boundary"
    return _status_name(state).lower()


def _measure_wire(
    face: object,
    wire: object,
    control: TrimFaceControl,
    stage: TrimStage,
    wire_index: int,
    role: WireRole,
    edge_map: object,
) -> tuple[WireObservation, tuple[EdgeUseObservation, ...]]:
    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Curve2d
    from OCP.BRepCheck import BRepCheck_Wire
    from OCP.BRepTools import BRepTools_WireExplorer
    from OCP.ShapeAnalysis import ShapeAnalysis_Edge, ShapeAnalysis_Wire
    from OCP.TopExp import TopExp
    from OCP.TopoDS import TopoDS

    raw_uses: list[dict[str, object]] = []
    explorer = BRepTools_WireExplorer(wire, face)
    while explorer.More():
        edge = TopoDS.Edge_s(explorer.Current())
        first_vertex = TopExp.FirstVertex_s(edge, True)
        last_vertex = TopExp.LastVertex_s(edge, True)
        first_parameter = float(BRep_Tool.Parameter_s(first_vertex, edge))
        last_parameter = float(BRep_Tool.Parameter_s(last_vertex, edge))
        pcurve = BRepAdaptor_Curve2d(edge, face)
        raw_uses.append(
            {
                "edge": edge,
                "edge_index": int(edge_map.FindIndex(edge)),
                "orientation": _orientation_name(edge.Orientation()),
                "degenerated": bool(BRep_Tool.Degenerated_s(edge)),
                "seam": bool(BRep_Tool.IsClosed_s(edge, face)),
                "has_curve_3d": bool(ShapeAnalysis_Edge().HasCurve3d(edge)),
                "first_vertex": first_vertex,
                "last_vertex": last_vertex,
                "first_parameter": first_parameter,
                "last_parameter": last_parameter,
                "uv_start": _xy(pcurve.Value(first_parameter)),
                "uv_end": _xy(pcurve.Value(last_parameter)),
            }
        )
        explorer.Next()
    if not raw_uses:
        raise RuntimeError(f"wire has no ordered uses: {control.face_id}")

    observations: list[EdgeUseObservation] = []
    for index, current in enumerate(raw_uses):
        following = raw_uses[(index + 1) % len(raw_uses)]
        current_end = current["uv_end"]
        following_start = following["uv_start"]
        last_vertex = current["last_vertex"]
        next_vertex = following["first_vertex"]
        observations.append(
            EdgeUseObservation(
                stage=stage,
                face_id=control.face_id,
                wire_index=wire_index,
                wire_role=role,
                wire_use_index=index + 1,
                edge_index=int(current["edge_index"]),
                orientation=str(current["orientation"]),
                degenerated=bool(current["degenerated"]),
                seam=bool(current["seam"]),
                has_curve_3d=bool(current["has_curve_3d"]),
                vertex_start_parameter=float(current["first_parameter"]),
                vertex_end_parameter=float(current["last_parameter"]),
                uv_start=current["uv_start"],  # type: ignore[arg-type]
                uv_end=current_end,  # type: ignore[arg-type]
                next_uv_gap=_distance_2d(current_end, following_start),  # type: ignore[arg-type]
                next_vertex_distance=_distance_3d(
                    _xyz(BRep_Tool.Pnt_s(last_vertex)),
                    _xyz(BRep_Tool.Pnt_s(next_vertex)),
                ),
                next_vertex_is_same=bool(last_vertex.IsSame(next_vertex)),
            )
        )

    signed_area = 0.5 * sum(
        item.uv_start[0] * item.uv_end[1]
        - item.uv_end[0] * item.uv_start[1]
        for item in observations
    )
    expected_area = expected_wire_signed_uv_area(control, role)
    checker = BRepCheck_Wire(wire)
    analysis = ShapeAnalysis_Wire(wire, face, 1.0e-7)
    return (
        WireObservation(
            stage=stage,
            face_id=control.face_id,
            wire_index=wire_index,
            role=role,
            orientation=_orientation_name(wire.Orientation()),
            edge_occurrence_count=len(observations),
            unique_edge_count=len({item.edge_index for item in observations}),
            degenerate_occurrence_count=sum(item.degenerated for item in observations),
            seam_occurrence_count=sum(item.seam for item in observations),
            expected_signed_uv_area=expected_area,
            observed_signed_uv_area=signed_area,
            signed_uv_area_absolute_error=abs(signed_area - expected_area),
            max_uv_connection_gap=max(item.next_uv_gap for item in observations),
            max_vertex_distance=max(item.next_vertex_distance for item in observations),
            topologically_closed=all(item.next_vertex_is_same for item in observations),
            brepcheck_closed_2d_status=_status_name(checker.Closed2d(face)),
            brepcheck_orientation_status=_status_name(checker.Orientation(face)),
            order_defect=bool(analysis.CheckOrder()),
            connected_defect=bool(analysis.CheckConnected()),
            closed_defect=bool(analysis.CheckClosed()),
            degenerated_defect=bool(analysis.CheckDegenerated()),
        ),
        tuple(observations),
    )


def _measure_face(
    face: object, stage: TrimStage
) -> tuple[
    FaceTrimObservation,
    tuple[WireObservation, ...],
    tuple[EdgeUseObservation, ...],
    tuple[ClassificationObservation, ...],
]:
    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepClass import BRepClass_FaceClassifier
    from OCP.BRepGProp import BRepGProp
    from OCP.BRepTools import BRepTools
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_WIRE
    from OCP.TopExp import TopExp, TopExp_Explorer
    from OCP.TopTools import TopTools_IndexedMapOfShape
    from OCP.TopoDS import TopoDS
    from OCP.gp import gp_Pnt2d

    control = _match_control(face)
    properties = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, properties)
    centroid = _xyz(properties.CentreOfMass())
    expected_centroid = analytic_face_centroid(control)
    restricted_bounds = tuple(float(value) for value in BRepTools.UVBounds_s(face))
    support = BRepAdaptor_Surface(face, False)
    support_bounds = (
        float(support.FirstUParameter()),
        float(support.LastUParameter()),
        float(support.FirstVParameter()),
        float(support.LastVParameter()),
    )

    edge_map = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(face, TopAbs_EDGE, edge_map)
    outer = BRepTools.OuterWire_s(face)
    wire_observations: list[WireObservation] = []
    edge_uses: list[EdgeUseObservation] = []
    wire_explorer = TopExp_Explorer(face, TopAbs_WIRE)
    wire_index = 0
    while wire_explorer.More():
        wire_index += 1
        wire = TopoDS.Wire_s(wire_explorer.Current())
        role: WireRole = "outer" if wire.IsSame(outer) else "inner"
        wire_observation, uses = _measure_wire(
            face, wire, control, stage, wire_index, role, edge_map
        )
        wire_observations.append(wire_observation)
        edge_uses.extend(uses)
        wire_explorer.Next()

    classifications: list[ClassificationObservation] = []
    for sample in classification_controls():
        if sample.face_id != control.face_id:
            continue
        classifier = BRepClass_FaceClassifier(
            face, gp_Pnt2d(*sample.uv), 1.0e-7
        )
        observed = _classification_name(classifier.State())
        classifications.append(
            ClassificationObservation(
                stage=stage,
                face_id=control.face_id,
                sample_id=sample.sample_id,
                uv=sample.uv,
                expected_state=sample.expected_state,
                observed_state=observed,
                matches=observed == sample.expected_state,
            )
        )

    expected_area = analytic_face_area(control)
    expected_bounds = control.restricted_uv_bounds
    return (
        FaceTrimObservation(
            stage=stage,
            face_id=control.face_id,
            surface_type=control.surface_type,
            expected_orientation="reversed" if control.reversed else "forward",
            observed_orientation=_orientation_name(face.Orientation()),
            expected_area=expected_area,
            observed_area=float(properties.Mass()),
            area_absolute_error=abs(float(properties.Mass()) - expected_area),
            expected_centroid=expected_centroid,
            observed_centroid=centroid,
            centroid_distance=_distance_3d(centroid, expected_centroid),
            expected_restricted_uv_bounds=expected_bounds,
            observed_restricted_uv_bounds=restricted_bounds,  # type: ignore[arg-type]
            restricted_uv_max_absolute_error=max(
                abs(actual - expected)
                for actual, expected in zip(
                    restricted_bounds, expected_bounds, strict=True
                )
            ),
            support_uv_bounds=support_bounds,
            expected_support_u_finite=control.support_u_finite,
            observed_support_u_finite=all(
                _is_finite_support_value(value) for value in support_bounds[:2]
            ),
            expected_support_v_finite=control.support_v_finite,
            observed_support_v_finite=all(
                _is_finite_support_value(value) for value in support_bounds[2:]
            ),
            u_periodic=bool(support.IsUPeriodic()),
            v_periodic=bool(support.IsVPeriodic()),
            expected_natural_restriction=control.natural_restriction,
            observed_natural_restriction=bool(BRep_Tool.NaturalRestriction_s(face)),
            wire_count=len(wire_observations),
            outer_wire_count=sum(item.role == "outer" for item in wire_observations),
            inner_wire_count=sum(item.role == "inner" for item in wire_observations),
        ),
        tuple(wire_observations),
        tuple(edge_uses),
        tuple(classifications),
    )


def _measure_shape(
    shape: object, stage: TrimStage
) -> tuple[
    tuple[FaceTrimObservation, ...],
    tuple[WireObservation, ...],
    tuple[EdgeUseObservation, ...],
    tuple[ClassificationObservation, ...],
]:
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    measured: dict[str, tuple[FaceTrimObservation, tuple[WireObservation, ...], tuple[EdgeUseObservation, ...], tuple[ClassificationObservation, ...]]] = {}
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        face = TopoDS.Face_s(explorer.Current())
        control = _match_control(face)
        if control.face_id in measured:
            raise RuntimeError(f"duplicate controlled face: {control.face_id}")
        measured[control.face_id] = _measure_face(face, stage)
        explorer.Next()
    expected_ids = {item.face_id for item in wire_trimming_controls()}
    if set(measured) != expected_ids:
        raise RuntimeError("measured faces do not match the controlled catalog")
    faces: list[FaceTrimObservation] = []
    wires: list[WireObservation] = []
    uses: list[EdgeUseObservation] = []
    classifications: list[ClassificationObservation] = []
    for control in wire_trimming_controls():
        face, face_wires, face_uses, face_classifications = measured[control.face_id]
        faces.append(face)
        wires.extend(face_wires)
        uses.extend(face_uses)
        classifications.extend(face_classifications)
    return tuple(faces), tuple(wires), tuple(uses), tuple(classifications)


_ASSEMBLY_OCCURRENCE_PATTERN = re.compile(
    rb"(NEXT_ASSEMBLY_USAGE_OCCURRENCE\(')[0-9]+(')"
)


def _normalize_step_bytes(source_bytes: bytes) -> bytes:
    normalized = normalize_ocp_step_bytes(
        source_bytes, expected_translator_occurrences=10
    )
    occurrence_index = 0

    def replacement(match: re.Match[bytes]) -> bytes:
        nonlocal occurrence_index
        occurrence_index += 1
        return match.group(1) + str(occurrence_index).encode("ascii") + match.group(2)

    normalized = _ASSEMBLY_OCCURRENCE_PATTERN.sub(replacement, normalized)
    if occurrence_index != 4:
        raise ValueError("expected exactly four generated assembly occurrence IDs")
    return normalized


def _step_processor(source_bytes: bytes) -> str:
    match = re.search(rb"'Open CASCADE STEP processor ([^']+)'", source_bytes)
    return (
        "unreported"
        if match is None
        else f"Open CASCADE STEP processor {match.group(1).decode('ascii')}"
    )


def _entity_count(source_bytes: bytes, entity_name: bytes) -> int:
    return len(re.findall(rb"=\s*" + entity_name + rb"\(", source_bytes))


def probe_wire_trimming(
    *, platform_label: str = "linux-x64-reference"
) -> WireTrimmingProbe:
    """Evaluate trimming semantics before and after deterministic STEP exchange."""
    if not isinstance(platform_label, str):
        raise TypeError("platform_label must be a string")
    if not platform_label:
        raise ValueError("platform_label must not be empty")

    import OCP
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_AsIs, STEPControl_Reader, STEPControl_Writer

    shape = _construct_shape()
    constructed_valid = bool(BRepCheck_Analyzer(shape).IsValid())
    constructed = _measure_shape(shape, "constructed")

    with tempfile.TemporaryDirectory(prefix="research-notes-wire-trimming-") as directory:
        raw_path = Path(directory) / "analytic_trimmed_faces_raw.step"
        normalized_path = Path(directory) / "analytic_trimmed_faces.step"
        writer = STEPControl_Writer()
        transfer_status = writer.Transfer(shape, STEPControl_AsIs)
        if transfer_status != IFSelect_RetDone:
            raise RuntimeError(f"STEP transfer failed: {_status_name(transfer_status)}")
        writer_status = writer.Write(str(raw_path))
        if writer_status != IFSelect_RetDone:
            raise RuntimeError(f"STEP write failed: {_status_name(writer_status)}")
        source_bytes = _normalize_step_bytes(raw_path.read_bytes())
        normalized_path.write_bytes(source_bytes)
        reader = STEPControl_Reader()
        reader_status = reader.ReadFile(str(normalized_path))
        if reader_status != IFSelect_RetDone:
            raise RuntimeError(f"STEP read failed: {_status_name(reader_status)}")
        transferred_roots = int(reader.TransferRoots())
        imported_shape = reader.OneShape()

    imported_valid = bool(BRepCheck_Analyzer(imported_shape).IsValid())
    imported = _measure_shape(imported_shape, "step_imported")
    return WireTrimmingProbe(
        platform_label=platform_label,
        binding_distribution_version=importlib.metadata.version("cadquery-ocp"),
        binding_module_version=str(OCP.__version__),
        step_processor=_step_processor(source_bytes),
        writer_status=_status_name(writer_status),
        reader_status=_status_name(reader_status),
        transferred_roots=transferred_roots,
        constructed_valid=constructed_valid,
        imported_valid=imported_valid,
        step_advanced_face_count=_entity_count(source_bytes, b"ADVANCED_FACE"),
        step_face_outer_bound_count=_entity_count(source_bytes, b"FACE_OUTER_BOUND"),
        step_face_bound_count=_entity_count(source_bytes, b"FACE_BOUND"),
        step_edge_loop_count=_entity_count(source_bytes, b"EDGE_LOOP"),
        step_seam_curve_count=_entity_count(source_bytes, b"SEAM_CURVE"),
        step_degenerate_pcurve_count=_entity_count(source_bytes, b"DEGENERATE_PCURVE"),
        source_bytes=source_bytes,
        source_sha256=hashlib.sha256(source_bytes).hexdigest(),
        face_observations=constructed[0] + imported[0],
        wire_observations=constructed[1] + imported[1],
        edge_use_observations=constructed[2] + imported[2],
        classification_observations=constructed[3] + imported[3],
    )
