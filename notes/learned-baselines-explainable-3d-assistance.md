# Learned Baselines and Explainable 3D Assistance

## 日本語概要

この研究は、v0.53.0の合成3Dデータ集合で、限定規則方式、幾何量方式、面隣接グラフ方式、両者を使う表形式方式を比較します。学習、確率調整、試験の形状系列を分離し、各判断へ元STEPの要約値と影響の大きい記述子を結び付け、確信度が低い場合は判定を保留します。小規模な二値評価であり、実製品の認識性能や確率の正しさを保証しません。詳細は英語本文に示します。

---

## English Summary

This study compares one bounded rule and three NumPy nearest-centroid baselines on family-isolated synthetic STEP data. Fit, calibration, evaluation, evidence links, and abstention remain explicit.

## Research Question

Can a small learned baseline add measurable assistance without hiding dataset leakage, unsupported families, descriptor evidence, or the distinction between a score and a calibrated probability?

## Background

The v0.53.0 dataset deliberately isolates construction families. Its binary target means “supported by the bounded repository feature rules,” not “contains a manufacturing feature.” A model must therefore retain the local target definition and must not promote high synthetic accuracy into a general CAD claim.

## Method

Four deterministic methods are evaluated: a bounded descriptor rule, a geometry-only nearest-centroid model, a graph-only nearest-centroid model, and a combined tabular nearest-centroid model. Centroids and normalization statistics use only the train split. A small temperature grid is selected by validation Brier score. The test split remains untouched until evaluation.

Every prediction records its STEP digest, raw binary prediction, supported probability, confidence, selective decision, most influential descriptor, observed value, and evidence direction. Confidence below 0.70 produces `abstain`.

## Controlled Experiment

The task has 36 samples and two local labels: `supported` and `none`. The test families are a fillet and an unsupported torus. Results are reported for all splits, with raw accuracy, selective accuracy, coverage, Brier score, calibration bins, and within-family perturbation stability.

## Results

The bounded rule and combined tabular centroid each reach 100% raw accuracy and 100% coverage on the eight held-out samples. The graph centroid reaches 100% raw accuracy but decides only four samples at 100% selective accuracy. The geometry centroid reaches 12.5% raw accuracy and makes four decisions, all incorrect. Validation raw accuracy is 66.7% for the bounded rule, graph centroid, and tabular centroid, and 33.3% for the geometry centroid. These exact counts expose the external cylindrical boss as a difficult negative and show why coverage, held-out family identity, and abstention must accompany accuracy.

## Interpretation

This is an assistance contract: predictions remain linked to source evidence and can be withheld. A descriptor contribution explains which numeric field moved a nearest-centroid decision; it does not prove a causal geometric reason. Temperature selection reduces one validation loss over a tiny grid but does not establish calibration.

## Failure Modes

- Nearest centroids impose a simple class geometry and can fail on multimodal families.
- One negative construction family in training provides weak coverage of the unsupported class.
- Held-out feature classes make multiclass feature naming inappropriate.
- Confidence can be high for a systematically wrong model.
- Descriptor explanations omit face-local evidence and interactions.

## Practical Guidance

Keep the target definition beside every score. Fit preprocessing on train only, calibrate on a separate split, report coverage with selective accuracy, preserve source hashes, and require abstention when confidence or schema support is insufficient.

## Limitations

The study uses 36 synthetic STEP files, one binary target, four simple methods, and one writer/reader route. It does not evaluate graph neural networks, point clouds, meshes, industrial CAD, assemblies, adversarial inputs, cross-kernel transfer, or human decision quality.

## Sources

- [scikit-learn probability calibration guide](https://scikit-learn.org/stable/modules/calibration.html) explains reliability diagrams, calibration data separation, and the distinction between discrimination and calibration.
- [scikit-learn common pitfalls](https://scikit-learn.org/stable/common_pitfalls.html) documents preprocessing and model-selection leakage risks.
- [SketchGraphs](https://arxiv.org/abs/2007.08506) describes geometric constraint graphs for large-scale CAD sketch learning; this study uses a much smaller face-graph setting and makes no comparable scale claim.
- [Joshi and Chang’s attributed-adjacency graph paper](https://doi.org/10.1016/0010-4485(88)90050-4) motivates graph attributes for bounded feature recognition.
