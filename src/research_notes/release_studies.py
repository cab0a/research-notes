"""Auditable v0.91-v1.0 release studies; platform claims require real observations."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import tempfile

from research_notes.robustness_studies import ROOT, evidence_bytes, finish

STUDIES = {"cad_platform_reproducibility": 91, "cad_fuzzing": 92, "cad_resource_contracts": 93,
           "blinded_assistance_evaluation": 94, "cad_review_workflow": 95, "cad_end_to_end": 96,
           "cad_claim_traceability": 97, "cad_contract_freeze": 98, "cad_release_candidate": 99,
           "cad_stable_release": 100}
LIMITATIONS = [
    "Stability covers the declared API, controls and resource policies, not arbitrary STEP or full AP conformance.",
    "Reconstruction is a confirmed hypothesis in a small feature grammar, never recovered authoring history.",
    "Native operations in the interactive API are in-process; only the resource/fuzz workers have hard process deadlines.",
    "Memory admission is estimated; Python allocation measurements exclude native OCCT/NumPy memory.",
    "AI ranking remains advisory; held-out synthetic families do not establish industrial accuracy or human productivity.",
    "Local topology IDs expire with their source/revision; preserve mode does not include geometry edits.",
    "PolyForm Noncommercial 1.0.0 and separately recorded third-party licenses apply.",
]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def record(name, passed, outcome="verified"):
    return {"control_id": name, "outcome": outcome, "checks_pass": bool(passed)}


def platform_study():
    from research_notes.cad_platform import aggregate_platforms
    paths = sorted((ROOT / "results/cad-platforms").glob("*/cad_platform.json"))
    report = aggregate_platforms(paths)
    rows = [record(r["label"], r["checks_pass"], "measured") for r in report["platforms"]]
    return rows, report, {"observations.json": evidence_bytes([{"path": p.relative_to(ROOT).as_posix(), "sha256": digest(p)} for p in paths])}


def review_study(output):
    from research_notes.cad_api import CadWorkspace, CadAPIError
    from research_notes.operational_studies import HOLE
    api = CadWorkspace()
    api.open_step(HOLE, mode="reconstruct")
    rows, audit = [], []
    def add(name, passed, data):
        rows.append(record(name, passed))
        audit.append({"task": name, "result": data, "state": api.status().record()})
    def denied(name, call, code):
        token = api.revision_token
        try:
            call()
        except CadAPIError as error:
            add(name, error.code == code and token == api.revision_token, error.record())
        else:
            add(name, False, {"error": "operation was not refused"})
    candidates = api.candidates().data["candidates"]
    candidate = next(c for c in candidates if c["explanation"] == "through_hole")
    add("inspect_alternatives", len(candidates) >= 2, candidates)
    denied("confirmation_required", lambda: api.select(candidate["candidate_id"], expected_revision=api.revision_token), "confirmation_required")
    denied("reject_without_adopting", lambda: api.edit("feature", "radius", 1.3, expected_revision=api.revision_token), "no_model")
    selected = api.select(candidate["candidate_id"], confirm=True, expected_revision=api.revision_token)
    add("explicit_adoption", selected.status == "ok", selected.record())
    old = api.revision_token
    api.edit("feature", "radius", 30., expected_revision=old)
    denied("stale_review_token", lambda: api.recompute(expected_revision=old), "revision_conflict")
    aborted = api.recompute(expected_revision=api.revision_token)
    add("invalid_proposal_retains_geometry", aborted.status == "aborted", aborted.record())
    denied("failed_draft_cannot_export", lambda: api.export_step(output / "must_not_exist.step"), "pending_changes")
    api.rollback(expected_revision=api.revision_token)
    api.edit("feature", "radius", 1.3, expected_revision=api.revision_token)
    corrected = api.recompute(expected_revision=api.revision_token)
    add("correct_and_commit", corrected.status == "committed", corrected.record())
    compared = api.compare()
    add("compare_evidence", bool(compared.data), compared.record())
    token = api.revision_token
    api.workspace(output / "cad-review-workspace")
    add("read_only_snapshot", token == api.revision_token, {"snapshot": "cad-review-workspace/workspace.html"})
    return rows, {"tasks": audit, "study_design": "scripted interaction controls; no recruited human participants and no productivity estimate"}, {"tasks.json": evidence_bytes([r["control_id"] for r in rows])}


def end_to_end_study(output):
    from research_notes.cad_api import CadWorkspace
    from research_notes.public_step import read_step_for_inspection, measured_round_trip
    edits = [("plain_plate", "plate_extrusion", "base", "width", 13.),
             ("through_hole", "through_hole", "feature", "radius", 1.3),
             ("blind_hole", "blind_hole", "feature", "depth", 1.2),
             ("boss", "cylindrical_boss", "feature", "height", 2.5),
             ("pocket", "rectangular_pocket", "feature", "depth", 1.2),
             ("rib", "rectangular_rib", "feature", "height", 2.5)]
    rows, evidence, inputs = [], [], []
    with tempfile.TemporaryDirectory() as temporary:
        for name, explanation, node, parameter, value in edits:
            source = ROOT / "fixtures/step-reconstruction" / (name + ".step")
            api = CadWorkspace()
            opened = api.open_step(source, mode="reconstruct")
            candidates = api.candidates().data["candidates"]
            candidate = next(c for c in candidates if c["explanation"] == explanation)
            api.select(candidate["candidate_id"], confirm=True, expected_revision=api.revision_token)
            api.edit(node, parameter, value, expected_revision=api.revision_token)
            result = api.recompute(expected_revision=api.revision_token)
            comparison = api.compare().record()
            destination = Path(temporary) / (name + ".step")
            export = api.export_step(destination)
            reimport = read_step_for_inspection(destination)
            passed = result.status == "committed" and reimport.imported.metrics.analyzer_valid
            rows.append(record(name, passed, "edited_and_reimported"))
            inputs.append({"path": source.relative_to(ROOT).as_posix(), "sha256": digest(source), "edit": [node, parameter, value]})
            # Paths and native writer bytes are not stable identifiers.
            evidence.append({"control_id": name, "opened": opened.status, "candidate": explanation,
                "recompute": result.status, "comparison": comparison, "export_checks": export.data["checks"],
                "reimport_metrics": asdict(reimport.imported.metrics)})
        for name in ("cadquery_assembly", "build123d_bracket", "ublox_sam_ap203", "ublox_sam_ap214"):
            source = ROOT / "fixtures/public-step-corpus/sources" / (name + ".step")
            api = CadWorkspace()
            api.open_step(source)
            candidate_status = api.candidates().status
            destination = Path(temporary) / (name + ".step")
            api.export_step(destination, mode="preserve")
            imported = read_step_for_inspection(source)
            payload, roundtrip = measured_round_trip(imported.imported.shape)
            passed = candidate_status == "abstained" and destination.read_bytes() == source.read_bytes() and roundtrip["status"] == "verified_invariants"
            rows.append(record(name, passed, "inspection_preserve_and_geometry_roundtrip"))
            inputs.append({"path": source.relative_to(ROOT).as_posix(), "sha256": digest(source), "edit": None})
            evidence.append({"control_id": name, "candidate_status": candidate_status, "roundtrip": roundtrip,
                "license_manifest": "fixtures/public-step-corpus/manifest.json", "public_dimension_edit": "unsupported"})
    return rows, evidence, {"workflow_inputs.json": evidence_bytes(inputs)}


def claims():
    base = "https://www.steptools.com/stds/step/IS_final_p21e3.html"
    occt = "https://dev.opencascade.org/doc/overview/html/occt_user_guides__modeling_algos.html"
    data = [
        ("part21", "bounded", base, "step_part21.py", "lex_part21", "fixtures/step-part21-source-model", "tests/test_step_part21.py", "Transport control filtering, full schema conformance and external resolution are outside the profile."),
        ("product_paths", "partial", base, "portable_step.py", "inspect_step_semantics", "fixtures/ap-portability", "tests/test_robustness_studies.py", "Recognized AP paths do not establish complete AP conformance or PMI support."),
        ("geometry", "bounded", occt, "public_step.py", "read_step_for_inspection", "fixtures/public-step-corpus", "tests/test_public_step_corpus.py", "Complex face analysis can be partial; persistent face identity is not promised."),
        ("transactions", "supported", occt, "transactional_recompute.py", "TransactionalModel", "fixtures/transactional-recompute", "tests/test_operational_studies.py", "Only valid supported DAGs commit; no native process isolation in the API."),
        ("review", "supported", "docs/cad-v1-support.md", "cad_api.py", "CadWorkspace", "fixtures/cad-review-workflow", "tests/test_release_studies.py", "Scripted usability controls are not a human participant study."),
        ("writer", "bounded", base, "step_writer_modes.py", "write_step", "fixtures/step-writer-modes", "tests/test_operational_studies.py", "Reconstruct mode preserves measured geometry, not original history, attributes or exact topology IDs."),
        ("ai_assistance", "experimental", "fixtures/blinded-assistance/protocol.json", "blinded_assistance.py", "blind_predict", "fixtures/blinded-assistance-evaluation", "tests/test_release_studies.py", "Frozen synthetic holdout; inaccurate high-confidence predictions remain."),
        ("resources", "bounded", "https://docs.python.org/3/library/subprocess.html#subprocess.run", "cad_resources.py", "run_workload", "fixtures/cad-resource-contracts", "tests/test_release_studies.py", "Worker timeout includes startup; estimated memory admission is not an RSS cap."),
        ("authoring_history", "unsupported", base, "step_reconstruction.py", "reconstruct_step", "fixtures/step-reconstruction", "tests/test_operational_studies.py", "No recovered proprietary CAD history; only explicitly selected reconstructed hypotheses."),
    ]
    return [{"claim_id": c, "support": status, "primary_source": source, "implementation": "src/research_notes/" + module,
             "entry_point": symbol, "fixture": fixture, "test": test, "limitation": limitation,
             "evidence": "results/cad_claim_traceability_evidence.json"} for c, status, source, module, symbol, fixture, test, limitation in data]


def freeze_contract():
    from research_notes.cad_api import api_contract
    from research_notes.cad_resources import ResourceLimits
    return {"version": "1.0.0", "api": api_contract(), "worker_limits": asdict(ResourceLimits()),
        "cli_commands": ["open", "candidates", "select", "set", "recompute", "rollback", "status", "compare", "workspace", "export", "quit"],
        "writer_modes": ["preserve", "canonical", "reconstruct"], "worker_outcomes": ["ok", "resource_exhausted", "invalid", "error"],
        "evidence_schema": {"contract": ["version", "study", "control_count", "checks_pass", "boundaries", "numeric_evidence", "regression_check"],
                            "csv": "columns recorded per study; diagnostic JSON data is additive"},
        "compatibility": "v0.87 API version 1.0.0 signatures/envelope/errors unchanged; private modules are research interfaces",
        "license": "PolyForm-Noncommercial-1.0.0", "python_tested": "3.12", "package_extra": "geometry"}


def run_study(name, output, fixtures, *, refresh=False):
    output, fixtures = Path(output), Path(fixtures)
    output.mkdir(parents=True, exist_ok=True)
    if name == "cad_platform_reproducibility":
        rows, detail, inputs = platform_study()
    elif name == "cad_fuzzing":
        from research_notes.cad_fuzz import run_campaign, fuzz_cases
        rows, detail, timings = run_campaign()
        inputs = {"cases.json": evidence_bytes(fuzz_cases()), "minimized.json": evidence_bytes(detail["reduction"])}
        (output / "cad_fuzzing_runtime.json").write_bytes(evidence_bytes(timings))
    elif name == "cad_resource_contracts":
        from research_notes.cad_resources import evaluate_resources, resource_cases
        rows, detail, timings = evaluate_resources()
        inputs = {"workloads.json": evidence_bytes([{ "id": n, "spec": s, "limits": asdict(l), "expected": e} for n, s, l, e in resource_cases()])}
        (output / "cad_resource_measurements.json").write_bytes(evidence_bytes(timings))
        resource_plot(output, timings)
    elif name == "blinded_assistance_evaluation":
        from research_notes.blinded_assistance import evaluate_blinded
        rows, detail, inputs, features, truth = evaluate_blinded()
        inputs.update({"features.json": evidence_bytes(features), "sealed_truth.json": evidence_bytes(truth)})
        detail["adopted_high_confidence_errors"] = [p["sample_id"] for p in detail["predictions"] if p["decision"] != "abstain" and p["prediction"] != p["truth"] and p["confidence"] >= .7]
    elif name == "cad_review_workflow":
        rows, detail, inputs = review_study(output)
    elif name == "cad_end_to_end":
        rows, detail, inputs = end_to_end_study(output)
    elif name == "cad_claim_traceability":
        detail = claims()
        rows = [record(c["claim_id"], (ROOT/c["implementation"]).is_file() and c["entry_point"] in (ROOT/c["implementation"]).read_text(encoding="utf-8") and (ROOT/c["fixture"]).exists() and (ROOT/c["test"]).is_file(), c["support"]) for c in detail]
        inputs = {"claims.json": evidence_bytes(detail)}
    elif name == "cad_contract_freeze":
        detail = freeze_contract()
        from research_notes.cad_api import api_contract
        rows = [record("api_v087_compatible", api_contract() == json.loads((ROOT/"fixtures/stable-cad-api/api_contract.json").read_bytes())),
                record("license_present", (ROOT/"LICENSE").exists() and (ROOT/"LICENSING.md").exists()),
                record("public_source_notices", (ROOT/"fixtures/public-step-corpus/manifest.json").exists()),
                record("contract_no_private_objects", "TopoDS" not in json.dumps(detail))]
        inputs = {"v1_contract.json": evidence_bytes(detail)}
    elif name in {"cad_release_candidate", "cad_stable_release"}:
        from research_notes.cad_platform import runtime_digest
        _, platform, _ = platform_study()
        contracts = [json.loads((output/(n+"_contract.json")).read_bytes()) for n in STUDIES if STUDIES[n] < 99]
        rows = [record("measured_platform_matrix", platform["checks_pass"]), record("tested_runtime_identity", platform["runtime_sha256"] == runtime_digest()),
                record("eight_study_gates", all(c["checks_pass"] for c in contracts)),
                record("published_support_boundary", (ROOT/"docs/cad-v1-support.md").exists())]
        detail = {"runtime_sha256": runtime_digest(), "platforms": platform, "contracts": contracts, "accepted_limitations": LIMITATIONS,
                  "full_suite_ci": "See results/cad-release-validation.json; a local study does not attest to a remote test run."}
        inputs = {"acceptance.json": evidence_bytes({"required_studies": list(STUDIES)[:8], "required_platforms": platform["expected_labels"], "limitations": LIMITATIONS})}
    else:
        raise ValueError("unknown release study")
    version = "v1.0.0" if STUDIES[name] == 100 else f"v0.{STUDIES[name]}.0"
    return finish(output, fixtures, name, rows, detail, inputs, LIMITATIONS, refresh=refresh, version=version)


def resource_plot(output, timings):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for kind in ("syntax", "model", "sketch"):
        points = [r for r in timings if r["control_id"].startswith(kind+"_") and r["status"] == "ok"]
        x = [int(r["control_id"].rsplit("_", 1)[1]) for r in points]
        axes[0].plot(x, [r["wall_seconds"] for r in points], "o-", label=kind)
        axes[1].plot(x, [r["python_peak_bytes"]/1e6 for r in points], "o-", label=kind)
    for ax in axes:
        ax.set_xscale("log"); ax.set_xlabel("Entities / nodes"); ax.legend()
    axes[0].set_ylabel("Seconds including process startup")
    axes[1].set_ylabel("Python allocation peak (MB; excludes native)")
    fig.tight_layout(); fig.savefig(output/"cad_resource_scaling.png", dpi=140); plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("study", choices=[*STUDIES, "all"])
    parser.add_argument("--output-dir", type=Path, default=ROOT/"results")
    parser.add_argument("--fixture-root", type=Path, default=ROOT/"fixtures")
    parser.add_argument("--refresh-fixtures", action="store_true")
    args = parser.parse_args()
    names = STUDIES if args.study == "all" else [args.study]
    passed = True
    for name in names:
        rows = run_study(name, args.output_dir, args.fixture_root/name.replace("_", "-"), refresh=args.refresh_fixtures)
        passed &= all(r["checks_pass"] for r in rows)
        print(name, len(rows), "PASS" if all(r["checks_pass"] for r in rows) else "FAIL")
    return int(not passed)


if __name__ == "__main__":
    raise SystemExit(main())
