"""Tests for the v0.52.0 feature-recognition robustness benchmark."""

import json
from pathlib import Path

import pytest

from research_notes.feature_benchmark import benchmark_cases, probe_feature_benchmark


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def probe():
    return probe_feature_benchmark()


def test_catalog_crosses_eight_families_with_four_perturbations():
    cases = benchmark_cases()
    assert len(cases) == 32
    assert len({item.source_control_id for item in cases}) == 8
    assert {item.perturbation for item in cases} == {
        "baseline",
        "small_scale",
        "rotated_z_30",
        "tolerance_healed",
    }


def test_each_case_has_constructed_and_step_imported_evidence(probe):
    assert len(probe.fixtures) == 32
    assert len(probe.observations) == 64
    assert all(len(item.source_sha256) == 64 for item in probe.fixtures)
    for case in probe.cases:
        rows = [item for item in probe.observations if item.case_id == case.case_id]
        assert [item.stage for item in rows] == ["constructed", "step_imported"]


def test_baseline_and_scale_controls_preserve_expected_classification(probe):
    selected = [
        item
        for item in probe.observations
        if item.perturbation in {"baseline", "small_scale"}
    ]
    assert len(selected) == 32
    assert all(item.classification_correct for item in selected)
    assert all(item.dimensions_correct for item in selected)


def test_rotated_axis_assumption_is_visible_as_abstention(probe):
    rotated = [
        item
        for item in probe.observations
        if item.perturbation == "rotated_z_30"
    ]
    assert any(item.decision == "abstain" for item in rotated)
    assert all(
        item.reason == "orientation_outside_axis_aligned_rule"
        for item in rotated
        if item.decision == "abstain"
    )


def test_negative_controls_are_rejected_not_promoted(probe):
    negatives = [
        item
        for item in probe.observations
        if item.source_control_id in {"plain_block", "cylindrical_boss"}
    ]
    assert len(negatives) == 16
    assert all(item.decision == "reject" for item in negatives)
    assert all(item.observed_label == "none" for item in negatives)


def test_step_exchange_never_changes_the_observed_label(probe):
    for case in probe.cases:
        constructed, imported = [
            item for item in probe.observations if item.case_id == case.case_id
        ]
        assert constructed.observed_label == imported.observed_label
        assert constructed.decision == imported.decision


def test_committed_contract_states_generated_corpus_boundary():
    contract = json.loads(
        (ROOT / "results/feature_benchmark_contract.json").read_text(encoding="utf-8")
    )
    boundaries = " ".join(contract["claim_boundaries"])
    assert "not recovered STEP history" in boundaries
    assert "not evidence of production" in boundaries
