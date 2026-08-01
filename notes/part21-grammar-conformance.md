# Part 21 Grammar Coverage and Controlled Conformance Testing

## 日本語概要

本ノートは、ISO 10303-21の第1版・第2版・第3版で追加された構文を整理し、文字列・UTF-8・コメント・数値・binary・複数DATA部・ANCHOR・REFERENCE・SIGNATURE・ZIP transportを34個の決定論的な合成fixtureで検証します。内部パーサーは17件の正常例をacceptし、17件の異常例を理由付きでrejectしました。固定revisionのSTEPutilsとIfcOpenShell `step-file-parser`にも同じ入力を与え、受理境界の差を観測しました。これは限定した構文適合性研究であり、ISO認証、EXPRESS schema適合、外部参照の解決、CMS署名検証、任意のSTEPファイル対応を主張しません。詳細は以下の英語本文に示します。

---

## English Summary

This note maps selected ISO 10303-21 edition changes to a deterministic corpus,
checks syntax and declared implementation-level consistency, and compares the
same inputs with two pinned public Python parsers. Parser agreement is treated
as differential evidence, not as a vote on conformance.

## Research Question

Which Part 21 lexical, structural, edition, conformance-class, and archive
rules does the source-preserving Python parser implement, and where do its
acceptance boundaries differ from independently published parsers?

The objective is not to claim that a file “looks like STEP.” The output must
identify the syntax under test, the earliest edition that admits it, the
declared implementation level, the observed decision, and every deferred
semantic or trust-boundary operation.

## Background

ISO lists three editions of ISO 10303-21: [Edition 1 from
1994](https://www.iso.org/standard/20580.html), [Edition 2 from
2002](https://www.iso.org/standard/33713.html), and the published [Edition 3
from 2016](https://www.iso.org/standard/63141.html). Edition 3 remains the
current published edition on the ISO page. The public final Edition 3 text
describes the exchange structure with an unambiguous context-free grammar and
maps EXPRESS-described product data into that physical syntax.

The edition history matters because an implementation-level string is a
claim, not decoration. In this study the compatibility table is:

| Declared value | Interpreted edition | Syntactical conformance class |
| --- | ---: | ---: |
| `2;1`, `2;2` | 1 | 1, 2 |
| `3;1`, `3;2` | 2 | 1, 2 |
| `4;1`, `4;2`, `4;3` | 3 | 1, 2, 3 |

The [Edition 3 `FILE_DESCRIPTION`
definition](https://www.steptools.com/stds/step/IS_final_p21e3.html)
uses `4;1`, `4;2`, and `4;3`. This experiment retains the earlier forms only
to classify compatibility fixtures; it does not infer an edition from a file
extension or silently upgrade a declaration.

## Edition Differences

The public [Edition 3 change
log](https://www.steptools.com/stds/step/IS_final_p21e3.html)
provides the feature baseline used here.

| Capability | First edition in this study | Controlled interpretation |
| --- | ---: | --- |
| Core clear-text exchange, comments, binary, legacy string controls | 1 | Token and structure syntax only |
| `FILE_POPULATION`, `SECTION_LANGUAGE`, `SECTION_CONTEXT`, short enumeration names, multiple `DATA` sections | 2 | Section structure without EXPRESS validation |
| Direct UTF-8, `ANCHOR`, `REFERENCE`, `SIGNATURE`, optional `DATA`, constants and value instances, ZIP transport | 3 | Syntax and bounded intake; deferred semantics remain explicit |

Edition 3 directly represents non-ASCII code points with UTF-8 while retaining
the earlier `\X\`, `\X2\`, `\X4\`, `\S\`, and `\P?\` controls for
compatibility. Strings and binary tokens can also contain the `\N\` and
`\F\` print controls. The parser decodes this controlled set and preserves the
raw source token separately.

The grammar contains details that permissive readers can easily blur:

- a real mantissa requires a digit before the decimal point and requires the
  decimal point even when an exponent is present;
- standard entity and type keywords are normalized to uppercase, while a
  user-defined keyword begins with `!`;
- an entity or value occurrence number must contain a non-zero digit;
- an enumeration begins with an uppercase letter and is delimited by full
  stops;
- a binary encoding begins with an unused-bit count from zero through three,
  followed by uppercase hexadecimal digits;
- comments use `/* ... */`, do not nest, and have no exchange semantics.

The [real-number examples](https://www.steptools.com/stds/step/IS_final_p21e3.html),
[occurrence-name rules](https://www.steptools.com/stds/step/IS_final_p21e3.html),
[binary encoding](https://www.steptools.com/stds/step/IS_final_p21e3.html),
and [comment rule](https://www.steptools.com/stds/step/IS_final_p21e3.html)
were used to select positive and negative controls.

## Method

`build_part21_conformance_fixtures()` generates every byte of the corpus in
memory. Each fixture records its condition, expected decision, reason code,
declared and required edition, byte length, and SHA-256 digest. The experiment
then performs four distinct checks:

1. decode or boundedly open the transport;
2. lex and parse the controlled Part 21 grammar;
3. derive used features and their minimum edition and class;
4. compare the derived requirements with `FILE_DESCRIPTION`.

An accepted result means only that these checks pass. `schema_conformance`
remains `not_evaluated`, external resolution and signature verification remain
`not_attempted`, and no application protocol or geometry is evaluated.

ZIP inputs are inspected in memory without extracting paths. Explicit limits
cover archive bytes, entry count, total uncompressed bytes, root bytes, and
compression ratio. The reader rejects absolute or parent-relative paths,
duplicate names, encryption, unsupported compression, and a missing required
`ISO-10303.p21` root. This implements a bounded subset of the [Edition 3 ZIP
transport requirements](https://www.steptools.com/stds/step/IS_final_p21e3.html).

## Controlled Experiment

The 34-fixture corpus contains 17 expected accepts and 17 expected rejects.
Positive cases isolate all three editions, legacy and direct character
encoding, comments, binary, complex entities, user-defined keywords, multiple
data sections, Edition 2 headers, anchors, references, signatures, constants,
optional data, and the ZIP root. Negative cases isolate malformed reals,
lowercase keywords, unterminated comments, invalid binary and Base64, all-zero
occurrence names, unsafe archives, missing roots, and edition or class
mismatches.

The same committed bytes are passed to:

- [STEPutils](https://github.com/mozman/steputils) at commit
  `547860b349a36cf24c564d6c87ffd8f60484f6fb`;
- [IfcOpenShell `step-file-parser`](https://github.com/IfcOpenShell/step-file-parser)
  at commit `9400d243d880dace57490949d74ab1932ce99a09`.

Each parser runs in a child process. The adapter records only `accept`,
`reject`, or execution error and the final diagnostic class. It does not
translate one parser's object model into another, and it never uses majority
agreement as an oracle. The [STEPutils Part 21
documentation](https://steputils.readthedocs.io/en/latest/p21.html) and the
[IfcOpenShell parser README](https://github.com/IfcOpenShell/step-file-parser#readme)
define the public capabilities used to select these comparison points.

## Results

The internal parser matched all 34 declared expectations: 17 accepts, zero
quarantines, and 17 rejects. Every edition or class mismatch retained its
parsed evidence, including both the declared and required values.

| Parser | Accepted fixtures | Agreement with fixture expectations | Important observed differences |
| --- | ---: | ---: | --- |
| `research_notes` | 17 | 34/34 | Controlled target implementation |
| STEPutils | 14 | 23/34 | Rejected several Edition 2/3 positives; accepted `1E3`, `#0`, an unknown string control, and Edition 2 without `DATA` |
| IfcOpenShell `step-file-parser` | 5 | 22/34 | Accepted the Edition 1 core and complex entity; rejected the tested Edition 2/3 extensions and ZIP |

![Part 21 grammar coverage and controlled conformance](../results/step_part21_conformance.png)

The count is not a ranking. For example, a parser designed around a narrower
physical-file profile can correctly reject inputs outside that profile while
remaining useful for its intended application. Conversely, acceptance does
not prove that every token, declaration, schema rule, reference, or signature
was interpreted as this experiment expects.

The experiment also corrected an issue exposed in the earlier v0.22 corpus:
direct UTF-8, anchor, reference, and signature fixtures had all declared
`3;1`. They now declare the minimum appropriate Edition 3 level (`4;1` or
`4;2`); the existing route and entity-count results are unchanged.

## Interpretation

Edition-aware parsing needs two outputs. The abstract syntax tree answers what
was present, while a separate conformance observation answers whether the
declared edition and class permit those features. Combining them would discard
valuable evidence when a well-formed construct is paired with a false
declaration.

The differential results show why a STEP intake tool should expose capability
metadata. “Parsed successfully” is too weak unless the caller also knows the
accepted edition, character model, section forms, archive policy, and semantic
work that was skipped. The v0.24 CSVs make those dimensions inspectable rather
than hiding them behind one Boolean.

## Failure Modes

- Permissive number tokenization can accept a real without its required decimal
  point or split malformed input into misleading tokens.
- Treating lowercase names as equivalent can lose the distinction between
  source spelling and normalized Part 21 keywords.
- Treating `#0` as an ordinary identifier violates the occurrence-name rule.
- Reading direct UTF-8 as ASCII-only rejects Edition 3 text; blindly accepting
  arbitrary bytes loses decoding diagnostics.
- Opening a ZIP as text rejects the transport before finding its required root;
  extracting it without path and expansion checks creates a separate intake
  risk.
- Parsing Base64 does not authenticate a signature. Fetching a `REFERENCE`
  during parsing would cross a network and resource trust boundary.
- A syntax accept can still describe nonexistent schema types, wrong attribute
  arity, invalid B-Rep topology, or geometrically inconsistent data.

## Practical Guidance

- Record the raw implementation-level string and the derived edition and
  conformance class.
- Preserve raw tokens and source spans even when normalized values are exposed.
- Make character-control decoding explicit and test legacy and direct UTF-8
  forms separately.
- Use paired positive and negative fixtures for every implemented boundary.
- Keep archive admission, external resolution, signature verification, schema
  validation, and geometric evaluation as separate stages.
- Pin independent parsers by revision and retain their licenses and repository
  URLs in the result manifest.
- Investigate parser disagreement at fixture level; do not convert agreement
  percentages into a standards-compliance score.

## Limitations

- This is a controlled subset, not an ISO conformance certification or a full
  Protocol Implementation Conformance Statement.
- The corpus has 34 generated inputs and is not exhaustive over the complete
  Wirth Syntax Notation, every legal control-directive combination, URI form,
  signature construction, or ZIP layout.
- Only one positive case represents most feature families. More combinatorial
  and mutation-based coverage is required before claiming broad robustness.
- EXPRESS schema syntax, type checking, entity arity, WHERE and UNIQUE rules,
  application-protocol semantics, units, products, geometry, and B-Rep
  validity are not evaluated.
- External references are recorded but never resolved. Signature payloads are
  Base64-decoded but are synthetic placeholders, not valid CMS signatures.
- ZIP subsidiary files and nested archives are not resolved. Resource limits
  bound controlled parser work but do not prove memory safety or resistance to
  hostile native libraries.
- External parser observations are tied to two pinned revisions and the tested
  adapters. They do not describe every version, configuration, or intended
  usage of either project.
- The public Edition 3 final text is used as a directly reviewable technical
  source, while the ISO catalog pages establish publication status. This note
  does not reproduce the standard and should not substitute for licensed
  normative material where formal certification is required.

## Questions Carried Forward

- Should edition validation be a strict reject mode, a compatibility warning,
  or a caller-selected policy when a legacy producer misdeclares modern
  syntax?
- Which combinations of string controls, direct UTF-8, and print controls need
  mutation-based testing next?
- How should a future writer distinguish exact-source preservation from a
  canonical Edition 3 serialization?
- Which EXPRESS schema subset must be available before `accept` can mean more
  than physical-file syntax acceptance?

## Sources

- [ISO 10303-21:1994 catalog page](https://www.iso.org/standard/20580.html)
- [ISO 10303-21:2002 catalog page](https://www.iso.org/standard/33713.html)
- [ISO 10303-21:2016 catalog page](https://www.iso.org/standard/63141.html)
- [Public final Edition 3 text of ISO 10303-21](https://www.steptools.com/stds/step/IS_final_p21e3.html)
- [STEPutils repository](https://github.com/mozman/steputils)
- [STEPutils Part 21 documentation](https://steputils.readthedocs.io/en/latest/p21.html)
- [IfcOpenShell `step-file-parser` repository](https://github.com/IfcOpenShell/step-file-parser)
