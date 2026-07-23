# Independent Codec Families and Advanced JPEG Syntax

## Research Question

How do fixed synthetic JPEG streams decode through the libjpeg-turbo family
and FFmpeg's native MJPEG decoder when the streams use progressive scans,
restart markers, grayscale, or CMYK components?

The study separates three questions:

1. Does each stream retain its declared marker-level syntax?
2. Does every decoder return the declared 128 x 128, three-channel, `uint8`
   BGR interface?
3. Which pixel differences come from decoder-family output rather than from
   progressive scan organization or restart-marker insertion?

Exact equality and a maximum difference of one integer code value are reported
separately. The latter remains a narrow regression diagnostic, not a
perceptual threshold or a default acceptance rule.

## Background

ITU-T T.81 defines multiple JPEG DCT processes. Baseline sequential streams
use an SOF0 frame, while progressive DCT streams use SOF2 and distribute
coefficient information over multiple scans. A DRI segment declares a restart
interval, and RST0 through RST7 markers divide entropy-coded data into restart
segments. These syntax choices affect stream organization and error recovery;
they do not inherently require a different final coefficient field.

Pillow documents support for standard and progressive JPEG, grayscale, RGB,
and CMYK data, plus restart-marker controls. OpenCV exposes JPEG flags for
progressive output and restart intervals. These APIs make it possible to build
a fixed, generated corpus without external photographs.

OpenCV and Pillow report libjpeg-turbo-family backends in the pinned wheels.
The third path uses the native `mjpeg` decoder in FFmpeg's libavcodec and emits
explicit `bgr24` raw output. The `imageio-ffmpeg` wheel supplies a
platform-specific FFmpeg executable, allowing the same adapter contract to run
on the five CI profiles. The experiment records the executable version and a
fingerprint of its build configuration without recording a local path.

## Method Selection

A fixed compressed corpus is required. Re-encoding on each operating system
would mix encoder differences with decoder differences. Each JPEG file,
marker summary, and lossless BGR reference is therefore committed once and
validated by SHA-256 before decoding.

The BGR reference PNG is the pinned OpenCV decode of that JPEG, not the
uncompressed synthetic source and not an assertion that OpenCV is universally
correct. OpenCV is exact against this anchor by construction. The useful
comparisons are the other decoder outputs, direct decoder pairs, and controlled
syntax pairs decoded by the same implementation.

## Advanced-Syntax Corpus

The experiment generates one 128 x 128 BGR pattern containing gradients,
hard chromatic boundaries, geometric shapes, and an eight-pixel tile
modulation. A deterministic grayscale conversion and a separate four-channel
CMYK pattern provide the other source modes. All JPEGs use numeric quality
control 75.

The ten fixed streams are:

| Control | Source | Frame | Sampling | Scans | Restart interval |
| --- | --- | --- | --- | ---: | ---: |
| RGB baseline | BGR | SOF0 | 4:4:4 | 1 | 0 |
| RGB progressive | BGR | SOF2 | 4:4:4 | 10 | 0 |
| RGB baseline | BGR | SOF0 | 4:2:0 | 1 | 0 |
| RGB restart | BGR | SOF0 | 4:2:0 | 1 | 4 |
| RGB progressive | BGR | SOF2 | 4:2:0 | 10 | 0 |
| RGB progressive restart | BGR | SOF2 | 4:2:0 | 10 | 4 |
| Grayscale baseline | L | SOF0 | grayscale | 1 | 0 |
| Grayscale progressive | L | SOF2 | grayscale | 6 | 0 |
| CMYK baseline | CMYK | SOF0 | four components | 1 | 0 |
| CMYK progressive | CMYK | SOF2 | four components | 18 | 0 |

The baseline RGB restart stream contains 15 restart markers. The progressive
restart stream contains 342 because restart markers occur across its ten
scans. The CMYK streams contain an Adobe APP14 marker with transform value 0
and no JFIF marker. These are observed properties of the committed files, not
claims about every encoder using the same controls.

## Controlled Experiment

Each platform profile runs these three adapters:

- OpenCV 4.13.0 through its reported libjpeg-turbo build;
- Pillow 12.3.0 through its reported libjpeg-turbo build;
- imageio-ffmpeg 0.6.0 through FFmpeg's native MJPEG decoder and `bgr24`
  conversion.

For every fixture and decoder, the experiment records shape, dtype, exact
array hash, maximum and mean absolute error, changed-sample and changed-pixel
fractions, and Laplacian-variance and Tenengrad ratios to the reference. It
also records all three within-fixture decoder pairs.

Five controlled syntax pairs compare the same decoded content before and
after only one stream-organization change:

- 4:4:4 baseline versus progressive;
- 4:2:0 baseline versus restart markers;
- 4:2:0 progressive versus progressive plus restart markers;
- grayscale baseline versus progressive;
- CMYK baseline versus progressive.

Across three decoders, this produces 15 syntax-equivalence observations per
platform. No exact or bounded pixel result is assumed by the validation code;
only stream coverage and the BGR array interface are mandatory.

### Reproduction

```bash
python -m pip install -e ".[test]"
python -m pytest
python experiments/run_advanced_jpeg_syntax.py
```

Regenerate the synthetic fixture provenance only when intentionally auditing
the committed corpus:

```bash
python experiments/run_advanced_jpeg_syntax.py --refresh-fixtures
```

## Results

### Local Linux x64 reference

All 30 decoder observations satisfied the shape and dtype contracts. OpenCV
matched all ten BGR anchors, as expected from the reference definition. Pillow
matched eight of ten exactly; both CMYK streams differed with maximum error 2
and changed-sample fraction 0.802979. FFmpeg did not exactly match the OpenCV
anchor for any fixture. Its two grayscale outputs stayed within one code
value, changing 0.005432 of samples.

For the 4:4:4 RGB streams, FFmpeg's maximum error was 3 and the changed-sample
fraction was 0.017171. For the 4:2:0 RGB streams, the maximum error was 79,
the mean absolute error was 3.897746, and 0.867371 of channel samples changed.
The synthetic pattern deliberately contains hard chromatic boundaries, so
this condition exposes differences in chroma reconstruction and BGR
conversion rather than estimating a natural-image error distribution.

The derivative metrics moved less than the largest individual channel errors.
For the FFmpeg 4:2:0 result, the Laplacian-variance ratio was 1.026871 and the
Tenengrad ratio was 1.012696. This does not make the difference perceptually
small; it shows that a large local channel difference and a modest aggregate
derivative change are different measurements.

All 15 controlled syntax comparisons were pixel-exact. Within each decoder,
progressive scan organization and restart-marker insertion preserved the final
array for these paired streams. This isolates the observed cross-family
differences from those two syntax controls in this corpus.

### Cross-platform matrix

The release CI executes the same fixed streams on Ubuntu x64 with default and
forced-scalar libjpeg-turbo paths, Windows x64, macOS arm64, and macOS Intel
x64. The aggregate snapshot records decoder hashes, pairwise errors, controlled
syntax comparisons, codec builds, and runner image identifiers. Cross-platform
claims are added only from the successful release workflow.

## Interpretation

Supporting a JPEG syntax and reproducing another decoder's BGR array are
different contracts. All three decoder families accepted every committed
progressive, restart, grayscale, RGB, and CMYK stream and returned the declared
array interface. Exact pixel portability was narrower.

The exact syntax-pair results show that progressive scans and restart markers
were not the cause of the local decoder-family differences. The largest
difference instead appears on the 4:2:0 chromatic pattern, where upsampling and
color conversion are part of the observable decode path. The CMYK result also
depends on an application-visible conversion from four encoded components to
three BGR channels.

An application that requires cache identity or checksum stability should test
exact decoded arrays. A numerical pipeline should measure the downstream
features it actually consumes. A display or publishing workflow additionally
needs explicit color-management and perceptual evaluation; neither is supplied
by a small code-value diagnostic.

## Failure Modes

- Treating successful decode as proof of identical reconstructed pixels.
- Calling two Python wrappers independent codec families when both report
  libjpeg-turbo backends.
- Comparing CMYK component arrays directly with BGR outputs without declaring
  the conversion contract.
- Attributing 4:2:0 output differences to progressive scans when sampling and
  color reconstruction have not been controlled separately.
- Using one maximum error without reporting its frequency or location.
- Re-encoding fixtures on each runner and thereby confounding encoder and
  decoder behavior.
- Treating an FFmpeg executable name or operating-system label as complete
  build provenance.

## Practical Guidance

1. Keep compressed bytes fixed when evaluating decoder portability.
2. Record frame, scan, DRI, RST, component, JFIF, and Adobe marker properties.
3. Normalize output channel order and dtype before comparing arrays.
4. Test structural support, exact pixels, numerical magnitude, and downstream
   feature response separately.
5. Include hard chromatic boundaries when 4:2:0 upsampling matters, but do not
   present that synthetic stress pattern as a natural-image distribution.
6. Pair baseline, progressive, and restart streams with matched DQT and source
   controls before assigning causality.
7. Treat every numerical bound as an application contract, not a JPEG quality
   score.

## Limitations

- The corpus has ten small, 8-bit synthetic JPEGs at one numeric quality
  control. It is a syntax and regression fixture set, not a content benchmark.
- OpenCV defines the BGR reference, so its exact-reference rate is tautological.
- OpenCV and Pillow remain two wrappers over the libjpeg-turbo family; only the
  FFmpeg path adds a separate decoder implementation.
- The CMYK files use the observed Adobe transform value 0. YCCK is not covered.
- The study does not include arithmetic coding, lossless JPEG, hierarchical
  modes, 12-bit samples, abbreviated table streams, malformed entropy data, or
  restart corruption and recovery.
- ICC profiles, EXIF orientation, rendering intents, monitor transforms, and
  human judgments are outside the declared BGR contract.
- Bundled FFmpeg binaries and hosted runner images are recorded release
  snapshots, not guarantees for every build with a similar version label.
- Maximum error, changed fraction, Laplacian variance, and Tenengrad do not
  replace a task-specific or perceptual evaluation.

## Sources

- [ITU-T T.81: Digital compression and coding of continuous-tone still images](https://www.itu.int/rec/T-REC-T.81-199209-I/en)
- [OpenCV JPEG reading and writing flags](https://docs.opencv.org/4.x/d8/d6a/group__imgcodecs__flags.html)
- [Pillow JPEG format documentation](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#jpeg)
- [FFmpeg codec documentation](https://ffmpeg.org/ffmpeg-codecs.html)
- [FFmpeg native MJPEG decoder source](https://ffmpeg.org/doxygen/trunk/mjpegdec_8c_source.html)
- [imageio-ffmpeg platform binary packaging](https://github.com/imageio/imageio-ffmpeg)
- [libjpeg-turbo mathematical compatibility notes](https://github.com/libjpeg-turbo/libjpeg-turbo#mathematical-compatibility)
- [GitHub-hosted runner reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
