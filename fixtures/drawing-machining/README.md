# Machining drawing development examples

Own FreeCAD 1.1.4 TechDraw exports, under the repository's PolyForm Noncommercial 1.0.0.
No third-party dataset or runtime is redistributed.

- `authoring-specs.json`: authoring/evaluation only; not reconstruction input.
- `inputs/`: actual SVG/DXF and nonnumeric view/family contexts.
- `evaluation/`: independent authoring STEP, edited STEP, nominal parameters and hashes.
- `authoring/`: native FCStd and FreeCAD export log.
- `manifest.json`: input/context SHA-256 and provenance.
- `protocol.json`: requested scope and explicit absence of test-suite execution.

Ten own-authored pages are development examples, not a held-out benchmark.
Three pages deliberately omit depth, give a conflicting quantity, or contain unsupported fit notation.
Each SVG/DXF is executed once in the recorded completed demonstration.
No tests were added or run. This does not establish regression safety or generalization.

See [research note](../../notes/drawing-machining.md) and [execution guide](../../docs/drawing-machining.md).
