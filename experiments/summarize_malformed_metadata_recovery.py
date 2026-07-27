"""Aggregate malformed JPEG metadata recovery observations from CI."""

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


PLATFORM_MANIFEST_NAME = "jpeg_recovery_codec_manifest.csv"
AUDIT_NAME = "jpeg_recovery_audit.csv"
OBSERVATIONS_NAME = "jpeg_recovery_decoder_observations.csv"
COMBINED_MANIFEST_NAME = "jpeg_recovery_cross_platform_codec_manifest.csv"
COMBINED_AUDIT_NAME = "jpeg_recovery_cross_platform_audit.csv"
COMBINED_OBSERVATIONS_NAME = (
    "jpeg_recovery_cross_platform_decoder_observations.csv"
)
SUMMARY_NAME = "jpeg_recovery_cross_platform_summary.csv"
FIGURE_NAME = "jpeg_recovery_cross_platform_contracts.png"
DECODERS = ("opencv", "pillow", "ffmpeg")
FIXTURE_COUNT = 21
MANIFEST_ROWS_PER_PLATFORM = 4
AUDIT_ROWS_PER_PLATFORM = 21
OBSERVATION_ROWS_PER_PLATFORM = 63
LOG_PAYLOAD_NAMES = (
    COMBINED_MANIFEST_NAME,
    COMBINED_AUDIT_NAME,
    COMBINED_OBSERVATIONS_NAME,
    SUMMARY_NAME,
)


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read one UTF-8 CSV report."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Sequence[dict[str, str]]) -> None:
    """Write deterministic UTF-8 CSV rows."""
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
    audits: Sequence[dict[str, str]],
    observations: Sequence[dict[str, str]],
    expected_platform_count: int,
) -> list[str]:
    """Validate matrix coverage, uniqueness, and strict audit contracts."""
    platform_labels = sorted(
        {row["platform_label"] for row in manifests}
    )
    if len(platform_labels) != expected_platform_count:
        raise RuntimeError(
            f"Expected {expected_platform_count} platforms, found "
            f"{len(platform_labels)}"
        )
    expected_counts = (
        (
            "manifest",
            len(manifests),
            MANIFEST_ROWS_PER_PLATFORM,
        ),
        ("audit", len(audits), AUDIT_ROWS_PER_PLATFORM),
        (
            "observation",
            len(observations),
            OBSERVATION_ROWS_PER_PLATFORM,
        ),
    )
    for name, observed, per_platform in expected_counts:
        if observed != expected_platform_count * per_platform:
            raise RuntimeError(
                f"Unexpected cross-platform {name} row count"
            )
    if len({row["fixture_id"] for row in audits}) != FIXTURE_COUNT:
        raise RuntimeError("Unexpected fixture coverage")
    audit_keys = {
        (row["platform_label"], row["fixture_id"]) for row in audits
    }
    observation_keys = {
        (row["platform_label"], row["fixture_id"], row["decoder"])
        for row in observations
    }
    if len(audit_keys) != len(audits):
        raise RuntimeError("Duplicate strict audit rows found")
    if len(observation_keys) != len(observations):
        raise RuntimeError("Duplicate decoder observation rows found")
    if not all(row["expected_contract_met"] == "1" for row in audits):
        raise RuntimeError("A strict audit expectation failed")
    if any(
        row["decode_success"] == "1"
        and (
            row["shape_contract"] != "1"
            or row["dtype_contract"] != "1"
        )
        for row in observations
    ):
        raise RuntimeError("A successful decoder array contract failed")
    return platform_labels


def finite_values(
    rows: Sequence[dict[str, str]], field: str
) -> list[float]:
    """Return finite numeric fields from successful observations."""
    return [float(row[field]) for row in rows if row[field] != "nan"]


def make_summary_row(
    *,
    report_family: str,
    fixture_id: str,
    fixture_family: str,
    mutation: str,
    adapter: str,
    rows: Sequence[dict[str, str]],
    strict_accept_rate: float,
    platform_count: int,
) -> dict[str, str]:
    """Summarize one fixed fixture and adapter group."""
    successful = [
        row for row in rows if row["decode_success"] == "1"
    ]
    means = finite_values(successful, "mean_absolute_error")
    maxima = finite_values(successful, "maximum_absolute_error")
    exact_success_count = sum(
        int(row["exact_to_decoder_control"]) for row in successful
    )
    output_hashes = {
        row["output_bgr_sha256"]
        for row in successful
        if row["output_bgr_sha256"]
    }
    diagnostics = {
        row["diagnostic_sha256"]
        for row in rows
        if row["diagnostic_sha256"]
    }
    errors = sorted(
        {
            row["error_category"]
            for row in rows
            if row["error_category"] != "none"
        }
    )
    return {
        "report_family": report_family,
        "fixture_id": fixture_id,
        "fixture_family": fixture_family,
        "mutation": mutation,
        "adapter": adapter,
        "platform_profiles": str(platform_count),
        "observations": str(len(rows)),
        "strict_accept_rate": f"{strict_accept_rate:.6f}",
        "decode_success_rate": (
            f"{np.mean([int(row['decode_success']) for row in rows]):.6f}"
        ),
        "shape_contract_rate": (
            f"{np.mean([int(row['shape_contract']) for row in rows]):.6f}"
        ),
        "dtype_contract_rate": (
            f"{np.mean([int(row['dtype_contract']) for row in rows]):.6f}"
        ),
        "exact_success_rate": f"{exact_success_count / len(rows):.6f}",
        "exact_rate_among_successes": (
            f"{exact_success_count / len(successful):.6f}"
            if successful
            else "nan"
        ),
        "unique_output_hashes": str(len(output_hashes)),
        "error_categories": "|".join(errors) if errors else "none",
        "unique_diagnostic_hashes": str(len(diagnostics)),
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
    audits: Sequence[dict[str, str]],
    observations: Sequence[dict[str, str]],
    platform_labels: Sequence[str],
) -> list[dict[str, str]]:
    """Summarize every fixed fixture overall and per decoder."""
    summary: list[dict[str, str]] = []
    fixture_ids = sorted({row["fixture_id"] for row in audits})
    for fixture_id in fixture_ids:
        audit_group = [
            row for row in audits if row["fixture_id"] == fixture_id
        ]
        observation_group = [
            row
            for row in observations
            if row["fixture_id"] == fixture_id
        ]
        strict_rate = float(
            np.mean(
                [int(row["strict_accept"]) for row in audit_group]
            )
        )
        exemplar = audit_group[0]
        summary.append(
            make_summary_row(
                report_family="fixture_overall",
                fixture_id=fixture_id,
                fixture_family=exemplar["fixture_family"],
                mutation=exemplar["mutation"],
                adapter="all_decoders",
                rows=observation_group,
                strict_accept_rate=strict_rate,
                platform_count=len(platform_labels),
            )
        )
        for decoder in DECODERS:
            decoder_group = [
                row
                for row in observation_group
                if row["decoder"] == decoder
            ]
            summary.append(
                make_summary_row(
                    report_family="fixture_decoder",
                    fixture_id=fixture_id,
                    fixture_family=exemplar["fixture_family"],
                    mutation=exemplar["mutation"],
                    adapter=decoder,
                    rows=decoder_group,
                    strict_accept_rate=strict_rate,
                    platform_count=len(platform_labels),
                )
            )
    if len(summary) != FIXTURE_COUNT * 4:
        raise RuntimeError("Unexpected cross-platform summary row count")
    return summary


def plot_cross_platform(
    audits: Sequence[dict[str, str]],
    observations: Sequence[dict[str, str]],
    output_path: Path,
) -> None:
    """Visualize cross-platform acceptance, exactness, and hash counts."""
    fixture_ids = sorted({row["fixture_id"] for row in audits})
    labels = [
        name.replace("_orientation_", "_ori_")
        .replace("_sequence", "_seq")
        .replace("_conflicting", "_conflict")
        .replace("_after_eoi", "_post_eoi")
        for name in fixture_ids
    ]
    acceptance = np.zeros((len(fixture_ids), 4), dtype=np.float64)
    exactness = np.zeros((len(fixture_ids), 3), dtype=np.float64)
    hash_counts = np.zeros((len(fixture_ids), 3), dtype=np.float64)
    for row_index, fixture_id in enumerate(fixture_ids):
        audit_group = [
            row for row in audits if row["fixture_id"] == fixture_id
        ]
        acceptance[row_index, 0] = np.mean(
            [int(row["strict_accept"]) for row in audit_group]
        )
        for column_index, decoder in enumerate(DECODERS):
            group = [
                row
                for row in observations
                if row["fixture_id"] == fixture_id
                and row["decoder"] == decoder
            ]
            acceptance[row_index, column_index + 1] = np.mean(
                [int(row["decode_success"]) for row in group]
            )
            exactness[row_index, column_index] = np.mean(
                [int(row["exact_to_decoder_control"]) for row in group]
            )
            hash_counts[row_index, column_index] = len(
                {
                    row["output_bgr_sha256"]
                    for row in group
                    if row["output_bgr_sha256"]
                }
            )

    figure, axes = plt.subplots(
        1, 3, figsize=(17, 11), constrained_layout=True
    )
    image = axes[0].imshow(
        acceptance, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1
    )
    axes[0].set_xticks(
        range(4), ("strict", "OpenCV", "Pillow", "FFmpeg"), rotation=30
    )
    axes[0].set_yticks(range(len(labels)), labels, fontsize=8)
    axes[0].set_title("Acceptance rate across five profiles")
    for row_index in range(len(labels)):
        for column_index in range(4):
            axes[0].text(
                column_index,
                row_index,
                f"{acceptance[row_index, column_index]:.1f}",
                ha="center",
                va="center",
                fontsize=7,
            )
    figure.colorbar(image, ax=axes[0], shrink=0.65)

    image = axes[1].imshow(
        exactness, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1
    )
    axes[1].set_xticks(range(3), DECODERS, rotation=30)
    axes[1].set_yticks(range(len(labels)), labels, fontsize=8)
    axes[1].set_title("Pixel-exact success rate")
    for row_index in range(len(labels)):
        for column_index in range(3):
            axes[1].text(
                column_index,
                row_index,
                f"{exactness[row_index, column_index]:.1f}",
                ha="center",
                va="center",
                fontsize=7,
            )
    figure.colorbar(image, ax=axes[1], shrink=0.65)

    image = axes[2].imshow(
        hash_counts, aspect="auto", cmap="Blues", vmin=0
    )
    axes[2].set_xticks(range(3), DECODERS, rotation=30)
    axes[2].set_yticks(range(len(labels)), labels, fontsize=8)
    axes[2].set_title("Unique successful output hashes")
    for row_index in range(len(labels)):
        for column_index in range(3):
            axes[2].text(
                column_index,
                row_index,
                f"{hash_counts[row_index, column_index]:.0f}",
                ha="center",
                va="center",
                fontsize=7,
            )
    figure.colorbar(image, ax=axes[2], shrink=0.65)
    figure.suptitle(
        "Malformed JPEG metadata recovery across recorded codec builds"
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
    chunks = [
        encoded[start : start + 4000]
        for start in range(0, len(encoded), 4000)
    ]
    print("V013_RESULTS_PAYLOAD_BEGIN")
    for index, chunk in enumerate(chunks, start=1):
        print(f"V013_RESULTS_PAYLOAD_{index:04d}={chunk}")
    print("V013_RESULTS_PAYLOAD_END")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Aggregate malformed JPEG metadata recovery contracts."
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
    audits = collect_rows(args.input_dir, AUDIT_NAME)
    observations = collect_rows(args.input_dir, OBSERVATIONS_NAME)
    platform_labels = validate_coverage(
        manifests,
        audits,
        observations,
        args.expected_platform_count,
    )
    manifests.sort(
        key=lambda row: (row["platform_label"], row["component"])
    )
    audits.sort(
        key=lambda row: (row["platform_label"], row["fixture_id"])
    )
    observations.sort(
        key=lambda row: (
            row["platform_label"],
            row["fixture_id"],
            row["decoder"],
        )
    )
    summary = summarize_all(audits, observations, platform_labels)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / COMBINED_MANIFEST_NAME, manifests)
    write_csv(args.output_dir / COMBINED_AUDIT_NAME, audits)
    write_csv(
        args.output_dir / COMBINED_OBSERVATIONS_NAME, observations
    )
    write_csv(args.output_dir / SUMMARY_NAME, summary)
    plot_cross_platform(
        audits, observations, args.output_dir / FIGURE_NAME
    )
    print(
        "Cross-platform malformed metadata aggregation complete: "
        f"{len(platform_labels)} profiles, {len(audits)} audits, and "
        f"{len(observations)} decoder observations."
    )
    if args.emit_log_payload:
        emit_log_payload(args.output_dir)


if __name__ == "__main__":
    main()
