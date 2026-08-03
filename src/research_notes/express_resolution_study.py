"""Synthetic fixtures and observations for EXPRESS semantic resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from research_notes.express_resolution import (
    DEFAULT_EXPRESS_RESOLUTION_LIMITS,
    ExpressResolutionLimitError,
    ExpressResolutionLimits,
    ExpressResolvedDocument,
    resolve_express_document,
)
from research_notes.express_schema import (
    DEFAULT_EXPRESS_PARSE_LIMITS,
    ExpressParseError,
    ExpressParseLimits,
    parse_express_document,
)


@dataclass(frozen=True)
class ExpressResolutionFixture:
    """One deterministic synthetic schema graph and expected decision."""

    fixture: str
    category: str
    condition: str
    file_name: str
    expected_decision: Literal["accept", "quarantine", "reject"]
    expected_reason_code: str
    source_bytes: bytes
    parse_limits: ExpressParseLimits = DEFAULT_EXPRESS_PARSE_LIMITS
    resolution_limits: ExpressResolutionLimits = DEFAULT_EXPRESS_RESOLUTION_LIMITS


@dataclass(frozen=True)
class ExpressResolutionObservation:
    """One staged syntax and semantic-resolution outcome."""

    decision: Literal["accept", "quarantine", "reject"]
    reason_code: str
    syntax_status: Literal["parsed", "rejected", "quarantined"]
    symbol_count: int
    reference_count: int
    resolved_reference_count: int
    unresolved_reference_count: int
    ambiguous_reference_count: int
    invalid_kind_reference_count: int
    type_count: int
    resolved_type_count: int
    cyclic_type_count: int
    entity_count: int
    resolved_inheritance_count: int
    cyclic_inheritance_count: int
    aggregate_bound_count: int
    resolved_bound_count: int
    deferred_bound_count: int
    diagnostic_count: int
    expression_validation: Literal["envelope_only"]
    rule_execution: Literal["not_attempted"]
    external_schema_loading: Literal["not_attempted"]


def inspect_express_resolution(
    source_bytes: bytes,
    *,
    parse_limits: ExpressParseLimits = DEFAULT_EXPRESS_PARSE_LIMITS,
    resolution_limits: ExpressResolutionLimits = DEFAULT_EXPRESS_RESOLUTION_LIMITS,
) -> tuple[ExpressResolutionObservation, ExpressResolvedDocument | None]:
    """Parse and resolve one controlled source without loading external schemas."""
    if not isinstance(source_bytes, bytes):
        raise TypeError("source_bytes must be bytes")
    if not isinstance(parse_limits, ExpressParseLimits):
        raise TypeError("parse_limits must be ExpressParseLimits")
    if not isinstance(resolution_limits, ExpressResolutionLimits):
        raise TypeError("resolution_limits must be ExpressResolutionLimits")
    try:
        document = parse_express_document(source_bytes, limits=parse_limits)
    except ExpressParseError as error:
        observation = _empty_observation(
            error.decision,
            error.reason_code,
            "quarantined" if error.decision == "quarantine" else "rejected",
        )
        return observation, None
    try:
        resolved = resolve_express_document(document, limits=resolution_limits)
    except ExpressResolutionLimitError as error:
        return _empty_observation("quarantine", error.reason_code, "parsed"), None
    statuses = [reference.status for reference in resolved.references]
    type_statuses = [item.status for item in resolved.types]
    inheritance_statuses = [item.status for item in resolved.inheritance]
    bound_statuses = [item.status for item in resolved.aggregate_bounds]
    observation = ExpressResolutionObservation(
        decision=resolved.decision,
        reason_code=resolved.reason_code,
        syntax_status="parsed",
        symbol_count=len(resolved.symbols),
        reference_count=len(resolved.references),
        resolved_reference_count=statuses.count("resolved"),
        unresolved_reference_count=statuses.count("unresolved"),
        ambiguous_reference_count=statuses.count("ambiguous"),
        invalid_kind_reference_count=statuses.count("invalid_kind"),
        type_count=len(resolved.types),
        resolved_type_count=type_statuses.count("resolved"),
        cyclic_type_count=type_statuses.count("cyclic"),
        entity_count=len(resolved.inheritance),
        resolved_inheritance_count=inheritance_statuses.count("resolved"),
        cyclic_inheritance_count=inheritance_statuses.count("cyclic"),
        aggregate_bound_count=len(resolved.aggregate_bounds),
        resolved_bound_count=bound_statuses.count("resolved"),
        deferred_bound_count=bound_statuses.count("deferred"),
        diagnostic_count=len(resolved.diagnostics),
        expression_validation=resolved.expression_validation,
        rule_execution=resolved.rule_execution,
        external_schema_loading=resolved.external_schema_loading,
    )
    return observation, resolved


def _empty_observation(
    decision: Literal["accept", "quarantine", "reject"],
    reason_code: str,
    syntax_status: Literal["parsed", "rejected", "quarantined"],
) -> ExpressResolutionObservation:
    return ExpressResolutionObservation(
        decision,
        reason_code,
        syntax_status,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        "envelope_only",
        "not_attempted",
        "not_attempted",
    )


def build_express_resolution_fixtures() -> tuple[ExpressResolutionFixture, ...]:
    """Return the complete deterministic v0.26 semantic fixture corpus."""
    fixtures = (
        _fixture("local_attribute_type", "local_scope", "local entity attribute type", "accept", "resolved", "SCHEMA demo; TYPE label = STRING; END_TYPE; ENTITY item; name : label; END_ENTITY; END_SCHEMA;"),
        _fixture("alias_chain", "types", "three-level type alias chain", "accept", "resolved", "SCHEMA demo; TYPE base = INTEGER; END_TYPE; TYPE middle = base; END_TYPE; TYPE top = middle; END_TYPE; END_SCHEMA;"),
        _fixture("case_insensitive_resolution", "local_scope", "case-insensitive symbol lookup", "accept", "resolved", "SCHEMA Demo; TYPE Label = STRING; END_TYPE; ENTITY Item; name : lAbEl; END_ENTITY; END_SCHEMA;"),
        _fixture("forward_type_reference", "local_scope", "forward named-type reference", "accept", "resolved", "SCHEMA demo; ENTITY item; code : label; END_ENTITY; TYPE label = STRING; END_TYPE; END_SCHEMA;"),
        _fixture("aggregate_entity_element", "types", "aggregate element entity", "accept", "resolved", "SCHEMA demo; ENTITY item; END_ENTITY; TYPE items = LIST [0:?] OF item; END_TYPE; END_SCHEMA;"),
        _fixture("select_members", "types", "defined-type and entity select members", "accept", "resolved", "SCHEMA demo; TYPE label = STRING; END_TYPE; ENTITY item; END_ENTITY; TYPE choice = SELECT (label, item); END_TYPE; END_SCHEMA;"),
        _fixture("literal_bounds", "bounds", "integer and unbounded aggregate bounds", "accept", "resolved", "SCHEMA demo; TYPE labels = LIST [1:?] OF STRING; END_TYPE; END_SCHEMA;"),
        _fixture("constant_bounds", "bounds", "local integer constant upper bound", "accept", "resolved", "SCHEMA demo; CONSTANT upper_limit : INTEGER := 8; END_CONSTANT; TYPE labels = LIST [1:upper_limit] OF STRING; END_TYPE; END_SCHEMA;"),
        _fixture("single_inheritance", "inheritance", "single entity inheritance", "accept", "resolved", "SCHEMA demo; ENTITY base; code : STRING; END_ENTITY; ENTITY child SUBTYPE OF (base); END_ENTITY; END_SCHEMA;"),
        _fixture("transitive_inheritance", "inheritance", "transitive entity inheritance", "accept", "resolved", "SCHEMA demo; ENTITY root; code : STRING; END_ENTITY; ENTITY middle SUBTYPE OF (root); END_ENTITY; ENTITY leaf SUBTYPE OF (middle); END_ENTITY; END_SCHEMA;"),
        _fixture("multiple_inheritance_distinct", "inheritance", "multiple inheritance with distinct attributes", "accept", "resolved", "SCHEMA demo; ENTITY left; left_code : STRING; END_ENTITY; ENTITY right; right_code : STRING; END_ENTITY; ENTITY child SUBTYPE OF (left, right); END_ENTITY; END_SCHEMA;"),
        _fixture("diamond_inheritance", "inheritance", "diamond inheritance with one shared origin", "accept", "resolved", "SCHEMA demo; ENTITY root; code : STRING; END_ENTITY; ENTITY left SUBTYPE OF (root); END_ENTITY; ENTITY right SUBTYPE OF (root); END_ENTITY; ENTITY leaf SUBTYPE OF (left, right); END_ENTITY; END_SCHEMA;"),
        _fixture("qualified_redeclaration", "inheritance", "qualified inherited attribute redeclaration", "accept", "resolved", "SCHEMA demo; ENTITY base; code : STRING; END_ENTITY; ENTITY child SUBTYPE OF (base); SELF\\base.code : STRING; END_ENTITY; END_SCHEMA;"),
        _fixture("use_explicit", "interfaces", "explicit USE import", "accept", "resolved", "SCHEMA base; ENTITY item; END_ENTITY; END_SCHEMA; SCHEMA app; USE FROM base (item); ENTITY holder; value : item; END_ENTITY; END_SCHEMA;"),
        _fixture("use_alias", "interfaces", "renamed USE import", "accept", "resolved", "SCHEMA base; TYPE identifier = STRING; END_TYPE; END_SCHEMA; SCHEMA app; USE FROM base (identifier AS local_id); ENTITY item; id : local_id; END_ENTITY; END_SCHEMA;"),
        _fixture("use_all", "interfaces", "whole-schema direct USE import", "accept", "resolved", "SCHEMA base; TYPE label = STRING; END_TYPE; ENTITY item; END_ENTITY; END_SCHEMA; SCHEMA app; USE FROM base; ENTITY holder; value : item; name : label; END_ENTITY; END_SCHEMA;"),
        _fixture("reference_constant", "interfaces", "REFERENCE import used as aggregate bound", "accept", "resolved", "SCHEMA base; CONSTANT upper_limit : INTEGER := 4; END_CONSTANT; END_SCHEMA; SCHEMA app; REFERENCE FROM base (upper_limit); TYPE labels = LIST [1:upper_limit] OF STRING; END_TYPE; END_SCHEMA;"),
        _fixture("reference_function", "interfaces", "REFERENCE import of a function symbol", "accept", "resolved", "SCHEMA base; FUNCTION identity(value : INTEGER) : INTEGER; RETURN(value); END_FUNCTION; END_SCHEMA; SCHEMA app; REFERENCE FROM base (identity); END_SCHEMA;"),
        _fixture("inverse_attribute", "inheritance", "inverse forward-attribute lookup", "accept", "resolved", "SCHEMA demo; ENTITY owner; items : SET [0:?] OF item; END_ENTITY; ENTITY item; owner_ref : owner; INVERSE owners : SET [0:?] OF owner FOR items; END_ENTITY; END_SCHEMA;"),
        _fixture("rule_target", "interfaces", "global rule entity target", "accept", "resolved", "SCHEMA demo; ENTITY item; END_ENTITY; RULE item_rule FOR (item); WHERE wr1: TRUE; END_RULE; END_SCHEMA;"),
        _fixture("missing_type", "references", "unresolved attribute type", "reject", "unresolved_reference", "SCHEMA demo; ENTITY item; value : missing_type; END_ENTITY; END_SCHEMA;"),
        _fixture("wrong_kind_type_alias", "types", "entity used as defined-type alias target", "reject", "invalid_kind_reference", "SCHEMA demo; ENTITY item; END_ENTITY; TYPE item_alias = item; END_TYPE; END_SCHEMA;"),
        _fixture("missing_select_member", "types", "unresolved select member", "reject", "unresolved_reference", "SCHEMA demo; TYPE choice = SELECT (missing_item); END_TYPE; END_SCHEMA;"),
        _fixture("missing_import_schema", "interfaces", "interface schema absent from document", "reject", "unresolved_interface_schema", "SCHEMA app; USE FROM absent (item); END_SCHEMA;"),
        _fixture("missing_import_item", "interfaces", "interface item absent from source schema", "reject", "unresolved_interface_item", "SCHEMA base; ENTITY item; END_ENTITY; END_SCHEMA; SCHEMA app; USE FROM base (missing_item); END_SCHEMA;"),
        _fixture("invalid_use_kind", "interfaces", "USE attempts to import a function", "reject", "invalid_use_item_kind", "SCHEMA base; FUNCTION identity(value : INTEGER) : INTEGER; RETURN(value); END_FUNCTION; END_SCHEMA; SCHEMA app; USE FROM base (identity); END_SCHEMA;"),
        _fixture("import_collision", "interfaces", "two imported declarations share one visible name", "reject", "ambiguous_visible_name", "SCHEMA left_schema; TYPE code = STRING; END_TYPE; END_SCHEMA; SCHEMA right_schema; TYPE code = INTEGER; END_TYPE; END_SCHEMA; SCHEMA app; USE FROM left_schema (code); USE FROM right_schema (code); ENTITY item; value : code; END_ENTITY; END_SCHEMA;"),
        _fixture("alias_cycle", "types", "two-node type alias cycle", "reject", "type_alias_cycle", "SCHEMA demo; TYPE first = second; END_TYPE; TYPE second = first; END_TYPE; END_SCHEMA;"),
        _fixture("missing_supertype", "inheritance", "unresolved entity supertype", "reject", "unresolved_reference", "SCHEMA demo; ENTITY child SUBTYPE OF (missing_base); END_ENTITY; END_SCHEMA;"),
        _fixture("wrong_supertype_kind", "inheritance", "defined type used as entity supertype", "reject", "invalid_kind_reference", "SCHEMA demo; TYPE base = STRING; END_TYPE; ENTITY child SUBTYPE OF (base); END_ENTITY; END_SCHEMA;"),
        _fixture("inheritance_cycle", "inheritance", "two-node entity inheritance cycle", "reject", "inheritance_cycle", "SCHEMA demo; ENTITY first SUBTYPE OF (second); END_ENTITY; ENTITY second SUBTYPE OF (first); END_ENTITY; END_SCHEMA;"),
        _fixture("unqualified_redeclaration", "inheritance", "inherited name hidden without SELF qualification", "reject", "unqualified_attribute_redeclaration", "SCHEMA demo; ENTITY base; code : STRING; END_ENTITY; ENTITY child SUBTYPE OF (base); code : STRING; END_ENTITY; END_SCHEMA;"),
        _fixture("inherited_collision", "inheritance", "multiple inherited attributes share a name", "reject", "inherited_attribute_ambiguity", "SCHEMA demo; ENTITY left; code : STRING; END_ENTITY; ENTITY right; code : STRING; END_ENTITY; ENTITY child SUBTYPE OF (left, right); END_ENTITY; END_SCHEMA;"),
        _fixture("invalid_qualified_redeclaration", "inheritance", "qualified redeclaration names missing ancestor attribute", "reject", "invalid_attribute_redeclaration", "SCHEMA demo; ENTITY base; code : STRING; END_ENTITY; ENTITY child SUBTYPE OF (base); SELF\\base.other : STRING; END_ENTITY; END_SCHEMA;"),
        _fixture("inverse_missing_forward", "inheritance", "inverse names absent forward attribute", "reject", "unresolved_inverse_attribute", "SCHEMA demo; ENTITY owner; END_ENTITY; ENTITY item; INVERSE owners : SET [0:?] OF owner FOR missing_items; END_ENTITY; END_SCHEMA;"),
        _fixture("invalid_bound_order", "bounds", "aggregate lower bound exceeds upper bound", "reject", "invalid_aggregate_bound_order", "SCHEMA demo; TYPE labels = LIST [5:2] OF STRING; END_TYPE; END_SCHEMA;"),
        _fixture("missing_bound_constant", "bounds", "aggregate bound constant is unresolved", "reject", "unresolved_reference", "SCHEMA demo; TYPE labels = LIST [1:missing_limit] OF STRING; END_TYPE; END_SCHEMA;"),
        _fixture("symbol_limit", "resources", "semantic symbol budget exceeded", "quarantine", "symbol_count_limit", "SCHEMA demo; TYPE label = STRING; END_TYPE; END_SCHEMA;", resolution_limits=ExpressResolutionLimits(max_symbols=1)),
    )
    return fixtures


def _fixture(
    fixture: str,
    category: str,
    condition: str,
    expected_decision: Literal["accept", "quarantine", "reject"],
    expected_reason_code: str,
    source: str,
    *,
    resolution_limits: ExpressResolutionLimits = DEFAULT_EXPRESS_RESOLUTION_LIMITS,
) -> ExpressResolutionFixture:
    return ExpressResolutionFixture(
        fixture,
        category,
        condition,
        f"{fixture}.exp",
        expected_decision,
        expected_reason_code,
        (source.strip() + "\n").encode("ascii"),
        resolution_limits=resolution_limits,
    )
