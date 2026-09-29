# STEP Revision Evaluation and Public Evidence — v1.6–v1.7

## 日本語概要

新旧STEP比較を22条件で各3回実行しました。自作16組は比較完了9件、一部保留2件、全体保留5件です。外部公開STEP6件は現在の読込条件で全て拒否され、一般部品の比較成功例にはなりません。出所・ライセンス付きの固定サンプル、実測JSON/CSV、比較図、16組のHTMLレポートを公開用に揃えました。104件の関連テストも成功しました。判定・保留・拒否が予定の扱いに一致したことと、変更検出の一般的な精度は区別します。英語本文の要約に続いて結果を示します。

---

## English Summary

This evaluation freezes 16 authored revision pairs and six unchanged external
STEP inputs. Each case runs three times through the v1.5 geometry rules, retained
without threshold tuning. Nine authored pairs complete comparison, two retain
partial ambiguity and five abstain entirely. All six external self-pairs fail
the bounded intake contract, so no external revision-comparison success is
claimed. All 22 expected handling contracts match and repeats retain identical
non-timing results. Reports, figures, JSON/CSV observations, provenance and a
licensed sample archive accompany the Insights article. These are regression
controls, not representative accuracy or customer productivity measurements.

## Question and method

Can a reader reproduce where the current comparator measures a change, and where
it declines to decide? v1.6 fixes the evaluation conditions; v1.7 packages their
evidence for [the Insights article](https://inefficiencylab.com/insights/step-revision-comparison/).

The [fixture constructor](../experiments/build_revision_fixtures.py) uses OCCT
boxes, cylinders, Boolean cuts and transforms independently of the recognition
grammar. Each old/new shape is exported to a separate STEP. The analyzer receives
only bytes and filenames; analytic recipes and expected dimensions enter the
audit afterwards. The [manifest](../fixtures/revision-comparison/manifest.json)
was fixed before evaluation. This small curated set shares a kernel and simple
geometric families with development; it is not an independent learning test set.

All six previously frozen external STEP files are included without selecting
only successful inputs. Each is passed as both old and new to test intake.
There is no authentic manufacturer revision history or inferred truth for them.
SAM AP203/AP214 belong to one part family: six files represent five families.

## Recorded observations

| Group | Compared | Partial | Unresolved | Intake rejected |
| --- | --- | --- | --- | --- |
| 16 authored pairs | 9 | 2 | 5 | 0 |
| 6 external self-pairs | 0 | 0 | 0 | 6 |

The 22 expected handling contracts match; this includes successful refusal and
abstention and must not be described as “100% change-detection accuracy.” The
audit checks disposition, hole-status counts, missing/spurious dimension rows
and old/new/delta values. It does not establish independent face-level precision
or recall. Source-local face identifiers are references, never identity truth.

| Control | Observation |
| --- | --- |
| Same shape, reversed hole construction order | Compared; two holes within tolerance |
| Hole diameter | 2.0 → 2.6 mm, delta +0.6 mm |
| Hole position, equal material volume | X +1.5 mm; Y +0.5 mm |
| Thickness | 4.0 → 5.0 mm, delta +1.0 mm |
| Addition / deletion | Retained hole matches; one added / deleted candidate |
| Ambiguous repeated holes / distant movement | Partial; hole measurements withheld |
| Whole-plate translation / rotation | Unresolved; no automatic alignment |
| Changed outer width / blind hole | Unresolved; outside the grammar |
| Diameter delta 0.000002 / 0.00004 mm | Within / above the 0.00001 mm tolerance |
| Combined diameter and position changes | Compared with all three measured deltas |
| Same material with split planar faces | Unresolved; face splitting remains unsupported |

The 41 measured dimension rows (including unchanged dimensions and the thickness
rows in partial cases) match analytic truth to 0.000000 mm at the recorded
precision. Current descriptors round selected coordinates/radii to nine decimals;
this is not a proof of exact arithmetic or metrology accuracy. An unsupported
change has not been measured simply because its expected abstention passes.

Each case ran three times sequentially. The committed local run totals 32.22 s
inside the measured boundaries. Authored-case medians range from 0.107 to 0.228 s;
external rejection medians range from 0.056 to 2.306 s. Timing includes both
imports, qualification, tessellation and matching; it excludes fixture creation,
file reads and report rendering. The first run is included. These figures are
machine-specific observations, not throughput promises. Runtime identity and
all individual durations are retained in JSON.

## Why the external inputs did not compare

The revision screen reuses a stricter importer than the earlier general
inspection study: explicit SI mm, one length unit/context, one root, one valid
solid/shell, at most 24 faces and 2 MB. The assembly has two solids, the bracket
42 faces, the screw 28 faces, SAM three solids/98 faces, and EMMY 54 solids/399
faces in the earlier recorded inspection. Some are rejected earlier by their
unit contexts; the exact observed first rejection is retained per side in JSON.
No units, topology, or component structure were silently rewritten to admit them.

Thus the earlier public STEP inspection success does not imply support in this
revision comparator. Extending intake and correspondence to those files is future
work. Arbitrary assemblies, split/merged faces, freeform geometry, automatic
alignment, original CAD dimensions/tolerances and authoring history remain outside
this release's claims.

## Artifacts and reproduction

- [CSV observations](../results/revision-benchmark/results.csv) and [complete JSON](../results/revision-benchmark/results.json).
- [Downloadable STEP bundle](../results/revision-benchmark/samples.zip) and [bundle hash](../results/revision-benchmark/bundle.json).
- [Diameter comparison](../results/revision-benchmark/figures/diameter.svg), [equal-volume movement](../results/revision-benchmark/figures/position.svg), [ambiguous holes](../results/revision-benchmark/figures/ambiguous.svg).
- [Diameter report](../results/revision-benchmark/reports/diameter.html), [ambiguous report](../results/revision-benchmark/reports/ambiguous.html), [split-face abstention](../results/revision-benchmark/reports/split_plane.html).
- [Corpus provenance and rights](../fixtures/revision-comparison/README.md).

```bash
python -m pip install -e ".[geometry,test]"
python -m research_notes.revision_benchmark --output-dir output/revision-check --repeats 3
python -m pytest tests/test_revision_benchmark.py tests/test_revision_detection.py tests/test_cad_web.py tests/test_operational_studies.py -k "not artifacts_reproduce" -q
python experiments/package_revision_evidence.py
```

The local regression run passed 104 tests, with five historical artifact
reproduction cases deselected. The corpus checks run in the existing CAD CI
matrix; this local record does not claim the new CI runs have passed.

Normal evaluation never fetches. Every STEP and the original external license
snapshots are checked against SHA-256 before native import. Authored fixtures
use PolyForm Noncommercial 1.0.0; external files retain their separate upstream
terms and notices. Input recipes, code hashes, runtime and conditions are retained.
Native OCCT work is in-process, without a hard native time/memory sandbox.

Reports are static self-contained HTML with embedded SVG and non-executable JSON.
Export timestamps and elapsed times will differ on rerun. Compare input hashes,
classification and measured values, not entire report bytes across executions.
