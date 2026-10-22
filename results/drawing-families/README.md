# Drawing families: fixed observations

[Offline HTML](report.html) / [Research](../../notes/drawing-families.md) /
[Reproduction and human review](../../docs/drawing-families.md).

2026-10-22, 32 inputs × 2 runs = 64 trials:
- 21 positive inputs pass code execution, solid/STEP, dimensions, analytic area/volume, truth IoU, HLR and edited-CAD checks.
- 11 negative inputs withhold with the specified reason; no false confirmations on these controls.
- Eight positive native SVG/DXF pairs agree in parameters and original/edited volume IoU 1.0.
- Three negative native pairs agree in dimension_missing.
- Outline/tspan controls, shared hole positions, quantities and changed export settings are explicitly separated.
- Human roles/projection/family assumptions remain. Same exporter, authored development data, same OCCT kernel family.
- review-correction/ contains a context downloaded from the actual HTML after correcting a swapped view mapping and the actual CLI-generated STEP.

The rendering meshes come from the STEP-reimported B-Rep.
The paired SVG shown on DXF cases is display-only and never input to DXF reconstruction.
The HTML supports context JSON download; CAD calculation happens separately in the CLI.
No external assets/network are required to view the HTML.

results.json holds all metrics, per-trial failures, thresholds and environment/source fingerprints.
summary.csv is the case summary.
verification.json audits frozen bytes, linked artifacts and the actual test run.
browser-check.json records the actual browser operations, distinct from participant usability testing.

Raw CAD exports preserve bytes; STEP result headers can contain environment/time-dependent information.
Reproduction compares numerical metrics and classifications, not byte-identical regenerated STEP files.
