"""Bounded inspection of advanced ISO 10303-21 exchange structures."""

from __future__ import annotations

import base64
import io
import zipfile
from dataclasses import dataclass
from typing import Literal

from research_notes.step_brep import build_step_brep_fixtures
from research_notes.step_part21 import (
    DEFAULT_STEP_PARSE_LIMITS,
    STEPParseLimits,
    Part21ParseError as _STEPExchangeError,
    Part21Value,
    parse_part21_document,
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
    source = parse_part21_document(source_bytes, limits=limits)
    data_sections = tuple(
        STEPDataSection(
            section.name,
            section.schema_identifier,
            tuple(
                STEPExchangeEntity(
                    entity.entity_id,
                    tuple(
                        STEPExchangeRecord(
                            record.type_name,
                            tuple(
                                _convert_part21_value(value)
                                for value in record.arguments
                            ),
                        )
                        for record in entity.records
                    ),
                    entity.uses_subsuper_record,
                )
                for entity in section.entities
            ),
        )
        for section in source.data_sections
    )
    anchors = tuple(
        STEPAnchor(
            anchor.name,
            _convert_part21_value(anchor.item),
            anchor.tag_count,
        )
        for anchor in source.anchors
    )
    external_references = tuple(
        STEPExternalReference(
            STEPExchangeReference(
                reference.kind, reference.occurrence_name
            ),
            reference.resource,
        )
        for reference in source.external_references
    )
    return STEPExchangeDocument(
        schema_identifiers=source.schema_identifiers,
        data_sections=data_sections,
        anchors=anchors,
        external_references=external_references,
        signatures=tuple(
            STEPSignature(signature.payload_bytes)
            for signature in source.signatures
        ),
        reference_count=source.reference_count,
    )


def _convert_part21_value(value: Part21Value) -> object:
    reference_kind = {
        "entity_reference": "entity",
        "value_reference": "value",
        "constant_reference": "constant",
    }
    if value.kind in reference_kind:
        return STEPExchangeReference(
            reference_kind[value.kind], str(value.value)
        )
    if value.kind == "string":
        return str(value.value)
    if value.kind == "binary":
        return _Binary(str(value.value))
    if value.kind == "resource":
        return _Resource(str(value.value))
    if value.kind == "enumeration":
        return _Enumeration(str(value.value))
    if value.kind in {"integer", "real"}:
        return value.value
    if value.kind in {"omitted", "derived"}:
        return _Absent(str(value.value))
    if value.kind == "list":
        return tuple(_convert_part21_value(child) for child in value.children)
    if value.kind == "typed":
        return _TypedValue(
            str(value.value),
            tuple(_convert_part21_value(child) for child in value.children),
        )
    if value.kind == "keyword":
        return str(value.value)
    raise _STEPExchangeError(
        "quarantine",
        "parameter_kind_unsupported",
        f"{value.kind} is outside the exchange parameter subset",
        value.span,
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


def _container_kind(source_bytes: object) -> Literal["clear_text", "zip", "unknown"]:
    if not isinstance(source_bytes, bytes):
        return "unknown"
    if source_bytes.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        return "zip"
    return "clear_text"


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
