"""Tests for controlled metadata-family and relationship coverage."""

from __future__ import annotations

import numpy as np
import pytest

from research_notes import (
    build_metadata_coverage_fixtures,
    encode_jpeg_pillow,
    inspect_jpeg_metadata_coverage,
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
    """Return controlled inspection results by fixture name."""
    return {
        fixture.fixture: inspect_jpeg_metadata_coverage(fixture.jpeg_bytes)
        for fixture in build_metadata_coverage_fixtures(make_base_jpeg())
    }


def test_fixture_expectations_are_met() -> None:
    """Every controlled fixture should reach its declared routing state."""
    fixtures = build_metadata_coverage_fixtures(make_base_jpeg())

    assert len(fixtures) == 15
    for fixture in fixtures:
        result = inspect_jpeg_metadata_coverage(fixture.jpeg_bytes)
        assert result.decision == fixture.expected_decision
        assert result.reason_code == fixture.expected_reason_code


def test_nested_payloads_are_resolved_without_semantic_overclaim() -> None:
    """The mixed fixture should resolve links but keep maker notes opaque."""
    result = fixture_results()["mixed_nested_complete"]

    assert result.accepted
    assert result.relationships_declared == 4
    assert result.relationships_resolved == 4
    assert result.relationship_completion_rate == 1.0
    assert result.exif_thumbnails == 1
    assert result.maker_notes == 1
    assert result.opaque_components == 1
    assert result.standard_xmp_packets == 1
    assert result.extended_xmp_chunks == 2
    assert result.iptc_iim_datasets == 3


def test_extended_xmp_order_is_not_a_semantic_dependency() -> None:
    """Chunk order should not change complete GUID-based reconstruction."""
    results = fixture_results()
    in_order = results["extended_xmp_in_order"]
    out_of_order = results["extended_xmp_out_of_order"]

    assert in_order.accepted and out_of_order.accepted
    assert in_order.extended_xmp_bytes == out_of_order.extended_xmp_bytes
    assert in_order.relationships_resolved == out_of_order.relationships_resolved


def test_incomplete_and_ambiguous_relations_fail_closed() -> None:
    """Missing, duplicate, orphaned, and out-of-bounds links quarantine."""
    results = fixture_results()
    expected = {
        "exif_thumbnail_out_of_bounds": "exif_thumbnail_out_of_bounds",
        "maker_note_out_of_bounds": "maker_note_out_of_bounds",
        "extended_xmp_missing_chunk": "extended_xmp_incomplete",
        "extended_xmp_duplicate_chunk": "extended_xmp_duplicate_offset",
        "extended_xmp_orphan": "extended_xmp_orphan",
        "extended_xmp_guid_mismatch": "extended_xmp_missing",
        "iptc_iim_truncated_dataset": "iptc_iim_dataset_overrun",
    }
    for fixture, reason in expected.items():
        assert results[fixture].decision == "quarantine"
        assert results[fixture].reason_code == reason


def test_maker_note_presence_is_not_interpreted_as_trust() -> None:
    """A bounded maker note remains an explicitly opaque component."""
    result = fixture_results()["maker_note_opaque"]

    assert result.accepted
    assert result.families == ("maker_note",)
    assert result.opaque_components == 1
    assert result.maker_note_bytes > 0


def test_public_input_validation() -> None:
    """The public parser and fixture builder should validate input types."""
    with pytest.raises(TypeError, match="jpeg_bytes"):
        inspect_jpeg_metadata_coverage(bytearray(b"\xff\xd8"))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="base_jpeg"):
        build_metadata_coverage_fixtures(b"")
