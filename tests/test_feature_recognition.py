"""Tests for the v0.40 rule-based B-Rep feature-recognition contract."""

from __future__ import annotations

import importlib.util
import math

import pytest

from research_notes.feature_recognition import (
    feature_controls,
    probe_feature_recognition,
    recovered_dimension_series,
    round_trip_dimension_differences,
)


HAS_OCP = importlib.util.find_spec("OCP") is not None


@pytest.fixture(scope="module")
def probe() -> object:
    """Run the native feature probe once for all tests."""
    if not HAS_OCP:
        pytest.skip("install the geometry extra to run feature-recognition tests")
    return probe_feature_recognition()


def _candidate(probe: object, control_id: str, stage: str) -> object:
    matches = [
        item
        for item in probe.candidates
        if item.control_id == control_id and item.stage == stage
    ]
    assert len(matches) == 1
    return matches[0]


def _dot(first: tuple[float, ...], second: tuple[float, ...]) -> float:
    return sum(a * b for a, b in zip(first, second, strict=True))


def test_control_catalog_separates_features_and_confounders() -> None:
    """The corpus should contain seven candidates and two negative controls."""
    controls = feature_controls()
    assert len(controls) == 9
    assert sum(len(item.expected_candidate_types) for item in controls) == 7
    assert [
        item.control_id for item in controls if not item.expected_candidate_types
    ] == ["plain_block", "cylindrical_boss"]
    expected = {
        item.control_id: (
            item.expected_primary_size,
            item.expected_secondary_size,
            item.expected_depth,
            item.expected_angle_degrees,
        )
        for item in controls
    }
    assert expected["through_hole"] == (2.5, None, 6.0, None)
    assert expected["through_slot"] == (2.0, 6.0, 4.0, None)
    assert expected["fillet_operation"] == (1.0, 8.0, None, 90.0)


def test_candidate_inventory_is_stable_after_step_import(probe: object) -> None:
    """All seven controlled candidates should retain class and subtype."""
    constructed = sorted(
        (item.control_id, item.candidate_type, item.subtype)
        for item in probe.candidates
        if item.stage == "constructed"
    )
    imported = sorted(
        (item.control_id, item.candidate_type, item.subtype)
        for item in probe.candidates
        if item.stage == "step_imported"
    )
    assert len(constructed) == 7
    assert imported == constructed
    assert all(item.classification_matches_truth for item in probe.candidates)
    assert all(item.dimension_matches_truth for item in probe.candidates)
    assert all(item.truth_correct for item in probe.candidates)


def test_candidate_dimensions_are_compared_with_controlled_truth(
    probe: object,
) -> None:
    """Every recovered dimension should retain its truth value and residual."""
    for item in probe.candidates:
        comparisons = (
            (
                item.primary_size,
                item.expected_primary_size,
                item.primary_size_absolute_error,
            ),
            (
                item.secondary_size,
                item.expected_secondary_size,
                item.secondary_size_absolute_error,
            ),
            (item.depth, item.expected_depth, item.depth_absolute_error),
            (
                item.angle_degrees,
                item.expected_angle_degrees,
                item.angle_absolute_error_degrees,
            ),
        )
        for observed, expected, error in comparisons:
            if expected is None:
                assert observed is None
                assert error is None
            else:
                assert observed is not None
                assert error == pytest.approx(abs(observed - expected))
                assert error < 1.0e-8


def test_round_holes_distinguish_through_and_blind(probe: object) -> None:
    """Cap topology should separate through and flat-bottom blind holes."""
    for stage in ("constructed", "step_imported"):
        through = _candidate(probe, "through_hole", stage)
        blind = _candidate(probe, "blind_hole", stage)
        assert (through.candidate_type, through.subtype) == ("hole", "through")
        assert through.primary_size == pytest.approx(2.5)
        assert through.depth == pytest.approx(6.0)
        assert (blind.candidate_type, blind.subtype) == ("hole", "blind")
        assert blind.primary_size == pytest.approx(2.0)
        assert blind.depth == pytest.approx(3.5)
        assert len(blind.face_indices) == 2
        blind_faces = {
            item.face_index: item
            for item in probe.faces
            if item.control_id == "blind_hole" and item.stage == stage
        }
        assert {blind_faces[index].surface_type for index in blind.face_indices} == {
            "cylinder",
            "plane",
        }
        cap = next(
            blind_faces[index]
            for index in blind.face_indices
            if blind_faces[index].surface_type == "plane"
        )
        assert cap.wire_count == cap.edge_count == 1
        assert cap.area == pytest.approx(math.pi)


def test_step_and_slot_dimensions_match_construction_truth(probe: object) -> None:
    """Graph rules should recover the controlled step and capsule dimensions."""
    for stage in ("constructed", "step_imported"):
        step = _candidate(probe, "stepped_block", stage)
        slot = _candidate(probe, "through_slot", stage)
        assert step.candidate_type == "step"
        assert step.primary_size == pytest.approx(2.0)
        assert step.secondary_size == pytest.approx(8.0)
        assert slot.candidate_type == "slot"
        assert slot.primary_size == pytest.approx(2.0)
        assert slot.secondary_size == pytest.approx(6.0)
        assert slot.depth == pytest.approx(4.0)


def test_chamfer_like_and_fillet_like_dimensions_are_recovered(probe: object) -> None:
    """Planar bevel and constant-curvature rules should recover known sizes."""
    for stage in ("constructed", "step_imported"):
        chamfer = _candidate(probe, "chamfer_operation", stage)
        bevel = _candidate(probe, "equivalent_bevel", stage)
        fillet = _candidate(probe, "fillet_operation", stage)
        assert chamfer.primary_size == pytest.approx(1.0)
        assert chamfer.angle_degrees == pytest.approx(45.0)
        assert bevel.primary_size == pytest.approx(1.0)
        assert bevel.angle_degrees == pytest.approx(45.0)
        assert fillet.primary_size == pytest.approx(1.0)
        assert fillet.secondary_size == pytest.approx(8.0)
        assert fillet.angle_degrees == pytest.approx(90.0)


@pytest.mark.parametrize("control_id", ["chamfer_operation", "equivalent_bevel"])
def test_chamfer_candidate_uses_the_two_geometric_parent_faces(
    probe: object, control_id: str
) -> None:
    """Chamfer evidence should exclude extrusion end caps selected by local order."""
    for stage in ("constructed", "step_imported"):
        candidate = _candidate(probe, control_id, stage)
        faces = {
            item.face_index: item
            for item in probe.faces
            if item.control_id == control_id and item.stage == stage
        }
        selected = [faces[index] for index in candidate.face_indices]
        feature = next(
            item
            for item in selected
            if sum(abs(value) > 1.0e-6 for value in item.normal) == 2
        )
        parents = [item for item in selected if item.face_index != feature.face_index]
        assert len(parents) == 2
        assert abs(_dot(parents[0].normal, parents[1].normal)) <= 1.0e-7
        assert all(
            parent.face_index in feature.adjacent_face_indices for parent in parents
        )
        assert all(
            abs(_dot(feature.normal, parent.normal))
            == pytest.approx(math.sqrt(0.5), abs=1.0e-6)
            for parent in parents
        )
        shared_pairs = {
            frozenset((item.first_face_index, item.second_face_index))
            for item in probe.adjacencies
            if item.control_id == control_id and item.stage == stage
        }
        assert all(
            frozenset((feature.face_index, parent.face_index)) in shared_pairs
            for parent in parents
        )


def test_fillet_candidate_uses_radial_parent_faces(probe: object) -> None:
    """Fillet evidence should exclude planar caps normal to the cylinder axis."""
    for stage in ("constructed", "step_imported"):
        candidate = _candidate(probe, "fillet_operation", stage)
        faces = {
            item.face_index: item
            for item in probe.faces
            if item.control_id == "fillet_operation" and item.stage == stage
        }
        selected = [faces[index] for index in candidate.face_indices]
        feature = next(item for item in selected if item.surface_type == "cylinder")
        assert feature.axis_direction is not None
        parents = [item for item in selected if item.face_index != feature.face_index]
        assert len(parents) == 2
        assert abs(_dot(parents[0].normal, parents[1].normal)) <= 1.0e-7
        assert all(
            parent.face_index in feature.adjacent_face_indices for parent in parents
        )
        assert all(
            abs(_dot(parent.normal, feature.axis_direction)) <= 1.0e-7
            for parent in parents
        )
        shared_pairs = {
            frozenset((item.first_face_index, item.second_face_index))
            for item in probe.adjacencies
            if item.control_id == "fillet_operation" and item.stage == stage
        }
        assert all(
            frozenset((feature.face_index, parent.face_index)) in shared_pairs
            for parent in parents
        )


def test_hole_rule_rejects_external_cylindrical_boss(probe: object) -> None:
    """Outward radial polarity should keep the boss out of the hole class."""
    assert not [
        item for item in probe.candidates if item.control_id == "cylindrical_boss"
    ]
    for stage in ("constructed", "step_imported"):
        hole_faces = [
            item
            for item in probe.faces
            if item.control_id == "through_hole"
            and item.stage == stage
            and item.surface_type == "cylinder"
        ]
        boss_faces = [
            item
            for item in probe.faces
            if item.control_id == "cylindrical_boss"
            and item.stage == stage
            and item.surface_type == "cylinder"
        ]
        assert len(hole_faces) == len(boss_faces) == 1
        assert hole_faces[0].radial_polarity == pytest.approx(-1.0)
        assert boss_faces[0].radial_polarity == pytest.approx(1.0)


def test_equivalent_bevel_proves_the_design_intent_boundary(probe: object) -> None:
    """Equivalent geometry must not be promoted into a construction-history claim."""
    for stage in ("constructed", "step_imported"):
        chamfer = _candidate(probe, "chamfer_operation", stage)
        bevel = _candidate(probe, "equivalent_bevel", stage)
        assert chamfer.candidate_type == bevel.candidate_type == "chamfer_like"
        assert chamfer.construction_history_label == "chamfer_operation"
        assert bevel.construction_history_label == "direct_profile"
        assert not chamfer.design_intent_proven
        assert not bevel.design_intent_proven


def test_equivalent_bevel_has_the_same_final_material_boundary(probe: object) -> None:
    """Construction truth should include topology, volume, and both differences."""
    assert [item.stage for item in probe.equivalent_boundaries] == [
        "constructed",
        "step_imported",
    ]
    for item in probe.equivalent_boundaries:
        assert item.first_control_id == "chamfer_operation"
        assert item.second_control_id == "equivalent_bevel"
        assert item.topology_matches
        assert (
            item.first_vertex_count,
            item.first_edge_count,
            item.first_face_count,
            item.first_shell_count,
            item.first_solid_count,
        ) == (10, 15, 7, 1, 1)
        assert item.first_volume == pytest.approx(572.0)
        assert item.second_volume == pytest.approx(572.0)
        assert item.volume_absolute_difference == pytest.approx(0.0)
        assert item.first_minus_second_volume == pytest.approx(0.0)
        assert item.second_minus_first_volume == pytest.approx(0.0)
        assert item.boundary_equivalent


def test_feature_graph_and_fixtures_are_nonempty(probe: object) -> None:
    """The evidence should retain face nodes, adjacencies, and nine STEP files."""
    assert len(probe.faces) > 100
    assert len(probe.adjacencies) > 100
    assert len(probe.fixtures) == 9
    assert len({item.source_sha256 for item in probe.fixtures}) == 9


def test_round_trip_metrics_keep_lengths_and_angles_separate(probe: object) -> None:
    """Model-unit differences must not be aggregated with angular degrees."""
    length_difference, angle_difference = round_trip_dimension_differences(probe)
    assert length_difference == pytest.approx(3.9523939676655573e-13)
    assert angle_difference == pytest.approx(5.8832938520936295e-12)


def test_figure_dimensions_are_derived_from_recognized_candidates(
    probe: object,
) -> None:
    """The plotted dimension series should be backed by probe candidates."""
    series = recovered_dimension_series(probe)
    assert [label for label, _ in series] == [
        "Through hole Ø",
        "Blind depth",
        "Step height",
        "Slot width",
        "Slot length",
        "Chamfer",
        "Fillet R",
    ]
    assert [value for _, value in series] == pytest.approx(
        [2.5, 3.5, 2.0, 2.0, 6.0, 1.0, 1.0]
    )
