"""Generate v0.43.0 primitive-construction and STEP round-trip evidence."""

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
from research_notes.modeling_common import (  # noqa: E402
    maximum_parameter_difference,
    vector_distance,
)
from research_notes.primitive_round_trips import (  # noqa: E402
    CONTRACT_VERSION,
    PrimitiveObservation,
    PrimitiveRoundTripProbe,
    probe_primitive_round_trips,
)


OBSERVATION_NAME = "primitive_round_trip_observations.csv"
SUMMARY_NAME = "primitive_round_trip_summary.csv"
CONTRACT_NAME = "primitive_round_trip_contract.json"
FIGURE_NAME = "primitive_round_trip.png"
SHAPES_NAME = "primitive_round_trip_shapes.png"
MANIFEST_NAME = "manifest.csv"

OBSERVATION_FIELDS = (
    "contract_version",
    "stage",
    "control_id",
    "source_file",
    "source_sha256",
    "construction_parameters",
    "vertex_count",
    "edge_count",
    "face_count",
    "shell_count",
    "solid_count",
    "absolute_volume",
    "expected_volume",
    "volume_absolute_error",
    "surface_area",
    "expected_surface_area",
    "surface_area_absolute_error",
    "surface_centroid_x",
    "surface_centroid_y",
    "surface_centroid_z",
    "bounds_min_x",
    "bounds_min_y",
    "bounds_min_z",
    "bounds_max_x",
    "bounds_max_y",
    "bounds_max_z",
    "maximum_vertex_tolerance",
    "maximum_edge_tolerance",
    "maximum_face_tolerance",
    "surface_counts",
    "support_parameters",
    "surface_inventory_matches",
    "solid_count_matches",
    "analyzer_valid",
    "step_entity_count",
    "step_advanced_face_count",
)

SUMMARY_FIELDS = (
    "control_id",
    "constructed_topology",
    "step_imported_topology",
    "topology_matches",
    "constructed_surface_counts",
    "step_imported_surface_counts",
    "surface_counts_match",
    "volume_absolute_difference",
    "surface_area_absolute_difference",
    "surface_centroid_distance",
    "bounds_maximum_absolute_difference",
    "support_parameter_maximum_absolute_difference",
    "constructed_analyzer_valid",
    "step_imported_analyzer_valid",
    "round_trip_contract_passes",
)


def _float(value: float | None) -> str:
    return "" if value is None else format(value, ".17g")


def _pairs(values: tuple[tuple[str, object], ...]) -> str:
    return "|".join(f"{name}:{value}" for name, value in values)


def _parameters(values: tuple[tuple[str, tuple[float, ...]], ...]) -> str:
    return "|".join(
        f"{name}:{','.join(_float(value) for value in parameters)}"
        for name, parameters in values
    )


def _topology(item: PrimitiveObservation) -> str:
    metrics = item.metrics
    return (
        f"V={metrics.vertex_count}|E={metrics.edge_count}|F={metrics.face_count}"
        f"|Sh={metrics.shell_count}|So={metrics.solid_count}"
    )


def observation_rows(probe: PrimitiveRoundTripProbe) -> list[dict[str, object]]:
    """Serialize stage observations into a stable flat schema."""
    controls = {item.control_id: item for item in probe.controls}
    rows: list[dict[str, object]] = []
    for item in probe.observations:
        metrics = item.metrics
        control = controls[item.control_id]
        rows.append(
            {
                "contract_version": item.contract_version,
                "stage": item.stage,
                "control_id": item.control_id,
                "source_file": item.source_file or "",
                "source_sha256": item.source_sha256 or "",
                "construction_parameters": _pairs(control.parameters),
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
                "surface_area_absolute_error": _float(
                    item.surface_area_absolute_error
                ),
                "surface_centroid_x": _float(metrics.surface_centroid[0]),
                "surface_centroid_y": _float(metrics.surface_centroid[1]),
                "surface_centroid_z": _float(metrics.surface_centroid[2]),
                "bounds_min_x": _float(metrics.bounds_min[0]),
                "bounds_min_y": _float(metrics.bounds_min[1]),
                "bounds_min_z": _float(metrics.bounds_min[2]),
                "bounds_max_x": _float(metrics.bounds_max[0]),
                "bounds_max_y": _float(metrics.bounds_max[1]),
                "bounds_max_z": _float(metrics.bounds_max[2]),
                "maximum_vertex_tolerance": _float(
                    metrics.maximum_vertex_tolerance
                ),
                "maximum_edge_tolerance": _float(metrics.maximum_edge_tolerance),
                "maximum_face_tolerance": _float(metrics.maximum_face_tolerance),
                "surface_counts": _pairs(metrics.surface_counts),
                "support_parameters": _parameters(item.support_parameters),
                "surface_inventory_matches": int(item.surface_inventory_matches),
                "solid_count_matches": int(item.solid_count_matches),
                "analyzer_valid": int(metrics.analyzer_valid),
                "step_entity_count": ""
                if item.step_entity_count is None
                else item.step_entity_count,
                "step_advanced_face_count": ""
                if item.step_advanced_face_count is None
                else item.step_advanced_face_count,
            }
        )
    return rows


def summary_rows(probe: PrimitiveRoundTripProbe) -> list[dict[str, object]]:
    """Compare constructed and imported observations without index identity."""
    by_key = {(item.control_id, item.stage): item for item in probe.observations}
    rows: list[dict[str, object]] = []
    for control in probe.controls:
        constructed = by_key[(control.control_id, "constructed")]
        imported = by_key[(control.control_id, "step_imported")]
        first = constructed.metrics
        second = imported.metrics
        topology_match = _topology(constructed) == _topology(imported)
        surface_match = first.surface_counts == second.surface_counts
        bounds_difference = max(
            abs(a - b)
            for a, b in zip(
                first.bounds_min + first.bounds_max,
                second.bounds_min + second.bounds_max,
                strict=True,
            )
        )
        parameter_difference = maximum_parameter_difference(
            constructed.support_parameters, imported.support_parameters
        )
        passes = (
            topology_match
            and surface_match
            and abs(first.absolute_volume - second.absolute_volume) <= 1.0e-8
            and abs(first.surface_area - second.surface_area) <= 1.0e-8
            and vector_distance(first.surface_centroid, second.surface_centroid)
            <= 1.0e-8
            and bounds_difference <= 1.0e-8
            and parameter_difference is not None
            and parameter_difference <= 1.0e-8
            and first.analyzer_valid
            and second.analyzer_valid
        )
        rows.append(
            {
                "control_id": control.control_id,
                "constructed_topology": _topology(constructed),
                "step_imported_topology": _topology(imported),
                "topology_matches": int(topology_match),
                "constructed_surface_counts": _pairs(first.surface_counts),
                "step_imported_surface_counts": _pairs(second.surface_counts),
                "surface_counts_match": int(surface_match),
                "volume_absolute_difference": _float(
                    abs(first.absolute_volume - second.absolute_volume)
                ),
                "surface_area_absolute_difference": _float(
                    abs(first.surface_area - second.surface_area)
                ),
                "surface_centroid_distance": _float(
                    vector_distance(first.surface_centroid, second.surface_centroid)
                ),
                "bounds_maximum_absolute_difference": _float(bounds_difference),
                "support_parameter_maximum_absolute_difference": _float(
                    parameter_difference
                ),
                "constructed_analyzer_valid": int(first.analyzer_valid),
                "step_imported_analyzer_valid": int(second.analyzer_valid),
                "round_trip_contract_passes": int(passes),
            }
        )
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


def _fixture_manifest(probe: PrimitiveRoundTripProbe) -> bytes:
    rows = [
        {
            "control_id": item.fixture_id,
            "file_name": item.file_name,
            "source_bytes": len(item.source_bytes),
            "source_sha256": item.source_sha256,
            "generator": "experiments/run_primitive_round_trips.py",
            "binding_distribution_version": probe.binding_distribution_version,
            "step_processor": item.step_processor,
            "writer_status": item.writer_status,
            "reader_status": item.reader_status,
            "transferred_roots": item.transferred_roots,
        }
        for item in probe.fixtures
    ]
    return _csv_bytes(rows, tuple(rows[0]))


def handle_fixtures(path: Path, probe: PrimitiveRoundTripProbe, *, refresh: bool) -> None:
    """Write or verify normalized primitive STEP fixtures."""
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


def write_contract(path: Path, probe: PrimitiveRoundTripProbe) -> None:
    """Write the v0.43.0 row and interpretation contract."""
    payload = {
        "contract_version": CONTRACT_VERSION,
        "study_version": "v0.43.0",
        "title": "Primitive Construction and STEP Round Trips",
        "controls": [
            {
                "control_id": item.control_id,
                "construction": item.construction,
                "parameters": dict(item.parameters),
                "expected_surface_counts": dict(item.expected_surface_counts),
                "expected_solid_count": item.expected_solid_count,
                "expected_volume": item.expected_volume,
                "expected_surface_area": item.expected_surface_area,
            }
            for item in probe.controls
        ],
        "observation_csv": {
            "file": OBSERVATION_NAME,
            "ordered_fields": list(OBSERVATION_FIELDS),
            "primary_key": ["control_id", "stage"],
        },
        "summary_csv": {
            "file": SUMMARY_NAME,
            "ordered_fields": list(SUMMARY_FIELDS),
            "primary_key": ["control_id"],
        },
        "fixture_sha256": {
            item.file_name: item.source_sha256 for item in probe.fixtures
        },
        "claim_boundaries": [
            "construction parameters are synthetic ground truth, not recovered feature history",
            "B-spline area has no independent closed-form truth in this study",
            "topology counts and local indices are not persistent CAD identities",
            "one pinned OCCT STEP route is not cross-kernel portability evidence",
            "normalized STEP bytes are deterministic fixtures, not semantic byte-identity requirements",
            "diagnostic previews are not exact B-Rep geometry",
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def write_figure(path: Path, probe: PrimitiveRoundTripProbe) -> None:
    """Plot round-trip residuals and topology inventory."""
    summaries = summary_rows(probe)
    labels = [item["control_id"].removeprefix("primitive_") for item in summaries]
    figure, axes = plt.subplots(1, 2, figsize=(13.0, 4.8), constrained_layout=True)
    residual_fields = (
        ("volume_absolute_difference", "Volume"),
        ("surface_area_absolute_difference", "Area"),
        ("surface_centroid_distance", "Centroid"),
        ("bounds_maximum_absolute_difference", "Bounds"),
        ("support_parameter_maximum_absolute_difference", "Parameters"),
    )
    x_values = list(range(len(labels)))
    width = 0.15
    for offset, (field, label) in enumerate(residual_fields):
        axes[0].bar(
            [value + (offset - 2) * width for value in x_values],
            [max(float(item[field]), 1.0e-17) for item in summaries],
            width,
            label=label,
        )
    axes[0].set_yscale("log")
    axes[0].set_xticks(x_values, labels, rotation=22)
    axes[0].set_ylabel("Absolute difference (log scale)")
    axes[0].set_title("Constructed versus STEP-imported")
    axes[0].legend(fontsize=8)
    imported = {
        item.control_id: item
        for item in probe.observations
        if item.stage == "step_imported"
    }
    axes[1].bar(
        x_values,
        [imported[control.control_id].metrics.face_count for control in probe.controls],
        color="#2563eb",
    )
    axes[1].set_xticks(x_values, labels, rotation=22)
    axes[1].set_ylabel("Unique faces")
    axes[1].set_title("Imported topology inventory")
    axes[1].grid(axis="y", alpha=0.25)
    figure.suptitle("v0.43.0 Primitive Construction and STEP Round Trips")
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160)
    plt.close(figure)


def run(output_dir: Path, fixture_dir: Path, *, refresh: bool) -> None:
    """Run and serialize the complete v0.43.0 experiment."""
    probe = probe_primitive_round_trips()
    handle_fixtures(fixture_dir, probe, refresh=refresh)
    _write_csv(
        output_dir / OBSERVATION_NAME,
        observation_rows(probe),
        OBSERVATION_FIELDS,
    )
    _write_csv(output_dir / SUMMARY_NAME, summary_rows(probe), SUMMARY_FIELDS)
    write_contract(output_dir / CONTRACT_NAME, probe)
    write_figure(output_dir / FIGURE_NAME, probe)
    imported_previews = tuple(
        (control_id.removeprefix("primitive_").replace("_", " ").title(), shape)
        for control_id, stage, shape in probe.preview_shapes
        if stage == "step_imported"
    )
    write_shape_previews(
        output_dir / SHAPES_NAME,
        imported_previews,
        title="v0.43.0 Imported Primitive Controls",
        columns=3,
    )
    print(f"Wrote primitive round-trip artifacts to {output_dir}")


def main() -> None:
    """Parse command-line arguments and run the experiment."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument(
        "--fixture-dir", type=Path, default=Path("fixtures/primitive-round-trips")
    )
    parser.add_argument("--refresh-fixtures", action="store_true")
    arguments = parser.parse_args()
    run(arguments.output_dir, arguments.fixture_dir, refresh=arguments.refresh_fixtures)


if __name__ == "__main__":
    main()

