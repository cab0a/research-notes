"""Timing/quality accounting must distinguish missing, explicit NA and zero."""
import copy
import json
from pathlib import Path

import pytest

from research_notes.workflow_baseline import (
    add_phase, add_quality, main, measure_interactive, new_session, summarize, _save,
)
from research_notes.workflow_contract import canonical_bytes, read_contract
from experiments.run_workflow_baseline_study import reference_session, synthetic_session, negative_controls

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "fixtures/cad-workflow-contract/reference-contract.json"
CASES = ROOT / "fixtures/cad-workflow-contract/reference-cases.json"


def test_new_observation_has_no_invented_time_or_error_rate():
    report = summarize(reference_session())
    assert report["planned_cases"] == 7 and report["missing_or_unfinished_phases"] == 54
    assert report["total_active_seconds"] is None and report["known_active_seconds"] == 0
    assert all(r["total"] is None and r["unknown_cases"] == 7 for r in report["error_counts"].values())
    assert report["measurement_state"] == "not_measured" and report["operator_time_measured"] is False
    assert report["context_complete"] is False and report["adoption_decision"] == "not_evaluated"


def test_synthetic_arithmetic_does_not_become_operator_evidence():
    report = summarize(synthetic_session())
    assert report["total_active_seconds"] == 180 + 60 + 100
    assert report["not_needed_phases"] == 3 and report["timing_complete"] and report["quality_complete"]
    assert report["error_counts"]["incorrect_fields"]["total"] == 1
    assert report["error_counts"]["missed_features"]["total"] == 1
    assert report["error_counts"]["false_complete"]["total"] == 1
    assert not report["operator_time_measured"] and not report["baseline_record_complete"]
    assert report["measurement_state"] == "synthetic_control" and report["time_saving_seconds"] is None


def test_complete_record_does_not_mean_success_or_adoption():
    session = synthetic_session()
    session["record_kind"] = "operator_observation"
    for record in session["phase_records"]:
        if record["basis"] == "synthetic":
            record["basis"] = "reported_stopwatch"
    report = summarize(session)
    assert report["baseline_record_complete"] and report["operator_time_measured"]
    assert report["error_counts"]["false_complete"]["total"] == 1
    assert report["adoption_decision"] == "not_evaluated" and report["customer_approved"] is False


def test_interrupted_phase_contributes_time_but_is_not_complete():
    session = add_phase(reference_session(), case_id="single", phase="cad_check", seconds=12,
                        completed=False, evidence="test stopwatch")
    report = summarize(session)
    assert report["known_active_seconds"] == 12 and report["total_active_seconds"] is None
    row = next(r for r in report["phases"] if r["case_id"] == "single" and r["phase"] == "cad_check")
    assert row["seconds"] is None and row["known_seconds"] == 12
    session = add_phase(session, case_id="single", phase="cad_check", seconds=8, evidence="resumed test stopwatch")
    row = next(r for r in summarize(session)["phases"] if r["case_id"] == "single" and r["phase"] == "cad_check")
    assert row["seconds"] == 20 and row["accounted"]


def test_explicit_not_needed_differs_from_unrecorded_or_measured_zero():
    session = add_phase(reference_session(), phase="training", basis="not_needed", evidence="No training in control")
    session = add_phase(session, phase="setup", seconds=0, evidence="Recorded zero in control")
    report = summarize(session)
    assert report["not_needed_phases"] == 1 and report["missing_or_unfinished_phases"] == 52
    phases = {r["phase"]: r for r in report["phases"] if r["case_id"] is None}
    assert phases["training"]["seconds"] == 0 and phases["training"]["not_needed"]
    assert phases["setup"]["seconds"] == 0 and not phases["setup"]["not_needed"]
    assert phases["update"]["seconds"] is None


@pytest.mark.parametrize("value", [-1, True, float("nan"), float("inf"), 604801, 10**1000, "12", None])
def test_invalid_durations_are_rejected_without_mutation(value):
    session = reference_session()
    original = copy.deepcopy(session)
    with pytest.raises(ValueError):
        add_phase(session, phase="setup", seconds=value, evidence="test")
    assert session == original


@pytest.mark.parametrize("case_id,phase", [(None, "cad_open"), ("single", "setup"), ("absent", "cad_check"), ([], "cad_check")])
def test_batch_and_part_phases_do_not_mix(case_id, phase):
    with pytest.raises(ValueError):
        add_phase(reference_session(), case_id=case_id, phase=phase, seconds=1, evidence="test")


def test_not_needed_cannot_erase_interrupted_time_and_completed_phase_cannot_repeat():
    session = add_phase(reference_session(), phase="setup", seconds=12, completed=False, evidence="test")
    with pytest.raises(ValueError):
        add_phase(session, phase="setup", basis="not_needed", evidence="discard")
    session = add_phase(session, phase="setup", seconds=1, evidence="finish")
    with pytest.raises(ValueError):
        add_phase(session, phase="setup", seconds=1, evidence="duplicate")


def test_partial_quality_keeps_whole_errors_unknown():
    session = add_quality(reference_session(), case_id="public_bracket", truth_scope="selected_fields",
        truth_origin="independent_human_review", truth_reference="control-only independent review",
        checked_fields=3, incorrect_fields=1)
    report = summarize(session)
    assert report["planned_cases"] == 7 and report["quality_unknown_cases"] == 7
    assert report["error_counts"]["incorrect_fields"] == {"known_total": 1, "unknown_cases": 6, "total": None}
    assert report["error_counts"]["missed_features"]["unknown_cases"] == 7
    with pytest.raises(ValueError):
        add_quality(reference_session(), case_id="public_bracket", truth_scope="selected_fields",
            truth_origin="independent_human_review", truth_reference="test", checked_fields=3,
            incorrect_fields=0, missed_features=0)


def test_unknown_public_whole_truth_needs_new_independent_review():
    args = dict(case_id="public_bracket", truth_scope="whole_part", truth_reference="test",
                truth_hole_count=11, checked_fields=3, incorrect_fields=0, missed_features=0, false_complete=False)
    with pytest.raises(ValueError):
        add_quality(reference_session(), truth_origin="independent_recipe", **args)
    reviewed = add_quality(reference_session(), truth_origin="independent_human_review", **args)
    assert reviewed["case_manifest"]["cases"][5]["whole_count_truth"] is None
    assert reviewed["quality_records"][0]["truth_hole_count"] == 11
    # This is only a toy quality-record validation, not a new bracket ground truth.


def test_whole_truth_without_error_assessment_still_has_unknown_quality():
    session = add_quality(reference_session(), case_id="single", truth_scope="whole_part",
        truth_origin="independent_recipe", truth_reference="fixture recipe", truth_hole_count=1)
    report = summarize(session)
    assert report["whole_truth_unknown_cases"] == 6 and report["quality_unknown_cases"] == 7
    assert not report["quality_complete"] and report["error_counts"]["missed_features"]["total"] is None


def test_case_manifest_cannot_bootstrap_whole_truth_from_recognizer_output():
    manifest = read_contract(CASES)
    manifest["cases"][0]["truth_origin"] = "recognizer_output"
    with pytest.raises(ValueError):
        new_session(read_contract(CONTRACT), manifest, method="manual_cad_and_transcription", operator="test")


def test_all_negative_study_controls_are_rejected():
    controls = negative_controls(synthetic_session())
    assert len(controls) == 12 and all(row["rejected"] for row in controls)


@pytest.mark.parametrize("commands,ticks,expected", [
    ([""], [10, 15], (5, True)),
    (["p", "r", ""], [10, 15, 45, 52], (12, True)),
    (["p", "", "r", ""], [0, 2, 20, 30, 33], (5, True)),
    (["q"], [10, 15], (5, False)),
])
def test_timer_excludes_pauses_but_retains_interrupted_active_work(commands, ticks, expected, capsys):
    commands, ticks = iter(commands), iter(ticks)
    assert measure_interactive(reader=lambda: next(commands), clock=lambda: next(ticks)) == expected
    capsys.readouterr()


def test_timer_eof_is_incomplete_and_clock_reversal_is_rejected(capsys):
    def eof():
        raise EOFError()
    ticks = iter([10, 15])
    assert measure_interactive(reader=eof, clock=lambda: next(ticks)) == (5, False)
    ticks = iter([10, 9])
    with pytest.raises(ValueError):
        measure_interactive(reader=lambda: "", clock=lambda: next(ticks))
    capsys.readouterr()


def test_session_binding_and_schema_are_checked():
    session = reference_session()
    for key, value in (("method", []), ("contract_sha256", "0" * 64), ("case_manifest_sha256", "0" * 64)):
        altered = dict(session, **{key: value})
        with pytest.raises(ValueError):
            summarize(altered)
    manifest = read_contract(CASES)
    manifest["cases"].append(manifest["cases"][0])
    with pytest.raises(ValueError):
        new_session(read_contract(CONTRACT), manifest, method="manual_cad_and_transcription", operator="test")


def test_existing_extraction_method_has_review_phase_without_assuming_savings():
    session = new_session(read_contract(CONTRACT), read_contract(CASES),
        method="existing_extraction_with_full_review", operator="test")
    phases = {r["phase"] for r in summarize(session)["phases"] if r["case_id"] == "single"}
    assert "review" in phases and "extract" in phases and "cad_check" not in phases
    assert summarize(session)["time_saving_seconds"] is None


def test_locked_or_changed_record_cannot_be_overwritten(tmp_path):
    path = tmp_path / "session.json"
    session = reference_session()
    _save(path, session)
    original = path.read_bytes()
    with pytest.raises(ValueError):
        _save(path, session)
    with pytest.raises(ValueError):
        _save(path, session, original=b"stale")
    assert path.read_bytes() == original and not path.with_name("session.json.lock").exists()
    lock = path.with_name("session.json.lock")
    lock.write_text("other writer")
    with pytest.raises(FileExistsError):
        _save(path, session, original=original)
    assert lock.read_text() == "other writer" and path.read_bytes() == original


def test_cli_records_na_and_quality_then_exports_same_report(tmp_path, capsys):
    path = tmp_path / "記録.json"
    assert main(["init", str(path), "--contract", str(CONTRACT), "--cases", str(CASES),
                 "--operator", "test", "--kind", "synthetic_control"]) == 0
    original = path.read_bytes()
    capsys.readouterr()
    assert main(["init", str(path), "--contract", str(CONTRACT), "--cases", str(CASES), "--operator", "test"]) == 2
    assert path.read_bytes() == original
    capsys.readouterr()
    assert main(["record", str(path), "--phase", "setup", "--seconds", "30", "--evidence", "synthetic test"]) == 0
    capsys.readouterr()
    assert main(["record", str(path), "--case", "single", "--phase", "correction", "--not-needed", "--evidence", "no correction in control"]) == 0
    capsys.readouterr()
    assert main(["quality", str(path), "--case", "single", "--truth-scope", "whole_part", "--truth-origin", "independent_recipe",
                 "--truth-reference", "fixtures/hole-inventory/manifest.json#single", "--truth-hole-count", "1",
                 "--checked-fields", "17", "--incorrect-fields", "0", "--missed-features", "0", "--false-complete", "no"]) == 0
    capsys.readouterr()
    assert main(["report", str(path), "--output-dir", str(tmp_path / "out")]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report == summarize(read_contract(path))
    assert (tmp_path / "out/baseline-report.json").read_bytes() == canonical_bytes(report)
    assert "未測定・未完了" in (tmp_path / "out/baseline-report.md").read_text()


def test_cli_time_keeps_unfinished_segment(tmp_path, monkeypatch, capsys):
    path = tmp_path / "session.json"
    _save(path, reference_session(synthetic=True))
    monkeypatch.setattr("research_notes.workflow_baseline.measure_interactive", lambda: (12, False))
    assert main(["time", str(path), "--phase", "setup", "--evidence", "test timer"]) == 130
    report = summarize(read_contract(path))
    assert report["known_active_seconds"] == 12 and report["total_active_seconds"] is None
    assert read_contract(path)["phase_records"][0]["basis"] == "synthetic"
    capsys.readouterr()


@pytest.mark.parametrize("payload", [b'{"method": "a", "method": "b"}', b'{"value": NaN}', b'[]', b'not JSON', b' ' * 128001])
def test_malformed_ledger_is_rejected_without_touching_file(tmp_path, capsys, payload):
    path = tmp_path / "bad.json"
    path.write_bytes(payload)
    assert main(["report", str(path)]) == 2
    assert json.loads(capsys.readouterr().out)["record_valid"] is False
    assert path.read_bytes() == payload


def test_machine_study_does_not_claim_operator_measurement(tmp_path):
    pytest.importorskip("OCP")
    from experiments.run_workflow_baseline_study import run
    result = run(tmp_path, repeats=1)
    assert result["passed"] and result["data_summary"]["inputs"] == 7
    assert result["data_summary"]["step_inputs_with_known_whole_truth"] == 5
    assert result["data_summary"]["step_inputs_with_unknown_whole_truth"] == 1
    assert not result["operator_time_measured"] and not result["manual_error_rate_measured"]
    assert result["time_saving_seconds"] is None
