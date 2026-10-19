# v1.17 existing-route workflow extraction evidence

This release connects one existing STEP/OCCT inventory route to the v1.15
workflow fields and optionally binds it to a v1.16 extraction-method case.
It does not add recognition algorithms, workbook transfer, workflow
suitability/completion decisions or measured operator savings.

## Evidence

- [results.json](results.json): ten known inputs, two runs each, provenance
  checks, timings, seven previous-result comparisons, source/code hashes.
- [reference-baseline-session.json](reference-baseline-session.json): frozen
  extraction-side session with no operator timings, quality records or real
  workbook. Its ID/time are reference metadata, not a human observation.
- [observations](observations): one full connector report per input, retaining
  contract, raw inventory JSON, normalized fields and local source pointers.
- [verification.json](verification.json): tests, installed CLI and wheel checks.

The [manifest](../../fixtures/cad-workflow-extraction/manifest.json) reuses seven
v1.15 controls and adds an existing ellipse, a published two-solid assembly and
a missing-unit control. No STEP asset is copied/changed/re-exported, and no new
whole-count ground truth is assigned to the three added controls. Original
sources/licenses remain in the
[fixture README](../../fixtures/cad-workflow-extraction/README.md).

## Protocol and boundaries

Every call uses `hole_inventory.analyze_step` once with public inspection,
circles+slots and no preview. All geometry/qualification rules remain unchanged.
The report retains the source SHA-256 and canonical raw result, mm conversion
contexts, measured shape metrics, runtime and six selected implementation
hashes. These are not a full environment/dependency attestation.

Five summary and twelve per-feature fields implement the reference definitions.
Every value points into the retained snapshot/caller input. XYZ composition and
sole-solid ownership derivation are explicit operations. Missing information,
non-applicable dimensions and omitted caller references remain distinct.
The 242 checked cells include missing/non-applicable states; they are not 242
independently measured dimensions or recognized features.

Baseline binding requires the same contract and source hash, a planned case ID
and the extraction+full-review method. It never changes the session or silently
records machine execution as human timing or independent quality assessment.

Results excluding extraction time must match on repetition. All 17 reference
fields must be represented for each recognized feature, and every provenance
pointer/operation must reproduce its value. The seven previous raw inventory
results must equal the committed v1.15 observations. Observed states are four
complete, two partial, two unresolved and two rejected. The public bracket's
five circles and six slots still do not certify its whole count.

These are known development controls, not blinded accuracy/eligibility tests.
Operator time, manual error rates, customer workbook/acceptance and SME
advantage remain unevaluated. Presence of a field is not permission to use it
automatically in a business workflow. Native SMLib/SolidCraft/ClassCAD input
routes are not connected in this version.

## Reproduction

From the repository root with the geometry/test environment installed:

```bash
python -m research_notes.workflow_extraction \
  fixtures/public-step-corpus/sources/build123d_bracket.step \
  --contract fixtures/cad-workflow-contract/reference-contract.json \
  --output-dir output/workflow-extraction-bracket
python experiments/run_workflow_extraction_study.py \
  --output-dir output/workflow-extraction-study --repeats 2
python -m pytest -q
python -m pip wheel --no-deps . --wheel-dir output/workflow-extraction-wheel
```

Use `output/venv312/bin/python` in the prepared WSL environment. Timings and
platform/package metadata may differ across environments. Source hashes are
frozen; canonical JSON uses finite values, sorted keys, UTF-8 and a trailing LF.
See the [guide](../../docs/cad-workflow-extraction.md) and
[research note](../../notes/cad-workflow-extraction.md).
