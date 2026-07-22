"""Evaluate JPEG quality order, grid alignment, and chroma sampling."""

from __future__ import annotations

import argparse
import csv
from collections.abc import Sequence
from pathlib import Path

import cv2
import matplotlib
import numpy as np
from numpy.typing import NDArray

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

from research_notes import (
    jpeg_encode_decode,
    laplacian_variance,
    tenengrad_energy,
    to_grayscale,
)


SOURCE_SIZE = 264
CROP_SIZE = 256
BLUR_SIGMAS = (0, 1, 2, 3)
NOISE_STANDARD_DEVIATIONS = (0, 15)
NOISE_TRIALS = 5
BASE_SEED = 20261301
ALIGNMENTS = {"aligned": 0, "shifted_4x4": 4}
HISTORIES = (
    {
        "name": "gray_q75_to_q75",
        "description": "grayscale JPEG quality 75 to quality 75",
        "color_path": "grayscale",
        "primary_quality": 75,
        "secondary_quality": 75,
        "primary_sampling": None,
        "secondary_sampling": None,
    },
    {
        "name": "gray_q95_to_q75",
        "description": "grayscale JPEG quality 95 to quality 75",
        "color_path": "grayscale",
        "primary_quality": 95,
        "secondary_quality": 75,
        "primary_sampling": None,
        "secondary_sampling": None,
    },
    {
        "name": "gray_q50_to_q75",
        "description": "grayscale JPEG quality 50 to quality 75",
        "color_path": "grayscale",
        "primary_quality": 50,
        "secondary_quality": 75,
        "primary_sampling": None,
        "secondary_sampling": None,
    },
    {
        "name": "gray_q75_to_q95",
        "description": "grayscale JPEG quality 75 to quality 95",
        "color_path": "grayscale",
        "primary_quality": 75,
        "secondary_quality": 95,
        "primary_sampling": None,
        "secondary_sampling": None,
    },
    {
        "name": "gray_q75_to_q50",
        "description": "grayscale JPEG quality 75 to quality 50",
        "color_path": "grayscale",
        "primary_quality": 75,
        "secondary_quality": 50,
        "primary_sampling": None,
        "secondary_sampling": None,
    },
    {
        "name": "color_q75_444_to_q75_444",
        "description": "BGR JPEG quality 75 4:4:4 to quality 75 4:4:4",
        "color_path": "bgr",
        "primary_quality": 75,
        "secondary_quality": 75,
        "primary_sampling": "444",
        "secondary_sampling": "444",
    },
    {
        "name": "color_q75_420_to_q75_420",
        "description": "BGR JPEG quality 75 4:2:0 to quality 75 4:2:0",
        "color_path": "bgr",
        "primary_quality": 75,
        "secondary_quality": 75,
        "primary_sampling": "420",
        "secondary_sampling": "420",
    },
    {
        "name": "color_q75_444_to_q75_420",
        "description": "BGR JPEG quality 75 4:4:4 to quality 75 4:2:0",
        "color_path": "bgr",
        "primary_quality": 75,
        "secondary_quality": 75,
        "primary_sampling": "444",
        "secondary_sampling": "420",
    },
    {
        "name": "color_q75_420_to_q75_444",
        "description": "BGR JPEG quality 75 4:2:0 to quality 75 4:4:4",
        "color_path": "bgr",
        "primary_quality": 75,
        "secondary_quality": 75,
        "primary_sampling": "420",
        "secondary_sampling": "444",
    },
)
METRICS = {
    "laplacian_variance": laplacian_variance,
    "tenengrad_energy": tenengrad_energy,
}

TRIALS_CSV_NAME = "jpeg_history_trials.csv"
RESPONSE_CSV_NAME = "jpeg_history_response_summary.csv"
ANCHORS_CSV_NAME = "jpeg_history_calibration_anchors.csv"
CALIBRATION_CSV_NAME = "jpeg_history_calibration_summary.csv"
EXAMPLES_FIGURE_NAME = "jpeg_history_examples.png"
SENSITIVITY_FIGURE_NAME = "jpeg_history_sensitivity.png"


def make_patterns() -> dict[str, NDArray[np.uint8]]:
    """Create three deterministic synthetic BGR patterns on a padded canvas."""
    rows, columns = np.indices((SOURCE_SIZE, SOURCE_SIZE))
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

    horizontal = np.linspace(0.0, 1.0, SOURCE_SIZE, dtype=np.float64)
    vertical = horizontal[:, np.newaxis]
    blue = np.broadcast_to(30.0 + 170.0 * horizontal, (SOURCE_SIZE, SOURCE_SIZE))
    green = np.broadcast_to(45.0 + 130.0 * vertical, (SOURCE_SIZE, SOURCE_SIZE))
    red = 220.0 - 120.0 * (horizontal[np.newaxis, :] + vertical) / 2.0
    colored_targets = np.stack((blue, green, red), axis=2)
    colored_targets = np.clip(np.rint(colored_targets), 0, 255).astype(np.uint8)
    cv2.rectangle(colored_targets, (24, 24), (112, 104), (230, 35, 220), -1)
    cv2.circle(colored_targets, (184, 72), 42, (35, 230, 210), -1)
    cv2.line(colored_targets, (20, 228), (243, 139), (245, 245, 35), 9)
    cv2.circle(colored_targets, (78, 188), 30, (30, 50, 240), 7)

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


def add_channel_noise(
    image: NDArray[np.uint8], standard_deviation: int, seed: int
) -> NDArray[np.uint8]:
    """Add seeded independent Gaussian noise to each BGR channel."""
    if standard_deviation < 0:
        raise ValueError("standard_deviation must not be negative")
    if standard_deviation == 0:
        return image.copy()
    generator = np.random.default_rng(seed)
    noise = generator.normal(0.0, standard_deviation, image.shape)
    return np.clip(
        np.rint(image.astype(np.float64) + noise), 0, 255
    ).astype(np.uint8)


def trial_seed(
    pattern_index: int, blur_index: int, noise_index: int, trial: int
) -> int:
    """Return a unique deterministic seed for one source condition."""
    return (
        BASE_SEED
        + pattern_index * 100_000
        + blur_index * 10_000
        + noise_index * 1_000
        + trial
    )


def crop_at_offset(
    image: NDArray[np.uint8], offset: int
) -> NDArray[np.uint8]:
    """Return the fixed-size crop that controls second-stage grid alignment."""
    if offset < 0 or offset + CROP_SIZE > min(image.shape[:2]):
        raise ValueError("offset does not permit the declared crop")
    return image[offset : offset + CROP_SIZE, offset : offset + CROP_SIZE].copy()


def find_history(name: str) -> dict[str, object]:
    """Return one declared compression-history specification."""
    matches = [history for history in HISTORIES if history["name"] == name]
    if len(matches) != 1:
        raise ValueError(f"unknown history: {name}")
    return matches[0]


def apply_primary_compression(
    image: NDArray[np.uint8], history: dict[str, object]
) -> NDArray[np.uint8]:
    """Apply the declared primary JPEG stage."""
    quality = int(history["primary_quality"])
    if history["color_path"] == "grayscale":
        return jpeg_encode_decode(to_grayscale(image), quality=quality)
    return jpeg_encode_decode(
        image,
        quality=quality,
        chroma_sampling=str(history["primary_sampling"]),
    )


def apply_secondary_compression(
    primary_crop: NDArray[np.uint8], history: dict[str, object]
) -> NDArray[np.uint8]:
    """Apply the declared secondary JPEG stage and return grayscale pixels."""
    quality = int(history["secondary_quality"])
    if history["color_path"] == "grayscale":
        return jpeg_encode_decode(primary_crop, quality=quality)
    decoded = jpeg_encode_decode(
        primary_crop,
        quality=quality,
        chroma_sampling=str(history["secondary_sampling"]),
    )
    return to_grayscale(decoded)


def run_history(
    source: NDArray[np.uint8],
    history: dict[str, object],
    alignment: str,
) -> tuple[NDArray[np.uint8], NDArray[np.uint8], NDArray[np.uint8]]:
    """Return uncompressed, primary-only, and secondary decoded crops."""
    offset = ALIGNMENTS[alignment]
    primary = apply_primary_compression(source, history)
    primary_crop = crop_at_offset(primary, offset)
    uncompressed_crop = to_grayscale(crop_at_offset(source, offset))
    primary_gray = to_grayscale(primary_crop)
    final_gray = apply_secondary_compression(primary_crop, history)
    return uncompressed_crop, primary_gray, final_gray


def build_calibration_anchors(
) -> tuple[list[dict[str, str]], dict[tuple[str, str, str], float]]:
    """Create per-pattern and per-crop midpoint rules from uncompressed inputs."""
    rows: list[dict[str, str]] = []
    thresholds: dict[tuple[str, str, str], float] = {}
    for pattern, image in make_patterns().items():
        blurred = apply_gaussian_blur(image, 3)
        for alignment, offset in ALIGNMENTS.items():
            sharp_crop = to_grayscale(crop_at_offset(image, offset))
            blurred_crop = to_grayscale(crop_at_offset(blurred, offset))
            for metric_name, metric in METRICS.items():
                sharp_score = metric(sharp_crop)
                blurred_score = metric(blurred_crop)
                threshold = (sharp_score + blurred_score) / 2.0
                thresholds[(pattern, alignment, metric_name)] = threshold
                rows.append(
                    {
                        "pattern": pattern,
                        "alignment": alignment,
                        "crop_offset": str(offset),
                        "metric": metric_name,
                        "source_pipeline": "uncompressed grayscale crop",
                        "source_noise_std": "0",
                        "sharp_blur_sigma": "0",
                        "blurred_blur_sigma": "3",
                        "sharp_score": f"{sharp_score:.6f}",
                        "blurred_score": f"{blurred_score:.6f}",
                        "midpoint_threshold": f"{threshold:.6f}",
                    }
                )
    return rows, thresholds


def run_trials(
    thresholds: dict[tuple[str, str, str], float],
) -> list[dict[str, str]]:
    """Run every quality-order, alignment, sampling, blur, and noise control."""
    rows: list[dict[str, str]] = []
    for pattern_index, (pattern, image) in enumerate(make_patterns().items()):
        for blur_index, blur_sigma in enumerate(BLUR_SIGMAS):
            blurred = apply_gaussian_blur(image, blur_sigma)
            for noise_index, noise_std in enumerate(NOISE_STANDARD_DEVIATIONS):
                for trial in range(NOISE_TRIALS):
                    seed = trial_seed(
                        pattern_index, blur_index, noise_index, trial
                    )
                    source = add_channel_noise(blurred, noise_std, seed)
                    for history in HISTORIES:
                        primary = apply_primary_compression(source, history)
                        for alignment, offset in ALIGNMENTS.items():
                            primary_crop = crop_at_offset(primary, offset)
                            uncompressed_crop = to_grayscale(
                                crop_at_offset(source, offset)
                            )
                            primary_gray = to_grayscale(primary_crop)
                            final_gray = apply_secondary_compression(
                                primary_crop, history
                            )
                            for metric_name, metric in METRICS.items():
                                score = metric(final_gray)
                                primary_score = metric(primary_gray)
                                uncompressed_score = metric(uncompressed_crop)
                                threshold = thresholds[
                                    (pattern, alignment, metric_name)
                                ]
                                expected_class = (
                                    "sharp"
                                    if blur_sigma == 0
                                    else "blurred"
                                    if blur_sigma == 3
                                    else "intermediate"
                                )
                                rows.append(
                                    {
                                        "pattern": pattern,
                                        "blur_sigma": str(blur_sigma),
                                        "noise_std": str(noise_std),
                                        "trial": str(trial),
                                        "seed": str(seed),
                                        "alignment": alignment,
                                        "crop_offset": str(offset),
                                        "history": str(history["name"]),
                                        "history_description": str(
                                            history["description"]
                                        ),
                                        "color_path": str(history["color_path"]),
                                        "primary_quality": str(
                                            history["primary_quality"]
                                        ),
                                        "secondary_quality": str(
                                            history["secondary_quality"]
                                        ),
                                        "primary_sampling": str(
                                            history["primary_sampling"] or "none"
                                        ),
                                        "secondary_sampling": str(
                                            history["secondary_sampling"] or "none"
                                        ),
                                        "metric": metric_name,
                                        "score": f"{score:.6f}",
                                        "primary_only_score": (
                                            f"{primary_score:.6f}"
                                        ),
                                        "ratio_to_primary_only": (
                                            f"{score / primary_score:.6f}"
                                        ),
                                        "uncompressed_same_crop_score": (
                                            f"{uncompressed_score:.6f}"
                                        ),
                                        "ratio_to_uncompressed_same_crop": (
                                            f"{score / uncompressed_score:.6f}"
                                        ),
                                        "calibration_threshold": (
                                            f"{threshold:.6f}"
                                        ),
                                        "expected_class": expected_class,
                                        "predicted_blurred": str(
                                            int(score < threshold)
                                        ),
                                    }
                                )
    return rows


def summarize_responses(
    rows: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Summarize final response relative to matched primary and raw crops."""
    summary_rows: list[dict[str, str]] = []
    for history in HISTORIES:
        for alignment in ALIGNMENTS:
            for noise_std in NOISE_STANDARD_DEVIATIONS:
                for blur_sigma in BLUR_SIGMAS:
                    for metric in METRICS:
                        group = [
                            row
                            for row in rows
                            if row["history"] == history["name"]
                            and row["alignment"] == alignment
                            and int(row["noise_std"]) == noise_std
                            and int(row["blur_sigma"]) == blur_sigma
                            and row["metric"] == metric
                        ]
                        scores = np.array(
                            [float(row["score"]) for row in group],
                            dtype=np.float64,
                        )
                        primary_ratios = np.array(
                            [
                                float(row["ratio_to_primary_only"])
                                for row in group
                            ],
                            dtype=np.float64,
                        )
                        uncompressed_ratios = np.array(
                            [
                                float(row["ratio_to_uncompressed_same_crop"])
                                for row in group
                            ],
                            dtype=np.float64,
                        )
                        summary_rows.append(
                            {
                                "history": str(history["name"]),
                                "history_description": str(
                                    history["description"]
                                ),
                                "alignment": alignment,
                                "crop_offset": str(ALIGNMENTS[alignment]),
                                "noise_std": str(noise_std),
                                "blur_sigma": str(blur_sigma),
                                "metric": metric,
                                "observations": str(len(group)),
                                "score_mean": f"{np.mean(scores):.6f}",
                                "score_sample_std": (
                                    f"{np.std(scores, ddof=1):.6f}"
                                ),
                                "primary_ratio_mean": (
                                    f"{np.mean(primary_ratios):.6f}"
                                ),
                                "primary_ratio_sample_std": (
                                    f"{np.std(primary_ratios, ddof=1):.6f}"
                                ),
                                "primary_ratio_p10": (
                                    f"{np.quantile(primary_ratios, 0.1):.6f}"
                                ),
                                "primary_ratio_median": (
                                    f"{np.median(primary_ratios):.6f}"
                                ),
                                "primary_ratio_p90": (
                                    f"{np.quantile(primary_ratios, 0.9):.6f}"
                                ),
                                "uncompressed_ratio_mean": (
                                    f"{np.mean(uncompressed_ratios):.6f}"
                                ),
                                "uncompressed_ratio_sample_std": (
                                    f"{np.std(uncompressed_ratios, ddof=1):.6f}"
                                ),
                            }
                        )
    return summary_rows


def summarize_calibration_transfer(
    rows: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Evaluate uncompressed midpoint transfer and blur-order preservation."""
    summary_rows: list[dict[str, str]] = []
    for history in HISTORIES:
        for alignment in ALIGNMENTS:
            for noise_std in NOISE_STANDARD_DEVIATIONS:
                for metric in METRICS:
                    group = [
                        row
                        for row in rows
                        if row["history"] == history["name"]
                        and row["alignment"] == alignment
                        and int(row["noise_std"]) == noise_std
                        and row["metric"] == metric
                    ]
                    sharp = [
                        row for row in group if row["expected_class"] == "sharp"
                    ]
                    blurred = [
                        row
                        for row in group
                        if row["expected_class"] == "blurred"
                    ]
                    false_blur_count = sum(
                        int(row["predicted_blurred"]) for row in sharp
                    )
                    blur_miss_count = sum(
                        1 - int(row["predicted_blurred"]) for row in blurred
                    )
                    false_blur_rate = false_blur_count / len(sharp)
                    blur_miss_rate = blur_miss_count / len(blurred)
                    balanced_accuracy = 1.0 - (
                        false_blur_rate + blur_miss_rate
                    ) / 2.0

                    adjacent_pair_count = 0
                    violation_count = 0
                    fully_ordered_count = 0
                    sequence_count = 0
                    for pattern in make_patterns():
                        for trial in range(NOISE_TRIALS):
                            sequence = sorted(
                                (
                                    row
                                    for row in group
                                    if row["pattern"] == pattern
                                    and int(row["trial"]) == trial
                                ),
                                key=lambda row: int(row["blur_sigma"]),
                            )
                            scores = [float(row["score"]) for row in sequence]
                            pair_violations = sum(
                                right >= left
                                for left, right in zip(scores, scores[1:])
                            )
                            adjacent_pair_count += len(scores) - 1
                            violation_count += pair_violations
                            fully_ordered_count += int(pair_violations == 0)
                            sequence_count += 1

                    summary_rows.append(
                        {
                            "history": str(history["name"]),
                            "history_description": str(history["description"]),
                            "alignment": alignment,
                            "crop_offset": str(ALIGNMENTS[alignment]),
                            "noise_std": str(noise_std),
                            "metric": metric,
                            "calibration_source": (
                                "per-pattern uncompressed same-crop noise-0 "
                                "sigma-0/sigma-3 midpoint"
                            ),
                            "anchor_observations": str(len(sharp) + len(blurred)),
                            "balanced_accuracy": f"{balanced_accuracy:.6f}",
                            "sharp_false_blur_count": str(false_blur_count),
                            "sharp_false_blur_rate": f"{false_blur_rate:.6f}",
                            "blurred_miss_count": str(blur_miss_count),
                            "blurred_miss_rate": f"{blur_miss_rate:.6f}",
                            "adjacent_pair_count": str(adjacent_pair_count),
                            "adjacent_order_violation_count": str(
                                violation_count
                            ),
                            "adjacent_order_violation_rate": (
                                f"{violation_count / adjacent_pair_count:.6f}"
                            ),
                            "sequence_count": str(sequence_count),
                            "fully_ordered_sequence_rate": (
                                f"{fully_ordered_count / sequence_count:.6f}"
                            ),
                        }
                    )
    return summary_rows


def find_response(
    rows: Sequence[dict[str, str]],
    history: str,
    alignment: str,
    noise_std: int,
    blur_sigma: int,
    metric: str,
) -> dict[str, str]:
    """Find one response-summary row."""
    matches = [
        row
        for row in rows
        if row["history"] == history
        and row["alignment"] == alignment
        and int(row["noise_std"]) == noise_std
        and int(row["blur_sigma"]) == blur_sigma
        and row["metric"] == metric
    ]
    if len(matches) != 1:
        raise RuntimeError("Expected one response summary row.")
    return matches[0]


def find_calibration(
    rows: Sequence[dict[str, str]],
    history: str,
    alignment: str,
    noise_std: int,
    metric: str,
) -> dict[str, str]:
    """Find one calibration-summary row."""
    matches = [
        row
        for row in rows
        if row["history"] == history
        and row["alignment"] == alignment
        and int(row["noise_std"]) == noise_std
        and row["metric"] == metric
    ]
    if len(matches) != 1:
        raise RuntimeError("Expected one calibration summary row.")
    return matches[0]


def validate_expected_relationships(
    trial_rows: Sequence[dict[str, str]],
    response_rows: Sequence[dict[str, str]],
    anchor_rows: Sequence[dict[str, str]],
    calibration_rows: Sequence[dict[str, str]],
) -> None:
    """Validate row counts and bounded relationships used in the note."""
    pattern_count = len(make_patterns())
    expected_trials = (
        pattern_count
        * len(BLUR_SIGMAS)
        * len(NOISE_STANDARD_DEVIATIONS)
        * NOISE_TRIALS
        * len(HISTORIES)
        * len(ALIGNMENTS)
        * len(METRICS)
    )
    if len(trial_rows) != expected_trials:
        raise RuntimeError("Unexpected number of trial rows.")
    if len(response_rows) != (
        len(HISTORIES)
        * len(ALIGNMENTS)
        * len(NOISE_STANDARD_DEVIATIONS)
        * len(BLUR_SIGMAS)
        * len(METRICS)
    ):
        raise RuntimeError("Unexpected number of response rows.")
    if len(anchor_rows) != pattern_count * len(ALIGNMENTS) * len(METRICS):
        raise RuntimeError("Unexpected number of calibration anchors.")
    if len(calibration_rows) != (
        len(HISTORIES)
        * len(ALIGNMENTS)
        * len(NOISE_STANDARD_DEVIATIONS)
        * len(METRICS)
    ):
        raise RuntimeError("Unexpected number of calibration rows.")
    if not all(
        float(row["sharp_score"]) > float(row["blurred_score"])
        for row in anchor_rows
    ):
        raise RuntimeError("Clean sharp anchors must exceed blurred anchors.")

    for metric in METRICS:
        high_then_low = float(
            find_response(
                response_rows,
                "gray_q95_to_q75",
                "aligned",
                0,
                0,
                metric,
            )["primary_ratio_mean"]
        )
        low_then_high = float(
            find_response(
                response_rows,
                "gray_q75_to_q95",
                "aligned",
                0,
                0,
                metric,
            )["primary_ratio_mean"]
        )
        if np.isclose(high_then_low, low_then_high, rtol=0.0, atol=1e-6):
            raise RuntimeError("JPEG quality order must change the bounded mean.")

        aligned = float(
            find_response(
                response_rows,
                "gray_q75_to_q75",
                "aligned",
                0,
                0,
                metric,
            )["primary_ratio_mean"]
        )
        shifted = float(
            find_response(
                response_rows,
                "gray_q75_to_q75",
                "shifted_4x4",
                0,
                0,
                metric,
            )["primary_ratio_mean"]
        )
        if np.isclose(aligned, shifted, rtol=0.0, atol=1e-6):
            raise RuntimeError("Grid shift must change the bounded mean.")

        sampling_444 = float(
            find_response(
                response_rows,
                "color_q75_444_to_q75_444",
                "aligned",
                0,
                0,
                metric,
            )["primary_ratio_mean"]
        )
        sampling_420 = float(
            find_response(
                response_rows,
                "color_q75_420_to_q75_420",
                "aligned",
                0,
                0,
                metric,
            )["primary_ratio_mean"]
        )
        if np.isclose(sampling_444, sampling_420, rtol=0.0, atol=1e-6):
            raise RuntimeError("Chroma sampling must change the bounded mean.")

    if all(
        np.isclose(float(row["balanced_accuracy"]), 1.0)
        for row in calibration_rows
    ):
        raise RuntimeError("A JPEG history must expose calibration drift.")

    clean_blurred = float(
        find_response(
            response_rows,
            "gray_q75_to_q75",
            "shifted_4x4",
            0,
            3,
            "laplacian_variance",
        )["score_mean"]
    )
    noisy_blurred = float(
        find_response(
            response_rows,
            "gray_q75_to_q75",
            "shifted_4x4",
            15,
            3,
            "laplacian_variance",
        )["score_mean"]
    )
    if noisy_blurred <= clean_blurred:
        raise RuntimeError("Noise must raise the bounded blurred Laplacian mean.")


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


def write_examples_figure(output_path: Path) -> None:
    """Visualize aligned, shifted, and explicit sampling controls."""
    source = make_patterns()["chromatic_stripes"]
    noisy_blurred = add_channel_noise(
        apply_gaussian_blur(source, 2),
        standard_deviation=15,
        seed=trial_seed(1, 2, 1, 0),
    )
    conditions = (
        ("sharp, noise 0", source),
        ("sigma 2, noise 15", noisy_blurred),
    )
    history_420 = find_history("color_q75_420_to_q75_420")
    history_444 = find_history("color_q75_444_to_q75_444")
    titles = (
        "uncompressed crop",
        "primary q75 4:2:0",
        "secondary aligned 4:2:0",
        "secondary shifted 4:2:0",
        "secondary aligned 4:4:4",
    )

    figure, axes = plt.subplots(2, 5, figsize=(12.5, 5.2))
    for row_index, (row_label, image) in enumerate(conditions):
        uncompressed, primary_420, aligned_420 = run_history(
            image, history_420, "aligned"
        )
        _, _, shifted_420 = run_history(image, history_420, "shifted_4x4")
        _, _, aligned_444 = run_history(image, history_444, "aligned")
        views = (
            uncompressed,
            primary_420,
            aligned_420,
            shifted_420,
            aligned_444,
        )
        for column_index, (view, title) in enumerate(zip(views, titles)):
            axis = axes[row_index, column_index]
            axis.imshow(view, cmap="gray", vmin=0, vmax=255)
            if row_index == 0:
                axis.set_title(title, fontsize=9)
            if column_index == 0:
                axis.set_ylabel(row_label, fontsize=9)
            axis.set_xticks([])
            axis.set_yticks([])
    figure.suptitle("Synthetic JPEG history controls")
    figure.tight_layout()
    figure.savefig(
        output_path,
        dpi=150,
        metadata={"Software": "research-notes v0.8.0"},
    )
    plt.close(figure)


def write_sensitivity_figure(
    response_rows: Sequence[dict[str, str]],
    calibration_rows: Sequence[dict[str, str]],
    output_path: Path,
) -> None:
    """Plot quality order, grid shift, sampling, and calibration transfer."""
    metric_layout = (
        ("laplacian_variance", "Laplacian variance"),
        ("tenengrad_energy", "Tenengrad energy"),
    )
    labels = {
        "gray_q95_to_q75": "q95 -> q75",
        "gray_q50_to_q75": "q50 -> q75",
        "gray_q75_to_q95": "q75 -> q95",
        "gray_q75_to_q50": "q75 -> q50",
        "color_q75_444_to_q75_444": "4:4:4 -> 4:4:4",
        "color_q75_420_to_q75_420": "4:2:0 -> 4:2:0",
        "color_q75_444_to_q75_420": "4:4:4 -> 4:2:0",
        "color_q75_420_to_q75_444": "4:2:0 -> 4:4:4",
    }
    figure, axes = plt.subplots(4, 2, figsize=(12, 14), constrained_layout=True)
    colors = ("#2563eb", "#dc2626", "#059669", "#d97706")

    for column, (metric, metric_label) in enumerate(metric_layout):
        quality_histories = (
            "gray_q95_to_q75",
            "gray_q50_to_q75",
            "gray_q75_to_q95",
            "gray_q75_to_q50",
        )
        for history, color in zip(quality_histories, colors):
            values = [
                float(
                    find_response(
                        response_rows,
                        history,
                        "aligned",
                        0,
                        sigma,
                        metric,
                    )["primary_ratio_mean"]
                )
                for sigma in BLUR_SIGMAS
            ]
            axes[0, column].plot(
                BLUR_SIGMAS,
                values,
                marker="o",
                label=labels[history],
                color=color,
            )
        axes[0, column].axhline(1.0, color="#9ca3af", linewidth=1)
        axes[0, column].set_title(f"{metric_label}: quality order")
        axes[0, column].set_ylabel("secondary / primary score")
        axes[0, column].legend(fontsize=8)

        for alignment, color in zip(ALIGNMENTS, ("#2563eb", "#dc2626")):
            values = [
                float(
                    find_response(
                        response_rows,
                        "gray_q75_to_q75",
                        alignment,
                        0,
                        sigma,
                        metric,
                    )["primary_ratio_mean"]
                )
                for sigma in BLUR_SIGMAS
            ]
            axes[1, column].plot(
                BLUR_SIGMAS,
                values,
                marker="o",
                label=alignment.replace("_", " "),
                color=color,
            )
        axes[1, column].axhline(1.0, color="#9ca3af", linewidth=1)
        axes[1, column].set_title(f"{metric_label}: q75 grid alignment")
        axes[1, column].set_ylabel("secondary / primary score")
        axes[1, column].legend(fontsize=8)

        sampling_histories = (
            "color_q75_444_to_q75_444",
            "color_q75_420_to_q75_420",
            "color_q75_444_to_q75_420",
            "color_q75_420_to_q75_444",
        )
        for history, color in zip(sampling_histories, colors):
            values = [
                float(
                    find_response(
                        response_rows,
                        history,
                        "aligned",
                        0,
                        sigma,
                        metric,
                    )["uncompressed_ratio_mean"]
                )
                for sigma in BLUR_SIGMAS
            ]
            axes[2, column].plot(
                BLUR_SIGMAS,
                values,
                marker="o",
                label=labels[history],
                color=color,
            )
        axes[2, column].axhline(1.0, color="#9ca3af", linewidth=1)
        axes[2, column].set_title(f"{metric_label}: chroma sampling path")
        axes[2, column].set_ylabel("final / uncompressed score")
        axes[2, column].legend(fontsize=8)

        calibration_histories = (
            "gray_q75_to_q75",
            "gray_q95_to_q75",
            "color_q75_444_to_q75_444",
            "color_q75_420_to_q75_420",
        )
        positions = np.arange(len(calibration_histories))
        width = 0.36
        for index, noise_std in enumerate(NOISE_STANDARD_DEVIATIONS):
            values = [
                float(
                    find_calibration(
                        calibration_rows,
                        history,
                        "shifted_4x4",
                        noise_std,
                        metric,
                    )["balanced_accuracy"]
                )
                for history in calibration_histories
            ]
            axes[3, column].bar(
                positions + (index - 0.5) * width,
                values,
                width,
                label=f"noise {noise_std}",
                color=("#2563eb", "#dc2626")[index],
            )
        axes[3, column].set_xticks(
            positions,
            ("gray 75->75", "gray 95->75", "444->444", "420->420"),
            rotation=20,
            ha="right",
        )
        axes[3, column].set_ylim(0.0, 1.05)
        axes[3, column].set_title(f"{metric_label}: fixed-anchor transfer")
        axes[3, column].set_ylabel("balanced accuracy")
        axes[3, column].legend(fontsize=8)

        for row in range(3):
            axes[row, column].set_xlabel("Gaussian blur sigma")
            axes[row, column].set_xticks(BLUR_SIGMAS)
            axes[row, column].grid(alpha=0.2)
        axes[3, column].grid(axis="y", alpha=0.2)

    figure.suptitle(
        "JPEG compression history changes derivative-metric response",
        fontsize=14,
    )
    figure.savefig(
        output_path,
        dpi=150,
        metadata={"Software": "research-notes v0.8.0"},
    )
    plt.close(figure)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Run the deterministic JPEG compression-history experiment."
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
    anchor_rows, thresholds = build_calibration_anchors()
    trial_rows = run_trials(thresholds)
    response_rows = summarize_responses(trial_rows)
    calibration_rows = summarize_calibration_transfer(trial_rows)
    validate_expected_relationships(
        trial_rows,
        response_rows,
        anchor_rows,
        calibration_rows,
    )
    write_csv(trial_rows, args.output_dir / TRIALS_CSV_NAME)
    write_csv(response_rows, args.output_dir / RESPONSE_CSV_NAME)
    write_csv(anchor_rows, args.output_dir / ANCHORS_CSV_NAME)
    write_csv(calibration_rows, args.output_dir / CALIBRATION_CSV_NAME)
    write_examples_figure(args.output_dir / EXAMPLES_FIGURE_NAME)
    write_sensitivity_figure(
        response_rows,
        calibration_rows,
        args.output_dir / SENSITIVITY_FIGURE_NAME,
    )
    print(
        f"Wrote {len(trial_rows)} trial rows, {len(response_rows)} response "
        f"rows, {len(anchor_rows)} anchors, and {len(calibration_rows)} "
        f"calibration rows to {args.output_dir}."
    )


if __name__ == "__main__":
    main()
