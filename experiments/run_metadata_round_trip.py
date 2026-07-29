"""Evaluate JPEG metadata round-trip preservation and sanitization policies."""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import platform
import sys
import warnings
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
    apply_jpeg_metadata_policy,
    audit_jpeg_metadata,
    compare_decoded_pixels,
    decode_jpeg_pillow,
    encode_jpeg_opencv,
    encode_jpeg_pillow,
    inspect_jpeg_metadata,
    pixel_array_sha256,
    strip_jpeg_interpretation_metadata,
)


QUALITY = 75
CHROMA_SAMPLING = "444"
POLICIES = ("preserve", "strip", "normalize", "reject")
ENCODERS = ("pillow", "opencv")
FIXTURE_COUNT = 21

FIXTURE_MANIFEST_NAME = "manifest.csv"
PLATFORM_MANIFEST_NAME = "jpeg_round_trip_codec_manifest.csv"
OBSERVATIONS_NAME = "jpeg_round_trip_observations.csv"
SUMMARY_NAME = "jpeg_round_trip_summary.csv"
FIGURE_NAME = "jpeg_metadata_round_trip.png"

OBSERVATION_FIELDS = (
    "platform_label",
    "fixture_id",
    "fixture_family",
    "mutation",
    "source_strict_accept",
    "source_issue_codes",
    "source_decode_success",
    "encoder",
    "policy",
    "policy_action",
    "output_emitted",
    "output_strict_accept",
    "output_issue_codes",
    "output_decode_success",
    "input_envelope_bytes",
    "envelope_contract_applicable",
    "input_envelope_byte_exact",
    "semantic_contract_applicable",
    "supported_semantics_retained",
    "output_exif_orientation",
    "output_icc_profile_sha256",
    "compressed_core_exact",
    "pixels_exact_to_reencode_control",
    "reencode_mean_absolute_error",
    "reencode_maximum_absolute_error",
    "output_size_bytes",
    "output_sha256",
    "output_bgr_sha256",
    "error_category",
)


def bytes_sha256(payload: bytes) -> str:
    """Return the SHA-256 digest of one byte string."""
    return hashlib.sha256(payload).hexdigest()


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
    """Record the policy, decoder, and encoder implementations."""
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
            "metadata_policy_engine",
            "policy",
            "research-notes",
            "0.14.0",
            "bounded_python_policy",
            "strict audit plus controlled metadata transfer",
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


def load_fixtures(fixture_dir: Path) -> list[dict[str, str]]:
    """Load and hash-check the committed v0.13 synthetic fixture corpus."""
    rows = read_csv(fixture_dir / FIXTURE_MANIFEST_NAME)
    if len(rows) != FIXTURE_COUNT:
        raise RuntimeError("Unexpected malformed-metadata fixture count")
    if len({row["fixture_id"] for row in rows}) != FIXTURE_COUNT:
        raise RuntimeError("Duplicate malformed-metadata fixture identifier")
    for row in rows:
        payload = (fixture_dir / row["jpeg_file"]).read_bytes()
        if bytes_sha256(payload) != row["jpeg_sha256"]:
            raise RuntimeError(
                f"Fixture {row['fixture_id']} failed its SHA-256 contract"
            )
        audit = audit_jpeg_metadata(payload)
        if int(audit.accepted) != int(row["expected_strict_accept"]):
            raise RuntimeError(
                f"Fixture {row['fixture_id']} failed its audit contract"
            )
    return sorted(rows, key=lambda row: row["fixture_id"])


def controlled_envelope(
    source_jpeg: bytes, placement: str, inserted_bytes: int
) -> bytes:
    """Extract the manifest-declared mutation bytes from one fixture."""
    if inserted_bytes < 0:
        raise ValueError("inserted_bytes must not be negative")
    if placement == "none":
        if inserted_bytes != 0:
            raise ValueError("none placement requires zero inserted bytes")
        return b""
    if inserted_bytes == 0:
        raise ValueError("metadata placement requires inserted bytes")
    if placement == "after_soi":
        return source_jpeg[2 : 2 + inserted_bytes]
    if placement == "after_eoi":
        return source_jpeg[-inserted_bytes:]
    raise ValueError("unknown fixture placement")


def remove_controlled_envelope(
    output_jpeg: bytes, envelope: bytes, placement: str
) -> bytes:
    """Remove an exactly copied controlled envelope from one output."""
    if placement == "none":
        return output_jpeg
    if placement == "after_soi":
        if output_jpeg[2 : 2 + len(envelope)] != envelope:
            raise ValueError("after-SOI envelope is not byte-exact")
        return output_jpeg[:2] + output_jpeg[2 + len(envelope) :]
    if placement == "after_eoi":
        if not output_jpeg.endswith(envelope):
            raise ValueError("after-EOI envelope is not byte-exact")
        return output_jpeg[: -len(envelope)]
    raise ValueError("unknown fixture placement")


def envelope_is_exact(
    output_jpeg: bytes, envelope: bytes, placement: str
) -> bool:
    """Check an output against the manifest-declared byte envelope."""
    if not envelope:
        return False
    if placement == "after_soi":
        return output_jpeg[2 : 2 + len(envelope)] == envelope
    if placement == "after_eoi":
        return output_jpeg.endswith(envelope)
    raise ValueError("non-empty envelope has no declared placement")


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


def decode_pillow_quietly(jpeg_bytes: bytes) -> NDArray[np.uint8]:
    """Decode through Pillow while suppressing fixture-specific warnings."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return decode_jpeg_pillow(jpeg_bytes)


def inspect_supported_semantics(
    jpeg_bytes: bytes,
) -> tuple[str, str]:
    """Return supported EXIF Orientation and ICC fingerprint fields."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            metadata = inspect_jpeg_metadata(jpeg_bytes)
    except ValueError:
        return "", ""
    return (
        (
            str(metadata.exif_orientation)
            if metadata.exif_orientation is not None
            else ""
        ),
        metadata.icc_profile_sha256,
    )


def failure_row(
    *,
    platform_label: str,
    fixture: dict[str, str],
    audit_accepted: bool,
    issue_codes: str,
    encoder: str,
    policy: str,
) -> dict[str, str]:
    """Build one row when the source cannot reach the encoder boundary."""
    action = (
        "strict_reject"
        if policy == "reject" and not audit_accepted
        else "source_decode_failed"
    )
    return {
        "platform_label": platform_label,
        "fixture_id": fixture["fixture_id"],
        "fixture_family": fixture["fixture_family"],
        "mutation": fixture["mutation"],
        "source_strict_accept": str(int(audit_accepted)),
        "source_issue_codes": issue_codes,
        "source_decode_success": "0",
        "encoder": encoder,
        "policy": policy,
        "policy_action": action,
        "output_emitted": "0",
        "output_strict_accept": "n/a",
        "output_issue_codes": "n/a",
        "output_decode_success": "0",
        "input_envelope_bytes": fixture["inserted_bytes"],
        "envelope_contract_applicable": "0",
        "input_envelope_byte_exact": "n/a",
        "semantic_contract_applicable": "0",
        "supported_semantics_retained": "n/a",
        "output_exif_orientation": "",
        "output_icc_profile_sha256": "",
        "compressed_core_exact": "n/a",
        "pixels_exact_to_reencode_control": "n/a",
        "reencode_mean_absolute_error": "nan",
        "reencode_maximum_absolute_error": "nan",
        "output_size_bytes": "0",
        "output_sha256": "",
        "output_bgr_sha256": "",
        "error_category": "source_decoder_rejected",
    }


def observation_rows(
    fixtures: Sequence[dict[str, str]],
    fixture_dir: Path,
    platform_label: str,
) -> list[dict[str, str]]:
    """Run every fixture through two encoders and four metadata policies."""
    rows: list[dict[str, str]] = []
    for fixture in fixtures:
        source_jpeg = (fixture_dir / fixture["jpeg_file"]).read_bytes()
        source_audit = audit_jpeg_metadata(source_jpeg)
        source_issues = (
            "|".join(source_audit.issue_codes)
            if source_audit.issue_codes
            else "none"
        )
        inserted_bytes = int(fixture["inserted_bytes"])
        envelope = controlled_envelope(
            source_jpeg, fixture["placement"], inserted_bytes
        )
        source_orientation, source_icc = inspect_supported_semantics(
            source_jpeg
        )
        semantic_applicable = bool(source_orientation or source_icc) and (
            source_audit.accepted
        )
        try:
            source_pixels = decode_pillow_quietly(source_jpeg)
        except ValueError:
            for encoder in ENCODERS:
                for policy in POLICIES:
                    rows.append(
                        failure_row(
                            platform_label=platform_label,
                            fixture=fixture,
                            audit_accepted=source_audit.accepted,
                            issue_codes=source_issues,
                            encoder=encoder,
                            policy=policy,
                        )
                    )
            continue

        for encoder in ENCODERS:
            reencoded = encode_image(encoder, source_pixels)
            reencode_control = decode_pillow_quietly(reencoded)
            reencode_difference = compare_decoded_pixels(
                source_pixels, reencode_control
            )
            for policy in POLICIES:
                result = apply_jpeg_metadata_policy(
                    source_jpeg,
                    reencoded,
                    policy,  # type: ignore[arg-type]
                    preserved_envelope=envelope,
                    envelope_placement=fixture["placement"],  # type: ignore[arg-type]
                )
                if not result.emitted:
                    rows.append(
                        {
                            **failure_row(
                                platform_label=platform_label,
                                fixture=fixture,
                                audit_accepted=source_audit.accepted,
                                issue_codes=source_issues,
                                encoder=encoder,
                                policy=policy,
                            ),
                            "source_decode_success": "1",
                            "policy_action": result.action,
                            "error_category": "strict_policy_reject",
                        }
                    )
                    continue
                output = result.output_bytes
                if output is None:
                    raise RuntimeError("Emitted policy result has no bytes")
                output_audit = audit_jpeg_metadata(output)
                output_issues = (
                    "|".join(output_audit.issue_codes)
                    if output_audit.issue_codes
                    else "none"
                )
                envelope_applicable = bool(envelope)
                exact_envelope = (
                    envelope_is_exact(
                        output, envelope, fixture["placement"]
                    )
                    if envelope_applicable
                    else False
                )
                output_orientation, output_icc = inspect_supported_semantics(
                    output
                )
                semantics_retained = (
                    output_orientation == source_orientation
                    and output_icc == source_icc
                )
                if policy == "preserve":
                    try:
                        output_core = remove_controlled_envelope(
                            output, envelope, fixture["placement"]
                        )
                    except ValueError:
                        output_core = b""
                else:
                    try:
                        output_core = strip_jpeg_interpretation_metadata(
                            output
                        )
                    except ValueError:
                        output_core = b""
                core_exact = output_core == reencoded

                output_pixels: NDArray[np.uint8] | None = None
                try:
                    output_pixels = decode_pillow_quietly(output)
                except ValueError:
                    pass
                if output_pixels is None:
                    pixels_exact = "0"
                    output_bgr_hash = ""
                    error_category = "output_decoder_rejected"
                else:
                    pixel_difference = compare_decoded_pixels(
                        reencode_control, output_pixels
                    )
                    pixels_exact = str(int(pixel_difference.exact))
                    output_bgr_hash = pixel_array_sha256(output_pixels)
                    error_category = "none"

                rows.append(
                    {
                        "platform_label": platform_label,
                        "fixture_id": fixture["fixture_id"],
                        "fixture_family": fixture["fixture_family"],
                        "mutation": fixture["mutation"],
                        "source_strict_accept": str(
                            int(source_audit.accepted)
                        ),
                        "source_issue_codes": source_issues,
                        "source_decode_success": "1",
                        "encoder": encoder,
                        "policy": policy,
                        "policy_action": result.action,
                        "output_emitted": "1",
                        "output_strict_accept": str(
                            int(output_audit.accepted)
                        ),
                        "output_issue_codes": output_issues,
                        "output_decode_success": str(
                            int(output_pixels is not None)
                        ),
                        "input_envelope_bytes": str(len(envelope)),
                        "envelope_contract_applicable": str(
                            int(envelope_applicable)
                        ),
                        "input_envelope_byte_exact": (
                            str(int(exact_envelope))
                            if envelope_applicable
                            else "n/a"
                        ),
                        "semantic_contract_applicable": str(
                            int(semantic_applicable)
                        ),
                        "supported_semantics_retained": (
                            str(int(semantics_retained))
                            if semantic_applicable
                            else "n/a"
                        ),
                        "output_exif_orientation": output_orientation,
                        "output_icc_profile_sha256": output_icc,
                        "compressed_core_exact": str(int(core_exact)),
                        "pixels_exact_to_reencode_control": pixels_exact,
                        "reencode_mean_absolute_error": (
                            f"{reencode_difference.mean_absolute_error:.9f}"
                        ),
                        "reencode_maximum_absolute_error": str(
                            reencode_difference.maximum_absolute_error
                        ),
                        "output_size_bytes": str(len(output)),
                        "output_sha256": bytes_sha256(output),
                        "output_bgr_sha256": output_bgr_hash,
                        "error_category": error_category,
                    }
                )
    validate_observations(rows)
    return rows


def validate_observations(rows: Sequence[dict[str, str]]) -> None:
    """Validate controlled contracts without assuming codec portability."""
    expected_count = FIXTURE_COUNT * len(ENCODERS) * len(POLICIES)
    if len(rows) != expected_count:
        raise RuntimeError("Unexpected metadata policy observation count")
    keys = {
        (
            row["platform_label"],
            row["fixture_id"],
            row["encoder"],
            row["policy"],
        )
        for row in rows
    }
    if len(keys) != len(rows):
        raise RuntimeError("Duplicate metadata policy observation found")
    emitted = [row for row in rows if row["output_emitted"] == "1"]
    if any(row["compressed_core_exact"] != "1" for row in emitted):
        raise RuntimeError("A metadata policy changed the re-encoded core")
    if any(
        row["output_decode_success"] == "1"
        and row["pixels_exact_to_reencode_control"] != "1"
        for row in emitted
    ):
        raise RuntimeError("A metadata-only policy changed raw decoded pixels")
    if any(
        row["policy"] in ("strip", "normalize")
        and row["output_emitted"] == "1"
        and row["output_strict_accept"] != "1"
        for row in rows
    ):
        raise RuntimeError("A sanitizing policy emitted rejected metadata")
    if any(
        row["policy"] == "reject"
        and (
            row["output_emitted"] != row["source_strict_accept"]
            or (
                row["output_emitted"] == "1"
                and row["output_strict_accept"] != "1"
            )
        )
        for row in rows
    ):
        raise RuntimeError("Reject policy violated its strict audit contract")
    if any(
        row["policy"] == "preserve"
        and row["output_emitted"] == "1"
        and row["envelope_contract_applicable"] == "1"
        and row["input_envelope_byte_exact"] != "1"
        for row in rows
    ):
        raise RuntimeError("Preserve policy did not copy an input envelope")


def rate(
    rows: Sequence[dict[str, str]], field: str, value: str = "1"
) -> str:
    """Return one fixed-precision categorical rate."""
    if not rows:
        return "nan"
    return f"{np.mean([row[field] == value for row in rows]):.6f}"


def summarize(
    observations: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Summarize output, audit, byte, semantic, and pixel contracts."""
    rows: list[dict[str, str]] = []
    for encoder in ENCODERS:
        for policy in POLICIES:
            group = [
                row
                for row in observations
                if row["encoder"] == encoder and row["policy"] == policy
            ]
            emitted = [
                row for row in group if row["output_emitted"] == "1"
            ]
            decoded = [
                row
                for row in emitted
                if row["output_decode_success"] == "1"
            ]
            envelope_rows = [
                row
                for row in emitted
                if row["envelope_contract_applicable"] == "1"
            ]
            semantic_rows = [
                row
                for row in emitted
                if row["semantic_contract_applicable"] == "1"
            ]
            reencode_errors = [
                float(row["reencode_mean_absolute_error"])
                for row in emitted
                if row["reencode_mean_absolute_error"] != "nan"
            ]
            rows.append(
                {
                    "encoder": encoder,
                    "policy": policy,
                    "attempts": str(len(group)),
                    "source_decode_successes": str(
                        sum(
                            int(row["source_decode_success"])
                            for row in group
                        )
                    ),
                    "outputs_emitted": str(len(emitted)),
                    "output_rate": rate(group, "output_emitted"),
                    "strict_accepted_outputs": str(
                        sum(
                            row["output_strict_accept"] == "1"
                            for row in emitted
                        )
                    ),
                    "strict_accept_rate_among_outputs": rate(
                        emitted, "output_strict_accept"
                    ),
                    "output_decode_successes": str(len(decoded)),
                    "output_decode_rate_among_outputs": rate(
                        emitted, "output_decode_success"
                    ),
                    "byte_envelope_cases": str(len(envelope_rows)),
                    "byte_exact_envelope_cases": str(
                        sum(
                            row["input_envelope_byte_exact"] == "1"
                            for row in envelope_rows
                        )
                    ),
                    "byte_exact_envelope_rate": rate(
                        envelope_rows, "input_envelope_byte_exact"
                    ),
                    "supported_semantic_cases": str(len(semantic_rows)),
                    "supported_semantics_retained": str(
                        sum(
                            row["supported_semantics_retained"] == "1"
                            for row in semantic_rows
                        )
                    ),
                    "supported_semantic_retention_rate": rate(
                        semantic_rows, "supported_semantics_retained"
                    ),
                    "compressed_core_exact_rate": rate(
                        emitted, "compressed_core_exact"
                    ),
                    "pixel_exact_rate_among_decoded_outputs": rate(
                        decoded, "pixels_exact_to_reencode_control"
                    ),
                    "reencode_mean_absolute_error_mean": (
                        f"{np.mean(reencode_errors):.9f}"
                        if reencode_errors
                        else "nan"
                    ),
                    "reencode_mean_absolute_error_max": (
                        f"{max(reencode_errors):.9f}"
                        if reencode_errors
                        else "nan"
                    ),
                }
            )
    return rows


def plot_summary(
    summary: Sequence[dict[str, str]], output_path: Path
) -> None:
    """Plot policy output, audit, byte, semantic, and pixel contracts."""
    figure, axes = plt.subplots(
        1, 3, figsize=(15, 4.8), constrained_layout=True
    )
    positions = np.arange(len(POLICIES), dtype=np.float64)
    width = 0.36
    colors = {"pillow": "#4472C4", "opencv": "#ED7D31"}

    for encoder_index, encoder in enumerate(ENCODERS):
        encoder_rows = [
            row for row in summary if row["encoder"] == encoder
        ]
        offset = (encoder_index - 0.5) * width
        axes[0].bar(
            positions + offset,
            [float(row["output_rate"]) for row in encoder_rows],
            width,
            label=encoder,
            color=colors[encoder],
            alpha=0.88,
        )
        axes[0].plot(
            positions + offset,
            [
                float(row["strict_accept_rate_among_outputs"])
                if row["strict_accept_rate_among_outputs"] != "nan"
                else 0.0
                for row in encoder_rows
            ],
            "o",
            color="#222222",
            markersize=4,
        )
    axes[0].set_title("Emission bars; strict acceptance dots")
    axes[0].set_ylabel("Rate")
    axes[0].set_ylim(0, 1.08)
    axes[0].set_xticks(positions, POLICIES, rotation=20)
    axes[0].legend(title="Re-encoder")
    axes[0].grid(axis="y", alpha=0.25)

    contract_names = (
        "byte_exact_envelope_rate",
        "supported_semantic_retention_rate",
    )
    contract_labels = ("Input envelope", "EXIF / ICC semantics")
    contract_values = np.zeros(
        (len(POLICIES), len(contract_names)), dtype=np.float64
    )
    for policy_index, policy in enumerate(POLICIES):
        policy_rows = [row for row in summary if row["policy"] == policy]
        for contract_index, field in enumerate(contract_names):
            values = [
                float(row[field])
                for row in policy_rows
                if row[field] != "nan"
            ]
            contract_values[policy_index, contract_index] = (
                float(np.mean(values)) if values else np.nan
            )
    image = axes[1].imshow(
        contract_values,
        cmap="RdYlGn",
        vmin=0,
        vmax=1,
        aspect="auto",
    )
    axes[1].set_title("Input metadata retention")
    axes[1].set_xticks(range(len(contract_labels)), contract_labels, rotation=20)
    axes[1].set_yticks(range(len(POLICIES)), POLICIES)
    for row_index in range(len(POLICIES)):
        for column_index in range(len(contract_names)):
            value = contract_values[row_index, column_index]
            axes[1].text(
                column_index,
                row_index,
                "n/a" if np.isnan(value) else f"{value:.2f}",
                ha="center",
                va="center",
            )
    figure.colorbar(image, ax=axes[1], shrink=0.8)

    for encoder_index, encoder in enumerate(ENCODERS):
        encoder_rows = [
            row for row in summary if row["encoder"] == encoder
        ]
        offset = (encoder_index - 0.5) * width
        axes[2].bar(
            positions + offset,
            [
                float(row["pixel_exact_rate_among_decoded_outputs"])
                if row["pixel_exact_rate_among_decoded_outputs"] != "nan"
                else 0.0
                for row in encoder_rows
            ],
            width,
            label=encoder,
            color=colors[encoder],
            alpha=0.88,
        )
    axes[2].set_title("Pixels exact to re-encode control")
    axes[2].set_ylabel("Rate among decoded outputs")
    axes[2].set_ylim(0, 1.08)
    axes[2].set_xticks(positions, POLICIES, rotation=20)
    axes[2].grid(axis="y", alpha=0.25)
    figure.suptitle(
        "Metadata round-trip preservation and sanitization policies"
    )
    figure.savefig(
        output_path,
        dpi=160,
        metadata={"Software": "research-notes v0.14.0"},
    )
    plt.close(figure)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate JPEG metadata preservation and sanitization policies."
        )
    )
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=Path("fixtures/malformed-jpeg-metadata"),
        help="Directory containing the v0.13 synthetic fixture corpus.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results"),
        help="Directory for CSV and PNG outputs.",
    )
    parser.add_argument(
        "--platform-label",
        default="linux-x64-reference",
        help="Stable label for the current platform profile.",
    )
    parser.add_argument(
        "--record-runner-image",
        action="store_true",
        help="Record GitHub-hosted runner image metadata when available.",
    )
    return parser.parse_args()


def main() -> None:
    """Load fixtures, run every policy, and write deterministic reports."""
    args = parse_args()
    fixtures = load_fixtures(args.fixture_dir)
    manifests = build_platform_manifest(
        args.platform_label,
        record_runner_image=args.record_runner_image,
    )
    observations = observation_rows(
        fixtures, args.fixture_dir, args.platform_label
    )
    summary = summarize(observations)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        args.output_dir / PLATFORM_MANIFEST_NAME,
        manifests,
    )
    write_csv(
        args.output_dir / OBSERVATIONS_NAME,
        observations,
        OBSERVATION_FIELDS,
    )
    write_csv(args.output_dir / SUMMARY_NAME, summary)
    plot_summary(summary, args.output_dir / FIGURE_NAME)
    print(
        "JPEG metadata round-trip evaluation complete: "
        f"{len(fixtures)} fixtures, {len(ENCODERS)} encoders, "
        f"{len(POLICIES)} policies, {len(observations)} observations."
    )


if __name__ == "__main__":
    main()
