# Native SVG / DXF paired study

[manifest.json](manifest.json) references the unchanged native FreeCAD exports in
[the previous fixture set](../cad-drawing-exports/README.md). No raw drawing is
rewritten or regenerated here. There are nine conditions (five positive, four
withheld), each in two formats. Wrong projection reuses the one-hole drawing.

The eighteen context files contain only human assumptions and view selections.
For SVG, DrawingContent and three reviewed outline path ordinals replace the DXF
layer mapping. No dimensions or scale are supplied. The ordinal is within path
elements of the selected drawing group, zero based; it is a reference, not a
semantic meaning inferred from drawing order.

Selections are frozen in [prepare_cad_svg_pairs.py](../../experiments/prepare_cad_svg_pairs.py).
Ground-truth recipes and STEP stay in the previous evaluation directory and are
read by the evaluator only after interpretation and CAD generation.
The interpreter accepts bytes/context; it does not read paired DXF or source CAD.

Own authored drawings/contexts follow [PolyForm Noncommercial 1.0.0](../../LICENSE).
This set adds no external dataset, runtime, font or AI dependency.
These are development controls, not independent held-out engineering drawings.
[Results and method](../../notes/cad-svg-dxf.md).
