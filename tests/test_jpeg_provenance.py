"""Tests for controlled field-level JPEG metadata provenance."""

import numpy as np

from research_notes import (
    FIELD_ORDER,
    apply_selective_metadata_policy,
    build_controlled_metadata_fixture,
    build_synthetic_rgb_profile,
    compare_decoded_pixels,
    decode_jpeg_pillow,
    encode_jpeg_opencv,
    encode_jpeg_pillow,
    extract_controlled_metadata_fields,
    metadata_state_sha256,
    strip_controlled_metadata,
)


def make_base_jpeg() -> bytes:
    """Return one deterministic synthetic 4:4:4 JPEG."""
    rows, columns = np.indices((80, 112))
    image = np.stack(
        (
            (columns * 3 + rows) % 256,
            (rows * 5 + columns // 2) % 256,
            ((rows + columns) * 2) % 256,
        ),
        axis=2,
    ).astype(np.uint8)
    return encode_jpeg_pillow(image, quality=75, chroma_sampling="444")


def make_fixture(variant: str) -> bytes:
    """Build one controlled metadata layout."""
    return build_controlled_metadata_fixture(
        make_base_jpeg(),
        icc_profile=build_synthetic_rgb_profile(2.2),
        variant=variant,  # type: ignore[arg-type]
    )


def reencode_with_opencv(source: bytes) -> bytes:
    """Decode through Pillow and re-encode through OpenCV."""
    return encode_jpeg_opencv(
        decode_jpeg_pillow(source),
        quality=75,
        chroma_sampling="444",
    )


def field_hashes(jpeg_bytes: bytes) -> dict[str, str]:
    """Return normalized field hashes keyed by field identifier."""
    return {
        field.field_id: field.value_sha256
        for field in extract_controlled_metadata_fields(jpeg_bytes)
    }


def test_equivalent_layouts_have_the_same_normalized_fields() -> None:
    canonical = make_fixture("canonical_order")
    reordered = make_fixture("reordered_equivalent")

    assert canonical != reordered
    assert strip_controlled_metadata(canonical) == strip_controlled_metadata(
        reordered
    )
    assert field_hashes(canonical) == field_hashes(reordered)
    assert tuple(field_hashes(canonical)) == FIELD_ORDER
    assert metadata_state_sha256(canonical) == metadata_state_sha256(reordered)


def test_location_denylist_retains_unclassified_fields() -> None:
    source = make_fixture("canonical_order")
    result = apply_selective_metadata_policy(
        source,
        reencode_with_opencv(source),
        "drop_location_denylist",
    )
    retained = {
        decision.field_id
        for decision in result.decisions
        if decision.retained
    }

    assert "xmp.exif_gps_latitude" not in retained
    assert "xmp.exif_gps_longitude" not in retained
    assert "xmp.synthetic_pipeline_hint" in retained
    assert "app13.opaque" in retained
    assert all(
        decision.semantic_value_exact
        for decision in result.decisions
        if decision.retained
    )


def test_visual_allowlist_keeps_only_interpretation_fields() -> None:
    source = make_fixture("canonical_order")
    result = apply_selective_metadata_policy(
        source,
        reencode_with_opencv(source),
        "allow_visual_context",
    )
    retained = {
        decision.field_id
        for decision in result.decisions
        if decision.retained
    }

    assert retained == {"exif.orientation", "icc.profile"}
    assert field_hashes(result.output_bytes) == {
        field_id: field_hashes(source)[field_id]
        for field_id in retained
    }


def test_policy_is_metadata_only_and_canonicalizes_layout() -> None:
    canonical = make_fixture("canonical_order")
    reordered = make_fixture("reordered_equivalent")
    canonical_reencoded = reencode_with_opencv(canonical)
    reordered_reencoded = reencode_with_opencv(reordered)
    first = apply_selective_metadata_policy(
        canonical, canonical_reencoded, "allow_catalog"
    )
    second = apply_selective_metadata_policy(
        reordered, reordered_reencoded, "allow_catalog"
    )

    assert canonical_reencoded == reordered_reencoded
    assert first.output_bytes == second.output_bytes
    assert strip_controlled_metadata(first.output_bytes) == canonical_reencoded
    difference = compare_decoded_pixels(
        decode_jpeg_pillow(canonical_reencoded),
        decode_jpeg_pillow(first.output_bytes),
    )
    assert difference.exact
