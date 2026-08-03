# STEP Sample and Preview Catalog

## 日本語概要

本書は、STEP/B-repとEXPRESSの調査でコミットした合成サンプル、hash付きmanifest、目視用preview、主な用途を対応付けます。v0.21.0からv0.24.0までの位相・交換構造・source model・版別構文適合性に加え、v0.25.0のEXPRESS字句・構文・未解決schema modelとv0.26.0のシンボル・型・継承graphを収録します。形状にはpreview、構文だけを扱うサンプルには構造・関係図を用いますが、schema適合性、幾何妥当性、公差、kernel間互換性の証明ではありません。詳細は以下の英語本文に示します。

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
```

## Interpretation Boundary

Opening a sample in a viewer is useful diagnostic evidence, but viewer success
does not prove Part 21 conformance, EXPRESS conformance or semantic validity,
application-protocol conformance, B-Rep validity, unit correctness, tolerance
consistency, or preservation across another kernel. Those claims require the
separate observations and tests defined by each study.
