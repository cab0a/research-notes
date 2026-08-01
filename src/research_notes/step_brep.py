"""Bounded STEP Part 21 parsing and controlled B-Rep topology inspection."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Literal


STEPDecision = Literal["accept", "quarantine", "reject"]


@dataclass(frozen=True)
class STEPParseLimits:
    """Explicit work limits for one Part 21 document."""

    max_file_bytes: int = 2_000_000
    max_entities: int = 20_000
    max_references: int = 100_000
    max_nesting_depth: int = 32
    max_token_chars: int = 16_384

    def __post_init__(self) -> None:
        for field_name, value in vars(self).items():
            if value <= 0:
                raise ValueError(f"{field_name} must be positive")


DEFAULT_STEP_PARSE_LIMITS = STEPParseLimits()


@dataclass(frozen=True)
class STEPReference:
    """Reference to one Part 21 entity instance."""

    entity_id: int


@dataclass(frozen=True)
class STEPEnumeration:
    """Part 21 enumeration value without surrounding periods."""

    value: str


@dataclass(frozen=True)
class STEPTypedValue:
    """Typed Part 21 parameter."""

    type_name: str
    arguments: tuple[object, ...]


@dataclass(frozen=True)
class STEPAbsentValue:
    """Omitted or derived Part 21 parameter."""

    marker: str


@dataclass(frozen=True)
class STEPEntity:
    """One parsed Part 21 entity instance."""

    entity_id: int
    type_name: str
    arguments: tuple[object, ...]


@dataclass(frozen=True)
class STEPDocument:
    """One bounded Part 21 document."""

    schema_identifiers: tuple[str, ...]
    entities: tuple[STEPEntity, ...]
    reference_count: int

    @property
    def entity_map(self) -> dict[int, STEPEntity]:
        """Return entities keyed by their Part 21 instance identifiers."""
        return {entity.entity_id: entity for entity in self.entities}


@dataclass(frozen=True)
class STEPFaceObservation:
    """Face-level topology and declared surface information."""

    face_index: int
    entity_id: int
    parent_shell_ids: tuple[int, ...]
    parent_solid_ids: tuple[int, ...]
    surface_entity_id: int
    surface_type: str
    same_sense: bool | None
    outer_bound_count: int
    inner_bound_count: int
    boundary_edge_count: int
    free_edge_count: int
    nonmanifold_edge_count: int
    adjacent_face_indices: tuple[int, ...]
    origin: tuple[float, float, float] | None
    axis: tuple[float, float, float] | None
    reference_direction: tuple[float, float, float] | None
    radius: float | None
    semi_angle: float | None
    major_radius: float | None
    minor_radius: float | None
    u_degree: int | None
    v_degree: int | None


@dataclass(frozen=True)
class STEPEdgeObservation:
    """Edge-level topology and declared curve information."""

    edge_index: int
    entity_id: int
    start_vertex_id: int
    end_vertex_id: int
    curve_entity_id: int
    curve_type: str
    same_sense: bool | None
    oriented_use_count: int
    incident_face_count: int
    incident_face_indices: tuple[int, ...]
    is_free: bool
    is_nonmanifold: bool


@dataclass(frozen=True)
class STEPShellObservation:
    """Shell-level topology and edge-incidence evidence."""

    shell_index: int
    entity_id: int
    shell_type: str
    face_entity_ids: tuple[int, ...]
    face_count: int
    edge_count: int
    free_edge_count: int
    nonmanifold_edge_count: int
    declared_closed: bool
    incidence_closed: bool
    parent_solid_ids: tuple[int, ...]


@dataclass(frozen=True)
class STEPSolidObservation:
    """Solid-level outer-shell inventory."""

    solid_index: int
    entity_id: int
    solid_type: str
    name: str
    outer_shell_id: int
    face_count: int
    edge_count: int


@dataclass(frozen=True)
class STEPInspectionResult:
    """One fail-closed Part 21 and B-Rep topology decision."""

    decision: STEPDecision
    reason_code: str
    schema_identifiers: tuple[str, ...]
    entity_count: int
    reference_count: int
    unresolved_reference_count: int
    faces: tuple[STEPFaceObservation, ...]
    edges: tuple[STEPEdgeObservation, ...]
    shells: tuple[STEPShellObservation, ...]
    solids: tuple[STEPSolidObservation, ...]

    @property
    def accepted(self) -> bool:
        """Return whether parsing and controlled topology resolution passed."""
        return self.decision == "accept"


@dataclass(frozen=True)
class STEPBRepFixture:
    """One deterministic synthetic Part 21 fixture and its expectations."""

    fixture: str
    condition: str
    expected_decision: STEPDecision
    expected_reason_code: str
    expected_faces: int
    expected_edges: int
    expected_shells: int
    expected_solids: int
    expected_free_edges: int
    step_bytes: bytes


@dataclass(frozen=True)
class _Token:
    kind: str
    value: str
    position: int


class _STEPParseError(ValueError):
    def __init__(
        self, decision: STEPDecision, reason_code: str, message: str
    ) -> None:
        super().__init__(message)
        self.decision = decision
        self.reason_code = reason_code


class _STEPTopologyError(ValueError):
    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


_NUMBER_RE = re.compile(
    r"[-+]?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:[Ee][-+]?\d+)?"
)
_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")


def parse_step_part21(
    step_bytes: bytes,
    *,
    limits: STEPParseLimits = DEFAULT_STEP_PARSE_LIMITS,
) -> STEPDocument:
    """Parse a bounded single-data-section ISO 10303-21 document.

    The parser implements the lexical and aggregate forms needed by the
    controlled v0.21 corpus. It deliberately does not claim full Part 21:2016
    coverage, EXPRESS schema validation, or geometric validity.
    """
    if not isinstance(step_bytes, bytes):
        raise TypeError("step_bytes must be bytes")
    if not isinstance(limits, STEPParseLimits):
        raise TypeError("limits must be STEPParseLimits")
    if len(step_bytes) > limits.max_file_bytes:
        raise _STEPParseError(
            "quarantine", "file_size_limit", "STEP file exceeds byte limit"
        )
    try:
        text = step_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise _STEPParseError(
            "reject", "invalid_utf8", "STEP file is not valid UTF-8"
        ) from error

    tokens = _tokenize(text, limits)
    stream = _TokenStream(tokens, limits)
    stream.expect_identifier("ISO-10303-21")
    stream.expect_symbol(";")
    stream.expect_identifier("HEADER")
    stream.expect_symbol(";")

    header_records: list[tuple[str, tuple[object, ...]]] = []
    while not stream.matches_identifier("ENDSEC"):
        type_name = stream.pop_identifier()
        arguments = stream.parse_argument_list(0)
        stream.expect_symbol(";")
        header_records.append((type_name, arguments))
    stream.expect_identifier("ENDSEC")
    stream.expect_symbol(";")
    stream.expect_identifier("DATA")
    if stream.matches_symbol("("):
        raise _STEPParseError(
            "quarantine",
            "parameterized_data_section_unsupported",
            "parameterized DATA sections are outside the controlled scope",
        )
    stream.expect_symbol(";")

    entities: list[STEPEntity] = []
    seen_ids: set[int] = set()
    while not stream.matches_identifier("ENDSEC"):
        reference = stream.expect_kind("REFERENCE")
        entity_id = _parse_reference_token(reference)
        if entity_id in seen_ids:
            raise _STEPParseError(
                "reject",
                "duplicate_entity_id",
                f"duplicate entity identifier #{entity_id}",
            )
        seen_ids.add(entity_id)
        if len(entities) >= limits.max_entities:
            raise _STEPParseError(
                "quarantine",
                "entity_count_limit",
                "STEP entity count exceeds limit",
            )
        stream.expect_symbol("=")
        if stream.matches_symbol("("):
            raise _STEPParseError(
                "quarantine",
                "complex_entity_unsupported",
                "complex entity instances are outside the controlled scope",
            )
        type_name = stream.pop_identifier()
        arguments = stream.parse_argument_list(0)
        stream.expect_symbol(";")
        entities.append(STEPEntity(entity_id, type_name, arguments))
    stream.expect_identifier("ENDSEC")
    stream.expect_symbol(";")
    stream.expect_identifier("END-ISO-10303-21")
    stream.expect_symbol(";")
    if not stream.at_end:
        raise _STEPParseError(
            "reject", "trailing_tokens", "tokens follow END-ISO-10303-21"
        )

    reference_count = sum(
        len(_references_in(entity.arguments)) for entity in entities
    )
    if reference_count > limits.max_references:
        raise _STEPParseError(
            "quarantine",
            "reference_count_limit",
            "STEP reference count exceeds limit",
        )
    return STEPDocument(
        schema_identifiers=_schema_identifiers(header_records),
        entities=tuple(entities),
        reference_count=reference_count,
    )


def inspect_step_brep(
    step_bytes: bytes,
    *,
    limits: STEPParseLimits = DEFAULT_STEP_PARSE_LIMITS,
) -> STEPInspectionResult:
    """Inspect controlled face, edge, shell, and solid relationships."""
    try:
        document = parse_step_part21(step_bytes, limits=limits)
    except _STEPParseError as error:
        return _empty_result(error.decision, error.reason_code)

    entity_map = document.entity_map
    unresolved = sorted(
        {
            reference.entity_id
            for entity in document.entities
            for reference in _references_in(entity.arguments)
            if reference.entity_id not in entity_map
        }
    )
    if unresolved:
        return STEPInspectionResult(
            decision="quarantine",
            reason_code="unresolved_reference",
            schema_identifiers=document.schema_identifiers,
            entity_count=len(document.entities),
            reference_count=document.reference_count,
            unresolved_reference_count=len(unresolved),
            faces=(),
            edges=(),
            shells=(),
            solids=(),
        )

    try:
        faces, face_edges = _inspect_faces(entity_map)
        shells = _inspect_shells(entity_map, face_edges)
        solids = _inspect_solids(entity_map, face_edges)
        faces = _attach_face_ownership_and_adjacency(
            faces, face_edges, shells, solids
        )
        edges = _inspect_edges(entity_map, face_edges, faces)
        shells = _attach_shell_ownership(shells, solids)
    except _STEPTopologyError as error:
        return STEPInspectionResult(
            decision="quarantine",
            reason_code=error.reason_code,
            schema_identifiers=document.schema_identifiers,
            entity_count=len(document.entities),
            reference_count=document.reference_count,
            unresolved_reference_count=0,
            faces=(),
            edges=(),
            shells=(),
            solids=(),
        )

    return STEPInspectionResult(
        decision="accept",
        reason_code="controlled_topology_resolved",
        schema_identifiers=document.schema_identifiers,
        entity_count=len(document.entities),
        reference_count=document.reference_count,
        unresolved_reference_count=0,
        faces=faces,
        edges=edges,
        shells=shells,
        solids=solids,
    )


def build_step_brep_fixtures() -> tuple[STEPBRepFixture, ...]:
    """Build the deterministic v0.21 synthetic Part 21 corpus."""
    closed = _build_tetrahedron_document(closed=True, two_solids=False)
    opened = _build_tetrahedron_document(closed=False, two_solids=False)
    two_solids = _build_tetrahedron_document(closed=True, two_solids=True)
    catalog = _build_surface_catalog_document()
    unresolved = _replace_first_oriented_edge_target(opened)
    duplicate = _duplicate_first_data_entity(closed)
    return (
        STEPBRepFixture(
            "closed_tetrahedron",
            "closed_shell_and_solid",
            "accept",
            "controlled_topology_resolved",
            4,
            6,
            1,
            1,
            0,
            closed,
        ),
        STEPBRepFixture(
            "open_tetrahedron",
            "one_face_removed",
            "accept",
            "controlled_topology_resolved",
            3,
            6,
            1,
            0,
            3,
            opened,
        ),
        STEPBRepFixture(
            "two_closed_solids",
            "two_disconnected_tetrahedra",
            "accept",
            "controlled_topology_resolved",
            8,
            12,
            2,
            2,
            0,
            two_solids,
        ),
        STEPBRepFixture(
            "surface_catalog",
            "six_declared_surface_types",
            "accept",
            "controlled_topology_resolved",
            6,
            18,
            1,
            0,
            18,
            catalog,
        ),
        STEPBRepFixture(
            "unresolved_reference",
            "missing_edge_target",
            "quarantine",
            "unresolved_reference",
            0,
            0,
            0,
            0,
            0,
            unresolved,
        ),
        STEPBRepFixture(
            "duplicate_entity_id",
            "duplicate_instance_identifier",
            "reject",
            "duplicate_entity_id",
            0,
            0,
            0,
            0,
            0,
            duplicate,
        ),
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
            raise _STEPParseError(
                "reject", "unexpected_end", "unexpected end of STEP file"
            )
        return self._tokens[self._index]

    def pop(self) -> _Token:
        token = self._peek()
        self._index += 1
        return token

    def expect_kind(self, kind: str) -> _Token:
        token = self.pop()
        if token.kind != kind:
            raise _STEPParseError(
                "reject",
                "unexpected_token",
                f"expected {kind} at {token.position}",
            )
        return token

    def pop_identifier(self) -> str:
        return self.expect_kind("IDENTIFIER").value.upper()

    def expect_identifier(self, value: str) -> None:
        token = self.expect_kind("IDENTIFIER")
        if token.value.upper() != value.upper():
            raise _STEPParseError(
                "reject",
                "unexpected_token",
                f"expected {value} at {token.position}",
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
            raise _STEPParseError(
                "reject",
                "unexpected_token",
                f"expected {value} at {token.position}",
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
            raise _STEPParseError(
                "quarantine",
                "nesting_depth_limit",
                "Part 21 aggregate nesting exceeds limit",
            )
        token = self._peek()
        if token.kind == "REFERENCE":
            self.pop()
            return STEPReference(_parse_reference_token(token))
        if token.kind == "STRING":
            self.pop()
            return token.value
        if token.kind == "BINARY":
            self.pop()
            return STEPTypedValue("BINARY", (token.value,))
        if token.kind == "ENUMERATION":
            self.pop()
            return STEPEnumeration(token.value.upper())
        if token.kind == "NUMBER":
            self.pop()
            return _parse_number_token(token)
        if token.kind == "SYMBOL" and token.value in {"$", "*"}:
            self.pop()
            return STEPAbsentValue(token.value)
        if token.kind == "SYMBOL" and token.value == "(":
            return self.parse_argument_list(depth)
        if token.kind == "IDENTIFIER":
            type_name = self.pop_identifier()
            if not self.matches_symbol("("):
                return type_name
            return STEPTypedValue(
                type_name, self.parse_argument_list(depth)
            )
        raise _STEPParseError(
            "reject",
            "unexpected_token",
            f"unexpected token at {token.position}",
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
                raise _STEPParseError(
                    "reject", "unterminated_comment", "unterminated comment"
                )
            index = end + 2
            continue
        if character == "'":
            value, index = _read_quoted(text, index, "'", limits)
            tokens.append(_Token("STRING", value, index))
            continue
        if character == '"':
            value, index = _read_quoted(text, index, '"', limits)
            tokens.append(_Token("BINARY", value, index))
            continue
        if character == "#":
            end = index + 1
            while end < len(text) and text[end].isdigit():
                end += 1
            if end == index + 1:
                raise _STEPParseError(
                    "reject", "invalid_reference", "reference lacks digits"
                )
            value = text[index:end]
            _check_token_length(value, limits)
            tokens.append(_Token("REFERENCE", value, index))
            index = end
            continue
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
        if character in "(),;=$*":
            tokens.append(_Token("SYMBOL", character, index))
            index += 1
            continue
        raise _STEPParseError(
            "reject",
            "illegal_character",
            f"illegal character at position {index}",
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
    raise _STEPParseError(
        "reject", "unterminated_string", "unterminated quoted value"
    )


def _check_token_length(value: str, limits: STEPParseLimits) -> None:
    if len(value) > limits.max_token_chars:
        raise _STEPParseError(
            "quarantine", "token_length_limit", "token exceeds length limit"
        )


def _parse_reference_token(token: _Token) -> int:
    try:
        return int(token.value[1:])
    except ValueError as error:
        raise _STEPParseError(
            "quarantine",
            "reference_conversion_limit",
            f"reference at {token.position} cannot be represented",
        ) from error


def _parse_number_token(token: _Token) -> int | float:
    try:
        if any(character in token.value.upper() for character in ".E"):
            value: int | float = float(token.value)
        else:
            value = int(token.value)
    except ValueError as error:
        raise _STEPParseError(
            "quarantine",
            "number_conversion_limit",
            f"number at {token.position} cannot be represented",
        ) from error
    if isinstance(value, float) and not math.isfinite(value):
        raise _STEPParseError(
            "reject",
            "nonfinite_number",
            f"number at {token.position} is not finite",
        )
    return value


def _schema_identifiers(
    header_records: list[tuple[str, tuple[object, ...]]],
) -> tuple[str, ...]:
    for type_name, arguments in header_records:
        if type_name == "FILE_SCHEMA" and arguments:
            first = arguments[0]
            if isinstance(first, tuple):
                return tuple(str(value) for value in first)
    return ()


def _references_in(value: object) -> tuple[STEPReference, ...]:
    if isinstance(value, STEPReference):
        return (value,)
    if isinstance(value, tuple):
        return tuple(
            reference for item in value for reference in _references_in(item)
        )
    if isinstance(value, STEPTypedValue):
        return _references_in(value.arguments)
    return ()


def _empty_result(
    decision: STEPDecision, reason_code: str
) -> STEPInspectionResult:
    return STEPInspectionResult(
        decision=decision,
        reason_code=reason_code,
        schema_identifiers=(),
        entity_count=0,
        reference_count=0,
        unresolved_reference_count=0,
        faces=(),
        edges=(),
        shells=(),
        solids=(),
    )


def _expect_reference(value: object, context: str) -> int:
    if not isinstance(value, STEPReference):
        raise _STEPTopologyError(
            "topology_relationship_incomplete", f"{context} is not a reference"
        )
    return value.entity_id


def _expect_reference_list(value: object, context: str) -> tuple[int, ...]:
    if not isinstance(value, tuple):
        raise _STEPTopologyError(
            "topology_relationship_incomplete", f"{context} is not an aggregate"
        )
    return tuple(_expect_reference(item, context) for item in value)


def _boolean(value: object) -> bool | None:
    if isinstance(value, STEPEnumeration):
        if value.value == "T":
            return True
        if value.value == "F":
            return False
    return None


def _inspect_faces(
    entity_map: dict[int, STEPEntity],
) -> tuple[tuple[STEPFaceObservation, ...], dict[int, tuple[int, ...]]]:
    face_entities = sorted(
        (
            entity
            for entity in entity_map.values()
            if entity.type_name in {"ADVANCED_FACE", "FACE_SURFACE"}
        ),
        key=lambda entity: entity.entity_id,
    )
    face_edges: dict[int, tuple[int, ...]] = {}
    faces: list[STEPFaceObservation] = []
    for face_index, entity in enumerate(face_entities):
        if len(entity.arguments) < 4:
            raise _STEPTopologyError(
                "topology_relationship_incomplete",
                f"face #{entity.entity_id} lacks required parameters",
            )
        bound_ids = _expect_reference_list(
            entity.arguments[1], f"face #{entity.entity_id} bounds"
        )
        surface_id = _expect_reference(
            entity.arguments[2], f"face #{entity.entity_id} surface"
        )
        if surface_id not in entity_map:
            raise _STEPTopologyError(
                "topology_relationship_incomplete",
                f"face #{entity.entity_id} surface is missing",
            )
        outer_count = 0
        inner_count = 0
        edges: list[int] = []
        for bound_id in bound_ids:
            bound = entity_map.get(bound_id)
            if bound is None or bound.type_name not in {
                "FACE_BOUND",
                "FACE_OUTER_BOUND",
            }:
                raise _STEPTopologyError(
                    "topology_relationship_incomplete",
                    f"face #{entity.entity_id} bound is unsupported",
                )
            if bound.type_name == "FACE_OUTER_BOUND":
                outer_count += 1
            else:
                inner_count += 1
            if len(bound.arguments) < 2:
                raise _STEPTopologyError(
                    "topology_relationship_incomplete",
                    f"bound #{bound_id} lacks a loop",
                )
            loop_id = _expect_reference(
                bound.arguments[1], f"bound #{bound_id} loop"
            )
            loop = entity_map.get(loop_id)
            if loop is None or loop.type_name != "EDGE_LOOP" or len(loop.arguments) < 2:
                raise _STEPTopologyError(
                    "topology_relationship_incomplete",
                    f"bound #{bound_id} does not reference an edge loop",
                )
            for oriented_id in _expect_reference_list(
                loop.arguments[1], f"loop #{loop_id} edges"
            ):
                oriented = entity_map.get(oriented_id)
                if (
                    oriented is None
                    or oriented.type_name != "ORIENTED_EDGE"
                    or len(oriented.arguments) < 5
                ):
                    raise _STEPTopologyError(
                        "topology_relationship_incomplete",
                        f"loop #{loop_id} contains an unsupported edge use",
                    )
                edges.append(
                    _expect_reference(
                        oriented.arguments[3],
                        f"oriented edge #{oriented_id} element",
                    )
                )
                edge = entity_map.get(edges[-1])
                if edge is None or edge.type_name != "EDGE_CURVE":
                    raise _STEPTopologyError(
                        "topology_relationship_incomplete",
                        f"oriented edge #{oriented_id} does not reference "
                        "an edge curve",
                    )
        face_edges[entity.entity_id] = tuple(dict.fromkeys(edges))
        surface = entity_map[surface_id]
        parameters = _surface_parameters(surface, entity_map)
        faces.append(
            STEPFaceObservation(
                face_index=face_index,
                entity_id=entity.entity_id,
                parent_shell_ids=(),
                parent_solid_ids=(),
                surface_entity_id=surface_id,
                surface_type=parameters["surface_type"],
                same_sense=_boolean(entity.arguments[3]),
                outer_bound_count=outer_count,
                inner_bound_count=inner_count,
                boundary_edge_count=len(face_edges[entity.entity_id]),
                free_edge_count=0,
                nonmanifold_edge_count=0,
                adjacent_face_indices=(),
                origin=parameters["origin"],
                axis=parameters["axis"],
                reference_direction=parameters["reference_direction"],
                radius=parameters["radius"],
                semi_angle=parameters["semi_angle"],
                major_radius=parameters["major_radius"],
                minor_radius=parameters["minor_radius"],
                u_degree=parameters["u_degree"],
                v_degree=parameters["v_degree"],
            )
        )
    return tuple(faces), face_edges


def _surface_parameters(
    surface: STEPEntity, entity_map: dict[int, STEPEntity]
) -> dict[str, object]:
    type_map = {
        "PLANE": "plane",
        "CYLINDRICAL_SURFACE": "cylinder",
        "CONICAL_SURFACE": "cone",
        "SPHERICAL_SURFACE": "sphere",
        "TOROIDAL_SURFACE": "torus",
        "B_SPLINE_SURFACE": "b_spline",
        "B_SPLINE_SURFACE_WITH_KNOTS": "b_spline",
        "RATIONAL_B_SPLINE_SURFACE": "b_spline",
    }
    result: dict[str, object] = {
        "surface_type": type_map.get(surface.type_name, "unsupported"),
        "origin": None,
        "axis": None,
        "reference_direction": None,
        "radius": None,
        "semi_angle": None,
        "major_radius": None,
        "minor_radius": None,
        "u_degree": None,
        "v_degree": None,
    }
    if surface.type_name.startswith("B_SPLINE_SURFACE"):
        if len(surface.arguments) >= 3:
            result["u_degree"] = _integer_or_none(surface.arguments[1])
            result["v_degree"] = _integer_or_none(surface.arguments[2])
        return result
    if len(surface.arguments) < 2:
        return result
    position_id = _expect_reference(
        surface.arguments[1], f"surface #{surface.entity_id} position"
    )
    origin, axis, reference_direction = _axis_placement(
        entity_map.get(position_id), entity_map
    )
    result.update(
        {
            "origin": origin,
            "axis": axis,
            "reference_direction": reference_direction,
        }
    )
    if surface.type_name == "CYLINDRICAL_SURFACE" and len(surface.arguments) >= 3:
        result["radius"] = _float_or_none(surface.arguments[2])
    elif surface.type_name == "CONICAL_SURFACE" and len(surface.arguments) >= 4:
        result["radius"] = _float_or_none(surface.arguments[2])
        result["semi_angle"] = _float_or_none(surface.arguments[3])
    elif surface.type_name == "SPHERICAL_SURFACE" and len(surface.arguments) >= 3:
        result["radius"] = _float_or_none(surface.arguments[2])
    elif surface.type_name == "TOROIDAL_SURFACE" and len(surface.arguments) >= 4:
        result["major_radius"] = _float_or_none(surface.arguments[2])
        result["minor_radius"] = _float_or_none(surface.arguments[3])
    return result


def _axis_placement(
    entity: STEPEntity | None, entity_map: dict[int, STEPEntity]
) -> tuple[
    tuple[float, float, float] | None,
    tuple[float, float, float] | None,
    tuple[float, float, float] | None,
]:
    if entity is None or entity.type_name != "AXIS2_PLACEMENT_3D":
        return None, None, None
    origin = _coordinates_from_reference(entity.arguments, 1, entity_map)
    axis = _coordinates_from_reference(entity.arguments, 2, entity_map)
    reference = _coordinates_from_reference(entity.arguments, 3, entity_map)
    return origin, axis, reference


def _coordinates_from_reference(
    arguments: tuple[object, ...],
    index: int,
    entity_map: dict[int, STEPEntity],
) -> tuple[float, float, float] | None:
    if index >= len(arguments) or not isinstance(arguments[index], STEPReference):
        return None
    entity = entity_map.get(arguments[index].entity_id)
    if entity is None or len(entity.arguments) < 2:
        return None
    values = entity.arguments[1]
    if not isinstance(values, tuple) or len(values) != 3:
        return None
    coordinates = tuple(_float_or_none(value) for value in values)
    if any(value is None for value in coordinates):
        return None
    return coordinates  # type: ignore[return-value]


def _float_or_none(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _integer_or_none(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _inspect_shells(
    entity_map: dict[int, STEPEntity],
    face_edges: dict[int, tuple[int, ...]],
) -> tuple[STEPShellObservation, ...]:
    shell_entities = sorted(
        (
            entity
            for entity in entity_map.values()
            if entity.type_name in {"CLOSED_SHELL", "OPEN_SHELL"}
        ),
        key=lambda entity: entity.entity_id,
    )
    shells = []
    for shell_index, entity in enumerate(shell_entities):
        if len(entity.arguments) < 2:
            raise _STEPTopologyError(
                "topology_relationship_incomplete",
                f"shell #{entity.entity_id} lacks faces",
            )
        face_ids = _expect_reference_list(
            entity.arguments[1], f"shell #{entity.entity_id} faces"
        )
        if len(face_ids) != len(set(face_ids)):
            raise _STEPTopologyError(
                "topology_relationship_ambiguous",
                f"shell #{entity.entity_id} repeats a face reference",
            )
        if any(face_id not in face_edges for face_id in face_ids):
            raise _STEPTopologyError(
                "topology_relationship_incomplete",
                f"shell #{entity.entity_id} references a non-face entity",
            )
        incidence = _edge_incidence(face_ids, face_edges)
        free_count = sum(count == 1 for count in incidence.values())
        nonmanifold_count = sum(count > 2 for count in incidence.values())
        shells.append(
            STEPShellObservation(
                shell_index=shell_index,
                entity_id=entity.entity_id,
                shell_type=entity.type_name.lower(),
                face_entity_ids=face_ids,
                face_count=len(face_ids),
                edge_count=len(incidence),
                free_edge_count=free_count,
                nonmanifold_edge_count=nonmanifold_count,
                declared_closed=entity.type_name == "CLOSED_SHELL",
                incidence_closed=(
                    bool(incidence)
                    and free_count == 0
                    and nonmanifold_count == 0
                ),
                parent_solid_ids=(),
            )
        )
    return tuple(shells)


def _inspect_solids(
    entity_map: dict[int, STEPEntity],
    face_edges: dict[int, tuple[int, ...]],
) -> tuple[STEPSolidObservation, ...]:
    solid_entities = sorted(
        (
            entity
            for entity in entity_map.values()
            if entity.type_name in {"MANIFOLD_SOLID_BREP", "BREP_WITH_VOIDS"}
        ),
        key=lambda entity: entity.entity_id,
    )
    solids = []
    for solid_index, entity in enumerate(solid_entities):
        if len(entity.arguments) < 2:
            raise _STEPTopologyError(
                "topology_relationship_incomplete",
                f"solid #{entity.entity_id} lacks an outer shell",
            )
        shell_id = _expect_reference(
            entity.arguments[1], f"solid #{entity.entity_id} shell"
        )
        shell = entity_map.get(shell_id)
        if shell is None or shell.type_name != "CLOSED_SHELL":
            raise _STEPTopologyError(
                "topology_relationship_incomplete",
                f"solid #{entity.entity_id} lacks a closed outer shell",
            )
        face_ids = _expect_reference_list(
            shell.arguments[1], f"shell #{shell_id} faces"
        )
        edge_ids = {
            edge_id
            for face_id in face_ids
            for edge_id in face_edges.get(face_id, ())
        }
        name = entity.arguments[0] if isinstance(entity.arguments[0], str) else ""
        solids.append(
            STEPSolidObservation(
                solid_index=solid_index,
                entity_id=entity.entity_id,
                solid_type=entity.type_name.lower(),
                name=name,
                outer_shell_id=shell_id,
                face_count=len(face_ids),
                edge_count=len(edge_ids),
            )
        )
    return tuple(solids)


def _attach_face_ownership_and_adjacency(
    faces: tuple[STEPFaceObservation, ...],
    face_edges: dict[int, tuple[int, ...]],
    shells: tuple[STEPShellObservation, ...],
    solids: tuple[STEPSolidObservation, ...],
) -> tuple[STEPFaceObservation, ...]:
    face_index = {face.entity_id: face.face_index for face in faces}
    edge_faces: dict[int, set[int]] = {}
    for face_id, edges in face_edges.items():
        for edge_id in edges:
            edge_faces.setdefault(edge_id, set()).add(face_id)
    shell_by_face: dict[int, list[int]] = {face.entity_id: [] for face in faces}
    for shell in shells:
        for face_id in shell.face_entity_ids:
            shell_by_face.setdefault(face_id, []).append(shell.entity_id)
    solid_by_shell: dict[int, list[int]] = {}
    for solid in solids:
        solid_by_shell.setdefault(solid.outer_shell_id, []).append(solid.entity_id)

    output = []
    for face in faces:
        adjacent_ids = {
            other_face
            for edge_id in face_edges[face.entity_id]
            for other_face in edge_faces.get(edge_id, set())
            if other_face != face.entity_id
        }
        incident_counts = [
            len(edge_faces.get(edge_id, set()))
            for edge_id in face_edges[face.entity_id]
        ]
        parent_shells = tuple(sorted(shell_by_face.get(face.entity_id, [])))
        parent_solids = tuple(
            sorted(
                {
                    solid_id
                    for shell_id in parent_shells
                    for solid_id in solid_by_shell.get(shell_id, [])
                }
            )
        )
        output.append(
            STEPFaceObservation(
                **{
                    **vars(face),
                    "parent_shell_ids": parent_shells,
                    "parent_solid_ids": parent_solids,
                    "free_edge_count": sum(count == 1 for count in incident_counts),
                    "nonmanifold_edge_count": sum(
                        count > 2 for count in incident_counts
                    ),
                    "adjacent_face_indices": tuple(
                        sorted(face_index[entity_id] for entity_id in adjacent_ids)
                    ),
                }
            )
        )
    return tuple(output)


def _inspect_edges(
    entity_map: dict[int, STEPEntity],
    face_edges: dict[int, tuple[int, ...]],
    faces: tuple[STEPFaceObservation, ...],
) -> tuple[STEPEdgeObservation, ...]:
    face_index = {face.entity_id: face.face_index for face in faces}
    edge_faces: dict[int, set[int]] = {}
    for face_id, edge_ids in face_edges.items():
        for edge_id in edge_ids:
            edge_faces.setdefault(edge_id, set()).add(face_id)
    oriented_counts: dict[int, int] = {}
    for entity in entity_map.values():
        if entity.type_name == "ORIENTED_EDGE" and len(entity.arguments) >= 4:
            edge_id = _expect_reference(
                entity.arguments[3], f"oriented edge #{entity.entity_id}"
            )
            oriented_counts[edge_id] = oriented_counts.get(edge_id, 0) + 1

    edge_entities = sorted(
        (
            entity
            for entity in entity_map.values()
            if entity.type_name == "EDGE_CURVE"
        ),
        key=lambda entity: entity.entity_id,
    )
    output = []
    for edge_index, entity in enumerate(edge_entities):
        if len(entity.arguments) < 5:
            raise _STEPTopologyError(
                "topology_relationship_incomplete",
                f"edge #{entity.entity_id} lacks required parameters",
            )
        start_id = _expect_reference(entity.arguments[1], "edge start")
        end_id = _expect_reference(entity.arguments[2], "edge end")
        curve_id = _expect_reference(entity.arguments[3], "edge curve")
        if entity_map[start_id].type_name != "VERTEX_POINT":
            raise _STEPTopologyError(
                "topology_relationship_incomplete",
                f"edge #{entity.entity_id} start is not a vertex point",
            )
        if entity_map[end_id].type_name != "VERTEX_POINT":
            raise _STEPTopologyError(
                "topology_relationship_incomplete",
                f"edge #{entity.entity_id} end is not a vertex point",
            )
        curve = entity_map.get(curve_id)
        incident = edge_faces.get(entity.entity_id, set())
        output.append(
            STEPEdgeObservation(
                edge_index=edge_index,
                entity_id=entity.entity_id,
                start_vertex_id=start_id,
                end_vertex_id=end_id,
                curve_entity_id=curve_id,
                curve_type=(
                    curve.type_name.lower() if curve is not None else "missing"
                ),
                same_sense=_boolean(entity.arguments[4]),
                oriented_use_count=oriented_counts.get(entity.entity_id, 0),
                incident_face_count=len(incident),
                incident_face_indices=tuple(
                    sorted(face_index[face_id] for face_id in incident)
                ),
                is_free=len(incident) == 1,
                is_nonmanifold=len(incident) > 2,
            )
        )
    return tuple(output)


def _attach_shell_ownership(
    shells: tuple[STEPShellObservation, ...],
    solids: tuple[STEPSolidObservation, ...],
) -> tuple[STEPShellObservation, ...]:
    return tuple(
        STEPShellObservation(
            **{
                **vars(shell),
                "parent_solid_ids": tuple(
                    solid.entity_id
                    for solid in solids
                    if solid.outer_shell_id == shell.entity_id
                ),
            }
        )
        for shell in shells
    )


def _edge_incidence(
    face_ids: tuple[int, ...], face_edges: dict[int, tuple[int, ...]]
) -> dict[int, int]:
    counts: dict[int, int] = {}
    for face_id in face_ids:
        for edge_id in face_edges[face_id]:
            counts[edge_id] = counts.get(edge_id, 0) + 1
    return counts


class _Part21Builder:
    def __init__(self) -> None:
        self._next_id = 1
        self._entities: list[str] = []

    def add(self, type_name: str, *arguments: str) -> int:
        entity_id = self._next_id
        self._next_id += 1
        self._entities.append(
            f"#{entity_id}={type_name}({','.join(arguments)});"
        )
        return entity_id

    def document(self, name: str) -> bytes:
        body = "\n".join(self._entities)
        text = (
            "ISO-10303-21;\n"
            "HEADER;\n"
            "FILE_DESCRIPTION(('Synthetic B-Rep topology fixture'),'2;1');\n"
            f"FILE_NAME('{name}.step','2000-01-01T00:00:00',"
            "('research-notes'),('research-notes'),'research-notes',"
            "'research-notes','');\n"
            "FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));\n"
            "ENDSEC;\n"
            "DATA;\n"
            f"{body}\n"
            "ENDSEC;\n"
            "END-ISO-10303-21;\n"
        )
        return text.encode("utf-8")


def _q(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _r(entity_id: int) -> str:
    return f"#{entity_id}"


def _refs(entity_ids: tuple[int, ...] | list[int]) -> str:
    return "(" + ",".join(_r(entity_id) for entity_id in entity_ids) + ")"


def _numbers(values: tuple[float, float, float]) -> str:
    return "(" + ",".join(f"{value:.6f}" for value in values) + ")"


def _add_point(
    builder: _Part21Builder, coordinates: tuple[float, float, float]
) -> tuple[int, int]:
    point = builder.add("CARTESIAN_POINT", _q(""), _numbers(coordinates))
    vertex = builder.add("VERTEX_POINT", _q(""), _r(point))
    return point, vertex


def _add_direction(
    builder: _Part21Builder, values: tuple[float, float, float]
) -> int:
    return builder.add("DIRECTION", _q(""), _numbers(values))


def _add_edge(
    builder: _Part21Builder,
    start: tuple[int, int, tuple[float, float, float]],
    end: tuple[int, int, tuple[float, float, float]],
) -> int:
    delta = tuple(end[2][index] - start[2][index] for index in range(3))
    magnitude = math.sqrt(sum(value * value for value in delta))
    direction = tuple(value / magnitude for value in delta)
    direction_id = _add_direction(builder, direction)  # type: ignore[arg-type]
    vector = builder.add("VECTOR", _q(""), _r(direction_id), f"{magnitude:.6f}")
    line = builder.add("LINE", _q(""), _r(start[0]), _r(vector))
    return builder.add(
        "EDGE_CURVE", _q(""), _r(start[1]), _r(end[1]), _r(line), ".T."
    )


def _add_plane(
    builder: _Part21Builder,
    location_id: int,
    normal: tuple[float, float, float],
) -> int:
    normal_magnitude = math.sqrt(sum(value * value for value in normal))
    normal = tuple(value / normal_magnitude for value in normal)
    axis = _add_direction(builder, normal)  # type: ignore[arg-type]
    reference = _add_direction(builder, (1.0, 0.0, 0.0))
    placement = builder.add(
        "AXIS2_PLACEMENT_3D",
        _q(""),
        _r(location_id),
        _r(axis),
        _r(reference),
    )
    return builder.add("PLANE", _q(""), _r(placement))


def _add_face(
    builder: _Part21Builder,
    edge_uses: tuple[tuple[int, bool], ...],
    surface_id: int,
) -> int:
    oriented = [
        builder.add(
            "ORIENTED_EDGE",
            _q(""),
            "*",
            "*",
            _r(edge_id),
            ".T." if orientation else ".F.",
        )
        for edge_id, orientation in edge_uses
    ]
    loop = builder.add("EDGE_LOOP", _q(""), _refs(oriented))
    bound = builder.add("FACE_OUTER_BOUND", _q(""), _r(loop), ".T.")
    return builder.add(
        "ADVANCED_FACE", _q(""), _refs((bound,)), _r(surface_id), ".T."
    )


def _add_tetrahedron(
    builder: _Part21Builder,
    *,
    offset: tuple[float, float, float],
    closed: bool,
    name: str,
) -> tuple[int, int | None]:
    local = (
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
    )
    coordinates = tuple(
        tuple(point[index] + offset[index] for index in range(3))
        for point in local
    )
    points = tuple(
        (*_add_point(builder, point), point) for point in coordinates
    )
    edge_pairs = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))
    edges = {
        pair: _add_edge(builder, points[pair[0]], points[pair[1]])
        for pair in edge_pairs
    }
    face_definitions = (
        (((0, 1), True), ((1, 2), True), ((0, 2), False), (0.0, 0.0, -1.0), 0),
        (((0, 1), True), ((1, 3), True), ((0, 3), False), (0.0, -1.0, 0.0), 0),
        (((0, 2), True), ((2, 3), True), ((0, 3), False), (-1.0, 0.0, 0.0), 0),
        (((1, 2), True), ((2, 3), True), ((1, 3), False), (1.0, 1.0, 1.0), 1),
    )
    selected = face_definitions if closed else face_definitions[:3]
    faces = []
    for first, second, third, normal, location_index in selected:
        surface = _add_plane(builder, points[location_index][0], normal)
        faces.append(
            _add_face(
                builder,
                (
                    (edges[first[0]], first[1]),
                    (edges[second[0]], second[1]),
                    (edges[third[0]], third[1]),
                ),
                surface,
            )
        )
    shell_type = "CLOSED_SHELL" if closed else "OPEN_SHELL"
    shell = builder.add(shell_type, _q(name), _refs(faces))
    solid = (
        builder.add("MANIFOLD_SOLID_BREP", _q(name), _r(shell))
        if closed
        else None
    )
    return shell, solid


def _build_tetrahedron_document(*, closed: bool, two_solids: bool) -> bytes:
    builder = _Part21Builder()
    _add_tetrahedron(
        builder, offset=(0.0, 0.0, 0.0), closed=closed, name="tetrahedron_a"
    )
    if two_solids:
        _add_tetrahedron(
            builder,
            offset=(3.0, 0.0, 0.0),
            closed=True,
            name="tetrahedron_b",
        )
    name = "two_closed_solids" if two_solids else (
        "closed_tetrahedron" if closed else "open_tetrahedron"
    )
    return builder.document(name)


def _build_surface_catalog_document() -> bytes:
    builder = _Part21Builder()
    surface_types = (
        "PLANE",
        "CYLINDRICAL_SURFACE",
        "CONICAL_SURFACE",
        "SPHERICAL_SURFACE",
        "TOROIDAL_SURFACE",
        "B_SPLINE_SURFACE",
    )
    faces = []
    for surface_index, surface_type in enumerate(surface_types):
        x_offset = float(surface_index * 4)
        coordinates = (
            (x_offset, 0.0, 0.0),
            (x_offset + 1.0, 0.0, 0.0),
            (x_offset, 1.0, 0.0),
        )
        points = tuple(
            (*_add_point(builder, point), point) for point in coordinates
        )
        edges = (
            _add_edge(builder, points[0], points[1]),
            _add_edge(builder, points[1], points[2]),
            _add_edge(builder, points[0], points[2]),
        )
        if surface_type == "B_SPLINE_SURFACE":
            fourth_point, _ = _add_point(
                builder, (x_offset + 1.0, 1.0, 0.2)
            )
            control_points = (
                f"(({_r(points[0][0])},{_r(points[1][0])}),"
                f"({_r(points[2][0])},{_r(fourth_point)}))"
            )
            surface = builder.add(
                surface_type,
                _q(""),
                "1",
                "1",
                control_points,
                ".UNSPECIFIED.",
                ".F.",
                ".F.",
                ".F.",
            )
        else:
            axis = _add_direction(builder, (0.0, 0.0, 1.0))
            reference = _add_direction(builder, (1.0, 0.0, 0.0))
            placement = builder.add(
                "AXIS2_PLACEMENT_3D",
                _q(""),
                _r(points[0][0]),
                _r(axis),
                _r(reference),
            )
            arguments = {
                "PLANE": (),
                "CYLINDRICAL_SURFACE": ("2.000000",),
                "CONICAL_SURFACE": ("2.000000", "0.500000"),
                "SPHERICAL_SURFACE": ("3.000000",),
                "TOROIDAL_SURFACE": ("4.000000", "1.000000"),
            }[surface_type]
            surface = builder.add(
                surface_type, _q(""), _r(placement), *arguments
            )
        faces.append(
            _add_face(
                builder,
                ((edges[0], True), (edges[1], True), (edges[2], False)),
                surface,
            )
        )
    builder.add("OPEN_SHELL", _q("surface_catalog"), _refs(faces))
    return builder.document("surface_catalog")


def _duplicate_first_data_entity(step_bytes: bytes) -> bytes:
    text = step_bytes.decode("utf-8")
    data_start = text.index("DATA;\n") + len("DATA;\n")
    first_end = text.index("\n", data_start) + 1
    first_entity = text[data_start:first_end]
    return (text[:first_end] + first_entity + text[first_end:]).encode("utf-8")


def _replace_first_oriented_edge_target(step_bytes: bytes) -> bytes:
    text = step_bytes.decode("utf-8")
    pattern = re.compile(
        r"(ORIENTED_EDGE\('[^']*',\*,\*,)#\d+(,(?:\.T\.|\.F\.)\);)"
    )
    replaced, count = pattern.subn(r"\g<1>#999999\g<2>", text, count=1)
    if count != 1:
        raise RuntimeError("synthetic fixture lacks an oriented edge target")
    return replaced.encode("utf-8")


__all__ = [
    "build_step_brep_fixtures",
    "DEFAULT_STEP_PARSE_LIMITS",
    "inspect_step_brep",
    "parse_step_part21",
    "STEPBRepFixture",
    "STEPDecision",
    "STEPDocument",
    "STEPEdgeObservation",
    "STEPEntity",
    "STEPFaceObservation",
    "STEPInspectionResult",
    "STEPParseLimits",
    "STEPReference",
    "STEPShellObservation",
    "STEPSolidObservation",
]
