# STEP, B-Rep, and 3D Intelligence Roadmap

## 日本語概要

このロードマップは、STEPの交換構造を読む段階から、EXPRESS・application protocol・幾何・位相・公差・形状修復・モデリング・assembly・相互運用性を順に検証し、最終的に根拠を説明できる3D解析・モデリングツールとAI利用へ進む長期計画です。各releaseでは合成STEP本体、hash付きmanifest、目視用preview、機械可読な観測結果、テスト、限界を残します。v0.22.0は高度なPart 21構造とparser境界を扱い、外部参照取得、署名検証、ZIP展開、EXPRESS適合性を未実装のまま成功扱いしません。幾何kernelは機能だけでなく、native依存、ライセンス、配布義務、再現性を比較してから採用します。詳細は以下の英語本文に示します。

---

## English Summary

This roadmap develops evidence-backed competence from STEP exchange syntax to
EXPRESS and application-protocol semantics, evaluated geometry, B-Rep
topology, modeling, interoperability, 3D analysis, and carefully bounded AI
use. Every release preserves synthetic STEP samples, visual previews,
machine-readable observations, tests, sources, and explicit claim boundaries.

## Long-Term Objective

The target is a small but technically honest 3D analysis and modeling tool,
not merely a STEP viewer. It should be able to answer three different kinds of
question without mixing them:

1. What bytes, sections, entities, and references does the exchange structure
   contain?
2. What product, representation, geometry, topology, tolerance, attribute, and
   assembly semantics are justified by the governing schemas?
3. What geometry has a selected kernel actually evaluated, changed, repaired,
   tessellated, or exported?

The eventual tool should expose those answers through inspectable records,
visual evidence, and stable identifiers scoped to one analysis. AI may consume
the same attributed graph and measurements later, but it must not invent
missing geometry, silently infer design intent, or erase source provenance.

## Conceptual Layers to Master

```text
Container and bytes
    -> ISO 10303-21 exchange structure
    -> EXPRESS schema and application protocol
    -> product and representation graph
    -> geometry definitions and B-Rep topology
    -> evaluated kernel shape and tolerances
    -> tessellation and visual preview
    -> analysis features and attributed graphs
    -> modeling operations and topology history
    -> AI-ready observations with provenance
```

Each arrow is a boundary. Passing one layer does not validate the next. A file
can be syntactically readable while violating its EXPRESS schema. A schema-
valid model can still be geometrically invalid for a particular kernel. A
successful tessellation can hide topology or tolerance problems. A plausible
AI label is not recovered design intent.

## Release Program

### Phase A — Exchange Structure and STEP Semantics

#### v0.21.0 — STEP Part 21 and B-Rep Topology Inspection

Parse a bounded simple-entity subset and resolve selected `EDGE_CURVE`,
`ORIENTED_EDGE`, `EDGE_LOOP`, face-bound, surface, shell, and solid
relationships. Establish analysis-local indices, topology inventories, and
fail-closed reference handling using synthetic closed, open, disconnected,
surface-catalog, and malformed fixtures.

#### v0.22.0 — Advanced Part 21 Exchange Structure and Parser Boundaries

Recognize ordered `HEADER`, `ANCHOR`, `REFERENCE`, repeated and parameterized
`DATA`, complex entity instances, direct UTF-8 strings, binary tokens, trailing
`SIGNATURE` sections, and ZIP container signatures. Validate section order,
global occurrence-name uniqueness, DATA-section names, and schema bindings.

External resources are recorded but never fetched. Base64 signature payloads
are inventoried but CMS signatures are not verified. ZIP containers are
recognized but not opened. EXPRESS conformance, ECMAScript execution, legacy
control directives, and arbitrary Part 21 compatibility remain outside this
release.

#### v0.23.0 — EXPRESS Models and AP242 Representation Paths

Trace the difference between EXPRESS declarations and Part 21 instances.
Resolve a controlled path from product definition and shape definition through
shape representation, representation context, units, and geometric items.
Compare selected AP203, AP214, and AP242-era naming patterns without treating
entity-name similarity as semantic equivalence.

Key question: how much application meaning can be established from public
schemas and explicit graph relationships before a geometry kernel is needed?

#### v0.24.0 — Kernel Selection, Licensing, and Import Contracts

Record a reproducible decision matrix for candidate geometry backends and
Python bindings. Compare supported STEP subsets, native packaging, version
discovery, deterministic installation, headless CI behavior, error reporting,
license terms, notice requirements, relinking or source obligations, and
commercial alternatives. Import fixed samples and compare parser facts with
kernel inventories before adopting a backend.

This is an engineering and distribution decision record, not legal advice.

### Phase B — Evaluated Geometry and B-Rep Correctness

#### v0.25.0 — Evaluated Face Geometry and Tolerances

Measure trimmed-face area, centroid, UV bounds, representative normals, and
face tolerance. Validate planes, cylinders, cones, spheres, tori, and bounded
B-spline examples against independently derived synthetic expectations.
Separate face orientation, surface orientation, and chosen normal convention.

#### v0.26.0 — Curves, Edge Parameters, P-Curves, and Seams

Inspect 3D curves, edge parameter ranges, vertices, curve-on-surface
representations, seam edges, and periodic surfaces. Test whether 3D edges and
2D p-curves agree within declared tolerances.

#### v0.27.0 — Wires, Trimming, UV Domains, and Orientation

Evaluate ordered wires, outer and inner loops, holes, reversed uses, periodic
wrap-around, and degenerate boundaries. Demonstrate why an unbounded
supporting surface is not the same object as a trimmed face.

#### v0.28.0 — Shell and Solid Validity

Measure connected components, edge incidence, orientability, closure,
nonmanifold use, Euler characteristics, and signed-volume consistency. Compare
topological tests with kernel validity reports on controlled counterexamples.

#### v0.29.0 — Tolerances, Sewing, and Healing Effects

Generate gaps and mismatches around explicit tolerance boundaries. Separate
detection from repair, record every changed tolerance and topology count, and
retain the original input beside the healed output. A repair is an operation,
not proof that the intended shape was recovered.

### Phase C — Modeling Operations and Topology History

#### v0.30.0 — Primitive Construction and STEP Round Trips

Construct boxes, cylinders, cones, spheres, tori, and controlled B-spline
patches. Export and re-import them, then compare declared parameters,
topological counts, mass properties, tolerances, and exchange structure.

#### v0.31.0 — Profiles, Extrusion, and Revolution

Build planar profiles with holes, extrude and revolve them, and connect sketch
orientation to resulting faces and seams. Preserve construction parameters as
synthetic ground truth rather than attempting to recover undocumented intent.

#### v0.32.0 — Sweeps, Lofts, and Surface Construction

Study guide curves, section compatibility, parameterization, continuity, and
failure conditions for sweeps and lofts. Compare the construction inputs with
the evaluated B-Rep rather than relying only on a rendered result.

#### v0.33.0 — Boolean Operations and Robustness

Exercise union, intersection, and subtraction across disjoint, tangent,
near-coincident, and tolerance-sensitive cases. Record validity, volume,
topology counts, diagnostics, and operation time under explicit bounds.

#### v0.34.0 — Fillets, Chamfers, and Topological Naming

Apply edge-local operations and record generated, modified, deleted, split,
and merged shapes where the backend exposes history. Demonstrate why positional
face indices are not persistent design identities across edits.

### Phase D — Product Structure, Attributes, and Presentation

#### v0.35.0 — Assemblies, Reuse, Placements, and Units

Resolve product structure, repeated components, nested transforms, coordinate
systems, and unit conversion. Distinguish a reused definition from each placed
occurrence and detect transform or unit ambiguity.

#### v0.36.0 — Names, Colors, Layers, and Provenance

Extract names, colors, layers, and selected attributes while recording whether
each value comes from a Part 21 entity, schema relationship, import-library
mapping, kernel object, or analysis-derived calculation.

#### v0.37.0 — PMI and Semantic Presentation Boundaries

Inventory selected dimensions, tolerances, datum relationships, and
presentation-only annotations. Keep semantic PMI separate from graphical
presentation and do not claim manufacturing interpretation beyond tested
constructs.

#### v0.38.0 — Tessellation Contracts and Visual Diagnostics

Generate meshes under explicit chordal, angular, and deflection settings.
Compare triangulated area, normals, boundaries, and component identities with
the underlying B-Rep. Treat previews as inspection aids, not geometric truth.

### Phase E — Interoperability, Scale, and Defensive Processing

#### v0.39.0 — STEP Round-Trip Preservation

Compare import-export-import cycles for structure, geometry, topology,
attributes, tolerances, and file size. Separate semantic preservation from byte
identity and record every unsupported or rewritten construct.

#### v0.40.0 — Independent Kernel and Converter Portability

Run fixed samples through independently selected importers or kernels. Compare
entity inventories, shape counts, measurements, healing effects, and
tessellations. Backend disagreements become explicit portability evidence.

#### v0.41.0 — Resource-Bounded 3D Intake

Add limits for file bytes, tokens, entities, references, archive members,
decompressed bytes, recursion, topology counts, tessellation output, and
operation time. Isolate parsing from external reference resolution and kernel
execution. This is defensive processing evidence, not a memory-safety proof.

### Phase F — Feature Understanding and AI-Ready Representations

#### v0.42.0 — Face-Adjacency Graphs and Geometric Descriptors

Represent faces as attributed nodes and shared edges as attributed relations.
Include surface family, area, orientation, curvature summaries, boundary
counts, tolerances, and provenance. Define canonicalization and invariance
tests before using the graph for learning.

#### v0.43.0 — Deterministic Feature Recognition

Build auditable rules for through holes, blind holes, pockets, slots, bosses,
ribs, and blends on generated shapes. Measure precision and recall against
known construction history while treating outputs as geometric
interpretations, not recovered design intent.

#### v0.44.0 — Synthetic 3D Dataset and Label Contracts

Generate parameterized model families with construction-history labels,
controlled variations, negative examples, train-validation-test grouping, and
leakage checks. Preserve STEP, B-Rep observations, previews, and label
provenance for every sample.

#### v0.45.0 — Learned Feature and Anomaly Baselines

Compare simple graph, tabular, and geometric baselines against deterministic
rules. Evaluate robustness to tessellation density, face ordering, kernel
version, unit scale, and export history. Report calibration and abstention, not
only aggregate accuracy.

#### v0.46.0 — Explainable 3D Queries and AI Assistance

Translate user questions into bounded graph and geometry queries, attach each
answer to source entities and computed evidence, and require abstention when a
claim depends on missing schema semantics or unsupported geometry. Generated
text remains a presentation layer over verified observations.

### Phase G — Integrated Analysis and Modeling Tool

#### v0.47.0 — Stable CLI and Machine-Readable Reports

Unify inspection, validation, preview, comparison, and export behind a small
CLI with documented exit codes and versioned JSON/CSV schemas.

#### v0.48.0 — Interactive Face and Assembly Explorer

Link a 3D selection to face, edge, shell, solid, assembly, source-entity,
tolerance, and provenance records. Keep the core analysis usable headlessly so
the viewer does not become the only source of truth.

#### v0.49.0 — Scriptable Modeling Prototype

Expose a bounded modeling API for primitives, profiles, transformations,
Boolean operations, and local edits. Every operation records inputs, outputs,
history, validity, and export evidence.

#### v0.50.0 — End-to-End 3D Analysis Contract

Combine bounded intake, STEP semantics, kernel evaluation, topology analysis,
visual diagnostics, rule-based features, optional learned assistance, and
modeling operations. Define the supported subset precisely enough that a later
v1.0 can be a compatibility promise rather than a marketing label.

## Sample and Visual Evidence Contract

Every STEP and B-Rep release must preserve, when applicable:

- generated `.step`, archive, or derivative input files;
- a manifest containing the generator condition, byte length, SHA-256 digest,
  expected decision, and expected structural or geometric relations;
- one or more previews that make the controlled shape or failure condition
  visually inspectable;
- CSV observations produced from the same committed samples;
- an exact regeneration command and CI comparison;
- both valid controls and isolated negative or boundary cases;
- a note explaining which preview elements come from declared construction
  coordinates, parsed topology, evaluated kernel geometry, or tessellation.

Previews are not substitutes for topology, tolerance, or geometry tests. For a
syntax-only fixture with no meaningful shape, the release should provide a
section or relationship diagram instead of fabricating geometry.

## Evidence Required at Every Stage

Each release follows the repository workflow:

```text
Research Question
    -> Source Review
    -> Method Selection
    -> Controlled Experiment
    -> Evaluation
    -> Interpretation
    -> Limitations
    -> Documentation
```

Acceptance requires source links, deterministic samples, machine-readable
results, relative or invariant tests, visual evidence where meaningful, and a
clear separation between observed results and general claims.

## Kernel and License Checkpoint

The v0.21.0 and v0.22.0 parsers deliberately have no geometry-kernel runtime.
This keeps exchange-structure evidence independent of native CAD behavior and
postpones distribution commitments until they can be examined directly.

The current OCCT licensing page states that OCCT 6.7.0 and later use LGPL 2.1
with an additional exception. A permissively licensed Python wrapper does not
replace the terms of the native kernel it loads or distributes. Other
candidate libraries can have commercial, copyleft, component-specific, or
non-B-Rep limitations.

Before a geometry backend enters the runtime dependency set, v0.24.0 will
record:

- exact kernel, wrapper, and native-binary versions;
- direct and transitive licenses and required notices;
- how binaries are linked, bundled, downloaded, or supplied by the user;
- redistribution, source, relinking, or commercial-license considerations;
- supported platforms and headless CI installation;
- import, evaluation, healing, modeling, history, and export capabilities;
- an independent parser fallback for the controlled Part 21 subset.

## Open Questions

- Which public EXPRESS schemas can be redistributed and tested without
  introducing unclear terms or unverifiable copies?
- Which kernel provides sufficient STEP, B-Rep, history, and healing access
  under acceptable distribution conditions?
- Which face and edge facts remain stable across kernel builds, tolerances,
  and round trips?
- How should topology identities be represented when operations split, merge,
  generate, or delete shapes?
- Which preview method exposes errors without letting tessellation hide them?
- How can synthetic construction history provide labels without making learned
  results depend on generator shortcuts?
- Where must an AI-assisted tool abstain because the exchange structure,
  schema, geometry, or provenance is incomplete?

These are research questions, not gaps to conceal. Each later release should
answer a bounded subset and add new questions when the evidence warrants them.

## Sources

- [ISO 10303-21:2016 overview](https://www.iso.org/standard/63141.html)
- [Public final draft of ISO 10303-21 edition 3](https://www.steptools.com/stds/step/IS_final_p21e3.html)
- [ISO 10303-11:2004 overview](https://www.iso.org/standard/38047.html)
- [ISO 10303-42:2021 overview](https://www.iso.org/standard/79892.html)
- [ISO 10303-242:2025 overview](https://www.iso.org/standard/84300.html)
- [Library of Congress STEP-file description](https://www.loc.gov/preservation/digital/formats/fdd/fdd000448.shtml)
- [NIST STEP File Analyzer and Viewer](https://www.nist.gov/services-resources/software/step-file-analyzer-and-viewer)
- [OCCT STEP translator documentation](https://dev.opencascade.org/doc/overview/html/occt_user_guides__step.html)
- [OCCT Shape Healing documentation](https://dev.opencascade.org/doc/overview/html/occt_user_guides__shape_healing.html)
- [OCCT licensing](https://dev.opencascade.org/resources/licensing)
- [OCCT licensing FAQ](https://dev.opencascade.org/resources/faq)
- [CadQuery OCP wrapper repository](https://github.com/CadQuery/OCP)
