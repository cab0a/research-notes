"""Aggregate advanced JPEG decoder-family observations from CI artifacts."""

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


PLATFORM_MANIFEST_NAME = "jpeg_advanced_codec_manifest.csv"
OBSERVATIONS_NAME = "jpeg_advanced_decoder_observations.csv"
PAIRWISE_NAME = "jpeg_advanced_pairwise_differences.csv"
SYNTAX_EQUIVALENCE_NAME = "jpeg_advanced_syntax_equivalence.csv"
COMBINED_MANIFEST_NAME = "jpeg_advanced_cross_platform_codec_manifest.csv"
COMBINED_OBSERVATIONS_NAME = "jpeg_advanced_cross_platform_observations.csv"
COMBINED_PAIRS_NAME = "jpeg_advanced_cross_platform_pairs.csv"
COMBINED_EQUIVALENCE_NAME = (
    "jpeg_advanced_cross_platform_syntax_equivalence.csv"
)
SUMMARY_NAME = "jpeg_advanced_cross_platform_summary.csv"
PAIR_SUMMARY_NAME = "jpeg_advanced_cross_platform_pair_summary.csv"
FIGURE_NAME = "jpeg_advanced_cross_platform_codec_families.png"
DECODERS = ("opencv", "pillow", "ffmpeg")
FIXTURE_COUNT = 10
PAIR_COUNT_PER_FIXTURE = 3
CONTROL_COUNT = 5
LOG_PAYLOAD_NAMES = (
    COMBINED_MANIFEST_NAME,
    COMBINED_OBSERVATIONS_NAME,
    COMBINED_PAIRS_NAME,
    COMBINED_EQUIVALENCE_NAME,
    SUMMARY_NAME,
    PAIR_SUMMARY_NAME,
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


def validate_coverage(
    manifests: Sequence[dict[str, str]],
    observations: Sequence[dict[str, str]],
    pairs: Sequence[dict[str, str]],
    equivalence: Sequence[dict[str, str]],
    expected_platform_count: int,
) -> list[str]:
    """Validate matrix coverage and non-negotiable interface contracts."""
    platform_labels = sorted({row["platform_label"] for row in manifests})
    if len(platform_labels) != expected_platform_count:
        raise RuntimeError(
            f"Expected {expected_platform_count} platforms, found "
            f"{len(platform_labels)}"
        )
    if len(manifests) != expected_platform_count * len(DECODERS):
        raise RuntimeError("Expected three decoder manifests per platform")
    if len(observations) != (
        expected_platform_count * FIXTURE_COUNT * len(DECODERS)
    ):
        raise RuntimeError("Unexpected advanced observation count")
    if len(pairs) != (
        expected_platform_count * FIXTURE_COUNT * PAIR_COUNT_PER_FIXTURE
    ):
        raise RuntimeError("Unexpected advanced pair count")
    if len(equivalence) != (
        expected_platform_count * CONTROL_COUNT * len(DECODERS)
    ):
        raise RuntimeError("Unexpected controlled syntax comparison count")
    if not all(
        row["structure_contract"] == "1"
        and row["shape_contract"] == "1"
        and row["dtype_contract"] == "1"
        for row in observations
    ):
        raise RuntimeError("An advanced JPEG interface contract failed")
    observation_keys = {
        (row["platform_label"], row["fixture_id"], row["decoder"])
        for row in observations
    }
    if len(observation_keys) != len(observations):
        raise RuntimeError("Duplicate platform, fixture, and decoder rows found")
    pair_keys = {
        (
            row["platform_label"],
            row["fixture_id"],
            row["reference_decoder"],
            row["candidate_decoder"],
        )
        for row in pairs
    }
    if len(pair_keys) != len(pairs):
        raise RuntimeError("Duplicate platform and decoder-pair rows found")
    return platform_labels


def summarize_observations(
    observations: Sequence[dict[str, str]],
    platform_labels: Sequence[str],
) -> list[dict[str, str]]:
    """Summarize every fixed fixture and decoder across platforms."""
    rows: list[dict[str, str]] = []
    fixture_ids = sorted({row["fixture_id"] for row in observations})
    for fixture_id in fixture_ids:
        for decoder in DECODERS:
            group = [
                row
                for row in observations
                if row["fixture_id"] == fixture_id
                and row["decoder"] == decoder
            ]
            first = group[0]
            hashes = {row["decoded_bgr_sha256"] for row in group}
            rows.append(
                {
                    "fixture_id": fixture_id,
                    "syntax_class": first["syntax_class"],
                    "source_mode": first["source_mode"],
                    "decoder": decoder,
                    "platform_profiles": str(len(platform_labels)),
                    "observations": str(len(group)),
                    "unique_decoded_sha256_count": str(len(hashes)),
                    "cross_platform_exact_hash_agreement": str(
                        int(len(hashes) == 1)
                    ),
                    "exact_reference_rate": (
                        f"{np.mean([int(row['exact_reference_pixels']) for row in group]):.6f}"
                    ),
                    "within_one_code_value_rate": (
                        f"{np.mean([int(row['within_one_code_value']) for row in group]):.6f}"
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


def summarize_pairs(
    pairs: Sequence[dict[str, str]], platform_labels: Sequence[str]
) -> list[dict[str, str]]:
    """Summarize every decoder-family pair across platform profiles."""
    rows: list[dict[str, str]] = []
    keys = sorted(
        {
            (
                row["fixture_id"],
                row["reference_decoder"],
                row["candidate_decoder"],
            )
            for row in pairs
        }
    )
    for fixture_id, reference_decoder, candidate_decoder in keys:
        group = [
            row
            for row in pairs
            if row["fixture_id"] == fixture_id
            and row["reference_decoder"] == reference_decoder
            and row["candidate_decoder"] == candidate_decoder
        ]
        rows.append(
            {
                "fixture_id": fixture_id,
                "syntax_class": group[0]["syntax_class"],
                "reference_decoder": reference_decoder,
                "candidate_decoder": candidate_decoder,
                "platform_profiles": str(len(platform_labels)),
                "exact_pixel_rate": (
                    f"{np.mean([int(row['exact_pixels']) for row in group]):.6f}"
                ),
                "within_one_code_value_rate": (
                    f"{np.mean([int(row['within_one_code_value']) for row in group]):.6f}"
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
            }
        )
    return rows


def plot_cross_platform(
    summary: Sequence[dict[str, str]], output_path: Path
) -> None:
    """Visualize decoder-family contracts across the platform matrix."""
    fixture_ids = sorted({row["fixture_id"] for row in summary})
    fields = (
        ("exact_reference_rate", "Exact reference rate", ".3f"),
        (
            "within_one_code_value_rate",
            "Within-one diagnostic rate",
            ".3f",
        ),
        ("maximum_absolute_error_max", "Maximum code-value error", ".0f"),
        (
            "unique_decoded_sha256_count",
            "Unique cross-platform decoded hashes",
            ".0f",
        ),
    )
    figure, axes = plt.subplots(2, 2, figsize=(13, 10), constrained_layout=True)
    for axis, (field, title, number_format) in zip(axes.flat, fields):
        values = np.array(
            [
                [
                    float(
                        next(
                            row[field]
                            for row in summary
                            if row["fixture_id"] == fixture_id
                            and row["decoder"] == decoder
                        )
                    )
                    for decoder in DECODERS
                ]
                for fixture_id in fixture_ids
            ],
            dtype=np.float64,
        )
        image = axis.imshow(values, aspect="auto", cmap="Blues")
        axis.set_xticks(range(len(DECODERS)), DECODERS)
        axis.set_yticks(range(len(fixture_ids)), fixture_ids)
        axis.set_title(title)
        for row_index in range(values.shape[0]):
            for column_index in range(values.shape[1]):
                axis.text(
                    column_index,
                    row_index,
                    format(values[row_index, column_index], number_format),
                    ha="center",
                    va="center",
                    color="black",
                )
        figure.colorbar(image, ax=axis, shrink=0.72)
    figure.suptitle(
        "Advanced JPEG contracts across platforms and decoder families"
    )
    figure.savefig(output_path, dpi=160)
    plt.close(figure)


def emit_log_payload(output_dir: Path, chunk_size: int = 1000) -> None:
    """Print a deterministic compressed copy of combined CSV reports."""
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
        "V011_RESULTS_PAYLOAD_BEGIN "
        f"chunks={chunk_count} gzip_sha256={digest}"
    )
    for index in range(chunk_count):
        start = index * chunk_size
        print(
            f"V011_RESULTS_PAYLOAD_{index:04d}="
            f"{payload[start:start + chunk_size]}"
        )
    print("V011_RESULTS_PAYLOAD_END")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Aggregate advanced JPEG decoder-family observations."
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
    pairs = collect_rows(args.input_dir, PAIRWISE_NAME)
    equivalence = collect_rows(args.input_dir, SYNTAX_EQUIVALENCE_NAME)
    platform_labels = validate_coverage(
        manifests,
        observations,
        pairs,
        equivalence,
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
    pairs.sort(
        key=lambda row: (
            row["platform_label"],
            row["fixture_id"],
            row["reference_decoder"],
            row["candidate_decoder"],
        )
    )
    equivalence.sort(
        key=lambda row: (
            row["platform_label"],
            row["control_id"],
            row["decoder"],
        )
    )
    summary = summarize_observations(observations, platform_labels)
    pair_summary = summarize_pairs(pairs, platform_labels)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / COMBINED_MANIFEST_NAME, manifests)
    write_csv(args.output_dir / COMBINED_OBSERVATIONS_NAME, observations)
    write_csv(args.output_dir / COMBINED_PAIRS_NAME, pairs)
    write_csv(args.output_dir / COMBINED_EQUIVALENCE_NAME, equivalence)
    write_csv(args.output_dir / SUMMARY_NAME, summary)
    write_csv(args.output_dir / PAIR_SUMMARY_NAME, pair_summary)
    plot_cross_platform(summary, args.output_dir / FIGURE_NAME)

    exact = sum(int(row["exact_reference_pixels"]) for row in observations)
    bounded = sum(
        int(row["within_one_code_value"]) for row in observations
    )
    print(
        "Advanced JPEG aggregation complete: "
        f"{len(platform_labels)} profiles, {len(observations)} observations, "
        f"{exact} exact, {bounded} within one code value."
    )
    if args.emit_log_payload:
        emit_log_payload(args.output_dir)


if __name__ == "__main__":
    main()
