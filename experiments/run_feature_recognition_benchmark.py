"""Generate v0.52.0 feature-recognition robustness evidence."""

from __future__ import annotations

import argparse
import csv
import io
import json
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

from research_notes.brep_preview import write_shape_previews  # noqa: E402
from research_notes.feature_benchmark import (  # noqa: E402
    CONTRACT_VERSION,
    FeatureBenchmarkProbe,
    probe_feature_benchmark,
)


OBSERVATION_NAME = "feature_benchmark_observations.csv"
CONFUSION_NAME = "feature_benchmark_confusion.csv"
SUMMARY_NAME = "feature_benchmark_summary.csv"
CONTRACT_NAME = "feature_benchmark_contract.json"
FIGURE_NAME = "feature_benchmark.png"
SHAPES_NAME = "feature_benchmark_shapes.png"
MANIFEST_NAME = "manifest.csv"


def _csv_bytes(rows: list[dict[str, object]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=tuple(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_csv_bytes(rows))


def observation_rows(probe: FeatureBenchmarkProbe) -> list[dict[str, object]]:
    cases = {item.case_id: item for item in probe.cases}
    return [
        {
            "contract_version": CONTRACT_VERSION,
            "case_id": item.case_id,
            "source_control_id": item.source_control_id,
            "perturbation": item.perturbation,
            "stage": item.stage,
            "expected_label": item.expected_label,
            "observed_label": item.observed_label,
            "candidate_count": item.candidate_count,
            "decision": item.decision,
            "reason": item.reason,
            "classification_correct": int(item.classification_correct),
            "dimensions_correct": int(item.dimensions_correct),
            "scale_factor": format(cases[item.case_id].scale_factor, ".17g"),
            "rotation_degrees": format(cases[item.case_id].rotation_degrees, ".17g"),
            "assigned_tolerance": format(cases[item.case_id].assigned_tolerance, ".17g"),
            "healing_applied": int(cases[item.case_id].healing_applied),
            "source_file": item.source_file or "",
            "source_sha256": item.source_sha256 or "",
        }
        for item in probe.observations
    ]


def confusion_rows(probe: FeatureBenchmarkProbe) -> list[dict[str, object]]:
    counts = Counter(
        (item.stage, item.expected_label, item.observed_label)
        for item in probe.observations
    )
    return [
        {
            "stage": stage,
            "expected_label": expected,
            "observed_label": observed,
            "count": count,
        }
        for (stage, expected, observed), count in sorted(counts.items())
    ]


def summary_rows(probe: FeatureBenchmarkProbe) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = [
        {"scope": "corpus", "metric": "cases", "value": len(probe.cases)},
        {"scope": "corpus", "metric": "step_files", "value": len(probe.fixtures)},
        {"scope": "corpus", "metric": "observations", "value": len(probe.observations)},
    ]
    for stage in ("constructed", "step_imported"):
        selected = [item for item in probe.observations if item.stage == stage]
        for decision in ("accept", "reject", "abstain", "incorrect"):
            rows.append(
                {
                    "scope": stage,
                    "metric": f"decision_{decision}",
                    "value": sum(item.decision == decision for item in selected),
                }
            )
        rows.append(
            {
                "scope": stage,
                "metric": "classification_correct",
                "value": sum(item.classification_correct for item in selected),
            }
        )
    for perturbation in sorted({item.perturbation for item in probe.observations}):
        selected = [
            item
            for item in probe.observations
            if item.stage == "step_imported" and item.perturbation == perturbation
        ]
        rows.append(
            {
                "scope": perturbation,
                "metric": "classification_correct",
                "value": sum(item.classification_correct for item in selected),
            }
        )
        rows.append(
            {"scope": perturbation, "metric": "cases", "value": len(selected)}
        )
    return rows


def _manifest_bytes(probe: FeatureBenchmarkProbe) -> bytes:
    return _csv_bytes(
        [
            {
                "case_id": case.case_id,
                "file_name": fixture.file_name,
                "source_bytes": len(fixture.source_bytes),
                "source_sha256": fixture.source_sha256,
                "generator": "experiments/run_feature_recognition_benchmark.py",
                "binding_distribution_version": probe.binding_distribution_version,
            }
            for case, fixture in zip(probe.cases, probe.fixtures, strict=True)
        ]
    )


def handle_fixtures(path: Path, probe: FeatureBenchmarkProbe, *, refresh: bool) -> None:
    expected = {item.file_name: item.source_bytes for item in probe.fixtures}
    expected[MANIFEST_NAME] = _manifest_bytes(probe)
    path.mkdir(parents=True, exist_ok=True)
    if refresh:
        for name, payload in expected.items():
            (path / name).write_bytes(payload)
        return
    unexpected = sorted(item.name for item in path.iterdir() if item.name not in expected)
    if unexpected:
        raise RuntimeError("unexpected fixture files: " + ", ".join(unexpected))
    for name, payload in expected.items():
        target = path / name
        if not target.exists() or target.read_bytes() != payload:
            raise RuntimeError(f"fixture differs; rerun with --refresh-fixtures: {target}")


def write_contract(path: Path, probe: FeatureBenchmarkProbe) -> None:
    payload = {
        "contract_version": CONTRACT_VERSION,
        "study_version": "v0.52.0",
        "title": "Feature Recognition Robustness and Benchmarking",
        "primary_key": ["case_id", "stage"],
        "perturbations": sorted({item.perturbation for item in probe.cases}),
        "fixtures": {item.file_name: item.source_sha256 for item in probe.fixtures},
        "claim_boundaries": [
            "construction labels are synthetic truth and not recovered STEP history",
            "the benchmark covers eight shape families and four perturbations only",
            "an abstention records a bounded rule limitation rather than an unknown universal class",
            "assigned tolerance and healing do not simulate arbitrary damaged production geometry",
            "accuracy on generated controls is not evidence of production feature-recognition accuracy",
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_figure(path: Path, probe: FeatureBenchmarkProbe) -> None:
    perturbations = sorted({item.perturbation for item in probe.observations})
    decisions = ("accept", "reject", "abstain", "incorrect")
    colors = ("#4c78a8", "#59a14f", "#f28e2b", "#e15759")
    figure, axis = plt.subplots(figsize=(10, 5.5))
    bottoms = [0] * len(perturbations)
    for decision, color in zip(decisions, colors, strict=True):
        values = [
            sum(
                item.stage == "step_imported"
                and item.perturbation == perturbation
                and item.decision == decision
                for item in probe.observations
            )
            for perturbation in perturbations
        ]
        axis.bar(perturbations, values, bottom=bottoms, label=decision, color=color)
        bottoms = [a + b for a, b in zip(bottoms, values, strict=True)]
    axis.set_ylabel("STEP-imported cases")
    axis.set_title("Bounded feature-rule outcomes under controlled perturbations")
    axis.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.13))
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160, metadata={"Software": "research-notes"})
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the deterministic B-Rep feature benchmark.")
    parser.add_argument("--fixture-dir", type=Path, default=Path("fixtures/feature-recognition-benchmark"))
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument("--refresh-fixtures", action="store_true")
    args = parser.parse_args()
    probe = probe_feature_benchmark()
    handle_fixtures(args.fixture_dir, probe, refresh=args.refresh_fixtures)
    _write_csv(args.output_dir / OBSERVATION_NAME, observation_rows(probe))
    _write_csv(args.output_dir / CONFUSION_NAME, confusion_rows(probe))
    _write_csv(args.output_dir / SUMMARY_NAME, summary_rows(probe))
    write_contract(args.output_dir / CONTRACT_NAME, probe)
    write_figure(args.output_dir / FIGURE_NAME, probe)
    write_shape_previews(args.output_dir / SHAPES_NAME, probe.preview_shapes, title="Feature benchmark baseline controls", columns=4)
    print(f"Wrote deterministic feature benchmark evidence to {args.output_dir}")


if __name__ == "__main__":
    main()
