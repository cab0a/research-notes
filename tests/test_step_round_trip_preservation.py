"""Regression tests for semantic versus physical STEP preservation."""

from __future__ import annotations

from research_notes.step_round_trip_preservation import (
    probe_step_round_trip_preservation,
)


def test_preservation_corpus_is_deterministic_and_complete() -> None:
    probe = probe_step_round_trip_preservation()
    assert len(probe.controls) == 3
    assert len(probe.files) == 6
    assert len(probe.observations) == 6
    assert len(probe.comparisons) == 3
    assert all(len(item.source_sha256) == 64 for item in probe.files)


def test_semantic_geometry_topology_and_tolerances_survive() -> None:
    probe = probe_step_round_trip_preservation()
    assert all(item.structure_preserved for item in probe.comparisons)
    assert all(item.semantics_preserved for item in probe.comparisons)
    assert all(item.geometry_preserved for item in probe.comparisons)
    assert all(item.topology_preserved for item in probe.comparisons)
    assert all(item.attributes_preserved for item in probe.comparisons)
    assert all(item.tolerances_preserved for item in probe.comparisons)


def test_source_attribute_truth_is_not_assumed_from_round_trip_stability() -> None:
    probe = probe_step_round_trip_preservation()
    by_id = {item.control_id: item for item in probe.comparisons}
    assert by_id["named_colored_box"].source_attributes_match_truth
    assert by_id["named_colored_bspline"].source_attributes_match_truth
    assert not by_id["named_colored_through_hole"].source_attributes_match_truth
    assert by_id["named_colored_through_hole"].attributes_preserved


def test_semantic_preservation_does_not_require_byte_identity() -> None:
    probe = probe_step_round_trip_preservation()
    assert sum(item.normalized_bytes_identical for item in probe.comparisons) == 1
    assert all(item.semantics_preserved for item in probe.comparisons)
    assert all(item.geometry_preserved for item in probe.comparisons)


def test_every_imported_shape_is_valid() -> None:
    probe = probe_step_round_trip_preservation()
    assert all(item.metrics.analyzer_valid for item in probe.observations)
