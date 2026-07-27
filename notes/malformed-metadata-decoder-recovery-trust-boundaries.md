# Malformed Metadata, Decoder Recovery, and Trust Boundaries

## Research Question

When a JPEG retains the same compressed image stream but carries malformed,
ambiguous, or excessive application metadata, which inputs are accepted by a
strict bounded audit, which inputs are decoded by OpenCV, Pillow, and FFmpeg,
and what can a successful pixel decode legitimately establish?

The study tests a narrow proposition: decoder recovery is an availability
behavior, not proof that metadata is valid, unambiguous, safe to interpret, or
appropriate to preserve.

## Background

JPEG defines marker segments with 16-bit length fields and reserves APP0
through APP15 for application-specific information. Exif commonly uses APP1,
and embedded ICC profiles use APP2. These layers are adjacent but have
different contracts:

1. JPEG marker framing determines whether a reader can locate later image
   structure.
2. An APP identifier determines which metadata grammar may apply.
3. Exif TIFF offsets, field types, counts, and values require independent
   bounds and semantic checks.
4. ICC chunk sequence numbers, total counts, and reconstructed profile headers
   require independent consistency checks.
5. A decoder may ignore, warn about, recover past, or reject malformed
   metadata while still having enough information to decode image samples.

The ICC embedding guidance states that APP2 segment lengths include the
two-byte length field, that lengths zero and one are illegal, and that ICC
profiles may be split into numbered chunks whose total-count declarations
should agree. Exif defines an APP1 identifier followed by TIFF-structured
attribute data. These rules are not equivalent to a decoder's willingness to
produce pixels.

## Method

The experiment uses one deterministic 104 by 72 synthetic BGR image encoded
once through Pillow as a quality-75, 4:4:4 baseline JPEG. Every derived fixture
either:

- inserts controlled bytes immediately after SOI while preserving every
  original byte after SOI;
- appends controlled bytes after the original EOI; or
- is the unchanged control.

No downloaded, workplace, customer, or camera image is used.

The strict auditor is intentionally separate from the decoder adapters. It:

- walks length-delimited markers before SOS;
- enforces positive APP-count and metadata-byte limits;
- validates selected Exif TIFF header, IFD, and Orientation properties;
- validates ICC chunk topology and the reconstructed profile header;
- detects conflicting Adobe transforms;
- requires SOS and EOI and rejects trailing bytes under the declared policy.

The default limits are 32 APP segments and 131,072 APP payload bytes. They are
explicit application policy controls for this experiment, not JPEG-wide
correctness thresholds.

Raw decoder probes use:

- OpenCV BGR decode with automatic EXIF orientation disabled;
- Pillow RGB conversion followed by BGR channel order, without EXIF transpose
  or ICC conversion;
- FFmpeg native MJPEG decode with `-noautorotate` and a trusted expected output
  shape from the fixture manifest.

Each successful output is compared with the same decoder's unmodified control.
This within-decoder comparison isolates metadata recovery from the
cross-decoder pixel differences already established in earlier notes.

## Controlled Experiment

The 21 committed fixtures cover:

| Family | Controls |
| --- | --- |
| Valid controls | untagged RGB, valid Orientation 6, valid single-chunk ICC |
| Unknown and large APP data | unknown well-framed APP1, 60,000-byte APP15 |
| Malformed Exif | truncated TIFF header, invalid byte order, out-of-bounds IFD offset, Orientation 9, conflicting Orientation 3 and 6 |
| Malformed ICC | truncated chunk header, zero sequence number, missing chunk, duplicate chunk, inconsistent total counts, truncated profile |
| Framing | illegal length one, declared segment overrun, trailing bytes after EOI |
| Ambiguity and resource policy | conflicting Adobe transforms, 40 small APP15 segments |

All inserted streams are deterministic. The fixture manifest hashes the
synthetic source, each JPEG, the shared reference decode, and the preservation
relationship to the base stream.

The experiment records four distinct facts rather than collapsing them into
one pass/fail label:

1. strict audit acceptance;
2. native decoder success or rejection;
3. output shape and dtype;
4. exact equality to the same decoder's control.

## Results

### Local reference profile

The strict policy accepted 5 of 21 fixtures and rejected the remaining 16 for
a named framing, metadata, ambiguity, trailing-data, or resource-limit issue.

Across 63 decoder probes:

- 60 decoded successfully;
- all 60 successful outputs satisfied the expected BGR shape and `uint8`
  contract;
- all 60 successful outputs were pixel-exact relative to the same decoder's
  unmodified control;
- 45 of the 48 probes for strict-rejected fixtures still decoded
  successfully.

OpenCV succeeded on 20 of 21 fixtures, Pillow on 19 of 21, and FFmpeg on all
21 in the local reference environment. OpenCV and Pillow rejected the declared
APP1 length overrun, while FFmpeg recovered an exact control image. Pillow
also rejected the truncated ICC chunk header; OpenCV and FFmpeg returned exact
control pixels.

All three decoders accepted the illegal APP1 length-one fixture and returned
exact control pixels. This observation is especially useful: even malformed
marker framing can be skipped by a recovery implementation, so pixel
availability cannot be treated as a structural validation result.

The 60,000-byte well-framed APP15 fixture passed the declared strict limits and
decoded exactly. The fixture with 40 small APP15 segments exceeded the
application's count limit, was rejected by the strict audit, and nevertheless
decoded exactly through all three adapters.

### Cross-platform release matrix

The release workflow evaluates the same corpus on Ubuntu x64 default and
forced-scalar paths, Windows x64, macOS arm64, and macOS Intel x64. The
committed cross-platform CSV files preserve per-build acceptance, rejection,
pixel hashes, and diagnostic fingerprints. Findings are limited to those
recorded runner images and bundled codec builds.

Across the five recorded profiles, the strict audit met all 105 declared
fixture expectations: it accepted 25 fixture-platform observations and
rejected 80. Of 315 decoder probes, 300 decoded successfully, and every
successful output was pixel-exact relative to that decoder's control on the
same platform. Each platform therefore reproduced the local 60-of-63 recovery
result. Strict-rejected fixtures still decoded in 225 of 240 probes.

The rejection set was stable across all profiles. OpenCV rejected the APP1
length overrun in 5 of 105 probes; Pillow rejected that fixture and the
truncated ICC chunk header in 10 of 105 probes; FFmpeg decoded all 105 probes.
OpenCV and Pillow each retained one successful output hash per fixture across
the matrix. FFmpeg retained exact metadata invariance within every profile but
had two control hashes per fixture because the macOS arm64 output differed
from the other four recorded profiles. That cross-build difference is separate
from malformed-metadata recovery and reinforces the need for a within-build
control.

These observations were produced by the successful
[five-profile release workflow](https://github.com/cab0a/research-notes/actions/runs/30242822114),
not by relabeling one local execution.

## Interpretation

The main finding is not that permissive recovery is wrong. Recovery can be
useful when an application needs preview pixels from a damaged file. The
finding is that recovery and trust are different decisions.

A decoder can safely ignore an APP segment for pixel reconstruction while an
application still needs to reject that segment before it:

- rotates an image;
- builds a color transform;
- copies metadata into a new file;
- exposes metadata to downstream parsers;
- allocates storage from declared counts or offsets;
- treats a decoded image as evidence that the entire file is conforming.

Within this fixed corpus, ignored or recovered metadata did not change
successful raw pixels. That is fixture-specific evidence about pixel
invariance, not evidence that the metadata is harmless in every consumer.

## Failure Modes

### Decode success mistaken for validation

Most strict-rejected fixtures produced exact pixels. An ingestion pipeline
that equates a non-empty decoded array with file validity loses the distinction
between preview availability and metadata trust.

### Conflicting values silently resolved

Two validly framed Exif segments can declare different orientations, and two
Adobe segments can declare different transforms. A consumer may select the
first, the last, or neither. The strict policy rejects the ambiguity instead
of depending on undocumented selection order.

### Chunk topology ignored

Missing, duplicate, zero-numbered, or inconsistent ICC chunks can coexist with
a decodable image. Applying or copying the reconstructed bytes without
topology validation creates a different risk than raw JPEG decoding.

### Marker recovery hides framing errors

The length-one and length-overrun controls demonstrate different recovery
paths. A decoder that finds the later JPEG structure is not certifying that
the earlier segment length was legal.

### Resource policy omitted

Individually well-framed APP segments can still create excessive counts or
total metadata size. The selected limits are bounded application decisions and
must be chosen for the deployment context.

## Practical Guidance

1. Treat container audit, metadata interpretation, and pixel decoding as
   separate stages with separate outcomes.
2. Enforce input byte, APP count, aggregate metadata byte, dimension, and
   decode-time limits before retaining or transforming untrusted metadata.
3. Reject conflicting values rather than relying on first-wins or last-wins
   behavior unless that precedence is an explicit compatibility contract.
4. Validate all ICC chunk sequence and total-count fields before
   reconstruction, then validate the reconstructed profile itself.
5. Validate TIFF byte order, offsets, entry bounds, field type, count, and
   value range before using Exif fields.
6. If recovery pixels are useful, label them as recovered output and do not
   silently propagate rejected metadata.
7. Record decoder build provenance because recovery behavior may change
   independently of application code.
8. Keep strict policy limits configurable and tested, but do not present one
   repository's limits as universal security constants.

## Limitations

- The corpus modifies APP metadata around one small baseline 8-bit RGB JPEG.
- It does not truncate entropy-coded scans, corrupt Huffman or quantization
  tables, exercise progressive scan recovery, or generate exploit payloads.
- It is a controlled compatibility study, not a fuzzer, vulnerability
  assessment, sandbox, or proof of memory safety.
- Peak memory, decode time, warning streams, and denial-of-service behavior
  are not benchmarked.
- Pillow warnings are suppressed during the fixed pixel probe so warning text
  does not become a platform-dependent result contract.
- FFmpeg receives trusted expected dimensions from the fixture manifest; this
  adapter does not establish a safe way to trust dimensions from an arbitrary
  malformed file.
- Successful output is compared within each decoder. The study does not claim
  cross-decoder pixel equivalence.
- The APP-count and metadata-byte limits are declared application policy, not
  values required by the JPEG, Exif, or ICC specifications.
- Hosted CI behavior is a snapshot of the recorded builds and must not be
  generalized to every build of the same codec family.

## Sources

- [ITU-T T.81: JPEG requirements and guidelines](https://www.itu.int/ITU-T/recommendations/rec.aspx?lang=en&rec=2633)
- [ITU-T T.86: JPEG APPn markers](https://www.itu.int/epublications/publication/itu-t-t-86-v2-2024-02-information-technology-digital-compression-and-coding-of-continuous-tone-still-images-appn-markers)
- [CIPA Exif standards list](https://www.cipa.jp/e/std/std-sec.html)
- [CIPA DC-008-2012 Exif structure reference](https://www.cipa.jp/std/documents/e/DC-008-2012_E.pdf)
- [ICC technical note on profile embedding](https://www.color.org/technotes/ICC-Technote-ProfileEmbedding.pdf)
- [OpenCV image decoding documentation](https://docs.opencv.org/4.12.0/d4/da8/group__imgcodecs.html)
- [Pillow `ImageFile` documentation](https://pillow.readthedocs.io/en/stable/reference/ImageFile.html)
- [FFmpeg error-detection documentation](https://ffmpeg.org/ffmpeg-all.html)
- [libjpeg-turbo change log](https://github.com/libjpeg-turbo/libjpeg-turbo/blob/main/ChangeLog.md)
