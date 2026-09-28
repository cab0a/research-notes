# 安定版候補の受入検証 / Cad Release Candidate

## 日本語概要

v0.99.0では、固定入力を再生成し、全テストと実測4環境の結果を確認します。コードと依存定義の識別値が実測記録に一致することを受入条件にします。詳細は英語本文に示します。

---

## English Summary

The candidate gate joins the eight stabilization studies and four actual platform observations, checks the tested runtime digest, and publishes accepted limitations. Full-suite CI and package checks are recorded separately with their run identities. Old runner observations cannot qualify a changed runtime.

## Evidence and Reproduction

- [CSV observations](../results/cad_release_candidate.csv)
- [Detailed evidence](../results/cad_release_candidate_evidence.json)
- [Contract](../results/cad_release_candidate_contract.json)
- [HTML report](../results/cad_release_candidate.html)
- [Input manifest](../fixtures/cad-release-candidate/manifest.csv)

```bash
python experiments/run_cad_release_candidate.py
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
