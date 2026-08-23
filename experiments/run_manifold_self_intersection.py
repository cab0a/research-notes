"""Generate the v0.37 manifoldness and aggregate-interference evidence."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

from research_notes.manifold_self_intersection import (  # noqa: E402
    ManifoldProbe,
    manifold_controls,
    probe_manifold_self_intersection,
)


OBSERVATIONS_NAME = "manifold_intersection_observations.csv"
VERTEX_LINKS_NAME = "vertex_link_observations.csv"
PAIR_RELATIONS_NAME = "shape_pair_relations.csv"
SELF_INTERSECTIONS_NAME = "self_intersection_observations.csv"
SUMMARY_NAME = "manifold_intersection_summary.csv"
CONTRACT_NAME = "manifold_intersection_contract.json"
FIGURE_NAME = "manifold_self_intersection.png"
SHAPES_NAME = "manifold_self_intersection_shapes.png"
MANIFEST_NAME = "manifest.csv"


def _value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(int(value))
    if isinstance(value, float):
        return format(value, ".17g")
    return str(value)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("CSV rows must not be empty")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(
            {key: _value(value) for key, value in row.items()} for row in rows
        )


def _fixture_rows(probe: ManifoldProbe) -> list[dict[str, object]]:
    return [
        {
            "control_id": item.fixture_id,
            "file_name": item.file_name,
            "source_bytes": len(item.source_bytes),
            "source_sha256": item.source_sha256,
            "binding_distribution_version": probe.binding_distribution_version,
            "binding_module_version": probe.binding_module_version,
            "step_processor": item.step_processor,
            "writer_status": item.writer_status,
            "reader_status": item.reader_status,
            "transferred_roots": item.transferred_roots,
        }
        for item in probe.fixtures
    ]


def _handle_fixtures(directory: Path, probe: ManifoldProbe, *, refresh: bool) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    expected = {item.file_name for item in probe.fixtures} | {MANIFEST_NAME}
    unexpected = sorted(
        path.name for path in directory.iterdir() if path.name not in expected
    )
    if unexpected:
        raise RuntimeError("unexpected fixture files: " + ", ".join(unexpected))
    manifest = _fixture_rows(probe)
    if refresh:
        for item in probe.fixtures:
            (directory / item.file_name).write_bytes(item.source_bytes)
        _write_csv(directory / MANIFEST_NAME, manifest)
        return
    for item in probe.fixtures:
        path = directory / item.file_name
        if not path.is_file() or path.read_bytes() != item.source_bytes:
            raise RuntimeError(f"committed fixture differs: {item.file_name}")
    with (directory / MANIFEST_NAME).open(encoding="utf-8", newline="") as handle:
        if list(csv.DictReader(handle)) != [
            {key: _value(value) for key, value in row.items()} for row in manifest
        ]:
            raise RuntimeError("committed fixture manifest differs")


def _summary_rows(probe: ManifoldProbe) -> list[dict[str, object]]:
    constructed = [row for row in probe.observations if row.stage == "constructed"]
    imported = [row for row in probe.observations if row.stage == "step_imported"]
    return [
        {
            "scope": "corpus",
            "metric": "control_count",
            "value": len(manifold_controls()),
        },
        {
            "scope": "corpus",
            "metric": "stage_observation_count",
            "value": len(probe.observations),
        },
        {
            "scope": "constructed",
            "metric": "topology_matches",
            "value": sum(row.topology_matches_control for row in constructed),
        },
        {
            "scope": "step_imported",
            "metric": "topology_matches",
            "value": sum(row.topology_matches_control for row in imported),
        },
        {
            "scope": "constructed",
            "metric": "relationship_matches",
            "value": sum(
                row.relationship_matches_control is True for row in constructed
            ),
        },
        {
            "scope": "step_imported",
            "metric": "relationship_matches",
            "value": sum(row.relationship_matches_control is True for row in imported),
        },
        {
            "scope": "constructed",
            "metric": "self_intersection_matches",
            "value": sum(
                row.self_intersection_matches_control is True for row in constructed
            ),
        },
        {
            "scope": "step_imported",
            "metric": "self_intersection_matches",
            "value": sum(
                row.self_intersection_matches_control is True for row in imported
            ),
        },
        {
            "scope": "corpus",
            "metric": "nonmanifold_vertex_observations",
            "value": sum(row.nonmanifold_vertex_count for row in probe.observations),
        },
        {
            "scope": "corpus",
            "metric": "maximum_measure_absolute_error",
            "value": max(row.measure_absolute_error for row in probe.pair_relations),
        },
        {
            "scope": "corpus",
            "metric": "maximum_self_intersection_quantity_absolute_error",
            "value": max(
                row.quantity_absolute_error for row in probe.self_intersections
            ),
        },
    ]


def _plot_summary(path: Path, probe: ManifoldProbe) -> None:
    constructed = [row for row in probe.pair_relations if row.stage == "constructed"]
    colors = {
        "disjoint": "#94a3b8",
        "point_contact": "#60a5fa",
        "edge_contact": "#34d399",
        "face_contact": "#fbbf24",
        "volume_overlap": "#f87171",
        "proper_crossing": "#c084fc",
    }
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.8))
    label_by_control = {
        "disjoint_boxes": "gap",
        "vertex_touching_boxes": "point",
        "edge_touching_boxes": "edge",
        "face_touching_boxes": "face",
        "overlapping_boxes": "volume",
        "separated_faces": "separated\nfaces",
        "crossing_faces": "crossing\nfaces",
    }
    labels = [label_by_control[row.control_id] for row in constructed]
    dimensions = [row.contact_dimension for row in constructed]
    positions = list(range(len(constructed)))
    axes[0].bar(
        positions,
        dimensions,
        color=[colors[row.relationship] for row in constructed],
        alpha=0.75,
    )
    axes[0].scatter(
        positions,
        dimensions,
        color=[colors[row.relationship] for row in constructed],
        edgecolor="#0f172a",
        linewidth=0.8,
        s=55,
        zorder=3,
    )
    for position, dimension in zip(positions, dimensions):
        axes[0].annotate(
            str(dimension),
            (position, dimension),
            xytext=(0, 8),
            textcoords="offset points",
            ha="center",
            fontsize=9,
            fontweight="bold",
        )
    axes[0].set_xticks(positions, labels, fontsize=8)
    axes[0].set_ylabel("Contact dimension")
    axes[0].set_yticks(
        [-1, 0, 1, 2, 3], ["none", "point", "curve", "surface", "volume"]
    )
    axes[0].set_ylim(-1.35, 3.45)
    axes[0].set_title("Controlled geometric relationships")
    checker_rows = [
        row for row in probe.self_intersections if row.stage == "constructed"
    ]
    checker_positions = list(range(len(checker_rows)))
    checker_labels = [row.control_id.replace("_", "\n") for row in checker_rows]
    edge_edge_counts = [row.edge_edge_interference_count for row in checker_rows]
    face_face_counts = [row.face_face_interference_count for row in checker_rows]
    axes[1].bar(
        checker_positions,
        edge_edge_counts,
        color="#0ea5e9",
        label="Edge/edge",
    )
    axes[1].bar(
        checker_positions,
        face_face_counts,
        bottom=edge_edge_counts,
        color="#a855f7",
        label="Face/face",
    )
    for position, row in zip(checker_positions, checker_rows, strict=True):
        height = row.edge_edge_interference_count + row.face_face_interference_count
        axes[1].annotate(
            f"d={row.intersection_dimension}",
            (position, height),
            xytext=(0, 7),
            textcoords="offset points",
            ha="center",
            fontsize=8,
        )
    axes[1].set_xticks(checker_positions, checker_labels, fontsize=8)
    axes[1].set_ylabel("Checker interference records")
    axes[1].set_ylim(0, 1.55)
    axes[1].set_title("Single-argument self-interference checks")
    axes[1].legend(frameon=False)
    controls = ["valid_tetrahedron", "pinched_tetrahedra", "nonmanifold_fan"]
    rows = [
        next(
            item
            for item in probe.observations
            if item.stage == "constructed" and item.control_id == control
        )
        for control in controls
    ]
    topology_labels = ["tetrahedron", "pinched\ntetrahedra", "three-face\nfan"]
    vertex_counts = [row.nonmanifold_vertex_count for row in rows]
    edge_counts = [row.nonmanifold_edge_count for row in rows]
    axes[2].bar(
        topology_labels,
        vertex_counts,
        label="Nonmanifold vertices",
        color="#ef4444",
    )
    axes[2].bar(
        topology_labels,
        edge_counts,
        bottom=vertex_counts,
        label="Nonmanifold edges",
        color="#7c3aed",
    )
    axes[2].set_ylabel("Detected count")
    axes[2].set_title("Topology checks are complementary")
    axes[2].legend(frameon=False)
    fig.suptitle(
        "Manifoldness and aggregate B-Rep interference controls",
        fontweight="bold",
    )
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _box_edges(
    origin: tuple[float, float, float],
) -> list[tuple[tuple[float, float, float], tuple[float, float, float]]]:
    x, y, z = origin
    points = [
        (x + dx, y + dy, z + dz) for dx in (0, 4) for dy in (0, 4) for dz in (0, 4)
    ]
    return [
        (a, b)
        for index, a in enumerate(points)
        for b in points[index + 1 :]
        if sum(first != second for first, second in zip(a, b)) == 1
    ]


def _plot_shapes(path: Path) -> None:
    cases = [
        ("Disjoint", (5, 0, 0), "#64748b"),
        ("Point contact", (4, 4, 4), "#3b82f6"),
        ("Edge contact", (4, 4, 0), "#10b981"),
        ("Face contact", (4, 0, 0), "#f59e0b"),
        ("Volume overlap", (3, 1, 1), "#ef4444"),
    ]
    fig = plt.figure(figsize=(13, 10))
    for index, (title, origin, color) in enumerate(cases, start=1):
        axis = fig.add_subplot(3, 3, index, projection="3d")
        for first, second in _box_edges((0, 0, 0)):
            axis.plot(*zip(first, second), color="#1e293b", linewidth=1)
        for first, second in _box_edges(origin):
            axis.plot(*zip(first, second), color=color, linewidth=1.5)
        axis.set_title(title)
        axis.set_xlim(-0.5, 9)
        axis.set_ylim(-0.5, 9)
        axis.set_zlim(-0.5, 9)
        axis.set_axis_off()
    axis = fig.add_subplot(3, 3, 6, projection="3d")
    axis.plot([-2, 2], [-1, -1], [0, 0], color="#0284c7", linewidth=3)
    axis.plot([-2, 2], [1, 1], [0, 0], color="#0284c7", linewidth=3)
    axis.set_title("Separated edges")
    axis.set_xlim(-2.5, 2.5)
    axis.set_ylim(-2.5, 2.5)
    axis.set_zlim(-2.5, 2.5)
    axis.set_axis_off()
    axis = fig.add_subplot(3, 3, 7, projection="3d")
    axis.plot([-2, 2], [-2, 2], [0, 0], color="#dc2626", linewidth=3)
    axis.plot([-2, 2], [2, -2], [0, 0], color="#dc2626", linewidth=3)
    axis.scatter([0], [0], [0], color="#111827", s=24)
    axis.set_title("Crossing edges")
    axis.set_xlim(-2.5, 2.5)
    axis.set_ylim(-2.5, 2.5)
    axis.set_zlim(-2.5, 2.5)
    axis.set_axis_off()
    axis = fig.add_subplot(3, 3, 8, projection="3d")
    grid_x, grid_y = np.meshgrid([-2, 2], [-2, 2])
    axis.plot_wireframe(
        grid_x,
        grid_y,
        np.zeros((2, 2)),
        color="#64748b",
        alpha=0.75,
    )
    axis.plot_wireframe(
        grid_x,
        grid_y,
        np.ones((2, 2)),
        color="#0ea5e9",
        alpha=0.75,
    )
    axis.set_title("Separated faces")
    axis.set_xlim(-2.5, 2.5)
    axis.set_ylim(-2.5, 2.5)
    axis.set_zlim(-2.5, 2.5)
    axis.set_axis_off()
    axis = fig.add_subplot(3, 3, 9, projection="3d")
    axis.plot([-2, 2], [0, 0], [0, 0], color="#dc2626", linewidth=4)
    axis.plot_wireframe(
        grid_x,
        grid_y,
        np.zeros((2, 2)),
        color="#64748b",
        alpha=0.7,
    )
    vertical_x, vertical_z = np.meshgrid([-1, 1], [-1, 1])
    axis.plot_wireframe(
        vertical_x,
        np.zeros((2, 2)),
        vertical_z,
        color="#a855f7",
        alpha=0.7,
    )
    axis.set_title("Transverse face crossing")
    axis.set_xlim(-2.5, 2.5)
    axis.set_ylim(-2.5, 2.5)
    axis.set_zlim(-2.5, 2.5)
    axis.set_axis_off()
    fig.suptitle("Synthetic STEP controls (schematic)", fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def run(output_dir: Path, fixture_dir: Path, *, refresh_fixtures: bool) -> None:
    """Run the study and write deterministic evidence."""
    output_dir.mkdir(parents=True, exist_ok=True)
    probe = probe_manifold_self_intersection()
    _handle_fixtures(fixture_dir, probe, refresh=refresh_fixtures)
    _write_csv(
        output_dir / OBSERVATIONS_NAME,
        [
            {"platform_label": probe.platform_label, **asdict(row)}
            for row in probe.observations
        ],
    )
    _write_csv(
        output_dir / VERTEX_LINKS_NAME,
        [
            {"platform_label": probe.platform_label, **asdict(row)}
            for row in probe.vertex_links
        ],
    )
    _write_csv(
        output_dir / PAIR_RELATIONS_NAME,
        [
            {"platform_label": probe.platform_label, **asdict(row)}
            for row in probe.pair_relations
        ],
    )
    _write_csv(
        output_dir / SELF_INTERSECTIONS_NAME,
        [
            {"platform_label": probe.platform_label, **asdict(row)}
            for row in probe.self_intersections
        ],
    )
    summary = _summary_rows(probe)
    _write_csv(output_dir / SUMMARY_NAME, summary)
    contract = {
        "schema_version": "v0.37.0",
        "platform_label": probe.platform_label,
        "binding_distribution_version": probe.binding_distribution_version,
        "binding_module_version": probe.binding_module_version,
        "controls": [asdict(control) for control in manifold_controls()],
        "summary": summary,
    }
    (output_dir / CONTRACT_NAME).write_text(
        json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _plot_summary(output_dir / FIGURE_NAME, probe)
    _plot_shapes(output_dir / SHAPES_NAME)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate controlled vertex manifoldness and geometric intersections."
    )
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument(
        "--fixture-dir", type=Path, default=Path("fixtures/manifold-self-intersection")
    )
    parser.add_argument("--refresh-fixtures", action="store_true")
    args = parser.parse_args()
    run(args.output_dir, args.fixture_dir, refresh_fixtures=args.refresh_fixtures)
    print(f"Wrote v0.37 evidence to {args.output_dir}")


if __name__ == "__main__":
    main()
