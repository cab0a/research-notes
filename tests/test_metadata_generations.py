"""Tests for repeated JPEG metadata policy application."""

import numpy as np

from research_notes import (
    apply_jpeg_metadata_policy,
    audit_jpeg_metadata,
    decode_jpeg_pillow,
    encode_jpeg_opencv,
    encode_jpeg_pillow,
    inspect_jpeg_metadata,
    make_jpeg_app_segment,
)


def make_color_jpeg() -> bytes:
    """Return one deterministic synthetic 4:4:4 JPEG."""
    rows, columns = np.indices((72, 104))
    image = np.stack(
        (
            (columns * 3) % 256,
            (rows * 5) % 256,
            ((rows + columns) * 2) % 256,
        ),
        axis=2,
    ).astype(np.uint8)
    return encode_jpeg_pillow(image, quality=75, chroma_sampling="444")


def make_orientation_segment(value: int = 6) -> bytes:
    """Return one minimal big-endian EXIF Orientation APP1 segment."""
    payload = (
        b"Exif\x00\x00"
        + b"MM\x00*"
        + (8).to_bytes(4, "big")
        + (1).to_bytes(2, "big")
        + (274).to_bytes(2, "big")
        + (3).to_bytes(2, "big")
        + (1).to_bytes(4, "big")
        + value.to_bytes(2, "big")
        + b"\x00\x00"
        + b"\x00\x00\x00\x00"
    )
    return make_jpeg_app_segment(1, payload)


def reencode_with_opencv(jpeg_bytes: bytes) -> bytes:
    """Decode through Pillow and re-encode through the fixed OpenCV path."""
    return encode_jpeg_opencv(
        decode_jpeg_pillow(jpeg_bytes),
        quality=75,
        chroma_sampling="444",
    )


def test_repeated_preserve_keeps_the_controlled_envelope_exact() -> None:
    base = make_color_jpeg()
    envelope = make_jpeg_app_segment(1, b"synthetic-unknown-metadata")
    source = base[:2] + envelope + base[2:]

    first = apply_jpeg_metadata_policy(
        source,
        reencode_with_opencv(source),
        "preserve",
        preserved_envelope=envelope,
        envelope_placement="after_soi",
    )
    assert first.output_bytes is not None
    second = apply_jpeg_metadata_policy(
        first.output_bytes,
        reencode_with_opencv(first.output_bytes),
        "preserve",
        preserved_envelope=envelope,
        envelope_placement="after_soi",
    )

    assert second.output_bytes is not None
    assert first.output_bytes[2 : 2 + len(envelope)] == envelope
    assert second.output_bytes[2 : 2 + len(envelope)] == envelope
    assert audit_jpeg_metadata(second.output_bytes).accepted


def test_repeated_normalize_stabilizes_supported_exif_bytes() -> None:
    base = make_color_jpeg()
    envelope = make_orientation_segment()
    source = base[:2] + envelope + base[2:]

    first = apply_jpeg_metadata_policy(
        source, reencode_with_opencv(source), "normalize"
    )
    assert first.output_bytes is not None
    second = apply_jpeg_metadata_policy(
        first.output_bytes,
        reencode_with_opencv(first.output_bytes),
        "normalize",
    )

    assert second.output_bytes is not None
    assert first.output_bytes[2 : 2 + len(envelope)] == envelope
    assert second.output_bytes[2 : 2 + len(envelope)] == envelope
    assert inspect_jpeg_metadata(first.output_bytes).exif_orientation == 6
    assert inspect_jpeg_metadata(second.output_bytes).exif_orientation == 6


def test_strip_then_preserve_does_not_restore_removed_metadata() -> None:
    base = make_color_jpeg()
    envelope = make_orientation_segment()
    source = base[:2] + envelope + base[2:]

    stripped = apply_jpeg_metadata_policy(
        source, reencode_with_opencv(source), "strip"
    )
    assert stripped.output_bytes is not None
    preserved = apply_jpeg_metadata_policy(
        stripped.output_bytes,
        reencode_with_opencv(stripped.output_bytes),
        "preserve",
    )

    assert preserved.output_bytes is not None
    assert inspect_jpeg_metadata(stripped.output_bytes).exif_orientation is None
    assert (
        inspect_jpeg_metadata(preserved.output_bytes).exif_orientation is None
    )
    assert audit_jpeg_metadata(preserved.output_bytes).accepted
