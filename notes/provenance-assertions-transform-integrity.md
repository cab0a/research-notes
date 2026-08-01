# Provenance Assertions and Transform Integrity

## 日本語概要

この研究ノートは、JPEGのimage core、正規化したmetadata state、decoded pixelsに対する3つのSHA-256 bindingを持つ限定的なunsigned assertionを使い、metadata並べ替え、sanitization、再encode、pixel変更、assertion改変を区別できるかを11個の合成fixtureで評価します。metadataの物理順序変更は3 bindingを維持し、sanitizationはmetadata bindingだけ、再encodeとpixel変更はimage coreとdecoded-pixel bindingを失効させました。renewed assertionは現在の出力へ一致しますが、署名、identity、trust chain、C2PA validationを実装していないため、真正性や作成者を証明しません。詳細は以下の英語本文に示します。

---

## English Summary

This study evaluates an intentionally unsigned three-scope digest assertion
over 11 synthetic JPEG transform fixtures. Metadata reordering preserves the
image-core, normalized-metadata, and decoded-pixel bindings. Sanitization
invalidates only the metadata binding, while re-encoding and pixel editing
invalidate image-core and decoded-pixel bindings. Renewed assertions match
their current outputs and name a parent digest, but do not authenticate an
identity or validate a provenance chain.

## Research Question

Can explicit digest scopes distinguish metadata-only, compressed-image, and
decoded-pixel changes across controlled JPEG transforms, and what additional
evidence is still required before those records can be called authenticated
provenance?

## Background

A cryptographic digest can detect that the bytes supplied to the hash function
have changed. It does not identify who created the digest, establish when it
was created, or show that a parent record is trustworthy. Authenticated
provenance systems add signatures, credentials, trust policy, asset bindings,
and validation procedures around content assertions.

The C2PA specification separates hard content bindings, assertion hashes,
claim signatures, credential trust, and validation status. This study borrows
that separation as a research principle but does not implement the C2PA data
model, JUMBF storage, signatures, credentials, or validation algorithm.

## Method

One compact JSON document is stored in a controlled APP15 segment. It declares
an action, an optional parent-assertion SHA-256 digest, and three current-output
bindings:

- `image_core_sha256` hashes the JPEG after removing APP1 through APP15 and
  COM segments;
- `metadata_state_sha256` hashes the twelve normalized v0.16.0 controlled
  fields in canonical field order;
- `decoded_pixels_sha256` hashes the raw Pillow-decoded BGR array using its
  shape, data type, and bytes.

The assertion JSON uses sorted keys and compact ASCII serialization for this
fixed schema. This is a deterministic study encoding, not a complete RFC 8785
JSON Canonicalization Scheme implementation.

An inherited assertion is copied unchanged to a transformed JPEG. A renewed
assertion recomputes all three bindings for the current output and stores the
SHA-256 digest of the source assertion as `parent_assertion_sha256`. The
verifier reports assertion presence and syntax separately from binding
agreement.

## Controlled Experiment

All inputs are generated in code from one small synthetic image. The source is
encoded at quality 75 with 4:4:4 chroma sampling and receives the twelve-field
v0.16.0 metadata corpus. The re-encode control uses quality 65. The pixel edit
replaces one fixed rectangular region before re-encoding.

The 11 fixtures cover:

- a newly asserted source;
- byte-distinct but semantically equivalent metadata order with an inherited
  assertion;
- metadata sanitization with inherited and renewed assertions;
- JPEG re-encoding with inherited and renewed assertions;
- a controlled pixel edit with an inherited assertion;
- one declared digest changed inside otherwise valid JSON;
- malformed JSON, no assertion, and duplicate assertions.

Run:

```bash
python experiments/run_transform_integrity.py
```

The command writes observation and summary CSV files, a runtime manifest, and
the figure documented in `results/README.md`.

## Results

All 11 fixtures match their declared status and reason code:

| Status | Fixtures | Interpretation inside this study |
| --- | ---: | --- |
| `valid_binding` | 2 | all current scopes match; no parent declared |
| `valid_derived_binding` | 2 | all current scopes match; parent digest declared |
| `stale_binding` | 4 | at least one declared scope differs |
| `missing_assertion` | 1 | no controlled APP15 assertion is present |
| `malformed_assertion` | 1 | the controlled assertion is not valid JSON |
| `multiple_assertions` | 1 | more than one controlled assertion is present |

The metadata-reordered fixture preserves all three bindings even though the
complete JPEG bytes differ. The inherited sanitization fixture mismatches only
`metadata_state_sha256`; its image core and decoded pixels still match. The
inherited quality-65 re-encode and controlled pixel-edit fixtures mismatch
both `image_core_sha256` and `decoded_pixels_sha256` while retaining the
normalized metadata binding.

Renewing after sanitization or re-encoding produces a matching three-scope
record with a parent digest. Changing the declared metadata digest produces a
stale binding rather than a syntax error.

## Interpretation

Separate scopes make the reason for invalidation observable. A single whole-
file digest would detect all byte changes but would not distinguish harmless
metadata serialization order from metadata semantics, compressed-image bytes,
or decoded-pixel content.

An inherited assertion is appropriate only while its declared scopes remain
true. A transform that intentionally changes a bound scope must either remove
the record or emit a new assertion describing the current output. Copying the
old record makes the mismatch visible but does not document the new state.

A renewed digest is still not authenticated provenance. Any party able to
modify the JPEG can recompute this unsigned record. The parent digest is a
declared reference, not proof that the parent was retrieved, matched,
signature-validated, or trusted.

## Failure Modes

### Digest agreement is treated as authenticity

The study has no secret or private key. A matching digest shows only that the
current controlled scopes match values in the same unsigned document.

### Parent presence is treated as lineage validation

The verifier checks only the parent field's SHA-256 syntax. It does not locate
or validate a parent asset or assertion.

### One whole-file hash is treated as a sufficient transform contract

Metadata reordering changes complete JPEG bytes while preserving all three
declared semantic scopes. Conversely, sanitization changes one scope and
re-encoding changes two. The relevant scope depends on the application.

### Renewing a stale assertion hides the transform

A newly computed digest can match any current output. A meaningful provenance
system must authenticate the actor and bind the declared action, parent,
content, and validation evidence together.

## Practical Guidance

- Name every bound scope and define its canonicalization procedure.
- Treat missing, malformed, duplicate, mismatching, and valid assertions as
  separate states.
- Remove or renew assertions after intentional changes to a bound scope.
- Keep inherited and newly issued records distinguishable.
- Validate parent references rather than accepting a syntactically valid
  digest as lineage evidence.
- Add signatures, credential validation, trust policy, and revocation handling
  before making authenticity claims.
- Preserve machine-readable validation reasons for downstream policy stages.
- Test metadata-only, compressed-byte, and decoded-pixel changes separately.

## Limitations

- The assertion format is a project-specific experimental structure, not
  C2PA, Content Credentials, JUMBF, or a standard JPEG provenance format.
- Assertions are unsigned and have no identity, certificate, trust list,
  timestamp, revocation, or key-management model.
- Parent assertions are not retrieved or recursively validated.
- The deterministic JSON encoding is limited to the fixed ASCII schema and is
  not claimed to conform to RFC 8785.
- Metadata hashing covers only the twelve controlled v0.16.0 fields.
- Image-core hashing deliberately excludes APP1 through APP15 and COM, so it
  does not bind arbitrary metadata or provenance bytes.
- Decoded-pixel hashes depend on the pinned Pillow decoder path and array
  contract; they are not perceptual hashes.
- All inputs are synthetic and use one small image, two quality settings, and
  one fixed pixel edit.
- SHA-256 collision or preimage resistance is not experimentally evaluated.
- No adversarial key, signature, parser, or storage testing is included.

## Sources

- [NIST FIPS 180-4: Secure Hash Standard](https://csrc.nist.gov/pubs/fips/180-4/upd1/final)
- [C2PA Technical Specification](https://spec.c2pa.org/specifications/specifications/2.4/specs/C2PA_Specification.html)
- [C2PA Implementation Guidance](https://spec.c2pa.org/specifications/specifications/2.4/guidance/Guidance.html)
- [RFC 8785: JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html)
