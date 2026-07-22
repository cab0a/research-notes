# Cross-Platform Codec Builds and Decoded-Pixel Contracts

## Research Question

When a fixed baseline JPEG byte stream is decoded through pinned OpenCV and
Pillow wheels on different operating systems and processor architectures,
which properties remain identical, and which claims require an explicit
decoded-pixel contract?

The study separates four questions:

1. Does the file still satisfy the fixed marker-level structure contract?
2. Does the decoder return the declared shape and 8-bit three-channel type?
3. Is the decoded BGR array exactly identical to the committed reference?
4. If exact identity fails, is every channel sample within one integer code
   value of that reference?

The fourth check is a narrow numerical diagnostic. It is not a perceptual
quality threshold and is not proposed as a default for other applications.

## Background

JPEG standardizes a family of compressed image processes and interchange
syntax. The JPEG committee describes JPEG 1 as several parts: the core coding
system, compliance testing, extensions, registration, JFIF, printing, and
reference software. JFIF also covers chroma placement, upsampling, and the
YCbCr-to-RGB interpretation that affect application-visible pixels.

Library wrappers do not fully identify the executable codec path. Pillow can
report whether its build includes JPEG support and which libjpeg-turbo feature
version was compiled into the wheel. OpenCV exposes build information that
includes its JPEG backend. These runtime records are therefore part of the
experiment rather than incidental environment details.

The libjpeg-turbo project documents that mathematical compatibility can depend
on the selected DCT/IDCT algorithm, SIMD availability, compiler settings, and
sampling behavior. It also provides `JSIMD_FORCENONE=1` as a way to disable
SIMD paths for controlled testing. This is a reason to measure pixel arrays,
not evidence that every build must differ.

## Method Selection

A fixed corpus is more suitable than re-encoding on each runner. Re-encoding
would mix encoder portability with decoder portability and make a byte-stream
difference indistinguishable from a reconstruction difference. The experiment
therefore commits each JPEG stream, its marker metadata, and a lossless PNG of
one declared reference decode.

The reference PNG is a contract anchor generated through the pinned OpenCV
path. It is not an uncompressed ground truth and does not imply that one
decoder is universally more correct than another. OpenCV and Pillow decode the
same bytes to BGR arrays, after which the experiment applies direct integer
comparisons without a perceptual metric.

GitHub-hosted runners provide fresh virtual machines for each job. A matrix is
used to observe the pinned Python wheels on these five profiles:

- Ubuntu 24.04 x64 with the default SIMD policy
- Ubuntu 24.04 x64 with `JSIMD_FORCENONE=1`
- Windows 2025 x64 with the default SIMD policy
- macOS 15 arm64 with the default SIMD policy
- macOS 15 Intel x64 with the default SIMD policy

The workflow records the runner image identifiers reported at execution time.
The labels describe the release experiment; GitHub runner images can be
updated after the release.

## Decoded-Pixel Contracts

The experiment reports the following contracts independently.

### Stream structure

The JPEG SHA-256 digest, dimensions, baseline SOF marker, sample precision,
DQT fingerprint, and component sampling signature must match the committed
fixture manifest. A mismatch stops the experiment.

### Array interface

Each decoder must return the reference dimensions, three channels, and
`uint8` samples. A shape or dtype mismatch stops the experiment.

### Exact pixels

The shape, dtype, and array bytes are hashed together. Exact agreement means
the decoded array equals the committed BGR reference at every channel sample.
This is the strongest and most brittle contract.

### One-code-value diagnostic

If exact agreement fails, the report also checks whether the maximum absolute
channel difference is at most one integer code value. Mean absolute error and
changed-sample and changed-pixel fractions remain visible. Passing this bound
does not mean that the outputs are perceptually equivalent or suitable for a
particular downstream decision.

## Controlled Experiment

### Synthetic corpus

The fixture generator creates three 128 x 128 BGR patterns:

- `chroma_edges` contains saturated boundaries and a diagonal line;
- `gradient_shapes` combines smooth ramps and hard geometric boundaries;
- `high_frequency_tiles` contains dense four-pixel chromatic tiles.

Each pattern is encoded with OpenCV at numeric quality controls 50 and 95 with
explicit 4:4:4 and 4:2:0 sampling. This produces 12 baseline sequential JPEG
files. The committed manifest records source, JPEG, and reference pixel hashes,
encoded size, DQT fingerprint, SOF data, and generator build information.

Only generated patterns are used. No external, workplace, customer, or camera
imagery is included.

### Decoder observations

Each platform profile runs both decoders on all 12 files, producing 24 rows.
Across five profiles, the release matrix produces 120 decoder observations and
60 within-profile OpenCV-versus-Pillow comparisons. An aggregation job checks
coverage, combines build metadata, counts unique decoded hashes per fixture,
and writes a cross-platform summary and figure.

### Reproduction

From a clone, validate the committed corpus and run the local observation:

```bash
python -m pip install -e ".[test]"
python -m pytest
python experiments/run_cross_platform_codec_contracts.py
```

Regenerate the synthetic fixtures only when intentionally auditing their
provenance:

```bash
python experiments/run_cross_platform_codec_contracts.py --refresh-fixtures
```

The cross-platform result is reproduced by the repository CI matrix. Its
platform artifacts are combined with:

```bash
python experiments/summarize_cross_platform_codec_contracts.py \
  --input-dir platform-artifacts \
  --output-dir cross-platform-results \
  --expected-platform-count 5
```

## Results

### Local reference profile

The Linux x64 reference run produced 24 decoder observations. Both OpenCV and
Pillow matched all 12 committed reference arrays exactly. The 12 direct
OpenCV-versus-Pillow comparisons were also exact. Disabling libjpeg-turbo SIMD
locally produced the same 24 exact reference results.

This local observation only validates the current fixed corpus and pinned
builds. It does not establish a general rule for arbitrary JPEG files.

### Cross-platform matrix

The [successful five-profile release matrix](https://github.com/cab0a/research-notes/actions/runs/29901525179)
produced 120 decoder observations. All 120 matched the committed BGR reference
arrays exactly, so all 120 also passed the within-one diagnostic and had a
maximum absolute error of zero. All 60 within-profile OpenCV-versus-Pillow
comparisons were exact. For every fixture and decoder, the five profiles
produced one unique decoded-array hash. Consequently, the recorded Laplacian
variance and Tenengrad ratios to the reference were exactly 1.0 throughout
this matrix.

The runtime manifest records the builds rather than inferring them from the
wrapper names:

| Profile | Runner image | SIMD policy |
| --- | --- | --- |
| Ubuntu x64 default | `ubuntu24` `20260714.240.1` | runtime default |
| Ubuntu x64 scalar | `ubuntu24` `20260714.240.1` | forced scalar |
| Windows x64 | `win25-vs2026` `20260714.173.1` | runtime default |
| macOS arm64 | `macos15` `20260715.0234.1` | runtime default |
| macOS Intel x64 | `macos15` `20260715.0340.1` | runtime default |

Across those profiles, OpenCV 4.13.0 reported its build libjpeg-turbo backend
as version 3.1.2-70, while Pillow 12.3.0 reported libjpeg-turbo 3.1.4.1. The
jobs used Python 3.12. The committed CSV snapshot preserves the observations,
build records, and runner identifiers that support these release-specific
claims.

## Interpretation

Byte-stream identity, marker identity, decoded-pixel identity, and downstream
metric identity are different assertions. A stable DQT fingerprint cannot by
itself guarantee a pixel array. Conversely, two entropy-coded streams can
decode identically, as v0.9.0 demonstrated.

For the local controls and all five CI profiles, the pinned wrappers meet the
exact contract for this corpus. The default and forced-scalar Ubuntu results
are also identical, so the selected SIMD policy did not change these 12
decodes in the recorded builds. That result is useful evidence for a strict
regression test, but its scope is the exact files, output color order, decode
options, and builds recorded here.

An application should choose its contract from downstream requirements. A
content-addressed cache may need exact array bytes. A numerical pipeline may
instead define a bounded difference and separately test its effect on derived
features. A display workflow needs color-management and perceptual evaluation
that this experiment does not provide.

## Failure Modes

- A decoder can preserve dimensions and DQT metadata while producing a
  different pixel array through IDCT, upsampling, or color-conversion choices.
- Grayscale, RGB, and BGR output requests can create apparent disagreements if
  channel order is not normalized before comparison.
- Re-encoding on every platform confounds encoder and decoder portability.
- An exact SHA-256 comparison reveals any difference but provides no magnitude
  or perceptual interpretation.
- A maximum-error bound hides how many samples changed unless a changed-sample
  fraction is reported beside it.
- Runner labels alone are incomplete provenance because hosted images and
  bundled wheel internals can change.
- Passing a small synthetic corpus does not guarantee behavior for progressive,
  CMYK, malformed, metadata-rich, or unusual-sampling JPEG files.

## Practical Guidance

1. Keep the compressed fixture bytes fixed when testing decoder portability.
2. Record wrapper, backend, operating system, architecture, SIMD policy, and
   runner image identifiers.
3. Test marker structure and output interface before comparing pixels.
4. Report exact hashes and numerical differences separately.
5. Treat any tolerance as an application contract, not a JPEG quality score.
6. Re-evaluate downstream metrics if decoded pixels differ, even when the
   numerical error appears small.
7. Expand the fixture corpus around the formats and color paths the application
   actually accepts.

## Limitations

- Both Python wrappers use builds from the libjpeg-turbo family; this is not an
  independent codec-family comparison.
- The corpus contains 12 baseline sequential, eight-bit, three-component JPEG
  streams generated from only three synthetic patterns.
- Numeric quality controls 50 and 95 and sampling modes 4:4:4 and 4:2:0 do not
  cover the full JPEG syntax or real encoder diversity.
- The PNG anchors are OpenCV BGR reference decodes, not original scene truth.
- The within-one bound is intentionally narrow and arbitrary outside this
  regression study. No perceptual significance is claimed.
- GitHub-hosted runner results are snapshots of the recorded runner images and
  wheels, not guarantees for all machines using the same operating-system name.
- The experiment does not cover ICC profiles, EXIF orientation, CMYK/YCCK,
  progressive scans, restart-marker stress, damaged files, reduced-scale IDCT,
  hardware decoders, or human judgments.

## Sources

- [JPEG 1 overview and standard parts](https://jpeg.org/jpeg/)
- [ITU-T T.81: Digital compression and coding of continuous-tone still images](https://www.itu.int/rec/T-REC-T.81-199209-I/en)
- [libjpeg-turbo README: mathematical compatibility and SIMD controls](https://github.com/libjpeg-turbo/libjpeg-turbo#mathematical-compatibility)
- [Pillow feature and codec reporting](https://pillow.readthedocs.io/en/stable/reference/features.html)
- [OpenCV image decoding documentation](https://docs.opencv.org/4.x/d4/da8/group__imgcodecs.html)
- [OpenCV build information API](https://docs.opencv.org/4.x/db/de0/group__core__utils.html)
- [GitHub-hosted runner reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
- [GitHub Actions workflow artifacts](https://docs.github.com/en/actions/concepts/workflows-and-actions/workflow-artifacts)
