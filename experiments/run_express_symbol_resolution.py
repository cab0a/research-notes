"""Evaluate controlled EXPRESS symbols, types, and inheritance."""

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

from research_notes.express_resolution_study import (  # noqa: E402
    ExpressResolutionFixture,
    build_express_resolution_fixtures,
    inspect_express_resolution,
)


MANIFEST_NAME = "manifest.csv"
OBSERVATIONS_NAME = "express_resolution_observations.csv"
SYMBOLS_NAME = "express_symbols.csv"
REFERENCES_NAME = "express_reference_resolution.csv"
TYPES_NAME = "express_type_resolution.csv"
BOUNDS_NAME = "express_aggregate_bounds.csv"
INHERITANCE_NAME = "express_inheritance.csv"
SUMMARY_NAME = "express_resolution_summary.csv"
FIGURE_NAME = "express_symbols_types_inheritance.png"

MANIFEST_FIELDS = (
    "fixture", "category", "condition", "file_name", "expected_decision",
    "expected_reason_code", "source_bytes", "source_sha256", "max_symbols",
    "max_references", "max_inheritance_edges",
)
OBSERVATION_FIELDS = (
    "fixture", "category", "condition", "expected_decision",
    "observed_decision", "expectation_met", "expected_reason_code",
    "reason_code", "syntax_status", "symbol_count", "reference_count",
    "resolved_reference_count", "unresolved_reference_count",
    "ambiguous_reference_count", "invalid_kind_reference_count", "type_count",
    "resolved_type_count", "cyclic_type_count", "entity_count",
    "resolved_inheritance_count", "cyclic_inheritance_count",
    "aggregate_bound_count", "resolved_bound_count", "deferred_bound_count",
    "diagnostic_count", "expression_validation", "rule_execution",
    "external_schema_loading", "source_sha256",
)
SYMBOL_FIELDS = (
    "fixture", "symbol_id", "schema_name", "name", "kind", "source_line",
)
REFERENCE_FIELDS = (
    "fixture", "schema_name", "owner_symbol_id", "role", "source_name",
    "expected_kinds", "status", "resolved_symbol_id", "candidate_symbol_ids",
    "source_line",
)
TYPE_FIELDS = (
    "fixture", "symbol_id", "schema_name", "type_name", "status",
    "terminal_domain", "alias_chain",
)
BOUND_FIELDS = (
    "fixture", "schema_name", "owner_symbol_id", "role", "aggregate_kind",
    "lower_source", "upper_source", "lower_status", "upper_status",
    "lower_value", "upper_value", "status",
)
INHERITANCE_FIELDS = (
    "fixture", "symbol_id", "schema_name", "entity_name", "status",
    "immediate_supertype_ids", "transitive_supertype_ids",
    "local_attribute_count", "inherited_attribute_count",
    "effective_attribute_count", "redeclared_attribute_count",
)
SUMMARY_FIELDS = ("scope", "metric", "value")


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
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def fixture_manifest_rows(
    fixtures: Sequence[ExpressResolutionFixture],
) -> list[dict[str, str]]:
    """Describe exact fixture bytes, expectations, and semantic limits."""
    return [
        {
            "fixture": item.fixture,
            "category": item.category,
            "condition": item.condition,
            "file_name": item.file_name,
            "expected_decision": item.expected_decision,
            "expected_reason_code": item.expected_reason_code,
            "source_bytes": str(len(item.source_bytes)),
            "source_sha256": hashlib.sha256(item.source_bytes).hexdigest(),
            "max_symbols": str(item.resolution_limits.max_symbols),
            "max_references": str(item.resolution_limits.max_references),
            "max_inheritance_edges": str(item.resolution_limits.max_inheritance_edges),
        }
        for item in fixtures
    ]


def refresh_fixture_corpus(
    fixture_dir: Path,
    fixtures: Sequence[ExpressResolutionFixture],
) -> None:
    """Write the deterministic corpus without deleting unknown files."""
    fixture_dir.mkdir(parents=True, exist_ok=True)
    expected_names = {item.file_name for item in fixtures}
    existing_names = {
        path.name for path in fixture_dir.iterdir() if path.name != MANIFEST_NAME
    }
    unexpected = sorted(existing_names - expected_names)
    if unexpected:
        raise RuntimeError(
            "fixture directory contains unexpected files: " + ", ".join(unexpected)
        )
    for item in fixtures:
        (fixture_dir / item.file_name).write_bytes(item.source_bytes)
    write_csv(
        fixture_dir / MANIFEST_NAME,
        fixture_manifest_rows(fixtures),
        MANIFEST_FIELDS,
    )


def load_fixture_corpus(
    fixture_dir: Path,
    fixtures: Sequence[ExpressResolutionFixture],
) -> tuple[ExpressResolutionFixture, ...]:
    """Load committed bytes after exact manifest checks."""
    manifest_path = fixture_dir / MANIFEST_NAME
    if not manifest_path.is_file():
        raise RuntimeError(
            f"missing fixture manifest: {manifest_path}; use --refresh-fixtures"
        )
    with manifest_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if rows != fixture_manifest_rows(fixtures):
        raise RuntimeError("committed fixture manifest does not match definitions")
    for item in fixtures:
        path = fixture_dir / item.file_name
        if not path.is_file() or path.read_bytes() != item.source_bytes:
            raise RuntimeError(f"fixture differs from definition: {item.file_name}")
    return tuple(fixtures)


def build_rows(
    fixtures: Sequence[ExpressResolutionFixture],
) -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    """Run every fixture and expand the resolved semantic graph."""
    observations: list[dict[str, str]] = []
    symbols: list[dict[str, str]] = []
    references: list[dict[str, str]] = []
    types: list[dict[str, str]] = []
    bounds: list[dict[str, str]] = []
    inheritance: list[dict[str, str]] = []
    for fixture in fixtures:
        observed, resolved = inspect_express_resolution(
            fixture.source_bytes,
            parse_limits=fixture.parse_limits,
            resolution_limits=fixture.resolution_limits,
        )
        observations.append(
            {
                "fixture": fixture.fixture,
                "category": fixture.category,
                "condition": fixture.condition,
                "expected_decision": fixture.expected_decision,
                "observed_decision": observed.decision,
                "expectation_met": str(int(
                    observed.decision == fixture.expected_decision
                    and observed.reason_code == fixture.expected_reason_code
                )),
                "expected_reason_code": fixture.expected_reason_code,
                "reason_code": observed.reason_code,
                "syntax_status": observed.syntax_status,
                "symbol_count": str(observed.symbol_count),
                "reference_count": str(observed.reference_count),
                "resolved_reference_count": str(observed.resolved_reference_count),
                "unresolved_reference_count": str(observed.unresolved_reference_count),
                "ambiguous_reference_count": str(observed.ambiguous_reference_count),
                "invalid_kind_reference_count": str(observed.invalid_kind_reference_count),
                "type_count": str(observed.type_count),
                "resolved_type_count": str(observed.resolved_type_count),
                "cyclic_type_count": str(observed.cyclic_type_count),
                "entity_count": str(observed.entity_count),
                "resolved_inheritance_count": str(observed.resolved_inheritance_count),
                "cyclic_inheritance_count": str(observed.cyclic_inheritance_count),
                "aggregate_bound_count": str(observed.aggregate_bound_count),
                "resolved_bound_count": str(observed.resolved_bound_count),
                "deferred_bound_count": str(observed.deferred_bound_count),
                "diagnostic_count": str(observed.diagnostic_count),
                "expression_validation": observed.expression_validation,
                "rule_execution": observed.rule_execution,
                "external_schema_loading": observed.external_schema_loading,
                "source_sha256": hashlib.sha256(fixture.source_bytes).hexdigest(),
            }
        )
        if resolved is None:
            continue
        symbols.extend(
            {
                "fixture": fixture.fixture,
                "symbol_id": item.symbol_id,
                "schema_name": item.schema_name,
                "name": item.name,
                "kind": item.kind,
                "source_line": str(item.source_line),
            }
            for item in resolved.symbols
        )
        references.extend(
            {
                "fixture": fixture.fixture,
                "schema_name": item.schema_name,
                "owner_symbol_id": item.owner_symbol_id,
                "role": item.role,
                "source_name": item.source_name,
                "expected_kinds": "|".join(item.expected_kinds),
                "status": item.status,
                "resolved_symbol_id": item.resolved_symbol_id or "",
                "candidate_symbol_ids": "|".join(item.candidate_symbol_ids),
                "source_line": str(item.source_line),
            }
            for item in resolved.references
        )
        types.extend(
            {
                "fixture": fixture.fixture,
                "symbol_id": item.symbol_id,
                "schema_name": item.schema_name,
                "type_name": item.type_name,
                "status": item.status,
                "terminal_domain": item.terminal_domain or "",
                "alias_chain": "|".join(item.alias_chain),
            }
            for item in resolved.types
        )
        bounds.extend(
            {
                "fixture": fixture.fixture,
                "schema_name": item.schema_name,
                "owner_symbol_id": item.owner_symbol_id,
                "role": item.role,
                "aggregate_kind": item.aggregate_kind,
                "lower_source": item.lower_source or "",
                "upper_source": item.upper_source or "",
                "lower_status": item.lower_status,
                "upper_status": item.upper_status,
                "lower_value": "" if item.lower_value is None else str(item.lower_value),
                "upper_value": "" if item.upper_value is None else str(item.upper_value),
                "status": item.status,
            }
            for item in resolved.aggregate_bounds
        )
        inheritance.extend(
            {
                "fixture": fixture.fixture,
                "symbol_id": item.symbol_id,
                "schema_name": item.schema_name,
                "entity_name": item.entity_name,
                "status": item.status,
                "immediate_supertype_ids": "|".join(item.immediate_supertype_ids),
                "transitive_supertype_ids": "|".join(item.transitive_supertype_ids),
                "local_attribute_count": str(item.local_attribute_count),
                "inherited_attribute_count": str(item.inherited_attribute_count),
                "effective_attribute_count": str(item.effective_attribute_count),
                "redeclared_attribute_count": str(item.redeclared_attribute_count),
            }
            for item in resolved.inheritance
        )
    return observations, symbols, references, types, bounds, inheritance


def summary_rows(
    observations: Sequence[dict[str, str]],
    symbols: Sequence[dict[str, str]],
    references: Sequence[dict[str, str]],
    types: Sequence[dict[str, str]],
    bounds: Sequence[dict[str, str]],
    inheritance: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Summarize decisions and resolved graph evidence."""
    expected = Counter(row["expected_decision"] for row in observations)
    observed = Counter(row["observed_decision"] for row in observations)
    rows = [
        {"scope": "corpus", "metric": "fixture_count", "value": str(len(observations))},
        {"scope": "corpus", "metric": "expectation_rate", "value": f"{sum(int(row['expectation_met']) for row in observations) / len(observations):.6f}"},
    ]
    for decision in ("accept", "quarantine", "reject"):
        rows.append({"scope": "expected", "metric": decision, "value": str(expected[decision])})
        rows.append({"scope": "observed", "metric": decision, "value": str(observed[decision])})
    for scope, values in (
        ("symbols", symbols),
        ("references", references),
        ("types", types),
        ("aggregate_bounds", bounds),
        ("inheritance", inheritance),
    ):
        rows.append({"scope": scope, "metric": "row_count", "value": str(len(values))})
    for status, count in sorted(Counter(row["status"] for row in references).items()):
        rows.append({"scope": "references", "metric": status, "value": str(count)})
    for status, count in sorted(Counter(row["status"] for row in types).items()):
        rows.append({"scope": "types", "metric": status, "value": str(count)})
    for status, count in sorted(Counter(row["status"] for row in inheritance).items()):
        rows.append({"scope": "inheritance", "metric": status, "value": str(count)})
    return rows


def plot_results(
    observations: Sequence[dict[str, str]],
    references: Sequence[dict[str, str]],
    types: Sequence[dict[str, str]],
    inheritance: Sequence[dict[str, str]],
    output_path: Path,
) -> None:
    """Visualize fixture decisions and explicit semantic-resolution states."""
    figure, axes = plt.subplots(1, 3, figsize=(16.5, 6.2))
    decisions = ("accept", "quarantine", "reject")
    expected = Counter(row["expected_decision"] for row in observations)
    observed = Counter(row["observed_decision"] for row in observations)
    positions = np.arange(len(decisions))
    axes[0].bar(positions - 0.18, [expected[item] for item in decisions], 0.36, label="expected", color="#457b9d")
    axes[0].bar(positions + 0.18, [observed[item] for item in decisions], 0.36, label="observed", color="#2a9d8f")
    axes[0].set_xticks(positions, decisions)
    axes[0].set_ylabel("Fixture count")
    axes[0].set_title("Controlled decisions")
    axes[0].legend()
    axes[0].grid(axis="y", alpha=0.25)

    reference_statuses = ("resolved", "unresolved", "ambiguous", "invalid_kind")
    reference_counts = Counter(row["status"] for row in references)
    axes[1].barh(reference_statuses, [reference_counts[item] for item in reference_statuses], color=["#2a9d8f", "#e9c46a", "#e76f51", "#f4a261"])
    axes[1].set_xlabel("Reference rows")
    axes[1].set_title("Names remain explicit")
    axes[1].grid(axis="x", alpha=0.25)

    type_counts = Counter(row["status"] for row in types)
    inheritance_counts = Counter(row["status"] for row in inheritance)
    states = ("resolved", "unresolved", "ambiguous", "cyclic")
    x = np.arange(len(states))
    axes[2].bar(x - 0.18, [type_counts[item] for item in states], 0.36, label="defined types", color="#6d597a")
    axes[2].bar(x + 0.18, [inheritance_counts[item] for item in states], 0.36, label="entities", color="#457b9d")
    axes[2].set_xticks(x, states, rotation=15)
    axes[2].set_ylabel("Model rows")
    axes[2].set_title("Type and inheritance graphs")
    axes[2].legend()
    axes[2].grid(axis="y", alpha=0.25)

    figure.suptitle("EXPRESS Symbols, Types, and Inheritance", fontsize=14, fontweight="bold")
    figure.text(0.5, 0.012, "Direct in-document imports are resolved; expressions, transitive re-export, external schemas, and rule execution remain outside this release.", ha="center", fontsize=9)
    figure.tight_layout(rect=(0, 0.05, 1, 0.94))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Evaluate controlled EXPRESS symbol, type, and inheritance resolution."
    )
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=Path("fixtures/express-symbol-resolution"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument("--refresh-fixtures", action="store_true")
    return parser.parse_args()


def main() -> None:
    """Run the controlled EXPRESS semantic-resolution experiment."""
    args = parse_args()
    definitions = build_express_resolution_fixtures()
    if args.refresh_fixtures:
        refresh_fixture_corpus(args.fixture_dir, definitions)
    fixtures = load_fixture_corpus(args.fixture_dir, definitions)
    observations, symbols, references, types, bounds, inheritance = build_rows(fixtures)
    summary = summary_rows(observations, symbols, references, types, bounds, inheritance)
    for name, rows, fields in (
        (OBSERVATIONS_NAME, observations, OBSERVATION_FIELDS),
        (SYMBOLS_NAME, symbols, SYMBOL_FIELDS),
        (REFERENCES_NAME, references, REFERENCE_FIELDS),
        (TYPES_NAME, types, TYPE_FIELDS),
        (BOUNDS_NAME, bounds, BOUND_FIELDS),
        (INHERITANCE_NAME, inheritance, INHERITANCE_FIELDS),
        (SUMMARY_NAME, summary, SUMMARY_FIELDS),
    ):
        write_csv(args.output_dir / name, rows, fields)
    plot_results(observations, references, types, inheritance, args.output_dir / FIGURE_NAME)
    for name in (
        OBSERVATIONS_NAME,
        SYMBOLS_NAME,
        REFERENCES_NAME,
        TYPES_NAME,
        BOUNDS_NAME,
        INHERITANCE_NAME,
        SUMMARY_NAME,
        FIGURE_NAME,
    ):
        print(f"Wrote {args.output_dir / name}")


if __name__ == "__main__":
    main()
