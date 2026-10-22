"""Offline dimension-line interpretation, CAD checks, and a local HTML report.

Run from the repository root with python -m experiments.run_drawing_dimension_lines.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

from experiments.run_drawing_to_cad import evaluate, edit_parameters, projection_evaluation
from research_notes.diagnostic_workspace import shape_snapshot
from research_notes.drawing_to_cad import candidate_code, interpret_svg, json_bytes, project_shape
from research_notes.hole_inventory import analyze_step
from research_notes.step_reconstruction import read_step_input

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures/drawing-dimensions"


def analytic_volume(parameters):
    p = parameters
    return p["width"]*p["length"]*p["thickness"]-sum(math.pi*(h["diameter"]/2)**2*p["thickness"] for h in p["holes"])


def compare_edit(step, truth_parameters):
    imported = read_step_input(step)
    inventory = analyze_step(step.read_bytes(), step.name, inspection=True, preview=False)
    rows = sorted(inventory["holes"], key=lambda h: (h["x_mm"], h["y_mm"]))
    expected = sorted(truth_parameters["holes"], key=lambda h: (h["x"], h["y"]))
    errors = [abs(row[k]-value) for row, target in zip(rows, expected) for k, value in (
        ("x_mm", target["x"]), ("y_mm", target["y"]), ("diameter_mm", target["diameter"]), ("depth_mm", truth_parameters["thickness"]))]
    bounds = [imported.metrics.bounds_max[i]-imported.metrics.bounds_min[i] for i in range(3)]
    return imported, {"valid_solid": imported.metrics.analyzer_valid and imported.metrics.solid_count == 1,
                      "hole_count_matches_truth": inventory["hole_count"] == len(expected) and len(rows) == len(expected),
                      "hole_max_abs_error_mm": max(errors, default=0.),
                      "bounds_max_abs_error_mm": max(abs(v-truth_parameters[k]) for v,k in zip(bounds, ("width", "length", "thickness"))),
                      "volume_vs_analytic_abs_error_mm3": abs(imported.metrics.absolute_volume-analytic_volume(truth_parameters))}


def checked_input(case):
    for kind in ("svg", "context"):
        path = FIXTURES / case[kind]
        if hashlib.sha256(path.read_bytes()).hexdigest() != case[kind+"_sha256"]:
            raise ValueError("Input hash mismatch: "+case[kind])
    return (FIXTURES / case["svg"]).read_bytes(), json.loads((FIXTURES / case["context"]).read_text())


def run(output, repeats=2, case_ids=None):
    if type(repeats) is not int or not 1 <= repeats <= 3:
        raise ValueError("repeats must be 1..3")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("Use a new or empty output directory; stale CAD artifacts are not reused")
    output.mkdir(parents=True, exist_ok=True)
    cases = json.loads((FIXTURES / "manifest.json").read_text())["cases"]
    if case_ids is not None:
        if not set(case_ids) <= {c["id"] for c in cases}:
            raise ValueError("Unknown case ID")
        cases = [c for c in cases if c["id"] in case_ids]
    if not cases:
        raise ValueError("No cases selected")
    observations = []
    for case in cases:
        source, context = checked_input(case)
        legacy = interpret_svg(source, context)
        artifact = output / case["id"]
        artifact.mkdir()
        (artifact / "input.svg").write_bytes(source)
        (artifact / "context.json").write_bytes(json_bytes(context))
        trials = []
        for repeat in range(repeats):
            trial = {"repeat": repeat, "worker_inputs": [case["svg"], case["context"]],
                     "ground_truth_supplied_to_worker": False, "passed": False}
            stage = "drawing_recognition"
            try:
                with tempfile.TemporaryDirectory(prefix="dimension-line-worker-") as directory:
                    work = Path(directory)
                    command = [sys.executable, "-m", "research_notes.drawing_dimensions", str(FIXTURES / case["svg"]),
                               str(FIXTURES / case["context"]), "--output-dir", str(work)]
                    worker = subprocess.run(command, cwd=work, capture_output=True, timeout=60)
                    trial["interpretation_exit"] = worker.returncode
                    if worker.returncode:
                        raise RuntimeError(worker.stderr.decode(errors="replace")[-2000:])
                    inference = json.loads((work / "inference.json").read_text())
                    trial.update(status=inference["status"], interpretation_status=inference["status"], reason_code=inference.get("reason_code"),
                                 failure_stage=inference.get("failure_stage"))
                    if repeat == 0:
                        (artifact / "inference.json").write_bytes(json_bytes(inference))
                    if inference["status"] == "withheld":
                        trial["passed"] = case["expected_status"] == "withheld" and inference["reason_code"] == case["expected_reason"]
                    else:
                        stage = "cad_generation"
                        generated = subprocess.run([sys.executable, str(work / "candidate.py"), str(work / "candidate.step")],
                                                   cwd=work, capture_output=True, timeout=60)
                        trial["cad_code_exit"] = generated.returncode
                        if generated.returncode:
                            raise RuntimeError(generated.stderr.decode(errors="replace")[-2000:])
                        # Ground truth is read only after interpretation and code execution.
                        stage = "ground_truth_validation"
                        truth = json.loads((FIXTURES / "evaluation/truth.json").read_text())[case["truth_key"]]
                        truth_step = FIXTURES / "evaluation" / truth["step"]
                        if hashlib.sha256(truth_step.read_bytes()).hexdigest() != truth["sha256"]:
                            raise ValueError("Truth STEP hash mismatch")
                        stage = "kernel_geometry_evaluation"
                        imported, metrics = evaluate(work / "candidate.step", truth, truth_step)
                        stage = "reprojection_evaluation"
                        projected = project_shape(imported.shape)
                        projection = projection_evaluation(inference["views"], projected)
                        trial.update(metrics=metrics, projection=projection)
                        edited = edit_parameters(inference["parameters"])
                        (work / "edited.py").write_text(candidate_code(edited, inference["source_sha256"]), encoding="utf-8")
                        stage = "cad_edit_generation"
                        changed = subprocess.run([sys.executable, str(work / "edited.py"), str(work / "edited.step")],
                                                 cwd=work, capture_output=True, timeout=60)
                        trial["edit_code_exit"] = changed.returncode
                        if changed.returncode:
                            raise RuntimeError(changed.stderr.decode(errors="replace")[-2000:])
                        stage = "edit_evaluation"
                        edited_truth = edit_parameters(truth["parameters"])
                        edit_imported, edit_metrics = compare_edit(work / "edited.step", edited_truth)
                        trial["edit"] = edit_metrics
                        trial["initial_reconstruction_passed"] = all((
                            metrics["valid_solid"], metrics["step_read_success"], metrics["hole_count_matches_truth"], metrics["hole_dimensions_compared"],
                            metrics["bounds_max_abs_error_mm"] <= 1e-6, metrics["hole_dimension_max_abs_error_mm"] <= 1e-6,
                            metrics["volume_vs_analytic_abs_error_mm3"] <= 1e-5, metrics["area_vs_analytic_abs_error_mm2"] <= 1e-5,
                            metrics["same_kernel_volume_iou"] >= 1-1e-8,
                            max(v["sampled_symmetric_max_mm"] for v in projection.values()) <= .02))
                        trial["passed"] = case["expected_status"] == "candidate" and all((
                            trial["initial_reconstruction_passed"], edit_metrics["valid_solid"], edit_metrics["hole_count_matches_truth"],
                            edit_metrics["hole_max_abs_error_mm"] <= 1e-6, edit_metrics["bounds_max_abs_error_mm"] <= 1e-6,
                            edit_metrics["volume_vs_analytic_abs_error_mm3"] <= 1e-5))
                        trial["failure_stage"] = None if trial["passed"] else "edit_evaluation" if trial["initial_reconstruction_passed"] else "reconstruction_evaluation"
                        if repeat == 0:
                            for name in ("candidate.py", "candidate.step", "model.json", "edited.py", "edited.step"):
                                (artifact / name).write_bytes((work / name).read_bytes())
                            inventory = analyze_step((work / "candidate.step").read_bytes(), inspection=True, preview=False)
                            comparison = {"truth_parameters": truth["parameters"], "recovered_parameters": inference["parameters"],
                                          "measured_holes": inventory["holes"], "edited_parameters": edited,
                                          "edited_truth_parameters": edited_truth, "metrics": metrics, "edit_metrics": edit_metrics,
                                          "views": inference["views"], "reprojection": projected, "projection_metrics": projection}
                            (artifact / "comparison.json").write_bytes(json_bytes(comparison))
                            previews = {"original": shape_snapshot(imported.shape), "edited": shape_snapshot(edit_imported.shape)}
                            (artifact / "preview.json").write_text(json.dumps(previews, separators=(",", ":"), allow_nan=False)+"\n")
            except Exception as error:
                trial.update(status="failed", failure_stage=stage, error_type=type(error).__name__, detail=str(error))
            trials.append(trial)
        observation = {**case, "legacy_on_same_input": {"status": legacy["status"], "reason_code": legacy.get("reason_code")},
                       "trials": trials, "passed": all(t["passed"] for t in trials)}
        observations.append(observation)
        print(json.dumps({"case": case["id"], "passed": observation["passed"], "status": trials[0].get("status"),
                          "reason": trials[0].get("reason_code")}), flush=True)
    positives = [o for o in observations if o["expected_status"] == "candidate"]
    negatives = [o for o in observations if o["expected_status"] == "withheld"]
    paths = [Path(__file__), ROOT / "src/research_notes/drawing_dimensions.py", ROOT / "src/research_notes/drawing_dimension_report.py",
             ROOT / "src/research_notes/drawing_to_cad.py", ROOT / "experiments/run_drawing_to_cad.py",
             FIXTURES / "manifest.json", FIXTURES / "evaluation/truth.json"]
    report = {"study": "Ordinary dimension graphics to parametric CAD", "schema_version": "1.0.0", "date": "2026-10-22",
              "repeats": repeats, "observations": observations, "passed": all(o["passed"] for o in observations),
              "summary": {"inputs": len(observations), "candidate_inputs": len(positives), "candidate_successes": sum(o["passed"] for o in positives),
                          "withheld_controls": len(negatives), "correct_withholds": sum(o["passed"] for o in negatives),
                          "false_confirmations": sum(any(t.get("interpretation_status") == "candidate" for t in o["trials"]) for o in negatives),
                          "legacy_candidates_on_same_positive_inputs": sum(o["legacy_on_same_input"]["status"] == "candidate" for o in positives)},
              "runtime": {"python": platform.python_version(), "platform": platform.platform(),
                          "cadquery_ocp": importlib.metadata.version("cadquery-ocp"), "package_version": importlib.metadata.version("research-notes")},
              "thresholds": {"dimension_mm": 1e-6, "analytic_volume_mm3": 1e-5, "analytic_area_mm2": 1e-5,
                             "same_kernel_iou_min": 1-1e-8, "sampled_projection_mm": .02},
              "hashes": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
              "ai_model_calls": 0, "claim_boundary": "Authored development controls under explicit family, frame, unit and view assumptions; not OCR, drafting-standard compliance, real-drawing accuracy or a held-out benchmark."}
    (output / "results.json").write_bytes(json_bytes(report))
    with (output / "summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("id", "expected_status", "observed_status", "reason_code", "passed"))
        for o in observations:
            writer.writerow((o["id"], o["expected_status"], o["trials"][0].get("status"), o["trials"][0].get("reason_code"), o["passed"]))
    from research_notes.drawing_dimension_report import write_report
    write_report(output)
    print(json.dumps(report["summary"], indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--case", action="append", dest="case_ids")
    args = parser.parse_args()
    raise SystemExit(0 if run(args.output_dir, args.repeats, args.case_ids)["passed"] else 1)
