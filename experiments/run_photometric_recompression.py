"""Evaluate photometric normalization and repeated JPEG recompression drift."""

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
    gamma_transform,
    laplacian_variance,
    linear_intensity_transform,
    minmax_normalize,
    repeated_jpeg_round_trip,
    tenengrad_energy,
    to_grayscale,
)


IMAGE_SIZE = 256
BLUR_SIGMAS = (0, 1, 2, 3)
NOISE_STANDARD_DEVIATIONS = (0, 5, 15)
NOISE_TRIALS = 10
BASE_SEED = 20261201
JPEG_QUALITY = 75
JPEG_ROUNDS = (1, 2, 5)
PIPELINES = (
    "identity",
    "brightness_minus_30",
    "brightness_plus_30",
    "contrast_0_5",
    "contrast_1_25",
    "gamma_0_7",
    "gamma_1_4",
    "minmax_normalize",
    "gray_jpeg_q75_r1",
    "gray_jpeg_q75_r2",
    "gray_jpeg_q75_r5",
    "color_jpeg_q75_r1_then_gray",
    "color_jpeg_q75_r2_then_gray",
    "color_jpeg_q75_r5_then_gray",
    "gamma_0_7_then_gray_jpeg_q75_r2",
    "gray_jpeg_q75_r2_then_gamma_0_7",
)
PIPELINE_DESCRIPTIONS = {
    "identity": "BGR-to-grayscale conversion only",
    "brightness_minus_30": "Grayscale linear transform with beta -30",
    "brightness_plus_30": "Grayscale linear transform with beta +30",
    "contrast_0_5": "Grayscale linear transform with alpha 0.50",
    "contrast_1_25": "Grayscale linear transform with alpha 1.25",
    "gamma_0_7": "Grayscale power-law transform with gamma 0.7",
    "gamma_1_4": "Grayscale power-law transform with gamma 1.4",
    "minmax_normalize": "Grayscale global min-max normalization",
    "gray_jpeg_q75_r1": "Grayscale JPEG quality 75, one round",
    "gray_jpeg_q75_r2": "Grayscale JPEG quality 75, two rounds",
    "gray_jpeg_q75_r5": "Grayscale JPEG quality 75, five rounds",
    "color_jpeg_q75_r1_then_gray": (
        "BGR JPEG quality 75, one round, then grayscale"
    ),
    "color_jpeg_q75_r2_then_gray": (
        "BGR JPEG quality 75, two rounds, then grayscale"
    ),
    "color_jpeg_q75_r5_then_gray": (
        "BGR JPEG quality 75, five rounds, then grayscale"
    ),
    "gamma_0_7_then_gray_jpeg_q75_r2": (
        "Grayscale gamma 0.7, then JPEG quality 75 twice"
    ),
    "gray_jpeg_q75_r2_then_gamma_0_7": (
        "Grayscale JPEG quality 75 twice, then gamma 0.7"
    ),
}
METRICS = {
    "laplacian_variance": laplacian_variance,
    "tenengrad_energy": tenengrad_energy,
}

TRIALS_CSV_NAME = "photometric_recompression_trials.csv"
RESPONSE_CSV_NAME = "photometric_recompression_response_summary.csv"
ANCHORS_CSV_NAME = "photometric_recompression_calibration_anchors.csv"
CALIBRATION_CSV_NAME = "photometric_recompression_calibration_summary.csv"
EXAMPLES_FIGURE_NAME = "photometric_recompression_examples.png"
DRIFT_FIGURE_NAME = "photometric_recompression_drift.png"


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
    """Apply a Gaussian blur or return a copy for the zero control."""
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
    """Return a unique deterministic seed for one source image condition."""
    return (
        BASE_SEED
        + pattern_index * 100_000
        + blur_index * 10_000
        + noise_index * 1_000
        + trial
    )


def apply_pipeline(
    image: NDArray[np.uint8], pipeline: str
) -> NDArray[np.uint8]:
    """Apply one declared pipeline and return an 8-bit grayscale image."""
    grayscale = to_grayscale(image)
    if pipeline == "identity":
        return grayscale
    if pipeline == "brightness_minus_30":
        return linear_intensity_transform(grayscale, alpha=1.0, beta=-30.0)
    if pipeline == "brightness_plus_30":
        return linear_intensity_transform(grayscale, alpha=1.0, beta=30.0)
    if pipeline == "contrast_0_5":
        return linear_intensity_transform(grayscale, alpha=0.5, beta=0.0)
    if pipeline == "contrast_1_25":
        return linear_intensity_transform(grayscale, alpha=1.25, beta=0.0)
    if pipeline == "gamma_0_7":
        return gamma_transform(grayscale, gamma=0.7)
    if pipeline == "gamma_1_4":
        return gamma_transform(grayscale, gamma=1.4)
    if pipeline == "minmax_normalize":
        return minmax_normalize(grayscale)
    if pipeline == "gamma_0_7_then_gray_jpeg_q75_r2":
        corrected = gamma_transform(grayscale, gamma=0.7)
        return repeated_jpeg_round_trip(
            corrected, quality=JPEG_QUALITY, rounds=2
        )
    if pipeline == "gray_jpeg_q75_r2_then_gamma_0_7":
        compressed = repeated_jpeg_round_trip(
            grayscale, quality=JPEG_QUALITY, rounds=2
        )
        return gamma_transform(compressed, gamma=0.7)
    if pipeline.startswith("gray_jpeg_q75_r"):
        rounds = int(pipeline.rsplit("r", maxsplit=1)[1])
        return repeated_jpeg_round_trip(
            grayscale, quality=JPEG_QUALITY, rounds=rounds
        )
    if pipeline.startswith("color_jpeg_q75_r"):
        rounds = int(pipeline.split("_r", maxsplit=1)[1].split("_", 1)[0])
        compressed = repeated_jpeg_round_trip(
            image, quality=JPEG_QUALITY, rounds=rounds
        )
        return to_grayscale(compressed)
    raise ValueError(f"unknown pipeline: {pipeline}")


def build_calibration_anchors(
) -> tuple[
    list[dict[str, str]],
    dict[tuple[str, str], float],
    dict[tuple[str, str], float],
]:
    """Create per-pattern midpoint rules from clean identity endpoints."""
    rows: list[dict[str, str]] = []
    thresholds: dict[tuple[str, str], float] = {}
    sharp_scores: dict[tuple[str, str], float] = {}
    for pattern, image in make_patterns().items():
        sharp = apply_pipeline(image, "identity")
        blurred = apply_pipeline(apply_gaussian_blur(image, 3), "identity")
        for metric_name, metric in METRICS.items():
            sharp_score = metric(sharp)
            blurred_score = metric(blurred)
            threshold = (sharp_score + blurred_score) / 2.0
            key = (pattern, metric_name)
            thresholds[key] = threshold
            sharp_scores[key] = sharp_score
            rows.append(
                {
                    "pattern": pattern,
                    "metric": metric_name,
                    "source_pipeline": "identity",
                    "source_noise_std": "0",
                    "sharp_blur_sigma": "0",
                    "blurred_blur_sigma": "3",
                    "sharp_score": f"{sharp_score:.6f}",
                    "blurred_score": f"{blurred_score:.6f}",
                    "midpoint_threshold": f"{threshold:.6f}",
                }
            )
    return rows, thresholds, sharp_scores


def run_trials(
    thresholds: dict[tuple[str, str], float],
    sharp_scores: dict[tuple[str, str], float],
) -> list[dict[str, str]]:
    """Run all blur, noise, photometric, and recompression conditions."""
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
                    identity = apply_pipeline(source, "identity")
                    identity_scores = {
                        name: metric(identity) for name, metric in METRICS.items()
                    }
                    for pipeline in PIPELINES:
                        processed = apply_pipeline(source, pipeline)
                        low_fraction = float(np.mean(processed == 0))
                        high_fraction = float(np.mean(processed == 255))
                        for metric_name, metric in METRICS.items():
                            score = metric(processed)
                            identity_score = identity_scores[metric_name]
                            key = (pattern, metric_name)
                            threshold = thresholds[key]
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
                                    "pipeline": pipeline,
                                    "pipeline_description": (
                                        PIPELINE_DESCRIPTIONS[pipeline]
                                    ),
                                    "metric": metric_name,
                                    "score": f"{score:.6f}",
                                    "identity_same_input_score": (
                                        f"{identity_score:.6f}"
                                    ),
                                    "ratio_to_identity_same_input": (
                                        f"{score / identity_score:.6f}"
                                    ),
                                    "identity_sharp_anchor": (
                                        f"{sharp_scores[key]:.6f}"
                                    ),
                                    "ratio_to_identity_sharp_anchor": (
                                        f"{score / sharp_scores[key]:.6f}"
                                    ),
                                    "processed_min": str(int(processed.min())),
                                    "processed_max": str(int(processed.max())),
                                    "zero_fraction": f"{low_fraction:.6f}",
                                    "full_scale_fraction": f"{high_fraction:.6f}",
                                    "calibration_threshold": f"{threshold:.6f}",
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
    """Summarize score and saturation drift for each condition."""
    summary_rows: list[dict[str, str]] = []
    for pipeline in PIPELINES:
        for noise_std in NOISE_STANDARD_DEVIATIONS:
            for blur_sigma in BLUR_SIGMAS:
                for metric in METRICS:
                    group = [
                        row
                        for row in rows
                        if row["pipeline"] == pipeline
                        and int(row["noise_std"]) == noise_std
                        and int(row["blur_sigma"]) == blur_sigma
                        and row["metric"] == metric
                    ]
                    same_input = np.array(
                        [
                            float(row["ratio_to_identity_same_input"])
                            for row in group
                        ],
                        dtype=np.float64,
                    )
                    sharp_anchor = np.array(
                        [
                            float(row["ratio_to_identity_sharp_anchor"])
                            for row in group
                        ],
                        dtype=np.float64,
                    )
                    zero_fractions = np.array(
                        [float(row["zero_fraction"]) for row in group],
                        dtype=np.float64,
                    )
                    full_scale_fractions = np.array(
                        [float(row["full_scale_fraction"]) for row in group],
                        dtype=np.float64,
                    )
                    summary_rows.append(
                        {
                            "pipeline": pipeline,
                            "pipeline_description": (
                                PIPELINE_DESCRIPTIONS[pipeline]
                            ),
                            "noise_std": str(noise_std),
                            "blur_sigma": str(blur_sigma),
                            "metric": metric,
                            "observations": str(len(group)),
                            "same_input_ratio_mean": (
                                f"{np.mean(same_input):.6f}"
                            ),
                            "same_input_ratio_sample_std": (
                                f"{np.std(same_input, ddof=1):.6f}"
                            ),
                            "same_input_ratio_p10": (
                                f"{np.quantile(same_input, 0.1):.6f}"
                            ),
                            "same_input_ratio_median": (
                                f"{np.median(same_input):.6f}"
                            ),
                            "same_input_ratio_p90": (
                                f"{np.quantile(same_input, 0.9):.6f}"
                            ),
                            "sharp_anchor_ratio_mean": (
                                f"{np.mean(sharp_anchor):.6f}"
                            ),
                            "sharp_anchor_ratio_sample_std": (
                                f"{np.std(sharp_anchor, ddof=1):.6f}"
                            ),
                            "zero_fraction_mean": (
                                f"{np.mean(zero_fractions):.6f}"
                            ),
                            "full_scale_fraction_mean": (
                                f"{np.mean(full_scale_fractions):.6f}"
                            ),
                        }
                    )
    return summary_rows


def summarize_calibration_transfer(
    rows: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Evaluate fixed identity anchors and blur-order preservation."""
    summary_rows: list[dict[str, str]] = []
    for pipeline in PIPELINES:
        for noise_std in NOISE_STANDARD_DEVIATIONS:
            for metric in METRICS:
                group = [
                    row
                    for row in rows
                    if row["pipeline"] == pipeline
                    and int(row["noise_std"]) == noise_std
                    and row["metric"] == metric
                ]
                sharp = [row for row in group if row["expected_class"] == "sharp"]
                blurred = [
                    row for row in group if row["expected_class"] == "blurred"
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
                        "pipeline": pipeline,
                        "pipeline_description": PIPELINE_DESCRIPTIONS[pipeline],
                        "noise_std": str(noise_std),
                        "metric": metric,
                        "calibration_source": (
                            "per-pattern identity noise-0 sigma-0/sigma-3 midpoint"
                        ),
                        "anchor_observations": str(len(sharp) + len(blurred)),
                        "balanced_accuracy": f"{balanced_accuracy:.6f}",
                        "sharp_false_blur_count": str(false_blur_count),
                        "sharp_false_blur_rate": f"{false_blur_rate:.6f}",
                        "blurred_miss_count": str(blur_miss_count),
                        "blurred_miss_rate": f"{blur_miss_rate:.6f}",
                        "adjacent_pair_count": str(adjacent_pair_count),
                        "adjacent_order_violation_count": str(violation_count),
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


def _find_response(
    rows: Sequence[dict[str, str]],
    pipeline: str,
    noise_std: int,
    blur_sigma: int,
    metric: str,
) -> dict[str, str]:
    """Find one response-summary row."""
    matches = [
        row
        for row in rows
        if row["pipeline"] == pipeline
        and int(row["noise_std"]) == noise_std
        and int(row["blur_sigma"]) == blur_sigma
        and row["metric"] == metric
    ]
    if len(matches) != 1:
        raise RuntimeError("Expected one response summary row.")
    return matches[0]


def _find_calibration(
    rows: Sequence[dict[str, str]],
    pipeline: str,
    noise_std: int,
    metric: str,
) -> dict[str, str]:
    """Find one calibration-summary row."""
    matches = [
        row
        for row in rows
        if row["pipeline"] == pipeline
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
    """Validate counts and bounded relationships used in the note."""
    pattern_count = len(make_patterns())
    expected_trials = (
        pattern_count
        * len(BLUR_SIGMAS)
        * len(NOISE_STANDARD_DEVIATIONS)
        * NOISE_TRIALS
        * len(PIPELINES)
        * len(METRICS)
    )
    if len(trial_rows) != expected_trials:
        raise RuntimeError("Unexpected number of trial rows.")
    if len(response_rows) != (
        len(PIPELINES)
        * len(NOISE_STANDARD_DEVIATIONS)
        * len(BLUR_SIGMAS)
        * len(METRICS)
    ):
        raise RuntimeError("Unexpected number of response rows.")
    if len(anchor_rows) != pattern_count * len(METRICS):
        raise RuntimeError("Unexpected number of calibration anchors.")
    if len(calibration_rows) != (
        len(PIPELINES) * len(NOISE_STANDARD_DEVIATIONS) * len(METRICS)
    ):
        raise RuntimeError("Unexpected number of calibration rows.")

    identity_ratios = [
        float(row["ratio_to_identity_same_input"])
        for row in trial_rows
        if row["pipeline"] == "identity"
    ]
    if not np.allclose(identity_ratios, 1.0):
        raise RuntimeError("Identity ratios must equal one.")
    if not all(
        float(row["sharp_score"]) > float(row["blurred_score"])
        for row in anchor_rows
    ):
        raise RuntimeError("Clean sharp anchors must exceed blurred anchors.")

    for metric in METRICS:
        identity = _find_calibration(calibration_rows, "identity", 0, metric)
        if not np.isclose(float(identity["balanced_accuracy"]), 1.0):
            raise RuntimeError("Identity anchors must classify their source data.")
        if int(identity["adjacent_order_violation_count"]) != 0:
            raise RuntimeError("Clean identity blur scores must remain ordered.")
        photometric_accuracy = [
            float(
                _find_calibration(
                    calibration_rows, pipeline, 0, metric
                )["balanced_accuracy"]
            )
            for pipeline in (
                "brightness_minus_30",
                "brightness_plus_30",
                "contrast_0_5",
                "contrast_1_25",
                "gamma_0_7",
                "gamma_1_4",
                "minmax_normalize",
            )
        ]
        if all(np.isclose(value, 1.0) for value in photometric_accuracy):
            raise RuntimeError("A photometric control must expose calibration drift.")

        one_round = float(
            _find_response(
                response_rows, "gray_jpeg_q75_r1", 0, 0, metric
            )["same_input_ratio_mean"]
        )
        if np.isclose(one_round, 1.0, rtol=0.0, atol=1e-6):
            raise RuntimeError("The first JPEG round must change the bounded mean.")

        grayscale_first = float(
            _find_response(
                response_rows, "gray_jpeg_q75_r2", 0, 0, metric
            )["same_input_ratio_mean"]
        )
        color_first = float(
            _find_response(
                response_rows,
                "color_jpeg_q75_r2_then_gray",
                0,
                0,
                metric,
            )["same_input_ratio_mean"]
        )
        if np.isclose(
            grayscale_first, color_first, rtol=0.0, atol=1e-6
        ):
            raise RuntimeError("Color-conversion order must change the bounded mean.")


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
    """Visualize representative synthetic pipeline outputs."""
    pipelines = (
        "source_color",
        "identity",
        "gamma_0_7",
        "minmax_normalize",
        "gray_jpeg_q75_r5",
        "color_jpeg_q75_r5_then_gray",
        "gamma_0_7_then_gray_jpeg_q75_r2",
        "gray_jpeg_q75_r2_then_gamma_0_7",
    )
    titles = (
        "source BGR",
        "grayscale",
        "gamma 0.7",
        "min-max",
        "gray JPEG x5",
        "color JPEG x5 -> gray",
        "gamma -> JPEG x2",
        "JPEG x2 -> gamma",
    )
    image = make_patterns()["colored_targets"]
    noisy_blurred = add_channel_noise(
        apply_gaussian_blur(image, 2),
        standard_deviation=15,
        seed=trial_seed(2, 2, 2, 0),
    )
    sources = (("sharp, noise 0", image), ("sigma 2, noise 15", noisy_blurred))

    figure, axes = plt.subplots(2, len(pipelines), figsize=(15, 4.5))
    for row_index, (row_label, source) in enumerate(sources):
        for column_index, (pipeline, title) in enumerate(zip(pipelines, titles)):
            axis = axes[row_index, column_index]
            if pipeline == "source_color":
                axis.imshow(cv2.cvtColor(source, cv2.COLOR_BGR2RGB))
            else:
                axis.imshow(
                    apply_pipeline(source, pipeline),
                    cmap="gray",
                    vmin=0,
                    vmax=255,
                )
            if row_index == 0:
                axis.set_title(title, fontsize=8)
            if column_index == 0:
                axis.set_ylabel(row_label, fontsize=9)
            axis.set_xticks([])
            axis.set_yticks([])
    figure.suptitle("Synthetic photometric and recompression controls")
    figure.tight_layout()
    figure.savefig(
        output_path,
        dpi=150,
        metadata={"Software": "research-notes v0.7.0"},
    )
    plt.close(figure)


def write_drift_figure(
    response_rows: Sequence[dict[str, str]],
    calibration_rows: Sequence[dict[str, str]],
    output_path: Path,
) -> None:
    """Plot photometric response, recompression, and calibration transfer."""
    metric_layout = (
        ("laplacian_variance", "Laplacian variance"),
        ("tenengrad_energy", "Tenengrad energy"),
    )
    photometric = (
        "identity",
        "contrast_0_5",
        "contrast_1_25",
        "gamma_0_7",
        "gamma_1_4",
        "minmax_normalize",
    )
    labels = {
        "identity": "identity",
        "contrast_0_5": "contrast 0.50",
        "contrast_1_25": "contrast 1.25",
        "gamma_0_7": "gamma 0.7",
        "gamma_1_4": "gamma 1.4",
        "minmax_normalize": "min-max",
        "gray_jpeg_q75_r5": "gray JPEG x5",
        "color_jpeg_q75_r5_then_gray": "color JPEG x5 -> gray",
        "gamma_0_7_then_gray_jpeg_q75_r2": "gamma -> JPEG x2",
        "gray_jpeg_q75_r2_then_gamma_0_7": "JPEG x2 -> gamma",
    }
    colors = ("#111827", "#2563eb", "#dc2626", "#059669", "#d97706", "#7c3aed")
    figure, axes = plt.subplots(3, 2, figsize=(11, 11), constrained_layout=True)

    for column, (metric, metric_label) in enumerate(metric_layout):
        for pipeline, color in zip(photometric, colors):
            values = [
                float(
                    _find_response(
                        response_rows, pipeline, 0, blur_sigma, metric
                    )["same_input_ratio_mean"]
                )
                for blur_sigma in BLUR_SIGMAS
            ]
            axes[0, column].plot(
                BLUR_SIGMAS,
                values,
                marker="o",
                linewidth=2,
                color=color,
                label=labels[pipeline],
            )

        for color_mode, line_style in (("gray", "-"), ("color", "--")):
            for blur_sigma, color in ((0, "#2563eb"), (3, "#dc2626")):
                values = [1.0]
                for rounds in JPEG_ROUNDS:
                    pipeline = (
                        f"gray_jpeg_q75_r{rounds}"
                        if color_mode == "gray"
                        else f"color_jpeg_q75_r{rounds}_then_gray"
                    )
                    values.append(
                        float(
                            _find_response(
                                response_rows,
                                pipeline,
                                0,
                                blur_sigma,
                                metric,
                            )["same_input_ratio_mean"]
                        )
                    )
                axes[1, column].plot(
                    (0, *JPEG_ROUNDS),
                    values,
                    marker="o",
                    linewidth=2,
                    linestyle=line_style,
                    color=color,
                    label=f"{color_mode}, sigma {blur_sigma}",
                )

        calibration_pipelines = (
            "identity",
            "minmax_normalize",
            "gray_jpeg_q75_r5",
            "color_jpeg_q75_r5_then_gray",
            "gamma_0_7_then_gray_jpeg_q75_r2",
            "gray_jpeg_q75_r2_then_gamma_0_7",
        )
        for pipeline, color in zip(calibration_pipelines, colors):
            values = [
                float(
                    _find_calibration(
                        calibration_rows, pipeline, noise_std, metric
                    )["balanced_accuracy"]
                )
                for noise_std in NOISE_STANDARD_DEVIATIONS
            ]
            axes[2, column].plot(
                NOISE_STANDARD_DEVIATIONS,
                values,
                marker="o",
                linewidth=2,
                color=color,
                label=labels[pipeline],
            )

        axes[0, column].set(
            title=f"{metric_label}: photometric response",
            xlabel="Gaussian blur sigma",
            ylabel="Mean ratio to same-input identity",
            xticks=BLUR_SIGMAS,
        )
        axes[1, column].set(
            title=f"{metric_label}: JPEG round-trip drift",
            xlabel="JPEG round trips at quality 75",
            ylabel="Mean ratio to uncompressed input",
            xticks=(0, *JPEG_ROUNDS),
        )
        axes[2, column].set(
            title=f"{metric_label}: fixed calibration transfer",
            xlabel="Channel-noise standard deviation",
            ylabel="Balanced accuracy",
            xticks=NOISE_STANDARD_DEVIATIONS,
            ylim=(0.45, 1.02),
        )
        for row_index in range(3):
            axes[row_index, column].grid(axis="y", alpha=0.25)
            axes[row_index, column].legend(frameon=False, fontsize=7)

    figure.suptitle("Photometric normalization and recompression drift")
    figure.savefig(
        output_path,
        dpi=150,
        metadata={"Software": "research-notes v0.7.0"},
    )
    plt.close(figure)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results"),
        help="Directory for generated CSV and PNG files (default: results)",
    )
    return parser.parse_args()


def main() -> int:
    """Generate all v0.7.0 reference artifacts."""
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    anchor_rows, thresholds, sharp_scores = build_calibration_anchors()
    trial_rows = run_trials(thresholds, sharp_scores)
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
    write_drift_figure(
        response_rows,
        calibration_rows,
        args.output_dir / DRIFT_FIGURE_NAME,
    )

    print("Validated the expected photometric and recompression relationships.")
    print(f"Generated {len(trial_rows)} metric observations.")
    print(f"Generated {len(response_rows)} response summaries.")
    print(f"Generated {len(calibration_rows)} calibration summaries.")
    print("Wrote four CSV files and two PNG figures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
