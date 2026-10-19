"""Check the frozen v1.15 definition and existing inventory field conventions."""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import time

from research_notes.workflow_contract import canonical_bytes, read_contract, review_contract

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures/cad-workflow-contract"


def definition_controls(contract):
    changes = [
        ("unknown_to_zero", ("completion", "unknown_is_zero"), True),
        ("unanalysed_to_zero", ("completion", "unanalysed_is_zero"), True),
        ("partial_to_complete", ("completion", "partial_is_complete"), True),
        ("count_not_required", ("completion", "whole_count_required"), False),
        ("wrong_coordinate_origin", ("coordinates", "origin"), "recentred_without_mapping"),
        ("diameter_for_slots", ("fields", "diameter_mm", "required_when"), "all_features"),
        ("wrong_length_unit", ("coordinates", "length_unit"), "inch"),
        ("recognizer_as_truth", ("truth", "recognizer_output_is_truth"), True),
        ("leaking_family_split", ("truth", "split_unit"), "file"),
        ("review_time_omitted", ("required_metrics",), [m for m in contract["required_metrics"] if m != "review_minutes"]),
        ("pretend_customer_agreement", ("acceptance", "customer_agreed"), True),
    ]
    rows = []
    for name, keys, value in changes:
        altered = copy.deepcopy(contract)
        target = altered
        for key in keys[:-1]:
            target = target[key]
        target[keys[-1]] = value
        report = review_contract(altered)
        expected_path = "$." + ".".join(keys)
        rows.append({"id": name, "definition_valid": report["definition_valid"], "expected_issue_path": expected_path,
                     "issues": report["issues"], "passed": not report["definition_valid"] and any(i["path"] == expected_path for i in report["issues"])})
    return rows


def run(output: Path, repeats: int = 2) -> dict:
    if type(repeats) is not int or not 1 <= repeats <= 5:
        raise ValueError("repeats must be an integer from 1 to 5")
    from research_notes.hole_inventory import analyze_step

    output.mkdir(parents=True, exist_ok=True)
    contract_path = FIXTURES / "reference-contract.json"
    contract = read_contract(contract_path)
    definition = review_contract(contract)
    cases_path = FIXTURES / "reference-cases.json"
    cases = json.loads(cases_path.read_text())["cases"]
    observations = []
    for case in cases:
        payload = (ROOT / case["source_path"]).read_bytes() if case["source_path"] else case["source_text"].encode()
        if hashlib.sha256(payload).hexdigest() != case["source_sha256"]:
            raise ValueError("Reference input hash mismatch: " + case["id"])
        results, seconds = [], []
        for _ in range(repeats):
            start = time.perf_counter()
            results.append(analyze_step(payload, case["id"] + ".step", inspection=True, preview=False))
            seconds.append(time.perf_counter() - start)
        result = results[0]
        checks = {"repeat_results_identical": all(r == result for r in results)}
        if case["handling_control"] == "full_count_reference":
            checks["whole_count_matches_independent_recipe"] = result["status"] == "complete" and result["hole_count"] == case["whole_count_truth"]
            actual, truth = result["holes"], case["dimensions_truth"]
            checks["dimensions_match_independent_recipe"] = len(actual) == len(truth) and all(
                a["kind"] == t["kind"] and a["axis"] == t["axis"] and all(
                    abs(a[k] - t[k]) <= contract["acceptance"]["dimension_match_tolerance_mm"]
                    for k in ("diameter_mm", "x_mm", "y_mm", "entry_z_mm", "depth_mm"))
                for a, t in zip(actual, truth))
        elif case["handling_control"] == "partial_must_not_be_complete":
            checks["partial_keeps_unknown_total"] = result["status"] == "partial" and result["hole_count"] is None
        else:
            checks["unanalysed_is_not_zero"] = result["status"] == "rejected" and result["hole_count"] is None and result["holes"] == []
        checks["type_specific_dimensions"] = all(
            (h["diameter_mm"] is None and h["width_mm"] is not None and h["length_mm"] is not None)
            if h["feature_type"] == "straight_slot" else
            (h["diameter_mm"] is not None and h["width_mm"] is None and h["length_mm"] is None)
            for h in result["holes"])
        observations.append({"id": case["id"], "family_id": case["family_id"], "source_sha256": case["source_sha256"],
            "truth_origin": case["truth_origin"], "whole_count_truth": case["whole_count_truth"],
            "checks": checks, "passed": all(checks.values()), "extraction_seconds": seconds, "result": result})
    negative = definition_controls(contract)
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (
        contract_path, cases_path, Path(__file__), ROOT / "src/research_notes/workflow_contract.py",
        ROOT / "src/research_notes/hole_inventory.py", ROOT / "fixtures/hole-inventory/manifest.json",
        ROOT / "fixtures/hole-robustness/manifest.json", ROOT / "fixtures/public-step-corpus/manifest.json")}
    report = {"version": "1.15.0", "definition": definition, "definition_controls": negative,
        "inventory_observations": observations, "repeats": repeats, "hashes": hashes,
        "passed": definition["definition_valid"] and all(r["passed"] for r in negative + observations),
        "runtime": {"python": platform.python_version(), "platform": platform.platform(),
                    "cadquery_ocp": importlib.metadata.version("cadquery-ocp")},
        "operator_time_measured": False, "customer_approved": False, "adoption_decision": "not_evaluated",
        "claim_boundary": "Definition and seven existing-inventory controls only. Not operator timing, customer workbook output, suitability prediction or SME benefit evaluation."}
    (output / "results.json").write_bytes(canonical_bytes(report))
    (output / "reference-contract.json").write_bytes(canonical_bytes(contract))
    (output / "contract-review.json").write_bytes(canonical_bytes(definition))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results/cad-workflow-contract")
    parser.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args(argv)
    report = run(args.output_dir, args.repeats)
    print(json.dumps({"passed": report["passed"], "definition_controls": len(report["definition_controls"]),
                      "inventory_inputs": len(report["inventory_observations"]), "adoption_decision": report["adoption_decision"]}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
