# Feature Recognition Robustness and Benchmarking

## 日本語概要

この研究は、既存の穴・段差・溝・面取り状・丸み状の幾何規則を、縮尺、回転、許容差変更、修復、STEP往復の条件で評価します。合成形状の作成履歴を正解として、正答、負例の拒否、判定保留、誤判定を分離します。結果は限定された規則の挙動であり、一般的な製造形状の認識精度や元の設計履歴の復元を意味しません。詳細は英語本文に示します。

---

## English Summary

This study evaluates bounded geometric feature rules across controlled scale, orientation, tolerance, healing, and STEP-exchange perturbations. Generated construction labels remain separate from inferred geometry.

## Research Question

Which v0.40.0 feature rules remain stable under declared perturbations, and where should the analyzer reject or abstain instead of returning an unsupported feature claim?

## Background

An attributed face-adjacency graph can expose geometric and topological patterns useful for feature recognition, but a matching boundary pattern does not recover authoring history. The v0.51.0 graph contract also showed that analysis-local face identifiers are not persistent CAD names. A benchmark therefore needs construction truth outside the recognizer, explicit perturbations, negative controls, and outcomes richer than a single accuracy value.

## Method

Eight synthetic families are crossed with four perturbations: baseline, uniform half scale, a 30-degree rotation about the global Z axis, and a tolerance assignment followed by bounded shape fixing. Six families contain a supported feature candidate; a plain block and an external cylindrical boss are negative controls. Every case is evaluated before and after deterministic STEP exchange.

The benchmark records `accept`, `reject`, `abstain`, and `incorrect` separately. A missing supported feature under a documented rule-domain violation is an abstention. A negative control with no supported pattern is a rejection. Construction labels are never inferred from the STEP file.

## Controlled Experiment

The corpus contains 32 generated cases, 32 committed STEP files, and 64 observations. Uniform scaling changes length truth but not angle truth. Rotation intentionally challenges rules that use global-axis alignment. The tolerance-and-healing condition changes stored tolerances without pretending to reproduce arbitrary damaged models.

## Results

The committed CSV files report confusion counts and perturbation-specific outcomes. Baseline and half-scale cases preserve classification and controlled dimensions before and after STEP. The rotated controls expose the global-axis assumption as explicit abstentions. Both negative families remain rejected. STEP exchange does not change any observed label or terminal decision in this corpus.

## Interpretation

The experiment is valuable because failures are localized to declared rule assumptions. A rotation-related abstention is more informative than silently converting a missing pattern into a negative feature claim. The stable scale response shows that the tested measurements are dimensional rather than tied to one absolute size.

## Failure Modes

- Global-axis predicates can miss otherwise equivalent rotated features.
- A geometric candidate cannot distinguish a chamfer operation from a directly constructed equivalent bevel.
- Assigned tolerances and generic shape fixing can hide which earlier operation created an inconsistency.
- A single observed candidate inventory can be incomplete for interacting or overlapping features.

## Practical Guidance

Treat rule scope, reason codes, and abstention as part of the public result. Keep generated history labels outside graph features, group results by perturbation, and compare constructed and imported stages. Do not convert benchmark accuracy into a quality threshold for unrelated STEP files.

## Limitations

The corpus contains eight families and four perturbations on one pinned OCCT route. It is not a production distribution, a complete machining-feature taxonomy, a damage simulator, or cross-kernel evidence. Rotations cover one axis and one angle. Healing is bounded and does not establish safe repair of arbitrary files.

## Sources

- [Joshi and Chang, “Graph-based heuristics for recognition of machined features from a 3D solid model”](https://doi.org/10.1016/0010-4485(88)90050-4) introduces attributed adjacency graphs for bounded feature-recognition rules.
- [Open CASCADE `ShapeAnalysis` reference](https://dev.opencascade.org/doc/refman/html/class_shape_analysis.html) documents topology, tolerance, wire, bound, and consistency analysis services.
- [Open CASCADE `ShapeFix_Wire` reference](https://dev.opencascade.org/doc/refman/html/class_shape_fix___wire.html) documents precision-aware wire repair controls and their required context.
- [NIST STEP File Analyzer User’s Guide](https://nvlpubs.nist.gov/nistpubs/ams/NIST.AMS.200-4.pdf) provides a public example of source-linked STEP analysis and validation reporting.
