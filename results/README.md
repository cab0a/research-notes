# Reference Results

This directory contains the committed outputs of the v0.1.0 controlled
experiment. Both artifacts are generated exclusively from synthetic images by
`experiments/run_laplacian_variance.py`.

- `laplacian_variance_summary.csv` contains one row for each pattern, blur
  sigma, and noise standard deviation.
- `laplacian_variance.png` visualizes the aggregate blur response and the noise
  response for strongly blurred inputs.

Regenerate the artifacts from the repository root:

```bash
python experiments/run_laplacian_variance.py
```

The CSV is the numeric reference artifact checked by CI. CI also regenerates
the chart and verifies that a non-empty PNG is produced. PNG byte identity is
not asserted because font rasterization can differ across operating systems.
