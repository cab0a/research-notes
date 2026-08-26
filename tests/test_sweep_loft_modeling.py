"""Tests for v0.45.0 sweep, loft, and surface-construction contracts."""

from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import pytest

from experiments.run_sweep_loft_modeling import (
    CONTRACT_NAME,
    DECISION_FIELDS,
    DECISION_NAME,
    OBSERVATION_FIELDS,
    OBSERVATION_NAME,
    SUMMARY_FIELDS,
    SUMMARY_NAME,
    decision_rows,
    observation_rows,
    run,
    summary_rows,
)
from research_notes.sweep_loft_modeling import (
    construction_controls,
    probe_sweep_loft_modeling,
)


HAS_OCP = importlib.util.find_spec("OCP") is not None


@pytest.fixture(scope="module")
def probe() -> object:
    """Run the native construction probe once for all tests."""
    if not HAS_OCP:
        pytest.skip("install the geometry extra to run sweep and loft tests")
    return probe_sweep_loft_modeling()


def test_controls_cover_sweeps_lofts_surfaces_and_failures() -> None:
    """The catalog should isolate three construction families and two rejections."""
    controls = construction_controls()
    assert len(controls) == 7
    assert {item.operation for item in controls} == {
        "pipe_sweep",
        "section_loft",
        "point_grid_surface",
    }
    assert sum(item.expected_decision == "accept" for item in controls) == 5
    assert sum(item.expected_decision == "reject" for item in controls) == 2


def test_invalid_inputs_are_rejected_before_kernel_invocation(probe: object) -> None:
    """Known precondition failures should not be delegated to native behavior."""
    rejected = [item for item in probe.decisions if item.decision == "reject"]
    assert {(item.control_id, item.reason) for item in rejected} == {
        ("c0_corner_sweep", "spine_not_g1"),
        ("single_section_loft", "insufficient_sections"),
    }
    assert all(not item.kernel_invoked for item in rejected)


def test_accepted_results_are_valid_and_round_trip(probe: object) -> None:
    """All accepted construction stages should be kernel-valid."""
    assert len(probe.observations) == 10
    assert all(item.metrics.analyzer_valid for item in probe.observations)
    rows = summary_rows(probe)
    assert len(rows) == 5
    assert all(item["round_trip_passes"] == 1 for item in rows)


def test_analytic_sweep_and_ruled_loft_truth(probe: object) -> None:
    """Three independently measurable solids should match closed-form truth."""
    analytic = [
        item for item in probe.observations if item.expected_volume is not None
    ]
    assert len(analytic) == 6
    assert all(item.volume_absolute_error is not None for item in analytic)
    assert all(item.surface_area_absolute_error is not None for item in analytic)
    assert all(item.volume_absolute_error <= 1.0e-8 for item in analytic)
    assert all(item.surface_area_absolute_error <= 1.0e-8 for item in analytic)


def test_expected_support_surfaces_are_observable(probe: object) -> None:
    """Controlled operations should expose their expected result-surface families."""
    constructed = {
        item.control_id: item.metrics.surface_counts
        for item in probe.observations
        if item.stage == "constructed"
    }
    assert constructed["straight_circular_sweep"] == (("plane", 2), ("cylinder", 1))
    assert constructed["quarter_bend_sweep"] == (("plane", 2), ("torus", 1))
    assert constructed["ruled_circular_loft"] == (("plane", 2), ("cone", 1))
    assert constructed["smooth_square_loft"] == (("plane", 2), ("bspline", 4))
    assert constructed["interpolated_bspline_surface"] == (("bspline", 1),)


def test_smooth_loft_documents_input_envelope_overshoot(probe: object) -> None:
    """The smooth interpolant should visibly exceed the largest input half-span."""
    row = next(item for item in summary_rows(probe) if item["control_id"] == "smooth_square_loft")
    assert float(row["input_envelope_ratio"]) > 1.4


def test_serializers_have_exact_fields_and_no_local_paths(probe: object) -> None:
    """Public evidence should be stable and machine-independent."""
    decisions = decision_rows(probe)
    observations = observation_rows(probe)
    summaries = summary_rows(probe)
    assert all(tuple(item) == DECISION_FIELDS for item in decisions)
    assert all(tuple(item) == OBSERVATION_FIELDS for item in observations)
    assert all(tuple(item) == SUMMARY_FIELDS for item in summaries)
    joined = "\n".join(str(value) for row in observations for value in row.values())
    assert "/home/" not in joined
    assert "wsl.localhost" not in joined
    assert ":\\" not in joined


def test_artifact_and_fixture_generation_is_reproducible(tmp_path: Path) -> None:
    """A fresh run should write stable rows, accepted fixtures, and figures."""
    if not HAS_OCP:
        pytest.skip("install the geometry extra to run sweep and loft tests")
    output = tmp_path / "results"
    fixtures = tmp_path / "fixtures"
    run(output, fixtures, refresh=True)
    with (output / DECISION_NAME).open(encoding="utf-8", newline="") as handle:
        decisions = list(csv.DictReader(handle))
    with (output / OBSERVATION_NAME).open(encoding="utf-8", newline="") as handle:
        observations = list(csv.DictReader(handle))
    with (output / SUMMARY_NAME).open(encoding="utf-8", newline="") as handle:
        summaries = list(csv.DictReader(handle))
    contract = json.loads((output / CONTRACT_NAME).read_text(encoding="utf-8"))
    assert (len(decisions), len(observations), len(summaries)) == (7, 10, 5)
    assert contract["study_version"] == "v0.45.0"
    assert len(list(fixtures.glob("*.step"))) == 5
    assert (output / "sweep_loft_modeling.png").stat().st_size > 0
    assert (output / "sweep_loft_shapes.png").stat().st_size > 0
