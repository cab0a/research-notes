# Native CAD drawings and bounded family controls

Own-authored FreeCAD 1.1.4 / TechDraw / OCCT 7.8.1 evidence.
The repository's PolyForm-Noncommercial-1.0.0 terms apply to our code and authored fixtures.
No customer drawings or externally licensed CAD dataset is included.

- inputs/: 11 actual exported CAD pages × SVG/DXF, raw bytes preserved; human context has no design dimensions.
- authoring/: source.FCStd documents, blank A3 page, FreeCAD version, independent parameters, dimension references.
- evaluation/: truth STEP, independently authored edited STEP, design parameters, measured authoring-CAD volume/area, hashes. Never reconstruction inputs.
- variants/: 10 explicitly derived SVG/context controls, not native exports or independent parts.
- manifest.json: expected status/reason, cohort, original hashes, provenance, authoring macro hash.
- baseline.json: unchanged previous implementation observations, including initial unseen settings.

Source macro: experiments/export_drawing_families.FCMacro.
Native freezing: experiments/freeze_drawing_families.py.
Derived controls: experiments/derive_drawing_family_controls.py.

The old-code baseline was observed before adaptation. After observing failures, all these samples are development data.
Only three of four initial unseen-setting inputs yielded old-parser candidates; full old-pipeline accuracy was not measured.

The outlined_text control uses Matplotlib TextPath and substituted **DejaVu Sans** outlines rather than the original FreeCAD font.
[DejaVu license](licenses/LICENSE_DEJAVU) is retained; no font binary is distributed.
This is an unsupported OCR case, not successful outlined-text recognition.

[Research](../../notes/drawing-families.md) / [Reproduction](../../docs/drawing-families.md).
