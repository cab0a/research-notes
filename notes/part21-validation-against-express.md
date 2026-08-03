# Part 21 Validation Against EXPRESS

## 日本語概要

この研究ノートは、別々に実装したSTEP Part 21パーサーとEXPRESS semantic graphを結合し、DATA部のschema、entity名、引数数・順序・型、任意値`$`、派生値`*`、集約、`SELECT`、entity参照、継承を段階的に検証します。40組の合成STEP・EXPRESS fixtureは15件受理・21件拒否・4件隔離となり、全期待結果と一致しました。複合entityの構成と局所引数は検査しますが、完全なevaluated set、定数・value instance解決、文字幅、WHERE・UNIQUE、AP242意味論は保留し、完全な規格適合を主張しません。詳細は以下の英語本文に示します。

---

## English Summary

This note connects the source-preserving Part 21 parser to the resolved
EXPRESS declaration graph. A bounded validator binds DATA sections to schemas,
maps record parameters to explicit attributes, checks controlled value domains
and occurrence references, and preserves invalid, deferred, and not-reached
stages instead of collapsing them into one parse result.

## Research Question

Can a small Python implementation distinguish a syntactically readable STEP
exchange from a schema-bound instance whose controlled entity names,
parameters, values, references, and inheritance mapping agree with an EXPRESS
document?

## Background

[ISO 10303-21:2016](https://www.iso.org/standard/63141.html) defines the
physical exchange representation for product data described in EXPRESS. The
public final Edition 3 text separates physical syntax from the mapping rules
that connect parameters to EXPRESS declarations. In particular, the
[simple-entity mapping](https://www.steptools.com/stds/step/IS_final_p21e3.html#clause-12-2-1)
places explicit attributes in declaration order, while the
[internal subtype mapping](https://www.steptools.com/stds/step/IS_final_p21e3.html#clause-12-2-5-2)
places inherited attributes before local attributes, follows `SUBTYPE OF`
order, and ignores repeated ancestor traversal.

The same public text assigns distinct encodings to an absent optional value
and an inherited explicit attribute redeclared as derived. The former uses
`$`; the latter retains the inherited parameter position and uses `*`.
Inverse and ordinary derived attributes do not otherwise create Part 21
parameters. Entity-valued attributes use occurrence names, and forward
references are allowed when a corresponding instance is defined in the
exchange structure.

[ISO 10303-11:2004](https://www.iso.org/standard/38047.html) defines EXPRESS as
a data-specification language. Therefore a resolved declaration graph still
does not execute `WHERE`, `UNIQUE`, derived expressions, functions, or global
rules. This release treats physical syntax, EXPRESS syntax, symbol resolution,
schema binding, instance validation, application semantics, and rule execution
as separate stages.

The public [STEPcode documentation](https://stepcode.github.io/docs/home/) and
pinned source at commit
[`7836a9ec77edf01816720e0c6e2b9529ee210129`](https://github.com/stepcode/stepcode/tree/7836a9ec77edf01816720e0c6e2b9529ee210129)
provide an independent implementation reference for keeping schema
descriptions and exchange instances distinct. STEPcode is not executed as a
conformance oracle in this study.

## Method

`inspect_step_express_validation()` performs the following bounded stages:

1. Parse the Part 21 bytes with exact source spans and resource limits.
2. Parse the EXPRESS bytes and resolve its controlled symbols, types, and
   inheritance graph.
3. Bind each DATA section to one case-insensitively matching schema.
4. Resolve each simple record keyword to one visible entity declaration.
5. Construct the internal-mapping parameter order by traversing immediate
   supertypes in declared order, placing higher ancestors first, and
   deduplicating shared diamond origins.
6. Retain an inherited slot when a subtype redeclares that attribute and
   require `*` when the redeclaration is derived.
7. Check parameter arity and controlled scalar, enumeration, aggregate,
   defined-type, `SELECT`, and entity-reference encodings.
8. Resolve occurrence references globally, including forward references, and
   admit a referenced subtype for an attribute declared as a supertype.
9. Apply explicit instance, parameter, and recursive-value limits.

The value checker covers:

- `INTEGER`, `REAL`, `NUMBER`, `STRING`, `BINARY`, `BOOLEAN`, and `LOGICAL`;
- controlled enumeration membership;
- literal aggregate bounds, list cardinality, and set or `UNIQUE` duplicates;
- direct entity members and typed defined-type members of controlled `SELECT`
  declarations;
- optional explicit omission and qualified derived redeclaration markers.

Complex instances receive structural checks for component names, uniqueness,
ascending encoded-name order, ancestor closure, local parameter arity, and
local value types. The result is then quarantined because complete EXPRESS
evaluated-set semantics and supertype-expression evaluation are not yet
implemented.

## Controlled Experiment

All 40 paired `.step` and `.exp` inputs are generated in Python. Their exact
bytes, SHA-256 digests, conditions, expected decisions, and validation limits
are committed in `fixtures/step-express-validation/manifest.csv`.

The 15 accepted pairs cover simple value domains, optional values, an
enumeration, bounded lists and sets, forward and subtype-compatible entity
references, single and diamond inheritance, entity and typed defined-type
`SELECT` members, a derived redeclaration, direct `USE` visibility, and an
empty entity.

The 21 rejected pairs isolate schema ownership, unknown or abstract entities,
parameter count, invalid `$` and `*` use, scalar and enumeration mismatches,
aggregate cardinality and uniqueness, missing or wrong-kind occurrence
targets, select wrappers, inheritance order, complex-component order, and
failures at the Part 21 syntax, EXPRESS syntax, or EXPRESS resolution stages.

The four quarantined pairs isolate a structurally checked complex instance, a
schema-constant occurrence, a fixed string-width constraint, and a
schema-bound parameter budget.

Run:

```bash
python experiments/run_step_express_validation.py
```

Regenerate the exact fixture corpus in a separate directory:

```bash
python experiments/run_step_express_validation.py \
  --fixture-dir output/fixtures/step-express-validation \
  --output-dir output/step-express-validation \
  --refresh-fixtures
```

## Results

Every paired fixture matched its expected decision and reason code.

| Decision | Expected | Observed |
| --- | ---: | ---: |
| Accept | 15 | 15 |
| Quarantine | 4 | 4 |
| Reject | 21 | 21 |

The committed evidence contains 39 instance rows because five staged failures
stop before instance validation while several accepted reference fixtures
contain two instances.

| Evidence | Valid | Invalid | Deferred |
| --- | ---: | ---: | ---: |
| Instances | 20 | 16 | 3 |
| Parameters | 35 | 13 | 2 |

The internal inheritance control maps `root.label`, `middle.rank`, and
`leaf.score` to three positions in that order. The diamond control maps the
shared `root.label` once, followed by the left, right, and leaf attributes.
The derived-redeclaration control maps the inherited `base.value` position to
`*`. Forward and subtype-compatible references both resolve successfully.

![Part 21 validation against EXPRESS](../results/step_express_validation.png)

These counts describe only the generated corpus. They are not conformance or
interoperability rates for arbitrary schemas or STEP files.

## Interpretation

The main result is the new boundary between parsing and validation. A Part 21
record can be syntactically valid yet fail because its governing schema is
absent, its keyword is not an entity, its parameter count is wrong, or a
reference targets an incompatible entity type. Those failures now retain
separate stage and reason fields.

Attribute-level rows also make inheritance mapping reviewable. The validator
does not infer parameter meaning solely from position in the STEP record; it
records the originating EXPRESS entity and attribute for each controlled
position. This is necessary before a generic STEP graph or B-Rep interpreter
can claim that a numeric value is a radius, coordinate, tolerance, or other
application property.

Quarantine remains a positive design result. The complex instance, constant
reference, width constraint, and resource-limit fixtures are readable enough
to preserve evidence, but the current implementation does not have enough
semantics or budget to call them valid.

## Failure Modes

- Treating a successful Part 21 parse as schema validity admits unknown entity
  names and incorrect parameter counts.
- Flattening inheritance without declared traversal order assigns values to
  the wrong attributes.
- Counting a diamond ancestor once per path shifts every later parameter.
- Treating `$` and `*` as interchangeable loses the distinction between an
  absent optional value and a derived inherited value.
- Validating an entity reference only for existence permits a target whose
  entity type is incompatible with the declared attribute.
- Accepting an unwrapped scalar for a defined-type member of a `SELECT` loses
  the selected type identity.
- Accepting complex component closure as a complete evaluated-set result
  ignores supertype expressions and legal instance combinations.
- Evaluating constants, rules, or external values with unrestricted host code
  would cross semantic, resource, and trust boundaries.

## Practical Guidance

- Report the deepest completed validation stage for every input.
- Preserve the Part 21 source span, EXPRESS attribute origin, expected type,
  raw value, and reason code in one joinable parameter record.
- Resolve all occurrence targets before validating entity-valued attributes so
  forward references remain legal.
- Keep application protocol meaning separate from schema type validity.
- Quarantine legal but unsupported constructs rather than guessing their
  meaning or relabeling them as malformed syntax.
- Use synthetic paired schema and instance fixtures to isolate each mapping
  rule before testing a large public schema.

## Limitations

- This is a controlled validator, not certification against ISO 10303-21 or
  ISO 10303-11.
- The EXPRESS parser still implements an ASCII declaration subset. Extensible
  types, subtype constraints, complete supertype expressions, generic types,
  local scopes, and several redeclaration forms remain unsupported.
- Complex records are structurally inspected but always quarantined after the
  controlled checks because evaluated-set semantics are not implemented.
- Schema constants, value instances, external resources, short names, and
  complete schema identification rules are not resolved.
- String and binary width constraints and non-literal aggregate-bound
  expressions are deferred.
- Complete assignment compatibility, numeric coercion, aggregate element
  compatibility, nested select cases, and all legal Part 21 mappings are not
  covered.
- `WHERE`, `UNIQUE`, derived expressions, functions, procedures, and global
  rules are not executed.
- AP242 product meaning, units, placements, assemblies, geometry, topology,
  tolerances, and B-Rep validity are not evaluated.
- The 40 generated pairs do not establish compatibility with AP242, IFC, a
  production schema compiler, or arbitrary field files.

## Questions Carried Forward

- Which public, redistributable schema subset should be the first large-schema
  integration target?
- How should schema identifiers, versions, short names, and external schema
  catalogs be represented without implicit network access?
- Which supertype-expression and evaluated-set rules are required before
  complex instances can move from quarantine to accept?
- Which assignment-compatibility rules must be complete before validating
  AP242 measure and select patterns?
- Should rule execution produce a separate validation report or extend the
  same parameter-level provenance model?

## Sources

- [ISO 10303-21:2016 catalog page](https://www.iso.org/standard/63141.html)
- [Public final draft of ISO 10303-21 Edition 3](https://www.steptools.com/stds/step/IS_final_p21e3.html)
- [Part 21 simple-entity mapping](https://www.steptools.com/stds/step/IS_final_p21e3.html#clause-12-2-1)
- [Part 21 optional explicit-attribute mapping](https://www.steptools.com/stds/step/IS_final_p21e3.html#clause-12-2-2)
- [Part 21 internal and external subtype mappings](https://www.steptools.com/stds/step/IS_final_p21e3.html#clause-12-2-5)
- [Part 21 derived-redeclaration mapping](https://www.steptools.com/stds/step/IS_final_p21e3.html#clause-12-2-6)
- [Part 21 `SELECT` mapping](https://www.steptools.com/stds/step/IS_final_p21e3.html#clause-12-1-8)
- [ISO 10303-11:2004 catalog page](https://www.iso.org/standard/38047.html)
- [STEPcode documentation](https://stepcode.github.io/docs/home/)
- [Pinned STEPcode source](https://github.com/stepcode/stepcode/tree/7836a9ec77edf01816720e0c6e2b9529ee210129)
- [STEPcode 3-Clause BSD license](https://github.com/stepcode/stepcode/blob/7836a9ec77edf01816720e0c6e2b9529ee210129/COPYING)
