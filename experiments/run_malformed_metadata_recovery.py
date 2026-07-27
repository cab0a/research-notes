"""Evaluate malformed JPEG metadata recovery across decoder boundaries."""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import platform
import sys
import warnings
from collections.abc import Callable, Sequence
from pathlib import Path

import cv2
import matplotlib
import numpy as np
import PIL
from numpy.typing import NDArray
from PIL import features

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

from research_notes import (  # noqa: E402
    audit_jpeg_metadata,
    build_synthetic_rgb_profile,
    compare_decoded_pixels,
    decode_jpeg_ffmpeg_with_expected_shape,
    decode_jpeg_opencv,
    decode_jpeg_pillow,
    encode_jpeg_pillow,
    ffmpeg_build_information,
    make_jpeg_app_segment,
    pixel_array_sha256,
)


IMAGE_HEIGHT = 72
IMAGE_WIDTH = 104
QUALITY = 75
FIXTURE_IDS = (
    "rgb_control",
    "exif_orientation_6_valid",
    "icc_gamma_2_2_valid",
    "app1_unknown_valid",
    "app15_large_valid",
    "exif_truncated_header",
    "exif_invalid_byte_order",
    "exif_ifd_offset_oob",
    "exif_orientation_9",
    "exif_conflicting_orientation",
    "icc_truncated_chunk_header",
    "icc_zero_sequence",
    "icc_missing_second_chunk",
    "icc_duplicate_sequence",
    "icc_inconsistent_chunk_count",
    "icc_truncated_profile",
    "app1_length_one",
    "app1_length_overrun",
    "trailing_data_after_eoi",
    "adobe_conflicting_transform",
    "app15_segment_limit",
)
DECODERS = ("opencv", "pillow", "ffmpeg")

FIXTURE_MANIFEST_NAME = "manifest.csv"
REFERENCE_PNG_NAME = "rgb_control.reference.png"
PLATFORM_MANIFEST_NAME = "jpeg_recovery_codec_manifest.csv"
AUDIT_NAME = "jpeg_recovery_audit.csv"
OBSERVATIONS_NAME = "jpeg_recovery_decoder_observations.csv"
SUMMARY_NAME = "jpeg_recovery_summary.csv"
FIGURE_NAME = "jpeg_recovery_contracts.png"

FIXTURE_FIELDS = (
    "fixture_id",
    "fixture_family",
    "mutation",
    "expected_strict_accept",
    "placement",
    "jpeg_file",
    "reference_png_file",
    "source_pixels_sha256",
    "jpeg_sha256",
    "jpeg_size_bytes",
    "inserted_bytes",
    "base_stream_preserved",
    "reference_bgr_sha256",
    "reference_png_sha256",
    "width",
    "height",
    "generator_adapter",
    "generator_wrapper_version",
    "generator_jpeg_backend",
)


def bytes_sha256(payload: bytes) -> str:
    """Return the SHA-256 digest of one byte string."""
    return hashlib.sha256(payload).hexdigest()


def source_array_sha256(image: NDArray[np.uint8]) -> str:
    """Hash a synthetic source array including shape and dtype."""
    digest = hashlib.sha256()
    digest.update(str(image.shape).encode("ascii"))
    digest.update(image.dtype.str.encode("ascii"))
    digest.update(image.tobytes())
    return digest.hexdigest()


def write_csv(
    path: Path,
    rows: Sequence[dict[str, str]],
    fieldnames: Sequence[str] | None = None,
) -> None:
    """Write deterministic UTF-8 CSV rows."""
    if not rows:
        raise ValueError("rows must not be empty")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(fieldnames or rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read one UTF-8 CSV file."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def make_source_image() -> NDArray[np.uint8]:
    """Create one asymmetric deterministic BGR source."""
    rows, columns = np.indices((IMAGE_HEIGHT, IMAGE_WIDTH))
    horizontal = columns.astype(np.float64) / (IMAGE_WIDTH - 1)
    vertical = rows.astype(np.float64) / (IMAGE_HEIGHT - 1)
    tiles = ((rows // 6 + columns // 8) % 2) == 0
    image = np.stack(
        (
            18.0 + 218.0 * horizontal,
            24.0 + 198.0 * vertical,
            232.0 - 105.0 * horizontal - 68.0 * vertical,
        ),
        axis=2,
    )
    image = np.clip(np.rint(image), 0, 255).astype(np.uint8)
    image[tiles] = np.clip(
        image[tiles].astype(np.int16) + np.array([16, -11, 19]),
        0,
        255,
    ).astype(np.uint8)
    cv2.circle(image, (21, 23), 13, (226, 24, 235), -1)
    cv2.rectangle(image, (54, 9), (93, 38), (21, 229, 44), -1)
    cv2.line(image, (6, 64), (97, 48), (243, 218, 21), 4)
    cv2.putText(
        image,
        "M",
        (78, 67),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.58,
        (245, 31, 31),
        2,
        cv2.LINE_AA,
    )
    return image


def encode_png(image: NDArray[np.uint8]) -> bytes:
    """Encode a BGR reference as deterministic PNG bytes."""
    succeeded, encoded = cv2.imencode(
        ".png", image, [cv2.IMWRITE_PNG_COMPRESSION, 9]
    )
    if not succeeded:
        raise RuntimeError("OpenCV PNG encoding failed")
    return encoded.tobytes()


def decode_png(payload: bytes) -> NDArray[np.uint8]:
    """Decode committed PNG reference bytes to BGR."""
    decoded = cv2.imdecode(
        np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR
    )
    if decoded is None:
        raise ValueError("OpenCV could not decode the reference PNG")
    return decoded


def opencv_jpeg_backend() -> str:
    """Return the JPEG backend line reported by OpenCV."""
    matches = [
        line.strip()
        for line in cv2.getBuildInformation().splitlines()
        if line.strip().startswith("JPEG:")
    ]
    if len(matches) != 1:
        raise RuntimeError("Could not identify the OpenCV JPEG backend")
    return matches[0].split(":", maxsplit=1)[1].strip()


def pillow_jpeg_backend() -> str:
    """Return the JPEG backend reported by Pillow."""
    turbo_version = features.version_feature("libjpeg_turbo")
    if turbo_version is not None:
        codec_name = (
            "mozjpeg"
            if features.check_feature("mozjpeg")
            else "libjpeg-turbo"
        )
        return f"{codec_name} {turbo_version}"
    jpeg_version = features.version_codec("jpg")
    if jpeg_version is None:
        raise RuntimeError("Pillow does not report a JPEG codec")
    return f"libjpeg {jpeg_version}"


def make_exif_payload(orientation: int) -> bytes:
    """Build a minimal big-endian EXIF Orientation payload."""
    tiff = (
        b"MM\x00*"
        + (8).to_bytes(4, "big")
        + (1).to_bytes(2, "big")
        + (274).to_bytes(2, "big")
        + (3).to_bytes(2, "big")
        + (1).to_bytes(4, "big")
        + orientation.to_bytes(2, "big")
        + b"\x00\x00"
        + b"\x00\x00\x00\x00"
    )
    return b"Exif\x00\x00" + tiff


def make_icc_segment(
    profile_chunk: bytes, sequence_number: int, chunk_count: int
) -> bytes:
    """Build one ICC APP2 segment with explicit topology bytes."""
    return make_jpeg_app_segment(
        2,
        b"ICC_PROFILE\x00"
        + bytes((sequence_number, chunk_count))
        + profile_chunk,
    )


def make_adobe_segment(transform: int) -> bytes:
    """Build one Adobe APP14 segment."""
    payload = (
        b"Adobe"
        + (100).to_bytes(2, "big")
        + (0).to_bytes(2, "big")
        + (0).to_bytes(2, "big")
        + bytes((transform,))
    )
    return make_jpeg_app_segment(14, payload)


def insert_after_soi(base: bytes, prefix: bytes) -> bytes:
    """Insert bytes after SOI while preserving the original stream tail."""
    return base[:2] + prefix + base[2:]


def fixture_payloads() -> list[dict[str, object]]:
    """Build all valid and malformed metadata controls."""
    source = make_source_image()
    base = encode_jpeg_pillow(
        source, quality=QUALITY, chroma_sampling="444"
    )
    profile = build_synthetic_rgb_profile(2.2)
    valid_exif = make_jpeg_app_segment(1, make_exif_payload(6))
    valid_icc = make_icc_segment(profile, 1, 1)
    profile_midpoint = len(profile) // 2
    definitions: list[tuple[str, str, str, bool, str, bytes]] = [
        (
            "rgb_control",
            "control",
            "none",
            True,
            "none",
            base,
        ),
        (
            "exif_orientation_6_valid",
            "valid_exif",
            "orientation_6",
            True,
            "after_soi",
            insert_after_soi(base, valid_exif),
        ),
        (
            "icc_gamma_2_2_valid",
            "valid_icc",
            "single_complete_chunk",
            True,
            "after_soi",
            insert_after_soi(base, valid_icc),
        ),
        (
            "app1_unknown_valid",
            "unknown_app",
            "well_framed_non_exif_app1",
            True,
            "after_soi",
            insert_after_soi(
                base,
                make_jpeg_app_segment(
                    1, b"http://ns.example.invalid/metadata/\x00synthetic"
                ),
            ),
        ),
        (
            "app15_large_valid",
            "resource_boundary",
            "single_60000_byte_app15",
            True,
            "after_soi",
            insert_after_soi(
                base, make_jpeg_app_segment(15, b"L" * 60000)
            ),
        ),
        (
            "exif_truncated_header",
            "malformed_exif",
            "truncated_tiff_header",
            False,
            "after_soi",
            insert_after_soi(
                base, make_jpeg_app_segment(1, b"Exif\x00\x00MM\x00")
            ),
        ),
        (
            "exif_invalid_byte_order",
            "malformed_exif",
            "invalid_tiff_byte_order",
            False,
            "after_soi",
            insert_after_soi(
                base,
                make_jpeg_app_segment(
                    1, b"Exif\x00\x00ZZ\x00*\x00\x00\x00\x08"
                ),
            ),
        ),
        (
            "exif_ifd_offset_oob",
            "malformed_exif",
            "ifd_offset_out_of_bounds",
            False,
            "after_soi",
            insert_after_soi(
                base,
                make_jpeg_app_segment(
                    1, b"Exif\x00\x00MM\x00*" + (4096).to_bytes(4, "big")
                ),
            ),
        ),
        (
            "exif_orientation_9",
            "malformed_exif",
            "orientation_out_of_range",
            False,
            "after_soi",
            insert_after_soi(
                base, make_jpeg_app_segment(1, make_exif_payload(9))
            ),
        ),
        (
            "exif_conflicting_orientation",
            "malformed_exif",
            "duplicate_orientation_3_and_6",
            False,
            "after_soi",
            insert_after_soi(
                base,
                make_jpeg_app_segment(1, make_exif_payload(3))
                + valid_exif,
            ),
        ),
        (
            "icc_truncated_chunk_header",
            "malformed_icc",
            "missing_chunk_count",
            False,
            "after_soi",
            insert_after_soi(
                base,
                make_jpeg_app_segment(2, b"ICC_PROFILE\x00\x01"),
            ),
        ),
        (
            "icc_zero_sequence",
            "malformed_icc",
            "zero_sequence_number",
            False,
            "after_soi",
            insert_after_soi(base, make_icc_segment(profile, 0, 1)),
        ),
        (
            "icc_missing_second_chunk",
            "malformed_icc",
            "declared_two_observed_one",
            False,
            "after_soi",
            insert_after_soi(base, make_icc_segment(profile, 1, 2)),
        ),
        (
            "icc_duplicate_sequence",
            "malformed_icc",
            "duplicate_sequence_one",
            False,
            "after_soi",
            insert_after_soi(
                base,
                make_icc_segment(profile, 1, 1)
                + make_icc_segment(profile, 1, 1),
            ),
        ),
        (
            "icc_inconsistent_chunk_count",
            "malformed_icc",
            "chunk_counts_two_and_three",
            False,
            "after_soi",
            insert_after_soi(
                base,
                make_icc_segment(profile[:profile_midpoint], 1, 2)
                + make_icc_segment(profile[profile_midpoint:], 2, 3),
            ),
        ),
        (
            "icc_truncated_profile",
            "malformed_icc",
            "profile_size_mismatch",
            False,
            "after_soi",
            insert_after_soi(
                base, make_icc_segment(profile[:-32], 1, 1)
            ),
        ),
        (
            "app1_length_one",
            "malformed_framing",
            "illegal_segment_length_one",
            False,
            "after_soi",
            insert_after_soi(base, b"\xff\xe1\x00\x01"),
        ),
        (
            "app1_length_overrun",
            "malformed_framing",
            "declared_segment_exceeds_file",
            False,
            "after_soi",
            insert_after_soi(base, b"\xff\xe1\xff\xffshort"),
        ),
        (
            "trailing_data_after_eoi",
            "malformed_framing",
            "eight_trailing_bytes",
            False,
            "after_eoi",
            base + b"TRAILING",
        ),
        (
            "adobe_conflicting_transform",
            "malformed_adobe",
            "duplicate_transform_zero_and_one",
            False,
            "after_soi",
            insert_after_soi(
                base, make_adobe_segment(0) + make_adobe_segment(1)
            ),
        ),
        (
            "app15_segment_limit",
            "resource_boundary",
            "forty_small_app15_segments",
            False,
            "after_soi",
            insert_after_soi(
                base,
                b"".join(
                    make_jpeg_app_segment(15, bytes((index,)))
                    for index in range(40)
                ),
            ),
        ),
    ]
    return [
        {
            "fixture_id": fixture_id,
            "fixture_family": family,
            "mutation": mutation,
            "expected_strict_accept": expected,
            "placement": placement,
            "jpeg_bytes": jpeg_bytes,
            "base_bytes": base,
        }
        for fixture_id, family, mutation, expected, placement, jpeg_bytes
        in definitions
    ]


def preserved_base_stream(
    fixture: bytes, base: bytes, placement: str, inserted_bytes: int
) -> bool:
    """Check the declared byte-preservation relationship."""
    if placement == "none":
        return fixture == base and inserted_bytes == 0
    if placement == "after_soi":
        return fixture[2 + inserted_bytes :] == base[2:]
    if placement == "after_eoi":
        return fixture[: len(base)] == base
    raise ValueError("unknown fixture placement")


def refresh_fixtures(fixture_dir: Path) -> list[dict[str, str]]:
    """Generate the fixed malformed-metadata corpus and manifest."""
    fixture_dir.mkdir(parents=True, exist_ok=True)
    source = make_source_image()
    base_reference = decode_jpeg_opencv(
        encode_jpeg_pillow(
            source, quality=QUALITY, chroma_sampling="444"
        ),
        ignore_orientation=True,
    )
    png_bytes = encode_png(base_reference)
    (fixture_dir / REFERENCE_PNG_NAME).write_bytes(png_bytes)
    rows: list[dict[str, str]] = []
    for item in fixture_payloads():
        fixture_id = str(item["fixture_id"])
        jpeg_bytes = item["jpeg_bytes"]
        base = item["base_bytes"]
        if not isinstance(jpeg_bytes, bytes) or not isinstance(base, bytes):
            raise TypeError("fixture payloads must be bytes")
        placement = str(item["placement"])
        inserted_bytes = len(jpeg_bytes) - len(base)
        audit = audit_jpeg_metadata(jpeg_bytes)
        expected = bool(item["expected_strict_accept"])
        if audit.accepted != expected:
            raise RuntimeError(
                f"Fixture {fixture_id} failed its strict audit contract"
            )
        if not preserved_base_stream(
            jpeg_bytes, base, placement, inserted_bytes
        ):
            raise RuntimeError(
                f"Fixture {fixture_id} changed the controlled base stream"
            )
        jpeg_name = f"{fixture_id}.jpg"
        (fixture_dir / jpeg_name).write_bytes(jpeg_bytes)
        rows.append(
            {
                "fixture_id": fixture_id,
                "fixture_family": str(item["fixture_family"]),
                "mutation": str(item["mutation"]),
                "expected_strict_accept": str(int(expected)),
                "placement": placement,
                "jpeg_file": jpeg_name,
                "reference_png_file": REFERENCE_PNG_NAME,
                "source_pixels_sha256": source_array_sha256(source),
                "jpeg_sha256": bytes_sha256(jpeg_bytes),
                "jpeg_size_bytes": str(len(jpeg_bytes)),
                "inserted_bytes": str(inserted_bytes),
                "base_stream_preserved": "1",
                "reference_bgr_sha256": pixel_array_sha256(base_reference),
                "reference_png_sha256": bytes_sha256(png_bytes),
                "width": str(IMAGE_WIDTH),
                "height": str(IMAGE_HEIGHT),
                "generator_adapter": "pillow_rgb_plus_controlled_app_bytes",
                "generator_wrapper_version": PIL.__version__,
                "generator_jpeg_backend": pillow_jpeg_backend(),
            }
        )
    rows.sort(key=lambda row: row["fixture_id"])
    validate_fixture_coverage(rows)
    write_csv(
        fixture_dir / FIXTURE_MANIFEST_NAME, rows, FIXTURE_FIELDS
    )
    return rows


def validate_fixture_coverage(rows: Sequence[dict[str, str]]) -> None:
    """Validate the fixed fixture identities and declared controls."""
    if {row["fixture_id"] for row in rows} != set(FIXTURE_IDS):
        raise RuntimeError("Fixture manifest has unexpected coverage")
    if len(rows) != len(FIXTURE_IDS):
        raise RuntimeError("Fixture manifest contains duplicate identifiers")
    if not all(row["base_stream_preserved"] == "1" for row in rows):
        raise RuntimeError("A fixture changed the controlled base stream")


def load_and_validate_fixtures(
    fixture_dir: Path,
) -> list[dict[str, str]]:
    """Load and validate the committed fixture corpus."""
    rows = read_csv(fixture_dir / FIXTURE_MANIFEST_NAME)
    generated = {
        str(item["fixture_id"]): item for item in fixture_payloads()
    }
    source = make_source_image()
    png_bytes = (fixture_dir / REFERENCE_PNG_NAME).read_bytes()
    reference = decode_png(png_bytes)
    for row in rows:
        fixture_id = row["fixture_id"]
        item = generated[fixture_id]
        jpeg_bytes = (fixture_dir / row["jpeg_file"]).read_bytes()
        expected_bytes = item["jpeg_bytes"]
        base = item["base_bytes"]
        if jpeg_bytes != expected_bytes:
            raise RuntimeError(
                f"Fixture {fixture_id} differs from deterministic generation"
            )
        if not isinstance(base, bytes):
            raise TypeError("base fixture must be bytes")
        inserted_bytes = len(jpeg_bytes) - len(base)
        checks = {
            "source_pixels_sha256": source_array_sha256(source),
            "jpeg_sha256": bytes_sha256(jpeg_bytes),
            "jpeg_size_bytes": str(len(jpeg_bytes)),
            "inserted_bytes": str(inserted_bytes),
            "base_stream_preserved": str(
                int(
                    preserved_base_stream(
                        jpeg_bytes,
                        base,
                        row["placement"],
                        inserted_bytes,
                    )
                )
            ),
            "reference_bgr_sha256": pixel_array_sha256(reference),
            "reference_png_sha256": bytes_sha256(png_bytes),
            "width": str(IMAGE_WIDTH),
            "height": str(IMAGE_HEIGHT),
        }
        for field, observed in checks.items():
            if row[field] != observed:
                raise RuntimeError(
                    f"Fixture {fixture_id} failed {field} validation"
                )
        audit = audit_jpeg_metadata(jpeg_bytes)
        if int(row["expected_strict_accept"]) != int(audit.accepted):
            raise RuntimeError(
                f"Fixture {fixture_id} failed its audit expectation"
            )
    validate_fixture_coverage(rows)
    return sorted(rows, key=lambda row: row["fixture_id"])


def build_platform_manifest(
    platform_label: str, *, record_runner_image: bool = False
) -> list[dict[str, str]]:
    """Record decoder and strict-auditor provenance without local paths."""
    common = {
        "platform_label": platform_label,
        "operating_system": platform.system(),
        "architecture": platform.machine().lower(),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
        "runner_image_os": (
            os.environ.get("ImageOS", "unknown")
            if record_runner_image
            else "not_recorded"
        ),
        "runner_image_version": (
            os.environ.get("ImageVersion", "unknown")
            if record_runner_image
            else "not_recorded"
        ),
        "libjpeg_simd_policy": (
            "forced_scalar"
            if os.environ.get("JSIMD_FORCENONE") == "1"
            else "runtime_default"
        ),
    }
    opencv_backend = opencv_jpeg_backend()
    pillow_backend = pillow_jpeg_backend()
    ffmpeg = ffmpeg_build_information()
    definitions = (
        (
            "strict_metadata_auditor",
            "audit",
            "research-notes",
            "0.13.0",
            "bounded_python_marker_parser",
            "JPEG APP, EXIF, ICC, and Adobe structural policy",
            bytes_sha256(b"v0.13.0-strict-metadata-auditor"),
        ),
        (
            "opencv",
            "decoder",
            "OpenCV",
            cv2.__version__,
            "libjpeg-turbo",
            opencv_backend,
            bytes_sha256(opencv_backend.encode("utf-8")),
        ),
        (
            "pillow",
            "decoder",
            "Pillow",
            PIL.__version__,
            "libjpeg-turbo",
            pillow_backend,
            bytes_sha256(pillow_backend.encode("utf-8")),
        ),
        (
            "ffmpeg",
            "decoder",
            ffmpeg["adapter"],
            ffmpeg["adapter_version"],
            ffmpeg["codec_family"],
            f"FFmpeg {ffmpeg['codec_version']} native mjpeg",
            ffmpeg["codec_build_fingerprint"],
        ),
    )
    return [
        {
            **common,
            "component": component,
            "component_role": role,
            "adapter": adapter,
            "adapter_version": adapter_version,
            "implementation_family": implementation,
            "reported_backend": reported,
            "build_fingerprint": fingerprint,
        }
        for (
            component,
            role,
            adapter,
            adapter_version,
            implementation,
            reported,
            fingerprint,
        ) in definitions
    ]


def decode_fixture(
    decoder: str, payload: bytes
) -> NDArray[np.uint8]:
    """Decode one fixture through a declared raw-pixel adapter."""
    adapters: dict[str, Callable[[bytes], NDArray[np.uint8]]] = {
        "opencv": lambda value: decode_jpeg_opencv(
            value, ignore_orientation=True
        ),
        "pillow": decode_jpeg_pillow,
        "ffmpeg": lambda value: decode_jpeg_ffmpeg_with_expected_shape(
            value,
            width=IMAGE_WIDTH,
            height=IMAGE_HEIGHT,
            ignore_orientation=True,
        ),
    }
    if decoder == "pillow":
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return adapters[decoder](payload)
    return adapters[decoder](payload)


def diagnostic_sha256(error: Exception) -> str:
    """Hash a decoder diagnostic without publishing environment text."""
    normalized = " ".join(str(error).split())
    return bytes_sha256(
        f"{type(error).__name__}:{normalized}".encode("utf-8")
    )


def audit_rows(
    fixtures: Sequence[dict[str, str]],
    fixture_dir: Path,
    platform_label: str,
) -> list[dict[str, str]]:
    """Audit every fixture under the fixed strict policy."""
    rows: list[dict[str, str]] = []
    for fixture in fixtures:
        payload = (fixture_dir / fixture["jpeg_file"]).read_bytes()
        audit = audit_jpeg_metadata(payload)
        expected = int(fixture["expected_strict_accept"])
        rows.append(
            {
                "platform_label": platform_label,
                "fixture_id": fixture["fixture_id"],
                "fixture_family": fixture["fixture_family"],
                "mutation": fixture["mutation"],
                "expected_strict_accept": str(expected),
                "strict_accept": str(int(audit.accepted)),
                "expected_contract_met": str(
                    int(expected == int(audit.accepted))
                ),
                "container_valid": str(int(audit.container_valid)),
                "metadata_valid": str(int(audit.metadata_valid)),
                "image_data_present": str(int(audit.image_data_present)),
                "issue_codes": (
                    "|".join(audit.issue_codes) if audit.issue_codes else "none"
                ),
                "issue_count": str(len(audit.issue_codes)),
                "app_segment_count": str(audit.app_segment_count),
                "metadata_payload_bytes": str(
                    audit.metadata_payload_bytes
                ),
                "exif_orientations": (
                    "|".join(map(str, audit.exif_orientations))
                    if audit.exif_orientations
                    else "none"
                ),
                "icc_declared_chunks": str(audit.icc_declared_chunks),
                "icc_observed_chunks": str(audit.icc_observed_chunks),
                "icc_profile_length": str(audit.icc_profile_length),
                "adobe_transforms": (
                    "|".join(map(str, audit.adobe_transforms))
                    if audit.adobe_transforms
                    else "none"
                ),
                "trailing_bytes": str(audit.trailing_bytes),
            }
        )
    if not all(row["expected_contract_met"] == "1" for row in rows):
        raise RuntimeError("A strict audit expectation failed")
    return rows


def decoder_observation_rows(
    fixtures: Sequence[dict[str, str]],
    fixture_dir: Path,
    audits: Sequence[dict[str, str]],
    platform_label: str,
) -> list[dict[str, str]]:
    """Probe decoder recovery and compare successes with decoder controls."""
    fixture_index = {row["fixture_id"]: row for row in fixtures}
    audit_index = {row["fixture_id"]: row for row in audits}
    control_payload = (
        fixture_dir / fixture_index["rgb_control"]["jpeg_file"]
    ).read_bytes()
    controls = {
        decoder: decode_fixture(decoder, control_payload)
        for decoder in DECODERS
    }
    expected_shape = (IMAGE_HEIGHT, IMAGE_WIDTH, 3)
    if any(
        image.shape != expected_shape or image.dtype != np.uint8
        for image in controls.values()
    ):
        raise RuntimeError("A decoder control failed its array contract")

    rows: list[dict[str, str]] = []
    for fixture in fixtures:
        payload = (fixture_dir / fixture["jpeg_file"]).read_bytes()
        for decoder in DECODERS:
            candidate: NDArray[np.uint8] | None = None
            error: Exception | None = None
            try:
                candidate = decode_fixture(decoder, payload)
            except (RuntimeError, TypeError, ValueError) as caught:
                error = caught
            success = candidate is not None
            shape_contract = (
                success and candidate is not None
                and candidate.shape == expected_shape
            )
            dtype_contract = (
                success and candidate is not None
                and candidate.dtype == np.uint8
            )
            if shape_contract and dtype_contract and candidate is not None:
                difference = compare_decoded_pixels(
                    controls[decoder], candidate
                )
                exact = str(int(difference.exact))
                mean_error = f"{difference.mean_absolute_error:.9f}"
                maximum_error = str(difference.maximum_absolute_error)
                changed_fraction = (
                    f"{difference.changed_pixel_fraction:.9f}"
                )
                output_hash = difference.candidate_sha256
                error_category = "none"
                error_hash = ""
            else:
                exact = "0"
                mean_error = "nan"
                maximum_error = "nan"
                changed_fraction = "nan"
                output_hash = (
                    pixel_array_sha256(candidate)
                    if candidate is not None
                    else ""
                )
                error_category = (
                    "decoder_rejected"
                    if error is not None
                    else "array_contract_failed"
                )
                error_hash = (
                    diagnostic_sha256(error) if error is not None else ""
                )
            rows.append(
                {
                    "platform_label": platform_label,
                    "fixture_id": fixture["fixture_id"],
                    "fixture_family": fixture["fixture_family"],
                    "mutation": fixture["mutation"],
                    "decoder": decoder,
                    "strict_audit_accept": audit_index[
                        fixture["fixture_id"]
                    ]["strict_accept"],
                    "decode_success": str(int(success)),
                    "shape_contract": str(int(shape_contract)),
                    "dtype_contract": str(int(dtype_contract)),
                    "exact_to_decoder_control": exact,
                    "mean_absolute_error": mean_error,
                    "maximum_absolute_error": maximum_error,
                    "changed_pixel_fraction": changed_fraction,
                    "control_bgr_sha256": pixel_array_sha256(
                        controls[decoder]
                    ),
                    "output_bgr_sha256": output_hash,
                    "error_category": error_category,
                    "diagnostic_sha256": error_hash,
                }
            )
    expected_count = len(FIXTURE_IDS) * len(DECODERS)
    if len(rows) != expected_count:
        raise RuntimeError("Unexpected decoder observation count")
    return rows


def summarize_local(
    audits: Sequence[dict[str, str]],
    observations: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Summarize strict decisions and decoder recovery by fixture."""
    rows: list[dict[str, str]] = []
    for audit in sorted(audits, key=lambda row: row["fixture_id"]):
        group = [
            row
            for row in observations
            if row["fixture_id"] == audit["fixture_id"]
        ]
        successful = [
            row for row in group if row["decode_success"] == "1"
        ]
        exact = [
            row
            for row in successful
            if row["exact_to_decoder_control"] == "1"
        ]
        rows.append(
            {
                "fixture_id": audit["fixture_id"],
                "fixture_family": audit["fixture_family"],
                "mutation": audit["mutation"],
                "strict_audit_accept": audit["strict_accept"],
                "issue_codes": audit["issue_codes"],
                "decoder_attempts": str(len(group)),
                "decoder_successes": str(len(successful)),
                "exact_successes": str(len(exact)),
                "strict_reject_but_decode_successes": str(
                    len(successful)
                    if audit["strict_accept"] == "0"
                    else 0
                ),
                "rejected_decoders": (
                    "|".join(
                        row["decoder"]
                        for row in group
                        if row["decode_success"] == "0"
                    )
                    or "none"
                ),
                "nonexact_successful_decoders": (
                    "|".join(
                        row["decoder"]
                        for row in successful
                        if row["exact_to_decoder_control"] == "0"
                    )
                    or "none"
                ),
            }
        )
    return rows


def plot_results(
    audits: Sequence[dict[str, str]],
    observations: Sequence[dict[str, str]],
    output_path: Path,
) -> None:
    """Visualize strict acceptance, decoder recovery, and resource controls."""
    audit_index = {row["fixture_id"]: row for row in audits}
    observation_index = {
        (row["fixture_id"], row["decoder"]): row for row in observations
    }
    fixture_ids = list(FIXTURE_IDS)
    short_labels = [
        fixture_id.replace("_orientation_", "_ori_")
        .replace("_sequence", "_seq")
        .replace("_conflicting", "_conflict")
        .replace("_after_eoi", "_post_eoi")
        for fixture_id in fixture_ids
    ]
    acceptance = np.array(
        [
            [int(audit_index[fixture_id]["strict_accept"])]
            + [
                int(
                    observation_index[
                        (fixture_id, decoder)
                    ]["decode_success"]
                )
                for decoder in DECODERS
            ]
            for fixture_id in fixture_ids
        ],
        dtype=np.float64,
    )
    exactness = np.full((len(fixture_ids), len(DECODERS)), np.nan)
    for row_index, fixture_id in enumerate(fixture_ids):
        for column_index, decoder in enumerate(DECODERS):
            row = observation_index[(fixture_id, decoder)]
            if row["decode_success"] == "1":
                exactness[row_index, column_index] = int(
                    row["exact_to_decoder_control"]
                )

    figure, axes = plt.subplots(
        1, 3, figsize=(17, 11), constrained_layout=True
    )
    accepted_image = axes[0].imshow(
        acceptance, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1
    )
    axes[0].set_xticks(
        range(4), ("strict audit", "OpenCV", "Pillow", "FFmpeg"), rotation=30
    )
    axes[0].set_yticks(range(len(short_labels)), short_labels, fontsize=8)
    axes[0].set_title("Policy acceptance versus decode success")
    for row_index in range(len(fixture_ids)):
        for column_index in range(4):
            axes[0].text(
                column_index,
                row_index,
                "yes" if acceptance[row_index, column_index] else "no",
                ha="center",
                va="center",
                fontsize=7,
            )
    figure.colorbar(accepted_image, ax=axes[0], shrink=0.65)

    exact_image = axes[1].imshow(
        exactness, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1
    )
    axes[1].set_xticks(range(3), DECODERS, rotation=30)
    axes[1].set_yticks(range(len(short_labels)), short_labels, fontsize=8)
    axes[1].set_title("Successful output versus decoder control")
    for row_index in range(len(fixture_ids)):
        for column_index in range(3):
            value = exactness[row_index, column_index]
            axes[1].text(
                column_index,
                row_index,
                "reject"
                if np.isnan(value)
                else ("exact" if value else "changed"),
                ha="center",
                va="center",
                fontsize=7,
            )
    figure.colorbar(exact_image, ax=axes[1], shrink=0.65)

    issue_counts = np.array(
        [int(audit_index[name]["issue_count"]) for name in fixture_ids]
    )
    metadata_bytes = np.array(
        [
            int(audit_index[name]["metadata_payload_bytes"])
            for name in fixture_ids
        ]
    )
    positions = np.arange(len(fixture_ids))
    axes[2].barh(
        positions,
        np.log10(metadata_bytes + 1),
        color="#4f81bd",
        label="log10(metadata bytes + 1)",
    )
    axes[2].scatter(
        issue_counts,
        positions,
        color="#c75046",
        marker="x",
        label="strict issue count",
    )
    axes[2].set_yticks(positions, short_labels, fontsize=8)
    axes[2].invert_yaxis()
    axes[2].set_xlabel("Diagnostic scale")
    axes[2].set_title("Bounded metadata and audit issues")
    axes[2].legend(loc="lower right")

    figure.suptitle(
        "Malformed JPEG metadata: strict audit and decoder recovery"
    )
    figure.savefig(output_path, dpi=160)
    plt.close(figure)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate malformed JPEG metadata recovery and trust boundaries."
        )
    )
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=Path("fixtures/malformed-jpeg-metadata"),
        help="Directory containing the fixed JPEG fixture corpus.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results"),
        help="Directory for CSV and PNG outputs.",
    )
    parser.add_argument(
        "--platform-label",
        default="local-reference",
        help="Stable label recorded in platform observations.",
    )
    parser.add_argument(
        "--refresh-fixtures",
        action="store_true",
        help="Regenerate the deterministic fixture corpus before evaluation.",
    )
    parser.add_argument(
        "--record-runner-image",
        action="store_true",
        help="Record GitHub-hosted runner image environment fields.",
    )
    return parser.parse_args()


def main() -> None:
    """Validate fixtures, probe decoders, and write reference evidence."""
    args = parse_args()
    if args.refresh_fixtures:
        refresh_fixtures(args.fixture_dir)
    fixtures = load_and_validate_fixtures(args.fixture_dir)
    audits = audit_rows(fixtures, args.fixture_dir, args.platform_label)
    observations = decoder_observation_rows(
        fixtures, args.fixture_dir, audits, args.platform_label
    )
    summary = summarize_local(audits, observations)
    manifest = build_platform_manifest(
        args.platform_label,
        record_runner_image=args.record_runner_image,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / PLATFORM_MANIFEST_NAME, manifest)
    write_csv(args.output_dir / AUDIT_NAME, audits)
    write_csv(args.output_dir / OBSERVATIONS_NAME, observations)
    write_csv(args.output_dir / SUMMARY_NAME, summary)
    plot_results(
        audits, observations, args.output_dir / FIGURE_NAME
    )
    successful = sum(
        int(row["decode_success"]) for row in observations
    )
    exact = sum(
        int(row["exact_to_decoder_control"]) for row in observations
    )
    print(
        "Malformed metadata evaluation complete: "
        f"{len(fixtures)} fixtures, {len(observations)} decoder probes, "
        f"{successful} successful decodes, and {exact} pixel-exact "
        "successful outputs."
    )


if __name__ == "__main__":
    main()
