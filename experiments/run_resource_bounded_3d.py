"""Generate v0.50.0 resource-bounded 3D intake evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from dataclasses import asdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

from research_notes.brep_preview import write_shape_previews  # noqa: E402
from research_notes.resource_bounded_3d import (  # noqa: E402
    CONTRACT_VERSION,
    STAGES,
    IntakeProbe,
    build_intake_fixture_bytes,
    probe_resource_bounded_3d,
)


STAGE_NAME = "resource_bounded_3d_stages.csv"
DECISION_NAME = "resource_bounded_3d_decisions.csv"
SUMMARY_NAME = "resource_bounded_3d_summary.csv"
CONTRACT_NAME = "resource_bounded_3d_contract.json"
FIGURE_NAME = "resource_bounded_3d.png"
SHAPES_NAME = "resource_bounded_3d_shapes.png"
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


def _fixture_manifest_bytes(files: dict[str, bytes]) -> bytes:
    return _csv_bytes([
        {
            "file_name": name,
            "format": "stpz" if name.endswith(".stpz") else "step",
            "source_bytes": len(payload),
            "source_sha256": hashlib.sha256(payload).hexdigest(),
            "generator": "experiments/run_resource_bounded_3d.py",
        }
        for name, payload in sorted(files.items())
    ])


def handle_fixtures(path: Path, source_fixture_dir: Path, *, refresh: bool) -> None:
    """Write or byte-verify raw STEP and controlled ZIP-container fixtures."""
    expected = build_intake_fixture_bytes(source_fixture_dir)
    expected[MANIFEST_NAME] = _fixture_manifest_bytes(expected)
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


def stage_rows(probe: IntakeProbe) -> list[dict[str, object]]:
    return [
        {
            "contract_version": CONTRACT_VERSION,
            "control_id": item.control_id,
            "stage": item.stage,
            "decision": item.decision,
            "reason_code": item.reason_code,
            "observed_value": "" if item.observed_value is None else item.observed_value,
            "limit_value": "" if item.limit_value is None else item.limit_value,
            "worker_isolated": int(item.worker_isolated),
        }
        for item in probe.stages
    ]


def decision_rows(probe: IntakeProbe) -> list[dict[str, object]]:
    return [
        {
            "contract_version": CONTRACT_VERSION,
            "control_id": item.control_id,
            "input_sha256": item.input_sha256,
            "payload_sha256": item.payload_sha256 or "",
            "decision": item.decision,
            "reason_code": item.reason_code,
            "terminal_stage": item.terminal_stage,
            "expectation_met": int(item.expectation_met),
            "token_count": "" if item.token_count is None else item.token_count,
            "entity_count": "" if item.entity_count is None else item.entity_count,
            "reference_count": "" if item.reference_count is None else item.reference_count,
            "external_reference_count": "" if item.external_reference_count is None else item.external_reference_count,
            "edge_count": "" if item.edge_count is None else item.edge_count,
            "face_count": "" if item.face_count is None else item.face_count,
            "triangle_count": "" if item.triangle_count is None else item.triangle_count,
        }
        for item in probe.results
    ]


def summary_rows(probe: IntakeProbe) -> list[dict[str, object]]:
    rows = [
        {"scope": "corpus", "metric": "controls", "value": len(probe.controls)},
        {"scope": "corpus", "metric": "fixture_files", "value": len(probe.fixtures)},
        {"scope": "expectation", "metric": "matched_controls", "value": sum(item.expectation_met for item in probe.results)},
    ]
    rows.extend(
        {"scope": "decision", "metric": name, "value": sum(item.decision == name for item in probe.results)}
        for name in ("accept", "quarantine", "reject")
    )
    rows.extend(
        {"scope": "terminal_stage", "metric": stage, "value": sum(item.terminal_stage == stage for item in probe.results)}
        for stage in STAGES
    )
    return rows


def write_contract(path: Path, probe: IntakeProbe) -> None:
    payload = {
        "contract_version": CONTRACT_VERSION,
        "study_version": "v0.50.0",
        "title": "Resource-Bounded 3D Intake",
        "stage_order": list(STAGES),
        "controls": [
            {
                "control_id": item.control_id,
                "file_name": item.file_name,
                "condition": item.condition,
                "expected_decision": item.expected_decision,
                "expected_reason_code": item.expected_reason_code,
                "limits": asdict(item.limits),
                "kernel_delay_seconds": item.kernel_delay_seconds,
            }
            for item in probe.controls
        ],
        "fixtures": {item.file_name: item.source_sha256 for item in probe.fixtures},
        "claim_boundaries": [
            "preflight checks archive declarations and paths without extracting members to the filesystem",
            "syntax parsing and native kernel execution run in separate child processes with wall-clock timeouts",
            "external references are detected and quarantined without network retrieval",
            "timeouts and counters are policy evidence, not memory-safety or exploit-resistance proofs",
            "ZIP metadata may be deceptive and Python or native libraries may allocate memory before a counter is observed",
            "the controlled fixtures do not represent arbitrary malformed or adversarial STEP files",
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_figure(path: Path, probe: IntakeProbe) -> None:
    decisions = ("accept", "quarantine", "reject")
    decision_counts = [sum(item.decision == name for item in probe.results) for name in decisions]
    stage_counts = [sum(item.terminal_stage == name for item in probe.results) for name in STAGES]
    figure, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    axes[0].bar(decisions, decision_counts, color=("#70ad47", "#ffc000", "#c00000"))
    axes[0].set_ylabel("Controls")
    axes[0].set_title("Terminal decisions")
    axes[1].bar(STAGES, stage_counts, color="#4472c4")
    axes[1].tick_params(axis="x", rotation=30)
    axes[1].set_ylabel("Controls")
    axes[1].set_title("Stage that stopped intake")
    figure.suptitle("Resource-bounded STEP intake outcomes")
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160, metadata={"Software": "research-notes"})
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic resource-bounded 3D intake controls.")
    parser.add_argument("--source-fixture-dir", type=Path, default=Path("fixtures/step-round-trip-preservation"))
    parser.add_argument("--fixture-dir", type=Path, default=Path("fixtures/resource-bounded-3d"))
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument("--refresh-fixtures", action="store_true")
    args = parser.parse_args()
    handle_fixtures(args.fixture_dir, args.source_fixture_dir, refresh=args.refresh_fixtures)
    probe = probe_resource_bounded_3d(args.fixture_dir)
    _write_csv(args.output_dir / STAGE_NAME, stage_rows(probe))
    _write_csv(args.output_dir / DECISION_NAME, decision_rows(probe))
    _write_csv(args.output_dir / SUMMARY_NAME, summary_rows(probe))
    write_contract(args.output_dir / CONTRACT_NAME, probe)
    write_figure(args.output_dir / FIGURE_NAME, probe)
    write_shape_previews(args.output_dir / SHAPES_NAME, probe.preview_shapes, title="Resource-bounded 3D intake controls", columns=2)
    print(f"Wrote deterministic resource-bounded 3D evidence to {args.output_dir}")


if __name__ == "__main__":
    main()
