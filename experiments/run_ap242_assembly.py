"""Evaluate controlled AP242 assembly occurrences, placements, and units."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

from research_notes import (  # noqa: E402
    AP242AssemblyFixture,
    build_ap242_assembly_fixtures,
    inspect_ap242_assembly_fixture,
)


MANIFEST_NAME = "manifest.csv"
OBSERVATIONS_NAME = "ap242_assembly_observations.csv"
OCCURRENCES_NAME = "ap242_assembly_occurrences.csv"
PATHS_NAME = "ap242_assembly_paths.csv"
RELATIONS_NAME = "ap242_assembly_relations.csv"
UNITS_NAME = "ap242_assembly_units.csv"
DIAGNOSTICS_NAME = "ap242_assembly_diagnostics.csv"
SUMMARY_NAME = "ap242_assembly_summary.csv"
JSON_NAME = "ap242_assembly.json"
FIGURE_NAME = "ap242_assembly_paths.png"

MANIFEST_FIELDS = (
    "fixture",
    "category",
    "condition",
    "file_name",
    "expected_decision",
    "expected_reason_code",
    "source_bytes",
    "source_sha256",
    "max_occurrences",
    "max_paths",
    "max_relations",
    "max_depth",
    "max_unit_hops",
)
OBSERVATION_FIELDS = (
    "fixture",
    "category",
    "condition",
    "expected_decision",
    "observed_decision",
    "expectation_met",
    "expected_reason_code",
    "reason_code",
    "schema_identifier",
    "occurrence_count",
    "path_count",
    "relation_count",
    "unit_observation_count",
    "distinct_definition_count",
    "reused_definition_count",
    "maximum_depth",
    "diagnostic_count",
    "source_sha256",
)
OCCURRENCE_FIELDS = (
    "fixture",
    "occurrence_index",
    "entity_id",
    "identifier",
    "name",
    "reference_designator",
    "parent_product_definition_entity_id",
    "child_product_definition_entity_id",
    "parent_representation_entity_id",
    "child_representation_entity_id",
    "transformation_entity_id",
    "source_placement_entity_id",
    "target_placement_entity_id",
    "child_unit_name",
    "child_scale_to_millimetre",
    "parent_unit_name",
    "parent_scale_to_millimetre",
    "local_translation_x_mm",
    "local_translation_y_mm",
    "local_translation_z_mm",
    "local_rotation",
    "rotation_determinant",
    "source_line",
)
PATH_FIELDS = (
    "fixture",
    "path_index",
    "root_product_definition_entity_id",
    "leaf_product_definition_entity_id",
    "depth",
    "occurrence_indices",
    "occurrence_entity_ids",
    "reference_designators",
    "global_translation_x_mm",
    "global_translation_y_mm",
    "global_translation_z_mm",
    "global_rotation",
    "rotation_determinant",
)
RELATION_FIELDS = (
    "fixture",
    "occurrence_index",
    "role",
    "source_entity_id",
    "target_entity_id",
    "source_edge_index",
    "parameter_path",
    "source_line",
    "source_column",
)
UNIT_FIELDS = (
    "fixture",
    "occurrence_index",
    "side",
    "representation_entity_id",
    "unit_entity_id",
    "unit_name",
    "unit_form",
    "scale_to_millimetre",
    "conversion_hops",
    "source_line",
)
DIAGNOSTIC_FIELDS = (
    "fixture",
    "diagnostic_index",
    "severity",
    "reason_code",
    "role",
    "entity_id",
    "source_line",
    "detail",
)
SUMMARY_FIELDS = ("scope", "metric", "value")


def write_csv(
    path: Path, rows: Sequence[dict[str, str]], fields: Sequence[str]
) -> None:
    """Write deterministic UTF-8 CSV evidence, including an empty header."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _numbers(values: Sequence[float]) -> str:
    return "|".join(f"{value:.12g}" for value in values)


def manifest_rows(
    fixtures: Sequence[AP242AssemblyFixture],
) -> list[dict[str, str]]:
    """Describe exact inputs, expected routes, hashes, and work budgets."""
    rows: list[dict[str, str]] = []
    for fixture in fixtures:
        limits = fixture.assembly_limits
        rows.append(
            {
                "fixture": fixture.fixture,
                "category": fixture.category,
                "condition": fixture.condition,
                "file_name": fixture.file_name,
                "expected_decision": fixture.expected_decision,
                "expected_reason_code": fixture.expected_reason_code,
                "source_bytes": str(len(fixture.source_bytes)),
                "source_sha256": hashlib.sha256(fixture.source_bytes).hexdigest(),
                "max_occurrences": str(limits.max_occurrences),
                "max_paths": str(limits.max_paths),
                "max_relations": str(limits.max_relations),
                "max_depth": str(limits.max_depth),
                "max_unit_hops": str(limits.max_unit_hops),
            }
        )
    return rows


def refresh_fixture_corpus(
    fixture_dir: Path, fixtures: Sequence[AP242AssemblyFixture]
) -> None:
    """Write deterministic STEP fixtures without deleting unknown files."""
    fixture_dir.mkdir(parents=True, exist_ok=True)
    expected = {fixture.file_name for fixture in fixtures}
    existing = {
        path.name for path in fixture_dir.iterdir() if path.name != MANIFEST_NAME
    }
    unexpected = sorted(existing - expected)
    if unexpected:
        raise RuntimeError(
            "fixture directory contains unexpected files: " + ", ".join(unexpected)
        )
    for fixture in fixtures:
        (fixture_dir / fixture.file_name).write_bytes(fixture.source_bytes)
    write_csv(fixture_dir / MANIFEST_NAME, manifest_rows(fixtures), MANIFEST_FIELDS)


def load_fixture_corpus(
    fixture_dir: Path, fixtures: Sequence[AP242AssemblyFixture]
) -> tuple[AP242AssemblyFixture, ...]:
    """Load committed fixture bytes after exact manifest and content checks."""
    manifest_path = fixture_dir / MANIFEST_NAME
    if not manifest_path.is_file():
        raise RuntimeError(
            f"missing fixture manifest: {manifest_path}; use --refresh-fixtures"
        )
    with manifest_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if rows != manifest_rows(fixtures):
        raise RuntimeError("committed fixture manifest does not match definitions")
    for fixture in fixtures:
        if (fixture_dir / fixture.file_name).read_bytes() != fixture.source_bytes:
            raise RuntimeError(f"fixture differs from definition: {fixture.file_name}")
    return tuple(fixtures)


def build_rows(fixtures: Sequence[AP242AssemblyFixture]):
    """Run the corpus and expand assembly evidence into stable tables."""
    observations: list[dict[str, str]] = []
    occurrences: list[dict[str, str]] = []
    paths: list[dict[str, str]] = []
    relations: list[dict[str, str]] = []
    units: list[dict[str, str]] = []
    diagnostics: list[dict[str, str]] = []
    json_records: list[dict[str, object]] = []
    for fixture in fixtures:
        observation = inspect_ap242_assembly_fixture(fixture)
        result = observation.result
        source_hash = hashlib.sha256(fixture.source_bytes).hexdigest()
        observations.append(
            {
                "fixture": fixture.fixture,
                "category": fixture.category,
                "condition": fixture.condition,
                "expected_decision": fixture.expected_decision,
                "observed_decision": observation.decision,
                "expectation_met": str(
                    int(
                        observation.decision == fixture.expected_decision
                        and observation.reason_code == fixture.expected_reason_code
                    )
                ),
                "expected_reason_code": fixture.expected_reason_code,
                "reason_code": observation.reason_code,
                "schema_identifier": (
                    ""
                    if result is None or result.schema_identifier is None
                    else result.schema_identifier
                ),
                "occurrence_count": str(observation.occurrence_count),
                "path_count": str(observation.path_count),
                "relation_count": str(observation.relation_count),
                "unit_observation_count": str(observation.unit_observation_count),
                "distinct_definition_count": str(observation.distinct_definition_count),
                "reused_definition_count": str(observation.reused_definition_count),
                "maximum_depth": str(observation.maximum_depth),
                "diagnostic_count": str(observation.diagnostic_count),
                "source_sha256": source_hash,
            }
        )
        fixture_json: dict[str, object] = {
            "fixture": fixture.fixture,
            "decision": observation.decision,
            "reason_code": observation.reason_code,
            "source_sha256": source_hash,
            "occurrences": [],
            "paths": [],
        }
        if result is None:
            json_records.append(fixture_json)
            continue
        for occurrence in result.occurrences:
            x, y, z = occurrence.local_translation_mm
            occurrences.append(
                {
                    "fixture": fixture.fixture,
                    "occurrence_index": str(occurrence.occurrence_index),
                    "entity_id": str(occurrence.entity_id),
                    "identifier": occurrence.identifier,
                    "name": occurrence.name,
                    "reference_designator": occurrence.reference_designator,
                    "parent_product_definition_entity_id": str(occurrence.parent_product_definition_entity_id),
                    "child_product_definition_entity_id": str(occurrence.child_product_definition_entity_id),
                    "parent_representation_entity_id": str(occurrence.parent_representation_entity_id),
                    "child_representation_entity_id": str(occurrence.child_representation_entity_id),
                    "transformation_entity_id": str(occurrence.transformation_entity_id),
                    "source_placement_entity_id": str(occurrence.source_placement_entity_id),
                    "target_placement_entity_id": str(occurrence.target_placement_entity_id),
                    "child_unit_name": occurrence.child_unit_name,
                    "child_scale_to_millimetre": f"{occurrence.child_scale_to_millimetre:.12g}",
                    "parent_unit_name": occurrence.parent_unit_name,
                    "parent_scale_to_millimetre": f"{occurrence.parent_scale_to_millimetre:.12g}",
                    "local_translation_x_mm": f"{x:.12g}",
                    "local_translation_y_mm": f"{y:.12g}",
                    "local_translation_z_mm": f"{z:.12g}",
                    "local_rotation": _numbers(occurrence.local_rotation),
                    "rotation_determinant": f"{occurrence.rotation_determinant:.12g}",
                    "source_line": str(occurrence.source_span.start_line),
                }
            )
            fixture_json["occurrences"].append(
                {
                    "occurrence_index": occurrence.occurrence_index,
                    "reference_designator": occurrence.reference_designator,
                    "parent_product_definition_entity_id": occurrence.parent_product_definition_entity_id,
                    "child_product_definition_entity_id": occurrence.child_product_definition_entity_id,
                    "local_matrix": list(occurrence.local_matrix),
                    "local_translation_mm": list(occurrence.local_translation_mm),
                }
            )
        for path in result.paths:
            x, y, z = path.global_translation_mm
            paths.append(
                {
                    "fixture": fixture.fixture,
                    "path_index": str(path.path_index),
                    "root_product_definition_entity_id": str(path.root_product_definition_entity_id),
                    "leaf_product_definition_entity_id": str(path.leaf_product_definition_entity_id),
                    "depth": str(path.depth),
                    "occurrence_indices": "|".join(map(str, path.occurrence_indices)),
                    "occurrence_entity_ids": "|".join(map(str, path.occurrence_entity_ids)),
                    "reference_designators": "/".join(path.reference_designators),
                    "global_translation_x_mm": f"{x:.12g}",
                    "global_translation_y_mm": f"{y:.12g}",
                    "global_translation_z_mm": f"{z:.12g}",
                    "global_rotation": _numbers(path.global_rotation),
                    "rotation_determinant": f"{path.rotation_determinant:.12g}",
                }
            )
            fixture_json["paths"].append(
                {
                    "path_index": path.path_index,
                    "reference_designators": list(path.reference_designators),
                    "global_matrix": list(path.global_matrix),
                    "global_translation_mm": list(path.global_translation_mm),
                }
            )
        for relation in result.relations:
            relations.append(
                {
                    "fixture": fixture.fixture,
                    "occurrence_index": str(relation.occurrence_index),
                    "role": relation.role,
                    "source_entity_id": str(relation.source_entity_id),
                    "target_entity_id": str(relation.target_entity_id),
                    "source_edge_index": str(relation.source_edge_index),
                    "parameter_path": ".".join(map(str, relation.parameter_path)),
                    "source_line": str(relation.source_span.start_line),
                    "source_column": str(relation.source_span.start_column),
                }
            )
        for unit in result.units:
            units.append(
                {
                    "fixture": fixture.fixture,
                    "occurrence_index": str(unit.occurrence_index),
                    "side": unit.side,
                    "representation_entity_id": str(unit.representation_entity_id),
                    "unit_entity_id": str(unit.unit_entity_id),
                    "unit_name": unit.unit_name,
                    "unit_form": unit.unit_form,
                    "scale_to_millimetre": f"{unit.scale_to_millimetre:.12g}",
                    "conversion_hops": str(unit.conversion_hops),
                    "source_line": str(unit.source_span.start_line),
                }
            )
        for diagnostic_index, diagnostic in enumerate(result.diagnostics):
            diagnostics.append(
                {
                    "fixture": fixture.fixture,
                    "diagnostic_index": str(diagnostic_index),
                    "severity": diagnostic.severity,
                    "reason_code": diagnostic.reason_code,
                    "role": diagnostic.role,
                    "entity_id": "" if diagnostic.entity_id is None else str(diagnostic.entity_id),
                    "source_line": "" if diagnostic.source_line is None else str(diagnostic.source_line),
                    "detail": diagnostic.detail,
                }
            )
        json_records.append(fixture_json)
    return observations, occurrences, paths, relations, units, diagnostics, json_records


def summary_rows(
    observations: Sequence[dict[str, str]],
    occurrences: Sequence[dict[str, str]],
    paths: Sequence[dict[str, str]],
    relations: Sequence[dict[str, str]],
    units: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Summarize declared routes and controlled evidence counts."""
    decisions = Counter(row["observed_decision"] for row in observations)
    accepted_names = {
        row["fixture"] for row in observations if row["observed_decision"] == "accept"
    }
    accepted_paths = [row for row in paths if row["fixture"] in accepted_names]
    return [
        {"scope": "corpus", "metric": "fixture_count", "value": str(len(observations))},
        {"scope": "corpus", "metric": "expectation_mismatch_count", "value": str(sum(row["expectation_met"] != "1" for row in observations))},
        *(
            {"scope": "decision", "metric": decision, "value": str(decisions[decision])}
            for decision in ("accept", "quarantine", "reject")
        ),
        {"scope": "accepted", "metric": "occurrence_count", "value": str(sum(row["fixture"] in accepted_names for row in occurrences))},
        {"scope": "accepted", "metric": "path_count", "value": str(len(accepted_paths))},
        {"scope": "accepted", "metric": "maximum_depth", "value": str(max((int(row["depth"]) for row in accepted_paths), default=0))},
        {"scope": "accepted", "metric": "physical_relation_count", "value": str(sum(row["fixture"] in accepted_names for row in relations))},
        {"scope": "accepted", "metric": "unit_observation_count", "value": str(sum(row["fixture"] in accepted_names for row in units))},
        {"scope": "accepted", "metric": "conversion_based_unit_count", "value": str(sum(row["fixture"] in accepted_names and row["unit_form"] == "conversion_based" for row in units))},
    ]


def plot_results(
    observations: Sequence[dict[str, str]],
    paths: Sequence[dict[str, str]],
    output_path: Path,
) -> None:
    """Plot declared route counts and the evaluated nested coordinate frames."""
    decisions = Counter(row["observed_decision"] for row in observations)
    nested = [row for row in paths if row["fixture"] == "nested_reuse"]
    colors = {"accept": "#2A9D8F", "quarantine": "#E9C46A", "reject": "#E76F51"}
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    labels = ["accept", "quarantine", "reject"]
    axes[0].bar(labels, [decisions[label] for label in labels], color=[colors[label] for label in labels])
    axes[0].set_ylabel("Fixture count")
    axes[0].set_title("Declared evaluation routes")
    axes[0].grid(axis="y", alpha=0.25)
    for row in nested:
        x = float(row["global_translation_x_mm"])
        y = float(row["global_translation_y_mm"])
        label = row["reference_designators"]
        axes[1].scatter(x, y, s=70, color="#264653")
        axes[1].annotate(label, (x, y), xytext=(5, 6), textcoords="offset points")
    axes[1].scatter(0.0, 0.0, marker="s", s=90, color="#E76F51", label="root")
    axes[1].set_aspect("equal", adjustable="datalim")
    axes[1].set_xlabel("Root-frame x (mm)")
    axes[1].set_ylabel("Root-frame y (mm)")
    axes[1].set_title("Nested reuse: evaluated origins")
    axes[1].grid(alpha=0.25)
    axes[1].legend()
    fig.suptitle("AP242 assembly occurrence evaluation")
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    """Parse deterministic fixture and output locations."""
    parser = argparse.ArgumentParser(
        description="Evaluate controlled AP242 assembly occurrences and placements."
    )
    parser.add_argument(
        "--fixture-dir", type=Path, default=Path("fixtures/ap242-assemblies")
    )
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument("--refresh-fixtures", action="store_true")
    return parser.parse_args()


def main() -> None:
    """Regenerate or verify fixtures and write all controlled evidence."""
    args = parse_args()
    definitions = build_ap242_assembly_fixtures()
    if args.refresh_fixtures:
        refresh_fixture_corpus(args.fixture_dir, definitions)
    fixtures = load_fixture_corpus(args.fixture_dir, definitions)
    rows = build_rows(fixtures)
    observations, occurrences, paths, relations, units, diagnostics, records = rows
    mismatches = [row["fixture"] for row in observations if row["expectation_met"] != "1"]
    if mismatches:
        raise RuntimeError("fixture expectations failed: " + ", ".join(mismatches))
    write_csv(args.output_dir / OBSERVATIONS_NAME, observations, OBSERVATION_FIELDS)
    write_csv(args.output_dir / OCCURRENCES_NAME, occurrences, OCCURRENCE_FIELDS)
    write_csv(args.output_dir / PATHS_NAME, paths, PATH_FIELDS)
    write_csv(args.output_dir / RELATIONS_NAME, relations, RELATION_FIELDS)
    write_csv(args.output_dir / UNITS_NAME, units, UNIT_FIELDS)
    write_csv(args.output_dir / DIAGNOSTICS_NAME, diagnostics, DIAGNOSTIC_FIELDS)
    write_csv(
        args.output_dir / SUMMARY_NAME,
        summary_rows(observations, occurrences, paths, relations, units),
        SUMMARY_FIELDS,
    )
    (args.output_dir / JSON_NAME).write_text(
        json.dumps(
            {
                "schema": "research-notes.ap242-assembly",
                "version": "1.0",
                "canonical_length_unit": "millimetre",
                "fixtures": records,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    plot_results(observations, paths, args.output_dir / FIGURE_NAME)
    print(
        f"Evaluated {len(fixtures)} fixtures; wrote deterministic evidence to {args.output_dir}."
    )


if __name__ == "__main__":
    main()
