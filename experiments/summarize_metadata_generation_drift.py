"""Aggregate multi-generation JPEG metadata policy observations from CI."""

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


PLATFORM_MANIFEST_NAME = "jpeg_metadata_generation_codec_manifest.csv"
OBSERVATIONS_NAME = "jpeg_metadata_generation_observations.csv"
COMBINED_MANIFEST_NAME = (
    "jpeg_metadata_generation_cross_platform_codec_manifest.csv"
)
COMBINED_OBSERVATIONS_NAME = (
    "jpeg_metadata_generation_cross_platform_observations.csv"
)
CONTRACTS_NAME = "jpeg_metadata_generation_cross_platform_contracts.csv"
SUMMARY_NAME = "jpeg_metadata_generation_cross_platform_summary.csv"
FIGURE_NAME = "jpeg_metadata_generation_cross_platform.png"
ENCODERS = ("pillow", "opencv")
SEQUENCES = (
    "preserve_repeat",
    "strip_repeat",
    "normalize_repeat",
    "preserve_then_normalize",
    "normalize_then_strip",
    "strip_then_preserve",
)
GENERATIONS = tuple(range(11))
CHECKPOINTS = (0, 1, 2, 5, 10)
FIXTURE_COUNT = 5
MANIFEST_ROWS_PER_PLATFORM = 4
OBSERVATION_ROWS_PER_PLATFORM = 660
BEHAVIOR_FIELDS = (
    "policy",
    "policy_action",
    "source_strict_accept",
    "output_strict_accept",
    "application_segment_count",
    "application_metadata_bytes",
    "metadata_changed_from_previous",
    "original_envelope_byte_exact",
    "supported_semantics_retained",
    "jpeg_changed_from_previous",
    "pixels_exact_to_previous",
    "pixels_exact_to_generation_zero",
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
        raise RuntimeError("Unexpected generation fixture coverage")
    keys = {
        (
            row["platform_label"],
            row["fixture_id"],
            row["encoder"],
            row["sequence_id"],
            row["generation"],
        )
        for row in observations
    }
    if len(keys) != len(observations):
        raise RuntimeError("Duplicate cross-platform generation observation")
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


def numeric_mean(rows: Sequence[dict[str, str]], field: str) -> str:
    """Return one fixed-precision mean over numeric string fields."""
    if not rows:
        return "nan"
    return f"{np.mean([float(row[field]) for row in rows]):.9f}"


def build_contracts(
    observations: Sequence[dict[str, str]],
    platform_count: int,
) -> list[dict[str, str]]:
    """Summarize each temporal observation key across platforms."""
    rows: list[dict[str, str]] = []
    fixture_ids = sorted({row["fixture_id"] for row in observations})
    for fixture_id in fixture_ids:
        for encoder in ENCODERS:
            for sequence_id in SEQUENCES:
                for generation in GENERATIONS:
                    group = [
                        row
                        for row in observations
                        if row["fixture_id"] == fixture_id
                        and row["encoder"] == encoder
                        and row["sequence_id"] == sequence_id
                        and int(row["generation"]) == generation
                    ]
                    if len(group) != platform_count:
                        raise RuntimeError(
                            "Incomplete temporal contract coverage"
                        )
                    exemplar = group[0]
                    behavior_signatures = {
                        tuple(row[field] for field in BEHAVIOR_FIELDS)
                        for row in group
                    }
                    generation_errors = [
                        float(
                            row["mean_absolute_error_to_generation_zero"]
                        )
                        for row in group
                    ]
                    rows.append(
                        {
                            "fixture_id": fixture_id,
                            "fixture_family": exemplar["fixture_family"],
                            "encoder": encoder,
                            "sequence_id": sequence_id,
                            "generation": str(generation),
                            "checkpoint": exemplar["checkpoint"],
                            "platform_profiles": str(platform_count),
                            "behavior_signature_count": str(
                                len(behavior_signatures)
                            ),
                            "unique_metadata_state_hashes": str(
                                len(
                                    {
                                        row["metadata_state_sha256"]
                                        for row in group
                                    }
                                )
                            ),
                            "unique_compressed_core_hashes": str(
                                len(
                                    {
                                        row["compressed_core_sha256"]
                                        for row in group
                                    }
                                )
                            ),
                            "unique_jpeg_hashes": str(
                                len({row["jpeg_sha256"] for row in group})
                            ),
                            "unique_pixel_hashes": str(
                                len(
                                    {
                                        row["output_bgr_sha256"]
                                        for row in group
                                    }
                                )
                            ),
                            "strict_accept_rate": categorical_rate(
                                group, "output_strict_accept"
                            ),
                            "original_envelope_exact_rate": (
                                categorical_rate(
                                    [
                                        row
                                        for row in group
                                        if row[
                                            "original_envelope_contract_applicable"
                                        ]
                                        == "1"
                                    ],
                                    "original_envelope_byte_exact",
                                )
                            ),
                            "supported_semantics_retained_rate": (
                                categorical_rate(
                                    [
                                        row
                                        for row in group
                                        if row[
                                            "semantic_contract_applicable"
                                        ]
                                        == "1"
                                    ],
                                    "supported_semantics_retained",
                                )
                            ),
                            "mean_absolute_error_to_generation_zero_min": (
                                f"{min(generation_errors):.9f}"
                            ),
                            "mean_absolute_error_to_generation_zero_max": (
                                f"{max(generation_errors):.9f}"
                            ),
                        }
                    )
    expected_count = (
        FIXTURE_COUNT
        * len(ENCODERS)
        * len(SEQUENCES)
        * len(GENERATIONS)
    )
    if len(rows) != expected_count:
        raise RuntimeError("Unexpected temporal contract row count")
    return rows


def build_summary(
    observations: Sequence[dict[str, str]],
    contracts: Sequence[dict[str, str]],
    platform_count: int,
) -> list[dict[str, str]]:
    """Summarize temporal contracts by encoder, sequence, and generation."""
    rows: list[dict[str, str]] = []
    for encoder in ENCODERS:
        for sequence_id in SEQUENCES:
            for generation in GENERATIONS:
                group = [
                    row
                    for row in observations
                    if row["encoder"] == encoder
                    and row["sequence_id"] == sequence_id
                    and int(row["generation"]) == generation
                ]
                contract_group = [
                    row
                    for row in contracts
                    if row["encoder"] == encoder
                    and row["sequence_id"] == sequence_id
                    and int(row["generation"]) == generation
                ]
                envelope_rows = [
                    row
                    for row in group
                    if row["original_envelope_contract_applicable"] == "1"
                ]
                semantic_rows = [
                    row
                    for row in group
                    if row["semantic_contract_applicable"] == "1"
                ]
                rows.append(
                    {
                        "encoder": encoder,
                        "sequence_id": sequence_id,
                        "generation": str(generation),
                        "checkpoint": str(int(generation in CHECKPOINTS)),
                        "platform_profiles": str(platform_count),
                        "observations": str(len(group)),
                        "strict_accept_rate": categorical_rate(
                            group, "output_strict_accept"
                        ),
                        "original_envelope_exact_rate": categorical_rate(
                            envelope_rows, "original_envelope_byte_exact"
                        ),
                        "supported_semantics_retained_rate": categorical_rate(
                            semantic_rows, "supported_semantics_retained"
                        ),
                        "mean_absolute_error_to_generation_zero": (
                            numeric_mean(
                                group,
                                "mean_absolute_error_to_generation_zero",
                            )
                        ),
                        "stable_behavior_contracts": str(
                            sum(
                                row["behavior_signature_count"] == "1"
                                for row in contract_group
                            )
                        ),
                        "metadata_hash_stable_contracts": str(
                            sum(
                                row["unique_metadata_state_hashes"] == "1"
                                for row in contract_group
                            )
                        ),
                        "compressed_core_stable_contracts": str(
                            sum(
                                row["unique_compressed_core_hashes"] == "1"
                                for row in contract_group
                            )
                        ),
                        "jpeg_hash_stable_contracts": str(
                            sum(
                                row["unique_jpeg_hashes"] == "1"
                                for row in contract_group
                            )
                        ),
                        "pixel_hash_stable_contracts": str(
                            sum(
                                row["unique_pixel_hashes"] == "1"
                                for row in contract_group
                            )
                        ),
                        "total_contracts": str(len(contract_group)),
                    }
                )
    return rows


def plot_cross_platform(
    summary: Sequence[dict[str, str]], output_path: Path
) -> None:
    """Visualize behavior, metadata, and pixel stability across profiles."""
    figure, axes = plt.subplots(
        1, 3, figsize=(16, 4.9), constrained_layout=True
    )
    colors = {
        "preserve_repeat": "#4472C4",
        "strip_repeat": "#A5A5A5",
        "normalize_repeat": "#70AD47",
        "preserve_then_normalize": "#5B9BD5",
        "normalize_then_strip": "#FFC000",
        "strip_then_preserve": "#ED7D31",
    }
    fields = (
        "stable_behavior_contracts",
        "metadata_hash_stable_contracts",
        "pixel_hash_stable_contracts",
    )
    titles = (
        "Stable categorical behavior",
        "Stable metadata-state hashes",
        "Stable decoded-pixel hashes",
    )
    generations = np.arange(11)
    for axis, field, title in zip(axes, fields, titles):
        for sequence_id in SEQUENCES:
            values = []
            for generation in generations:
                generation_rows = [
                    row
                    for row in summary
                    if row["sequence_id"] == sequence_id
                    and int(row["generation"]) == generation
                ]
                values.append(
                    float(
                        np.mean(
                            [
                                int(row[field]) / int(row["total_contracts"])
                                for row in generation_rows
                            ]
                        )
                    )
                )
            axis.plot(
                generations,
                values,
                marker="o",
                markersize=3,
                color=colors[sequence_id],
                label=sequence_id,
            )
        axis.set_title(title)
        axis.set_ylim(-0.04, 1.04)
        axis.set_xticks(CHECKPOINTS)
        axis.grid(alpha=0.25)
    axes[0].set_ylabel("Fraction of fixture contracts")
    axes[0].legend(fontsize=7, loc="lower right", ncol=2)
    figure.supxlabel("JPEG generation")
    figure.suptitle(
        "Metadata generation contracts across five codec-build profiles"
    )
    figure.savefig(
        output_path,
        dpi=160,
        metadata={"Software": "research-notes v0.15.0"},
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
    print("V015_RESULTS_PAYLOAD_BEGIN")
    for index, chunk in enumerate(chunks, start=1):
        print(f"V015_RESULTS_PAYLOAD_{index:04d}={chunk}")
    print("V015_RESULTS_PAYLOAD_END")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Aggregate multi-generation metadata policy contracts."
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
    """Collect platform artifacts and write aggregate temporal reports."""
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
            row["sequence_id"],
            int(row["generation"]),
        )
    )
    contracts = build_contracts(observations, len(platforms))
    summary = build_summary(observations, contracts, len(platforms))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / COMBINED_MANIFEST_NAME, manifests)
    write_csv(args.output_dir / COMBINED_OBSERVATIONS_NAME, observations)
    write_csv(args.output_dir / CONTRACTS_NAME, contracts)
    write_csv(args.output_dir / SUMMARY_NAME, summary)
    plot_cross_platform(summary, args.output_dir / FIGURE_NAME)
    if args.emit_log_payload:
        emit_log_payload(args.output_dir)
    print(
        "Cross-platform metadata generation aggregation complete: "
        f"{len(platforms)} profiles, {len(observations)} observations, "
        f"{len(contracts)} contracts."
    )


if __name__ == "__main__":
    main()
