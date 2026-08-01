# Unified Part 21 Lexer, Grammar, and Source Model

## 日本語概要

本研究は、v0.21とv0.22で分かれていたSTEP Part 21読み取り処理を一つのPython基盤へ統合し、元の綴り・空白・コメント・文字位置・byte位置を保持したまま構文モデルを作れるかを検証します。10個の合成fixtureのうち5件をaccept、resource上限2件をquarantine、構文またはencoding異常3件をrejectに分類しました。acceptした5件は元のUTF-8 bytesを完全再構成し、閉じた四面体は74 entities・97 referencesと従来の面・辺・シェル・立体解析を維持しました。これは限定したPart 21構文の結果であり、完全な版間適合、EXPRESS・AP242適合、幾何妥当性、書き戻し互換性は主張しません。詳細は以下の英語本文に示します。

---

## English Summary

This study replaces two experiment-specific STEP readers with one
source-preserving, resource-bounded Part 21 lexer and parser. The concrete
source model retains raw spelling, normalized values, whitespace, comments,
character offsets, UTF-8 byte offsets, line numbers, and columns. Ten
synthetic fixtures separate accepted syntax, localized syntax failures, and
resource-limit quarantine. All five accepted fixtures reconstruct their exact
input bytes. EXPRESS schema conformance remains explicitly unevaluated.

## Research Question

Can one small Python parser provide a shared Part 21 foundation for the v0.21
B-Rep topology experiment and the v0.22 exchange-structure experiment while
retaining enough source evidence for precise diagnostics and future schema
validation?

The study asks four narrower questions:

1. Can grammar tokens and otherwise discarded whitespace and comments coexist
   in one complete token stream?
2. Can every parsed record and entity retain exact character, UTF-8 byte,
   line, and column coordinates?
3. Can simple records, subsuper records, and forward references share one
   parser without changing the published v0.21 and v0.22 observations?
4. Can syntax failures and configured resource limits produce distinct,
   localized, fail-closed outcomes?

## Background

[ISO 10303-21:2016](https://www.iso.org/standard/63141.html) defines a clear-text
exchange format for product data described using EXPRESS. The
[public final edition-3 draft](https://www.steptools.com/stds/step/IS_final_p21e3.html)
describes the exchange structure with a context-free grammar and states that
syntactic conformance is a prerequisite for schema conformance. That ordering
is central to this implementation: successfully building a Part 21 source
model does not prove that an entity exists in the declared schema or that its
parameters have valid types.

The earlier repository studies had two valid experimental purposes but
duplicated their parser mechanics:

- v0.21 parsed one unparameterized DATA section and converted selected entity
  records into controlled B-Rep topology observations.
- v0.22 parsed edition-3 exchange sections, multiple DATA sections, complex
  records, anchors, external references, signatures, and container boundaries.

Keeping both tokenizers would make later EXPRESS diagnostics and source
comparison ambiguous. The new shared layer therefore owns decoding,
tokenization, grammar construction, source coordinates, section validation,
and resource budgets. The old public functions remain compatibility adapters
over that layer.

Public OSS provides useful comparison points without defining this study's
claim boundary. [STEPcode](https://stepcode.github.io/docs/home/) includes
Part 21 read/write support and an EXPRESS parser. The
[IfcOpenShell physical-file parser](https://github.com/IfcOpenShell/step-file-parser)
demonstrates a pure-Python parser with line and column diagnostics. Their
existence motivates independent comparison in v0.24; this release does not
claim behavioral equivalence with either implementation.

## Method

### Layered implementation

`src/research_notes/step_part21.py` now provides:

- explicit limits for file bytes, tokens, entity instances, occurrence
  references, nesting depth, and token characters;
- UTF-8 decoding before grammar interpretation;
- lexical tokens for identifiers, numbers, strings, binary values,
  enumerations, occurrence references, resources, punctuation, comments, and
  whitespace;
- exact raw spelling and a normalized value for every token;
- half-open character and byte ranges plus one-based line and column
  coordinates;
- a concrete document model for header records, anchors, external references,
  DATA sections, simple and complex entities, values, and signatures;
- stable parser decisions and reason codes with an optional source span.

`step_brep.py` and `step_exchange.py` convert the shared model into their
existing study-specific representations. They no longer contain independent
tokenizers or grammar streams.

### Source retention contract

The parser retains all decoded characters as tokens, including trivia. For an
accepted input, the experiment verifies both relations:

```text
concatenate(token.raw for every token) == decoded source text
decoded source text encoded as UTF-8 == original input bytes
```

Semantic names may be normalized for lookup, but `raw` remains unchanged. A
future writer can therefore choose between exact-source preservation and an
explicit canonicalization policy instead of silently losing the original
form.

### Validation stages

This study records the stages separately:

```text
UTF-8 decoding
    -> lexical tokenization
    -> Part 21 grammar construction
    -> bounded exchange-structure checks
    -> EXPRESS schema conformance: not evaluated
    -> application semantics: not evaluated
    -> geometry evaluation: not evaluated
```

The word `accept` in the CSV means that the controlled source-model stage
passed. It is not a claim of complete ISO 10303-21, EXPRESS, AP242, or B-Rep
validity.

## Controlled Experiment

The experiment generates ten deterministic fixtures under
`fixtures/step-part21-source-model/`:

| Fixture | Controlled condition | Expected route |
| --- | --- | --- |
| `geometry_control.step` | The v0.21 closed tetrahedron through the unified parser | accept |
| `trivia_preservation.step` | Whitespace, two comments, aggregates, and an escaped apostrophe | accept |
| `utf8_coordinates.step` | Direct non-ASCII text followed by another entity | accept |
| `simple_and_complex.step` | Simple and subsuper records in one DATA section | accept |
| `forward_reference.step` | A reference appears before its target definition | accept |
| `missing_semicolon.step` | One entity terminator is absent | reject |
| `unterminated_comment.step` | A comment reaches end of file | reject |
| `nesting_limit.step` | Aggregate depth exceeds a limit of 8 | quarantine |
| `token_length_limit.step` | One string exceeds a limit of 48 characters | quarantine |
| `invalid_utf8.step` | Invalid UTF-8 remains after an otherwise valid exchange | reject |

Every manifest row records the input hash, byte count, expected outcome, and
all six parser limits. The invalid and resource-boundary fixtures remain
synthetic; no external CAD or customer data is used.

Run the study with:

```bash
python experiments/run_step_part21_source_model.py
```

Regenerate the exact fixture corpus in a separate location with:

```bash
python experiments/run_step_part21_source_model.py \
  --fixture-dir output/fixtures/step-part21-source-model \
  --output-dir output/step-part21-source-model \
  --refresh-fixtures
```

## Results

All ten expected routes were reproduced:

| Result | Observed value |
| --- | ---: |
| Fixtures | 10 |
| Accept | 5 |
| Quarantine | 2 |
| Reject | 3 |
| Expectation rate | 1.000000 |
| Exact reconstruction among accepted fixtures | 5 / 5 |
| Token inventory rows | 1,435 |
| UTF-8 fixture byte count minus character count | 7 |

The geometry integration control retained 74 entity instances and 97
occurrence references. The existing topology adapter still resolved four
faces, six edges, one shell, one solid, and zero free edges.

The missing-semicolon diagnostic points to line 9, column 1, where `ENDSEC`
appears instead of the required entity terminator. The unterminated comment
also begins at line 9, column 1. The nesting and token-length cases are
quarantined rather than reported as malformed syntax because the parser stops
at an explicit processing budget.

![Unified Part 21 source-model results](../results/step_part21_source_model.png)

The token-level coordinates and raw spellings are committed in
[`step_part21_token_inventory.csv`](../results/step_part21_token_inventory.csv).
Corpus outcomes are in
[`step_part21_source_model_observations.csv`](../results/step_part21_source_model_observations.csv).

## Interpretation

The central result is architectural rather than geometric. Both previous STEP
studies now consume the same parsed source model, so a later EXPRESS validator
can attach a type or parameter diagnostic to the same source span used by the
lexer and grammar.

Retaining character and byte coordinates matters because UTF-8 breaks the
assumption that one displayed character occupies one byte. In the controlled
UTF-8 fixture, the source contains seven more bytes than Python characters.
The `#2` token after the non-ASCII string therefore has a byte offset larger
than its character offset while remaining at line 9, column 1.

Retaining trivia is also deliberate. Comments and whitespace are not needed
for normalized entity lookup, but discarding them would prevent exact source
comparison and make a later minimally changing writer impossible. The design
keeps normalized semantic values and exact lexical evidence as separate
fields.

## Failure Modes

- A missing delimiter may be reported at the next token rather than at the
  location where a human would have typed the delimiter. The diagnostic still
  identifies the parser's first contradictory token.
- Invalid UTF-8 cannot receive decoded line and column coordinates because no
  text model exists yet. A future diagnostic may add raw byte offsets for
  decode failures.
- Character limits count Python Unicode code points, not grapheme clusters or
  display width.
- Exact reconstruction is tested only after successful UTF-8 decoding. It is
  not a byte-preserving model for arbitrary invalid input.
- Case normalization supports controlled lookup but does not yet publish a
  complete standard-conformance decision for keyword spelling.
- The parser recognizes only the documented edition-3 subset. Legacy string
  control directives and print control directives remain unsupported.

## Practical Guidance

- Use `parse_part21_document()` when source spans, comments, or complex
  exchange sections matter.
- Use `parse_step_part21()` only for the older bounded single-DATA topology
  representation.
- Use `parse_step_exchange()` for the v0.22 structural representation and its
  trust-boundary inventory.
- Treat `Part21SourceSpan` ranges as half-open. The start is included and the
  end is excluded.
- Do not label an input schema-valid because the source parser accepted it.
- Keep external retrieval, signature verification, archive expansion, schema
  evaluation, and native geometry-kernel execution behind separate policies
  and budgets.

## Limitations

- The ten fixtures are controlled examples, not a conformance certification
  corpus.
- Edition-1 and edition-2 differences have not been evaluated systematically.
- Legacy control directives, ECMAScript, value instances, and several
  edition-3 productions remain outside the tested subset.
- The parser does not read EXPRESS source, resolve schema imports, check
  entity declarations, validate parameter types, or execute constraints.
- The implementation has not been differentially tested against STEPcode,
  IfcOpenShell, commercial translators, or arbitrary field files.
- No writer or canonical serializer is provided.
- The geometry control validates parser integration and declared topology
  extraction; it does not independently evaluate surfaces, tolerances, or
  geometric validity.

## Open Questions

1. Should the next parser expose an explicit `syntactically_valid` status
   instead of using the broader decision word `accept`?
2. Which edition-1 and edition-2 lexical distinctions must remain visible
   rather than normalized into the edition-3 model?
3. Should comments attach to the following syntax node, the preceding node,
   or remain only in the complete token stream?
4. How should a future writer distinguish exact preservation, minimal edits,
   and canonical output?
5. What overlap corpus can be checked independently with STEPcode and the
   IfcOpenShell parser without treating implementation agreement as proof of
   standard conformance?

The recommended next release is v0.24.0: build a classified Part 21 grammar
and conformance corpus before starting the EXPRESS lexer.

## Sources

- [ISO 10303-21:2016 overview](https://www.iso.org/standard/63141.html)
- [Public final edition-3 draft of ISO 10303-21](https://www.steptools.com/stds/step/IS_final_p21e3.html)
- [STEPcode documentation](https://stepcode.github.io/docs/home/)
- [STEPcode Part 21 editor source](https://github.com/stepcode/stepcode/tree/develop/src/cleditor)
- [IfcOpenShell pure-Python physical-file parser](https://github.com/IfcOpenShell/step-file-parser)
- [Library of Congress STEP-file description](https://www.loc.gov/preservation/digital/formats/fdd/fdd000448.shtml)
