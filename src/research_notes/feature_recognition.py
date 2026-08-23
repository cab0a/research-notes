"""Recognize controlled geometric feature candidates from B-Rep evidence."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from research_notes.brep_runtime import (
    StepRoundTrip,
    indexed_shapes,
    iter_shapes,
    signed_volume,
    status_name,
    step_round_trip,
    surface_area_and_centroid,
    topology_counts,
)


FeatureStage = Literal["constructed", "step_imported"]
Vector3 = tuple[float, float, float]
LENGTH_TRUTH_TOLERANCE = 1.0e-8
ANGLE_TRUTH_TOLERANCE_DEGREES = 1.0e-8
BOUNDARY_EQUIVALENCE_TOLERANCE = 1.0e-8


@dataclass(frozen=True)
class FeatureControl:
    """Synthetic feature truth kept outside the recognition rules."""

    control_id: str
    condition: str
    expected_candidate_types: tuple[str, ...]
    expected_subtypes: tuple[str, ...]
    history_label: str
    expected_primary_size: float | None
    expected_secondary_size: float | None
    expected_depth: float | None
    expected_angle_degrees: float | None


@dataclass(frozen=True)
class FeatureFaceAttribute:
    """One node in the controlled attributed face-adjacency graph."""

    stage: FeatureStage
    control_id: str
    face_index: int
    surface_type: str
    area: float
    centroid: Vector3
    normal: Vector3
    u_span: float
    v_span: float
    axis_origin: Vector3 | None
    axis_direction: Vector3 | None
    radius: float | None
    radial_polarity: float | None
    maximum_absolute_curvature: float | None
    wire_count: int
    inner_wire_count: int
    edge_count: int
    maximum_edge_length: float
    adjacent_face_indices: tuple[int, ...]


@dataclass(frozen=True)
class FeatureAdjacency:
    """One shared-edge relation between two face nodes."""

    stage: FeatureStage
    control_id: str
    edge_index: int
    first_face_index: int
    second_face_index: int
    curve_type: str
    length: float
    normal_dot: float
    representative_normals_parallel: bool


@dataclass(frozen=True)
class FeatureCandidate:
    """One rule-derived geometric candidate and its independent truth label."""

    stage: FeatureStage
    control_id: str
    candidate_index: int
    candidate_type: str
    subtype: str
    face_indices: tuple[int, ...]
    primary_size: float | None
    secondary_size: float | None
    depth: float | None
    angle_degrees: float | None
    expected_primary_size: float | None
    expected_secondary_size: float | None
    expected_depth: float | None
    expected_angle_degrees: float | None
    primary_size_absolute_error: float | None
    secondary_size_absolute_error: float | None
    depth_absolute_error: float | None
    angle_absolute_error_degrees: float | None
    geometric_candidate: bool
    construction_history_label: str
    design_intent_proven: bool
    classification_matches_truth: bool
    dimension_matches_truth: bool
    truth_correct: bool


@dataclass(frozen=True)
class EquivalentBoundaryObservation:
    """Bidirectional material and topology evidence for equivalent controls."""

    stage: FeatureStage
    first_control_id: str
    second_control_id: str
    first_vertex_count: int
    first_edge_count: int
    first_face_count: int
    first_shell_count: int
    first_solid_count: int
    second_vertex_count: int
    second_edge_count: int
    second_face_count: int
    second_shell_count: int
    second_solid_count: int
    topology_matches: bool
    first_volume: float
    second_volume: float
    volume_absolute_difference: float
    first_minus_second_volume: float
    second_minus_first_volume: float
    boundary_equivalent: bool


@dataclass(frozen=True)
class FeatureRecognitionProbe:
    """Complete constructed and STEP-imported feature evidence."""

    controls: tuple[FeatureControl, ...]
    fixtures: tuple[StepRoundTrip, ...]
    faces: tuple[FeatureFaceAttribute, ...]
    adjacencies: tuple[FeatureAdjacency, ...]
    candidates: tuple[FeatureCandidate, ...]
    equivalent_boundaries: tuple[EquivalentBoundaryObservation, ...]
    preview_shapes: tuple[tuple[str, FeatureStage, object], ...]


def round_trip_dimension_differences(
    probe: FeatureRecognitionProbe,
) -> tuple[float, float]:
    """Return maximum length-like and angular differences across STEP import."""
    constructed = {
        (item.control_id, item.candidate_type, item.subtype): item
        for item in probe.candidates
        if item.stage == "constructed"
    }
    length_differences: list[float] = []
    angle_differences: list[float] = []
    for imported in (
        item for item in probe.candidates if item.stage == "step_imported"
    ):
        source = constructed[
            (imported.control_id, imported.candidate_type, imported.subtype)
        ]
        for source_value, imported_value in (
            (source.primary_size, imported.primary_size),
            (source.secondary_size, imported.secondary_size),
            (source.depth, imported.depth),
        ):
            if source_value is not None and imported_value is not None:
                length_differences.append(abs(source_value - imported_value))
        if source.angle_degrees is not None and imported.angle_degrees is not None:
            angle_differences.append(abs(source.angle_degrees - imported.angle_degrees))
    return max(length_differences, default=0.0), max(angle_differences, default=0.0)


def truth_dimension_errors(
    probe: FeatureRecognitionProbe,
) -> tuple[float, float]:
    """Return maximum candidate-to-truth length and angle errors."""
    length_errors = [
        value
        for item in probe.candidates
        for value in (
            item.primary_size_absolute_error,
            item.secondary_size_absolute_error,
            item.depth_absolute_error,
        )
        if value is not None
    ]
    angle_errors = [
        item.angle_absolute_error_degrees
        for item in probe.candidates
        if item.angle_absolute_error_degrees is not None
    ]
    return max(length_errors, default=0.0), max(angle_errors, default=0.0)


def recovered_dimension_series(
    probe: FeatureRecognitionProbe,
) -> tuple[tuple[str, float], ...]:
    """Return plotted dimensions from constructed-stage recognition results."""
    requested = (
        ("Through hole Ø", "through_hole", "primary_size"),
        ("Blind depth", "blind_hole", "depth"),
        ("Step height", "stepped_block", "primary_size"),
        ("Slot width", "through_slot", "primary_size"),
        ("Slot length", "through_slot", "secondary_size"),
        ("Chamfer", "chamfer_operation", "primary_size"),
        ("Fillet R", "fillet_operation", "primary_size"),
    )
    candidates = {
        item.control_id: item
        for item in probe.candidates
        if item.stage == "constructed"
    }
    rows: list[tuple[str, float]] = []
    for label, control_id, attribute in requested:
        value = getattr(candidates[control_id], attribute)
        if value is None:
            raise RuntimeError(
                f"missing recovered dimension {attribute} for {control_id}"
            )
        rows.append((label, float(value)))
    return tuple(rows)


def feature_controls() -> tuple[FeatureControl, ...]:
    """Return the preregistered isolated feature and confounder controls."""
    return (
        FeatureControl(
            "plain_block",
            "Feature-free rectangular block",
            (),
            (),
            "primitive",
            None,
            None,
            None,
            None,
        ),
        FeatureControl(
            "through_hole",
            "Round through hole",
            ("hole",),
            ("through",),
            "boolean_cut",
            2.5,
            None,
            6.0,
            None,
        ),
        FeatureControl(
            "blind_hole",
            "Flat-bottom blind hole",
            ("hole",),
            ("blind",),
            "boolean_cut",
            2.0,
            None,
            3.5,
            None,
        ),
        FeatureControl(
            "stepped_block",
            "Two parallel levels joined by one riser",
            ("step",),
            ("open",),
            "direct_profile",
            2.0,
            8.0,
            None,
            None,
        ),
        FeatureControl(
            "through_slot",
            "Straight capsule slot through a plate",
            ("slot",),
            ("through",),
            "boolean_cut",
            2.0,
            6.0,
            4.0,
            None,
        ),
        FeatureControl(
            "chamfer_operation",
            "Symmetric edge chamfer",
            ("chamfer_like",),
            ("symmetric",),
            "chamfer_operation",
            1.0,
            None,
            None,
            45.0,
        ),
        FeatureControl(
            "equivalent_bevel",
            "Direct profile with chamfer-equivalent boundary",
            ("chamfer_like",),
            ("symmetric",),
            "direct_profile",
            1.0,
            None,
            None,
            45.0,
        ),
        FeatureControl(
            "fillet_operation",
            "Constant-radius edge fillet",
            ("fillet_like",),
            ("constant_radius",),
            "fillet_operation",
            1.0,
            8.0,
            None,
            90.0,
        ),
        FeatureControl(
            "cylindrical_boss",
            "External cylinder confounding a hole-only rule",
            (),
            (),
            "boolean_fuse",
            None,
            None,
            None,
            None,
        ),
    )


def _polygon_face(points: tuple[Vector3, ...]) -> object:
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
    from OCP.gp import gp_Pnt

    polygon = BRepBuilderAPI_MakePolygon()
    for point in points:
        polygon.Add(gp_Pnt(*point))
    polygon.Close()
    return BRepBuilderAPI_MakeFace(polygon.Wire()).Face()


def _cut(first: object, second: object) -> object:
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut

    operation = BRepAlgoAPI_Cut(first, second)
    operation.Build()
    if not operation.IsDone():
        raise RuntimeError("controlled Boolean cut failed")
    return operation.Shape()


def _fuse(first: object, second: object) -> object:
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse

    operation = BRepAlgoAPI_Fuse(first, second)
    operation.Build()
    if not operation.IsDone():
        raise RuntimeError("controlled Boolean fuse failed")
    return operation.Shape()


def _vertical_cylinder(
    x: float, y: float, z: float, radius: float, height: float
) -> object:
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    return BRepPrimAPI_MakeCylinder(
        gp_Ax2(gp_Pnt(x, y, z), gp_Dir(0.0, 0.0, 1.0)), radius, height
    ).Shape()


def _edge_at(shape: object, *, x: float, z: float) -> object:
    from OCP.BRep import BRep_Tool
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_VERTEX
    from OCP.TopoDS import TopoDS

    matches: list[object] = []
    edge_map = indexed_shapes(shape, TopAbs_EDGE)
    for edge_index in range(1, edge_map.Extent() + 1):
        edge_shape = edge_map.FindKey(edge_index)
        points = []
        for vertex_shape in iter_shapes(edge_shape, TopAbs_VERTEX):
            point = BRep_Tool.Pnt_s(TopoDS.Vertex_s(vertex_shape))
            points.append((point.X(), point.Y(), point.Z()))
        if len(points) == 2 and all(
            math.isclose(point[0], x, abs_tol=1.0e-9)
            and math.isclose(point[2], z, abs_tol=1.0e-9)
            for point in points
        ):
            matches.append(TopoDS.Edge_s(edge_shape))
    if len(matches) != 1:
        raise RuntimeError(
            f"expected one controlled edge at x={x}, z={z}; found {len(matches)}"
        )
    return matches[0]


def _capsule_prism() -> object:
    from OCP.BRepBuilderAPI import (
        BRepBuilderAPI_MakeEdge,
        BRepBuilderAPI_MakeFace,
        BRepBuilderAPI_MakeWire,
    )
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.GC import GC_MakeArcOfCircle
    from OCP.gp import gp_Pnt, gp_Vec

    p1 = gp_Pnt(5.0, 4.0, -1.0)
    p2 = gp_Pnt(9.0, 4.0, -1.0)
    p3 = gp_Pnt(9.0, 6.0, -1.0)
    p4 = gp_Pnt(5.0, 6.0, -1.0)
    edges = (
        BRepBuilderAPI_MakeEdge(p1, p2).Edge(),
        BRepBuilderAPI_MakeEdge(
            GC_MakeArcOfCircle(p2, gp_Pnt(10.0, 5.0, -1.0), p3).Value()
        ).Edge(),
        BRepBuilderAPI_MakeEdge(p3, p4).Edge(),
        BRepBuilderAPI_MakeEdge(
            GC_MakeArcOfCircle(p4, gp_Pnt(4.0, 5.0, -1.0), p1).Value()
        ).Edge(),
    )
    wire = BRepBuilderAPI_MakeWire()
    for edge in edges:
        wire.Add(edge)
    face = BRepBuilderAPI_MakeFace(wire.Wire()).Face()
    return BRepPrimAPI_MakePrism(face, gp_Vec(0.0, 0.0, 6.0)).Shape()


def build_feature_shapes() -> dict[str, object]:
    """Construct all deterministic feature-recognition controls."""
    from OCP.BRepFilletAPI import BRepFilletAPI_MakeChamfer, BRepFilletAPI_MakeFillet
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakePrism
    from OCP.gp import gp_Vec

    plain = BRepPrimAPI_MakeBox(12.0, 8.0, 6.0).Shape()
    through = _cut(plain, _vertical_cylinder(4.0, 4.0, -1.0, 1.25, 8.0))
    blind = _cut(plain, _vertical_cylinder(4.0, 4.0, 2.5, 1.0, 4.5))
    step_profile = _polygon_face(
        (
            (0.0, 0.0, 0.0),
            (12.0, 0.0, 0.0),
            (12.0, 0.0, 3.0),
            (5.0, 0.0, 3.0),
            (5.0, 0.0, 5.0),
            (0.0, 0.0, 5.0),
        )
    )
    stepped = BRepPrimAPI_MakePrism(step_profile, gp_Vec(0.0, 8.0, 0.0)).Shape()
    slot_block = BRepPrimAPI_MakeBox(14.0, 10.0, 4.0).Shape()
    slot = _cut(slot_block, _capsule_prism())

    chamfer_builder = BRepFilletAPI_MakeChamfer(plain)
    chamfer_builder.Add(1.0, _edge_at(plain, x=12.0, z=6.0))
    chamfer_builder.Build()
    if not chamfer_builder.IsDone():
        raise RuntimeError("controlled chamfer construction failed")
    chamfer = chamfer_builder.Shape()

    bevel_profile = _polygon_face(
        (
            (0.0, 0.0, 0.0),
            (12.0, 0.0, 0.0),
            (12.0, 0.0, 5.0),
            (11.0, 0.0, 6.0),
            (0.0, 0.0, 6.0),
        )
    )
    bevel = BRepPrimAPI_MakePrism(bevel_profile, gp_Vec(0.0, 8.0, 0.0)).Shape()

    fillet_builder = BRepFilletAPI_MakeFillet(plain)
    fillet_builder.Add(1.0, _edge_at(plain, x=12.0, z=6.0))
    fillet_builder.Build()
    if not fillet_builder.IsDone():
        raise RuntimeError("controlled fillet construction failed")
    fillet = fillet_builder.Shape()

    boss = _fuse(plain, _vertical_cylinder(4.0, 4.0, 6.0, 1.25, 2.0))
    return {
        "plain_block": plain,
        "through_hole": through,
        "blind_hole": blind,
        "stepped_block": stepped,
        "through_slot": slot,
        "chamfer_operation": chamfer,
        "equivalent_bevel": bevel,
        "fillet_operation": fillet,
        "cylindrical_boss": boss,
    }


def _normalize(vector: Vector3) -> Vector3:
    length = math.sqrt(sum(value * value for value in vector))
    if length <= 1.0e-15:
        return (0.0, 0.0, 0.0)
    return tuple(value / length for value in vector)


def _dot(first: Vector3, second: Vector3) -> float:
    return sum(a * b for a, b in zip(first, second, strict=True))


def _absolute_error(observed: float | None, expected: float | None) -> float | None:
    if observed is None or expected is None:
        return None
    return abs(observed - expected)


def _dimension_matches(
    observed: float | None, expected: float | None, tolerance: float
) -> bool:
    if expected is None:
        return observed is None
    return observed is not None and abs(observed - expected) <= tolerance


def _equivalent_boundary_observation(
    stage: FeatureStage,
    first_control_id: str,
    first: object,
    second_control_id: str,
    second: object,
) -> EquivalentBoundaryObservation:
    first_topology = topology_counts(first)
    second_topology = topology_counts(second)
    first_volume = signed_volume(first)
    second_volume = signed_volume(second)
    first_minus_second_volume = abs(signed_volume(_cut(first, second)))
    second_minus_first_volume = abs(signed_volume(_cut(second, first)))
    volume_difference = abs(first_volume - second_volume)
    topology_matches = first_topology == second_topology
    equivalent = (
        topology_matches
        and volume_difference <= BOUNDARY_EQUIVALENCE_TOLERANCE
        and first_minus_second_volume <= BOUNDARY_EQUIVALENCE_TOLERANCE
        and second_minus_first_volume <= BOUNDARY_EQUIVALENCE_TOLERANCE
    )
    return EquivalentBoundaryObservation(
        stage,
        first_control_id,
        second_control_id,
        *first_topology,
        *second_topology,
        topology_matches,
        first_volume,
        second_volume,
        volume_difference,
        first_minus_second_volume,
        second_minus_first_volume,
        equivalent,
    )


def _face_geometry(
    face: object,
) -> tuple[
    str,
    Vector3,
    float,
    float,
    Vector3 | None,
    Vector3 | None,
    float | None,
    float | None,
    float | None,
]:
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepLProp import BRepLProp_SLProps
    from OCP.BRepTools import BRepTools
    from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
    from OCP.TopAbs import TopAbs_REVERSED
    from OCP.gp import gp_Pnt, gp_Vec

    adaptor = BRepAdaptor_Surface(face, True)
    bounds = tuple(float(value) for value in BRepTools.UVBounds_s(face))
    u_mid = (bounds[0] + bounds[1]) / 2.0
    v_mid = (bounds[2] + bounds[3]) / 2.0
    point = gp_Pnt()
    du = gp_Vec()
    dv = gp_Vec()
    adaptor.D1(u_mid, v_mid, point, du, dv)
    cross = du.Crossed(dv)
    normal = _normalize((cross.X(), cross.Y(), cross.Z()))
    if face.Orientation() == TopAbs_REVERSED:
        normal = tuple(-value for value in normal)

    surface_value = adaptor.GetType()
    axis_origin: Vector3 | None = None
    axis_direction: Vector3 | None = None
    radius: float | None = None
    polarity: float | None = None
    if surface_value == GeomAbs_Plane:
        surface_type = "plane"
    elif surface_value == GeomAbs_Cylinder:
        surface_type = "cylinder"
        cylinder = adaptor.Cylinder()
        location = cylinder.Axis().Location()
        direction = cylinder.Axis().Direction()
        axis_origin = (location.X(), location.Y(), location.Z())
        axis_direction = _normalize((direction.X(), direction.Y(), direction.Z()))
        radius = float(cylinder.Radius())
        relative = tuple(
            coordinate - origin
            for coordinate, origin in zip(
                (point.X(), point.Y(), point.Z()), axis_origin, strict=True
            )
        )
        axial = _dot(relative, axis_direction)
        radial = _normalize(
            tuple(
                value - axial * direction_value
                for value, direction_value in zip(relative, axis_direction, strict=True)
            )
        )
        polarity = _dot(normal, radial)
    else:
        surface_type = status_name(surface_value).removeprefix("GeomAbs_").lower()

    curvature: float | None = None
    try:
        properties = BRepLProp_SLProps(adaptor, u_mid, v_mid, 2, 1.0e-9)
        if properties.IsCurvatureDefined():
            curvature = max(
                abs(float(properties.MinCurvature())),
                abs(float(properties.MaxCurvature())),
            )
    except (RuntimeError, TypeError):
        curvature = None
    return (
        surface_type,
        normal,
        abs(bounds[1] - bounds[0]),
        abs(bounds[3] - bounds[2]),
        axis_origin,
        axis_direction,
        radius,
        polarity,
        curvature,
    )


def _measure_graph(
    control_id: str, stage: FeatureStage, shape: object
) -> tuple[tuple[FeatureFaceAttribute, ...], tuple[FeatureAdjacency, ...]]:
    from OCP.BRepGProp import BRepGProp
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepTools import BRepTools
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_WIRE
    from OCP.TopoDS import TopoDS

    face_map = indexed_shapes(shape, TopAbs_FACE)
    edge_map = indexed_shapes(shape, TopAbs_EDGE)
    faces = tuple(
        TopoDS.Face_s(face_map.FindKey(index))
        for index in range(1, face_map.Extent() + 1)
    )
    edge_faces: dict[int, set[int]] = {
        index: set() for index in range(1, edge_map.Extent() + 1)
    }
    face_edges: dict[int, set[int]] = {
        index: set() for index in range(1, len(faces) + 1)
    }
    for face_index, face in enumerate(faces, start=1):
        for edge in iter_shapes(face, TopAbs_EDGE):
            edge_index = int(edge_map.FindIndex(edge))
            if edge_index:
                edge_faces[edge_index].add(face_index)
                face_edges[face_index].add(edge_index)

    partial: list[dict[str, object]] = []
    for face_index, face in enumerate(faces, start=1):
        area, centroid = surface_area_and_centroid(face)
        geometry = _face_geometry(face)
        outer = BRepTools.OuterWire_s(face)
        wires = tuple(iter_shapes(face, TopAbs_WIRE))
        inner_count = sum(not wire.IsSame(outer) for wire in wires)
        adjacent = sorted(
            {
                other
                for edge_index in face_edges[face_index]
                for other in edge_faces[edge_index]
                if other != face_index
            }
        )
        edge_lengths: list[float] = []
        for edge_index in face_edges[face_index]:
            edge_properties = GProp_GProps()
            BRepGProp.LinearProperties_s(
                TopoDS.Edge_s(edge_map.FindKey(edge_index)), edge_properties
            )
            edge_lengths.append(float(edge_properties.Mass()))
        partial.append(
            {
                "stage": stage,
                "control_id": control_id,
                "face_index": face_index,
                "surface_type": geometry[0],
                "area": area,
                "centroid": centroid,
                "normal": geometry[1],
                "u_span": geometry[2],
                "v_span": geometry[3],
                "axis_origin": geometry[4],
                "axis_direction": geometry[5],
                "radius": geometry[6],
                "radial_polarity": geometry[7],
                "maximum_absolute_curvature": geometry[8],
                "wire_count": len(wires),
                "inner_wire_count": inner_count,
                "edge_count": len(face_edges[face_index]),
                "maximum_edge_length": max(edge_lengths, default=0.0),
                "adjacent_face_indices": tuple(adjacent),
            }
        )
    attributes = tuple(FeatureFaceAttribute(**item) for item in partial)
    by_index = {item.face_index: item for item in attributes}

    adjacencies: list[FeatureAdjacency] = []
    for edge_index, owners in edge_faces.items():
        if len(owners) != 2:
            continue
        first, second = sorted(owners)
        edge = TopoDS.Edge_s(edge_map.FindKey(edge_index))
        properties = GProp_GProps()
        BRepGProp.LinearProperties_s(edge, properties)
        adaptor = BRepAdaptor_Curve(edge)
        curve_type = status_name(adaptor.GetType()).removeprefix("GeomAbs_").lower()
        normal_dot = _dot(by_index[first].normal, by_index[second].normal)
        adjacencies.append(
            FeatureAdjacency(
                stage,
                control_id,
                edge_index,
                first,
                second,
                curve_type,
                float(properties.Mass()),
                normal_dot,
                abs(normal_dot) >= 1.0 - 1.0e-6,
            )
        )
    return attributes, tuple(adjacencies)


def _axis_aligned(normal: Vector3) -> bool:
    return max(abs(value) for value in normal) >= 1.0 - 1.0e-7


def _recognize(
    control: FeatureControl,
    stage: FeatureStage,
    faces: tuple[FeatureFaceAttribute, ...],
) -> tuple[FeatureCandidate, ...]:
    by_index = {face.face_index: face for face in faces}
    candidates: list[
        tuple[
            str,
            str,
            tuple[int, ...],
            float | None,
            float | None,
            float | None,
            float | None,
        ]
    ] = []
    consumed_curved: set[int] = set()

    full_period_cylinders = [
        face
        for face in faces
        if face.surface_type == "cylinder"
        and abs(face.u_span - 2.0 * math.pi) <= 1.0e-5
    ]
    for face in full_period_cylinders:
        if face.radial_polarity is None or face.radial_polarity >= -0.5:
            continue
        adjacent_planes = [
            by_index[index]
            for index in face.adjacent_face_indices
            if by_index[index].surface_type == "plane"
        ]
        blind_caps = [
            item
            for item in adjacent_planes
            if item.wire_count == 1
            and item.edge_count == 1
            and face.radius is not None
            and abs(item.area - math.pi * face.radius**2) <= 1.0e-5
        ]
        subtype = "blind" if blind_caps else "through"
        depth = (
            None if face.radius is None else face.area / (2.0 * math.pi * face.radius)
        )
        evidence_faces = tuple(
            sorted((face.face_index, *(item.face_index for item in blind_caps)))
        )
        candidates.append(
            (
                "hole",
                subtype,
                evidence_faces,
                2.0 * face.radius if face.radius else None,
                None,
                depth,
                None,
            )
        )
        consumed_curved.add(face.face_index)

    partial_negative = [
        face
        for face in faces
        if face.surface_type == "cylinder"
        and face.radial_polarity is not None
        and face.radial_polarity < -0.5
        and face.face_index not in consumed_curved
    ]
    if len(partial_negative) == 2:
        first, second = partial_negative
        if (
            first.radius is not None
            and second.radius is not None
            and math.isclose(first.radius, second.radius, abs_tol=1.0e-6)
        ):
            shared_planes = sorted(
                set(first.adjacent_face_indices)
                & set(second.adjacent_face_indices)
                & {
                    face.face_index
                    for face in faces
                    if face.surface_type == "plane"
                    and first.axis_direction is not None
                    and abs(_dot(face.normal, first.axis_direction)) <= 1.0e-7
                }
            )
            if len(shared_planes) >= 2 and first.axis_origin and second.axis_origin:
                center_distance = math.sqrt(
                    sum(
                        (a - b) ** 2
                        for a, b in zip(
                            first.axis_origin, second.axis_origin, strict=True
                        )
                    )
                )
                radius = first.radius
                depth = first.area / (math.pi * radius)
                group = tuple(
                    sorted((first.face_index, second.face_index, *shared_planes[:2]))
                )
                candidates.append(
                    (
                        "slot",
                        "through",
                        group,
                        2.0 * radius,
                        center_distance + 2.0 * radius,
                        depth,
                        None,
                    )
                )
                consumed_curved.update((first.face_index, second.face_index))

    diagonal_planes = [
        face
        for face in faces
        if face.surface_type == "plane"
        and sum(abs(value) > 1.0e-6 for value in face.normal) == 2
        and math.isclose(
            sorted(abs(value) for value in face.normal)[1],
            math.sqrt(0.5),
            abs_tol=1.0e-6,
        )
        and math.isclose(
            sorted(abs(value) for value in face.normal)[2],
            math.sqrt(0.5),
            abs_tol=1.0e-6,
        )
    ]
    for face in diagonal_planes:
        parent_planes = [
            index
            for index in face.adjacent_face_indices
            if by_index[index].surface_type == "plane"
            and _axis_aligned(by_index[index].normal)
            and math.isclose(
                abs(_dot(face.normal, by_index[index].normal)),
                math.sqrt(0.5),
                abs_tol=1.0e-6,
            )
        ]
        if (
            len(parent_planes) == 2
            and abs(
                _dot(
                    by_index[parent_planes[0]].normal,
                    by_index[parent_planes[1]].normal,
                )
            )
            < 1.0 - 1.0e-6
        ):
            long_edges = max(face.maximum_edge_length, 1.0e-12)
            distance = face.area / long_edges / math.sqrt(2.0)
            group = tuple(sorted((face.face_index, *parent_planes)))
            candidates.append(
                ("chamfer_like", "symmetric", group, distance, None, None, 45.0)
            )

    horizontal_up = [
        face
        for face in faces
        if face.surface_type == "plane" and face.normal[2] > 1.0 - 1.0e-7
    ]
    all_axis_planar = all(
        face.surface_type == "plane" and _axis_aligned(face.normal) for face in faces
    )
    if all_axis_planar and len(horizontal_up) >= 2:
        ordered = sorted(horizontal_up, key=lambda face: face.centroid[2])
        lower, upper = ordered[0], ordered[-1]
        common_risers = [
            face
            for face in faces
            if face.surface_type == "plane"
            and abs(face.normal[2]) <= 1.0e-7
            and face.face_index in lower.adjacent_face_indices
            and face.face_index in upper.adjacent_face_indices
        ]
        if common_risers:
            riser = min(common_risers, key=lambda face: face.face_index)
            height = abs(upper.centroid[2] - lower.centroid[2])
            candidates.append(
                (
                    "step",
                    "open",
                    tuple(
                        sorted((lower.face_index, riser.face_index, upper.face_index))
                    ),
                    height,
                    riser.area / height,
                    None,
                    None,
                )
            )

    for face in faces:
        if face.face_index in consumed_curved or face.surface_type == "plane":
            continue
        if (
            face.surface_type == "cylinder"
            and abs(face.u_span - 2.0 * math.pi) <= 1.0e-5
        ):
            continue
        adjacent_planes = [
            index
            for index in face.adjacent_face_indices
            if by_index[index].surface_type == "plane"
            and (
                face.axis_direction is None
                or abs(_dot(by_index[index].normal, face.axis_direction)) <= 1.0e-7
            )
        ]
        if (
            len(adjacent_planes) != 2
            or abs(
                _dot(
                    by_index[adjacent_planes[0]].normal,
                    by_index[adjacent_planes[1]].normal,
                )
            )
            >= 1.0 - 1.0e-6
        ):
            continue
        radius = face.radius
        if (
            radius is None
            and face.maximum_absolute_curvature
            and face.maximum_absolute_curvature > 1.0e-12
        ):
            radius = 1.0 / face.maximum_absolute_curvature
        if radius is None:
            continue
        axial_length = face.maximum_edge_length
        sweep = math.degrees(face.area / max(radius * axial_length, 1.0e-12))
        if 45.0 <= sweep <= 135.0:
            group = tuple(sorted((face.face_index, *adjacent_planes)))
            candidates.append(
                (
                    "fillet_like",
                    "constant_radius",
                    group,
                    radius,
                    axial_length,
                    None,
                    sweep,
                )
            )

    expected_pairs = sorted(
        zip(control.expected_candidate_types, control.expected_subtypes, strict=True)
    )
    observed_pairs = sorted((item[0], item[1]) for item in candidates)
    classification_matches = observed_pairs == expected_pairs
    result: list[FeatureCandidate] = []
    for index, item in enumerate(
        sorted(candidates, key=lambda value: (value[0], value[2])), start=1
    ):
        primary_error = _absolute_error(item[3], control.expected_primary_size)
        secondary_error = _absolute_error(item[4], control.expected_secondary_size)
        depth_error = _absolute_error(item[5], control.expected_depth)
        angle_error = _absolute_error(item[6], control.expected_angle_degrees)
        dimension_matches = all(
            (
                _dimension_matches(
                    item[3], control.expected_primary_size, LENGTH_TRUTH_TOLERANCE
                ),
                _dimension_matches(
                    item[4], control.expected_secondary_size, LENGTH_TRUTH_TOLERANCE
                ),
                _dimension_matches(
                    item[5], control.expected_depth, LENGTH_TRUTH_TOLERANCE
                ),
                _dimension_matches(
                    item[6],
                    control.expected_angle_degrees,
                    ANGLE_TRUTH_TOLERANCE_DEGREES,
                ),
            )
        )
        result.append(
            FeatureCandidate(
                stage,
                control.control_id,
                index,
                item[0],
                item[1],
                item[2],
                item[3],
                item[4],
                item[5],
                item[6],
                control.expected_primary_size,
                control.expected_secondary_size,
                control.expected_depth,
                control.expected_angle_degrees,
                primary_error,
                secondary_error,
                depth_error,
                angle_error,
                True,
                control.history_label,
                False,
                classification_matches,
                dimension_matches,
                classification_matches and dimension_matches,
            )
        )
    return tuple(result)


def probe_feature_recognition() -> FeatureRecognitionProbe:
    """Run feature recognition before and after deterministic STEP exchange."""
    controls = feature_controls()
    shapes = build_feature_shapes()
    fixtures: list[StepRoundTrip] = []
    faces: list[FeatureFaceAttribute] = []
    adjacencies: list[FeatureAdjacency] = []
    candidates: list[FeatureCandidate] = []
    previews: list[tuple[str, FeatureStage, object]] = []
    stage_shapes: dict[tuple[str, FeatureStage], object] = {}
    for control in controls:
        shape = shapes[control.control_id]
        fixture = step_round_trip(shape, control.control_id)
        fixtures.append(fixture)
        for stage, stage_shape in (
            ("constructed", shape),
            ("step_imported", fixture.imported_shape),
        ):
            stage_faces, stage_adjacencies = _measure_graph(
                control.control_id, stage, stage_shape
            )
            stage_shapes[(control.control_id, stage)] = stage_shape
            faces.extend(stage_faces)
            adjacencies.extend(stage_adjacencies)
            stage_candidates = _recognize(control, stage, stage_faces)
            expected_count = len(control.expected_candidate_types)
            if len(stage_candidates) != expected_count:
                raise RuntimeError(
                    f"unexpected {stage} feature count for {control.control_id}: "
                    f"{len(stage_candidates)} != {expected_count}"
                )
            if not all(item.truth_correct for item in stage_candidates):
                raise RuntimeError(
                    f"feature classification mismatch for {control.control_id} at {stage}"
                )
            candidates.extend(stage_candidates)
            previews.append((control.control_id, stage, stage_shape))
    equivalent_boundaries = tuple(
        _equivalent_boundary_observation(
            stage,
            "chamfer_operation",
            stage_shapes[("chamfer_operation", stage)],
            "equivalent_bevel",
            stage_shapes[("equivalent_bevel", stage)],
        )
        for stage in ("constructed", "step_imported")
    )
    if not all(item.boundary_equivalent for item in equivalent_boundaries):
        raise RuntimeError("equivalent chamfer boundaries no longer match")
    return FeatureRecognitionProbe(
        controls,
        tuple(fixtures),
        tuple(faces),
        tuple(adjacencies),
        tuple(candidates),
        equivalent_boundaries,
        tuple(previews),
    )
