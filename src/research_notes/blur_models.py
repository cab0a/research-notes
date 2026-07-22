"""Deterministic point-spread-function models for controlled blur studies."""

from __future__ import annotations

import math

import cv2
import numpy as np
from numpy.typing import NDArray


def _validate_grayscale_uint8(
    image: NDArray[np.generic],
) -> NDArray[np.uint8]:
    """Return a validated non-empty 8-bit grayscale image."""
    if not isinstance(image, np.ndarray):
        raise TypeError("image must be a NumPy array")
    if image.ndim != 2 or image.size == 0:
        raise ValueError("image must be a non-empty grayscale array")
    if image.dtype != np.uint8:
        raise TypeError("image must have dtype uint8")
    return image


def disk_psf(radius: int) -> NDArray[np.float64]:
    """Return a normalized discrete disk PSF for a non-negative radius."""
    if not isinstance(radius, int) or isinstance(radius, bool):
        raise TypeError("radius must be an integer")
    if radius < 0:
        raise ValueError("radius must not be negative")
    if radius == 0:
        return np.ones((1, 1), dtype=np.float64)

    coordinates = np.arange(-radius, radius + 1)
    rows, columns = np.meshgrid(coordinates, coordinates, indexing="ij")
    support = rows * rows + columns * columns <= radius * radius
    kernel = support.astype(np.float64)
    return kernel / np.sum(kernel)


def linear_motion_psf(
    length: int,
    angle_degrees: float,
    samples_per_pixel: int = 32,
) -> NDArray[np.float64]:
    """Return a normalized, bilinearly rasterized linear-motion PSF.

    Angles follow image coordinates: zero degrees is horizontal and positive
    angles rotate toward increasing row coordinates. The path is sampled more
    finely than the pixel grid, then distributed with bilinear weights.
    """
    if not isinstance(length, int) or isinstance(length, bool):
        raise TypeError("length must be an integer")
    if length < 1 or length % 2 == 0:
        raise ValueError("length must be a positive odd integer")
    if isinstance(angle_degrees, bool) or not isinstance(
        angle_degrees, (int, float)
    ):
        raise TypeError("angle_degrees must be numeric")
    if not math.isfinite(float(angle_degrees)):
        raise ValueError("angle_degrees must be finite")
    if not isinstance(samples_per_pixel, int) or isinstance(
        samples_per_pixel, bool
    ):
        raise TypeError("samples_per_pixel must be an integer")
    if samples_per_pixel < 1:
        raise ValueError("samples_per_pixel must be positive")
    if length == 1:
        return np.ones((1, 1), dtype=np.float64)

    center = (length - 1) / 2.0
    angle_radians = math.radians(float(angle_degrees) % 180.0)
    sample_count = (length - 1) * samples_per_pixel + 1
    offsets = np.linspace(-center, center, sample_count)
    x_coordinates = center + offsets * math.cos(angle_radians)
    y_coordinates = center + offsets * math.sin(angle_radians)

    x_lower = np.floor(x_coordinates).astype(np.int64)
    y_lower = np.floor(y_coordinates).astype(np.int64)
    x_fraction = x_coordinates - x_lower
    y_fraction = y_coordinates - y_lower
    kernel = np.zeros((length, length), dtype=np.float64)
    for x_shift, y_shift, weights in (
        (0, 0, (1.0 - x_fraction) * (1.0 - y_fraction)),
        (1, 0, x_fraction * (1.0 - y_fraction)),
        (0, 1, (1.0 - x_fraction) * y_fraction),
        (1, 1, x_fraction * y_fraction),
    ):
        x_indices = x_lower + x_shift
        y_indices = y_lower + y_shift
        valid = (
            (x_indices >= 0)
            & (x_indices < length)
            & (y_indices >= 0)
            & (y_indices < length)
        )
        np.add.at(
            kernel,
            (y_indices[valid], x_indices[valid]),
            weights[valid],
        )
    return kernel / np.sum(kernel)


def apply_psf(
    image: NDArray[np.generic],
    kernel: NDArray[np.generic],
) -> NDArray[np.uint8]:
    """Convolve an 8-bit grayscale image with a normalized odd-sized PSF."""
    grayscale = _validate_grayscale_uint8(image)
    if not isinstance(kernel, np.ndarray):
        raise TypeError("kernel must be a NumPy array")
    if kernel.ndim != 2 or kernel.size == 0:
        raise ValueError("kernel must be a non-empty two-dimensional array")
    if kernel.shape[0] % 2 == 0 or kernel.shape[1] % 2 == 0:
        raise ValueError("kernel dimensions must be odd")
    numeric_kernel = kernel.astype(np.float64)
    if not np.all(np.isfinite(numeric_kernel)):
        raise ValueError("kernel values must be finite")
    if np.any(numeric_kernel < 0.0):
        raise ValueError("kernel values must not be negative")
    if not np.isclose(float(np.sum(numeric_kernel)), 1.0, atol=1e-12):
        raise ValueError("kernel weights must sum to one")

    filtered = cv2.filter2D(
        grayscale,
        ddepth=cv2.CV_64F,
        kernel=numeric_kernel,
        borderType=cv2.BORDER_REFLECT_101,
    )
    return np.clip(np.rint(filtered), 0, 255).astype(np.uint8)
