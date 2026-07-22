"""Evaluate local blur and spatial aggregation under controlled conditions."""

from __future__ import annotations

import argparse
import csv
from collections.abc import Sequence
from pathlib import Path

import cv2
import matplotlib
import numpy as np
from matplotlib.patches import Rectangle
from numpy.typing import NDArray

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

from research_notes import (
    laplacian_variance,
    tenengrad_energy,
    tiled_metric_map,
)


IMAGE_SIZE = 256
TILE_SIZE = 64
GRID_SIZE = IMAGE_SIZE // TILE_SIZE
BLUR_SIGMAS = (1, 2, 3)
LOCAL_CONDITIONS = (
    (1, "edge"),
    (1, "center"),
    (4, "edge"),
    (4, "center"),
    (8, "edge"),
    (8, "center"),
    (16, "full"),
)
METRICS = {
    "laplacian_variance": laplacian_variance,
    "tenengrad_energy": tenengrad_energy,
}

OBSERVATIONS_CSV_NAME = "local_blur_observations.csv"
TILES_CSV_NAME = "local_blur_tiles.csv"
AGGREGATE_CSV_NAME = "local_blur_aggregate.csv"
EXAMPLE_FIGURE_NAME = "local_blur_example.png"
EVALUATION_FIGURE_NAME = "local_blur_spatial_aggregation.png"


def make_patterns() -> dict[str, NDArray[np.uint8]]:
    """Create deterministic patterns with texture in every evaluation tile."""
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
    concentric_tiles = np.tile(ring_tile.astype(np.uint8), (GRID_SIZE, GRID_SIZE))

    return {
        "checkerboard": checkerboard,
        "vertical_bars": vertical_bars,
        "concentric_tiles": concentric_tiles,
    }


def select_blurred_tiles(tile_count: int, placement: str) -> set[tuple[int, int]]:
    """Return an aligned rectangular set of tiles for one local-blur condition."""
    if tile_count == 1 and placement == "edge":
        return {(0, 0)}
    if tile_count == 1 and placement == "center":
        return {(1, 1)}
    if tile_count == 4 and placement == "edge":
        return {(row, column) for row in range(2) for column in range(2)}
    if tile_count == 4 and placement == "center":
        return {(row, column) for row in range(1, 3) for column in range(1, 3)}
    if tile_count == 8 and placement == "edge":
        return {(row, column) for row in range(2) for column in range(GRID_SIZE)}
    if tile_count == 8 and placement == "center":
        return {(row, column) for row in range(1, 3) for column in range(GRID_SIZE)}
    if tile_count == 16 and placement == "full":
        return {
            (row, column)
            for row in range(GRID_SIZE)
            for column in range(GRID_SIZE)
        }
    raise ValueError("unsupported tile count and placement combination")


def apply_local_gaussian_blur(
    image: NDArray[np.uint8],
    sigma: int,
    blurred_tiles: set[tuple[int, int]],
) -> NDArray[np.uint8]:
    """Replace selected tile regions with pixels from a fully blurred image."""
    if sigma <= 0:
        raise ValueError("sigma must be positive")
    fully_blurred = cv2.GaussianBlur(
        image,
        (0, 0),
        sigmaX=float(sigma),
        sigmaY=float(sigma),
        borderType=cv2.BORDER_REFLECT_101,
    )
    observed = image.copy()
    for tile_row, tile_column in blurred_tiles:
        row_start = tile_row * TILE_SIZE
        column_start = tile_column * TILE_SIZE
        observed[
            row_start : row_start + TILE_SIZE,
            column_start : column_start + TILE_SIZE,
        ] = fully_blurred[
            row_start : row_start + TILE_SIZE,
            column_start : column_start + TILE_SIZE,
        ]
    return observed


def lowest_quartile_mean(values: NDArray[np.float64]) -> float:
    """Return the mean of the lowest quarter of a non-empty score array."""
    flat_values = np.sort(np.asarray(values, dtype=np.float64).ravel())
    if flat_values.size == 0:
        raise ValueError("values must not be empty")
    count = max(1, flat_values.size // 4)
    return float(np.mean(flat_values[:count]))


def top_k_localization_recall(
    tile_ratios: NDArray[np.float64],
    blurred_tiles: set[tuple[int, int]],
) -> float:
    """Measure how many known blurred tiles occur among the k lowest ratios."""
    if not blurred_tiles:
        raise ValueError("blurred_tiles must not be empty")
    flat_order = np.argsort(tile_ratios.ravel(), kind="stable")
    predicted = {
        (int(index) // tile_ratios.shape[1], int(index) % tile_ratios.shape[1])
        for index in flat_order[: len(blurred_tiles)]
    }
    return len(predicted & blurred_tiles) / len(blurred_tiles)


def _format_optional(value: float | None) -> str:
    """Format a numeric CSV value or return an empty field."""
    return "" if value is None else f"{value:.6f}"


def _record_condition(
    pattern: str,
    image: NDArray[np.uint8],
    observed: NDArray[np.uint8],
    blur_sigma: int,
    placement: str,
    blurred_tiles: set[tuple[int, int]],
    observation_rows: list[dict[str, str]],
    tile_rows: list[dict[str, str]],
) -> None:
    """Calculate full-image, tile-level, and spatial aggregation results."""
    area_fraction = len(blurred_tiles) / (GRID_SIZE * GRID_SIZE)
    for metric_name, metric in METRICS.items():
        reference_global = metric(image)
        observed_global = metric(observed)
        reference_map = tiled_metric_map(image, metric, TILE_SIZE)
        observed_map = tiled_metric_map(observed, metric, TILE_SIZE)
        if np.any(reference_map <= 0.0) or reference_global <= 0.0:
            raise RuntimeError(f"Non-positive reference score for {pattern}.")
        ratios = observed_map / reference_map

        blurred_values = np.array(
            [ratios[row, column] for row, column in sorted(blurred_tiles)],
            dtype=np.float64,
        )
        sharp_values = np.array(
            [
                ratios[row, column]
                for row in range(GRID_SIZE)
                for column in range(GRID_SIZE)
                if (row, column) not in blurred_tiles
            ],
            dtype=np.float64,
        )
        localization_recall = (
            top_k_localization_recall(ratios, blurred_tiles)
            if blurred_tiles
            else None
        )
        observation_rows.append(
            {
                "pattern": pattern,
                "blur_sigma": str(blur_sigma),
                "blurred_tiles": str(len(blurred_tiles)),
                "area_fraction": f"{area_fraction:.4f}",
                "placement": placement,
                "metric": metric_name,
                "global_score": f"{observed_global:.6f}",
                "global_ratio": f"{observed_global / reference_global:.6f}",
                "tile_mean_ratio": f"{np.mean(ratios):.6f}",
                "lowest_quartile_mean_ratio": (
                    f"{lowest_quartile_mean(ratios):.6f}"
                ),
                "minimum_tile_ratio": f"{np.min(ratios):.6f}",
                "blurred_tile_mean_ratio": _format_optional(
                    float(np.mean(blurred_values)) if blurred_values.size else None
                ),
                "sharp_tile_mean_ratio": _format_optional(
                    float(np.mean(sharp_values)) if sharp_values.size else None
                ),
                "top_k_recall": _format_optional(localization_recall),
            }
        )

        for tile_row in range(GRID_SIZE):
            for tile_column in range(GRID_SIZE):
                tile_rows.append(
                    {
                        "pattern": pattern,
                        "blur_sigma": str(blur_sigma),
                        "blurred_tiles": str(len(blurred_tiles)),
                        "area_fraction": f"{area_fraction:.4f}",
                        "placement": placement,
                        "tile_row": str(tile_row),
                        "tile_column": str(tile_column),
                        "is_blurred": str(
                            int((tile_row, tile_column) in blurred_tiles)
                        ),
                        "metric": metric_name,
                        "reference_score": f"{reference_map[tile_row, tile_column]:.6f}",
                        "observed_score": f"{observed_map[tile_row, tile_column]:.6f}",
                        "score_ratio": f"{ratios[tile_row, tile_column]:.6f}",
                    }
                )


def run_experiment() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Run every deterministic local-blur condition."""
    observation_rows: list[dict[str, str]] = []
    tile_rows: list[dict[str, str]] = []
    for pattern, image in make_patterns().items():
        _record_condition(
            pattern,
            image,
            image.copy(),
            blur_sigma=0,
            placement="none",
            blurred_tiles=set(),
            observation_rows=observation_rows,
            tile_rows=tile_rows,
        )
        for blur_sigma in BLUR_SIGMAS:
            for tile_count, placement in LOCAL_CONDITIONS:
                blurred_tiles = select_blurred_tiles(tile_count, placement)
                observed = apply_local_gaussian_blur(
                    image, blur_sigma, blurred_tiles
                )
                _record_condition(
                    pattern,
                    image,
                    observed,
                    blur_sigma,
                    placement,
                    blurred_tiles,
                    observation_rows,
                    tile_rows,
                )
    return observation_rows, tile_rows


def aggregate_observations(
    rows: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Average normalized observations across patterns and placements."""
    aggregate_rows: list[dict[str, str]] = []
    group_keys = sorted(
        {
            (int(row["blur_sigma"]), int(row["blurred_tiles"]), row["metric"])
            for row in rows
        }
    )
    for blur_sigma, blurred_tiles, metric in group_keys:
        group = [
            row
            for row in rows
            if int(row["blur_sigma"]) == blur_sigma
            and int(row["blurred_tiles"]) == blurred_tiles
            and row["metric"] == metric
        ]

        def mean_field(name: str) -> float:
            return float(np.mean([float(row[name]) for row in group]))

        recall_values = [
            float(row["top_k_recall"])
            for row in group
            if row["top_k_recall"]
        ]
        aggregate_rows.append(
            {
                "blur_sigma": str(blur_sigma),
                "blurred_tiles": str(blurred_tiles),
                "area_fraction": f"{blurred_tiles / (GRID_SIZE * GRID_SIZE):.4f}",
                "metric": metric,
                "observations": str(len(group)),
                "global_ratio_mean": f"{mean_field('global_ratio'):.6f}",
                "tile_mean_ratio_mean": f"{mean_field('tile_mean_ratio'):.6f}",
                "lowest_quartile_mean_ratio_mean": (
                    f"{mean_field('lowest_quartile_mean_ratio'):.6f}"
                ),
                "minimum_tile_ratio_mean": (
                    f"{mean_field('minimum_tile_ratio'):.6f}"
                ),
                "top_k_recall_mean": (
                    f"{np.mean(recall_values):.6f}" if recall_values else ""
                ),
            }
        )
    return aggregate_rows


def validate_expected_relationships(
    observation_rows: Sequence[dict[str, str]],
) -> None:
    """Validate only relative relationships claimed by this experiment."""
    expected_observations = len(make_patterns()) * (
        1 + len(BLUR_SIGMAS) * len(LOCAL_CONDITIONS)
    ) * len(METRICS)
    if len(observation_rows) != expected_observations:
        raise RuntimeError("Unexpected number of observation rows.")

    for row in observation_rows:
        blurred_tiles = int(row["blurred_tiles"])
        if blurred_tiles == 0:
            for field in (
                "global_ratio",
                "tile_mean_ratio",
                "lowest_quartile_mean_ratio",
                "minimum_tile_ratio",
            ):
                if not np.isclose(float(row[field]), 1.0):
                    raise RuntimeError("Sharp control ratios must equal one.")
            continue

        if float(row["blurred_tile_mean_ratio"]) >= 1.0:
            raise RuntimeError("Blurred tiles must score below their sharp controls.")
        if blurred_tiles < GRID_SIZE * GRID_SIZE:
            if not np.isclose(float(row["sharp_tile_mean_ratio"]), 1.0):
                raise RuntimeError("Unchanged tile ratios must equal one.")
            if float(row["minimum_tile_ratio"]) >= float(row["global_ratio"]):
                raise RuntimeError("The lowest tile must reveal a larger relative drop.")

    for pattern in make_patterns():
        for metric in METRICS:
            fully_blurred = [
                float(row["global_ratio"])
                for sigma in BLUR_SIGMAS
                for row in observation_rows
                if row["pattern"] == pattern
                and row["metric"] == metric
                and int(row["blur_sigma"]) == sigma
                and int(row["blurred_tiles"]) == GRID_SIZE * GRID_SIZE
            ]
            if not all(
                left > right
                for left, right in zip(fully_blurred, fully_blurred[1:])
            ):
                raise RuntimeError(
                    f"Full-image {metric} response is not decreasing for {pattern}."
                )


def write_csv(rows: Sequence[dict[str, str]], output_path: Path) -> None:
    """Write a deterministic CSV table."""
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


def _condition_tile_ratios(
    image: NDArray[np.uint8],
    sigma: int,
    blurred_tiles: set[tuple[int, int]],
    metric_name: str,
) -> NDArray[np.float64]:
    """Return tile ratios for one figure condition."""
    metric = METRICS[metric_name]
    observed = apply_local_gaussian_blur(image, sigma, blurred_tiles)
    return tiled_metric_map(observed, metric, TILE_SIZE) / tiled_metric_map(
        image, metric, TILE_SIZE
    )


def write_example_figure(output_path: Path) -> None:
    """Write a synthetic example, known mask, and both metric maps."""
    image = make_patterns()["checkerboard"]
    blurred_tiles = select_blurred_tiles(4, "center")
    observed = apply_local_gaussian_blur(image, 3, blurred_tiles)
    laplacian_ratios = _condition_tile_ratios(
        image, 3, blurred_tiles, "laplacian_variance"
    )
    tenengrad_ratios = _condition_tile_ratios(
        image, 3, blurred_tiles, "tenengrad_energy"
    )

    figure, axes = plt.subplots(1, 4, figsize=(12, 3.2), constrained_layout=True)
    axes[0].imshow(image, cmap="gray", vmin=0, vmax=255)
    axes[0].set_title("Sharp control")
    axes[1].imshow(observed, cmap="gray", vmin=0, vmax=255)
    axes[1].set_title("25% local blur, sigma 3")
    axes[1].add_patch(
        Rectangle(
            (TILE_SIZE, TILE_SIZE),
            TILE_SIZE * 2,
            TILE_SIZE * 2,
            fill=False,
            edgecolor="#f59e0b",
            linewidth=2,
        )
    )
    heatmaps = (
        (laplacian_ratios, "Laplacian tile ratios"),
        (tenengrad_ratios, "Tenengrad tile ratios"),
    )
    for axis, (ratios, title) in zip(axes[2:], heatmaps):
        image_artist = axis.imshow(ratios, cmap="viridis", vmin=0, vmax=1)
        axis.set_title(title)
        axis.set_xticks(range(GRID_SIZE))
        axis.set_yticks(range(GRID_SIZE))
        for row in range(GRID_SIZE):
            for column in range(GRID_SIZE):
                axis.text(
                    column,
                    row,
                    f"{ratios[row, column]:.2f}",
                    ha="center",
                    va="center",
                    fontsize=8,
                    color="white" if ratios[row, column] < 0.55 else "black",
                )
        figure.colorbar(image_artist, ax=axis, fraction=0.046, pad=0.04)
    for axis in axes[:2]:
        axis.set_axis_off()
    figure.suptitle("Controlled spatially localized Gaussian blur", fontsize=12)
    figure.savefig(
        output_path,
        dpi=150,
        metadata={"Software": "research-notes v0.3.0"},
    )
    plt.close(figure)


def _aggregate_value(
    rows: Sequence[dict[str, str]],
    sigma: int,
    blurred_tiles: int,
    metric: str,
    field: str,
) -> float:
    """Read one unique numeric value from the aggregate table."""
    matches = [
        float(row[field])
        for row in rows
        if int(row["blur_sigma"]) == sigma
        and int(row["blurred_tiles"]) == blurred_tiles
        and row["metric"] == metric
    ]
    if len(matches) != 1:
        raise RuntimeError("Expected exactly one aggregate value.")
    return matches[0]


def write_evaluation_figure(
    observation_rows: Sequence[dict[str, str]],
    aggregate_rows: Sequence[dict[str, str]],
    output_path: Path,
) -> None:
    """Visualize global retention, spatial aggregation, and localization."""
    figure, axes = plt.subplots(2, 2, figsize=(10, 7), constrained_layout=True)
    colors = {
        "global_ratio_mean": "#2563eb",
        "tile_mean_ratio_mean": "#0f766e",
        "lowest_quartile_mean_ratio_mean": "#d97706",
        "minimum_tile_ratio_mean": "#b91c1c",
    }
    labels = {
        "global_ratio_mean": "Full-image score",
        "tile_mean_ratio_mean": "Tile mean",
        "lowest_quartile_mean_ratio_mean": "Lowest-quartile mean",
        "minimum_tile_ratio_mean": "Minimum tile",
    }
    tile_counts = (0, 1, 4, 8, 16)
    area_percentages = [count / (GRID_SIZE * GRID_SIZE) * 100 for count in tile_counts]

    for axis, metric, title in (
        (axes[0, 0], "laplacian_variance", "Laplacian variance, sigma 3"),
        (axes[0, 1], "tenengrad_energy", "Tenengrad energy, sigma 3"),
    ):
        for field in colors:
            values = [
                1.0
                if count == 0
                else _aggregate_value(aggregate_rows, 3, count, metric, field)
                for count in tile_counts
            ]
            axis.plot(
                area_percentages,
                values,
                marker="o",
                linewidth=2,
                color=colors[field],
                label=labels[field],
            )
        axis.set(
            title=title,
            xlabel="Blurred image area (%)",
            ylabel="Ratio to matched sharp control",
            xticks=area_percentages,
            ylim=(-0.03, 1.05),
        )
        axis.grid(alpha=0.25)

    for metric, color, label in (
        ("laplacian_variance", "#2563eb", "Laplacian"),
        ("tenengrad_energy", "#b91c1c", "Tenengrad"),
    ):
        global_values = [
            _aggregate_value(aggregate_rows, sigma, 1, metric, "global_ratio_mean")
            for sigma in BLUR_SIGMAS
        ]
        minimum_values = [
            _aggregate_value(
                aggregate_rows, sigma, 1, metric, "minimum_tile_ratio_mean"
            )
            for sigma in BLUR_SIGMAS
        ]
        axes[1, 0].plot(
            BLUR_SIGMAS,
            global_values,
            marker="o",
            linewidth=2,
            color=color,
            label=f"{label}: full image",
        )
        axes[1, 0].plot(
            BLUR_SIGMAS,
            minimum_values,
            marker="s",
            linestyle="--",
            linewidth=2,
            color=color,
            label=f"{label}: minimum tile",
        )
    axes[1, 0].set(
        title="A 6.25% region can be diluted globally",
        xlabel="Gaussian blur sigma (pixels)",
        ylabel="Ratio to matched sharp control",
        xticks=BLUR_SIGMAS,
        ylim=(-0.03, 1.05),
    )
    axes[1, 0].grid(alpha=0.25)

    for metric, color, label in (
        ("laplacian_variance", "#2563eb", "Laplacian"),
        ("tenengrad_energy", "#b91c1c", "Tenengrad"),
    ):
        recall_means = []
        for sigma in BLUR_SIGMAS:
            recalls = [
                float(row["top_k_recall"])
                for row in observation_rows
                if row["metric"] == metric
                and int(row["blur_sigma"]) == sigma
                and 0 < int(row["blurred_tiles"]) < GRID_SIZE * GRID_SIZE
            ]
            recall_means.append(float(np.mean(recalls)))
        axes[1, 1].plot(
            BLUR_SIGMAS,
            recall_means,
            marker="o",
            linewidth=2,
            color=color,
            label=label,
        )
    axes[1, 1].set(
        title="Known-region top-k localization",
        xlabel="Gaussian blur sigma (pixels)",
        ylabel="Mean top-k recall",
        xticks=BLUR_SIGMAS,
        ylim=(0.0, 1.05),
    )
    axes[1, 1].grid(alpha=0.25)

    for axis in axes.ravel():
        axis.legend(frameon=False, fontsize=8)
    figure.suptitle(
        "Local scores expose controlled blur hidden by global aggregation",
        fontsize=12,
    )
    figure.savefig(
        output_path,
        dpi=150,
        metadata={"Software": "research-notes v0.3.0"},
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
    """Generate all v0.3.0 reference artifacts."""
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    observation_rows, tile_rows = run_experiment()
    aggregate_rows = aggregate_observations(observation_rows)
    validate_expected_relationships(observation_rows)

    write_csv(observation_rows, args.output_dir / OBSERVATIONS_CSV_NAME)
    write_csv(tile_rows, args.output_dir / TILES_CSV_NAME)
    write_csv(aggregate_rows, args.output_dir / AGGREGATE_CSV_NAME)
    write_example_figure(args.output_dir / EXAMPLE_FIGURE_NAME)
    write_evaluation_figure(
        observation_rows,
        aggregate_rows,
        args.output_dir / EVALUATION_FIGURE_NAME,
    )

    print("Validated the expected local-blur relationships.")
    print(f"Generated {len(observation_rows)} metric observations.")
    print(f"Generated {len(tile_rows)} tile-level metric observations.")
    print("Wrote three CSV files and two PNG figures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
