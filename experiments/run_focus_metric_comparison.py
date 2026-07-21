"""Compare Laplacian variance and Tenengrad under controlled degradations."""

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

from research_notes import laplacian_variance, tenengrad_energy


IMAGE_SIZE = 256
BLUR_SIGMAS = (0, 1, 2, 3)
NOISE_STANDARD_DEVIATIONS = (0, 5, 15)
TRIALS = 20
BASE_SEED = 20260820
MOTION_LENGTHS = (1, 5, 9, 15)
RESIZE_SCALES = (1.0, 0.75, 0.5, 0.25)
METRICS = ("laplacian_variance", "tenengrad_energy")

TRIALS_CSV_NAME = "focus_metric_trials.csv"
SUMMARY_CSV_NAME = "focus_metric_summary.csv"
MOTION_CSV_NAME = "motion_blur_summary.csv"
RESIZE_CSV_NAME = "resize_sensitivity_summary.csv"
FIGURE_NAME = "focus_metric_comparison.png"


def make_patterns() -> dict[str, NDArray[np.uint8]]:
    """Create the same deterministic patterns used by the v0.1.0 study."""
    rows, columns = np.indices((IMAGE_SIZE, IMAGE_SIZE))
    checkerboard = (((rows // 16 + columns // 16) % 2) * 255).astype(np.uint8)

    bar_columns = np.arange(IMAGE_SIZE)
    bar_row = (((bar_columns // 8) % 2) * 255).astype(np.uint8)
    vertical_bars = np.repeat(bar_row[np.newaxis, :], IMAGE_SIZE, axis=0)

    geometric_shapes = np.full((IMAGE_SIZE, IMAGE_SIZE), 32, dtype=np.uint8)
    cv2.rectangle(geometric_shapes, (24, 24), (112, 104), 220, thickness=-1)
    cv2.rectangle(geometric_shapes, (42, 42), (94, 86), 70, thickness=-1)
    cv2.circle(geometric_shapes, (180, 70), 42, 245, thickness=-1)
    cv2.circle(geometric_shapes, (180, 70), 18, 80, thickness=-1)
    cv2.line(geometric_shapes, (18, 222), (230, 126), 200, thickness=5)
    cv2.line(geometric_shapes, (24, 132), (224, 232), 120, thickness=3)

    return {
        "checkerboard": checkerboard,
        "vertical_bars": vertical_bars,
        "geometric_shapes": geometric_shapes,
    }


def apply_gaussian_blur(
    image: NDArray[np.uint8], sigma: int
) -> NDArray[np.uint8]:
    """Apply Gaussian blur, using sigma zero as the unchanged control."""
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
    if standard_deviation == 0:
        return image.copy()
    generator = np.random.default_rng(seed)
    noise = generator.normal(0.0, standard_deviation, image.shape)
    return np.clip(image.astype(np.float64) + noise, 0, 255).astype(np.uint8)


def apply_horizontal_motion_blur(
    image: NDArray[np.uint8], length: int
) -> NDArray[np.uint8]:
    """Apply an odd-length normalized horizontal motion kernel."""
    if length < 1 or length % 2 == 0:
        raise ValueError("motion length must be a positive odd integer")
    if length == 1:
        return image.copy()
    kernel = np.zeros((length, length), dtype=np.float64)
    kernel[length // 2, :] = 1.0 / length
    return cv2.filter2D(
        image,
        ddepth=-1,
        kernel=kernel,
        borderType=cv2.BORDER_REFLECT_101,
    )


def resize_round_trip(
    image: NDArray[np.uint8], scale: float
) -> NDArray[np.uint8]:
    """Shrink with area interpolation, then restore size with linear interpolation."""
    if not 0.0 < scale <= 1.0:
        raise ValueError("resize scale must be in the interval (0, 1]")
    if scale == 1.0:
        return image.copy()
    height, width = image.shape
    reduced_size = (round(width * scale), round(height * scale))
    reduced = cv2.resize(image, reduced_size, interpolation=cv2.INTER_AREA)
    return cv2.resize(reduced, (width, height), interpolation=cv2.INTER_LINEAR)


def calculate_metrics(image: NDArray[np.uint8]) -> dict[str, float]:
    """Calculate both focus measures for one controlled observation."""
    return {
        "laplacian_variance": laplacian_variance(image),
        "tenengrad_energy": tenengrad_energy(image),
    }


def run_repeated_trials() -> list[dict[str, str]]:
    """Run the Gaussian blur and repeated Gaussian-noise factorial experiment."""
    rows: list[dict[str, str]] = []
    for pattern_index, (pattern_name, image) in enumerate(make_patterns().items()):
        for blur_index, blur_sigma in enumerate(BLUR_SIGMAS):
            blurred = apply_gaussian_blur(image, blur_sigma)
            for noise_index, noise_std in enumerate(NOISE_STANDARD_DEVIATIONS):
                for trial in range(TRIALS):
                    seed = (
                        BASE_SEED
                        + pattern_index * 100_000
                        + blur_index * 10_000
                        + noise_index * 1_000
                        + trial
                    )
                    observed = add_gaussian_noise(blurred, noise_std, seed)
                    metrics = calculate_metrics(observed)
                    rows.append(
                        {
                            "pattern": pattern_name,
                            "blur_sigma": str(blur_sigma),
                            "noise_std": str(noise_std),
                            "trial": str(trial),
                            "seed": str(seed),
                            "laplacian_variance": (
                                f"{metrics['laplacian_variance']:.6f}"
                            ),
                            "tenengrad_energy": f"{metrics['tenengrad_energy']:.6f}",
                        }
                    )
    return rows


def summarize_trials(rows: Sequence[dict[str, str]]) -> list[dict[str, str]]:
    """Summarize repeated observations with spread and quantile statistics."""
    summary_rows: list[dict[str, str]] = []
    patterns = tuple(make_patterns())
    for pattern in patterns:
        for blur_sigma in BLUR_SIGMAS:
            for noise_std in NOISE_STANDARD_DEVIATIONS:
                condition = [
                    row
                    for row in rows
                    if row["pattern"] == pattern
                    and int(row["blur_sigma"]) == blur_sigma
                    and int(row["noise_std"]) == noise_std
                ]
                summary: dict[str, str] = {
                    "pattern": pattern,
                    "blur_sigma": str(blur_sigma),
                    "noise_std": str(noise_std),
                    "trials": str(len(condition)),
                }
                for metric in METRICS:
                    values = np.array(
                        [float(row[metric]) for row in condition], dtype=np.float64
                    )
                    summary.update(
                        {
                            f"{metric}_mean": f"{np.mean(values):.6f}",
                            f"{metric}_sample_std": f"{np.std(values, ddof=1):.6f}",
                            f"{metric}_p10": f"{np.quantile(values, 0.1):.6f}",
                            f"{metric}_median": f"{np.median(values):.6f}",
                            f"{metric}_p90": f"{np.quantile(values, 0.9):.6f}",
                        }
                    )
                summary_rows.append(summary)
    return summary_rows


def run_motion_sensitivity() -> list[dict[str, str]]:
    """Evaluate both metrics under horizontal linear motion blur."""
    rows: list[dict[str, str]] = []
    for pattern, image in make_patterns().items():
        for length in MOTION_LENGTHS:
            metrics = calculate_metrics(apply_horizontal_motion_blur(image, length))
            rows.append(
                {
                    "pattern": pattern,
                    "motion_length": str(length),
                    "angle_degrees": "0",
                    "laplacian_variance": f"{metrics['laplacian_variance']:.6f}",
                    "tenengrad_energy": f"{metrics['tenengrad_energy']:.6f}",
                }
            )
    return rows


def run_resize_sensitivity() -> list[dict[str, str]]:
    """Evaluate both metrics after controlled downscale-upscale round trips."""
    rows: list[dict[str, str]] = []
    for pattern, image in make_patterns().items():
        for scale in RESIZE_SCALES:
            metrics = calculate_metrics(resize_round_trip(image, scale))
            rows.append(
                {
                    "pattern": pattern,
                    "scale": f"{scale:.2f}",
                    "down_interpolation": "INTER_AREA",
                    "up_interpolation": "INTER_LINEAR",
                    "laplacian_variance": f"{metrics['laplacian_variance']:.6f}",
                    "tenengrad_energy": f"{metrics['tenengrad_energy']:.6f}",
                }
            )
    return rows


def validate_expected_relationships(
    summary_rows: Sequence[dict[str, str]],
) -> None:
    """Check only the relative relationships claimed by the main experiment."""
    for pattern in make_patterns():
        for metric in METRICS:
            noiseless_means = [
                float(row[f"{metric}_mean"])
                for blur_sigma in BLUR_SIGMAS
                for row in summary_rows
                if row["pattern"] == pattern
                and int(row["blur_sigma"]) == blur_sigma
                and int(row["noise_std"]) == 0
            ]
            if not all(
                left > right
                for left, right in zip(noiseless_means, noiseless_means[1:])
            ):
                raise RuntimeError(
                    f"Noiseless {metric} means are not decreasing for {pattern}."
                )

            sigma_three_means = [
                float(row[f"{metric}_mean"])
                for noise_std in NOISE_STANDARD_DEVIATIONS
                for row in summary_rows
                if row["pattern"] == pattern
                and int(row["blur_sigma"]) == 3
                and int(row["noise_std"]) == noise_std
            ]
            if not all(
                left < right
                for left, right in zip(
                    sigma_three_means, sigma_three_means[1:]
                )
            ):
                raise RuntimeError(
                    f"Noise does not raise sigma-3 {metric} means for {pattern}."
                )


def write_csv(rows: Sequence[dict[str, str]], output_path: Path) -> None:
    """Write rows with field order taken from the stable first-row schema."""
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


def _summary_mean(
    rows: Sequence[dict[str, str]],
    pattern: str,
    blur_sigma: int,
    noise_std: int,
    metric: str,
) -> float:
    matches = [
        float(row[f"{metric}_mean"])
        for row in rows
        if row["pattern"] == pattern
        and int(row["blur_sigma"]) == blur_sigma
        and int(row["noise_std"]) == noise_std
    ]
    if len(matches) != 1:
        raise RuntimeError("summary condition is not unique")
    return matches[0]


def _sensitivity_score(
    rows: Sequence[dict[str, str]], pattern: str, key: str, value: float, metric: str
) -> float:
    matches = [
        float(row[metric])
        for row in rows
        if row["pattern"] == pattern and float(row[key]) == value
    ]
    if len(matches) != 1:
        raise RuntimeError("sensitivity condition is not unique")
    return matches[0]


def write_figure(
    trial_rows: Sequence[dict[str, str]],
    summary_rows: Sequence[dict[str, str]],
    motion_rows: Sequence[dict[str, str]],
    resize_rows: Sequence[dict[str, str]],
    output_path: Path,
) -> None:
    """Plot relative responses so the two differently scaled metrics can be compared."""
    labels = {
        "laplacian_variance": "Laplacian variance",
        "tenengrad_energy": "Tenengrad energy",
    }
    colors = {
        "laplacian_variance": "#1f77b4",
        "tenengrad_energy": "#d95f02",
    }
    patterns = tuple(make_patterns())
    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.titleweight": "bold",
            "axes.grid": True,
            "grid.alpha": 0.25,
            "figure.facecolor": "white",
        }
    )
    figure, axes = plt.subplots(2, 2, figsize=(10, 7.5), constrained_layout=True)

    for metric in METRICS:
        blur_response = []
        for blur_sigma in BLUR_SIGMAS:
            ratios = [
                _summary_mean(summary_rows, pattern, blur_sigma, 0, metric)
                / _summary_mean(summary_rows, pattern, 0, 0, metric)
                for pattern in patterns
            ]
            blur_response.append(float(np.mean(ratios)))
        axes[0, 0].plot(
            BLUR_SIGMAS,
            blur_response,
            marker="o",
            linewidth=2,
            color=colors[metric],
            label=labels[metric],
        )
    axes[0, 0].set(
        title="Noiseless Gaussian blur response",
        xlabel="Gaussian blur sigma (pixels)",
        ylabel="Mean ratio to sigma 0",
        xticks=BLUR_SIGMAS,
    )
    axes[0, 0].legend(frameon=False)

    for metric in METRICS:
        medians = []
        lower = []
        upper = []
        for noise_std in NOISE_STANDARD_DEVIATIONS:
            ratios = []
            for row in trial_rows:
                if int(row["blur_sigma"]) != 3 or int(row["noise_std"]) != noise_std:
                    continue
                baseline = _summary_mean(
                    summary_rows, row["pattern"], 3, 0, metric
                )
                ratios.append(float(row[metric]) / baseline)
            medians.append(float(np.median(ratios)))
            lower.append(float(np.quantile(ratios, 0.1)))
            upper.append(float(np.quantile(ratios, 0.9)))
        axes[0, 1].plot(
            NOISE_STANDARD_DEVIATIONS,
            medians,
            marker="o",
            linewidth=2,
            color=colors[metric],
            label=labels[metric],
        )
        axes[0, 1].fill_between(
            NOISE_STANDARD_DEVIATIONS,
            lower,
            upper,
            color=colors[metric],
            alpha=0.15,
        )
    axes[0, 1].set(
        title="Noise inflation at Gaussian sigma 3",
        xlabel="Gaussian noise standard deviation",
        ylabel="Median ratio to noise SD 0 (log scale)",
        xticks=NOISE_STANDARD_DEVIATIONS,
        yscale="log",
    )
    axes[0, 1].legend(frameon=False)

    for metric in METRICS:
        motion_response = []
        for length in MOTION_LENGTHS:
            ratios = [
                _sensitivity_score(motion_rows, pattern, "motion_length", length, metric)
                / _sensitivity_score(motion_rows, pattern, "motion_length", 1, metric)
                for pattern in patterns
            ]
            motion_response.append(float(np.mean(ratios)))
        axes[1, 0].plot(
            MOTION_LENGTHS,
            motion_response,
            marker="o",
            linewidth=2,
            color=colors[metric],
            label=labels[metric],
        )
    axes[1, 0].set(
        title="Horizontal motion blur sensitivity",
        xlabel="Motion kernel length (pixels)",
        ylabel="Mean ratio to length 1",
        xticks=MOTION_LENGTHS,
    )

    for metric in METRICS:
        resize_response = []
        for scale in RESIZE_SCALES:
            ratios = [
                _sensitivity_score(resize_rows, pattern, "scale", scale, metric)
                / _sensitivity_score(resize_rows, pattern, "scale", 1.0, metric)
                for pattern in patterns
            ]
            resize_response.append(float(np.mean(ratios)))
        axes[1, 1].plot(
            RESIZE_SCALES,
            resize_response,
            marker="o",
            linewidth=2,
            color=colors[metric],
            label=labels[metric],
        )
    axes[1, 1].set(
        title="Downscale-upscale sensitivity",
        xlabel="Intermediate scale",
        ylabel="Mean ratio to scale 1",
        xticks=RESIZE_SCALES,
    )
    axes[1, 1].invert_xaxis()

    figure.suptitle(
        "Laplacian variance and Tenengrad respond differently to degradation",
        fontsize=12,
    )
    figure.savefig(
        output_path,
        dpi=150,
        metadata={"Software": "research-notes v0.2.0"},
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
    """Generate all v0.2.0 reference artifacts."""
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    trial_rows = run_repeated_trials()
    summary_rows = summarize_trials(trial_rows)
    motion_rows = run_motion_sensitivity()
    resize_rows = run_resize_sensitivity()
    validate_expected_relationships(summary_rows)

    write_csv(trial_rows, args.output_dir / TRIALS_CSV_NAME)
    write_csv(summary_rows, args.output_dir / SUMMARY_CSV_NAME)
    write_csv(motion_rows, args.output_dir / MOTION_CSV_NAME)
    write_csv(resize_rows, args.output_dir / RESIZE_CSV_NAME)
    write_figure(
        trial_rows,
        summary_rows,
        motion_rows,
        resize_rows,
        args.output_dir / FIGURE_NAME,
    )

    print("Validated the expected within-experiment relationships.")
    print(f"Generated {len(trial_rows)} repeated trial observations.")
    print("Wrote four CSV files and focus_metric_comparison.png.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
