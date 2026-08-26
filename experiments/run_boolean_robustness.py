"""Generate v0.46.0 Boolean-operation and robustness evidence."""

from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

from research_notes.boolean_robustness import (  # noqa: E402
    CONTRACT_VERSION,
    BooleanProbe,
    probe_boolean_robustness,
)
from research_notes.brep_preview import write_shape_previews  # noqa: E402
from research_notes.modeling_common import vector_distance  # noqa: E402


DECISION_NAME = "boolean_operation_decisions.csv"
OBSERVATION_NAME = "boolean_operation_observations.csv"
SUMMARY_NAME = "boolean_operation_summary.csv"
TOLERANCE_NAME = "boolean_tolerance_relations.csv"
CONTRACT_NAME = "boolean_operation_contract.json"
FIGURE_NAME = "boolean_operation_robustness.png"
SHAPES_NAME = "boolean_operation_shapes.png"
MANIFEST_NAME = "manifest.csv"

DECISION_FIELDS = (
    "contract_version", "control_id", "operation", "relationship",
    "first_cuboid", "second_cuboid", "requested_fuzzy_value",
    "applied_fuzzy_value", "is_done", "has_history",
    "first_operand_unchanged", "second_operand_unchanged",
    "commutative_invariants_match", "reverse_volume_difference",
    "reverse_surface_area_difference",
)
OBSERVATION_FIELDS = (
    "contract_version", "stage", "control_id", "source_file", "source_sha256",
    "vertex_count", "edge_count", "face_count", "shell_count", "solid_count",
    "absolute_volume", "expected_exact_volume", "volume_exact_set_difference",
    "surface_area", "expected_exact_surface_area",
    "surface_area_exact_set_difference", "surface_centroid_x",
    "surface_centroid_y", "surface_centroid_z", "surface_counts",
    "maximum_vertex_tolerance", "maximum_edge_tolerance",
    "maximum_face_tolerance", "analyzer_valid",
)
SUMMARY_FIELDS = (
    "control_id", "expected_solid_count", "constructed_solid_count",
    "step_imported_solid_count", "expected_solid_count_matches",
    "topology_matches", "surface_counts_match", "volume_absolute_difference",
    "surface_area_absolute_difference", "surface_centroid_distance",
    "constructed_exact_set_measure_matches", "step_imported_exact_set_measure_matches",
    "round_trip_passes",
)
TOLERANCE_FIELDS = (
    "relation_id", "gap", "default_requested_fuzzy", "fuzzy_requested_fuzzy",
    "default_solid_count", "fuzzy_solid_count", "solid_count_changed",
    "default_exact_volume_difference", "fuzzy_exact_volume_difference",
    "fuzzy_maximum_vertex_tolerance", "fuzzy_bridges_gap",
)


def _float(value: float | None) -> str:
    return "" if value is None else format(value, ".17g")


def _tuple(values: tuple[object, ...]) -> str:
    return "|".join(str(value) for value in values)


def decision_rows(probe: BooleanProbe) -> list[dict[str, object]]:
    """Flatten Boolean inputs, options, and operation-local outcomes."""
    controls = {item.control_id: item for item in probe.controls}
    rows: list[dict[str, object]] = []
    for item in probe.decisions:
        control = controls[item.control_id]
        rows.append({
            "contract_version": CONTRACT_VERSION,
            "control_id": item.control_id,
            "operation": control.operation,
            "relationship": control.relationship,
            "first_cuboid": _tuple(control.first_cuboid),
            "second_cuboid": _tuple(control.second_cuboid),
            "requested_fuzzy_value": _float(control.requested_fuzzy_value),
            "applied_fuzzy_value": _float(item.applied_fuzzy_value),
            "is_done": int(item.is_done),
            "has_history": int(item.has_history),
            "first_operand_unchanged": int(item.first_operand_unchanged),
            "second_operand_unchanged": int(item.second_operand_unchanged),
            "commutative_invariants_match": "" if item.commutative_invariants_match is None else int(item.commutative_invariants_match),
            "reverse_volume_difference": _float(item.reverse_volume_difference),
            "reverse_surface_area_difference": _float(item.reverse_surface_area_difference),
        })
    return rows


def observation_rows(probe: BooleanProbe) -> list[dict[str, object]]:
    """Flatten constructed and imported Boolean-result measurements."""
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
            "expected_exact_volume": _float(item.expected_exact_volume),
            "volume_exact_set_difference": _float(item.volume_exact_set_difference),
            "surface_area": _float(metrics.surface_area),
            "expected_exact_surface_area": _float(item.expected_exact_surface_area),
            "surface_area_exact_set_difference": _float(item.surface_area_exact_set_difference),
            "surface_centroid_x": _float(metrics.surface_centroid[0]),
            "surface_centroid_y": _float(metrics.surface_centroid[1]),
            "surface_centroid_z": _float(metrics.surface_centroid[2]),
            "surface_counts": _tuple(metrics.surface_counts),
            "maximum_vertex_tolerance": _float(metrics.maximum_vertex_tolerance),
            "maximum_edge_tolerance": _float(metrics.maximum_edge_tolerance),
            "maximum_face_tolerance": _float(metrics.maximum_face_tolerance),
            "analyzer_valid": int(metrics.analyzer_valid),
        })
    return rows


def summary_rows(probe: BooleanProbe) -> list[dict[str, object]]:
    """Compare exact-set truth and STEP round-trip invariants."""
    by_key = {(item.control_id, item.stage): item for item in probe.observations}
    rows: list[dict[str, object]] = []
    for control in probe.controls:
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
        surfaces_match = first.metrics.surface_counts == second.metrics.surface_counts
        volume_difference = abs(first.metrics.absolute_volume - second.metrics.absolute_volume)
        area_difference = abs(first.metrics.surface_area - second.metrics.surface_area)
        centroid_distance = vector_distance(first.metrics.surface_centroid, second.metrics.surface_centroid)
        first_exact = (
            first.volume_exact_set_difference <= 1.0e-8
            and first.surface_area_exact_set_difference <= 1.0e-8
        )
        second_exact = (
            second.volume_exact_set_difference <= 1.0e-8
            and second.surface_area_exact_set_difference <= 1.0e-8
        )
        solid_match = (
            first.metrics.solid_count == control.expected_solid_count
            and second.metrics.solid_count == control.expected_solid_count
        )
        passes = (
            topology_match and surfaces_match and solid_match
            and volume_difference <= 1.0e-8 and area_difference <= 1.0e-8
            and centroid_distance <= 1.0e-8 and first.metrics.analyzer_valid
            and second.metrics.analyzer_valid
            and (not control.expects_exact_set_measure or (first_exact and second_exact))
        )
        rows.append({
            "control_id": control.control_id,
            "expected_solid_count": control.expected_solid_count,
            "constructed_solid_count": first.metrics.solid_count,
            "step_imported_solid_count": second.metrics.solid_count,
            "expected_solid_count_matches": int(solid_match),
            "topology_matches": int(topology_match),
            "surface_counts_match": int(surfaces_match),
            "volume_absolute_difference": _float(volume_difference),
            "surface_area_absolute_difference": _float(area_difference),
            "surface_centroid_distance": _float(centroid_distance),
            "constructed_exact_set_measure_matches": "" if not control.expects_exact_set_measure else int(first_exact),
            "step_imported_exact_set_measure_matches": "" if not control.expects_exact_set_measure else int(second_exact),
            "round_trip_passes": int(passes),
        })
    return rows


def tolerance_rows(probe: BooleanProbe) -> list[dict[str, object]]:
    """Compare the same near-gap input under default and fuzzy settings."""
    controls = {item.control_id: item for item in probe.controls}
    constructed = {
        item.control_id: item for item in probe.observations if item.stage == "constructed"
    }
    default = constructed["near_gap_fuse_default"]
    fuzzy = constructed["near_gap_fuse_fuzzy"]
    return [{
        "relation_id": "near_gap_default_vs_fuzzy",
        "gap": _float(0.00005),
        "default_requested_fuzzy": _float(controls["near_gap_fuse_default"].requested_fuzzy_value),
        "fuzzy_requested_fuzzy": _float(controls["near_gap_fuse_fuzzy"].requested_fuzzy_value),
        "default_solid_count": default.metrics.solid_count,
        "fuzzy_solid_count": fuzzy.metrics.solid_count,
        "solid_count_changed": int(default.metrics.solid_count != fuzzy.metrics.solid_count),
        "default_exact_volume_difference": _float(default.volume_exact_set_difference),
        "fuzzy_exact_volume_difference": _float(fuzzy.volume_exact_set_difference),
        "fuzzy_maximum_vertex_tolerance": _float(fuzzy.metrics.maximum_vertex_tolerance),
        "fuzzy_bridges_gap": int(default.metrics.solid_count == 2 and fuzzy.metrics.solid_count == 1),
    }]


def _csv_bytes(rows: list[dict[str, object]], fields: tuple[str, ...]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _write_csv(path: Path, rows: list[dict[str, object]], fields: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_csv_bytes(rows, fields))


def _fixture_manifest(probe: BooleanProbe) -> bytes:
    rows = [{
        "control_id": item.fixture_id,
        "file_name": item.file_name,
        "source_bytes": len(item.source_bytes),
        "source_sha256": item.source_sha256,
        "generator": "experiments/run_boolean_robustness.py",
        "binding_distribution_version": probe.binding_distribution_version,
        "step_processor": item.step_processor,
        "writer_status": item.writer_status,
        "reader_status": item.reader_status,
        "transferred_roots": item.transferred_roots,
    } for item in probe.fixtures]
    return _csv_bytes(rows, tuple(rows[0]))


def handle_fixtures(path: Path, probe: BooleanProbe, *, refresh: bool) -> None:
    """Write or verify normalized Boolean-result STEP fixtures."""
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


def write_contract(path: Path, probe: BooleanProbe) -> None:
    """Write the Boolean inputs, exact truth, options, and claim boundaries."""
    payload = {
        "contract_version": CONTRACT_VERSION,
        "study_version": "v0.46.0",
        "title": "Boolean Operations and Robustness",
        "controls": [{
            "control_id": item.control_id,
            "operation": item.operation,
            "relationship": item.relationship,
            "first_cuboid": item.first_cuboid,
            "second_cuboid": item.second_cuboid,
            "requested_fuzzy_value": item.requested_fuzzy_value,
            "expected_solid_count": item.expected_solid_count,
            "expected_exact_volume": item.expected_exact_volume,
            "expected_exact_surface_area": item.expected_exact_surface_area,
            "expects_exact_set_measure": item.expects_exact_set_measure,
        } for item in probe.controls],
        "decision_csv": {"file": DECISION_NAME, "ordered_fields": list(DECISION_FIELDS)},
        "observation_csv": {"file": OBSERVATION_NAME, "ordered_fields": list(OBSERVATION_FIELDS)},
        "summary_csv": {"file": SUMMARY_NAME, "ordered_fields": list(SUMMARY_FIELDS)},
        "tolerance_csv": {"file": TOLERANCE_NAME, "ordered_fields": list(TOLERANCE_FIELDS)},
        "fixture_sha256": {item.file_name: item.source_sha256 for item in probe.fixtures},
        "claim_boundaries": [
            "independent truth uses only the declared axis-aligned cuboid sets",
            "commutativity checks topology and measures, not persistent identity",
            "the fuzzy near-gap result intentionally is not claimed to match exact-set measures",
            "one fuzzy value does not define a universal robustness tolerance",
            "STEP output does not recover Boolean operands, order, options, or operation history",
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_figure(path: Path, probe: BooleanProbe) -> None:
    """Plot exact-set residuals and solid-count changes."""
    constructed = [item for item in probe.observations if item.stage == "constructed"]
    labels = [item.control_id.replace("_", " ") for item in constructed]
    figure, axes = plt.subplots(1, 2, figsize=(13.5, 4.8), constrained_layout=True)
    axes[0].bar(
        range(len(constructed)),
        [max(item.volume_exact_set_difference, 1.0e-17) for item in constructed],
        color="#7c3aed",
    )
    axes[0].set_yscale("log")
    axes[0].set_xticks(range(len(labels)), labels, rotation=28, ha="right")
    axes[0].set_ylabel("Difference from exact cuboid-set volume")
    axes[0].set_title("Exact and fuzzy set-measure response")
    axes[1].bar(
        range(len(constructed)),
        [item.metrics.solid_count for item in constructed],
        color="#0f766e",
    )
    axes[1].set_xticks(range(len(labels)), labels, rotation=28, ha="right")
    axes[1].set_ylabel("Result solid count")
    axes[1].set_title("Separation, contact, and fuzzy bridging")
    figure.suptitle("v0.46.0 Boolean Operations and Robustness")
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160)
    plt.close(figure)


def run(output_dir: Path, fixture_dir: Path, *, refresh: bool) -> None:
    """Run and serialize the complete v0.46.0 experiment."""
    probe = probe_boolean_robustness()
    handle_fixtures(fixture_dir, probe, refresh=refresh)
    _write_csv(output_dir / DECISION_NAME, decision_rows(probe), DECISION_FIELDS)
    _write_csv(output_dir / OBSERVATION_NAME, observation_rows(probe), OBSERVATION_FIELDS)
    _write_csv(output_dir / SUMMARY_NAME, summary_rows(probe), SUMMARY_FIELDS)
    _write_csv(output_dir / TOLERANCE_NAME, tolerance_rows(probe), TOLERANCE_FIELDS)
    write_contract(output_dir / CONTRACT_NAME, probe)
    write_figure(output_dir / FIGURE_NAME, probe)
    write_shape_previews(
        output_dir / SHAPES_NAME,
        tuple((name.replace("_", " ").title(), shape) for name, shape in probe.preview_shapes),
        title="v0.46.0 Imported Boolean Results",
        columns=4,
    )
    print(f"Wrote Boolean-operation artifacts to {output_dir}")


def main() -> None:
    """Parse command-line arguments and run the experiment."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument("--fixture-dir", type=Path, default=Path("fixtures/boolean-robustness"))
    parser.add_argument("--refresh-fixtures", action="store_true")
    arguments = parser.parse_args()
    run(arguments.output_dir, arguments.fixture_dir, refresh=arguments.refresh_fixtures)


if __name__ == "__main__":
    main()
