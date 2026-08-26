"""Generate v0.44.0 profile, extrusion, and revolution evidence."""

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
from research_notes.profile_modeling import (  # noqa: E402
    CONTRACT_VERSION,
    ProfileModelingProbe,
    ProfileObservation,
    probe_profile_modeling,
)


OBSERVATION_NAME = "profile_modeling_observations.csv"
SUMMARY_NAME = "profile_modeling_summary.csv"
RECOMPUTE_NAME = "profile_recompute_relations.csv"
CONTRACT_NAME = "profile_modeling_contract.json"
FIGURE_NAME = "profile_modeling.png"
SHAPES_NAME = "profile_modeling_shapes.png"
MANIFEST_NAME = "manifest.csv"

OBSERVATION_FIELDS = (
    "contract_version", "stage", "control_id", "recompute_family",
    "operation", "profile_type", "construction_parameters",
    "profile_outer_wire_count", "profile_inner_wire_count",
    "profile_edge_count", "source_file", "source_sha256", "vertex_count",
    "edge_count", "face_count", "shell_count", "solid_count",
    "absolute_volume", "expected_volume", "volume_absolute_error",
    "surface_area", "expected_surface_area", "surface_area_absolute_error",
    "surface_centroid_x", "surface_centroid_y", "surface_centroid_z",
    "surface_counts", "maximum_vertex_tolerance", "maximum_edge_tolerance",
    "maximum_face_tolerance", "analyzer_valid", "step_advanced_face_count",
)

SUMMARY_FIELDS = (
    "control_id", "topology_matches", "surface_counts_match",
    "volume_absolute_difference", "surface_area_absolute_difference",
    "surface_centroid_distance", "constructed_truth_matches",
    "step_imported_truth_matches", "round_trip_passes",
)

RECOMPUTE_FIELDS = (
    "relation_id", "baseline_control_id", "changed_control_id",
    "changed_parameter", "baseline_parameter", "changed_parameter_value",
    "expected_volume_ratio", "observed_constructed_volume_ratio",
    "observed_step_imported_volume_ratio", "constructed_ratio_error",
    "step_imported_ratio_error", "recompute_relation_passes",
)


def _float(value: float | None) -> str:
    return "" if value is None else format(value, ".17g")


def _pairs(values: tuple[tuple[str, object], ...]) -> str:
    return "|".join(f"{name}:{value}" for name, value in values)


def _topology(item: ProfileObservation) -> tuple[int, int, int, int, int]:
    metrics = item.metrics
    return (
        metrics.vertex_count, metrics.edge_count, metrics.face_count,
        metrics.shell_count, metrics.solid_count,
    )


def observation_rows(probe: ProfileModelingProbe) -> list[dict[str, object]]:
    """Flatten profile truth and evaluated results."""
    controls = {item.control_id: item for item in probe.controls}
    rows: list[dict[str, object]] = []
    for item in probe.observations:
        control = controls[item.control_id]
        metrics = item.metrics
        rows.append({
            "contract_version": item.contract_version,
            "stage": item.stage,
            "control_id": item.control_id,
            "recompute_family": control.recompute_family,
            "operation": control.operation,
            "profile_type": control.profile_type,
            "construction_parameters": _pairs(control.parameters),
            "profile_outer_wire_count": control.outer_wire_count,
            "profile_inner_wire_count": control.inner_wire_count,
            "profile_edge_count": control.profile_edge_count,
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
            "surface_counts": _pairs(metrics.surface_counts),
            "maximum_vertex_tolerance": _float(metrics.maximum_vertex_tolerance),
            "maximum_edge_tolerance": _float(metrics.maximum_edge_tolerance),
            "maximum_face_tolerance": _float(metrics.maximum_face_tolerance),
            "analyzer_valid": int(metrics.analyzer_valid),
            "step_advanced_face_count": "" if item.step_advanced_face_count is None else item.step_advanced_face_count,
        })
    return rows


def summary_rows(probe: ProfileModelingProbe) -> list[dict[str, object]]:
    """Compare constructed and imported profile-driven results."""
    by_key = {(item.control_id, item.stage): item for item in probe.observations}
    rows: list[dict[str, object]] = []
    for control in probe.controls:
        first = by_key[(control.control_id, "constructed")]
        second = by_key[(control.control_id, "step_imported")]
        constructed_truth = (
            first.volume_absolute_error <= 1.0e-8
            and first.surface_area_absolute_error <= 1.0e-8
        )
        imported_truth = (
            second.volume_absolute_error <= 1.0e-8
            and second.surface_area_absolute_error <= 1.0e-8
        )
        topology_match = _topology(first) == _topology(second)
        surfaces_match = first.metrics.surface_counts == second.metrics.surface_counts
        volume_difference = abs(first.metrics.absolute_volume - second.metrics.absolute_volume)
        area_difference = abs(first.metrics.surface_area - second.metrics.surface_area)
        centroid_distance = vector_distance(
            first.metrics.surface_centroid, second.metrics.surface_centroid
        )
        passes = (
            topology_match and surfaces_match and constructed_truth and imported_truth
            and volume_difference <= 1.0e-8 and area_difference <= 1.0e-8
            and centroid_distance <= 1.0e-8 and first.metrics.analyzer_valid
            and second.metrics.analyzer_valid
        )
        rows.append({
            "control_id": control.control_id,
            "topology_matches": int(topology_match),
            "surface_counts_match": int(surfaces_match),
            "volume_absolute_difference": _float(volume_difference),
            "surface_area_absolute_difference": _float(area_difference),
            "surface_centroid_distance": _float(centroid_distance),
            "constructed_truth_matches": int(constructed_truth),
            "step_imported_truth_matches": int(imported_truth),
            "round_trip_passes": int(passes),
        })
    return rows


def recompute_rows(probe: ProfileModelingProbe) -> list[dict[str, object]]:
    """Record volume response to one changed operation parameter."""
    by_key = {(item.control_id, item.stage): item for item in probe.observations}
    relations = (
        (
            "rectangle_height_5_to_7", "extruded_rectangle_h5",
            "extruded_rectangle_h7", "height", 5.0, 7.0, 7.0 / 5.0,
        ),
        (
            "revolution_360_to_180", "revolved_annulus_full",
            "revolved_annulus_half", "angle_degrees", 360.0, 180.0, 0.5,
        ),
    )
    rows: list[dict[str, object]] = []
    for relation_id, baseline, changed, parameter, first_value, second_value, expected in relations:
        constructed_ratio = (
            by_key[(changed, "constructed")].metrics.absolute_volume
            / by_key[(baseline, "constructed")].metrics.absolute_volume
        )
        imported_ratio = (
            by_key[(changed, "step_imported")].metrics.absolute_volume
            / by_key[(baseline, "step_imported")].metrics.absolute_volume
        )
        first_error = abs(constructed_ratio - expected)
        second_error = abs(imported_ratio - expected)
        rows.append({
            "relation_id": relation_id,
            "baseline_control_id": baseline,
            "changed_control_id": changed,
            "changed_parameter": parameter,
            "baseline_parameter": _float(first_value),
            "changed_parameter_value": _float(second_value),
            "expected_volume_ratio": _float(expected),
            "observed_constructed_volume_ratio": _float(constructed_ratio),
            "observed_step_imported_volume_ratio": _float(imported_ratio),
            "constructed_ratio_error": _float(first_error),
            "step_imported_ratio_error": _float(second_error),
            "recompute_relation_passes": int(first_error <= 1.0e-10 and second_error <= 1.0e-10),
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


def _fixture_manifest(probe: ProfileModelingProbe) -> bytes:
    rows = [{
        "control_id": item.fixture_id, "file_name": item.file_name,
        "source_bytes": len(item.source_bytes), "source_sha256": item.source_sha256,
        "generator": "experiments/run_profile_modeling.py",
        "binding_distribution_version": probe.binding_distribution_version,
        "step_processor": item.step_processor, "writer_status": item.writer_status,
        "reader_status": item.reader_status, "transferred_roots": item.transferred_roots,
    } for item in probe.fixtures]
    return _csv_bytes(rows, tuple(rows[0]))


def handle_fixtures(path: Path, probe: ProfileModelingProbe, *, refresh: bool) -> None:
    """Write or verify normalized profile-modeling STEP fixtures."""
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


def write_contract(path: Path, probe: ProfileModelingProbe) -> None:
    """Write the profile, operation, recompute, and claim contract."""
    payload = {
        "contract_version": CONTRACT_VERSION,
        "study_version": "v0.44.0",
        "title": "Profiles, Extrusion, and Revolution",
        "controls": [{
            "control_id": item.control_id,
            "recompute_family": item.recompute_family,
            "operation": item.operation,
            "profile_type": item.profile_type,
            "parameters": dict(item.parameters),
            "outer_wire_count": item.outer_wire_count,
            "inner_wire_count": item.inner_wire_count,
            "profile_edge_count": item.profile_edge_count,
            "expected_volume": item.expected_volume,
            "expected_surface_area": item.expected_surface_area,
        } for item in probe.controls],
        "observation_csv": {"file": OBSERVATION_NAME, "ordered_fields": list(OBSERVATION_FIELDS)},
        "summary_csv": {"file": SUMMARY_NAME, "ordered_fields": list(SUMMARY_FIELDS)},
        "recompute_csv": {"file": RECOMPUTE_NAME, "ordered_fields": list(RECOMPUTE_FIELDS)},
        "fixture_sha256": {item.file_name: item.source_sha256 for item in probe.fixtures},
        "claim_boundaries": [
            "profile and operation parameters are synthetic construction truth",
            "STEP output does not recover the original sketch or feature command",
            "only planar rectangle, annulus, and radial-rectangle profiles are covered",
            "recompute evidence changes one declared parameter in two bounded families",
            "local topology indices are not persistent feature identities",
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_figure(path: Path, probe: ProfileModelingProbe) -> None:
    """Plot truth residuals and controlled recompute response."""
    imported = [item for item in probe.observations if item.stage == "step_imported"]
    labels = [item.control_id.replace("_", " ") for item in imported]
    figure, axes = plt.subplots(1, 2, figsize=(13.5, 4.8), constrained_layout=True)
    x_values = list(range(len(imported)))
    axes[0].bar(
        [x - 0.18 for x in x_values],
        [max(item.volume_absolute_error, 1.0e-17) for item in imported],
        0.36, label="Volume",
    )
    axes[0].bar(
        [x + 0.18 for x in x_values],
        [max(item.surface_area_absolute_error, 1.0e-17) for item in imported],
        0.36, label="Surface area",
    )
    axes[0].set_yscale("log")
    axes[0].set_xticks(x_values, labels, rotation=25, ha="right")
    axes[0].set_ylabel("Absolute truth error (log scale)")
    axes[0].set_title("Imported results versus analytic truth")
    axes[0].legend()
    relations = recompute_rows(probe)
    relation_labels = [item["relation_id"].replace("_", " ") for item in relations]
    axes[1].bar(
        range(len(relations)),
        [float(item["expected_volume_ratio"]) for item in relations],
        color="#64748b", alpha=0.5, label="Expected",
    )
    axes[1].scatter(
        range(len(relations)),
        [float(item["observed_step_imported_volume_ratio"]) for item in relations],
        color="#dc2626", s=55, label="STEP-imported",
    )
    axes[1].set_xticks(range(len(relations)), relation_labels, rotation=20)
    axes[1].set_ylabel("Changed / baseline volume")
    axes[1].set_title("Parameter-driven recompute relations")
    axes[1].legend()
    figure.suptitle("v0.44.0 Profiles, Extrusion, and Revolution")
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160)
    plt.close(figure)


def run(output_dir: Path, fixture_dir: Path, *, refresh: bool) -> None:
    """Run and serialize the complete v0.44.0 experiment."""
    probe = probe_profile_modeling()
    handle_fixtures(fixture_dir, probe, refresh=refresh)
    _write_csv(output_dir / OBSERVATION_NAME, observation_rows(probe), OBSERVATION_FIELDS)
    _write_csv(output_dir / SUMMARY_NAME, summary_rows(probe), SUMMARY_FIELDS)
    _write_csv(output_dir / RECOMPUTE_NAME, recompute_rows(probe), RECOMPUTE_FIELDS)
    write_contract(output_dir / CONTRACT_NAME, probe)
    write_figure(output_dir / FIGURE_NAME, probe)
    imported = tuple(
        (control_id.replace("_", " ").title(), shape)
        for control_id, stage, shape in probe.preview_shapes if stage == "step_imported"
    )
    write_shape_previews(output_dir / SHAPES_NAME, imported, title="v0.44.0 Profile-Driven Results", columns=3)
    print(f"Wrote profile-modeling artifacts to {output_dir}")


def main() -> None:
    """Parse command-line arguments and run the experiment."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument("--fixture-dir", type=Path, default=Path("fixtures/profile-modeling"))
    parser.add_argument("--refresh-fixtures", action="store_true")
    arguments = parser.parse_args()
    run(arguments.output_dir, arguments.fixture_dir, refresh=arguments.refresh_fixtures)


if __name__ == "__main__":
    main()

