"""Evaluate controlled B-Rep edge curves, p-curves, and seams."""

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
EdgeStage = Literal["constructed", "step_imported"]
SurfaceKind = Literal["plane", "cylinder"]
BoundaryRole = Literal["u_min", "u_max", "v_min", "v_max"]

SAMPLE_COUNT = 17


@dataclass(frozen=True)
class EdgeFaceControl:
    """Independent analytic definition for one bounded support surface."""

    face_id: str
    surface_type: SurfaceKind
    origin: Vector3
    axis: Vector3
    x_direction: Vector3
    uv_bounds: UVBounds
    constructed_edge_tolerance: float
    radius: float | None = None


@dataclass(frozen=True)
class BoundaryTruth:
    """Analytic truth for one boundary role on a controlled face."""

    face_id: str
    role: BoundaryRole
    expected_curve_type: Literal["line", "circle"]
    expected_length: float
    expected_parameter_span: float
    expected_uv_start: Vector2
    expected_uv_mid: Vector2
    expected_uv_end: Vector2
    expected_is_seam: bool


@dataclass(frozen=True)
class PCurveObservation:
    """One oriented wire use and its curve in the surface parameter plane."""

    stage: EdgeStage
    face_id: str
    edge_index: int
    wire_use_index: int
    boundary_role: BoundaryRole
    orientation: str
    pcurve_type: str
    parameter_first: float
    parameter_last: float
    vertex_start_parameter: float
    vertex_end_parameter: float
    uv_start: Vector2
    uv_mid: Vector2
    uv_end: Vector2
    uv_max_absolute_error: float
    range_alignment_error: float
    max_pcurve_to_curve_distance: float
    sample_count: int


@dataclass(frozen=True)
class EdgeCurveObservation:
    """One unique topological edge and its three-dimensional curve evidence."""

    stage: EdgeStage
    face_id: str
    edge_index: int
    boundary_roles: tuple[BoundaryRole, ...]
    expected_curve_type: str
    observed_curve_type: str
    expected_length: float
    observed_length: float
    length_absolute_error: float
    expected_parameter_span: float
    parameter_first: float
    parameter_last: float
    parameter_span: float
    parameter_span_absolute_error: float
    same_parameter_flag: bool
    same_range_flag: bool
    degenerated: bool
    expected_is_seam: bool
    observed_is_seam: bool
    wire_occurrence_count: int
    pcurve_branch_count: int
    edge_tolerance: float
    max_pcurve_to_curve_distance: float


@dataclass(frozen=True)
class EdgeGeometryProbe:
    """Construction and STEP round-trip evidence for controlled edge geometry."""

    platform_label: str
    binding_distribution_version: str
    binding_module_version: str
    step_processor: str
    writer_status: str
    reader_status: str
    transferred_roots: int
    constructed_valid: bool
    imported_valid: bool
    step_edge_curve_count: int
    step_surface_curve_count: int
    step_pcurve_count: int
    step_seam_curve_count: int
    source_bytes: bytes
    source_sha256: str
    edge_observations: tuple[EdgeCurveObservation, ...]
    pcurve_observations: tuple[PCurveObservation, ...]


def edge_face_controls() -> tuple[EdgeFaceControl, ...]:
    """Return the fixed planar, partial-cylinder, and seam controls."""
    return (
        EdgeFaceControl(
            face_id="planar_rectangle",
            surface_type="plane",
            origin=(0.0, 0.0, 0.0),
            axis=(0.0, 0.0, 1.0),
            x_direction=(1.0, 0.0, 0.0),
            uv_bounds=(-2.0, 3.0, -1.0, 2.0),
            constructed_edge_tolerance=1.0e-5,
        ),
        EdgeFaceControl(
            face_id="partial_cylinder",
            surface_type="cylinder",
            origin=(10.0, 0.0, 1.0),
            axis=(0.0, 0.0, 1.0),
            x_direction=(1.0, 0.0, 0.0),
            uv_bounds=(0.25, 1.75, -1.0, 3.5),
            constructed_edge_tolerance=2.0e-5,
            radius=2.0,
        ),
        EdgeFaceControl(
            face_id="closed_cylinder",
            surface_type="cylinder",
            origin=(20.0, 0.0, -2.0),
            axis=(0.0, 0.0, 1.0),
            x_direction=(1.0, 0.0, 0.0),
            uv_bounds=(0.0, 2.0 * math.pi, 0.0, 4.0),
            constructed_edge_tolerance=3.0e-5,
            radius=3.0,
        ),
    )


def analytic_boundary_truth(
    control: EdgeFaceControl, role: BoundaryRole
) -> BoundaryTruth:
    """Derive boundary type, length, parameter span, and UV samples."""
    if not isinstance(control, EdgeFaceControl):
        raise TypeError("control must be an EdgeFaceControl")
    if role not in {"u_min", "u_max", "v_min", "v_max"}:
        raise ValueError(f"unsupported boundary role: {role}")
    u_min, u_max, v_min, v_max = control.uv_bounds
    if not (u_min < u_max and v_min < v_max):
        raise ValueError("UV bounds must be strictly increasing")
    u_mid = (u_min + u_max) / 2.0
    v_mid = (v_min + v_max) / 2.0
    if role == "u_min":
        uv = ((u_min, v_min), (u_min, v_mid), (u_min, v_max))
    elif role == "u_max":
        uv = ((u_max, v_min), (u_max, v_mid), (u_max, v_max))
    elif role == "v_min":
        uv = ((u_min, v_min), (u_mid, v_min), (u_max, v_min))
    else:
        uv = ((u_min, v_max), (u_mid, v_max), (u_max, v_max))

    if control.surface_type == "plane":
        curve_type: Literal["line", "circle"] = "line"
        length = v_max - v_min if role.startswith("u_") else u_max - u_min
        parameter_span = length
    elif control.surface_type == "cylinder":
        if control.radius is None or control.radius <= 0.0:
            raise ValueError("a cylinder control requires a positive radius")
        if role.startswith("u_"):
            curve_type = "line"
            length = v_max - v_min
            parameter_span = length
        else:
            curve_type = "circle"
            parameter_span = u_max - u_min
            length = control.radius * parameter_span
    else:  # pragma: no cover - guarded by the public literal contract
        raise ValueError(f"unsupported surface type: {control.surface_type}")

    expected_is_seam = (
        control.face_id == "closed_cylinder" and role in {"u_min", "u_max"}
    )
    return BoundaryTruth(
        face_id=control.face_id,
        role=role,
        expected_curve_type=curve_type,
        expected_length=length,
        expected_parameter_span=parameter_span,
        expected_uv_start=uv[0],
        expected_uv_mid=uv[1],
        expected_uv_end=uv[2],
        expected_is_seam=expected_is_seam,
    )


def _construct_shape() -> object:
    from OCP.BRep import BRep_Builder
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS, TopoDS_Compound
    from OCP.gp import gp_Ax3, gp_Cylinder, gp_Dir, gp_Pln, gp_Pnt

    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    for control in edge_face_controls():
        axis = gp_Ax3(
            gp_Pnt(*control.origin),
            gp_Dir(*control.axis),
            gp_Dir(*control.x_direction),
        )
        surface = (
            gp_Pln(axis)
            if control.surface_type == "plane"
            else gp_Cylinder(axis, float(control.radius))
        )
        face = BRepBuilderAPI_MakeFace(surface, *control.uv_bounds).Face()
        explorer = TopExp_Explorer(face, TopAbs_EDGE)
        while explorer.More():
            builder.UpdateEdge(
                TopoDS.Edge_s(explorer.Current()),
                control.constructed_edge_tolerance,
            )
            explorer.Next()
        builder.Add(compound, face)
    return compound


def _xyz(value: object) -> Vector3:
    return (float(value.X()), float(value.Y()), float(value.Z()))


def _xy(value: object) -> Vector2:
    return (float(value.X()), float(value.Y()))


def _distance_3d(left: Vector3, right: Vector3) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right, strict=True)))


def _surface_type_and_origin(face: object) -> tuple[str, Vector3]:
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane

    adaptor = BRepAdaptor_Surface(face, True)
    surface_type = adaptor.GetType()
    if surface_type == GeomAbs_Plane:
        return "plane", _xyz(adaptor.Plane().Position().Location())
    if surface_type == GeomAbs_Cylinder:
        return "cylinder", _xyz(adaptor.Cylinder().Position().Location())
    raise RuntimeError(f"unexpected controlled surface type: {surface_type}")


def _match_control(face: object) -> EdgeFaceControl:
    surface_type, origin = _surface_type_and_origin(face)
    candidates = [
        control
        for control in edge_face_controls()
        if control.surface_type == surface_type
    ]
    if not candidates:
        raise RuntimeError(f"no control for measured surface type: {surface_type}")
    return min(candidates, key=lambda item: _distance_3d(origin, item.origin))


def _curve_type_name(value: object) -> str:
    from OCP.GeomAbs import (
        GeomAbs_BSplineCurve,
        GeomAbs_BezierCurve,
        GeomAbs_Circle,
        GeomAbs_Ellipse,
        GeomAbs_Hyperbola,
        GeomAbs_Line,
        GeomAbs_Parabola,
    )

    names = {
        GeomAbs_Line: "line",
        GeomAbs_Circle: "circle",
        GeomAbs_Ellipse: "ellipse",
        GeomAbs_Hyperbola: "hyperbola",
        GeomAbs_Parabola: "parabola",
        GeomAbs_BezierCurve: "bezier",
        GeomAbs_BSplineCurve: "b_spline",
    }
    return names.get(value, str(value).rsplit(".", 1)[-1].removeprefix("GeomAbs_").lower())


def _orientation_name(value: object) -> str:
    from OCP.TopAbs import TopAbs_FORWARD, TopAbs_REVERSED

    if value == TopAbs_FORWARD:
        return "forward"
    if value == TopAbs_REVERSED:
        return "reversed"
    return str(value).rsplit(".", 1)[-1].lower()


def _boundary_role(control: EdgeFaceControl, uv_mid: Vector2) -> BoundaryRole:
    u_min, u_max, v_min, v_max = control.uv_bounds
    distances: dict[BoundaryRole, float] = {
        "u_min": abs(uv_mid[0] - u_min),
        "u_max": abs(uv_mid[0] - u_max),
        "v_min": abs(uv_mid[1] - v_min),
        "v_max": abs(uv_mid[1] - v_max),
    }
    role = min(distances, key=distances.__getitem__)
    if distances[role] > 1.0e-7:
        raise RuntimeError("p-curve midpoint does not lie on a controlled boundary")
    return role


def _max_uv_error(observed: tuple[Vector2, ...], truth: BoundaryTruth) -> float:
    expected = (truth.expected_uv_start, truth.expected_uv_mid, truth.expected_uv_end)
    return max(
        abs(actual_value - expected_value)
        for actual, target in zip(observed, expected, strict=True)
        for actual_value, expected_value in zip(actual, target, strict=True)
    )


def _measure_face(
    face: object, stage: EdgeStage
) -> tuple[tuple[EdgeCurveObservation, ...], tuple[PCurveObservation, ...]]:
    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import (
        BRepAdaptor_Curve,
        BRepAdaptor_Curve2d,
        BRepAdaptor_Surface,
    )
    from OCP.BRepGProp import BRepGProp
    from OCP.BRepTools import BRepTools_WireExplorer
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_WIRE
    from OCP.TopExp import TopExp, TopExp_Explorer
    from OCP.TopTools import TopTools_IndexedMapOfShape
    from OCP.TopoDS import TopoDS

    control = _match_control(face)
    surface = BRepAdaptor_Surface(face, True)
    edge_map = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(face, TopAbs_EDGE, edge_map)
    wire_explorer = TopExp_Explorer(face, TopAbs_WIRE)
    if not wire_explorer.More():
        raise RuntimeError(f"controlled face has no wire: {control.face_id}")
    wire = TopoDS.Wire_s(wire_explorer.Current())
    ordered = BRepTools_WireExplorer(wire, face)
    uses_by_edge: dict[int, list[PCurveObservation]] = {}
    edges: dict[int, object] = {}
    use_index = 0
    while ordered.More():
        use_index += 1
        edge = TopoDS.Edge_s(ordered.Current())
        edge_index = int(edge_map.FindIndex(edge))
        edges.setdefault(edge_index, edge)
        curve3d = BRepAdaptor_Curve(edge)
        pcurve = BRepAdaptor_Curve2d(edge, face)
        first3d = float(curve3d.FirstParameter())
        last3d = float(curve3d.LastParameter())
        first2d = float(pcurve.FirstParameter())
        last2d = float(pcurve.LastParameter())
        midpoint2d = (first2d + last2d) / 2.0
        uv_points = (
            _xy(pcurve.Value(first2d)),
            _xy(pcurve.Value(midpoint2d)),
            _xy(pcurve.Value(last2d)),
        )
        role = _boundary_role(control, uv_points[1])
        truth = analytic_boundary_truth(control, role)
        distances: list[float] = []
        for sample_index in range(SAMPLE_COUNT):
            fraction = sample_index / (SAMPLE_COUNT - 1)
            parameter = first3d + fraction * (last3d - first3d)
            uv = pcurve.Value(parameter)
            point_on_surface = surface.Value(uv.X(), uv.Y())
            distances.append(
                _distance_3d(_xyz(curve3d.Value(parameter)), _xyz(point_on_surface))
            )
        first_vertex = TopExp.FirstVertex_s(edge, True)
        last_vertex = TopExp.LastVertex_s(edge, True)
        observation = PCurveObservation(
            stage=stage,
            face_id=control.face_id,
            edge_index=edge_index,
            wire_use_index=use_index,
            boundary_role=role,
            orientation=_orientation_name(edge.Orientation()),
            pcurve_type=_curve_type_name(pcurve.GetType()),
            parameter_first=first2d,
            parameter_last=last2d,
            vertex_start_parameter=float(BRep_Tool.Parameter_s(first_vertex, edge)),
            vertex_end_parameter=float(BRep_Tool.Parameter_s(last_vertex, edge)),
            uv_start=uv_points[0],
            uv_mid=uv_points[1],
            uv_end=uv_points[2],
            uv_max_absolute_error=_max_uv_error(uv_points, truth),
            range_alignment_error=max(
                abs(first2d - first3d), abs(last2d - last3d)
            ),
            max_pcurve_to_curve_distance=max(distances),
            sample_count=SAMPLE_COUNT,
        )
        uses_by_edge.setdefault(edge_index, []).append(observation)
        ordered.Next()

    edge_observations: list[EdgeCurveObservation] = []
    for edge_index in sorted(edges):
        edge = edges[edge_index]
        uses = uses_by_edge[edge_index]
        role_set = {item.boundary_role for item in uses}
        roles = tuple(
            role
            for role in ("u_min", "u_max", "v_min", "v_max")
            if role in role_set
        )
        truths = tuple(analytic_boundary_truth(control, role) for role in roles)
        expected_types = {item.expected_curve_type for item in truths}
        expected_lengths = {item.expected_length for item in truths}
        expected_spans = {item.expected_parameter_span for item in truths}
        expected_seams = {item.expected_is_seam for item in truths}
        if not (
            len(expected_types)
            == len(expected_lengths)
            == len(expected_spans)
            == len(expected_seams)
            == 1
        ):
            raise RuntimeError("one controlled edge mapped to inconsistent truths")
        curve = BRepAdaptor_Curve(edge)
        first = float(curve.FirstParameter())
        last = float(curve.LastParameter())
        properties = GProp_GProps()
        BRepGProp.LinearProperties_s(edge, properties)
        observed_length = float(properties.Mass())
        expected_length = next(iter(expected_lengths))
        expected_span = next(iter(expected_spans))
        branch_signatures = {
            tuple(round(value, 12) for point in (item.uv_start, item.uv_mid, item.uv_end) for value in point)
            for item in uses
        }
        edge_observations.append(
            EdgeCurveObservation(
                stage=stage,
                face_id=control.face_id,
                edge_index=edge_index,
                boundary_roles=roles,
                expected_curve_type=next(iter(expected_types)),
                observed_curve_type=_curve_type_name(curve.GetType()),
                expected_length=expected_length,
                observed_length=observed_length,
                length_absolute_error=abs(observed_length - expected_length),
                expected_parameter_span=expected_span,
                parameter_first=first,
                parameter_last=last,
                parameter_span=last - first,
                parameter_span_absolute_error=abs((last - first) - expected_span),
                same_parameter_flag=bool(BRep_Tool.SameParameter_s(edge)),
                same_range_flag=bool(BRep_Tool.SameRange_s(edge)),
                degenerated=bool(BRep_Tool.Degenerated_s(edge)),
                expected_is_seam=next(iter(expected_seams)),
                observed_is_seam=bool(BRep_Tool.IsClosed_s(edge, face)),
                wire_occurrence_count=len(uses),
                pcurve_branch_count=len(branch_signatures),
                edge_tolerance=float(BRep_Tool.Tolerance_s(edge)),
                max_pcurve_to_curve_distance=max(
                    item.max_pcurve_to_curve_distance for item in uses
                ),
            )
        )
    return tuple(edge_observations), tuple(
        item for edge_index in sorted(uses_by_edge) for item in uses_by_edge[edge_index]
    )


def _measure_shape(
    shape: object, stage: EdgeStage
) -> tuple[tuple[EdgeCurveObservation, ...], tuple[PCurveObservation, ...]]:
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    by_face: dict[str, tuple[tuple[EdgeCurveObservation, ...], tuple[PCurveObservation, ...]]] = {}
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        face = TopoDS.Face_s(explorer.Current())
        control = _match_control(face)
        if control.face_id in by_face:
            raise RuntimeError(f"duplicate controlled face: {control.face_id}")
        by_face[control.face_id] = _measure_face(face, stage)
        explorer.Next()
    expected_ids = {item.face_id for item in edge_face_controls()}
    if set(by_face) != expected_ids:
        raise RuntimeError("measured faces do not match the controlled catalog")
    edges: list[EdgeCurveObservation] = []
    pcurves: list[PCurveObservation] = []
    for control in edge_face_controls():
        face_edges, face_pcurves = by_face[control.face_id]
        edges.extend(face_edges)
        pcurves.extend(face_pcurves)
    return tuple(edges), tuple(pcurves)


_ASSEMBLY_OCCURRENCE_PATTERN = re.compile(
    rb"(NEXT_ASSEMBLY_USAGE_OCCURRENCE\(')[0-9]+(')"
)


def _normalize_edge_step_bytes(source_bytes: bytes) -> bytes:
    normalized = normalize_ocp_step_bytes(
        source_bytes, expected_translator_occurrences=8
    )
    occurrence_index = 0

    def replacement(match: re.Match[bytes]) -> bytes:
        nonlocal occurrence_index
        occurrence_index += 1
        return match.group(1) + str(occurrence_index).encode("ascii") + match.group(2)

    normalized = _ASSEMBLY_OCCURRENCE_PATTERN.sub(replacement, normalized)
    if occurrence_index != 3:
        raise ValueError("expected exactly three generated assembly occurrence IDs")
    return normalized


def _status_name(status: object) -> str:
    return str(status).rsplit(".", 1)[-1]


def _step_processor(source_bytes: bytes) -> str:
    match = re.search(rb"'Open CASCADE STEP processor ([^']+)'", source_bytes)
    return (
        "unreported"
        if match is None
        else f"Open CASCADE STEP processor {match.group(1).decode('ascii')}"
    )


def _entity_count(source_bytes: bytes, entity_name: bytes) -> int:
    return len(re.findall(rb"=\s*" + entity_name + rb"\(", source_bytes))


def probe_edge_geometry(
    *, platform_label: str = "linux-x64-reference"
) -> EdgeGeometryProbe:
    """Evaluate controlled edge geometry before and after STEP exchange."""
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
    constructed_edges, constructed_pcurves = _measure_shape(shape, "constructed")

    with tempfile.TemporaryDirectory(prefix="research-notes-edge-geometry-") as directory:
        raw_path = Path(directory) / "analytic_edge_faces_raw.step"
        normalized_path = Path(directory) / "analytic_edge_faces.step"
        writer = STEPControl_Writer()
        writer.SetTolerance(1.0e-5)
        transfer_status = writer.Transfer(shape, STEPControl_AsIs)
        if transfer_status != IFSelect_RetDone:
            raise RuntimeError(f"STEP transfer failed: {_status_name(transfer_status)}")
        writer_status = writer.Write(str(raw_path))
        if writer_status != IFSelect_RetDone:
            raise RuntimeError(f"STEP write failed: {_status_name(writer_status)}")
        source_bytes = _normalize_edge_step_bytes(raw_path.read_bytes())
        normalized_path.write_bytes(source_bytes)

        reader = STEPControl_Reader()
        reader_status = reader.ReadFile(str(normalized_path))
        if reader_status != IFSelect_RetDone:
            raise RuntimeError(f"STEP read failed: {_status_name(reader_status)}")
        transferred_roots = int(reader.TransferRoots())
        imported_shape = reader.OneShape()

    imported_valid = bool(BRepCheck_Analyzer(imported_shape).IsValid())
    imported_edges, imported_pcurves = _measure_shape(imported_shape, "step_imported")
    return EdgeGeometryProbe(
        platform_label=platform_label,
        binding_distribution_version=importlib.metadata.version("cadquery-ocp"),
        binding_module_version=str(OCP.__version__),
        step_processor=_step_processor(source_bytes),
        writer_status=_status_name(writer_status),
        reader_status=_status_name(reader_status),
        transferred_roots=transferred_roots,
        constructed_valid=constructed_valid,
        imported_valid=imported_valid,
        step_edge_curve_count=_entity_count(source_bytes, b"EDGE_CURVE"),
        step_surface_curve_count=_entity_count(source_bytes, b"SURFACE_CURVE"),
        step_pcurve_count=_entity_count(source_bytes, b"PCURVE"),
        step_seam_curve_count=_entity_count(source_bytes, b"SEAM_CURVE"),
        source_bytes=source_bytes,
        source_sha256=hashlib.sha256(source_bytes).hexdigest(),
        edge_observations=constructed_edges + imported_edges,
        pcurve_observations=constructed_pcurves + imported_pcurves,
    )
