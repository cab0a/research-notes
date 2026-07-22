"""Evaluate disk defocus and directional linear-motion blur models."""

from __future__ import annotations

import argparse
import csv
import math
from collections.abc import Sequence
from pathlib import Path
from typing import NamedTuple

import matplotlib
import numpy as np
from numpy.typing import NDArray

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

from research_notes import (
    apply_psf,
    disk_psf,
    laplacian_variance,
    linear_motion_psf,
    tenengrad_energy,
)


IMAGE_SIZE = 256
GRATING_PERIOD = 16.0
GRATING_AXES = (0, 45, 90, 135)
DEFOCUS_RADII = (1, 2, 3, 5)
MOTION_LENGTHS = (5, 9, 15)
MOTION_ANGLES = (0, 45, 90, 135)
NOISE_STANDARD_DEVIATIONS = (0, 5, 15)
NOISE_TRIALS = 10
BASE_SEED = 20261101
METRICS = {
    "laplacian_variance": laplacian_variance,
    "tenengrad_energy": tenengrad_energy,
}

KERNELS_CSV_NAME = "optical_blur_kernels.csv"
TRIALS_CSV_NAME = "optical_blur_trials.csv"
SUMMARY_CSV_NAME = "optical_blur_summary.csv"
DIRECTION_CSV_NAME = "motion_direction_summary.csv"
EXAMPLES_FIGURE_NAME = "optical_blur_examples.png"
SENSITIVITY_FIGURE_NAME = "optical_blur_directional_sensitivity.png"


class BlurCondition(NamedTuple):
    """Describe one declared blur condition and its normalized kernel."""

    condition: str
    blur_model: str
    defocus_radius: int | None
    motion_length: int | None
    motion_angle_degrees: int | None
    kernel: NDArray[np.float64]


def make_grating(angle_degrees: int) -> NDArray[np.uint8]:
    """Create a sinusoidal grating with a declared gradient axis."""
    rows, columns = np.indices((IMAGE_SIZE, IMAGE_SIZE), dtype=np.float64)
    angle_radians = math.radians(angle_degrees)
    phase = columns * math.cos(angle_radians) + rows * math.sin(angle_radians)
    values = 127.5 + 110.0 * np.cos(
        2.0 * np.pi * phase / GRATING_PERIOD
    )
    return np.clip(np.rint(values), 0, 255).astype(np.uint8)


def make_patterns() -> dict[str, NDArray[np.uint8]]:
    """Create oriented gratings and one mixed-orientation checkerboard."""
    patterns = {
        f"grating_{angle}": make_grating(angle) for angle in GRATING_AXES
    }
    rows, columns = np.indices((IMAGE_SIZE, IMAGE_SIZE))
    patterns["checkerboard"] = (
        ((rows // 16 + columns // 16) % 2) * 255
    ).astype(np.uint8)
    return patterns


def pattern_gradient_axis(pattern: str) -> int | None:
    """Return a grating's intensity-gradient axis, if one is declared."""
    if pattern.startswith("grating_"):
        return int(pattern.removeprefix("grating_"))
    return None


def build_conditions() -> list[BlurCondition]:
    """Build the identity, disk-defocus, and linear-motion conditions."""
    conditions = [
        BlurCondition(
            condition="identity",
            blur_model="identity",
            defocus_radius=0,
            motion_length=None,
            motion_angle_degrees=None,
            kernel=disk_psf(0),
        )
    ]
    conditions.extend(
        BlurCondition(
            condition=f"defocus_r{radius}",
            blur_model="disk_defocus",
            defocus_radius=radius,
            motion_length=None,
            motion_angle_degrees=None,
            kernel=disk_psf(radius),
        )
        for radius in DEFOCUS_RADII
    )
    conditions.extend(
        BlurCondition(
            condition=f"motion_l{length}_a{angle}",
            blur_model="linear_motion",
            defocus_radius=None,
            motion_length=length,
            motion_angle_degrees=angle,
            kernel=linear_motion_psf(length, angle),
        )
        for length in MOTION_LENGTHS
        for angle in MOTION_ANGLES
    )
    return conditions


def angular_distance(angle: int, reference: int) -> int:
    """Return the unsigned distance between two line orientations."""
    difference = abs(angle - reference) % 180
    return min(difference, 180 - difference)


def trial_seed(pattern_index: int, noise_index: int, trial: int) -> int:
    """Return one seed shared by all blur conditions in a paired trial."""
    return BASE_SEED + pattern_index * 10_000 + noise_index * 100 + trial


def add_gaussian_noise(
    image: NDArray[np.uint8], standard_deviation: int, seed: int
) -> NDArray[np.uint8]:
    """Add deterministic zero-mean Gaussian noise after optical blur."""
    if standard_deviation == 0:
        return image.copy()
    generator = np.random.default_rng(seed)
    noise = generator.normal(0.0, standard_deviation, image.shape)
    return np.clip(
        np.rint(image.astype(np.float64) + noise),
        0,
        255,
    ).astype(np.uint8)


def _optional_integer(value: int | None) -> str:
    """Format an optional integer for CSV output."""
    return "" if value is None else str(value)


def run_trials() -> list[dict[str, str]]:
    """Run paired-noise trials across all declared blur conditions."""
    rows: list[dict[str, str]] = []
    conditions = build_conditions()
    for pattern_index, (pattern, sharp) in enumerate(make_patterns().items()):
        gradient_axis = pattern_gradient_axis(pattern)
        blurred_inputs = {
            condition.condition: apply_psf(sharp, condition.kernel)
            for condition in conditions
        }
        for noise_index, noise_std in enumerate(NOISE_STANDARD_DEVIATIONS):
            for trial in range(NOISE_TRIALS):
                seed = trial_seed(pattern_index, noise_index, trial)
                sharp_observed = add_gaussian_noise(sharp, noise_std, seed)
                sharp_scores = {
                    metric: function(sharp_observed)
                    for metric, function in METRICS.items()
                }
                for condition in conditions:
                    observed = add_gaussian_noise(
                        blurred_inputs[condition.condition],
                        noise_std,
                        seed,
                    )
                    relative_angle = ""
                    if (
                        gradient_axis is not None
                        and condition.motion_angle_degrees is not None
                    ):
                        relative_angle = str(
                            angular_distance(
                                condition.motion_angle_degrees,
                                gradient_axis,
                            )
                        )
                    for metric, function in METRICS.items():
                        score = function(observed)
                        sharp_score = sharp_scores[metric]
                        rows.append(
                            {
                                "pattern": pattern,
                                "gradient_axis_degrees": _optional_integer(
                                    gradient_axis
                                ),
                                "condition": condition.condition,
                                "blur_model": condition.blur_model,
                                "defocus_radius": _optional_integer(
                                    condition.defocus_radius
                                ),
                                "motion_length": _optional_integer(
                                    condition.motion_length
                                ),
                                "motion_angle_degrees": _optional_integer(
                                    condition.motion_angle_degrees
                                ),
                                "relative_motion_angle_degrees": relative_angle,
                                "noise_std": str(noise_std),
                                "trial": str(trial),
                                "seed": str(seed),
                                "metric": metric,
                                "score": f"{score:.6f}",
                                "matched_sharp_score": f"{sharp_score:.6f}",
                                "ratio_to_matched_sharp": (
                                    f"{score / sharp_score:.6f}"
                                ),
                            }
                        )
    return rows


def summarize_trials(
    trial_rows: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Summarize score and matched-sharp ratios for every condition."""
    summary_rows: list[dict[str, str]] = []
    for pattern in make_patterns():
        gradient_axis = pattern_gradient_axis(pattern)
        for condition in build_conditions():
            relative_angle = ""
            if (
                gradient_axis is not None
                and condition.motion_angle_degrees is not None
            ):
                relative_angle = str(
                    angular_distance(
                        condition.motion_angle_degrees,
                        gradient_axis,
                    )
                )
            for noise_std in NOISE_STANDARD_DEVIATIONS:
                for metric in METRICS:
                    group = [
                        row
                        for row in trial_rows
                        if row["pattern"] == pattern
                        and row["condition"] == condition.condition
                        and int(row["noise_std"]) == noise_std
                        and row["metric"] == metric
                    ]
                    scores = np.array(
                        [float(row["score"]) for row in group],
                        dtype=np.float64,
                    )
                    ratios = np.array(
                        [
                            float(row["ratio_to_matched_sharp"])
                            for row in group
                        ],
                        dtype=np.float64,
                    )
                    summary_rows.append(
                        {
                            "pattern": pattern,
                            "gradient_axis_degrees": _optional_integer(
                                gradient_axis
                            ),
                            "condition": condition.condition,
                            "blur_model": condition.blur_model,
                            "defocus_radius": _optional_integer(
                                condition.defocus_radius
                            ),
                            "motion_length": _optional_integer(
                                condition.motion_length
                            ),
                            "motion_angle_degrees": _optional_integer(
                                condition.motion_angle_degrees
                            ),
                            "relative_motion_angle_degrees": relative_angle,
                            "noise_std": str(noise_std),
                            "metric": metric,
                            "trials": str(len(group)),
                            "score_mean": f"{np.mean(scores):.6f}",
                            "score_sample_std": (
                                f"{np.std(scores, ddof=1):.6f}"
                            ),
                            "score_p10": f"{np.quantile(scores, 0.1):.6f}",
                            "score_median": f"{np.median(scores):.6f}",
                            "score_p90": f"{np.quantile(scores, 0.9):.6f}",
                            "ratio_mean": f"{np.mean(ratios):.6f}",
                            "ratio_sample_std": (
                                f"{np.std(ratios, ddof=1):.6f}"
                            ),
                            "ratio_p10": f"{np.quantile(ratios, 0.1):.6f}",
                            "ratio_median": f"{np.median(ratios):.6f}",
                            "ratio_p90": f"{np.quantile(ratios, 0.9):.6f}",
                        }
                    )
    return summary_rows


def _find_summary(
    rows: Sequence[dict[str, str]],
    pattern: str,
    condition: str,
    noise_std: int,
    metric: str,
) -> dict[str, str]:
    """Find one unique condition summary row."""
    matches = [
        row
        for row in rows
        if row["pattern"] == pattern
        and row["condition"] == condition
        and int(row["noise_std"]) == noise_std
        and row["metric"] == metric
    ]
    if len(matches) != 1:
        raise RuntimeError("Expected one optical-blur summary row.")
    return matches[0]


def summarize_motion_direction(
    summary_rows: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Compare aligned, oblique, and perpendicular motion per grating."""
    direction_rows: list[dict[str, str]] = []
    for gradient_axis in GRATING_AXES:
        pattern = f"grating_{gradient_axis}"
        for length in MOTION_LENGTHS:
            for noise_std in NOISE_STANDARD_DEVIATIONS:
                for metric in METRICS:
                    ratios = {
                        angle: float(
                            _find_summary(
                                summary_rows,
                                pattern,
                                f"motion_l{length}_a{angle}",
                                noise_std,
                                metric,
                            )["ratio_mean"]
                        )
                        for angle in MOTION_ANGLES
                    }
                    aligned_angle = gradient_axis
                    perpendicular_angle = (gradient_axis + 90) % 180
                    oblique_angles = [
                        angle
                        for angle in MOTION_ANGLES
                        if angle not in (aligned_angle, perpendicular_angle)
                    ]
                    aligned_ratio = ratios[aligned_angle]
                    perpendicular_ratio = ratios[perpendicular_angle]
                    direction_rows.append(
                        {
                            "pattern": pattern,
                            "gradient_axis_degrees": str(gradient_axis),
                            "motion_length": str(length),
                            "noise_std": str(noise_std),
                            "metric": metric,
                            "trials_per_angle": str(NOISE_TRIALS),
                            "aligned_angle_degrees": str(aligned_angle),
                            "aligned_ratio_mean": f"{aligned_ratio:.6f}",
                            "oblique_ratio_mean": (
                                f"{np.mean([ratios[a] for a in oblique_angles]):.6f}"
                            ),
                            "perpendicular_angle_degrees": str(
                                perpendicular_angle
                            ),
                            "perpendicular_ratio_mean": (
                                f"{perpendicular_ratio:.6f}"
                            ),
                            "aligned_to_perpendicular_ratio": (
                                f"{aligned_ratio / perpendicular_ratio:.6f}"
                            ),
                            "most_attenuating_angle_degrees": str(
                                min(ratios, key=ratios.get)
                            ),
                            "least_attenuating_angle_degrees": str(
                                max(ratios, key=ratios.get)
                            ),
                            "angular_ratio_range": (
                                f"{max(ratios.values()) - min(ratios.values()):.6f}"
                            ),
                        }
                    )
    return direction_rows


def audit_kernels() -> list[dict[str, str]]:
    """Record normalization, centroid, spread, and symmetry for every PSF."""
    rows: list[dict[str, str]] = []
    for condition in build_conditions():
        kernel = condition.kernel
        row_coordinates, column_coordinates = np.indices(kernel.shape)
        centroid_x = float(np.sum(kernel * column_coordinates))
        centroid_y = float(np.sum(kernel * row_coordinates))
        center_x = (kernel.shape[1] - 1) / 2.0
        center_y = (kernel.shape[0] - 1) / 2.0
        squared_radius = (
            (column_coordinates - centroid_x) ** 2
            + (row_coordinates - centroid_y) ** 2
        )
        rows.append(
            {
                "condition": condition.condition,
                "blur_model": condition.blur_model,
                "defocus_radius": _optional_integer(
                    condition.defocus_radius
                ),
                "motion_length": _optional_integer(condition.motion_length),
                "motion_angle_degrees": _optional_integer(
                    condition.motion_angle_degrees
                ),
                "kernel_height": str(kernel.shape[0]),
                "kernel_width": str(kernel.shape[1]),
                "nonzero_support": str(int(np.count_nonzero(kernel))),
                "weight_sum": f"{np.sum(kernel):.12f}",
                "centroid_offset_x": f"{centroid_x - center_x:.12f}",
                "centroid_offset_y": f"{centroid_y - center_y:.12f}",
                "rms_radius": (
                    f"{math.sqrt(float(np.sum(kernel * squared_radius))):.6f}"
                ),
                "centrosymmetry_max_error": (
                    f"{np.max(np.abs(kernel - np.flip(kernel))):.12f}"
                ),
            }
        )
    return rows


def validate_expected_relationships(
    trial_rows: Sequence[dict[str, str]],
    summary_rows: Sequence[dict[str, str]],
    direction_rows: Sequence[dict[str, str]],
    kernel_rows: Sequence[dict[str, str]],
) -> None:
    """Validate counts and only the relative claims made by this study."""
    condition_count = len(build_conditions())
    expected_trials = (
        len(make_patterns())
        * condition_count
        * len(NOISE_STANDARD_DEVIATIONS)
        * NOISE_TRIALS
        * len(METRICS)
    )
    if len(trial_rows) != expected_trials:
        raise RuntimeError("Unexpected number of optical-blur trial rows.")
    if len(summary_rows) != (
        len(make_patterns())
        * condition_count
        * len(NOISE_STANDARD_DEVIATIONS)
        * len(METRICS)
    ):
        raise RuntimeError("Unexpected number of optical-blur summaries.")
    if len(direction_rows) != (
        len(GRATING_AXES)
        * len(MOTION_LENGTHS)
        * len(NOISE_STANDARD_DEVIATIONS)
        * len(METRICS)
    ):
        raise RuntimeError("Unexpected number of motion-direction summaries.")
    if len(kernel_rows) != condition_count:
        raise RuntimeError("Unexpected number of PSF audit rows.")

    unique_seeds = {row["seed"] for row in trial_rows}
    expected_seeds = (
        len(make_patterns())
        * len(NOISE_STANDARD_DEVIATIONS)
        * NOISE_TRIALS
    )
    if len(unique_seeds) != expected_seeds:
        raise RuntimeError("Unexpected number of paired random seeds.")
    if not all(
        np.isclose(float(row["ratio_to_matched_sharp"]), 1.0)
        for row in trial_rows
        if row["condition"] == "identity"
    ):
        raise RuntimeError("Identity observations must match their controls.")
    if not all(
        np.isclose(float(row["weight_sum"]), 1.0)
        and abs(float(row["centroid_offset_x"])) < 1e-10
        and abs(float(row["centroid_offset_y"])) < 1e-10
        and float(row["centrosymmetry_max_error"]) < 1e-10
        for row in kernel_rows
    ):
        raise RuntimeError("Every PSF must be normalized and centered.")

    clean_direction_rows = [
        row for row in direction_rows if int(row["noise_std"]) == 0
    ]
    if not all(
        float(row["aligned_ratio_mean"])
        < float(row["perpendicular_ratio_mean"])
        for row in clean_direction_rows
    ):
        raise RuntimeError("Aligned motion must attenuate each clean grating more.")
    if not all(
        int(row["most_attenuating_angle_degrees"])
        == int(row["gradient_axis_degrees"])
        for row in clean_direction_rows
    ):
        raise RuntimeError("The clean strongest attenuation angle is unexpected.")

    for metric in METRICS:
        radius_responses = []
        for radius in (0, *DEFOCUS_RADII):
            condition = "identity" if radius == 0 else f"defocus_r{radius}"
            radius_responses.append(
                float(
                    np.mean(
                        [
                            float(
                                _find_summary(
                                    summary_rows,
                                    pattern,
                                    condition,
                                    0,
                                    metric,
                                )["ratio_mean"]
                            )
                            for pattern in make_patterns()
                        ]
                    )
                )
            )
        if not all(
            left > right
            for left, right in zip(radius_responses, radius_responses[1:])
        ):
            raise RuntimeError(
                f"Mean clean defocus response is not decreasing for {metric}."
            )

    for metric in METRICS:
        clean_scores = [
            float(row["score_mean"])
            for row in summary_rows
            if row["condition"] == "defocus_r5"
            and int(row["noise_std"]) == 0
            and row["metric"] == metric
        ]
        noisy_scores = [
            float(row["score_mean"])
            for row in summary_rows
            if row["condition"] == "defocus_r5"
            and int(row["noise_std"]) == 15
            and row["metric"] == metric
        ]
        if np.mean(noisy_scores) <= np.mean(clean_scores):
            raise RuntimeError("Noise must raise the bounded defocus response.")


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
    """Show isotropic and aligned versus perpendicular directional blur."""
    patterns = make_patterns()
    figure, axes = plt.subplots(4, 4, figsize=(9, 9), constrained_layout=True)
    column_titles = (
        "sharp",
        "disk defocus r3",
        "motion l15 aligned",
        "motion l15 perpendicular",
    )
    for row_index, gradient_axis in enumerate(GRATING_AXES):
        pattern = patterns[f"grating_{gradient_axis}"]
        examples = (
            pattern,
            apply_psf(pattern, disk_psf(3)),
            apply_psf(pattern, linear_motion_psf(15, gradient_axis)),
            apply_psf(
                pattern,
                linear_motion_psf(15, (gradient_axis + 90) % 180),
            ),
        )
        for column_index, example in enumerate(examples):
            axis = axes[row_index, column_index]
            axis.imshow(example, cmap="gray", vmin=0, vmax=255)
            if row_index == 0:
                axis.set_title(column_titles[column_index], fontsize=9)
            if column_index == 0:
                axis.set_ylabel(f"gradient axis {gradient_axis} deg")
            axis.set_xticks([])
            axis.set_yticks([])
    figure.suptitle("Controlled disk-defocus and linear-motion examples")
    figure.savefig(
        output_path,
        dpi=150,
        metadata={"Software": "research-notes v0.6.0"},
    )
    plt.close(figure)


def _direction_mean(
    rows: Sequence[dict[str, str]],
    length: int,
    noise_std: int,
    metric: str,
    field: str,
) -> float:
    """Return one mean directional response across the oriented gratings."""
    values = [
        float(row[field])
        for row in rows
        if int(row["motion_length"]) == length
        and int(row["noise_std"]) == noise_std
        and row["metric"] == metric
    ]
    return float(np.mean(values))


def write_sensitivity_figure(
    summary_rows: Sequence[dict[str, str]],
    direction_rows: Sequence[dict[str, str]],
    output_path: Path,
) -> None:
    """Plot direction, defocus-radius, and noise sensitivity summaries."""
    colors = {0: "#dc2626", 45: "#d97706", 90: "#2563eb"}
    labels = {0: "aligned", 45: "oblique", 90: "perpendicular"}
    fields = {
        0: "aligned_ratio_mean",
        45: "oblique_ratio_mean",
        90: "perpendicular_ratio_mean",
    }
    metric_layout = (
        ("laplacian_variance", "Laplacian variance"),
        ("tenengrad_energy", "Tenengrad energy"),
    )
    figure, axes = plt.subplots(2, 2, figsize=(10, 7), constrained_layout=True)
    for column, (metric, metric_label) in enumerate(metric_layout):
        for relative_angle in (0, 45, 90):
            responses = [
                _direction_mean(
                    direction_rows,
                    length,
                    noise_std=0,
                    metric=metric,
                    field=fields[relative_angle],
                )
                for length in MOTION_LENGTHS
            ]
            axes[0, column].plot(
                MOTION_LENGTHS,
                responses,
                marker="o",
                linewidth=2,
                color=colors[relative_angle],
                label=labels[relative_angle],
            )
        axes[0, column].set(
            title=f"{metric_label}: linear motion",
            xlabel="Motion PSF length (pixels)",
            ylabel="Mean ratio to paired sharp input",
            xticks=MOTION_LENGTHS,
        )
        axes[0, column].legend(frameon=False)
        axes[0, column].grid(alpha=0.25)

    for metric, metric_label in metric_layout:
        responses = []
        lower = []
        upper = []
        for radius in (0, *DEFOCUS_RADII):
            condition = "identity" if radius == 0 else f"defocus_r{radius}"
            values = [
                float(
                    _find_summary(
                        summary_rows,
                        pattern,
                        condition,
                        0,
                        metric,
                    )["ratio_mean"]
                )
                for pattern in make_patterns()
            ]
            responses.append(float(np.mean(values)))
            lower.append(float(np.min(values)))
            upper.append(float(np.max(values)))
        color = "#1d4ed8" if metric == "laplacian_variance" else "#c2410c"
        axes[1, 0].plot(
            (0, *DEFOCUS_RADII),
            responses,
            marker="o",
            linewidth=2,
            color=color,
            label=metric_label,
        )
        axes[1, 0].fill_between(
            (0, *DEFOCUS_RADII),
            lower,
            upper,
            color=color,
            alpha=0.12,
        )
    axes[1, 0].set(
        title="Disk-defocus response across patterns",
        xlabel="Disk PSF radius (pixels)",
        ylabel="Mean ratio to paired sharp input",
        xticks=(0, *DEFOCUS_RADII),
    )
    axes[1, 0].legend(frameon=False)
    axes[1, 0].grid(alpha=0.25)

    for metric, metric_label in metric_layout:
        selectivity = [
            _direction_mean(
                direction_rows,
                length=15,
                noise_std=noise_std,
                metric=metric,
                field="aligned_to_perpendicular_ratio",
            )
            for noise_std in NOISE_STANDARD_DEVIATIONS
        ]
        color = "#1d4ed8" if metric == "laplacian_variance" else "#c2410c"
        axes[1, 1].plot(
            NOISE_STANDARD_DEVIATIONS,
            selectivity,
            marker="o",
            linewidth=2,
            color=color,
            label=metric_label,
        )
    axes[1, 1].axhline(1.0, color="#6b7280", linestyle="--", linewidth=1)
    axes[1, 1].set(
        title="Noise weakens directional contrast at length 15",
        xlabel="Gaussian noise standard deviation",
        ylabel="Aligned / perpendicular response ratio",
        xticks=NOISE_STANDARD_DEVIATIONS,
    )
    axes[1, 1].legend(frameon=False)
    axes[1, 1].grid(alpha=0.25)

    figure.suptitle("Focus metrics depend on optical model and direction")
    figure.savefig(
        output_path,
        dpi=150,
        metadata={"Software": "research-notes v0.6.0"},
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
    """Generate all v0.6.0 reference artifacts."""
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    kernel_rows = audit_kernels()
    trial_rows = run_trials()
    summary_rows = summarize_trials(trial_rows)
    direction_rows = summarize_motion_direction(summary_rows)
    validate_expected_relationships(
        trial_rows,
        summary_rows,
        direction_rows,
        kernel_rows,
    )

    write_csv(kernel_rows, args.output_dir / KERNELS_CSV_NAME)
    write_csv(trial_rows, args.output_dir / TRIALS_CSV_NAME)
    write_csv(summary_rows, args.output_dir / SUMMARY_CSV_NAME)
    write_csv(direction_rows, args.output_dir / DIRECTION_CSV_NAME)
    write_examples_figure(args.output_dir / EXAMPLES_FIGURE_NAME)
    write_sensitivity_figure(
        summary_rows,
        direction_rows,
        args.output_dir / SENSITIVITY_FIGURE_NAME,
    )

    print("Validated the expected optical-blur relationships.")
    print(f"Generated {len(trial_rows)} metric trial observations.")
    print(f"Generated {len(summary_rows)} condition summaries.")
    print(f"Generated {len(direction_rows)} direction summaries.")
    print("Wrote four CSV files and two PNG figures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
