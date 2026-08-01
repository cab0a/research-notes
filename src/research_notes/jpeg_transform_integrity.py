"""Controlled digest bindings for JPEG transform-integrity experiments."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal

import numpy as np

from research_notes.jpeg_codec import (
    decode_jpeg_pillow,
    encode_jpeg_pillow,
)
from research_notes.jpeg_contracts import pixel_array_sha256
from research_notes.jpeg_provenance import (
    apply_selective_metadata_policy,
    build_controlled_metadata_fixture,
    metadata_state_sha256,
)
from research_notes.jpeg_recovery import make_jpeg_app_segment


JPEGIntegrityStatus = Literal[
    "valid_binding",
    "valid_derived_binding",
    "stale_binding",
    "missing_assertion",
    "malformed_assertion",
    "multiple_assertions",
]

_ASSERTION_IDENTIFIER = b"ResearchNotesIntegrity\x00"
_ASSERTION_SCHEMA = "research-notes-integrity/1"
_BINDING_NAMES = (
    "image_core_sha256",
    "metadata_state_sha256",
    "decoded_pixels_sha256",
)
_STANDALONE_MARKERS = {0x01, *range(0xD0, 0xD8)}


@dataclass(frozen=True)
class JPEGTransformIntegrityResult:
    """Validation result for one controlled digest assertion."""

    status: JPEGIntegrityStatus
    reason_code: str
    action: str
    parent_assertion_sha256: str
    assertion_sha256: str
    binding_names: tuple[str, ...]
    matching_bindings: tuple[str, ...]
    mismatching_bindings: tuple[str, ...]

    @property
    def valid(self) -> bool:
        """Return whether all declared digest bindings match current bytes."""
        return self.status in ("valid_binding", "valid_derived_binding")


@dataclass(frozen=True)
class JPEGTransformIntegrityFixture:
    """One deterministic transform and expected integrity outcome."""

    fixture: str
    transform: str
    assertion_mode: str
    expected_status: JPEGIntegrityStatus
    expected_reason_code: str
    jpeg_bytes: bytes


def attach_transform_integrity_assertion(
    jpeg_bytes: bytes,
    *,
    action: str,
    parent_assertion_sha256: str = "",
) -> bytes:
    """Attach one unsigned, canonical digest assertion to a controlled JPEG.

    The record detects changes to three declared scopes. It is not a digital
    signature, identity claim, trust-chain validation, or C2PA implementation.
    """
    _validate_jpeg(jpeg_bytes, "jpeg_bytes")
    if not isinstance(action, str) or not action:
        raise ValueError("action must be a non-empty string")
    if parent_assertion_sha256 and not _is_sha256(parent_assertion_sha256):
        raise ValueError("parent_assertion_sha256 must be empty or SHA-256")
    neutral = strip_transform_integrity_assertions(jpeg_bytes)
    document = {
        "action": action,
        "bindings": _current_bindings(neutral),
        "parent_assertion_sha256": parent_assertion_sha256,
        "schema": _ASSERTION_SCHEMA,
    }
    payload = _ASSERTION_IDENTIFIER + _canonical_json(document)
    return neutral[:2] + make_jpeg_app_segment(15, payload) + neutral[2:]


def verify_transform_integrity_assertion(
    jpeg_bytes: bytes,
) -> JPEGTransformIntegrityResult:
    """Verify one controlled digest assertion against current content."""
    _validate_jpeg(jpeg_bytes, "jpeg_bytes")
    payloads = _integrity_payloads(jpeg_bytes)
    if not payloads:
        return _result("missing_assertion", "assertion_missing")
    if len(payloads) > 1:
        return _result("multiple_assertions", "assertion_multiple")
    payload = payloads[0]
    assertion_sha256 = hashlib.sha256(payload).hexdigest()
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _result(
            "malformed_assertion",
            "assertion_json_invalid",
            assertion_sha256=assertion_sha256,
        )
    validation_error = _validate_document(document)
    if validation_error:
        return _result(
            "malformed_assertion",
            validation_error,
            assertion_sha256=assertion_sha256,
        )
    neutral = strip_transform_integrity_assertions(jpeg_bytes)
    current = _current_bindings(neutral)
    declared = document["bindings"]
    matching = tuple(
        name for name in _BINDING_NAMES if declared[name] == current[name]
    )
    mismatching = tuple(
        name for name in _BINDING_NAMES if declared[name] != current[name]
    )
    parent = document["parent_assertion_sha256"]
    if mismatching:
        status: JPEGIntegrityStatus = "stale_binding"
        reason = "binding_mismatch"
    elif parent:
        status = "valid_derived_binding"
        reason = "bindings_match"
    else:
        status = "valid_binding"
        reason = "bindings_match"
    return JPEGTransformIntegrityResult(
        status=status,
        reason_code=reason,
        action=document["action"],
        parent_assertion_sha256=parent,
        assertion_sha256=assertion_sha256,
        binding_names=_BINDING_NAMES,
        matching_bindings=matching,
        mismatching_bindings=mismatching,
    )


def strip_transform_integrity_assertions(jpeg_bytes: bytes) -> bytes:
    """Remove controlled integrity APP15 segments and preserve other bytes."""
    _validate_jpeg(jpeg_bytes, "jpeg_bytes")
    return _rewrite_header(
        jpeg_bytes,
        lambda marker, payload: not (
            marker == 0xEF and payload.startswith(_ASSERTION_IDENTIFIER)
        ),
    )


def image_core_sha256(jpeg_bytes: bytes) -> str:
    """Hash JPEG bytes after removing APP1-APP15 and COM metadata segments."""
    _validate_jpeg(jpeg_bytes, "jpeg_bytes")
    neutral = strip_transform_integrity_assertions(jpeg_bytes)
    core = _rewrite_header(
        neutral,
        lambda marker, payload: not (
            marker == 0xFE or 0xE1 <= marker <= 0xEF
        ),
    )
    return hashlib.sha256(core).hexdigest()


def integrity_assertion_sha256(jpeg_bytes: bytes) -> str:
    """Return the controlled assertion hash when exactly one is present."""
    _validate_jpeg(jpeg_bytes, "jpeg_bytes")
    payloads = _integrity_payloads(jpeg_bytes)
    if len(payloads) != 1:
        raise ValueError("jpeg_bytes must contain exactly one integrity assertion")
    return hashlib.sha256(payloads[0]).hexdigest()


def build_transform_integrity_fixtures(
    base_jpeg: bytes,
    *,
    icc_profile: bytes,
) -> tuple[JPEGTransformIntegrityFixture, ...]:
    """Build controlled inherited, renewed, stale, and malformed assertions."""
    _validate_jpeg(base_jpeg, "base_jpeg")
    if not isinstance(icc_profile, bytes) or not icc_profile:
        raise TypeError("icc_profile must be non-empty bytes")
    canonical = build_controlled_metadata_fixture(
        base_jpeg,
        icc_profile=icc_profile,
        variant="canonical_order",
    )
    reordered = build_controlled_metadata_fixture(
        base_jpeg,
        icc_profile=icc_profile,
        variant="reordered_equivalent",
    )
    source = attach_transform_integrity_assertion(
        canonical, action="created"
    )
    source_payload = _integrity_payloads(source)[0]
    source_hash = hashlib.sha256(source_payload).hexdigest()

    sanitized = apply_selective_metadata_policy(
        canonical,
        base_jpeg,
        "allow_visual_context",
    ).output_bytes
    decoded = decode_jpeg_pillow(canonical)
    reencoded_core = encode_jpeg_pillow(
        decoded, quality=65, chroma_sampling="444"
    )
    reencoded = apply_selective_metadata_policy(
        canonical,
        reencoded_core,
        "retain_all",
    ).output_bytes
    modified_pixels = decoded.copy()
    modified_pixels[8:20, 10:24] = np.array([15, 220, 40], dtype=np.uint8)
    modified_core = encode_jpeg_pillow(
        modified_pixels, quality=75, chroma_sampling="444"
    )
    modified = apply_selective_metadata_policy(
        canonical,
        modified_core,
        "retain_all",
    ).output_bytes

    inherited_reordered = _attach_payload(reordered, source_payload)
    inherited_sanitized = _attach_payload(sanitized, source_payload)
    renewed_sanitized = attach_transform_integrity_assertion(
        sanitized,
        action="metadata_sanitized",
        parent_assertion_sha256=source_hash,
    )
    inherited_reencoded = _attach_payload(reencoded, source_payload)
    renewed_reencoded = attach_transform_integrity_assertion(
        reencoded,
        action="reencoded",
        parent_assertion_sha256=source_hash,
    )
    inherited_modified = _attach_payload(modified, source_payload)

    tampered_document = json.loads(source_payload.decode("utf-8"))
    tampered_document["bindings"]["metadata_state_sha256"] = "0" * 64
    tampered = _attach_payload(
        canonical, _canonical_json(tampered_document)
    )
    malformed = _attach_payload(canonical, b"{not-json")
    duplicate = (
        canonical[:2]
        + make_jpeg_app_segment(
            15, _ASSERTION_IDENTIFIER + source_payload
        )
        + make_jpeg_app_segment(
            15, _ASSERTION_IDENTIFIER + source_payload
        )
        + canonical[2:]
    )
    return (
        JPEGTransformIntegrityFixture(
            "source_valid_binding",
            "created",
            "new",
            "valid_binding",
            "bindings_match",
            source,
        ),
        JPEGTransformIntegrityFixture(
            "metadata_reordered_inherited",
            "metadata_reordered",
            "inherited",
            "valid_binding",
            "bindings_match",
            inherited_reordered,
        ),
        JPEGTransformIntegrityFixture(
            "metadata_sanitized_inherited",
            "metadata_sanitized",
            "inherited",
            "stale_binding",
            "binding_mismatch",
            inherited_sanitized,
        ),
        JPEGTransformIntegrityFixture(
            "metadata_sanitized_renewed",
            "metadata_sanitized",
            "renewed",
            "valid_derived_binding",
            "bindings_match",
            renewed_sanitized,
        ),
        JPEGTransformIntegrityFixture(
            "reencoded_inherited",
            "reencoded",
            "inherited",
            "stale_binding",
            "binding_mismatch",
            inherited_reencoded,
        ),
        JPEGTransformIntegrityFixture(
            "reencoded_renewed",
            "reencoded",
            "renewed",
            "valid_derived_binding",
            "bindings_match",
            renewed_reencoded,
        ),
        JPEGTransformIntegrityFixture(
            "pixel_modified_inherited",
            "pixel_modified",
            "inherited",
            "stale_binding",
            "binding_mismatch",
            inherited_modified,
        ),
        JPEGTransformIntegrityFixture(
            "manifest_digest_tampered",
            "manifest_tampered",
            "tampered",
            "stale_binding",
            "binding_mismatch",
            tampered,
        ),
        JPEGTransformIntegrityFixture(
            "manifest_json_malformed",
            "manifest_malformed",
            "malformed",
            "malformed_assertion",
            "assertion_json_invalid",
            malformed,
        ),
        JPEGTransformIntegrityFixture(
            "manifest_missing",
            "manifest_removed",
            "missing",
            "missing_assertion",
            "assertion_missing",
            canonical,
        ),
        JPEGTransformIntegrityFixture(
            "manifest_duplicate",
            "manifest_duplicated",
            "duplicate",
            "multiple_assertions",
            "assertion_multiple",
            duplicate,
        ),
    )


def _current_bindings(jpeg_bytes: bytes) -> dict[str, str]:
    """Compute the three controlled content scopes."""
    return {
        "image_core_sha256": image_core_sha256(jpeg_bytes),
        "metadata_state_sha256": metadata_state_sha256(jpeg_bytes),
        "decoded_pixels_sha256": pixel_array_sha256(
            decode_jpeg_pillow(jpeg_bytes)
        ),
    }


def _validate_document(document: object) -> str:
    """Return an error code or an empty string for one parsed assertion."""
    if not isinstance(document, dict):
        return "assertion_document_invalid"
    if set(document) != {
        "action",
        "bindings",
        "parent_assertion_sha256",
        "schema",
    }:
        return "assertion_fields_invalid"
    if document["schema"] != _ASSERTION_SCHEMA:
        return "assertion_schema_unsupported"
    if not isinstance(document["action"], str) or not document["action"]:
        return "assertion_action_invalid"
    parent = document["parent_assertion_sha256"]
    if not isinstance(parent, str) or (parent and not _is_sha256(parent)):
        return "assertion_parent_invalid"
    bindings = document["bindings"]
    if not isinstance(bindings, dict) or tuple(sorted(bindings)) != tuple(
        sorted(_BINDING_NAMES)
    ):
        return "assertion_bindings_invalid"
    if any(not isinstance(bindings[name], str) or not _is_sha256(bindings[name]) for name in _BINDING_NAMES):
        return "assertion_digest_invalid"
    return ""


def _result(
    status: JPEGIntegrityStatus,
    reason_code: str,
    *,
    assertion_sha256: str = "",
) -> JPEGTransformIntegrityResult:
    """Build a result for an assertion that cannot reach binding checks."""
    return JPEGTransformIntegrityResult(
        status=status,
        reason_code=reason_code,
        action="",
        parent_assertion_sha256="",
        assertion_sha256=assertion_sha256,
        binding_names=(),
        matching_bindings=(),
        mismatching_bindings=(),
    )


def _canonical_json(document: dict[str, object]) -> bytes:
    """Serialize one assertion deterministically."""
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")


def _attach_payload(jpeg_bytes: bytes, assertion_json: bytes) -> bytes:
    """Attach caller-supplied controlled assertion JSON after SOI."""
    neutral = strip_transform_integrity_assertions(jpeg_bytes)
    segment = make_jpeg_app_segment(
        15, _ASSERTION_IDENTIFIER + assertion_json
    )
    return neutral[:2] + segment + neutral[2:]


def _integrity_payloads(jpeg_bytes: bytes) -> tuple[bytes, ...]:
    """Return JSON payloads from controlled APP15 assertions."""
    payloads = []
    for marker, payload in _header_segments(jpeg_bytes):
        if marker == 0xEF and payload.startswith(_ASSERTION_IDENTIFIER):
            payloads.append(payload[len(_ASSERTION_IDENTIFIER) :])
    return tuple(payloads)


def _rewrite_header(
    jpeg_bytes: bytes,
    keep: object,
) -> bytes:
    """Rewrite length-delimited header segments while preserving image data."""
    output = bytearray(jpeg_bytes[:2])
    position = 2
    while position < len(jpeg_bytes):
        marker_start = position
        if jpeg_bytes[position] != 0xFF:
            raise ValueError("expected JPEG marker prefix")
        while position < len(jpeg_bytes) and jpeg_bytes[position] == 0xFF:
            position += 1
        if position >= len(jpeg_bytes):
            raise ValueError("truncated JPEG marker")
        marker = jpeg_bytes[position]
        position += 1
        if marker in (0xD9, 0xDA):
            output.extend(jpeg_bytes[marker_start:])
            break
        if marker in _STANDALONE_MARKERS:
            output.extend(jpeg_bytes[marker_start:position])
            continue
        start, end = _payload_bounds(jpeg_bytes, position)
        payload = jpeg_bytes[start:end]
        if keep(marker, payload):  # type: ignore[operator]
            output.extend(jpeg_bytes[marker_start:end])
        position = end
    if not output.endswith(b"\xff\xd9"):
        raise ValueError("JPEG EOI marker was not found")
    return bytes(output)


def _header_segments(jpeg_bytes: bytes) -> tuple[tuple[int, bytes], ...]:
    """Return length-delimited JPEG header segments before SOS."""
    segments = []
    position = 2
    while position < len(jpeg_bytes):
        if jpeg_bytes[position] != 0xFF:
            raise ValueError("expected JPEG marker prefix")
        while position < len(jpeg_bytes) and jpeg_bytes[position] == 0xFF:
            position += 1
        if position >= len(jpeg_bytes):
            raise ValueError("truncated JPEG marker")
        marker = jpeg_bytes[position]
        position += 1
        if marker in (0xD9, 0xDA):
            break
        if marker in _STANDALONE_MARKERS:
            continue
        start, end = _payload_bounds(jpeg_bytes, position)
        segments.append((marker, jpeg_bytes[start:end]))
        position = end
    return tuple(segments)


def _payload_bounds(jpeg_bytes: bytes, length_offset: int) -> tuple[int, int]:
    """Return validated payload bounds for one segment."""
    if length_offset + 2 > len(jpeg_bytes):
        raise ValueError("truncated JPEG segment length")
    length = int.from_bytes(jpeg_bytes[length_offset : length_offset + 2], "big")
    if length < 2:
        raise ValueError("invalid JPEG segment length")
    start = length_offset + 2
    end = length_offset + length
    if end > len(jpeg_bytes):
        raise ValueError("JPEG segment exceeds the input")
    return start, end


def _is_sha256(value: str) -> bool:
    """Return whether a string is one lowercase SHA-256 digest."""
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _validate_jpeg(jpeg_bytes: bytes, name: str) -> None:
    """Validate one complete JPEG byte string at the public boundary."""
    if not isinstance(jpeg_bytes, bytes) or not jpeg_bytes:
        raise TypeError(f"{name} must be non-empty bytes")
    if not jpeg_bytes.startswith(b"\xff\xd8"):
        raise ValueError(f"{name} must start with a JPEG SOI marker")
