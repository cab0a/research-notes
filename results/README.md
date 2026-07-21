# Reference Results

This directory contains committed outputs generated exclusively from synthetic
images by the versioned experiment scripts.

- `laplacian_variance_summary.csv` contains one row for each pattern, blur
  sigma, and noise standard deviation.
- `laplacian_variance.png` visualizes the aggregate blur response and the noise
  response for strongly blurred inputs.
- `focus_metric_trials.csv` contains the 720 repeated v0.2.0 observations.
- `focus_metric_summary.csv` contains condition-level means, sample standard
  deviations, and p10, median, and p90 values for both focus measures.
- `motion_blur_summary.csv` contains the bounded horizontal-motion sensitivity
  experiment.
- `resize_sensitivity_summary.csv` contains the downscale-upscale sensitivity
  experiment.
- `focus_metric_comparison.png` compares normalized responses across the four
  v0.2.0 evaluations.

Regenerate the artifacts from the repository root:

```bash
python experiments/run_laplacian_variance.py
python experiments/run_focus_metric_comparison.py
```

All committed CSV files are numeric reference artifacts checked by CI. CI also
regenerates both charts and verifies that non-empty PNG files are produced. PNG
byte identity is not asserted because font rasterization can differ across
operating systems.
