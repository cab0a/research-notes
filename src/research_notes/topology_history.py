"""Evaluate fillets, chamfers, and operation-local topology history."""

from __future__ import annotations

import importlib.metadata
import math
from dataclasses import dataclass, replace
from typing import Literal

from research_notes.brep_runtime import (
    StepRoundTrip,
    indexed_shapes,
    step_round_trip,
    surface_area_and_centroid,
)
from research_notes.modeling_common import ShapeMetrics, measure_shape, surface_inventory


Operation = Literal["fillet", "chamfer"]
Stage = Literal["constructed", "step_imported"]
CONTRACT_VERSION = "1.0.0"


@dataclass(frozen=True)
class FeatureControl:
    """Synthetic local-operation truth retained outside the result shape."""

    control_id: str
    operation: Operation
    parameter_name: str
    parameter_value: float
    expected_decision: str
    selected_edge_endpoints: tuple[tuple[float, float, float], ...]
    expected_volume: float | None
    expected_surface_area: float | None


@dataclass(frozen=True)
class FeatureDecision:
    """Native completion status for one local operation attempt."""

    control_id: str
    decision: str
    reason: str
    kernel_invoked: bool
    is_done: bool
    contour_count: int


@dataclass(frozen=True)
class FeatureObservation:
    """One successful feature result before or after STEP exchange."""

    stage: Stage
    control_id: str
    source_file: str | None
    source_sha256: str | None
    metrics: ShapeMetrics
    expected_volume: float
    expected_surface_area: float
    volume_absolute_error: float
    surface_area_absolute_error: float


@dataclass(frozen=True)
class HistoryObservation:
    """One documented history query over an input subshape."""

    control_id: str
    source_kind: str
    source_index: int
    query_scope: str
    direct_result_indices: tuple[str, ...]
    generated_result_indices: tuple[str, ...]
    modified_result_indices: tuple[str, ...]
    is_deleted: bool | None
    modified_is_split: bool | None
    modified_target_max_source_count: int | None


@dataclass(frozen=True)
class FaceRoundTripMatch:
    """Geometry-matched face indices across one STEP read boundary."""

    control_id: str
    constructed_face_index: int
    imported_face_index: int
    surface_type: str
    area_absolute_difference: float
    centroid_distance: float
    index_values_equal: bool
    direct_topological_identity: bool
    operation_history_available_after_import: bool


@dataclass(frozen=True)
class TopologyHistoryProbe:
    """Complete v0.47.0 construction, history, and exchange evidence."""

    controls: tuple[FeatureControl, ...]
    decisions: tuple[FeatureDecision, ...]
    fixtures: tuple[StepRoundTrip, ...]
    observations: tuple[FeatureObservation, ...]
    history: tuple[HistoryObservation, ...]
    face_matches: tuple[FaceRoundTripMatch, ...]
    preview_shapes: tuple[tuple[str, object], ...]
    binding_distribution_version: str


def feature_controls() -> tuple[FeatureControl, ...]:
    """Return bounded successful and oversized local-operation controls."""
    edge = ((12.0, 0.0, 6.0), (12.0, 8.0, 6.0))
    fillet_volume = 576.0 - 8.0 * (1.0 - math.pi / 4.0)
    fillet_area = 432.0 - 16.0 + 4.0 * math.pi - 2.0 * (1.0 - math.pi / 4.0)
    chamfer_volume = 576.0 - 8.0 * 0.5
    chamfer_area = 432.0 - 16.0 + 8.0 * math.sqrt(2.0) - 1.0
    return (
        FeatureControl(
            "edge_fillet_r1",
            "fillet",
            "radius",
            1.0,
            "accept",
            edge,
            fillet_volume,
            fillet_area,
        ),
        FeatureControl(
            "edge_chamfer_d1",
            "chamfer",
            "distance",
            1.0,
            "accept",
            edge,
            chamfer_volume,
            chamfer_area,
        ),
        FeatureControl(
            "edge_fillet_r20",
            "fillet",
            "radius",
            20.0,
            "reject",
            edge,
            None,
            None,
        ),
        FeatureControl(
            "edge_chamfer_d20",
            "chamfer",
            "distance",
            20.0,
            "reject",
            edge,
            None,
            None,
        ),
    )


def _point(vertex: object) -> tuple[float, float, float]:
    from OCP.BRep import BRep_Tool
    from OCP.TopoDS import TopoDS

    point = BRep_Tool.Pnt_s(TopoDS.Vertex_s(vertex))
    return (float(point.X()), float(point.Y()), float(point.Z()))


def _selected_edge(shape: object, endpoints: tuple[tuple[float, float, float], ...]) -> tuple[int, object]:
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_VERTEX
    from OCP.TopoDS import TopoDS

    expected = {tuple(round(value, 9) for value in point) for point in endpoints}
    edges = indexed_shapes(shape, TopAbs_EDGE)
    for index in range(1, edges.Extent() + 1):
        edge = TopoDS.Edge_s(edges.FindKey(index))
        vertices = indexed_shapes(edge, TopAbs_VERTEX)
        actual = {
            tuple(round(value, 9) for value in _point(vertices.FindKey(vertex_index)))
            for vertex_index in range(1, vertices.Extent() + 1)
        }
        if actual == expected:
            return index, edge
    raise RuntimeError("controlled feature edge was not found")


def _build(control: FeatureControl) -> tuple[object, object, object]:
    from OCP.BRepFilletAPI import BRepFilletAPI_MakeChamfer, BRepFilletAPI_MakeFillet
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

    base = BRepPrimAPI_MakeBox(12.0, 8.0, 6.0).Shape()
    _, edge = _selected_edge(base, control.selected_edge_endpoints)
    if control.operation == "fillet":
        builder = BRepFilletAPI_MakeFillet(base)
    else:
        builder = BRepFilletAPI_MakeChamfer(base)
    builder.Add(control.parameter_value, edge)
    builder.Build()
    return base, edge, builder


def _result_indices(shape: object, target: object) -> tuple[str, ...]:
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_VERTEX

    values: list[str] = []
    for name, shape_type in (
        ("vertex", TopAbs_VERTEX),
        ("edge", TopAbs_EDGE),
        ("face", TopAbs_FACE),
    ):
        mapping = indexed_shapes(shape, shape_type)
        for index in range(1, mapping.Extent() + 1):
            if mapping.FindKey(index).IsSame(target):
                values.append(f"{name}:{index}")
    return tuple(values)


def _history_rows(control_id: str, base: object, result: object, builder: object) -> tuple[HistoryObservation, ...]:
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_VERTEX

    rows: list[HistoryObservation] = []
    for kind, shape_type in (
        ("vertex", TopAbs_VERTEX),
        ("edge", TopAbs_EDGE),
        ("face", TopAbs_FACE),
    ):
        sources = indexed_shapes(base, shape_type)
        for index in range(1, sources.Extent() + 1):
            source = sources.FindKey(index)
            generated = tuple(builder.Generated(source)) if kind in {"vertex", "edge"} else ()
            modified = tuple(builder.Modified(source)) if kind == "face" else ()
            rows.append(
                HistoryObservation(
                    control_id,
                    kind,
                    index,
                    {
                        "vertex": "Generated(vertex)",
                        "edge": "Generated(edge)",
                        "face": "Modified(face)|IsDeleted(face)",
                    }[kind],
                    _result_indices(result, source),
                    tuple(value for item in generated for value in _result_indices(result, item)),
                    tuple(value for item in modified for value in _result_indices(result, item)),
                    bool(builder.IsDeleted(source)) if kind == "face" else None,
                    len(modified) > 1 if kind == "face" else None,
                    None,
                )
            )

    modified_owners: dict[str, int] = {}
    for row in rows:
        for target in set(row.modified_result_indices):
            modified_owners[target] = modified_owners.get(target, 0) + 1
    return tuple(
        replace(
            row,
            modified_target_max_source_count=(
                max((modified_owners[target] for target in row.modified_result_indices), default=0)
                if row.source_kind == "face"
                else None
            ),
        )
        for row in rows
    )


def _face_descriptors(shape: object) -> tuple[tuple[int, object, str, float, tuple[float, float, float]], ...]:
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopoDS import TopoDS

    faces = indexed_shapes(shape, TopAbs_FACE)
    rows: list[tuple[int, object, str, float, tuple[float, float, float]]] = []
    for index in range(1, faces.Extent() + 1):
        face = TopoDS.Face_s(faces.FindKey(index))
        area, centroid = surface_area_and_centroid(face)
        surface_type = surface_inventory(face)[0][0]
        rows.append((index, face, surface_type, area, centroid))
    return tuple(rows)


def _distance(first: tuple[float, float, float], second: tuple[float, float, float]) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(first, second, strict=True)))


def _match_faces(control_id: str, constructed: object, imported: object) -> tuple[FaceRoundTripMatch, ...]:
    first_rows = _face_descriptors(constructed)
    second_rows = _face_descriptors(imported)
    available = {item[0]: item for item in second_rows}
    matches: list[FaceRoundTripMatch] = []
    for first_index, first_face, surface_type, first_area, first_centroid in first_rows:
        candidates = [
            (
                abs(first_area - second_area) + _distance(first_centroid, second_centroid),
                second_index,
                second_face,
                second_area,
                second_centroid,
            )
            for second_index, second_face, second_type, second_area, second_centroid in available.values()
            if second_type == surface_type
        ]
        if not candidates:
            raise RuntimeError("controlled feature face matching failed")
        _, second_index, second_face, second_area, second_centroid = min(candidates)
        del available[second_index]
        matches.append(
            FaceRoundTripMatch(
                control_id,
                first_index,
                second_index,
                surface_type,
                abs(first_area - second_area),
                _distance(first_centroid, second_centroid),
                first_index == second_index,
                bool(first_face.IsSame(second_face)),
                False,
            )
        )
    return tuple(matches)


def _observe(
    control: FeatureControl,
    stage: Stage,
    shape: object,
    fixture: StepRoundTrip | None,
) -> FeatureObservation:
    if control.expected_volume is None or control.expected_surface_area is None:
        raise ValueError("successful feature controls require analytic truth")
    metrics = measure_shape(shape)
    return FeatureObservation(
        stage,
        control.control_id,
        None if fixture is None else fixture.file_name,
        None if fixture is None else fixture.source_sha256,
        metrics,
        control.expected_volume,
        control.expected_surface_area,
        abs(metrics.absolute_volume - control.expected_volume),
        abs(metrics.surface_area - control.expected_surface_area),
    )


def probe_topology_history() -> TopologyHistoryProbe:
    """Run the complete deterministic v0.47.0 study."""
    controls = feature_controls()
    decisions: list[FeatureDecision] = []
    fixtures: list[StepRoundTrip] = []
    observations: list[FeatureObservation] = []
    history: list[HistoryObservation] = []
    face_matches: list[FaceRoundTripMatch] = []
    previews: list[tuple[str, object]] = []
    for control in controls:
        base, _, builder = _build(control)
        is_done = bool(builder.IsDone())
        decision = "accept" if is_done else "reject"
        reason = "constructed" if is_done else "native_not_done"
        decisions.append(
            FeatureDecision(
                control.control_id,
                decision,
                reason,
                True,
                is_done,
                int(builder.NbContours()),
            )
        )
        if not is_done:
            continue
        result = builder.Shape()
        fixture = step_round_trip(result, control.control_id)
        fixtures.append(fixture)
        observations.append(_observe(control, "constructed", result, None))
        observations.append(_observe(control, "step_imported", fixture.imported_shape, fixture))
        history.extend(_history_rows(control.control_id, base, result, builder))
        face_matches.extend(_match_faces(control.control_id, result, fixture.imported_shape))
        previews.append((control.control_id, fixture.imported_shape))
    return TopologyHistoryProbe(
        controls,
        tuple(decisions),
        tuple(fixtures),
        tuple(observations),
        tuple(history),
        tuple(face_matches),
        tuple(previews),
        importlib.metadata.version("cadquery-ocp"),
    )
