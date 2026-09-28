"""Exercise the actual Python and terminal import/edit/export interfaces."""

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

from research_notes.assisted_modeling import ConfirmationRequired, ModelingSession
from research_notes.parametric_features import analytic_feature_truth, feature_controls
from research_notes.step_reconstruction import read_step_input


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures/step-reconstruction"


def selected_session(kind="through_hole", explanation="through_hole"):
    session = ModelingSession()
    session.open_step(FIXTURES / f"{kind}.step")
    candidate = next(c for c in session.inspection.candidates if c.explanation == explanation)
    session.select_candidate(candidate.candidate_id, confirm=True)
    return session


@pytest.mark.parametrize("kind,explanation,parameter,value", [
    ("through_hole", "through_hole", "radius", 1.5),
    ("blind_hole", "blind_hole", "depth", 2.),
    ("pocket", "rectangular_pocket", "depth", 2.),
    ("boss", "cylindrical_boss", "height", 3.),
    ("rib", "rectangular_rib", "width", 1.5),
])
def test_complete_workflow_matches_independent_truth_and_preserves_source(tmp_path, kind, explanation, parameter, value):
    session = selected_session(kind, explanation)
    source = (FIXTURES / f"{kind}.step").read_bytes()
    session.edit("feature", parameter, value)
    assert session.status()["recompute_required"]
    session.recompute()
    target = tmp_path / "edited.step"
    report = session.export_step(target)
    imported = read_step_input(target)
    _, plate, feature = next(control for control in feature_controls() if control[0] == f"{kind}_after")
    volume, area = analytic_feature_truth(plate, feature)
    assert imported.metrics.absolute_volume == pytest.approx(volume, abs=1e-7)
    assert imported.metrics.surface_area == pytest.approx(area, abs=1e-7)
    assert report["sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()
    assert report["selection_confirmed"]
    assert not report["authoring_history_recovered"]
    assert (FIXTURES / f"{kind}.step").read_bytes() == source


def test_confirmation_gate_precedes_model_replacement(tmp_path):
    session = selected_session()
    old_model = session.model
    alternative = next(c for c in session.inspection.candidates if c.explanation == "profile_hole")
    with pytest.raises(ConfirmationRequired):
        session.select_candidate(alternative.candidate_id)
    assert session.model is old_model
    session.open_step(FIXTURES / "pocket.step")
    assert session.model is None and session.result is None
    with pytest.raises(ValueError, match="confirmed model"):
        session.export_step(tmp_path / "unconfirmed.step")
    assert not (tmp_path / "unconfirmed.step").exists()


def test_dirty_and_stale_results_cannot_be_compared_or_exported(tmp_path):
    session = selected_session()
    session.edit("feature", "radius", 30.)
    for action in (session.compare, lambda: session.export_step(tmp_path / "dirty.step")):
        with pytest.raises(ValueError, match="recompute"):
            action()
    failed = session.recompute()
    assert failed.state("feature").status == "failed"
    for action in (session.compare, lambda: session.export_step(tmp_path / "stale.step")):
        with pytest.raises(ValueError, match="stale"):
            action()
    assert not list(tmp_path.iterdir())
    session.edit("feature", "radius", 1.)
    recovered = session.recompute()
    assert not recovered.evaluated_nodes
    assert session.compare()["volume_change"] == pytest.approx(0., abs=1e-7)


def test_source_and_existing_destinations_are_protected(tmp_path):
    session = selected_session()
    with pytest.raises(ValueError, match="read-only"):
        session.export_step(session.source_path, overwrite=True)
    target = tmp_path / "existing.step"
    target.write_bytes(b"keep this data")
    with pytest.raises(FileExistsError):
        session.export_step(target)
    assert target.read_bytes() == b"keep this data"
    session.export_step(target, overwrite=True)
    assert read_step_input(target).metrics.analyzer_valid


def test_failed_import_does_not_discard_the_current_session(tmp_path):
    session = selected_session()
    old = session.model
    invalid = tmp_path / "invalid.step"
    invalid.write_bytes(b"not a STEP file")
    with pytest.raises(ValueError):
        session.open_step(invalid)
    assert session.model is old
    assert session.result.current_output().status == "valid"


def test_visual_report_contains_comparison_and_inspectable_state(tmp_path):
    session = selected_session()
    session.edit("feature", "radius", 1.5)
    session.recompute()
    report = session.write_comparison(tmp_path)
    assert report["volume_change"] < 0
    assert (tmp_path / "comparison.png").read_bytes().startswith(b"\x89PNG")
    assert "comparison.png" in (tmp_path / "comparison.html").read_text()
    assert (tmp_path / "comparison.json").is_file()
    assert (tmp_path / "session.json").is_file()


def test_actual_terminal_demo_executes_end_to_end(tmp_path):
    script = (ROOT / "fixtures/assisted-modeling/demo_commands.txt").read_text()
    export = tmp_path / "edited.step"
    script = script.replace("output/modeling-demo/edited.step", str(export))
    commands = tmp_path / "commands.txt"
    commands.write_text(script)
    completed = subprocess.run([sys.executable, "-m", "research_notes.modeling_tool", "--script", str(commands),
                                "--output-dir", str(tmp_path / "report")], cwd=ROOT, capture_output=True,
                               text=True, timeout=90)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert '"selection_confirmed": true' in completed.stdout
    assert (tmp_path / "report/comparison.html").exists()
    assert read_step_input(export).metrics.absolute_volume == pytest.approx(451.72566611769184, abs=1e-7)


def test_script_stops_on_unconfirmed_selection_without_export(tmp_path):
    target = tmp_path / "must_not_exist.step"
    commands = tmp_path / "commands.txt"
    commands.write_text(f"open fixtures/step-reconstruction/through_hole.step\nselect 2\nexport {target}\n")
    completed = subprocess.run([sys.executable, "-m", "research_notes.modeling_tool", "--script", str(commands)],
                               cwd=ROOT, capture_output=True, text=True, timeout=90)
    assert completed.returncode == 1
    assert "explicit confirmation" in completed.stdout
    assert not target.exists()
