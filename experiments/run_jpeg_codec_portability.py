"""Audit JPEG quantization tables and bounded codec portability."""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections.abc import Sequence
from pathlib import Path

import cv2
import matplotlib
import numpy as np
import PIL
from numpy.typing import NDArray
from PIL import features

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

from research_notes import (
    decode_jpeg_opencv,
    decode_jpeg_pillow,
    encode_jpeg_opencv,
    encode_jpeg_pillow,
    laplacian_variance,
    parse_jpeg_structure,
    tenengrad_energy,
    to_grayscale,
)


IMAGE_SIZE = 256
BLUR_SIGMAS = (0, 1, 2, 3)
QUALITIES = (50, 75, 95)
QUALITY_SWEEP = tuple(range(1, 101))
CHROMA_SAMPLINGS = ("444", "420")
ENCODER_PATHS = (
    "opencv_quality",
    "pillow_quality",
    "pillow_explicit_dqt",
    "pillow_optimized",
)
ALTERNATIVE_PATHS = ENCODER_PATHS[1:]
DECODERS = {
    "opencv": decode_jpeg_opencv,
    "pillow": decode_jpeg_pillow,
}
METRICS = {
    "laplacian_variance": laplacian_variance,
    "tenengrad_energy": tenengrad_energy,
}
PATH_DESCRIPTIONS = {
    "opencv_quality": "OpenCV numeric quality, default Huffman coding",
    "pillow_quality": "Pillow numeric quality, default Huffman coding",
    "pillow_explicit_dqt": "Pillow explicit OpenCV-extracted DQT tables",
    "pillow_optimized": "Pillow numeric quality, optimized Huffman coding",
}

MANIFEST_CSV_NAME = "jpeg_codec_manifest.csv"
SWEEP_CSV_NAME = "jpeg_quality_table_sweep.csv"
TABLES_CSV_NAME = "jpeg_quantization_tables.csv"
TRIALS_CSV_NAME = "jpeg_codec_trials.csv"
ENCODER_CSV_NAME = "jpeg_encoder_agreement.csv"
DECODER_CSV_NAME = "jpeg_decoder_agreement.csv"
SUMMARY_CSV_NAME = "jpeg_codec_portability_summary.csv"
TABLES_FIGURE_NAME = "jpeg_quantization_tables.png"
PORTABILITY_FIGURE_NAME = "jpeg_codec_portability.png"


def make_patterns() -> dict[str, NDArray[np.uint8]]:
    """Create three deterministic synthetic BGR patterns."""
    rows, columns = np.indices((IMAGE_SIZE, IMAGE_SIZE))
    checker = ((rows // 8 + columns // 8) % 2).astype(np.uint8)
    checker_gray = np.where(checker == 0, 32, 224).astype(np.uint8)
    achromatic_checkerboard = cv2.cvtColor(
        checker_gray, cv2.COLOR_GRAY2BGR
    )

    palette = np.array(
        [
            [240, 40, 40],
            [40, 220, 40],
            [40, 40, 240],
            [220, 220, 40],
            [220, 40, 220],
            [40, 220, 220],
        ],
        dtype=np.uint8,
    )
    palette_indices = ((columns // 8) + 2 * (rows // 32)) % len(palette)
    chromatic_stripes = palette[palette_indices]

    horizontal = np.linspace(0.0, 1.0, IMAGE_SIZE, dtype=np.float64)
    vertical = horizontal[:, np.newaxis]
    blue = np.broadcast_to(30.0 + 170.0 * horizontal, (IMAGE_SIZE, IMAGE_SIZE))
    green = np.broadcast_to(45.0 + 130.0 * vertical, (IMAGE_SIZE, IMAGE_SIZE))
    red = 220.0 - 120.0 * (horizontal[np.newaxis, :] + vertical) / 2.0
    colored_targets = np.stack((blue, green, red), axis=2)
    colored_targets = np.clip(np.rint(colored_targets), 0, 255).astype(np.uint8)
    cv2.rectangle(colored_targets, (24, 24), (112, 104), (230, 35, 220), -1)
    cv2.circle(colored_targets, (184, 72), 42, (35, 230, 210), -1)
    cv2.line(colored_targets, (20, 220), (235, 135), (245, 245, 35), 9)
    cv2.circle(colored_targets, (78, 180), 30, (30, 50, 240), 7)

    return {
        "achromatic_checkerboard": achromatic_checkerboard,
        "chromatic_stripes": chromatic_stripes,
        "colored_targets": colored_targets,
    }


def apply_gaussian_blur(
    image: NDArray[np.uint8], sigma: int
) -> NDArray[np.uint8]:
    """Apply Gaussian blur or return a copy for the zero control."""
    if sigma < 0:
        raise ValueError("sigma must not be negative")
    if sigma == 0:
        return image.copy()
    return cv2.GaussianBlur(
        image,
        (0, 0),
        sigmaX=float(sigma),
        sigmaY=float(sigma),
        borderType=cv2.BORDER_REFLECT_101,
    )


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
    version = features.version_feature("libjpeg_turbo")
    if version is None:
        raise RuntimeError("Pillow does not report libjpeg-turbo support.")
    return f"libjpeg-turbo {version}"


def build_codec_manifest() -> list[dict[str, str]]:
    """Record the two wrapper and backend versions under comparison."""
    return [
        {
            "adapter": "opencv",
            "wrapper": "OpenCV",
            "wrapper_version": cv2.__version__,
            "jpeg_backend": opencv_jpeg_backend(),
            "roles": "quality encoder; decoder; DQT source",
        },
        {
            "adapter": "pillow",
            "wrapper": "Pillow",
            "wrapper_version": PIL.__version__,
            "jpeg_backend": pillow_jpeg_backend(),
            "roles": "quality encoder; explicit-DQT encoder; optimized encoder; decoder",
        },
    ]


def libjpeg_quality_scale(quality: int) -> int:
    """Return the integer table-scaling percentage used by libjpeg."""
    if not 1 <= quality <= 100:
        raise ValueError("quality must be in the interval [1, 100]")
    if quality < 50:
        return 5000 // quality
    return 200 - 2 * quality


def make_sweep_reference() -> NDArray[np.uint8]:
    """Create a small color input for the quality-to-DQT sweep."""
    rows, columns = np.indices((16, 16))
    gray = (((rows // 3 + columns // 5) % 2) * 255).astype(np.uint8)
    return cv2.applyColorMap(gray, cv2.COLORMAP_TURBO)


def run_quality_sweep(
) -> tuple[
    list[dict[str, str]],
    dict[int, dict[int, tuple[int, ...]]],
]:
    """Compare numeric quality-to-DQT mappings across both wrappers."""
    rows: list[dict[str, str]] = []
    reference_tables: dict[int, dict[int, tuple[int, ...]]] = {}
    image = make_sweep_reference()
    previous_values: tuple[int, ...] | None = None
    for quality in QUALITY_SWEEP:
        opencv_bytes = encode_jpeg_opencv(
            image, quality=quality, chroma_sampling="444"
        )
        pillow_bytes = encode_jpeg_pillow(
            image, quality=quality, chroma_sampling="444"
        )
        opencv_structure = parse_jpeg_structure(opencv_bytes)
        pillow_structure = parse_jpeg_structure(pillow_bytes)
        tables = opencv_structure.quantization_tables_natural()
        reference_tables[quality] = tables
        combined = tables[0] + tables[1]
        adjacent_l1 = (
            0
            if previous_values is None
            else sum(
                abs(current - previous)
                for current, previous in zip(combined, previous_values)
            )
        )
        previous_values = combined
        rows.append(
            {
                "quality": str(quality),
                "libjpeg_scale_percent": str(
                    libjpeg_quality_scale(quality)
                ),
                "opencv_quantization_fingerprint": (
                    opencv_structure.quantization_fingerprint
                ),
                "pillow_quantization_fingerprint": (
                    pillow_structure.quantization_fingerprint
                ),
                "quantization_tables_equal": str(
                    int(
                        opencv_structure.quantization_fingerprint
                        == pillow_structure.quantization_fingerprint
                    )
                ),
                "encoded_bytes_equal": str(
                    int(opencv_bytes == pillow_bytes)
                ),
                "luma_min": str(min(tables[0])),
                "luma_max": str(max(tables[0])),
                "luma_mean": f"{np.mean(tables[0]):.6f}",
                "chroma_min": str(min(tables[1])),
                "chroma_max": str(max(tables[1])),
                "chroma_mean": f"{np.mean(tables[1]):.6f}",
                "adjacent_table_l1_from_previous_quality": str(adjacent_l1),
            }
        )
    return rows, reference_tables


def build_quantization_table_rows(
    reference_tables: dict[int, dict[int, tuple[int, ...]]],
) -> list[dict[str, str]]:
    """Expand selected DQT tables into auditable coefficient rows."""
    rows: list[dict[str, str]] = []
    reference = make_sweep_reference()
    for quality in QUALITIES:
        structure = parse_jpeg_structure(
            encode_jpeg_opencv(reference, quality, "444")
        )
        for table in structure.quantization_tables:
            natural_values = reference_tables[quality][table.table_id]
            for natural_index, value in enumerate(natural_values):
                rows.append(
                    {
                        "quality": str(quality),
                        "table_id": str(table.table_id),
                        "component_role": (
                            "luma" if table.table_id == 0 else "chroma"
                        ),
                        "precision_bits": str(table.precision_bits),
                        "natural_index": str(natural_index),
                        "row": str(natural_index // 8),
                        "column": str(natural_index % 8),
                        "value": str(value),
                        "table_fingerprint": table.fingerprint,
                        "source": "OpenCV quality path; verified equal to Pillow",
                    }
                )
    return rows


def encode_path(
    image: NDArray[np.uint8],
    path: str,
    quality: int,
    chroma_sampling: str,
    reference_tables: dict[int, dict[int, tuple[int, ...]]],
) -> bytes:
    """Apply one declared encoder path."""
    if path == "opencv_quality":
        return encode_jpeg_opencv(image, quality, chroma_sampling)
    if path == "pillow_quality":
        return encode_jpeg_pillow(image, quality, chroma_sampling)
    if path == "pillow_explicit_dqt":
        return encode_jpeg_pillow(
            image,
            quality=None,
            chroma_sampling=chroma_sampling,
            quantization_tables=reference_tables[quality],
        )
    if path == "pillow_optimized":
        return encode_jpeg_pillow(
            image,
            quality,
            chroma_sampling,
            optimize=True,
        )
    raise ValueError(f"unknown encoder path: {path}")


def image_sha256(image: NDArray[np.uint8]) -> str:
    """Return a stable hash of array shape, dtype, and bytes."""
    digest = hashlib.sha256()
    digest.update(str(image.shape).encode("ascii"))
    digest.update(image.dtype.str.encode("ascii"))
    digest.update(image.tobytes())
    return digest.hexdigest()


def pixel_difference(
    left: NDArray[np.uint8], right: NDArray[np.uint8]
) -> tuple[bool, float, int, float]:
    """Return exact equality, MAE, maximum error, and changed-pixel fraction."""
    if left.shape != right.shape:
        raise ValueError("pixel arrays must have identical shapes")
    difference = np.abs(left.astype(np.int16) - right.astype(np.int16))
    if difference.ndim == 3:
        changed = np.any(difference != 0, axis=2)
    else:
        changed = difference != 0
    return (
        bool(np.array_equal(left, right)),
        float(np.mean(difference)),
        int(np.max(difference)),
        float(np.mean(changed)),
    )


def run_codec_trials(
    reference_tables: dict[int, dict[int, tuple[int, ...]]],
) -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    """Run encoder-path and cross-decoder portability comparisons."""
    trial_rows: list[dict[str, str]] = []
    encoder_rows: list[dict[str, str]] = []
    decoder_rows: list[dict[str, str]] = []
    for pattern, image in make_patterns().items():
        for blur_sigma in BLUR_SIGMAS:
            source = apply_gaussian_blur(image, blur_sigma)
            source_gray = to_grayscale(source)
            source_scores = {
                metric_name: metric(source_gray)
                for metric_name, metric in METRICS.items()
            }
            for quality in QUALITIES:
                for sampling in CHROMA_SAMPLINGS:
                    encoded_by_path: dict[str, bytes] = {}
                    decoded_by_path: dict[
                        str, dict[str, NDArray[np.uint8]]
                    ] = {}
                    structures = {}
                    for path in ENCODER_PATHS:
                        encoded = encode_path(
                            source,
                            path,
                            quality,
                            sampling,
                            reference_tables,
                        )
                        encoded_by_path[path] = encoded
                        structure = parse_jpeg_structure(encoded)
                        structures[path] = structure
                        decoded_by_path[path] = {
                            decoder_name: decoder(encoded)
                            for decoder_name, decoder in DECODERS.items()
                        }
                        for decoder_name, decoded in decoded_by_path[path].items():
                            decoded_gray = to_grayscale(decoded)
                            for metric_name, metric in METRICS.items():
                                score = metric(decoded_gray)
                                trial_rows.append(
                                    {
                                        "pattern": pattern,
                                        "blur_sigma": str(blur_sigma),
                                        "quality": str(quality),
                                        "chroma_sampling": sampling,
                                        "encoder_path": path,
                                        "encoder_path_description": (
                                            PATH_DESCRIPTIONS[path]
                                        ),
                                        "decoder": decoder_name,
                                        "metric": metric_name,
                                        "score": f"{score:.6f}",
                                        "uncompressed_score": (
                                            f"{source_scores[metric_name]:.6f}"
                                        ),
                                        "ratio_to_uncompressed": (
                                            f"{score / source_scores[metric_name]:.6f}"
                                        ),
                                        "encoded_size_bytes": str(len(encoded)),
                                        "encoded_sha256": (
                                            hashlib.sha256(encoded).hexdigest()
                                        ),
                                        "decoded_sha256": image_sha256(decoded),
                                        "quantization_fingerprint": (
                                            structure.quantization_fingerprint
                                        ),
                                        "component_signature": (
                                            structure.component_signature
                                        ),
                                    }
                                )

                        opencv_decoded = decoded_by_path[path]["opencv"]
                        pillow_decoded = decoded_by_path[path]["pillow"]
                        equal, mae, maximum, changed_fraction = pixel_difference(
                            opencv_decoded, pillow_decoded
                        )
                        opencv_gray = to_grayscale(opencv_decoded)
                        pillow_gray = to_grayscale(pillow_decoded)
                        decoder_rows.append(
                            {
                                "pattern": pattern,
                                "blur_sigma": str(blur_sigma),
                                "quality": str(quality),
                                "chroma_sampling": sampling,
                                "encoder_path": path,
                                "encoded_sha256": (
                                    hashlib.sha256(encoded).hexdigest()
                                ),
                                "decoded_pixels_equal": str(int(equal)),
                                "pixel_mae": f"{mae:.6f}",
                                "pixel_max_abs_error": str(maximum),
                                "changed_pixel_fraction": (
                                    f"{changed_fraction:.6f}"
                                ),
                                "opencv_decoded_sha256": image_sha256(
                                    opencv_decoded
                                ),
                                "pillow_decoded_sha256": image_sha256(
                                    pillow_decoded
                                ),
                                "laplacian_pillow_to_opencv_ratio": (
                                    f"{laplacian_variance(pillow_gray) / laplacian_variance(opencv_gray):.6f}"
                                ),
                                "tenengrad_pillow_to_opencv_ratio": (
                                    f"{tenengrad_energy(pillow_gray) / tenengrad_energy(opencv_gray):.6f}"
                                ),
                            }
                        )

                    baseline_bytes = encoded_by_path["opencv_quality"]
                    baseline_structure = structures["opencv_quality"]
                    baseline_decoded = decoded_by_path["opencv_quality"][
                        "opencv"
                    ]
                    baseline_gray = to_grayscale(baseline_decoded)
                    for path in ALTERNATIVE_PATHS:
                        candidate_bytes = encoded_by_path[path]
                        candidate_structure = structures[path]
                        candidate_decoded = decoded_by_path[path]["opencv"]
                        candidate_gray = to_grayscale(candidate_decoded)
                        equal, mae, maximum, changed_fraction = pixel_difference(
                            baseline_decoded, candidate_decoded
                        )
                        encoder_rows.append(
                            {
                                "pattern": pattern,
                                "blur_sigma": str(blur_sigma),
                                "quality": str(quality),
                                "chroma_sampling": sampling,
                                "baseline_path": "opencv_quality",
                                "candidate_path": path,
                                "candidate_path_description": (
                                    PATH_DESCRIPTIONS[path]
                                ),
                                "encoded_bytes_equal": str(
                                    int(baseline_bytes == candidate_bytes)
                                ),
                                "quantization_tables_equal": str(
                                    int(
                                        baseline_structure.quantization_fingerprint
                                        == candidate_structure.quantization_fingerprint
                                    )
                                ),
                                "component_signatures_equal": str(
                                    int(
                                        baseline_structure.component_signature
                                        == candidate_structure.component_signature
                                    )
                                ),
                                "baseline_size_bytes": str(
                                    len(baseline_bytes)
                                ),
                                "candidate_size_bytes": str(
                                    len(candidate_bytes)
                                ),
                                "candidate_to_baseline_size_ratio": (
                                    f"{len(candidate_bytes) / len(baseline_bytes):.6f}"
                                ),
                                "decoded_pixels_equal": str(int(equal)),
                                "decoded_pixel_mae": f"{mae:.6f}",
                                "decoded_pixel_max_abs_error": str(maximum),
                                "decoded_changed_pixel_fraction": (
                                    f"{changed_fraction:.6f}"
                                ),
                                "laplacian_candidate_to_baseline_ratio": (
                                    f"{laplacian_variance(candidate_gray) / laplacian_variance(baseline_gray):.6f}"
                                ),
                                "tenengrad_candidate_to_baseline_ratio": (
                                    f"{tenengrad_energy(candidate_gray) / tenengrad_energy(baseline_gray):.6f}"
                                ),
                            }
                        )
    return trial_rows, encoder_rows, decoder_rows


def summarize_portability(
    encoder_rows: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Aggregate encoder agreement across the three source patterns."""
    summary_rows: list[dict[str, str]] = []
    for path in ALTERNATIVE_PATHS:
        for quality in QUALITIES:
            for sampling in CHROMA_SAMPLINGS:
                for blur_sigma in BLUR_SIGMAS:
                    group = [
                        row
                        for row in encoder_rows
                        if row["candidate_path"] == path
                        and int(row["quality"]) == quality
                        and row["chroma_sampling"] == sampling
                        and int(row["blur_sigma"]) == blur_sigma
                    ]
                    summary_rows.append(
                        {
                            "candidate_path": path,
                            "candidate_path_description": (
                                PATH_DESCRIPTIONS[path]
                            ),
                            "quality": str(quality),
                            "chroma_sampling": sampling,
                            "blur_sigma": str(blur_sigma),
                            "observations": str(len(group)),
                            "encoded_byte_equality_rate": (
                                f"{np.mean([int(row['encoded_bytes_equal']) for row in group]):.6f}"
                            ),
                            "quantization_table_equality_rate": (
                                f"{np.mean([int(row['quantization_tables_equal']) for row in group]):.6f}"
                            ),
                            "component_signature_equality_rate": (
                                f"{np.mean([int(row['component_signatures_equal']) for row in group]):.6f}"
                            ),
                            "decoded_pixel_equality_rate": (
                                f"{np.mean([int(row['decoded_pixels_equal']) for row in group]):.6f}"
                            ),
                            "candidate_to_baseline_size_ratio_mean": (
                                f"{np.mean([float(row['candidate_to_baseline_size_ratio']) for row in group]):.6f}"
                            ),
                            "laplacian_candidate_to_baseline_ratio_mean": (
                                f"{np.mean([float(row['laplacian_candidate_to_baseline_ratio']) for row in group]):.6f}"
                            ),
                            "tenengrad_candidate_to_baseline_ratio_mean": (
                                f"{np.mean([float(row['tenengrad_candidate_to_baseline_ratio']) for row in group]):.6f}"
                            ),
                        }
                    )
    return summary_rows


def validate_expected_relationships(
    manifest_rows: Sequence[dict[str, str]],
    sweep_rows: Sequence[dict[str, str]],
    table_rows: Sequence[dict[str, str]],
    trial_rows: Sequence[dict[str, str]],
    encoder_rows: Sequence[dict[str, str]],
    decoder_rows: Sequence[dict[str, str]],
    summary_rows: Sequence[dict[str, str]],
) -> None:
    """Validate counts and bounded portability relationships."""
    pattern_count = len(make_patterns())
    base_condition_count = (
        pattern_count
        * len(BLUR_SIGMAS)
        * len(QUALITIES)
        * len(CHROMA_SAMPLINGS)
    )
    expected_trials = (
        base_condition_count
        * len(ENCODER_PATHS)
        * len(DECODERS)
        * len(METRICS)
    )
    if len(manifest_rows) != 2:
        raise RuntimeError("Unexpected codec manifest row count.")
    if len(sweep_rows) != len(QUALITY_SWEEP):
        raise RuntimeError("Unexpected quality-sweep row count.")
    if len(table_rows) != len(QUALITIES) * 2 * 64:
        raise RuntimeError("Unexpected quantization-table row count.")
    if len(trial_rows) != expected_trials:
        raise RuntimeError("Unexpected codec trial row count.")
    if len(encoder_rows) != base_condition_count * len(ALTERNATIVE_PATHS):
        raise RuntimeError("Unexpected encoder-agreement row count.")
    if len(decoder_rows) != base_condition_count * len(ENCODER_PATHS):
        raise RuntimeError("Unexpected decoder-agreement row count.")
    if len(summary_rows) != (
        len(ALTERNATIVE_PATHS)
        * len(QUALITIES)
        * len(CHROMA_SAMPLINGS)
        * len(BLUR_SIGMAS)
    ):
        raise RuntimeError("Unexpected portability-summary row count.")

    if not all(
        row["quantization_tables_equal"] == "1"
        and row["encoded_bytes_equal"] == "1"
        for row in sweep_rows
    ):
        raise RuntimeError("Numeric quality paths must match in the sweep.")
    fingerprints = {
        row["opencv_quantization_fingerprint"] for row in sweep_rows
    }
    if len(fingerprints) != len(QUALITY_SWEEP):
        raise RuntimeError("Each tested quality must have a distinct DQT set.")
    means = [
        (
            float(next(row["luma_mean"] for row in sweep_rows if row["quality"] == str(quality))),
            float(next(row["chroma_mean"] for row in sweep_rows if row["quality"] == str(quality))),
        )
        for quality in QUALITIES
    ]
    if not all(
        left[0] > right[0] and left[1] > right[1]
        for left, right in zip(means, means[1:])
    ):
        raise RuntimeError("Selected higher qualities must use smaller DQT means.")

    exact_paths = {"pillow_quality", "pillow_explicit_dqt"}
    exact_rows = [
        row for row in encoder_rows if row["candidate_path"] in exact_paths
    ]
    if not all(
        row["encoded_bytes_equal"] == "1"
        and row["quantization_tables_equal"] == "1"
        and row["decoded_pixels_equal"] == "1"
        for row in exact_rows
    ):
        raise RuntimeError("Default and explicit-DQT paths must match exactly.")
    optimized_rows = [
        row
        for row in encoder_rows
        if row["candidate_path"] == "pillow_optimized"
    ]
    if any(row["quantization_tables_equal"] != "1" for row in optimized_rows):
        raise RuntimeError("Huffman optimization must preserve DQT tables.")
    if any(row["decoded_pixels_equal"] != "1" for row in optimized_rows):
        raise RuntimeError("Huffman optimization must preserve decoded pixels.")
    if all(row["encoded_bytes_equal"] == "1" for row in optimized_rows):
        raise RuntimeError("Huffman optimization must change a byte stream.")
    if not all(row["decoded_pixels_equal"] == "1" for row in decoder_rows):
        raise RuntimeError("The two decoders must agree in this bounded study.")


def write_csv(rows: Sequence[dict[str, str]], output_path: Path) -> None:
    """Write deterministic CSV with platform-independent newlines."""
    if not rows:
        raise ValueError("rows must not be empty")
    with output_path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def find_summary(
    rows: Sequence[dict[str, str]],
    path: str,
    quality: int,
    sampling: str,
    blur_sigma: int,
) -> dict[str, str]:
    """Find one portability-summary row."""
    matches = [
        row
        for row in rows
        if row["candidate_path"] == path
        and int(row["quality"]) == quality
        and row["chroma_sampling"] == sampling
        and int(row["blur_sigma"]) == blur_sigma
    ]
    if len(matches) != 1:
        raise RuntimeError("Expected one portability summary row.")
    return matches[0]


def write_quantization_figure(
    sweep_rows: Sequence[dict[str, str]],
    reference_tables: dict[int, dict[int, tuple[int, ...]]],
    output_path: Path,
) -> None:
    """Visualize selected tables and nonlinear quality scaling."""
    figure, axes = plt.subplots(
        2, 4, figsize=(15, 7), constrained_layout=True
    )
    maximum = max(
        max(reference_tables[quality][table_id])
        for quality in QUALITIES
        for table_id in (0, 1)
    )
    image = None
    for row_index, table_id in enumerate((0, 1)):
        for column_index, quality in enumerate(QUALITIES):
            table = np.array(
                reference_tables[quality][table_id], dtype=np.int32
            ).reshape(8, 8)
            image = axes[row_index, column_index].imshow(
                table,
                cmap="viridis",
                vmin=1,
                vmax=maximum,
            )
            for row in range(8):
                for column in range(8):
                    axes[row_index, column_index].text(
                        column,
                        row,
                        str(table[row, column]),
                        ha="center",
                        va="center",
                        fontsize=5,
                        color=(
                            "white"
                            if table[row, column] > maximum * 0.45
                            else "black"
                        ),
                    )
            axes[row_index, column_index].set_title(
                f"{'luma' if table_id == 0 else 'chroma'} q{quality}"
            )
            axes[row_index, column_index].set_xticks([])
            axes[row_index, column_index].set_yticks([])
    if image is not None:
        figure.colorbar(image, ax=axes[:, :3], shrink=0.75, label="DQT value")

    qualities = [int(row["quality"]) for row in sweep_rows]
    luma_means = [float(row["luma_mean"]) for row in sweep_rows]
    chroma_means = [float(row["chroma_mean"]) for row in sweep_rows]
    adjacent = [
        int(row["adjacent_table_l1_from_previous_quality"])
        for row in sweep_rows
    ]
    scales = [int(row["libjpeg_scale_percent"]) for row in sweep_rows]
    axes[0, 3].plot(qualities, luma_means, label="luma mean", color="#2563eb")
    axes[0, 3].plot(
        qualities, chroma_means, label="chroma mean", color="#dc2626"
    )
    axes[0, 3].set_title("Mean quantization step")
    axes[0, 3].set_xlabel("numeric quality")
    axes[0, 3].set_ylabel("mean DQT value")
    axes[0, 3].set_yscale("log")
    axes[0, 3].legend()
    axes[0, 3].grid(alpha=0.2)

    axes[1, 3].plot(
        qualities,
        adjacent,
        label="adjacent DQT L1",
        color="#059669",
    )
    scale_axis = axes[1, 3].twinx()
    scale_axis.plot(
        qualities,
        scales,
        label="libjpeg scale",
        color="#d97706",
        alpha=0.7,
    )
    axes[1, 3].set_title("Quality steps are nonlinear")
    axes[1, 3].set_xlabel("numeric quality")
    axes[1, 3].set_ylabel("DQT L1 change")
    scale_axis.set_ylabel("scale percent")
    axes[1, 3].grid(alpha=0.2)

    figure.suptitle(
        "JPEG quantization tables extracted from encoded marker data",
        fontsize=14,
    )
    figure.savefig(
        output_path,
        dpi=150,
        metadata={"Software": "research-notes v0.9.0"},
    )
    plt.close(figure)


def write_portability_figure(
    summary_rows: Sequence[dict[str, str]],
    trial_rows: Sequence[dict[str, str]],
    output_path: Path,
) -> None:
    """Plot portability layers, size changes, and metric response."""
    figure, axes = plt.subplots(2, 2, figsize=(12, 9), constrained_layout=True)
    path_labels = {
        "pillow_quality": "Pillow quality",
        "pillow_explicit_dqt": "Pillow explicit DQT",
        "pillow_optimized": "Pillow optimized",
    }
    positions = np.arange(len(ALTERNATIVE_PATHS))
    width = 0.24
    equality_fields = (
        ("quantization_table_equality_rate", "DQT"),
        ("encoded_byte_equality_rate", "bytes"),
        ("decoded_pixel_equality_rate", "decoded pixels"),
    )
    for field_index, (field, label) in enumerate(equality_fields):
        values = []
        for path in ALTERNATIVE_PATHS:
            group = [row for row in summary_rows if row["candidate_path"] == path]
            values.append(np.mean([float(row[field]) for row in group]))
        axes[0, 0].bar(
            positions + (field_index - 1) * width,
            values,
            width,
            label=label,
        )
    axes[0, 0].set_xticks(
        positions,
        [path_labels[path] for path in ALTERNATIVE_PATHS],
        rotation=15,
        ha="right",
    )
    axes[0, 0].set_ylim(0.0, 1.05)
    axes[0, 0].set_ylabel("agreement rate")
    axes[0, 0].set_title("Portability depends on the comparison layer")
    axes[0, 0].legend(fontsize=8)
    axes[0, 0].grid(axis="y", alpha=0.2)

    for path, color in zip(ALTERNATIVE_PATHS, ("#2563eb", "#059669", "#dc2626")):
        values = []
        for quality in QUALITIES:
            group = [
                row
                for row in summary_rows
                if row["candidate_path"] == path
                and int(row["quality"]) == quality
            ]
            values.append(
                np.mean(
                    [
                        float(row["candidate_to_baseline_size_ratio_mean"])
                        for row in group
                    ]
                )
            )
        axes[0, 1].plot(
            QUALITIES,
            values,
            marker="o",
            label=path_labels[path],
            color=color,
        )
    axes[0, 1].axhline(1.0, color="#9ca3af", linewidth=1)
    axes[0, 1].set_title("Encoded size relative to OpenCV default")
    axes[0, 1].set_xlabel("numeric quality")
    axes[0, 1].set_ylabel("candidate / OpenCV bytes")
    axes[0, 1].legend(fontsize=8)
    axes[0, 1].grid(alpha=0.2)

    for axis, (metric, metric_label) in zip(
        axes[1],
        (
            ("laplacian_variance", "Laplacian variance"),
            ("tenengrad_energy", "Tenengrad energy"),
        ),
    ):
        for quality, color in zip(QUALITIES, ("#2563eb", "#059669", "#dc2626")):
            values = []
            for blur_sigma in BLUR_SIGMAS:
                group = [
                    row
                    for row in trial_rows
                    if row["encoder_path"] == "opencv_quality"
                    and row["decoder"] == "opencv"
                    and row["metric"] == metric
                    and int(row["quality"]) == quality
                    and row["chroma_sampling"] == "420"
                    and int(row["blur_sigma"]) == blur_sigma
                ]
                values.append(
                    np.mean(
                        [float(row["ratio_to_uncompressed"]) for row in group]
                    )
                )
            axis.plot(
                BLUR_SIGMAS,
                values,
                marker="o",
                label=f"q{quality}",
                color=color,
            )
        axis.axhline(1.0, color="#9ca3af", linewidth=1)
        axis.set_title(f"{metric_label}: decoded / uncompressed")
        axis.set_xlabel("Gaussian blur sigma")
        axis.set_ylabel("score ratio")
        axis.set_xticks(BLUR_SIGMAS)
        axis.legend(fontsize=8)
        axis.grid(alpha=0.2)

    figure.suptitle(
        "Bounded JPEG codec portability and derivative-metric response",
        fontsize=14,
    )
    figure.savefig(
        output_path,
        dpi=150,
        metadata={"Software": "research-notes v0.9.0"},
    )
    plt.close(figure)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Run the deterministic JPEG quantization and codec-portability audit."
        )
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results"),
        help="Directory for generated CSV and PNG artifacts (default: results).",
    )
    return parser.parse_args()


def main() -> None:
    """Run, validate, and write the experiment outputs."""
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest_rows = build_codec_manifest()
    sweep_rows, reference_tables = run_quality_sweep()
    table_rows = build_quantization_table_rows(reference_tables)
    trial_rows, encoder_rows, decoder_rows = run_codec_trials(
        reference_tables
    )
    summary_rows = summarize_portability(encoder_rows)
    validate_expected_relationships(
        manifest_rows,
        sweep_rows,
        table_rows,
        trial_rows,
        encoder_rows,
        decoder_rows,
        summary_rows,
    )
    write_csv(manifest_rows, args.output_dir / MANIFEST_CSV_NAME)
    write_csv(sweep_rows, args.output_dir / SWEEP_CSV_NAME)
    write_csv(table_rows, args.output_dir / TABLES_CSV_NAME)
    write_csv(trial_rows, args.output_dir / TRIALS_CSV_NAME)
    write_csv(encoder_rows, args.output_dir / ENCODER_CSV_NAME)
    write_csv(decoder_rows, args.output_dir / DECODER_CSV_NAME)
    write_csv(summary_rows, args.output_dir / SUMMARY_CSV_NAME)
    write_quantization_figure(
        sweep_rows,
        reference_tables,
        args.output_dir / TABLES_FIGURE_NAME,
    )
    write_portability_figure(
        summary_rows,
        trial_rows,
        args.output_dir / PORTABILITY_FIGURE_NAME,
    )
    print(
        f"Wrote {len(sweep_rows)} quality rows, {len(table_rows)} DQT rows, "
        f"{len(trial_rows)} metric rows, {len(encoder_rows)} encoder "
        f"comparisons, {len(decoder_rows)} decoder comparisons, and "
        f"{len(summary_rows)} summaries to {args.output_dir}."
    )


if __name__ == "__main__":
    main()
