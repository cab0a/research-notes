"""Aggregate cross-platform JPEG metadata resource-boundary observations."""

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


MANIFEST_INPUT = "jpeg_resource_budget_runtime_manifest.csv"
OBSERVATIONS_INPUT = "jpeg_resource_budget_observations.csv"

MANIFEST_OUTPUT = (
    "jpeg_resource_budget_cross_platform_runtime_manifest.csv"
)
OBSERVATIONS_OUTPUT = (
    "jpeg_resource_budget_cross_platform_observations.csv"
)
CONTRACTS_OUTPUT = "jpeg_resource_budget_cross_platform_contracts.csv"
SUMMARY_OUTPUT = "jpeg_resource_budget_cross_platform_summary.csv"
FIGURE_OUTPUT = "jpeg_resource_budget_cross_platform.png"

CONTRACT_FIELDS = (
    "fixture",
    "resource_family",
    "boundary_relation",
    "expected_decision",
    "expected_reason_code",
    "platform_count",
    "observed_decision_count",
    "reason_code_count",
    "issue_signature_count",
    "counter_signature_count",
    "fixture_sha256_count",
    "expectation_met_count",
    "stable_contract",
)

SUMMARY_FIELDS = (
    "resource_family",
    "fixture_contracts",
    "platform_observations",
    "accept_observations",
    "quarantine_observations",
    "reject_observations",
    "expectation_rate",
    "stable_contract_rate",
    "maximum_counter_signature_count",
)

COUNTER_SIGNATURE_FIELDS = (
    "observed_decision",
    "reason_code",
    "issue_codes",
    "header_scan_complete",
    "image_data_reached",
    "limit_value",
    "observed_value",
    "admitted_value",
    "header_segments_seen",
    "header_segments_admitted",
    "metadata_segments_seen",
    "metadata_segments_admitted",
    "metadata_bytes_seen",
    "metadata_bytes_admitted",
    "largest_metadata_segment_seen",
    "largest_metadata_segment_admitted",
    "exif_entries_seen",
    "exif_entries_admitted",
    "xmp_packet_bytes_seen",
    "xmp_packet_bytes_admitted",
    "xmp_nodes_seen",
    "xmp_nodes_admitted",
    "xmp_depth_seen",
    "xmp_depth_admitted",
    "xmp_text_bytes_seen",
    "xmp_text_bytes_admitted",
    "icc_chunks_seen",
    "icc_chunks_admitted",
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
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Load manifests and observations from downloaded platform artifacts."""
    manifest_paths = sorted(input_dir.rglob(MANIFEST_INPUT))
    observation_paths = sorted(input_dir.rglob(OBSERVATIONS_INPUT))
    if not manifest_paths or not observation_paths:
        raise FileNotFoundError(
            "resource-boundary platform artifacts were not found"
        )
    manifests = [
        row for path in manifest_paths for row in read_csv(path)
    ]
    observations = [
        row for path in observation_paths for row in read_csv(path)
    ]
    manifests.sort(
        key=lambda row: (row["platform_label"], row["component"])
    )
    observations.sort(
        key=lambda row: (row["fixture"], row["platform_label"])
    )
    return manifests, observations


def build_contracts(
    observations: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Build one compatibility contract for each controlled fixture."""
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in observations:
        grouped[row["fixture"]].append(row)

    contracts: list[dict[str, str]] = []
    for fixture in sorted(grouped):
        rows = grouped[fixture]
        decision_count = len(
            {row["observed_decision"] for row in rows}
        )
        reason_count = len({row["reason_code"] for row in rows})
        issue_count = len({row["issue_codes"] for row in rows})
        counter_count = len(
            {
                _signature(row, COUNTER_SIGNATURE_FIELDS)
                for row in rows
            }
        )
        fixture_hash_count = len(
            {row["fixture_sha256"] for row in rows}
        )
        expectation_count = sum(
            int(row["expectation_met"]) for row in rows
        )
        platform_count = len(
            {row["platform_label"] for row in rows}
        )
        stable = (
            decision_count
            == reason_count
            == issue_count
            == counter_count
            == fixture_hash_count
            == 1
            and expectation_count == platform_count
        )
        contracts.append(
            {
                "fixture": fixture,
                "resource_family": rows[0]["resource_family"],
                "boundary_relation": rows[0]["boundary_relation"],
                "expected_decision": rows[0]["expected_decision"],
                "expected_reason_code": rows[0][
                    "expected_reason_code"
                ],
                "platform_count": str(platform_count),
                "observed_decision_count": str(decision_count),
                "reason_code_count": str(reason_count),
                "issue_signature_count": str(issue_count),
                "counter_signature_count": str(counter_count),
                "fixture_sha256_count": str(fixture_hash_count),
                "expectation_met_count": str(expectation_count),
                "stable_contract": str(int(stable)),
            }
        )
    return contracts


def _signature(
    row: dict[str, str], fields: Sequence[str]
) -> str:
    """Hash one deterministic observation projection."""
    payload = json.dumps(
        [row[field] for field in fields],
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def build_summary(
    observations: Sequence[dict[str, str]],
    contracts: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Aggregate observed decisions and stability by resource family."""
    observations_by_family: dict[
        str, list[dict[str, str]]
    ] = defaultdict(list)
    contracts_by_family: dict[
        str, list[dict[str, str]]
    ] = defaultdict(list)
    for row in observations:
        observations_by_family[row["resource_family"]].append(row)
    for row in contracts:
        contracts_by_family[row["resource_family"]].append(row)

    summary: list[dict[str, str]] = []
    for family in sorted(observations_by_family):
        rows = observations_by_family[family]
        family_contracts = contracts_by_family[family]
        summary.append(
            {
                "resource_family": family,
                "fixture_contracts": str(len(family_contracts)),
                "platform_observations": str(len(rows)),
                "accept_observations": str(
                    sum(
                        row["observed_decision"] == "accept"
                        for row in rows
                    )
                ),
                "quarantine_observations": str(
                    sum(
                        row["observed_decision"] == "quarantine"
                        for row in rows
                    )
                ),
                "reject_observations": str(
                    sum(
                        row["observed_decision"] == "reject"
                        for row in rows
                    )
                ),
                "expectation_rate": _rate(rows, "expectation_met"),
                "stable_contract_rate": _rate(
                    family_contracts, "stable_contract"
                ),
                "maximum_counter_signature_count": str(
                    max(
                        int(row["counter_signature_count"])
                        for row in family_contracts
                    )
                ),
            }
        )
    return summary


def _rate(rows: Sequence[dict[str, str]], field: str) -> str:
    """Return a deterministic binary rate."""
    return f"{sum(int(row[field]) for row in rows) / len(rows):.6f}"


def validate_aggregate(
    manifests: Sequence[dict[str, str]],
    observations: Sequence[dict[str, str]],
    contracts: Sequence[dict[str, str]],
    *,
    expected_platform_count: int,
) -> None:
    """Validate completeness and compatibility expectations."""
    platforms = {row["platform_label"] for row in observations}
    manifest_platforms = {row["platform_label"] for row in manifests}
    if len(platforms) != expected_platform_count:
        raise RuntimeError(
            f"expected {expected_platform_count} platforms, "
            f"found {len(platforms)}"
        )
    if platforms != manifest_platforms:
        raise RuntimeError(
            "manifest and observation platform labels do not match"
        )
    if len(observations) != 24 * expected_platform_count:
        raise RuntimeError("unexpected cross-platform observation count")
    if len(contracts) != 24:
        raise RuntimeError("expected 24 resource-boundary contracts")
    if any(
        int(row["platform_count"]) != expected_platform_count
        for row in contracts
    ):
        raise RuntimeError("a fixture contract is missing a platform")
    if any(row["stable_contract"] != "1" for row in contracts):
        raise RuntimeError("a resource-boundary contract is unstable")


def plot_cross_platform(
    observations: Sequence[dict[str, str]],
    contracts: Sequence[dict[str, str]],
    output_path: Path,
) -> None:
    """Visualize cross-platform routing and counter stability."""
    families = sorted(
        {row["resource_family"] for row in observations}
    )
    y = np.arange(len(families))
    decision_counts = {
        decision: [
            sum(
                row["resource_family"] == family
                and row["observed_decision"] == decision
                for row in observations
            )
            for family in families
        ]
        for decision in ("accept", "quarantine", "reject")
    }
    stable_rates = []
    for family in families:
        family_contracts = [
            row
            for row in contracts
            if row["resource_family"] == family
        ]
        stable_rates.append(
            sum(int(row["stable_contract"]) for row in family_contracts)
            / len(family_contracts)
        )

    figure, axes = plt.subplots(1, 2, figsize=(13.5, 7.5))
    left = np.zeros(len(families))
    colors = {
        "accept": "#2a9d8f",
        "quarantine": "#e9c46a",
        "reject": "#e76f51",
    }
    for decision in ("accept", "quarantine", "reject"):
        values = np.asarray(decision_counts[decision])
        axes[0].barh(
            y,
            values,
            left=left,
            label=decision,
            color=colors[decision],
        )
        left += values
    axes[0].set_yticks(y, families)
    axes[0].set_xlabel("Platform observations")
    axes[0].set_title("Routing decisions across five profiles")
    axes[0].legend(loc="lower right")
    axes[0].grid(axis="x", alpha=0.25)

    axes[1].barh(y, stable_rates, color="#457b9d")
    axes[1].set_yticks(y, families)
    axes[1].set_xlim(0, 1.05)
    axes[1].set_xlabel("Stable contracts / fixture contracts")
    axes[1].set_title("Decision, reason, counter, and fixture stability")
    axes[1].axvline(1.0, color="#264653", linestyle="--", linewidth=1)
    axes[1].grid(axis="x", alpha=0.25)

    figure.suptitle(
        "Cross-Platform JPEG Metadata Resource Contracts",
        fontsize=14,
        fontweight="bold",
    )
    figure.tight_layout(rect=(0, 0, 1, 0.96))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Aggregate cross-platform metadata resource-boundary results."
        )
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
        help="Directory for combined CSV and PNG artifacts.",
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
        help="Print a compact machine-readable aggregate summary.",
    )
    return parser.parse_args()


def main() -> None:
    """Aggregate downloaded platform evidence."""
    args = parse_args()
    manifests, observations = load_platform_rows(args.input_dir)
    contracts = build_contracts(observations)
    summary = build_summary(observations, contracts)
    validate_aggregate(
        manifests,
        observations,
        contracts,
        expected_platform_count=args.expected_platform_count,
    )
    write_csv(args.output_dir / MANIFEST_OUTPUT, manifests)
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
    plot_cross_platform(
        observations,
        contracts,
        args.output_dir / FIGURE_OUTPUT,
    )
    if args.emit_log_payload:
        print(
            json.dumps(
                {
                    "platforms": args.expected_platform_count,
                    "observations": len(observations),
                    "contracts": len(contracts),
                    "stable_contracts": sum(
                        int(row["stable_contract"])
                        for row in contracts
                    ),
                },
                sort_keys=True,
            )
        )
    else:
        print(
            "Wrote "
            f"{len(observations)} observations and {len(contracts)} "
            f"contracts to {args.output_dir}"
        )


if __name__ == "__main__":
    main()
