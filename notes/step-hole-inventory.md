# STEP Hole Inventory Evaluation — v1.8.0

## 日本語概要

STEPから穴の径・位置・数を一覧にできるかを、固定21条件で各3回評価しました。自作15条件は一覧取得8件・保留7件、外部公開STEP6件は全て読込条件で拒否されました。一覧取得した8条件には穴0個の板も含み、確認した穴は計13個です。記録した精度の寸法値は作成式と一致しましたが、一般部品の認識率や測定精度を保証する結果ではありません。画面・CSV・CLI・公開記事を同じ実測結果に結び付けます。英語本文で方法と限界を示します。

---

## English Summary

A conservative single-STEP inventory extends the local research CAD workflow
to separated Z-axis cylindrical through holes and flat-bottom blind holes in
axis-aligned rectangular plates. Fifteen independent authored controls and all
six frozen external STEP sources were evaluated three times. Eight authored
cases complete, seven abstain, and all external inputs are rejected by intake.
The eight complete cases contain 13 holes, including a separately verified zero
case. Recorded dimensions match analytic truth at the reported precision. All
21 expected handling contracts pass; that includes abstention and rejection,
not a 100% general hole-recognition accuracy claim.

## Question and method

Can a received STEP produce a useful table of hole diameter, location and count
without misinterpreting unsupported cylindrical geometry as a confirmed list?
The [inventory implementation](../src/research_notes/hole_inventory.py) first
uses the existing explicit-mm single-root/single-solid importer. Surface
descriptors reconstruct a box with cylindrical cuts. Symmetric material volume
and surface-area residuals must pass the inherited tolerance gates before any
whole-part inventory is returned. Bosses and counterbores are not counted merely
because they contain cylindrical surfaces. Unsupported cases have no count.

The [fixture constructor](../experiments/build_hole_inventory_fixtures.py) uses
OCCT boxes, cylinders, Boolean operations and transforms independently of the
recognition functions. Analytic recipes and expectations in
[the manifest](../fixtures/hole-inventory/manifest.json) are fixed before audit.
The recognizer receives only source bytes and name. The audit checks status,
count, missing/spurious rows, types, axis vectors and five dimensions per hole.
Faces are source-local rendering references, not independent identity truth.
Simple curated shape families and the shared OCCT kernel limit independence.

## Observations

| Input group | Complete inventory | Geometry unresolved | Intake rejected |
| --- | --- | --- | --- |
| 15 authored controls | 8 | 7 | 0 |
| 6 external sources | 0 | 0 | 6 |

Three repeated non-timing results agree for every source. Recorded numeric
dimension error is 0.0 mm relative to analytic recipes at output precision;
the shared surface descriptor rounds cylinder X/Y/radius to nine decimal
places. This is not a statement of metrological accuracy or exact arithmetic.
Timing observations include parsing/import, qualification and tessellation,
exclude input reading and artifact output, and retain the first run.
Python 3.12.14 with cadquery-ocp 7.9.3.1.1 on Linux is the recorded local runtime.

| Confirmed example | Observation in mm |
| --- | --- |
| Three diameters | Ø1.2 at (3,3), Ø2 at (6,5), Ø2.5 at (9,7); opening Z4, depth4 |
| Mixed holes | Through Ø1.6 at (3,5), depth4; blind Ø2 at (9,5), depth3; both opening Z4 |
| Bottom blind | Ø2 at (6,5), opening Z0, depth2, inward axis (0,0,1) |
| Translated plate | Ø2 at (36,-15), opening Z11, depth4; source coordinates preserved |
| Plain plate | complete, hole_count=0; summary retained in CSV |
| Counterbore / boss | unresolved, hole_count=null; CSV count empty, reason retained |

Six external inputs retain the original corpus provenance and licenses.
The rejection reasons are recorded individually in JSON: this restrictive
application importer differs from the earlier general public-part inspection
experiment. Their failure here does not mean STEP lacks holes or cannot be
imported by other paths. No external-part inventory success is established.

## Artifacts and reproduction

- [Measured JSON](../results/hole-inventory/results.json) binds runtime source and manifest hashes.
- [Summary CSV](../results/hole-inventory/results.csv) retains all 21 dispositions and timings.
- [Per-source CSVs](../results/hole-inventory/csv/) include a summary and confirmed hole rows.
- [Measured figures](../results/hole-inventory/figures/) use the same geometry projection as saved evidence.
- [Licensed archive](../results/hole-inventory/samples.zip) contains 21 STEP inputs and provenance.
- [Verification record](../results/hole-inventory/verification.json) distinguishes completed checks and limitations.
- [Local operation guide](../docs/cad-hole-inventory.md) defines coordinates, statuses and commands.

```bash
python -m pip install -e ".[geometry]"
python -m research_notes.hole_inventory_benchmark --output-dir output/hole-check --repeats 3
python -m research_notes.hole_inventory fixtures/hole-inventory/sources/multiple_diameters.step --output-dir output/my-holes
python -m research_notes.cad_web
```

Open `http://127.0.0.1:8767/holes`. CLI output is verified; browser automation
covers loading, selection, rotation, zero and unresolved states. HTTP controls
check CSV bytes, headers, stale state and Origin/token rejection. The in-app
browser Blob-save click does not yield a filesystem download event in this
verification environment; that final filesystem step remains unverified.
Related local tests pass 110 cases. The wheel includes nine browser assets.
These observations do not establish additional OS/architecture support.

The [Insights article](https://inefficiencylab.com/insights/step-hole-inventory/)
uses the same measured evidence and explicit scope. Usable next evaluations
would extend verified intake and handle arbitrary orientation, stepped holes
and face splitting with independent truth; broader support is not claimed here.
