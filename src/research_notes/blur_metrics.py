"""Blur-related image metrics used in controlled experiments."""

from __future__ import annotations

import cv2
import numpy as np
from numpy.typing import NDArray


def _to_grayscale(image: NDArray[np.generic]) -> NDArray[np.generic]:
    """Return a grayscale view or conversion of a non-empty image array."""
    if not isinstance(image, np.ndarray):
        raise TypeError("image must be a NumPy array")
    if image.size == 0:
        raise ValueError("image must not be empty")

    if image.ndim == 2:
        return image
    if image.ndim == 3 and image.shape[2] == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if image.ndim == 3 and image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
    raise ValueError("image must be grayscale, BGR, or BGRA")


def laplacian_variance(image: NDArray[np.generic]) -> float:
    """Return the variance of the 64-bit grayscale Laplacian response.

    The value is an image-dependent focus heuristic, not a calibrated or
    universal image-quality score. Comparisons are most meaningful when image
    content, scale, encoding, and preprocessing are controlled.
    """
    grayscale = _to_grayscale(image)
    laplacian = cv2.Laplacian(
        grayscale,
        cv2.CV_64F,
        ksize=1,
        borderType=cv2.BORDER_REFLECT_101,
    )
    return float(np.var(laplacian))
