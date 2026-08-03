"""Bounded symbol, type, and inheritance resolution for controlled EXPRESS models."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from research_notes.express_schema import (
    ExpressAttribute,
    ExpressDocument,
    ExpressEntityDeclaration,
    ExpressSchemaDeclaration,
    ExpressTypeReference,
)


ExpressSymbolKind = Literal[
    "schema", "type", "entity", "constant", "function", "procedure", "rule"
]
ExpressResolutionStatus = Literal[
    "resolved", "unresolved", "ambiguous", "invalid_kind", "cyclic", "deferred"
]


@dataclass(frozen=True)
class ExpressResolutionLimits:
    """Explicit resource limits for semantic graph construction."""

    max_symbols: int = 20_000
    max_references: int = 200_000
    max_inheritance_edges: int = 50_000

    def __post_init__(self) -> None:
        for field_name, value in vars(self).items():
            if value <= 0:
                raise ValueError(f"{field_name} must be positive")


DEFAULT_EXPRESS_RESOLUTION_LIMITS = ExpressResolutionLimits()


@dataclass(frozen=True)
class ExpressSymbol:
    """One schema or declaration symbol with a stable analysis-local identity."""

    symbol_id: str
    schema_name: str
    name: str
    kind: ExpressSymbolKind
    source_line: int


@dataclass(frozen=True)
class ExpressReferenceResolution:
    """One named reference and the candidates considered by the resolver."""

    schema_name: str
    owner_symbol_id: str
    role: str
    source_name: str
    expected_kinds: tuple[ExpressSymbolKind, ...]
    status: ExpressResolutionStatus
    resolved_symbol_id: str | None
    candidate_symbol_ids: tuple[str, ...]
    source_line: int


@dataclass(frozen=True)
class ExpressTypeResolution:
    """The controlled terminal-domain result for one defined type."""

    symbol_id: str
    schema_name: str
    type_name: str
    status: ExpressResolutionStatus
    terminal_domain: str | None
    alias_chain: tuple[str, ...]


@dataclass(frozen=True)
class ExpressAggregateBoundResolution:
    """A bounded evaluation result for one aggregate type expression."""

    schema_name: str
    owner_symbol_id: str
    role: str
    aggregate_kind: str
    lower_source: str | None
    upper_source: str | None
    lower_status: str
    upper_status: str
    lower_value: int | None
    upper_value: int | None
    status: ExpressResolutionStatus


@dataclass(frozen=True)
class ExpressInheritanceResolution:
    """Resolved entity ancestry and effective attribute inventory."""

    symbol_id: str
    schema_name: str
    entity_name: str
    status: ExpressResolutionStatus
    immediate_supertype_ids: tuple[str, ...]
    transitive_supertype_ids: tuple[str, ...]
    local_attribute_count: int
    inherited_attribute_count: int
    effective_attribute_count: int
    redeclared_attribute_count: int


@dataclass(frozen=True)
class ExpressResolutionDiagnostic:
    """One stable semantic failure or explicit implementation boundary."""

    reason_code: str
    schema_name: str
    owner_symbol_id: str
    detail: str
    source_line: int


@dataclass(frozen=True)
class ExpressResolvedDocument:
    """A controlled semantic graph derived from one parsed EXPRESS document."""

    decision: Literal["accept", "reject"]
    reason_code: str
    symbols: tuple[ExpressSymbol, ...]
    references: tuple[ExpressReferenceResolution, ...]
    types: tuple[ExpressTypeResolution, ...]
    aggregate_bounds: tuple[ExpressAggregateBoundResolution, ...]
    inheritance: tuple[ExpressInheritanceResolution, ...]
    diagnostics: tuple[ExpressResolutionDiagnostic, ...]
    expression_validation: Literal["envelope_only"] = "envelope_only"
    rule_execution: Literal["not_attempted"] = "not_attempted"
    external_schema_loading: Literal["not_attempted"] = "not_attempted"


class ExpressResolutionLimitError(RuntimeError):
    """A stable quarantine outcome for a semantic resource limit."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


@dataclass(frozen=True)
class _Declaration:
    symbol: ExpressSymbol
    value: object


class _Resolver:
    def __init__(
        self, document: ExpressDocument, limits: ExpressResolutionLimits
    ) -> None:
        self.document = document
        self.limits = limits
        self.schemas = {schema.name.casefold(): schema for schema in document.schemas}
        self.symbols: list[ExpressSymbol] = []
        self.declarations: dict[str, _Declaration] = {}
        self.local_tables: dict[str, dict[str, str]] = {}
        self.visible_tables: dict[str, dict[str, list[str]]] = {}
        self.references: list[ExpressReferenceResolution] = []
        self.bounds: list[ExpressAggregateBoundResolution] = []
        self.diagnostics: list[ExpressResolutionDiagnostic] = []
        self._reference_keys: set[tuple[str, str, str, str, tuple[str, ...]]] = set()

    def resolve(self) -> ExpressResolvedDocument:
        self._index_symbols()
        self._build_visibility()
        self._collect_references_and_bounds()
        types = self._resolve_types()
        inheritance = self._resolve_inheritance()
        self._resolve_inverse_attributes(inheritance)
        diagnostics = tuple(self.diagnostics)
        reason = diagnostics[0].reason_code if diagnostics else "resolved"
        return ExpressResolvedDocument(
            decision="reject" if diagnostics else "accept",
            reason_code=reason,
            symbols=tuple(self.symbols),
            references=tuple(self.references),
            types=tuple(types),
            aggregate_bounds=tuple(self.bounds),
            inheritance=tuple(inheritance),
            diagnostics=diagnostics,
        )

    def _index_symbols(self) -> None:
        for schema in self.document.schemas:
            schema_key = schema.name.casefold()
            table: dict[str, str] = {}
            self._add_symbol(schema, schema.name, "schema", schema, table=None)
            for declaration, kind in self._schema_declarations(schema):
                self._add_symbol(
                    schema,
                    declaration.name,
                    kind,
                    declaration,
                    table=table,
                )
            self.local_tables[schema_key] = table

    def _add_symbol(
        self,
        schema: ExpressSchemaDeclaration,
        name: str,
        kind: ExpressSymbolKind,
        value: object,
        *,
        table: dict[str, str] | None,
    ) -> None:
        if len(self.symbols) >= self.limits.max_symbols:
            raise ExpressResolutionLimitError(
                "symbol_count_limit", "semantic graph exceeds the symbol limit"
            )
        symbol_id = (
            f"schema::{schema.name.casefold()}"
            if kind == "schema"
            else f"{schema.name.casefold()}::{name.casefold()}"
        )
        symbol = ExpressSymbol(
            symbol_id,
            schema.name,
            name,
            kind,
            value.span.start_line,
        )
        self.symbols.append(symbol)
        self.declarations[symbol_id] = _Declaration(symbol, value)
        if table is not None:
            table[name.casefold()] = symbol_id

    @staticmethod
    def _schema_declarations(
        schema: ExpressSchemaDeclaration,
    ) -> tuple[tuple[object, ExpressSymbolKind], ...]:
        declarations: list[tuple[object, ExpressSymbolKind]] = []
        declarations.extend((item, "type") for item in schema.types)
        declarations.extend((item, "entity") for item in schema.entities)
        declarations.extend((item, item.kind) for item in schema.algorithms)
        declarations.extend((item, "constant") for item in schema.constants)
        return tuple(declarations)

    def _build_visibility(self) -> None:
        for schema in self.document.schemas:
            schema_key = schema.name.casefold()
            visible = {
                name: [symbol_id]
                for name, symbol_id in self.local_tables[schema_key].items()
            }
            for interface in schema.interfaces:
                source_schema = self.schemas.get(interface.schema_name.casefold())
                owner_id = f"{schema_key}::<interface:{interface.span.start_line}>"
                if source_schema is None:
                    self._append_reference(
                        schema.name,
                        owner_id,
                        "interface_schema",
                        interface.schema_name,
                        ("schema",),
                        "unresolved",
                        None,
                        (),
                        interface.span.start_line,
                    )
                    self._diagnose(
                        "unresolved_interface_schema",
                        schema.name,
                        owner_id,
                        f"schema {interface.schema_name!r} is not present in the document",
                        interface.span.start_line,
                    )
                    continue
                schema_symbol_id = f"schema::{source_schema.name.casefold()}"
                self._append_reference(
                    schema.name,
                    owner_id,
                    "interface_schema",
                    interface.schema_name,
                    ("schema",),
                    "resolved",
                    schema_symbol_id,
                    (schema_symbol_id,),
                    interface.span.start_line,
                )
                source_table = self.local_tables[source_schema.name.casefold()]
                if interface.items:
                    requested = tuple(
                        (item.name, item.alias or item.name) for item in interface.items
                    )
                else:
                    requested = tuple(
                        (
                            self.declarations[symbol_id].symbol.name,
                            self.declarations[symbol_id].symbol.name,
                        )
                        for symbol_id in source_table.values()
                    )
                for source_name, local_name in requested:
                    symbol_id = source_table.get(source_name.casefold())
                    if symbol_id is None:
                        self._append_reference(
                            schema.name,
                            owner_id,
                            f"interface_{interface.kind}_item",
                            source_name,
                            self._interface_kinds(interface.kind),
                            "unresolved",
                            None,
                            (),
                            interface.span.start_line,
                        )
                        self._diagnose(
                            "unresolved_interface_item",
                            schema.name,
                            owner_id,
                            f"{source_name!r} is not declared directly by {source_schema.name!r}",
                            interface.span.start_line,
                        )
                        continue
                    symbol = self.declarations[symbol_id].symbol
                    expected = self._interface_kinds(interface.kind)
                    status: ExpressResolutionStatus = (
                        "resolved" if symbol.kind in expected else "invalid_kind"
                    )
                    self._append_reference(
                        schema.name,
                        owner_id,
                        f"interface_{interface.kind}_item",
                        source_name,
                        expected,
                        status,
                        symbol_id if status == "resolved" else None,
                        (symbol_id,),
                        interface.span.start_line,
                    )
                    if status == "invalid_kind":
                        self._diagnose(
                            "invalid_use_item_kind",
                            schema.name,
                            owner_id,
                            f"USE cannot import {symbol.kind} declaration {source_name!r}",
                            interface.span.start_line,
                        )
                        continue
                    candidates = visible.setdefault(local_name.casefold(), [])
                    if symbol_id not in candidates:
                        candidates.append(symbol_id)
            for local_name, candidates in visible.items():
                if len(candidates) > 1:
                    self._diagnose(
                        "ambiguous_visible_name",
                        schema.name,
                        f"{schema_key}::<scope>",
                        f"visible name {local_name!r} has candidates {', '.join(candidates)}",
                        schema.span.start_line,
                    )
            self.visible_tables[schema_key] = visible

    @staticmethod
    def _interface_kinds(
        kind: str,
    ) -> tuple[ExpressSymbolKind, ...]:
        if kind == "use":
            return ("type", "entity")
        return ("type", "entity", "constant", "function", "procedure")

    def _collect_references_and_bounds(self) -> None:
        for schema in self.document.schemas:
            for schema_type in schema.types:
                owner_id = self._symbol_id(schema.name, schema_type.name)
                self._walk_type_ref(
                    schema, owner_id, "type_underlying", schema_type.underlying_type
                )
            for entity in schema.entities:
                owner_id = self._symbol_id(schema.name, entity.name)
                for supertype in entity.supertypes:
                    self._lookup_reference(
                        schema,
                        owner_id,
                        "entity_supertype",
                        supertype,
                        ("entity",),
                        entity.span.start_line,
                    )
                for attribute in entity.attributes:
                    self._walk_type_ref(
                        schema,
                        owner_id,
                        f"attribute_{attribute.kind}:{attribute.name}",
                        attribute.type_ref,
                    )
            for constant in schema.constants:
                owner_id = self._symbol_id(schema.name, constant.name)
                self._walk_type_ref(
                    schema, owner_id, "constant_type", constant.type_ref
                )
            for algorithm in schema.algorithms:
                owner_id = self._symbol_id(schema.name, algorithm.name)
                for parameter in algorithm.parameters:
                    self._walk_type_ref(
                        schema,
                        owner_id,
                        f"parameter:{parameter.name}",
                        parameter.type_ref,
                    )
                if algorithm.return_type is not None:
                    self._walk_type_ref(
                        schema, owner_id, "function_return", algorithm.return_type
                    )
                for target in algorithm.applies_to:
                    self._lookup_reference(
                        schema,
                        owner_id,
                        "rule_target",
                        target,
                        ("entity",),
                        algorithm.span.start_line,
                    )

    def _walk_type_ref(
        self,
        schema: ExpressSchemaDeclaration,
        owner_id: str,
        role: str,
        type_ref: ExpressTypeReference,
    ) -> None:
        if type_ref.kind == "named" and type_ref.name is not None:
            self._lookup_reference(
                schema,
                owner_id,
                role,
                type_ref.name,
                ("type", "entity"),
                type_ref.span.start_line,
            )
        elif type_ref.kind == "select":
            for member in type_ref.members:
                self._lookup_reference(
                    schema,
                    owner_id,
                    "select_member",
                    member,
                    ("type", "entity"),
                    type_ref.span.start_line,
                )
        if type_ref.kind == "aggregate":
            self._evaluate_bounds(schema, owner_id, role, type_ref)
            if type_ref.element_type is not None:
                self._walk_type_ref(
                    schema, owner_id, f"{role}.element", type_ref.element_type
                )

    def _evaluate_bounds(
        self,
        schema: ExpressSchemaDeclaration,
        owner_id: str,
        role: str,
        type_ref: ExpressTypeReference,
    ) -> None:
        lower_status, lower_value = self._evaluate_bound(
            schema, owner_id, f"{role}.lower", type_ref.lower_bound, False, type_ref.span.start_line
        )
        upper_status, upper_value = self._evaluate_bound(
            schema, owner_id, f"{role}.upper", type_ref.upper_bound, True, type_ref.span.start_line
        )
        status: ExpressResolutionStatus = "resolved"
        if "deferred" in {lower_status, upper_status}:
            status = "deferred"
        elif "unresolved" in {lower_status, upper_status}:
            status = "unresolved"
        if lower_value is not None and upper_value is not None and lower_value > upper_value:
            status = "unresolved"
            self._diagnose(
                "invalid_aggregate_bound_order",
                schema.name,
                owner_id,
                f"aggregate lower bound {lower_value} exceeds upper bound {upper_value}",
                type_ref.span.start_line,
            )
        self.bounds.append(
            ExpressAggregateBoundResolution(
                schema.name,
                owner_id,
                role,
                str(type_ref.aggregate_kind),
                type_ref.lower_bound,
                type_ref.upper_bound,
                lower_status,
                upper_status,
                lower_value,
                upper_value,
                status,
            )
        )

    def _evaluate_bound(
        self,
        schema: ExpressSchemaDeclaration,
        owner_id: str,
        role: str,
        source: str | None,
        allow_unbounded: bool,
        source_line: int,
    ) -> tuple[str, int | None]:
        if source is None:
            return "omitted", None
        value = source.strip()
        if value == "?":
            if allow_unbounded:
                return "unbounded", None
            self._diagnose(
                "invalid_unbounded_lower_bound",
                schema.name,
                owner_id,
                "the controlled evaluator does not admit '?' as a lower bound",
                source_line,
            )
            return "unresolved", None
        if re.fullmatch(r"[+-]?\d+", value):
            return "integer_literal", int(value)
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", value):
            reference = self._lookup_reference(
                schema,
                owner_id,
                role,
                value,
                ("constant",),
                source_line,
            )
            if reference.status != "resolved" or reference.resolved_symbol_id is None:
                return "unresolved", None
            declaration = self.declarations[reference.resolved_symbol_id].value
            expression = declaration.expression.strip()
            if re.fullmatch(r"[+-]?\d+", expression):
                return "integer_constant", int(expression)
            self._diagnose(
                "non_integer_bound_constant",
                schema.name,
                owner_id,
                f"bound constant {value!r} is not an integer literal in the controlled evaluator",
                source_line,
            )
            return "unresolved", None
        return "deferred", None

    def _resolve_types(self) -> list[ExpressTypeResolution]:
        cache: dict[str, ExpressTypeResolution] = {}
        visiting: list[str] = []

        def resolve_type(symbol_id: str) -> ExpressTypeResolution:
            if symbol_id in cache:
                return cache[symbol_id]
            declaration = self.declarations[symbol_id]
            schema = self.schemas[declaration.symbol.schema_name.casefold()]
            if symbol_id in visiting:
                start = visiting.index(symbol_id)
                cycle = tuple(visiting[start:] + [symbol_id])
                self._diagnose(
                    "type_alias_cycle",
                    schema.name,
                    symbol_id,
                    "type alias cycle: " + " -> ".join(cycle),
                    declaration.symbol.source_line,
                )
                result = ExpressTypeResolution(
                    symbol_id,
                    schema.name,
                    declaration.symbol.name,
                    "cyclic",
                    None,
                    cycle,
                )
                cache[symbol_id] = result
                return result
            visiting.append(symbol_id)
            type_ref = declaration.value.underlying_type
            status: ExpressResolutionStatus = "resolved"
            terminal: str | None
            chain: tuple[str, ...] = (symbol_id,)
            if type_ref.kind == "simple":
                terminal = f"simple:{type_ref.name}"
            elif type_ref.kind == "enumeration":
                terminal = "enumeration"
            elif type_ref.kind == "select":
                terminal = "select"
                if any(
                    reference.status != "resolved"
                    for reference in self.references
                    if reference.owner_symbol_id == symbol_id
                    and reference.role == "select_member"
                ):
                    status = "unresolved"
            elif type_ref.kind == "aggregate":
                terminal = f"aggregate:{type_ref.aggregate_kind}"
                if any(
                    bound.owner_symbol_id == symbol_id
                    and bound.status == "unresolved"
                    for bound in self.bounds
                ):
                    status = "unresolved"
            elif type_ref.kind == "named" and type_ref.name is not None:
                reference = self._lookup_reference(
                    schema,
                    symbol_id,
                    "type_alias_target",
                    type_ref.name,
                    ("type",),
                    type_ref.span.start_line,
                )
                if reference.status != "resolved" or reference.resolved_symbol_id is None:
                    status = reference.status
                    terminal = None
                else:
                    target = resolve_type(reference.resolved_symbol_id)
                    status = target.status
                    terminal = target.terminal_domain
                    if target.status == "cyclic" and symbol_id in target.alias_chain[:-1]:
                        cycle = target.alias_chain[:-1]
                        offset = cycle.index(symbol_id)
                        rotated = cycle[offset:] + cycle[:offset]
                        chain = rotated + (symbol_id,)
                    else:
                        chain = (symbol_id,) + target.alias_chain
            else:
                status = "unresolved"
                terminal = None
            visiting.pop()
            result = ExpressTypeResolution(
                symbol_id,
                schema.name,
                declaration.symbol.name,
                status,
                terminal,
                chain,
            )
            cache[symbol_id] = result
            return result

        type_ids = [symbol.symbol_id for symbol in self.symbols if symbol.kind == "type"]
        return [resolve_type(symbol_id) for symbol_id in type_ids]

    def _resolve_inheritance(self) -> list[ExpressInheritanceResolution]:
        entity_ids = [
            symbol.symbol_id for symbol in self.symbols if symbol.kind == "entity"
        ]
        direct: dict[str, list[str]] = {symbol_id: [] for symbol_id in entity_ids}
        for symbol_id in entity_ids:
            declaration = self.declarations[symbol_id]
            schema = self.schemas[declaration.symbol.schema_name.casefold()]
            entity: ExpressEntityDeclaration = declaration.value
            for supertype in entity.supertypes:
                reference = self._lookup_reference(
                    schema,
                    symbol_id,
                    "entity_supertype",
                    supertype,
                    ("entity",),
                    entity.span.start_line,
                )
                if reference.status == "resolved" and reference.resolved_symbol_id:
                    direct[symbol_id].append(reference.resolved_symbol_id)
                    if sum(len(items) for items in direct.values()) > self.limits.max_inheritance_edges:
                        raise ExpressResolutionLimitError(
                            "inheritance_edge_limit",
                            "semantic graph exceeds the inheritance edge limit",
                        )

        cycle_nodes: set[str] = set()
        state: dict[str, int] = {}
        stack: list[str] = []

        def detect(symbol_id: str) -> None:
            state[symbol_id] = 1
            stack.append(symbol_id)
            for parent_id in direct[symbol_id]:
                if state.get(parent_id, 0) == 0:
                    detect(parent_id)
                elif state.get(parent_id) == 1:
                    start = stack.index(parent_id)
                    cycle = stack[start:] + [parent_id]
                    cycle_nodes.update(cycle)
                    self._diagnose(
                        "inheritance_cycle",
                        self.declarations[symbol_id].symbol.schema_name,
                        symbol_id,
                        "inheritance cycle: " + " -> ".join(cycle),
                        self.declarations[symbol_id].symbol.source_line,
                    )
            stack.pop()
            state[symbol_id] = 2

        for symbol_id in entity_ids:
            if state.get(symbol_id, 0) == 0:
                detect(symbol_id)

        transitive_cache: dict[str, tuple[str, ...]] = {}

        def transitive(symbol_id: str, active: set[str] | None = None) -> tuple[str, ...]:
            if symbol_id in transitive_cache:
                return transitive_cache[symbol_id]
            active = set() if active is None else set(active)
            if symbol_id in active:
                return ()
            active.add(symbol_id)
            ordered: list[str] = []
            for parent_id in direct[symbol_id]:
                for ancestor_id in (*transitive(parent_id, active), parent_id):
                    if ancestor_id not in ordered:
                        ordered.append(ancestor_id)
            transitive_cache[symbol_id] = tuple(ordered)
            return tuple(ordered)

        results: list[ExpressInheritanceResolution] = []
        for symbol_id in entity_ids:
            declaration = self.declarations[symbol_id]
            entity: ExpressEntityDeclaration = declaration.value
            missing_super = any(
                reference.owner_symbol_id == symbol_id
                and reference.role == "entity_supertype"
                and reference.status != "resolved"
                for reference in self.references
            )
            ancestors = () if symbol_id in cycle_nodes else transitive(symbol_id)
            inherited: dict[str, list[str]] = {}
            for ancestor_id in ancestors:
                ancestor: ExpressEntityDeclaration = self.declarations[ancestor_id].value
                for attribute in ancestor.attributes:
                    origin = self._attribute_id(ancestor_id, attribute.name)
                    candidates = inherited.setdefault(attribute.name.casefold(), [])
                    if origin not in candidates:
                        candidates.append(origin)
            redeclared_count = 0
            for attribute in entity.attributes:
                name_key = attribute.name.casefold()
                if attribute.redeclared_from is not None:
                    target = self._resolve_redeclaration(
                        symbol_id, entity, attribute, ancestors
                    )
                    if target:
                        redeclared_count += 1
                        inherited.pop(name_key, None)
                elif name_key in inherited:
                    self._diagnose(
                        "unqualified_attribute_redeclaration",
                        declaration.symbol.schema_name,
                        symbol_id,
                        f"attribute {attribute.name!r} hides an inherited name without SELF qualification",
                        attribute.span.start_line,
                    )
            for name, origins in inherited.items():
                if len(origins) > 1:
                    self._diagnose(
                        "inherited_attribute_ambiguity",
                        declaration.symbol.schema_name,
                        symbol_id,
                        f"inherited attribute {name!r} has origins {', '.join(origins)}",
                        entity.span.start_line,
                    )
            inherited_count = sum(len(origins) for origins in inherited.values())
            if symbol_id in cycle_nodes:
                status: ExpressResolutionStatus = "cyclic"
            elif missing_super:
                status = "unresolved"
            elif any(
                diagnostic.owner_symbol_id == symbol_id
                and diagnostic.reason_code
                in {
                    "unqualified_attribute_redeclaration",
                    "invalid_attribute_redeclaration",
                    "inherited_attribute_ambiguity",
                }
                for diagnostic in self.diagnostics
            ):
                status = "ambiguous"
            else:
                status = "resolved"
            results.append(
                ExpressInheritanceResolution(
                    symbol_id,
                    declaration.symbol.schema_name,
                    declaration.symbol.name,
                    status,
                    tuple(direct[symbol_id]),
                    ancestors,
                    len(entity.attributes),
                    inherited_count,
                    inherited_count + len(entity.attributes),
                    redeclared_count,
                )
            )
        return results

    def _resolve_redeclaration(
        self,
        entity_id: str,
        entity: ExpressEntityDeclaration,
        attribute: ExpressAttribute,
        ancestors: tuple[str, ...],
    ) -> bool:
        candidates = [
            ancestor_id
            for ancestor_id in ancestors
            if self.declarations[ancestor_id].symbol.name.casefold()
            == str(attribute.redeclared_from).casefold()
        ]
        valid = False
        if len(candidates) == 1:
            target_id = candidates[0]
            target: ExpressEntityDeclaration = self.declarations[target_id].value
            valid = any(
                item.name.casefold() == attribute.name.casefold()
                for item in target.attributes
            )
        if not valid:
            self._diagnose(
                "invalid_attribute_redeclaration",
                self.declarations[entity_id].symbol.schema_name,
                entity_id,
                f"SELF\\{attribute.redeclared_from}.{attribute.name} does not identify a direct declaration in an ancestor",
                attribute.span.start_line,
            )
        return valid

    def _resolve_inverse_attributes(
        self, inheritance: list[ExpressInheritanceResolution]
    ) -> None:
        inheritance_by_id = {item.symbol_id: item for item in inheritance}
        for symbol in self.symbols:
            if symbol.kind != "entity":
                continue
            entity: ExpressEntityDeclaration = self.declarations[symbol.symbol_id].value
            schema = self.schemas[symbol.schema_name.casefold()]
            for attribute in entity.attributes:
                if attribute.kind != "inverse" or attribute.inverse_for is None:
                    continue
                named = self._innermost_named(attribute.type_ref)
                role = f"inverse_for_attribute:{attribute.name}"
                if named is None:
                    self._append_reference(
                        schema.name,
                        symbol.symbol_id,
                        role,
                        attribute.inverse_for,
                        (),
                        "unresolved",
                        None,
                        (),
                        attribute.span.start_line,
                    )
                    self._diagnose(
                        "inverse_target_not_entity",
                        schema.name,
                        symbol.symbol_id,
                        f"inverse attribute {attribute.name!r} has no directly named entity target",
                        attribute.span.start_line,
                    )
                    continue
                target_ref = self._lookup_reference(
                    schema,
                    symbol.symbol_id,
                    f"attribute_inverse:{attribute.name}.target",
                    named,
                    ("entity",),
                    attribute.span.start_line,
                )
                target_id = target_ref.resolved_symbol_id
                candidate_ids: tuple[str, ...] = ()
                if target_id is not None:
                    target_entity: ExpressEntityDeclaration = self.declarations[target_id].value
                    candidates: list[str] = []
                    search_ids = (
                        *inheritance_by_id[target_id].transitive_supertype_ids,
                        target_id,
                    )
                    for search_id in search_ids:
                        search_entity: ExpressEntityDeclaration = self.declarations[search_id].value
                        for forward in search_entity.attributes:
                            if forward.name.casefold() == attribute.inverse_for.casefold():
                                candidates.append(self._attribute_id(search_id, forward.name))
                    candidate_ids = tuple(dict.fromkeys(candidates))
                if len(candidate_ids) == 1:
                    status: ExpressResolutionStatus = "resolved"
                    resolved_id = candidate_ids[0]
                elif len(candidate_ids) > 1:
                    status = "ambiguous"
                    resolved_id = None
                else:
                    status = "unresolved"
                    resolved_id = None
                self._append_reference(
                    schema.name,
                    symbol.symbol_id,
                    role,
                    attribute.inverse_for,
                    (),
                    status,
                    resolved_id,
                    candidate_ids,
                    attribute.span.start_line,
                )
                if status != "resolved":
                    self._diagnose(
                        "unresolved_inverse_attribute",
                        schema.name,
                        symbol.symbol_id,
                        f"inverse target attribute {attribute.inverse_for!r} is {status}",
                        attribute.span.start_line,
                    )

    @staticmethod
    def _innermost_named(type_ref: ExpressTypeReference) -> str | None:
        current = type_ref
        while current.kind == "aggregate" and current.element_type is not None:
            current = current.element_type
        return current.name if current.kind == "named" else None

    def _lookup_reference(
        self,
        schema: ExpressSchemaDeclaration,
        owner_id: str,
        role: str,
        source_name: str,
        expected_kinds: tuple[ExpressSymbolKind, ...],
        source_line: int,
    ) -> ExpressReferenceResolution:
        key = (
            schema.name.casefold(),
            owner_id,
            role,
            source_name.casefold(),
            expected_kinds,
        )
        for reference in self.references:
            existing_key = (
                reference.schema_name.casefold(),
                reference.owner_symbol_id,
                reference.role,
                reference.source_name.casefold(),
                reference.expected_kinds,
            )
            if existing_key == key:
                return reference
        candidates = tuple(
            self.visible_tables.get(schema.name.casefold(), {}).get(
                source_name.casefold(), []
            )
        )
        matching = tuple(
            symbol_id
            for symbol_id in candidates
            if self.declarations[symbol_id].symbol.kind in expected_kinds
        )
        if not candidates:
            status: ExpressResolutionStatus = "unresolved"
            resolved = None
        elif not matching:
            status = "invalid_kind"
            resolved = None
        elif len(matching) > 1 or len(candidates) > 1:
            status = "ambiguous"
            resolved = None
        else:
            status = "resolved"
            resolved = matching[0]
        reference = self._append_reference(
            schema.name,
            owner_id,
            role,
            source_name,
            expected_kinds,
            status,
            resolved,
            candidates,
            source_line,
        )
        if status != "resolved":
            self._diagnose(
                f"{status}_reference",
                schema.name,
                owner_id,
                f"{role} name {source_name!r} is {status}",
                source_line,
            )
        return reference

    def _append_reference(
        self,
        schema_name: str,
        owner_id: str,
        role: str,
        source_name: str,
        expected_kinds: tuple[ExpressSymbolKind, ...],
        status: ExpressResolutionStatus,
        resolved_symbol_id: str | None,
        candidate_symbol_ids: tuple[str, ...],
        source_line: int,
    ) -> ExpressReferenceResolution:
        key = (
            schema_name.casefold(),
            owner_id,
            role,
            source_name.casefold(),
            expected_kinds,
        )
        if key in self._reference_keys:
            return next(
                reference
                for reference in self.references
                if (
                    reference.schema_name.casefold(),
                    reference.owner_symbol_id,
                    reference.role,
                    reference.source_name.casefold(),
                    reference.expected_kinds,
                )
                == key
            )
        if len(self.references) >= self.limits.max_references:
            raise ExpressResolutionLimitError(
                "reference_count_limit", "semantic graph exceeds the reference limit"
            )
        reference = ExpressReferenceResolution(
            schema_name,
            owner_id,
            role,
            source_name,
            expected_kinds,
            status,
            resolved_symbol_id,
            candidate_symbol_ids,
            source_line,
        )
        self.references.append(reference)
        self._reference_keys.add(key)
        return reference

    def _diagnose(
        self,
        reason_code: str,
        schema_name: str,
        owner_symbol_id: str,
        detail: str,
        source_line: int,
    ) -> None:
        diagnostic = ExpressResolutionDiagnostic(
            reason_code, schema_name, owner_symbol_id, detail, source_line
        )
        if diagnostic not in self.diagnostics:
            self.diagnostics.append(diagnostic)

    @staticmethod
    def _symbol_id(schema_name: str, name: str) -> str:
        return f"{schema_name.casefold()}::{name.casefold()}"

    @staticmethod
    def _attribute_id(entity_id: str, name: str) -> str:
        return f"{entity_id}::attribute::{name.casefold()}"


def resolve_express_document(
    document: ExpressDocument,
    *,
    limits: ExpressResolutionLimits = DEFAULT_EXPRESS_RESOLUTION_LIMITS,
) -> ExpressResolvedDocument:
    """Resolve a parsed document using bounded, case-insensitive direct imports."""
    if not isinstance(document, ExpressDocument):
        raise TypeError("document must be an ExpressDocument")
    if not isinstance(limits, ExpressResolutionLimits):
        raise TypeError("limits must be ExpressResolutionLimits")
    return _Resolver(document, limits).resolve()
