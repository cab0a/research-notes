"""Tests for the v0.41.0 face-level analysis report contract."""

from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import pytest

from experiments.run_face_level_analysis import (
    REPORT_FIELDS,
    REPORT_NAME,
    handle_fixtures,
    report_row,
    run,
    write_contract,
)
from research_notes.face_analysis import (
    CONTRACT_VERSION,
    SUPPORTED_SURFACE_TYPES,
    analyze_shape_faces,
    build_face_analysis_shapes,
    face_analysis_controls,
    probe_face_analysis,
)


HAS_OCP = importlib.util.find_spec("OCP") is not None


@pytest.fixture(scope="module")
def probe() -> object:
    """Run the native face-analysis probe once for all report tests."""
    if not HAS_OCP:
        pytest.skip("install the geometry extra to run face-analysis tests")
    return probe_face_analysis()


def test_control_catalog_declares_all_six_surface_families() -> None:
    """The independent corpus contract should cover every v0.41 surface kind."""
    controls = face_analysis_controls()
    assert [item.control_id for item in controls] == [
        "through_hole_solid",
        "conical_solid",
        "spherical_solid",
        "toroidal_solid",
        "bspline_shell",
    ]
    declared = {
        surface_type
        for control in controls
        for surface_type, count in control.expected_surface_counts
        if count
    }
    assert declared == set(SUPPORTED_SURFACE_TYPES)
    assert controls[-1].expected_solid_count == 0
    assert all(item.expected_shell_count == 1 for item in controls)


def test_report_inventory_is_stable_across_step_import(probe: object) -> None:
    """Both stages should expose the same controlled surface inventory."""
    expected = {
        "plane": 8,
        "cylinder": 1,
        "cone": 1,
        "sphere": 1,
        "torus": 1,
        "bspline": 1,
    }
    assert len(probe.rows) == 26
    for stage in ("constructed", "step_imported"):
        rows = [item for item in probe.rows if item.stage == stage]
        assert len(rows) == 13
        assert {
            surface_type: sum(item.surface_type == surface_type for item in rows)
            for surface_type in SUPPORTED_SURFACE_TYPES
        } == expected


def test_primary_keys_are_unique_and_indices_are_stage_local(probe: object) -> None:
    """The CSV key should be unique without claiming cross-stage identity."""
    keys = {
        (item.stage, item.control_id, item.analysis_face_index) for item in probe.rows
    }
    assert len(keys) == len(probe.rows)
    assert {item.contract_version for item in probe.rows} == {CONTRACT_VERSION}
    for control in probe.controls:
        for stage in ("constructed", "step_imported"):
            indices = sorted(
                item.analysis_face_index
                for item in probe.rows
                if item.control_id == control.control_id and item.stage == stage
            )
            assert indices == list(range(1, len(indices) + 1))


def test_parent_solid_and_shell_memberships_are_explicit(probe: object) -> None:
    """Open-shell rows should not receive an invented solid parent."""
    for item in probe.rows:
        assert item.parent_shell_indices == (1,)
        if item.control_id == "bspline_shell":
            assert item.parent_solid_indices == ()
        else:
            assert item.parent_solid_indices == (1,)


def test_type_specific_surface_parameters_are_populated(probe: object) -> None:
    """Each supported family should use only its applicable parameter group."""
    constructed = [item for item in probe.rows if item.stage == "constructed"]
    plane = next(item for item in constructed if item.surface_type == "plane")
    cylinder = next(item for item in constructed if item.surface_type == "cylinder")
    cone = next(item for item in constructed if item.surface_type == "cone")
    sphere = next(item for item in constructed if item.surface_type == "sphere")
    torus = next(item for item in constructed if item.surface_type == "torus")
    bspline = next(item for item in constructed if item.surface_type == "bspline")

    assert plane.plane_normal is not None
    assert plane.surface_axis is None
    assert cylinder.radius == pytest.approx(1.25)
    assert cylinder.surface_axis is not None
    assert cone.radius == pytest.approx(3.0)
    assert abs(cone.semi_angle_degrees) == pytest.approx(16.69924423399362)
    assert sphere.radius == pytest.approx(2.0)
    assert torus.radius == pytest.approx(4.0)
    assert torus.secondary_radius == pytest.approx(1.0)
    assert (
        bspline.u_degree,
        bspline.v_degree,
        bspline.u_pole_count,
        bspline.v_pole_count,
        bspline.u_knot_count,
        bspline.v_knot_count,
    ) == (3, 3, 4, 4, 2, 2)
    assert not bspline.u_periodic
    assert not bspline.v_periodic
    assert not bspline.u_rational
    assert not bspline.v_rational


def test_geometry_fields_are_finite_and_normals_are_unit_length(probe: object) -> None:
    """Required numeric columns should be usable for every controlled face."""
    for item in probe.rows:
        assert item.area > 0.0
        assert item.uv_bounds[0] < item.uv_bounds[1]
        assert item.uv_bounds[2] < item.uv_bounds[3]
        assert sum(value * value for value in item.representative_normal) == pytest.approx(
            1.0, abs=1.0e-12
        )
        assert item.outer_wire_count == 1
        assert item.boundary_edge_count > 0
        assert item.face_tolerance > 0.0


def test_inner_wires_and_adjacency_are_reported_without_self_seams(
    probe: object,
) -> None:
    """Hole rims should be inner wires while periodic self-seams stay nonadjacent."""
    for stage in ("constructed", "step_imported"):
        hole_rows = [
            item
            for item in probe.rows
            if item.control_id == "through_hole_solid" and item.stage == stage
        ]
        assert sum(item.inner_wire_count > 0 for item in hole_rows) == 2
        cylinder = next(item for item in hole_rows if item.surface_type == "cylinder")
        assert len(cylinder.adjacent_face_indices) == 2
        periodic = [
            item
            for item in probe.rows
            if item.stage == stage and item.surface_type in {"sphere", "torus"}
        ]
        assert all(not item.adjacent_face_indices for item in periodic)


def test_metadata_values_never_cross_an_unproven_source_boundary(
    probe: object,
) -> None:
    """Control-manifest metadata must not be presented as STEP/XCAF metadata."""
    constructed = [item for item in probe.rows if item.stage == "constructed"]
    imported = [item for item in probe.rows if item.stage == "step_imported"]
    assert all(item.name and item.color_rgb for item in constructed)
    assert {item.name_source for item in constructed} == {
        "synthetic_control_manifest:shape"
    }
    assert {item.color_source for item in constructed} == {
        "synthetic_control_manifest:shape"
    }
    assert all(item.name is None and item.color_rgb is None for item in imported)
    assert {item.name_source for item in imported} == {
        "not_present:stepcontrol_topods_shape"
    }
    assert {item.color_source for item in imported} == {
        "not_present:stepcontrol_topods_shape"
    }


def test_round_trip_matching_uses_geometry_instead_of_local_indices(
    probe: object,
) -> None:
    """The evaluation should compare faces without promoting indices to identity."""
    assert len(probe.matches) == 13
    assert {item.matched_by for item in probe.matches} == {
        "surface_type_then_nearest_centroid"
    }
    assert max(item.area_absolute_difference for item in probe.matches) < 2.0e-11
    assert max(item.centroid_distance for item in probe.matches) < 1.0e-12
    assert all(item.orientation_matches for item in probe.matches)
    assert all(item.outer_wire_count_matches for item in probe.matches)
    assert all(item.inner_wire_count_matches for item in probe.matches)
    assert all(item.boundary_edge_count_matches for item in probe.matches)


def test_cone_angle_sign_change_is_preserved_as_evidence(probe: object) -> None:
    """Equivalent cone axes may change the sign of the reported semi-angle."""
    values = {
        item.stage: item.semi_angle_degrees
        for item in probe.rows
        if item.surface_type == "cone"
    }
    assert values["constructed"] * values["step_imported"] < 0.0
    assert abs(values["constructed"]) == pytest.approx(
        abs(values["step_imported"]), abs=1.0e-11
    )


def test_tolerance_is_observed_instead_of_treated_as_design_truth(
    probe: object,
) -> None:
    """The deliberately raised B-spline tolerance should be reconstructed."""
    constructed = next(
        item
        for item in probe.rows
        if item.stage == "constructed" and item.control_id == "bspline_shell"
    )
    imported = next(
        item
        for item in probe.rows
        if item.stage == "step_imported" and item.control_id == "bspline_shell"
    )
    assert constructed.face_tolerance == pytest.approx(2.0e-4)
    assert imported.face_tolerance == pytest.approx(1.0e-7)


def test_csv_contract_has_exact_fields_and_no_absolute_paths(probe: object) -> None:
    """Flattened rows should conform and remain independent of local paths."""
    rows = [report_row(item) for item in probe.rows]
    assert all(set(item) == set(REPORT_FIELDS) for item in rows)
    assert all(tuple(item.keys()) != () for item in rows)
    joined = "\n".join(value for item in rows for value in item.values())
    assert "/home/" not in joined
    assert "wsl.localhost" not in joined
    assert ":\\" not in joined


def test_contract_records_nullability_and_local_index_scope(
    probe: object, tmp_path: Path
) -> None:
    """The machine-readable contract should make key ambiguities explicit."""
    path = tmp_path / "contract.json"
    write_contract(path, probe)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["contract_version"] == CONTRACT_VERSION
    assert payload["csv"]["ordered_fields"] == list(REPORT_FIELDS)
    assert payload["csv"]["primary_key"] == [
        "stage",
        "control_id",
        "analysis_face_index",
    ]
    assert "not a persistent CAD identity" in payload["index_scope"]
    assert payload["metadata"]["metadata_is_not_inferred"]


def test_generated_artifacts_and_fixtures_are_reproducible(
    probe: object, tmp_path: Path
) -> None:
    """A second run should verify fixed fixtures and reproduce the CSV report."""
    output = tmp_path / "results"
    fixtures = tmp_path / "fixtures"
    run(output, fixtures, refresh=True)
    handle_fixtures(fixtures, probe, refresh=False)
    with (output / REPORT_NAME).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 26
    assert tuple(rows[0]) == REPORT_FIELDS


def test_stage_and_fixture_provenance_combinations_are_validated() -> None:
    """Invalid provenance combinations should fail before face traversal."""
    if not HAS_OCP:
        pytest.skip("install the geometry extra to run face-analysis tests")
    control = face_analysis_controls()[0]
    shape = build_face_analysis_shapes()[control.control_id]
    with pytest.raises(ValueError, match="requires fixture provenance"):
        analyze_shape_faces(shape, control=control, stage="step_imported")
