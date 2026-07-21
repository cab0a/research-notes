"""Tests for the Laplacian-variance implementation and its relative behavior."""

import cv2
import numpy as np
import pytest

from research_notes import laplacian_variance


def make_checkerboard(size: int = 128, cell_size: int = 8) -> np.ndarray:
    """Return a test checkerboard with controlled spatial frequency."""
    rows, columns = np.indices((size, size))
    return (((rows // cell_size + columns // cell_size) % 2) * 255).astype(
        np.uint8
    )


def test_constant_image_has_zero_laplacian_variance() -> None:
    image = np.full((64, 64), 127, dtype=np.uint8)

    assert laplacian_variance(image) == pytest.approx(0.0)


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


def test_noise_can_raise_score_for_a_blurred_image() -> None:
    sharp = make_checkerboard()
    blurred = cv2.GaussianBlur(sharp, (0, 0), sigmaX=3.0, sigmaY=3.0)
    generator = np.random.default_rng(20260721)
    noise = generator.normal(0.0, 15.0, blurred.shape)
    noisy_blurred = np.clip(blurred.astype(np.float64) + noise, 0, 255).astype(
        np.uint8
    )

    assert laplacian_variance(noisy_blurred) > laplacian_variance(blurred)


def test_bgr_and_grayscale_inputs_agree() -> None:
    grayscale = make_checkerboard()
    bgr = cv2.cvtColor(grayscale, cv2.COLOR_GRAY2BGR)

    assert laplacian_variance(bgr) == pytest.approx(laplacian_variance(grayscale))


def test_invalid_shape_is_rejected() -> None:
    with pytest.raises(ValueError, match="grayscale, BGR, or BGRA"):
        laplacian_variance(np.zeros((8, 8, 2), dtype=np.uint8))
