"""Tests for controlled JPEG transform-integrity assertions."""

from __future__ import annotations

import numpy as np
import pytest

from research_notes import (
    attach_transform_integrity_assertion,
    build_synthetic_rgb_profile,
    build_transform_integrity_fixtures,
    encode_jpeg_pillow,
    image_core_sha256,
    integrity_assertion_sha256,
    strip_transform_integrity_assertions,
    verify_transform_integrity_assertion,
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


def fixture_results() -> dict[str, object]:
    """Return controlled integrity results by fixture name."""
    return {
        fixture.fixture: verify_transform_integrity_assertion(
            fixture.jpeg_bytes
        )
        for fixture in build_transform_integrity_fixtures(
            make_base_jpeg(), icc_profile=build_synthetic_rgb_profile(2.2)
        )
    }


def test_fixture_expectations_are_met() -> None:
    """Every transform should reach its declared integrity status."""
    fixtures = build_transform_integrity_fixtures(
        make_base_jpeg(), icc_profile=build_synthetic_rgb_profile(2.2)
    )

    assert len(fixtures) == 11
    for fixture in fixtures:
        result = verify_transform_integrity_assertion(fixture.jpeg_bytes)
        assert result.status == fixture.expected_status
        assert result.reason_code == fixture.expected_reason_code


def test_equivalent_metadata_reordering_preserves_declared_scopes() -> None:
    """Byte reordering alone should not invalidate normalized scopes."""
    result = fixture_results()["metadata_reordered_inherited"]

    assert result.valid
    assert result.status == "valid_binding"
    assert result.mismatching_bindings == ()
    assert set(result.matching_bindings) == {
        "image_core_sha256",
        "metadata_state_sha256",
        "decoded_pixels_sha256",
    }


def test_inherited_assertions_expose_transform_specific_mismatches() -> None:
    """Sanitization and re-encoding should invalidate different scopes."""
    results = fixture_results()

    sanitized = results["metadata_sanitized_inherited"]
    assert sanitized.mismatching_bindings == ("metadata_state_sha256",)

    reencoded = results["reencoded_inherited"]
    assert reencoded.mismatching_bindings == (
        "image_core_sha256",
        "decoded_pixels_sha256",
    )
    modified = results["pixel_modified_inherited"]
    assert modified.mismatching_bindings == (
        "image_core_sha256",
        "decoded_pixels_sha256",
    )


def test_renewed_assertions_bind_current_output_and_declare_parent() -> None:
    """A renewed output record should match while retaining a parent digest."""
    results = fixture_results()
    for fixture in ("metadata_sanitized_renewed", "reencoded_renewed"):
        result = results[fixture]
        assert result.status == "valid_derived_binding"
        assert result.valid
        assert len(result.parent_assertion_sha256) == 64
        assert not result.mismatching_bindings


def test_missing_malformed_duplicate_and_tampered_are_distinct() -> None:
    """Assertion presence, syntax, multiplicity, and digest mismatch differ."""
    results = fixture_results()

    assert results["manifest_missing"].status == "missing_assertion"
    assert results["manifest_json_malformed"].status == "malformed_assertion"
    assert results["manifest_duplicate"].status == "multiple_assertions"
    tampered = results["manifest_digest_tampered"]
    assert tampered.status == "stale_binding"
    assert tampered.mismatching_bindings == ("metadata_state_sha256",)


def test_attachment_is_external_to_its_bound_scopes() -> None:
    """Adding or removing the assertion should not change the image core."""
    base = make_base_jpeg()
    asserted = attach_transform_integrity_assertion(base, action="created")

    assert image_core_sha256(asserted) == image_core_sha256(base)
    assert strip_transform_integrity_assertions(asserted) == base
    assert len(integrity_assertion_sha256(asserted)) == 64


def test_public_input_validation() -> None:
    """Public helpers should reject invalid JPEG and parent declarations."""
    with pytest.raises(TypeError, match="jpeg_bytes"):
        verify_transform_integrity_assertion(b"")
    with pytest.raises(ValueError, match="non-empty"):
        attach_transform_integrity_assertion(make_base_jpeg(), action="")
    with pytest.raises(ValueError, match="parent_assertion"):
        attach_transform_integrity_assertion(
            make_base_jpeg(), action="derived", parent_assertion_sha256="bad"
        )
