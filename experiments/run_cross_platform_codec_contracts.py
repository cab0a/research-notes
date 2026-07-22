"""Evaluate decoded-pixel contracts for a fixed synthetic JPEG corpus."""

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
    classify_decoded_pixel_contract,
    compare_decoded_pixels,
    decode_jpeg_opencv,
    decode_jpeg_pillow,
    encode_jpeg_opencv,
    laplacian_variance,
    parse_jpeg_structure,
    pixel_array_sha256,
    tenengrad_energy,
    to_grayscale,
)


IMAGE_SIZE = 128
QUALITIES = (50, 95)
CHROMA_SAMPLINGS = ("444", "420")
DECODERS: dict[
    str, Callable[[bytes], NDArray[np.uint8]]
] = {
    "opencv": decode_jpeg_opencv,
    "pillow": decode_jpeg_pillow,
}

FIXTURE_MANIFEST_NAME = "manifest.csv"
PLATFORM_MANIFEST_NAME = "jpeg_platform_codec_manifest.csv"
OBSERVATIONS_NAME = "jpeg_decoded_pixel_observations.csv"
PAIR_OBSERVATIONS_NAME = "jpeg_decoder_pair_observations.csv"
SUMMARY_NAME = "jpeg_decoded_pixel_summary.csv"
FIGURE_NAME = "jpeg_decoded_pixel_contracts.png"

FIXTURE_FIELDS = (
    "fixture_id",
    "pattern",
    "quality_control",
    "chroma_sampling",
    "jpeg_file",
    "reference_png_file",
    "source_bgr_sha256",
    "jpeg_sha256",
    "jpeg_size_bytes",
    "reference_bgr_sha256",
    "reference_png_sha256",
    "width",
    "height",
    "frame_marker",
    "precision_bits",
    "quantization_fingerprint",
    "component_signature",
    "generator_adapter",
    "generator_wrapper_version",
    "generator_jpeg_backend",
    "reference_decoder",
)


def make_contract_patterns() -> dict[str, NDArray[np.uint8]]:
    """Create deterministic BGR patterns that exercise JPEG reconstruction."""
    rows, columns = np.indices((IMAGE_SIZE, IMAGE_SIZE))

    palette = np.array(
        [
            [16, 32, 240],
            [240, 32, 16],
            [32, 224, 48],
            [224, 48, 224],
        ],
        dtype=np.uint8,
    )
    tile_index = ((rows // 4) + 3 * (columns // 4)) % len(palette)
    high_frequency_tiles = palette[tile_index]

    chroma_edges = np.empty((IMAGE_SIZE, IMAGE_SIZE, 3), dtype=np.uint8)
    chroma_edges[:, : IMAGE_SIZE // 4] = (230, 25, 25)
    chroma_edges[:, IMAGE_SIZE // 4 : IMAGE_SIZE // 2] = (25, 230, 25)
    chroma_edges[:, IMAGE_SIZE // 2 : 3 * IMAGE_SIZE // 4] = (25, 25, 230)
    chroma_edges[:, 3 * IMAGE_SIZE // 4 :] = (220, 220, 30)
    chroma_edges[30:98, 30:98] = (30, 210, 220)
    cv2.line(chroma_edges, (7, 117), (120, 10), (235, 35, 210), 3)

    horizontal = columns.astype(np.float64) / (IMAGE_SIZE - 1)
    vertical = rows.astype(np.float64) / (IMAGE_SIZE - 1)
    gradient_shapes = np.stack(
        (
            24.0 + 205.0 * horizontal,
            36.0 + 172.0 * vertical,
            226.0 - 88.0 * horizontal - 70.0 * vertical,
        ),
        axis=2,
    )
    gradient_shapes = np.clip(
        np.rint(gradient_shapes), 0, 255
    ).astype(np.uint8)
    cv2.circle(gradient_shapes, (36, 38), 19, (215, 45, 230), -1)
    cv2.rectangle(gradient_shapes, (70, 22), (111, 67), (35, 225, 50), -1)
    cv2.line(gradient_shapes, (14, 110), (116, 83), (238, 220, 30), 5)

    return {
        "chroma_edges": chroma_edges,
        "gradient_shapes": gradient_shapes,
        "high_frequency_tiles": high_frequency_tiles,
    }


def opencv_jpeg_backend() -> str:
    """Return the JPEG backend line reported by the OpenCV build."""
    matches = [
        line.strip()
        for line in cv2.getBuildInformation().splitlines()
        if line.strip().startswith("JPEG:")
    ]
    if len(matches) != 1:
        raise RuntimeError("Could not identify the OpenCV JPEG backend.")
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
        raise RuntimeError("Pillow does not report a JPEG codec.")
    return f"libjpeg {jpeg_version}"


def bytes_sha256(payload: bytes) -> str:
    """Return the SHA-256 digest of a byte string."""
    return hashlib.sha256(payload).hexdigest()


def write_csv(
    path: Path,
    rows: Sequence[dict[str, str]],
    fieldnames: Sequence[str] | None = None,
) -> None:
    """Write deterministic CSV rows with explicit ordering."""
    if not rows:
        raise ValueError("rows must not be empty")
    path.parent.mkdir(parents=True, exist_ok=True)
    selected_fields = list(fieldnames or rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=selected_fields, lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read one UTF-8 CSV file into dictionaries."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def encode_png(image: NDArray[np.uint8]) -> bytes:
    """Encode a reference image as a lossless PNG byte string."""
    succeeded, encoded = cv2.imencode(
        ".png", image, [cv2.IMWRITE_PNG_COMPRESSION, 9]
    )
    if not succeeded:
        raise RuntimeError("OpenCV PNG encoding failed")
    return encoded.tobytes()


def decode_png(payload: bytes) -> NDArray[np.uint8]:
    """Decode a committed reference PNG to BGR pixels."""
    decoded = cv2.imdecode(
        np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR
    )
    if decoded is None:
        raise ValueError("OpenCV could not decode the reference PNG")
    return decoded


def refresh_fixtures(fixture_dir: Path) -> list[dict[str, str]]:
    """Generate the fixed synthetic JPEG corpus and decoded references."""
    fixture_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    backend = opencv_jpeg_backend()
    for pattern, source in make_contract_patterns().items():
        for quality in QUALITIES:
            for sampling in CHROMA_SAMPLINGS:
                fixture_id = f"{pattern}_q{quality}_{sampling}"
                jpeg_name = f"{fixture_id}.jpg"
                reference_name = f"{fixture_id}.reference.png"
                jpeg_bytes = encode_jpeg_opencv(
                    source,
                    quality=quality,
                    chroma_sampling=sampling,
                )
                structure = parse_jpeg_structure(jpeg_bytes)
                reference = decode_jpeg_opencv(jpeg_bytes)
                png_bytes = encode_png(reference)
                (fixture_dir / jpeg_name).write_bytes(jpeg_bytes)
                (fixture_dir / reference_name).write_bytes(png_bytes)
                rows.append(
                    {
                        "fixture_id": fixture_id,
                        "pattern": pattern,
                        "quality_control": str(quality),
                        "chroma_sampling": sampling,
                        "jpeg_file": jpeg_name,
                        "reference_png_file": reference_name,
                        "source_bgr_sha256": pixel_array_sha256(source),
                        "jpeg_sha256": bytes_sha256(jpeg_bytes),
                        "jpeg_size_bytes": str(len(jpeg_bytes)),
                        "reference_bgr_sha256": pixel_array_sha256(reference),
                        "reference_png_sha256": bytes_sha256(png_bytes),
                        "width": str(structure.width),
                        "height": str(structure.height),
                        "frame_marker": f"0x{structure.frame_marker:02x}",
                        "precision_bits": str(structure.precision_bits),
                        "quantization_fingerprint": (
                            structure.quantization_fingerprint
                        ),
                        "component_signature": structure.component_signature,
                        "generator_adapter": "opencv_quality",
                        "generator_wrapper_version": cv2.__version__,
                        "generator_jpeg_backend": backend,
                        "reference_decoder": "opencv_bgr",
                    }
                )
    rows.sort(key=lambda row: row["fixture_id"])
    write_csv(
        fixture_dir / FIXTURE_MANIFEST_NAME,
        rows,
        FIXTURE_FIELDS,
    )
    return rows


def load_and_validate_fixtures(
    fixture_dir: Path,
) -> list[dict[str, str]]:
    """Load the fixed corpus and validate bytes, pixels, and marker data."""
    manifest_path = fixture_dir / FIXTURE_MANIFEST_NAME
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"fixture manifest not found: {manifest_path.as_posix()}"
        )
    rows = read_csv(manifest_path)
    expected_ids = {
        f"{pattern}_q{quality}_{sampling}"
        for pattern in make_contract_patterns()
        for quality in QUALITIES
        for sampling in CHROMA_SAMPLINGS
    }
    if {row["fixture_id"] for row in rows} != expected_ids:
        raise RuntimeError("Fixture manifest does not contain the expected corpus.")

    sources = make_contract_patterns()
    for row in rows:
        jpeg_bytes = (fixture_dir / row["jpeg_file"]).read_bytes()
        png_bytes = (fixture_dir / row["reference_png_file"]).read_bytes()
        reference = decode_png(png_bytes)
        structure = parse_jpeg_structure(jpeg_bytes)
        checks = {
            "source_bgr_sha256": pixel_array_sha256(sources[row["pattern"]]),
            "jpeg_sha256": bytes_sha256(jpeg_bytes),
            "jpeg_size_bytes": str(len(jpeg_bytes)),
            "reference_bgr_sha256": pixel_array_sha256(reference),
            "reference_png_sha256": bytes_sha256(png_bytes),
            "width": str(structure.width),
            "height": str(structure.height),
            "frame_marker": f"0x{structure.frame_marker:02x}",
            "precision_bits": str(structure.precision_bits),
            "quantization_fingerprint": structure.quantization_fingerprint,
            "component_signature": structure.component_signature,
        }
        for field, observed in checks.items():
            if row[field] != observed:
                raise RuntimeError(
                    f"Fixture {row['fixture_id']} failed {field} validation."
                )
    return sorted(rows, key=lambda row: row["fixture_id"])


def build_platform_manifest(
    platform_label: str, *, record_runner_image: bool = False
) -> list[dict[str, str]]:
    """Record wrapper, codec, platform, and SIMD policy metadata."""
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
        "simd_policy": (
            "forced_scalar"
            if os.environ.get("JSIMD_FORCENONE") == "1"
            else "runtime_default"
        ),
    }
    return [
        {
            **common,
            "decoder": "opencv",
            "wrapper": "OpenCV",
            "wrapper_version": cv2.__version__,
            "jpeg_backend": opencv_jpeg_backend(),
        },
        {
            **common,
            "decoder": "pillow",
            "wrapper": "Pillow",
            "wrapper_version": PIL.__version__,
            "jpeg_backend": pillow_jpeg_backend(),
        },
    ]


def observe_decoders(
    fixture_dir: Path,
    fixture_rows: Sequence[dict[str, str]],
    platform_label: str,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Decode every fixture and compare each output with fixed references."""
    observations: list[dict[str, str]] = []
    pair_rows: list[dict[str, str]] = []
    for fixture in fixture_rows:
        jpeg_bytes = (fixture_dir / fixture["jpeg_file"]).read_bytes()
        reference = decode_png(
            (fixture_dir / fixture["reference_png_file"]).read_bytes()
        )
        decoded_by_adapter = {
            name: decoder(jpeg_bytes)
            for name, decoder in DECODERS.items()
        }
        reference_gray = to_grayscale(reference)
        reference_laplacian = laplacian_variance(reference_gray)
        reference_tenengrad = tenengrad_energy(reference_gray)
        for decoder_name, decoded in decoded_by_adapter.items():
            difference = compare_decoded_pixels(reference, decoded)
            decoded_gray = to_grayscale(decoded)
            observations.append(
                {
                    "platform_label": platform_label,
                    "fixture_id": fixture["fixture_id"],
                    "pattern": fixture["pattern"],
                    "quality_control": fixture["quality_control"],
                    "chroma_sampling": fixture["chroma_sampling"],
                    "decoder": decoder_name,
                    "jpeg_sha256": fixture["jpeg_sha256"],
                    "quantization_fingerprint": fixture[
                        "quantization_fingerprint"
                    ],
                    "component_signature": fixture["component_signature"],
                    "structure_contract": "1",
                    "shape_contract": str(int(decoded.shape == reference.shape)),
                    "dtype_contract": str(int(decoded.dtype == np.uint8)),
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
                        f"{laplacian_variance(decoded_gray) / reference_laplacian:.9f}"
                    ),
                    "tenengrad_to_reference_ratio": (
                        f"{tenengrad_energy(decoded_gray) / reference_tenengrad:.9f}"
                    ),
                }
            )

        pair_difference = compare_decoded_pixels(
            decoded_by_adapter["opencv"], decoded_by_adapter["pillow"]
        )
        pair_rows.append(
            {
                "platform_label": platform_label,
                "fixture_id": fixture["fixture_id"],
                "pattern": fixture["pattern"],
                "quality_control": fixture["quality_control"],
                "chroma_sampling": fixture["chroma_sampling"],
                "opencv_decoded_sha256": pair_difference.reference_sha256,
                "pillow_decoded_sha256": pair_difference.candidate_sha256,
                "exact_cross_decoder_pixels": str(int(pair_difference.exact)),
                "within_one_code_value": str(
                    int(pair_difference.maximum_absolute_error <= 1)
                ),
                "contract_level": classify_decoded_pixel_contract(
                    pair_difference
                ),
                "mean_absolute_error": (
                    f"{pair_difference.mean_absolute_error:.9f}"
                ),
                "maximum_absolute_error": str(
                    pair_difference.maximum_absolute_error
                ),
                "changed_sample_fraction": (
                    f"{pair_difference.changed_sample_fraction:.9f}"
                ),
                "changed_pixel_fraction": (
                    f"{pair_difference.changed_pixel_fraction:.9f}"
                ),
            }
        )
    return observations, pair_rows


def summarize_observations(
    observations: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Summarize exact and one-code-value contracts by declared controls."""
    rows: list[dict[str, str]] = []
    for decoder in DECODERS:
        for quality in QUALITIES:
            for sampling in CHROMA_SAMPLINGS:
                group = [
                    row
                    for row in observations
                    if row["decoder"] == decoder
                    and int(row["quality_control"]) == quality
                    and row["chroma_sampling"] == sampling
                ]
                rows.append(
                    {
                        "platform_label": group[0]["platform_label"],
                        "decoder": decoder,
                        "quality_control": str(quality),
                        "chroma_sampling": sampling,
                        "observations": str(len(group)),
                        "exact_reference_rate": (
                            f"{np.mean([int(row['exact_reference_pixels']) for row in group]):.6f}"
                        ),
                        "within_one_code_value_rate": (
                            f"{np.mean([int(row['within_one_code_value']) for row in group]):.6f}"
                        ),
                        "mean_absolute_error_max": (
                            f"{max(float(row['mean_absolute_error']) for row in group):.9f}"
                        ),
                        "maximum_absolute_error_max": str(
                            max(int(row["maximum_absolute_error"]) for row in group)
                        ),
                        "changed_sample_fraction_max": (
                            f"{max(float(row['changed_sample_fraction']) for row in group):.9f}"
                        ),
                    }
                )
    return rows


def validate_outputs(
    observations: Sequence[dict[str, str]],
    pair_rows: Sequence[dict[str, str]],
    summary_rows: Sequence[dict[str, str]],
) -> None:
    """Validate corpus coverage and non-negotiable structural contracts."""
    expected_fixture_count = (
        len(make_contract_patterns()) * len(QUALITIES) * len(CHROMA_SAMPLINGS)
    )
    if len(observations) != expected_fixture_count * len(DECODERS):
        raise RuntimeError("Unexpected decoded-pixel observation count.")
    if len(pair_rows) != expected_fixture_count:
        raise RuntimeError("Unexpected cross-decoder observation count.")
    if len(summary_rows) != len(DECODERS) * len(QUALITIES) * len(
        CHROMA_SAMPLINGS
    ):
        raise RuntimeError("Unexpected decoded-pixel summary count.")
    if not all(
        row["structure_contract"] == "1"
        and row["shape_contract"] == "1"
        and row["dtype_contract"] == "1"
        for row in observations
    ):
        raise RuntimeError("A structural decoded-pixel contract failed.")


def plot_summary(
    summary_rows: Sequence[dict[str, str]], output_path: Path
) -> None:
    """Visualize exact agreement and maximum observed code-value error."""
    labels = [
        f"{row['decoder']}\nq{row['quality_control']} {row['chroma_sampling']}"
        for row in summary_rows
    ]
    exact_rates = [float(row["exact_reference_rate"]) for row in summary_rows]
    maximum_errors = [
        int(row["maximum_absolute_error_max"]) for row in summary_rows
    ]
    colors = [
        "#3267a8" if row["decoder"] == "opencv" else "#d17a22"
        for row in summary_rows
    ]
    positions = np.arange(len(summary_rows))
    figure, axes = plt.subplots(2, 1, figsize=(11, 7), constrained_layout=True)
    axes[0].bar(positions, exact_rates, color=colors)
    axes[0].set_ylim(0.0, 1.05)
    axes[0].set_ylabel("Exact reference rate")
    axes[0].set_xticks(positions, [])
    axes[0].set_title("Decoded-pixel contracts for the fixed JPEG corpus")
    axes[0].grid(axis="y", alpha=0.25)
    axes[1].bar(positions, maximum_errors, color=colors)
    axes[1].axhline(
        1,
        color="#7a3e9d",
        linestyle="--",
        linewidth=1.5,
        label="Declared one-code-value bound",
    )
    axes[1].set_ylim(0.0, max(1.05, max(maximum_errors) + 0.2))
    axes[1].set_ylabel("Maximum absolute error")
    axes[1].set_xticks(positions, labels, rotation=30, ha="right")
    axes[1].grid(axis="y", alpha=0.25)
    axes[1].legend(loc="upper right")
    figure.savefig(output_path, dpi=160)
    plt.close(figure)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate OpenCV and Pillow decoded-pixel contracts for a fixed "
            "synthetic JPEG corpus."
        )
    )
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=Path("fixtures/jpeg-decoder-contracts"),
        help="Directory containing the fixed JPEG corpus.",
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
    """Generate or validate fixtures, run decoders, and write reports."""
    args = parse_args()
    if args.refresh_fixtures:
        refresh_fixtures(args.fixture_dir)
    fixture_rows = load_and_validate_fixtures(args.fixture_dir)
    platform_rows = build_platform_manifest(
        args.platform_label,
        record_runner_image=args.record_runner_image,
    )
    observation_rows, pair_rows = observe_decoders(
        args.fixture_dir, fixture_rows, args.platform_label
    )
    summary_rows = summarize_observations(observation_rows)
    validate_outputs(observation_rows, pair_rows, summary_rows)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / PLATFORM_MANIFEST_NAME, platform_rows)
    write_csv(args.output_dir / OBSERVATIONS_NAME, observation_rows)
    write_csv(args.output_dir / PAIR_OBSERVATIONS_NAME, pair_rows)
    write_csv(args.output_dir / SUMMARY_NAME, summary_rows)
    plot_summary(summary_rows, args.output_dir / FIGURE_NAME)

    exact_count = sum(
        int(row["exact_reference_pixels"]) for row in observation_rows
    )
    bounded_count = sum(
        int(row["within_one_code_value"]) for row in observation_rows
    )
    print(
        "Decoded-pixel contract evaluation complete: "
        f"{len(fixture_rows)} fixtures, {len(observation_rows)} decoder "
        f"observations, {exact_count} exact, {bounded_count} within one code "
        f"value. Results written to {args.output_dir.as_posix()}."
    )


if __name__ == "__main__":
    main()
