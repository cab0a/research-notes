"""Tests for the v0.37 manifoldness and aggregate-interference contract."""

from __future__ import annotations

import importlib.util

import pytest

from research_notes.manifold_self_intersection import (
    manifold_controls,
    probe_manifold_self_intersection,
)


HAS_OCP = importlib.util.find_spec("OCP") is not None


@pytest.fixture(scope="module")
def probe() -> object:
    if not HAS_OCP:
        pytest.skip("install the geometry extra to run the manifold probe")
    return probe_manifold_self_intersection()


def _observation(probe: object, control_id: str, stage: str) -> object:
    rows = [
        row
        for row in probe.observations
        if row.control_id == control_id and row.stage == stage
    ]
    assert len(rows) == 1
    return rows[0]


def _relation(probe: object, control_id: str, stage: str) -> object:
    rows = [
        row
        for row in probe.pair_relations
        if row.control_id == control_id and row.stage == stage
    ]
    assert len(rows) == 1
    return rows[0]


def _self_intersection(probe: object, control_id: str, stage: str) -> object:
    rows = [
        row
        for row in probe.self_intersections
        if row.control_id == control_id and row.stage == stage
    ]
    assert len(rows) == 1
    return rows[0]


def test_control_catalog_separates_topology_and_geometry() -> None:
    controls = manifold_controls()
    assert len(controls) == 12
    assert [row.expected_contact_dimension for row in controls[-7:]] == [
        -1,
        0,
        1,
        2,
        3,
        -1,
        1,
    ]
    checker_controls = [row for row in controls if row.checker_level is not None]
    assert [row.control_id for row in checker_controls] == [
        "separated_edges",
        "crossing_edges",
        "separated_faces",
        "crossing_faces",
    ]


def test_all_stage_contracts_match(probe: object) -> None:
    assert len(probe.observations) == 24
    assert all(row.topology_matches_control for row in probe.observations)
    assert all(
        row.relationship_matches_control is not False for row in probe.observations
    )
    assert all(
        row.self_intersection_matches_control is not False for row in probe.observations
    )


def test_valid_tetrahedron_vertex_links_are_cycles(probe: object) -> None:
    for stage in ("constructed", "step_imported"):
        rows = [
            row
            for row in probe.vertex_links
            if row.control_id == "valid_tetrahedron" and row.stage == stage
        ]
        assert len(rows) == 4
        assert all(row.classification == "closed_manifold" for row in rows)
        assert all(
            row.link_component_count == 1 and row.maximum_degree == 2 for row in rows
        )


def test_pinched_vertex_is_detected_despite_two_use_edges(probe: object) -> None:
    for stage in ("constructed", "step_imported"):
        item = _observation(probe, "pinched_tetrahedra", stage)
        assert item.nonmanifold_edge_count == 0
        assert item.nonmanifold_vertex_count == 1
        rows = [
            row
            for row in probe.vertex_links
            if row.control_id == "pinched_tetrahedra"
            and row.stage == stage
            and row.classification == "nonmanifold"
        ]
        assert len(rows) == 1
        assert rows[0].link_component_count == 2


def test_three_face_fan_has_edge_and_vertex_failures(probe: object) -> None:
    for stage in ("constructed", "step_imported"):
        item = _observation(probe, "nonmanifold_fan", stage)
        assert item.nonmanifold_edge_count == 1
        assert item.nonmanifold_vertex_count == 2
        rows = [
            row
            for row in probe.vertex_links
            if row.control_id == "nonmanifold_fan"
            and row.stage == stage
            and row.classification == "nonmanifold"
        ]
        assert len(rows) == 2
        assert all(row.maximum_degree == 3 for row in rows)


@pytest.mark.parametrize(
    ("control_id", "dimension", "measure"),
    [
        ("disjoint_boxes", -1, 1.0),
        ("vertex_touching_boxes", 0, 0.0),
        ("edge_touching_boxes", 1, 4.0),
        ("face_touching_boxes", 2, 16.0),
        ("overlapping_boxes", 3, 9.0),
    ],
)
def test_box_relationship_dimension_and_measure(
    probe: object, control_id: str, dimension: int, measure: float
) -> None:
    for stage in ("constructed", "step_imported"):
        row = _relation(probe, control_id, stage)
        assert row.contact_dimension == dimension
        assert row.expected_measure == measure
        assert row.measure_absolute_error < 1.0e-8


def test_transverse_faces_have_two_unit_section(probe: object) -> None:
    for stage in ("constructed", "step_imported"):
        row = _relation(probe, "crossing_faces", stage)
        assert row.relationship == "proper_crossing"
        assert row.section_edge_count == 1
        assert row.section_length == pytest.approx(2.0)


def test_single_argument_checker_distinguishes_crossing_edges(probe: object) -> None:
    """One aggregate B-Rep should expose one interior edge/edge point only when crossed."""
    for stage in ("constructed", "step_imported"):
        separated = _self_intersection(probe, "separated_edges", stage)
        crossing = _self_intersection(probe, "crossing_edges", stage)
        assert separated.edge_edge_interference_count == 0
        assert separated.intersection_dimension == -1
        assert crossing.checker_level == 2
        assert crossing.edge_edge_interference_count == 1
        assert crossing.edge_edge_point_count == 1
        assert crossing.intersection_dimension == 0
        assert crossing.quantity_kind == "intersection_point_count"
        assert crossing.intersection_quantity == 1.0
        assert crossing.self_intersection_matches_control


def test_single_argument_checker_distinguishes_crossing_faces(probe: object) -> None:
    """Independent faces in one aggregate should retain one two-unit section curve."""
    for stage in ("constructed", "step_imported"):
        separated = _self_intersection(probe, "separated_faces", stage)
        crossing = _self_intersection(probe, "crossing_faces", stage)
        assert separated.face_face_interference_count == 0
        assert separated.intersection_dimension == -1
        separation = _relation(probe, "separated_faces", stage).minimum_distance
        assert separation == pytest.approx(1.0)
        assert crossing.checker_level == 5
        assert crossing.edge_face_interference_count == 2
        assert crossing.face_face_interference_count == 1
        assert crossing.face_face_curve_count == 1
        assert crossing.intersection_dimension == 1
        assert crossing.quantity_kind == "section_length"
        assert crossing.intersection_quantity == pytest.approx(2.0)
        assert crossing.self_intersection_matches_control


def test_step_fixtures_are_byte_deterministic(probe: object) -> None:
    second = probe_manifold_self_intersection()
    assert [row.source_bytes for row in probe.fixtures] == [
        row.source_bytes for row in second.fixtures
    ]
    assert all(b"2000-01-01T00:00:00" in row.source_bytes for row in probe.fixtures)
    assert len(probe.fixtures) == 12


def test_probe_rejects_invalid_platform_labels() -> None:
    with pytest.raises(TypeError, match="platform_label"):
        probe_manifold_self_intersection(platform_label=1)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="must not be empty"):
        probe_manifold_self_intersection(platform_label="")
