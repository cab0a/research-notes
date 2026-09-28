from research_notes.artifact_contracts import compare_file
from pathlib import Path
import subprocess
import sys

import pytest

from research_notes.assembly_studies import (
    run_topological_references, run_parameter_expressions, run_feature_history_editing,
    run_assembly_constraints, run_assembly_recompute,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("runner,fixture", [
    (run_topological_references, "topological-references"),
    (run_parameter_expressions, "parameter-expressions"),
    (run_feature_history_editing, "feature-history-editing"),
    (run_assembly_constraints, "assembly-constraints"),
    (run_assembly_recompute, "assembly-recompute"),
])
def test_reference_artifacts_reproduce_exactly(tmp_path, runner, fixture):
    output, fixtures = tmp_path/"results", tmp_path/"fixtures"
    rows = runner(output, fixtures, refresh=True)
    assert all(r["checks_pass"] for r in rows)
    expected = ROOT/"fixtures"/fixture
    assert {p.name for p in fixtures.iterdir()} == {p.name for p in expected.iterdir()}
    for generated in fixtures.iterdir():
        compare_file(generated, expected/generated.name)
    for generated in output.iterdir():
        if generated.suffix in {".json", ".csv"}:
            compare_file(generated, ROOT/"results"/generated.name)
        else:
            assert generated.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_assembly_terminal_demo_and_motion_inspection(tmp_path):
    script = (ROOT/"fixtures/assembly-recompute/demo_commands.txt").read_text()
    script = script.replace("output/assembly-demo", str(tmp_path))
    script = script.replace("quit", "drop twist\nrecompute\nstatus\nrestore twist\nrecompute\nreport\nquit")
    commands = tmp_path/"commands.txt"
    commands.write_text(script)
    result = subprocess.run([sys.executable, "-m", "research_notes.assembly_tool", "--script", str(commands),
                             "--output-dir", str(tmp_path)], cwd=ROOT, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"degrees_of_freedom": 1' in result.stdout
    assert '"status": "interference"' in result.stdout
    assert (tmp_path/"edited.step").exists()
    assert (tmp_path/"assembly.html").exists()


def test_assembly_script_blocks_interfering_export(tmp_path):
    commands = tmp_path/"commands.txt"
    target = tmp_path/"clash.step"
    commands.write_text(f"open fixtures/assembly-constraints/fully_fixed.json\nset clearance -1 * mm\nrecompute\nexport {target}\n")
    result = subprocess.run([sys.executable, "-m", "research_notes.assembly_tool", "--script", str(commands)],
                             cwd=ROOT, capture_output=True, text=True, timeout=90)
    assert result.returncode == 1
    assert "interference" in result.stdout
    assert not target.exists()
