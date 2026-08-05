"""Tests for the v0.32 evaluated face-geometry contract."""

from __future__ import annotations

import importlib.util
import pytest

from research_notes.face_geometry import (
    FaceControl,
    analytic_face_truth,
    face_controls,
    probe_evaluated_face_geometry,
)


def test_analytic_catalog_has_separate_orientation_and_surface_controls() -> None:
    """The truth corpus should expose plane, cylinder, and reversed cases."""
    controls = face_controls()

    assert [item.face_id for item in controls] == [
        "plane_forward",
        "plane_reversed",
        "cylinder_forward",
    ]
    assert [item.surface_type for item in controls] == [
        "plane",
        "plane",
        "cylinder",
    ]
    assert [item.reversed for item in controls] == [False, True, False]
    assert [item.constructed_tolerance for item in controls] == [
        1.0e-4,
        2.0e-4,
        3.0e-4,
    ]


def test_plane_truth_is_derived_from_uv_spans_and_orientation() -> None:
    """A reversed face should flip only its oriented normal."""
    forward = analytic_face_truth(face_controls()[0])
    reversed_face = analytic_face_truth(face_controls()[1])

    assert forward.area == 25.0
    assert forward.centroid == (0.5, 1.5, 0.0)
    assert forward.representative_point == forward.centroid
    assert forward.support_normal == (0.0, 0.0, 1.0)
    assert forward.oriented_normal == forward.support_normal
    assert reversed_face.area == 12.0
    assert reversed_face.centroid == (20.5, 0.0, 5.0)
    assert reversed_face.support_normal == (0.0, 1.0, 0.0)
    assert reversed_face.oriented_normal == (0.0, -1.0, 0.0)


def test_cylinder_truth_uses_surface_area_and_area_weighted_centroid() -> None:
    """The cylindrical truth should not use the midpoint as its centroid."""
    truth = analytic_face_truth(face_controls()[2])

    assert truth.area == 17.5
    assert truth.radius == 2.5
    assert truth.centroid == pytest.approx(
        (11.24311536391273, -0.06396252960512383, 2.5), abs=1.0e-14
    )
    assert truth.representative_point == pytest.approx(
        (11.35075576467035, 0.1036774620197414, 2.5), abs=1.0e-14
    )
    assert truth.centroid != truth.representative_point


def test_invalid_analytic_control_fails_before_backend_use() -> None:
    """Degenerate bounds and nonorthogonal directions must not become truth."""
    control = face_controls()[0]
    with pytest.raises(ValueError, match="strictly increasing"):
        analytic_face_truth(
            FaceControl(
                **{
                    **control.__dict__,
                    "uv_bounds": (0.0, 0.0, -1.0, 1.0),
                }
            )
        )
    with pytest.raises(ValueError, match="orthogonal"):
        analytic_face_truth(
            FaceControl(
                **{
                    **control.__dict__,
                    "x_direction": (1.0, 0.0, 1.0),
                }
            )
        )
    with pytest.raises(TypeError, match="FaceControl"):
        analytic_face_truth("bad")  # type: ignore[arg-type]


@pytest.mark.skipif(
    importlib.util.find_spec("OCP") is None,
    reason="install the geometry extra to run the native face probe",
)
def test_backend_matches_analytic_truth_before_and_after_step() -> None:
    """Exact surfaces should remain within the synthetic numeric contract."""
    probe = probe_evaluated_face_geometry()

    assert probe.writer_status == "IFSelect_RetDone"
    assert probe.reader_status == "IFSelect_RetDone"
    assert probe.transferred_roots == 1
    assert probe.constructed_valid
    assert probe.imported_valid
    assert len(probe.evaluations) == 6
    for evaluation in probe.evaluations:
        assert evaluation.truth.surface_type == evaluation.measurement.surface_type
        assert evaluation.truth.orientation == evaluation.measurement.orientation
        assert evaluation.area_absolute_error < 1.0e-12
        assert evaluation.centroid_distance < 1.0e-12
        assert evaluation.uv_max_absolute_error < 5.0e-12
        assert evaluation.representative_point_distance < 1.0e-12
        assert evaluation.support_normal_angle_degrees < 1.0e-6
        assert evaluation.oriented_normal_angle_degrees < 1.0e-6
        assert evaluation.surface_origin_distance < 1.0e-12
        assert evaluation.surface_axis_angle_degrees < 1.0e-6
        assert evaluation.surface_x_direction_angle_degrees < 1.0e-6
        if evaluation.radius_absolute_error is not None:
            assert evaluation.radius_absolute_error < 1.0e-12


@pytest.mark.skipif(
    importlib.util.find_spec("OCP") is None,
    reason="install the geometry extra to run the native face probe",
)
def test_face_orientation_survives_but_face_tolerance_is_reconstructed() -> None:
    """Topology orientation and numeric tolerance should remain separate claims."""
    probe = probe_evaluated_face_geometry()
    constructed = [
        item for item in probe.evaluations if item.measurement.stage == "constructed"
    ]
    imported = [
        item for item in probe.evaluations if item.measurement.stage == "step_imported"
    ]

    assert [item.measurement.face_tolerance for item in constructed] == pytest.approx(
        [1.0e-4, 2.0e-4, 3.0e-4]
    )
    assert {item.measurement.face_tolerance for item in imported} == {1.0e-7}
    assert {item.measurement.orientation for item in imported} == {
        "forward",
        "reversed",
    }
    assert probe.exported_uncertainty_values
    assert set(probe.exported_uncertainty_values) == {1.0e-4}


@pytest.mark.skipif(
    importlib.util.find_spec("OCP") is None,
    reason="install the geometry extra to run the native face probe",
)
def test_face_fixture_is_byte_deterministic_and_path_free() -> None:
    """Narrow header normalization should make repeated outputs identical."""
    first = probe_evaluated_face_geometry()
    second = probe_evaluated_face_geometry()

    assert first.source_bytes == second.source_bytes
    assert first.source_sha256 == second.source_sha256
    assert b"2000-01-01T00:00:00" in first.source_bytes
    assert b"research-notes-face-geometry-" not in first.source_bytes


def test_probe_rejects_invalid_platform_labels_without_importing_geometry() -> None:
    """Public provenance labels should fail predictably."""
    with pytest.raises(TypeError, match="platform_label"):
        probe_evaluated_face_geometry(platform_label=1)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="must not be empty"):
        probe_evaluated_face_geometry(platform_label="")
