# 実測のクロスプラットフォーム再現性 / Cad Platform Reproducibility

## 日本語概要

v0.91.0では、Linux、Windows、macOS Intel・arm64の4環境で、構文判定・形状測定・拘束・再計算・出力を比較します。仮想のOS結果は使わず、依存バージョンとソースの識別値を記録します。詳細は英語本文に示します。

---

## English Summary

Four actual runners compare exact classifications and source hashes, with relative 1e-6 and absolute 1e-7 tolerances for geometric observations. Each environment records its OS, architecture, Python, OCP and runtime digest. Agreement is limited to the fixed corpus.

## Evidence and Reproduction

- [CSV observations](../results/cad_platform_reproducibility.csv)
- [Detailed evidence](../results/cad_platform_reproducibility_evidence.json)
- [Contract](../results/cad_platform_reproducibility_contract.json)
- [HTML report](../results/cad_platform_reproducibility.html)
- [Input manifest](../fixtures/cad-platform-reproducibility/manifest.csv)

```bash
python experiments/run_cad_platform_reproducibility.py
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
