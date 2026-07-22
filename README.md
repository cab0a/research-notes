# Research Notes

Reproducible technical investigations that connect a focused research question
to source review, controlled experiments, evaluation, interpretation, and
explicit limitations.

## Overview

This repository demonstrates a compact research workflow for computer vision
and image-processing questions. Each note is backed by reviewable code,
synthetic data, committed reference results, tests, and continuous integration.
It is not a collection of links and does not claim that a controlled synthetic
experiment automatically generalizes to production imagery.

The studies progress from one global blur heuristic to comparative robustness,
spatial aggregation, window geometry, preprocessing sensitivity, optical blur
models, photometric pipeline drift, and JPEG compression history. v0.8.0
evaluates primary-to-secondary quality order, aligned and shifted block grids,
explicit 4:4:4 and 4:2:0 sampling paths, and fixed-calibration transfer.

## Research Workflow

```text
Research Question
    -> Source Review
    -> Method Selection
    -> Controlled Experiment
    -> Evaluation
    -> Interpretation
    -> Limitations
    -> Documentation
```

Every published note makes that chain inspectable and reproducible.

## Published Notes

- [JPEG Compression History: Quality Order, Grid Alignment, and Chroma Sampling](notes/jpeg-compression-history.md)
  — v0.8.0
- [Photometric Normalization and Recompression Drift](notes/photometric-normalization-recompression-drift.md)
  — v0.7.0
- [Optical Blur Models and Directional Motion Sensitivity](notes/optical-blur-models-directional-motion.md)
  — v0.6.0
- [Preprocessing Sensitivity and Calibration Drift](notes/preprocessing-sensitivity-calibration-drift.md)
  — v0.5.0
- [Window Geometry and Robustness for Local Blur Detection](notes/window-geometry-robustness.md)
  — v0.4.0
- [Local Blur and Spatial Aggregation](notes/local-blur-spatial-aggregation.md)
  — v0.3.0
- [Laplacian Variance vs. Tenengrad Under Blur and Noise](notes/laplacian-vs-tenengrad.md)
  — v0.2.0
- [Laplacian Variance as a Blur Heuristic: Controlled Evaluation and Limitations](notes/laplacian-variance-blur.md)
  — v0.1.0

## Reproducibility

Python 3.11 or newer is required. The reference environment uses Python 3.12
and exact runtime dependency versions declared in `pyproject.toml`.

```bash
git clone https://github.com/cab0a/research-notes.git
cd research-notes
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
python -m pytest
python experiments/run_laplacian_variance.py
python experiments/run_focus_metric_comparison.py
python experiments/run_local_blur_evaluation.py
python experiments/run_window_geometry_evaluation.py
python experiments/run_preprocessing_sensitivity.py
python experiments/run_optical_blur_models.py
python experiments/run_photometric_recompression.py
python experiments/run_jpeg_compression_history.py
```

On Windows PowerShell, activate the environment with
`.venv\Scripts\Activate.ps1`. The experiments use only programmatically
generated images and deterministic random seeds. Each experiment writes its
CSV and PNG artifacts under `results/`.

## Evaluation

The notes evaluate relative relationships under declared controls instead of
proposing a fixed quality threshold:

- v0.1.0 confirms that noiseless Gaussian blur lowers Laplacian variance and
  that added noise can reverse a simple interpretation.
- v0.2.0 compares Laplacian variance with area-normalized Tenengrad over 720
  repeated observations, plus bounded motion-blur and resize controls.
- v0.3.0 shows spatial dilution: with one of 16 aligned tiles blurred at sigma
  3, mean full-image ratios remain 0.936866 for Laplacian variance and 0.940676
  for Tenengrad, while mean minimum tile ratios fall to 0.005025 and 0.062950.
- v0.4.0 shows a window-geometry blind spot: a 64/64 grid captures at most 25%
  of a 64-pixel region offset by 32 pixels, while a 64/32 grid recovers 100%
  coverage. In repeated sigma-3 trials, noise standard deviation 15 raises the
  mean minimum Laplacian ratio from 0.005765 to 0.200820 on the 64/32 grid even
  though localization ranking remains unchanged.
- v0.5.0 shows preprocessing calibration drift over 9,360 observations. For
  clean sharp inputs, resize and Gaussian denoising lower mean Laplacian ratios
  to 0.091416 and 0.048873, causing the unchanged synthetic midpoint rule to
  fall to balanced accuracy 0.5. JPEG quality 50 raises the sigma-3 Laplacian
  response to 1.853677 times the same uncompressed input, while unsharp masking
  under noise 15 produces a blurred miss rate of 0.666667.
- v0.6.0 compares 17 identity, disk-defocus, and directional-motion conditions
  over 5,100 metric observations. At motion length 15 without noise, mean
  aligned-to-perpendicular ratios are 0.066796 for Laplacian variance and
  0.024429 for Tenengrad. At noise standard deviation 15, the Laplacian ratio
  reaches 1.008207, showing that noise can erase and slightly reverse the
  directional contrast in this controlled setting.
- v0.7.0 records 11,520 metric observations across 16 photometric and JPEG
  pipelines. Contrast gain 0.50 lowers clean sharp responses to 0.250919 for
  Laplacian variance and 0.250680 for Tenengrad, reducing the unchanged
  midpoint calibration to balanced accuracy 0.5 for both metrics. A first
  grayscale JPEG quality-75 round trip lowers the clean sharp Laplacian ratio
  to 0.930825 but raises the sigma-3 ratio to 1.637515; rounds 2 and 5 converge
  to the same six-decimal aggregate values in this bounded setting.
- v0.8.0 records 4,320 metric observations across nine two-stage JPEG
  histories. An aligned grayscale quality-75 second round remains at a
  six-decimal final-to-primary ratio of 1.000000, while a 4 x 4 grid shift
  changes the sigma-3 Laplacian ratio to 0.805242. Reversing quality 95 -> 75
  to 75 -> 95 changes the clean sharp Laplacian ratio from 0.920521 to
  1.003831. At noise standard deviation 15, the unchanged uncompressed midpoint
  rule falls to balanced accuracy 0.666667 for Laplacian variance and 0.833333
  for Tenengrad on the shifted quality-75 path.

These are experiment-specific observations, not transferable quality
thresholds or proof of universal metric superiority.

## Limitations

The studies use small, 8-bit synthetic images. v0.8.0 adds five grayscale
quality orders, four explicit BGR sampling paths, and aligned or 4 x 4-shifted
two-stage JPEG grids under one pinned OpenCV build. It does not establish
behavior for natural scenes, measured camera response or PSFs, explicit
quantization-table equivalence, arbitrary grid shifts, codec-build variation,
progressive JPEG, color profiles, demosaicing, HDR tone mapping, diffraction,
aberrations, rolling shutter, or human quality judgments.
Scores remain dependent on texture, contrast, resolution, codec implementation,
preprocessing order, window geometry, PSF rasterization, border handling, and
metric details. Known pattern identities, matched sharp references, and
synthetic anchors are controls that are usually unavailable in blind
inspection.

## Project Structure

```text
.
|-- .github/workflows/ci.yml
|-- experiments/
|   |-- run_focus_metric_comparison.py
|   |-- run_jpeg_compression_history.py
|   |-- run_laplacian_variance.py
|   |-- run_local_blur_evaluation.py
|   |-- run_optical_blur_models.py
|   |-- run_photometric_recompression.py
|   |-- run_preprocessing_sensitivity.py
|   `-- run_window_geometry_evaluation.py
|-- notes/
|   |-- laplacian-variance-blur.md
|   |-- laplacian-vs-tenengrad.md
|   |-- jpeg-compression-history.md
|   |-- local-blur-spatial-aggregation.md
|   |-- optical-blur-models-directional-motion.md
|   |-- photometric-normalization-recompression-drift.md
|   |-- preprocessing-sensitivity-calibration-drift.md
|   `-- window-geometry-robustness.md
|-- results/
|   |-- README.md
|   |-- *.csv
|   `-- *.png
|-- src/research_notes/
|   |-- __init__.py
|   |-- blur_models.py
|   |-- blur_metrics.py
|   |-- photometric.py
|   `-- preprocessing.py
|-- tests/test_blur_metrics.py
|-- LICENSE
|-- README.md
`-- pyproject.toml
```

## Roadmap

- Compare explicit JPEG quantization tables and codec builds without treating
  nominal quality values as portable equivalents.
- Evaluate adaptive or multiscale aggregation without treating overlapping
  windows as independent evidence.
- Extend the global PSF controls to spatially varying defocus and non-uniform
  motion without treating synthetic labels as measured camera truth.
- Replicate selected controls on a traceable public image set with labels.

The roadmap is exploratory and does not represent completed work.

## License

Code and documentation are available under the [MIT License](LICENSE).
