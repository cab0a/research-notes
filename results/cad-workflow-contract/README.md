# v1.15 workflow definition evidence

This study fixes a research reference for one single-solid part's hole
inventory -> existing table workflow. It does **not** measure operator effort,
produce a customer workbook, predict suitability, or establish SME advantage.

## Committed evidence

- [reference-contract.json](reference-contract.json): canonical copy of the
  [fixture definition](../../fixtures/cad-workflow-contract/reference-contract.json).
- [contract-review.json](contract-review.json): definition check; a valid
  definition is not adoption or customer approval.
- [results.json](results.json): 11 invalid-definition controls, seven existing
  inventory inputs, two repeats per input, raw observations, runtime and hashes.
- [sources.json](sources.json): five primary-source URLs, versions, retrieval
  scope and SHA-256, plus references to previous kernel/recognition evidence.
- [verification.json](verification.json): test, CLI and wheel verification.

## Protocol and boundaries

The fixture defines 17 conditional fields, source coordinates, unknown/zero
semantics, independent truth, quality-matched baselines and setup-inclusive time
metrics. Deliberate mutations check unknown/unanalysed -> zero, partial ->
complete, omitted whole counts, origin/unit errors, circle/slot field confusion,
recognizer-as-truth, part-family leakage, omitted review time and invented
customer agreement. All 11 must be rejected at the expected definition path.

The seven input controls are frozen in
[reference-cases.json](../../fixtures/cad-workflow-contract/reference-cases.json).
Four complete plate inventories are compared to independent authored recipes;
the remaining controls check partial/unknown and rejected/unknown handling.
The mixed plate has an independently known total of two, but the existing
inventory still withholds whole-part completeness. The bracket's five circles
and six slots are not whole-part ground truth. No source STEP is copied,
modified or re-exported. Original source licenses continue to apply; see the
[fixture README](../../fixtures/cad-workflow-contract/README.md).

All controls are known development/reference inputs. Translated and related
authored plates share one family ID. This is not a blinded holdout or a claim
of 100% extraction accuracy. Runtime seconds exclude operator effort and must
not be reported as business time savings.

The zero-error thresholds and 1e-6 mm comparison tolerance are reference
criteria, not achieved customer acceptance or manufacturing accuracy. Twenty
planned runs are a projection assumption. Each comparison arm must include its
own setup, execution/operator work and updates. Customer workbook, mappings,
coordinate conventions, quality/time targets and data-use conditions remain
pending agreement.

## Reproduction

From the repository root with the geometry/test environment installed:

```bash
python -m research_notes.workflow_contract \
  fixtures/cad-workflow-contract/reference-contract.json \
  --output-dir output/workflow-contract-definition
python experiments/run_workflow_contract_study.py \
  --output-dir output/workflow-contract-study --repeats 2
python -m pytest -q
python -m pip wheel --no-deps . --wheel-dir output/workflow-contract-wheel
```

The prepared WSL interpreter is `output/venv312/bin/python`. Repeated inventory
results must match; timings and platform strings need not be identical. Input,
definition, experiment and recognizer hashes are recorded in `results.json`.
Canonical JSON uses sorted keys, UTF-8, finite numbers and one trailing newline.
Its SHA-256 is independent of original key ordering/indentation. Prior-art HTML
caches are ignored local artifacts under `output/`; no vendor article content
is redistributed as committed evidence.

See the [research note](../../notes/cad-workflow-definition.md) and
[CLI/Python guide](../../docs/cad-workflow-contract.md).
