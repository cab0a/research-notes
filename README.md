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

The v0.1.0 study evaluates Laplacian variance as a blur heuristic. It tests the
expected response to Gaussian blur and a known confounder: high-frequency
Gaussian noise.

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
```

On Windows PowerShell, activate the environment with
`.venv\Scripts\Activate.ps1`. The experiment uses only programmatically
generated images and deterministic random seeds. Running it writes the CSV and
PNG under `results/`.

## Evaluation

The v0.1.0 experiment covers three synthetic spatial patterns, Gaussian blur
sigma values 0, 1, 2, and 3, and Gaussian noise standard deviations 0, 5, and
15. The evaluation checks relative relationships:

- without added noise, stronger Gaussian blur should reduce Laplacian variance
  for each controlled pattern;
- added noise can increase Laplacian variance, including for an already blurred
  image;
- repeated runs with the declared environment and seeds should reproduce the
  committed CSV.

Across the three patterns, the mean noise-free score falls from 11788.257772 at
blur sigma 0 to 41.224080 at sigma 3. At sigma 3, adding noise with standard
deviation 15 raises the mean to 4354.484975. These are experiment-specific
observations, not transferable quality thresholds.

No fixed Laplacian-variance threshold is presented as a universal quality bar.

## Limitations

The experiment isolates Gaussian blur and additive Gaussian noise on small,
8-bit synthetic grayscale images. It does not establish behavior for motion
blur, defocus point-spread functions, compression artifacts, demosaicing,
resizing, color pipelines, local blur, natural-scene content, or human quality
judgments. Scores remain dependent on texture, contrast, resolution, border
handling, and implementation details.

## Project Structure

```text
.
├── .github/workflows/ci.yml
├── experiments/run_laplacian_variance.py
├── notes/laplacian-variance-blur.md
├── results/
│   ├── README.md
│   ├── laplacian_variance_summary.csv
│   └── laplacian_variance.png
├── src/research_notes/
│   ├── __init__.py
│   └── blur_metrics.py
├── tests/test_blur_metrics.py
├── LICENSE
├── README.md
└── pyproject.toml
```

## Roadmap

- Compare Laplacian variance with a first-derivative focus measure under the
  same controls.
- Add controlled motion blur and spatially localized blur.
- Study the effect of resizing and image resolution on metric comparability.

The roadmap is exploratory and does not represent completed work.

## License

Code and documentation are available under the [MIT License](LICENSE).
