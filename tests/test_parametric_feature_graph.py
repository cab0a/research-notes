"""Tests for the v0.55.0 parametric feature graph contract."""

import json
from pathlib import Path

import pytest

from research_notes.parametric_feature_graph import probe_parametric_feature_graphs


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def probe():
    return probe_parametric_feature_graphs(
        ROOT / "fixtures/feature-recognition-benchmark/benchmark_through_hole_baseline.step"
    )


def test_graph_catalog_separates_explicit_models_from_import_candidate(probe):
    assert len(probe.graphs) == 4
    assert [item.graph_kind for item in probe.graphs].count("explicit_construction") == 3
    assert [item.graph_kind for item in probe.graphs].count("import_reconstruction_candidate") == 1
    assert len(probe.evaluations) == len(probe.fixtures) == 3


def test_all_graph_structural_validations_pass(probe):
    assert len(probe.validations) == 16
    assert all(item.passed for item in probe.validations)
    assert all(len(item.fingerprint_sha256) == 64 for item in probe.graphs)


def test_explicit_results_match_truth_and_step_round_trip(probe):
    for item in probe.evaluations:
        assert item.volume_truth_absolute_error < 1.0e-9
        assert item.area_truth_absolute_error < 1.0e-9
        assert item.imported_volume_absolute_difference < 1.0e-9
        assert item.imported_area_absolute_difference < 1.0e-9
        assert item.topology_counts_match
        assert item.analyzer_valid_both


def test_imported_candidate_never_becomes_authoring_history(probe):
    graph = next(item for item in probe.graphs if item.graph_kind == "import_reconstruction_candidate")
    assert not [item for item in graph.nodes if item.node_type == "result"]
    candidate = next(item for item in graph.nodes if item.node_type == "reconstruction_candidate")
    assert dict(candidate.attributes)["status"] == "unconfirmed"
    reference = next(item for item in graph.nodes if item.node_type == "import_reference")
    assert dict(reference.attributes)["sha256"] == probe.import_reference_sha256


def test_node_types_cover_parametric_construction_contract(probe):
    explicit = [item for graph in probe.graphs if graph.graph_kind == "explicit_construction" for item in graph.nodes]
    assert {item.node_type for item in explicit} == {"datum_plane", "parameter", "sketch", "feature", "result"}


def test_committed_contract_states_recompute_and_history_boundaries():
    contract = json.loads((ROOT / "results/parametric_feature_graph_contract.json").read_text(encoding="utf-8"))
    assert contract["all_validations_pass"]
    boundaries = " ".join(contract["claim_boundaries"])
    assert "not inferred from STEP" in boundaries
    assert "does not yet provide" in boundaries
