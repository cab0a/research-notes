"""Tests for the v0.35 shell and solid validity contract."""

from __future__ import annotations

import importlib.util
import math

import pytest

from research_notes.shell_solid_validity import (
    analytic_box_volume,
    analytic_torus_volume,
    euler_characteristic,
    probe_shell_solid_validity,
    shell_solid_controls,
)


HAS_OCP = importlib.util.find_spec("OCP") is not None


@pytest.fixture(scope="module")
def probe() -> object:
    """Run the native probe once for all validity contract tests."""
    if not HAS_OCP:
        pytest.skip("install the geometry extra to run the shell/solid probe")
    return probe_shell_solid_validity()


def _observation(probe: object, control_id: str, stage: str) -> object:
    matches = [
        item
        for item in probe.observations
        if item.control_id == control_id and item.stage == stage
    ]
    assert len(matches) == 1
    return matches[0]


def test_control_catalog_separates_validity_conditions() -> None:
    """The catalog should isolate closure, orientation, genus, and connectivity."""
    controls = shell_solid_controls()

    assert [item.control_id for item in controls] == [
        "valid_box",
        "reversed_box",
        "open_box",
        "flipped_face_box",
        "nonmanifold_fan",
        "valid_torus",
        "disconnected_faces",
    ]
    assert [item.shape_class for item in controls].count("solid") == 3
    assert [item.expected_euler_characteristic for item in controls] == [
        2,
        2,
        1,
        2,
        1,
        0,
        2,
    ]


def test_independent_volume_and_euler_helpers() -> None:
    """Closed-form truth should not depend on the geometry backend."""
    assert analytic_box_volume(4, 5, 6) == 120.0
    assert analytic_torus_volume(4, 1.5) == pytest.approx(18.0 * math.pi**2)
    assert euler_characteristic(8, 12, 6) == 2
    assert euler_characteristic(1, 2, 1) == 0


def test_independent_helpers_reject_invalid_values() -> None:
    """Truth helpers should fail before importing or calling the backend."""
    with pytest.raises(TypeError, match="real numbers"):
        analytic_box_volume("4", 5, 6)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="finite and positive"):
        analytic_box_volume(4, 0, 6)
    with pytest.raises(ValueError, match="greater than minor"):
        analytic_torus_volume(1, 1.5)
    with pytest.raises(TypeError, match="integers"):
        euler_characteristic(8.0, 12, 6)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="nonnegative"):
        euler_characteristic(8, -1, 6)


def test_all_stage_topology_matches_independent_controls(probe: object) -> None:
    """STEP exchange should retain V/E/F, incidence, components, and Euler truth."""
    assert len(probe.observations) == 14
    assert all(item.topology_matches_control for item in probe.observations)
    assert len(probe.component_observations) == 16


def test_valid_box_is_a_closed_oriented_solid(probe: object) -> None:
    """The genus-zero positive control should satisfy every validity layer."""
    for stage in ("constructed", "step_imported"):
        item = _observation(probe, "valid_box", stage)
        assert (item.vertex_count, item.edge_count, item.face_count) == (8, 12, 6)
        assert item.euler_characteristic == 2
        assert item.closed_by_incidence
        assert item.orientable_manifold
        assert item.current_orientation_consistent
        assert item.closed_oriented_shell_candidate
        assert item.kernel_analyzer_valid
        assert item.solid_count == 1
        assert item.kernel_signed_volume == 120.0
        assert item.volume_magnitude_absolute_error == 0.0


def test_whole_solid_reversal_changes_sign_then_step_normalizes_it(probe: object) -> None:
    """Relative orientation can remain valid while global volume sign changes."""
    constructed = _observation(probe, "reversed_box", "constructed")
    imported = _observation(probe, "reversed_box", "step_imported")

    assert constructed.closed_oriented_shell_candidate
    assert imported.closed_oriented_shell_candidate
    assert constructed.volume_sign == "negative"
    assert imported.volume_sign == "positive"
    assert constructed.kernel_signed_volume == -120.0
    assert imported.kernel_signed_volume == 120.0
    assert constructed.volume_magnitude_absolute_error == 0.0
    assert imported.volume_magnitude_absolute_error == 0.0


def test_open_shell_is_kernel_valid_but_not_closed(probe: object) -> None:
    """Generic kernel validity should not be treated as a solid contract."""
    for stage in ("constructed", "step_imported"):
        item = _observation(probe, "open_box", stage)
        assert item.kernel_analyzer_valid
        assert item.boundary_edge_count == 4
        assert item.boundary_component_count == 1
        assert item.boundary_degree_violation_count == 0
        assert not item.closed_by_incidence
        assert not item.closed_oriented_shell_candidate
        assert not item.volume_contract_eligible
    shell_rows = [
        item for item in probe.shell_observations if item.control_id == "open_box"
    ]
    assert {item.closed_status for item in shell_rows} == {"BRepCheck_NotClosed"}


def test_one_flipped_face_is_detected_then_reoriented_on_import(probe: object) -> None:
    """Incidence closure and current orientation should remain separate checks."""
    constructed = _observation(probe, "flipped_face_box", "constructed")
    imported = _observation(probe, "flipped_face_box", "step_imported")

    assert constructed.closed_by_incidence
    assert constructed.orientable_manifold
    assert not constructed.current_orientation_consistent
    assert constructed.minimum_face_flips == 1
    assert constructed.kernel_analyzer_valid
    assert not constructed.volume_contract_eligible
    assert constructed.kernel_signed_volume == 80.0
    assert imported.current_orientation_consistent
    assert imported.minimum_face_flips == 0
    assert imported.volume_contract_eligible
    assert imported.kernel_signed_volume == 120.0
    statuses = {
        item.stage: item.orientation_status
        for item in probe.shell_observations
        if item.control_id == "flipped_face_box"
    }
    assert statuses == {
        "constructed": "BRepCheck_BadOrientationOfSubshape",
        "step_imported": "BRepCheck_NoError",
    }


def test_nonmanifold_edge_is_detected_even_after_shell_splitting(probe: object) -> None:
    """Three uses of one edge should survive despite imported shell regrouping."""
    constructed = _observation(probe, "nonmanifold_fan", "constructed")
    imported = _observation(probe, "nonmanifold_fan", "step_imported")

    for item in (constructed, imported):
        assert item.kernel_analyzer_valid
        assert item.nonmanifold_edge_count == 1
        assert not item.orientable_manifold
        assert not item.closed_oriented_shell_candidate
    assert (constructed.shell_count, imported.shell_count) == (1, 3)
    shared = [
        item
        for item in probe.edge_observations
        if item.control_id == "nonmanifold_fan" and item.nonmanifold
    ]
    assert len(shared) == 2
    assert all(item.use_count == 3 and item.incident_face_count == 3 for item in shared)


def test_torus_demonstrates_closed_genus_one_euler_truth(probe: object) -> None:
    """A closed solid need not have Euler characteristic two."""
    for stage in ("constructed", "step_imported"):
        item = _observation(probe, "valid_torus", stage)
        assert (item.vertex_count, item.edge_count, item.face_count) == (1, 2, 1)
        assert item.euler_characteristic == 0
        assert item.closed_oriented_shell_candidate
        assert item.volume_magnitude_absolute_error < 7.0e-12
    torus_edges = [
        item
        for item in probe.edge_observations
        if item.control_id == "valid_torus"
    ]
    assert len(torus_edges) == 4
    assert all(item.use_count == 2 for item in torus_edges)
    assert all(item.incident_face_count == 1 for item in torus_edges)
    assert all(item.paired_orientations_opposed for item in torus_edges)


def test_disconnected_shell_container_is_split_by_step_import(probe: object) -> None:
    """Connected components should remain visible when shell grouping changes."""
    constructed = _observation(probe, "disconnected_faces", "constructed")
    imported = _observation(probe, "disconnected_faces", "step_imported")

    assert constructed.face_component_count == imported.face_component_count == 2
    assert constructed.euler_characteristic == imported.euler_characteristic == 2
    assert constructed.shell_count == 1
    assert imported.shell_count == 2
    assert not constructed.kernel_analyzer_valid
    assert imported.kernel_analyzer_valid
    assert not constructed.closed_oriented_shell_candidate
    assert not imported.closed_oriented_shell_candidate


def test_backend_shell_statuses_expose_specific_failures(probe: object) -> None:
    """Shell-specific reports should distinguish closure, orientation, and use."""
    constructed = {
        item.control_id: item
        for item in probe.shell_observations
        if item.stage == "constructed"
    }
    assert constructed["valid_box"].closed_status == "BRepCheck_NoError"
    assert constructed["open_box"].closed_status == "BRepCheck_NotClosed"
    assert (
        constructed["flipped_face_box"].orientation_status
        == "BRepCheck_BadOrientationOfSubshape"
    )
    assert (
        constructed["nonmanifold_fan"].closed_status
        == "BRepCheck_InvalidMultiConnexity"
    )
    assert (
        constructed["disconnected_faces"].closed_status
        == "BRepCheck_NotConnected"
    )


def test_step_fixtures_are_byte_deterministic_and_path_free(probe: object) -> None:
    """Narrow normalization should stabilize only known writer variability."""
    second = probe_shell_solid_validity()

    assert [item.source_bytes for item in probe.fixtures] == [
        item.source_bytes for item in second.fixtures
    ]
    assert [item.source_sha256 for item in probe.fixtures] == [
        item.source_sha256 for item in second.fixtures
    ]
    assert all(b"2000-01-01T00:00:00" in item.source_bytes for item in probe.fixtures)
    assert all(b"research-notes-shell-solid-" not in item.source_bytes for item in probe.fixtures)
    assert sum(item.step_manifold_solid_brep_count for item in probe.fixtures) == 3
    assert sum(item.step_open_shell_count for item in probe.fixtures) == 4


def test_probe_rejects_invalid_platform_labels_without_backend_use() -> None:
    """Provenance labels should fail predictably."""
    with pytest.raises(TypeError, match="platform_label"):
        probe_shell_solid_validity(platform_label=1)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="must not be empty"):
        probe_shell_solid_validity(platform_label="")
