# 文法・幾何の不正入力検証 / Cad Fuzzing

## 日本語概要

v0.92.0では、固定seedで52条件を生成し、Part 21・EXPRESS・位相・トリム・配置・依存グラフの拒否を検証します。NULの扱いの不一致を修正し、縮約した再現入力を保存します。詳細は英語本文に示します。

---

## English Summary

The 52 controls cover truncation, raw NUL, harmless comments, reversed/free topology, self-intersecting trims, improper placement and invalid dependencies. Native geometry workers have a 15-second deadline. A bounded deletion reducer preserves the diagnostic predicate; it is not a proof of global minimality.

## Evidence and Reproduction

- [CSV observations](../results/cad_fuzzing.csv)
- [Detailed evidence](../results/cad_fuzzing_evidence.json)
- [Contract](../results/cad_fuzzing_contract.json)
- [HTML report](../results/cad_fuzzing.html)
- [Input manifest](../fixtures/cad-fuzzing/manifest.csv)

```bash
python experiments/run_cad_fuzzing.py
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

Section 5.2 permits ignored transport octets; rejecting raw NUL is an explicit bounded-profile limitation, not a claim that every such exchange is invalid under the complete standard. The original campaign accepted NUL inside a quoted string while rejecting it elsewhere. Both positions now return `unsupported_transport_control`.
