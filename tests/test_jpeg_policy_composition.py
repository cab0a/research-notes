"""Tests for explainable JPEG policy composition."""

from __future__ import annotations

import numpy as np
import pytest

from research_notes import (
    JPEG_INTAKE_POLICIES,
    JPEGIntakePolicy,
    apply_explainable_jpeg_policy,
    build_policy_composition_fixtures,
    build_synthetic_rgb_profile,
    encode_jpeg_pillow,
)


def make_base_jpeg() -> bytes:
    """Return one deterministic metadata-free JPEG carrier."""
    rows, columns = np.indices((48, 64), dtype=np.uint16)
    image = np.stack(
        (
            (columns * 3 + rows) % 256,
            (rows * 5 + columns) % 256,
            ((rows // 6 + columns // 8) % 2) * 180 + 35,
        ),
        axis=2,
    ).astype(np.uint8)
    return encode_jpeg_pillow(image, quality=75, chroma_sampling="444")


def all_results() -> dict[tuple[str, str], object]:
    """Evaluate all fixture and policy combinations."""
    base = make_base_jpeg()
    fixtures = build_policy_composition_fixtures(
        base, icc_profile=build_synthetic_rgb_profile(2.2)
    )
    return {
        (fixture.fixture, policy.name): apply_explainable_jpeg_policy(
            fixture.jpeg_bytes, base, policy
        )
        for fixture in fixtures
        for policy in JPEG_INTAKE_POLICIES
    }


def test_all_fixture_policy_expectations_are_met() -> None:
    """Every fixture and profile should reach its declared terminal reason."""
    base = make_base_jpeg()
    fixtures = build_policy_composition_fixtures(
        base, icc_profile=build_synthetic_rgb_profile(2.2)
    )

    assert len(fixtures) == 9
    assert len(JPEG_INTAKE_POLICIES) == 4
    for fixture in fixtures:
        for policy in JPEG_INTAKE_POLICIES:
            result = apply_explainable_jpeg_policy(
                fixture.jpeg_bytes, base, policy
            )
            assert result.decision == fixture.expected_decision(policy.name)
            assert result.reason_code == fixture.expected_reason_code(
                policy.name
            )


def test_every_trace_has_one_decisive_terminal_step() -> None:
    """Ordered explanations should end at exactly one decisive rule."""
    for result in all_results().values():
        decisive = [step for step in result.trace if step.decisive]
        assert len(decisive) == 1
        assert result.trace[-1] == decisive[0]
        assert decisive[0].reason_code == result.reason_code


def test_stage_precedence_attributes_failures_to_first_boundary() -> None:
    """Resource, coverage, and integrity failures should remain attributable."""
    results = all_results()

    resource = results[("resource_over_budget", "open_catalog")]
    assert [step.stage for step in resource.trace] == ["resource"]
    assert resource.decision == "quarantine"

    coverage = results[("incomplete_relationship", "open_catalog")]
    assert [step.stage for step in coverage.trace] == ["resource", "coverage"]

    integrity = results[("stale_assertion", "open_catalog")]
    assert [step.stage for step in integrity.trace] == [
        "resource",
        "coverage",
        "opacity",
        "integrity",
    ]


def test_clean_input_differs_by_declared_profile() -> None:
    """The same unsigned input should expose each profile's policy choice."""
    results = all_results()

    assert results[("clean_unsigned", "open_catalog")].decision == "accept"
    assert results[("clean_unsigned", "privacy_review")].decision == "sanitize"
    assert results[("clean_unsigned", "verified_archive")].reason_code == (
        "integrity_required_missing"
    )
    assert results[("clean_unsigned", "minimal_export")].decision == "sanitize"


def test_sanitization_records_field_and_assertion_changes() -> None:
    """Selective and minimal outputs should expose retained field counts."""
    results = all_results()

    privacy = results[("clean_valid_assertion", "privacy_review")]
    assert privacy.source_field_count == 6
    assert privacy.retained_field_count == 2
    assert privacy.integrity_status_before == "valid_binding"
    assert privacy.integrity_status_after == "missing_assertion"
    assert privacy.emitted

    minimal = results[("clean_valid_assertion", "minimal_export")]
    assert minimal.source_field_count == 6
    assert minimal.retained_field_count == 0
    assert minimal.integrity_status_after == "missing_assertion"


def test_opaque_metadata_is_allowed_quarantined_or_stripped_explicitly() -> None:
    """Profiles should not share an implicit treatment of opaque bytes."""
    results = all_results()

    assert results[("opaque_valid_assertion", "open_catalog")].decision == "accept"
    assert results[("opaque_valid_assertion", "privacy_review")].reason_code == (
        "opaque_metadata_quarantined"
    )
    minimal = results[("opaque_valid_assertion", "minimal_export")]
    assert minimal.decision == "sanitize"
    assert minimal.opaque_component_count == 1


def test_public_input_validation() -> None:
    """The public policy boundary should reject invalid inputs and profiles."""
    base = make_base_jpeg()
    with pytest.raises(TypeError, match="source_jpeg"):
        apply_explainable_jpeg_policy(bytearray(base), base, JPEG_INTAKE_POLICIES[0])  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="reencoded_jpeg"):
        apply_explainable_jpeg_policy(base, b"", JPEG_INTAKE_POLICIES[0])
    with pytest.raises(TypeError, match="policy"):
        apply_explainable_jpeg_policy(base, base, object())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="icc_profile"):
        build_policy_composition_fixtures(base, icc_profile=b"")
    assert isinstance(JPEG_INTAKE_POLICIES[0], JPEGIntakePolicy)
