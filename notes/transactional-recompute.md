# Transactional Recompute and Rollback

## 日本語概要

v0.86.0では、寸法の変更を仮状態に保存し、モデル全体の再計算が成功したときだけ確定する仕組みを追加しました。失敗した枝と、その影響を受ける枝を記録し、最後に成功した形状を保持します。組立でも、部品・配置・干渉検査をまとめて判定します。14条件が期待した結果と一致しました。詳細は英語本文に示します。

---

## English Summary

Can a failed feature or assembly recomputation expose a partly updated model?
Two explicit transaction boundaries prevent publication of intermediate work:
every node in a feature DAG, or every component, placement and interference
check in an authored assembly. A successful independent branch in a failed
transaction is diagnostic evidence, not a published result.

## Method and Findings

The six-node branching plate separates a through-hole/boss path from a spare
rib path. A radius change from 1 to 1.5 mm commits; cold recomputation gives the
same volume. A radius of 30 mm fails while an independent rib-height edit can
succeed. Neither branch is published. Descendants retain explicitly stale
states, and the committed model and native shapes remain unchanged.

The two-block assembly commits zero clearance as contact. A clearance of
-1 mm produces interference, aborts publication and retains the contact state.
Rollback restores the last commit or a named retained checkpoint. Revision
tokens change after edits, attempts and rollback, preventing a stale token
from becoming valid again when returning to old dimensions.

Fourteen recorded cases cover initialization, staging, pending-output refusal,
commit, cold comparison, atomic abort, independent branch isolation, rollback,
checkpoint restoration, stale-token rejection, invalid input, assembly contact,
interference and rollback. Additional tests inject native failures, mutate a
copied vertex tolerance and exercise checkpoint eviction and failed side branches.

## Interface and Boundaries

`TransactionalModel` defaults to 16 checkpoints (configurable from 1 to 64).
`TransactionalAssembly` retains at most 16. The bounded Python facade uses the
default limit. Native recomputation receives copied geometry so a candidate
cannot mutate the published cache. Unexpected exceptions record an aborted
attempt and propagate without replacing the commit.

`current()` refuses a pending draft. Diagnostics can still display the last
commit with an explicit retained-state label. Checkpoints exist only in memory;
there is no disk journal, process-crash recovery or multi-process concurrency
control. Public `CadWorkspace` exposes data records rather than native shapes.
Earlier low-level incremental recompute functions retain their historical behavior.

## Reproduce and Evidence

```bash
python experiments/run_transactional_recompute.py
python -m pytest tests/test_operational_studies.py -q
```

- [Input model and manifest](../fixtures/transactional-recompute/manifest.csv)
- [CSV](../results/transactional_recompute.csv)
- [Detailed records](../results/transactional_recompute_evidence.json)
- [HTML report](../results/transactional_recompute.html)
- [Implementation](../src/research_notes/transactional_recompute.py)

The experiment builds on the repository's [deterministic recompute study](dependency-graph-deterministic-recompute.md)
and authored [assembly recompute implementation](../src/research_notes/assembly_recompute.py).
