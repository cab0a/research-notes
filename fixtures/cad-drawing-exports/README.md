# FreeCAD TechDraw fixed drawing exports

Own authored rectangular plates, one round through-hole family and controlled
annotation variants. Created by executing FreeCAD 1.1.4, not by manually composing
DXF or SVG to match the parser. No customer or third-party CAD datasets.

- [Authoring macro](../../experiments/export_freecad_drawings.FCMacro)
- [Freeze script](../../experiments/freeze_freecad_drawings.py)
- [Manifest and hashes](manifest.json)
- [CAD runtime/authoring log](authoring/export-log.json)
- [Reproduction](../../docs/cad-drawing-exports.md)

inputs/ contains the unmodified export bytes and human view/family/unit/projection
contexts. Eight source drawing configurations yield sixteen files. One additional
context intentionally assigns the wrong projection to the unchanged one-hole DXF.
No numeric dimensions or scale are included in the worker context.

authoring/ stores the eight FreeCAD native documents and the own authored blank
template. evaluation/ contains source STEP, design values and analytic truth.
Both are evaluation/authoring only; the reconstruction function and subprocess
receive drawing bytes and the limited human context. This is not an OS sandbox.

These are development controls (same base families and derivatives), not a
held-out benchmark or measurements on independently received business drawings.
SVG unsupported outcomes must not be counted as reconstruction accuracy.

Own models, drawings, template and code use the repository's
[PolyForm Noncommercial 1.0.0](../../LICENSE).
FreeCAD/ezdxf runtimes, fonts and third-party models are not redistributed here.
FCStd files contain the document and template, not the FreeCAD application.

FreeCAD AppImage SHA-256:
`f6dc6ba676e5ac96a565ebc8d657232f94c6158e85b4352141bd1a46f6b43434`.
Regeneration changes timestamps and may change bytes; normal reproduction uses
these frozen hashes. Do not overwrite the fixed evidence just to refresh dates.
