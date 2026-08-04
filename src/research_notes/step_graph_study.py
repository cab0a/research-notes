"""Deterministic STEP graph fixtures and observations for v0.28."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from research_notes.step_graph import (
    DEFAULT_STEP_GRAPH_LIMITS,
    STEPGraph,
    STEPGraphLimitError,
    STEPGraphLimits,
    STEPGraphTraversal,
    build_step_graph,
)
from research_notes.step_part21 import Part21ParseError


@dataclass(frozen=True)
class STEPGraphFixture:
    """One synthetic graph fixture with its expected construction route."""

    fixture: str
    category: str
    condition: str
    file_name: str
    expected_decision: Literal["accept", "quarantine", "reject"]
    expected_reason_code: str
    root_entity_ids: tuple[int, ...]
    source_bytes: bytes
    graph_limits: STEPGraphLimits = DEFAULT_STEP_GRAPH_LIMITS
    query_max_depth: int | None = None


@dataclass(frozen=True)
class STEPGraphObservation:
    """One fixture-level graph construction and query observation."""

    decision: Literal["accept", "quarantine", "reject"]
    reason_code: str
    node_count: int
    edge_count: int
    local_edge_count: int
    external_edge_count: int
    unresolved_edge_count: int
    constant_edge_count: int
    root_count: int
    isolated_count: int
    cyclic_component_count: int
    traversal_complete: bool | None
    traversal_reason_code: str
    reachable_count: int
    orphan_count: int | None
    graph: STEPGraph | None
    traversal: STEPGraphTraversal | None


def _exchange(
    data_text: str,
    *,
    schemas: tuple[str, ...] = ("DEMO",),
    pre_data: str = "",
) -> bytes:
    schema_values = ",".join(f"'{schema}'" for schema in schemas)
    return f"""ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('Controlled generic STEP graph fixture'),'4;3');
FILE_NAME('fixture.step','2026-01-01T00:00:00',('research-notes'),('research-notes'),'','','');
FILE_SCHEMA(({schema_values}));
ENDSEC;
{pre_data}{data_text.strip()}
END-ISO-10303-21;
""".encode("utf-8")


def _fixture(
    fixture: str,
    category: str,
    condition: str,
    data_text: str,
    *,
    expected_decision: Literal["accept", "quarantine", "reject"] = "accept",
    expected_reason_code: str = "graph_constructed",
    root_entity_ids: tuple[int, ...] = (1,),
    schemas: tuple[str, ...] = ("DEMO",),
    pre_data: str = "",
    graph_limits: STEPGraphLimits = DEFAULT_STEP_GRAPH_LIMITS,
    query_max_depth: int | None = None,
) -> STEPGraphFixture:
    return STEPGraphFixture(
        fixture,
        category,
        condition,
        f"{fixture}.step",
        expected_decision,
        expected_reason_code,
        root_entity_ids,
        _exchange(data_text, schemas=schemas, pre_data=pre_data),
        graph_limits,
        query_max_depth,
    )


def build_step_graph_fixtures() -> tuple[STEPGraphFixture, ...]:
    """Build the complete deterministic v0.28 graph corpus."""
    return (
        _fixture(
            "branching_orphan",
            "reachability",
            "branching graph with one root-relative orphan",
            """DATA;
#1=ROOT((#2,#3));
#2=LEAF();
#3=BRANCH(#4);
#4=LEAF();
#99=ORPHAN();
ENDSEC;""",
        ),
        _fixture(
            "directed_cycles",
            "cycles",
            "three-node cycle and one self-loop",
            """DATA;
#1=LINK(#2);
#2=LINK(#3);
#3=LINK(#1);
#4=SELF(#4);
#5=ROOT(#1);
ENDSEC;""",
            root_entity_ids=(5,),
        ),
        _fixture(
            "nested_parameter_paths",
            "source_paths",
            "references nested in aggregates and typed parameters",
            """DATA;
#1=HOLDER((#2,WRAP((#3,#2))));
#2=ITEM();
#3=ITEM();
ENDSEC;""",
        ),
        _fixture(
            "multiple_data_sections",
            "ownership",
            "named DATA sections governed by distinct declared schemas",
            """DATA('left',('DEMO_A'));
#1=ASSEMBLY(#2);
ENDSEC;
DATA('right',('DEMO_B'));
#2=COMPONENT();
ENDSEC;""",
            schemas=("DEMO_A", "DEMO_B"),
        ),
        _fixture(
            "complex_instance",
            "record_types",
            "external mapping records retained on one graph node",
            """DATA;
#1=(BASE(#2) CHILD((#3)));
#2=TARGET();
#3=TARGET();
ENDSEC;""",
        ),
        _fixture(
            "unresolved_entity",
            "target_scope",
            "missing local entity target retained as unresolved",
            """DATA;
#1=ROOT(#404);
ENDSEC;""",
        ),
        _fixture(
            "external_entity",
            "target_scope",
            "REFERENCE entity target retained without retrieval",
            """DATA;
#1=ROOT(#900);
ENDSEC;""",
            pre_data="""REFERENCE;
#900=<https://example.invalid/external.step#entity>;
ENDSEC;
""",
        ),
        _fixture(
            "external_value_and_constant",
            "target_scope",
            "external value and schema constant references remain nonlocal",
            """DATA;
#1=MEASURE(@10,@PI);
ENDSEC;""",
            pre_data="""REFERENCE;
@10=<https://example.invalid/external.step#value>;
ENDSEC;
""",
        ),
        _fixture(
            "duplicate_reference_occurrences",
            "multigraph",
            "two source occurrences produce two edges to one target",
            """DATA;
#1=PAIR(#2,#2);
#2=ITEM();
ENDSEC;""",
        ),
        _fixture(
            "isolated_nodes",
            "isolation",
            "two nodes without local reference edges",
            """DATA;
#1=LEFT();
#2=RIGHT();
ENDSEC;""",
        ),
        _fixture(
            "depth_limited_chain",
            "query_limits",
            "construction succeeds while traversal reports a depth boundary",
            """DATA;
#1=LINK(#2);
#2=LINK(#3);
#3=LINK(#4);
#4=LINK(#5);
#5=LINK(#6);
#6=END_NODE();
ENDSEC;""",
            graph_limits=STEPGraphLimits(max_traversal_depth=3),
            query_max_depth=3,
        ),
        _fixture(
            "node_budget",
            "construction_limits",
            "entity count exceeds a tighter graph budget",
            """DATA;
#1=ITEM();
#2=ITEM();
#3=ITEM();
ENDSEC;""",
            expected_decision="quarantine",
            expected_reason_code="graph_node_limit",
            graph_limits=STEPGraphLimits(max_nodes=2),
        ),
        _fixture(
            "edge_budget",
            "construction_limits",
            "reference occurrences exceed a tighter graph budget",
            """DATA;
#1=ROOT(#2,#2,#2);
#2=ITEM();
ENDSEC;""",
            expected_decision="quarantine",
            expected_reason_code="graph_edge_limit",
            graph_limits=STEPGraphLimits(max_edges=2),
        ),
        _fixture(
            "syntax_failure",
            "parser_boundary",
            "Part 21 syntax failure stops before graph construction",
            """DATA;
#1=ITEM()
ENDSEC;""",
            expected_decision="reject",
            expected_reason_code="unexpected_token",
        ),
    )


def inspect_step_graph_fixture(fixture: STEPGraphFixture) -> STEPGraphObservation:
    """Build and query one fixture while retaining staged failure decisions."""
    if not isinstance(fixture, STEPGraphFixture):
        raise TypeError("fixture must be STEPGraphFixture")
    try:
        graph = build_step_graph(
            fixture.source_bytes, graph_limits=fixture.graph_limits
        )
    except Part21ParseError as error:
        return _empty_observation(error.decision, error.reason_code)
    except STEPGraphLimitError as error:
        return _empty_observation("quarantine", error.reason_code)

    traversal = graph.traverse(
        fixture.root_entity_ids, max_depth=fixture.query_max_depth
    )
    if traversal.complete:
        orphan_count: int | None = len(
            graph.orphaned_from(fixture.root_entity_ids)
        )
    else:
        orphan_count = None
    scopes = [edge.target_scope for edge in graph.edges]
    return STEPGraphObservation(
        "accept",
        "graph_constructed",
        len(graph.nodes),
        len(graph.edges),
        scopes.count("local_entity"),
        scopes.count("external_entity") + scopes.count("external_value"),
        scopes.count("unresolved"),
        scopes.count("schema_constant"),
        len(graph.root_nodes()),
        len(graph.isolated_nodes()),
        len(graph.cyclic_components()),
        traversal.complete,
        traversal.reason_code,
        len(traversal.visits),
        orphan_count,
        graph,
        traversal,
    )


def _empty_observation(
    decision: Literal["quarantine", "reject"], reason_code: str
) -> STEPGraphObservation:
    return STEPGraphObservation(
        decision,
        reason_code,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        None,
        "not_reached",
        0,
        None,
        None,
        None,
    )
