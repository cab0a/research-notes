# Native CAD drawing export experiment

[Open the offline HTML](report.html) · [Research note](../../notes/cad-drawing-exports.md)
· [Reproduction](../../docs/cad-drawing-exports.md)

FreeCAD 1.1.4 TechDraw exported eight own authored drawing configurations.
Original SVG/DXF bytes and evaluation-only source CAD are in
[fixtures](../../fixtures/cad-drawing-exports/README.md).

Seventeen inputs, each repeated twice:

- Five positive DXF conditions pass candidate execution, valid solid, STEP
  reimport, dimensional/volume/area/IoU/reprojection and edited-CAD checks.
- Four DXF negative conditions (including an intentionally wrong context)
  are withheld with their expected reason, with no candidate artifacts.
- Eight SVG exports remain unsupported; zero SVG reconstructions.

The result `passed` flag means each declared experiment expectation was met.
It does **not** turn unsupported SVGs into successful reconstructions.
Use `summary.by_format` and the per-trial interpretation status.

The viewer embeds drawings, actual B-Rep mesh previews and measurements.
DXF is rendered using ezdxf, separately from the paired native FreeCAD SVG;
neither renderer participates in inference. CAD cannot be recalculated in HTML.
Download links require the case directories beside the HTML.

Source truth is FreeCAD/OCCT 7.8.1; candidates/evaluation use OCCT 7.9.3.1.
This is not independent-kernel validation, customer drawing accuracy, a
held-out family benchmark, OCR or an AI comparison.

[All observations](results.json), [summary CSV](summary.csv),
[verification](verification.json) include code/input hashes, environment,
failure stages and executed checks. Own authored artifacts use the repository
license. FreeCAD/ezdxf binaries are not distributed.
