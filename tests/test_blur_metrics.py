"""Tests for focus metrics, preprocessing, and controlled blur models."""

import cv2
import numpy as np
import pytest

from research_notes import (
    apply_psf,
    disk_psf,
    gaussian_denoise,
    jpeg_round_trip,
    laplacian_variance,
    linear_motion_psf,
    resize_round_trip,
    sliding_metric_map,
    tenengrad_energy,
    tiled_metric_map,
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
