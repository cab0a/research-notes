"""Blur-related image metrics used in controlled experiments."""

from __future__ import annotations

from collections.abc import Callable

import cv2
import numpy as np
from numpy.typing import NDArray


MetricFunction = Callable[[NDArray[np.generic]], float]


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


def tenengrad_energy(image: NDArray[np.generic]) -> float:
    """Return the area-normalized squared Sobel gradient response.

    This implementation uses 3 x 3 Sobel derivatives and averages ``Gx² +
    Gy²`` over all pixels. Dividing the conventional Tenengrad sum by the image
    area avoids a purely pixel-count-driven scale change, but it does not make
    scores comparable across different content or preprocessing pipelines.
    """
    grayscale = _to_grayscale(image)
    gradient_x = cv2.Sobel(
        grayscale,
        cv2.CV_64F,
        1,
        0,
        ksize=3,
        borderType=cv2.BORDER_REFLECT_101,
    )
    gradient_y = cv2.Sobel(
        grayscale,
        cv2.CV_64F,
        0,
        1,
        ksize=3,
        borderType=cv2.BORDER_REFLECT_101,
    )
    return float(np.mean(gradient_x * gradient_x + gradient_y * gradient_y))


def tiled_metric_map(
    image: NDArray[np.generic],
    metric: MetricFunction,
    tile_size: int,
) -> NDArray[np.float64]:
    """Evaluate an image metric independently on a non-overlapping tile grid.

    Tile evaluation intentionally gives every tile its own reflected border.
    This prevents derivative responses from crossing tile boundaries, but it
    also means that the result is not identical to aggregating a full-image
    response map. Image dimensions must be divisible by ``tile_size``.
    """
    grayscale = _to_grayscale(image)
    if not callable(metric):
        raise TypeError("metric must be callable")
    if not isinstance(tile_size, int) or isinstance(tile_size, bool):
        raise TypeError("tile_size must be an integer")
    if tile_size <= 0:
        raise ValueError("tile_size must be positive")

    height, width = grayscale.shape
    if height % tile_size != 0 or width % tile_size != 0:
        raise ValueError("image dimensions must be divisible by tile_size")

    scores = np.empty(
        (height // tile_size, width // tile_size), dtype=np.float64
    )
    for tile_row in range(scores.shape[0]):
        row_start = tile_row * tile_size
        for tile_column in range(scores.shape[1]):
            column_start = tile_column * tile_size
            tile = grayscale[
                row_start : row_start + tile_size,
                column_start : column_start + tile_size,
            ]
            scores[tile_row, tile_column] = metric(tile)
    return scores
