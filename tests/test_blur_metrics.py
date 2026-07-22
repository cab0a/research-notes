"""Tests for the Laplacian-variance implementation and its relative behavior."""

import cv2
import numpy as np
import pytest

from research_notes import laplacian_variance, tenengrad_energy, tiled_metric_map


def make_checkerboard(size: int = 128, cell_size: int = 8) -> np.ndarray:
    """Return a test checkerboard with controlled spatial frequency."""
    rows, columns = np.indices((size, size))
    return (((rows // cell_size + columns // cell_size) % 2) * 255).astype(
        np.uint8
    )


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
