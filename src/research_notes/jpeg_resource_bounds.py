"""Resource-bounded JPEG metadata admission and quarantine decisions."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Literal

from research_notes.jpeg_recovery import make_jpeg_app_segment


JPEGMetadataBoundaryDecision = Literal["accept", "quarantine", "reject"]

_EXIF_IDENTIFIER = b"Exif\x00\x00"
_XMP_IDENTIFIER = b"http://ns.adobe.com/xap/1.0/\x00"
_ICC_IDENTIFIER = b"ICC_PROFILE\x00"
_STANDALONE_MARKERS = {0x01, *range(0xD0, 0xD8)}
_METADATA_MARKERS = {0xFE, *range(0xE1, 0xF0)}
_TIFF_TYPE_WIDTHS = {
    1: 1,
    2: 1,
    3: 2,
    4: 4,
    5: 8,
    7: 1,
    9: 4,
    10: 8,
}


@dataclass(frozen=True)
class JPEGMetadataResourceBudget:
    """Explicit work ceilings for a JPEG metadata admission boundary."""

    max_header_segments: int = 64
    max_metadata_segments: int = 8
    max_metadata_bytes: int = 16384
    max_single_metadata_segment_bytes: int = 4096
    max_exif_entries: int = 16
    max_xmp_packet_bytes: int = 2048
    max_xmp_nodes: int = 32
    max_xmp_depth: int = 8
    max_xmp_text_bytes: int = 512
    max_icc_chunks: int = 4

    def __post_init__(self) -> None:
        """Validate every resource ceiling as a positive integer."""
        for name, value in self.as_dict().items():
            if not isinstance(value, int) or isinstance(value, bool):
                raise TypeError(f"{name} must be an integer")
            if value <= 0:
                raise ValueError(f"{name} must be positive")

    def as_dict(self) -> dict[str, int]:
        """Return the resource ceilings in a stable field order."""
        return {
            "max_header_segments": self.max_header_segments,
            "max_metadata_segments": self.max_metadata_segments,
            "max_metadata_bytes": self.max_metadata_bytes,
            "max_single_metadata_segment_bytes": (
                self.max_single_metadata_segment_bytes
            ),
            "max_exif_entries": self.max_exif_entries,
            "max_xmp_packet_bytes": self.max_xmp_packet_bytes,
            "max_xmp_nodes": self.max_xmp_nodes,
            "max_xmp_depth": self.max_xmp_depth,
            "max_xmp_text_bytes": self.max_xmp_text_bytes,
            "max_icc_chunks": self.max_icc_chunks,
        }


DEFAULT_JPEG_METADATA_RESOURCE_BUDGET = JPEGMetadataResourceBudget()


@dataclass(frozen=True)
class JPEGMetadataBoundaryResult:
    """One fail-closed metadata admission decision and its work counters."""

    decision: JPEGMetadataBoundaryDecision
    reason_code: str
    issue_codes: tuple[str, ...]
    header_scan_complete: bool
    image_data_reached: bool
    header_segments_seen: int
    header_segments_admitted: int
    metadata_segments_seen: int
    metadata_segments_admitted: int
    metadata_bytes_seen: int
    metadata_bytes_admitted: int
    largest_metadata_segment_seen: int
    largest_metadata_segment_admitted: int
    exif_entries_seen: int
    exif_entries_admitted: int
    xmp_packet_bytes_seen: int
    xmp_packet_bytes_admitted: int
    xmp_nodes_seen: int
    xmp_nodes_admitted: int
    xmp_depth_seen: int
    xmp_depth_admitted: int
    xmp_text_bytes_seen: int
    xmp_text_bytes_admitted: int
    icc_chunks_seen: int
    icc_chunks_admitted: int

    @property
    def accepted(self) -> bool:
        """Return whether the input may proceed to a downstream decoder."""
        return self.decision == "accept"


@dataclass(frozen=True)
class JPEGMetadataResourceFixture:
    """One deterministic synthetic boundary fixture and expected decision."""

    fixture: str
    resource_family: str
    boundary_relation: str
    expected_decision: JPEGMetadataBoundaryDecision
    expected_reason_code: str
    jpeg_bytes: bytes


@dataclass
class _AuditState:
    """Mutable counters used only during one bounded audit."""

    header_segments_seen: int = 0
    header_segments_admitted: int = 0
    metadata_segments_seen: int = 0
    metadata_segments_admitted: int = 0
    metadata_bytes_seen: int = 0
    metadata_bytes_admitted: int = 0
    largest_metadata_segment_seen: int = 0
    largest_metadata_segment_admitted: int = 0
    exif_entries_seen: int = 0
    exif_entries_admitted: int = 0
    xmp_packet_bytes_seen: int = 0
    xmp_packet_bytes_admitted: int = 0
    xmp_nodes_seen: int = 0
    xmp_nodes_admitted: int = 0
    xmp_depth_seen: int = 0
    xmp_depth_admitted: int = 0
    xmp_text_bytes_seen: int = 0
    xmp_text_bytes_admitted: int = 0
    icc_chunks_seen: int = 0
    icc_chunks_admitted: int = 0


class _QuarantineSignal(Exception):
    """Internal control flow for a fail-closed quarantine decision."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


def audit_jpeg_metadata_resources(
    jpeg_bytes: bytes,
    budget: JPEGMetadataResourceBudget = (
        DEFAULT_JPEG_METADATA_RESOURCE_BUDGET
    ),
) -> JPEGMetadataBoundaryResult:
    """Apply bounded metadata parsing before any image decoder is called.

    The input byte string is already resident in memory. This function bounds
    marker traversal and admitted metadata work; callers must independently
    bound file reads, request sizes, decoder pixels, process memory, and time.
    """
    if not isinstance(jpeg_bytes, bytes):
        raise TypeError("jpeg_bytes must be bytes")
    if not isinstance(budget, JPEGMetadataResourceBudget):
        raise TypeError("budget must be JPEGMetadataResourceBudget")

    state = _AuditState()
    if len(jpeg_bytes) < 2 or jpeg_bytes[:2] != b"\xff\xd8":
        return _finish(state, "reject", "missing_soi")

    position = 2
    icc_sequences: set[int] = set()
    icc_declared_counts: set[int] = set()
    while position < len(jpeg_bytes):
        if jpeg_bytes[position] != 0xFF:
            return _finish(state, "reject", "expected_marker")
        while position < len(jpeg_bytes) and jpeg_bytes[position] == 0xFF:
            position += 1
        if position >= len(jpeg_bytes):
            return _finish(state, "reject", "truncated_marker")
        marker = jpeg_bytes[position]
        position += 1

        state.header_segments_seen += 1
        if state.header_segments_seen > budget.max_header_segments:
            return _finish(
                state, "quarantine", "header_segment_limit_exceeded"
            )
        state.header_segments_admitted += 1

        if marker == 0xD9:
            return _finish(state, "reject", "missing_sos")
        if marker in _STANDALONE_MARKERS:
            continue
        if position + 2 > len(jpeg_bytes):
            return _finish(state, "reject", "truncated_segment_length")
        segment_length = int.from_bytes(
            jpeg_bytes[position : position + 2], "big"
        )
        if segment_length < 2:
            return _finish(state, "reject", "invalid_segment_length")
        payload_start = position + 2
        payload_end = position + segment_length
        if payload_end > len(jpeg_bytes):
            return _finish(state, "reject", "segment_overrun")
        payload_length = payload_end - payload_start
        position = payload_end

        if marker == 0xDA:
            icc_issue = _validate_icc_topology(
                icc_sequences, icc_declared_counts
            )
            if icc_issue:
                return _finish(state, "quarantine", icc_issue)
            return _finish(
                state,
                "accept",
                "within_resource_budget",
                header_scan_complete=True,
                image_data_reached=True,
            )

        if marker not in _METADATA_MARKERS:
            continue

        state.metadata_segments_seen += 1
        if state.metadata_segments_seen > budget.max_metadata_segments:
            return _finish(
                state, "quarantine", "metadata_segment_limit_exceeded"
            )
        state.metadata_segments_admitted += 1
        state.metadata_bytes_seen += payload_length
        state.largest_metadata_segment_seen = max(
            state.largest_metadata_segment_seen, payload_length
        )
        if payload_length > budget.max_single_metadata_segment_bytes:
            return _finish(
                state,
                "quarantine",
                "metadata_single_segment_limit_exceeded",
            )
        if (
            state.metadata_bytes_admitted + payload_length
            > budget.max_metadata_bytes
        ):
            return _finish(
                state, "quarantine", "metadata_byte_limit_exceeded"
            )
        state.metadata_bytes_admitted += payload_length
        state.largest_metadata_segment_admitted = max(
            state.largest_metadata_segment_admitted, payload_length
        )
        payload = jpeg_bytes[payload_start:payload_end]

        try:
            if marker == 0xE1 and payload.startswith(_EXIF_IDENTIFIER):
                _audit_exif_payload(payload, budget, state)
            elif marker == 0xE1 and payload.startswith(_XMP_IDENTIFIER):
                _audit_xmp_payload(payload, budget, state)
            elif marker == 0xE2 and payload.startswith(_ICC_IDENTIFIER):
                _audit_icc_payload(
                    payload,
                    budget,
                    state,
                    icc_sequences,
                    icc_declared_counts,
                )
        except _QuarantineSignal as signal:
            return _finish(state, "quarantine", signal.reason_code)

    return _finish(state, "reject", "missing_sos")


def build_resource_boundary_fixtures(
    base_jpeg: bytes,
    budget: JPEGMetadataResourceBudget = (
        DEFAULT_JPEG_METADATA_RESOURCE_BUDGET
    ),
) -> tuple[JPEGMetadataResourceFixture, ...]:
    """Build paired at-limit and over-limit JPEG metadata fixtures."""
    _validate_base_jpeg(base_jpeg)
    if not isinstance(budget, JPEGMetadataResourceBudget):
        raise TypeError("budget must be JPEGMetadataResourceBudget")

    baseline_header_segments = audit_jpeg_metadata_resources(
        base_jpeg, budget
    ).header_segments_seen
    if baseline_header_segments >= budget.max_header_segments:
        raise ValueError("base_jpeg leaves no header-segment fixture budget")

    fixtures = [
        JPEGMetadataResourceFixture(
            "baseline_mixed_metadata",
            "baseline",
            "control",
            "accept",
            "within_resource_budget",
            _insert_after_soi(base_jpeg, _baseline_metadata_segments()),
        ),
        _paired_fixture(
            base_jpeg,
            "header_segments_at_limit",
            "header_segments",
            "at_limit",
            b"\xff\x01"
            * (budget.max_header_segments - baseline_header_segments),
        ),
        _paired_fixture(
            base_jpeg,
            "header_segments_over_limit",
            "header_segments",
            "over_limit",
            b"\xff\x01"
            * (budget.max_header_segments - baseline_header_segments + 1),
            expected_decision="quarantine",
            expected_reason_code="header_segment_limit_exceeded",
        ),
        _paired_fixture(
            base_jpeg,
            "metadata_segments_at_limit",
            "metadata_segments",
            "at_limit",
            _opaque_segments(budget.max_metadata_segments, (1,)),
        ),
        _paired_fixture(
            base_jpeg,
            "metadata_segments_over_limit",
            "metadata_segments",
            "over_limit",
            _opaque_segments(budget.max_metadata_segments + 1, (1,)),
            expected_decision="quarantine",
            expected_reason_code="metadata_segment_limit_exceeded",
        ),
        _paired_fixture(
            base_jpeg,
            "metadata_bytes_at_limit",
            "metadata_bytes",
            "at_limit",
            _opaque_segments_for_total(
                budget.max_metadata_bytes,
                budget.max_single_metadata_segment_bytes,
            ),
        ),
        _paired_fixture(
            base_jpeg,
            "metadata_bytes_over_limit",
            "metadata_bytes",
            "over_limit",
            _opaque_segments_for_total(
                budget.max_metadata_bytes + 1,
                budget.max_single_metadata_segment_bytes,
            ),
            expected_decision="quarantine",
            expected_reason_code="metadata_byte_limit_exceeded",
        ),
        _paired_fixture(
            base_jpeg,
            "single_segment_at_limit",
            "single_segment_bytes",
            "at_limit",
            make_jpeg_app_segment(
                13, b"s" * budget.max_single_metadata_segment_bytes
            ),
        ),
        _paired_fixture(
            base_jpeg,
            "single_segment_over_limit",
            "single_segment_bytes",
            "over_limit",
            make_jpeg_app_segment(
                13, b"s" * (budget.max_single_metadata_segment_bytes + 1)
            ),
            expected_decision="quarantine",
            expected_reason_code="metadata_single_segment_limit_exceeded",
        ),
        _paired_fixture(
            base_jpeg,
            "exif_entries_at_limit",
            "exif_entries",
            "at_limit",
            make_jpeg_app_segment(
                1, _build_exif_payload(budget.max_exif_entries)
            ),
        ),
        _paired_fixture(
            base_jpeg,
            "exif_entries_over_limit",
            "exif_entries",
            "over_limit",
            make_jpeg_app_segment(
                1, _build_exif_payload(budget.max_exif_entries + 1)
            ),
            expected_decision="quarantine",
            expected_reason_code="exif_entry_limit_exceeded",
        ),
        _paired_fixture(
            base_jpeg,
            "xmp_packet_at_limit",
            "xmp_packet_bytes",
            "at_limit",
            make_jpeg_app_segment(
                1, _build_xmp_packet_bytes(budget.max_xmp_packet_bytes)
            ),
        ),
        _paired_fixture(
            base_jpeg,
            "xmp_packet_over_limit",
            "xmp_packet_bytes",
            "over_limit",
            make_jpeg_app_segment(
                1, _build_xmp_packet_bytes(budget.max_xmp_packet_bytes + 1)
            ),
            expected_decision="quarantine",
            expected_reason_code="xmp_packet_byte_limit_exceeded",
        ),
        _paired_fixture(
            base_jpeg,
            "xmp_nodes_at_limit",
            "xmp_nodes",
            "at_limit",
            make_jpeg_app_segment(
                1, _build_xmp_node_packet(budget.max_xmp_nodes)
            ),
        ),
        _paired_fixture(
            base_jpeg,
            "xmp_nodes_over_limit",
            "xmp_nodes",
            "over_limit",
            make_jpeg_app_segment(
                1, _build_xmp_node_packet(budget.max_xmp_nodes + 1)
            ),
            expected_decision="quarantine",
            expected_reason_code="xmp_node_limit_exceeded",
        ),
        _paired_fixture(
            base_jpeg,
            "xmp_depth_at_limit",
            "xmp_depth",
            "at_limit",
            make_jpeg_app_segment(
                1, _build_xmp_depth_packet(budget.max_xmp_depth)
            ),
        ),
        _paired_fixture(
            base_jpeg,
            "xmp_depth_over_limit",
            "xmp_depth",
            "over_limit",
            make_jpeg_app_segment(
                1, _build_xmp_depth_packet(budget.max_xmp_depth + 1)
            ),
            expected_decision="quarantine",
            expected_reason_code="xmp_depth_limit_exceeded",
        ),
        _paired_fixture(
            base_jpeg,
            "xmp_text_at_limit",
            "xmp_text_bytes",
            "at_limit",
            make_jpeg_app_segment(
                1, _build_xmp_text_packet(budget.max_xmp_text_bytes)
            ),
        ),
        _paired_fixture(
            base_jpeg,
            "xmp_text_over_limit",
            "xmp_text_bytes",
            "over_limit",
            make_jpeg_app_segment(
                1, _build_xmp_text_packet(budget.max_xmp_text_bytes + 1)
            ),
            expected_decision="quarantine",
            expected_reason_code="xmp_text_byte_limit_exceeded",
        ),
        _paired_fixture(
            base_jpeg,
            "icc_chunks_at_limit",
            "icc_chunks",
            "at_limit",
            _build_icc_segments(budget.max_icc_chunks),
        ),
        _paired_fixture(
            base_jpeg,
            "icc_chunks_over_limit",
            "icc_chunks",
            "over_limit",
            _build_icc_segments(budget.max_icc_chunks + 1),
            expected_decision="quarantine",
            expected_reason_code="icc_chunk_limit_exceeded",
        ),
        _paired_fixture(
            base_jpeg,
            "xmp_prohibited_doctype",
            "unsafe_xmp_syntax",
            "unsafe_syntax",
            make_jpeg_app_segment(
                1,
                _XMP_IDENTIFIER
                + b'<!DOCTYPE x [<!ENTITY y "z">]><x>&y;</x>',
            ),
            expected_decision="quarantine",
            expected_reason_code="xmp_prohibited_declaration",
        ),
        _paired_fixture(
            base_jpeg,
            "exif_invalid_magic",
            "invalid_metadata_syntax",
            "invalid_syntax",
            make_jpeg_app_segment(
                1,
                _EXIF_IDENTIFIER
                + b"MM\x00\x00"
                + (8).to_bytes(4, "big")
                + (0).to_bytes(2, "big")
                + b"\x00\x00\x00\x00",
            ),
            expected_decision="quarantine",
            expected_reason_code="exif_invalid_magic",
        ),
        JPEGMetadataResourceFixture(
            "segment_length_overrun",
            "container_framing",
            "malformed",
            "reject",
            "segment_overrun",
            b"\xff\xd8\xff\xe1\xff\xffx",
        ),
    ]
    return tuple(fixtures)


def boundary_observed_and_admitted(
    result: JPEGMetadataBoundaryResult,
    resource_family: str,
) -> tuple[int, int]:
    """Return comparable observed and admitted counters for one family."""
    fields = {
        "header_segments": (
            result.header_segments_seen,
            result.header_segments_admitted,
        ),
        "metadata_segments": (
            result.metadata_segments_seen,
            result.metadata_segments_admitted,
        ),
        "metadata_bytes": (
            result.metadata_bytes_seen,
            result.metadata_bytes_admitted,
        ),
        "single_segment_bytes": (
            result.largest_metadata_segment_seen,
            result.largest_metadata_segment_admitted,
        ),
        "exif_entries": (
            result.exif_entries_seen,
            result.exif_entries_admitted,
        ),
        "xmp_packet_bytes": (
            result.xmp_packet_bytes_seen,
            result.xmp_packet_bytes_admitted,
        ),
        "xmp_nodes": (
            result.xmp_nodes_seen,
            result.xmp_nodes_admitted,
        ),
        "xmp_depth": (
            result.xmp_depth_seen,
            result.xmp_depth_admitted,
        ),
        "xmp_text_bytes": (
            result.xmp_text_bytes_seen,
            result.xmp_text_bytes_admitted,
        ),
        "icc_chunks": (
            result.icc_chunks_seen,
            result.icc_chunks_admitted,
        ),
    }
    return fields.get(resource_family, (0, 0))


def boundary_limit_value(
    budget: JPEGMetadataResourceBudget, resource_family: str
) -> int:
    """Return the declared ceiling corresponding to one fixture family."""
    fields = {
        "header_segments": budget.max_header_segments,
        "metadata_segments": budget.max_metadata_segments,
        "metadata_bytes": budget.max_metadata_bytes,
        "single_segment_bytes": budget.max_single_metadata_segment_bytes,
        "exif_entries": budget.max_exif_entries,
        "xmp_packet_bytes": budget.max_xmp_packet_bytes,
        "xmp_nodes": budget.max_xmp_nodes,
        "xmp_depth": budget.max_xmp_depth,
        "xmp_text_bytes": budget.max_xmp_text_bytes,
        "icc_chunks": budget.max_icc_chunks,
    }
    return fields.get(resource_family, 0)


def _audit_exif_payload(
    payload: bytes,
    budget: JPEGMetadataResourceBudget,
    state: _AuditState,
) -> None:
    """Inspect one TIFF IFD0 without following nested IFD pointers."""
    tiff = payload[len(_EXIF_IDENTIFIER) :]
    if len(tiff) < 10:
        raise _QuarantineSignal("exif_truncated_tiff_header")
    if tiff[:2] == b"II":
        endian = "little"
    elif tiff[:2] == b"MM":
        endian = "big"
    else:
        raise _QuarantineSignal("exif_invalid_byte_order")
    if int.from_bytes(tiff[2:4], endian) != 42:
        raise _QuarantineSignal("exif_invalid_magic")
    ifd_offset = int.from_bytes(tiff[4:8], endian)
    if ifd_offset < 8 or ifd_offset + 2 > len(tiff):
        raise _QuarantineSignal("exif_ifd_offset_out_of_bounds")
    entry_count = int.from_bytes(
        tiff[ifd_offset : ifd_offset + 2], endian
    )
    state.exif_entries_seen += entry_count
    if state.exif_entries_seen > budget.max_exif_entries:
        raise _QuarantineSignal("exif_entry_limit_exceeded")
    entries_start = ifd_offset + 2
    entries_end = entries_start + entry_count * 12
    if entries_end + 4 > len(tiff):
        raise _QuarantineSignal("exif_truncated_ifd")
    for index in range(entry_count):
        entry_start = entries_start + index * 12
        entry = tiff[entry_start : entry_start + 12]
        field_type = int.from_bytes(entry[2:4], endian)
        value_count = int.from_bytes(entry[4:8], endian)
        if field_type not in _TIFF_TYPE_WIDTHS:
            raise _QuarantineSignal("exif_unsupported_field_type")
        value_bytes = _TIFF_TYPE_WIDTHS[field_type] * value_count
        if value_bytes > 4:
            value_offset = int.from_bytes(entry[8:12], endian)
            if value_offset + value_bytes > len(tiff):
                raise _QuarantineSignal("exif_value_out_of_bounds")
        state.exif_entries_admitted += 1


def _audit_xmp_payload(
    payload: bytes,
    budget: JPEGMetadataResourceBudget,
    state: _AuditState,
) -> None:
    """Incrementally inspect one bounded XMP packet."""
    xml_bytes = payload[len(_XMP_IDENTIFIER) :]
    state.xmp_packet_bytes_seen += len(xml_bytes)
    if state.xmp_packet_bytes_seen > budget.max_xmp_packet_bytes:
        raise _QuarantineSignal("xmp_packet_byte_limit_exceeded")
    state.xmp_packet_bytes_admitted += len(xml_bytes)
    upper = xml_bytes.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise _QuarantineSignal("xmp_prohibited_declaration")

    parser = ET.XMLPullParser(events=("start", "end"))
    depth = 0
    try:
        for start in range(0, len(xml_bytes), 64):
            parser.feed(xml_bytes[start : start + 64])
            for event, element in parser.read_events():
                if event == "start":
                    depth += 1
                    state.xmp_nodes_seen += 1
                    state.xmp_depth_seen = max(
                        state.xmp_depth_seen, depth
                    )
                    if state.xmp_nodes_seen > budget.max_xmp_nodes:
                        raise _QuarantineSignal(
                            "xmp_node_limit_exceeded"
                        )
                    if depth > budget.max_xmp_depth:
                        raise _QuarantineSignal(
                            "xmp_depth_limit_exceeded"
                        )
                    state.xmp_nodes_admitted += 1
                    state.xmp_depth_admitted = max(
                        state.xmp_depth_admitted, depth
                    )
                else:
                    text_bytes = len(
                        (element.text or "").encode("utf-8")
                    ) + len((element.tail or "").encode("utf-8"))
                    state.xmp_text_bytes_seen += text_bytes
                    if (
                        state.xmp_text_bytes_seen
                        > budget.max_xmp_text_bytes
                    ):
                        raise _QuarantineSignal(
                            "xmp_text_byte_limit_exceeded"
                        )
                    state.xmp_text_bytes_admitted += text_bytes
                    element.clear()
                    depth -= 1
        parser.close()
    except ET.ParseError as error:
        raise _QuarantineSignal("xmp_xml_invalid") from error


def _audit_icc_payload(
    payload: bytes,
    budget: JPEGMetadataResourceBudget,
    state: _AuditState,
    sequences: set[int],
    declared_counts: set[int],
) -> None:
    """Inspect ICC chunk topology without assembling the profile."""
    if len(payload) < 14:
        raise _QuarantineSignal("icc_truncated_chunk_header")
    sequence = payload[12]
    declared_count = payload[13]
    next_observed_chunk = state.icc_chunks_admitted + 1
    state.icc_chunks_seen = max(
        state.icc_chunks_seen, declared_count, next_observed_chunk
    )
    if (
        declared_count > budget.max_icc_chunks
        or next_observed_chunk > budget.max_icc_chunks
    ):
        raise _QuarantineSignal("icc_chunk_limit_exceeded")
    if sequence == 0 or declared_count == 0:
        raise _QuarantineSignal("icc_zero_sequence_or_count")
    if sequence > declared_count:
        raise _QuarantineSignal("icc_sequence_exceeds_count")
    if sequence in sequences:
        raise _QuarantineSignal("icc_duplicate_sequence")
    sequences.add(sequence)
    declared_counts.add(declared_count)
    state.icc_chunks_admitted += 1


def _validate_icc_topology(
    sequences: set[int], declared_counts: set[int]
) -> str:
    """Return a stable issue code for incomplete ICC chunk topology."""
    if not declared_counts:
        return ""
    if len(declared_counts) != 1:
        return "icc_inconsistent_chunk_count"
    declared_count = next(iter(declared_counts))
    if sequences != set(range(1, declared_count + 1)):
        return "icc_missing_sequence"
    return ""


def _finish(
    state: _AuditState,
    decision: JPEGMetadataBoundaryDecision,
    reason_code: str,
    *,
    header_scan_complete: bool = False,
    image_data_reached: bool = False,
) -> JPEGMetadataBoundaryResult:
    """Freeze the current counters into one public decision record."""
    issue_codes = () if decision == "accept" else (reason_code,)
    return JPEGMetadataBoundaryResult(
        decision=decision,
        reason_code=reason_code,
        issue_codes=issue_codes,
        header_scan_complete=header_scan_complete,
        image_data_reached=image_data_reached,
        header_segments_seen=state.header_segments_seen,
        header_segments_admitted=state.header_segments_admitted,
        metadata_segments_seen=state.metadata_segments_seen,
        metadata_segments_admitted=state.metadata_segments_admitted,
        metadata_bytes_seen=state.metadata_bytes_seen,
        metadata_bytes_admitted=state.metadata_bytes_admitted,
        largest_metadata_segment_seen=(
            state.largest_metadata_segment_seen
        ),
        largest_metadata_segment_admitted=(
            state.largest_metadata_segment_admitted
        ),
        exif_entries_seen=state.exif_entries_seen,
        exif_entries_admitted=state.exif_entries_admitted,
        xmp_packet_bytes_seen=state.xmp_packet_bytes_seen,
        xmp_packet_bytes_admitted=state.xmp_packet_bytes_admitted,
        xmp_nodes_seen=state.xmp_nodes_seen,
        xmp_nodes_admitted=state.xmp_nodes_admitted,
        xmp_depth_seen=state.xmp_depth_seen,
        xmp_depth_admitted=state.xmp_depth_admitted,
        xmp_text_bytes_seen=state.xmp_text_bytes_seen,
        xmp_text_bytes_admitted=state.xmp_text_bytes_admitted,
        icc_chunks_seen=state.icc_chunks_seen,
        icc_chunks_admitted=state.icc_chunks_admitted,
    )


def _paired_fixture(
    base_jpeg: bytes,
    fixture: str,
    resource_family: str,
    boundary_relation: str,
    envelope: bytes,
    *,
    expected_decision: JPEGMetadataBoundaryDecision = "accept",
    expected_reason_code: str = "within_resource_budget",
) -> JPEGMetadataResourceFixture:
    """Build one fixture from a controlled header envelope."""
    return JPEGMetadataResourceFixture(
        fixture=fixture,
        resource_family=resource_family,
        boundary_relation=boundary_relation,
        expected_decision=expected_decision,
        expected_reason_code=expected_reason_code,
        jpeg_bytes=_insert_after_soi(base_jpeg, envelope),
    )


def _insert_after_soi(base_jpeg: bytes, envelope: bytes) -> bytes:
    """Insert a deterministic metadata envelope after JPEG SOI."""
    return base_jpeg[:2] + envelope + base_jpeg[2:]


def _opaque_segments(count: int, payload_sizes: tuple[int, ...]) -> bytes:
    """Build APP13 segments with repeated controlled payload sizes."""
    return b"".join(
        make_jpeg_app_segment(
            13,
            bytes((65 + index % 26,))
            * payload_sizes[index % len(payload_sizes)],
        )
        for index in range(count)
    )


def _opaque_segments_for_total(total_bytes: int, maximum: int) -> bytes:
    """Split one exact metadata-byte total across bounded APP13 segments."""
    sizes: list[int] = []
    remaining = total_bytes
    while remaining:
        size = min(remaining, maximum)
        sizes.append(size)
        remaining -= size
    if not sizes:
        raise ValueError("total_bytes must be positive")
    return _opaque_segments(len(sizes), tuple(sizes))


def _build_exif_payload(entry_count: int) -> bytes:
    """Build a valid big-endian IFD0 with controlled inline SHORT values."""
    entries = bytearray()
    for index in range(entry_count):
        entries.extend((0xC000 + index).to_bytes(2, "big"))
        entries.extend((3).to_bytes(2, "big"))
        entries.extend((1).to_bytes(4, "big"))
        entries.extend((index % 65536).to_bytes(2, "big") + b"\x00\x00")
    return (
        _EXIF_IDENTIFIER
        + b"MM\x00*"
        + (8).to_bytes(4, "big")
        + entry_count.to_bytes(2, "big")
        + bytes(entries)
        + b"\x00\x00\x00\x00"
    )


def _build_xmp_packet_bytes(xml_bytes: int) -> bytes:
    """Build a valid XML packet with an exact byte length."""
    root = b"<x/>"
    if xml_bytes < len(root):
        raise ValueError("xml_bytes is too small for the controlled root")
    return _XMP_IDENTIFIER + root + b" " * (xml_bytes - len(root))


def _build_xmp_node_packet(node_count: int) -> bytes:
    """Build a shallow XML packet with an exact element count."""
    if node_count < 1:
        raise ValueError("node_count must be positive")
    return (
        _XMP_IDENTIFIER
        + b"<r>"
        + b"<n/>" * (node_count - 1)
        + b"</r>"
    )


def _build_xmp_depth_packet(depth: int) -> bytes:
    """Build a single-chain XML packet with an exact element depth."""
    if depth < 1:
        raise ValueError("depth must be positive")
    return (
        _XMP_IDENTIFIER
        + b"<n>" * depth
        + b"</n>" * depth
    )


def _build_xmp_text_packet(text_bytes: int) -> bytes:
    """Build an XML packet with an exact ASCII text payload."""
    return _XMP_IDENTIFIER + b"<x>" + b"t" * text_bytes + b"</x>"


def _build_icc_segments(chunk_count: int) -> bytes:
    """Build a complete controlled ICC chunk topology."""
    return b"".join(
        make_jpeg_app_segment(
            2,
            _ICC_IDENTIFIER
            + bytes((sequence, chunk_count))
            + bytes((sequence,)),
        )
        for sequence in range(1, chunk_count + 1)
    )


def _baseline_metadata_segments() -> bytes:
    """Build a small mixed EXIF, XMP, ICC, APP13, and COM envelope."""
    return (
        make_jpeg_app_segment(1, _build_exif_payload(1))
        + make_jpeg_app_segment(1, _build_xmp_node_packet(3))
        + _build_icc_segments(1)
        + make_jpeg_app_segment(13, b"controlled-opaque")
        + _make_comment_segment(b"controlled-comment")
    )


def _make_comment_segment(payload: bytes) -> bytes:
    """Build one bounded JPEG COM segment."""
    segment_length = len(payload) + 2
    return b"\xff\xfe" + segment_length.to_bytes(2, "big") + payload


def _validate_base_jpeg(base_jpeg: bytes) -> None:
    """Validate the controlled image carrier used by fixture generation."""
    if not isinstance(base_jpeg, bytes) or not base_jpeg:
        raise TypeError("base_jpeg must be non-empty bytes")
    if not base_jpeg.startswith(b"\xff\xd8"):
        raise ValueError("base_jpeg must start with a JPEG SOI marker")
    if b"\xff\xda" not in base_jpeg:
        raise ValueError("base_jpeg must contain a JPEG SOS marker")
