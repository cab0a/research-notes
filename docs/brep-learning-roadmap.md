# STEP Mastery, Python Parser, and 3D Tool Roadmap

## 日本語概要

STEP規格をPythonパーサーとして実装・検証し、構文・意味・幾何・位相を分離して合成証拠を残す道筋です。

<p>STEPを仕様から深く理解する<br>↓<br>STEPファイルをPythonで正しく読み取る<br>↓<br>形状・位相・製品構成を解析する<br>↓<br>面・辺・シェル・立体を扱う<br>↓<br>検査・可視化・変換・モデリングへ発展させる<br>↓<br>将来的に3DデータをAIでも利用する</p>

v0.55.0は基準面、寸法、スケッチ、形状操作、結果形状を版番号付き非巡回依存グラフとして表します。明示的な3形状は真値と一致し、STEP読込後も位相数と計測値を保持しました。読込STEPの穴候補は未確認のまま結果形状と分離します。拘束条件と再計算は未実装です。v0.56.0以降は未実装です。

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

The [current STEP and B-Rep capability matrix](step-brep-capabilities.md)
separates completed evidence from controlled subsets, structural-only outputs,
and planned work.

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

The assembly layer now distinguishes reusable product definitions from placed
occurrences, resolves their context-dependent shape relationships, evaluates
explicit 3D item-defined child-to-parent rigid transforms, composes nested
root-relative paths, and normalizes supported SI and conversion-based length
units to millimetres. Seventeen fixtures produce five accepts, six
quarantines, and six rejects.

Answered boundary: source-frame offsets, quarter-turn rotation, nested reuse,
and inch conversion independently constrain transformation direction and
scale. Unsupported transformation selections, missing semantic evidence,
cycles, ambiguous reference designators, and work-budget exhaustion remain
explicit. Complete AP242 conformance and B-Rep geometry evaluation remain
outside the result.

### Phase D — B-Rep Semantics and Evaluated Geometry

#### v0.31.0 — Geometry Kernel and License Decision

Completed with eight candidates, six explicit technical gates, installed
package evidence, and one headless synthetic box round trip. CadQuery OCP with
OCCT is selected as an optional bounded research backend. The kernel-free
parser remains authoritative for source provenance, and no third-party wheel
or native library is committed or redistributed.

The Apache-2.0 Python wrapper and OCCT's LGPL-2.1 additional-exception terms
remain separate license layers. The installed reference inventory did not
surface the OCCT LGPL notice through standard Python distribution license-file
records, so packaged redistribution remains blocked pending a dedicated audit.
The study is an engineering decision record, not legal advice.

Answered boundary: the selected route can construct and validate one box,
write it to STEP, read it back, and preserve 1 solid, 6 faces, 12 unique edges,
and 8 unique vertices. It does not yet evaluate face fields. The strict Part 21
parser's original rejection of the writer's `.PCURVE_S1.` spelling was
resolved by the v0.49.0 portability study and retained as a regression case.

#### v0.32.0 — Evaluated Face Geometry and Tolerances

Completed with two bounded planes, one bounded cylindrical face, independent
closed-form truth, and a deterministic STEP round trip. Area, centroid, UV
bounds, representative points, support normals, orientation-adjusted normals,
surface frames, and cylinder radius remain inside the fixed numeric contract.
The reversed plane retains its topological orientation.

Answered boundary: constructed face tolerances of `1e-4`, `2e-4`, and `3e-4`
are all observed as `1e-7` after import while the STEP representation
uncertainty is `1e-4`. Tolerance is therefore recorded with stage and
provenance rather than claimed as per-face round-trip identity. Periodic seams,
p-curves, general trimming, holes, and spline surfaces remain deferred.

#### v0.33.0 — Curves, Edge Parameters, P-Curves, and Seams

Completed with one plane, one partial cylinder, one full cylinder, independent
boundary truth, and a deterministic STEP round trip. Eleven unique edges and
twelve oriented wire occurrences distinguish line and circle geometry,
analytic length, parameter span, vertex traversal, p-curves, and tolerance.

Answered boundary: the full cylinder uses one topological seam edge twice,
with two p-curve branches at `u=0` and `u=2π`. All controlled
`SameParameter` and `SameRange` flags are true, while a separate 17-sample
check records a maximum imported 3D-to-surface distance of `1.24e-12`.
Stored-versus-generated planar p-curves, degenerate edges, singularities,
splines, adaptive checks, and repair remain deferred.

#### v0.34.0 — Wires, Trimming, and Face Orientation

Completed with two planar frames, one full cylinder, one natural sphere,
independent material and signed-UV truth, and a deterministic STEP round trip.
The controls separate ordered wires, outer and inner loops, face reversal,
periodic seams, support domains, face restrictions, and point classification.

Answered boundary: reversing the planar face flips outer and inner loop signs
without changing area, centroid, or material classification. The sphere needs
two degenerate pole edges without 3D curves to close its UV boundary. The
constructed natural-restriction flag does not survive STEP import, so kernel
flags remain stage-specific observations. Curved p-curve integration, invalid
wires, nested islands, splines, non-manifold uses, and repair remain deferred.

#### v0.35.0 — Shell and Solid Validity

Completed with an outward box, a whole reversed box, an open box, a
one-face-flipped box, a three-face nonmanifold fan, a genus-one torus, and two
disconnected faces. Fourteen constructed and STEP-imported observations match
independent V/E/F, component, incidence, closure, orientability, and Euler
truth. Exact box and torus volume magnitudes are admitted only after explicit
topology and orientation gates.

Answered boundary: generic backend validity is true for the open,
misoriented, and nonmanifold constructed controls, while shell-specific and
independent checks retain the distinction. STEP import normalizes the whole
reversed box from signed volume `-120` to `+120`, reorients one flipped face,
and splits nonmanifold or disconnected shell containers. Vertex-neighborhood
manifoldness, self-intersection, nested void shells, tolerance-aware sewing,
and repair remain deferred.

#### v0.36.0 — Tolerances, Sewing, and Healing Effects

Completed with three controlled top-face gaps crossed against three requested
sewing tolerances. Seventeen stage observations, 550 subshape-tolerance rows,
12 operation records, and 10 STEP samples separate requested tolerance, stored
tolerance, topology, support geometry, and translator behavior. Zero gap closes
at every request, `5e-7` closes at `1e-6` and above, and `5e-5` closes only at
`1e-4`.

Answered boundary: tolerance-mediated closure does not move the six controlled
support planes or prove that a physical gap was filled. Shell orientation
repair is a no-op for the valid box and reduces the one-face-reversed control
from one required flip to zero. A deliberately over-tight tolerance cap keeps
the sewn topology closed but changes generic validity from true to false; its
STEP re-import becomes valid again, so the rejected in-memory operation remains
the decision record rather than being erased by translator normalization.

#### v0.37.0 — Manifoldness and Self-Intersection

Completed with 12 generated controls and 24 constructed/imported stage
observations. Tetrahedral vertex links, five box-pair relationships, and
separated/crossing edge and face aggregates are measured before and after
deterministic STEP exchange. The pinched pair has two uses on every edge but a
two-component link at its shared vertex; the three-face fan exposes both a
three-use edge and branching endpoint links.

Answered boundary: minimum distance zero does not distinguish point, curve,
surface, or volume contact. Single-argument `BOPAlgo_CheckerSI` evidence records one
crossing-edge point and one transverse face/face curve while paired negative
controls remain clear. Common-part and section evidence preserve the
controlled length `4`, area `16`, volume `9`, and transverse section length
`2` in the pinned route. The result remains a bounded polyhedral contract, not
a general proof for curved, spline, tangent, near-contact, or folded geometry.

#### v0.38.0 — Voids, Inner Shells, and Composite Solids

Completed with ten generated controls and 20 constructed/imported stage
observations. Forty-four shell-role rows, 60 containment rows, and nine solid-
adjacency rows separate outer and void shells, local and global nesting,
material islands, partial shell overlap, generic collections, and connected or
disconnected composite-solid claims. All ten constructed material-candidate,
shared-face-count, and solid-component-count expectations match.

Answered boundary: both overlapping voids have local depth one and the correct
orientation, yet their raw signed sum is `522` rather than the independently
known union-subtracted volume `531`; the partial-overlap gate rejects the
candidate. The constructed face-connected composite solid has one shared face
and one solid component, but STEP import returns two components with no shared
topological face. The result is a bounded axis-aligned-box study in one kernel
and translator route, not a general containment proof or preservation claim.

#### v0.39.0 — Correspondence Across Import and Healing

Completed with four generated planar/open-line controls. The face evidence
contains 56 stage-local descriptors, 37 geometry-gated candidates, and 35
source relations. Support-plane, area, and centroid evidence resolves 23
source faces uniquely across STEP import and leaves two coincident sources
ambiguous. Same-domain healing records two one-to-one and eight many-to-one
relations in four merge groups; all ten agree with separately recorded
operation history.

The edge evidence contains 122 stage-local descriptors, 79 candidates, and 75
source relations. Curve type, endpoints, length, and line-support evidence
resolve 47 STEP-import relations one-to-one and leave eight sources ambiguous.
Incident-face topology support is retained separately and does not force a
choice. Healing changes 20 edges to 12: eight relations are
`one_to_one_modified`, eight are many-to-one in four merge groups, and four
are deleted. All 20 agree with operation history. Direct `IsSame` and
`IsPartner` checks are each present for zero of the 75 edge relations.

Answered boundary: deterministic local indices are not persistent names.
Geometry inference, topology support for a candidate, operation history, and
direct identity are distinct evidence classes. These planar faces and open
line edges do not prove topological identity, STEP-carried operation history,
semantic provenance, or design intent. One-to-many splits, generated-result
controls, moving frames, curved and closed edges, and interacting repairs
remain unevaluated.

#### v0.40.0 — Rule-Based Feature Recognition

Completed with nine generated controls and their deterministic STEP fixtures.
Across constructed and imported stages, 136 face-attribute rows and 282
adjacency rows support seven geometric candidates per stage: through and blind
holes, an open step, a through slot, two chamfer-like boundaries, and one
constant-radius fillet-like boundary. The 14 candidate rows match both
controlled classification and registered dimensions; 18 whole-shape
observation rows and two equivalent-boundary rows retain the surrounding
evidence. Maximum controlled-truth error is
`3.9612757518625585e-13` model units for length and
`5.8832938520936295e-12` degrees for angle. The plain block and external
cylindrical boss are negative controls and produce zero false positives.

Answered boundary: the operation-built chamfer and a directly profiled bevel
have equivalent final boundaries at both stages. Each has 10 vertices, 15
edges, seven faces, one shell, one solid, volume `572`, and zero Boolean
difference volume in both directions. The rules therefore report both as
chamfer-like while `design_intent_proven` remains false. This is a bounded,
geometry-only, rule-based candidate recognizer for the named controls; it does
not recover feature history, prove manufacturing or design intent, or support
arbitrary and interacting features.

### Phase E — Inspection, Visualization, and Modeling

The stages from v0.56.0 onward are planned and not implemented at v0.55.0.

#### v0.41.0 — Face-Level Analysis Reports

Completed with five generated controls and normalized STEP fixtures. A
versioned 60-field CSV records 13 faces per stage: eight planes and one
cylinder, cone, sphere, torus, and B-spline. It integrates local parent solid
and shell lists, orientation, area, centroid, UV bounds, representative normal,
analytic or B-spline parameters, wire and unique-edge counts, tolerance,
adjacency, and attributed name/color sources.

All 13 geometry-matched round-trip pairs retain orientation and boundary
counts. Maximum area difference is `1.0317080523236655e-11` squared model units
and maximum centroid distance is `2.9535772102134982e-13` model units. The cone
semi-angle sign changes with an equivalent imported axis parameterization, and
the raised B-spline tolerance changes from `2.0e-4` to `1.0e-7`. Constructed
metadata is explicitly manifest-sourced; imported metadata remains blank on
the shape-only reader route. The stable schema does not provide persistent
face identity, arbitrary-file support, or XCAF attribution.

#### v0.42.0 — Tessellation and Visual Diagnostic Contracts

Completed with three normalized STEP fixtures and a two-by-two absolute
linear/angular meshing design. The experiment records 3,782 triangles across
36 face-condition observations. Every one of the nine imported faces maps
through direct transfer history to a verified source `ADVANCED_FACE` instance.

The through-hole triangle count changes from 88 to 220 only under the selected
angular refinement, the sphere changes from 168 to 422 under linear refinement
and to 1,260 under angular refinement, and the B-spline patch changes from 10
to 18 only under linear refinement. Eight zero-area sphere-pole triangles are
retained with blank geometric normals. Requested deflections and one
UV-barycentric deviation sample per triangle are diagnostic observations, not
certified error bounds; face-colored previews are not exact B-Rep geometry.

#### v0.43.0 — Primitive Construction and STEP Round Trips

Completed with six constructed and STEP-imported controls. All twelve stage
observations are analyzer-valid, and all six pairs retain unique topology and
support-surface inventories. The five analytic solids agree with independent
volume and area truth within `2e-8` at both stages.

Four pairs meet the intentionally literal contract. The cone's semi-angle
changes sign under an equivalent imported axis convention, and the B-spline
face tolerance changes from `2e-4` to `1e-7`, moving its tolerance-inflated
bounds by `0.0001999`. Construction parameters remain external synthetic
truth; they are not inferred feature history.

#### v0.44.0 — Profiles, Extrusion, and Revolution

Completed with five profile-driven controls and STEP fixtures. All ten stage
observations are analyzer-valid and match analytic volume and area within
`1e-8`; every pair retains topology and support-surface inventories.

The rectangle height change from `5` to `7` retains the expected volume ratio
`1.4`, and changing the annular revolution from `360°` to `180°` retains ratio
`0.5` at both stages. The inner annulus wire is explicitly opposite to the
outer wire; loop direction is construction semantics, not incidental ordering.

#### v0.45.0 — Sweeps, Lofts, and Surface Construction

Completed with two pipe sweeps, two section lofts, one point-grid B-spline
surface, and two precondition rejections. All ten accepted stage observations
are analyzer-valid, and all five pairs retain topology and support-surface
inventories across STEP. The three analytic controls match independent volume
and area truth within `1e-8`.

The C0 corner spine and single-section loft are rejected before native
construction. The smooth square loft remains valid but reaches approximately
`1.5` times the largest input half-span, demonstrating that interpolation
through sections does not imply containment inside their simple envelope.

#### v0.46.0 — Boolean Operations and Robustness

Completed with seven axis-aligned cuboid controls covering union, intersection,
subtraction, volume overlap, positive separation, face contact, and one
near-gap default/fuzzy pair. Twelve default stage observations match independent
cell-decomposition volume and area truth, and all 14 observations are valid.

The additional fuzzy value `0.0001` bridges a gap of `0.00005`, changing two
solids into one and changing exact-set volume and area. Six literal STEP
contracts pass; the fuzzy result retains topology but exhibits further volume
and area drift after import. No universal robustness tolerance follows.

#### v0.47.0 — Fillets, Chamfers, and Topology History

Completed with unit fillet and chamfer controls plus two oversized native
non-completion cases. Both successful shapes match analytic volume and area at
construction and after STEP import. Each operation records 26 source-subshape
rows under the documented query scope: one source edge has a generated face,
four source faces have modified successors, and no supported deletion, split,
or merge occurs in these bounded controls.

All fourteen geometry-matched face pairs retain equal local integer indices on
the pinned writer/reader route, but direct identity and imported operation
history are both absent. Equal index values are recorded as ordering evidence,
not persistent naming or recovered design history.

### Phase F — Interoperability and Defensive Processing

#### v0.48.0 — STEP Round-Trip Preservation

Completed with three named and colored XCAF documents and six normalized STEP
files. All pairs retain free-shape/product counts, imported names, global
geometry, topology, color-table inventory, and maximum subshape tolerances
between generations. Only the box pair is byte identical.

The compound through-hole control loses its declared color before the source
import and then preserves the empty color inventory. Source-truth agreement,
generation stability, and physical byte identity are therefore three separate
claims.

#### v0.49.0 — Independent Parser and Kernel Portability

Completed with three frozen STEP files, the repository parser, two pinned
public parsers, and two OCCT import routes. All nine parser observations accept
their inputs, and both import routes agree on topology, volume, area, and
support surfaces for all three controls. The XCAF route exposes document names
and selected colors that the shape-only route does not report. Both routes use
one OCCT build, so the contract records no independent-kernel conclusion.

#### v0.50.0 — Resource-Bounded 3D Intake

Completed with seven deterministic raw STEP and controlled ZIP-container
fixtures and thirteen policy controls. All expected terminal decisions and
reason codes match: two accepts, five quarantines, and six rejects. Syntax and
native geometry execute in separate child processes; external references are
quarantined without retrieval. Byte, syntax, archive, path, depth, topology,
triangle, and time limits remain policy evidence rather than a native security
or memory-safety proof.

### Phase G — 3D Features and AI-Ready Evidence

#### v0.51.0 — Face-Adjacency Graphs and Geometric Descriptors

Completed with four constructed and STEP-imported graph pairs. The constructed
corpus contains 28 face nodes and 59 distinct-face shared-edge relations. All
pairs retain selected topology, surface, degree, relation, seam, boundary,
non-manifold, and coarse structural-signature invariants. Every CSV field is
routed to contract, topology, geometry, or exchange provenance. Local IDs,
representative samples, and the structural signature are not persistent naming,
complete graph isomorphism, or recovered design intent.

#### v0.52.0 — Feature Recognition Robustness and Benchmarking

Completed with 32 generated cases and 64 constructed/imported observations.
Baseline, half-scale, and tolerance/healing controls retain their expected
classification and dimensions. Two rotated cases expose the global-axis rule
assumption as explicit abstentions; negative controls remain rejected and STEP
exchange changes no decision. Generated truth is not recovered CAD history.

#### v0.53.0 — Synthetic 3D Dataset and Label Contracts

Completed with 36 STEP-backed samples from nine construction families. Fixed
family-isolated train, validation, and test partitions retain labels, STEP
digests, B-Rep measurements, face graphs, previews, and provenance. Five
identity, family, source, and provenance leakage checks report zero violations.

#### v0.54.0 — Learned Baselines and Explainable 3D Assistance

Completed with one bounded rule and three NumPy nearest-centroid baselines.
Training, validation calibration, and test families remain separate. Every
prediction retains source, descriptor evidence, confidence, and abstention.
Test success for rule and tabular methods coexists with a geometry-only failure,
so accuracy, coverage, and held-out families remain inseparable.

### Phase H — Parametric Reconstruction and Recompute

#### v0.55.0 — Parametric Feature Graph

Completed with three explicit construction graphs and one isolated imported
candidate graph. Sixteen structural validations pass, three generated B-Reps
match independent truth and STEP measurements, and the imported hole candidate
remains unconfirmed without a result node. Constraint solving and recompute are
deferred.

#### v0.56.0 — Two-Dimensional Sketches and Geometric Constraints

Implement bounded line, arc, circle, coincidence, parallel, perpendicular,
tangent, horizontal, vertical, distance, radius, and angle constraints.
Separate under-constrained, fully constrained, over-constrained, and
inconsistent systems.

#### v0.57.0 — Parametric Holes, Pockets, Bosses, and Ribs

Construct common features from explicit parameters and compare their generated
topology and geometry with independently known synthetic construction truth.

#### v0.58.0 — Dependency Graph and Deterministic Recompute

Propagate parameter changes through an acyclic feature dependency graph,
isolate failed features, retain the last valid result, and report which
downstream shapes became invalid or stale.

#### v0.59.0 — STEP-to-Feature Reconstruction Candidates

Generate auditable candidate sketches and features from imported B-Rep
evidence. Report geometric residuals, ambiguity, alternative explanations,
and confidence; never claim recovery of unavailable original CAD history.

#### v0.60.0 — Assisted Parametric Modeling Tool

Expose import, inspection, candidate selection, parameter editing, recompute,
visual comparison, and STEP export through a bounded Python API and a focused
interactive tool. Require explicit user confirmation before replacing inferred
features or repaired geometry.

## Parametric Modeling Milestones

The phrase "parametric STEP editing" has three distinct meanings:

| Milestone | Planned release | Claim boundary |
| --- | --- | --- |
| Construct new parameter-driven geometry | v0.44.0 | Profiles, extrusion, and revolution recompute from explicit user parameters |
| Import STEP, add modeled operations, and export STEP | v0.47.0–v0.48.0 | The imported B-Rep is a base shape; no original feature history is implied |
| Infer an editable feature model from imported STEP | v0.59.0–v0.60.0 | Outputs are evidence-backed reconstruction candidates, not recovered authoring history |

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
