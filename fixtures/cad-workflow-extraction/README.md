# Existing-route workflow extraction controls — v1.17.0

[manifest.json](manifest.json) freezes ten known connector controls, with input
SHA-256, part-family and original truth/source references. The first seven reuse
the unchanged [v1.15 reference](../cad-workflow-contract/README.md).

Three additional existing assets exercise unqualified geometry (ellipse), a
two-solid published assembly with metre-to-mm context conversion, and rejected
missing-unit input. No new whole-count ground truth is assigned to them. Their
original sources remain in:

- [Hole robustness manifest](../hole-robustness/manifest.json)
- [Published STEP corpus and licenses](../public-step-corpus/README.md)
- [AP242 assembly controls](../ap242-assemblies/manifest.csv)

No STEP is copied, modified or re-exported. Existing source licenses continue
to apply. All authored plate variants share a family; these are development
controls, not blinded independent evaluation. The bracket's five circles and
six slots remain partial observations, not whole-part truth.

The study's `research-control:*` part references are explicit caller labels,
not drawing numbers inferred from CAD. Its baseline session has no operator
time, quality observations or real workbook. See the
[guide](../../docs/cad-workflow-extraction.md) and
[study](../../notes/cad-workflow-extraction.md).
