# Reference Results

## 日本語概要

このディレクトリには、37件の研究を固定した合成画像・合成STEP・合成EXPRESSと版管理された実験スクリプトから生成した参照成果物があります。画像・JPEG・メタデータ・STEP・EXPRESS・AP242の観測に加え、面・辺・輪郭線・外殻・立体、許容差付き縫合、辺使用回数、頂点リンク、接触次元、重複、横断交差を、CSV・JSON・比較図・ハッシュ付き試験データとして研究版ごとに対応付けています。

各成果物の内容と再生成元は以下の英語本文を参照してください。

---

This directory contains committed outputs generated exclusively from synthetic
images and STEP exchange structures by the versioned experiment scripts.

## v0.1.0

- `laplacian_variance_summary.csv` contains one row for each pattern, blur
  sigma, and noise standard deviation.
- `laplacian_variance.png` visualizes the aggregate blur response and the noise
  response for strongly blurred inputs.

## v0.2.0

- `focus_metric_trials.csv` contains 720 repeated observations.
- `focus_metric_summary.csv` contains condition-level means, sample standard
  deviations, and p10, median, and p90 values for both focus measures.
- `motion_blur_summary.csv` contains the bounded horizontal-motion sensitivity
  experiment.
- `resize_sensitivity_summary.csv` contains the downscale-upscale sensitivity
  experiment.
- `focus_metric_comparison.png` compares normalized responses across the four
  evaluations.

## v0.3.0

- `local_blur_observations.csv` contains 132 full-image and tile-aggregation
  observations.
- `local_blur_tiles.csv` contains all 2,112 tile-level metric observations and
  their matched-control ratios.
- `local_blur_aggregate.csv` averages normalized results across patterns and
  applicable placements.
- `local_blur_example.png` shows a synthetic partial-blur sample and its two
  normalized tile maps.
- `local_blur_spatial_aggregation.png` compares full-image, mean, lower-tail,
  and minimum aggregation behavior.

## v0.4.0

- `window_geometry_windows.csv` contains 8,073 window-level geometry, score,
  and matched-control observations.
- `window_geometry_summary.csv` contains 216 clean condition summaries with
  coverage, response ratios, and ranking AP.
- `window_noise_trials.csv` contains 360 deterministic repeated-noise
  observations.
- `window_noise_summary.csv` contains 12 noise-condition summaries.
- `low_texture_confounds.csv` records the sharp flat-patch counterexample for
  both metrics.
- `window_geometry_example.png` visualizes coverage and score maps for an
  off-grid blur region.
- `window_geometry_robustness.png` summarizes geometry, ranking, noise, and
  low-texture controls.

## v0.5.0

- `preprocessing_trials.csv` contains 9,360 blur, noise, pipeline, and metric
  observations.
- `preprocessing_response_summary.csv` contains 312 score-scale summaries.
- `preprocessing_calibration_anchors.csv` records the six clean identity
  anchors and their per-pattern midpoint rules.
- `preprocessing_calibration_summary.csv` contains 78 fixed-calibration and
  blur-order summaries.
- `preprocessing_examples.png` shows synthetic inputs after selected pipeline
  operations.
- `preprocessing_calibration_drift.png` compares score response and calibration
  transfer for both metrics.

## v0.6.0

- `optical_blur_kernels.csv` audits all 17 identity, disk-defocus, and
  linear-motion PSFs.
- `optical_blur_trials.csv` contains 5,100 paired-noise metric observations.
- `optical_blur_summary.csv` contains 510 pattern-condition summaries.
- `motion_direction_summary.csv` contains 72 aligned, oblique, and
  perpendicular motion comparisons.
- `optical_blur_examples.png` shows controlled grating responses to disk and
  directional blur.
- `optical_blur_directional_sensitivity.png` summarizes motion direction,
  defocus radius, and noise sensitivity.

## v0.7.0

- `photometric_recompression_trials.csv` contains 11,520 paired metric
  observations across photometric, recompression, blur, and noise controls.
- `photometric_recompression_response_summary.csv` contains 384 score-scale
  and clipped-endpoint summaries.
- `photometric_recompression_calibration_anchors.csv` records the six clean
  identity midpoint anchors.
- `photometric_recompression_calibration_summary.csv` contains 96 fixed-rule
  transfer and blur-order summaries.
- `photometric_recompression_examples.png` shows BGR, grayscale, tone-mapped,
  normalized, and recompressed synthetic examples.
- `photometric_recompression_drift.png` compares photometric scale,
  recompression trajectories, and fixed-calibration transfer.

## v0.8.0

- `jpeg_history_trials.csv` contains 4,320 paired observations across nine
  two-stage JPEG histories, two block-grid alignments, blur, and noise controls.
- `jpeg_history_response_summary.csv` contains 288 matched primary-only and
  uncompressed response summaries.
- `jpeg_history_calibration_anchors.csv` records 12 uncompressed same-crop
  midpoint anchors.
- `jpeg_history_calibration_summary.csv` contains 72 fixed-rule transfer and
  blur-order summaries.
- `jpeg_history_examples.png` shows aligned, shifted, 4:4:4, and 4:2:0 synthetic
  decoded controls.
- `jpeg_history_sensitivity.png` compares quality order, block-grid alignment,
  chroma sampling, and calibration transfer.

## v0.9.0

- `jpeg_codec_manifest.csv` records the two wrapper and reported JPEG backend
  versions under comparison.
- `jpeg_quality_table_sweep.csv` audits DQT mappings and exact byte agreement
  for numeric qualities 1 through 100.
- `jpeg_quantization_tables.csv` expands the quality-50, 75, and 95 luma and
  chroma tables into 384 coefficient rows.
- `jpeg_codec_trials.csv` contains 1,152 decoded metric observations across
  four encoder paths and two decoders.
- `jpeg_encoder_agreement.csv` contains 216 byte, table, component, pixel, size,
  and metric comparisons against the OpenCV default path.
- `jpeg_decoder_agreement.csv` contains 288 cross-decoder pixel comparisons.
- `jpeg_codec_portability_summary.csv` contains 72 encoder-path summaries.
- `jpeg_quantization_tables.png` visualizes the selected DQT tables and numeric-
  quality scaling.
- `jpeg_codec_portability.png` separates DQT, byte, decoded-pixel, size, and
  derivative-response behavior.

## v0.10.0

- `fixtures/jpeg-decoder-contracts/manifest.csv` records the source, JPEG,
  reference-pixel, DQT, and component-sampling identities for 12 generated
  baseline JPEG streams and their lossless BGR decode references.
- `jpeg_platform_codec_manifest.csv` records the local reference wrappers,
  JPEG backends, platform, architecture, Python version, and SIMD policy.
- `jpeg_decoded_pixel_observations.csv` contains 24 local decoder observations
  with separate structure, shape, dtype, exact-pixel, and within-one contracts.
- `jpeg_decoder_pair_observations.csv` contains 12 direct local
  OpenCV-versus-Pillow decoded-pixel comparisons.
- `jpeg_decoded_pixel_summary.csv` summarizes the local observations by
  decoder, numeric quality control, and chroma sampling.
- `jpeg_decoded_pixel_contracts.png` visualizes local exact-reference rates and
  maximum code-value errors.
- `jpeg_cross_platform_codec_manifest.csv` records the ten wrapper/backend rows
  from the five-profile release matrix.
- `jpeg_cross_platform_observations.csv` combines 120 decoder observations from
  Ubuntu x64 default and forced-scalar, Windows x64, macOS arm64, and macOS
  Intel x64 profiles.
- `jpeg_cross_platform_decoder_pairs.csv` combines 60 within-profile
  OpenCV-versus-Pillow comparisons.
- `jpeg_cross_platform_contract_summary.csv` reports hash multiplicity and
  exact and bounded contracts for each fixture and decoder.
- `jpeg_cross_platform_contracts.png` visualizes exact, bounded, maximum-error,
  and decoded-hash behavior across the release matrix.

The committed cross-platform snapshot comes from the successful v0.10.0
release matrix rather than a simulated local platform label. The aggregation
job verifies the three stable decoded-pixel reports against the committed
references on every CI run. Runner image identifiers remain observational
metadata because hosted images can be updated independently of this project.

## v0.11.0

- `fixtures/advanced-jpeg-syntax/manifest.csv` records ten generated baseline,
  progressive, restart-marker, grayscale, RGB, and CMYK JPEG streams and their
  lossless BGR reference decodes.
- `jpeg_advanced_codec_manifest.csv` records the local OpenCV, Pillow, and
  FFmpeg adapter, codec-family, platform, and build provenance.
- `jpeg_advanced_decoder_observations.csv` contains 30 local structure,
  interface, exact-pixel, numerical-error, and derivative-response records.
- `jpeg_advanced_pairwise_differences.csv` contains all 30 local decoder-family
  pairs across the ten fixtures.
- `jpeg_advanced_syntax_equivalence.csv` contains 15 matched progression and
  restart-marker comparisons within the three decoders.
- `jpeg_advanced_summary.csv` provides one local row for every fixture and
  decoder.
- `jpeg_advanced_codec_families.png` visualizes maximum error, changed-sample
  fraction, and derivative-metric ratios.
- `jpeg_advanced_cross_platform_codec_manifest.csv` records the 15 decoder
  build rows from the five-profile release matrix.
- `jpeg_advanced_cross_platform_observations.csv`,
  `jpeg_advanced_cross_platform_pairs.csv`, and
  `jpeg_advanced_cross_platform_syntax_equivalence.csv` preserve the combined
  release observations.
- `jpeg_advanced_cross_platform_summary.csv` and
  `jpeg_advanced_cross_platform_pair_summary.csv` aggregate those observations
  by fixed fixture and decoder or decoder pair.
- `jpeg_advanced_cross_platform_codec_families.png` visualizes exact, bounded,
  maximum-error, and cross-platform hash behavior.

The committed v0.11.0 cross-platform snapshot comes from the successful
five-profile release workflow. CI compares the combined observations, decoder
pairs, controlled syntax comparisons, and both summaries against these
references. The codec manifest is retained as release provenance but is not
byte-compared on future runs because hosted runner image metadata can change
independently of the fixed decoder outputs.

## v0.12.0

- `fixtures/color-metadata-contracts/manifest.csv` records 13 fixed ICC, EXIF
  orientation, CMYK, and YCCK JPEG streams, their metadata-stripped core
  identities, and lossless raw BGR reference decodes.
- `jpeg_metadata_codec_manifest.csv` records the local OpenCV, Pillow, FFmpeg,
  and LittleCMS adapter and implementation provenance.
- `jpeg_metadata_raw_observations.csv` contains 39 local raw decode records
  with ICC conversion and orientation normalization explicitly disabled.
- `jpeg_metadata_policy_observations.csv` contains 44 explicit ICC,
  orientation, CMYK, and YCCK interpretation-policy records.
- `jpeg_metadata_control_pairs.csv` contains 31 metadata-invariance, managed-
  profile-response, and CMYK/YCCK comparisons.
- `jpeg_metadata_summary.csv` contains 22 compact local aggregates.
- `jpeg_metadata_interpretation.png` visualizes ICC response, orientation
  contracts, raw metadata invariance, and CMYK/YCCK rendering differences.
- `jpeg_metadata_cross_platform_codec_manifest.csv` records the 20 adapter and
  implementation rows from the five-profile release matrix.
- `jpeg_metadata_cross_platform_raw_observations.csv`,
  `jpeg_metadata_cross_platform_policy_observations.csv`, and
  `jpeg_metadata_cross_platform_control_pairs.csv` preserve the combined
  release observations.
- `jpeg_metadata_cross_platform_summary.csv` aggregates every fixed raw,
  policy, and control key across the matrix.
- `jpeg_metadata_cross_platform_interpretation.png` visualizes response ranges,
  orientation policy exactness, decoded hash multiplicity, and CMYK/YCCK
  behavior across the recorded builds.

The fixed fixture corpus separates compressed component identity from APP
metadata and rendering policy. Numerical code-value differences are diagnostic
observations, not perceptual thresholds or device-color accuracy claims. The
cross-platform files are produced by the successful
[five-profile workflow](https://github.com/cab0a/research-notes/actions/runs/29971527088)
rather than simulated platform labels. CI compares the combined raw, policy,
control, and summary CSV files with these references on subsequent runs. The
codec manifest remains release provenance because hosted runner image metadata
can change independently of the fixed observations.

## v0.13.0

- `fixtures/malformed-jpeg-metadata/manifest.csv` records 21 deterministic
  valid, malformed, ambiguous, trailing-data, and resource-boundary JPEG
  fixtures around one preserved synthetic image stream.
- `jpeg_recovery_codec_manifest.csv` records the local strict auditor and
  OpenCV, Pillow, and FFmpeg decoder provenance.
- `jpeg_recovery_audit.csv` records one bounded structural decision per
  fixture, including stable issue codes, APP counts, metadata bytes, selected
  Exif and ICC topology fields, Adobe transforms, and trailing bytes.
- `jpeg_recovery_decoder_observations.csv` contains 63 local decoder probes
  with success, interface, exact-pixel, numerical difference, output hash, and
  diagnostic fingerprint fields.
- `jpeg_recovery_summary.csv` separates strict audit acceptance from decoder
  recovery for every fixture.
- `jpeg_recovery_contracts.png` visualizes strict acceptance, decoder success,
  exact output, and bounded metadata diagnostics.
- `jpeg_recovery_cross_platform_codec_manifest.csv`,
  `jpeg_recovery_cross_platform_audit.csv`, and
  `jpeg_recovery_cross_platform_decoder_observations.csv` preserve the
  five-profile release matrix.
- `jpeg_recovery_cross_platform_summary.csv` aggregates each fixture overall
  and by decoder.
- `jpeg_recovery_cross_platform_contracts.png` visualizes cross-platform
  acceptance, exact-success rates, and successful output-hash counts.

The successful
[five-profile workflow](https://github.com/cab0a/research-notes/actions/runs/30242822114)
recorded 105 audit observations and 315 decoder probes. All audit expectations
were met. Decoding succeeded exactly against the same decoder's platform
control in 300 probes, including 225 of the 240 probes attached to strict-
rejected fixtures. OpenCV failed only on the APP1 length overrun, Pillow failed
on that fixture and the truncated ICC chunk header, and FFmpeg recovered all
105 probes. The repeated failure set was identical on all five profiles.

The strict policy is an application boundary, not a universal JPEG acceptance
rule. A successful pixel decode is reported as recovery availability and never
as evidence that rejected metadata is valid or safe to propagate. The codec
manifest is release provenance and is not byte-compared on later CI runs
because hosted runner image identifiers can change independently of decoder
behavior.

## v0.14.0

- `jpeg_round_trip_codec_manifest.csv` records the local policy engine, Pillow
  raw decoder, and Pillow and OpenCV re-encoder provenance.
- `jpeg_round_trip_observations.csv` contains 168 local fixture, encoder, and
  policy observations with separate source decode, output, strict audit,
  complete-envelope byte, supported-semantic, compressed-core, and raw-pixel
  contracts.
- `jpeg_round_trip_summary.csv` aggregates output availability, strict
  acceptance, metadata retention, compressed-core identity, raw-pixel
  identity, and lossy re-encoding error by re-encoder and policy.
- `jpeg_metadata_round_trip.png` visualizes output and strict acceptance,
  complete-envelope and supported-semantic retention, and pixel equality to
  the policy-free re-encode control.
- `jpeg_round_trip_cross_platform_codec_manifest.csv` records 20 policy,
  decoder, and encoder provenance rows from the five-profile matrix.
- `jpeg_round_trip_cross_platform_observations.csv` combines all 840
  platform observations.
- `jpeg_round_trip_cross_platform_contracts.csv` summarizes behavior
  signatures and JPEG-byte and decoded-pixel hash multiplicity for all 168
  fixture, encoder, and policy contracts.
- `jpeg_round_trip_cross_platform_summary.csv` aggregates the matrix by
  re-encoder and policy.
- `jpeg_metadata_round_trip_cross_platform.png` visualizes emission and strict
  acceptance, behavior stability, and JPEG-byte stability.

The preserve policy is a manifest-controlled blind-copy baseline, not a
generic metadata parser. Normalize retains only strict-audit EXIF Orientation
and complete ICC profile semantics. Strip and normalize require a successful
Pillow source decode, while reject makes its trust decision at the strict audit
boundary. Byte equality, semantic retention, strict validity, output
availability, compressed-core identity, and decoded-pixel identity remain
separate claims.

The successful
[five-profile workflow](https://github.com/cab0a/research-notes/actions/runs/30427760311)
recorded one behavior signature for every fixed contract. All 620 emitted
outputs satisfied the compressed-core and decoded-pixel controls. The 124
output-bearing contracts also retained one output JPEG hash and one
decoded-pixel hash across the matrix. The codec manifest remains release
provenance and is not byte-compared on later CI runs because hosted runner
image metadata can change independently of fixed observations.

## v0.15.0

- `jpeg_metadata_generation_codec_manifest.csv` records the local policy,
  Pillow raw decoder, and Pillow and OpenCV encoder provenance.
- `jpeg_metadata_generation_observations.csv` contains 660 local records from
  five strict-accepted fixtures, two encoders, six policy sequences, and
  generations 0 through 10.
- `jpeg_metadata_generation_summary.csv` aggregates strict acceptance,
  metadata changes, original-envelope retention, supported-semantic retention,
  and decoded-pixel drift by encoder, sequence, and generation.
- `jpeg_metadata_generation_contracts.csv` contains 60 temporal contracts with
  post-transition metadata, JPEG, and pixel hash counts.
- `jpeg_metadata_generation_drift.png` visualizes original-envelope retention,
  supported EXIF and ICC retention, and the separate lossy image trajectory.
- `jpeg_metadata_generation_cross_platform_codec_manifest.csv` records the 20
  policy, decoder, and encoder provenance rows from the five-profile matrix.
- `jpeg_metadata_generation_cross_platform_observations.csv` combines all
  3,300 platform observations.
- `jpeg_metadata_generation_cross_platform_contracts.csv` summarizes behavior
  and metadata, compressed-core, complete-JPEG, and decoded-pixel hash
  multiplicity for all 660 temporal contracts.
- `jpeg_metadata_generation_cross_platform_summary.csv` contains 132 encoder,
  sequence, and generation aggregates.
- `jpeg_metadata_generation_cross_platform.png` visualizes behavior,
  metadata-state, and decoded-pixel stability across the recorded profiles.

All 60 local contracts reach one metadata-state hash after their final policy
transition, and all 660 outputs pass the strict metadata audit. Within every
fixture, encoder, and generation control, the six sequences have one
compressed-core and decoded-pixel hash. The generation-3 pixel fixed point is
specific to the one small synthetic image, quality 75, 4:4:4 sampling, and the
pinned local builds; it is not a general convergence or quality claim.

The successful
[five-profile workflow](https://github.com/cab0a/research-notes/actions/runs/30434189139)
recorded one behavior, metadata-state, compressed-core, complete-JPEG, and
decoded-pixel hash for every temporal contract. The codec manifest remains
release provenance and is not byte-compared on later CI runs because hosted
runner image identifiers can change independently of fixed observations.

## v0.16.0

- `jpeg_field_provenance_codec_manifest.csv` records the local field policy,
  controlled parser, raw decoder, and encoder provenance.
- `jpeg_field_provenance_decisions.csv` contains 288 source-to-output field
  decisions with field identifiers, categories, value hashes, retention
  states, and reason codes.
- `jpeg_selective_retention_observations.csv` contains 24 local output
  observations from two equivalent metadata layouts, two encoders, and six
  policies.
- `jpeg_selective_retention_summary.csv` aggregates retained fields,
  location and unclassified outcomes, strict acceptance, compressed-core
  identity, raw-pixel identity, and layout-equivalence hashes.
- `jpeg_selective_retention.png` visualizes retained field counts and
  category-level retention for every policy.
- `jpeg_field_provenance_cross_platform_codec_manifest.csv` records the 25
  policy, parser, decoder, and encoder provenance rows from the five-profile
  matrix.
- `jpeg_field_provenance_cross_platform_decisions.csv` combines all 1,440
  platform field decisions.
- `jpeg_selective_retention_cross_platform_observations.csv` combines all 120
  platform output observations.
- `jpeg_selective_retention_cross_platform_contracts.csv` records behavior,
  decision, metadata-state, complete-JPEG, and decoded-pixel multiplicity for
  all 24 fixture, encoder, and policy contracts.
- `jpeg_selective_retention_cross_platform_summary.csv` aggregates the matrix
  by encoder and policy.
- `jpeg_selective_retention_cross_platform.png` visualizes policy field counts
  and compatibility-contract stability.

All 24 outputs pass the strict metadata audit and remain exact to the
policy-free compressed image and raw-pixel controls. The location denylist
removes both controlled GPS fields but retains the custom XMP field and opaque
APP13 payload. The three selective allowlists remove every field that is not
explicitly enumerated. These results apply only to the twelve controlled
fields and bounded parser; they do not establish complete metadata semantics
or privacy compliance.

The successful
[five-profile workflow](https://github.com/cab0a/research-notes/actions/runs/30501815768)
recorded one behavior signature, decision signature, metadata-state hash,
complete-JPEG hash, and decoded-pixel hash for every contract. The codec
manifest remains release provenance and is not byte-compared on later CI runs
because hosted runner image identifiers can change independently of fixed
observations.

## v0.17.0

- `jpeg_resource_budget_runtime_manifest.csv` records the local admission
  policy, ElementTree/Expat parser, fixture encoder, and declared runtime
  profile.
- `jpeg_resource_budget_observations.csv` contains 24 local fixture
  observations with expected and observed routing, reason codes, fixture
  hashes, and observed-versus-admitted counters.
- `jpeg_resource_budget_summary.csv` aggregates the 24 observations into 14
  resource and negative-control families.
- `jpeg_resource_budget_boundaries.png` visualizes exact-limit admission,
  limit-plus-one quarantine, and admitted-counter ceilings.
- `jpeg_resource_budget_cross_platform_runtime_manifest.csv` records 15
  provenance rows from the five-profile matrix.
- `jpeg_resource_budget_cross_platform_observations.csv` combines all 120
  platform observations.
- `jpeg_resource_budget_cross_platform_contracts.csv` records decision,
  reason-code, issue, work-counter, and fixture-hash multiplicity for all 24
  fixture contracts.
- `jpeg_resource_budget_cross_platform_summary.csv` aggregates the matrix by
  resource family.
- `jpeg_resource_budget_cross_platform.png` visualizes routing counts and
  contract stability across the five profiles.

All ten exact-limit fixtures are accepted. All ten limit-plus-one fixtures are
quarantined at the first disallowed value without admitting the corresponding
counter above its ceiling. The prohibited-XMP and invalid-EXIF controls are
quarantined, while the segment-length overrun is rejected as a framing error.

The successful
[five-profile workflow](https://github.com/cab0a/research-notes/actions/runs/30506465070)
recorded one decision, reason-code, issue, work-counter, and fixture-hash
signature for every contract. The runtime manifest remains release provenance
and is not byte-compared on later CI runs because hosted runner image
identifiers can change independently of the fixed behavior.

## v0.18.0

- `jpeg_metadata_coverage_runtime_manifest.csv` records the local coverage
  parser, resource-admission gate, fixture encoder, and runtime profile.
- `jpeg_metadata_coverage_observations.csv` contains 15 controlled fixture
  observations with routing, reason codes, family recognition, relationship
  counts, opaque counts, and fixture hashes.
- `jpeg_metadata_coverage_summary.csv` aggregates the observations across
  seven primary fixture families.
- `jpeg_metadata_coverage.png` visualizes routing by family and declared versus
  resolved relationships.

Eight fixtures are accepted and seven are quarantined. Accepted fixtures
resolve all nine of their declared relationships. Forward and reverse Extended
XMP chunk order reconstruct the same 270-byte packet. Missing, duplicate,
orphaned, mismatched, truncated, and out-of-bounds controls fail closed. The
20-byte maker-note control remains opaque and is not interpreted as verified
metadata.

## v0.19.0

- `jpeg_transform_integrity_runtime_manifest.csv` records the local digest
  model, SHA-256 implementation, fixture encoder, and runtime profile.
- `jpeg_transform_integrity_observations.csv` contains 11 controlled transform
  observations with assertion status, reason, parent declaration, matching and
  mismatching scopes, assertion digest, and fixture hash.
- `jpeg_transform_integrity_summary.csv` aggregates statuses and mismatches
  across nine transform families.
- `jpeg_transform_integrity.png` visualizes assertion states and scope-specific
  mismatches.

The experiment produces two `valid_binding`, two `valid_derived_binding`, four
`stale_binding`, and one each of missing, malformed, and multiple assertion
states. Metadata reordering preserves all three declared scopes. Sanitization
invalidates only normalized metadata, while re-encoding and pixel editing
invalidate image-core and decoded-pixel bindings. Renewed records match their
current output and declare a parent digest, but remain unsigned and do not
authenticate provenance.

## v0.20.0

- `jpeg_policy_composition_runtime_manifest.csv` records the local decision
  engine, prerequisite study contracts, fixture encoder, and runtime profile.
- `jpeg_policy_composition_observations.csv` contains 36 fixture-profile
  observations with decisions, reasons, ordered traces, decisive stages,
  field counts, integrity states, and input/output hashes.
- `jpeg_policy_composition_summary.csv` aggregates decisions and emitted field
  counts for the four controlled profiles.
- `jpeg_policy_composition.png` visualizes profile-specific decisions and the
  stage responsible for each terminal result.

Across all profiles, the nine synthetic inputs produce 4 `accept`, 5
`sanitize`, 23 `quarantine`, and 4 `reject` decisions. All expectations match,
and every trace contains exactly one decisive final stage. The two selective
privacy outputs retain two of six controlled fields; minimal outputs retain
none. Sanitization removes the unsigned assertion rather than silently copying
a stale binding. Profile names remain study labels rather than compliance or
production-safety claims.

## v0.21.0

- `step_brep_topology_observations.csv` records the decision, reason, schema
  identifier, entity and reference counts, topology inventory, boundary counts,
  and exact source hash for each of six synthetic STEP fixtures.
- `step_brep_faces.csv` records analysis-local face indices, STEP entity IDs,
  parent shells and solids, declared surface types and parameters, bound counts,
  edge incidence, and adjacency.
- `step_brep_edges.csv` records vertex and curve references, curve types,
  oriented-use counts, incident faces, and free/nonmanifold classifications.
- `step_brep_shells.csv` records constituent faces, topology counts, declared
  closure, incidence-derived closure, and parent solids.
- `step_brep_solids.csv` records solid names, outer shells, and topology counts.
- `step_brep_topology_summary.csv` records corpus decisions, surface-family
  counts, and fixture-level topology metrics.
- `step_brep_topology.png` visualizes topology inventories, free boundaries,
  declared surface families, and fail-closed decisions.

All six fixtures match their declared outcomes. The closed tetrahedron has 4
faces, 6 edges, 1 shell, 1 solid, and no free edges; removing one face exposes
3 free edges. These results cover the committed simple-entity subset. They do
not establish general STEP conformance, evaluated geometric validity, or safe
handling of arbitrary files.

## v0.22.0

- `step_part21_exchange_observations.csv` records expected and observed
  decisions, section and entity counts, trust-boundary states, source sizes,
  and SHA-256 digests for 13 advanced exchange-structure fixtures.
- `step_part21_data_sections.csv` records DATA-section names, governing schema
  identifiers, and simple and complex entity counts for every parseable input.
- `step_part21_exchange_summary.csv` records the 5 accept, 4 quarantine, and 4
  reject outcomes plus representative feature routes.
- `step_part21_exchange_boundaries.png` visualizes structural recognition
  separately from external resolution, signature verification, archive work,
  and invalid structure.
- `step_part21_geometry_control.png` renders the synthetic coordinates of the
  committed closed tetrahedron geometry control.

All 13 fixtures match their declared outcomes. Accepted controls cover one and
multiple DATA sections, a three-component complex entity, direct UTF-8 and
binary tokens, and a tagged anchor. External references and signatures remain
quarantined with resolution and verification explicitly `not_attempted`.
Excessive nesting and ZIP input are also quarantined; four contradictory or
invalid structures are rejected. These results do not establish EXPRESS or
AP242 conformance, external resource safety, CMS validity, archive safety, or
evaluated geometry.

## v0.23.0

- `step_part21_source_model_observations.csv` records the expected and observed
  route, syntax status, exact-source status, source size, token composition,
  structure counts, diagnostics, schema status, and SHA-256 digest for ten
  fixtures.
- `step_part21_token_inventory.csv` contains 1,435 token rows for the five
  accepted fixtures, including exact raw spelling, normalized value, character
  offsets, UTF-8 byte offsets, and one-based line and column coordinates.
- `step_part21_source_model_summary.csv` records the 5 accept, 2 quarantine,
  and 3 reject outcomes, exact reconstruction rate, token inventory size, and
  the UTF-8 byte-versus-character difference.
- `step_part21_source_model.png` visualizes syntax decisions separately from
  resource-limit quarantine and shows retained grammar and trivia tokens.

All ten fixtures match their declared outcomes. The five accepted sources
reconstruct their original UTF-8 bytes exactly. The closed tetrahedron remains
an integration control with 74 entities and 97 occurrence references. Missing
syntax and invalid UTF-8 are rejected, while explicit nesting and token-length
budgets produce quarantine. EXPRESS schema conformance remains
`not_evaluated`; exact source retention is not proof of full Part 21 edition
coverage, application semantics, or geometric validity.

## v0.24.0

- `step_part21_conformance_observations.csv` records expected and observed
  decisions, reason codes, transport, implementation level, declared and
  required edition and class, detected features, structure counts, external
  parser outcomes, deferred semantic states, and fixture hashes.
- `step_part21_parser_comparison.csv` contains 102 parser-by-fixture outcomes
  for the controlled implementation, STEPutils, and the IfcOpenShell
  `step-file-parser`.
- `step_part21_grammar_coverage.csv` maps 13 feature families to their first
  edition, fixture, implementation status, and claim boundary.
- `step_part21_parser_manifest.csv` pins repository URLs, revisions, licenses,
  and comparison roles for all three parser observations.
- `step_part21_conformance_summary.csv` records the 34-fixture expectation
  rate, decision counts, accepted counts, and expectation agreement by parser.
- `step_part21_conformance.png` visualizes edition feature floors, controlled
  decisions, and different external-parser acceptance boundaries.

All 34 internal observations match their declared expectations: 17 accept and
17 reject. STEPutils accepts 14 fixtures and agrees with 23 expectations; the
IfcOpenShell `step-file-parser` accepts five and agrees with 22. These are
diagnostic comparisons, not standards-compliance scores. The corpus does not
evaluate EXPRESS schema rules, external resources, CMS authenticity,
application semantics, or geometry.

## v0.25.0

- `express_schema_observations.csv` records expected and observed routes,
  reason codes, source sizes and hashes, token and declaration counts, exact
  reconstruction, and deferred semantic states for 40 synthetic fixtures.
- `express_schema_inventory.csv` flattens 59 accepted schema, type, entity,
  attribute, interface, constant, rule, and algorithm-envelope records with
  source-line evidence.
- `express_grammar_coverage.csv` states which controlled lexical, declaration,
  and semantic stages are implemented, preserved as envelopes, or deferred.
- `express_schema_summary.csv` records corpus decisions, expectation rate,
  model inventory counts, and the explicit semantic-stage boundaries.
- `express_schema_model.png` visualizes controlled decisions, declaration
  composition, and the implemented-versus-deferred pipeline.

All 40 fixtures match their expected routes: 20 accept, 19 reject, and one
quarantine. Accepted sources reconstruct exactly, but acceptance establishes
only an unresolved syntax model for the controlled ASCII subset. It does not
establish complete EXPRESS conformance, symbol resolution, type correctness,
constraint evaluation, rule execution, Part 21 validation, or application
semantics.

## v0.26.0

- `express_resolution_observations.csv` records expected and observed routes,
  reason codes, semantic counts, deferred stages, and source identities for 38
  synthetic fixtures.
- `express_symbols.csv` contains 118 analysis-local schema and declaration
  symbols with original spelling and source lines.
- `express_reference_resolution.csv` contains 72 interface, type, select,
  inheritance, rule, bound, and inverse references with required kinds, all
  candidates, and explicit resolution states.
- `express_type_resolution.csv` records terminal domains and alias chains for
  23 defined types.
- `express_aggregate_bounds.csv` records nine aggregate-bound pairs with raw
  source, integer-literal or constant provenance, evaluated values, and state.
- `express_inheritance.csv` records immediate and transitive supertypes plus
  local, inherited, effective, and redeclared attribute counts for 44 entity
  observations.
- `express_resolution_summary.csv` records decision, graph-row, and state
  counts.
- `express_symbols_types_inheritance.png` visualizes decisions, reference
  states, and type-versus-inheritance graph outcomes.

All 38 fixtures match their expected routes: 20 accept, 17 reject, and one
quarantine. The 72 reference rows contain 61 resolved, seven unresolved, one
ambiguous, and three invalid-kind states. These results apply only to local and
direct in-document imports in the controlled subset. They do not establish
complete EXPRESS visibility, external schema loading, type compatibility,
expression typing, rule execution, Part 21 validation, or AP242 semantics.

## v0.27.0

- `step_express_validation_observations.csv` records the expected and observed
  routes, five validation-stage states, counts, deferred work, and paired
  source identities for 40 synthetic STEP/EXPRESS fixtures.
- `step_express_sections.csv` records DATA-section schema ownership and binding
  outcomes.
- `step_express_instances.csv` records internal or external mapping, component
  entity identities, expected and actual parameter counts, and instance state.
- `step_express_parameters.csv` maps 50 Part 21 parameters to their EXPRESS
  entity and attribute origins, expected types, exact value sources, and
  validation reasons.
- `step_express_diagnostics.csv` records 21 invalid or deferred stage,
  instance, and parameter diagnostics with source coordinates where available.
- `step_express_validation_summary.csv` records decisions, stage reach,
  instance states, and parameter states.
- `step_express_validation.png` visualizes fixture decisions, stage reach,
  parameter evidence, and frequent controlled diagnostics.

All 40 fixtures match their expected routes: 15 accept, 21 reject, and four
quarantine. The parameter evidence contains 35 valid, 13 invalid, and two
deferred rows. Complex evaluated sets, constants, width constraints, complete
assignment compatibility, rules, AP242 application meaning, and geometry are
not validated.

## v0.28.0

- `step_graph_observations.csv` records expected and observed routes, graph
  counts, traversal status, source hashes, and controlled graph limits for 14
  synthetic fixtures.
- `step_graph_nodes.csv` records stable analysis-local node IDs, Part 21 IDs,
  DATA-section and schema ownership, record types, source spans, and adjacency
  edge indices.
- `step_graph_edges.csv` records every reference occurrence independently,
  including repeated edges, nested parameter paths, target scope, reference
  kind, and source span.
- `step_graph_queries.csv` records exact-type, forward, reverse, root,
  isolation, cycle, reachability, and caller-relative orphan queries with
  explicit complete, partial, or not-evaluated states.
- `step_graph_summary.csv` records corpus, graph, decision, target-scope, and
  query-status counts.
- `step_graph.json` is the deterministic `research-notes.step-graph` version
  `1.0` record for the representative branching fixture.
- `step_graph.png` visualizes that graph, corpus edge scopes, and query states.

All 14 fixtures match their expected routes: 11 accept, two quarantine, and
one reject. Accepted graphs contain 31 nodes and 25 reference-occurrence
edges; 86 query rows complete, two stop at a declared depth limit, and one
orphan query remains not evaluated because its traversal is partial. These
are physical Part 21 relationships, not AP242 product structure, assembly
semantics, B-Rep interpretation, or persistent CAD identity.

## v0.29.0

- `ap242_path_observations.csv` records expected and observed routes, schema
  identifiers, evidence counts, diagnostics, source hashes, and controlled
  semantic work limits for 14 synthetic fixtures.
- `ap242_product_paths.csv` records product, formation, product-definition,
  shape-definition, representation, context, dimension, item, placement, and
  unit facts for each resolved path.
- `ap242_semantic_relations.csv` joins each schema-derived role to one physical
  reference occurrence, parameter path, and source coordinate.
- `ap242_representation_items.csv` classifies direct items as placements, solid
  models, geometric items, mapped items, or unclassified.
- `ap242_context_units.csv` records controlled SI length, plane-angle, and
  solid-angle assignments without performing conversion.
- `ap242_path_diagnostics.csv` preserves deferred and invalid semantic states.
- `ap242_path_summary.csv` records corpus, decision, evidence, and item-role
  counts.
- `ap242_product_paths.json` is the deterministic
  `research-notes.ap242-product-paths` version `1.0` record.
- `ap242_product_paths.png` visualizes the controlled semantic chain and corpus
  decisions.

All 14 fixtures match their expected routes: three accept, eight quarantine,
and three reject. The experiment resolves five paths, 59 source-linked
semantic relations, nine direct items, five placements, and 15 units. These
results do not establish complete AP242 conformance, assembly occurrence
semantics, transformation composition, unit conversion, or B-Rep validity.

## v0.30.0

- `ap242_assembly_observations.csv` records expected and observed routes,
  evidence counts, diagnostics, source hashes, and controlled semantic work
  limits for 17 synthetic fixtures.
- `ap242_assembly_occurrences.csv` records definition identities, occurrence
  identities, reference designators, source and target placements, source
  units, child-to-parent translations, rotations, and source coordinates.
- `ap242_assembly_paths.csv` records root-relative occurrence chains, depth,
  composed translations, rotations, and determinants.
- `ap242_assembly_relations.csv` joins every controlled assembly role to one
  physical reference occurrence, parameter path, and source coordinate.
- `ap242_assembly_units.csv` records child and parent length-unit declarations,
  unit forms, millimetre scales, and conversion hops.
- `ap242_assembly_diagnostics.csv` preserves deferred and invalid semantic
  states when parsing and graph construction complete.
- `ap242_assembly_summary.csv` records corpus routes and accepted evidence
  counts.
- `ap242_assembly.json` preserves occurrence and path matrices in deterministic
  machine-readable records.
- `ap242_assembly_paths.png` visualizes corpus decisions and root-relative
  origins for the nested reuse control.

All 17 fixtures match their expected routes: five accept, six quarantine, and
six reject. Accepted evidence contains eight occurrences, eight paths, 226
source-linked relations, and 16 unit observations. The maximum accepted depth
is two, and one conversion-based unit is normalized to millimetres. These
results do not establish complete AP242 conformance, support for arbitrary
transformation selections, derived-unit evaluation, or B-Rep validity.

## v0.31.0

- `geometry_kernel_candidates.csv` compares eight routes against six technical
  gates while preserving kernel family, Python route, license layers,
  independence, disposition, rationale, and direct source links.
- `geometry_kernel_package_audit.csv` records versions, package metadata
  licenses, requirements, manifest file counts and sizes, standard license-file
  paths, and whether the bounded inventory found an OCCT LGPL notice. The
  installer-history-specific zero-byte `REQUESTED` marker is excluded.
- `geometry_kernel_probe.csv` records the pinned binding and processor versions,
  STEP write/read status, kernel checks, unique topology counts, normalized
  fixture hash, and the internal Part 21 parser boundary.
- `geometry_kernel_selection_summary.csv` provides compact selection,
  round-trip, parser, and package evidence.
- `geometry_kernel_decision.json` is the deterministic
  `research-notes.geometry-kernel-selection` version `1.0` decision record.
- `geometry_kernel_selection.png` visualizes the candidate gates, topology
  preservation, and installed reference dependency footprint.

CadQuery OCP with OCCT is the only route passing all six project gates. The
synthetic box retains 1 solid, 6 faces, 12 unique edges, and 8 unique vertices
after STEP exchange. The 940,567,380-byte installed-file inventory describes
three pinned Python distributions; it is not memory use or download size. No
third-party binaries are committed, and the result is not legal advice or
permission to redistribute OCCT.

## v0.32.0

- `evaluated_face_geometry_observations.csv` records six matched observations:
  three constructed faces and the same three controls after STEP import. Every
  row contains expected and observed surface type, orientation, area,
  centroid, UV bounds, representative point, support normal, oriented normal,
  surface frame, cylinder radius, face tolerance, and explicit error fields.
- `evaluated_face_geometry_summary.csv` records compact maximum-error,
  orientation, validity, representation-uncertainty, and face-tolerance
  evidence by evaluation stage.
- `evaluated_face_geometry.json` is the deterministic
  `research-notes.evaluated-face-geometry` version `1.0` truth, tolerance,
  provenance, limitation, and open-question contract.
- `evaluated_face_geometry.png` visualizes the three analytic controls,
  closed-form comparison errors, and constructed-versus-imported tolerances.

The constructed and imported geometric values remain inside the declared
synthetic numeric contract, and the reversed plane orientation is retained.
The constructed face tolerances `1e-4`, `2e-4`, and `3e-4` become `1e-7` for
all three imported faces. This is a pinned translation observation, not a
universal STEP tolerance rule or a manufacturing quality threshold.

## v0.33.0

- `edge_curve_observations.csv` records 22 unique-edge observations: 11
  constructed and 11 STEP imported. Each row contains boundary roles, expected
  and observed 3D curve type, analytic and measured length, parameter range,
  `SameParameter`, `SameRange`, degenerate and seam states, p-curve branch
  count, edge tolerance, and maximum consistency distance.
- `pcurve_observations.csv` records 24 oriented wire occurrences: 12 at each
  stage. Each row contains p-curve range, topological start and end vertex
  parameters, UV start/mid/end, UV error, range alignment, and the 17-sample
  3D-curve-to-surface residual.
- `edge_curve_summary.csv` records compact topology, STEP entity-count,
  curve-type, length, parameter, UV, residual, flag, and tolerance evidence.
- `edge_curve_contract.json` is the deterministic
  `research-notes.edge-curve-evaluation` version `1.0` truth, sampling,
  provenance, limitation, and open-question contract.
- `edge_curve_evaluation.png` visualizes the analytic boundary controls, the
  two periodic p-curve branches of one seam edge, and maximum numeric errors.

The full-cylinder seam is one unique edge used twice, with separate p-curves
at `u=0` and `u=2π`. All controlled curve types and parameter spans match; the
maximum imported p-curve-to-3D-curve distance is `1.24e-12`. This is a fixed
fixture result, not a universal consistency threshold or repair policy.

## v0.34.0

- `wire_trimming_face_observations.csv` records eight face observations: four
  constructed and four STEP imported. Each row separates restricted UV bounds
  from support-surface bounds and reports orientation, area, centroid,
  periodicity, natural-restriction state, and outer/inner wire counts.
- `wire_trimming_wire_observations.csv` records twelve ordered loops with role,
  orientation, occurrence and unique-edge counts, seam and degenerate counts,
  expected and observed signed UV area, closure gaps, topology identity, and
  independent backend check statuses.
- `wire_trimming_edge_uses.csv` records 48 ordered edge occurrences with
  orientation-aware vertex parameters, p-curve endpoints, next-use closure,
  seam state, degenerate state, and 3D-curve availability.
- `wire_trimming_classifications.csv` records 32 observations over sixteen
  material, void, exterior, and boundary samples at both stages.
- `wire_trimming_summary.csv` records compact face, wire, classification,
  validity, numeric-error, and STEP entity-count evidence.
- `wire_trimming_contract.json` is the deterministic
  `research-notes.wire-trimming-evaluation` version `1.0` truth, exchange,
  limitation, and open-question contract.
- `wire_trimming_evaluation.png` visualizes planar winding, periodic seams,
  singular pole boundaries, and maximum analytic or closure errors.
- `wire_trimming_shapes.png` renders the generated planar frames, closed
  cylinder, sphere, seam locations, and degenerate poles for visual review.

The forward planar frame has signed outer and inner UV areas `+48` and `-6`;
the reversed face has `-48` and `+6` while both retain material area `42` and
the same classifications. The sphere uses one seam edge twice plus two
degenerate pole edges without 3D curves. All six wires remain closed and all
sixteen classifications match after STEP import. The imported sphere no
longer reports the constructed `NaturalRestriction` flag, so that kernel state
is not claimed as a portable STEP semantic.

## v0.35.0

- `shell_solid_observations.csv` records fourteen whole-shape observations:
  seven constructed and seven STEP imported. Each row reports V/E/F,
  shell/solid counts, face components, boundary and nonmanifold incidence,
  Euler characteristic, orientability, current orientation, minimum face
  flips, project admission, generic backend validity, and signed volume.
- `shell_solid_edge_incidence.csv` records every unique edge with oriented use
  count, unique incident faces, boundary/nonmanifold class, and paired
  direction evidence.
- `shell_solid_components.csv` records sixteen connected face components with
  local V/E/F, Euler, boundary, nonmanifold, and closure values.
- `shell_validity_observations.csv` keeps every backend shell's closure and
  orientation status separate from the whole-shape analyzer result.
- `shell_solid_summary.csv` records the compact independent topology,
  volume-admission, backend-boundary, and STEP-change findings.
- `shell_solid_contract.json` is the deterministic
  `research-notes.shell-solid-validity` version `1.0` truth, exchange,
  limitation, and open-question contract.
- `shell_solid_validity.png` compares validity layers, topology counts, signed
  volumes, and STEP shell regrouping.
- `shell_solid_shapes.png` renders the valid, reversed, open, misoriented,
  nonmanifold, genus-one, and disconnected controls for visual inspection.

All fourteen stages retain their controlled topology values. The generic
analyzer returns true for three constructed controls that fail the project's
closed-oriented-shell gate: the open box, one-face-flipped box, and
nonmanifold fan. STEP import changes the reversed box volume sign from `-120`
to `+120`, reorients the flipped face, splits the nonmanifold fan from one
shell into three, and splits the disconnected face pair from one shell into
two. The valid torus retains Euler characteristic `0`; its imported volume
magnitude differs from `18π²` by `6.37e-12`.

## v0.36.0

- `tolerance_sewing_observations.csv` records seventeen source, sewn,
  orientation-repair, and tolerance-cap stages with topology, incidence,
  orientation, local-tolerance aggregates, planar geometry, raw volume, and
  admission fields.
- `tolerance_sewing_subshape_tolerances.csv` records all 550 analysis-local
  vertex, edge, and face tolerances without claiming stable identity across
  stages.
- `tolerance_sewing_operations.csv` records twelve sewing, orientation, and
  tolerance-change operations with exact parameters, backend reports, observed
  changes, and bounded decisions.
- `tolerance_sewing_summary.csv` records the closure matrix, tolerance growth,
  orientation repair, invalidating cap, geometry preservation, and volume gate.
- `tolerance_sewing_contract.json` is the deterministic
  `research-notes.tolerance-sewing-healing` version `1.0` contract.
- `tolerance_sewing_healing.png` compares closure, stored edge tolerances,
  free boundaries, orientation, validity, and volume eligibility.
- `tolerance_sewing_shapes.png` shows the synthetic gap and orientation
  controls with nonzero gaps deliberately exaggerated.

The `5e-7` gap closes at `1e-6` and above; the `5e-5` gap closes only at
`1e-4`. All six planar face areas, centroids, and support-plane equations
remain fixed, while selected vertex and edge tolerances grow with the merged
residual. One reversed face is
reoriented without topology or support-geometry drift. Capping the large-gap
result below its residual retains closure but changes native validity from
true to false, so the completed operation is rejected.

## v0.37.0

- `manifold_intersection_observations.csv` records 24 constructed and
  STEP-imported topology, edge-incidence, nonmanifold-vertex, relationship,
  and self-interference contract summaries for 12 controls.
- `vertex_link_observations.csv` records 224 analysis-local vertices, their
  incident edges and faces, link arcs, link components, degree counts, and
  manifold classification.
- `shape_pair_relations.csv` records 14 pair observations with minimum
  distance, common-part topology and measures, section topology and measures,
  contact dimension, relationship, expected measure, and absolute error.
- `self_intersection_observations.csv` records eight single-argument
  `BOPAlgo_CheckerSI`
  observations for four controls at constructed and STEP-imported stages,
  including checker level, edge/edge, edge/face, and face/face interference
  counts, point/curve evidence, derived intersection dimension and quantity,
  and contract matches.
- `manifold_intersection_summary.csv` records corpus size, stage matches,
  nonmanifold-vertex observations, and maximum pair and self-intersection
  quantity errors.
- `manifold_intersection_contract.json` is the deterministic v0.37.0 control
  and summary contract for the pinned geometry route.
- `manifold_self_intersection.png` compares relationship dimension,
  complementary edge- and vertex-nonmanifold detections, and aggregate
  self-interference counts.
- `manifold_self_intersection_shapes.png` shows generated box-contact and
  aggregate edge/face-interference controls schematically.

The pinched tetrahedra have two face uses per edge but a disconnected link at
their shared vertex. In one aggregate B-Rep, separated edges have no edge/edge
interference while crossing edges have one interior point; separated faces
have no face/face interference while transverse faces have one curve of length
`2`. Separate box controls distinguish a unit gap, point contact, length-`4`
edge contact, area-`16` face contact, and volume-`9` overlap. These results are
bounded polyhedral regressions, not a general self-intersection or collision-
policy claim.

Regenerate the artifacts from the repository root:

```bash
python experiments/run_laplacian_variance.py
python experiments/run_focus_metric_comparison.py
python experiments/run_local_blur_evaluation.py
python experiments/run_window_geometry_evaluation.py
python experiments/run_preprocessing_sensitivity.py
python experiments/run_optical_blur_models.py
python experiments/run_photometric_recompression.py
python experiments/run_jpeg_compression_history.py
python experiments/run_jpeg_codec_portability.py
python experiments/run_cross_platform_codec_contracts.py
python experiments/run_advanced_jpeg_syntax.py
python experiments/run_color_metadata_interpretation.py
python experiments/run_malformed_metadata_recovery.py
python experiments/run_metadata_round_trip.py
python experiments/run_metadata_generation_drift.py
python experiments/run_field_level_metadata_provenance.py
python experiments/run_resource_bounded_metadata.py
python experiments/run_metadata_family_coverage.py
python experiments/run_transform_integrity.py
python experiments/run_policy_composition.py
python experiments/run_step_brep_topology.py
python experiments/run_step_exchange_structure.py
python experiments/run_step_part21_source_model.py
python experiments/run_step_part21_conformance.py
python experiments/run_express_schema_model.py
python experiments/run_express_symbol_resolution.py
python experiments/run_step_express_validation.py
python experiments/run_step_graph_queries.py
python experiments/run_ap242_product_paths.py
python experiments/run_ap242_assembly.py
python experiments/run_geometry_kernel_selection.py
python experiments/run_evaluated_face_geometry.py
python experiments/run_edge_curve_evaluation.py
python experiments/run_wire_trimming_evaluation.py
python experiments/run_shell_solid_validity.py
python experiments/run_tolerance_sewing_healing.py
python experiments/run_manifold_self_intersection.py
```

All committed CSV and JSON files are deterministic reference artifacts checked by CI.
CI also regenerates every chart and verifies that non-empty PNG files are
produced. PNG byte identity is not asserted because font rasterization can
differ across operating systems.
