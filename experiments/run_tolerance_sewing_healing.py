"""Run controlled tolerance, sewing, and shell-orientation repair experiments."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections.abc import Sequence
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402

from research_notes.tolerance_sewing_healing import (  # noqa: E402
    OperationObservation,
    ShapeObservation,
    SubshapeToleranceObservation,
    ToleranceFixture,
    ToleranceSewingProbe,
    probe_tolerance_sewing_healing,
    sewing_settings,
    tolerance_sewing_controls,
)


MANIFEST_NAME = "manifest.csv"
OBSERVATIONS_NAME = "tolerance_sewing_observations.csv"
SUBSHAPE_TOLERANCES_NAME = "tolerance_sewing_subshape_tolerances.csv"
OPERATIONS_NAME = "tolerance_sewing_operations.csv"
SUMMARY_NAME = "tolerance_sewing_summary.csv"
CONTRACT_NAME = "tolerance_sewing_contract.json"
FIGURE_NAME = "tolerance_sewing_healing.png"
SHAPES_FIGURE_NAME = "tolerance_sewing_shapes.png"

OBSERVATION_FIELDS = (
    "platform_label",
    "observation_id",
    "parent_observation_id",
    "stage",
    "control_id",
    "condition",
    "operation_id",
    "controlled_gap",
    "requested_tolerance",
    "observed_shape_type",
    "vertex_count",
    "edge_count",
    "face_count",
    "shell_count",
    "solid_count",
    "face_component_count",
    "boundary_edge_count",
    "manifold_pair_edge_count",
    "nonmanifold_edge_count",
    "closed_by_incidence",
    "orientable_manifold",
    "current_orientation_consistent",
    "minimum_face_flips",
    "closed_oriented_shell_candidate",
    "kernel_analyzer_valid",
    "vertex_tolerance_min",
    "vertex_tolerance_mean",
    "vertex_tolerance_max",
    "edge_tolerance_min",
    "edge_tolerance_mean",
    "edge_tolerance_max",
    "face_tolerance_min",
    "face_tolerance_mean",
    "face_tolerance_max",
    "surface_area",
    "maximum_face_area_error",
    "maximum_face_centroid_distance",
    "maximum_support_plane_error",
    "face_geometry_matches_control",
    "raw_signed_volume",
    "volume_contract_eligible",
    "volume_magnitude_absolute_error",
)
SUBSHAPE_FIELDS = (
    "platform_label",
    "observation_id",
    "control_id",
    "stage",
    "entity_type",
    "analysis_local_index",
    "tolerance",
)
OPERATION_FIELDS = (
    "platform_label",
    "operation_id",
    "control_id",
    "operation_type",
    "input_observation_id",
    "output_observation_id",
    "requested_tolerance",
    "maximum_tolerance_limit",
    "local_tolerances_mode",
    "nonmanifold_mode",
    "performed",
    "reported_modified",
    "modified_input_face_count",
    "reported_free_edge_count",
    "reported_contiguous_edge_count",
    "reported_multiple_edge_count",
    "reported_deleted_face_count",
    "reported_degenerated_shape_count",
    "topology_changed",
    "tolerance_changed",
    "geometry_changed",
    "kernel_validity_change",
    "decision",
    "decision_reason",
)
MANIFEST_FIELDS = (
    "fixture_id",
    "observation_id",
    "artifact_role",
    "file_name",
    "source_bytes",
    "source_sha256",
    "generator",
    "binding_distribution_version",
    "binding_module_version",
    "step_processor",
    "writer_status",
    "reader_status",
    "transferred_roots",
    "step_advanced_face_count",
    "step_open_shell_count",
    "step_closed_shell_count",
    "imported_vertex_count",
    "imported_edge_count",
    "imported_face_count",
    "imported_shell_count",
    "imported_solid_count",
    "imported_kernel_analyzer_valid",
)
SUMMARY_FIELDS = ("scope", "metric", "value")


def _float(value: float) -> str:
    return format(value, ".17g")


def _flag(value: bool) -> str:
    return str(int(value))


def _optional_float(value: float | None) -> str:
    return "" if value is None else _float(value)


def _optional_int(value: int | None) -> str:
    return "" if value is None else str(value)


def _optional_flag(value: bool | None) -> str:
    return "" if value is None else _flag(value)


def write_csv(path: Path, rows: Sequence[dict[str, str]], fields: Sequence[str]) -> None:
    """Write deterministic UTF-8 CSV evidence."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def observation_row(item: ShapeObservation, platform_label: str) -> dict[str, str]:
    """Flatten one complete stage observation."""
    return {
        "platform_label": platform_label,
        "observation_id": item.observation_id,
        "parent_observation_id": item.parent_observation_id or "",
        "stage": item.stage,
        "control_id": item.control_id,
        "condition": item.condition,
        "operation_id": item.operation_id or "",
        "controlled_gap": _float(item.controlled_gap),
        "requested_tolerance": _optional_float(item.requested_tolerance),
        "observed_shape_type": item.observed_shape_type,
        "vertex_count": str(item.vertex_count),
        "edge_count": str(item.edge_count),
        "face_count": str(item.face_count),
        "shell_count": str(item.shell_count),
        "solid_count": str(item.solid_count),
        "face_component_count": str(item.face_component_count),
        "boundary_edge_count": str(item.boundary_edge_count),
        "manifold_pair_edge_count": str(item.manifold_pair_edge_count),
        "nonmanifold_edge_count": str(item.nonmanifold_edge_count),
        "closed_by_incidence": _flag(item.closed_by_incidence),
        "orientable_manifold": _flag(item.orientable_manifold),
        "current_orientation_consistent": _flag(
            item.current_orientation_consistent
        ),
        "minimum_face_flips": _optional_int(item.minimum_face_flips),
        "closed_oriented_shell_candidate": _flag(
            item.closed_oriented_shell_candidate
        ),
        "kernel_analyzer_valid": _flag(item.kernel_analyzer_valid),
        "vertex_tolerance_min": _float(item.vertex_tolerance_min),
        "vertex_tolerance_mean": _float(item.vertex_tolerance_mean),
        "vertex_tolerance_max": _float(item.vertex_tolerance_max),
        "edge_tolerance_min": _float(item.edge_tolerance_min),
        "edge_tolerance_mean": _float(item.edge_tolerance_mean),
        "edge_tolerance_max": _float(item.edge_tolerance_max),
        "face_tolerance_min": _float(item.face_tolerance_min),
        "face_tolerance_mean": _float(item.face_tolerance_mean),
        "face_tolerance_max": _float(item.face_tolerance_max),
        "surface_area": _float(item.surface_area),
        "maximum_face_area_error": _float(item.maximum_face_area_error),
        "maximum_face_centroid_distance": _float(
            item.maximum_face_centroid_distance
        ),
        "maximum_support_plane_error": _float(
            item.maximum_support_plane_error
        ),
        "face_geometry_matches_control": _flag(
            item.face_geometry_matches_control
        ),
        "raw_signed_volume": _float(item.raw_signed_volume),
        "volume_contract_eligible": _flag(item.volume_contract_eligible),
        "volume_magnitude_absolute_error": _optional_float(
            item.volume_magnitude_absolute_error
        ),
    }


def subshape_row(
    item: SubshapeToleranceObservation, platform_label: str
) -> dict[str, str]:
    """Flatten one analysis-local subshape tolerance."""
    return {
        "platform_label": platform_label,
        "observation_id": item.observation_id,
        "control_id": item.control_id,
        "stage": item.stage,
        "entity_type": item.entity_type,
        "analysis_local_index": str(item.analysis_local_index),
        "tolerance": _float(item.tolerance),
    }


def operation_row(
    item: OperationObservation, platform_label: str
) -> dict[str, str]:
    """Flatten one explicit sewing or repair operation."""
    return {
        "platform_label": platform_label,
        "operation_id": item.operation_id,
        "control_id": item.control_id,
        "operation_type": item.operation_type,
        "input_observation_id": item.input_observation_id,
        "output_observation_id": item.output_observation_id,
        "requested_tolerance": _optional_float(item.requested_tolerance),
        "maximum_tolerance_limit": _optional_float(
            item.maximum_tolerance_limit
        ),
        "local_tolerances_mode": _optional_flag(item.local_tolerances_mode),
        "nonmanifold_mode": _optional_flag(item.nonmanifold_mode),
        "performed": _flag(item.performed),
        "reported_modified": _flag(item.reported_modified),
        "modified_input_face_count": _optional_int(
            item.modified_input_face_count
        ),
        "reported_free_edge_count": _optional_int(
            item.reported_free_edge_count
        ),
        "reported_contiguous_edge_count": _optional_int(
            item.reported_contiguous_edge_count
        ),
        "reported_multiple_edge_count": _optional_int(
            item.reported_multiple_edge_count
        ),
        "reported_deleted_face_count": _optional_int(
            item.reported_deleted_face_count
        ),
        "reported_degenerated_shape_count": _optional_int(
            item.reported_degenerated_shape_count
        ),
        "topology_changed": _flag(item.topology_changed),
        "tolerance_changed": _flag(item.tolerance_changed),
        "geometry_changed": _flag(item.geometry_changed),
        "kernel_validity_change": item.kernel_validity_change,
        "decision": item.decision,
        "decision_reason": item.decision_reason,
    }


def fixture_rows(probe: ToleranceSewingProbe) -> list[dict[str, str]]:
    """Describe every retained synthetic STEP sample and re-import result."""
    return [
        {
            "fixture_id": item.fixture_id,
            "observation_id": item.observation_id,
            "artifact_role": item.artifact_role,
            "file_name": item.file_name,
            "source_bytes": str(len(item.source_bytes)),
            "source_sha256": item.source_sha256,
            "generator": "synthetic 4 by 5 by 6 planar box-face control",
            "binding_distribution_version": probe.binding_distribution_version,
            "binding_module_version": probe.binding_module_version,
            "step_processor": item.step_processor,
            "writer_status": item.writer_status,
            "reader_status": item.reader_status,
            "transferred_roots": str(item.transferred_roots),
            "step_advanced_face_count": str(item.step_advanced_face_count),
            "step_open_shell_count": str(item.step_open_shell_count),
            "step_closed_shell_count": str(item.step_closed_shell_count),
            "imported_vertex_count": str(item.imported_vertex_count),
            "imported_edge_count": str(item.imported_edge_count),
            "imported_face_count": str(item.imported_face_count),
            "imported_shell_count": str(item.imported_shell_count),
            "imported_solid_count": str(item.imported_solid_count),
            "imported_kernel_analyzer_valid": _flag(
                item.imported_kernel_analyzer_valid
            ),
        }
        for item in probe.fixtures
    ]


def handle_fixtures(
    fixture_dir: Path, probe: ToleranceSewingProbe, *, refresh: bool
) -> None:
    """Refresh or byte-verify the deterministic STEP corpus and manifest."""
    fixture_dir.mkdir(parents=True, exist_ok=True)
    expected_names = {item.file_name for item in probe.fixtures} | {MANIFEST_NAME}
    unexpected = sorted(
        path.name for path in fixture_dir.iterdir() if path.name not in expected_names
    )
    if unexpected:
        raise RuntimeError(
            "fixture directory contains unexpected files: " + ", ".join(unexpected)
        )
    rows = fixture_rows(probe)
    manifest_path = fixture_dir / MANIFEST_NAME
    if refresh:
        for item in probe.fixtures:
            (fixture_dir / item.file_name).write_bytes(item.source_bytes)
        write_csv(manifest_path, rows, MANIFEST_FIELDS)
        return
    for item in probe.fixtures:
        path = fixture_dir / item.file_name
        if not path.is_file():
            raise RuntimeError(
                f"missing committed fixture {item.file_name}; use --refresh-fixtures"
            )
        if path.read_bytes() != item.source_bytes:
            raise RuntimeError(f"committed fixture differs: {item.file_name}")
    if not manifest_path.is_file():
        raise RuntimeError("missing committed fixture manifest; use --refresh-fixtures")
    with manifest_path.open(encoding="utf-8", newline="") as handle:
        if list(csv.DictReader(handle)) != rows:
            raise RuntimeError("committed fixture manifest differs")


def _observation(probe: ToleranceSewingProbe, observation_id: str) -> ShapeObservation:
    matches = [
        item for item in probe.observations if item.observation_id == observation_id
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one observation for {observation_id}")
    return matches[0]


def summary_rows(probe: ToleranceSewingProbe) -> list[dict[str, str]]:
    """Build compact evidence for closure boundaries and bounded repair."""
    sewn = [item for item in probe.observations if item.stage == "sewn"]
    eligible_errors = [
        float(item.volume_magnitude_absolute_error)
        for item in probe.observations
        if item.volume_magnitude_absolute_error is not None
    ]
    small_low = _observation(probe, "small_gap_box_faces__sewn_tol_1e_7")
    small_mid = _observation(probe, "small_gap_box_faces__sewn_tol_1e_6")
    large_mid = _observation(probe, "large_gap_box_faces__sewn_tol_1e_6")
    large_high = _observation(probe, "large_gap_box_faces__sewn_tol_1e_4")
    flipped_before = _observation(
        probe, "flipped_face_box_shell__orientation_input"
    )
    flipped_after = _observation(
        probe, "flipped_face_box_shell__orientation_repaired"
    )
    valid_before = _observation(probe, "valid_box_shell__orientation_input")
    valid_after = _observation(probe, "valid_box_shell__orientation_repaired")
    capped = _observation(
        probe, "large_gap_box_faces__tolerance_capped_1e_5"
    )
    return [
        {"scope": "fixture", "metric": "step_file_count", "value": str(len(probe.fixtures))},
        {"scope": "experiment", "metric": "observation_count", "value": str(len(probe.observations))},
        {"scope": "experiment", "metric": "operation_count", "value": str(len(probe.operations))},
        {"scope": "sewing", "metric": "matrix_cell_count", "value": str(len(sewn))},
        {
            "scope": "sewing",
            "metric": "closed_cell_count_by_control",
            "value": ";".join(
                f"{control.control_id}:{sum(item.closed_by_incidence for item in sewn if item.control_id == control.control_id)}"
                for control in tolerance_sewing_controls()
            ),
        },
        {
            "scope": "boundary",
            "metric": "small_gap_closure_change_1e_7_to_1e_6",
            "value": f"{_flag(small_low.closed_by_incidence)}->{_flag(small_mid.closed_by_incidence)}",
        },
        {
            "scope": "boundary",
            "metric": "large_gap_closure_change_1e_6_to_1e_4",
            "value": f"{_flag(large_mid.closed_by_incidence)}->{_flag(large_high.closed_by_incidence)}",
        },
        {
            "scope": "tolerance",
            "metric": "small_gap_closed_max_edge_tolerance",
            "value": _float(small_mid.edge_tolerance_max),
        },
        {
            "scope": "tolerance",
            "metric": "large_gap_closed_max_edge_tolerance",
            "value": _float(large_high.edge_tolerance_max),
        },
        {
            "scope": "orientation",
            "metric": "valid_shell_minimum_face_flips",
            "value": f"{valid_before.minimum_face_flips}->{valid_after.minimum_face_flips}",
        },
        {
            "scope": "orientation",
            "metric": "flipped_shell_minimum_face_flips",
            "value": f"{flipped_before.minimum_face_flips}->{flipped_after.minimum_face_flips}",
        },
        {
            "scope": "orientation",
            "metric": "flipped_shell_signed_volume",
            "value": f"{_float(flipped_before.raw_signed_volume)}->{_float(flipped_after.raw_signed_volume)}",
        },
        {
            "scope": "negative_control",
            "metric": "tolerance_cap_kernel_validity",
            "value": f"{_flag(large_high.kernel_analyzer_valid)}->{_flag(capped.kernel_analyzer_valid)}",
        },
        {
            "scope": "geometry",
            "metric": "face_geometry_match_count",
            "value": f"{sum(item.face_geometry_matches_control for item in probe.observations)}/{len(probe.observations)}",
        },
        {
            "scope": "volume",
            "metric": "eligible_observation_count",
            "value": str(sum(item.volume_contract_eligible for item in probe.observations)),
        },
        {
            "scope": "volume",
            "metric": "maximum_eligible_magnitude_absolute_error",
            "value": _float(max(eligible_errors, default=0.0)),
        },
    ]


def write_contract(path: Path, probe: ToleranceSewingProbe) -> None:
    """Write the versioned truth, operation, and claim-boundary contract."""
    sewn = [item for item in probe.observations if item.stage == "sewn"]
    payload = {
        "schema": "research-notes.tolerance-sewing-healing",
        "schema_version": "1.0",
        "release": "v0.36.0",
        "platform_label": probe.platform_label,
        "backend": {
            "distribution": "cadquery-ocp",
            "distribution_version": probe.binding_distribution_version,
            "module_version": probe.binding_module_version,
            "step_processor": probe.step_processor,
        },
        "box_dimensions": [4.0, 5.0, 6.0],
        "controls": [
            {
                "control_id": item.control_id,
                "condition": item.condition,
                "controlled_gap": item.gap,
            }
            for item in tolerance_sewing_controls()
        ],
        "sewing_settings": [
            {"setting_id": item.setting_id, "requested_tolerance": item.tolerance}
            for item in sewing_settings()
        ],
        "closure_matrix": {
            item.control_id: {
                setting.setting_id: next(
                    observation.closed_by_incidence
                    for observation in sewn
                    if observation.control_id == item.control_id
                    and math.isclose(
                        float(observation.requested_tolerance),
                        setting.tolerance,
                        rel_tol=0.0,
                        abs_tol=0.0,
                    )
                )
                for setting in sewing_settings()
            }
            for item in tolerance_sewing_controls()
        },
        "operation_policy": {
            "exact_coincident_closure": "accepted_control",
            "tolerance_mediated_gap_closure": "review_required",
            "remaining_free_boundary": "not_closed",
            "valid_orientation_no_op": "no_change",
            "controlled_single_face_reorientation": "accepted_control",
            "invalidating_tolerance_cap": "rejected_invalid",
        },
        "limitations": [
            "The corpus contains axis-aligned planar synthetic controls and one pinned OCCT route.",
            "A requested sewing tolerance is an algorithm parameter, not a manufacturing acceptance limit.",
            "Tolerance-mediated topological closure does not prove coincident support geometry or recovered design intent.",
            "The face descriptor check is specific to six known planar faces and is not a persistent-identity method.",
            "The orientation repair study changes one controlled face only and does not establish material side for nested shells.",
            "STEP samples are exchange and visual artifacts; STEP import may normalize topology or orientation.",
            "No arbitrary-input healing, spline repair, self-intersection repair, or cross-kernel portability claim is made.",
        ],
        "questions": [
            "Which application evidence should define an acceptable sewing-tolerance budget?",
            "Should tolerance-mediated closure be quarantined until geometric residuals are reviewed?",
            "How should modified, split, and merged subshapes be matched without treating local indices as identities?",
            "How can orientation repair preserve material side when outer and void shells are nested?",
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def write_figure(path: Path, probe: ToleranceSewingProbe) -> None:
    """Visualize closure boundaries, tolerance inflation, and repair effects."""
    controls = tolerance_sewing_controls()
    settings = sewing_settings()
    closure = np.zeros((len(controls), len(settings)), dtype=float)
    edge_tolerance = np.zeros_like(closure)
    boundary_edges = np.zeros_like(closure)
    for row, control in enumerate(controls):
        for column, setting in enumerate(settings):
            item = _observation(
                probe, f"{control.control_id}__sewn_{setting.setting_id}"
            )
            closure[row, column] = item.closed_by_incidence
            edge_tolerance[row, column] = item.edge_tolerance_max
            boundary_edges[row, column] = item.boundary_edge_count

    figure, axes = plt.subplots(2, 2, figsize=(14.8, 10.0), constrained_layout=True)
    closure_axis, tolerance_axis, boundary_axis, repair_axis = axes.flat
    closure_axis.imshow(closure, cmap="RdYlGn", vmin=0.0, vmax=1.0, aspect="auto")
    closure_axis.set_xticks(
        range(len(settings)), [f"{item.tolerance:.0e}" for item in settings]
    )
    closure_axis.set_yticks(
        range(len(controls)), [f"gap {item.gap:.0e}" for item in controls]
    )
    for row in range(len(controls)):
        for column in range(len(settings)):
            closure_axis.text(
                column,
                row,
                "closed" if closure[row, column] else "open",
                ha="center",
                va="center",
                fontsize=9,
            )
    closure_axis.set_xlabel("Requested sewing tolerance")
    closure_axis.set_title("Closure changes across controlled gap/tolerance ratios")

    x = np.arange(len(settings))
    for row, control in enumerate(controls):
        tolerance_axis.plot(
            x,
            edge_tolerance[row],
            marker="o",
            linewidth=2,
            label=f"gap {control.gap:.0e}",
        )
    tolerance_axis.set_xticks(x, [f"{item.tolerance:.0e}" for item in settings])
    tolerance_axis.set_yscale("log")
    tolerance_axis.set_ylabel("Maximum stored edge tolerance")
    tolerance_axis.set_xlabel("Requested sewing tolerance")
    tolerance_axis.grid(True, axis="y", alpha=0.25)
    tolerance_axis.legend(fontsize=8)
    tolerance_axis.set_title("Stored tolerances follow merged residuals, not request alone")

    width = 0.24
    for row, control in enumerate(controls):
        boundary_axis.bar(
            x + (row - 1) * width,
            boundary_edges[row],
            width,
            label=f"gap {control.gap:.0e}",
        )
    boundary_axis.set_xticks(x, [f"{item.tolerance:.0e}" for item in settings])
    boundary_axis.set_ylabel("Boundary edge count")
    boundary_axis.set_xlabel("Requested sewing tolerance")
    boundary_axis.set_ylim(0.0, 9.5)
    boundary_axis.legend(fontsize=8)
    boundary_axis.set_title("An unmerged top face contributes eight free boundary edges")

    repair_columns = (
        ("valid\ninput", _observation(probe, "valid_box_shell__orientation_input")),
        ("valid\noutput", _observation(probe, "valid_box_shell__orientation_repaired")),
        ("flipped\ninput", _observation(probe, "flipped_face_box_shell__orientation_input")),
        ("flipped\noutput", _observation(probe, "flipped_face_box_shell__orientation_repaired")),
        ("large gap\nsewn", _observation(probe, "large_gap_box_faces__sewn_tol_1e_4")),
        ("tolerance\ncapped", _observation(probe, "large_gap_box_faces__tolerance_capped_1e_5")),
    )
    repair_values = np.array(
        [
            [
                item.current_orientation_consistent,
                item.kernel_analyzer_valid,
                item.volume_contract_eligible,
            ]
            for _, item in repair_columns
        ],
        dtype=float,
    ).T
    repair_axis.imshow(
        repair_values, cmap="RdYlGn", vmin=0.0, vmax=1.0, aspect="auto"
    )
    repair_axis.set_xticks(
        range(len(repair_columns)), [label for label, _ in repair_columns], fontsize=8
    )
    repair_axis.set_yticks(
        range(3), ["orientation consistent", "kernel valid", "volume eligible"]
    )
    for row in range(repair_values.shape[0]):
        for column in range(repair_values.shape[1]):
            repair_axis.text(
                column,
                row,
                "yes" if repair_values[row, column] else "no",
                ha="center",
                va="center",
                fontsize=8,
            )
    repair_axis.set_title("Repair success and validity remain separate decisions")

    figure.suptitle(
        "v0.36.0 — Tolerances, Sewing, and Healing Effects",
        fontsize=16,
        fontweight="bold",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160, metadata={"Software": "research-notes"})
    plt.close(figure)


def _box_faces(display_gap: float) -> list[list[tuple[float, float, float]]]:
    x0, x1 = 0.0, 4.0
    y0, y1 = 0.0, 5.0
    z0, z1 = 0.0, 6.0
    return [
        [(x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)],
        [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)],
        [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)],
        [(x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1)],
        [(x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1)],
        [
            (x0, y0, z1 + display_gap),
            (x1, y0, z1 + display_gap),
            (x1, y1, z1 + display_gap),
            (x0, y1, z1 + display_gap),
        ],
    ]


def _draw_box(
    axis: object,
    *,
    display_gap: float,
    title: str,
    flipped: bool = False,
    repaired: bool = False,
) -> None:
    faces = _box_faces(display_gap)
    colors = ["#cbd5e1", "#93c5fd", "#60a5fa", "#3b82f6", "#2563eb", "#86efac"]
    if flipped:
        colors[2] = "#ef4444"
    if repaired:
        colors[2] = "#22c55e"
    collection = Poly3DCollection(
        faces,
        facecolors=colors,
        edgecolors="#0f172a",
        linewidths=1.0,
        alpha=0.68,
    )
    axis.add_collection3d(collection)
    if display_gap > 0.0:
        for x, y in ((0.0, 0.0), (4.0, 0.0), (4.0, 5.0), (0.0, 5.0)):
            axis.plot([x, x], [y, y], [6.0, 6.0 + display_gap], color="#dc2626", linewidth=2.5)
    axis.set_xlim(-0.4, 4.4)
    axis.set_ylim(-0.4, 5.4)
    axis.set_zlim(-0.4, 6.9)
    axis.set_box_aspect((4.8, 5.8, 7.3))
    axis.set_xticks([])
    axis.set_yticks([])
    axis.set_zticks([])
    axis.view_init(elev=24, azim=-56)
    axis.set_title(title, fontsize=10)


def write_shapes_figure(path: Path) -> None:
    """Render visual controls with explicitly exaggerated gaps."""
    figure = plt.figure(figsize=(15.0, 9.0), constrained_layout=True)
    titles = (
        (0.0, "Coincident independent faces\n(actual gap 0)", False, False),
        (0.5, "Small-gap input\n5e-7 shown as 0.5", False, False),
        (0.5, "Large-gap input\n5e-5 shown as 0.5", False, False),
        (0.0, "Tolerance-mediated sewn shell\nsupport faces remain unchanged", False, False),
        (0.0, "Orientation input\none controlled face reversed", True, False),
        (0.0, "Orientation repair output\nsame support geometry", False, True),
    )
    for index, (gap, title, flipped, repaired) in enumerate(titles, start=1):
        axis = figure.add_subplot(2, 3, index, projection="3d")
        _draw_box(
            axis,
            display_gap=gap,
            title=title,
            flipped=flipped,
            repaired=repaired,
        )
    figure.suptitle(
        "Synthetic controls — gap panels are deliberately not to scale",
        fontsize=15,
        fontweight="bold",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160, metadata={"Software": "research-notes"})
    plt.close(figure)


def run(
    output_dir: Path,
    fixture_dir: Path,
    *,
    refresh: bool,
    platform_label: str,
) -> None:
    """Run the complete controlled tolerance, sewing, and healing study."""
    probe = probe_tolerance_sewing_healing(platform_label=platform_label)
    handle_fixtures(fixture_dir, probe, refresh=refresh)
    write_csv(
        output_dir / OBSERVATIONS_NAME,
        [observation_row(item, probe.platform_label) for item in probe.observations],
        OBSERVATION_FIELDS,
    )
    write_csv(
        output_dir / SUBSHAPE_TOLERANCES_NAME,
        [subshape_row(item, probe.platform_label) for item in probe.tolerance_observations],
        SUBSHAPE_FIELDS,
    )
    write_csv(
        output_dir / OPERATIONS_NAME,
        [operation_row(item, probe.platform_label) for item in probe.operations],
        OPERATION_FIELDS,
    )
    write_csv(output_dir / SUMMARY_NAME, summary_rows(probe), SUMMARY_FIELDS)
    write_contract(output_dir / CONTRACT_NAME, probe)
    write_figure(output_dir / FIGURE_NAME, probe)
    write_shapes_figure(output_dir / SHAPES_FIGURE_NAME)


def main() -> None:
    """Parse command-line arguments and run the experiment."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=Path("fixtures/tolerance-sewing-healing"),
    )
    parser.add_argument("--platform-label", default="linux-x64-reference")
    parser.add_argument("--refresh-fixtures", action="store_true")
    arguments = parser.parse_args()
    run(
        arguments.output_dir,
        arguments.fixture_dir,
        refresh=arguments.refresh_fixtures,
        platform_label=arguments.platform_label,
    )
    print(f"Wrote tolerance, sewing, and healing artifacts to {arguments.output_dir}")


if __name__ == "__main__":
    main()
