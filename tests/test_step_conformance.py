"""Tests for controlled Part 21 edition and syntax conformance."""

from __future__ import annotations

import hashlib

import pytest

from research_notes import (
    STEPArchiveLimits,
    build_part21_conformance_fixtures,
    inspect_part21_conformance,
    parse_part21_document,
)


def fixture_map() -> dict[str, object]:
    """Return v0.24 fixtures keyed by stable names."""
    return {
        fixture.fixture: fixture
        for fixture in build_part21_conformance_fixtures()
    }


def test_all_conformance_fixture_expectations_are_met() -> None:
    """Every controlled edition, syntax, and archive decision should match."""
    fixtures = build_part21_conformance_fixtures()

    assert len(fixtures) == 34
    for fixture in fixtures:
        result = inspect_part21_conformance(fixture.source_bytes)
        assert result.decision == fixture.expected_decision, fixture.fixture
        assert result.reason_code == fixture.expected_reason_code, fixture.fixture
        assert result.declared_edition == fixture.expected_declared_edition, fixture.fixture
        assert result.required_edition == fixture.expected_required_edition, fixture.fixture
        assert result.schema_conformance == "not_evaluated"


def test_edition_profiles_separate_declared_and_required_capabilities() -> None:
    """Edition 1, 2, and 3 fixtures should expose different feature floors."""
    fixtures = fixture_map()
    edition1 = inspect_part21_conformance(
        fixtures["edition1_minimal"].source_bytes
    )
    edition2 = inspect_part21_conformance(
        fixtures["edition2_multiple_data"].source_bytes
    )
    edition3 = inspect_part21_conformance(
        fixtures["edition3_reference"].source_bytes
    )

    assert (edition1.declared_edition, edition1.required_edition) == (1, 1)
    assert (edition2.declared_edition, edition2.required_edition) == (2, 2)
    assert "multiple_data_sections" in edition2.features
    assert (edition3.declared_edition, edition3.required_edition) == (3, 3)
    assert edition3.required_conformance_class == 2
    assert "reference_section" in edition3.features


def test_direct_utf8_and_legacy_controls_normalize_to_the_same_text() -> None:
    """Direct UTF-8 and edition-compatible X2 controls should remain distinct."""
    fixtures = fixture_map()
    legacy = parse_part21_document(
        fixtures["edition1_legacy_x2"].source_bytes
    )
    direct = parse_part21_document(fixtures["edition3_utf8"].source_bytes)

    legacy_label = legacy.entities[0].records[0].arguments[0]
    direct_label = direct.entities[0].records[0].arguments[0]
    assert legacy_label.value == "café"
    assert "測定面" in str(direct_label.value)
    assert "\\X2\\" in legacy.source_slice(legacy_label.span)
    assert "direct_utf8" in inspect_part21_conformance(
        fixtures["edition3_utf8"].source_bytes
    ).features

    controls = parse_part21_document(
        fixtures["edition1_legacy_controls"].source_bytes
    ).entities[0].records[0].arguments
    assert tuple(value.value for value in controls) == (
        "§",
        "🙂",
        "Ä",
        "linebreak",
        "pagebreak",
    )


def test_archive_is_read_in_memory_without_path_materialization() -> None:
    """A bounded root should parse while unsafe archive paths fail closed."""
    fixtures = fixture_map()
    valid = inspect_part21_conformance(fixtures["zip_root"].source_bytes)
    unsafe = inspect_part21_conformance(
        fixtures["zip_unsafe_path"].source_bytes
    )

    assert valid.container == "zip"
    assert valid.archive_entry_count == 1
    assert valid.entity_count == 1
    assert unsafe.decision == "reject"
    assert unsafe.reason_code == "archive_unsafe_path"


def test_fixture_generation_is_byte_deterministic() -> None:
    """Repeated generation should preserve names, bytes, and SHA-256 values."""
    first = build_part21_conformance_fixtures()
    second = build_part21_conformance_fixtures()

    assert [fixture.file_name for fixture in first] == [
        fixture.file_name for fixture in second
    ]
    assert [fixture.source_bytes for fixture in first] == [
        fixture.source_bytes for fixture in second
    ]
    assert [hashlib.sha256(fixture.source_bytes).hexdigest() for fixture in first] == [
        hashlib.sha256(fixture.source_bytes).hexdigest() for fixture in second
    ]


def test_archive_limits_and_public_types_are_validated() -> None:
    """Archive budgets and public input types should fail explicitly."""
    with pytest.raises(ValueError, match="max_entries"):
        STEPArchiveLimits(max_entries=0)
    with pytest.raises(TypeError, match="source_bytes"):
        inspect_part21_conformance("not bytes")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="archive_limits"):
        inspect_part21_conformance(b"", archive_limits=object())  # type: ignore[arg-type]
