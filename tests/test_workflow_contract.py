"""Workflow definition boundaries must not masquerade as geometry or adoption."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from research_notes.workflow_contract import (
    MAX_CONTRACT_BYTES, canonical_bytes, main, read_contract, review_contract,
)

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "fixtures/cad-workflow-contract/reference-contract.json"


@pytest.fixture
def contract():
    return read_contract(REFERENCE)


def test_valid_definition_is_neither_customer_approval_nor_adoption(contract):
    report = review_contract(contract)
    assert report["definition_valid"] and report["definition_state"] == "research_definition_fixed"
    assert report["customer_approved"] is False and report["performance_measured"] is False
    assert report["adoption_decision"] == "not_evaluated"
    assert report["contract_sha256"] == hashlib.sha256(canonical_bytes(contract)).hexdigest()
    assert all(v == "pending_customer_agreement" for v in contract["customer_inputs"].values())


@pytest.mark.parametrize("section,key,value", [
    ("completion", "unknown_is_zero", True), ("completion", "unanalysed_is_zero", True),
    ("completion", "partial_is_complete", True), ("completion", "whole_count_required", False),
    ("truth", "recognizer_output_is_truth", True), ("truth", "split_unit", "file"),
    ("comparison", "quality_matched", False), ("acceptance", "customer_agreed", True),
])
def test_semantic_shortcuts_are_invalid_even_when_json_is_well_formed(contract, section, key, value):
    contract[section][key] = value
    report = review_contract(contract)
    assert not report["definition_valid"] and report["contract_sha256"] is None
    assert any(i["path"] == f"$.{section}.{key}" for i in report["issues"])
    assert report["adoption_decision"] == "not_evaluated"


def test_circle_diameter_cannot_become_a_required_slot_value(contract):
    contract["fields"]["diameter_mm"]["required_when"] = "all_features"
    assert not review_contract(contract)["definition_valid"]
    assert contract["fields"]["width_mm"]["required_when"] == "straight_slot"


def test_coordinate_and_operator_time_definitions_cannot_disappear(contract):
    del contract["coordinates"]["origin"]
    contract["required_metrics"].remove("review_minutes")
    paths = {i["path"] for i in review_contract(contract)["issues"]}
    assert "$.coordinates.origin" in paths and "$.required_metrics" in paths


@pytest.mark.parametrize("value", [True, -1, 0, float("nan"), float("inf"), 10**1000])
def test_numerical_match_criteria_are_finite_positive_and_not_booleans(contract, value):
    contract["acceptance"]["dimension_match_tolerance_mm"] = value
    assert not review_contract(contract)["definition_valid"]


def test_repeat_projection_is_a_positive_integer_not_measured_volume(contract):
    for value in (True, 0, 1.5):
        contract["acceptance"]["planning_runs"] = value
        assert not review_contract(contract)["definition_valid"]


def test_unknown_keys_and_missing_definitions_are_reported(contract):
    contract["fields"]["diametre_mm"] = contract["fields"].pop("diameter_mm")
    issues = review_contract(contract)["issues"]
    assert any(i["code"] == "unknown_definition" and i["path"].endswith("diametre_mm") for i in issues)
    assert any(i["code"] == "missing_definition" and i["path"].endswith("diameter_mm") for i in issues)


def test_definition_review_does_not_modify_its_input_and_is_order_stable(contract):
    before = copy.deepcopy(contract)
    report = review_contract(contract)
    assert contract == before
    assert report == review_contract(dict(reversed(list(contract.items()))))


@pytest.mark.parametrize("text", ['{"a":1,"a":2}', '{"x":NaN}', '{"x":Infinity}', '{broken', '[]'])
def test_cli_rejects_bad_or_non_contract_json_without_an_adoption_claim(tmp_path, capsys, text):
    path = tmp_path / "input.json"
    path.write_text(text)
    assert main([str(path), "--output-dir", str(tmp_path / "out")]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report == json.loads((tmp_path / "out/contract-review.json").read_text())
    assert not report["definition_valid"] and report["adoption_decision"] == "not_evaluated"


def test_read_limit_and_missing_file_produce_a_definition_error(tmp_path, capsys):
    path = tmp_path / "too-large.json"
    path.write_bytes(b" " * (MAX_CONTRACT_BYTES + 1))
    assert main([str(path)]) == 2
    assert json.loads(capsys.readouterr().out)["issues"][0]["code"] == "definition_read_failed"
    assert main([str(tmp_path / "missing.json")]) == 2
    assert json.loads(capsys.readouterr().out)["definition_valid"] is False


def test_cli_saves_the_same_definition_report_as_python(tmp_path, capsys, contract):
    assert main([str(REFERENCE), "--output-dir", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out) == review_contract(contract)
    assert (tmp_path / "contract-review.json").read_bytes() == canonical_bytes(review_contract(contract))


def test_existing_inventory_observations_keep_unknown_and_zero_distinct(tmp_path):
    pytest.importorskip("OCP")
    from experiments.run_workflow_contract_study import run
    report = run(tmp_path, repeats=1)
    assert report["passed"] and len(report["definition_controls"]) == 11
    rows = {r["id"]: r for r in report["inventory_observations"]}
    assert rows["no_holes"]["result"]["hole_count"] == 0
    assert rows["single"]["result"]["hole_count"] == 1
    assert rows["translated"]["result"]["holes"][0]["x_mm"] == pytest.approx(36)
    assert rows["mixed_circle_slot"]["result"]["hole_count"] is None
    assert rows["public_bracket"]["whole_count_truth"] is None
    assert rows["public_bracket"]["result"]["recognized_hole_count"] == 11
    assert rows["invalid_transport"]["result"]["status"] == "rejected"
    assert not report["operator_time_measured"] and report["adoption_decision"] == "not_evaluated"
