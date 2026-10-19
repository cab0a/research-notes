"""A connector must preserve observations, source pointers and uncertainty."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from research_notes.workflow_contract import FIELD_RULES, canonical_bytes, read_contract
from research_notes.workflow_baseline import new_session
from research_notes.workflow_extraction import extract_step, main, _validate_inventory

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "fixtures/cad-workflow-contract/reference-contract.json"
MANIFEST = ROOT / "fixtures/cad-workflow-extraction/manifest.json"
CASES = read_contract(MANIFEST)["cases"]


def payload(case):
    return (ROOT / case["source_path"]).read_bytes() if case["source_path"] else case["source_text"].encode()


def pointer(report, path):
    value = report
    for key in path.split("/")[1:]:
        value = value[int(key)] if isinstance(value, list) else value[key.replace("~1", "/").replace("~0", "~")]
    return value


@pytest.fixture(scope="module")
def reports():
    pytest.importorskip("OCP")
    contract = read_contract(CONTRACT)
    return {c["id"]: extract_step(payload(c), contract, file_name=c["id"] + ".step") for c in CASES}


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_live_route_preserves_one_snapshot_and_all_provenance(case, reports):
    report = reports[case["id"]]
    assert report["source"]["sha256"] == case["source_sha256"]
    assert report["inventory_sha256"] == hashlib.sha256(canonical_bytes(report["inventory"])).hexdigest()
    assert report["route"]["options"] == {"inspection": True, "include_slots": True, "preview": False}
    assert report["route"]["inventory_version"] == "1.14.0"
    assert report["contract_conformance"] == report["business_completion"] == report["adoption_decision"] == "not_evaluated"
    assert not report["customer_approved"] and not report["timing"]["operator_time_measured"]
    cells = list(report["summary"].values()) + [f for row in report["features"] for f in row["fields"].values()]
    for field in cells:
        values = [pointer(report, p) for p in field["provenance"]["paths"]]
        operation = field["provenance"]["operation"]
        if operation == "copy":
            assert len(values) == 1 and values[0] == field["value"]
        elif operation == "xyz_vector":
            assert values == field["value"]
        elif operation == "sole_solid_index":
            assert values == [1] and field["value"] == 1
        else:
            assert operation == "owner_not_recorded" and field["value"] is None
    if report["features"]:
        assert set(report["summary"]) | set(report["features"][0]["fields"]) == set(FIELD_RULES)


def test_zero_unknown_and_unanalysed_counts_are_distinct(reports):
    assert reports["no_holes"]["summary"]["whole_hole_count"]["value"] == 0
    assert reports["no_holes"]["summary"]["count_state"]["value"] == "certified_zero"
    for name in ("public_bracket", "mixed_circle_slot", "ellipse", "invalid_transport", "missing_units"):
        assert reports[name]["summary"]["whole_hole_count"]["value"] is None
        assert reports[name]["summary"]["whole_hole_count"]["availability"] == "unknown"
    assert len(reports["public_bracket"]["features"]) == 11
    assert reports["invalid_transport"]["input_observations"]["metrics"] is None
    assert reports["ellipse"]["inventory"]["status"] == "unresolved"


def test_circle_slot_dimensions_and_legacy_owner_are_mapped_without_inference(reports):
    circles = reports["public_bracket"]["features"][:5]
    slots = reports["public_bracket"]["features"][5:]
    assert all(r["fields"]["width_mm"]["availability"] == "not_applicable" for r in circles)
    assert all(r["fields"]["diameter_mm"]["availability"] == "not_applicable" for r in slots)
    assert all(r["fields"]["width_mm"]["value"] == pytest.approx(4.5) for r in slots)
    assert all(r["fields"]["length_mm"]["value"] == pytest.approx(7.5) for r in slots)
    assert reports["single"]["features"][0]["fields"]["solid_index"]["provenance"]["operation"] == "sole_solid_index"
    assert reports["public_bracket"]["features"][0]["fields"]["solid_index"]["provenance"]["operation"] == "copy"


def test_import_conditions_stay_observations_without_single_part_approval(reports):
    report = reports["public_assembly"]
    assert report["input_observations"]["metrics"]["solid_count"] == 2
    assert report["input_observations"]["single_solid_observed"] is False
    assert report["input_observations"]["unit_contexts"][0]["millimetres_per_source_unit"] == 1000
    assert report["input_observations"]["length_unit"] == "mm"
    assert report["contract_conformance"] == "not_evaluated"
    translated = reports["translated"]["features"][0]["fields"]["entry_center_mm"]
    assert translated["value"] == pytest.approx([36, -15, 11])


def test_first_seven_raw_results_match_previous_release(reports):
    old = read_contract(ROOT / "results/cad-workflow-contract/results.json")
    for row in old["inventory_observations"]:
        assert reports[row["id"]]["inventory"] == row["result"]


def test_case_binding_requires_same_source_and_contract_and_never_adds_operator_data(monkeypatch, reports):
    contract = read_contract(CONTRACT)
    session = new_session(contract, read_contract(MANIFEST), method="existing_extraction_with_full_review", operator="test")
    before = copy.deepcopy(session)
    raw = reports["single"]["inventory"]
    calls = []
    def existing(source, name, **options):
        calls.append((source, name, options))
        return copy.deepcopy(raw)
    monkeypatch.setattr("research_notes.hole_inventory.analyze_step", existing)
    case = next(c for c in CASES if c["id"] == "single")
    report = extract_step(payload(case), contract, part_reference="PART-A", baseline_session=session, case_id="single")
    assert len(calls) == 1 and calls[0][2] == {"inspection": True, "include_slots": True, "preview": False}
    assert report["summary"]["part_reference"]["value"] == "PART-A"
    assert report["baseline_binding"]["case_id"] == "single" and not report["baseline_binding"]["session_modified"]
    assert session == before and session["phase_records"] == session["quality_records"] == []
    for change in (dict(case_id="no_holes"), dict(case_id=None), dict(case_id="not-in-plan")):
        with pytest.raises(ValueError):
            extract_step(payload(case), contract, baseline_session=session, **change)
    assert len(calls) == 1
    other = copy.deepcopy(contract)
    other["contract_id"] = "different-reference"
    with pytest.raises(ValueError):
        extract_step(payload(case), other, baseline_session=session, case_id="single")
    session["method"] = "manual_cad_and_transcription"
    with pytest.raises(ValueError):
        extract_step(payload(case), contract, baseline_session=session, case_id="single")
    assert len(calls) == 1


@pytest.mark.parametrize("source", [b"", b"x" * 2_000_001, bytearray(b"STEP"), None])
def test_invalid_sources_do_not_call_the_backend(monkeypatch, source):
    def forbidden(*args, **kwargs):
        pytest.fail("backend called for invalid source")
    monkeypatch.setattr("research_notes.hole_inventory.analyze_step", forbidden)
    with pytest.raises(ValueError):
        extract_step(source, read_contract(CONTRACT))


@pytest.mark.parametrize("mutation", [
    lambda r: r.update(source_sha256="0" * 64),
    lambda r: r.update(analysis_mode="legacy_plate"),
    lambda r: r.update(recognized_hole_count=99),
    lambda r: r.update(hole_count=11),
    lambda r: r["holes"][0].update(axis=[0, 0, 0]),
    lambda r: r["holes"][0].update(depth_mm=True),
    lambda r: r["holes"][0].update(x_mm=float("nan")),
    lambda r: r["holes"][0].update(faces=[99999]),
    lambda r: r["holes"][0].update(solid_index=2),
    lambda r: r["holes"][0].update(id="H2"),
    lambda r: r["holes"][0].pop("longitudinal_direction"),
    lambda r: r["holes"][5].update(diameter_mm=4.5),
    lambda r: r["holes"][5].update(longitudinal_direction=[0, 0, 0]),
    lambda r: r["holes"][5].update(length_mm=1),
])
def test_inconsistent_upstream_observations_are_rejected(reports, mutation):
    raw = copy.deepcopy(reports["public_bracket"]["inventory"])
    mutation(raw)
    with pytest.raises(ValueError):
        _validate_inventory(raw, reports["public_bracket"]["source"]["sha256"], reports["public_bracket"]["source"]["bytes"])


def test_missing_part_reference_does_not_become_filename(reports):
    field = reports["public_bracket"]["summary"]["part_reference"]
    assert field["value"] is None and field["availability"] == "not_provided"
    assert field["provenance"]["paths"] == ["/caller_input/part_reference"]


def test_missing_owner_in_multi_solid_observation_does_not_default_to_one(monkeypatch, reports):
    raw = copy.deepcopy(reports["public_bracket"]["inventory"])
    raw["metrics"]["solid_count"] = 2
    del raw["holes"][0]["solid_index"]
    monkeypatch.setattr("research_notes.hole_inventory.analyze_step", lambda *a, **kw: raw)
    case = next(c for c in CASES if c["id"] == "public_bracket")
    report = extract_step(payload(case), read_contract(CONTRACT))
    owner = report["features"][0]["fields"]["solid_index"]
    assert owner["value"] is None and owner["availability"] == "unknown"


def test_study_records_connector_checks_without_workflow_or_operator_claims(tmp_path):
    pytest.importorskip("OCP")
    from experiments.run_workflow_extraction_study import run
    result = run(tmp_path, repeats=1)
    assert result["passed"] and result["summary"]["inputs"] == 10
    assert result["summary"]["provenance_cells"] == 242
    assert result["summary"]["previous_inventory_controls"] == 7
    assert result["business_completion"] == "not_evaluated" and not result["operator_time_measured"]


def test_cli_json_preserves_snapshot_and_rejects_output_input_collision(tmp_path, capsys):
    pytest.importorskip("OCP")
    source = ROOT / "fixtures/hole-inventory/sources/single.step"
    assert main([str(source), "--contract", str(CONTRACT), "--part-reference", "P-001", "--output-dir", str(tmp_path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert (tmp_path / "workflow-extraction.json").read_bytes() == canonical_bytes(report)
    assert report["summary"]["part_reference"]["value"] == "P-001"
    assert report["contract_conformance"] == "not_evaluated"
    collision = tmp_path / "workflow-extraction.json"
    original = collision.read_bytes()
    assert main([str(collision), "--contract", str(CONTRACT), "--output-dir", str(tmp_path)]) == 2
    capsys.readouterr()
    assert collision.read_bytes() == original


def test_rejected_cad_input_still_has_a_successfully_connected_report(tmp_path, capsys):
    pytest.importorskip("OCP")
    source = tmp_path / "invalid.step"
    source.write_bytes(b"not STEP")
    assert main([str(source), "--contract", str(CONTRACT)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["inventory"]["status"] == "rejected"
    assert report["summary"]["whole_hole_count"]["value"] is None


def test_invalid_definition_and_missing_file_produce_connection_error(tmp_path, capsys):
    path = tmp_path / "contract.json"
    path.write_text('{"x":NaN}')
    assert main([str(CONTRACT), "--contract", str(path)]) == 2
    assert not json.loads(capsys.readouterr().out)["connection_succeeded"]
    assert main([str(tmp_path / "missing.step"), "--contract", str(CONTRACT)]) == 2
    capsys.readouterr()
