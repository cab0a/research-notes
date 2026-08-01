"""Controlled JPEG metadata-family coverage and relationship resolution."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Literal

from research_notes.jpeg_recovery import make_jpeg_app_segment
from research_notes.jpeg_resource_bounds import audit_jpeg_metadata_resources


JPEGMetadataCoverageDecision = Literal["accept", "quarantine", "reject"]

_EXIF_IDENTIFIER = b"Exif\x00\x00"
_XMP_IDENTIFIER = b"http://ns.adobe.com/xap/1.0/\x00"
_EXTENDED_XMP_IDENTIFIER = b"http://ns.adobe.com/xmp/extension/\x00"
_PHOTOSHOP_IDENTIFIER = b"Photoshop 3.0\x00"
_PHOTOSHOP_SIGNATURE = b"8BIM"
_IPTC_RESOURCE_ID = 0x0404
_STANDALONE_MARKERS = {0x01, *range(0xD0, 0xD8)}


@dataclass(frozen=True)
class JPEGMetadataCoverageResult:
    """One bounded coverage decision and its relationship evidence."""

    decision: JPEGMetadataCoverageDecision
    reason_code: str
    resource_decision: str
    resource_reason_code: str
    families: tuple[str, ...]
    recognized_components: int
    opaque_components: int
    relationships_declared: int
    relationships_resolved: int
    exif_thumbnails: int
    exif_thumbnail_bytes: int
    maker_notes: int
    maker_note_bytes: int
    standard_xmp_packets: int
    extended_xmp_chunks: int
    extended_xmp_bytes: int
    iptc_iim_blocks: int
    iptc_iim_datasets: int

    @property
    def accepted(self) -> bool:
        """Return whether all recognized relationships are complete."""
        return self.decision == "accept"

    @property
    def relationship_completion_rate(self) -> float:
        """Return the resolved fraction, treating no relations as complete."""
        if self.relationships_declared == 0:
            return 1.0
        return self.relationships_resolved / self.relationships_declared


@dataclass(frozen=True)
class JPEGMetadataCoverageFixture:
    """One deterministic metadata-family coverage fixture."""

    fixture: str
    family: str
    condition: str
    expected_decision: JPEGMetadataCoverageDecision
    expected_reason_code: str
    jpeg_bytes: bytes


@dataclass
class _CoverageState:
    """Mutable counters used during one controlled inspection."""

    families: set[str]
    recognized_components: int = 0
    opaque_components: int = 0
    relationships_declared: int = 0
    relationships_resolved: int = 0
    exif_thumbnails: int = 0
    exif_thumbnail_bytes: int = 0
    maker_notes: int = 0
    maker_note_bytes: int = 0
    standard_xmp_packets: int = 0
    extended_xmp_chunks: int = 0
    extended_xmp_bytes: int = 0
    iptc_iim_blocks: int = 0
    iptc_iim_datasets: int = 0


class _CoverageError(Exception):
    """Internal fail-closed signal for one recognized metadata family."""


def inspect_jpeg_metadata_coverage(
    jpeg_bytes: bytes,
) -> JPEGMetadataCoverageResult:
    """Inspect controlled metadata families after resource admission.

    This parser deliberately recognizes only the structures exercised by the
    v0.18 synthetic corpus. A successful result is not evidence of complete
    EXIF, XMP, IPTC IIM, Photoshop IRB, or maker-note support.
    """
    if not isinstance(jpeg_bytes, bytes):
        raise TypeError("jpeg_bytes must be bytes")
    resource = audit_jpeg_metadata_resources(jpeg_bytes)
    state = _CoverageState(families=set())
    if resource.decision != "accept":
        return _finish(
            state,
            resource.decision,
            f"resource_{resource.reason_code}",
            resource.decision,
            resource.reason_code,
        )

    try:
        segments = _header_segments(jpeg_bytes)
    except ValueError as error:
        return _finish(
            state,
            "reject",
            str(error),
            resource.decision,
            resource.reason_code,
        )

    extended_chunks: dict[str, list[tuple[int, int, bytes]]] = {}
    referenced_extensions: list[str] = []
    try:
        for marker, payload in segments:
            if marker == 0xE1 and payload.startswith(_EXIF_IDENTIFIER):
                _inspect_exif(payload, state)
            elif marker == 0xE1 and payload.startswith(_XMP_IDENTIFIER):
                referenced = _inspect_standard_xmp(payload, state)
                if referenced is not None:
                    referenced_extensions.append(referenced)
            elif marker == 0xE1 and payload.startswith(
                _EXTENDED_XMP_IDENTIFIER
            ):
                guid, full_length, offset, chunk = _parse_extended_xmp_chunk(
                    payload
                )
                extended_chunks.setdefault(guid, []).append(
                    (full_length, offset, chunk)
                )
                state.extended_xmp_chunks += 1
            elif marker == 0xED and payload.startswith(
                _PHOTOSHOP_IDENTIFIER
            ):
                _inspect_photoshop_resources(payload, state)
            elif marker == 0xED:
                state.families.add("app13_opaque")
                state.recognized_components += 1
                state.opaque_components += 1
        _resolve_extended_xmp(
            referenced_extensions, extended_chunks, state
        )
    except _CoverageError as error:
        return _finish(
            state,
            "quarantine",
            str(error),
            resource.decision,
            resource.reason_code,
        )

    reason = (
        "coverage_complete_with_opaque"
        if state.opaque_components
        else "coverage_complete"
    )
    return _finish(
        state,
        "accept",
        reason,
        resource.decision,
        resource.reason_code,
    )


def build_metadata_coverage_fixtures(
    base_jpeg: bytes,
) -> tuple[JPEGMetadataCoverageFixture, ...]:
    """Build the deterministic v0.18 metadata-family fixture corpus."""
    _validate_base_jpeg(base_jpeg)
    thumbnail = _minimal_nested_jpeg()
    maker_note = b"SYNTHETIC-MAKER-NOTE"
    exif_complete = make_jpeg_app_segment(
        1,
        _build_exif_payload(
            thumbnail=thumbnail,
            maker_note=None,
        ),
    )
    exif_missing = make_jpeg_app_segment(
        1,
        _build_exif_payload(
            thumbnail=thumbnail,
            maker_note=None,
            thumbnail_length_delta=1,
        ),
    )
    maker_complete = make_jpeg_app_segment(
        1,
        _build_exif_payload(
            thumbnail=None,
            maker_note=maker_note,
        ),
    )
    maker_missing = make_jpeg_app_segment(
        1,
        _build_exif_payload(
            thumbnail=None,
            maker_note=maker_note,
            maker_note_offset_delta=1,
        ),
    )

    guid = "0123456789ABCDEF0123456789ABCDEF"
    other_guid = "FEDCBA9876543210FEDCBA9876543210"
    main_only = make_jpeg_app_segment(
        1, _build_standard_xmp_payload(None)
    )
    main_extended = make_jpeg_app_segment(
        1, _build_standard_xmp_payload(guid)
    )
    extension_packet = _build_extended_xmp_packet()
    split = len(extension_packet) // 2
    extension_chunks = (
        _build_extended_xmp_segment(
            guid, len(extension_packet), 0, extension_packet[:split]
        ),
        _build_extended_xmp_segment(
            guid,
            len(extension_packet),
            split,
            extension_packet[split:],
        ),
    )
    orphan = _build_extended_xmp_segment(
        other_guid,
        len(extension_packet),
        0,
        extension_packet,
    )

    iim = _build_iptc_iim_block()
    iptc_complete = make_jpeg_app_segment(
        13, _build_photoshop_payload(iim)
    )
    iptc_truncated = make_jpeg_app_segment(
        13, _build_photoshop_payload(iim[:-1])
    )

    def source(*segments: bytes) -> bytes:
        return base_jpeg[:2] + b"".join(segments) + base_jpeg[2:]

    fixtures = (
        JPEGMetadataCoverageFixture(
            "baseline_no_metadata",
            "baseline",
            "no_metadata",
            "accept",
            "coverage_complete",
            base_jpeg,
        ),
        JPEGMetadataCoverageFixture(
            "exif_thumbnail_complete",
            "exif_thumbnail",
            "complete",
            "accept",
            "coverage_complete",
            source(exif_complete),
        ),
        JPEGMetadataCoverageFixture(
            "exif_thumbnail_out_of_bounds",
            "exif_thumbnail",
            "out_of_bounds",
            "quarantine",
            "exif_thumbnail_out_of_bounds",
            source(exif_missing),
        ),
        JPEGMetadataCoverageFixture(
            "maker_note_opaque",
            "maker_note",
            "opaque_complete",
            "accept",
            "coverage_complete_with_opaque",
            source(maker_complete),
        ),
        JPEGMetadataCoverageFixture(
            "maker_note_out_of_bounds",
            "maker_note",
            "out_of_bounds",
            "quarantine",
            "maker_note_out_of_bounds",
            source(maker_missing),
        ),
        JPEGMetadataCoverageFixture(
            "standard_xmp_only",
            "standard_xmp",
            "complete",
            "accept",
            "coverage_complete",
            source(main_only),
        ),
        JPEGMetadataCoverageFixture(
            "extended_xmp_in_order",
            "extended_xmp",
            "complete_in_order",
            "accept",
            "coverage_complete",
            source(main_extended, *extension_chunks),
        ),
        JPEGMetadataCoverageFixture(
            "extended_xmp_out_of_order",
            "extended_xmp",
            "complete_out_of_order",
            "accept",
            "coverage_complete",
            source(main_extended, *reversed(extension_chunks)),
        ),
        JPEGMetadataCoverageFixture(
            "extended_xmp_missing_chunk",
            "extended_xmp",
            "missing_chunk",
            "quarantine",
            "extended_xmp_incomplete",
            source(main_extended, extension_chunks[0]),
        ),
        JPEGMetadataCoverageFixture(
            "extended_xmp_duplicate_chunk",
            "extended_xmp",
            "duplicate_chunk",
            "quarantine",
            "extended_xmp_duplicate_offset",
            source(
                main_extended,
                extension_chunks[0],
                extension_chunks[0],
                extension_chunks[1],
            ),
        ),
        JPEGMetadataCoverageFixture(
            "extended_xmp_orphan",
            "extended_xmp",
            "orphan",
            "quarantine",
            "extended_xmp_orphan",
            source(orphan),
        ),
        JPEGMetadataCoverageFixture(
            "extended_xmp_guid_mismatch",
            "extended_xmp",
            "guid_mismatch",
            "quarantine",
            "extended_xmp_missing",
            source(main_extended, orphan),
        ),
        JPEGMetadataCoverageFixture(
            "iptc_iim_complete",
            "iptc_iim",
            "complete",
            "accept",
            "coverage_complete",
            source(iptc_complete),
        ),
        JPEGMetadataCoverageFixture(
            "iptc_iim_truncated_dataset",
            "iptc_iim",
            "truncated_dataset",
            "quarantine",
            "iptc_iim_dataset_overrun",
            source(iptc_truncated),
        ),
        JPEGMetadataCoverageFixture(
            "mixed_nested_complete",
            "mixed",
            "complete",
            "accept",
            "coverage_complete_with_opaque",
            source(
                make_jpeg_app_segment(
                    1,
                    _build_exif_payload(
                        thumbnail=thumbnail,
                        maker_note=maker_note,
                    ),
                ),
                main_extended,
                *extension_chunks,
                iptc_complete,
            ),
        ),
    )
    return fixtures


def _inspect_exif(payload: bytes, state: _CoverageState) -> None:
    """Inspect controlled IFD pointers, thumbnail, and maker-note payloads."""
    tiff = payload[len(_EXIF_IDENTIFIER) :]
    if len(tiff) < 8:
        raise _CoverageError("exif_header_truncated")
    if tiff[:2] == b"II":
        endian = "little"
    elif tiff[:2] == b"MM":
        endian = "big"
    else:
        raise _CoverageError("exif_byte_order_invalid")
    if int.from_bytes(tiff[2:4], endian) != 42:
        raise _CoverageError("exif_magic_invalid")
    ifd0_offset = int.from_bytes(tiff[4:8], endian)
    entries, next_ifd = _parse_ifd(tiff, ifd0_offset, endian, "exif_ifd0")
    exif_pointers = [entry for entry in entries if entry[0] == 0x8769]
    if len(exif_pointers) > 1:
        raise _CoverageError("exif_ifd_pointer_duplicate")
    if exif_pointers:
        state.relationships_declared += 1
        exif_offset = exif_pointers[0][3]
        sub_entries, _ = _parse_ifd(
            tiff, exif_offset, endian, "exif_sub_ifd"
        )
        maker_entries = [entry for entry in sub_entries if entry[0] == 0x927C]
        if len(maker_entries) > 1:
            raise _CoverageError("maker_note_duplicate")
        if maker_entries:
            maker = _entry_bytes(
                tiff,
                maker_entries[0],
                endian,
                "maker_note_out_of_bounds",
            )
            state.families.add("maker_note")
            state.recognized_components += 1
            state.opaque_components += 1
            state.maker_notes += 1
            state.maker_note_bytes += len(maker)
        state.relationships_resolved += 1
    if next_ifd:
        state.relationships_declared += 1
        thumbnail_entries, _ = _parse_ifd(
            tiff, next_ifd, endian, "exif_thumbnail_ifd"
        )
        offsets = [entry for entry in thumbnail_entries if entry[0] == 0x0201]
        lengths = [entry for entry in thumbnail_entries if entry[0] == 0x0202]
        if len(offsets) != 1 or len(lengths) != 1:
            raise _CoverageError("exif_thumbnail_pointer_incomplete")
        offset = offsets[0][3]
        length = lengths[0][3]
        if offset + length > len(tiff):
            raise _CoverageError("exif_thumbnail_out_of_bounds")
        thumbnail = tiff[offset : offset + length]
        if not thumbnail.startswith(b"\xff\xd8") or not thumbnail.endswith(
            b"\xff\xd9"
        ):
            raise _CoverageError("exif_thumbnail_jpeg_invalid")
        state.families.add("exif_thumbnail")
        state.recognized_components += 1
        state.exif_thumbnails += 1
        state.exif_thumbnail_bytes += len(thumbnail)
        state.relationships_resolved += 1


def _inspect_standard_xmp(
    payload: bytes, state: _CoverageState
) -> str | None:
    """Parse one standard XMP packet and return an extension GUID."""
    xml_bytes = payload[len(_XMP_IDENTIFIER) :]
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as error:
        raise _CoverageError("standard_xmp_xml_invalid") from error
    state.families.add("standard_xmp")
    state.recognized_components += 1
    state.standard_xmp_packets += 1
    candidates: list[str] = []
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] == "HasExtendedXMP" and element.text:
            candidates.append(element.text.strip())
        for name, value in element.attrib.items():
            if name.rsplit("}", 1)[-1] == "HasExtendedXMP":
                candidates.append(value.strip())
    if not candidates:
        return None
    if len(set(candidates)) != 1:
        raise _CoverageError("extended_xmp_reference_conflict")
    guid = candidates[0]
    if not _valid_extended_xmp_guid(guid):
        raise _CoverageError("extended_xmp_guid_invalid")
    state.relationships_declared += 1
    return guid


def _parse_extended_xmp_chunk(
    payload: bytes,
) -> tuple[str, int, int, bytes]:
    """Return the controlled Extended XMP chunk header and bytes."""
    body = payload[len(_EXTENDED_XMP_IDENTIFIER) :]
    if len(body) < 40:
        raise _CoverageError("extended_xmp_chunk_header_truncated")
    try:
        guid = body[:32].decode("ascii")
    except UnicodeDecodeError as error:
        raise _CoverageError("extended_xmp_guid_invalid") from error
    if not _valid_extended_xmp_guid(guid):
        raise _CoverageError("extended_xmp_guid_invalid")
    full_length = int.from_bytes(body[32:36], "big")
    offset = int.from_bytes(body[36:40], "big")
    chunk = body[40:]
    if full_length == 0 or offset + len(chunk) > full_length:
        raise _CoverageError("extended_xmp_chunk_out_of_bounds")
    return guid, full_length, offset, chunk


def _resolve_extended_xmp(
    references: list[str],
    chunks_by_guid: dict[str, list[tuple[int, int, bytes]]],
    state: _CoverageState,
) -> None:
    """Resolve main-packet GUIDs to complete, non-overlapping chunks."""
    if len(references) != len(set(references)):
        raise _CoverageError("extended_xmp_reference_duplicate")
    referenced = set(references)
    for guid in references:
        if guid not in chunks_by_guid:
            raise _CoverageError("extended_xmp_missing")
    if set(chunks_by_guid) - referenced:
        raise _CoverageError("extended_xmp_orphan")
    for guid in references:
        chunks = chunks_by_guid.get(guid)
        if not chunks:
            raise RuntimeError("a referenced extension was not collected")
        lengths = {full_length for full_length, _, _ in chunks}
        if len(lengths) != 1:
            raise _CoverageError("extended_xmp_length_conflict")
        full_length = next(iter(lengths))
        ordered = sorted(chunks, key=lambda item: item[1])
        expected_offset = 0
        output = bytearray()
        for _, offset, chunk in ordered:
            if offset < expected_offset:
                raise _CoverageError("extended_xmp_duplicate_offset")
            if offset > expected_offset:
                raise _CoverageError("extended_xmp_incomplete")
            output.extend(chunk)
            expected_offset += len(chunk)
        if expected_offset != full_length:
            raise _CoverageError("extended_xmp_incomplete")
        try:
            ET.fromstring(output)
        except ET.ParseError as error:
            raise _CoverageError("extended_xmp_xml_invalid") from error
        state.families.add("extended_xmp")
        state.recognized_components += 1
        state.extended_xmp_bytes += len(output)
        state.relationships_resolved += 1


def _inspect_photoshop_resources(
    payload: bytes, state: _CoverageState
) -> None:
    """Inspect controlled Photoshop IRBs and embedded IPTC IIM datasets."""
    body = payload[len(_PHOTOSHOP_IDENTIFIER) :]
    position = 0
    found = False
    while position < len(body):
        if position + 7 > len(body) or body[position : position + 4] != _PHOTOSHOP_SIGNATURE:
            raise _CoverageError("photoshop_irb_header_invalid")
        resource_id = int.from_bytes(body[position + 4 : position + 6], "big")
        position += 6
        name_length = body[position]
        position += 1
        if position + name_length > len(body):
            raise _CoverageError("photoshop_irb_name_overrun")
        position += name_length
        if (1 + name_length) % 2:
            position += 1
        if position + 4 > len(body):
            raise _CoverageError("photoshop_irb_size_truncated")
        size = int.from_bytes(body[position : position + 4], "big")
        position += 4
        if position + size > len(body):
            raise _CoverageError("photoshop_irb_data_overrun")
        data = body[position : position + size]
        position += size
        if size % 2:
            position += 1
        if position > len(body):
            raise _CoverageError("photoshop_irb_padding_overrun")
        if resource_id == _IPTC_RESOURCE_ID:
            state.relationships_declared += 1
            datasets = _parse_iptc_iim(data)
            state.families.add("iptc_iim")
            state.recognized_components += 1
            state.iptc_iim_blocks += 1
            state.iptc_iim_datasets += datasets
            state.relationships_resolved += 1
            found = True
    if not found:
        state.families.add("photoshop_irb")
        state.recognized_components += 1


def _parse_iptc_iim(data: bytes) -> int:
    """Count bounded, short-form IIM datasets in one controlled block."""
    position = 0
    count = 0
    while position < len(data):
        if position + 5 > len(data) or data[position] != 0x1C:
            raise _CoverageError("iptc_iim_dataset_header_invalid")
        length = int.from_bytes(data[position + 3 : position + 5], "big")
        position += 5
        if length & 0x8000:
            raise _CoverageError("iptc_iim_extended_length_unsupported")
        if position + length > len(data):
            raise _CoverageError("iptc_iim_dataset_overrun")
        position += length
        count += 1
    if count == 0:
        raise _CoverageError("iptc_iim_empty")
    return count


def _parse_ifd(
    tiff: bytes, offset: int, endian: str, label: str
) -> tuple[list[tuple[int, int, int, int]], int]:
    """Parse one bounded TIFF IFD into primitive entries."""
    if offset < 8 or offset + 2 > len(tiff):
        raise _CoverageError(f"{label}_out_of_bounds")
    count = int.from_bytes(tiff[offset : offset + 2], endian)
    entries_start = offset + 2
    entries_end = entries_start + count * 12
    if entries_end + 4 > len(tiff):
        raise _CoverageError(f"{label}_truncated")
    entries = []
    for index in range(count):
        start = entries_start + index * 12
        entry = tiff[start : start + 12]
        entries.append(
            (
                int.from_bytes(entry[:2], endian),
                int.from_bytes(entry[2:4], endian),
                int.from_bytes(entry[4:8], endian),
                int.from_bytes(entry[8:12], endian),
            )
        )
    next_ifd = int.from_bytes(tiff[entries_end : entries_end + 4], endian)
    return entries, next_ifd


def _entry_bytes(
    tiff: bytes,
    entry: tuple[int, int, int, int],
    endian: str,
    error_code: str,
) -> bytes:
    """Resolve one controlled BYTE/UNDEFINED TIFF entry."""
    _, field_type, count, value = entry
    if field_type not in (1, 7) or count == 0:
        raise _CoverageError(error_code)
    if count <= 4:
        return value.to_bytes(4, endian)[:count]
    if value + count > len(tiff):
        raise _CoverageError(error_code)
    return tiff[value : value + count]


def _finish(
    state: _CoverageState,
    decision: JPEGMetadataCoverageDecision,
    reason_code: str,
    resource_decision: str,
    resource_reason_code: str,
) -> JPEGMetadataCoverageResult:
    """Freeze mutable counters into one public result."""
    return JPEGMetadataCoverageResult(
        decision=decision,
        reason_code=reason_code,
        resource_decision=resource_decision,
        resource_reason_code=resource_reason_code,
        families=tuple(sorted(state.families)),
        recognized_components=state.recognized_components,
        opaque_components=state.opaque_components,
        relationships_declared=state.relationships_declared,
        relationships_resolved=state.relationships_resolved,
        exif_thumbnails=state.exif_thumbnails,
        exif_thumbnail_bytes=state.exif_thumbnail_bytes,
        maker_notes=state.maker_notes,
        maker_note_bytes=state.maker_note_bytes,
        standard_xmp_packets=state.standard_xmp_packets,
        extended_xmp_chunks=state.extended_xmp_chunks,
        extended_xmp_bytes=state.extended_xmp_bytes,
        iptc_iim_blocks=state.iptc_iim_blocks,
        iptc_iim_datasets=state.iptc_iim_datasets,
    )


def _build_exif_payload(
    *,
    thumbnail: bytes | None,
    maker_note: bytes | None,
    thumbnail_length_delta: int = 0,
    maker_note_offset_delta: int = 0,
) -> bytes:
    """Build a small TIFF graph containing controlled nested payloads."""
    endian = "little"
    ifd0_offset = 8
    ifd0_count = int(maker_note is not None)
    ifd0_size = 2 + ifd0_count * 12 + 4
    cursor = ifd0_offset + ifd0_size
    exif_ifd_offset = cursor if maker_note is not None else 0
    if maker_note is not None:
        cursor += 18
        maker_offset = cursor
        cursor += len(maker_note)
    else:
        maker_offset = 0
    thumbnail_ifd_offset = cursor if thumbnail is not None else 0
    if thumbnail is not None:
        cursor += 42
        thumbnail_offset = cursor
    else:
        thumbnail_offset = 0

    ifd0 = bytearray(ifd0_count.to_bytes(2, endian))
    if maker_note is not None:
        ifd0.extend((0x8769).to_bytes(2, endian))
        ifd0.extend((4).to_bytes(2, endian))
        ifd0.extend((1).to_bytes(4, endian))
        ifd0.extend(exif_ifd_offset.to_bytes(4, endian))
    ifd0.extend(thumbnail_ifd_offset.to_bytes(4, endian))

    parts = [
        b"II" + (42).to_bytes(2, endian) + ifd0_offset.to_bytes(4, endian),
        bytes(ifd0),
    ]
    if maker_note is not None:
        exif_ifd = bytearray((1).to_bytes(2, endian))
        exif_ifd.extend((0x927C).to_bytes(2, endian))
        exif_ifd.extend((7).to_bytes(2, endian))
        exif_ifd.extend(len(maker_note).to_bytes(4, endian))
        exif_ifd.extend(
            (maker_offset + maker_note_offset_delta).to_bytes(4, endian)
        )
        exif_ifd.extend(b"\x00\x00\x00\x00")
        parts.extend((bytes(exif_ifd), maker_note))
    if thumbnail is not None:
        thumbnail_ifd = bytearray((3).to_bytes(2, endian))
        thumbnail_ifd.extend(
            _ifd_entry(0x0103, 3, 1, 6, endian, short_inline=True)
        )
        thumbnail_ifd.extend(
            _ifd_entry(0x0201, 4, 1, thumbnail_offset, endian)
        )
        thumbnail_ifd.extend(
            _ifd_entry(
                0x0202,
                4,
                1,
                len(thumbnail) + thumbnail_length_delta,
                endian,
            )
        )
        thumbnail_ifd.extend(b"\x00\x00\x00\x00")
        parts.extend((bytes(thumbnail_ifd), thumbnail))
    return _EXIF_IDENTIFIER + b"".join(parts)


def _ifd_entry(
    tag: int,
    field_type: int,
    count: int,
    value: int,
    endian: str,
    *,
    short_inline: bool = False,
) -> bytes:
    """Serialize one controlled TIFF entry."""
    encoded = value.to_bytes(2 if short_inline else 4, endian)
    if short_inline:
        encoded += b"\x00\x00"
    return (
        tag.to_bytes(2, endian)
        + field_type.to_bytes(2, endian)
        + count.to_bytes(4, endian)
        + encoded
    )


def _build_standard_xmp_payload(guid: str | None) -> bytes:
    """Build one compact standard XMP packet with an optional GUID."""
    extension = (
        f' xmpNote:HasExtendedXMP="{guid}"' if guid is not None else ""
    )
    xml = (
        '<x:xmpmeta xmlns:x="adobe:ns:meta/" '
        'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
        'xmlns:xmpNote="http://ns.adobe.com/xmp/note/">'
        '<rdf:RDF><rdf:Description'
        f"{extension}"
        '/></rdf:RDF></x:xmpmeta>'
    ).encode("utf-8")
    return _XMP_IDENTIFIER + xml


def _build_extended_xmp_packet() -> bytes:
    """Build one deterministic XML packet used as an extension body."""
    return (
        '<x:xmpmeta xmlns:x="adobe:ns:meta/" '
        'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/">'
        '<rdf:RDF><rdf:Description><dc:description>'
        'Synthetic extended metadata payload'
        '</dc:description></rdf:Description></rdf:RDF></x:xmpmeta>'
    ).encode("utf-8")


def _build_extended_xmp_segment(
    guid: str, full_length: int, offset: int, chunk: bytes
) -> bytes:
    """Build one controlled Extended XMP APP1 chunk."""
    return make_jpeg_app_segment(
        1,
        _EXTENDED_XMP_IDENTIFIER
        + guid.encode("ascii")
        + full_length.to_bytes(4, "big")
        + offset.to_bytes(4, "big")
        + chunk,
    )


def _build_iptc_iim_block() -> bytes:
    """Build three short-form IIM datasets."""
    values = ((2, 5, b"Synthetic Object"), (2, 80, b"Synthetic Byline"), (2, 120, b"Controlled caption"))
    return b"".join(
        b"\x1c"
        + bytes((record, dataset))
        + len(value).to_bytes(2, "big")
        + value
        for record, dataset, value in values
    )


def _build_photoshop_payload(iim: bytes) -> bytes:
    """Wrap one IIM block in a Photoshop Image Resource Block."""
    name = b"\x00\x00"
    padding = b"\x00" if len(iim) % 2 else b""
    return (
        _PHOTOSHOP_IDENTIFIER
        + _PHOTOSHOP_SIGNATURE
        + _IPTC_RESOURCE_ID.to_bytes(2, "big")
        + name
        + len(iim).to_bytes(4, "big")
        + iim
        + padding
    )


def _minimal_nested_jpeg() -> bytes:
    """Return a framing-only nested JPEG for relationship testing."""
    return b"\xff\xd8\xff\xd9"


def _valid_extended_xmp_guid(value: str) -> bool:
    """Return whether a value is the controlled 32-hex GUID form."""
    return len(value) == 32 and all(
        character in "0123456789ABCDEF" for character in value
    )


def _header_segments(jpeg_bytes: bytes) -> tuple[tuple[int, bytes], ...]:
    """Return validated length-delimited header segments before SOS."""
    if len(jpeg_bytes) < 2 or not jpeg_bytes.startswith(b"\xff\xd8"):
        raise ValueError("missing_soi")
    segments: list[tuple[int, bytes]] = []
    position = 2
    while position < len(jpeg_bytes):
        if jpeg_bytes[position] != 0xFF:
            raise ValueError("expected_marker")
        while position < len(jpeg_bytes) and jpeg_bytes[position] == 0xFF:
            position += 1
        if position >= len(jpeg_bytes):
            raise ValueError("truncated_marker")
        marker = jpeg_bytes[position]
        position += 1
        if marker in (0xD9, 0xDA):
            break
        if marker in _STANDALONE_MARKERS:
            continue
        if position + 2 > len(jpeg_bytes):
            raise ValueError("truncated_segment_length")
        length = int.from_bytes(jpeg_bytes[position : position + 2], "big")
        if length < 2:
            raise ValueError("invalid_segment_length")
        start = position + 2
        end = position + length
        if end > len(jpeg_bytes):
            raise ValueError("segment_overrun")
        segments.append((marker, jpeg_bytes[start:end]))
        position = end
    return tuple(segments)


def _validate_base_jpeg(base_jpeg: bytes) -> None:
    """Validate a metadata-free carrier for fixture generation."""
    if not isinstance(base_jpeg, bytes) or not base_jpeg:
        raise TypeError("base_jpeg must be non-empty bytes")
    result = audit_jpeg_metadata_resources(base_jpeg)
    if not result.accepted:
        raise ValueError("base_jpeg must pass resource admission")
