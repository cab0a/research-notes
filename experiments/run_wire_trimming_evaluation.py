"""Evaluate controlled wires, trimming loops, and face orientation."""

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

from research_notes.wire_trimming import (  # noqa: E402
    ClassificationObservation,
    EdgeUseObservation,
    FaceTrimObservation,
    WireObservation,
    WireTrimmingProbe,
    probe_wire_trimming,
    wire_trimming_controls,
)


FIXTURE_NAME = "analytic_trimmed_faces.step"
MANIFEST_NAME = "manifest.csv"
FACE_OBSERVATIONS_NAME = "wire_trimming_face_observations.csv"
WIRE_OBSERVATIONS_NAME = "wire_trimming_wire_observations.csv"
EDGE_USES_NAME = "wire_trimming_edge_uses.csv"
CLASSIFICATIONS_NAME = "wire_trimming_classifications.csv"
SUMMARY_NAME = "wire_trimming_summary.csv"
CONTRACT_NAME = "wire_trimming_contract.json"
FIGURE_NAME = "wire_trimming_evaluation.png"
SHAPES_FIGURE_NAME = "wire_trimming_shapes.png"

FACE_FIELDS = (
    "platform_label",
    "stage",
    "face_id",
    "surface_type",
    "expected_orientation",
    "observed_orientation",
    "expected_area",
    "observed_area",
    "area_absolute_error",
    "expected_centroid_x",
    "expected_centroid_y",
    "expected_centroid_z",
    "observed_centroid_x",
    "observed_centroid_y",
    "observed_centroid_z",
    "centroid_distance",
    "expected_u_min",
    "expected_u_max",
    "expected_v_min",
    "expected_v_max",
    "observed_u_min",
    "observed_u_max",
    "observed_v_min",
    "observed_v_max",
    "restricted_uv_max_absolute_error",
    "support_u_min",
    "support_u_max",
    "support_v_min",
    "support_v_max",
    "expected_support_u_finite",
    "observed_support_u_finite",
    "expected_support_v_finite",
    "observed_support_v_finite",
    "u_periodic",
    "v_periodic",
    "expected_natural_restriction",
    "observed_natural_restriction",
    "wire_count",
    "outer_wire_count",
    "inner_wire_count",
)
WIRE_FIELDS = (
    "platform_label",
    "stage",
    "face_id",
    "wire_index",
    "role",
    "orientation",
    "edge_occurrence_count",
    "unique_edge_count",
    "degenerate_occurrence_count",
    "seam_occurrence_count",
    "expected_signed_uv_area",
    "observed_signed_uv_area",
    "signed_uv_area_absolute_error",
    "max_uv_connection_gap",
    "max_vertex_distance",
    "topologically_closed",
    "brepcheck_closed_2d_status",
    "brepcheck_orientation_status",
    "order_defect",
    "connected_defect",
    "closed_defect",
    "degenerated_defect",
)
EDGE_USE_FIELDS = (
    "platform_label",
    "stage",
    "face_id",
    "wire_index",
    "wire_role",
    "wire_use_index",
    "edge_index",
    "orientation",
    "degenerated",
    "seam",
    "has_curve_3d",
    "vertex_start_parameter",
    "vertex_end_parameter",
    "uv_start_u",
    "uv_start_v",
    "uv_end_u",
    "uv_end_v",
    "next_uv_gap",
    "next_vertex_distance",
    "next_vertex_is_same",
)
CLASSIFICATION_FIELDS = (
    "platform_label",
    "stage",
    "face_id",
    "sample_id",
    "u",
    "v",
    "expected_state",
    "observed_state",
    "matches",
)
SUMMARY_FIELDS = ("scope", "metric", "value")
MANIFEST_FIELDS = (
    "fixture",
    "file_name",
    "source_bytes",
    "source_sha256",
    "generator",
    "binding_distribution_version",
    "binding_module_version",
    "step_processor",
)


def _float(value: float) -> str:
    return format(value, ".17g")


def _flag(value: bool) -> str:
    return str(int(value))


def write_csv(
    path: Path, rows: Sequence[dict[str, str]], fields: Sequence[str]
) -> None:
    """Write deterministic UTF-8 CSV evidence."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def face_row(item: FaceTrimObservation, platform_label: str) -> dict[str, str]:
    """Flatten one face observation."""
    expected_uv = item.expected_restricted_uv_bounds
    observed_uv = item.observed_restricted_uv_bounds
    support_uv = item.support_uv_bounds
    return {
        "platform_label": platform_label,
        "stage": item.stage,
        "face_id": item.face_id,
        "surface_type": item.surface_type,
        "expected_orientation": item.expected_orientation,
        "observed_orientation": item.observed_orientation,
        "expected_area": _float(item.expected_area),
        "observed_area": _float(item.observed_area),
        "area_absolute_error": _float(item.area_absolute_error),
        **{
            f"expected_centroid_{axis}": _float(value)
            for axis, value in zip("xyz", item.expected_centroid, strict=True)
        },
        **{
            f"observed_centroid_{axis}": _float(value)
            for axis, value in zip("xyz", item.observed_centroid, strict=True)
        },
        "centroid_distance": _float(item.centroid_distance),
        "expected_u_min": _float(expected_uv[0]),
        "expected_u_max": _float(expected_uv[1]),
        "expected_v_min": _float(expected_uv[2]),
        "expected_v_max": _float(expected_uv[3]),
        "observed_u_min": _float(observed_uv[0]),
        "observed_u_max": _float(observed_uv[1]),
        "observed_v_min": _float(observed_uv[2]),
        "observed_v_max": _float(observed_uv[3]),
        "restricted_uv_max_absolute_error": _float(
            item.restricted_uv_max_absolute_error
        ),
        "support_u_min": _float(support_uv[0]),
        "support_u_max": _float(support_uv[1]),
        "support_v_min": _float(support_uv[2]),
        "support_v_max": _float(support_uv[3]),
        "expected_support_u_finite": _flag(item.expected_support_u_finite),
        "observed_support_u_finite": _flag(item.observed_support_u_finite),
        "expected_support_v_finite": _flag(item.expected_support_v_finite),
        "observed_support_v_finite": _flag(item.observed_support_v_finite),
        "u_periodic": _flag(item.u_periodic),
        "v_periodic": _flag(item.v_periodic),
        "expected_natural_restriction": _flag(item.expected_natural_restriction),
        "observed_natural_restriction": _flag(item.observed_natural_restriction),
        "wire_count": str(item.wire_count),
        "outer_wire_count": str(item.outer_wire_count),
        "inner_wire_count": str(item.inner_wire_count),
    }


def wire_row(item: WireObservation, platform_label: str) -> dict[str, str]:
    """Flatten one wire observation."""
    return {
        "platform_label": platform_label,
        "stage": item.stage,
        "face_id": item.face_id,
        "wire_index": str(item.wire_index),
        "role": item.role,
        "orientation": item.orientation,
        "edge_occurrence_count": str(item.edge_occurrence_count),
        "unique_edge_count": str(item.unique_edge_count),
        "degenerate_occurrence_count": str(item.degenerate_occurrence_count),
        "seam_occurrence_count": str(item.seam_occurrence_count),
        "expected_signed_uv_area": _float(item.expected_signed_uv_area),
        "observed_signed_uv_area": _float(item.observed_signed_uv_area),
        "signed_uv_area_absolute_error": _float(
            item.signed_uv_area_absolute_error
        ),
        "max_uv_connection_gap": _float(item.max_uv_connection_gap),
        "max_vertex_distance": _float(item.max_vertex_distance),
        "topologically_closed": _flag(item.topologically_closed),
        "brepcheck_closed_2d_status": item.brepcheck_closed_2d_status,
        "brepcheck_orientation_status": item.brepcheck_orientation_status,
        "order_defect": _flag(item.order_defect),
        "connected_defect": _flag(item.connected_defect),
        "closed_defect": _flag(item.closed_defect),
        "degenerated_defect": _flag(item.degenerated_defect),
    }


def edge_use_row(item: EdgeUseObservation, platform_label: str) -> dict[str, str]:
    """Flatten one ordered edge occurrence."""
    return {
        "platform_label": platform_label,
        "stage": item.stage,
        "face_id": item.face_id,
        "wire_index": str(item.wire_index),
        "wire_role": item.wire_role,
        "wire_use_index": str(item.wire_use_index),
        "edge_index": str(item.edge_index),
        "orientation": item.orientation,
        "degenerated": _flag(item.degenerated),
        "seam": _flag(item.seam),
        "has_curve_3d": _flag(item.has_curve_3d),
        "vertex_start_parameter": _float(item.vertex_start_parameter),
        "vertex_end_parameter": _float(item.vertex_end_parameter),
        "uv_start_u": _float(item.uv_start[0]),
        "uv_start_v": _float(item.uv_start[1]),
        "uv_end_u": _float(item.uv_end[0]),
        "uv_end_v": _float(item.uv_end[1]),
        "next_uv_gap": _float(item.next_uv_gap),
        "next_vertex_distance": _float(item.next_vertex_distance),
        "next_vertex_is_same": _flag(item.next_vertex_is_same),
    }


def classification_row(
    item: ClassificationObservation, platform_label: str
) -> dict[str, str]:
    """Flatten one parameter-domain classification."""
    return {
        "platform_label": platform_label,
        "stage": item.stage,
        "face_id": item.face_id,
        "sample_id": item.sample_id,
        "u": _float(item.uv[0]),
        "v": _float(item.uv[1]),
        "expected_state": item.expected_state,
        "observed_state": item.observed_state,
        "matches": _flag(item.matches),
    }


def manifest_row(probe: WireTrimmingProbe) -> dict[str, str]:
    """Describe the synthetic STEP fixture and runtime provenance."""
    return {
        "fixture": "analytic_trimmed_faces",
        "file_name": FIXTURE_NAME,
        "source_bytes": str(len(probe.source_bytes)),
        "source_sha256": probe.source_sha256,
        "generator": "two planar frames, one closed cylinder, and one natural sphere",
        "binding_distribution_version": probe.binding_distribution_version,
        "binding_module_version": probe.binding_module_version,
        "step_processor": probe.step_processor,
    }


def handle_fixture(
    fixture_dir: Path, probe: WireTrimmingProbe, *, refresh: bool
) -> None:
    """Refresh or verify the deterministic generated STEP fixture."""
    fixture_dir.mkdir(parents=True, exist_ok=True)
    expected_names = {FIXTURE_NAME, MANIFEST_NAME}
    unexpected = sorted(
        path.name for path in fixture_dir.iterdir() if path.name not in expected_names
    )
    if unexpected:
        raise RuntimeError(
            "fixture directory contains unexpected files: " + ", ".join(unexpected)
        )
    expected_manifest = [manifest_row(probe)]
    fixture_path = fixture_dir / FIXTURE_NAME
    manifest_path = fixture_dir / MANIFEST_NAME
    if refresh:
        fixture_path.write_bytes(probe.source_bytes)
        write_csv(manifest_path, expected_manifest, MANIFEST_FIELDS)
        return
    if not fixture_path.is_file() or not manifest_path.is_file():
        raise RuntimeError("missing committed trimming fixture; use --refresh-fixtures")
    if fixture_path.read_bytes() != probe.source_bytes:
        raise RuntimeError("committed trimming fixture differs from regenerated bytes")
    with manifest_path.open(encoding="utf-8", newline="") as handle:
        if list(csv.DictReader(handle)) != expected_manifest:
            raise RuntimeError("committed trimming fixture manifest differs")


def _stage(probe: WireTrimmingProbe, name: str) -> tuple[list[FaceTrimObservation], list[WireObservation], list[ClassificationObservation]]:
    return (
        [item for item in probe.face_observations if item.stage == name],
        [item for item in probe.wire_observations if item.stage == name],
        [item for item in probe.classification_observations if item.stage == name],
    )


def summary_rows(probe: WireTrimmingProbe) -> list[dict[str, str]]:
    """Build compact evidence for topology, trimming, orientation, and exchange."""
    rows = [
        {"scope": "fixture", "metric": "face_count", "value": "4"},
        {"scope": "fixture", "metric": "wire_count", "value": "6"},
        {"scope": "fixture", "metric": "outer_wire_count", "value": "4"},
        {"scope": "fixture", "metric": "inner_wire_count", "value": "2"},
        {"scope": "fixture", "metric": "edge_occurrence_count", "value": "24"},
        {"scope": "fixture", "metric": "degenerate_occurrence_count", "value": "2"},
        {"scope": "fixture", "metric": "seam_occurrence_count", "value": "4"},
        {"scope": "exchange", "metric": "constructed_valid", "value": _flag(probe.constructed_valid)},
        {"scope": "exchange", "metric": "imported_valid", "value": _flag(probe.imported_valid)},
        {"scope": "exchange", "metric": "step_advanced_face_count", "value": str(probe.step_advanced_face_count)},
        {"scope": "exchange", "metric": "step_face_outer_bound_count", "value": str(probe.step_face_outer_bound_count)},
        {"scope": "exchange", "metric": "step_face_bound_count", "value": str(probe.step_face_bound_count)},
        {"scope": "exchange", "metric": "step_edge_loop_count", "value": str(probe.step_edge_loop_count)},
        {"scope": "exchange", "metric": "step_seam_curve_count", "value": str(probe.step_seam_curve_count)},
        {"scope": "exchange", "metric": "step_degenerate_pcurve_count", "value": str(probe.step_degenerate_pcurve_count)},
    ]
    for name in ("constructed", "step_imported"):
        faces, wires, classifications = _stage(probe, name)
        rows.extend(
            (
                {"scope": name, "metric": "orientation_match_count", "value": str(sum(item.expected_orientation == item.observed_orientation for item in faces))},
                {"scope": name, "metric": "max_face_area_absolute_error", "value": _float(max(item.area_absolute_error for item in faces))},
                {"scope": name, "metric": "max_centroid_distance", "value": _float(max(item.centroid_distance for item in faces))},
                {"scope": name, "metric": "max_restricted_uv_absolute_error", "value": _float(max(item.restricted_uv_max_absolute_error for item in faces))},
                {"scope": name, "metric": "max_signed_uv_area_absolute_error", "value": _float(max(item.signed_uv_area_absolute_error for item in wires))},
                {"scope": name, "metric": "max_uv_connection_gap", "value": _float(max(item.max_uv_connection_gap for item in wires))},
                {"scope": name, "metric": "max_vertex_distance", "value": _float(max(item.max_vertex_distance for item in wires))},
                {"scope": name, "metric": "classification_match_count", "value": str(sum(item.matches for item in classifications))},
                {"scope": name, "metric": "classification_count", "value": str(len(classifications))},
                {"scope": name, "metric": "wire_defect_count", "value": str(sum(item.order_defect or item.connected_defect or item.closed_defect or item.degenerated_defect for item in wires))},
            )
        )
    return rows


def write_contract(path: Path, probe: WireTrimmingProbe) -> None:
    """Write machine-readable methods, evidence boundaries, and questions."""
    payload = {
        "schema": "research-notes.wire-trimming-evaluation",
        "schema_version": "1.0",
        "release": "v0.34.0",
        "fixture": {
            "file": FIXTURE_NAME,
            "sha256": probe.source_sha256,
            "faces": [
                {
                    "face_id": item.face_id,
                    "surface_type": item.surface_type,
                    "origin": item.origin,
                    "radius": item.radius,
                    "restricted_uv_bounds": item.restricted_uv_bounds,
                    "reversed": item.reversed,
                    "natural_restriction": item.natural_restriction,
                }
                for item in wire_trimming_controls()
            ],
        },
        "runtime": {
            "platform_label": probe.platform_label,
            "binding_distribution_version": probe.binding_distribution_version,
            "binding_module_version": probe.binding_module_version,
            "step_processor": probe.step_processor,
        },
        "truth_contract": [
            "Face area, centroid, restricted UV bounds, and signed loop areas are derived analytically without calling OCCT.",
            "The planar inner loop subtracts material; reversing the face changes loop signs but not area, centroid, or point classification.",
            "Ordered edge uses are evaluated at oriented topological vertex parameters, not assumed to follow ascending curve parameters.",
            "The cylinder uses one seam edge twice, while the sphere additionally uses two degenerate pole edges without three-dimensional curves.",
            "Support-surface bounds are reported separately from the finite restriction imposed by face wires.",
        ],
        "observed_exchange_boundary": {
            "constructed_sphere_natural_restriction": True,
            "step_imported_sphere_natural_restriction": next(
                item.observed_natural_restriction
                for item in probe.face_observations
                if item.stage == "step_imported" and item.face_id == "natural_sphere"
            ),
            "meaning": "NaturalRestriction is observed as a kernel flag, not treated as a portable STEP semantic contract.",
        },
        "claim_boundaries": [
            "The fixtures contain valid analytic faces, not adversarial, self-intersecting, disconnected, or non-manifold wires.",
            "Signed UV area is a controlled diagnostic for these line-segment parameter loops, not a general classifier for arbitrary curved p-curves.",
            "A zero-length three-dimensional edge may remain necessary in the parameter domain at a surface singularity.",
            "The experiment observes validation statuses and does not invoke wire or face repair.",
            "Numerical limits apply only to the committed fixtures and pinned OCCT binding.",
        ],
        "open_questions": [
            "Which STEP constructs, if any, should map to a kernel NaturalRestriction flag after import?",
            "How should curved p-curve loop area and winding be evaluated without flattening accuracy loss?",
            "Which quarantine policy should handle self-intersections, missing p-curves, and inconsistent outer-loop labels before repair?",
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _plot_arrow_loop(axis: object, points: Sequence[tuple[float, float]], color: str, label: str) -> None:
    axis.plot([p[0] for p in points] + [points[0][0]], [p[1] for p in points] + [points[0][1]], color=color, linewidth=2, label=label)
    for start, end in zip(points, points[1:] + points[:1], strict=True):
        middle = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
        delta = ((end[0] - start[0]) * 0.18, (end[1] - start[1]) * 0.18)
        axis.arrow(middle[0] - delta[0] / 2.0, middle[1] - delta[1] / 2.0, delta[0], delta[1], head_width=0.18, color=color, length_includes_head=True)


def write_figure(path: Path, probe: WireTrimmingProbe) -> None:
    """Visualize material loops, periodic singular boundaries, and errors."""
    figure, axes = plt.subplots(2, 2, figsize=(13.8, 9.2), constrained_layout=True)
    forward_axis, reversed_axis, periodic_axis, evidence_axis = axes.flat

    outer_forward = [(-4.0, -3.0), (4.0, -3.0), (4.0, 3.0), (-4.0, 3.0)]
    inner_forward = [(-1.0, -1.0), (-1.0, 1.0), (2.0, 1.0), (2.0, -1.0)]
    _plot_arrow_loop(forward_axis, outer_forward, "#2563eb", "outer: +48")
    _plot_arrow_loop(forward_axis, inner_forward, "#dc2626", "inner: -6")
    forward_axis.fill([-4, 4, 4, -4], [-3, -3, 3, 3], color="#bfdbfe", alpha=0.35)
    forward_axis.fill([-1, 2, 2, -1], [-1, -1, 1, 1], color="white")
    forward_axis.set_title("Forward planar face: material on loop left")

    _plot_arrow_loop(reversed_axis, list(reversed(outer_forward)), "#7c3aed", "outer: -48")
    _plot_arrow_loop(reversed_axis, list(reversed(inner_forward)), "#ea580c", "inner: +6")
    reversed_axis.fill([-4, 4, 4, -4], [-3, -3, 3, 3], color="#ddd6fe", alpha=0.35)
    reversed_axis.fill([-1, 2, 2, -1], [-1, -1, 1, 1], color="white")
    reversed_axis.set_title("Reversed face: loop signs change, material does not")
    for axis in (forward_axis, reversed_axis):
        axis.set_aspect("equal")
        axis.set_xlim(-5, 5)
        axis.set_ylim(-4, 4)
        axis.set_xlabel("U parameter")
        axis.set_ylabel("V parameter")
        axis.grid(alpha=0.2)
        axis.legend(fontsize=8)

    imported_uses = [
        item for item in probe.edge_use_observations if item.stage == "step_imported" and item.face_id in {"closed_cylinder", "natural_sphere"}
    ]
    colors = {"closed_cylinder": "#059669", "natural_sphere": "#d97706"}
    for item in imported_uses:
        style = "--" if item.degenerated else "-"
        periodic_axis.plot(
            [item.uv_start[0], item.uv_end[0]],
            [item.uv_start[1], item.uv_end[1]],
            linestyle=style,
            linewidth=3 if item.seam else 2,
            color=colors[item.face_id],
        )
    periodic_axis.text(0.15, -1.7, "cylinder", color=colors["closed_cylinder"])
    periodic_axis.text(3.6, 1.18, "sphere: dashed pole edges", color=colors["natural_sphere"], fontsize=8)
    periodic_axis.set_xlim(-0.35, 2.0 * math.pi + 0.35)
    periodic_axis.set_ylim(-2.3, 2.3)
    periodic_axis.set_xlabel("U parameter")
    periodic_axis.set_ylabel("V parameter")
    periodic_axis.set_title("Periodic seams and singular pole boundaries")
    periodic_axis.grid(alpha=0.25)

    stages = ("constructed", "step_imported")
    labels = ("Face area", "Centroid", "UV bounds", "Loop area", "UV closure")
    width = 0.36
    positions = np.arange(len(labels))
    for offset, stage, color in ((-width / 2, stages[0], "#2563eb"), (width / 2, stages[1], "#f59e0b")):
        faces, wires, _ = _stage(probe, stage)
        values = (
            max(item.area_absolute_error for item in faces),
            max(item.centroid_distance for item in faces),
            max(item.restricted_uv_max_absolute_error for item in faces),
            max(item.signed_uv_area_absolute_error for item in wires),
            max(item.max_uv_connection_gap for item in wires),
        )
        evidence_axis.bar(positions + offset, [max(value, 1.0e-18) for value in values], width, label=stage.replace("_", " "), color=color)
    evidence_axis.set_yscale("log")
    evidence_axis.set_xticks(positions, labels, rotation=20)
    evidence_axis.set_ylabel("Maximum absolute error or distance")
    evidence_axis.set_title("Analytic and closure checks")
    evidence_axis.legend(fontsize=8)

    figure.suptitle("v0.34.0 Wires, Trimming, and Face Orientation")
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160)
    plt.close(figure)


def write_shapes_figure(path: Path) -> None:
    """Render the generated planar, cylindrical, and spherical face controls."""
    figure = plt.figure(figsize=(15.6, 5.4), constrained_layout=True)
    plane_axis = figure.add_subplot(1, 3, 1, projection="3d")
    cylinder_axis = figure.add_subplot(1, 3, 2, projection="3d")
    sphere_axis = figure.add_subplot(1, 3, 3, projection="3d")

    u_grid, v_grid = np.meshgrid(np.linspace(-4.0, 4.0, 80), np.linspace(-3.0, 3.0, 60))
    hole = (u_grid >= -1.0) & (u_grid <= 2.0) & (v_grid >= -1.0) & (v_grid <= 1.0)
    for origin_x, color in ((0.0, "#60a5fa"), (12.0, "#a78bfa")):
        x_grid = np.where(hole, np.nan, origin_x + u_grid)
        y_grid = np.where(hole, np.nan, v_grid)
        z_grid = np.where(hole, np.nan, 0.0)
        plane_axis.plot_surface(x_grid, y_grid, z_grid, color=color, alpha=0.72, linewidth=0)
    plane_axis.plot([], [], [], color="#60a5fa", linewidth=8, label="forward")
    plane_axis.plot([], [], [], color="#a78bfa", linewidth=8, label="reversed")
    plane_axis.set_title("Planar frames with inner wires")
    plane_axis.set_xlabel("X")
    plane_axis.set_ylabel("Y")
    plane_axis.set_zlim(-1.0, 1.0)
    plane_axis.set_zticks([])
    plane_axis.set_box_aspect((20.0, 7.0, 2.5))
    plane_axis.view_init(elev=28, azim=-62)
    plane_axis.legend(fontsize=8)

    u_grid, v_grid = np.meshgrid(np.linspace(0.0, 2.0 * math.pi, 90), np.linspace(-2.0, 2.0, 45))
    cylinder_x = 25.0 + 2.0 * np.cos(u_grid)
    cylinder_y = 2.0 * np.sin(u_grid)
    cylinder_axis.plot_surface(cylinder_x, cylinder_y, v_grid, color="#6ee7b7", alpha=0.72, linewidth=0)
    cylinder_axis.plot(np.full(80, 27.0), np.zeros(80), np.linspace(-2.0, 2.0, 80), color="#dc2626", linewidth=3, label="seam")
    cylinder_axis.set_title("Closed cylindrical lateral face")
    cylinder_axis.set_xlabel("X")
    cylinder_axis.set_ylabel("Y")
    cylinder_axis.set_zlabel("Z")
    cylinder_axis.set_box_aspect((1.0, 1.0, 1.0))
    cylinder_axis.view_init(elev=24, azim=-52)
    cylinder_axis.legend(fontsize=8)

    u_grid, v_grid = np.meshgrid(np.linspace(0.0, 2.0 * math.pi, 90), np.linspace(-math.pi / 2.0, math.pi / 2.0, 50))
    sphere_x = 40.0 + 3.0 * np.cos(v_grid) * np.cos(u_grid)
    sphere_y = 3.0 * np.cos(v_grid) * np.sin(u_grid)
    sphere_z = 3.0 * np.sin(v_grid)
    sphere_axis.plot_surface(sphere_x, sphere_y, sphere_z, color="#fbbf24", alpha=0.72, linewidth=0)
    seam_v = np.linspace(-math.pi / 2.0, math.pi / 2.0, 100)
    sphere_axis.plot(40.0 + 3.0 * np.cos(seam_v), np.zeros(100), 3.0 * np.sin(seam_v), color="#dc2626", linewidth=3, label="seam")
    sphere_axis.scatter([40.0, 40.0], [0.0, 0.0], [-3.0, 3.0], color="#7c2d12", s=35, label="degenerate poles")
    sphere_axis.set_title("Natural sphere with singular poles")
    sphere_axis.set_xlabel("X")
    sphere_axis.set_ylabel("Y")
    sphere_axis.set_zlabel("Z")
    sphere_axis.set_box_aspect((1.0, 1.0, 1.0))
    sphere_axis.view_init(elev=24, azim=-52)
    sphere_axis.legend(fontsize=8)

    figure.suptitle("Synthetic STEP Geometry Controls for v0.34.0")
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160)
    plt.close(figure)


def run(output_dir: Path, fixture_dir: Path, *, refresh: bool, platform_label: str) -> None:
    """Run the complete controlled wire-trimming experiment."""
    probe = probe_wire_trimming(platform_label=platform_label)
    handle_fixture(fixture_dir, probe, refresh=refresh)
    write_csv(output_dir / FACE_OBSERVATIONS_NAME, [face_row(item, probe.platform_label) for item in probe.face_observations], FACE_FIELDS)
    write_csv(output_dir / WIRE_OBSERVATIONS_NAME, [wire_row(item, probe.platform_label) for item in probe.wire_observations], WIRE_FIELDS)
    write_csv(output_dir / EDGE_USES_NAME, [edge_use_row(item, probe.platform_label) for item in probe.edge_use_observations], EDGE_USE_FIELDS)
    write_csv(output_dir / CLASSIFICATIONS_NAME, [classification_row(item, probe.platform_label) for item in probe.classification_observations], CLASSIFICATION_FIELDS)
    write_csv(output_dir / SUMMARY_NAME, summary_rows(probe), SUMMARY_FIELDS)
    write_contract(output_dir / CONTRACT_NAME, probe)
    write_figure(output_dir / FIGURE_NAME, probe)
    write_shapes_figure(output_dir / SHAPES_FIGURE_NAME)


def main() -> None:
    """Parse command-line arguments and run the experiment."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument("--fixture-dir", type=Path, default=Path("fixtures/wire-trimming-evaluation"))
    parser.add_argument("--platform-label", default="linux-x64-reference")
    parser.add_argument("--refresh-fixtures", action="store_true")
    arguments = parser.parse_args()
    run(arguments.output_dir, arguments.fixture_dir, refresh=arguments.refresh_fixtures, platform_label=arguments.platform_label)
    print(f"Wrote wire-trimming evaluation artifacts to {arguments.output_dir}")


if __name__ == "__main__":
    main()
