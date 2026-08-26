# Parametric Feature Graph

## 日本語概要

この研究は、基準面、寸法、スケッチ、形状操作、結果形状を、版番号付きの非巡回依存グラフとして表します。明示的に作成した板、穴付き板、段差付き角柱をSTEPへ出力して真値と比較し、別のSTEP読込形状から得た穴候補は未確認候補として隔離します。読込形状を元の作成履歴へ読み替えず、今後の拘束条件と再計算の土台を作ります。詳細は英語本文に示します。

---

## English Summary

This study defines a versioned directed acyclic graph for explicit parametric construction and keeps an imported STEP reconstruction candidate in a separate, unconfirmed graph.

## Research Question

Can sketches, datum planes, dimensions, features, dependencies, generated B-Reps, and imported reconstruction evidence share one auditable graph contract without relabeling final STEP geometry as original authoring history?

## Background

A final B-Rep records boundary geometry and topology, while a parametric model also needs application-level references, parameters, operation order, and dependencies. Open CASCADE Application Framework documents a reference-key data model and function dependencies, but this release implements a small repository-specific graph rather than adopting the full framework.

## Method

Three explicit graphs represent a plate extrusion, a plate extrusion followed by a through-hole subtraction, and a stepped-profile extrusion. Nodes cover datum planes, millimetre parameters, sketches, features, and generated results. Directed edges point from a dependent node to its prerequisite. A fourth graph references a committed through-hole STEP file, its measured face graph, and an unconfirmed reconstruction candidate; it contains no result node.

Every graph revision has a deterministic fingerprint. Validation checks unique node identifiers, locally resolved endpoints, acyclic dependencies, and the imported-candidate boundary. Generated shapes are compared with closed-form volume and surface-area truth before and after STEP exchange.

## Controlled Experiment

The plate has volume 192 and area 272 square model units. The radius-one through hole changes volume to `192 - 2π`; two removed disks subtract `2π`, while the height-two cylindrical wall adds `4π`, producing area `272 + 2π`. The stepped prism has volume 368 and area 364. Three normalized STEP results and their previews are committed.

## Results

All 16 graph validations pass. All three constructed shapes match their independent volume and area truth within `1e-9`; their imported results remain analyzer-valid, retain topology counts, and differ in volume and area by less than `1e-9`. The imported graph retains the STEP digest and an `unconfirmed` hole candidate, with no generated-result node.

## Interpretation

The graph introduces stable application identifiers above volatile B-Rep face and edge numbering. Explicit construction and imported inference can use a common serialization while preserving different provenance. This is the first modeling-oriented contract in the roadmap, but parameter editing and dependency recompute remain later work.

## Failure Modes

- Acyclic structure does not prove that geometric operations are valid.
- Application node identifiers do not persistently name generated faces or edges.
- Parameters can be syntactically present but dimensionally or semantically incompatible.
- An imported candidate can have multiple equally plausible feature explanations.
- STEP round-trip agreement does not preserve an unavailable authoring timeline.

## Practical Guidance

Store application identifiers separately from B-Rep subshape indices. Record units, provenance, revision, dependency direction, and candidate status in the graph contract. Require explicit confirmation before converting an imported candidate into an authored feature.

## Limitations

The graph covers three explicit solids, one imported candidate, scalar millimetre parameters, and one revision. It has no sketch constraint solver, transaction history, undo/redo, persistent topological naming, general recompute engine, assembly graph, or interactive editor.

## Sources

- [Open CASCADE introduction](https://dev.opencascade.org/doc/overview/html/index.html) describes OCAF documents, attributes, parametric dependencies, and recomputation services.
- [Open CASCADE OCAF guide](https://dev.opencascade.org/doc/occt-7.7.0/overview/html/occt_user_guides__ocaf.html) documents reference-key organization and function dependency graphs.
- [Open CASCADE `TFunction_GraphNode` reference](https://dev.opencascade.org/doc/refman/html/class_t_function___graph_node.html) documents previous and next function links.
- [Improved Representation of Dependencies in Feature-based Parametric CAD Models using Acyclic Digraphs](https://doi.org/10.5220/0005261500160025) discusses acyclic dependency representations for feature-based parametric models.
