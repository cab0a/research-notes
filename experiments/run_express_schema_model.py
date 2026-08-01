"""Evaluate controlled EXPRESS grammar coverage and schema-model extraction."""

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

from research_notes import (  # noqa: E402
    ExpressSchemaFixture,
    ExpressTypeReference,
    build_express_schema_fixtures,
    inspect_express_schema,
    parse_express_document,
)


MANIFEST_NAME = "manifest.csv"
OBSERVATIONS_NAME = "express_schema_observations.csv"
INVENTORY_NAME = "express_schema_inventory.csv"
COVERAGE_NAME = "express_grammar_coverage.csv"
SUMMARY_NAME = "express_schema_summary.csv"
FIGURE_NAME = "express_schema_model.png"

MANIFEST_FIELDS = (
    "fixture",
    "category",
    "condition",
    "file_name",
    "expected_decision",
    "expected_reason_code",
    "source_bytes",
    "source_sha256",
    "max_file_bytes",
    "max_tokens",
    "max_declarations",
    "max_nesting_depth",
    "max_token_chars",
)
OBSERVATION_FIELDS = (
    "fixture",
    "category",
    "condition",
    "file_name",
    "expected_decision",
    "observed_decision",
    "expectation_met",
    "expected_reason_code",
    "reason_code",
    "features",
    "schema_count",
    "interface_count",
    "type_count",
    "entity_count",
    "algorithm_count",
    "constant_count",
    "explicit_attribute_count",
    "derived_attribute_count",
    "inverse_attribute_count",
    "where_rule_count",
    "unique_rule_count",
    "token_count",
    "trivia_token_count",
    "source_bytes",
    "exact_reconstruction",
    "diagnostic_line",
    "diagnostic_column",
    "symbol_resolution",
    "type_checking",
    "expression_validation",
    "rule_execution",
    "source_sha256",
)
INVENTORY_FIELDS = (
    "fixture",
    "schema",
    "declaration_kind",
    "name",
    "parent",
    "detail",
    "source_line",
    "symbol_resolution",
)
COVERAGE_FIELDS = (
    "feature",
    "fixture",
    "implementation_status",
    "model_output",
    "claim_boundary",
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
        writer = csv.DictWriter(
            handle, fieldnames=list(fieldnames), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def fixture_manifest_rows(
    fixtures: Sequence[ExpressSchemaFixture],
) -> list[dict[str, str]]:
    """Describe exact fixture bytes, expectations, and active limits."""
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
            "max_file_bytes": str(item.limits.max_file_bytes),
            "max_tokens": str(item.limits.max_tokens),
            "max_declarations": str(item.limits.max_declarations),
            "max_nesting_depth": str(item.limits.max_nesting_depth),
            "max_token_chars": str(item.limits.max_token_chars),
        }
        for item in fixtures
    ]


def refresh_fixture_corpus(
    fixture_dir: Path,
    fixtures: Sequence[ExpressSchemaFixture],
) -> None:
    """Write the deterministic EXPRESS corpus without deleting unknown files."""
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
    fixtures: Sequence[ExpressSchemaFixture],
) -> tuple[ExpressSchemaFixture, ...]:
    """Load committed fixture bytes after exact manifest checks."""
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


def observation_rows(
    fixtures: Sequence[ExpressSchemaFixture],
) -> list[dict[str, str]]:
    """Run the parser over every committed fixture."""
    rows: list[dict[str, str]] = []
    for item in fixtures:
        result = inspect_express_schema(item.source_bytes, limits=item.limits)
        rows.append(
            {
                "fixture": item.fixture,
                "category": item.category,
                "condition": item.condition,
                "file_name": item.file_name,
                "expected_decision": item.expected_decision,
                "observed_decision": result.decision,
                "expectation_met": str(
                    int(
                        result.decision == item.expected_decision
                        and result.reason_code == item.expected_reason_code
                    )
                ),
                "expected_reason_code": item.expected_reason_code,
                "reason_code": result.reason_code,
                "features": "|".join(result.features),
                "schema_count": str(result.schema_count),
                "interface_count": str(result.interface_count),
                "type_count": str(result.type_count),
                "entity_count": str(result.entity_count),
                "algorithm_count": str(result.algorithm_count),
                "constant_count": str(result.constant_count),
                "explicit_attribute_count": str(result.explicit_attribute_count),
                "derived_attribute_count": str(result.derived_attribute_count),
                "inverse_attribute_count": str(result.inverse_attribute_count),
                "where_rule_count": str(result.where_rule_count),
                "unique_rule_count": str(result.unique_rule_count),
                "token_count": str(result.token_count),
                "trivia_token_count": str(result.trivia_token_count),
                "source_bytes": str(result.source_bytes),
                "exact_reconstruction": str(int(result.exact_reconstruction)),
                "diagnostic_line": "" if result.diagnostic_line is None else str(result.diagnostic_line),
                "diagnostic_column": "" if result.diagnostic_column is None else str(result.diagnostic_column),
                "symbol_resolution": result.symbol_resolution,
                "type_checking": result.type_checking,
                "expression_validation": result.expression_validation,
                "rule_execution": result.rule_execution,
                "source_sha256": hashlib.sha256(item.source_bytes).hexdigest(),
            }
        )
    return rows


def inventory_rows(
    fixtures: Sequence[ExpressSchemaFixture],
) -> list[dict[str, str]]:
    """Flatten accepted schema declarations into an auditable inventory."""
    rows: list[dict[str, str]] = []
    for item in fixtures:
        if item.expected_decision != "accept":
            continue
        document = parse_express_document(item.source_bytes, limits=item.limits)
        for schema in document.schemas:
            rows.append(_inventory_row(item.fixture, schema.name, "schema", schema.name, "", "declaration envelope", schema.span.start_line))
            for interface in schema.interfaces:
                item_text = "*" if not interface.items else "|".join(
                    value.name if value.alias is None else f"{value.name} AS {value.alias}"
                    for value in interface.items
                )
                rows.append(_inventory_row(item.fixture, schema.name, f"interface_{interface.kind}", interface.schema_name, schema.name, item_text, interface.span.start_line))
            for schema_type in schema.types:
                rows.append(_inventory_row(item.fixture, schema.name, "type", schema_type.name, schema.name, type_reference_text(schema_type.underlying_type), schema_type.span.start_line))
                rows.extend(
                    _inventory_row(item.fixture, schema.name, "where_rule", rule.label, schema_type.name, rule.expression, rule.span.start_line)
                    for rule in schema_type.where_rules
                )
            for entity in schema.entities:
                header = "ABSTRACT" if entity.abstract else "concrete"
                if entity.supertypes:
                    header += "; SUBTYPE OF " + "|".join(entity.supertypes)
                if entity.supertype_expression:
                    header += "; SUPERTYPE OF " + entity.supertype_expression
                rows.append(_inventory_row(item.fixture, schema.name, "entity", entity.name, schema.name, header, entity.span.start_line))
                rows.extend(
                    _inventory_row(item.fixture, schema.name, f"attribute_{attribute.kind}", attribute.name, entity.name, type_reference_text(attribute.type_ref), attribute.span.start_line)
                    for attribute in entity.attributes
                )
                rows.extend(
                    _inventory_row(item.fixture, schema.name, "unique_rule", rule.label, entity.name, rule.expression, rule.span.start_line)
                    for rule in entity.unique_rules
                )
                rows.extend(
                    _inventory_row(item.fixture, schema.name, "where_rule", rule.label, entity.name, rule.expression, rule.span.start_line)
                    for rule in entity.where_rules
                )
            for algorithm in schema.algorithms:
                detail = (
                    "targets=" + "|".join(algorithm.applies_to)
                    if algorithm.kind == "rule"
                    else f"parameters={len(algorithm.parameters)}"
                )
                rows.append(_inventory_row(item.fixture, schema.name, algorithm.kind, algorithm.name, schema.name, detail, algorithm.span.start_line))
            rows.extend(
                _inventory_row(item.fixture, schema.name, "constant", constant.name, schema.name, type_reference_text(constant.type_ref), constant.span.start_line)
                for constant in schema.constants
            )
    return rows


def _inventory_row(
    fixture: str,
    schema: str,
    declaration_kind: str,
    name: str,
    parent: str,
    detail: str,
    source_line: int,
) -> dict[str, str]:
    return {
        "fixture": fixture,
        "schema": schema,
        "declaration_kind": declaration_kind,
        "name": name,
        "parent": parent,
        "detail": detail.replace("\n", " ").strip(),
        "source_line": str(source_line),
        "symbol_resolution": "not_attempted",
    }


def type_reference_text(type_ref: ExpressTypeReference) -> str:
    """Return a deterministic compact rendering of an unresolved type."""
    if type_ref.kind in {"simple", "named"}:
        value = str(type_ref.name)
        if type_ref.parameter is not None:
            value += f"({type_ref.parameter})"
        if type_ref.fixed:
            value += " FIXED"
        return value
    if type_ref.kind in {"select", "enumeration"}:
        return f"{type_ref.kind.upper()}({','.join(type_ref.members)})"
    bounds = ""
    if type_ref.lower_bound is not None:
        bounds = f" [{type_ref.lower_bound}:{type_ref.upper_bound}]"
    flags = ""
    if type_ref.optional:
        flags += " OPTIONAL"
    if type_ref.unique:
        flags += " UNIQUE"
    element = "" if type_ref.element_type is None else type_reference_text(type_ref.element_type)
    return f"{type_ref.aggregate_kind}{bounds} OF{flags} {element}".strip()


def coverage_rows() -> list[dict[str, str]]:
    """Describe implemented, envelope-only, and deferred grammar layers."""
    definitions = (
        ("ascii_lexical_source", "minimal_schema|invalid_source_character", "implemented_subset", "tokens and source spans", "non-ASCII source is rejected; encoded strings remain raw"),
        ("case_insensitive_identifiers", "mixed_case|duplicate_declaration", "implemented", "raw and normalized keyword forms", "identifier spelling is preserved; resolution is deferred"),
        ("tail_and_block_comments", "comments|unterminated_comment", "implemented", "trivia tokens", "nested block comments are bounded"),
        ("literal_tokens", "source_literals|invalid_real|invalid_binary", "implemented_subset", "typed lexical tokens", "literal types are not checked against declarations"),
        ("schema_envelope", "minimal_schema|multiple_schemas", "implemented", "schema declarations", "schema identification strings are not interpreted"),
        ("use_and_reference", "use_import|reference_import", "implemented", "interface specifications", "import targets and aliases are not resolved"),
        ("simple_and_named_types", "type_alias_where", "implemented", "unresolved type references", "domain equivalence is not computed"),
        ("aggregate_types", "aggregate_type", "implemented_subset", "kind, bounds, flags, element type", "bound expressions are stored, not evaluated"),
        ("select_and_enumeration", "select_type|enumeration_type", "implemented", "ordered member names", "members are not resolved or checked for uniqueness"),
        ("entity_subsuper_syntax", "entity_inheritance", "implemented_subset", "abstract flag, supertypes, expression envelope", "inheritance graphs and redeclarations are deferred"),
        ("entity_attributes", "explicit_attributes|derived_attribute|inverse_attribute", "implemented_subset", "explicit, derived, and inverse declarations", "derived expressions and inverse targets are unresolved"),
        ("where_and_unique", "unique_where", "envelope_only", "labels and source expressions", "expression grammar, typing, and execution are deferred"),
        ("constants", "constant_block", "envelope_only", "name, type, expression", "constant expressions are not evaluated"),
        ("functions_procedures_rules", "function_envelope|procedure_envelope|rule_envelope", "envelope_only", "headers, parameters, targets, source bodies", "statement grammar and execution are deferred"),
        ("symbol_resolution_and_type_checking", "none", "deferred", "explicit status fields", "planned for v0.26.0"),
    )
    return [
        {
            "feature": feature,
            "fixture": fixture,
            "implementation_status": status,
            "model_output": output,
            "claim_boundary": boundary,
        }
        for feature, fixture, status, output, boundary in definitions
    ]


def summary_rows(
    observations: Sequence[dict[str, str]],
    inventory: Sequence[dict[str, str]],
) -> list[dict[str, str]]:
    """Summarize corpus decisions and accepted declaration-model evidence."""
    decisions = Counter(row["observed_decision"] for row in observations)
    expected = Counter(row["expected_decision"] for row in observations)
    inventory_kinds = Counter(row["declaration_kind"] for row in inventory)
    rows = [
        {"scope": "corpus", "metric": "fixture_count", "value": str(len(observations))},
        {"scope": "corpus", "metric": "expectation_rate", "value": f"{sum(int(row['expectation_met']) for row in observations) / len(observations):.6f}"},
    ]
    for decision in ("accept", "quarantine", "reject"):
        rows.append({"scope": "expected", "metric": decision, "value": str(expected.get(decision, 0))})
        rows.append({"scope": "observed", "metric": decision, "value": str(decisions.get(decision, 0))})
    rows.append({"scope": "model", "metric": "inventory_row_count", "value": str(len(inventory))})
    for kind in sorted(inventory_kinds):
        rows.append({"scope": "model", "metric": kind, "value": str(inventory_kinds[kind])})
    return rows


def plot_results(
    observations: Sequence[dict[str, str]],
    inventory: Sequence[dict[str, str]],
    output_path: Path,
) -> None:
    """Visualize decisions, schema-model inventory, and semantic stage boundary."""
    figure, axes = plt.subplots(1, 3, figsize=(16.5, 6.3))
    decisions = ("accept", "quarantine", "reject")
    expected = Counter(row["expected_decision"] for row in observations)
    observed = Counter(row["observed_decision"] for row in observations)
    positions = np.arange(len(decisions))
    axes[0].bar(positions - 0.18, [expected[item] for item in decisions], width=0.36, label="expected", color="#457b9d")
    axes[0].bar(positions + 0.18, [observed[item] for item in decisions], width=0.36, label="observed", color="#2a9d8f")
    axes[0].set_xticks(positions, decisions)
    axes[0].set_ylabel("Fixture count")
    axes[0].set_title("Controlled decisions")
    axes[0].legend()
    axes[0].grid(axis="y", alpha=0.25)

    kind_groups = {
        "schema": {"schema", "interface_use", "interface_reference"},
        "types": {"type"},
        "entities": {"entity"},
        "attributes": {"attribute_explicit", "attribute_derived", "attribute_inverse"},
        "constraints": {"where_rule", "unique_rule"},
        "algorithms/constants": {"function", "procedure", "rule", "constant"},
    }
    kind_counts = Counter(row["declaration_kind"] for row in inventory)
    group_counts = [sum(kind_counts[item] for item in members) for members in kind_groups.values()]
    axes[1].barh(list(kind_groups), group_counts, color="#6d597a")
    axes[1].set_xlabel("Inventory rows")
    axes[1].set_title("Extracted declaration model")
    axes[1].grid(axis="x", alpha=0.25)

    stages = ("lexical", "declaration\nsyntax", "schema\nmodel", "symbol\nresolution", "type\nchecking", "rule\nexecution")
    stage_values = (1, 1, 1, 0, 0, 0)
    axes[2].bar(positions := np.arange(len(stages)), stage_values, color=["#2a9d8f"] * 3 + ["#d9d9d9"] * 3)
    axes[2].set_xticks(positions, stages, fontsize=8)
    axes[2].set_ylim(0, 1.18)
    axes[2].set_yticks((0, 1), ("deferred", "implemented"))
    axes[2].set_title("Claim boundary by stage")
    axes[2].grid(axis="y", alpha=0.25)

    figure.suptitle("EXPRESS Lexer, Parser, and Schema Model", fontsize=14, fontweight="bold")
    figure.text(0.5, 0.012, "Expressions and algorithm bodies are preserved as envelopes; name resolution, type checking, and execution are not attempted.", ha="center", fontsize=9)
    figure.tight_layout(rect=(0, 0.05, 1, 0.94))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Evaluate controlled EXPRESS syntax and schema-model extraction."
    )
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=Path("fixtures/express-schema-model"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument("--refresh-fixtures", action="store_true")
    return parser.parse_args()


def main() -> None:
    """Run the controlled EXPRESS grammar and schema-model experiment."""
    args = parse_args()
    definitions = build_express_schema_fixtures()
    if args.refresh_fixtures:
        refresh_fixture_corpus(args.fixture_dir, definitions)
    fixtures = load_fixture_corpus(args.fixture_dir, definitions)
    observations = observation_rows(fixtures)
    inventory = inventory_rows(fixtures)
    coverage = coverage_rows()
    summary = summary_rows(observations, inventory)
    write_csv(args.output_dir / OBSERVATIONS_NAME, observations, OBSERVATION_FIELDS)
    write_csv(args.output_dir / INVENTORY_NAME, inventory, INVENTORY_FIELDS)
    write_csv(args.output_dir / COVERAGE_NAME, coverage, COVERAGE_FIELDS)
    write_csv(args.output_dir / SUMMARY_NAME, summary, SUMMARY_FIELDS)
    plot_results(observations, inventory, args.output_dir / FIGURE_NAME)
    for name in (
        OBSERVATIONS_NAME,
        INVENTORY_NAME,
        COVERAGE_NAME,
        SUMMARY_NAME,
        FIGURE_NAME,
    ):
        print(f"Wrote {args.output_dir / name}")


if __name__ == "__main__":
    main()
