"""Controlled EXPRESS grammar fixtures and declaration-model observations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from research_notes.express_schema import (
    DEFAULT_EXPRESS_PARSE_LIMITS,
    ExpressDocument,
    ExpressParseError,
    ExpressParseLimits,
    ExpressSchemaDeclaration,
    parse_express_document,
)


@dataclass(frozen=True)
class ExpressSchemaObservation:
    """A syntax decision separated from name resolution and rule execution."""

    decision: Literal["accept", "quarantine", "reject"]
    reason_code: str
    features: tuple[str, ...]
    schema_count: int
    interface_count: int
    type_count: int
    entity_count: int
    algorithm_count: int
    constant_count: int
    explicit_attribute_count: int
    derived_attribute_count: int
    inverse_attribute_count: int
    where_rule_count: int
    unique_rule_count: int
    token_count: int
    trivia_token_count: int
    source_bytes: int
    exact_reconstruction: bool
    diagnostic_line: int | None
    diagnostic_column: int | None
    symbol_resolution: Literal["not_attempted"] = "not_attempted"
    type_checking: Literal["not_attempted"] = "not_attempted"
    expression_validation: Literal["envelope_only"] = "envelope_only"
    rule_execution: Literal["not_attempted"] = "not_attempted"


@dataclass(frozen=True)
class ExpressSchemaFixture:
    """One deterministic synthetic EXPRESS source and expected decision."""

    fixture: str
    category: str
    condition: str
    file_name: str
    expected_decision: Literal["accept", "quarantine", "reject"]
    expected_reason_code: str
    source_bytes: bytes
    limits: ExpressParseLimits = DEFAULT_EXPRESS_PARSE_LIMITS


def inspect_express_schema(
    source_bytes: bytes,
    *,
    limits: ExpressParseLimits = DEFAULT_EXPRESS_PARSE_LIMITS,
) -> ExpressSchemaObservation:
    """Parse controlled EXPRESS syntax and summarize the unresolved model."""
    if not isinstance(source_bytes, bytes):
        raise TypeError("source_bytes must be bytes")
    if not isinstance(limits, ExpressParseLimits):
        raise TypeError("limits must be ExpressParseLimits")
    try:
        document = parse_express_document(source_bytes, limits=limits)
    except ExpressParseError as error:
        return ExpressSchemaObservation(
            decision=error.decision,
            reason_code=error.reason_code,
            features=(),
            schema_count=0,
            interface_count=0,
            type_count=0,
            entity_count=0,
            algorithm_count=0,
            constant_count=0,
            explicit_attribute_count=0,
            derived_attribute_count=0,
            inverse_attribute_count=0,
            where_rule_count=0,
            unique_rule_count=0,
            token_count=0,
            trivia_token_count=0,
            source_bytes=len(source_bytes),
            exact_reconstruction=False,
            diagnostic_line=error.span.start_line if error.span else None,
            diagnostic_column=error.span.start_column if error.span else None,
        )
    return _document_observation(document, source_bytes)


def build_express_schema_fixtures() -> tuple[ExpressSchemaFixture, ...]:
    """Build positive and negative EXPRESS grammar fixtures from source text."""
    accepted = (
        _fixture("minimal_schema", "schema", "empty_schema_envelope", "SCHEMA demo;\nEND_SCHEMA;\n"),
        _fixture("mixed_case", "lexical", "case_insensitive_keywords_and_names", "sChEmA Demo;\nTyPe Label = STRING; EnD_tYpE;\neNd_ScHeMa;\n"),
        _fixture("comments", "lexical", "tail_and_nested_block_comments", "-- leading tail remark\nSCHEMA comments;\n(* outer (* nested *) remark *)\nEND_SCHEMA;\n"),
        _fixture("type_alias_where", "type", "alias_with_width_fixed_and_where", "SCHEMA types;\nTYPE label = STRING(32) FIXED;\nWHERE\n  nonempty : SELF <> '';\nEND_TYPE;\nEND_SCHEMA;\n"),
        _fixture("enumeration_type", "type", "enumeration_members", "SCHEMA types;\nTYPE finish = ENUMERATION OF (rough, smooth, polished);\nEND_TYPE;\nEND_SCHEMA;\n"),
        _fixture("select_type", "type", "select_members", "SCHEMA types;\nTYPE geometry = SELECT (point, curve, surface);\nEND_TYPE;\nEND_SCHEMA;\n"),
        _fixture("aggregate_type", "type", "bounded_unique_list", "SCHEMA types;\nTYPE labels = LIST [1:?] OF UNIQUE STRING;\nEND_TYPE;\nEND_SCHEMA;\n"),
        _fixture("explicit_attributes", "entity", "required_and_optional_attributes", "SCHEMA entities;\nENTITY item;\n  identifier : STRING;\n  description : OPTIONAL STRING;\nEND_ENTITY;\nEND_SCHEMA;\n"),
        _fixture("entity_inheritance", "entity", "abstract_supertype_and_subtype", "SCHEMA entities;\nENTITY product ABSTRACT SUPERTYPE OF (ONEOF(part, assembly));\n  identifier : STRING;\nEND_ENTITY;\nENTITY part SUBTYPE OF (product);\nEND_ENTITY;\nENTITY assembly SUBTYPE OF (product);\nEND_ENTITY;\nEND_SCHEMA;\n"),
        _fixture("derived_attribute", "entity", "derived_expression_envelope", "SCHEMA entities;\nENTITY segment;\n  start_value, end_value : REAL;\nDERIVE\n  span : REAL := end_value - start_value;\nEND_ENTITY;\nEND_SCHEMA;\n"),
        _fixture("inverse_attribute", "entity", "inverse_set_and_for_attribute", "SCHEMA entities;\nENTITY parent;\nINVERSE\n  children : SET [0:?] OF child FOR owner;\nEND_ENTITY;\nENTITY child;\n  owner : parent;\nEND_ENTITY;\nEND_SCHEMA;\n"),
        _fixture("unique_where", "entity", "unique_and_where_constraints", "SCHEMA entities;\nENTITY item;\n  identifier : STRING;\nUNIQUE\n  ur1 : identifier;\nWHERE\n  wr1 : SIZEOF(identifier) > 0;\nEND_ENTITY;\nEND_SCHEMA;\n"),
        _fixture("use_import", "interface", "use_from_with_alias", "SCHEMA imports;\nUSE FROM base_schema (base_item AS local_item, label);\nEND_SCHEMA;\n"),
        _fixture("reference_import", "interface", "whole_schema_reference", "SCHEMA imports;\nREFERENCE FROM base_schema;\nEND_SCHEMA;\n"),
        _fixture("constant_block", "constant", "typed_schema_constants", "SCHEMA constants;\nCONSTANT\n  default_count : INTEGER := 4;\n  default_name : STRING := 'controlled';\nEND_CONSTANT;\nEND_SCHEMA;\n"),
        _fixture("function_envelope", "algorithm", "function_header_and_body", "SCHEMA algorithms;\nFUNCTION add_one(value : INTEGER) : INTEGER;\n  RETURN(value + 1);\nEND_FUNCTION;\nEND_SCHEMA;\n"),
        _fixture("procedure_envelope", "algorithm", "procedure_var_parameter_and_body", "SCHEMA algorithms;\nPROCEDURE initialize(VAR value : INTEGER);\n  value := 0;\nEND_PROCEDURE;\nEND_SCHEMA;\n"),
        _fixture("rule_envelope", "algorithm", "rule_targets_and_where_body", "SCHEMA algorithms;\nENTITY item;\n  identifier : STRING;\nEND_ENTITY;\nRULE item_rule FOR (item);\nWHERE\n  wr1 : SIZEOF(identifier) > 0;\nEND_RULE;\nEND_SCHEMA;\n"),
        _fixture("multiple_schemas", "schema", "two_schema_declarations", "SCHEMA first_schema;\nEND_SCHEMA;\nSCHEMA second_schema;\nEND_SCHEMA;\n"),
        _fixture("source_literals", "lexical", "string_binary_encoded_and_real_literals", "SCHEMA literals;\nCONSTANT\n  text_value : STRING := 'it''s controlled';\n  bits : BINARY := %1010;\n  encoded : STRING := \"00410042\";\n  ratio : REAL := 1.25E+2;\nEND_CONSTANT;\nEND_SCHEMA;\n"),
    )
    rejected = (
        _fixture("missing_schema", "schema", "source_has_no_schema", "", "reject", "missing_schema"),
        ExpressSchemaFixture("invalid_source_character", "lexical", "non_ascii_source_byte", "invalid_source_character.exp", "reject", "unsupported_source_character", "SCHEMA café; END_SCHEMA;".encode("utf-8")),
        _fixture("invalid_identifier", "lexical", "identifier_starts_with_underscore", "SCHEMA _demo; END_SCHEMA;", "reject", "invalid_identifier"),
        _fixture("unterminated_comment", "lexical", "block_comment_reaches_eof", "SCHEMA demo; (* never closed", "reject", "unterminated_comment"),
        _fixture("unmatched_comment_close", "lexical", "comment_close_without_open", "SCHEMA demo; *) END_SCHEMA;", "reject", "unmatched_comment_close"),
        _fixture("unterminated_string", "lexical", "string_crosses_line", "SCHEMA demo; CONSTANT value : STRING := 'open\nEND_CONSTANT; END_SCHEMA;", "reject", "unterminated_string"),
        _fixture("invalid_binary", "lexical", "binary_has_no_bits", "SCHEMA demo; CONSTANT bits : BINARY := %; END_CONSTANT; END_SCHEMA;", "reject", "invalid_binary_literal"),
        _fixture("invalid_real", "lexical", "exponent_without_decimal_point", "SCHEMA demo; CONSTANT value : REAL := 1E3; END_CONSTANT; END_SCHEMA;", "reject", "invalid_real_literal"),
        _fixture("missing_header_semicolon", "schema", "schema_header_has_no_semicolon", "SCHEMA demo\nEND_SCHEMA;", "reject", "missing_semicolon"),
        _fixture("missing_end_schema", "schema", "schema_reaches_eof", "SCHEMA demo;\n", "reject", "missing_end_schema"),
        _fixture("duplicate_schema", "schema", "case_insensitive_schema_collision", "SCHEMA demo; END_SCHEMA;\nSCHEMA DEMO; END_SCHEMA;", "reject", "duplicate_schema"),
        _fixture("duplicate_declaration", "model", "type_and_entity_name_collision", "SCHEMA demo;\nTYPE item = STRING; END_TYPE;\nENTITY ITEM; END_ENTITY;\nEND_SCHEMA;", "reject", "duplicate_declaration"),
        _fixture("empty_select", "type", "select_member_list_is_empty", "SCHEMA demo;\nTYPE choice = SELECT (); END_TYPE;\nEND_SCHEMA;", "reject", "empty_identifier_list"),
        _fixture("missing_end_entity", "entity", "entity_reaches_schema_end", "SCHEMA demo;\nENTITY item; identifier : STRING;\nEND_SCHEMA;", "reject", "missing_end_entity"),
        _fixture("duplicate_attribute", "entity", "case_insensitive_attribute_collision", "SCHEMA demo;\nENTITY item; label : STRING; LABEL : STRING; END_ENTITY;\nEND_SCHEMA;", "reject", "duplicate_attribute"),
        _fixture("derived_missing_assignment", "entity", "derived_attribute_lacks_assignment", "SCHEMA demo;\nENTITY item; value : REAL; DERIVE doubled : REAL value * 2; END_ENTITY;\nEND_SCHEMA;", "reject", "missing_derived_assignment"),
        _fixture("empty_where", "constraint", "where_section_has_no_rule", "SCHEMA demo;\nTYPE label = STRING; WHERE END_TYPE;\nEND_SCHEMA;", "reject", "empty_rule_section"),
        _fixture("unsupported_declaration", "boundary", "context_declaration_is_outside_subset", "SCHEMA demo;\nALIAS item FOR other; END_ALIAS;\nEND_SCHEMA;", "reject", "unsupported_declaration"),
        _fixture("missing_end_function", "algorithm", "function_reaches_schema_end", "SCHEMA demo;\nFUNCTION identity(value : INTEGER) : INTEGER; RETURN(value);\nEND_SCHEMA;", "reject", "missing_end_function"),
        ExpressSchemaFixture(
            "comment_nesting_limit",
            "resource_limit",
            "nested_comments_exceed_limit",
            "comment_nesting_limit.exp",
            "quarantine",
            "comment_nesting_limit",
            b"SCHEMA demo; (* one (* two (* three *) two *) one *) END_SCHEMA;",
            ExpressParseLimits(max_nesting_depth=2),
        ),
    )
    return accepted + rejected


def _fixture(
    fixture: str,
    category: str,
    condition: str,
    source: str,
    decision: Literal["accept", "quarantine", "reject"] = "accept",
    reason_code: str = "controlled_syntax_conforms",
) -> ExpressSchemaFixture:
    return ExpressSchemaFixture(
        fixture,
        category,
        condition,
        f"{fixture}.exp",
        decision,
        reason_code,
        source.encode("ascii"),
    )


def _document_observation(
    document: ExpressDocument, source_bytes: bytes
) -> ExpressSchemaObservation:
    schemas = document.schemas
    entities = tuple(entity for schema in schemas for entity in schema.entities)
    attributes = tuple(
        attribute for entity in entities for attribute in entity.attributes
    )
    features = _document_features(document, schemas)
    return ExpressSchemaObservation(
        decision="accept",
        reason_code="controlled_syntax_conforms",
        features=features,
        schema_count=len(schemas),
        interface_count=sum(len(schema.interfaces) for schema in schemas),
        type_count=sum(len(schema.types) for schema in schemas),
        entity_count=len(entities),
        algorithm_count=sum(len(schema.algorithms) for schema in schemas),
        constant_count=sum(len(schema.constants) for schema in schemas),
        explicit_attribute_count=sum(attribute.kind == "explicit" for attribute in attributes),
        derived_attribute_count=sum(attribute.kind == "derived" for attribute in attributes),
        inverse_attribute_count=sum(attribute.kind == "inverse" for attribute in attributes),
        where_rule_count=sum(
            len(schema_type.where_rules)
            for schema in schemas
            for schema_type in schema.types
        )
        + sum(len(entity.where_rules) for entity in entities),
        unique_rule_count=sum(len(entity.unique_rules) for entity in entities),
        token_count=len(document.significant_tokens),
        trivia_token_count=sum(token.is_trivia for token in document.tokens),
        source_bytes=len(source_bytes),
        exact_reconstruction=document.reconstruct_source().encode("ascii") == source_bytes,
        diagnostic_line=None,
        diagnostic_column=None,
    )


def _document_features(
    document: ExpressDocument,
    schemas: tuple[ExpressSchemaDeclaration, ...],
) -> tuple[str, ...]:
    features: set[str] = set()
    if any(token.kind == "LINE_COMMENT" for token in document.tokens):
        features.add("tail_comment")
    if any(token.kind == "BLOCK_COMMENT" for token in document.tokens):
        features.add("block_comment")
    if any(
        token.kind == "KEYWORD" and token.raw != token.raw.upper()
        for token in document.tokens
    ):
        features.add("case_insensitive_keyword")
    if len(schemas) > 1:
        features.add("multiple_schemas")
    for schema in schemas:
        features.update(f"interface_{item.kind}" for item in schema.interfaces)
        if schema.constants:
            features.add("constant")
        features.update(f"algorithm_{item.kind}" for item in schema.algorithms)
        for schema_type in schema.types:
            features.add(f"type_{schema_type.underlying_type.kind}")
            if schema_type.where_rules:
                features.add("where_rule")
        for entity in schema.entities:
            features.add("entity")
            if entity.abstract or entity.supertypes or entity.supertype_expression:
                features.add("inheritance_syntax")
            features.update(f"attribute_{item.kind}" for item in entity.attributes)
            if entity.where_rules:
                features.add("where_rule")
            if entity.unique_rules:
                features.add("unique_rule")
    return tuple(sorted(features))
