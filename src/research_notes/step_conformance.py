"""Controlled Part 21 edition, conformance, and transport evaluation."""

from __future__ import annotations

import base64
import io
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal

from research_notes.step_part21 import (
    DEFAULT_STEP_PARSE_LIMITS,
    STEPParseLimits,
    Part21Document,
    Part21ParseError,
    parse_part21_document,
)


Part21ConformanceDecision = Literal["accept", "quarantine", "reject"]


@dataclass(frozen=True)
class STEPArchiveLimits:
    """Explicit limits for inspecting one Part 21 ZIP transport."""

    max_archive_bytes: int = 2_000_000
    max_entries: int = 64
    max_total_uncompressed_bytes: int = 4_000_000
    max_root_bytes: int = 2_000_000
    max_compression_ratio: float = 100.0

    def __post_init__(self) -> None:
        for field_name, value in vars(self).items():
            if value <= 0:
                raise ValueError(f"{field_name} must be positive")


DEFAULT_STEP_ARCHIVE_LIMITS = STEPArchiveLimits()


@dataclass(frozen=True)
class Part21ConformanceResult:
    """A bounded syntax decision separated from schema conformance."""

    decision: Part21ConformanceDecision
    reason_code: str
    container: Literal["clear_text", "zip", "unknown"]
    implementation_level: str
    declared_edition: int
    required_edition: int
    declared_conformance_class: int
    required_conformance_class: int
    features: tuple[str, ...]
    data_section_count: int
    entity_count: int
    anchor_count: int
    external_reference_count: int
    signature_count: int
    source_bytes: int
    root_bytes: int
    archive_entry_count: int
    diagnostic_line: int | None
    diagnostic_column: int | None
    schema_conformance: Literal["not_evaluated"] = "not_evaluated"
    external_resolution: Literal["not_attempted"] = "not_attempted"
    signature_verification: Literal["not_attempted"] = "not_attempted"


@dataclass(frozen=True)
class Part21ConformanceFixture:
    """One deterministic edition or malformed-syntax fixture."""

    fixture: str
    category: str
    condition: str
    file_name: str
    expected_decision: Part21ConformanceDecision
    expected_reason_code: str
    expected_declared_edition: int
    expected_required_edition: int
    source_bytes: bytes


def inspect_part21_conformance(
    source_bytes: bytes,
    *,
    limits: STEPParseLimits = DEFAULT_STEP_PARSE_LIMITS,
    archive_limits: STEPArchiveLimits = DEFAULT_STEP_ARCHIVE_LIMITS,
) -> Part21ConformanceResult:
    """Check controlled Part 21 syntax and declared edition compatibility."""
    if not isinstance(source_bytes, bytes):
        raise TypeError("source_bytes must be bytes")
    if not isinstance(limits, STEPParseLimits):
        raise TypeError("limits must be STEPParseLimits")
    if not isinstance(archive_limits, STEPArchiveLimits):
        raise TypeError("archive_limits must be STEPArchiveLimits")

    container: Literal["clear_text", "zip"] = "clear_text"
    root_bytes = source_bytes
    archive_entry_count = 0
    if source_bytes.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        container = "zip"
        try:
            root_bytes, archive_entry_count = _read_archive_root(
                source_bytes, archive_limits
            )
        except Part21ParseError as error:
            return _failure_result(error, "zip", len(source_bytes))

    try:
        document = parse_part21_document(root_bytes, limits=limits)
        implementation_level = _implementation_level(document)
        declared_edition, declared_class = _decode_implementation_level(
            implementation_level
        )
        features = _document_features(document, container, archive_entry_count)
        required_edition = _required_edition(features)
        required_class = _required_conformance_class(features)
        if declared_edition < required_edition:
            return _document_result(
                document,
                decision="reject",
                reason_code="edition_feature_mismatch",
                container=container,
                implementation_level=implementation_level,
                declared_edition=declared_edition,
                required_edition=required_edition,
                declared_class=declared_class,
                required_class=required_class,
                features=features,
                source_bytes=len(source_bytes),
                root_bytes=len(root_bytes),
                archive_entry_count=archive_entry_count,
            )
        if declared_class < required_class:
            return _document_result(
                document,
                decision="reject",
                reason_code="conformance_class_mismatch",
                container=container,
                implementation_level=implementation_level,
                declared_edition=declared_edition,
                required_edition=required_edition,
                declared_class=declared_class,
                required_class=required_class,
                features=features,
                source_bytes=len(source_bytes),
                root_bytes=len(root_bytes),
                archive_entry_count=archive_entry_count,
            )
    except Part21ParseError as error:
        return _failure_result(
            error,
            container,
            len(source_bytes),
            root_bytes=len(root_bytes),
            archive_entry_count=archive_entry_count,
        )

    return _document_result(
        document,
        decision="accept",
        reason_code="controlled_syntax_conforms",
        container=container,
        implementation_level=implementation_level,
        declared_edition=declared_edition,
        required_edition=required_edition,
        declared_class=declared_class,
        required_class=required_class,
        features=features,
        source_bytes=len(source_bytes),
        root_bytes=len(root_bytes),
        archive_entry_count=archive_entry_count,
    )


def build_part21_conformance_fixtures() -> tuple[Part21ConformanceFixture, ...]:
    """Build deterministic positive and negative Part 21 syntax fixtures."""
    valid_signature = base64.b64encode(b"controlled-cms-placeholder").decode("ascii")
    fixtures = (
        _fixture("edition1_minimal", "edition", "edition_1_single_data", "2;1", "DATA;\n#1=ITEM('legacy');\nENDSEC;", "accept", "controlled_syntax_conforms", 1, 1),
        _fixture("edition1_legacy_x2", "character_encoding", "edition_1_x2_unicode_control", "2;1", "DATA;\n#1=LABEL('caf\\X2\\00E9\\X0\\');\nENDSEC;", "accept", "controlled_syntax_conforms", 1, 1),
        _fixture("edition1_legacy_controls", "character_encoding", "legacy_arbitrary_x4_page_and_print_controls", "2;1", "DATA;\n#1=LABEL('\\X\\A7','\\X4\\0001F642\\X0\\','\\PA\\\\S\\D','line\\N\\break','page\\F\\break');\nENDSEC;", "accept", "controlled_syntax_conforms", 1, 1),
        _fixture("edition1_binary", "binary", "valid_binary_with_unused_bit_count", "2;1", 'DATA;\n#1=PAYLOAD("23B");\nENDSEC;', "accept", "controlled_syntax_conforms", 1, 1),
        _fixture("edition1_comment", "comment", "non_nested_comment_between_tokens", "2;1", "DATA;\n#1=ITEM(/* human note */'commented');\nENDSEC;", "accept", "controlled_syntax_conforms", 1, 1),
        _fixture("edition2_multiple_data", "edition", "edition_2_named_data_sections", "3;1", "DATA('ONE',('DEMO_SCHEMA'));\n#1=ITEM('one');\nENDSEC;\nDATA('TWO',('DEMO_SCHEMA'));\n#2=ITEM('two');\nENDSEC;", "accept", "controlled_syntax_conforms", 2, 2),
        _fixture("edition2_section_context", "header", "edition_2_section_context_header", "3;1", "DATA;\n#1=ITEM('context');\nENDSEC;", "accept", "controlled_syntax_conforms", 2, 2, extra_header="SECTION_CONTEXT($,('controlled'));\n"),
        _fixture("edition3_utf8", "character_encoding", "edition_3_direct_utf8", "4;1", "DATA;\n#1=LABEL('café 測定面');\nENDSEC;", "accept", "controlled_syntax_conforms", 3, 3),
        _fixture("edition3_anchor", "anchor", "edition_3_anchor_and_tag", "4;1", "ANCHOR;\n<shape>=#1 {label:'primary'};\nENDSEC;\nDATA;\n#1=ITEM('anchored');\nENDSEC;", "accept", "controlled_syntax_conforms", 3, 3),
        _fixture("edition3_reference", "external_reference", "edition_3_entity_reference", "4;2", "REFERENCE;\n#10=<https://example.invalid/part.step#shape>;\nENDSEC;\nDATA;\n#1=USE(#10);\nENDSEC;", "accept", "controlled_syntax_conforms", 3, 3),
        _fixture("edition3_signature", "signature", "edition_3_base64_signature", "4;1", f"DATA;\n#1=ITEM('signed');\nENDSEC;\nEND-ISO-10303-21;\nSIGNATURE;\n{valid_signature}\nENDSEC;", "accept", "controlled_syntax_conforms", 3, 3, includes_end_marker=True),
        _fixture("edition3_constant", "constant", "edition_3_constant_value_reference", "4;3", "DATA;\n#1=MEASURE(@PI);\nENDSEC;", "accept", "controlled_syntax_conforms", 3, 3),
        _fixture("edition3_value_reference", "value_instance", "edition_3_external_value_instance", "4;3", "REFERENCE;\n@10=<https://example.invalid/part.step#value>;\nENDSEC;\nDATA;\n#1=USE(@10);\nENDSEC;", "accept", "controlled_syntax_conforms", 3, 3),
        _fixture("complex_entity", "entity_mapping", "subsuper_record", "2;1", "DATA;\n#1=(REPRESENTATION_ITEM('curve') CURVE());\nENDSEC;", "accept", "controlled_syntax_conforms", 1, 1),
        _fixture("user_defined_keyword", "keyword", "leading_exclamation_user_keyword", "2;1", "DATA;\n#1=!CONTROLLED(1.);\nENDSEC;", "accept", "controlled_syntax_conforms", 1, 1),
        _fixture("edition3_no_data", "edition", "edition_3_optional_data_section", "4;1", "", "accept", "controlled_syntax_conforms", 3, 3),
        _fixture("invalid_real_leading_dot", "number", "real_without_leading_digit", "2;1", "DATA;\n#1=VALUE(.5);\nENDSEC;", "reject", "invalid_real", 0, 0),
        _fixture("invalid_real_exponent", "number", "real_exponent_without_decimal_point", "2;1", "DATA;\n#1=VALUE(1E3);\nENDSEC;", "reject", "invalid_real", 0, 0),
        _fixture("lowercase_keyword", "keyword", "record_keyword_is_not_normalized", "2;1", "DATA;\n#1=item('lower');\nENDSEC;", "reject", "invalid_keyword", 0, 0),
        _fixture("unterminated_comment", "comment", "comment_reaches_end_of_file", "2;1", "DATA;\n#1=ITEM('before');\n/* never closed", "reject", "unterminated_comment", 0, 0),
        _fixture("invalid_binary", "binary", "binary_contains_non_hex_digit", "2;1", 'DATA;\n#1=PAYLOAD("04G");\nENDSEC;', "reject", "invalid_binary", 0, 0),
        _fixture("invalid_string_control", "character_encoding", "unknown_reverse_solidus_directive", "2;1", "DATA;\n#1=LABEL('\\Q\\bad');\nENDSEC;", "reject", "invalid_string_control_directive", 0, 0),
        _fixture("edition1_multiple_data", "edition", "edition_2_feature_declared_as_edition_1", "2;1", "DATA('ONE',('DEMO_SCHEMA'));\n#1=ITEM('one');\nENDSEC;\nDATA('TWO',('DEMO_SCHEMA'));\n#2=ITEM('two');\nENDSEC;", "reject", "edition_feature_mismatch", 1, 2),
        _fixture("edition2_direct_utf8", "character_encoding", "edition_3_utf8_declared_as_edition_2", "3;1", "DATA;\n#1=LABEL('測定面');\nENDSEC;", "reject", "edition_feature_mismatch", 2, 3),
        _fixture("edition2_anchor", "anchor", "edition_3_anchor_declared_as_edition_2", "3;1", "ANCHOR;\n<shape>=#1;\nENDSEC;\nDATA;\n#1=ITEM('a');\nENDSEC;", "reject", "edition_feature_mismatch", 2, 3),
        _fixture("reference_class_1", "external_reference", "reference_requires_class_2", "4;1", "REFERENCE;\n#10=<part.step#shape>;\nENDSEC;\nDATA;\n#1=USE(#10);\nENDSEC;", "reject", "conformance_class_mismatch", 3, 3),
        _fixture("constant_class_2", "constant", "constant_requires_class_3", "4;2", "DATA;\n#1=MEASURE(@PI);\nENDSEC;", "reject", "conformance_class_mismatch", 3, 3),
        _fixture("invalid_signature", "signature", "signature_is_not_base64", "4;1", "DATA;\n#1=ITEM('signed');\nENDSEC;\nEND-ISO-10303-21;\nSIGNATURE;\nnot_base64*\nENDSEC;", "reject", "invalid_signature_base64", 0, 0, includes_end_marker=True),
        _fixture("zero_occurrence", "occurrence_name", "all_zero_occurrence_name", "2;1", "DATA;\n#0=ITEM('zero');\nENDSEC;", "reject", "invalid_occurrence_name", 0, 0),
        _fixture("edition2_no_data", "edition", "optional_data_declared_as_edition_2", "3;1", "", "reject", "edition_feature_mismatch", 2, 3),
        Part21ConformanceFixture(
            "invalid_utf8",
            "character_encoding",
            "invalid_utf8_octet_after_exchange",
            "invalid_utf8.step",
            "reject",
            "invalid_utf8",
            0,
            0,
            _exchange("2;1", "DATA;\n#1=ITEM('valid');\nENDSEC;") + b"\xff",
        ),
    )
    archive_root = _exchange("4;1", "DATA;\n#1=ITEM('archive');\nENDSEC;")
    return fixtures + (
        Part21ConformanceFixture("zip_root", "archive", "bounded_zip_with_required_root", "zip_root.stpz", "accept", "controlled_syntax_conforms", 3, 3, _zip_bytes((("ISO-10303.p21", archive_root),))),
        Part21ConformanceFixture("zip_missing_root", "archive", "archive_has_no_required_root", "zip_missing_root.stpz", "reject", "archive_root_missing", 0, 0, _zip_bytes((("model.p21", archive_root),))),
        Part21ConformanceFixture("zip_unsafe_path", "archive", "archive_contains_parent_path", "zip_unsafe_path.stpz", "reject", "archive_unsafe_path", 0, 0, _zip_bytes((("ISO-10303.p21", archive_root), ("../escape.txt", b"blocked")))),
    )


def _fixture(
    fixture: str,
    category: str,
    condition: str,
    implementation_level: str,
    body: str,
    decision: Part21ConformanceDecision,
    reason_code: str,
    declared_edition: int,
    required_edition: int,
    *,
    extra_header: str = "",
    includes_end_marker: bool = False,
) -> Part21ConformanceFixture:
    return Part21ConformanceFixture(
        fixture,
        category,
        condition,
        f"{fixture}.step",
        decision,
        reason_code,
        declared_edition,
        required_edition,
        _exchange(
            implementation_level,
            body,
            extra_header=extra_header,
            includes_end_marker=includes_end_marker,
        ),
    )


def _exchange(
    implementation_level: str,
    body: str,
    *,
    extra_header: str = "",
    includes_end_marker: bool = False,
) -> bytes:
    prefix = (
        "ISO-10303-21;\n"
        "HEADER;\n"
        f"FILE_DESCRIPTION(('Controlled conformance fixture'),'{implementation_level}');\n"
        "FILE_NAME('fixture.step','2026-01-01T00:00:00',"
        "('research-notes'),('research-notes'),'','','');\n"
        "FILE_SCHEMA(('DEMO_SCHEMA'));\n"
        f"{extra_header}"
        "ENDSEC;\n"
    )
    suffix = "" if includes_end_marker else "\nEND-ISO-10303-21;\n"
    return (prefix + body + suffix).encode("utf-8")


def _zip_bytes(entries: tuple[tuple[str, bytes], ...]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in entries:
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, payload)
    return buffer.getvalue()


def _read_archive_root(
    source_bytes: bytes, limits: STEPArchiveLimits
) -> tuple[bytes, int]:
    if len(source_bytes) > limits.max_archive_bytes:
        raise Part21ParseError(
            "quarantine", "archive_size_limit", "archive exceeds the byte limit"
        )
    try:
        archive = zipfile.ZipFile(io.BytesIO(source_bytes))
    except (zipfile.BadZipFile, OSError) as error:
        raise Part21ParseError(
            "reject", "invalid_archive", "ZIP transport is malformed"
        ) from error
    with archive:
        entries = archive.infolist()
        if len(entries) > limits.max_entries:
            raise Part21ParseError(
                "quarantine", "archive_entry_limit", "archive has too many entries"
            )
        names = [entry.filename for entry in entries]
        if len(names) != len(set(names)):
            raise Part21ParseError(
                "reject", "archive_duplicate_name", "archive repeats an entry name"
            )
        total_size = 0
        for entry in entries:
            path = PurePosixPath(entry.filename.replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts:
                raise Part21ParseError(
                    "reject", "archive_unsafe_path", "archive entry path is unsafe"
                )
            if entry.flag_bits & 0x1:
                raise Part21ParseError(
                    "reject", "archive_encrypted", "encrypted archive entries are unsupported"
                )
            if entry.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                raise Part21ParseError(
                    "reject",
                    "archive_compression_unsupported",
                    "archive compression method is unsupported",
                )
            total_size += entry.file_size
            if total_size > limits.max_total_uncompressed_bytes:
                raise Part21ParseError(
                    "quarantine",
                    "archive_uncompressed_size_limit",
                    "archive expands beyond the total byte limit",
                )
            ratio = entry.file_size / max(entry.compress_size, 1)
            if ratio > limits.max_compression_ratio:
                raise Part21ParseError(
                    "quarantine",
                    "archive_compression_ratio_limit",
                    "archive entry exceeds the compression-ratio limit",
                )
        try:
            root = archive.getinfo("ISO-10303.p21")
        except KeyError as error:
            raise Part21ParseError(
                "reject", "archive_root_missing", "archive lacks ISO-10303.p21"
            ) from error
        if root.file_size > limits.max_root_bytes:
            raise Part21ParseError(
                "quarantine", "archive_root_size_limit", "archive root is too large"
            )
        with archive.open(root) as handle:
            payload = handle.read(limits.max_root_bytes + 1)
        if len(payload) > limits.max_root_bytes:
            raise Part21ParseError(
                "quarantine", "archive_root_size_limit", "archive root is too large"
            )
        return payload, len(entries)


def _implementation_level(document: Part21Document) -> str:
    record = document.header_records[0]
    if (
        record.type_name != "FILE_DESCRIPTION"
        or len(record.arguments) != 2
        or record.arguments[1].kind != "string"
    ):
        raise Part21ParseError(
            "reject",
            "invalid_file_description",
            "FILE_DESCRIPTION implementation_level is invalid",
            record.span,
        )
    return str(record.arguments[1].value)


def _decode_implementation_level(value: str) -> tuple[int, int]:
    mapping = {
        "1": (1, 1),
        "2;1": (1, 1),
        "2;2": (1, 2),
        "3;1": (2, 1),
        "3;2": (2, 2),
        "4;1": (3, 1),
        "4;2": (3, 2),
        "4;3": (3, 3),
    }
    try:
        return mapping[value]
    except KeyError as error:
        raise Part21ParseError(
            "reject",
            "unsupported_implementation_level",
            "implementation_level is outside the controlled edition table",
        ) from error


def _document_features(
    document: Part21Document,
    container: str,
    archive_entry_count: int,
) -> tuple[str, ...]:
    features: set[str] = set()
    if any(token.kind == "COMMENT" for token in document.tokens):
        features.add("comment")
    if any(token.kind == "BINARY" for token in document.tokens):
        features.add("binary")
    legacy_markers = ("\\N\\", "\\F\\", "\\P", "\\S\\", "\\X")
    if any(
        any(marker in token.raw for marker in legacy_markers)
        for token in document.tokens
        if token.kind == "STRING"
    ):
        features.add("legacy_string_control")
    if any(any(ord(character) > 127 for character in token.raw) for token in document.tokens if token.kind == "STRING"):
        features.add("direct_utf8")
    if len(document.data_sections) > 1:
        features.add("multiple_data_sections")
    if not document.data_sections:
        features.add("optional_data_section")
    if any(record.type_name in {"FILE_POPULATION", "SECTION_LANGUAGE", "SECTION_CONTEXT"} for record in document.header_records[3:]):
        features.add("edition2_header")
    if document.anchors:
        features.add("anchor_section")
    if document.external_references:
        features.add("reference_section")
    if document.signatures:
        features.add("signature_section")
    if any(token.kind == "CONSTANT_REFERENCE" for token in document.tokens):
        features.add("constant_reference")
    if any(token.kind == "VALUE_REFERENCE" for token in document.tokens):
        features.add("value_instance_reference")
    if container == "zip":
        features.add("zip_transport")
        if archive_entry_count > 1:
            features.add("multi_file_zip")
    return tuple(sorted(features))


def _required_edition(features: tuple[str, ...]) -> int:
    if set(features).intersection(
        {
            "anchor_section",
            "constant_reference",
            "direct_utf8",
            "optional_data_section",
            "reference_section",
            "signature_section",
            "value_instance_reference",
            "zip_transport",
        }
    ):
        return 3
    if set(features).intersection({"edition2_header", "multiple_data_sections"}):
        return 2
    return 1


def _required_conformance_class(features: tuple[str, ...]) -> int:
    if set(features).intersection({"constant_reference", "value_instance_reference"}):
        return 3
    if set(features).intersection({"reference_section", "multi_file_zip"}):
        return 2
    return 1


def _document_result(
    document: Part21Document,
    *,
    decision: Part21ConformanceDecision,
    reason_code: str,
    container: Literal["clear_text", "zip"],
    implementation_level: str,
    declared_edition: int,
    required_edition: int,
    declared_class: int,
    required_class: int,
    features: tuple[str, ...],
    source_bytes: int,
    root_bytes: int,
    archive_entry_count: int,
) -> Part21ConformanceResult:
    """Build a result while retaining parsed evidence for mismatch decisions."""
    return Part21ConformanceResult(
        decision=decision,
        reason_code=reason_code,
        container=container,
        implementation_level=implementation_level,
        declared_edition=declared_edition,
        required_edition=required_edition,
        declared_conformance_class=declared_class,
        required_conformance_class=required_class,
        features=features,
        data_section_count=len(document.data_sections),
        entity_count=len(document.entities),
        anchor_count=len(document.anchors),
        external_reference_count=len(document.external_references),
        signature_count=len(document.signatures),
        source_bytes=source_bytes,
        root_bytes=root_bytes,
        archive_entry_count=archive_entry_count,
        diagnostic_line=None,
        diagnostic_column=None,
    )


def _failure_result(
    error: Part21ParseError,
    container: Literal["clear_text", "zip"],
    source_bytes: int,
    *,
    root_bytes: int = 0,
    archive_entry_count: int = 0,
) -> Part21ConformanceResult:
    return Part21ConformanceResult(
        decision=error.decision,
        reason_code=error.reason_code,
        container=container,
        implementation_level="",
        declared_edition=0,
        required_edition=0,
        declared_conformance_class=0,
        required_conformance_class=0,
        features=(),
        data_section_count=0,
        entity_count=0,
        anchor_count=0,
        external_reference_count=0,
        signature_count=0,
        source_bytes=source_bytes,
        root_bytes=root_bytes,
        archive_entry_count=archive_entry_count,
        diagnostic_line=error.span.start_line if error.span else None,
        diagnostic_column=error.span.start_column if error.span else None,
    )
