"""Tests for staged Part 21 validation against controlled EXPRESS schemas."""

from __future__ import annotations

import hashlib
from collections import Counter

import pytest

from research_notes import (
    STEPExpressValidationLimits,
    build_step_express_validation_fixtures,
    inspect_step_express_validation,
)


def fixture_map() -> dict[str, object]:
    """Return paired v0.27 fixtures keyed by stable names."""
    return {
        fixture.fixture: fixture
        for fixture in build_step_express_validation_fixtures()
    }


def inspect_fixture(name: str):
    """Inspect one named fixture with its declared validation limits."""
    fixture = fixture_map()[name]
    return inspect_step_express_validation(
        fixture.step_bytes,
        fixture.express_bytes,
        validation_limits=fixture.validation_limits,
    )


def test_all_paired_fixture_expectations_are_met() -> None:
    """Every controlled schema-binding outcome should match its declaration."""
    fixtures = build_step_express_validation_fixtures()

    assert len(fixtures) == 40
    assert Counter(item.expected_decision for item in fixtures) == {
        "accept": 15,
        "reject": 21,
        "quarantine": 4,
    }
    for fixture in fixtures:
        result = inspect_step_express_validation(
            fixture.step_bytes,
            fixture.express_bytes,
            validation_limits=fixture.validation_limits,
        )
        assert result.decision == fixture.expected_decision, fixture.fixture
        assert result.reason_code == fixture.expected_reason_code, fixture.fixture
        assert result.application_semantics == "not_attempted"
        assert result.rule_execution == "not_attempted"


def test_simple_values_optional_markers_and_enumerations_validate() -> None:
    """Controlled scalar encodings and optional omission should bind to attributes."""
    scalar = inspect_fixture("scalar_types")
    optional = inspect_fixture("optional_omitted")
    enumeration = inspect_fixture("enumeration_value")

    assert scalar.parameter_count == 7
    assert scalar.valid_parameter_count == 7
    assert [item.attribute_name for item in scalar.parameters] == [
        "integer_value",
        "real_value",
        "number_value",
        "text_value",
        "flag",
        "state",
        "bits",
    ]
    assert optional.parameters[0].reason_code == "optional_omission_valid"
    assert enumeration.parameters[0].reason_code == "enumeration_value_valid"


def test_internal_mapping_orders_ancestors_and_deduplicates_diamonds() -> None:
    """Inherited explicit attributes should occupy stable Part 21 positions."""
    internal = inspect_fixture("internal_inheritance")
    diamond = inspect_fixture("diamond_inheritance")
    wrong_order = inspect_fixture("inheritance_parameter_order")

    assert [item.attribute_owner for item in internal.parameters] == [
        "root",
        "middle",
        "leaf",
    ]
    assert [item.attribute_owner for item in diamond.parameters] == [
        "root",
        "left",
        "right",
        "leaf",
    ]
    assert wrong_order.decision == "reject"
    assert wrong_order.invalid_parameter_count == 2


def test_derived_redeclaration_requires_the_asterisk_at_the_origin_slot() -> None:
    """A derived redeclaration should replace the inherited value with `*`."""
    valid = inspect_fixture("derived_redeclaration")
    invalid = inspect_fixture("derived_marker_required")

    assert valid.parameters[0].attribute_owner == "base"
    assert valid.parameters[0].value_source == "*"
    assert valid.parameters[0].reason_code == "derived_marker_valid"
    assert invalid.parameters[0].reason_code == "derived_marker_required"


def test_references_allow_forward_targets_and_entity_subtypes() -> None:
    """Reference validation should use global IDs and resolved inheritance."""
    forward = inspect_fixture("forward_entity_reference")
    subtype = inspect_fixture("subtype_entity_reference")
    unresolved = inspect_fixture("unresolved_entity_reference")
    wrong = inspect_fixture("wrong_reference_type")

    assert forward.parameters[0].reason_code == "entity_reference_valid"
    assert subtype.parameters[0].reason_code == "entity_reference_valid"
    assert unresolved.reason_code == "unresolved_entity_reference"
    assert wrong.reason_code == "entity_reference_type_mismatch"


def test_aggregate_cardinality_uniqueness_and_select_wrappers_are_checked() -> None:
    """Container and select contracts should retain distinct failure reasons."""
    aggregate = inspect_fixture("aggregate_list")
    too_short = inspect_fixture("aggregate_cardinality")
    duplicate = inspect_fixture("aggregate_duplicate")
    select = inspect_fixture("select_typed_defined")
    untyped = inspect_fixture("select_untyped")

    assert aggregate.parameters[0].reason_code == "aggregate_value_valid"
    assert too_short.reason_code == "aggregate_cardinality_mismatch"
    assert duplicate.reason_code == "aggregate_unique_violation"
    assert select.parameters[0].status == "valid"
    assert untyped.reason_code == "select_typed_parameter_required"


def test_stages_stop_before_claiming_deeper_validation() -> None:
    """Syntax, name resolution, and schema validation should remain separate."""
    part21 = inspect_fixture("part21_syntax_failure")
    express = inspect_fixture("express_syntax_failure")
    resolution = inspect_fixture("express_resolution_failure")

    assert part21.part21_syntax == "invalid"
    assert part21.express_syntax == "not_reached"
    assert express.part21_syntax == "valid"
    assert express.express_syntax == "invalid"
    assert resolution.express_syntax == "valid"
    assert resolution.express_resolution == "invalid"
    assert resolution.schema_binding == "not_reached"


def test_complex_mapping_is_structurally_checked_then_deferred() -> None:
    """Partial records should not imply complete evaluated-set validation."""
    controlled = inspect_fixture("complex_mapping_deferred")
    wrong_order = inspect_fixture("complex_component_order")

    assert controlled.decision == "quarantine"
    assert controlled.instances[0].record_types == ("BASE", "LEFT", "RIGHT")
    assert controlled.instances[0].expected_parameter_count == 3
    assert controlled.instances[0].actual_parameter_count == 3
    assert controlled.valid_parameter_count == 3
    assert wrong_order.decision == "reject"
    assert wrong_order.reason_code == "complex_component_order"


def test_fixture_bytes_and_analysis_rows_are_deterministic() -> None:
    """Repeated construction should preserve paired source bytes and evidence."""
    first = build_step_express_validation_fixtures()
    second = build_step_express_validation_fixtures()

    assert [item.step_bytes for item in first] == [item.step_bytes for item in second]
    assert [item.express_bytes for item in first] == [
        item.express_bytes for item in second
    ]
    assert [hashlib.sha256(item.step_bytes).hexdigest() for item in first] == [
        hashlib.sha256(item.step_bytes).hexdigest() for item in second
    ]
    assert inspect_fixture("diamond_inheritance").parameters == inspect_fixture(
        "diamond_inheritance"
    ).parameters


def test_public_input_and_validation_limits_are_explicit() -> None:
    """Invalid public inputs and resource budgets should fail predictably."""
    valid = fixture_map()["empty_entity"]
    limited = inspect_fixture("validation_parameter_limit")

    assert limited.decision == "quarantine"
    assert limited.reason_code == "validation_parameter_limit"
    with pytest.raises(TypeError, match="step_bytes"):
        inspect_step_express_validation("bad", valid.express_bytes)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="express_bytes"):
        inspect_step_express_validation(valid.step_bytes, "bad")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="validation_limits"):
        inspect_step_express_validation(
            valid.step_bytes, valid.express_bytes, validation_limits=object()
        )  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="max_parameters"):
        STEPExpressValidationLimits(max_parameters=0)
