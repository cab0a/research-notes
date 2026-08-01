# Extended Metadata Families, Nested Payloads, and Parser Coverage

## 日本語概要

この研究ノートは、Exif thumbnail、Extended XMP、IPTC IIM、maker noteを含む15個の合成JPEG fixtureを使い、限定的なparserがmetadata familyを認識し、親子関係を解決し、不完全または曖昧な関係を隔離できるかを評価します。8 fixtureはaccept、7 fixtureはquarantineとなり、acceptされたfixtureの9関係はすべて解決されました。一方、maker noteは20 byteのopaque payloadとしてのみ記録しており、意味解釈、完全な規格対応、安全性、真正性は主張しません。実験設計、結果、failure mode、適用限界は以下の英語本文に示します。

---

## English Summary

This note evaluates a deliberately narrow parser over 15 synthetic JPEG
fixtures containing EXIF thumbnails, Standard and Extended XMP, IPTC IIM, and
maker-note payloads. Eight fixtures are accepted and seven are quarantined.
All nine relationships declared by accepted fixtures are resolved, while
missing, duplicate, orphaned, truncated, or out-of-bounds structures fail
closed. Maker-note bytes remain explicitly opaque.

## Research Question

Can a resource-admitted JPEG metadata stage recognize selected extended
metadata families, resolve their nested relationships independently of byte
order, and quarantine known incomplete or ambiguous structures without
claiming complete format semantics?

## Background

JPEG application segments can carry metadata whose logical structure is more
complex than one marker and one value. EXIF uses TIFF IFD pointers and can
reference a compressed thumbnail. XMP can place a primary packet and chunks
of an extended packet in separate APP1 segments. IPTC IIM data is commonly
wrapped in a Photoshop Image Resource Block inside APP13. Maker notes are
manufacturer-defined values reached through an EXIF sub-IFD.

The v0.17.0 study bounded marker traversal and metadata work but deliberately
did not follow these relationships. Resource admission answers whether work
may begin; it does not show that related components are complete, uniquely
linked, or semantically understood.

## Method

The implementation first applies the v0.17.0 resource budget. Only accepted
inputs reach the v0.18.0 parser. The parser then recognizes a controlled subset
of four structures:

- an EXIF IFD0 pointer to an EXIF sub-IFD and an IFD1 pointer to a compressed
  thumbnail;
- a Standard XMP `HasExtendedXMP` GUID and Extended XMP chunks carrying the
  same GUID, full length, and byte offsets;
- an APP13 Photoshop Image Resource Block with resource identifier `0x0404`
  and short-form IPTC IIM datasets;
- a maker-note entry whose bounded bytes are recorded as opaque.

The output separates family recognition, opaque components, declared
relationships, resolved relationships, and routing. `accept` requires every
recognized relationship to be complete. `quarantine` records a stable reason
for known inconsistencies. Container and resource decisions remain separate
inputs rather than being reinterpreted as coverage results.

## Controlled Experiment

All image and metadata bytes are generated in code. The carrier is one small
synthetic image encoded with Pillow at quality 75 and 4:4:4 chroma sampling.
No external image or metadata sample is used.

The 15 fixtures comprise:

- one metadata-free baseline;
- one complete and one out-of-bounds EXIF thumbnail;
- one bounded opaque and one out-of-bounds maker note;
- one Standard XMP packet without an extension;
- two complete Extended XMP layouts with chunks in forward and reverse order;
- four Extended XMP failures covering a missing chunk, duplicate offset,
  orphan extension, and GUID mismatch;
- one complete and one truncated IPTC IIM block;
- one mixed fixture containing all four nested families.

Run the experiment from the repository root:

```bash
python experiments/run_metadata_family_coverage.py
```

The command writes the observation CSV, family summary, runtime manifest, and
figure documented in `results/README.md`.

## Results

The experiment produces 15 observations: 8 `accept`, 7 `quarantine`, and no
container `reject`. Every fixture matches its declared decision and reason.

The accepted fixtures declare nine relationships and resolve all nine. The
mixed fixture alone resolves four links: IFD0 to EXIF sub-IFD, IFD0 to IFD1
thumbnail, Standard XMP to Extended XMP, and Photoshop IRB to IPTC IIM.

Both complete Extended XMP layouts reconstruct the same 270-byte XML packet,
even though the two APP1 chunks appear in opposite orders. The maker-note
fixture records one 20-byte opaque component without assigning field meaning.

The seven negative controls stop at their first known inconsistency:

| Controlled condition | Decision | Reason |
| --- | --- | --- |
| EXIF thumbnail range exceeds TIFF payload | `quarantine` | `exif_thumbnail_out_of_bounds` |
| Maker-note range exceeds TIFF payload | `quarantine` | `maker_note_out_of_bounds` |
| Extended XMP has a byte gap | `quarantine` | `extended_xmp_incomplete` |
| Extended XMP repeats an offset | `quarantine` | `extended_xmp_duplicate_offset` |
| Extension has no Standard XMP reference | `quarantine` | `extended_xmp_orphan` |
| Standard and extension GUIDs differ | `quarantine` | `extended_xmp_missing` |
| IIM dataset length exceeds its block | `quarantine` | `iptc_iim_dataset_overrun` |

## Interpretation

Relationship-aware validation catches failures that segment-level byte limits
cannot express. A packet may fit every resource ceiling while still being
incomplete, multiply addressed, or detached from its parent.

The reverse-order Extended XMP control also separates physical order from the
declared offset contract. Sorting by offsets and rejecting gaps or overlaps is
more defensible for this controlled representation than assuming segment
arrival order is semantic order.

Maker-note recognition demonstrates a different boundary. The parser can
state that bounded bytes exist at a known EXIF tag without claiming that their
manufacturer-specific structure is understood. Recognition and semantic
interpretation are different capabilities.

## Failure Modes

### Resource admission is treated as semantic completeness

All seven quarantined metadata fixtures pass the preceding resource gate.
Size and count ceilings do not prove that pointers, chunks, or nested datasets
form a complete graph.

### Segment order is treated as relationship identity

The two valid Extended XMP layouts use different APP1 order but reconstruct
the same controlled packet. A parser that concatenates arrival order would
mis-handle the reversed control.

### Opaque maker-note bytes are treated as verified fields

The study records only byte count and presence. It does not infer tags,
privacy properties, provenance, camera identity, or safety from the payload.

### One fixture grammar is treated as format-wide support

The parser supports exactly the bounded encodings emitted by this study. It
does not implement all TIFF types, IFD graphs, XMP serialization forms,
Photoshop resources, IIM extended lengths, or maker-note dialects.

## Practical Guidance

- Apply byte and work ceilings before following nested metadata pointers.
- Record parent identifiers, offsets, declared lengths, and resolved lengths
  separately.
- Reject gaps, overlaps, duplicates, conflicting identifiers, and out-of-range
  pointers with stable reason codes.
- Resolve chunked formats by their declared identity and offsets rather than
  incidental segment order.
- Represent unknown or manufacturer-specific payloads as opaque and let a
  later policy decide whether to retain, strip, or quarantine them.
- Keep parser coverage statements tied to tested structures and fixtures.
- Do not infer authenticity, safety, or privacy compliance from successful
  structural parsing.

## Limitations

- All 15 fixtures are synthetic and use one small JPEG carrier.
- The nested thumbnail is a framing-only four-byte JPEG, not a decoded image
  quality or thumbnail compatibility test.
- EXIF parsing covers a small TIFF graph and only the pointer and payload types
  required by the controlled corpus.
- Extended XMP uses one uppercase 32-hex identifier, two chunks, and one XML
  packet form. It does not establish general XMP reconciliation behavior.
- IPTC IIM parsing accepts only short-form dataset lengths inside one
  Photoshop resource block.
- Maker-note bytes remain uninterpreted and are not matched to any vendor.
- The parser does not normalize duplicated semantic fields across EXIF, XMP,
  and IIM.
- No decoder is called and no nested thumbnail pixels are evaluated.
- No fuzzing, memory-safety analysis, vulnerability assessment, or denial-of-
  service claim is included.
- An `accept` result means only that the controlled relationships are complete
  after resource admission.

## Sources

- [ITU-T T.81: JPEG continuous-tone image coding](https://www.itu.int/ITU-T/recommendations/rec.aspx?id=2633)
- [CIPA Exif standards list](https://www.cipa.jp/e/std/std-sec.html)
- [Adobe XMP specifications](https://developer.adobe.com/xmp/docs/xmp-specifications/)
- [Adobe XMP Specification Part 3: Storage in Files](https://github.com/adobe/XMP-Toolkit-SDK/blob/main/docs/XMPSpecificationPart3.pdf)
- [IPTC Information Interchange Model](https://iptc.org/standards/iim/)
- [IPTC Photo Metadata User Guide](https://www.iptc.org/std/photometadata/documentation/userguide/)
