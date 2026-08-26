"""Tests for v0.47.0 fillet, chamfer, and topology-history contracts."""

from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import pytest

from experiments.run_topology_history import (
    CONTRACT_NAME,
    DECISION_FIELDS,
    DECISION_NAME,
    FACE_MATCH_FIELDS,
    FACE_MATCH_NAME,
    HISTORY_FIELDS,
    HISTORY_NAME,
    OBSERVATION_FIELDS,
    OBSERVATION_NAME,
    SUMMARY_FIELDS,
    SUMMARY_NAME,
    decision_rows,
    face_match_rows,
    history_rows,
    observation_rows,
    run,
    summary_rows,
)
from research_notes.topology_history import feature_controls, probe_topology_history


HAS_OCP = importlib.util.find_spec("OCP") is not None


@pytest.fixture(scope="module")
def probe() -> object:
    """Run the native feature probe once for all tests."""
    if not HAS_OCP:
        pytest.skip("install the geometry extra to run topology-history tests")
    return probe_topology_history()


def test_controls_cover_success_and_oversized_failure() -> None:
    """Both feature families should include accepted and rejected parameters."""
    controls = feature_controls()
    assert len(controls) == 4
    assert {item.operation for item in controls} == {"fillet", "chamfer"}
    assert sum(item.expected_decision == "accept" for item in controls) == 2
    assert sum(item.expected_decision == "reject" for item in controls) == 2
    assert all(item.selected_edge_endpoints[0] == (12.0, 0.0, 6.0) for item in controls)


def test_native_decisions_match_success_and_failure_controls(probe: object) -> None:
    """Unit parameters should succeed and oversized parameters should not complete."""
    decisions = {item.control_id: item for item in probe.decisions}
    assert decisions["edge_fillet_r1"].decision == "accept"
    assert decisions["edge_chamfer_d1"].decision == "accept"
    assert decisions["edge_fillet_r20"].reason == "native_not_done"
    assert decisions["edge_chamfer_d20"].reason == "native_not_done"
    assert all(item.kernel_invoked and item.contour_count == 1 for item in probe.decisions)


def test_successful_results_match_analytic_truth(probe: object) -> None:
    """Fillet and chamfer volume and area should match cross-section formulas."""
    assert len(probe.observations) == 4
    assert all(item.metrics.analyzer_valid for item in probe.observations)
    assert all(item.volume_absolute_error <= 1.0e-8 for item in probe.observations)
    assert all(item.surface_area_absolute_error <= 1.0e-8 for item in probe.observations)


def test_history_queries_follow_documented_source_kind_scope(probe: object) -> None:
    """Generated and modified queries should not be generalized beyond their API scope."""
    assert len(probe.history) == 52
    for control_id in ("edge_fillet_r1", "edge_chamfer_d1"):
        rows = [item for item in probe.history if item.control_id == control_id]
        assert sum(bool(item.generated_result_indices) for item in rows) == 1
        assert sum(bool(item.modified_result_indices) for item in rows) == 4
        assert sum(item.modified_is_split is True for item in rows) == 0
        assert sum((item.modified_target_max_source_count or 0) > 1 for item in rows) == 0
        assert all(item.is_deleted is None for item in rows if item.source_kind != "face")


def test_step_face_indices_are_values_not_identity(probe: object) -> None:
    """Equal local numbers should coexist with zero direct identity and no history."""
    assert len(probe.face_matches) == 14
    assert all(item.index_values_equal for item in probe.face_matches)
    assert all(not item.direct_topological_identity for item in probe.face_matches)
    assert all(not item.operation_history_available_after_import for item in probe.face_matches)
    assert all(item.area_absolute_difference <= 1.0e-8 for item in probe.face_matches)


def test_round_trip_summaries_preserve_geometry_not_history(probe: object) -> None:
    """Both accepted results should pass geometry while keeping history unavailable."""
    rows = summary_rows(probe)
    assert len(rows) == 2
    assert all(item["round_trip_passes"] == 1 for item in rows)
    assert all(item["round_trip_face_matches"] == 7 for item in rows)
    assert all(item["direct_face_identities_across_step"] == 0 for item in rows)
    assert all(item["imported_history_available"] == 0 for item in rows)


def test_serializers_have_exact_fields_and_no_local_paths(probe: object) -> None:
    """Public evidence should be stable and machine-independent."""
    decisions = decision_rows(probe)
    observations = observation_rows(probe)
    histories = history_rows(probe)
    matches = face_match_rows(probe)
    summaries = summary_rows(probe)
    assert all(tuple(item) == DECISION_FIELDS for item in decisions)
    assert all(tuple(item) == OBSERVATION_FIELDS for item in observations)
    assert all(tuple(item) == HISTORY_FIELDS for item in histories)
    assert all(tuple(item) == FACE_MATCH_FIELDS for item in matches)
    assert all(tuple(item) == SUMMARY_FIELDS for item in summaries)
    joined = "\n".join(str(value) for row in histories for value in row.values())
    assert "/home/" not in joined
    assert "wsl.localhost" not in joined
    assert ":\\" not in joined


def test_artifact_and_fixture_generation_is_reproducible(tmp_path: Path) -> None:
    """A fresh run should write stable rows, two fixtures, and figures."""
    if not HAS_OCP:
        pytest.skip("install the geometry extra to run topology-history tests")
    output = tmp_path / "results"
    fixtures = tmp_path / "fixtures"
    run(output, fixtures, refresh=True)
    with (output / DECISION_NAME).open(encoding="utf-8", newline="") as handle:
        decisions = list(csv.DictReader(handle))
    with (output / OBSERVATION_NAME).open(encoding="utf-8", newline="") as handle:
        observations = list(csv.DictReader(handle))
    with (output / HISTORY_NAME).open(encoding="utf-8", newline="") as handle:
        histories = list(csv.DictReader(handle))
    with (output / FACE_MATCH_NAME).open(encoding="utf-8", newline="") as handle:
        matches = list(csv.DictReader(handle))
    with (output / SUMMARY_NAME).open(encoding="utf-8", newline="") as handle:
        summaries = list(csv.DictReader(handle))
    contract = json.loads((output / CONTRACT_NAME).read_text(encoding="utf-8"))
    assert (len(decisions), len(observations), len(histories), len(matches), len(summaries)) == (4, 4, 52, 14, 2)
    assert contract["study_version"] == "v0.47.0"
    assert len(list(fixtures.glob("*.step"))) == 2
    assert (output / "topology_history.png").stat().st_size > 0
    assert (output / "feature_operation_shapes.png").stat().st_size > 0
