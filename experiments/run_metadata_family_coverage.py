"""Evaluate controlled JPEG metadata-family and relationship coverage."""

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
    build_metadata_coverage_fixtures,
    encode_jpeg_pillow,
    inspect_jpeg_metadata_coverage,
)


MANIFEST_NAME = "jpeg_metadata_coverage_runtime_manifest.csv"
OBSERVATIONS_NAME = "jpeg_metadata_coverage_observations.csv"
SUMMARY_NAME = "jpeg_metadata_coverage_summary.csv"
FIGURE_NAME = "jpeg_metadata_coverage.png"

COUNTER_FIELDS = (
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

OBSERVATION_FIELDS = (
    "platform_label",
    "fixture",
    "family",
    "condition",
    "expected_decision",
    "observed_decision",
    "expectation_met",
    "expected_reason_code",
    "reason_code",
    "resource_decision",
    "resource_reason_code",
    "families",
    "relationship_completion_rate",
    "fixture_bytes",
    "fixture_sha256",
    *COUNTER_FIELDS,
)

SUMMARY_FIELDS = (
    "family",
    "fixtures",
    "accept_count",
    "quarantine_count",
    "reject_count",
    "expectation_rate",
    "recognized_components",
    "opaque_components",
    "relationships_declared",
    "relationships_resolved",
    "relationship_completion_rate",
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
    """Record the parser, resource gate, and synthetic fixture encoder."""
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
            "metadata_coverage_parser",
            "relationship_parser",
            "research-notes",
            "0.18.0",
            "controlled EXIF, XMP, IPTC IIM, and opaque maker-note coverage",
        ),
        (
            "resource_admission_gate",
            "precondition",
            "research-notes",
            "0.17.0",
            "default metadata resource budget",
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


def collect_observations(platform_label: str) -> list[dict[str, str]]:
    """Inspect all controlled metadata-family fixtures."""
    base_jpeg = encode_jpeg_pillow(
        make_base_image(), quality=75, chroma_sampling="444"
    )
    observations: list[dict[str, str]] = []
    for fixture in build_metadata_coverage_fixtures(base_jpeg):
        result = inspect_jpeg_metadata_coverage(fixture.jpeg_bytes)
        row = {
            "platform_label": platform_label,
            "fixture": fixture.fixture,
            "family": fixture.family,
            "condition": fixture.condition,
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
            "resource_decision": result.resource_decision,
            "resource_reason_code": result.resource_reason_code,
            "families": "|".join(result.families),
            "relationship_completion_rate": (
                f"{result.relationship_completion_rate:.6f}"
            ),
            "fixture_bytes": str(len(fixture.jpeg_bytes)),
            "fixture_sha256": hashlib.sha256(fixture.jpeg_bytes).hexdigest(),
        }
        row.update(
            {field: str(getattr(result, field)) for field in COUNTER_FIELDS}
        )
        observations.append(row)
    validate_observations(observations)
    return observations


def validate_observations(
    observations: Sequence[dict[str, str]],
) -> None:
    """Enforce fixture expectations and relationship invariants."""
    if len(observations) != 15:
        raise RuntimeError("expected 15 metadata-coverage observations")
    if any(row["expectation_met"] != "1" for row in observations):
        raise RuntimeError("a metadata-coverage expectation failed")
    accepted = [
        row for row in observations if row["observed_decision"] == "accept"
    ]
    if any(
        row["relationships_declared"] != row["relationships_resolved"]
        for row in accepted
    ):
        raise RuntimeError("an accepted fixture has an unresolved relationship")
    maker = next(
        row for row in observations if row["fixture"] == "maker_note_opaque"
    )
    if maker["opaque_components"] != "1":
        raise RuntimeError("the maker note was not retained as opaque")
    ordered = next(
        row
        for row in observations
        if row["fixture"] == "extended_xmp_in_order"
    )
    reordered = next(
        row
        for row in observations
        if row["fixture"] == "extended_xmp_out_of_order"
    )
    if ordered["extended_xmp_bytes"] != reordered["extended_xmp_bytes"]:
        raise RuntimeError("Extended XMP reconstruction depends on chunk order")


def summarize(
    observations: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Aggregate controlled outcomes by primary metadata family."""
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in observations:
        grouped[row["family"]].append(row)
    summary = []
    for family in sorted(grouped):
        rows = grouped[family]
        declared = sum(int(row["relationships_declared"]) for row in rows)
        resolved = sum(int(row["relationships_resolved"]) for row in rows)
        summary.append(
            {
                "family": family,
                "fixtures": str(len(rows)),
                "accept_count": str(
                    sum(row["observed_decision"] == "accept" for row in rows)
                ),
                "quarantine_count": str(
                    sum(
                        row["observed_decision"] == "quarantine"
                        for row in rows
                    )
                ),
                "reject_count": str(
                    sum(row["observed_decision"] == "reject" for row in rows)
                ),
                "expectation_rate": (
                    f"{sum(int(row['expectation_met']) for row in rows) / len(rows):.6f}"
                ),
                "recognized_components": str(
                    sum(int(row["recognized_components"]) for row in rows)
                ),
                "opaque_components": str(
                    sum(int(row["opaque_components"]) for row in rows)
                ),
                "relationships_declared": str(declared),
                "relationships_resolved": str(resolved),
                "relationship_completion_rate": (
                    f"{resolved / declared:.6f}" if declared else "1.000000"
                ),
            }
        )
    return summary


def plot_results(
    observations: Sequence[dict[str, str]], output_path: Path
) -> None:
    """Visualize decisions and relationship resolution by fixture."""
    families = sorted({row["family"] for row in observations})
    decisions = ("accept", "quarantine", "reject")
    colors = {"accept": "#2a9d8f", "quarantine": "#e9c46a", "reject": "#e76f51"}
    figure, axes = plt.subplots(1, 2, figsize=(14, 7.2))
    bottom = np.zeros(len(families))
    for decision in decisions:
        counts = [
            sum(
                row["family"] == family
                and row["observed_decision"] == decision
                for row in observations
            )
            for family in families
        ]
        axes[0].bar(families, counts, bottom=bottom, label=decision, color=colors[decision])
        bottom += np.array(counts)
    axes[0].set_ylabel("Fixture count")
    axes[0].set_title("Known relationship failures route to quarantine")
    axes[0].tick_params(axis="x", rotation=38)
    axes[0].legend()
    axes[0].grid(axis="y", alpha=0.25)

    relation_rows = [
        row for row in observations if int(row["relationships_declared"]) > 0
    ]
    y = np.arange(len(relation_rows))
    declared = [int(row["relationships_declared"]) for row in relation_rows]
    resolved = [int(row["relationships_resolved"]) for row in relation_rows]
    axes[1].barh(y, declared, color="#d9d9d9", label="declared")
    axes[1].barh(y, resolved, color="#457b9d", label="resolved")
    axes[1].set_yticks(y, [row["fixture"] for row in relation_rows])
    axes[1].set_xlabel("Relationship count")
    axes[1].set_title("Accepted fixtures resolve every declared relation")
    axes[1].legend()
    axes[1].grid(axis="x", alpha=0.25)
    figure.suptitle(
        "Controlled JPEG Metadata-Family Coverage",
        fontsize=14,
        fontweight="bold",
    )
    figure.text(
        0.5,
        0.012,
        "Recognition is bounded to the synthetic corpus; maker-note bytes remain opaque.",
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
        description="Evaluate controlled JPEG metadata-family coverage."
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
        f"Wrote {len(observations)} metadata-coverage observations and "
        f"{len(summary)} family summaries to {args.output_dir}"
    )


if __name__ == "__main__":
    main()
