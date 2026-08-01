# EXPRESS Lexer, Parser, and Schema Model

## 日本語概要

本ノートは、STEP Part 21のentityをschema定義へ接続する前段として、EXPRESS sourceを字句解析し、schema・type・entity・attribute・interface・constant・algorithmの宣言モデルへ変換します。40個の決定論的な合成fixtureで、20件の正常例、19件の構文異常、1件のresource上限超過を検証し、すべて期待どおり判定しました。正常例は元sourceを完全再構成でき、59行の宣言inventoryへ展開されます。ただし、式とalgorithm bodyはsource envelopeとして保持するだけで、symbol resolution、type checking、constraint実行、Part 21 instance検証は行いません。詳細と根拠は以下の英語本文に示します。

---

## English Summary

This study adds a source-preserving lexer, a controlled declaration parser,
and an unresolved schema model for synthetic EXPRESS sources. It deliberately
separates declaration syntax from name resolution, type checking, expression
semantics, and constraint execution.

## Research Question

Can a small Python implementation parse enough EXPRESS declaration structure
to expose auditable schemas, types, entities, attributes, interfaces, and
algorithm headers without claiming that unresolved names or stored expressions
are semantically valid?

The required output is not one Boolean. It must distinguish lexical validity,
declaration syntax, schema-model construction, symbol resolution, type
checking, and rule execution.

## Background

[ISO 10303-11:2004](https://www.iso.org/standard/38047.html) defines EXPRESS as
a data specification language for data types and constraints on instances of
those types. The ISO scope explicitly separates this language from database,
file, and transfer-format definitions and states that EXPRESS is not a
programming language. The ISO catalog identifies the 2004 publication as
Edition 2 and records its latest confirmation in 2025.

This distinction explains the v0.24 to v0.25 boundary. Part 21 describes a
physical exchange syntax. EXPRESS describes the information model that gives
names, parameter domains, relationships, and constraints to exchanged
instances. A Part 21 parser can expose `#1=ITEM(...)`, but it cannot determine
whether `ITEM` exists, whether its parameter count is correct, or whether a
constraint holds without schema information.

The [STEPcode documentation](https://stepcode.github.io/docs/home/) describes
an open-source EXPRESS schema parser and Part 21 libraries. Its scanner and
grammar at commit
[`7836a9ec77edf01816720e0c6e2b9529ee210129`](https://github.com/stepcode/stepcode/tree/7836a9ec77edf01816720e0c6e2b9529ee210129)
were used as a public implementation reference. In particular, the pinned
[`expscan.l`](https://github.com/stepcode/stepcode/blob/7836a9ec77edf01816720e0c6e2b9529ee210129/src/express/expscan.l)
shows case-insensitive keyword processing, identifiers that begin with a
letter, numeric and binary literal forms, tail remarks, block comments, and
the operator token set. The pinned
[`expparse.y`](https://github.com/stepcode/stepcode/blob/7836a9ec77edf01816720e0c6e2b9529ee210129/src/express/expparse.y)
provides an independently published grammar for schema, entity, type,
interface, attribute, constraint, function, procedure, and rule productions.
STEPcode is distributed under its documented
[3-Clause BSD license](https://github.com/stepcode/stepcode/blob/7836a9ec77edf01816720e0c6e2b9529ee210129/COPYING).
No STEPcode source is copied into this implementation.

The [STEP Tools EXPRESS data-dictionary
documentation](https://www.steptools.com/docs/roselib/data_dictionary.html)
provides a useful architectural comparison: parsed definitions can form a
late-bound dictionary of domains and attributes. The v0.25 Python model follows
that separation in a smaller form, but it is neither binary-compatible with
that dictionary nor a replacement for its compiler.

## Method

The implementation has three layers:

1. `lex_express()` decodes a bounded ASCII source and emits every token,
   whitespace segment, tail comment, and nested block comment with exact raw
   spelling and one-based source coordinates.
2. `parse_express_document()` consumes the significant tokens and constructs
   source-spanned declaration objects.
3. `inspect_express_schema()` reports the syntax decision, model counts,
   feature inventory, exact reconstruction result, and deferred semantic
   stages.

Keywords are matched case-insensitively while raw spelling is retained.
Declaration identifiers are retained exactly; comparisons for duplicate schema,
declaration, and attribute names use case-insensitive keys.

The schema model contains:

- schemas and `USE FROM` or `REFERENCE FROM` interface specifications;
- simple, named, aggregate, `SELECT`, and `ENUMERATION` type references;
- abstract, supertype, and subtype entity header syntax;
- explicit, derived, and inverse attributes;
- labelled `WHERE` and `UNIQUE` expression envelopes;
- constants with typed expression envelopes;
- function, procedure, and rule headers with source-preserved bodies.

This release parses declaration boundaries and balanced delimiters but does not
implement full expression precedence or statement semantics. Expressions and
algorithm bodies therefore have the explicit status `envelope_only`.

## Controlled Experiment

All 40 fixtures are generated by `build_express_schema_fixtures()` and stored
with their exact bytes, active limits, expected decision, reason code, byte
length, and SHA-256 digest. No standards text, vendor schema, customer model, or
business data is included.

The 20 accepted fixtures cover:

- minimal and multiple schema envelopes;
- mixed-case keywords and identifiers;
- tail and nested block comments;
- simple aliases, fixed string width, aggregates, selects, and enumerations;
- explicit, optional, derived, and inverse attributes;
- abstract supertypes and subtype declarations;
- `WHERE` and `UNIQUE` rule envelopes;
- `USE FROM`, renamed imports, and `REFERENCE FROM`;
- constants and function, procedure, and rule envelopes;
- string, encoded-string, binary, integer, and real literal tokens.

The remaining fixtures isolate non-ASCII source, malformed identifiers and
literals, open or unmatched comments, open strings, missing terminators,
case-insensitive duplicate names, empty member lists, incorrect entity or
algorithm endings, unsupported declarations, and a controlled comment-nesting
limit.

## Results

All 40 observed outcomes and reason codes matched their fixture expectations.

| Decision | Expected | Observed |
| --- | ---: | ---: |
| Accept | 20 | 20 |
| Quarantine | 1 | 1 |
| Reject | 19 | 19 |

Every accepted source reconstructed its original ASCII bytes from the complete
token stream. The 20 accepted fixtures produced 59 inventory rows:

| Model item | Count |
| --- | ---: |
| Schema | 21 |
| Interface specification | 2 |
| Type | 5 |
| Entity | 9 |
| Explicit / derived / inverse attribute | 8 / 1 / 1 |
| `WHERE` / `UNIQUE` rule | 2 / 1 |
| Constant | 6 |
| Function / procedure / rule | 1 / 1 / 1 |

![EXPRESS lexer, parser, and schema-model boundary](../results/express_schema_model.png)

These counts describe the synthetic corpus, not the size or complexity of a
production STEP schema.

## Interpretation

The important result is the staged contract. A valid declaration model is more
useful than raw tokens because callers can enumerate entities, distinguish
attribute kinds, inspect aggregate bounds, and retain import and inheritance
syntax. It is still not a resolved schema.

This boundary prevents several misleading conclusions. A parsed named type may
refer to nothing. A `SELECT` member can remain unresolved. An inverse attribute
can name a nonexistent forward attribute. A stored `WHERE` expression can be
syntactically incomplete beyond the balanced envelope. An algorithm body can
contain invalid statements. All these cases require later grammar and semantic
stages.

The source-preserving model is also relevant to future writing and diagnostics.
Normalized identifiers are convenient for lookup, while raw tokens and spans
are required to explain exactly what a schema author wrote.

## Failure Modes

- Treating EXPRESS keywords as case-sensitive rejects valid spelling variants
  and misses collisions such as `item` and `ITEM`.
- Discarding comments and raw token spelling prevents byte reconstruction and
  weakens diagnostics or source-to-source tooling.
- Flattening every type to a string loses aggregate bounds, flags, element
  types, and ordered select or enumeration members.
- Building inheritance edges before resolving imports can attach an entity to
  the wrong declaration.
- Treating balanced expression text as an evaluated constraint creates false
  confidence about schema validity.
- Executing an algorithm or external import during initial parsing crosses a
  separate trust and resource boundary.
- Silently ignoring unsupported top-level declarations makes a partial schema
  appear complete.

## Practical Guidance

- Report lexical, declaration, resolution, type, and execution stages
  separately.
- Preserve source spelling and normalized comparison keys at the same time.
- Keep `USE FROM` and `REFERENCE FROM` distinct until their visibility rules
  are implemented.
- Store named references as unresolved values rather than guessing a target.
- Apply explicit byte, token, declaration, nesting, and token-length limits
  before accepting arbitrary schemas.
- Use synthetic positive and negative fixtures for every supported production.
- Do not validate Part 21 instances against this v0.25 model; wait for symbol
  resolution and type checking.

## Limitations

- This is a controlled EXPRESS subset, not ISO conformance certification or a
  complete implementation of ISO 10303-11.
- Source is deliberately restricted to ASCII. Encoded strings are retained,
  not decoded into an international character model.
- Full expression grammar, operator precedence, qualifiers, query semantics,
  statements, local declarations, redeclared attributes, extensible types,
  generic types, schema identification clauses, and several less common
  productions are not implemented.
- Function, procedure, and rule bodies are bounded envelopes, not parsed or
  executable programs.
- Import targets, type names, select members, inheritance, inverse attributes,
  and rule references are not resolved.
- Aggregate bounds and constant expressions are stored but not evaluated.
- Duplicate local declaration and attribute names are checked, but complete
  EXPRESS visibility and uniqueness rules are not.
- The corpus contains 40 generated sources. It does not contain or establish
  compatibility with AP242, IFC, or any other large public schema.
- STEPcode is used as a pinned public implementation reference, not a
  conformance oracle, and is not executed in this experiment.

## Questions Carried Forward

- Should the project continue with an ASCII source contract and decoded encoded
  strings, or implement a broader character model first?
- Which scope and visibility rules are required before an imported name can be
  resolved without ambiguity?
- How should built-in functions and constants be represented in the symbol
  table without confusing them with schema declarations?
- Should expression parsing precede type resolution, or should both be added in
  one staged validator?
- Which small public schemas can be referenced in interoperability tests without
  redistributing restricted standards content?

## Sources

- [ISO 10303-11:2004 catalog page](https://www.iso.org/standard/38047.html)
- [STEPcode documentation](https://stepcode.github.io/docs/home/)
- [Pinned STEPcode source](https://github.com/stepcode/stepcode/tree/7836a9ec77edf01816720e0c6e2b9529ee210129)
- [Pinned STEPcode EXPRESS scanner](https://github.com/stepcode/stepcode/blob/7836a9ec77edf01816720e0c6e2b9529ee210129/src/express/expscan.l)
- [Pinned STEPcode EXPRESS parser grammar](https://github.com/stepcode/stepcode/blob/7836a9ec77edf01816720e0c6e2b9529ee210129/src/express/expparse.y)
- [STEPcode 3-Clause BSD license](https://github.com/stepcode/stepcode/blob/7836a9ec77edf01816720e0c6e2b9529ee210129/COPYING)
- [STEP Tools EXPRESS data dictionary](https://www.steptools.com/docs/roselib/data_dictionary.html)
