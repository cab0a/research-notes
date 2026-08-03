"""Deterministic paired Part 21 and EXPRESS fixtures for v0.27."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from research_notes.step_express_validation import (
    DEFAULT_STEP_EXPRESS_VALIDATION_LIMITS,
    STEPExpressValidationLimits,
)


@dataclass(frozen=True)
class STEPExpressValidationFixture:
    """One synthetic exchange/schema pair and its expected route."""

    fixture: str
    category: str
    condition: str
    step_file_name: str
    express_file_name: str
    expected_decision: Literal["accept", "quarantine", "reject"]
    expected_reason_code: str
    step_bytes: bytes
    express_bytes: bytes
    validation_limits: STEPExpressValidationLimits = (
        DEFAULT_STEP_EXPRESS_VALIDATION_LIMITS
    )


def _step(
    entities: str,
    *,
    schemas: tuple[str, ...] = ("DEMO",),
    data_header: str = "DATA;",
) -> str:
    schema_values = ",".join(f"'{name}'" for name in schemas)
    return f"""ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('Controlled STEP and EXPRESS validation fixture'),'4;1');
FILE_NAME('fixture.step','2026-01-01T00:00:00',('research-notes'),('research-notes'),'','','');
FILE_SCHEMA(({schema_values}));
ENDSEC;
{data_header}
{entities.strip()}
ENDSEC;
END-ISO-10303-21;
"""


def _fixture(
    fixture: str,
    category: str,
    condition: str,
    expected_decision: Literal["accept", "quarantine", "reject"],
    expected_reason_code: str,
    express: str,
    entities: str,
    *,
    schemas: tuple[str, ...] = ("DEMO",),
    data_header: str = "DATA;",
    step_source: str | None = None,
    validation_limits: STEPExpressValidationLimits = (
        DEFAULT_STEP_EXPRESS_VALIDATION_LIMITS
    ),
) -> STEPExpressValidationFixture:
    return STEPExpressValidationFixture(
        fixture,
        category,
        condition,
        f"{fixture}.step",
        f"{fixture}.exp",
        expected_decision,
        expected_reason_code,
        (step_source or _step(entities, schemas=schemas, data_header=data_header)).encode(
            "utf-8"
        ),
        (express.strip() + "\n").encode("ascii"),
        validation_limits,
    )


def build_step_express_validation_fixtures(
) -> tuple[STEPExpressValidationFixture, ...]:
    """Build the complete paired v0.27 validation corpus."""
    fixtures = (
        _fixture(
            "scalar_types",
            "values",
            "all controlled simple value domains",
            "accept",
            "schema_validation_passed",
            """SCHEMA demo;
ENTITY item;
  integer_value : INTEGER;
  real_value : REAL;
  number_value : NUMBER;
  text_value : STRING;
  flag : BOOLEAN;
  state : LOGICAL;
  bits : BINARY;
END_ENTITY;
END_SCHEMA;""",
            "#1=ITEM(3,1.5,2,'label',.T.,.U.,\"0A\");",
        ),
        _fixture(
            "optional_present",
            "markers",
            "optional explicit value supplied",
            "accept",
            "schema_validation_passed",
            "SCHEMA demo; ENTITY item; label : OPTIONAL STRING; END_ENTITY; END_SCHEMA;",
            "#1=ITEM('present');",
        ),
        _fixture(
            "optional_omitted",
            "markers",
            "optional explicit value omitted with dollar marker",
            "accept",
            "schema_validation_passed",
            "SCHEMA demo; ENTITY item; label : OPTIONAL STRING; END_ENTITY; END_SCHEMA;",
            "#1=ITEM($);",
        ),
        _fixture(
            "enumeration_value",
            "values",
            "declared enumeration member",
            "accept",
            "schema_validation_passed",
            "SCHEMA demo; TYPE state = ENUMERATION OF (new, ready, done); END_TYPE; ENTITY item; value : state; END_ENTITY; END_SCHEMA;",
            "#1=ITEM(.READY.);",
        ),
        _fixture(
            "aggregate_list",
            "aggregates",
            "bounded list cardinality and integer elements",
            "accept",
            "schema_validation_passed",
            "SCHEMA demo; ENTITY item; values : LIST [1:3] OF INTEGER; END_ENTITY; END_SCHEMA;",
            "#1=ITEM((1,2,3));",
        ),
        _fixture(
            "aggregate_set",
            "aggregates",
            "bounded set with distinct elements",
            "accept",
            "schema_validation_passed",
            "SCHEMA demo; ENTITY item; values : SET [1:3] OF INTEGER; END_ENTITY; END_SCHEMA;",
            "#1=ITEM((1,2));",
        ),
        _fixture(
            "forward_entity_reference",
            "references",
            "forward occurrence reference with matching entity type",
            "accept",
            "schema_validation_passed",
            "SCHEMA demo; ENTITY target; label : STRING; END_ENTITY; ENTITY holder; value : target; END_ENTITY; END_SCHEMA;",
            "#1=HOLDER(#2);\n#2=TARGET('target');",
        ),
        _fixture(
            "subtype_entity_reference",
            "references",
            "subtype instance accepted for a supertype attribute",
            "accept",
            "schema_validation_passed",
            "SCHEMA demo; ENTITY base; label : STRING; END_ENTITY; ENTITY child SUBTYPE OF (base); code : INTEGER; END_ENTITY; ENTITY holder; value : base; END_ENTITY; END_SCHEMA;",
            "#1=HOLDER(#2);\n#2=CHILD('child',7);",
        ),
        _fixture(
            "internal_inheritance",
            "inheritance",
            "ancestor attributes precede local attributes",
            "accept",
            "schema_validation_passed",
            "SCHEMA demo; ENTITY root; label : STRING; END_ENTITY; ENTITY middle SUBTYPE OF (root); rank : INTEGER; END_ENTITY; ENTITY leaf SUBTYPE OF (middle); score : REAL; END_ENTITY; END_SCHEMA;",
            "#1=LEAF('leaf',2,3.5);",
        ),
        _fixture(
            "diamond_inheritance",
            "inheritance",
            "shared ancestor attribute encoded once",
            "accept",
            "schema_validation_passed",
            "SCHEMA demo; ENTITY root; label : STRING; END_ENTITY; ENTITY left SUBTYPE OF (root); left_value : INTEGER; END_ENTITY; ENTITY right SUBTYPE OF (root); right_value : BOOLEAN; END_ENTITY; ENTITY leaf SUBTYPE OF (left, right); score : REAL; END_ENTITY; END_SCHEMA;",
            "#1=LEAF('leaf',1,.T.,2.5);",
        ),
        _fixture(
            "select_entity",
            "selects",
            "entity occurrence selected directly",
            "accept",
            "schema_validation_passed",
            "SCHEMA demo; ENTITY target; label : STRING; END_ENTITY; TYPE choice = SELECT (target); END_TYPE; ENTITY holder; value : choice; END_ENTITY; END_SCHEMA;",
            "#1=HOLDER(#2);\n#2=TARGET('selected');",
        ),
        _fixture(
            "select_typed_defined",
            "selects",
            "defined-type select member encoded as a typed parameter",
            "accept",
            "schema_validation_passed",
            "SCHEMA demo; TYPE measured_value = REAL; END_TYPE; TYPE choice = SELECT (measured_value); END_TYPE; ENTITY item; value : choice; END_ENTITY; END_SCHEMA;",
            "#1=ITEM(MEASURED_VALUE(1.5));",
        ),
        _fixture(
            "derived_redeclaration",
            "markers",
            "inherited explicit attribute redeclared as derived",
            "accept",
            "schema_validation_passed",
            "SCHEMA demo; ENTITY base; value : REAL; END_ENTITY; ENTITY child SUBTYPE OF (base); DERIVE SELF\\base.value : REAL := 1.0; END_ENTITY; END_SCHEMA;",
            "#1=CHILD(*);",
        ),
        _fixture(
            "direct_use_entity",
            "schema_binding",
            "direct USE entity visible in governing schema",
            "accept",
            "schema_validation_passed",
            "SCHEMA base; ENTITY target; label : STRING; END_ENTITY; END_SCHEMA; SCHEMA demo; USE FROM base (target); ENTITY holder; value : target; END_ENTITY; END_SCHEMA;",
            "#1=HOLDER(#2);\n#2=TARGET('imported');",
        ),
        _fixture(
            "empty_entity",
            "arity",
            "entity with an empty parameter list",
            "accept",
            "schema_validation_passed",
            "SCHEMA demo; ENTITY marker; END_ENTITY; END_SCHEMA;",
            "#1=MARKER();",
        ),
        _fixture(
            "missing_data_schema",
            "schema_binding",
            "FILE_SCHEMA absent from EXPRESS document",
            "reject",
            "data_schema_not_found",
            "SCHEMA demo; ENTITY item; END_ENTITY; END_SCHEMA;",
            "#1=ITEM();",
            schemas=("MISSING",),
        ),
        _fixture(
            "ambiguous_data_schema",
            "schema_binding",
            "unnamed DATA governed by more than one header schema",
            "reject",
            "ambiguous_unnamed_data_schema",
            "SCHEMA left_schema; ENTITY left_item; END_ENTITY; END_SCHEMA; SCHEMA right_schema; ENTITY right_item; END_ENTITY; END_SCHEMA;",
            "#1=LEFT_ITEM();",
            schemas=("LEFT_SCHEMA", "RIGHT_SCHEMA"),
        ),
        _fixture(
            "unknown_entity",
            "entities",
            "record keyword absent from governing schema",
            "reject",
            "unknown_entity_type",
            "SCHEMA demo; ENTITY item; END_ENTITY; END_SCHEMA;",
            "#1=MISSING();",
        ),
        _fixture(
            "abstract_entity",
            "entities",
            "abstract entity instantiated directly",
            "reject",
            "abstract_entity_instance",
            "SCHEMA demo; ENTITY item ABSTRACT; value : INTEGER; END_ENTITY; END_SCHEMA;",
            "#1=ITEM(1);",
        ),
        _fixture(
            "parameter_count_short",
            "arity",
            "required parameter is absent",
            "reject",
            "parameter_count_mismatch",
            "SCHEMA demo; ENTITY item; first : INTEGER; second : STRING; END_ENTITY; END_SCHEMA;",
            "#1=ITEM(1);",
        ),
        _fixture(
            "required_value_omitted",
            "markers",
            "dollar marker used for required attribute",
            "reject",
            "required_value_omitted",
            "SCHEMA demo; ENTITY item; label : STRING; END_ENTITY; END_SCHEMA;",
            "#1=ITEM($);",
        ),
        _fixture(
            "unexpected_derived_marker",
            "markers",
            "asterisk used for ordinary explicit attribute",
            "reject",
            "unexpected_derived_marker",
            "SCHEMA demo; ENTITY item; value : REAL; END_ENTITY; END_SCHEMA;",
            "#1=ITEM(*);",
        ),
        _fixture(
            "derived_marker_required",
            "markers",
            "derived redeclaration encoded with a concrete value",
            "reject",
            "derived_marker_required",
            "SCHEMA demo; ENTITY base; value : REAL; END_ENTITY; ENTITY child SUBTYPE OF (base); DERIVE SELF\\base.value : REAL := 1.0; END_ENTITY; END_SCHEMA;",
            "#1=CHILD(1.0);",
        ),
        _fixture(
            "wrong_scalar_type",
            "values",
            "string supplied for integer attribute",
            "reject",
            "parameter_type_mismatch",
            "SCHEMA demo; ENTITY item; value : INTEGER; END_ENTITY; END_SCHEMA;",
            "#1=ITEM('one');",
        ),
        _fixture(
            "invalid_enumeration",
            "values",
            "enumeration token absent from declared members",
            "reject",
            "enumeration_value_invalid",
            "SCHEMA demo; TYPE state = ENUMERATION OF (new, done); END_TYPE; ENTITY item; value : state; END_ENTITY; END_SCHEMA;",
            "#1=ITEM(.MISSING.);",
        ),
        _fixture(
            "aggregate_cardinality",
            "aggregates",
            "list shorter than declared lower bound",
            "reject",
            "aggregate_cardinality_mismatch",
            "SCHEMA demo; ENTITY item; values : LIST [2:3] OF INTEGER; END_ENTITY; END_SCHEMA;",
            "#1=ITEM((1));",
        ),
        _fixture(
            "aggregate_duplicate",
            "aggregates",
            "set contains duplicate values",
            "reject",
            "aggregate_unique_violation",
            "SCHEMA demo; ENTITY item; values : SET [1:3] OF INTEGER; END_ENTITY; END_SCHEMA;",
            "#1=ITEM((1,1));",
        ),
        _fixture(
            "unresolved_entity_reference",
            "references",
            "entity occurrence target is absent",
            "reject",
            "unresolved_entity_reference",
            "SCHEMA demo; ENTITY target; END_ENTITY; ENTITY holder; value : target; END_ENTITY; END_SCHEMA;",
            "#1=HOLDER(#99);",
        ),
        _fixture(
            "wrong_reference_type",
            "references",
            "entity occurrence has an incompatible entity type",
            "reject",
            "entity_reference_type_mismatch",
            "SCHEMA demo; ENTITY expected; END_ENTITY; ENTITY other; END_ENTITY; ENTITY holder; value : expected; END_ENTITY; END_SCHEMA;",
            "#1=HOLDER(#2);\n#2=OTHER();",
        ),
        _fixture(
            "select_untyped",
            "selects",
            "defined-type select value lacks its type wrapper",
            "reject",
            "select_typed_parameter_required",
            "SCHEMA demo; TYPE measured_value = REAL; END_TYPE; TYPE choice = SELECT (measured_value); END_TYPE; ENTITY item; value : choice; END_ENTITY; END_SCHEMA;",
            "#1=ITEM(1.5);",
        ),
        _fixture(
            "select_wrong_member",
            "selects",
            "typed parameter names a type outside the select",
            "reject",
            "select_member_invalid",
            "SCHEMA demo; TYPE measured_value = REAL; END_TYPE; TYPE other_value = REAL; END_TYPE; TYPE choice = SELECT (measured_value); END_TYPE; ENTITY item; value : choice; END_ENTITY; END_SCHEMA;",
            "#1=ITEM(OTHER_VALUE(1.5));",
        ),
        _fixture(
            "inheritance_parameter_order",
            "inheritance",
            "local and inherited values are swapped",
            "reject",
            "parameter_type_mismatch",
            "SCHEMA demo; ENTITY base; label : STRING; END_ENTITY; ENTITY child SUBTYPE OF (base); rank : INTEGER; END_ENTITY; END_SCHEMA;",
            "#1=CHILD(1,'label');",
        ),
        _fixture(
            "complex_component_order",
            "complex_mapping",
            "external component records are not sorted",
            "reject",
            "complex_component_order",
            "SCHEMA demo; ENTITY base; label : STRING; END_ENTITY; ENTITY left SUBTYPE OF (base); left_value : INTEGER; END_ENTITY; ENTITY right SUBTYPE OF (base); right_value : REAL; END_ENTITY; END_SCHEMA;",
            "#1=(LEFT(1)BASE('root')RIGHT(2.0));",
        ),
        _fixture(
            "express_resolution_failure",
            "staging",
            "EXPRESS contains an unresolved attribute type",
            "reject",
            "express_resolution_failed",
            "SCHEMA demo; ENTITY item; value : missing_type; END_ENTITY; END_SCHEMA;",
            "#1=ITEM(1);",
        ),
        _fixture(
            "part21_syntax_failure",
            "staging",
            "Part 21 entity terminator is missing",
            "reject",
            "unexpected_token",
            "SCHEMA demo; ENTITY item; END_ENTITY; END_SCHEMA;",
            "",
            step_source=_step("#1=ITEM()\n"),
        ),
        _fixture(
            "express_syntax_failure",
            "staging",
            "EXPRESS schema terminator is missing",
            "reject",
            "missing_end_schema",
            "SCHEMA demo; ENTITY item; END_ENTITY;",
            "#1=ITEM();",
        ),
        _fixture(
            "complex_mapping_deferred",
            "complex_mapping",
            "component closure and local parameters pass before evaluated-set deferral",
            "quarantine",
            "complex_evaluated_set_deferred",
            "SCHEMA demo; ENTITY base; label : STRING; END_ENTITY; ENTITY left SUBTYPE OF (base); left_value : INTEGER; END_ENTITY; ENTITY right SUBTYPE OF (base); right_value : REAL; END_ENTITY; END_SCHEMA;",
            "#1=(BASE('root')LEFT(1)RIGHT(2.0));",
        ),
        _fixture(
            "constant_reference_deferred",
            "deferred_values",
            "schema constant occurrence requires value resolution",
            "quarantine",
            "external_value_resolution_deferred",
            "SCHEMA demo; ENTITY item; value : INTEGER; END_ENTITY; END_SCHEMA;",
            "#1=ITEM(#LIMIT);",
        ),
        _fixture(
            "width_constraint_deferred",
            "deferred_values",
            "fixed string width remains outside controlled validation",
            "quarantine",
            "width_constraint_deferred",
            "SCHEMA demo; ENTITY item; label : STRING(4) FIXED; END_ENTITY; END_SCHEMA;",
            "#1=ITEM('text');",
        ),
        _fixture(
            "validation_parameter_limit",
            "resources",
            "schema-bound parameter budget is exceeded",
            "quarantine",
            "validation_parameter_limit",
            "SCHEMA demo; ENTITY item; first : INTEGER; second : INTEGER; END_ENTITY; END_SCHEMA;",
            "#1=ITEM(1,2);",
            validation_limits=STEPExpressValidationLimits(max_parameters=1),
        ),
    )
    return fixtures
