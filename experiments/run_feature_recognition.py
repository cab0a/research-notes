"""Evaluate rule-based B-Rep feature candidates on synthetic STEP controls."""

from __future__ import annotations

import argparse
import csv
import importlib.metadata
import io
import json
from dataclasses import asdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402
from matplotlib.patches import Arc, Circle, Polygon, Rectangle  # noqa: E402

from research_notes.feature_recognition import (  # noqa: E402
    ANGLE_TRUTH_TOLERANCE_DEGREES,
    BOUNDARY_EQUIVALENCE_TOLERANCE,
    LENGTH_TRUTH_TOLERANCE,
    FeatureRecognitionProbe,
    probe_feature_recognition,
    recovered_dimension_series,
    round_trip_dimension_differences,
    truth_dimension_errors,
)


FACE_NAME = "feature_face_attributes.csv"
ADJACENCY_NAME = "feature_adjacency_edges.csv"
CANDIDATE_NAME = "feature_candidates.csv"
OBSERVATION_NAME = "feature_recognition_observations.csv"
EQUIVALENCE_NAME = "feature_equivalent_boundary_observations.csv"
SUMMARY_NAME = "feature_recognition_summary.csv"
CONTRACT_NAME = "feature_recognition_contract.json"
FIGURE_NAME = "feature_recognition.png"
SHAPES_NAME = "feature_recognition_shapes.png"
MANIFEST_NAME = "manifest.csv"


def _float(value: float | None) -> str:
    return "" if value is None else format(value, ".17g")


def _values(values: tuple[object, ...]) -> str:
    return "|".join(str(value) for value in values)


def _csv_bytes(rows: list[dict[str, object]], fields: tuple[str, ...]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _write_csv(
    path: Path, rows: list[dict[str, object]], fields: tuple[str, ...]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_csv_bytes(rows, fields))


def _face_rows(probe: FeatureRecognitionProbe) -> list[dict[str, object]]:
    return [
        {
            "stage": item.stage,
            "control_id": item.control_id,
            "face_index": item.face_index,
            "surface_type": item.surface_type,
            "area": _float(item.area),
            "centroid_x": _float(item.centroid[0]),
            "centroid_y": _float(item.centroid[1]),
            "centroid_z": _float(item.centroid[2]),
            "normal_x": _float(item.normal[0]),
            "normal_y": _float(item.normal[1]),
            "normal_z": _float(item.normal[2]),
            "u_span": _float(item.u_span),
            "v_span": _float(item.v_span),
            "axis_origin": _values(item.axis_origin or ()),
            "axis_direction": _values(item.axis_direction or ()),
            "radius": _float(item.radius),
            "radial_polarity": _float(item.radial_polarity),
            "maximum_absolute_curvature": _float(item.maximum_absolute_curvature),
            "wire_count": item.wire_count,
            "inner_wire_count": item.inner_wire_count,
            "edge_count": item.edge_count,
            "maximum_edge_length": _float(item.maximum_edge_length),
            "adjacent_face_indices": _values(item.adjacent_face_indices),
        }
        for item in probe.faces
    ]


def _adjacency_rows(probe: FeatureRecognitionProbe) -> list[dict[str, object]]:
    return [
        {
            "stage": item.stage,
            "control_id": item.control_id,
            "edge_index": item.edge_index,
            "first_face_index": item.first_face_index,
            "second_face_index": item.second_face_index,
            "curve_type": item.curve_type,
            "length": _float(item.length),
            "normal_dot": _float(item.normal_dot),
            "representative_normals_parallel": int(
                item.representative_normals_parallel
            ),
        }
        for item in probe.adjacencies
    ]


def _candidate_rows(probe: FeatureRecognitionProbe) -> list[dict[str, object]]:
    return [
        {
            "stage": item.stage,
            "control_id": item.control_id,
            "candidate_index": item.candidate_index,
            "candidate_type": item.candidate_type,
            "subtype": item.subtype,
            "face_indices": _values(item.face_indices),
            "primary_size": _float(item.primary_size),
            "secondary_size": _float(item.secondary_size),
            "depth": _float(item.depth),
            "angle_degrees": _float(item.angle_degrees),
            "expected_primary_size": _float(item.expected_primary_size),
            "expected_secondary_size": _float(item.expected_secondary_size),
            "expected_depth": _float(item.expected_depth),
            "expected_angle_degrees": _float(item.expected_angle_degrees),
            "primary_size_absolute_error": _float(item.primary_size_absolute_error),
            "secondary_size_absolute_error": _float(item.secondary_size_absolute_error),
            "depth_absolute_error": _float(item.depth_absolute_error),
            "angle_absolute_error_degrees": _float(item.angle_absolute_error_degrees),
            "geometric_candidate": int(item.geometric_candidate),
            "construction_history_label": item.construction_history_label,
            "design_intent_proven": int(item.design_intent_proven),
            "classification_matches_truth": int(item.classification_matches_truth),
            "dimension_matches_truth": int(item.dimension_matches_truth),
            "truth_correct": int(item.truth_correct),
        }
        for item in probe.candidates
    ]


def _observation_rows(probe: FeatureRecognitionProbe) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for control in probe.controls:
        for stage in ("constructed", "step_imported"):
            found = [
                item
                for item in probe.candidates
                if item.control_id == control.control_id and item.stage == stage
            ]
            candidate = found[0] if len(found) == 1 else None
            classification_matches = sorted(
                (item.candidate_type, item.subtype) for item in found
            ) == sorted(
                zip(
                    control.expected_candidate_types,
                    control.expected_subtypes,
                    strict=True,
                )
            )
            dimension_matches = (
                candidate.dimension_matches_truth
                if candidate is not None
                else not found
                and all(
                    value is None
                    for value in (
                        control.expected_primary_size,
                        control.expected_secondary_size,
                        control.expected_depth,
                        control.expected_angle_degrees,
                    )
                )
            )
            rows.append(
                {
                    "stage": stage,
                    "control_id": control.control_id,
                    "condition": control.condition,
                    "expected_candidate_types": _values(
                        control.expected_candidate_types
                    ),
                    "observed_candidate_types": _values(
                        tuple(item.candidate_type for item in found)
                    ),
                    "expected_subtypes": _values(control.expected_subtypes),
                    "observed_subtypes": _values(tuple(item.subtype for item in found)),
                    "candidate_count": len(found),
                    "expected_candidate_count": len(control.expected_candidate_types),
                    "expected_primary_size": _float(control.expected_primary_size),
                    "observed_primary_size": _float(
                        None if candidate is None else candidate.primary_size
                    ),
                    "primary_size_absolute_error": _float(
                        None
                        if candidate is None
                        else candidate.primary_size_absolute_error
                    ),
                    "expected_secondary_size": _float(control.expected_secondary_size),
                    "observed_secondary_size": _float(
                        None if candidate is None else candidate.secondary_size
                    ),
                    "secondary_size_absolute_error": _float(
                        None
                        if candidate is None
                        else candidate.secondary_size_absolute_error
                    ),
                    "expected_depth": _float(control.expected_depth),
                    "observed_depth": _float(
                        None if candidate is None else candidate.depth
                    ),
                    "depth_absolute_error": _float(
                        None if candidate is None else candidate.depth_absolute_error
                    ),
                    "expected_angle_degrees": _float(control.expected_angle_degrees),
                    "observed_angle_degrees": _float(
                        None if candidate is None else candidate.angle_degrees
                    ),
                    "angle_absolute_error_degrees": _float(
                        None
                        if candidate is None
                        else candidate.angle_absolute_error_degrees
                    ),
                    "classification_matches_truth": int(classification_matches),
                    "dimension_matches_truth": int(dimension_matches),
                    "overall_matches_truth": int(
                        classification_matches and dimension_matches
                    ),
                    "construction_history_label": control.history_label,
                    "design_intent_claim_eligible": 0,
                }
            )
    return rows


def _equivalence_rows(probe: FeatureRecognitionProbe) -> list[dict[str, object]]:
    return [
        {
            "stage": item.stage,
            "first_control_id": item.first_control_id,
            "second_control_id": item.second_control_id,
            "first_vertex_count": item.first_vertex_count,
            "first_edge_count": item.first_edge_count,
            "first_face_count": item.first_face_count,
            "first_shell_count": item.first_shell_count,
            "first_solid_count": item.first_solid_count,
            "second_vertex_count": item.second_vertex_count,
            "second_edge_count": item.second_edge_count,
            "second_face_count": item.second_face_count,
            "second_shell_count": item.second_shell_count,
            "second_solid_count": item.second_solid_count,
            "topology_matches": int(item.topology_matches),
            "first_volume": _float(item.first_volume),
            "second_volume": _float(item.second_volume),
            "volume_absolute_difference": _float(item.volume_absolute_difference),
            "first_minus_second_volume": _float(item.first_minus_second_volume),
            "second_minus_first_volume": _float(item.second_minus_first_volume),
            "boundary_equivalent": int(item.boundary_equivalent),
        }
        for item in probe.equivalent_boundaries
    ]


def _summary_rows(probe: FeatureRecognitionProbe) -> list[dict[str, object]]:
    constructed = [item for item in probe.candidates if item.stage == "constructed"]
    imported = [item for item in probe.candidates if item.stage == "step_imported"]
    maximum_length_difference, maximum_angle_difference = (
        round_trip_dimension_differences(probe)
    )
    maximum_truth_length_error, maximum_truth_angle_error = truth_dimension_errors(
        probe
    )
    values = (
        ("corpus", "control_count", len(probe.controls)),
        ("corpus", "fixture_count", len(probe.fixtures)),
        ("constructed", "candidate_count", len(constructed)),
        ("step_imported", "candidate_count", len(imported)),
        (
            "all",
            "classification_matches_truth_candidate_count",
            sum(item.classification_matches_truth for item in probe.candidates),
        ),
        (
            "all",
            "dimension_matches_truth_candidate_count",
            sum(item.dimension_matches_truth for item in probe.candidates),
        ),
        (
            "all",
            "truth_correct_candidate_count",
            sum(item.truth_correct for item in probe.candidates),
        ),
        ("all", "candidate_count", len(probe.candidates)),
        (
            "all",
            "design_intent_proven_count",
            sum(item.design_intent_proven for item in probe.candidates),
        ),
        (
            "round_trip",
            "maximum_length_absolute_difference",
            maximum_length_difference,
        ),
        (
            "round_trip",
            "maximum_angle_absolute_difference_degrees",
            maximum_angle_difference,
        ),
        (
            "controlled_truth",
            "maximum_length_absolute_error",
            maximum_truth_length_error,
        ),
        (
            "controlled_truth",
            "maximum_angle_absolute_error_degrees",
            maximum_truth_angle_error,
        ),
        (
            "negative_controls",
            "false_positive_count",
            sum(
                item.control_id in {"plain_block", "cylindrical_boss"}
                for item in probe.candidates
            ),
        ),
        (
            "intent_boundary",
            "equivalent_bevel_candidate_count",
            sum(item.control_id == "equivalent_bevel" for item in probe.candidates),
        ),
        (
            "intent_boundary",
            "equivalent_boundary_stage_count",
            len(probe.equivalent_boundaries),
        ),
        (
            "intent_boundary",
            "equivalent_boundary_match_count",
            sum(item.boundary_equivalent for item in probe.equivalent_boundaries),
        ),
        (
            "intent_boundary",
            "maximum_bidirectional_difference_volume",
            max(
                (
                    max(
                        item.first_minus_second_volume,
                        item.second_minus_first_volume,
                    )
                    for item in probe.equivalent_boundaries
                ),
                default=0.0,
            ),
        ),
    )
    return [
        {
            "scope": scope,
            "metric": metric,
            "value": _float(value) if isinstance(value, float) else value,
        }
        for scope, metric, value in values
    ]


def _fixture_manifest(probe: FeatureRecognitionProbe) -> bytes:
    version = importlib.metadata.version("cadquery-ocp")
    rows = [
        {
            "control_id": item.fixture_id,
            "file_name": item.file_name,
            "source_bytes": len(item.source_bytes),
            "source_sha256": item.source_sha256,
            "generator": "experiments/run_feature_recognition.py",
            "binding_distribution_version": version,
            "step_processor": item.step_processor,
            "writer_status": item.writer_status,
            "reader_status": item.reader_status,
            "transferred_roots": item.transferred_roots,
        }
        for item in probe.fixtures
    ]
    return _csv_bytes(rows, tuple(rows[0]))


def handle_fixtures(
    path: Path, probe: FeatureRecognitionProbe, *, refresh: bool
) -> None:
    """Write or verify normalized feature STEP fixtures and their manifest."""
    expected = {item.file_name: item.source_bytes for item in probe.fixtures}
    expected[MANIFEST_NAME] = _fixture_manifest(probe)
    path.mkdir(parents=True, exist_ok=True)
    if refresh:
        for name, content in expected.items():
            (path / name).write_bytes(content)
        return
    for name, content in expected.items():
        target = path / name
        if not target.exists() or target.read_bytes() != content:
            raise RuntimeError(
                f"fixture differs; rerun with --refresh-fixtures: {target}"
            )


def write_contract(path: Path, probe: FeatureRecognitionProbe) -> None:
    """Write the controlled recognition and claim-boundary contract."""
    maximum_length_difference, maximum_angle_difference = (
        round_trip_dimension_differences(probe)
    )
    maximum_truth_length_error, maximum_truth_angle_error = truth_dimension_errors(
        probe
    )
    payload = {
        "contract_version": "1.0",
        "study_version": "v0.40.0",
        "title": "Rule-Based B-Rep Feature Recognition",
        "recognized_geometric_candidates": [
            "hole",
            "step",
            "slot",
            "chamfer_like",
            "fillet_like",
        ],
        "controlled_candidate_instances_per_stage": 7,
        "controlled_truth": {
            control.control_id: {
                "condition": control.condition,
                "expected_candidate_types": control.expected_candidate_types,
                "expected_subtypes": control.expected_subtypes,
                "construction_history_label": control.history_label,
                "expected_primary_size": control.expected_primary_size,
                "expected_secondary_size": control.expected_secondary_size,
                "expected_depth": control.expected_depth,
                "expected_angle_degrees": control.expected_angle_degrees,
            }
            for control in probe.controls
        },
        "negative_controls": ["plain_block", "cylindrical_boss"],
        "design_intent_is_not_inferred": True,
        "equivalent_boundary_control": "equivalent_bevel",
        "round_trip_regression": {
            "maximum_angle_absolute_difference_degrees": maximum_angle_difference,
            "maximum_length_absolute_difference": maximum_length_difference,
        },
        "controlled_truth_regression": {
            "angle_absolute_tolerance_degrees": ANGLE_TRUTH_TOLERANCE_DEGREES,
            "length_absolute_tolerance": LENGTH_TRUTH_TOLERANCE,
            "maximum_angle_absolute_error_degrees": maximum_truth_angle_error,
            "maximum_length_absolute_error": maximum_truth_length_error,
        },
        "equivalent_boundary_contract": {
            "controls": ["chamfer_operation", "equivalent_bevel"],
            "expected_equivalent": True,
            "volume_absolute_tolerance": BOUNDARY_EQUIVALENCE_TOLERANCE,
            "observations": [asdict(item) for item in probe.equivalent_boundaries],
        },
        "regression_gates_are_not_manufacturing_tolerances": True,
        "fixture_sha256": {
            item.file_name: item.source_sha256 for item in probe.fixtures
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def write_figure(path: Path, probe: FeatureRecognitionProbe) -> None:
    """Plot recognized instances and STEP round-trip dimensional stability."""
    figure, axes = plt.subplots(1, 2, figsize=(12.0, 4.8), constrained_layout=True)
    types = ["hole", "step", "slot", "chamfer_like", "fillet_like"]
    constructed = [
        sum(
            item.stage == "constructed" and item.candidate_type == name
            for item in probe.candidates
        )
        for name in types
    ]
    imported = [
        sum(
            item.stage == "step_imported" and item.candidate_type == name
            for item in probe.candidates
        )
        for name in types
    ]
    positions = list(range(len(types)))
    axes[0].bar(
        [value - 0.18 for value in positions],
        constructed,
        width=0.36,
        label="Constructed",
        color="#2563eb",
    )
    axes[0].bar(
        [value + 0.18 for value in positions],
        imported,
        width=0.36,
        label="STEP imported",
        color="#14b8a6",
    )
    axes[0].set_xticks(
        positions, ["Hole", "Step", "Slot", "Chamfer-like", "Fillet-like"], rotation=15
    )
    axes[0].set_ylabel("Candidate instances")
    axes[0].set_title("Geometric candidate inventory")
    axes[0].legend()
    recovered = recovered_dimension_series(probe)
    size_labels = [label for label, _ in recovered]
    size_values = [value for _, value in recovered]
    bars = axes[1].barh(
        size_labels,
        size_values,
        color=[
            "#60a5fa",
            "#60a5fa",
            "#a78bfa",
            "#f59e0b",
            "#f59e0b",
            "#f472b6",
            "#34d399",
        ],
    )
    axes[1].bar_label(bars, fmt="%.1f")
    axes[1].set_xlabel("Controlled model units")
    axes[1].set_title("Recovered synthetic dimensions")
    maximum_length_difference, maximum_angle_difference = (
        round_trip_dimension_differences(probe)
    )
    maximum_truth_length_error, maximum_truth_angle_error = truth_dimension_errors(
        probe
    )
    axes[1].text(
        0.5,
        -0.16,
        "Maximum STEP round-trip differences: "
        f"length {maximum_length_difference:.2e} model units; "
        f"angle {maximum_angle_difference:.2e}°\n"
        "Maximum controlled-truth errors: "
        f"length {maximum_truth_length_error:.2e} model units; "
        f"angle {maximum_truth_angle_error:.2e}°",
        transform=axes[1].transAxes,
        ha="center",
        va="top",
        fontsize=8,
    )
    figure.suptitle("v0.40.0 Rule-Based B-Rep Feature Evidence")
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160)
    plt.close(figure)


def write_shapes_figure(path: Path) -> None:
    """Render schematic previews of the nine generated feature controls."""
    figure, axes = plt.subplots(3, 3, figsize=(11.0, 9.0), constrained_layout=True)
    panels = axes.ravel()
    for axis in panels:
        axis.add_patch(
            Rectangle((0, 0), 12, 7, facecolor="#dbeafe", edgecolor="#1e3a8a")
        )
        axis.set_xlim(-1, 13)
        axis.set_ylim(-1, 8)
        axis.set_aspect("equal")
        axis.axis("off")
    panels[0].set_title("Plain block")
    panels[1].add_patch(
        Circle((4, 3.5), 1.2, facecolor="white", edgecolor="#dc2626", linewidth=2)
    )
    panels[1].set_title("Through hole")
    panels[2].add_patch(
        Circle((4, 3.5), 1.0, facecolor="#fef3c7", edgecolor="#dc2626", linewidth=2)
    )
    panels[2].text(4, 3.5, "blind", ha="center", va="center", fontsize=8)
    panels[2].set_title("Blind hole")
    panels[3].clear()
    panels[3].add_patch(
        Polygon(
            [(0, 0), (12, 0), (12, 3), (5, 3), (5, 5), (0, 5)],
            closed=True,
            facecolor="#c4b5fd",
            edgecolor="#5b21b6",
        )
    )
    panels[3].set_xlim(-1, 13)
    panels[3].set_ylim(-1, 7)
    panels[3].set_aspect("equal")
    panels[3].axis("off")
    panels[3].set_title("Step")
    panels[4].add_patch(
        Rectangle((5, 2.5), 4, 2, facecolor="white", edgecolor="#d97706")
    )
    panels[4].add_patch(Circle((5, 3.5), 1, facecolor="white", edgecolor="#d97706"))
    panels[4].add_patch(Circle((9, 3.5), 1, facecolor="white", edgecolor="#d97706"))
    panels[4].set_title("Through slot")
    chamfer_outline = [(0, 0), (12, 0), (12, 6), (11, 7), (0, 7)]
    panels[5].clear()
    panels[5].add_patch(
        Polygon(chamfer_outline, closed=True, facecolor="#fbcfe8", edgecolor="#9d174d")
    )
    panels[5].set_xlim(-1, 13)
    panels[5].set_ylim(-1, 8)
    panels[5].set_aspect("equal")
    panels[5].axis("off")
    panels[5].set_title("Chamfer operation")
    panels[6].clear()
    panels[6].add_patch(
        Polygon(chamfer_outline, closed=True, facecolor="#fde68a", edgecolor="#92400e")
    )
    panels[6].set_xlim(-1, 13)
    panels[6].set_ylim(-1, 8)
    panels[6].set_aspect("equal")
    panels[6].axis("off")
    panels[6].set_title("Equivalent direct bevel")
    panels[7].add_patch(
        Arc((11, 6), 2, 2, theta1=0, theta2=90, color="#059669", linewidth=4)
    )
    panels[7].set_title("Constant-radius fillet")
    panels[8].add_patch(
        Circle((4, 3.5), 1.2, facecolor="#93c5fd", edgecolor="#0369a1", linewidth=2)
    )
    panels[8].text(4, 3.5, "boss", ha="center", va="center", fontsize=8)
    panels[8].set_title("External cylindrical boss")
    figure.suptitle("Synthetic STEP Controls for Geometric Feature Recognition")
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160)
    plt.close(figure)


def run(output_dir: Path, fixture_dir: Path, *, refresh: bool) -> None:
    """Run and serialize the complete v0.40.0 experiment."""
    probe = probe_feature_recognition()
    handle_fixtures(fixture_dir, probe, refresh=refresh)
    face_rows = _face_rows(probe)
    adjacency_rows = _adjacency_rows(probe)
    candidate_rows = _candidate_rows(probe)
    observation_rows = _observation_rows(probe)
    equivalence_rows = _equivalence_rows(probe)
    _write_csv(output_dir / FACE_NAME, face_rows, tuple(face_rows[0]))
    _write_csv(output_dir / ADJACENCY_NAME, adjacency_rows, tuple(adjacency_rows[0]))
    _write_csv(output_dir / CANDIDATE_NAME, candidate_rows, tuple(candidate_rows[0]))
    _write_csv(
        output_dir / OBSERVATION_NAME, observation_rows, tuple(observation_rows[0])
    )
    _write_csv(
        output_dir / EQUIVALENCE_NAME,
        equivalence_rows,
        tuple(equivalence_rows[0]),
    )
    summary_rows = _summary_rows(probe)
    _write_csv(output_dir / SUMMARY_NAME, summary_rows, ("scope", "metric", "value"))
    write_contract(output_dir / CONTRACT_NAME, probe)
    write_figure(output_dir / FIGURE_NAME, probe)
    write_shapes_figure(output_dir / SHAPES_NAME)


def main() -> None:
    """Parse command-line arguments and run the experiment."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument(
        "--fixture-dir", type=Path, default=Path("fixtures/feature-recognition")
    )
    parser.add_argument("--refresh-fixtures", action="store_true")
    arguments = parser.parse_args()
    run(arguments.output_dir, arguments.fixture_dir, refresh=arguments.refresh_fixtures)
    print(f"Wrote feature-recognition artifacts to {arguments.output_dir}")


if __name__ == "__main__":
    main()
