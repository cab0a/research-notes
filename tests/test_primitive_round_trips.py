"""Tests for v0.43.0 primitive construction and STEP round trips."""

from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import pytest

from experiments.run_primitive_round_trips import (
    CONTRACT_NAME,
    OBSERVATION_FIELDS,
    OBSERVATION_NAME,
    SUMMARY_FIELDS,
    SUMMARY_NAME,
    observation_rows,
    run,
    summary_rows,
)
from research_notes.primitive_round_trips import (
    CONTRACT_VERSION,
    primitive_controls,
    probe_primitive_round_trips,
)


HAS_OCP = importlib.util.find_spec("OCP") is not None


@pytest.fixture(scope="module")
def probe() -> object:
    """Run the native primitive probe once for all tests."""
    if not HAS_OCP:
        pytest.skip("install the geometry extra to run primitive tests")
    return probe_primitive_round_trips()


def test_control_catalog_has_independent_truth_boundaries() -> None:
    """Analytic solids and the non-analytic patch should remain distinct."""
    controls = primitive_controls()
    assert [item.control_id for item in controls] == [
        "primitive_box",
        "primitive_cylinder",
        "primitive_cone",
        "primitive_sphere",
        "primitive_torus",
        "primitive_bspline_patch",
    ]
    assert all(item.expected_volume is not None for item in controls[:5])
    assert controls[-1].expected_volume is None
    assert controls[-1].expected_surface_area is None


def test_all_constructed_and_imported_shapes_are_valid(probe: object) -> None:
    """Every controlled route should produce a kernel-valid observation."""
    assert len(probe.observations) == 12
    assert all(item.metrics.analyzer_valid for item in probe.observations)
    assert all(item.surface_inventory_matches for item in probe.observations)
    assert all(item.solid_count_matches for item in probe.observations)
    assert {item.contract_version for item in probe.observations} == {
        CONTRACT_VERSION
    }


def test_analytic_truth_matches_kernel_measurements(probe: object) -> None:
    """Known volume and area formulas should agree at both stages."""
    for item in probe.observations:
        if item.expected_volume is not None:
            assert item.volume_absolute_error is not None
            assert item.volume_absolute_error < 2.0e-8
        if item.expected_surface_area is not None:
            assert item.surface_area_absolute_error is not None
            assert item.surface_area_absolute_error < 2.0e-8


def test_topology_and_surface_inventories_survive_exchange(probe: object) -> None:
    """Every primitive should retain its controlled topology inventories."""
    rows = summary_rows(probe)
    assert len(rows) == 6
    assert all(item["topology_matches"] == 1 for item in rows)
    assert all(item["surface_counts_match"] == 1 for item in rows)


def test_cone_parameterization_and_bspline_tolerance_drift_are_explicit(
    probe: object,
) -> None:
    """Equivalent cone signs and tolerance-inflated bounds should not be hidden."""
    rows = {item["control_id"]: item for item in summary_rows(probe)}
    assert float(
        rows["primitive_cone"][
            "support_parameter_maximum_absolute_difference"
        ]
    ) == pytest.approx(0.9272952180018061)
    assert float(
        rows["primitive_bspline_patch"]["bounds_maximum_absolute_difference"]
    ) == pytest.approx(0.0001999)
    assert sum(int(item["round_trip_contract_passes"]) for item in rows.values()) == 4


def test_step_sources_contain_one_advanced_face_per_imported_face(
    probe: object,
) -> None:
    """STEP exchange structure should agree with imported face inventories."""
    imported = [item for item in probe.observations if item.stage == "step_imported"]
    assert all(
        item.step_advanced_face_count == item.metrics.face_count for item in imported
    )
    assert all(item.step_entity_count == 1 for item in imported)


def test_serializers_follow_exact_contracts_without_local_paths(probe: object) -> None:
    """Public rows should be stable and machine-independent."""
    observations = observation_rows(probe)
    summaries = summary_rows(probe)
    assert all(tuple(item) == OBSERVATION_FIELDS for item in observations)
    assert all(tuple(item) == SUMMARY_FIELDS for item in summaries)
    joined = "\n".join(str(value) for row in observations for value in row.values())
    assert "/home/" not in joined
    assert "wsl.localhost" not in joined
    assert ":\\" not in joined


def test_generated_artifacts_and_fixtures_are_reproducible(tmp_path: Path) -> None:
    """A fresh run should write every declared artifact and fixture."""
    if not HAS_OCP:
        pytest.skip("install the geometry extra to run primitive tests")
    output = tmp_path / "results"
    fixtures = tmp_path / "fixtures"
    run(output, fixtures, refresh=True)
    with (output / OBSERVATION_NAME).open(encoding="utf-8", newline="") as handle:
        observations = list(csv.DictReader(handle))
    with (output / SUMMARY_NAME).open(encoding="utf-8", newline="") as handle:
        summaries = list(csv.DictReader(handle))
    contract = json.loads((output / CONTRACT_NAME).read_text(encoding="utf-8"))
    assert len(observations) == 12
    assert len(summaries) == 6
    assert tuple(observations[0]) == OBSERVATION_FIELDS
    assert tuple(summaries[0]) == SUMMARY_FIELDS
    assert contract["study_version"] == "v0.43.0"
    assert len(contract["fixture_sha256"]) == 6
    assert len(list(fixtures.glob("*.step"))) == 6
    assert (output / "primitive_round_trip.png").stat().st_size > 0
    assert (output / "primitive_round_trip_shapes.png").stat().st_size > 0

