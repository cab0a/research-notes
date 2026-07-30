"""Aggregate cross-platform field-level metadata retention contracts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


MANIFEST_INPUT = "jpeg_field_provenance_codec_manifest.csv"
DECISIONS_INPUT = "jpeg_field_provenance_decisions.csv"
OBSERVATIONS_INPUT = "jpeg_selective_retention_observations.csv"

MANIFEST_OUTPUT = "jpeg_field_provenance_cross_platform_codec_manifest.csv"
DECISIONS_OUTPUT = "jpeg_field_provenance_cross_platform_decisions.csv"
OBSERVATIONS_OUTPUT = (
    "jpeg_selective_retention_cross_platform_observations.csv"
)
CONTRACTS_OUTPUT = "jpeg_selective_retention_cross_platform_contracts.csv"
SUMMARY_OUTPUT = "jpeg_selective_retention_cross_platform_summary.csv"
FIGURE_OUTPUT = "jpeg_selective_retention_cross_platform.png"

CONTRACT_FIELDS = (
    "fixture_id",
    "encoder",
    "policy",
    "platform_count",
    "behavior_signature_count",
    "decision_signature_count",
    "metadata_state_hash_count",
    "complete_jpeg_hash_count",
    "decoded_pixel_hash_count",
    "strict_accept_count",
    "metadata_core_exact_count",
    "pixel_exact_count",
    "all_contracts_stable",
)

SUMMARY_FIELDS = (
    "encoder",
    "policy",
    "platform_count",
    "observation_count",
    "field_decision_count",
    "mean_retained_fields",
    "retained_location_fields",
    "retained_unclassified_fields",
    "contract_count",
    "stable_behavior_contracts",
    "stable_decision_contracts",
    "stable_metadata_contracts",
    "stable_complete_jpeg_contracts",
    "stable_decoded_pixel_contracts",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read one UTF-8 CSV file."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(
    path: Path,
    rows: Sequence[dict[str, str]],
    fieldnames: Sequence[str] | None = None,
) -> None:
    """Write deterministic UTF-8 CSV rows."""
    if not rows:
        raise ValueError("rows must not be empty")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(fieldnames or rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def load_platform_rows(
    input_dir: Path,
    filename: str,
    *,
    expected_platform_count: int,
) -> list[dict[str, str]]:
    """Load one named artifact from every platform directory."""
    paths = sorted(input_dir.rglob(filename))
    if len(paths) != expected_platform_count:
        raise RuntimeError(
            f"Expected {expected_platform_count} {filename} files, "
            f"found {len(paths)}"
        )
    rows: list[dict[str, str]] = []
    seen_platforms: set[str] = set()
    for path in paths:
        file_rows = read_csv(path)
        platforms = {row["platform_label"] for row in file_rows}
        if len(platforms) != 1:
            raise RuntimeError(f"{path} does not contain one platform")
        platform_label = next(iter(platforms))
        if platform_label in seen_platforms:
            raise RuntimeError(f"duplicate platform: {platform_label}")
        seen_platforms.add(platform_label)
        rows.extend(file_rows)
    return rows


def decision_signatures(
    decisions: Sequence[dict[str, str]],
) -> dict[tuple[str, str, str, str], str]:
    """Hash the ordered field decision set for each platform contract."""
    groups: dict[
        tuple[str, str, str, str], list[dict[str, str]]
    ] = defaultdict(list)
    for row in decisions:
        key = (
            row["platform_label"],
            row["fixture_id"],
            row["encoder"],
            row["policy"],
        )
        groups[key].append(row)
    signatures: dict[tuple[str, str, str, str], str] = {}
    for key, group in groups.items():
        payload = "\n".join(
            "|".join(
                (
                    row["field_id"],
                    row["category"],
                    row["source_value_sha256"],
                    row["retained"],
                    row["reason"],
                    row["output_value_sha256"],
                    row["semantic_value_exact"],
                )
            )
            for row in sorted(group, key=lambda value: value["field_id"])
        ).encode("utf-8")
        signatures[key] = hashlib.sha256(payload).hexdigest()
    return signatures


def build_contracts(
    observations: Sequence[dict[str, str]],
    decisions: Sequence[dict[str, str]],
    *,
    expected_platform_count: int,
) -> list[dict[str, str]]:
    """Summarize per-condition compatibility across platforms."""
    signatures = decision_signatures(decisions)
    groups: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(
        list
    )
    for row in observations:
        groups[(row["fixture_id"], row["encoder"], row["policy"])].append(
            row
        )
    rows: list[dict[str, str]] = []
    for key in sorted(groups):
        fixture_id, encoder, policy = key
        group = groups[key]
        platforms = {row["platform_label"] for row in group}
        if len(platforms) != expected_platform_count:
            raise RuntimeError(f"incomplete platform contract: {key}")
        behavior_signatures = {
            "|".join(
                (
                    row["source_field_count"],
                    row["retained_field_count"],
                    row["removed_field_count"],
                    row["retained_location_field_count"],
                    row["retained_unclassified_field_count"],
                    row["output_strict_accept"],
                    row["metadata_core_exact"],
                    row["pixels_exact_to_reencode_control"],
                    row["equivalent_layout_output_exact"],
                    row["error_category"],
                )
            )
            for row in group
        }
        decision_hashes = {
            signatures[
                (
                    row["platform_label"],
                    row["fixture_id"],
                    row["encoder"],
                    row["policy"],
                )
            ]
            for row in group
        }
        multiplicities = (
            len(behavior_signatures),
            len(decision_hashes),
            len({row["output_metadata_sha256"] for row in group}),
            len({row["output_sha256"] for row in group}),
            len({row["output_bgr_sha256"] for row in group}),
        )
        rows.append(
            {
                "fixture_id": fixture_id,
                "encoder": encoder,
                "policy": policy,
                "platform_count": str(len(platforms)),
                "behavior_signature_count": str(multiplicities[0]),
                "decision_signature_count": str(multiplicities[1]),
                "metadata_state_hash_count": str(multiplicities[2]),
                "complete_jpeg_hash_count": str(multiplicities[3]),
                "decoded_pixel_hash_count": str(multiplicities[4]),
                "strict_accept_count": str(
                    sum(row["output_strict_accept"] == "1" for row in group)
                ),
                "metadata_core_exact_count": str(
                    sum(row["metadata_core_exact"] == "1" for row in group)
                ),
                "pixel_exact_count": str(
                    sum(
                        row["pixels_exact_to_reencode_control"] == "1"
                        for row in group
                    )
                ),
                "all_contracts_stable": str(
                    int(all(count == 1 for count in multiplicities))
                ),
            }
        )
    return rows


def build_summary(
    observations: Sequence[dict[str, str]],
    decisions: Sequence[dict[str, str]],
    contracts: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Aggregate cross-platform evidence by encoder and policy."""
    observation_groups: dict[
        tuple[str, str], list[dict[str, str]]
    ] = defaultdict(list)
    decision_groups: dict[
        tuple[str, str], list[dict[str, str]]
    ] = defaultdict(list)
    contract_groups: dict[
        tuple[str, str], list[dict[str, str]]
    ] = defaultdict(list)
    for row in observations:
        observation_groups[(row["encoder"], row["policy"])].append(row)
    for row in decisions:
        decision_groups[(row["encoder"], row["policy"])].append(row)
    for row in contracts:
        contract_groups[(row["encoder"], row["policy"])].append(row)
    rows: list[dict[str, str]] = []
    for key in sorted(observation_groups):
        encoder, policy = key
        observation_group = observation_groups[key]
        decision_group = decision_groups[key]
        contract_group = contract_groups[key]
        platforms = {
            row["platform_label"] for row in observation_group
        }
        mean_retained = np.mean(
            [
                int(row["retained_field_count"])
                for row in observation_group
            ]
        )
        rows.append(
            {
                "encoder": encoder,
                "policy": policy,
                "platform_count": str(len(platforms)),
                "observation_count": str(len(observation_group)),
                "field_decision_count": str(len(decision_group)),
                "mean_retained_fields": f"{mean_retained:.9f}",
                "retained_location_fields": str(
                    sum(
                        int(row["retained_location_field_count"])
                        for row in observation_group
                    )
                ),
                "retained_unclassified_fields": str(
                    sum(
                        int(row["retained_unclassified_field_count"])
                        for row in observation_group
                    )
                ),
                "contract_count": str(len(contract_group)),
                "stable_behavior_contracts": _stable_count(
                    contract_group, "behavior_signature_count"
                ),
                "stable_decision_contracts": _stable_count(
                    contract_group, "decision_signature_count"
                ),
                "stable_metadata_contracts": _stable_count(
                    contract_group, "metadata_state_hash_count"
                ),
                "stable_complete_jpeg_contracts": _stable_count(
                    contract_group, "complete_jpeg_hash_count"
                ),
                "stable_decoded_pixel_contracts": _stable_count(
                    contract_group, "decoded_pixel_hash_count"
                ),
            }
        )
    return rows


def _stable_count(
    rows: Sequence[dict[str, str]], field: str
) -> str:
    """Count contracts with exactly one observed signature or hash."""
    return str(sum(row[field] == "1" for row in rows))


def validate_aggregate(
    observations: Sequence[dict[str, str]],
    decisions: Sequence[dict[str, str]],
    contracts: Sequence[dict[str, str]],
    *,
    expected_platform_count: int,
) -> None:
    """Validate the expected five-profile cross-platform matrix."""
    if len(observations) != expected_platform_count * 24:
        raise RuntimeError("unexpected cross-platform observation count")
    if len(decisions) != expected_platform_count * 288:
        raise RuntimeError("unexpected cross-platform decision count")
    if len(contracts) != 24:
        raise RuntimeError("unexpected cross-platform contract count")
    if any(row["all_contracts_stable"] != "1" for row in contracts):
        raise RuntimeError("a cross-platform field contract diverged")
    expected_count = str(expected_platform_count)
    if any(
        row["strict_accept_count"] != expected_count
        or row["metadata_core_exact_count"] != expected_count
        or row["pixel_exact_count"] != expected_count
        for row in contracts
    ):
        raise RuntimeError("a platform violated an output safety contract")


def plot_cross_platform(
    summary: Sequence[dict[str, str]], output_path: Path
) -> None:
    """Visualize field counts and cross-platform contract stability."""
    policies = (
        "retain_all",
        "drop_location_denylist",
        "allow_visual_context",
        "allow_catalog",
        "allow_attribution",
        "strip_all",
    )
    labels = (
        "Retain all",
        "Drop location",
        "Visual",
        "Catalog",
        "Attribution",
        "Strip all",
    )
    pillow_rows = {
        row["policy"]: row for row in summary if row["encoder"] == "pillow"
    }
    retained = [
        float(pillow_rows[policy]["mean_retained_fields"])
        for policy in policies
    ]
    stability_fields = (
        "stable_behavior_contracts",
        "stable_decision_contracts",
        "stable_metadata_contracts",
        "stable_complete_jpeg_contracts",
        "stable_decoded_pixel_contracts",
    )
    stability_labels = (
        "Behavior",
        "Decisions",
        "Metadata",
        "Complete JPEG",
        "Decoded pixels",
    )
    stability = np.array(
        [
            [
                int(pillow_rows[policy][field])
                / int(pillow_rows[policy]["contract_count"])
                for policy in policies
            ]
            for field in stability_fields
        ]
    )

    figure, axes = plt.subplots(1, 2, figsize=(13.2, 4.9))
    positions = np.arange(len(policies))
    axes[0].bar(positions, retained, color="#376996")
    axes[0].set_xticks(positions, labels, rotation=25, ha="right")
    axes[0].set_ylabel("Mean retained fields")
    axes[0].set_ylim(0, 13)
    axes[0].set_title("Policy field counts across five profiles")
    axes[0].grid(axis="y", alpha=0.25)

    image = axes[1].imshow(
        stability, vmin=0, vmax=1, cmap="Blues", aspect="auto"
    )
    axes[1].set_xticks(positions, labels, rotation=25, ha="right")
    axes[1].set_yticks(np.arange(len(stability_labels)), stability_labels)
    axes[1].set_title("Stable cross-platform contracts")
    for row_index in range(stability.shape[0]):
        for column_index in range(stability.shape[1]):
            value = stability[row_index, column_index]
            axes[1].text(
                column_index,
                row_index,
                f"{value:.0%}",
                ha="center",
                va="center",
                color="white" if value > 0.55 else "black",
            )
    figure.colorbar(image, ax=axes[1], fraction=0.046, pad=0.04)
    figure.suptitle(
        "Cross-Platform Selective Metadata Retention Contracts",
        fontsize=14,
    )
    figure.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=160)
    plt.close(figure)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Aggregate cross-platform field-level metadata contracts."
        )
    )
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--expected-platform-count", type=int, default=5
    )
    parser.add_argument(
        "--emit-log-payload",
        action="store_true",
        help="Print a compact JSON summary for the CI log.",
    )
    return parser.parse_args()


def main() -> None:
    """Aggregate platform artifacts and write deterministic reports."""
    args = parse_args()
    manifests = load_platform_rows(
        args.input_dir,
        MANIFEST_INPUT,
        expected_platform_count=args.expected_platform_count,
    )
    decisions = load_platform_rows(
        args.input_dir,
        DECISIONS_INPUT,
        expected_platform_count=args.expected_platform_count,
    )
    observations = load_platform_rows(
        args.input_dir,
        OBSERVATIONS_INPUT,
        expected_platform_count=args.expected_platform_count,
    )
    manifests.sort(
        key=lambda row: (row["platform_label"], row["component"])
    )
    decisions.sort(
        key=lambda row: (
            row["platform_label"],
            row["fixture_id"],
            row["encoder"],
            row["policy"],
            row["field_id"],
        )
    )
    observations.sort(
        key=lambda row: (
            row["platform_label"],
            row["fixture_id"],
            row["encoder"],
            row["policy"],
        )
    )
    contracts = build_contracts(
        observations,
        decisions,
        expected_platform_count=args.expected_platform_count,
    )
    validate_aggregate(
        observations,
        decisions,
        contracts,
        expected_platform_count=args.expected_platform_count,
    )
    summary = build_summary(observations, decisions, contracts)
    write_csv(args.output_dir / MANIFEST_OUTPUT, manifests)
    write_csv(args.output_dir / DECISIONS_OUTPUT, decisions)
    write_csv(args.output_dir / OBSERVATIONS_OUTPUT, observations)
    write_csv(
        args.output_dir / CONTRACTS_OUTPUT,
        contracts,
        CONTRACT_FIELDS,
    )
    write_csv(
        args.output_dir / SUMMARY_OUTPUT,
        summary,
        SUMMARY_FIELDS,
    )
    plot_cross_platform(summary, args.output_dir / FIGURE_OUTPUT)
    if args.emit_log_payload:
        print(
            json.dumps(
                {
                    "platforms": args.expected_platform_count,
                    "observations": len(observations),
                    "field_decisions": len(decisions),
                    "contracts": len(contracts),
                    "stable_contracts": sum(
                        row["all_contracts_stable"] == "1"
                        for row in contracts
                    ),
                },
                sort_keys=True,
            )
        )
    else:
        print(
            "Wrote "
            f"{len(contracts)} cross-platform field contracts to "
            f"{args.output_dir}"
        )


if __name__ == "__main__":
    main()
