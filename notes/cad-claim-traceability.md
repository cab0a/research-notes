# 仕様・実装・証拠の対応表 / Cad Claim Traceability

## 日本語概要

v0.97.0では、対応する主張を一次資料、実装箇所、固定入力、観測値、テスト、制限へ対応付けます。部分対応・実験段階・非対応も表から除外しません。詳細は英語本文に示します。

---

## English Summary

Nine claim records map public specifications or project contracts to implementation entry points, fixtures, tests and observations. Claim status distinguishes supported, bounded, partial, experimental and unsupported behavior. Existence checks prevent broken implementation and fixture references; they do not constitute formal verification of the governing standards.

## Evidence and Reproduction

- [CSV observations](../results/cad_claim_traceability.csv)
- [Detailed evidence](../results/cad_claim_traceability_evidence.json)
- [Contract](../results/cad_claim_traceability_contract.json)
- [HTML report](../results/cad_claim_traceability.html)
- [Input manifest](../fixtures/cad-claim-traceability/manifest.csv)

```bash
python experiments/run_cad_claim_traceability.py
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
