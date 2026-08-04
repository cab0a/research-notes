"""Tests for the deterministic generic STEP graph and query API."""

from __future__ import annotations

import hashlib
import json
from collections import Counter

import pytest

from research_notes import (
    STEPGraphLimitError,
    STEPGraphLimits,
    build_step_graph,
    build_step_graph_fixtures,
    inspect_step_graph_fixture,
)


def fixture_map() -> dict[str, object]:
    """Return v0.28 fixtures keyed by stable names."""
    return {fixture.fixture: fixture for fixture in build_step_graph_fixtures()}


def graph_for(name: str):
    """Build one accepted graph fixture."""
    fixture = fixture_map()[name]
    return build_step_graph(
        fixture.source_bytes, graph_limits=fixture.graph_limits
    )


def test_all_graph_fixture_expectations_are_met() -> None:
    """Every construction, syntax, and resource route should match its declaration."""
    fixtures = build_step_graph_fixtures()

    assert len(fixtures) == 14
    assert Counter(item.expected_decision for item in fixtures) == {
        "accept": 11,
        "quarantine": 2,
        "reject": 1,
    }
    for fixture in fixtures:
        observation = inspect_step_graph_fixture(fixture)
        assert observation.decision == fixture.expected_decision, fixture.fixture
        assert observation.reason_code == fixture.expected_reason_code, fixture.fixture


def test_nodes_retain_stable_indices_section_schema_and_source_spans() -> None:
    """Analysis indices and ownership should follow DATA-section source order."""
    graph = graph_for("multiple_data_sections")

    assert [(node.node_index, node.entity_id) for node in graph.nodes] == [
        (0, 1),
        (1, 2),
    ]
    assert [(node.section_name, node.schema_identifier) for node in graph.nodes] == [
        ("left", "DEMO_A"),
        ("right", "DEMO_B"),
    ]
    assert graph.nodes[0].source_span.start_line < graph.nodes[1].source_span.start_line
    assert graph.nodes[0].source_span.start_byte == graph.nodes[0].source_span.start_offset


def test_forward_reverse_type_and_orphan_queries_are_explicit() -> None:
    """Graph direction and caller-declared reachability roots should remain distinct."""
    graph = graph_for("branching_orphan")

    assert [node.entity_id for node in graph.nodes_of_type("leaf")] == [2, 4]
    assert graph.traverse((1,)).entity_ids == (1, 2, 3, 4)
    assert graph.traverse((4,), direction="reverse").entity_ids == (4, 3, 1)
    assert [node.entity_id for node in graph.orphaned_from((1,))] == [99]
    assert [node.entity_id for node in graph.root_nodes()] == [1, 99]
    assert [node.entity_id for node in graph.isolated_nodes()] == [99]


def test_reference_occurrences_preserve_multigraph_edges_and_nested_paths() -> None:
    """Repeated and nested source occurrences should not collapse into one edge."""
    duplicate = graph_for("duplicate_reference_occurrences")
    nested = graph_for("nested_parameter_paths")

    assert len(duplicate.edges) == 2
    assert [edge.target_entity_id for edge in duplicate.edges] == [2, 2]
    assert [edge.parameter_path for edge in duplicate.edges] == [(0,), (1,)]
    assert [edge.parameter_path for edge in nested.edges] == [
        (0, 0),
        (0, 1, 0, 0),
        (0, 1, 0, 1),
    ]
    assert [edge.target_entity_id for edge in nested.edges] == [2, 3, 2]


def test_complex_record_types_share_one_node_and_keep_record_coordinates() -> None:
    """External mapping components should remain records on one entity node."""
    graph = graph_for("complex_instance")

    assert graph.node(1).record_types == ("BASE", "CHILD")
    assert graph.node(1).is_complex
    assert [(edge.record_index, edge.target_entity_id) for edge in graph.outbound(1)] == [
        (0, 2),
        (1, 3),
    ]


def test_nonlocal_target_scopes_remain_edges_without_becoming_nodes() -> None:
    """Unresolved, external, and constant references should retain distinct scopes."""
    unresolved = graph_for("unresolved_entity")
    external = graph_for("external_entity")
    values = graph_for("external_value_and_constant")

    assert unresolved.edges[0].target_scope == "unresolved"
    assert unresolved.edges[0].target_entity_id == 404
    assert external.edges[0].target_scope == "external_entity"
    assert external.edges[0].target_node_index is None
    assert [(edge.reference_kind, edge.target_scope) for edge in values.edges] == [
        ("value", "external_value"),
        ("constant", "schema_constant"),
    ]


def test_cycle_query_returns_components_not_unbounded_cycle_enumeration() -> None:
    """Strongly connected components should identify cycles deterministically."""
    graph = graph_for("directed_cycles")

    assert graph.cyclic_components() == ((1, 2, 3), (4,))
    assert graph.traverse((5,)).entity_ids == (5, 1, 2, 3)
    assert [node.entity_id for node in graph.orphaned_from((5,))] == [4]


def test_bounded_traversal_marks_partial_evidence_and_blocks_orphan_claims() -> None:
    """A depth boundary should be observable instead of yielding false orphans."""
    graph = graph_for("depth_limited_chain")
    traversal = graph.traverse((1,), max_depth=3)

    assert traversal.entity_ids == (1, 2, 3, 4)
    assert not traversal.complete
    assert traversal.reason_code == "traversal_depth_limit"
    with pytest.raises(STEPGraphLimitError, match="complete forward traversal"):
        graph.orphaned_from((1,))


def test_versioned_json_is_deterministic_and_contains_source_contracts() -> None:
    """Repeated serialization should preserve exact JSON records and source hashes."""
    fixture = fixture_map()["branching_orphan"]
    first = graph_for("branching_orphan")
    second = graph_for("branching_orphan")
    record = json.loads(first.to_json())

    assert first.to_json() == second.to_json()
    assert record["record_type"] == "research-notes.step-graph"
    assert record["format_version"] == "1.0"
    assert record["source_sha256"] == hashlib.sha256(fixture.source_bytes).hexdigest()
    assert record["nodes"][0]["source_span"]["start_line"] > 0
    assert record["edges"][0]["parameter_path"] == [0, 0]


def test_public_inputs_and_query_result_limits_fail_predictably() -> None:
    """Invalid types, IDs, directions, depths, and result budgets should be explicit."""
    fixture = fixture_map()["isolated_nodes"]
    limited = build_step_graph(
        fixture.source_bytes,
        graph_limits=STEPGraphLimits(max_query_results=1),
    )

    with pytest.raises(STEPGraphLimitError, match="result budget"):
        limited.root_nodes()
    with pytest.raises(TypeError, match="source_bytes"):
        build_step_graph("bad")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="graph_limits"):
        build_step_graph(fixture.source_bytes, graph_limits=object())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="non-empty string"):
        graph_for("isolated_nodes").nodes_of_type("")
    with pytest.raises(ValueError, match="direction"):
        graph_for("isolated_nodes").traverse((1,), direction="sideways")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="configured traversal depth"):
        graph_for("isolated_nodes").traverse((1,), max_depth=65)
    with pytest.raises(ValueError, match="max_edges"):
        STEPGraphLimits(max_edges=0)
