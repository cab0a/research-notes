"""Bounded JPEG application-metadata auditing for untrusted inputs."""

from __future__ import annotations

from dataclasses import dataclass


_EXIF_IDENTIFIER = b"Exif\x00\x00"
_ICC_IDENTIFIER = b"ICC_PROFILE\x00"
_STANDALONE_MARKERS = {0x01, *range(0xD0, 0xD8)}


@dataclass(frozen=True)
class JPEGMetadataAudit:
    """Best-effort structural audit performed before metadata interpretation."""

    container_valid: bool
    metadata_valid: bool
    image_data_present: bool
    issue_codes: tuple[str, ...]
    app_segment_count: int
    metadata_payload_bytes: int
    exif_orientations: tuple[int, ...]
    icc_declared_chunks: int
    icc_observed_chunks: int
    icc_profile_length: int
    adobe_transforms: tuple[int, ...]
    trailing_bytes: int

    @property
    def accepted(self) -> bool:
        """Return whether the input satisfies the declared strict policy."""
        return (
            self.container_valid
            and self.metadata_valid
            and self.image_data_present
        )


def make_jpeg_app_segment(app_number: int, payload: bytes) -> bytes:
    """Build one well-framed JPEG APPn segment."""
    if not isinstance(app_number, int) or isinstance(app_number, bool):
        raise TypeError("app_number must be an integer")
    if not 0 <= app_number <= 15:
        raise ValueError("app_number must be in the interval [0, 15]")
    if not isinstance(payload, bytes):
        raise TypeError("payload must be bytes")
    segment_length = len(payload) + 2
    if segment_length > 65535:
        raise ValueError("JPEG APP segment exceeds the 16-bit length field")
    return (
        b"\xff"
        + bytes((0xE0 + app_number,))
        + segment_length.to_bytes(2, "big")
        + payload
    )


def audit_jpeg_metadata(
    jpeg_bytes: bytes,
    *,
    max_app_segments: int = 32,
    max_metadata_bytes: int = 131072,
) -> JPEGMetadataAudit:
    """Audit JPEG APP framing and selected EXIF, ICC, and Adobe structures.

    The audit is deliberately stricter than a decoder recovery policy. It
    returns issue codes for malformed byte streams rather than interpreting a
    successful pixel decode as evidence that metadata is valid.
    """
    if not isinstance(jpeg_bytes, bytes):
        raise TypeError("jpeg_bytes must be bytes")
    _validate_positive_limit(max_app_segments, "max_app_segments")
    _validate_positive_limit(max_metadata_bytes, "max_metadata_bytes")

    issues: list[str] = []
    exif_orientations: list[int] = []
    icc_chunks: dict[int, bytes] = {}
    icc_chunk_counts: list[int] = []
    adobe_transforms: list[int] = []
    app_segment_count = 0
    metadata_payload_bytes = 0
    image_data_present = False
    trailing_bytes = 0
    container_valid = True

    if len(jpeg_bytes) < 2 or jpeg_bytes[:2] != b"\xff\xd8":
        return _audit_result(
            container_valid=False,
            metadata_valid=False,
            image_data_present=False,
            issues=("missing_soi",),
        )

    position = 2
    while position < len(jpeg_bytes):
        if jpeg_bytes[position] != 0xFF:
            issues.append("expected_marker")
            container_valid = False
            break
        while position < len(jpeg_bytes) and jpeg_bytes[position] == 0xFF:
            position += 1
        if position >= len(jpeg_bytes):
            issues.append("truncated_marker")
            container_valid = False
            break
        marker = jpeg_bytes[position]
        position += 1

        if marker == 0xD9:
            trailing_bytes = len(jpeg_bytes) - position
            if trailing_bytes:
                issues.append("trailing_data")
                container_valid = False
            break
        if marker in _STANDALONE_MARKERS:
            continue
        if position + 2 > len(jpeg_bytes):
            issues.append("truncated_segment_length")
            container_valid = False
            break
        segment_length = int.from_bytes(
            jpeg_bytes[position : position + 2], "big"
        )
        if segment_length < 2:
            issues.append("invalid_segment_length")
            container_valid = False
            break
        payload_start = position + 2
        payload_end = position + segment_length
        if payload_end > len(jpeg_bytes):
            issues.append("segment_overrun")
            container_valid = False
            break
        payload = jpeg_bytes[payload_start:payload_end]
        position = payload_end

        if marker == 0xDA:
            image_data_present = True
            eoi_offset = jpeg_bytes.rfind(b"\xff\xd9", position)
            if eoi_offset < position:
                issues.append("missing_eoi")
                container_valid = False
            else:
                trailing_bytes = len(jpeg_bytes) - (eoi_offset + 2)
                if trailing_bytes:
                    issues.append("trailing_data")
                    container_valid = False
            break

        if 0xE0 <= marker <= 0xEF:
            app_segment_count += 1
            metadata_payload_bytes += len(payload)
        if marker == 0xE1 and payload.startswith(_EXIF_IDENTIFIER):
            orientations, exif_issues = _audit_exif_payload(payload)
            exif_orientations.extend(orientations)
            issues.extend(exif_issues)
        elif marker == 0xE2 and payload.startswith(_ICC_IDENTIFIER):
            _collect_icc_chunk(
                payload, icc_chunks, icc_chunk_counts, issues
            )
        elif marker == 0xEE and payload.startswith(b"Adobe"):
            if len(payload) < 12:
                issues.append("adobe_truncated_segment")
            else:
                transform = payload[11]
                adobe_transforms.append(transform)
                if transform not in (0, 1, 2):
                    issues.append("adobe_transform_out_of_range")

    if not image_data_present and "missing_eoi" not in issues:
        issues.append("missing_sos")
        container_valid = False
    if app_segment_count > max_app_segments:
        issues.append("app_segment_limit_exceeded")
    if metadata_payload_bytes > max_metadata_bytes:
        issues.append("metadata_byte_limit_exceeded")
    if len(set(exif_orientations)) > 1:
        issues.append("exif_conflicting_orientation")
    if len(set(adobe_transforms)) > 1:
        issues.append("adobe_conflicting_transform")

    profile = _finish_icc_audit(
        icc_chunks, icc_chunk_counts, issues
    )
    unique_issues = tuple(dict.fromkeys(issues))
    metadata_valid = not any(
        code.startswith(("exif_", "icc_", "adobe_", "app_", "metadata_"))
        for code in unique_issues
    )
    return JPEGMetadataAudit(
        container_valid=container_valid,
        metadata_valid=metadata_valid,
        image_data_present=image_data_present,
        issue_codes=unique_issues,
        app_segment_count=app_segment_count,
        metadata_payload_bytes=metadata_payload_bytes,
        exif_orientations=tuple(exif_orientations),
        icc_declared_chunks=(
            icc_chunk_counts[0] if icc_chunk_counts else 0
        ),
        icc_observed_chunks=len(icc_chunks),
        icc_profile_length=len(profile),
        adobe_transforms=tuple(adobe_transforms),
        trailing_bytes=trailing_bytes,
    )


def _audit_result(
    *,
    container_valid: bool,
    metadata_valid: bool,
    image_data_present: bool,
    issues: tuple[str, ...],
) -> JPEGMetadataAudit:
    """Build an empty audit result for an early container failure."""
    return JPEGMetadataAudit(
        container_valid=container_valid,
        metadata_valid=metadata_valid,
        image_data_present=image_data_present,
        issue_codes=issues,
        app_segment_count=0,
        metadata_payload_bytes=0,
        exif_orientations=(),
        icc_declared_chunks=0,
        icc_observed_chunks=0,
        icc_profile_length=0,
        adobe_transforms=(),
        trailing_bytes=0,
    )


def _validate_positive_limit(value: int, name: str) -> None:
    """Validate one positive integer resource limit."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")
    if value <= 0:
        raise ValueError(f"{name} must be positive")


def _audit_exif_payload(payload: bytes) -> tuple[list[int], list[str]]:
    """Audit the TIFF header and Orientation entries in one EXIF APP1."""
    tiff = payload[len(_EXIF_IDENTIFIER) :]
    if len(tiff) < 8:
        return [], ["exif_truncated_tiff_header"]
    byte_order = tiff[:2]
    if byte_order == b"II":
        endian = "little"
    elif byte_order == b"MM":
        endian = "big"
    else:
        return [], ["exif_invalid_byte_order"]
    if int.from_bytes(tiff[2:4], endian) != 42:
        return [], ["exif_invalid_magic"]
    ifd_offset = int.from_bytes(tiff[4:8], endian)
    if ifd_offset < 8 or ifd_offset + 2 > len(tiff):
        return [], ["exif_ifd_offset_out_of_bounds"]
    entry_count = int.from_bytes(
        tiff[ifd_offset : ifd_offset + 2], endian
    )
    entries_start = ifd_offset + 2
    entries_end = entries_start + entry_count * 12
    if entries_end > len(tiff):
        return [], ["exif_truncated_ifd"]

    orientations: list[int] = []
    issues: list[str] = []
    for index in range(entry_count):
        start = entries_start + index * 12
        entry = tiff[start : start + 12]
        tag = int.from_bytes(entry[:2], endian)
        if tag != 274:
            continue
        field_type = int.from_bytes(entry[2:4], endian)
        count = int.from_bytes(entry[4:8], endian)
        if field_type != 3 or count != 1:
            issues.append("exif_orientation_type_or_count")
            continue
        orientation = int.from_bytes(entry[8:10], endian)
        orientations.append(orientation)
        if not 1 <= orientation <= 8:
            issues.append("exif_orientation_out_of_range")
    return orientations, issues


def _collect_icc_chunk(
    payload: bytes,
    chunks: dict[int, bytes],
    declared_counts: list[int],
    issues: list[str],
) -> None:
    """Collect one ICC APP2 chunk while recording topology errors."""
    if len(payload) < 14:
        issues.append("icc_truncated_chunk_header")
        return
    sequence_number = payload[12]
    chunk_count = payload[13]
    declared_counts.append(chunk_count)
    if sequence_number == 0:
        issues.append("icc_zero_sequence_number")
    if chunk_count == 0:
        issues.append("icc_zero_chunk_count")
    if chunk_count and sequence_number > chunk_count:
        issues.append("icc_sequence_exceeds_count")
    if sequence_number in chunks:
        issues.append("icc_duplicate_sequence")
    else:
        chunks[sequence_number] = payload[14:]


def _finish_icc_audit(
    chunks: dict[int, bytes],
    declared_counts: list[int],
    issues: list[str],
) -> bytes:
    """Validate ICC chunk topology and the reconstructed profile header."""
    if not declared_counts:
        return b""
    nonzero_counts = {count for count in declared_counts if count}
    if len(nonzero_counts) > 1:
        issues.append("icc_inconsistent_chunk_count")
    declared_count = declared_counts[0]
    if declared_count:
        expected = set(range(1, declared_count + 1))
        if set(chunks) != expected:
            issues.append("icc_missing_sequence")
    if (
        declared_count == 0
        or set(chunks) != set(range(1, declared_count + 1))
    ):
        return b""
    profile = b"".join(chunks[index] for index in range(1, declared_count + 1))
    if len(profile) < 128:
        issues.append("icc_profile_too_short")
        return profile
    declared_size = int.from_bytes(profile[:4], "big")
    if declared_size != len(profile):
        issues.append("icc_profile_size_mismatch")
    if profile[36:40] != b"acsp":
        issues.append("icc_missing_signature")
    return profile
