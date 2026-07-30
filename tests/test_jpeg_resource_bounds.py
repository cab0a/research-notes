"""Tests for resource-bounded JPEG metadata admission decisions."""

from __future__ import annotations

import numpy as np
import pytest

from research_notes import (
    DEFAULT_JPEG_METADATA_RESOURCE_BUDGET,
    JPEGMetadataResourceBudget,
    audit_jpeg_metadata_resources,
    boundary_limit_value,
    boundary_observed_and_admitted,
    build_resource_boundary_fixtures,
    encode_jpeg_pillow,
    make_jpeg_app_segment,
)


def make_base_jpeg() -> bytes:
    """Return one deterministic metadata-free synthetic JPEG carrier."""
    rows, columns = np.indices((48, 64), dtype=np.uint16)
    image = np.stack(
        (
            (columns * 3 + rows) % 256,
            (rows * 5 + columns) % 256,
            ((rows // 6 + columns // 8) % 2) * 180 + 35,
        ),
        axis=2,
    ).astype(np.uint8)
    return encode_jpeg_pillow(
        image, quality=75, chroma_sampling="444"
    )


def fixture_results() -> dict[str, object]:
    """Return the controlled fixture audit results by fixture name."""
    budget = DEFAULT_JPEG_METADATA_RESOURCE_BUDGET
    return {
        fixture.fixture: audit_jpeg_metadata_resources(
            fixture.jpeg_bytes, budget
        )
        for fixture in build_resource_boundary_fixtures(
            make_base_jpeg(), budget
        )
    }


def test_controlled_fixture_expectations_are_met() -> None:
    """Every synthetic fixture should reach its declared routing decision."""
    budget = DEFAULT_JPEG_METADATA_RESOURCE_BUDGET
    fixtures = build_resource_boundary_fixtures(make_base_jpeg(), budget)

    assert len(fixtures) == 24
    for fixture in fixtures:
        result = audit_jpeg_metadata_resources(
            fixture.jpeg_bytes, budget
        )
        assert result.decision == fixture.expected_decision
        assert result.reason_code == fixture.expected_reason_code


def test_at_limit_cases_pass_and_over_limit_cases_quarantine() -> None:
    """Equality is admitted while the first value above a limit fails closed."""
    budget = DEFAULT_JPEG_METADATA_RESOURCE_BUDGET
    fixtures = build_resource_boundary_fixtures(make_base_jpeg(), budget)

    paired = [
        fixture
        for fixture in fixtures
        if fixture.boundary_relation in ("at_limit", "over_limit")
    ]
    assert len(paired) == 20
    for fixture in paired:
        result = audit_jpeg_metadata_resources(
            fixture.jpeg_bytes, budget
        )
        observed, admitted = boundary_observed_and_admitted(
            result, fixture.resource_family
        )
        limit = boundary_limit_value(budget, fixture.resource_family)
        if fixture.boundary_relation == "at_limit":
            assert result.decision == "accept"
            assert observed == admitted == limit
        else:
            assert result.decision == "quarantine"
            assert observed > limit
            assert admitted <= limit


def test_admitted_work_counters_never_exceed_the_budget() -> None:
    """All fixture outcomes should preserve every declared work ceiling."""
    budget = DEFAULT_JPEG_METADATA_RESOURCE_BUDGET
    fixtures = build_resource_boundary_fixtures(make_base_jpeg(), budget)

    for fixture in fixtures:
        result = audit_jpeg_metadata_resources(
            fixture.jpeg_bytes, budget
        )
        assert result.header_segments_admitted <= budget.max_header_segments
        assert (
            result.metadata_segments_admitted
            <= budget.max_metadata_segments
        )
        assert result.metadata_bytes_admitted <= budget.max_metadata_bytes
        assert (
            result.largest_metadata_segment_admitted
            <= budget.max_single_metadata_segment_bytes
        )
        assert result.exif_entries_admitted <= budget.max_exif_entries
        assert (
            result.xmp_packet_bytes_admitted
            <= budget.max_xmp_packet_bytes
        )
        assert result.xmp_nodes_admitted <= budget.max_xmp_nodes
        assert result.xmp_depth_admitted <= budget.max_xmp_depth
        assert (
            result.xmp_text_bytes_admitted
            <= budget.max_xmp_text_bytes
        )
        assert result.icc_chunks_admitted <= budget.max_icc_chunks


def test_routing_states_separate_admission_quarantine_and_rejection() -> None:
    """Metadata policy failures and container failures remain distinct."""
    results = fixture_results()

    accepted = results["baseline_mixed_metadata"]
    unsafe_xmp = results["xmp_prohibited_doctype"]
    malformed = results["segment_length_overrun"]

    assert accepted.accepted
    assert accepted.header_scan_complete
    assert accepted.image_data_reached
    assert unsafe_xmp.decision == "quarantine"
    assert not unsafe_xmp.header_scan_complete
    assert not unsafe_xmp.image_data_reached
    assert malformed.decision == "reject"
    assert malformed.issue_codes == ("segment_overrun",)


def test_incomplete_icc_topology_is_quarantined_after_header_scan() -> None:
    """A bounded chunk count does not imply a complete ICC profile."""
    base = make_base_jpeg()
    incomplete = make_jpeg_app_segment(
        2, b"ICC_PROFILE\x00" + bytes((1, 2)) + b"first"
    )
    source = base[:2] + incomplete + base[2:]

    result = audit_jpeg_metadata_resources(source)

    assert result.decision == "quarantine"
    assert result.reason_code == "icc_missing_sequence"
    assert result.icc_chunks_admitted == 1


def test_invalid_xmp_is_quarantined_without_decoder_admission() -> None:
    """A small malformed packet remains a metadata failure, not a reject."""
    base = make_base_jpeg()
    invalid = make_jpeg_app_segment(
        1,
        b"http://ns.adobe.com/xap/1.0/\x00"
        b"<root><unclosed></root>",
    )

    result = audit_jpeg_metadata_resources(
        base[:2] + invalid + base[2:]
    )

    assert result.decision == "quarantine"
    assert result.reason_code == "xmp_xml_invalid"
    assert result.metadata_bytes_admitted == len(invalid) - 4


def test_budget_and_input_types_are_validated() -> None:
    """Public boundaries should reject invalid configuration and input types."""
    with pytest.raises(ValueError, match="positive"):
        JPEGMetadataResourceBudget(max_xmp_nodes=0)
    with pytest.raises(TypeError, match="integer"):
        JPEGMetadataResourceBudget(max_icc_chunks=True)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="jpeg_bytes"):
        audit_jpeg_metadata_resources(bytearray(b"\xff\xd8"))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="budget"):
        audit_jpeg_metadata_resources(b"\xff\xd8", object())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="base_jpeg"):
        build_resource_boundary_fixtures(b"")
