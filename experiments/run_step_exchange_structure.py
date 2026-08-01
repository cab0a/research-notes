"""Evaluate advanced Part 21 exchange structure and parser boundaries."""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402

from research_notes import (  # noqa: E402
    STEPExchangeFixture,
    build_step_exchange_fixtures,
    inspect_step_exchange,
    parse_step_exchange,
)


MANIFEST_NAME = "manifest.csv"
OBSERVATIONS_NAME = "step_part21_exchange_observations.csv"
SECTIONS_NAME = "step_part21_data_sections.csv"
SUMMARY_NAME = "step_part21_exchange_summary.csv"
FIGURE_NAME = "step_part21_exchange_boundaries.png"
GEOMETRY_PREVIEW_NAME = "step_part21_geometry_control.png"

MANIFEST_FIELDS = (
    "fixture",
    "condition",
    "file_name",
    "expected_decision",
    "expected_reason_code",
    "expected_data_sections",
    "expected_entities",
    "expected_complex_entities",
    "expected_anchors",
    "expected_external_references",
    "expected_signatures",
    "source_bytes",
    "source_sha256",
)
OBSERVATION_FIELDS = (
    "fixture",
    "condition",
    "file_name",
    "expected_decision",
    "observed_decision",
    "expectation_met",
    "expected_reason_code",
    "reason_code",
    "container",
    "schema_identifiers",
    "data_section_count",
    "named_data_section_count",
    "entity_count",
    "simple_entity_count",
    "complex_entity_count",
    "anchor_count",
    "anchor_tag_count",
    "external_reference_count",
    "signature_count",
    "signature_payload_bytes",
    "local_reference_count",
    "unresolved_local_reference_count",
    "schema_conformance",
    "external_resolution",
    "signature_verification",
    "source_bytes",
    "source_sha256",
)
SECTION_FIELDS = (
    "fixture",
    "section_index",
    "section_name",
    "schema_identifier",
    "entity_count",
    "simple_entity_count",
    "complex_entity_count",
)
SUMMARY_FIELDS = ("scope", "metric", "value")


def write_csv(
    path: Path,
    rows: Sequence[dict[str, str]],
    fieldnames: Sequence[str],
    *,
    allow_empty: bool = False,
) -> None:
    """Write deterministic UTF-8 CSV rows."""
    if not rows and not allow_empty:
        raise ValueError("rows must not be empty")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(fieldnames), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def fixture_manifest_rows(
    fixtures: Sequence[STEPExchangeFixture],
) -> list[dict[str, str]]:
    """Describe fixture bytes and expected structural decisions."""
    rows = []
    for fixture in fixtures:
        rows.append(
            {
                "fixture": fixture.fixture,
                "condition": fixture.condition,
                "file_name": fixture.file_name,
                "expected_decision": fixture.expected_decision,
                "expected_reason_code": fixture.expected_reason_code,
                "expected_data_sections": str(fixture.expected_data_sections),
                "expected_entities": str(fixture.expected_entities),
                "expected_complex_entities": str(
                    fixture.expected_complex_entities
                ),
                "expected_anchors": str(fixture.expected_anchors),
                "expected_external_references": str(
                    fixture.expected_external_references
                ),
                "expected_signatures": str(fixture.expected_signatures),
                "source_bytes": str(len(fixture.source_bytes)),
                "source_sha256": hashlib.sha256(
                    fixture.source_bytes
                ).hexdigest(),
            }
        )
    return rows


def refresh_fixture_corpus(
    fixture_dir: Path, fixtures: Sequence[STEPExchangeFixture]
) -> None:
    """Write the complete deterministic fixture corpus."""
    fixture_dir.mkdir(parents=True, exist_ok=True)
    expected_names = {fixture.file_name for fixture in fixtures}
    existing_names = {
        path.name for path in fixture_dir.iterdir() if path.name != MANIFEST_NAME
    }
    unexpected = sorted(existing_names - expected_names)
    if unexpected:
        raise RuntimeError(
            "fixture directory contains unexpected files: " + ", ".join(unexpected)
        )
    for fixture in fixtures:
        (fixture_dir / fixture.file_name).write_bytes(fixture.source_bytes)
    write_csv(
        fixture_dir / MANIFEST_NAME,
        fixture_manifest_rows(fixtures),
        MANIFEST_FIELDS,
    )


def load_fixture_corpus(
    fixture_dir: Path, fixtures: Sequence[STEPExchangeFixture]
) -> tuple[STEPExchangeFixture, ...]:
    """Load committed fixtures after exact manifest and byte checks."""
    manifest_path = fixture_dir / MANIFEST_NAME
    if not manifest_path.is_file():
        raise RuntimeError(
            f"missing fixture manifest: {manifest_path}; use --refresh-fixtures"
        )
    with manifest_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if rows != fixture_manifest_rows(fixtures):
        raise RuntimeError("committed fixture manifest does not match definitions")

    loaded = []
    for fixture in fixtures:
        path = fixture_dir / fixture.file_name
        if not path.is_file():
            raise RuntimeError(f"missing Part 21 fixture: {path}")
        source_bytes = path.read_bytes()
        if source_bytes != fixture.source_bytes:
            raise RuntimeError(f"fixture differs from definition: {path.name}")
        loaded.append(
            STEPExchangeFixture(
                **{**vars(fixture), "source_bytes": source_bytes}
            )
        )
    return tuple(loaded)


def collect_results(
    fixtures: Sequence[STEPExchangeFixture],
) -> dict[str, list[dict[str, str]]]:
    """Inspect every fixture and return deterministic observation rows."""
    observations: list[dict[str, str]] = []
    sections: list[dict[str, str]] = []
    for fixture in fixtures:
        result = inspect_step_exchange(fixture.source_bytes)
        expectation_met = (
            result.decision == fixture.expected_decision
            and result.reason_code == fixture.expected_reason_code
        )
        observations.append(
            {
                "fixture": fixture.fixture,
                "condition": fixture.condition,
                "file_name": fixture.file_name,
                "expected_decision": fixture.expected_decision,
                "observed_decision": result.decision,
                "expectation_met": str(int(expectation_met)),
                "expected_reason_code": fixture.expected_reason_code,
                "reason_code": result.reason_code,
                "container": result.container,
                "schema_identifiers": "|".join(result.schema_identifiers),
                "data_section_count": str(result.data_section_count),
                "named_data_section_count": str(
                    result.named_data_section_count
                ),
                "entity_count": str(result.entity_count),
                "simple_entity_count": str(result.simple_entity_count),
                "complex_entity_count": str(result.complex_entity_count),
                "anchor_count": str(result.anchor_count),
                "anchor_tag_count": str(result.anchor_tag_count),
                "external_reference_count": str(
                    result.external_reference_count
                ),
                "signature_count": str(result.signature_count),
                "signature_payload_bytes": str(
                    result.signature_payload_bytes
                ),
                "local_reference_count": str(result.local_reference_count),
                "unresolved_local_reference_count": str(
                    result.unresolved_local_reference_count
                ),
                "schema_conformance": result.schema_conformance,
                "external_resolution": result.external_resolution,
                "signature_verification": result.signature_verification,
                "source_bytes": str(len(fixture.source_bytes)),
                "source_sha256": hashlib.sha256(
                    fixture.source_bytes
                ).hexdigest(),
            }
        )
        try:
            document = parse_step_exchange(fixture.source_bytes)
        except ValueError:
            continue
        for index, section in enumerate(document.data_sections):
            sections.append(
                {
                    "fixture": fixture.fixture,
                    "section_index": str(index),
                    "section_name": section.name or "",
                    "schema_identifier": section.schema_identifier or "",
                    "entity_count": str(len(section.entities)),
                    "simple_entity_count": str(
                        sum(not entity.is_complex for entity in section.entities)
                    ),
                    "complex_entity_count": str(
                        sum(entity.is_complex for entity in section.entities)
                    ),
                }
            )
    _validate_results(observations)
    return {"observations": observations, "sections": sections}


def _validate_results(observations: Sequence[dict[str, str]]) -> None:
    """Enforce the controlled corpus expectations."""
    if len(observations) != 13:
        raise RuntimeError("expected thirteen advanced Part 21 fixtures")
    if any(row["expectation_met"] != "1" for row in observations):
        raise RuntimeError("an advanced Part 21 expectation failed")
    decisions = Counter(row["observed_decision"] for row in observations)
    if decisions != {"accept": 5, "quarantine": 4, "reject": 4}:
        raise RuntimeError(f"unexpected decision totals: {dict(decisions)}")


def summarize(
    collected: dict[str, list[dict[str, str]]],
) -> list[dict[str, str]]:
    """Build corpus-level and feature-level summary rows."""
    observations = collected["observations"]
    decisions = Counter(row["observed_decision"] for row in observations)
    rows = [
        {"scope": "corpus", "metric": "fixture_count", "value": "13"},
        {"scope": "corpus", "metric": "expectation_rate", "value": "1.000000"},
    ]
    rows.extend(
        {
            "scope": "corpus",
            "metric": f"decision_{decision}",
            "value": str(decisions.get(decision, 0)),
        }
        for decision in ("accept", "quarantine", "reject")
    )
    feature_fixtures = (
        "single_data_control",
        "multiple_data_sections",
        "complex_entity_instance",
        "utf8_binary_values",
        "anchor_with_tag",
        "external_reference",
        "signature_present",
        "zip_archive",
    )
    by_name = {row["fixture"]: row for row in observations}
    for fixture in feature_fixtures:
        row = by_name[fixture]
        rows.append(
            {
                "scope": fixture,
                "metric": "decision",
                "value": row["observed_decision"],
            }
        )
        rows.append(
            {
                "scope": fixture,
                "metric": "reason_code",
                "value": row["reason_code"],
            }
        )
    return rows


def plot_boundaries(
    collected: dict[str, list[dict[str, str]]], output_path: Path
) -> None:
    """Visualize feature recognition and fail-closed boundaries."""
    observations = collected["observations"]
    labels = [row["fixture"].replace("_", "\n") for row in observations]
    decision_value = {"accept": 3, "quarantine": 2, "reject": 1}
    decision_color = {
        "accept": "#2a9d8f",
        "quarantine": "#e9c46a",
        "reject": "#e76f51",
    }
    figure, axes = plt.subplots(2, 1, figsize=(14.5, 9.0))
    x_positions = np.arange(len(observations))
    axes[0].bar(
        x_positions,
        [decision_value[row["observed_decision"]] for row in observations],
        color=[decision_color[row["observed_decision"]] for row in observations],
    )
    axes[0].set_xticks(x_positions, labels, fontsize=8)
    axes[0].set_yticks((1, 2, 3), ("reject", "quarantine", "accept"))
    axes[0].set_ylim(0.8, 3.35)
    axes[0].set_title("Structural acceptance is separate from trust-boundary use")
    axes[0].grid(axis="y", alpha=0.25)

    selected_names = (
        "single_data_control",
        "multiple_data_sections",
        "complex_entity_instance",
        "anchor_with_tag",
        "external_reference",
        "signature_present",
    )
    selected = [
        next(row for row in observations if row["fixture"] == name)
        for name in selected_names
    ]
    selected_labels = [row["fixture"].replace("_", "\n") for row in selected]
    selected_x = np.arange(len(selected))
    metrics = (
        ("data_section_count", "DATA sections", "#457b9d"),
        ("complex_entity_count", "complex entities", "#6d597a"),
        ("anchor_count", "anchors", "#2a9d8f"),
        ("external_reference_count", "external references", "#e76f51"),
        ("signature_count", "signatures", "#f4a261"),
    )
    bottoms = np.zeros(len(selected))
    for metric, label, color in metrics:
        values = np.array([int(row[metric]) for row in selected])
        axes[1].bar(
            selected_x,
            values,
            bottom=bottoms,
            label=label,
            color=color,
        )
        bottoms += values
    axes[1].set_xticks(selected_x, selected_labels, fontsize=9)
    axes[1].set_ylabel("Recognized structures")
    axes[1].set_title("The inventory records syntax without resolving external trust")
    axes[1].legend(ncols=3)
    axes[1].grid(axis="y", alpha=0.25)

    figure.suptitle(
        "Advanced Part 21 Exchange Structure and Parser Boundaries",
        fontsize=14,
        fontweight="bold",
    )
    figure.text(
        0.5,
        0.012,
        "External resources are not fetched, signatures are not verified, and ZIP containers are not opened.",
        ha="center",
        fontsize=9,
    )
    figure.tight_layout(rect=(0, 0.035, 1, 0.96))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def plot_geometry_control(output_path: Path) -> None:
    """Render the synthetic tetrahedron used as the viewable STEP control."""
    vertices = np.array(
        (
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
        )
    )
    face_indices = ((0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3))
    faces = [vertices[list(indices)] for indices in face_indices]
    figure = plt.figure(figsize=(8.0, 7.0))
    axis = figure.add_subplot(111, projection="3d")
    collection = Poly3DCollection(
        faces,
        facecolors=("#8ecae6", "#90be6d", "#f9c74f", "#f9844a"),
        edgecolors="#264653",
        linewidths=1.8,
        alpha=0.58,
    )
    axis.add_collection3d(collection)
    axis.scatter(
        vertices[:, 0], vertices[:, 1], vertices[:, 2], color="#1d3557", s=45
    )
    for index, vertex in enumerate(vertices):
        axis.text(*vertex, f"  V{index}", fontsize=9)
    axis.set(xlabel="X", ylabel="Y", zlabel="Z")
    axis.set_xlim(-0.1, 1.1)
    axis.set_ylim(-0.1, 1.1)
    axis.set_zlim(-0.1, 1.1)
    axis.set_box_aspect((1, 1, 1))
    axis.view_init(elev=24, azim=35)
    axis.set_title("Geometry control: closed tetrahedron\n4 faces · 6 edges · 1 shell · 1 solid")
    figure.text(
        0.5,
        0.025,
        "Preview of the independently declared synthetic coordinates; not a geometry-validation result.",
        ha="center",
        fontsize=9,
    )
    figure.tight_layout(rect=(0, 0.05, 1, 1))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Evaluate advanced Part 21 exchange structure boundaries."
    )
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=Path("fixtures/step-part21-exchange"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument("--refresh-fixtures", action="store_true")
    return parser.parse_args()


def main() -> None:
    """Run the controlled experiment and write deterministic artifacts."""
    args = parse_args()
    definitions = build_step_exchange_fixtures()
    if args.refresh_fixtures:
        refresh_fixture_corpus(args.fixture_dir, definitions)
    fixtures = load_fixture_corpus(args.fixture_dir, definitions)
    collected = collect_results(fixtures)
    summary = summarize(collected)
    write_csv(
        args.output_dir / OBSERVATIONS_NAME,
        collected["observations"],
        OBSERVATION_FIELDS,
    )
    write_csv(
        args.output_dir / SECTIONS_NAME,
        collected["sections"],
        SECTION_FIELDS,
    )
    write_csv(args.output_dir / SUMMARY_NAME, summary, SUMMARY_FIELDS)
    plot_boundaries(collected, args.output_dir / FIGURE_NAME)
    plot_geometry_control(args.output_dir / GEOMETRY_PREVIEW_NAME)
    print(f"Wrote {args.output_dir / OBSERVATIONS_NAME}")
    print(f"Wrote {args.output_dir / SECTIONS_NAME}")
    print(f"Wrote {args.output_dir / SUMMARY_NAME}")
    print(f"Wrote {args.output_dir / FIGURE_NAME}")
    print(f"Wrote {args.output_dir / GEOMETRY_PREVIEW_NAME}")


if __name__ == "__main__":
    main()
