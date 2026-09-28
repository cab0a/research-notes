"""Contract regressions, atomic failure injection and actual adapter controls."""
from dataclasses import replace
import io
import json
import os
from pathlib import Path
import subprocess

import pytest

from research_notes.cad_api import CadWorkspace, CadAPIError, api_contract
from research_notes.operational_studies import ROOT, STUDIES, HOLE, run_study, selected_workspace
from research_notes.transactional_recompute import TransactionalModel, RevisionConflict, isolated_result
from research_notes.modeling_studies import branching_model
from research_notes.deterministic_recompute import model_fingerprint
from research_notes.step_writer_modes import canonical_step, write_step


def compare_json(actual, expected):
    if isinstance(expected, dict):
        assert actual.keys() == expected.keys()
        for key in expected:
            compare_json(actual[key], expected[key])
    elif isinstance(expected, list):
        assert len(actual) == len(expected)
        for a, b in zip(actual, expected):
            compare_json(a, b)
    elif isinstance(expected, float):
        assert actual == pytest.approx(expected, rel=1e-5, abs=1e-9)
    else:
        assert actual == expected


@pytest.mark.parametrize("name", STUDIES)
def test_operational_artifacts_reproduce(tmp_path, name):
    output, fixtures = tmp_path / "results", tmp_path / "fixtures"
    rows = run_study(name, output, fixtures, refresh=True)
    assert all(r["checks_pass"] for r in rows)
    reference = ROOT / "fixtures" / name.replace("_", "-")
    assert {p.name for p in fixtures.iterdir()} == {p.name for p in reference.iterdir()}
    for path in fixtures.iterdir():
        assert path.read_bytes() == (reference / path.name).read_bytes()
    for path in output.iterdir():
        if path.is_dir():
            compare_json(json.loads((path / "workspace.json").read_text()),
                         json.loads((ROOT / "results" / path.name / "workspace.json").read_text()))
            assert '<svg id="viewer"' in (path / "workspace.html").read_text()
        elif path.name.endswith("_environment.json"):
            environment = json.loads(path.read_text())
            assert environment["packages"]["cadquery-ocp"] == "7.9.3.1.1"
            assert len(environment["external_parsers"]) == 2
        elif path.suffix == ".png":
            assert path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        elif path.suffix == ".json":
            compare_json(json.loads(path.read_text()), json.loads((ROOT / "results" / path.name).read_text()))
        else:
            assert path.read_bytes() == (ROOT / "results" / path.name).read_bytes()


def test_checkpoint_eviction_and_aba_tokens():
    tx = TransactionalModel(branching_model(), checkpoint_limit=2)
    first, old = model_fingerprint(tx.committed_model), tx.token
    for radius in (1.2, 1.3):
        tx.edit("feature", "radius", radius, expected_revision=tx.token)
        tx.commit(expected_revision=tx.token)
    assert len(tx.checkpoints) == 2 and first not in tx.checkpoints
    with pytest.raises(ValueError, match="evicted"):
        tx.rollback(first, expected_revision=tx.token)
    with pytest.raises(RevisionConflict):
        tx.commit(expected_revision=old)


def test_failed_side_branch_aborts_otherwise_valid_output():
    tx = TransactionalModel(branching_model())
    published = tx.committed
    tx.edit("feature", "radius", 1.3, expected_revision=tx.token)
    tx.edit("spare_rib", "width", 100., expected_revision=tx.token)
    tx.commit(expected_revision=tx.token)
    assert tx.last_outcome == "aborted" and tx.committed is published
    assert next(s for s in tx.attempt.states if s.node_id == "result").status == "valid"
    assert any(s.status == "failed" for s in tx.attempt.states)
    with pytest.raises(ValueError, match="draft"):
        tx.current()


def test_native_cache_is_deeply_isolated():
    from OCP.BRep import BRep_Builder, BRep_Tool
    from OCP.TopAbs import TopAbs_VERTEX
    from OCP.TopoDS import TopoDS
    from research_notes.brep_runtime import indexed_shapes
    tx = TransactionalModel(branching_model())
    original = TopoDS.Vertex_s(indexed_shapes(tx.current().shape, TopAbs_VERTEX).FindKey(1))
    before = BRep_Tool.Tolerance_s(original)
    copied = isolated_result(tx.committed)
    vertex = TopoDS.Vertex_s(indexed_shapes(copied.current_output().shape, TopAbs_VERTEX).FindKey(1))
    BRep_Builder().UpdateVertex(vertex, .2)
    assert BRep_Tool.Tolerance_s(vertex) == .2
    assert BRep_Tool.Tolerance_s(original) == before


def test_assembly_aborts_on_failed_component_side_branch():
    from research_notes.assembly_controls import slider_assembly
    from research_notes.parameter_expressions import Parameter
    from research_notes.transactional_recompute import TransactionalAssembly
    assembly = slider_assembly()
    assembly = replace(assembly,
        definitions=(replace(assembly.definitions[0], model=branching_model()),),
        parameters=tuple(replace(p, expression="4 * mm") if p.name == "clearance" else p for p in assembly.parameters) +
                   (Parameter("rib_width", "1 * mm", "mm", .001, 100.),),
        bindings=assembly.bindings + (("block", "rib_width", "spare_rib", "width"),))
    tx = TransactionalAssembly(assembly)
    committed = tx.committed
    tx.edit("rib_width", "100 * mm", expected_revision=tx.token)
    tx.commit(expected_revision=tx.token)
    assert tx.last_outcome == "aborted" and tx.committed is committed
    component = dict(tx.attempt.component_results)["block"]
    assert component.current_output().status == "valid"
    assert component.state("spare_rib").status == "failed"


def test_unexpected_recompute_exception_keeps_commit_and_records_failure(monkeypatch):
    import research_notes.transactional_recompute as module
    tx = TransactionalModel(branching_model())
    committed = tx.committed
    tx.edit("feature", "radius", 1.3, expected_revision=tx.token)
    old_token = tx.token
    def crash(*args):
        raise RuntimeError("injected native failure")
    monkeypatch.setattr(module, "recompute", crash)
    with pytest.raises(RuntimeError, match="injected"):
        tx.commit(expected_revision=old_token)
    assert tx.committed is committed and tx.last_outcome == "aborted"
    assert tx.token != old_token and tx.record()["attempt_error"]["diagnostic_class"] == "RuntimeError"
    tx.rollback(expected_revision=tx.token)
    assert tx.current().shape is committed.current_output().shape and tx.attempt_error is None


def test_contract_matches_frozen_fixture():
    assert api_contract() == json.loads((ROOT / "fixtures/stable-cad-api/api_contract.json").read_text())
    assert set(CadWorkspace().status().record()) == set(api_contract()["result_fields"])


def test_confirmed_selection_failure_is_atomic(monkeypatch):
    import research_notes.cad_api as module
    workspace = CadWorkspace()
    workspace.open_step(HOLE, mode="reconstruct")
    before = workspace.status().record()
    identifier = workspace.candidates().data["candidates"][0]["candidate_id"]
    def fail(model):
        raise RuntimeError("injected initialization failure")
    monkeypatch.setattr(module, "TransactionalModel", fail)
    with pytest.raises(CadAPIError) as caught:
        workspace.select(identifier, confirm=True, expected_revision=workspace.revision_token)
    assert caught.value.code == "native_failure"
    assert workspace.status().record() == before and workspace._session.selected_candidate_id is None


def test_source_preservation_does_not_silently_export_edits(tmp_path):
    workspace = selected_workspace()
    workspace.edit("feature", "radius", 30., expected_revision=workspace.revision_token)
    workspace.recompute(expected_revision=workspace.revision_token)
    with pytest.raises(CadAPIError) as error:
        workspace.export_step(tmp_path / "bad.step")
    assert error.value.code == "pending_changes" and not (tmp_path / "bad.step").exists()
    result = workspace.export_step(tmp_path / "original.step", mode="preserve")
    assert "source_bytes_do_not_include_model_edits" in result.warnings
    assert (tmp_path / "original.step").read_bytes() == HOLE.read_bytes()


def test_workspace_meshing_never_mutates_published_geometry(tmp_path):
    from research_notes.modeling_common import measure_shape
    from research_notes.diagnostic_workspace import workspace_snapshot
    workspace = selected_workspace()
    shape = workspace._transaction.current().shape
    before = measure_shape(shape)
    token = workspace.revision_token
    workspace.workspace(tmp_path)
    assert before == measure_shape(shape) and token == workspace.revision_token
    snapshot = workspace_snapshot(workspace)
    assert set(snapshot["polygon_face_ids"]) <= set(range(1, before.face_count + 1))
    assert all(len(e["points"]) == 25 for e in snapshot["edges"])


def test_workspace_escapes_hostile_source_name(tmp_path):
    workspace = selected_workspace()
    imported = replace(workspace._session.inspection.imported, file_name='</script><script>alert(1)</script>')
    workspace._session.inspection = replace(workspace._session.inspection, imported=imported)
    workspace.workspace(tmp_path)
    page = (tmp_path / "workspace.html").read_text()
    assert '</script><script>alert(1)' not in page
    assert '\\u003c/script>' in page
    assert json.loads((tmp_path / "workspace.json").read_text())["file_name"] == imported.file_name


def test_canonical_preserves_comment_markers_inside_strings():
    raw = (ROOT / "fixtures/step-round-trip-preservation/named_colored_box_source.step").read_bytes()
    raw = raw.replace(b"Controlled Box", b"Box /* literal */ O''Brien")
    result = canonical_step(raw)
    assert b"Box /* literal */ O''Brien" in result
    assert canonical_step(result) == result
    from research_notes.step_part21 import parse_part21_document
    tokens = lambda source: [(t.kind, t.raw) for t in parse_part21_document(source).significant_tokens]
    assert tokens(raw) == tokens(result)


def test_original_alias_and_existing_file_are_guarded(tmp_path):
    source = HOLE.read_bytes()
    original, alias = tmp_path / "original.step", tmp_path / "alias.step"
    original.write_bytes(source)
    os.link(original, alias)
    with pytest.raises(ValueError, match="read-only"):
        write_step(alias, source=source, mode="canonical", source_path=original, overwrite=True)
    assert original.read_bytes() == source


def test_failed_publication_leaves_existing_file_and_no_temporary(tmp_path, monkeypatch):
    import research_notes.step_writer_modes as module
    target = tmp_path / "existing.step"
    target.write_bytes(b"retained")
    def fail(*args):
        raise OSError("injected publication failure")
    monkeypatch.setattr(module.os, "replace", fail)
    with pytest.raises(OSError):
        write_step(target, source=HOLE.read_bytes(), mode="canonical", overwrite=True)
    assert target.read_bytes() == b"retained"
    assert list(tmp_path.iterdir()) == [target]


def test_intervening_output_is_not_overwritten(tmp_path, monkeypatch):
    import research_notes.step_writer_modes as module
    target = tmp_path / "raced.step"
    link = os.link
    def intervene(source, destination):
        Path(destination).write_bytes(b"other writer")
        return link(source, destination)
    monkeypatch.setattr(module.os, "link", intervene)
    with pytest.raises(FileExistsError):
        write_step(target, source=HOLE.read_bytes(), mode="preserve")
    assert target.read_bytes() == b"other writer"
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.parametrize("fixture", ["edition3_anchor", "edition3_signature"])
def test_canonical_excluded_exchange_sections(fixture):
    with pytest.raises(ValueError, match="excludes"):
        canonical_step((ROOT / "fixtures/step-part21-conformance" / (fixture + ".step")).read_bytes())


def test_adapter_fault_and_timeout_are_not_parser_rejections(monkeypatch):
    from research_notes.interoperability_benchmark import observe_route
    import research_notes.interoperability_benchmark as module
    result = observe_route("ifcopenshell_step_file_parser", HOLE, parser_root=ROOT / "missing-checkout")
    assert result["outcome"] == "error"
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])
    monkeypatch.setattr(module.subprocess, "run", timeout)
    assert observe_route("stepcontrol", HOLE)["diagnostic_class"] == "timeout"


def test_layer_disagreements_are_preserved():
    evidence = {r["control_id"]: r for r in json.loads((ROOT / "results/interoperability_benchmark_evidence.json").read_text())}
    invalid = evidence["invalid_exponent"]["routes"]
    assert [invalid[r]["outcome"] for r in ("builtin", "steputils", "ifcopenshell_step_file_parser")] == ["reject", "accept", "reject"]
    schema = evidence["schema_invalid"]
    assert all(schema["routes"][r]["outcome"] == "accept" for r in schema["routes"])
    assert schema["schema_validation"]["decision"] == "reject"
    for name in ("named_box", "named_hole", "public_bracket"):
        item = evidence[name]
        assert item["geometry_comparison"]["independence"] == "same_OCCT_kernel_different_transfer_interfaces"
        assert item["routes"]["stepcontrol"]["mesh_integral"]["volume_relative_error_vs_gprop"] <= .001
    assert evidence["public_assembly"]["routes"]["stepcontrol"]["mesh_integral"]["status"] == "not_eligible"


def test_geometry_comparator_detects_drift():
    from copy import deepcopy
    from research_notes.interoperability_benchmark import compare_geometry
    item = json.loads((ROOT / "results/interoperability_benchmark_evidence.json").read_text())[0]["routes"]["stepcontrol"]
    changed = deepcopy(item)
    changed["metrics"]["absolute_volume"] *= 1.001
    assert compare_geometry(item, changed)["status"] == "disagree"
    assert compare_geometry(item, {"outcome": "error"})["status"] == "not_comparable"


def test_terminal_end_to_end_and_integrated_entrypoint(tmp_path):
    from research_notes.integrated_tool import IntegratedShell
    shell = IntegratedShell(tmp_path, stdout=io.StringIO())
    for command in (f'open "{HOLE}"', "select 1 --confirm", "set feature radius 1.3", "recompute", "compare", "workspace",
                    f'export "{tmp_path / "edited.step"}" reconstruct', "set feature radius 30", "recompute", "rollback"):
        shell.onecmd("cad " + command)
        assert shell.errors == 0, shell.stdout.getvalue()
    assert (tmp_path / "edited.step").is_file() and (tmp_path / "cad/workspace.html").is_file()
    assert shell.session.inspection is None  # The legacy workspace is a separate explicit command group.
    assert not shell.cad.workspace.status().data["transaction"]["draft_pending"]
