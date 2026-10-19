"""Verify existing-route mapping, provenance and baseline-case binding."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform

from research_notes.workflow_contract import canonical_bytes, read_contract, FIELD_RULES
from research_notes.workflow_baseline import new_session
from research_notes.workflow_extraction import extract_step

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "fixtures/cad-workflow-contract/reference-contract.json"
MANIFEST = ROOT / "fixtures/cad-workflow-extraction/manifest.json"


def pointer(report, path):
    value = report
    for key in path.split("/")[1:]:
        value = value[int(key)] if isinstance(value, list) else value[key.replace("~1", "/").replace("~0", "~")]
    return value


def provenance_matches(report):
    cells = [*report["summary"].values(), *(f for row in report["features"] for f in row["fields"].values())]
    for cell in cells:
        values = [pointer(report, p) for p in cell["provenance"]["paths"]]
        operation, value = cell["provenance"]["operation"], cell["value"]
        if operation == "copy":
            correct = len(values) == 1 and values[0] == value
        elif operation == "xyz_vector":
            correct = values == value
        elif operation == "sole_solid_index":
            correct = values == [1] and value == 1
        else:
            correct = operation == "owner_not_recorded" and value is None
        if not correct:
            return False
    return True


def run(output: Path, repeats=2):
    if type(repeats) is not int or not 1 <= repeats <= 5:
        raise ValueError("repeats must be an integer from 1 to 5")
    output.mkdir(parents=True, exist_ok=True)
    (output / "observations").mkdir(exist_ok=True)
    contract, manifest = read_contract(CONTRACT), read_contract(MANIFEST)
    session = new_session(contract, manifest, method="existing_extraction_with_full_review", operator="pending-participant",
                          tool="research_notes.hole_inventory.analyze_step 1.14.0")
    session.update(session_id="unmeasured-extraction-reference", created_at="2026-10-19T00:00:00+00:00")
    session_bytes = canonical_bytes(session)
    previous = read_contract(ROOT / "results/cad-workflow-contract/results.json")
    previous = {row["id"]: row["result"] for row in previous["inventory_observations"]}
    observations = []
    for case in manifest["cases"]:
        payload = (ROOT / case["source_path"]).read_bytes() if case["source_path"] else case["source_text"].encode()
        if hashlib.sha256(payload).hexdigest() != case["source_sha256"]:
            raise ValueError("Source hash mismatch: " + case["id"])
        reports = [extract_step(payload, contract, file_name=case["id"] + ".step", part_reference="research-control:" + case["id"],
                     baseline_session=session, case_id=case["id"]) for _ in range(repeats)]
        first = reports[0]
        stable = lambda r: {k: v for k, v in r.items() if k != "timing"}
        cells = [*first["summary"].values(), *(f for row in first["features"] for f in row["fields"].values())]
        checks = {"repeat_observations_equal_without_timing": all(stable(r) == stable(first) for r in reports),
            "all_provenance_resolves_and_matches": all(provenance_matches(r) for r in reports),
            "source_and_case_binding_match": first["source"]["sha256"] == case["source_sha256"] and first["baseline_binding"]["case_id"] == case["id"],
            "baseline_session_unchanged": canonical_bytes(session) == session_bytes,
            "all_17_fields_mapped_when_features_exist": all(set(first["summary"]) | set(row["fields"]) == set(FIELD_RULES) for row in first["features"]),
            "no_business_or_operator_claim": first["business_completion"] == "not_evaluated" and not first["timing"]["operator_time_measured"]}
        if case["id"] in previous:
            checks["previous_inventory_unchanged"] = first["inventory"] == previous[case["id"]]
        data = canonical_bytes(first)
        name = "observations/" + case["id"] + ".json"
        (output / name).write_bytes(data)
        observations.append({"id": case["id"], "family_id": case["family_id"], "source_sha256": case["source_sha256"],
            "inventory_status": first["inventory"]["status"], "whole_count": first["summary"]["whole_hole_count"]["value"],
            "recognized_rows": len(first["features"]), "provenance_cells": len(cells),
            "inventory_sha256": first["inventory_sha256"], "artifact": name, "artifact_sha256": hashlib.sha256(data).hexdigest(),
            "extraction_seconds": [r["timing"]["extraction_seconds"] for r in reports], "checks": checks, "passed": all(checks.values())})
    paths = [CONTRACT, MANIFEST, Path(__file__), ROOT / "src/research_notes/workflow_extraction.py",
             ROOT / "src/research_notes/workflow_baseline.py", ROOT / "src/research_notes/workflow_contract.py",
             ROOT / "src/research_notes/hole_inventory.py", ROOT / "fixtures/public-step-corpus/manifest.json"]
    result = {"version": "1.17.0", "date": "2026-10-19", "repeats": repeats, "observations": observations,
        "summary": {"inputs": len(observations), "provenance_cells": sum(r["provenance_cells"] for r in observations),
            "previous_inventory_controls": sum("previous_inventory_unchanged" in r["checks"] for r in observations),
            "statuses": {s: sum(r["inventory_status"] == s for r in observations) for s in ("complete", "partial", "unresolved", "rejected")}},
        "hashes": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        "runtime": {"python": platform.python_version(), "platform": platform.platform(), "cadquery_ocp": importlib.metadata.version("cadquery-ocp")},
        "operator_time_measured": False, "field_baseline_complete": False, "customer_workbook_available": False,
        "business_completion": "not_evaluated", "adoption_decision": "not_evaluated",
        "passed": all(r["passed"] for r in observations),
        "claim_boundary": "Known-input connector, provenance and case-binding controls only; not new recognition accuracy, job suitability, operator savings or customer acceptance."}
    (output / "reference-baseline-session.json").write_bytes(session_bytes)
    (output / "results.json").write_bytes(canonical_bytes(result))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results/cad-workflow-extraction")
    parser.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args(argv)
    result = run(args.output_dir, args.repeats)
    print(json.dumps({"passed": result["passed"], "summary": result["summary"], "operator_time_measured": False}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
