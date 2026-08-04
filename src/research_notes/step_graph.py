"""Deterministic, bounded graph queries over parsed STEP Part 21 instances."""

from __future__ import annotations

import hashlib
import json
from collections import deque
from dataclasses import dataclass, replace
from typing import Literal, Sequence

from research_notes.step_part21 import (
    DEFAULT_STEP_PARSE_LIMITS,
    STEPParseLimits,
    Part21Document,
    Part21SourceSpan,
    Part21Value,
    parse_part21_document,
)


STEPGraphDirection = Literal["forward", "reverse"]
STEPGraphTargetScope = Literal[
    "local_entity", "external_entity", "external_value", "schema_constant", "unresolved"
]


@dataclass(frozen=True)
class STEPGraphLimits:
    """Explicit construction and query budgets for one graph."""

    max_nodes: int = 20_000
    max_edges: int = 100_000
    max_query_results: int = 20_000
    max_traversal_visits: int = 20_000
    max_traversal_depth: int = 64

    def __post_init__(self) -> None:
        for field_name, value in vars(self).items():
            if value <= 0:
                raise ValueError(f"{field_name} must be positive")


DEFAULT_STEP_GRAPH_LIMITS = STEPGraphLimits()


class STEPGraphLimitError(RuntimeError):
    """A stable failure when graph construction or a complete query exceeds a budget."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


@dataclass(frozen=True)
class STEPGraphNode:
    """One analysis-local node backed by a DATA-section entity instance."""

    node_index: int
    entity_id: int
    section_index: int
    section_name: str | None
    schema_identifier: str
    record_types: tuple[str, ...]
    is_complex: bool
    source_span: Part21SourceSpan
    outbound_edge_indices: tuple[int, ...] = ()
    inbound_edge_indices: tuple[int, ...] = ()


@dataclass(frozen=True)
class STEPGraphEdge:
    """One reference occurrence retained with its parameter path and source span."""

    edge_index: int
    source_node_index: int
    source_entity_id: int
    target_node_index: int | None
    target_entity_id: int | None
    target_occurrence: str
    target_scope: STEPGraphTargetScope
    reference_kind: Literal["entity", "value", "constant"]
    record_index: int
    parameter_path: tuple[int, ...]
    source_span: Part21SourceSpan

    @property
    def is_local(self) -> bool:
        """Return whether this edge resolves to a node in the same exchange structure."""
        return self.target_scope == "local_entity"


@dataclass(frozen=True)
class STEPGraphVisit:
    """One breadth-first traversal visit with a reproducible predecessor."""

    visit_index: int
    node_index: int
    entity_id: int
    depth: int
    predecessor_entity_id: int | None
    via_edge_index: int | None


@dataclass(frozen=True)
class STEPGraphTraversal:
    """A bounded traversal result that distinguishes complete and partial evidence."""

    direction: STEPGraphDirection
    start_entity_ids: tuple[int, ...]
    visits: tuple[STEPGraphVisit, ...]
    traversed_edge_count: int
    complete: bool
    reason_code: str

    @property
    def entity_ids(self) -> tuple[int, ...]:
        """Return visited Part 21 entity identifiers in breadth-first order."""
        return tuple(visit.entity_id for visit in self.visits)


@dataclass(frozen=True)
class STEPGraph:
    """A source-linked directed multigraph over Part 21 entity references."""

    format_version: str
    source_sha256: str
    schema_identifiers: tuple[str, ...]
    nodes: tuple[STEPGraphNode, ...]
    edges: tuple[STEPGraphEdge, ...]
    limits: STEPGraphLimits

    def node(self, entity_id: int) -> STEPGraphNode:
        """Return one node by its Part 21 entity identifier."""
        _validate_entity_id(entity_id)
        for node in self.nodes:
            if node.entity_id == entity_id:
                return node
        raise KeyError(f"entity #{entity_id} is not present in the graph")

    def nodes_of_type(self, type_name: str) -> tuple[STEPGraphNode, ...]:
        """Return nodes containing an exact simple or complex record type."""
        if not isinstance(type_name, str) or not type_name.strip():
            raise TypeError("type_name must be a non-empty string")
        normalized = type_name.upper()
        matches = tuple(
            node for node in self.nodes if normalized in node.record_types
        )
        self._require_query_capacity(len(matches))
        return matches

    def outbound(self, entity_id: int) -> tuple[STEPGraphEdge, ...]:
        """Return every reference occurrence emitted by one entity."""
        node = self.node(entity_id)
        return tuple(self.edges[index] for index in node.outbound_edge_indices)

    def inbound(self, entity_id: int) -> tuple[STEPGraphEdge, ...]:
        """Return local entity-reference occurrences targeting one entity."""
        node = self.node(entity_id)
        return tuple(self.edges[index] for index in node.inbound_edge_indices)

    def root_nodes(self) -> tuple[STEPGraphNode, ...]:
        """Return nodes with no incoming local entity-reference occurrences."""
        roots = tuple(node for node in self.nodes if not node.inbound_edge_indices)
        self._require_query_capacity(len(roots))
        return roots

    def isolated_nodes(self) -> tuple[STEPGraphNode, ...]:
        """Return nodes with neither incoming nor outgoing local entity references."""
        isolated = tuple(
            node
            for node in self.nodes
            if not node.inbound_edge_indices
            and not any(edge.is_local for edge in self.outbound(node.entity_id))
        )
        self._require_query_capacity(len(isolated))
        return isolated

    def traverse(
        self,
        start_entity_ids: Sequence[int],
        *,
        direction: STEPGraphDirection = "forward",
        max_depth: int | None = None,
    ) -> STEPGraphTraversal:
        """Traverse local references breadth first within explicit depth and visit limits."""
        if isinstance(start_entity_ids, (str, bytes)) or not isinstance(
            start_entity_ids, Sequence
        ):
            raise TypeError("start_entity_ids must be a sequence of integers")
        if direction not in {"forward", "reverse"}:
            raise ValueError("direction must be 'forward' or 'reverse'")
        depth_limit = self.limits.max_traversal_depth if max_depth is None else max_depth
        if not isinstance(depth_limit, int) or isinstance(depth_limit, bool):
            raise TypeError("max_depth must be an integer or None")
        if depth_limit < 0 or depth_limit > self.limits.max_traversal_depth:
            raise ValueError(
                "max_depth must be between zero and the configured traversal depth"
            )
        starts: list[int] = []
        seen_starts: set[int] = set()
        for entity_id in start_entity_ids:
            _validate_entity_id(entity_id)
            self.node(entity_id)
            if entity_id not in seen_starts:
                seen_starts.add(entity_id)
                starts.append(entity_id)
        if not starts:
            raise ValueError("start_entity_ids must not be empty")
        capacity = min(
            self.limits.max_query_results, self.limits.max_traversal_visits
        )
        if len(starts) > capacity:
            raise STEPGraphLimitError(
                "traversal_visit_limit",
                "start nodes exceed the configured traversal result budget",
            )

        node_by_id = {node.entity_id: node for node in self.nodes}
        visited = set(starts)
        queue = deque((entity_id, 0, None, None) for entity_id in starts)
        visits: list[STEPGraphVisit] = []
        traversed_edges: set[int] = set()
        complete = True
        reason_code = "traversal_complete"

        while queue:
            entity_id, depth, predecessor, via_edge = queue.popleft()
            node = node_by_id[entity_id]
            visits.append(
                STEPGraphVisit(
                    len(visits),
                    node.node_index,
                    entity_id,
                    depth,
                    predecessor,
                    via_edge,
                )
            )
            edges = (
                self.outbound(entity_id)
                if direction == "forward"
                else self.inbound(entity_id)
            )
            local_neighbors: list[tuple[int, int]] = []
            for edge in edges:
                if not edge.is_local:
                    continue
                traversed_edges.add(edge.edge_index)
                neighbor = (
                    edge.target_entity_id
                    if direction == "forward"
                    else edge.source_entity_id
                )
                assert neighbor is not None
                local_neighbors.append((neighbor, edge.edge_index))
            unseen = [item for item in local_neighbors if item[0] not in visited]
            if depth >= depth_limit:
                if unseen and complete:
                    complete = False
                    reason_code = "traversal_depth_limit"
                continue
            for neighbor, edge_index in unseen:
                if neighbor in visited:
                    continue
                if len(visited) >= capacity:
                    if complete:
                        complete = False
                        reason_code = "traversal_visit_limit"
                    continue
                visited.add(neighbor)
                queue.append((neighbor, depth + 1, entity_id, edge_index))

        return STEPGraphTraversal(
            direction,
            tuple(starts),
            tuple(visits),
            len(traversed_edges),
            complete,
            reason_code,
        )

    def orphaned_from(
        self, root_entity_ids: Sequence[int]
    ) -> tuple[STEPGraphNode, ...]:
        """Return nodes unreachable from caller-declared roots after a complete query."""
        traversal = self.traverse(root_entity_ids)
        if not traversal.complete:
            raise STEPGraphLimitError(
                traversal.reason_code,
                "orphan classification requires a complete forward traversal",
            )
        reached = set(traversal.entity_ids)
        orphans = tuple(node for node in self.nodes if node.entity_id not in reached)
        self._require_query_capacity(len(orphans))
        return orphans

    def cyclic_components(self) -> tuple[tuple[int, ...], ...]:
        """Return deterministic strongly connected local components that contain cycles."""
        if len(self.nodes) > self.limits.max_traversal_visits:
            raise STEPGraphLimitError(
                "cycle_visit_limit",
                "complete cycle analysis exceeds the configured visit budget",
            )
        adjacency = self._adjacency("forward")
        reverse = self._adjacency("reverse")
        finish: list[int] = []
        visited: set[int] = set()

        for node in self.nodes:
            if node.entity_id in visited:
                continue
            visited.add(node.entity_id)
            stack: list[tuple[int, int]] = [(node.entity_id, 0)]
            while stack:
                entity_id, offset = stack[-1]
                neighbors = adjacency[entity_id]
                if offset < len(neighbors):
                    neighbor = neighbors[offset]
                    stack[-1] = (entity_id, offset + 1)
                    if neighbor not in visited:
                        visited.add(neighbor)
                        stack.append((neighbor, 0))
                else:
                    finish.append(entity_id)
                    stack.pop()

        assigned: set[int] = set()
        components: list[tuple[int, ...]] = []
        node_index = {node.entity_id: node.node_index for node in self.nodes}
        self_loops = {
            edge.source_entity_id
            for edge in self.edges
            if edge.is_local and edge.source_entity_id == edge.target_entity_id
        }
        for start in reversed(finish):
            if start in assigned:
                continue
            assigned.add(start)
            component: list[int] = []
            stack = [start]
            while stack:
                entity_id = stack.pop()
                component.append(entity_id)
                for neighbor in reversed(reverse[entity_id]):
                    if neighbor not in assigned:
                        assigned.add(neighbor)
                        stack.append(neighbor)
            component.sort(key=node_index.__getitem__)
            if len(component) > 1 or component[0] in self_loops:
                components.append(tuple(component))
        components.sort(key=lambda item: node_index[item[0]])
        self._require_query_capacity(len(components))
        return tuple(components)

    def to_record(self) -> dict[str, object]:
        """Return a versioned JSON-compatible graph record without local paths."""
        return {
            "record_type": "research-notes.step-graph",
            "format_version": self.format_version,
            "source_sha256": self.source_sha256,
            "schema_identifiers": list(self.schema_identifiers),
            "limits": {
                "max_nodes": self.limits.max_nodes,
                "max_edges": self.limits.max_edges,
                "max_query_results": self.limits.max_query_results,
                "max_traversal_visits": self.limits.max_traversal_visits,
                "max_traversal_depth": self.limits.max_traversal_depth,
            },
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "nodes": [self._node_record(node) for node in self.nodes],
            "edges": [self._edge_record(edge) for edge in self.edges],
        }

    def to_json(self) -> str:
        """Serialize the versioned graph record deterministically as UTF-8 JSON text."""
        return json.dumps(
            self.to_record(), ensure_ascii=False, indent=2, sort_keys=True
        ) + "\n"

    def _adjacency(self, direction: STEPGraphDirection) -> dict[int, tuple[int, ...]]:
        adjacency: dict[int, list[int]] = {
            node.entity_id: [] for node in self.nodes
        }
        for edge in self.edges:
            if not edge.is_local:
                continue
            assert edge.target_entity_id is not None
            source = (
                edge.source_entity_id
                if direction == "forward"
                else edge.target_entity_id
            )
            target = (
                edge.target_entity_id
                if direction == "forward"
                else edge.source_entity_id
            )
            if target not in adjacency[source]:
                adjacency[source].append(target)
        return {key: tuple(value) for key, value in adjacency.items()}

    def _require_query_capacity(self, count: int) -> None:
        if count > self.limits.max_query_results:
            raise STEPGraphLimitError(
                "query_result_limit",
                "query results exceed the configured result budget",
            )

    @staticmethod
    def _node_record(node: STEPGraphNode) -> dict[str, object]:
        return {
            "node_index": node.node_index,
            "entity_id": node.entity_id,
            "section_index": node.section_index,
            "section_name": node.section_name,
            "schema_identifier": node.schema_identifier,
            "record_types": list(node.record_types),
            "is_complex": node.is_complex,
            "outbound_edge_indices": list(node.outbound_edge_indices),
            "inbound_edge_indices": list(node.inbound_edge_indices),
            "source_span": _span_record(node.source_span),
        }

    @staticmethod
    def _edge_record(edge: STEPGraphEdge) -> dict[str, object]:
        return {
            "edge_index": edge.edge_index,
            "source_node_index": edge.source_node_index,
            "source_entity_id": edge.source_entity_id,
            "target_node_index": edge.target_node_index,
            "target_entity_id": edge.target_entity_id,
            "target_occurrence": edge.target_occurrence,
            "target_scope": edge.target_scope,
            "reference_kind": edge.reference_kind,
            "record_index": edge.record_index,
            "parameter_path": list(edge.parameter_path),
            "source_span": _span_record(edge.source_span),
        }


def build_step_graph(
    source_bytes: bytes,
    *,
    parse_limits: STEPParseLimits = DEFAULT_STEP_PARSE_LIMITS,
    graph_limits: STEPGraphLimits = DEFAULT_STEP_GRAPH_LIMITS,
) -> STEPGraph:
    """Build a deterministic graph over every Part 21 DATA entity and reference."""
    if not isinstance(source_bytes, bytes):
        raise TypeError("source_bytes must be bytes")
    if not isinstance(parse_limits, STEPParseLimits):
        raise TypeError("parse_limits must be STEPParseLimits")
    if not isinstance(graph_limits, STEPGraphLimits):
        raise TypeError("graph_limits must be STEPGraphLimits")
    document = parse_part21_document(source_bytes, limits=parse_limits)
    return _build_from_document(source_bytes, document, graph_limits)


def _build_from_document(
    source_bytes: bytes,
    document: Part21Document,
    limits: STEPGraphLimits,
) -> STEPGraph:
    entities = [
        (section_index, section, entity)
        for section_index, section in enumerate(document.data_sections)
        for entity in section.entities
    ]
    if len(entities) > limits.max_nodes:
        raise STEPGraphLimitError(
            "graph_node_limit", "entity count exceeds the configured graph node budget"
        )
    nodes: list[STEPGraphNode] = []
    node_index_by_id: dict[int, int] = {}
    for node_index, (section_index, section, entity) in enumerate(entities):
        schema_identifier = section.schema_identifier
        if schema_identifier is None:
            schema_identifier = document.schema_identifiers[0]
        node_index_by_id[entity.entity_id] = node_index
        nodes.append(
            STEPGraphNode(
                node_index,
                entity.entity_id,
                section_index,
                section.name,
                schema_identifier,
                tuple(record.type_name for record in entity.records),
                entity.is_complex,
                entity.span,
            )
        )

    external_by_name = {
        reference.occurrence_name: reference for reference in document.external_references
    }
    edges: list[STEPGraphEdge] = []
    outbound: dict[int, list[int]] = {node.node_index: [] for node in nodes}
    inbound: dict[int, list[int]] = {node.node_index: [] for node in nodes}
    for node, (_, _, entity) in zip(nodes, entities, strict=True):
        for record_index, record in enumerate(entity.records):
            for parameter_index, argument in enumerate(record.arguments):
                for path, value in _reference_values(argument, (parameter_index,)):
                    if len(edges) >= limits.max_edges:
                        raise STEPGraphLimitError(
                            "graph_edge_limit",
                            "reference count exceeds the configured graph edge budget",
                        )
                    occurrence = str(value.value)
                    target_node_index: int | None = None
                    target_entity_id: int | None = None
                    if value.kind == "entity_reference":
                        reference_kind: Literal["entity", "value", "constant"] = (
                            "entity"
                        )
                        target_entity_id = int(occurrence[1:])
                        if target_entity_id in node_index_by_id:
                            target_scope: STEPGraphTargetScope = "local_entity"
                            target_node_index = node_index_by_id[target_entity_id]
                        elif occurrence in external_by_name:
                            target_scope = "external_entity"
                        else:
                            target_scope = "unresolved"
                    elif value.kind == "value_reference":
                        reference_kind = "value"
                        target_scope = (
                            "external_value"
                            if occurrence in external_by_name
                            else "unresolved"
                        )
                    else:
                        reference_kind = "constant"
                        target_scope = "schema_constant"
                    edge_index = len(edges)
                    edge = STEPGraphEdge(
                        edge_index,
                        node.node_index,
                        node.entity_id,
                        target_node_index,
                        target_entity_id,
                        occurrence,
                        target_scope,
                        reference_kind,
                        record_index,
                        path,
                        value.span,
                    )
                    edges.append(edge)
                    outbound[node.node_index].append(edge_index)
                    if target_node_index is not None:
                        inbound[target_node_index].append(edge_index)

    nodes = [
        replace(
            node,
            outbound_edge_indices=tuple(outbound[node.node_index]),
            inbound_edge_indices=tuple(inbound[node.node_index]),
        )
        for node in nodes
    ]
    return STEPGraph(
        "1.0",
        hashlib.sha256(source_bytes).hexdigest(),
        document.schema_identifiers,
        tuple(nodes),
        tuple(edges),
        limits,
    )


def _reference_values(
    value: Part21Value, path: tuple[int, ...]
) -> tuple[tuple[tuple[int, ...], Part21Value], ...]:
    references: list[tuple[tuple[int, ...], Part21Value]] = []
    stack = [(value, path)]
    while stack:
        current, current_path = stack.pop()
        if current.kind in {
            "entity_reference",
            "value_reference",
            "constant_reference",
        }:
            references.append((current_path, current))
        for child_index in range(len(current.children) - 1, -1, -1):
            stack.append(
                (current.children[child_index], current_path + (child_index,))
            )
    return tuple(references)


def _validate_entity_id(entity_id: int) -> None:
    if not isinstance(entity_id, int) or isinstance(entity_id, bool):
        raise TypeError("entity identifiers must be integers")
    if entity_id <= 0:
        raise ValueError("entity identifiers must be positive")


def _span_record(span: Part21SourceSpan) -> dict[str, int]:
    return {
        "start_offset": span.start_offset,
        "end_offset": span.end_offset,
        "start_byte": span.start_byte,
        "end_byte": span.end_byte,
        "start_line": span.start_line,
        "start_column": span.start_column,
        "end_line": span.end_line,
        "end_column": span.end_column,
    }
