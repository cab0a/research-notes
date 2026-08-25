"""Generate tessellation and visual-diagnostic evidence for controlled STEP shapes."""

from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402

from research_notes.tessellation_diagnostics import (  # noqa: E402
    CONTRACT_VERSION,
    MeshCondition,
    TessellationFaceObservation,
    TessellationProbe,
    TessellationTriangle,
    probe_tessellation_diagnostics,
)


TRIANGLE_NAME = "tessellation_triangles.csv"
FACE_NAME = "tessellation_face_summary.csv"
SUMMARY_NAME = "tessellation_summary.csv"
CONTRACT_NAME = "tessellation_contract.json"
FIGURE_NAME = "tessellation_diagnostics.png"
VISUAL_NAME = "tessellation_visual_diagnostics.png"
MANIFEST_NAME = "manifest.csv"

TRIANGLE_FIELDS = (
    "contract_version",
    "control_id",
    "source_file",
    "source_sha256",
    "mesh_condition",
    "requested_linear_deflection",
    "requested_angular_deflection_radians",
    "relative_deflection",
    "parallel_meshing",
    "mesher_status_flags",
    "analysis_face_index",
    "source_entity_id",
    "source_entity_type",
    "source_mapping_method",
    "surface_type",
    "face_orientation",
    "analysis_triangle_index",
    "node_index_1",
    "node_index_2",
    "node_index_3",
    "vertex_1_x",
    "vertex_1_y",
    "vertex_1_z",
    "vertex_2_x",
    "vertex_2_y",
    "vertex_2_z",
    "vertex_3_x",
    "vertex_3_y",
    "vertex_3_z",
    "uv_1_u",
    "uv_1_v",
    "uv_2_u",
    "uv_2_v",
    "uv_3_u",
    "uv_3_v",
    "centroid_x",
    "centroid_y",
    "centroid_z",
    "oriented_normal_x",
    "oriented_normal_y",
    "oriented_normal_z",
    "triangle_area",
    "is_degenerate",
    "barycentric_u",
    "barycentric_v",
    "sampled_surface_x",
    "sampled_surface_y",
    "sampled_surface_z",
    "sampled_surface_deviation",
)

FACE_FIELDS = (
    "contract_version",
    "control_id",
    "source_file",
    "source_sha256",
    "mesh_condition",
    "requested_linear_deflection",
    "requested_angular_deflection_radians",
    "relative_deflection",
    "parallel_meshing",
    "mesher_status_flags",
    "analysis_face_index",
    "source_entity_id",
    "source_entity_type",
    "source_mapping_method",
    "surface_type",
    "face_orientation",
    "node_count",
    "triangle_count",
    "degenerate_triangle_count",
    "has_uv_nodes",
    "has_normals",
    "stored_deflection",
    "exact_surface_area",
    "mesh_surface_area",
    "signed_area_difference",
    "absolute_area_difference",
    "relative_area_difference",
    "maximum_sampled_surface_deviation",
    "mean_sampled_surface_deviation",
)

SUMMARY_FIELDS = (
    "control_id",
    "mesh_condition",
    "requested_linear_deflection",
    "requested_angular_deflection_radians",
    "face_count",
    "source_mapped_face_count",
    "face_local_node_reference_count",
    "triangle_count",
    "degenerate_triangle_count",
    "exact_surface_area",
    "mesh_surface_area",
    "signed_area_difference",
    "absolute_area_difference",
    "relative_area_difference",
    "maximum_sampled_surface_deviation",
    "mean_sampled_surface_deviation",
)


def _float(value: float | None) -> str:
    return "" if value is None else format(value, ".17g")


def _boolean(value: bool) -> str:
    return str(int(value))


def _vector_fields(
    prefix: str, value: tuple[float, float, float] | None
) -> dict[str, str]:
    vector = (None, None, None) if value is None else value
    return {
        f"{prefix}_{axis}": _float(component)
        for axis, component in zip(("x", "y", "z"), vector, strict=True)
    }


def triangle_row(item: TessellationTriangle) -> dict[str, str]:
    """Flatten one triangle into the stable v1 observation contract."""
    row = {
        "contract_version": item.contract_version,
        "control_id": item.control_id,
        "source_file": item.source_file,
        "source_sha256": item.source_sha256,
        "mesh_condition": item.mesh_condition,
        "requested_linear_deflection": _float(item.requested_linear_deflection),
        "requested_angular_deflection_radians": _float(
            item.requested_angular_deflection_radians
        ),
        "relative_deflection": _boolean(item.relative_deflection),
        "parallel_meshing": _boolean(item.parallel_meshing),
        "mesher_status_flags": str(item.mesher_status_flags),
        "analysis_face_index": str(item.analysis_face_index),
        "source_entity_id": item.source_entity_id or "",
        "source_entity_type": item.source_entity_type or "",
        "source_mapping_method": item.source_mapping_method,
        "surface_type": item.surface_type,
        "face_orientation": item.face_orientation,
        "analysis_triangle_index": str(item.analysis_triangle_index),
        "node_index_1": str(item.node_indices[0]),
        "node_index_2": str(item.node_indices[1]),
        "node_index_3": str(item.node_indices[2]),
        "triangle_area": _float(item.area),
        "is_degenerate": _boolean(item.is_degenerate),
        "barycentric_u": "" if item.barycentric_uv is None else _float(item.barycentric_uv[0]),
        "barycentric_v": "" if item.barycentric_uv is None else _float(item.barycentric_uv[1]),
        "sampled_surface_deviation": _float(item.sampled_surface_deviation),
    }
    for index, vertex in enumerate(item.vertices, start=1):
        row.update(_vector_fields(f"vertex_{index}", vertex))
    if item.uv_nodes is None:
        for index in range(1, 4):
            row[f"uv_{index}_u"] = ""
            row[f"uv_{index}_v"] = ""
    else:
        for index, uv_node in enumerate(item.uv_nodes, start=1):
            row[f"uv_{index}_u"] = _float(uv_node[0])
            row[f"uv_{index}_v"] = _float(uv_node[1])
    row.update(_vector_fields("centroid", item.centroid))
    row.update(_vector_fields("oriented_normal", item.oriented_normal))
    row.update(_vector_fields("sampled_surface", item.sampled_surface_point))
    if set(row) != set(TRIANGLE_FIELDS):
        raise RuntimeError("triangle serialization no longer matches its contract")
    return row


def face_row(item: TessellationFaceObservation) -> dict[str, str]:
    """Flatten one face-level tessellation observation."""
    row = {
        "contract_version": item.contract_version,
        "control_id": item.control_id,
        "source_file": item.source_file,
        "source_sha256": item.source_sha256,
        "mesh_condition": item.mesh_condition,
        "requested_linear_deflection": _float(item.requested_linear_deflection),
        "requested_angular_deflection_radians": _float(
            item.requested_angular_deflection_radians
        ),
        "relative_deflection": _boolean(item.relative_deflection),
        "parallel_meshing": _boolean(item.parallel_meshing),
        "mesher_status_flags": str(item.mesher_status_flags),
        "analysis_face_index": str(item.analysis_face_index),
        "source_entity_id": item.source_entity_id or "",
        "source_entity_type": item.source_entity_type or "",
        "source_mapping_method": item.source_mapping_method,
        "surface_type": item.surface_type,
        "face_orientation": item.face_orientation,
        "node_count": str(item.node_count),
        "triangle_count": str(item.triangle_count),
        "degenerate_triangle_count": str(item.degenerate_triangle_count),
        "has_uv_nodes": _boolean(item.has_uv_nodes),
        "has_normals": _boolean(item.has_normals),
        "stored_deflection": _float(item.stored_deflection),
        "exact_surface_area": _float(item.exact_surface_area),
        "mesh_surface_area": _float(item.mesh_surface_area),
        "signed_area_difference": _float(item.signed_area_difference),
        "absolute_area_difference": _float(item.absolute_area_difference),
        "relative_area_difference": _float(item.relative_area_difference),
        "maximum_sampled_surface_deviation": _float(
            item.maximum_sampled_surface_deviation
        ),
        "mean_sampled_surface_deviation": _float(
            item.mean_sampled_surface_deviation
        ),
    }
    if tuple(row) != FACE_FIELDS:
        raise RuntimeError("face serialization no longer matches its contract")
    return row


def summary_rows(probe: TessellationProbe) -> list[dict[str, str]]:
    """Aggregate face and triangle observations by control and condition."""
    rows: list[dict[str, str]] = []
    for control in probe.controls:
        for condition in probe.conditions:
            faces = [
                item
                for item in probe.faces
                if item.control_id == control.control_id
                and item.mesh_condition == condition.condition_id
            ]
            triangles = [
                item
                for item in probe.triangles
                if item.control_id == control.control_id
                and item.mesh_condition == condition.condition_id
            ]
            exact_area = sum(item.exact_surface_area for item in faces)
            mesh_area = sum(item.mesh_surface_area for item in faces)
            signed_difference = mesh_area - exact_area
            deviations = [
                item.sampled_surface_deviation
                for item in triangles
                if item.sampled_surface_deviation is not None
            ]
            rows.append(
                {
                    "control_id": control.control_id,
                    "mesh_condition": condition.condition_id,
                    "requested_linear_deflection": _float(
                        condition.linear_deflection
                    ),
                    "requested_angular_deflection_radians": _float(
                        condition.angular_deflection_radians
                    ),
                    "face_count": str(len(faces)),
                    "source_mapped_face_count": str(
                        sum(item.source_entity_id is not None for item in faces)
                    ),
                    "face_local_node_reference_count": str(
                        sum(item.node_count for item in faces)
                    ),
                    "triangle_count": str(len(triangles)),
                    "degenerate_triangle_count": str(
                        sum(item.is_degenerate for item in triangles)
                    ),
                    "exact_surface_area": _float(exact_area),
                    "mesh_surface_area": _float(mesh_area),
                    "signed_area_difference": _float(signed_difference),
                    "absolute_area_difference": _float(abs(signed_difference)),
                    "relative_area_difference": _float(
                        abs(signed_difference) / exact_area
                    ),
                    "maximum_sampled_surface_deviation": _float(
                        max(deviations, default=None)
                    ),
                    "mean_sampled_surface_deviation": _float(
                        None if not deviations else sum(deviations) / len(deviations)
                    ),
                }
            )
    return rows


def _csv_bytes(rows: list[dict[str, str]], fields: tuple[str, ...]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _write_csv(
    path: Path, rows: list[dict[str, str]], fields: tuple[str, ...]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_csv_bytes(rows, fields))


def _fixture_manifest(probe: TessellationProbe) -> bytes:
    rows = [
        {
            "control_id": item.fixture_id,
            "file_name": item.file_name,
            "source_bytes": str(len(item.source_bytes)),
            "source_sha256": item.source_sha256,
            "generator": "experiments/run_tessellation_diagnostics.py",
            "binding_distribution_version": probe.binding_distribution_version,
            "step_processor": item.step_processor,
            "writer_status": item.writer_status,
            "reader_status": item.reader_status,
            "transferred_roots": str(item.transferred_roots),
        }
        for item in probe.fixtures
    ]
    return _csv_bytes(rows, tuple(rows[0]))


def handle_fixtures(path: Path, probe: TessellationProbe, *, refresh: bool) -> None:
    """Write or byte-verify normalized STEP fixtures and their manifest."""
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
            raise RuntimeError(
                f"fixture differs; rerun with --refresh-fixtures: {target}"
            )


def write_contract(path: Path, probe: TessellationProbe) -> None:
    """Write the machine-readable row, provenance, and interpretation contract."""
    payload = {
        "contract_version": CONTRACT_VERSION,
        "study_version": "v0.42.0",
        "title": "Tessellation and Visual Diagnostic Contracts",
        "conditions": [
            {
                "condition_id": item.condition_id,
                "linear_deflection": item.linear_deflection,
                "angular_deflection_radians": item.angular_deflection_radians,
                "relative_deflection": False,
                "parallel_meshing": False,
            }
            for item in probe.conditions
        ],
        "triangle_csv": {
            "file": TRIANGLE_NAME,
            "encoding": "UTF-8",
            "delimiter": ",",
            "line_ending": "LF",
            "row_unit": "one face-local triangle under one control and mesh condition",
            "primary_key": [
                "control_id",
                "mesh_condition",
                "analysis_face_index",
                "analysis_triangle_index",
            ],
            "ordered_fields": list(TRIANGLE_FIELDS),
            "nullable_fields": [
                "source_entity_id",
                "source_entity_type",
                "uv_1_u",
                "uv_1_v",
                "uv_2_u",
                "uv_2_v",
                "uv_3_u",
                "uv_3_v",
                "oriented_normal_x",
                "oriented_normal_y",
                "oriented_normal_z",
                "barycentric_u",
                "barycentric_v",
                "sampled_surface_x",
                "sampled_surface_y",
                "sampled_surface_z",
                "sampled_surface_deviation",
            ],
        },
        "face_csv": {
            "file": FACE_NAME,
            "row_unit": "one analysis-local face under one control and mesh condition",
            "primary_key": [
                "control_id",
                "mesh_condition",
                "analysis_face_index",
            ],
            "ordered_fields": list(FACE_FIELDS),
        },
        "summary_csv": {
            "file": SUMMARY_NAME,
            "row_unit": "one control and mesh condition",
            "primary_key": ["control_id", "mesh_condition"],
            "ordered_fields": list(SUMMARY_FIELDS),
        },
        "units": {
            "requested_linear_deflection": "model units",
            "requested_angular_deflection_radians": "radians",
            "stored_deflection": "model units",
            "triangle_area": "squared model units",
            "surface_area": "squared model units",
            "sampled_surface_deviation": "model units",
            "uv": "surface-parameter units",
        },
        "source_entity_mapping": {
            "method": probe.source_references[0].mapping_method,
            "scope": "direct OCCT STEP transfer history for each controlled imported face",
            "source_identity": "Part 21 instance label verified against normalized fixture bytes",
            "persistent_identity": False,
        },
        "triangle_geometry": {
            "node_coordinates": "face triangulation nodes transformed by the returned TopLoc_Location",
            "normal": "normalized triangle cross product reversed for a reversed face; blank for zero-area triangles",
            "sampled_surface_deviation": "distance between the triangle centroid and exact surface point at mean vertex UV",
            "sample_is_bound": False,
        },
        "fixture_sha256": {
            item.file_name: item.source_sha256 for item in probe.fixtures
        },
        "claim_boundaries": [
            "requested meshing controls are inputs, not independently certified maximum errors",
            "one barycentric UV sample per triangle is diagnostic evidence, not a bound over the triangle",
            "triangle area is an approximation and can lie above or below exact B-Rep surface area",
            "zero-area pole triangles are retained and have no geometric normal",
            "face, node, and triangle indices are local to one decoded shape and mesh condition",
            "STEP source-entity provenance does not provide persistent identity after editing or re-export",
            "the visual preview is not geometric truth",
            "the controlled corpus is not general STEP, meshing, or rendering conformance evidence",
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _condition_labels(conditions: tuple[MeshCondition, ...]) -> list[str]:
    labels = {
        "coarse_both": "Coarse both",
        "fine_angular": "Fine angular",
        "fine_linear": "Fine linear",
        "fine_both": "Fine both",
    }
    return [labels[item.condition_id] for item in conditions]


def write_figure(path: Path, probe: TessellationProbe) -> None:
    """Plot mesh density and two non-certifying approximation diagnostics."""
    summaries = summary_rows(probe)
    figure, axes = plt.subplots(1, 3, figsize=(14.2, 4.8), constrained_layout=True)
    labels = _condition_labels(probe.conditions)
    colors = ("#2563eb", "#dc2626", "#0f766e")
    names = {
        "meshing_through_hole": "Through hole",
        "meshing_sphere": "Sphere",
        "meshing_bspline_shell": "B-spline shell",
    }
    for control, color in zip(probe.controls, colors, strict=True):
        rows = [item for item in summaries if item["control_id"] == control.control_id]
        axes[0].plot(
            labels,
            [int(item["triangle_count"]) for item in rows],
            marker="o",
            linewidth=2,
            color=color,
            label=names[control.control_id],
        )
        axes[1].plot(
            labels,
            [100.0 * float(item["relative_area_difference"]) for item in rows],
            marker="o",
            linewidth=2,
            color=color,
        )
        axes[2].plot(
            labels,
            [float(item["maximum_sampled_surface_deviation"]) for item in rows],
            marker="o",
            linewidth=2,
            color=color,
        )
    axes[0].set_yscale("log")
    axes[0].set_ylabel("Triangles (log scale)")
    axes[0].set_title("Mesh density responds by surface")
    axes[0].legend()
    axes[1].set_yscale("log")
    axes[1].set_ylabel("Absolute area difference (%)")
    axes[1].set_title("Mesh area versus exact B-Rep area")
    axes[2].set_yscale("log")
    axes[2].set_ylabel("Maximum sampled deviation")
    axes[2].set_title("One UV-barycentric sample per triangle")
    for axis in axes:
        axis.tick_params(axis="x", rotation=24)
        axis.grid(True, which="both", alpha=0.25)
    figure.suptitle(
        "v0.42.0 Tessellation Diagnostics\n"
        "Requested controls are inputs; sampled deviations are not certified bounds"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160)
    plt.close(figure)


def _equal_3d_axes(axis: object, vertices: list[tuple[float, float, float]]) -> None:
    minima = [min(item[index] for item in vertices) for index in range(3)]
    maxima = [max(item[index] for item in vertices) for index in range(3)]
    centers = [(low + high) / 2.0 for low, high in zip(minima, maxima, strict=True)]
    radius = max(high - low for low, high in zip(minima, maxima, strict=True)) / 2.0
    radius = max(radius, 1.0)
    axis.set_xlim(centers[0] - radius, centers[0] + radius)
    axis.set_ylim(centers[1] - radius, centers[1] + radius)
    axis.set_zlim(centers[2] - radius, centers[2] + radius)
    axis.set_box_aspect((1, 1, 1))


def write_visual(path: Path, probe: TessellationProbe) -> None:
    """Render face-colored coarse and fine mesh previews from report triangles."""
    figure = plt.figure(figsize=(11.5, 11.0), constrained_layout=True)
    condition_ids = ("coarse_both", "fine_both")
    condition_titles = ("Coarse controls", "Fine controls")
    control_titles = {
        "meshing_through_hole": "Through-hole solid",
        "meshing_sphere": "Sphere",
        "meshing_bspline_shell": "B-spline shell",
    }
    color_map = plt.get_cmap("tab20")
    for row_index, control in enumerate(probe.controls):
        for column_index, (condition_id, condition_title) in enumerate(
            zip(condition_ids, condition_titles, strict=True)
        ):
            axis = figure.add_subplot(
                len(probe.controls), len(condition_ids),
                row_index * len(condition_ids) + column_index + 1,
                projection="3d",
            )
            rows = [
                item
                for item in probe.triangles
                if item.control_id == control.control_id
                and item.mesh_condition == condition_id
            ]
            polygons = [list(item.vertices) for item in rows]
            face_colors = [color_map((item.analysis_face_index - 1) % 20) for item in rows]
            collection = Poly3DCollection(
                polygons,
                facecolors=face_colors,
                edgecolors="#111827",
                linewidths=0.18,
                alpha=0.92,
            )
            axis.add_collection3d(collection)
            all_vertices = [vertex for item in rows for vertex in item.vertices]
            _equal_3d_axes(axis, all_vertices)
            axis.view_init(elev=24, azim=-55)
            axis.set_axis_off()
            axis.set_title(
                f"{control_titles[control.control_id]} — {condition_title}\n"
                f"{len(rows)} triangles"
            )
    figure.suptitle(
        "Face-Colored Tessellation Previews\n"
        "Colors identify analysis-local faces; previews are not exact geometry",
        fontsize=14,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160)
    plt.close(figure)


def run(output_dir: Path, fixture_dir: Path, *, refresh: bool) -> None:
    """Run and serialize the complete v0.42.0 experiment."""
    probe = probe_tessellation_diagnostics()
    handle_fixtures(fixture_dir, probe, refresh=refresh)
    _write_csv(
        output_dir / TRIANGLE_NAME,
        [triangle_row(item) for item in probe.triangles],
        TRIANGLE_FIELDS,
    )
    _write_csv(
        output_dir / FACE_NAME,
        [face_row(item) for item in probe.faces],
        FACE_FIELDS,
    )
    _write_csv(output_dir / SUMMARY_NAME, summary_rows(probe), SUMMARY_FIELDS)
    write_contract(output_dir / CONTRACT_NAME, probe)
    write_figure(output_dir / FIGURE_NAME, probe)
    write_visual(output_dir / VISUAL_NAME, probe)


def main() -> None:
    """Parse command-line arguments and run the experiment."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument(
        "--fixture-dir", type=Path, default=Path("fixtures/tessellation-diagnostics")
    )
    parser.add_argument("--refresh-fixtures", action="store_true")
    arguments = parser.parse_args()
    run(arguments.output_dir, arguments.fixture_dir, refresh=arguments.refresh_fixtures)
    print(f"Wrote tessellation diagnostic artifacts to {arguments.output_dir}")


if __name__ == "__main__":
    main()
