# 研究用3D基盤の安定版 / Cad Stable Release

## 日本語概要

v1.0.0では、解析・編集・再計算・検証・出力を、明示した対応範囲で安定提供します。設計履歴の復元、完全なSTEP適合、汎用CADの代替を意味しません。詳細は英語本文に示します。

---

## English Summary

The first stable release connects source-preserving intake, bounded interpretation, geometry inspection, confirmed reconstruction, transactional edits, comparison and STEP output. Stability applies to the frozen interfaces and measured corpus. Read the support contract before interpreting a successful case as evidence for arbitrary CAD files or production use.

## Evidence and Reproduction

- [CSV observations](../results/cad_stable_release.csv)
- [Detailed evidence](../results/cad_stable_release_evidence.json)
- [Contract](../results/cad_stable_release_contract.json)
- [HTML report](../results/cad_stable_release.html)
- [Input manifest](../fixtures/cad-stable-release/manifest.csv)

```bash
python experiments/run_cad_stable_release.py
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
