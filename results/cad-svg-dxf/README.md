# Native SVG / DXF equivalence evidence

[Open the offline HTML](report.html). [Study](../../notes/cad-svg-dxf.md) /
[reproduction](../../docs/cad-svg-dxf.md).

- 9 paired conditions, 18 inputs, each repeated twice.
- 5 positive pairs: both formats produce valid editable STEP; extracted parameter
  differences are zero; original and edited pair IoU are 1.0.
- 4 negative pairs: both formats withhold with matching reasons; no false confirmation.
- Native cubic SVG contours are sampled separately from fitted exact circles.
  Maximum native-contour/HLR sampled residual is approximately 0.00167841 mm.
- Raw exported input bytes are preserved. Source/truth hashes, runtime, trial
  failures and thresholds are in [results.json](results.json).
- [pairs.csv](pairs.csv) compares the formats; [summary.csv](summary.csv) lists cases;
  [verification.json](verification.json) records test, link and artifact checks.

Truth and output use different OCCT versions but the same kernel family.
Own authored development controls only; no customer drawing, general SVG,
held-out benchmark, native Windows or AI comparison claim.
