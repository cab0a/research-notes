# STEP and B-Rep Capability Matrix

## 日本語概要

本書は、v0.31.0時点のSTEP・EXPRESS・AP242・B-rep機能を、実装済み、限定対応、構造のみ、研究実証、未実装に分けて整理します。現在は原文を保持したPart 21解析、限定したEXPRESS検証、物理参照グラフ、単純な位相関係、AP242製品・組立経路に加え、任意のOpen CASCADE形状計算経路で合成箱を生成しSTEP往復する研究実証まで完了しました。一方、面積・重心・UV範囲・代表法線・公差・体積などの面・立体計算、一般的な実ファイルへの適合、利用者向け形状編集機能、AIモデルは未実装です。第三者バイナリの再配布も選定対象外です。詳細な根拠と予定版は以下の英語本文に示します。

---

## English Summary

This document states what the STEP and B-Rep track can and cannot claim at
v0.31.0. It separates syntax recognition, schema validation, physical-reference
graphs, application semantics, declared topology, evaluated geometry, and
modeling so that success at one layer is not presented as success at another.

## Status Definitions

| Status | Meaning |
| --- | --- |
| Implemented | The repository exposes code, deterministic evidence, and tests for the stated behavior. |
| Implemented for declared cases | The behavior is tested for named positive, negative, or bounded cases, not as a general validator. |
| Controlled subset | Implemented only for explicitly listed generated forms and limits; arbitrary files are outside the claim. |
| Structural only | Declarations or relationships are retained, but their geometry or application meaning is not evaluated. |
| Partial | Some requested fields can be joined or inferred from separate outputs, but the intended direct contract is incomplete. |
| Research evidence | A reproducible experiment records observations without exposing a general supported feature. |
| Not implemented | No current public implementation supports the capability. |

Only published releases count as completed work. Planned release numbers are
directions, not delivery promises.

## Executive Snapshot

| Layer | Current status | What works now | What does not follow |
| --- | --- | --- | --- |
| Part 21 physical file | Controlled subset | Parse selected Edition 1, 2, and 3 clear-text forms from bytes while retaining tokens and source coordinates | Complete ISO 10303-21 conformance or arbitrary STEP-file compatibility |
| EXPRESS | Controlled subset | Parse selected declarations and resolve bounded in-document symbols, types, imports, and inheritance | Complete language semantics, external schema loading, or rule execution |
| Part 21 against EXPRESS | Controlled subset | Bind selected DATA sections to controlled schemas and check selected entity parameters | Full EXPRESS validation or AP242 conformance |
| Physical reference graph | Implemented | Query local and nonlocal reference occurrences with source provenance and explicit traversal budgets | Product, assembly, topology, or geometry meaning without another semantic layer |
| B-Rep topology | Structural only | Inventory selected faces, edges, shells, solids, ownership, adjacency, and edge incidence | Kernel-evaluated geometry, tolerance validity, orientability, volume, or repair |
| AP242 product paths | Controlled subset | Resolve one exact schema identifier through selected product, shape, representation, item, context, and unit roles | AP203/AP214 portability, complete AP242 coverage, or geometric validity |
| AP242 assemblies | Controlled subset | Separate definitions from occurrences, evaluate selected rigid placements, compose nested paths, and normalize supported length units | Arbitrary transformation operators, all unit forms, moved B-Rep evaluation, or persistent CAD identity |
| Geometry backend | Research evidence | One optional pinned OCCT route constructs, validates, writes, reads, and recounts a synthetic box headlessly | Face geometry, independent validation, cross-platform portability, redistribution approval, or general STEP compatibility |
| Inspection artifacts | Implemented | Regenerate synthetic STEP/EXPRESS inputs, CSV, JSON, and diagnostic figures deterministically | A general end-user CAD inspector or an interactive 3D viewer |
| Geometry modeling | Research evidence | The v0.31 experiment constructs one fixed box and writes it to STEP through the optional backend | A supported modeling API, parameter editing, sketches, sweeps, Boolean operations, healing, and evaluated export preservation |
| AI use | Not implemented | Source-linked tables and graphs can become future inputs | No dataset contract, feature learner, trained model, inference API, or quality claim exists |

## Part 21 and Container Capabilities

| Capability | Status | Current contract | Current boundary | Evidence |
| --- | --- | --- | --- | --- |
| Byte input | Implemented | Public parsers accept an in-memory `bytes` value | No streaming reader or bounded file acquisition | [`step_part21.py`](../src/research_notes/step_part21.py) |
| Exact source reconstruction | Controlled subset | Accepted source-model fixtures reconstruct the original byte stream from retained tokens | Not established for every legal Part 21 spelling | [`test_step_part21.py`](../tests/test_step_part21.py) |
| Source coordinates | Implemented | Tokens retain character offsets, byte offsets, lines, and columns | Downstream B-Rep tables do not yet repeat every span directly | [`step_part21_token_inventory.csv`](../results/step_part21_token_inventory.csv) |
| Comments and whitespace | Controlled subset | Retained as source trivia in the unified token stream | Complete grammar coverage is not claimed | [`unified-part21-lexer-grammar-source-model.md`](../notes/unified-part21-lexer-grammar-source-model.md) |
| Strings and character encodings | Controlled subset | Selected legacy directives, direct UTF-8, and byte-versus-character coordinates are tested | Not a complete implementation of every edition-specific encoding rule | [`part21-grammar-conformance.md`](../notes/part21-grammar-conformance.md) |
| Numbers, enumerations, binary values, typed values, and omitted markers | Controlled subset | Selected valid and invalid lexical forms are parsed or rejected predictably | Complete Wirth Syntax Notation coverage is not claimed | [`step_conformance.py`](../src/research_notes/step_conformance.py) |
| Simple and complex entity instances | Controlled subset | Both record forms are structurally retained | Complete complex-instance schema mapping is deferred | [`step_exchange.py`](../src/research_notes/step_exchange.py) |
| Multiple DATA sections | Controlled subset | Section names, schema ownership, and selected cross-references are retained | External schema retrieval is not performed | [`test_step_exchange.py`](../tests/test_step_exchange.py) |
| Anchors, references, and signatures | Structural only | Syntax and source relationships are retained | External resources are not fetched and signatures are not verified | [`advanced-part21-exchange-parser-boundaries.md`](../notes/advanced-part21-exchange-parser-boundaries.md) |
| ZIP transport | Controlled subset | A bounded root entry is read in memory and unsafe archive paths fail closed | No general archive extraction, recursive containers, or archive-safety certification | [`test_step_conformance.py`](../tests/test_step_conformance.py) |
| Edition and implementation-level observations | Controlled subset | Selected Edition 1, 2, and 3 features are compared with the declared implementation level | Not an ISO certification suite | [`step_part21_conformance_observations.csv`](../results/step_part21_conformance_observations.csv) |
| Malformed-input routing | Implemented for declared cases | Syntax failures reject; configured work-limit failures quarantine | No fuzzing, memory-safety proof, or denial-of-service guarantee | [`step_part21.py`](../src/research_notes/step_part21.py) |
| Public-parser comparison | Research evidence | Selected fixtures are compared with pinned `steputils` and `step-file-parser` revisions | Neither parser is treated as a conformance oracle | [`step_part21_parser_comparison.csv`](../results/step_part21_parser_comparison.csv) |
| Arbitrary production STEP files | Not implemented | None | Coverage is limited to generated corpora and explicit subsets | [Claim boundaries](../README.md#claim-boundaries) |

## EXPRESS and Schema-Validation Capabilities

| Capability | Status | Current contract | Current boundary | Evidence |
| --- | --- | --- | --- | --- |
| Source-preserving EXPRESS tokens | Controlled subset | Retains selected ASCII identifiers, literals, comments, case, and source coordinates | Direct non-ASCII source and the complete lexical standard are outside the claim | [`express_schema.py`](../src/research_notes/express_schema.py) |
| Schema and type declarations | Controlled subset | Parses aliases, aggregates, selects, enumerations, and selected declaration structure | Does not prove that referenced names or expressions are valid | [`express_schema_inventory.csv`](../results/express_schema_inventory.csv) |
| Entity declarations | Controlled subset | Retains inheritance plus explicit, derived, and inverse attributes | Complete subtype constraints and executable semantics are deferred | [`test_express_schema.py`](../tests/test_express_schema.py) |
| Interfaces and algorithms | Structural only | Retains direct interfaces, constants, functions, procedures, and rules as inspectable declarations or envelopes | Algorithm bodies are not executed | [`express-lexer-parser-schema-model.md`](../notes/express-lexer-parser-schema-model.md) |
| Symbol tables and name lookup | Controlled subset | Resolves case-insensitive local names and detects missing, ambiguous, wrong-kind, and cyclic states | No guessed target is selected for unresolved names | [`express_symbols.csv`](../results/express_symbols.csv) |
| Direct imports | Controlled subset | Resolves selected `USE` and `REFERENCE` imports between schemas in the same source document | No external schema loading, implicit import, or transitive re-export | [`express_reference_resolution.csv`](../results/express_reference_resolution.csv) |
| Type aliases, selects, and aggregate bounds | Controlled subset | Resolves selected chains, members, literal bounds, and constant bounds | Complete assignment compatibility and expression typing are deferred | [`express_type_resolution.csv`](../results/express_type_resolution.csv) |
| Inheritance and redeclaration | Controlled subset | Resolves selected single, multiple, and diamond inheritance plus qualified redeclaration | Complete EXPRESS subtype semantics are not claimed | [`express_inheritance.csv`](../results/express_inheritance.csv) |
| Part 21 DATA-to-schema binding | Controlled subset | Binds selected in-document schemas and separates parsing, resolution, binding, and validation stages | Installed AP242 schemas are not loaded automatically | [`step_express_validation.py`](../src/research_notes/step_express_validation.py) |
| Instance parameter validation | Controlled subset | Checks selected scalar values, aggregates, optional and derived markers, enumerations, selects, references, and inheritance order | Constants, external values, full complex mapping, width expressions, and rules remain deferred | [`test_step_express_validation.py`](../tests/test_step_express_validation.py) |
| WHERE, UNIQUE, DERIVE, and executable rule evaluation | Not implemented | Source declarations may be retained | No constraint engine or rule interpreter exists | [Roadmap](brep-learning-roadmap.md) |
| Complete AP242 EXPRESS validation | Not implemented | None | Current AP242 interpretation uses one explicit controlled mapping instead | [`ap242-product-representation-paths.md`](../notes/ap242-product-representation-paths.md) |

## Physical Graph and AP242 Capabilities

| Capability | Status | Current contract | Current boundary | Evidence |
| --- | --- | --- | --- | --- |
| Deterministic node identity | Implemented | Assigns stable analysis-local node indices to DATA entities | Indices are not persistent CAD identifiers | [`step_graph.py`](../src/research_notes/step_graph.py) |
| Reference multiplicity and provenance | Implemented | Preserves each physical reference occurrence, parameter path, and source span as a distinct directed edge | An edge has no application meaning until interpreted | [`step_graph.json`](../results/step_graph.json) |
| Forward, reverse, and type queries | Implemented | Queries exact entity types and reference directions | No subtype reasoning is implied by a text match | [`test_step_graph.py`](../tests/test_step_graph.py) |
| Reachability, isolation, orphans, and cycles | Implemented | Provides bounded traversal and strongly connected components | These graph properties do not establish product or B-Rep semantics | [`generic-step-graph-query-api.md`](../notes/generic-step-graph-query-api.md) |
| Nonlocal reference representation | Structural only | Records external entity, external value, schema constant, and unresolved target scopes | Does not retrieve or authenticate targets | [`step_graph_edges.csv`](../results/step_graph_edges.csv) |
| Product-to-representation path | Controlled subset | Resolves selected product, formation, definition, shape, representation, item, context, dimension, and assigned-unit roles | Requires the exact controlled AP242 MIM schema identifier | [`ap242_product_paths.csv`](../results/ap242_product_paths.csv) |
| Direct representation-item classification | Controlled subset | Classifies selected placements, solid models, mapped items, and geometric items | Unknown items remain unclassified and quarantine the stronger claim | [`ap242_representation_items.csv`](../results/ap242_representation_items.csv) |
| Product and representation names | Controlled subset | Retains selected identifiers and names with source-linked semantic relations | No general property, document, material, or presentation-style model | [`ap242_semantic_relations.csv`](../results/ap242_semantic_relations.csv) |
| Assembly occurrence identity | Controlled subset | Distinguishes reusable definitions from `NEXT_ASSEMBLY_USAGE_OCCURRENCE` records and their reference designators | Alternate occurrence mappings are not supported | [`ap242_assembly_occurrences.csv`](../results/ap242_assembly_occurrences.csv) |
| Child-to-parent rigid placement | Controlled subset | Evaluates selected `ITEM_DEFINED_TRANSFORMATION` records between explicit `AXIS2_PLACEMENT_3D` frames | No arbitrary transformation select, scaling, reflection, or deformation | [`test_ap242_assembly.py`](../tests/test_ap242_assembly.py) |
| Nested assembly placement | Controlled subset | Composes selected occurrence matrices to root-relative paths while retaining occurrence identity | Does not transform or validate the referenced B-Rep itself | [`ap242_assembly_paths.csv`](../results/ap242_assembly_paths.csv) |
| Length-unit normalization | Controlled subset | Converts supported SI metre prefixes and selected conversion-based units to millimetres | General derived units, uncertainty, context mixing, and all unit dimensions are not implemented | [`ap242_assembly_units.csv`](../results/ap242_assembly_units.csv) |
| Assembly failure boundaries | Implemented for declared cases | Detects selected cycles, duplicate reference designators, reversed representation order, nonorthogonal frames, unresolved definitions, and work-limit exhaustion | Not a complete AP242 validity checker | [`ap242_assembly_diagnostics.csv`](../results/ap242_assembly_diagnostics.csv) |
| AP203 and AP214 semantic portability | Not implemented | A mismatched schema remains deferred | Similar entity names are not treated as equivalent evidence | [`ap242_path_observations.csv`](../results/ap242_path_observations.csv) |

## Current B-Rep Topology Capabilities

The v0.21.0 inspector reads selected topology relationships directly from the
exchange records. It does not use a geometry kernel. Accordingly, its surface
values are declared parameters, not independently evaluated geometric facts.

| Capability | Status | Current output | Missing evaluation | Evidence |
| --- | --- | --- | --- | --- |
| Faces | Structural only | Analysis-local index, Part 21 entity ID, supporting-surface ID, bounds, ownership, and adjacency | Trimmed-domain geometry and tolerance validity | [`step_brep_faces.csv`](../results/step_brep_faces.csv) |
| Edges | Structural only | Analysis-local index, endpoint vertex IDs, supporting-curve ID and type, use count, incident faces, free/nonmanifold flags | Vertex coordinates, edge parameters, curve length, p-curves, and seam evaluation | [`step_brep_edges.csv`](../results/step_brep_edges.csv) |
| Shells | Structural only | Face membership, edge counts, declared open/closed state, incidence closure, and parent solids | Orientability, geometric closure, tolerance-aware sewing, and validity | [`step_brep_shells.csv`](../results/step_brep_shells.csv) |
| Solids | Structural only | Outer-shell relationship, name, face count, and edge count for selected solid types | Inner void evaluation, volume, centroid, inertia, signed orientation, and kernel validity | [`step_brep_solids.csv`](../results/step_brep_solids.csv) |
| Surface declarations | Controlled subset | Plane, cylinder, cone, sphere, torus, and selected B-spline declarations | Evaluation outside the generated catalog or proof that trimming produces a valid face | [`test_step_brep.py`](../tests/test_step_brep.py) |
| Broken topology routes | Implemented for declared cases | Missing references quarantine, duplicate entity IDs reject, and selected wrong-type relationships quarantine | No broad corrupt-file recovery or healing | [`step_brep_topology_observations.csv`](../results/step_brep_topology_observations.csv) |
| Visual evidence | Research evidence | Generated tetrahedron and surface-catalog previews support human inspection | The previews are not a kernel rendering or geometric proof | [Sample catalog](step-sample-catalog.md) |

## Face-Level Field Matrix

This table maps the intended face report to the fields that are actually
available at v0.31.0.

| Requested field | Current status | What can be reported now | What is still missing | Planned stage |
| --- | --- | --- | --- | --- |
| Analysis-local face index | Implemented | Deterministic `face_index` ordered by Part 21 entity ID | Persistence across export, editing, Boolean operations, or healing | v0.37.0 report contract retains the local-only warning |
| Parent solid and shell | Controlled subset | Parent shell and outer-solid entity IDs for selected topology patterns | Complete void-shell ownership and arbitrary schema mapping | v0.35.0–v0.37.0 |
| Surface type | Controlled subset | Declared plane, cylinder, cone, sphere, torus, and selected B-spline categories | Kernel classification of arbitrary support surfaces | v0.32.0 |
| Face orientation | Structural only | The face's declared `same_sense` value | Combined face, bound, edge-use, surface, and shell orientation semantics | v0.34.0–v0.35.0 |
| Area | Not implemented | None | Trimmed-surface integration and independently checked truth | v0.32.0 |
| Centroid | Not implemented | None | Area-weighted trimmed-face centroid | v0.32.0 |
| UV bounds | Not implemented | None | Valid parameter domain, periodic wrap handling, and trim-aware bounds | v0.32.0–v0.34.0 |
| Representative normal | Not implemented | A declared analytic-surface axis may be retained, but it is not reported as a face normal | Evaluated point, derivative convention, face orientation, and degeneracy handling | v0.32.0 |
| Plane normal | Structural only | Declared placement axis for the generated plane catalog | Independent unit-vector validation and oriented face normal | v0.32.0 |
| Cylinder axis and radius | Structural only | Declared placement origin, axis, reference direction, and radius | Unit normalization, tolerance comparison, and trimmed-face verification | v0.32.0 |
| Cone parameters | Structural only | Declared origin, axis, reference direction, radius, and semi-angle | Independent surface evaluation and unit-aware validation | v0.32.0 |
| Sphere parameters | Structural only | Declared center placement and radius | Independent surface evaluation and unit-aware validation | v0.32.0 |
| Torus parameters | Structural only | Declared placement, major radius, and minor radius | Independent surface evaluation and unit-aware validation | v0.32.0 |
| B-spline parameters | Structural only | Selected declared U and V degrees | Control points, weights, knots, multiplicities, closure, rational evaluation, and continuity | v0.32.0–v0.33.0 |
| Outer and inner wire counts | Controlled subset | Counts `FACE_OUTER_BOUND` separately from other `FACE_BOUND` records | Ordered wire semantics, nested islands, degeneracy, and periodic wrapping | v0.34.0 |
| Boundary-edge count | Controlled subset | Counts distinct selected `EDGE_CURVE` references used by a face | Orientation-aware edge uses, repeated seam use, and p-curve agreement | v0.33.0–v0.34.0 |
| Free and nonmanifold edge evidence | Controlled subset | Counts incidence of selected edge IDs across parsed faces | Tolerance-aware geometric coincidence and full nonmanifold classification | v0.35.0 |
| Adjacent face indices | Controlled subset | Reports faces sharing a selected edge entity | Geometric adjacency without a shared topological edge and persistent identity | v0.37.0 |
| Face tolerance | Not implemented | None | Declared and kernel-normalized tolerance with provenance | v0.32.0 |
| Face name | Not implemented | Product, representation, and solid names exist in separate controlled outputs | General face-name attribution and its source relationship | v0.37.0 |
| Face color | Not implemented | None | Presentation-style traversal, inheritance/override policy, and source attribution | v0.37.0 |
| Direct source provenance | Partial | Entity IDs allow a join to the source model; AP242 relations retain direct spans | Face CSV rows do not yet include every originating source span | v0.37.0 |

## Geometry, Modeling, Interoperability, and AI Gaps

| Capability | Current status | Earliest roadmap stage | Required evidence before a claim |
| --- | --- | --- | --- |
| Geometry-kernel selection | Implemented as research evidence | v0.31.0 | Eight candidates, six gates, installed-package audit, optional dependency, and one deterministic box round trip; binary redistribution remains excluded |
| Evaluated face geometry and tolerance | Not implemented | v0.32.0 | Synthetic analytic truth plus independent numerical checks |
| Curves, p-curves, seams, and periodicity | Not implemented | v0.33.0 | 3D/2D agreement under declared tolerances |
| Wire ordering, trimming, holes, and oriented faces | Not implemented | v0.34.0 | Controlled reversed, periodic, degenerate, and nested-bound cases |
| Shell and solid validity | Not implemented | v0.35.0 | Independent incidence, orientation, closure, Euler, volume, and kernel reports |
| Sewing and healing | Not implemented | v0.36.0 | Original-versus-repaired evidence and a complete modification log |
| Complete face-level report | Not implemented | v0.37.0 | Evaluated fields, attribution, source provenance, and explicit local identity |
| Tessellation and interactive viewing | Not implemented | v0.38.0 | Meshing controls and triangle-to-face provenance |
| Primitive and surface construction | Not implemented | v0.39.0 | Known parameters, export, re-import, and measured comparison |
| Profiles, extrusion, and revolution | Not implemented | v0.40.0 | Parameter-driven recompute with known construction truth |
| Sweeps, lofts, and Boolean operations | Not implemented | v0.41.0–v0.42.0 | Controlled success and failure conditions across tolerances |
| Fillets, chamfers, and topology history | Not implemented | v0.43.0 | Generated, modified, deleted, split, and merged-shape evidence |
| STEP import-edit-export preservation | Not implemented | v0.44.0 | Structure, semantics, geometry, topology, attribute, and tolerance comparison |
| Independent kernel portability | Not implemented | v0.45.0 | Fixed corpus evaluated by independently selected implementations |
| Resource-bounded native 3D intake | Not implemented | v0.46.0 | Isolation and budgets for parsing, archives, kernels, topology, meshes, and time |
| Face-adjacency descriptors and feature recognition | Not implemented | v0.47.0–v0.48.0 | Attributed graphs and deterministic rules over known synthetic history |
| AI-ready 3D dataset | Not implemented | v0.49.0 | Grouped splits, leakage checks, labels, and complete provenance |
| Learned 3D assistance | Not implemented | v0.50.0 | Baselines, calibration, robustness, evidence links, and abstention |
| Parametric feature model and constraints | Not implemented | v0.51.0–v0.54.0 | Versioned feature graphs, solver states, and deterministic recompute |
| STEP-to-feature reconstruction | Not implemented | v0.55.0 | Residuals, ambiguity, alternatives, confidence, and no design-history claim |
| Assisted parametric modeling tool | Not implemented | v0.56.0 | Bounded import, inspection, candidate selection, editing, recompute, comparison, and export |

## Safe Present-Day Uses

- Study and test selected Part 21 syntax with exact source provenance.
- Build deterministic physical-reference graphs for controlled or prequalified
  inputs.
- Inspect selected simple B-Rep topology declarations and edge incidence.
- Resolve the controlled AP242 product and assembly paths documented by the
  generated corpora.
- Reproduce one headless OCCT box construction and STEP round trip with the
  optional pinned geometry dependency.
- Reproduce every published STEP/EXPRESS observation and inspect its CSV, JSON,
  figure, and test evidence.
- Extend the parser carefully by adding a generated positive/negative corpus,
  explicit resource limits, and a narrow claim boundary.

## Unsafe or Unsupported Present-Day Uses

- Treating parser acceptance as ISO, AP242, or B-Rep conformance.
- Treating a declared surface axis as an evaluated face normal.
- Using the current tables for area, centroid, volume, inertia, collision,
  clearance, or tolerance decisions.
- Editing, healing, tessellating, rendering, or exporting arbitrary CAD models.
- Processing untrusted arbitrary STEP files as if resource use or native-code
  safety had been established.
- Claiming recovered sketches, dimensions, feature history, or design intent
  from an imported STEP model.
- Feeding current outputs into an AI system without a separate dataset, label,
  split, calibration, and abstention contract.

## Reproduction

Run the current STEP and EXPRESS test surface:

```bash
python -m pip install -e ".[geometry,test]"
python -m pytest \
  tests/test_step_part21.py \
  tests/test_step_exchange.py \
  tests/test_step_conformance.py \
  tests/test_step_brep.py \
  tests/test_express_schema.py \
  tests/test_express_resolution.py \
  tests/test_step_express_validation.py \
  tests/test_step_graph.py \
  tests/test_ap242_paths.py \
  tests/test_ap242_assembly.py \
  tests/test_geometry_kernel.py
```

The complete generated-input catalog is in the
[STEP sample and preview catalog](step-sample-catalog.md). The sequence from
current limitations to modeling and AI is in the
[STEP mastery roadmap](brep-learning-roadmap.md).
