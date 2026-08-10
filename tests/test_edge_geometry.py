"""Tests for the v0.33 edge-curve, p-curve, and seam contract."""

from __future__ import annotations

import importlib.util
import math

import pytest

from research_notes.edge_geometry import (
    EdgeFaceControl,
    analytic_boundary_truth,
    edge_face_controls,
    probe_edge_geometry,
)


def test_control_catalog_separates_plane_partial_and_closed_surfaces() -> None:
    """The corpus should expose ordinary boundaries and a periodic seam."""
    controls = edge_face_controls()

    assert [item.face_id for item in controls] == [
        "planar_rectangle",
        "partial_cylinder",
        "closed_cylinder",
    ]
    assert [item.surface_type for item in controls] == [
        "plane",
        "cylinder",
        "cylinder",
    ]
    assert controls[1].uv_bounds[1] - controls[1].uv_bounds[0] < 2.0 * math.pi
    assert controls[2].uv_bounds[1] - controls[2].uv_bounds[0] == pytest.approx(
        2.0 * math.pi
    )


def test_boundary_truth_distinguishes_parameter_span_from_arc_length() -> None:
    """A circular curve uses an angular parameter, not distance along the arc."""
    partial = edge_face_controls()[1]
    axial = analytic_boundary_truth(partial, "u_min")
    arc = analytic_boundary_truth(partial, "v_min")

    assert axial.expected_curve_type == "line"
    assert axial.expected_length == axial.expected_parameter_span == 4.5
    assert arc.expected_curve_type == "circle"
    assert arc.expected_parameter_span == 1.5
    assert arc.expected_length == 3.0
    assert not axial.expected_is_seam
    assert not arc.expected_is_seam


def test_closed_cylinder_has_two_uv_boundaries_for_one_seam_truth() -> None:
    """The periodic U boundaries should describe the same geometric seam."""
    control = edge_face_controls()[2]
    left = analytic_boundary_truth(control, "u_min")
    right = analytic_boundary_truth(control, "u_max")

    assert left.expected_is_seam
    assert right.expected_is_seam
    assert left.expected_length == right.expected_length == 4.0
    assert left.expected_uv_mid == (0.0, 2.0)
    assert right.expected_uv_mid == pytest.approx((2.0 * math.pi, 2.0))


def test_invalid_boundary_truth_fails_before_backend_use() -> None:
    """Invalid roles, bounds, and cylinder radii must not become truth."""
    control = edge_face_controls()[0]
    with pytest.raises(TypeError, match="EdgeFaceControl"):
        analytic_boundary_truth("bad", "u_min")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="unsupported boundary role"):
        analytic_boundary_truth(control, "diagonal")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="strictly increasing"):
        analytic_boundary_truth(
            EdgeFaceControl(**{**control.__dict__, "uv_bounds": (0.0, 0.0, 0.0, 1.0)}),
            "u_min",
        )
    cylinder = edge_face_controls()[1]
    with pytest.raises(ValueError, match="positive radius"):
        analytic_boundary_truth(
            EdgeFaceControl(**{**cylinder.__dict__, "radius": 0.0}), "v_min"
        )


@pytest.mark.skipif(
    importlib.util.find_spec("OCP") is None,
    reason="install the geometry extra to run the native edge probe",
)
def test_backend_matches_curve_and_pcurve_truth_across_step() -> None:
    """Controlled curve types, lengths, ranges, and UV paths should survive."""
    probe = probe_edge_geometry()

    assert probe.constructed_valid
    assert probe.imported_valid
    assert probe.writer_status == "IFSelect_RetDone"
    assert probe.reader_status == "IFSelect_RetDone"
    assert probe.transferred_roots == 1
    assert len(probe.edge_observations) == 22
    assert len(probe.pcurve_observations) == 24
    for edge in probe.edge_observations:
        assert edge.observed_curve_type == edge.expected_curve_type
        assert edge.length_absolute_error < 1.0e-12
        assert edge.parameter_span_absolute_error < 1.0e-12
        assert edge.same_parameter_flag
        assert edge.same_range_flag
        assert not edge.degenerated
        assert edge.observed_is_seam == edge.expected_is_seam
        assert edge.max_pcurve_to_curve_distance < 2.0e-12
    for pcurve in probe.pcurve_observations:
        assert pcurve.pcurve_type == "line"
        assert pcurve.uv_max_absolute_error < 1.0e-12
        assert pcurve.range_alignment_error < 1.0e-12
        assert pcurve.max_pcurve_to_curve_distance < 2.0e-12
        assert pcurve.sample_count == 17


@pytest.mark.skipif(
    importlib.util.find_spec("OCP") is None,
    reason="install the geometry extra to run the native edge probe",
)
def test_seam_is_one_edge_with_two_oriented_pcurve_branches() -> None:
    """One seam edge should occur twice at U=0 and U=2π on the same face."""
    probe = probe_edge_geometry()
    seams = [item for item in probe.edge_observations if item.expected_is_seam]

    assert len(seams) == 2
    assert {item.stage for item in seams} == {"constructed", "step_imported"}
    for seam in seams:
        assert seam.face_id == "closed_cylinder"
        assert seam.boundary_roles == ("u_min", "u_max")
        assert seam.wire_occurrence_count == 2
        assert seam.pcurve_branch_count == 2
        branches = [
            item
            for item in probe.pcurve_observations
            if item.stage == seam.stage
            and item.face_id == seam.face_id
            and item.edge_index == seam.edge_index
        ]
        assert {item.boundary_role for item in branches} == {"u_min", "u_max"}
        assert {item.orientation for item in branches} == {"forward", "reversed"}
        assert {
            round(item.uv_mid[0], 12) for item in branches
        } == {0.0, round(2.0 * math.pi, 12)}


@pytest.mark.skipif(
    importlib.util.find_spec("OCP") is None,
    reason="install the geometry extra to run the native edge probe",
)
def test_topological_orientation_controls_vertex_parameter_order() -> None:
    """Reversed wire uses should traverse an ascending geometric range backward."""
    probe = probe_edge_geometry()

    for item in probe.pcurve_observations:
        if item.orientation == "forward":
            assert item.vertex_start_parameter < item.vertex_end_parameter
        elif item.orientation == "reversed":
            assert item.vertex_start_parameter > item.vertex_end_parameter
        else:  # pragma: no cover - the controlled corpus uses two orientations
            pytest.fail(f"unexpected orientation: {item.orientation}")


@pytest.mark.skipif(
    importlib.util.find_spec("OCP") is None,
    reason="install the geometry extra to run the native edge probe",
)
def test_step_fixture_contains_explicit_curve_representations() -> None:
    """The controlled STEP exchange should include edges, p-curves, and a seam."""
    probe = probe_edge_geometry()

    assert probe.step_edge_curve_count == 11
    assert probe.step_surface_curve_count == 10
    assert probe.step_pcurve_count == 12
    assert probe.step_seam_curve_count == 1


@pytest.mark.skipif(
    importlib.util.find_spec("OCP") is None,
    reason="install the geometry extra to run the native edge probe",
)
def test_edge_fixture_is_byte_deterministic_and_path_free() -> None:
    """Narrow writer normalization should stabilize the generated STEP bytes."""
    first = probe_edge_geometry()
    second = probe_edge_geometry()

    assert first.source_bytes == second.source_bytes
    assert first.source_sha256 == second.source_sha256
    assert b"2000-01-01T00:00:00" in first.source_bytes
    assert b"research-notes-edge-geometry-" not in first.source_bytes


def test_probe_rejects_invalid_platform_labels_without_importing_geometry() -> None:
    """Public provenance labels should fail predictably."""
    with pytest.raises(TypeError, match="platform_label"):
        probe_edge_geometry(platform_label=1)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="must not be empty"):
        probe_edge_geometry(platform_label="")
