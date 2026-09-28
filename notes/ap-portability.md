# AP203, AP214 and AP242 Semantic Portability

## 日本語概要

v0.82.0では、AP203・AP214・AP242で製品、形状、単位、出所属性、組立の参照経路を比較する18条件を追加しました。製品名や形状の候補IDを読み取り、元ファイルのSHA-256と位置情報を保ちます。AP名が似ているだけでは対応済みと判定しません。

公開SAMのAP203版とAP214版から各4製品・7表現、CadQueryのサンプルから2製品・2表現を読み取れました。ただし、SAMの形状候補や組立配置には未解決の経路が残ります。これは全規格への適合や編集履歴の復元ではありません。詳細は英語本文に示します。

---

## English Summary

Eighteen controls compare a declared, bounded role profile across three AP
identifiers, plus an explicit AP214 OID spelling found in the original CadQuery
sample. The reader never rewrites source headers or bytes to invoke another AP.

## Method and Evidence

The synthetic cases independently declare each profile and probe product names,
formation subtypes, explicit metre/millimetre scaling and immediate assembly
occurrences. They are role probes, not certified AP-conformant exchange files.
Negative controls retain unknown schema, wrong formation target and missing
unit diagnoses. Three original, licensed files reuse the pinned v0.81 corpus.

| Original input | Product definitions | Qualified representations | Selection |
| --- | --- | --- | --- |
| SAM AP203 | 4 | 7 | 1 unique, 3 ambiguous; assembly placement deferred |
| SAM AP214 | 4 | 7 | 1 unique, 3 ambiguous; placement decoder retains unresolved paths |
| CadQuery cube/cylinder | 2 | 2 | Both unique; multiple transfer roots are not inferred mating constraints |

The SAM root names differ between AP versions. Similar graph roles do not
prove equal product semantics, shape geometry or metadata. The existing
AP242-only API and v0.81 inspection reports retain their historical contract.

## Use

```python
from pathlib import Path
from research_notes.portable_step import inspect_step_file

report = inspect_step_file(Path("fixtures/public-step-corpus/sources/ublox_sam_ap214.step"))
print(report["products"])
print(report["diagnostics"])
```

```bash
python experiments/run_ap_portability.py
```

See [CSV](../results/ap_portability.csv),
[detailed evidence](../results/ap_portability_evidence.json) and
[HTML report](../results/ap_portability.html).

## Sources and Boundaries

The explicit roles are checked against STEP Tools'
[product definition shape](https://www.steptools.com/docs/stp_aim/html/t_product_definition_shape.html),
[shape definition representation](https://www.steptools.com/docs/stp_aim/html/t_shape_definition_representation.html)
and [context-dependent shape representation](https://www.steptools.com/docs/stp_aim/html/t_context_dependent_shape_representation.html)
documentation. Those merged EXPRESS pages include AP-specific differences;
they do not certify these fixtures or justify general AP equivalence.

The code accepts selected simple product/formation attributes, 3D shape
representations and bounded length-unit chains. Colors, classifications,
arbitrary property assignments, full AP242 occurrence alternatives and full
EXPRESS rules remain outside this profile. Legacy AP203 placement is explicitly
deferred. Source attributes are inspected, not preserved by geometry export.
