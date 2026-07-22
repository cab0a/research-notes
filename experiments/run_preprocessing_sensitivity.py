"""Evaluate preprocessing sensitivity and synthetic calibration transfer."""

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
    gaussian_denoise,
    jpeg_round_trip,
    laplacian_variance,
    resize_round_trip,
    tenengrad_energy,
    unsharp_mask,
)


IMAGE_SIZE = 256
TILE_SIZE = 64
BLUR_SIGMAS = (0, 1, 2, 3)
NOISE_STANDARD_DEVIATIONS = (0, 5, 15)
NOISE_TRIALS = 10
BASE_SEED = 20261001
PIPELINES = (
    "identity",
    "jpeg_q95",
    "jpeg_q75",
    "jpeg_q50",
    "resize_area_linear",
    "resize_linear_linear",
    "gaussian_denoise",
    "unsharp_0_5",
    "unsharp_1_0",
    "denoise_then_unsharp",
    "unsharp_then_denoise",
    "jpeg_then_resize",
    "resize_then_jpeg",
)
PIPELINE_DESCRIPTIONS = {
    "identity": "No preprocessing",
    "jpeg_q95": "JPEG quality 95 round trip",
    "jpeg_q75": "JPEG quality 75 round trip",
    "jpeg_q50": "JPEG quality 50 round trip",
    "resize_area_linear": "0.5x INTER_AREA down, INTER_LINEAR up",
    "resize_linear_linear": "0.5x INTER_LINEAR down and up",
    "gaussian_denoise": "Gaussian low-pass sigma 1",
    "unsharp_0_5": "Unsharp amount 0.5, sigma 1",
    "unsharp_1_0": "Unsharp amount 1.0, sigma 1",
    "denoise_then_unsharp": "Gaussian denoise then unsharp amount 1.0",
    "unsharp_then_denoise": "Unsharp amount 1.0 then Gaussian denoise",
    "jpeg_then_resize": "JPEG quality 75 then area-linear resize",
    "resize_then_jpeg": "Area-linear resize then JPEG quality 75",
}
METRICS = {
    "laplacian_variance": laplacian_variance,
    "tenengrad_energy": tenengrad_energy,
}

TRIALS_CSV_NAME = "preprocessing_trials.csv"
RESPONSE_CSV_NAME = "preprocessing_response_summary.csv"
ANCHORS_CSV_NAME = "preprocessing_calibration_anchors.csv"
CALIBRATION_CSV_NAME = "preprocessing_calibration_summary.csv"
EXAMPLES_FIGURE_NAME = "preprocessing_examples.png"
CALIBRATION_FIGURE_NAME = "preprocessing_calibration_drift.png"


def make_patterns() -> dict[str, NDArray[np.uint8]]:
    """Create the deterministic patterns shared by the earlier studies."""
    rows, columns = np.indices((IMAGE_SIZE, IMAGE_SIZE))
    checkerboard = (((rows // 8 + columns // 8) % 2) * 255).astype(np.uint8)

    bar_row = (((np.arange(IMAGE_SIZE) // 8) % 2) * 255).astype(np.uint8)
    vertical_bars = np.repeat(bar_row[np.newaxis, :], IMAGE_SIZE, axis=0)

    tile_rows, tile_columns = np.indices((TILE_SIZE, TILE_SIZE))
    radius = np.sqrt(
        (tile_rows - (TILE_SIZE - 1) / 2) ** 2
        + (tile_columns - (TILE_SIZE - 1) / 2) ** 2
    )
    ring_tile = np.where((radius.astype(np.int32) // 5) % 2 == 0, 224, 24)
    concentric_tiles = np.tile(ring_tile.astype(np.uint8), (4, 4))

    return {
        "checkerboard": checkerboard,
        "vertical_bars": vertical_bars,
        "concentric_tiles": concentric_tiles,
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


def add_gaussian_noise(
    image: NDArray[np.uint8], standard_deviation: int, seed: int
) -> NDArray[np.uint8]:
    """Add seeded zero-mean Gaussian noise and clip to the 8-bit range."""
    if standard_deviation < 0:
        raise ValueError("standard_deviation must not be negative")
    if standard_deviation == 0:
        return image.copy()
    generator = np.random.default_rng(seed)
    noise = generator.normal(0.0, standard_deviation, image.shape)
    return np.clip(image.astype(np.float64) + noise, 0, 255).astype(np.uint8)


def trial_seed(
    pattern_index: int, blur_index: int, noise_index: int, trial: int
) -> int:
    """Return a unique deterministic seed for one raw image condition."""
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
    """Apply one declared preprocessing pipeline."""
    if pipeline == "identity":
        return image.copy()
    if pipeline == "jpeg_q95":
        return jpeg_round_trip(image, quality=95)
    if pipeline == "jpeg_q75":
        return jpeg_round_trip(image, quality=75)
    if pipeline == "jpeg_q50":
        return jpeg_round_trip(image, quality=50)
    if pipeline == "resize_area_linear":
        return resize_round_trip(image, scale=0.5)
    if pipeline == "resize_linear_linear":
        return resize_round_trip(
            image,
            scale=0.5,
            down_interpolation=cv2.INTER_LINEAR,
            up_interpolation=cv2.INTER_LINEAR,
        )
    if pipeline == "gaussian_denoise":
        return gaussian_denoise(image, sigma=1.0)
    if pipeline == "unsharp_0_5":
        return unsharp_mask(image, amount=0.5, sigma=1.0)
    if pipeline == "unsharp_1_0":
        return unsharp_mask(image, amount=1.0, sigma=1.0)
    if pipeline == "denoise_then_unsharp":
        return unsharp_mask(
            gaussian_denoise(image, sigma=1.0),
            amount=1.0,
            sigma=1.0,
        )
    if pipeline == "unsharp_then_denoise":
        return gaussian_denoise(
            unsharp_mask(image, amount=1.0, sigma=1.0),
            sigma=1.0,
        )
    if pipeline == "jpeg_then_resize":
        return resize_round_trip(
            jpeg_round_trip(image, quality=75),
            scale=0.5,
        )
    if pipeline == "resize_then_jpeg":
        return jpeg_round_trip(
            resize_round_trip(image, scale=0.5),
            quality=75,
        )
    raise ValueError(f"unknown pipeline: {pipeline}")


def build_calibration_anchors(
) -> tuple[
    list[dict[str, str]],
    dict[tuple[str, str], float],
    dict[tuple[str, str], float],
]:
    """Create per-pattern midpoint thresholds from clean identity anchors."""
    rows: list[dict[str, str]] = []
    thresholds: dict[tuple[str, str], float] = {}
    sharp_scores: dict[tuple[str, str], float] = {}
    for pattern, image in make_patterns().items():
        blurred = apply_gaussian_blur(image, sigma=3)
        for metric_name, metric in METRICS.items():
            sharp_score = metric(image)
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
    """Run all blur, noise, and preprocessing conditions."""
    rows: list[dict[str, str]] = []
    for pattern_index, (pattern, image) in enumerate(make_patterns().items()):
        for blur_index, blur_sigma in enumerate(BLUR_SIGMAS):
            blurred = apply_gaussian_blur(image, blur_sigma)
            for noise_index, noise_std in enumerate(NOISE_STANDARD_DEVIATIONS):
                for trial in range(NOISE_TRIALS):
                    seed = trial_seed(
                        pattern_index,
                        blur_index,
                        noise_index,
                        trial,
                    )
                    raw = add_gaussian_noise(blurred, noise_std, seed)
                    identity_scores = {
                        metric_name: metric(raw)
                        for metric_name, metric in METRICS.items()
                    }
                    for pipeline in PIPELINES:
                        processed = apply_pipeline(raw, pipeline)
                        for metric_name, metric in METRICS.items():
                            score = metric(processed)
                            identity_score = identity_scores[metric_name]
                            key = (pattern, metric_name)
                            threshold = thresholds[key]
                            if blur_sigma == 0:
                                expected_class = "sharp"
                            elif blur_sigma == 3:
                                expected_class = "blurred"
                            else:
                                expected_class = "intermediate"
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
                                    "calibration_threshold": f"{threshold:.6f}",
                                    "expected_class": expected_class,
                                    "predicted_blurred": str(int(score < threshold)),
                                }
                            )
    return rows


def summarize_responses(
    rows: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Summarize score drift for every preprocessing condition."""
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
                    same_input_ratios = np.array(
                        [
                            float(row["ratio_to_identity_same_input"])
                            for row in group
                        ],
                        dtype=np.float64,
                    )
                    sharp_anchor_ratios = np.array(
                        [
                            float(row["ratio_to_identity_sharp_anchor"])
                            for row in group
                        ],
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
                                f"{np.mean(same_input_ratios):.6f}"
                            ),
                            "same_input_ratio_sample_std": (
                                f"{np.std(same_input_ratios, ddof=1):.6f}"
                            ),
                            "same_input_ratio_p10": (
                                f"{np.quantile(same_input_ratios, 0.1):.6f}"
                            ),
                            "same_input_ratio_median": (
                                f"{np.median(same_input_ratios):.6f}"
                            ),
                            "same_input_ratio_p90": (
                                f"{np.quantile(same_input_ratios, 0.9):.6f}"
                            ),
                            "sharp_anchor_ratio_mean": (
                                f"{np.mean(sharp_anchor_ratios):.6f}"
                            ),
                            "sharp_anchor_ratio_sample_std": (
                                f"{np.std(sharp_anchor_ratios, ddof=1):.6f}"
                            ),
                        }
                    )
    return summary_rows


def summarize_calibration_transfer(
    rows: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Evaluate fixed identity-anchor thresholds and blur-order preservation."""
    summary_rows: list[dict[str, str]] = []
    patterns = tuple(make_patterns())
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
                for pattern in patterns:
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
                        violation_count += pair_violations
                        adjacent_pair_count += len(scores) - 1
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


def _find_summary(
    rows: Sequence[dict[str, str]],
    pipeline: str,
    noise_std: int,
    metric: str,
) -> dict[str, str]:
    """Find one calibration summary row."""
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
    """Validate row counts and the controlled relationships in the note."""
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
        raise RuntimeError("Unexpected number of preprocessing trial rows.")
    if len(response_rows) != (
        len(PIPELINES)
        * len(NOISE_STANDARD_DEVIATIONS)
        * len(BLUR_SIGMAS)
        * len(METRICS)
    ):
        raise RuntimeError("Unexpected number of response summaries.")
    if len(anchor_rows) != pattern_count * len(METRICS):
        raise RuntimeError("Unexpected number of calibration anchors.")
    if len(calibration_rows) != (
        len(PIPELINES) * len(NOISE_STANDARD_DEVIATIONS) * len(METRICS)
    ):
        raise RuntimeError("Unexpected number of calibration summaries.")

    identity_ratios = [
        float(row["ratio_to_identity_same_input"])
        for row in trial_rows
        if row["pipeline"] == "identity"
    ]
    if not np.allclose(identity_ratios, 1.0):
        raise RuntimeError("Identity preprocessing must retain a ratio of one.")
    if not all(
        float(row["sharp_score"]) > float(row["blurred_score"])
        for row in anchor_rows
    ):
        raise RuntimeError("Clean sharp anchors must exceed blurred anchors.")

    for metric in METRICS:
        identity = _find_summary(
            calibration_rows, "identity", 0, metric
        )
        denoised = _find_summary(
            calibration_rows, "gaussian_denoise", 0, metric
        )
        if not np.isclose(float(identity["balanced_accuracy"]), 1.0):
            raise RuntimeError("Identity anchors must classify their source data.")
        if int(identity["adjacent_order_violation_count"]) != 0:
            raise RuntimeError("Clean identity blur scores must remain ordered.")
        if float(denoised["balanced_accuracy"]) >= 1.0:
            raise RuntimeError("Denoising must expose fixed-calibration drift.")

    noisy_identity = _find_summary(
        calibration_rows, "identity", 15, "laplacian_variance"
    )
    noisy_sharpened = _find_summary(
        calibration_rows, "unsharp_1_0", 15, "laplacian_variance"
    )
    if float(noisy_sharpened["blurred_miss_rate"]) <= float(
        noisy_identity["blurred_miss_rate"]
    ):
        raise RuntimeError("Sharpening must increase the bounded blur-miss rate.")

    jpeg_response = [
        row
        for row in response_rows
        if row["pipeline"] == "jpeg_q50"
        and int(row["noise_std"]) == 0
        and int(row["blur_sigma"]) == 3
        and row["metric"] == "laplacian_variance"
    ]
    if len(jpeg_response) != 1 or float(
        jpeg_response[0]["same_input_ratio_mean"]
    ) <= 1.0:
        raise RuntimeError("JPEG must inflate the bounded blurred Laplacian mean.")

    forward = _find_summary(
        calibration_rows, "denoise_then_unsharp", 0, "tenengrad_energy"
    )
    reverse = _find_summary(
        calibration_rows, "unsharp_then_denoise", 0, "tenengrad_energy"
    )
    if np.isclose(
        float(forward["balanced_accuracy"]),
        float(reverse["balanced_accuracy"]),
    ):
        raise RuntimeError("The bounded operation-order control must differ.")


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
    """Show visual examples of the declared preprocessing controls."""
    pipelines = (
        "identity",
        "jpeg_q50",
        "resize_area_linear",
        "gaussian_denoise",
        "unsharp_1_0",
        "denoise_then_unsharp",
    )
    titles = (
        "identity",
        "JPEG q50",
        "resize 0.5x",
        "Gaussian denoise",
        "unsharp 1.0",
        "denoise -> unsharp",
    )
    image = make_patterns()["concentric_tiles"]
    sharp = image.copy()
    blurred = apply_gaussian_blur(image, sigma=2)
    noisy = add_gaussian_noise(
        blurred,
        standard_deviation=15,
        seed=trial_seed(2, 2, 2, 0),
    )
    row_inputs = (("sharp, noise 0", sharp), ("sigma 2, noise 15", noisy))

    figure, axes = plt.subplots(2, len(pipelines), figsize=(12, 4.5))
    for row_index, (row_label, source) in enumerate(row_inputs):
        for column_index, (pipeline, title) in enumerate(zip(pipelines, titles)):
            axis = axes[row_index, column_index]
            axis.imshow(
                apply_pipeline(source, pipeline),
                cmap="gray",
                vmin=0,
                vmax=255,
            )
            if row_index == 0:
                axis.set_title(title, fontsize=9)
            if column_index == 0:
                axis.set_ylabel(row_label, fontsize=9)
            axis.set_xticks([])
            axis.set_yticks([])
    figure.suptitle("Synthetic preprocessing controls")
    figure.tight_layout()
    figure.savefig(
        output_path,
        dpi=150,
        metadata={"Software": "research-notes v0.5.0"},
    )
    plt.close(figure)


def _response_value(
    rows: Sequence[dict[str, str]],
    pipeline: str,
    noise_std: int,
    blur_sigma: int,
    metric: str,
) -> float:
    """Return one mean sharp-anchor response."""
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
    return float(matches[0]["sharp_anchor_ratio_mean"])


def write_calibration_figure(
    response_rows: Sequence[dict[str, str]],
    calibration_rows: Sequence[dict[str, str]],
    output_path: Path,
) -> None:
    """Plot response scale and fixed-calibration transfer by metric."""
    selected = (
        "identity",
        "jpeg_q50",
        "resize_area_linear",
        "gaussian_denoise",
        "unsharp_1_0",
    )
    labels = {
        "identity": "identity",
        "jpeg_q50": "JPEG q50",
        "resize_area_linear": "resize 0.5x",
        "gaussian_denoise": "Gaussian denoise",
        "unsharp_1_0": "unsharp 1.0",
    }
    colors = {
        "identity": "#111827",
        "jpeg_q50": "#d97706",
        "resize_area_linear": "#2563eb",
        "gaussian_denoise": "#059669",
        "unsharp_1_0": "#dc2626",
    }
    figure, axes = plt.subplots(2, 2, figsize=(10, 7), constrained_layout=True)
    metric_layout = (
        ("laplacian_variance", "Laplacian variance"),
        ("tenengrad_energy", "Tenengrad energy"),
    )
    for column, (metric, metric_label) in enumerate(metric_layout):
        for pipeline in selected:
            response = [
                _response_value(
                    response_rows,
                    pipeline,
                    noise_std=0,
                    blur_sigma=blur_sigma,
                    metric=metric,
                )
                for blur_sigma in BLUR_SIGMAS
            ]
            axes[0, column].plot(
                BLUR_SIGMAS,
                response,
                marker="o",
                linewidth=2,
                color=colors[pipeline],
                label=labels[pipeline],
            )
            calibration = [
                float(
                    _find_summary(
                        calibration_rows,
                        pipeline,
                        noise_std,
                        metric,
                    )["balanced_accuracy"]
                )
                for noise_std in NOISE_STANDARD_DEVIATIONS
            ]
            axes[1, column].plot(
                NOISE_STANDARD_DEVIATIONS,
                calibration,
                marker="o",
                linewidth=2,
                color=colors[pipeline],
                label=labels[pipeline],
            )

        axes[0, column].set(
            title=f"{metric_label}: noise-free response",
            xlabel="Gaussian blur sigma",
            ylabel="Mean ratio to identity sharp anchor",
            xticks=BLUR_SIGMAS,
        )
        axes[1, column].set(
            title=f"{metric_label}: fixed calibration transfer",
            xlabel="Gaussian noise standard deviation",
            ylabel="Balanced accuracy",
            xticks=NOISE_STANDARD_DEVIATIONS,
            ylim=(0.45, 1.02),
        )
        for row in range(2):
            axes[row, column].grid(axis="y", alpha=0.25)
            axes[row, column].legend(frameon=False, fontsize=8)
    figure.suptitle("Preprocessing changes response scale and calibration transfer")
    figure.savefig(
        output_path,
        dpi=150,
        metadata={"Software": "research-notes v0.5.0"},
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
    """Generate all v0.5.0 reference artifacts."""
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
    write_calibration_figure(
        response_rows,
        calibration_rows,
        args.output_dir / CALIBRATION_FIGURE_NAME,
    )

    print("Validated the expected preprocessing relationships.")
    print(f"Generated {len(trial_rows)} preprocessing observations.")
    print(f"Generated {len(response_rows)} response summaries.")
    print(f"Generated {len(calibration_rows)} calibration summaries.")
    print("Wrote four CSV files and two PNG figures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
