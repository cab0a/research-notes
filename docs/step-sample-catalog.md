# STEP Sample and Preview Catalog

## 日本語概要

本書は、STEP/B-repとEXPRESSの調査でコミットした合成サンプル、ハッシュ付き一覧、目視用画像、主な用途を対応付けます。v0.21.0からv0.24.0までの位相・交換構造・原文モデル・版別構文適合性、v0.25.0のEXPRESS字句・構文・未解決スキーマモデル、v0.26.0のシンボル・型・継承グラフ、v0.27.0のSTEP・EXPRESS組合せ検証、v0.28.0の物理参照グラフ、v0.29.0のAP242製品経路、v0.30.0の組立出現・配置・単位換算、v0.31.0のOpen CASCADE合成箱STEP往復を収録します。形状には目視用画像、構文や意味経路だけを扱うサンプルには構造・関係図を用いますが、完全なスキーマ適合性、AP242適合性、幾何妥当性、公差、形状計算核間の互換性の証明ではありません。詳細は以下の英語本文に示します。

---

## English Summary

This catalog maps committed synthetic STEP and EXPRESS samples to their
manifests, previews, research purpose, and validation boundary. Samples live
under `fixtures/` because they are both human-inspectable examples and exact
CI inputs.

## Sample Policy

Each STEP, B-Rep, or EXPRESS study keeps the actual input bytes whenever licensing and
privacy permit. This repository uses only generated synthetic inputs. A sample
set includes:

- a deterministic generator in `src/research_notes/`;
- committed `.step` or container files under `fixtures/`;
- a manifest with byte lengths, SHA-256 digests, conditions, and expectations;
- an experiment command that regenerates and compares the corpus;
- a PNG shape preview or structure diagram when visually meaningful;
- CSV observations that remain the primary validation evidence.

## v0.21.0 — Topology Samples

Directory: [`fixtures/step-brep-topology/`](../fixtures/step-brep-topology/)

Manifest: [`manifest.csv`](../fixtures/step-brep-topology/manifest.csv)

Representative samples:

| Sample | Visual or structural purpose |
| --- | --- |
| [`closed_tetrahedron.step`](../fixtures/step-brep-topology/closed_tetrahedron.step) | Closed four-face solid control |
| [`open_tetrahedron.step`](../fixtures/step-brep-topology/open_tetrahedron.step) | One removed face and three free edges |
| [`two_closed_solids.step`](../fixtures/step-brep-topology/two_closed_solids.step) | Two disconnected solids and ownership separation |
| [`surface_catalog.step`](../fixtures/step-brep-topology/surface_catalog.step) | Declared plane, cylinder, cone, sphere, torus, and B-spline surfaces |
| [`unresolved_reference.step`](../fixtures/step-brep-topology/unresolved_reference.step) | Missing topology target; quarantine control |
| [`duplicate_entity_id.step`](../fixtures/step-brep-topology/duplicate_entity_id.step) | Ambiguous occurrence identifier; reject control |

![Topology experiment overview](../results/step_brep_topology.png)

The surface catalog tests declaration extraction. Its triangular face bounds
do not establish valid trimmed geometry on every listed support surface.

## v0.22.0 — Advanced Exchange Structure Samples

Directory: [`fixtures/step-part21-exchange/`](../fixtures/step-part21-exchange/)

Manifest: [`manifest.csv`](../fixtures/step-part21-exchange/manifest.csv)

The [`single_data_control.step`](../fixtures/step-part21-exchange/single_data_control.step)
sample is the same closed tetrahedron used by the v0.21.0 topology study. It is
the geometry-bearing control for v0.22.0: 74 Part 21 entity instances and 97
local occurrence references resolve to four faces, six edges, one shell, one
solid, and no free edges.

![Closed tetrahedron geometry control](../results/step_part21_geometry_control.png)

The remaining samples isolate exchange-structure forms or parser boundaries:

| Sample | Purpose | Expected route |
| --- | --- | --- |
| [`multiple_data_sections.step`](../fixtures/step-part21-exchange/multiple_data_sections.step) | Two named DATA sections governed by a declared schema | accept |
| [`complex_entity_instance.step`](../fixtures/step-part21-exchange/complex_entity_instance.step) | One subsuper record with three component records | accept |
| [`utf8_binary_values.step`](../fixtures/step-part21-exchange/utf8_binary_values.step) | Direct UTF-8 string and valid binary token | accept |
| [`anchor_with_tag.step`](../fixtures/step-part21-exchange/anchor_with_tag.step) | Local anchor and one non-schema tag | accept |
| [`external_reference.step`](../fixtures/step-part21-exchange/external_reference.step) | External URI retained without retrieval | quarantine |
| [`signature_present.step`](../fixtures/step-part21-exchange/signature_present.step) | Two Base64 payloads retained without CMS verification | quarantine |
| [`deep_nesting.step`](../fixtures/step-part21-exchange/deep_nesting.step) | Aggregate depth beyond the parser budget | quarantine |
| [`zip_archive.stpz`](../fixtures/step-part21-exchange/zip_archive.stpz) | ZIP signature recognized without extraction | quarantine |
| [`duplicate_entity_across_sections.step`](../fixtures/step-part21-exchange/duplicate_entity_across_sections.step) | Duplicate global entity identifier | reject |
| [`unnamed_multiple_data.step`](../fixtures/step-part21-exchange/unnamed_multiple_data.step) | Missing names on repeated DATA sections | reject |
| [`undeclared_data_schema.step`](../fixtures/step-part21-exchange/undeclared_data_schema.step) | DATA schema absent from FILE_SCHEMA | reject |
| [`invalid_binary.step`](../fixtures/step-part21-exchange/invalid_binary.step) | Non-hex character in a binary token | reject |

![Advanced exchange structure boundaries](../results/step_part21_exchange_boundaries.png)

Most v0.22.0 samples intentionally use a minimal synthetic schema vocabulary
and do not define a meaningful CAD shape. The structure diagram is therefore
more honest than fabricating a 3D preview for them.

## v0.23.0 — Unified Source Model Samples

Directory: [`fixtures/step-part21-source-model/`](../fixtures/step-part21-source-model/)

Manifest: [`manifest.csv`](../fixtures/step-part21-source-model/manifest.csv)

The [`geometry_control.step`](../fixtures/step-part21-source-model/geometry_control.step)
sample is byte-identical to the v0.21 closed tetrahedron. Reusing the exact
shape makes the parser refactor measurable: the unified source model retains
74 entities and 97 references, and the compatibility adapter still produces
the same face, edge, shell, and solid observations.

![Closed tetrahedron integration control](../results/step_part21_geometry_control.png)

The syntax-focused samples isolate source retention and diagnostics:

| Sample | Purpose | Expected route |
| --- | --- | --- |
| [`trivia_preservation.step`](../fixtures/step-part21-source-model/trivia_preservation.step) | Preserve whitespace, comments, aggregates, and an escaped apostrophe | accept |
| [`utf8_coordinates.step`](../fixtures/step-part21-source-model/utf8_coordinates.step) | Separate character positions from UTF-8 byte positions | accept |
| [`simple_and_complex.step`](../fixtures/step-part21-source-model/simple_and_complex.step) | Parse simple and subsuper records with one grammar | accept |
| [`forward_reference.step`](../fixtures/step-part21-source-model/forward_reference.step) | Retain a reference whose target is defined later | accept |
| [`missing_semicolon.step`](../fixtures/step-part21-source-model/missing_semicolon.step) | Localize a missing entity terminator | reject |
| [`unterminated_comment.step`](../fixtures/step-part21-source-model/unterminated_comment.step) | Localize an open comment at end of input | reject |
| [`nesting_limit.step`](../fixtures/step-part21-source-model/nesting_limit.step) | Stop beyond an explicit aggregate-depth budget | quarantine |
| [`token_length_limit.step`](../fixtures/step-part21-source-model/token_length_limit.step) | Stop beyond an explicit token-character budget | quarantine |
| [`invalid_utf8.step`](../fixtures/step-part21-source-model/invalid_utf8.step) | Reject invalid UTF-8 before grammar construction | reject |

![Unified Part 21 source-model evidence](../results/step_part21_source_model.png)

Most samples have no meaningful shape. Their diagram shows syntax decisions
and retained token classes rather than fabricating a geometry preview. The
invalid UTF-8 sample is intentionally not a valid text document and should be
inspected as bytes or through its manifest and observation row.

## v0.24.0 — Edition and Conformance Samples

Directory: [`fixtures/step-part21-conformance/`](../fixtures/step-part21-conformance/)

Manifest: [`manifest.csv`](../fixtures/step-part21-conformance/manifest.csv)

The corpus contains 31 clear-text `.step` inputs and three `.stpz` archives.
Every byte is generated in code and the manifest records its SHA-256 digest,
condition, expected decision, reason code, and edition floor.

| Sample group | Representative samples | Boundary isolated |
| --- | --- | --- |
| Edition 1 core | [`edition1_minimal.step`](../fixtures/step-part21-conformance/edition1_minimal.step), [`edition1_legacy_controls.step`](../fixtures/step-part21-conformance/edition1_legacy_controls.step) | Core exchange and legacy `X`, `X4`, `S/P`, and `N/F` controls |
| Comments and binary | [`edition1_comment.step`](../fixtures/step-part21-conformance/edition1_comment.step), [`invalid_binary.step`](../fixtures/step-part21-conformance/invalid_binary.step) | Non-nested trivia and binary hexadecimal rules |
| Edition 2 structure | [`edition2_multiple_data.step`](../fixtures/step-part21-conformance/edition2_multiple_data.step), [`edition2_section_context.step`](../fixtures/step-part21-conformance/edition2_section_context.step) | Multiple named `DATA` and an Edition 2 header entity |
| Edition 3 text and sections | [`edition3_utf8.step`](../fixtures/step-part21-conformance/edition3_utf8.step), [`edition3_anchor.step`](../fixtures/step-part21-conformance/edition3_anchor.step), [`edition3_value_reference.step`](../fixtures/step-part21-conformance/edition3_value_reference.step), [`edition3_signature.step`](../fixtures/step-part21-conformance/edition3_signature.step) | Direct UTF-8, anchor, external value reference, and signature syntax |
| Edition and class mismatch | [`edition1_multiple_data.step`](../fixtures/step-part21-conformance/edition1_multiple_data.step), [`reference_class_1.step`](../fixtures/step-part21-conformance/reference_class_1.step), [`constant_class_2.step`](../fixtures/step-part21-conformance/constant_class_2.step) | Parsed feature floor versus declared implementation level |
| Numeric and identifier errors | [`invalid_real_exponent.step`](../fixtures/step-part21-conformance/invalid_real_exponent.step), [`zero_occurrence.step`](../fixtures/step-part21-conformance/zero_occurrence.step), [`lowercase_keyword.step`](../fixtures/step-part21-conformance/lowercase_keyword.step) | Strict real, occurrence-name, and keyword syntax |
| Character errors | [`invalid_string_control.step`](../fixtures/step-part21-conformance/invalid_string_control.step), [`invalid_utf8.step`](../fixtures/step-part21-conformance/invalid_utf8.step) | Unknown legacy directive and invalid UTF-8 input |
| ZIP transport | [`zip_root.stpz`](../fixtures/step-part21-conformance/zip_root.stpz), [`zip_missing_root.stpz`](../fixtures/step-part21-conformance/zip_missing_root.stpz), [`zip_unsafe_path.stpz`](../fixtures/step-part21-conformance/zip_unsafe_path.stpz) | Required root and fail-closed path admission without extraction |

![Part 21 grammar coverage and conformance corpus](../results/step_part21_conformance.png)

These files intentionally use a synthetic schema vocabulary and generally do
not describe a meaningful 3D shape. The figure shows edition coverage and
acceptance boundaries; the CSV observations remain the validation evidence.

## v0.25.0 — EXPRESS Schema-Model Samples

Directory: [`fixtures/express-schema-model/`](../fixtures/express-schema-model/)

Manifest: [`manifest.csv`](../fixtures/express-schema-model/manifest.csv)

The corpus contains 40 generated `.exp` sources. The manifest records exact
byte length, SHA-256 digest, active resource limits, expected route, and reason
code for every input.

| Sample group | Representative samples | Boundary isolated |
| --- | --- | --- |
| Schema and lexical controls | [`minimal_schema.exp`](../fixtures/express-schema-model/minimal_schema.exp), [`mixed_case.exp`](../fixtures/express-schema-model/mixed_case.exp), [`comments.exp`](../fixtures/express-schema-model/comments.exp) | Schema envelopes, case-insensitive names, and source-preserved trivia |
| Type declarations | [`aggregate_type.exp`](../fixtures/express-schema-model/aggregate_type.exp), [`select_type.exp`](../fixtures/express-schema-model/select_type.exp), [`enumeration_type.exp`](../fixtures/express-schema-model/enumeration_type.exp) | Structured type references and member lists |
| Entity declarations | [`entity_inheritance.exp`](../fixtures/express-schema-model/entity_inheritance.exp), [`derived_attribute.exp`](../fixtures/express-schema-model/derived_attribute.exp), [`inverse_attribute.exp`](../fixtures/express-schema-model/inverse_attribute.exp) | Header relationships and three attribute kinds |
| Interfaces and algorithms | [`use_import.exp`](../fixtures/express-schema-model/use_import.exp), [`function_envelope.exp`](../fixtures/express-schema-model/function_envelope.exp), [`rule_envelope.exp`](../fixtures/express-schema-model/rule_envelope.exp) | Parsed declarations with unresolved imports and opaque executable bodies |
| Lexical and grammar failures | [`invalid_real.exp`](../fixtures/express-schema-model/invalid_real.exp), [`duplicate_declaration.exp`](../fixtures/express-schema-model/duplicate_declaration.exp), [`missing_end_entity.exp`](../fixtures/express-schema-model/missing_end_entity.exp) | Stable rejection reasons and case-insensitive collisions |
| Resource boundary | [`comment_nesting_limit.exp`](../fixtures/express-schema-model/comment_nesting_limit.exp) | Quarantine before accepting excessive nested-comment work |

![EXPRESS schema-model corpus](../results/express_schema_model.png)

These sources specify no CAD shape and therefore have no geometry preview.
The figure shows the observed routes, model composition, and the boundary
between parsed declarations, opaque envelopes, and deferred semantic stages.

## v0.26.0 — EXPRESS Semantic-Graph Samples

Directory: [`fixtures/express-symbol-resolution/`](../fixtures/express-symbol-resolution/)

Manifest: [`manifest.csv`](../fixtures/express-symbol-resolution/manifest.csv)

The corpus contains 38 generated `.exp` sources. Every source is independently
readable and the manifest records its exact bytes, SHA-256 identity, expected
semantic route, reason code, and active graph limits.

| Sample group | Representative samples | Boundary isolated |
| --- | --- | --- |
| Local symbols and types | [`alias_chain.exp`](../fixtures/express-symbol-resolution/alias_chain.exp), [`select_members.exp`](../fixtures/express-symbol-resolution/select_members.exp), [`constant_bounds.exp`](../fixtures/express-symbol-resolution/constant_bounds.exp) | Terminal domains, select targets, and bounded constants |
| Interfaces | [`use_alias.exp`](../fixtures/express-symbol-resolution/use_alias.exp), [`reference_constant.exp`](../fixtures/express-symbol-resolution/reference_constant.exp), [`import_collision.exp`](../fixtures/express-symbol-resolution/import_collision.exp) | Direct imports, aliases, kinds, and multiple visible candidates |
| Inheritance | [`diamond_inheritance.exp`](../fixtures/express-symbol-resolution/diamond_inheritance.exp), [`qualified_redeclaration.exp`](../fixtures/express-symbol-resolution/qualified_redeclaration.exp), [`inherited_collision.exp`](../fixtures/express-symbol-resolution/inherited_collision.exp) | Shared origins, qualified replacement, and conflicting origins |
| Graph failures | [`alias_cycle.exp`](../fixtures/express-symbol-resolution/alias_cycle.exp), [`inheritance_cycle.exp`](../fixtures/express-symbol-resolution/inheritance_cycle.exp), [`missing_type.exp`](../fixtures/express-symbol-resolution/missing_type.exp) | Cyclic and unresolved states without guessed targets |
| Resource boundary | [`symbol_limit.exp`](../fixtures/express-symbol-resolution/symbol_limit.exp) | Quarantine before exceeding a declared semantic graph budget |

![EXPRESS symbol and relationship corpus](../results/express_symbols_types_inheritance.png)

These sources define schema relationships, not CAD instance geometry. The
figure therefore visualizes decisions and graph states rather than inventing
shape previews.

## v0.27.0 — Paired STEP and EXPRESS Validation Samples

Directory: [`fixtures/step-express-validation/`](../fixtures/step-express-validation/)

Manifest: [`manifest.csv`](../fixtures/step-express-validation/manifest.csv)

The corpus contains 40 generated pairs. Each condition has one `.step` exchange
and one `.exp` schema. The manifest binds both file names, byte lengths,
SHA-256 identities, expected decision and reason, and active schema-validation
limits.

| Sample group | Representative pairs | Boundary isolated |
| --- | --- | --- |
| Values and markers | [`scalar_types.step`](../fixtures/step-express-validation/scalar_types.step) + [`scalar_types.exp`](../fixtures/step-express-validation/scalar_types.exp), [`derived_redeclaration.step`](../fixtures/step-express-validation/derived_redeclaration.step) + [`derived_redeclaration.exp`](../fixtures/step-express-validation/derived_redeclaration.exp) | Scalar domains, `$`, and inherited `*` positions |
| Inheritance | [`internal_inheritance.step`](../fixtures/step-express-validation/internal_inheritance.step) + [`internal_inheritance.exp`](../fixtures/step-express-validation/internal_inheritance.exp), [`diamond_inheritance.step`](../fixtures/step-express-validation/diamond_inheritance.step) + [`diamond_inheritance.exp`](../fixtures/step-express-validation/diamond_inheritance.exp) | Ancestor order and shared-origin deduplication |
| References and selects | [`subtype_entity_reference.step`](../fixtures/step-express-validation/subtype_entity_reference.step), [`select_typed_defined.step`](../fixtures/step-express-validation/select_typed_defined.step) | Forward targets, subtype compatibility, and typed select members |
| Staged failures | [`part21_syntax_failure.step`](../fixtures/step-express-validation/part21_syntax_failure.step), [`express_syntax_failure.exp`](../fixtures/step-express-validation/express_syntax_failure.exp), [`express_resolution_failure.exp`](../fixtures/step-express-validation/express_resolution_failure.exp) | Part 21 syntax, EXPRESS syntax, and name resolution stop independently |
| Deferred work | [`complex_mapping_deferred.step`](../fixtures/step-express-validation/complex_mapping_deferred.step), [`constant_reference_deferred.step`](../fixtures/step-express-validation/constant_reference_deferred.step), [`width_constraint_deferred.exp`](../fixtures/step-express-validation/width_constraint_deferred.exp) | Evaluated sets, external values, and width constraints remain quarantine boundaries |

![Paired Part 21 and EXPRESS validation corpus](../results/step_express_validation.png)

The paired sources describe schema-validation controls rather than meaningful
product geometry. The figure shows validation stages and parameter evidence;
it is not a fabricated CAD preview.

## v0.28.0 — Physical Reference Graph Samples

Directory: [`fixtures/step-graph-queries/`](../fixtures/step-graph-queries/)

Manifest: [`manifest.csv`](../fixtures/step-graph-queries/manifest.csv)

The corpus contains 14 generated STEP files. The manifest binds exact bytes
and SHA-256 identities to expected routes, graph-construction budgets,
traversal roots, and per-fixture depth limits.

| Sample group | Representative samples | Boundary isolated |
| --- | --- | --- |
| Reachability | [`branching_orphan.step`](../fixtures/step-graph-queries/branching_orphan.step), [`isolated_nodes.step`](../fixtures/step-graph-queries/isolated_nodes.step) | Caller-relative reachability, zero indegree, isolation, and orphans |
| Cycles and multiplicity | [`directed_cycles.step`](../fixtures/step-graph-queries/directed_cycles.step), [`duplicate_reference_occurrences.step`](../fixtures/step-graph-queries/duplicate_reference_occurrences.step) | Strongly connected components, self-loops, and repeated edge occurrences |
| Source and ownership | [`nested_parameter_paths.step`](../fixtures/step-graph-queries/nested_parameter_paths.step), [`multiple_data_sections.step`](../fixtures/step-graph-queries/multiple_data_sections.step), [`complex_instance.step`](../fixtures/step-graph-queries/complex_instance.step) | Nested parameter paths, schema-owned DATA sections, and multiple record types on one node |
| Nonlocal targets | [`external_entity.step`](../fixtures/step-graph-queries/external_entity.step), [`external_value_and_constant.step`](../fixtures/step-graph-queries/external_value_and_constant.step), [`unresolved_entity.step`](../fixtures/step-graph-queries/unresolved_entity.step) | External entity and value scopes, schema constants, and unresolved local IDs without retrieval |
| Resource boundaries | [`depth_limited_chain.step`](../fixtures/step-graph-queries/depth_limited_chain.step), [`node_budget.step`](../fixtures/step-graph-queries/node_budget.step), [`edge_budget.step`](../fixtures/step-graph-queries/edge_budget.step), [`syntax_failure.step`](../fixtures/step-graph-queries/syntax_failure.step) | Partial query results, construction quarantine, and parse rejection |

![Physical STEP reference graph corpus](../results/step_graph.png)

The figure shows source-level reference relationships and controlled query
states. It does not assert product structure, assembly occurrence semantics,
B-Rep ownership, evaluated geometry, or persistent identity.

## v0.29.0 — AP242 Product-Path Samples

Directory: [`fixtures/ap242-product-paths/`](../fixtures/ap242-product-paths/)

Manifest: [`manifest.csv`](../fixtures/ap242-product-paths/manifest.csv)

The corpus contains 14 generated STEP files. The manifest binds each exact
byte stream and SHA-256 identity to an expected semantic route and explicit
product-definition, path, relation, item, and unit work budgets.

| Sample group | Representative samples | Boundary isolated |
| --- | --- | --- |
| Resolved paths | [`ap242_block_path.step`](../fixtures/ap242-product-paths/ap242_block_path.step), [`ap242_multiple_representations.step`](../fixtures/ap242-product-paths/ap242_multiple_representations.step) | Product, formation, definition, shape, representation, item, context, and unit roles |
| Representation subtype | [`ap242_advanced_brep_root.step`](../fixtures/ap242-product-paths/ap242_advanced_brep_root.step) | Controlled advanced B-rep representation root without geometry evaluation |
| Optional and subset boundaries | [`product_without_shape.step`](../fixtures/ap242-product-paths/product_without_shape.step), [`unsupported_representation.step`](../fixtures/ap242-product-paths/unsupported_representation.step), [`context_without_units.step`](../fixtures/ap242-product-paths/context_without_units.step) | Absent or unsupported semantic evidence remains quarantine |
| Schema boundary | [`ap214_schema_boundary.step`](../fixtures/ap242-product-paths/ap214_schema_boundary.step) | Familiar entity names do not establish AP242 interpretation |
| Invalid and bounded routes | [`wrong_formation_target.step`](../fixtures/ap242-product-paths/wrong_formation_target.step), [`unresolved_formation.step`](../fixtures/ap242-product-paths/unresolved_formation.step), [`path_budget.step`](../fixtures/ap242-product-paths/path_budget.step) | Wrong type, absent target, and semantic work limit |

![AP242 product-path corpus](../results/ap242_product_paths.png)

The representative block is encoded with product and shape context sufficient
for the controlled path query. The advanced B-rep sample reuses the v0.21.0
closed tetrahedron, so its shape remains inspectable through the existing
geometry control below. The path figure visualizes semantic relationships,
not evaluated solid geometry or AP242 conformance.

![AP242 advanced B-rep tetrahedron control](../results/step_part21_geometry_control.png)

## v0.30.0 — AP242 Assembly and Placement Samples

Directory: [`fixtures/ap242-assemblies/`](../fixtures/ap242-assemblies/)

Manifest: [`manifest.csv`](../fixtures/ap242-assemblies/manifest.csv)

The corpus contains 17 generated STEP files. Each readable file encodes only
synthetic products and block primitives. The manifest binds the exact bytes
and SHA-256 identity to an expected assembly route and explicit occurrence,
path, relation, depth, and unit-conversion budgets.

| Sample group | Representative samples | Boundary isolated |
| --- | --- | --- |
| Placement direction | [`single_translation.step`](../fixtures/ap242-assemblies/single_translation.step), [`rotated_occurrence.step`](../fixtures/ap242-assemblies/rotated_occurrence.step), [`source_frame_offset.step`](../fixtures/ap242-assemblies/source_frame_offset.step) | Translation, rotation, and child-frame inverse order |
| Nested reuse | [`nested_reuse.step`](../fixtures/ap242-assemblies/nested_reuse.step) | Distinct occurrences of one reusable definition and parent-to-root composition |
| Unit conversion | [`conversion_based_inch.step`](../fixtures/ap242-assemblies/conversion_based_inch.step) | Conversion-based child unit normalized into the parent millimetre frame |
| Optional and subset boundaries | [`missing_occurrence_shape.step`](../fixtures/ap242-assemblies/missing_occurrence_shape.step), [`unsupported_transform_operator.step`](../fixtures/ap242-assemblies/unsupported_transform_operator.step), [`missing_length_unit.step`](../fixtures/ap242-assemblies/missing_length_unit.step) | Missing evidence and unsupported forms remain quarantine |
| Invalid and bounded routes | [`wrong_representation_order.step`](../fixtures/ap242-assemblies/wrong_representation_order.step), [`assembly_cycle.step`](../fixtures/ap242-assemblies/assembly_cycle.step), [`unit_conversion_cycle.step`](../fixtures/ap242-assemblies/unit_conversion_cycle.step), [`assembly_depth_budget.step`](../fixtures/ap242-assemblies/assembly_depth_budget.step) | Direction mismatch, cycles, and semantic work limits |

![AP242 assembly placement corpus](../results/ap242_assembly_paths.png)

The right panel is a coordinate-frame view of evaluated occurrence origins,
not a kernel rendering of moved solids. The STEP files include block geometry
so the exchange records remain inspectable, but v0.30.0 does not tessellate,
transform, intersect, or validate those solids.

## v0.31.0 — Geometry-Kernel Round-Trip Sample

Directory: [`fixtures/geometry-kernel-selection/`](../fixtures/geometry-kernel-selection/)

Manifest: [`manifest.csv`](../fixtures/geometry-kernel-selection/manifest.csv)

The corpus contains one STEP file generated headlessly by the pinned optional
OCCT route. `ocp_box.step` is a 10 × 20 × 30 synthetic box with a normalized
writer timestamp and process counter. Its committed SHA-256 binds the visible
sample to the round-trip observations.

| Sample | Construction | Recorded round-trip evidence |
| --- | --- | --- |
| [`ocp_box.step`](../fixtures/geometry-kernel-selection/ocp_box.step) | `BRepPrimAPI_MakeBox(10.0, 20.0, 30.0)` | 1 solid, 6 faces, 12 unique edges, and 8 unique vertices before and after STEP exchange; both shapes pass the selected kernel check |

![Geometry-kernel selection and box round trip](../results/geometry_kernel_selection.png)

The figure includes the candidate gate matrix and the topology counts rather
than a tessellated rendering. v0.31.0 proves one construction and exchange
probe, not face geometry, visual equivalence, general STEP compatibility, or
independent-kernel agreement. The strict internal Part 21 parser rejects the
writer's `.PCURVE_S1.` spelling; the exact boundary remains visible in the
probe CSV.

## Regeneration

```bash
python experiments/run_step_brep_topology.py \
  --fixture-dir fixtures/step-brep-topology \
  --refresh-fixtures

python experiments/run_step_exchange_structure.py \
  --fixture-dir fixtures/step-part21-exchange \
  --refresh-fixtures

python experiments/run_step_part21_source_model.py \
  --fixture-dir fixtures/step-part21-source-model \
  --refresh-fixtures

python experiments/run_step_part21_conformance.py \
  --fixture-dir fixtures/step-part21-conformance \
  --refresh-fixtures

python experiments/run_express_schema_model.py \
  --fixture-dir fixtures/express-schema-model \
  --refresh-fixtures

python experiments/run_express_symbol_resolution.py \
  --fixture-dir fixtures/express-symbol-resolution \
  --refresh-fixtures

python experiments/run_step_express_validation.py \
  --fixture-dir fixtures/step-express-validation \
  --refresh-fixtures

python experiments/run_step_graph_queries.py \
  --fixture-dir fixtures/step-graph-queries \
  --refresh-fixtures

python experiments/run_ap242_product_paths.py \
  --fixture-dir fixtures/ap242-product-paths \
  --refresh-fixtures

python experiments/run_ap242_assembly.py \
  --fixture-dir fixtures/ap242-assemblies \
  --refresh-fixtures

python experiments/run_geometry_kernel_selection.py \
  --fixture-dir fixtures/geometry-kernel-selection \
  --refresh-fixtures
```

## Interpretation Boundary

Opening a sample in a viewer is useful diagnostic evidence, but viewer success
does not prove Part 21 conformance, EXPRESS conformance or semantic validity,
application-protocol conformance, B-Rep validity, unit correctness, tolerance
consistency, or preservation across another kernel. Those claims require the
separate observations and tests defined by each study.
