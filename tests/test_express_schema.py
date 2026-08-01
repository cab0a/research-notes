"""Tests for the controlled EXPRESS lexer, parser, and schema model."""

from __future__ import annotations

import hashlib

import pytest

from research_notes.express_schema import (
    ExpressParseLimits,
    lex_express,
    parse_express_document,
)
from research_notes.express_study import (
    build_express_schema_fixtures,
    inspect_express_schema,
)


def fixture_map() -> dict[str, object]:
    """Return v0.25 fixtures keyed by stable names."""
    return {
        fixture.fixture: fixture for fixture in build_express_schema_fixtures()
    }


def test_all_express_fixture_expectations_are_met() -> None:
    """Every controlled syntax and resource-boundary outcome should match."""
    fixtures = build_express_schema_fixtures()

    assert len(fixtures) == 40
    assert sum(item.expected_decision == "accept" for item in fixtures) == 20
    for fixture in fixtures:
        result = inspect_express_schema(
            fixture.source_bytes, limits=fixture.limits
        )
        assert result.decision == fixture.expected_decision, fixture.fixture
        assert result.reason_code == fixture.expected_reason_code, fixture.fixture
        assert result.symbol_resolution == "not_attempted"
        assert result.expression_validation == "envelope_only"


def test_lexer_preserves_source_comments_and_case_insensitive_keywords() -> None:
    """Raw spelling should survive while keyword matching remains case-insensitive."""
    fixtures = fixture_map()
    source, tokens = lex_express(fixtures["mixed_case"].source_bytes)
    comments = parse_express_document(fixtures["comments"].source_bytes)

    assert "sChEmA" in source
    assert tokens[0].kind == "KEYWORD"
    assert tokens[0].value == "SCHEMA"
    assert tokens[0].raw == "sChEmA"
    assert comments.reconstruct_source() == comments.source_text
    assert any(token.kind == "LINE_COMMENT" for token in comments.tokens)
    assert any(token.kind == "BLOCK_COMMENT" for token in comments.tokens)
    for token in comments.tokens:
        assert comments.source_slice(token.span) == token.raw


def test_type_model_separates_alias_enumeration_select_and_aggregate() -> None:
    """Controlled type forms should retain distinct unresolved structures."""
    fixtures = fixture_map()
    alias = parse_express_document(fixtures["type_alias_where"].source_bytes)
    enumeration = parse_express_document(fixtures["enumeration_type"].source_bytes)
    select = parse_express_document(fixtures["select_type"].source_bytes)
    aggregate = parse_express_document(fixtures["aggregate_type"].source_bytes)

    alias_type = alias.schemas[0].types[0]
    assert alias_type.underlying_type.kind == "simple"
    assert alias_type.underlying_type.parameter == "32"
    assert alias_type.underlying_type.fixed
    assert alias_type.where_rules[0].label == "nonempty"
    assert enumeration.schemas[0].types[0].underlying_type.members == (
        "rough",
        "smooth",
        "polished",
    )
    assert select.schemas[0].types[0].underlying_type.kind == "select"
    aggregate_type = aggregate.schemas[0].types[0].underlying_type
    assert aggregate_type.aggregate_kind == "LIST"
    assert (aggregate_type.lower_bound, aggregate_type.upper_bound) == ("1", "?")
    assert aggregate_type.unique
    assert aggregate_type.element_type is not None
    assert aggregate_type.element_type.name == "STRING"


def test_entity_model_retains_inheritance_and_attribute_kinds() -> None:
    """Entity declarations should preserve headers and all three attribute groups."""
    fixtures = fixture_map()
    inheritance = parse_express_document(
        fixtures["entity_inheritance"].source_bytes
    )
    derived = parse_express_document(fixtures["derived_attribute"].source_bytes)
    inverse = parse_express_document(fixtures["inverse_attribute"].source_bytes)

    product, part, assembly = inheritance.schemas[0].entities
    assert product.abstract
    assert "ONEOF" in str(product.supertype_expression)
    assert part.supertypes == ("product",)
    assert assembly.supertypes == ("product",)
    assert [item.kind for item in derived.schemas[0].entities[0].attributes] == [
        "explicit",
        "explicit",
        "derived",
    ]
    inverse_attribute = inverse.schemas[0].entities[0].attributes[0]
    assert inverse_attribute.kind == "inverse"
    assert inverse_attribute.type_ref.aggregate_kind == "SET"
    assert inverse_attribute.inverse_for == "owner"


def test_interfaces_constants_and_algorithm_envelopes_are_inspectable() -> None:
    """Schema-level constructs should be modeled without executing their meaning."""
    fixtures = fixture_map()
    imported = parse_express_document(fixtures["use_import"].source_bytes)
    constants = parse_express_document(fixtures["constant_block"].source_bytes)
    function = parse_express_document(fixtures["function_envelope"].source_bytes)
    rule = parse_express_document(fixtures["rule_envelope"].source_bytes)

    interface = imported.schemas[0].interfaces[0]
    assert interface.kind == "use"
    assert interface.items[0].alias == "local_item"
    assert [item.name for item in constants.schemas[0].constants] == [
        "default_count",
        "default_name",
    ]
    algorithm = function.schemas[0].algorithms[0]
    assert algorithm.kind == "function"
    assert algorithm.parameters[0].name == "value"
    assert "RETURN" in algorithm.body.upper()
    assert rule.schemas[0].algorithms[0].applies_to == ("item",)


def test_observation_reports_model_counts_and_deferred_semantics() -> None:
    """A syntax accept should keep semantic work explicitly deferred."""
    fixture = fixture_map()["unique_where"]
    result = inspect_express_schema(fixture.source_bytes)

    assert result.decision == "accept"
    assert result.entity_count == 1
    assert result.explicit_attribute_count == 1
    assert result.unique_rule_count == 1
    assert result.where_rule_count == 1
    assert result.exact_reconstruction
    assert result.type_checking == "not_attempted"
    assert result.rule_execution == "not_attempted"


def test_fixture_generation_is_byte_deterministic() -> None:
    """Repeated fixture construction should preserve bytes, limits, and digests."""
    first = build_express_schema_fixtures()
    second = build_express_schema_fixtures()

    assert [item.file_name for item in first] == [item.file_name for item in second]
    assert [item.source_bytes for item in first] == [item.source_bytes for item in second]
    assert [item.limits for item in first] == [item.limits for item in second]
    assert [hashlib.sha256(item.source_bytes).hexdigest() for item in first] == [
        hashlib.sha256(item.source_bytes).hexdigest() for item in second
    ]


def test_public_entry_points_validate_types_and_limits() -> None:
    """Invalid public inputs should fail before tokenization or parsing."""
    with pytest.raises(TypeError, match="source_bytes"):
        lex_express("not bytes")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="limits"):
        parse_express_document(b"", limits=object())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="source_bytes"):
        inspect_express_schema("not bytes")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="max_tokens"):
        ExpressParseLimits(max_tokens=0)
    limited = inspect_express_schema(
        b"SCHEMA first; END_SCHEMA; SCHEMA second; END_SCHEMA;",
        limits=ExpressParseLimits(max_declarations=1),
    )
    assert limited.decision == "quarantine"
    assert limited.reason_code == "declaration_count_limit"
    nested_type = inspect_express_schema(
        b"SCHEMA demo; TYPE nested = LIST OF LIST OF STRING; END_TYPE; END_SCHEMA;",
        limits=ExpressParseLimits(max_nesting_depth=1),
    )
    assert nested_type.decision == "quarantine"
    assert nested_type.reason_code == "nesting_limit"
