"""Bounded inspection of advanced ISO 10303-21 exchange structures."""

from __future__ import annotations

import base64
import binascii
import io
import math
import re
import zipfile
from dataclasses import dataclass
from typing import Literal

from research_notes.step_brep import (
    DEFAULT_STEP_PARSE_LIMITS,
    STEPParseLimits,
    build_step_brep_fixtures,
)


STEPExchangeDecision = Literal["accept", "quarantine", "reject"]


@dataclass(frozen=True)
class STEPExchangeReference:
    """An entity, value, or schema-constant occurrence name."""

    kind: Literal["entity", "value", "constant"]
    name: str


@dataclass(frozen=True)
class STEPExchangeRecord:
    """One simple record, including a component of a complex entity."""

    type_name: str
    arguments: tuple[object, ...]


@dataclass(frozen=True)
class STEPExchangeEntity:
    """One simple or complex entity instance from a DATA section."""

    entity_id: int
    records: tuple[STEPExchangeRecord, ...]
    uses_subsuper_record: bool

    @property
    def is_complex(self) -> bool:
        """Return whether the instance uses a subsuper record."""
        return self.uses_subsuper_record


@dataclass(frozen=True)
class STEPDataSection:
    """One parsed DATA section and its declared governing schema."""

    name: str | None
    schema_identifier: str | None
    entities: tuple[STEPExchangeEntity, ...]


@dataclass(frozen=True)
class STEPAnchor:
    """One ANCHOR entry without interpreting its application semantics."""

    name: str
    item: object
    tag_count: int


@dataclass(frozen=True)
class STEPExternalReference:
    """One REFERENCE association retained without resource retrieval."""

    occurrence: STEPExchangeReference
    resource: str


@dataclass(frozen=True)
class STEPSignature:
    """One syntactically valid Base64 signature payload."""

    payload_bytes: int


@dataclass(frozen=True)
class STEPExchangeDocument:
    """A bounded structural representation of a Part 21 exchange."""

    schema_identifiers: tuple[str, ...]
    data_sections: tuple[STEPDataSection, ...]
    anchors: tuple[STEPAnchor, ...]
    external_references: tuple[STEPExternalReference, ...]
    signatures: tuple[STEPSignature, ...]
    reference_count: int

    @property
    def entities(self) -> tuple[STEPExchangeEntity, ...]:
        """Return entities flattened in DATA-section order."""
        return tuple(
            entity
            for section in self.data_sections
            for entity in section.entities
        )


@dataclass(frozen=True)
class STEPExchangeInspection:
    """One fail-closed structural decision for a Part 21 input."""

    decision: STEPExchangeDecision
    reason_code: str
    container: Literal["clear_text", "zip", "unknown"]
    schema_identifiers: tuple[str, ...]
    data_section_count: int
    named_data_section_count: int
    entity_count: int
    simple_entity_count: int
    complex_entity_count: int
    anchor_count: int
    anchor_tag_count: int
    external_reference_count: int
    signature_count: int
    signature_payload_bytes: int
    local_reference_count: int
    unresolved_local_reference_count: int
    schema_conformance: Literal["not_evaluated"] = "not_evaluated"
    external_resolution: Literal["not_attempted"] = "not_attempted"
    signature_verification: Literal["not_attempted"] = "not_attempted"


@dataclass(frozen=True)
class STEPExchangeFixture:
    """One deterministic advanced Part 21 fixture and expected observation."""

    fixture: str
    condition: str
    file_name: str
    expected_decision: STEPExchangeDecision
    expected_reason_code: str
    expected_data_sections: int
    expected_entities: int
    expected_complex_entities: int
    expected_anchors: int
    expected_external_references: int
    expected_signatures: int
    source_bytes: bytes


@dataclass(frozen=True)
class _Token:
    kind: str
    value: str
    position: int


@dataclass(frozen=True)
class _Absent:
    marker: str


@dataclass(frozen=True)
class _Enumeration:
    value: str


@dataclass(frozen=True)
class _Binary:
    value: str


@dataclass(frozen=True)
class _Resource:
    value: str


@dataclass(frozen=True)
class _TypedValue:
    type_name: str
    arguments: tuple[object, ...]


class _STEPExchangeError(ValueError):
    def __init__(
        self,
        decision: STEPExchangeDecision,
        reason_code: str,
        message: str,
    ) -> None:
        super().__init__(message)
        self.decision = decision
        self.reason_code = reason_code


_NUMBER_RE = re.compile(
    r"[-+]?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:[Ee][-+]?\d+)?"
)
_IDENTIFIER_RE = re.compile(r"!?[A-Za-z_][A-Za-z0-9_-]*")
_BINARY_RE = re.compile(r"[0-3][0-9A-F]*")


def parse_step_exchange(
    source_bytes: bytes,
    *,
    limits: STEPParseLimits = DEFAULT_STEP_PARSE_LIMITS,
) -> STEPExchangeDocument:
    """Parse the controlled advanced Part 21 clear-text subset.

    This parser recognizes ordered exchange sections, multiple named DATA
    sections, complex entity instances, direct UTF-8 strings, binary values,
    anchors, external-reference declarations, and trailing signatures. It does
    not resolve external resources, verify CMS signatures, validate an EXPRESS
    schema, execute ECMAScript, or open archive containers.
    """
    _validate_input(source_bytes, limits)
    if _container_kind(source_bytes) == "zip":
        raise _STEPExchangeError(
            "quarantine",
            "archive_container_unsupported",
            "ZIP exchange containers are recognized but not opened",
        )
    try:
        text = source_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise _STEPExchangeError(
            "reject", "invalid_utf8", "exchange structure is not valid UTF-8"
        ) from error

    stream = _TokenStream(_tokenize(text, limits), limits)
    stream.expect_identifier("ISO-10303-21")
    stream.expect_symbol(";")
    stream.expect_identifier("HEADER")
    stream.expect_symbol(";")
    header_records = _parse_header(stream)
    schema_identifiers = _validate_header(header_records)

    anchors: tuple[STEPAnchor, ...] = ()
    if stream.matches_identifier("ANCHOR"):
        anchors = _parse_anchor_section(stream)

    external_references: tuple[STEPExternalReference, ...] = ()
    if stream.matches_identifier("REFERENCE"):
        external_references = _parse_reference_section(stream)

    data_sections: list[STEPDataSection] = []
    entity_ids: set[int] = set()
    while stream.matches_identifier("DATA"):
        data_sections.append(_parse_data_section(stream, entity_ids, limits))

    stream.expect_identifier("END-ISO-10303-21")
    stream.expect_symbol(";")
    signatures: list[STEPSignature] = []
    while stream.matches_identifier("SIGNATURE"):
        signatures.append(_parse_signature_section(stream))
    if not stream.at_end:
        raise _STEPExchangeError(
            "reject", "trailing_tokens", "tokens follow the final section"
        )

    _validate_data_sections(data_sections, schema_identifiers)
    reference_names = {
        reference.occurrence.name for reference in external_references
    }
    duplicate_occurrences = sorted(
        reference_names.intersection(f"#{entity_id}" for entity_id in entity_ids)
    )
    if duplicate_occurrences:
        raise _STEPExchangeError(
            "reject",
            "duplicate_occurrence_name",
            "an occurrence name is defined in REFERENCE and DATA",
        )

    values: list[object] = []
    for section in data_sections:
        for entity in section.entities:
            values.extend(record.arguments for record in entity.records)
    values.extend(anchor.item for anchor in anchors)
    occurrence_references = tuple(
        reference for value in values for reference in _references_in(value)
    )
    if len(occurrence_references) > limits.max_references:
        raise _STEPExchangeError(
            "quarantine",
            "reference_count_limit",
            "Part 21 occurrence reference count exceeds the configured limit",
        )

    return STEPExchangeDocument(
        schema_identifiers=schema_identifiers,
        data_sections=tuple(data_sections),
        anchors=anchors,
        external_references=external_references,
        signatures=tuple(signatures),
        reference_count=len(occurrence_references),
    )


def inspect_step_exchange(
    source_bytes: bytes,
    *,
    limits: STEPParseLimits = DEFAULT_STEP_PARSE_LIMITS,
) -> STEPExchangeInspection:
    """Return a bounded decision without resolving trust-boundary features."""
    container = _container_kind(source_bytes) if isinstance(source_bytes, bytes) else "unknown"
    try:
        document = parse_step_exchange(source_bytes, limits=limits)
    except _STEPExchangeError as error:
        return _empty_inspection(error.decision, error.reason_code, container)

    entities = document.entities
    entity_names = {f"#{entity.entity_id}" for entity in entities}
    external_names = {
        reference.occurrence.name for reference in document.external_references
    }
    references = tuple(
        reference
        for section in document.data_sections
        for entity in section.entities
        for record in entity.records
        for reference in _references_in(record.arguments)
    ) + tuple(
        reference
        for anchor in document.anchors
        for reference in _references_in(anchor.item)
    )
    unresolved = {
        reference.name
        for reference in references
        if reference.kind in {"entity", "value"}
        and reference.name not in entity_names
        and reference.name not in external_names
    }

    if unresolved:
        decision: STEPExchangeDecision = "quarantine"
        reason_code = "unresolved_local_reference"
    elif document.external_references:
        decision = "quarantine"
        reason_code = "external_reference_unresolved"
    elif document.signatures:
        decision = "quarantine"
        reason_code = "signature_unverified"
    else:
        decision = "accept"
        reason_code = "controlled_exchange_structure"

    return STEPExchangeInspection(
        decision=decision,
        reason_code=reason_code,
        container="clear_text",
        schema_identifiers=document.schema_identifiers,
        data_section_count=len(document.data_sections),
        named_data_section_count=sum(
            section.name is not None for section in document.data_sections
        ),
        entity_count=len(entities),
        simple_entity_count=sum(not entity.is_complex for entity in entities),
        complex_entity_count=sum(entity.is_complex for entity in entities),
        anchor_count=len(document.anchors),
        anchor_tag_count=sum(anchor.tag_count for anchor in document.anchors),
        external_reference_count=len(document.external_references),
        signature_count=len(document.signatures),
        signature_payload_bytes=sum(
            signature.payload_bytes for signature in document.signatures
        ),
        local_reference_count=len(references),
        unresolved_local_reference_count=len(unresolved),
    )


def build_step_exchange_fixtures() -> tuple[STEPExchangeFixture, ...]:
    """Build the deterministic v0.22 advanced Part 21 corpus."""
    fixtures = (
        STEPExchangeFixture(
            "single_data_control",
            "closed_tetrahedron_single_data_section",
            "single_data_control.step",
            "accept",
            "controlled_exchange_structure",
            1,
            74,
            0,
            0,
            0,
            0,
            _geometry_control_exchange(),
        ),
        STEPExchangeFixture(
            "multiple_data_sections",
            "two_named_schema_bound_sections",
            "multiple_data_sections.step",
            "accept",
            "controlled_exchange_structure",
            2,
            2,
            0,
            0,
            0,
            0,
            _exchange(
                "DATA('GEOMETRY',('DEMO_SCHEMA'));\n"
                "#1=POINT('origin',(0.,0.,0.));\nENDSEC;\n"
                "DATA('ATTRIBUTES',('DEMO_SCHEMA'));\n"
                "#2=LABEL('測定面',#1);\nENDSEC;"
            ),
        ),
        STEPExchangeFixture(
            "complex_entity_instance",
            "subsuper_record_with_three_components",
            "complex_entity_instance.step",
            "accept",
            "controlled_exchange_structure",
            1,
            1,
            1,
            0,
            0,
            0,
            _exchange(
                "DATA;\n#1=(REPRESENTATION_ITEM('curve') "
                "GEOMETRIC_REPRESENTATION_ITEM() CURVE());\nENDSEC;"
            ),
        ),
        STEPExchangeFixture(
            "utf8_binary_values",
            "direct_utf8_and_binary_tokens",
            "utf8_binary_values.step",
            "accept",
            "controlled_exchange_structure",
            1,
            1,
            0,
            0,
            0,
            0,
            _exchange("DATA;\n#1=PROPERTY('café 測定面',\"0A1F\");\nENDSEC;"),
        ),
        STEPExchangeFixture(
            "anchor_with_tag",
            "local_anchor_and_non_schema_tag",
            "anchor_with_tag.step",
            "accept",
            "controlled_exchange_structure",
            1,
            1,
            0,
            1,
            0,
            0,
            _exchange(
                "ANCHOR;\n<shape> = #1 {label:'primary'};\nENDSEC;\n"
                "DATA;\n#1=ITEM('anchored');\nENDSEC;"
            ),
        ),
        STEPExchangeFixture(
            "external_reference",
            "remote_resource_declared_but_not_fetched",
            "external_reference.step",
            "quarantine",
            "external_reference_unresolved",
            1,
            1,
            0,
            0,
            1,
            0,
            _exchange(
                "REFERENCE;\n"
                "#10=<https://example.invalid/model.step#shape>;\nENDSEC;\n"
                "DATA;\n#1=USE(#10);\nENDSEC;"
            ),
        ),
        STEPExchangeFixture(
            "signature_present",
            "base64_payload_present_without_cms_verification",
            "signature_present.step",
            "quarantine",
            "signature_unverified",
            1,
            1,
            0,
            0,
            0,
            2,
            _signed_exchange(),
        ),
        STEPExchangeFixture(
            "duplicate_entity_across_sections",
            "global_occurrence_name_collision",
            "duplicate_entity_across_sections.step",
            "reject",
            "duplicate_entity_id",
            0,
            0,
            0,
            0,
            0,
            0,
            _exchange(
                "DATA('A',('DEMO_SCHEMA'));\n#1=ITEM('a');\nENDSEC;\n"
                "DATA('B',('DEMO_SCHEMA'));\n#1=ITEM('b');\nENDSEC;"
            ),
        ),
        STEPExchangeFixture(
            "unnamed_multiple_data",
            "multiple_sections_without_required_parameters",
            "unnamed_multiple_data.step",
            "reject",
            "multiple_data_sections_require_names",
            0,
            0,
            0,
            0,
            0,
            0,
            _exchange("DATA;\n#1=ITEM('a');\nENDSEC;\nDATA;\n#2=ITEM('b');\nENDSEC;"),
        ),
        STEPExchangeFixture(
            "undeclared_data_schema",
            "section_schema_absent_from_file_schema",
            "undeclared_data_schema.step",
            "reject",
            "data_schema_not_declared",
            0,
            0,
            0,
            0,
            0,
            0,
            _exchange(
                "DATA('GEOMETRY',('OTHER_SCHEMA'));\n#1=ITEM('a');\nENDSEC;"
            ),
        ),
        STEPExchangeFixture(
            "invalid_binary",
            "binary_token_uses_non_hex_character",
            "invalid_binary.step",
            "reject",
            "invalid_binary",
            0,
            0,
            0,
            0,
            0,
            0,
            _exchange("DATA;\n#1=PROPERTY(\"0G\");\nENDSEC;"),
        ),
        STEPExchangeFixture(
            "deep_nesting",
            "aggregate_depth_exceeds_parser_budget",
            "deep_nesting.step",
            "quarantine",
            "nesting_depth_limit",
            0,
            0,
            0,
            0,
            0,
            0,
            _exchange(
                "DATA;\n#1=NESTED(" + "(" * 34 + "1" + ")" * 34 + ");\nENDSEC;"
            ),
        ),
        STEPExchangeFixture(
            "zip_archive",
            "part21_archive_recognized_without_extraction",
            "zip_archive.stpz",
            "quarantine",
            "archive_container_unsupported",
            0,
            0,
            0,
            0,
            0,
            0,
            _zip_exchange(),
        ),
    )
    return fixtures


def _validate_input(source_bytes: bytes, limits: STEPParseLimits) -> None:
    if not isinstance(source_bytes, bytes):
        raise TypeError("source_bytes must be bytes")
    if not isinstance(limits, STEPParseLimits):
        raise TypeError("limits must be STEPParseLimits")
    if len(source_bytes) > limits.max_file_bytes:
        raise _STEPExchangeError(
            "quarantine", "file_size_limit", "input exceeds the byte limit"
        )


def _container_kind(source_bytes: object) -> Literal["clear_text", "zip", "unknown"]:
    if not isinstance(source_bytes, bytes):
        return "unknown"
    if source_bytes.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        return "zip"
    return "clear_text"


def _parse_header(stream: _TokenStream) -> tuple[STEPExchangeRecord, ...]:
    records: list[STEPExchangeRecord] = []
    while not stream.matches_identifier("ENDSEC"):
        type_name = stream.pop_identifier()
        records.append(STEPExchangeRecord(type_name, stream.parse_argument_list(0)))
        stream.expect_symbol(";")
    stream.expect_identifier("ENDSEC")
    stream.expect_symbol(";")
    return tuple(records)


def _validate_header(records: tuple[STEPExchangeRecord, ...]) -> tuple[str, ...]:
    required = ("FILE_DESCRIPTION", "FILE_NAME", "FILE_SCHEMA")
    if tuple(record.type_name for record in records[:3]) != required:
        raise _STEPExchangeError(
            "reject",
            "invalid_header_order",
            "HEADER must begin with FILE_DESCRIPTION, FILE_NAME, FILE_SCHEMA",
        )
    if len(records) < 3:
        raise _STEPExchangeError(
            "reject", "invalid_header_order", "HEADER lacks required records"
        )
    schema_arguments = records[2].arguments
    if (
        len(schema_arguments) != 1
        or not isinstance(schema_arguments[0], tuple)
        or not schema_arguments[0]
        or not all(isinstance(value, str) for value in schema_arguments[0])
    ):
        raise _STEPExchangeError(
            "reject", "invalid_file_schema", "FILE_SCHEMA has an invalid shape"
        )
    schemas = tuple(value.upper() for value in schema_arguments[0])
    if len(set(schemas)) != len(schemas):
        raise _STEPExchangeError(
            "reject", "duplicate_file_schema", "FILE_SCHEMA repeats an identifier"
        )
    return schemas


def _parse_anchor_section(stream: _TokenStream) -> tuple[STEPAnchor, ...]:
    stream.expect_identifier("ANCHOR")
    stream.expect_symbol(";")
    anchors: list[STEPAnchor] = []
    seen: set[str] = set()
    while not stream.matches_identifier("ENDSEC"):
        name = stream.expect_kind("RESOURCE").value
        if name in seen:
            raise _STEPExchangeError(
                "reject", "duplicate_anchor_name", "ANCHOR name is repeated"
            )
        seen.add(name)
        stream.expect_symbol("=")
        item = stream.parse_value(0)
        tag_count = 0
        while stream.matches_symbol("{"):
            stream.expect_symbol("{")
            stream.pop_identifier()
            stream.expect_symbol(":")
            stream.parse_value(0)
            stream.expect_symbol("}")
            tag_count += 1
        stream.expect_symbol(";")
        anchors.append(STEPAnchor(name, item, tag_count))
    stream.expect_identifier("ENDSEC")
    stream.expect_symbol(";")
    return tuple(anchors)


def _parse_reference_section(
    stream: _TokenStream,
) -> tuple[STEPExternalReference, ...]:
    stream.expect_identifier("REFERENCE")
    stream.expect_symbol(";")
    references: list[STEPExternalReference] = []
    seen: set[str] = set()
    while not stream.matches_identifier("ENDSEC"):
        occurrence = stream.pop_occurrence()
        if occurrence.name in seen:
            raise _STEPExchangeError(
                "reject",
                "duplicate_reference_name",
                "REFERENCE occurrence name is repeated",
            )
        seen.add(occurrence.name)
        stream.expect_symbol("=")
        resource = stream.expect_kind("RESOURCE").value
        stream.expect_symbol(";")
        references.append(STEPExternalReference(occurrence, resource))
    stream.expect_identifier("ENDSEC")
    stream.expect_symbol(";")
    return tuple(references)


def _parse_data_section(
    stream: _TokenStream,
    seen_entity_ids: set[int],
    limits: STEPParseLimits,
) -> STEPDataSection:
    stream.expect_identifier("DATA")
    name: str | None = None
    schema: str | None = None
    if stream.matches_symbol("("):
        parameters = stream.parse_argument_list(0)
        if (
            len(parameters) != 2
            or not isinstance(parameters[0], str)
            or not isinstance(parameters[1], tuple)
            or len(parameters[1]) != 1
            or not isinstance(parameters[1][0], str)
        ):
            raise _STEPExchangeError(
                "reject",
                "invalid_data_section_parameters",
                "parameterized DATA requires a name and one schema identifier",
            )
        name = parameters[0]
        schema = parameters[1][0].upper()
    stream.expect_symbol(";")

    entities: list[STEPExchangeEntity] = []
    while not stream.matches_identifier("ENDSEC"):
        occurrence = stream.expect_kind("ENTITY_REFERENCE")
        entity_id = int(occurrence.value[1:])
        if entity_id in seen_entity_ids:
            raise _STEPExchangeError(
                "reject", "duplicate_entity_id", "entity identifier is repeated"
            )
        if len(seen_entity_ids) >= limits.max_entities:
            raise _STEPExchangeError(
                "quarantine",
                "entity_count_limit",
                "Part 21 entity count exceeds the configured limit",
            )
        seen_entity_ids.add(entity_id)
        stream.expect_symbol("=")
        uses_subsuper_record = stream.matches_symbol("(")
        if uses_subsuper_record:
            stream.expect_symbol("(")
            records: list[STEPExchangeRecord] = []
            while not stream.matches_symbol(")"):
                records.append(_parse_simple_record(stream))
            stream.expect_symbol(")")
            if not records:
                raise _STEPExchangeError(
                    "reject",
                    "invalid_complex_entity",
                    "complex entity requires at least one component record",
                )
        else:
            records = [_parse_simple_record(stream)]
        stream.expect_symbol(";")
        entities.append(
            STEPExchangeEntity(entity_id, tuple(records), uses_subsuper_record)
        )
    stream.expect_identifier("ENDSEC")
    stream.expect_symbol(";")
    return STEPDataSection(name, schema, tuple(entities))


def _parse_simple_record(stream: _TokenStream) -> STEPExchangeRecord:
    type_name = stream.pop_identifier()
    return STEPExchangeRecord(type_name, stream.parse_argument_list(0))


def _parse_signature_section(stream: _TokenStream) -> STEPSignature:
    stream.expect_identifier("SIGNATURE")
    stream.expect_symbol(";")
    parts: list[str] = []
    while not stream.matches_identifier("ENDSEC"):
        token = stream.pop()
        if token.kind not in {"IDENTIFIER", "NUMBER", "SYMBOL"} or (
            token.kind == "SYMBOL" and token.value not in {"+", "/", "="}
        ):
            raise _STEPExchangeError(
                "reject", "invalid_signature_base64", "signature is not Base64"
            )
        parts.append(token.value)
    stream.expect_identifier("ENDSEC")
    stream.expect_symbol(";")
    encoded = "".join(parts)
    try:
        payload = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as error:
        raise _STEPExchangeError(
            "reject", "invalid_signature_base64", "signature is not valid Base64"
        ) from error
    return STEPSignature(len(payload))


def _validate_data_sections(
    sections: list[STEPDataSection], schema_identifiers: tuple[str, ...]
) -> None:
    if len(sections) > 1 and any(section.name is None for section in sections):
        raise _STEPExchangeError(
            "reject",
            "multiple_data_sections_require_names",
            "each of multiple DATA sections must be parameterized",
        )
    names = [section.name for section in sections if section.name is not None]
    if len(set(names)) != len(names):
        raise _STEPExchangeError(
            "reject", "duplicate_data_section_name", "DATA section name is repeated"
        )
    for section in sections:
        if section.schema_identifier is not None:
            if section.schema_identifier not in schema_identifiers:
                raise _STEPExchangeError(
                    "reject",
                    "data_schema_not_declared",
                    "DATA schema is absent from FILE_SCHEMA",
                )
        elif len(schema_identifiers) != 1:
            raise _STEPExchangeError(
                "reject",
                "ambiguous_unnamed_data_schema",
                "unnamed DATA requires exactly one FILE_SCHEMA identifier",
            )


class _TokenStream:
    def __init__(self, tokens: list[_Token], limits: STEPParseLimits) -> None:
        self._tokens = tokens
        self._index = 0
        self._limits = limits

    @property
    def at_end(self) -> bool:
        return self._index == len(self._tokens)

    def _peek(self) -> _Token:
        if self.at_end:
            raise _STEPExchangeError(
                "reject", "unexpected_end", "unexpected end of exchange structure"
            )
        return self._tokens[self._index]

    def pop(self) -> _Token:
        token = self._peek()
        self._index += 1
        return token

    def expect_kind(self, kind: str) -> _Token:
        token = self.pop()
        if token.kind != kind:
            raise _STEPExchangeError(
                "reject", "unexpected_token", f"expected {kind} at {token.position}"
            )
        return token

    def pop_identifier(self) -> str:
        return self.expect_kind("IDENTIFIER").value.upper()

    def pop_occurrence(self) -> STEPExchangeReference:
        token = self.pop()
        if token.kind == "ENTITY_REFERENCE":
            return STEPExchangeReference("entity", token.value)
        if token.kind == "VALUE_REFERENCE":
            return STEPExchangeReference("value", token.value)
        raise _STEPExchangeError(
            "reject", "unexpected_token", f"expected occurrence at {token.position}"
        )

    def expect_identifier(self, value: str) -> None:
        token = self.expect_kind("IDENTIFIER")
        if token.value.upper() != value.upper():
            raise _STEPExchangeError(
                "reject", "unexpected_token", f"expected {value} at {token.position}"
            )

    def matches_identifier(self, value: str) -> bool:
        return (
            not self.at_end
            and self._peek().kind == "IDENTIFIER"
            and self._peek().value.upper() == value.upper()
        )

    def expect_symbol(self, value: str) -> None:
        token = self.expect_kind("SYMBOL")
        if token.value != value:
            raise _STEPExchangeError(
                "reject", "unexpected_token", f"expected {value} at {token.position}"
            )

    def matches_symbol(self, value: str) -> bool:
        return (
            not self.at_end
            and self._peek().kind == "SYMBOL"
            and self._peek().value == value
        )

    def parse_argument_list(self, depth: int) -> tuple[object, ...]:
        self.expect_symbol("(")
        if self.matches_symbol(")"):
            self.expect_symbol(")")
            return ()
        values = [self.parse_value(depth + 1)]
        while self.matches_symbol(","):
            self.expect_symbol(",")
            values.append(self.parse_value(depth + 1))
        self.expect_symbol(")")
        return tuple(values)

    def parse_value(self, depth: int) -> object:
        if depth > self._limits.max_nesting_depth:
            raise _STEPExchangeError(
                "quarantine",
                "nesting_depth_limit",
                "Part 21 aggregate nesting exceeds the configured limit",
            )
        token = self._peek()
        if token.kind in {"ENTITY_REFERENCE", "VALUE_REFERENCE", "CONSTANT_REFERENCE"}:
            self.pop()
            kind = {
                "ENTITY_REFERENCE": "entity",
                "VALUE_REFERENCE": "value",
                "CONSTANT_REFERENCE": "constant",
            }[token.kind]
            return STEPExchangeReference(kind, token.value)
        if token.kind == "STRING":
            self.pop()
            return token.value
        if token.kind == "BINARY":
            self.pop()
            return _Binary(token.value)
        if token.kind == "RESOURCE":
            self.pop()
            return _Resource(token.value)
        if token.kind == "ENUMERATION":
            self.pop()
            return _Enumeration(token.value.upper())
        if token.kind == "NUMBER":
            self.pop()
            return _parse_number(token)
        if token.kind == "SYMBOL" and token.value in {"$", "*"}:
            self.pop()
            return _Absent(token.value)
        if token.kind == "SYMBOL" and token.value == "(":
            return self.parse_argument_list(depth)
        if token.kind == "IDENTIFIER":
            type_name = self.pop_identifier()
            if not self.matches_symbol("("):
                return type_name
            return _TypedValue(type_name, self.parse_argument_list(depth))
        raise _STEPExchangeError(
            "reject", "unexpected_token", f"unexpected token at {token.position}"
        )


def _tokenize(text: str, limits: STEPParseLimits) -> list[_Token]:
    tokens: list[_Token] = []
    index = 0
    while index < len(text):
        character = text[index]
        if character.isspace():
            index += 1
            continue
        if text.startswith("/*", index):
            end = text.find("*/", index + 2)
            if end < 0:
                raise _STEPExchangeError(
                    "reject", "unterminated_comment", "comment is not terminated"
                )
            index = end + 2
            continue
        if character == "\\":
            raise _STEPExchangeError(
                "quarantine",
                "control_directive_unsupported",
                "Part 21 control directives are outside this controlled subset",
            )
        if character == "'":
            value, end = _read_quoted(text, index, "'", limits)
            tokens.append(_Token("STRING", value, index))
            index = end
            continue
        if character == '"':
            value, end = _read_quoted(text, index, '"', limits)
            if not _BINARY_RE.fullmatch(value):
                raise _STEPExchangeError(
                    "reject", "invalid_binary", "binary token is not Part 21 hex"
                )
            tokens.append(_Token("BINARY", value, index))
            index = end
            continue
        if character == "<":
            end = text.find(">", index + 1)
            if end < 0:
                raise _STEPExchangeError(
                    "reject", "unterminated_resource", "resource is not terminated"
                )
            value = text[index + 1 : end]
            _check_token_length(value, limits)
            tokens.append(_Token("RESOURCE", value, index))
            index = end + 1
            continue
        if character in {"#", "@"}:
            end = index + 1
            while end < len(text) and text[end].isdigit():
                end += 1
            if end > index + 1:
                kind = "ENTITY_REFERENCE" if character == "#" else "VALUE_REFERENCE"
                tokens.append(_Token(kind, text[index:end], index))
                index = end
                continue
            if character == "#":
                match = _IDENTIFIER_RE.match(text, index + 1)
                if match is not None:
                    value = text[index : match.end()]
                    _check_token_length(value, limits)
                    tokens.append(_Token("CONSTANT_REFERENCE", value, index))
                    index = match.end()
                    continue
            raise _STEPExchangeError(
                "reject", "invalid_occurrence_name", "occurrence name is invalid"
            )
        if character == ".":
            end = text.find(".", index + 1)
            if end > index + 1:
                value = text[index + 1 : end]
                if _IDENTIFIER_RE.fullmatch(value):
                    _check_token_length(value, limits)
                    tokens.append(_Token("ENUMERATION", value, index))
                    index = end + 1
                    continue
        number = _NUMBER_RE.match(text, index)
        if number is not None:
            value = number.group(0)
            _check_token_length(value, limits)
            tokens.append(_Token("NUMBER", value, index))
            index = number.end()
            continue
        identifier = _IDENTIFIER_RE.match(text, index)
        if identifier is not None:
            value = identifier.group(0)
            _check_token_length(value, limits)
            tokens.append(_Token("IDENTIFIER", value, index))
            index = identifier.end()
            continue
        if character in "(),;=$*{}:+/":
            tokens.append(_Token("SYMBOL", character, index))
            index += 1
            continue
        raise _STEPExchangeError(
            "reject", "illegal_character", f"illegal character at position {index}"
        )
    return tokens


def _read_quoted(
    text: str,
    start: int,
    quote: str,
    limits: STEPParseLimits,
) -> tuple[str, int]:
    index = start + 1
    output: list[str] = []
    while index < len(text):
        if text[index] == quote:
            if quote == "'" and index + 1 < len(text) and text[index + 1] == quote:
                output.append(quote)
                index += 2
                continue
            value = "".join(output)
            _check_token_length(value, limits)
            return value, index + 1
        output.append(text[index])
        index += 1
    raise _STEPExchangeError(
        "reject", "unterminated_string", "quoted value is not terminated"
    )


def _check_token_length(value: str, limits: STEPParseLimits) -> None:
    if len(value) > limits.max_token_chars:
        raise _STEPExchangeError(
            "quarantine", "token_length_limit", "token exceeds the length limit"
        )


def _parse_number(token: _Token) -> int | float:
    try:
        value: int | float
        if any(character in token.value.upper() for character in ".E"):
            value = float(token.value)
        else:
            value = int(token.value)
    except ValueError as error:
        raise _STEPExchangeError(
            "quarantine", "number_conversion_limit", "number cannot be represented"
        ) from error
    if isinstance(value, float) and not math.isfinite(value):
        raise _STEPExchangeError(
            "reject", "nonfinite_number", "number is not finite"
        )
    return value


def _references_in(value: object) -> tuple[STEPExchangeReference, ...]:
    if isinstance(value, STEPExchangeReference):
        return (value,)
    if isinstance(value, tuple):
        return tuple(
            reference for item in value for reference in _references_in(item)
        )
    if isinstance(value, _TypedValue):
        return _references_in(value.arguments)
    return ()


def _empty_inspection(
    decision: STEPExchangeDecision,
    reason_code: str,
    container: Literal["clear_text", "zip", "unknown"],
) -> STEPExchangeInspection:
    return STEPExchangeInspection(
        decision=decision,
        reason_code=reason_code,
        container=container,
        schema_identifiers=(),
        data_section_count=0,
        named_data_section_count=0,
        entity_count=0,
        simple_entity_count=0,
        complex_entity_count=0,
        anchor_count=0,
        anchor_tag_count=0,
        external_reference_count=0,
        signature_count=0,
        signature_payload_bytes=0,
        local_reference_count=0,
        unresolved_local_reference_count=0,
    )


def _exchange(body: str) -> bytes:
    text = (
        "ISO-10303-21;\n"
        "HEADER;\n"
        "FILE_DESCRIPTION(('Controlled synthetic exchange'),'3;1');\n"
        "FILE_NAME('fixture.step','2026-01-01T00:00:00',"
        "('research-notes'),('research-notes'),'','','');\n"
        "FILE_SCHEMA(('DEMO_SCHEMA'));\n"
        "ENDSEC;\n"
        f"{body}\n"
        "END-ISO-10303-21;\n"
    )
    return text.encode("utf-8")


def _geometry_control_exchange() -> bytes:
    fixtures = build_step_brep_fixtures()
    return next(
        fixture.step_bytes
        for fixture in fixtures
        if fixture.fixture == "closed_tetrahedron"
    )


def _signed_exchange() -> bytes:
    unsigned = _exchange("DATA;\n#1=ITEM('signed');\nENDSEC;")
    first = base64.b64encode(b"controlled-first-placeholder").decode("ascii")
    second = base64.b64encode(b"controlled-second-placeholder").decode("ascii")
    return unsigned + (
        f"SIGNATURE;\n{first}\nENDSEC;\n"
        f"SIGNATURE;\n{second}\nENDSEC;\n"
    ).encode("ascii")


def _zip_exchange() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        entry = zipfile.ZipInfo("ISO-10303.p21", date_time=(2026, 1, 1, 0, 0, 0))
        entry.compress_type = zipfile.ZIP_STORED
        entry.external_attr = 0o100644 << 16
        archive.writestr(entry, _exchange("DATA;\n#1=ITEM('archive');\nENDSEC;"))
    return buffer.getvalue()
