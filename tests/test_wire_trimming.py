"""Tests for the v0.34 wire, trimming, and face-orientation contract."""

from __future__ import annotations

import importlib.util
import math

import pytest

from research_notes.wire_trimming import (
    TrimFaceControl,
    analytic_face_area,
    analytic_face_centroid,
    classification_controls,
    expected_wire_signed_uv_area,
    probe_wire_trimming,
    wire_trimming_controls,
)


HAS_OCP = importlib.util.find_spec("OCP") is not None


@pytest.fixture(scope="module")
def probe() -> object:
    """Run the native probe once for all backend contract tests."""
    if not HAS_OCP:
        pytest.skip("install the geometry extra to run the native trimming probe")
    return probe_wire_trimming()


def test_control_catalog_separates_holes_periodicity_and_singularities() -> None:
    """The catalog should isolate the four intended trimming conditions."""
    controls = wire_trimming_controls()

    assert [item.face_id for item in controls] == [
        "planar_frame_forward",
        "planar_frame_reversed",
        "closed_cylinder",
        "natural_sphere",
    ]
    assert [item.surface_type for item in controls] == [
        "plane",
        "plane",
        "cylinder",
        "sphere",
    ]
    assert [item.reversed for item in controls] == [False, True, False, False]
    assert [item.natural_restriction for item in controls] == [
        False,
        False,
        False,
        True,
    ]


def test_analytic_face_truth_subtracts_hole_and_handles_curvature() -> None:
    """Independent truth should use material area, not UV box area alone."""
    forward, reversed_face, cylinder, sphere = wire_trimming_controls()

    assert analytic_face_area(forward) == 42.0
    assert analytic_face_area(reversed_face) == 42.0
    assert analytic_face_area(cylinder) == pytest.approx(16.0 * math.pi)
    assert analytic_face_area(sphere) == pytest.approx(36.0 * math.pi)
    assert analytic_face_centroid(forward) == pytest.approx((-1.0 / 14.0, 0.0, 0.0))
    assert analytic_face_centroid(reversed_face) == pytest.approx((12.0 - 1.0 / 14.0, 0.0, 0.0))
    assert analytic_face_centroid(cylinder) == cylinder.origin
    assert analytic_face_centroid(sphere) == sphere.origin


def test_face_reversal_flips_loop_signs_without_changing_material() -> None:
    """Outer and inner winding should invert together under face reversal."""
    forward, reversed_face, _, _ = wire_trimming_controls()

    assert expected_wire_signed_uv_area(forward, "outer") == 48.0
    assert expected_wire_signed_uv_area(forward, "inner") == -6.0
    assert expected_wire_signed_uv_area(reversed_face, "outer") == -48.0
    assert expected_wire_signed_uv_area(reversed_face, "inner") == 6.0


def test_periodic_wire_truth_is_expressed_in_parameter_space() -> None:
    """Cylinder and sphere loop areas should reflect their UV rectangles."""
    _, _, cylinder, sphere = wire_trimming_controls()

    assert expected_wire_signed_uv_area(cylinder, "outer") == pytest.approx(
        8.0 * math.pi
    )
    assert expected_wire_signed_uv_area(sphere, "outer") == pytest.approx(
        2.0 * math.pi**2
    )
    with pytest.raises(ValueError, match="do not contain an inner wire"):
        expected_wire_signed_uv_area(sphere, "inner")


def test_invalid_truth_inputs_fail_without_backend_use() -> None:
    """Public analytic helpers should reject type, role, and radius errors."""
    with pytest.raises(TypeError, match="TrimFaceControl"):
        analytic_face_area("bad")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="TrimFaceControl"):
        analytic_face_centroid("bad")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="unsupported wire role"):
        expected_wire_signed_uv_area(
            wire_trimming_controls()[0], "middle"  # type: ignore[arg-type]
        )
    cylinder = wire_trimming_controls()[2]
    with pytest.raises(ValueError, match="positive radius"):
        analytic_face_area(TrimFaceControl(**{**cylinder.__dict__, "radius": 0.0}))


def test_classification_catalog_covers_material_void_exterior_and_boundaries() -> None:
    """The point samples should exercise more than one interior location."""
    samples = classification_controls()

    assert len(samples) == 16
    assert {item.expected_state for item in samples} == {
        "inside",
        "outside",
        "on_boundary",
    }
    assert sum(item.sample_id == "hole" for item in samples) == 2


def test_backend_matches_face_geometry_and_support_domain_truth(probe: object) -> None:
    """Areas, centroids, restrictions, and orientations should match controls."""
    assert probe.constructed_valid
    assert probe.imported_valid
    assert len(probe.face_observations) == 8
    for item in probe.face_observations:
        assert item.observed_orientation == item.expected_orientation
        assert item.area_absolute_error < 4.0e-12
        assert item.centroid_distance < 2.0e-13
        assert item.restricted_uv_max_absolute_error < 5.0e-13
        assert item.observed_support_u_finite == item.expected_support_u_finite
        assert item.observed_support_v_finite == item.expected_support_v_finite
        assert item.outer_wire_count == 1
        assert item.inner_wire_count == (1 if item.surface_type == "plane" else 0)


def test_ordered_wires_close_and_match_signed_parameter_area(probe: object) -> None:
    """Every valid loop should close by identity, position, and UV connection."""
    assert len(probe.wire_observations) == 12
    for item in probe.wire_observations:
        assert item.signed_uv_area_absolute_error < 9.0e-13
        assert item.max_uv_connection_gap < 5.0e-13
        assert item.max_vertex_distance == 0.0
        assert item.topologically_closed
        assert item.brepcheck_closed_2d_status == "BRepCheck_NoError"
        assert item.brepcheck_orientation_status == "BRepCheck_NoError"
        assert not item.order_defect
        assert not item.connected_defect
        assert not item.closed_defect
        assert not item.degenerated_defect


def test_sphere_requires_degenerate_uv_edges_without_3d_curves(probe: object) -> None:
    """Pole edges should close the UV loop despite having no 3D curve."""
    sphere_uses = [
        item
        for item in probe.edge_use_observations
        if item.face_id == "natural_sphere"
    ]
    assert len(sphere_uses) == 8
    for stage in ("constructed", "step_imported"):
        stage_uses = [item for item in sphere_uses if item.stage == stage]
        degenerate = [item for item in stage_uses if item.degenerated]
        seams = [item for item in stage_uses if item.seam]
        assert len(stage_uses) == 4
        assert len(degenerate) == 2
        assert len(seams) == 2
        assert all(not item.has_curve_3d for item in degenerate)
        assert all(item.has_curve_3d for item in seams)


def test_point_classification_survives_face_reversal_and_step(probe: object) -> None:
    """Material, hole, exterior, and boundary states should remain stable."""
    assert len(probe.classification_observations) == 32
    assert all(item.matches for item in probe.classification_observations)


def test_step_exchange_preserves_shape_but_not_natural_restriction_flag(probe: object) -> None:
    """Kernel flags should not be promoted to portable STEP semantics blindly."""
    sphere = [
        item
        for item in probe.face_observations
        if item.face_id == "natural_sphere"
    ]
    assert [item.observed_natural_restriction for item in sphere] == [True, False]
    assert probe.step_advanced_face_count == 4
    assert probe.step_face_outer_bound_count == 0
    assert probe.step_face_bound_count == 6
    assert probe.step_edge_loop_count == 5
    assert probe.step_seam_curve_count == 1
    assert probe.step_degenerate_pcurve_count == 0


def test_step_fixture_is_byte_deterministic_and_path_free(probe: object) -> None:
    """Narrow normalization should stabilize only known writer variability."""
    second = probe_wire_trimming()

    assert probe.source_bytes == second.source_bytes
    assert probe.source_sha256 == second.source_sha256
    assert b"2000-01-01T00:00:00" in probe.source_bytes
    assert b"research-notes-wire-trimming-" not in probe.source_bytes


def test_probe_rejects_invalid_platform_labels_without_importing_geometry() -> None:
    """Provenance labels should fail predictably."""
    with pytest.raises(TypeError, match="platform_label"):
        probe_wire_trimming(platform_label=1)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="must not be empty"):
        probe_wire_trimming(platform_label="")
