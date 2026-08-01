"""Evaluate explainable composition of JPEG metadata policy stages."""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import platform
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

import matplotlib
import numpy as np
import PIL
from numpy.typing import NDArray
from PIL import features

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

from research_notes import (  # noqa: E402
    JPEG_INTAKE_POLICIES,
    apply_explainable_jpeg_policy,
    build_policy_composition_fixtures,
    build_synthetic_rgb_profile,
    encode_jpeg_pillow,
    output_sha256,
)


MANIFEST_NAME = "jpeg_policy_composition_runtime_manifest.csv"
OBSERVATIONS_NAME = "jpeg_policy_composition_observations.csv"
SUMMARY_NAME = "jpeg_policy_composition_summary.csv"
FIGURE_NAME = "jpeg_policy_composition.png"

OBSERVATION_FIELDS = (
    "platform_label",
    "fixture",
    "condition",
    "profile",
    "require_integrity",
    "opaque_metadata_policy",
    "retention_policy",
    "expected_decision",
    "observed_decision",
    "expectation_met",
    "expected_reason_code",
    "reason_code",
    "emitted",
    "stages_evaluated",
    "decisive_stage",
    "trace",
    "source_field_count",
    "retained_field_count",
    "dropped_field_count",
    "opaque_component_count",
    "integrity_status_before",
    "integrity_status_after",
    "input_sha256",
    "output_sha256",
)

SUMMARY_FIELDS = (
    "profile",
    "fixtures",
    "accept_count",
    "sanitize_count",
    "quarantine_count",
    "reject_count",
    "emitted_count",
    "expectation_rate",
    "source_field_count",
    "retained_field_count",
    "dropped_field_count",
)


def write_csv(
    path: Path,
    rows: Sequence[dict[str, str]],
    fieldnames: Sequence[str],
) -> None:
    """Write deterministic UTF-8 CSV rows."""
    if not rows:
        raise ValueError("rows must not be empty")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(fieldnames), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def make_base_image() -> NDArray[np.uint8]:
    """Return one deterministic synthetic BGR image."""
    rows, columns = np.indices((72, 96), dtype=np.uint16)
    return np.stack(
        (
            (columns * 3 + rows) % 256,
            (rows * 5 + columns // 2) % 256,
            ((rows // 8 + columns // 8) % 2) * 180 + 35,
        ),
        axis=2,
    ).astype(np.uint8)


def pillow_jpeg_backend() -> str:
    """Return the JPEG backend reported by Pillow."""
    turbo_version = features.version_feature("libjpeg_turbo")
    if turbo_version is not None:
        codec_name = (
            "mozjpeg" if features.check_feature("mozjpeg") else "libjpeg-turbo"
        )
        return f"{codec_name} {turbo_version}"
    jpeg_version = features.version_codec("jpg")
    if jpeg_version is None:
        raise RuntimeError("Pillow does not report a JPEG codec")
    return f"libjpeg {jpeg_version}"


def build_runtime_manifest(
    platform_label: str, *, record_runner_image: bool = False
) -> list[dict[str, str]]:
    """Record the composition engine, prerequisite stages, and encoder."""
    common = {
        "platform_label": platform_label,
        "operating_system": platform.system(),
        "architecture": platform.machine().lower(),
        "python_version": platform.python_version(),
        "runner_image_os": (
            os.environ.get("ImageOS", "unknown")
            if record_runner_image
            else "not_recorded"
        ),
        "runner_image_version": (
            os.environ.get("ImageVersion", "unknown")
            if record_runner_image
            else "not_recorded"
        ),
    }
    definitions = (
        (
            "policy_composition_engine",
            "decision_engine",
            "research-notes",
            "0.20.0",
            "ordered resource, coverage, opacity, integrity, and retention stages",
        ),
        (
            "policy_inputs",
            "stage_contracts",
            "research-notes",
            "0.16.0-0.19.0",
            "selective retention, resource admission, coverage, and digest binding",
        ),
        (
            "fixture_encoder",
            "image_encoder",
            f"Pillow {PIL.__version__}",
            pillow_jpeg_backend(),
            "quality 75; chroma 444",
        ),
    )
    return [
        {
            **common,
            "component": component,
            "role": role,
            "implementation": implementation,
            "version_or_backend": version,
            "contract": contract,
        }
        for component, role, implementation, version, contract in definitions
    ]


def _serialize_trace(result: object) -> str:
    """Serialize an ordered trace into one deterministic CSV field."""
    return "|".join(
        f"{step.stage}:{step.outcome}:{step.reason_code}:{int(step.decisive)}"
        for step in result.trace
    )


def collect_observations(platform_label: str) -> list[dict[str, str]]:
    """Evaluate every controlled fixture under all four profiles."""
    base_jpeg = encode_jpeg_pillow(
        make_base_image(), quality=75, chroma_sampling="444"
    )
    fixtures = build_policy_composition_fixtures(
        base_jpeg, icc_profile=build_synthetic_rgb_profile(2.2)
    )
    observations = []
    for fixture in fixtures:
        input_hash = hashlib.sha256(fixture.jpeg_bytes).hexdigest()
        for policy in JPEG_INTAKE_POLICIES:
            result = apply_explainable_jpeg_policy(
                fixture.jpeg_bytes, base_jpeg, policy
            )
            expected_decision = fixture.expected_decision(policy.name)
            expected_reason = fixture.expected_reason_code(policy.name)
            decisive = next(step for step in result.trace if step.decisive)
            observations.append(
                {
                    "platform_label": platform_label,
                    "fixture": fixture.fixture,
                    "condition": fixture.condition,
                    "profile": policy.name,
                    "require_integrity": str(int(policy.require_integrity)),
                    "opaque_metadata_policy": policy.opaque_metadata,
                    "retention_policy": policy.retention_policy,
                    "expected_decision": expected_decision,
                    "observed_decision": result.decision,
                    "expectation_met": str(
                        int(
                            result.decision == expected_decision
                            and result.reason_code == expected_reason
                        )
                    ),
                    "expected_reason_code": expected_reason,
                    "reason_code": result.reason_code,
                    "emitted": str(int(result.emitted)),
                    "stages_evaluated": str(len(result.trace)),
                    "decisive_stage": decisive.stage,
                    "trace": _serialize_trace(result),
                    "source_field_count": str(result.source_field_count),
                    "retained_field_count": str(result.retained_field_count),
                    "dropped_field_count": str(
                        result.source_field_count - result.retained_field_count
                    ),
                    "opaque_component_count": str(
                        result.opaque_component_count
                    ),
                    "integrity_status_before": result.integrity_status_before,
                    "integrity_status_after": result.integrity_status_after,
                    "input_sha256": input_hash,
                    "output_sha256": output_sha256(result),
                }
            )
    observations.sort(key=lambda row: (row["fixture"], row["profile"]))
    validate_observations(observations)
    return observations


def validate_observations(
    observations: Sequence[dict[str, str]],
) -> None:
    """Enforce fixture, profile, trace, and aggregate expectations."""
    if len(observations) != 36:
        raise RuntimeError("expected 36 policy-composition observations")
    if any(row["expectation_met"] != "1" for row in observations):
        raise RuntimeError("a policy-composition expectation failed")
    counts = {
        decision: sum(row["observed_decision"] == decision for row in observations)
        for decision in ("accept", "sanitize", "quarantine", "reject")
    }
    if counts != {"accept": 4, "sanitize": 5, "quarantine": 23, "reject": 4}:
        raise RuntimeError(f"unexpected decision totals: {counts}")
    for row in observations:
        decisive_count = sum(
            item.endswith(":1") for item in row["trace"].split("|")
        )
        if decisive_count != 1:
            raise RuntimeError("a trace does not contain one decisive step")
    privacy = next(
        row
        for row in observations
        if row["fixture"] == "clean_valid_assertion"
        and row["profile"] == "privacy_review"
    )
    if (privacy["source_field_count"], privacy["retained_field_count"]) != (
        "6",
        "2",
    ):
        raise RuntimeError("privacy review did not retain two visual fields")


def summarize(
    observations: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Aggregate decisions and emitted field counts by profile."""
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in observations:
        grouped[row["profile"]].append(row)
    summary = []
    for profile in sorted(grouped):
        rows = grouped[profile]
        summary.append(
            {
                "profile": profile,
                "fixtures": str(len(rows)),
                "accept_count": str(
                    sum(row["observed_decision"] == "accept" for row in rows)
                ),
                "sanitize_count": str(
                    sum(row["observed_decision"] == "sanitize" for row in rows)
                ),
                "quarantine_count": str(
                    sum(row["observed_decision"] == "quarantine" for row in rows)
                ),
                "reject_count": str(
                    sum(row["observed_decision"] == "reject" for row in rows)
                ),
                "emitted_count": str(sum(int(row["emitted"]) for row in rows)),
                "expectation_rate": (
                    f"{sum(int(row['expectation_met']) for row in rows) / len(rows):.6f}"
                ),
                "source_field_count": str(
                    sum(int(row["source_field_count"]) for row in rows)
                ),
                "retained_field_count": str(
                    sum(int(row["retained_field_count"]) for row in rows)
                ),
                "dropped_field_count": str(
                    sum(int(row["dropped_field_count"]) for row in rows)
                ),
            }
        )
    return summary


def plot_results(
    observations: Sequence[dict[str, str]], output_path: Path
) -> None:
    """Visualize final decisions and their decisive stages."""
    profiles = [policy.name for policy in JPEG_INTAKE_POLICIES]
    decisions = ("accept", "sanitize", "quarantine", "reject")
    colors = ("#2a9d8f", "#457b9d", "#e9c46a", "#e76f51")
    figure, axes = plt.subplots(1, 2, figsize=(14, 6.7))
    bottom = np.zeros(len(profiles))
    for decision, color in zip(decisions, colors, strict=True):
        values = [
            sum(
                row["profile"] == profile
                and row["observed_decision"] == decision
                for row in observations
            )
            for profile in profiles
        ]
        axes[0].bar(profiles, values, bottom=bottom, label=decision, color=color)
        bottom += np.array(values)
    axes[0].set_ylabel("Fixture count")
    axes[0].set_title("The same inputs produce profile-specific decisions")
    axes[0].tick_params(axis="x", rotation=25)
    axes[0].legend()
    axes[0].grid(axis="y", alpha=0.25)

    stages = ("resource", "coverage", "opacity", "integrity", "retention")
    stage_counts = [
        sum(row["decisive_stage"] == stage for row in observations)
        for stage in stages
    ]
    axes[1].barh(stages, stage_counts, color=("#264653", "#2a9d8f", "#8d99ae", "#f4a261", "#457b9d"))
    axes[1].set_xlabel("Terminal decisions")
    axes[1].set_title("First decisive stage remains attributable")
    axes[1].grid(axis="x", alpha=0.25)
    figure.suptitle(
        "Explainable JPEG Metadata Policy Composition",
        fontsize=14,
        fontweight="bold",
    )
    figure.text(
        0.5,
        0.012,
        "Profiles are study policies, not universal production recommendations.",
        ha="center",
        fontsize=9,
    )
    figure.tight_layout(rect=(0, 0.04, 1, 0.96))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Evaluate explainable JPEG metadata policy composition."
    )
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument("--platform-label", default="local-reference")
    parser.add_argument("--record-runner-image", action="store_true")
    return parser.parse_args()


def main() -> None:
    """Run the controlled experiment and write deterministic artifacts."""
    args = parse_args()
    observations = collect_observations(args.platform_label)
    summary = summarize(observations)
    manifest = build_runtime_manifest(
        args.platform_label, record_runner_image=args.record_runner_image
    )
    write_csv(args.output_dir / MANIFEST_NAME, manifest, tuple(manifest[0]))
    write_csv(
        args.output_dir / OBSERVATIONS_NAME,
        observations,
        OBSERVATION_FIELDS,
    )
    write_csv(args.output_dir / SUMMARY_NAME, summary, SUMMARY_FIELDS)
    plot_results(observations, args.output_dir / FIGURE_NAME)
    print(
        f"Wrote {len(observations)} policy-composition observations and "
        f"{len(summary)} profile summaries to {args.output_dir}"
    )


if __name__ == "__main__":
    main()
