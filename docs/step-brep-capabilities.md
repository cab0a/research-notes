# STEP and B-Rep Capability Matrix

## 日本語概要

本書は、v0.36.0時点のSTEP・EXPRESS・AP242・B-rep機能を、実装済み、限定対応、構造のみ、研究実証、未実装に分けて整理します。原文を保持したPart 21解析、限定したEXPRESS検証、物理参照グラフ、AP242製品・組立経路、任意のOpen CASCADE形状計算経路に加え、面・辺・外周・内周・切り取り、7形状に限定した外殻・立体の妥当性、3水準の隙間と3水準の縫合許容差、正常外殻と1面反転外殻の向き修復、許容差を過度に縮小する異常対照を検証しました。許容差による閉包は隙間の除去を意味せず、STEP再読込による正常化も不正なメモリ内操作の判断を取り消しません。頂点近傍の多様体性、自己交差、空洞と内殻、読込・修復前後の形状対応、一般的な修復、形状編集、AIモデルは未実装で、第三者バイナリの再配布も対象外です。詳細な根拠と予定版は以下の英語本文に示します。

---

## English Summary

This document states what the STEP and B-Rep track can and cannot claim at
v0.36.0. It separates syntax recognition, schema validation, physical-reference
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
| B-Rep topology | Controlled subset | Inventory selected declarations and evaluate incidence, components, closure, orientability, Euler, and signed-volume gates for seven synthetic shell/solid controls, then evaluate tolerance-mediated sewing for three box gaps | General vertex-manifold, self-intersection, nested-shell, or arbitrary repair validity |
| AP242 product paths | Controlled subset | Resolve one exact schema identifier through selected product, shape, representation, item, context, and unit roles | AP203/AP214 portability, complete AP242 coverage, or geometric validity |
| AP242 assemblies | Controlled subset | Separate definitions from occurrences, evaluate selected rigid placements, compose nested paths, and normalize supported length units | Arbitrary transformation operators, all unit forms, moved B-Rep evaluation, or persistent CAD identity |
| Geometry backend | Research evidence | One optional pinned OCCT route constructs, evaluates, sews, selectively reorients, writes, and reads small analytic face, edge, wire, shell, and solid corpora headlessly | Arbitrary trimmed geometry, independent-kernel validation, cross-platform portability, redistribution approval, general healing, or general STEP compatibility |
| Evaluated face geometry | Controlled subset | Closed-form truth checks planar frames, cylindrical faces, and a sphere, including holes, face reversal, restrictions, and point classification before and after STEP exchange | Arbitrary curved trims, invalid loops, splines, shell-relative outwardness, and general tolerance validity |
| Evaluated edge and wire geometry | Controlled subset | Closed-form truth checks line and circle edges, p-curves, parameter spans, ordered outer and inner wires, periodic seams, and sphere-pole degenerate edges before and after STEP exchange | Splines, curved-loop integration, invalid or nested loops, non-manifold uses, adaptive checks, and general repair validity |
| Evaluated shell and solid validity | Controlled subset | Seven validity conditions compare independent topology and volume gates; a separate 3-by-3 gap/tolerance matrix and two orientation-repair controls record topology, stored tolerances, support geometry, and backend reports | Vertex-neighborhood manifoldness, self-intersection, nested voids, arbitrary geometry, or general repair |
| Inspection artifacts | Implemented | Regenerate synthetic STEP/EXPRESS inputs, CSV, JSON, and diagnostic figures deterministically | A general end-user CAD inspector or an interactive 3D viewer |
| Geometry modeling | Research evidence | The v0.31 through v0.36 experiments construct bounded analytic controls and apply one sewing sweep plus targeted shell-orientation repair for exchange studies | A supported modeling API, parameter editing, sketches, sweeps, Boolean operations, general healing, and evaluated export preservation |
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
| Faces | Partial | The dependency-free parser reports selected declarations and ownership; the optional backend evaluates four controlled trimmed faces with outer/inner loops, restrictions, area, centroid, orientation, and point classification | A unified arbitrary-file report, curved or invalid trims, shell-relative outwardness, and general tolerance validity | [`wire_trimming_face_observations.csv`](../results/wire_trimming_face_observations.csv) |
| Edges | Partial | The dependency-free parser reports endpoint IDs, declared curve type, uses, incident faces, and incidence; the optional controlled backend reports evaluated line/circle type, length, parameter range, oriented vertex parameters, p-curves, seams, and sphere-pole degeneracy | A unified arbitrary-file report, splines, general singularities, and general consistency policy | [`wire_trimming_edge_uses.csv`](../results/wire_trimming_edge_uses.csv) |
| Shells | Controlled subset | Declared membership plus seven validity controls and a 3-by-3 box-gap sewing matrix with face components, edge-use incidence, closure, orientability, stored tolerances, support-plane equations, and shell-specific statuses | Vertex-neighborhood manifoldness, self-intersection, nested shells, arbitrary geometry, and general healing | [`shell_solid_observations.csv`](../results/shell_solid_observations.csv), [`tolerance_sewing_observations.csv`](../results/tolerance_sewing_observations.csv) |
| Solids | Controlled subset | Outer-shell structure plus box and torus controls with signed volume, analytic magnitude, eligibility gates, generic validity, and STEP-stage comparison | General void shells, centroid, inertia, containment, arbitrary geometry, and cross-kernel validity | [`shell_solid_observations.csv`](../results/shell_solid_observations.csv) |
| Surface declarations | Controlled subset | Plane, cylinder, cone, sphere, torus, and selected B-spline declarations | Evaluation outside the generated catalog or proof that trimming produces a valid face | [`test_step_brep.py`](../tests/test_step_brep.py) |
| Broken topology routes | Implemented for declared cases | Missing references quarantine, duplicate entity IDs reject, and selected wrong-type relationships quarantine | No broad corrupt-file recovery or healing | [`step_brep_topology_observations.csv`](../results/step_brep_topology_observations.csv) |
| Visual evidence | Research evidence | Generated tetrahedron and surface-catalog previews support human inspection | The previews are not a kernel rendering or geometric proof | [Sample catalog](step-sample-catalog.md) |

## Face-Level Field Matrix

This table maps the intended face report to the fields that are actually
available at v0.36.0.

| Requested field | Current status | What can be reported now | What is still missing | Planned stage |
| --- | --- | --- | --- | --- |
| Analysis-local face index | Implemented | Deterministic `face_index` ordered by Part 21 entity ID | Persistence across export, editing, Boolean operations, or healing | v0.39.0 correspondence study; v0.41.0 report contract retains the local-only warning |
| Parent solid and shell | Controlled subset | Parent shell and outer-solid entity IDs for selected topology patterns; controlled backend rows separately report shell and solid counts | Complete per-face imported ownership, void-shell ownership, and arbitrary schema mapping | v0.38.0 void ownership; v0.41.0 report contract |
| Surface type | Controlled subset | Declared analytic categories plus kernel classification for controlled planes, cylinders, and one sphere | Kernel classification of arbitrary or nonanalytic support surfaces | Future corpus expansion |
| Face orientation | Controlled subset | Face reversal flips loop winding; shell-level parity detects one inconsistent box face, and targeted repair distinguishes a valid no-op from the one-face-reversed control | Nested-loop, non-manifold vertex neighborhoods, nested-shell material side, and arbitrary imported face correspondence | v0.37.0–v0.39.0 |
| Area | Controlled subset | Exact-surface area agrees with independent truth for rectangular planes, planar holes, cylindrical faces, and one whole sphere | Arbitrary curved trims, splines, invalid or repaired faces | Future corpus expansion |
| Centroid | Controlled subset | Area centroid agrees with independent plane-hole, cylinder, and sphere formulas | Arbitrary curved trims, splines, invalid or repaired faces | Future corpus expansion |
| UV bounds | Controlled subset | Restricted and support bounds are separated for planes, a full cylinder, and a whole sphere; periodic seams retain both U branches | Seam-crossing intervals outside the canonical full period and general curved trim-aware bounds | Future corpus expansion |
| Representative normal | Controlled subset | Derivative-cross-product support normals and orientation-adjusted normals are reported at the UV midpoint | Interior-point selection, degeneracy handling, and whole-face normal variation | v0.33.0–v0.34.0 |
| Plane normal | Controlled subset | Two plane support normals are checked independently; the reversed face flips only its oriented normal | Arbitrary plane placement, unit, and shell-relative outward validation | Future corpus expansion |
| Cylinder axis and radius | Controlled subset | One partial and one full cylinder use independent frames and radii; the full cylinder exposes a periodic seam | Seam-crossing intervals, transformed units, conical cases, and arbitrary trims | Future corpus expansion |
| Cone parameters | Structural only | Declared origin, axis, reference direction, radius, and semi-angle | Independent surface evaluation and unit-aware validation | Future analytic corpus |
| Sphere parameters | Controlled subset | One radius-3 sphere has independent area, centroid, UV-domain, seam, pole-degeneracy, and classification evidence | Arbitrary placement, units, partial-sphere trims, and cross-kernel validation | Future corpus expansion |
| Torus parameters | Structural only | Declared placement, major radius, and minor radius | Independent surface evaluation and unit-aware validation | Future analytic corpus |
| B-spline parameters | Structural only | Selected declared U and V degrees | Control points, weights, knots, multiplicities, closure, rational evaluation, and continuity | v0.33.0 onward |
| Outer and inner wire counts | Controlled subset | Two planar frames each expose one outer and one inner wire; cylinder and sphere expose one outer wire; the kernel observation is kept separate from writer entity-name counts | Nested islands, arbitrary schemas, ambiguous or invalid loops | Future corpus expansion |
| Boundary-edge count | Controlled subset | Each loop reports ordered occurrence and unique-edge counts; cylinder and sphere distinguish three unique edges from four uses; the sphere includes two degenerate uses | General curved or invalid loops, splines, and arbitrary schemas | Future corpus expansion |
| Free and nonmanifold edge evidence | Controlled subset | Source parsing counts selected incidence; the backend corpus records one-use boundary edges, two-use pairs, and a controlled three-use nonmanifold edge before and after STEP exchange | Vertex-neighborhood manifoldness, tolerance-aware geometric coincidence, self-intersection, and full nonmanifold classification | v0.37.0 |
| Adjacent face indices | Controlled subset | Reports faces sharing a selected edge entity | Geometric adjacency without a shared topological edge and persistent identity | v0.39.0 correspondence; v0.41.0 report contract |
| Face tolerance | Controlled subset | Separates requested sewing tolerance from 550 stage-local vertex, edge, and face tolerance rows across constructed, sewn, repaired, capped, and imported controls | General writer/reader behavior, arbitrary gap geometry, persistent source identity, and application policy | v0.36.0 bounded study; future corpus expansion |
| Face name | Not implemented | Product, representation, and solid names exist in separate controlled outputs | General face-name attribution and its source relationship | v0.41.0 |
| Face color | Not implemented | None | Presentation-style traversal, inheritance/override policy, and source attribution | v0.41.0 |
| Direct source provenance | Partial | Entity IDs allow a join to the source model; AP242 relations retain direct spans | Face CSV rows do not yet include every originating source span or post-operation correspondence | v0.39.0 correspondence; v0.41.0 report contract |

## Geometry, Modeling, Interoperability, and AI Gaps

| Capability | Current status | Earliest roadmap stage | Required evidence before a claim |
| --- | --- | --- | --- |
| Geometry-kernel selection | Implemented as research evidence | v0.31.0 | Eight candidates, six gates, installed-package audit, optional dependency, and one deterministic box round trip; binary redistribution remains excluded |
| Evaluated face geometry and tolerance | Controlled subset | v0.32.0 | Two planes and one cylinder checked against analytic truth; arbitrary trim and general tolerance claims remain excluded |
| Curves, p-curves, seams, and periodicity | Controlled subset | v0.33.0 | Eleven analytic edges, twelve oriented uses, closed-form line/circle truth, UV paths, sampled 3D agreement, and one full-cylinder seam; splines remain excluded |
| Wire ordering, trimming, holes, and oriented faces | Controlled subset | v0.34.0 | Two planar frames, one cylinder, and one sphere with independent material and signed-loop truth, point classification, connection-ordered traversal, seams, and pole degeneracy; arbitrary curved, invalid, and nested cases remain excluded |
| Shell and solid validity | Controlled subset | v0.35.0 | Seven controls provide independent incidence, components, orientability, closure, Euler, volume eligibility, signed volume, and generic/shell-specific backend reports; arbitrary topology, vertex manifoldness, self-intersection, nested voids, and repair remain excluded |
| Tolerance-mediated sewing and targeted orientation repair | Controlled subset | v0.36.0 | Three gaps by three requested tolerances, 17 stage observations, 550 subshape-tolerance rows, positive and negative orientation controls, a rejected tolerance-cap operation, and STEP-stage comparison; no universal threshold or general healing claim |
| Vertex manifoldness and self-intersection | Not implemented | v0.37.0 | Vertex-neighborhood topology, geometric intersection, and contact-versus-crossing controls |
| Voids, inner shells, and composite solids | Not implemented | v0.38.0 | Material-side orientation, containment depth, multiple regions, and independently known additive or subtractive volume |
| Correspondence across import and healing | Not implemented | v0.39.0 | Preserved, changed, split, merged, unmatched, and ambiguous face/edge mappings without a persistent-identity claim |
| Rule-based feature recognition | Not implemented | v0.40.0 | Holes, steps, slots, chamfers, and fillets compared with synthetic construction truth and false-positive controls |
| Complete face-level report | Not implemented | v0.41.0 | Evaluated fields, attribution, source provenance, and explicit local identity |
| Tessellation and interactive viewing | Not implemented | v0.42.0 | Meshing controls and triangle-to-face provenance |
| Primitive and surface construction | Not implemented | v0.43.0 | Known parameters, export, re-import, and measured comparison |
| Profiles, extrusion, and revolution | Not implemented | v0.44.0 | Parameter-driven recompute with known construction truth |
| Sweeps, lofts, and Boolean operations | Not implemented | v0.45.0–v0.46.0 | Controlled success and failure conditions across tolerances |
| Fillets, chamfers, and topology history | Not implemented | v0.47.0 | Generated, modified, deleted, split, and merged-shape evidence |
| STEP import-edit-export preservation | Not implemented | v0.48.0 | Structure, semantics, geometry, topology, attribute, and tolerance comparison |
| Independent kernel portability | Not implemented | v0.49.0 | Fixed corpus evaluated by independently selected implementations |
| Resource-bounded native 3D intake | Not implemented | v0.50.0 | Isolation and budgets for parsing, archives, kernels, topology, meshes, and time |
| Face-adjacency descriptors | Not implemented | v0.51.0 | Attributed graphs with source and calculation provenance |
| Feature-recognition robustness | Not implemented | v0.52.0 | Deterministic confusion counts and abstention under tolerance, size, orientation, import, and healing perturbations |
| AI-ready 3D dataset | Not implemented | v0.53.0 | Grouped splits, leakage checks, labels, and complete provenance |
| Learned 3D assistance | Not implemented | v0.54.0 | Baselines, calibration, robustness, evidence links, and abstention |
| Parametric feature model and constraints | Not implemented | v0.55.0–v0.58.0 | Versioned feature graphs, solver states, and deterministic recompute |
| STEP-to-feature reconstruction | Not implemented | v0.59.0 | Residuals, ambiguity, alternatives, confidence, and no design-history claim |
| Assisted parametric modeling tool | Not implemented | v0.60.0 | Bounded import, inspection, candidate selection, editing, recompute, comparison, and export |

## Safe Present-Day Uses

- Study and test selected Part 21 syntax with exact source provenance.
- Build deterministic physical-reference graphs for controlled or prequalified
  inputs.
- Inspect selected simple B-Rep topology declarations and edge incidence.
- Resolve the controlled AP242 product and assembly paths documented by the
  generated corpora.
- Reproduce one headless OCCT box construction and STEP round trip with the
  optional pinned geometry dependency.
- Reproduce controlled face-level area, centroid, UV-bound, representative
  point, normal, surface-frame, radius, orientation, and tolerance-stage
  observations for the v0.32 analytic corpus.
- Reproduce controlled line and circle edge types, analytic lengths, parameter
  spans, oriented vertex traversal, p-curve UV paths, and one cylindrical seam
  for the v0.33 analytic corpus.
- Reproduce controlled wire ordering, holes, face reversal, periodic seams,
  sphere-pole degeneracy, and material classification for the v0.34 corpus.
- Reproduce incidence, components, closure, orientation parity, Euler, and
  signed-volume eligibility for the seven v0.35 shell and solid controls.
- Reproduce the v0.36 gap/tolerance closure matrix, stage-local subshape
  tolerances, support-plane invariants, orientation-repair controls, rejected
  tolerance cap, and STEP re-import normalization observation.
- Reproduce every published STEP/EXPRESS observation and inspect its CSV, JSON,
  figure, and test evidence.
- Extend the parser carefully by adding a generated positive/negative corpus,
  explicit resource limits, and a narrow claim boundary.

## Unsafe or Unsupported Present-Day Uses

- Treating parser acceptance as ISO, AP242, or B-Rep conformance.
- Treating a declared surface axis as an evaluated face normal.
- Using the controlled face results as evidence for arbitrary area, centroid,
  volume, inertia, collision, clearance, or manufacturing-tolerance decisions.
- Treating `SameParameter` flags or the fixed 17-sample edge residual as proof
  of arbitrary p-curve consistency or as a universal CAD threshold.
- Treating the controlled sewing and orientation-repair results as a general
  healing policy or proof of recovered design intent.
- Editing, tessellating, rendering, or exporting arbitrary production CAD
  models through a supported end-user workflow.
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
  tests/test_geometry_kernel.py \
  tests/test_face_geometry.py \
  tests/test_edge_geometry.py \
  tests/test_wire_trimming.py \
  tests/test_shell_solid_validity.py \
  tests/test_tolerance_sewing_healing.py
python experiments/run_tolerance_sewing_healing.py
```

The complete generated-input catalog is in the
[STEP sample and preview catalog](step-sample-catalog.md). The sequence from
current limitations to modeling and AI is in the
[STEP mastery roadmap](brep-learning-roadmap.md).
