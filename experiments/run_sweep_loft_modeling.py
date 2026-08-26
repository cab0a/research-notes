"""Generate v0.45.0 sweep, loft, and surface-construction evidence."""

from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

from research_notes.brep_preview import write_shape_previews  # noqa: E402
from research_notes.modeling_common import vector_distance  # noqa: E402
from research_notes.sweep_loft_modeling import (  # noqa: E402
    CONTRACT_VERSION,
    SweepLoftProbe,
    probe_sweep_loft_modeling,
)


DECISION_NAME = "sweep_loft_decisions.csv"
OBSERVATION_NAME = "sweep_loft_observations.csv"
SUMMARY_NAME = "sweep_loft_summary.csv"
CONTRACT_NAME = "sweep_loft_contract.json"
FIGURE_NAME = "sweep_loft_modeling.png"
SHAPES_NAME = "sweep_loft_shapes.png"
MANIFEST_NAME = "manifest.csv"

DECISION_FIELDS = (
    "contract_version", "control_id", "operation", "input_description",
    "spine_continuity", "section_count", "expected_decision", "decision",
    "reason", "kernel_invoked", "builder_status", "error_on_surface",
)
OBSERVATION_FIELDS = (
    "contract_version", "stage", "control_id", "source_file", "source_sha256",
    "vertex_count", "edge_count", "face_count", "shell_count", "solid_count",
    "absolute_volume", "expected_volume", "volume_absolute_error", "surface_area",
    "expected_surface_area", "surface_area_absolute_error", "surface_centroid_x",
    "surface_centroid_y", "surface_centroid_z", "bounds_min", "bounds_max",
    "surface_counts", "maximum_vertex_tolerance", "maximum_edge_tolerance",
    "maximum_face_tolerance", "analyzer_valid",
)
SUMMARY_FIELDS = (
    "control_id", "topology_matches", "surface_counts_match",
    "volume_absolute_difference", "surface_area_absolute_difference",
    "surface_centroid_distance", "constructed_truth_matches",
    "step_imported_truth_matches", "input_envelope_ratio", "round_trip_passes",
)


def _float(value: float | None) -> str:
    return "" if value is None else format(value, ".17g")


def _pairs(values: tuple[tuple[str, object], ...]) -> str:
    return "|".join(f"{name}:{value}" for name, value in values)


def _vector(value: tuple[float, float, float]) -> str:
    return "|".join(_float(item) for item in value)


def decision_rows(probe: SweepLoftProbe) -> list[dict[str, object]]:
    """Flatten construction admissions and native outcomes."""
    controls = {item.control_id: item for item in probe.controls}
    rows: list[dict[str, object]] = []
    for item in probe.decisions:
        control = controls[item.control_id]
        rows.append({
            "contract_version": CONTRACT_VERSION,
            "control_id": item.control_id,
            "operation": control.operation,
            "input_description": control.input_description,
            "spine_continuity": control.spine_continuity,
            "section_count": control.section_count,
            "expected_decision": control.expected_decision,
            "decision": item.decision,
            "reason": item.reason,
            "kernel_invoked": int(item.kernel_invoked),
            "builder_status": item.builder_status,
            "error_on_surface": _float(item.error_on_surface),
        })
    return rows


def observation_rows(probe: SweepLoftProbe) -> list[dict[str, object]]:
    """Flatten accepted constructed and imported shape measurements."""
    rows: list[dict[str, object]] = []
    for item in probe.observations:
        metrics = item.metrics
        rows.append({
            "contract_version": CONTRACT_VERSION,
            "stage": item.stage,
            "control_id": item.control_id,
            "source_file": item.source_file or "",
            "source_sha256": item.source_sha256 or "",
            "vertex_count": metrics.vertex_count,
            "edge_count": metrics.edge_count,
            "face_count": metrics.face_count,
            "shell_count": metrics.shell_count,
            "solid_count": metrics.solid_count,
            "absolute_volume": _float(metrics.absolute_volume),
            "expected_volume": _float(item.expected_volume),
            "volume_absolute_error": _float(item.volume_absolute_error),
            "surface_area": _float(metrics.surface_area),
            "expected_surface_area": _float(item.expected_surface_area),
            "surface_area_absolute_error": _float(item.surface_area_absolute_error),
            "surface_centroid_x": _float(metrics.surface_centroid[0]),
            "surface_centroid_y": _float(metrics.surface_centroid[1]),
            "surface_centroid_z": _float(metrics.surface_centroid[2]),
            "bounds_min": _vector(metrics.bounds_min),
            "bounds_max": _vector(metrics.bounds_max),
            "surface_counts": _pairs(metrics.surface_counts),
            "maximum_vertex_tolerance": _float(metrics.maximum_vertex_tolerance),
            "maximum_edge_tolerance": _float(metrics.maximum_edge_tolerance),
            "maximum_face_tolerance": _float(metrics.maximum_face_tolerance),
            "analyzer_valid": int(metrics.analyzer_valid),
        })
    return rows


def summary_rows(probe: SweepLoftProbe) -> list[dict[str, object]]:
    """Compare each accepted result across construction and STEP import."""
    by_key = {(item.control_id, item.stage): item for item in probe.observations}
    rows: list[dict[str, object]] = []
    for control in probe.controls:
        if control.expected_decision == "reject":
            continue
        first = by_key[(control.control_id, "constructed")]
        second = by_key[(control.control_id, "step_imported")]
        topology_match = (
            first.metrics.vertex_count,
            first.metrics.edge_count,
            first.metrics.face_count,
            first.metrics.shell_count,
            first.metrics.solid_count,
        ) == (
            second.metrics.vertex_count,
            second.metrics.edge_count,
            second.metrics.face_count,
            second.metrics.shell_count,
            second.metrics.solid_count,
        )
        surface_match = first.metrics.surface_counts == second.metrics.surface_counts
        volume_difference = abs(first.metrics.absolute_volume - second.metrics.absolute_volume)
        area_difference = abs(first.metrics.surface_area - second.metrics.surface_area)
        centroid_distance = vector_distance(first.metrics.surface_centroid, second.metrics.surface_centroid)
        first_truth = (
            control.expected_volume is None
            or (
                first.volume_absolute_error is not None
                and first.surface_area_absolute_error is not None
                and first.volume_absolute_error <= 1.0e-8
                and first.surface_area_absolute_error <= 1.0e-8
            )
        )
        second_truth = (
            control.expected_volume is None
            or (
                second.volume_absolute_error is not None
                and second.surface_area_absolute_error is not None
                and second.volume_absolute_error <= 1.0e-8
                and second.surface_area_absolute_error <= 1.0e-8
            )
        )
        envelope_ratio: float | None = None
        if control.control_id == "smooth_square_loft":
            envelope_ratio = max(
                abs(first.metrics.bounds_min[0]),
                abs(first.metrics.bounds_min[1]),
                abs(first.metrics.bounds_max[0]),
                abs(first.metrics.bounds_max[1]),
            ) / 2.0
        passes = (
            topology_match and surface_match and first_truth and second_truth
            and volume_difference <= 1.0e-8 and area_difference <= 1.0e-8
            and centroid_distance <= 1.0e-8 and first.metrics.analyzer_valid
            and second.metrics.analyzer_valid
        )
        rows.append({
            "control_id": control.control_id,
            "topology_matches": int(topology_match),
            "surface_counts_match": int(surface_match),
            "volume_absolute_difference": _float(volume_difference),
            "surface_area_absolute_difference": _float(area_difference),
            "surface_centroid_distance": _float(centroid_distance),
            "constructed_truth_matches": "" if control.expected_volume is None else int(first_truth),
            "step_imported_truth_matches": "" if control.expected_volume is None else int(second_truth),
            "input_envelope_ratio": _float(envelope_ratio),
            "round_trip_passes": int(passes),
        })
    return rows


def _csv_bytes(rows: list[dict[str, object]], fields: tuple[str, ...]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _write_csv(path: Path, rows: list[dict[str, object]], fields: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_csv_bytes(rows, fields))


def _fixture_manifest(probe: SweepLoftProbe) -> bytes:
    rows = [{
        "control_id": item.fixture_id,
        "file_name": item.file_name,
        "source_bytes": len(item.source_bytes),
        "source_sha256": item.source_sha256,
        "generator": "experiments/run_sweep_loft_modeling.py",
        "binding_distribution_version": probe.binding_distribution_version,
        "step_processor": item.step_processor,
        "writer_status": item.writer_status,
        "reader_status": item.reader_status,
        "transferred_roots": item.transferred_roots,
    } for item in probe.fixtures]
    return _csv_bytes(rows, tuple(rows[0]))


def handle_fixtures(path: Path, probe: SweepLoftProbe, *, refresh: bool) -> None:
    """Write or verify normalized STEP fixtures for accepted controls."""
    expected = {item.file_name: item.source_bytes for item in probe.fixtures}
    expected[MANIFEST_NAME] = _fixture_manifest(probe)
    path.mkdir(parents=True, exist_ok=True)
    if refresh:
        for name, content in expected.items():
            (path / name).write_bytes(content)
        return
    unexpected = sorted(item.name for item in path.iterdir() if item.name not in expected)
    if unexpected:
        raise RuntimeError("unexpected fixture files: " + ", ".join(unexpected))
    for name, content in expected.items():
        target = path / name
        if not target.exists() or target.read_bytes() != content:
            raise RuntimeError(f"fixture differs; rerun with --refresh-fixtures: {target}")


def write_contract(path: Path, probe: SweepLoftProbe) -> None:
    """Write the construction, admission, and claim contract."""
    payload = {
        "contract_version": CONTRACT_VERSION,
        "study_version": "v0.45.0",
        "title": "Sweeps, Lofts, and Surface Construction",
        "controls": [{
            "control_id": item.control_id,
            "operation": item.operation,
            "input_description": item.input_description,
            "expected_decision": item.expected_decision,
            "expected_reason": item.expected_reason,
            "spine_continuity": item.spine_continuity,
            "section_count": item.section_count,
            "expected_volume": item.expected_volume,
            "expected_surface_area": item.expected_surface_area,
        } for item in probe.controls],
        "decision_csv": {"file": DECISION_NAME, "ordered_fields": list(DECISION_FIELDS)},
        "observation_csv": {"file": OBSERVATION_NAME, "ordered_fields": list(OBSERVATION_FIELDS)},
        "summary_csv": {"file": SUMMARY_NAME, "ordered_fields": list(SUMMARY_FIELDS)},
        "fixture_sha256": {item.file_name: item.source_sha256 for item in probe.fixtures},
        "claim_boundaries": [
            "only two G1 pipe spines and two controlled loft families are accepted",
            "C0 spine and insufficient-section inputs are rejected before native construction",
            "smooth interpolation may leave the envelope of its input sections",
            "B-spline support retention does not prove interpolation error over the full surface",
            "STEP output does not recover sweep paths, profiles, sections, or construction history",
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_figure(path: Path, probe: SweepLoftProbe) -> None:
    """Plot admission decisions and round-trip geometric residuals."""
    decisions = decision_rows(probe)
    summaries = summary_rows(probe)
    figure, axes = plt.subplots(1, 2, figsize=(13.5, 4.8), constrained_layout=True)
    labels = [item["control_id"].replace("_", " ") for item in decisions]
    axes[0].bar(
        range(len(decisions)),
        [1 if item["decision"] == "accept" else -1 for item in decisions],
        color=["#15803d" if item["decision"] == "accept" else "#b91c1c" for item in decisions],
    )
    axes[0].axhline(0.0, color="#334155", linewidth=0.8)
    axes[0].set_xticks(range(len(labels)), labels, rotation=28, ha="right")
    axes[0].set_yticks((-1, 1), ("Reject", "Accept"))
    axes[0].set_title("Precondition and construction decisions")
    summary_labels = [item["control_id"].replace("_", " ") for item in summaries]
    axes[1].bar(
        range(len(summaries)),
        [max(float(item["surface_area_absolute_difference"]), 1.0e-17) for item in summaries],
        color="#2563eb",
    )
    axes[1].set_yscale("log")
    axes[1].set_xticks(range(len(summary_labels)), summary_labels, rotation=28, ha="right")
    axes[1].set_ylabel("Constructed/imported area difference")
    axes[1].set_title("STEP round-trip residuals")
    figure.suptitle("v0.45.0 Sweeps, Lofts, and Surface Construction")
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160)
    plt.close(figure)


def run(output_dir: Path, fixture_dir: Path, *, refresh: bool) -> None:
    """Run and serialize the complete v0.45.0 experiment."""
    probe = probe_sweep_loft_modeling()
    handle_fixtures(fixture_dir, probe, refresh=refresh)
    _write_csv(output_dir / DECISION_NAME, decision_rows(probe), DECISION_FIELDS)
    _write_csv(output_dir / OBSERVATION_NAME, observation_rows(probe), OBSERVATION_FIELDS)
    _write_csv(output_dir / SUMMARY_NAME, summary_rows(probe), SUMMARY_FIELDS)
    write_contract(output_dir / CONTRACT_NAME, probe)
    write_figure(output_dir / FIGURE_NAME, probe)
    write_shape_previews(
        output_dir / SHAPES_NAME,
        tuple((name.replace("_", " ").title(), shape) for name, shape in probe.preview_shapes),
        title="v0.45.0 Accepted Sweep, Loft, and Surface Results",
        columns=3,
    )
    print(f"Wrote sweep, loft, and surface artifacts to {output_dir}")


def main() -> None:
    """Parse command-line arguments and run the experiment."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument("--fixture-dir", type=Path, default=Path("fixtures/sweep-loft-modeling"))
    parser.add_argument("--refresh-fixtures", action="store_true")
    arguments = parser.parse_args()
    run(arguments.output_dir, arguments.fixture_dir, refresh=arguments.refresh_fixtures)


if __name__ == "__main__":
    main()
