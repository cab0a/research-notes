"""Deterministic preprocessing utilities used by controlled experiments."""

from __future__ import annotations

import cv2
import numpy as np
from numpy.typing import NDArray


def _validate_grayscale_uint8(
    image: NDArray[np.generic],
) -> NDArray[np.uint8]:
    """Return a validated 8-bit grayscale image."""
    if not isinstance(image, np.ndarray):
        raise TypeError("image must be a NumPy array")
    if image.ndim != 2 or image.size == 0:
        raise ValueError("image must be a non-empty grayscale array")
    if image.dtype != np.uint8:
        raise TypeError("image must have dtype uint8")
    return image


def jpeg_round_trip(
    image: NDArray[np.generic], quality: int
) -> NDArray[np.uint8]:
    """Encode and decode an 8-bit grayscale image at a JPEG quality setting."""
    grayscale = _validate_grayscale_uint8(image)
    if not isinstance(quality, int) or isinstance(quality, bool):
        raise TypeError("quality must be an integer")
    if not 1 <= quality <= 100:
        raise ValueError("quality must be in the interval [1, 100]")

    succeeded, encoded = cv2.imencode(
        ".jpg",
        grayscale,
        [cv2.IMWRITE_JPEG_QUALITY, quality],
    )
    if not succeeded:
        raise RuntimeError("JPEG encoding failed")
    decoded = cv2.imdecode(encoded, cv2.IMREAD_GRAYSCALE)
    if decoded is None or decoded.shape != grayscale.shape:
        raise RuntimeError("JPEG decoding failed or changed image dimensions")
    return decoded


def resize_round_trip(
    image: NDArray[np.generic],
    scale: float,
    down_interpolation: int = cv2.INTER_AREA,
    up_interpolation: int = cv2.INTER_LINEAR,
) -> NDArray[np.uint8]:
    """Resize down and back to the original shape with declared interpolators."""
    grayscale = _validate_grayscale_uint8(image)
    if isinstance(scale, bool) or not isinstance(scale, (int, float)):
        raise TypeError("scale must be numeric")
    if not 0.0 < float(scale) <= 1.0:
        raise ValueError("scale must be in the interval (0, 1]")

    height, width = grayscale.shape
    reduced_size = (
        max(1, round(width * float(scale))),
        max(1, round(height * float(scale))),
    )
    reduced = cv2.resize(
        grayscale,
        reduced_size,
        interpolation=down_interpolation,
    )
    return cv2.resize(
        reduced,
        (width, height),
        interpolation=up_interpolation,
    )


def gaussian_denoise(
    image: NDArray[np.generic], sigma: float
) -> NDArray[np.uint8]:
    """Apply a Gaussian low-pass filter as a bounded denoising control."""
    grayscale = _validate_grayscale_uint8(image)
    if isinstance(sigma, bool) or not isinstance(sigma, (int, float)):
        raise TypeError("sigma must be numeric")
    if float(sigma) <= 0.0:
        raise ValueError("sigma must be positive")
    return cv2.GaussianBlur(
        grayscale,
        (0, 0),
        sigmaX=float(sigma),
        sigmaY=float(sigma),
        borderType=cv2.BORDER_REFLECT_101,
    )


def unsharp_mask(
    image: NDArray[np.generic], amount: float, sigma: float
) -> NDArray[np.uint8]:
    """Apply clipped unsharp masking using a Gaussian low-pass reference."""
    grayscale = _validate_grayscale_uint8(image)
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise TypeError("amount must be numeric")
    if float(amount) < 0.0:
        raise ValueError("amount must not be negative")
    smoothed = gaussian_denoise(grayscale, sigma)
    source = grayscale.astype(np.float64)
    detail = source - smoothed.astype(np.float64)
    sharpened = source + float(amount) * detail
    return np.clip(np.rint(sharpened), 0, 255).astype(np.uint8)
