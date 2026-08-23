"""Evaluate face and edge correspondence across STEP import and healing."""

from __future__ import annotations

import argparse
import csv
import importlib.metadata
import io
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402
from matplotlib.patches import Polygon, Rectangle  # noqa: E402

from research_notes.shape_correspondence import (  # noqa: E402
    ShapeCorrespondenceProbe,
    probe_shape_correspondence,
)


FACE_NAME = "shape_correspondence_faces.csv"
CANDIDATE_NAME = "shape_correspondence_candidates.csv"
RELATION_NAME = "shape_correspondence_relations.csv"
EDGE_NAME = "shape_correspondence_edges.csv"
EDGE_CANDIDATE_NAME = "shape_correspondence_edge_candidates.csv"
EDGE_RELATION_NAME = "shape_correspondence_edge_relations.csv"
SUMMARY_NAME = "shape_correspondence_summary.csv"
CONTRACT_NAME = "shape_correspondence_contract.json"
FIGURE_NAME = "shape_correspondence.png"
SHAPES_NAME = "shape_correspondence_shapes.png"
MANIFEST_NAME = "manifest.csv"


def _float(value: float | None) -> str:
    return "" if value is None else format(value, ".17g")


def _values(values: tuple[object, ...]) -> str:
    return "|".join(str(value) for value in values)


def _csv_bytes(rows: list[dict[str, object]], fields: tuple[str, ...]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _write_csv(
    path: Path, rows: list[dict[str, object]], fields: tuple[str, ...]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_csv_bytes(rows, fields))


def _face_rows(probe: ShapeCorrespondenceProbe) -> list[dict[str, object]]:
    return [
        {
            "stage": item.stage,
            "control_id": item.control_id,
            "face_index": item.face_index,
            "truth_role": item.truth_role,
            "surface_type": item.surface_type,
            "area": _float(item.area),
            "centroid_x": _float(item.centroid[0]),
            "centroid_y": _float(item.centroid[1]),
            "centroid_z": _float(item.centroid[2]),
            "support_direction": _values(item.support_direction or ()),
            "support_offset": _float(item.support_offset),
            "cylinder_radius": _float(item.cylinder_radius),
            "wire_count": item.wire_count,
            "edge_count": item.edge_count,
            "adjacency_degree": item.adjacency_degree,
            "edge_length_signature": _values(
                tuple(_float(value) for value in item.edge_length_signature)
            ),
        }
        for item in probe.faces
    ]


def _candidate_rows(probe: ShapeCorrespondenceProbe) -> list[dict[str, object]]:
    return [
        {
            "comparison": item.comparison,
            "control_id": item.control_id,
            "source_stage": item.source_stage,
            "target_stage": item.target_stage,
            "source_face_index": item.source_face_index,
            "target_face_index": item.target_face_index,
            "source_truth_role": item.source_truth_role,
            "target_truth_role": item.target_truth_role,
            "area_relative_error": _float(item.area_relative_error),
            "centroid_distance": _float(item.centroid_distance),
            "support_offset_error": _float(item.support_offset_error),
            "source_centroid_contained": int(item.source_centroid_contained),
            "selected": int(item.selected),
        }
        for item in probe.candidates
    ]


def _relation_rows(probe: ShapeCorrespondenceProbe) -> list[dict[str, object]]:
    return [
        {
            "comparison": item.comparison,
            "control_id": item.control_id,
            "source_stage": item.source_stage,
            "target_stage": item.target_stage,
            "source_face_index": item.source_face_index,
            "source_truth_role": item.source_truth_role,
            "target_face_indices": _values(item.target_face_indices),
            "target_truth_roles": _values(item.target_truth_roles),
            "relation_kind": item.relation_kind,
            "candidate_count": item.candidate_count,
            "truth_correct": int(item.truth_correct),
            "history_target_indices": _values(item.history_target_indices),
            "history_agrees": (
                "" if item.history_agrees is None else int(item.history_agrees)
            ),
        }
        for item in probe.relations
    ]


def _edge_rows(probe: ShapeCorrespondenceProbe) -> list[dict[str, object]]:
    return [
        {
            "stage": item.stage,
            "control_id": item.control_id,
            "edge_index": item.edge_index,
            "truth_role": item.truth_role,
            "curve_type": item.curve_type,
            "length": _float(item.length),
            "first_point_x": _float(item.first_point[0]),
            "first_point_y": _float(item.first_point[1]),
            "first_point_z": _float(item.first_point[2]),
            "last_point_x": _float(item.last_point[0]),
            "last_point_y": _float(item.last_point[1]),
            "last_point_z": _float(item.last_point[2]),
            "support_direction": _values(item.support_direction or ()),
            "support_anchor": _values(item.support_anchor or ()),
            "incident_face_count": item.incident_face_count,
            "incident_face_indices": _values(item.incident_face_indices),
        }
        for item in probe.edges
    ]


def _edge_candidate_rows(probe: ShapeCorrespondenceProbe) -> list[dict[str, object]]:
    return [
        {
            "comparison": item.comparison,
            "control_id": item.control_id,
            "source_stage": item.source_stage,
            "target_stage": item.target_stage,
            "source_edge_index": item.source_edge_index,
            "target_edge_index": item.target_edge_index,
            "source_truth_role": item.source_truth_role,
            "target_truth_role": item.target_truth_role,
            "curve_type_matches": int(item.curve_type_matches),
            "support_error": _float(item.support_error),
            "length_relative_error": _float(item.length_relative_error),
            "endpoint_pair_max_distance": _float(item.endpoint_pair_max_distance),
            "source_endpoints_on_target": int(item.source_endpoints_on_target),
            "source_incident_face_count": item.source_incident_face_count,
            "target_incident_face_count": item.target_incident_face_count,
            "incident_face_count_matches": int(item.incident_face_count_matches),
            "source_incident_face_indices": _values(
                item.source_incident_face_indices
            ),
            "mapped_source_incident_target_face_indices": _values(
                item.mapped_source_incident_target_face_indices
            ),
            "target_incident_face_indices": _values(
                item.target_incident_face_indices
            ),
            "mapped_target_incident_source_face_indices": _values(
                item.mapped_target_incident_source_face_indices
            ),
            "topology_candidate_supports_geometry": int(
                item.topology_candidate_supports_geometry
            ),
            "selected": int(item.selected),
        }
        for item in probe.edge_candidates
    ]


def _edge_relation_rows(probe: ShapeCorrespondenceProbe) -> list[dict[str, object]]:
    return [
        {
            "comparison": item.comparison,
            "control_id": item.control_id,
            "source_stage": item.source_stage,
            "target_stage": item.target_stage,
            "source_edge_index": item.source_edge_index,
            "source_truth_role": item.source_truth_role,
            "target_edge_indices": _values(item.target_edge_indices),
            "target_truth_roles": _values(item.target_truth_roles),
            "inferred_relation_kind": item.inferred_relation_kind,
            "relation_kind": item.relation_kind,
            "candidate_count": item.candidate_count,
            "truth_correct": int(item.truth_correct),
            "history_modified_target_indices": _values(
                item.history_modified_target_indices
            ),
            "history_generated_target_indices": _values(
                item.history_generated_target_indices
            ),
            "history_modified_item_count": (
                ""
                if item.history_modified_item_count is None
                else item.history_modified_item_count
            ),
            "history_generated_item_count": (
                ""
                if item.history_generated_item_count is None
                else item.history_generated_item_count
            ),
            "history_unresolved_item_count": (
                ""
                if item.history_unresolved_item_count is None
                else item.history_unresolved_item_count
            ),
            "history_removed": (
                "" if item.history_removed is None else int(item.history_removed)
            ),
            "history_relation_kind": item.history_relation_kind or "",
            "direct_identity_checked": int(item.direct_identity_checked),
            "direct_is_same": int(item.direct_is_same),
            "direct_is_partner": int(item.direct_is_partner),
            "direct_same_target_indices": _values(item.direct_same_target_indices),
            "direct_partner_target_indices": _values(
                item.direct_partner_target_indices
            ),
            "history_agrees": (
                "" if item.history_agrees is None else int(item.history_agrees)
            ),
        }
        for item in probe.edge_relations
    ]


def _summary_rows(probe: ShapeCorrespondenceProbe) -> list[dict[str, object]]:
    selected_faces = [
        item
        for item in probe.candidates
        if item.selected and item.comparison == "step_import"
    ]
    imported_faces = [
        item for item in probe.relations if item.comparison == "step_import"
    ]
    healed_faces = [
        item for item in probe.relations if item.comparison == "same_domain_healing"
    ]
    selected_edges = [
        item
        for item in probe.edge_candidates
        if item.selected and item.comparison == "step_import"
    ]
    imported_edges = [
        item for item in probe.edge_relations if item.comparison == "step_import"
    ]
    healed_edges = [
        item
        for item in probe.edge_relations
        if item.comparison == "same_domain_healing"
    ]
    face_local_index_changes = sum(
        len(item.target_face_indices) == 1
        and item.source_face_index != item.target_face_indices[0]
        for item in imported_faces
    )
    edge_local_index_changes = sum(
        len(item.target_edge_indices) == 1
        and item.source_edge_index != item.target_edge_indices[0]
        for item in imported_edges
    )
    values = (
        ("corpus", "control_count", len(probe.controls)),
        ("corpus", "fixture_count", len(probe.fixtures)),
        (
            "face_corpus",
            "descriptor_count",
            len(probe.faces),
        ),
        (
            "face_corpus",
            "candidate_count",
            len(probe.candidates),
        ),
        ("face_all", "source_relation_count", len(probe.relations)),
        (
            "face_step_import",
            "one_to_one_source_count",
            sum(item.relation_kind == "one_to_one" for item in imported_faces),
        ),
        (
            "face_step_import",
            "ambiguous_source_count",
            sum(item.relation_kind == "ambiguous" for item in imported_faces),
        ),
        (
            "face_step_import",
            "changed_local_index_count",
            face_local_index_changes,
        ),
        (
            "face_healing",
            "one_to_one_source_count",
            sum(item.relation_kind == "one_to_one" for item in healed_faces),
        ),
        (
            "face_healing",
            "many_to_one_source_count",
            sum(item.relation_kind == "many_to_one" for item in healed_faces),
        ),
        (
            "face_all",
            "truth_correct_source_count",
            sum(item.truth_correct for item in probe.relations),
        ),
        (
            "face_healing",
            "history_agreement_count",
            sum(item.history_agrees is True for item in healed_faces),
        ),
        (
            "face_step_import_selected",
            "maximum_area_relative_error",
            max((item.area_relative_error for item in selected_faces), default=0.0),
        ),
        (
            "face_step_import_selected",
            "maximum_centroid_distance",
            max((item.centroid_distance for item in selected_faces), default=0.0),
        ),
        ("edge_corpus", "descriptor_count", len(probe.edges)),
        ("edge_corpus", "candidate_count", len(probe.edge_candidates)),
        ("edge_all", "source_relation_count", len(probe.edge_relations)),
        (
            "edge_step_import",
            "one_to_one_source_count",
            sum(item.relation_kind == "one_to_one" for item in imported_edges),
        ),
        (
            "edge_step_import",
            "ambiguous_source_count",
            sum(item.relation_kind == "ambiguous" for item in imported_edges),
        ),
        (
            "edge_step_import",
            "changed_local_index_count",
            edge_local_index_changes,
        ),
        (
            "edge_healing",
            "one_to_one_modified_source_count",
            sum(
                item.relation_kind == "one_to_one_modified"
                for item in healed_edges
            ),
        ),
        (
            "edge_healing",
            "many_to_one_source_count",
            sum(item.relation_kind == "many_to_one" for item in healed_edges),
        ),
        (
            "edge_healing",
            "deleted_source_count",
            sum(item.relation_kind == "deleted" for item in healed_edges),
        ),
        (
            "edge_all",
            "truth_correct_source_count",
            sum(item.truth_correct for item in probe.edge_relations),
        ),
        (
            "edge_healing",
            "history_agreement_count",
            sum(item.history_agrees is True for item in healed_edges),
        ),
        (
            "edge_healing",
            "history_modified_item_count",
            sum(item.history_modified_item_count or 0 for item in healed_edges),
        ),
        (
            "edge_healing",
            "history_generated_item_count",
            sum(item.history_generated_item_count or 0 for item in healed_edges),
        ),
        (
            "edge_healing",
            "history_removed_source_count",
            sum(bool(item.history_removed) for item in healed_edges),
        ),
        (
            "edge_all",
            "direct_identity_checked_source_count",
            sum(item.direct_identity_checked for item in probe.edge_relations),
        ),
        (
            "edge_all",
            "direct_is_same_source_count",
            sum(item.direct_is_same for item in probe.edge_relations),
        ),
        (
            "edge_all",
            "direct_is_partner_source_count",
            sum(item.direct_is_partner for item in probe.edge_relations),
        ),
        (
            "edge_step_import_selected",
            "maximum_length_relative_error",
            max((item.length_relative_error for item in selected_edges), default=0.0),
        ),
        (
            "edge_step_import_selected",
            "maximum_endpoint_pair_distance",
            max(
                (item.endpoint_pair_max_distance for item in selected_edges),
                default=0.0,
            ),
        ),
        (
            "edge_step_import_selected",
            "maximum_support_error",
            max((item.support_error for item in selected_edges), default=0.0),
        ),
    )
    return [
        {
            "scope": scope,
            "metric": metric,
            "value": _float(value) if isinstance(value, float) else value,
        }
        for scope, metric, value in values
    ]


def _fixture_manifest(probe: ShapeCorrespondenceProbe) -> bytes:
    version = importlib.metadata.version("cadquery-ocp")
    rows = [
        {
            "control_id": item.fixture_id,
            "file_name": item.file_name,
            "source_bytes": len(item.source_bytes),
            "source_sha256": item.source_sha256,
            "generator": "experiments/run_shape_correspondence.py",
            "binding_distribution_version": version,
            "step_processor": item.step_processor,
            "writer_status": item.writer_status,
            "reader_status": item.reader_status,
            "transferred_roots": item.transferred_roots,
        }
        for item in probe.fixtures
    ]
    return _csv_bytes(rows, tuple(rows[0]))


def handle_fixtures(
    path: Path, probe: ShapeCorrespondenceProbe, *, refresh: bool
) -> None:
    """Write or verify normalized STEP fixtures and their manifest."""
    expected = {item.file_name: item.source_bytes for item in probe.fixtures}
    expected[MANIFEST_NAME] = _fixture_manifest(probe)
    path.mkdir(parents=True, exist_ok=True)
    if refresh:
        for name, content in expected.items():
            (path / name).write_bytes(content)
        return
    for name, content in expected.items():
        target = path / name
        if not target.exists() or target.read_bytes() != content:
            raise RuntimeError(
                f"fixture differs; rerun with --refresh-fixtures: {target}"
            )


def write_contract(path: Path, probe: ShapeCorrespondenceProbe) -> None:
    """Write the versioned correspondence claim boundary."""
    payload = {
        "contract_version": "1.0",
        "study_version": "v0.39.0",
        "title": "Face and Edge Correspondence Across STEP Import and Healing",
        "matching_policy": {
            "persistent_local_indices": False,
            "force_ambiguous_matches": False,
            "face_step_import_evidence": "support_plane_area_centroid_geometry_inference",
            "edge_step_import_geometry_evidence": "curve_type_line_support_endpoints_length",
            "edge_topology_evidence": "incident_face_candidate_sets_recorded_separately",
            "edge_healing_evidence": "geometry_inference_compared_with_operation_local_history",
            "direct_topology_identity_used_as_matching_signal": False,
        },
        "controlled_expectations": {
            "face_step_import_one_to_one_sources": 23,
            "face_ambiguous_sources_correctly_abstained": 2,
            "healed_face_count": 6,
            "face_many_to_one_source_relations": 8,
            "face_many_to_one_target_groups": 4,
            "edge_step_import_one_to_one_sources": 47,
            "edge_ambiguous_sources_correctly_abstained": 8,
            "healed_edge_count": 12,
            "edge_one_to_one_modified_source_relations": 8,
            "edge_many_to_one_source_relations": 8,
            "edge_many_to_one_target_groups": 4,
            "edge_deleted_source_relations": 4,
            "edge_history_modified_items": 16,
            "edge_history_generated_items": 0,
            "edge_history_removed_sources": 4,
            "edge_direct_identity_checked_sources": 75,
            "edge_direct_is_same_sources": 0,
            "edge_direct_is_partner_sources": 0,
        },
        "observed_edge_curve_types": ["line"],
        "regression_gates_are_not_general_cad_tolerances": True,
        "fixture_sha256": {
            item.file_name: item.source_sha256 for item in probe.fixtures
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def write_figure(path: Path, probe: ShapeCorrespondenceProbe) -> None:
    """Plot face and edge outcomes with maximum numeric residuals."""
    figure, axes = plt.subplots(2, 2, figsize=(14.0, 8.4), constrained_layout=True)
    imported_faces = [
        item for item in probe.relations if item.comparison == "step_import"
    ]
    healed_faces = [
        item for item in probe.relations if item.comparison == "same_domain_healing"
    ]
    face_labels = [
        "one-to-one\nSTEP",
        "ambiguous\nSTEP",
        "one-to-one\nhealing",
        "many-to-one\nhealing",
    ]
    face_values = [
        sum(item.relation_kind == "one_to_one" for item in imported_faces),
        sum(item.relation_kind == "ambiguous" for item in imported_faces),
        sum(item.relation_kind == "one_to_one" for item in healed_faces),
        sum(item.relation_kind == "many_to_one" for item in healed_faces),
    ]
    bars = axes[0, 0].bar(
        face_labels,
        face_values,
        color=["#2563eb", "#f59e0b", "#14b8a6", "#7c3aed"],
    )
    axes[0, 0].bar_label(bars)
    axes[0, 0].set_ylabel("Source faces")
    axes[0, 0].set_title("Face relations")

    imported_edges = [
        item for item in probe.edge_relations if item.comparison == "step_import"
    ]
    healed_edges = [
        item
        for item in probe.edge_relations
        if item.comparison == "same_domain_healing"
    ]
    edge_labels = [
        "one-to-one\nSTEP",
        "ambiguous\nSTEP",
        "one-to-one modified\nhealing",
        "many-to-one\nhealing",
        "deleted\nhealing",
    ]
    edge_values = [
        sum(item.relation_kind == "one_to_one" for item in imported_edges),
        sum(item.relation_kind == "ambiguous" for item in imported_edges),
        sum(
            item.relation_kind == "one_to_one_modified" for item in healed_edges
        ),
        sum(item.relation_kind == "many_to_one" for item in healed_edges),
        sum(item.relation_kind == "deleted" for item in healed_edges),
    ]
    bars = axes[0, 1].bar(
        edge_labels,
        edge_values,
        color=["#2563eb", "#f59e0b", "#14b8a6", "#7c3aed", "#dc2626"],
    )
    axes[0, 1].bar_label(bars)
    axes[0, 1].set_ylabel("Source edges")
    axes[0, 1].set_title("Edge relations")

    selected_faces = [
        item
        for item in probe.candidates
        if item.selected and item.comparison == "step_import"
    ]
    face_residuals = [
        max((item.area_relative_error for item in selected_faces), default=0.0),
        max((item.centroid_distance for item in selected_faces), default=0.0),
        max((item.support_offset_error for item in selected_faces), default=0.0),
    ]
    axes[1, 0].bar(
        ["Area relative", "Centroid", "Support offset"],
        [max(value, 1.0e-18) for value in face_residuals],
        color="#0f766e",
    )
    axes[1, 0].set_yscale("log")
    axes[1, 0].set_ylabel("Maximum observed residual")
    axes[1, 0].set_title("Selected STEP face candidates")
    axes[1, 0].tick_params(axis="x", rotation=15)

    selected_edges = [
        item
        for item in probe.edge_candidates
        if item.selected and item.comparison == "step_import"
    ]
    edge_residuals = [
        max((item.length_relative_error for item in selected_edges), default=0.0),
        max(
            (item.endpoint_pair_max_distance for item in selected_edges),
            default=0.0,
        ),
        max((item.support_error for item in selected_edges), default=0.0),
    ]
    axes[1, 1].bar(
        ["Length relative", "Endpoint pair", "Line support"],
        [max(value, 1.0e-18) for value in edge_residuals],
        color="#1d4ed8",
    )
    axes[1, 1].set_yscale("log")
    axes[1, 1].set_ylabel("Maximum observed residual")
    axes[1, 1].set_title("Selected STEP edge candidates")
    axes[1, 1].tick_params(axis="x", rotation=15)
    figure.suptitle("v0.39.0 Face and Edge Correspondence Evidence")
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160)
    plt.close(figure)


def write_shapes_figure(path: Path) -> None:
    """Render schematic previews of the four generated STEP controls."""
    figure, axes = plt.subplots(1, 4, figsize=(14.0, 3.8), constrained_layout=True)
    polygon = Polygon(
        [(0, 0), (7, 0), (6, 3), (2, 5), (0, 2)],
        closed=True,
        facecolor="#93c5fd",
        edgecolor="#1e3a8a",
    )
    axes[0].add_patch(polygon)
    axes[0].set_title("Asymmetric prism\n7 faces / 15 edges")
    axes[0].set_xlim(-1, 8)
    axes[0].set_ylim(-1, 6)
    axes[1].add_patch(Rectangle((0, 0), 4, 5, facecolor="#c4b5fd", edgecolor="#5b21b6"))
    axes[1].annotate("reversed", (2, 2.5), ha="center", va="center", color="#5b21b6")
    axes[1].set_title("Reversed box\n6 faces / 12 edges")
    axes[1].set_xlim(-1, 5)
    axes[1].set_ylim(-1, 6)
    axes[2].add_patch(
        Rectangle((0, 0), 10, 6, facecolor="#99f6e4", edgecolor="#115e59")
    )
    axes[2].plot([4, 4], [0, 6], color="#dc2626", linewidth=2, linestyle="--")
    axes[2].set_title("Split box\n10 → 6 faces / 20 → 12 edges")
    axes[2].set_xlim(-1, 11)
    axes[2].set_ylim(-1, 7)
    for offset, alpha in ((0.0, 0.55), (0.15, 0.35)):
        axes[3].add_patch(
            Rectangle(
                (offset, offset),
                3,
                2,
                facecolor="#fbbf24",
                edgecolor="#92400e",
                alpha=alpha,
            )
        )
    axes[3].set_title("Coincident faces\n2 faces / 8 duplicate edges")
    axes[3].set_xlim(-1, 4)
    axes[3].set_ylim(-1, 3)
    for axis in axes:
        axis.set_aspect("equal")
        axis.axis("off")
    figure.suptitle("Synthetic STEP Controls for Face and Edge Correspondence")
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160)
    plt.close(figure)


def run(output_dir: Path, fixture_dir: Path, *, refresh: bool) -> None:
    """Run and serialize the complete v0.39.0 experiment."""
    probe = probe_shape_correspondence()
    handle_fixtures(fixture_dir, probe, refresh=refresh)
    face_rows = _face_rows(probe)
    candidate_rows = _candidate_rows(probe)
    relation_rows = _relation_rows(probe)
    edge_rows = _edge_rows(probe)
    edge_candidate_rows = _edge_candidate_rows(probe)
    edge_relation_rows = _edge_relation_rows(probe)
    _write_csv(output_dir / FACE_NAME, face_rows, tuple(face_rows[0]))
    _write_csv(output_dir / CANDIDATE_NAME, candidate_rows, tuple(candidate_rows[0]))
    _write_csv(output_dir / RELATION_NAME, relation_rows, tuple(relation_rows[0]))
    _write_csv(output_dir / EDGE_NAME, edge_rows, tuple(edge_rows[0]))
    _write_csv(
        output_dir / EDGE_CANDIDATE_NAME,
        edge_candidate_rows,
        tuple(edge_candidate_rows[0]),
    )
    _write_csv(
        output_dir / EDGE_RELATION_NAME,
        edge_relation_rows,
        tuple(edge_relation_rows[0]),
    )
    summary_rows = _summary_rows(probe)
    _write_csv(output_dir / SUMMARY_NAME, summary_rows, ("scope", "metric", "value"))
    write_contract(output_dir / CONTRACT_NAME, probe)
    write_figure(output_dir / FIGURE_NAME, probe)
    write_shapes_figure(output_dir / SHAPES_NAME)


def main() -> None:
    """Parse command-line arguments and run the experiment."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument(
        "--fixture-dir", type=Path, default=Path("fixtures/shape-correspondence")
    )
    parser.add_argument("--refresh-fixtures", action="store_true")
    arguments = parser.parse_args()
    run(arguments.output_dir, arguments.fixture_dir, refresh=arguments.refresh_fixtures)
    print(f"Wrote face and edge correspondence artifacts to {arguments.output_dir}")


if __name__ == "__main__":
    main()
