"""Evaluate the unified source-preserving Part 21 parser foundation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

from research_notes import (  # noqa: E402
    STEPSourceModelFixture,
    build_step_source_model_fixtures,
    inspect_part21_source_model,
    parse_part21_document,
)


MANIFEST_NAME = "manifest.csv"
OBSERVATIONS_NAME = "step_part21_source_model_observations.csv"
TOKENS_NAME = "step_part21_token_inventory.csv"
SUMMARY_NAME = "step_part21_source_model_summary.csv"
FIGURE_NAME = "step_part21_source_model.png"

MANIFEST_FIELDS = (
    "fixture",
    "condition",
    "file_name",
    "expected_decision",
    "expected_reason_code",
    "max_file_bytes",
    "max_tokens",
    "max_entities",
    "max_references",
    "max_nesting_depth",
    "max_token_chars",
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
    "syntactically_parsed",
    "exact_source_reconstruction",
    "source_bytes",
    "source_characters",
    "token_count",
    "significant_token_count",
    "trivia_token_count",
    "comment_count",
    "header_record_count",
    "data_section_count",
    "entity_count",
    "simple_entity_count",
    "complex_entity_count",
    "reference_count",
    "diagnostic_line",
    "diagnostic_column",
    "schema_conformance",
    "source_sha256",
)
TOKEN_FIELDS = (
    "fixture",
    "token_index",
    "kind",
    "raw_json",
    "value_json",
    "start_offset",
    "end_offset",
    "start_byte",
    "end_byte",
    "start_line",
    "start_column",
    "end_line",
    "end_column",
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
    fixtures: Sequence[STEPSourceModelFixture],
) -> list[dict[str, str]]:
    """Describe exact fixture bytes, limits, and expected decisions."""
    rows: list[dict[str, str]] = []
    for fixture in fixtures:
        rows.append(
            {
                "fixture": fixture.fixture,
                "condition": fixture.condition,
                "file_name": fixture.file_name,
                "expected_decision": fixture.expected_decision,
                "expected_reason_code": fixture.expected_reason_code,
                **{
                    field_name: str(value)
                    for field_name, value in vars(fixture.limits).items()
                },
                "source_bytes": str(len(fixture.source_bytes)),
                "source_sha256": hashlib.sha256(
                    fixture.source_bytes
                ).hexdigest(),
            }
        )
    return rows


def refresh_fixture_corpus(
    fixture_dir: Path, fixtures: Sequence[STEPSourceModelFixture]
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
    fixture_dir: Path, fixtures: Sequence[STEPSourceModelFixture]
) -> tuple[STEPSourceModelFixture, ...]:
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

    loaded: list[STEPSourceModelFixture] = []
    for fixture in fixtures:
        path = fixture_dir / fixture.file_name
        if not path.is_file():
            raise RuntimeError(f"missing Part 21 fixture: {path}")
        source_bytes = path.read_bytes()
        if source_bytes != fixture.source_bytes:
            raise RuntimeError(f"fixture differs from definition: {path.name}")
        loaded.append(
            STEPSourceModelFixture(
                **{**vars(fixture), "source_bytes": source_bytes}
            )
        )
    return tuple(loaded)


def collect_results(
    fixtures: Sequence[STEPSourceModelFixture],
) -> dict[str, list[dict[str, str]]]:
    """Inspect fixtures and expose exact token coordinates for parsed inputs."""
    observations: list[dict[str, str]] = []
    tokens: list[dict[str, str]] = []
    for fixture in fixtures:
        result = inspect_part21_source_model(
            fixture.source_bytes, limits=fixture.limits
        )
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
                "syntactically_parsed": str(int(result.syntactically_parsed)),
                "exact_source_reconstruction": str(
                    int(result.exact_source_reconstruction)
                ),
                "source_bytes": str(result.source_bytes),
                "source_characters": str(result.source_characters),
                "token_count": str(result.token_count),
                "significant_token_count": str(result.significant_token_count),
                "trivia_token_count": str(result.trivia_token_count),
                "comment_count": str(result.comment_count),
                "header_record_count": str(result.header_record_count),
                "data_section_count": str(result.data_section_count),
                "entity_count": str(result.entity_count),
                "simple_entity_count": str(result.simple_entity_count),
                "complex_entity_count": str(result.complex_entity_count),
                "reference_count": str(result.reference_count),
                "diagnostic_line": (
                    "" if result.diagnostic_line is None else str(result.diagnostic_line)
                ),
                "diagnostic_column": (
                    ""
                    if result.diagnostic_column is None
                    else str(result.diagnostic_column)
                ),
                "schema_conformance": result.schema_conformance,
                "source_sha256": hashlib.sha256(
                    fixture.source_bytes
                ).hexdigest(),
            }
        )
        if not result.syntactically_parsed:
            continue
        document = parse_part21_document(
            fixture.source_bytes, limits=fixture.limits
        )
        for token_index, token in enumerate(document.tokens):
            tokens.append(
                {
                    "fixture": fixture.fixture,
                    "token_index": str(token_index),
                    "kind": token.kind,
                    "raw_json": json.dumps(token.raw, ensure_ascii=False),
                    "value_json": json.dumps(token.value, ensure_ascii=False),
                    "start_offset": str(token.span.start_offset),
                    "end_offset": str(token.span.end_offset),
                    "start_byte": str(token.span.start_byte),
                    "end_byte": str(token.span.end_byte),
                    "start_line": str(token.span.start_line),
                    "start_column": str(token.span.start_column),
                    "end_line": str(token.span.end_line),
                    "end_column": str(token.span.end_column),
                }
            )
    _validate_results(observations)
    return {"observations": observations, "tokens": tokens}


def _validate_results(observations: Sequence[dict[str, str]]) -> None:
    """Enforce the preregistered controlled relationships."""
    if len(observations) != 10:
        raise RuntimeError("expected ten Part 21 source-model fixtures")
    if any(row["expectation_met"] != "1" for row in observations):
        raise RuntimeError("a Part 21 source-model expectation failed")
    decisions = Counter(row["observed_decision"] for row in observations)
    if decisions != {"accept": 5, "quarantine": 2, "reject": 3}:
        raise RuntimeError(f"unexpected decision totals: {dict(decisions)}")
    accepted = [
        row for row in observations if row["observed_decision"] == "accept"
    ]
    if any(row["exact_source_reconstruction"] != "1" for row in accepted):
        raise RuntimeError("an accepted source failed exact reconstruction")


def summarize(
    collected: dict[str, list[dict[str, str]]],
) -> list[dict[str, str]]:
    """Build compact corpus and source-coordinate summary rows."""
    observations = collected["observations"]
    decisions = Counter(row["observed_decision"] for row in observations)
    accepted = [
        row for row in observations if row["observed_decision"] == "accept"
    ]
    utf8 = next(row for row in observations if row["fixture"] == "utf8_coordinates")
    rows = [
        {"scope": "corpus", "metric": "fixture_count", "value": "10"},
        {"scope": "corpus", "metric": "expectation_rate", "value": "1.000000"},
        {
            "scope": "accepted",
            "metric": "exact_source_reconstruction_rate",
            "value": f"{sum(int(row['exact_source_reconstruction']) for row in accepted) / len(accepted):.6f}",
        },
        {
            "scope": "accepted",
            "metric": "token_inventory_rows",
            "value": str(len(collected["tokens"])),
        },
        {
            "scope": "utf8_coordinates",
            "metric": "byte_minus_character_count",
            "value": str(int(utf8["source_bytes"]) - int(utf8["source_characters"])),
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
    return rows


def plot_source_model(
    collected: dict[str, list[dict[str, str]]], output_path: Path
) -> None:
    """Visualize parser decisions, retained trivia, and UTF-8 coordinates."""
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
    axes[0].set_title("Syntax failures and resource limits remain distinct")
    axes[0].grid(axis="y", alpha=0.25)

    selected_names = (
        "trivia_preservation",
        "utf8_coordinates",
        "simple_and_complex",
        "forward_reference",
    )
    selected = [
        next(row for row in observations if row["fixture"] == name)
        for name in selected_names
    ]
    selected_x = np.arange(len(selected))
    significant = np.array([int(row["significant_token_count"]) for row in selected])
    trivia = np.array([int(row["trivia_token_count"]) for row in selected])
    axes[1].bar(selected_x, significant, label="grammar tokens", color="#457b9d")
    axes[1].bar(
        selected_x,
        trivia,
        bottom=significant,
        label="preserved whitespace/comments",
        color="#a8dadc",
    )
    axes[1].set_xticks(
        selected_x,
        [name.replace("_", "\n") for name in selected_names],
        fontsize=9,
    )
    axes[1].set_ylabel("Tokens")
    axes[1].set_title("The concrete source model retains grammar and trivia tokens")
    axes[1].legend()
    axes[1].grid(axis="y", alpha=0.25)

    utf8 = next(row for row in observations if row["fixture"] == "utf8_coordinates")
    figure.suptitle(
        "Unified Part 21 Lexer, Grammar, and Source Model",
        fontsize=14,
        fontweight="bold",
    )
    figure.text(
        0.5,
        0.012,
        (
            "All 5 accepted fixtures reconstruct exactly; the UTF-8 fixture has "
            f"{int(utf8['source_bytes']) - int(utf8['source_characters'])} more bytes than characters. "
            "EXPRESS conformance was not evaluated."
        ),
        ha="center",
        fontsize=9,
    )
    figure.tight_layout(rect=(0, 0.035, 1, 0.96))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Evaluate the unified source-preserving Part 21 parser."
    )
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=Path("fixtures/step-part21-source-model"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument("--refresh-fixtures", action="store_true")
    return parser.parse_args()


def main() -> None:
    """Run the controlled experiment and write deterministic artifacts."""
    args = parse_args()
    definitions = build_step_source_model_fixtures()
    if args.refresh_fixtures:
        refresh_fixture_corpus(args.fixture_dir, definitions)
    fixtures = load_fixture_corpus(args.fixture_dir, definitions)
    collected = collect_results(fixtures)
    write_csv(
        args.output_dir / OBSERVATIONS_NAME,
        collected["observations"],
        OBSERVATION_FIELDS,
    )
    write_csv(
        args.output_dir / TOKENS_NAME,
        collected["tokens"],
        TOKEN_FIELDS,
    )
    write_csv(
        args.output_dir / SUMMARY_NAME,
        summarize(collected),
        SUMMARY_FIELDS,
    )
    plot_source_model(collected, args.output_dir / FIGURE_NAME)
    print(f"Wrote {args.output_dir / OBSERVATIONS_NAME}")
    print(f"Wrote {args.output_dir / TOKENS_NAME}")
    print(f"Wrote {args.output_dir / SUMMARY_NAME}")
    print(f"Wrote {args.output_dir / FIGURE_NAME}")


if __name__ == "__main__":
    main()
