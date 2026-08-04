"""Tests for controlled AP242 product-to-representation path resolution."""

from __future__ import annotations

from collections import Counter

import pytest

from research_notes import (
    AP242PathLimitError,
    AP242PathLimits,
    build_ap242_path_fixtures,
    inspect_ap242_path_fixture,
    resolve_ap242_product_paths,
)


def fixture_map() -> dict[str, object]:
    """Return v0.29 fixtures keyed by stable names."""
    return {fixture.fixture: fixture for fixture in build_ap242_path_fixtures()}


def result_for(name: str):
    """Resolve one fixture without discarding controlled evidence."""
    fixture = fixture_map()[name]
    return resolve_ap242_product_paths(
        fixture.source_bytes, path_limits=fixture.path_limits
    )


def test_all_ap242_fixture_expectations_are_met() -> None:
    """Every resolved, deferred, invalid, and bounded route should be declared."""
    fixtures = build_ap242_path_fixtures()

    assert len(fixtures) == 14
    assert Counter(item.expected_decision for item in fixtures) == {
        "accept": 3,
        "quarantine": 8,
        "reject": 3,
    }
    for fixture in fixtures:
        observation = inspect_ap242_path_fixture(fixture)
        assert observation.decision == fixture.expected_decision, fixture.fixture
        assert observation.reason_code == fixture.expected_reason_code, fixture.fixture


def test_resolved_path_exposes_product_representation_items_and_units() -> None:
    """The representative path should expose controlled semantic attributes."""
    result = result_for("ap242_block_path")

    assert result.decision == "accept"
    assert result.product_definition_count == 1
    assert result.path_count == 1
    path = result.paths[0]
    assert (path.product_identifier, path.product_name) == (
        "P-001",
        "Controlled block",
    )
    assert path.representation_type == "SHAPE_REPRESENTATION"
    assert path.coordinate_space_dimension == 3
    assert path.representation_item_count == 2
    assert path.placement_count == 1
    assert [item.role for item in result.representation_items] == [
        "placement",
        "solid_model",
    ]
    assert [(unit.unit_kind, unit.si_prefix, unit.si_name) for unit in result.units] == [
        ("length", "MILLI", "METRE"),
        ("plane_angle", None, "RADIAN"),
        ("solid_angle", None, "STERADIAN"),
    ]


def test_semantic_relations_are_unique_physical_reference_occurrences() -> None:
    """Reverse discovery and forward validation must not duplicate source edges."""
    result = result_for("ap242_block_path")
    physical_keys = [
        (relation.source_entity_id, relation.source_edge_index)
        for relation in result.relations
    ]

    assert len(result.relations) == 12
    assert len(physical_keys) == len(set(physical_keys))
    assert [relation.role for relation in result.relations] == [
        "product_definition.formation",
        "product_definition.frame_of_reference",
        "product_definition_formation.of_product",
        "product_definition_shape.definition",
        "shape_definition_representation.definition",
        "shape_definition_representation.used_representation",
        "representation.context_of_items",
        "representation.items",
        "representation.items",
        "global_unit_assigned_context.units",
        "global_unit_assigned_context.units",
        "global_unit_assigned_context.units",
    ]
    assert all(relation.source_span.start_line > 0 for relation in result.relations)


def test_multiple_shape_associations_remain_distinct_paths() -> None:
    """One product definition can resolve to more than one representation path."""
    result = result_for("ap242_multiple_representations")

    assert result.decision == "accept"
    assert result.path_count == 2
    assert [path.representation_name for path in result.paths] == [
        "controlled shape",
        "alternate shape",
    ]
    assert [path.representation_item_count for path in result.paths] == [2, 1]


def test_absent_geometry_and_schema_mismatch_are_deferred_not_corrupt() -> None:
    """Missing optional paths and unsupported schemas should remain quarantine routes."""
    no_shape = result_for("product_without_shape")
    ap214 = result_for("ap214_schema_boundary")

    assert (no_shape.decision, no_shape.reason_code) == (
        "quarantine",
        "product_definition_shape_not_found",
    )
    assert (ap214.decision, ap214.reason_code) == (
        "quarantine",
        "unsupported_application_schema",
    )
    assert no_shape.graph.nodes
    assert not no_shape.paths


def test_unclassified_item_preserves_path_evidence_but_quarantines_claim() -> None:
    """Unknown item roles should be exported without being called interpreted."""
    result = result_for("unclassified_item")

    assert result.decision == "quarantine"
    assert result.path_count == 1
    assert result.representation_items[-1].role == "unclassified"
    assert result.diagnostics[0].reason_code == "representation_item_type_deferred"


def test_resource_budget_and_public_input_contracts_fail_predictably() -> None:
    """Semantic work limits and invalid API inputs should be explicit."""
    fixture = fixture_map()["ap242_multiple_representations"]

    with pytest.raises(AP242PathLimitError, match="path budget"):
        resolve_ap242_product_paths(
            fixture.source_bytes,
            path_limits=AP242PathLimits(max_paths=1),
        )
    with pytest.raises(TypeError, match="source_bytes"):
        resolve_ap242_product_paths("bad")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="path_limits"):
        resolve_ap242_product_paths(
            fixture.source_bytes, path_limits=object()  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="max_relations"):
        AP242PathLimits(max_relations=0)
