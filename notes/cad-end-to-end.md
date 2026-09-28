# 読込から編集・再出力までの検証 / Cad End To End

## 日本語概要

v0.96.0では、自作6形状は候補確認・寸法変更・再計算・比較・出力・再読込まで、公開4形状は検査・元データ保持・形状の往復を確認します。公開部品の任意の寸法変更は対応外です。詳細は英語本文に示します。

---

## English Summary

Six authored inputs exercise plate, through-hole, blind-hole, boss, pocket and rib edits. Four licensed public inputs exercise inspection, explicit candidate abstention, exact-byte preservation and measured geometry round trips. The public controls are CadQuery assembly, build123d bracket and u-blox SAM AP203/AP214. Editing claims apply only to qualified reconstructed candidates.

## Evidence and Reproduction

- [CSV observations](../results/cad_end_to_end.csv)
- [Detailed evidence](../results/cad_end_to_end_evidence.json)
- [Contract](../results/cad_end_to_end_contract.json)
- [HTML report](../results/cad_end_to_end.html)
- [Input manifest](../fixtures/cad-end-to-end/manifest.csv)

```bash
python experiments/run_cad_end_to_end.py
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
