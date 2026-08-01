"""Aggregate cross-platform metadata-family coverage observations."""

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


MANIFEST_INPUT = "jpeg_metadata_coverage_runtime_manifest.csv"
OBSERVATIONS_INPUT = "jpeg_metadata_coverage_observations.csv"
MANIFEST_OUTPUT = "jpeg_metadata_coverage_cross_platform_runtime_manifest.csv"
OBSERVATIONS_OUTPUT = "jpeg_metadata_coverage_cross_platform_observations.csv"
CONTRACTS_OUTPUT = "jpeg_metadata_coverage_cross_platform_contracts.csv"
SUMMARY_OUTPUT = "jpeg_metadata_coverage_cross_platform_summary.csv"
FIGURE_OUTPUT = "jpeg_metadata_coverage_cross_platform.png"

SIGNATURE_FIELDS = (
    "observed_decision",
    "reason_code",
    "resource_decision",
    "resource_reason_code",
    "families",
    "relationship_completion_rate",
    "recognized_components",
    "opaque_components",
    "relationships_declared",
    "relationships_resolved",
    "exif_thumbnails",
    "exif_thumbnail_bytes",
    "maker_notes",
    "maker_note_bytes",
    "standard_xmp_packets",
    "extended_xmp_chunks",
    "extended_xmp_bytes",
    "iptc_iim_blocks",
    "iptc_iim_datasets",
)

CONTRACT_FIELDS = (
    "fixture",
    "family",
    "condition",
    "expected_decision",
    "expected_reason_code",
    "platform_count",
    "observed_decision_count",
    "reason_code_count",
    "behavior_signature_count",
    "fixture_sha256_count",
    "expectation_met_count",
    "stable_contract",
)

SUMMARY_FIELDS = (
    "family",
    "fixture_contracts",
    "platform_observations",
    "accept_observations",
    "quarantine_observations",
    "reject_observations",
    "expectation_rate",
    "stable_contract_rate",
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
    """Load all manifests and observations from platform artifacts."""
    manifest_paths = sorted(input_dir.rglob(MANIFEST_INPUT))
    observation_paths = sorted(input_dir.rglob(OBSERVATIONS_INPUT))
    if not manifest_paths or not observation_paths:
        raise FileNotFoundError("metadata-coverage platform artifacts were not found")
    manifests = [row for path in manifest_paths for row in read_csv(path)]
    observations = [
        row for path in observation_paths for row in read_csv(path)
    ]
    manifests.sort(key=lambda row: (row["platform_label"], row["component"]))
    observations.sort(key=lambda row: (row["fixture"], row["platform_label"]))
    return manifests, observations


def _signature(row: dict[str, str]) -> str:
    """Hash the deterministic behavior fields of one observation."""
    payload = "\x1f".join(row[field] for field in SIGNATURE_FIELDS)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_contracts(
    observations: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Summarize cross-platform multiplicity for every fixture."""
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in observations:
        grouped[row["fixture"]].append(row)
    contracts = []
    for fixture in sorted(grouped):
        rows = grouped[fixture]
        first = rows[0]
        decisions = {row["observed_decision"] for row in rows}
        reasons = {row["reason_code"] for row in rows}
        behavior = {_signature(row) for row in rows}
        hashes = {row["fixture_sha256"] for row in rows}
        platform_count = len({row["platform_label"] for row in rows})
        expectation_met = sum(int(row["expectation_met"]) for row in rows)
        stable = (
            len(decisions) == 1
            and len(reasons) == 1
            and len(behavior) == 1
            and len(hashes) == 1
            and expectation_met == platform_count
        )
        contracts.append(
            {
                "fixture": fixture,
                "family": first["family"],
                "condition": first["condition"],
                "expected_decision": first["expected_decision"],
                "expected_reason_code": first["expected_reason_code"],
                "platform_count": str(platform_count),
                "observed_decision_count": str(len(decisions)),
                "reason_code_count": str(len(reasons)),
                "behavior_signature_count": str(len(behavior)),
                "fixture_sha256_count": str(len(hashes)),
                "expectation_met_count": str(expectation_met),
                "stable_contract": str(int(stable)),
            }
        )
    return contracts


def build_summary(
    observations: Sequence[dict[str, str]],
    contracts: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Aggregate platform observations and contracts by family."""
    obs_grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    contract_grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in observations:
        obs_grouped[row["family"]].append(row)
    for row in contracts:
        contract_grouped[row["family"]].append(row)
    summary = []
    for family in sorted(obs_grouped):
        rows = obs_grouped[family]
        family_contracts = contract_grouped[family]
        summary.append(
            {
                "family": family,
                "fixture_contracts": str(len(family_contracts)),
                "platform_observations": str(len(rows)),
                "accept_observations": str(
                    sum(row["observed_decision"] == "accept" for row in rows)
                ),
                "quarantine_observations": str(
                    sum(
                        row["observed_decision"] == "quarantine"
                        for row in rows
                    )
                ),
                "reject_observations": str(
                    sum(row["observed_decision"] == "reject" for row in rows)
                ),
                "expectation_rate": (
                    f"{sum(int(row['expectation_met']) for row in rows) / len(rows):.6f}"
                ),
                "stable_contract_rate": (
                    f"{sum(int(row['stable_contract']) for row in family_contracts) / len(family_contracts):.6f}"
                ),
            }
        )
    return summary


def validate_aggregate(
    manifests: Sequence[dict[str, str]],
    observations: Sequence[dict[str, str]],
    contracts: Sequence[dict[str, str]],
    *,
    expected_platform_count: int,
) -> None:
    """Validate complete platform and fixture coverage."""
    platforms = {row["platform_label"] for row in observations}
    if len(platforms) != expected_platform_count:
        raise RuntimeError("unexpected metadata-coverage platform count")
    if len(observations) != 15 * expected_platform_count:
        raise RuntimeError("unexpected metadata-coverage observation count")
    if len(contracts) != 15:
        raise RuntimeError("expected 15 metadata-coverage contracts")
    if any(row["stable_contract"] != "1" for row in contracts):
        raise RuntimeError("a metadata-coverage contract is unstable")
    manifest_platforms = {row["platform_label"] for row in manifests}
    if manifest_platforms != platforms:
        raise RuntimeError("manifest and observation platforms differ")


def plot_cross_platform(
    observations: Sequence[dict[str, str]],
    contracts: Sequence[dict[str, str]],
    output_path: Path,
) -> None:
    """Visualize matrix routing and contract stability."""
    platforms = sorted({row["platform_label"] for row in observations})
    decisions = ("accept", "quarantine", "reject")
    colors = ("#2a9d8f", "#e9c46a", "#e76f51")
    figure, axes = plt.subplots(1, 2, figsize=(13.5, 6.5))
    bottom = np.zeros(len(platforms))
    for decision, color in zip(decisions, colors, strict=True):
        values = [
            sum(
                row["platform_label"] == label
                and row["observed_decision"] == decision
                for row in observations
            )
            for label in platforms
        ]
        axes[0].bar(platforms, values, bottom=bottom, color=color, label=decision)
        bottom += np.array(values)
    axes[0].set_ylabel("Observation count")
    axes[0].set_title("Routing is repeated on every profile")
    axes[0].tick_params(axis="x", rotation=30)
    axes[0].legend()

    stable = sum(int(row["stable_contract"]) for row in contracts)
    axes[1].bar(
        ["Stable", "Unstable"],
        [stable, len(contracts) - stable],
        color=["#457b9d", "#e76f51"],
    )
    axes[1].set_ylim(0, len(contracts) + 1)
    axes[1].set_ylabel("Fixture contracts")
    axes[1].set_title("Decision, reason, counters, and hashes")
    axes[1].grid(axis="y", alpha=0.25)
    figure.suptitle(
        "Cross-Platform Metadata Coverage Contracts",
        fontsize=14,
        fontweight="bold",
    )
    figure.tight_layout(rect=(0, 0.03, 1, 0.96))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Aggregate cross-platform metadata coverage results."
    )
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-platform-count", type=int, default=5)
    parser.add_argument("--emit-log-payload", action="store_true")
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
    write_csv(args.output_dir / CONTRACTS_OUTPUT, contracts, CONTRACT_FIELDS)
    write_csv(args.output_dir / SUMMARY_OUTPUT, summary, SUMMARY_FIELDS)
    plot_cross_platform(observations, contracts, args.output_dir / FIGURE_OUTPUT)
    payload = {
        "platforms": args.expected_platform_count,
        "observations": len(observations),
        "contracts": len(contracts),
        "stable_contracts": sum(int(row["stable_contract"]) for row in contracts),
    }
    if args.emit_log_payload:
        print(json.dumps(payload, sort_keys=True))
    else:
        print(
            f"Wrote {len(observations)} observations and {len(contracts)} "
            f"contracts to {args.output_dir}"
        )


if __name__ == "__main__":
    main()
