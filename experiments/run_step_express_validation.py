"""Evaluate staged Part 21 instance validation against EXPRESS schemas."""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

from research_notes import (  # noqa: E402
    STEPExpressValidationFixture,
    build_step_express_validation_fixtures,
    inspect_step_express_validation,
)


MANIFEST_NAME = "manifest.csv"
OBSERVATIONS_NAME = "step_express_validation_observations.csv"
SECTIONS_NAME = "step_express_sections.csv"
INSTANCES_NAME = "step_express_instances.csv"
PARAMETERS_NAME = "step_express_parameters.csv"
DIAGNOSTICS_NAME = "step_express_diagnostics.csv"
SUMMARY_NAME = "step_express_validation_summary.csv"
FIGURE_NAME = "step_express_validation.png"

MANIFEST_FIELDS = (
    "fixture",
    "category",
    "condition",
    "step_file_name",
    "express_file_name",
    "expected_decision",
    "expected_reason_code",
    "step_bytes",
    "step_sha256",
    "express_bytes",
    "express_sha256",
    "max_instances",
    "max_parameters",
    "max_validation_depth",
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
    "part21_syntax",
    "express_syntax",
    "express_resolution",
    "schema_binding",
    "instance_validation",
    "section_count",
    "instance_count",
    "parameter_count",
    "valid_parameter_count",
    "invalid_parameter_count",
    "deferred_parameter_count",
    "diagnostic_count",
    "application_semantics",
    "rule_execution",
    "step_sha256",
    "express_sha256",
)
SECTION_FIELDS = (
    "fixture",
    "section_index",
    "section_name",
    "declared_schema",
    "resolved_schema",
    "entity_count",
    "status",
    "reason_code",
)
INSTANCE_FIELDS = (
    "fixture",
    "section_index",
    "entity_id",
    "mapping",
    "record_types",
    "resolved_entity_ids",
    "expected_parameter_count",
    "actual_parameter_count",
    "status",
    "reason_code",
)
PARAMETER_FIELDS = (
    "fixture",
    "section_index",
    "entity_id",
    "record_index",
    "parameter_index",
    "entity_type",
    "attribute_owner",
    "attribute_name",
    "expected_type",
    "value_kind",
    "value_source",
    "status",
    "reason_code",
    "source_line",
)
DIAGNOSTIC_FIELDS = (
    "fixture",
    "severity",
    "reason_code",
    "stage",
    "section_index",
    "entity_id",
    "record_index",
    "parameter_index",
    "source_line",
    "detail",
)
SUMMARY_FIELDS = ("scope", "metric", "value")


def write_csv(
    path: Path,
    rows: Sequence[dict[str, str]],
    fields: Sequence[str],
) -> None:
    """Write deterministic UTF-8 CSV evidence."""
    if not rows:
        raise ValueError("rows must not be empty")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def manifest_rows(
    fixtures: Sequence[STEPExpressValidationFixture],
) -> list[dict[str, str]]:
    """Describe exact paired inputs, expectations, and validation limits."""
    return [
        {
            "fixture": item.fixture,
            "category": item.category,
            "condition": item.condition,
            "step_file_name": item.step_file_name,
            "express_file_name": item.express_file_name,
            "expected_decision": item.expected_decision,
            "expected_reason_code": item.expected_reason_code,
            "step_bytes": str(len(item.step_bytes)),
            "step_sha256": hashlib.sha256(item.step_bytes).hexdigest(),
            "express_bytes": str(len(item.express_bytes)),
            "express_sha256": hashlib.sha256(item.express_bytes).hexdigest(),
            "max_instances": str(item.validation_limits.max_instances),
            "max_parameters": str(item.validation_limits.max_parameters),
            "max_validation_depth": str(
                item.validation_limits.max_validation_depth
            ),
        }
        for item in fixtures
    ]


def refresh_fixture_corpus(
    fixture_dir: Path,
    fixtures: Sequence[STEPExpressValidationFixture],
) -> None:
    """Write paired fixture bytes without deleting unknown files."""
    fixture_dir.mkdir(parents=True, exist_ok=True)
    expected = {
        name
        for item in fixtures
        for name in (item.step_file_name, item.express_file_name)
    }
    existing = {
        path.name for path in fixture_dir.iterdir() if path.name != MANIFEST_NAME
    }
    unexpected = sorted(existing - expected)
    if unexpected:
        raise RuntimeError(
            "fixture directory contains unexpected files: "
            + ", ".join(unexpected)
        )
    for item in fixtures:
        (fixture_dir / item.step_file_name).write_bytes(item.step_bytes)
        (fixture_dir / item.express_file_name).write_bytes(item.express_bytes)
    write_csv(fixture_dir / MANIFEST_NAME, manifest_rows(fixtures), MANIFEST_FIELDS)


def load_fixture_corpus(
    fixture_dir: Path,
    fixtures: Sequence[STEPExpressValidationFixture],
) -> tuple[STEPExpressValidationFixture, ...]:
    """Load committed paired bytes after exact manifest checks."""
    manifest_path = fixture_dir / MANIFEST_NAME
    if not manifest_path.is_file():
        raise RuntimeError(
            f"missing fixture manifest: {manifest_path}; use --refresh-fixtures"
        )
    with manifest_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if rows != manifest_rows(fixtures):
        raise RuntimeError("committed fixture manifest does not match definitions")
    for item in fixtures:
        if (fixture_dir / item.step_file_name).read_bytes() != item.step_bytes:
            raise RuntimeError(f"fixture differs from definition: {item.step_file_name}")
        if (fixture_dir / item.express_file_name).read_bytes() != item.express_bytes:
            raise RuntimeError(
                f"fixture differs from definition: {item.express_file_name}"
            )
    return tuple(fixtures)


def build_rows(
    fixtures: Sequence[STEPExpressValidationFixture],
) -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    """Run the corpus and expand staged validation evidence."""
    observations: list[dict[str, str]] = []
    sections: list[dict[str, str]] = []
    instances: list[dict[str, str]] = []
    parameters: list[dict[str, str]] = []
    diagnostics: list[dict[str, str]] = []
    for fixture in fixtures:
        result = inspect_step_express_validation(
            fixture.step_bytes,
            fixture.express_bytes,
            validation_limits=fixture.validation_limits,
        )
        observations.append(
            {
                "fixture": fixture.fixture,
                "category": fixture.category,
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
                "part21_syntax": result.part21_syntax,
                "express_syntax": result.express_syntax,
                "express_resolution": result.express_resolution,
                "schema_binding": result.schema_binding,
                "instance_validation": result.instance_validation,
                "section_count": str(result.section_count),
                "instance_count": str(result.instance_count),
                "parameter_count": str(result.parameter_count),
                "valid_parameter_count": str(result.valid_parameter_count),
                "invalid_parameter_count": str(result.invalid_parameter_count),
                "deferred_parameter_count": str(result.deferred_parameter_count),
                "diagnostic_count": str(len(result.diagnostics)),
                "application_semantics": result.application_semantics,
                "rule_execution": result.rule_execution,
                "step_sha256": hashlib.sha256(fixture.step_bytes).hexdigest(),
                "express_sha256": hashlib.sha256(fixture.express_bytes).hexdigest(),
            }
        )
        sections.extend(
            {
                "fixture": fixture.fixture,
                "section_index": str(item.section_index),
                "section_name": item.section_name or "",
                "declared_schema": item.declared_schema or "",
                "resolved_schema": item.resolved_schema or "",
                "entity_count": str(item.entity_count),
                "status": item.status,
                "reason_code": item.reason_code,
            }
            for item in result.sections
        )
        instances.extend(
            {
                "fixture": fixture.fixture,
                "section_index": str(item.section_index),
                "entity_id": str(item.entity_id),
                "mapping": item.mapping,
                "record_types": "|".join(item.record_types),
                "resolved_entity_ids": "|".join(item.resolved_entity_ids),
                "expected_parameter_count": str(item.expected_parameter_count),
                "actual_parameter_count": str(item.actual_parameter_count),
                "status": item.status,
                "reason_code": item.reason_code,
            }
            for item in result.instances
        )
        parameters.extend(
            {
                "fixture": fixture.fixture,
                "section_index": str(item.section_index),
                "entity_id": str(item.entity_id),
                "record_index": str(item.record_index),
                "parameter_index": str(item.parameter_index),
                "entity_type": item.entity_type,
                "attribute_owner": item.attribute_owner,
                "attribute_name": item.attribute_name,
                "expected_type": item.expected_type,
                "value_kind": item.value_kind,
                "value_source": item.value_source,
                "status": item.status,
                "reason_code": item.reason_code,
                "source_line": str(item.source_line),
            }
            for item in result.parameters
        )
        diagnostics.extend(
            {
                "fixture": fixture.fixture,
                "severity": item.severity,
                "reason_code": item.reason_code,
                "stage": item.stage,
                "section_index": "" if item.section_index is None else str(item.section_index),
                "entity_id": "" if item.entity_id is None else str(item.entity_id),
                "record_index": "" if item.record_index is None else str(item.record_index),
                "parameter_index": "" if item.parameter_index is None else str(item.parameter_index),
                "source_line": "" if item.source_line is None else str(item.source_line),
                "detail": item.detail,
            }
            for item in result.diagnostics
        )
    return observations, sections, instances, parameters, diagnostics


def summary_rows(
    observations: Sequence[dict[str, str]],
    instances: Sequence[dict[str, str]],
    parameters: Sequence[dict[str, str]],
    diagnostics: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Summarize corpus outcomes without generalizing beyond the fixtures."""
    decisions = Counter(item["observed_decision"] for item in observations)
    instance_states = Counter(item["status"] for item in instances)
    parameter_states = Counter(item["status"] for item in parameters)
    stages = (
        "part21_syntax",
        "express_syntax",
        "express_resolution",
        "schema_binding",
        "instance_validation",
    )
    rows: list[dict[str, str]] = [
        {"scope": "corpus", "metric": "fixtures", "value": str(len(observations))},
        {"scope": "corpus", "metric": "expectations_met", "value": str(sum(item["expectation_met"] == "1" for item in observations))},
    ]
    rows.extend(
        {"scope": "decision", "metric": key, "value": str(decisions[key])}
        for key in ("accept", "quarantine", "reject")
    )
    rows.extend(
        {"scope": "instances", "metric": key, "value": str(instance_states[key])}
        for key in ("valid", "invalid", "deferred")
    )
    rows.extend(
        {"scope": "parameters", "metric": key, "value": str(parameter_states[key])}
        for key in ("valid", "invalid", "deferred")
    )
    rows.append(
        {"scope": "diagnostics", "metric": "rows", "value": str(len(diagnostics))}
    )
    for stage in stages:
        counts = Counter(item[stage] for item in observations)
        for status in ("valid", "invalid", "deferred", "not_reached"):
            rows.append(
                {
                    "scope": stage,
                    "metric": status,
                    "value": str(counts[status]),
                }
            )
    return rows


def render_figure(
    path: Path,
    observations: Sequence[dict[str, str]],
    parameters: Sequence[dict[str, str]],
    diagnostics: Sequence[dict[str, str]],
) -> None:
    """Render the controlled validation outcomes and staged boundaries."""
    decision_counts = Counter(item["observed_decision"] for item in observations)
    parameter_counts = Counter(item["status"] for item in parameters)
    stages = (
        "part21_syntax",
        "express_syntax",
        "express_resolution",
        "schema_binding",
        "instance_validation",
    )
    stage_valid = [sum(item[stage] == "valid" for item in observations) for stage in stages]
    stage_stopped = [len(observations) - value for value in stage_valid]
    reasons = Counter(item["reason_code"] for item in diagnostics)
    top_reasons = reasons.most_common(8)

    figure, axes = plt.subplots(2, 2, figsize=(15, 10))
    colors = {"accept": "#2a9d8f", "quarantine": "#e9c46a", "reject": "#e76f51"}
    labels = ("accept", "quarantine", "reject")
    axes[0, 0].bar(
        labels,
        [decision_counts[label] for label in labels],
        color=[colors[label] for label in labels],
    )
    axes[0, 0].set_title("Controlled fixture decisions")
    axes[0, 0].set_ylabel("Fixtures")

    stage_labels = [item.replace("_", "\n") for item in stages]
    axes[0, 1].bar(stage_labels, stage_valid, label="valid", color="#2a9d8f")
    axes[0, 1].bar(
        stage_labels,
        stage_stopped,
        bottom=stage_valid,
        label="invalid, deferred, or not reached",
        color="#d9d9d9",
    )
    axes[0, 1].set_title("Validation remains staged")
    axes[0, 1].set_ylabel("Fixtures")
    axes[0, 1].legend()

    parameter_labels = ("valid", "invalid", "deferred")
    axes[1, 0].bar(
        parameter_labels,
        [parameter_counts[label] for label in parameter_labels],
        color=["#2a9d8f", "#e76f51", "#e9c46a"],
    )
    axes[1, 0].set_title("Schema-bound parameter evidence")
    axes[1, 0].set_ylabel("Parameters")

    if top_reasons:
        reason_labels = [name.replace("_", " ") for name, _ in reversed(top_reasons)]
        reason_values = [count for _, count in reversed(top_reasons)]
        axes[1, 1].barh(reason_labels, reason_values, color="#457b9d")
    axes[1, 1].set_title("Most frequent controlled diagnostics")
    axes[1, 1].set_xlabel("Diagnostic rows")

    figure.suptitle("Part 21 Validation Against EXPRESS", fontsize=18, fontweight="bold")
    figure.text(
        0.5,
        0.01,
        "Synthetic pairs demonstrate a bounded validator, not AP242 or complete ISO conformance.",
        ha="center",
    )
    figure.tight_layout(rect=(0, 0.035, 1, 0.96))
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160)
    plt.close(figure)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Validate deterministic Part 21 instances against EXPRESS schemas."
    )
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=Path("fixtures/step-express-validation"),
        help="Directory containing committed paired fixtures.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results"),
        help="Directory for generated CSV and PNG evidence.",
    )
    parser.add_argument(
        "--refresh-fixtures",
        action="store_true",
        help="Write deterministic paired fixture bytes before validation.",
    )
    return parser.parse_args()


def main() -> None:
    """Run the paired corpus and write deterministic evidence."""
    args = parse_args()
    definitions = build_step_express_validation_fixtures()
    if args.refresh_fixtures:
        refresh_fixture_corpus(args.fixture_dir, definitions)
    fixtures = load_fixture_corpus(args.fixture_dir, definitions)
    observations, sections, instances, parameters, diagnostics = build_rows(fixtures)
    summaries = summary_rows(observations, instances, parameters, diagnostics)
    write_csv(args.output_dir / OBSERVATIONS_NAME, observations, OBSERVATION_FIELDS)
    write_csv(args.output_dir / SECTIONS_NAME, sections, SECTION_FIELDS)
    write_csv(args.output_dir / INSTANCES_NAME, instances, INSTANCE_FIELDS)
    write_csv(args.output_dir / PARAMETERS_NAME, parameters, PARAMETER_FIELDS)
    write_csv(args.output_dir / DIAGNOSTICS_NAME, diagnostics, DIAGNOSTIC_FIELDS)
    write_csv(args.output_dir / SUMMARY_NAME, summaries, SUMMARY_FIELDS)
    render_figure(
        args.output_dir / FIGURE_NAME, observations, parameters, diagnostics
    )
    print(f"Validated {len(fixtures)} paired fixtures.")
    print(f"Wrote deterministic evidence to {args.output_dir}.")


if __name__ == "__main__":
    main()
