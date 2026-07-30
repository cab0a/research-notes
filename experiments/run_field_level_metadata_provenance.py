"""Evaluate field-level JPEG metadata provenance and selective retention."""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import platform
import sys
from collections import defaultdict
from collections.abc import Callable, Sequence
from pathlib import Path

import cv2
import matplotlib
import numpy as np
import PIL
from numpy.typing import NDArray
from PIL import features

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

from research_notes import (  # noqa: E402
    FIELD_CATEGORIES,
    FIELD_ORDER,
    JPEG_SELECTIVE_RETENTION_POLICIES,
    apply_selective_metadata_policy,
    audit_jpeg_metadata,
    build_controlled_metadata_fixture,
    build_synthetic_rgb_profile,
    compare_decoded_pixels,
    decode_jpeg_pillow,
    encode_jpeg_opencv,
    encode_jpeg_pillow,
    extract_controlled_metadata_fields,
    metadata_state_sha256,
    pixel_array_sha256,
    strip_controlled_metadata,
)


QUALITY = 75
CHROMA_SAMPLING = "444"
ENCODERS = ("pillow", "opencv")
FIXTURES = ("canonical_order", "reordered_equivalent")

PLATFORM_MANIFEST_NAME = "jpeg_field_provenance_codec_manifest.csv"
DECISIONS_NAME = "jpeg_field_provenance_decisions.csv"
OBSERVATIONS_NAME = "jpeg_selective_retention_observations.csv"
SUMMARY_NAME = "jpeg_selective_retention_summary.csv"
FIGURE_NAME = "jpeg_selective_retention.png"

DECISION_FIELDS = (
    "platform_label",
    "fixture_id",
    "encoder",
    "policy",
    "field_id",
    "category",
    "container",
    "source_ordinal",
    "source_value_bytes",
    "source_value_sha256",
    "retained",
    "reason",
    "output_value_sha256",
    "semantic_value_exact",
)

OBSERVATION_FIELDS = (
    "platform_label",
    "fixture_id",
    "encoder",
    "policy",
    "source_sha256",
    "source_metadata_sha256",
    "source_field_count",
    "retained_field_count",
    "removed_field_count",
    "location_field_count",
    "retained_location_field_count",
    "unclassified_field_count",
    "retained_unclassified_field_count",
    "output_strict_accept",
    "output_issue_codes",
    "metadata_core_exact",
    "pixels_exact_to_reencode_control",
    "equivalent_layout_output_exact",
    "output_metadata_sha256",
    "output_size_bytes",
    "output_sha256",
    "output_bgr_sha256",
    "error_category",
)

SUMMARY_FIELDS = (
    "encoder",
    "policy",
    "observations",
    "source_fields",
    "retained_fields",
    "removed_fields",
    "retained_fraction",
    "retained_location_fields",
    "retained_unclassified_fields",
    "strict_accept_rate",
    "metadata_core_exact_rate",
    "pixel_exact_rate",
    "layout_output_hash_count",
    "metadata_state_hash_count",
)


def bytes_sha256(payload: bytes) -> str:
    """Return the SHA-256 digest of one byte string."""
    return hashlib.sha256(payload).hexdigest()


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


def opencv_jpeg_backend() -> str:
    """Return the JPEG backend line reported by OpenCV."""
    matches = [
        line.strip()
        for line in cv2.getBuildInformation().splitlines()
        if line.strip().startswith("JPEG:")
    ]
    if len(matches) != 1:
        raise RuntimeError("Could not identify the OpenCV JPEG backend")
    return matches[0].split(":", maxsplit=1)[1].strip()


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


def build_platform_manifest(
    platform_label: str, *, record_runner_image: bool = False
) -> list[dict[str, str]]:
    """Record policy, parser, decoder, and encoder provenance."""
    common = {
        "platform_label": platform_label,
        "operating_system": platform.system(),
        "architecture": platform.machine().lower(),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
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
        "libjpeg_simd_policy": (
            "forced_scalar"
            if os.environ.get("JSIMD_FORCENONE") == "1"
            else "runtime_default"
        ),
    }
    pillow_backend = pillow_jpeg_backend()
    opencv_backend = opencv_jpeg_backend()
    definitions = (
        (
            "field_policy_engine",
            "policy",
            "research-notes",
            "0.16.0",
            "bounded_python_policy",
            "explicit field allowlists and category denylist",
        ),
        (
            "controlled_field_parser",
            "metadata_parser",
            "research-notes",
            "0.16.0",
            "bounded_python_parser",
            "EXIF, XMP, ICC, COM, and controlled APP13",
        ),
        (
            "pillow_raw",
            "decoder",
            "Pillow",
            PIL.__version__,
            "libjpeg-turbo",
            pillow_backend,
        ),
        (
            "pillow",
            "encoder",
            "Pillow",
            PIL.__version__,
            "libjpeg-turbo",
            pillow_backend,
        ),
        (
            "opencv",
            "encoder",
            "OpenCV",
            cv2.__version__,
            "libjpeg-turbo",
            opencv_backend,
        ),
    )
    return [
        {
            **common,
            "component": component,
            "component_role": role,
            "adapter": adapter,
            "adapter_version": version,
            "implementation_family": family,
            "reported_backend": backend,
            "build_fingerprint": bytes_sha256(
                f"{adapter}|{version}|{backend}".encode("utf-8")
            ),
        }
        for component, role, adapter, version, family, backend in definitions
    ]


def make_base_image() -> NDArray[np.uint8]:
    """Return one deterministic synthetic BGR image."""
    rows, columns = np.indices((80, 112))
    return np.stack(
        (
            (columns * 3 + rows) % 256,
            (rows * 5 + columns // 2) % 256,
            ((rows + columns) * 2) % 256,
        ),
        axis=2,
    ).astype(np.uint8)


def build_fixtures() -> dict[str, bytes]:
    """Build two byte-distinct sources with equivalent normalized fields."""
    base = encode_jpeg_pillow(
        make_base_image(),
        quality=QUALITY,
        chroma_sampling=CHROMA_SAMPLING,
    )
    profile = build_synthetic_rgb_profile(2.2)
    fixtures = {
        fixture_id: build_controlled_metadata_fixture(
            base,
            icc_profile=profile,
            variant=fixture_id,  # type: ignore[arg-type]
        )
        for fixture_id in FIXTURES
    }
    if fixtures[FIXTURES[0]] == fixtures[FIXTURES[1]]:
        raise RuntimeError("controlled metadata layouts must be byte-distinct")
    normalized_states = {
        metadata_state_sha256(payload) for payload in fixtures.values()
    }
    if len(normalized_states) != 1:
        raise RuntimeError("controlled layouts must have equivalent fields")
    if any(
        len(extract_controlled_metadata_fields(payload)) != len(FIELD_ORDER)
        for payload in fixtures.values()
    ):
        raise RuntimeError("controlled fixture field count changed")
    if any(not audit_jpeg_metadata(payload).accepted for payload in fixtures.values()):
        raise RuntimeError("a controlled source failed the strict audit")
    return fixtures


def encode_image(encoder: str, image: NDArray[np.uint8]) -> bytes:
    """Encode one raw BGR array under fixed JPEG controls."""
    adapters: dict[str, Callable[[NDArray[np.uint8]], bytes]] = {
        "pillow": lambda value: encode_jpeg_pillow(
            value, quality=QUALITY, chroma_sampling=CHROMA_SAMPLING
        ),
        "opencv": lambda value: encode_jpeg_opencv(
            value, quality=QUALITY, chroma_sampling=CHROMA_SAMPLING
        ),
    }
    return adapters[encoder](image)


def collect_observations(
    platform_label: str,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Run two layouts through two encoders and six field policies."""
    fixtures = build_fixtures()
    observations: list[dict[str, str]] = []
    decisions: list[dict[str, str]] = []
    for fixture_id in FIXTURES:
        source = fixtures[fixture_id]
        source_fields = extract_controlled_metadata_fields(source)
        source_pixels = decode_jpeg_pillow(source)
        location_count = sum(
            field.category == "location" for field in source_fields
        )
        unclassified_count = sum(
            field.category == "unclassified" for field in source_fields
        )
        for encoder in ENCODERS:
            reencoded = encode_image(encoder, source_pixels)
            reencode_control = decode_jpeg_pillow(reencoded)
            for policy in JPEG_SELECTIVE_RETENTION_POLICIES:
                result = apply_selective_metadata_policy(
                    source,
                    reencoded,
                    policy,
                )
                output = result.output_bytes
                output_audit = audit_jpeg_metadata(output)
                output_pixels = decode_jpeg_pillow(output)
                difference = compare_decoded_pixels(
                    reencode_control, output_pixels
                )
                retained_location = sum(
                    decision.retained and decision.category == "location"
                    for decision in result.decisions
                )
                retained_unclassified = sum(
                    decision.retained
                    and decision.category == "unclassified"
                    for decision in result.decisions
                )
                observations.append(
                    {
                        "platform_label": platform_label,
                        "fixture_id": fixture_id,
                        "encoder": encoder,
                        "policy": policy,
                        "source_sha256": bytes_sha256(source),
                        "source_metadata_sha256": metadata_state_sha256(source),
                        "source_field_count": str(len(source_fields)),
                        "retained_field_count": str(
                            result.retained_field_count
                        ),
                        "removed_field_count": str(
                            len(source_fields) - result.retained_field_count
                        ),
                        "location_field_count": str(location_count),
                        "retained_location_field_count": str(
                            retained_location
                        ),
                        "unclassified_field_count": str(
                            unclassified_count
                        ),
                        "retained_unclassified_field_count": str(
                            retained_unclassified
                        ),
                        "output_strict_accept": str(
                            int(output_audit.accepted)
                        ),
                        "output_issue_codes": (
                            "|".join(output_audit.issue_codes)
                            if output_audit.issue_codes
                            else "none"
                        ),
                        "metadata_core_exact": str(
                            int(strip_controlled_metadata(output) == reencoded)
                        ),
                        "pixels_exact_to_reencode_control": str(
                            int(difference.exact)
                        ),
                        "equivalent_layout_output_exact": "",
                        "output_metadata_sha256": metadata_state_sha256(output),
                        "output_size_bytes": str(len(output)),
                        "output_sha256": bytes_sha256(output),
                        "output_bgr_sha256": pixel_array_sha256(output_pixels),
                        "error_category": "none",
                    }
                )
                decisions.extend(
                    {
                        "platform_label": platform_label,
                        "fixture_id": fixture_id,
                        "encoder": encoder,
                        "policy": policy,
                        "field_id": decision.field_id,
                        "category": decision.category,
                        "container": decision.container,
                        "source_ordinal": str(decision.source_ordinal),
                        "source_value_bytes": str(
                            decision.source_value_bytes
                        ),
                        "source_value_sha256": (
                            decision.source_value_sha256
                        ),
                        "retained": str(int(decision.retained)),
                        "reason": decision.reason,
                        "output_value_sha256": (
                            decision.output_value_sha256
                        ),
                        "semantic_value_exact": str(
                            int(decision.semantic_value_exact)
                        ),
                    }
                    for decision in result.decisions
                )

    hashes: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in observations:
        hashes[(row["encoder"], row["policy"])].add(row["output_sha256"])
    for row in observations:
        row["equivalent_layout_output_exact"] = str(
            int(len(hashes[(row["encoder"], row["policy"])]) == 1)
        )
    validate_results(observations, decisions)
    return observations, decisions


def validate_results(
    observations: Sequence[dict[str, str]],
    decisions: Sequence[dict[str, str]],
) -> None:
    """Validate field, image, and provenance contracts."""
    expected_observations = (
        len(FIXTURES) * len(ENCODERS) * len(JPEG_SELECTIVE_RETENTION_POLICIES)
    )
    if len(observations) != expected_observations:
        raise RuntimeError("unexpected selective-retention observation count")
    if len(decisions) != expected_observations * len(FIELD_ORDER):
        raise RuntimeError("unexpected field decision count")
    if any(row["output_strict_accept"] != "1" for row in observations):
        raise RuntimeError("a selective policy emitted rejected metadata")
    if any(row["metadata_core_exact"] != "1" for row in observations):
        raise RuntimeError("a selective policy changed compressed image data")
    if any(
        row["pixels_exact_to_reencode_control"] != "1"
        for row in observations
    ):
        raise RuntimeError("a selective policy changed decoded pixels")
    if any(
        row["equivalent_layout_output_exact"] != "1"
        for row in observations
    ):
        raise RuntimeError("equivalent field layouts produced different outputs")
    if any(
        row["retained"] == "1" and row["semantic_value_exact"] != "1"
        for row in decisions
    ):
        raise RuntimeError("a retained field changed normalized value")
    if any(
        row["retained"] == "0" and row["output_value_sha256"]
        for row in decisions
    ):
        raise RuntimeError("a removed field remained in the output")

    denylist = [
        row
        for row in decisions
        if row["policy"] == "drop_location_denylist"
    ]
    if any(
        (row["category"] == "location") == (row["retained"] == "1")
        for row in denylist
    ):
        raise RuntimeError("location denylist violated its category contract")
    if any(
        row["retained"] != "1"
        for row in denylist
        if row["category"] == "unclassified"
    ):
        raise RuntimeError("denylist no longer exposes unclassified retention")


def summarize(
    observations: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Aggregate results by encoder and policy."""
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in observations:
        groups[(row["encoder"], row["policy"])].append(row)
    rows: list[dict[str, str]] = []
    for encoder in ENCODERS:
        for policy in JPEG_SELECTIVE_RETENTION_POLICIES:
            group = groups[(encoder, policy)]
            source_fields = sum(int(row["source_field_count"]) for row in group)
            retained = sum(int(row["retained_field_count"]) for row in group)
            removed = sum(int(row["removed_field_count"]) for row in group)
            rows.append(
                {
                    "encoder": encoder,
                    "policy": policy,
                    "observations": str(len(group)),
                    "source_fields": str(source_fields),
                    "retained_fields": str(retained),
                    "removed_fields": str(removed),
                    "retained_fraction": f"{retained / source_fields:.9f}",
                    "retained_location_fields": str(
                        sum(
                            int(row["retained_location_field_count"])
                            for row in group
                        )
                    ),
                    "retained_unclassified_fields": str(
                        sum(
                            int(row["retained_unclassified_field_count"])
                            for row in group
                        )
                    ),
                    "strict_accept_rate": _rate(
                        group, "output_strict_accept"
                    ),
                    "metadata_core_exact_rate": _rate(
                        group, "metadata_core_exact"
                    ),
                    "pixel_exact_rate": _rate(
                        group, "pixels_exact_to_reencode_control"
                    ),
                    "layout_output_hash_count": str(
                        len({row["output_sha256"] for row in group})
                    ),
                    "metadata_state_hash_count": str(
                        len(
                            {
                                row["output_metadata_sha256"]
                                for row in group
                            }
                        )
                    ),
                }
            )
    return rows


def _rate(rows: Sequence[dict[str, str]], field: str) -> str:
    """Return a nine-decimal binary rate."""
    return f"{sum(int(row[field]) for row in rows) / len(rows):.9f}"


def plot_results(
    decisions: Sequence[dict[str, str]],
    output_path: Path,
) -> None:
    """Plot retained field counts and category retention by policy."""
    policy_labels = {
        "retain_all": "Retain all",
        "drop_location_denylist": "Drop location\ndenylist",
        "allow_visual_context": "Visual\nallowlist",
        "allow_catalog": "Catalog\nallowlist",
        "allow_attribution": "Attribution\nallowlist",
        "strip_all": "Strip all",
    }
    categories = (
        "interpretation",
        "descriptive",
        "attribution",
        "temporal",
        "location",
        "unclassified",
    )
    unique = [
        row
        for row in decisions
        if row["fixture_id"] == FIXTURES[0]
        and row["encoder"] == ENCODERS[0]
    ]
    counts = [
        sum(
            row["retained"] == "1"
            for row in unique
            if row["policy"] == policy
        )
        for policy in JPEG_SELECTIVE_RETENTION_POLICIES
    ]
    matrix = np.zeros(
        (len(categories), len(JPEG_SELECTIVE_RETENTION_POLICIES)),
        dtype=np.float64,
    )
    for category_index, category in enumerate(categories):
        for policy_index, policy in enumerate(
            JPEG_SELECTIVE_RETENTION_POLICIES
        ):
            category_rows = [
                row
                for row in unique
                if row["category"] == category and row["policy"] == policy
            ]
            matrix[category_index, policy_index] = (
                sum(row["retained"] == "1" for row in category_rows)
                / len(category_rows)
            )

    figure, axes = plt.subplots(1, 2, figsize=(13.5, 5.2))
    positions = np.arange(len(JPEG_SELECTIVE_RETENTION_POLICIES))
    axes[0].bar(positions, counts, color="#376996")
    axes[0].set_xticks(
        positions,
        [
            policy_labels[policy]
            for policy in JPEG_SELECTIVE_RETENTION_POLICIES
        ],
        rotation=20,
        ha="right",
    )
    axes[0].set_ylim(0, len(FIELD_ORDER) + 1)
    axes[0].set_ylabel("Retained fields")
    axes[0].set_title("Explicit policies retain different field sets")
    axes[0].grid(axis="y", alpha=0.25)
    for position, count in zip(positions, counts, strict=True):
        axes[0].text(position, count + 0.2, str(count), ha="center")

    image = axes[1].imshow(
        matrix,
        vmin=0,
        vmax=1,
        cmap="Blues",
        aspect="auto",
    )
    axes[1].set_xticks(
        positions,
        [
            policy_labels[policy]
            for policy in JPEG_SELECTIVE_RETENTION_POLICIES
        ],
        rotation=20,
        ha="right",
    )
    axes[1].set_yticks(
        np.arange(len(categories)),
        [category.title() for category in categories],
    )
    axes[1].set_title("Category-level retention rate")
    for row_index in range(len(categories)):
        for column_index in range(
            len(JPEG_SELECTIVE_RETENTION_POLICIES)
        ):
            value = matrix[row_index, column_index]
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
        "Field-Level Metadata Provenance and Selective Retention",
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
            "Evaluate field-level JPEG metadata provenance and retention."
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
        help="Stable label recorded in platform observation rows.",
    )
    parser.add_argument(
        "--record-runner-image",
        action="store_true",
        help="Record hosted-runner image identifiers in the codec manifest.",
    )
    return parser.parse_args()


def main() -> None:
    """Run the controlled experiment and write deterministic artifacts."""
    args = parse_args()
    observations, decisions = collect_observations(args.platform_label)
    summary = summarize(observations)
    manifest = build_platform_manifest(
        args.platform_label,
        record_runner_image=args.record_runner_image,
    )
    write_csv(
        args.output_dir / PLATFORM_MANIFEST_NAME,
        manifest,
    )
    write_csv(
        args.output_dir / DECISIONS_NAME,
        decisions,
        DECISION_FIELDS,
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
    plot_results(decisions, args.output_dir / FIGURE_NAME)
    print(
        "Wrote "
        f"{len(decisions)} field decisions and {len(observations)} "
        f"policy observations to {args.output_dir}"
    )


if __name__ == "__main__":
    main()
