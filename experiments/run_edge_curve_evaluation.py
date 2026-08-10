"""Evaluate controlled 3D curves, p-curves, parameters, and seams."""

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

from research_notes.edge_geometry import (  # noqa: E402
    EdgeCurveObservation,
    EdgeGeometryProbe,
    PCurveObservation,
    edge_face_controls,
    probe_edge_geometry,
)


FIXTURE_NAME = "analytic_edge_faces.step"
MANIFEST_NAME = "manifest.csv"
EDGE_OBSERVATIONS_NAME = "edge_curve_observations.csv"
PCURVE_OBSERVATIONS_NAME = "pcurve_observations.csv"
SUMMARY_NAME = "edge_curve_summary.csv"
CONTRACT_NAME = "edge_curve_contract.json"
FIGURE_NAME = "edge_curve_evaluation.png"

EDGE_FIELDS = (
    "platform_label",
    "stage",
    "face_id",
    "edge_index",
    "boundary_roles",
    "expected_curve_type",
    "observed_curve_type",
    "expected_length",
    "observed_length",
    "length_absolute_error",
    "expected_parameter_span",
    "parameter_first",
    "parameter_last",
    "parameter_span",
    "parameter_span_absolute_error",
    "same_parameter_flag",
    "same_range_flag",
    "degenerated",
    "expected_is_seam",
    "observed_is_seam",
    "wire_occurrence_count",
    "pcurve_branch_count",
    "edge_tolerance",
    "max_pcurve_to_curve_distance",
)
PCURVE_FIELDS = (
    "platform_label",
    "stage",
    "face_id",
    "edge_index",
    "wire_use_index",
    "boundary_role",
    "orientation",
    "pcurve_type",
    "parameter_first",
    "parameter_last",
    "vertex_start_parameter",
    "vertex_end_parameter",
    "uv_start_u",
    "uv_start_v",
    "uv_mid_u",
    "uv_mid_v",
    "uv_end_u",
    "uv_end_v",
    "uv_max_absolute_error",
    "range_alignment_error",
    "max_pcurve_to_curve_distance",
    "sample_count",
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


def _format_float(value: float) -> str:
    return format(value, ".17g")


def edge_row(
    observation: EdgeCurveObservation, platform_label: str
) -> dict[str, str]:
    """Flatten one unique-edge observation for deterministic CSV output."""
    return {
        "platform_label": platform_label,
        "stage": observation.stage,
        "face_id": observation.face_id,
        "edge_index": str(observation.edge_index),
        "boundary_roles": "|".join(observation.boundary_roles),
        "expected_curve_type": observation.expected_curve_type,
        "observed_curve_type": observation.observed_curve_type,
        "expected_length": _format_float(observation.expected_length),
        "observed_length": _format_float(observation.observed_length),
        "length_absolute_error": _format_float(observation.length_absolute_error),
        "expected_parameter_span": _format_float(
            observation.expected_parameter_span
        ),
        "parameter_first": _format_float(observation.parameter_first),
        "parameter_last": _format_float(observation.parameter_last),
        "parameter_span": _format_float(observation.parameter_span),
        "parameter_span_absolute_error": _format_float(
            observation.parameter_span_absolute_error
        ),
        "same_parameter_flag": str(int(observation.same_parameter_flag)),
        "same_range_flag": str(int(observation.same_range_flag)),
        "degenerated": str(int(observation.degenerated)),
        "expected_is_seam": str(int(observation.expected_is_seam)),
        "observed_is_seam": str(int(observation.observed_is_seam)),
        "wire_occurrence_count": str(observation.wire_occurrence_count),
        "pcurve_branch_count": str(observation.pcurve_branch_count),
        "edge_tolerance": _format_float(observation.edge_tolerance),
        "max_pcurve_to_curve_distance": _format_float(
            observation.max_pcurve_to_curve_distance
        ),
    }


def pcurve_row(
    observation: PCurveObservation, platform_label: str
) -> dict[str, str]:
    """Flatten one oriented p-curve observation for deterministic CSV output."""
    return {
        "platform_label": platform_label,
        "stage": observation.stage,
        "face_id": observation.face_id,
        "edge_index": str(observation.edge_index),
        "wire_use_index": str(observation.wire_use_index),
        "boundary_role": observation.boundary_role,
        "orientation": observation.orientation,
        "pcurve_type": observation.pcurve_type,
        "parameter_first": _format_float(observation.parameter_first),
        "parameter_last": _format_float(observation.parameter_last),
        "vertex_start_parameter": _format_float(
            observation.vertex_start_parameter
        ),
        "vertex_end_parameter": _format_float(observation.vertex_end_parameter),
        "uv_start_u": _format_float(observation.uv_start[0]),
        "uv_start_v": _format_float(observation.uv_start[1]),
        "uv_mid_u": _format_float(observation.uv_mid[0]),
        "uv_mid_v": _format_float(observation.uv_mid[1]),
        "uv_end_u": _format_float(observation.uv_end[0]),
        "uv_end_v": _format_float(observation.uv_end[1]),
        "uv_max_absolute_error": _format_float(
            observation.uv_max_absolute_error
        ),
        "range_alignment_error": _format_float(
            observation.range_alignment_error
        ),
        "max_pcurve_to_curve_distance": _format_float(
            observation.max_pcurve_to_curve_distance
        ),
        "sample_count": str(observation.sample_count),
    }


def write_csv(
    path: Path, rows: Sequence[dict[str, str]], fields: Sequence[str]
) -> None:
    """Write deterministic UTF-8 CSV evidence."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def manifest_row(probe: EdgeGeometryProbe) -> dict[str, str]:
    """Describe the generated STEP fixture and runtime provenance."""
    return {
        "fixture": "analytic_edge_faces",
        "file_name": FIXTURE_NAME,
        "source_bytes": str(len(probe.source_bytes)),
        "source_sha256": probe.source_sha256,
        "generator": "one bounded plane, one partial cylinder, and one closed cylindrical lateral face",
        "binding_distribution_version": probe.binding_distribution_version,
        "binding_module_version": probe.binding_module_version,
        "step_processor": probe.step_processor,
    }


def handle_fixture(
    fixture_dir: Path, probe: EdgeGeometryProbe, *, refresh: bool
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
        raise RuntimeError("missing committed edge fixture; use --refresh-fixtures")
    if fixture_path.read_bytes() != probe.source_bytes:
        raise RuntimeError("committed edge fixture differs from regenerated bytes")
    with manifest_path.open(encoding="utf-8", newline="") as handle:
        if list(csv.DictReader(handle)) != expected_manifest:
            raise RuntimeError("committed edge fixture manifest differs")


def _stage_edges(
    probe: EdgeGeometryProbe, stage: str
) -> list[EdgeCurveObservation]:
    return [item for item in probe.edge_observations if item.stage == stage]


def _stage_pcurves(
    probe: EdgeGeometryProbe, stage: str
) -> list[PCurveObservation]:
    return [item for item in probe.pcurve_observations if item.stage == stage]


def summary_rows(probe: EdgeGeometryProbe) -> list[dict[str, str]]:
    """Build compact topology, geometry, parameter, and exchange evidence."""
    rows = [
        {"scope": "fixture", "metric": "face_count", "value": "3"},
        {"scope": "fixture", "metric": "unique_edge_count", "value": "11"},
        {"scope": "fixture", "metric": "wire_occurrence_count", "value": "12"},
        {"scope": "fixture", "metric": "line_edge_count", "value": "7"},
        {"scope": "fixture", "metric": "circle_edge_count", "value": "4"},
        {"scope": "fixture", "metric": "seam_edge_count", "value": "1"},
        {
            "scope": "exchange",
            "metric": "step_edge_curve_count",
            "value": str(probe.step_edge_curve_count),
        },
        {
            "scope": "exchange",
            "metric": "step_surface_curve_count",
            "value": str(probe.step_surface_curve_count),
        },
        {
            "scope": "exchange",
            "metric": "step_pcurve_count",
            "value": str(probe.step_pcurve_count),
        },
        {
            "scope": "exchange",
            "metric": "step_seam_curve_count",
            "value": str(probe.step_seam_curve_count),
        },
        {
            "scope": "exchange",
            "metric": "constructed_valid",
            "value": str(int(probe.constructed_valid)),
        },
        {
            "scope": "exchange",
            "metric": "imported_valid",
            "value": str(int(probe.imported_valid)),
        },
    ]
    for stage in ("constructed", "step_imported"):
        edges = _stage_edges(probe, stage)
        pcurves = _stage_pcurves(probe, stage)
        rows.extend(
            (
                {
                    "scope": stage,
                    "metric": "curve_type_match_count",
                    "value": str(
                        sum(
                            item.expected_curve_type == item.observed_curve_type
                            for item in edges
                        )
                    ),
                },
                {
                    "scope": stage,
                    "metric": "same_parameter_true_count",
                    "value": str(sum(item.same_parameter_flag for item in edges)),
                },
                {
                    "scope": stage,
                    "metric": "same_range_true_count",
                    "value": str(sum(item.same_range_flag for item in edges)),
                },
                {
                    "scope": stage,
                    "metric": "max_length_absolute_error",
                    "value": _format_float(
                        max(item.length_absolute_error for item in edges)
                    ),
                },
                {
                    "scope": stage,
                    "metric": "max_parameter_span_absolute_error",
                    "value": _format_float(
                        max(item.parameter_span_absolute_error for item in edges)
                    ),
                },
                {
                    "scope": stage,
                    "metric": "max_uv_absolute_error",
                    "value": _format_float(
                        max(item.uv_max_absolute_error for item in pcurves)
                    ),
                },
                {
                    "scope": stage,
                    "metric": "max_range_alignment_error",
                    "value": _format_float(
                        max(item.range_alignment_error for item in pcurves)
                    ),
                },
                {
                    "scope": stage,
                    "metric": "max_pcurve_to_curve_distance",
                    "value": _format_float(
                        max(item.max_pcurve_to_curve_distance for item in pcurves)
                    ),
                },
                {
                    "scope": stage,
                    "metric": "min_edge_tolerance",
                    "value": _format_float(min(item.edge_tolerance for item in edges)),
                },
                {
                    "scope": stage,
                    "metric": "max_edge_tolerance",
                    "value": _format_float(max(item.edge_tolerance for item in edges)),
                },
            )
        )
    return rows


def write_contract(path: Path, probe: EdgeGeometryProbe) -> None:
    """Write the machine-readable scope, evidence, and claim boundaries."""
    payload = {
        "schema": "research-notes.edge-curve-evaluation",
        "schema_version": "1.0",
        "release": "v0.33.0",
        "fixture": {
            "file": FIXTURE_NAME,
            "sha256": probe.source_sha256,
            "faces": [
                {
                    "face_id": control.face_id,
                    "surface_type": control.surface_type,
                    "origin": control.origin,
                    "axis": control.axis,
                    "x_direction": control.x_direction,
                    "uv_bounds": control.uv_bounds,
                    "radius": control.radius,
                    "constructed_edge_tolerance": control.constructed_edge_tolerance,
                }
                for control in edge_face_controls()
            ],
        },
        "runtime": {
            "platform_label": probe.platform_label,
            "binding_distribution_version": probe.binding_distribution_version,
            "binding_module_version": probe.binding_module_version,
            "step_processor": probe.step_processor,
        },
        "sampling": {
            "samples_per_pcurve": 17,
            "rule": "equally spaced in the shared three-dimensional curve range",
        },
        "truth_contract": [
            "Boundary curve type, length, parameter span, and UV path are derived from plane and cylinder equations without calling OCCT.",
            "A circular parameter span is angular and is deliberately reported separately from arc length.",
            "A seam is expected only where the full cylindrical face uses one topological edge at both periodic U boundaries.",
            "Topological vertex order is reported separately from the ascending geometric curve range.",
            "SameParameter and SameRange are flags; sampled three-dimensional residuals provide separate controlled evidence.",
        ],
        "claim_boundaries": [
            "Observed numerical limits validate only these analytic fixtures and this pinned backend.",
            "A p-curve returned for a planar face is not proof that the p-curve was stored because OCCT may generate one on demand.",
            "The experiment observes but does not repair missing curves, inconsistent flags, or excessive tolerances.",
            "Degenerate edges, singular surfaces, inner wires, spline curves, and cross-kernel behavior are outside this release.",
        ],
        "open_questions": [
            "How should stored and generated-on-demand p-curves be distinguished through the Python binding?",
            "Which checks should precede any SameParameter or tolerance repair decision?",
            "How should degenerate edges at surface singularities participate in wire traversal?",
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _surface_grid(control_index: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    control = edge_face_controls()[control_index]
    u_min, u_max, v_min, v_max = control.uv_bounds
    u_grid, v_grid = np.meshgrid(
        np.linspace(u_min, u_max, 35), np.linspace(v_min, v_max, 24)
    )
    origin = np.asarray(control.origin)[:, None, None]
    axis = np.asarray(control.axis)[:, None, None]
    x_direction = np.asarray(control.x_direction)[:, None, None]
    y_direction = np.cross(np.asarray(control.axis), np.asarray(control.x_direction))[
        :, None, None
    ]
    if control.surface_type == "plane":
        points = origin + x_direction * u_grid + y_direction * v_grid
    else:
        radial = x_direction * np.cos(u_grid) + y_direction * np.sin(u_grid)
        points = origin + float(control.radius) * radial + axis * v_grid
    return points[0], points[1], points[2]


def _boundary_points(control_index: int, role: str) -> np.ndarray:
    control = edge_face_controls()[control_index]
    u_min, u_max, v_min, v_max = control.uv_bounds
    if role == "u_min":
        u_values = np.full(80, u_min)
        v_values = np.linspace(v_min, v_max, 80)
    elif role == "u_max":
        u_values = np.full(80, u_max)
        v_values = np.linspace(v_min, v_max, 80)
    elif role == "v_min":
        u_values = np.linspace(u_min, u_max, 80)
        v_values = np.full(80, v_min)
    else:
        u_values = np.linspace(u_min, u_max, 80)
        v_values = np.full(80, v_max)
    origin = np.asarray(control.origin)[:, None]
    axis = np.asarray(control.axis)[:, None]
    x_direction = np.asarray(control.x_direction)[:, None]
    y_direction = np.cross(np.asarray(control.axis), np.asarray(control.x_direction))[
        :, None
    ]
    if control.surface_type == "plane":
        return origin + x_direction * u_values + y_direction * v_values
    radial = x_direction * np.cos(u_values) + y_direction * np.sin(u_values)
    return origin + float(control.radius) * radial + axis * v_values


def write_figure(path: Path, probe: EdgeGeometryProbe) -> None:
    """Visualize the controls, periodic UV seam, and numerical evidence."""
    figure = plt.figure(figsize=(15.5, 5.3), constrained_layout=True)
    grid = figure.add_gridspec(1, 3, width_ratios=(1.25, 1.0, 1.0))

    geometry_axis = figure.add_subplot(grid[0, 0], projection="3d")
    surface_colors = ("#93c5fd", "#86efac", "#fcd34d")
    for index, (control, color) in enumerate(
        zip(edge_face_controls(), surface_colors, strict=True)
    ):
        x_grid, y_grid, z_grid = _surface_grid(index)
        geometry_axis.plot_surface(
            x_grid, y_grid, z_grid, color=color, alpha=0.48, linewidth=0
        )
        for role in ("u_min", "u_max", "v_min", "v_max"):
            points = _boundary_points(index, role)
            is_seam = control.face_id == "closed_cylinder" and role.startswith("u_")
            geometry_axis.plot(
                points[0],
                points[1],
                points[2],
                color="#dc2626" if is_seam else "#1f2937",
                linewidth=2.5 if is_seam else 1.2,
            )
        geometry_axis.text(*control.origin, control.face_id.replace("_", "\n"), fontsize=7)
    geometry_axis.set_xlabel("X")
    geometry_axis.set_ylabel("Y")
    geometry_axis.set_zlabel("Z")
    geometry_axis.set_title("Analytic boundary controls")
    geometry_axis.view_init(elev=22, azim=-57)

    uv_axis = figure.add_subplot(grid[0, 1])
    imported = [
        item
        for item in probe.pcurve_observations
        if item.stage == "step_imported" and item.face_id == "closed_cylinder"
    ]
    colors = {"u_min": "#dc2626", "u_max": "#7c3aed", "v_min": "#2563eb", "v_max": "#16a34a"}
    for item in imported:
        uv_axis.plot(
            [item.uv_start[0], item.uv_mid[0], item.uv_end[0]],
            [item.uv_start[1], item.uv_mid[1], item.uv_end[1]],
            marker="o",
            color=colors[item.boundary_role],
            label=f"{item.boundary_role} ({item.orientation})",
        )
    uv_axis.set_xlim(-0.35, 2.0 * math.pi + 0.35)
    uv_axis.set_ylim(-0.25, 4.25)
    uv_axis.set_xlabel("U parameter")
    uv_axis.set_ylabel("V parameter")
    uv_axis.set_title("One seam edge, two p-curve branches")
    uv_axis.legend(fontsize=7, loc="center")
    uv_axis.grid(alpha=0.25)

    error_axis = figure.add_subplot(grid[0, 2])
    labels = ("Length", "Parameter span", "UV path", "3D↔surface")
    width = 0.36
    x_positions = np.arange(len(labels))
    for offset, stage, label, color in (
        (-width / 2, "constructed", "Constructed", "#2563eb"),
        (width / 2, "step_imported", "STEP imported", "#f59e0b"),
    ):
        edges = _stage_edges(probe, stage)
        pcurves = _stage_pcurves(probe, stage)
        values = (
            max(item.length_absolute_error for item in edges),
            max(item.parameter_span_absolute_error for item in edges),
            max(item.uv_max_absolute_error for item in pcurves),
            max(item.max_pcurve_to_curve_distance for item in pcurves),
        )
        error_axis.bar(
            x_positions + offset,
            [max(value, 1.0e-18) for value in values],
            width,
            label=label,
            color=color,
        )
    error_axis.set_yscale("log")
    error_axis.set_xticks(x_positions, labels, rotation=22)
    error_axis.set_ylabel("Maximum absolute error or distance")
    error_axis.set_title("Closed-form and consistency checks")
    error_axis.legend(fontsize=8)

    figure.suptitle("v0.33.0 Curves, Edge Parameters, P-Curves, and Seams")
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160)
    plt.close(figure)


def run(
    output_dir: Path,
    fixture_dir: Path,
    *,
    refresh: bool,
    platform_label: str,
) -> None:
    """Run the complete v0.33 controlled edge-geometry experiment."""
    probe = probe_edge_geometry(platform_label=platform_label)
    handle_fixture(fixture_dir, probe, refresh=refresh)
    write_csv(
        output_dir / EDGE_OBSERVATIONS_NAME,
        [edge_row(item, probe.platform_label) for item in probe.edge_observations],
        EDGE_FIELDS,
    )
    write_csv(
        output_dir / PCURVE_OBSERVATIONS_NAME,
        [pcurve_row(item, probe.platform_label) for item in probe.pcurve_observations],
        PCURVE_FIELDS,
    )
    write_csv(output_dir / SUMMARY_NAME, summary_rows(probe), SUMMARY_FIELDS)
    write_contract(output_dir / CONTRACT_NAME, probe)
    write_figure(output_dir / FIGURE_NAME, probe)


def main() -> None:
    """Parse command-line arguments and run the controlled experiment."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=Path("fixtures/edge-curve-evaluation"),
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
    print(f"Wrote edge-curve evaluation artifacts to {arguments.output_dir}")


if __name__ == "__main__":
    main()
