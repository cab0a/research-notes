"""Tests for the v0.42.0 tessellation and visual-diagnostic contracts."""

from __future__ import annotations

import csv
import importlib.util
import json
import math
import re
from pathlib import Path

import pytest

from experiments.run_tessellation_diagnostics import (
    CONTRACT_NAME,
    FACE_FIELDS,
    FACE_NAME,
    SUMMARY_FIELDS,
    SUMMARY_NAME,
    TRIANGLE_FIELDS,
    TRIANGLE_NAME,
    face_row,
    handle_fixtures,
    run,
    summary_rows,
    triangle_row,
    write_contract,
)
from research_notes.tessellation_diagnostics import (
    CONTRACT_VERSION,
    SOURCE_MAPPING_METHOD,
    mesh_conditions,
    probe_tessellation_diagnostics,
    tessellation_controls,
)


HAS_OCP = importlib.util.find_spec("OCP") is not None


@pytest.fixture(scope="module")
def probe() -> object:
    """Run the native tessellation probe once for all observation tests."""
    if not HAS_OCP:
        pytest.skip("install the geometry extra to run tessellation tests")
    return probe_tessellation_diagnostics()


def test_conditions_form_the_declared_two_by_two_design() -> None:
    """Linear and angular controls should vary independently and absolutely."""
    conditions = mesh_conditions()
    assert [item.condition_id for item in conditions] == [
        "coarse_both",
        "fine_angular",
        "fine_linear",
        "fine_both",
    ]
    assert {
        (item.linear_deflection, item.angular_deflection_radians)
        for item in conditions
    } == {(0.8, 0.7), (0.8, 0.25), (0.05, 0.7), (0.05, 0.25)}


def test_controls_cover_trims_periodicity_and_free_form_curvature() -> None:
    """The corpus should retain three distinct meshing challenges."""
    controls = tessellation_controls()
    assert [item.control_id for item in controls] == [
        "meshing_through_hole",
        "meshing_sphere",
        "meshing_bspline_shell",
    ]
    assert [item.expected_face_count for item in controls] == [7, 1, 1]
    assert controls[0].expected_surface_counts == (("plane", 6), ("cylinder", 1))
    assert controls[1].expected_surface_counts == (("sphere", 1),)
    assert controls[2].expected_surface_counts == (("bspline", 1),)


def test_direct_step_face_sources_are_recorded(probe: object) -> None:
    """Every controlled imported face should map to an ADVANCED_FACE instance."""
    assert len(probe.source_references) == 9
    assert all(item.source_entity_id for item in probe.source_references)
    assert {item.source_entity_type for item in probe.source_references} == {
        "ADVANCED_FACE"
    }
    assert {item.mapping_method for item in probe.source_references} == {
        SOURCE_MAPPING_METHOD
    }
    for control in probe.controls:
        ids = [
            item.source_entity_id
            for item in probe.source_references
            if item.control_id == control.control_id
        ]
        assert len(ids) == len(set(ids))


def test_source_entity_ids_exist_in_committed_fixture_bytes(probe: object) -> None:
    """Transfer-history labels should resolve to constructors in source bytes."""
    fixture_by_control = {item.fixture_id: item for item in probe.fixtures}
    for reference in probe.source_references:
        source = fixture_by_control[reference.control_id].source_bytes
        pattern = (
            rb"(?m)^\s*"
            + re.escape(reference.source_entity_id.encode("ascii"))
            + rb"\s*=\s*ADVANCED_FACE\s*\("
        )
        assert re.search(pattern, source)


def test_observation_inventories_and_keys_are_stable(probe: object) -> None:
    """All expected faces and triangles should have unique local keys."""
    assert len(probe.faces) == 36
    assert len(probe.triangles) == 3782
    face_keys = {
        (item.control_id, item.mesh_condition, item.analysis_face_index)
        for item in probe.faces
    }
    triangle_keys = {
        (
            item.control_id,
            item.mesh_condition,
            item.analysis_face_index,
            item.analysis_triangle_index,
        )
        for item in probe.triangles
    }
    assert len(face_keys) == len(probe.faces)
    assert len(triangle_keys) == len(probe.triangles)
    assert {item.contract_version for item in probe.faces} == {CONTRACT_VERSION}
    assert {item.contract_version for item in probe.triangles} == {CONTRACT_VERSION}


def _summary_by_key(probe: object) -> dict[tuple[str, str], dict[str, str]]:
    return {
        (item["control_id"], item["mesh_condition"]): item
        for item in summary_rows(probe)
    }


def test_surface_families_respond_to_different_controls(probe: object) -> None:
    """The factorial design should expose which requested input dominates."""
    rows = _summary_by_key(probe)
    assert [
        int(rows[("meshing_through_hole", condition)]["triangle_count"])
        for condition in ("coarse_both", "fine_angular", "fine_linear", "fine_both")
    ] == [88, 220, 88, 220]
    assert [
        int(rows[("meshing_sphere", condition)]["triangle_count"])
        for condition in ("coarse_both", "fine_angular", "fine_linear", "fine_both")
    ] == [168, 1260, 422, 1260]
    assert [
        int(rows[("meshing_bspline_shell", condition)]["triangle_count"])
        for condition in ("coarse_both", "fine_angular", "fine_linear", "fine_both")
    ] == [10, 10, 18, 18]


def test_refinement_reduces_controlled_area_differences(probe: object) -> None:
    """Relevant refinements should reduce area residuals without a universal rule."""
    rows = _summary_by_key(probe)

    def difference(control: str, condition: str) -> float:
        return float(rows[(control, condition)]["relative_area_difference"])

    assert difference("meshing_through_hole", "fine_angular") < difference(
        "meshing_through_hole", "coarse_both"
    )
    assert difference("meshing_sphere", "fine_angular") < difference(
        "meshing_sphere", "fine_linear"
    ) < difference("meshing_sphere", "coarse_both")
    assert difference("meshing_bspline_shell", "fine_linear") < difference(
        "meshing_bspline_shell", "coarse_both"
    )


def test_sampled_surface_deviation_is_diagnostic_not_a_bound(probe: object) -> None:
    """All UV samples should be finite while refinement relationships remain local."""
    assert all(item.uv_nodes is not None for item in probe.triangles)
    assert all(item.barycentric_uv is not None for item in probe.triangles)
    assert all(item.sampled_surface_point is not None for item in probe.triangles)
    assert all(
        item.sampled_surface_deviation is not None
        and math.isfinite(item.sampled_surface_deviation)
        and item.sampled_surface_deviation >= 0.0
        for item in probe.triangles
    )
    rows = _summary_by_key(probe)
    coarse = float(
        rows[("meshing_sphere", "coarse_both")][
            "maximum_sampled_surface_deviation"
        ]
    )
    fine = float(
        rows[("meshing_sphere", "fine_both")][
            "maximum_sampled_surface_deviation"
        ]
    )
    assert fine < coarse


def test_sphere_pole_degeneracy_is_retained_explicitly(probe: object) -> None:
    """Zero-area pole triangles should remain visible and have no normal."""
    for condition in probe.conditions:
        sphere = [
            item
            for item in probe.triangles
            if item.control_id == "meshing_sphere"
            and item.mesh_condition == condition.condition_id
        ]
        assert sum(item.is_degenerate for item in sphere) == 2
    assert sum(item.is_degenerate for item in probe.triangles) == 8
    assert all(
        (item.oriented_normal is None) == item.is_degenerate
        for item in probe.triangles
    )
    for item in probe.triangles:
        if item.oriented_normal is not None:
            assert sum(value * value for value in item.oriented_normal) == pytest.approx(
                1.0, abs=1.0e-12
            )


def test_mesh_area_can_lie_on_either_side_of_exact_area(probe: object) -> None:
    """Approximation error should not be documented as one-sided."""
    rows = _summary_by_key(probe)
    for condition in probe.conditions:
        assert (
            float(
                rows[("meshing_through_hole", condition.condition_id)][
                    "signed_area_difference"
                ]
            )
            < 0.0
        )
        assert (
            float(
                rows[("meshing_sphere", condition.condition_id)][
                    "signed_area_difference"
                ]
            )
            < 0.0
        )
        assert (
            float(
                rows[("meshing_bspline_shell", condition.condition_id)][
                    "signed_area_difference"
                ]
            )
            > 0.0
        )


def test_face_summaries_equal_triangle_observations(probe: object) -> None:
    """Face counts and areas should be recomputable from triangle rows."""
    for face in probe.faces:
        triangles = [
            item
            for item in probe.triangles
            if item.control_id == face.control_id
            and item.mesh_condition == face.mesh_condition
            and item.analysis_face_index == face.analysis_face_index
        ]
        assert len(triangles) == face.triangle_count
        assert sum(item.is_degenerate for item in triangles) == face.degenerate_triangle_count
        assert sum(item.area for item in triangles) == pytest.approx(
            face.mesh_surface_area, abs=1.0e-12
        )
        assert {item.source_entity_id for item in triangles} == {
            face.source_entity_id
        }


def test_csv_serializers_follow_exact_contracts_without_local_paths(
    probe: object,
) -> None:
    """Serialized evidence should have exact fields and no machine-local paths."""
    triangle_rows = [triangle_row(item) for item in probe.triangles]
    face_rows = [face_row(item) for item in probe.faces]
    summaries = summary_rows(probe)
    assert all(set(item) == set(TRIANGLE_FIELDS) for item in triangle_rows)
    assert all(tuple(item) == FACE_FIELDS for item in face_rows)
    assert all(tuple(item) == SUMMARY_FIELDS for item in summaries)
    joined = "\n".join(value for item in triangle_rows for value in item.values())
    assert "/home/" not in joined
    assert "wsl.localhost" not in joined
    assert ":\\" not in joined


def test_contract_separates_requests_samples_and_identity(
    probe: object, tmp_path: Path
) -> None:
    """The machine-readable contract should preserve all critical claim boundaries."""
    path = tmp_path / CONTRACT_NAME
    write_contract(path, probe)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["contract_version"] == CONTRACT_VERSION
    assert payload["triangle_csv"]["ordered_fields"] == list(TRIANGLE_FIELDS)
    assert payload["face_csv"]["ordered_fields"] == list(FACE_FIELDS)
    assert payload["summary_csv"]["ordered_fields"] == list(SUMMARY_FIELDS)
    assert not payload["triangle_geometry"]["sample_is_bound"]
    assert not payload["source_entity_mapping"]["persistent_identity"]
    assert any(
        "not independently certified maximum errors" in item
        for item in payload["claim_boundaries"]
    )


def test_generated_artifacts_and_fixtures_are_reproducible(
    tmp_path: Path,
) -> None:
    """A fresh run should write all stable tables and byte-verify its fixtures."""
    if not HAS_OCP:
        pytest.skip("install the geometry extra to run tessellation tests")
    output = tmp_path / "results"
    fixtures = tmp_path / "fixtures"
    run(output, fixtures, refresh=True)
    fresh_probe = probe_tessellation_diagnostics()
    handle_fixtures(fixtures, fresh_probe, refresh=False)
    with (output / TRIANGLE_NAME).open(encoding="utf-8", newline="") as handle:
        triangles = list(csv.DictReader(handle))
    with (output / FACE_NAME).open(encoding="utf-8", newline="") as handle:
        faces = list(csv.DictReader(handle))
    with (output / SUMMARY_NAME).open(encoding="utf-8", newline="") as handle:
        summaries = list(csv.DictReader(handle))
    assert len(triangles) == 3782
    assert len(faces) == 36
    assert len(summaries) == 12
    assert tuple(triangles[0]) == TRIANGLE_FIELDS
    assert tuple(faces[0]) == FACE_FIELDS
    assert tuple(summaries[0]) == SUMMARY_FIELDS
