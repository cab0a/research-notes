# Released recognition capability catalog — 2026-10-19

Interpretation, available APIs, limits and the next research decision:
[Japanese catalog](../../notes/released-recognition-catalog.md).

This study inventories existing functions before deciding what to implement.
It does not add or port a production recognizer.

## Evidence and scope

- [builtin-probe.json](builtin-probe.json): 30 bounded observations of existing
  smlibpy 0.3.5 APIs on seven inputs. All tasks completed. Completion is not a
  claim of perfect recognition accuracy.
- [builtin-matrix.csv](builtin-matrix.csv): every input/operation row, including
  zero results and overlapping feature selections.
- [quiddity-0.3.11-inventory.json](quiddity-0.3.11-inventory.json): 36 shipped
  capability families, entry points, record names and field names, read from the
  published wheel without executing the package. Families include derived
  patterns and stock/surface context, not just physical manufacturing features.
- [sources.json](sources.json): pinned source/package information, source hashes,
  predecessor audit reference, environment and evidence hashes.
- [verification.json](verification.json): code, artifact and authored-control
  checks. The existing production test suite was not rerun because production
  code, dependencies and old fixtures/results did not change.

The main release under investigation is NVIDIA USD BRep/SMLib 1.0.0 at
`c9c5979f04cea8c38213004d4f04df0dcfb40d05`. Added behavior in AWV smlibpy 0.3.5
is identified separately. ClassCAD and SolidCraft remain source/API reviews.
SMLib C++ analytic promotion and Quiddity recognition were not executed here.

## Built-in API probe

Run in Linux/WSL with the isolated smlibpy environment from the
[kernel comparison](../cad-kernel-choice/README.md). Override its interpreter
using `--smlibpy-python` if needed:

```bash
output/venv312/bin/python experiments/run_recognition_builtin_probe.py
```

Each observation is a new child process: address-space limit 4 GiB, CPU limit
20 seconds soft / 21 seconds hard, wall limit 30 seconds, no core dumps. Two
workers are used, with BLAS/OpenMP threads limited to one. Native output or
exceptions are retained; stale result files are deleted before each job.
This is a Linux resource-limit experiment, not a Windows-native runtime test or
a performance benchmark. One result per task is retained after the final code
was frozen; exploratory calls preceded it.

Seven inputs:

1. Box, round-hole plate and straight-slot plate, constructed independently in
   smlibpy using the prior [primitive helper](../../experiments/run_cad_kernel_probe.py).
2. Box with four vertical-edge radius-2 fillets.
3. Authored sheet folded by 90 degrees, inside radius 2 mm, thickness 2 mm and
   bend-axis length 40 mm.
4. The pinned public bracket and the existing NURBS-converted bore control.

Four operations per input: geometry/convexity selectors, fillet-face selection,
bends, and draft analysis. Parting-line analysis is also run on the box and
round-hole plate. The API performs recognition/analysis; no new hole, fillet or
bend detector is implemented by this script.

The authored folded sheet returns the expected bend dimensions and the filleted
box returns four selected faces. The slot-only plate also returns one selected
fillet face. The bracket returns 13 selected fillet faces and no bends. These
results demonstrate why geometric selectors cannot be silently interpreted as
complete manufacturing-feature classifications. No ground-truth total of
bracket fillets or bends is asserted.

Draft direction is +Z, with a one-degree threshold. A box's bottom face is
classified as `undercut` for that one direction; this does not prove the box
cannot be molded. Parting-line wire counts are not hole counts. The K-factor
0.44 is an input default, not inferred from the STEP.

This probe bypasses production STEP admission conditions and does not change
existing hole certification or review states. Imported sample attribution stays
in the [public corpus](../../fixtures/public-step-corpus/README.md); no new
derivative STEP is exported.

## Published-wheel inspection

Use the **0.3.11 wheel**, not a moving development checkout. Download it from
[the fixed PyPI release](https://pypi.org/project/quiddity/0.3.11/#files) into an
ignored output directory. For example, in an environment with pip:

```bash
python -m pip download --no-deps --only-binary=:all: --dest output/recognition-wheel quiddity==0.3.11
python3 experiments/inspect_recognition_distribution.py \
  output/recognition-wheel/quiddity-0.3.11-py3-none-any.whl \
  --sha256 950828b5f23b38ac1deb17bf9d478c15ba5c79b9c799b8bf5ebb6197dd332cdf \
  --output results/recognition-catalog/quiddity-0.3.11-inventory.json
```

The inspector verifies the wheel digest, reads METADATA and
`quiddity/capabilities.json`, and parses public exports with Python's AST.
It does not import the package, install its dependencies, execute recognizers
or extract untrusted paths into the workspace. All declared recognizer entry
points are checked against the shipped root module's imports.

The wheel metadata declares 0.3.11; the associated Git tag's pyproject declares
0.3.11.dev0. Shipped capability claims here come from the hashed wheel, not an
assumption that the development version is identical. The tag and source commit
are recorded as supplementary provenance.

## Source and licensing boundaries

The predecessor audit scanned public SMLib headers, smlibpy Python modules and
ClassCAD API documentation/types. This follow-up reads the implementations that
decide analytic promotion, curve predicates, fillet selection, bend inference,
draft classification, and the published recognition contract. Missing public
APIs are bounded negative findings, not proofs about private commercial code.

Two guessed documentation URLs returned 404; their correct paths
`/docs/sheet-metal/` and `/docs/analysis/` were subsequently retrieved. These
outcomes are retained and do not mean the functions lack documentation.

Only authored research code, observations and derived API facts are committed.
Third-party source bodies, wheels and ClassCAD API archives remain in ignored
output caches. Their licenses are separate: NVIDIA's relevant code is
Apache-2.0, smlibpy's own code MIT, Quiddity Apache-2.0, and ClassCAD engine use
has its own product conditions. This study does not activate a ClassCAD engine
or change this repository's [license](../../LICENSING.md).
