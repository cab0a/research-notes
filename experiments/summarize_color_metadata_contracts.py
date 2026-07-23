"""Aggregate JPEG metadata interpretation observations from CI artifacts."""

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


PLATFORM_MANIFEST_NAME = "jpeg_metadata_codec_manifest.csv"
RAW_OBSERVATIONS_NAME = "jpeg_metadata_raw_observations.csv"
POLICY_OBSERVATIONS_NAME = "jpeg_metadata_policy_observations.csv"
CONTROL_PAIRS_NAME = "jpeg_metadata_control_pairs.csv"
COMBINED_MANIFEST_NAME = "jpeg_metadata_cross_platform_codec_manifest.csv"
COMBINED_RAW_NAME = "jpeg_metadata_cross_platform_raw_observations.csv"
COMBINED_POLICY_NAME = "jpeg_metadata_cross_platform_policy_observations.csv"
COMBINED_CONTROL_NAME = "jpeg_metadata_cross_platform_control_pairs.csv"
SUMMARY_NAME = "jpeg_metadata_cross_platform_summary.csv"
FIGURE_NAME = "jpeg_metadata_cross_platform_interpretation.png"
DECODERS = ("opencv", "pillow", "ffmpeg")
FIXTURE_COUNT = 13
RAW_ROWS_PER_PLATFORM = 39
POLICY_ROWS_PER_PLATFORM = 44
CONTROL_ROWS_PER_PLATFORM = 31
MANIFEST_ROWS_PER_PLATFORM = 4
LOG_PAYLOAD_NAMES = (
    COMBINED_MANIFEST_NAME,
    COMBINED_RAW_NAME,
    COMBINED_POLICY_NAME,
    COMBINED_CONTROL_NAME,
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


def validate_coverage(
    manifests: Sequence[dict[str, str]],
    raw_rows: Sequence[dict[str, str]],
    policy_rows: Sequence[dict[str, str]],
    control_rows: Sequence[dict[str, str]],
    expected_platform_count: int,
) -> list[str]:
    """Validate matrix coverage, uniqueness, and array contracts."""
    platform_labels = sorted({row["platform_label"] for row in manifests})
    if len(platform_labels) != expected_platform_count:
        raise RuntimeError(
            f"Expected {expected_platform_count} platforms, found "
            f"{len(platform_labels)}"
        )
    expected_counts = (
        ("manifest", len(manifests), MANIFEST_ROWS_PER_PLATFORM),
        ("raw", len(raw_rows), RAW_ROWS_PER_PLATFORM),
        ("policy", len(policy_rows), POLICY_ROWS_PER_PLATFORM),
        ("control", len(control_rows), CONTROL_ROWS_PER_PLATFORM),
    )
    for name, observed, per_platform in expected_counts:
        if observed != expected_platform_count * per_platform:
            raise RuntimeError(f"Unexpected cross-platform {name} row count")
    if len({row["fixture_id"] for row in raw_rows}) != FIXTURE_COUNT:
        raise RuntimeError("Unexpected fixture coverage")
    if not all(
        row["shape_contract"] == "1" and row["dtype_contract"] == "1"
        for row in (*raw_rows, *policy_rows, *control_rows)
    ):
        raise RuntimeError("A cross-platform array interface contract failed")
    raw_keys = {
        (row["platform_label"], row["fixture_id"], row["decoder"])
        for row in raw_rows
    }
    policy_keys = {
        (row["platform_label"], row["fixture_id"], row["policy"])
        for row in policy_rows
    }
    control_keys = {
        (
            row["platform_label"],
            row["control_id"],
            row["reference_fixture"],
            row["candidate_fixture"],
            row["adapter"],
        )
        for row in control_rows
    }
    if len(raw_keys) != len(raw_rows):
        raise RuntimeError("Duplicate raw observation rows found")
    if len(policy_keys) != len(policy_rows):
        raise RuntimeError("Duplicate policy observation rows found")
    if len(control_keys) != len(control_rows):
        raise RuntimeError("Duplicate control comparison rows found")
    return platform_labels


def finite_values(rows: Sequence[dict[str, str]], field: str) -> list[float]:
    """Return numeric values while excluding explicit non-comparable rows."""
    return [float(row[field]) for row in rows if row[field] != "nan"]


def make_summary_row(
    *,
    report_family: str,
    group_id: str,
    fixture_family: str,
    fixture_id: str,
    adapter_or_policy: str,
    rows: Sequence[dict[str, str]],
    platform_count: int,
) -> dict[str, str]:
    """Summarize one fixed observation key across platform profiles."""
    means = finite_values(rows, "mean_absolute_error")
    maxima = finite_values(rows, "maximum_absolute_error")
    return {
        "report_family": report_family,
        "group_id": group_id,
        "fixture_family": fixture_family,
        "fixture_id": fixture_id,
        "adapter_or_policy": adapter_or_policy,
        "platform_profiles": str(platform_count),
        "observations": str(len(rows)),
        "shape_contract_rate": (
            f"{np.mean([int(row['shape_contract']) for row in rows]):.6f}"
        ),
        "dtype_contract_rate": (
            f"{np.mean([int(row['dtype_contract']) for row in rows]):.6f}"
        ),
        "exact_pixel_rate": (
            f"{np.mean([int(row['exact_pixels']) for row in rows]):.6f}"
        ),
        "unique_candidate_hashes": str(
            len({row["candidate_bgr_sha256"] for row in rows})
        ),
        "mean_absolute_error_min": (
            f"{min(means):.9f}" if means else "nan"
        ),
        "mean_absolute_error_max": (
            f"{max(means):.9f}" if means else "nan"
        ),
        "maximum_absolute_error_max": (
            str(int(max(maxima))) if maxima else "nan"
        ),
    }


def summarize_all(
    raw_rows: Sequence[dict[str, str]],
    policy_rows: Sequence[dict[str, str]],
    control_rows: Sequence[dict[str, str]],
    platform_labels: Sequence[str],
) -> list[dict[str, str]]:
    """Summarize every fixed raw, policy, and control key."""
    summary: list[dict[str, str]] = []
    raw_keys = sorted(
        {
            (row["fixture_family"], row["fixture_id"], row["decoder"])
            for row in raw_rows
        }
    )
    for family, fixture_id, decoder in raw_keys:
        group = [
            row
            for row in raw_rows
            if row["fixture_id"] == fixture_id
            and row["decoder"] == decoder
        ]
        summary.append(
            make_summary_row(
                report_family="raw_decoder",
                group_id=f"{fixture_id}:{decoder}",
                fixture_family=family,
                fixture_id=fixture_id,
                adapter_or_policy=decoder,
                rows=group,
                platform_count=len(platform_labels),
            )
        )
    policy_keys = sorted(
        {
            (row["fixture_family"], row["fixture_id"], row["policy"])
            for row in policy_rows
        }
    )
    for family, fixture_id, policy in policy_keys:
        group = [
            row
            for row in policy_rows
            if row["fixture_id"] == fixture_id and row["policy"] == policy
        ]
        summary.append(
            make_summary_row(
                report_family="interpretation_policy",
                group_id=f"{fixture_id}:{policy}",
                fixture_family=family,
                fixture_id=fixture_id,
                adapter_or_policy=policy,
                rows=group,
                platform_count=len(platform_labels),
            )
        )
    control_keys = sorted(
        {
            (
                row["control_id"],
                row["reference_fixture"],
                row["candidate_fixture"],
                row["adapter"],
            )
            for row in control_rows
        }
    )
    for control_id, reference_fixture, candidate_fixture, adapter in control_keys:
        group = [
            row
            for row in control_rows
            if row["control_id"] == control_id
            and row["reference_fixture"] == reference_fixture
            and row["candidate_fixture"] == candidate_fixture
            and row["adapter"] == adapter
        ]
        summary.append(
            make_summary_row(
                report_family="control_pair",
                group_id=(
                    f"{control_id}:{reference_fixture}:{candidate_fixture}:"
                    f"{adapter}"
                ),
                fixture_family=control_id,
                fixture_id=f"{reference_fixture}->{candidate_fixture}",
                adapter_or_policy=adapter,
                rows=group,
                platform_count=len(platform_labels),
            )
        )
    if len(summary) != 114:
        raise RuntimeError("Unexpected cross-platform summary row count")
    return summary


def plot_cross_platform(
    raw_rows: Sequence[dict[str, str]],
    policy_rows: Sequence[dict[str, str]],
    control_rows: Sequence[dict[str, str]],
    output_path: Path,
) -> None:
    """Visualize response ranges and cross-platform decoded contracts."""
    figure, axes = plt.subplots(2, 2, figsize=(13, 9), constrained_layout=True)

    gamma_ids = ("rgb_icc_gamma_1_0", "rgb_icc_gamma_2_2")
    gamma_labels = ("gamma 1.0", "gamma 2.2")
    gamma_groups = [
        [
            float(row["mean_absolute_error"])
            for row in policy_rows
            if row["fixture_id"] == fixture_id
            and row["policy"] == "icc_to_srgb_relative"
        ]
        for fixture_id in gamma_ids
    ]
    gamma_means = [float(np.mean(values)) for values in gamma_groups]
    gamma_ranges = np.array(
        [
            [mean - min(values) for mean, values in zip(gamma_means, gamma_groups)],
            [max(values) - mean for mean, values in zip(gamma_means, gamma_groups)],
        ]
    )
    axes[0, 0].bar(
        gamma_labels,
        gamma_means,
        yerr=gamma_ranges,
        capsize=5,
        color=("#3569a8", "#78a9dc"),
    )
    axes[0, 0].set_title("ICC-managed response across platforms")
    axes[0, 0].set_ylabel("Mean absolute code-value difference")

    orientation_policies = (
        "opencv_ignore_orientation",
        "opencv_apply_orientation",
        "pillow_ignore_orientation",
        "pillow_exif_transpose",
    )
    orientation_labels = (
        "OpenCV: ignore",
        "OpenCV: apply",
        "Pillow: ignore",
        "Pillow: transpose",
    )
    exact_rates = [
        np.mean(
            [
                int(row["exact_pixels"])
                for row in policy_rows
                if row["policy"] == policy
            ]
        )
        for policy in orientation_policies
    ]
    axes[0, 1].barh(
        range(len(orientation_policies)), exact_rates, color="#4c956c"
    )
    axes[0, 1].set_yticks(
        range(len(orientation_labels)), orientation_labels
    )
    axes[0, 1].set_xlim(0, 1.05)
    axes[0, 1].set_title("EXIF orientation policy exactness")
    axes[0, 1].set_xlabel("Exact contract rate")

    family_names = ("icc_profile", "exif_orientation")
    unique_counts = np.array(
        [
            [
                max(
                    len(
                        {
                            row["candidate_bgr_sha256"]
                            for row in raw_rows
                            if row["fixture_family"] == family
                            and row["fixture_id"] == fixture_id
                            and row["decoder"] == decoder
                        }
                    )
                    for fixture_id in {
                        row["fixture_id"]
                        for row in raw_rows
                        if row["fixture_family"] == family
                    }
                )
                for decoder in DECODERS
            ]
            for family in family_names
        ],
        dtype=np.float64,
    )
    image = axes[1, 0].imshow(
        unique_counts, aspect="auto", cmap="Blues", vmin=1
    )
    axes[1, 0].set_xticks(range(3), DECODERS)
    axes[1, 0].set_yticks(range(2), ("ICC tags", "EXIF orientation"))
    axes[1, 0].set_title("Maximum hashes per fixed fixture across platforms")
    for row_index in range(2):
        for column_index in range(3):
            axes[1, 0].text(
                column_index,
                row_index,
                f"{unique_counts[row_index, column_index]:.0f}",
                ha="center",
                va="center",
            )
    figure.colorbar(image, ax=axes[1, 0], shrink=0.75)

    pair_groups = {
        decoder: [
            row
            for row in control_rows
            if row["control_id"] == "cmyk_ycck_rendered_equivalence"
            and row["adapter"] == decoder
        ]
        for decoder in DECODERS
    }
    pair_means = [
        np.mean(
            [float(row["mean_absolute_error"]) for row in pair_groups[decoder]]
        )
        for decoder in DECODERS
    ]
    pair_maxima = [
        max(
            int(row["maximum_absolute_error"])
            for row in pair_groups[decoder]
        )
        for decoder in DECODERS
    ]
    axes[1, 1].bar(range(3), pair_means, color="#d88c46")
    for index, maximum in enumerate(pair_maxima):
        axes[1, 1].text(
            index,
            pair_means[index],
            f"max {maximum}",
            ha="center",
            va="bottom",
        )
    axes[1, 1].set_xticks(range(3), DECODERS)
    axes[1, 1].set_title("CMYK versus YCCK rendered output")
    axes[1, 1].set_ylabel("Mean absolute code-value difference")

    figure.suptitle(
        "Color metadata interpretation across platforms and codec builds"
    )
    figure.savefig(output_path, dpi=160)
    plt.close(figure)


def emit_log_payload(output_dir: Path) -> None:
    """Emit compressed result files for retrieval from workflow logs."""
    files = {
        name: (output_dir / name).read_text(encoding="utf-8")
        for name in LOG_PAYLOAD_NAMES
    }
    payload = {
        "files": files,
        "sha256": {
            name: hashlib.sha256(content.encode("utf-8")).hexdigest()
            for name, content in files.items()
        },
    }
    encoded = base64.b64encode(
        gzip.compress(
            json.dumps(payload, sort_keys=True).encode("utf-8"),
            mtime=0,
        )
    ).decode("ascii")
    chunk_size = 4000
    chunks = [
        encoded[start : start + chunk_size]
        for start in range(0, len(encoded), chunk_size)
    ]
    print("V012_RESULTS_PAYLOAD_BEGIN")
    for index, chunk in enumerate(chunks, start=1):
        print(f"V012_RESULTS_PAYLOAD_{index:04d}={chunk}")
    print("V012_RESULTS_PAYLOAD_END")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Aggregate cross-platform JPEG metadata contracts."
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
        default=Path("results"),
        help="Directory for combined CSV and PNG outputs.",
    )
    parser.add_argument(
        "--expected-platform-count",
        type=int,
        default=5,
        help="Required number of distinct platform labels.",
    )
    parser.add_argument(
        "--emit-log-payload",
        action="store_true",
        help="Print compressed CSV outputs for retrieval from CI logs.",
    )
    return parser.parse_args()


def main() -> None:
    """Collect platform artifacts, validate them, and write aggregates."""
    args = parse_args()
    manifests = collect_rows(args.input_dir, PLATFORM_MANIFEST_NAME)
    raw_rows = collect_rows(args.input_dir, RAW_OBSERVATIONS_NAME)
    policy_rows = collect_rows(args.input_dir, POLICY_OBSERVATIONS_NAME)
    control_rows = collect_rows(args.input_dir, CONTROL_PAIRS_NAME)
    platform_labels = validate_coverage(
        manifests,
        raw_rows,
        policy_rows,
        control_rows,
        args.expected_platform_count,
    )
    manifests.sort(key=lambda row: (row["platform_label"], row["component"]))
    raw_rows.sort(
        key=lambda row: (
            row["platform_label"],
            row["fixture_id"],
            row["decoder"],
        )
    )
    policy_rows.sort(
        key=lambda row: (
            row["platform_label"],
            row["fixture_id"],
            row["policy"],
        )
    )
    control_rows.sort(
        key=lambda row: (
            row["platform_label"],
            row["control_id"],
            row["reference_fixture"],
            row["candidate_fixture"],
            row["adapter"],
        )
    )
    summary = summarize_all(
        raw_rows, policy_rows, control_rows, platform_labels
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / COMBINED_MANIFEST_NAME, manifests)
    write_csv(args.output_dir / COMBINED_RAW_NAME, raw_rows)
    write_csv(args.output_dir / COMBINED_POLICY_NAME, policy_rows)
    write_csv(args.output_dir / COMBINED_CONTROL_NAME, control_rows)
    write_csv(args.output_dir / SUMMARY_NAME, summary)
    plot_cross_platform(
        raw_rows,
        policy_rows,
        control_rows,
        args.output_dir / FIGURE_NAME,
    )
    print(
        "Cross-platform JPEG metadata aggregation complete: "
        f"{len(platform_labels)} platform profiles, {len(raw_rows)} raw "
        f"observations, {len(policy_rows)} policy observations, and "
        f"{len(control_rows)} control pairs."
    )
    if args.emit_log_payload:
        emit_log_payload(args.output_dir)


if __name__ == "__main__":
    main()
