# Advanced Part 21 Exchange Structure and Parser Boundaries

## 日本語概要

この研究ノートは、ISO 10303-21の高度な交換構造を、外部resource取得や幾何kernelに依存せず、どこまで決定論的かつfail-closedに認識できるかを検証します。13個の合成fixtureに対し、単一・複数DATA、complex entity、UTF-8、binary、ANCHORを含む5件をaccept、外部参照・未検証署名・深いnesting・ZIP containerの4件をquarantine、entity ID重複・無名の複数DATA・未宣言schema・不正binaryの4件をrejectにしました。形状を持つcontrolとして閉じた四面体STEPとpreviewも保存しています。これは限定した構造parserの結果であり、EXPRESSやAP242への適合、URI解決、CMS署名検証、archive展開、任意STEPの安全性を保証しません。詳細は以下の英語本文に示します。

---

## English Summary

This study extends bounded STEP inspection from a single simple DATA section
to selected edition-3 exchange structures. Thirteen deterministic synthetic
fixtures isolate repeated and parameterized DATA sections, complex entities,
direct UTF-8, binary values, anchors, external references, signatures,
archives, structural ambiguity, invalid tokens, and a nesting limit.

## Research Question

Which advanced ISO 10303-21 exchange structures can a small bounded parser
recognize deterministically, and where must it stop before syntax recognition
is mistaken for schema validation, external-resource trust, signature
verification, archive safety, or geometric correctness?

## Background

ISO 10303-21 defines a clear-text exchange structure for data governed by
EXPRESS schemas. Edition 3 adds mechanisms for anchors, references, signatures,
direct UTF-8 strings, and archive transport. The public final draft describes
an ordered structure consisting of a required HEADER, optional ANCHOR and
REFERENCE sections, zero or more DATA sections, the exchange terminator, and
zero or more trailing SIGNATURE sections.

Multiple DATA sections are not interchangeable with repeated anonymous blocks.
Each section must declare a unique section name and one governing schema, and
that schema must appear in `FILE_SCHEMA`. Entity occurrence names remain global
across the exchange structure. A complex entity instance uses a parenthesized
subsuper record containing multiple adjacent simple records.

These are physical-file rules, not full application meaning. EXPRESS schema
validation and an application protocol such as AP242 determine whether entity
types, attribute counts, references, and constraints are semantically valid.
A geometry kernel adds another separate layer when surfaces, trimming,
tolerances, and solids are evaluated.

## Method

The v0.22.0 parser uses the Python standard library and the existing explicit
Part 21 work limits. It recognizes:

- required HEADER records in their required initial order;
- optional ANCHOR entries and tags;
- optional entity and value REFERENCE associations;
- zero, one, or repeated DATA sections;
- the required name and one-schema parameter form for repeated DATA sections;
- simple and complex entity instances with globally unique numeric entity IDs;
- strings, direct UTF-8 text, numbers, enumerations, omitted values,
  aggregates, typed values, binary tokens, resources, and controlled
  occurrence names;
- one or more Base64 signature payloads after `END-ISO-10303-21;`;
- ZIP magic without extracting archive members.

The decision policy is deliberately stricter than recognition:

- `accept` means the fixture is inside the implemented structural subset;
- `quarantine` means a recognized feature requires work or trust that this
  release does not perform, or an explicit resource budget was exceeded;
- `reject` means the controlled parser found contradictory or invalid
  structure.

An accepted result always records `schema_conformance=not_evaluated`.
External resolution and signature verification always record `not_attempted`.

## Controlled Experiment

The experiment generates 13 exact inputs in code and commits them with a
manifest containing file names, byte lengths, SHA-256 digests, conditions, and
expected decisions.

Five positive controls isolate supported structure:

1. a geometry-bearing closed tetrahedron in one unnamed DATA section;
2. two named DATA sections governed by `DEMO_SCHEMA` with a cross-section
   reference;
3. one complex entity with three component records;
4. one direct UTF-8 string plus a lexically valid binary token;
5. one local anchor with a non-schema tag.

Four quarantine controls isolate trust or resource boundaries:

1. an HTTPS external resource declaration;
2. two syntactically Base64 signature payloads that are not claimed to be CMS;
3. aggregate nesting beyond the configured depth;
4. a deterministic ZIP container with `ISO-10303.p21` as its root member.

Four reject controls isolate structural contradictions:

1. one entity ID defined in two DATA sections;
2. multiple unnamed DATA sections;
3. a DATA schema absent from `FILE_SCHEMA`;
4. a binary token containing a non-hex character.

The tetrahedron is also inspected by the v0.21.0 topology analyzer. Its PNG
preview is generated from the same declared synthetic coordinates. The preview
supports human inspection but is not used as a geometry-validity oracle.

Run the study from the repository root:

```bash
python experiments/run_step_exchange_structure.py
```

Refresh the committed samples in a separate location:

```bash
python experiments/run_step_exchange_structure.py \
  --fixture-dir output/fixtures/step-part21-exchange \
  --output-dir output/step-part21-exchange \
  --refresh-fixtures
```

## Results

All 13 observations match their declared outcomes:

| Decision | Fixtures | Interpretation |
| --- | ---: | --- |
| accept | 5 | Inside the controlled structural subset |
| quarantine | 4 | External trust, archive work, or depth budget remains unresolved |
| reject | 4 | Contradictory or invalid controlled structure |

The geometry control contains 74 entity instances and 97 local occurrence
references. The advanced parser accepts its exchange structure, and the
independent topology path resolves four faces, six edges, one shell, one solid,
and no free edges.

The repeated-DATA fixture retains two unique section names, two governing
schema declarations, and one resolved cross-section entity reference. The
complex fixture retains one entity with the component sequence
`REPRESENTATION_ITEM`, `GEOMETRIC_REPRESENTATION_ITEM`, and `CURVE`. The anchor
fixture records one anchor and one tag.

The external-reference fixture is quarantined even though the URI token is
syntactically recognized. No DNS, HTTP, file, registry, or recursive reference
lookup occurs. The signature fixture is also quarantined after both Base64
payloads are recognized; neither is interpreted as CMS and no signer or
content-integrity claim is made. The ZIP fixture is identified by container
magic and is not opened.

![Advanced exchange structure boundaries](../results/step_part21_exchange_boundaries.png)

![Closed tetrahedron geometry control](../results/step_part21_geometry_control.png)

## Interpretation

The main result is a separation of responsibilities. Parsing can inventory a
REFERENCE section without authorizing resource retrieval. It can retain a
signature payload without authenticating it. It can identify an archive
container without accepting decompression work. It can associate DATA sections
with declared schema names without evaluating the schemas.

This separation makes later capability additions auditable. A future resolver
must define allowed URI schemes, local versus remote policy, recursion and
cycle handling, byte and time limits, cache behavior, and provenance. A future
signature verifier must define the exact signed byte range, CMS processing,
certificate validation, trust stores, time, revocation, and multiple-signature
semantics. A future archive reader must bound member names, counts, paths,
compression ratios, uncompressed bytes, nesting, and root-file selection.

## Failure Modes

- Treating every `ENDSEC`-delimited block as interchangeable can miss the
  required section order and special placement of signatures.
- Accepting repeated anonymous DATA sections loses the section-to-schema
  contract.
- Checking duplicate IDs only within one DATA section permits ambiguous global
  occurrence names.
- Flattening complex entities into one invented type discards their component
  structure.
- Fetching a syntactically valid URI during parsing crosses a network and trust
  boundary before policy is established.
- Calling a Base64 payload a valid signature confuses transport encoding with
  CMS and certificate verification.
- Opening ZIP content merely because its header is recognized exposes
  decompression and path-handling work that this parser has not bounded.
- A successful visual preview can hide schema, topology, tolerance, or
  orientation problems.

## Practical Guidance

- Keep the physical parser independent from schema and geometry-kernel layers.
- Preserve section names, schema identifiers, entity component records, and
  source hashes rather than exposing only a flattened entity count.
- Use explicit states such as `not_evaluated` and `not_attempted`; absence of an
  error is not evidence that deeper validation occurred.
- Keep resource resolution disabled by default and require an explicit policy
  before supporting local files, remote URIs, or registries.
- Quarantine signed content until the signature, certificate path, trust
  anchors, signed byte range, and verification time are evaluated.
- Treat archives as separate containers with their own admission budgets.
- Pair structure-only fixtures with at least one geometry-bearing sample and a
  preview, while keeping numerical and topological tests authoritative.

## Limitations

- This is not a complete implementation or conformance test for ISO 10303-21.
- EXPRESS schemas, entity attribute constraints, WHERE rules, UNIQUE rules,
  and application-protocol semantics are not evaluated.
- External resources, local fragments that require broader resolution,
  registries, redirect chains, and cycles are not resolved.
- Base64 syntax is checked, but CMS structure, signatures, certificates,
  revocation, timestamps, and trust stores are not evaluated.
- ZIP members are not listed or extracted; archive safety and edition-3
  transport conformance are not established.
- Legacy string and print control directives, ECMAScript bindings, arbitrary
  occurrence-name variants, and all user-defined forms are not covered.
- Byte, entity, token-length, reference, and nesting ceilings reduce work but
  do not prove memory safety, denial-of-service resistance, or safe handling of
  arbitrary hostile files.
- Most syntax-isolation fixtures use a synthetic vocabulary rather than a
  redistributable AP242 schema and therefore do not define viewable geometry.
- The tetrahedron preview comes from declared construction coordinates, not an
  independent CAD-kernel tessellation.

## Questions Raised

The next semantic step is to decide how public EXPRESS schemas should be
versioned and tested. In particular, should v0.23.0 begin with a very small
documented AP242 representation path, or first build a schema-neutral EXPRESS
meta-model and validation vocabulary? The roadmap currently favors one narrow
AP242 path so that abstract schema work stays tied to visible product and shape
evidence.

A second open question is whether local fragment references can be resolved
safely before general URI resolution. They share syntax with external
references but have a smaller trust boundary. This should be a separately
tested policy, not an accidental side effect of parsing.

## Sources

- [ISO 10303-21:2016 overview](https://www.iso.org/standard/63141.html)
- [Public final draft of ISO 10303-21 edition 3](https://www.steptools.com/stds/step/IS_final_p21e3.html)
- [Library of Congress STEP-file description](https://www.loc.gov/preservation/digital/formats/fdd/fdd000448.shtml)
- [RFC 3986: Uniform Resource Identifier syntax](https://www.rfc-editor.org/rfc/rfc3986)
- [RFC 4648: Base-N encodings](https://www.rfc-editor.org/rfc/rfc4648)
- [RFC 5652: Cryptographic Message Syntax](https://www.rfc-editor.org/rfc/rfc5652)
- [IfcOpenShell STEP physical-file parser](https://github.com/IfcOpenShell/step-file-parser)
- [OCCT STEP parser architecture notes](https://github.com/Open-Cascade-SAS/OCCT/wiki/step)
