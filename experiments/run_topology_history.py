"""Generate v0.47.0 fillet, chamfer, and topology-history evidence."""

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
from research_notes.topology_history import (  # noqa: E402
    CONTRACT_VERSION,
    TopologyHistoryProbe,
    probe_topology_history,
)


DECISION_NAME = "feature_operation_decisions.csv"
OBSERVATION_NAME = "feature_operation_observations.csv"
HISTORY_NAME = "topology_history.csv"
FACE_MATCH_NAME = "feature_face_round_trip_matches.csv"
SUMMARY_NAME = "feature_operation_summary.csv"
CONTRACT_NAME = "feature_operation_contract.json"
FIGURE_NAME = "topology_history.png"
SHAPES_NAME = "feature_operation_shapes.png"
MANIFEST_NAME = "manifest.csv"

DECISION_FIELDS = (
    "contract_version", "control_id", "operation", "parameter_name",
    "parameter_value", "selected_edge_endpoints", "expected_decision",
    "decision", "reason", "kernel_invoked", "is_done", "contour_count",
)
OBSERVATION_FIELDS = (
    "contract_version", "stage", "control_id", "source_file", "source_sha256",
    "vertex_count", "edge_count", "face_count", "shell_count", "solid_count",
    "absolute_volume", "expected_volume", "volume_absolute_error", "surface_area",
    "expected_surface_area", "surface_area_absolute_error", "surface_counts",
    "maximum_vertex_tolerance", "maximum_edge_tolerance",
    "maximum_face_tolerance", "analyzer_valid",
)
HISTORY_FIELDS = (
    "contract_version", "control_id", "source_kind", "source_index",
    "query_scope", "direct_result_indices", "generated_result_indices",
    "modified_result_indices", "is_deleted", "modified_is_split",
    "modified_target_max_source_count",
)
FACE_MATCH_FIELDS = (
    "contract_version", "control_id", "constructed_face_index",
    "imported_face_index", "surface_type", "area_absolute_difference",
    "centroid_distance", "index_values_equal", "direct_topological_identity",
    "operation_history_available_after_import",
)
SUMMARY_FIELDS = (
    "control_id", "topology_matches", "surface_counts_match",
    "volume_absolute_difference", "surface_area_absolute_difference",
    "surface_centroid_distance", "constructed_truth_matches",
    "step_imported_truth_matches", "history_source_rows",
    "sources_with_direct_result_presence", "sources_with_generated_results",
    "sources_with_modified_results", "supported_deleted_sources",
    "modified_split_sources", "modified_merge_targets",
    "round_trip_face_matches", "equal_face_index_values",
    "direct_face_identities_across_step", "imported_history_available",
    "round_trip_passes",
)


def _float(value: float | None) -> str:
    return "" if value is None else format(value, ".17g")


def _joined(values: tuple[object, ...]) -> str:
    return "|".join(str(value) for value in values)


def decision_rows(probe: TopologyHistoryProbe) -> list[dict[str, object]]:
    """Flatten attempted local operations and completion decisions."""
    controls = {item.control_id: item for item in probe.controls}
    rows: list[dict[str, object]] = []
    for item in probe.decisions:
        control = controls[item.control_id]
        rows.append({
            "contract_version": CONTRACT_VERSION,
            "control_id": item.control_id,
            "operation": control.operation,
            "parameter_name": control.parameter_name,
            "parameter_value": _float(control.parameter_value),
            "selected_edge_endpoints": ";".join(_joined(point) for point in control.selected_edge_endpoints),
            "expected_decision": control.expected_decision,
            "decision": item.decision,
            "reason": item.reason,
            "kernel_invoked": int(item.kernel_invoked),
            "is_done": int(item.is_done),
            "contour_count": item.contour_count,
        })
    return rows


def observation_rows(probe: TopologyHistoryProbe) -> list[dict[str, object]]:
    """Flatten successful constructed and imported result measurements."""
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
            "surface_counts": _joined(metrics.surface_counts),
            "maximum_vertex_tolerance": _float(metrics.maximum_vertex_tolerance),
            "maximum_edge_tolerance": _float(metrics.maximum_edge_tolerance),
            "maximum_face_tolerance": _float(metrics.maximum_face_tolerance),
            "analyzer_valid": int(metrics.analyzer_valid),
        })
    return rows


def history_rows(probe: TopologyHistoryProbe) -> list[dict[str, object]]:
    """Flatten documented operation-local history queries."""
    return [{
        "contract_version": CONTRACT_VERSION,
        "control_id": item.control_id,
        "source_kind": item.source_kind,
        "source_index": item.source_index,
        "query_scope": item.query_scope,
        "direct_result_indices": _joined(item.direct_result_indices),
        "generated_result_indices": _joined(item.generated_result_indices),
        "modified_result_indices": _joined(item.modified_result_indices),
        "is_deleted": "" if item.is_deleted is None else int(item.is_deleted),
        "modified_is_split": "" if item.modified_is_split is None else int(item.modified_is_split),
        "modified_target_max_source_count": "" if item.modified_target_max_source_count is None else item.modified_target_max_source_count,
    } for item in probe.history]


def face_match_rows(probe: TopologyHistoryProbe) -> list[dict[str, object]]:
    """Flatten geometry-based face matches across STEP import."""
    return [{
        "contract_version": CONTRACT_VERSION,
        "control_id": item.control_id,
        "constructed_face_index": item.constructed_face_index,
        "imported_face_index": item.imported_face_index,
        "surface_type": item.surface_type,
        "area_absolute_difference": _float(item.area_absolute_difference),
        "centroid_distance": _float(item.centroid_distance),
        "index_values_equal": int(item.index_values_equal),
        "direct_topological_identity": int(item.direct_topological_identity),
        "operation_history_available_after_import": int(item.operation_history_available_after_import),
    } for item in probe.face_matches]


def summary_rows(probe: TopologyHistoryProbe) -> list[dict[str, object]]:
    """Summarize truth, history cardinality, and STEP identity boundaries."""
    by_key = {(item.control_id, item.stage): item for item in probe.observations}
    rows: list[dict[str, object]] = []
    accepted = [item for item in probe.controls if item.expected_decision == "accept"]
    for control in accepted:
        first = by_key[(control.control_id, "constructed")]
        second = by_key[(control.control_id, "step_imported")]
        history = [item for item in probe.history if item.control_id == control.control_id]
        matches = [item for item in probe.face_matches if item.control_id == control.control_id]
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
        first_truth = first.volume_absolute_error <= 1.0e-8 and first.surface_area_absolute_error <= 1.0e-8
        second_truth = second.volume_absolute_error <= 1.0e-8 and second.surface_area_absolute_error <= 1.0e-8
        split_sources = sum(item.modified_is_split is True for item in history)
        modified_targets = {
            target for item in history for target in item.modified_result_indices
        }
        merge_targets = sum(
            sum(target in item.modified_result_indices for item in history) > 1
            for target in modified_targets
        )
        passes = (
            topology_match and surfaces_match and first_truth and second_truth
            and volume_difference <= 1.0e-8 and area_difference <= 1.0e-8
            and centroid_distance <= 1.0e-8 and first.metrics.analyzer_valid
            and second.metrics.analyzer_valid and len(matches) == first.metrics.face_count
        )
        rows.append({
            "control_id": control.control_id,
            "topology_matches": int(topology_match),
            "surface_counts_match": int(surfaces_match),
            "volume_absolute_difference": _float(volume_difference),
            "surface_area_absolute_difference": _float(area_difference),
            "surface_centroid_distance": _float(centroid_distance),
            "constructed_truth_matches": int(first_truth),
            "step_imported_truth_matches": int(second_truth),
            "history_source_rows": len(history),
            "sources_with_direct_result_presence": sum(bool(item.direct_result_indices) for item in history),
            "sources_with_generated_results": sum(bool(item.generated_result_indices) for item in history),
            "sources_with_modified_results": sum(bool(item.modified_result_indices) for item in history),
            "supported_deleted_sources": sum(item.is_deleted is True for item in history),
            "modified_split_sources": split_sources,
            "modified_merge_targets": merge_targets,
            "round_trip_face_matches": len(matches),
            "equal_face_index_values": sum(item.index_values_equal for item in matches),
            "direct_face_identities_across_step": sum(item.direct_topological_identity for item in matches),
            "imported_history_available": int(any(item.operation_history_available_after_import for item in matches)),
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


def _fixture_manifest(probe: TopologyHistoryProbe) -> bytes:
    rows = [{
        "control_id": item.fixture_id,
        "file_name": item.file_name,
        "source_bytes": len(item.source_bytes),
        "source_sha256": item.source_sha256,
        "generator": "experiments/run_topology_history.py",
        "binding_distribution_version": probe.binding_distribution_version,
        "step_processor": item.step_processor,
        "writer_status": item.writer_status,
        "reader_status": item.reader_status,
        "transferred_roots": item.transferred_roots,
    } for item in probe.fixtures]
    return _csv_bytes(rows, tuple(rows[0]))


def handle_fixtures(path: Path, probe: TopologyHistoryProbe, *, refresh: bool) -> None:
    """Write or verify normalized successful-feature STEP fixtures."""
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


def write_contract(path: Path, probe: TopologyHistoryProbe) -> None:
    """Write feature truth, history-query scope, and identity boundaries."""
    payload = {
        "contract_version": CONTRACT_VERSION,
        "study_version": "v0.47.0",
        "title": "Fillets, Chamfers, and Topology History",
        "controls": [{
            "control_id": item.control_id,
            "operation": item.operation,
            "parameter_name": item.parameter_name,
            "parameter_value": item.parameter_value,
            "expected_decision": item.expected_decision,
            "selected_edge_endpoints": item.selected_edge_endpoints,
            "expected_volume": item.expected_volume,
            "expected_surface_area": item.expected_surface_area,
        } for item in probe.controls],
        "history_query_scope": {
            "vertex": ["Generated"],
            "edge": ["Generated"],
            "face": ["Modified", "IsDeleted"],
        },
        "decision_csv": {"file": DECISION_NAME, "ordered_fields": list(DECISION_FIELDS)},
        "observation_csv": {"file": OBSERVATION_NAME, "ordered_fields": list(OBSERVATION_FIELDS)},
        "history_csv": {"file": HISTORY_NAME, "ordered_fields": list(HISTORY_FIELDS)},
        "face_match_csv": {"file": FACE_MATCH_NAME, "ordered_fields": list(FACE_MATCH_FIELDS)},
        "summary_csv": {"file": SUMMARY_NAME, "ordered_fields": list(SUMMARY_FIELDS)},
        "fixture_sha256": {item.file_name: item.source_sha256 for item in probe.fixtures},
        "claim_boundaries": [
            "history queries follow the source-kind scope documented by the selected local-operation APIs",
            "zero observed splits or merges is not a claim that those events cannot occur",
            "equal analysis-local face index values across this STEP route are coincidental ordering evidence",
            "direct topological identity and operation-local history do not cross STEP exchange",
            "STEP output does not recover the selected edge, radius, distance, or feature order",
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_figure(path: Path, probe: TopologyHistoryProbe) -> None:
    """Plot history cardinalities and STEP identity boundaries."""
    summaries = summary_rows(probe)
    labels = [item["control_id"].replace("_", " ") for item in summaries]
    figure, axes = plt.subplots(1, 2, figsize=(12.5, 4.8), constrained_layout=True)
    x_values = list(range(len(summaries)))
    axes[0].bar(
        [x - 0.2 for x in x_values],
        [int(item["sources_with_generated_results"]) for item in summaries],
        0.4,
        label="Generated",
    )
    axes[0].bar(
        [x + 0.2 for x in x_values],
        [int(item["sources_with_modified_results"]) for item in summaries],
        0.4,
        label="Modified",
    )
    axes[0].set_xticks(x_values, labels, rotation=20)
    axes[0].set_ylabel("Input subshapes with history results")
    axes[0].set_title("Operation-local history")
    axes[0].legend()
    axes[1].bar(
        [x - 0.2 for x in x_values],
        [int(item["equal_face_index_values"]) for item in summaries],
        0.4,
        label="Equal local index values",
    )
    axes[1].bar(
        [x + 0.2 for x in x_values],
        [int(item["direct_face_identities_across_step"]) for item in summaries],
        0.4,
        label="Direct identity",
    )
    axes[1].set_xticks(x_values, labels, rotation=20)
    axes[1].set_ylabel("Geometry-matched faces")
    axes[1].set_title("STEP index values versus identity")
    axes[1].legend()
    figure.suptitle("v0.47.0 Fillets, Chamfers, and Topology History")
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160)
    plt.close(figure)


def run(output_dir: Path, fixture_dir: Path, *, refresh: bool) -> None:
    """Run and serialize the complete v0.47.0 experiment."""
    probe = probe_topology_history()
    handle_fixtures(fixture_dir, probe, refresh=refresh)
    _write_csv(output_dir / DECISION_NAME, decision_rows(probe), DECISION_FIELDS)
    _write_csv(output_dir / OBSERVATION_NAME, observation_rows(probe), OBSERVATION_FIELDS)
    _write_csv(output_dir / HISTORY_NAME, history_rows(probe), HISTORY_FIELDS)
    _write_csv(output_dir / FACE_MATCH_NAME, face_match_rows(probe), FACE_MATCH_FIELDS)
    _write_csv(output_dir / SUMMARY_NAME, summary_rows(probe), SUMMARY_FIELDS)
    write_contract(output_dir / CONTRACT_NAME, probe)
    write_figure(output_dir / FIGURE_NAME, probe)
    write_shape_previews(
        output_dir / SHAPES_NAME,
        tuple((name.replace("_", " ").title(), shape) for name, shape in probe.preview_shapes),
        title="v0.47.0 Imported Fillet and Chamfer Results",
        columns=2,
    )
    print(f"Wrote feature-operation and topology-history artifacts to {output_dir}")


def main() -> None:
    """Parse command-line arguments and run the experiment."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument("--fixture-dir", type=Path, default=Path("fixtures/topology-history"))
    parser.add_argument("--refresh-fixtures", action="store_true")
    arguments = parser.parse_args()
    run(arguments.output_dir, arguments.fixture_dir, refresh=arguments.refresh_fixtures)


if __name__ == "__main__":
    main()
