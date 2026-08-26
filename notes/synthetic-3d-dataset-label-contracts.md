# Synthetic 3D Dataset and Label Contracts

## 日本語概要

この研究は、合成STEP試料を形状系列単位で学習用、調整用、試験用に分け、正解ラベル、面隣接グラフ、B-rep計測値、画像、元ファイルの要約値を結び付けます。同じ形状系列や同一ファイルが複数分割へ混入しないことを検査します。小規模な合成データ集合であり、実製品の分布や元の設計履歴を表しません。詳細は英語本文に示します。

---

## English Summary

This study publishes a small synthetic STEP dataset with family-isolated splits, construction-truth labels, attributed face graphs, B-Rep descriptors, previews, source digests, and explicit leakage checks.

## Research Question

Can generated STEP controls become an auditable dataset without losing the distinction between construction truth, measured geometry, exchange bytes, and a later model prediction?

## Background

Randomly splitting near-duplicate variants can make evaluation optimistic. The relevant group in this corpus is the construction family: scaled, rotated, healed, and baseline variants share a common lineage even when their bytes differ. Dataset records must therefore preserve a group key and source digest in addition to a class label.

## Method

The dataset reuses the 32 v0.52.0 STEP files by reference and adds four toroidal negative controls. Nine construction families are assigned wholly to one of three splits. Each sample links its external construction label to a STEP digest, B-Rep counts and measures, an attributed face graph, a coarse structural signature, and a preview family.

Five leakage checks cover unique sample IDs, family isolation, digest isolation, file-name isolation, and required provenance. The split is fixed rather than randomly regenerated.

## Controlled Experiment

The 36 samples cover supported hole, step, slot, chamfer-like, and fillet-like candidates plus planar, external-cylinder, and unsupported-torus negatives. The train, validation, and test partitions contain disjoint families. The dataset intentionally does not force every feature class into every partition; held-out families test a harder transfer boundary.

## Results

All 36 samples have STEP digests, construction-truth labels, B-Rep measurements, and graph records. All five leakage checks report zero violations. The four torus controls add a non-planar unsupported surface family to the test partition. The committed split and label summaries make class imbalance visible.

## Interpretation

The main result is the contract, not dataset size. The same sample can be traced from exchange bytes through measured B-Rep and graph features to a label whose source is declared independently. Family isolation prevents exact and transformed members of one construction family from appearing in multiple partitions.

## Failure Modes

- A source digest proves byte identity, not semantic equivalence.
- A family key can be too broad or too narrow for another modeling generator.
- Held-out classes make ordinary multiclass accuracy inappropriate without an unknown-class policy.
- A coarse graph signature can collide for non-isomorphic or geometrically distinct shapes.

## Practical Guidance

Keep construction truth, file provenance, measured descriptors, and predictions in separate fields. Split by the strongest known lineage key before fitting a model. Report classes absent from a split and retain explicit unsupported-surface negatives.

## Limitations

The dataset contains 36 synthetic files, nine families, one STEP writer/reader route, and analytic or simple swept shapes. It is not representative of industrial CAD, assemblies, free-form surfaces, damaged files, proprietary systems, or manufacturing semantics. No third-party CAD data are included.

## Sources

- [NIST MBE PMI Validation and Conformance Testing](https://www.nist.gov/ctl/smart-connected-systems-division/smart-connected-manufacturing-systems-group/mbe-pmi-0) publishes public CAD and STEP testing resources and illustrates the value of declared reference models.
- [Open CASCADE `BRepAdaptor` package](https://dev.opencascade.org/doc/refman/html/package_brepadaptor.html) documents the surface and curve adaptor family used for measured descriptors.
- [Open CASCADE `ShapeAnalysis` reference](https://dev.opencascade.org/doc/refman/html/class_shape_analysis.html) documents topology and geometry consistency analysis services.
- [scikit-learn common pitfalls](https://scikit-learn.org/stable/common_pitfalls.html) explains why preprocessing and model selection must avoid information from held-out data.
