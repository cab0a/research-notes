# STEP Round-Trip Preservation

## 日本語概要

v0.48.0では、名称と色を持つ箱、貫通穴形状、Bスプライン殻を合成し、STEP出力・拡張文書読込・再出力・再読込を行います。3条件すべてで製品数、名称、体積、表面積、位相数、曲面構成、公差、再読込された色一覧が世代間で保持されましたが、正規化後のバイト列まで一致したのは1条件だけでした。また、複合形状の貫通穴では宣言した色が最初のSTEP出力時点で表現されず、その後の空の色一覧だけが安定しました。保持性と入力真値への一致、意味保持とバイト同一性を分離する必要があります。詳細は以下の英語本文を参照してください。

---

## English Summary

This note separates semantic, structural, geometric, topological, attribute,
tolerance, and physical-file outcomes across a controlled XCAF-aware
import-export-import cycle. All three exchanged controls retain the measured
semantic and B-Rep dimensions between imports, while only one pair is byte
identical after narrow normalization. A stable empty color inventory is not
mistaken for successful transfer of the declared source color.

## Research Question

Which dimensions of a controlled STEP document survive an
import-export-import cycle, and when does semantic preservation differ from
physical-file byte identity?

## Background

Open CASCADE documents the shape-only `STEPControl_Reader` result as an
accumulated `TopoDS_Shape`. Its XDE route uses `STEPCAFControl_Reader` and
`STEPCAFControl_Writer` when names, colors, layers, and other document
attributes matter. The writer can create a fresh STEP model from a document,
so entity numbering and serialization choices are not persistent identities.

The experiment therefore does not define preservation as equality of the
whole file. It evaluates independently observable dimensions and records the
normalized bytes as a separate physical representation.

## Method

Three synthetic controls are created without external or business data:

1. one red named analytic box;
2. one green named Boolean through-hole result;
3. one blue named free-form B-spline shell.

Each shape is placed in a new XCAF document with a declared free-shape name and
generic color. The document is written through `STEPCAFControl_Writer`, read
through `STEPCAFControl_Reader`, written again, and read a second time. Known
writer timestamps and counters are narrowly normalized before hashing.

The two imported stages are compared by:

- free-shape and `PRODUCT_DEFINITION` counts for structure;
- imported free-shape names for semantics;
- volume, surface area, and support-surface inventory for geometry;
- unique vertex, edge, face, shell, and solid counts for topology;
- XCAF color-table RGB inventory for attributes;
- maximum vertex, edge, and face tolerances;
- normalized bytes, SHA-256, and file size for physical representation.

## Controlled Experiment

The committed corpus contains six STEP files: a source and re-export for each
control. Every stage is checked by `BRepCheck_Analyzer`. The source-import
observation is also compared with the declared synthetic name and color truth,
because a repeated cycle can preserve an earlier omission.

Reproduce the evidence with:

```bash
python -m pip install -e ".[geometry,test]"
python experiments/run_step_round_trip_preservation.py
python -m pytest tests/test_step_round_trip_preservation.py
```

## Results

| Control | Source name truth | Source color truth | Six semantic/B-Rep dimensions preserved | Normalized bytes identical | File-size delta |
| --- | ---: | ---: | ---: | ---: | ---: |
| Named box | Yes | Yes | 6/6 | Yes | 0 |
| Named through hole | Yes | No | 6/6 | No | -1 byte |
| Named B-spline shell | Yes | Yes | 6/6 | No | 0 bytes |

All six imported shapes are analyzer-valid. Volume, surface area, topology,
surface inventories, and maximum subshape tolerances have zero measured
difference between the two imported generations. Names remain equal to the
declared truth for all three controls.

The through-hole control is a `COMPOUND` result on the selected writer route.
Its declared top-level generic color is absent from the first imported color
table. The second generation preserves that absence. This is recorded as
round-trip attribute stability but failure against source attribute truth.

## Interpretation

Preservation is a relation between explicit observations, not a single yes/no
property. The box demonstrates that byte identity can occur on a bounded
control, but the through-hole and B-spline controls demonstrate that semantic
and geometric preservation do not require it. Conversely, a stable empty
attribute inventory does not prove the intended attribute entered the first
exchange file.

The most useful contract is therefore staged:

1. compare the first written file with independently declared source truth;
2. compare later generations with the first imported baseline;
3. keep byte identity as diagnostic evidence rather than a semantic oracle.

## Failure Modes

- A shape-only reader can retain geometry while discarding document
  attributes.
- A writer can omit or relocate a top-level attribute before the first import.
- Re-export can renumber or reformat equivalent entities.
- Equal topology counts do not establish persistent face or edge identity.
- Equal maximum tolerances can hide different per-subshape assignments.
- A color-table inventory does not prove every intended shape-to-color link.

## Practical Guidance

- Declare which preservation dimensions matter before testing a conversion.
- Compare imported values with external source truth, not only with the next
  generation.
- Use XCAF-aware transfer when names, colors, layers, or product structure are
  required.
- Treat hashes as provenance for exact fixtures, not as a semantic CAD
  equivalence test.
- Require geometry-based correspondence or application identifiers when
  element continuity matters across exchange.
- Report omissions and normalization changes explicitly instead of silently
  accepting a valid shape.

## Limitations

- The corpus contains one free shape per document and does not evaluate a
  nested assembly or external references.
- Only generic color-table RGB inventory and free-shape names are measured.
- Layers, materials, presentation styles, product properties, and PMI are not
  evaluated.
- The color observation does not prove subshape association preservation.
- Geometry equivalence uses global measures, topology counts, and support
  families; it is not a pointwise Hausdorff proof.
- Only one pinned Open CASCADE binding and writer configuration are used.
- No independent geometry kernel is evaluated in this release.

## Sources

- [Open CASCADE STEP translator guide](https://dev.opencascade.org/doc/occt-7.9.0/overview/html/occt_user_guides__step.html)
- [Open CASCADE `STEPControl_Writer` reference](https://dev.opencascade.org/doc/refman/html/class_s_t_e_p_control___writer.html)
- [Open CASCADE XDE user guide](https://dev.opencascade.org/doc/occt-7.9.0/overview/html/occt_user_guides__xde.html)
- [STEPutils Part 21 document model](https://github.com/mozman/steputils/blob/master/docs/source/p21.rst)
