# B-Rep Learning and Modeling Roadmap

## 日本語概要

このロードマップは、STEPの文字列を読む段階から、面・辺・シェル・立体の位相理解、幾何評価、形状生成、編集履歴、妥当性検査、feature認識、assembly解析へ進み、最終的にB-repを説明・検証・実装できる状態を目指します。v0.21.0ではOpen CASCADEを依存にせず、限定したSTEP Part 21構文と位相関係を合成fixtureで検証します。幾何kernelの採用は、機能だけでなくライセンス、配布方法、再現性を確認してから判断します。詳細は以下の英語本文に示します。

---

## English Summary

This roadmap develops B-Rep competence from bounded STEP inspection to
geometry evaluation, modeling operations, validity analysis, feature
recognition, and assembly interpretation. Each stage requires controlled
fixtures, machine-readable evidence, tests, and explicit claim boundaries.

## Target Capability

The long-term target is not merely to display STEP files. It is to explain and
test how geometric definitions and topological relationships form a model,
then use those concepts to build a small analysis and modeling tool.

A completed path should support four kinds of work:

- inspect a STEP exchange structure without confusing file syntax, schema
  semantics, topology, and evaluated geometry;
- traverse vertices, edges, wires, faces, shells, solids, and assemblies while
  preserving orientation and ownership;
- create and modify controlled B-Rep models while recording which topology
  changed;
- identify invalid, ambiguous, unsupported, or resource-excessive input
  instead of inventing geometry or silently accepting it.

## Release Sequence

### v0.21.0 — STEP Part 21 and B-Rep Topology Inspection

Build a bounded, dependency-free parser for the controlled Part 21 subset and
resolve `EDGE_CURVE`, `ORIENTED_EDGE`, `EDGE_LOOP`, face bounds, analytic
surface declarations, shells, and solids. Export face-, edge-, shell-, and
solid-level CSV tables. Use synthetic closed, open, disconnected, surface-
catalog, unresolved-reference, and duplicate-identifier fixtures.

This release establishes topology inspection. It does not evaluate exact
surface geometry, validate an EXPRESS schema, or claim general STEP
conformance.

### v0.22.0 — Evaluated Face Geometry and Tolerances

Add an explicitly selected geometry backend and evaluate face area, centroid,
UV bounds, representative normals, boundary lengths, and tolerances. Compare
declared surface parameters with evaluated geometry and distinguish a face's
orientation from its supporting surface orientation.

The acceptance gate is a documented kernel and license decision plus analytic
fixtures whose expected measurements can be derived independently.

### v0.23.0 — Primitive Construction and Modeling Operators

Construct boxes, cylinders, cones, spheres, and tori, then exercise extrusion,
revolution, and Boolean union, intersection, and subtraction. Export the
result to STEP and re-inspect it. Record topological counts and geometric
properties before and after each operation.

### v0.24.0 — Topology Change and Shape History

Study fillets, chamfers, sweeps, lofts, and local edits. Track generated,
modified, deleted, split, and merged faces where the backend exposes that
history. Test why positional face indices are analysis-local identifiers and
cannot be treated as persistent design identities.

### v0.25.0 — Validity, Tolerance, and Healing

Create controlled gaps, reversed wires, missing seam edges, self-
intersections, tolerance mismatches, and nonmanifold cases. Separate detection
from repair, quantify every repair's effect, and retain the original evidence.

### v0.26.0 — Feature Recognition

Build adjacency-graph rules for planar pockets, cylindrical holes, bosses,
slots, and blends. Measure precision and recall on generated models with known
construction history. Treat recognized features as evidence-backed
interpretations, not recovered design intent.

### v0.27.0 — Assemblies, Placement, and Attributes

Resolve product structure, component reuse, placements, units, names, colors,
layers, and validation properties. Record whether each value comes from a STEP
entity, an exchange-library mapping, a kernel object, or an analysis-derived
calculation.

### v0.28.0 — Kernel Portability and Exchange Contracts

Run fixed STEP fixtures through independently selected import and geometry
backends. Compare topology inventories, evaluated properties, tolerances,
healing effects, and exported STEP structure. Differences become explicit
portability contracts rather than being hidden behind a single wrapper.

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

Every stage must add generated fixtures, a documented reproduction command,
observation CSV files, at least one explanatory figure or structured report,
relative or invariant tests, and a research note that separates direct
observations from broader interpretation.

## Dependency and License Checkpoint

v0.21.0 deliberately has no Open CASCADE Technology runtime or wrapper
dependency. The implementation uses the Python standard library for bounded
Part 21 tokenization and relationship resolution. NumPy and Matplotlib are used
only by the repository's experiment reporting path.

The current OCCT licensing page states that OCCT 6.7.0 and later use LGPL 2.1
with an additional exception. Its FAQ describes notice, license-copy, and
other license obligations for distributed products, including proprietary
ones. Those terms may be workable, but they are not invisible. A permissively
licensed Python wrapper also does not replace the license terms of a native
kernel it loads or distributes.

Before v0.22.0 introduces any geometry kernel, the project will record:

- the exact kernel and wrapper versions;
- direct and transitive licenses and required notices;
- whether binaries are linked, bundled, downloaded, or supplied by the user;
- source or relinking obligations relevant to the chosen distribution;
- whether a commercial alternative is required for the intended product;
- a dependency-free fallback for inspecting the controlled topology subset.

This checklist is an engineering decision record, not legal advice.

## Scope Discipline

The sequence intentionally postpones claims that require an evaluated geometry
kernel. v0.21.0 can report declared plane axes, cylinder radii, face bounds,
edge incidence, adjacency, and parent relationships. It cannot honestly report
exact trimmed-face area, centroid, UV domain, tolerance propagated by an
importer, or a robust representative normal for arbitrary STEP files. Those
fields remain roadmap items until their implementation and validation evidence
exist.

## Sources

- [ISO 10303-21:2016 overview](https://www.iso.org/standard/63141.html)
- [ISO 10303-242:2025 overview](https://www.iso.org/standard/84300.html)
- [Library of Congress STEP-file description](https://www.loc.gov/preservation/digital/formats/fdd/fdd000448.shtml)
- [NIST STEP File Analyzer and Viewer](https://www.nist.gov/services-resources/software/step-file-analyzer-and-viewer)
- [OCCT STEP translator documentation](https://dev.opencascade.org/doc/overview/html/occt_user_guides__step.html)
- [OCCT Shape Healing documentation](https://dev.opencascade.org/doc/overview/html/occt_user_guides__shape_healing.html)
- [OCCT licensing](https://dev.opencascade.org/resources/licensing)
- [OCCT licensing FAQ](https://dev.opencascade.org/resources/faq)
- [CadQuery OCP wrapper repository](https://github.com/CadQuery/OCP)
