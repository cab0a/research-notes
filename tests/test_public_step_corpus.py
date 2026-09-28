from research_notes.artifact_contracts import compare_file
from dataclasses import replace
import hashlib
import io
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from research_notes.integrated_workflow import IntegratedSession
from research_notes.public_step import length_contexts, read_step_for_inspection, analyze_public_shape
from research_notes.public_step_corpus import CORPUS, load_manifest, verify_corpus, fetch_corpus, run_public_step_corpus
from research_notes.spatial_workflow import WorkBudget
from research_notes.step_part21 import parse_part21_document

ROOT = Path(__file__).resolve().parents[1]
SOURCES = CORPUS / "sources"


def test_upstream_bytes_notices_and_family_provenance():
    manifest = verify_corpus()
    assert len(manifest["samples"]) == 6
    assert len({s["family_id"] for s in manifest["samples"]}) == 5
    assert len({a["repository"] for a in manifest["assets"]}) == 3
    assert all(s["evaluation_role"].startswith("external_validation_only") for s in manifest["samples"])
    assert all(s["modifications"] == "none; local filename only" for s in manifest["samples"])


def test_corrupt_upstream_file_is_never_accepted_or_refetched_silently(tmp_path, monkeypatch):
    root = tmp_path / "corpus"
    shutil.copytree(CORPUS, root)
    asset = root / "sources/cadquery_assembly.step"
    original = asset.read_bytes()
    asset.write_bytes(original.replace(b"METRE", b"INCH ", 1))
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_corpus(root)
    monkeypatch.setattr("research_notes.public_step_corpus.urlopen", lambda *a, **kw: pytest.fail("unexpected network"))
    with pytest.raises(ValueError, match="changed upstream/existing"):
        fetch_corpus(root)
    assert asset.read_bytes() != original


@pytest.mark.parametrize("mutation", ["escape", "revision", "license", "license_revision"])
def test_manifest_rejects_unpinned_or_unlicensed_assets(tmp_path, mutation):
    data = load_manifest()
    if mutation == "escape": data["assets"][0]["path"] = "../escape"
    if mutation == "revision": data["assets"][0]["revision"] = "master"
    if mutation == "license": data["samples"][0]["license_paths"] = []
    if mutation == "license_revision": data["samples"][0]["license_paths"] = ["licenses/build123d/LICENSE"]
    (tmp_path / "manifest.json").write_text(json.dumps(data))
    with pytest.raises(ValueError): load_manifest(tmp_path)


def test_explicit_fetch_checks_hashes_and_is_idempotent(tmp_path, monkeypatch):
    manifest = load_manifest()
    payloads = {a["download_url"]:(CORPUS/a["path"]).read_bytes() for a in manifest["assets"]}
    calls = []
    def opener(request, **kwargs):
        calls.append(request.full_url)
        return io.BytesIO(payloads[request.full_url])
    monkeypatch.setattr("research_notes.public_step_corpus.urlopen", opener)
    fetch_corpus(tmp_path)
    assert len(calls) == 10
    fetch_corpus(tmp_path)
    assert len(calls) == 10
    assert (tmp_path / "expectations.json").read_bytes() == (CORPUS / "expectations.json").read_bytes()


def test_changed_download_is_not_written(tmp_path, monkeypatch):
    monkeypatch.setattr("research_notes.public_step_corpus.urlopen", lambda *a, **kw: io.BytesIO(b"changed"))
    with pytest.raises(ValueError, match="changed upstream"):
        fetch_corpus(tmp_path)
    assert not list(tmp_path.rglob("*"))


def test_metre_source_is_normalized_to_millimetres_without_guessing_unit_name():
    source = SOURCES / "cadquery_assembly.step"
    data = read_step_for_inspection(source)
    assert data.roots == 2
    assert data.unit_contexts[0]["millimetres_per_source_unit"] == 1000
    assert data.imported.metrics.solid_count == 2
    # Independent analytic volumes: a 10-mm cube and radius-5, height-10 cylinder.
    assert data.imported.metrics.absolute_volume == pytest.approx(1000 + 250 * math.pi)
    payload = source.read_bytes().replace(b"'METRE'", b"'misleading name'")
    assert length_contexts(parse_part21_document(payload))[0]["millimetres_per_source_unit"] == 1000


@pytest.mark.parametrize("old,new", [
    (b"LENGTH_MEASURE( 1.00000000000000 )", b"LENGTH_MEASURE( -1.0 )"),
    (b"#65 = LENGTH_MEASURE_WITH_UNIT( LENGTH_MEASURE( 1.00000000000000 ), #115 )", b"#65 = LENGTH_MEASURE_WITH_UNIT( LENGTH_MEASURE( 1.0 ), #33 )"),
    (b"#65 = LENGTH_MEASURE_WITH_UNIT( LENGTH_MEASURE( 1.00000000000000 ), #115 )", b"#65 = LENGTH_MEASURE_WITH_UNIT( LENGTH_MEASURE( 1.0 ), #999999 )"),
    (b"DIMENSIONAL_EXPONENTS( 1.00000000000000,", b"DIMENSIONAL_EXPONENTS( 2.00000000000000,"),
])
def test_invalid_unit_factors_cycles_references_and_dimensions_are_refused(old, new):
    payload = (SOURCES / "cadquery_assembly.step").read_bytes()
    assert old in payload
    with pytest.raises(ValueError): length_contexts(parse_part21_document(payload.replace(old, new)))


def test_mixed_contexts_and_external_sources_are_refused():
    payload = (SOURCES / "ublox_sam_ap203.step").read_bytes()
    mixed = payload.replace(b"SI_UNIT ( .MILLI., .METRE. )", b"SI_UNIT ( .CENTI., .METRE. )", 1)
    with pytest.raises(ValueError, match="mixed length"):
        length_contexts(parse_part21_document(mixed))
    payload = (SOURCES / "build123d_bracket.step").read_bytes()
    payload = payload.replace(b"END-ISO-10303-21;", b"END-ISO-10303-21;")
    end = payload.rfind(b"ENDSEC;")
    payload = payload[:end] + b"#999999=EXTERNAL_SOURCE('https://example.invalid/part.step');\n" + payload[end:]
    with pytest.raises(ValueError, match="external STEP"):
        length_contexts(parse_part21_document(payload))


@pytest.mark.parametrize("budget", [replace(WorkBudget(), max_bytes=100), replace(WorkBudget(), max_geometry=1), replace(WorkBudget(), max_topology=10)])
def test_native_inspection_budgets(budget):
    with pytest.raises(ValueError, match="budget"):
        read_step_for_inspection(SOURCES / "cadquery_assembly.step", budget=budget)


def test_inspection_mode_keeps_edit_guards_and_failed_open_is_atomic(tmp_path):
    session = IntegratedSession()
    with pytest.raises(ValueError): session.open_step(SOURCES / "build123d_bracket.step")
    session.open_step_for_inspection(SOURCES / "build123d_bracket.step")
    assert session.inspection.imported.metrics.face_count == 42
    assert session.review()["alternatives"] == [] and session.rank()["decision"] == "not_evaluated"
    with pytest.raises(ValueError): session.edit("base", "width", 8)
    with pytest.raises(ValueError): session.export_step(tmp_path / "invalid.step")
    before = session.status()
    invalid = tmp_path / "bad.step"; invalid.write_bytes(b"not STEP")
    with pytest.raises(ValueError): session.open_step_for_inspection(invalid)
    assert session.status() == before
    source = SOURCES / "build123d_bracket.step"
    with pytest.raises(ValueError, match="read-only"): session.export_inspected_step(source, overwrite=True)
    exported = session.export_inspected_step(tmp_path / "bracket.step")
    assert exported["round_trip"]["status"] == "verified_invariants"
    with pytest.raises(FileExistsError): session.export_inspected_step(tmp_path / "bracket.step")
    assert read_step_for_inspection(tmp_path / "bracket.step").imported.metrics.face_count == 42


def test_disputed_export_does_not_write(tmp_path, monkeypatch):
    session = IntegratedSession(); session.open_step_for_inspection(SOURCES / "cadquery_assembly.step")
    monkeypatch.setattr("research_notes.public_step.measured_round_trip", lambda shape:(None,{"status":"disputed"}))
    with pytest.raises(ValueError, match="disagrees"): session.export_inspected_step(tmp_path / "blocked.step")
    assert not (tmp_path / "blocked.step").exists()


def test_face_analysis_retains_partial_coverage_and_errors(monkeypatch):
    shape = read_step_for_inspection(SOURCES / "cadquery_assembly.step").imported.shape
    def failure(*args, **kwargs): raise ValueError("missing p-curve control")
    monkeypatch.setattr("research_notes.intersection_analysis.inspect_trimming", failure)
    report = analyze_public_shape(shape, max_faces=2)
    assert report["status"] == "partial" and report["omitted_face_count"] == 7
    assert report["trim_check_failures"] == 2
    assert all(r["trimming"]["status"] == "unsupported" for r in report["faces"])


def test_public_corpus_reproduces_offline_and_keeps_failures(tmp_path, monkeypatch):
    monkeypatch.setattr("research_notes.public_step_corpus.urlopen", lambda *a, **kw: pytest.fail("ordinary validation must stay offline"))
    rows = run_public_step_corpus(tmp_path)
    assert all(r["checks_pass"] for r in rows)
    assert sum(r["trim_check_failures"] for r in rows) == 114
    assert rows[-1]["analysis"] == "partial" and rows[-1]["analyzed_faces"] == 256
    assert all(r["editable_candidates"] == 0 for r in rows)
    for path in tmp_path.iterdir():
        if path.suffix in {".json", ".csv"}:
            compare_file(path, ROOT/"results"/path.name)


def test_public_terminal_demo(tmp_path):
    commands = (CORPUS / "demo_commands.txt").read_text().replace("output/public-step-demo", str(tmp_path))
    script = tmp_path / "demo.txt"; script.write_text(commands)
    result = subprocess.run([sys.executable, "-m", "research_notes.integrated_tool", "--script", str(script), "--output-dir", str(tmp_path)],
                            cwd=ROOT, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    evidence = json.loads((tmp_path / "workflow.json").read_text())
    assert evidence["reconstruction"]["status"] == "inspection_only"
    assert evidence["export"]["mode"] == "inspection_only"
    assert evidence["geometry_analysis"]["face_count"] == 42
    assert "Inspection only: no editable candidates" in (tmp_path / "workflow.html").read_text()
