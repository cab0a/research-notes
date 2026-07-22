"""Evaluate window geometry and robustness for localized blur measures."""

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
from matplotlib.patches import Rectangle  # noqa: E402

from research_notes import (
    laplacian_variance,
    sliding_metric_map,
    tenengrad_energy,
)


IMAGE_SIZE = 256
REGION_SIZE = 64
BLUR_SIGMAS = (1, 2, 3)
PLACEMENTS = {
    "aligned": (64, 64),
    "offset_16": (80, 80),
    "offset_32": (96, 96),
}
WINDOW_CONFIGURATIONS = (
    ("nonoverlap_64", 64, 64),
    ("overlap_64", 64, 32),
    ("fine_32", 32, 16),
    ("coarse_128", 128, 64),
)
NOISE_CONFIGURATIONS = (
    ("overlap_64", 64, 32),
    ("fine_32", 32, 16),
)
NOISE_STANDARD_DEVIATIONS = (0, 5, 15)
NOISE_TRIALS = 10
BASE_SEED = 20260922
POSITIVE_COVERAGE = 0.5
METRICS = {
    "laplacian_variance": laplacian_variance,
    "tenengrad_energy": tenengrad_energy,
}

WINDOWS_CSV_NAME = "window_geometry_windows.csv"
SUMMARY_CSV_NAME = "window_geometry_summary.csv"
NOISE_TRIALS_CSV_NAME = "window_noise_trials.csv"
NOISE_SUMMARY_CSV_NAME = "window_noise_summary.csv"
LOW_TEXTURE_CSV_NAME = "low_texture_confounds.csv"
EXAMPLE_FIGURE_NAME = "window_geometry_example.png"
ROBUSTNESS_FIGURE_NAME = "window_geometry_robustness.png"


def make_patterns() -> dict[str, NDArray[np.uint8]]:
    """Create deterministic textured patterns matched to the v0.3.0 study."""
    rows, columns = np.indices((IMAGE_SIZE, IMAGE_SIZE))
    checkerboard = (((rows // 8 + columns // 8) % 2) * 255).astype(np.uint8)

    bar_row = (((np.arange(IMAGE_SIZE) // 8) % 2) * 255).astype(np.uint8)
    vertical_bars = np.repeat(bar_row[np.newaxis, :], IMAGE_SIZE, axis=0)

    tile_rows, tile_columns = np.indices((REGION_SIZE, REGION_SIZE))
    radius = np.sqrt(
        (tile_rows - (REGION_SIZE - 1) / 2) ** 2
        + (tile_columns - (REGION_SIZE - 1) / 2) ** 2
    )
    ring_tile = np.where((radius.astype(np.int32) // 5) % 2 == 0, 224, 24)
    concentric_tiles = np.tile(ring_tile.astype(np.uint8), (4, 4))

    return {
        "checkerboard": checkerboard,
        "vertical_bars": vertical_bars,
        "concentric_tiles": concentric_tiles,
    }


def apply_rectangular_blur(
    image: NDArray[np.uint8],
    sigma: int,
    region_top: int,
    region_left: int,
    region_size: int = REGION_SIZE,
) -> NDArray[np.uint8]:
    """Copy a rectangular region from a fully Gaussian-blurred image."""
    if sigma <= 0:
        raise ValueError("sigma must be positive")
    if region_size <= 0:
        raise ValueError("region_size must be positive")
    if (
        region_top < 0
        or region_left < 0
        or region_top + region_size > image.shape[0]
        or region_left + region_size > image.shape[1]
    ):
        raise ValueError("blur region must lie within the image")

    fully_blurred = cv2.GaussianBlur(
        image,
        (0, 0),
        sigmaX=float(sigma),
        sigmaY=float(sigma),
        borderType=cv2.BORDER_REFLECT_101,
    )
    observed = image.copy()
    observed[
        region_top : region_top + region_size,
        region_left : region_left + region_size,
    ] = fully_blurred[
        region_top : region_top + region_size,
        region_left : region_left + region_size,
    ]
    return observed


def add_gaussian_noise(
    image: NDArray[np.uint8], standard_deviation: int, seed: int
) -> NDArray[np.uint8]:
    """Add deterministic zero-mean Gaussian noise and clip to 8-bit range."""
    if standard_deviation < 0:
        raise ValueError("standard_deviation must not be negative")
    if standard_deviation == 0:
        return image.copy()
    generator = np.random.default_rng(seed)
    noise = generator.normal(0.0, standard_deviation, image.shape)
    return np.clip(image.astype(np.float64) + noise, 0, 255).astype(np.uint8)


def window_coverage(
    row_start: int,
    column_start: int,
    window_size: int,
    region_top: int,
    region_left: int,
    region_size: int = REGION_SIZE,
) -> float:
    """Return the fraction of a window covered by the known blur region."""
    row_overlap = max(
        0,
        min(row_start + window_size, region_top + region_size)
        - max(row_start, region_top),
    )
    column_overlap = max(
        0,
        min(column_start + window_size, region_left + region_size)
        - max(column_start, region_left),
    )
    return row_overlap * column_overlap / (window_size * window_size)


def average_precision(
    labels: NDArray[np.bool_], scores: NDArray[np.float64]
) -> float | None:
    """Return ranking average precision, or None when there are no positives."""
    if labels.shape != scores.shape:
        raise ValueError("labels and scores must have the same shape")
    positive_count = int(np.count_nonzero(labels))
    if positive_count == 0:
        return None
    order = np.argsort(-scores, kind="stable")
    ranked_labels = labels[order].astype(np.int64)
    cumulative_positives = np.cumsum(ranked_labels)
    ranks = np.arange(1, ranked_labels.size + 1)
    precision = cumulative_positives / ranks
    return float(np.sum(precision * ranked_labels) / positive_count)


def _format_optional(value: float | None) -> str:
    """Format an optional numeric CSV field."""
    return "" if value is None else f"{value:.6f}"


def evaluate_windows(
    pattern: str,
    placement: str,
    reference: NDArray[np.uint8],
    observed: NDArray[np.uint8],
    blur_sigma: int,
    region_top: int,
    region_left: int,
    configuration: str,
    window_size: int,
    stride: int,
) -> list[dict[str, str]]:
    """Evaluate both metrics and ground-truth coverage on one window grid."""
    metric_maps: dict[str, tuple[NDArray[np.float64], NDArray[np.float64]]] = {}
    for metric_name, metric in METRICS.items():
        reference_map = sliding_metric_map(reference, metric, window_size, stride)
        if np.any(reference_map <= 0.0):
            raise RuntimeError(f"Non-positive reference window for {pattern}.")
        observed_map = sliding_metric_map(observed, metric, window_size, stride)
        metric_maps[metric_name] = (reference_map, observed_map)

    grid_shape = next(iter(metric_maps.values()))[0].shape
    rows: list[dict[str, str]] = []
    for window_row in range(grid_shape[0]):
        row_start = window_row * stride
        for window_column in range(grid_shape[1]):
            column_start = window_column * stride
            coverage = window_coverage(
                row_start,
                column_start,
                window_size,
                region_top,
                region_left,
            )
            row = {
                "pattern": pattern,
                "placement": placement,
                "region_top": str(region_top),
                "region_left": str(region_left),
                "region_size": str(REGION_SIZE),
                "blur_sigma": str(blur_sigma),
                "configuration": configuration,
                "window_size": str(window_size),
                "stride": str(stride),
                "window_row": str(window_row),
                "window_column": str(window_column),
                "row_start": str(row_start),
                "column_start": str(column_start),
                "coverage_fraction": f"{coverage:.6f}",
                "is_positive": str(int(coverage >= POSITIVE_COVERAGE)),
            }
            for metric_name, (reference_map, observed_map) in metric_maps.items():
                reference_score = reference_map[window_row, window_column]
                observed_score = observed_map[window_row, window_column]
                row.update(
                    {
                        f"{metric_name}_reference": f"{reference_score:.6f}",
                        f"{metric_name}_observed": f"{observed_score:.6f}",
                        f"{metric_name}_ratio": (
                            f"{observed_score / reference_score:.6f}"
                        ),
                    }
                )
            rows.append(row)
    return rows


def summarize_window_condition(
    rows: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Summarize window coverage and metric ranking for one condition."""
    if not rows:
        raise ValueError("rows must not be empty")
    coverages = np.array(
        [float(row["coverage_fraction"]) for row in rows], dtype=np.float64
    )
    labels = coverages >= POSITIVE_COVERAGE
    max_coverage = float(np.max(coverages))
    summary_rows: list[dict[str, str]] = []
    for metric_name in METRICS:
        ratios = np.array(
            [float(row[f"{metric_name}_ratio"]) for row in rows],
            dtype=np.float64,
        )
        minimum_index = int(np.argmin(ratios))
        best_coverage_ratios = ratios[np.isclose(coverages, max_coverage)]
        ap = average_precision(labels, 1.0 - ratios)
        first = rows[0]
        summary_rows.append(
            {
                "pattern": first["pattern"],
                "placement": first["placement"],
                "blur_sigma": first["blur_sigma"],
                "configuration": first["configuration"],
                "window_size": first["window_size"],
                "stride": first["stride"],
                "metric": metric_name,
                "window_count": str(len(rows)),
                "positive_window_count": str(int(np.count_nonzero(labels))),
                "max_window_coverage": f"{max_coverage:.6f}",
                "minimum_ratio": f"{ratios[minimum_index]:.6f}",
                "minimum_ratio_window_coverage": (
                    f"{coverages[minimum_index]:.6f}"
                ),
                "best_coverage_ratio": f"{np.mean(best_coverage_ratios):.6f}",
                "average_precision": _format_optional(ap),
            }
        )
    return summary_rows


def run_geometry_experiment(
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Run aligned and off-grid blur through four window geometries."""
    window_rows: list[dict[str, str]] = []
    summary_rows: list[dict[str, str]] = []
    for pattern, image in make_patterns().items():
        for placement, (region_top, region_left) in PLACEMENTS.items():
            for blur_sigma in BLUR_SIGMAS:
                observed = apply_rectangular_blur(
                    image, blur_sigma, region_top, region_left
                )
                for configuration, window_size, stride in WINDOW_CONFIGURATIONS:
                    condition_rows = evaluate_windows(
                        pattern,
                        placement,
                        image,
                        observed,
                        blur_sigma,
                        region_top,
                        region_left,
                        configuration,
                        window_size,
                        stride,
                    )
                    window_rows.extend(condition_rows)
                    summary_rows.extend(summarize_window_condition(condition_rows))
    return window_rows, summary_rows


def run_noise_trials() -> list[dict[str, str]]:
    """Evaluate ranking stability with repeated additive Gaussian noise."""
    rows: list[dict[str, str]] = []
    region_top, region_left = PLACEMENTS["offset_32"]
    for pattern_index, (pattern, image) in enumerate(make_patterns().items()):
        locally_blurred = apply_rectangular_blur(image, 3, region_top, region_left)
        for noise_index, noise_std in enumerate(NOISE_STANDARD_DEVIATIONS):
            for trial in range(NOISE_TRIALS):
                seed = BASE_SEED + pattern_index * 10_000 + noise_index * 1_000 + trial
                observed = add_gaussian_noise(locally_blurred, noise_std, seed)
                for configuration, window_size, stride in NOISE_CONFIGURATIONS:
                    condition_rows = evaluate_windows(
                        pattern,
                        "offset_32",
                        image,
                        observed,
                        3,
                        region_top,
                        region_left,
                        configuration,
                        window_size,
                        stride,
                    )
                    for summary in summarize_window_condition(condition_rows):
                        rows.append(
                            {
                                "pattern": pattern,
                                "noise_std": str(noise_std),
                                "trial": str(trial),
                                "seed": str(seed),
                                "configuration": configuration,
                                "window_size": str(window_size),
                                "stride": str(stride),
                                "metric": summary["metric"],
                                "positive_window_count": summary[
                                    "positive_window_count"
                                ],
                                "minimum_ratio": summary["minimum_ratio"],
                                "minimum_ratio_window_coverage": summary[
                                    "minimum_ratio_window_coverage"
                                ],
                                "average_precision": summary["average_precision"],
                            }
                        )
    return rows


def summarize_noise_trials(
    rows: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Aggregate repeated noise trials across patterns and seeds."""
    summary_rows: list[dict[str, str]] = []
    for configuration, window_size, stride in NOISE_CONFIGURATIONS:
        for noise_std in NOISE_STANDARD_DEVIATIONS:
            for metric in METRICS:
                group = [
                    row
                    for row in rows
                    if row["configuration"] == configuration
                    and int(row["noise_std"]) == noise_std
                    and row["metric"] == metric
                ]
                ap_values = np.array(
                    [float(row["average_precision"]) for row in group],
                    dtype=np.float64,
                )
                minimum_ratios = np.array(
                    [float(row["minimum_ratio"]) for row in group],
                    dtype=np.float64,
                )
                coverage_values = np.array(
                    [
                        float(row["minimum_ratio_window_coverage"])
                        for row in group
                    ],
                    dtype=np.float64,
                )
                summary_rows.append(
                    {
                        "configuration": configuration,
                        "window_size": str(window_size),
                        "stride": str(stride),
                        "noise_std": str(noise_std),
                        "metric": metric,
                        "observations": str(len(group)),
                        "average_precision_mean": f"{np.mean(ap_values):.6f}",
                        "average_precision_sample_std": (
                            f"{np.std(ap_values, ddof=1):.6f}"
                        ),
                        "average_precision_p10": (
                            f"{np.quantile(ap_values, 0.1):.6f}"
                        ),
                        "average_precision_p90": (
                            f"{np.quantile(ap_values, 0.9):.6f}"
                        ),
                        "minimum_ratio_mean": f"{np.mean(minimum_ratios):.6f}",
                        "minimum_ratio_sample_std": (
                            f"{np.std(minimum_ratios, ddof=1):.6f}"
                        ),
                        "minimum_window_coverage_mean": (
                            f"{np.mean(coverage_values):.6f}"
                        ),
                    }
                )
    return summary_rows


def run_low_texture_control() -> list[dict[str, str]]:
    """Compare a sharp flat patch with sharp and blurred textured patches."""
    image = make_patterns()["checkerboard"]
    observed = image.copy()
    observed[0:REGION_SIZE, 0:REGION_SIZE] = 127
    fully_blurred = cv2.GaussianBlur(
        image,
        (0, 0),
        sigmaX=3.0,
        sigmaY=3.0,
        borderType=cv2.BORDER_REFLECT_101,
    )
    observed[128:192, 128:192] = fully_blurred[128:192, 128:192]
    regions = (
        ("sharp_low_texture", "sharp", 0, 0),
        ("sharp_textured", "sharp", 0, 128),
        ("blurred_textured", "blurred", 128, 128),
    )

    rows: list[dict[str, str]] = []
    for metric_name, metric in METRICS.items():
        sharp_textured = observed[0:REGION_SIZE, 128:192]
        reference_score = metric(sharp_textured)
        metric_rows: list[dict[str, str]] = []
        for region, ground_truth, row_start, column_start in regions:
            patch = observed[
                row_start : row_start + REGION_SIZE,
                column_start : column_start + REGION_SIZE,
            ]
            score = metric(patch)
            metric_rows.append(
                {
                    "region": region,
                    "ground_truth": ground_truth,
                    "row_start": str(row_start),
                    "column_start": str(column_start),
                    "window_size": str(REGION_SIZE),
                    "metric": metric_name,
                    "score": f"{score:.6f}",
                    "ratio_to_sharp_textured": f"{score / reference_score:.6f}",
                    "ascending_score_rank": "",
                }
            )
        ordered = sorted(metric_rows, key=lambda row: float(row["score"]))
        for rank, row in enumerate(ordered, start=1):
            row["ascending_score_rank"] = str(rank)
        rows.extend(metric_rows)
    return rows


def validate_expected_relationships(
    window_rows: Sequence[dict[str, str]],
    geometry_rows: Sequence[dict[str, str]],
    noise_rows: Sequence[dict[str, str]],
    noise_summary_rows: Sequence[dict[str, str]],
    low_texture_rows: Sequence[dict[str, str]],
) -> None:
    """Validate the controlled relationships claimed by the experiment."""
    expected_windows = (
        len(make_patterns())
        * len(PLACEMENTS)
        * len(BLUR_SIGMAS)
        * sum(
            ((IMAGE_SIZE - window_size) // stride + 1) ** 2
            for _, window_size, stride in WINDOW_CONFIGURATIONS
        )
    )
    if len(window_rows) != expected_windows:
        raise RuntimeError("Unexpected number of window observations.")
    if len(geometry_rows) != (
        len(make_patterns())
        * len(PLACEMENTS)
        * len(BLUR_SIGMAS)
        * len(WINDOW_CONFIGURATIONS)
        * len(METRICS)
    ):
        raise RuntimeError("Unexpected number of geometry summaries.")
    if len(noise_rows) != (
        len(make_patterns())
        * len(NOISE_STANDARD_DEVIATIONS)
        * NOISE_TRIALS
        * len(NOISE_CONFIGURATIONS)
        * len(METRICS)
    ):
        raise RuntimeError("Unexpected number of noise trials.")
    if len(noise_summary_rows) != (
        len(NOISE_STANDARD_DEVIATIONS)
        * len(NOISE_CONFIGURATIONS)
        * len(METRICS)
    ):
        raise RuntimeError("Unexpected number of noise summaries.")
    if len(low_texture_rows) != len(METRICS) * 3:
        raise RuntimeError("Unexpected number of low-texture controls.")

    defined_geometry_ap = [
        float(row["average_precision"])
        for row in geometry_rows
        if row["average_precision"]
    ]
    if not defined_geometry_ap or not np.allclose(defined_geometry_ap, 1.0):
        raise RuntimeError("Expected perfect ranking in clean defined conditions.")
    if not all(
        np.isclose(float(row["average_precision"]), 1.0) for row in noise_rows
    ):
        raise RuntimeError("Expected localization ranking to survive bounded noise.")

    for configuration, _, _ in NOISE_CONFIGURATIONS:
        for metric in METRICS:
            clean = next(
                row
                for row in noise_summary_rows
                if row["configuration"] == configuration
                and int(row["noise_std"]) == 0
                and row["metric"] == metric
            )
            noisy = next(
                row
                for row in noise_summary_rows
                if row["configuration"] == configuration
                and int(row["noise_std"]) == 15
                and row["metric"] == metric
            )
            if float(noisy["minimum_ratio_mean"]) <= float(
                clean["minimum_ratio_mean"]
            ):
                raise RuntimeError("Expected bounded noise to inflate score ratios.")

    for metric in METRICS:
        split_rows = [
            row
            for row in geometry_rows
            if row["pattern"] == "checkerboard"
            and row["placement"] == "offset_32"
            and int(row["blur_sigma"]) == 3
            and row["configuration"] == "nonoverlap_64"
            and row["metric"] == metric
        ]
        overlap_rows = [
            row
            for row in geometry_rows
            if row["pattern"] == "checkerboard"
            and row["placement"] == "offset_32"
            and int(row["blur_sigma"]) == 3
            and row["configuration"] == "overlap_64"
            and row["metric"] == metric
        ]
        if len(split_rows) != 1 or len(overlap_rows) != 1:
            raise RuntimeError("Missing alignment control rows.")
        if not np.isclose(float(split_rows[0]["max_window_coverage"]), 0.25):
            raise RuntimeError("The split non-overlapping window must cover 25%.")
        if split_rows[0]["average_precision"]:
            raise RuntimeError("The split grid must have no 50%-coverage positive.")
        if not np.isclose(float(overlap_rows[0]["max_window_coverage"]), 1.0):
            raise RuntimeError("The overlapping grid must contain the full region.")
        if float(overlap_rows[0]["best_coverage_ratio"]) >= 1.0:
            raise RuntimeError("The full-coverage window must respond to blur.")

        metric_controls = [
            row for row in low_texture_rows if row["metric"] == metric
        ]
        flat = next(
            row for row in metric_controls if row["region"] == "sharp_low_texture"
        )
        blurred = next(
            row for row in metric_controls if row["region"] == "blurred_textured"
        )
        if float(flat["score"]) >= float(blurred["score"]):
            raise RuntimeError("The sharp flat patch must score below blurred texture.")
        if flat["ascending_score_rank"] != "1":
            raise RuntimeError("The sharp flat patch must rank as the lowest score.")


def write_csv(rows: Sequence[dict[str, str]], output_path: Path) -> None:
    """Write a deterministic CSV table with platform-independent newlines."""
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


def _rows_for_condition(
    rows: Sequence[dict[str, str]],
    pattern: str,
    placement: str,
    sigma: int,
    configuration: str,
) -> list[dict[str, str]]:
    """Select one geometry condition from the window-level table."""
    return [
        row
        for row in rows
        if row["pattern"] == pattern
        and row["placement"] == placement
        and int(row["blur_sigma"]) == sigma
        and row["configuration"] == configuration
    ]


def _reshape_field(
    rows: Sequence[dict[str, str]], field: str
) -> NDArray[np.float64]:
    """Reshape one ordered numeric window field into its grid."""
    row_count = max(int(row["window_row"]) for row in rows) + 1
    column_count = max(int(row["window_column"]) for row in rows) + 1
    return np.array([float(row[field]) for row in rows], dtype=np.float64).reshape(
        row_count, column_count
    )


def write_example_figure(
    window_rows: Sequence[dict[str, str]], output_path: Path
) -> None:
    """Visualize an off-grid region and the effect of overlapping windows."""
    image = make_patterns()["checkerboard"]
    region_top, region_left = PLACEMENTS["offset_32"]
    observed = apply_rectangular_blur(image, 3, region_top, region_left)
    nonoverlap = _rows_for_condition(
        window_rows, "checkerboard", "offset_32", 3, "nonoverlap_64"
    )
    overlap = _rows_for_condition(
        window_rows, "checkerboard", "offset_32", 3, "overlap_64"
    )

    figure, axes = plt.subplots(1, 4, figsize=(12, 3.2), constrained_layout=True)
    axes[0].imshow(observed, cmap="gray", vmin=0, vmax=255)
    axes[0].add_patch(
        Rectangle(
            (region_left, region_top),
            REGION_SIZE,
            REGION_SIZE,
            fill=False,
            edgecolor="#f59e0b",
            linewidth=2,
        )
    )
    axes[0].set_title("32-pixel off-grid blur")
    axes[0].set_axis_off()

    heatmaps = (
        (
            _reshape_field(nonoverlap, "coverage_fraction"),
            "64/64 coverage",
            "magma",
        ),
        (
            _reshape_field(nonoverlap, "laplacian_variance_ratio"),
            "64/64 Laplacian ratio",
            "viridis",
        ),
        (
            _reshape_field(overlap, "laplacian_variance_ratio"),
            "64/32 Laplacian ratio",
            "viridis",
        ),
    )
    for axis, (values, title, color_map) in zip(axes[1:], heatmaps):
        artist = axis.imshow(values, cmap=color_map, vmin=0, vmax=1)
        axis.set_title(title)
        axis.set_xticks(range(values.shape[1]))
        axis.set_yticks(range(values.shape[0]))
        figure.colorbar(artist, ax=axis, fraction=0.046, pad=0.04)
    figure.suptitle("Window stride changes capture of an off-grid blur region")
    figure.savefig(
        output_path,
        dpi=150,
        metadata={"Software": "research-notes v0.4.0"},
    )
    plt.close(figure)


def _geometry_mean(
    rows: Sequence[dict[str, str]],
    placement: str,
    configuration: str,
    field: str,
    sigma: int = 3,
) -> float:
    """Average one geometry summary field across patterns and metrics."""
    values = [
        float(row[field])
        for row in rows
        if row["placement"] == placement
        and row["configuration"] == configuration
        and int(row["blur_sigma"]) == sigma
        and row[field]
    ]
    return float(np.mean(values)) if values else float("nan")


def write_robustness_figure(
    geometry_rows: Sequence[dict[str, str]],
    noise_summary_rows: Sequence[dict[str, str]],
    low_texture_rows: Sequence[dict[str, str]],
    output_path: Path,
) -> None:
    """Visualize geometry capture, ranking, noise, and texture ambiguity."""
    figure, axes = plt.subplots(2, 2, figsize=(10, 7), constrained_layout=True)
    configurations = [configuration for configuration, _, _ in WINDOW_CONFIGURATIONS]
    short_labels = ["64/64", "64/32", "32/16", "128/64"]
    colors = {"aligned": "#2563eb", "offset_16": "#0f766e", "offset_32": "#b91c1c"}

    for placement in PLACEMENTS:
        coverage_values = [
            _geometry_mean(
                geometry_rows,
                placement,
                configuration,
                "max_window_coverage",
            )
            for configuration in configurations
        ]
        axes[0, 0].plot(
            short_labels,
            coverage_values,
            marker="o",
            linewidth=2,
            color=colors[placement],
            label=placement,
        )
    axes[0, 0].set(
        title="Maximum window coverage of the blur region",
        xlabel="Window size / stride",
        ylabel="Coverage fraction",
        ylim=(-0.02, 1.05),
    )

    for placement in PLACEMENTS:
        ap_values = [
            _geometry_mean(
                geometry_rows,
                placement,
                configuration,
                "average_precision",
            )
            for configuration in configurations
        ]
        axes[0, 1].plot(
            short_labels,
            ap_values,
            marker="o",
            linewidth=2,
            color=colors[placement],
            label=placement,
        )
    axes[0, 1].set(
        title="Ranking AP where 50%-coverage positives exist",
        xlabel="Window size / stride",
        ylabel="Average precision",
        ylim=(-0.02, 1.05),
    )

    noise_colors = {
        ("overlap_64", "laplacian_variance"): "#2563eb",
        ("overlap_64", "tenengrad_energy"): "#b91c1c",
        ("fine_32", "laplacian_variance"): "#60a5fa",
        ("fine_32", "tenengrad_energy"): "#f87171",
    }
    for configuration, _, _ in NOISE_CONFIGURATIONS:
        for metric in METRICS:
            values = [
                float(row["minimum_ratio_mean"])
                for noise_std in NOISE_STANDARD_DEVIATIONS
                for row in noise_summary_rows
                if row["configuration"] == configuration
                and int(row["noise_std"]) == noise_std
                and row["metric"] == metric
            ]
            metric_label = (
                "Laplacian" if metric == "laplacian_variance" else "Tenengrad"
            )
            axes[1, 0].plot(
                NOISE_STANDARD_DEVIATIONS,
                values,
                marker="o",
                linewidth=2,
                color=noise_colors[(configuration, metric)],
                label=f"{configuration}: {metric_label}",
            )
    axes[1, 0].set(
        title="Repeated-noise response magnitude",
        xlabel="Gaussian noise standard deviation",
        ylabel="Mean minimum score ratio",
        xticks=NOISE_STANDARD_DEVIATIONS,
        ylim=(0.0, 0.23),
    )

    regions = ("sharp_low_texture", "blurred_textured", "sharp_textured")
    x_positions = np.arange(len(regions))
    bar_width = 0.36
    for offset, metric, color, label in (
        (-bar_width / 2, "laplacian_variance", "#2563eb", "Laplacian"),
        (bar_width / 2, "tenengrad_energy", "#b91c1c", "Tenengrad"),
    ):
        values = [
            float(row["ratio_to_sharp_textured"])
            for region in regions
            for row in low_texture_rows
            if row["region"] == region and row["metric"] == metric
        ]
        axes[1, 1].bar(
            x_positions + offset,
            values,
            width=bar_width,
            color=color,
            label=label,
        )
    axes[1, 1].set(
        title="A sharp flat patch has the lowest raw score",
        ylabel="Ratio to sharp textured patch",
        xticks=x_positions,
        xticklabels=("sharp flat", "blurred texture", "sharp texture"),
        ylim=(0.0, 1.05),
    )

    for axis in axes.ravel():
        axis.grid(axis="y", alpha=0.25)
        axis.legend(frameon=False, fontsize=8)
    figure.suptitle("Window geometry improves alignment but does not remove confounds")
    figure.savefig(
        output_path,
        dpi=150,
        metadata={"Software": "research-notes v0.4.0"},
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
    """Generate all v0.4.0 reference artifacts."""
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    window_rows, geometry_rows = run_geometry_experiment()
    noise_rows = run_noise_trials()
    noise_summary_rows = summarize_noise_trials(noise_rows)
    low_texture_rows = run_low_texture_control()
    validate_expected_relationships(
        window_rows,
        geometry_rows,
        noise_rows,
        noise_summary_rows,
        low_texture_rows,
    )

    write_csv(window_rows, args.output_dir / WINDOWS_CSV_NAME)
    write_csv(geometry_rows, args.output_dir / SUMMARY_CSV_NAME)
    write_csv(noise_rows, args.output_dir / NOISE_TRIALS_CSV_NAME)
    write_csv(noise_summary_rows, args.output_dir / NOISE_SUMMARY_CSV_NAME)
    write_csv(low_texture_rows, args.output_dir / LOW_TEXTURE_CSV_NAME)
    write_example_figure(window_rows, args.output_dir / EXAMPLE_FIGURE_NAME)
    write_robustness_figure(
        geometry_rows,
        noise_summary_rows,
        low_texture_rows,
        args.output_dir / ROBUSTNESS_FIGURE_NAME,
    )

    print("Validated the expected window-geometry relationships.")
    print(f"Generated {len(window_rows)} window observations.")
    print(f"Generated {len(geometry_rows)} geometry summaries.")
    print(f"Generated {len(noise_rows)} repeated noise observations.")
    print("Wrote five CSV files and two PNG figures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
