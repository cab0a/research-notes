"""Evaluate resource-bounded JPEG metadata parsing and quarantine decisions."""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import platform
import sys
import xml.parsers.expat as pyexpat
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
    DEFAULT_JPEG_METADATA_RESOURCE_BUDGET,
    JPEGMetadataBoundaryResult,
    JPEGMetadataResourceBudget,
    audit_jpeg_metadata_resources,
    boundary_limit_value,
    boundary_observed_and_admitted,
    build_resource_boundary_fixtures,
    encode_jpeg_pillow,
)


QUALITY = 75
CHROMA_SAMPLING = "444"

MANIFEST_NAME = "jpeg_resource_budget_runtime_manifest.csv"
OBSERVATIONS_NAME = "jpeg_resource_budget_observations.csv"
SUMMARY_NAME = "jpeg_resource_budget_summary.csv"
FIGURE_NAME = "jpeg_resource_budget_boundaries.png"

COUNTER_FIELDS = (
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

OBSERVATION_FIELDS = (
    "platform_label",
    "fixture",
    "resource_family",
    "boundary_relation",
    "expected_decision",
    "observed_decision",
    "expectation_met",
    "expected_reason_code",
    "reason_code",
    "issue_codes",
    "header_scan_complete",
    "image_data_reached",
    "fixture_bytes",
    "fixture_sha256",
    "limit_value",
    "observed_value",
    "admitted_value",
    "observed_to_limit",
    "admitted_to_limit",
    *COUNTER_FIELDS,
)

SUMMARY_FIELDS = (
    "resource_family",
    "fixtures",
    "accept_count",
    "quarantine_count",
    "reject_count",
    "expectation_rate",
    "at_limit_decision",
    "over_limit_decision",
    "maximum_observed_to_limit",
    "maximum_admitted_to_limit",
)


def bytes_sha256(payload: bytes) -> str:
    """Return the SHA-256 digest of one byte string."""
    return hashlib.sha256(payload).hexdigest()


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
            handle,
            fieldnames=list(fieldnames),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def pillow_jpeg_backend() -> str:
    """Return the JPEG backend reported by Pillow."""
    turbo_version = features.version_feature("libjpeg_turbo")
    if turbo_version is not None:
        codec_name = (
            "mozjpeg"
            if features.check_feature("mozjpeg")
            else "libjpeg-turbo"
        )
        return f"{codec_name} {turbo_version}"
    jpeg_version = features.version_codec("jpg")
    if jpeg_version is None:
        raise RuntimeError("Pillow does not report a JPEG codec")
    return f"libjpeg {jpeg_version}"


def build_runtime_manifest(
    platform_label: str, *, record_runner_image: bool = False
) -> list[dict[str, str]]:
    """Record the bounded auditor, XML parser, and fixture encoder."""
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
            "resource_boundary_auditor",
            "admission_policy",
            "research-notes",
            "0.17.0",
            "bounded marker and metadata work counters",
        ),
        (
            "xml_pull_parser",
            "metadata_parser",
            "Python ElementTree",
            pyexpat.EXPAT_VERSION,
            "64-byte feed chunks after packet-size admission",
        ),
        (
            "fixture_encoder",
            "image_encoder",
            f"Pillow {PIL.__version__}",
            pillow_jpeg_backend(),
            f"quality {QUALITY}; chroma {CHROMA_SAMPLING}",
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


def collect_observations(
    platform_label: str,
    budget: JPEGMetadataResourceBudget = (
        DEFAULT_JPEG_METADATA_RESOURCE_BUDGET
    ),
) -> list[dict[str, str]]:
    """Audit all controlled boundary fixtures without calling a decoder."""
    base_jpeg = encode_jpeg_pillow(
        make_base_image(),
        quality=QUALITY,
        chroma_sampling=CHROMA_SAMPLING,
    )
    observations: list[dict[str, str]] = []
    for fixture in build_resource_boundary_fixtures(base_jpeg, budget):
        result = audit_jpeg_metadata_resources(
            fixture.jpeg_bytes, budget
        )
        observed, admitted = boundary_observed_and_admitted(
            result, fixture.resource_family
        )
        limit = boundary_limit_value(budget, fixture.resource_family)
        row = {
            "platform_label": platform_label,
            "fixture": fixture.fixture,
            "resource_family": fixture.resource_family,
            "boundary_relation": fixture.boundary_relation,
            "expected_decision": fixture.expected_decision,
            "observed_decision": result.decision,
            "expectation_met": str(
                int(
                    result.decision == fixture.expected_decision
                    and result.reason_code == fixture.expected_reason_code
                )
            ),
            "expected_reason_code": fixture.expected_reason_code,
            "reason_code": result.reason_code,
            "issue_codes": "|".join(result.issue_codes),
            "header_scan_complete": str(
                int(result.header_scan_complete)
            ),
            "image_data_reached": str(int(result.image_data_reached)),
            "fixture_bytes": str(len(fixture.jpeg_bytes)),
            "fixture_sha256": bytes_sha256(fixture.jpeg_bytes),
            "limit_value": str(limit) if limit else "",
            "observed_value": str(observed) if limit else "",
            "admitted_value": str(admitted) if limit else "",
            "observed_to_limit": (
                f"{observed / limit:.6f}" if limit else ""
            ),
            "admitted_to_limit": (
                f"{admitted / limit:.6f}" if limit else ""
            ),
        }
        row.update(_counter_row(result))
        observations.append(row)
    validate_observations(observations, budget)
    return observations


def _counter_row(
    result: JPEGMetadataBoundaryResult,
) -> dict[str, str]:
    """Serialize all deterministic work counters."""
    return {
        field: str(getattr(result, field)) for field in COUNTER_FIELDS
    }


def validate_observations(
    observations: Sequence[dict[str, str]],
    budget: JPEGMetadataResourceBudget,
) -> None:
    """Enforce the controlled expectations and admitted-work ceilings."""
    if len(observations) != 24:
        raise RuntimeError("expected 24 resource-boundary observations")
    if any(row["expectation_met"] != "1" for row in observations):
        raise RuntimeError("a resource-boundary expectation failed")
    paired = [
        row
        for row in observations
        if row["boundary_relation"] in ("at_limit", "over_limit")
    ]
    if len(paired) != 20:
        raise RuntimeError("expected ten paired boundary dimensions")
    for row in paired:
        limit = int(row["limit_value"])
        observed = int(row["observed_value"])
        admitted = int(row["admitted_value"])
        if row["boundary_relation"] == "at_limit":
            if not observed == admitted == limit:
                raise RuntimeError(
                    f"{row['fixture']} did not land exactly on its limit"
                )
        elif not (observed > limit and admitted <= limit):
            raise RuntimeError(
                f"{row['fixture']} did not fail closed above its limit"
            )
        elif observed != limit + 1:
            raise RuntimeError(
                f"{row['fixture']} did not stop at the first disallowed value"
            )
    ceiling_fields = {
        "header_segments_admitted": budget.max_header_segments,
        "metadata_segments_admitted": budget.max_metadata_segments,
        "metadata_bytes_admitted": budget.max_metadata_bytes,
        "largest_metadata_segment_admitted": (
            budget.max_single_metadata_segment_bytes
        ),
        "exif_entries_admitted": budget.max_exif_entries,
        "xmp_packet_bytes_admitted": budget.max_xmp_packet_bytes,
        "xmp_nodes_admitted": budget.max_xmp_nodes,
        "xmp_depth_admitted": budget.max_xmp_depth,
        "xmp_text_bytes_admitted": budget.max_xmp_text_bytes,
        "icc_chunks_admitted": budget.max_icc_chunks,
    }
    for row in observations:
        for field, ceiling in ceiling_fields.items():
            if int(row[field]) > ceiling:
                raise RuntimeError(
                    f"{row['fixture']} exceeded admitted {field}"
                )


def summarize(
    observations: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Aggregate routing decisions by resource family."""
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in observations:
        grouped[row["resource_family"]].append(row)

    summary: list[dict[str, str]] = []
    for family in sorted(grouped):
        rows = grouped[family]
        ratios = [
            float(row["observed_to_limit"])
            for row in rows
            if row["observed_to_limit"]
        ]
        admitted_ratios = [
            float(row["admitted_to_limit"])
            for row in rows
            if row["admitted_to_limit"]
        ]
        relation_decisions = {
            row["boundary_relation"]: row["observed_decision"]
            for row in rows
        }
        summary.append(
            {
                "resource_family": family,
                "fixtures": str(len(rows)),
                "accept_count": str(
                    sum(
                        row["observed_decision"] == "accept"
                        for row in rows
                    )
                ),
                "quarantine_count": str(
                    sum(
                        row["observed_decision"] == "quarantine"
                        for row in rows
                    )
                ),
                "reject_count": str(
                    sum(
                        row["observed_decision"] == "reject"
                        for row in rows
                    )
                ),
                "expectation_rate": _rate(rows, "expectation_met"),
                "at_limit_decision": relation_decisions.get(
                    "at_limit", ""
                ),
                "over_limit_decision": relation_decisions.get(
                    "over_limit", ""
                ),
                "maximum_observed_to_limit": (
                    f"{max(ratios):.6f}" if ratios else ""
                ),
                "maximum_admitted_to_limit": (
                    f"{max(admitted_ratios):.6f}"
                    if admitted_ratios
                    else ""
                ),
            }
        )
    return summary


def _rate(rows: Sequence[dict[str, str]], field: str) -> str:
    """Return a deterministic binary rate."""
    return f"{sum(int(row[field]) for row in rows) / len(rows):.6f}"


def plot_results(
    observations: Sequence[dict[str, str]], output_path: Path
) -> None:
    """Visualize boundary routing and admitted-work ceilings."""
    paired_families = sorted(
        {
            row["resource_family"]
            for row in observations
            if row["boundary_relation"] == "at_limit"
        }
    )
    by_key = {
        (row["resource_family"], row["boundary_relation"]): row
        for row in observations
    }
    y = np.arange(len(paired_families))
    at_observed = [
        float(by_key[(family, "at_limit")]["observed_to_limit"])
        for family in paired_families
    ]
    over_observed = [
        float(by_key[(family, "over_limit")]["observed_to_limit"])
        for family in paired_families
    ]
    over_admitted = [
        float(by_key[(family, "over_limit")]["admitted_to_limit"])
        for family in paired_families
    ]

    figure, axes = plt.subplots(1, 2, figsize=(13.5, 6.8))
    axes[0].scatter(
        at_observed,
        y - 0.14,
        color="#2a9d8f",
        label="At limit: accept",
        s=55,
    )
    axes[0].scatter(
        over_observed,
        y + 0.14,
        color="#e76f51",
        label="Over limit: quarantine",
        s=55,
    )
    axes[0].axvline(1.0, color="#264653", linestyle="--", linewidth=1)
    axes[0].set_yticks(y, paired_families)
    axes[0].set_xlabel("Observed value / declared limit")
    axes[0].set_title("Routing changes immediately above each boundary")
    axes[0].legend(loc="lower right")
    axes[0].grid(axis="x", alpha=0.25)

    axes[1].barh(
        y,
        over_admitted,
        color="#457b9d",
        height=0.58,
    )
    axes[1].scatter(
        over_admitted,
        y,
        color="#264653",
        s=32,
        zorder=3,
    )
    axes[1].axvline(1.0, color="#264653", linestyle="--", linewidth=1)
    axes[1].set_yticks(y, paired_families)
    axes[1].set_xlim(0, 1.05)
    axes[1].set_xlabel("Admitted counter / declared limit")
    axes[1].set_title("Values admitted past the boundary stay within limits")
    axes[1].grid(axis="x", alpha=0.25)

    figure.suptitle(
        "Resource-Bounded JPEG Metadata Admission",
        fontsize=14,
        fontweight="bold",
    )
    figure.text(
        0.5,
        0.015,
        (
            "Counters are control-flow evidence, not direct measurements of "
            "decoder memory, CPU time, or exploitability."
        ),
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
        description=(
            "Evaluate resource-bounded JPEG metadata admission decisions."
        )
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results"),
        help="Directory for generated CSV and PNG artifacts.",
    )
    parser.add_argument(
        "--platform-label",
        default="local-reference",
        help="Stable label recorded in observation rows.",
    )
    parser.add_argument(
        "--record-runner-image",
        action="store_true",
        help="Record hosted-runner identifiers in the runtime manifest.",
    )
    return parser.parse_args()


def main() -> None:
    """Run the controlled experiment and write deterministic artifacts."""
    args = parse_args()
    budget = DEFAULT_JPEG_METADATA_RESOURCE_BUDGET
    observations = collect_observations(args.platform_label, budget)
    summary = summarize(observations)
    manifest = build_runtime_manifest(
        args.platform_label,
        record_runner_image=args.record_runner_image,
    )
    write_csv(
        args.output_dir / MANIFEST_NAME,
        manifest,
        tuple(manifest[0]),
    )
    write_csv(
        args.output_dir / OBSERVATIONS_NAME,
        observations,
        OBSERVATION_FIELDS,
    )
    write_csv(
        args.output_dir / SUMMARY_NAME,
        summary,
        SUMMARY_FIELDS,
    )
    plot_results(observations, args.output_dir / FIGURE_NAME)
    print(
        "Wrote "
        f"{len(observations)} resource-boundary observations and "
        f"{len(summary)} family summaries to {args.output_dir}"
    )


if __name__ == "__main__":
    main()
