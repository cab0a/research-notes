# 未学習サンプルによるAI支援評価 / Blinded Assistance Evaluation

## 日本語概要

v0.94.0では、事前に条件をコミットしてから20例を評価しました。正解率70%、判断した15例のうち13例正解です。高信頼でも2例を誤判定したため、自動採用は行いません。詳細は英語本文に示します。

---

## English Summary

The v0.77 checkpoint, training samples and threshold were hash-frozen before predictions. Ten new construction families with two variants yield 14/20 top-1 accuracy, 15/20 coverage and 13/15 selective accuracy. Brier score is 0.4092513506 and ECE is 0.3145283064. Six incorrect high-confidence scores include four abstentions; only two are proposed decisions. Evidence coverage is 100%, not correctness.

## Evidence and Reproduction

- [CSV observations](../results/blinded_assistance_evaluation.csv)
- [Detailed evidence](../results/blinded_assistance_evaluation_evidence.json)
- [Contract](../results/blinded_assistance_evaluation_contract.json)
- [HTML report](../results/blinded_assistance_evaluation.html)
- [Input manifest](../fixtures/blinded-assistance-evaluation/manifest.csv)

```bash
python experiments/run_blinded_assistance_evaluation.py
```

To regenerate into a separate directory, use `--output-dir output/release-results
--fixture-root output/release-fixtures --refresh-fixtures`. The platform study
consumes the committed measured runner records; creating fresh observations
requires the CAD platform workflow. The release-candidate and stable studies
also require the preceding eight reports in their output directory.

## Interpretation and Limits

A passing check means the declared case outcome matched; it may record a
rejection, abstention or known unsupported behavior. See the
[v1 support contract](../docs/cad-v1-support.md),
[reproduction guide](../docs/reproducibility.md) and
[capability matrix](../docs/step-brep-capabilities.md). Project and public-source
license terms are preserved; no unrestricted commercial license is implied.

## Primary Sources

- [ISO 10303-21 public edition-3 text](https://www.steptools.com/stds/step/IS_final_p21e3.html), syntax, source transport and exchange structure.
- [OCCT modeling algorithms](https://dev.opencascade.org/doc/overview/html/occt_user_guides__modeling_algos.html), the native geometry implementation boundary.
- [Python subprocess deadlines](https://docs.python.org/3/library/subprocess.html#subprocess.run), worker timeout semantics.

The protocol was frozen in commit `4731ab07e08e099cbedf6c5deda5e83c6b9d83ae` before prediction. [Protocol](../fixtures/blinded-assistance/protocol.json), [hash lock](../fixtures/blinded-assistance/preregistration.json).

The authored shapes are regenerated and compared geometrically. Predictions use the same hash-verified committed STEP bytes on all platforms; native STEP writer spellings need not be byte-identical.
