# Evaluated Face Geometry and Tolerances

## 日本語概要

本研究は、平面2面と円筒面1面を解析式から合成し、Open CASCADE Technologyが計算した面積、重心、UV範囲、代表点、支持曲面法線、面の向きを反映した法線、曲面原点・軸・半径、面公差を独立真値と比較します。構築直後とSTEP再読込後の幾何値は浮動小数点誤差の範囲で一致し、反転面の向きも保持されました。一方、構築時の面公差 `1e-4`、`2e-4`、`3e-4` は再読込後にすべて `1e-7` となりました。この結果は、面公差を交換前後で同一と仮定せず、生成・書出し・読込みの各段階と出典を伴う値として記録すべきことを示します。完全なトリム面、周期境界、穴、Bスプライン面、一般的なSTEPファイルへの一般化は主張しません。詳細と出典は英語本文に示します。

---

## English Summary

This study evaluates two bounded planes and one bounded cylindrical surface
against closed-form truth derived without OCCT. Constructed and STEP-imported
area, centroid, UV bounds, representative point, support normal, oriented face
normal, surface frame, and cylinder radius agree within the declared synthetic
numeric contract. The reversed plane retains its topological orientation.
Constructed face tolerances of `1e-4`, `2e-4`, and `3e-4` are all observed as
`1e-7` after the controlled STEP import, while the exported representation
uncertainty is `1e-4`. Tolerance is therefore reported as stage-specific
backend state, not assumed to be a round-trip-preserved face attribute.

## Research Question

Can the selected optional geometry backend evaluate bounded planar and
cylindrical B-Rep faces accurately against independently derived truth, and
which orientation and tolerance claims remain valid after a STEP write/read
round trip?

## Background

v0.31.0 established that the optional CadQuery OCP route can construct a box,
write STEP, read it back, and retain the expected unique topology. Matching
topology counts do not establish that individual face geometry is correct.
This study moves from counting entities to evaluating what selected faces mean
numerically.

The terms are kept separate:

- A **support surface** is the unbounded plane or cylinder carrying a face.
- A **face** is a topological use of a bounded region on that support surface.
- A **support normal** follows the surface parameterization and is computed as
  the normalized cross product of the first U and V derivatives.
- An **oriented face normal** additionally flips the support normal when the
  topological face orientation is reversed.
- A **face tolerance** is a value held by the backend's B-Rep face at one
  observed stage. It is not the same object as a STEP geometric-dimensioning
  tolerance, and this study does not treat it as an automatically preserved
  source attribute.

OCCT documents that `BRepGProp::SurfaceProperties` uses exact surface objects
when triangulation is not requested and that the returned mass represents
surface area. `BRepTools::UVBounds` returns bounds in a face's parametric
space. `BRepAdaptor_Surface` provides surface classification, analytic
parameters, points, and first derivatives. `BRep_Tool::Tolerance` exposes the
current B-Rep face tolerance. These functions define the backend observation
path, not the independent truth path.

## Method

### Independent truth

Three controls are defined only by numeric origins, orthonormal directions,
parameter bounds, orientation, radius where applicable, and requested
constructed tolerance:

| Face | Surface | U bounds | V bounds | Orientation | Constructed tolerance |
| --- | --- | --- | --- | --- | --- |
| `plane_forward` | Plane | `[-2, 3]` | `[-1, 4]` | Forward | `1e-4` |
| `plane_reversed` | Plane | `[-1, 2]` | `[-2, 2]` | Reversed | `2e-4` |
| `cylinder_forward` | Cylinder, radius `2.5` | `[0.3, 1.7]` | `[-1, 4]` | Forward | `3e-4` |

For a plane, area is the product of the U and V spans, and the centroid is the
surface point at the midpoint of both intervals. For a cylindrical lateral
face with radius (r), angular span ([u_0,u_1]), and axial span
([v_0,v_1]), area is
(r(u_1-u_0)(v_1-v_0)). The X and Y centroid coefficients use the analytic
averages of cosine and sine over the angular interval; the axial coefficient
is the V midpoint. This matters because the area centroid of a cylindrical
patch is not generally the surface point at its parameter midpoint.

The truth module uses only Python arithmetic and `math`. It does not call OCCT
to derive expected area, centroid, representative point, normals, or analytic
surface parameters.

### Backend observations

The pinned optional backend constructs the three faces and records:

1. Surface type and topological orientation.
2. Exact-surface area and area centroid.
3. Face UV bounds.
4. Point and first derivatives at the UV midpoint.
5. Support normal and orientation-adjusted face normal.
6. Surface origin, main axis, X direction, and cylinder radius.
7. Current face tolerance.

The faces are matched to controls by surface type and nearest analytic
centroid, not by explorer order. This avoids presenting a traversal order as a
persistent face identity.

### STEP round trip

The three faces are placed in one generated compound and written with a
declared representation uncertainty of `1e-4`. The writer timestamp, process
counter, and generated compound occurrence numbers are narrowly normalized.
The committed bytes are then imported and measured again. The experiment
retains the normalized STEP fixture and its SHA-256.

## Controlled Experiment

Install the optional geometry dependency and run:

```bash
python -m pip install -e ".[geometry,test]"
python experiments/run_evaluated_face_geometry.py
python -m pytest tests/test_face_geometry.py
```

To reproduce the committed fixture itself:

```bash
python experiments/run_evaluated_face_geometry.py \
  --fixture-dir fixtures/evaluated-face-geometry \
  --refresh-fixtures
```

Every geometry input is generated by the experiment. No external, company,
customer, or production CAD model is used.

## Results

| Observation | Constructed | STEP imported |
| --- | ---: | ---: |
| Faces measured | 3 | 3 |
| Surface-type matches | 3 | 3 |
| Orientation matches | 3 | 3 |
| Maximum area absolute error | `3.55e-15` | `3.55e-15` |
| Maximum centroid distance | `5.55e-17` | `1.67e-16` |
| Maximum UV-bound absolute error | `0` | `1.32e-13` |
| Maximum representative-point distance | `0` | `5.96e-14` |
| Maximum oriented-normal angular error | `0°` | `0°` |
| Maximum surface-origin distance | `0` | `0` |
| Maximum surface-axis angular error | `0°` | `0°` |
| Maximum cylinder-radius absolute error | `0` | `0` |
| Observed face-tolerance range | `1e-4` to `3e-4` | `1e-7` to `1e-7` |

The normalized 15,611-byte fixture has SHA-256
`95dc8978750fe4fcffa987cff58e0eef252525cd7b78d66b2eb1564818ae9047`.
The STEP file contains four representation-uncertainty records, each with
`1e-4`; one belongs to the compound representation and three to its generated
component representations.

![Evaluated face geometry and tolerance evidence](../results/evaluated_face_geometry.png)

The error chart uses `1e-18` only as a display floor for exact-zero bars. It is
not an observed error and not a quality threshold.

## Interpretation

The result supports a narrow but useful capability: for the three controlled
analytic faces, the backend can classify the support surface and evaluate
area, centroid, UV bounds, a representative point and normal, surface frame,
and cylinder radius consistently before and after STEP exchange. The reversed
plane demonstrates that support-surface orientation and topological face
orientation must be reported separately. A plane axis alone is not always the
outward or use-oriented face normal.

The tolerance observation is deliberately different. The writer emits a
representation uncertainty of `1e-4`, but the reader returns `1e-7` for all
three imported B-Rep faces. OCCT's STEP guide documents that reader tolerance
management combines representation uncertainty or configured precision with
translation algorithms and minimum precision rules. Therefore, a face
tolerance after import is a translation result. The experiment does not infer
that the three original per-face tolerance values exist as separately
recoverable STEP attributes.

The test limits such as `5e-12` verify floating-point agreement for this fixed
synthetic corpus and pinned backend. They are regression tolerances, not
general CAD acceptance limits, manufacturing tolerances, or evidence that an
arbitrary imported face is accurate.

## Failure Modes

- Reporting a support-surface axis as an oriented face normal without applying
  topological orientation.
- Calling the UV midpoint a centroid on a curved face.
- Matching faces by traversal position and treating the position as stable
  identity.
- Treating the bounds of an unbounded analytic support surface as face trim
  bounds.
- Assuming that a B-Rep face tolerance is preserved as an identical per-face
  STEP attribute.
- Confusing STEP representation uncertainty, B-Rep geometric tolerance, and
  semantic geometric-dimensioning tolerances.
- Treating small synthetic regression errors as universal quality thresholds.
- Generalizing plane and non-seam cylindrical patches to holes, seams,
  singularities, B-splines, or repaired production models.

## Practical Guidance

- Record the stage, backend version, STEP processor, fixture hash, surface
  type, and face orientation with every evaluated value.
- Report both support normal and orientation-adjusted face normal when the
  distinction matters.
- Define the representative UV point explicitly; do not imply that one sample
  represents an entire trimmed face.
- Keep analytic truth independent of the geometry kernel for controlled
  regression fixtures.
- Treat face matching as an analysis operation and preserve its method.
- Compare tolerance values with their provenance rather than demanding silent
  round-trip identity.
- Use application-specific tolerance policies only after units, translation
  settings, topology, and geometric residuals have been evaluated.

## Limitations

- Only two planar rectangles and one cylindrical lateral patch are measured.
- The cylindrical interval does not cross the periodic seam.
- There are no holes, nested wires, degenerate edges, singular parameter
  regions, B-spline surfaces, offset surfaces, cones, spheres, or tori.
- The representative point is the UV midpoint and is known to lie inside every
  controlled rectangular parameter domain; arbitrary trimmed domains need an
  interior-point policy.
- Geometry and topology are evaluated by one OCCT build. The truth formulas
  are independent, but no independent B-Rep kernel is compared.
- The STEP writer may create product and assembly records for the compound;
  this study evaluates face geometry, not preservation of product semantics.
- The controlled imported tolerance outcome depends on the pinned writer,
  reader, and translation defaults and is not claimed for other tools.
- No arbitrary or untrusted STEP input is admitted by this native-code path.
- The study is not a manufacturing-inspection method, a complete STEP
  validator, or legal advice about third-party software distribution.

## Open Questions

1. How should UV intervals be canonicalized when a periodic cylindrical face
   crosses its seam?
2. Which 3D-curve, parameter-curve, and edge-use checks are needed before an
   arbitrary trim can be evaluated safely?
3. How do different STEP writers encode representation uncertainty, and how
   do independent readers turn it into vertex, edge, and face tolerances?
4. Which interior sample policy remains valid for nonrectangular trimmed
   domains and faces with holes?
5. Should a future report expose raw support-surface orientation, topological
   orientation, and shell-relative outward orientation as three fields?

## Sources

- [OCCT `BRepGProp` reference](https://dev.opencascade.org/doc/refman/html/class_b_rep_g_prop.html)
  documents surface-property computation, exact-surface versus triangulation
  selection, and the area meaning of the accumulated mass.
- [OCCT `BRepTools` reference](https://dev.opencascade.org/doc/refman/html/class_b_rep_tools.html)
  documents face UV-bound extraction.
- [OCCT `BRepAdaptor_Surface` reference](https://dev.opencascade.org/doc/refman/html/class_b_rep_adaptor___surface.html)
  documents surface classification, analytic-surface access, points, and
  first derivatives.
- [OCCT `BRep_Tool` reference](https://dev.opencascade.org/doc/refman/html/class_b_rep___tool.html)
  documents access to face geometry and the current face tolerance.
- [OCCT STEP translator guide](https://dev.opencascade.org/doc/overview/html/occt_user_guides__step.html)
  documents geometry/topology exchange, writing uncertainty values, and
  tolerance management during import.
- [CadQuery OCP on PyPI](https://pypi.org/project/cadquery-ocp/) identifies the
  pinned Python distribution used to reach the OCCT build in the reference
  environment.
