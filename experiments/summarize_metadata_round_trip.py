"""Aggregate JPEG metadata round-trip observations from CI."""

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


PLATFORM_MANIFEST_NAME = "jpeg_round_trip_codec_manifest.csv"
OBSERVATIONS_NAME = "jpeg_round_trip_observations.csv"
COMBINED_MANIFEST_NAME = "jpeg_round_trip_cross_platform_codec_manifest.csv"
COMBINED_OBSERVATIONS_NAME = "jpeg_round_trip_cross_platform_observations.csv"
CONTRACTS_NAME = "jpeg_round_trip_cross_platform_contracts.csv"
SUMMARY_NAME = "jpeg_round_trip_cross_platform_summary.csv"
FIGURE_NAME = "jpeg_metadata_round_trip_cross_platform.png"
ENCODERS = ("pillow", "opencv")
POLICIES = ("preserve", "strip", "normalize", "reject")
FIXTURE_COUNT = 21
MANIFEST_ROWS_PER_PLATFORM = 4
OBSERVATION_ROWS_PER_PLATFORM = 168
BEHAVIOR_FIELDS = (
    "source_strict_accept",
    "source_decode_success",
    "policy_action",
    "output_emitted",
    "output_strict_accept",
    "output_decode_success",
    "input_envelope_byte_exact",
    "supported_semantics_retained",
    "compressed_core_exact",
    "pixels_exact_to_reencode_control",
    "error_category",
)
LOG_PAYLOAD_NAMES = (
    COMBINED_MANIFEST_NAME,
    COMBINED_OBSERVATIONS_NAME,
    CONTRACTS_NAME,
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
    observations: Sequence[dict[str, str]],
    expected_platform_count: int,
) -> list[str]:
    """Validate matrix coverage and observation uniqueness."""
    platforms = sorted({row["platform_label"] for row in manifests})
    if len(platforms) != expected_platform_count:
        raise RuntimeError(
            f"Expected {expected_platform_count} platforms, found "
            f"{len(platforms)}"
        )
    if len(manifests) != expected_platform_count * MANIFEST_ROWS_PER_PLATFORM:
        raise RuntimeError("Unexpected cross-platform manifest row count")
    if (
        len(observations)
        != expected_platform_count * OBSERVATION_ROWS_PER_PLATFORM
    ):
        raise RuntimeError("Unexpected cross-platform observation row count")
    if len({row["fixture_id"] for row in observations}) != FIXTURE_COUNT:
        raise RuntimeError("Unexpected fixture coverage")
    keys = {
        (
            row["platform_label"],
            row["fixture_id"],
            row["encoder"],
            row["policy"],
        )
        for row in observations
    }
    if len(keys) != len(observations):
        raise RuntimeError("Duplicate cross-platform observation found")
    if {row["platform_label"] for row in observations} != set(platforms):
        raise RuntimeError("Manifest and observation platforms differ")
    return platforms


def categorical_rate(
    rows: Sequence[dict[str, str]], field: str, value: str = "1"
) -> str:
    """Return one fixed-precision categorical rate."""
    if not rows:
        return "nan"
    return f"{np.mean([row[field] == value for row in rows]):.6f}"


def build_contracts(
    observations: Sequence[dict[str, str]],
    platform_count: int,
) -> list[dict[str, str]]:
    """Summarize each fixture, encoder, and policy across platforms."""
    rows: list[dict[str, str]] = []
    fixture_ids = sorted({row["fixture_id"] for row in observations})
    for fixture_id in fixture_ids:
        for encoder in ENCODERS:
            for policy in POLICIES:
                group = [
                    row
                    for row in observations
                    if row["fixture_id"] == fixture_id
                    and row["encoder"] == encoder
                    and row["policy"] == policy
                ]
                if len(group) != platform_count:
                    raise RuntimeError(
                        "Incomplete fixture, encoder, and policy coverage"
                    )
                exemplar = group[0]
                emitted = [
                    row for row in group if row["output_emitted"] == "1"
                ]
                decoded = [
                    row
                    for row in emitted
                    if row["output_decode_success"] == "1"
                ]
                behavior_signatures = {
                    tuple(row[field] for field in BEHAVIOR_FIELDS)
                    for row in group
                }
                error_categories = sorted(
                    {
                        row["error_category"]
                        for row in group
                        if row["error_category"] != "none"
                    }
                )
                rows.append(
                    {
                        "fixture_id": fixture_id,
                        "fixture_family": exemplar["fixture_family"],
                        "mutation": exemplar["mutation"],
                        "encoder": encoder,
                        "policy": policy,
                        "platform_profiles": str(platform_count),
                        "source_decode_rate": categorical_rate(
                            group, "source_decode_success"
                        ),
                        "output_rate": categorical_rate(
                            group, "output_emitted"
                        ),
                        "strict_accept_rate_among_outputs": categorical_rate(
                            emitted, "output_strict_accept"
                        ),
                        "output_decode_rate_among_outputs": categorical_rate(
                            emitted, "output_decode_success"
                        ),
                        "byte_exact_envelope_rate_among_applicable": (
                            categorical_rate(
                                [
                                    row
                                    for row in emitted
                                    if row[
                                        "envelope_contract_applicable"
                                    ]
                                    == "1"
                                ],
                                "input_envelope_byte_exact",
                            )
                        ),
                        "semantic_retention_rate_among_applicable": (
                            categorical_rate(
                                [
                                    row
                                    for row in emitted
                                    if row[
                                        "semantic_contract_applicable"
                                    ]
                                    == "1"
                                ],
                                "supported_semantics_retained",
                            )
                        ),
                        "compressed_core_exact_rate": categorical_rate(
                            emitted, "compressed_core_exact"
                        ),
                        "pixel_exact_rate_among_decoded_outputs": (
                            categorical_rate(
                                decoded,
                                "pixels_exact_to_reencode_control",
                            )
                        ),
                        "unique_output_jpeg_hashes": str(
                            len(
                                {
                                    row["output_sha256"]
                                    for row in emitted
                                    if row["output_sha256"]
                                }
                            )
                        ),
                        "unique_output_pixel_hashes": str(
                            len(
                                {
                                    row["output_bgr_sha256"]
                                    for row in decoded
                                    if row["output_bgr_sha256"]
                                }
                            )
                        ),
                        "behavior_signature_count": str(
                            len(behavior_signatures)
                        ),
                        "error_categories": (
                            "|".join(error_categories)
                            if error_categories
                            else "none"
                        ),
                    }
                )
    expected = FIXTURE_COUNT * len(ENCODERS) * len(POLICIES)
    if len(rows) != expected:
        raise RuntimeError("Unexpected cross-platform contract row count")
    return rows


def build_summary(
    observations: Sequence[dict[str, str]],
    contracts: Sequence[dict[str, str]],
    platform_count: int,
) -> list[dict[str, str]]:
    """Summarize policy outcomes over all fixtures and profiles."""
    rows: list[dict[str, str]] = []
    for encoder in ENCODERS:
        for policy in POLICIES:
            group = [
                row
                for row in observations
                if row["encoder"] == encoder and row["policy"] == policy
            ]
            emitted = [
                row for row in group if row["output_emitted"] == "1"
            ]
            decoded = [
                row
                for row in emitted
                if row["output_decode_success"] == "1"
            ]
            envelope_rows = [
                row
                for row in emitted
                if row["envelope_contract_applicable"] == "1"
            ]
            semantic_rows = [
                row
                for row in emitted
                if row["semantic_contract_applicable"] == "1"
            ]
            contract_group = [
                row
                for row in contracts
                if row["encoder"] == encoder and row["policy"] == policy
            ]
            rows.append(
                {
                    "encoder": encoder,
                    "policy": policy,
                    "platform_profiles": str(platform_count),
                    "attempts": str(len(group)),
                    "outputs_emitted": str(len(emitted)),
                    "output_rate": categorical_rate(
                        group, "output_emitted"
                    ),
                    "strict_accept_rate_among_outputs": categorical_rate(
                        emitted, "output_strict_accept"
                    ),
                    "output_decode_rate_among_outputs": categorical_rate(
                        emitted, "output_decode_success"
                    ),
                    "byte_exact_envelope_rate": categorical_rate(
                        envelope_rows, "input_envelope_byte_exact"
                    ),
                    "supported_semantic_retention_rate": categorical_rate(
                        semantic_rows, "supported_semantics_retained"
                    ),
                    "compressed_core_exact_rate": categorical_rate(
                        emitted, "compressed_core_exact"
                    ),
                    "pixel_exact_rate_among_decoded_outputs": (
                        categorical_rate(
                            decoded, "pixels_exact_to_reencode_control"
                        )
                    ),
                    "stable_behavior_contracts": str(
                        sum(
                            row["behavior_signature_count"] == "1"
                            for row in contract_group
                        )
                    ),
                    "total_behavior_contracts": str(len(contract_group)),
                    "contracts_with_platform_pixel_variation": str(
                        sum(
                            int(row["unique_output_pixel_hashes"]) > 1
                            for row in contract_group
                        )
                    ),
                    "contracts_with_platform_jpeg_variation": str(
                        sum(
                            int(row["unique_output_jpeg_hashes"]) > 1
                            for row in contract_group
                        )
                    ),
                }
            )
    return rows


def plot_cross_platform(
    summary: Sequence[dict[str, str]], output_path: Path
) -> None:
    """Visualize cross-platform policy behavior and byte variability."""
    figure, axes = plt.subplots(
        1, 3, figsize=(15, 4.8), constrained_layout=True
    )
    positions = np.arange(len(POLICIES), dtype=np.float64)
    width = 0.36
    colors = {"pillow": "#4472C4", "opencv": "#ED7D31"}
    for encoder_index, encoder in enumerate(ENCODERS):
        group = [row for row in summary if row["encoder"] == encoder]
        offset = (encoder_index - 0.5) * width
        axes[0].bar(
            positions + offset,
            [float(row["output_rate"]) for row in group],
            width,
            label=encoder,
            color=colors[encoder],
            alpha=0.88,
        )
        axes[0].plot(
            positions + offset,
            [
                float(row["strict_accept_rate_among_outputs"])
                if row["strict_accept_rate_among_outputs"] != "nan"
                else 0.0
                for row in group
            ],
            "o",
            color="#222222",
            markersize=4,
        )
        axes[1].bar(
            positions + offset,
            [
                int(row["stable_behavior_contracts"])
                / int(row["total_behavior_contracts"])
                for row in group
            ],
            width,
            color=colors[encoder],
            alpha=0.88,
        )
        axes[2].bar(
            positions + offset,
            [
                int(row["contracts_with_platform_jpeg_variation"])
                for row in group
            ],
            width,
            color=colors[encoder],
            alpha=0.88,
        )
    axes[0].set_title("Emission bars; strict acceptance dots")
    axes[0].set_ylabel("Rate")
    axes[0].set_ylim(0, 1.08)
    axes[0].legend(title="Re-encoder")
    axes[1].set_title("Stable behavior contracts")
    axes[1].set_ylabel("Fraction of 21 fixtures")
    axes[1].set_ylim(0, 1.08)
    axes[2].set_title("Contracts with JPEG byte variation")
    axes[2].set_ylabel("Fixture contracts")
    for axis in axes:
        axis.set_xticks(positions, POLICIES, rotation=20)
        axis.grid(axis="y", alpha=0.25)
    figure.suptitle(
        "Metadata policy contracts across five codec-build profiles"
    )
    figure.savefig(
        output_path,
        dpi=160,
        metadata={"Software": "research-notes v0.14.0"},
    )
    plt.close(figure)


def emit_log_payload(output_dir: Path) -> None:
    """Emit compressed CSV results for retrieval from workflow logs."""
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
    print("V014_RESULTS_PAYLOAD_BEGIN")
    for index, chunk in enumerate(chunks, start=1):
        print(f"V014_RESULTS_PAYLOAD_{index:04d}={chunk}")
    print("V014_RESULTS_PAYLOAD_END")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Aggregate JPEG metadata round-trip policy contracts."
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
    """Collect platform artifacts and write aggregate policy reports."""
    args = parse_args()
    manifests = collect_rows(args.input_dir, PLATFORM_MANIFEST_NAME)
    observations = collect_rows(args.input_dir, OBSERVATIONS_NAME)
    platforms = validate_coverage(
        manifests, observations, args.expected_platform_count
    )
    manifests.sort(
        key=lambda row: (row["platform_label"], row["component"])
    )
    observations.sort(
        key=lambda row: (
            row["platform_label"],
            row["fixture_id"],
            row["encoder"],
            row["policy"],
        )
    )
    contracts = build_contracts(observations, len(platforms))
    summary = build_summary(
        observations, contracts, len(platforms)
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / COMBINED_MANIFEST_NAME, manifests)
    write_csv(args.output_dir / COMBINED_OBSERVATIONS_NAME, observations)
    write_csv(args.output_dir / CONTRACTS_NAME, contracts)
    write_csv(args.output_dir / SUMMARY_NAME, summary)
    plot_cross_platform(summary, args.output_dir / FIGURE_NAME)
    if args.emit_log_payload:
        emit_log_payload(args.output_dir)
    print(
        "Cross-platform JPEG metadata round-trip aggregation complete: "
        f"{len(platforms)} profiles, {len(observations)} observations, "
        f"{len(contracts)} contracts."
    )


if __name__ == "__main__":
    main()
