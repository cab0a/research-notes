"""Generate stable face-level analysis reports for synthetic B-Rep controls."""

from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, Ellipse, Polygon, Rectangle  # noqa: E402

from research_notes.face_analysis import (  # noqa: E402
    CONTRACT_VERSION,
    SUPPORTED_SURFACE_TYPES,
    FaceAnalysisProbe,
    FaceAnalysisRow,
    probe_face_analysis,
)


REPORT_NAME = "face_analysis_report.csv"
MATCH_NAME = "face_analysis_round_trip_matches.csv"
SUMMARY_NAME = "face_analysis_summary.csv"
CONTRACT_NAME = "face_analysis_contract.json"
FIGURE_NAME = "face_analysis.png"
SHAPES_NAME = "face_analysis_shapes.png"
MANIFEST_NAME = "manifest.csv"

REPORT_FIELDS = (
    "contract_version",
    "stage",
    "control_id",
    "source_file",
    "source_sha256",
    "analysis_face_index",
    "parent_solid_indices",
    "parent_shell_indices",
    "surface_type",
    "kernel_surface_type",
    "orientation",
    "area",
    "centroid_x",
    "centroid_y",
    "centroid_z",
    "u_min",
    "u_max",
    "v_min",
    "v_max",
    "representative_u",
    "representative_v",
    "representative_normal_x",
    "representative_normal_y",
    "representative_normal_z",
    "surface_origin_x",
    "surface_origin_y",
    "surface_origin_z",
    "surface_axis_x",
    "surface_axis_y",
    "surface_axis_z",
    "surface_x_direction_x",
    "surface_x_direction_y",
    "surface_x_direction_z",
    "plane_normal_x",
    "plane_normal_y",
    "plane_normal_z",
    "radius",
    "secondary_radius",
    "semi_angle_degrees",
    "u_degree",
    "v_degree",
    "u_pole_count",
    "v_pole_count",
    "u_knot_count",
    "v_knot_count",
    "u_periodic",
    "v_periodic",
    "u_rational",
    "v_rational",
    "outer_wire_count",
    "inner_wire_count",
    "boundary_edge_count",
    "face_tolerance",
    "adjacent_face_indices",
    "name",
    "name_source",
    "color_red",
    "color_green",
    "color_blue",
    "color_source",
)

MATCH_FIELDS = (
    "control_id",
    "constructed_face_index",
    "step_imported_face_index",
    "matched_by",
    "surface_type",
    "area_absolute_difference",
    "centroid_distance",
    "orientation_matches",
    "outer_wire_count_matches",
    "inner_wire_count_matches",
    "boundary_edge_count_matches",
)


def _float(value: float | None) -> str:
    return "" if value is None else format(value, ".17g")


def _integer(value: int | None) -> str:
    return "" if value is None else str(value)


def _boolean(value: bool | None) -> str:
    return "" if value is None else str(int(value))


def _indices(values: tuple[int, ...]) -> str:
    return "|".join(str(value) for value in values)


def _vector_fields(
    prefix: str, value: tuple[float, float, float] | None
) -> dict[str, str]:
    vector = (None, None, None) if value is None else value
    return {
        f"{prefix}_{axis}": _float(component)
        for axis, component in zip(("x", "y", "z"), vector, strict=True)
    }


def report_row(item: FaceAnalysisRow) -> dict[str, str]:
    """Flatten one face observation according to the v1 CSV contract."""
    color = (None, None, None) if item.color_rgb is None else item.color_rgb
    row = {
        "contract_version": item.contract_version,
        "stage": item.stage,
        "control_id": item.control_id,
        "source_file": item.source_file or "",
        "source_sha256": item.source_sha256 or "",
        "analysis_face_index": str(item.analysis_face_index),
        "parent_solid_indices": _indices(item.parent_solid_indices),
        "parent_shell_indices": _indices(item.parent_shell_indices),
        "surface_type": item.surface_type,
        "kernel_surface_type": item.kernel_surface_type,
        "orientation": item.orientation,
        "area": _float(item.area),
        "u_min": _float(item.uv_bounds[0]),
        "u_max": _float(item.uv_bounds[1]),
        "v_min": _float(item.uv_bounds[2]),
        "v_max": _float(item.uv_bounds[3]),
        "representative_u": _float(item.representative_uv[0]),
        "representative_v": _float(item.representative_uv[1]),
        "radius": _float(item.radius),
        "secondary_radius": _float(item.secondary_radius),
        "semi_angle_degrees": _float(item.semi_angle_degrees),
        "u_degree": _integer(item.u_degree),
        "v_degree": _integer(item.v_degree),
        "u_pole_count": _integer(item.u_pole_count),
        "v_pole_count": _integer(item.v_pole_count),
        "u_knot_count": _integer(item.u_knot_count),
        "v_knot_count": _integer(item.v_knot_count),
        "u_periodic": _boolean(item.u_periodic),
        "v_periodic": _boolean(item.v_periodic),
        "u_rational": _boolean(item.u_rational),
        "v_rational": _boolean(item.v_rational),
        "outer_wire_count": str(item.outer_wire_count),
        "inner_wire_count": str(item.inner_wire_count),
        "boundary_edge_count": str(item.boundary_edge_count),
        "face_tolerance": _float(item.face_tolerance),
        "adjacent_face_indices": _indices(item.adjacent_face_indices),
        "name": item.name or "",
        "name_source": item.name_source,
        "color_red": _float(color[0]),
        "color_green": _float(color[1]),
        "color_blue": _float(color[2]),
        "color_source": item.color_source,
    }
    row.update(_vector_fields("centroid", item.centroid))
    row.update(_vector_fields("representative_normal", item.representative_normal))
    row.update(_vector_fields("surface_origin", item.surface_origin))
    row.update(_vector_fields("surface_axis", item.surface_axis))
    row.update(_vector_fields("surface_x_direction", item.surface_x_direction))
    row.update(_vector_fields("plane_normal", item.plane_normal))
    if set(row) != set(REPORT_FIELDS):
        raise RuntimeError("face report serialization no longer matches field contract")
    return row


def match_rows(probe: FaceAnalysisProbe) -> list[dict[str, str]]:
    """Serialize geometry-matched round-trip comparisons."""
    return [
        {
            "control_id": item.control_id,
            "constructed_face_index": str(item.constructed_face_index),
            "step_imported_face_index": str(item.step_imported_face_index),
            "matched_by": item.matched_by,
            "surface_type": item.surface_type,
            "area_absolute_difference": _float(item.area_absolute_difference),
            "centroid_distance": _float(item.centroid_distance),
            "orientation_matches": str(int(item.orientation_matches)),
            "outer_wire_count_matches": str(int(item.outer_wire_count_matches)),
            "inner_wire_count_matches": str(int(item.inner_wire_count_matches)),
            "boundary_edge_count_matches": str(
                int(item.boundary_edge_count_matches)
            ),
        }
        for item in probe.matches
    ]


def _cone_signed_angle_flip_count(probe: FaceAnalysisProbe) -> int:
    constructed = next(
        item
        for item in probe.rows
        if item.stage == "constructed" and item.surface_type == "cone"
    )
    imported = next(
        item
        for item in probe.rows
        if item.stage == "step_imported" and item.surface_type == "cone"
    )
    if constructed.semi_angle_degrees is None or imported.semi_angle_degrees is None:
        return 0
    return int(
        constructed.semi_angle_degrees * imported.semi_angle_degrees < 0.0
        and abs(abs(constructed.semi_angle_degrees) - abs(imported.semi_angle_degrees))
        < 1.0e-9
    )


def summary_rows(probe: FaceAnalysisProbe) -> list[dict[str, str]]:
    """Build compact corpus, coverage, and round-trip evidence."""
    constructed = [item for item in probe.rows if item.stage == "constructed"]
    imported = [item for item in probe.rows if item.stage == "step_imported"]
    topology_matches = sum(
        item.orientation_matches
        and item.outer_wire_count_matches
        and item.inner_wire_count_matches
        and item.boundary_edge_count_matches
        for item in probe.matches
    )
    values: list[tuple[str, str, object]] = [
        ("corpus", "control_count", len(probe.controls)),
        ("corpus", "fixture_count", len(probe.fixtures)),
        ("all", "face_row_count", len(probe.rows)),
        ("constructed", "face_row_count", len(constructed)),
        ("step_imported", "face_row_count", len(imported)),
        ("all", "round_trip_match_count", len(probe.matches)),
        ("round_trip", "topology_attribute_match_count", topology_matches),
        (
            "round_trip",
            "maximum_area_absolute_difference",
            max(item.area_absolute_difference for item in probe.matches),
        ),
        (
            "round_trip",
            "maximum_centroid_distance",
            max(item.centroid_distance for item in probe.matches),
        ),
        (
            "round_trip",
            "cone_signed_semi_angle_flip_count",
            _cone_signed_angle_flip_count(probe),
        ),
        (
            "constructed",
            "maximum_face_tolerance",
            max(item.face_tolerance for item in constructed),
        ),
        (
            "step_imported",
            "maximum_face_tolerance",
            max(item.face_tolerance for item in imported),
        ),
        ("constructed", "named_face_count", sum(item.name is not None for item in constructed)),
        ("step_imported", "named_face_count", sum(item.name is not None for item in imported)),
        ("constructed", "colored_face_count", sum(item.color_rgb is not None for item in constructed)),
        ("step_imported", "colored_face_count", sum(item.color_rgb is not None for item in imported)),
        ("all", "faces_with_inner_wires", sum(item.inner_wire_count > 0 for item in probe.rows)),
        ("all", "faces_without_parent_solid", sum(not item.parent_solid_indices for item in probe.rows)),
    ]
    for stage, stage_rows in (("constructed", constructed), ("step_imported", imported)):
        for surface_type in SUPPORTED_SURFACE_TYPES:
            values.append(
                (
                    stage,
                    f"{surface_type}_face_count",
                    sum(item.surface_type == surface_type for item in stage_rows),
                )
            )
    return [
        {
            "scope": scope,
            "metric": metric,
            "value": _float(value) if isinstance(value, float) else str(value),
        }
        for scope, metric, value in values
    ]


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


def _fixture_manifest(probe: FaceAnalysisProbe) -> bytes:
    rows = [
        {
            "control_id": item.fixture_id,
            "file_name": item.file_name,
            "source_bytes": str(len(item.source_bytes)),
            "source_sha256": item.source_sha256,
            "generator": "experiments/run_face_level_analysis.py",
            "binding_distribution_version": probe.binding_distribution_version,
            "step_processor": item.step_processor,
            "writer_status": item.writer_status,
            "reader_status": item.reader_status,
            "transferred_roots": str(item.transferred_roots),
        }
        for item in probe.fixtures
    ]
    return _csv_bytes(rows, tuple(rows[0]))


def handle_fixtures(
    path: Path, probe: FaceAnalysisProbe, *, refresh: bool
) -> None:
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


def write_contract(path: Path, probe: FaceAnalysisProbe) -> None:
    """Write the machine-readable CSV and interpretation contract."""
    nullable_fields = [
        "source_file",
        "source_sha256",
        "parent_solid_indices",
        "parent_shell_indices",
        "surface_origin_x",
        "surface_origin_y",
        "surface_origin_z",
        "surface_axis_x",
        "surface_axis_y",
        "surface_axis_z",
        "surface_x_direction_x",
        "surface_x_direction_y",
        "surface_x_direction_z",
        "plane_normal_x",
        "plane_normal_y",
        "plane_normal_z",
        "radius",
        "secondary_radius",
        "semi_angle_degrees",
        "u_degree",
        "v_degree",
        "u_pole_count",
        "v_pole_count",
        "u_knot_count",
        "v_knot_count",
        "u_periodic",
        "v_periodic",
        "u_rational",
        "v_rational",
        "adjacent_face_indices",
        "name",
        "color_red",
        "color_green",
        "color_blue",
    ]
    payload = {
        "contract_version": CONTRACT_VERSION,
        "study_version": "v0.41.0",
        "title": "Face-Level Analysis Reports",
        "csv": {
            "file": REPORT_NAME,
            "encoding": "UTF-8",
            "delimiter": ",",
            "line_ending": "LF",
            "row_unit": "one unique analysis-local face within one control and stage",
            "primary_key": ["stage", "control_id", "analysis_face_index"],
            "ordered_fields": list(REPORT_FIELDS),
            "nullable_fields": nullable_fields,
            "integer_list_encoding": "ascending decimal indices joined by |; empty means none",
            "boolean_encoding": "1=true, 0=false, empty=not applicable",
            "floating_point_encoding": "Python .17g decimal formatting",
        },
        "surface_types": list(SUPPORTED_SURFACE_TYPES),
        "surface_parameter_semantics": {
            "plane": ["surface_origin", "surface_x_direction", "plane_normal"],
            "cylinder": ["surface_origin", "surface_axis", "surface_x_direction", "radius"],
            "cone": ["surface_origin", "surface_axis", "surface_x_direction", "radius", "semi_angle_degrees"],
            "sphere": ["surface_origin", "surface_axis", "surface_x_direction", "radius"],
            "torus": ["surface_origin", "surface_axis", "surface_x_direction", "radius", "secondary_radius"],
            "bspline": ["u_degree", "v_degree", "u_pole_count", "v_pole_count", "u_knot_count", "v_knot_count", "u_periodic", "v_periodic", "u_rational", "v_rational"],
        },
        "parameter_units": {
            "area": "squared model units",
            "centroid": "model units",
            "radius": "model units",
            "secondary_radius": "model units",
            "semi_angle_degrees": "degrees",
            "face_tolerance": "model units",
            "uv_bounds": "surface-parameter units",
        },
        "index_scope": "analysis-local to one control and stage; not a persistent CAD identity",
        "representative_normal": "oriented face normal at the first nonsingular deterministic UV sample",
        "boundary_edge_count": "unique topological edges referenced by the face",
        "adjacency": "distinct faces sharing at least one unique topological edge; self-seams are excluded",
        "metadata": {
            "constructed": "shape-level values copied from the synthetic control manifest",
            "step_imported": "blank because STEPControl_Reader returns a TopoDS_Shape without XCAF name or color attributes",
            "metadata_is_not_inferred": True,
        },
        "fixture_sha256": {
            item.file_name: item.source_sha256 for item in probe.fixtures
        },
        "claim_boundaries": [
            "CSV schema stability does not make analysis-local face indices persistent",
            "UV bounds depend on surface parameterization and are not a three-dimensional bounding box",
            "one representative normal does not prove regularity over an entire face",
            "face tolerances are kernel values and not manufacturing tolerances",
            "blank STEP-imported names and colors do not prove that source metadata never existed",
            "the controlled corpus is not general STEP or B-Rep conformance evidence",
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def write_figure(path: Path, probe: FaceAnalysisProbe) -> None:
    """Plot surface inventory and nullable-field coverage by stage."""
    figure, axes = plt.subplots(1, 2, figsize=(12.4, 4.9), constrained_layout=True)
    labels = ["Plane", "Cylinder", "Cone", "Sphere", "Torus", "B-spline"]
    positions = list(range(len(SUPPORTED_SURFACE_TYPES)))
    for offset, stage, color, label in (
        (-0.18, "constructed", "#2563eb", "Constructed"),
        (0.18, "step_imported", "#14b8a6", "STEP imported"),
    ):
        counts = [
            sum(
                item.stage == stage and item.surface_type == surface_type
                for item in probe.rows
            )
            for surface_type in SUPPORTED_SURFACE_TYPES
        ]
        axes[0].bar(
            [value + offset for value in positions],
            counts,
            width=0.36,
            color=color,
            label=label,
        )
    axes[0].set_xticks(positions, labels, rotation=20)
    axes[0].set_ylabel("Face rows")
    axes[0].set_title("Surface-family inventory")
    axes[0].legend()

    coverage_labels = [
        "Solid parent",
        "Shell parent",
        "Axis",
        "Radius",
        "Inner wire",
        "Name",
        "Color",
    ]
    predicates = [
        lambda item: bool(item.parent_solid_indices),
        lambda item: bool(item.parent_shell_indices),
        lambda item: item.surface_axis is not None,
        lambda item: item.radius is not None,
        lambda item: item.inner_wire_count > 0,
        lambda item: item.name is not None,
        lambda item: item.color_rgb is not None,
    ]
    for offset, stage, color, label in (
        (-0.18, "constructed", "#2563eb", "Constructed"),
        (0.18, "step_imported", "#14b8a6", "STEP imported"),
    ):
        rows = [item for item in probe.rows if item.stage == stage]
        coverage = [100.0 * sum(test(item) for item in rows) / len(rows) for test in predicates]
        axes[1].barh(
            [value + offset for value in range(len(coverage_labels))],
            coverage,
            height=0.36,
            color=color,
            label=label,
        )
    axes[1].set_yticks(range(len(coverage_labels)), coverage_labels)
    axes[1].set_xlim(0.0, 105.0)
    axes[1].set_xlabel("Rows with field evidence (%)")
    axes[1].set_title("Field coverage is explicit")
    axes[1].legend()
    maximum_area = max(item.area_absolute_difference for item in probe.matches)
    maximum_centroid = max(item.centroid_distance for item in probe.matches)
    figure.suptitle(
        "v0.41.0 Face-Level Report Evidence\n"
        f"13 matched faces; max area difference {maximum_area:.2e}; "
        f"max centroid distance {maximum_centroid:.2e} model units"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160)
    plt.close(figure)


def write_shapes_figure(path: Path) -> None:
    """Render schematic previews of the five generated shape controls."""
    figure, axes = plt.subplots(1, 5, figsize=(14.5, 3.4), constrained_layout=True)
    for axis in axes:
        axis.set_xlim(-1.0, 7.0)
        axis.set_ylim(-1.0, 7.0)
        axis.set_aspect("equal")
        axis.axis("off")

    axes[0].add_patch(Rectangle((0, 0), 6, 5, facecolor="#dbeafe", edgecolor="#1e3a8a"))
    axes[0].add_patch(Circle((2.2, 2.5), 0.8, facecolor="white", edgecolor="#dc2626", linewidth=2))
    axes[0].set_title("Through-hole solid\n7 faces")

    axes[1].add_patch(Polygon([(1, 0), (5, 0), (4, 5), (2, 5)], closed=True, facecolor="#fed7aa", edgecolor="#9a3412"))
    axes[1].add_patch(Ellipse((3, 5), 2, 0.55, facecolor="#ffedd5", edgecolor="#9a3412"))
    axes[1].set_title("Conical solid\n3 faces")

    axes[2].add_patch(Circle((3, 2.7), 2.1, facecolor="#bbf7d0", edgecolor="#166534"))
    axes[2].add_patch(Ellipse((3, 2.7), 4.2, 1.1, fill=False, edgecolor="#16a34a", linestyle="--"))
    axes[2].set_title("Spherical solid\n1 face")

    axes[3].add_patch(Circle((3, 2.7), 2.4, facecolor="#e9d5ff", edgecolor="#6b21a8"))
    axes[3].add_patch(Circle((3, 2.7), 1.2, facecolor="white", edgecolor="#6b21a8"))
    axes[3].set_title("Toroidal solid\n1 face")

    patch = Polygon([(0.5, 0.5), (5.8, 0.9), (5.2, 5.4), (1.0, 4.8)], closed=True, facecolor="#a5f3fc", edgecolor="#0e7490")
    axes[4].add_patch(patch)
    for value in (1.6, 2.7, 3.8, 4.9):
        axes[4].plot([0.8, 5.5], [value, value + 0.35], color="#0891b2", linewidth=0.8)
    axes[4].set_title("B-spline shell\n1 face, no solid")

    figure.suptitle("Synthetic Controls for Face-Level Analysis")
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160)
    plt.close(figure)


def run(output_dir: Path, fixture_dir: Path, *, refresh: bool) -> None:
    """Run and serialize the complete v0.41.0 experiment."""
    probe = probe_face_analysis()
    handle_fixtures(fixture_dir, probe, refresh=refresh)
    reports = [report_row(item) for item in probe.rows]
    _write_csv(output_dir / REPORT_NAME, reports, REPORT_FIELDS)
    matches = match_rows(probe)
    _write_csv(output_dir / MATCH_NAME, matches, MATCH_FIELDS)
    summaries = summary_rows(probe)
    _write_csv(output_dir / SUMMARY_NAME, summaries, ("scope", "metric", "value"))
    write_contract(output_dir / CONTRACT_NAME, probe)
    write_figure(output_dir / FIGURE_NAME, probe)
    write_shapes_figure(output_dir / SHAPES_NAME)


def main() -> None:
    """Parse command-line arguments and run the experiment."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument(
        "--fixture-dir", type=Path, default=Path("fixtures/face-analysis")
    )
    parser.add_argument("--refresh-fixtures", action="store_true")
    arguments = parser.parse_args()
    run(arguments.output_dir, arguments.fixture_dir, refresh=arguments.refresh_fixtures)
    print(f"Wrote face-level analysis artifacts to {arguments.output_dir}")


if __name__ == "__main__":
    main()
