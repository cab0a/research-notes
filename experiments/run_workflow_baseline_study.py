"""v1.16 timing/quality accounting controls and separate machine observations."""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import time

from research_notes.workflow_contract import canonical_bytes, read_contract
from research_notes.workflow_baseline import new_session, add_phase, add_quality, summarize

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "fixtures/cad-workflow-contract/reference-contract.json"
CASES = ROOT / "fixtures/cad-workflow-contract/reference-cases.json"
PLAN = ROOT / "fixtures/cad-workflow-baseline/control-plan.json"


def reference_session(*, synthetic=False):
    manifest = read_contract(CASES)
    if synthetic:
        plan = read_contract(PLAN)
        manifest["cases"] = [c for name in plan["case_ids"] for c in manifest["cases"] if c["id"] == name]
    session = new_session(read_contract(CONTRACT), manifest, method="manual_cad_and_transcription",
        operator="synthetic-control" if synthetic else "pending-participant",
        kind="synthetic_control" if synthetic else "operator_observation",
        tool="synthetic CAD context" if synthetic else None,
        workbook="synthetic table context" if synthetic else None)
    session["session_id"] = "synthetic-arithmetic-control" if synthetic else "unmeasured-reference-template"
    session["created_at"] = "2026-10-19T00:00:00+00:00"
    return session


def synthetic_session():
    plan = read_contract(PLAN)
    session = reference_session(synthetic=True)
    for case_id, values in [(None, plan["batch_seconds"]), *plan["case_seconds"].items()]:
        for phase, value in values.items():
            session = add_phase(session, case_id=case_id, phase=phase, seconds=None if value == "not_needed" else value,
                basis="not_needed" if value == "not_needed" else "synthetic", evidence="Synthetic control, not operator time")
            session["phase_records"][-1]["id"] = f'control-{len(session["phase_records"]):03d}'
    for case in session["case_manifest"]["cases"]:
        session = add_quality(session, case_id=case["id"], truth_scope="whole_part", truth_origin="independent_recipe",
            truth_reference=case["truth_reference"], truth_hole_count=case["whole_count_truth"], **plan["case_quality"][case["id"]])
    return session


def negative_controls(session):
    controls = []
    def invalid(name, mutate):
        altered = copy.deepcopy(session)
        mutate(altered)
        try:
            summarize(altered)
        except ValueError as error:
            controls.append({"id": name, "rejected": True, "reason": str(error)})
        else:
            controls.append({"id": name, "rejected": False})
    invalid("double_counted_phase", lambda s: s["phase_records"].append(dict(s["phase_records"][0], id="duplicate")))
    invalid("negative_time", lambda s: s["phase_records"][0].update(seconds=-1))
    invalid("boolean_time", lambda s: s["phase_records"][0].update(seconds=True))
    invalid("synthetic_as_operator", lambda s: s.update(record_kind="operator_observation"))
    invalid("omitted_correction_as_zero", lambda s: s["phase_records"][-1].update(seconds=None))
    invalid("unknown_truth_as_zero_errors", lambda s: s["quality_records"][0].update(truth_scope="unknown", truth_origin="unknown"))
    invalid("partial_truth_as_whole_errors", lambda s: s["quality_records"][0].update(truth_scope="selected_fields"))
    invalid("recognizer_as_truth", lambda s: s["quality_records"][0].update(truth_origin="recognizer_output"))
    invalid("no_checked_fields_as_zero_errors", lambda s: s["quality_records"][0].update(checked_fields=0))
    invalid("different_recipe_count", lambda s: s["quality_records"][0].update(truth_hole_count=10))
    invalid("definition_digest_changed", lambda s: s.update(contract_sha256="0" * 64))
    invalid("manifest_digest_changed", lambda s: s.update(case_manifest_sha256="0" * 64))
    return controls


def run(output: Path, repeats=2):
    from research_notes.hole_inventory import analyze_step
    if type(repeats) is not int or not 1 <= repeats <= 5:
        raise ValueError("repeats must be an integer from 1 to 5")
    output.mkdir(parents=True, exist_ok=True)
    unmeasured = reference_session()
    control = synthetic_session()
    unmeasured_report, control_report = summarize(unmeasured), summarize(control)
    plan = read_contract(PLAN)
    checks = {"unmeasured_time_is_null": unmeasured_report["total_active_seconds"] is None,
        "unmeasured_quality_is_null": all(r["total"] is None for r in unmeasured_report["error_counts"].values()),
        "synthetic_time_matches_independent_arithmetic": control_report["total_active_seconds"] == plan["expected"]["total_active_seconds"],
        "synthetic_not_needed_is_explicit": control_report["not_needed_phases"] == plan["expected"]["not_needed_phases"],
        "synthetic_errors_are_not_lost": all(control_report["error_counts"][k]["total"] == plan["expected"][k] for k in ("incorrect_fields", "missed_features", "false_complete")),
        "synthetic_is_not_operator_evidence": not control_report["operator_time_measured"] and not control_report["baseline_record_complete"]}
    negatives = negative_controls(control)
    observations = []
    for case in read_contract(CASES)["cases"]:
        payload = (ROOT / case["source_path"]).read_bytes() if case["source_path"] else case["source_text"].encode()
        if hashlib.sha256(payload).hexdigest() != case["source_sha256"]:
            raise ValueError("Source hash mismatch: " + case["id"])
        runs, seconds = [], []
        for _ in range(repeats):
            start = time.perf_counter()
            runs.append(analyze_step(payload, case["id"] + ".step", inspection=True, preview=False))
            seconds.append(time.perf_counter() - start)
        first = runs[0]
        observations.append({"id": case["id"], "family_id": case["family_id"], "source_sha256": case["source_sha256"],
            "bytes": len(payload), "source_kind": "step" if case["source_path"] else "invalid_transport",
            "truth_origin": case["truth_origin"], "whole_count_truth": case["whole_count_truth"],
            "status": first["status"], "whole_count": first["hole_count"], "recognized_rows": len(first["holes"]),
            "extraction_seconds": seconds, "result_sha256": hashlib.sha256(canonical_bytes(first)).hexdigest(),
            "repeat_results_identical": all(r == first for r in runs)})
    paths = [CONTRACT, CASES, PLAN, Path(__file__), ROOT / "src/research_notes/workflow_baseline.py",
             ROOT / "src/research_notes/hole_inventory.py", ROOT / "fixtures/hole-inventory/manifest.json",
             ROOT / "fixtures/hole-robustness/manifest.json", ROOT / "fixtures/public-step-corpus/manifest.json"]
    result = {"version": "1.16.0", "date": "2026-10-19", "accounting_checks": checks,
        "negative_controls": negatives, "machine_observations": observations, "repeats": repeats,
        "data_summary": {"inputs": len(observations), "step_inputs": sum(r["source_kind"] == "step" for r in observations),
            "invalid_transport_controls": sum(r["source_kind"] == "invalid_transport" for r in observations),
            "families": len({r["family_id"] for r in observations}),
            "step_inputs_with_known_whole_truth": sum(r["source_kind"] == "step" and r["whole_count_truth"] is not None for r in observations),
            "step_inputs_with_unknown_whole_truth": sum(r["source_kind"] == "step" and r["whole_count_truth"] is None for r in observations),
            "statuses": {status: sum(r["status"] == status for r in observations) for status in ("complete", "partial", "rejected")}},
        "hashes": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        "runtime": {"python": platform.python_version(), "platform": platform.platform(), "cadquery_ocp": importlib.metadata.version("cadquery-ocp")},
        "operator_time_measured": False, "manual_error_rate_measured": False, "customer_workbook_available": False,
        "adoption_decision": "not_evaluated", "time_saving_seconds": None,
        "passed": all(checks.values()) and all(r["rejected"] for r in negatives) and all(r["repeat_results_identical"] for r in observations),
        "claim_boundary": "Accounting software controls and machine extraction only. Synthetic timing/quality is not operator evidence; no business baseline or time-saving claim."}
    for name, value in (("unmeasured-session", unmeasured), ("unmeasured-report", unmeasured_report),
                        ("synthetic-session", control), ("synthetic-report", control_report), ("results", result)):
        (output / (name + ".json")).write_bytes(canonical_bytes(value))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results/cad-workflow-baseline")
    parser.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args(argv)
    result = run(args.output_dir, args.repeats)
    print(json.dumps({"passed": result["passed"], "negative_controls": len(result["negative_controls"]),
        "data_summary": result["data_summary"], "operator_time_measured": False}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
