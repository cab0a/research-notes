"""Produce stable face-level reports from controlled B-Rep shapes."""

from __future__ import annotations

import importlib.metadata
import math
from dataclasses import dataclass
from typing import Literal

from research_notes.brep_runtime import (
    StepRoundTrip,
    indexed_shapes,
    iter_shapes,
    status_name,
    step_round_trip,
    surface_area_and_centroid,
)


Vector3 = tuple[float, float, float]
ColorRGB = tuple[float, float, float]
FaceAnalysisStage = Literal["constructed", "step_imported"]
CONTRACT_VERSION = "1.0.0"
SUPPORTED_SURFACE_TYPES = (
    "plane",
    "cylinder",
    "cone",
    "sphere",
    "torus",
    "bspline",
)


@dataclass(frozen=True)
class FaceAnalysisControl:
    """Synthetic shape definition and independently declared report truth."""

    control_id: str
    condition: str
    expected_surface_counts: tuple[tuple[str, int], ...]
    expected_solid_count: int
    expected_shell_count: int
    shape_name: str
    shape_color_rgb: ColorRGB


@dataclass(frozen=True)
class SurfaceParameters:
    """Type-specific parameters normalized into one nullable field set."""

    surface_type: str
    kernel_surface_type: str
    surface_origin: Vector3 | None
    surface_axis: Vector3 | None
    surface_x_direction: Vector3 | None
    plane_normal: Vector3 | None
    radius: float | None
    secondary_radius: float | None
    semi_angle_degrees: float | None
    u_degree: int | None
    v_degree: int | None
    u_pole_count: int | None
    v_pole_count: int | None
    u_knot_count: int | None
    v_knot_count: int | None
    u_periodic: bool | None
    v_periodic: bool | None
    u_rational: bool | None
    v_rational: bool | None


@dataclass(frozen=True)
class FaceAnalysisRow:
    """One versioned face row independent of CSV serialization details."""

    contract_version: str
    stage: FaceAnalysisStage
    control_id: str
    source_file: str | None
    source_sha256: str | None
    analysis_face_index: int
    parent_solid_indices: tuple[int, ...]
    parent_shell_indices: tuple[int, ...]
    surface_type: str
    kernel_surface_type: str
    orientation: str
    area: float
    centroid: Vector3
    uv_bounds: tuple[float, float, float, float]
    representative_uv: tuple[float, float]
    representative_normal: Vector3
    surface_origin: Vector3 | None
    surface_axis: Vector3 | None
    surface_x_direction: Vector3 | None
    plane_normal: Vector3 | None
    radius: float | None
    secondary_radius: float | None
    semi_angle_degrees: float | None
    u_degree: int | None
    v_degree: int | None
    u_pole_count: int | None
    v_pole_count: int | None
    u_knot_count: int | None
    v_knot_count: int | None
    u_periodic: bool | None
    v_periodic: bool | None
    u_rational: bool | None
    v_rational: bool | None
    outer_wire_count: int
    inner_wire_count: int
    boundary_edge_count: int
    face_tolerance: float
    adjacent_face_indices: tuple[int, ...]
    name: str | None
    name_source: str
    color_rgb: ColorRGB | None
    color_source: str


@dataclass(frozen=True)
class FaceRoundTripMatch:
    """Geometry-based comparison that does not treat local indices as identity."""

    control_id: str
    constructed_face_index: int
    step_imported_face_index: int
    matched_by: str
    surface_type: str
    area_absolute_difference: float
    centroid_distance: float
    orientation_matches: bool
    outer_wire_count_matches: bool
    inner_wire_count_matches: bool
    boundary_edge_count_matches: bool


@dataclass(frozen=True)
class FaceAnalysisProbe:
    """Complete controlled face report, fixtures, and round-trip evidence."""

    controls: tuple[FaceAnalysisControl, ...]
    fixtures: tuple[StepRoundTrip, ...]
    rows: tuple[FaceAnalysisRow, ...]
    matches: tuple[FaceRoundTripMatch, ...]
    binding_distribution_version: str


def face_analysis_controls() -> tuple[FaceAnalysisControl, ...]:
    """Return the fixed v0.41.0 surface-family and topology controls."""
    return (
        FaceAnalysisControl(
            "through_hole_solid",
            "Block with one cylindrical through hole and inner planar wires",
            (("plane", 6), ("cylinder", 1)),
            1,
            1,
            "Synthetic Through-Hole Solid",
            (0.20, 0.45, 0.80),
        ),
        FaceAnalysisControl(
            "conical_solid",
            "Truncated cone with two planar caps",
            (("plane", 2), ("cone", 1)),
            1,
            1,
            "Synthetic Conical Solid",
            (0.90, 0.45, 0.15),
        ),
        FaceAnalysisControl(
            "spherical_solid",
            "Complete analytic sphere",
            (("sphere", 1),),
            1,
            1,
            "Synthetic Spherical Solid",
            (0.20, 0.70, 0.45),
        ),
        FaceAnalysisControl(
            "toroidal_solid",
            "Complete analytic torus",
            (("torus", 1),),
            1,
            1,
            "Synthetic Toroidal Solid",
            (0.65, 0.35, 0.80),
        ),
        FaceAnalysisControl(
            "bspline_shell",
            "Open shell containing one bounded bicubic B-spline face",
            (("bspline", 1),),
            0,
            1,
            "Synthetic B-Spline Shell",
            (0.15, 0.65, 0.70),
        ),
    )


def _through_hole_shape() -> object:
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    block = BRepPrimAPI_MakeBox(12.0, 8.0, 6.0).Shape()
    cutter = BRepPrimAPI_MakeCylinder(
        gp_Ax2(gp_Pnt(4.0, 4.0, -1.0), gp_Dir(0.0, 0.0, 1.0)),
        1.25,
        8.0,
    ).Shape()
    operation = BRepAlgoAPI_Cut(block, cutter)
    operation.Build()
    if not operation.IsDone():
        raise RuntimeError("controlled through-hole construction failed")
    return operation.Shape()


def _bspline_shell() -> object:
    from OCP.BRep import BRep_Builder
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.GeomAPI import GeomAPI_PointsToBSplineSurface
    from OCP.TColgp import TColgp_Array2OfPnt
    from OCP.TopoDS import TopoDS_Shell
    from OCP.gp import gp_Pnt

    points = TColgp_Array2OfPnt(1, 4, 1, 4)
    for u_index in range(1, 5):
        for v_index in range(1, 5):
            u_value = float(u_index - 1)
            v_value = float(v_index - 1)
            z_value = 0.15 * u_value * v_value
            points.SetValue(u_index, v_index, gp_Pnt(u_value, v_value, z_value))
    surface = GeomAPI_PointsToBSplineSurface(points).Surface()
    face_builder = BRepBuilderAPI_MakeFace(surface, 1.0e-7)
    if not face_builder.IsDone():
        raise RuntimeError("controlled B-spline face construction failed")
    face = face_builder.Face()
    builder = BRep_Builder()
    builder.UpdateFace(face, 2.0e-4)
    shell = TopoDS_Shell()
    builder.MakeShell(shell)
    builder.Add(shell, face)
    return shell


def build_face_analysis_shapes() -> dict[str, object]:
    """Construct the five deterministic face-report controls."""
    from OCP.BRepPrimAPI import (
        BRepPrimAPI_MakeCone,
        BRepPrimAPI_MakeSphere,
        BRepPrimAPI_MakeTorus,
    )

    return {
        "through_hole_solid": _through_hole_shape(),
        "conical_solid": BRepPrimAPI_MakeCone(3.0, 1.5, 5.0).Shape(),
        "spherical_solid": BRepPrimAPI_MakeSphere(2.0).Shape(),
        "toroidal_solid": BRepPrimAPI_MakeTorus(4.0, 1.0).Shape(),
        "bspline_shell": _bspline_shell(),
    }


def _xyz(value: object) -> Vector3:
    return (float(value.X()), float(value.Y()), float(value.Z()))


def _distance(first: Vector3, second: Vector3) -> float:
    return math.sqrt(
        sum(
            (first_value - second_value) ** 2
            for first_value, second_value in zip(first, second, strict=True)
        )
    )


def _orientation_name(face: object) -> str:
    from OCP.TopAbs import (
        TopAbs_EXTERNAL,
        TopAbs_FORWARD,
        TopAbs_INTERNAL,
        TopAbs_REVERSED,
    )

    value = face.Orientation()
    names = {
        TopAbs_FORWARD: "forward",
        TopAbs_REVERSED: "reversed",
        TopAbs_INTERNAL: "internal",
        TopAbs_EXTERNAL: "external",
    }
    return names.get(value, status_name(value).removeprefix("TopAbs_").lower())


def _position_parameters(surface: object) -> tuple[Vector3, Vector3, Vector3]:
    position = surface.Position()
    return (
        _xyz(position.Location()),
        _xyz(position.Direction()),
        _xyz(position.XDirection()),
    )


def _surface_parameters(adaptor: object) -> SurfaceParameters:
    from OCP.GeomAbs import (
        GeomAbs_BSplineSurface,
        GeomAbs_Cone,
        GeomAbs_Cylinder,
        GeomAbs_Plane,
        GeomAbs_Sphere,
        GeomAbs_Torus,
    )

    value = adaptor.GetType()
    raw_name = status_name(value)
    origin: Vector3 | None = None
    axis: Vector3 | None = None
    x_direction: Vector3 | None = None
    plane_normal: Vector3 | None = None
    radius: float | None = None
    secondary_radius: float | None = None
    semi_angle: float | None = None
    u_degree: int | None = None
    v_degree: int | None = None
    u_poles: int | None = None
    v_poles: int | None = None
    u_knots: int | None = None
    v_knots: int | None = None
    u_periodic: bool | None = None
    v_periodic: bool | None = None
    u_rational: bool | None = None
    v_rational: bool | None = None

    if value == GeomAbs_Plane:
        surface_type = "plane"
        plane = adaptor.Plane()
        origin, plane_normal, x_direction = _position_parameters(plane)
    elif value == GeomAbs_Cylinder:
        surface_type = "cylinder"
        cylinder = adaptor.Cylinder()
        origin, axis, x_direction = _position_parameters(cylinder)
        radius = float(cylinder.Radius())
    elif value == GeomAbs_Cone:
        surface_type = "cone"
        cone = adaptor.Cone()
        origin, axis, x_direction = _position_parameters(cone)
        radius = float(cone.RefRadius())
        semi_angle = math.degrees(float(cone.SemiAngle()))
    elif value == GeomAbs_Sphere:
        surface_type = "sphere"
        sphere = adaptor.Sphere()
        origin, axis, x_direction = _position_parameters(sphere)
        radius = float(sphere.Radius())
    elif value == GeomAbs_Torus:
        surface_type = "torus"
        torus = adaptor.Torus()
        origin, axis, x_direction = _position_parameters(torus)
        radius = float(torus.MajorRadius())
        secondary_radius = float(torus.MinorRadius())
    elif value == GeomAbs_BSplineSurface:
        surface_type = "bspline"
        bspline = adaptor.BSpline()
        u_degree = int(bspline.UDegree())
        v_degree = int(bspline.VDegree())
        u_poles = int(bspline.NbUPoles())
        v_poles = int(bspline.NbVPoles())
        u_knots = int(bspline.NbUKnots())
        v_knots = int(bspline.NbVKnots())
        u_periodic = bool(bspline.IsUPeriodic())
        v_periodic = bool(bspline.IsVPeriodic())
        u_rational = bool(bspline.IsURational())
        v_rational = bool(bspline.IsVRational())
    else:
        surface_type = "other"

    return SurfaceParameters(
        surface_type,
        raw_name,
        origin,
        axis,
        x_direction,
        plane_normal,
        radius,
        secondary_radius,
        semi_angle,
        u_degree,
        v_degree,
        u_poles,
        v_poles,
        u_knots,
        v_knots,
        u_periodic,
        v_periodic,
        u_rational,
        v_rational,
    )


def _representative_normal(
    face: object,
    adaptor: object,
    bounds: tuple[float, float, float, float],
) -> tuple[tuple[float, float], Vector3]:
    from OCP.TopAbs import TopAbs_REVERSED
    from OCP.gp import gp_Pnt, gp_Vec

    u_min, u_max, v_min, v_max = bounds
    fractions = ((0.5, 0.5), (0.37, 0.41), (0.63, 0.59))
    for u_fraction, v_fraction in fractions:
        u_value = u_min + u_fraction * (u_max - u_min)
        v_value = v_min + v_fraction * (v_max - v_min)
        point = gp_Pnt()
        d_u = gp_Vec()
        d_v = gp_Vec()
        adaptor.D1(u_value, v_value, point, d_u, d_v)
        cross = d_u.Crossed(d_v)
        if cross.Magnitude() <= 1.0e-14:
            continue
        cross.Normalize()
        if face.Orientation() == TopAbs_REVERSED:
            cross.Reverse()
        return (u_value, v_value), _xyz(cross)
    raise RuntimeError("no nonsingular representative normal sample was found")


def _parent_memberships(
    shape: object, face_map: object, parent_type: object
) -> dict[int, tuple[int, ...]]:
    from OCP.TopAbs import TopAbs_FACE

    result: dict[int, list[int]] = {
        face_index: [] for face_index in range(1, face_map.Extent() + 1)
    }
    parent_map = indexed_shapes(shape, parent_type)
    for parent_index in range(1, parent_map.Extent() + 1):
        parent = parent_map.FindKey(parent_index)
        for child in iter_shapes(parent, TopAbs_FACE):
            face_index = int(face_map.FindIndex(child))
            if face_index and parent_index not in result[face_index]:
                result[face_index].append(parent_index)
    return {key: tuple(sorted(value)) for key, value in result.items()}


def analyze_shape_faces(
    shape: object,
    *,
    control: FaceAnalysisControl,
    stage: FaceAnalysisStage,
    fixture: StepRoundTrip | None = None,
) -> tuple[FaceAnalysisRow, ...]:
    """Analyze every unique face and return deterministic local report rows."""
    if stage == "step_imported" and fixture is None:
        raise ValueError("step_imported analysis requires fixture provenance")
    if stage == "constructed" and fixture is not None:
        raise ValueError("constructed analysis must not claim STEP provenance")

    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepTools import BRepTools
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_SHELL, TopAbs_SOLID, TopAbs_WIRE
    from OCP.TopoDS import TopoDS

    face_map = indexed_shapes(shape, TopAbs_FACE)
    edge_map = indexed_shapes(shape, TopAbs_EDGE)
    solid_parents = _parent_memberships(shape, face_map, TopAbs_SOLID)
    shell_parents = _parent_memberships(shape, face_map, TopAbs_SHELL)
    edge_faces: dict[int, set[int]] = {
        edge_index: set() for edge_index in range(1, edge_map.Extent() + 1)
    }
    face_edges: dict[int, set[int]] = {
        face_index: set() for face_index in range(1, face_map.Extent() + 1)
    }
    faces = {
        face_index: TopoDS.Face_s(face_map.FindKey(face_index))
        for face_index in range(1, face_map.Extent() + 1)
    }
    for face_index, face in faces.items():
        for edge in iter_shapes(face, TopAbs_EDGE):
            edge_index = int(edge_map.FindIndex(edge))
            if edge_index:
                face_edges[face_index].add(edge_index)
                edge_faces[edge_index].add(face_index)

    if stage == "constructed":
        name = control.shape_name
        name_source = "synthetic_control_manifest:shape"
        color = control.shape_color_rgb
        color_source = "synthetic_control_manifest:shape"
    else:
        name = None
        name_source = "not_present:stepcontrol_topods_shape"
        color = None
        color_source = "not_present:stepcontrol_topods_shape"

    rows: list[FaceAnalysisRow] = []
    for face_index, face in faces.items():
        adaptor = BRepAdaptor_Surface(face, True)
        parameters = _surface_parameters(adaptor)
        bounds = tuple(float(value) for value in BRepTools.UVBounds_s(face))
        representative_uv, representative_normal = _representative_normal(
            face, adaptor, bounds  # type: ignore[arg-type]
        )
        area, centroid = surface_area_and_centroid(face)
        wires = tuple(iter_shapes(face, TopAbs_WIRE))
        outer_wire = BRepTools.OuterWire_s(face)
        outer_wire_count = int(not outer_wire.IsNull())
        inner_wire_count = sum(not wire.IsSame(outer_wire) for wire in wires)
        adjacent = tuple(
            sorted(
                {
                    other
                    for edge_index in face_edges[face_index]
                    for other in edge_faces[edge_index]
                    if other != face_index
                }
            )
        )
        rows.append(
            FaceAnalysisRow(
                CONTRACT_VERSION,
                stage,
                control.control_id,
                None if fixture is None else fixture.file_name,
                None if fixture is None else fixture.source_sha256,
                face_index,
                solid_parents[face_index],
                shell_parents[face_index],
                parameters.surface_type,
                parameters.kernel_surface_type,
                _orientation_name(face),
                area,
                centroid,
                bounds,  # type: ignore[arg-type]
                representative_uv,
                representative_normal,
                parameters.surface_origin,
                parameters.surface_axis,
                parameters.surface_x_direction,
                parameters.plane_normal,
                parameters.radius,
                parameters.secondary_radius,
                parameters.semi_angle_degrees,
                parameters.u_degree,
                parameters.v_degree,
                parameters.u_pole_count,
                parameters.v_pole_count,
                parameters.u_knot_count,
                parameters.v_knot_count,
                parameters.u_periodic,
                parameters.v_periodic,
                parameters.u_rational,
                parameters.v_rational,
                outer_wire_count,
                inner_wire_count,
                len(face_edges[face_index]),
                float(BRep_Tool.Tolerance_s(face)),
                adjacent,
                name,
                name_source,
                color,
                color_source,
            )
        )
    return tuple(rows)


def _surface_counts(rows: tuple[FaceAnalysisRow, ...]) -> tuple[tuple[str, int], ...]:
    return tuple(
        (surface_type, sum(item.surface_type == surface_type for item in rows))
        for surface_type in SUPPORTED_SURFACE_TYPES
        if any(item.surface_type == surface_type for item in rows)
    )


def _round_trip_matches(
    controls: tuple[FaceAnalysisControl, ...], rows: tuple[FaceAnalysisRow, ...]
) -> tuple[FaceRoundTripMatch, ...]:
    matches: list[FaceRoundTripMatch] = []
    for control in controls:
        constructed = [
            item
            for item in rows
            if item.control_id == control.control_id and item.stage == "constructed"
        ]
        remaining = [
            item
            for item in rows
            if item.control_id == control.control_id and item.stage == "step_imported"
        ]
        for source in constructed:
            candidates = [
                item for item in remaining if item.surface_type == source.surface_type
            ]
            if not candidates:
                raise RuntimeError(
                    f"missing imported {source.surface_type} face for {control.control_id}"
                )
            target = min(
                candidates,
                key=lambda item: (
                    _distance(source.centroid, item.centroid),
                    abs(source.area - item.area),
                    item.analysis_face_index,
                ),
            )
            remaining.remove(target)
            matches.append(
                FaceRoundTripMatch(
                    control.control_id,
                    source.analysis_face_index,
                    target.analysis_face_index,
                    "surface_type_then_nearest_centroid",
                    source.surface_type,
                    abs(source.area - target.area),
                    _distance(source.centroid, target.centroid),
                    source.orientation == target.orientation,
                    source.outer_wire_count == target.outer_wire_count,
                    source.inner_wire_count == target.inner_wire_count,
                    source.boundary_edge_count == target.boundary_edge_count,
                )
            )
        if remaining:
            raise RuntimeError(f"unmatched imported faces remain for {control.control_id}")
    return tuple(matches)


def probe_face_analysis() -> FaceAnalysisProbe:
    """Build, exchange, and report the complete v0.41.0 control corpus."""
    controls = face_analysis_controls()
    shapes = build_face_analysis_shapes()
    fixtures: list[StepRoundTrip] = []
    rows: list[FaceAnalysisRow] = []
    for control in controls:
        shape = shapes[control.control_id]
        fixture = step_round_trip(shape, control.control_id)
        fixtures.append(fixture)
        constructed = analyze_shape_faces(
            shape, control=control, stage="constructed"
        )
        imported = analyze_shape_faces(
            fixture.imported_shape,
            control=control,
            stage="step_imported",
            fixture=fixture,
        )
        expected_counts = control.expected_surface_counts
        if _surface_counts(constructed) != expected_counts:
            raise RuntimeError(
                f"constructed surface inventory changed for {control.control_id}"
            )
        if _surface_counts(imported) != expected_counts:
            raise RuntimeError(
                f"imported surface inventory changed for {control.control_id}"
            )
        if any(len(item.parent_solid_indices) != control.expected_solid_count for item in constructed + imported):
            raise RuntimeError(f"solid parent inventory changed for {control.control_id}")
        if any(len(item.parent_shell_indices) != control.expected_shell_count for item in constructed + imported):
            raise RuntimeError(f"shell parent inventory changed for {control.control_id}")
        rows.extend(constructed)
        rows.extend(imported)
    row_tuple = tuple(rows)
    return FaceAnalysisProbe(
        controls,
        tuple(fixtures),
        row_tuple,
        _round_trip_matches(controls, row_tuple),
        importlib.metadata.version("cadquery-ocp"),
    )
