"""Evaluate JPEG color and orientation metadata interpretation policies."""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import platform
import sys
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
    apply_exif_orientation_bgr,
    attach_jpeg_metadata,
    build_synthetic_rgb_profile,
    cmyk_to_bgr_arithmetic,
    compare_decoded_pixels,
    decode_jpeg_ffmpeg,
    decode_jpeg_opencv,
    decode_jpeg_pillow,
    decode_jpeg_pillow_color_managed,
    decode_jpeg_pillow_oriented,
    encode_jpeg_cmyk_pillow,
    encode_jpeg_pillow,
    encode_jpeg_ycck_pillow,
    ffmpeg_build_information,
    inspect_jpeg_metadata,
    inspect_jpeg_syntax,
    parse_jpeg_structure,
    pixel_array_sha256,
    strip_jpeg_interpretation_metadata,
)


IMAGE_HEIGHT = 72
IMAGE_WIDTH = 104
QUALITY = 75
ICC_FIXTURES = (
    "rgb_untagged",
    "rgb_icc_gamma_1_0",
    "rgb_icc_gamma_2_2",
)
ORIENTATION_FIXTURES = tuple(f"rgb_orientation_{value}" for value in range(1, 9))
FOUR_COMPONENT_FIXTURES = ("cmyk_adobe0", "ycck_adobe2")
FIXTURE_IDS = ICC_FIXTURES + ORIENTATION_FIXTURES + FOUR_COMPONENT_FIXTURES
RAW_DECODERS: dict[str, Callable[[bytes], NDArray[np.uint8]]] = {
    "opencv": lambda payload: decode_jpeg_opencv(
        payload, ignore_orientation=True
    ),
    "pillow": decode_jpeg_pillow,
    "ffmpeg": lambda payload: decode_jpeg_ffmpeg(
        payload, ignore_orientation=True
    ),
}

FIXTURE_MANIFEST_NAME = "manifest.csv"
PLATFORM_MANIFEST_NAME = "jpeg_metadata_codec_manifest.csv"
RAW_OBSERVATIONS_NAME = "jpeg_metadata_raw_observations.csv"
POLICY_OBSERVATIONS_NAME = "jpeg_metadata_policy_observations.csv"
CONTROL_PAIRS_NAME = "jpeg_metadata_control_pairs.csv"
SUMMARY_NAME = "jpeg_metadata_summary.csv"
FIGURE_NAME = "jpeg_metadata_interpretation.png"

FIXTURE_FIELDS = (
    "fixture_id",
    "fixture_family",
    "metadata_control",
    "source_mode",
    "jpeg_file",
    "reference_png_file",
    "source_pixels_sha256",
    "jpeg_sha256",
    "jpeg_core_sha256",
    "jpeg_size_bytes",
    "reference_bgr_sha256",
    "reference_png_sha256",
    "width",
    "height",
    "component_count",
    "component_signature",
    "quantization_fingerprint",
    "exif_orientation",
    "icc_profile_length",
    "icc_profile_sha256",
    "icc_chunk_count",
    "adobe_transform",
    "generator_adapter",
    "generator_wrapper_version",
    "generator_jpeg_backend",
    "reference_decoder",
)


def bytes_sha256(payload: bytes) -> str:
    """Return the SHA-256 digest of a byte string."""
    return hashlib.sha256(payload).hexdigest()


def source_array_sha256(image: NDArray[np.uint8]) -> str:
    """Hash a declared synthetic source array including its interface."""
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
    """Write deterministic CSV rows with explicit field ordering."""
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
    """Read one UTF-8 CSV report."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def make_color_sources() -> dict[str, NDArray[np.uint8]]:
    """Create asymmetric deterministic BGR and CMYK control arrays."""
    rows, columns = np.indices((IMAGE_HEIGHT, IMAGE_WIDTH))
    horizontal = columns.astype(np.float64) / (IMAGE_WIDTH - 1)
    vertical = rows.astype(np.float64) / (IMAGE_HEIGHT - 1)
    tile_mask = ((rows // 7 + columns // 9) % 2) == 0
    bgr = np.stack(
        (
            20.0 + 218.0 * horizontal,
            28.0 + 190.0 * vertical,
            235.0 - 110.0 * horizontal - 72.0 * vertical,
        ),
        axis=2,
    )
    bgr = np.clip(np.rint(bgr), 0, 255).astype(np.uint8)
    bgr[tile_mask] = np.clip(
        bgr[tile_mask].astype(np.int16) + np.array([15, -12, 18]),
        0,
        255,
    ).astype(np.uint8)
    cv2.circle(bgr, (22, 24), 13, (226, 24, 235), -1)
    cv2.rectangle(bgr, (55, 10), (92, 39), (22, 228, 45), -1)
    cv2.line(bgr, (7, 64), (96, 48), (242, 219, 20), 4)
    cv2.putText(
        bgr,
        "R",
        (79, 66),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.58,
        (245, 30, 30),
        2,
        cv2.LINE_AA,
    )
    cmyk = np.stack(
        (
            np.rint(225.0 * horizontal),
            np.rint(225.0 * vertical),
            np.where(tile_mask, 35.0, 205.0),
            np.rint(15.0 + 105.0 * (horizontal + vertical) / 2.0),
        ),
        axis=2,
    ).astype(np.uint8)
    return {"BGR": bgr, "CMYK": cmyk}


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


def encode_png(image: NDArray[np.uint8]) -> bytes:
    """Encode a BGR reference as deterministic lossless PNG bytes."""
    succeeded, encoded = cv2.imencode(
        ".png", image, [cv2.IMWRITE_PNG_COMPRESSION, 9]
    )
    if not succeeded:
        raise RuntimeError("OpenCV PNG encoding failed")
    return encoded.tobytes()


def decode_png(payload: bytes) -> NDArray[np.uint8]:
    """Decode a committed PNG reference to BGR pixels."""
    decoded = cv2.imdecode(
        np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR
    )
    if decoded is None:
        raise ValueError("OpenCV could not decode the reference PNG")
    return decoded


def fixture_payloads() -> list[dict[str, object]]:
    """Build JPEG streams for all controlled metadata families."""
    sources = make_color_sources()
    bgr = sources["BGR"]
    cmyk = sources["CMYK"]
    base_rgb = encode_jpeg_pillow(
        bgr, quality=QUALITY, chroma_sampling="444"
    )
    gamma_1 = build_synthetic_rgb_profile(1.0)
    gamma_2_2 = build_synthetic_rgb_profile(2.2)
    payloads: list[dict[str, object]] = [
        {
            "fixture_id": "rgb_untagged",
            "fixture_family": "icc_profile",
            "metadata_control": "untagged",
            "source_mode": "BGR",
            "jpeg_bytes": base_rgb,
            "generator_adapter": "pillow_rgb_plus_app_segments",
        },
        {
            "fixture_id": "rgb_icc_gamma_1_0",
            "fixture_family": "icc_profile",
            "metadata_control": "matrix_trc_gamma_1_0",
            "source_mode": "BGR",
            "jpeg_bytes": attach_jpeg_metadata(
                base_rgb, icc_profile=gamma_1
            ),
            "generator_adapter": "pillow_rgb_plus_app_segments",
        },
        {
            "fixture_id": "rgb_icc_gamma_2_2",
            "fixture_family": "icc_profile",
            "metadata_control": "matrix_trc_gamma_2_2",
            "source_mode": "BGR",
            "jpeg_bytes": attach_jpeg_metadata(
                base_rgb, icc_profile=gamma_2_2
            ),
            "generator_adapter": "pillow_rgb_plus_app_segments",
        },
    ]
    payloads.extend(
        {
            "fixture_id": f"rgb_orientation_{orientation}",
            "fixture_family": "exif_orientation",
            "metadata_control": f"orientation_{orientation}",
            "source_mode": "BGR",
            "jpeg_bytes": attach_jpeg_metadata(
                base_rgb, exif_orientation=orientation
            ),
            "generator_adapter": "pillow_rgb_plus_app_segments",
        }
        for orientation in range(1, 9)
    )
    payloads.extend(
        (
            {
                "fixture_id": "cmyk_adobe0",
                "fixture_family": "four_component_color",
                "metadata_control": "adobe_transform_0",
                "source_mode": "CMYK",
                "jpeg_bytes": encode_jpeg_cmyk_pillow(
                    cmyk, quality=QUALITY
                ),
                "generator_adapter": "pillow_cmyk",
            },
            {
                "fixture_id": "ycck_adobe2",
                "fixture_family": "four_component_color",
                "metadata_control": "adobe_transform_2",
                "source_mode": "CMYK",
                "jpeg_bytes": encode_jpeg_ycck_pillow(
                    cmyk, quality=QUALITY
                ),
                "generator_adapter": "pillow_ycck_control",
            },
        )
    )
    return payloads


def refresh_fixtures(fixture_dir: Path) -> list[dict[str, str]]:
    """Generate the fixed JPEG corpus and raw OpenCV BGR references."""
    fixture_dir.mkdir(parents=True, exist_ok=True)
    sources = make_color_sources()
    rows: list[dict[str, str]] = []
    backend = pillow_jpeg_backend()
    for payload in fixture_payloads():
        fixture_id = str(payload["fixture_id"])
        jpeg_bytes = payload["jpeg_bytes"]
        if not isinstance(jpeg_bytes, bytes):
            raise TypeError("fixture JPEG payload must be bytes")
        jpeg_name = f"{fixture_id}.jpg"
        reference_name = f"{fixture_id}.reference.png"
        reference = decode_jpeg_opencv(
            jpeg_bytes, ignore_orientation=True
        )
        png_bytes = encode_png(reference)
        structure = parse_jpeg_structure(jpeg_bytes)
        metadata = inspect_jpeg_metadata(jpeg_bytes)
        (fixture_dir / jpeg_name).write_bytes(jpeg_bytes)
        (fixture_dir / reference_name).write_bytes(png_bytes)
        source_mode = str(payload["source_mode"])
        rows.append(
            {
                "fixture_id": fixture_id,
                "fixture_family": str(payload["fixture_family"]),
                "metadata_control": str(payload["metadata_control"]),
                "source_mode": source_mode,
                "jpeg_file": jpeg_name,
                "reference_png_file": reference_name,
                "source_pixels_sha256": source_array_sha256(
                    sources[source_mode]
                ),
                "jpeg_sha256": bytes_sha256(jpeg_bytes),
                "jpeg_core_sha256": bytes_sha256(
                    strip_jpeg_interpretation_metadata(jpeg_bytes)
                ),
                "jpeg_size_bytes": str(len(jpeg_bytes)),
                "reference_bgr_sha256": pixel_array_sha256(reference),
                "reference_png_sha256": bytes_sha256(png_bytes),
                "width": str(structure.width),
                "height": str(structure.height),
                "component_count": str(len(structure.components)),
                "component_signature": structure.component_signature,
                "quantization_fingerprint": (
                    structure.quantization_fingerprint
                ),
                "exif_orientation": (
                    "none"
                    if metadata.exif_orientation is None
                    else str(metadata.exif_orientation)
                ),
                "icc_profile_length": str(metadata.icc_profile_length),
                "icc_profile_sha256": metadata.icc_profile_sha256,
                "icc_chunk_count": str(metadata.icc_chunk_count),
                "adobe_transform": (
                    "none"
                    if metadata.adobe_transform is None
                    else str(metadata.adobe_transform)
                ),
                "generator_adapter": str(payload["generator_adapter"]),
                "generator_wrapper_version": PIL.__version__,
                "generator_jpeg_backend": backend,
                "reference_decoder": "opencv_bgr_ignore_orientation",
            }
        )
    rows.sort(key=lambda row: row["fixture_id"])
    validate_fixture_controls(rows)
    write_csv(fixture_dir / FIXTURE_MANIFEST_NAME, rows, FIXTURE_FIELDS)
    return rows


def validate_fixture_controls(rows: Sequence[dict[str, str]]) -> None:
    """Validate corpus coverage and metadata-only control relationships."""
    if {row["fixture_id"] for row in rows} != set(FIXTURE_IDS):
        raise RuntimeError("Fixture manifest does not contain the expected corpus")
    indexed = {row["fixture_id"]: row for row in rows}
    if len({indexed[name]["jpeg_core_sha256"] for name in ICC_FIXTURES}) != 1:
        raise RuntimeError("ICC fixtures do not share one compressed JPEG core")
    if len(
        {
            indexed[name]["jpeg_core_sha256"]
            for name in ORIENTATION_FIXTURES
        }
    ) != 1:
        raise RuntimeError(
            "Orientation fixtures do not share one compressed JPEG core"
        )
    for orientation, fixture_id in enumerate(ORIENTATION_FIXTURES, start=1):
        if indexed[fixture_id]["exif_orientation"] != str(orientation):
            raise RuntimeError(f"Fixture {fixture_id} failed its EXIF control")
    if indexed["cmyk_adobe0"]["adobe_transform"] != "0":
        raise RuntimeError("CMYK fixture does not declare Adobe transform 0")
    if indexed["ycck_adobe2"]["adobe_transform"] != "2":
        raise RuntimeError("YCCK fixture does not declare Adobe transform 2")
    if any(
        int(row["component_count"]) != 3
        for row in rows
        if row["source_mode"] == "BGR"
    ):
        raise RuntimeError("An RGB control does not contain three components")
    if any(
        int(row["component_count"]) != 4
        for row in rows
        if row["source_mode"] == "CMYK"
    ):
        raise RuntimeError("A four-component control has the wrong component count")


def load_and_validate_fixtures(
    fixture_dir: Path,
) -> list[dict[str, str]]:
    """Load and validate committed streams, references, and metadata."""
    manifest_path = fixture_dir / FIXTURE_MANIFEST_NAME
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"fixture manifest not found: {manifest_path.as_posix()}"
        )
    rows = read_csv(manifest_path)
    sources = make_color_sources()
    for row in rows:
        jpeg_bytes = (fixture_dir / row["jpeg_file"]).read_bytes()
        png_bytes = (fixture_dir / row["reference_png_file"]).read_bytes()
        reference = decode_png(png_bytes)
        structure = parse_jpeg_structure(jpeg_bytes)
        metadata = inspect_jpeg_metadata(jpeg_bytes)
        checks = {
            "source_pixels_sha256": source_array_sha256(
                sources[row["source_mode"]]
            ),
            "jpeg_sha256": bytes_sha256(jpeg_bytes),
            "jpeg_core_sha256": bytes_sha256(
                strip_jpeg_interpretation_metadata(jpeg_bytes)
            ),
            "jpeg_size_bytes": str(len(jpeg_bytes)),
            "reference_bgr_sha256": pixel_array_sha256(reference),
            "reference_png_sha256": bytes_sha256(png_bytes),
            "width": str(structure.width),
            "height": str(structure.height),
            "component_count": str(len(structure.components)),
            "component_signature": structure.component_signature,
            "quantization_fingerprint": structure.quantization_fingerprint,
            "exif_orientation": (
                "none"
                if metadata.exif_orientation is None
                else str(metadata.exif_orientation)
            ),
            "icc_profile_length": str(metadata.icc_profile_length),
            "icc_profile_sha256": metadata.icc_profile_sha256,
            "icc_chunk_count": str(metadata.icc_chunk_count),
            "adobe_transform": (
                "none"
                if metadata.adobe_transform is None
                else str(metadata.adobe_transform)
            ),
        }
        for field, observed in checks.items():
            if row[field] != observed:
                raise RuntimeError(
                    f"Fixture {row['fixture_id']} failed {field} validation"
                )
    validate_fixture_controls(rows)
    return sorted(rows, key=lambda row: row["fixture_id"])


def build_platform_manifest(
    platform_label: str, *, record_runner_image: bool = False
) -> list[dict[str, str]]:
    """Record codec and color-engine provenance without executable paths."""
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
    littlecms_version = features.version("littlecms2")
    if littlecms_version is None:
        raise RuntimeError("Pillow does not report a LittleCMS build")
    definitions = (
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
        (
            "pillow_imagecms",
            "color_management_module",
            "Pillow ImageCms",
            PIL.__version__,
            "LittleCMS",
            f"LittleCMS {littlecms_version}",
            bytes_sha256(f"LittleCMS {littlecms_version}".encode("utf-8")),
        ),
    )
    return [
        {
            **common,
            "component": name,
            "component_role": role,
            "adapter": adapter,
            "adapter_version": adapter_version,
            "implementation_family": implementation,
            "reported_backend": reported,
            "build_fingerprint": fingerprint,
        }
        for (
            name,
            role,
            adapter,
            adapter_version,
            implementation,
            reported,
            fingerprint,
        ) in definitions
    ]


def comparison_fields(
    reference: NDArray[np.uint8], candidate: NDArray[np.uint8]
) -> dict[str, str]:
    """Return stable pixel-difference fields for equally shaped arrays."""
    shape_contract = candidate.shape == reference.shape
    dtype_contract = candidate.dtype == np.uint8
    if not shape_contract or not dtype_contract:
        return {
            "shape_contract": str(int(shape_contract)),
            "dtype_contract": str(int(dtype_contract)),
            "exact_pixels": "0",
            "within_one_code_value": "0",
            "reference_bgr_sha256": pixel_array_sha256(reference),
            "candidate_bgr_sha256": pixel_array_sha256(candidate),
            "mean_absolute_error": "nan",
            "maximum_absolute_error": "nan",
            "changed_sample_fraction": "nan",
            "changed_pixel_fraction": "nan",
        }
    difference = compare_decoded_pixels(reference, candidate)
    return {
        "shape_contract": "1",
        "dtype_contract": "1",
        "exact_pixels": str(int(difference.exact)),
        "within_one_code_value": str(
            int(difference.maximum_absolute_error <= 1)
        ),
        "reference_bgr_sha256": difference.reference_sha256,
        "candidate_bgr_sha256": difference.candidate_sha256,
        "mean_absolute_error": f"{difference.mean_absolute_error:.9f}",
        "maximum_absolute_error": str(difference.maximum_absolute_error),
        "changed_sample_fraction": (
            f"{difference.changed_sample_fraction:.9f}"
        ),
        "changed_pixel_fraction": f"{difference.changed_pixel_fraction:.9f}",
    }


def observe_raw_decoders(
    fixture_dir: Path,
    fixtures: Sequence[dict[str, str]],
    platform_label: str,
) -> tuple[
    list[dict[str, str]],
    dict[str, dict[str, NDArray[np.uint8]]],
]:
    """Observe three raw decode adapters on every committed fixture."""
    rows: list[dict[str, str]] = []
    decoded: dict[str, dict[str, NDArray[np.uint8]]] = {}
    for fixture in fixtures:
        jpeg_bytes = (fixture_dir / fixture["jpeg_file"]).read_bytes()
        reference = decode_png(
            (fixture_dir / fixture["reference_png_file"]).read_bytes()
        )
        decoded[fixture["fixture_id"]] = {}
        for decoder, adapter in RAW_DECODERS.items():
            image = adapter(jpeg_bytes)
            decoded[fixture["fixture_id"]][decoder] = image
            rows.append(
                {
                    "platform_label": platform_label,
                    "fixture_id": fixture["fixture_id"],
                    "fixture_family": fixture["fixture_family"],
                    "metadata_control": fixture["metadata_control"],
                    "decoder": decoder,
                    "decode_policy": "raw_ignore_orientation_no_icc_transform",
                    "jpeg_sha256": fixture["jpeg_sha256"],
                    "jpeg_core_sha256": fixture["jpeg_core_sha256"],
                    "exif_orientation": fixture["exif_orientation"],
                    "icc_profile_sha256": fixture["icc_profile_sha256"],
                    "adobe_transform": fixture["adobe_transform"],
                    **comparison_fields(reference, image),
                }
            )
    return rows, decoded


def observe_interpretation_policies(
    fixture_dir: Path,
    fixtures: Sequence[dict[str, str]],
    raw: dict[str, dict[str, NDArray[np.uint8]]],
    platform_label: str,
) -> list[dict[str, str]]:
    """Apply explicit ICC, EXIF orientation, and four-channel policies."""
    rows: list[dict[str, str]] = []
    fixture_by_id = {row["fixture_id"]: row for row in fixtures}

    icc_reference = raw["rgb_untagged"]["pillow"]
    for fixture_id in ICC_FIXTURES:
        jpeg_bytes = (fixture_dir / fixture_by_id[fixture_id]["jpeg_file"]).read_bytes()
        policies = {
            "pillow_unmanaged": decode_jpeg_pillow(jpeg_bytes),
            "icc_to_srgb_relative": decode_jpeg_pillow_color_managed(
                jpeg_bytes
            ),
        }
        for policy, image in policies.items():
            rows.append(
                {
                    "platform_label": platform_label,
                    "fixture_id": fixture_id,
                    "fixture_family": "icc_profile",
                    "policy": policy,
                    "reference_policy": "untagged_pillow_unmanaged",
                    "metadata_control": fixture_by_id[fixture_id][
                        "metadata_control"
                    ],
                    **comparison_fields(icc_reference, image),
                }
            )

    opencv_orientation_reference = raw["rgb_orientation_1"]["opencv"]
    pillow_orientation_reference = raw["rgb_orientation_1"]["pillow"]
    for orientation, fixture_id in enumerate(ORIENTATION_FIXTURES, start=1):
        fixture = fixture_by_id[fixture_id]
        jpeg_bytes = (fixture_dir / fixture["jpeg_file"]).read_bytes()
        opencv_oriented_reference = apply_exif_orientation_bgr(
            opencv_orientation_reference, orientation
        )
        pillow_oriented_reference = apply_exif_orientation_bgr(
            pillow_orientation_reference, orientation
        )
        policies = (
            (
                "opencv_ignore_orientation",
                "opencv_raw_unoriented_pixels",
                opencv_orientation_reference,
                decode_jpeg_opencv(jpeg_bytes, ignore_orientation=True),
            ),
            (
                "opencv_apply_orientation",
                "opencv_orientation_normalized_pixels",
                opencv_oriented_reference,
                decode_jpeg_opencv(jpeg_bytes),
            ),
            (
                "pillow_ignore_orientation",
                "pillow_raw_unoriented_pixels",
                pillow_orientation_reference,
                decode_jpeg_pillow(jpeg_bytes),
            ),
            (
                "pillow_exif_transpose",
                "pillow_orientation_normalized_pixels",
                pillow_oriented_reference,
                decode_jpeg_pillow_oriented(jpeg_bytes),
            ),
        )
        for policy, reference_policy, reference, image in policies:
            rows.append(
                {
                    "platform_label": platform_label,
                    "fixture_id": fixture_id,
                    "fixture_family": "exif_orientation",
                    "policy": policy,
                    "reference_policy": reference_policy,
                    "metadata_control": fixture["metadata_control"],
                    **comparison_fields(reference, image),
                }
            )

    arithmetic_reference = cmyk_to_bgr_arithmetic(
        make_color_sources()["CMYK"]
    )
    for fixture_id in FOUR_COMPONENT_FIXTURES:
        fixture = fixture_by_id[fixture_id]
        for decoder in RAW_DECODERS:
            rows.append(
                {
                    "platform_label": platform_label,
                    "fixture_id": fixture_id,
                    "fixture_family": "four_component_color",
                    "policy": f"{decoder}_rendered_bgr",
                    "reference_policy": "source_cmyk_arithmetic_preview",
                    "metadata_control": fixture["metadata_control"],
                    **comparison_fields(
                        arithmetic_reference, raw[fixture_id][decoder]
                    ),
                }
            )
    return rows


def build_control_pairs(
    fixtures: Sequence[dict[str, str]],
    raw: dict[str, dict[str, NDArray[np.uint8]]],
    fixture_dir: Path,
    platform_label: str,
) -> list[dict[str, str]]:
    """Compare metadata-only controls and equivalent color intentions."""
    fixture_by_id = {row["fixture_id"]: row for row in fixtures}
    definitions: list[
        tuple[str, str, str, str, NDArray[np.uint8], NDArray[np.uint8]]
    ] = []
    for candidate in ICC_FIXTURES[1:]:
        for decoder in RAW_DECODERS:
            definitions.append(
                (
                    "icc_raw_metadata_invariance",
                    "rgb_untagged",
                    candidate,
                    decoder,
                    raw["rgb_untagged"][decoder],
                    raw[candidate][decoder],
                )
            )
    gamma_1_bytes = (
        fixture_dir / fixture_by_id["rgb_icc_gamma_1_0"]["jpeg_file"]
    ).read_bytes()
    gamma_2_bytes = (
        fixture_dir / fixture_by_id["rgb_icc_gamma_2_2"]["jpeg_file"]
    ).read_bytes()
    definitions.append(
        (
            "icc_managed_profile_response",
            "rgb_icc_gamma_1_0",
            "rgb_icc_gamma_2_2",
            "pillow_imagecms",
            decode_jpeg_pillow_color_managed(gamma_1_bytes),
            decode_jpeg_pillow_color_managed(gamma_2_bytes),
        )
    )
    for candidate in ORIENTATION_FIXTURES[1:]:
        for decoder in RAW_DECODERS:
            definitions.append(
                (
                    "exif_raw_metadata_invariance",
                    "rgb_orientation_1",
                    candidate,
                    decoder,
                    raw["rgb_orientation_1"][decoder],
                    raw[candidate][decoder],
                )
            )
    for decoder in RAW_DECODERS:
        definitions.append(
            (
                "cmyk_ycck_rendered_equivalence",
                "cmyk_adobe0",
                "ycck_adobe2",
                decoder,
                raw["cmyk_adobe0"][decoder],
                raw["ycck_adobe2"][decoder],
            )
        )

    rows: list[dict[str, str]] = []
    for (
        control_id,
        reference_fixture,
        candidate_fixture,
        adapter,
        reference,
        candidate,
    ) in definitions:
        reference_manifest = fixture_by_id[reference_fixture]
        candidate_manifest = fixture_by_id[candidate_fixture]
        rows.append(
            {
                "platform_label": platform_label,
                "control_id": control_id,
                "reference_fixture": reference_fixture,
                "candidate_fixture": candidate_fixture,
                "adapter": adapter,
                "compressed_core_equal": str(
                    int(
                        reference_manifest["jpeg_core_sha256"]
                        == candidate_manifest["jpeg_core_sha256"]
                    )
                ),
                **comparison_fields(reference, candidate),
            }
        )
    return rows


def summarize_results(
    raw_rows: Sequence[dict[str, str]],
    policy_rows: Sequence[dict[str, str]],
    control_rows: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Create concise aggregates for documentation and plotting."""
    groups: list[tuple[str, str, str, list[dict[str, str]]]] = []
    for fixture_id in ICC_FIXTURES:
        for policy in ("pillow_unmanaged", "icc_to_srgb_relative"):
            groups.append(
                (
                    "icc_policy",
                    fixture_id,
                    policy,
                    [
                        row
                        for row in policy_rows
                        if row["fixture_id"] == fixture_id
                        and row["policy"] == policy
                    ],
                )
            )
    for policy in (
        "opencv_ignore_orientation",
        "opencv_apply_orientation",
        "pillow_ignore_orientation",
        "pillow_exif_transpose",
    ):
        groups.append(
            (
                "orientation_policy",
                "orientations_1_to_8",
                policy,
                [row for row in policy_rows if row["policy"] == policy],
            )
        )
    for family in ("icc_profile", "exif_orientation"):
        for decoder in RAW_DECODERS:
            member_rows = [
                row
                for row in raw_rows
                if row["fixture_family"] == family
                and row["decoder"] == decoder
            ]
            groups.append(
                ("raw_metadata_invariance", family, decoder, member_rows)
            )
    for fixture_id in FOUR_COMPONENT_FIXTURES:
        for decoder in RAW_DECODERS:
            groups.append(
                (
                    "four_component_rendering",
                    fixture_id,
                    decoder,
                    [
                        row
                        for row in policy_rows
                        if row["fixture_id"] == fixture_id
                        and row["policy"] == f"{decoder}_rendered_bgr"
                    ],
                )
            )

    rows: list[dict[str, str]] = []
    for category, subject, adapter, group in groups:
        if not group:
            raise RuntimeError(f"Empty summary group: {category}/{subject}")
        finite_mean = [
            float(row["mean_absolute_error"])
            for row in group
            if row["mean_absolute_error"] != "nan"
        ]
        finite_max = [
            int(row["maximum_absolute_error"])
            for row in group
            if row["maximum_absolute_error"] != "nan"
        ]
        rows.append(
            {
                "platform_label": group[0]["platform_label"],
                "category": category,
                "subject": subject,
                "adapter_or_policy": adapter,
                "observations": str(len(group)),
                "shape_contract_rate": (
                    f"{np.mean([int(row['shape_contract']) for row in group]):.6f}"
                ),
                "dtype_contract_rate": (
                    f"{np.mean([int(row['dtype_contract']) for row in group]):.6f}"
                ),
                "exact_pixel_rate": (
                    f"{np.mean([int(row['exact_pixels']) for row in group]):.6f}"
                ),
                "mean_absolute_error_mean": (
                    f"{np.mean(finite_mean):.9f}" if finite_mean else "nan"
                ),
                "maximum_absolute_error_max": (
                    str(max(finite_max)) if finite_max else "nan"
                ),
                "unique_candidate_hashes": str(
                    len({row["candidate_bgr_sha256"] for row in group})
                ),
            }
        )

    cmyk_ycck = [
        row
        for row in control_rows
        if row["control_id"] == "cmyk_ycck_rendered_equivalence"
    ]
    if len(cmyk_ycck) != len(RAW_DECODERS):
        raise RuntimeError("Missing CMYK/YCCK control comparisons")
    return rows


def validate_outputs(
    raw_rows: Sequence[dict[str, str]],
    policy_rows: Sequence[dict[str, str]],
    control_rows: Sequence[dict[str, str]],
    summary_rows: Sequence[dict[str, str]],
) -> None:
    """Validate coverage and controlled interpretation relationships."""
    if len(raw_rows) != len(FIXTURE_IDS) * len(RAW_DECODERS):
        raise RuntimeError("Unexpected raw decoder observation count")
    if len(policy_rows) != 44:
        raise RuntimeError("Unexpected interpretation policy observation count")
    if len(control_rows) != 31:
        raise RuntimeError("Unexpected control-pair observation count")
    if len(summary_rows) != 22:
        raise RuntimeError("Unexpected summary row count")
    if not all(
        row["shape_contract"] == "1" and row["dtype_contract"] == "1"
        for row in (*raw_rows, *policy_rows, *control_rows)
    ):
        raise RuntimeError("A decoded-pixel interface contract failed")
    raw_invariance = [
        row
        for row in control_rows
        if row["control_id"]
        in {"icc_raw_metadata_invariance", "exif_raw_metadata_invariance"}
    ]
    if not all(
        row["compressed_core_equal"] == "1"
        and row["exact_pixels"] == "1"
        for row in raw_invariance
    ):
        raise RuntimeError("A metadata-only raw decode invariant failed")
    normalized_orientation = [
        row
        for row in policy_rows
        if row["policy"]
        in {"opencv_apply_orientation", "pillow_exif_transpose"}
    ]
    if not all(row["exact_pixels"] == "1" for row in normalized_orientation):
        raise RuntimeError("An orientation normalization contract failed")
    managed_gamma = [
        row
        for row in policy_rows
        if row["fixture_id"].startswith("rgb_icc_gamma_")
        and row["policy"] == "icc_to_srgb_relative"
    ]
    if not all(row["exact_pixels"] == "0" for row in managed_gamma):
        raise RuntimeError("ICC controls did not produce a managed response")


def plot_results(
    raw_rows: Sequence[dict[str, str]],
    policy_rows: Sequence[dict[str, str]],
    control_rows: Sequence[dict[str, str]],
    output_path: Path,
) -> None:
    """Visualize interpretation-policy responses without quality thresholds."""
    figure, axes = plt.subplots(2, 2, figsize=(13, 9), constrained_layout=True)

    icc_ids = ICC_FIXTURES[1:]
    icc_labels = ("gamma 1.0", "gamma 2.2")
    icc_rows = [
        next(
            row
            for row in policy_rows
            if row["fixture_id"] == fixture_id
            and row["policy"] == "icc_to_srgb_relative"
        )
        for fixture_id in icc_ids
    ]
    axes[0, 0].bar(
        icc_labels,
        [float(row["mean_absolute_error"]) for row in icc_rows],
        color=("#3569a8", "#78a9dc"),
    )
    for index, row in enumerate(icc_rows):
        axes[0, 0].text(
            index,
            float(row["mean_absolute_error"]),
            f"max {row['maximum_absolute_error']}",
            ha="center",
            va="bottom",
        )
    axes[0, 0].set_title("ICC-managed response from identical JPEG scans")
    axes[0, 0].set_ylabel("Mean absolute code-value difference")

    orientation_policies = (
        "opencv_ignore_orientation",
        "opencv_apply_orientation",
        "pillow_ignore_orientation",
        "pillow_exif_transpose",
    )
    exact_rates = [
        np.mean(
            [
                int(row["exact_pixels"])
                for row in policy_rows
                if row["policy"] == policy
            ]
        )
        for policy in orientation_policies
    ]
    axes[0, 1].barh(
        range(len(orientation_policies)), exact_rates, color="#4c956c"
    )
    axes[0, 1].set_yticks(
        range(len(orientation_policies)), orientation_policies
    )
    axes[0, 1].set_xlim(0, 1.05)
    axes[0, 1].set_title("EXIF orientation policy exactness")
    axes[0, 1].set_xlabel("Exact contract rate across orientations 1-8")

    family_names = ("icc_profile", "exif_orientation")
    raw_hash_counts = np.array(
        [
            [
                len(
                    {
                        row["candidate_bgr_sha256"]
                        for row in raw_rows
                        if row["fixture_family"] == family
                        and row["decoder"] == decoder
                    }
                )
                for decoder in RAW_DECODERS
            ]
            for family in family_names
        ],
        dtype=np.float64,
    )
    image = axes[1, 0].imshow(
        raw_hash_counts, aspect="auto", cmap="Blues", vmin=1
    )
    axes[1, 0].set_xticks(range(3), tuple(RAW_DECODERS))
    axes[1, 0].set_yticks(range(2), ("ICC tags", "EXIF orientation"))
    axes[1, 0].set_title("Unique raw decoded hashes per metadata family")
    for row_index in range(2):
        for column_index in range(3):
            axes[1, 0].text(
                column_index,
                row_index,
                f"{raw_hash_counts[row_index, column_index]:.0f}",
                ha="center",
                va="center",
            )
    figure.colorbar(image, ax=axes[1, 0], shrink=0.75)

    pair_rows = {
        row["adapter"]: row
        for row in control_rows
        if row["control_id"] == "cmyk_ycck_rendered_equivalence"
    }
    decoders = tuple(RAW_DECODERS)
    x = np.arange(len(decoders))
    mean_values = [float(pair_rows[name]["mean_absolute_error"]) for name in decoders]
    maximum_values = [
        int(pair_rows[name]["maximum_absolute_error"])
        for name in decoders
    ]
    axes[1, 1].bar(x, mean_values, color="#d88c46")
    for index, maximum in enumerate(maximum_values):
        axes[1, 1].text(
            index,
            mean_values[index],
            f"max {maximum}",
            ha="center",
            va="bottom",
        )
    axes[1, 1].set_xticks(x, decoders)
    axes[1, 1].set_title("CMYK versus YCCK rendered output")
    axes[1, 1].set_ylabel("Mean absolute code-value difference")

    figure.suptitle("Color management, YCCK, and metadata interpretation")
    figure.savefig(output_path, dpi=160)
    plt.close(figure)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate controlled JPEG color and orientation metadata "
            "interpretation policies."
        )
    )
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=Path("fixtures/color-metadata-contracts"),
        help="Directory containing the fixed color-metadata corpus.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results"),
        help="Directory for CSV and PNG outputs.",
    )
    parser.add_argument(
        "--platform-label",
        default="linux-x64-reference",
        help="Stable label for the current platform observation.",
    )
    parser.add_argument(
        "--refresh-fixtures",
        action="store_true",
        help="Regenerate the synthetic JPEG and PNG fixture corpus.",
    )
    parser.add_argument(
        "--record-runner-image",
        action="store_true",
        help="Record GitHub-hosted runner image metadata when available.",
    )
    return parser.parse_args()


def main() -> None:
    """Generate or validate fixtures, execute policies, and write reports."""
    args = parse_args()
    if args.refresh_fixtures:
        refresh_fixtures(args.fixture_dir)
    fixtures = load_and_validate_fixtures(args.fixture_dir)
    platform_rows = build_platform_manifest(
        args.platform_label,
        record_runner_image=args.record_runner_image,
    )
    raw_rows, decoded = observe_raw_decoders(
        args.fixture_dir, fixtures, args.platform_label
    )
    policy_rows = observe_interpretation_policies(
        args.fixture_dir, fixtures, decoded, args.platform_label
    )
    control_rows = build_control_pairs(
        fixtures, decoded, args.fixture_dir, args.platform_label
    )
    summary_rows = summarize_results(raw_rows, policy_rows, control_rows)
    validate_outputs(raw_rows, policy_rows, control_rows, summary_rows)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / PLATFORM_MANIFEST_NAME, platform_rows)
    write_csv(args.output_dir / RAW_OBSERVATIONS_NAME, raw_rows)
    write_csv(args.output_dir / POLICY_OBSERVATIONS_NAME, policy_rows)
    write_csv(args.output_dir / CONTROL_PAIRS_NAME, control_rows)
    write_csv(args.output_dir / SUMMARY_NAME, summary_rows)
    plot_results(
        raw_rows,
        policy_rows,
        control_rows,
        args.output_dir / FIGURE_NAME,
    )
    print(
        "JPEG metadata interpretation evaluation complete: "
        f"{len(fixtures)} fixtures, {len(raw_rows)} raw observations, "
        f"{len(policy_rows)} policy observations, and "
        f"{len(control_rows)} control pairs. Results written to "
        f"{args.output_dir.as_posix()}."
    )


if __name__ == "__main__":
    main()
