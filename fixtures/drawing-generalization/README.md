# Frozen drawing generalization evidence

Own-authored drawings; PolyForm-Noncommercial-1.0.0 (repository terms).
No customer files, paid CAD assets, external training dataset, font binary or
CAD runtime is redistributed. FreeCAD/LibreCAD are external tools, not copied
into this repository. Native export bytes and FCStd documents are preserved.

- `protocol.json`: scope, seed, baseline hashes, preregistered acceptance rules.
- `development-specs.json`: six pocket configurations for developing the policy.
- `holdout-specs.json`: 24 new configurations in four known families; six each.
- `engine-freeze.json`: source SHA-256 and UTC time recorded after the 21
  development tests and **before generating** the holdout drawings. No inference
  changes after the holdout observations. Generated examples do not constitute
  a family/customer/exporter-independent test set.
- `development/`, `holdout/`: actual FreeCAD 1.1.4 TechDraw SVG/DXF,
  source FCStd, authoring/export logs and separate evaluation-only truth STEP.
  Context specifies only unit, projection, family and human-confirmed view roles.
  It contains no design dimensions, scale, opening direction or truth path.
- `development/inputs/*/section.svg`: actual CAD slice contour, exported by TechDraw;
  human-confirmed X-normal plane through pocket center and Y-right/Z-up axes.
  This is not automatic interpretation of section labels/hatching.
- `solid_lines` cases: explicitly derived SVG controls with dash style removed;
  `native-drawing.svg` preserves the unmodified export. DXF already lost line types.
- `portability/`: LibreCAD 2.2.1.5 CLI imported previous FreeCAD DXF and re-exported
  SVG. Four source parts, two resolution flags, **four unique SVG hashes**.
  This is a second 2D CAD export path, not native drafting in a different 3D CAD.
  Dimension layers are empty and no XML dimension text is present. Do not infer
  that an OCR pass could restore annotations that the exporter omitted.

Truth STEP and numeric authoring specs are only evaluator inputs. Workers get
copied drawing/context and optional section files with neutral filenames.
Separate processes are an evidence-flow boundary, not a filesystem security sandbox.
The new interpreter never opens truth/manifest/authoring files. The baseline
decision in each manifest is recorded with unchanged a32ed76 family code.

Authoring/replay commands and pinned external sources:
[reproduction](../../docs/drawing-generalization.md).
