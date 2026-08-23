"""Tests for the v0.36 tolerance, sewing, and healing contract."""

from __future__ import annotations

import importlib.util

import pytest

from research_notes.tolerance_sewing_healing import (
    analytic_box_surface_area,
    probe_tolerance_sewing_healing,
    sewing_settings,
    tolerance_sewing_controls,
)


HAS_OCP = importlib.util.find_spec("OCP") is not None


@pytest.fixture(scope="module")
def probe() -> object:
    """Run the native probe once for all tolerance and repair tests."""
    if not HAS_OCP:
        pytest.skip("install the geometry extra to run the tolerance probe")
    return probe_tolerance_sewing_healing()


def _observation(probe: object, observation_id: str) -> object:
    matches = [
        item
        for item in probe.observations
        if item.observation_id == observation_id
    ]
    assert len(matches) == 1
    return matches[0]


def _operation(probe: object, operation_id: str) -> object:
    matches = [item for item in probe.operations if item.operation_id == operation_id]
    assert len(matches) == 1
    return matches[0]


def test_control_catalog_and_tolerance_sweep_are_fixed() -> None:
    """The matrix should keep three independent gaps and three requests."""
    assert [(item.control_id, item.gap) for item in tolerance_sewing_controls()] == [
        ("coincident_box_faces", 0.0),
        ("small_gap_box_faces", 5.0e-7),
        ("large_gap_box_faces", 5.0e-5),
    ]
    assert [(item.setting_id, item.tolerance) for item in sewing_settings()] == [
        ("tol_1e_7", 1.0e-7),
        ("tol_1e_6", 1.0e-6),
        ("tol_1e_4", 1.0e-4),
    ]


def test_independent_box_surface_area_helper() -> None:
    """Closed-form truth should not call the geometry backend."""
    assert analytic_box_surface_area(4, 5, 6) == 148.0
    with pytest.raises(TypeError, match="real numbers"):
        analytic_box_surface_area("4", 5, 6)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="finite and positive"):
        analytic_box_surface_area(4, 0, 6)


def test_probe_has_complete_stage_and_operation_evidence(probe: object) -> None:
    """Every matrix cell and bounded repair should have an audit row."""
    assert len(probe.observations) == 17
    assert len(probe.operations) == 12
    assert len(probe.fixtures) == 10
    assert sum(item.stage == "sewn" for item in probe.observations) == 9
    assert len(probe.tolerance_observations) == sum(
        item.vertex_count + item.edge_count + item.face_count
        for item in probe.observations
    )


def test_sewing_matrix_crosses_only_controlled_boundaries(probe: object) -> None:
    """Closure should follow the declared gap-to-request relationships."""
    expected = {
        "coincident_box_faces": [True, True, True],
        "small_gap_box_faces": [False, True, True],
        "large_gap_box_faces": [False, False, True],
    }
    for control_id, outcomes in expected.items():
        observed = [
            _observation(probe, f"{control_id}__sewn_{setting.setting_id}")
            for setting in sewing_settings()
        ]
        assert [item.closed_by_incidence for item in observed] == outcomes
        assert [item.boundary_edge_count for item in observed] == [
            0 if closed else 8 for closed in outcomes
        ]


def test_open_and_closed_sewing_topology_is_explicit(probe: object) -> None:
    """The unmerged top should remain distinct until its four edges merge."""
    open_shape = _observation(
        probe, "large_gap_box_faces__sewn_tol_1e_6"
    )
    closed_shape = _observation(
        probe, "large_gap_box_faces__sewn_tol_1e_4"
    )
    assert (
        open_shape.vertex_count,
        open_shape.edge_count,
        open_shape.face_count,
        open_shape.face_component_count,
    ) == (12, 16, 6, 2)
    assert (
        closed_shape.vertex_count,
        closed_shape.edge_count,
        closed_shape.face_count,
        closed_shape.face_component_count,
    ) == (8, 12, 6, 1)
    assert open_shape.kernel_analyzer_valid
    assert closed_shape.kernel_analyzer_valid


def test_gap_closure_inflates_local_vertex_and_edge_tolerances(probe: object) -> None:
    """Stored tolerances should reflect the merged residual, not just the request."""
    small_open = _observation(probe, "small_gap_box_faces__sewn_tol_1e_7")
    small_closed = _observation(probe, "small_gap_box_faces__sewn_tol_1e_6")
    large_closed = _observation(probe, "large_gap_box_faces__sewn_tol_1e_4")

    assert small_closed.edge_tolerance_max > small_open.edge_tolerance_max
    assert small_closed.edge_tolerance_max >= 5.0e-7
    assert small_closed.vertex_tolerance_max >= 5.0e-7
    assert large_closed.edge_tolerance_max >= 5.0e-5
    assert large_closed.vertex_tolerance_max >= 5.0e-5
    assert large_closed.edge_tolerance_max > small_closed.edge_tolerance_max
    assert large_closed.edge_tolerance_max < 1.0e-4


def test_sewing_and_orientation_repair_preserve_controlled_face_geometry(
    probe: object,
) -> None:
    """Known planar face areas and centroids should remain unchanged."""
    assert all(item.face_geometry_matches_control for item in probe.observations)
    assert all(item.maximum_face_area_error <= 1.0e-12 for item in probe.observations)
    assert all(
        item.maximum_face_centroid_distance <= 1.0e-12
        for item in probe.observations
    )
    assert all(
        item.maximum_support_plane_error <= 1.0e-12
        for item in probe.observations
    )
    assert all(item.surface_area == pytest.approx(148.0) for item in probe.observations)


def test_valid_shell_is_an_orientation_repair_no_op(probe: object) -> None:
    """The negative repair control should not report a modification."""
    before = _observation(probe, "valid_box_shell__orientation_input")
    after = _observation(probe, "valid_box_shell__orientation_repaired")
    operation = _operation(probe, "fix_orientation_valid_box_shell")

    assert before.current_orientation_consistent
    assert after.current_orientation_consistent
    assert before.minimum_face_flips == after.minimum_face_flips == 0
    assert before.raw_signed_volume == after.raw_signed_volume == 120.0
    assert not operation.reported_modified
    assert operation.decision == "no_change"


def test_one_flipped_face_is_repaired_without_topology_or_geometry_drift(
    probe: object,
) -> None:
    """The positive repair control should change only relative orientation."""
    before = _observation(probe, "flipped_face_box_shell__orientation_input")
    after = _observation(probe, "flipped_face_box_shell__orientation_repaired")
    operation = _operation(probe, "fix_orientation_flipped_face_box_shell")

    assert not before.current_orientation_consistent
    assert before.minimum_face_flips == 1
    assert after.current_orientation_consistent
    assert after.minimum_face_flips == 0
    assert before.raw_signed_volume == 80.0
    assert after.raw_signed_volume == 120.0
    assert not operation.topology_changed
    assert not operation.geometry_changed
    assert operation.reported_modified
    assert operation.decision == "accepted_control"


def test_tolerance_cap_is_a_deterministic_invalidating_negative_control(
    probe: object,
) -> None:
    """Reducing stored tolerance below the residual should not be called healing."""
    before = _observation(probe, "large_gap_box_faces__sewn_tol_1e_4")
    capped = _observation(
        probe, "large_gap_box_faces__tolerance_capped_1e_5"
    )
    operation = _operation(probe, "limit_large_gap_tolerance_to_1e_5")

    assert before.closed_by_incidence and before.kernel_analyzer_valid
    assert capped.closed_by_incidence and not capped.kernel_analyzer_valid
    assert capped.vertex_tolerance_max == 1.0e-5
    assert capped.edge_tolerance_max == 1.0e-5
    assert not operation.topology_changed
    assert operation.tolerance_changed
    assert not operation.geometry_changed
    assert operation.kernel_validity_change == "1->0"
    assert operation.decision == "rejected_invalid"


def test_gap_closed_under_tolerance_is_not_admitted_to_volume_contract(
    probe: object,
) -> None:
    """A finite raw volume should not erase known noncoincident support geometry."""
    exact = _observation(probe, "coincident_box_faces__sewn_tol_1e_7")
    small = _observation(probe, "small_gap_box_faces__sewn_tol_1e_6")
    large = _observation(probe, "large_gap_box_faces__sewn_tol_1e_4")

    assert exact.volume_contract_eligible
    assert exact.volume_magnitude_absolute_error == 0.0
    assert not small.volume_contract_eligible
    assert not large.volume_contract_eligible
    assert small.raw_signed_volume > 120.0
    assert large.raw_signed_volume > small.raw_signed_volume


def test_step_samples_are_deterministic_and_path_free(probe: object) -> None:
    """Normalized visual samples should be reproducible and machine-neutral."""
    second = probe_tolerance_sewing_healing()
    assert [item.source_bytes for item in probe.fixtures] == [
        item.source_bytes for item in second.fixtures
    ]
    assert [item.source_sha256 for item in probe.fixtures] == [
        item.source_sha256 for item in second.fixtures
    ]
    assert all(b"2000-01-01T00:00:00" in item.source_bytes for item in probe.fixtures)
    assert all(b"research-notes-brep-" not in item.source_bytes for item in probe.fixtures)
    assert all(item.step_advanced_face_count == 6 for item in probe.fixtures)


def test_probe_rejects_invalid_platform_labels_without_backend_use() -> None:
    """Provenance labels should fail before native geometry work."""
    with pytest.raises(TypeError, match="platform_label"):
        probe_tolerance_sewing_healing(platform_label=1)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="must not be empty"):
        probe_tolerance_sewing_healing(platform_label="")
