"""Evaluate tolerance-mediated sewing and bounded shell-orientation repair."""

from __future__ import annotations

import importlib.metadata
import itertools
import math
from collections import deque
from dataclasses import dataclass
from typing import Literal

from research_notes.brep_runtime import (
    indexed_shapes,
    shape_type_name,
    signed_volume,
    status_name,
    step_entity_count,
    step_round_trip,
    surface_area_and_centroid,
    topology_counts,
)


Vector3 = tuple[float, float, float]
ObservationStage = Literal[
    "constructed",
    "sewn",
    "orientation_input",
    "orientation_repaired",
    "tolerance_capped",
]


@dataclass(frozen=True)
class SewingControl:
    """Independent gap truth for one six-face box construction."""

    control_id: str
    condition: str
    gap: float


@dataclass(frozen=True)
class SewingSetting:
    """One explicitly requested global sewing tolerance."""

    setting_id: str
    tolerance: float


@dataclass(frozen=True)
class ShapeObservation:
    """Topology, orientation, tolerance, geometry, and validity at one stage."""

    observation_id: str
    parent_observation_id: str | None
    stage: ObservationStage
    control_id: str
    condition: str
    operation_id: str | None
    controlled_gap: float
    requested_tolerance: float | None
    observed_shape_type: str
    vertex_count: int
    edge_count: int
    face_count: int
    shell_count: int
    solid_count: int
    face_component_count: int
    boundary_edge_count: int
    manifold_pair_edge_count: int
    nonmanifold_edge_count: int
    closed_by_incidence: bool
    orientable_manifold: bool
    current_orientation_consistent: bool
    minimum_face_flips: int | None
    closed_oriented_shell_candidate: bool
    kernel_analyzer_valid: bool
    vertex_tolerance_min: float
    vertex_tolerance_mean: float
    vertex_tolerance_max: float
    edge_tolerance_min: float
    edge_tolerance_mean: float
    edge_tolerance_max: float
    face_tolerance_min: float
    face_tolerance_mean: float
    face_tolerance_max: float
    surface_area: float
    maximum_face_area_error: float
    maximum_face_centroid_distance: float
    maximum_support_plane_error: float
    face_geometry_matches_control: bool
    raw_signed_volume: float
    volume_contract_eligible: bool
    volume_magnitude_absolute_error: float | None


@dataclass(frozen=True)
class SubshapeToleranceObservation:
    """One analysis-local B-Rep tolerance with no persistent-identity claim."""

    observation_id: str
    control_id: str
    stage: ObservationStage
    entity_type: Literal["vertex", "edge", "face"]
    analysis_local_index: int
    tolerance: float


@dataclass(frozen=True)
class OperationObservation:
    """Configuration and observed effects for one explicit shape operation."""

    operation_id: str
    control_id: str
    operation_type: Literal[
        "sew_faces", "fix_face_orientation", "limit_tolerance"
    ]
    input_observation_id: str
    output_observation_id: str
    requested_tolerance: float | None
    maximum_tolerance_limit: float | None
    local_tolerances_mode: bool | None
    nonmanifold_mode: bool | None
    performed: bool
    reported_modified: bool
    modified_input_face_count: int | None
    reported_free_edge_count: int | None
    reported_contiguous_edge_count: int | None
    reported_multiple_edge_count: int | None
    reported_deleted_face_count: int | None
    reported_degenerated_shape_count: int | None
    topology_changed: bool
    tolerance_changed: bool
    geometry_changed: bool
    kernel_validity_change: str
    decision: Literal[
        "accepted_control", "review_required", "not_closed", "no_change", "rejected_invalid"
    ]
    decision_reason: str


@dataclass(frozen=True)
class ToleranceFixture:
    """One normalized STEP sample retained for visual and exchange inspection."""

    fixture_id: str
    observation_id: str
    artifact_role: str
    file_name: str
    source_bytes: bytes
    source_sha256: str
    writer_status: str
    reader_status: str
    transferred_roots: int
    step_processor: str
    step_advanced_face_count: int
    step_open_shell_count: int
    step_closed_shell_count: int
    imported_vertex_count: int
    imported_edge_count: int
    imported_face_count: int
    imported_shell_count: int
    imported_solid_count: int
    imported_kernel_analyzer_valid: bool


@dataclass(frozen=True)
class ToleranceSewingProbe:
    """Complete controlled sewing, repair, and tolerance-change evidence."""

    platform_label: str
    binding_distribution_version: str
    binding_module_version: str
    step_processor: str
    observations: tuple[ShapeObservation, ...]
    tolerance_observations: tuple[SubshapeToleranceObservation, ...]
    operations: tuple[OperationObservation, ...]
    fixtures: tuple[ToleranceFixture, ...]


def tolerance_sewing_controls() -> tuple[SewingControl, ...]:
    """Return fixed exact, sub-micrometre, and larger-gap controls."""
    return (
        SewingControl(
            "coincident_box_faces",
            "six independent box faces with coincident boundaries",
            0.0,
        ),
        SewingControl(
            "small_gap_box_faces",
            "six independent box faces with the top face displaced by 5e-7",
            5.0e-7,
        ),
        SewingControl(
            "large_gap_box_faces",
            "six independent box faces with the top face displaced by 5e-5",
            5.0e-5,
        ),
    )


def sewing_settings() -> tuple[SewingSetting, ...]:
    """Return the fixed global sewing-tolerance sweep."""
    return (
        SewingSetting("tol_1e_7", 1.0e-7),
        SewingSetting("tol_1e_6", 1.0e-6),
        SewingSetting("tol_1e_4", 1.0e-4),
    )


def analytic_box_surface_area(width: float, depth: float, height: float) -> float:
    """Return independent rectangular-box surface-area truth."""
    values = (width, depth, height)
    if any(
        isinstance(value, bool) or not isinstance(value, (int, float))
        for value in values
    ):
        raise TypeError("box dimensions must be real numbers")
    numeric = tuple(float(value) for value in values)
    if any(not math.isfinite(value) or value <= 0.0 for value in numeric):
        raise ValueError("box dimensions must be finite and positive")
    width_value, depth_value, height_value = numeric
    return 2.0 * (
        width_value * depth_value
        + width_value * height_value
        + depth_value * height_value
    )


def _validate_nonnegative_finite(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    numeric = float(value)
    if not math.isfinite(numeric) or numeric < 0.0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return numeric


def _polygon_face(points: tuple[Vector3, ...]) -> object:
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
    from OCP.gp import gp_Pnt

    polygon = BRepBuilderAPI_MakePolygon()
    for point in points:
        polygon.Add(gp_Pnt(*point))
    polygon.Close()
    return BRepBuilderAPI_MakeFace(polygon.Wire()).Face()


def _independent_box_faces(gap: float) -> tuple[object, ...]:
    gap_value = _validate_nonnegative_finite(gap, "gap")
    x0, x1 = 0.0, 4.0
    y0, y1 = 0.0, 5.0
    z0, z1 = 0.0, 6.0
    return (
        _polygon_face(((x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0))),
        _polygon_face(((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1))),
        _polygon_face(((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1))),
        _polygon_face(((x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1))),
        _polygon_face(((x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1))),
        _polygon_face(
            (
                (x0, y0, z1 + gap_value),
                (x1, y0, z1 + gap_value),
                (x1, y1, z1 + gap_value),
                (x0, y1, z1 + gap_value),
            )
        ),
    )


def _compound(faces: tuple[object, ...]) -> object:
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound

    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    for face in faces:
        builder.Add(compound, face)
    return compound


def _face_centroid(face: object) -> Vector3:
    return surface_area_and_centroid(face)[1]


def _connected_box_shell(*, flip_max_x: bool) -> object:
    from OCP.BRep import BRep_Builder
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS, TopoDS_Shell
    from OCP.gp import gp_Pnt

    box = BRepPrimAPI_MakeBox(gp_Pnt(0.0, 0.0, 0.0), 4.0, 5.0, 6.0).Shape()
    builder = BRep_Builder()
    shell = TopoDS_Shell()
    builder.MakeShell(shell)
    explorer = TopExp_Explorer(box, TopAbs_FACE)
    while explorer.More():
        face = TopoDS.Face_s(explorer.Current())
        if flip_max_x and math.isclose(
            _face_centroid(face)[0], 4.0, abs_tol=1.0e-12
        ):
            face = TopoDS.Face_s(face.Reversed())
        builder.Add(shell, face)
        explorer.Next()
    return shell


def _orientation_name(value: object) -> str:
    from OCP.TopAbs import TopAbs_FORWARD, TopAbs_REVERSED

    if value == TopAbs_FORWARD:
        return "forward"
    if value == TopAbs_REVERSED:
        return "reversed"
    return status_name(value).removeprefix("TopAbs_").lower()


def _edge_uses(shape: object, face_map: object, edge_map: object) -> dict[int, list[tuple[int, str]]]:
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    uses: dict[int, list[tuple[int, str]]] = {
        index: [] for index in range(1, int(edge_map.Extent()) + 1)
    }
    face_explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while face_explorer.More():
        face = TopoDS.Face_s(face_explorer.Current())
        face_index = int(face_map.FindIndex(face))
        edge_explorer = TopExp_Explorer(face, TopAbs_EDGE)
        while edge_explorer.More():
            edge = TopoDS.Edge_s(edge_explorer.Current())
            uses[int(edge_map.FindIndex(edge))].append(
                (face_index, _orientation_name(edge.Orientation()))
            )
            edge_explorer.Next()
        face_explorer.Next()
    return uses


def _face_components(face_count: int, uses: dict[int, list[tuple[int, str]]]) -> int:
    adjacency = {index: set() for index in range(1, face_count + 1)}
    for edge_uses in uses.values():
        faces = sorted({face_index for face_index, _ in edge_uses})
        for left in faces:
            adjacency[left].update(right for right in faces if right != left)
    component_count = 0
    unseen = set(adjacency)
    while unseen:
        component_count += 1
        queue = deque([min(unseen)])
        while queue:
            face_index = queue.popleft()
            if face_index not in unseen:
                continue
            unseen.remove(face_index)
            queue.extend(sorted(adjacency[face_index] & unseen))
    return component_count


def _orientation_contract(
    face_count: int, uses: dict[int, list[tuple[int, str]]]
) -> tuple[bool, bool, int | None]:
    adjacency: dict[int, list[tuple[int, int]]] = {
        index: [] for index in range(1, face_count + 1)
    }
    contradiction = False
    nonmanifold = False
    current_consistent = True
    for edge_uses in uses.values():
        if len(edge_uses) > 2:
            nonmanifold = True
            current_consistent = False
            continue
        if len(edge_uses) != 2:
            continue
        (left_face, left_orientation), (right_face, right_orientation) = edge_uses
        opposed = left_orientation != right_orientation
        current_consistent &= opposed
        required_xor = 0 if opposed else 1
        if left_face == right_face:
            contradiction |= required_xor == 1
            continue
        adjacency[left_face].append((right_face, required_xor))
        adjacency[right_face].append((left_face, required_xor))

    assignments: dict[int, int] = {}
    minimum_flips = 0
    for start in range(1, face_count + 1):
        if start in assignments:
            continue
        assignments[start] = 0
        queue = deque([start])
        group: list[int] = []
        while queue:
            face_index = queue.popleft()
            group.append(face_index)
            for neighbor, required_xor in adjacency[face_index]:
                expected = assignments[face_index] ^ required_xor
                if neighbor in assignments:
                    contradiction |= assignments[neighbor] != expected
                else:
                    assignments[neighbor] = expected
                    queue.append(neighbor)
        ones = sum(assignments[index] for index in group)
        minimum_flips += min(ones, len(group) - ones)
    orientable = not nonmanifold and not contradiction
    return orientable, current_consistent, minimum_flips if orientable else None


def _subshape_tolerances(
    shape: object,
    observation_id: str,
    control_id: str,
    stage: ObservationStage,
) -> tuple[SubshapeToleranceObservation, ...]:
    from OCP.BRep import BRep_Tool
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_VERTEX
    from OCP.TopoDS import TopoDS

    requests = (
        ("vertex", TopAbs_VERTEX, TopoDS.Vertex_s),
        ("edge", TopAbs_EDGE, TopoDS.Edge_s),
        ("face", TopAbs_FACE, TopoDS.Face_s),
    )
    rows: list[SubshapeToleranceObservation] = []
    for entity_type, shape_type, converter in requests:
        mapping = indexed_shapes(shape, shape_type)
        for index in range(1, int(mapping.Extent()) + 1):
            rows.append(
                SubshapeToleranceObservation(
                    observation_id,
                    control_id,
                    stage,
                    entity_type,  # type: ignore[arg-type]
                    index,
                    float(BRep_Tool.Tolerance_s(converter(mapping.FindKey(index)))),
                )
            )
    return tuple(rows)


def _tolerance_statistics(
    rows: tuple[SubshapeToleranceObservation, ...], entity_type: str
) -> tuple[float, float, float]:
    values = [item.tolerance for item in rows if item.entity_type == entity_type]
    if not values:
        return 0.0, 0.0, 0.0
    return min(values), sum(values) / len(values), max(values)


def _face_descriptors(
    shape: object,
) -> tuple[tuple[float, float, float, float, float, float, float, float], ...]:
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Plane
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopoDS import TopoDS

    mapping = indexed_shapes(shape, TopAbs_FACE)
    descriptors: list[
        tuple[float, float, float, float, float, float, float, float]
    ] = []
    for index in range(1, int(mapping.Extent()) + 1):
        face = TopoDS.Face_s(mapping.FindKey(index))
        area, centroid = surface_area_and_centroid(face)
        adaptor = BRepAdaptor_Surface(face, True)
        if adaptor.GetType() != GeomAbs_Plane:
            raise RuntimeError("controlled tolerance faces must remain planar")
        plane = adaptor.Plane()
        direction = plane.Axis().Direction()
        normal = [float(direction.X()), float(direction.Y()), float(direction.Z())]
        for value in normal:
            if abs(value) > 1.0e-15:
                if value < 0.0:
                    normal = [-component for component in normal]
                break
        location = plane.Location()
        offset = sum(
            component * coordinate
            for component, coordinate in zip(
                normal,
                (float(location.X()), float(location.Y()), float(location.Z())),
                strict=True,
            )
        )
        descriptors.append((*centroid, area, *normal, offset))
    return tuple(sorted(descriptors))


def _descriptor_errors(
    observed: tuple[
        tuple[float, float, float, float, float, float, float, float], ...
    ],
    expected: tuple[
        tuple[float, float, float, float, float, float, float, float], ...
    ],
) -> tuple[float, float, float]:
    if len(observed) != len(expected):
        return math.inf, math.inf, math.inf
    best: tuple[float, float, float, float] | None = None
    for permutation in itertools.permutations(observed):
        area_error = max(
            (abs(item[3] - truth[3]) for item, truth in zip(permutation, expected)),
            default=0.0,
        )
        centroid_error = max(
            (
                math.dist(item[:3], truth[:3])
                for item, truth in zip(permutation, expected)
            ),
            default=0.0,
        )
        support_plane_error = max(
            (
                max(
                    abs(value - target)
                    for value, target in zip(item[4:], truth[4:], strict=True)
                )
                for item, truth in zip(permutation, expected, strict=True)
            ),
            default=0.0,
        )
        score = area_error + centroid_error + support_plane_error
        candidate = (score, area_error, centroid_error, support_plane_error)
        if best is None or candidate < best:
            best = candidate
    if best is None:
        return 0.0, 0.0, 0.0
    return best[1], best[2], best[3]


def _measure_shape(
    shape: object,
    *,
    observation_id: str,
    parent_observation_id: str | None,
    stage: ObservationStage,
    control_id: str,
    condition: str,
    operation_id: str | None,
    controlled_gap: float,
    requested_tolerance: float | None,
    expected_face_descriptors: tuple[
        tuple[float, float, float, float, float, float, float, float], ...
    ],
) -> tuple[ShapeObservation, tuple[SubshapeToleranceObservation, ...]]:
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE

    vertices, edges, faces, shells, solids = topology_counts(shape)
    face_map = indexed_shapes(shape, TopAbs_FACE)
    edge_map = indexed_shapes(shape, TopAbs_EDGE)
    uses = _edge_uses(shape, face_map, edge_map)
    boundary_count = sum(len(item) == 1 for item in uses.values())
    manifold_pair_count = sum(len(item) == 2 for item in uses.values())
    nonmanifold_count = sum(len(item) > 2 for item in uses.values())
    closed = (
        bool(uses)
        and boundary_count == 0
        and nonmanifold_count == 0
        and manifold_pair_count == len(uses)
    )
    orientable, current_orientation, minimum_flips = _orientation_contract(
        faces, uses
    )
    component_count = _face_components(faces, uses)
    candidate = (
        closed and orientable and current_orientation and component_count == 1
    )
    tolerance_rows = _subshape_tolerances(
        shape, observation_id, control_id, stage
    )
    vertex_stats = _tolerance_statistics(tolerance_rows, "vertex")
    edge_stats = _tolerance_statistics(tolerance_rows, "edge")
    face_stats = _tolerance_statistics(tolerance_rows, "face")
    observed_descriptors = _face_descriptors(shape)
    area_error, centroid_error, support_plane_error = _descriptor_errors(
        observed_descriptors, expected_face_descriptors
    )
    surface_area = sum(item[3] for item in observed_descriptors)
    volume = signed_volume(shape)
    volume_eligible = candidate and controlled_gap == 0.0
    volume_error = abs(abs(volume) - 120.0) if volume_eligible else None
    return (
        ShapeObservation(
            observation_id,
            parent_observation_id,
            stage,
            control_id,
            condition,
            operation_id,
            controlled_gap,
            requested_tolerance,
            shape_type_name(shape),
            vertices,
            edges,
            faces,
            shells,
            solids,
            component_count,
            boundary_count,
            manifold_pair_count,
            nonmanifold_count,
            closed,
            orientable,
            current_orientation,
            minimum_flips,
            candidate,
            bool(BRepCheck_Analyzer(shape).IsValid()),
            *vertex_stats,
            *edge_stats,
            *face_stats,
            surface_area,
            area_error,
            centroid_error,
            support_plane_error,
            area_error <= 1.0e-12
            and centroid_error <= 1.0e-12
            and support_plane_error <= 1.0e-12,
            volume,
            volume_eligible,
            volume_error,
        ),
        tolerance_rows,
    )


def _topology_changed(left: ShapeObservation, right: ShapeObservation) -> bool:
    return (
        left.vertex_count,
        left.edge_count,
        left.face_count,
        left.shell_count,
        left.solid_count,
        left.face_component_count,
        left.boundary_edge_count,
    ) != (
        right.vertex_count,
        right.edge_count,
        right.face_count,
        right.shell_count,
        right.solid_count,
        right.face_component_count,
        right.boundary_edge_count,
    )


def _tolerance_changed(left: ShapeObservation, right: ShapeObservation) -> bool:
    return not all(
        math.isclose(first, second, rel_tol=0.0, abs_tol=1.0e-15)
        for first, second in (
            (left.vertex_tolerance_max, right.vertex_tolerance_max),
            (left.edge_tolerance_max, right.edge_tolerance_max),
            (left.face_tolerance_max, right.face_tolerance_max),
        )
    )


def _operation_change_fields(
    left: ShapeObservation, right: ShapeObservation
) -> tuple[bool, bool, bool, str]:
    return (
        _topology_changed(left, right),
        _tolerance_changed(left, right),
        not right.face_geometry_matches_control,
        f"{int(left.kernel_analyzer_valid)}->{int(right.kernel_analyzer_valid)}",
    )


def _fixture(
    shape: object, fixture_id: str, observation_id: str, artifact_role: str
) -> ToleranceFixture:
    from OCP.BRepCheck import BRepCheck_Analyzer

    round_trip = step_round_trip(shape, fixture_id)
    counts = topology_counts(round_trip.imported_shape)
    return ToleranceFixture(
        fixture_id,
        observation_id,
        artifact_role,
        round_trip.file_name,
        round_trip.source_bytes,
        round_trip.source_sha256,
        round_trip.writer_status,
        round_trip.reader_status,
        round_trip.transferred_roots,
        round_trip.step_processor,
        step_entity_count(round_trip.source_bytes, "ADVANCED_FACE"),
        step_entity_count(round_trip.source_bytes, "OPEN_SHELL"),
        step_entity_count(round_trip.source_bytes, "CLOSED_SHELL"),
        *counts,
        bool(BRepCheck_Analyzer(round_trip.imported_shape).IsValid()),
    )


def probe_tolerance_sewing_healing(
    *, platform_label: str = "linux-x64-reference"
) -> ToleranceSewingProbe:
    """Run the fixed sewing matrix, orientation controls, and unsafe clamp."""
    if not isinstance(platform_label, str):
        raise TypeError("platform_label must be a string")
    if not platform_label:
        raise ValueError("platform_label must not be empty")

    import OCP
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing
    from OCP.ShapeFix import ShapeFix_ShapeTolerance, ShapeFix_Shell
    from OCP.TopAbs import TopAbs_SHAPE
    from OCP.TopoDS import TopoDS

    observations: list[ShapeObservation] = []
    tolerance_rows: list[SubshapeToleranceObservation] = []
    operations: list[OperationObservation] = []
    fixture_requests: list[tuple[object, str, str, str]] = []
    observed_by_id: dict[str, ShapeObservation] = {}

    def add_measurement(measured: tuple[ShapeObservation, tuple[SubshapeToleranceObservation, ...]]) -> ShapeObservation:
        observation, rows = measured
        observations.append(observation)
        tolerance_rows.extend(rows)
        observed_by_id[observation.observation_id] = observation
        return observation

    selected_sewn_shapes: dict[str, object] = {}
    expected_by_control: dict[str, tuple[tuple[float, float, float, float], ...]] = {}
    for control in tolerance_sewing_controls():
        source_faces = _independent_box_faces(control.gap)
        source_shape = _compound(source_faces)
        expected_descriptors = _face_descriptors(source_shape)
        expected_by_control[control.control_id] = expected_descriptors
        source_id = f"{control.control_id}__constructed"
        source = add_measurement(
            _measure_shape(
                source_shape,
                observation_id=source_id,
                parent_observation_id=None,
                stage="constructed",
                control_id=control.control_id,
                condition=control.condition,
                operation_id=None,
                controlled_gap=control.gap,
                requested_tolerance=None,
                expected_face_descriptors=expected_descriptors,
            )
        )
        fixture_requests.append(
            (source_shape, f"{control.control_id}_input", source_id, "operation_input")
        )

        for setting in sewing_settings():
            faces = _independent_box_faces(control.gap)
            sewing = BRepBuilderAPI_Sewing(
                setting.tolerance, True, True, True, False
            )
            sewing.SetLocalTolerancesMode(False)
            sewing.SetSameParameterMode(True)
            sewing.SetNonManifoldMode(False)
            for face in faces:
                sewing.Add(face)
            sewing.Perform()
            output_shape = sewing.SewedShape()
            operation_id = f"sew_{control.control_id}_{setting.setting_id}"
            output_id = f"{control.control_id}__sewn_{setting.setting_id}"
            output = add_measurement(
                _measure_shape(
                    output_shape,
                    observation_id=output_id,
                    parent_observation_id=source_id,
                    stage="sewn",
                    control_id=control.control_id,
                    condition=control.condition,
                    operation_id=operation_id,
                    controlled_gap=control.gap,
                    requested_tolerance=setting.tolerance,
                    expected_face_descriptors=expected_descriptors,
                )
            )
            modified_face_count = sum(bool(sewing.IsModified(face)) for face in faces)
            change_fields = _operation_change_fields(source, output)
            if not output.closed_by_incidence:
                decision = "not_closed"
                reason = "the controlled free boundary remains after sewing"
            elif control.gap == 0.0:
                decision = "accepted_control"
                reason = "coincident boundaries form the exact positive control"
            else:
                decision = "review_required"
                reason = "closure depends on a tolerance envelope across a real gap"
            operations.append(
                OperationObservation(
                    operation_id,
                    control.control_id,
                    "sew_faces",
                    source_id,
                    output_id,
                    setting.tolerance,
                    None,
                    False,
                    False,
                    True,
                    modified_face_count > 0,
                    modified_face_count,
                    int(sewing.NbFreeEdges()),
                    int(sewing.NbContigousEdges()),
                    int(sewing.NbMultipleEdges()),
                    int(sewing.NbDeletedFaces()),
                    int(sewing.NbDegeneratedShapes()),
                    *change_fields,
                    decision,  # type: ignore[arg-type]
                    reason,
                )
            )
            if setting.setting_id == "tol_1e_4":
                selected_sewn_shapes[control.control_id] = output_shape

    for control_id, flip_face in (
        ("valid_box_shell", False),
        ("flipped_face_box_shell", True),
    ):
        condition = (
            "connected box shell with consistent face orientations"
            if not flip_face
            else "connected box shell with one reversed face"
        )
        input_shape = _connected_box_shell(flip_max_x=flip_face)
        expected_descriptors = _face_descriptors(input_shape)
        input_id = f"{control_id}__orientation_input"
        input_observation = add_measurement(
            _measure_shape(
                input_shape,
                observation_id=input_id,
                parent_observation_id=None,
                stage="orientation_input",
                control_id=control_id,
                condition=condition,
                operation_id=None,
                controlled_gap=0.0,
                requested_tolerance=None,
                expected_face_descriptors=expected_descriptors,
            )
        )
        fixer = ShapeFix_Shell()
        modified = bool(
            fixer.FixFaceOrientation(TopoDS.Shell_s(input_shape), True, False)
        )
        output_shape = fixer.Shape()
        operation_id = f"fix_orientation_{control_id}"
        output_id = f"{control_id}__orientation_repaired"
        output_observation = add_measurement(
            _measure_shape(
                output_shape,
                observation_id=output_id,
                parent_observation_id=input_id,
                stage="orientation_repaired",
                control_id=control_id,
                condition=condition,
                operation_id=operation_id,
                controlled_gap=0.0,
                requested_tolerance=None,
                expected_face_descriptors=expected_descriptors,
            )
        )
        change_fields = _operation_change_fields(
            input_observation, output_observation
        )
        operations.append(
            OperationObservation(
                operation_id,
                control_id,
                "fix_face_orientation",
                input_id,
                output_id,
                None,
                None,
                None,
                False,
                True,
                modified,
                None,
                None,
                None,
                None,
                None,
                None,
                *change_fields,
                "accepted_control" if flip_face else "no_change",
                (
                    "one controlled reversed face is reoriented"
                    if flip_face
                    else "the valid shell requires no orientation change"
                ),
            )
        )
        fixture_requests.append(
            (input_shape, f"{control_id}_input", input_id, "repair_input")
        )
        if flip_face:
            fixture_requests.append(
                (
                    output_shape,
                    f"{control_id}_reoriented",
                    output_id,
                    "repair_output",
                )
            )

    large_control = next(
        item
        for item in tolerance_sewing_controls()
        if item.control_id == "large_gap_box_faces"
    )
    clamp_input_faces = _independent_box_faces(large_control.gap)
    clamp_sewing = BRepBuilderAPI_Sewing(1.0e-4, True, True, True, False)
    for face in clamp_input_faces:
        clamp_sewing.Add(face)
    clamp_sewing.Perform()
    clamp_shape = clamp_sewing.SewedShape()
    cap_limit = 1.0e-5
    capper = ShapeFix_ShapeTolerance()
    cap_modified = bool(
        capper.LimitTolerance(clamp_shape, 0.0, cap_limit, TopAbs_SHAPE)
    )
    cap_operation_id = "limit_large_gap_tolerance_to_1e_5"
    cap_output_id = "large_gap_box_faces__tolerance_capped_1e_5"
    cap_output = add_measurement(
        _measure_shape(
            clamp_shape,
            observation_id=cap_output_id,
            parent_observation_id="large_gap_box_faces__sewn_tol_1e_4",
            stage="tolerance_capped",
            control_id=large_control.control_id,
            condition="sewn large-gap shell with subshape tolerances capped at 1e-5",
            operation_id=cap_operation_id,
            controlled_gap=large_control.gap,
            requested_tolerance=cap_limit,
            expected_face_descriptors=expected_by_control[large_control.control_id],
        )
    )
    cap_input = observed_by_id["large_gap_box_faces__sewn_tol_1e_4"]
    operations.append(
        OperationObservation(
            cap_operation_id,
            large_control.control_id,
            "limit_tolerance",
            cap_input.observation_id,
            cap_output_id,
            None,
            cap_limit,
            None,
            None,
            True,
            cap_modified,
            None,
            None,
            None,
            None,
            None,
            None,
            *_operation_change_fields(cap_input, cap_output),
            "rejected_invalid",
            "lowering stored tolerances below the sewn residual invalidates the shape",
        )
    )

    fixture_requests.extend(
        (
            (
                selected_sewn_shapes["coincident_box_faces"],
                "coincident_box_faces_sewn_tol_1e_4",
                "coincident_box_faces__sewn_tol_1e_4",
                "sewing_output",
            ),
            (
                selected_sewn_shapes["small_gap_box_faces"],
                "small_gap_box_faces_sewn_tol_1e_4",
                "small_gap_box_faces__sewn_tol_1e_4",
                "sewing_output",
            ),
            (
                selected_sewn_shapes["large_gap_box_faces"],
                "large_gap_box_faces_sewn_tol_1e_4",
                "large_gap_box_faces__sewn_tol_1e_4",
                "sewing_output",
            ),
            (
                clamp_shape,
                "large_gap_box_faces_tolerance_capped",
                cap_output_id,
                "rejected_tolerance_output",
            ),
        )
    )

    fixtures = tuple(
        _fixture(shape, fixture_id, observation_id, artifact_role)
        for shape, fixture_id, observation_id, artifact_role in fixture_requests
    )
    processors = {item.step_processor for item in fixtures}
    if len(processors) != 1:
        raise RuntimeError("controlled fixtures reported inconsistent STEP processors")
    return ToleranceSewingProbe(
        platform_label,
        importlib.metadata.version("cadquery-ocp"),
        str(OCP.__version__),
        processors.pop(),
        tuple(observations),
        tuple(tolerance_rows),
        tuple(operations),
        fixtures,
    )
