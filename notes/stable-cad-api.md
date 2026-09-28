# Stable Bounded Python CAD API

## 日本語概要

v0.87.0では、STEP読込、候補確認・明示選択、寸法変更、再計算、取り消し、比較、出力を扱うPython APIの契約1.0を固定しました。古い状態に対する操作、未確定の形状出力、入力容量の超過などを識別できます。17条件を検証しました。プロジェクト全体のv1.0到達を意味するものではありません。詳細は英語本文に示します。

---

## English Summary

`research_notes.cad_api.CadWorkspace` is a bounded public facade over inspection
and confirmed reconstruction. API version `1.0.0` freezes method inputs, result
envelopes, status names, error codes and declared limits. Operation-specific
diagnostic `data` may gain fields; private objects and all older research
modules are outside this interface contract. The project version is v0.90.0.

## Contract

Every successful call returns `APIResult`: `api_version`, `operation`, `status`,
`revision_token`, `data`, `warnings`. `record()` produces a JSON-compatible
mapping. Statuses distinguish `ok`, `partial`, `abstained`, `staged`,
`committed` and `aborted`; an aborted recomputation is a normal diagnostic result.

`CadAPIError` records `api_version`, `status=error`, `code` and `detail`.
Codes include invalid requests, stale revisions, missing explicit confirmation,
resource limits, missing source/model, pending changes, I/O and native runtime
failures. Diagnostic text is not a parsing contract. Programming defects or
unexpected foreign exception types may propagate; state publication still
remains atomic. The [contract fixture](../fixtures/stable-cad-api/api_contract.json)
records exact signatures and supported names.

`open_step` defaults to inspection. Reconstruction must be requested, and every
candidate selection requires `confirm=True`. All mutating model operations
require the latest opaque token. A failed open or failed candidate initialization
retains the current workspace. Opening a successful new source replaces it.

Limits include 2 MB source acquisition, 64 model nodes, 16 checkpoints, and
diagnostic views with at most 256 faces, 512 edges and 60,000 triangles. These
are bounded input/output contracts, not hard native CPU/RAM isolation.

## Try It

From the repository root, with the geometry dependencies installed:

```bash
python examples/cad_workspace.py --output-dir output/cad-demo
python -m research_notes.cad_tool
```

At the `cad>` prompt, inspect the displayed candidates before confirming one:

```text
open fixtures/step-reconstruction/through_hole.step
candidates
select 2 --confirm
set feature radius 1.3
recompute
compare
workspace
export output/cad-demo-edited.step reconstruct
set feature radius 30
recompute
rollback
```

In the pinned sample, candidate 2 is `through_hole`; the other candidate is
`profile_hole`. Candidate numbering belongs to the displayed list, not the API
contract. Python selects a specific candidate ID after inspecting its explanation.
The terminal automatically uses the latest token in its own workspace.
`python -m research_notes.integrated_tool` exposes the same commands as
`cad open ...`, `cad set ...`, and so on, in a separate transactional session.
Existing top-level commands retain their previous semantics.

The [runnable Python example](../examples/cad_workspace.py) demonstrates explicit
selection, token use, staged edits, checking commit status, comparison, HTML
creation and STEP export. It requires `--overwrite` to replace its prior STEP.

## Findings and Reproduction

Seventeen cases verify normal calls, confirmation refusal, stale tokens, pending
comparison/export refusal, failed-open retention, source byte limits and
inspection-mode abstention. Imported geometry does not imply editable history.

```bash
python experiments/run_stable_cad_api.py
```

- [CSV](../results/stable_cad_api.csv)
- [HTML report](../results/stable_cad_api.html)
- [Implementation](../src/research_notes/cad_api.py)
- [Transaction policy](transactional-recompute.md)
- [Writer policy](step-writer-modes.md)
