"""Tests for advanced Part 21 exchange structure boundaries."""

from __future__ import annotations

import hashlib

import pytest

from research_notes import (
    STEPParseLimits,
    build_step_exchange_fixtures,
    inspect_step_brep,
    inspect_step_exchange,
    parse_step_exchange,
)


def fixture_map() -> dict[str, object]:
    """Return advanced Part 21 fixtures keyed by stable names."""
    return {
        fixture.fixture: fixture for fixture in build_step_exchange_fixtures()
    }


def test_all_advanced_exchange_expectations_are_met() -> None:
    """Every controlled syntax and trust-boundary fixture should match."""
    fixtures = build_step_exchange_fixtures()

    assert len(fixtures) == 13
    for fixture in fixtures:
        result = inspect_step_exchange(fixture.source_bytes)
        assert result.decision == fixture.expected_decision
        assert result.reason_code == fixture.expected_reason_code
        if result.decision != "reject" and result.reason_code not in {
            "nesting_depth_limit",
            "archive_container_unsupported",
        }:
            assert result.data_section_count == fixture.expected_data_sections
            assert result.entity_count == fixture.expected_entities
            assert result.complex_entity_count == (
                fixture.expected_complex_entities
            )
            assert result.anchor_count == fixture.expected_anchors
            assert result.external_reference_count == (
                fixture.expected_external_references
            )
            assert result.signature_count == fixture.expected_signatures


def test_geometry_control_remains_a_resolved_closed_tetrahedron() -> None:
    """The viewable exchange control should retain the v0.21 topology."""
    fixture = fixture_map()["single_data_control"]
    exchange = inspect_step_exchange(fixture.source_bytes)
    topology = inspect_step_brep(fixture.source_bytes)

    assert exchange.decision == "accept"
    assert exchange.schema_identifiers == ("AUTOMOTIVE_DESIGN",)
    assert exchange.entity_count == 74
    assert topology.decision == "accept"
    assert (len(topology.faces), len(topology.edges)) == (4, 6)
    assert len(topology.solids) == 1
    assert sum(edge.is_free for edge in topology.edges) == 0


def test_multiple_data_sections_preserve_names_schemas_and_cross_reference() -> None:
    """Named sections should bind to FILE_SCHEMA and share occurrence scope."""
    fixture = fixture_map()["multiple_data_sections"]
    document = parse_step_exchange(fixture.source_bytes)
    result = inspect_step_exchange(fixture.source_bytes)

    assert [section.name for section in document.data_sections] == [
        "GEOMETRY",
        "ATTRIBUTES",
    ]
    assert [section.schema_identifier for section in document.data_sections] == [
        "DEMO_SCHEMA",
        "DEMO_SCHEMA",
    ]
    assert result.local_reference_count == 1
    assert result.unresolved_local_reference_count == 0


def test_complex_utf8_binary_and_anchor_forms_are_structurally_retained() -> None:
    """Advanced accepted forms should remain visible in the document model."""
    fixtures = fixture_map()
    complex_document = parse_step_exchange(
        fixtures["complex_entity_instance"].source_bytes
    )
    utf8_document = parse_step_exchange(fixtures["utf8_binary_values"].source_bytes)
    anchor_document = parse_step_exchange(fixtures["anchor_with_tag"].source_bytes)

    assert complex_document.entities[0].is_complex
    assert [
        record.type_name for record in complex_document.entities[0].records
    ] == ["REPRESENTATION_ITEM", "GEOMETRIC_REPRESENTATION_ITEM", "CURVE"]
    assert "測定面" in utf8_document.entities[0].records[0].arguments[0]
    assert anchor_document.anchors[0].name == "shape"
    assert anchor_document.anchors[0].tag_count == 1


def test_external_references_and_signatures_never_imply_validation() -> None:
    """Recognized trust-boundary syntax should remain quarantined and inert."""
    fixtures = fixture_map()
    external = inspect_step_exchange(fixtures["external_reference"].source_bytes)
    signature = inspect_step_exchange(fixtures["signature_present"].source_bytes)

    assert (external.decision, external.reason_code) == (
        "quarantine",
        "external_reference_unresolved",
    )
    assert external.external_resolution == "not_attempted"
    assert (signature.decision, signature.reason_code) == (
        "quarantine",
        "signature_unverified",
    )
    assert signature.signature_verification == "not_attempted"
    assert signature.signature_payload_bytes > 0
    assert signature.schema_conformance == "not_evaluated"


def test_invalid_structure_and_resource_limits_fail_closed() -> None:
    """Ambiguity, invalid tokens, depth excess, and archives should not pass."""
    fixtures = fixture_map()

    assert inspect_step_exchange(
        fixtures["duplicate_entity_across_sections"].source_bytes
    ).reason_code == "duplicate_entity_id"
    assert inspect_step_exchange(
        fixtures["unnamed_multiple_data"].source_bytes
    ).reason_code == "multiple_data_sections_require_names"
    assert inspect_step_exchange(
        fixtures["undeclared_data_schema"].source_bytes
    ).reason_code == "data_schema_not_declared"
    assert inspect_step_exchange(
        fixtures["invalid_binary"].source_bytes
    ).reason_code == "invalid_binary"
    assert inspect_step_exchange(
        fixtures["deep_nesting"].source_bytes
    ).reason_code == "nesting_depth_limit"
    archive = inspect_step_exchange(fixtures["zip_archive"].source_bytes)
    assert (archive.container, archive.reason_code) == (
        "zip",
        "archive_container_unsupported",
    )


def test_advanced_fixture_bytes_are_deterministic() -> None:
    """Repeated fixture construction should preserve names, bytes, and hashes."""
    first = build_step_exchange_fixtures()
    second = build_step_exchange_fixtures()

    assert [fixture.file_name for fixture in first] == [
        fixture.file_name for fixture in second
    ]
    assert [fixture.source_bytes for fixture in first] == [
        fixture.source_bytes for fixture in second
    ]
    assert [hashlib.sha256(fixture.source_bytes).hexdigest() for fixture in first] == [
        hashlib.sha256(fixture.source_bytes).hexdigest() for fixture in second
    ]


def test_advanced_public_input_validation() -> None:
    """The public parser should validate types and byte limits."""
    with pytest.raises(TypeError, match="source_bytes"):
        parse_step_exchange("not bytes")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="limits"):
        parse_step_exchange(b"", limits=object())  # type: ignore[arg-type]

    fixture = fixture_map()["single_data_control"]
    result = inspect_step_exchange(
        fixture.source_bytes,
        limits=STEPParseLimits(max_file_bytes=32),
    )
    assert (result.decision, result.reason_code) == (
        "quarantine",
        "file_size_limit",
    )
