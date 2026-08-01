"""Aggregate cross-platform JPEG transform-integrity observations."""

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


MANIFEST_INPUT = "jpeg_transform_integrity_runtime_manifest.csv"
OBSERVATIONS_INPUT = "jpeg_transform_integrity_observations.csv"
MANIFEST_OUTPUT = "jpeg_transform_integrity_cross_platform_runtime_manifest.csv"
OBSERVATIONS_OUTPUT = "jpeg_transform_integrity_cross_platform_observations.csv"
CONTRACTS_OUTPUT = "jpeg_transform_integrity_cross_platform_contracts.csv"
SUMMARY_OUTPUT = "jpeg_transform_integrity_cross_platform_summary.csv"
FIGURE_OUTPUT = "jpeg_transform_integrity_cross_platform.png"

SIGNATURE_FIELDS = (
    "observed_status",
    "reason_code",
    "action",
    "parent_declared",
    "assertion_sha256",
    "binding_names",
    "matching_bindings",
    "mismatching_bindings",
    "matching_binding_count",
    "mismatching_binding_count",
)

CONTRACT_FIELDS = (
    "fixture",
    "transform",
    "assertion_mode",
    "expected_status",
    "expected_reason_code",
    "platform_count",
    "observed_status_count",
    "reason_code_count",
    "behavior_signature_count",
    "fixture_sha256_count",
    "expectation_met_count",
    "stable_contract",
)

SUMMARY_FIELDS = (
    "transform",
    "fixture_contracts",
    "platform_observations",
    "valid_observations",
    "stale_observations",
    "invalid_assertion_observations",
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
    """Load all platform manifests and observations."""
    manifest_paths = sorted(input_dir.rglob(MANIFEST_INPUT))
    observation_paths = sorted(input_dir.rglob(OBSERVATIONS_INPUT))
    if not manifest_paths or not observation_paths:
        raise FileNotFoundError("transform-integrity artifacts were not found")
    manifests = [row for path in manifest_paths for row in read_csv(path)]
    observations = [row for path in observation_paths for row in read_csv(path)]
    manifests.sort(key=lambda row: (row["platform_label"], row["component"]))
    observations.sort(key=lambda row: (row["fixture"], row["platform_label"]))
    return manifests, observations


def _signature(row: dict[str, str]) -> str:
    """Hash deterministic behavior fields."""
    payload = "\x1f".join(row[field] for field in SIGNATURE_FIELDS)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_contracts(
    observations: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Build one multiplicity contract per fixture."""
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in observations:
        grouped[row["fixture"]].append(row)
    contracts = []
    for fixture in sorted(grouped):
        rows = grouped[fixture]
        first = rows[0]
        statuses = {row["observed_status"] for row in rows}
        reasons = {row["reason_code"] for row in rows}
        behaviors = {_signature(row) for row in rows}
        hashes = {row["fixture_sha256"] for row in rows}
        platforms = {row["platform_label"] for row in rows}
        met = sum(int(row["expectation_met"]) for row in rows)
        stable = (
            len(statuses) == len(reasons) == len(behaviors) == len(hashes) == 1
            and met == len(platforms)
        )
        contracts.append(
            {
                "fixture": fixture,
                "transform": first["transform"],
                "assertion_mode": first["assertion_mode"],
                "expected_status": first["expected_status"],
                "expected_reason_code": first["expected_reason_code"],
                "platform_count": str(len(platforms)),
                "observed_status_count": str(len(statuses)),
                "reason_code_count": str(len(reasons)),
                "behavior_signature_count": str(len(behaviors)),
                "fixture_sha256_count": str(len(hashes)),
                "expectation_met_count": str(met),
                "stable_contract": str(int(stable)),
            }
        )
    return contracts


def build_summary(
    observations: Sequence[dict[str, str]],
    contracts: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Aggregate observations and contracts by transform."""
    obs_grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    con_grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in observations:
        obs_grouped[row["transform"]].append(row)
    for row in contracts:
        con_grouped[row["transform"]].append(row)
    summary = []
    for transform in sorted(obs_grouped):
        rows = obs_grouped[transform]
        related = con_grouped[transform]
        summary.append(
            {
                "transform": transform,
                "fixture_contracts": str(len(related)),
                "platform_observations": str(len(rows)),
                "valid_observations": str(
                    sum(row["observed_status"].startswith("valid_") for row in rows)
                ),
                "stale_observations": str(
                    sum(row["observed_status"] == "stale_binding" for row in rows)
                ),
                "invalid_assertion_observations": str(
                    sum(
                        row["observed_status"]
                        in (
                            "missing_assertion",
                            "malformed_assertion",
                            "multiple_assertions",
                        )
                        for row in rows
                    )
                ),
                "expectation_rate": (
                    f"{sum(int(row['expectation_met']) for row in rows) / len(rows):.6f}"
                ),
                "stable_contract_rate": (
                    f"{sum(int(row['stable_contract']) for row in related) / len(related):.6f}"
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
    """Validate complete and stable matrix coverage."""
    platforms = {row["platform_label"] for row in observations}
    if len(platforms) != expected_platform_count:
        raise RuntimeError("unexpected transform-integrity platform count")
    if len(observations) != 11 * expected_platform_count:
        raise RuntimeError("unexpected transform-integrity observation count")
    if len(contracts) != 11 or any(
        row["stable_contract"] != "1" for row in contracts
    ):
        raise RuntimeError("a transform-integrity contract is incomplete or unstable")
    if {row["platform_label"] for row in manifests} != platforms:
        raise RuntimeError("manifest and observation platforms differ")


def plot_cross_platform(
    observations: Sequence[dict[str, str]],
    contracts: Sequence[dict[str, str]],
    output_path: Path,
) -> None:
    """Visualize platform status counts and contract stability."""
    platforms = sorted({row["platform_label"] for row in observations})
    groups = (
        ("valid", lambda status: status.startswith("valid_"), "#2a9d8f"),
        ("stale", lambda status: status == "stale_binding", "#e9c46a"),
        ("invalid assertion", lambda status: status not in ("valid_binding", "valid_derived_binding", "stale_binding"), "#e76f51"),
    )
    figure, axes = plt.subplots(1, 2, figsize=(13.5, 6.5))
    bottom = np.zeros(len(platforms))
    for label, predicate, color in groups:
        values = [
            sum(
                row["platform_label"] == platform_label
                and predicate(row["observed_status"])
                for row in observations
            )
            for platform_label in platforms
        ]
        axes[0].bar(platforms, values, bottom=bottom, label=label, color=color)
        bottom += np.array(values)
    axes[0].set_ylabel("Observation count")
    axes[0].set_title("Integrity outcomes repeat across profiles")
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
    axes[1].set_title("Status, reason, bindings, assertion, and fixture hashes")
    figure.suptitle(
        "Cross-Platform Transform-Integrity Contracts",
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
        description="Aggregate cross-platform transform-integrity results."
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
    print(json.dumps(payload, sort_keys=True) if args.emit_log_payload else f"Wrote {len(observations)} observations and {len(contracts)} contracts to {args.output_dir}")


if __name__ == "__main__":
    main()
