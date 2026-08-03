"""Tests for controlled EXPRESS symbols, types, and inheritance."""

from __future__ import annotations

import hashlib

import pytest

from research_notes.express_resolution import (
    ExpressResolutionLimits,
    resolve_express_document,
)
from research_notes.express_resolution_study import (
    build_express_resolution_fixtures,
    inspect_express_resolution,
)
from research_notes.express_schema import parse_express_document


def fixture_map() -> dict[str, object]:
    """Return v0.26 fixtures keyed by stable names."""
    return {
        fixture.fixture: fixture for fixture in build_express_resolution_fixtures()
    }


def resolved_fixture(name: str):
    """Parse and resolve one fixture expected to reach the semantic stage."""
    fixture = fixture_map()[name]
    document = parse_express_document(fixture.source_bytes)
    return resolve_express_document(document, limits=fixture.resolution_limits)


def test_all_resolution_fixture_expectations_are_met() -> None:
    """Every controlled symbol and graph outcome should match its declaration."""
    fixtures = build_express_resolution_fixtures()

    assert len(fixtures) == 38
    assert sum(item.expected_decision == "accept" for item in fixtures) == 20
    assert sum(item.expected_decision == "reject" for item in fixtures) == 17
    assert sum(item.expected_decision == "quarantine" for item in fixtures) == 1
    for fixture in fixtures:
        observation, _ = inspect_express_resolution(
            fixture.source_bytes,
            parse_limits=fixture.parse_limits,
            resolution_limits=fixture.resolution_limits,
        )
        assert observation.decision == fixture.expected_decision, fixture.fixture
        assert observation.reason_code == fixture.expected_reason_code, fixture.fixture
        assert observation.expression_validation == "envelope_only"
        assert observation.rule_execution == "not_attempted"


def test_aliases_and_select_members_resolve_case_insensitively() -> None:
    """Alias chains and SELECT members should bind to stable symbol identities."""
    aliases = resolved_fixture("alias_chain")
    mixed_case = resolved_fixture("case_insensitive_resolution")
    select = resolved_fixture("select_members")

    top = next(item for item in aliases.types if item.type_name == "top")
    assert top.status == "resolved"
    assert top.terminal_domain == "simple:INTEGER"
    assert top.alias_chain == (
        "demo::top",
        "demo::middle",
        "demo::base",
    )
    name_ref = next(
        item
        for item in mixed_case.references
        if item.role == "attribute_explicit:name"
    )
    assert name_ref.resolved_symbol_id == "demo::label"
    assert {
        item.resolved_symbol_id
        for item in select.references
        if item.role == "select_member"
    } == {"demo::label", "demo::item"}
    same_name = resolve_express_document(
        parse_express_document(
            b"SCHEMA demo; TYPE demo = STRING; END_TYPE; END_SCHEMA;"
        )
    )
    assert [item.symbol_id for item in same_name.symbols] == (
        ["schema::demo", "demo::demo"]
    )


def test_imports_preserve_kind_alias_and_ambiguity() -> None:
    """Direct USE and REFERENCE imports should remain distinct and auditable."""
    use_alias = resolved_fixture("use_alias")
    reference = resolved_fixture("reference_constant")
    collision = resolved_fixture("import_collision")

    alias_ref = next(
        item
        for item in use_alias.references
        if item.role == "attribute_explicit:id"
    )
    assert alias_ref.resolved_symbol_id == "base::identifier"
    bound_ref = next(
        item for item in reference.references if item.role.endswith(".upper")
    )
    assert bound_ref.expected_kinds == ("constant",)
    assert bound_ref.resolved_symbol_id == "base::upper_limit"
    assert collision.decision == "reject"
    assert any(
        item.reason_code == "ambiguous_visible_name"
        for item in collision.diagnostics
    )
    ambiguous = next(
        item
        for item in collision.references
        if item.role == "attribute_explicit:value"
    )
    assert ambiguous.status == "ambiguous"
    assert len(ambiguous.candidate_symbol_ids) == 2


def test_inheritance_deduplicates_diamonds_and_validates_redeclarations() -> None:
    """Shared origins and qualified redeclarations should remain distinguishable."""
    diamond = resolved_fixture("diamond_inheritance")
    redeclaration = resolved_fixture("qualified_redeclaration")
    collision = resolved_fixture("inherited_collision")

    leaf = next(item for item in diamond.inheritance if item.entity_name == "leaf")
    assert leaf.status == "resolved"
    assert leaf.transitive_supertype_ids == (
        "demo::root",
        "demo::left",
        "demo::right",
    )
    assert leaf.inherited_attribute_count == 1
    child = next(
        item for item in redeclaration.inheritance if item.entity_name == "child"
    )
    assert child.status == "resolved"
    assert child.redeclared_attribute_count == 1
    assert child.inherited_attribute_count == 0
    assert collision.decision == "reject"
    assert any(
        item.reason_code == "inherited_attribute_ambiguity"
        for item in collision.diagnostics
    )


def test_cycles_and_unresolved_names_are_not_silently_selected() -> None:
    """Distinct failure states should survive instead of receiving guessed targets."""
    alias_cycle = resolved_fixture("alias_cycle")
    inheritance_cycle = resolved_fixture("inheritance_cycle")
    missing = resolved_fixture("missing_type")

    assert any(item.status == "cyclic" for item in alias_cycle.types)
    assert any(
        item.status == "cyclic" for item in inheritance_cycle.inheritance
    )
    reference = next(
        item
        for item in missing.references
        if item.role == "attribute_explicit:value"
    )
    assert reference.status == "unresolved"
    assert reference.resolved_symbol_id is None
    assert reference.candidate_symbol_ids == ()


def test_aggregate_bounds_distinguish_literals_constants_and_failures() -> None:
    """The controlled evaluator should report bound provenance and order failures."""
    literal = resolved_fixture("literal_bounds")
    constant = resolved_fixture("constant_bounds")
    invalid = resolved_fixture("invalid_bound_order")

    literal_bound = literal.aggregate_bounds[0]
    assert literal_bound.lower_status == "integer_literal"
    assert literal_bound.lower_value == 1
    assert literal_bound.upper_status == "unbounded"
    constant_bound = constant.aggregate_bounds[0]
    assert constant_bound.upper_status == "integer_constant"
    assert constant_bound.upper_value == 8
    assert invalid.decision == "reject"
    assert invalid.aggregate_bounds[0].status == "unresolved"


def test_inverse_lookup_resolves_forward_attribute_without_executing_rules() -> None:
    """An inverse attribute should point to one named forward attribute."""
    result = resolved_fixture("inverse_attribute")

    inverse = next(
        item
        for item in result.references
        if item.role == "inverse_for_attribute:owners"
    )
    assert inverse.status == "resolved"
    assert inverse.resolved_symbol_id == "demo::owner::attribute::items"
    assert result.rule_execution == "not_attempted"


def test_fixture_generation_and_analysis_ids_are_deterministic() -> None:
    """Repeated construction should preserve source bytes, digests, and symbol IDs."""
    first = build_express_resolution_fixtures()
    second = build_express_resolution_fixtures()

    assert [item.file_name for item in first] == [item.file_name for item in second]
    assert [item.source_bytes for item in first] == [item.source_bytes for item in second]
    assert [hashlib.sha256(item.source_bytes).hexdigest() for item in first] == [
        hashlib.sha256(item.source_bytes).hexdigest() for item in second
    ]
    first_symbols = [item.symbol_id for item in resolved_fixture("use_alias").symbols]
    second_symbols = [item.symbol_id for item in resolved_fixture("use_alias").symbols]
    assert first_symbols == second_symbols


def test_public_entry_points_validate_types_and_resource_limits() -> None:
    """Invalid inputs and semantic budgets should fail with stable boundaries."""
    document = parse_express_document(b"SCHEMA demo; END_SCHEMA;")
    with pytest.raises(TypeError, match="document"):
        resolve_express_document(object())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="limits"):
        resolve_express_document(document, limits=object())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="source_bytes"):
        inspect_express_resolution("not bytes")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="max_symbols"):
        ExpressResolutionLimits(max_symbols=0)
    fixture = fixture_map()["symbol_limit"]
    observation, resolved = inspect_express_resolution(
        fixture.source_bytes,
        resolution_limits=fixture.resolution_limits,
    )
    assert observation.decision == "quarantine"
    assert observation.reason_code == "symbol_count_limit"
    assert resolved is None
    reference_limited, _ = inspect_express_resolution(
        b"SCHEMA demo; TYPE label = STRING; END_TYPE; ENTITY item; a : label; b : label; END_ENTITY; END_SCHEMA;",
        resolution_limits=ExpressResolutionLimits(max_references=1),
    )
    assert reference_limited.decision == "quarantine"
    assert reference_limited.reason_code == "reference_count_limit"
    inheritance_limited, _ = inspect_express_resolution(
        b"SCHEMA demo; ENTITY root; END_ENTITY; ENTITY middle SUBTYPE OF (root); END_ENTITY; ENTITY leaf SUBTYPE OF (middle); END_ENTITY; END_SCHEMA;",
        resolution_limits=ExpressResolutionLimits(max_inheritance_edges=1),
    )
    assert inheritance_limited.decision == "quarantine"
    assert inheritance_limited.reason_code == "inheritance_edge_limit"
