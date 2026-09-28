"""Reproduce the v0.86-v0.90 transactional CAD and interoperability controls."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
from pathlib import Path
import tempfile

from research_notes.robustness_studies import ROOT, evidence_bytes, finish

STUDIES = {"transactional_recompute": 86, "stable_cad_api": 87, "diagnostic_workspace": 88,
           "step_writer_modes": 89, "interoperability_benchmark": 90}
HOLE = ROOT / "fixtures/step-reconstruction/through_hole.step"


def selected_workspace():
    from research_notes.cad_api import CadWorkspace
    workspace = CadWorkspace()
    workspace.open_step(HOLE, mode="reconstruct")
    candidate = next(c for c in workspace.candidates().data["candidates"] if c["explanation"] == "through_hole")
    workspace.select(candidate["candidate_id"], confirm=True, expected_revision=workspace.revision_token)
    return workspace


def source_manifest(path):
    data = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def rejected(operation, exception=ValueError):
    try:
        operation()
    except exception as error:
        return type(error).__name__
    return "not_rejected"


def _finish(name, output, fixtures, rows, detail, inputs, boundaries, refresh):
    return finish(output, fixtures, name, rows, detail, inputs, boundaries,
                  refresh=refresh, version=f"v0.{STUDIES[name]}.0")


def run_transactional_recompute(output, fixtures, *, refresh=False):
    from research_notes.transactional_recompute import TransactionalModel, TransactionalAssembly, RevisionConflict
    from research_notes.deterministic_recompute import recompute, model_fingerprint
    from research_notes.modeling_studies import branching_model
    from research_notes.assembly_controls import slider_assembly
    model, assembly = branching_model(), slider_assembly()
    tx = TransactionalModel(model)
    first = model_fingerprint(model)
    rows, detail = [], []
    def add(name, passed, record=None):
        rows.append({"control_id": name, "outcome": tx.last_outcome, "draft_pending": tx.dirty, "checks_pass": bool(passed)})
        detail.append({"control_id": name, "transaction": record or tx.record()})
    add("initial", all(s.status == "valid" for s in tx.committed.states))
    initial_token = tx.token
    tx.edit("feature", "radius", 1.5, expected_revision=tx.token)
    add("stage_without_publish", tx.dirty and model_fingerprint(tx.committed_model) == first)
    add("pending_export_refused", rejected(tx.current) == "ValueError")
    tx.commit(expected_revision=tx.token)
    add("commit_all", not tx.dirty and tx.last_outcome == "committed")
    cold = recompute(tx.committed_model)
    add("cold_recompute_equivalent", abs(cold.current_output().metrics.absolute_volume - tx.current().metrics.absolute_volume) < 1e-9)
    committed = tx.committed
    tx.edit("feature", "radius", 30., expected_revision=tx.token)
    tx.edit("spare_rib", "height", 3., expected_revision=tx.token)
    tx.commit(expected_revision=tx.token)
    states = {s.node_id: s for s in tx.attempt.states}
    add("failed_branch_atomic_abort", tx.last_outcome == "aborted" and tx.committed is committed and states["feature"].status == "failed" and states["result"].status == "stale")
    add("independent_branch_not_published", states["spare_result"].status == "valid" and
        states["spare_result"].metrics.absolute_volume != next(s.metrics.absolute_volume for s in committed.states if s.node_id == "spare_result"))
    tx.rollback(expected_revision=tx.token)
    add("rollback_last_valid", tx.committed is committed and not tx.dirty)
    tx.rollback(first, expected_revision=tx.token)
    add("rollback_checkpoint", model_fingerprint(tx.committed_model) == first and tx.token != initial_token)
    add("old_token_never_revives", rejected(lambda: tx.commit(expected_revision=initial_token), RevisionConflict) == "RevisionConflict")
    token = tx.token
    add("invalid_edit_unchanged", rejected(lambda: tx.edit("feature", "radius", float("nan"), expected_revision=tx.token)) == "ValueError" and tx.token == token)
    atx = TransactionalAssembly(assembly)
    atx.edit("clearance", "0 * mm", expected_revision=atx.token)
    atx.commit(expected_revision=atx.token)
    rows.append({"control_id": "assembly_contact_commit", "outcome": atx.last_outcome, "draft_pending": atx.record()["draft_pending"], "checks_pass": atx.last_outcome == "committed"})
    detail.append({"control_id": "assembly_contact_commit", "transaction": atx.record()})
    contact = atx.committed
    atx.edit("clearance", "-1 * mm", expected_revision=atx.token)
    atx.commit(expected_revision=atx.token)
    rows.append({"control_id": "assembly_interference_abort", "outcome": atx.last_outcome, "draft_pending": atx.record()["draft_pending"], "checks_pass": atx.last_outcome == "aborted" and atx.committed is contact})
    detail.append({"control_id": "assembly_interference_abort", "transaction": atx.record()})
    atx.rollback(expected_revision=atx.token)
    rows.append({"control_id": "assembly_rollback", "outcome": atx.last_outcome, "draft_pending": False, "checks_pass": atx.current() is contact})
    return _finish("transactional_recompute", output, fixtures, rows, detail,
        {"branching_model.json": evidence_bytes(asdict(model)), "assembly.json": evidence_bytes(asdict(assembly))},
        ["Atomic publication includes every feature node; assembly publication includes parts, placements and interference checks.",
         "Failed candidates retain last valid geometry with stale/failed branch diagnostics; pending drafts cannot export as current.",
         "In-memory checkpoints are bounded; this is not a persistent database, crash recovery system or concurrent shared workspace."], refresh)


def run_stable_cad_api(output, fixtures, *, refresh=False):
    from research_notes.cad_api import CadWorkspace, CadAPIError, api_contract
    workspace = CadWorkspace()
    rows, detail = [], []
    def case(name, operation, expected):
        try:
            result = operation()
            outcome = result.status
            evidence = {"api_version": result.api_version, "operation": result.operation, "status": result.status,
                        "envelope_fields": list(result.record()), "warnings": result.warnings}
        except CadAPIError as error:
            outcome, evidence = error.code, {"code": error.code, "api_version": "1.0.0"}
        rows.append({"control_id": name, "outcome": outcome, "expected": expected, "checks_pass": outcome == expected})
        detail.append({"control_id": name, **evidence})
    case("no_source", workspace.candidates, "no_source")
    case("open", lambda: workspace.open_step(HOLE, mode="reconstruct"), "ok")
    case("candidates", workspace.candidates, "ok")
    identifier = next(c["candidate_id"] for c in workspace.candidates().data["candidates"] if c["explanation"] == "through_hole")
    case("explicit_confirmation", lambda: workspace.select(identifier, expected_revision=workspace.revision_token), "confirmation_required")
    case("select", lambda: workspace.select(identifier, confirm=True, expected_revision=workspace.revision_token), "ok")
    previous = workspace.revision_token
    case("stage", lambda: workspace.edit("feature", "radius", 1.3, expected_revision=previous), "staged")
    case("stale_token", lambda: workspace.recompute(expected_revision=previous), "revision_conflict")
    case("pending_comparison", workspace.compare, "pending_changes")
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        case("pending_export", lambda: workspace.export_step(directory / "pending.step"), "pending_changes")
        case("recompute", lambda: workspace.recompute(expected_revision=workspace.revision_token), "committed")
        case("compare", workspace.compare, "ok")
        case("export", lambda: workspace.export_step(directory / "edited.step"), "ok")
        previous = workspace.revision_token
        case("failed_open", lambda: workspace.open_step(directory / "missing.step"), "io_error")
        rows.append({"control_id": "failed_open_keeps_state", "outcome": "retained", "expected": "retained", "checks_pass": previous == workspace.revision_token})
        oversized = directory / "large.step"
        oversized.write_bytes(b" " * 2_000_001)
        case("source_budget", lambda: workspace.open_step(oversized), "resource_limit")
    case("inspection_mode", lambda: workspace.open_step(HOLE), "ok")
    case("no_editable_candidate", workspace.candidates, "abstained")
    return _finish("stable_cad_api", output, fixtures, rows, detail,
        {"api_contract.json": evidence_bytes(api_contract()), "source.json": evidence_bytes(source_manifest(HOLE))},
        ["API contract 1.0 freezes method inputs, envelope, statuses, error codes and limits; additive diagnostic data can evolve.",
         "Reconstruction requires explicit candidate confirmation. Input inspection may abstain from editability.",
         "Revision tokens protect individual workspace edits, not concurrent processes or persistent transactions."], refresh)


def run_diagnostic_workspace(output, fixtures, *, refresh=False):
    from research_notes.diagnostic_workspace import workspace_snapshot
    workspace = selected_workspace()
    workspace.edit("feature", "radius", 1.3, expected_revision=workspace.revision_token)
    workspace.recompute(expected_revision=workspace.revision_token)
    report = workspace.workspace(output / "diagnostic-workspace").data
    snapshot = workspace_snapshot(workspace)
    checks = {"face_selection": len(snapshot["faces"]) == snapshot["comparison"]["after"]["face_count"],
        "edge_selection": len(snapshot["edges"]) == snapshot["comparison"]["after"]["edge_count"] and all(e["status"] == "sampled" for e in snapshot["edges"]),
        "source_and_revision": len(snapshot["source_sha256"]) == 64 and snapshot["revision_token"] == workspace.revision_token,
        "dependencies": len(snapshot["nodes"]) == 3 and snapshot["nodes"][-1]["dependencies"] == ("feature",),
        "constraint_state": len(snapshot["constraints"]) == 2 and all(c["satisfied"] for c in snapshot["constraints"]),
        "candidate_comparison": len(snapshot["candidates"]) == 2 and sum(c["selected"] for c in snapshot["candidates"]) == 1,
        "geometry_difference": abs(snapshot["comparison"]["volume_change_mm3"]) > 1.,
        "mesh_local_ids": set(snapshot["polygon_face_ids"]) <= {f["index"] for f in snapshot["faces"]}}
    workspace.edit("feature", "radius", 30., expected_revision=workspace.revision_token)
    workspace.recompute(expected_revision=workspace.revision_token)
    failed = workspace_snapshot(workspace)
    checks["failed_draft_labeled"] = failed["geometry_state"] == "retained_committed_not_draft" and failed["comparison"] == snapshot["comparison"]
    rows = [{"control_id": name, "outcome": "matched" if passed else "mismatch", "checks_pass": bool(passed)} for name, passed in checks.items()]
    return _finish("diagnostic_workspace", output, fixtures, rows,
        {"committed": {k: v for k, v in snapshot.items() if k not in {"polygons", "edges"}},
         "failed_draft": {k: v for k, v in failed.items() if k not in {"polygons", "edges"}},
         "display": {k: v for k, v in report.items() if k not in {"html", "snapshot"}}},
        {"source.json": evidence_bytes(source_manifest(HOLE)), "actions.json": evidence_bytes(["select through_hole with confirmation", "stage radius 1.3", "commit", "snapshot", "stage radius 30", "abort", "snapshot retained geometry"])},
        ["Interactive standalone HTML supports rotation and face/edge selection; JSON records the exact source and revision.",
         "Selection IDs are local to this snapshot. Candidate support faces refer to the imported source, not persistent edited IDs.",
         "The view is a read-only diagnostic snapshot. API/terminal commands perform edits and recomputation."], refresh)


def run_step_writer_modes(output, fixtures, *, refresh=False):
    from research_notes.step_writer_modes import prepare_step_write, canonical_step, write_step
    source_path = ROOT / "fixtures/step-round-trip-preservation/named_colored_box_source.step"
    source = source_path.read_bytes()
    # Use the production inspection route, with explicit source-unit normalization.
    from research_notes.cad_api import CadWorkspace
    workspace = CadWorkspace()
    workspace.open_step(source_path)
    shape = workspace._session.inspection.imported.shape
    rows, detail = [], []
    for mode in ("preserve", "canonical", "reconstruct"):
        payload, report = prepare_step_write(source=source, mode=mode, shape=shape)
        ok = payload == source if mode == "preserve" else payload != source and canonical_step(payload) == payload if mode == "canonical" else report["checks"]["geometry"] == "verified_invariants" and report["checks"]["attributes"] == "not_preserved"
        rows.append({"control_id": mode, "outcome": report["checks"]["structure"], "checks_pass": bool(ok)})
        detail.append(report)
    signed_path = ROOT / "fixtures/step-part21-exchange/signature_present.step"
    signed = signed_path.read_bytes()
    signed_copy, _ = prepare_step_write(source=signed, mode="preserve")
    controls = {"signed_preserve_exact": signed_copy == signed,
                "signed_canonical_refused": rejected(lambda: canonical_step(signed)) == "ValueError"}
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        original = directory / "original.step"
        original.write_bytes(source)
        controls["original_read_only"] = rejected(lambda: write_step(original, source=source, source_path=original, mode="canonical", overwrite=True)) == "ValueError" and original.read_bytes() == source
        target = directory / "target.step"
        write_step(target, source=source, mode="canonical")
        retained = target.read_bytes()
        controls["existing_requires_overwrite"] = rejected(lambda: write_step(target, source=source, mode="preserve"), OSError) == "FileExistsError" and target.read_bytes() == retained
        write_step(target, source=source, mode="preserve", overwrite=True)
        controls["explicit_overwrite"] = target.read_bytes() == source
    rows.extend({"control_id": name, "outcome": "matched" if passed else "mismatch", "checks_pass": bool(passed)} for name, passed in controls.items())
    return _finish("step_writer_modes", output, fixtures, rows, detail,
        {"sources.json": evidence_bytes([source_manifest(source_path), source_manifest(signed_path)])},
        ["Preserve retains exact source bytes. Canonical rewrites lexical trivia only, preserving significant token spelling/order.",
         "Canonical mode refuses signatures, anchors and external references; preserve does not validate signature authenticity.",
         "Reconstruction measures geometric round-trip invariants; semantic roles, names, colors and persistent topology identity are not retained.",
         "Output is verified before atomic file publication; original source and existing outputs are guarded."], refresh)


def run_interoperability_benchmark(output, fixtures, *, refresh=False):
    from research_notes.interoperability_benchmark import evaluate_interoperability
    rows, evidence, inputs, environment = evaluate_interoperability()
    output.mkdir(parents=True, exist_ok=True)
    (output / "interoperability_benchmark_environment.json").write_bytes(evidence_bytes(environment))
    return _finish("interoperability_benchmark", output, fixtures, rows, evidence,
        {"inputs.json": evidence_bytes(inputs)},
        ["Three syntax routes on 11 fixed inputs; two OCCT transfer interfaces on seven eligible geometry inputs.",
         "STEPControl and STEPCAF share OCCT 7.9.3. Agreement is not independent-kernel validation or majority-vote truth.",
         "Closed-single-solid mesh integration uses independent arithmetic over OCCT tessellation; ineligible shells/compounds remain explicit.",
         "Controlled EXPRESS sidecars validate two cases. Public-file full schemas are not supplied; syntax acceptance is not AP conformance.",
         "Names/colors are observed in XCAF only, at free roots/color table scope. One recorded Linux environment, not cross-platform certification."], refresh)


def run_study(name, output=None, fixtures=None, *, refresh=False):
    if name not in STUDIES:
        raise ValueError("unknown operational study")
    return globals()["run_" + name](Path(output or ROOT / "results"),
        Path(fixtures or ROOT / "fixtures" / name.replace("_", "-")), refresh=refresh)


def main(default=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", choices=tuple(STUDIES), default=default)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results")
    parser.add_argument("--fixture-dir", type=Path)
    parser.add_argument("--refresh-fixtures", action="store_true")
    args = parser.parse_args()
    passed = True
    for name in (args.study,) if args.study else STUDIES:
        directory = args.fixture_dir if args.study else args.fixture_dir / name.replace("_", "-") if args.fixture_dir else None
        rows = run_study(name, args.output_dir, directory, refresh=args.refresh_fixtures)
        matched = sum(bool(r["checks_pass"]) for r in rows)
        print(f"{name}: {matched}/{len(rows)} case contracts matched", flush=True)
        passed &= matched == len(rows)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
