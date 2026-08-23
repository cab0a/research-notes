# Wires, Trimming, and Face Orientation

## 日本語概要

本研究は、曲面そのものと、その上で面として残す範囲を分けて扱います。外周と穴を持つ平面枠、その反転面、周期境界を持つ円柱面、極に特異点を持つ球面を解析式から合成し、境界を構成する辺の接続順、外周・内周、向き、面積、重心、媒介変数範囲、内外判定、継ぎ目、縮退辺を構築直後とSTEP再読込後で比較しました。平面枠では外周と穴の符号付き媒介変数面積が `+48` と `-6`、面反転後は `-48` と `+6` になりましたが、物質領域の面積 `42`、重心、内外判定は変わりません。球面では同じ継ぎ目辺を2回使い、三次元曲線を持たない極上の縮退辺2本が二次元境界を閉じます。STEP再読込後も全16点の内外・境界判定と全6周回の検査は一致しましたが、球面の自然境界印は保持されませんでした。これは合成形状と固定した形状計算核での研究結果であり、任意の曲線境界、壊れた位相、修復、一般的なSTEP互換性は保証しません。詳細と出典は英語本文に示します。

---

## English Summary

This study separates an unbounded or naturally bounded support surface from
the finite region retained by face wires. Two planar frames, a full-period
cylinder, and a natural sphere provide controlled outer loops, inner loops,
face reversal, periodic seams, and singular pole edges. Analytic material
area, centroid, restricted UV bounds, and signed loop area are compared with
the selected geometry backend before and after STEP exchange. Ordered edge
uses, topological closure, UV closure, in/out/boundary classification, wire
checks, and STEP representation counts are recorded separately.

## Research Question

Can the selected geometry backend recover ordered outer and inner wires,
trimmed material regions, orientation-aware loop winding, periodic seams, and
degenerate singular boundaries after STEP exchange without confusing support
surface extent, topological use, and material classification?

## Background

A B-Rep face is not the same object as its support surface. An infinite plane
can support a finite rectangular frame. A cylinder can have an unbounded axial
domain but a face restricted to a finite height. A sphere has a finite natural
parameter domain, yet its rectangular UV boundary includes two pole segments
that collapse to points in three dimensions.

A wire is an ordered loop of edge uses. The same underlying edge may be used
with different orientations, and a seam edge on a periodic surface can occur
twice in one boundary. OCCT's `BRepTools_WireExplorer` documents connection-
ordered traversal and accepts a face so that the next edge can be selected in
the face's parameter representation. Its documented precondition is a valid,
properly connected wire; defective inputs can terminate traversal before all
edges are visited.

Orientation is relational rather than a permanent direction attached to the
underlying geometry. Reversing a face reverses its boundary uses and swaps the
material-side interpretation, while geometric area and centroid remain
unsigned physical properties. For a simple straight-segment UV loop, the
signed shoelace area exposes that winding change. The sign is diagnostic in
this controlled corpus; it is not a complete replacement for face
classification or arbitrary curved-loop integration.

OCCT's face classifier returns `IN`, `OUT`, or `ON` for a UV point. Separate
wire checks report two-dimensional closure and orientation, while shape-
analysis checks expose ordering, connectivity, closure, and degenerate-edge
defects. These observations answer different questions and are not collapsed
into one Boolean validity claim.

## Method

### Independent controls

The experiment creates four faces exclusively from fixed numeric inputs:

| Face | Support and restriction | Intended evidence |
| --- | --- | --- |
| `planar_frame_forward` | Infinite plane; outer `[-4,4] × [-3,3]`; inner hole `[-1,2] × [-1,1]` | Outer and inner winding, material subtraction, point classification |
| `planar_frame_reversed` | The same local restriction at a translated origin, then face reversal | Winding-sign reversal without material-area change |
| `closed_cylinder` | Radius `2`; U `[0,2π]`; V `[-2,2]` | One periodic seam edge used twice |
| `natural_sphere` | Radius `3`; U `[0,2π]`; V `[-π/2,π/2]` | Two seam uses and two degenerate pole boundaries |

The planar material area is `8 × 6 - 3 × 2 = 42`. Its centroid is found by
subtracting the off-center hole, giving local X coordinate `-1/14`. The
cylinder area is `2π × 2 × 4 = 16π`; the sphere area is `4π × 3² = 36π`.
Symmetry places both curved-face centroids at their support origins.

Expected signed UV areas are derived from the controlled boundary polygons:

| Face and loop | Forward value | Reversed value |
| --- | ---: | ---: |
| Planar outer loop | `+48` | `-48` |
| Planar inner loop | `-6` | `+6` |
| Cylinder outer loop | `+8π` | Not included |
| Sphere outer loop | `+2π²` | Not included |

### Ordered topology observations

Each face receives an analysis-local unique-edge map. Each wire is then
visited in connection order with its parent face. For every edge occurrence,
the experiment records:

1. Wire role, occurrence order, unique-edge index, and orientation.
2. Degenerate and seam states and whether a 3D curve exists.
3. Start and end topological vertices and their oriented edge parameters.
4. P-curve UV endpoints evaluated at those vertex parameters.
5. UV gap, 3D vertex gap, and topological vertex identity to the next use.

This order matters. A geometric curve exposes an ascending parameter range,
but a reversed topological use traverses it from its end vertex toward its
start. Evaluating only the ascending range would produce the wrong loop
winding.

For each wire, the experiment also records unique and occurrence edge counts,
seam and degenerate occurrences, signed UV area, maximum closure gaps,
`BRepCheck_Wire` two-dimensional closure and orientation statuses, and
`ShapeAnalysis_Wire` defect flags. No repair function is called.

### Face and classification observations

The face table separates restricted UV bounds from the unrestricted support-
surface bounds. It also records surface periodicity, the kernel's
`NaturalRestriction` flag, outer and inner wire counts, orientation, area, and
centroid. Sixteen fixed UV samples cover material, the planar hole, exterior,
outer and inner boundaries, a cylinder boundary, and sphere poles. Expected
states are declared before backend classification.

### STEP exchange

The four faces are written as one compound using the pinned optional OCCT
route. Only the known writer timestamp, process counters, and generated
compound occurrence numbers are normalized. The committed bytes are then read
back and measured through the same code path. STEP entity counts are treated
as writer-specific observations, not universal encoding rules.

## Controlled Experiment

Install the optional geometry dependency and run:

```bash
python -m pip install -e ".[geometry,test]"
python experiments/run_wire_trimming_evaluation.py
python -m pytest tests/test_wire_trimming.py
```

Regenerate the committed synthetic STEP fixture with:

```bash
python experiments/run_wire_trimming_evaluation.py \
  --fixture-dir fixtures/wire-trimming-evaluation \
  --refresh-fixtures
```

All geometry and expected values are generated by project code. No external,
company, customer, or production CAD data is used.

## Results

| Observation | Constructed | STEP imported |
| --- | ---: | ---: |
| Valid compound | Yes | Yes |
| Faces / wires / ordered edge uses | `4 / 6 / 24` | `4 / 6 / 24` |
| Orientation matches | `4/4` | `4/4` |
| Classification matches | `16/16` | `16/16` |
| Wires with reported defects | `0/6` | `0/6` |
| Maximum face-area absolute error | `0` | `3.31e-12` |
| Maximum centroid distance | `1.39e-16` | `1.31e-13` |
| Maximum restricted-UV error | `0` | `4.14e-13` |
| Maximum signed-loop-area error | `0` | `8.28e-13` |
| Maximum UV connection gap | `0` | `4.14e-13` |
| Maximum connected-vertex distance | `0` | `0` |

The two planar faces each have one outer and one inner wire. Their signed UV
areas have the expected opposite signs, and face reversal flips both signs.
The unsigned material area remains `42`, and the corresponding material, hole,
exterior, and boundary classifications are unchanged.

The cylinder wire has four ordered occurrences but only three unique edges:
one seam edge occurs twice. The sphere also has four occurrences and three
unique edges. Its seam edge occurs twice, and its two pole uses are degenerate,
have no 3D curve, and still span the bottom and top boundaries of the UV
rectangle. All next vertices are identical topologically and at zero 3D
distance in both stages.

The normalized 22,605-byte STEP fixture has SHA-256
`224f0d295a684602264ef82e30b6632041570490b5514788ca90fd9796e47366`.
It contains four `ADVANCED_FACE`, six `FACE_BOUND`, five `EDGE_LOOP`, and one
`SEAM_CURVE` instances. It contains no `FACE_OUTER_BOUND` or
`DEGENERATE_PCURVE` instances. The imported backend nevertheless reconstructs
one outer wire per face and two degenerate sphere edge uses; therefore those
kernel observations must not be inferred from entity-name counts alone.

![Wire winding, periodic seams, singular pole boundaries, and numeric checks](../results/wire_trimming_evaluation.png)

![Generated planar frames, cylinder, sphere, seams, and poles](../results/wire_trimming_shapes.png)

The chart replaces exact-zero bars with `1e-18` only for logarithmic display.
That value is neither an observation nor an acceptance threshold.

## Interpretation

The controlled result supports four distinctions.

First, the support surface and face restriction are separate domains. Both
planes report effectively unbounded support parameters but finite face bounds.
The cylinder has a finite periodic U support and unbounded V support, while
the face wire restricts V to `[-2,2]`. The sphere's support and restricted
bounds coincide.

Second, outer versus inner is material semantics, not merely the numerical
sign of one coordinate-space polygon. The planar hole subtracts area because
its wire has the opposite winding relative to its face. Reversing the face
reverses both loop signs while leaving the represented material region intact.

Third, topology cannot be reconstructed from distinct 3D curves alone. One
cylinder seam edge needs two boundary occurrences. The sphere additionally
needs two degenerate edges that map to points in 3D but to full boundary
segments in UV. Dropping those edges because their 3D length is zero leaves
the parameter-space boundary open.

Fourth, a backend flag is not automatically an exchange semantic. The sphere
has `NaturalRestriction=true` immediately after construction and `false` after
STEP import, even though its support bounds, face bounds, area, centroid, wire,
and classifications remain correct. This release therefore records the flag
as stage-specific kernel state rather than requiring it to survive STEP.

## Failure Modes

- Treating a face as its entire support surface and ignoring boundary wires.
- Counting all loops as material additions instead of distinguishing outer
  and inner roles.
- Calculating loop winding from ascending curve ranges instead of oriented
  topological vertex order.
- Assuming face reversal changes area, centroid, or in/out classification.
- Collapsing the two UV branches of a periodic seam into one segment.
- Deleting a degenerate edge because it has no 3D curve or visible length.
- Inferring outer-loop role or degeneracy only from STEP entity names emitted
  by one writer.
- Treating signed shoelace area as a general classifier for curved,
  self-intersecting, seam-crossing, or multiply nested loops.
- Repairing an invalid wire during inspection and reporting the repaired state
  as the imported state.
- Reusing the fixture's residuals as universal CAD, manufacturing, or healing
  thresholds.

## Practical Guidance

- Report the support surface, restricted domain, wires, and edge occurrences
  as separate layers.
- Preserve unique-edge identity and ordered edge-use identity simultaneously;
  seams require both views.
- Evaluate p-curve endpoints at orientation-aware topological vertex
  parameters.
- Check UV connection, 3D vertex distance, and topological vertex identity
  separately.
- Retain degenerate edges when they close a valid parameter-space boundary.
- Use point classification and kernel validity checks alongside winding
  diagnostics instead of replacing them with one sign test.
- Record construction, import, validation, and any later repair as distinct
  stages with explicit provenance.
- Quarantine unsupported self-intersections, missing representations, and
  ambiguous nested loops before attempting repair.

## Limitations

- The corpus contains four valid analytic faces from one pinned OCCT build.
- Planar boundaries and all p-curve segments are straight in parameter space;
  general curved-loop integration is not implemented.
- Only one hole is nested inside each planar outer loop. Islands, multiple
  nesting levels, touching loops, and crossing loops are absent.
- The experiment does not include invalid ordering, disconnected wires,
  self-intersections, missing p-curves, excessive tolerances, non-manifold
  uses, or ambiguous seam-crossing intervals.
- Cone and torus singularities, trimmed B-spline surfaces, and B-spline
  p-curves are not evaluated.
- `ShapeAnalysis_Wire` and `BRepCheck_Wire` observations are backend reports,
  not independent proofs of all mathematical validity conditions.
- One STEP writer and reader are used; no independent kernel or public parser
  is compared for evaluated trimming behavior.
- STEP entity counts are specific to the pinned writer configuration.
- The native route is not a hardened boundary for arbitrary untrusted files.
- No repair, sewing, shell validation, solid validation, tessellation,
  editing, or public modeling API is implemented.

## Open Questions

1. Which STEP representation choices should, if any, reconstruct a backend's
   `NaturalRestriction` flag?
2. How should winding and enclosed UV area be computed robustly for B-spline
   p-curves, periodic unwraps, and seam-crossing loops?
3. Which independent checks should define quarantine before any ordering,
   p-curve, tolerance, or face repair?
4. How should nested holes and islands be represented in a general face report
   without relying on traversal order?
5. Which shell-level orientation and incidence rules are needed before a face
   normal can be interpreted as outward from a solid?

## Sources

- [OCCT `BRepTools_WireExplorer`](https://dev.opencascade.org/doc/refman/html/class_b_rep_tools___wire_explorer.html) documents connection-ordered edge traversal and the role of a face in selecting p-curve connections.
- [OCCT `BRepTools`](https://dev.opencascade.org/doc/refman/html/class_b_rep_tools.html) documents outer-wire lookup and restricted UV bounds.
- [OCCT `TopAbs_Orientation`](https://dev.opencascade.org/doc/refman/html/_top_abs___orientation_8hxx.html) defines the orientation states used by topological entity occurrences.
- [OCCT `BRepClass_FaceClassifier`](https://dev.opencascade.org/doc/refman/html/class_b_rep_class___face_classifier.html) documents UV point classification on a face.
- [OCCT `BRepCheck_Wire`](https://dev.opencascade.org/doc/refman/html/class_b_rep_check___wire.html) documents two-dimensional closure and orientation checks in face context.
- [OCCT `ShapeAnalysis_Wire`](https://dev.opencascade.org/doc/refman/html/class_shape_analysis___wire.html) documents ordering, connectivity, closure, degenerate-edge, and self-intersection analysis.
- [OCCT `BRepAdaptor_Surface`](https://dev.opencascade.org/doc/refman/html/class_b_rep_adaptor___surface.html) distinguishes a face-restricted parameter range from its unrestricted support surface.
- [OCCT `BRepBuilderAPI_MakeFace`](https://dev.opencascade.org/doc/refman/html/class_b_rep_builder_a_p_i___make_face.html) documents construction of faces from support surfaces and boundary wires, including added hole wires.
- [STEP Tools AP242 `face_bound`](https://www.steptools.com/stds/stp_aim/html/t_face_bound.html) provides the public schema reference for a face boundary and its orientation flag.
- [STEP Tools AP242 `edge_loop`](https://www.steptools.com/stds/stp_aim/html/t_edge_loop.html) provides the public schema reference for an ordered loop of oriented edges.
