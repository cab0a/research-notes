# v1.15 research workflow reference definition

[reference-contract.json](reference-contract.json) fixes a single-solid part's
hole inventory -> existing table task. It declares 17 conditional fields,
source-coordinate conventions, unknown/zero/complete semantics, independent
truth, baseline methods, required time/error metrics and reference thresholds.
It is **not a customer-approved specification** or a workbook template.

[reference-cases.json](reference-cases.json) freezes seven definition and
field-convention controls. Source STEP files are referenced with SHA-256 rather
than copied or re-exported. Four complete plate controls use independent recipes
in [the original inventory manifest](../hole-inventory/manifest.json). The mixed
circle/slot control uses independent authored truth in
[the robustness manifest](../hole-robustness/manifest.json).

The public bracket's total hole count remains unknown. Its existing 5 round / 6
slot observations must not become whole-part truth. Its source and license stay
in [the public corpus](../public-step-corpus/README.md). `not STEP` is a literal
transport rejection control; no geometric hole count is assigned.

The authored plate variants share one family ID: translated geometry cannot be
randomly split into setup and evaluation as independent unseen parts. All seven
are development/reference controls, not a newly blinded holdout set. The new
case IDs, definitions and metadata are authored in this repository; existing
asset licenses continue to apply.

Research acceptance values are provisional for a fixed labeled evaluation set.
The 1e-6 mm numeric comparison tolerance is not manufacturing accuracy. Twenty
planned runs are a projection assumption, not measured operator trials. Metrics
are recorded per comparison method, including each method's setup and update
work. Unknown truth is retained and reported, not treated as zero or removed
silently from a business-completion denominator.

See the [Japanese guide](../../docs/cad-workflow-contract.md) and
[release study](../../notes/cad-workflow-definition.md). Reproduce using:

```bash
python -m research_notes.workflow_contract fixtures/cad-workflow-contract/reference-contract.json
python experiments/run_workflow_contract_study.py --output-dir output/workflow-contract-study
```
