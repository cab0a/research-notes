# Generic STEP Graph and Query API

## 日本語概要

この研究ノートは、STEP Part 21のDATA entityを解析ローカルnode、各参照出現をsource span付きの有向edgeとして保存し、型検索、順方向・逆方向参照、到達性、孤立、循環、複数DATA部のschema所有を上限制御付きで照会します。14件の合成fixtureは11件受理・2件隔離・1件拒否で期待と一致し、31 node、25 edge、89 query rowを記録しました。これは物理参照graphであり、AP242製品構成、B-rep意味論、外部resource解決、永続CAD identityは主張しません。詳細は以下の英語本文に示します。

---

## English Summary

This note turns the source-preserving Part 21 model into a deterministic,
bounded directed multigraph. Each DATA entity becomes one analysis-local node,
and each entity, value, or constant reference occurrence becomes one edge with
its record position, nested parameter path, target scope, and source span. The
API supports exact type lookup, forward and reverse adjacency, bounded
breadth-first traversal, caller-relative orphan queries, and deterministic
cyclic components without claiming application meaning.

## Research Question

Can a small Python API expose a reproducible and source-linked graph over STEP
Part 21 instances while keeping physical references, query-relative graph
properties, schema ownership, and later AP242 or B-Rep interpretation separate?

## Background

[ISO 10303-21:2016](https://www.iso.org/standard/63141.html) specifies the
clear-text exchange structure used to transfer product data described in
EXPRESS. The public Edition 3 text defines
[occurrence names](https://www.steptools.com/stds/step/IS_final_p21e3.html#clause-6-4-4),
[DATA-section entity instances](https://www.steptools.com/stds/step/IS_final_p21e3.html#clause-11-2),
and a separate
[REFERENCE section](https://www.steptools.com/stds/step/IS_final_p21e3.html#clause-10-1).
The Library of Congress format description likewise notes that the numeric
entity names and their relationships are difficult to interpret without
connecting the exchange structure to its governing schema.

A reference occurrence provides a physical relationship, but it does not by
itself say that the source is an assembly, the target is a component, or either
record is geometry. Those claims require EXPRESS declarations and application-
protocol semantics. Multiple DATA sections also require explicit section and
schema ownership rather than a global type guess.

The committed JSON artifact follows the portable structured-data model defined
by [RFC 8259](https://www.rfc-editor.org/rfc/rfc8259). Its project-specific
`record_type` and `format_version` fields define this repository's contract;
they are not an ISO STEP serialization or a standard graph interchange format.

## Method

`build_step_graph()` consumes the existing bounded, source-preserving Part 21
document and performs these steps:

1. Assign a zero-based `node_index` in DATA-section and entity source order.
2. Retain the Part 21 entity identifier, section index and name, governing
   schema identifier, simple or complex record types, and complete source span.
3. Walk each record parameter depth first and create one edge for every
   reference occurrence. Repeated references remain repeated multigraph edges.
4. Record the source entity, optional local target, raw occurrence name,
   reference kind, target scope, record index, nested parameter path, and
   source span for every edge.
5. Build incoming indexes only for entity references resolved to a local DATA
   node. External entity and value references, schema constants, and unresolved
   references remain observable nonlocal edges.
6. Apply explicit node, edge, query-result, traversal-visit, and traversal-depth
   budgets.

The query layer provides:

- exact, case-insensitive record-type lookup;
- source-ordered outgoing and incoming reference occurrences;
- zero-indegree and isolated-node inventories;
- bounded breadth-first forward and reverse traversal;
- nodes unreachable from caller-declared roots, only after a complete traversal;
- deterministic strongly connected components containing a cycle;
- a versioned JSON-compatible record with no timestamps or local paths.

Cycle detection reports strongly connected components rather than enumerating
every simple cycle. Simple-cycle enumeration can grow rapidly and is not needed
to answer whether a controlled component participates in a directed cycle.

## Controlled Experiment

Fourteen deterministic STEP fixtures isolate one graph behavior at a time.

| Category | Controlled evidence |
| --- | --- |
| Reachability | A branching graph rooted at `#1` and a disconnected `#99` node |
| Direction | Forward and reverse breadth-first traversal |
| Source paths | References nested in aggregates and typed parameters |
| Ownership | Two named DATA sections governed by different declared schemas |
| Record types | One complex instance with two component records |
| Target scope | Local, external entity, external value, schema constant, and unresolved targets |
| Multigraph | Two parameter occurrences that both reference the same target |
| Isolation | Nodes with no local incoming or outgoing references |
| Cycles | A three-node strongly connected component and one self-loop |
| Query boundary | A chain whose depth-limited traversal is explicitly partial |
| Construction boundary | Separate node and edge budget quarantines |
| Parser boundary | One malformed Part 21 input rejected before graph construction |

The generated fixture manifest records source hashes, declared roots, expected
routes, and every graph budget. All input data is synthetic.

## Results

All 14 fixtures matched their declared decisions:

- 11 accepted graph constructions;
- two resource-budget quarantines;
- one Part 21 syntax rejection.

The accepted fixtures produced 31 nodes and 25 reference-occurrence edges:

| Target scope | Edges |
| --- | ---: |
| Local entity | 21 |
| External entity | 1 |
| External value | 1 |
| Schema constant | 1 |
| Unresolved | 1 |

The experiment emitted 89 query rows: 86 complete, two partial, and one
`not_evaluated`. The two partial rows are the forward and reverse traversals of
the controlled depth-limited chain. Root-relative orphan classification is not
performed for the incomplete forward traversal.

In the representative graph, root `#1` reaches `#1`, `#2`, `#3`, and `#4` in
breadth-first order. Node `#99` is unreachable from the declared root and is
therefore the one root-relative orphan. The cycle fixture reports `(1, 2, 3)`
and the self-loop `(4)` as separate cyclic components.

![Generic STEP graph evidence](../results/step_graph.png)

Committed evidence:

- [`step_graph_observations.csv`](../results/step_graph_observations.csv)
- [`step_graph_nodes.csv`](../results/step_graph_nodes.csv)
- [`step_graph_edges.csv`](../results/step_graph_edges.csv)
- [`step_graph_queries.csv`](../results/step_graph_queries.csv)
- [`step_graph_summary.csv`](../results/step_graph_summary.csv)
- [`step_graph.json`](../results/step_graph.json)

## Interpretation

The graph is now a reusable boundary between syntax and meaning. Later AP242
work can query a product or representation path without reparsing source text,
while every returned node and edge can still be traced to exact character,
byte, line, and column coordinates.

Retaining repeated edge occurrences matters. A set-only adjacency map would
show that `#1` reaches `#2`, but it would lose whether two different attributes
or aggregate positions carried that relationship. The parameter path preserves
that evidence until EXPRESS attributes can be joined in a later layer.

Unresolved and external targets do not automatically invalidate graph
construction. They are useful observations about the exchange structure. They
must not become local nodes or silently trigger network retrieval.

The root-relative orphan result is intentionally narrower than an application
claim. A zero-indegree node can be a valid top-level product, an auxiliary
record, or an incomplete fragment. Only AP242 semantics can identify meaningful
product and representation roots.

## Failure Modes

- Collapsing repeated references into one edge destroys parameter-occurrence
  provenance.
- Treating every numeric occurrence name as a local entity invents nodes for
  external or unresolved targets.
- Using record type names without section and schema ownership can mix distinct
  schema populations.
- Calling every zero-indegree node an orphan confuses graph structure with
  product semantics.
- Reporting unreachable nodes after a truncated traversal creates false orphan
  claims.
- Enumerating every simple cycle can consume unbounded work on dense graphs.
- Assigning stable CAD identity to `node_index` or `#` identifiers fails across
  export, editing, healing, and Boolean operations.
- Resolving REFERENCE resources during graph construction crosses an external
  trust boundary.

## Practical Guidance

- Use Part 21 entity identifiers to join records within one parsed exchange;
  use `node_index` only as a deterministic analysis-local ordering.
- Preserve the source span and parameter path for every reference occurrence.
- Choose traversal roots explicitly and label unreachable results as relative
  to those roots.
- Treat `complete=False` as a hard boundary against negative reachability or
  orphan claims.
- Keep nonlocal targets visible but unresolved until a separate resource policy
  authorizes retrieval and validation.
- Join EXPRESS attribute provenance before assigning application meaning to an
  edge.
- Version JSON records and compare semantic fields rather than formatting or
  dictionary insertion order.

## Limitations

- This is a physical Part 21 reference graph, not an AP242 product graph,
  assembly graph, B-Rep graph, or geometry dependency graph.
- Type queries match encoded record keywords. They do not include EXPRESS
  supertypes, select membership, or application roles.
- Complex instances remain one node with multiple encoded record types; complete
  evaluated-set semantics are still deferred.
- External entity and value references are retained but never retrieved,
  authenticated, or merged into the local graph.
- Schema constants are identified by occurrence syntax but not resolved to
  EXPRESS declarations or values.
- Zero-indegree, isolated, cyclic, reachable, and orphan results describe only
  local entity-reference edges under the declared query controls.
- The JSON contract is project-specific and has no backward-compatibility
  promise beyond the recorded `1.0` format in this release.
- The 14 synthetic fixtures do not establish performance, memory safety, ISO
  conformance, AP242 compatibility, or behavior on arbitrary field files.

## Questions Carried Forward

- Which AP242 entities define defensible product, shape, and representation
  roots for v0.29.0?
- How should EXPRESS supertypes and attribute names become optional graph query
  indexes without duplicating the validation layer?
- Which external-reference policy can merge separately validated graphs while
  preserving resource origin and trust state?
- Should the versioned JSON contract later separate physical edges from
  schema-derived and application-derived relationships?
- Which graph summaries are useful for 3D AI without erasing source provenance
  or inventing geometry?

## Sources

- [ISO 10303-21:2016 catalog page](https://www.iso.org/standard/63141.html)
- [Public final draft of ISO 10303-21 Edition 3](https://www.steptools.com/stds/step/IS_final_p21e3.html)
- [Part 21 occurrence names](https://www.steptools.com/stds/step/IS_final_p21e3.html#clause-6-4-4)
- [Part 21 REFERENCE section](https://www.steptools.com/stds/step/IS_final_p21e3.html#clause-10-1)
- [Part 21 DATA-section entity instances](https://www.steptools.com/stds/step/IS_final_p21e3.html#clause-11-2)
- [Part 21 multiple-schema reference validity](https://www.steptools.com/stds/step/IS_final_p21e3.html#annex-E-1)
- [Library of Congress STEP-file format description](https://www.loc.gov/preservation/digital/formats/fdd/fdd000448.shtml)
- [RFC 8259: The JavaScript Object Notation Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259)
