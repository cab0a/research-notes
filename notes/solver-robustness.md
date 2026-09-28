# Constraint-Solver Robustness Benchmark

## 日本語概要

v0.85.0では、スケッチと組立の拘束ソルバーを70条件で評価しました。初期値、座標スケール、重複・矛盾する拘束、特異に近い配置、小さな数値変動を試します。「計算が収束した」「正しい位置に来た」「解が一意である」を別々に判定します。

結果は正解との一致46件、残差は合格でも座標誤差が大きい13件、未収束5件、解が複数または連続的に存在する条件3件、矛盾検出2件、入力範囲外の拒否1件です。通常条件の検証とともに、接する円など特異に近い条件への弱さが見えるようになりました。解が左右対称に2つある条件では、一方が正しく求まっても「一意」とは扱いません。詳細は英語本文に示します。

---

## English Summary

Seventy deterministic cases evaluate the existing sketch and pose solvers
without changing their stopping tolerances. Independent analytic coordinates,
solution multiplicity and local rank evidence separate convergence from
correctness and uniqueness. All declared case contracts match, including
documented limitations.

## Controls and Independent Truth

Rectangle and circle controls use authored endpoint/center/radius answers.
Sketch coordinate scales span 1e-4 to 1e4. Circle cases add duplicate radius,
contradictory radii, a free center, a large translation and deterministic
radius perturbations of ±1e-10 mm.

The nonlinear sketch places a point at distance
`scale * sqrt(1 + height**2)` from two fixed centers at
`(-scale, 0)` and `(scale, 0)`. Its answers are
`(0, ±height * scale)`. Heights are 1, 1e-3, 1e-6 and 0;
scales are 1e-3, 1 and 1e3; positive, negative and central seeds are retained.
At zero height the tangent solution is singular. An analytic two-row position
Jacobian supplies additional singular-value evidence.

Assembly controls constrain a moving origin with three signed plane distances
and fixed rotations, while grounding the other component. Authored plane
normals and target position supply independent coordinate truth. Nearly
parallel normals at 1, 0.001, 0.000001 and 0 degrees test rank sensitivity.
Scale factors 1e-4, 1 and 100, two seeds, duplicates, conflicting distances,
a free translation and ±1e-9 mm RHS perturbations are included. The scale-1000
case is rejected because a distance exceeds the existing ±1000 mm input domain.

## Results

| Independent assessment | Cases | Meaning |
| --- | ---: | --- |
| Correct | 46 | A converged solution meets the analytic coordinate tolerance |
| Satisfied but inaccurate | 13 | Native residual tolerance passes; analytic coordinate tolerance fails |
| Not converged | 5 | The local iteration does not establish a solution |
| Non-unique | 3 | Feasible controls retain continuous freedom |
| Conflict detected | 2 | Contradictory affine/radius or duplicate-distance equations are detected |
| Input rejected | 1 | Input domain check prevents a solver run |

The 46 correct cases include mirror-branch problems. Their
`analytic_uniqueness` column remains `two_branches` even when the reported
local DOF is zero. The three `non_unique` assessments specifically describe
the continuous-freedom controls.

Coordinate correctness uses maximum error divided by the authored scale
≤ 1e-6. Assembly rotation matrices must additionally differ from identity by
at most 1e-7 in Frobenius norm. These are evaluation criteria, not revised
solver stopping tolerances or universal CAD tolerances.

For a unit-scale tangent sketch with a positive seed, residuals satisfy 1e-9
while the computed height remains about 2.51e-5 instead of zero. Small residuals
therefore do not certify accurate coordinates near singularity. The central
seed also exposes failure to escape a symmetric stationary configuration.

## Reproduce and Inspect

```bash
python experiments/run_solver_robustness.py
python -m pytest tests/test_robustness_studies.py -q
python -m research_notes.integrated_tool
```

Then run:

```text
benchmark solver
```

The terminal saves CSV, HTML, PNG and detailed evidence under its output
directory. See the committed [HTML report](../results/solver_robustness.html),
[CSV](../results/solver_robustness.csv) and
[residuals, solutions and truth](../results/solver_robustness_evidence.json).

Python callers can use
`research_notes.solver_benchmark.evaluate_solver_benchmark()`, which returns
rows, unrounded detailed observations and input records.

## Interpretation and Limits

Difficult cases explicitly allow non-convergence or inaccurate satisfied
solutions in the experiment contract. Exact CSV classifications freeze the
observed result; numerical evidence comparisons allow 1e-5 relative / 1e-10
absolute differences for finite-difference and BLAS arithmetic. Input fixtures
are exact. Small residuals and singular values are retained at ten significant
digits instead of being rounded to zero.

This is a measured baseline, not a new globally robust solver. Local numerical
rank is scale- and tolerance-dependent. Nonlinear failure does not prove
inconsistency, and zero local DOF does not establish global uniqueness.
Large assemblies, arbitrary CAD constraint systems and universal tolerance
selection are not validated. Solver normalization, better conditioning and
transactional recompute remain subsequent work.
