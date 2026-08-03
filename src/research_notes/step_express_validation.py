"""Bounded Part 21 instance validation against controlled EXPRESS schemas."""

from __future__ import annotations

from dataclasses import dataclass, replace
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
    ExpressAttribute,
    ExpressDocument,
    ExpressEntityDeclaration,
    ExpressParseError,
    ExpressParseLimits,
    ExpressSchemaDeclaration,
    ExpressTypeDeclaration,
    ExpressTypeReference,
    parse_express_document,
)
from research_notes.step_part21 import (
    DEFAULT_STEP_PARSE_LIMITS,
    STEPParseLimits,
    Part21DataSection,
    Part21Document,
    Part21Entity,
    Part21ParseError,
    Part21Record,
    Part21Value,
    parse_part21_document,
)


ValidationDecision = Literal["accept", "quarantine", "reject"]
ValidationStatus = Literal["valid", "invalid", "deferred", "not_reached"]


@dataclass(frozen=True)
class STEPExpressValidationLimits:
    """Explicit limits for schema-bound instance validation."""

    max_instances: int = 20_000
    max_parameters: int = 200_000
    max_validation_depth: int = 32

    def __post_init__(self) -> None:
        for field_name, value in vars(self).items():
            if value <= 0:
                raise ValueError(f"{field_name} must be positive")


DEFAULT_STEP_EXPRESS_VALIDATION_LIMITS = STEPExpressValidationLimits()


@dataclass(frozen=True)
class STEPExpressDiagnostic:
    """One stable schema-binding, instance, or parameter diagnostic."""

    severity: Literal["invalid", "deferred"]
    reason_code: str
    stage: str
    section_index: int | None
    entity_id: int | None
    record_index: int | None
    parameter_index: int | None
    source_line: int | None
    detail: str


@dataclass(frozen=True)
class STEPExpressSectionValidation:
    """Schema ownership resolved for one Part 21 DATA section."""

    section_index: int
    section_name: str | None
    declared_schema: str | None
    resolved_schema: str | None
    entity_count: int
    status: ValidationStatus
    reason_code: str


@dataclass(frozen=True)
class STEPExpressInstanceValidation:
    """Validation result for one simple or complex entity instance."""

    section_index: int
    entity_id: int
    mapping: Literal["internal", "external"]
    record_types: tuple[str, ...]
    resolved_entity_ids: tuple[str, ...]
    expected_parameter_count: int
    actual_parameter_count: int
    status: ValidationStatus
    reason_code: str


@dataclass(frozen=True)
class STEPExpressParameterValidation:
    """One Part 21 parameter matched to one EXPRESS explicit attribute."""

    section_index: int
    entity_id: int
    record_index: int
    parameter_index: int
    entity_type: str
    attribute_owner: str
    attribute_name: str
    expected_type: str
    value_kind: str
    value_source: str
    status: ValidationStatus
    reason_code: str
    source_line: int


@dataclass(frozen=True)
class STEPExpressValidationResult:
    """Staged Part 21-to-EXPRESS validation evidence."""

    decision: ValidationDecision
    reason_code: str
    part21_syntax: ValidationStatus
    express_syntax: ValidationStatus
    express_resolution: ValidationStatus
    schema_binding: ValidationStatus
    instance_validation: ValidationStatus
    section_count: int
    instance_count: int
    parameter_count: int
    valid_parameter_count: int
    invalid_parameter_count: int
    deferred_parameter_count: int
    sections: tuple[STEPExpressSectionValidation, ...]
    instances: tuple[STEPExpressInstanceValidation, ...]
    parameters: tuple[STEPExpressParameterValidation, ...]
    diagnostics: tuple[STEPExpressDiagnostic, ...]
    application_semantics: Literal["not_attempted"] = "not_attempted"
    rule_execution: Literal["not_attempted"] = "not_attempted"


class STEPExpressValidationLimitError(RuntimeError):
    """A stable quarantine outcome for a validation resource limit."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


@dataclass(frozen=True)
class _NamedDeclaration:
    kind: Literal["type", "entity"]
    symbol_id: str
    schema_name: str
    name: str
    declaration: ExpressTypeDeclaration | ExpressEntityDeclaration


@dataclass(frozen=True)
class _AttributeSlot:
    owner_entity_id: str
    attribute: ExpressAttribute
    requires_derived_marker: bool = False


@dataclass(frozen=True)
class _ValueCheck:
    status: Literal["valid", "invalid", "deferred"]
    reason_code: str


class _Validator:
    def __init__(
        self,
        part21: Part21Document,
        express: ExpressDocument,
        resolved: ExpressResolvedDocument,
        limits: STEPExpressValidationLimits,
    ) -> None:
        self.part21 = part21
        self.express = express
        self.resolved = resolved
        self.limits = limits
        self.schemas = {
            schema.name.casefold(): schema for schema in express.schemas
        }
        self.declarations: dict[str, _NamedDeclaration] = {}
        self.visible: dict[str, dict[str, list[_NamedDeclaration]]] = {}
        self.inheritance = {
            item.symbol_id: item for item in resolved.inheritance
        }
        self.sections: list[STEPExpressSectionValidation] = []
        self.instances: list[STEPExpressInstanceValidation] = []
        self.parameters: list[STEPExpressParameterValidation] = []
        self.diagnostics: list[STEPExpressDiagnostic] = []
        self.section_schemas: dict[int, ExpressSchemaDeclaration] = {}
        self.instance_types: dict[int, tuple[str, ...]] = {}
        self.instance_sections: dict[int, int] = {}
        self._layout_cache: dict[str, tuple[_AttributeSlot, ...]] = {}
        self._value_count = 0
        self._index_declarations()
        self._build_visibility()

    def validate(self) -> STEPExpressValidationResult:
        self._bind_sections()
        self._index_instance_types()
        self._validate_instances()
        invalid = [item for item in self.diagnostics if item.severity == "invalid"]
        deferred = [item for item in self.diagnostics if item.severity == "deferred"]
        if invalid:
            decision: ValidationDecision = "reject"
            reason_code = invalid[0].reason_code
            instance_status: ValidationStatus = "invalid"
        elif deferred:
            decision = "quarantine"
            reason_code = deferred[0].reason_code
            instance_status = "deferred"
        else:
            decision = "accept"
            reason_code = "schema_validation_passed"
            instance_status = "valid"
        schema_invalid = any(item.status == "invalid" for item in self.sections)
        parameter_statuses = [item.status for item in self.parameters]
        return STEPExpressValidationResult(
            decision=decision,
            reason_code=reason_code,
            part21_syntax="valid",
            express_syntax="valid",
            express_resolution="valid",
            schema_binding="invalid" if schema_invalid else "valid",
            instance_validation=instance_status,
            section_count=len(self.sections),
            instance_count=len(self.instances),
            parameter_count=len(self.parameters),
            valid_parameter_count=parameter_statuses.count("valid"),
            invalid_parameter_count=parameter_statuses.count("invalid"),
            deferred_parameter_count=parameter_statuses.count("deferred"),
            sections=tuple(self.sections),
            instances=tuple(self.instances),
            parameters=tuple(self.parameters),
            diagnostics=tuple(self.diagnostics),
        )

    def _index_declarations(self) -> None:
        for schema in self.express.schemas:
            for declaration in schema.types:
                self._add_declaration(schema, declaration, "type")
            for declaration in schema.entities:
                self._add_declaration(schema, declaration, "entity")

    def _add_declaration(
        self,
        schema: ExpressSchemaDeclaration,
        declaration: ExpressTypeDeclaration | ExpressEntityDeclaration,
        kind: Literal["type", "entity"],
    ) -> None:
        symbol_id = f"{schema.name.casefold()}::{declaration.name.casefold()}"
        self.declarations[symbol_id] = _NamedDeclaration(
            kind, symbol_id, schema.name, declaration.name, declaration
        )

    def _build_visibility(self) -> None:
        for schema in self.express.schemas:
            local: dict[str, list[_NamedDeclaration]] = {}
            for declaration in self.declarations.values():
                if declaration.schema_name.casefold() == schema.name.casefold():
                    local.setdefault(declaration.name.casefold(), []).append(declaration)
            for interface in schema.interfaces:
                if interface.kind != "use":
                    continue
                source = self.schemas.get(interface.schema_name.casefold())
                if source is None:
                    continue
                source_items = [
                    item
                    for item in self.declarations.values()
                    if item.schema_name.casefold() == source.name.casefold()
                ]
                if interface.items:
                    requested = {
                        item.name.casefold(): (item.alias or item.name).casefold()
                        for item in interface.items
                    }
                    source_items = [
                        item for item in source_items if item.name.casefold() in requested
                    ]
                    for item in source_items:
                        local.setdefault(requested[item.name.casefold()], []).append(item)
                else:
                    for item in source_items:
                        local.setdefault(item.name.casefold(), []).append(item)
            self.visible[schema.name.casefold()] = local

    def _bind_sections(self) -> None:
        for index, section in enumerate(self.part21.data_sections):
            declared = section.schema_identifier
            if declared is None and len(self.part21.schema_identifiers) == 1:
                declared = self.part21.schema_identifiers[0]
            if declared is None:
                reason = "ambiguous_data_schema"
                self.sections.append(
                    STEPExpressSectionValidation(
                        index, section.name, None, None, len(section.entities),
                        "invalid", reason,
                    )
                )
                self._diagnose(
                    "invalid", reason, "schema_binding", index, None, None,
                    None, section.span.start_line,
                    "DATA section does not identify one governing schema",
                )
                continue
            schema = self.schemas.get(declared.casefold())
            if schema is None:
                reason = "data_schema_not_found"
                self.sections.append(
                    STEPExpressSectionValidation(
                        index, section.name, declared, None, len(section.entities),
                        "invalid", reason,
                    )
                )
                self._diagnose(
                    "invalid", reason, "schema_binding", index, None, None,
                    None, section.span.start_line,
                    f"schema {declared!r} is not present in the EXPRESS document",
                )
                continue
            self.section_schemas[index] = schema
            self.sections.append(
                STEPExpressSectionValidation(
                    index, section.name, declared, schema.name,
                    len(section.entities), "valid", "schema_resolved",
                )
            )

    def _index_instance_types(self) -> None:
        count = 0
        for section_index, section in enumerate(self.part21.data_sections):
            schema = self.section_schemas.get(section_index)
            if schema is None:
                continue
            for entity in section.entities:
                count += 1
                if count > self.limits.max_instances:
                    raise STEPExpressValidationLimitError(
                        "validation_instance_limit",
                        "instance validation exceeds the configured limit",
                    )
                resolved_ids: list[str] = []
                for record in entity.records:
                    declaration = self._visible_declaration(
                        schema.name, record.type_name, "entity"
                    )
                    if declaration is not None:
                        resolved_ids.append(declaration.symbol_id)
                self.instance_types[entity.entity_id] = tuple(resolved_ids)
                self.instance_sections[entity.entity_id] = section_index

    def _validate_instances(self) -> None:
        for section_index, section in enumerate(self.part21.data_sections):
            schema = self.section_schemas.get(section_index)
            if schema is None:
                continue
            for entity in section.entities:
                if entity.is_complex:
                    self._validate_complex_instance(section_index, schema, entity)
                else:
                    self._validate_simple_instance(section_index, schema, entity)

    def _validate_simple_instance(
        self,
        section_index: int,
        schema: ExpressSchemaDeclaration,
        entity: Part21Entity,
    ) -> None:
        record = entity.records[0]
        declaration = self._visible_declaration(
            schema.name, record.type_name, "entity"
        )
        if declaration is None:
            self._unknown_entity(section_index, entity, 0, record)
            return
        express_entity = declaration.declaration
        assert isinstance(express_entity, ExpressEntityDeclaration)
        if express_entity.abstract:
            self._diagnose(
                "invalid", "abstract_entity_instance", "instance_validation",
                section_index, entity.entity_id, 0, None,
                record.span.start_line,
                f"abstract entity {declaration.name!r} cannot be instantiated directly",
            )
        slots = self._internal_layout(declaration.symbol_id)
        status, reason = self._validate_record(
            section_index, entity, 0, record, declaration, slots
        )
        if express_entity.abstract:
            status, reason = "invalid", "abstract_entity_instance"
        self.instances.append(
            STEPExpressInstanceValidation(
                section_index,
                entity.entity_id,
                "internal",
                (record.type_name,),
                (declaration.symbol_id,),
                len(slots),
                len(record.arguments),
                status,
                reason,
            )
        )

    def _validate_complex_instance(
        self,
        section_index: int,
        schema: ExpressSchemaDeclaration,
        entity: Part21Entity,
    ) -> None:
        resolved_items: list[_NamedDeclaration] = []
        for record_index, record in enumerate(entity.records):
            declaration = self._visible_declaration(
                schema.name, record.type_name, "entity"
            )
            if declaration is None:
                self._unknown_entity(section_index, entity, record_index, record)
            else:
                resolved_items.append(declaration)
        record_names = tuple(record.type_name for record in entity.records)
        invalid_reason: str | None = None
        if len(resolved_items) != len(entity.records):
            invalid_reason = "unknown_entity_type"
        elif len({item.symbol_id for item in resolved_items}) != len(resolved_items):
            invalid_reason = "duplicate_complex_component"
            self._diagnose(
                "invalid", invalid_reason, "instance_validation", section_index,
                entity.entity_id, None, None, entity.span.start_line,
                "complex instance repeats an entity component",
            )
        elif record_names != tuple(sorted(record_names)):
            invalid_reason = "complex_component_order"
            self._diagnose(
                "invalid", invalid_reason, "instance_validation", section_index,
                entity.entity_id, None, None, entity.span.start_line,
                "complex component records are not in ascending encoded-name order",
            )
        component_ids = {item.symbol_id for item in resolved_items}
        if invalid_reason is None:
            missing_ancestors = sorted(
                {
                    ancestor
                    for item in resolved_items
                    for ancestor in self._ancestors(item.symbol_id)
                    if ancestor not in component_ids
                }
            )
            if missing_ancestors:
                invalid_reason = "complex_component_closure"
                self._diagnose(
                    "invalid", invalid_reason, "instance_validation", section_index,
                    entity.entity_id, None, None, entity.span.start_line,
                    "complex instance omits required ancestor components: "
                    + ", ".join(missing_ancestors),
                )
        expected = 0
        actual = sum(len(record.arguments) for record in entity.records)
        aggregate_status: ValidationStatus = "valid"
        aggregate_reason = "parameters_valid"
        if invalid_reason is None:
            slots_by_entity = {
                item.symbol_id: list(self._local_slots(item.symbol_id))
                for item in resolved_items
            }
            self._apply_complex_redeclarations(resolved_items, slots_by_entity)
            for record_index, (record, declaration) in enumerate(
                zip(entity.records, resolved_items, strict=True)
            ):
                slots = tuple(slots_by_entity[declaration.symbol_id])
                expected += len(slots)
                status, reason = self._validate_record(
                    section_index, entity, record_index, record, declaration, slots
                )
                if status == "invalid":
                    aggregate_status, aggregate_reason = status, reason
                elif status == "deferred" and aggregate_status == "valid":
                    aggregate_status, aggregate_reason = status, reason
            if aggregate_status != "invalid":
                aggregate_status = "deferred"
                aggregate_reason = "complex_evaluated_set_deferred"
                self._diagnose(
                    "deferred", aggregate_reason, "instance_validation",
                    section_index, entity.entity_id, None, None,
                    entity.span.start_line,
                    "component closure is checked, but complete EXPRESS evaluated-set semantics are not implemented",
                )
        else:
            aggregate_status, aggregate_reason = "invalid", invalid_reason
        self.instances.append(
            STEPExpressInstanceValidation(
                section_index,
                entity.entity_id,
                "external",
                record_names,
                tuple(item.symbol_id for item in resolved_items),
                expected,
                actual,
                aggregate_status,
                aggregate_reason,
            )
        )

    def _unknown_entity(
        self,
        section_index: int,
        entity: Part21Entity,
        record_index: int,
        record: Part21Record,
    ) -> None:
        self._diagnose(
            "invalid", "unknown_entity_type", "instance_validation",
            section_index, entity.entity_id, record_index, None,
            record.span.start_line,
            f"entity type {record.type_name!r} is not visible in the governing schema",
        )
        if not entity.is_complex:
            self.instances.append(
                STEPExpressInstanceValidation(
                    section_index, entity.entity_id, "internal",
                    (record.type_name,), (), 0, len(record.arguments),
                    "invalid", "unknown_entity_type",
                )
            )

    def _validate_record(
        self,
        section_index: int,
        entity: Part21Entity,
        record_index: int,
        record: Part21Record,
        declaration: _NamedDeclaration,
        slots: tuple[_AttributeSlot, ...],
    ) -> tuple[ValidationStatus, str]:
        status: ValidationStatus = "valid"
        reason = "parameters_valid"
        if len(record.arguments) != len(slots):
            status, reason = "invalid", "parameter_count_mismatch"
            self._diagnose(
                "invalid", reason, "instance_validation", section_index,
                entity.entity_id, record_index, None, record.span.start_line,
                f"{record.type_name} expects {len(slots)} parameters but received {len(record.arguments)}",
            )
        for parameter_index, (value, slot) in enumerate(
            zip(record.arguments, slots)
        ):
            self._value_count += 1
            if self._value_count > self.limits.max_parameters:
                raise STEPExpressValidationLimitError(
                    "validation_parameter_limit",
                    "parameter validation exceeds the configured limit",
                )
            check = self._validate_slot(value, slot, depth=1)
            if check.status == "invalid":
                status, reason = "invalid", check.reason_code
            elif check.status == "deferred" and status == "valid":
                status, reason = "deferred", check.reason_code
            owner = self.declarations[slot.owner_entity_id]
            self.parameters.append(
                STEPExpressParameterValidation(
                    section_index,
                    entity.entity_id,
                    record_index,
                    parameter_index,
                    record.type_name,
                    owner.name,
                    slot.attribute.name,
                    self._type_label(slot.attribute.type_ref),
                    value.kind,
                    self.part21.source_slice(value.span),
                    check.status,
                    check.reason_code,
                    value.span.start_line,
                )
            )
            if check.status != "valid":
                self._diagnose(
                    check.status,
                    check.reason_code,
                    "parameter_validation",
                    section_index,
                    entity.entity_id,
                    record_index,
                    parameter_index,
                    value.span.start_line,
                    f"parameter for {owner.name}.{slot.attribute.name} is {check.reason_code}",
                )
        return status, reason

    def _validate_slot(
        self, value: Part21Value, slot: _AttributeSlot, *, depth: int
    ) -> _ValueCheck:
        if slot.requires_derived_marker:
            return (
                _ValueCheck("valid", "derived_marker_valid")
                if value.kind == "derived"
                else _ValueCheck("invalid", "derived_marker_required")
            )
        if value.kind == "derived":
            return _ValueCheck("invalid", "unexpected_derived_marker")
        if value.kind == "omitted":
            return (
                _ValueCheck("valid", "optional_omission_valid")
                if slot.attribute.optional
                else _ValueCheck("invalid", "required_value_omitted")
            )
        owner = self.declarations[slot.owner_entity_id]
        return self._validate_value(
            value, slot.attribute.type_ref, owner.schema_name, depth=depth
        )

    def _validate_value(
        self,
        value: Part21Value,
        type_ref: ExpressTypeReference,
        schema_name: str,
        *,
        depth: int,
    ) -> _ValueCheck:
        if depth > self.limits.max_validation_depth:
            raise STEPExpressValidationLimitError(
                "validation_depth_limit",
                "value validation exceeds the configured depth limit",
            )
        if value.kind in {"constant_reference", "value_reference"}:
            return _ValueCheck("deferred", "external_value_resolution_deferred")
        if value.kind in {"omitted", "derived"}:
            return _ValueCheck("invalid", "nested_marker_invalid")
        if type_ref.kind == "simple":
            return self._validate_simple_value(value, type_ref)
        if type_ref.kind == "enumeration":
            if value.kind != "enumeration":
                return _ValueCheck("invalid", "parameter_type_mismatch")
            members = {member.casefold() for member in type_ref.members}
            return (
                _ValueCheck("valid", "enumeration_value_valid")
                if str(value.value).casefold() in members
                else _ValueCheck("invalid", "enumeration_value_invalid")
            )
        if type_ref.kind == "aggregate":
            return self._validate_aggregate(value, type_ref, schema_name, depth)
        if type_ref.kind == "select":
            return self._validate_select(value, type_ref, schema_name, depth)
        if type_ref.kind == "named" and type_ref.name is not None:
            declaration = self._visible_declaration(schema_name, type_ref.name)
            if declaration is None:
                return _ValueCheck("invalid", "named_type_unresolved")
            if declaration.kind == "entity":
                return self._validate_entity_reference(value, declaration.symbol_id)
            defined = declaration.declaration
            assert isinstance(defined, ExpressTypeDeclaration)
            nested = value
            if (
                value.kind == "typed"
                and str(value.value).casefold() == declaration.name.casefold()
            ):
                if len(value.children) != 1:
                    return _ValueCheck("invalid", "typed_parameter_arity")
                nested = value.children[0]
            return self._validate_value(
                nested,
                defined.underlying_type,
                declaration.schema_name,
                depth=depth + 1,
            )
        return _ValueCheck("deferred", "type_expression_deferred")

    @staticmethod
    def _validate_simple_value(
        value: Part21Value, type_ref: ExpressTypeReference
    ) -> _ValueCheck:
        if type_ref.parameter is not None:
            return _ValueCheck("deferred", "width_constraint_deferred")
        expected = {
            "INTEGER": {"integer"},
            "REAL": {"real"},
            "NUMBER": {"integer", "real"},
            "STRING": {"string"},
            "BINARY": {"binary"},
        }
        if type_ref.name in expected:
            return (
                _ValueCheck("valid", "scalar_value_valid")
                if value.kind in expected[type_ref.name]
                else _ValueCheck("invalid", "parameter_type_mismatch")
            )
        if type_ref.name == "BOOLEAN":
            valid = value.kind == "enumeration" and value.value in {"T", "F"}
            return _ValueCheck(
                "valid" if valid else "invalid",
                "boolean_value_valid" if valid else "boolean_value_invalid",
            )
        if type_ref.name == "LOGICAL":
            valid = value.kind == "enumeration" and value.value in {"T", "F", "U"}
            return _ValueCheck(
                "valid" if valid else "invalid",
                "logical_value_valid" if valid else "logical_value_invalid",
            )
        return _ValueCheck("deferred", "simple_type_deferred")

    def _validate_aggregate(
        self,
        value: Part21Value,
        type_ref: ExpressTypeReference,
        schema_name: str,
        depth: int,
    ) -> _ValueCheck:
        if value.kind != "list" or type_ref.element_type is None:
            return _ValueCheck("invalid", "parameter_type_mismatch")
        lower = self._literal_bound(type_ref.lower_bound)
        upper = self._literal_bound(type_ref.upper_bound)
        if lower is ... or upper is ...:
            return _ValueCheck("deferred", "aggregate_bound_expression_deferred")
        count = len(value.children)
        if type_ref.aggregate_kind == "ARRAY" and lower is not None and upper is not None:
            if count != upper - lower + 1:
                return _ValueCheck("invalid", "aggregate_cardinality_mismatch")
        else:
            if lower is not None and count < lower:
                return _ValueCheck("invalid", "aggregate_cardinality_mismatch")
            if upper is not None and count > upper:
                return _ValueCheck("invalid", "aggregate_cardinality_mismatch")
        if type_ref.unique or type_ref.aggregate_kind == "SET":
            keys = [self._value_key(item) for item in value.children]
            if len(keys) != len(set(keys)):
                return _ValueCheck("invalid", "aggregate_unique_violation")
        deferred = False
        for child in value.children:
            if child.kind == "omitted" and type_ref.optional:
                continue
            check = self._validate_value(
                child,
                type_ref.element_type,
                schema_name,
                depth=depth + 1,
            )
            if check.status == "invalid":
                return check
            deferred = deferred or check.status == "deferred"
        return _ValueCheck(
            "deferred" if deferred else "valid",
            "aggregate_element_deferred" if deferred else "aggregate_value_valid",
        )

    def _validate_select(
        self,
        value: Part21Value,
        type_ref: ExpressTypeReference,
        schema_name: str,
        depth: int,
    ) -> _ValueCheck:
        members = [
            self._visible_declaration(schema_name, name)
            for name in type_ref.members
        ]
        members = [item for item in members if item is not None]
        if value.kind == "entity_reference":
            matches = [
                item
                for item in members
                if item.kind == "entity"
                and self._entity_reference_matches(value, item.symbol_id)
            ]
            return (
                _ValueCheck("valid", "select_entity_value_valid")
                if matches
                else _ValueCheck("invalid", "select_entity_type_mismatch")
            )
        if value.kind != "typed" or len(value.children) != 1:
            return _ValueCheck("invalid", "select_typed_parameter_required")
        wrapper = str(value.value).casefold()
        matching = [item for item in members if item.name.casefold() == wrapper]
        if len(matching) != 1 or matching[0].kind != "type":
            return _ValueCheck("invalid", "select_member_invalid")
        declaration = matching[0]
        defined = declaration.declaration
        assert isinstance(defined, ExpressTypeDeclaration)
        return self._validate_value(
            value.children[0],
            defined.underlying_type,
            declaration.schema_name,
            depth=depth + 1,
        )

    def _validate_entity_reference(
        self, value: Part21Value, expected_entity_id: str
    ) -> _ValueCheck:
        if value.kind != "entity_reference":
            return _ValueCheck("invalid", "parameter_type_mismatch")
        try:
            target = int(str(value.value)[1:])
        except ValueError:
            return _ValueCheck("invalid", "entity_reference_invalid")
        if target not in self.instance_types:
            return _ValueCheck("invalid", "unresolved_entity_reference")
        if not self.instance_types[target]:
            return _ValueCheck("invalid", "target_instance_type_unavailable")
        if self._entity_reference_matches(value, expected_entity_id):
            return _ValueCheck("valid", "entity_reference_valid")
        return _ValueCheck("invalid", "entity_reference_type_mismatch")

    def _entity_reference_matches(
        self, value: Part21Value, expected_entity_id: str
    ) -> bool:
        target = int(str(value.value)[1:])
        actual_ids = self.instance_types.get(target, ())
        return any(
            actual == expected_entity_id
            or expected_entity_id in self._ancestors(actual)
            for actual in actual_ids
        )

    def _internal_layout(self, entity_id: str) -> tuple[_AttributeSlot, ...]:
        if entity_id in self._layout_cache:
            return self._layout_cache[entity_id]
        ordered: list[_AttributeSlot] = []
        seen_origins: set[tuple[str, str]] = set()
        inheritance = self.inheritance[entity_id]
        for parent_id in inheritance.immediate_supertype_ids:
            for slot in self._internal_layout(parent_id):
                key = (slot.owner_entity_id, slot.attribute.name.casefold())
                if key not in seen_origins:
                    seen_origins.add(key)
                    ordered.append(slot)
        declaration = self.declarations[entity_id]
        entity = declaration.declaration
        assert isinstance(entity, ExpressEntityDeclaration)
        ordered = self._apply_redeclarations(entity, ordered)
        for slot in self._local_slots(entity_id):
            key = (slot.owner_entity_id, slot.attribute.name.casefold())
            if key not in seen_origins:
                seen_origins.add(key)
                ordered.append(slot)
        result = tuple(ordered)
        self._layout_cache[entity_id] = result
        return result

    def _local_slots(self, entity_id: str) -> tuple[_AttributeSlot, ...]:
        entity = self.declarations[entity_id].declaration
        assert isinstance(entity, ExpressEntityDeclaration)
        return tuple(
            _AttributeSlot(entity_id, attribute)
            for attribute in entity.attributes
            if attribute.kind == "explicit" and attribute.redeclared_from is None
        )

    def _apply_redeclarations(
        self,
        entity: ExpressEntityDeclaration,
        slots: list[_AttributeSlot],
    ) -> list[_AttributeSlot]:
        output = list(slots)
        for redeclaration in entity.attributes:
            if redeclaration.redeclared_from is None:
                continue
            for index, slot in enumerate(output):
                owner = self.declarations[slot.owner_entity_id]
                if (
                    owner.name.casefold() == redeclaration.redeclared_from.casefold()
                    and slot.attribute.name.casefold() == redeclaration.name.casefold()
                    and redeclaration.kind == "derived"
                ):
                    output[index] = replace(slot, requires_derived_marker=True)
        return output

    def _apply_complex_redeclarations(
        self,
        declarations: list[_NamedDeclaration],
        slots_by_entity: dict[str, list[_AttributeSlot]],
    ) -> None:
        for declaration in declarations:
            entity = declaration.declaration
            assert isinstance(entity, ExpressEntityDeclaration)
            for redeclaration in entity.attributes:
                if redeclaration.redeclared_from is None or redeclaration.kind != "derived":
                    continue
                target = next(
                    (
                        item
                        for item in declarations
                        if item.name.casefold() == redeclaration.redeclared_from.casefold()
                    ),
                    None,
                )
                if target is None:
                    continue
                slots_by_entity[target.symbol_id] = [
                    replace(slot, requires_derived_marker=True)
                    if slot.attribute.name.casefold() == redeclaration.name.casefold()
                    else slot
                    for slot in slots_by_entity[target.symbol_id]
                ]

    def _ancestors(self, entity_id: str) -> tuple[str, ...]:
        item = self.inheritance.get(entity_id)
        return item.transitive_supertype_ids if item is not None else ()

    def _visible_declaration(
        self,
        schema_name: str,
        name: str,
        kind: Literal["type", "entity"] | None = None,
    ) -> _NamedDeclaration | None:
        candidates = self.visible.get(schema_name.casefold(), {}).get(
            name.casefold(), []
        )
        if kind is not None:
            candidates = [item for item in candidates if item.kind == kind]
        return candidates[0] if len(candidates) == 1 else None

    @staticmethod
    def _literal_bound(source: str | None) -> int | None | type(Ellipsis):
        if source is None or source.strip() == "?":
            return None
        source = source.strip()
        if source.isdigit():
            return int(source)
        return ...

    @staticmethod
    def _value_key(value: Part21Value) -> tuple[object, ...]:
        return (
            value.kind,
            value.value,
            tuple(_Validator._value_key(child) for child in value.children),
        )

    @staticmethod
    def _type_label(type_ref: ExpressTypeReference) -> str:
        if type_ref.kind in {"simple", "named"}:
            return str(type_ref.name)
        if type_ref.kind == "aggregate":
            return f"{type_ref.aggregate_kind} OF {type_ref.element_type and _Validator._type_label(type_ref.element_type)}"
        if type_ref.kind == "select":
            return "SELECT(" + ",".join(type_ref.members) + ")"
        if type_ref.kind == "enumeration":
            return "ENUMERATION(" + ",".join(type_ref.members) + ")"
        return type_ref.kind

    def _diagnose(
        self,
        severity: Literal["invalid", "deferred"],
        reason_code: str,
        stage: str,
        section_index: int | None,
        entity_id: int | None,
        record_index: int | None,
        parameter_index: int | None,
        source_line: int | None,
        detail: str,
    ) -> None:
        diagnostic = STEPExpressDiagnostic(
            severity,
            reason_code,
            stage,
            section_index,
            entity_id,
            record_index,
            parameter_index,
            source_line,
            detail,
        )
        if diagnostic not in self.diagnostics:
            self.diagnostics.append(diagnostic)


def _empty_result(
    decision: ValidationDecision,
    reason_code: str,
    *,
    part21_syntax: ValidationStatus,
    express_syntax: ValidationStatus,
    express_resolution: ValidationStatus,
) -> STEPExpressValidationResult:
    return STEPExpressValidationResult(
        decision,
        reason_code,
        part21_syntax,
        express_syntax,
        express_resolution,
        "not_reached",
        "not_reached",
        0,
        0,
        0,
        0,
        0,
        0,
        (),
        (),
        (),
        (),
    )


def inspect_step_express_validation(
    step_bytes: bytes,
    express_bytes: bytes,
    *,
    step_limits: STEPParseLimits = DEFAULT_STEP_PARSE_LIMITS,
    express_parse_limits: ExpressParseLimits = DEFAULT_EXPRESS_PARSE_LIMITS,
    express_resolution_limits: ExpressResolutionLimits = DEFAULT_EXPRESS_RESOLUTION_LIMITS,
    validation_limits: STEPExpressValidationLimits = DEFAULT_STEP_EXPRESS_VALIDATION_LIMITS,
) -> STEPExpressValidationResult:
    """Parse and validate one Part 21 exchange against one EXPRESS document."""
    if not isinstance(step_bytes, bytes):
        raise TypeError("step_bytes must be bytes")
    if not isinstance(express_bytes, bytes):
        raise TypeError("express_bytes must be bytes")
    if not isinstance(step_limits, STEPParseLimits):
        raise TypeError("step_limits must be STEPParseLimits")
    if not isinstance(express_parse_limits, ExpressParseLimits):
        raise TypeError("express_parse_limits must be ExpressParseLimits")
    if not isinstance(express_resolution_limits, ExpressResolutionLimits):
        raise TypeError("express_resolution_limits must be ExpressResolutionLimits")
    if not isinstance(validation_limits, STEPExpressValidationLimits):
        raise TypeError("validation_limits must be STEPExpressValidationLimits")
    try:
        part21 = parse_part21_document(step_bytes, limits=step_limits)
    except Part21ParseError as error:
        return _empty_result(
            error.decision,
            error.reason_code,
            part21_syntax="invalid" if error.decision == "reject" else "deferred",
            express_syntax="not_reached",
            express_resolution="not_reached",
        )
    try:
        express = parse_express_document(express_bytes, limits=express_parse_limits)
    except ExpressParseError as error:
        return _empty_result(
            error.decision,
            error.reason_code,
            part21_syntax="valid",
            express_syntax="invalid" if error.decision == "reject" else "deferred",
            express_resolution="not_reached",
        )
    try:
        resolved = resolve_express_document(
            express, limits=express_resolution_limits
        )
    except ExpressResolutionLimitError as error:
        return _empty_result(
            "quarantine",
            error.reason_code,
            part21_syntax="valid",
            express_syntax="valid",
            express_resolution="deferred",
        )
    if resolved.decision != "accept":
        return _empty_result(
            "reject",
            "express_resolution_failed",
            part21_syntax="valid",
            express_syntax="valid",
            express_resolution="invalid",
        )
    try:
        return _Validator(part21, express, resolved, validation_limits).validate()
    except STEPExpressValidationLimitError as error:
        return _empty_result(
            "quarantine",
            error.reason_code,
            part21_syntax="valid",
            express_syntax="valid",
            express_resolution="valid",
        )
