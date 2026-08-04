"""Evaluate deterministic graph construction and queries over STEP Part 21."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

from research_notes import (  # noqa: E402
    STEPGraph,
    STEPGraphFixture,
    build_step_graph_fixtures,
    inspect_step_graph_fixture,
)


MANIFEST_NAME = "manifest.csv"
OBSERVATIONS_NAME = "step_graph_observations.csv"
NODES_NAME = "step_graph_nodes.csv"
EDGES_NAME = "step_graph_edges.csv"
QUERIES_NAME = "step_graph_queries.csv"
SUMMARY_NAME = "step_graph_summary.csv"
JSON_NAME = "step_graph.json"
FIGURE_NAME = "step_graph.png"

MANIFEST_FIELDS = (
    "fixture",
    "category",
    "condition",
    "file_name",
    "expected_decision",
    "expected_reason_code",
    "root_entity_ids",
    "source_bytes",
    "source_sha256",
    "max_nodes",
    "max_edges",
    "max_query_results",
    "max_traversal_visits",
    "max_traversal_depth",
    "query_max_depth",
)
OBSERVATION_FIELDS = (
    "fixture",
    "category",
    "condition",
    "expected_decision",
    "observed_decision",
    "expectation_met",
    "expected_reason_code",
    "reason_code",
    "node_count",
    "edge_count",
    "local_edge_count",
    "external_edge_count",
    "unresolved_edge_count",
    "constant_edge_count",
    "root_count",
    "isolated_count",
    "cyclic_component_count",
    "traversal_complete",
    "traversal_reason_code",
    "reachable_count",
    "orphan_count",
    "source_sha256",
)
NODE_FIELDS = (
    "fixture",
    "node_index",
    "entity_id",
    "section_index",
    "section_name",
    "schema_identifier",
    "record_types",
    "is_complex",
    "outbound_edge_count",
    "inbound_edge_count",
    "start_offset",
    "end_offset",
    "start_byte",
    "end_byte",
    "start_line",
    "start_column",
    "end_line",
    "end_column",
)
EDGE_FIELDS = (
    "fixture",
    "edge_index",
    "source_node_index",
    "source_entity_id",
    "target_node_index",
    "target_entity_id",
    "target_occurrence",
    "target_scope",
    "reference_kind",
    "record_index",
    "parameter_path",
    "start_offset",
    "end_offset",
    "start_byte",
    "end_byte",
    "start_line",
    "start_column",
    "end_line",
    "end_column",
)
QUERY_FIELDS = (
    "fixture",
    "query",
    "arguments",
    "status",
    "reason_code",
    "result_count",
    "result_entity_ids",
)
SUMMARY_FIELDS = ("scope", "metric", "value")


def write_csv(
    path: Path,
    rows: Sequence[dict[str, str]],
    fields: Sequence[str],
) -> None:
    """Write deterministic UTF-8 CSV evidence."""
    if not rows:
        raise ValueError("rows must not be empty")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def manifest_rows(fixtures: Sequence[STEPGraphFixture]) -> list[dict[str, str]]:
    """Describe exact graph inputs, expectations, roots, and budgets."""
    return [
        {
            "fixture": item.fixture,
            "category": item.category,
            "condition": item.condition,
            "file_name": item.file_name,
            "expected_decision": item.expected_decision,
            "expected_reason_code": item.expected_reason_code,
            "root_entity_ids": _ids(item.root_entity_ids),
            "source_bytes": str(len(item.source_bytes)),
            "source_sha256": hashlib.sha256(item.source_bytes).hexdigest(),
            "max_nodes": str(item.graph_limits.max_nodes),
            "max_edges": str(item.graph_limits.max_edges),
            "max_query_results": str(item.graph_limits.max_query_results),
            "max_traversal_visits": str(item.graph_limits.max_traversal_visits),
            "max_traversal_depth": str(item.graph_limits.max_traversal_depth),
            "query_max_depth": (
                "" if item.query_max_depth is None else str(item.query_max_depth)
            ),
        }
        for item in fixtures
    ]


def refresh_fixture_corpus(
    fixture_dir: Path, fixtures: Sequence[STEPGraphFixture]
) -> None:
    """Write deterministic STEP fixtures without deleting unknown files."""
    fixture_dir.mkdir(parents=True, exist_ok=True)
    expected = {item.file_name for item in fixtures}
    existing = {
        path.name for path in fixture_dir.iterdir() if path.name != MANIFEST_NAME
    }
    unexpected = sorted(existing - expected)
    if unexpected:
        raise RuntimeError(
            "fixture directory contains unexpected files: " + ", ".join(unexpected)
        )
    for fixture in fixtures:
        (fixture_dir / fixture.file_name).write_bytes(fixture.source_bytes)
    write_csv(fixture_dir / MANIFEST_NAME, manifest_rows(fixtures), MANIFEST_FIELDS)


def load_fixture_corpus(
    fixture_dir: Path, fixtures: Sequence[STEPGraphFixture]
) -> tuple[STEPGraphFixture, ...]:
    """Load committed fixture bytes after exact manifest checks."""
    manifest_path = fixture_dir / MANIFEST_NAME
    if not manifest_path.is_file():
        raise RuntimeError(
            f"missing fixture manifest: {manifest_path}; use --refresh-fixtures"
        )
    with manifest_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if rows != manifest_rows(fixtures):
        raise RuntimeError("committed fixture manifest does not match definitions")
    for fixture in fixtures:
        if (fixture_dir / fixture.file_name).read_bytes() != fixture.source_bytes:
            raise RuntimeError(f"fixture differs from definition: {fixture.file_name}")
    return tuple(fixtures)


def build_rows(
    fixtures: Sequence[STEPGraphFixture],
) -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    dict[str, STEPGraph],
]:
    """Run the corpus and expand graph, source, and query evidence."""
    observations: list[dict[str, str]] = []
    nodes: list[dict[str, str]] = []
    edges: list[dict[str, str]] = []
    queries: list[dict[str, str]] = []
    graphs: dict[str, STEPGraph] = {}
    for fixture in fixtures:
        observation = inspect_step_graph_fixture(fixture)
        source_sha256 = hashlib.sha256(fixture.source_bytes).hexdigest()
        observations.append(
            {
                "fixture": fixture.fixture,
                "category": fixture.category,
                "condition": fixture.condition,
                "expected_decision": fixture.expected_decision,
                "observed_decision": observation.decision,
                "expectation_met": str(
                    int(
                        observation.decision == fixture.expected_decision
                        and observation.reason_code == fixture.expected_reason_code
                    )
                ),
                "expected_reason_code": fixture.expected_reason_code,
                "reason_code": observation.reason_code,
                "node_count": str(observation.node_count),
                "edge_count": str(observation.edge_count),
                "local_edge_count": str(observation.local_edge_count),
                "external_edge_count": str(observation.external_edge_count),
                "unresolved_edge_count": str(observation.unresolved_edge_count),
                "constant_edge_count": str(observation.constant_edge_count),
                "root_count": str(observation.root_count),
                "isolated_count": str(observation.isolated_count),
                "cyclic_component_count": str(observation.cyclic_component_count),
                "traversal_complete": (
                    ""
                    if observation.traversal_complete is None
                    else str(int(observation.traversal_complete))
                ),
                "traversal_reason_code": observation.traversal_reason_code,
                "reachable_count": str(observation.reachable_count),
                "orphan_count": (
                    "" if observation.orphan_count is None else str(observation.orphan_count)
                ),
                "source_sha256": source_sha256,
            }
        )
        if observation.graph is None or observation.traversal is None:
            continue
        graph = observation.graph
        graphs[fixture.fixture] = graph
        for node in graph.nodes:
            nodes.append(
                {
                    "fixture": fixture.fixture,
                    "node_index": str(node.node_index),
                    "entity_id": str(node.entity_id),
                    "section_index": str(node.section_index),
                    "section_name": node.section_name or "",
                    "schema_identifier": node.schema_identifier,
                    "record_types": "|".join(node.record_types),
                    "is_complex": str(int(node.is_complex)),
                    "outbound_edge_count": str(len(node.outbound_edge_indices)),
                    "inbound_edge_count": str(len(node.inbound_edge_indices)),
                    **_span_columns(node.source_span),
                }
            )
        for edge in graph.edges:
            edges.append(
                {
                    "fixture": fixture.fixture,
                    "edge_index": str(edge.edge_index),
                    "source_node_index": str(edge.source_node_index),
                    "source_entity_id": str(edge.source_entity_id),
                    "target_node_index": (
                        "" if edge.target_node_index is None else str(edge.target_node_index)
                    ),
                    "target_entity_id": (
                        "" if edge.target_entity_id is None else str(edge.target_entity_id)
                    ),
                    "target_occurrence": edge.target_occurrence,
                    "target_scope": edge.target_scope,
                    "reference_kind": edge.reference_kind,
                    "record_index": str(edge.record_index),
                    "parameter_path": "/".join(str(item) for item in edge.parameter_path),
                    **_span_columns(edge.source_span),
                }
            )
        queries.extend(_query_rows(fixture, graph, observation))
    return observations, nodes, edges, queries, graphs


def _query_rows(
    fixture: STEPGraphFixture,
    graph: STEPGraph,
    observation,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    traversal = observation.traversal
    assert traversal is not None
    rows.append(
        _query_row(
            fixture.fixture,
            "forward_reachability",
            _ids(fixture.root_entity_ids),
            "complete" if traversal.complete else "partial",
            traversal.reason_code,
            traversal.entity_ids,
        )
    )
    reverse_start = graph.nodes[-1].entity_id
    reverse = graph.traverse((reverse_start,), direction="reverse")
    rows.append(
        _query_row(
            fixture.fixture,
            "reverse_reachability",
            str(reverse_start),
            "complete" if reverse.complete else "partial",
            reverse.reason_code,
            reverse.entity_ids,
        )
    )
    roots = tuple(node.entity_id for node in graph.root_nodes())
    isolated = tuple(node.entity_id for node in graph.isolated_nodes())
    rows.append(
        _query_row(
            fixture.fixture, "zero_indegree_nodes", "", "complete", "query_complete", roots
        )
    )
    rows.append(
        _query_row(
            fixture.fixture, "isolated_nodes", "", "complete", "query_complete", isolated
        )
    )
    cycles = graph.cyclic_components()
    cycle_text = ";".join(_ids(component) for component in cycles)
    rows.append(
        {
            "fixture": fixture.fixture,
            "query": "cyclic_components",
            "arguments": "",
            "status": "complete",
            "reason_code": "query_complete",
            "result_count": str(len(cycles)),
            "result_entity_ids": cycle_text,
        }
    )
    if traversal.complete:
        orphans = tuple(
            node.entity_id for node in graph.orphaned_from(fixture.root_entity_ids)
        )
        rows.append(
            _query_row(
                fixture.fixture,
                "root_relative_orphans",
                _ids(fixture.root_entity_ids),
                "complete",
                "query_complete",
                orphans,
            )
        )
    else:
        rows.append(
            {
                "fixture": fixture.fixture,
                "query": "root_relative_orphans",
                "arguments": _ids(fixture.root_entity_ids),
                "status": "not_evaluated",
                "reason_code": traversal.reason_code,
                "result_count": "",
                "result_entity_ids": "",
            }
        )
    for type_name in sorted({name for node in graph.nodes for name in node.record_types}):
        matches = tuple(node.entity_id for node in graph.nodes_of_type(type_name))
        rows.append(
            _query_row(
                fixture.fixture,
                "entity_type",
                type_name,
                "complete",
                "query_complete",
                matches,
            )
        )
    return rows


def _query_row(
    fixture: str,
    query: str,
    arguments: str,
    status: str,
    reason_code: str,
    entity_ids: Sequence[int],
) -> dict[str, str]:
    return {
        "fixture": fixture,
        "query": query,
        "arguments": arguments,
        "status": status,
        "reason_code": reason_code,
        "result_count": str(len(entity_ids)),
        "result_entity_ids": _ids(entity_ids),
    }


def summary_rows(
    observations: Sequence[dict[str, str]],
    edges: Sequence[dict[str, str]],
    queries: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Aggregate decisions, edge scopes, and query completion states."""
    decisions = Counter(row["observed_decision"] for row in observations)
    scopes = Counter(row["target_scope"] for row in edges)
    statuses = Counter(row["status"] for row in queries)
    rows = [
        {"scope": "corpus", "metric": "fixture_count", "value": str(len(observations))},
        {
            "scope": "corpus",
            "metric": "expectation_match_count",
            "value": str(sum(int(row["expectation_met"]) for row in observations)),
        },
        {"scope": "graph", "metric": "node_count", "value": str(sum(int(row["node_count"]) for row in observations))},
        {"scope": "graph", "metric": "edge_count", "value": str(len(edges))},
    ]
    rows.extend(
        {"scope": "decision", "metric": key, "value": str(decisions.get(key, 0))}
        for key in ("accept", "quarantine", "reject")
    )
    rows.extend(
        {"scope": "target_scope", "metric": key, "value": str(scopes.get(key, 0))}
        for key in (
            "local_entity",
            "external_entity",
            "external_value",
            "schema_constant",
            "unresolved",
        )
    )
    rows.extend(
        {"scope": "query_status", "metric": key, "value": str(statuses.get(key, 0))}
        for key in ("complete", "partial", "not_evaluated")
    )
    return rows


def save_figure(
    path: Path,
    observations: Sequence[dict[str, str]],
    edges: Sequence[dict[str, str]],
    representative: STEPGraph,
) -> None:
    """Visualize one graph and aggregate construction evidence."""
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.6))
    ax = axes[0]
    positions = {
        1: (0.05, 0.50),
        2: (0.42, 0.80),
        3: (0.42, 0.25),
        4: (0.78, 0.25),
        99: (0.78, 0.80),
    }
    for edge in representative.edges:
        if not edge.is_local or edge.target_entity_id is None:
            continue
        start = positions[edge.source_entity_id]
        end = positions[edge.target_entity_id]
        ax.annotate(
            "",
            xy=end,
            xytext=start,
            arrowprops={
                "arrowstyle": "->",
                "color": "#4b5563",
                "lw": 1.5,
                "shrinkA": 18,
                "shrinkB": 18,
                "mutation_scale": 12,
            },
        )
    for node in representative.nodes:
        x, y = positions[node.entity_id]
        color = "#ef8354" if node.entity_id == 99 else "#4f86c6"
        ax.scatter([x], [y], s=900, color=color, edgecolor="white", linewidth=1.5, zorder=3)
        ax.text(
            x,
            y,
            f"#{node.entity_id}",
            ha="center",
            va="center",
            color="white",
            fontsize=9,
            zorder=4,
        )
        ax.text(
            x,
            y - 0.085,
            node.record_types[0],
            ha="center",
            va="top",
            color="#263238",
            fontsize=7,
            zorder=4,
        )
    ax.set_title("Declared root #1 and root-relative orphan #99")
    ax.set_xlim(-0.1, 0.95)
    ax.set_ylim(0.05, 0.95)
    ax.axis("off")

    scopes = Counter(row["target_scope"] for row in edges)
    scope_order = [
        "local_entity",
        "external_entity",
        "external_value",
        "schema_constant",
        "unresolved",
    ]
    axes[1].barh(scope_order, [scopes.get(scope, 0) for scope in scope_order], color="#4f86c6")
    axes[1].set_title("Reference occurrences by target scope")
    axes[1].set_xlabel("Edges")
    axes[1].grid(axis="x", alpha=0.25)

    decisions = Counter(row["observed_decision"] for row in observations)
    decision_order = ["accept", "quarantine", "reject"]
    axes[2].bar(
        decision_order,
        [decisions.get(decision, 0) for decision in decision_order],
        color=["#3a9d5d", "#e0a11a", "#c94c4c"],
    )
    axes[2].set_title("Controlled fixture routes")
    axes[2].set_ylabel("Fixtures")
    axes[2].grid(axis="y", alpha=0.25)
    for index, decision in enumerate(decision_order):
        axes[2].text(index, decisions.get(decision, 0) + 0.2, str(decisions.get(decision, 0)), ha="center")

    fig.suptitle("Generic STEP Graph and Query API — v0.28.0", fontsize=14)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def run(fixture_dir: Path, output_dir: Path, *, refresh_fixtures: bool) -> None:
    """Generate fixtures, execute graph queries, and write committed evidence."""
    definitions = build_step_graph_fixtures()
    if refresh_fixtures:
        refresh_fixture_corpus(fixture_dir, definitions)
    fixtures = load_fixture_corpus(fixture_dir, definitions)
    observations, nodes, edges, queries, graphs = build_rows(fixtures)
    write_csv(output_dir / OBSERVATIONS_NAME, observations, OBSERVATION_FIELDS)
    write_csv(output_dir / NODES_NAME, nodes, NODE_FIELDS)
    write_csv(output_dir / EDGES_NAME, edges, EDGE_FIELDS)
    write_csv(output_dir / QUERIES_NAME, queries, QUERY_FIELDS)
    write_csv(
        output_dir / SUMMARY_NAME,
        summary_rows(observations, edges, queries),
        SUMMARY_FIELDS,
    )
    representative = graphs["branching_orphan"]
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / JSON_NAME).open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(
            representative.to_record(),
            handle,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        handle.write("\n")
    save_figure(output_dir / FIGURE_NAME, observations, edges, representative)


def _span_columns(span) -> dict[str, str]:
    return {
        "start_offset": str(span.start_offset),
        "end_offset": str(span.end_offset),
        "start_byte": str(span.start_byte),
        "end_byte": str(span.end_byte),
        "start_line": str(span.start_line),
        "start_column": str(span.start_column),
        "end_line": str(span.end_line),
        "end_column": str(span.end_column),
    }


def _ids(values: Sequence[int]) -> str:
    return "|".join(str(value) for value in values)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate bounded graph queries over deterministic STEP fixtures."
    )
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=Path("fixtures/step-graph-queries"),
        help="Directory containing the committed STEP graph fixture corpus.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results"),
        help="Directory for CSV, JSON, and PNG evidence.",
    )
    parser.add_argument(
        "--refresh-fixtures",
        action="store_true",
        help="Rewrite deterministic fixture files and their manifest.",
    )
    args = parser.parse_args()
    run(args.fixture_dir, args.output_dir, refresh_fixtures=args.refresh_fixtures)


if __name__ == "__main__":
    main()
