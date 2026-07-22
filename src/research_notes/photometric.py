"""Deterministic photometric and recompression controls."""

from __future__ import annotations

import cv2
import numpy as np
from numpy.typing import NDArray


JPEG_SAMPLING_FACTORS = {
    "444": cv2.IMWRITE_JPEG_SAMPLING_FACTOR_444,
    "420": cv2.IMWRITE_JPEG_SAMPLING_FACTOR_420,
}


def _validate_uint8_image(
    image: NDArray[np.generic],
) -> NDArray[np.uint8]:
    """Return a validated grayscale or BGR 8-bit image."""
    if not isinstance(image, np.ndarray):
        raise TypeError("image must be a NumPy array")
    if image.size == 0 or (
        image.ndim != 2 and not (image.ndim == 3 and image.shape[2] == 3)
    ):
        raise ValueError("image must be a non-empty grayscale or BGR array")
    if image.dtype != np.uint8:
        raise TypeError("image must have dtype uint8")
    return image


def to_grayscale(image: NDArray[np.generic]) -> NDArray[np.uint8]:
    """Convert BGR to grayscale, or copy an existing grayscale image."""
    validated = _validate_uint8_image(image)
    if validated.ndim == 2:
        return validated.copy()
    return cv2.cvtColor(validated, cv2.COLOR_BGR2GRAY)


def linear_intensity_transform(
    image: NDArray[np.generic], alpha: float, beta: float
) -> NDArray[np.uint8]:
    """Apply a clipped linear intensity transform ``alpha * image + beta``."""
    validated = _validate_uint8_image(image)
    if isinstance(alpha, bool) or not isinstance(alpha, (int, float)):
        raise TypeError("alpha must be numeric")
    if isinstance(beta, bool) or not isinstance(beta, (int, float)):
        raise TypeError("beta must be numeric")
    if not np.isfinite(float(alpha)) or float(alpha) <= 0.0:
        raise ValueError("alpha must be positive and finite")
    if not np.isfinite(float(beta)):
        raise ValueError("beta must be finite")
    transformed = float(alpha) * validated.astype(np.float64) + float(beta)
    return np.clip(np.rint(transformed), 0, 255).astype(np.uint8)


def gamma_transform(
    image: NDArray[np.generic], gamma: float
) -> NDArray[np.uint8]:
    """Apply the power-law mapping ``255 * (image / 255) ** gamma``."""
    validated = _validate_uint8_image(image)
    if isinstance(gamma, bool) or not isinstance(gamma, (int, float)):
        raise TypeError("gamma must be numeric")
    if not np.isfinite(float(gamma)) or float(gamma) <= 0.0:
        raise ValueError("gamma must be positive and finite")
    normalized = validated.astype(np.float64) / 255.0
    transformed = 255.0 * np.power(normalized, float(gamma))
    return np.clip(np.rint(transformed), 0, 255).astype(np.uint8)


def minmax_normalize(
    image: NDArray[np.generic],
) -> NDArray[np.uint8]:
    """Map the observed global intensity range to the full 8-bit interval."""
    validated = _validate_uint8_image(image)
    minimum = int(np.min(validated))
    maximum = int(np.max(validated))
    if minimum == maximum:
        return np.zeros_like(validated)
    normalized = (
        (validated.astype(np.float64) - minimum)
        * 255.0
        / (maximum - minimum)
    )
    return np.clip(np.rint(normalized), 0, 255).astype(np.uint8)


def repeated_jpeg_round_trip(
    image: NDArray[np.generic], quality: int, rounds: int
) -> NDArray[np.uint8]:
    """Apply a fixed-quality JPEG encode/decode cycle repeatedly."""
    current = _validate_uint8_image(image).copy()
    if not isinstance(quality, int) or isinstance(quality, bool):
        raise TypeError("quality must be an integer")
    if not 1 <= quality <= 100:
        raise ValueError("quality must be in the interval [1, 100]")
    if not isinstance(rounds, int) or isinstance(rounds, bool):
        raise TypeError("rounds must be an integer")
    if rounds < 0:
        raise ValueError("rounds must not be negative")

    for _ in range(rounds):
        current = jpeg_encode_decode(current, quality=quality)
    return current


def jpeg_encode_decode(
    image: NDArray[np.generic],
    quality: int,
    chroma_sampling: str | None = None,
) -> NDArray[np.uint8]:
    """Apply one JPEG round trip with an optional BGR chroma-sampling mode."""
    validated = _validate_uint8_image(image)
    if not isinstance(quality, int) or isinstance(quality, bool):
        raise TypeError("quality must be an integer")
    if not 1 <= quality <= 100:
        raise ValueError("quality must be in the interval [1, 100]")
    if chroma_sampling is not None and chroma_sampling not in JPEG_SAMPLING_FACTORS:
        supported = ", ".join(sorted(JPEG_SAMPLING_FACTORS))
        raise ValueError(f"chroma_sampling must be one of: {supported}")
    if validated.ndim == 2 and chroma_sampling is not None:
        raise ValueError("chroma_sampling applies only to BGR images")

    parameters = [cv2.IMWRITE_JPEG_QUALITY, quality]
    if chroma_sampling is not None:
        parameters.extend(
            [
                cv2.IMWRITE_JPEG_SAMPLING_FACTOR,
                JPEG_SAMPLING_FACTORS[chroma_sampling],
            ]
        )
    succeeded, encoded = cv2.imencode(".jpg", validated, parameters)
    if not succeeded:
        raise RuntimeError("JPEG encoding failed")
    decode_flag = (
        cv2.IMREAD_GRAYSCALE if validated.ndim == 2 else cv2.IMREAD_COLOR
    )
    decoded = cv2.imdecode(encoded, decode_flag)
    if decoded is None or decoded.shape != validated.shape:
        raise RuntimeError("JPEG decoding failed or changed image dimensions")
    return decoded
