"""Represent explicit parametric construction and imported candidates as DAGs."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
from dataclasses import dataclass
from pathlib import Path

from research_notes.brep_runtime import StepRoundTrip, step_round_trip
from research_notes.feature_recognition import _cut, _polygon_face, _vertical_cylinder
from research_notes.modeling_common import ShapeMetrics, measure_shape


CONTRACT_VERSION = "1.0.0"


@dataclass(frozen=True)
class FeatureGraphNode:
    """One stable application-level node in a parametric feature graph."""

    graph_id: str
    node_id: str
    node_type: str
    name: str
    attributes: tuple[tuple[str, object], ...]
    provenance: str


@dataclass(frozen=True)
class FeatureGraphEdge:
    """One typed dependency from a dependent node to its prerequisite."""

    graph_id: str
    edge_id: str
    dependent_node_id: str
    dependency_node_id: str
    relation_type: str


@dataclass(frozen=True)
class FeatureGraph:
    """One revisioned acyclic model or reconstruction-candidate graph."""

    graph_id: str
    graph_revision: int
    graph_kind: str
    nodes: tuple[FeatureGraphNode, ...]
    edges: tuple[FeatureGraphEdge, ...]
    fingerprint_sha256: str


@dataclass(frozen=True)
class FeatureGraphEvaluation:
    """Generated B-Rep truth and STEP round-trip observations for one graph."""

    graph_id: str
    result_node_id: str
    expected_volume: float
    expected_surface_area: float
    constructed_metrics: ShapeMetrics
    imported_metrics: ShapeMetrics
    volume_truth_absolute_error: float
    area_truth_absolute_error: float
    imported_volume_absolute_difference: float
    imported_area_absolute_difference: float
    topology_counts_match: bool
    analyzer_valid_both: bool
    source_file: str
    source_sha256: str


@dataclass(frozen=True)
class FeatureGraphValidation:
    """One structural validation outcome for a graph revision."""

    graph_id: str
    check_id: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class ParametricFeatureGraphProbe:
    """Complete v0.55.0 graph, geometry, candidate, and validation evidence."""

    graphs: tuple[FeatureGraph, ...]
    evaluations: tuple[FeatureGraphEvaluation, ...]
    validations: tuple[FeatureGraphValidation, ...]
    fixtures: tuple[StepRoundTrip, ...]
    preview_shapes: tuple[tuple[str, object], ...]
    import_reference_file: str
    import_reference_sha256: str
    binding_distribution_version: str


def _node(graph_id: str, node_id: str, node_type: str, name: str, provenance: str, **attributes: object) -> FeatureGraphNode:
    return FeatureGraphNode(graph_id, node_id, node_type, name, tuple(sorted(attributes.items())), provenance)


def _edge(graph_id: str, index: int, dependent: str, dependency: str, relation: str) -> FeatureGraphEdge:
    return FeatureGraphEdge(graph_id, f"e{index}", dependent, dependency, relation)


def _fingerprint(graph_id: str, revision: int, kind: str, nodes: tuple[FeatureGraphNode, ...], edges: tuple[FeatureGraphEdge, ...]) -> str:
    payload = {
        "graph_id": graph_id,
        "graph_revision": revision,
        "graph_kind": kind,
        "nodes": [
            {
                "node_id": item.node_id,
                "node_type": item.node_type,
                "name": item.name,
                "attributes": item.attributes,
                "provenance": item.provenance,
            }
            for item in nodes
        ],
        "edges": [item.__dict__ for item in edges],
    }
    return hashlib.sha256(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")).hexdigest()


def _graph(graph_id: str, kind: str, nodes: tuple[FeatureGraphNode, ...], edges: tuple[FeatureGraphEdge, ...]) -> FeatureGraph:
    return FeatureGraph(graph_id, 1, kind, nodes, edges, _fingerprint(graph_id, 1, kind, nodes, edges))


def _explicit_plate_graph() -> FeatureGraph:
    graph_id = "explicit_plate"
    provenance = "explicit repository parametric construction"
    nodes = (
        _node(graph_id, "datum_xy", "datum_plane", "XY datum", provenance, origin="0|0|0", normal="0|0|1"),
        _node(graph_id, "width", "parameter", "Plate width", provenance, value=12.0, unit="mm"),
        _node(graph_id, "height", "parameter", "Plate height", provenance, value=8.0, unit="mm"),
        _node(graph_id, "thickness", "parameter", "Plate thickness", provenance, value=2.0, unit="mm"),
        _node(graph_id, "profile", "sketch", "Rectangle profile", provenance, primitive="rectangle", closed=True),
        _node(graph_id, "extrude", "feature", "Pad", provenance, operation="extrusion", direction="0|0|1"),
        _node(graph_id, "result", "result", "Plate B-Rep", provenance, representation="TopoDS_Shape"),
    )
    edges = (
        _edge(graph_id, 1, "profile", "datum_xy", "located_on"),
        _edge(graph_id, 2, "profile", "width", "uses_parameter"),
        _edge(graph_id, 3, "profile", "height", "uses_parameter"),
        _edge(graph_id, 4, "extrude", "profile", "uses_profile"),
        _edge(graph_id, 5, "extrude", "thickness", "uses_parameter"),
        _edge(graph_id, 6, "result", "extrude", "generated_by"),
    )
    return _graph(graph_id, "explicit_construction", nodes, edges)


def _explicit_plate_with_hole_graph() -> FeatureGraph:
    graph_id = "explicit_plate_with_hole"
    provenance = "explicit repository parametric construction"
    base = (
        _node(graph_id, "datum_xy", "datum_plane", "XY datum", provenance, origin="0|0|0", normal="0|0|1"),
        _node(graph_id, "width", "parameter", "Plate width", provenance, value=12.0, unit="mm"),
        _node(graph_id, "height", "parameter", "Plate height", provenance, value=8.0, unit="mm"),
        _node(graph_id, "thickness", "parameter", "Plate thickness", provenance, value=2.0, unit="mm"),
        _node(graph_id, "hole_x", "parameter", "Hole X", provenance, value=4.0, unit="mm"),
        _node(graph_id, "hole_y", "parameter", "Hole Y", provenance, value=4.0, unit="mm"),
        _node(graph_id, "hole_radius", "parameter", "Hole radius", provenance, value=1.0, unit="mm"),
        _node(graph_id, "profile", "sketch", "Rectangle profile", provenance, primitive="rectangle", closed=True),
        _node(graph_id, "extrude", "feature", "Pad", provenance, operation="extrusion", direction="0|0|1"),
        _node(graph_id, "hole", "feature", "Through hole", provenance, operation="subtractive_cylinder", extent="through_all"),
        _node(graph_id, "result", "result", "Holed plate B-Rep", provenance, representation="TopoDS_Shape"),
    )
    edges = (
        _edge(graph_id, 1, "profile", "datum_xy", "located_on"),
        _edge(graph_id, 2, "profile", "width", "uses_parameter"),
        _edge(graph_id, 3, "profile", "height", "uses_parameter"),
        _edge(graph_id, 4, "extrude", "profile", "uses_profile"),
        _edge(graph_id, 5, "extrude", "thickness", "uses_parameter"),
        _edge(graph_id, 6, "hole", "extrude", "modifies_result_of"),
        _edge(graph_id, 7, "hole", "hole_x", "uses_parameter"),
        _edge(graph_id, 8, "hole", "hole_y", "uses_parameter"),
        _edge(graph_id, 9, "hole", "hole_radius", "uses_parameter"),
        _edge(graph_id, 10, "result", "hole", "generated_by"),
    )
    return _graph(graph_id, "explicit_construction", base, edges)


def _explicit_step_graph() -> FeatureGraph:
    graph_id = "explicit_stepped_prism"
    provenance = "explicit repository parametric construction"
    nodes = (
        _node(graph_id, "datum_xz", "datum_plane", "XZ datum", provenance, origin="0|0|0", normal="0|1|0"),
        _node(graph_id, "length", "parameter", "Overall length", provenance, value=12.0, unit="mm"),
        _node(graph_id, "lower_height", "parameter", "Lower height", provenance, value=3.0, unit="mm"),
        _node(graph_id, "step_height", "parameter", "Step height", provenance, value=2.0, unit="mm"),
        _node(graph_id, "step_position", "parameter", "Step position", provenance, value=5.0, unit="mm"),
        _node(graph_id, "depth", "parameter", "Prism depth", provenance, value=8.0, unit="mm"),
        _node(graph_id, "profile", "sketch", "Stepped profile", provenance, primitive="closed_polyline", closed=True),
        _node(graph_id, "extrude", "feature", "Stepped extrusion", provenance, operation="extrusion", direction="0|1|0"),
        _node(graph_id, "result", "result", "Stepped B-Rep", provenance, representation="TopoDS_Shape"),
    )
    edges = (
        _edge(graph_id, 1, "profile", "datum_xz", "located_on"),
        _edge(graph_id, 2, "profile", "length", "uses_parameter"),
        _edge(graph_id, 3, "profile", "lower_height", "uses_parameter"),
        _edge(graph_id, 4, "profile", "step_height", "uses_parameter"),
        _edge(graph_id, 5, "profile", "step_position", "uses_parameter"),
        _edge(graph_id, 6, "extrude", "profile", "uses_profile"),
        _edge(graph_id, 7, "extrude", "depth", "uses_parameter"),
        _edge(graph_id, 8, "result", "extrude", "generated_by"),
    )
    return _graph(graph_id, "explicit_construction", nodes, edges)


def _import_candidate_graph(file_name: str, digest: str) -> FeatureGraph:
    graph_id = "imported_hole_candidate"
    source = "committed STEP input reference"
    inference = "bounded geometric inference; user confirmation required"
    nodes = (
        _node(graph_id, "input", "import_reference", "Imported STEP", source, file_name=file_name, sha256=digest, access="read_only"),
        _node(graph_id, "face_graph", "observation", "Attributed face graph", inference, representation="v0.51.0-compatible descriptors"),
        _node(graph_id, "hole_candidate", "reconstruction_candidate", "Through-hole candidate", inference, candidate_type="hole:through", status="unconfirmed"),
    )
    edges = (
        _edge(graph_id, 1, "face_graph", "input", "measured_from"),
        _edge(graph_id, 2, "hole_candidate", "face_graph", "supported_by"),
    )
    return _graph(graph_id, "import_reconstruction_candidate", nodes, edges)


def _build_plate() -> object:
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.gp import gp_Vec

    profile = _polygon_face(((0.0, 0.0, 0.0), (12.0, 0.0, 0.0), (12.0, 8.0, 0.0), (0.0, 8.0, 0.0)))
    return BRepPrimAPI_MakePrism(profile, gp_Vec(0.0, 0.0, 2.0)).Shape()


def _build_stepped_prism() -> object:
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.gp import gp_Vec

    profile = _polygon_face(((0.0, 0.0, 0.0), (12.0, 0.0, 0.0), (12.0, 0.0, 3.0), (5.0, 0.0, 3.0), (5.0, 0.0, 5.0), (0.0, 0.0, 5.0)))
    return BRepPrimAPI_MakePrism(profile, gp_Vec(0.0, 8.0, 0.0)).Shape()


def _topology(metrics: ShapeMetrics) -> tuple[int, int, int, int, int]:
    return (metrics.vertex_count, metrics.edge_count, metrics.face_count, metrics.shell_count, metrics.solid_count)


def _validations(graph: FeatureGraph) -> tuple[FeatureGraphValidation, ...]:
    node_ids = [item.node_id for item in graph.nodes]
    unique = len(node_ids) == len(set(node_ids))
    references = all(item.dependent_node_id in node_ids and item.dependency_node_id in node_ids for item in graph.edges)
    adjacency = {node_id: [] for node_id in node_ids}
    for edge in graph.edges:
        adjacency[edge.dependent_node_id].append(edge.dependency_node_id)
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> bool:
        if node_id in visiting:
            return False
        if node_id in visited:
            return True
        visiting.add(node_id)
        if not all(visit(item) for item in adjacency[node_id]):
            return False
        visiting.remove(node_id)
        visited.add(node_id)
        return True

    acyclic = all(visit(node_id) for node_id in node_ids)
    import_nodes = [item for item in graph.nodes if item.node_type == "import_reference"]
    candidates = [item for item in graph.nodes if item.node_type == "reconstruction_candidate"]
    candidate_boundary = all(dict(item.attributes).get("status") == "unconfirmed" for item in candidates)
    if graph.graph_kind == "import_reconstruction_candidate":
        candidate_boundary = candidate_boundary and bool(import_nodes) and not any(item.node_type == "result" for item in graph.nodes)
    return (
        FeatureGraphValidation(graph.graph_id, "unique_node_ids", unique, "node IDs are unique inside one graph revision"),
        FeatureGraphValidation(graph.graph_id, "resolved_edge_endpoints", references, "every dependency endpoint resolves locally"),
        FeatureGraphValidation(graph.graph_id, "acyclic_dependencies", acyclic, "dependency edges form a directed acyclic graph"),
        FeatureGraphValidation(graph.graph_id, "import_candidate_boundary", candidate_boundary, "imported candidates remain unconfirmed and do not become generated results"),
    )


def probe_parametric_feature_graphs(import_reference: Path) -> ParametricFeatureGraphProbe:
    """Build three explicit models and one isolated imported candidate graph."""
    import_payload = import_reference.read_bytes()
    import_digest = hashlib.sha256(import_payload).hexdigest()
    graphs = (
        _explicit_plate_graph(),
        _explicit_plate_with_hole_graph(),
        _explicit_step_graph(),
        _import_candidate_graph(import_reference.name, import_digest),
    )
    plate = _build_plate()
    holed = _cut(plate, _vertical_cylinder(4.0, 4.0, -1.0, 1.0, 4.0))
    stepped = _build_stepped_prism()
    shapes = (
        ("explicit_plate", plate, 192.0, 272.0),
        ("explicit_plate_with_hole", holed, 192.0 - 2.0 * math.pi, 272.0 + 2.0 * math.pi),
        ("explicit_stepped_prism", stepped, 368.0, 364.0),
    )
    fixtures: list[StepRoundTrip] = []
    evaluations: list[FeatureGraphEvaluation] = []
    previews: list[tuple[str, object]] = []
    for graph_id, shape, expected_volume, expected_area in shapes:
        fixture = step_round_trip(shape, f"parametric_{graph_id}")
        fixtures.append(fixture)
        constructed = measure_shape(shape)
        imported = measure_shape(fixture.imported_shape)
        evaluations.append(
            FeatureGraphEvaluation(
                graph_id,
                "result",
                expected_volume,
                expected_area,
                constructed,
                imported,
                abs(constructed.absolute_volume - expected_volume),
                abs(constructed.surface_area - expected_area),
                abs(constructed.absolute_volume - imported.absolute_volume),
                abs(constructed.surface_area - imported.surface_area),
                _topology(constructed) == _topology(imported),
                constructed.analyzer_valid and imported.analyzer_valid,
                fixture.file_name,
                fixture.source_sha256,
            )
        )
        previews.append((graph_id, fixture.imported_shape))
    validations = tuple(item for graph in graphs for item in _validations(graph))
    return ParametricFeatureGraphProbe(
        graphs,
        tuple(evaluations),
        validations,
        tuple(fixtures),
        tuple(previews),
        import_reference.name,
        import_digest,
        importlib.metadata.version("cadquery-ocp"),
    )
