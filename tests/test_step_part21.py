"""Tests for the unified source-preserving Part 21 parser foundation."""

from __future__ import annotations

import hashlib

import pytest

from research_notes import (
    STEPParseLimits,
    build_step_source_model_fixtures,
    inspect_part21_source_model,
    lex_part21,
    parse_part21_document,
)


def fixture_map() -> dict[str, object]:
    """Return source-model fixtures keyed by stable names."""
    return {
        fixture.fixture: fixture
        for fixture in build_step_source_model_fixtures()
    }


def test_all_source_model_expectations_are_met() -> None:
    """Every controlled grammar and resource-boundary fixture should match."""
    fixtures = build_step_source_model_fixtures()

    assert len(fixtures) == 10
    for fixture in fixtures:
        result = inspect_part21_source_model(
            fixture.source_bytes, limits=fixture.limits
        )
        assert result.decision == fixture.expected_decision
        assert result.reason_code == fixture.expected_reason_code
        assert result.schema_conformance == "not_evaluated"


def test_complete_token_stream_reconstructs_exact_source() -> None:
    """Raw token spellings and spans should retain every decoded character."""
    fixture = fixture_map()["trivia_preservation"]
    document = parse_part21_document(fixture.source_bytes)

    assert document.reconstruct_source() == document.source_text
    assert document.source_text.encode("utf-8") == fixture.source_bytes
    assert any(token.kind == "COMMENT" for token in document.tokens)
    assert any(token.kind == "WHITESPACE" for token in document.tokens)
    for token in document.tokens:
        assert document.source_slice(token.span) == token.raw
        assert len(
            document.source_text[: token.span.start_offset].encode("utf-8")
        ) == token.span.start_byte


def test_utf8_spans_separate_character_and_byte_offsets() -> None:
    """Tokens after non-ASCII text should expose distinct byte coordinates."""
    fixture = fixture_map()["utf8_coordinates"]
    document = parse_part21_document(fixture.source_bytes)
    second_entity = next(
        token
        for token in document.significant_tokens
        if token.kind == "ENTITY_REFERENCE" and token.value == "#2"
    )

    assert second_entity.span.start_byte > second_entity.span.start_offset
    assert second_entity.span.start_line > 1
    assert second_entity.span.start_column == 1
    assert document.source_slice(document.entities[1].span).startswith("#2=USE")


def test_semantic_model_retains_simple_complex_and_forward_references() -> None:
    """One grammar should support both record forms and forward references."""
    fixtures = fixture_map()
    mixed = parse_part21_document(fixtures["simple_and_complex"].source_bytes)
    forward = parse_part21_document(fixtures["forward_reference"].source_bytes)

    assert [entity.is_complex for entity in mixed.entities] == [False, True]
    assert [record.type_name for record in mixed.entities[1].records] == [
        "REPRESENTATION_ITEM",
        "CURVE",
    ]
    assert forward.reference_count == 1
    assert forward.entities[0].records[0].arguments[0].kind == "entity_reference"
    assert forward.entities[0].records[0].arguments[0].value == "#2"


def test_geometry_control_passes_unified_source_and_legacy_topology_paths() -> None:
    """The v0.21 shape should remain the integration control after refactoring."""
    from research_notes import inspect_step_brep, parse_step_exchange

    fixture = fixture_map()["geometry_control"]
    source = parse_part21_document(fixture.source_bytes)
    exchange = parse_step_exchange(fixture.source_bytes)
    topology = inspect_step_brep(fixture.source_bytes)

    assert len(source.entities) == len(exchange.entities) == 74
    assert source.reference_count == exchange.reference_count == 97
    assert topology.decision == "accept"
    assert (len(topology.faces), len(topology.edges)) == (4, 6)


def test_fail_closed_diagnostics_report_source_coordinates() -> None:
    """Localized syntax failures should include stable one-based coordinates."""
    fixtures = fixture_map()
    missing = inspect_part21_source_model(
        fixtures["missing_semicolon"].source_bytes
    )
    comment = inspect_part21_source_model(
        fixtures["unterminated_comment"].source_bytes
    )

    assert missing.diagnostic_line is not None
    assert missing.diagnostic_column is not None
    assert comment.diagnostic_line is not None
    assert comment.diagnostic_column == 1


def test_source_model_fixture_generation_is_deterministic() -> None:
    """Repeated generation should preserve bytes, limits, names, and hashes."""
    first = build_step_source_model_fixtures()
    second = build_step_source_model_fixtures()

    assert [fixture.file_name for fixture in first] == [
        fixture.file_name for fixture in second
    ]
    assert [fixture.limits for fixture in first] == [
        fixture.limits for fixture in second
    ]
    assert [fixture.source_bytes for fixture in first] == [
        fixture.source_bytes for fixture in second
    ]
    assert [hashlib.sha256(fixture.source_bytes).hexdigest() for fixture in first] == [
        hashlib.sha256(fixture.source_bytes).hexdigest() for fixture in second
    ]


def test_public_lexer_and_parser_validate_input_types() -> None:
    """Public source-model entry points should reject invalid argument types."""
    with pytest.raises(TypeError, match="source_bytes"):
        lex_part21("not bytes")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="limits"):
        parse_part21_document(b"", limits=object())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="max_tokens"):
        STEPParseLimits(max_tokens=0)
