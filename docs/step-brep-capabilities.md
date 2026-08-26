# STEP and B-Rep Capability Matrix

## 日本語概要

本書は、v0.55.0時点のSTEP・EXPRESS・AP242・B-rep機能を、実装済み、限定対応、構造のみ、研究実証、未実装に分けます。v0.55.0は基準面、寸法、スケッチ、形状操作、結果形状、依存関係、読込候補を版番号付き非巡回グラフとして表します。拘束条件と一般再計算は未実装です。詳細は英語本文に示します。

---

## English Summary

This document states what the STEP and B-Rep track can and cannot claim across
55 studies through v0.55.0. It separates syntax recognition, schema validation, physical-reference
graphs, application semantics, declared topology, evaluated geometry, and
modeling so that success at one layer is not presented as success at another.
v0.56.0 and later roadmap stages remain unimplemented.

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
| B-Rep topology | Controlled subset | Inventory selected declarations; evaluate shell/solid invariants, tolerance-mediated sewing, vertex links, shell containment, material-side orientation, solid face adjacency, and stage-local face and edge descriptors for bounded controls | General curved or arbitrary vertex-manifold, self-intersection, nonconvex containment, nested material regions, repair validity, or persistent identity |
| AP242 product paths | Controlled subset | Resolve one exact schema identifier through selected product, shape, representation, item, context, and unit roles | AP203/AP214 portability, complete AP242 coverage, or geometric validity |
| AP242 assemblies | Controlled subset | Separate definitions from occurrences, evaluate selected rigid placements, compose nested paths, and normalize supported length units | Arbitrary transformation operators, all unit forms, moved B-Rep evaluation, or persistent CAD identity |
| Geometry backend | Research evidence | One optional pinned OCCT route constructs, evaluates, sews, selectively reorients, intersects, classifies shell containment, performs one same-domain unification, writes, and reads small analytic and polyhedral corpora headlessly | Arbitrary trimmed geometry, independent-kernel validation, cross-platform portability, redistribution approval, general healing, persistent naming, or general STEP compatibility |
| Evaluated face geometry | Controlled subset | Closed-form truth checks planar frames, cylindrical faces, and a sphere, including holes, face reversal, restrictions, and point classification before and after STEP exchange | Arbitrary curved trims, invalid loops, splines, shell-relative outwardness, and general tolerance validity |
| Evaluated edge and wire geometry | Controlled subset | Closed-form truth checks line and circle edges, p-curves, parameter spans, ordered outer and inner wires, periodic seams, and sphere-pole degenerate edges before and after STEP exchange | Splines, curved-loop integration, invalid or nested loops, non-manifold uses, adaptive checks, and general repair validity |
| Evaluated shell and solid validity | Controlled subset | Seven validity controls, a 3-by-3 sewing matrix, bounded vertex-link counterexamples, and ten material-region controls separate topology, containment, orientation, partial overlap, volume, and composite-solid connectivity | General curved-shell self-intersection, nonconvex containment, arbitrary nesting depth, arbitrary geometry, or general repair |
| Vertex manifoldness and geometric relationships | Controlled subset | Vertex-link components and degree classify generated tetrahedral neighborhoods; one-argument interference records cover separated/crossing edges and faces; minimum distance, common parts, and sections distinguish disjoint, point, curve, surface, and volume relations | Arbitrary curved or spline shapes, tangent or near-contact cases, tolerance policy, and independent-kernel proof |
| Face and edge correspondence | Controlled subset | Four planar/open-line controls record 56 face descriptors, 37 face candidates, 35 face relations, 122 edge descriptors, 79 edge candidates, and 75 edge relations; STEP import resolves 23 faces and 47 edges one-to-one while two faces and eight edges abstain, and all 10 face plus 20 edge healing relations agree with separate operation history | Persistent topological identity, one-to-many splits, generated-result controls, moving frames, curved or closed edges, semantic provenance, or design-history recovery |
| Rule-based feature recognition | Controlled subset | Nine generated solids and STEP fixtures produce 136 face rows, 282 adjacency rows, 14 candidate rows, 18 stage observations, and two equivalent-boundary rows; all 14 candidates match controlled classification and dimensions, while two negative controls produce no false positives | Feature-history reconstruction, design-intent proof, interacting or arbitrary features, or a general recognizer |
| Face-level reports | Controlled subset | A versioned 60-field CSV records 13 faces per stage across six surface families with parent lists, geometry, parameters, boundaries, adjacency, tolerance, and attributed metadata source | Persistent identity, arbitrary-file coverage, XCAF metadata traversal, shell-relative material orientation, or cross-kernel portability |
| Inspection artifacts | Implemented | Regenerate synthetic STEP/EXPRESS inputs, CSV, JSON, and diagnostic figures deterministically | A general end-user CAD inspector or an interactive 3D viewer |
| Geometry modeling | Research evidence | Bounded controls cover primitives, profiles, extrusion, revolution, sweeps, lofts, one point-grid surface, seven Boolean cases, and fillet/chamfer history on one box edge | A supported modeling API, parameter editing, sketches, arbitrary local-feature behavior, history composition, general healing, persistent naming, and evaluated export preservation |
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
| Faces | Controlled subset | The dependency-free parser reports selected declarations and ownership; the optional backend now emits a unified 60-field report for 26 controlled rows across plane, cylinder, cone, sphere, torus, and B-spline faces, in addition to v0.39 correspondence and v0.40 feature evidence | Arbitrary-file coverage, invalid-face reporting, shell-relative material outwardness, general tolerance validity, persistent naming, XCAF attribution, and cross-kernel portability | [`face_analysis_report.csv`](../results/face_analysis_report.csv), [`shape_correspondence_relations.csv`](../results/shape_correspondence_relations.csv), [`feature_face_attributes.csv`](../results/feature_face_attributes.csv) |
| Edges | Partial | The dependency-free parser reports endpoint IDs, declared curve type, uses, incident faces, and incidence; the optional backend evaluates line/circle geometry, p-curves, seams, and degeneracy, while v0.39 records 122 stage-local descriptors, 79 geometry candidates with separately retained incident-face support, and 75 inferred or history-compared relations for open line edges | A unified arbitrary-file report, splines, closed-edge correspondence, general singularities, general consistency policy, and persistent naming | [`wire_trimming_edge_uses.csv`](../results/wire_trimming_edge_uses.csv), [`shape_correspondence_edge_relations.csv`](../results/shape_correspondence_edge_relations.csv) |
| Shells | Controlled subset | Declared membership, seven validity controls, a 3-by-3 box-gap sewing matrix, tetrahedral vertex links, and 44 shell-role observations separate incidence, neighborhoods, closure, orientation, tolerances, containment depth, and backend status | Curved or degenerate neighborhoods, general self-intersection, nonconvex or unbounded containment, arbitrary nesting, and general healing | [`shell_solid_observations.csv`](../results/shell_solid_observations.csv), [`tolerance_sewing_observations.csv`](../results/tolerance_sewing_observations.csv), [`manifold_intersection_observations.csv`](../results/manifold_intersection_observations.csv), [`shell_role_observations.csv`](../results/shell_role_observations.csv) |
| Solids | Controlled subset | Box and torus validity controls plus ten material-region controls evaluate signed and analytic volume, void containment, material islands, shared-face adjacency, connected components, container type, and STEP-stage change | General curved or nonconvex voids, centroid, inertia, arbitrary cellular complexes, or cross-kernel validity | [`shell_solid_observations.csv`](../results/shell_solid_observations.csv), [`solid_region_observations.csv`](../results/solid_region_observations.csv), [`solid_adjacency_observations.csv`](../results/solid_adjacency_observations.csv) |
| Geometric contact and intersection | Controlled subset | Generated shape pairs distinguish disjoint, point, curve, surface, volume-overlap, and transverse-face-crossing relations; four aggregate controls separately record single-argument edge/edge, edge/face, and face/face interference evidence | Self-crossing of one parametric curve or supporting surface, general interference enumeration, curved or tangent cases, tolerance-sensitive near contact, and an application acceptance policy | [`shape_pair_relations.csv`](../results/shape_pair_relations.csv), [`self_intersection_observations.csv`](../results/self_intersection_observations.csv) |
| Surface declarations | Controlled subset | Plane, cylinder, cone, sphere, torus, and selected B-spline declarations plus evaluated v0.41 support-family and parameter rows | Evaluation outside the generated catalog or proof that arbitrary trimming produces a valid face | [`face_analysis_report.csv`](../results/face_analysis_report.csv), [`test_step_brep.py`](../tests/test_step_brep.py) |
| Broken topology routes | Implemented for declared cases | Missing references quarantine, duplicate entity IDs reject, and selected wrong-type relationships quarantine | No broad corrupt-file recovery or healing | [`step_brep_topology_observations.csv`](../results/step_brep_topology_observations.csv) |
| Visual evidence | Research evidence | Generated tetrahedron and surface-catalog previews support human inspection | The previews are not a kernel rendering or geometric proof | [Sample catalog](step-sample-catalog.md) |

## Face-Level Field Matrix

This table maps the requested face report to the v0.41.0 contract. Every field
is present in one stable CSV, but the evidence remains bounded by the generated
corpus and its declared provenance.

| Requested field | Current status | What can be reported now | What is still missing | Evidence |
| --- | --- | --- | --- | --- |
| Analysis-local face index | Implemented | One-based local index with primary key `(stage, control_id, analysis_face_index)` and a machine-readable nonpersistent-identity warning | Persistence across export, editing, Boolean operations, healing, readers, or kernel versions | [`face_analysis_contract.json`](../results/face_analysis_contract.json) |
| Parent solid and shell | Controlled subset | Sorted parent-index lists for every row; 24 solid-owned rows and two open-shell rows across both stages | Arbitrary nonmanifold sharing, imported void-shell semantics, and source STEP entity ownership | [`face_analysis_report.csv`](../results/face_analysis_report.csv) |
| Surface type | Controlled subset | Eight planes and one cylinder, cone, sphere, torus, and B-spline per stage, with normalized and raw kernel type | Arbitrary support families, invalid faces, and cross-kernel classification | [`face_analysis_summary.csv`](../results/face_analysis_summary.csv) |
| Face orientation | Controlled subset | Forward/reversed topology orientation and an orientation-adjusted representative normal; all 13 round-trip pairs match | General shell-relative material outwardness, nested regions, and persistent orientation identity | [`face_analysis_round_trip_matches.csv`](../results/face_analysis_round_trip_matches.csv) |
| Area | Controlled subset | Exact-surface area for all 26 rows; maximum matched round-trip difference `1.0317080523236655e-11` squared model units | Independent truth for every curved trim, invalid or repaired faces, and cross-kernel agreement | [`face_analysis_report.csv`](../results/face_analysis_report.csv) |
| Centroid | Controlled subset | Exact-surface centroid for all 26 rows; maximum matched distance `2.9535772102134982e-13` model units | Independent truth for every curved trim, invalid or repaired faces, and cross-kernel agreement | [`face_analysis_round_trip_matches.csv`](../results/face_analysis_round_trip_matches.csv) |
| UV bounds | Controlled subset | Restricted U/V bounds for all six controlled families, in surface-parameter units | Parameterization equivalence, seam-crossing normalization, and arbitrary trim-aware comparison | [`face_analysis_report.csv`](../results/face_analysis_report.csv) |
| Representative normal | Controlled subset | Oriented derivative-cross-product normal at the first nonsingular point from three deterministic samples | Whole-face regularity, curvature continuity, and guaranteed interior classification | [`face_analysis.py`](../src/research_notes/face_analysis.py) |
| Plane normal | Controlled subset | Support-plane normal, origin, and X direction in separate nullable columns | General unit normalization and shell-relative material interpretation | [`face_analysis_report.csv`](../results/face_analysis_report.csv) |
| Cylinder axis and radius | Controlled subset | Located axis, origin, X direction, and radius `1.25` for the controlled through-hole cylinder | Arbitrary transforms, units, partial trims, and cross-kernel validation | [`face_analysis_report.csv`](../results/face_analysis_report.csv) |
| Cone parameters | Controlled subset | Located axis, origin, X direction, reference radius `3`, and signed semi-angle; the sign flip after import is retained | A canonical parameter-frame policy, arbitrary cones, and unit-aware validation | [`face_analysis_report.csv`](../results/face_analysis_report.csv) |
| Sphere parameters | Controlled subset | Located center/origin, axis, X direction, and radius `2` | Partial spheres, arbitrary placement, units, and cross-kernel validation | [`face_analysis_report.csv`](../results/face_analysis_report.csv) |
| Torus parameters | Controlled subset | Located center/origin, axis, X direction, major radius `4`, and minor radius `1` | Partial tori, spindle or self-intersecting cases, units, and cross-kernel validation | [`face_analysis_report.csv`](../results/face_analysis_report.csv) |
| B-spline parameters | Controlled subset | U/V degrees, pole and knot counts, periodicity, and rationality for one bicubic patch | Pole coordinates, knots, multiplicities, weights, continuity, arbitrary trims, and evaluation truth | [`face_analysis_report.csv`](../results/face_analysis_report.csv) |
| Outer and inner wire counts | Controlled subset | Outer/inner counts for every row; the through-hole control has two inner-wire faces per stage | Nested islands, invalid loops, and distinction between every ordered edge use | [`face_analysis_report.csv`](../results/face_analysis_report.csv) |
| Boundary-edge count | Controlled subset | Unique topological edge count for every row; all 13 round-trip pairs match | General invalid topology and ordered-use or seam-branch counts in the same contract | [`face_analysis_round_trip_matches.csv`](../results/face_analysis_round_trip_matches.csv) |
| Free-edge and nonmanifold evidence | Controlled subset | Separate v0.35–v0.37 outputs retain incidence, closure, and vertex-link evidence | The v0.41 row does not duplicate arbitrary free-edge or vertex-link classifications | [`manifold_intersection_observations.csv`](../results/manifold_intersection_observations.csv) |
| Adjacent face indices | Controlled subset | Sorted distinct faces sharing at least one unique edge; periodic self-seams are excluded | Geometric contact without shared topology and persistent adjacency identity | [`face_analysis_report.csv`](../results/face_analysis_report.csv) |
| Face tolerance | Controlled subset | Stored face tolerance for every stage; the B-spline control changes from `2.0e-4` to `1.0e-7` | Manufacturing acceptance policy, general writer behavior, and persistent source identity | [`face_analysis_summary.csv`](../results/face_analysis_summary.csv) |
| Face name | Partial | Constructed shape-level names are copied with source `synthetic_control_manifest:shape`; imported values remain blank | XCAF face/shape/instance label traversal, inheritance, and source STEP attribution | [`face_analysis_report.csv`](../results/face_analysis_report.csv) |
| Face color | Partial | Constructed shape-level RGB values carry the same explicit manifest source; imported values remain blank | XCAF general/surface/curve color precedence, inheritance, overrides, and source attribution | [`face_analysis_report.csv`](../results/face_analysis_report.csv) |
| Direct source provenance | Partial | Fixture file and SHA-256 identify imported rows; metadata fields carry source-kind strings; local keys and geometry matches remain separate | Direct STEP entity-to-kernel-face mapping, original source spans, and XCAF label lineage | [`face_analysis_contract.json`](../results/face_analysis_contract.json) |

## Geometry, Modeling, Interoperability, and AI Gaps

| Capability | Current status | Earliest roadmap stage | Required evidence before a claim |
| --- | --- | --- | --- |
| Geometry-kernel selection | Implemented as research evidence | v0.31.0 | Eight candidates, six gates, installed-package audit, optional dependency, and one deterministic box round trip; binary redistribution remains excluded |
| Evaluated face geometry and tolerance | Controlled subset | v0.32.0 | Two planes and one cylinder checked against analytic truth; arbitrary trim and general tolerance claims remain excluded |
| Curves, p-curves, seams, and periodicity | Controlled subset | v0.33.0 | Eleven analytic edges, twelve oriented uses, closed-form line/circle truth, UV paths, sampled 3D agreement, and one full-cylinder seam; splines remain excluded |
| Wire ordering, trimming, holes, and oriented faces | Controlled subset | v0.34.0 | Two planar frames, one cylinder, and one sphere with independent material and signed-loop truth, point classification, connection-ordered traversal, seams, and pole degeneracy; arbitrary curved, invalid, and nested cases remain excluded |
| Shell and solid validity | Controlled subset | v0.35.0 | Seven controls provide independent incidence, components, orientability, closure, Euler, volume eligibility, signed volume, and generic/shell-specific backend reports; arbitrary topology, vertex manifoldness, self-intersection, nested voids, and repair remain excluded |
| Tolerance-mediated sewing and targeted orientation repair | Controlled subset | v0.36.0 | Three gaps by three requested tolerances, 17 stage observations, 550 subshape-tolerance rows, positive and negative orientation controls, a rejected tolerance-cap operation, and STEP-stage comparison; no universal threshold or general healing claim |
| Vertex manifoldness and self-intersection | Controlled subset | v0.37.0 | Twelve controls produce 24 topology, 224 vertex-link, 14 pair-relation, and eight single-argument `BOPAlgo_CheckerSI` observations; all controlled matches hold with zero recorded quantity error, but no arbitrary curved-shape proof follows |
| Voids, inner shells, and composite solids | Controlled subset | v0.38.0 | Ten controls produce 20 main, 44 shell-role, 60 containment, and nine adjacency rows; all constructed candidate, shared-face, and component expectations match, but axis-aligned convex boxes and one STEP route do not establish general containment or composite-solid preservation |
| Correspondence across import and healing | Controlled subset | v0.39.0 | Four planar/open-line controls provide face and edge one-to-one, many-to-one, deletion, and ambiguous-abstention evidence across STEP import and one healing operation; geometry, incident-face topology support, operation history, and direct identity are separate, with no split, moving-frame, curved/closed-edge, or persistent-identity claim |
| Rule-based feature recognition | Controlled subset | v0.40.0 | Nine controls and STEP fixtures produce seven candidates per stage; all 14 match controlled classification and dimensions, with maximum truth errors of `3.9612757518625585e-13` model units and `5.8832938520936295e-12` degrees, zero false positives across the plain block and external boss, and no design-intent claim |
| Complete face-level report | Controlled subset | v0.41.0 | A 60-field v1 contract covers 26 rows, six surface families, local ownership, evaluated geometry, boundaries, adjacency, tolerance, and source-bounded name/color fields; arbitrary inputs, persistent identity, and XCAF traversal remain excluded |
| Tessellation and visual diagnostics | Controlled subset | v0.42.0 | Three STEP fixtures, four absolute linear/angular conditions, 36 face rows, 3,782 triangle rows, direct `ADVANCED_FACE` provenance for nine faces, exact-area comparison, sampled surface deviation, eight explicit pole-degenerate triangles, and face-colored previews; no certified error bound, global welded mesh, arbitrary-file coverage, or interactive viewer |
| Primitive and surface construction | Controlled subset | v0.43.0 | Six controls retain topology and surface inventories across STEP; five analytic solids match independent volume/area truth, while equivalent cone parameterization and B-spline tolerance drift remain explicit; no supported general modeling API or feature-history recovery |
| Profiles, extrusion, and revolution | Controlled subset | v0.44.0 | Five controls preserve analytic truth, topology, and surfaces across STEP; rectangle height and revolution angle recompute ratios match, while general sketches, constraints, taper, and recovered feature history remain excluded |
| Sweeps, lofts, and surface construction | Controlled subset | v0.45.0 | Five accepted controls retain validity, topology, surfaces, and measurements across STEP; two invalid preconditions reject without kernel invocation, while arbitrary guide curves, section compatibility, fairness, and certified fitting bounds remain excluded |
| Boolean operations and robustness | Controlled subset | v0.46.0 | Seven cuboid controls cover union, intersection, subtraction, overlap, disjointness, shared-face contact, and one near-gap fuzzy pair; curved, invalid, sliver, warning, performance, cross-kernel, and universal-tolerance claims remain excluded |
| Fillets, chamfers, and topology history | Controlled subset | v0.47.0 | Two successful and two oversized controls record analytic truth, 52 source-scoped history rows, generated and modified results, zero observed deletion/split/merge cases, and 14 STEP face matches with equal indices but zero direct identity; general local-feature history and persistent naming remain excluded |
| STEP import-edit-export preservation | Controlled subset | v0.48.0 | Three XCAF-aware controls retain structure, semantics, global geometry, topology, color inventory, and maximum tolerances between generations; only one is byte identical and one declared source color is omitted before the first import, while nested assemblies, complete attribute links, and cross-kernel evidence remain excluded |
| Independent parser and importer portability | Controlled subset | v0.49.0 | Three fixed files are accepted by three parser implementations and produce matching geometry on two OCCT routes; no independent kernel is included |
| Resource-bounded native 3D intake | Controlled subset | v0.50.0 | Five ordered stages cover raw and controlled ZIP inputs, parser counters, disabled external retrieval, child-process timeouts, topology, and triangle limits; no OS sandbox or memory-safety claim |
| Face-adjacency descriptors | Controlled subset | v0.51.0 | Four constructed/imported graph pairs expose attributed face nodes, distinct-face shared-edge relations, incidence classes, structural summaries, and field provenance; IDs remain analysis-local |
| Feature-recognition robustness | Controlled subset | v0.52.0 | Thirty-two generated cases and 64 observations separate accepts, negative-control rejects, rotation-related abstentions, and zero STEP-induced decision changes |
| AI-ready 3D dataset | Controlled subset | v0.53.0 | Thirty-six STEP-backed samples, nine family groups, fixed splits, graph/B-Rep features, labels, digests, and five zero-violation leakage checks |
| Learned 3D assistance | Research demonstration | v0.54.0 | Four binary baselines retain train/calibration/test separation, source-linked evidence, confidence, abstention, calibration bins, and perturbation stability; industrial transfer is untested |
| Parametric feature graph | Research demonstration | v0.55.0 | Four revisioned DAGs cover datum, parameter, sketch, feature, result, dependency, import reference, observation, and unconfirmed-candidate nodes; three generated B-Reps match truth and STEP |
| Parametric constraints and recompute | Not implemented | v0.56.0–v0.58.0 | Solver states, explicit feature families, and deterministic dependency recompute |
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
- Reproduce the v0.37 edge-incidence and vertex-link counterexamples plus the
  controlled single-argument edge/face interference and disjoint, point-,
  edge-, face-, volume-, and transverse-crossing relationship dimensions and
  measures.
- Reproduce the v0.38 outer/void-shell roles, containment relations, partial-
  overlap gate, material-island nesting, and solid face-adjacency graph for ten
  controlled material-region cases before and after STEP exchange.
- Reproduce the v0.39 face evidence: 56 descriptors, 37 candidates, 35
  relations, 23 unique STEP-import matches, two ambiguity abstentions, two
  healing one-to-one relations, eight healing many-to-one relations in four
  groups, and 10-of-10 operation-history agreement.
- Reproduce the v0.39 edge evidence: 122 descriptors, 79 candidates, 75
  relations, 47 unique STEP-import matches, eight ambiguity abstentions, and a
  `20 -> 12` healing change with eight `one_to_one_modified`, eight many-to-one
  relations in four groups, four deletions, and 20-of-20 history agreement.
- Inspect edge geometry, incident-face topology support, operation history,
  and direct identity as separate evidence; all 75 relations report neither
  direct `IsSame` nor direct `IsPartner` identity.
- Reproduce the v0.40 attributed-face and adjacency evidence for controlled
  through and blind holes, an open step, a through slot, chamfer-like faces,
  and a fillet-like face. All 14 stage-specific candidates match their
  registered classifications and dimensions, and the two negative controls
  produce zero false positives.
- Reproduce the v0.40 intent-boundary comparison: the operation chamfer and
  direct-profile equivalent bevel each have `V=10`, `E=15`, `F=7`, one shell,
  one solid, volume `572`, and zero bidirectional difference volumes at both
  constructed and STEP-imported stages, while design intent remains unproven.
- Reproduce the v0.41 stable face report: five fixtures produce 13 rows per
  stage across six surface families, and all 13 geometry-matched pairs retain
  orientation and boundary counts. Inspect local index scope, nullable
  type-specific parameters, tolerance reconstruction, and metadata sources.
- Reproduce the v0.42 tessellation evidence: three fixtures, four independent
  linear/angular conditions, 36 face rows, 3,782 triangle rows, nine direct
  `ADVANCED_FACE` mappings, eight explicit sphere-pole degeneracies, exact-area
  comparisons, sampled deviations, and face-colored previews.
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
- Treating the bounded vertex-link and shape-pair results as a general
  self-intersection proof, collision policy, or tolerance threshold.
- Treating signed volume, containment depth, generic kernel validity, or the
  top-level container type alone as proof of a valid material region or a
  preserved composite solid.
- Treating face support-plane, area, and centroid evidence, or edge curve,
  endpoint, length, support, and incident-face evidence, as topological
  identity, a persistent name, STEP-carried operation history, semantic
  provenance, or recovered design intent.
- Editing, interactively rendering, or exporting arbitrary production CAD
  models through a supported end-user workflow, or applying the controlled
  tessellation contract as a general meshing policy.
- Processing untrusted arbitrary STEP files as if resource use or native-code
  safety had been established.
- Claiming recovered sketches, dimensions, feature history, or design intent
  from an imported STEP model.
- Treating the v0.40 geometry-only rule candidates as recovered feature
  operations, machining intent, or a general feature recognizer.
- Treating v0.41 local face indices as persistent names, UV bounds as portable
  three-dimensional coordinates, one normal as whole-face proof, or blank
  imported metadata as evidence that no source attribute ever existed.
- Treating v0.42 requested deflections or one UV-barycentric sample as a
  certified maximum error, mesh area as one-sided, or a preview as exact B-Rep
  geometry.
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
  tests/test_tolerance_sewing_healing.py \
  tests/test_manifold_self_intersection.py \
  tests/test_solid_regions.py \
  tests/test_shape_correspondence.py \
  tests/test_feature_recognition.py \
  tests/test_face_analysis.py \
  tests/test_tessellation_diagnostics.py
python experiments/run_tolerance_sewing_healing.py
python experiments/run_manifold_self_intersection.py
python experiments/run_solid_region_evaluation.py
python experiments/run_shape_correspondence.py
python experiments/run_feature_recognition.py
python experiments/run_face_level_analysis.py
python experiments/run_tessellation_diagnostics.py
```

The complete generated-input catalog is in the
[STEP sample and preview catalog](step-sample-catalog.md). The sequence from
current limitations to modeling and AI is in the
[STEP mastery roadmap](brep-learning-roadmap.md).
