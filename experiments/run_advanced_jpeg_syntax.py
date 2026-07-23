"""Evaluate independent decoder families on advanced synthetic JPEG syntax."""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import platform
import sys
from collections.abc import Callable, Sequence
from itertools import combinations
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
    classify_decoded_pixel_contract,
    compare_decoded_pixels,
    decode_jpeg_ffmpeg,
    decode_jpeg_opencv,
    decode_jpeg_pillow,
    encode_jpeg_cmyk_pillow,
    encode_jpeg_opencv,
    encode_jpeg_pillow,
    ffmpeg_build_information,
    inspect_jpeg_syntax,
    laplacian_variance,
    parse_jpeg_structure,
    pixel_array_sha256,
    tenengrad_energy,
    to_grayscale,
)


IMAGE_SIZE = 128
QUALITY = 75
RESTART_INTERVAL = 4
DECODERS: dict[str, Callable[[bytes], NDArray[np.uint8]]] = {
    "opencv": decode_jpeg_opencv,
    "pillow": decode_jpeg_pillow,
    "ffmpeg": decode_jpeg_ffmpeg,
}

FIXTURE_MANIFEST_NAME = "manifest.csv"
PLATFORM_MANIFEST_NAME = "jpeg_advanced_codec_manifest.csv"
OBSERVATIONS_NAME = "jpeg_advanced_decoder_observations.csv"
PAIRWISE_NAME = "jpeg_advanced_pairwise_differences.csv"
SYNTAX_EQUIVALENCE_NAME = "jpeg_advanced_syntax_equivalence.csv"
SUMMARY_NAME = "jpeg_advanced_summary.csv"
FIGURE_NAME = "jpeg_advanced_codec_families.png"

FIXTURE_IDS = (
    "cmyk_baseline",
    "cmyk_progressive",
    "grayscale_baseline",
    "grayscale_progressive",
    "rgb_baseline_420",
    "rgb_baseline_444",
    "rgb_progressive_420",
    "rgb_progressive_444",
    "rgb_progressive_restart_420",
    "rgb_restart_420",
)

CONTROLLED_SYNTAX_PAIRS = (
    ("rgb_444_progression", "rgb_baseline_444", "rgb_progressive_444"),
    ("rgb_420_restart", "rgb_baseline_420", "rgb_restart_420"),
    (
        "rgb_420_progressive_restart",
        "rgb_progressive_420",
        "rgb_progressive_restart_420",
    ),
    (
        "grayscale_progression",
        "grayscale_baseline",
        "grayscale_progressive",
    ),
    ("cmyk_progression", "cmyk_baseline", "cmyk_progressive"),
)

FIXTURE_FIELDS = (
    "fixture_id",
    "syntax_class",
    "source_mode",
    "quality_control",
    "chroma_sampling",
    "progressive_control",
    "restart_interval_control",
    "jpeg_file",
    "reference_png_file",
    "source_pixels_sha256",
    "jpeg_sha256",
    "jpeg_size_bytes",
    "reference_bgr_sha256",
    "reference_png_sha256",
    "width",
    "height",
    "frame_marker",
    "frame_process",
    "precision_bits",
    "component_count",
    "component_signature",
    "quantization_fingerprint",
    "scan_count",
    "restart_interval",
    "restart_marker_count",
    "jfif_present",
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
    """Write deterministic CSV rows with explicit ordering."""
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


def make_advanced_sources() -> dict[str, NDArray[np.uint8]]:
    """Create deterministic BGR, grayscale, and CMYK synthetic arrays."""
    rows, columns = np.indices((IMAGE_SIZE, IMAGE_SIZE))
    horizontal = columns.astype(np.float64) / (IMAGE_SIZE - 1)
    vertical = rows.astype(np.float64) / (IMAGE_SIZE - 1)
    bgr = np.stack(
        (
            18.0 + 218.0 * horizontal,
            26.0 + 188.0 * vertical,
            236.0 - 98.0 * horizontal - 82.0 * vertical,
        ),
        axis=2,
    )
    bgr = np.clip(np.rint(bgr), 0, 255).astype(np.uint8)
    tile_mask = ((rows // 8 + columns // 8) % 2) == 0
    bgr[tile_mask] = np.clip(
        bgr[tile_mask].astype(np.int16) + np.array([18, -14, 22]),
        0,
        255,
    ).astype(np.uint8)
    cv2.circle(bgr, (35, 39), 20, (220, 30, 235), -1)
    cv2.rectangle(bgr, (70, 19), (113, 68), (28, 225, 48), -1)
    cv2.line(bgr, (9, 116), (119, 82), (242, 220, 24), 5)
    grayscale = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    cmyk = np.stack(
        (
            np.rint(230.0 * horizontal),
            np.rint(230.0 * vertical),
            np.where(tile_mask, 38.0, 208.0),
            np.rint(18.0 + 92.0 * (horizontal + vertical) / 2.0),
        ),
        axis=2,
    ).astype(np.uint8)
    return {"BGR": bgr, "L": grayscale, "CMYK": cmyk}


def opencv_jpeg_backend() -> str:
    """Return the JPEG backend line reported by the OpenCV build."""
    matches = [
        line.strip()
        for line in cv2.getBuildInformation().splitlines()
        if line.strip().startswith("JPEG:")
    ]
    if len(matches) != 1:
        raise RuntimeError("Could not identify the OpenCV JPEG backend")
    return matches[0].split(":", maxsplit=1)[1].strip()


def pillow_jpeg_backend() -> str:
    """Return the JPEG backend reported by Pillow features."""
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
    """Encode a BGR reference as a deterministic lossless PNG."""
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
    """Build all declared advanced-syntax JPEG byte streams."""
    sources = make_advanced_sources()
    bgr = sources["BGR"]
    grayscale = sources["L"]
    cmyk = sources["CMYK"]
    return [
        {
            "fixture_id": "rgb_baseline_420",
            "syntax_class": "baseline_rgb_420",
            "source_mode": "BGR",
            "chroma_sampling": "420",
            "progressive_control": "0",
            "restart_interval_control": "0",
            "generator_adapter": "opencv",
            "jpeg_bytes": encode_jpeg_opencv(
                bgr, quality=QUALITY, chroma_sampling="420"
            ),
        },
        {
            "fixture_id": "rgb_baseline_444",
            "syntax_class": "baseline_rgb",
            "source_mode": "BGR",
            "chroma_sampling": "444",
            "progressive_control": "0",
            "restart_interval_control": "0",
            "generator_adapter": "opencv",
            "jpeg_bytes": encode_jpeg_opencv(
                bgr, quality=QUALITY, chroma_sampling="444"
            ),
        },
        {
            "fixture_id": "rgb_progressive_420",
            "syntax_class": "progressive_rgb_420",
            "source_mode": "BGR",
            "chroma_sampling": "420",
            "progressive_control": "1",
            "restart_interval_control": "0",
            "generator_adapter": "pillow",
            "jpeg_bytes": encode_jpeg_pillow(
                bgr,
                quality=QUALITY,
                chroma_sampling="420",
                progressive=True,
            ),
        },
        {
            "fixture_id": "rgb_progressive_444",
            "syntax_class": "progressive_rgb",
            "source_mode": "BGR",
            "chroma_sampling": "444",
            "progressive_control": "1",
            "restart_interval_control": "0",
            "generator_adapter": "opencv",
            "jpeg_bytes": encode_jpeg_opencv(
                bgr,
                quality=QUALITY,
                chroma_sampling="444",
                progressive=True,
            ),
        },
        {
            "fixture_id": "rgb_restart_420",
            "syntax_class": "restart_rgb",
            "source_mode": "BGR",
            "chroma_sampling": "420",
            "progressive_control": "0",
            "restart_interval_control": str(RESTART_INTERVAL),
            "generator_adapter": "opencv",
            "jpeg_bytes": encode_jpeg_opencv(
                bgr,
                quality=QUALITY,
                chroma_sampling="420",
                restart_interval=RESTART_INTERVAL,
            ),
        },
        {
            "fixture_id": "rgb_progressive_restart_420",
            "syntax_class": "progressive_restart_rgb",
            "source_mode": "BGR",
            "chroma_sampling": "420",
            "progressive_control": "1",
            "restart_interval_control": str(RESTART_INTERVAL),
            "generator_adapter": "pillow",
            "jpeg_bytes": encode_jpeg_pillow(
                bgr,
                quality=QUALITY,
                chroma_sampling="420",
                progressive=True,
                restart_interval=RESTART_INTERVAL,
            ),
        },
        {
            "fixture_id": "grayscale_baseline",
            "syntax_class": "baseline_grayscale",
            "source_mode": "L",
            "chroma_sampling": "grayscale",
            "progressive_control": "0",
            "restart_interval_control": "0",
            "generator_adapter": "opencv",
            "jpeg_bytes": encode_jpeg_opencv(grayscale, quality=QUALITY),
        },
        {
            "fixture_id": "grayscale_progressive",
            "syntax_class": "progressive_grayscale",
            "source_mode": "L",
            "chroma_sampling": "grayscale",
            "progressive_control": "1",
            "restart_interval_control": "0",
            "generator_adapter": "pillow",
            "jpeg_bytes": encode_jpeg_pillow(
                grayscale, quality=QUALITY, progressive=True
            ),
        },
        {
            "fixture_id": "cmyk_baseline",
            "syntax_class": "baseline_cmyk",
            "source_mode": "CMYK",
            "chroma_sampling": "cmyk",
            "progressive_control": "0",
            "restart_interval_control": "0",
            "generator_adapter": "pillow_cmyk",
            "jpeg_bytes": encode_jpeg_cmyk_pillow(cmyk, quality=QUALITY),
        },
        {
            "fixture_id": "cmyk_progressive",
            "syntax_class": "progressive_cmyk",
            "source_mode": "CMYK",
            "chroma_sampling": "cmyk",
            "progressive_control": "1",
            "restart_interval_control": "0",
            "generator_adapter": "pillow_cmyk",
            "jpeg_bytes": encode_jpeg_cmyk_pillow(
                cmyk, quality=QUALITY, progressive=True
            ),
        },
    ]


def refresh_fixtures(fixture_dir: Path) -> list[dict[str, str]]:
    """Generate the fixed advanced-syntax corpus and BGR references."""
    fixture_dir.mkdir(parents=True, exist_ok=True)
    sources = make_advanced_sources()
    rows: list[dict[str, str]] = []
    opencv_backend = opencv_jpeg_backend()
    pillow_backend = pillow_jpeg_backend()
    for payload in fixture_payloads():
        fixture_id = str(payload["fixture_id"])
        jpeg_bytes = payload["jpeg_bytes"]
        if not isinstance(jpeg_bytes, bytes):
            raise TypeError("fixture JPEG payload must be bytes")
        jpeg_name = f"{fixture_id}.jpg"
        reference_name = f"{fixture_id}.reference.png"
        structure = parse_jpeg_structure(jpeg_bytes)
        syntax = inspect_jpeg_syntax(jpeg_bytes)
        reference = decode_jpeg_opencv(jpeg_bytes)
        png_bytes = encode_png(reference)
        (fixture_dir / jpeg_name).write_bytes(jpeg_bytes)
        (fixture_dir / reference_name).write_bytes(png_bytes)
        generator_adapter = str(payload["generator_adapter"])
        uses_opencv = generator_adapter == "opencv"
        rows.append(
            {
                "fixture_id": fixture_id,
                "syntax_class": str(payload["syntax_class"]),
                "source_mode": str(payload["source_mode"]),
                "quality_control": str(QUALITY),
                "chroma_sampling": str(payload["chroma_sampling"]),
                "progressive_control": str(payload["progressive_control"]),
                "restart_interval_control": str(
                    payload["restart_interval_control"]
                ),
                "jpeg_file": jpeg_name,
                "reference_png_file": reference_name,
                "source_pixels_sha256": source_array_sha256(
                    sources[str(payload["source_mode"])]
                ),
                "jpeg_sha256": bytes_sha256(jpeg_bytes),
                "jpeg_size_bytes": str(len(jpeg_bytes)),
                "reference_bgr_sha256": pixel_array_sha256(reference),
                "reference_png_sha256": bytes_sha256(png_bytes),
                "width": str(structure.width),
                "height": str(structure.height),
                "frame_marker": f"0x{structure.frame_marker:02x}",
                "frame_process": syntax.frame_process,
                "precision_bits": str(structure.precision_bits),
                "component_count": str(len(structure.components)),
                "component_signature": structure.component_signature,
                "quantization_fingerprint": (
                    structure.quantization_fingerprint
                ),
                "scan_count": str(syntax.scan_count),
                "restart_interval": str(syntax.restart_interval),
                "restart_marker_count": str(syntax.restart_marker_count),
                "jfif_present": str(int(syntax.jfif_present)),
                "adobe_transform": (
                    "none"
                    if syntax.adobe_transform is None
                    else str(syntax.adobe_transform)
                ),
                "generator_adapter": generator_adapter,
                "generator_wrapper_version": (
                    cv2.__version__ if uses_opencv else PIL.__version__
                ),
                "generator_jpeg_backend": (
                    opencv_backend if uses_opencv else pillow_backend
                ),
                "reference_decoder": "opencv_bgr",
            }
        )
    rows.sort(key=lambda row: row["fixture_id"])
    validate_fixture_syntax(rows)
    write_csv(fixture_dir / FIXTURE_MANIFEST_NAME, rows, FIXTURE_FIELDS)
    return rows


def validate_fixture_syntax(rows: Sequence[dict[str, str]]) -> None:
    """Validate the declared syntax families without pixel assumptions."""
    if {row["fixture_id"] for row in rows} != set(FIXTURE_IDS):
        raise RuntimeError("Fixture manifest does not contain the expected corpus")
    for row in rows:
        progressive = row["progressive_control"] == "1"
        if progressive != (row["frame_process"] == "progressive_dct"):
            raise RuntimeError(
                f"Fixture {row['fixture_id']} failed its frame-process control"
            )
        if progressive != (int(row["scan_count"]) > 1):
            raise RuntimeError(
                f"Fixture {row['fixture_id']} failed its scan-count control"
            )
        restart_control = int(row["restart_interval_control"])
        if int(row["restart_interval"]) != restart_control:
            raise RuntimeError(
                f"Fixture {row['fixture_id']} failed its restart interval"
            )
        if restart_control and int(row["restart_marker_count"]) == 0:
            raise RuntimeError(
                f"Fixture {row['fixture_id']} contains no restart markers"
            )
        expected_components = {"L": 1, "BGR": 3, "CMYK": 4}[
            row["source_mode"]
        ]
        if int(row["component_count"]) != expected_components:
            raise RuntimeError(
                f"Fixture {row['fixture_id']} has an unexpected component count"
            )


def load_and_validate_fixtures(
    fixture_dir: Path,
) -> list[dict[str, str]]:
    """Load and validate the fixed streams, references, and marker reports."""
    manifest_path = fixture_dir / FIXTURE_MANIFEST_NAME
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"fixture manifest not found: {manifest_path.as_posix()}"
        )
    rows = read_csv(manifest_path)
    sources = make_advanced_sources()
    for row in rows:
        jpeg_bytes = (fixture_dir / row["jpeg_file"]).read_bytes()
        png_bytes = (fixture_dir / row["reference_png_file"]).read_bytes()
        reference = decode_png(png_bytes)
        structure = parse_jpeg_structure(jpeg_bytes)
        syntax = inspect_jpeg_syntax(jpeg_bytes)
        checks = {
            "source_pixels_sha256": source_array_sha256(
                sources[row["source_mode"]]
            ),
            "jpeg_sha256": bytes_sha256(jpeg_bytes),
            "jpeg_size_bytes": str(len(jpeg_bytes)),
            "reference_bgr_sha256": pixel_array_sha256(reference),
            "reference_png_sha256": bytes_sha256(png_bytes),
            "width": str(structure.width),
            "height": str(structure.height),
            "frame_marker": f"0x{structure.frame_marker:02x}",
            "frame_process": syntax.frame_process,
            "precision_bits": str(structure.precision_bits),
            "component_count": str(len(structure.components)),
            "component_signature": structure.component_signature,
            "quantization_fingerprint": structure.quantization_fingerprint,
            "scan_count": str(syntax.scan_count),
            "restart_interval": str(syntax.restart_interval),
            "restart_marker_count": str(syntax.restart_marker_count),
            "jfif_present": str(int(syntax.jfif_present)),
            "adobe_transform": (
                "none"
                if syntax.adobe_transform is None
                else str(syntax.adobe_transform)
            ),
        }
        for field, observed in checks.items():
            if row[field] != observed:
                raise RuntimeError(
                    f"Fixture {row['fixture_id']} failed {field} validation"
                )
    validate_fixture_syntax(rows)
    return sorted(rows, key=lambda row: row["fixture_id"])


def build_platform_manifest(
    platform_label: str, *, record_runner_image: bool = False
) -> list[dict[str, str]]:
    """Record platform and codec-family provenance without executable paths."""
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
    return [
        {
            **common,
            "decoder": "opencv",
            "adapter": "OpenCV",
            "adapter_version": cv2.__version__,
            "codec_family": "libjpeg-turbo",
            "reported_backend": opencv_backend,
            "codec_build_fingerprint": bytes_sha256(
                opencv_backend.encode("utf-8")
            ),
        },
        {
            **common,
            "decoder": "pillow",
            "adapter": "Pillow",
            "adapter_version": PIL.__version__,
            "codec_family": "libjpeg-turbo",
            "reported_backend": pillow_backend,
            "codec_build_fingerprint": bytes_sha256(
                pillow_backend.encode("utf-8")
            ),
        },
        {
            **common,
            "decoder": "ffmpeg",
            "adapter": ffmpeg["adapter"],
            "adapter_version": ffmpeg["adapter_version"],
            "codec_family": ffmpeg["codec_family"],
            "reported_backend": f"FFmpeg {ffmpeg['codec_version']} native mjpeg",
            "codec_build_fingerprint": ffmpeg[
                "codec_build_fingerprint"
            ],
        },
    ]


def observe_decoders(
    fixture_dir: Path,
    fixture_rows: Sequence[dict[str, str]],
    platform_label: str,
) -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    """Decode every stream and compare families with references and peers."""
    observations: list[dict[str, str]] = []
    pairwise: list[dict[str, str]] = []
    decoded_by_fixture: dict[
        str, dict[str, NDArray[np.uint8]]
    ] = {}
    fixture_by_id = {row["fixture_id"]: row for row in fixture_rows}
    for fixture in fixture_rows:
        jpeg_bytes = (fixture_dir / fixture["jpeg_file"]).read_bytes()
        reference = decode_png(
            (fixture_dir / fixture["reference_png_file"]).read_bytes()
        )
        decoded = {
            decoder: adapter(jpeg_bytes)
            for decoder, adapter in DECODERS.items()
        }
        decoded_by_fixture[fixture["fixture_id"]] = decoded
        reference_gray = to_grayscale(reference)
        reference_laplacian = laplacian_variance(reference_gray)
        reference_tenengrad = tenengrad_energy(reference_gray)
        for decoder, image in decoded.items():
            difference = compare_decoded_pixels(reference, image)
            grayscale = to_grayscale(image)
            observations.append(
                {
                    "platform_label": platform_label,
                    "fixture_id": fixture["fixture_id"],
                    "syntax_class": fixture["syntax_class"],
                    "source_mode": fixture["source_mode"],
                    "frame_process": fixture["frame_process"],
                    "scan_count": fixture["scan_count"],
                    "restart_interval": fixture["restart_interval"],
                    "restart_marker_count": fixture[
                        "restart_marker_count"
                    ],
                    "component_count": fixture["component_count"],
                    "adobe_transform": fixture["adobe_transform"],
                    "decoder": decoder,
                    "jpeg_sha256": fixture["jpeg_sha256"],
                    "structure_contract": "1",
                    "shape_contract": str(int(image.shape == reference.shape)),
                    "dtype_contract": str(int(image.dtype == np.uint8)),
                    "exact_reference_pixels": str(int(difference.exact)),
                    "within_one_code_value": str(
                        int(difference.maximum_absolute_error <= 1)
                    ),
                    "contract_level": classify_decoded_pixel_contract(
                        difference
                    ),
                    "reference_bgr_sha256": difference.reference_sha256,
                    "decoded_bgr_sha256": difference.candidate_sha256,
                    "mean_absolute_error": (
                        f"{difference.mean_absolute_error:.9f}"
                    ),
                    "maximum_absolute_error": str(
                        difference.maximum_absolute_error
                    ),
                    "changed_sample_fraction": (
                        f"{difference.changed_sample_fraction:.9f}"
                    ),
                    "changed_pixel_fraction": (
                        f"{difference.changed_pixel_fraction:.9f}"
                    ),
                    "laplacian_to_reference_ratio": (
                        f"{laplacian_variance(grayscale) / reference_laplacian:.9f}"
                    ),
                    "tenengrad_to_reference_ratio": (
                        f"{tenengrad_energy(grayscale) / reference_tenengrad:.9f}"
                    ),
                }
            )
        for reference_decoder, candidate_decoder in combinations(DECODERS, 2):
            difference = compare_decoded_pixels(
                decoded[reference_decoder], decoded[candidate_decoder]
            )
            pairwise.append(
                {
                    "platform_label": platform_label,
                    "fixture_id": fixture["fixture_id"],
                    "syntax_class": fixture["syntax_class"],
                    "reference_decoder": reference_decoder,
                    "candidate_decoder": candidate_decoder,
                    "reference_decoded_sha256": difference.reference_sha256,
                    "candidate_decoded_sha256": difference.candidate_sha256,
                    "exact_pixels": str(int(difference.exact)),
                    "within_one_code_value": str(
                        int(difference.maximum_absolute_error <= 1)
                    ),
                    "contract_level": classify_decoded_pixel_contract(
                        difference
                    ),
                    "mean_absolute_error": (
                        f"{difference.mean_absolute_error:.9f}"
                    ),
                    "maximum_absolute_error": str(
                        difference.maximum_absolute_error
                    ),
                    "changed_sample_fraction": (
                        f"{difference.changed_sample_fraction:.9f}"
                    ),
                    "changed_pixel_fraction": (
                        f"{difference.changed_pixel_fraction:.9f}"
                    ),
                }
            )
    syntax_equivalence: list[dict[str, str]] = []
    for control_id, reference_fixture, candidate_fixture in CONTROLLED_SYNTAX_PAIRS:
        for decoder in DECODERS:
            difference = compare_decoded_pixels(
                decoded_by_fixture[reference_fixture][decoder],
                decoded_by_fixture[candidate_fixture][decoder],
            )
            syntax_equivalence.append(
                {
                    "platform_label": platform_label,
                    "control_id": control_id,
                    "reference_fixture": reference_fixture,
                    "candidate_fixture": candidate_fixture,
                    "decoder": decoder,
                    "reference_jpeg_sha256": fixture_by_id[reference_fixture][
                        "jpeg_sha256"
                    ],
                    "candidate_jpeg_sha256": fixture_by_id[candidate_fixture][
                        "jpeg_sha256"
                    ],
                    "exact_pixels": str(int(difference.exact)),
                    "within_one_code_value": str(
                        int(difference.maximum_absolute_error <= 1)
                    ),
                    "contract_level": classify_decoded_pixel_contract(
                        difference
                    ),
                    "mean_absolute_error": (
                        f"{difference.mean_absolute_error:.9f}"
                    ),
                    "maximum_absolute_error": str(
                        difference.maximum_absolute_error
                    ),
                    "changed_sample_fraction": (
                        f"{difference.changed_sample_fraction:.9f}"
                    ),
                    "changed_pixel_fraction": (
                        f"{difference.changed_pixel_fraction:.9f}"
                    ),
                }
            )
    return observations, pairwise, syntax_equivalence


def summarize_observations(
    observations: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Summarize each fixed fixture and decoder on the current platform."""
    rows: list[dict[str, str]] = []
    for fixture_id in FIXTURE_IDS:
        for decoder in DECODERS:
            row = next(
                item
                for item in observations
                if item["fixture_id"] == fixture_id
                and item["decoder"] == decoder
            )
            rows.append(
                {
                    "platform_label": row["platform_label"],
                    "fixture_id": fixture_id,
                    "syntax_class": row["syntax_class"],
                    "decoder": decoder,
                    "exact_reference_pixels": row["exact_reference_pixels"],
                    "within_one_code_value": row[
                        "within_one_code_value"
                    ],
                    "mean_absolute_error": row["mean_absolute_error"],
                    "maximum_absolute_error": row[
                        "maximum_absolute_error"
                    ],
                    "changed_sample_fraction": row[
                        "changed_sample_fraction"
                    ],
                    "laplacian_to_reference_ratio": row[
                        "laplacian_to_reference_ratio"
                    ],
                    "tenengrad_to_reference_ratio": row[
                        "tenengrad_to_reference_ratio"
                    ],
                }
            )
    return rows


def validate_outputs(
    observations: Sequence[dict[str, str]],
    pairwise: Sequence[dict[str, str]],
    syntax_equivalence: Sequence[dict[str, str]],
    summary: Sequence[dict[str, str]],
) -> None:
    """Validate coverage and non-negotiable interface contracts."""
    expected_observations = len(FIXTURE_IDS) * len(DECODERS)
    expected_pairs = len(FIXTURE_IDS) * 3
    if len(observations) != expected_observations:
        raise RuntimeError("Unexpected advanced decoder observation count")
    if len(pairwise) != expected_pairs:
        raise RuntimeError("Unexpected advanced decoder pair count")
    if len(syntax_equivalence) != len(CONTROLLED_SYNTAX_PAIRS) * len(
        DECODERS
    ):
        raise RuntimeError("Unexpected controlled syntax comparison count")
    if len(summary) != expected_observations:
        raise RuntimeError("Unexpected advanced decoder summary count")
    if not all(
        row["structure_contract"] == "1"
        and row["shape_contract"] == "1"
        and row["dtype_contract"] == "1"
        for row in observations
    ):
        raise RuntimeError("An advanced JPEG interface contract failed")


def plot_summary(
    summary: Sequence[dict[str, str]], output_path: Path
) -> None:
    """Visualize decoder-family differences by fixed syntax class."""
    decoders = tuple(DECODERS)
    fixture_ids = tuple(FIXTURE_IDS)
    values_by_field = {}
    for field in (
        "maximum_absolute_error",
        "changed_sample_fraction",
        "laplacian_to_reference_ratio",
        "tenengrad_to_reference_ratio",
    ):
        values_by_field[field] = np.array(
            [
                [
                    float(
                        next(
                            row[field]
                            for row in summary
                            if row["fixture_id"] == fixture_id
                            and row["decoder"] == decoder
                        )
                    )
                    for decoder in decoders
                ]
                for fixture_id in fixture_ids
            ],
            dtype=np.float64,
        )
    figure, axes = plt.subplots(2, 2, figsize=(13, 10), constrained_layout=True)
    panels = (
        ("maximum_absolute_error", "Maximum code-value error", ".0f"),
        ("changed_sample_fraction", "Changed sample fraction", ".3f"),
        ("laplacian_to_reference_ratio", "Laplacian ratio", ".3f"),
        ("tenengrad_to_reference_ratio", "Tenengrad ratio", ".3f"),
    )
    for axis, (field, title, number_format) in zip(axes.flat, panels):
        values = values_by_field[field]
        image = axis.imshow(values, aspect="auto", cmap="Blues")
        axis.set_xticks(range(len(decoders)), decoders)
        axis.set_yticks(range(len(fixture_ids)), fixture_ids)
        axis.set_title(title)
        for row_index in range(values.shape[0]):
            for column_index in range(values.shape[1]):
                axis.text(
                    column_index,
                    row_index,
                    format(values[row_index, column_index], number_format),
                    ha="center",
                    va="center",
                    color="black",
                )
        figure.colorbar(image, ax=axis, shrink=0.72)
    figure.suptitle("Independent decoder families and advanced JPEG syntax")
    figure.savefig(output_path, dpi=160)
    plt.close(figure)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate independent decoder families on fixed advanced JPEG "
            "syntax."
        )
    )
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=Path("fixtures/advanced-jpeg-syntax"),
        help="Directory containing the fixed advanced JPEG corpus.",
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
    """Generate or validate fixtures, execute decoders, and write reports."""
    args = parse_args()
    if args.refresh_fixtures:
        refresh_fixtures(args.fixture_dir)
    fixtures = load_and_validate_fixtures(args.fixture_dir)
    platform_rows = build_platform_manifest(
        args.platform_label,
        record_runner_image=args.record_runner_image,
    )
    observations, pairwise, syntax_equivalence = observe_decoders(
        args.fixture_dir, fixtures, args.platform_label
    )
    summary = summarize_observations(observations)
    validate_outputs(observations, pairwise, syntax_equivalence, summary)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / PLATFORM_MANIFEST_NAME, platform_rows)
    write_csv(args.output_dir / OBSERVATIONS_NAME, observations)
    write_csv(args.output_dir / PAIRWISE_NAME, pairwise)
    write_csv(args.output_dir / SYNTAX_EQUIVALENCE_NAME, syntax_equivalence)
    write_csv(args.output_dir / SUMMARY_NAME, summary)
    plot_summary(summary, args.output_dir / FIGURE_NAME)

    exact = sum(int(row["exact_reference_pixels"]) for row in observations)
    bounded = sum(int(row["within_one_code_value"]) for row in observations)
    print(
        "Advanced JPEG syntax evaluation complete: "
        f"{len(fixtures)} fixtures, {len(observations)} observations, "
        f"{exact} exact, {bounded} within one code value. Results written "
        f"to {args.output_dir.as_posix()}."
    )


if __name__ == "__main__":
    main()
