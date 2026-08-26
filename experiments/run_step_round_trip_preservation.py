"""Generate v0.48.0 STEP round-trip preservation evidence."""

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
from research_notes.step_round_trip_preservation import (  # noqa: E402
    CONTRACT_VERSION,
    PreservationProbe,
    probe_step_round_trip_preservation,
)


OBSERVATION_NAME = "step_preservation_observations.csv"
COMPARISON_NAME = "step_preservation_comparisons.csv"
SUMMARY_NAME = "step_preservation_summary.csv"
CONTRACT_NAME = "step_preservation_contract.json"
FIGURE_NAME = "step_round_trip_preservation.png"
SHAPES_NAME = "step_round_trip_preservation_shapes.png"
MANIFEST_NAME = "manifest.csv"

OBSERVATION_FIELDS = (
    "contract_version", "control_id", "stage", "file_name", "source_sha256",
    "source_bytes", "top_level_shape_count", "product_definition_count",
    "advanced_face_count", "names", "colors", "vertex_count", "edge_count",
    "face_count", "shell_count", "solid_count", "absolute_volume",
    "surface_area", "surface_counts", "maximum_vertex_tolerance",
    "maximum_edge_tolerance", "maximum_face_tolerance", "analyzer_valid",
)
COMPARISON_FIELDS = (
    "contract_version", "control_id", "source_semantics_match_truth",
    "source_attributes_match_truth", "structure_preserved",
    "semantics_preserved", "geometry_preserved", "topology_preserved",
    "attributes_preserved", "tolerances_preserved",
    "normalized_bytes_identical", "file_size_delta",
    "volume_absolute_difference", "surface_area_absolute_difference",
    "maximum_tolerance_difference",
)
SUMMARY_FIELDS = ("scope", "metric", "value")


def _float(value: float) -> str:
    return format(value, ".17g")


def _pairs(values: tuple[tuple[str, int], ...]) -> str:
    return "|".join(f"{name}:{value}" for name, value in values)


def _colors(values: tuple[tuple[float, float, float], ...]) -> str:
    return "|".join(",".join(_float(channel) for channel in color) for color in values)


def _csv_bytes(rows: list[dict[str, object]], fields: tuple[str, ...]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _write_csv(path: Path, rows: list[dict[str, object]], fields: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_csv_bytes(rows, fields))


def observation_rows(probe: PreservationProbe) -> list[dict[str, object]]:
    """Flatten structure, attributes, and B-Rep measurements by stage."""
    rows: list[dict[str, object]] = []
    for item in probe.observations:
        metrics = item.metrics
        rows.append({
            "contract_version": CONTRACT_VERSION,
            "control_id": item.control_id,
            "stage": item.stage,
            "file_name": item.file_name,
            "source_sha256": item.source_sha256,
            "source_bytes": item.source_bytes,
            "top_level_shape_count": item.top_level_shape_count,
            "product_definition_count": item.product_definition_count,
            "advanced_face_count": item.advanced_face_count,
            "names": "|".join(item.names),
            "colors": _colors(item.colors),
            "vertex_count": metrics.vertex_count,
            "edge_count": metrics.edge_count,
            "face_count": metrics.face_count,
            "shell_count": metrics.shell_count,
            "solid_count": metrics.solid_count,
            "absolute_volume": _float(metrics.absolute_volume),
            "surface_area": _float(metrics.surface_area),
            "surface_counts": _pairs(metrics.surface_counts),
            "maximum_vertex_tolerance": _float(metrics.maximum_vertex_tolerance),
            "maximum_edge_tolerance": _float(metrics.maximum_edge_tolerance),
            "maximum_face_tolerance": _float(metrics.maximum_face_tolerance),
            "analyzer_valid": int(metrics.analyzer_valid),
        })
    return rows


def comparison_rows(probe: PreservationProbe) -> list[dict[str, object]]:
    """Serialize dimension-specific preservation decisions."""
    return [
        {
            "contract_version": CONTRACT_VERSION,
            "control_id": item.control_id,
            "source_semantics_match_truth": int(item.source_semantics_match_truth),
            "source_attributes_match_truth": int(item.source_attributes_match_truth),
            "structure_preserved": int(item.structure_preserved),
            "semantics_preserved": int(item.semantics_preserved),
            "geometry_preserved": int(item.geometry_preserved),
            "topology_preserved": int(item.topology_preserved),
            "attributes_preserved": int(item.attributes_preserved),
            "tolerances_preserved": int(item.tolerances_preserved),
            "normalized_bytes_identical": int(item.normalized_bytes_identical),
            "file_size_delta": item.file_size_delta,
            "volume_absolute_difference": _float(item.volume_absolute_difference),
            "surface_area_absolute_difference": _float(
                item.surface_area_absolute_difference
            ),
            "maximum_tolerance_difference": _float(
                item.maximum_tolerance_difference
            ),
        }
        for item in probe.comparisons
    ]


def summary_rows(probe: PreservationProbe) -> list[dict[str, object]]:
    """Return compact counts used by documentation and regression tests."""
    dimensions = (
        "structure_preserved", "semantics_preserved", "geometry_preserved",
        "topology_preserved", "attributes_preserved", "tolerances_preserved",
    )
    rows = [
        {"scope": "corpus", "metric": "controls", "value": len(probe.controls)},
        {"scope": "corpus", "metric": "step_files", "value": len(probe.files)},
        {
            "scope": "source_truth",
            "metric": "attribute_matches",
            "value": sum(item.source_attributes_match_truth for item in probe.comparisons),
        },
        {
            "scope": "bytes",
            "metric": "identical_pairs",
            "value": sum(item.normalized_bytes_identical for item in probe.comparisons),
        },
    ]
    rows.extend(
        {
            "scope": "preservation",
            "metric": dimension,
            "value": sum(bool(getattr(item, dimension)) for item in probe.comparisons),
        }
        for dimension in dimensions
    )
    return rows


def _manifest_bytes(probe: PreservationProbe) -> bytes:
    rows = [
        {
            "control_id": item.control_id,
            "stage": item.stage,
            "file_name": item.file_name,
            "source_bytes": len(item.source_bytes),
            "source_sha256": item.source_sha256,
            "generator": "experiments/run_step_round_trip_preservation.py",
            "binding_distribution_version": probe.binding_distribution_version,
        }
        for item in probe.files
    ]
    return _csv_bytes(rows, tuple(rows[0]))


def handle_fixtures(path: Path, probe: PreservationProbe, *, refresh: bool) -> None:
    """Write or byte-verify the normalized source and re-export fixtures."""
    expected = {item.file_name: item.source_bytes for item in probe.files}
    expected[MANIFEST_NAME] = _manifest_bytes(probe)
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


def write_contract(path: Path, probe: PreservationProbe) -> None:
    """Write the interpretation and provenance contract."""
    payload = {
        "contract_version": CONTRACT_VERSION,
        "study_version": "v0.48.0",
        "title": "STEP Round-Trip Preservation",
        "controls": [
            {
                "control_id": item.control_id,
                "condition": item.condition,
                "expected_names": list(item.expected_names),
                "expected_colors": [list(color) for color in item.expected_colors],
            }
            for item in probe.controls
        ],
        "files": {
            item.file_name: item.source_sha256 for item in probe.files
        },
        "observation_primary_key": ["control_id", "stage"],
        "comparison_primary_key": ["control_id"],
        "dimension_rules": {
            "structure": "top-level shape and PRODUCT_DEFINITION counts",
            "semantics": "XCAF-imported free-shape names",
            "geometry": "volume, area, and support-surface inventory",
            "topology": "unique vertex, edge, face, shell, and solid counts",
            "attributes": "XCAF color-table RGB inventory",
            "tolerances": "maximum vertex, edge, and face tolerances",
            "bytes": "normalized physical-file bytes",
        },
        "claim_boundaries": [
            "semantic preservation is evaluated separately from byte identity",
            "the corpus contains one free shape per document and is not a general assembly test",
            "the color inventory does not prove every subshape color association",
            "the compound through-hole control demonstrates that declared source attributes may fail before the first import",
            "one pinned XCAF route is not cross-kernel portability evidence",
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_figure(path: Path, probe: PreservationProbe) -> None:
    """Plot preservation dimensions and physical-file changes."""
    labels = [item.control_id.removeprefix("named_colored_") for item in probe.comparisons]
    dimensions = (
        ("source_attributes_match_truth", "source color truth"),
        ("structure_preserved", "structure"),
        ("semantics_preserved", "semantics"),
        ("geometry_preserved", "geometry"),
        ("topology_preserved", "topology"),
        ("attributes_preserved", "attributes"),
        ("tolerances_preserved", "tolerances"),
        ("normalized_bytes_identical", "bytes"),
    )
    matrix = [
        [int(bool(getattr(item, field))) for field, _ in dimensions]
        for item in probe.comparisons
    ]
    figure, axes = plt.subplots(1, 2, figsize=(13.5, 4.8), constrained_layout=True)
    image = axes[0].imshow(matrix, vmin=0, vmax=1, cmap="RdYlGn", aspect="auto")
    axes[0].set_xticks(
        range(len(dimensions)),
        [label for _, label in dimensions],
        rotation=30,
        ha="right",
    )
    axes[0].set_yticks(range(len(labels)), labels)
    axes[0].set_title("Dimension-specific outcomes")
    figure.colorbar(image, ax=axes[0], ticks=(0, 1), label="Preserved")
    axes[1].bar(labels, [item.file_size_delta for item in probe.comparisons], color="#2563eb")
    axes[1].axhline(0.0, color="#111827", linewidth=0.8)
    axes[1].set_ylabel("Re-export minus source bytes")
    axes[1].set_title("Normalized physical-file size change")
    axes[1].tick_params(axis="x", rotation=22)
    figure.suptitle("v0.48.0 STEP Round-Trip Preservation")
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160)
    plt.close(figure)


def run(output_dir: Path, fixture_dir: Path, *, refresh: bool) -> None:
    """Run and serialize the complete v0.48.0 experiment."""
    probe = probe_step_round_trip_preservation()
    handle_fixtures(fixture_dir, probe, refresh=refresh)
    _write_csv(output_dir / OBSERVATION_NAME, observation_rows(probe), OBSERVATION_FIELDS)
    _write_csv(output_dir / COMPARISON_NAME, comparison_rows(probe), COMPARISON_FIELDS)
    _write_csv(output_dir / SUMMARY_NAME, summary_rows(probe), SUMMARY_FIELDS)
    write_contract(output_dir / CONTRACT_NAME, probe)
    write_figure(output_dir / FIGURE_NAME, probe)
    write_shape_previews(
        output_dir / SHAPES_NAME,
        probe.preview_shapes,
        title="v0.48.0 STEP Preservation Stages",
        columns=3,
    )
    print(f"Wrote STEP preservation artifacts to {output_dir}")


def main() -> None:
    """Parse command-line arguments and run the experiment."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=Path("fixtures/step-round-trip-preservation"),
    )
    parser.add_argument("--refresh-fixtures", action="store_true")
    arguments = parser.parse_args()
    run(arguments.output_dir, arguments.fixture_dir, refresh=arguments.refresh_fixtures)


if __name__ == "__main__":
    main()
