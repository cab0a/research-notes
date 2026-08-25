# Tessellation and Visual Diagnostic Contracts

## 日本語概要

v0.42.0では、穴あき立体、球、Bスプライン殻をSTEP再読込後に4組の距離・角度条件で三角形分割し、3,782個の三角形を元の解析用面番号とSTEPの`ADVANCED_FACE`実体番号へ対応付けます。曲面ごとに支配的な分割条件が異なり、球の極には各条件2個の面積ゼロ三角形が残りました。三角形面積、面積差、媒介変数重心での表面距離は診断値であり、要求した分割値を最大誤差として証明せず、表示画像を正確なB-rep形状として扱いません。詳細は以下の英語本文を参照してください。

---

## English Summary

This study defines versioned triangle, face, summary, source-provenance, and
visual contracts for three synthetic STEP-derived controls under a two-by-two
absolute meshing design. All 3,782 triangle rows retain their analysis-local
face and direct `ADVANCED_FACE` source instance. Angular refinement controls
the through-hole cylinder in this corpus, both inputs affect the sphere, and
linear refinement controls the B-spline patch. Eight zero-area sphere-pole
triangles remain explicit. Requested deflections, sampled surface deviations,
mesh areas, and previews are diagnostic evidence rather than certified error
bounds or exact B-Rep geometry.

## Research Question

Can a STEP-derived B-Rep tessellation be made auditable from each rendered
triangle back to its local face and source Part 21 entity, while preserving the
difference between requested meshing controls, observed samples, and exact
surface geometry?

## Background

Tessellation replaces trimmed analytic or free-form surfaces with triangles
for visualization and many downstream calculations. The representation is
useful because triangle traversal is simple and widely supported, but it is an
approximation with its own node, triangle, normal, and degeneracy behavior.

Four values must not be conflated:

1. requested linear deflection;
2. requested angular deflection;
3. the deflection value stored with the generated triangulation; and
4. independently measured geometric error.

This study records the first three where exposed and adds one deterministic
surface-deviation sample per triangle. That sample is not a maximum-error
certificate. Exact B-Rep surface area remains a separate reference.

## Source Review

The implementation follows the official Open CASCADE interfaces:

- [`BRepMesh_IncrementalMesh`](https://dev.opencascade.org/doc/refman/html/class_b_rep_mesh___incremental_mesh.html)
  accepts linear and angular deflection inputs, a relative/absolute selector,
  and a parallel-execution selector. This experiment uses absolute values and
  disables parallel meshing.
- [`BRep_Tool::Triangulation`](https://dev.opencascade.org/doc/refman/html/class_b_rep___tool.html)
  retrieves the active triangulation for a face and returns its location.
- [`Poly_Triangulation`](https://dev.opencascade.org/doc/refman/html/class_poly___triangulation.html)
  exposes face-local nodes, triangle node indices, optional UV nodes, optional
  normals, and stored deflection.
- [`Poly_Triangle`](https://dev.opencascade.org/doc/refman/html/class_poly___triangle.html)
  defines one triangle as three indices into its triangulation's node table.
- [`BRepAdaptor_Surface`](https://dev.opencascade.org/doc/refman/html/class_b_rep_adaptor___surface.html)
  evaluates the located support surface at the UV sample used by this study.
- [`BRepGProp`](https://dev.opencascade.org/doc/refman/html/class_b_rep_g_prop.html)
  supplies exact-surface area independently of the triangle sum.
- [`XSControl_TransferReader`](https://dev.opencascade.org/doc/refman/html/class_x_s_control___transfer_reader.html)
  can return the source entity that produced a transferred shape when
  intermediate transfer results are searched.

The documents describe interfaces and representation semantics. They do not
turn a requested deflection into a verified global error bound for this
corpus; that would require a separate certification procedure.

## Method

### Two-by-two control design

The experiment varies the two inputs independently:

| Condition | Linear deflection | Angular deflection |
| --- | ---: | ---: |
| `coarse_both` | `0.8` model units | `0.7` radians |
| `fine_angular` | `0.8` model units | `0.25` radians |
| `fine_linear` | `0.05` model units | `0.7` radians |
| `fine_both` | `0.05` model units | `0.25` radians |

Relative deflection and parallel meshing are both disabled. The labels
`coarse` and `fine` are comparisons inside this fixed experiment, not quality
grades for arbitrary geometry.

### Triangle geometry

For each imported face, the experiment retrieves its triangulation and
location. It transforms every face-local node into shape coordinates and
records the original node triplet. Triangle area is half the magnitude of the
cross product of two triangle edges. The normalized cross product is reversed
when the owning face is reversed.

A zero-area triangle has no geometric normal. It remains in the table with
`is_degenerate=1` and blank normal fields rather than being silently removed.

### Sampled surface deviation

When UV nodes exist, their arithmetic mean defines one deterministic sample in
the triangle's parameter-space image. The experiment evaluates the exact
support surface there and measures the distance to the three-dimensional
triangle centroid.

This is one diagnostic sample. It does not search the whole triangle, account
for every possible periodic parameter branch, or prove a maximum deviation.

### STEP entity provenance

The fixture SHA-256 identifies the exact normalized Part 21 source. For every
local face, the STEP transfer reader searches root and intermediate transfer
results with mode 1. The returned entity is located in the interface model,
then its corresponding Part 21 instance label is verified directly against
the fixture bytes.

All nine controlled faces resolve to an `ADVANCED_FACE` source instance. A
triangle therefore has the following bounded lineage:

```text
fixture SHA-256
  -> Part 21 ADVANCED_FACE instance
  -> STEP-imported analysis-local face
  -> mesh condition
  -> face-local triangle
```

This lineage is direct source provenance for one read operation. It is not a
persistent identifier after editing, healing, re-export, or another reader.

## Controlled Experiment

Only programmatically generated shapes are used.

| Control | Purpose | Imported faces |
| --- | --- | ---: |
| `meshing_through_hole` | planar trims, two inner wires, shared edges, one cylinder | 7 |
| `meshing_sphere` | periodic analytic curvature and polar singularities | 1 |
| `meshing_bspline_shell` | bounded free-form surface in an open shell | 1 |

Each shape is written to a normalized STEP fixture, read again with transfer
history retained, cleaned of earlier cached polygonal data, and meshed once
under each of the four conditions. Single-threaded execution and a pinned OCCT
binding provide the reference route.

![Face-colored coarse and fine tessellation previews](../results/tessellation_visual_diagnostics.png)

## Results

![Tessellation control response](../results/tessellation_diagnostics.png)

### Triangle counts

| Control | Coarse both | Fine angular | Fine linear | Fine both |
| --- | ---: | ---: | ---: | ---: |
| Through-hole solid | 88 | 220 | 88 | 220 |
| Sphere | 168 | 1,260 | 422 | 1,260 |
| B-spline shell | 10 | 10 | 18 | 18 |

The through-hole result changes only when the angular input is refined. The
sphere responds to both inputs, although the finer angular input is dominant
at the selected levels. The B-spline result changes only when the linear input
is refined. A single universal statement such as “smaller linear deflection
always produces more triangles” is therefore unsupported even within this
small corpus.

### Approximation diagnostics

| Control and comparison | Relative area difference | Maximum sampled deviation |
| --- | ---: | ---: |
| Through hole, coarse to fine angular | `8.6769e-5` to `1.0612e-5` | `0.0168787` to `0.00210739` |
| Sphere, coarse to fine both | `0.0412249` to `0.00595059` | `0.577726` to `0.231520` |
| B-spline, coarse to fine linear | `0.00742346` to `0.00370206` | `0.05` to `0.025` |

The through-hole and sphere triangle-area sums are below their exact B-Rep
areas. The B-spline triangle-area sum is above its exact area under all four
conditions. Mesh area error is not one-sided.

All 36 face-condition rows have UV nodes and direct STEP face provenance. The
3,782 triangle rows include eight zero-area triangles: exactly two at the
sphere poles under each meshing condition. Those triangles have blank normals
but retain their face and `ADVANCED_FACE` lineage.

## Interpretation

The factorial design is more informative than a single coarse-to-fine series.
It identifies which requested control is active for each controlled surface
at these values and exposes plateaus where tightening the other input produces
no observed change.

The direct transfer-history bridge improves the v0.41.0 face report. A visual
triangle can now be traced not only to an analysis-local face but also to the
source Part 21 face entity. That is enough for a diagnostic viewer to select a
triangle, open its face report, and locate the originating STEP statement.

The sphere result shows why a renderer and an analysis pipeline need different
acceptance rules. A renderer can display the sphere despite pole-degenerate
triangles. A downstream area, normal, learning, or collision pipeline should
not silently assume every rendered primitive is nondegenerate.

## Failure Modes

- Treating requested linear or angular deflection as an independently verified
  maximum geometric error.
- Treating one centroid-based sample as a bound over the complete triangle.
- Comparing triangle counts without the surface family, model scale, trim,
  and both meshing inputs.
- Assuming mesh area always underestimates or always overestimates exact area.
- Normalizing a zero-area triangle and producing an undefined or nonfinite
  normal.
- Ignoring the location returned with a face triangulation.
- Treating face-local node indices as shape-global vertex identifiers.
- Treating a source `ADVANCED_FACE` label as persistent after a new exchange or
  modeling operation.
- Treating the face-colored PNG as evidence of exact surface geometry.

## Practical Guidance

1. Record linear, angular, relative, and parallel settings with every mesh.
2. Keep the exact B-Rep face and mesh representation as separate artifacts.
3. Transform triangulation nodes with the returned face location.
4. Preserve face and source-entity provenance before merging nodes or faces.
5. Count and report degenerate triangles before computing normals or features.
6. Use sampled deviations for diagnosis only; use a dedicated extremum or
   certification method when a guaranteed bound is required.
7. Select meshing settings using the intended downstream task and model units,
   not a repository-wide absolute threshold.

## Limitations

- The corpus contains three small generated shapes, nine faces, and one pinned
  Linux x64 OCCT route.
- Only absolute, single-threaded meshing is evaluated.
- The two input levels do not establish response curves or optimal settings.
- Surface deviation is sampled once per triangle and is not a Hausdorff,
  chordal-maximum, or certified approximation error.
- Mesh validity beyond zero-area triangle detection is not evaluated.
- Shared boundary nodes are counted face-locally; no global welded mesh is
  constructed.
- Nodal normals are not generated or compared; triangle normals are computed
  directly except for degenerate triangles.
- The source mapping covers controlled `ADVANCED_FACE` transfer results, not
  arbitrary representation items, tessellated STEP entities, XCAF labels, or
  repaired topology.
- No interactive viewer, picking interface, GPU renderer, collision detector,
  or mesh exporter is implemented.
- No external production or customer CAD data is used.

## Questions Raised

1. Should a future viewer preserve face-local node duplication or also expose
   a tolerance-aware welded display mesh?
2. Which independently evaluated distance procedure can certify a maximum
   surface-to-triangle deviation without assuming convexity or regular UV
   parameterization?
3. How should source lineage be represented when one source face splits into
   several result faces, or several source faces merge during repair?
4. Which mesh diagnostics are necessary before triangle graphs or learned
   models consume the output?

## Reproduction

```bash
python -m pip install -e ".[geometry,test]"
python experiments/run_tessellation_diagnostics.py
python -m pytest tests/test_tessellation_diagnostics.py
```

The experiment regenerates three CSV files, one JSON contract, two PNG figures,
and three STEP fixtures. CI compares all text artifacts and the fixture
directory byte for byte and verifies that both figures are nonempty.

## Sources

- [Open CASCADE `BRepMesh_IncrementalMesh` reference](https://dev.opencascade.org/doc/refman/html/class_b_rep_mesh___incremental_mesh.html)
- [Open CASCADE `BRep_Tool` reference](https://dev.opencascade.org/doc/refman/html/class_b_rep___tool.html)
- [Open CASCADE `Poly_Triangulation` reference](https://dev.opencascade.org/doc/refman/html/class_poly___triangulation.html)
- [Open CASCADE `Poly_Triangle` reference](https://dev.opencascade.org/doc/refman/html/class_poly___triangle.html)
- [Open CASCADE `BRepAdaptor_Surface` reference](https://dev.opencascade.org/doc/refman/html/class_b_rep_adaptor___surface.html)
- [Open CASCADE `BRepGProp` reference](https://dev.opencascade.org/doc/refman/html/class_b_rep_g_prop.html)
- [Open CASCADE `XSControl_TransferReader` reference](https://dev.opencascade.org/doc/refman/html/class_x_s_control___transfer_reader.html)
