# Rule-Based B-Rep Feature Recognition: Geometry, Adjacency, and Intent Boundaries

## 日本語概要

本研究は、通常の直方体、貫通穴、止まり穴、段差、貫通溝、面取り操作、同じ最終境界を直接作った斜面、丸み操作、円筒突起の9形状を合成し、面の支持曲面、法線、曲率、境界、隣接関係から幾何特徴候補を抽出します。面取りと丸みでは候補面が実際につなぐ2親面を法線と共有辺で固定しました。構築時とSTEP再読込時の各7候補は分類と登録済み寸法に一致し、長さ系誤差は最大3.96e-13、角度誤差は最大5.88e-12度です。操作面取りと直接斜面は両方向の差分体積0、同じ位相・体積572ですが、設計履歴や加工意図は証明しません。英語本文で証拠と限界を説明します。

---

## English Summary

Nine synthetic solids test deterministic rules over an attributed B-Rep face
adjacency graph. The rules recover one through hole, one blind hole, one step,
one through slot, two chamfer-like boundaries, and one constant-radius
fillet-like boundary before and after STEP exchange. A plain block and an
external cylindrical boss produce no target candidates. An operation-built
chamfer and a directly extruded equivalent bevel deliberately receive the same
geometric label but different known construction labels. Their topology,
volume `572`, and zero bidirectional difference volumes verify the controlled
boundary equivalence. Every observed dimension is compared with preregistered
truth, while final boundary geometry still does not prove design history or
manufacturing intent.

## Research Question

Can isolated holes, steps, slots, chamfer-like faces, and fillet-like faces be
recognized reproducibly from evaluated B-Rep geometry and face adjacency while
keeping geometric candidates separate from construction history and design
intent?

## Background

Feature recognition commonly represents B-Rep faces as attributed graph nodes
and shared edges as graph relations. The primary work by Joshi and Chang
introduced an attributed adjacency graph for recognizing selected polyhedral
machining features. This experiment follows the graph principle but makes a
smaller claim: it recognizes five geometric candidate families in nine fixed
synthetic controls. It does not determine machining accessibility, stock,
tooling, process sequence, or designer intent.

The selected backend exposes the required observations. OCCT's
[`TopExp`](https://dev.opencascade.org/doc/refman/html/class_top_exp.html)
maps subshapes and ancestors;
[`BRepAdaptor_Surface`](https://dev.opencascade.org/doc/refman/html/class_b_rep_adaptor___surface.html)
classifies and evaluates face support surfaces; and the
[`GeomLProp_SLPropsBase`](https://dev.opencascade.org/doc/refman/html/class_geom_l_prop___s_l_props_base.html)
interface provides local normals and curvatures. The construction truth uses
documented Boolean, chamfer, and fillet operations, but the recognizer does not
consume those operation labels.

## Method

### Attributed face graph

Each face node records surface type, exact-surface area and centroid,
orientation-adjusted representative normal, parameter spans, analytic cylinder
axis and radius where available, radial-normal polarity, maximum absolute
principal curvature, wire and inner-wire counts, unique boundary-edge count,
maximum boundary-edge length, and adjacent face indices.

Each shared-edge row records the two incident faces, curve type, length, and
the dot product of the two representative normals. That dot product is a
coarse descriptor, not an edge-local continuity proof, and is not used alone
to classify a feature.

### Controlled rules

- **Hole.** A full-period cylinder whose orientation-adjusted normal points
  toward its axis is a cavity candidate. A circular single-wire cap identifies
  the blind subtype; absence of that cap identifies the controlled through
  subtype. Diameter and depth come from radius and lateral area.
- **Slot.** Two equal-radius inward partial cylinders with two shared planar
  walls form the controlled capsule subgraph. Radius, axis separation, and
  lateral area recover width, total length, and depth.
- **Step.** Two upward parallel planar levels connected to one common vertical
  riser form the controlled open step. Plane separation gives height and riser
  area divided by height gives span.
- **Chamfer-like boundary.** A diagonal planar face with two equal nonzero
  normal components must have exactly two parent planes whose normals project
  onto those components and are not parallel to one another. Axis-normal
  extrusion caps are excluded. Area divided by the longest boundary edge gives
  slant width, from which the equal setback is recovered.
- **Fillet-like boundary.** A non-full-period curved face adjacent to at least
  two planar faces uses analytic radius or sampled curvature, longest boundary
  edge, and area to recover constant radius and angular sweep. For the
  controlled cylindrical fillet, exactly two parent planes normal to the
  radial section are required; planar caps normal to the cylinder axis are
  excluded, and the two parent normals must not be parallel.

Every result is named a geometric candidate. The separate construction label
is attached only during evaluation, and `design_intent_proven` is always false.
Candidate rows retain expected dimensions, absolute residuals, and separate
classification and dimensional truth flags. The parent faces in chamfer-like
and fillet-like groups are also required to share recorded edges with the
candidate face.

The intent-boundary control is evaluated independently of the recognizer. At
both stages, the operation-built chamfer and direct bevel are compared by
vertex, edge, face, shell, and solid counts, signed volume, and Boolean
difference volume in both directions.

## Controlled Experiment

| Control | Construction truth | Expected geometric result |
| --- | --- | --- |
| `plain_block` | `12 × 8 × 6` box | None |
| `through_hole` | Radius `1.25`, depth `6` Boolean cut | Through hole, diameter `2.5` |
| `blind_hole` | Radius `1`, depth `3.5`, flat bottom | Blind hole, diameter `2` |
| `stepped_block` | Direct L-profile extrusion | Open step, height `2`, span `8` |
| `through_slot` | Capsule profile, radius `1`, center distance `4`, depth `4` | Through slot, width `2`, total length `6` |
| `chamfer_operation` | Symmetric distance-`1` chamfer on a length-`8` edge | One `45°` chamfer-like candidate |
| `equivalent_bevel` | Directly extruded profile with the same bevel boundary | The same geometric candidate, but no chamfer-operation claim |
| `fillet_operation` | Radius-`1` fillet on a length-`8` edge | Constant-radius fillet-like candidate with `90°` sweep |
| `cylindrical_boss` | External radius-`1.25` Boolean union | None; radial polarity is opposite to a hole |

Run from the repository root:

```bash
python -m pip install -e ".[geometry,test]"
python experiments/run_feature_recognition.py
python -m pytest tests/test_feature_recognition.py
```

Refresh the committed synthetic STEP fixtures explicitly:

```bash
python experiments/run_feature_recognition.py --refresh-fixtures
```

## Results

| Result | Constructed | STEP imported |
| --- | ---: | ---: |
| Geometric candidate instances | 7 | 7 |
| Hole candidates | 2 | 2 |
| Step candidates | 1 | 1 |
| Slot candidates | 1 | 1 |
| Chamfer-like candidates | 2 | 2 |
| Fillet-like candidates | 1 | 1 |
| Plain-block false positives | 0 | 0 |
| Cylindrical-boss false positives | 0 | 0 |

All 14 stage-specific candidates match both the controlled class/subtype and
the preregistered dimensions. The maximum candidate-to-truth length error is
`3.96e-13` model units, and the maximum candidate-to-truth angular error is
`5.88e-12` degrees. The maximum constructed-to-STEP differences remain
`3.95e-13` model units and `5.88e-12` degrees. These are recorded regression
results, not manufacturing tolerances.

At both constructed and STEP-imported stages, `chamfer_operation` and
`equivalent_bevel` have `V=10, E=15, F=7`, one shell, one solid, and volume
`572`. The absolute volume difference and both Boolean difference volumes are
zero. These observations are serialized separately from the construction
labels in
[`feature_equivalent_boundary_observations.csv`](../results/feature_equivalent_boundary_observations.csv).

![Feature inventory and recovered dimensions](../results/feature_recognition.png)

The preview shows all nine generated shapes, including the deliberately
equivalent chamfer-operation and direct-bevel boundaries.

![Nine synthetic feature-recognition controls](../results/feature_recognition_shapes.png)

## Interpretation

Surface type alone is insufficient. The through hole and external boss both
contain full cylindrical faces with the same radius. The orientation-adjusted
normal points toward the axis for the cavity and away from the axis for the
boss, giving the controlled distinction. The blind-hole subtype additionally
depends on its circular cap topology.

Likewise, one face is not always one feature. The slot is a four-face subgraph,
and the step is a three-face subgraph. Instance-level grouping must therefore
be retained separately from per-face labels.

The same applies to edge treatments. An extrusion end cap is adjacent to a
chamfer or fillet face but is not one of the two parent surfaces being bridged.
Selecting adjacent faces by local index would produce a plausible but wrong
evidence group; parent-normal and shared-edge conditions make that distinction
explicit in this corpus.

The equivalent-bevel control is the central claim boundary. Its final planar
boundary satisfies the same rule and dimensions as the operation-built
chamfer. A geometry-only system cannot determine which construction history
produced it. Calling both `chamfer_like` is supported; claiming both were made
by a chamfer operation is not.

## Failure Modes

- Labeling every cylinder as a hole without material-side orientation.
- Treating a circular face or one curved wall as a complete feature instance.
- Selecting the first two adjacent faces by traversal order instead of proving
  that they are the two parent surfaces.
- Detecting a diagonal plane and silently claiming a chamfer operation.
- Inferring machining accessibility or tool choice from a final boundary.
- Using representative-normal agreement as proof of edge-local tangency.
- Treating fixed dimensional regression gates as manufacturing tolerances.
- Evaluating invalid or open topology without first applying a shell/solid
  eligibility gate.

## Practical Guidance

- Build feature instances from attributed adjacency subgraphs, not isolated
  surface labels.
- Retain oriented normals and material-side evidence for cavity/protrusion
  distinctions.
- Store recovered dimensions, contributing face indices, stage, fixture hash,
  and backend provenance with every candidate.
- Call geometry-only outputs candidates and preserve ambiguity.
- Keep construction labels unavailable to recognition rules and use them only
  for controlled evaluation.
- Verify topology and validity before feature recognition on a new input
  class.

## Limitations

- Features are isolated and axis-aligned; no feature interactions are tested.
- There are no counterbores, countersinks, conical holes, threads, pockets,
  ribs, drafts, undercuts, islands, or variable-radius blends.
- The fillet rule covers one constant-radius quarter-round control.
- The chamfer rule covers one symmetric `45°` control.
- Parent-plane selection is verified only for straight extruded chamfer and
  cylindrical-fillet controls.
- Curvature is sampled at one representative parameter location.
- No cutter accessibility, stock, tolerance stack, process planning, or
  manufacturability claim is made.
- STEP stage agreement is evaluated through one pinned OCCT route.
- The rules are not trained or evaluated on production CAD data.
- Native geometry processing is not admitted for arbitrary untrusted input.

## Open Questions

1. Which edge-local sampling contract should replace representative-normal
   descriptors for general tangency and concavity?
2. How should overlapping hole, slot, pocket, chamfer, and fillet candidates
   be enumerated without forcing one interpretation?
3. Which stock and accessibility evidence is required before a geometric
   candidate may be called a machining feature?
4. How stable are the rules across independent kernels and STEP translators?
5. Which attributed graph fields should become inputs to a future learned
   recognizer while preserving provenance and abstention?

## Sources

- [OCCT `TopExp`](https://dev.opencascade.org/doc/refman/html/class_top_exp.html)
  documents subshape and ancestor mapping used for face adjacency.
- [OCCT `BRepAdaptor_Surface`](https://dev.opencascade.org/doc/refman/html/class_b_rep_adaptor___surface.html)
  documents restricted surface evaluation and analytic classification.
- [OCCT local surface properties](https://dev.opencascade.org/doc/refman/html/class_geom_l_prop___s_l_props_base.html)
  documents normal and curvature evaluation.
- [OCCT `BRepClass3d_SolidClassifier`](https://dev.opencascade.org/doc/refman/html/class_b_rep_class3d___solid_classifier.html)
  documents point classification available for future material-side checks.
- [OCCT `BRepAlgoAPI_Cut`](https://dev.opencascade.org/doc/refman/html/class_b_rep_algo_a_p_i___cut.html)
  documents the Boolean subtraction used to create synthetic cavity truth.
- [OCCT `BRepFilletAPI_MakeChamfer`](https://dev.opencascade.org/doc/refman/html/class_b_rep_fillet_a_p_i___make_chamfer.html)
  documents the chamfer construction control and its operation history API.
- [OCCT `BRepFilletAPI_MakeFillet`](https://dev.opencascade.org/doc/refman/html/class_b_rep_fillet_a_p_i___make_fillet.html)
  documents the fillet construction control.
- [S. Joshi and T. C. Chang, "Graph-based heuristics for recognition of machined features from a 3D solid model"](https://doi.org/10.1016/0010-4485(88)90050-4)
  introduces the attributed-adjacency-graph approach for selected features.
