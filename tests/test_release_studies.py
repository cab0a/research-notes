"""Independent release failure controls and reproduction of the bounded workflow."""
import json
from dataclasses import replace
from pathlib import Path

import pytest

from research_notes.cad_fuzz import STEP, fuzz_cases, minimize_bytes, observe_case
from research_notes.cad_resources import ResourceLimits, run_workload
from research_notes.release_studies import ROOT, STUDIES, run_study, freeze_contract
from research_notes.artifact_contracts import compare_file


@pytest.mark.parametrize("name", [n for n in STUDIES if 92 <= STUDIES[n] <= 98])
def test_release_study_reproduces(tmp_path, name):
    rows = run_study(name, tmp_path/"results", tmp_path/"fixtures", refresh=True)
    assert rows and all(r["checks_pass"] for r in rows)
    for path in (tmp_path/"fixtures").iterdir():
        compare_file(path, ROOT/"fixtures"/name.replace("_", "-")/path.name)
    for path in (tmp_path/"results").glob("*_contract.json"):
        compare_file(path, ROOT/"results"/path.name)


@pytest.mark.parametrize("raw", [b"\x00"+STEP, STEP.replace(b"'fuzz'", b"'fu\x00zz'")])
def test_nul_transport_control_is_consistently_outside_profile(raw):
    from research_notes.step_part21 import parse_part21_document, Part21ParseError
    with pytest.raises(Part21ParseError) as caught:
        parse_part21_document(raw)
    assert caught.value.reason_code == "unsupported_transport_control"


def test_fuzz_seed_and_minimized_regression():
    assert fuzz_cases() == fuzz_cases()
    assert fuzz_cases(44) != fuzz_cases()
    minimal, calls = minimize_bytes(b"aaaaNULbbbb", lambda data: b"NUL" in data)
    assert minimal == b"NUL" and calls <= 64
    with pytest.raises(ValueError):
        minimize_bytes(b"abc", lambda data: False)


@pytest.mark.parametrize("counter", ["bytes", "entities", "seconds", "triangles"])
def test_invalid_resource_limits(counter):
    for value in (0, -1, True, float("inf"), float("nan")):
        with pytest.raises(ValueError):
            replace(ResourceLimits(), **{counter: value})


def test_real_worker_timeout_and_invalid_request_are_distinct():
    assert run_workload({"kind": "deadline_control"}, replace(ResourceLimits(), seconds=.02))["status"] == "resource_exhausted"
    assert run_workload({"kind": "syntax", "count": 0})["status"] == "error"


def test_blind_boundary_rejects_label_or_recipe_leakage():
    from research_notes.blinded_assistance import blind_predict
    with pytest.raises(ValueError, match="non-feature"):
        blind_predict(None, [{"sample_id": "x", "values": [], "source_sha256": "x", "support": {}, "truth": "hole"}])


def test_frozen_holdout_contains_errors_and_abstentions():
    report = json.loads((ROOT/"results/blinded_assistance_evaluation_evidence.json").read_bytes())
    assert report["checkpoint_unchanged"] and not report["threshold_tuned_on_holdout"]
    assert report["preregistration"]["protocol_commit"] == "4731ab07e08e099cbedf6c5deda5e83c6b9d83ae"
    assert report["metrics"]["accuracy"] == .7
    assert len(report["adopted_high_confidence_errors"]) == 2
    assert any(p["decision"] == "abstain" for p in report["predictions"])


def test_evidence_comparison_does_not_ignore_classification_or_geometry_changes():
    from research_notes.artifact_contracts import evidence_differences
    assert evidence_differences({"volume": 24.1}, {"volume": 24.})
    assert evidence_differences({"checks_pass": False}, {"checks_pass": True})
    assert not evidence_differences({"volume": 24.+1e-9}, {"volume": 24.})


def test_final_api_contract_remains_v087_compatible():
    old = json.loads((ROOT/"fixtures/stable-cad-api/api_contract.json").read_bytes())
    assert freeze_contract()["api"] == old
