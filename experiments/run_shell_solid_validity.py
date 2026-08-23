"""Evaluate controlled shell and solid validity before and after STEP exchange."""

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

from research_notes.shell_solid_validity import (  # noqa: E402
    EdgeIncidenceObservation,
    FaceComponentObservation,
    KernelShellObservation,
    ShellSolidObservation,
    ShellSolidProbe,
    probe_shell_solid_validity,
    shell_solid_controls,
)


MANIFEST_NAME = "manifest.csv"
OBSERVATIONS_NAME = "shell_solid_observations.csv"
EDGE_INCIDENCE_NAME = "shell_solid_edge_incidence.csv"
COMPONENTS_NAME = "shell_solid_components.csv"
SHELLS_NAME = "shell_validity_observations.csv"
SUMMARY_NAME = "shell_solid_summary.csv"
CONTRACT_NAME = "shell_solid_contract.json"
FIGURE_NAME = "shell_solid_validity.png"
SHAPES_FIGURE_NAME = "shell_solid_shapes.png"

OBSERVATION_FIELDS = (
    "platform_label",
    "stage",
    "control_id",
    "condition",
    "observed_shape_type",
    "vertex_count",
    "edge_count",
    "face_count",
    "shell_count",
    "solid_count",
    "face_component_count",
    "boundary_edge_count",
    "boundary_component_count",
    "boundary_degree_violation_count",
    "manifold_pair_edge_count",
    "nonmanifold_edge_count",
    "euler_characteristic",
    "closed_by_incidence",
    "orientable_manifold",
    "current_orientation_consistent",
    "minimum_face_flips",
    "closed_oriented_shell_candidate",
    "topology_matches_control",
    "kernel_analyzer_valid",
    "kernel_signed_volume",
    "analytic_volume_magnitude",
    "volume_contract_eligible",
    "volume_magnitude_absolute_error",
    "volume_sign",
    "kernel_solid_statuses",
)
EDGE_FIELDS = (
    "platform_label",
    "stage",
    "control_id",
    "edge_index",
    "use_count",
    "incident_face_count",
    "incident_face_indices",
    "orientations",
    "boundary",
    "manifold_pair",
    "nonmanifold",
    "paired_orientations_opposed",
)
COMPONENT_FIELDS = (
    "platform_label",
    "stage",
    "control_id",
    "component_index",
    "face_indices",
    "vertex_count",
    "edge_count",
    "face_count",
    "euler_characteristic",
    "boundary_edge_count",
    "nonmanifold_edge_count",
    "closed_by_incidence",
)
SHELL_FIELDS = (
    "platform_label",
    "stage",
    "control_id",
    "shell_index",
    "orientation",
    "vertex_count",
    "edge_count",
    "face_count",
    "closed_status",
    "orientation_status",
)
MANIFEST_FIELDS = (
    "control_id",
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
    "step_closed_shell_count",
    "step_open_shell_count",
    "step_manifold_solid_brep_count",
    "step_oriented_closed_shell_count",
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


def write_csv(
    path: Path, rows: Sequence[dict[str, str]], fields: Sequence[str]
) -> None:
    """Write deterministic UTF-8 CSV evidence."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def observation_row(
    item: ShellSolidObservation, platform_label: str
) -> dict[str, str]:
    """Flatten one whole-shape observation."""
    return {
        "platform_label": platform_label,
        "stage": item.stage,
        "control_id": item.control_id,
        "condition": item.condition,
        "observed_shape_type": item.observed_shape_type,
        "vertex_count": str(item.vertex_count),
        "edge_count": str(item.edge_count),
        "face_count": str(item.face_count),
        "shell_count": str(item.shell_count),
        "solid_count": str(item.solid_count),
        "face_component_count": str(item.face_component_count),
        "boundary_edge_count": str(item.boundary_edge_count),
        "boundary_component_count": str(item.boundary_component_count),
        "boundary_degree_violation_count": str(
            item.boundary_degree_violation_count
        ),
        "manifold_pair_edge_count": str(item.manifold_pair_edge_count),
        "nonmanifold_edge_count": str(item.nonmanifold_edge_count),
        "euler_characteristic": str(item.euler_characteristic),
        "closed_by_incidence": _flag(item.closed_by_incidence),
        "orientable_manifold": _flag(item.orientable_manifold),
        "current_orientation_consistent": _flag(
            item.current_orientation_consistent
        ),
        "minimum_face_flips": _optional_int(item.minimum_face_flips),
        "closed_oriented_shell_candidate": _flag(
            item.closed_oriented_shell_candidate
        ),
        "topology_matches_control": _flag(item.topology_matches_control),
        "kernel_analyzer_valid": _flag(item.kernel_analyzer_valid),
        "kernel_signed_volume": _float(item.kernel_signed_volume),
        "analytic_volume_magnitude": _optional_float(
            item.analytic_volume_magnitude
        ),
        "volume_contract_eligible": _flag(item.volume_contract_eligible),
        "volume_magnitude_absolute_error": _optional_float(
            item.volume_magnitude_absolute_error
        ),
        "volume_sign": item.volume_sign,
        "kernel_solid_statuses": ";".join(item.kernel_solid_statuses),
    }


def edge_row(
    item: EdgeIncidenceObservation, platform_label: str
) -> dict[str, str]:
    """Flatten one unique-edge incidence observation."""
    return {
        "platform_label": platform_label,
        "stage": item.stage,
        "control_id": item.control_id,
        "edge_index": str(item.edge_index),
        "use_count": str(item.use_count),
        "incident_face_count": str(item.incident_face_count),
        "incident_face_indices": ";".join(map(str, item.incident_face_indices)),
        "orientations": ";".join(item.orientations),
        "boundary": _flag(item.boundary),
        "manifold_pair": _flag(item.manifold_pair),
        "nonmanifold": _flag(item.nonmanifold),
        "paired_orientations_opposed": _optional_flag(
            item.paired_orientations_opposed
        ),
    }


def component_row(
    item: FaceComponentObservation, platform_label: str
) -> dict[str, str]:
    """Flatten one connected face component."""
    return {
        "platform_label": platform_label,
        "stage": item.stage,
        "control_id": item.control_id,
        "component_index": str(item.component_index),
        "face_indices": ";".join(map(str, item.face_indices)),
        "vertex_count": str(item.vertex_count),
        "edge_count": str(item.edge_count),
        "face_count": str(item.face_count),
        "euler_characteristic": str(item.euler_characteristic),
        "boundary_edge_count": str(item.boundary_edge_count),
        "nonmanifold_edge_count": str(item.nonmanifold_edge_count),
        "closed_by_incidence": _flag(item.closed_by_incidence),
    }


def shell_row(
    item: KernelShellObservation, platform_label: str
) -> dict[str, str]:
    """Flatten one backend shell report."""
    return {
        "platform_label": platform_label,
        "stage": item.stage,
        "control_id": item.control_id,
        "shell_index": str(item.shell_index),
        "orientation": item.orientation,
        "vertex_count": str(item.vertex_count),
        "edge_count": str(item.edge_count),
        "face_count": str(item.face_count),
        "closed_status": item.closed_status,
        "orientation_status": item.orientation_status,
    }


def manifest_rows(probe: ShellSolidProbe) -> list[dict[str, str]]:
    """Describe every synthetic STEP fixture and its runtime provenance."""
    controls = {item.control_id: item for item in shell_solid_controls()}
    return [
        {
            "control_id": item.control_id,
            "file_name": item.file_name,
            "source_bytes": str(len(item.source_bytes)),
            "source_sha256": item.source_sha256,
            "generator": controls[item.control_id].condition,
            "binding_distribution_version": probe.binding_distribution_version,
            "binding_module_version": probe.binding_module_version,
            "step_processor": probe.step_processor,
            "writer_status": item.writer_status,
            "reader_status": item.reader_status,
            "transferred_roots": str(item.transferred_roots),
            "step_closed_shell_count": str(item.step_closed_shell_count),
            "step_open_shell_count": str(item.step_open_shell_count),
            "step_manifold_solid_brep_count": str(
                item.step_manifold_solid_brep_count
            ),
            "step_oriented_closed_shell_count": str(
                item.step_oriented_closed_shell_count
            ),
        }
        for item in probe.fixtures
    ]


def handle_fixtures(
    fixture_dir: Path, probe: ShellSolidProbe, *, refresh: bool
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
    rows = manifest_rows(probe)
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


def _by_control_stage(
    probe: ShellSolidProbe, control_id: str, stage: str
) -> ShellSolidObservation:
    matches = [
        item
        for item in probe.observations
        if item.control_id == control_id and item.stage == stage
    ]
    if len(matches) != 1:
        raise RuntimeError("expected exactly one control-stage observation")
    return matches[0]


def summary_rows(probe: ShellSolidProbe) -> list[dict[str, str]]:
    """Build compact evidence for topology, validity, volume, and exchange."""
    constructed = [item for item in probe.observations if item.stage == "constructed"]
    imported = [item for item in probe.observations if item.stage == "step_imported"]
    reversed_constructed = _by_control_stage(probe, "reversed_box", "constructed")
    reversed_imported = _by_control_stage(probe, "reversed_box", "step_imported")
    flipped_constructed = _by_control_stage(
        probe, "flipped_face_box", "constructed"
    )
    flipped_imported = _by_control_stage(probe, "flipped_face_box", "step_imported")
    fan_constructed = _by_control_stage(probe, "nonmanifold_fan", "constructed")
    fan_imported = _by_control_stage(probe, "nonmanifold_fan", "step_imported")
    disconnected_constructed = _by_control_stage(
        probe, "disconnected_faces", "constructed"
    )
    disconnected_imported = _by_control_stage(
        probe, "disconnected_faces", "step_imported"
    )
    eligible_errors = [
        float(item.volume_magnitude_absolute_error)
        for item in probe.observations
        if item.volume_magnitude_absolute_error is not None
    ]
    return [
        {"scope": "fixture", "metric": "control_count", "value": "7"},
        {"scope": "fixture", "metric": "step_file_count", "value": "7"},
        {
            "scope": "topology",
            "metric": "control_stage_observation_count",
            "value": str(len(probe.observations)),
        },
        {
            "scope": "topology",
            "metric": "topology_matches_control_count",
            "value": str(sum(item.topology_matches_control for item in probe.observations)),
        },
        {
            "scope": "constructed",
            "metric": "closed_by_incidence_count",
            "value": str(sum(item.closed_by_incidence for item in constructed)),
        },
        {
            "scope": "constructed",
            "metric": "boundary_edge_count",
            "value": str(sum(item.boundary_edge_count for item in constructed)),
        },
        {
            "scope": "constructed",
            "metric": "nonmanifold_edge_count",
            "value": str(sum(item.nonmanifold_edge_count for item in constructed)),
        },
        {
            "scope": "constructed",
            "metric": "closed_oriented_shell_candidate_count",
            "value": str(
                sum(item.closed_oriented_shell_candidate for item in constructed)
            ),
        },
        {
            "scope": "kernel",
            "metric": "constructed_analyzer_true_but_contract_false_count",
            "value": str(
                sum(
                    item.kernel_analyzer_valid
                    and not item.closed_oriented_shell_candidate
                    for item in constructed
                )
            ),
        },
        {
            "scope": "kernel",
            "metric": "imported_analyzer_true_but_contract_false_count",
            "value": str(
                sum(
                    item.kernel_analyzer_valid
                    and not item.closed_oriented_shell_candidate
                    for item in imported
                )
            ),
        },
        {
            "scope": "volume",
            "metric": "maximum_eligible_magnitude_absolute_error",
            "value": _float(max(eligible_errors)),
        },
        {
            "scope": "exchange",
            "metric": "reversed_box_constructed_volume_sign",
            "value": reversed_constructed.volume_sign,
        },
        {
            "scope": "exchange",
            "metric": "reversed_box_imported_volume_sign",
            "value": reversed_imported.volume_sign,
        },
        {
            "scope": "exchange",
            "metric": "flipped_face_constructed_minimum_flips",
            "value": _optional_int(flipped_constructed.minimum_face_flips),
        },
        {
            "scope": "exchange",
            "metric": "flipped_face_imported_minimum_flips",
            "value": _optional_int(flipped_imported.minimum_face_flips),
        },
        {
            "scope": "exchange",
            "metric": "nonmanifold_fan_shell_count_change",
            "value": f"{fan_constructed.shell_count}->{fan_imported.shell_count}",
        },
        {
            "scope": "exchange",
            "metric": "disconnected_shell_count_change",
            "value": (
                f"{disconnected_constructed.shell_count}"
                f"->{disconnected_imported.shell_count}"
            ),
        },
        {
            "scope": "exchange",
            "metric": "disconnected_kernel_analyzer_change",
            "value": (
                f"{_flag(disconnected_constructed.kernel_analyzer_valid)}"
                f"->{_flag(disconnected_imported.kernel_analyzer_valid)}"
            ),
        },
    ]


def write_contract(path: Path, probe: ShellSolidProbe) -> None:
    """Write the versioned truth, evidence, and claim-boundary contract."""
    payload = {
        "schema": "research-notes.shell-solid-validity",
        "schema_version": "1.0",
        "release": "v0.35.0",
        "platform_label": probe.platform_label,
        "backend": {
            "distribution": "cadquery-ocp",
            "distribution_version": probe.binding_distribution_version,
            "module_version": probe.binding_module_version,
            "step_processor": probe.step_processor,
        },
        "controls": [
            {
                "control_id": item.control_id,
                "condition": item.condition,
                "shape_class": item.shape_class,
                "expected_counts": {
                    "vertices": item.expected_vertex_count,
                    "edges": item.expected_edge_count,
                    "faces": item.expected_face_count,
                    "face_components": item.expected_face_component_count,
                    "boundary_edges": item.expected_boundary_edge_count,
                    "nonmanifold_edges": item.expected_nonmanifold_edge_count,
                    "euler_characteristic": item.expected_euler_characteristic,
                },
                "expected_closed_by_incidence": item.expected_closed_by_incidence,
                "expected_orientable_manifold": item.expected_orientable_manifold,
                "analytic_volume_magnitude": item.analytic_volume_magnitude,
            }
            for item in shell_solid_controls()
        ],
        "exchange_changes": {
            "reversed_box_volume_sign": [
                _by_control_stage(probe, "reversed_box", "constructed").volume_sign,
                _by_control_stage(probe, "reversed_box", "step_imported").volume_sign,
            ],
            "flipped_face_current_orientation_consistent": [
                _by_control_stage(
                    probe, "flipped_face_box", "constructed"
                ).current_orientation_consistent,
                _by_control_stage(
                    probe, "flipped_face_box", "step_imported"
                ).current_orientation_consistent,
            ],
            "nonmanifold_fan_shell_count": [
                _by_control_stage(probe, "nonmanifold_fan", "constructed").shell_count,
                _by_control_stage(probe, "nonmanifold_fan", "step_imported").shell_count,
            ],
            "disconnected_faces_shell_count": [
                _by_control_stage(
                    probe, "disconnected_faces", "constructed"
                ).shell_count,
                _by_control_stage(
                    probe, "disconnected_faces", "step_imported"
                ).shell_count,
            ],
        },
        "limitations": [
            "The corpus contains seven small synthetic analytic controls and one pinned OCCT route.",
            "Edge-use incidence does not detect every vertex-neighborhood or geometric self-intersection defect.",
            "Euler characteristic is an invariant check, not a complete validity proof.",
            "Volume properties are accepted only for closed, orientable, consistently oriented single face components.",
            "STEP import may normalize orientation or split shell containers; local topology identities are not preserved contracts.",
            "No sewing, healing, tolerance modification, self-intersection repair, or arbitrary-file safety claim is made.",
        ],
        "questions": [
            "Which STEP translator changes should be reported as normalization, repair, or semantic drift?",
            "How should vertex-manifoldness and shell self-intersection be checked independently of one kernel?",
            "Which original-to-imported face correspondence remains defensible after shell splitting or reorientation?",
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def write_figure(path: Path, probe: ShellSolidProbe) -> None:
    """Visualize validity layers, topology invariants, and volume behavior."""
    controls = shell_solid_controls()
    labels = [item.control_id.replace("_", "\n") for item in controls]
    figure, axes = plt.subplots(2, 2, figsize=(15.5, 10.2), constrained_layout=True)
    contract_axis, euler_axis, volume_axis, exchange_axis = axes.flat

    constructed = [
        _by_control_stage(probe, item.control_id, "constructed")
        for item in controls
    ]
    metrics = np.array(
        [
            [
                item.closed_by_incidence,
                item.orientable_manifold,
                item.current_orientation_consistent,
                item.face_component_count == 1,
                item.closed_oriented_shell_candidate,
                item.kernel_analyzer_valid,
            ]
            for item in constructed
        ],
        dtype=float,
    )
    contract_axis.imshow(metrics.T, cmap="RdYlGn", vmin=0.0, vmax=1.0, aspect="auto")
    contract_axis.set_xticks(range(len(labels)), labels, fontsize=8)
    contract_axis.set_yticks(
        range(metrics.shape[1]),
        [
            "closed by incidence",
            "orientable manifold",
            "current orientation",
            "one face component",
            "project shell candidate",
            "kernel analyzer valid",
        ],
        fontsize=8,
    )
    for row in range(metrics.shape[1]):
        for column in range(metrics.shape[0]):
            contract_axis.text(
                column,
                row,
                "yes" if metrics[column, row] else "no",
                ha="center",
                va="center",
                fontsize=7,
            )
    contract_axis.set_title("Constructed validity layers are not interchangeable")

    positions = np.arange(len(controls))
    width = 0.2
    euler_axis.bar(
        positions - 1.5 * width,
        [item.vertex_count for item in constructed],
        width,
        label="V",
        color="#2563eb",
    )
    euler_axis.bar(
        positions - 0.5 * width,
        [item.edge_count for item in constructed],
        width,
        label="E",
        color="#ef4444",
    )
    euler_axis.bar(
        positions + 0.5 * width,
        [item.face_count for item in constructed],
        width,
        label="F",
        color="#10b981",
    )
    euler_axis.bar(
        positions + 1.5 * width,
        [item.euler_characteristic for item in constructed],
        width,
        label="V-E+F",
        color="#7c3aed",
    )
    euler_axis.set_xticks(positions, labels, fontsize=8)
    euler_axis.set_ylabel("Count")
    euler_axis.set_title("Independent topology counts and Euler characteristic")
    euler_axis.legend(ncol=4, fontsize=8)
    euler_axis.grid(axis="y", alpha=0.25)

    volume_controls = ("valid_box", "reversed_box", "flipped_face_box", "valid_torus")
    volume_labels = [item.replace("_", "\n") for item in volume_controls]
    volume_positions = np.arange(len(volume_controls))
    for offset, stage, color in (
        (-0.18, "constructed", "#2563eb"),
        (0.18, "step_imported", "#f59e0b"),
    ):
        values = [
            _by_control_stage(probe, control_id, stage).kernel_signed_volume
            for control_id in volume_controls
        ]
        volume_axis.bar(
            volume_positions + offset,
            values,
            0.36,
            label=stage.replace("_", " "),
            color=color,
        )
    volume_axis.axhline(0.0, color="#111827", linewidth=0.8)
    volume_axis.set_xticks(volume_positions, volume_labels, fontsize=8)
    volume_axis.set_ylabel("Signed volume")
    volume_axis.set_title("Volume signs expose orientation and exchange changes")
    volume_axis.legend(fontsize=8)
    volume_axis.grid(axis="y", alpha=0.25)
    volume_axis.text(
        1.0,
        -105.0,
        "reversed solid: negative -> positive",
        ha="center",
        fontsize=8,
        color="#991b1b",
    )

    change_controls = ("flipped_face_box", "nonmanifold_fan", "disconnected_faces")
    change_labels = [item.replace("_", "\n") for item in change_controls]
    constructed_shells = [
        _by_control_stage(probe, item, "constructed").shell_count
        for item in change_controls
    ]
    imported_shells = [
        _by_control_stage(probe, item, "step_imported").shell_count
        for item in change_controls
    ]
    change_positions = np.arange(len(change_controls))
    exchange_axis.bar(
        change_positions - 0.18,
        constructed_shells,
        0.36,
        label="constructed",
        color="#2563eb",
    )
    exchange_axis.bar(
        change_positions + 0.18,
        imported_shells,
        0.36,
        label="STEP imported",
        color="#f59e0b",
    )
    exchange_axis.set_xticks(change_positions, change_labels, fontsize=8)
    exchange_axis.set_ylabel("Kernel shell count")
    exchange_axis.set_yticks(range(0, 4))
    exchange_axis.set_title("STEP import may reorient or split shell containers")
    exchange_axis.legend(fontsize=8)
    exchange_axis.grid(axis="y", alpha=0.25)
    exchange_axis.text(
        0.0,
        1.18,
        "one face flip -> zero",
        ha="center",
        fontsize=8,
        color="#065f46",
    )

    figure.suptitle("v0.35.0 Shell and Solid Validity")
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160)
    plt.close(figure)


def _cube_faces(origin: tuple[float, float, float]) -> list[list[tuple[float, float, float]]]:
    x, y, z = origin
    vertices = np.array(
        [
            [x, y, z],
            [x + 4, y, z],
            [x + 4, y + 5, z],
            [x, y + 5, z],
            [x, y, z + 6],
            [x + 4, y, z + 6],
            [x + 4, y + 5, z + 6],
            [x, y + 5, z + 6],
        ],
        dtype=float,
    )
    return [
        vertices[indexes].tolist()
        for indexes in (
            [0, 1, 2, 3],
            [4, 5, 6, 7],
            [0, 1, 5, 4],
            [1, 2, 6, 5],
            [2, 3, 7, 6],
            [3, 0, 4, 7],
        )
    ]


def _style_3d(axis: object, title: str) -> None:
    axis.set_title(title, fontsize=9)
    axis.set_xticks([])
    axis.set_yticks([])
    axis.set_zticks([])
    axis.set_box_aspect((1.0, 1.0, 1.0))
    axis.view_init(elev=24, azim=-52)


def write_shapes_figure(path: Path) -> None:
    """Render the seven analytic controls for human visual inspection."""
    figure = plt.figure(figsize=(16.0, 8.0), constrained_layout=True)
    axes = [figure.add_subplot(2, 4, index, projection="3d") for index in range(1, 8)]

    for axis, title, color in (
        (axes[0], "Valid outward box", "#60a5fa"),
        (axes[1], "Whole box reversed", "#a78bfa"),
    ):
        axis.add_collection3d(
            Poly3DCollection(
                _cube_faces((0.0, 0.0, 0.0)),
                facecolors=color,
                edgecolors="#1f2937",
                linewidths=0.8,
                alpha=0.72,
            )
        )
        axis.set_xlim(-1, 5)
        axis.set_ylim(-1, 6)
        axis.set_zlim(-1, 7)
        _style_3d(axis, title)

    open_faces = _cube_faces((0.0, 0.0, 0.0))
    del open_faces[1]
    axes[2].add_collection3d(
        Poly3DCollection(
            open_faces,
            facecolors="#fbbf24",
            edgecolors="#1f2937",
            linewidths=0.8,
            alpha=0.72,
        )
    )
    axes[2].plot(
        [0, 4, 4, 0, 0],
        [0, 0, 5, 5, 0],
        [6, 6, 6, 6, 6],
        color="#dc2626",
        linewidth=2.5,
    )
    axes[2].set_xlim(-1, 5)
    axes[2].set_ylim(-1, 6)
    axes[2].set_zlim(-1, 7)
    _style_3d(axes[2], "Open box: top face missing")

    cube = _cube_faces((0.0, 0.0, 0.0))
    axes[3].add_collection3d(
        Poly3DCollection(
            cube,
            facecolors=["#fb7185" if index == 3 else "#6ee7b7" for index in range(6)],
            edgecolors="#1f2937",
            linewidths=0.8,
            alpha=0.75,
        )
    )
    axes[3].set_xlim(-1, 5)
    axes[3].set_ylim(-1, 6)
    axes[3].set_zlim(-1, 7)
    _style_3d(axes[3], "Closed shell: one face flipped")

    fan_faces = [
        [(0, 0, 0), (3, 0, 0), (0, 2, 0)],
        [(0, 0, 0), (3, 0, 0), (0, 0, 2)],
        [(0, 0, 0), (3, 0, 0), (0, -2, 0)],
    ]
    axes[4].add_collection3d(
        Poly3DCollection(
            fan_faces,
            facecolors=["#60a5fa", "#fbbf24", "#fb7185"],
            edgecolors="#1f2937",
            linewidths=0.8,
            alpha=0.76,
        )
    )
    axes[4].plot([0, 3], [0, 0], [0, 0], color="#dc2626", linewidth=4)
    axes[4].set_xlim(-0.5, 3.5)
    axes[4].set_ylim(-2.5, 2.5)
    axes[4].set_zlim(-0.5, 2.5)
    _style_3d(axes[4], "Nonmanifold: three faces share edge")

    u_grid, v_grid = np.meshgrid(
        np.linspace(0.0, 2.0 * math.pi, 90),
        np.linspace(0.0, 2.0 * math.pi, 45),
    )
    torus_x = (4.0 + 1.5 * np.cos(v_grid)) * np.cos(u_grid)
    torus_y = (4.0 + 1.5 * np.cos(v_grid)) * np.sin(u_grid)
    torus_z = 1.5 * np.sin(v_grid)
    axes[5].plot_surface(
        torus_x, torus_y, torus_z, color="#34d399", alpha=0.78, linewidth=0
    )
    axes[5].set_xlim(-6, 6)
    axes[5].set_ylim(-6, 6)
    axes[5].set_zlim(-3, 3)
    _style_3d(axes[5], "Valid torus: Euler characteristic 0")

    triangles = [
        [(0, 0, 0), (2, 0, 0), (0, 2, 0)],
        [(5, 0, 0), (7, 0, 0), (5, 2, 0)],
    ]
    axes[6].add_collection3d(
        Poly3DCollection(
            triangles,
            facecolors=["#60a5fa", "#f59e0b"],
            edgecolors="#1f2937",
            linewidths=1.0,
            alpha=0.8,
        )
    )
    axes[6].set_xlim(-1, 8)
    axes[6].set_ylim(-1, 3)
    axes[6].set_zlim(-1, 1)
    _style_3d(axes[6], "Disconnected: two face components")

    figure.suptitle("Synthetic STEP Geometry Controls for v0.35.0")
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
    """Run the complete controlled shell/solid validity experiment."""
    probe = probe_shell_solid_validity(platform_label=platform_label)
    handle_fixtures(fixture_dir, probe, refresh=refresh)
    write_csv(
        output_dir / OBSERVATIONS_NAME,
        [observation_row(item, probe.platform_label) for item in probe.observations],
        OBSERVATION_FIELDS,
    )
    write_csv(
        output_dir / EDGE_INCIDENCE_NAME,
        [edge_row(item, probe.platform_label) for item in probe.edge_observations],
        EDGE_FIELDS,
    )
    write_csv(
        output_dir / COMPONENTS_NAME,
        [
            component_row(item, probe.platform_label)
            for item in probe.component_observations
        ],
        COMPONENT_FIELDS,
    )
    write_csv(
        output_dir / SHELLS_NAME,
        [shell_row(item, probe.platform_label) for item in probe.shell_observations],
        SHELL_FIELDS,
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
        default=Path("fixtures/shell-solid-validity"),
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
    print(f"Wrote shell and solid validity artifacts to {arguments.output_dir}")


if __name__ == "__main__":
    main()
