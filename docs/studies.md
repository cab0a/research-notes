# Study Index

## 日本語概要

本書は、ぼけ指標、局所評価、前処理、JPEG圧縮、デコーダー差、色管理、壊れたメタデータ、メタデータ保持・無害化・世代間ドリフト・field単位の選択保持・resource上限を扱う17件の研究を索引化しています。各版の問い、代表結果、CSV・図、再現コマンド、完全な研究ノートを対応付け、数値を一般的なしきい値として扱わない境界も示します。

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

## Artifact Details

The [`results` catalog](../results/README.md) documents every committed CSV and
PNG file. Fixed JPEG streams, reference decodes, and their manifests are under
[`fixtures/`](../fixtures/).

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
  arbitrary malformed files.

The complete notes contain the narrower limitations for each experiment.
