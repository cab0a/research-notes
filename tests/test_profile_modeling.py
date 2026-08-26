"""Tests for v0.44.0 profile, extrusion, and revolution contracts."""

from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import pytest

from experiments.run_profile_modeling import (
    CONTRACT_NAME,
    OBSERVATION_FIELDS,
    OBSERVATION_NAME,
    RECOMPUTE_FIELDS,
    RECOMPUTE_NAME,
    SUMMARY_FIELDS,
    SUMMARY_NAME,
    observation_rows,
    recompute_rows,
    run,
    summary_rows,
)
from research_notes.profile_modeling import profile_controls, probe_profile_modeling


HAS_OCP = importlib.util.find_spec("OCP") is not None


@pytest.fixture(scope="module")
def probe() -> object:
    """Run the native profile probe once for all tests."""
    if not HAS_OCP:
        pytest.skip("install the geometry extra to run profile tests")
    return probe_profile_modeling()


def test_controls_cover_holes_extrusion_revolution_and_recompute() -> None:
    """The catalog should isolate the intended construction variables."""
    controls = profile_controls()
    assert len(controls) == 5
    assert {item.operation for item in controls} == {
        "linear_extrusion",
        "axis_revolution",
    }
    annulus = next(item for item in controls if item.control_id == "extruded_annulus")
    assert (annulus.outer_wire_count, annulus.inner_wire_count) == (1, 1)
    assert sum(item.recompute_family == "rectangle_height" for item in controls) == 2
    assert sum(item.recompute_family == "annular_revolution_angle" for item in controls) == 2


def test_all_profile_results_are_valid_and_match_analytic_truth(probe: object) -> None:
    """Every constructed and imported result should match its closed-form truth."""
    assert len(probe.observations) == 10
    assert all(item.metrics.analyzer_valid for item in probe.observations)
    assert all(item.volume_absolute_error <= 1.0e-8 for item in probe.observations)
    assert all(item.surface_area_absolute_error <= 1.0e-8 for item in probe.observations)


def test_round_trip_topology_and_surface_inventories_match(probe: object) -> None:
    """All five profile-driven results should preserve bounded inventories."""
    rows = summary_rows(probe)
    assert len(rows) == 5
    assert all(item["topology_matches"] == 1 for item in rows)
    assert all(item["surface_counts_match"] == 1 for item in rows)
    assert all(item["round_trip_passes"] == 1 for item in rows)


def test_annulus_hole_and_partial_revolution_change_topology(probe: object) -> None:
    """Inner wires and partial angles should remain observable in result topology."""
    constructed = {
        item.control_id: item for item in probe.observations if item.stage == "constructed"
    }
    assert constructed["extruded_annulus"].metrics.surface_counts == (
        ("plane", 2),
        ("cylinder", 2),
    )
    assert constructed["revolved_annulus_full"].metrics.face_count == 4
    assert constructed["revolved_annulus_half"].metrics.face_count == 6


def test_parameter_driven_recompute_relations_match_truth(probe: object) -> None:
    """Changing height or angle should produce the expected volume ratio."""
    rows = recompute_rows(probe)
    assert len(rows) == 2
    assert [float(item["expected_volume_ratio"]) for item in rows] == [1.4, 0.5]
    assert all(item["recompute_relation_passes"] == 1 for item in rows)


def test_step_face_entities_match_imported_faces(probe: object) -> None:
    """Every imported result should expose one source face entity per face."""
    imported = [item for item in probe.observations if item.stage == "step_imported"]
    assert all(item.step_advanced_face_count == item.metrics.face_count for item in imported)


def test_serializers_have_exact_fields_and_no_local_paths(probe: object) -> None:
    """Public evidence should be stable and machine-independent."""
    observations = observation_rows(probe)
    summaries = summary_rows(probe)
    recomputes = recompute_rows(probe)
    assert all(tuple(item) == OBSERVATION_FIELDS for item in observations)
    assert all(tuple(item) == SUMMARY_FIELDS for item in summaries)
    assert all(tuple(item) == RECOMPUTE_FIELDS for item in recomputes)
    joined = "\n".join(str(value) for row in observations for value in row.values())
    assert "/home/" not in joined
    assert "wsl.localhost" not in joined
    assert ":\\" not in joined


def test_artifact_and_fixture_generation_is_reproducible(tmp_path: Path) -> None:
    """A fresh run should write all stable rows, fixtures, and figures."""
    if not HAS_OCP:
        pytest.skip("install the geometry extra to run profile tests")
    output = tmp_path / "results"
    fixtures = tmp_path / "fixtures"
    run(output, fixtures, refresh=True)
    with (output / OBSERVATION_NAME).open(encoding="utf-8", newline="") as handle:
        observations = list(csv.DictReader(handle))
    with (output / SUMMARY_NAME).open(encoding="utf-8", newline="") as handle:
        summaries = list(csv.DictReader(handle))
    with (output / RECOMPUTE_NAME).open(encoding="utf-8", newline="") as handle:
        recomputes = list(csv.DictReader(handle))
    contract = json.loads((output / CONTRACT_NAME).read_text(encoding="utf-8"))
    assert (len(observations), len(summaries), len(recomputes)) == (10, 5, 2)
    assert contract["study_version"] == "v0.44.0"
    assert len(list(fixtures.glob("*.step"))) == 5
    assert (output / "profile_modeling.png").stat().st_size > 0
    assert (output / "profile_modeling_shapes.png").stat().st_size > 0

