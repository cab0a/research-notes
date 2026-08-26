"""Tests for the v0.54.0 explainable learned-baseline contract."""

import json
from pathlib import Path

from research_notes.learned_3d_baselines import evaluate_baselines, load_dataset


ROOT = Path(__file__).resolve().parents[1]


def _probe():
    return evaluate_baselines(load_dataset(ROOT / "results/synthetic_3d_samples.csv"))


def test_four_small_baselines_are_fit_without_label_features():
    probe = _probe()
    assert [item.model_id for item in probe.models] == [
        "bounded_rule",
        "geometry_centroid",
        "graph_centroid",
        "tabular_centroid",
    ]
    assert all("supported_feature" not in item.feature_names for item in probe.models)
    assert all(item.abstention_threshold == 0.70 for item in probe.models)


def test_every_prediction_retains_source_and_explanation_evidence():
    probe = _probe()
    assert len(probe.predictions) == 4 * 36
    assert all(len(item.source_sha256) == 64 for item in probe.predictions)
    assert all(item.top_evidence_feature for item in probe.predictions)
    assert all(item.evidence_direction in {"supports_feature", "supports_none"} for item in probe.predictions)


def test_test_partition_contains_decisions_for_supported_and_unknown_families():
    probe = _probe()
    test = [item for item in probe.predictions if item.split == "test"]
    assert {item.family_id for item in test} == {"fillet_operation", "toroidal_surface"}
    for model in probe.models:
        selected = [item for item in test if item.model_id == model.model_id]
        assert any(item.truth_label == "supported" for item in selected)
        assert any(item.truth_label == "none" for item in selected)
        assert any(item.decision != "abstain" for item in selected)


def test_temperature_is_selected_from_declared_grid():
    probe = _probe()
    learned = [item for item in probe.models if item.model_kind == "nearest_centroid"]
    assert all(item.temperature in {0.25, 0.5, 1.0, 2.0, 4.0, 8.0} for item in learned)


def test_test_results_expose_both_success_and_failure_modes():
    probe = _probe()
    by_model = {
        model.model_id: [
            item
            for item in probe.predictions
            if item.model_id == model.model_id and item.split == "test"
        ]
        for model in probe.models
    }
    assert all(item.raw_correct for item in by_model["bounded_rule"])
    assert all(item.raw_correct for item in by_model["tabular_centroid"])
    graph_decided = [item for item in by_model["graph_centroid"] if item.decision != "abstain"]
    assert len(graph_decided) == 4
    assert all(item.decided_correct for item in graph_decided)
    geometry_decided = [item for item in by_model["geometry_centroid"] if item.decision != "abstain"]
    assert len(geometry_decided) == 4
    assert not any(item.decided_correct for item in geometry_decided)


def test_committed_contract_separates_fit_calibration_and_test():
    contract = json.loads((ROOT / "results/learned_3d_model_contract.json").read_text(encoding="utf-8"))
    assert contract["fit_split"] == "train"
    assert contract["calibration_split"] == "validation"
    assert contract["evaluation_split"] == "test"
    assert "not a guarantee" in " ".join(contract["claim_boundaries"])
