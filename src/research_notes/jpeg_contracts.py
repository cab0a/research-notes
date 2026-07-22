"""Decoded-pixel comparison utilities for controlled JPEG contracts."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray


PixelContractLevel = Literal["exact", "within_one", "outside_contract"]


@dataclass(frozen=True)
class PixelDifference:
    """Numerical differences between two equally shaped 8-bit images."""

    exact: bool
    mean_absolute_error: float
    maximum_absolute_error: int
    changed_sample_fraction: float
    changed_pixel_fraction: float
    reference_sha256: str
    candidate_sha256: str


def pixel_array_sha256(image: NDArray[np.generic]) -> str:
    """Return a stable hash of an 8-bit array's shape, dtype, and bytes."""
    validated = _validate_pixel_array(image, "image")
    digest = hashlib.sha256()
    digest.update(str(validated.shape).encode("ascii"))
    digest.update(validated.dtype.str.encode("ascii"))
    digest.update(validated.tobytes())
    return digest.hexdigest()


def compare_decoded_pixels(
    reference: NDArray[np.generic],
    candidate: NDArray[np.generic],
) -> PixelDifference:
    """Compare two decoded 8-bit images without a perceptual quality model."""
    reference_pixels = _validate_pixel_array(reference, "reference")
    candidate_pixels = _validate_pixel_array(candidate, "candidate")
    if reference_pixels.shape != candidate_pixels.shape:
        raise ValueError("reference and candidate must have identical shapes")

    difference = np.abs(
        reference_pixels.astype(np.int16)
        - candidate_pixels.astype(np.int16)
    )
    if difference.ndim == 3:
        changed_pixels = np.any(difference != 0, axis=2)
    else:
        changed_pixels = difference != 0
    return PixelDifference(
        exact=bool(np.array_equal(reference_pixels, candidate_pixels)),
        mean_absolute_error=float(np.mean(difference)),
        maximum_absolute_error=int(np.max(difference)),
        changed_sample_fraction=float(np.mean(difference != 0)),
        changed_pixel_fraction=float(np.mean(changed_pixels)),
        reference_sha256=pixel_array_sha256(reference_pixels),
        candidate_sha256=pixel_array_sha256(candidate_pixels),
    )


def classify_decoded_pixel_contract(
    difference: PixelDifference,
) -> PixelContractLevel:
    """Classify exact output or a declared one-code-value diagnostic bound."""
    if not isinstance(difference, PixelDifference):
        raise TypeError("difference must be a PixelDifference")
    if difference.exact:
        return "exact"
    if difference.maximum_absolute_error <= 1:
        return "within_one"
    return "outside_contract"


def _validate_pixel_array(
    image: NDArray[np.generic], name: str
) -> NDArray[np.uint8]:
    """Return a validated non-empty grayscale or three-channel array."""
    if not isinstance(image, np.ndarray):
        raise TypeError(f"{name} must be a NumPy array")
    if image.dtype != np.uint8:
        raise TypeError(f"{name} must have dtype uint8")
    if image.size == 0 or (
        image.ndim != 2 and not (image.ndim == 3 and image.shape[2] == 3)
    ):
        raise ValueError(
            f"{name} must be a non-empty grayscale or three-channel array"
        )
    return image
