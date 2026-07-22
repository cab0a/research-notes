# Reference Results

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
```

All committed CSV files are deterministic reference artifacts checked by CI.
CI also regenerates every chart and verifies that non-empty PNG files are
produced. PNG byte identity is not asserted because font rasterization can
differ across operating systems.
