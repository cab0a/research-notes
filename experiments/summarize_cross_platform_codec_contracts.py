"""Aggregate JPEG decoded-pixel observations from platform CI artifacts."""

from __future__ import annotations

import argparse
import base64
import csv
import gzip
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


PLATFORM_MANIFEST_NAME = "jpeg_platform_codec_manifest.csv"
OBSERVATIONS_NAME = "jpeg_decoded_pixel_observations.csv"
PAIR_OBSERVATIONS_NAME = "jpeg_decoder_pair_observations.csv"
COMBINED_MANIFEST_NAME = "jpeg_cross_platform_codec_manifest.csv"
COMBINED_OBSERVATIONS_NAME = "jpeg_cross_platform_observations.csv"
COMBINED_PAIRS_NAME = "jpeg_cross_platform_decoder_pairs.csv"
SUMMARY_NAME = "jpeg_cross_platform_contract_summary.csv"
FIGURE_NAME = "jpeg_cross_platform_contracts.png"
LOG_PAYLOAD_NAMES = (
    COMBINED_MANIFEST_NAME,
    COMBINED_OBSERVATIONS_NAME,
    COMBINED_PAIRS_NAME,
    SUMMARY_NAME,
)


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read one UTF-8 CSV report."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Sequence[dict[str, str]]) -> None:
    """Write deterministic CSV rows."""
    if not rows:
        raise ValueError("rows must not be empty")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(rows[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def collect_rows(input_dir: Path, filename: str) -> list[dict[str, str]]:
    """Collect one report type recursively from downloaded artifacts."""
    paths = sorted(input_dir.rglob(filename))
    if not paths:
        raise FileNotFoundError(f"No {filename} files found under {input_dir}")
    return [row for path in paths for row in read_csv(path)]


def validate_observations(
    manifests: Sequence[dict[str, str]],
    observations: Sequence[dict[str, str]],
    pairs: Sequence[dict[str, str]],
    expected_platform_count: int,
) -> list[str]:
    """Validate matrix coverage and structural contracts."""
    platform_labels = sorted({row["platform_label"] for row in manifests})
    if len(platform_labels) != expected_platform_count:
        raise RuntimeError(
            f"Expected {expected_platform_count} platforms, found "
            f"{len(platform_labels)}."
        )
    if len(manifests) != expected_platform_count * 2:
        raise RuntimeError("Expected two decoder manifest rows per platform.")
    if len(observations) != expected_platform_count * 12 * 2:
        raise RuntimeError("Unexpected cross-platform observation count.")
    if len(pairs) != expected_platform_count * 12:
        raise RuntimeError("Unexpected cross-platform decoder-pair count.")
    if not all(
        row["structure_contract"] == "1"
        and row["shape_contract"] == "1"
        and row["dtype_contract"] == "1"
        for row in observations
    ):
        raise RuntimeError("A structural decoded-pixel contract failed.")

    observation_keys = {
        (row["platform_label"], row["fixture_id"], row["decoder"])
        for row in observations
    }
    if len(observation_keys) != len(observations):
        raise RuntimeError("Duplicate platform, fixture, and decoder rows found.")
    pair_keys = {
        (row["platform_label"], row["fixture_id"]) for row in pairs
    }
    if len(pair_keys) != len(pairs):
        raise RuntimeError("Duplicate platform and fixture pair rows found.")
    return platform_labels


def summarize_cross_platform(
    observations: Sequence[dict[str, str]],
    platform_labels: Sequence[str],
) -> list[dict[str, str]]:
    """Summarize each fixture and decoder across all platform profiles."""
    rows: list[dict[str, str]] = []
    fixture_ids = sorted({row["fixture_id"] for row in observations})
    decoders = sorted({row["decoder"] for row in observations})
    for fixture_id in fixture_ids:
        for decoder in decoders:
            group = [
                row
                for row in observations
                if row["fixture_id"] == fixture_id
                and row["decoder"] == decoder
            ]
            first = group[0]
            unique_hashes = {
                row["decoded_bgr_sha256"] for row in group
            }
            rows.append(
                {
                    "fixture_id": fixture_id,
                    "pattern": first["pattern"],
                    "quality_control": first["quality_control"],
                    "chroma_sampling": first["chroma_sampling"],
                    "decoder": decoder,
                    "platform_profiles": str(len(platform_labels)),
                    "observations": str(len(group)),
                    "unique_decoded_sha256_count": str(len(unique_hashes)),
                    "cross_platform_exact_hash_agreement": str(
                        int(len(unique_hashes) == 1)
                    ),
                    "all_profiles_exact_reference": str(
                        int(
                            all(
                                row["exact_reference_pixels"] == "1"
                                for row in group
                            )
                        )
                    ),
                    "all_profiles_within_one_code_value": str(
                        int(
                            all(
                                row["within_one_code_value"] == "1"
                                for row in group
                            )
                        )
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
                    "laplacian_ratio_min": (
                        f"{min(float(row['laplacian_to_reference_ratio']) for row in group):.9f}"
                    ),
                    "laplacian_ratio_max": (
                        f"{max(float(row['laplacian_to_reference_ratio']) for row in group):.9f}"
                    ),
                    "tenengrad_ratio_min": (
                        f"{min(float(row['tenengrad_to_reference_ratio']) for row in group):.9f}"
                    ),
                    "tenengrad_ratio_max": (
                        f"{max(float(row['tenengrad_to_reference_ratio']) for row in group):.9f}"
                    ),
                }
            )
    return rows


def plot_cross_platform(
    observations: Sequence[dict[str, str]],
    summary_rows: Sequence[dict[str, str]],
    platform_labels: Sequence[str],
    output_path: Path,
) -> None:
    """Visualize exact rates and numerical error across platform profiles."""
    decoders = ("opencv", "pillow")
    exact = np.zeros((len(platform_labels), len(decoders)), dtype=np.float64)
    bounded = np.zeros_like(exact)
    maximum = np.zeros_like(exact)
    for platform_index, platform_label in enumerate(platform_labels):
        for decoder_index, decoder in enumerate(decoders):
            group = [
                row
                for row in observations
                if row["platform_label"] == platform_label
                and row["decoder"] == decoder
            ]
            exact[platform_index, decoder_index] = np.mean(
                [int(row["exact_reference_pixels"]) for row in group]
            )
            bounded[platform_index, decoder_index] = np.mean(
                [int(row["within_one_code_value"]) for row in group]
            )
            maximum[platform_index, decoder_index] = max(
                int(row["maximum_absolute_error"]) for row in group
            )

    figure, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    for axis, values, title, color_limit in (
        (axes[0, 0], exact, "Exact reference rate", (0.0, 1.0)),
        (axes[0, 1], bounded, "Within-one rate", (0.0, 1.0)),
        (axes[1, 0], maximum, "Maximum code-value error", None),
    ):
        image = axis.imshow(
            values,
            aspect="auto",
            cmap="Blues",
            vmin=None if color_limit is None else color_limit[0],
            vmax=None if color_limit is None else color_limit[1],
        )
        axis.set_xticks(range(len(decoders)), decoders)
        axis.set_yticks(range(len(platform_labels)), platform_labels)
        axis.set_title(title)
        for row_index in range(values.shape[0]):
            for column_index in range(values.shape[1]):
                value = values[row_index, column_index]
                label = f"{value:.3f}" if title != "Maximum code-value error" else f"{value:.0f}"
                axis.text(
                    column_index,
                    row_index,
                    label,
                    ha="center",
                    va="center",
                    color="black",
                )
        figure.colorbar(image, ax=axis, shrink=0.75)

    hash_counts = {
        decoder: [
            int(row["unique_decoded_sha256_count"])
            for row in summary_rows
            if row["decoder"] == decoder
        ]
        for decoder in decoders
    }
    positions = np.arange(len(hash_counts["opencv"]))
    axes[1, 1].plot(
        positions,
        hash_counts["opencv"],
        "o-",
        label="OpenCV",
        color="#3267a8",
    )
    axes[1, 1].plot(
        positions,
        hash_counts["pillow"],
        "s--",
        label="Pillow",
        color="#d17a22",
    )
    axes[1, 1].axhline(1, color="#666666", linewidth=1)
    axes[1, 1].set_xlabel("Fixed JPEG fixture index")
    axes[1, 1].set_ylabel("Unique decoded hashes")
    axes[1, 1].set_title("Cross-platform decoded hash multiplicity")
    axes[1, 1].legend()
    axes[1, 1].grid(alpha=0.25)
    figure.suptitle("JPEG decoded-pixel contracts across platform builds")
    figure.savefig(output_path, dpi=160)
    plt.close(figure)


def emit_log_payload(output_dir: Path, chunk_size: int = 1000) -> None:
    """Print a deterministic, compressed copy of the combined CSV reports."""
    reports = {
        name: (output_dir / name).read_text(encoding="utf-8")
        for name in LOG_PAYLOAD_NAMES
    }
    serialized = json.dumps(
        reports,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    compressed = gzip.compress(serialized, mtime=0)
    payload = base64.b64encode(compressed).decode("ascii")
    digest = hashlib.sha256(compressed).hexdigest()
    chunk_count = (len(payload) + chunk_size - 1) // chunk_size
    print(
        "V010_RESULTS_PAYLOAD_BEGIN "
        f"chunks={chunk_count} gzip_sha256={digest}"
    )
    for index in range(chunk_count):
        start = index * chunk_size
        chunk = payload[start : start + chunk_size]
        print(f"V010_RESULTS_PAYLOAD_{index:04d}={chunk}")
    print("V010_RESULTS_PAYLOAD_END")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Aggregate cross-platform JPEG contract observations."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="Directory containing downloaded platform artifacts.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory for combined CSV and PNG reports.",
    )
    parser.add_argument(
        "--expected-platform-count",
        type=int,
        default=5,
        help="Required number of unique platform profiles.",
    )
    parser.add_argument(
        "--emit-log-payload",
        action="store_true",
        help="Print a compressed copy of the combined CSV reports.",
    )
    return parser.parse_args()


def main() -> None:
    """Collect, validate, summarize, and plot matrix observations."""
    args = parse_args()
    manifests = collect_rows(args.input_dir, PLATFORM_MANIFEST_NAME)
    observations = collect_rows(args.input_dir, OBSERVATIONS_NAME)
    pairs = collect_rows(args.input_dir, PAIR_OBSERVATIONS_NAME)
    platform_labels = validate_observations(
        manifests,
        observations,
        pairs,
        args.expected_platform_count,
    )
    manifests.sort(key=lambda row: (row["platform_label"], row["decoder"]))
    observations.sort(
        key=lambda row: (
            row["platform_label"],
            row["fixture_id"],
            row["decoder"],
        )
    )
    pairs.sort(key=lambda row: (row["platform_label"], row["fixture_id"]))
    summary_rows = summarize_cross_platform(observations, platform_labels)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / COMBINED_MANIFEST_NAME, manifests)
    write_csv(args.output_dir / COMBINED_OBSERVATIONS_NAME, observations)
    write_csv(args.output_dir / COMBINED_PAIRS_NAME, pairs)
    write_csv(args.output_dir / SUMMARY_NAME, summary_rows)
    plot_cross_platform(
        observations,
        summary_rows,
        platform_labels,
        args.output_dir / FIGURE_NAME,
    )
    exact = sum(
        int(row["exact_reference_pixels"]) for row in observations
    )
    bounded = sum(
        int(row["within_one_code_value"]) for row in observations
    )
    print(
        "Cross-platform aggregation complete: "
        f"{len(platform_labels)} profiles, {len(observations)} observations, "
        f"{exact} exact, {bounded} within one code value."
    )
    if args.emit_log_payload:
        emit_log_payload(args.output_dir)


if __name__ == "__main__":
    main()
