# APIと配布契約の固定 / Cad Contract Freeze

## 日本語概要

v0.98.0では、v0.87で導入したAPI 1.0の呼出し・結果・エラー契約を維持し、CLI、出力方針、資源制限を固定します。クリーン環境でwheelを読み込み、編集・出力まで確認します。詳細は英語本文に示します。

---

## English Summary

The frozen contract retains v0.87 API signatures, envelopes, statuses, error codes and revision semantics. It records console commands, three STEP writer modes and worker budgets. Packaging checks exercise a wheel outside an editable checkout. Private modules and diagnostic payload internals remain research interfaces; third-party STEP notices remain separate.

## Evidence and Reproduction

- [CSV observations](../results/cad_contract_freeze.csv)
- [Detailed evidence](../results/cad_contract_freeze_evidence.json)
- [Contract](../results/cad_contract_freeze_contract.json)
- [HTML report](../results/cad_contract_freeze.html)
- [Input manifest](../fixtures/cad-contract-freeze/manifest.csv)

```bash
python experiments/run_cad_contract_freeze.py
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
