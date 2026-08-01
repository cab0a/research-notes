# Reference Results

## 日本語概要

このディレクトリには、17件の研究を固定した合成画像と版管理された実験スクリプトから生成した参照成果物があります。観測値、集約CSV、比較図、環境別の復号結果、メタデータ監査・保持・無害化・世代間ドリフト・field単位の選択保持・resource上限の結果を研究版ごとに対応付けています。

各成果物の内容と再生成元は以下の英語本文を参照してください。

---

This directory contains committed outputs generated exclusively from synthetic
images by the versioned experiment scripts.

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
```

All committed CSV files are deterministic reference artifacts checked by CI.
CI also regenerates every chart and verifies that non-empty PNG files are
produced. PNG byte identity is not asserted because font rasterization can
differ across operating systems.
