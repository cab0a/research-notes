"""Tests for focus metrics, preprocessing, and controlled blur models."""

import cv2
import numpy as np
import pytest

from research_notes import (
    apply_psf,
    classify_decoded_pixel_contract,
    compare_decoded_pixels,
    disk_psf,
    decode_jpeg_ffmpeg,
    decode_jpeg_opencv,
    decode_jpeg_pillow,
    encode_jpeg_opencv,
    encode_jpeg_pillow,
    encode_jpeg_cmyk_pillow,
    gaussian_denoise,
    gamma_transform,
    jpeg_encode_decode,
    jpeg_round_trip,
    laplacian_variance,
    linear_intensity_transform,
    linear_motion_psf,
    minmax_normalize,
    inspect_jpeg_syntax,
    parse_jpeg_structure,
    pixel_array_sha256,
    repeated_jpeg_round_trip,
    resize_round_trip,
    sliding_metric_map,
    tenengrad_energy,
    tiled_metric_map,
    to_grayscale,
    unsharp_mask,
)


def make_checkerboard(size: int = 128, cell_size: int = 8) -> np.ndarray:
    """Return a test checkerboard with controlled spatial frequency."""
    rows, columns = np.indices((size, size))
    return (((rows // cell_size + columns // cell_size) % 2) * 255).astype(
        np.uint8
    )


def make_grating(
    angle_degrees: float, size: int = 128, period: float = 16.0
) -> np.ndarray:
    """Return a sinusoidal grating whose gradient axis has a known angle."""
    rows, columns = np.indices((size, size), dtype=np.float64)
    angle_radians = np.deg2rad(angle_degrees)
    phase = columns * np.cos(angle_radians) + rows * np.sin(angle_radians)
    values = 127.5 + 110.0 * np.cos(2.0 * np.pi * phase / period)
    return np.clip(np.rint(values), 0, 255).astype(np.uint8)


def test_constant_image_has_zero_laplacian_variance() -> None:
    image = np.full((64, 64), 127, dtype=np.uint8)

    assert laplacian_variance(image) == pytest.approx(0.0)


def test_constant_image_has_zero_tenengrad_energy() -> None:
    image = np.full((64, 64), 127, dtype=np.uint8)

    assert tenengrad_energy(image) == pytest.approx(0.0)


def test_noiseless_blur_produces_strictly_decreasing_scores() -> None:
    sharp = make_checkerboard()
    images = [sharp]
    images.extend(
        cv2.GaussianBlur(
            sharp,
            (0, 0),
            sigmaX=float(sigma),
            sigmaY=float(sigma),
            borderType=cv2.BORDER_REFLECT_101,
        )
        for sigma in (1, 2, 3)
    )
    scores = [laplacian_variance(image) for image in images]

    assert all(left > right for left, right in zip(scores, scores[1:]))


def test_noiseless_blur_produces_strictly_decreasing_tenengrad() -> None:
    sharp = make_checkerboard()
    images = [sharp]
    images.extend(
        cv2.GaussianBlur(
            sharp,
            (0, 0),
            sigmaX=float(sigma),
            sigmaY=float(sigma),
            borderType=cv2.BORDER_REFLECT_101,
        )
        for sigma in (1, 2, 3)
    )
    scores = [tenengrad_energy(image) for image in images]

    assert all(left > right for left, right in zip(scores, scores[1:]))


def test_noise_can_raise_score_for_a_blurred_image() -> None:
    sharp = make_checkerboard()
    blurred = cv2.GaussianBlur(sharp, (0, 0), sigmaX=3.0, sigmaY=3.0)
    generator = np.random.default_rng(20260721)
    noise = generator.normal(0.0, 15.0, blurred.shape)
    noisy_blurred = np.clip(blurred.astype(np.float64) + noise, 0, 255).astype(
        np.uint8
    )

    assert laplacian_variance(noisy_blurred) > laplacian_variance(blurred)


def test_noise_can_raise_tenengrad_for_a_blurred_image() -> None:
    sharp = make_checkerboard()
    blurred = cv2.GaussianBlur(sharp, (0, 0), sigmaX=3.0, sigmaY=3.0)
    generator = np.random.default_rng(20260820)
    noise = generator.normal(0.0, 15.0, blurred.shape)
    noisy_blurred = np.clip(blurred.astype(np.float64) + noise, 0, 255).astype(
        np.uint8
    )

    assert tenengrad_energy(noisy_blurred) > tenengrad_energy(blurred)


def test_bgr_and_grayscale_inputs_agree() -> None:
    grayscale = make_checkerboard()
    bgr = cv2.cvtColor(grayscale, cv2.COLOR_GRAY2BGR)

    assert laplacian_variance(bgr) == pytest.approx(laplacian_variance(grayscale))
    assert tenengrad_energy(bgr) == pytest.approx(tenengrad_energy(grayscale))


def test_invalid_shape_is_rejected() -> None:
    with pytest.raises(ValueError, match="grayscale, BGR, or BGRA"):
        laplacian_variance(np.zeros((8, 8, 2), dtype=np.uint8))


def test_tiled_metric_map_returns_one_score_per_tile() -> None:
    image = make_checkerboard(size=128)

    scores = tiled_metric_map(image, laplacian_variance, tile_size=64)

    assert scores.shape == (2, 2)
    assert np.all(scores > 0.0)
    assert np.all(scores == pytest.approx(scores[0, 0]))


def test_local_blur_reduces_only_the_selected_tile_score() -> None:
    sharp = make_checkerboard(size=128)
    blurred = cv2.GaussianBlur(sharp, (0, 0), sigmaX=3.0, sigmaY=3.0)
    observed = sharp.copy()
    observed[:64, :64] = blurred[:64, :64]

    reference = tiled_metric_map(sharp, tenengrad_energy, tile_size=64)
    ratios = tiled_metric_map(observed, tenengrad_energy, tile_size=64) / reference

    assert ratios[0, 0] < 1.0
    assert ratios[0, 1] == pytest.approx(1.0)
    assert ratios[1, 0] == pytest.approx(1.0)
    assert ratios[1, 1] == pytest.approx(1.0)


def test_tiled_metric_map_rejects_non_divisible_dimensions() -> None:
    image = np.zeros((65, 64), dtype=np.uint8)

    with pytest.raises(ValueError, match="divisible"):
        tiled_metric_map(image, laplacian_variance, tile_size=32)


def test_sliding_metric_map_supports_overlapping_windows() -> None:
    image = make_checkerboard(size=128)

    scores = sliding_metric_map(
        image, laplacian_variance, window_size=64, stride=32
    )

    assert scores.shape == (3, 3)
    assert np.all(scores > 0.0)


def test_sliding_map_matches_tiled_map_when_stride_equals_size() -> None:
    image = make_checkerboard(size=128)

    tiled = tiled_metric_map(image, tenengrad_energy, tile_size=64)
    sliding = sliding_metric_map(
        image, tenengrad_energy, window_size=64, stride=64
    )

    assert sliding == pytest.approx(tiled)


def test_sliding_metric_map_rejects_incomplete_boundary_coverage() -> None:
    image = np.zeros((128, 128), dtype=np.uint8)

    with pytest.raises(ValueError, match="end at the image boundary"):
        sliding_metric_map(image, laplacian_variance, window_size=64, stride=48)


def test_jpeg_round_trip_is_deterministic_and_preserves_shape() -> None:
    image = make_checkerboard()

    first = jpeg_round_trip(image, quality=75)
    second = jpeg_round_trip(image, quality=75)

    assert first.shape == image.shape
    assert first.dtype == np.uint8
    assert np.array_equal(first, second)


def test_resize_round_trip_reduces_checkerboard_derivative_energy() -> None:
    image = make_checkerboard()

    resized = resize_round_trip(image, scale=0.5)

    assert resized.shape == image.shape
    assert laplacian_variance(resized) < laplacian_variance(image)
    assert tenengrad_energy(resized) < tenengrad_energy(image)


def test_gaussian_denoise_reduces_seeded_noise_response() -> None:
    image = make_checkerboard()
    generator = np.random.default_rng(20261001)
    noisy = np.clip(
        image.astype(np.float64) + generator.normal(0.0, 15.0, image.shape),
        0,
        255,
    ).astype(np.uint8)

    denoised = gaussian_denoise(noisy, sigma=1.0)

    assert laplacian_variance(denoised) < laplacian_variance(noisy)
    assert tenengrad_energy(denoised) < tenengrad_energy(noisy)


def test_unsharp_mask_increases_blurred_checkerboard_response() -> None:
    image = make_checkerboard()
    blurred = cv2.GaussianBlur(image, (0, 0), sigmaX=2.0, sigmaY=2.0)

    sharpened = unsharp_mask(blurred, amount=1.0, sigma=1.0)

    assert laplacian_variance(sharpened) > laplacian_variance(blurred)
    assert tenengrad_energy(sharpened) > tenengrad_energy(blurred)


def test_preprocessing_parameters_are_validated() -> None:
    image = make_checkerboard()

    with pytest.raises(ValueError, match=r"\[1, 100\]"):
        jpeg_round_trip(image, quality=0)
    with pytest.raises(ValueError, match=r"\(0, 1\]"):
        resize_round_trip(image, scale=0.0)
    with pytest.raises(ValueError, match="positive"):
        gaussian_denoise(image, sigma=0.0)
    with pytest.raises(ValueError, match="not be negative"):
        unsharp_mask(image, amount=-0.1, sigma=1.0)


def test_disk_psf_is_normalized_and_centrosymmetric() -> None:
    kernel = disk_psf(radius=3)

    assert kernel.shape == (7, 7)
    assert np.sum(kernel) == pytest.approx(1.0)
    assert kernel == pytest.approx(np.flip(kernel))


def test_linear_motion_psf_is_normalized_and_centrosymmetric() -> None:
    kernel = linear_motion_psf(length=15, angle_degrees=45)

    assert kernel.shape == (15, 15)
    assert np.sum(kernel) == pytest.approx(1.0)
    assert kernel == pytest.approx(np.flip(kernel), abs=1e-12)


def test_identity_psf_preserves_an_image() -> None:
    image = make_checkerboard()

    assert np.array_equal(apply_psf(image, disk_psf(radius=0)), image)
    assert np.array_equal(
        apply_psf(image, linear_motion_psf(length=1, angle_degrees=37)),
        image,
    )


def test_aligned_motion_reduces_grating_more_than_perpendicular() -> None:
    image = make_grating(angle_degrees=0)
    aligned = apply_psf(image, linear_motion_psf(15, angle_degrees=0))
    perpendicular = apply_psf(
        image, linear_motion_psf(15, angle_degrees=90)
    )

    assert laplacian_variance(aligned) < laplacian_variance(perpendicular)
    assert tenengrad_energy(aligned) < tenengrad_energy(perpendicular)


def test_blur_model_parameters_are_validated() -> None:
    image = make_checkerboard()

    with pytest.raises(ValueError, match="not be negative"):
        disk_psf(radius=-1)
    with pytest.raises(ValueError, match="positive odd"):
        linear_motion_psf(length=4, angle_degrees=0)
    with pytest.raises(ValueError, match="finite"):
        linear_motion_psf(length=5, angle_degrees=float("nan"))
    with pytest.raises(ValueError, match="sum to one"):
        apply_psf(image, np.ones((3, 3), dtype=np.float64))


def test_linear_intensity_transform_rounds_and_clips() -> None:
    image = np.array([[0, 32, 128, 240]], dtype=np.uint8)

    transformed = linear_intensity_transform(image, alpha=1.25, beta=-20)

    assert np.array_equal(
        transformed,
        np.array([[0, 20, 140, 255]], dtype=np.uint8),
    )


def test_gamma_transform_preserves_endpoints_and_is_monotonic() -> None:
    image = np.arange(256, dtype=np.uint8).reshape(16, 16)

    transformed = gamma_transform(image, gamma=0.7)

    assert transformed[0, 0] == 0
    assert transformed[-1, -1] == 255
    assert np.all(np.diff(transformed.ravel().astype(np.int16)) >= 0)


def test_minmax_normalize_uses_observed_range() -> None:
    image = np.array([[20, 40], [60, 80]], dtype=np.uint8)

    normalized = minmax_normalize(image)

    assert normalized.min() == 0
    assert normalized.max() == 255
    assert np.array_equal(
        minmax_normalize(np.full((4, 4), 7, np.uint8)),
        np.zeros((4, 4), np.uint8),
    )


def test_repeated_jpeg_is_deterministic_and_zero_rounds_are_identity() -> None:
    grayscale = make_checkerboard(cell_size=7)
    color = cv2.applyColorMap(grayscale, cv2.COLORMAP_TURBO)

    first = repeated_jpeg_round_trip(color, quality=75, rounds=2)
    second = repeated_jpeg_round_trip(color, quality=75, rounds=2)

    assert np.array_equal(first, second)
    assert first.shape == color.shape
    assert first.dtype == np.uint8
    assert np.array_equal(
        repeated_jpeg_round_trip(grayscale, quality=75, rounds=0), grayscale
    )


def test_explicit_jpeg_sampling_is_deterministic_and_preserves_shape() -> None:
    grayscale = make_checkerboard(cell_size=7)
    color = cv2.applyColorMap(grayscale, cv2.COLORMAP_TURBO)

    first = jpeg_encode_decode(color, quality=75, chroma_sampling="420")
    second = jpeg_encode_decode(color, quality=75, chroma_sampling="420")

    assert np.array_equal(first, second)
    assert first.shape == color.shape
    assert first.dtype == np.uint8


def test_chroma_sampling_can_change_a_chromatic_metric_response() -> None:
    grayscale = make_checkerboard(cell_size=7)
    color = cv2.applyColorMap(grayscale, cv2.COLORMAP_TURBO)
    sampling_444 = to_grayscale(
        jpeg_encode_decode(color, quality=75, chroma_sampling="444")
    )
    sampling_420 = to_grayscale(
        jpeg_encode_decode(color, quality=75, chroma_sampling="420")
    )

    assert laplacian_variance(sampling_444) != pytest.approx(
        laplacian_variance(sampling_420)
    )


def test_jpeg_quality_order_can_change_recompression_response() -> None:
    image = make_checkerboard(cell_size=7)
    high_then_low = jpeg_encode_decode(
        jpeg_encode_decode(image, quality=95), quality=50
    )
    low_then_high = jpeg_encode_decode(
        jpeg_encode_decode(image, quality=50), quality=95
    )

    assert not np.array_equal(high_then_low, low_then_high)
    assert tenengrad_energy(high_then_low) != pytest.approx(
        tenengrad_energy(low_then_high)
    )


def test_jpeg_structure_exposes_dqt_and_component_sampling() -> None:
    grayscale = make_checkerboard(cell_size=7)
    color = cv2.applyColorMap(grayscale, cv2.COLORMAP_TURBO)
    encoded = encode_jpeg_opencv(color, quality=75, chroma_sampling="420")

    structure = parse_jpeg_structure(encoded)

    assert structure.width == color.shape[1]
    assert structure.height == color.shape[0]
    assert structure.precision_bits == 8
    assert structure.frame_marker == 0xC0
    assert structure.component_signature == "1:2x2:q0;2:1x1:q1;3:1x1:q1"
    assert len(structure.quantization_tables) == 2
    assert all(
        len(table.values_zigzag) == 64
        and len(table.values_natural) == 64
        and len(table.fingerprint) == 64
        for table in structure.quantization_tables
    )


def test_opencv_and_pillow_quality_paths_can_match_exactly() -> None:
    grayscale = make_checkerboard(cell_size=7)
    color = cv2.applyColorMap(grayscale, cv2.COLORMAP_TURBO)

    opencv_bytes = encode_jpeg_opencv(
        color, quality=75, chroma_sampling="444"
    )
    pillow_bytes = encode_jpeg_pillow(
        color, quality=75, chroma_sampling="444"
    )

    assert pillow_bytes == opencv_bytes
    assert np.array_equal(
        decode_jpeg_opencv(opencv_bytes), decode_jpeg_pillow(opencv_bytes)
    )


def test_explicit_quantization_tables_reproduce_quality_path() -> None:
    grayscale = make_checkerboard(cell_size=7)
    color = cv2.applyColorMap(grayscale, cv2.COLORMAP_TURBO)
    quality_bytes = encode_jpeg_opencv(
        color, quality=50, chroma_sampling="420"
    )
    tables = parse_jpeg_structure(quality_bytes).quantization_tables_natural()

    explicit_bytes = encode_jpeg_pillow(
        color,
        quality=None,
        chroma_sampling="420",
        quantization_tables=tables,
    )

    assert explicit_bytes == quality_bytes


def test_entropy_optimization_changes_bytes_not_decoded_pixels() -> None:
    grayscale = make_checkerboard(cell_size=7)
    color = cv2.applyColorMap(grayscale, cv2.COLORMAP_TURBO)
    default_bytes = encode_jpeg_pillow(
        color, quality=75, chroma_sampling="420"
    )
    optimized_bytes = encode_jpeg_pillow(
        color, quality=75, chroma_sampling="420", optimize=True
    )

    assert optimized_bytes != default_bytes
    assert (
        parse_jpeg_structure(optimized_bytes).quantization_fingerprint
        == parse_jpeg_structure(default_bytes).quantization_fingerprint
    )
    assert np.array_equal(
        decode_jpeg_opencv(optimized_bytes),
        decode_jpeg_opencv(default_bytes),
    )


def test_jpeg_codec_controls_and_marker_data_are_validated() -> None:
    grayscale = make_checkerboard()

    with pytest.raises(ValueError, match="exactly one"):
        encode_jpeg_pillow(
            grayscale,
            quality=75,
            quantization_tables={0: (1,) * 64},
        )
    with pytest.raises(ValueError, match="64 values"):
        encode_jpeg_pillow(
            grayscale,
            quality=None,
            quantization_tables={0: (1,) * 63},
        )
    with pytest.raises(ValueError, match="SOI"):
        parse_jpeg_structure(b"not a JPEG")
    with pytest.raises(ValueError, match="truncated DQT"):
        parse_jpeg_structure(
            b"\xff\xd8\xff\xdb\x00\x0d\x00" + b"\x01" * 10
        )


def test_advanced_jpeg_syntax_reports_progressive_and_restart_markers() -> None:
    grayscale = make_checkerboard(cell_size=7)
    color = cv2.applyColorMap(grayscale, cv2.COLORMAP_TURBO)
    progressive = encode_jpeg_opencv(
        color,
        quality=75,
        chroma_sampling="444",
        progressive=True,
    )
    restarted = encode_jpeg_opencv(
        color,
        quality=75,
        chroma_sampling="420",
        restart_interval=2,
    )

    progressive_syntax = inspect_jpeg_syntax(progressive)
    restarted_syntax = inspect_jpeg_syntax(restarted)

    assert progressive_syntax.frame_process == "progressive_dct"
    assert progressive_syntax.scan_count > 1
    assert restarted_syntax.frame_process == "baseline_sequential"
    assert restarted_syntax.restart_interval == 2
    assert restarted_syntax.restart_marker_count > 0


def test_cmyk_and_ffmpeg_decoder_preserve_the_array_interface() -> None:
    grayscale = make_checkerboard(cell_size=7)
    cmyk = np.stack(
        (
            grayscale,
            255 - grayscale,
            np.roll(grayscale, 3, axis=1),
            np.full_like(grayscale, 24),
        ),
        axis=2,
    )
    encoded = encode_jpeg_cmyk_pillow(cmyk, quality=75, progressive=True)

    syntax = inspect_jpeg_syntax(encoded)
    opencv = decode_jpeg_opencv(encoded)
    ffmpeg = decode_jpeg_ffmpeg(encoded)

    assert syntax.frame_process == "progressive_dct"
    assert len(parse_jpeg_structure(encoded).components) == 4
    assert opencv.shape == ffmpeg.shape == (*grayscale.shape, 3)
    assert opencv.dtype == ffmpeg.dtype == np.uint8


def test_decoded_pixel_contracts_separate_exact_and_bounded_results() -> None:
    reference = np.zeros((4, 4, 3), dtype=np.uint8)
    exact = compare_decoded_pixels(reference, reference.copy())
    one_step = reference.copy()
    one_step[1, 2, 0] = 1
    bounded = compare_decoded_pixels(reference, one_step)
    outside = reference.copy()
    outside[1, 2, 0] = 2
    outside_difference = compare_decoded_pixels(reference, outside)

    assert exact.exact
    assert classify_decoded_pixel_contract(exact) == "exact"
    assert bounded.maximum_absolute_error == 1
    assert bounded.changed_sample_fraction == pytest.approx(1 / 48)
    assert bounded.changed_pixel_fraction == pytest.approx(1 / 16)
    assert classify_decoded_pixel_contract(bounded) == "within_one"
    assert classify_decoded_pixel_contract(outside_difference) == (
        "outside_contract"
    )


def test_pixel_hash_includes_shape_and_validates_inputs() -> None:
    flat = np.arange(16, dtype=np.uint8).reshape(4, 4)
    reshaped = flat.reshape(2, 8)

    assert pixel_array_sha256(flat) != pixel_array_sha256(reshaped)
    with pytest.raises(ValueError, match="identical shapes"):
        compare_decoded_pixels(flat, reshaped)
    with pytest.raises(TypeError, match="uint8"):
        pixel_array_sha256(flat.astype(np.float32))


def test_recompression_and_color_conversion_order_can_change_scores() -> None:
    grayscale = make_checkerboard(cell_size=7)
    color = cv2.applyColorMap(grayscale, cv2.COLORMAP_TURBO)
    one_round = repeated_jpeg_round_trip(grayscale, quality=75, rounds=1)
    five_rounds = repeated_jpeg_round_trip(grayscale, quality=75, rounds=5)
    gray_then_jpeg = repeated_jpeg_round_trip(
        to_grayscale(color), quality=75, rounds=2
    )
    jpeg_then_gray = to_grayscale(
        repeated_jpeg_round_trip(color, quality=75, rounds=2)
    )

    assert laplacian_variance(one_round) != pytest.approx(
        laplacian_variance(five_rounds)
    )
    assert tenengrad_energy(gray_then_jpeg) != pytest.approx(
        tenengrad_energy(jpeg_then_gray)
    )


def test_photometric_parameters_are_validated() -> None:
    image = make_checkerboard()

    with pytest.raises(ValueError, match="positive and finite"):
        linear_intensity_transform(image, alpha=0.0, beta=0.0)
    with pytest.raises(ValueError, match="positive and finite"):
        gamma_transform(image, gamma=float("nan"))
    with pytest.raises(ValueError, match=r"\[1, 100\]"):
        repeated_jpeg_round_trip(image, quality=0, rounds=1)
    with pytest.raises(ValueError, match="not be negative"):
        repeated_jpeg_round_trip(image, quality=75, rounds=-1)
    with pytest.raises(ValueError, match="one of"):
        jpeg_encode_decode(image, quality=75, chroma_sampling="422")
    with pytest.raises(ValueError, match="only to BGR"):
        jpeg_encode_decode(image, quality=75, chroma_sampling="420")
