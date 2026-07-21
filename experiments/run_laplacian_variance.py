"""Run the controlled Laplacian-variance blur and noise experiment."""

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

from research_notes import laplacian_variance


IMAGE_SIZE = 256
BLUR_SIGMAS = (0, 1, 2, 3)
NOISE_STANDARD_DEVIATIONS = (0, 5, 15)
BASE_SEED = 20260721
CSV_NAME = "laplacian_variance_summary.csv"
FIGURE_NAME = "laplacian_variance.png"


def make_checkerboard() -> NDArray[np.uint8]:
    """Create a high-contrast checkerboard with 16-pixel cells."""
    rows, columns = np.indices((IMAGE_SIZE, IMAGE_SIZE))
    return (((rows // 16 + columns // 16) % 2) * 255).astype(np.uint8)


def make_vertical_bars() -> NDArray[np.uint8]:
    """Create alternating vertical bars with an eight-pixel period."""
    columns = np.arange(IMAGE_SIZE)
    row = (((columns // 8) % 2) * 255).astype(np.uint8)
    return np.repeat(row[np.newaxis, :], IMAGE_SIZE, axis=0)


def make_geometric_shapes() -> NDArray[np.uint8]:
    """Create a deterministic mixture of edges, curves, and flat regions."""
    image = np.full((IMAGE_SIZE, IMAGE_SIZE), 32, dtype=np.uint8)
    cv2.rectangle(image, (24, 24), (112, 104), 220, thickness=-1)
    cv2.rectangle(image, (42, 42), (94, 86), 70, thickness=-1)
    cv2.circle(image, (180, 70), 42, 245, thickness=-1)
    cv2.circle(image, (180, 70), 18, 80, thickness=-1)
    cv2.line(image, (18, 222), (230, 126), 200, thickness=5)
    cv2.line(image, (24, 132), (224, 232), 120, thickness=3)
    return image


def apply_gaussian_blur(
    image: NDArray[np.uint8], sigma: int
) -> NDArray[np.uint8]:
    """Apply Gaussian blur, treating sigma zero as the unmodified control."""
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
    """Add seeded zero-mean Gaussian noise in intensity units and clip to uint8."""
    if standard_deviation == 0:
        return image.copy()
    generator = np.random.default_rng(seed)
    noise = generator.normal(0.0, standard_deviation, image.shape)
    return np.clip(image.astype(np.float64) + noise, 0, 255).astype(np.uint8)


def run_experiment() -> list[dict[str, str]]:
    """Evaluate every controlled pattern, blur, and noise combination."""
    patterns = {
        "checkerboard": make_checkerboard(),
        "vertical_bars": make_vertical_bars(),
        "geometric_shapes": make_geometric_shapes(),
    }
    rows: list[dict[str, str]] = []

    for pattern_index, (pattern_name, image) in enumerate(patterns.items()):
        for blur_index, blur_sigma in enumerate(BLUR_SIGMAS):
            blurred = apply_gaussian_blur(image, blur_sigma)
            for noise_index, noise_std in enumerate(NOISE_STANDARD_DEVIATIONS):
                seed = BASE_SEED + pattern_index * 100 + blur_index * 10 + noise_index
                observed = add_gaussian_noise(blurred, noise_std, seed)
                rows.append(
                    {
                        "pattern": pattern_name,
                        "blur_sigma": str(blur_sigma),
                        "noise_std": str(noise_std),
                        "seed": str(seed),
                        "laplacian_variance": f"{laplacian_variance(observed):.6f}",
                    }
                )
    return rows


def validate_expected_relationships(rows: Sequence[dict[str, str]]) -> None:
    """Fail if the reference observations violate the stated relative checks."""
    patterns = {row["pattern"] for row in rows}
    for pattern in patterns:
        noiseless_scores = [
            float(row["laplacian_variance"])
            for blur_sigma in BLUR_SIGMAS
            for row in rows
            if row["pattern"] == pattern
            and int(row["blur_sigma"]) == blur_sigma
            and int(row["noise_std"]) == 0
        ]
        if not all(
            left > right
            for left, right in zip(noiseless_scores, noiseless_scores[1:])
        ):
            raise RuntimeError(
                f"Noiseless scores are not strictly decreasing for {pattern}."
            )

        noisy_blurred_scores = [
            float(row["laplacian_variance"])
            for noise_std in NOISE_STANDARD_DEVIATIONS
            for row in rows
            if row["pattern"] == pattern
            and int(row["blur_sigma"]) == 3
            and int(row["noise_std"]) == noise_std
        ]
        if not all(
            left < right
            for left, right in zip(
                noisy_blurred_scores, noisy_blurred_scores[1:]
            )
        ):
            raise RuntimeError(
                f"Noise does not strictly raise the sigma-3 score for {pattern}."
            )


def write_csv(rows: Sequence[dict[str, str]], output_path: Path) -> None:
    """Write experiment rows with a stable schema and numeric formatting."""
    fieldnames = [
        "pattern",
        "blur_sigma",
        "noise_std",
        "seed",
        "laplacian_variance",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _mean_score(
    rows: Sequence[dict[str, str]], blur_sigma: int, noise_std: int
) -> float:
    scores = [
        float(row["laplacian_variance"])
        for row in rows
        if int(row["blur_sigma"]) == blur_sigma
        and int(row["noise_std"]) == noise_std
    ]
    return float(np.mean(scores))


def write_figure(rows: Sequence[dict[str, str]], output_path: Path) -> None:
    """Plot the aggregate blur response and the noisy blurred-image response."""
    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.titleweight": "bold",
            "axes.grid": True,
            "grid.alpha": 0.25,
            "figure.facecolor": "white",
        }
    )
    figure, axes = plt.subplots(1, 2, figsize=(10, 4.2), constrained_layout=True)

    for noise_std in NOISE_STANDARD_DEVIATIONS:
        means = [_mean_score(rows, sigma, noise_std) for sigma in BLUR_SIGMAS]
        axes[0].plot(
            BLUR_SIGMAS,
            means,
            marker="o",
            linewidth=2,
            label=f"Noise SD {noise_std}",
        )
    axes[0].set(
        title="Mean response across synthetic patterns",
        xlabel="Gaussian blur sigma (pixels)",
        ylabel="Laplacian variance (log scale)",
        xticks=BLUR_SIGMAS,
        yscale="log",
    )
    axes[0].legend(frameon=False)

    for pattern in ("checkerboard", "vertical_bars", "geometric_shapes"):
        scores = [
            float(row["laplacian_variance"])
            for noise_std in NOISE_STANDARD_DEVIATIONS
            for row in rows
            if row["pattern"] == pattern
            and int(row["blur_sigma"]) == 3
            and int(row["noise_std"]) == noise_std
        ]
        axes[1].plot(
            NOISE_STANDARD_DEVIATIONS,
            scores,
            marker="o",
            linewidth=2,
            label=pattern.replace("_", " ").title(),
        )
    axes[1].set(
        title="Noise response at blur sigma 3",
        xlabel="Gaussian noise standard deviation",
        ylabel="Laplacian variance",
        xticks=NOISE_STANDARD_DEVIATIONS,
    )
    axes[1].legend(frameon=False)

    figure.suptitle("Laplacian variance responds to both blur and noise", fontsize=12)
    figure.savefig(
        output_path,
        dpi=150,
        metadata={"Software": "research-notes v0.1.0"},
    )
    plt.close(figure)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results"),
        help="Directory for the generated CSV and PNG files (default: results)",
    )
    return parser.parse_args()


def main() -> int:
    """Generate all reference experiment artifacts."""
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    rows = run_experiment()
    validate_expected_relationships(rows)
    write_csv(rows, args.output_dir / CSV_NAME)
    write_figure(rows, args.output_dir / FIGURE_NAME)
    print("Validated the expected within-experiment relationships.")
    print(f"Generated {len(rows)} controlled observations.")
    print(f"Wrote {CSV_NAME} and {FIGURE_NAME}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
