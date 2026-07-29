"""Evaluate metadata policy drift across repeated JPEG generations."""

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
    apply_jpeg_metadata_policy,
    audit_jpeg_metadata,
    compare_decoded_pixels,
    decode_jpeg_pillow,
    encode_jpeg_opencv,
    encode_jpeg_pillow,
    inspect_jpeg_metadata,
    pixel_array_sha256,
)


QUALITY = 75
CHROMA_SAMPLING = "444"
MAX_GENERATION = 10
CHECKPOINTS = {0, 1, 2, 5, 10}
ENCODERS = ("pillow", "opencv")
FIXTURE_IDS = (
    "app15_large_valid",
    "app1_unknown_valid",
    "exif_orientation_6_valid",
    "icc_gamma_2_2_valid",
    "rgb_control",
)
SEQUENCES = (
    "preserve_repeat",
    "strip_repeat",
    "normalize_repeat",
    "preserve_then_normalize",
    "normalize_then_strip",
    "strip_then_preserve",
)

FIXTURE_MANIFEST_NAME = "manifest.csv"
PLATFORM_MANIFEST_NAME = "jpeg_metadata_generation_codec_manifest.csv"
OBSERVATIONS_NAME = "jpeg_metadata_generation_observations.csv"
SUMMARY_NAME = "jpeg_metadata_generation_summary.csv"
CONTRACTS_NAME = "jpeg_metadata_generation_contracts.csv"
FIGURE_NAME = "jpeg_metadata_generation_drift.png"

OBSERVATION_FIELDS = (
    "platform_label",
    "fixture_id",
    "fixture_family",
    "encoder",
    "sequence_id",
    "generation",
    "checkpoint",
    "policy",
    "policy_action",
    "source_strict_accept",
    "output_strict_accept",
    "application_segment_count",
    "application_metadata_bytes",
    "metadata_state_sha256",
    "metadata_changed_from_previous",
    "original_envelope_contract_applicable",
    "original_envelope_byte_exact",
    "semantic_contract_applicable",
    "supported_semantics_retained",
    "output_exif_orientation",
    "output_icc_profile_sha256",
    "compressed_core_sha256",
    "jpeg_size_bytes",
    "jpeg_sha256",
    "output_bgr_sha256",
    "jpeg_changed_from_previous",
    "pixels_exact_to_previous",
    "mean_absolute_error_to_previous",
    "maximum_absolute_error_to_previous",
    "pixels_exact_to_generation_zero",
    "mean_absolute_error_to_generation_zero",
    "maximum_absolute_error_to_generation_zero",
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
            "metadata_generation_policy",
            "policy",
            "research-notes",
            "0.15.0",
            "bounded_python_policy",
            "controlled repeated metadata transfer",
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
    """Load the five strict-accepted controls from the v0.13 corpus."""
    rows = {
        row["fixture_id"]: row
        for row in read_csv(fixture_dir / FIXTURE_MANIFEST_NAME)
    }
    if set(FIXTURE_IDS) - rows.keys():
        raise RuntimeError("A required metadata-generation fixture is missing")
    selected = [rows[fixture_id] for fixture_id in FIXTURE_IDS]
    for row in selected:
        payload = (fixture_dir / row["jpeg_file"]).read_bytes()
        if bytes_sha256(payload) != row["jpeg_sha256"]:
            raise RuntimeError(
                f"Fixture {row['fixture_id']} failed its SHA-256 contract"
            )
        if row["expected_strict_accept"] != "1":
            raise RuntimeError(
                f"Fixture {row['fixture_id']} is not a strict-accepted control"
            )
        if not audit_jpeg_metadata(payload).accepted:
            raise RuntimeError(
                f"Fixture {row['fixture_id']} failed its audit contract"
            )
    return selected


def controlled_envelope(
    source_jpeg: bytes, placement: str, inserted_bytes: int
) -> bytes:
    """Extract one manifest-declared controlled metadata envelope."""
    if inserted_bytes < 0:
        raise ValueError("inserted_bytes must not be negative")
    if placement == "none":
        if inserted_bytes != 0:
            raise ValueError("none placement requires zero inserted bytes")
        return b""
    if placement != "after_soi":
        raise ValueError("generation fixtures require after-SOI metadata")
    if inserted_bytes == 0:
        raise ValueError("after-SOI placement requires inserted bytes")
    return source_jpeg[2 : 2 + inserted_bytes]


def split_application_metadata(jpeg_bytes: bytes) -> tuple[tuple[bytes, ...], bytes]:
    """Separate APP1-APP15 segments from a strict-accepted JPEG.

    APP0 is kept in the compressed-core control because the encoders create
    their own JFIF envelope. The function is an experiment helper for audited
    fixtures, not an untrusted-input parser.
    """
    if not isinstance(jpeg_bytes, bytes) or not jpeg_bytes.startswith(
        b"\xff\xd8"
    ):
        raise ValueError("jpeg_bytes must contain a JPEG SOI marker")
    metadata: list[bytes] = []
    core = bytearray(jpeg_bytes[:2])
    position = 2
    while position < len(jpeg_bytes):
        marker_start = position
        if jpeg_bytes[position] != 0xFF:
            raise ValueError("expected a JPEG marker prefix")
        while position < len(jpeg_bytes) and jpeg_bytes[position] == 0xFF:
            position += 1
        if position >= len(jpeg_bytes):
            raise ValueError("truncated JPEG marker")
        marker = jpeg_bytes[position]
        position += 1
        if marker in (0xD9, 0xDA):
            core.extend(jpeg_bytes[marker_start:])
            break
        if marker == 0x01 or 0xD0 <= marker <= 0xD8:
            core.extend(jpeg_bytes[marker_start:position])
            continue
        if position + 2 > len(jpeg_bytes):
            raise ValueError("truncated JPEG segment length")
        segment_length = int.from_bytes(jpeg_bytes[position : position + 2], "big")
        if segment_length < 2:
            raise ValueError("invalid JPEG segment length")
        segment_end = position + segment_length
        if segment_end > len(jpeg_bytes):
            raise ValueError("JPEG segment exceeds the byte stream")
        segment = jpeg_bytes[marker_start:segment_end]
        if 0xE1 <= marker <= 0xEF:
            metadata.append(segment)
        else:
            core.extend(segment)
        position = segment_end
    if not core.endswith(b"\xff\xd9"):
        raise ValueError("JPEG EOI marker was not found")
    return tuple(metadata), bytes(core)


def inspect_supported_semantics(jpeg_bytes: bytes) -> tuple[str, str]:
    """Return EXIF Orientation and the complete ICC profile fingerprint."""
    metadata = inspect_jpeg_metadata(jpeg_bytes)
    return (
        (
            str(metadata.exif_orientation)
            if metadata.exif_orientation is not None
            else ""
        ),
        metadata.icc_profile_sha256,
    )


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


def policy_for_generation(sequence_id: str, generation: int) -> str:
    """Return the declared policy for one positive generation."""
    if generation < 1:
        raise ValueError("generation must be positive")
    if sequence_id == "preserve_repeat":
        return "preserve"
    if sequence_id == "strip_repeat":
        return "strip"
    if sequence_id == "normalize_repeat":
        return "normalize"
    if sequence_id == "preserve_then_normalize":
        return "preserve" if generation == 1 else "normalize"
    if sequence_id == "normalize_then_strip":
        return "normalize" if generation == 1 else "strip"
    if sequence_id == "strip_then_preserve":
        return "strip" if generation == 1 else "preserve"
    raise ValueError(f"Unknown policy sequence: {sequence_id}")


def preservation_inputs(
    sequence_id: str,
    generation: int,
    original_envelope: bytes,
    original_placement: str,
) -> tuple[bytes, str]:
    """Return the controlled envelope visible to a preserve step."""
    policy = policy_for_generation(sequence_id, generation)
    if policy != "preserve":
        return b"", "none"
    if sequence_id == "preserve_repeat":
        return original_envelope, original_placement
    if sequence_id == "preserve_then_normalize" and generation == 1:
        return original_envelope, original_placement
    return b"", "none"


def make_observation(
    *,
    platform_label: str,
    fixture: dict[str, str],
    encoder: str,
    sequence_id: str,
    generation: int,
    policy: str,
    policy_action: str,
    source_accepted: bool,
    output_jpeg: bytes,
    previous_jpeg: bytes | None,
    previous_pixels: NDArray[np.uint8] | None,
    generation_zero_pixels: NDArray[np.uint8],
    original_envelope: bytes,
    original_orientation: str,
    original_icc: str,
) -> dict[str, str]:
    """Measure metadata state and pixel drift for one generation."""
    output_audit = audit_jpeg_metadata(output_jpeg)
    if not output_audit.accepted:
        raise RuntimeError("A generation output failed the strict audit")
    output_pixels = decode_jpeg_pillow(output_jpeg)
    metadata_segments, compressed_core = split_application_metadata(output_jpeg)
    metadata_blob = b"".join(metadata_segments)
    output_orientation, output_icc = inspect_supported_semantics(output_jpeg)
    semantic_applicable = bool(original_orientation or original_icc)
    semantics_retained = (
        output_orientation == original_orientation
        and output_icc == original_icc
    )
    envelope_applicable = bool(original_envelope)
    envelope_exact = metadata_blob == original_envelope
    zero_difference = compare_decoded_pixels(
        generation_zero_pixels, output_pixels
    )

    if previous_jpeg is None or previous_pixels is None:
        metadata_changed = "n/a"
        jpeg_changed = "n/a"
        pixels_exact_previous = "n/a"
        previous_mean_error = "nan"
        previous_maximum_error = "nan"
    else:
        previous_segments, _ = split_application_metadata(previous_jpeg)
        previous_blob = b"".join(previous_segments)
        previous_difference = compare_decoded_pixels(
            previous_pixels, output_pixels
        )
        metadata_changed = str(int(metadata_blob != previous_blob))
        jpeg_changed = str(int(output_jpeg != previous_jpeg))
        pixels_exact_previous = str(int(previous_difference.exact))
        previous_mean_error = (
            f"{previous_difference.mean_absolute_error:.9f}"
        )
        previous_maximum_error = str(
            previous_difference.maximum_absolute_error
        )

    return {
        "platform_label": platform_label,
        "fixture_id": fixture["fixture_id"],
        "fixture_family": fixture["fixture_family"],
        "encoder": encoder,
        "sequence_id": sequence_id,
        "generation": str(generation),
        "checkpoint": str(int(generation in CHECKPOINTS)),
        "policy": policy,
        "policy_action": policy_action,
        "source_strict_accept": str(int(source_accepted)),
        "output_strict_accept": "1",
        "application_segment_count": str(len(metadata_segments)),
        "application_metadata_bytes": str(len(metadata_blob)),
        "metadata_state_sha256": bytes_sha256(metadata_blob),
        "metadata_changed_from_previous": metadata_changed,
        "original_envelope_contract_applicable": str(
            int(envelope_applicable)
        ),
        "original_envelope_byte_exact": (
            str(int(envelope_exact)) if envelope_applicable else "n/a"
        ),
        "semantic_contract_applicable": str(int(semantic_applicable)),
        "supported_semantics_retained": (
            str(int(semantics_retained)) if semantic_applicable else "n/a"
        ),
        "output_exif_orientation": output_orientation,
        "output_icc_profile_sha256": output_icc,
        "compressed_core_sha256": bytes_sha256(compressed_core),
        "jpeg_size_bytes": str(len(output_jpeg)),
        "jpeg_sha256": bytes_sha256(output_jpeg),
        "output_bgr_sha256": pixel_array_sha256(output_pixels),
        "jpeg_changed_from_previous": jpeg_changed,
        "pixels_exact_to_previous": pixels_exact_previous,
        "mean_absolute_error_to_previous": previous_mean_error,
        "maximum_absolute_error_to_previous": previous_maximum_error,
        "pixels_exact_to_generation_zero": str(int(zero_difference.exact)),
        "mean_absolute_error_to_generation_zero": (
            f"{zero_difference.mean_absolute_error:.9f}"
        ),
        "maximum_absolute_error_to_generation_zero": str(
            zero_difference.maximum_absolute_error
        ),
    }


def run_sequence(
    *,
    fixture: dict[str, str],
    fixture_dir: Path,
    encoder: str,
    sequence_id: str,
    platform_label: str,
) -> list[dict[str, str]]:
    """Run one fixture and encoder through one ten-generation sequence."""
    original_jpeg = (fixture_dir / fixture["jpeg_file"]).read_bytes()
    original_audit = audit_jpeg_metadata(original_jpeg)
    if not original_audit.accepted:
        raise RuntimeError("Generation inputs must pass the strict audit")
    generation_zero_pixels = decode_jpeg_pillow(original_jpeg)
    original_orientation, original_icc = inspect_supported_semantics(
        original_jpeg
    )
    original_envelope = controlled_envelope(
        original_jpeg,
        fixture["placement"],
        int(fixture["inserted_bytes"]),
    )

    rows = [
        make_observation(
            platform_label=platform_label,
            fixture=fixture,
            encoder=encoder,
            sequence_id=sequence_id,
            generation=0,
            policy="source",
            policy_action="source_control",
            source_accepted=True,
            output_jpeg=original_jpeg,
            previous_jpeg=None,
            previous_pixels=None,
            generation_zero_pixels=generation_zero_pixels,
            original_envelope=original_envelope,
            original_orientation=original_orientation,
            original_icc=original_icc,
        )
    ]
    current_jpeg = original_jpeg
    current_pixels = generation_zero_pixels
    for generation in range(1, MAX_GENERATION + 1):
        source_audit = audit_jpeg_metadata(current_jpeg)
        if not source_audit.accepted:
            raise RuntimeError("A previous generation failed the strict audit")
        reencoded = encode_image(encoder, current_pixels)
        policy = policy_for_generation(sequence_id, generation)
        envelope, placement = preservation_inputs(
            sequence_id,
            generation,
            original_envelope,
            fixture["placement"],
        )
        result = apply_jpeg_metadata_policy(
            current_jpeg,
            reencoded,
            policy,  # type: ignore[arg-type]
            preserved_envelope=envelope,
            envelope_placement=placement,  # type: ignore[arg-type]
        )
        if not result.emitted or result.output_bytes is None:
            raise RuntimeError("A non-reject generation policy emitted no output")
        next_jpeg = result.output_bytes
        rows.append(
            make_observation(
                platform_label=platform_label,
                fixture=fixture,
                encoder=encoder,
                sequence_id=sequence_id,
                generation=generation,
                policy=policy,
                policy_action=result.action,
                source_accepted=source_audit.accepted,
                output_jpeg=next_jpeg,
                previous_jpeg=current_jpeg,
                previous_pixels=current_pixels,
                generation_zero_pixels=generation_zero_pixels,
                original_envelope=original_envelope,
                original_orientation=original_orientation,
                original_icc=original_icc,
            )
        )
        current_jpeg = next_jpeg
        current_pixels = decode_jpeg_pillow(current_jpeg)
    return rows


def observation_rows(
    fixtures: Sequence[dict[str, str]],
    fixture_dir: Path,
    platform_label: str,
) -> list[dict[str, str]]:
    """Run all fixed fixtures, encoders, and policy sequences."""
    rows = [
        row
        for fixture in fixtures
        for encoder in ENCODERS
        for sequence_id in SEQUENCES
        for row in run_sequence(
            fixture=fixture,
            fixture_dir=fixture_dir,
            encoder=encoder,
            sequence_id=sequence_id,
            platform_label=platform_label,
        )
    ]
    validate_observations(rows)
    return rows


def validate_observations(rows: Sequence[dict[str, str]]) -> None:
    """Validate temporal contracts without asserting pixel idempotence."""
    expected_count = (
        len(FIXTURE_IDS)
        * len(ENCODERS)
        * len(SEQUENCES)
        * (MAX_GENERATION + 1)
    )
    if len(rows) != expected_count:
        raise RuntimeError("Unexpected metadata-generation observation count")
    keys = {
        (
            row["platform_label"],
            row["fixture_id"],
            row["encoder"],
            row["sequence_id"],
            row["generation"],
        )
        for row in rows
    }
    if len(keys) != len(rows):
        raise RuntimeError("Duplicate metadata-generation observation found")
    if any(row["output_strict_accept"] != "1" for row in rows):
        raise RuntimeError("A generation output violated the strict policy")

    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[
            (row["fixture_id"], row["encoder"], row["sequence_id"])
        ].append(row)

    for (_, _, sequence_id), group in grouped.items():
        ordered = sorted(group, key=lambda row: int(row["generation"]))
        hashes = [row["metadata_state_sha256"] for row in ordered]
        if sequence_id == "preserve_repeat" and len(set(hashes)) != 1:
            raise RuntimeError("Repeated preserve changed metadata bytes")
        stable_start = (
            2
            if sequence_id
            in ("preserve_then_normalize", "normalize_then_strip")
            else 1
        )
        if len(set(hashes[stable_start:])) != 1:
            raise RuntimeError(
                f"{sequence_id} did not reach a stable metadata state"
            )
        if sequence_id in ("strip_repeat", "strip_then_preserve") and any(
            int(row["application_metadata_bytes"]) != 0
            for row in ordered[1:]
        ):
            raise RuntimeError(f"{sequence_id} restored removed metadata")
        if sequence_id == "normalize_then_strip" and any(
            int(row["application_metadata_bytes"]) != 0
            for row in ordered[2:]
        ):
            raise RuntimeError("Normalize-then-strip retained metadata")
        if sequence_id == "preserve_repeat" and any(
            row["original_envelope_contract_applicable"] == "1"
            and row["original_envelope_byte_exact"] != "1"
            for row in ordered
        ):
            raise RuntimeError("Repeated preserve lost an original envelope")


def rate(
    rows: Sequence[dict[str, str]], field: str, value: str = "1"
) -> str:
    """Return one fixed-precision categorical rate."""
    if not rows:
        return "nan"
    return f"{np.mean([row[field] == value for row in rows]):.6f}"


def mean_field(rows: Sequence[dict[str, str]], field: str) -> str:
    """Return one fixed-precision mean over numeric string fields."""
    if not rows:
        return "nan"
    return f"{np.mean([float(row[field]) for row in rows]):.9f}"


def summarize(
    observations: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Summarize metadata retention and pixel drift by generation."""
    rows: list[dict[str, str]] = []
    for encoder in ENCODERS:
        for sequence_id in SEQUENCES:
            for generation in range(MAX_GENERATION + 1):
                group = [
                    row
                    for row in observations
                    if row["encoder"] == encoder
                    and row["sequence_id"] == sequence_id
                    and int(row["generation"]) == generation
                ]
                envelope_rows = [
                    row
                    for row in group
                    if row["original_envelope_contract_applicable"] == "1"
                ]
                semantic_rows = [
                    row
                    for row in group
                    if row["semantic_contract_applicable"] == "1"
                ]
                comparable_rows = [
                    row
                    for row in group
                    if row["metadata_changed_from_previous"] != "n/a"
                ]
                rows.append(
                    {
                        "encoder": encoder,
                        "sequence_id": sequence_id,
                        "generation": str(generation),
                        "checkpoint": str(int(generation in CHECKPOINTS)),
                        "fixture_count": str(len(group)),
                        "strict_accept_rate": rate(
                            group, "output_strict_accept"
                        ),
                        "metadata_change_rate_from_previous": rate(
                            comparable_rows,
                            "metadata_changed_from_previous",
                        ),
                        "mean_application_segment_count": mean_field(
                            group, "application_segment_count"
                        ),
                        "mean_application_metadata_bytes": mean_field(
                            group, "application_metadata_bytes"
                        ),
                        "original_envelope_cases": str(len(envelope_rows)),
                        "original_envelope_exact_rate": rate(
                            envelope_rows, "original_envelope_byte_exact"
                        ),
                        "supported_semantic_cases": str(len(semantic_rows)),
                        "supported_semantics_retained_rate": rate(
                            semantic_rows, "supported_semantics_retained"
                        ),
                        "pixel_exact_rate_to_previous": rate(
                            comparable_rows, "pixels_exact_to_previous"
                        ),
                        "mean_absolute_error_to_previous": (
                            mean_field(
                                comparable_rows,
                                "mean_absolute_error_to_previous",
                            )
                        ),
                        "pixel_exact_rate_to_generation_zero": rate(
                            group, "pixels_exact_to_generation_zero"
                        ),
                        "mean_absolute_error_to_generation_zero": mean_field(
                            group, "mean_absolute_error_to_generation_zero"
                        ),
                        "maximum_absolute_error_to_generation_zero": str(
                            max(
                                int(
                                    row[
                                        "maximum_absolute_error_to_generation_zero"
                                    ]
                                )
                                for row in group
                            )
                        ),
                    }
                )
    return rows


def build_contracts(
    observations: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Summarize steady-state metadata and continuing image changes."""
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in observations:
        grouped[
            (row["fixture_id"], row["encoder"], row["sequence_id"])
        ].append(row)

    contracts: list[dict[str, str]] = []
    for fixture_id, encoder, sequence_id in sorted(grouped):
        ordered = sorted(
            grouped[(fixture_id, encoder, sequence_id)],
            key=lambda row: int(row["generation"]),
        )
        transition_generation = (
            2
            if sequence_id
            in (
                "preserve_then_normalize",
                "normalize_then_strip",
                "strip_then_preserve",
            )
            else 1
        )
        steady = ordered[transition_generation:]
        final = ordered[-1]
        metadata_hash_count = len(
            {row["metadata_state_sha256"] for row in steady}
        )
        contracts.append(
            {
                "fixture_id": fixture_id,
                "encoder": encoder,
                "sequence_id": sequence_id,
                "last_policy_transition_generation": str(
                    transition_generation
                ),
                "strict_accept_all_generations": str(
                    int(
                        all(
                            row["output_strict_accept"] == "1"
                            for row in ordered
                        )
                    )
                ),
                "metadata_hash_count_after_transition": str(
                    metadata_hash_count
                ),
                "metadata_stable_after_transition": str(
                    int(metadata_hash_count == 1)
                ),
                "jpeg_hash_count_after_transition": str(
                    len({row["jpeg_sha256"] for row in steady})
                ),
                "pixel_hash_count_after_transition": str(
                    len({row["output_bgr_sha256"] for row in steady})
                ),
                "original_envelope_contract_applicable": final[
                    "original_envelope_contract_applicable"
                ],
                "original_envelope_byte_exact_at_generation_10": final[
                    "original_envelope_byte_exact"
                ],
                "semantic_contract_applicable": final[
                    "semantic_contract_applicable"
                ],
                "supported_semantics_retained_at_generation_10": final[
                    "supported_semantics_retained"
                ],
                "generation_10_mean_absolute_error": final[
                    "mean_absolute_error_to_generation_zero"
                ],
                "generation_10_maximum_absolute_error": final[
                    "maximum_absolute_error_to_generation_zero"
                ],
            }
        )
    return contracts


def plot_summary(
    summary: Sequence[dict[str, str]], output_path: Path
) -> None:
    """Plot metadata retention and repeated-codec pixel drift."""
    figure, axes = plt.subplots(
        1, 3, figsize=(16, 4.9), constrained_layout=True
    )
    colors = {
        "preserve_repeat": "#4472C4",
        "strip_repeat": "#A5A5A5",
        "normalize_repeat": "#70AD47",
        "preserve_then_normalize": "#5B9BD5",
        "normalize_then_strip": "#FFC000",
        "strip_then_preserve": "#ED7D31",
    }
    generations = np.arange(MAX_GENERATION + 1)

    for sequence_id in SEQUENCES:
        sequence_rows = [
            row for row in summary if row["sequence_id"] == sequence_id
        ]
        envelope_values = []
        semantic_values = []
        for generation in generations:
            generation_rows = [
                row
                for row in sequence_rows
                if int(row["generation"]) == generation
            ]
            envelope_values.append(
                float(
                    np.mean(
                        [
                            float(row["original_envelope_exact_rate"])
                            for row in generation_rows
                        ]
                    )
                )
            )
            semantic_values.append(
                float(
                    np.mean(
                        [
                            float(
                                row[
                                    "supported_semantics_retained_rate"
                                ]
                            )
                            for row in generation_rows
                        ]
                    )
                )
            )
        axes[0].plot(
            generations,
            envelope_values,
            marker="o",
            markersize=3,
            label=sequence_id,
            color=colors[sequence_id],
        )
        axes[1].plot(
            generations,
            semantic_values,
            marker="o",
            markersize=3,
            label=sequence_id,
            color=colors[sequence_id],
        )

    axes[0].set_title("Original envelope byte retention")
    axes[0].set_ylabel("Rate across four metadata fixtures")
    axes[0].set_ylim(-0.04, 1.04)
    axes[0].set_xticks(sorted(CHECKPOINTS))
    axes[0].grid(alpha=0.25)

    axes[1].set_title("Supported EXIF / ICC retention")
    axes[1].set_ylabel("Rate across two semantic fixtures")
    axes[1].set_ylim(-0.04, 1.04)
    axes[1].set_xticks(sorted(CHECKPOINTS))
    axes[1].grid(alpha=0.25)

    line_styles = {"pillow": "-", "opencv": "--"}
    for encoder in ENCODERS:
        values = []
        for generation in generations:
            generation_rows = [
                row
                for row in summary
                if row["encoder"] == encoder
                and row["sequence_id"]
                in ("preserve_repeat", "strip_repeat", "normalize_repeat")
                and int(row["generation"]) == generation
            ]
            values.append(
                float(
                    np.mean(
                        [
                            float(
                                row[
                                    "mean_absolute_error_to_generation_zero"
                                ]
                            )
                            for row in generation_rows
                        ]
                    )
                )
            )
        axes[2].plot(
            generations,
            values,
            linestyle=line_styles[encoder],
            color="#7030A0",
            label=f"{encoder}; three repeated policies coincide",
        )
    axes[2].set_title("Policy-independent lossy drift")
    axes[2].set_ylabel("Mean absolute BGR error to generation 0")
    axes[2].set_xticks(sorted(CHECKPOINTS))
    axes[2].grid(alpha=0.25)
    axes[2].legend(fontsize=7, loc="lower right")
    axes[0].legend(fontsize=7, loc="lower right", ncol=2)
    figure.supxlabel("JPEG generation")
    figure.suptitle(
        "Multi-generation metadata policy drift and idempotence"
    )
    figure.savefig(
        output_path,
        dpi=160,
        metadata={"Software": "research-notes v0.15.0"},
    )
    plt.close(figure)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate metadata policy drift across repeated JPEG generations."
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
    """Run all temporal policy controls and write deterministic reports."""
    args = parse_args()
    fixtures = load_fixtures(args.fixture_dir)
    observations = observation_rows(
        fixtures, args.fixture_dir, args.platform_label
    )
    summary = summarize(observations)
    contracts = build_contracts(observations)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        args.output_dir / PLATFORM_MANIFEST_NAME,
        build_platform_manifest(
            args.platform_label,
            record_runner_image=args.record_runner_image,
        ),
    )
    write_csv(
        args.output_dir / OBSERVATIONS_NAME,
        observations,
        OBSERVATION_FIELDS,
    )
    write_csv(args.output_dir / SUMMARY_NAME, summary)
    write_csv(args.output_dir / CONTRACTS_NAME, contracts)
    plot_summary(summary, args.output_dir / FIGURE_NAME)
    print(
        "JPEG metadata generation evaluation complete: "
        f"{len(fixtures)} fixtures, {len(ENCODERS)} encoders, "
        f"{len(SEQUENCES)} policy sequences, "
        f"{MAX_GENERATION + 1} generations, "
        f"{len(observations)} observations."
    )


if __name__ == "__main__":
    main()
