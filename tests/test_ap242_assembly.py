"""Tests for controlled AP242 assembly and placement evaluation."""

from __future__ import annotations

from collections import Counter

import numpy as np
import pytest

from research_notes import (
    AP242AssemblyFixture,
    AssemblyLimitError,
    AssemblyLimits,
    build_ap242_assembly_fixtures,
    evaluate_ap242_assembly,
    inspect_ap242_assembly_fixture,
)


def fixture_map() -> dict[str, AP242AssemblyFixture]:
    """Return v0.30 fixtures keyed by stable names."""
    return {fixture.fixture: fixture for fixture in build_ap242_assembly_fixtures()}


def result_for(name: str):
    """Evaluate one fixture without discarding controlled evidence."""
    fixture = fixture_map()[name]
    return evaluate_ap242_assembly(
        fixture.source_bytes, assembly_limits=fixture.assembly_limits
    )


def test_all_assembly_fixture_expectations_are_met() -> None:
    """Every evaluated, deferred, invalid, and bounded route should be declared."""
    fixtures = build_ap242_assembly_fixtures()

    assert len(fixtures) == 17
    assert Counter(item.expected_decision for item in fixtures) == {
        "accept": 5,
        "quarantine": 6,
        "reject": 6,
    }
    for fixture in fixtures:
        observation = inspect_ap242_assembly_fixture(fixture)
        assert observation.decision == fixture.expected_decision, fixture.fixture
        assert observation.reason_code == fixture.expected_reason_code, fixture.fixture


def test_translation_and_source_frame_direction_are_evaluated() -> None:
    """A source-frame offset must be subtracted in the child-to-parent mapping."""
    translated = result_for("single_translation")
    offset = result_for("source_frame_offset")

    assert translated.paths[0].global_translation_mm == (10.0, 20.0, 30.0)
    assert offset.occurrences[0].local_translation_mm == (15.0, 0.0, 0.0)
    assert offset.paths[0].global_translation_mm == (15.0, 0.0, 0.0)


def test_rotation_is_a_proper_child_to_parent_rigid_transform() -> None:
    """A controlled quarter turn should preserve handedness and orthogonality."""
    result = result_for("rotated_occurrence")
    rotation = np.asarray(result.paths[0].global_rotation).reshape(3, 3)

    np.testing.assert_allclose(
        rotation,
        np.asarray(((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0))),
        atol=1.0e-12,
    )
    np.testing.assert_allclose(rotation.T @ rotation, np.eye(3), atol=1.0e-12)
    assert result.paths[0].rotation_determinant == pytest.approx(1.0)


def test_nested_reuse_keeps_definitions_and_occurrences_distinct() -> None:
    """One reusable definition should produce separate root-relative paths."""
    result = result_for("nested_reuse")
    paths = {path.reference_designators: path for path in result.paths}

    assert result.occurrence_count == 4
    assert result.path_count == 4
    assert result.distinct_definition_count == 3
    assert result.reused_definition_count == 1
    assert result.maximum_depth == 2
    assert paths[("S1", "B3")].global_translation_mm == (100.0, 10.0, 0.0)
    assert paths[("B1",)].global_translation_mm == (10.0, 0.0, 0.0)
    assert paths[("B2",)].global_translation_mm == (20.0, 0.0, 0.0)


def test_conversion_based_unit_normalizes_coordinates_to_millimetres() -> None:
    """An inch source coordinate should be scaled before frame composition."""
    result = result_for("conversion_based_inch")
    occurrence = result.occurrences[0]
    child_unit = next(unit for unit in result.units if unit.side == "child")

    assert occurrence.child_unit_name == "inch"
    assert occurrence.child_scale_to_millimetre == pytest.approx(25.4)
    assert occurrence.local_translation_mm == pytest.approx((25.4, 0.0, 0.0))
    assert child_unit.unit_form == "conversion_based"
    assert child_unit.conversion_hops == 1


def test_semantic_relations_retain_unique_physical_source_edges() -> None:
    """Each occurrence role should join to an exact parsed reference occurrence."""
    result = result_for("single_translation")
    physical_keys = [
        (relation.source_entity_id, relation.source_edge_index)
        for relation in result.relations
    ]

    assert result.relation_count == 28
    assert len(physical_keys) == len(set(physical_keys))
    assert all(relation.source_span.start_line > 0 for relation in result.relations)
    assert {relation.role for relation in result.relations} >= {
        "assembly_occurrence.parent_definition",
        "assembly_occurrence.child_definition",
        "representation_relationship.transformation_operator",
        "source_placement.location",
        "target_placement.location",
    }


def test_invalid_structures_do_not_become_accepted_partial_paths() -> None:
    """Wrong ordering, cycles, and duplicate labels must remain invalid."""
    wrong_order = result_for("wrong_representation_order")
    duplicate = result_for("duplicate_reference_designator")
    cycle = result_for("assembly_cycle")

    assert (wrong_order.decision, wrong_order.path_count) == ("reject", 0)
    assert (duplicate.decision, duplicate.path_count) == ("reject", 0)
    assert (cycle.decision, cycle.path_count) == ("reject", 0)


def test_work_budgets_and_public_input_contracts_fail_predictably() -> None:
    """Semantic limits and invalid API inputs should have stable outcomes."""
    fixture = fixture_map()["nested_reuse"]

    with pytest.raises(AssemblyLimitError, match="work budget"):
        evaluate_ap242_assembly(
            fixture.source_bytes,
            assembly_limits=AssemblyLimits(max_paths=1),
        )
    with pytest.raises(TypeError, match="source_bytes"):
        evaluate_ap242_assembly("bad")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="assembly_limits"):
        evaluate_ap242_assembly(
            fixture.source_bytes, assembly_limits=object()  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="max_unit_hops"):
        AssemblyLimits(max_unit_hops=0)
