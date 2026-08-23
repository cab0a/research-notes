"""Tests for the v0.38 solid-region contract."""

from __future__ import annotations

import importlib.util

import pytest

from research_notes.solid_regions import probe_solid_regions, solid_region_controls


HAS_OCP = importlib.util.find_spec("OCP") is not None


@pytest.fixture(scope="module")
def probe() -> object:
    if not HAS_OCP:
        pytest.skip("install the geometry extra to run the solid-region probe")
    return probe_solid_regions()


def _observation(probe: object, control_id: str, stage: str) -> object:
    rows = [
        row
        for row in probe.observations
        if row.control_id == control_id and row.stage == stage
    ]
    assert len(rows) == 1
    return rows[0]


def test_control_catalog_has_outer_void_and_container_boundaries() -> None:
    controls = solid_region_controls()
    assert len(controls) == 10
    assert [row.control_id for row in controls[:3]] == [
        "single_outer_box",
        "centered_void_box",
        "two_void_box",
    ]
    assert [row.analytic_material_volume for row in controls[:3]] == [
        480.0,
        464.0,
        560.0,
    ]


def test_constructed_topology_matches_all_controls(probe: object) -> None:
    rows = [row for row in probe.observations if row.stage == "constructed"]
    assert len(rows) == 10
    assert all(row.topology_matches_constructed_control for row in rows)


def test_constructed_contract_adjacency_and_components_match_controls(
    probe: object,
) -> None:
    """Every declared constructed expectation must be compared with evidence."""
    rows = [row for row in probe.observations if row.stage == "constructed"]
    assert all(
        row.material_region_candidate_matches_constructed_control for row in rows
    )
    assert all(row.shared_face_count_matches_constructed_control for row in rows)
    assert all(row.solid_component_count_matches_constructed_control for row in rows)
    shared = _observation(probe, "shared_face_compsolid", "constructed")
    assert shared.expected_shared_face_count == shared.shared_face_count == 1
    assert shared.expected_solid_component_count == shared.solid_component_count == 1


@pytest.mark.parametrize(
    ("control_id", "shell_count", "volume"),
    [
        ("single_outer_box", 1, 480.0),
        ("centered_void_box", 2, 464.0),
        ("two_void_box", 3, 560.0),
    ],
)
def test_valid_void_controls_retain_analytic_volume(
    probe: object, control_id: str, shell_count: int, volume: float
) -> None:
    for stage in ("constructed", "step_imported"):
        row = _observation(probe, control_id, stage)
        assert row.shell_count == shell_count
        assert row.kernel_signed_volume == pytest.approx(volume)
        assert row.volume_absolute_error < 3.0e-13
        assert row.material_region_candidate


def test_wrong_void_orientation_is_normalized_by_step(probe: object) -> None:
    constructed = _observation(probe, "wrong_void_orientation", "constructed")
    imported = _observation(probe, "wrong_void_orientation", "step_imported")
    assert constructed.kernel_signed_volume == pytest.approx(496.0)
    assert not constructed.shell_orientation_contract
    assert not constructed.material_region_candidate
    assert imported.kernel_signed_volume == pytest.approx(464.0)
    assert imported.shell_orientation_contract
    assert imported.material_region_candidate


def test_outside_void_matches_numeric_volume_but_fails_containment(
    probe: object,
) -> None:
    constructed = _observation(probe, "outside_void_shell", "constructed")
    imported = _observation(probe, "outside_void_shell", "step_imported")
    assert constructed.kernel_signed_volume == pytest.approx(464.0)
    assert constructed.volume_absolute_error < 1.0e-12
    assert not constructed.root_shell_count_matches_solids
    assert not constructed.material_region_candidate
    assert imported.observed_shape_type == "compound"
    assert imported.solid_count == 2
    assert imported.kernel_signed_volume == pytest.approx(496.0)
    assert not imported.material_region_candidate


def test_overlapping_voids_expose_double_subtraction(probe: object) -> None:
    for stage in ("constructed", "step_imported"):
        row = _observation(probe, "overlapping_void_shells", stage)
        assert row.kernel_signed_volume == pytest.approx(522.0)
        assert row.analytic_material_volume == 531.0
        assert row.volume_absolute_error == pytest.approx(9.0)
        assert row.same_depth_shell_overlap_count == 1
        assert row.shell_orientation_contract
        assert row.root_shell_count_matches_solids
        assert not row.shell_overlap_gate_passed
        assert not row.material_region_candidate
        voids = [
            item
            for item in probe.shell_roles
            if item.control_id == "overlapping_void_shells"
            and item.stage == stage
            and item.inferred_role == "void"
        ]
        assert len(voids) == 2
        assert all(item.local_containment_depth == 1 for item in voids)
        assert all(item.orientation_matches_depth for item in voids)
        cross_void_relations = [
            item
            for item in probe.containment
            if item.control_id == "overlapping_void_shells"
            and item.stage == stage
            and item.outer_shell_index in {2, 3}
            and item.inner_shell_index in {2, 3}
        ]
        assert len(cross_void_relations) == 2
        assert all(not item.full_inner_volume_covered for item in cross_void_relations)
        assert all(not item.contains for item in cross_void_relations)


def test_material_island_is_a_second_solid(probe: object) -> None:
    for stage in ("constructed", "step_imported"):
        row = _observation(probe, "material_island_compound", stage)
        assert row.solid_count == 2
        assert row.shell_count == 3
        assert row.kernel_signed_volume == pytest.approx(392.0)
        assert row.material_region_candidate
        depths = {
            item.global_containment_depth
            for item in probe.shell_roles
            if item.control_id == "material_island_compound" and item.stage == stage
        }
        assert depths == {0, 1, 2}


def test_shared_face_compsolid_loses_container_and_shared_identity(
    probe: object,
) -> None:
    constructed = _observation(probe, "shared_face_compsolid", "constructed")
    imported = _observation(probe, "shared_face_compsolid", "step_imported")
    assert constructed.observed_shape_type == "compsolid"
    assert (
        constructed.vertex_count,
        constructed.edge_count,
        constructed.face_count,
    ) == (12, 20, 11)
    assert constructed.shared_face_count == 1
    assert constructed.solid_component_count == 1
    assert constructed.composite_solid_contract is True
    assert imported.observed_shape_type == "compound"
    assert (imported.vertex_count, imported.edge_count, imported.face_count) == (
        16,
        24,
        12,
    )
    assert imported.shared_face_count == 0
    assert imported.solid_component_count == 2


def test_disconnected_compsolid_type_is_not_connectivity_proof(probe: object) -> None:
    constructed = _observation(probe, "disconnected_compsolid", "constructed")
    imported = _observation(probe, "disconnected_compsolid", "step_imported")
    assert constructed.composite_solid_contract is False
    assert not constructed.material_region_candidate
    assert imported.observed_shape_type == "compound"
    assert imported.composite_solid_contract is None


def test_step_void_entities_match_shell_roles(probe: object) -> None:
    fixtures = {row.round_trip.fixture_id: row for row in probe.fixtures}
    assert fixtures["single_outer_box"].manifold_solid_brep_count == 1
    assert fixtures["centered_void_box"].brep_with_voids_count == 1
    assert fixtures["centered_void_box"].oriented_closed_shell_count == 1
    assert fixtures["two_void_box"].oriented_closed_shell_count == 2


def test_step_fixtures_are_byte_deterministic(probe: object) -> None:
    second = probe_solid_regions()
    assert [row.round_trip.source_bytes for row in probe.fixtures] == [
        row.round_trip.source_bytes for row in second.fixtures
    ]
    assert all(
        b"2000-01-01T00:00:00" in row.round_trip.source_bytes for row in probe.fixtures
    )


def test_probe_rejects_invalid_platform_labels() -> None:
    with pytest.raises(TypeError, match="platform_label"):
        probe_solid_regions(platform_label=1)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="must not be empty"):
        probe_solid_regions(platform_label="")
