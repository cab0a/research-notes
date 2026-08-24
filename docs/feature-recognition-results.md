# Rule-Based B-Rep Feature Recognition Results

## 日本語概要

本書は、v0.40.0の形状特徴候補認識を短時間で確認するための補助文書です。9個の合成立体、構築直後とSTEP再読込後の14候補、分類・寸法の全件一致、負例の誤検出0件、異なる作成経路が同じ最終境界を持つ比較を図と表で示します。通常は完全な結果を研究ノートへ集約しますが、今回は結果確認用の一回限りの案内を特例として追加します。方法と限界は以下の英語本文および完全な研究ノートを参照してください。

---

## English Summary

This document is a reader-facing digest of the v0.40.0 controlled evaluation.
It connects the two generated figures to the exact result tables, recognition
evidence, and claim boundaries. The canonical study remains the
[complete research note](../notes/rule-based-brep-feature-recognition.md).
The full reader-facing explanation is also committed as a
[Japanese-language companion](feature-recognition-results-ja.txt).

## Documentation Exception

Repository studies normally keep the complete technical narrative in one
research note and use indexes only for navigation. This one-release digest is
an explicit exception requested to make the v0.40.0 evidence easier to inspect.
It does not replace the research note, create a second source of truth, or
extend any experimental claim. The Japanese companion uses a plain-text file
with Markdown notation so the repository-wide bilingual Markdown contract
remains enforceable without shortening the requested Japanese account.

## Evaluation Scope

The experiment asks whether surface attributes and face adjacency are enough
to recognize a deliberately bounded set of geometric candidates:

- through and blind cylindrical holes;
- an open planar step;
- a through slot with semicircular ends;
- chamfer-like planar faces; and
- a constant-radius fillet-like face.

All inputs are synthetic. Each positive and negative control has independently
declared classification and dimension truth. Every shape is evaluated after
construction and after STEP exchange through the selected geometry-kernel
route.

![Nine synthetic feature and confounder controls](../results/feature_recognition_shapes.png)

| Synthetic control | Declared truth | Expected candidate |
| --- | --- | --- |
| Plain block | `12 x 8 x 6` block | None |
| Through hole | Radius `1.25`, depth `6` cylindrical subtraction | Through hole; diameter `2.5`, depth `6` |
| Blind hole | Radius `1`, depth `3.5`, planar bottom | Blind hole; diameter `2`, depth `3.5` |
| Open step | Two horizontal levels and one connecting riser | Open step; height `2`, width `8` |
| Through slot | Radius `1`, center distance `4`, depth `4` subtraction | Through slot; width `2`, total length `6`, depth `4` |
| Operation-made chamfer | Symmetric distance-`1` chamfer on an edge of length `8` | Chamfer-like; size `1`, angle `45°` |
| Direct-profile bevel | Extruded profile with the same final boundary as the chamfer control | Chamfer-like; size `1`, angle `45°` |
| Constant-radius fillet | Radius `1` fillet on an edge of length `8` | Fillet-like; radius `1`, length `8`, angle `90°` |
| External cylindrical boss | Radius `1.25` cylinder added to a block | None |

## Recorded Results

![Candidate counts and recovered dimensions](../results/feature_recognition.png)

| Evidence | Recorded result |
| --- | ---: |
| Synthetic solids | 9 |
| Constructed-stage candidates | 7 |
| STEP-imported candidates | 7 |
| Classification matches | 14 / 14 |
| Dimension matches | 14 / 14 |
| Negative-control false positives | 0 |
| Face-attribute rows | 136 |
| Face-adjacency rows | 282 |
| Control/stage observation rows | 18 |
| Equivalent-boundary comparison rows | 2 |
| Maximum controlled-truth length error | `3.9612757518625585e-13` model units |
| Maximum controlled-truth angle error | `5.8832938520936295e-12°` |
| Candidates proving design intent | 0 |

The seven positive controls are classified consistently at both stages, and
all registered dimensions satisfy the experiment's declared comparisons. The
plain block and the external cylindrical boss remain negative. These values
are regression evidence for this fixed corpus and one selected kernel route;
they are not manufacturing tolerances or general quality thresholds.

## Recognition Evidence

### Hole candidates

The recognizer first requires a full-period cylindrical face. It then uses
radial normal polarity to distinguish material-facing cavity geometry from an
outward cylindrical boss. A planar circular cap adjacent to the cylinder
separates the controlled blind-hole case from the through-hole case.

### Step candidates

Two parallel planar levels and a planar riser adjacent to both levels form the
controlled open-step subgraph. Level separation gives the height. Riser area
divided by height gives the controlled width.

### Slot candidates

The controlled slot requires two inward-facing partial cylinders of equal
radius connected through planar side faces. Cylinder radius, axis separation,
and side-face area provide width, total length, and depth evidence.

### Chamfer-like candidates

A diagonal planar face must share edges with exactly two nonparallel parent
planes. The rule uses both normals and shared-edge evidence so that extrusion
end caps are not mistaken for the two planes bridged by the diagonal face.

### Fillet-like candidates

A partial constant-radius curved face must share edges with two nonparallel
radial parent planes. Axial end caps are excluded. Radius, area, and the
longest boundary edge support the controlled radius, length, and angle values.

## Why the Result Says `Chamfer-Like`

The experiment compares an operation-made chamfer with a directly extruded
bevel profile. Their construction labels differ, but their checked final
boundaries agree at both the constructed and STEP-imported stages.

| Boundary observation | Operation-made chamfer | Direct-profile bevel |
| --- | ---: | ---: |
| Vertices | 10 | 10 |
| Edges | 15 | 15 |
| Faces | 7 | 7 |
| Shells | 1 | 1 |
| Solids | 1 | 1 |
| Volume | `572` | `572` |
| Forward Boolean difference volume | `0` | `0` |
| Reverse Boolean difference volume | `0` | `0` |

The same boundary supports the same geometric candidate even when it came from
a different modeling sequence. Boundary geometry therefore supports
`chamfer-like`, but it does not prove that a chamfer operation was used, recover
design history, or establish manufacturing intent.

## Interpretation

- Surface type alone does not separate a cylindrical hole from an external
  boss; orientation and material-side evidence are necessary.
- A feature candidate is usually a connected subgraph of faces and shared
  edges, not a label attached to one face.
- Analysis-local face indices are identifiers for reporting, not semantic
  evidence. Normals, curvature, boundaries, and adjacency carry the evidence.
- The selected candidates and dimensions survive STEP exchange for these nine
  controls.
- Geometrically equivalent final boundaries do not reveal which modeling
  operation produced them.

## Limitations

- Features are isolated; interacting or overlapping candidates are not tested.
- Controls are axis-aligned synthetic solids with fixed dimensions.
- Countersinks, counterbores, conical holes, threads, pockets, islands, ribs,
  draft, undercuts, and variable-radius fillets are outside the corpus.
- The chamfer has one symmetric `45°` condition, and the fillet has one
  constant-radius `90°` condition.
- Representative curvature samples do not prove continuity over an entire
  face.
- Tool accessibility, stock, process order, manufacturability, and design
  intent are not evaluated.
- Only one geometry-kernel and STEP-import route is evaluated.
- No external production CAD data is used, so dataset-level generalization is
  not established.

## Evidence Files

- [Feature candidates and recovered dimensions](../results/feature_candidates.csv)
- [Face attributes](../results/feature_face_attributes.csv)
- [Face adjacency](../results/feature_adjacency_edges.csv)
- [Control-stage observations](../results/feature_recognition_observations.csv)
- [Equivalent-boundary observations](../results/feature_equivalent_boundary_observations.csv)
- [Summary](../results/feature_recognition_summary.csv)
- [Machine-readable evaluation contract](../results/feature_recognition_contract.json)
- [Complete research note](../notes/rule-based-brep-feature-recognition.md)

## Reproduction

```bash
python -m pip install -e ".[geometry,test]"
python experiments/run_feature_recognition.py
python -m pytest tests/test_feature_recognition.py
```

The experiment deterministically regenerates the CSV, JSON, PNG, and STEP
artifacts. The dedicated v0.40.0 test module contains 15 tests; the recorded
v0.40.0 repository suite contains 298 tests.
