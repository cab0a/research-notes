"""Tests for the v0.53.0 synthetic 3D dataset contract."""

import json
from pathlib import Path

import pytest

from research_notes.synthetic_3d_dataset import probe_synthetic_dataset


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def probe(tmp_path_factory):
    return probe_synthetic_dataset(
        ROOT / "fixtures/feature-recognition-benchmark",
        tmp_path_factory.mktemp("synthetic-dataset"),
        refresh_added=True,
    )


def test_dataset_contains_family_isolated_step_samples(probe):
    assert len(probe.samples) == 36
    assert len({item.family_id for item in probe.samples}) == 9
    assert {item.split for item in probe.samples} == {"train", "validation", "test"}
    assert all(len(item.source_sha256) == 64 for item in probe.samples)


def test_all_lineages_stay_inside_one_split(probe):
    for family in {item.family_id for item in probe.samples}:
        assert len({item.split for item in probe.samples if item.family_id == family}) == 1
    assert all(item.passed for item in probe.leakage_checks)


def test_each_sample_has_brep_graph_and_label_provenance(probe):
    assert len(probe.graphs) == len(probe.samples)
    graph_ids = {item["sample_id"] for item in probe.graphs}
    assert graph_ids == {item.sample_id for item in probe.samples}
    assert all(item.label_provenance for item in probe.samples)
    assert all(item.face_count > 0 for item in probe.samples)
    assert all(
        item.relation_count > 0
        for item in probe.samples
        if item.family_id != "toroidal_surface"
    )
    assert all(
        item.relation_count == 0
        for item in probe.samples
        if item.family_id == "toroidal_surface"
    )


def test_negative_families_cover_planar_external_and_unsupported_curvature(probe):
    negatives = {item.family_id for item in probe.samples if not item.supported_feature}
    assert negatives == {"plain_block", "cylindrical_boss", "toroidal_surface"}
    torus = [item for item in probe.samples if item.family_id == "toroidal_surface"]
    assert len(torus) == 4
    assert all(item.other_curved_face_count >= 1 for item in torus)


def test_committed_contract_forbids_recovered_history_claim():
    contract = json.loads((ROOT / "results/synthetic_3d_dataset_contract.json").read_text(encoding="utf-8"))
    assert contract["all_leakage_checks_pass"]
    assert "not recovered STEP history" in " ".join(contract["claim_boundaries"])
