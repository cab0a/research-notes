"""Bounded AP242 product-to-shape path resolution over the Part 21 graph."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

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


AP242_SCHEMA_IDENTIFIER = "AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF"
AP242Decision = Literal["accept", "quarantine", "reject"]
AP242ItemRole = Literal[
    "placement", "solid_model", "geometric_item", "mapped_item", "unclassified"
]


@dataclass(frozen=True)
class AP242PathLimits:
    """Explicit semantic work budgets for one AP242 path query."""

    max_product_definitions: int = 10_000
    max_paths: int = 20_000
    max_relations: int = 200_000
    max_representation_items: int = 100_000
    max_units: int = 20_000

    def __post_init__(self) -> None:
        for field_name, value in vars(self).items():
            if not isinstance(value, int) or isinstance(value, bool):
                raise TypeError(f"{field_name} must be an integer")
            if value <= 0:
                raise ValueError(f"{field_name} must be positive")


DEFAULT_AP242_PATH_LIMITS = AP242PathLimits()


class AP242PathLimitError(RuntimeError):
    """A stable quarantine outcome for an AP242 semantic work budget."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


@dataclass(frozen=True)
class AP242PathDiagnostic:
    """One invalid or deferred semantic-path observation."""

    severity: Literal["invalid", "deferred"]
    reason_code: str
    role: str
    entity_id: int | None
    source_line: int | None
    detail: str


@dataclass(frozen=True)
class AP242SemanticRelation:
    """One schema-derived role linked back to a physical reference occurrence."""

    path_index: int
    role: str
    source_entity_id: int
    target_entity_id: int
    source_edge_index: int
    parameter_path: tuple[int, ...]
    source_span: Part21SourceSpan


@dataclass(frozen=True)
class AP242RepresentationItem:
    """One direct representation item with a bounded role classification."""

    path_index: int
    item_index: int
    entity_id: int
    role: AP242ItemRole
    record_types: tuple[str, ...]
    name: str | None
    source_span: Part21SourceSpan


@dataclass(frozen=True)
class AP242UnitObservation:
    """One unit assigned by the representation context."""

    path_index: int
    unit_index: int
    entity_id: int
    unit_kind: str
    si_prefix: str | None
    si_name: str | None
    record_types: tuple[str, ...]
    source_span: Part21SourceSpan


@dataclass(frozen=True)
class AP242ProductRepresentationPath:
    """One resolved product-definition to shape-representation path."""

    path_index: int
    product_entity_id: int
    product_identifier: str
    product_name: str
    formation_entity_id: int
    formation_identifier: str
    product_definition_entity_id: int
    product_definition_identifier: str
    product_definition_context_entity_id: int
    product_definition_shape_entity_id: int
    shape_definition_representation_entity_id: int
    representation_entity_id: int
    representation_type: str
    representation_name: str
    representation_context_entity_id: int
    context_identifier: str
    context_type: str
    coordinate_space_dimension: int
    representation_item_count: int
    placement_count: int
    unit_count: int
    source_span: Part21SourceSpan


@dataclass(frozen=True)
class AP242PathResult:
    """Controlled AP242 path resolution evidence and its physical graph."""

    decision: AP242Decision
    reason_code: str
    schema_identifier: str | None
    product_definition_count: int
    path_count: int
    relation_count: int
    representation_item_count: int
    placement_count: int
    unit_count: int
    paths: tuple[AP242ProductRepresentationPath, ...]
    relations: tuple[AP242SemanticRelation, ...]
    representation_items: tuple[AP242RepresentationItem, ...]
    units: tuple[AP242UnitObservation, ...]
    diagnostics: tuple[AP242PathDiagnostic, ...]
    graph: STEPGraph


class _SemanticError(RuntimeError):
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
    target: Part21Entity
    edge: STEPGraphEdge


_REPRESENTATION_TYPES = {
    "SHAPE_REPRESENTATION",
    "ADVANCED_BREP_SHAPE_REPRESENTATION",
    "FACETED_BREP_SHAPE_REPRESENTATION",
    "TESSELLATED_SHAPE_REPRESENTATION",
}
_PLACEMENT_TYPES = {
    "AXIS1_PLACEMENT",
    "AXIS2_PLACEMENT_2D",
    "AXIS2_PLACEMENT_3D",
}
_SOLID_MODEL_TYPES = {
    "BLOCK",
    "BREP_WITH_VOIDS",
    "CSG_SOLID",
    "FACETED_BREP",
    "MANIFOLD_SOLID_BREP",
    "SWEPT_AREA_SOLID",
    "SWEPT_FACE_SOLID",
    "TESSELLATED_SOLID",
}
_GEOMETRIC_ITEM_TYPES = {
    "CARTESIAN_POINT",
    "DIRECTION",
    "EDGE_BASED_WIREFRAME_MODEL",
    "FACE_BASED_SURFACE_MODEL",
    "GEOMETRIC_CURVE_SET",
    "GEOMETRIC_SET",
    "SHELL_BASED_SURFACE_MODEL",
    "SHELL_BASED_WIREFRAME_MODEL",
}
_UNIT_KIND_TYPES = {
    "LENGTH_UNIT": "length",
    "PLANE_ANGLE_UNIT": "plane_angle",
    "SOLID_ANGLE_UNIT": "solid_angle",
}


def resolve_ap242_product_paths(
    source_bytes: bytes,
    *,
    parse_limits: STEPParseLimits = DEFAULT_STEP_PARSE_LIMITS,
    graph_limits: STEPGraphLimits = DEFAULT_STEP_GRAPH_LIMITS,
    path_limits: AP242PathLimits = DEFAULT_AP242_PATH_LIMITS,
) -> AP242PathResult:
    """Resolve a controlled AP242 product-to-shape subset with source provenance."""
    if not isinstance(source_bytes, bytes):
        raise TypeError("source_bytes must be bytes")
    if not isinstance(parse_limits, STEPParseLimits):
        raise TypeError("parse_limits must be STEPParseLimits")
    if not isinstance(graph_limits, STEPGraphLimits):
        raise TypeError("graph_limits must be STEPGraphLimits")
    if not isinstance(path_limits, AP242PathLimits):
        raise TypeError("path_limits must be AP242PathLimits")
    document = parse_part21_document(source_bytes, limits=parse_limits)
    graph = build_step_graph(
        source_bytes, parse_limits=parse_limits, graph_limits=graph_limits
    )
    return _AP242Resolver(document, graph, path_limits).resolve()


class _AP242Resolver:
    def __init__(
        self, document: Part21Document, graph: STEPGraph, limits: AP242PathLimits
    ) -> None:
        self.document = document
        self.graph = graph
        self.limits = limits
        self.entities = {entity.entity_id: entity for entity in document.entities}
        self.paths: list[AP242ProductRepresentationPath] = []
        self.relations: list[AP242SemanticRelation] = []
        self.items: list[AP242RepresentationItem] = []
        self.units: list[AP242UnitObservation] = []
        self.diagnostics: list[AP242PathDiagnostic] = []

    def resolve(self) -> AP242PathResult:
        schema = self._schema_identifier()
        product_definitions = self._entities_of_type("PRODUCT_DEFINITION")
        if len(product_definitions) > self.limits.max_product_definitions:
            raise AP242PathLimitError(
                "ap242_product_definition_limit",
                "product definitions exceed the AP242 path budget",
            )
        if schema != AP242_SCHEMA_IDENTIFIER:
            self._diagnose(
                _SemanticError(
                    "deferred",
                    "unsupported_application_schema",
                    "file_schema",
                    None,
                    "the controlled resolver accepts only the declared AP242 MIM schema",
                )
            )
            return self._result(schema, len(product_definitions))
        if not product_definitions:
            self._diagnose(
                _SemanticError(
                    "deferred",
                    "product_definition_not_found",
                    "product_definition",
                    None,
                    "no encoded PRODUCT_DEFINITION root is available",
                )
            )
            return self._result(schema, 0)
        for product_definition in product_definitions:
            try:
                self._resolve_product_definition(product_definition)
            except _SemanticError as error:
                self._diagnose(error)
        return self._result(schema, len(product_definitions))

    def _resolve_product_definition(self, product_definition: Part21Entity) -> None:
        pd_record_index, pd_record = self._record(
            product_definition, "PRODUCT_DEFINITION", exact_arguments=4
        )
        formation = self._required_reference(
            product_definition,
            pd_record_index,
            pd_record,
            2,
            "product_definition.formation",
            {"PRODUCT_DEFINITION_FORMATION"},
        )
        pd_context = self._required_reference(
            product_definition,
            pd_record_index,
            pd_record,
            3,
            "product_definition.frame_of_reference",
            {"PRODUCT_DEFINITION_CONTEXT"},
        )
        formation_record_index, formation_record = self._record(
            formation.target, "PRODUCT_DEFINITION_FORMATION", exact_arguments=3
        )
        product = self._required_reference(
            formation.target,
            formation_record_index,
            formation_record,
            2,
            "product_definition_formation.of_product",
            {"PRODUCT"},
        )
        _, product_record = self._record(product.target, "PRODUCT", exact_arguments=4)
        product_identifier = self._required_string(
            product.target, product_record, 0, "product.id"
        )
        product_name = self._required_string(
            product.target, product_record, 1, "product.name"
        )
        formation_identifier = self._required_string(
            formation.target, formation_record, 0, "product_definition_formation.id"
        )
        definition_identifier = self._required_string(
            product_definition, pd_record, 0, "product_definition.id"
        )
        shapes = self._referrers(
            product_definition.entity_id,
            "PRODUCT_DEFINITION_SHAPE",
            record_index=0,
            parameter_path=(2,),
        )
        if not shapes:
            raise _SemanticError(
                "deferred",
                "product_definition_shape_not_found",
                "product_definition_shape.definition",
                product_definition,
                "a product definition need not have a geometric shape association",
            )
        if len(shapes) > 1:
            raise _SemanticError(
                "invalid",
                "duplicate_product_definition_shape",
                "product_definition_shape.definition",
                product_definition,
                "more than one PRODUCT_DEFINITION_SHAPE refers to the same definition",
            )
        shape = shapes[0]
        shape_record_index, shape_record = self._record(
            shape.target, "PRODUCT_DEFINITION_SHAPE", exact_arguments=3
        )
        shape_definition = self._required_reference(
            shape.target,
            shape_record_index,
            shape_record,
            2,
            "product_definition_shape.definition",
            {"PRODUCT_DEFINITION"},
        )
        if shape_definition.target.entity_id != product_definition.entity_id:
            raise _SemanticError(
                "invalid",
                "shape_definition_target_mismatch",
                "product_definition_shape.definition",
                shape.target,
                "the shape definition does not refer to the selected product definition",
            )
        associations = self._referrers(
            shape.target.entity_id,
            "SHAPE_DEFINITION_REPRESENTATION",
            record_index=0,
            parameter_path=(0,),
        )
        if not associations:
            raise _SemanticError(
                "deferred",
                "shape_representation_not_found",
                "shape_definition_representation.definition",
                shape.target,
                "the shape definition has no supported representation association",
            )
        # Keep one semantic row per physical reference occurrence.  ``shape``
        # already carries the PRODUCT_DEFINITION_SHAPE -> PRODUCT_DEFINITION
        # edge used to discover the reverse association.
        base_relations = (formation, pd_context, product, shape)
        for association in associations:
            self._resolve_association(
                product_definition,
                product_identifier,
                product_name,
                formation,
                formation_identifier,
                pd_context,
                definition_identifier,
                shape,
                association,
                base_relations,
            )

    def _resolve_association(
        self,
        product_definition: Part21Entity,
        product_identifier: str,
        product_name: str,
        formation: _Reference,
        formation_identifier: str,
        pd_context: _Reference,
        definition_identifier: str,
        shape: _Reference,
        association: _Reference,
        base_relations: Sequence[_Reference],
    ) -> None:
        if len(self.paths) >= self.limits.max_paths:
            raise AP242PathLimitError(
                "ap242_path_limit", "resolved paths exceed the AP242 path budget"
            )
        association_record_index, association_record = self._record(
            association.target,
            "SHAPE_DEFINITION_REPRESENTATION",
            exact_arguments=2,
        )
        definition = self._required_reference(
            association.target,
            association_record_index,
            association_record,
            0,
            "shape_definition_representation.definition",
            {"PRODUCT_DEFINITION_SHAPE"},
        )
        if definition.target.entity_id != shape.target.entity_id:
            raise _SemanticError(
                "invalid",
                "shape_association_target_mismatch",
                "shape_definition_representation.definition",
                association.target,
                "the representation association targets another shape definition",
            )
        representation = self._required_reference(
            association.target,
            association_record_index,
            association_record,
            1,
            "shape_definition_representation.used_representation",
            _REPRESENTATION_TYPES,
            unsupported_is_deferred=True,
        )
        representation_type = self._single_supported_type(
            representation.target, _REPRESENTATION_TYPES, "shape_representation"
        )
        representation_record_index, representation_record = self._record(
            representation.target, representation_type, exact_arguments=3
        )
        representation_name = self._required_string(
            representation.target, representation_record, 0, "representation.name"
        )
        item_references = self._reference_list(
            representation.target,
            representation_record_index,
            representation_record,
            1,
            "representation.items",
        )
        context = self._required_reference(
            representation.target,
            representation_record_index,
            representation_record,
            2,
            "representation.context_of_items",
            {"REPRESENTATION_CONTEXT"},
        )
        context_identifier, context_type, dimension, unit_references = (
            self._decode_context(context.target)
        )
        path_index = len(self.paths)
        classified_items = self._decode_items(path_index, item_references)
        decoded_units = self._decode_units(path_index, unit_references)
        placement_count = sum(item.role == "placement" for item in classified_items)
        path = AP242ProductRepresentationPath(
            path_index,
            product_identifier=product_identifier,
            product_name=product_name,
            product_entity_id=base_relations[2].target.entity_id,
            formation_entity_id=formation.target.entity_id,
            formation_identifier=formation_identifier,
            product_definition_entity_id=product_definition.entity_id,
            product_definition_identifier=definition_identifier,
            product_definition_context_entity_id=pd_context.target.entity_id,
            product_definition_shape_entity_id=shape.target.entity_id,
            shape_definition_representation_entity_id=association.target.entity_id,
            representation_entity_id=representation.target.entity_id,
            representation_type=representation_type,
            representation_name=representation_name,
            representation_context_entity_id=context.target.entity_id,
            context_identifier=context_identifier,
            context_type=context_type,
            coordinate_space_dimension=dimension,
            representation_item_count=len(classified_items),
            placement_count=placement_count,
            unit_count=len(decoded_units),
            source_span=product_definition.span,
        )
        self.paths.append(path)
        relation_refs = (
            *base_relations,
            association,
            representation,
            context,
            *item_references,
            *unit_references,
        )
        for reference in relation_refs:
            self._append_relation(path_index, reference)
        self.items.extend(classified_items)
        self.units.extend(decoded_units)

    def _decode_context(
        self, context: Part21Entity
    ) -> tuple[str, str, int, tuple[_Reference, ...]]:
        _, representation_context = self._record(
            context, "REPRESENTATION_CONTEXT", exact_arguments=2
        )
        context_identifier = self._required_string(
            context, representation_context, 0, "representation_context.identifier"
        )
        context_type = self._required_string(
            context, representation_context, 1, "representation_context.type"
        )
        try:
            _, geometric_context = self._record(
                context, "GEOMETRIC_REPRESENTATION_CONTEXT", exact_arguments=1
            )
        except _SemanticError as error:
            raise _SemanticError(
                "deferred",
                "geometric_context_not_available",
                "geometric_representation_context",
                context,
                "the controlled path requires an encoded geometric context",
            ) from error
        dimension_value = geometric_context.arguments[0]
        if dimension_value.kind != "integer" or not isinstance(
            dimension_value.value, int
        ):
            raise _SemanticError(
                "invalid",
                "invalid_coordinate_space_dimension",
                "geometric_representation_context.coordinate_space_dimension",
                context,
                "coordinate-space dimension must be an encoded integer",
            )
        if dimension_value.value not in {2, 3}:
            raise _SemanticError(
                "deferred",
                "unsupported_coordinate_space_dimension",
                "geometric_representation_context.coordinate_space_dimension",
                context,
                "the controlled path supports only two- or three-dimensional contexts",
            )
        try:
            unit_record_index, unit_context = self._record(
                context, "GLOBAL_UNIT_ASSIGNED_CONTEXT", exact_arguments=1
            )
        except _SemanticError as error:
            raise _SemanticError(
                "deferred",
                "global_units_not_available",
                "global_unit_assigned_context",
                context,
                "the controlled path requires explicit context units",
            ) from error
        unit_references = self._reference_list(
            context,
            unit_record_index,
            unit_context,
            0,
            "global_unit_assigned_context.units",
        )
        return (
            context_identifier,
            context_type,
            dimension_value.value,
            unit_references,
        )

    def _decode_items(
        self, path_index: int, references: Sequence[_Reference]
    ) -> tuple[AP242RepresentationItem, ...]:
        if len(self.items) + len(references) > self.limits.max_representation_items:
            raise AP242PathLimitError(
                "ap242_representation_item_limit",
                "representation items exceed the AP242 path budget",
            )
        observations: list[AP242RepresentationItem] = []
        for item_index, reference in enumerate(references):
            record_types = tuple(record.type_name for record in reference.target.records)
            type_set = set(record_types)
            if type_set & _PLACEMENT_TYPES:
                role: AP242ItemRole = "placement"
            elif type_set & _SOLID_MODEL_TYPES:
                role = "solid_model"
            elif "MAPPED_ITEM" in type_set:
                role = "mapped_item"
            elif type_set & _GEOMETRIC_ITEM_TYPES:
                role = "geometric_item"
            else:
                role = "unclassified"
                self._diagnose(
                    _SemanticError(
                        "deferred",
                        "representation_item_type_deferred",
                        "representation.items",
                        reference.target,
                        "item type is outside the controlled AP242 classification subset",
                    )
                )
            observations.append(
                AP242RepresentationItem(
                    path_index,
                    item_index,
                    reference.target.entity_id,
                    role,
                    record_types,
                    self._first_string(reference.target),
                    reference.target.span,
                )
            )
        return tuple(observations)

    def _decode_units(
        self, path_index: int, references: Sequence[_Reference]
    ) -> tuple[AP242UnitObservation, ...]:
        if len(self.units) + len(references) > self.limits.max_units:
            raise AP242PathLimitError(
                "ap242_unit_limit", "context units exceed the AP242 path budget"
            )
        observations: list[AP242UnitObservation] = []
        for unit_index, reference in enumerate(references):
            record_types = tuple(record.type_name for record in reference.target.records)
            kinds = {
                unit_kind
                for type_name, unit_kind in _UNIT_KIND_TYPES.items()
                if type_name in record_types
            }
            if len(kinds) != 1:
                self._diagnose(
                    _SemanticError(
                        "deferred",
                        "unit_kind_deferred",
                        "global_unit_assigned_context.units",
                        reference.target,
                        "unit kind is outside the controlled length and angle subset",
                    )
                )
                unit_kind = "unclassified"
            else:
                unit_kind = next(iter(kinds))
            si_prefix: str | None = None
            si_name: str | None = None
            si_records = [
                record for record in reference.target.records if record.type_name == "SI_UNIT"
            ]
            if len(si_records) == 1 and len(si_records[0].arguments) == 2:
                prefix, name = si_records[0].arguments
                if prefix.kind == "enumeration":
                    si_prefix = str(prefix.value)
                elif prefix.kind != "omitted":
                    self._diagnose(
                        _SemanticError(
                            "invalid",
                            "invalid_si_unit_prefix",
                            "si_unit.prefix",
                            reference.target,
                            "SI unit prefix must be an enumeration or omitted marker",
                        )
                    )
                if name.kind == "enumeration":
                    si_name = str(name.value)
                else:
                    self._diagnose(
                        _SemanticError(
                            "invalid",
                            "invalid_si_unit_name",
                            "si_unit.name",
                            reference.target,
                            "SI unit name must be an enumeration",
                        )
                    )
            else:
                self._diagnose(
                    _SemanticError(
                        "deferred",
                        "non_si_unit_deferred",
                        "global_unit_assigned_context.units",
                        reference.target,
                        "non-SI or complex unit conversion is not evaluated in this release",
                    )
                )
            observations.append(
                AP242UnitObservation(
                    path_index,
                    unit_index,
                    reference.target.entity_id,
                    unit_kind,
                    si_prefix,
                    si_name,
                    record_types,
                    reference.target.span,
                )
            )
        return tuple(observations)

    def _schema_identifier(self) -> str | None:
        identifiers = tuple(dict.fromkeys(self.document.schema_identifiers))
        if len(identifiers) != 1:
            return None
        return identifiers[0]

    def _entities_of_type(self, type_name: str) -> tuple[Part21Entity, ...]:
        return tuple(
            entity
            for entity in self.document.entities
            if any(record.type_name == type_name for record in entity.records)
        )

    def _record(
        self, entity: Part21Entity, type_name: str, *, exact_arguments: int
    ) -> tuple[int, Part21Record]:
        matches = [
            (index, record)
            for index, record in enumerate(entity.records)
            if record.type_name == type_name
        ]
        if len(matches) != 1:
            raise _SemanticError(
                "invalid",
                "semantic_record_missing",
                type_name.casefold(),
                entity,
                f"expected exactly one {type_name} record",
            )
        record_index, record = matches[0]
        if len(record.arguments) != exact_arguments:
            raise _SemanticError(
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
        record: Part21Record,
        parameter_index: int,
        role: str,
        expected_types: set[str],
        *,
        unsupported_is_deferred: bool = False,
    ) -> _Reference:
        value = record.arguments[parameter_index]
        if value.kind != "entity_reference":
            raise _SemanticError(
                "invalid",
                "semantic_reference_required",
                role,
                entity,
                "the semantic role requires a local entity reference",
            )
        target_id = int(str(value.value)[1:])
        target = self.entities.get(target_id)
        if target is None:
            raise _SemanticError(
                "invalid",
                "unresolved_semantic_reference",
                role,
                entity,
                f"local target #{target_id} is absent",
            )
        record_types = {item.type_name for item in target.records}
        if not record_types & expected_types:
            severity: Literal["invalid", "deferred"] = (
                "deferred" if unsupported_is_deferred else "invalid"
            )
            reason = (
                "representation_type_deferred"
                if unsupported_is_deferred
                else "unexpected_semantic_target"
            )
            raise _SemanticError(
                severity,
                reason,
                role,
                entity,
                "target type is outside the expected controlled role",
            )
        edge = self._edge(entity.entity_id, record_index, (parameter_index,), target_id)
        return _Reference(target, edge)

    def _reference_list(
        self,
        entity: Part21Entity,
        record_index: int,
        record: Part21Record,
        parameter_index: int,
        role: str,
    ) -> tuple[_Reference, ...]:
        value = record.arguments[parameter_index]
        if value.kind != "list" or not value.children:
            raise _SemanticError(
                "invalid",
                "semantic_reference_list_required",
                role,
                entity,
                "the semantic role requires a non-empty aggregate of local references",
            )
        references: list[_Reference] = []
        for child_index, child in enumerate(value.children):
            if child.kind != "entity_reference":
                raise _SemanticError(
                    "invalid",
                    "semantic_reference_list_required",
                    role,
                    entity,
                    "every aggregate member must be a local entity reference",
                )
            target_id = int(str(child.value)[1:])
            target = self.entities.get(target_id)
            if target is None:
                raise _SemanticError(
                    "invalid",
                    "unresolved_semantic_reference",
                    role,
                    entity,
                    f"local target #{target_id} is absent",
                )
            edge = self._edge(
                entity.entity_id,
                record_index,
                (parameter_index, child_index),
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
                    edge.target_entity_id == target_id
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
            if edge.record_index == record_index
            and edge.parameter_path == parameter_path
            and edge.target_entity_id == target_id
            and edge.is_local
        ]
        if len(matches) != 1:
            source = self.entities[source_id]
            raise _SemanticError(
                "invalid",
                "physical_reference_provenance_missing",
                "physical_reference",
                source,
                "semantic role cannot be joined to one physical reference occurrence",
            )
        return matches[0]

    def _required_string(
        self, entity: Part21Entity, record: Part21Record, index: int, role: str
    ) -> str:
        value = record.arguments[index]
        if value.kind != "string":
            raise _SemanticError(
                "invalid",
                "semantic_string_required",
                role,
                entity,
                "the controlled semantic attribute requires an encoded string",
            )
        return str(value.value)

    @staticmethod
    def _first_string(entity: Part21Entity) -> str | None:
        for record in entity.records:
            if record.arguments and record.arguments[0].kind == "string":
                return str(record.arguments[0].value)
        return None

    @staticmethod
    def _single_supported_type(
        entity: Part21Entity, supported: set[str], role: str
    ) -> str:
        matches = [
            record.type_name for record in entity.records if record.type_name in supported
        ]
        if len(matches) != 1:
            raise _SemanticError(
                "deferred",
                "representation_type_deferred",
                role,
                entity,
                "representation type is ambiguous or outside the controlled subset",
            )
        return matches[0]

    def _append_relation(self, path_index: int, reference: _Reference) -> None:
        if len(self.relations) >= self.limits.max_relations:
            raise AP242PathLimitError(
                "ap242_relation_limit",
                "semantic relations exceed the AP242 path budget",
            )
        edge = reference.edge
        if edge.target_entity_id is None:
            raise RuntimeError("AP242 semantic relations require local entity targets")
        self.relations.append(
            AP242SemanticRelation(
                path_index,
                self._relation_role(edge),
                edge.source_entity_id,
                edge.target_entity_id,
                edge.edge_index,
                edge.parameter_path,
                edge.source_span,
            )
        )

    def _relation_role(self, edge: STEPGraphEdge) -> str:
        source_types = self.graph.node(edge.source_entity_id).record_types
        source_type = source_types[edge.record_index]
        role_by_path = {
            ("PRODUCT_DEFINITION", (2,)): "product_definition.formation",
            ("PRODUCT_DEFINITION", (3,)): "product_definition.frame_of_reference",
            ("PRODUCT_DEFINITION_FORMATION", (2,)): "product_definition_formation.of_product",
            ("PRODUCT_DEFINITION_SHAPE", (2,)): "product_definition_shape.definition",
            ("SHAPE_DEFINITION_REPRESENTATION", (0,)): "shape_definition_representation.definition",
            ("SHAPE_DEFINITION_REPRESENTATION", (1,)): "shape_definition_representation.used_representation",
            ("SHAPE_REPRESENTATION", (2,)): "representation.context_of_items",
            ("ADVANCED_BREP_SHAPE_REPRESENTATION", (2,)): "representation.context_of_items",
            ("FACETED_BREP_SHAPE_REPRESENTATION", (2,)): "representation.context_of_items",
            ("TESSELLATED_SHAPE_REPRESENTATION", (2,)): "representation.context_of_items",
        }
        direct = role_by_path.get((source_type, edge.parameter_path))
        if direct is not None:
            return direct
        if source_type in _REPRESENTATION_TYPES and edge.parameter_path[:1] == (1,):
            return "representation.items"
        if source_type == "GLOBAL_UNIT_ASSIGNED_CONTEXT" and edge.parameter_path[:1] == (0,):
            return "global_unit_assigned_context.units"
        return "physical_reference"

    def _diagnose(self, error: _SemanticError) -> None:
        self.diagnostics.append(
            AP242PathDiagnostic(
                error.severity,
                error.reason_code,
                error.role,
                None if error.entity is None else error.entity.entity_id,
                None if error.entity is None else error.entity.span.start_line,
                error.detail,
            )
        )

    def _result(self, schema: str | None, product_definition_count: int) -> AP242PathResult:
        invalid = [item for item in self.diagnostics if item.severity == "invalid"]
        deferred = [item for item in self.diagnostics if item.severity == "deferred"]
        if invalid:
            decision: AP242Decision = "reject"
            reason_code = invalid[0].reason_code
        elif deferred:
            decision = "quarantine"
            reason_code = deferred[0].reason_code
        elif self.paths:
            decision = "accept"
            reason_code = "ap242_paths_resolved"
        else:
            decision = "quarantine"
            reason_code = "ap242_path_not_resolved"
        return AP242PathResult(
            decision,
            reason_code,
            schema,
            product_definition_count,
            len(self.paths),
            len(self.relations),
            len(self.items),
            sum(item.role == "placement" for item in self.items),
            len(self.units),
            tuple(self.paths),
            tuple(self.relations),
            tuple(self.items),
            tuple(self.units),
            tuple(self.diagnostics),
            self.graph,
        )
