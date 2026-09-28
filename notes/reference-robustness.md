# Persistent-Reference Robustness Benchmark

## 日本語概要

v0.84.0では、面・辺の対応付けを13条件で評価しました。拡大縮小、回転、寸法変更、格納順の変更、切断、修復、メッシュ作成、STEP再読込を試し、対応率と誤対応、保留、分割・結合・削除を分けて記録します。

重要な限界として、対称な箱を90度回転すると、見た目の形状は同じでも18個の面・辺のうち16個を幾何だけの照合が取り違えました。この結果も回帰試験に残します。詳細は英語本文に示します。

---

## English Summary

Thirteen controls score the existing reference policies under named
perturbations. Passing a case contract includes reproducing a documented wrong
match. This milestone evaluates robustness; it does not provide universal
persistent topology naming.

## Oracles and Scoring

The analytic box oracle labels faces and edges by area/length centroids on
authored boundary planes, independently of the tracker's vertex signatures.
Edit, exchange and tessellation-cache cases use these authored roles.
Reordering uses native subshape identity. Transform, Boolean and repair cases
use kernel operation ancestry, explicitly a scoped kernel oracle.

Every source face/edge receives an oracle target set. Asserted one-to-one,
split, merge and deletion relations are compared with that set. Ambiguity and
unresolved relations count as abstentions, not successful matches. The scorer
is tested with deliberately incorrect target IDs.

| Family | Observation |
| --- | --- |
| Scale 0.001 and 1000 | All 18 authored box references tracked with normalized roles |
| 37-degree rotation | Geometry policy abstains on all 18; operation history tracks all 18 |
| Symmetric 90-degree rotation | Geometry asserts 18 relations; 16 disagree with transform ancestry |
| Width edit / reordered faces | All 18 references agree with the declared oracle |
| Boolean split | 8 split relations among 18 source references |
| Boolean deletion | 5 deleted relations among 18 source references |
| Repair | 16 merges and 4 deletions among 30 source references |
| Tessellation cache / STEP exchange | 18/18 agree with analytic box roles |
| Coincident duplicate boxes | All 18 abstain as ambiguous |

## Reproduce

```bash
python experiments/run_reference_robustness.py
```

Or run `benchmark references` in the integrated terminal. See
[CSV](../results/reference_robustness.csv),
[HTML report](../results/reference_robustness.html) and
[per-reference evidence](../results/reference_robustness_evidence.json).

## Boundaries and Consequences

Operation ancestry is not an independent CAD implementation. Native indices
are local to the generated shape and stage. Truth covers the named edits,
not arbitrary geometry or design intent.

The tessellation case adds a mesh cache to a retained B-Rep. It does not rebuild
analytic surfaces from triangles. Reordering constructs a face compound and
does not claim a valid solid. Curved topology remains unqualified by the
existing planar/straight descriptor policy.

Geometric coincidence can be misleading when feature identity matters.
A workflow requiring identity through rotation must retain operation provenance
or request review; geometric similarity alone is insufficient evidence.
