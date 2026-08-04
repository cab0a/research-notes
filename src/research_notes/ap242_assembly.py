"""Bounded AP242 assembly occurrence, placement, and length-unit evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from research_notes.ap242_paths import AP242_SCHEMA_IDENTIFIER
from research_notes.step_graph import (
    DEFAULT_STEP_GRAPH_LIMITS,
    STEPGraph,
    STEPGraphEdge,
    STEPGraphLimits,
    build_step_graph,
)
from research_notes.step_part21 import (
    DEFAULT_STEP_PARSE_LIMITS,
    STEPParseLimits,
    Part21Document,
    Part21Entity,
    Part21Record,
    Part21SourceSpan,
    Part21Value,
    parse_part21_document,
)


AssemblyDecision = Literal["accept", "quarantine", "reject"]


@dataclass(frozen=True)
class AssemblyLimits:
    """Explicit semantic and traversal budgets for one assembly evaluation."""

    max_occurrences: int = 20_000
    max_paths: int = 50_000
    max_relations: int = 500_000
    max_depth: int = 64
    max_unit_hops: int = 16

    def __post_init__(self) -> None:
        for field_name, value in vars(self).items():
            if not isinstance(value, int) or isinstance(value, bool):
                raise TypeError(f"{field_name} must be an integer")
            if value <= 0:
                raise ValueError(f"{field_name} must be positive")


DEFAULT_ASSEMBLY_LIMITS = AssemblyLimits()


class AssemblyLimitError(RuntimeError):
    """A stable quarantine outcome for an assembly work budget."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


@dataclass(frozen=True)
class AssemblyDiagnostic:
    """One invalid or deferred assembly interpretation."""

    severity: Literal["invalid", "deferred"]
    reason_code: str
    role: str
    entity_id: int | None
    source_line: int | None
    detail: str


@dataclass(frozen=True)
class AssemblyRelation:
    """One assembly role joined to one physical reference occurrence."""

    occurrence_index: int
    role: str
    source_entity_id: int
    target_entity_id: int
    source_edge_index: int
    parameter_path: tuple[int, ...]
    source_span: Part21SourceSpan


@dataclass(frozen=True)
class AssemblyUnitObservation:
    """One representation length unit evaluated in an occurrence context."""

    occurrence_index: int
    side: Literal["child", "parent"]
    representation_entity_id: int
    unit_entity_id: int
    unit_name: str
    unit_form: Literal["si", "conversion_based"]
    scale_to_millimetre: float
    conversion_hops: int
    source_span: Part21SourceSpan


@dataclass(frozen=True)
class AssemblyOccurrence:
    """One reusable child definition placed in one immediate parent assembly."""

    occurrence_index: int
    entity_id: int
    identifier: str
    name: str
    reference_designator: str
    parent_product_definition_entity_id: int
    child_product_definition_entity_id: int
    parent_representation_entity_id: int
    child_representation_entity_id: int
    product_definition_shape_entity_id: int
    context_dependent_shape_representation_entity_id: int
    representation_relationship_entity_id: int
    transformation_entity_id: int
    source_placement_entity_id: int
    target_placement_entity_id: int
    child_unit_name: str
    child_scale_to_millimetre: float
    parent_unit_name: str
    parent_scale_to_millimetre: float
    local_matrix: tuple[float, ...]
    local_translation_mm: tuple[float, float, float]
    local_rotation: tuple[float, ...]
    rotation_determinant: float
    source_span: Part21SourceSpan


@dataclass(frozen=True)
class AssemblyPath:
    """One root-relative occurrence path with its composed rigid transform."""

    path_index: int
    root_product_definition_entity_id: int
    leaf_product_definition_entity_id: int
    depth: int
    occurrence_indices: tuple[int, ...]
    occurrence_entity_ids: tuple[int, ...]
    reference_designators: tuple[str, ...]
    global_matrix: tuple[float, ...]
    global_translation_mm: tuple[float, float, float]
    global_rotation: tuple[float, ...]
    rotation_determinant: float


@dataclass(frozen=True)
class AssemblyResult:
    """Controlled assembly evidence with source provenance and physical graph."""

    decision: AssemblyDecision
    reason_code: str
    schema_identifier: str | None
    occurrence_count: int
    path_count: int
    relation_count: int
    unit_observation_count: int
    distinct_definition_count: int
    reused_definition_count: int
    maximum_depth: int
    occurrences: tuple[AssemblyOccurrence, ...]
    paths: tuple[AssemblyPath, ...]
    relations: tuple[AssemblyRelation, ...]
    units: tuple[AssemblyUnitObservation, ...]
    diagnostics: tuple[AssemblyDiagnostic, ...]
    graph: STEPGraph


class _AssemblyError(RuntimeError):
    def __init__(
        self,
        severity: Literal["invalid", "deferred"],
        reason_code: str,
        role: str,
        entity: Part21Entity | None,
        detail: str,
    ) -> None:
        super().__init__(detail)
        self.severity = severity
        self.reason_code = reason_code
        self.role = role
        self.entity = entity
        self.detail = detail


@dataclass(frozen=True)
class _Reference:
    selected: Part21Entity
    edge: STEPGraphEdge


@dataclass(frozen=True)
class _DecodedUnit:
    entity: Part21Entity
    name: str
    form: Literal["si", "conversion_based"]
    scale_to_millimetre: float
    hops: int
    relations: tuple[tuple[str, _Reference], ...]


@dataclass(frozen=True)
class _RepresentationBinding:
    representation: Part21Entity
    relations: tuple[tuple[str, _Reference], ...]


_REPRESENTATION_TYPES = {
    "SHAPE_REPRESENTATION",
    "ADVANCED_BREP_SHAPE_REPRESENTATION",
    "FACETED_BREP_SHAPE_REPRESENTATION",
    "TESSELLATED_SHAPE_REPRESENTATION",
}

_SI_PREFIX_TO_MILLIMETRE = {
    None: 1_000.0,
    "EXA": 1.0e21,
    "PETA": 1.0e18,
    "TERA": 1.0e15,
    "GIGA": 1.0e12,
    "MEGA": 1.0e9,
    "KILO": 1.0e6,
    "HECTO": 1.0e5,
    "DECA": 1.0e4,
    "DECI": 1.0e2,
    "CENTI": 1.0e1,
    "MILLI": 1.0,
    "MICRO": 1.0e-3,
    "NANO": 1.0e-6,
    "PICO": 1.0e-9,
    "FEMTO": 1.0e-12,
    "ATTO": 1.0e-15,
}


def evaluate_ap242_assembly(
    source_bytes: bytes,
    *,
    parse_limits: STEPParseLimits = DEFAULT_STEP_PARSE_LIMITS,
    graph_limits: STEPGraphLimits = DEFAULT_STEP_GRAPH_LIMITS,
    assembly_limits: AssemblyLimits = DEFAULT_ASSEMBLY_LIMITS,
) -> AssemblyResult:
    """Evaluate a controlled AP242 assembly subset in canonical millimetres."""
    if not isinstance(source_bytes, bytes):
        raise TypeError("source_bytes must be bytes")
    if not isinstance(parse_limits, STEPParseLimits):
        raise TypeError("parse_limits must be STEPParseLimits")
    if not isinstance(graph_limits, STEPGraphLimits):
        raise TypeError("graph_limits must be STEPGraphLimits")
    if not isinstance(assembly_limits, AssemblyLimits):
        raise TypeError("assembly_limits must be AssemblyLimits")
    document = parse_part21_document(source_bytes, limits=parse_limits)
    graph = build_step_graph(
        source_bytes, parse_limits=parse_limits, graph_limits=graph_limits
    )
    return _AssemblyResolver(document, graph, assembly_limits).resolve()


class _AssemblyResolver:
    def __init__(
        self, document: Part21Document, graph: STEPGraph, limits: AssemblyLimits
    ) -> None:
        self.document = document
        self.graph = graph
        self.limits = limits
        self.entities = {entity.entity_id: entity for entity in document.entities}
        self.occurrences: list[AssemblyOccurrence] = []
        self.paths: list[AssemblyPath] = []
        self.relations: list[AssemblyRelation] = []
        self.units: list[AssemblyUnitObservation] = []
        self.diagnostics: list[AssemblyDiagnostic] = []
        self._representation_cache: dict[int, _RepresentationBinding] = {}

    def resolve(self) -> AssemblyResult:
        schema = self._schema_identifier()
        occurrence_entities = self._entities_of_type(
            "NEXT_ASSEMBLY_USAGE_OCCURRENCE"
        )
        if len(occurrence_entities) > self.limits.max_occurrences:
            raise AssemblyLimitError(
                "assembly_occurrence_limit",
                "assembly occurrences exceed the configured work budget",
            )
        if schema != AP242_SCHEMA_IDENTIFIER:
            self._diagnose(
                _AssemblyError(
                    "deferred",
                    "unsupported_application_schema",
                    "file_schema",
                    None,
                    "the controlled evaluator accepts only the declared AP242 MIM schema",
                )
            )
            return self._result(schema)
        if not occurrence_entities:
            self._diagnose(
                _AssemblyError(
                    "deferred",
                    "assembly_occurrence_not_found",
                    "next_assembly_usage_occurrence",
                    None,
                    "no encoded immediate assembly occurrence is available",
                )
            )
            return self._result(schema)
        for entity in occurrence_entities:
            try:
                self._resolve_occurrence(entity)
            except _AssemblyError as error:
                self._diagnose(error)
        try:
            self._validate_designators()
            self._build_paths()
        except _AssemblyError as error:
            self._diagnose(error)
        return self._result(schema)

    def _resolve_occurrence(self, occurrence: Part21Entity) -> None:
        index = len(self.occurrences)
        record_index, record = self._record(
            occurrence, "NEXT_ASSEMBLY_USAGE_OCCURRENCE", exact_arguments=6
        )
        identifier = self._required_string(
            occurrence, record.arguments[0], "assembly_occurrence.id"
        )
        name = self._optional_string(
            occurrence, record.arguments[1], "assembly_occurrence.name"
        )
        reference_designator = self._required_string(
            occurrence,
            record.arguments[5],
            "assembly_occurrence.reference_designator",
        )
        parent = self._required_reference(
            occurrence,
            record_index,
            record.arguments[3],
            (3,),
            "assembly_occurrence.parent_definition",
            {"PRODUCT_DEFINITION"},
        )
        child = self._required_reference(
            occurrence,
            record_index,
            record.arguments[4],
            (4,),
            "assembly_occurrence.child_definition",
            {"PRODUCT_DEFINITION"},
        )
        if parent.selected.entity_id == child.selected.entity_id:
            raise _AssemblyError(
                "invalid",
                "self_referential_assembly_occurrence",
                "next_assembly_usage_occurrence",
                occurrence,
                "an immediate occurrence cannot use its parent definition as its child",
            )
        parent_binding = self._representation_for_definition(parent.selected)
        child_binding = self._representation_for_definition(child.selected)

        shapes = self._referrers(
            occurrence.entity_id,
            "PRODUCT_DEFINITION_SHAPE",
            record_index=0,
            parameter_path=(2,),
        )
        if len(shapes) != 1:
            severity: Literal["invalid", "deferred"] = (
                "deferred" if not shapes else "invalid"
            )
            raise _AssemblyError(
                severity,
                (
                    "occurrence_shape_not_found"
                    if not shapes
                    else "duplicate_occurrence_shape"
                ),
                "product_definition_shape.definition",
                occurrence,
                "the occurrence requires exactly one product-definition shape association",
            )
        shape = shapes[0]
        shape_record_index, shape_record = self._record(
            shape.selected, "PRODUCT_DEFINITION_SHAPE", exact_arguments=3
        )
        shape_definition = self._required_reference(
            shape.selected,
            shape_record_index,
            shape_record.arguments[2],
            (2,),
            "occurrence_shape.definition",
            {"NEXT_ASSEMBLY_USAGE_OCCURRENCE"},
        )
        if shape_definition.selected.entity_id != occurrence.entity_id:
            raise _AssemblyError(
                "invalid",
                "occurrence_shape_target_mismatch",
                "product_definition_shape.definition",
                shape.selected,
                "the occurrence shape targets another usage occurrence",
            )
        associations = self._referrers(
            shape.selected.entity_id,
            "CONTEXT_DEPENDENT_SHAPE_REPRESENTATION",
            record_index=0,
            parameter_path=(1,),
        )
        if len(associations) != 1:
            severity = "deferred" if not associations else "invalid"
            raise _AssemblyError(
                severity,
                (
                    "context_dependent_shape_representation_not_found"
                    if not associations
                    else "duplicate_context_dependent_shape_representation"
                ),
                "context_dependent_shape_representation.represented_product_relation",
                shape.selected,
                "the occurrence requires exactly one context-dependent shape association",
            )
        association = associations[0]
        association_record_index, association_record = self._record(
            association.selected,
            "CONTEXT_DEPENDENT_SHAPE_REPRESENTATION",
            exact_arguments=2,
        )
        relationship = self._required_reference(
            association.selected,
            association_record_index,
            association_record.arguments[0],
            (0,),
            "context_dependent_shape_representation.representation_relation",
            {"REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION"},
        )
        represented_product_relation = self._required_reference(
            association.selected,
            association_record_index,
            association_record.arguments[1],
            (1,),
            "context_dependent_shape_representation.represented_product_relation",
            {"PRODUCT_DEFINITION_SHAPE"},
        )
        if represented_product_relation.selected.entity_id != shape.selected.entity_id:
            raise _AssemblyError(
                "invalid",
                "represented_product_relation_mismatch",
                "context_dependent_shape_representation.represented_product_relation",
                association.selected,
                "the context-dependent association targets another occurrence shape",
            )

        relationship_record_index, relationship_record = self._record(
            relationship.selected, "REPRESENTATION_RELATIONSHIP", exact_arguments=4
        )
        self._record(
            relationship.selected,
            "SHAPE_REPRESENTATION_RELATIONSHIP",
            exact_arguments=0,
        )
        transformation_record_index, transformation_record = self._record(
            relationship.selected,
            "REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION",
            exact_arguments=1,
        )
        child_representation = self._required_reference(
            relationship.selected,
            relationship_record_index,
            relationship_record.arguments[2],
            (2,),
            "representation_relationship.child_representation",
            _REPRESENTATION_TYPES,
        )
        parent_representation = self._required_reference(
            relationship.selected,
            relationship_record_index,
            relationship_record.arguments[3],
            (3,),
            "representation_relationship.parent_representation",
            _REPRESENTATION_TYPES,
        )
        if (
            child_representation.selected.entity_id
            != child_binding.representation.entity_id
            or parent_representation.selected.entity_id
            != parent_binding.representation.entity_id
        ):
            raise _AssemblyError(
                "invalid",
                "assembly_representation_order_mismatch",
                "representation_relationship",
                relationship.selected,
                "rep_1 must be the child representation and rep_2 the parent representation",
            )
        operator = self._required_reference(
            relationship.selected,
            transformation_record_index,
            transformation_record.arguments[0],
            (0,),
            "representation_relationship.transformation_operator",
            {"ITEM_DEFINED_TRANSFORMATION"},
            unsupported_is_deferred=True,
        )
        operator_record_index, operator_record = self._record(
            operator.selected, "ITEM_DEFINED_TRANSFORMATION", exact_arguments=4
        )
        source_placement = self._required_reference(
            operator.selected,
            operator_record_index,
            operator_record.arguments[2],
            (2,),
            "item_defined_transformation.transform_item_1",
            {"AXIS2_PLACEMENT_3D"},
            unsupported_is_deferred=True,
        )
        target_placement = self._required_reference(
            operator.selected,
            operator_record_index,
            operator_record.arguments[3],
            (3,),
            "item_defined_transformation.transform_item_2",
            {"AXIS2_PLACEMENT_3D"},
            unsupported_is_deferred=True,
        )

        child_membership = self._representation_item_membership(
            child_representation.selected,
            source_placement.selected.entity_id,
            "child_representation.items",
        )
        parent_membership = self._representation_item_membership(
            parent_representation.selected,
            target_placement.selected.entity_id,
            "parent_representation.items",
        )
        child_unit, child_unit_relations, child_context_id = (
            self._length_unit_for_representation(
                child_representation.selected, "child"
            )
        )
        parent_unit, parent_unit_relations, parent_context_id = (
            self._length_unit_for_representation(
                parent_representation.selected, "parent"
            )
        )
        if child_context_id == parent_context_id:
            raise _AssemblyError(
                "invalid",
                "representation_contexts_not_distinct",
                "representation_relationship",
                relationship.selected,
                "the child and parent representations require distinct contexts",
            )
        source_frame, source_frame_relations = self._decode_placement(
            source_placement.selected,
            child_unit.scale_to_millimetre,
            "source_placement",
        )
        target_frame, target_frame_relations = self._decode_placement(
            target_placement.selected,
            parent_unit.scale_to_millimetre,
            "target_placement",
        )
        local = target_frame @ self._rigid_inverse(source_frame)
        rotation = local[:3, :3]
        determinant = float(np.linalg.det(rotation))
        if not np.isfinite(local).all() or not np.isclose(
            determinant, 1.0, atol=1.0e-9
        ):
            raise _AssemblyError(
                "invalid",
                "invalid_rigid_transform",
                "item_defined_transformation",
                operator.selected,
                "the evaluated placement relationship is not a finite proper rigid transform",
            )

        occurrence_row = AssemblyOccurrence(
            index,
            occurrence.entity_id,
            identifier,
            name,
            reference_designator,
            parent.selected.entity_id,
            child.selected.entity_id,
            parent_representation.selected.entity_id,
            child_representation.selected.entity_id,
            shape.selected.entity_id,
            association.selected.entity_id,
            relationship.selected.entity_id,
            operator.selected.entity_id,
            source_placement.selected.entity_id,
            target_placement.selected.entity_id,
            child_unit.name,
            child_unit.scale_to_millimetre,
            parent_unit.name,
            parent_unit.scale_to_millimetre,
            self._flatten_matrix(local),
            self._translation(local),
            tuple(float(value) for value in rotation.reshape(-1)),
            determinant,
            occurrence.span,
        )
        relation_refs: tuple[tuple[str, _Reference], ...] = (
            ("assembly_occurrence.parent_definition", parent),
            ("assembly_occurrence.child_definition", child),
            ("occurrence_shape.definition", shape),
            (
                "context_dependent_shape_representation.represented_product_relation",
                association,
            ),
            (
                "context_dependent_shape_representation.representation_relation",
                relationship,
            ),
            ("representation_relationship.child_representation", child_representation),
            ("representation_relationship.parent_representation", parent_representation),
            ("representation_relationship.transformation_operator", operator),
            ("item_defined_transformation.transform_item_1", source_placement),
            ("item_defined_transformation.transform_item_2", target_placement),
            ("child_representation.items", child_membership),
            ("parent_representation.items", parent_membership),
            *child_binding.relations,
            *parent_binding.relations,
            *child_unit_relations,
            *parent_unit_relations,
            *source_frame_relations,
            *target_frame_relations,
        )
        self.occurrences.append(occurrence_row)
        for role, reference in relation_refs:
            self._append_relation(index, role, reference)
        self.units.extend(
            (
                AssemblyUnitObservation(
                    index,
                    "child",
                    child_representation.selected.entity_id,
                    child_unit.entity.entity_id,
                    child_unit.name,
                    child_unit.form,
                    child_unit.scale_to_millimetre,
                    child_unit.hops,
                    child_unit.entity.span,
                ),
                AssemblyUnitObservation(
                    index,
                    "parent",
                    parent_representation.selected.entity_id,
                    parent_unit.entity.entity_id,
                    parent_unit.name,
                    parent_unit.form,
                    parent_unit.scale_to_millimetre,
                    parent_unit.hops,
                    parent_unit.entity.span,
                ),
            )
        )

    def _representation_for_definition(
        self, definition: Part21Entity
    ) -> _RepresentationBinding:
        cached = self._representation_cache.get(definition.entity_id)
        if cached is not None:
            return cached
        shapes = self._referrers(
            definition.entity_id,
            "PRODUCT_DEFINITION_SHAPE",
            record_index=0,
            parameter_path=(2,),
        )
        if len(shapes) != 1:
            severity: Literal["invalid", "deferred"] = (
                "deferred" if not shapes else "invalid"
            )
            raise _AssemblyError(
                severity,
                (
                    "product_definition_shape_not_found"
                    if not shapes
                    else "duplicate_product_definition_shape"
                ),
                "product_definition_shape.definition",
                definition,
                "each controlled assembly definition requires one shape definition",
            )
        shape = shapes[0]
        shape_record_index, shape_record = self._record(
            shape.selected, "PRODUCT_DEFINITION_SHAPE", exact_arguments=3
        )
        shape_definition = self._required_reference(
            shape.selected,
            shape_record_index,
            shape_record.arguments[2],
            (2,),
            "product_definition_shape.definition",
            {"PRODUCT_DEFINITION"},
        )
        if shape_definition.selected.entity_id != definition.entity_id:
            raise _AssemblyError(
                "invalid",
                "product_definition_shape_target_mismatch",
                "product_definition_shape.definition",
                shape.selected,
                "the shape definition targets another product definition",
            )
        associations = self._referrers(
            shape.selected.entity_id,
            "SHAPE_DEFINITION_REPRESENTATION",
            record_index=0,
            parameter_path=(0,),
        )
        if len(associations) != 1:
            severity = "deferred" if not associations else "invalid"
            raise _AssemblyError(
                severity,
                (
                    "shape_representation_not_found"
                    if not associations
                    else "duplicate_shape_representation"
                ),
                "shape_definition_representation.definition",
                shape.selected,
                "each controlled assembly definition requires one shape representation",
            )
        association = associations[0]
        association_record_index, association_record = self._record(
            association.selected,
            "SHAPE_DEFINITION_REPRESENTATION",
            exact_arguments=2,
        )
        associated_shape = self._required_reference(
            association.selected,
            association_record_index,
            association_record.arguments[0],
            (0,),
            "shape_definition_representation.definition",
            {"PRODUCT_DEFINITION_SHAPE"},
        )
        if associated_shape.selected.entity_id != shape.selected.entity_id:
            raise _AssemblyError(
                "invalid",
                "shape_definition_representation_target_mismatch",
                "shape_definition_representation.definition",
                association.selected,
                "the representation association targets another shape definition",
            )
        representation = self._required_reference(
            association.selected,
            association_record_index,
            association_record.arguments[1],
            (1,),
            "shape_definition_representation.used_representation",
            _REPRESENTATION_TYPES,
        )
        binding = _RepresentationBinding(
            representation.selected,
            (
                ("product_definition_shape.definition", shape_definition),
                ("shape_definition_representation.definition", associated_shape),
                (
                    "shape_definition_representation.used_representation",
                    representation,
                ),
            ),
        )
        self._representation_cache[definition.entity_id] = binding
        return binding

    def _representation_item_membership(
        self, representation: Part21Entity, item_id: int, role: str
    ) -> _Reference:
        record_index, record = self._representation_record(representation)
        references = self._reference_list(
            representation,
            record_index,
            record.arguments[1],
            (1,),
            role,
        )
        matches = [item for item in references if item.selected.entity_id == item_id]
        if len(matches) != 1:
            raise _AssemblyError(
                "invalid",
                "transformation_item_not_in_representation",
                role,
                representation,
                "the transformation placement must occur once in the related representation",
            )
        return matches[0]

    def _length_unit_for_representation(
        self, representation: Part21Entity, side: str
    ) -> tuple[_DecodedUnit, tuple[tuple[str, _Reference], ...], int]:
        record_index, record = self._representation_record(representation)
        context = self._required_reference(
            representation,
            record_index,
            record.arguments[2],
            (2,),
            f"{side}_representation.context_of_items",
            {"REPRESENTATION_CONTEXT"},
        )
        try:
            unit_record_index, unit_record = self._record(
                context.selected,
                "GLOBAL_UNIT_ASSIGNED_CONTEXT",
                exact_arguments=1,
            )
        except _AssemblyError as error:
            raise _AssemblyError(
                "deferred",
                "global_units_not_available",
                f"{side}_representation.global_units",
                context.selected,
                "the controlled assembly evaluator requires an explicit length unit",
            ) from error
        unit_refs = self._reference_list(
            context.selected,
            unit_record_index,
            unit_record.arguments[0],
            (0,),
            f"{side}_representation.units",
        )
        length_refs = [
            reference
            for reference in unit_refs
            if self._has_type(reference.selected, "LENGTH_UNIT")
        ]
        if len(length_refs) != 1:
            raise _AssemblyError(
                "invalid" if length_refs else "deferred",
                (
                    "ambiguous_length_unit"
                    if length_refs
                    else "length_unit_not_available"
                ),
                f"{side}_representation.units",
                context.selected,
                "the representation context requires exactly one controlled length unit",
            )
        decoded = self._decode_length_unit(
            length_refs[0].selected, (), self.limits.max_unit_hops
        )
        relations = (
            (f"{side}_representation.context_of_items", context),
            (f"{side}_representation.length_unit", length_refs[0]),
            *decoded.relations,
        )
        return decoded, relations, context.selected.entity_id

    def _decode_length_unit(
        self,
        unit: Part21Entity,
        stack: tuple[int, ...],
        remaining_hops: int,
    ) -> _DecodedUnit:
        if unit.entity_id in stack:
            raise _AssemblyError(
                "invalid",
                "unit_conversion_cycle",
                "conversion_based_unit",
                unit,
                "conversion-based length units must not form a cycle",
            )
        if remaining_hops <= 0:
            raise AssemblyLimitError(
                "unit_conversion_hop_limit",
                "unit conversion chain exceeds the configured hop budget",
            )
        if not self._has_type(unit, "LENGTH_UNIT"):
            raise _AssemblyError(
                "invalid",
                "length_unit_kind_required",
                "length_unit",
                unit,
                "the selected context unit is not encoded as a length unit",
            )
        si_records = [record for record in unit.records if record.type_name == "SI_UNIT"]
        conversion_records = [
            (index, record)
            for index, record in enumerate(unit.records)
            if record.type_name == "CONVERSION_BASED_UNIT"
        ]
        if len(si_records) == 1 and not conversion_records:
            record = si_records[0]
            if len(record.arguments) != 2:
                raise _AssemblyError(
                    "invalid",
                    "semantic_parameter_count_mismatch",
                    "si_unit",
                    unit,
                    "SI_UNIT requires two encoded parameters",
                )
            prefix_value, name_value = record.arguments
            if name_value.kind != "enumeration" or name_value.value != "METRE":
                raise _AssemblyError(
                    "deferred",
                    "unsupported_si_length_unit",
                    "si_unit.name",
                    unit,
                    "only SI metre length units are evaluated",
                )
            if prefix_value.kind == "omitted":
                prefix: str | None = None
            elif prefix_value.kind == "enumeration":
                prefix = str(prefix_value.value)
            else:
                raise _AssemblyError(
                    "invalid",
                    "invalid_si_unit_prefix",
                    "si_unit.prefix",
                    unit,
                    "an SI prefix must be an enumeration or omitted marker",
                )
            scale = _SI_PREFIX_TO_MILLIMETRE.get(prefix)
            if scale is None:
                raise _AssemblyError(
                    "deferred",
                    "unsupported_si_prefix",
                    "si_unit.prefix",
                    unit,
                    "the SI prefix is outside the controlled conversion table",
                )
            name = "metre" if prefix is None else f"{prefix.casefold()}metre"
            return _DecodedUnit(unit, name, "si", scale, 0, ())
        if len(conversion_records) == 1 and not si_records:
            record_index, record = conversion_records[0]
            if len(record.arguments) != 2:
                raise _AssemblyError(
                    "invalid",
                    "semantic_parameter_count_mismatch",
                    "conversion_based_unit",
                    unit,
                    "CONVERSION_BASED_UNIT requires a name and conversion factor",
                )
            name = self._required_string(unit, record.arguments[0], "unit.name")
            factor = self._required_reference(
                unit,
                record_index,
                record.arguments[1],
                (1,),
                "conversion_based_unit.conversion_factor",
                {"LENGTH_MEASURE_WITH_UNIT"},
            )
            factor_record_index, factor_record = self._record(
                factor.selected, "LENGTH_MEASURE_WITH_UNIT", exact_arguments=2
            )
            value = self._typed_number(
                factor.selected,
                factor_record.arguments[0],
                "LENGTH_MEASURE",
                "length_measure_with_unit.value_component",
            )
            if not np.isfinite(value) or value <= 0.0:
                raise _AssemblyError(
                    "invalid",
                    "invalid_unit_conversion_factor",
                    "length_measure_with_unit.value_component",
                    factor.selected,
                    "a length conversion factor must be finite and positive",
                )
            base = self._required_reference(
                factor.selected,
                factor_record_index,
                factor_record.arguments[1],
                (1,),
                "length_measure_with_unit.unit_component",
                {"LENGTH_UNIT"},
            )
            decoded_base = self._decode_length_unit(
                base.selected, (*stack, unit.entity_id), remaining_hops - 1
            )
            return _DecodedUnit(
                unit,
                name,
                "conversion_based",
                value * decoded_base.scale_to_millimetre,
                decoded_base.hops + 1,
                (
                    ("conversion_based_unit.conversion_factor", factor),
                    ("length_measure_with_unit.unit_component", base),
                    *decoded_base.relations,
                ),
            )
        raise _AssemblyError(
            "deferred",
            "unsupported_length_unit_form",
            "length_unit",
            unit,
            "the length unit is neither one SI unit nor one conversion-based unit",
        )

    def _decode_placement(
        self, placement: Part21Entity, scale: float, role_prefix: str
    ) -> tuple[np.ndarray, tuple[tuple[str, _Reference], ...]]:
        record_index, record = self._record(
            placement, "AXIS2_PLACEMENT_3D", exact_arguments=4
        )
        location = self._required_reference(
            placement,
            record_index,
            record.arguments[1],
            (1,),
            f"{role_prefix}.location",
            {"CARTESIAN_POINT"},
        )
        axis = self._required_reference(
            placement,
            record_index,
            record.arguments[2],
            (2,),
            f"{role_prefix}.axis",
            {"DIRECTION"},
            unsupported_is_deferred=True,
        )
        reference_direction = self._required_reference(
            placement,
            record_index,
            record.arguments[3],
            (3,),
            f"{role_prefix}.reference_direction",
            {"DIRECTION"},
            unsupported_is_deferred=True,
        )
        origin = self._coordinates(location.selected, "CARTESIAN_POINT") * scale
        z_axis = self._coordinates(axis.selected, "DIRECTION")
        x_axis = self._coordinates(reference_direction.selected, "DIRECTION")
        z_norm = float(np.linalg.norm(z_axis))
        x_norm = float(np.linalg.norm(x_axis))
        if z_norm <= 1.0e-12 or x_norm <= 1.0e-12:
            raise _AssemblyError(
                "invalid",
                "zero_length_placement_direction",
                role_prefix,
                placement,
                "placement directions must have non-zero magnitude",
            )
        z_axis = z_axis / z_norm
        x_axis = x_axis / x_norm
        if not np.isclose(float(np.dot(z_axis, x_axis)), 0.0, atol=1.0e-9):
            raise _AssemblyError(
                "invalid",
                "nonorthogonal_placement_axes",
                role_prefix,
                placement,
                "the controlled placement requires orthogonal axis and reference direction",
            )
        y_axis = np.cross(z_axis, x_axis)
        y_axis = y_axis / np.linalg.norm(y_axis)
        x_axis = np.cross(y_axis, z_axis)
        frame = np.eye(4, dtype=np.float64)
        frame[:3, :3] = np.column_stack((x_axis, y_axis, z_axis))
        frame[:3, 3] = origin
        return frame, (
            (f"{role_prefix}.location", location),
            (f"{role_prefix}.axis", axis),
            (f"{role_prefix}.reference_direction", reference_direction),
        )

    def _coordinates(self, entity: Part21Entity, type_name: str) -> np.ndarray:
        _, record = self._record(entity, type_name, exact_arguments=2)
        value = record.arguments[1]
        if value.kind != "list" or len(value.children) != 3:
            raise _AssemblyError(
                "invalid",
                "three_coordinates_required",
                type_name.casefold(),
                entity,
                "the controlled three-dimensional placement requires three coordinates",
            )
        coordinates: list[float] = []
        for child in value.children:
            if child.kind not in {"integer", "real"}:
                raise _AssemblyError(
                    "invalid",
                    "numeric_coordinate_required",
                    type_name.casefold(),
                    entity,
                    "each coordinate must be an encoded integer or real",
                )
            coordinates.append(float(child.value))
        result = np.asarray(coordinates, dtype=np.float64)
        if not np.isfinite(result).all():
            raise _AssemblyError(
                "invalid",
                "finite_coordinate_required",
                type_name.casefold(),
                entity,
                "placement coordinates must be finite",
            )
        return result

    def _validate_designators(self) -> None:
        seen: dict[tuple[int, str], AssemblyOccurrence] = {}
        for occurrence in self.occurrences:
            key = (
                occurrence.parent_product_definition_entity_id,
                occurrence.reference_designator.casefold(),
            )
            previous = seen.get(key)
            if previous is not None:
                entity = self.entities[occurrence.entity_id]
                raise _AssemblyError(
                    "invalid",
                    "duplicate_reference_designator",
                    "assembly_occurrence.reference_designator",
                    entity,
                    "reference designators must be unique within one parent definition",
                )
            seen[key] = occurrence

    def _build_paths(self) -> None:
        if not self.occurrences:
            return
        children = {
            occurrence.child_product_definition_entity_id
            for occurrence in self.occurrences
        }
        parents = {
            occurrence.parent_product_definition_entity_id
            for occurrence in self.occurrences
        }
        roots = tuple(sorted(parents - children))
        if not roots:
            entity = self.entities[self.occurrences[0].entity_id]
            raise _AssemblyError(
                "invalid",
                "assembly_cycle",
                "assembly_structure",
                entity,
                "the assembly occurrence graph has no acyclic root",
            )
        outbound: dict[int, list[AssemblyOccurrence]] = {}
        for occurrence in self.occurrences:
            outbound.setdefault(
                occurrence.parent_product_definition_entity_id, []
            ).append(occurrence)
        for values in outbound.values():
            values.sort(key=lambda item: item.occurrence_index)
        for root in roots:
            self._walk_paths(root, root, np.eye(4), (), (), outbound)
        visited_occurrences = {
            occurrence_index
            for path in self.paths
            for occurrence_index in path.occurrence_indices
        }
        if len(visited_occurrences) != len(self.occurrences):
            missing = next(
                occurrence
                for occurrence in self.occurrences
                if occurrence.occurrence_index not in visited_occurrences
            )
            raise _AssemblyError(
                "invalid",
                "assembly_cycle",
                "assembly_structure",
                self.entities[missing.entity_id],
                "at least one occurrence is not reachable from an acyclic root",
            )

    def _walk_paths(
        self,
        root: int,
        parent: int,
        parent_to_root: np.ndarray,
        occurrence_path: tuple[AssemblyOccurrence, ...],
        definition_stack: tuple[int, ...],
        outbound: dict[int, list[AssemblyOccurrence]],
    ) -> None:
        if parent in definition_stack:
            entity = self.entities[occurrence_path[-1].entity_id]
            raise _AssemblyError(
                "invalid",
                "assembly_cycle",
                "assembly_structure",
                entity,
                "a product definition repeats on one assembly path",
            )
        next_stack = (*definition_stack, parent)
        for occurrence in outbound.get(parent, []):
            depth = len(occurrence_path) + 1
            if depth > self.limits.max_depth:
                raise AssemblyLimitError(
                    "assembly_depth_limit",
                    "assembly traversal exceeds the configured depth budget",
                )
            if len(self.paths) >= self.limits.max_paths:
                raise AssemblyLimitError(
                    "assembly_path_limit",
                    "assembly paths exceed the configured work budget",
                )
            local = np.asarray(occurrence.local_matrix, dtype=np.float64).reshape(4, 4)
            global_matrix = parent_to_root @ local
            current = (*occurrence_path, occurrence)
            rotation = global_matrix[:3, :3]
            self.paths.append(
                AssemblyPath(
                    len(self.paths),
                    root,
                    occurrence.child_product_definition_entity_id,
                    depth,
                    tuple(item.occurrence_index for item in current),
                    tuple(item.entity_id for item in current),
                    tuple(item.reference_designator for item in current),
                    self._flatten_matrix(global_matrix),
                    self._translation(global_matrix),
                    tuple(float(value) for value in rotation.reshape(-1)),
                    float(np.linalg.det(rotation)),
                )
            )
            self._walk_paths(
                root,
                occurrence.child_product_definition_entity_id,
                global_matrix,
                current,
                next_stack,
                outbound,
            )

    def _representation_record(
        self, representation: Part21Entity
    ) -> tuple[int, Part21Record]:
        matches = [
            record.type_name
            for record in representation.records
            if record.type_name in _REPRESENTATION_TYPES
        ]
        if len(matches) != 1:
            raise _AssemblyError(
                "deferred",
                "representation_type_deferred",
                "shape_representation",
                representation,
                "the representation is outside the controlled shape subset",
            )
        return self._record(representation, matches[0], exact_arguments=3)

    def _schema_identifier(self) -> str | None:
        identifiers = tuple(dict.fromkeys(self.document.schema_identifiers))
        return identifiers[0] if len(identifiers) == 1 else None

    def _entities_of_type(self, type_name: str) -> tuple[Part21Entity, ...]:
        return tuple(
            entity
            for entity in self.document.entities
            if self._has_type(entity, type_name)
        )

    @staticmethod
    def _has_type(entity: Part21Entity, type_name: str) -> bool:
        return any(record.type_name == type_name for record in entity.records)

    def _record(
        self, entity: Part21Entity, type_name: str, *, exact_arguments: int
    ) -> tuple[int, Part21Record]:
        matches = [
            (index, record)
            for index, record in enumerate(entity.records)
            if record.type_name == type_name
        ]
        if len(matches) != 1:
            raise _AssemblyError(
                "invalid",
                "semantic_record_missing",
                type_name.casefold(),
                entity,
                f"expected exactly one {type_name} record",
            )
        record_index, record = matches[0]
        if len(record.arguments) != exact_arguments:
            raise _AssemblyError(
                "invalid",
                "semantic_parameter_count_mismatch",
                type_name.casefold(),
                entity,
                f"{type_name} requires {exact_arguments} encoded parameters in this subset",
            )
        return record_index, record

    def _required_reference(
        self,
        entity: Part21Entity,
        record_index: int,
        value: Part21Value,
        parameter_path: tuple[int, ...],
        role: str,
        expected_types: set[str],
        *,
        unsupported_is_deferred: bool = False,
    ) -> _Reference:
        if value.kind != "entity_reference":
            severity: Literal["invalid", "deferred"] = (
                "deferred" if unsupported_is_deferred else "invalid"
            )
            raise _AssemblyError(
                severity,
                (
                    "transformation_form_deferred"
                    if unsupported_is_deferred
                    else "semantic_reference_required"
                ),
                role,
                entity,
                "the semantic role requires a supported local entity reference",
            )
        target_id = int(str(value.value)[1:])
        target = self.entities.get(target_id)
        if target is None:
            raise _AssemblyError(
                "invalid",
                "unresolved_semantic_reference",
                role,
                entity,
                f"local target #{target_id} is absent",
            )
        if not any(self._has_type(target, item) for item in expected_types):
            severity = "deferred" if unsupported_is_deferred else "invalid"
            raise _AssemblyError(
                severity,
                (
                    "transformation_form_deferred"
                    if unsupported_is_deferred
                    else "unexpected_semantic_target"
                ),
                role,
                entity,
                "the target type is outside the expected controlled role",
            )
        edge = self._edge(entity.entity_id, record_index, parameter_path, target_id)
        return _Reference(target, edge)

    def _reference_list(
        self,
        entity: Part21Entity,
        record_index: int,
        value: Part21Value,
        parameter_path: tuple[int, ...],
        role: str,
    ) -> tuple[_Reference, ...]:
        if value.kind != "list" or not value.children:
            raise _AssemblyError(
                "invalid",
                "semantic_reference_list_required",
                role,
                entity,
                "the semantic role requires a non-empty aggregate of local references",
            )
        references: list[_Reference] = []
        for child_index, child in enumerate(value.children):
            if child.kind != "entity_reference":
                raise _AssemblyError(
                    "invalid",
                    "semantic_reference_required",
                    role,
                    entity,
                    "every aggregate member must be a local entity reference",
                )
            target_id = int(str(child.value)[1:])
            target = self.entities.get(target_id)
            if target is None:
                raise _AssemblyError(
                    "invalid",
                    "unresolved_semantic_reference",
                    role,
                    entity,
                    f"local target #{target_id} is absent",
                )
            edge = self._edge(
                entity.entity_id,
                record_index,
                (*parameter_path, child_index),
                target_id,
            )
            references.append(_Reference(target, edge))
        return tuple(references)

    def _referrers(
        self,
        target_id: int,
        source_type: str,
        *,
        record_index: int,
        parameter_path: tuple[int, ...],
    ) -> tuple[_Reference, ...]:
        references: list[_Reference] = []
        for source in self._entities_of_type(source_type):
            for edge in self.graph.outbound(source.entity_id):
                if (
                    edge.is_local
                    and edge.target_entity_id == target_id
                    and edge.record_index == record_index
                    and edge.parameter_path == parameter_path
                ):
                    references.append(_Reference(source, edge))
        return tuple(references)

    def _edge(
        self,
        source_id: int,
        record_index: int,
        parameter_path: tuple[int, ...],
        target_id: int,
    ) -> STEPGraphEdge:
        matches = [
            edge
            for edge in self.graph.outbound(source_id)
            if edge.is_local
            and edge.record_index == record_index
            and edge.parameter_path == parameter_path
            and edge.target_entity_id == target_id
        ]
        if len(matches) != 1:
            raise _AssemblyError(
                "invalid",
                "physical_reference_provenance_missing",
                "physical_reference",
                self.entities[source_id],
                "the semantic role cannot be joined to one physical reference occurrence",
            )
        return matches[0]

    def _required_string(
        self, entity: Part21Entity, value: Part21Value, role: str
    ) -> str:
        if value.kind != "string":
            raise _AssemblyError(
                "invalid",
                "semantic_string_required",
                role,
                entity,
                "the controlled semantic attribute requires an encoded string",
            )
        return str(value.value)

    def _optional_string(
        self, entity: Part21Entity, value: Part21Value, role: str
    ) -> str:
        if value.kind == "omitted":
            return ""
        return self._required_string(entity, value, role)

    def _typed_number(
        self,
        entity: Part21Entity,
        value: Part21Value,
        expected_type: str,
        role: str,
    ) -> float:
        if (
            value.kind != "typed"
            or value.value != expected_type
            or len(value.children) != 1
            or value.children[0].kind not in {"integer", "real"}
        ):
            raise _AssemblyError(
                "invalid",
                "typed_measure_required",
                role,
                entity,
                f"the conversion factor requires {expected_type}(numeric_value)",
            )
        return float(value.children[0].value)

    def _append_relation(
        self, occurrence_index: int, role: str, reference: _Reference
    ) -> None:
        if len(self.relations) >= self.limits.max_relations:
            raise AssemblyLimitError(
                "assembly_relation_limit",
                "assembly semantic relations exceed the configured work budget",
            )
        edge = reference.edge
        if edge.target_entity_id is None:
            raise RuntimeError("assembly semantic relations require local targets")
        self.relations.append(
            AssemblyRelation(
                occurrence_index,
                role,
                edge.source_entity_id,
                edge.target_entity_id,
                edge.edge_index,
                edge.parameter_path,
                edge.source_span,
            )
        )

    def _diagnose(self, error: _AssemblyError) -> None:
        self.diagnostics.append(
            AssemblyDiagnostic(
                error.severity,
                error.reason_code,
                error.role,
                None if error.entity is None else error.entity.entity_id,
                None if error.entity is None else error.entity.span.start_line,
                error.detail,
            )
        )

    def _result(self, schema: str | None) -> AssemblyResult:
        invalid = [item for item in self.diagnostics if item.severity == "invalid"]
        deferred = [item for item in self.diagnostics if item.severity == "deferred"]
        if invalid:
            decision: AssemblyDecision = "reject"
            reason_code = invalid[0].reason_code
        elif deferred:
            decision = "quarantine"
            reason_code = deferred[0].reason_code
        elif self.occurrences and self.paths:
            decision = "accept"
            reason_code = "assembly_paths_evaluated"
        else:
            decision = "quarantine"
            reason_code = "assembly_path_not_evaluated"
        definitions = {
            value
            for occurrence in self.occurrences
            for value in (
                occurrence.parent_product_definition_entity_id,
                occurrence.child_product_definition_entity_id,
            )
        }
        child_counts: dict[int, int] = {}
        for occurrence in self.occurrences:
            child_counts[occurrence.child_product_definition_entity_id] = (
                child_counts.get(occurrence.child_product_definition_entity_id, 0) + 1
            )
        return AssemblyResult(
            decision,
            reason_code,
            schema,
            len(self.occurrences),
            len(self.paths),
            len(self.relations),
            len(self.units),
            len(definitions),
            sum(count > 1 for count in child_counts.values()),
            max((path.depth for path in self.paths), default=0),
            tuple(self.occurrences),
            tuple(self.paths),
            tuple(self.relations),
            tuple(self.units),
            tuple(self.diagnostics),
            self.graph,
        )

    @staticmethod
    def _rigid_inverse(matrix: np.ndarray) -> np.ndarray:
        result = np.eye(4, dtype=np.float64)
        rotation = matrix[:3, :3]
        translation = matrix[:3, 3]
        result[:3, :3] = rotation.T
        result[:3, 3] = -(rotation.T @ translation)
        return result

    @staticmethod
    def _flatten_matrix(matrix: np.ndarray) -> tuple[float, ...]:
        return tuple(float(value) for value in matrix.reshape(-1))

    @staticmethod
    def _translation(matrix: np.ndarray) -> tuple[float, float, float]:
        return tuple(float(value) for value in matrix[:3, 3])  # type: ignore[return-value]
