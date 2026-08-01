"""Controlled fixtures and observations for the unified Part 21 source model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from research_notes.step_brep import build_step_brep_fixtures
from research_notes.step_part21 import (
    DEFAULT_STEP_PARSE_LIMITS,
    STEPParseLimits,
    Part21ParseError,
    parse_part21_document,
)


@dataclass(frozen=True)
class STEPSourceModelInspection:
    """One staged syntax decision with source-preservation evidence."""

    decision: Literal["accept", "quarantine", "reject"]
    reason_code: str
    syntactically_parsed: bool
    exact_source_reconstruction: bool
    source_bytes: int
    source_characters: int
    token_count: int
    significant_token_count: int
    trivia_token_count: int
    comment_count: int
    header_record_count: int
    data_section_count: int
    entity_count: int
    simple_entity_count: int
    complex_entity_count: int
    reference_count: int
    diagnostic_line: int | None
    diagnostic_column: int | None
    schema_conformance: Literal["not_evaluated"] = "not_evaluated"


@dataclass(frozen=True)
class STEPSourceModelFixture:
    """One deterministic source-model fixture and its bounded expectation."""

    fixture: str
    condition: str
    file_name: str
    expected_decision: Literal["accept", "quarantine", "reject"]
    expected_reason_code: str
    limits: STEPParseLimits
    source_bytes: bytes


def inspect_part21_source_model(
    source_bytes: bytes,
    *,
    limits: STEPParseLimits = DEFAULT_STEP_PARSE_LIMITS,
) -> STEPSourceModelInspection:
    """Inspect syntax and exact source retention without schema validation."""
    if not isinstance(source_bytes, bytes):
        raise TypeError("source_bytes must be bytes")
    if not isinstance(limits, STEPParseLimits):
        raise TypeError("limits must be STEPParseLimits")
    try:
        document = parse_part21_document(source_bytes, limits=limits)
    except Part21ParseError as error:
        return STEPSourceModelInspection(
            decision=error.decision,
            reason_code=error.reason_code,
            syntactically_parsed=False,
            exact_source_reconstruction=False,
            source_bytes=len(source_bytes),
            source_characters=0,
            token_count=0,
            significant_token_count=0,
            trivia_token_count=0,
            comment_count=0,
            header_record_count=0,
            data_section_count=0,
            entity_count=0,
            simple_entity_count=0,
            complex_entity_count=0,
            reference_count=0,
            diagnostic_line=(error.span.start_line if error.span else None),
            diagnostic_column=(
                error.span.start_column if error.span else None
            ),
        )

    tokens = document.tokens
    return STEPSourceModelInspection(
        decision="accept",
        reason_code="source_model_parsed",
        syntactically_parsed=True,
        exact_source_reconstruction=(
            document.reconstruct_source() == document.source_text
            and document.source_text.encode("utf-8") == source_bytes
        ),
        source_bytes=len(source_bytes),
        source_characters=len(document.source_text),
        token_count=len(tokens),
        significant_token_count=len(document.significant_tokens),
        trivia_token_count=sum(token.is_trivia for token in tokens),
        comment_count=sum(token.kind == "COMMENT" for token in tokens),
        header_record_count=len(document.header_records),
        data_section_count=len(document.data_sections),
        entity_count=len(document.entities),
        simple_entity_count=sum(not entity.is_complex for entity in document.entities),
        complex_entity_count=sum(entity.is_complex for entity in document.entities),
        reference_count=document.reference_count,
        diagnostic_line=None,
        diagnostic_column=None,
    )


def build_step_source_model_fixtures() -> tuple[STEPSourceModelFixture, ...]:
    """Build deterministic positive and fail-closed v0.23 fixtures."""
    geometry_control = next(
        fixture.step_bytes
        for fixture in build_step_brep_fixtures()
        if fixture.fixture == "closed_tetrahedron"
    )
    nesting_limits = STEPParseLimits(max_nesting_depth=8)
    token_limits = STEPParseLimits(max_token_chars=48)
    return (
        STEPSourceModelFixture(
            "geometry_control",
            "v021_closed_tetrahedron_through_unified_parser",
            "geometry_control.step",
            "accept",
            "source_model_parsed",
            DEFAULT_STEP_PARSE_LIMITS,
            geometry_control,
        ),
        STEPSourceModelFixture(
            "trivia_preservation",
            "whitespace_comments_and_escaped_apostrophe",
            "trivia_preservation.step",
            "accept",
            "source_model_parsed",
            DEFAULT_STEP_PARSE_LIMITS,
            _exchange(
                "/* DATA-leading comment */\n"
                "DATA;\n"
                "#1 = ITEM(/* parameter comment */ 'O''Brien', (1, 2.5, .TRUE., $, *));\n"
                "ENDSEC;"
            ),
        ),
        STEPSourceModelFixture(
            "utf8_coordinates",
            "utf8_byte_and_character_offsets_diverge",
            "utf8_coordinates.step",
            "accept",
            "source_model_parsed",
            DEFAULT_STEP_PARSE_LIMITS,
            _exchange(
                "DATA;\n#1=LABEL('café 測定面');\n#2=USE(#1);\nENDSEC;"
            ),
        ),
        STEPSourceModelFixture(
            "simple_and_complex",
            "simple_and_subsuper_records_share_one_grammar",
            "simple_and_complex.step",
            "accept",
            "source_model_parsed",
            DEFAULT_STEP_PARSE_LIMITS,
            _exchange(
                "DATA;\n"
                "#1=ITEM('simple');\n"
                "#2=(REPRESENTATION_ITEM('complex') CURVE());\n"
                "ENDSEC;"
            ),
        ),
        STEPSourceModelFixture(
            "forward_reference",
            "reference_precedes_target_definition",
            "forward_reference.step",
            "accept",
            "source_model_parsed",
            DEFAULT_STEP_PARSE_LIMITS,
            _exchange("DATA;\n#1=USE(#2);\n#2=ITEM('target');\nENDSEC;"),
        ),
        STEPSourceModelFixture(
            "missing_semicolon",
            "entity_terminator_is_missing",
            "missing_semicolon.step",
            "reject",
            "unexpected_token",
            DEFAULT_STEP_PARSE_LIMITS,
            _exchange("DATA;\n#1=ITEM('broken')\nENDSEC;"),
        ),
        STEPSourceModelFixture(
            "unterminated_comment",
            "comment_reaches_end_of_file",
            "unterminated_comment.step",
            "reject",
            "unterminated_comment",
            DEFAULT_STEP_PARSE_LIMITS,
            _exchange("DATA;\n#1=ITEM('before');\n/* never closed"),
        ),
        STEPSourceModelFixture(
            "nesting_limit",
            "aggregate_depth_exceeds_explicit_budget",
            "nesting_limit.step",
            "quarantine",
            "nesting_depth_limit",
            nesting_limits,
            _exchange(
                "DATA;\n#1=NESTED("
                + "(" * 10
                + "1"
                + ")" * 10
                + ");\nENDSEC;"
            ),
        ),
        STEPSourceModelFixture(
            "token_length_limit",
            "one_string_exceeds_explicit_budget",
            "token_length_limit.step",
            "quarantine",
            "token_length_limit",
            token_limits,
            _exchange("DATA;\n#1=ITEM('" + "x" * 49 + "');\nENDSEC;"),
        ),
        STEPSourceModelFixture(
            "invalid_utf8",
            "source_contains_invalid_utf8_octets",
            "invalid_utf8.step",
            "reject",
            "invalid_utf8",
            DEFAULT_STEP_PARSE_LIMITS,
            _exchange("DATA;\n#1=ITEM('valid');\nENDSEC;") + b"\xff",
        ),
    )


def _exchange(body: str) -> bytes:
    return (
        "ISO-10303-21;\n"
        "HEADER;\n"
        "FILE_DESCRIPTION(('Controlled source-model fixture'),'4;1');\n"
        "FILE_NAME('fixture.step','2026-01-01T00:00:00',"
        "('research-notes'),('research-notes'),'','','');\n"
        "FILE_SCHEMA(('DEMO_SCHEMA'));\n"
        "ENDSEC;\n"
        f"{body}\n"
        "END-ISO-10303-21;\n"
    ).encode("utf-8")
