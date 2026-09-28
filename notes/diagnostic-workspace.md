# Diagnostic Modeling Workspace

## 日本語概要

v0.88.0では、面・辺を選択できる3D診断画面を追加しました。出所、変更状態、依存関係、拘束の状態、再構成候補、編集前後の体積・面積をまとめて確認できます。画面は検査用スナップショットで、編集はPython APIまたはターミナルで行います。9条件を検証しました。詳細は英語本文に示します。

---

## English Summary

Can a diagnostic view make the selected shape, its provenance and pending
changes distinguishable? A standalone HTML page combines a rotatable mesh,
face/edge selection, source digest and revision token, feature dependencies,
profile constraint status, candidate residuals and before/after measurements.
No network or browser library is required.

## Recorded Scenario

The fixed through-hole source has two reconstruction hypotheses. After explicit
selection of `through_hole`, radius 1.3 mm is staged and committed. The view
contains seven faces and fifteen edges. Volume changes from 467.433629 to
458.762834 mm³, a difference of -8.670796 mm³. The view shows the base, feature
and result dependency chain, plus fully constrained base and hole sketches.

A radius of 30 mm then aborts recomputation. A new snapshot identifies its
geometry as `retained_committed_not_draft`, keeps the previous volume and exposes
failed/stale attempted nodes. Profile constraint satisfaction does not imply
that the proposed feature fits inside the solid.

Nine controls cover face and edge counts, source/revision binding, dependencies,
constraints, competing candidates, geometric change, mesh IDs and failed-state
labeling. Browser checks exercise face selection, edge selection, rotation and
reset. Tests also verify that meshing cannot mutate committed geometry and
hostile source names remain escaped data in HTML.

## Scope

Face/edge numbers are analysis-local IDs bound to one source digest and model
revision. They are not STEP entity IDs or persistent topology names. Supporting
faces in the candidate table refer to the imported geometry, not edited faces.
Edge curves are sampled at 25 parameter positions; the triangle display is
diagnostic, without certified screen-space error or exact occlusion guarantees.

The page is read-only. It cannot modify dimensions, solve constraints or export
edited geometry by itself. The versioned Python API and terminal reproduce the
underlying actions without using the view. A JSON sidecar preserves the exact
snapshot data. A generated view does not claim recovered design history.

## Reproduce and Inspect

```bash
python experiments/run_diagnostic_workspace.py
```

- [Interactive reference view](../results/diagnostic-workspace/workspace.html)
- [Snapshot JSON](../results/diagnostic-workspace/workspace.json)
- [CSV](../results/diagnostic_workspace.csv)
- [Detailed committed/failed records](../results/diagnostic_workspace_evidence.json)
- [Implementation](../src/research_notes/diagnostic_workspace.py)
- [API and terminal instructions](stable-cad-api.md)
