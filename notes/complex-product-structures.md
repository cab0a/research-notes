# Complex Product Structures and Representation Selection

## 日本語概要

v0.83.0では、入れ子の組立、同じ部品の再利用、複数の形状候補、表現間の関係を12条件で検証しました。候補が1つなら採用できますが、複数ならIDを一覧にして保留します。利用者が製品定義IDと形状表現IDを指定すると、その候補を明示的に選べます。

再利用された部品は配置経路ごとに区別します。循環、不足した組立関係、解釈できない形状候補も記録し、勝手に省きません。詳細は英語本文に示します。

---

## English Summary

Twelve controls expose selection and unresolved ambiguity for multiple direct
shape associations, related representations, nested reuse and context-dependent
placement. Enumeration is bounded and does not establish geometric equivalence.

## Selection Contract

1. Preserve every qualified direct association and its source IDs.
2. Traverse non-transformed shape relationships with a visited set.
3. List all candidates; a relationship to another representation is not proof
   that the two shapes are geometrically interchangeable.
4. Select only one unique candidate, or an explicit qualified candidate.
5. If an associated candidate cannot be interpreted, retain an unresolved state.
   Selecting a different candidate does not conceal the unsupported alternative.

Transformed relationships belong to the occurrence-placement decoder rather
than the list of product shape alternatives. A representation containing two
solid items retains two model IDs. An explicit product selection does not
silently rewrite the assembly decoder's unresolved placement decisions.

## Findings

The nested fixture has three definitions and four root-relative occurrence
paths. The bolt is reused on three distinct paths, with translations
(10, 0, 0), (20, 0, 0), and (100, 10, 0) mm. The last position combines a
subassembly translation and a 90-degree rotation.

A cyclic representation graph terminates with all three alternatives visible.
An assembly cycle is diagnosed by the existing bounded placement decoder.
Missing context-dependent relationships and reversed representation order
retain non-accepted assembly decisions. All 12 case contracts match.

## Use

At the integrated terminal:

```text
semantics fixtures/complex-product-structures/alternative.step
semantics fixtures/complex-product-structures/alternative.step 6=21
```

In Python, call
`inspect_step_file(path, selections={6: 21})`. Unknown IDs, duplicate terminal
selections and selections hiding an unqualified candidate are refused.

```bash
python experiments/run_complex_product_structures.py
```

See [CSV](../results/complex_product_structures.csv),
[HTML report](../results/complex_product_structures.html) and
[detailed evidence](../results/complex_product_structures_evidence.json).

## Boundaries

Traversal permits at most 4096 representation relationships and 256 candidate
IDs per product by default, within the parser's 2 MB/20,000-entity envelope.
A visited set handles cycles; it does not declare those relationships valid
under a complete schema. No external references are fetched.

The occurrence roles follow the scoped
[STEP Tools assembly usage definition](https://www.steptools.com/docs/stp_aim/html/t_next_assembly_usage_occurrence.html)
and the earlier AP242 placement implementation. Arbitrary configurations,
effectivity, alternate shape placement and STEP metadata-preserving export
remain outside the contract.
