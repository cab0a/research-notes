"""Deterministic JPEG metadata controls and interpretation policies."""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass

import cv2
import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageCms, ImageOps

from research_notes.jpeg_codec import (
    encode_jpeg_cmyk_pillow,
    inspect_jpeg_syntax,
)


_EXIF_ORIENTATION_TAG = 274
_ICC_IDENTIFIER = b"ICC_PROFILE\x00"
_PROFILE_DATE = (2026, 7, 23, 0, 0, 0)
_SUPPORTED_PROFILE_GAMMAS = (1.0, 2.2)


@dataclass(frozen=True)
class JPEGMetadataSummary:
    """Metadata that can change interpretation without changing JPEG scans."""

    exif_orientation: int | None
    icc_profile_length: int
    icc_profile_sha256: str
    icc_chunk_count: int
    adobe_transform: int | None

    @property
    def icc_profile_present(self) -> bool:
        """Return whether a complete embedded ICC profile was observed."""
        return self.icc_profile_length > 0


def build_synthetic_rgb_profile(gamma: float) -> bytes:
    """Build one fixed matrix/TRC RGB profile for a controlled ICC test."""
    if not isinstance(gamma, (int, float)) or isinstance(gamma, bool):
        raise TypeError("gamma must be a real number")
    normalized_gamma = float(gamma)
    if normalized_gamma not in _SUPPORTED_PROFILE_GAMMAS:
        raise ValueError("gamma must be one of: 1.0, 2.2")

    profile = bytearray(
        ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    )
    profile[24:36] = b"".join(
        value.to_bytes(2, "big") for value in _PROFILE_DATE
    )
    profile[84:100] = b"\x00" * 16
    tags = _icc_tag_table(profile)

    description = f"gamma {normalized_gamma:.1f} RGB".encode("utf-16-be")
    description_offset, description_size = tags["desc"]
    if description_size != 54 or len(description) != 26:
        raise RuntimeError("unexpected generated ICC description layout")
    profile[
        description_offset + 28 : description_offset + description_size
    ] = description

    trc_offset, trc_size = tags["rTRC"]
    if trc_size != 32 or not all(
        tags[name] == (trc_offset, trc_size)
        for name in ("rTRC", "gTRC", "bTRC")
    ):
        raise RuntimeError("unexpected generated ICC TRC layout")
    profile[trc_offset : trc_offset + trc_size] = (
        b"para"
        + b"\x00" * 4
        + (3).to_bytes(2, "big")
        + b"\x00" * 2
        + b"".join(
            _s15_fixed16(value)
            for value in (normalized_gamma, 1.0, 0.0, 1.0, 0.0)
        )
    )
    result = bytes(profile)
    ImageCms.getOpenProfile(io.BytesIO(result))
    return result


def attach_jpeg_metadata(
    jpeg_bytes: bytes,
    *,
    exif_orientation: int | None = None,
    icc_profile: bytes | None = None,
) -> bytes:
    """Replace EXIF orientation and ICC APP segments without re-encoding."""
    neutral = strip_jpeg_interpretation_metadata(jpeg_bytes)
    segments = bytearray()
    if exif_orientation is not None:
        segments.extend(
            _make_app_segment(0xE1, _build_exif_payload(exif_orientation))
        )
    if icc_profile is not None:
        if not isinstance(icc_profile, bytes) or not icc_profile:
            raise TypeError("icc_profile must be non-empty bytes")
        segments.extend(_build_icc_segments(icc_profile))
    return neutral[:2] + bytes(segments) + neutral[2:]


def strip_jpeg_interpretation_metadata(jpeg_bytes: bytes) -> bytes:
    """Remove EXIF APP1 and ICC APP2 segments while preserving JPEG scans."""
    _validate_jpeg_bytes(jpeg_bytes)
    output = bytearray(jpeg_bytes[:2])
    position = 2
    while position < len(jpeg_bytes):
        marker_start = position
        if jpeg_bytes[position] != 0xFF:
            raise ValueError("expected a JPEG marker prefix")
        while position < len(jpeg_bytes) and jpeg_bytes[position] == 0xFF:
            position += 1
        if position >= len(jpeg_bytes):
            raise ValueError("truncated JPEG marker")
        marker = jpeg_bytes[position]
        position += 1
        if marker in (0xD9, 0xDA):
            output.extend(jpeg_bytes[marker_start:])
            break
        if marker == 0x01 or 0xD0 <= marker <= 0xD8:
            output.extend(jpeg_bytes[marker_start:position])
            continue
        payload_start, payload_end = _segment_payload_bounds(
            jpeg_bytes, position
        )
        payload = jpeg_bytes[payload_start:payload_end]
        is_exif = marker == 0xE1 and payload.startswith(b"Exif\x00\x00")
        is_icc = marker == 0xE2 and payload.startswith(_ICC_IDENTIFIER)
        if not is_exif and not is_icc:
            output.extend(jpeg_bytes[marker_start:payload_end])
        position = payload_end
    if not output.endswith(b"\xff\xd9"):
        raise ValueError("JPEG EOI marker was not found")
    return bytes(output)


def inspect_jpeg_metadata(jpeg_bytes: bytes) -> JPEGMetadataSummary:
    """Inspect EXIF orientation, ICC chunks, and Adobe color transform."""
    _validate_jpeg_bytes(jpeg_bytes)
    chunks: dict[int, bytes] = {}
    declared_chunk_count: int | None = None
    position = 2
    while position < len(jpeg_bytes):
        if jpeg_bytes[position] != 0xFF:
            raise ValueError("expected a JPEG marker prefix")
        while position < len(jpeg_bytes) and jpeg_bytes[position] == 0xFF:
            position += 1
        if position >= len(jpeg_bytes):
            raise ValueError("truncated JPEG marker")
        marker = jpeg_bytes[position]
        position += 1
        if marker in (0xD9, 0xDA):
            break
        if marker == 0x01 or 0xD0 <= marker <= 0xD8:
            continue
        payload_start, payload_end = _segment_payload_bounds(
            jpeg_bytes, position
        )
        payload = jpeg_bytes[payload_start:payload_end]
        position = payload_end
        if marker != 0xE2 or not payload.startswith(_ICC_IDENTIFIER):
            continue
        if len(payload) < 14:
            raise ValueError("truncated ICC APP2 segment")
        sequence_number = payload[12]
        chunk_count = payload[13]
        if sequence_number == 0 or chunk_count == 0:
            raise ValueError("invalid ICC APP2 sequence metadata")
        if declared_chunk_count not in (None, chunk_count):
            raise ValueError("inconsistent ICC APP2 chunk counts")
        if sequence_number in chunks:
            raise ValueError("duplicate ICC APP2 sequence number")
        declared_chunk_count = chunk_count
        chunks[sequence_number] = payload[14:]

    if declared_chunk_count is None:
        profile = b""
    else:
        expected = set(range(1, declared_chunk_count + 1))
        if set(chunks) != expected:
            raise ValueError("incomplete ICC APP2 chunk sequence")
        profile = b"".join(chunks[index] for index in sorted(chunks))

    try:
        with Image.open(io.BytesIO(jpeg_bytes)) as image:
            orientation_value = image.getexif().get(_EXIF_ORIENTATION_TAG)
    except (OSError, SyntaxError) as error:
        raise ValueError("Pillow could not inspect JPEG metadata") from error
    orientation = int(orientation_value) if orientation_value is not None else None
    if orientation is not None and not 1 <= orientation <= 8:
        raise ValueError("EXIF orientation must be in the interval [1, 8]")
    return JPEGMetadataSummary(
        exif_orientation=orientation,
        icc_profile_length=len(profile),
        icc_profile_sha256=(hashlib.sha256(profile).hexdigest() if profile else ""),
        icc_chunk_count=len(chunks),
        adobe_transform=inspect_jpeg_syntax(jpeg_bytes).adobe_transform,
    )


def decode_jpeg_pillow_oriented(jpeg_bytes: bytes) -> NDArray[np.uint8]:
    """Decode to BGR after applying the declared EXIF orientation."""
    _validate_jpeg_bytes(jpeg_bytes)
    try:
        with Image.open(io.BytesIO(jpeg_bytes)) as image:
            oriented = ImageOps.exif_transpose(image)
            rgb = np.asarray(oriented.convert("RGB"), dtype=np.uint8)
    except (OSError, SyntaxError) as error:
        raise ValueError("Pillow could not decode the JPEG data") from error
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def decode_jpeg_pillow_color_managed(
    jpeg_bytes: bytes,
) -> NDArray[np.uint8]:
    """Decode to BGR and map an embedded RGB ICC profile to sRGB."""
    _validate_jpeg_bytes(jpeg_bytes)
    try:
        with Image.open(io.BytesIO(jpeg_bytes)) as image:
            profile = image.info.get("icc_profile")
            rgb_image = image.convert("RGB")
            if profile:
                rgb_image = ImageCms.profileToProfile(
                    rgb_image,
                    io.BytesIO(profile),
                    ImageCms.createProfile("sRGB"),
                    renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC,
                    outputMode="RGB",
                )
            rgb = np.asarray(rgb_image, dtype=np.uint8)
    except (OSError, SyntaxError, ImageCms.PyCMSError) as error:
        raise ValueError("Pillow could not apply the JPEG ICC profile") from error
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def apply_exif_orientation_bgr(
    image: NDArray[np.generic], orientation: int
) -> NDArray[np.uint8]:
    """Apply one EXIF orientation value to a BGR array."""
    validated = _validate_bgr(image)
    if not isinstance(orientation, int) or isinstance(orientation, bool):
        raise TypeError("orientation must be an integer")
    if not 1 <= orientation <= 8:
        raise ValueError("orientation must be in the interval [1, 8]")
    operations = {
        1: lambda value: value,
        2: lambda value: np.flip(value, axis=1),
        3: lambda value: np.rot90(value, 2),
        4: lambda value: np.flip(value, axis=0),
        5: lambda value: np.transpose(value, (1, 0, 2)),
        6: lambda value: np.rot90(value, 3),
        7: lambda value: np.flip(
            np.transpose(value, (1, 0, 2)), axis=(0, 1)
        ),
        8: lambda value: np.rot90(value, 1),
    }
    return np.ascontiguousarray(operations[orientation](validated))


def encode_jpeg_ycck_pillow(
    cmyk: NDArray[np.generic], quality: int
) -> bytes:
    """Encode a synthetic CMYK array as Adobe YCCK through Pillow."""
    validated = _validate_cmyk(cmyk)
    inverted_cmy = 255.0 - validated[:, :, :3].astype(np.float64)
    red, green, blue = np.moveaxis(inverted_cmy, 2, 0)
    luminance = 0.29900 * red + 0.58700 * green + 0.11400 * blue
    blue_difference = (
        -0.16874 * red - 0.33126 * green + 0.50000 * blue + 128.0
    )
    red_difference = (
        0.50000 * red - 0.41869 * green - 0.08131 * blue + 128.0
    )
    ycck = np.stack(
        (
            np.clip(np.rint(luminance), 0, 255),
            np.clip(np.rint(blue_difference), 0, 255),
            np.clip(np.rint(red_difference), 0, 255),
            validated[:, :, 3],
        ),
        axis=2,
    ).astype(np.uint8)
    encoded = encode_jpeg_cmyk_pillow(ycck, quality=quality)
    return _replace_adobe_transform(encoded, transform=2)


def cmyk_to_bgr_arithmetic(
    cmyk: NDArray[np.generic],
) -> NDArray[np.uint8]:
    """Apply a declared profile-free arithmetic CMYK preview policy."""
    validated = _validate_cmyk(cmyk).astype(np.uint16)
    rgb = (
        (255 - validated[:, :, :3])
        * (255 - validated[:, :, 3:4])
        + 127
    ) // 255
    return np.ascontiguousarray(rgb.astype(np.uint8)[:, :, ::-1])


def _icc_tag_table(profile: bytes | bytearray) -> dict[str, tuple[int, int]]:
    """Return the ICC tag table from a generated profile."""
    if len(profile) < 132 or profile[36:40] != b"acsp":
        raise ValueError("data is not an ICC profile")
    count = int.from_bytes(profile[128:132], "big")
    if len(profile) < 132 + 12 * count:
        raise ValueError("truncated ICC tag table")
    tags: dict[str, tuple[int, int]] = {}
    for index in range(count):
        offset = 132 + 12 * index
        signature = bytes(profile[offset : offset + 4]).decode("ascii")
        data_offset = int.from_bytes(profile[offset + 4 : offset + 8], "big")
        data_size = int.from_bytes(profile[offset + 8 : offset + 12], "big")
        if data_offset + data_size > len(profile):
            raise ValueError("ICC tag data exceeds the profile length")
        tags[signature] = (data_offset, data_size)
    return tags


def _s15_fixed16(value: float) -> bytes:
    """Encode one signed 15.16 fixed-point ICC value."""
    return int(round(value * 65536)).to_bytes(4, "big", signed=True)


def _build_exif_payload(orientation: int) -> bytes:
    """Build a minimal big-endian TIFF IFD containing Orientation."""
    if not isinstance(orientation, int) or isinstance(orientation, bool):
        raise TypeError("exif_orientation must be an integer")
    if not 1 <= orientation <= 8:
        raise ValueError("exif_orientation must be in the interval [1, 8]")
    tiff = (
        b"MM"
        + b"\x00*"
        + (8).to_bytes(4, "big")
        + (1).to_bytes(2, "big")
        + _EXIF_ORIENTATION_TAG.to_bytes(2, "big")
        + (3).to_bytes(2, "big")
        + (1).to_bytes(4, "big")
        + orientation.to_bytes(2, "big")
        + b"\x00\x00"
        + b"\x00\x00\x00\x00"
    )
    return b"Exif\x00\x00" + tiff


def _build_icc_segments(profile: bytes) -> bytes:
    """Split one ICC profile over deterministic APP2 chunks."""
    maximum_chunk_size = 65533 - 14
    chunks = [
        profile[start : start + maximum_chunk_size]
        for start in range(0, len(profile), maximum_chunk_size)
    ]
    if len(chunks) > 255:
        raise ValueError("ICC profile requires more than 255 APP2 chunks")
    return b"".join(
        _make_app_segment(
            0xE2,
            _ICC_IDENTIFIER
            + bytes((index, len(chunks)))
            + chunk,
        )
        for index, chunk in enumerate(chunks, start=1)
    )


def _make_app_segment(marker: int, payload: bytes) -> bytes:
    """Build one length-delimited JPEG APP segment."""
    segment_length = len(payload) + 2
    if segment_length > 65535:
        raise ValueError("JPEG APP segment exceeds the 16-bit length field")
    return b"\xff" + bytes((marker,)) + segment_length.to_bytes(2, "big") + payload


def _replace_adobe_transform(jpeg_bytes: bytes, transform: int) -> bytes:
    """Replace the transform byte in one Adobe APP14 segment."""
    if transform not in (0, 1, 2):
        raise ValueError("Adobe transform must be 0, 1, or 2")
    data = bytearray(jpeg_bytes)
    position = 2
    matches = 0
    while position < len(data):
        if data[position] != 0xFF:
            raise ValueError("expected a JPEG marker prefix")
        while position < len(data) and data[position] == 0xFF:
            position += 1
        marker = data[position]
        position += 1
        if marker in (0xD9, 0xDA):
            break
        if marker == 0x01 or 0xD0 <= marker <= 0xD8:
            continue
        payload_start, payload_end = _segment_payload_bounds(data, position)
        payload = data[payload_start:payload_end]
        if marker == 0xEE and payload.startswith(b"Adobe"):
            if len(payload) < 12:
                raise ValueError("truncated Adobe APP14 segment")
            data[payload_start + 11] = transform
            matches += 1
        position = payload_end
    if matches != 1:
        raise ValueError("expected exactly one Adobe APP14 segment")
    return bytes(data)


def _segment_payload_bounds(
    jpeg_bytes: bytes | bytearray, length_offset: int
) -> tuple[int, int]:
    """Return validated payload bounds for one JPEG segment."""
    if length_offset + 2 > len(jpeg_bytes):
        raise ValueError("truncated JPEG segment length")
    segment_length = int.from_bytes(
        jpeg_bytes[length_offset : length_offset + 2], "big"
    )
    if segment_length < 2:
        raise ValueError("invalid JPEG segment length")
    payload_start = length_offset + 2
    payload_end = length_offset + segment_length
    if payload_end > len(jpeg_bytes):
        raise ValueError("truncated JPEG segment")
    return payload_start, payload_end


def _validate_jpeg_bytes(jpeg_bytes: bytes) -> None:
    """Validate a complete JPEG byte input at the public boundary."""
    if not isinstance(jpeg_bytes, bytes) or not jpeg_bytes:
        raise TypeError("jpeg_bytes must be non-empty bytes")
    if len(jpeg_bytes) < 4 or jpeg_bytes[:2] != b"\xff\xd8":
        raise ValueError("data does not begin with a JPEG SOI marker")


def _validate_bgr(image: NDArray[np.generic]) -> NDArray[np.uint8]:
    """Return a validated BGR image."""
    if not isinstance(image, np.ndarray):
        raise TypeError("image must be a NumPy array")
    if image.size == 0 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("image must be a non-empty BGR array")
    if image.dtype != np.uint8:
        raise TypeError("image must have dtype uint8")
    return image


def _validate_cmyk(image: NDArray[np.generic]) -> NDArray[np.uint8]:
    """Return a validated CMYK image."""
    if not isinstance(image, np.ndarray):
        raise TypeError("image must be a NumPy array")
    if image.size == 0 or image.ndim != 3 or image.shape[2] != 4:
        raise ValueError("image must be a non-empty CMYK array")
    if image.dtype != np.uint8:
        raise TypeError("image must have dtype uint8")
    return image
