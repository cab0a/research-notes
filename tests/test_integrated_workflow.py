from pathlib import Path
from dataclasses import asdict
import io
import json
import subprocess
import sys
import pytest
from research_notes.integration_studies import selected_session
from research_notes.integrated_workflow import IntegratedSession,source_layers
from research_notes.conversational_proposals import parse_request
from research_notes.deterministic_recompute import model_fingerprint

ROOT=Path(__file__).resolve().parents[1]


def test_proposal_preview_confirmation_and_stale_guards(tmp_path):
    session=selected_session();fingerprint=model_fingerprint(session.model);volume=session._current_output().metrics.absolute_volume
    a=session.ask("穴の半径を1.3 mmに");b=session.ask("set feature radius 1.4 mm")
    assert model_fingerprint(session.model)==fingerprint
    assert session._current_output().metrics.absolute_volume==volume
    with pytest.raises(ValueError):session.apply(a["proposal_id"])
    session.apply(a["proposal_id"],confirm=True)
    assert session._current_output().metrics.absolute_volume<volume
    with pytest.raises(ValueError,match="stale"):session.apply(b["proposal_id"],confirm=True)
    with pytest.raises(ValueError,match="stale"):session.apply(a["proposal_id"],confirm=True)
    export=session.export_step(tmp_path/"edited.step")
    imported=IntegratedSession();imported.open_step(tmp_path/"edited.step")
    assert imported.inspection.imported.metrics.absolute_volume==pytest.approx(session._current_output().metrics.absolute_volume)
    assert "geometry only" in export["pmi_policy"]


def test_invalid_edit_and_failed_open_preserve_session(tmp_path):
    session=selected_session();before=session.status()
    with pytest.raises(ValueError):session.ask("穴の半径を99 mmに")
    bad=tmp_path/"invalid.step";bad.write_text("not STEP")
    with pytest.raises(ValueError):session.open_step(bad)
    assert session.status()==before
    with pytest.raises(ValueError):session.ask("set feature radius __import__('os')")
    assert parse_request("厚さを0.5 cmに").expression=="0.5 * cm"


def test_reconstruction_alternatives_are_never_auto_selected():
    session=IntegratedSession();session.open_step(ROOT/"fixtures/step-reconstruction/through_hole.step")
    report=session.review()
    assert len(report["alternatives"])==2 and session.model is None
    assert {r["explanation"] for r in report["alternatives"]}=={"profile_hole","through_hole"}
    assert all(p["sketch_evidence"] for p in report["alternatives"])
    assert session.rank()["automatic_selection"] is False
    assert session.model is None


def test_integrated_supplied_schema_keeps_stages_separate():
    fixture=ROOT/"fixtures/step-express-validation/scalar_types"
    result=source_layers(fixture.with_suffix(".step"),schema_path=fixture.with_suffix(".exp"))
    assert result["syntax"]["status"]=="accepted"
    assert result["schema"]["validation"]["decision"]=="accept"
    assert result["schema"]["full_ap_conformance"] is False
    assert result["application_semantics"]["status"]=="unsupported_schema"


def test_report_invalidation_after_direct_edit(tmp_path):
    session=selected_session();session.export_step(tmp_path/"old.step")
    assert session.export_record
    session.edit("feature","radius",1.2)
    assert session.export_record is None
    with pytest.raises(ValueError,match="recompute"):session.mass() if session.material else session.shape()
    session.recompute()
    assert session.analyze()["faces"]


def test_integrated_demo_terminal_and_fail_closed(tmp_path):
    script=(ROOT/"fixtures/integrated-workflow/demo_commands.txt").read_text(encoding="utf-8").replace("output/integrated-demo",str(tmp_path))
    path=tmp_path/"commands.txt";path.write_text(script,encoding="utf-8")
    result=subprocess.run([sys.executable,"-m","research_notes.integrated_tool","--script",str(path),"--output-dir",str(tmp_path)],cwd=ROOT,text=True,capture_output=True,timeout=90)
    assert result.returncode==0,result.stdout+result.stderr
    report=json.loads((tmp_path/"workflow.json").read_text())
    assert report["mass"]["mass_kg"]>0 and report["comparison"]["volume_change"]<0
    assert (tmp_path/"assembly/assembly.html").exists()
    path.write_text("open fixtures/step-reconstruction/through_hole.step\nselect 2 --confirm\nask 穴の半径を1.3 mmに\napply latest\nexport "+str(tmp_path/"blocked.step"),encoding="utf-8")
    result=subprocess.run([sys.executable,"-m","research_notes.integrated_tool","--script",str(path)],cwd=ROOT,text=True,capture_output=True,timeout=90)
    assert result.returncode==1 and not (tmp_path/"blocked.step").exists()
