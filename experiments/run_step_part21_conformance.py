"""Evaluate Part 21 edition coverage and compare pinned public parsers."""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter, defaultdict
from collections.abc import Sequence
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

from research_notes import (  # noqa: E402
    Part21ConformanceFixture,
    build_part21_conformance_fixtures,
    external_parser_definitions,
    inspect_part21_conformance,
    observe_external_parser,
    verify_external_parser_checkout,
)


MANIFEST_NAME = "manifest.csv"
OBSERVATIONS_NAME = "step_part21_conformance_observations.csv"
MATRIX_NAME = "step_part21_parser_comparison.csv"
COVERAGE_NAME = "step_part21_grammar_coverage.csv"
PARSER_MANIFEST_NAME = "step_part21_parser_manifest.csv"
SUMMARY_NAME = "step_part21_conformance_summary.csv"
FIGURE_NAME = "step_part21_conformance.png"

MANIFEST_FIELDS = (
    "fixture",
    "category",
    "condition",
    "file_name",
    "expected_decision",
    "expected_reason_code",
    "expected_declared_edition",
    "expected_required_edition",
    "source_bytes",
    "source_sha256",
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
    "container",
    "implementation_level",
    "declared_edition",
    "required_edition",
    "declared_conformance_class",
    "required_conformance_class",
    "features",
    "data_section_count",
    "entity_count",
    "anchor_count",
    "external_reference_count",
    "signature_count",
    "archive_entry_count",
    "diagnostic_line",
    "diagnostic_column",
    "steputils_outcome",
    "ifcopenshell_parser_outcome",
    "schema_conformance",
    "source_sha256",
)
MATRIX_FIELDS = (
    "fixture",
    "category",
    "expected_decision",
    "parser",
    "outcome",
    "return_code",
    "diagnostic_class",
    "agreement_with_fixture_expectation",
)
COVERAGE_FIELDS = (
    "feature",
    "first_edition",
    "edition_1",
    "edition_2",
    "edition_3",
    "controlled_fixture",
    "implementation_status",
    "claim_boundary",
)
PARSER_MANIFEST_FIELDS = (
    "parser",
    "repository",
    "revision",
    "license",
    "comparison_role",
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
    fixtures: Sequence[Part21ConformanceFixture],
) -> list[dict[str, str]]:
    """Describe the exact conformance fixture bytes and expectations."""
    return [
        {
            "fixture": fixture.fixture,
            "category": fixture.category,
            "condition": fixture.condition,
            "file_name": fixture.file_name,
            "expected_decision": fixture.expected_decision,
            "expected_reason_code": fixture.expected_reason_code,
            "expected_declared_edition": str(fixture.expected_declared_edition),
            "expected_required_edition": str(fixture.expected_required_edition),
            "source_bytes": str(len(fixture.source_bytes)),
            "source_sha256": hashlib.sha256(fixture.source_bytes).hexdigest(),
        }
        for fixture in fixtures
    ]


def refresh_fixture_corpus(
    fixture_dir: Path,
    fixtures: Sequence[Part21ConformanceFixture],
) -> None:
    """Write the deterministic normal and malformed fixture corpus."""
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
    fixture_dir: Path,
    fixtures: Sequence[Part21ConformanceFixture],
) -> tuple[Part21ConformanceFixture, ...]:
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
    loaded: list[Part21ConformanceFixture] = []
    for fixture in fixtures:
        path = fixture_dir / fixture.file_name
        if not path.is_file() or path.read_bytes() != fixture.source_bytes:
            raise RuntimeError(f"fixture differs from definition: {fixture.file_name}")
        loaded.append(fixture)
    return tuple(loaded)


def collect_results(
    fixtures: Sequence[Part21ConformanceFixture],
    fixture_dir: Path,
    steputils_root: Path,
    ifcopenshell_parser_root: Path,
) -> dict[str, list[dict[str, str]]]:
    """Collect internal decisions and isolated external parser outcomes."""
    external_parsers = external_parser_definitions(
        steputils_root, ifcopenshell_parser_root
    )
    for parser in external_parsers:
        verify_external_parser_checkout(parser)

    observations: list[dict[str, str]] = []
    matrix: list[dict[str, str]] = []
    for fixture in fixtures:
        result = inspect_part21_conformance(fixture.source_bytes)
        expected_outcome = (
            "accept" if fixture.expected_decision == "accept" else "reject"
        )
        internal_outcome = (
            "accept" if result.decision == "accept" else "reject"
        )
        matrix.append(
            {
                "fixture": fixture.fixture,
                "category": fixture.category,
                "expected_decision": fixture.expected_decision,
                "parser": "research_notes",
                "outcome": internal_outcome,
                "return_code": "0" if internal_outcome == "accept" else "1",
                "diagnostic_class": result.reason_code,
                "agreement_with_fixture_expectation": str(
                    int(internal_outcome == expected_outcome)
                ),
            }
        )
        external_outcomes: dict[str, str] = {}
        for parser in external_parsers:
            observation = observe_external_parser(
                parser, fixture_dir / fixture.file_name
            )
            external_outcomes[parser.parser] = observation.outcome
            matrix.append(
                {
                    "fixture": fixture.fixture,
                    "category": fixture.category,
                    "expected_decision": fixture.expected_decision,
                    "parser": parser.parser,
                    "outcome": observation.outcome,
                    "return_code": (
                        ""
                        if observation.return_code is None
                        else str(observation.return_code)
                    ),
                    "diagnostic_class": observation.diagnostic_class,
                    "agreement_with_fixture_expectation": str(
                        int(observation.outcome == expected_outcome)
                    ),
                }
            )
        observations.append(
            {
                "fixture": fixture.fixture,
                "category": fixture.category,
                "condition": fixture.condition,
                "file_name": fixture.file_name,
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
                "container": result.container,
                "implementation_level": result.implementation_level,
                "declared_edition": str(result.declared_edition),
                "required_edition": str(result.required_edition),
                "declared_conformance_class": str(
                    result.declared_conformance_class
                ),
                "required_conformance_class": str(
                    result.required_conformance_class
                ),
                "features": "|".join(result.features),
                "data_section_count": str(result.data_section_count),
                "entity_count": str(result.entity_count),
                "anchor_count": str(result.anchor_count),
                "external_reference_count": str(
                    result.external_reference_count
                ),
                "signature_count": str(result.signature_count),
                "archive_entry_count": str(result.archive_entry_count),
                "diagnostic_line": (
                    "" if result.diagnostic_line is None else str(result.diagnostic_line)
                ),
                "diagnostic_column": (
                    ""
                    if result.diagnostic_column is None
                    else str(result.diagnostic_column)
                ),
                "steputils_outcome": external_outcomes["steputils"],
                "ifcopenshell_parser_outcome": external_outcomes[
                    "ifcopenshell_step_file_parser"
                ],
                "schema_conformance": result.schema_conformance,
                "source_sha256": hashlib.sha256(
                    fixture.source_bytes
                ).hexdigest(),
            }
        )
    return {"observations": observations, "matrix": matrix}


def grammar_coverage_rows() -> list[dict[str, str]]:
    """Return the controlled edition feature map supported by public sources."""
    definitions = (
        ("clear_text_core", 1, "edition1_minimal", "implemented", "EXPRESS schema rules are not evaluated"),
        ("comments", 1, "edition1_comment", "implemented", "comments are retained as source trivia"),
        ("binary_values", 1, "edition1_binary", "implemented", "binary syntax is checked without schema typing"),
        ("legacy_string_controls", 1, "edition1_legacy_x2|edition1_legacy_controls", "implemented_subset", "X, X2, X4, S, P, N, and F directives are decoded; not a certification suite"),
        ("multiple_data_sections", 2, "edition2_multiple_data", "implemented", "section-to-schema declaration is checked without EXPRESS validation"),
        ("edition2_header_entities", 2, "edition2_section_context", "syntax_only", "header record shape beyond FILE_DESCRIPTION and FILE_SCHEMA is not fully validated"),
        ("direct_utf8", 3, "edition3_utf8", "implemented", "invalid UTF-8 is rejected before tokenization"),
        ("anchor_section", 3, "edition3_anchor", "implemented", "anchor semantics and ECMAScript bindings are not executed"),
        ("reference_section", 3, "edition3_reference", "syntax_only", "external resources are never retrieved"),
        ("signature_section", 3, "edition3_signature", "syntax_only", "Base64 is decoded but CMS is not verified"),
        ("zip_transport", 3, "zip_root", "bounded_root_only", "root is read in memory; subsidiary references are not resolved"),
        ("optional_data_section", 3, "edition3_no_data", "implemented", "schema populations are not evaluated"),
        ("constant_and_value_references", 3, "edition3_constant|edition3_value_reference", "syntax_only", "EXPRESS constants and referenced value types are not resolved"),
    )
    rows: list[dict[str, str]] = []
    for feature, first_edition, fixture, status, boundary in definitions:
        rows.append(
            {
                "feature": feature,
                "first_edition": str(first_edition),
                "edition_1": str(int(first_edition <= 1)),
                "edition_2": str(int(first_edition <= 2)),
                "edition_3": str(int(first_edition <= 3)),
                "controlled_fixture": fixture,
                "implementation_status": status,
                "claim_boundary": boundary,
            }
        )
    return rows


def parser_manifest_rows(
    steputils_root: Path,
    ifcopenshell_parser_root: Path,
) -> list[dict[str, str]]:
    """Record exact public parser revisions and comparison roles."""
    external = external_parser_definitions(
        steputils_root, ifcopenshell_parser_root
    )
    licenses = {
        "steputils": "MIT",
        "ifcopenshell_step_file_parser": "LGPL-2.1",
    }
    rows = [
        {
            "parser": "research_notes",
            "repository": "https://github.com/cab0a/research-notes",
            "revision": "v0.24.0",
            "license": "MIT",
            "comparison_role": "controlled implementation under study",
        }
    ]
    rows.extend(
        {
            "parser": parser.parser,
            "repository": parser.repository,
            "revision": verify_external_parser_checkout(parser),
            "license": licenses[parser.parser],
            "comparison_role": "independent public parser observation",
        }
        for parser in external
    )
    return rows


def summarize(
    collected: dict[str, list[dict[str, str]]],
) -> list[dict[str, str]]:
    """Summarize fixture decisions without treating parser voting as truth."""
    observations = collected["observations"]
    matrix = collected["matrix"]
    decisions = Counter(row["observed_decision"] for row in observations)
    rows = [
        {"scope": "corpus", "metric": "fixture_count", "value": str(len(observations))},
        {
            "scope": "corpus",
            "metric": "expectation_rate",
            "value": f"{sum(int(row['expectation_met']) for row in observations) / len(observations):.6f}",
        },
    ]
    rows.extend(
        {
            "scope": "corpus",
            "metric": f"decision_{decision}",
            "value": str(decisions.get(decision, 0)),
        }
        for decision in ("accept", "quarantine", "reject")
    )
    by_parser: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in matrix:
        by_parser[row["parser"]].append(row)
    for parser, parser_rows in by_parser.items():
        rows.extend(
            (
                {
                    "scope": parser,
                    "metric": "accepted_fixture_count",
                    "value": str(sum(row["outcome"] == "accept" for row in parser_rows)),
                },
                {
                    "scope": parser,
                    "metric": "agreement_with_fixture_expectation_rate",
                    "value": f"{sum(int(row['agreement_with_fixture_expectation']) for row in parser_rows) / len(parser_rows):.6f}",
                },
            )
        )
    return rows


def plot_results(
    collected: dict[str, list[dict[str, str]]],
    coverage: list[dict[str, str]],
    output_path: Path,
) -> None:
    """Visualize edition feature floors and differential parser behavior."""
    figure, axes = plt.subplots(1, 3, figsize=(16.5, 6.5))
    feature_labels = [row["feature"].replace("_", "\n") for row in coverage]
    feature_matrix = np.array(
        [
            [int(row[f"edition_{edition}"]) for edition in (1, 2, 3)]
            for row in coverage
        ]
    )
    axes[0].imshow(feature_matrix, cmap="Blues", vmin=0, vmax=1, aspect="auto")
    axes[0].set_xticks(range(3), ("Edition 1", "Edition 2", "Edition 3"))
    axes[0].set_yticks(range(len(feature_labels)), feature_labels, fontsize=7)
    axes[0].set_title("Feature availability by edition")

    observations = collected["observations"]
    decision_counts = Counter(row["observed_decision"] for row in observations)
    decisions = ("accept", "quarantine", "reject")
    axes[1].bar(
        decisions,
        [decision_counts.get(decision, 0) for decision in decisions],
        color=("#2a9d8f", "#e9c46a", "#e76f51"),
    )
    axes[1].set_ylabel("Fixture count")
    axes[1].set_title("Internal controlled decisions")
    axes[1].grid(axis="y", alpha=0.25)

    matrix = collected["matrix"]
    parser_order = (
        "research_notes",
        "steputils",
        "ifcopenshell_step_file_parser",
    )
    positive_counts = []
    negative_counts = []
    for parser in parser_order:
        parser_rows = [row for row in matrix if row["parser"] == parser]
        positive_counts.append(
            sum(
                row["outcome"] == "accept"
                for row in parser_rows
                if row["expected_decision"] == "accept"
            )
        )
        negative_counts.append(
            sum(
                row["outcome"] == "accept"
                for row in parser_rows
                if row["expected_decision"] != "accept"
            )
        )
    x_positions = np.arange(len(parser_order))
    axes[2].bar(x_positions, positive_counts, label="accepted normal fixtures", color="#457b9d")
    axes[2].bar(x_positions, negative_counts, bottom=positive_counts, label="accepted malformed fixtures", color="#e76f51")
    axes[2].set_xticks(
        x_positions,
        ("research-notes", "STEPutils", "IfcOpenShell\nstep-file-parser"),
        fontsize=8,
    )
    axes[2].set_ylabel("Accepted fixture count")
    axes[2].set_title("Different acceptance boundaries")
    axes[2].legend(fontsize=8)
    axes[2].grid(axis="y", alpha=0.25)

    figure.suptitle(
        "Part 21 Grammar Coverage and Controlled Conformance",
        fontsize=14,
        fontweight="bold",
    )
    figure.text(
        0.5,
        0.012,
        "External parser acceptance is an observation, not a conformance oracle; EXPRESS schema validity is not evaluated.",
        ha="center",
        fontsize=9,
    )
    figure.tight_layout(rect=(0, 0.04, 1, 0.95))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Evaluate Part 21 editions and compare pinned public parsers."
    )
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=Path("fixtures/step-part21-conformance"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument(
        "--steputils-root", type=Path, default=Path("external/steputils")
    )
    parser.add_argument(
        "--ifcopenshell-parser-root",
        type=Path,
        default=Path("external/ifcopenshell_step_file_parser"),
    )
    parser.add_argument("--refresh-fixtures", action="store_true")
    return parser.parse_args()


def main() -> None:
    """Run the controlled conformance and differential parser experiment."""
    args = parse_args()
    definitions = build_part21_conformance_fixtures()
    if args.refresh_fixtures:
        refresh_fixture_corpus(args.fixture_dir, definitions)
    fixtures = load_fixture_corpus(args.fixture_dir, definitions)
    collected = collect_results(
        fixtures,
        args.fixture_dir,
        args.steputils_root,
        args.ifcopenshell_parser_root,
    )
    coverage = grammar_coverage_rows()
    parser_manifest = parser_manifest_rows(
        args.steputils_root, args.ifcopenshell_parser_root
    )
    summary = summarize(collected)
    write_csv(
        args.output_dir / OBSERVATIONS_NAME,
        collected["observations"],
        OBSERVATION_FIELDS,
    )
    write_csv(
        args.output_dir / MATRIX_NAME,
        collected["matrix"],
        MATRIX_FIELDS,
    )
    write_csv(args.output_dir / COVERAGE_NAME, coverage, COVERAGE_FIELDS)
    write_csv(
        args.output_dir / PARSER_MANIFEST_NAME,
        parser_manifest,
        PARSER_MANIFEST_FIELDS,
    )
    write_csv(args.output_dir / SUMMARY_NAME, summary, SUMMARY_FIELDS)
    plot_results(collected, coverage, args.output_dir / FIGURE_NAME)
    for name in (
        OBSERVATIONS_NAME,
        MATRIX_NAME,
        COVERAGE_NAME,
        PARSER_MANIFEST_NAME,
        SUMMARY_NAME,
        FIGURE_NAME,
    ):
        print(f"Wrote {args.output_dir / name}")


if __name__ == "__main__":
    main()
