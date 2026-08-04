# STEP Mastery, Python Parser, and 3D Tool Roadmap

## 日本語概要

このロードマップは、STEP規格をPythonパーサーとして実装・検証する道筋です。Part 21、EXPRESS、構成、幾何、位相を分離し、合成データとテストを残します。

<p>STEPを仕様から深く理解する<br>↓<br>STEPファイルをPythonで正しく読み取る<br>↓<br>形状・位相・製品構成を解析する<br>↓<br>面・辺・シェル・立体を扱う<br>↓<br>検査・可視化・変換・モデリングへ発展させる<br>↓<br>将来的に3DデータをAIでも利用する</p>

v0.29.0までにPart 21・EXPRESS解析、schema・引数・参照・継承検証、source span付き物理参照graph、AP242の製品定義から形状表現・項目・座標次元・単位へ至る制御された意味経路を実装しました。次はassemblyの再利用・配置・単位へ進み、v0.40で形状生成、v0.44でSTEP編集・再出力、v0.55以降でフィーチャー再構築を目指します。

詳細は以下の英語本文に示します。

---

## English Summary

This roadmap makes STEP specification mastery and a Python parser the primary
development path. It proceeds from a source-preserving Part 21 parser through
EXPRESS parsing and schema validation, application-protocol semantics,
product and representation graphs, B-Rep geometry, analysis, modeling, and
finally evidence-backed 3D data for AI. Every stage keeps synthetic samples,
machine-readable observations, tests, visual evidence when meaningful, and
explicit unanswered questions.

## Direction

The intended progression is:

```text
Understand STEP from its specifications
    -> read STEP files correctly in Python
    -> analyze shape, topology, and product structure
    -> work with faces, edges, shells, and solids
    -> develop inspection, visualization, conversion, and modeling tools
    -> use attributed 3D evidence in carefully bounded AI systems
```

This is not a plan to wrap a geometry kernel and call the result a STEP
parser. A kernel can eventually evaluate geometry and perform modeling
operations, but it cannot replace explicit knowledge of the exchange syntax,
the governing EXPRESS schema, or the provenance of each interpreted fact.

## Layers to Master

### 1. ISO 10303 as a family of standards

Establish the role of the STEP standard family and identify which part
governs each claim. A file-format observation, a schema rule, and an
application-protocol interpretation are different kinds of evidence.

### 2. ISO 10303-21 physical-file syntax

Read the clear-text exchange structure as bytes, UTF-8 text, tokens, sections,
records, parameters, and occurrence references. Preserve source spelling and
coordinates so a diagnostic can identify the exact line, column, character
range, and byte range that produced it.

### 3. EXPRESS language and schemas

Parse entity declarations, types, attributes, inheritance, aggregates,
selects, enumerations, imports, and constraints. EXPRESS determines what the
ordered parameters in a Part 21 record mean; entity-name recognition alone
does not.

### 4. Part 21 validation against EXPRESS

Resolve the declared schema and verify entity existence, parameter count,
types, references, inheritance, and supported constraints. Report lexical,
syntactic, schema-resolution, and schema-validation status separately.

### 5. Application-protocol semantics

Study controlled AP242 and selected predecessor patterns for products,
representations, units, placements, assemblies, attributes, and shape
definitions. Similar entity names across schemas do not establish semantic
equivalence.

### 6. Geometry and B-Rep topology

Trace definitions for points, curves, surfaces, vertices, edges, loops,
faces, shells, and solids. Separate a declared supporting surface from a
trimmed face, and separate topology from kernel-evaluated geometry.

### 7. Analysis, modeling, and AI

Build inspection, visualization, transformation, validation, repair, and
modeling functions over attributed records with provenance. AI may consume
those observations later, but it must not invent missing geometry or erase an
unresolved schema boundary.

## Licensing Boundary

The current release and future roadmap work are offered under the PolyForm
Noncommercial License 1.0.0.
Noncommercial research, academic, educational, and personal experimental use
is governed by the license terms; commercial use requires a separate written
license. See [Licensing](../LICENSING.md) for the controlling files, historical
boundary, third-party scope, and inquiry process.

Source availability supports reproducible research but does not disclose or
recover proprietary CAD feature history, third-party schema rights, or rights
in a geometry kernel. Each future kernel decision must still record the
kernel's own license, notices, distribution conditions, and commercial terms.

## Release Program

### Phase A — Part 21 Parser Foundation

#### v0.21.0 — STEP Part 21 and B-Rep Topology Inspection

The first bounded experiment reads selected simple entity instances and
resolves controlled face, edge, shell, and solid relationships. It establishes
synthetic shape generation, topology inventories, and fail-closed reference
handling, but it is not a general Part 21 parser or a schema validator.

#### v0.22.0 — Advanced Part 21 Exchange Structure and Parser Boundaries

The second experiment recognizes selected edition-3 sections and constructs:
multiple DATA sections, complex instances, UTF-8 strings, binary values,
anchors, external references, signatures, and ZIP container signatures.
External resources, signatures, and archives cross explicit trust boundaries
and are not resolved merely because their syntax is recognized.

#### v0.23.0 — Unified Part 21 Lexer, Grammar, and Source Model

Replace the separate v0.21 and v0.22 tokenizers and parsers with one shared
foundation. Preserve every token, comment, whitespace region, raw spelling,
normalized value, character range, byte range, line, and column. Keep lexical
analysis, grammar construction, exchange-structure checks, and downstream
interpretation separate.

Controlled evidence includes normal simple and complex instances, forward
references, UTF-8 coordinate differences, exact source reconstruction,
localized syntax failures, resource-limit failures, and the v0.21 closed
tetrahedron as an integration control.

Key question: which source details must be retained now so later diagnostics,
comparison, and writing do not depend on reparsing or guesswork?

#### v0.24.0 — Part 21 Grammar Coverage and Conformance Corpus

Classify selected Edition 1, Edition 2, and Edition 3 grammar behavior with 34
deterministic fixtures. The published evidence covers implementation-level
declarations, legacy and direct character encodings, comments, binary values,
multiple data sections, user-defined keywords, occurrence-name constraints,
anchors, references, signatures, optional data, and bounded ZIP transport.
The controlled parser matches all 34 expectations; two pinned public parsers
expose different acceptance boundaries without being treated as conformance
oracles.

Answered boundary: the parser now states which controlled forms it accepts and
why it rejects the paired malformed or misdeclared inputs. It still does not
cover the complete Wirth Syntax Notation, validate EXPRESS, resolve external
resources, verify CMS, or establish support for arbitrary STEP files.

### Phase B — EXPRESS and Schema Validation

#### v0.25.0 — EXPRESS Lexer, Parser, and Schema Model

The source-preserving parser now covers a controlled ASCII declaration subset:
schemas, aliases, aggregates, selects, enumerations, entity inheritance,
explicit, derived, and inverse attributes, interfaces, constants, functions,
procedures, and rules. Forty deterministic fixtures produce 20 accepts, 19
rejects, one resource-limit quarantine, exact reconstruction for accepted
sources, and 59 schema-model inventory rows.

Answered boundary: declarations become an unresolved model without pretending
that spelling a name proves its target, type, or rule semantics. Expressions
and algorithm bodies remain source-preserved envelopes; symbol resolution,
type checking, expression validation, and rule execution are deferred.

#### v0.26.0 — EXPRESS Symbols, Types, and Inheritance

The bounded semantic stage now constructs case-insensitive symbol tables and
resolves local names, direct in-document `USE` and `REFERENCE` imports, type
aliases, select members, entity inheritance, qualified redeclarations,
aggregate bounds, rule targets, and inverse forward attributes. Thirty-eight
fixtures produce 20 accepts, 17 rejects, and one resource-limit quarantine.

Answered boundary: unresolved, ambiguous, invalid-kind, and cyclic states
remain explicit rather than receiving guessed targets. Implicit imports,
transitive re-export, external schema loading, complete type compatibility,
expression typing, constraints, and rule execution remain deferred.

#### v0.27.0 — Part 21 Validation Against EXPRESS

The controlled validator now binds DATA sections to in-document schemas and
checks entity names, internal inheritance order, parameter count, selected
data domains, optional and derived markers, aggregates, selects, and
occurrence-reference compatibility. Forty paired fixtures produce 15 accepts,
21 rejects, and four quarantines while retaining Part 21 syntax, EXPRESS
syntax, symbol resolution, schema binding, and instance validation as separate
stages.

Answered boundary: simple internal mapping can be checked without executing
rules, but complete complex evaluated sets, external values and schemas,
width expressions, assignment compatibility, constraints, and application
meaning remain deferred.

### Phase C — Generic STEP Graph and Application Semantics

#### v0.28.0 — Generic STEP Graph and Query API

The parser now exposes forward and reverse references, exact entity-type
queries, section and schema ownership, reachability, caller-relative orphan
detection, cycles, and bounded traversal. Stable analysis-local identifiers
and source spans are available through Python, CSV, and versioned JSON records.

Answered boundary: the graph preserves physical Part 21 reference occurrences
without claiming that an edge represents product structure, an assembly
occurrence, B-Rep ownership, or geometry. AP242 meaning remains the next stage.

#### v0.29.0 — AP242 Product and Representation Paths

The application-semantic layer now resolves controlled paths from product
definitions and shape definitions to representations, direct items, geometric
contexts, coordinate-space dimensions, and explicitly assigned SI units.
Fourteen fixtures produce three accepts, eight quarantines, and three rejects;
five paths and 59 source-linked semantic relations remain independently
inspectable.

Answered boundary: a schema-derived role can be joined to one physical Part 21
reference occurrence without turning the generic graph into an AP242 graph.
Missing optional shape associations and unsupported schemas remain deferred.
Complete AP242 conformance, AP203/AP214 portability, assembly occurrences,
transform composition, unit conversion, and B-Rep evaluation remain outside
the result.

#### v0.30.0 — Assembly, Reuse, Placement, and Units

Distinguish a reusable component definition from each placed occurrence.
Evaluate nested transforms, coordinate systems, and unit conversions on
synthetic assemblies with independently known expectations.

### Phase D — B-Rep Semantics and Evaluated Geometry

#### v0.31.0 — Geometry Kernel and License Decision

Compare candidate geometry backends and Python bindings for STEP coverage,
B-Rep access, modeling operations, native packaging, headless CI, diagnostic
quality, version discovery, license terms, notices, redistribution, and
commercial alternatives. A permissive wrapper license does not replace the
license of the native kernel it loads.

This is a reproducible engineering and distribution decision record, not legal
advice.

#### v0.32.0 — Evaluated Face Geometry and Tolerances

Measure area, centroid, UV bounds, representative normals, face tolerance,
surface type, and analytic surface parameters against independently derived
synthetic truth. Keep face orientation, surface orientation, and normal
conventions explicit.

#### v0.33.0 — Curves, Edge Parameters, P-Curves, and Seams

Inspect vertices, 3D curves, edge ranges, curve-on-surface representations,
seam edges, and periodic surfaces. Test 3D and 2D agreement inside declared
tolerances.

#### v0.34.0 — Wires, Trimming, and Face Orientation

Evaluate ordered wires, outer and inner loops, holes, reversed uses, periodic
wrap-around, and degenerate boundaries. Demonstrate why an unbounded support
surface is not the same object as a trimmed face.

#### v0.35.0 — Shell and Solid Validity

Measure edge incidence, connected components, orientability, closure,
nonmanifold use, Euler characteristics, and signed-volume consistency. Compare
independent topology checks with kernel validity reports.

#### v0.36.0 — Tolerances, Sewing, and Healing Effects

Generate gaps around controlled tolerance boundaries. Record every modified
tolerance and topology count, retain original and repaired models, and treat
repair as an operation rather than proof of recovered design intent.

### Phase E — Inspection, Visualization, and Modeling

#### v0.37.0 — Face-Level Analysis Reports

Publish face-local indices, parent solid and shell, surface type, orientation,
area, centroid, UV bounds, representative normal, analytic parameters, wire
counts, edge counts, tolerance, adjacent faces, and attributed name or color
sources.

#### v0.38.0 — Tessellation and Visual Diagnostic Contracts

Generate meshes with explicit chordal and angular controls. Relate selected
triangles back to faces and source entities, and treat previews as inspection
aids rather than geometric truth.

#### v0.39.0 — Primitive Construction and STEP Round Trips

Construct controlled primitives and B-spline patches, export them, re-import
them, and compare parameters, topology counts, measurements, tolerances, and
exchange structure.

#### v0.40.0 — Profiles, Extrusion, and Revolution

Build profiles with holes, extrude and revolve them, and preserve synthetic
construction parameters as ground truth.

#### v0.41.0 — Sweeps, Lofts, and Surface Construction

Study guide curves, section compatibility, parameterization, continuity, and
controlled failure conditions.

#### v0.42.0 — Boolean Operations and Robustness

Exercise union, intersection, and subtraction across disjoint, tangent,
near-coincident, and tolerance-sensitive cases.

#### v0.43.0 — Fillets, Chamfers, and Topology History

Record generated, modified, deleted, split, and merged shapes when the backend
exposes history. Demonstrate why positional face indices are not persistent
design identities.

### Phase F — Interoperability and Defensive Processing

#### v0.44.0 — STEP Round-Trip Preservation

Compare import-export-import cycles for structure, semantics, geometry,
topology, attributes, tolerances, and file size. Separate semantic preservation
from byte identity.

#### v0.45.0 — Independent Parser and Kernel Portability

Run fixed samples through independently selected parsers, importers, or
kernels. Treat disagreements as explicit interoperability evidence.

#### v0.46.0 — Resource-Bounded 3D Intake

Bound file bytes, tokens, entities, references, archive expansion, recursion,
topology, tessellation output, and operation time. Isolate parsing, external
resolution, and native-kernel execution.

### Phase G — 3D Features and AI-Ready Evidence

#### v0.47.0 — Face-Adjacency Graphs and Geometric Descriptors

Represent faces as attributed nodes and shared edges as attributed relations,
with source and calculation provenance for every field.

#### v0.48.0 — Deterministic Feature Recognition

Build auditable geometric rules for holes, pockets, slots, bosses, ribs, and
blends on generated shapes with known construction history.

#### v0.49.0 — Synthetic 3D Dataset and Label Contracts

Generate controlled model families, negative examples, grouped splits, and
leakage checks. Preserve STEP, graph, B-Rep, preview, and label provenance.

#### v0.50.0 — Learned Baselines and Explainable 3D Assistance

Compare simple graph, tabular, and geometric baselines with deterministic
rules. Require calibration, robustness checks, evidence links, and abstention
when schema or geometry support is incomplete.

### Phase H — Parametric Reconstruction and Recompute

#### v0.51.0 — Parametric Feature Graph

Represent sketches, construction planes, dimensions, features, dependencies,
and generated B-Rep results as a versioned graph. Imported STEP topology is an
input reference; it is not silently relabeled as recovered design history.

#### v0.52.0 — Two-Dimensional Sketches and Geometric Constraints

Implement bounded line, arc, circle, coincidence, parallel, perpendicular,
tangent, horizontal, vertical, distance, radius, and angle constraints.
Separate under-constrained, fully constrained, over-constrained, and
inconsistent systems.

#### v0.53.0 — Parametric Holes, Pockets, Bosses, and Ribs

Construct common features from explicit parameters and compare their generated
topology and geometry with independently known synthetic construction truth.

#### v0.54.0 — Dependency Graph and Deterministic Recompute

Propagate parameter changes through an acyclic feature dependency graph,
isolate failed features, retain the last valid result, and report which
downstream shapes became invalid or stale.

#### v0.55.0 — STEP-to-Feature Reconstruction Candidates

Generate auditable candidate sketches and features from imported B-Rep
evidence. Report geometric residuals, ambiguity, alternative explanations,
and confidence; never claim recovery of unavailable original CAD history.

#### v0.56.0 — Assisted Parametric Modeling Tool

Expose import, inspection, candidate selection, parameter editing, recompute,
visual comparison, and STEP export through a bounded Python API and a focused
interactive tool. Require explicit user confirmation before replacing inferred
features or repaired geometry.

## Parametric Modeling Milestones

The phrase "parametric STEP editing" has three distinct meanings:

| Milestone | Planned release | Claim boundary |
| --- | --- | --- |
| Construct new parameter-driven geometry | v0.40.0 | Profiles, extrusion, and revolution recompute from explicit user parameters |
| Import STEP, add modeled operations, and export STEP | v0.43.0–v0.44.0 | The imported B-Rep is a base shape; no original feature history is implied |
| Infer an editable feature model from imported STEP | v0.55.0–v0.56.0 | Outputs are evidence-backed reconstruction candidates, not recovered authoring history |

A normal STEP exchange can preserve final product geometry without preserving
the originating CAD system's sketches, constraints, feature order, or design
intent. The project therefore distinguishes deterministic modeling operations
from reverse-engineered feature hypotheses throughout its APIs and evidence.

## Sample and Visual Evidence Contract

Every release preserves, when applicable:

- generated `.step`, archive, schema, or derivative inputs;
- a manifest with condition, limits, byte length, SHA-256 digest, and expected
  relationships;
- positive, negative, and boundary examples;
- CSV observations from the committed inputs;
- a preview for meaningful geometry or a source/relationship diagram for
  syntax-only samples;
- exact regeneration commands and CI comparisons;
- a note identifying whether evidence comes from source text, schema
  interpretation, declared geometry, kernel evaluation, or tessellation.

## Questions Carried Forward

- How much of the Part 21 edition history should one parser normalize, and
  which distinctions must remain visible to callers?
- Should a writer preserve exact syntax by default, produce a canonical form,
  or expose both modes as separate contracts?
- Which public EXPRESS schemas may be redistributed as fixtures, and which
  should be downloaded only by an explicit user action?
- Which EXPRESS rules require executable semantics rather than static type
  checking?
- Which kernel offers sufficient geometry and topology access under acceptable
  packaging and license conditions?
- Which identifiers remain stable after healing, modeling, and round trips?
- Where must an AI-assisted tool abstain because syntax, schema, geometry, or
  provenance is incomplete?

These questions are part of the research record. A release should answer a
bounded subset and state new uncertainty instead of hiding it.

## Sources

- [ISO 10303-21:2016 overview](https://www.iso.org/standard/63141.html)
- [Public final edition-3 draft of ISO 10303-21](https://www.steptools.com/stds/step/IS_final_p21e3.html)
- [ISO 10303-11:2004 overview](https://www.iso.org/standard/38047.html)
- [ISO 10303-42:2021 overview](https://www.iso.org/standard/79892.html)
- [ISO 10303-242 overview](https://www.iso.org/standard/84300.html)
- [STEPcode documentation](https://stepcode.github.io/docs/home/)
- [STEPcode Part 21 editor source](https://github.com/stepcode/stepcode/tree/develop/src/cleditor)
- [IfcOpenShell pure-Python physical-file parser](https://github.com/IfcOpenShell/step-file-parser)
- [Library of Congress STEP-file description](https://www.loc.gov/preservation/digital/formats/fdd/fdd000448.shtml)
- [NIST STEP File Analyzer and Viewer](https://www.nist.gov/services-resources/software/step-file-analyzer-and-viewer)
- [OCCT STEP translator documentation](https://dev.opencascade.org/doc/overview/html/occt_user_guides__step.html)
- [OCCT licensing](https://dev.opencascade.org/resources/licensing)
