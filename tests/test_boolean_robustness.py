"""Tests for v0.46.0 Boolean-operation and robustness contracts."""

from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import pytest

from experiments.run_boolean_robustness import (
    CONTRACT_NAME,
    DECISION_FIELDS,
    DECISION_NAME,
    OBSERVATION_FIELDS,
    OBSERVATION_NAME,
    SUMMARY_FIELDS,
    SUMMARY_NAME,
    TOLERANCE_FIELDS,
    TOLERANCE_NAME,
    decision_rows,
    observation_rows,
    run,
    summary_rows,
    tolerance_rows,
)
from research_notes.boolean_robustness import (
    boolean_controls,
    exact_axis_aligned_measure,
    probe_boolean_robustness,
)


HAS_OCP = importlib.util.find_spec("OCP") is not None


@pytest.fixture(scope="module")
def probe() -> object:
    """Run the native Boolean probe once for all tests."""
    if not HAS_OCP:
        pytest.skip("install the geometry extra to run Boolean tests")
    return probe_boolean_robustness()


def test_controls_cover_operations_relationships_and_fuzzy_pair() -> None:
    """The catalog should isolate operation and contact classes."""
    controls = boolean_controls()
    assert len(controls) == 7
    assert {item.operation for item in controls} == {"fuse", "common", "cut"}
    assert {item.relationship for item in controls} == {
        "volume_overlap",
        "positive_gap",
        "shared_face",
        "gap_0.00005",
    }
    assert sum(item.requested_fuzzy_value > 0.0 for item in controls) == 1


def test_independent_axis_aligned_truth() -> None:
    """Cell decomposition should recover known overlap measures."""
    first = (0.0, 0.0, 0.0, 4.0, 4.0, 4.0)
    second = (2.0, 1.0, 1.0, 6.0, 5.0, 5.0)
    assert exact_axis_aligned_measure(first, second, "fuse") == (110.0, 150.0)
    assert exact_axis_aligned_measure(first, second, "common") == (18.0, 42.0)
    assert exact_axis_aligned_measure(first, second, "cut") == (46.0, 96.0)


def test_operations_complete_without_mutating_operands(probe: object) -> None:
    """Non-destructive mode should preserve both operand measurements."""
    assert all(item.is_done and item.has_history for item in probe.decisions)
    assert all(item.first_operand_unchanged for item in probe.decisions)
    assert all(item.second_operand_unchanged for item in probe.decisions)


def test_commutative_invariants_match_for_fuse_and_common(probe: object) -> None:
    """Operand reversal should retain bounded topology and measures."""
    controls = {item.control_id: item for item in probe.controls}
    for item in probe.decisions:
        if controls[item.control_id].operation in {"fuse", "common"}:
            assert item.commutative_invariants_match is True
        else:
            assert item.commutative_invariants_match is None


def test_exact_cases_match_truth_and_round_trip(probe: object) -> None:
    """Every non-fuzzy control should match exact cuboid-set measures."""
    controls = {item.control_id: item for item in probe.controls}
    exact = [
        item for item in probe.observations
        if controls[item.control_id].expects_exact_set_measure
    ]
    assert len(exact) == 12
    assert all(item.volume_exact_set_difference <= 1.0e-8 for item in exact)
    assert all(item.surface_area_exact_set_difference <= 1.0e-8 for item in exact)
    rows = {item["control_id"]: item for item in summary_rows(probe)}
    assert all(
        rows[control_id]["round_trip_passes"] == 1
        for control_id, control in controls.items()
        if control.expects_exact_set_measure
    )
    assert rows["near_gap_fuse_fuzzy"]["round_trip_passes"] == 0


def test_fuzzy_value_bridges_gap_and_records_distortion(probe: object) -> None:
    """The controlled fuzzy setting should change connectivity and exact measure."""
    row = tolerance_rows(probe)[0]
    assert row["default_solid_count"] == 2
    assert row["fuzzy_solid_count"] == 1
    assert row["fuzzy_bridges_gap"] == 1
    assert float(row["fuzzy_exact_volume_difference"]) > 1.0e-4
    assert float(row["fuzzy_maximum_vertex_tolerance"]) > 5.0e-5


def test_serializers_have_exact_fields_and_no_local_paths(probe: object) -> None:
    """Public evidence should be stable and machine-independent."""
    decisions = decision_rows(probe)
    observations = observation_rows(probe)
    summaries = summary_rows(probe)
    tolerances = tolerance_rows(probe)
    assert all(tuple(item) == DECISION_FIELDS for item in decisions)
    assert all(tuple(item) == OBSERVATION_FIELDS for item in observations)
    assert all(tuple(item) == SUMMARY_FIELDS for item in summaries)
    assert all(tuple(item) == TOLERANCE_FIELDS for item in tolerances)
    joined = "\n".join(str(value) for row in observations for value in row.values())
    assert "/home/" not in joined
    assert "wsl.localhost" not in joined
    assert ":\\" not in joined


def test_artifact_and_fixture_generation_is_reproducible(tmp_path: Path) -> None:
    """A fresh run should write stable rows, seven fixtures, and figures."""
    if not HAS_OCP:
        pytest.skip("install the geometry extra to run Boolean tests")
    output = tmp_path / "results"
    fixtures = tmp_path / "fixtures"
    run(output, fixtures, refresh=True)
    with (output / DECISION_NAME).open(encoding="utf-8", newline="") as handle:
        decisions = list(csv.DictReader(handle))
    with (output / OBSERVATION_NAME).open(encoding="utf-8", newline="") as handle:
        observations = list(csv.DictReader(handle))
    with (output / SUMMARY_NAME).open(encoding="utf-8", newline="") as handle:
        summaries = list(csv.DictReader(handle))
    with (output / TOLERANCE_NAME).open(encoding="utf-8", newline="") as handle:
        tolerances = list(csv.DictReader(handle))
    contract = json.loads((output / CONTRACT_NAME).read_text(encoding="utf-8"))
    assert (len(decisions), len(observations), len(summaries), len(tolerances)) == (7, 14, 7, 1)
    assert contract["study_version"] == "v0.46.0"
    assert len(list(fixtures.glob("*.step"))) == 7
    assert (output / "boolean_operation_robustness.png").stat().st_size > 0
    assert (output / "boolean_operation_shapes.png").stat().st_size > 0
