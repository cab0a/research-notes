# STEP Sample and Preview Catalog

## 日本語概要

本書は、STEP/B-rep調査でコミットした合成サンプル、hash付きmanifest、目視用preview、主な用途を対応付けます。v0.21.0の位相、v0.22.0の高度な交換構造、v0.23.0の統合source model用サンプルを収録します。閉じた四面体は形状を目視できる共通integration controlとして保存し、構文だけを扱うサンプルにはsource model図を用います。previewはschema適合性、幾何妥当性、公差、kernel間互換性の証明ではありません。詳細は以下の英語本文に示します。

---

## English Summary

This catalog maps committed synthetic STEP samples to their manifests,
previews, research purpose, and validation boundary. Samples live under
`fixtures/` because they are both human-inspectable examples and exact CI
inputs.

## Sample Policy

Each STEP/B-Rep study keeps the actual input bytes whenever licensing and
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
```

## Interpretation Boundary

Opening a sample in a viewer is useful diagnostic evidence, but viewer success
does not prove Part 21 conformance, application-protocol conformance, B-Rep
validity, unit correctness, tolerance consistency, or preservation across
another kernel. Those claims require the separate observations and tests
defined by each study.
