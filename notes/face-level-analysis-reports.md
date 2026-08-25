# Face-Level Analysis Reports

## 日本語概要

v0.41.0では、各面を一行で記録する版1.0.0のCSV契約を定義し、解析用面番号、親立体・親殻、6種類の曲面、向き、面積、重心、媒介変数範囲、代表法線、曲面固有値、輪郭線・境界辺・公差・隣接面、名前・色と出典を統合します。5個の合成形状を構築時とSTEP再読込後に評価し、各13面の曲面構成と位相属性が一致しました。面番号は段階内だけで有効であり、名前・色は推測せず、STEP形状から取得できない場合を明示します。詳細は以下の英語本文を参照してください。

---

## English Summary

This study defines a versioned, deterministic CSV contract with one row per
analysis-local face. Five synthetic controls cover plane, cylinder, cone,
sphere, torus, and B-spline support surfaces; solid and open-shell ownership;
inner wires; adjacency; tolerance; and explicit metadata provenance. The same
13 faces are measured before and after STEP exchange. All 13 geometry-matched
pairs retain orientation and boundary-count attributes, with a maximum area
difference of `1.0317080523236655e-11` squared model units and a maximum
centroid distance of `2.9535772102134982e-13` model units. Local indices,
parameterization, tolerance, names, and colors remain source-bounded rather
than being promoted to persistent identity or design semantics.

## Research Question

Can the repository expose one stable face-level CSV contract that integrates
topological ownership, evaluated geometry, type-specific surface parameters,
boundary structure, adjacency, tolerance, and metadata provenance without
claiming persistent face identity or inventing unavailable STEP attributes?

## Background

A useful face report sits between raw STEP entities and higher-level feature
recognition. It needs enough geometry and topology to support inspection,
filtering, graph construction, and later visualization, while retaining the
conditions under which each value was obtained.

Three distinctions are essential:

1. A stable column contract is not a persistent naming scheme. A local face
   index identifies one row only within one `control_id` and `stage`.
2. Surface parameters and UV bounds describe a parameterization, not the
   complete trimmed material region or a three-dimensional bounding box.
3. A name or color is an attributed value only when its source is known. A
   plain topological shape does not justify reconstructing presentation data.

The report therefore represents nullable values explicitly and carries
separate `name_source` and `color_source` columns.

## Source Review

The selected backend route follows the official Open CASCADE interfaces:

- [`BRepAdaptor_Surface`](https://dev.opencascade.org/doc/refman/html/class_b_rep_adaptor___surface.html)
  adapts a face to its located support surface and exposes restricted
  parameter ranges, analytic surface accessors, B-spline accessors, points,
  and derivatives.
- [`BRepGProp`](https://dev.opencascade.org/doc/refman/html/class_b_rep_g_prop.html)
  computes exact-surface area and surface centroid when triangulation is not
  requested.
- [`BRepTools`](https://dev.opencascade.org/doc/refman/html/class_b_rep_tools.html)
  provides face UV bounds and identifies the outer wire.
- [`BRep_Tool`](https://dev.opencascade.org/doc/refman/html/class_b_rep___tool.html)
  returns the stored face tolerance.
- [`TopExp`](https://dev.opencascade.org/doc/refman/html/class_top_exp.html)
  enumerates subshapes and ancestor relationships. This study assigns indices
  from one local traversal rather than treating those indices as STEP or CAD
  identity.
- [`STEPCAFControl_Reader`](https://dev.opencascade.org/doc/refman/html/class_s_t_e_p_c_a_f_control___reader.html)
  documents the XCAF route that supports names and colors in addition to basic
  STEP shape transfer.
- [`XCAFDoc_ColorTool`](https://dev.opencascade.org/doc/refman/html/class_x_c_a_f_doc___color_tool.html)
  stores and retrieves color attributes in an XCAF document, while
  [`TDataStd_Name`](https://dev.opencascade.org/doc/refman/html/class_t_data_std___name.html)
  represents a name attached to a document label.

The experiment deliberately uses the simpler `STEPControl_Reader` shape route
already selected by the preceding geometry studies. Consequently, imported
name and color cells remain empty and their source columns state why. XCAF
attribute traversal is a separate future experiment, not an inferred result.

## Method

### Stable row identity

The CSV contract version is `1.0.0`. Its primary key is:

```text
(stage, control_id, analysis_face_index)
```

`analysis_face_index` is an ascending, one-based index assigned by the local
topology map. It is not compared directly across construction and STEP import.
Round-trip evaluation instead matches faces by surface type and nearest
centroid, retaining both local indices in a separate evidence table.

### Parent ownership

Each face is joined independently to every local shell and solid that contains
it. Parent columns use ascending indices joined by `|`. An empty parent-solid
cell is meaningful: the B-spline control is an open shell and no solid parent
is invented.

### Surface classification and parameters

The normalized surface families are:

| Surface type | Populated type-specific fields |
| --- | --- |
| `plane` | surface origin, surface X direction, plane normal |
| `cylinder` | surface origin, axis, X direction, radius |
| `cone` | surface origin, axis, X direction, reference radius, signed semi-angle |
| `sphere` | center/origin, axis, X direction, radius |
| `torus` | center/origin, axis, X direction, major radius, minor radius |
| `bspline` | U/V degree, pole count, knot count, periodic flags, rational flags |

The raw kernel enumeration is retained separately in
`kernel_surface_type`. Nonapplicable fields are empty, not zero.

### Geometry and orientation

Area and centroid are evaluated from exact surface geometry. UV bounds come
from the trimmed face. The representative sample first uses the midpoint of
those bounds and has two deterministic fallback positions. The cross product
of the first derivatives gives the support normal; reversed face orientation
reverses the reported normal.

This is one representative normal. It does not establish that derivatives are
nonsingular everywhere or that curvature and orientation are uniform over the
face.

### Boundary and adjacency

The report records:

- one outer-wire count when an outer wire exists;
- the number of other wires as inner wires;
- the number of unique topological boundary edges; and
- distinct adjacent face indices sharing at least one unique edge.

A periodic seam owned twice by the same face is not reported as self-adjacency.
The report counts unique edges rather than ordered edge uses; ordered-use
semantics remain in the v0.33.0 and v0.34.0 studies.

### Name and color provenance

Constructed-stage rows copy shape-level names and RGB colors from the synthetic
control manifest. Their source fields are
`synthetic_control_manifest:shape`. These values demonstrate the CSV
attribution contract; they are not embedded face attributes.

The generated STEP fixtures use the basic shape writer and reader. Imported
rows therefore leave name and RGB values empty and report
`not_present:stepcontrol_topods_shape`. The control-manifest values are not
silently propagated across the exchange boundary.

## Controlled Experiment

Only programmatically generated shapes are used.

| Control | Topology purpose | Expected support surfaces |
| --- | --- | --- |
| `through_hole_solid` | closed solid, shared-edge adjacency, two inner planar wires | 6 planes, 1 cylinder |
| `conical_solid` | closed solid and signed cone parameterization | 2 planes, 1 cone |
| `spherical_solid` | closed periodic analytic surface | 1 sphere |
| `toroidal_solid` | doubly periodic analytic surface | 1 torus |
| `bspline_shell` | open shell with no solid parent and a raised constructed tolerance | 1 bicubic B-spline |

Each control is evaluated immediately after construction, written to a
normalized deterministic STEP fixture, read back, and evaluated again. The
five generated STEP files and their hashes are committed.

![Synthetic face-analysis controls](../results/face_analysis_shapes.png)

## CSV Contract

The primary artifact is
[`face_analysis_report.csv`](../results/face_analysis_report.csv). It contains
the requested fields in one ordered contract:

- source stage, control, fixture name, and fixture SHA-256;
- analysis-local face index and parent solid/shell indices;
- normalized and raw surface type plus topological orientation;
- area, centroid, UV bounds, representative UV, and oriented normal;
- plane, cylinder, cone, sphere, torus, and B-spline parameters;
- outer/inner wire counts, unique boundary-edge count, tolerance, and adjacent
  face indices; and
- name, RGB color, and separate source fields.

[`face_analysis_contract.json`](../results/face_analysis_contract.json)
records the exact 60-column order, primary key, nullable fields, list and
Boolean encodings, units, parameter semantics, fixture hashes, and claim
boundaries. Floating-point values use 17 significant digits so regeneration
does not depend on display rounding.

## Results

![Face-level report coverage](../results/face_analysis.png)

| Observation | Result |
| --- | ---: |
| Synthetic controls / STEP fixtures | 5 / 5 |
| Constructed face rows | 13 |
| STEP-imported face rows | 13 |
| Geometry-matched round-trip pairs | 13 |
| Orientation and boundary-count matches | 13 / 13 |
| Maximum area absolute difference | `1.0317080523236655e-11` squared model units |
| Maximum centroid distance | `2.9535772102134982e-13` model units |
| Constructed / imported faces with inner wires | 2 / 2 |
| Constructed / imported faces without a solid parent | 1 / 1 |
| Constructed faces with manifest name and color | 13 / 13 |
| Imported faces with a STEP/XCAF name or color | 0 / 13 |
| Constructed / imported maximum face tolerance | `2.0e-4` / `1.0e-7` model units |

Both stages contain eight planes and one face from each other supported
surface family. All 13 matched pairs retain orientation, outer-wire count,
inner-wire count, and unique boundary-edge count.

The cone has a constructed semi-angle of approximately `-16.699244234°` and
an imported semi-angle of approximately `+16.699244234°`. The absolute angle
is preserved, but the kernel-selected axis and signed parameterization change.
The report retains the signed values instead of normalizing away this evidence.

The deliberately raised B-spline face tolerance is `2.0e-4` before exchange
and `1.0e-7` after import. This confirms the earlier finding that a face
tolerance is a stage-specific kernel observation, not automatically preserved
design truth.

## Interpretation

The stable report solves a practical integration problem: downstream tools can
read one predictable row shape even when a field is meaningful only for one
surface family. Nullable columns are preferable to invented zeros because zero
can be a valid coordinate or angle.

Parent lists and adjacency convert the face table into an attributed graph
without hiding topology inside an opaque object. The open-shell control is
particularly important because it proves that `parent_solid_indices` can be
empty while `parent_shell_indices` remains populated.

The cone control shows why parameter values must be interpreted together. A
signed semi-angle without its associated axis can appear to change even when
the material boundary is stable. Likewise, UV bounds without a surface type
and parameterization are not portable geometric coordinates.

The metadata result is intentionally negative. The chosen shape-only STEP
route cannot provide document-label names or colors. Recording empty values
with a direct source reason is stronger evidence than copying the synthetic
labels and misrepresenting them as STEP-carried attributes.

## Failure Modes

- Treating `analysis_face_index` as a stable identifier across files,
  operations, readers, or kernel versions.
- Comparing UV bounds without first establishing compatible surface
  parameterizations.
- Interpreting a representative normal as a whole-face normal-validity proof.
- Reading a blank radius, axis, or B-spline field as numeric zero.
- Treating the signed cone semi-angle independently of its axis direction.
- Treating stored face tolerance as manufacturing tolerance or an acceptance
  threshold.
- Inferring a face name or color from a product name, control label, surface
  type, or neighboring face.
- Counting periodic self-seams as adjacency to another face.
- Assuming one parent solid or shell is always sufficient for nonmanifold or
  shared topology; the contract therefore uses lists.

## Practical Guidance

1. Use `(stage, control_id, analysis_face_index)` only as a report-local key.
2. Join faces across transformations through a separate correspondence table
   with explicit geometry, topology, history, and ambiguity evidence.
3. Branch on `surface_type` before consuming nullable parameter columns.
4. Keep UV values in surface-parameter units and three-dimensional values in
   model units.
5. Use `name_source` and `color_source` before displaying or retaining
   metadata.
6. Preserve raw kernel type and signed parameters for auditing even when an
   application also computes a normalized view.
7. Validate arbitrary input and resource use outside this report function;
   this experiment receives already constructed native shapes.

## Limitations

- The corpus contains five small synthetic shapes and 13 faces per stage.
- It does not cover Bezier, offset, extrusion, or revolution support surfaces.
- The B-spline control is one nonrational, nonperiodic bicubic patch.
- The sphere and torus are complete analytic primitives rather than trimmed
  patches with holes or singular neighborhoods beyond their standard seams.
- Round-trip matching uses surface type and nearest centroid; it is evaluation
  evidence, not a supported persistent-naming algorithm.
- Parent indices are local kernel indices, not original STEP entity IDs.
- Names and colors are not read through XCAF in this version.
- Face-level material-side orientation relative to nested solids is not
  separately classified.
- Invalid, self-intersecting, nonmanifold, or repaired inputs are not included.
- Only one pinned OCCT binding and one Linux x64 reference route are evaluated.
- No external production or customer CAD data is used.

## Questions Raised

1. How should XCAF face, shape, instance, and inherited presentation attributes
   be resolved when several labels provide names or colors?
2. Which normalized surface-frame representation is useful without discarding
   the signed parameterization needed for auditability?
3. Should a future general report expose ordered edge uses and seam branches
   in the same file, or keep them in linked edge and wire tables?
4. How can arbitrary-input reporting remain resource-bounded when native
   topology and geometry evaluation are involved?

## Reproduction

```bash
python -m pip install -e ".[geometry,test]"
python experiments/run_face_level_analysis.py
python -m pytest tests/test_face_analysis.py
```

The experiment regenerates the CSV, JSON, PNG, and five STEP fixtures. CI
compares the four text artifacts and the complete fixture directory byte for
byte, and checks that both figures are nonempty.

## Sources

- [Open CASCADE `BRepAdaptor_Surface` reference](https://dev.opencascade.org/doc/refman/html/class_b_rep_adaptor___surface.html)
- [Open CASCADE `BRepGProp` reference](https://dev.opencascade.org/doc/refman/html/class_b_rep_g_prop.html)
- [Open CASCADE `BRepTools` reference](https://dev.opencascade.org/doc/refman/html/class_b_rep_tools.html)
- [Open CASCADE `BRep_Tool` reference](https://dev.opencascade.org/doc/refman/html/class_b_rep___tool.html)
- [Open CASCADE `TopExp` reference](https://dev.opencascade.org/doc/refman/html/class_top_exp.html)
- [Open CASCADE `STEPCAFControl_Reader` reference](https://dev.opencascade.org/doc/refman/html/class_s_t_e_p_c_a_f_control___reader.html)
- [Open CASCADE `XCAFDoc_ColorTool` reference](https://dev.opencascade.org/doc/refman/html/class_x_c_a_f_doc___color_tool.html)
- [Open CASCADE `TDataStd_Name` reference](https://dev.opencascade.org/doc/refman/html/class_t_data_std___name.html)
