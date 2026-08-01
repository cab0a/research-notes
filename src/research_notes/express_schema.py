"""Source-preserving parsing and declaration modeling for controlled EXPRESS schemas."""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass
from typing import Literal


ExpressDecision = Literal["accept", "quarantine", "reject"]
ExpressAttributeKind = Literal["explicit", "derived", "inverse"]
ExpressAlgorithmKind = Literal["function", "procedure", "rule"]


@dataclass(frozen=True)
class ExpressParseLimits:
    """Explicit resource limits for one EXPRESS source."""

    max_file_bytes: int = 1_000_000
    max_tokens: int = 100_000
    max_declarations: int = 10_000
    max_nesting_depth: int = 32
    max_token_chars: int = 16_384

    def __post_init__(self) -> None:
        for field_name, value in vars(self).items():
            if value <= 0:
                raise ValueError(f"{field_name} must be positive")


DEFAULT_EXPRESS_PARSE_LIMITS = ExpressParseLimits()


@dataclass(frozen=True)
class ExpressSourceSpan:
    """Half-open character and byte coordinates in an ASCII EXPRESS source."""

    start_offset: int
    end_offset: int
    start_byte: int
    end_byte: int
    start_line: int
    start_column: int
    end_line: int
    end_column: int


@dataclass(frozen=True)
class ExpressToken:
    """One lexical token with exact spelling and normalized keyword value."""

    kind: str
    raw: str
    value: str
    span: ExpressSourceSpan

    @property
    def is_trivia(self) -> bool:
        """Return whether this token is whitespace or a comment."""
        return self.kind in {"WHITESPACE", "LINE_COMMENT", "BLOCK_COMMENT"}


@dataclass(frozen=True)
class ExpressTypeReference:
    """An unresolved EXPRESS type expression retained without symbol binding."""

    kind: Literal["simple", "named", "aggregate", "select", "enumeration"]
    name: str | None
    members: tuple[str, ...]
    aggregate_kind: str | None
    lower_bound: str | None
    upper_bound: str | None
    unique: bool
    optional: bool
    parameter: str | None
    fixed: bool
    element_type: ExpressTypeReference | None
    span: ExpressSourceSpan


@dataclass(frozen=True)
class ExpressRuleExpression:
    """A labelled constraint expression preserved as a bounded source envelope."""

    label: str
    expression: str
    span: ExpressSourceSpan


@dataclass(frozen=True)
class ExpressAttribute:
    """One explicit, derived, or inverse entity attribute."""

    name: str
    kind: ExpressAttributeKind
    type_ref: ExpressTypeReference
    optional: bool
    expression: str | None
    inverse_for: str | None
    span: ExpressSourceSpan


@dataclass(frozen=True)
class ExpressEntityDeclaration:
    """One entity declaration before inheritance or type resolution."""

    name: str
    abstract: bool
    supertypes: tuple[str, ...]
    supertype_expression: str | None
    attributes: tuple[ExpressAttribute, ...]
    unique_rules: tuple[ExpressRuleExpression, ...]
    where_rules: tuple[ExpressRuleExpression, ...]
    span: ExpressSourceSpan


@dataclass(frozen=True)
class ExpressTypeDeclaration:
    """One named type declaration and its unresolved underlying type."""

    name: str
    underlying_type: ExpressTypeReference
    where_rules: tuple[ExpressRuleExpression, ...]
    span: ExpressSourceSpan


@dataclass(frozen=True)
class ExpressInterfaceItem:
    """One imported name with an optional local alias."""

    name: str
    alias: str | None


@dataclass(frozen=True)
class ExpressInterfaceSpecification:
    """One USE FROM or REFERENCE FROM declaration."""

    kind: Literal["use", "reference"]
    schema_name: str
    items: tuple[ExpressInterfaceItem, ...]
    span: ExpressSourceSpan


@dataclass(frozen=True)
class ExpressParameter:
    """One flattened formal parameter."""

    name: str
    type_ref: ExpressTypeReference
    variable: bool


@dataclass(frozen=True)
class ExpressAlgorithmDeclaration:
    """A function, procedure, or rule with an opaque source-preserved body."""

    kind: ExpressAlgorithmKind
    name: str
    parameters: tuple[ExpressParameter, ...]
    return_type: ExpressTypeReference | None
    applies_to: tuple[str, ...]
    body: str
    span: ExpressSourceSpan


@dataclass(frozen=True)
class ExpressConstantDeclaration:
    """One schema constant with an unresolved type and expression envelope."""

    name: str
    type_ref: ExpressTypeReference
    expression: str
    span: ExpressSourceSpan


@dataclass(frozen=True)
class ExpressSchemaDeclaration:
    """One schema and its source-ordered declaration groups."""

    name: str
    interfaces: tuple[ExpressInterfaceSpecification, ...]
    types: tuple[ExpressTypeDeclaration, ...]
    entities: tuple[ExpressEntityDeclaration, ...]
    algorithms: tuple[ExpressAlgorithmDeclaration, ...]
    constants: tuple[ExpressConstantDeclaration, ...]
    span: ExpressSourceSpan

    @property
    def declaration_count(self) -> int:
        """Return the declarations owned by this schema."""
        return (
            len(self.interfaces)
            + len(self.types)
            + len(self.entities)
            + len(self.algorithms)
            + len(self.constants)
        )


@dataclass(frozen=True)
class ExpressDocument:
    """A source-preserving EXPRESS document with unresolved schema declarations."""

    source_text: str
    tokens: tuple[ExpressToken, ...]
    schemas: tuple[ExpressSchemaDeclaration, ...]
    span: ExpressSourceSpan

    @property
    def significant_tokens(self) -> tuple[ExpressToken, ...]:
        """Return all non-trivia tokens in source order."""
        return tuple(token for token in self.tokens if not token.is_trivia)

    def source_slice(self, span: ExpressSourceSpan) -> str:
        """Return the exact source spelling covered by a span."""
        return self.source_text[span.start_offset : span.end_offset]

    def reconstruct_source(self) -> str:
        """Reconstruct the complete decoded source from the token stream."""
        return "".join(token.raw for token in self.tokens)


class ExpressParseError(ValueError):
    """A stable parser decision with an optional source coordinate."""

    def __init__(
        self,
        decision: ExpressDecision,
        reason_code: str,
        message: str,
        span: ExpressSourceSpan | None = None,
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


_KEYWORDS = frozenset(
    {
        "ABS",
        "ABSTRACT",
        "AGGREGATE",
        "ALIAS",
        "AND",
        "ANDOR",
        "ARRAY",
        "AS",
        "BAG",
        "BEGIN",
        "BINARY",
        "BOOLEAN",
        "BY",
        "CASE",
        "CONSTANT",
        "DERIVE",
        "DIV",
        "ELSE",
        "END",
        "END_ALIAS",
        "END_CASE",
        "END_CONSTANT",
        "END_ENTITY",
        "END_FUNCTION",
        "END_IF",
        "END_LOCAL",
        "END_PROCEDURE",
        "END_REPEAT",
        "END_RULE",
        "END_SCHEMA",
        "END_TYPE",
        "ENTITY",
        "ENUMERATION",
        "ESCAPE",
        "FALSE",
        "FIXED",
        "FOR",
        "FROM",
        "FUNCTION",
        "GENERIC",
        "IF",
        "IN",
        "INTEGER",
        "INVERSE",
        "LIST",
        "LOCAL",
        "LOGICAL",
        "MOD",
        "NOT",
        "NUMBER",
        "OF",
        "ONEOF",
        "OPTIONAL",
        "OR",
        "OTHERWISE",
        "PROCEDURE",
        "QUERY",
        "REAL",
        "REFERENCE",
        "REPEAT",
        "RETURN",
        "RULE",
        "SCHEMA",
        "SELECT",
        "SELF",
        "SET",
        "SKIP",
        "STRING",
        "SUBTYPE",
        "SUPERTYPE",
        "THEN",
        "TO",
        "TRUE",
        "TYPE",
        "UNIQUE",
        "UNKNOWN",
        "UNTIL",
        "USE",
        "VAR",
        "WHERE",
        "WHILE",
        "XOR",
    }
)
_SIMPLE_TYPES = frozenset(
    {"BINARY", "BOOLEAN", "INTEGER", "LOGICAL", "NUMBER", "REAL", "STRING"}
)
_AGGREGATE_TYPES = frozenset({"AGGREGATE", "ARRAY", "BAG", "LIST", "SET"})
_IDENTIFIER_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]*")
_REAL_RE = re.compile(r"\d+\.\d*(?:[Ee][-+]?\d+)?")
_INTEGER_RE = re.compile(r"\d+")
_MULTI_SYMBOLS = (":<>:", ":=:", ":=", "||", "**", "<*", ">=", "<=", "<>")
_SINGLE_SYMBOLS = frozenset(":,.=|?[]{}()-+/;*\\<>")


def lex_express(
    source_bytes: bytes,
    *,
    limits: ExpressParseLimits = DEFAULT_EXPRESS_PARSE_LIMITS,
) -> tuple[str, tuple[ExpressToken, ...]]:
    """Decode ASCII EXPRESS source and preserve every token and comment."""
    _validate_input(source_bytes, limits)
    try:
        text = source_bytes.decode("ascii")
    except UnicodeDecodeError as error:
        raise ExpressParseError(
            "reject",
            "unsupported_source_character",
            "controlled EXPRESS source must be ASCII",
        ) from error

    coordinates = _SourceCoordinates(text)
    tokens: list[ExpressToken] = []
    index = 0
    while index < len(text):
        start = index
        character = text[index]
        if character.isspace():
            index += 1
            while index < len(text) and text[index].isspace():
                index += 1
            _append_token(tokens, "WHITESPACE", text[start:index], text[start:index], coordinates, start, index, limits)
            continue
        if text.startswith("--", index):
            newline = text.find("\n", index + 2)
            index = len(text) if newline < 0 else newline + 1
            _append_token(tokens, "LINE_COMMENT", text[start:index], text[start:index], coordinates, start, index, limits)
            continue
        if text.startswith("(*", index):
            index = _read_block_comment(text, index, coordinates, limits)
            _append_token(tokens, "BLOCK_COMMENT", text[start:index], text[start:index], coordinates, start, index, limits)
            continue
        if text.startswith("*)", index):
            raise ExpressParseError(
                "reject",
                "unmatched_comment_close",
                "block comment close has no matching open",
                coordinates.span(start, start + 2),
            )
        if character == "'":
            value, index = _read_string(text, start, "'", coordinates, limits)
            _append_token(tokens, "STRING", text[start:index], value, coordinates, start, index, limits)
            continue
        if character == '"':
            value, index = _read_string(text, start, '"', coordinates, limits)
            _append_token(tokens, "ENCODED_STRING", text[start:index], value, coordinates, start, index, limits)
            continue
        if character == "%":
            index += 1
            while index < len(text) and text[index] in "01":
                index += 1
            if index == start + 1:
                raise ExpressParseError(
                    "reject",
                    "invalid_binary_literal",
                    "binary literal requires at least one bit",
                    coordinates.span(start, index),
                )
            _append_token(tokens, "BINARY", text[start:index], text[start + 1 : index], coordinates, start, index, limits)
            continue
        identifier = _IDENTIFIER_RE.match(text, index)
        if identifier is not None:
            index = identifier.end()
            raw = text[start:index]
            normalized = raw.upper()
            kind = "KEYWORD" if normalized in _KEYWORDS else "IDENTIFIER"
            value = normalized if kind == "KEYWORD" else raw
            _append_token(tokens, kind, raw, value, coordinates, start, index, limits)
            continue
        if character == "_":
            end = index + 1
            while end < len(text) and (text[end].isalnum() or text[end] == "_"):
                end += 1
            raise ExpressParseError(
                "reject",
                "invalid_identifier",
                "identifier must begin with an ASCII letter",
                coordinates.span(start, end),
            )
        real = _REAL_RE.match(text, index)
        number = real if real is not None else _INTEGER_RE.match(text, index)
        if number is not None:
            index = number.end()
            if index < len(text) and text[index] in {"E", "e"}:
                raise ExpressParseError(
                    "reject",
                    "invalid_real_literal",
                    "real exponent requires a decimal point and exponent digits",
                    coordinates.span(start, min(index + 1, len(text))),
                )
            kind = "REAL" if real is not None else "INTEGER"
            _append_token(tokens, kind, text[start:index], text[start:index], coordinates, start, index, limits)
            continue
        symbol = next((item for item in _MULTI_SYMBOLS if text.startswith(item, index)), None)
        if symbol is not None:
            index += len(symbol)
            _append_token(tokens, "SYMBOL", symbol, symbol, coordinates, start, index, limits)
            continue
        if character in _SINGLE_SYMBOLS:
            index += 1
            _append_token(tokens, "SYMBOL", character, character, coordinates, start, index, limits)
            continue
        raise ExpressParseError(
            "reject",
            "unexpected_character",
            "character is outside the controlled EXPRESS lexical set",
            coordinates.span(start, start + 1),
        )
    return text, tuple(tokens)


def parse_express_document(
    source_bytes: bytes,
    *,
    limits: ExpressParseLimits = DEFAULT_EXPRESS_PARSE_LIMITS,
) -> ExpressDocument:
    """Parse controlled EXPRESS declarations into an unresolved schema model."""
    text, tokens = lex_express(source_bytes, limits=limits)
    stream = _TokenStream(text, tokens, limits)
    schemas: list[ExpressSchemaDeclaration] = []
    seen_schemas: set[str] = set()
    while not stream.at_end:
        schema = _parse_schema(stream)
        normalized = schema.name.casefold()
        if normalized in seen_schemas:
            raise ExpressParseError(
                "reject",
                "duplicate_schema",
                "schema name is repeated case-insensitively",
                schema.span,
            )
        seen_schemas.add(normalized)
        schemas.append(schema)
        declaration_count = sum(1 + item.declaration_count for item in schemas)
        if declaration_count > limits.max_declarations:
            raise ExpressParseError(
                "quarantine",
                "declaration_count_limit",
                "source has too many schema declarations",
                schema.span,
            )
    if not schemas:
        raise ExpressParseError(
            "reject", "missing_schema", "EXPRESS source contains no schema"
        )
    end_line, end_column = stream.coordinates.line_column(len(text))
    span = ExpressSourceSpan(
        0,
        len(text),
        0,
        len(source_bytes),
        1,
        1,
        end_line,
        end_column,
    )
    return ExpressDocument(text, tokens, tuple(schemas), span)


def _validate_input(source_bytes: bytes, limits: ExpressParseLimits) -> None:
    if not isinstance(source_bytes, bytes):
        raise TypeError("source_bytes must be bytes")
    if not isinstance(limits, ExpressParseLimits):
        raise TypeError("limits must be ExpressParseLimits")
    if len(source_bytes) > limits.max_file_bytes:
        raise ExpressParseError(
            "quarantine", "file_size_limit", "EXPRESS source exceeds the byte limit"
        )


def _append_token(
    tokens: list[ExpressToken],
    kind: str,
    raw: str,
    value: str,
    coordinates: _SourceCoordinates,
    start: int,
    end: int,
    limits: ExpressParseLimits,
) -> None:
    if len(raw) > limits.max_token_chars:
        raise ExpressParseError(
            "quarantine",
            "token_length_limit",
            "token exceeds the character limit",
            coordinates.span(start, end),
        )
    if len(tokens) >= limits.max_tokens:
        raise ExpressParseError(
            "quarantine", "token_count_limit", "source has too many tokens"
        )
    tokens.append(ExpressToken(kind, raw, value, coordinates.span(start, end)))


def _read_block_comment(
    text: str,
    start: int,
    coordinates: _SourceCoordinates,
    limits: ExpressParseLimits,
) -> int:
    index = start + 2
    depth = 1
    while index < len(text):
        if text.startswith("(*", index):
            depth += 1
            if depth > limits.max_nesting_depth:
                raise ExpressParseError(
                    "quarantine",
                    "comment_nesting_limit",
                    "block comments exceed the nesting limit",
                    coordinates.span(start, index + 2),
                )
            index += 2
        elif text.startswith("*)", index):
            depth -= 1
            index += 2
            if depth == 0:
                return index
        else:
            index += 1
    raise ExpressParseError(
        "reject",
        "unterminated_comment",
        "block comment is not terminated",
        coordinates.span(start, len(text)),
    )


def _read_string(
    text: str,
    start: int,
    quote: str,
    coordinates: _SourceCoordinates,
    limits: ExpressParseLimits,
) -> tuple[str, int]:
    index = start + 1
    output: list[str] = []
    while index < len(text):
        if text[index] in "\r\n":
            raise ExpressParseError(
                "reject",
                "unterminated_string",
                "string literal cannot cross a source line",
                coordinates.span(start, index),
            )
        if text[index] == quote:
            if quote == "'" and index + 1 < len(text) and text[index + 1] == quote:
                output.append(quote)
                index += 2
                continue
            end = index + 1
            if end - start > limits.max_token_chars:
                raise ExpressParseError(
                    "quarantine",
                    "token_length_limit",
                    "string token exceeds the character limit",
                    coordinates.span(start, end),
                )
            return "".join(output), end
        output.append(text[index])
        index += 1
    raise ExpressParseError(
        "reject",
        "unterminated_string",
        "string literal is not terminated",
        coordinates.span(start, len(text)),
    )


def _parse_schema(stream: _TokenStream) -> ExpressSchemaDeclaration:
    start = stream.expect_keyword("SCHEMA")
    name_token = stream.pop_identifier()
    stream.expect_symbol(";")
    interfaces: list[ExpressInterfaceSpecification] = []
    types: list[ExpressTypeDeclaration] = []
    entities: list[ExpressEntityDeclaration] = []
    algorithms: list[ExpressAlgorithmDeclaration] = []
    constants: list[ExpressConstantDeclaration] = []
    while not stream.matches_keyword("END_SCHEMA"):
        if stream.at_end:
            raise ExpressParseError(
                "reject", "missing_end_schema", "schema is not terminated", start.span
            )
        if stream.matches_keyword("USE") or stream.matches_keyword("REFERENCE"):
            interfaces.append(_parse_interface(stream))
        elif stream.matches_keyword("TYPE"):
            types.append(_parse_type_declaration(stream))
        elif stream.matches_keyword("ENTITY"):
            entities.append(_parse_entity(stream))
        elif stream.matches_keyword("CONSTANT"):
            constants.extend(_parse_constant_block(stream))
        elif stream.matches_keyword("FUNCTION"):
            algorithms.append(_parse_algorithm(stream, "function"))
        elif stream.matches_keyword("PROCEDURE"):
            algorithms.append(_parse_algorithm(stream, "procedure"))
        elif stream.matches_keyword("RULE"):
            algorithms.append(_parse_algorithm(stream, "rule"))
        else:
            token = stream.peek()
            raise ExpressParseError(
                "reject",
                "unsupported_declaration",
                "schema declaration is outside the controlled parser subset",
                token.span,
            )
        declaration_count = (
            1
            + len(interfaces)
            + len(types)
            + len(entities)
            + len(algorithms)
            + len(constants)
        )
        if declaration_count > stream.limits.max_declarations:
            raise ExpressParseError(
                "quarantine",
                "declaration_count_limit",
                "schema has too many declarations",
                start.span,
            )
    stream.expect_keyword("END_SCHEMA")
    semicolon = stream.expect_symbol(";")
    _reject_duplicate_declarations(types, entities, algorithms, constants)
    return ExpressSchemaDeclaration(
        name_token.value,
        tuple(interfaces),
        tuple(types),
        tuple(entities),
        tuple(algorithms),
        tuple(constants),
        _merge_span(start.span, semicolon.span),
    )


def _parse_interface(stream: _TokenStream) -> ExpressInterfaceSpecification:
    keyword = stream.pop()
    kind: Literal["use", "reference"] = (
        "use" if keyword.value == "USE" else "reference"
    )
    stream.expect_keyword("FROM")
    schema = stream.pop_identifier()
    items: list[ExpressInterfaceItem] = []
    if stream.matches_symbol("("):
        stream.expect_symbol("(")
        while not stream.matches_symbol(")"):
            name = stream.pop_identifier().value
            alias = None
            if stream.matches_keyword("AS"):
                stream.expect_keyword("AS")
                alias = stream.pop_identifier().value
            items.append(ExpressInterfaceItem(name, alias))
            if stream.matches_symbol(","):
                stream.expect_symbol(",")
            else:
                break
        if not items:
            raise ExpressParseError(
                "reject",
                "empty_import_list",
                "interface item list must not be empty",
                stream.peek().span,
            )
        stream.expect_symbol(")")
    semicolon = stream.expect_symbol(";")
    return ExpressInterfaceSpecification(
        kind, schema.value, tuple(items), _merge_span(keyword.span, semicolon.span)
    )


def _parse_type_declaration(stream: _TokenStream) -> ExpressTypeDeclaration:
    start = stream.expect_keyword("TYPE")
    name = stream.pop_identifier()
    stream.expect_symbol("=")
    underlying = _parse_type_reference(stream)
    stream.expect_symbol(";")
    where_rules: list[ExpressRuleExpression] = []
    if stream.matches_keyword("WHERE"):
        stream.expect_keyword("WHERE")
        where_rules = _parse_labelled_rules(stream, {"END_TYPE"})
    stream.expect_keyword("END_TYPE")
    end = stream.expect_symbol(";")
    return ExpressTypeDeclaration(
        name.value, underlying, tuple(where_rules), _merge_span(start.span, end.span)
    )


def _parse_entity(stream: _TokenStream) -> ExpressEntityDeclaration:
    start = stream.expect_keyword("ENTITY")
    name = stream.pop_identifier()
    abstract = False
    supertypes: list[str] = []
    supertype_expression: str | None = None
    while not stream.matches_symbol(";"):
        if stream.matches_keyword("ABSTRACT"):
            stream.expect_keyword("ABSTRACT")
            abstract = True
        elif stream.matches_keyword("SUPERTYPE"):
            stream.expect_keyword("SUPERTYPE")
            stream.expect_keyword("OF")
            supertype_expression = stream.collect_parenthesized_source()
        elif stream.matches_keyword("SUBTYPE"):
            stream.expect_keyword("SUBTYPE")
            stream.expect_keyword("OF")
            supertypes.extend(_parse_identifier_list(stream))
        else:
            token = stream.peek()
            raise ExpressParseError(
                "reject",
                "invalid_entity_header",
                "entity subtype or supertype declaration is malformed",
                token.span,
            )
    stream.expect_symbol(";")

    attributes: list[ExpressAttribute] = []
    unique_rules: list[ExpressRuleExpression] = []
    where_rules: list[ExpressRuleExpression] = []
    section: ExpressAttributeKind = "explicit"
    while not stream.matches_keyword("END_ENTITY"):
        if stream.at_end:
            raise ExpressParseError(
                "reject", "missing_end_entity", "entity is not terminated", start.span
            )
        if stream.matches_keyword("END_SCHEMA"):
            raise ExpressParseError(
                "reject", "missing_end_entity", "entity is not terminated", stream.peek().span
            )
        if stream.matches_keyword("DERIVE"):
            stream.expect_keyword("DERIVE")
            section = "derived"
            continue
        if stream.matches_keyword("INVERSE"):
            stream.expect_keyword("INVERSE")
            section = "inverse"
            continue
        if stream.matches_keyword("UNIQUE"):
            stream.expect_keyword("UNIQUE")
            unique_rules = _parse_labelled_rules(stream, {"WHERE", "END_ENTITY"})
            continue
        if stream.matches_keyword("WHERE"):
            stream.expect_keyword("WHERE")
            where_rules = _parse_labelled_rules(stream, {"END_ENTITY"})
            continue
        if unique_rules or where_rules:
            raise ExpressParseError(
                "reject",
                "invalid_entity_section_order",
                "attributes cannot follow UNIQUE or WHERE sections",
                stream.peek().span,
            )
        attributes.extend(_parse_attribute(stream, section))
    stream.expect_keyword("END_ENTITY")
    end = stream.expect_symbol(";")
    _reject_duplicate_attributes(attributes)
    return ExpressEntityDeclaration(
        name.value,
        abstract,
        tuple(supertypes),
        supertype_expression,
        tuple(attributes),
        tuple(unique_rules),
        tuple(where_rules),
        _merge_span(start.span, end.span),
    )


def _parse_attribute(
    stream: _TokenStream, kind: ExpressAttributeKind
) -> list[ExpressAttribute]:
    first = stream.peek()
    names = _parse_unparenthesized_identifier_list(stream)
    stream.expect_symbol(":")
    optional = False
    if kind == "explicit" and stream.matches_keyword("OPTIONAL"):
        stream.expect_keyword("OPTIONAL")
        optional = True
    type_ref = _parse_type_reference(stream)
    expression = None
    inverse_for = None
    if kind == "derived":
        if not stream.matches_symbol(":="):
            raise ExpressParseError(
                "reject",
                "missing_derived_assignment",
                "derived attribute requires an assignment expression",
                stream.peek().span,
            )
        stream.expect_symbol(":=")
        expression, expression_span = stream.collect_expression_until_semicolon()
        end_span = expression_span
    elif kind == "inverse":
        stream.expect_keyword("FOR")
        inverse_for = stream.pop_identifier().value
        end_span = stream.expect_symbol(";").span
    else:
        end_span = stream.expect_symbol(";").span
    span = _merge_span(first.span, end_span)
    return [
        ExpressAttribute(
            name,
            kind,
            type_ref,
            optional,
            expression,
            inverse_for,
            span,
        )
        for name in names
    ]


def _parse_constant_block(stream: _TokenStream) -> list[ExpressConstantDeclaration]:
    stream.expect_keyword("CONSTANT")
    constants: list[ExpressConstantDeclaration] = []
    while not stream.matches_keyword("END_CONSTANT"):
        start = stream.pop_identifier()
        stream.expect_symbol(":")
        type_ref = _parse_type_reference(stream)
        stream.expect_symbol(":=")
        expression, expression_span = stream.collect_expression_until_semicolon()
        constants.append(
            ExpressConstantDeclaration(
                start.value,
                type_ref,
                expression,
                _merge_span(start.span, expression_span),
            )
        )
    stream.expect_keyword("END_CONSTANT")
    stream.expect_symbol(";")
    return constants


def _parse_algorithm(
    stream: _TokenStream, kind: ExpressAlgorithmKind
) -> ExpressAlgorithmDeclaration:
    start_keyword = kind.upper()
    end_keyword = f"END_{start_keyword}"
    start = stream.expect_keyword(start_keyword)
    name = stream.pop_identifier()
    parameters: tuple[ExpressParameter, ...] = ()
    return_type: ExpressTypeReference | None = None
    applies_to: tuple[str, ...] = ()
    if kind == "rule":
        stream.expect_keyword("FOR")
        applies_to = tuple(_parse_identifier_list(stream))
    else:
        if stream.matches_symbol("("):
            parameters = tuple(_parse_parameters(stream))
        if kind == "function":
            stream.expect_symbol(":")
            return_type = _parse_type_reference(stream)
    stream.expect_symbol(";")
    body, _ = stream.collect_algorithm_body(start_keyword, end_keyword)
    stream.expect_keyword(end_keyword)
    end = stream.expect_symbol(";")
    return ExpressAlgorithmDeclaration(
        kind,
        name.value,
        parameters,
        return_type,
        applies_to,
        body,
        _merge_span(start.span, end.span),
    )


def _parse_parameters(stream: _TokenStream) -> list[ExpressParameter]:
    stream.expect_symbol("(")
    parameters: list[ExpressParameter] = []
    while not stream.matches_symbol(")"):
        variable = False
        if stream.matches_keyword("VAR"):
            stream.expect_keyword("VAR")
            variable = True
        names = _parse_unparenthesized_identifier_list(stream)
        stream.expect_symbol(":")
        type_ref = _parse_type_reference(stream)
        parameters.extend(
            ExpressParameter(name, type_ref, variable) for name in names
        )
        if stream.matches_symbol(";"):
            stream.expect_symbol(";")
        else:
            break
    stream.expect_symbol(")")
    return parameters


def _parse_type_reference(
    stream: _TokenStream, depth: int = 1
) -> ExpressTypeReference:
    if depth > stream.limits.max_nesting_depth:
        raise ExpressParseError(
            "quarantine",
            "nesting_limit",
            "type expression exceeds the nesting limit",
            stream.peek().span,
        )
    start = stream.peek()
    if start.kind == "KEYWORD" and start.value in _SIMPLE_TYPES:
        token = stream.pop()
        parameter = None
        fixed = False
        end_span = token.span
        if stream.matches_symbol("("):
            parameter = stream.collect_parenthesized_source()
            end_span = stream.previous.span
        if stream.matches_keyword("FIXED"):
            end_span = stream.expect_keyword("FIXED").span
            fixed = True
        return ExpressTypeReference(
            "simple", token.value, (), None, None, None, False, False,
            parameter, fixed, None, _merge_span(token.span, end_span)
        )
    if start.kind == "KEYWORD" and start.value in _AGGREGATE_TYPES:
        aggregate = stream.pop()
        lower = None
        upper = None
        if stream.matches_symbol("["):
            stream.expect_symbol("[")
            lower = stream.collect_source_until({":"})
            stream.expect_symbol(":")
            upper = stream.collect_source_until({"]"})
            stream.expect_symbol("]")
        stream.expect_keyword("OF")
        unique = False
        optional = False
        while stream.matches_keyword("UNIQUE") or stream.matches_keyword("OPTIONAL"):
            if stream.matches_keyword("UNIQUE"):
                stream.expect_keyword("UNIQUE")
                unique = True
            else:
                stream.expect_keyword("OPTIONAL")
                optional = True
        element = _parse_type_reference(stream, depth + 1)
        return ExpressTypeReference(
            "aggregate", None, (), aggregate.value, lower, upper, unique,
            optional, None, False, element, _merge_span(aggregate.span, element.span)
        )
    if stream.matches_keyword("SELECT") or stream.matches_keyword("ENUMERATION"):
        keyword = stream.pop()
        if keyword.value == "ENUMERATION":
            stream.expect_keyword("OF")
        members = _parse_identifier_list(stream)
        kind: Literal["select", "enumeration"] = (
            "select" if keyword.value == "SELECT" else "enumeration"
        )
        return ExpressTypeReference(
            kind, None, tuple(members), None, None, None, False, False,
            None, False, None, _merge_span(keyword.span, stream.previous.span)
        )
    if start.kind == "IDENTIFIER":
        token = stream.pop_identifier()
        return ExpressTypeReference(
            "named", token.value, (), None, None, None, False, False,
            None, False, None, token.span
        )
    raise ExpressParseError(
        "reject", "unsupported_type_expression", "type expression is unsupported", start.span
    )


def _parse_identifier_list(stream: _TokenStream) -> list[str]:
    stream.expect_symbol("(")
    if stream.matches_symbol(")"):
        raise ExpressParseError(
            "reject",
            "empty_identifier_list",
            "identifier list must not be empty",
            stream.peek().span,
        )
    names = _parse_unparenthesized_identifier_list(stream)
    stream.expect_symbol(")")
    return names


def _parse_unparenthesized_identifier_list(stream: _TokenStream) -> list[str]:
    names = [stream.pop_identifier().value]
    while stream.matches_symbol(","):
        stream.expect_symbol(",")
        names.append(stream.pop_identifier().value)
    return names


def _parse_labelled_rules(
    stream: _TokenStream, stop_keywords: set[str]
) -> list[ExpressRuleExpression]:
    rules: list[ExpressRuleExpression] = []
    while not stream.at_end and not any(
        stream.matches_keyword(keyword) for keyword in stop_keywords
    ):
        label = stream.pop_identifier()
        stream.expect_symbol(":")
        expression, expression_span = stream.collect_expression_until_semicolon()
        rules.append(
            ExpressRuleExpression(
                label.value,
                expression,
                _merge_span(label.span, expression_span),
            )
        )
    if not rules:
        raise ExpressParseError(
            "reject",
            "empty_rule_section",
            "constraint section must contain at least one labelled rule",
            stream.peek().span,
        )
    return rules


def _reject_duplicate_declarations(
    types: list[ExpressTypeDeclaration],
    entities: list[ExpressEntityDeclaration],
    algorithms: list[ExpressAlgorithmDeclaration],
    constants: list[ExpressConstantDeclaration],
) -> None:
    names = [item.name for item in (*types, *entities, *algorithms, *constants)]
    normalized = [name.casefold() for name in names]
    if len(normalized) != len(set(normalized)):
        raise ExpressParseError(
            "reject",
            "duplicate_declaration",
            "schema declaration name is repeated case-insensitively",
        )


def _reject_duplicate_attributes(attributes: list[ExpressAttribute]) -> None:
    normalized = [attribute.name.casefold() for attribute in attributes]
    if len(normalized) != len(set(normalized)):
        raise ExpressParseError(
            "reject",
            "duplicate_attribute",
            "entity attribute name is repeated case-insensitively",
        )


def _merge_span(start: ExpressSourceSpan, end: ExpressSourceSpan) -> ExpressSourceSpan:
    return ExpressSourceSpan(
        start.start_offset,
        end.end_offset,
        start.start_byte,
        end.end_byte,
        start.start_line,
        start.start_column,
        end.end_line,
        end.end_column,
    )


class _SourceCoordinates:
    def __init__(self, text: str) -> None:
        self.text = text
        self.line_starts = [0]
        for index, character in enumerate(text):
            if character == "\n":
                self.line_starts.append(index + 1)

    def line_column(self, offset: int) -> tuple[int, int]:
        line_index = bisect.bisect_right(self.line_starts, offset) - 1
        return line_index + 1, offset - self.line_starts[line_index] + 1

    def span(self, start: int, end: int) -> ExpressSourceSpan:
        start_line, start_column = self.line_column(start)
        end_line, end_column = self.line_column(end)
        return ExpressSourceSpan(
            start,
            end,
            start,
            end,
            start_line,
            start_column,
            end_line,
            end_column,
        )


class _TokenStream:
    def __init__(
        self,
        source_text: str,
        tokens: tuple[ExpressToken, ...],
        limits: ExpressParseLimits,
    ) -> None:
        self.source_text = source_text
        self.tokens = tuple(token for token in tokens if not token.is_trivia)
        self.index = 0
        self.limits = limits
        self.coordinates = _SourceCoordinates(source_text)
        self.previous = self.tokens[0] if self.tokens else ExpressToken(
            "EOF", "", "", self.coordinates.span(0, 0)
        )

    @property
    def at_end(self) -> bool:
        return self.index >= len(self.tokens)

    def peek(self) -> ExpressToken:
        if self.at_end:
            return ExpressToken(
                "EOF", "", "", self.coordinates.span(len(self.source_text), len(self.source_text))
            )
        return self.tokens[self.index]

    def pop(self) -> ExpressToken:
        token = self.peek()
        if token.kind == "EOF":
            raise ExpressParseError(
                "reject", "unexpected_end_of_file", "unexpected end of EXPRESS source", token.span
            )
        self.index += 1
        self.previous = token
        return token

    def matches_keyword(self, value: str) -> bool:
        token = self.peek()
        return token.kind == "KEYWORD" and token.value == value

    def matches_symbol(self, value: str) -> bool:
        token = self.peek()
        return token.kind == "SYMBOL" and token.value == value

    def expect_keyword(self, value: str) -> ExpressToken:
        token = self.peek()
        if not self.matches_keyword(value):
            raise ExpressParseError(
                "reject", "unexpected_token", f"expected keyword {value}", token.span
            )
        return self.pop()

    def expect_symbol(self, value: str) -> ExpressToken:
        token = self.peek()
        if not self.matches_symbol(value):
            reason = "missing_semicolon" if value == ";" else "unexpected_token"
            raise ExpressParseError(
                "reject", reason, f"expected symbol {value}", token.span
            )
        return self.pop()

    def pop_identifier(self) -> ExpressToken:
        token = self.peek()
        if token.kind != "IDENTIFIER":
            raise ExpressParseError(
                "reject", "expected_identifier", "expected EXPRESS identifier", token.span
            )
        return self.pop()

    def collect_parenthesized_source(self) -> str:
        self.expect_symbol("(")
        start_index = self.index
        depth = 1
        while not self.at_end:
            token = self.pop()
            if token.kind == "SYMBOL" and token.value == "(":
                depth += 1
                if depth > self.limits.max_nesting_depth:
                    raise ExpressParseError(
                        "quarantine", "nesting_limit", "parentheses exceed the nesting limit", token.span
                    )
            elif token.kind == "SYMBOL" and token.value == ")":
                depth -= 1
                if depth == 0:
                    content = self.tokens[start_index : self.index - 1]
                    if not content:
                        raise ExpressParseError(
                            "reject", "empty_parenthesized_value", "parenthesized value must not be empty", token.span
                        )
                    return self.source_text[
                        content[0].span.start_offset : content[-1].span.end_offset
                    ]
        raise ExpressParseError(
            "reject", "unbalanced_delimiter", "parenthesized value is not closed", self.previous.span
        )

    def collect_source_until(self, symbols: set[str]) -> str:
        start = self.peek()
        collected: list[ExpressToken] = []
        while not self.at_end and not (
            self.peek().kind == "SYMBOL" and self.peek().value in symbols
        ):
            collected.append(self.pop())
        if not collected:
            raise ExpressParseError(
                "reject", "empty_bound", "aggregate bound must not be empty", start.span
            )
        return self.source_text[
            collected[0].span.start_offset : collected[-1].span.end_offset
        ]

    def collect_expression_until_semicolon(self) -> tuple[str, ExpressSourceSpan]:
        start = self.peek()
        if self.matches_symbol(";"):
            raise ExpressParseError(
                "reject", "empty_expression", "expression must not be empty", start.span
            )
        stack: list[str] = []
        pairs = {")": "(", "]": "[", "}": "{"}
        tokens: list[ExpressToken] = []
        while not self.at_end:
            token = self.peek()
            if token.kind == "SYMBOL" and token.value == ";" and not stack:
                semicolon = self.pop()
                expression = self.source_text[
                    tokens[0].span.start_offset : tokens[-1].span.end_offset
                ]
                return expression, semicolon.span
            token = self.pop()
            if token.kind == "SYMBOL" and token.value in {"(", "[", "{"}:
                stack.append(token.value)
                if len(stack) > self.limits.max_nesting_depth:
                    raise ExpressParseError(
                        "quarantine", "nesting_limit", "expression exceeds the nesting limit", token.span
                    )
            elif token.kind == "SYMBOL" and token.value in pairs:
                if not stack or stack.pop() != pairs[token.value]:
                    raise ExpressParseError(
                        "reject", "unbalanced_delimiter", "expression delimiter is unbalanced", token.span
                    )
            tokens.append(token)
        raise ExpressParseError(
            "reject", "missing_semicolon", "expression is not terminated", start.span
        )

    def collect_algorithm_body(
        self, start_keyword: str, end_keyword: str
    ) -> tuple[str, ExpressSourceSpan]:
        start_offset = self.peek().span.start_offset if not self.at_end else self.previous.span.end_offset
        nested = 0
        stack: list[str] = []
        pairs = {")": "(", "]": "[", "}": "{"}
        last_span = self.previous.span
        while not self.at_end:
            token = self.peek()
            if token.kind == "KEYWORD" and token.value == end_keyword and nested == 0:
                body = self.source_text[start_offset : token.span.start_offset]
                return body, last_span
            token = self.pop()
            last_span = token.span
            if token.kind == "KEYWORD" and token.value == start_keyword:
                nested += 1
            elif token.kind == "KEYWORD" and token.value == end_keyword:
                nested -= 1
            elif token.kind == "SYMBOL" and token.value in {"(", "[", "{"}:
                stack.append(token.value)
            elif token.kind == "SYMBOL" and token.value in pairs:
                if not stack or stack.pop() != pairs[token.value]:
                    raise ExpressParseError(
                        "reject", "unbalanced_delimiter", "algorithm body delimiter is unbalanced", token.span
                    )
            if len(stack) > self.limits.max_nesting_depth:
                raise ExpressParseError(
                    "quarantine", "nesting_limit", "algorithm body exceeds the nesting limit", token.span
                )
        raise ExpressParseError(
            "reject", f"missing_{end_keyword.lower()}", f"{start_keyword} is not terminated", self.previous.span
        )
