# Fixed Hole Inventory Corpus — v1.8.0

## 日本語概要

自作15条件と、既存の外部公開STEP6件を固定した穴一覧の検証用サンプルです。自作は一覧取得8件・形状保留7件、外部は全6件が読込条件で拒否されます。自作の作成式と正解値を評価前に記録し、認識処理にはSTEPバイト列と名前だけを渡します。公開部品全般の精度を示すコーパスではありません。出所と利用条件は英語本文に示します。

---

## English Summary

The frozen corpus includes 15 independently constructed plate controls and all
six external sources from the earlier public STEP corpus. Analytic recipes and
expected measurements were fixed before evaluation; only STEP bytes and labels
enter the recognizer. Shared OCCT construction and simple curated families
limit independence. The corpus is not a representative industrial accuracy set.

## Inputs and licenses

The [manifest](manifest.json) records source hashes, byte lengths, independent
construction recipes, expected statuses, counts and dimensions. Eight authored
cases complete: no holes, single hole, three diameters, four equal holes, top
blind hole, bottom blind hole, mixed through/blind holes and a translated plate.
Seven abstain: rotated plate, boss, intersecting holes, edge hole, split planar
face, counterbore and tilted hole. Absence of a confirmed list means unknown.

The 15 authored files in `sources/` are Inefficiency Lab controls governed by
[PolyForm Noncommercial 1.0.0](../../LICENSE) and [licensing](../../LICENSING.md).
The six external inputs are referenced from
[the original corpus](../public-step-corpus/README.md), without modification.
Its manifest retains exact upstream URLs, commits, attribution, acquisition
time, SHA-256, license texts and build123d NOTICE. They comprise five part
families: SAM AP203/AP214 are two exports of one family.

CadQuery and build123d sources carry Apache-2.0 terms. The u-blox library's
original permission text permits use, copying, modification and distribution
subject to its retained conditions. External terms are independent of the
repository's own license. The downloadable ZIP includes the original public
manifest, README, licenses and NOTICE, plus the authored license and manifests.
No customer data or customer performance evidence is included.

## Reproduction

Use committed STEP bytes for normal evaluation. The constructor is provenance;
re-running it may change STEP timestamp headers and therefore hashes.

```bash
python -m research_notes.hole_inventory_benchmark --output-dir output/hole-check --repeats 3
python experiments/package_hole_inventory.py
```

The benchmark validates source and external-license hashes before importing.
The package builder validates every source and re-extracted archive member.
Expected rejection of all external inputs is intake evidence, not external
hole-detection success.
