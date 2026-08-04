"""Evaluate controlled AP242 product-to-representation paths."""

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
    AP242PathFixture,
    build_ap242_path_fixtures,
    inspect_ap242_path_fixture,
)


MANIFEST_NAME = "manifest.csv"
OBSERVATIONS_NAME = "ap242_path_observations.csv"
PATHS_NAME = "ap242_product_paths.csv"
RELATIONS_NAME = "ap242_semantic_relations.csv"
ITEMS_NAME = "ap242_representation_items.csv"
UNITS_NAME = "ap242_context_units.csv"
DIAGNOSTICS_NAME = "ap242_path_diagnostics.csv"
SUMMARY_NAME = "ap242_path_summary.csv"
JSON_NAME = "ap242_product_paths.json"
FIGURE_NAME = "ap242_product_paths.png"

MANIFEST_FIELDS = (
    "fixture",
    "category",
    "condition",
    "file_name",
    "expected_decision",
    "expected_reason_code",
    "source_bytes",
    "source_sha256",
    "max_product_definitions",
    "max_paths",
    "max_relations",
    "max_representation_items",
    "max_units",
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
    "product_definition_count",
    "path_count",
    "relation_count",
    "representation_item_count",
    "placement_count",
    "unit_count",
    "diagnostic_count",
    "source_sha256",
)
PATH_FIELDS = (
    "fixture",
    "path_index",
    "product_entity_id",
    "product_identifier",
    "product_name",
    "formation_entity_id",
    "formation_identifier",
    "product_definition_entity_id",
    "product_definition_identifier",
    "product_definition_context_entity_id",
    "product_definition_shape_entity_id",
    "shape_definition_representation_entity_id",
    "representation_entity_id",
    "representation_type",
    "representation_name",
    "representation_context_entity_id",
    "context_identifier",
    "context_type",
    "coordinate_space_dimension",
    "representation_item_count",
    "placement_count",
    "unit_count",
    "source_line",
)
RELATION_FIELDS = (
    "fixture",
    "path_index",
    "role",
    "source_entity_id",
    "target_entity_id",
    "source_edge_index",
    "parameter_path",
    "source_line",
    "source_column",
)
ITEM_FIELDS = (
    "fixture",
    "path_index",
    "item_index",
    "entity_id",
    "role",
    "record_types",
    "name",
    "source_line",
)
UNIT_FIELDS = (
    "fixture",
    "path_index",
    "unit_index",
    "entity_id",
    "unit_kind",
    "si_prefix",
    "si_name",
    "record_types",
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
    """Write deterministic UTF-8 CSV evidence, including an empty table header."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def manifest_rows(fixtures: Sequence[AP242PathFixture]) -> list[dict[str, str]]:
    """Describe exact AP242 inputs, expected routes, hashes, and work budgets."""
    rows: list[dict[str, str]] = []
    for fixture in fixtures:
        limits = fixture.path_limits
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
                "max_product_definitions": str(limits.max_product_definitions),
                "max_paths": str(limits.max_paths),
                "max_relations": str(limits.max_relations),
                "max_representation_items": str(limits.max_representation_items),
                "max_units": str(limits.max_units),
            }
        )
    return rows


def refresh_fixture_corpus(
    fixture_dir: Path, fixtures: Sequence[AP242PathFixture]
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
    fixture_dir: Path, fixtures: Sequence[AP242PathFixture]
) -> tuple[AP242PathFixture, ...]:
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


def build_rows(fixtures: Sequence[AP242PathFixture]):
    """Run the corpus and expand paths, relations, items, units, and diagnostics."""
    observations: list[dict[str, str]] = []
    paths: list[dict[str, str]] = []
    relations: list[dict[str, str]] = []
    items: list[dict[str, str]] = []
    units: list[dict[str, str]] = []
    diagnostics: list[dict[str, str]] = []
    json_records: list[dict[str, object]] = []
    for fixture in fixtures:
        observation = inspect_ap242_path_fixture(fixture)
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
                    "" if result is None or result.schema_identifier is None else result.schema_identifier
                ),
                "product_definition_count": str(observation.product_definition_count),
                "path_count": str(observation.path_count),
                "relation_count": str(observation.relation_count),
                "representation_item_count": str(observation.representation_item_count),
                "placement_count": str(observation.placement_count),
                "unit_count": str(observation.unit_count),
                "diagnostic_count": str(observation.diagnostic_count),
                "source_sha256": source_hash,
            }
        )
        fixture_json: dict[str, object] = {
            "fixture": fixture.fixture,
            "decision": observation.decision,
            "reason_code": observation.reason_code,
            "source_sha256": source_hash,
            "paths": [],
        }
        if result is None:
            json_records.append(fixture_json)
            continue
        for path in result.paths:
            row = {
                "fixture": fixture.fixture,
                "path_index": str(path.path_index),
                "product_entity_id": str(path.product_entity_id),
                "product_identifier": path.product_identifier,
                "product_name": path.product_name,
                "formation_entity_id": str(path.formation_entity_id),
                "formation_identifier": path.formation_identifier,
                "product_definition_entity_id": str(path.product_definition_entity_id),
                "product_definition_identifier": path.product_definition_identifier,
                "product_definition_context_entity_id": str(path.product_definition_context_entity_id),
                "product_definition_shape_entity_id": str(path.product_definition_shape_entity_id),
                "shape_definition_representation_entity_id": str(path.shape_definition_representation_entity_id),
                "representation_entity_id": str(path.representation_entity_id),
                "representation_type": path.representation_type,
                "representation_name": path.representation_name,
                "representation_context_entity_id": str(path.representation_context_entity_id),
                "context_identifier": path.context_identifier,
                "context_type": path.context_type,
                "coordinate_space_dimension": str(path.coordinate_space_dimension),
                "representation_item_count": str(path.representation_item_count),
                "placement_count": str(path.placement_count),
                "unit_count": str(path.unit_count),
                "source_line": str(path.source_span.start_line),
            }
            paths.append(row)
            json_path: dict[str, object] = {
                key: value for key, value in row.items() if key != "fixture"
            }
            for key in (
                "path_index",
                "product_entity_id",
                "formation_entity_id",
                "product_definition_entity_id",
                "product_definition_context_entity_id",
                "product_definition_shape_entity_id",
                "shape_definition_representation_entity_id",
                "representation_entity_id",
                "representation_context_entity_id",
                "coordinate_space_dimension",
                "representation_item_count",
                "placement_count",
                "unit_count",
                "source_line",
            ):
                json_path[key] = int(row[key])
            fixture_json["paths"].append(json_path)  # type: ignore[union-attr]
        for relation in result.relations:
            relations.append(
                {
                    "fixture": fixture.fixture,
                    "path_index": str(relation.path_index),
                    "role": relation.role,
                    "source_entity_id": str(relation.source_entity_id),
                    "target_entity_id": str(relation.target_entity_id),
                    "source_edge_index": str(relation.source_edge_index),
                    "parameter_path": "/".join(str(value) for value in relation.parameter_path),
                    "source_line": str(relation.source_span.start_line),
                    "source_column": str(relation.source_span.start_column),
                }
            )
        for item in result.representation_items:
            items.append(
                {
                    "fixture": fixture.fixture,
                    "path_index": str(item.path_index),
                    "item_index": str(item.item_index),
                    "entity_id": str(item.entity_id),
                    "role": item.role,
                    "record_types": "|".join(item.record_types),
                    "name": item.name or "",
                    "source_line": str(item.source_span.start_line),
                }
            )
        for unit in result.units:
            units.append(
                {
                    "fixture": fixture.fixture,
                    "path_index": str(unit.path_index),
                    "unit_index": str(unit.unit_index),
                    "entity_id": str(unit.entity_id),
                    "unit_kind": unit.unit_kind,
                    "si_prefix": unit.si_prefix or "",
                    "si_name": unit.si_name or "",
                    "record_types": "|".join(unit.record_types),
                    "source_line": str(unit.source_span.start_line),
                }
            )
        for index, diagnostic in enumerate(result.diagnostics):
            diagnostics.append(
                {
                    "fixture": fixture.fixture,
                    "diagnostic_index": str(index),
                    "severity": diagnostic.severity,
                    "reason_code": diagnostic.reason_code,
                    "role": diagnostic.role,
                    "entity_id": "" if diagnostic.entity_id is None else str(diagnostic.entity_id),
                    "source_line": "" if diagnostic.source_line is None else str(diagnostic.source_line),
                    "detail": diagnostic.detail,
                }
            )
        json_records.append(fixture_json)
    return observations, paths, relations, items, units, diagnostics, json_records


def summary_rows(observations, paths, relations, items, units, diagnostics):
    """Aggregate corpus decisions and controlled semantic evidence."""
    decisions = Counter(row["observed_decision"] for row in observations)
    roles = Counter(row["role"] for row in items)
    rows = [
        {"scope": "corpus", "metric": "fixture_count", "value": str(len(observations))},
        {
            "scope": "corpus",
            "metric": "expectation_match_count",
            "value": str(sum(int(row["expectation_met"]) for row in observations)),
        },
        {"scope": "evidence", "metric": "path_count", "value": str(len(paths))},
        {"scope": "evidence", "metric": "relation_count", "value": str(len(relations))},
        {"scope": "evidence", "metric": "representation_item_count", "value": str(len(items))},
        {"scope": "evidence", "metric": "unit_count", "value": str(len(units))},
        {"scope": "evidence", "metric": "diagnostic_count", "value": str(len(diagnostics))},
    ]
    rows.extend(
        {"scope": "decision", "metric": key, "value": str(decisions.get(key, 0))}
        for key in ("accept", "quarantine", "reject")
    )
    rows.extend(
        {"scope": "item_role", "metric": key, "value": str(roles.get(key, 0))}
        for key in ("placement", "solid_model", "geometric_item", "mapped_item", "unclassified")
    )
    return rows


def save_figure(path: Path, observations, paths, relations) -> None:
    """Visualize the representative semantic chain and corpus decisions."""
    fig, axes = plt.subplots(1, 2, figsize=(14.5, 5.2))
    ax = axes[0]
    labels = [
        "Product",
        "Formation",
        "Product\ndefinition",
        "Shape\ndefinition",
        "Shape\nrepresentation",
        "Representation\ncontext",
    ]
    x_values = [index * 1.25 for index in range(len(labels))]
    for index in range(len(labels) - 1):
        ax.annotate(
            "",
            xy=(x_values[index + 1] - 0.42, 0.5),
            xytext=(x_values[index] + 0.42, 0.5),
            arrowprops={"arrowstyle": "->", "lw": 1.7, "color": "#52616b"},
        )
    for x_value, label in zip(x_values, labels, strict=True):
        ax.text(
            x_value,
            0.5,
            label,
            ha="center",
            va="center",
            color="white",
            fontsize=7.5,
            bbox={
                "boxstyle": "round,pad=0.55",
                "facecolor": "#3b82a0",
                "edgecolor": "white",
                "linewidth": 1.5,
            },
        )
    ax.set_xlim(-0.65, x_values[-1] + 0.65)
    ax.set_ylim(0, 1)
    ax.set_axis_off()
    ax.set_title("Controlled semantic path")

    decision_counts = Counter(row["observed_decision"] for row in observations)
    labels2 = ["accept", "quarantine", "reject"]
    values = [decision_counts[label] for label in labels2]
    axes[1].bar(labels2, values, color=["#3a8f68", "#e0a458", "#c8553d"])
    axes[1].set_ylabel("Fixture count")
    axes[1].set_title(f"Corpus decisions ({len(paths)} paths, {len(relations)} relations)")
    axes[1].set_ylim(0, max(values) + 1)
    axes[1].grid(axis="y", alpha=0.25)
    for index, value in enumerate(values):
        axes[1].text(index, value + 0.12, str(value), ha="center", fontsize=9)
    fig.suptitle("AP242 Product and Representation Paths", fontsize=14)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160, metadata={"Software": "research-notes"})
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    """Parse deterministic experiment paths and fixture refresh mode."""
    parser = argparse.ArgumentParser(
        description="Evaluate controlled AP242 product-to-representation paths."
    )
    parser.add_argument(
        "--fixture-dir", type=Path, default=Path("fixtures/ap242-product-paths")
    )
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument("--refresh-fixtures", action="store_true")
    return parser.parse_args()


def main() -> None:
    """Regenerate fixtures or verify them, then write all v0.29 evidence."""
    args = parse_args()
    definitions = build_ap242_path_fixtures()
    if args.refresh_fixtures:
        refresh_fixture_corpus(args.fixture_dir, definitions)
    fixtures = load_fixture_corpus(args.fixture_dir, definitions)
    observations, paths, relations, items, units, diagnostics, json_records = build_rows(fixtures)
    output_dir = args.output_dir
    write_csv(output_dir / OBSERVATIONS_NAME, observations, OBSERVATION_FIELDS)
    write_csv(output_dir / PATHS_NAME, paths, PATH_FIELDS)
    write_csv(output_dir / RELATIONS_NAME, relations, RELATION_FIELDS)
    write_csv(output_dir / ITEMS_NAME, items, ITEM_FIELDS)
    write_csv(output_dir / UNITS_NAME, units, UNIT_FIELDS)
    write_csv(output_dir / DIAGNOSTICS_NAME, diagnostics, DIAGNOSTIC_FIELDS)
    write_csv(
        output_dir / SUMMARY_NAME,
        summary_rows(observations, paths, relations, items, units, diagnostics),
        SUMMARY_FIELDS,
    )
    payload = {
        "record_type": "research-notes.ap242-product-paths",
        "format_version": "1.0",
        "fixtures": json_records,
    }
    (output_dir / JSON_NAME).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    save_figure(output_dir / FIGURE_NAME, observations, paths, relations)
    if any(row["expectation_met"] != "1" for row in observations):
        raise RuntimeError("one or more AP242 path expectations failed")
    print(
        f"Wrote {len(observations)} fixture observations, {len(paths)} paths, "
        f"and {len(relations)} semantic relations to {output_dir}."
    )


if __name__ == "__main__":
    main()
