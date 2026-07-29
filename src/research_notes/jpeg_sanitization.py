"""Explicit JPEG metadata round-trip and sanitization policies."""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Literal

from PIL import Image

from research_notes.jpeg_metadata import (
    attach_jpeg_metadata,
    strip_jpeg_interpretation_metadata,
)
from research_notes.jpeg_recovery import audit_jpeg_metadata


JPEGMetadataPolicy = Literal["preserve", "strip", "normalize", "reject"]
JPEGEnvelopePlacement = Literal["none", "after_soi", "after_eoi"]


@dataclass(frozen=True)
class JPEGMetadataPolicyResult:
    """Result of applying one declared metadata policy after re-encoding."""

    policy: JPEGMetadataPolicy
    action: str
    source_accepted: bool
    output_bytes: bytes | None

    @property
    def emitted(self) -> bool:
        """Return whether the policy produced an output byte stream."""
        return self.output_bytes is not None


def apply_jpeg_metadata_policy(
    source_jpeg: bytes,
    reencoded_jpeg: bytes,
    policy: JPEGMetadataPolicy,
    *,
    preserved_envelope: bytes = b"",
    envelope_placement: JPEGEnvelopePlacement = "none",
) -> JPEGMetadataPolicyResult:
    """Apply one explicit metadata policy to a re-encoded JPEG.

    ``preserve`` is intentionally a byte-copy control: callers must supply the
    exact metadata envelope and its controlled placement. It is not a parser
    for arbitrary untrusted metadata. ``normalize`` and ``reject`` retain only
    supported EXIF Orientation and ICC semantics from strict-audit inputs.
    """
    _validate_jpeg_bytes(source_jpeg, "source_jpeg")
    _validate_jpeg_bytes(reencoded_jpeg, "reencoded_jpeg")
    if policy not in ("preserve", "strip", "normalize", "reject"):
        raise ValueError(
            "policy must be one of: preserve, strip, normalize, reject"
        )
    _validate_envelope(preserved_envelope, envelope_placement)

    source_audit = audit_jpeg_metadata(source_jpeg)
    neutral = strip_jpeg_interpretation_metadata(reencoded_jpeg)

    if policy == "reject" and not source_audit.accepted:
        return JPEGMetadataPolicyResult(
            policy=policy,
            action="strict_reject",
            source_accepted=False,
            output_bytes=None,
        )

    if policy == "preserve":
        output = _insert_envelope(
            neutral, preserved_envelope, envelope_placement
        )
        return JPEGMetadataPolicyResult(
            policy=policy,
            action=(
                "blind_copy_input_envelope"
                if preserved_envelope
                else "no_input_envelope"
            ),
            source_accepted=source_audit.accepted,
            output_bytes=output,
        )

    if policy == "strip" or not source_audit.accepted:
        return JPEGMetadataPolicyResult(
            policy=policy,
            action=(
                "strip_input_metadata"
                if policy == "strip"
                else "strip_invalid_input_metadata"
            ),
            source_accepted=source_audit.accepted,
            output_bytes=neutral,
        )

    orientation = (
        source_audit.exif_orientations[0]
        if source_audit.exif_orientations
        else None
    )
    icc_profile = _extract_icc_profile(source_jpeg)
    output = attach_jpeg_metadata(
        neutral,
        exif_orientation=orientation,
        icc_profile=icc_profile or None,
    )
    has_supported_metadata = orientation is not None or bool(icc_profile)
    return JPEGMetadataPolicyResult(
        policy=policy,
        action=(
            "normalize_supported_metadata"
            if has_supported_metadata
            else "strip_unsupported_input_metadata"
        ),
        source_accepted=True,
        output_bytes=output,
    )


def _extract_icc_profile(jpeg_bytes: bytes) -> bytes:
    """Return a complete ICC profile from one strict-audit JPEG."""
    try:
        with Image.open(io.BytesIO(jpeg_bytes)) as image:
            profile = image.info.get("icc_profile", b"")
    except (OSError, SyntaxError) as error:
        raise ValueError("Pillow could not inspect the JPEG ICC profile") from error
    if profile is None:
        return b""
    if not isinstance(profile, bytes):
        raise TypeError("Pillow returned a non-byte ICC profile")
    return profile


def _insert_envelope(
    jpeg_bytes: bytes,
    envelope: bytes,
    placement: JPEGEnvelopePlacement,
) -> bytes:
    """Insert one caller-supplied controlled metadata envelope."""
    if placement == "none":
        return jpeg_bytes
    if placement == "after_soi":
        return jpeg_bytes[:2] + envelope + jpeg_bytes[2:]
    return jpeg_bytes + envelope


def _validate_envelope(
    envelope: bytes, placement: JPEGEnvelopePlacement
) -> None:
    """Validate a controlled byte envelope and placement declaration."""
    if not isinstance(envelope, bytes):
        raise TypeError("preserved_envelope must be bytes")
    if placement not in ("none", "after_soi", "after_eoi"):
        raise ValueError(
            "envelope_placement must be one of: none, after_soi, after_eoi"
        )
    if bool(envelope) == (placement == "none"):
        raise ValueError(
            "non-empty envelopes require a placement and empty envelopes "
            "require placement 'none'"
        )


def _validate_jpeg_bytes(jpeg_bytes: bytes, name: str) -> None:
    """Validate a non-empty byte string with a JPEG SOI marker."""
    if not isinstance(jpeg_bytes, bytes) or not jpeg_bytes:
        raise TypeError(f"{name} must be non-empty bytes")
    if not jpeg_bytes.startswith(b"\xff\xd8"):
        raise ValueError(f"{name} must start with a JPEG SOI marker")
