"""Generate v0.51.0 face-adjacency graph and descriptor evidence."""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

from research_notes.brep_preview import write_shape_previews  # noqa: E402
from research_notes.face_adjacency_graph import (  # noqa: E402
    CONTRACT_VERSION,
    FaceGraphProbe,
    probe_face_adjacency_graphs,
)


NODE_NAME = "face_graph_nodes.csv"
RELATION_NAME = "face_graph_relations.csv"
DESCRIPTOR_NAME = "face_graph_descriptors.csv"
COMPARISON_NAME = "face_graph_round_trip_comparisons.csv"
SUMMARY_NAME = "face_graph_summary.csv"
GRAPH_NAME = "face_adjacency_graphs.json"
CONTRACT_NAME = "face_graph_contract.json"
FIGURE_NAME = "face_adjacency_graph.png"
SHAPES_NAME = "face_adjacency_graph_shapes.png"
MANIFEST_NAME = "manifest.csv"


def _float(value: float) -> str:
    return format(value, ".17g")


def _vector(value: tuple[float, float, float] | None) -> str:
    return "" if value is None else "|".join(_float(item) for item in value)


def _pairs(values: tuple[tuple[object, int], ...]) -> str:
    return "|".join(f"{name}:{count}" for name, count in values)


def _csv_bytes(rows: list[dict[str, object]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=tuple(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_csv_bytes(rows))


def node_rows(probe: FaceGraphProbe) -> list[dict[str, object]]:
    return [
        {
            "contract_version": CONTRACT_VERSION,
            "control_id": item.control_id,
            "stage": item.stage,
            "source_file": item.source_file or "",
            "source_sha256": item.source_sha256 or "",
            "node_id": item.node_id,
            "analysis_face_index": item.analysis_face_index,
            "surface_type": item.surface_type,
            "orientation": item.orientation,
            "area": _float(item.area),
            "centroid": _vector(item.centroid),
            "representative_normal": _vector(item.representative_normal),
            "u_span": _float(item.u_span),
            "v_span": _float(item.v_span),
            "axis_origin": _vector(item.axis_origin),
            "axis_direction": _vector(item.axis_direction),
            "radius": "" if item.radius is None else _float(item.radius),
            "radial_polarity": "" if item.radial_polarity is None else _float(item.radial_polarity),
            "maximum_absolute_curvature": "" if item.maximum_absolute_curvature is None else _float(item.maximum_absolute_curvature),
            "wire_count": item.wire_count,
            "inner_wire_count": item.inner_wire_count,
            "boundary_edge_count": item.boundary_edge_count,
            "face_tolerance": _float(item.face_tolerance),
            "maximum_edge_length": _float(item.maximum_edge_length),
            "adjacent_node_ids": "|".join(item.adjacent_node_ids),
            "degree": item.degree,
            "topology_provenance": item.topology_provenance,
            "geometry_provenance": item.geometry_provenance,
            "exchange_provenance": item.exchange_provenance,
        }
        for item in probe.nodes
    ]


def relation_rows(probe: FaceGraphProbe) -> list[dict[str, object]]:
    return [
        {
            "contract_version": CONTRACT_VERSION,
            "control_id": item.control_id,
            "stage": item.stage,
            "source_file": item.source_file or "",
            "source_sha256": item.source_sha256 or "",
            "relation_id": item.relation_id,
            "analysis_edge_index": item.analysis_edge_index,
            "first_node_id": item.first_node_id,
            "second_node_id": item.second_node_id,
            "curve_type": item.curve_type,
            "length": _float(item.length),
            "edge_tolerance": _float(item.edge_tolerance),
            "representative_normal_dot": _float(item.representative_normal_dot),
            "representative_normals_parallel": int(item.representative_normals_parallel),
            "topology_provenance": item.topology_provenance,
            "geometry_provenance": item.geometry_provenance,
            "exchange_provenance": item.exchange_provenance,
        }
        for item in probe.relations
    ]


def descriptor_rows(probe: FaceGraphProbe) -> list[dict[str, object]]:
    return [
        {
            "contract_version": CONTRACT_VERSION,
            "control_id": item.control_id,
            "stage": item.stage,
            "source_file": item.source_file or "",
            "source_sha256": item.source_sha256 or "",
            "node_count": item.node_count,
            "relation_count": item.relation_count,
            "connected_component_count": item.connected_component_count,
            "boundary_edge_count": item.boundary_edge_count,
            "seam_edge_count": item.seam_edge_count,
            "nonmanifold_edge_count": item.nonmanifold_edge_count,
            "minimum_degree": item.minimum_degree,
            "maximum_degree": item.maximum_degree,
            "mean_degree": _float(item.mean_degree),
            "surface_histogram": _pairs(item.surface_histogram),
            "degree_histogram": _pairs(item.degree_histogram),
            "relation_histogram": _pairs(item.relation_histogram),
            "structural_signature_sha256": item.structural_signature_sha256,
            "curved_area_ratio": _float(item.curved_area_ratio),
            "vertex_count": item.metrics.vertex_count,
            "edge_count": item.metrics.edge_count,
            "face_count": item.metrics.face_count,
            "shell_count": item.metrics.shell_count,
            "solid_count": item.metrics.solid_count,
            "absolute_volume": _float(item.metrics.absolute_volume),
            "surface_area": _float(item.metrics.surface_area),
            "analyzer_valid": int(item.metrics.analyzer_valid),
            "topology_provenance": item.topology_provenance,
            "geometry_provenance": item.geometry_provenance,
            "exchange_provenance": item.exchange_provenance,
        }
        for item in probe.descriptors
    ]


def comparison_rows(probe: FaceGraphProbe) -> list[dict[str, object]]:
    return [
        {
            "contract_version": CONTRACT_VERSION,
            "control_id": item.control_id,
            "node_count_matches": int(item.node_count_matches),
            "relation_count_matches": int(item.relation_count_matches),
            "component_count_matches": int(item.component_count_matches),
            "boundary_count_matches": int(item.boundary_count_matches),
            "seam_count_matches": int(item.seam_count_matches),
            "nonmanifold_count_matches": int(item.nonmanifold_count_matches),
            "surface_histogram_matches": int(item.surface_histogram_matches),
            "degree_histogram_matches": int(item.degree_histogram_matches),
            "relation_histogram_matches": int(item.relation_histogram_matches),
            "structural_signature_matches": int(item.structural_signature_matches),
            "topology_counts_match": int(item.topology_counts_match),
            "volume_absolute_difference": _float(item.volume_absolute_difference),
            "surface_area_absolute_difference": _float(item.surface_area_absolute_difference),
            "curved_area_ratio_absolute_difference": _float(item.curved_area_ratio_absolute_difference),
        }
        for item in probe.comparisons
    ]


def summary_rows(probe: FaceGraphProbe) -> list[dict[str, object]]:
    constructed = [item for item in probe.descriptors if item.stage == "constructed"]
    return [
        {"scope": "corpus", "metric": "controls", "value": len(probe.controls)},
        {"scope": "corpus", "metric": "step_files", "value": len(probe.fixtures)},
        {"scope": "constructed", "metric": "nodes", "value": sum(item.node_count for item in constructed)},
        {"scope": "constructed", "metric": "relations", "value": sum(item.relation_count for item in constructed)},
        {"scope": "round_trip", "metric": "structural_signature_matches", "value": sum(item.structural_signature_matches for item in probe.comparisons)},
        {"scope": "round_trip", "metric": "topology_count_matches", "value": sum(item.topology_counts_match for item in probe.comparisons)},
        {"scope": "round_trip", "metric": "surface_histogram_matches", "value": sum(item.surface_histogram_matches for item in probe.comparisons)},
        {"scope": "round_trip", "metric": "degree_histogram_matches", "value": sum(item.degree_histogram_matches for item in probe.comparisons)},
        {"scope": "constructed", "metric": "seam_edges", "value": sum(item.seam_edge_count for item in constructed)},
        {"scope": "constructed", "metric": "boundary_edges", "value": sum(item.boundary_edge_count for item in constructed)},
        {"scope": "constructed", "metric": "nonmanifold_edges", "value": sum(item.nonmanifold_edge_count for item in constructed)},
    ]


def _manifest_bytes(probe: FaceGraphProbe) -> bytes:
    return _csv_bytes([
        {
            "control_id": item.fixture_id.removeprefix("graph_"),
            "file_name": item.file_name,
            "source_bytes": len(item.source_bytes),
            "source_sha256": item.source_sha256,
            "generator": "experiments/run_face_adjacency_graphs.py",
            "binding_distribution_version": probe.binding_distribution_version,
        }
        for item in probe.fixtures
    ])


def handle_fixtures(path: Path, probe: FaceGraphProbe, *, refresh: bool) -> None:
    """Write or byte-verify normalized STEP graph fixtures."""
    expected = {item.file_name: item.source_bytes for item in probe.fixtures}
    expected[MANIFEST_NAME] = _manifest_bytes(probe)
    path.mkdir(parents=True, exist_ok=True)
    if refresh:
        for name, payload in expected.items():
            (path / name).write_bytes(payload)
        return
    unexpected = sorted(item.name for item in path.iterdir() if item.name not in expected)
    if unexpected:
        raise RuntimeError("unexpected fixture files: " + ", ".join(unexpected))
    for name, payload in expected.items():
        target = path / name
        if not target.exists() or target.read_bytes() != payload:
            raise RuntimeError(f"fixture differs; rerun with --refresh-fixtures: {target}")


def write_graph_json(path: Path, probe: FaceGraphProbe) -> None:
    graphs = []
    for descriptor in probe.descriptors:
        nodes = [item for item in probe.nodes if item.control_id == descriptor.control_id and item.stage == descriptor.stage]
        relations = [item for item in probe.relations if item.control_id == descriptor.control_id and item.stage == descriptor.stage]
        graphs.append({
            "control_id": descriptor.control_id,
            "stage": descriptor.stage,
            "source_file": descriptor.source_file,
            "source_sha256": descriptor.source_sha256,
            "directed": False,
            "multigraph": False,
            "nodes": [{"id": item.node_id, "surface_type": item.surface_type, "degree": item.degree, "area": item.area} for item in nodes],
            "relations": [{"id": item.relation_id, "source": item.first_node_id, "target": item.second_node_id, "curve_type": item.curve_type, "length": item.length} for item in relations],
            "structural_signature_sha256": descriptor.structural_signature_sha256,
        })
    path.write_text(json.dumps({"contract_version": CONTRACT_VERSION, "graphs": graphs}, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_contract(path: Path, probe: FaceGraphProbe) -> None:
    node_fields = tuple(node_rows(probe)[0])
    relation_fields = tuple(relation_rows(probe)[0])
    descriptor_fields = tuple(descriptor_rows(probe)[0])
    payload = {
        "contract_version": CONTRACT_VERSION,
        "study_version": "v0.51.0",
        "title": "Face-Adjacency Graphs and Geometric Descriptors",
        "node_primary_key": ["control_id", "stage", "node_id"],
        "relation_primary_key": ["control_id", "stage", "relation_id"],
        "graph_local_identity": "node and relation identifiers are local to one control and analysis stage",
        "field_provenance": {
            "node": {field: ("exchange" if field in {"source_file", "source_sha256", "exchange_provenance"} else "topology" if field in {"node_id", "analysis_face_index", "wire_count", "inner_wire_count", "boundary_edge_count", "adjacent_node_ids", "degree", "topology_provenance"} else "geometry" if field not in {"contract_version", "control_id", "stage"} else "contract") for field in node_fields},
            "relation": {field: ("exchange" if field in {"source_file", "source_sha256", "exchange_provenance"} else "topology" if field in {"relation_id", "analysis_edge_index", "first_node_id", "second_node_id", "topology_provenance"} else "geometry" if field not in {"contract_version", "control_id", "stage"} else "contract") for field in relation_fields},
            "descriptor": {field: ("exchange" if field in {"source_file", "source_sha256", "exchange_provenance"} else "topology" if field in {"node_count", "relation_count", "connected_component_count", "boundary_edge_count", "seam_edge_count", "nonmanifold_edge_count", "minimum_degree", "maximum_degree", "mean_degree", "surface_histogram", "degree_histogram", "relation_histogram", "structural_signature_sha256", "vertex_count", "edge_count", "face_count", "shell_count", "solid_count", "topology_provenance"} else "geometry" if field not in {"contract_version", "control_id", "stage"} else "contract") for field in descriptor_fields},
        },
        "fixtures": {item.file_name: item.source_sha256 for item in probe.fixtures},
        "claim_boundaries": [
            "local face and edge indices are not persistent CAD identifiers",
            "the structural signature is a coarse labeled multiset and not a complete graph-isomorphism proof",
            "representative normals and curvatures are samples rather than whole-face bounds",
            "shared-edge relations omit seam self-incidence and record seam counts separately",
            "descriptor agreement does not recover feature history, design intent, or manufacturing semantics",
            "four synthetic controls do not establish arbitrary B-Rep or imported-model coverage",
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_graph_figure(path: Path, probe: FaceGraphProbe) -> None:
    colors = {"plane": "#5b9bd5", "cylinder": "#ed7d31", "cone": "#a5a5a5", "sphere": "#ffc000", "torus": "#70ad47", "bspline": "#7030a0"}
    figure, axes = plt.subplots(2, 2, figsize=(10, 9))
    for axis, control in zip(axes.flat, probe.controls, strict=True):
        nodes = [item for item in probe.nodes if item.control_id == control.control_id and item.stage == "constructed"]
        relations = [item for item in probe.relations if item.control_id == control.control_id and item.stage == "constructed"]
        positions = {item.node_id: (math.cos(2.0 * math.pi * index / len(nodes)), math.sin(2.0 * math.pi * index / len(nodes))) for index, item in enumerate(nodes)}
        for relation in relations:
            x1, y1 = positions[relation.first_node_id]
            x2, y2 = positions[relation.second_node_id]
            axis.plot((x1, x2), (y1, y2), color="#9ca3af", linewidth=1.2, zorder=1)
        for node in nodes:
            x, y = positions[node.node_id]
            axis.scatter((x,), (y,), s=360, color=colors.get(node.surface_type, "#7f8c8d"), edgecolor="#111827", zorder=2)
            axis.text(x, y, node.node_id.upper(), ha="center", va="center", fontsize=8, color="white", weight="bold", zorder=3)
        descriptor = next(item for item in probe.descriptors if item.control_id == control.control_id and item.stage == "constructed")
        axis.set_title(f"{control.control_id}\n{descriptor.node_count} faces, {descriptor.relation_count} shared-edge relations")
        axis.set_aspect("equal")
        axis.set_xlim(-1.25, 1.25)
        axis.set_ylim(-1.25, 1.25)
        axis.axis("off")
    figure.suptitle("Constructed face-adjacency graphs\nBlue: plane, orange: cylinder")
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160, metadata={"Software": "research-notes"})
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic face-adjacency graph evaluation.")
    parser.add_argument("--fixture-dir", type=Path, default=Path("fixtures/face-adjacency-graphs"))
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument("--refresh-fixtures", action="store_true")
    args = parser.parse_args()
    probe = probe_face_adjacency_graphs()
    handle_fixtures(args.fixture_dir, probe, refresh=args.refresh_fixtures)
    _write_csv(args.output_dir / NODE_NAME, node_rows(probe))
    _write_csv(args.output_dir / RELATION_NAME, relation_rows(probe))
    _write_csv(args.output_dir / DESCRIPTOR_NAME, descriptor_rows(probe))
    _write_csv(args.output_dir / COMPARISON_NAME, comparison_rows(probe))
    _write_csv(args.output_dir / SUMMARY_NAME, summary_rows(probe))
    write_graph_json(args.output_dir / GRAPH_NAME, probe)
    write_contract(args.output_dir / CONTRACT_NAME, probe)
    write_graph_figure(args.output_dir / FIGURE_NAME, probe)
    write_shape_previews(args.output_dir / SHAPES_NAME, probe.preview_shapes, title="Face-adjacency graph shape controls", columns=2)
    print(f"Wrote deterministic face-adjacency graph evidence to {args.output_dir}")


if __name__ == "__main__":
    main()
