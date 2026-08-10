# Curves, Edge Parameters, P-Curves, and Seams

## 日本語概要

本研究は、平面、部分円筒面、全周円筒面を解析式から合成し、位相的な辺、三次元曲線、面の媒介変数空間にある二次元曲線、媒介変数範囲、境界での向き、継ぎ目を分離して評価します。各段階で11本の固有辺と12回の境界使用を観測し、線7本・円4本の種別、解析長、媒介変数幅、二次元境界経路が構築直後とSTEP再読込後で一致しました。全周円筒では1本の軸方向辺が境界で2回使われ、二次元では `u=0` と `u=2π` の2本として現れることを確認しました。STEP再読込後の二次元曲線から三次元曲線までの最大距離は `1.24e-12` でしたが、これは固定した合成形状と計算環境の回帰値であり、一般的なCAD品質基準ではありません。退化辺、曲面の特異点、内周、Bスプライン曲線、修復、異なる形状計算核は未評価です。詳細と出典は英語本文に示します。

---

## English Summary

This study separates a topological edge from its three-dimensional curve,
its curve in a face's two-dimensional parameter space, its parameter range,
and its oriented use in a boundary wire. Closed-form controls cover one plane,
one partial cylindrical face, and one full-period cylindrical face. Eleven
unique edges become twelve ordered wire occurrences because the full cylinder
uses one axial seam edge twice. The two seam p-curve branches lie at `u=0` and
`u=2π`. Curve type, analytic length, parameter span, UV path, and sampled
3D-to-surface consistency are evaluated before and after STEP exchange.

## Research Question

Can the selected geometry backend recover controlled edge curves, parameter
ranges, p-curves, orientation-aware boundary traversal, and a cylindrical seam
after STEP exchange, while keeping flags, numerical evidence, and topology as
separate claims?

## Background

A B-Rep edge is not only a visible line. It is a topological object that can
carry a three-dimensional curve, a bounded parameter interval, vertices, a
tolerance, and one or more two-dimensional curves on support surfaces. A face
wire uses that edge with an orientation. Consequently, these statements are
different:

- The edge's geometric curve has an ascending parameter range.
- A wire traverses the edge from one topological vertex to another.
- A p-curve maps the same parameter to a point `(u, v)` on a support surface.
- Evaluating the support surface at `(u, v)` agrees with the 3D curve within a
  declared tolerance or measured residual.
- An edge is a seam because one face has two p-curves for it on the same closed
  surface.

OCCT's `BRep_Tool` exposes the 3D curve, p-curve, parameter flags, tolerance,
degenerate state, and seam query. Its documentation defines the face-specific
closed-edge query as the case where one edge has two p-curves in the same
face's parameter space. `BRepAdaptor_Curve` supplies an orientation-independent
geometric interval and curve classification. `ShapeAnalysis_Edge` documents a
separate numerical check that samples the 3D curve and p-curves, rather than
treating the `SameParameter` flag as sufficient evidence.

For the controlled cylinder, the support surface equation is

`S(u, v) = origin + r cos(u) X + r sin(u) Y + v Z`.

It is periodic and closed in `u`. Therefore `u=0` and `u=2π` are different
locations in the two-dimensional parameter plane but evaluate to the same
three-dimensional generator line. That duplicate parameter-space boundary is
the seam examined here.

## Method

### Independent controls

The corpus contains three bounded analytic faces:

| Face | Surface | U bounds | V bounds | Radius | Constructed edge tolerance |
| --- | --- | --- | --- | ---: | ---: |
| `planar_rectangle` | Plane | `[-2, 3]` | `[-1, 2]` | — | `1e-5` |
| `partial_cylinder` | Cylinder | `[0.25, 1.75]` | `[-1, 3.5]` | `2` | `2e-5` |
| `closed_cylinder` | Cylinder | `[0, 2π]` | `[0, 4]` | `3` | `3e-5` |

Expected boundary type, length, parameter span, and three UV samples are
derived with Python arithmetic and `math`, without asking OCCT for the answer.
Plane boundaries and constant-U cylinder generators are lines. Constant-V
cylinder boundaries are circles. For a circular boundary, arc length is
`radius × angular span`, while the curve parameter span remains the angular
span. The two quantities are deliberately not conflated.

### Backend observations

For each unique edge, the experiment records:

1. Parent face and analysis-local edge index.
2. Boundary role or roles.
3. Expected and observed 3D curve type.
4. Expected and observed length.
5. Expected and observed parameter span.
6. `SameParameter`, `SameRange`, degenerate, and seam states.
7. Wire occurrence count, distinct p-curve branch count, and edge tolerance.
8. Maximum sampled distance between the 3D curve and the p-curve evaluated on
   its support surface.

For every ordered wire occurrence, it additionally records orientation,
p-curve type and range, start and end vertex parameters, UV start/mid/end,
range alignment, and the same 3D consistency residual. Seventeen equally
spaced parameters are sampled, including both interval endpoints. This is an
independent project check modeled on the purpose of OCCT's documented
same-parameter analysis; it does not call a repair routine.

Analysis-local indices are deterministic within the generated fixture but are
not claimed as persistent identifiers across unrelated files or tools. Faces
are matched to controls by analytic surface type and nearest controlled support
origin, not by traversal order.

### STEP exchange

The three faces are written as one compound with the pinned optional OCCT
route. Writer timestamp, process counters, and generated compound occurrence
numbers are narrowly normalized. The committed STEP bytes are read back and
measured through the same observation path. The generated file contains 11
`EDGE_CURVE`, 10 `SURFACE_CURVE`, 12 `PCURVE`, and one `SEAM_CURVE` instances.
These counts describe this fixture, not a universal encoding rule.

## Controlled Experiment

Install the optional geometry dependency and run:

```bash
python -m pip install -e ".[geometry,test]"
python experiments/run_edge_curve_evaluation.py
python -m pytest tests/test_edge_geometry.py
```

To regenerate the committed synthetic STEP fixture:

```bash
python experiments/run_edge_curve_evaluation.py \
  --fixture-dir fixtures/edge-curve-evaluation \
  --refresh-fixtures
```

All geometry is produced by the script. No external, company, customer, or
production CAD data is used.

## Results

| Observation | Constructed | STEP imported |
| --- | ---: | ---: |
| Unique edges | 11 | 11 |
| Ordered wire occurrences | 12 | 12 |
| 3D curve-type matches | 11/11 | 11/11 |
| `SameParameter=true` | 11/11 | 11/11 |
| `SameRange=true` | 11/11 | 11/11 |
| Maximum length absolute error | `3.55e-15` | `3.46e-14` |
| Maximum parameter-span absolute error | `0` | `1.73e-14` |
| Maximum UV-path absolute error | `0` | `4.14e-13` |
| Maximum 3D-curve-to-p-curve distance | `7.35e-16` | `1.24e-12` |
| Edge-tolerance range | `1e-5` to `3e-5` | `1e-7` to `1e-7` |

The one seam edge has boundary roles `u_min|u_max`, two wire occurrences, and
two distinct p-curve branches at `u=0` and `u=2π` at both stages. Its reversed
wire use traverses vertex parameters from `4` to `0`; its forward use
traverses from `0` to `4`. The underlying geometric range remains ascending
`[0, 4]` in both observations.

The normalized 15,386-byte fixture has SHA-256
`6969acae2a4cb674a5668573ba44e6b93ed1e7bb9e5088afa4b4197cbcdd420a`.

![Controlled edge curves, parameter-space seam, and residuals](../results/edge_curve_evaluation.png)

The chart uses `1e-18` only as a display floor for exact-zero bars. It is not
an observation or a quality threshold.

## Interpretation

The result supports a bounded capability: the selected backend distinguishes
line and circle edge geometry, exposes the expected parameter spans, returns
p-curves along the controlled parameter-domain boundaries, retains topological
traversal direction, and reconstructs the full-cylinder seam after the STEP
round trip.

The seam result is the most important conceptual finding. The 3D seam is one
topological edge and one generator line, but the face boundary needs two
parameter-space representations. Treating each p-curve as a different 3D edge
would duplicate topology. Treating the one 3D edge as having only one UV path
would leave the face boundary open in parameter space.

`SameParameter=true` and `SameRange=true` are reported as backend flags. The
separate sampled residual shows that the controlled 3D curve and mapped
p-curves agree numerically. The flags and residual answer different questions,
and neither is promoted to a universal acceptance policy.

The tolerance behavior repeats the provenance lesson from v0.32.0. Distinct
constructed edge tolerances become `1e-7` after this STEP import. This study
records that stage change but does not infer that original per-edge tolerance
values were explicit recoverable STEP attributes.

## Failure Modes

- Equating a topological edge with only its 3D curve.
- Using geometric parameter order as wire traversal order without applying
  the edge use's orientation.
- Assuming a curve parameter is arc length; this already fails for the
  controlled circular boundaries.
- Treating the two p-curves of a seam as two independent topological edges.
- Collapsing `u=0` and `u=2π` before constructing the closed parameter-space
  boundary.
- Trusting `SameParameter` or `SameRange` flags without measuring consistency.
- Assuming a returned planar p-curve was stored; OCCT documents that one may be
  generated on demand.
- Repairing ranges, p-curves, or tolerances during inspection and then
  presenting the repaired state as the imported source state.
- Treating analysis-local edge indices as persistent cross-tool identity.
- Reusing the synthetic residual limits as manufacturing or arbitrary-CAD
  acceptance thresholds.

## Practical Guidance

- Report edge topology, 3D curve geometry, p-curves, parameter ranges,
  orientation, and tolerance in separate fields.
- Iterate oriented wire occurrences when traversal order matters; also retain
  a unique-edge map to avoid duplicating seam topology.
- For every p-curve, evaluate the support surface and compare it with the 3D
  curve over the shared range.
- Preserve both periodic UV branches of a seam even when they map to the same
  3D points.
- Record whether a p-curve is stored or generated when the backend interface
  can distinguish the states.
- Keep observation and repair separate. Any range unification, p-curve
  reconstruction, or tolerance inflation should produce an explicit audit
  event and new state.
- Define numerical policies from units, intended use, kernel behavior, and
  measured residuals rather than from one global constant.

## Limitations

- The corpus contains only lines, circles, one plane, one partial cylinder,
  and one full cylindrical lateral face.
- Every face has one outer wire and no holes or nested boundaries.
- There are no degenerate edges, poles, singular parameter regions, cones,
  spheres, tori, offsets, intersections, B-spline curves, or B-spline surfaces.
- P-curve branches are observed through oriented wire occurrences. The Python
  binding's indexed low-level representation enumeration and stored-state
  output are not qualified here.
- Seventeen samples can miss a localized deviation between samples. This
  release does not establish an adaptive or mathematically exhaustive check.
- One pinned OCCT build performs construction and STEP import. No independent
  shape kernel or external writer is compared.
- STEP entity counts depend on the selected writer and its surface-curve mode.
- Imported edge tolerances depend on the pinned reader and translation
  settings and are not generalized to other systems.
- The native geometry route does not admit arbitrary untrusted STEP input and
  is not isolated as a hardened parser boundary.
- The study does not edit geometry, repair invalid edges, prove wire closure,
  or implement a modeling operation.

## Open Questions

1. How can the Python route reliably distinguish a stored planar p-curve from
   one generated on demand?
2. Which ordering of curve-existence, range, endpoint, p-curve, tolerance, and
   wire-closure checks is safe before any repair is considered?
3. How should degenerate edges at sphere or cone singularities be represented
   when they have a p-curve but no useful-length 3D curve?
4. Should consistency sampling adapt to curvature, spline knots, and edge
   tolerance instead of using a fixed sample count?
5. How should analysis-local identities be linked across import, repair, and
   export without claiming that traversal indices are persistent names?

## Sources

- [OCCT `BRep_Tool` reference](https://dev.opencascade.org/doc/refman/html/class_b_rep___tool.html)
  documents 3D-curve and p-curve access, curve ranges, edge tolerance,
  `SameParameter`, `SameRange`, degenerate state, vertex parameters, and the
  two-p-curves-on-one-face seam condition. It also warns that a planar p-curve
  may be generated rather than stored.
- [OCCT `BRepAdaptor_Curve` reference](https://dev.opencascade.org/doc/refman/html/class_b_rep_adaptor___curve.html)
  documents treating a topological edge as a 3D curve, including local
  locations, parameter evaluation, and analytic curve classification.
- [OCCT `ShapeAnalysis_Edge` reference](https://dev.opencascade.org/doc/refman/html/class_shape_analysis___edge.html)
  documents curve and p-curve existence queries, seam analysis, oriented
  parameter access, and sampled same-parameter deviation checks.
- [OCCT `Geom_CylindricalSurface` reference](https://dev.opencascade.org/doc/refman/html/class_geom___cylindrical_surface.html)
  gives the cylindrical parameter equation and states that the surface is
  closed and periodic in U but not in V.
- [OCCT STEP translator guide](https://dev.opencascade.org/doc/overview/html/occt_user_guides__step.html)
  documents STEP p-curve translation and the writer option controlling whether
  parameter-space curves are emitted.
- [Public STEP schema view for `surface_curve`](https://www.steptools.com/stds/stp_aim/html/t_surface_curve.html)
  shows the public schema relationships among the 3D curve, associated p-curves
  or surfaces, and preferred representation.
- [Public STEP schema view for `pcurve`](https://www.steptools.com/stds/stp_aim/html/t_pcurve.html)
  shows that a p-curve associates a support surface with a representation
  containing a two-dimensional curve.
