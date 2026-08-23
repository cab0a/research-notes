"""Infer controlled face and edge correspondence across STEP import and healing."""

from __future__ import annotations

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


CorrespondenceStage = Literal["constructed", "step_imported", "healed"]
ComparisonKind = Literal["step_import", "same_domain_healing"]
Vector3 = tuple[float, float, float]


@dataclass(frozen=True)
class CorrespondenceControl:
    """Independent construction truth for one correspondence control."""

    control_id: str
    condition: str
    expected_constructed_faces: int
    expected_imported_faces: int
    expected_healed_faces: int | None
    expected_constructed_edges: int
    expected_imported_edges: int
    expected_healed_edges: int | None
    analytic_volume: float | None


@dataclass(frozen=True)
class FaceDescriptor:
    """Orientation-insensitive geometry and topology for one local face."""

    stage: CorrespondenceStage
    control_id: str
    face_index: int
    truth_role: str
    surface_type: str
    area: float
    centroid: Vector3
    support_direction: Vector3 | None
    support_offset: float | None
    cylinder_radius: float | None
    wire_count: int
    edge_count: int
    adjacency_degree: int
    edge_length_signature: tuple[float, ...]


@dataclass(frozen=True)
class CandidateObservation:
    """One geometry-gated source-to-target face candidate."""

    comparison: ComparisonKind
    control_id: str
    source_stage: CorrespondenceStage
    target_stage: CorrespondenceStage
    source_face_index: int
    target_face_index: int
    source_truth_role: str
    target_truth_role: str
    area_relative_error: float
    centroid_distance: float
    support_offset_error: float
    source_centroid_contained: bool
    selected: bool


@dataclass(frozen=True)
class RelationObservation:
    """Resolved, ambiguous, or unmatched result for one source face."""

    comparison: ComparisonKind
    control_id: str
    source_stage: CorrespondenceStage
    target_stage: CorrespondenceStage
    source_face_index: int
    source_truth_role: str
    target_face_indices: tuple[int, ...]
    target_truth_roles: tuple[str, ...]
    relation_kind: str
    candidate_count: int
    truth_correct: bool
    history_target_indices: tuple[int, ...]
    history_agrees: bool | None


@dataclass(frozen=True)
class EdgeDescriptor:
    """Orientation-insensitive geometry and topology for one local edge."""

    stage: CorrespondenceStage
    control_id: str
    edge_index: int
    truth_role: str
    curve_type: str
    length: float
    first_point: Vector3
    last_point: Vector3
    support_direction: Vector3 | None
    support_anchor: Vector3 | None
    incident_face_count: int
    incident_face_indices: tuple[int, ...]


@dataclass(frozen=True)
class EdgeCandidateObservation:
    """One geometry-gated edge candidate with separate topology evidence."""

    comparison: ComparisonKind
    control_id: str
    source_stage: CorrespondenceStage
    target_stage: CorrespondenceStage
    source_edge_index: int
    target_edge_index: int
    source_truth_role: str
    target_truth_role: str
    curve_type_matches: bool
    support_error: float
    length_relative_error: float
    endpoint_pair_max_distance: float
    source_endpoints_on_target: bool
    source_incident_face_count: int
    target_incident_face_count: int
    incident_face_count_matches: bool
    source_incident_face_indices: tuple[int, ...]
    mapped_source_incident_target_face_indices: tuple[int, ...]
    target_incident_face_indices: tuple[int, ...]
    mapped_target_incident_source_face_indices: tuple[int, ...]
    topology_candidate_supports_geometry: bool
    selected: bool


@dataclass(frozen=True)
class EdgeRelationObservation:
    """Geometry inference and operation history for one source edge."""

    comparison: ComparisonKind
    control_id: str
    source_stage: CorrespondenceStage
    target_stage: CorrespondenceStage
    source_edge_index: int
    source_truth_role: str
    target_edge_indices: tuple[int, ...]
    target_truth_roles: tuple[str, ...]
    inferred_relation_kind: str
    relation_kind: str
    candidate_count: int
    truth_correct: bool
    history_modified_target_indices: tuple[int, ...]
    history_generated_target_indices: tuple[int, ...]
    history_modified_item_count: int | None
    history_generated_item_count: int | None
    history_unresolved_item_count: int | None
    history_removed: bool | None
    history_relation_kind: str | None
    direct_identity_checked: bool
    direct_is_same: bool
    direct_is_partner: bool
    direct_same_target_indices: tuple[int, ...]
    direct_partner_target_indices: tuple[int, ...]
    history_agrees: bool | None


@dataclass(frozen=True)
class _EdgeHistoryEvidence:
    modified_target_indices: tuple[int, ...]
    generated_target_indices: tuple[int, ...]
    modified_item_count: int
    generated_item_count: int
    unresolved_item_count: int
    removed: bool


@dataclass(frozen=True)
class _EdgeDirectIdentityEvidence:
    """Direct TopoDS identity checks kept separate from correspondence inference."""

    same_target_indices: tuple[int, ...]
    partner_target_indices: tuple[int, ...]


@dataclass(frozen=True)
class ShapeCorrespondenceProbe:
    """Complete evidence for controlled STEP and healing correspondence."""

    controls: tuple[CorrespondenceControl, ...]
    fixtures: tuple[StepRoundTrip, ...]
    faces: tuple[FaceDescriptor, ...]
    candidates: tuple[CandidateObservation, ...]
    relations: tuple[RelationObservation, ...]
    edges: tuple[EdgeDescriptor, ...]
    edge_candidates: tuple[EdgeCandidateObservation, ...]
    edge_relations: tuple[EdgeRelationObservation, ...]
    preview_shapes: tuple[tuple[str, CorrespondenceStage, object], ...]


def correspondence_controls() -> tuple[CorrespondenceControl, ...]:
    """Return the preregistered synthetic correspondence controls."""
    return (
        CorrespondenceControl(
            "asymmetric_prism",
            "Seven analytically distinguishable planar faces",
            7,
            7,
            None,
            15,
            15,
            None,
            98.0,
        ),
        CorrespondenceControl(
            "reversed_box",
            "Whole-solid reversal without loss of geometric face identity",
            6,
            6,
            None,
            12,
            12,
            None,
            120.0,
        ),
        CorrespondenceControl(
            "split_box",
            "Four coplanar face pairs merged by same-domain healing",
            10,
            10,
            6,
            20,
            20,
            12,
            180.0,
        ),
        CorrespondenceControl(
            "coincident_faces",
            "Two geometrically and topologically indistinguishable faces",
            2,
            2,
            None,
            8,
            8,
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


def _build_asymmetric_prism() -> object:
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.gp import gp_Vec

    base = _polygon_face(
        (
            (0.0, 0.0, 0.0),
            (7.0, 0.0, 0.0),
            (6.0, 3.0, 0.0),
            (2.0, 5.0, 0.0),
            (0.0, 2.0, 0.0),
        )
    )
    return BRepPrimAPI_MakePrism(base, gp_Vec(0.0, 0.0, 4.0)).Shape()


def _build_reversed_box() -> object:
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

    return BRepPrimAPI_MakeBox(4.0, 5.0, 6.0).Shape().Reversed()


def _build_split_box() -> object:
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt

    left = BRepPrimAPI_MakeBox(gp_Pnt(0.0, 0.0, 0.0), 4.0, 6.0, 3.0).Shape()
    right = BRepPrimAPI_MakeBox(gp_Pnt(4.0, 0.0, 0.0), 6.0, 6.0, 3.0).Shape()
    operation = BRepAlgoAPI_Fuse(left, right)
    operation.SetNonDestructive(True)
    operation.Build()
    if not operation.IsDone():
        raise RuntimeError("failed to construct the split-box control")
    return operation.Shape()


def _build_coincident_faces() -> object:
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound

    points = ((0.0, 0.0, 0.0), (3.0, 0.0, 0.0), (3.0, 2.0, 0.0), (0.0, 2.0, 0.0))
    first = _polygon_face(points)
    second = _polygon_face(points)
    compound = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(compound)
    builder.Add(compound, first)
    builder.Add(compound, second)
    return compound


def build_correspondence_shapes() -> dict[str, object]:
    """Construct every deterministic correspondence control."""
    return {
        "asymmetric_prism": _build_asymmetric_prism(),
        "reversed_box": _build_reversed_box(),
        "split_box": _build_split_box(),
        "coincident_faces": _build_coincident_faces(),
    }


def _canonical_direction(values: Vector3) -> Vector3:
    length = math.sqrt(sum(value * value for value in values))
    if length == 0.0:
        raise ValueError("support direction must be nonzero")
    result = tuple(value / length for value in values)
    for value in result:
        if abs(value) > 1.0e-12:
            return result if value > 0.0 else tuple(-item for item in result)
    raise ValueError("support direction is numerically zero")


def _distance(first: Vector3, second: Vector3) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(first, second, strict=True)))


def _face_role(control_id: str, face_count: int, descriptor: FaceDescriptor) -> str:
    x, y, z = descriptor.centroid
    if control_id == "coincident_faces":
        return "coincident"
    if control_id == "asymmetric_prism":
        if math.isclose(z, 0.0, abs_tol=1.0e-7):
            return "base_bottom"
        if math.isclose(z, 4.0, abs_tol=1.0e-7):
            return "base_top"
        side_areas = (
            28.0,
            4.0 * math.sqrt(10.0),
            4.0 * math.sqrt(20.0),
            4.0 * math.sqrt(13.0),
            8.0,
        )
        return (
            f"side_{min(range(5), key=lambda i: abs(descriptor.area - side_areas[i]))}"
        )
    if control_id == "reversed_box":
        coordinates = (
            ("x_min", abs(x)),
            ("x_max", abs(x - 4.0)),
            ("y_min", abs(y)),
            ("y_max", abs(y - 5.0)),
            ("z_min", abs(z)),
            ("z_max", abs(z - 6.0)),
        )
        return min(coordinates, key=lambda item: item[1])[0]
    if control_id == "split_box":
        if math.isclose(x, 0.0, abs_tol=1.0e-7):
            return "x_min"
        if math.isclose(x, 10.0, abs_tol=1.0e-7):
            return "x_max"
        if math.isclose(y, 0.0, abs_tol=1.0e-7):
            base = "y_min"
        elif math.isclose(y, 6.0, abs_tol=1.0e-7):
            base = "y_max"
        elif math.isclose(z, 0.0, abs_tol=1.0e-7):
            base = "z_min"
        elif math.isclose(z, 3.0, abs_tol=1.0e-7):
            base = "z_max"
        else:
            raise RuntimeError("unrecognized split-box face")
        if face_count == 6:
            return base
        return f"{base}_{'left' if x < 4.0 + 1.0e-7 else 'right'}"
    raise ValueError(f"unknown control: {control_id}")


def _describe_faces(
    control_id: str,
    stage: CorrespondenceStage,
    shape: object,
) -> tuple[tuple[FaceDescriptor, ...], tuple[object, ...]]:
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepGProp import BRepGProp
    from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_WIRE
    from OCP.TopoDS import TopoDS

    face_map = indexed_shapes(shape, TopAbs_FACE)
    edge_map = indexed_shapes(shape, TopAbs_EDGE)
    faces = tuple(
        TopoDS.Face_s(face_map.FindKey(index))
        for index in range(1, face_map.Extent() + 1)
    )
    edge_to_faces: dict[int, set[int]] = {
        index: set() for index in range(1, edge_map.Extent() + 1)
    }
    for face_index, face in enumerate(faces, start=1):
        for edge in iter_shapes(face, TopAbs_EDGE):
            edge_index = int(edge_map.FindIndex(edge))
            if edge_index:
                edge_to_faces[edge_index].add(face_index)

    descriptors: list[FaceDescriptor] = []
    for face_index, face in enumerate(faces, start=1):
        area, centroid = surface_area_and_centroid(face)
        adaptor = BRepAdaptor_Surface(face, True)
        surface_value = adaptor.GetType()
        direction: Vector3 | None = None
        offset: float | None = None
        radius: float | None = None
        if surface_value == GeomAbs_Plane:
            surface_type = "plane"
            plane = adaptor.Plane()
            raw = plane.Axis().Direction()
            direction = _canonical_direction((raw.X(), raw.Y(), raw.Z()))
            location = plane.Location()
            offset = sum(
                value * coordinate
                for value, coordinate in zip(
                    direction,
                    (location.X(), location.Y(), location.Z()),
                    strict=True,
                )
            )
        elif surface_value == GeomAbs_Cylinder:
            surface_type = "cylinder"
            cylinder = adaptor.Cylinder()
            raw = cylinder.Axis().Direction()
            direction = _canonical_direction((raw.X(), raw.Y(), raw.Z()))
            radius = float(cylinder.Radius())
        else:
            surface_type = status_name(surface_value).removeprefix("GeomAbs_").lower()

        edge_indices: set[int] = set()
        lengths: list[float] = []
        for edge_shape in iter_shapes(face, TopAbs_EDGE):
            edge_index = int(edge_map.FindIndex(edge_shape))
            if not edge_index or edge_index in edge_indices:
                continue
            edge_indices.add(edge_index)
            properties = GProp_GProps()
            BRepGProp.LinearProperties_s(TopoDS.Edge_s(edge_shape), properties)
            lengths.append(float(properties.Mass()))
        adjacent = {
            other
            for edge_index in edge_indices
            for other in edge_to_faces[edge_index]
            if other != face_index
        }
        provisional = FaceDescriptor(
            stage=stage,
            control_id=control_id,
            face_index=face_index,
            truth_role="",
            surface_type=surface_type,
            area=area,
            centroid=centroid,
            support_direction=direction,
            support_offset=offset,
            cylinder_radius=radius,
            wire_count=len(iter_shapes(face, TopAbs_WIRE)),
            edge_count=len(edge_indices),
            adjacency_degree=len(adjacent),
            edge_length_signature=tuple(sorted(lengths)),
        )
        descriptors.append(
            FaceDescriptor(
                **{
                    **provisional.__dict__,
                    "truth_role": _face_role(control_id, len(faces), provisional),
                }
            )
        )
    return tuple(descriptors), faces


def _point_token(point: Vector3) -> str:
    return ",".join(format(0.0 if abs(value) < 5.0e-9 else value, ".9g") for value in point)


def _edge_role(control_id: str, descriptor: EdgeDescriptor) -> str:
    first = descriptor.first_point
    last = descriptor.last_point
    if control_id == "split_box":
        if (
            math.isclose(first[1], last[1], abs_tol=1.0e-7)
            and math.isclose(first[2], last[2], abs_tol=1.0e-7)
            and not math.isclose(first[0], last[0], abs_tol=1.0e-7)
        ):
            prefix = f"long_y{_point_token((first[1], 0.0, 0.0)).split(',')[0]}_z{_point_token((first[2], 0.0, 0.0)).split(',')[0]}"
            low, high = sorted((first[0], last[0]))
            if math.isclose(low, 0.0, abs_tol=1.0e-7) and math.isclose(
                high, 4.0, abs_tol=1.0e-7
            ):
                return f"{prefix}_left"
            if math.isclose(low, 4.0, abs_tol=1.0e-7) and math.isclose(
                high, 10.0, abs_tol=1.0e-7
            ):
                return f"{prefix}_right"
            if math.isclose(low, 0.0, abs_tol=1.0e-7) and math.isclose(
                high, 10.0, abs_tol=1.0e-7
            ):
                return prefix
        if math.isclose(first[0], 4.0, abs_tol=1.0e-7) and math.isclose(
            last[0], 4.0, abs_tol=1.0e-7
        ):
            return f"seam_{_point_token(first)}__{_point_token(last)}"
    return f"edge_{_point_token(first)}__{_point_token(last)}"


def _describe_edges(
    control_id: str,
    stage: CorrespondenceStage,
    shape: object,
) -> tuple[tuple[EdgeDescriptor, ...], tuple[object, ...]]:
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepGProp import BRepGProp
    from OCP.GeomAbs import GeomAbs_Line
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopoDS import TopoDS

    edge_map = indexed_shapes(shape, TopAbs_EDGE)
    edges = tuple(
        TopoDS.Edge_s(edge_map.FindKey(index))
        for index in range(1, edge_map.Extent() + 1)
    )
    edge_face_counts = {index: 0 for index in range(1, edge_map.Extent() + 1)}
    for face in iter_shapes(shape, TopAbs_FACE):
        seen: set[int] = set()
        for edge in iter_shapes(face, TopAbs_EDGE):
            edge_index = int(edge_map.FindIndex(edge))
            if edge_index and edge_index not in seen:
                edge_face_counts[edge_index] += 1
                seen.add(edge_index)

    descriptors: list[EdgeDescriptor] = []
    for edge_index, edge in enumerate(edges, start=1):
        adaptor = BRepAdaptor_Curve(edge)
        curve_value = adaptor.GetType()
        curve_type = (
            "line"
            if curve_value == GeomAbs_Line
            else status_name(curve_value).removeprefix("GeomAbs_").lower()
        )
        first_raw = adaptor.Value(adaptor.FirstParameter())
        last_raw = adaptor.Value(adaptor.LastParameter())
        points = sorted(
            (
                (float(first_raw.X()), float(first_raw.Y()), float(first_raw.Z())),
                (float(last_raw.X()), float(last_raw.Y()), float(last_raw.Z())),
            )
        )
        first, last = points
        direction: Vector3 | None = None
        anchor: Vector3 | None = None
        if curve_type == "line":
            direction = _canonical_direction(
                tuple(b - a for a, b in zip(first, last, strict=True))
            )
            projection = sum(
                coordinate * value
                for coordinate, value in zip(first, direction, strict=True)
            )
            anchor = tuple(
                coordinate - projection * value
                for coordinate, value in zip(first, direction, strict=True)
            )
        properties = GProp_GProps()
        BRepGProp.LinearProperties_s(edge, properties)
        provisional = EdgeDescriptor(
            stage,
            control_id,
            edge_index,
            "",
            curve_type,
            float(properties.Mass()),
            first,
            last,
            direction,
            anchor,
            edge_face_counts[edge_index],
            tuple(
                sorted(
                    face_index
                    for face_index, face in enumerate(
                        iter_shapes(shape, TopAbs_FACE), start=1
                    )
                    if any(
                        edge.IsSame(face_edge)
                        for face_edge in iter_shapes(face, TopAbs_EDGE)
                    )
                )
            ),
        )
        descriptors.append(
            EdgeDescriptor(
                **{
                    **provisional.__dict__,
                    "truth_role": _edge_role(control_id, provisional),
                }
            )
        )
    return tuple(descriptors), edges


def _same_edge_support(
    source: EdgeDescriptor, target: EdgeDescriptor
) -> tuple[bool, float]:
    if source.curve_type != target.curve_type:
        return False, math.inf
    if (
        source.support_direction is None
        or target.support_direction is None
        or source.support_anchor is None
        or target.support_anchor is None
    ):
        return False, math.inf
    dot = abs(
        sum(
            a * b
            for a, b in zip(
                source.support_direction, target.support_direction, strict=True
            )
        )
    )
    anchor_error = _distance(source.support_anchor, target.support_anchor)
    return dot >= 1.0 - 1.0e-10 and anchor_error <= 1.0e-7, anchor_error


def _endpoint_pair_distance(source: EdgeDescriptor, target: EdgeDescriptor) -> float:
    direct = max(
        _distance(source.first_point, target.first_point),
        _distance(source.last_point, target.last_point),
    )
    reversed_distance = max(
        _distance(source.first_point, target.last_point),
        _distance(source.last_point, target.first_point),
    )
    return min(direct, reversed_distance)


def _point_on_segment(point: Vector3, target: EdgeDescriptor) -> bool:
    direction = tuple(
        b - a for a, b in zip(target.first_point, target.last_point, strict=True)
    )
    length_squared = sum(value * value for value in direction)
    if length_squared <= 1.0e-20:
        return False
    relative = tuple(
        value - origin
        for value, origin in zip(point, target.first_point, strict=True)
    )
    parameter = sum(
        value * axis for value, axis in zip(relative, direction, strict=True)
    ) / length_squared
    projection = tuple(
        origin + parameter * axis
        for origin, axis in zip(target.first_point, direction, strict=True)
    )
    return -1.0e-8 <= parameter <= 1.0 + 1.0e-8 and _distance(
        point, projection
    ) <= 1.0e-7


def _edge_candidate_rows(
    comparison: ComparisonKind,
    control_id: str,
    sources: tuple[EdgeDescriptor, ...],
    targets: tuple[EdgeDescriptor, ...],
    candidate_target_faces_by_source: dict[int, tuple[int, ...]],
    candidate_source_faces_by_target: dict[int, tuple[int, ...]],
) -> tuple[EdgeCandidateObservation, ...]:
    raw: list[
        tuple[EdgeDescriptor, EdgeDescriptor, float, float, float, bool]
    ] = []
    for source in sources:
        for target in targets:
            same_support, support_error = _same_edge_support(source, target)
            if not same_support:
                continue
            length_error = abs(source.length - target.length) / max(
                source.length, target.length, 1.0
            )
            endpoint_error = _endpoint_pair_distance(source, target)
            covered = _point_on_segment(
                source.first_point, target
            ) and _point_on_segment(source.last_point, target)
            eligible = (
                length_error <= 1.0e-8 and endpoint_error <= 1.0e-7
                if comparison == "step_import"
                else covered and target.length + 1.0e-7 >= source.length
            )
            if eligible:
                raw.append(
                    (
                        source,
                        target,
                        support_error,
                        length_error,
                        endpoint_error,
                        covered,
                    )
                )

    source_counts: dict[int, int] = {}
    target_counts: dict[int, int] = {}
    for source, target, *_ in raw:
        source_counts[source.edge_index] = source_counts.get(source.edge_index, 0) + 1
        target_counts[target.edge_index] = target_counts.get(target.edge_index, 0) + 1
    rows: list[EdgeCandidateObservation] = []
    for source, target, support_error, length_error, endpoint_error, covered in raw:
        selected = source_counts[source.edge_index] == 1
        if comparison == "step_import":
            selected = selected and target_counts[target.edge_index] == 1
        mapped_incident_faces = tuple(
            sorted(
                {
                    target_face
                    for source_face in source.incident_face_indices
                    for target_face in candidate_target_faces_by_source.get(
                        source_face, ()
                    )
                }
            )
        )
        mapped_target_incident_faces = tuple(
            sorted(
                {
                    source_face
                    for target_face in target.incident_face_indices
                    for source_face in candidate_source_faces_by_target.get(
                        target_face, ()
                    )
                }
            )
        )
        topology_support = (
            set(target.incident_face_indices).issubset(mapped_incident_faces)
            and set(source.incident_face_indices).issubset(
                mapped_target_incident_faces
            )
        )
        rows.append(
            EdgeCandidateObservation(
                comparison,
                control_id,
                source.stage,
                target.stage,
                source.edge_index,
                target.edge_index,
                source.truth_role,
                target.truth_role,
                source.curve_type == target.curve_type,
                support_error,
                length_error,
                endpoint_error,
                covered,
                source.incident_face_count,
                target.incident_face_count,
                source.incident_face_count == target.incident_face_count,
                source.incident_face_indices,
                mapped_incident_faces,
                target.incident_face_indices,
                mapped_target_incident_faces,
                topology_support,
                selected,
            )
        )
    return tuple(rows)


def _same_support(source: FaceDescriptor, target: FaceDescriptor) -> tuple[bool, float]:
    if source.surface_type != target.surface_type:
        return False, math.inf
    if source.support_direction is not None and target.support_direction is not None:
        dot = abs(
            sum(
                a * b
                for a, b in zip(
                    source.support_direction, target.support_direction, strict=True
                )
            )
        )
        if dot < 1.0 - 1.0e-10:
            return False, 1.0 - dot
    if source.support_offset is not None and target.support_offset is not None:
        error = abs(source.support_offset - target.support_offset)
        return error <= 1.0e-7, error
    if source.cylinder_radius is not None and target.cylinder_radius is not None:
        error = abs(source.cylinder_radius - target.cylinder_radius)
        return error <= 1.0e-7, error
    return True, 0.0


def _contains_centroid(face: object, point: Vector3) -> bool:
    from OCP.BRepClass import BRepClass_FaceClassifier
    from OCP.TopAbs import TopAbs_IN, TopAbs_ON
    from OCP.gp import gp_Pnt

    classifier = BRepClass_FaceClassifier(face, gp_Pnt(*point), 1.0e-7)
    return classifier.State() in (TopAbs_IN, TopAbs_ON)


def _candidate_rows(
    comparison: ComparisonKind,
    control_id: str,
    sources: tuple[FaceDescriptor, ...],
    source_faces: tuple[object, ...],
    targets: tuple[FaceDescriptor, ...],
    target_faces: tuple[object, ...],
) -> tuple[CandidateObservation, ...]:
    raw: list[tuple[FaceDescriptor, FaceDescriptor, float, float, float, bool]] = []
    for source in sources:
        for target in targets:
            same_support, support_error = _same_support(source, target)
            if not same_support:
                continue
            area_error = abs(source.area - target.area) / max(
                source.area, target.area, 1.0
            )
            centroid_error = _distance(source.centroid, target.centroid)
            contained = _contains_centroid(
                target_faces[target.face_index - 1], source.centroid
            )
            if comparison == "step_import":
                eligible = area_error <= 1.0e-8 and centroid_error <= 1.0e-7
            else:
                eligible = contained and target.area + 1.0e-7 >= source.area
            if eligible:
                raw.append(
                    (
                        source,
                        target,
                        area_error,
                        centroid_error,
                        support_error,
                        contained,
                    )
                )

    source_counts: dict[int, int] = {}
    target_counts: dict[int, int] = {}
    for source, target, *_ in raw:
        source_counts[source.face_index] = source_counts.get(source.face_index, 0) + 1
        target_counts[target.face_index] = target_counts.get(target.face_index, 0) + 1
    rows: list[CandidateObservation] = []
    for source, target, area_error, centroid_error, support_error, contained in raw:
        selected = source_counts[source.face_index] == 1
        if comparison == "step_import":
            selected = selected and target_counts[target.face_index] == 1
        rows.append(
            CandidateObservation(
                comparison,
                control_id,
                source.stage,
                target.stage,
                source.face_index,
                target.face_index,
                source.truth_role,
                target.truth_role,
                area_error,
                centroid_error,
                support_error,
                contained,
                selected,
            )
        )
    return tuple(rows)


def _face_candidate_maps(
    candidates: tuple[CandidateObservation, ...],
) -> tuple[dict[int, tuple[int, ...]], dict[int, tuple[int, ...]]]:
    forward: dict[int, set[int]] = {}
    reverse: dict[int, set[int]] = {}
    for row in candidates:
        forward.setdefault(row.source_face_index, set()).add(row.target_face_index)
        reverse.setdefault(row.target_face_index, set()).add(row.source_face_index)
    return (
        {index: tuple(sorted(values)) for index, values in forward.items()},
        {index: tuple(sorted(values)) for index, values in reverse.items()},
    )


def _history_targets(
    history: object, source_shape: object, target_shapes: tuple[object, ...]
) -> tuple[int, ...]:
    found: set[int] = set()
    modified = history.Modified(source_shape)
    for item in modified:
        for index, target in enumerate(target_shapes, start=1):
            if item.IsSame(target):
                found.add(index)
    return tuple(sorted(found))


def _history_generated_targets(
    history: object, source_shape: object, target_shapes: tuple[object, ...]
) -> tuple[int, ...]:
    found: set[int] = set()
    for item in history.Generated(source_shape):
        for index, target in enumerate(target_shapes, start=1):
            if item.IsSame(target):
                found.add(index)
    return tuple(sorted(found))


def _edge_history_evidence(
    history: object, source_edge: object, target_edges: tuple[object, ...]
) -> _EdgeHistoryEvidence:
    modified = tuple(history.Modified(source_edge))
    generated = tuple(history.Generated(source_edge))

    def mapped(items: tuple[object, ...]) -> tuple[tuple[int, ...], int]:
        found: set[int] = set()
        unresolved = 0
        for item in items:
            matches = [
                index
                for index, target in enumerate(target_edges, start=1)
                if item.IsSame(target)
            ]
            if matches:
                found.update(matches)
            else:
                unresolved += 1
        return tuple(sorted(found)), unresolved

    modified_targets, modified_unresolved = mapped(modified)
    generated_targets, generated_unresolved = mapped(generated)
    return _EdgeHistoryEvidence(
        modified_targets,
        generated_targets,
        len(modified),
        len(generated),
        modified_unresolved + generated_unresolved,
        bool(history.IsRemoved(source_edge)),
    )


def _edge_direct_identity_evidence(
    source_edge: object, target_edges: tuple[object, ...]
) -> _EdgeDirectIdentityEvidence:
    """Compare native topology identity without using it as a matching signal."""
    return _EdgeDirectIdentityEvidence(
        tuple(
            index
            for index, target in enumerate(target_edges, start=1)
            if source_edge.IsSame(target)
        ),
        tuple(
            index
            for index, target in enumerate(target_edges, start=1)
            if source_edge.IsPartner(target)
        ),
    )


def _edge_relations(
    comparison: ComparisonKind,
    control_id: str,
    sources: tuple[EdgeDescriptor, ...],
    candidates: tuple[EdgeCandidateObservation, ...],
    history_by_source: dict[int, _EdgeHistoryEvidence] | None = None,
    direct_identity_by_source: dict[int, _EdgeDirectIdentityEvidence] | None = None,
) -> tuple[EdgeRelationObservation, ...]:
    selected_target_counts: dict[int, int] = {}
    for row in candidates:
        if row.selected:
            selected_target_counts[row.target_edge_index] = (
                selected_target_counts.get(row.target_edge_index, 0) + 1
            )
    history_target_counts: dict[int, int] = {}
    if history_by_source is not None:
        for evidence in history_by_source.values():
            for target in evidence.modified_target_indices:
                history_target_counts[target] = history_target_counts.get(target, 0) + 1

    result: list[EdgeRelationObservation] = []
    for source in sources:
        rows = [row for row in candidates if row.source_edge_index == source.edge_index]
        selected = [row for row in rows if row.selected]
        targets = tuple(row.target_edge_index for row in selected)
        roles = tuple(row.target_truth_role for row in selected)
        if rows and not selected:
            inferred_kind = "ambiguous"
        elif not selected:
            inferred_kind = "unmatched"
        elif any(selected_target_counts[index] > 1 for index in targets):
            inferred_kind = "many_to_one"
        else:
            inferred_kind = "one_to_one"

        history_evidence = (
            None
            if history_by_source is None
            else history_by_source.get(source.edge_index)
        )
        direct_evidence = (
            None
            if direct_identity_by_source is None
            else direct_identity_by_source.get(source.edge_index)
        )
        history_modified_targets = (
            () if history_evidence is None else history_evidence.modified_target_indices
        )
        history_generated_targets = (
            () if history_evidence is None else history_evidence.generated_target_indices
        )
        history_removed = None if history_evidence is None else history_evidence.removed
        if history_evidence is None:
            history_kind = None
        elif history_removed:
            history_kind = "deleted"
        elif history_modified_targets and any(
            history_target_counts[index] > 1 for index in history_modified_targets
        ):
            history_kind = "many_to_one"
        elif history_modified_targets:
            history_kind = "one_to_one_modified"
        else:
            history_kind = "unrecorded"

        if comparison == "same_domain_healing":
            relation_kind = {
                "one_to_one": "one_to_one_modified",
                "many_to_one": "many_to_one",
            }.get(inferred_kind, inferred_kind)
            if inferred_kind == "unmatched" and history_removed:
                relation_kind = "deleted"
        else:
            relation_kind = inferred_kind

        if comparison == "step_import":
            truth_correct = (
                relation_kind == "ambiguous" and control_id == "coincident_faces"
            ) or (len(roles) == 1 and roles[0] == source.truth_role)
        elif source.truth_role.startswith("seam_"):
            truth_correct = relation_kind == "deleted" and not targets
        else:
            expected_role = source.truth_role.removesuffix("_left").removesuffix(
                "_right"
            )
            truth_correct = len(roles) == 1 and roles[0] == expected_role

        history_agrees = (
            None
            if history_kind is None
            else tuple(sorted(targets)) == tuple(sorted(history_modified_targets))
            and not history_generated_targets
            and relation_kind == history_kind
        )
        result.append(
            EdgeRelationObservation(
                comparison=comparison,
                control_id=control_id,
                source_stage=source.stage,
                target_stage=(
                    candidates[0].target_stage
                    if candidates
                    else (
                        "healed"
                        if comparison == "same_domain_healing"
                        else "step_imported"
                    )
                ),
                source_edge_index=source.edge_index,
                source_truth_role=source.truth_role,
                target_edge_indices=targets,
                target_truth_roles=roles,
                inferred_relation_kind=inferred_kind,
                relation_kind=relation_kind,
                candidate_count=len(rows),
                truth_correct=truth_correct,
                history_modified_target_indices=history_modified_targets,
                history_generated_target_indices=history_generated_targets,
                history_modified_item_count=(
                    None
                    if history_evidence is None
                    else history_evidence.modified_item_count
                ),
                history_generated_item_count=(
                    None
                    if history_evidence is None
                    else history_evidence.generated_item_count
                ),
                history_unresolved_item_count=(
                    None
                    if history_evidence is None
                    else history_evidence.unresolved_item_count
                ),
                history_removed=history_removed,
                history_relation_kind=history_kind,
                direct_identity_checked=direct_evidence is not None,
                direct_is_same=bool(
                    direct_evidence and direct_evidence.same_target_indices
                ),
                direct_is_partner=bool(
                    direct_evidence and direct_evidence.partner_target_indices
                ),
                direct_same_target_indices=(
                    ()
                    if direct_evidence is None
                    else direct_evidence.same_target_indices
                ),
                direct_partner_target_indices=(
                    ()
                    if direct_evidence is None
                    else direct_evidence.partner_target_indices
                ),
                history_agrees=history_agrees,
            )
        )
    return tuple(result)


def _relations(
    comparison: ComparisonKind,
    control_id: str,
    sources: tuple[FaceDescriptor, ...],
    candidates: tuple[CandidateObservation, ...],
    history_by_source: dict[int, tuple[int, ...]] | None = None,
) -> tuple[RelationObservation, ...]:
    selected_target_counts: dict[int, int] = {}
    for row in candidates:
        if row.selected:
            selected_target_counts[row.target_face_index] = (
                selected_target_counts.get(row.target_face_index, 0) + 1
            )
    result: list[RelationObservation] = []
    for source in sources:
        rows = [row for row in candidates if row.source_face_index == source.face_index]
        selected = [row for row in rows if row.selected]
        targets = tuple(row.target_face_index for row in selected)
        roles = tuple(row.target_truth_role for row in selected)
        if len(rows) > 1 and not selected:
            kind = "ambiguous"
        elif not selected:
            kind = "unmatched"
        elif any(selected_target_counts[index] > 1 for index in targets):
            kind = "many_to_one"
        else:
            kind = "one_to_one"
        expected_role = source.truth_role
        if comparison == "same_domain_healing":
            expected_role = expected_role.removesuffix("_left").removesuffix("_right")
        truth_correct = (kind == "ambiguous" and control_id == "coincident_faces") or (
            len(roles) == 1 and roles[0] == expected_role
        )
        history_targets = (
            ()
            if history_by_source is None
            else history_by_source.get(source.face_index, ())
        )
        history_agrees = (
            None
            if history_by_source is None
            else tuple(sorted(targets)) == history_targets
        )
        result.append(
            RelationObservation(
                comparison,
                control_id,
                source.stage,
                (
                    candidates[0].target_stage
                    if candidates
                    else (
                        "healed"
                        if comparison == "same_domain_healing"
                        else "step_imported"
                    )
                ),
                source.face_index,
                source.truth_role,
                targets,
                roles,
                kind,
                len(rows),
                truth_correct,
                history_targets,
                history_agrees,
            )
        )
    return tuple(result)


def probe_shape_correspondence() -> ShapeCorrespondenceProbe:
    """Run all controlled STEP-import and same-domain correspondence probes."""
    from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain

    controls = correspondence_controls()
    shapes = build_correspondence_shapes()
    fixtures: list[StepRoundTrip] = []
    descriptors: list[FaceDescriptor] = []
    candidates: list[CandidateObservation] = []
    relations: list[RelationObservation] = []
    edge_descriptors: list[EdgeDescriptor] = []
    edge_candidates: list[EdgeCandidateObservation] = []
    edge_relations: list[EdgeRelationObservation] = []
    previews: list[tuple[str, CorrespondenceStage, object]] = []

    imported: dict[str, object] = {}
    stage_data: dict[
        tuple[str, CorrespondenceStage],
        tuple[tuple[FaceDescriptor, ...], tuple[object, ...]],
    ] = {}
    edge_stage_data: dict[
        tuple[str, CorrespondenceStage],
        tuple[tuple[EdgeDescriptor, ...], tuple[object, ...]],
    ] = {}
    for control in controls:
        shape = shapes[control.control_id]
        fixture = step_round_trip(shape, control.control_id)
        fixtures.append(fixture)
        imported[control.control_id] = fixture.imported_shape
        for stage, stage_shape in (
            ("constructed", shape),
            ("step_imported", fixture.imported_shape),
        ):
            measured = _describe_faces(control.control_id, stage, stage_shape)
            stage_data[(control.control_id, stage)] = measured
            descriptors.extend(measured[0])
            measured_edges = _describe_edges(control.control_id, stage, stage_shape)
            edge_stage_data[(control.control_id, stage)] = measured_edges
            edge_descriptors.extend(measured_edges[0])
            previews.append((control.control_id, stage, stage_shape))
        source_desc, source_faces = stage_data[(control.control_id, "constructed")]
        target_desc, target_faces = stage_data[(control.control_id, "step_imported")]
        rows = _candidate_rows(
            "step_import",
            control.control_id,
            source_desc,
            source_faces,
            target_desc,
            target_faces,
        )
        candidates.extend(rows)
        face_relation_rows = _relations(
            "step_import", control.control_id, source_desc, rows
        )
        relations.extend(face_relation_rows)
        face_candidate_forward, face_candidate_reverse = _face_candidate_maps(rows)
        source_edge_desc, source_edges = edge_stage_data[
            (control.control_id, "constructed")
        ]
        target_edge_desc, target_edges = edge_stage_data[
            (control.control_id, "step_imported")
        ]
        edge_rows = _edge_candidate_rows(
            "step_import",
            control.control_id,
            source_edge_desc,
            target_edge_desc,
            face_candidate_forward,
            face_candidate_reverse,
        )
        edge_candidates.extend(edge_rows)
        edge_direct_identity = {
            index: _edge_direct_identity_evidence(edge, target_edges)
            for index, edge in enumerate(source_edges, start=1)
        }
        edge_relations.extend(
            _edge_relations(
                "step_import",
                control.control_id,
                source_edge_desc,
                edge_rows,
                direct_identity_by_source=edge_direct_identity,
            )
        )

    split_imported = imported["split_box"]
    unifier = ShapeUpgrade_UnifySameDomain(split_imported, True, True, False)
    unifier.Build()
    healed = unifier.Shape()
    healed_data = _describe_faces("split_box", "healed", healed)
    stage_data[("split_box", "healed")] = healed_data
    descriptors.extend(healed_data[0])
    healed_edge_data = _describe_edges("split_box", "healed", healed)
    edge_stage_data[("split_box", "healed")] = healed_edge_data
    edge_descriptors.extend(healed_edge_data[0])
    previews.append(("split_box", "healed", healed))
    source_desc, source_faces = stage_data[("split_box", "step_imported")]
    target_desc, target_faces = healed_data
    heal_rows = _candidate_rows(
        "same_domain_healing",
        "split_box",
        source_desc,
        source_faces,
        target_desc,
        target_faces,
    )
    history = unifier.History()
    history_by_source = {
        index: _history_targets(history, face, target_faces)
        for index, face in enumerate(source_faces, start=1)
    }
    candidates.extend(heal_rows)
    heal_face_relation_rows = _relations(
        "same_domain_healing",
        "split_box",
        source_desc,
        heal_rows,
        history_by_source,
    )
    relations.extend(heal_face_relation_rows)
    source_edge_desc, source_edges = edge_stage_data[("split_box", "step_imported")]
    target_edge_desc, target_edges = healed_edge_data
    heal_edge_rows = _edge_candidate_rows(
        "same_domain_healing",
        "split_box",
        source_edge_desc,
        target_edge_desc,
        *_face_candidate_maps(heal_rows),
    )
    edge_history_by_source = {
        index: _edge_history_evidence(history, edge, target_edges)
        for index, edge in enumerate(source_edges, start=1)
    }
    edge_direct_identity = {
        index: _edge_direct_identity_evidence(edge, target_edges)
        for index, edge in enumerate(source_edges, start=1)
    }
    edge_candidates.extend(heal_edge_rows)
    edge_relations.extend(
        _edge_relations(
            "same_domain_healing",
            "split_box",
            source_edge_desc,
            heal_edge_rows,
            edge_history_by_source,
            edge_direct_identity,
        )
    )

    expected = {control.control_id: control for control in controls}
    for control_id in expected:
        constructed_count = len(stage_data[(control_id, "constructed")][0])
        imported_count = len(stage_data[(control_id, "step_imported")][0])
        constructed_edge_count = len(edge_stage_data[(control_id, "constructed")][0])
        imported_edge_count = len(edge_stage_data[(control_id, "step_imported")][0])
        if constructed_count != expected[control_id].expected_constructed_faces:
            raise RuntimeError(
                f"unexpected constructed face count for {control_id}: {constructed_count}"
            )
        if imported_count != expected[control_id].expected_imported_faces:
            raise RuntimeError(
                f"unexpected imported face count for {control_id}: {imported_count}"
            )
        if constructed_edge_count != expected[control_id].expected_constructed_edges:
            raise RuntimeError(
                f"unexpected constructed edge count for {control_id}: {constructed_edge_count}"
            )
        if imported_edge_count != expected[control_id].expected_imported_edges:
            raise RuntimeError(
                f"unexpected imported edge count for {control_id}: {imported_edge_count}"
            )
    if len(healed_data[0]) != 6:
        raise RuntimeError(
            f"unexpected healed split-box face count: {len(healed_data[0])}"
        )
    if len(healed_edge_data[0]) != 12:
        raise RuntimeError(
            f"unexpected healed split-box edge count: {len(healed_edge_data[0])}"
        )

    return ShapeCorrespondenceProbe(
        controls,
        tuple(fixtures),
        tuple(descriptors),
        tuple(candidates),
        tuple(relations),
        tuple(edge_descriptors),
        tuple(edge_candidates),
        tuple(edge_relations),
        tuple(previews),
    )
