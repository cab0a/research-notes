"""Evaluate controlled face geometry before and after a STEP round trip."""

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

from research_notes.face_geometry import (  # noqa: E402
    FaceEvaluation,
    FaceGeometryProbe,
    analytic_face_truth,
    face_controls,
    probe_evaluated_face_geometry,
)


FIXTURE_NAME = "analytic_faces.step"
MANIFEST_NAME = "manifest.csv"
OBSERVATIONS_NAME = "evaluated_face_geometry_observations.csv"
SUMMARY_NAME = "evaluated_face_geometry_summary.csv"
CONTRACT_NAME = "evaluated_face_geometry.json"
FIGURE_NAME = "evaluated_face_geometry.png"

VECTOR_COLUMNS = (
    "centroid",
    "representative_point",
    "support_normal",
    "oriented_normal",
    "surface_origin",
    "surface_axis",
    "surface_x_direction",
)
OBSERVATION_FIELDS = (
    "platform_label",
    "stage",
    "face_id",
    "matched_by",
    "expected_surface_type",
    "observed_surface_type",
    "expected_orientation",
    "observed_orientation",
    "expected_area",
    "observed_area",
    "area_absolute_error",
    *(
        f"{prefix}_{axis}_{kind}"
        for prefix in VECTOR_COLUMNS
        for kind in ("expected", "observed")
        for axis in ("x", "y", "z")
    ),
    "centroid_distance",
    "representative_point_distance",
    "expected_u_min",
    "expected_u_max",
    "expected_v_min",
    "expected_v_max",
    "observed_u_min",
    "observed_u_max",
    "observed_v_min",
    "observed_v_max",
    "uv_max_absolute_error",
    "representative_u",
    "representative_v",
    "support_normal_angle_degrees",
    "oriented_normal_angle_degrees",
    "surface_origin_distance",
    "surface_axis_angle_degrees",
    "surface_x_direction_angle_degrees",
    "expected_radius",
    "observed_radius",
    "radius_absolute_error",
    "constructed_tolerance",
    "observed_face_tolerance",
    "tolerance_delta_from_constructed",
)
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
SUMMARY_FIELDS = ("scope", "metric", "value")


def _format_float(value: float | None) -> str:
    return "" if value is None else format(value, ".17g")


def _vector_fields(
    name: str, expected: tuple[float, float, float], observed: tuple[float, float, float]
) -> dict[str, str]:
    row: dict[str, str] = {}
    for kind, vector in (("expected", expected), ("observed", observed)):
        for axis, value in zip(("x", "y", "z"), vector, strict=True):
            row[f"{name}_{axis}_{kind}"] = _format_float(value)
    return row


def observation_row(
    evaluation: FaceEvaluation, platform_label: str
) -> dict[str, str]:
    """Flatten one matched analytic and backend face evaluation."""
    truth = evaluation.truth
    measured = evaluation.measurement
    row = {
        "platform_label": platform_label,
        "stage": measured.stage,
        "face_id": truth.face_id,
        "matched_by": evaluation.matched_by,
        "expected_surface_type": truth.surface_type,
        "observed_surface_type": measured.surface_type,
        "expected_orientation": truth.orientation,
        "observed_orientation": measured.orientation,
        "expected_area": _format_float(truth.area),
        "observed_area": _format_float(measured.area),
        "area_absolute_error": _format_float(evaluation.area_absolute_error),
        "centroid_distance": _format_float(evaluation.centroid_distance),
        "representative_point_distance": _format_float(
            evaluation.representative_point_distance
        ),
        "expected_u_min": _format_float(truth.uv_bounds[0]),
        "expected_u_max": _format_float(truth.uv_bounds[1]),
        "expected_v_min": _format_float(truth.uv_bounds[2]),
        "expected_v_max": _format_float(truth.uv_bounds[3]),
        "observed_u_min": _format_float(measured.uv_bounds[0]),
        "observed_u_max": _format_float(measured.uv_bounds[1]),
        "observed_v_min": _format_float(measured.uv_bounds[2]),
        "observed_v_max": _format_float(measured.uv_bounds[3]),
        "uv_max_absolute_error": _format_float(
            evaluation.uv_max_absolute_error
        ),
        "representative_u": _format_float(measured.representative_uv[0]),
        "representative_v": _format_float(measured.representative_uv[1]),
        "support_normal_angle_degrees": _format_float(
            evaluation.support_normal_angle_degrees
        ),
        "oriented_normal_angle_degrees": _format_float(
            evaluation.oriented_normal_angle_degrees
        ),
        "surface_origin_distance": _format_float(
            evaluation.surface_origin_distance
        ),
        "surface_axis_angle_degrees": _format_float(
            evaluation.surface_axis_angle_degrees
        ),
        "surface_x_direction_angle_degrees": _format_float(
            evaluation.surface_x_direction_angle_degrees
        ),
        "expected_radius": _format_float(truth.radius),
        "observed_radius": _format_float(measured.radius),
        "radius_absolute_error": _format_float(
            evaluation.radius_absolute_error
        ),
        "constructed_tolerance": _format_float(truth.constructed_tolerance),
        "observed_face_tolerance": _format_float(measured.face_tolerance),
        "tolerance_delta_from_constructed": _format_float(
            evaluation.tolerance_delta_from_constructed
        ),
    }
    for name in VECTOR_COLUMNS:
        row.update(
            _vector_fields(name, getattr(truth, name), getattr(measured, name))
        )
    return row


def write_csv(
    path: Path, rows: Sequence[dict[str, str]], fields: Sequence[str]
) -> None:
    """Write deterministic UTF-8 CSV evidence."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def manifest_row(probe: FaceGeometryProbe) -> dict[str, str]:
    """Describe the generated STEP fixture and runtime provenance."""
    return {
        "fixture": "analytic_faces",
        "file_name": FIXTURE_NAME,
        "source_bytes": str(len(probe.source_bytes)),
        "source_sha256": probe.source_sha256,
        "generator": "two bounded planes and one bounded cylinder from analytic controls",
        "binding_distribution_version": probe.binding_distribution_version,
        "binding_module_version": probe.binding_module_version,
        "step_processor": probe.step_processor,
    }


def handle_fixture(
    fixture_dir: Path, probe: FaceGeometryProbe, *, refresh: bool
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
        raise RuntimeError("missing committed face fixture; use --refresh-fixtures")
    if fixture_path.read_bytes() != probe.source_bytes:
        raise RuntimeError("committed face fixture differs from regenerated bytes")
    with manifest_path.open(encoding="utf-8", newline="") as handle:
        if list(csv.DictReader(handle)) != expected_manifest:
            raise RuntimeError("committed face fixture manifest differs")


def _max_error(
    evaluations: Sequence[FaceEvaluation], attribute: str, stage: str
) -> float:
    values = [
        getattr(item, attribute)
        for item in evaluations
        if item.measurement.stage == stage
    ]
    return max(float(value) for value in values if value is not None)


def summary_rows(probe: FaceGeometryProbe) -> list[dict[str, str]]:
    """Build compact geometry, orientation, tolerance, and exchange evidence."""
    rows = [
        {"scope": "fixture", "metric": "face_count", "value": "3"},
        {"scope": "fixture", "metric": "plane_count", "value": "2"},
        {"scope": "fixture", "metric": "cylinder_count", "value": "1"},
        {
            "scope": "fixture",
            "metric": "reversed_face_count",
            "value": "1",
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
        {
            "scope": "exchange",
            "metric": "orientation_matches",
            "value": str(
                sum(
                    item.truth.orientation == item.measurement.orientation
                    for item in probe.evaluations
                    if item.measurement.stage == "step_imported"
                )
            ),
        },
        {
            "scope": "exchange",
            "metric": "exported_uncertainty_unique_values",
            "value": "|".join(
                sorted({_format_float(value) for value in probe.exported_uncertainty_values})
            ),
        },
    ]
    for stage in ("constructed", "step_imported"):
        for metric in (
            "area_absolute_error",
            "centroid_distance",
            "uv_max_absolute_error",
            "representative_point_distance",
            "oriented_normal_angle_degrees",
            "surface_origin_distance",
            "surface_axis_angle_degrees",
            "radius_absolute_error",
        ):
            rows.append(
                {
                    "scope": stage,
                    "metric": f"max_{metric}",
                    "value": _format_float(
                        _max_error(probe.evaluations, metric, stage)
                    ),
                }
            )
        tolerances = [
            item.measurement.face_tolerance
            for item in probe.evaluations
            if item.measurement.stage == stage
        ]
        rows.extend(
            (
                {
                    "scope": stage,
                    "metric": "min_face_tolerance",
                    "value": _format_float(min(tolerances)),
                },
                {
                    "scope": stage,
                    "metric": "max_face_tolerance",
                    "value": _format_float(max(tolerances)),
                },
            )
        )
    return rows


def write_contract(path: Path, probe: FaceGeometryProbe) -> None:
    """Write a deterministic machine-readable evaluation and claim contract."""
    payload = {
        "schema": "research-notes.evaluated-face-geometry",
        "schema_version": "1.0",
        "release": "v0.32.0",
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
                    "reversed": control.reversed,
                    "constructed_tolerance": control.constructed_tolerance,
                }
                for control in face_controls()
            ],
        },
        "runtime": {
            "platform_label": probe.platform_label,
            "binding_distribution_version": probe.binding_distribution_version,
            "binding_module_version": probe.binding_module_version,
            "step_processor": probe.step_processor,
        },
        "truth_contract": [
            "Area, centroid, UV bounds, representative points, normals, and analytic parameters are derived from closed-form plane and cylinder equations without calling OCCT.",
            "Backend faces are matched by surface type and nearest analytic centroid rather than explorer order.",
            "Support-surface normals are derivative cross products; oriented face normals additionally apply the topological face orientation.",
            "Absolute error limits in tests verify this synthetic numeric contract and are not universal CAD quality thresholds.",
        ],
        "tolerance_contract": {
            "constructed_face_tolerances": [
                control.constructed_tolerance for control in face_controls()
            ],
            "exported_uncertainty_values": probe.exported_uncertainty_values,
            "imported_face_tolerances": [
                item.measurement.face_tolerance
                for item in probe.evaluations
                if item.measurement.stage == "step_imported"
            ],
            "claim": "Face tolerance is a backend state observed at each stage; STEP round-trip identity is not assumed.",
        },
        "open_questions": [
            "How should periodic UV intervals that cross the cylinder seam be canonicalized?",
            "How do per-face tolerances relate to representation uncertainty across other writers and readers?",
            "Which trim and p-curve checks are required before a representative normal can be trusted on arbitrary faces?",
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _surface_grid(face_id: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    control = next(item for item in face_controls() if item.face_id == face_id)
    u_min, u_max, v_min, v_max = control.uv_bounds
    u_values = np.linspace(u_min, u_max, 25)
    v_values = np.linspace(v_min, v_max, 25)
    u_grid, v_grid = np.meshgrid(u_values, v_values)
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


def write_figure(path: Path, probe: FaceGeometryProbe) -> None:
    """Visualize controls, numeric errors, and face-tolerance stage changes."""
    figure = plt.figure(figsize=(15.2, 5.3), constrained_layout=True)
    grid = figure.add_gridspec(1, 3, width_ratios=(1.35, 1.0, 1.0))

    geometry_axis = figure.add_subplot(grid[0, 0], projection="3d")
    colors = ("#2563eb", "#f59e0b", "#16a34a")
    for control, color in zip(face_controls(), colors, strict=True):
        x_grid, y_grid, z_grid = _surface_grid(control.face_id)
        geometry_axis.plot_surface(
            x_grid, y_grid, z_grid, color=color, alpha=0.55, linewidth=0
        )
        truth = analytic_face_truth(control)
        geometry_axis.scatter(*truth.centroid, color=color, s=25)
        geometry_axis.text(*truth.centroid, control.face_id.replace("_", "\n"), fontsize=7)
    geometry_axis.set_xlabel("X")
    geometry_axis.set_ylabel("Y")
    geometry_axis.set_zlabel("Z")
    geometry_axis.set_title("Analytic synthetic controls")
    geometry_axis.view_init(elev=23, azim=-58)

    error_axis = figure.add_subplot(grid[0, 1])
    metrics = (
        ("area_absolute_error", "Area"),
        ("centroid_distance", "Centroid"),
        ("uv_max_absolute_error", "UV bounds"),
        ("representative_point_distance", "Sample point"),
        ("radius_absolute_error", "Radius"),
    )
    positions = np.arange(len(metrics))
    width = 0.36
    for offset, stage, label, color in (
        (-width / 2, "constructed", "Constructed", "#2563eb"),
        (width / 2, "step_imported", "STEP imported", "#16a34a"),
    ):
        values = [
            max(_max_error(probe.evaluations, metric, stage), 1.0e-18)
            for metric, _ in metrics
        ]
        error_axis.bar(positions + offset, values, width, label=label, color=color)
    error_axis.set_yscale("log")
    error_axis.set_xticks(positions, [label for _, label in metrics], rotation=25)
    error_axis.set_ylabel("Maximum absolute error")
    error_axis.set_title("Closed-form truth comparison")
    error_axis.legend(fontsize=8)

    tolerance_axis = figure.add_subplot(grid[0, 2])
    x_positions = np.arange(len(face_controls()))
    constructed = [control.constructed_tolerance for control in face_controls()]
    imported = [
        next(
            item.measurement.face_tolerance
            for item in probe.evaluations
            if item.measurement.stage == "step_imported"
            and item.truth.face_id == control.face_id
        )
        for control in face_controls()
    ]
    tolerance_axis.bar(
        x_positions - width / 2,
        constructed,
        width,
        label="Constructed face",
        color="#f59e0b",
    )
    tolerance_axis.bar(
        x_positions + width / 2,
        imported,
        width,
        label="STEP imported face",
        color="#7c3aed",
    )
    tolerance_axis.axhline(
        probe.exported_uncertainty_values[0],
        color="#dc2626",
        linestyle="--",
        linewidth=1.2,
        label="STEP uncertainty",
    )
    tolerance_axis.set_yscale("log")
    tolerance_axis.set_xticks(
        x_positions,
        [control.face_id.replace("_", "\n") for control in face_controls()],
        fontsize=8,
    )
    tolerance_axis.set_ylabel("Length tolerance")
    tolerance_axis.set_title("Tolerance is stage-dependent")
    tolerance_axis.legend(fontsize=8)

    figure.suptitle("v0.32.0 Evaluated Face Geometry and Tolerances")
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
    """Run the complete v0.32 controlled face-geometry experiment."""
    probe = probe_evaluated_face_geometry(platform_label=platform_label)
    handle_fixture(fixture_dir, probe, refresh=refresh)
    rows = [
        observation_row(item, probe.platform_label) for item in probe.evaluations
    ]
    write_csv(output_dir / OBSERVATIONS_NAME, rows, OBSERVATION_FIELDS)
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
        default=Path("fixtures/evaluated-face-geometry"),
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
    print(f"Wrote evaluated face-geometry artifacts to {arguments.output_dir}")


if __name__ == "__main__":
    main()
