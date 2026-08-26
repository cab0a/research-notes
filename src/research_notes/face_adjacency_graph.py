"""Build provenance-bound face-adjacency graphs from controlled B-Reps."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
from dataclasses import dataclass
from typing import Literal

from research_notes.brep_runtime import (
    StepRoundTrip,
    indexed_shapes,
    iter_shapes,
    status_name,
    step_round_trip,
)
from research_notes.feature_recognition import _measure_graph, build_feature_shapes
from research_notes.modeling_common import ShapeMetrics, measure_shape


CONTRACT_VERSION = "1.0.0"
GraphStage = Literal["constructed", "step_imported"]
Vector3 = tuple[float, float, float]


@dataclass(frozen=True)
class FaceGraphControl:
    """One synthetic shape family selected for graph diversity."""

    control_id: str
    condition: str


@dataclass(frozen=True)
class FaceGraphNode:
    """One graph-local face node with geometric and topological descriptors."""

    control_id: str
    stage: GraphStage
    source_file: str | None
    source_sha256: str | None
    node_id: str
    analysis_face_index: int
    surface_type: str
    orientation: str
    area: float
    centroid: Vector3
    representative_normal: Vector3
    u_span: float
    v_span: float
    axis_origin: Vector3 | None
    axis_direction: Vector3 | None
    radius: float | None
    radial_polarity: float | None
    maximum_absolute_curvature: float | None
    wire_count: int
    inner_wire_count: int
    boundary_edge_count: int
    face_tolerance: float
    maximum_edge_length: float
    adjacent_node_ids: tuple[str, ...]
    degree: int
    topology_provenance: str
    geometry_provenance: str
    exchange_provenance: str


@dataclass(frozen=True)
class FaceGraphRelation:
    """One shared-edge relation between exactly two graph-local face nodes."""

    control_id: str
    stage: GraphStage
    source_file: str | None
    source_sha256: str | None
    relation_id: str
    analysis_edge_index: int
    first_node_id: str
    second_node_id: str
    curve_type: str
    length: float
    edge_tolerance: float
    representative_normal_dot: float
    representative_normals_parallel: bool
    topology_provenance: str
    geometry_provenance: str
    exchange_provenance: str


@dataclass(frozen=True)
class FaceGraphDescriptor:
    """One graph-level summary used for controlled round-trip comparison."""

    control_id: str
    stage: GraphStage
    source_file: str | None
    source_sha256: str | None
    node_count: int
    relation_count: int
    connected_component_count: int
    boundary_edge_count: int
    seam_edge_count: int
    nonmanifold_edge_count: int
    minimum_degree: int
    maximum_degree: int
    mean_degree: float
    surface_histogram: tuple[tuple[str, int], ...]
    degree_histogram: tuple[tuple[int, int], ...]
    relation_histogram: tuple[tuple[str, int], ...]
    structural_signature_sha256: str
    curved_area_ratio: float
    metrics: ShapeMetrics
    topology_provenance: str
    geometry_provenance: str
    exchange_provenance: str


@dataclass(frozen=True)
class FaceGraphComparison:
    """Constructed/imported graph agreement without persistent-ID claims."""

    control_id: str
    node_count_matches: bool
    relation_count_matches: bool
    component_count_matches: bool
    boundary_count_matches: bool
    seam_count_matches: bool
    nonmanifold_count_matches: bool
    surface_histogram_matches: bool
    degree_histogram_matches: bool
    relation_histogram_matches: bool
    structural_signature_matches: bool
    topology_counts_match: bool
    volume_absolute_difference: float
    surface_area_absolute_difference: float
    curved_area_ratio_absolute_difference: float


@dataclass(frozen=True)
class FaceGraphProbe:
    """Complete v0.51.0 face-adjacency graph evidence."""

    controls: tuple[FaceGraphControl, ...]
    fixtures: tuple[StepRoundTrip, ...]
    nodes: tuple[FaceGraphNode, ...]
    relations: tuple[FaceGraphRelation, ...]
    descriptors: tuple[FaceGraphDescriptor, ...]
    comparisons: tuple[FaceGraphComparison, ...]
    preview_shapes: tuple[tuple[str, object], ...]
    binding_distribution_version: str


def face_graph_controls() -> tuple[FaceGraphControl, ...]:
    """Return controls spanning simple, subtractive, stepped, and filleted B-Reps."""
    return (
        FaceGraphControl("plain_block", "six planar faces and regular degree four"),
        FaceGraphControl("through_hole", "planar block boundary plus one cylindrical hole wall"),
        FaceGraphControl("stepped_block", "two height levels connected by a planar riser"),
        FaceGraphControl("fillet_operation", "box edge replaced by a cylindrical blend face"),
    )


def _orientation(shape: object) -> str:
    return status_name(shape.Orientation()).removeprefix("TopAbs_").lower()


def _edge_incidence(shape: object) -> dict[int, tuple[int, int]]:
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE

    face_map = indexed_shapes(shape, TopAbs_FACE)
    edge_map = indexed_shapes(shape, TopAbs_EDGE)
    owners = {index: set() for index in range(1, edge_map.Extent() + 1)}
    uses = {index: 0 for index in range(1, edge_map.Extent() + 1)}
    for face_index in range(1, face_map.Extent() + 1):
        for edge in iter_shapes(face_map.FindKey(face_index), TopAbs_EDGE):
            edge_index = int(edge_map.FindIndex(edge))
            if edge_index:
                owners[edge_index].add(face_index)
                uses[edge_index] += 1
    return {
        index: (len(owners[index]), uses[index])
        for index in owners
    }


def _connected_components(node_ids: tuple[str, ...], relations: tuple[FaceGraphRelation, ...]) -> int:
    neighbors = {node_id: set() for node_id in node_ids}
    for relation in relations:
        neighbors[relation.first_node_id].add(relation.second_node_id)
        neighbors[relation.second_node_id].add(relation.first_node_id)
    remaining = set(node_ids)
    components = 0
    while remaining:
        components += 1
        frontier = [remaining.pop()]
        while frontier:
            current = frontier.pop()
            discovered = neighbors[current] & remaining
            remaining.difference_update(discovered)
            frontier.extend(sorted(discovered))
    return components


def _histogram(values: list[str]) -> tuple[tuple[str, int], ...]:
    return tuple((value, values.count(value)) for value in sorted(set(values)))


def _degree_histogram(values: list[int]) -> tuple[tuple[int, int], ...]:
    return tuple((value, values.count(value)) for value in sorted(set(values)))


def _structural_signature(nodes: tuple[FaceGraphNode, ...], relations: tuple[FaceGraphRelation, ...], boundary_edges: int, seam_edges: int, nonmanifold_edges: int) -> str:
    surfaces = {item.node_id: item.surface_type for item in nodes}
    payload = {
        "node_labels": sorted((item.surface_type, item.degree, item.wire_count, item.inner_wire_count, item.boundary_edge_count) for item in nodes),
        "relation_labels": sorted((min(surfaces[item.first_node_id], surfaces[item.second_node_id]), max(surfaces[item.first_node_id], surfaces[item.second_node_id]), item.curve_type) for item in relations),
        "boundary_edge_count": boundary_edges,
        "seam_edge_count": seam_edges,
        "nonmanifold_edge_count": nonmanifold_edges,
    }
    return hashlib.sha256(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")).hexdigest()


def _evaluate_graph(control_id: str, stage: GraphStage, shape: object, fixture: StepRoundTrip | None) -> tuple[tuple[FaceGraphNode, ...], tuple[FaceGraphRelation, ...], FaceGraphDescriptor]:
    from OCP.BRep import BRep_Tool
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopoDS import TopoDS

    source_file = None if fixture is None else fixture.file_name
    source_sha256 = None if fixture is None else fixture.source_sha256
    exchange_provenance = "synthetic construction in repository code" if fixture is None else "committed normalized STEP fixture SHA-256"
    topology_provenance = "OCCT unique-subshape maps and face-edge ownership"
    geometry_provenance = "OCCT B-Rep adaptors and geometric properties"
    attributes, shared = _measure_graph(control_id, stage, shape)
    face_map = indexed_shapes(shape, TopAbs_FACE)
    edge_map = indexed_shapes(shape, TopAbs_EDGE)
    nodes = tuple(
        FaceGraphNode(
            control_id,
            stage,
            source_file,
            source_sha256,
            f"f{item.face_index}",
            item.face_index,
            item.surface_type,
            _orientation(face_map.FindKey(item.face_index)),
            item.area,
            item.centroid,
            item.normal,
            item.u_span,
            item.v_span,
            item.axis_origin,
            item.axis_direction,
            item.radius,
            item.radial_polarity,
            item.maximum_absolute_curvature,
            item.wire_count,
            item.inner_wire_count,
            item.edge_count,
            float(BRep_Tool.Tolerance_s(TopoDS.Face_s(face_map.FindKey(item.face_index)))),
            item.maximum_edge_length,
            tuple(f"f{index}" for index in item.adjacent_face_indices),
            len(item.adjacent_face_indices),
            topology_provenance,
            geometry_provenance,
            exchange_provenance,
        )
        for item in attributes
    )
    relations = tuple(
        FaceGraphRelation(
            control_id,
            stage,
            source_file,
            source_sha256,
            f"e{item.edge_index}",
            item.edge_index,
            f"f{item.first_face_index}",
            f"f{item.second_face_index}",
            item.curve_type,
            item.length,
            float(BRep_Tool.Tolerance_s(TopoDS.Edge_s(edge_map.FindKey(item.edge_index)))),
            item.normal_dot,
            item.representative_normals_parallel,
            topology_provenance,
            geometry_provenance,
            exchange_provenance,
        )
        for item in shared
    )
    incidence = _edge_incidence(shape)
    boundary_edges = sum(use_count == 1 for _, use_count in incidence.values())
    seam_edges = sum(owner_count == 1 and use_count == 2 for owner_count, use_count in incidence.values())
    nonmanifold_edges = sum(owner_count > 2 or use_count > 2 for owner_count, use_count in incidence.values())
    degrees = [item.degree for item in nodes]
    surface_histogram = _histogram([item.surface_type for item in nodes])
    degree_histogram = _degree_histogram(degrees)
    node_surface = {item.node_id: item.surface_type for item in nodes}
    relation_histogram = _histogram([
        "--".join(sorted((node_surface[item.first_node_id], node_surface[item.second_node_id]))) + f"/{item.curve_type}"
        for item in relations
    ])
    metrics = measure_shape(shape)
    curved_area = sum(item.area for item in nodes if item.surface_type != "plane")
    descriptor = FaceGraphDescriptor(
        control_id,
        stage,
        source_file,
        source_sha256,
        len(nodes),
        len(relations),
        _connected_components(tuple(item.node_id for item in nodes), relations),
        boundary_edges,
        seam_edges,
        nonmanifold_edges,
        min(degrees, default=0),
        max(degrees, default=0),
        sum(degrees) / len(degrees) if degrees else 0.0,
        surface_histogram,
        degree_histogram,
        relation_histogram,
        _structural_signature(nodes, relations, boundary_edges, seam_edges, nonmanifold_edges),
        curved_area / metrics.surface_area if metrics.surface_area else 0.0,
        metrics,
        topology_provenance,
        geometry_provenance,
        exchange_provenance,
    )
    return nodes, relations, descriptor


def _topology(metrics: ShapeMetrics) -> tuple[int, int, int, int, int]:
    return (metrics.vertex_count, metrics.edge_count, metrics.face_count, metrics.shell_count, metrics.solid_count)


def probe_face_adjacency_graphs() -> FaceGraphProbe:
    """Build graph contracts before and after STEP exchange for four shapes."""
    controls = face_graph_controls()
    shapes = build_feature_shapes()
    fixtures: list[StepRoundTrip] = []
    nodes: list[FaceGraphNode] = []
    relations: list[FaceGraphRelation] = []
    descriptors: list[FaceGraphDescriptor] = []
    previews: list[tuple[str, object]] = []
    comparisons: list[FaceGraphComparison] = []
    for control in controls:
        shape = shapes[control.control_id]
        fixture = step_round_trip(shape, f"graph_{control.control_id}")
        fixtures.append(fixture)
        constructed_nodes, constructed_relations, constructed = _evaluate_graph(control.control_id, "constructed", shape, None)
        imported_nodes, imported_relations, imported = _evaluate_graph(control.control_id, "step_imported", fixture.imported_shape, fixture)
        nodes.extend((*constructed_nodes, *imported_nodes))
        relations.extend((*constructed_relations, *imported_relations))
        descriptors.extend((constructed, imported))
        comparisons.append(
            FaceGraphComparison(
                control.control_id,
                constructed.node_count == imported.node_count,
                constructed.relation_count == imported.relation_count,
                constructed.connected_component_count == imported.connected_component_count,
                constructed.boundary_edge_count == imported.boundary_edge_count,
                constructed.seam_edge_count == imported.seam_edge_count,
                constructed.nonmanifold_edge_count == imported.nonmanifold_edge_count,
                constructed.surface_histogram == imported.surface_histogram,
                constructed.degree_histogram == imported.degree_histogram,
                constructed.relation_histogram == imported.relation_histogram,
                constructed.structural_signature_sha256 == imported.structural_signature_sha256,
                _topology(constructed.metrics) == _topology(imported.metrics),
                abs(constructed.metrics.absolute_volume - imported.metrics.absolute_volume),
                abs(constructed.metrics.surface_area - imported.metrics.surface_area),
                abs(constructed.curved_area_ratio - imported.curved_area_ratio),
            )
        )
        previews.append((control.control_id, fixture.imported_shape))
    return FaceGraphProbe(controls, tuple(fixtures), tuple(nodes), tuple(relations), tuple(descriptors), tuple(comparisons), tuple(previews), importlib.metadata.version("cadquery-ocp"))
