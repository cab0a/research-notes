"""Tests for staged resource-bounded STEP intake decisions."""

from pathlib import Path

import pytest

from research_notes.resource_bounded_3d import (
    STAGES,
    IntakeLimits,
    build_intake_fixture_bytes,
    probe_resource_bounded_3d,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def probe():
    return probe_resource_bounded_3d(ROOT / "fixtures/resource-bounded-3d")


def test_generated_fixture_bytes_match_committed_corpus():
    expected = build_intake_fixture_bytes(
        ROOT / "fixtures/step-round-trip-preservation"
    )
    fixture_dir = ROOT / "fixtures/resource-bounded-3d"
    assert all((fixture_dir / name).read_bytes() == payload for name, payload in expected.items())


def test_every_control_matches_its_declared_terminal_decision(probe):
    assert len(probe.controls) == 13
    assert len(probe.fixtures) == 7
    assert all(item.expectation_met for item in probe.results)
    assert [sum(item.decision == name for item in probe.results) for name in ("accept", "quarantine", "reject")] == [2, 5, 6]


def test_every_control_has_a_complete_ordered_stage_record(probe):
    for control in probe.controls:
        rows = [item for item in probe.stages if item.control_id == control.control_id]
        assert tuple(item.stage for item in rows) == STAGES
        assert len(rows) == len(STAGES)


def test_parser_and_kernel_stages_are_process_isolated(probe):
    reached = [item for item in probe.stages if item.stage in {"parser", "kernel", "tessellation"} and item.decision != "not_run"]
    assert reached
    assert all(item.worker_isolated for item in reached)


def test_archive_and_raw_step_admit_the_same_payload(probe):
    results = {item.control_id: item for item in probe.results}
    raw = results["accepted_step"]
    archive = results["accepted_archive"]
    assert raw.decision == archive.decision == "accept"
    assert raw.payload_sha256 == archive.payload_sha256
    assert (raw.edge_count, raw.face_count, raw.triangle_count) == (12, 6, 12)
    assert (archive.edge_count, archive.face_count, archive.triangle_count) == (12, 6, 12)


def test_external_reference_stops_before_native_kernel(probe):
    result = next(item for item in probe.results if item.control_id == "external_reference_disabled")
    assert (result.decision, result.reason_code, result.external_reference_count) == ("quarantine", "external_resolution_disabled", 1)
    assert result.face_count is None
    kernel = next(item for item in probe.stages if item.control_id == result.control_id and item.stage == "kernel")
    assert kernel.decision == "not_run"


def test_topology_mesh_and_timeout_boundaries_remain_distinct(probe):
    results = {item.control_id: item for item in probe.results}
    assert (results["topology_face_limit"].terminal_stage, results["topology_face_limit"].face_count) == ("kernel", 6)
    assert (results["mesh_triangle_limit"].terminal_stage, results["mesh_triangle_limit"].triangle_count) == ("tessellation", 120)
    assert (results["kernel_timeout"].decision, results["kernel_timeout"].reason_code) == ("quarantine", "kernel_timeout")


def test_limits_reject_nonpositive_and_negative_values():
    with pytest.raises(ValueError, match="max_faces"):
        IntakeLimits(max_faces=0)
    with pytest.raises(ValueError, match="max_archive_depth"):
        IntakeLimits(max_archive_depth=-1)
