"""Controls for conditional SVG reconstruction, editability and truth separation."""
import copy
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys

import pytest

from research_notes.drawing_to_cad import interpret_svg, build_candidate, candidate_code, project_shape, feature_model, main

ROOT=Path(__file__).resolve().parents[1]
FIXTURES=ROOT/"fixtures/drawing-to-cad"
CASES=json.loads((FIXTURES/"manifest.json").read_text())["cases"]


def inference(name):
    case=next(c for c in CASES if c["id"]==name)
    return interpret_svg((FIXTURES/case["svg"]).read_bytes(),json.loads((FIXTURES/case["context"]).read_text()))


@pytest.mark.parametrize("case",CASES,ids=lambda c:c["id"])
def test_fixed_drawing_outcomes_and_no_uncertain_solid(case):
    report=inference(case["id"])
    assert report["status"]==case["expected_status"]
    assert not report["ai_used"] and not report["original_authoring_history_recovered"]
    if report["status"]=="withheld":
        assert report["reason_code"]==case["expected_reason"]
        assert "parameters" not in report and "views" not in report
    else:
        assert report["evidence"]["W"][0]["visible_text"]=="W=40"
        assert report["parameters"]["thickness"]==8


def test_first_third_and_scale_variants_are_not_distinct_geometry_truth():
    assert inference("plain_first")["parameters"]==inference("plain_third")["parameters"]
    assert inference("one_first")["parameters"]==inference("one_third")["parameters"]
    assert inference("two_scaled")["parameters"]==inference("two_third")["parameters"]
    assert next(c for c in CASES if c["id"]=="two_scaled")["family_id"]==next(c for c in CASES if c["id"]=="two_third")["family_id"]


def test_interpretation_needs_no_evaluation_files_or_step_import(monkeypatch):
    case=next(c for c in CASES if c["id"]=="one_third")
    source=(FIXTURES/case["svg"]).read_bytes()
    context=json.loads((FIXTURES/case["context"]).read_text())
    import builtins
    original=builtins.open
    def guarded(path,*args,**kwargs):
        assert "/evaluation/" not in str(path).replace("\\","/")
        return original(path,*args,**kwargs)
    monkeypatch.setattr(builtins,"open",guarded)
    def forbidden(*args,**kwargs):
        pytest.fail("ground-truth/STEP reader entered inference")
    monkeypatch.setattr("research_notes.step_reconstruction.read_step_input",forbidden)
    report=interpret_svg(source,context)
    assert report["parameters"]["holes"]==[{"x":12.,"y":10.,"diameter":6.}]


@pytest.mark.parametrize("source",[b"not SVG",b"<!DOCTYPE svg><svg/>",b"<svg><metadata>W=40</metadata></svg>",b"<svg style='display:none'/>"])
def test_unsupported_or_hidden_metadata_is_not_a_dimension_shortcut(source):
    context=json.loads((FIXTURES/"inputs/one_third.context.json").read_text())
    report=interpret_svg(source,context)
    assert report["status"]=="withheld" and "parameters" not in report


def test_extra_ground_truth_context_is_rejected_instead_of_read():
    case=next(c for c in CASES if c["id"]=="one_third")
    source=(FIXTURES/case["svg"]).read_bytes()
    context=json.loads((FIXTURES/case["context"]).read_text())
    context["secret_thickness"]=8
    assert interpret_svg(source,context)["reason_code"]=="context_missing"


@pytest.mark.parametrize("name",["plain_third","one_third","two_third"])
def test_existing_feature_history_is_valid_and_editable(name):
    pytest.importorskip("OCP")
    report=inference(name)
    original=copy.deepcopy(report["parameters"])
    model,recomputed,output=build_candidate(original,report["source_sha256"])
    assert model.provenance=="unconfirmed_candidate" and output.metrics.analyzer_valid
    assert output.metrics.solid_count==1 and all(s.status=="valid" for s in recomputed.states)
    assert all(s.sketch_fingerprint for s in recomputed.states if s.node_id!="result")
    edited=copy.deepcopy(original)
    edited["thickness"]+=2
    after=build_candidate(edited,report["source_sha256"])[2]
    assert after.metrics.absolute_volume==pytest.approx(output.metrics.absolute_volume*10/8)
    assert report["parameters"]==original
    from research_notes.deterministic_recompute import model_from_dict
    assert model_from_dict(asdict(model))==model


def test_reprojection_comes_from_solid_hidden_line_removal():
    pytest.importorskip("OCP")
    from experiments.run_drawing_to_cad import projection_evaluation
    report=inference("one_third")
    shape=build_candidate(report["parameters"],report["source_sha256"])[2].shape
    projected=project_shape(shape)
    result=projection_evaluation(report["views"],projected)
    assert all(projected[n]["visible"] for n in ("front","top","right"))
    assert projected["front"]["hidden"]
    assert max(v["sampled_symmetric_max_mm"] for v in result.values())<.02
    changed=copy.deepcopy(report["parameters"])
    changed["width"]+=5
    wrong=project_shape(build_candidate(changed,report["source_sha256"])[2].shape)
    assert max(v["sampled_symmetric_max_mm"] for v in projection_evaluation(report["views"],wrong).values())>1


def test_generated_python_exports_step_and_invalid_edit_does_not_export(tmp_path):
    pytest.importorskip("OCP")
    report=inference("one_third")
    code=tmp_path/"candidate.py"
    code.write_text(candidate_code(report["parameters"],report["source_sha256"]))
    destination=tmp_path/"candidate.step"
    run=subprocess.run([sys.executable,str(code),str(destination)],cwd=tmp_path,capture_output=True,timeout=60)
    assert run.returncode==0,run.stderr.decode()
    from research_notes.step_reconstruction import read_step_input
    assert read_step_input(destination).metrics.solid_count==1
    edited=copy.deepcopy(report["parameters"])
    edited["holes"][0]["diameter"]=100
    code.write_text(candidate_code(edited,report["source_sha256"]))
    invalid=tmp_path/"invalid.step"
    run=subprocess.run([sys.executable,str(code),str(invalid)],cwd=tmp_path,capture_output=True,timeout=60)
    assert run.returncode!=0 and not invalid.exists()


def test_withheld_cli_creates_no_cad_recipe_or_model(tmp_path,capsys):
    case=next(c for c in CASES if c["id"]=="ambiguous_extent")
    assert main([str(FIXTURES/case["svg"]),str(FIXTURES/case["context"]),"--output-dir",str(tmp_path)])==0
    assert json.loads(capsys.readouterr().out)["status"]=="withheld"
    assert not (tmp_path/"candidate.py").exists() and not (tmp_path/"model.json").exists()


def test_edit_target_policy_does_not_equate_array_order_with_geometric_identity():
    from experiments.run_drawing_to_cad import edit_parameters
    first={"width":40.,"length":30.,"thickness":8.,"holes":[{"x":10.,"y":8.,"diameter":4.},{"x":28.,"y":21.,"diameter":6.}]}
    reversed_rows=copy.deepcopy(first)
    reversed_rows["holes"].reverse()
    canonical=lambda p:sorted(p["holes"],key=lambda h:(h["x"],h["y"]))
    assert canonical(edit_parameters(first))==canonical(edit_parameters(reversed_rows))
    assert canonical(edit_parameters(first,"sequence_first"))!=canonical(edit_parameters(reversed_rows,"sequence_first"))


def test_cli_refuses_stale_candidate_directory(tmp_path):
    from research_notes.drawing_to_cad import main
    existing = tmp_path / "candidate.py"
    existing.write_text("# previous candidate\n")
    with pytest.raises(SystemExit) as error:
        main([str(FIXTURES / "inputs/ambiguous_extent.svg"),
              str(FIXTURES / "inputs/ambiguous_extent.context.json"),
              "--output-dir", str(tmp_path)])
    assert error.value.code == 2
    assert existing.read_text() == "# previous candidate\n"
    assert not (tmp_path / "inference.json").exists()
