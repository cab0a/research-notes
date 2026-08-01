"""Evaluate controlled digest bindings across JPEG transforms."""

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
    build_synthetic_rgb_profile,
    build_transform_integrity_fixtures,
    encode_jpeg_pillow,
    verify_transform_integrity_assertion,
)


MANIFEST_NAME = "jpeg_transform_integrity_runtime_manifest.csv"
OBSERVATIONS_NAME = "jpeg_transform_integrity_observations.csv"
SUMMARY_NAME = "jpeg_transform_integrity_summary.csv"
FIGURE_NAME = "jpeg_transform_integrity.png"

OBSERVATION_FIELDS = (
    "platform_label",
    "fixture",
    "transform",
    "assertion_mode",
    "expected_status",
    "observed_status",
    "expectation_met",
    "expected_reason_code",
    "reason_code",
    "action",
    "parent_declared",
    "assertion_sha256",
    "binding_names",
    "matching_bindings",
    "mismatching_bindings",
    "matching_binding_count",
    "mismatching_binding_count",
    "fixture_bytes",
    "fixture_sha256",
)

SUMMARY_FIELDS = (
    "transform",
    "fixtures",
    "valid_binding_count",
    "valid_derived_binding_count",
    "stale_binding_count",
    "missing_assertion_count",
    "malformed_assertion_count",
    "multiple_assertions_count",
    "expectation_rate",
    "mismatching_binding_count",
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
    """Record the assertion model, hash implementation, and encoder."""
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
            "transform_integrity_model",
            "digest_binding",
            "research-notes",
            "0.19.0",
            "unsigned image-core, normalized-metadata, and decoded-pixel bindings",
        ),
        (
            "sha256",
            "digest",
            "Python hashlib",
            "SHA-256",
            "canonical JSON assertion and controlled content scopes",
        ),
        (
            "fixture_encoder",
            "image_encoder",
            f"Pillow {PIL.__version__}",
            pillow_jpeg_backend(),
            "quality 75 source; quality 65 re-encode; chroma 444",
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
    """Evaluate all controlled transform-integrity fixtures."""
    base_jpeg = encode_jpeg_pillow(
        make_base_image(), quality=75, chroma_sampling="444"
    )
    fixtures = build_transform_integrity_fixtures(
        base_jpeg, icc_profile=build_synthetic_rgb_profile(2.2)
    )
    observations = []
    for fixture in fixtures:
        result = verify_transform_integrity_assertion(fixture.jpeg_bytes)
        observations.append(
            {
                "platform_label": platform_label,
                "fixture": fixture.fixture,
                "transform": fixture.transform,
                "assertion_mode": fixture.assertion_mode,
                "expected_status": fixture.expected_status,
                "observed_status": result.status,
                "expectation_met": str(
                    int(
                        result.status == fixture.expected_status
                        and result.reason_code == fixture.expected_reason_code
                    )
                ),
                "expected_reason_code": fixture.expected_reason_code,
                "reason_code": result.reason_code,
                "action": result.action,
                "parent_declared": str(
                    int(bool(result.parent_assertion_sha256))
                ),
                "assertion_sha256": result.assertion_sha256,
                "binding_names": "|".join(result.binding_names),
                "matching_bindings": "|".join(result.matching_bindings),
                "mismatching_bindings": "|".join(
                    result.mismatching_bindings
                ),
                "matching_binding_count": str(len(result.matching_bindings)),
                "mismatching_binding_count": str(
                    len(result.mismatching_bindings)
                ),
                "fixture_bytes": str(len(fixture.jpeg_bytes)),
                "fixture_sha256": hashlib.sha256(
                    fixture.jpeg_bytes
                ).hexdigest(),
            }
        )
    validate_observations(observations)
    return observations


def validate_observations(
    observations: Sequence[dict[str, str]],
) -> None:
    """Enforce status and binding-scope expectations."""
    if len(observations) != 11:
        raise RuntimeError("expected 11 transform-integrity observations")
    if any(row["expectation_met"] != "1" for row in observations):
        raise RuntimeError("a transform-integrity expectation failed")
    by_fixture = {row["fixture"]: row for row in observations}
    if by_fixture["metadata_sanitized_inherited"]["mismatching_bindings"] != "metadata_state_sha256":
        raise RuntimeError("sanitization did not isolate the metadata binding")
    expected_lossy = "image_core_sha256|decoded_pixels_sha256"
    for fixture in ("reencoded_inherited", "pixel_modified_inherited"):
        if by_fixture[fixture]["mismatching_bindings"] != expected_lossy:
            raise RuntimeError("a lossy transform changed unexpected bindings")
    renewed = [row for row in observations if row["assertion_mode"] == "renewed"]
    if any(
        row["observed_status"] != "valid_derived_binding"
        or row["parent_declared"] != "1"
        for row in renewed
    ):
        raise RuntimeError("a renewed assertion is not a valid derived binding")


def summarize(
    observations: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Aggregate statuses and mismatch counts by transform."""
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in observations:
        grouped[row["transform"]].append(row)
    statuses = (
        "valid_binding",
        "valid_derived_binding",
        "stale_binding",
        "missing_assertion",
        "malformed_assertion",
        "multiple_assertions",
    )
    summary = []
    for transform in sorted(grouped):
        rows = grouped[transform]
        row = {
            "transform": transform,
            "fixtures": str(len(rows)),
            **{
                f"{status}_count": str(
                    sum(item["observed_status"] == status for item in rows)
                )
                for status in statuses
            },
            "expectation_rate": (
                f"{sum(int(item['expectation_met']) for item in rows) / len(rows):.6f}"
            ),
            "mismatching_binding_count": str(
                sum(int(item["mismatching_binding_count"]) for item in rows)
            ),
        }
        summary.append(row)
    return summary


def plot_results(
    observations: Sequence[dict[str, str]], output_path: Path
) -> None:
    """Visualize assertion status and binding-scope mismatches."""
    statuses = (
        "valid_binding",
        "valid_derived_binding",
        "stale_binding",
        "missing_assertion",
        "malformed_assertion",
        "multiple_assertions",
    )
    colors = ("#2a9d8f", "#457b9d", "#e9c46a", "#8d99ae", "#e76f51", "#9b5de5")
    figure, axes = plt.subplots(1, 2, figsize=(14.5, 7.2))
    counts = [
        sum(row["observed_status"] == status for row in observations)
        for status in statuses
    ]
    axes[0].barh(statuses, counts, color=colors)
    axes[0].set_xlabel("Fixture count")
    axes[0].set_title("Presence, syntax, and digest outcomes remain distinct")
    axes[0].grid(axis="x", alpha=0.25)

    binding_names = (
        "image_core_sha256",
        "metadata_state_sha256",
        "decoded_pixels_sha256",
    )
    y = np.arange(len(observations))
    left = np.zeros(len(observations))
    for name, color in zip(binding_names, ("#264653", "#f4a261", "#2a9d8f"), strict=True):
        values = [int(name in row["mismatching_bindings"].split("|")) for row in observations]
        axes[1].barh(y, values, left=left, color=color, label=name)
        left += np.array(values)
    axes[1].set_yticks(y, [row["fixture"] for row in observations])
    axes[1].set_xlabel("Mismatching bound scopes")
    axes[1].set_title("Inherited assertions expose transform-specific drift")
    axes[1].legend(fontsize=8)
    axes[1].grid(axis="x", alpha=0.25)
    figure.suptitle(
        "Controlled JPEG Transform Integrity",
        fontsize=14,
        fontweight="bold",
    )
    figure.text(
        0.5,
        0.012,
        "Digest agreement detects declared changes; unsigned records do not authenticate origin.",
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
        description="Evaluate controlled JPEG transform-integrity bindings."
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
        f"Wrote {len(observations)} transform-integrity observations and "
        f"{len(summary)} transform summaries to {args.output_dir}"
    )


if __name__ == "__main__":
    main()
