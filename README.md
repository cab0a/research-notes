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

The v0.1.0 study evaluates Laplacian variance as a blur heuristic. The v0.2.0
study extends the same controls to an area-normalized Tenengrad comparison,
repeated noise trials, horizontal motion blur, and resize sensitivity.

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

Every published note should make that chain inspectable and reproducible.

## Published Notes

- [Laplacian Variance vs. Tenengrad Under Blur and
  Noise](notes/laplacian-vs-tenengrad.md) — v0.2.0
- [Laplacian Variance as a Blur Heuristic: Controlled Evaluation and
  Limitations](notes/laplacian-variance-blur.md) — v0.1.0

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
```

On Windows PowerShell, activate the environment with
`.venv\Scripts\Activate.ps1`. The experiment uses only programmatically
generated images and deterministic random seeds. Running it writes the CSV and
PNG under `results/`.

## Evaluation

The v0.2.0 experiment retains three synthetic spatial patterns, Gaussian blur
sigma values 0, 1, 2, and 3, and Gaussian noise standard deviations 0, 5, and
15. It adds an area-normalized Tenengrad measure and 20 seeded trials per
condition, producing 720 raw observations. The evaluation checks relative
relationships:

- without added noise, stronger Gaussian blur should reduce both metrics for
  each controlled pattern;
- added noise can increase both metrics for an already blurred image;
- repeated runs with the declared environment and seeds should reproduce the
  committed CSV files.

At Gaussian sigma 3, the mean within-pattern ratio to the no-blur baseline is
0.003073 for Laplacian variance and 0.137201 for Tenengrad energy. Adding noise
with standard deviation 15 produces median inflation ratios of 96.679135 and
1.173198 respectively, relative to each metric's noise-free sigma-3 baseline.
These are experiment-specific observations, not transferable quality
thresholds or proof of universal metric superiority.

No fixed Laplacian-variance threshold is presented as a universal quality bar.

## Limitations

The studies use small, 8-bit synthetic grayscale images. v0.2.0 adds one
horizontal-motion direction and one resize round trip, but does not establish
behavior for other motion angles, defocus point-spread functions, compression,
demosaicing, sharpening, color pipelines, local blur, natural scenes, or human
quality judgments. Scores remain dependent on texture, contrast, resolution,
border handling, and implementation details.

## Project Structure

```text
.
├── .github/workflows/ci.yml
├── experiments/run_focus_metric_comparison.py
├── experiments/run_laplacian_variance.py
├── notes/laplacian-vs-tenengrad.md
├── notes/laplacian-variance-blur.md
├── results/
│   ├── README.md
│   ├── focus_metric_comparison.png
│   ├── focus_metric_summary.csv
│   ├── focus_metric_trials.csv
│   ├── laplacian_variance_summary.csv
│   ├── laplacian_variance.png
│   ├── motion_blur_summary.csv
│   └── resize_sensitivity_summary.csv
├── src/research_notes/
│   ├── __init__.py
│   └── blur_metrics.py
├── tests/test_blur_metrics.py
├── LICENSE
├── README.md
└── pyproject.toml
```

## Roadmap

- Add spatially localized blur and regional evaluation.
- Extend motion sensitivity to multiple directions and a defocus model.
- Replicate selected controls on a traceable public image set with labels.

The roadmap is exploratory and does not represent completed work.

## License

Code and documentation are available under the [MIT License](LICENSE).
