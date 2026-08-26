# Study Index

## 日本語概要

本書は、画像処理、JPEG、メタデータ、STEP・EXPRESS・AP242、形状計算核、B-rep解析を扱う49件の研究を索引化しています。v0.49.0は3つの固定STEP標本を3つの構文解析実装と2つの読込経路で比較し、構文受理、形状転送、文書属性、形状計算核間可搬性を分離します。各版の問い、代表結果、成果物、再現コマンド、完全な研究ノートを対応付けます。

研究ごとの要点と成果物へのリンクは以下の英語本文を参照してください。

---

## English Summary

This index maps each published release to its research question, representative
finding, committed evidence, reproduction command, and complete note. The
numbers below describe the declared synthetic controls and recorded runtime
profiles; they are not general thresholds or production guarantees.

## Blur Measurement and Localization

### v0.1.0 — Laplacian Variance as a Blur Heuristic

**Question:** How does Laplacian variance respond to controlled Gaussian blur,
and when does noise make the score misleading?

**Representative finding:** Noiseless Gaussian blur lowers the score for the
fixed patterns. Added noise can raise the score of a blurred image and reverse
a simple sharp-versus-blurred interpretation.

- [Complete note](../notes/laplacian-variance-blur.md)
- [Summary CSV](../results/laplacian_variance_summary.csv)
- [Figure](../results/laplacian_variance.png)

```bash
python experiments/run_laplacian_variance.py
```

### v0.2.0 — Laplacian Variance vs. Tenengrad

**Question:** How do Laplacian variance and area-normalized Tenengrad differ
under blur, noise, bounded motion blur, and resize controls?

**Representative finding:** The study records 720 repeated observations.
Both metrics respond to blur, but their score scales and sensitivity to noise,
motion direction, and resizing differ.

- [Complete note](../notes/laplacian-vs-tenengrad.md)
- [Trial CSV](../results/focus_metric_trials.csv)
- [Summary CSV](../results/focus_metric_summary.csv)
- [Figure](../results/focus_metric_comparison.png)

```bash
python experiments/run_focus_metric_comparison.py
```

### v0.3.0 — Local Blur and Spatial Aggregation

**Question:** How does a small blurred region disappear inside a global or
mean-aggregated score?

**Representative finding:** With one of 16 aligned tiles blurred at sigma 3,
the mean full-image ratios remain 0.936866 for Laplacian variance and 0.940676
for Tenengrad. The mean minimum-tile ratios fall to 0.005025 and 0.062950,
showing the dilution created by global aggregation.

- [Complete note](../notes/local-blur-spatial-aggregation.md)
- [Aggregate CSV](../results/local_blur_aggregate.csv)
- [Figure](../results/local_blur_spatial_aggregation.png)

```bash
python experiments/run_local_blur_evaluation.py
```

### v0.4.0 — Window Geometry and Robustness

**Question:** How do window size, stride, region alignment, noise, and
low-texture content affect local blur detection?

**Representative finding:** A 64/64 grid captures at most 25% of a 64-pixel
region offset by 32 pixels, while a 64/32 grid recovers 100% coverage. Under
repeated sigma-3 trials, noise standard deviation 15 raises the mean minimum
Laplacian ratio from 0.005765 to 0.200820 on the overlapping grid.

- [Complete note](../notes/window-geometry-robustness.md)
- [Summary CSV](../results/window_geometry_summary.csv)
- [Figure](../results/window_geometry_robustness.png)

```bash
python experiments/run_window_geometry_evaluation.py
```

## Processing-Pipeline Sensitivity

### v0.5.0 — Preprocessing Sensitivity and Calibration Drift

**Question:** Does a calibration rule learned on one image pipeline transfer
after resize, denoising, sharpening, or JPEG compression?

**Representative finding:** Across 9,360 observations, resize and Gaussian
denoising lower clean-sharp mean Laplacian ratios to 0.091416 and 0.048873.
The unchanged synthetic midpoint rule then falls to balanced accuracy 0.5.

- [Complete note](../notes/preprocessing-sensitivity-calibration-drift.md)
- [Calibration summary](../results/preprocessing_calibration_summary.csv)
- [Figure](../results/preprocessing_calibration_drift.png)

```bash
python experiments/run_preprocessing_sensitivity.py
```

### v0.6.0 — Optical Blur Models and Directional Motion

**Question:** How do disk defocus and directional motion interact with image
orientation, metric choice, and noise?

**Representative finding:** Across 5,100 observations, motion length 15
without noise produces aligned-to-perpendicular ratios of 0.066796 for
Laplacian variance and 0.024429 for Tenengrad. Noise standard deviation 15
raises the Laplacian ratio to 1.008207 in the fixed setting.

- [Complete note](../notes/optical-blur-models-directional-motion.md)
- [Summary CSV](../results/optical_blur_summary.csv)
- [Figure](../results/optical_blur_directional_sensitivity.png)

```bash
python experiments/run_optical_blur_models.py
```

### v0.7.0 — Photometric Normalization and Recompression Drift

**Question:** How do intensity transforms, normalization, operation order, and
repeated JPEG encoding change derivative-based focus measures?

**Representative finding:** Across 11,520 observations, contrast gain 0.50
lowers clean-sharp responses to approximately 0.25 for both metrics and reduces
the unchanged midpoint calibration to balanced accuracy 0.5.

- [Complete note](../notes/photometric-normalization-recompression-drift.md)
- [Calibration summary](../results/photometric_recompression_calibration_summary.csv)
- [Figure](../results/photometric_recompression_drift.png)

```bash
python experiments/run_photometric_recompression.py
```

### v0.8.0 — JPEG Compression History

**Question:** Do quality order, block-grid alignment, and chroma sampling make
two-stage JPEG histories interchangeable?

**Representative finding:** Across 4,320 observations, an aligned grayscale
quality-75 second round remains at a six-decimal final-to-primary ratio of
1.000000, while a 4 x 4 grid shift changes the sigma-3 Laplacian ratio to
0.805242. Reversing quality order also changes the response.

- [Complete note](../notes/jpeg-compression-history.md)
- [Response summary](../results/jpeg_history_response_summary.csv)
- [Figure](../results/jpeg_history_sensitivity.png)

```bash
python experiments/run_jpeg_compression_history.py
```

## JPEG Codec and Metadata Contracts

### v0.9.0 — JPEG Quantization Tables and Codec Portability

**Question:** When do numeric quality, quantization tables, encoded bytes,
decoded pixels, and derivative responses agree across codec wrappers?

**Representative finding:** The pinned OpenCV 4.13.0 and Pillow 12.3.0 default
paths produce identical DQT fingerprints and JPEG bytes throughout the
quality-1-to-100 sweep and all 72 larger image conditions. Huffman optimization
preserves DQT and decoded pixels while changing every file.

- [Complete note](../notes/jpeg-quantization-codec-portability.md)
- [Quality sweep](../results/jpeg_quality_table_sweep.csv)
- [Figure](../results/jpeg_codec_portability.png)

```bash
python experiments/run_jpeg_codec_portability.py
```

### v0.10.0 — Cross-Platform Decoded-Pixel Contracts

**Question:** Do fixed baseline JPEG streams decode to the declared pixel
arrays across recorded operating-system and codec builds?

**Representative finding:** The five-profile matrix produces 120 of 120 exact
reference decodes and 60 of 60 exact within-profile OpenCV-versus-Pillow
comparisons for the 12-fixture corpus.

- [Complete note](../notes/cross-platform-codec-builds-decoded-pixel-contracts.md)
- [Cross-platform summary](../results/jpeg_cross_platform_contract_summary.csv)
- [Figure](../results/jpeg_cross_platform_contracts.png)

```bash
python experiments/run_cross_platform_codec_contracts.py
```

### v0.11.0 — Independent Codec Families and Advanced JPEG Syntax

**Question:** How do baseline, progressive, restart-marker, grayscale, RGB,
and CMYK streams behave across OpenCV, Pillow, and native FFmpeg decoding?

**Representative finding:** Across five CI profiles, all 150 observations
satisfy the array interface and all 75 controlled progression and restart
comparisons are pixel-exact. FFmpeg produces two hashes for four 4:2:0 RGB
fixtures because the recorded macOS arm64 result differs from the other four
profiles.

- [Complete note](../notes/independent-codec-families-advanced-jpeg-syntax.md)
- [Cross-platform summary](../results/jpeg_advanced_cross_platform_summary.csv)
- [Figure](../results/jpeg_advanced_cross_platform_codec_families.png)

```bash
python experiments/run_advanced_jpeg_syntax.py
```

### v0.12.0 — Color Management, YCCK, and Metadata Interpretation

**Question:** What changes when raw decoding is separated from EXIF
orientation, ICC conversion, and CMYK/YCCK interpretation policies?

**Representative finding:** All 27 local raw metadata-invariance pairs are
pixel-exact when orientation and ICC processing are disabled. All eight OpenCV
automatic-orientation and Pillow explicit-transpose outputs match their
declared normalized arrays. The numeric color differences remain synthetic
code-value responses, not device-color accuracy claims.

- [Complete note](../notes/color-management-ycck-metadata-interpretation.md)
- [Cross-platform summary](../results/jpeg_metadata_cross_platform_summary.csv)
- [Figure](../results/jpeg_metadata_cross_platform_interpretation.png)

```bash
python experiments/run_color_metadata_interpretation.py
```

### v0.13.0 — Malformed Metadata, Recovery, and Trust Boundaries

**Question:** When one JPEG image stream carries valid, malformed, ambiguous,
or excessive application metadata, which inputs pass a strict audit and which
still return pixels through OpenCV, Pillow, or FFmpeg?

**Representative finding:** The local audit accepts 5 of 21 fixtures, while 60
of 63 decoder probes return exact control pixels. Across five recorded
profiles, 300 of 315 probes succeed, including 225 of 240 probes for fixtures
rejected by the strict audit. Decode success therefore does not validate the
metadata.

- [Complete note](../notes/malformed-metadata-decoder-recovery-trust-boundaries.md)
- [Local summary](../results/jpeg_recovery_summary.csv)
- [Cross-platform summary](../results/jpeg_recovery_cross_platform_summary.csv)
- [Figure](../results/jpeg_recovery_cross_platform_contracts.png)

```bash
python experiments/run_malformed_metadata_recovery.py
```

### v0.14.0 — Metadata Round-Trip Preservation and Sanitization Policies

**Question:** How do blind preservation, stripping, supported normalization,
and strict rejection differ across JPEG decode and re-encode boundaries?

**Representative finding:** For each local re-encoder, preserve emits 19
outputs but only 5 pass the strict metadata audit. Strip and normalize emit 19
strict-accepted outputs, while reject emits only the 5 accepted inputs. All
emitted outputs remain exact to their policy-free compressed core and raw-pixel
control. Across five profiles, all 168 fixed behavior contracts repeat and all
124 output-bearing contracts retain one JPEG and pixel hash, showing that
metadata transfer, validity, semantics, and pixels are separate contracts.

- [Complete note](../notes/metadata-round-trip-preservation-sanitization-policies.md)
- [Local observations](../results/jpeg_round_trip_observations.csv)
- [Local summary](../results/jpeg_round_trip_summary.csv)
- [Cross-platform summary](../results/jpeg_round_trip_cross_platform_summary.csv)
- [Cross-platform figure](../results/jpeg_metadata_round_trip_cross_platform.png)

```bash
python experiments/run_metadata_round_trip.py
```

### v0.15.0 — Multi-Generation Metadata Policy Drift and Idempotence

**Question:** When preserve, strip, and supported normalization are applied
through ten repeated JPEG generations, which metadata, byte, and pixel
properties stabilize?

**Representative finding:** All 60 local fixture, encoder, and sequence
contracts reach one metadata-state hash after their final policy transition.
Preserve retains all eight generation-10 controlled envelopes, normalize
retains the four supported EXIF and ICC envelopes, and strip prevents a later
preserve stage from restoring removed metadata. Across five profiles, all 660
fixture, encoder, sequence, and generation contracts retain one behavior,
metadata, compressed-core, complete-JPEG, and decoded-pixel hash.

- [Complete note](../notes/multi-generation-metadata-policy-drift.md)
- [Observations](../results/jpeg_metadata_generation_observations.csv)
- [Summary](../results/jpeg_metadata_generation_summary.csv)
- [Temporal contracts](../results/jpeg_metadata_generation_contracts.csv)
- [Figure](../results/jpeg_metadata_generation_drift.png)
- [Cross-platform summary](../results/jpeg_metadata_generation_cross_platform_summary.csv)
- [Cross-platform figure](../results/jpeg_metadata_generation_cross_platform.png)

```bash
python experiments/run_metadata_generation_drift.py
```

### v0.16.0 — Field-Level Metadata Provenance and Selective Retention

**Question:** Can a JPEG pipeline retain selected metadata fields while
recording an auditable source-to-output decision for every controlled field?

**Representative finding:** The 24 local outputs and 288 field decisions all
preserve strict validity, the policy-free compressed image core, and raw
decoded pixels. The location denylist removes both GPS fields but retains two
unclassified fields. The visual, catalog, and attribution allowlists retain
only their declared 2, 6, and 4 fields. Two byte-distinct EXIF and XMP layouts
produce one normalized metadata state and one complete JPEG per encoder and
policy. Across five profiles, all 24 contracts retain one behavior, decision,
metadata-state, complete-JPEG, and decoded-pixel hash.

- [Complete note](../notes/field-level-metadata-provenance-selective-retention.md)
- [Field decisions](../results/jpeg_field_provenance_decisions.csv)
- [Output observations](../results/jpeg_selective_retention_observations.csv)
- [Summary](../results/jpeg_selective_retention_summary.csv)
- [Figure](../results/jpeg_selective_retention.png)
- [Cross-platform summary](../results/jpeg_selective_retention_cross_platform_summary.csv)
- [Cross-platform contracts](../results/jpeg_selective_retention_cross_platform_contracts.csv)
- [Cross-platform figure](../results/jpeg_selective_retention_cross_platform.png)

```bash
python experiments/run_field_level_metadata_provenance.py
```

### v0.17.0 — Resource-Bounded Metadata Parsing and Quarantine Decisions

**Question:** Can a JPEG metadata admission layer enforce explicit work
ceilings, stop at the first disallowed unit, and return deterministic routing
decisions before image decoding?

**Representative finding:** All ten at-limit fixtures return `accept`, while
all ten limit-plus-one fixtures return `quarantine` and keep their
corresponding admitted counter at or below the limit. Prohibited XMP and
invalid EXIF controls are quarantined, and the JPEG segment overrun is
rejected. Across five profiles, all 24 fixture contracts retain one decision,
reason-code, issue, counter, and fixture-hash signature.

- [Complete note](../notes/resource-bounded-metadata-parsing-quarantine.md)
- [Local observations](../results/jpeg_resource_budget_observations.csv)
- [Local summary](../results/jpeg_resource_budget_summary.csv)
- [Local figure](../results/jpeg_resource_budget_boundaries.png)
- [Cross-platform observations](../results/jpeg_resource_budget_cross_platform_observations.csv)
- [Cross-platform contracts](../results/jpeg_resource_budget_cross_platform_contracts.csv)
- [Cross-platform summary](../results/jpeg_resource_budget_cross_platform_summary.csv)
- [Cross-platform figure](../results/jpeg_resource_budget_cross_platform.png)

```bash
python experiments/run_resource_bounded_metadata.py
```

### v0.18.0 — Extended Metadata Families, Nested Payloads, and Parser Coverage

**Question:** Can a resource-admitted parser recognize selected extended
metadata families, resolve nested relationships independently of segment
order, and quarantine incomplete or ambiguous structures without claiming
complete format semantics?

**Representative finding:** Eight of 15 synthetic fixtures are accepted and
all nine relationships declared by accepted fixtures are resolved. Seven
missing, duplicate, orphaned, truncated, mismatched, or out-of-bounds controls
are quarantined with stable reason codes. Forward and reverse Extended XMP
chunk order reconstruct the same 270-byte packet, while maker-note bytes remain
explicitly opaque.

- [Complete note](../notes/extended-metadata-families-nested-payloads-parser-coverage.md)
- [Observations](../results/jpeg_metadata_coverage_observations.csv)
- [Summary](../results/jpeg_metadata_coverage_summary.csv)
- [Figure](../results/jpeg_metadata_coverage.png)

```bash
python experiments/run_metadata_family_coverage.py
```

### v0.19.0 — Provenance Assertions and Transform Integrity

**Question:** Can explicit digest scopes distinguish metadata-only,
compressed-image, and decoded-pixel changes, and what evidence is still
missing before a matching record can be called authenticated provenance?

**Representative finding:** Eleven fixtures produce two `valid_binding`, two
`valid_derived_binding`, four `stale_binding`, and one each of missing,
malformed, and multiple assertion states. Metadata reordering preserves all
three scopes; sanitization invalidates only normalized metadata; re-encoding
and pixel editing invalidate image-core and decoded-pixel scopes. Renewed
unsigned assertions match current outputs but do not authenticate an actor or
validate the declared parent.

- [Complete note](../notes/provenance-assertions-transform-integrity.md)
- [Observations](../results/jpeg_transform_integrity_observations.csv)
- [Summary](../results/jpeg_transform_integrity_summary.csv)
- [Figure](../results/jpeg_transform_integrity.png)

```bash
python experiments/run_transform_integrity.py
```

### v0.20.0 — Policy Composition and Explainable Decisions

**Question:** Can independently tested JPEG metadata controls be composed into
deterministic routing decisions while preserving the first decisive rule,
profile assumptions, and output effects as auditable evidence?

**Representative finding:** Nine synthetic inputs under four policy profiles
produce 36 observations: 4 `accept`, 5 `sanitize`, 23 `quarantine`, and 4
`reject`. Every trace has exactly one decisive final stage. Resource failures
stop before deeper parsing, incomplete relationships stop at coverage, stale
assertions stop at integrity, and clean inputs reach profile-specific retention
rules.

- [Complete note](../notes/policy-composition-explainable-decisions.md)
- [Observations](../results/jpeg_policy_composition_observations.csv)
- [Summary](../results/jpeg_policy_composition_summary.csv)
- [Figure](../results/jpeg_policy_composition.png)

```bash
python experiments/run_policy_composition.py
```

## STEP and B-Rep Foundations

### v0.21.0 — STEP Part 21 and B-Rep Topology Inspection

**Question:** How much face-, edge-, shell-, and solid-level structure can be
recovered deterministically from a controlled Part 21 subset without adopting
a geometry kernel?

**Representative finding:** The closed tetrahedron resolves to 4 faces, 6
edges, 1 shell, 1 solid, and no free edges. Removing one face exposes 3 free
edges. Two disconnected tetrahedra retain separate ownership, and the surface
catalog classifies six declared surface families. An unresolved reference is
quarantined and a duplicate entity identifier is rejected.

- [Complete note](../notes/step-part21-brep-topology-inspection.md)
- [Observations](../results/step_brep_topology_observations.csv)
- [Face inventory](../results/step_brep_faces.csv)
- [Summary](../results/step_brep_topology_summary.csv)
- [Figure](../results/step_brep_topology.png)
- [Learning and modeling roadmap](brep-learning-roadmap.md)

```bash
python experiments/run_step_brep_topology.py
```

### v0.22.0 — Advanced Part 21 Exchange Structure and Parser Boundaries

**Question:** Which advanced Part 21 structures can a bounded parser recognize
without confusing syntax with schema validation, resource resolution,
signature verification, archive safety, or evaluated geometry?

**Representative finding:** All 13 synthetic fixtures match their declared
routes: 5 accept, 4 quarantine, and 4 reject. Supported controls cover repeated
named DATA sections, a complex entity, direct UTF-8, a binary token, and a
tagged anchor. External references, an unverified signature, excessive
nesting, and a ZIP container remain quarantined. The geometry-bearing control
preserves the closed tetrahedron with 74 entities and 97 local references.

- [Complete note](../notes/advanced-part21-exchange-parser-boundaries.md)
- [Observations](../results/step_part21_exchange_observations.csv)
- [DATA-section inventory](../results/step_part21_data_sections.csv)
- [Summary](../results/step_part21_exchange_summary.csv)
- [Boundary figure](../results/step_part21_exchange_boundaries.png)
- [Geometry control preview](../results/step_part21_geometry_control.png)
- [Sample catalog](step-sample-catalog.md)
- [Long-term roadmap](brep-learning-roadmap.md)

```bash
python experiments/run_step_exchange_structure.py
```

### v0.23.0 — Unified Part 21 Lexer, Grammar, and Source Model

**Question:** Can one source-preserving Python parser replace the separate
v0.21 and v0.22 readers while retaining exact source evidence, localized
diagnostics, and the published topology and exchange observations?

**Representative finding:** All ten synthetic fixtures match their declared
routes: 5 accept, 2 quarantine, and 3 reject. Every accepted fixture
reconstructs its exact UTF-8 bytes, producing 1,435 token rows with raw
spelling and character, byte, line, and column coordinates. The closed
tetrahedron remains at 74 entities and 97 references and still resolves its
published topology through the compatibility adapter.

- [Complete note](../notes/unified-part21-lexer-grammar-source-model.md)
- [Observations](../results/step_part21_source_model_observations.csv)
- [Token inventory](../results/step_part21_token_inventory.csv)
- [Summary](../results/step_part21_source_model_summary.csv)
- [Figure](../results/step_part21_source_model.png)
- [Sample catalog](step-sample-catalog.md)
- [Parser-first roadmap](brep-learning-roadmap.md)

```bash
python experiments/run_step_part21_source_model.py
```

### v0.24.0 — Part 21 Grammar Coverage and Conformance Testing

**Question:** Which Edition 1, Edition 2, and Edition 3 lexical, section,
implementation-level, conformance-class, and archive rules does the controlled
Python parser implement, and where do independent public parsers differ?

**Representative finding:** All 34 synthetic fixtures match their expected
internal decisions: 17 accept and 17 reject. STEPutils accepts 14 fixtures and
agrees with 23 expectations, while the IfcOpenShell `step-file-parser` accepts
five and agrees with 22. The disagreements include Edition 2/3 features,
decimal-point requirements, all-zero occurrence names, optional data, and ZIP
transport. They are retained as diagnostic evidence rather than parser ranks.

- [Complete note](../notes/part21-grammar-conformance.md)
- [Observations](../results/step_part21_conformance_observations.csv)
- [Parser comparison](../results/step_part21_parser_comparison.csv)
- [Grammar coverage](../results/step_part21_grammar_coverage.csv)
- [Parser manifest](../results/step_part21_parser_manifest.csv)
- [Summary](../results/step_part21_conformance_summary.csv)
- [Figure](../results/step_part21_conformance.png)
- [Sample catalog](step-sample-catalog.md)

```bash
python experiments/run_step_part21_conformance.py
```

### v0.25.0 — EXPRESS Lexer, Parser, and Schema Model

**Question:** Can a bounded, source-preserving Python parser turn controlled
EXPRESS declarations into an explicit unresolved schema model without implying
symbol resolution, type correctness, or executable rule semantics?

**Representative finding:** All 40 synthetic fixtures match their expected
routes: 20 accept, 19 reject, and one quarantine at the declared comment-depth
limit. Accepted sources produce 59 inventory rows covering schemas, types,
entities, explicit, derived, and inverse attributes, interfaces, constants,
rules, and algorithm envelopes. Symbol resolution, type checking, expression
validation, and rule execution remain recorded as `not_attempted` or
`envelope_only`.

- [Complete note](../notes/express-lexer-parser-schema-model.md)
- [Observations](../results/express_schema_observations.csv)
- [Schema inventory](../results/express_schema_inventory.csv)
- [Grammar coverage](../results/express_grammar_coverage.csv)
- [Summary](../results/express_schema_summary.csv)
- [Figure](../results/express_schema_model.png)
- [Sample catalog](step-sample-catalog.md)

```bash
python experiments/run_express_schema_model.py
```

### v0.26.0 — EXPRESS Symbols, Types, and Inheritance

**Question:** Can a bounded resolver connect parsed EXPRESS names to explicit
symbols, terminal type domains, and entity inheritance without silently
selecting ambiguous imports or hiding graph cycles?

**Representative finding:** All 38 synthetic fixtures match their expected
routes: 20 accept, 17 reject, and one semantic-budget quarantine. The evidence
contains 118 symbol rows and 72 references: 61 resolve, seven remain
unresolved, one is ambiguous, and three have an invalid declaration kind.
Defined-type and inheritance tables preserve unresolved, ambiguous, and cyclic
states separately.

- [Complete note](../notes/express-symbols-types-inheritance.md)
- [Observations](../results/express_resolution_observations.csv)
- [Symbol table](../results/express_symbols.csv)
- [Reference resolution](../results/express_reference_resolution.csv)
- [Defined types](../results/express_type_resolution.csv)
- [Aggregate bounds](../results/express_aggregate_bounds.csv)
- [Entity inheritance](../results/express_inheritance.csv)
- [Summary](../results/express_resolution_summary.csv)
- [Figure](../results/express_symbols_types_inheritance.png)
- [Sample catalog](step-sample-catalog.md)

```bash
python experiments/run_express_symbol_resolution.py
```

### v0.27.0 — Part 21 Validation Against EXPRESS

**Question:** Can a bounded validator distinguish syntactically readable STEP
records from schema-bound instances whose entity names, parameter positions,
values, references, and inheritance mapping agree with a controlled EXPRESS
document?

**Representative finding:** All 40 paired synthetic fixtures match their
declared routes: 15 accept, 21 reject, and four quarantine. Thirty-five
parameters validate, 13 fail with attribute-level reasons, and two remain
deferred. Internal inheritance ordering, shared-diamond deduplication, `$`,
`*`, aggregates, `SELECT`, and entity-reference compatibility are checked.
Complex evaluated sets, constants, width constraints, rules, AP242 meaning,
and geometry remain deferred.

- [Complete note](../notes/part21-validation-against-express.md)
- [Observations](../results/step_express_validation_observations.csv)
- [DATA-section bindings](../results/step_express_sections.csv)
- [Instance validation](../results/step_express_instances.csv)
- [Parameter validation](../results/step_express_parameters.csv)
- [Diagnostics](../results/step_express_diagnostics.csv)
- [Summary](../results/step_express_validation_summary.csv)
- [Figure](../results/step_express_validation.png)
- [Paired sample catalog](step-sample-catalog.md)

```bash
python experiments/run_step_express_validation.py
```

### v0.28.0 — Generic STEP Graph and Query API

**Question:** Can the source-preserving Part 21 model expose stable,
source-linked graph records and bounded queries without confusing physical
references with AP242 product, assembly, or B-Rep meaning?

**Representative finding:** All 14 synthetic fixtures match their expected
routes: 11 accept, two quarantine, and one reject. The accepted graphs contain
31 nodes and 25 reference-occurrence edges. Eighty-six query rows complete,
two report the controlled traversal-depth boundary, and one orphan query is
not evaluated because its prerequisite traversal is partial.

- [Complete note](../notes/generic-step-graph-query-api.md)
- [Observations](../results/step_graph_observations.csv)
- [Nodes](../results/step_graph_nodes.csv)
- [Reference edges](../results/step_graph_edges.csv)
- [Queries](../results/step_graph_queries.csv)
- [Summary](../results/step_graph_summary.csv)
- [Versioned JSON](../results/step_graph.json)
- [Figure](../results/step_graph.png)
- [Sample catalog](step-sample-catalog.md)

```bash
python experiments/run_step_graph_queries.py
```

### v0.29.0 — AP242 Product and Representation Paths

**Question:** Can physical Part 21 references support a controlled AP242
product-to-representation query while keeping schema roles, optional paths,
unsupported forms, and source provenance explicit?

**Representative finding:** All 14 synthetic fixtures match their expected
routes: three accept, eight quarantine, and three reject. Five resolved paths
retain 59 unique source-linked semantic relations, nine direct representation
items, five placements, and 15 assigned units. Missing shape associations and
unsupported schemas remain deferred rather than being called corrupt.

- [Complete note](../notes/ap242-product-representation-paths.md)
- [Observations](../results/ap242_path_observations.csv)
- [Resolved paths](../results/ap242_product_paths.csv)
- [Semantic relations](../results/ap242_semantic_relations.csv)
- [Representation items](../results/ap242_representation_items.csv)
- [Context units](../results/ap242_context_units.csv)
- [Diagnostics](../results/ap242_path_diagnostics.csv)
- [Summary](../results/ap242_path_summary.csv)
- [Versioned JSON](../results/ap242_product_paths.json)
- [Figure](../results/ap242_product_paths.png)
- [Sample catalog](step-sample-catalog.md)

```bash
python experiments/run_ap242_product_paths.py
```

### v0.30.0 — AP242 Assembly Occurrences, Placements, and Units

**Question:** Can reusable product definitions, placed occurrences,
child-to-parent transformations, nested paths, and length-unit conversion be
evaluated without collapsing their distinct identities or losing source
provenance?

**Representative finding:** All 17 synthetic STEP fixtures match their
declared routes: five accept, six quarantine, and six reject. The accepted
fixtures contain eight occurrences and eight root-relative paths. A rotated
subassembly composes its local child origin to `(100, 10, 0)` millimetres, and
the conversion-based control maps a one-inch source-frame offset to the
declared `25.4` millimetre result.

- [Complete note](../notes/ap242-assembly-occurrences.md)
- [Observations](../results/ap242_assembly_observations.csv)
- [Occurrences](../results/ap242_assembly_occurrences.csv)
- [Root-relative paths](../results/ap242_assembly_paths.csv)
- [Source-linked relations](../results/ap242_assembly_relations.csv)
- [Unit observations](../results/ap242_assembly_units.csv)
- [Diagnostics](../results/ap242_assembly_diagnostics.csv)
- [Summary](../results/ap242_assembly_summary.csv)
- [Versioned JSON](../results/ap242_assembly.json)
- [Figure](../results/ap242_assembly_paths.png)
- [Sample catalog](step-sample-catalog.md)

```bash
python experiments/run_ap242_assembly.py
```

### v0.31.0 — Geometry Kernel and License Decision

**Question:** Which geometry-kernel route supplies reproducible Python STEP,
analytic B-Rep, modeling, and headless evaluation while keeping wrapper,
native-kernel, packaging, and redistribution boundaries explicit?

**Representative finding:** CadQuery OCP with OCCT is the only one of eight
candidates that passes all six project-specific technical gates. A generated
10 × 20 × 30 box retains 1 solid, 6 faces, 12 unique edges, and 8 unique
vertices after STEP write/read. The installed package records total
940,567,380 bytes and do not expose an OCCT LGPL notice through the audited
standard license-file inventory. The native route is therefore optional and
not redistributed by this repository.

- [Complete note](../notes/geometry-kernel-license-decision.md)
- [Candidate matrix](../results/geometry_kernel_candidates.csv)
- [Package audit](../results/geometry_kernel_package_audit.csv)
- [Round-trip probe](../results/geometry_kernel_probe.csv)
- [Summary](../results/geometry_kernel_selection_summary.csv)
- [Decision record](../results/geometry_kernel_decision.json)
- [Figure](../results/geometry_kernel_selection.png)
- [Generated STEP fixture](../fixtures/geometry-kernel-selection/ocp_box.step)
- [Sample catalog](step-sample-catalog.md)

```bash
python -m pip install -e ".[geometry]"
python experiments/run_geometry_kernel_selection.py
```

### v0.32.0 — Evaluated Face Geometry and Tolerances

**Question:** Can the selected optional geometry backend evaluate bounded
planar and cylindrical B-Rep faces against closed-form truth, and which
orientation and tolerance claims survive a STEP round trip?

**Representative finding:** Two planes and one cylindrical patch match
independent analytic area, centroid, UV bounds, representative point, normal,
surface-frame, and radius truth within the fixed regression contract before
and after STEP exchange. The reversed plane retains its orientation. The
constructed face tolerances `1e-4`, `2e-4`, and `3e-4` are all observed as
`1e-7` after import, so tolerance is reported as stage-specific state rather
than assumed round-trip identity.

- [Complete note](../notes/evaluated-face-geometry-tolerances.md)
- [Face observations](../results/evaluated_face_geometry_observations.csv)
- [Summary](../results/evaluated_face_geometry_summary.csv)
- [Evaluation contract](../results/evaluated_face_geometry.json)
- [Figure](../results/evaluated_face_geometry.png)
- [Generated STEP fixture](../fixtures/evaluated-face-geometry/analytic_faces.step)
- [Sample catalog](step-sample-catalog.md)

```bash
python -m pip install -e ".[geometry]"
python experiments/run_evaluated_face_geometry.py
```

### v0.33.0 — Curves, Edge Parameters, P-Curves, and Seams

**Question:** Can the selected geometry backend recover controlled edge
curves, parameter ranges, p-curves, oriented boundary traversal, and a
cylindrical seam after STEP exchange while keeping flags and measured
consistency separate?

**Representative finding:** Each stage contains 11 unique edges and 12 ordered
wire occurrences. All line and circle classifications, analytic lengths,
parameter spans, and controlled UV paths match. The full cylinder uses one
axial seam edge twice, with p-curve branches at `u=0` and `u=2π`. The maximum
STEP-imported 3D-curve-to-p-curve distance is `1.24e-12` over 17 samples per
p-curve; this is a fixture regression result, not a universal tolerance.

- [Complete note](../notes/curves-edge-parameters-pcurves-seams.md)
- [Unique-edge observations](../results/edge_curve_observations.csv)
- [P-curve observations](../results/pcurve_observations.csv)
- [Summary](../results/edge_curve_summary.csv)
- [Evaluation contract](../results/edge_curve_contract.json)
- [Figure](../results/edge_curve_evaluation.png)
- [Generated STEP fixture](../fixtures/edge-curve-evaluation/analytic_edge_faces.step)
- [Sample catalog](step-sample-catalog.md)

```bash
python -m pip install -e ".[geometry]"
python experiments/run_edge_curve_evaluation.py
```

### v0.34.0 — Wires, Trimming, and Face Orientation

**Question:** Can the selected geometry backend recover ordered outer and
inner wires, trimmed material regions, orientation-aware winding, periodic
seams, and degenerate singular boundaries after STEP exchange?

**Representative finding:** The planar frame's signed outer and inner UV
areas change from `+48 / -6` to `-48 / +6` under face reversal while material
area remains `42` and point classification remains unchanged. The sphere uses
one seam edge twice plus two degenerate pole edges without 3D curves to close
its UV boundary. All six wires and all sixteen classification samples retain
their expected states after STEP import. The sphere's constructed
`NaturalRestriction` flag is not retained, so it remains stage-specific kernel
state rather than a portable STEP claim.

- [Complete note](../notes/wires-trimming-face-orientation.md)
- [Face observations](../results/wire_trimming_face_observations.csv)
- [Wire observations](../results/wire_trimming_wire_observations.csv)
- [Ordered edge uses](../results/wire_trimming_edge_uses.csv)
- [Point classifications](../results/wire_trimming_classifications.csv)
- [Summary](../results/wire_trimming_summary.csv)
- [Evaluation contract](../results/wire_trimming_contract.json)
- [Figure](../results/wire_trimming_evaluation.png)
- [Shape preview](../results/wire_trimming_shapes.png)
- [Generated STEP fixture](../fixtures/wire-trimming-evaluation/analytic_trimmed_faces.step)
- [Sample catalog](step-sample-catalog.md)

```bash
python -m pip install -e ".[geometry]"
python experiments/run_wire_trimming_evaluation.py
```

### v0.35.0 — Shell and Solid Validity

**Question:** Can shell and solid validity be decomposed into reproducible
incidence, connectivity, orientation, Euler, volume, and backend claims before
and after STEP exchange?

**Representative finding:** All fourteen stage observations retain their
controlled V/E/F, face-component, edge-incidence, closure, orientability, and
Euler values. Generic backend validity nevertheless returns true for the open
box, one-face-flipped box, and nonmanifold fan. STEP import changes the whole
reversed box from signed volume `-120` to `+120`, reorients the flipped face,
splits the nonmanifold fan from one shell into three, and splits two
disconnected faces from one shell container into two. The valid one-face torus
demonstrates a closed solid with Euler characteristic `0` and imported volume
error `6.37e-12` against `18π²`.

- [Complete note](../notes/shell-solid-validity.md)
- [Whole-shape observations](../results/shell_solid_observations.csv)
- [Edge incidence](../results/shell_solid_edge_incidence.csv)
- [Connected components](../results/shell_solid_components.csv)
- [Per-shell backend reports](../results/shell_validity_observations.csv)
- [Summary](../results/shell_solid_summary.csv)
- [Evaluation contract](../results/shell_solid_contract.json)
- [Figure](../results/shell_solid_validity.png)
- [Shape preview](../results/shell_solid_shapes.png)
- [Generated STEP fixtures](../fixtures/shell-solid-validity/)
- [Sample catalog](step-sample-catalog.md)

```bash
python -m pip install -e ".[geometry]"
python experiments/run_shell_solid_validity.py
```

### v0.36.0 — Tolerances, Sewing, and Healing Effects

**Question:** When do controlled face gaps become topologically sewn, which
local tolerances change, and can a bounded repair be accepted without erasing
geometry, validity, and provenance boundaries?

**Representative finding:** The `5e-7` gap closes at requests `1e-6` and
`1e-4`, while the `5e-5` gap closes only at `1e-4`. All seventeen stage
observations retain the six controlled planar areas, centroids, and support-
plane equations, but stored edge tolerances rise with merged residuals. One
reversed face is repaired from
one required flip to zero and signed volume `80` to `120`; deliberately capping
the large-gap result to `1e-5` keeps V/E/F and closure while making the native
shape invalid.

- [Complete note](../notes/tolerance-sewing-healing.md)
- [Stage observations](../results/tolerance_sewing_observations.csv)
- [Analysis-local tolerances](../results/tolerance_sewing_subshape_tolerances.csv)
- [Operation log](../results/tolerance_sewing_operations.csv)
- [Summary](../results/tolerance_sewing_summary.csv)
- [Evaluation contract](../results/tolerance_sewing_contract.json)
- [Figure](../results/tolerance_sewing_healing.png)
- [Shape preview](../results/tolerance_sewing_shapes.png)
- [Generated STEP fixtures](../fixtures/tolerance-sewing-healing/)
- [Sample catalog](step-sample-catalog.md)

```bash
python -m pip install -e ".[geometry]"
python experiments/run_tolerance_sewing_healing.py
```

### v0.37.0 — Manifoldness and Self-Intersection

**Question:** Which explicit checks distinguish edge-manifold incidence,
manifold vertex neighborhoods, lower-dimensional contact, volumetric overlap,
and geometric self-intersection?

**Representative finding:** The pinched-tetrahedra control has two face uses
on every edge but two disconnected link components at its shared vertex, so
edge incidence alone misses the nonmanifold neighborhood. In one aggregate
B-Rep, the single-argument checker distinguishes separated edges from one
interior edge/edge point and separated faces from one transverse face/face
curve of length `2`. Separate box pairs retain a unit gap, point contact,
edge-contact length `4`, face-contact area `16`, and overlap volume `9` across
STEP exchange. These bounded polyhedral results do not establish a general
curved-shape self-intersection proof.

All 24 whole-shape observations, 14 pair-relation observations, and eight
single-argument `BOPAlgo_CheckerSI` observations match their controls at both stages. The
maximum recorded pair-measure and self-intersection-quantity errors are zero in
the pinned reference environment.

- [Complete note](../notes/manifoldness-self-intersection.md)
- [Whole-shape observations](../results/manifold_intersection_observations.csv)
- [Vertex-link observations](../results/vertex_link_observations.csv)
- [Shape-pair relations](../results/shape_pair_relations.csv)
- [Single-argument self-interference observations](../results/self_intersection_observations.csv)
- [Summary](../results/manifold_intersection_summary.csv)
- [Evaluation contract](../results/manifold_intersection_contract.json)
- [Figure](../results/manifold_self_intersection.png)
- [Shape preview](../results/manifold_self_intersection_shapes.png)
- [Generated STEP fixtures](../fixtures/manifold-self-intersection/)
- [Sample catalog](step-sample-catalog.md)

```bash
python -m pip install -e ".[geometry]"
python experiments/run_manifold_self_intersection.py
```

### v0.38.0 — Voids, Inner Shells, and Composite Solids

**Question:** How can outer shells, void shells, material islands, compounds,
and composite solids be evaluated as explicit material-region claims rather
than inferred from one container type or volume number?

**Representative finding:** A valid centered void and an invalid outside
reversed shell both have constructed volume `464`; only containment separates
them. The overlapping-void control retains two depth-one, correctly oriented
voids, but raw volume `522` differs from analytic material volume `531` and the
partial-overlap gate fails. The face-connected composite solid changes from
`V=12,E=20,F=11`, one shared face, and one component to
`V=16,E=24,F=12`, no shared face, and two components after STEP import.

All ten constructed material-candidate, shared-face, and component expectations
match. The committed evidence contains 20 main observations, 44 shell-role
rows, 60 containment relations, and nine solid-adjacency rows.

- [Complete note](../notes/voids-inner-shells-composite-solids.md)
- [Main observations](../results/solid_region_observations.csv)
- [Shell roles](../results/shell_role_observations.csv)
- [Containment relations](../results/shell_containment_relations.csv)
- [Solid adjacency](../results/solid_adjacency_observations.csv)
- [Summary](../results/solid_region_summary.csv)
- [Evaluation contract](../results/solid_region_contract.json)
- [Figure](../results/solid_regions.png)
- [Shape preview](../results/solid_region_shapes.png)
- [Generated STEP fixtures](../fixtures/solid-regions/)
- [Sample catalog](step-sample-catalog.md)

```bash
python -m pip install -e ".[geometry]"
python experiments/run_solid_region_evaluation.py
```

### v0.39.0 — Face and Edge Correspondence Across STEP Import and Healing

**Question:** Can face and edge relationships across STEP import and one
topology-changing healing operation be reported as one-to-one, modified,
many-to-one, deleted, ambiguous, or unmatched without treating analysis-local
order as identity?

**Representative finding:** Geometry evidence resolves 23 faces and 47 edges
across STEP import, while two coincident faces and eight duplicate edges retain
tied candidates and abstain. Same-domain healing changes the split box from 10
faces and 20 edges to 6 faces and 12 edges. Edge relations comprise eight
one-to-one modified sources, eight sources in four two-to-one groups, and four
deleted seams. All 35 face and 75 edge relations match construction truth; all
10 face and 20 edge healing relations agree with separately recorded operation
history.

The evidence contains 56 face descriptors, 37 face candidates, 35 face
relations, 122 edge descriptors, 79 edge candidates, 75 edge relations, four
hashed STEP fixtures, one versioned JSON contract, and two figures. Incident-
face candidates corroborate edge geometry without breaking ties. Operation
history and 75 direct identity checks are separate; `IsSame` and `IsPartner`
are both absent. This planar, straight-edge corpus is not persistent naming,
STEP-carried operation history, or recovered design intent.

- [Complete note](../notes/face-correspondence-step-import-healing.md)
- [Face descriptors](../results/shape_correspondence_faces.csv)
- [Candidate evidence](../results/shape_correspondence_candidates.csv)
- [Resolved and abstained relations](../results/shape_correspondence_relations.csv)
- [Edge descriptors](../results/shape_correspondence_edges.csv)
- [Edge candidate evidence](../results/shape_correspondence_edge_candidates.csv)
- [Edge relations and history](../results/shape_correspondence_edge_relations.csv)
- [Summary](../results/shape_correspondence_summary.csv)
- [Evaluation contract](../results/shape_correspondence_contract.json)
- [Figure](../results/shape_correspondence.png)
- [Shape preview](../results/shape_correspondence_shapes.png)
- [Generated STEP fixtures](../fixtures/shape-correspondence/)
- [Sample catalog](step-sample-catalog.md)

```bash
python -m pip install -e ".[geometry]"
python experiments/run_shape_correspondence.py
```

### v0.40.0 — Rule-Based B-Rep Feature Recognition

**Question:** Can bounded hole, step, slot, chamfer-like, and fillet-like
geometric candidates be recognized from evaluated face attributes and
adjacency while keeping construction history and design intent outside the
claim?

**Representative finding:** Nine controls produce seven candidates before and
seven after STEP import. All 14 candidates match controlled classification and
dimension truth. The maximum controlled-truth errors are
`3.9612757518625585e-13` model units for length and
`5.8832938520936295e-12°` for angle; the plain block and external cylindrical
boss produce no false positives.

An operation-made chamfer and a direct-profile bevel have equivalent checked
boundaries at both stages: `V=10`, `E=15`, `F=7`, one shell, one solid, volume
`572`, and zero Boolean difference volume in both directions. They retain
different construction labels, so all 14 candidates report design intent as
unproven. The evidence contains 136 face rows, 282 adjacency rows, 14 candidate
rows, 18 control/stage observations, and two equivalent-boundary rows. This is
a controlled geometric-candidate study, not feature-history reconstruction or
a general B-Rep recognizer.

- [Complete note](../notes/rule-based-brep-feature-recognition.md)
- [Reader-facing result digest](feature-recognition-results.md)
- [Complete Japanese-language companion](feature-recognition-results-ja.txt)
- [Face attributes](../results/feature_face_attributes.csv)
- [Adjacency evidence](../results/feature_adjacency_edges.csv)
- [Feature candidates](../results/feature_candidates.csv)
- [Control-stage observations](../results/feature_recognition_observations.csv)
- [Equivalent-boundary observations](../results/feature_equivalent_boundary_observations.csv)
- [Summary](../results/feature_recognition_summary.csv)
- [Evaluation contract](../results/feature_recognition_contract.json)
- [Figure](../results/feature_recognition.png)
- [Shape preview](../results/feature_recognition_shapes.png)
- [Generated STEP fixtures](../fixtures/feature-recognition/)
- [Sample catalog](step-sample-catalog.md)

```bash
python -m pip install -e ".[geometry]"
python experiments/run_feature_recognition.py
```

### v0.41.0 — Face-Level Analysis Reports

**Question:** Can one stable face-row contract integrate local parent
ownership, evaluated geometry, type-specific parameters, boundary topology,
adjacency, tolerance, and metadata provenance without claiming persistent
identity or inferring unavailable STEP attributes?

**Representative finding:** Five generated controls produce 13 constructed and
13 STEP-imported face rows. Both stages contain eight planes and one cylinder,
cone, sphere, torus, and B-spline face. All 13 geometry-matched pairs retain
orientation, outer/inner wire counts, and unique boundary-edge counts. The
maximum area difference is `1.0317080523236655e-11` squared model units and the
maximum centroid distance is `2.9535772102134982e-13` model units.

The 60-field CSV contract includes analysis-local face indices, parent solid
and shell lists, surface family and raw kernel type, orientation, area,
centroid, UV bounds, representative normal, analytic or B-spline parameters,
wire and edge counts, tolerance, adjacency, and source-attributed name/color
fields. The cone semi-angle changes sign with an equivalent imported axis
parameterization, and the raised B-spline tolerance changes from `2.0e-4` to
`1.0e-7`. Constructed rows contain manifest-sourced name/color values;
imported rows contain no inferred metadata on the shape-only reader route.

- [Complete note](../notes/face-level-analysis-reports.md)
- [Stable face report](../results/face_analysis_report.csv)
- [Round-trip matches](../results/face_analysis_round_trip_matches.csv)
- [Summary](../results/face_analysis_summary.csv)
- [CSV contract](../results/face_analysis_contract.json)
- [Figure](../results/face_analysis.png)
- [Shape preview](../results/face_analysis_shapes.png)
- [Generated STEP fixtures](../fixtures/face-analysis/)
- [Sample catalog](step-sample-catalog.md)

```bash
python -m pip install -e ".[geometry]"
python experiments/run_face_level_analysis.py
```

### v0.42.0 — Tessellation and Visual Diagnostic Contracts

**Question:** Can every controlled display triangle be traced to its imported
face and source Part 21 entity while requested meshing inputs, sampled
diagnostics, exact B-Rep measurements, and previews remain separate claims?

**Representative finding:** Three generated STEP controls are meshed under a
two-by-two absolute linear/angular design. The resulting 36 face-condition
rows and 3,782 triangle rows retain direct source provenance for all nine
imported faces. Through-hole counts are `88 / 220 / 88 / 220`, sphere counts
are `168 / 1260 / 422 / 1260`, and B-spline counts are `10 / 10 / 18 / 18`
for coarse-both, fine-angular, fine-linear, and fine-both respectively.

Angular refinement reduces the through-hole relative area difference from
`8.6769e-5` to `1.0612e-5`; both selected refinements reduce the sphere result
from `0.0412249` to `0.00595059`; and linear refinement reduces the B-spline
result from `0.00742346` to `0.00370206`. Eight zero-area sphere-pole triangles
remain explicit with blank normals. Requested deflections and one
UV-barycentric sample per triangle are not certified maximum-error bounds.

- [Complete note](../notes/tessellation-visual-diagnostic-contracts.md)
- [Triangle observations](../results/tessellation_triangles.csv)
- [Face observations](../results/tessellation_face_summary.csv)
- [Summary](../results/tessellation_summary.csv)
- [Evaluation contract](../results/tessellation_contract.json)
- [Diagnostic figure](../results/tessellation_diagnostics.png)
- [Face-colored previews](../results/tessellation_visual_diagnostics.png)
- [Generated STEP fixtures](../fixtures/tessellation-diagnostics/)
- [Sample catalog](step-sample-catalog.md)

```bash
python -m pip install -e ".[geometry]"
python experiments/run_tessellation_diagnostics.py
```

### v0.43.0 — Primitive Construction and STEP Round Trips

**Question.** Which parameter, topology, geometry, tolerance, and exchange
properties survive one controlled primitive STEP round trip?

**Result.** Six shapes produce twelve analyzer-valid stage observations. Every
pair retains topology and support-surface inventories, and five analytic solids
match independent volume and area truth within `2e-8`. Four strict literal
contracts pass. The cone retains geometry while its equivalent semi-angle
changes sign, and B-spline tolerance normalization moves inflated bounds by
`0.0001999` model units.

- [Complete note](../notes/primitive-construction-step-round-trips.md)
- [Stage observations](../results/primitive_round_trip_observations.csv)
- [Round-trip summary](../results/primitive_round_trip_summary.csv)
- [Evaluation contract](../results/primitive_round_trip_contract.json)
- [Residual figure](../results/primitive_round_trip.png)
- [Imported shape previews](../results/primitive_round_trip_shapes.png)
- [Generated STEP fixtures](../fixtures/primitive-round-trips/)

```bash
python -m pip install -e ".[geometry]"
python experiments/run_primitive_round_trips.py
```

### v0.44.0 — Profiles, Extrusion, and Revolution

**Question.** Can explicit profile loops and operation parameters drive
reproducible extrusion, revolution, recompute, and STEP exchange?

**Result.** Five constructed/imported pairs remain analyzer-valid, match
analytic volume and area within `1e-8`, and retain topology and support-surface
inventories. Height `5 -> 7` produces volume ratio `1.4`, and revolution angle
`360° -> 180°` produces ratio `0.5` at both stages. The annular profile retains
one oppositely oriented inner wire as explicit hole truth.

- [Complete note](../notes/profiles-extrusion-revolution.md)
- [Stage observations](../results/profile_modeling_observations.csv)
- [Round-trip summary](../results/profile_modeling_summary.csv)
- [Recompute relations](../results/profile_recompute_relations.csv)
- [Evaluation contract](../results/profile_modeling_contract.json)
- [Evaluation figure](../results/profile_modeling.png)
- [Shape previews](../results/profile_modeling_shapes.png)
- [Generated STEP fixtures](../fixtures/profile-modeling/)

```bash
python -m pip install -e ".[geometry]"
python experiments/run_profile_modeling.py
```

### v0.45.0 — Sweeps, Lofts, and Surface Construction

**Question.** Which bounded sweep, loft, and point-grid surface claims remain
reproducible when preconditions, native outcomes, evaluated geometry, and STEP
exchange are recorded separately?

**Result.** Five accepted controls produce ten analyzer-valid observations and
all five constructed/imported pairs retain topology, surface inventories, and
measurements. Six analytic stage observations match independent volume and
area truth within `1e-8`. A C0 corner spine and one-section loft are rejected
before kernel invocation. The smooth square loft reaches approximately `1.5`
times the largest input half-span despite remaining valid.

- [Complete note](../notes/sweeps-lofts-surface-construction.md)
- [Admission decisions](../results/sweep_loft_decisions.csv)
- [Stage observations](../results/sweep_loft_observations.csv)
- [Round-trip summary](../results/sweep_loft_summary.csv)
- [Evaluation contract](../results/sweep_loft_contract.json)
- [Evaluation figure](../results/sweep_loft_modeling.png)
- [Shape previews](../results/sweep_loft_shapes.png)
- [Generated STEP fixtures](../fixtures/sweep-loft-modeling/)

```bash
python -m pip install -e ".[geometry]"
python experiments/run_sweep_loft_modeling.py
```

### v0.46.0 — Boolean Operations and Robustness

**Question.** How do operation type, spatial relationship, and an additional
fuzzy tolerance change Boolean validity, topology, exact-set measures, and
STEP round-trip behavior?

**Result.** Seven controls produce 14 analyzer-valid observations. The 12
default stage observations match independent cuboid-set volume and area truth,
and six literal STEP contracts pass. A fuzzy value of `0.0001` bridges a
`0.00005` gap, changes two solids into one, differs from exact union volume by
about `0.0001333333`, and accumulates further measure drift after STEP import.

- [Complete note](../notes/boolean-operations-robustness.md)
- [Operation decisions](../results/boolean_operation_decisions.csv)
- [Stage observations](../results/boolean_operation_observations.csv)
- [Round-trip summary](../results/boolean_operation_summary.csv)
- [Tolerance relation](../results/boolean_tolerance_relations.csv)
- [Evaluation contract](../results/boolean_operation_contract.json)
- [Evaluation figure](../results/boolean_operation_robustness.png)
- [Shape previews](../results/boolean_operation_shapes.png)
- [Generated STEP fixtures](../fixtures/boolean-robustness/)

```bash
python -m pip install -e ".[geometry]"
python experiments/run_boolean_robustness.py
```

### v0.47.0 — Fillets, Chamfers, and Topology History

**Question.** What can operation-local generated, modified, and deleted queries
say about a controlled fillet and chamfer, and which relationships survive
STEP exchange?

**Result.** The unit fillet and chamfer match analytic volume and area before
and after STEP; radius and distance 20 do not complete. Each successful
operation records 26 source-scoped history rows, including one source with a
generated result and four with modified results. Fourteen STEP face matches
retain equal index values, but direct identity and imported operation history
are zero.

- [Complete note](../notes/fillets-chamfers-topology-history.md)
- [Operation decisions](../results/feature_operation_decisions.csv)
- [Stage observations](../results/feature_operation_observations.csv)
- [Topology history](../results/topology_history.csv)
- [STEP face matches](../results/feature_face_round_trip_matches.csv)
- [Summary](../results/feature_operation_summary.csv)
- [Evaluation contract](../results/feature_operation_contract.json)
- [History figure](../results/topology_history.png)
- [Shape previews](../results/feature_operation_shapes.png)
- [Generated STEP fixtures](../fixtures/topology-history/)

```bash
python -m pip install -e ".[geometry]"
python experiments/run_topology_history.py
```

### v0.48.0 — STEP Round-Trip Preservation

**Question.** Which structural, semantic, geometric, topological, attribute,
tolerance, and physical-file dimensions survive a controlled XCAF-aware
import-export-import cycle?

**Result.** All three controls retain the six semantic and B-Rep preservation
dimensions between imported generations, while only one pair is byte
identical. The through-hole source omits its declared color before the first
import, demonstrating that stable later generations do not prove agreement
with source attribute truth.

- [Complete note](../notes/step-round-trip-preservation.md)
- [Stage observations](../results/step_preservation_observations.csv)
- [Dimension comparisons](../results/step_preservation_comparisons.csv)
- [Summary](../results/step_preservation_summary.csv)
- [Evaluation contract](../results/step_preservation_contract.json)
- [Preservation figure](../results/step_round_trip_preservation.png)
- [Shape previews](../results/step_round_trip_preservation_shapes.png)
- [Generated STEP fixtures](../fixtures/step-round-trip-preservation/)

```bash
python -m pip install -e ".[geometry]"
python experiments/run_step_round_trip_preservation.py
```

### v0.49.0 — Independent Parser and Kernel Portability

**Question.** Which observations remain stable across independently
implemented Part 21 parsers and distinct import APIs, and which claims require
a genuinely independent geometry kernel?

**Result.** All three parsers accept all three fixed files. The shape-only and
XCAF routes agree on topology, volume, area, and support surfaces for all three
controls. XCAF exposes three name inventories and two color inventories. Both
routes share one OCCT build, so cross-kernel portability remains false.

- [Complete note](../notes/independent-parser-kernel-portability.md)
- [Parser observations](../results/step_parser_portability.csv)
- [Importer observations](../results/step_importer_portability.csv)
- [Summary](../results/step_portability_summary.csv)
- [Fixed-corpus manifest](../results/step_portability_manifest.csv)
- [Evaluation contract](../results/step_portability_contract.json)
- [Evaluation figure](../results/step_portability.png)

```bash
python -m pip install -e ".[comparison,geometry]"
python experiments/run_step_portability.py
```

## Artifact Details

The [`results` catalog](../results/README.md) documents every committed CSV and
PNG file. Fixed JPEG streams, reference decodes, synthetic STEP exchange
structures, and their manifests are under [`fixtures/`](../fixtures/).

## Claim Boundaries

The studies use controlled synthetic inputs so that changed variables and
expected relationships remain inspectable. This design supports regression and
failure-mode analysis, but it does not establish:

- a universal blur threshold or perceptual quality score;
- transfer to arbitrary natural images, cameras, or processing pipelines;
- codec-family behavior beyond the fixed fixtures and pinned builds;
- color accuracy for measured devices, LUT profiles, gamut mapping, or human
  judgments;
- bounded file acquisition, decoded-pixel allocation, process memory, or
  execution time beyond the declared metadata admission counters;
- security, memory safety, denial-of-service resistance, or safe handling of
  arbitrary malformed files;
- full Part 21 edition coverage, complete EXPRESS parsing or validation,
  external reference safety, CMS
  verification, archive safety, or exact geometry evaluation beyond the
  controlled v0.21.0 through v0.49.0 subsets;
- persistent face or edge identity, topological naming, or design-history
  recovery from the v0.39.0 geometry-inferred correspondence controls;
- feature-history or design-intent recovery, or general feature recognition,
  from the v0.40.0 rule-based geometric candidates.
- persistent identity, arbitrary-file coverage, or STEP/XCAF metadata recovery
  from the v0.41.0 controlled face-report rows.
- certified tessellation error bounds, global mesh validity, persistent source
  identity, or exact geometry from the v0.42.0 diagnostic mesh and previews.
- recovered construction history, literal analytic-parameter identity, exact
  tolerance-invariant bounds, or cross-kernel portability from the v0.43.0
  primitive round trips.
- general sketch validity, constraint solving, open-profile operations, taper,
  draft, or recovered feature commands from the v0.44.0 profile controls.
- arbitrary guide curves, loft compatibility, fairness, certified fitting
  bounds, or recovered history from the v0.45.0 construction controls.
- arbitrary curved or invalid Boolean operands, a universal fuzzy tolerance,
  or exact-set equivalence from the v0.46.0 cuboid controls.
- general local-feature history, positive split or merge coverage, persistent
  naming, or history preservation from the v0.47.0 box-edge controls.
- nested-assembly preservation, complete attribute association, pointwise
  geometry equivalence, or cross-kernel portability from the v0.48.0 controls.
- schema validity, semantic equivalence, or cross-kernel portability from the
  v0.49.0 parser and same-kernel import-route agreements.

The complete notes contain the narrower limitations for each experiment.
