"""Source-preserving, resource-bounded parsing for ISO 10303-21 studies."""

from __future__ import annotations

import base64
import binascii
import math
import re
from dataclasses import dataclass
from typing import Literal


Part21Decision = Literal["accept", "quarantine", "reject"]
Part21ReferenceKind = Literal["entity", "value", "constant"]


@dataclass(frozen=True)
class STEPParseLimits:
    """Explicit resource limits for one Part 21 input."""

    max_file_bytes: int = 2_000_000
    max_tokens: int = 250_000
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
class Part21SourceSpan:
    """Half-open character and byte coordinates in a decoded source."""

    start_offset: int
    end_offset: int
    start_byte: int
    end_byte: int
    start_line: int
    start_column: int
    end_line: int
    end_column: int


@dataclass(frozen=True)
class Part21Token:
    """One lexical token with exact raw spelling and source coordinates."""

    kind: str
    raw: str
    value: str
    span: Part21SourceSpan

    @property
    def is_trivia(self) -> bool:
        """Return whether the token is whitespace or a comment."""
        return self.kind in {"WHITESPACE", "COMMENT"}


@dataclass(frozen=True)
class Part21Value:
    """One parsed parameter while retaining its exact source span."""

    kind: str
    value: str | int | float | None
    children: tuple[Part21Value, ...]
    span: Part21SourceSpan


@dataclass(frozen=True)
class Part21Record:
    """One simple record in a header or entity instance."""

    type_name: str
    arguments: tuple[Part21Value, ...]
    span: Part21SourceSpan


@dataclass(frozen=True)
class Part21Entity:
    """One simple or complex entity instance in a DATA section."""

    entity_id: int
    records: tuple[Part21Record, ...]
    uses_subsuper_record: bool
    span: Part21SourceSpan

    @property
    def is_complex(self) -> bool:
        """Return whether the entity uses an external-mapping subsuper record."""
        return self.uses_subsuper_record


@dataclass(frozen=True)
class Part21DataSection:
    """One DATA section and its optional name and schema declaration."""

    name: str | None
    schema_identifier: str | None
    entities: tuple[Part21Entity, ...]
    span: Part21SourceSpan


@dataclass(frozen=True)
class Part21Anchor:
    """One ANCHOR entry retained without application interpretation."""

    name: str
    item: Part21Value
    tag_count: int
    span: Part21SourceSpan


@dataclass(frozen=True)
class Part21ExternalReference:
    """One external occurrence mapping retained without retrieval."""

    kind: Part21ReferenceKind
    occurrence_name: str
    resource: str
    span: Part21SourceSpan


@dataclass(frozen=True)
class Part21Signature:
    """One Base64-decoded signature payload retained without CMS verification."""

    payload_bytes: int
    span: Part21SourceSpan


@dataclass(frozen=True)
class Part21Document:
    """A source-preserving concrete model of a bounded exchange structure."""

    source_text: str
    tokens: tuple[Part21Token, ...]
    header_records: tuple[Part21Record, ...]
    schema_identifiers: tuple[str, ...]
    data_sections: tuple[Part21DataSection, ...]
    anchors: tuple[Part21Anchor, ...]
    external_references: tuple[Part21ExternalReference, ...]
    signatures: tuple[Part21Signature, ...]
    reference_count: int
    span: Part21SourceSpan

    @property
    def significant_tokens(self) -> tuple[Part21Token, ...]:
        """Return tokens consumed by the grammar, excluding preserved trivia."""
        return tuple(token for token in self.tokens if not token.is_trivia)

    @property
    def entities(self) -> tuple[Part21Entity, ...]:
        """Return all entity instances in DATA-section order."""
        return tuple(
            entity
            for section in self.data_sections
            for entity in section.entities
        )

    def source_slice(self, span: Part21SourceSpan) -> str:
        """Return the exact source spelling covered by a span."""
        return self.source_text[span.start_offset : span.end_offset]

    def reconstruct_source(self) -> str:
        """Reconstruct the exact decoded source from the complete token stream."""
        return "".join(token.raw for token in self.tokens)


class Part21ParseError(ValueError):
    """A stable parser decision with optional source coordinates."""

    def __init__(
        self,
        decision: Part21Decision,
        reason_code: str,
        message: str,
        span: Part21SourceSpan | None = None,
    ) -> None:
        if span is not None:
            message = (
                f"{message} at line {span.start_line}, "
                f"column {span.start_column}"
            )
        super().__init__(message)
        self.decision = decision
        self.reason_code = reason_code
        self.span = span


_REAL_RE = re.compile(r"[-+]?\d+\.\d*(?:[Ee][-+]?\d+)?")
_INTEGER_RE = re.compile(r"[-+]?\d+")
_IDENTIFIER_RE = re.compile(r"!?[A-Za-z_][A-Za-z0-9_-]*")
_KEYWORD_RE = re.compile(r"!?[A-Z][A-Z0-9_]*")
_CONSTANT_RE = re.compile(r"[A-Z][A-Z0-9]*")
_ENUMERATION_RE = re.compile(r"[A-Z][A-Z0-9]*")
_TAG_NAME_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*")
_BINARY_RE = re.compile(r"[0-3][0-9A-F]*")


def lex_part21(
    source_bytes: bytes,
    *,
    limits: STEPParseLimits = DEFAULT_STEP_PARSE_LIMITS,
) -> tuple[str, tuple[Part21Token, ...]]:
    """Decode and tokenize Part 21 bytes while preserving trivia and spelling."""
    _validate_input(source_bytes, limits)
    try:
        text = source_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise Part21ParseError(
            "reject", "invalid_utf8", "exchange structure is not valid UTF-8"
        ) from error

    coordinates = _SourceCoordinates(text)
    tokens: list[Part21Token] = []
    index = 0
    while index < len(text):
        start = index
        character = text[index]
        if character.isspace():
            index += 1
            while index < len(text) and text[index].isspace():
                index += 1
            _append_token(
                tokens,
                "WHITESPACE",
                text[start:index],
                text[start:index],
                coordinates.span(start, index),
                limits,
            )
            continue
        if text.startswith("/*", index):
            end = text.find("*/", index + 2)
            if end < 0:
                raise Part21ParseError(
                    "reject",
                    "unterminated_comment",
                    "comment is not terminated",
                    coordinates.span(start, len(text)),
                )
            index = end + 2
            raw = text[start:index]
            _append_token(
                tokens,
                "COMMENT",
                raw,
                raw[2:-2],
                coordinates.span(start, index),
                limits,
            )
            continue
        if character == "'":
            value, index = _read_string(text, start, coordinates, limits)
            _append_token(
                tokens,
                "STRING",
                text[start:index],
                value,
                coordinates.span(start, index),
                limits,
            )
            continue
        if character == '"':
            value, index = _read_binary(text, start, coordinates, limits)
            _append_token(
                tokens,
                "BINARY",
                text[start:index],
                value,
                coordinates.span(start, index),
                limits,
            )
            continue
        if character == "<":
            end = text.find(">", index + 1)
            if end < 0:
                raise Part21ParseError(
                    "reject",
                    "unterminated_resource",
                    "resource token is not terminated",
                    coordinates.span(start, len(text)),
                )
            index = end + 1
            _append_token(
                tokens,
                "RESOURCE",
                text[start:index],
                text[start + 1 : end],
                coordinates.span(start, index),
                limits,
            )
            continue
        if character in {"#", "@"}:
            index += 1
            while index < len(text) and text[index].isdigit():
                index += 1
            if index > start + 1:
                if set(text[start + 1 : index]) == {"0"}:
                    raise Part21ParseError(
                        "reject",
                        "invalid_occurrence_name",
                        "occurrence name must contain a non-zero digit",
                        coordinates.span(start, index),
                    )
                kind = "ENTITY_REFERENCE" if character == "#" else "VALUE_REFERENCE"
                _append_token(
                    tokens,
                    kind,
                    text[start:index],
                    text[start:index],
                    coordinates.span(start, index),
                    limits,
                )
                continue
            identifier = _IDENTIFIER_RE.match(text, index)
            if identifier is not None:
                index = identifier.end()
                if not _CONSTANT_RE.fullmatch(text[start + 1 : index]):
                    raise Part21ParseError(
                        "reject",
                        "invalid_occurrence_name",
                        "constant occurrence name is not normalized",
                        coordinates.span(start, index),
                    )
                _append_token(
                    tokens,
                    "CONSTANT_REFERENCE",
                    text[start:index],
                    text[start:index],
                    coordinates.span(start, index),
                    limits,
                )
                continue
            raise Part21ParseError(
                "reject",
                "invalid_occurrence_name",
                "occurrence name is invalid",
                coordinates.span(start, min(start + 1, len(text))),
            )
        if character == ".":
            end = text.find(".", index + 1)
            if end > index + 1:
                value = text[index + 1 : end]
                if _ENUMERATION_RE.fullmatch(value):
                    index = end + 1
                    _append_token(
                        tokens,
                        "ENUMERATION",
                        text[start:index],
                        value,
                        coordinates.span(start, index),
                        limits,
                    )
                    continue
            if index + 1 < len(text) and text[index + 1].isdigit():
                raise Part21ParseError(
                    "reject",
                    "invalid_real",
                    "real requires a digit before the decimal point",
                    coordinates.span(start, min(start + 2, len(text))),
                )
        number = _REAL_RE.match(text, index)
        if number is None:
            number = _INTEGER_RE.match(text, index)
        if number is not None:
            index = number.end()
            if index < len(text) and text[index] in {"E", "e"}:
                raise Part21ParseError(
                    "reject",
                    "invalid_real",
                    "real with an exponent requires a decimal point",
                    coordinates.span(start, min(index + 1, len(text))),
                )
            _append_token(
                tokens,
                "NUMBER",
                text[start:index],
                text[start:index],
                coordinates.span(start, index),
                limits,
            )
            continue
        identifier = _IDENTIFIER_RE.match(text, index)
        if identifier is not None:
            index = identifier.end()
            _append_token(
                tokens,
                "IDENTIFIER",
                text[start:index],
                text[start:index],
                coordinates.span(start, index),
                limits,
            )
            continue
        if character == "\\":
            raise Part21ParseError(
                "quarantine",
                "control_directive_unsupported",
                "Part 21 control directives are outside this release",
                coordinates.span(start, start + 1),
            )
        if character in "(),;=$*{}:+/":
            index += 1
            _append_token(
                tokens,
                "SYMBOL",
                character,
                character,
                coordinates.span(start, index),
                limits,
            )
            continue
        raise Part21ParseError(
            "reject",
            "illegal_character",
            "illegal character",
            coordinates.span(start, start + 1),
        )
    return text, tuple(tokens)


def parse_part21_document(
    source_bytes: bytes,
    *,
    limits: STEPParseLimits = DEFAULT_STEP_PARSE_LIMITS,
) -> Part21Document:
    """Parse the bounded edition-3 subset into a source-preserving model."""
    text, tokens = lex_part21(source_bytes, limits=limits)
    stream = _TokenStream(tokens, limits)
    first = stream.expect_identifier("ISO-10303-21")
    stream.expect_symbol(";")
    stream.expect_identifier("HEADER")
    stream.expect_symbol(";")
    header_records = _parse_header(stream)
    schema_identifiers = _validate_header(header_records)

    anchors: tuple[Part21Anchor, ...] = ()
    if stream.matches_identifier("ANCHOR"):
        anchors = _parse_anchor_section(stream)

    external_references: tuple[Part21ExternalReference, ...] = ()
    if stream.matches_identifier("REFERENCE"):
        external_references = _parse_reference_section(stream)

    data_sections: list[Part21DataSection] = []
    entity_ids: set[int] = set()
    while stream.matches_identifier("DATA"):
        data_sections.append(_parse_data_section(stream, entity_ids, limits))

    stream.expect_identifier("END-ISO-10303-21")
    exchange_end = stream.expect_symbol(";")
    signatures: list[Part21Signature] = []
    while stream.matches_identifier("SIGNATURE"):
        signatures.append(_parse_signature_section(stream))
    if not stream.at_end:
        token = stream.peek()
        raise Part21ParseError(
            "reject", "trailing_tokens", "tokens follow the final section", token.span
        )

    _validate_data_sections(data_sections, schema_identifiers)
    external_ids = {
        int(reference.occurrence_name[1:])
        for reference in external_references
    }
    duplicates = sorted(external_ids.intersection(entity_ids))
    if duplicates:
        raise Part21ParseError(
            "reject",
            "duplicate_occurrence_name",
            "an occurrence name is defined in REFERENCE and DATA",
        )

    values: list[Part21Value] = []
    for record in header_records:
        values.extend(record.arguments)
    for section in data_sections:
        for entity in section.entities:
            for record in entity.records:
                values.extend(record.arguments)
    values.extend(anchor.item for anchor in anchors)
    reference_count = sum(_count_references(value) for value in values)
    if reference_count > limits.max_references:
        raise Part21ParseError(
            "quarantine",
            "reference_count_limit",
            "Part 21 occurrence reference count exceeds the configured limit",
        )

    final_span = signatures[-1].span if signatures else exchange_end.span
    return Part21Document(
        source_text=text,
        tokens=tokens,
        header_records=header_records,
        schema_identifiers=schema_identifiers,
        data_sections=tuple(data_sections),
        anchors=anchors,
        external_references=external_references,
        signatures=tuple(signatures),
        reference_count=reference_count,
        span=_merge_spans(first.span, final_span),
    )


class _SourceCoordinates:
    def __init__(self, text: str) -> None:
        self._text = text
        self._bytes = [0]
        self._lines = [1]
        self._columns = [1]
        line = 1
        column = 1
        byte_offset = 0
        for character in text:
            byte_offset += len(character.encode("utf-8"))
            if character == "\n":
                line += 1
                column = 1
            else:
                column += 1
            self._bytes.append(byte_offset)
            self._lines.append(line)
            self._columns.append(column)

    def span(self, start: int, end: int) -> Part21SourceSpan:
        return Part21SourceSpan(
            start_offset=start,
            end_offset=end,
            start_byte=self._bytes[start],
            end_byte=self._bytes[end],
            start_line=self._lines[start],
            start_column=self._columns[start],
            end_line=self._lines[end],
            end_column=self._columns[end],
        )


def _append_token(
    tokens: list[Part21Token],
    kind: str,
    raw: str,
    value: str,
    span: Part21SourceSpan,
    limits: STEPParseLimits,
) -> None:
    if len(raw) > limits.max_token_chars:
        raise Part21ParseError(
            "quarantine", "token_length_limit", "token exceeds the length limit", span
        )
    if len(tokens) >= limits.max_tokens:
        raise Part21ParseError(
            "quarantine",
            "token_count_limit",
            "token count exceeds the configured limit",
            span,
        )
    tokens.append(Part21Token(kind, raw, value, span))


def _read_string(
    text: str,
    start: int,
    coordinates: _SourceCoordinates,
    limits: STEPParseLimits,
) -> tuple[str, int]:
    """Read one string and normalize legacy character control directives."""
    index = start + 1
    output: list[str] = []
    iso_8859_page = 1
    while index < len(text):
        if text[index] == "'":
            if index + 1 < len(text) and text[index + 1] == "'":
                output.append("'")
                index += 2
                continue
            value = "".join(output)
            end = index + 1
            if len(text[start:end]) > limits.max_token_chars:
                raise Part21ParseError(
                    "quarantine",
                    "token_length_limit",
                    "token exceeds the length limit",
                    coordinates.span(start, end),
                )
            return value, end
        if text[index] != "\\":
            output.append(text[index])
            index += 1
            continue
        if text.startswith("\\\\", index):
            output.append("\\")
            index += 2
            continue
        if text.startswith(("\\N\\", "\\F\\"), index):
            index += 3
            continue
        page_match = re.match(r"\\P([A-I])\\", text[index:])
        if page_match is not None:
            iso_8859_page = ord(page_match.group(1)) - ord("A") + 1
            index += len(page_match.group(0))
            continue
        if text.startswith("\\S\\", index):
            value_index = index + 3
            if value_index >= len(text):
                raise Part21ParseError(
                    "reject",
                    "invalid_string_control_directive",
                    "page control directive is missing its character",
                    coordinates.span(index, len(text)),
                )
            code_value = ord(text[value_index]) + 128
            if code_value > 255:
                raise Part21ParseError(
                    "reject",
                    "invalid_string_control_directive",
                    "page control character is outside the basic alphabet",
                    coordinates.span(index, value_index + 1),
                )
            codec = f"iso8859_{iso_8859_page}"
            try:
                output.append(bytes((code_value,)).decode(codec))
            except (LookupError, UnicodeDecodeError) as error:
                raise Part21ParseError(
                    "reject",
                    "invalid_string_control_directive",
                    "page control directive cannot be decoded",
                    coordinates.span(index, value_index + 1),
                ) from error
            index = value_index + 1
            continue
        if text.startswith("\\X\\", index):
            end = index + 5
            digits = text[index + 3 : end]
            if len(digits) != 2 or not re.fullmatch(r"[0-9A-F]{2}", digits):
                raise Part21ParseError(
                    "reject",
                    "invalid_string_control_directive",
                    "arbitrary character directive requires two hexadecimal digits",
                    coordinates.span(index, min(end, len(text))),
                )
            output.append(chr(int(digits, 16)))
            index = end
            continue
        extended = _read_extended_string_directive(text, index, coordinates)
        if extended is not None:
            decoded, index = extended
            output.append(decoded)
            continue
        raise Part21ParseError(
            "reject",
            "invalid_string_control_directive",
            "string contains an unknown reverse-solidus directive",
            coordinates.span(index, min(index + 1, len(text))),
        )
    raise Part21ParseError(
        "reject",
        "unterminated_string",
        "string token is not terminated",
        coordinates.span(start, len(text)),
    )


def _read_extended_string_directive(
    text: str,
    start: int,
    coordinates: _SourceCoordinates,
) -> tuple[str, int] | None:
    width = 0
    prefix = ""
    if text.startswith("\\X2\\", start):
        width = 4
        prefix = "\\X2\\"
    elif text.startswith("\\X4\\", start):
        width = 8
        prefix = "\\X4\\"
    else:
        return None
    payload_start = start + len(prefix)
    payload_end = text.find("\\X0\\", payload_start)
    if payload_end < 0:
        raise Part21ParseError(
            "reject",
            "invalid_string_control_directive",
            "extended character directive is not terminated",
            coordinates.span(start, len(text)),
        )
    payload = text[payload_start:payload_end]
    if not payload or len(payload) % width or not re.fullmatch(r"[0-9A-F]+", payload):
        raise Part21ParseError(
            "reject",
            "invalid_string_control_directive",
            "extended character directive has invalid hexadecimal groups",
            coordinates.span(start, payload_end + 4),
        )
    characters: list[str] = []
    for offset in range(0, len(payload), width):
        codepoint = int(payload[offset : offset + width], 16)
        if codepoint > 0x10FFFF or 0xD800 <= codepoint <= 0xDFFF:
            raise Part21ParseError(
                "reject",
                "invalid_string_codepoint",
                "extended character directive contains an invalid Unicode code point",
                coordinates.span(start, payload_end + 4),
            )
        characters.append(chr(codepoint))
    return "".join(characters), payload_end + 4


def _read_binary(
    text: str,
    start: int,
    coordinates: _SourceCoordinates,
    limits: STEPParseLimits,
) -> tuple[str, int]:
    """Read a binary token while ignoring permitted print controls."""
    index = start + 1
    output: list[str] = []
    while index < len(text):
        if text[index] == '"':
            end = index + 1
            if len(text[start:end]) > limits.max_token_chars:
                raise Part21ParseError(
                    "quarantine",
                    "token_length_limit",
                    "token exceeds the length limit",
                    coordinates.span(start, end),
                )
            value = "".join(output)
            if not _BINARY_RE.fullmatch(value):
                raise Part21ParseError(
                    "reject",
                    "invalid_binary",
                    "binary token is not Part 21 hexadecimal",
                    coordinates.span(start, end),
                )
            return value, end
        if text.startswith(("\\N\\", "\\F\\"), index):
            index += 3
            continue
        output.append(text[index])
        index += 1
    raise Part21ParseError(
        "reject",
        "unterminated_binary",
        "binary token is not terminated",
        coordinates.span(start, len(text)),
    )


class _TokenStream:
    def __init__(
        self, tokens: tuple[Part21Token, ...], limits: STEPParseLimits
    ) -> None:
        self._tokens = tuple(token for token in tokens if not token.is_trivia)
        self._index = 0
        self._limits = limits

    @property
    def at_end(self) -> bool:
        return self._index == len(self._tokens)

    def peek(self) -> Part21Token:
        if self.at_end:
            raise Part21ParseError(
                "reject", "unexpected_end", "unexpected end of exchange structure"
            )
        return self._tokens[self._index]

    def pop(self) -> Part21Token:
        token = self.peek()
        self._index += 1
        return token

    def expect_kind(self, kind: str) -> Part21Token:
        token = self.pop()
        if token.kind != kind:
            raise Part21ParseError(
                "reject", "unexpected_token", f"expected {kind}", token.span
            )
        return token

    def expect_identifier(self, value: str) -> Part21Token:
        token = self.expect_kind("IDENTIFIER")
        if token.value != value:
            raise Part21ParseError(
                "reject", "unexpected_token", f"expected {value}", token.span
            )
        return token

    def pop_identifier(self) -> Part21Token:
        return self.expect_kind("IDENTIFIER")

    def matches_identifier(self, value: str) -> bool:
        return (
            not self.at_end
            and self.peek().kind == "IDENTIFIER"
            and self.peek().value.upper() == value.upper()
        )

    def expect_symbol(self, value: str) -> Part21Token:
        token = self.expect_kind("SYMBOL")
        if token.value != value:
            raise Part21ParseError(
                "reject", "unexpected_token", f"expected {value}", token.span
            )
        return token

    def matches_symbol(self, value: str) -> bool:
        return (
            not self.at_end
            and self.peek().kind == "SYMBOL"
            and self.peek().value == value
        )

    def parse_argument_list(self, depth: int) -> tuple[tuple[Part21Value, ...], Part21SourceSpan]:
        opening = self.expect_symbol("(")
        if self.matches_symbol(")"):
            closing = self.expect_symbol(")")
            return (), _merge_spans(opening.span, closing.span)
        values = [self.parse_value(depth + 1)]
        while self.matches_symbol(","):
            self.expect_symbol(",")
            values.append(self.parse_value(depth + 1))
        closing = self.expect_symbol(")")
        return tuple(values), _merge_spans(opening.span, closing.span)

    def parse_value(self, depth: int) -> Part21Value:
        if depth > self._limits.max_nesting_depth:
            token = self.peek()
            raise Part21ParseError(
                "quarantine",
                "nesting_depth_limit",
                "Part 21 aggregate nesting exceeds the configured limit",
                token.span,
            )
        token = self.peek()
        reference_kinds = {
            "ENTITY_REFERENCE": "entity_reference",
            "VALUE_REFERENCE": "value_reference",
            "CONSTANT_REFERENCE": "constant_reference",
        }
        if token.kind in reference_kinds:
            self.pop()
            return Part21Value(reference_kinds[token.kind], token.value, (), token.span)
        if token.kind == "STRING":
            self.pop()
            return Part21Value("string", token.value, (), token.span)
        if token.kind == "BINARY":
            self.pop()
            return Part21Value("binary", token.value, (), token.span)
        if token.kind == "RESOURCE":
            self.pop()
            return Part21Value("resource", token.value, (), token.span)
        if token.kind == "ENUMERATION":
            self.pop()
            return Part21Value("enumeration", token.value.upper(), (), token.span)
        if token.kind == "NUMBER":
            self.pop()
            number = _parse_number(token)
            kind = "real" if isinstance(number, float) else "integer"
            return Part21Value(kind, number, (), token.span)
        if token.kind == "SYMBOL" and token.value in {"$", "*"}:
            self.pop()
            kind = "omitted" if token.value == "$" else "derived"
            return Part21Value(kind, token.value, (), token.span)
        if token.kind == "SYMBOL" and token.value == "(":
            values, span = self.parse_argument_list(depth)
            return Part21Value("list", None, values, span)
        if token.kind == "IDENTIFIER":
            identifier = self.pop_identifier()
            if not _KEYWORD_RE.fullmatch(identifier.value):
                raise Part21ParseError(
                    "reject",
                    "invalid_keyword",
                    "keyword is not normalized uppercase Part 21 syntax",
                    identifier.span,
                )
            if not self.matches_symbol("("):
                return Part21Value(
                    "keyword", identifier.value.upper(), (), identifier.span
                )
            arguments, list_span = self.parse_argument_list(depth)
            return Part21Value(
                "typed",
                identifier.value.upper(),
                arguments,
                _merge_spans(identifier.span, list_span),
            )
        raise Part21ParseError(
            "reject", "unexpected_token", "unexpected parameter token", token.span
        )


def _parse_header(stream: _TokenStream) -> tuple[Part21Record, ...]:
    records: list[Part21Record] = []
    while not stream.matches_identifier("ENDSEC"):
        records.append(_parse_record(stream))
        stream.expect_symbol(";")
    stream.expect_identifier("ENDSEC")
    stream.expect_symbol(";")
    return tuple(records)


def _parse_record(stream: _TokenStream) -> Part21Record:
    identifier = stream.pop_identifier()
    if not _KEYWORD_RE.fullmatch(identifier.value):
        raise Part21ParseError(
            "reject",
            "invalid_keyword",
            "record keyword is not normalized uppercase Part 21 syntax",
            identifier.span,
        )
    arguments, argument_span = stream.parse_argument_list(0)
    return Part21Record(
        identifier.value.upper(),
        arguments,
        _merge_spans(identifier.span, argument_span),
    )


def _validate_header(records: tuple[Part21Record, ...]) -> tuple[str, ...]:
    required = ("FILE_DESCRIPTION", "FILE_NAME", "FILE_SCHEMA")
    if len(records) < 3 or tuple(record.type_name for record in records[:3]) != required:
        span = records[0].span if records else None
        raise Part21ParseError(
            "reject",
            "invalid_header_order",
            "HEADER must begin with FILE_DESCRIPTION, FILE_NAME, FILE_SCHEMA",
            span,
        )
    schema_arguments = records[2].arguments
    if (
        len(schema_arguments) != 1
        or schema_arguments[0].kind != "list"
        or not schema_arguments[0].children
        or not all(item.kind == "string" for item in schema_arguments[0].children)
    ):
        raise Part21ParseError(
            "reject",
            "invalid_file_schema",
            "FILE_SCHEMA has an invalid parameter shape",
            records[2].span,
        )
    schemas = tuple(str(item.value).upper() for item in schema_arguments[0].children)
    if len(set(schemas)) != len(schemas):
        raise Part21ParseError(
            "reject",
            "duplicate_file_schema",
            "FILE_SCHEMA repeats an identifier",
            records[2].span,
        )
    return schemas


def _parse_anchor_section(stream: _TokenStream) -> tuple[Part21Anchor, ...]:
    stream.expect_identifier("ANCHOR")
    stream.expect_symbol(";")
    anchors: list[Part21Anchor] = []
    seen: set[str] = set()
    while not stream.matches_identifier("ENDSEC"):
        name = stream.expect_kind("RESOURCE")
        if name.value in seen:
            raise Part21ParseError(
                "reject", "duplicate_anchor_name", "ANCHOR name is repeated", name.span
            )
        seen.add(name.value)
        stream.expect_symbol("=")
        item = stream.parse_value(0)
        tag_count = 0
        while stream.matches_symbol("{"):
            stream.expect_symbol("{")
            tag_name = stream.pop_identifier()
            if not _TAG_NAME_RE.fullmatch(tag_name.value):
                raise Part21ParseError(
                    "reject",
                    "invalid_tag_name",
                    "anchor tag name is invalid",
                    tag_name.span,
                )
            stream.expect_symbol(":")
            stream.parse_value(0)
            stream.expect_symbol("}")
            tag_count += 1
        semicolon = stream.expect_symbol(";")
        anchors.append(
            Part21Anchor(
                name.value,
                item,
                tag_count,
                _merge_spans(name.span, semicolon.span),
            )
        )
    stream.expect_identifier("ENDSEC")
    stream.expect_symbol(";")
    return tuple(anchors)


def _parse_reference_section(
    stream: _TokenStream,
) -> tuple[Part21ExternalReference, ...]:
    stream.expect_identifier("REFERENCE")
    stream.expect_symbol(";")
    references: list[Part21ExternalReference] = []
    seen: set[int] = set()
    while not stream.matches_identifier("ENDSEC"):
        occurrence = stream.pop()
        kind_by_token: dict[str, Part21ReferenceKind] = {
            "ENTITY_REFERENCE": "entity",
            "VALUE_REFERENCE": "value",
        }
        if occurrence.kind not in kind_by_token:
            raise Part21ParseError(
                "reject", "unexpected_token", "expected occurrence name", occurrence.span
            )
        occurrence_id = int(occurrence.value[1:])
        if occurrence_id in seen:
            raise Part21ParseError(
                "reject",
                "duplicate_reference_name",
                "REFERENCE occurrence name is repeated",
                occurrence.span,
            )
        seen.add(occurrence_id)
        stream.expect_symbol("=")
        resource = stream.expect_kind("RESOURCE")
        semicolon = stream.expect_symbol(";")
        references.append(
            Part21ExternalReference(
                kind_by_token[occurrence.kind],
                occurrence.value,
                resource.value,
                _merge_spans(occurrence.span, semicolon.span),
            )
        )
    stream.expect_identifier("ENDSEC")
    stream.expect_symbol(";")
    return tuple(references)


def _parse_data_section(
    stream: _TokenStream,
    seen_entity_ids: set[int],
    limits: STEPParseLimits,
) -> Part21DataSection:
    start = stream.expect_identifier("DATA")
    name: str | None = None
    schema: str | None = None
    if stream.matches_symbol("("):
        parameters, _ = stream.parse_argument_list(0)
        if (
            len(parameters) != 2
            or parameters[0].kind != "string"
            or parameters[1].kind != "list"
            or len(parameters[1].children) != 1
            or parameters[1].children[0].kind != "string"
        ):
            raise Part21ParseError(
                "reject",
                "invalid_data_section_parameters",
                "parameterized DATA requires a name and one schema identifier",
                start.span,
            )
        name = str(parameters[0].value)
        schema = str(parameters[1].children[0].value).upper()
    stream.expect_symbol(";")

    entities: list[Part21Entity] = []
    while not stream.matches_identifier("ENDSEC"):
        occurrence = stream.expect_kind("ENTITY_REFERENCE")
        entity_id = _parse_entity_id(occurrence)
        if entity_id in seen_entity_ids:
            raise Part21ParseError(
                "reject",
                "duplicate_entity_id",
                "entity identifier is repeated",
                occurrence.span,
            )
        if len(seen_entity_ids) >= limits.max_entities:
            raise Part21ParseError(
                "quarantine",
                "entity_count_limit",
                "Part 21 entity count exceeds the configured limit",
                occurrence.span,
            )
        seen_entity_ids.add(entity_id)
        stream.expect_symbol("=")
        uses_subsuper_record = stream.matches_symbol("(")
        if uses_subsuper_record:
            stream.expect_symbol("(")
            records: list[Part21Record] = []
            while not stream.matches_symbol(")"):
                records.append(_parse_record(stream))
            stream.expect_symbol(")")
            if not records:
                raise Part21ParseError(
                    "reject",
                    "invalid_complex_entity",
                    "complex entity requires at least one component record",
                    occurrence.span,
                )
        else:
            records = [_parse_record(stream)]
        semicolon = stream.expect_symbol(";")
        entities.append(
            Part21Entity(
                entity_id,
                tuple(records),
                uses_subsuper_record,
                _merge_spans(occurrence.span, semicolon.span),
            )
        )
    stream.expect_identifier("ENDSEC")
    section_end = stream.expect_symbol(";")
    return Part21DataSection(
        name,
        schema,
        tuple(entities),
        _merge_spans(start.span, section_end.span),
    )


def _parse_signature_section(stream: _TokenStream) -> Part21Signature:
    start = stream.expect_identifier("SIGNATURE")
    stream.expect_symbol(";")
    parts: list[str] = []
    while not stream.matches_identifier("ENDSEC"):
        token = stream.pop()
        if token.kind not in {"IDENTIFIER", "NUMBER", "SYMBOL"} or (
            token.kind == "SYMBOL" and token.value not in {"+", "/", "="}
        ):
            raise Part21ParseError(
                "reject",
                "invalid_signature_base64",
                "signature is not Base64",
                token.span,
            )
        parts.append(token.value)
    stream.expect_identifier("ENDSEC")
    section_end = stream.expect_symbol(";")
    encoded = "".join(parts)
    try:
        payload = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as error:
        raise Part21ParseError(
            "reject",
            "invalid_signature_base64",
            "signature is not valid Base64",
            _merge_spans(start.span, section_end.span),
        ) from error
    return Part21Signature(
        len(payload), _merge_spans(start.span, section_end.span)
    )


def _validate_data_sections(
    sections: list[Part21DataSection], schema_identifiers: tuple[str, ...]
) -> None:
    if len(sections) > 1 and any(section.name is None for section in sections):
        raise Part21ParseError(
            "reject",
            "multiple_data_sections_require_names",
            "each of multiple DATA sections must be parameterized",
        )
    names = [section.name for section in sections if section.name is not None]
    if len(set(names)) != len(names):
        raise Part21ParseError(
            "reject", "duplicate_data_section_name", "DATA section name is repeated"
        )
    for section in sections:
        if section.schema_identifier is not None:
            if section.schema_identifier not in schema_identifiers:
                raise Part21ParseError(
                    "reject",
                    "data_schema_not_declared",
                    "DATA schema is absent from FILE_SCHEMA",
                    section.span,
                )
        elif len(schema_identifiers) != 1:
            raise Part21ParseError(
                "reject",
                "ambiguous_unnamed_data_schema",
                "unnamed DATA requires exactly one FILE_SCHEMA identifier",
                section.span,
            )


def _validate_input(source_bytes: bytes, limits: STEPParseLimits) -> None:
    if not isinstance(source_bytes, bytes):
        raise TypeError("source_bytes must be bytes")
    if not isinstance(limits, STEPParseLimits):
        raise TypeError("limits must be STEPParseLimits")
    if len(source_bytes) > limits.max_file_bytes:
        raise Part21ParseError(
            "quarantine", "file_size_limit", "input exceeds the byte limit"
        )
    if source_bytes.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        raise Part21ParseError(
            "quarantine",
            "archive_container_unsupported",
            "ZIP exchange containers are recognized but not opened",
        )


def _parse_entity_id(token: Part21Token) -> int:
    try:
        return int(token.value[1:])
    except ValueError as error:
        raise Part21ParseError(
            "quarantine",
            "reference_conversion_limit",
            "entity identifier cannot be represented",
            token.span,
        ) from error


def _parse_number(token: Part21Token) -> int | float:
    try:
        if any(character in token.value.upper() for character in ".E"):
            value: int | float = float(token.value)
        else:
            value = int(token.value)
    except ValueError as error:
        raise Part21ParseError(
            "quarantine",
            "number_conversion_limit",
            "number cannot be represented",
            token.span,
        ) from error
    if isinstance(value, float) and not math.isfinite(value):
        raise Part21ParseError(
            "reject", "nonfinite_number", "number is not finite", token.span
        )
    return value


def _count_references(value: Part21Value) -> int:
    own = int(
        value.kind
        in {"entity_reference", "value_reference", "constant_reference"}
    )
    return own + sum(_count_references(child) for child in value.children)


def _merge_spans(
    start: Part21SourceSpan, end: Part21SourceSpan
) -> Part21SourceSpan:
    return Part21SourceSpan(
        start_offset=start.start_offset,
        end_offset=end.end_offset,
        start_byte=start.start_byte,
        end_byte=end.end_byte,
        start_line=start.start_line,
        start_column=start.start_column,
        end_line=end.end_line,
        end_column=end.end_column,
    )
