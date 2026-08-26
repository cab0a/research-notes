"""Generate v0.55.0 parametric feature graph evidence."""

from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

from research_notes.brep_preview import write_shape_previews  # noqa: E402
from research_notes.parametric_feature_graph import (  # noqa: E402
    CONTRACT_VERSION,
    ParametricFeatureGraphProbe,
    probe_parametric_feature_graphs,
)


NODES_NAME = "parametric_feature_nodes.csv"
EDGES_NAME = "parametric_feature_edges.csv"
EVALUATIONS_NAME = "parametric_feature_evaluations.csv"
VALIDATIONS_NAME = "parametric_feature_validations.csv"
GRAPHS_NAME = "parametric_feature_graphs.json"
CONTRACT_NAME = "parametric_feature_graph_contract.json"
FIGURE_NAME = "parametric_feature_graph.png"
SHAPES_NAME = "parametric_feature_graph_shapes.png"
MANIFEST_NAME = "manifest.csv"


def _csv_bytes(rows: list[dict[str, object]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=tuple(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_csv_bytes(rows))


def node_rows(probe: ParametricFeatureGraphProbe) -> list[dict[str, object]]:
    return [
        {
            "contract_version": CONTRACT_VERSION,
            "graph_id": graph.graph_id,
            "graph_revision": graph.graph_revision,
            "graph_kind": graph.graph_kind,
            "graph_fingerprint_sha256": graph.fingerprint_sha256,
            "node_id": item.node_id,
            "node_type": item.node_type,
            "name": item.name,
            "attributes_json": json.dumps(dict(item.attributes), separators=(",", ":"), sort_keys=True),
            "provenance": item.provenance,
        }
        for graph in probe.graphs
        for item in graph.nodes
    ]


def edge_rows(probe: ParametricFeatureGraphProbe) -> list[dict[str, object]]:
    return [
        {
            "contract_version": CONTRACT_VERSION,
            "graph_id": item.graph_id,
            "edge_id": item.edge_id,
            "dependent_node_id": item.dependent_node_id,
            "dependency_node_id": item.dependency_node_id,
            "relation_type": item.relation_type,
        }
        for graph in probe.graphs
        for item in graph.edges
    ]


def evaluation_rows(probe: ParametricFeatureGraphProbe) -> list[dict[str, object]]:
    return [
        {
            "contract_version": CONTRACT_VERSION,
            "graph_id": item.graph_id,
            "result_node_id": item.result_node_id,
            "expected_volume": format(item.expected_volume, ".17g"),
            "expected_surface_area": format(item.expected_surface_area, ".17g"),
            "constructed_volume": format(item.constructed_metrics.absolute_volume, ".17g"),
            "constructed_surface_area": format(item.constructed_metrics.surface_area, ".17g"),
            "imported_volume": format(item.imported_metrics.absolute_volume, ".17g"),
            "imported_surface_area": format(item.imported_metrics.surface_area, ".17g"),
            "volume_truth_absolute_error": format(item.volume_truth_absolute_error, ".17g"),
            "area_truth_absolute_error": format(item.area_truth_absolute_error, ".17g"),
            "imported_volume_absolute_difference": format(item.imported_volume_absolute_difference, ".17g"),
            "imported_area_absolute_difference": format(item.imported_area_absolute_difference, ".17g"),
            "topology_counts_match": int(item.topology_counts_match),
            "analyzer_valid_both": int(item.analyzer_valid_both),
            "source_file": item.source_file,
            "source_sha256": item.source_sha256,
        }
        for item in probe.evaluations
    ]


def validation_rows(probe: ParametricFeatureGraphProbe) -> list[dict[str, object]]:
    return [
        {
            "graph_id": item.graph_id,
            "check_id": item.check_id,
            "passed": int(item.passed),
            "detail": item.detail,
        }
        for item in probe.validations
    ]


def _manifest_bytes(probe: ParametricFeatureGraphProbe) -> bytes:
    return _csv_bytes(
        [
            {
                "graph_id": item.graph_id,
                "file_name": item.source_file,
                "source_sha256": item.source_sha256,
                "generator": "experiments/run_parametric_feature_graphs.py",
                "binding_distribution_version": probe.binding_distribution_version,
            }
            for item in probe.evaluations
        ]
    )


def handle_fixtures(path: Path, probe: ParametricFeatureGraphProbe, *, refresh: bool) -> None:
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


def write_graphs(path: Path, probe: ParametricFeatureGraphProbe) -> None:
    payload = {
        "contract_version": CONTRACT_VERSION,
        "graphs": [
            {
                "graph_id": graph.graph_id,
                "graph_revision": graph.graph_revision,
                "graph_kind": graph.graph_kind,
                "fingerprint_sha256": graph.fingerprint_sha256,
                "nodes": [
                    {
                        "node_id": item.node_id,
                        "node_type": item.node_type,
                        "name": item.name,
                        "attributes": dict(item.attributes),
                        "provenance": item.provenance,
                    }
                    for item in graph.nodes
                ],
                "edges": [
                    {
                        "edge_id": item.edge_id,
                        "dependent_node_id": item.dependent_node_id,
                        "dependency_node_id": item.dependency_node_id,
                        "relation_type": item.relation_type,
                    }
                    for item in graph.edges
                ],
            }
            for graph in probe.graphs
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_contract(path: Path, probe: ParametricFeatureGraphProbe) -> None:
    payload = {
        "contract_version": CONTRACT_VERSION,
        "study_version": "v0.55.0",
        "title": "Parametric Feature Graph",
        "node_primary_key": ["graph_id", "graph_revision", "node_id"],
        "edge_primary_key": ["graph_id", "edge_id"],
        "dependency_direction": "dependent_node_id references dependency_node_id",
        "graph_types": ["explicit_construction", "import_reconstruction_candidate"],
        "import_reference": {"file_name": probe.import_reference_file, "source_sha256": probe.import_reference_sha256},
        "fixtures": {item.file_name: item.source_sha256 for item in probe.fixtures},
        "all_validations_pass": all(item.passed for item in probe.validations),
        "claim_boundaries": [
            "explicit construction graphs are authored in repository code and are not inferred from STEP",
            "the imported STEP graph contains an unconfirmed candidate and no generated result node",
            "graph node IDs are application identifiers and not persistent B-Rep subshape names",
            "the graph records initial parameters but does not yet provide a constraint solver or general recompute engine",
            "STEP round-trip agreement does not recover original CAD authoring history",
            "three generated controls do not establish a general parametric modeling API",
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_figure(path: Path, probe: ParametricFeatureGraphProbe) -> None:
    colors = {
        "datum_plane": "#4c78a8", "parameter": "#59a14f", "sketch": "#f28e2b",
        "feature": "#e15759", "result": "#b279a2", "import_reference": "#76b7b2",
        "observation": "#9c755f", "reconstruction_candidate": "#edc948",
    }
    figure, axes = plt.subplots(2, 2, figsize=(12, 9))
    for axis, graph in zip(axes.flat, probe.graphs, strict=True):
        levels: dict[str, int] = {}
        dependencies = {item.node_id: [] for item in graph.nodes}
        for edge in graph.edges:
            dependencies[edge.dependent_node_id].append(edge.dependency_node_id)
        def level(node_id: str) -> int:
            if node_id not in levels:
                levels[node_id] = 0 if not dependencies[node_id] else 1 + max(level(item) for item in dependencies[node_id])
            return levels[node_id]
        for item in graph.nodes:
            level(item.node_id)
        by_level: dict[int, list[object]] = {}
        for item in graph.nodes:
            by_level.setdefault(levels[item.node_id], []).append(item)
        positions = {}
        for x, items in sorted(by_level.items()):
            for index, item in enumerate(items):
                positions[item.node_id] = (x, index - (len(items) - 1) / 2.0)
        for edge in graph.edges:
            x1, y1 = positions[edge.dependency_node_id]
            x2, y2 = positions[edge.dependent_node_id]
            axis.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops={"arrowstyle": "->", "color": "#9ca3af"})
        for item in graph.nodes:
            x, y = positions[item.node_id]
            axis.scatter((x,), (y,), s=420, color=colors[item.node_type], edgecolor="#111827", zorder=2)
            axis.text(x, y - 0.35, item.name, ha="center", va="top", fontsize=7)
        axis.set_title(f"{graph.graph_id}\n{graph.graph_kind}")
        axis.axis("off")
    figure.suptitle("Versioned parametric feature graphs and isolated import candidate")
    figure.subplots_adjust(left=0.04, right=0.98, top=0.89, bottom=0.06, wspace=0.18, hspace=0.30)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160, metadata={"Software": "research-notes"})
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build deterministic parametric feature graph evidence.")
    parser.add_argument("--import-reference", type=Path, default=Path("fixtures/feature-recognition-benchmark/benchmark_through_hole_baseline.step"))
    parser.add_argument("--fixture-dir", type=Path, default=Path("fixtures/parametric-feature-graphs"))
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument("--refresh-fixtures", action="store_true")
    args = parser.parse_args()
    probe = probe_parametric_feature_graphs(args.import_reference)
    handle_fixtures(args.fixture_dir, probe, refresh=args.refresh_fixtures)
    _write_csv(args.output_dir / NODES_NAME, node_rows(probe))
    _write_csv(args.output_dir / EDGES_NAME, edge_rows(probe))
    _write_csv(args.output_dir / EVALUATIONS_NAME, evaluation_rows(probe))
    _write_csv(args.output_dir / VALIDATIONS_NAME, validation_rows(probe))
    write_graphs(args.output_dir / GRAPHS_NAME, probe)
    write_contract(args.output_dir / CONTRACT_NAME, probe)
    write_figure(args.output_dir / FIGURE_NAME, probe)
    write_shape_previews(args.output_dir / SHAPES_NAME, probe.preview_shapes, title="Parametric feature graph result shapes", columns=3)
    print(f"Wrote deterministic parametric feature graph evidence to {args.output_dir}")


if __name__ == "__main__":
    main()
