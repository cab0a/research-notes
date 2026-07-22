# Optical Blur Models and Directional Motion Sensitivity

## Research Question

How do Laplacian variance and Tenengrad energy respond to two different
space-invariant blur models: a circular disk point-spread function (PSF) for a
bounded defocus approximation and a line PSF for uniform linear motion? How
strongly do motion direction, image orientation, and additive noise change the
interpretation of either scalar focus measure?

## Background

An idealized spatially invariant degradation can be written as

```text
observed = quantize(PSF * sharp + noise)
```

where `*` denotes convolution. OpenCV's out-of-focus tutorial uses a circular
PSF parameterized by radius as an approximation of out-of-focus distortion.
Its motion tutorial models uniform linear motion with a line-segment PSF
parameterized by length and angle. These are useful controlled models, but they
are not interchangeable descriptions of physical severity.

Laplacian variance measures the spread of a second-derivative response.
Tenengrad energy averages squared horizontal and vertical Sobel responses.
Both collapse spatial and directional structure into one scalar. A line PSF is
anisotropic, so the scalar can depend on the angle between motion and the
image's intensity variation. A disk PSF is isotropic in the continuous model,
but sampled image content and discrete operators still affect the score.

Primary work on motion-blur identification reports that image characteristics
along the motion direction differ from those in other directions. Work on
defocus calibration also shows that a real blur kernel depends on aperture and
camera geometry and can depart from a simple Gaussian or pillbox model. The
experiment therefore treats the PSFs as declared synthetic controls, not as
calibrated camera simulations.

## Method Selection

The experiment uses two normalized, centered, centrosymmetric kernels:

- `disk_psf(radius)` assigns equal weight to pixel centers inside an integer
  radius. Radius zero is the identity control.
- `linear_motion_psf(length, angle)` samples a centered continuous line at 32
  samples per pixel and distributes each sample bilinearly to the image grid.
  Lengths are positive odd integers. Zero degrees is horizontal; positive
  angles rotate toward increasing image rows.

Every PSF is applied with OpenCV `filter2D`, 64-bit intermediate output, and
`BORDER_REFLECT_101`, followed by rounding and clipping to 8-bit grayscale.
Correlation and convolution are equivalent here because the declared kernels
are centrosymmetric. The committed kernel audit records support, weight sum,
centroid offset, root-mean-square radius, and centrosymmetry error rather than
assuming that kernel construction succeeded.

Laplacian variance and area-normalized Tenengrad retain the definitions from
the earlier notes. Scores are reported in raw units and as a ratio to the sharp
version of the same pattern with the same noise realization. The paired ratio
controls noise sampling, but it does not make scores transferable between
unseen content or imaging pipelines.

## Controlled Experiment

Five 256 x 256, 8-bit grayscale patterns are generated in code:

- four sinusoidal gratings with intensity-gradient axes at 0, 45, 90, and 135
  degrees and a period of 16 pixels;
- one 16-pixel checkerboard containing mixed horizontal and vertical edges.

Seventeen blur conditions are evaluated:

- one identity condition;
- disk-defocus radii 1, 2, 3, and 5 pixels;
- linear-motion lengths 5, 9, and 15 pixels at 0, 45, 90, and 135 degrees.

Gaussian noise with standard deviation 0, 5, or 15 is added after blur. Ten
trials are run for every noise level. A deterministic seed is derived from the
pattern, noise level, and trial, yielding 150 declared seeds. The same noise
field is reused across all blur conditions within a paired trial.

For a grating, relative motion angle is defined against its intensity-gradient
axis:

- 0 degrees: aligned motion crosses the bands;
- 45 degrees: oblique motion;
- 90 degrees: perpendicular motion follows the bands.

The experiment produces:

- 17 PSF audit rows;
- 5,100 long-form metric trial observations;
- 510 pattern-condition summaries;
- 72 motion-direction summaries;
- one visual example figure and one sensitivity figure.

No score is converted into a universal sharp/blurred label. Disk radius and
motion length are not matched as equivalent blur severities.

## Results

### Disk-defocus response

The following values average the clean matched-sharp ratios across all five
patterns. The shaded range in the committed figure retains the pattern spread.

| Disk radius | Laplacian variance | Tenengrad energy |
| ---: | ---: | ---: |
| 0 | 1.000000 | 1.000000 |
| 1 | 0.737339 | 0.881609 |
| 2 | 0.624818 | 0.760229 |
| 3 | 0.499276 | 0.604801 |
| 5 | 0.240865 | 0.294238 |

The mean response decreases over the declared radii, but the radius-5 result
is strongly content-dependent. Laplacian ratios range from 0.005603 for the
checkerboard to 0.316571 for an axis-aligned grating. Tenengrad ratios range
from 0.146223 to 0.334416. A radius value alone therefore does not determine a
content-independent score ratio.

At radius 5, adding noise standard deviation 5 raises the mean raw Laplacian
response to 9.494 times its noise-free value; noise standard deviation 15
raises it to 76.516 times. The corresponding Tenengrad factors are 1.024 and
1.229. These are averages over the declared patterns, not general noise laws.

### Directional motion response

Clean grating ratios averaged across the four gradient axes are:

| Metric | Length | Aligned | Oblique | Perpendicular |
| --- | ---: | ---: | ---: | ---: |
| Laplacian variance | 5 | 0.724007 | 0.830651 | 0.920052 |
| Laplacian variance | 9 | 0.368915 | 0.593747 | 0.910804 |
| Laplacian variance | 15 | 0.057063 | 0.212284 | 0.915820 |
| Tenengrad energy | 5 | 0.786001 | 0.880024 | 0.986888 |
| Tenengrad energy | 9 | 0.390506 | 0.632152 | 0.981138 |
| Tenengrad energy | 15 | 0.023614 | 0.223583 | 0.974244 |

At length 15 without noise, the mean aligned-to-perpendicular ratio is
0.066796 for Laplacian variance and 0.024429 for Tenengrad. The experiment's
strongest attenuating angle matches the declared gradient axis in every clean
grating condition.

Noise reduces this directional contrast differently for the two metrics:

| Noise standard deviation | Laplacian aligned/perpendicular | Tenengrad aligned/perpendicular |
| ---: | ---: | ---: |
| 0 | 0.066796 | 0.024429 |
| 5 | 0.789762 | 0.035051 |
| 15 | 1.008207 | 0.112947 |

At noise standard deviation 15, the Laplacian ratio is approximately one and
slightly reversed. In this bounded experiment, isotropic high-frequency noise
dominates the second-derivative response enough to hide the underlying motion
direction. Tenengrad retains more directional separation, but its ratio also
moves toward one.

The reference figures are
[`optical_blur_examples.png`](../results/optical_blur_examples.png) and
[`optical_blur_directional_sensitivity.png`](../results/optical_blur_directional_sensitivity.png).

## Interpretation

The scalar response depends on an interaction, not on blur extent alone:

```text
score = f(PSF model, PSF parameters, content spectrum, relative angle,
          noise, sampling, border rule, quantization, metric definition)
```

Disk defocus attenuates every tested orientation because its declared support
is isotropic, but the amount differs with pattern spectrum. Linear motion can
nearly remove a periodic grating when it crosses the bands while leaving the
same grating almost unchanged when it follows the bands. A high score in the
perpendicular case does not prove absence of motion; it means the visible
content provides little variation along that motion path.

The two metrics also emphasize different frequency content. The Laplacian's
second derivative makes it especially responsive to added high-frequency
noise. Tenengrad is not noise-invariant, but in this experiment its directional
contrast survives the tested noise levels better.

The PSF audit helps prevent a second mistake: equating parameter labels. A
radius-5 disk has RMS radius 3.603839 pixels, while a length-15 horizontal line
has RMS radius 4.070919 pixels. Even similar scalar spread would not make their
frequency responses or directional behavior equivalent.

## Failure Modes

1. **Orientation blind spot:** Motion along a locally constant direction can
   preserve a derivative score even when the declared PSF is long.
2. **Noise domination:** Added noise can erase or reverse score differences,
   especially for Laplacian variance.
3. **Content-spectrum dependence:** Periodic texture and mixed edges respond to
   the same disk radius by different ratios.
4. **Model ambiguity:** One scalar score cannot identify whether attenuation
   came from defocus, motion, preprocessing, resize, or another low-pass
   process.
5. **Rasterization dependence:** Diagonal line kernels require discrete
   sampling. Bilinear rasterization, derivative kernels, borders, and 8-bit
   quantization affect exact values.
6. **Optical-model mismatch:** A uniform disk omits aperture shape,
   diffraction, aberrations, depth variation, and sensor characteristics. A
   straight line omits acceleration, rotation, rolling shutter, and spatially
   varying motion.

## Practical Guidance

- Calibrate on the expected blur family, content scale, noise range, and
  processing pipeline instead of transferring one absolute threshold.
- Include structures at multiple orientations. A single directional texture
  cannot expose every motion direction.
- Inspect directional or local response maps when motion is plausible; a
  whole-image scalar discards the evidence needed to infer direction.
- Estimate or control noise before interpreting second-derivative energy.
- Store the PSF construction, border rule, quantization, and metric definition
  with experimental results.
- Compare disk and line models through declared response curves, not by
  assuming that radius and length labels are equivalent.
- Treat matched-sharp ratios as experimental controls. In blind inspection,
  the sharp reference and true PSF are usually unavailable.

## Limitations

This study uses synthetic, global, space-invariant blur on 8-bit grayscale
images. It evaluates one grating frequency, four motion angles, three motion
lengths, four disk radii, three noise levels, and one border rule. Noise is
additive, Gaussian, and applied after blur. The study does not include natural
images, measured camera PSFs, color filter arrays, demosaicing, compression,
spatially varying depth, local motion, acceleration, rotation, rolling shutter,
diffraction, aberration, deconvolution, or human judgments.

The disk PSF is a controlled approximation, not a complete optical simulator.
The line PSF represents uniform translation only. The observed relative
ordering and numerical values are evidence for these declared conditions and
must not be presented as universal image-quality thresholds or production
accuracy estimates.

## Sources

- [OpenCV: Motion Deblur Filter](https://docs.opencv.org/4.x/d1/dfd/tutorial_motion_deblur_filter.html)
  describes a linear-motion PSF as a line segment parameterized by length and
  angle.
- [OpenCV: Out-of-focus Deblur Filter](https://docs.opencv.org/4.x/de/d3c/tutorial_out_of_focus_deblur_filter.html)
  presents the degradation model and a circular PSF approximation controlled
  by radius.
- [OpenCV: Image Filtering](https://docs.opencv.org/4.x/d4/d86/group__imgproc__filter.html)
  is the official reference for `filter2D`, `Sobel`, and `Laplacian`.
- [Identification of Blur Parameters from Motion Blurred Images](https://doi.org/10.1006/gmip.1997.0435)
  is a primary study of motion-PSF direction and extent using directional image
  characteristics.
- [Blur Calibration for Depth from Defocus](https://doi.org/10.1109/CRV.2016.62)
  is a primary study showing why camera-dependent defocus kernels require
  calibration beyond a simple generic approximation. A public author copy is
  also available from the
  [McGill Computational Vision Lab](https://www.cim.mcgill.ca/~fmannan/CRV16/Calib.pdf).
- [Analysis of focus measure operators for shape-from-focus](https://doi.org/10.1016/j.patcog.2012.11.011)
  defines Tenengrad from squared Sobel responses and evaluates focus-measure
  behavior under controlled factors including noise.
