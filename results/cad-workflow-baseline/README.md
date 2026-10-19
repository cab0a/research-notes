# v1.16 workflow baseline evidence

**Operator measurements and a real customer workbook are not available.**
This release implements timing/quality recording and verifies its arithmetic,
missing-value handling and separate machine observations. The field baseline
is still pending; SME benefit and adoption remain unevaluated.

## Evidence

- [unmeasured-session.json](unmeasured-session.json) and
  [unmeasured-report.json](unmeasured-report.json): empty seven-input reference,
  54 unrecorded phases, unknown total time and quality totals.
- [synthetic-session.json](synthetic-session.json) and
  [synthetic-report.json](synthetic-report.json): invented 180 + 60 + 100 second
  control, three explicit not-needed phases and deliberately nonzero errors.
  Not human timing, task outcomes or CAD extraction accuracy.
- [results.json](results.json): six accounting checks, 12 rejected inconsistent
  controls, seven inputs with two machine extraction runs each, data coverage,
  runtime and hashes.
- [verification.json](verification.json): test, CLI and package verification.

The input/definition reference is unchanged from
[v1.15](../../fixtures/cad-workflow-contract/README.md). No new STEP assets,
operator observations or customer data are introduced. Existing licenses and
independent recipe references remain in the source manifests. The bracket's
whole count stays unknown; the invalid transport control has no geometric count.
The authored plate variants share one family. This is not a blinded holdout.

## Protocol

One session fixes method, case order, anonymized operator reference and the
full contract/case definitions with SHA-256. Shared phases include input
preparation, truth labeling, setup, training and updates. Each part includes
input check, CAD open/check (or extraction/review), transfer, final check,
correction and rerun. Not-needed phases require reasons; missing or unfinished
phases keep the total unknown. Interrupted segments contribute known time and
can be completed later. Completed phases cannot be double-counted.

Quality values are operator-entered independent assessments, not automatic
grading or proof that the reported observations happened. Partial/unknown
truth cannot establish whole-part zero misses or false-completion counts.
Unknown parts stay in the planned denominator. Complete observation fields
do not imply successful work, customer acceptance or time savings.

Interactive timing uses a monotonic clock inside one process and excludes
explicit pauses. Wall-clock dates are metadata only. Stopwatch reports and
synthetic controls have different provenance. Sessions do not mix operators,
methods or repeated trials. Measurement order, learning, interruptions and
common-cost allocation must be planned before field evaluation.

Machine extraction seconds are separate observations of the existing software.
They must not be substituted for CAD inspection, transcription, independent
truth creation, setup, review or correction effort.

## Reproduction

From the repository root:

```bash
python -m research_notes.workflow_baseline report \
  results/cad-workflow-baseline/unmeasured-session.json \
  --output-dir output/workflow-baseline-unmeasured
python experiments/run_workflow_baseline_study.py \
  --output-dir output/workflow-baseline-study --repeats 2
python -m pytest -q
python -m pip wheel --no-deps . --wheel-dir output/workflow-baseline-wheel
```

Use `output/venv312/bin/python` in the prepared WSL geometry/test environment.
Synthetic observations and reference sessions are deterministic. Extraction
results must repeat; their timings/platform strings need not be identical.
The committed control plan is
[control-plan.json](../../fixtures/cad-workflow-baseline/control-plan.json).
Source/code hashes and result digests are in `results.json`. No external
service receives CAD, workbooks or logs from the recorder.

See the [Japanese guide](../../docs/cad-workflow-baseline.md) and
[research note](../../notes/cad-workflow-baseline.md).
