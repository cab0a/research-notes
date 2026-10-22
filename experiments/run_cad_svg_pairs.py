"""Paired native SVG/DXF reconstruction, independent workers and CAD evaluation.

Run from the repository root with python -m experiments.run_cad_svg_pairs.
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
FIXTURES = ROOT / "fixtures/cad-svg-dxf"
EVALUATION = ROOT / "fixtures/cad-drawing-exports/evaluation"


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
    for kind in ("drawing", "svg", "context"):
        path = FIXTURES / case[kind]
        if hashlib.sha256(path.read_bytes()).hexdigest() != case[kind+"_sha256"]:
            raise ValueError("Input hash mismatch: "+case[kind])
    return (FIXTURES / case["drawing"]).read_bytes(), json.loads((FIXTURES / case["context"]).read_text())


def raw_projection_evaluation(inference, projected):
    """Sample native cubic contours, not just fitted exact circles."""
    from experiments.run_drawing_to_cad import directed_distance, drawing_polylines
    rows = {}
    for role in ("front", "top", "right"):
        drawing = inference.get("raw_drawing_polylines_mm", {}).get(role) or drawing_polylines(inference["views"][role])
        cad = projected[role]["visible"] + projected[role]["hidden"]
        forward = directed_distance(drawing, cad)
        reverse = directed_distance(cad, drawing)
        rows[role] = {"sampled_symmetric_max_mm": max(forward[0], reverse[0]),
                      "drawing_to_cad_max_mm": forward[0], "cad_to_drawing_max_mm": reverse[0],
                      "drawing_samples": sum(map(len, drawing)),
                      "method": "native cubic samples vs HLR polylines" if inference.get("input_format") == "svg" else "DXF primitives vs HLR polylines"}
    return rows


def compare_pairs(output, observations):
    from research_notes.parametric_features import shape_difference_volume
    groups = {}
    for o in observations:
        groups.setdefault(o["pair_id"], {})[o["format"]] = o
    rows = []
    for pair_id, formats in groups.items():
        if set(formats) != {"svg", "dxf"}:
            raise ValueError("Both formats are required for pair evaluation")
        inf = {f: json.loads((output/o["id"]/"inference.json").read_text()) for f, o in formats.items()}
        row = {"pair_id": pair_id, "statuses": {f: i["status"] for f, i in inf.items()}, "passed": False}
        if all(i["status"] == "candidate" for i in inf.values()):
            if not all((output/o["id"]/name).exists() for o in formats.values() for name in ("candidate.step", "edited.step")):
                row["detail"] = "A candidate failed CAD generation/evaluation; pair geometry unavailable"
                rows.append(row)
                continue
            def values(p):
                return [p[k] for k in ("width", "length", "thickness")] + [
                    h[k] for h in sorted(p["holes"], key=lambda h: (h["x"], h["y"])) for k in ("x", "y", "diameter")]
            a, b = (values(inf[f]["parameters"]) for f in ("svg", "dxf"))
            error = max((abs(x-y) for x,y in zip(a,b)), default=0.)
            row.update(parameter_max_abs_difference_mm=error, parameter_count_matches=len(a)==len(b))
            pair_geometry = {}
            for name in ("candidate", "edited"):
                shapes = [read_step_input(output/formats[f]["id"]/(name+".step")) for f in ("svg", "dxf")]
                difference = shape_difference_volume(shapes[0].shape, shapes[1].shape)
                total = sum(s.metrics.absolute_volume for s in shapes)
                intersection = (total-difference)/2; union = total-intersection
                pair_geometry[name] = {"material_symmetric_difference_mm3": difference, "same_kernel_volume_iou": intersection/union}
            row["geometry"] = pair_geometry
            row["passed"] = len(a)==len(b) and error<=1e-6 and all(v["same_kernel_volume_iou"]>=1-1e-8 for v in pair_geometry.values())
        elif all(i["status"] == "withheld" for i in inf.values()):
            row["reasons"] = {f: i["reason_code"] for f,i in inf.items()}
            row["passed"] = len(set(row["reasons"].values())) == 1
        row["passed"] = row["passed"] and all(o["passed"] for o in formats.values())
        rows.append(row)
    return rows


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
        from research_notes.cad_drawing_import import interpret_cad_drawing
        old_context = {**context, "view_roles": {"top": "Top", "front": "Front", "right": "Right"}}
        old_context.pop("drawing_group", None)
        legacy = interpret_cad_drawing(source, old_context, case["format"])
        artifact = output / case["id"]
        artifact.mkdir()
        (artifact / "input.svg").write_bytes((FIXTURES / case["svg"]).read_bytes())
        (artifact / ("input." + case["format"])).write_bytes(source)
        (artifact / "context.json").write_bytes(json_bytes(context))
        trials = []
        for repeat in range(repeats):
            trial = {"repeat": repeat, "worker_inputs": [case["drawing"], case["context"]],
                     "ground_truth_supplied_to_worker": False, "passed": False}
            stage = "drawing_recognition"
            try:
                with tempfile.TemporaryDirectory(prefix="cad-drawing-worker-") as directory:
                    work = Path(directory)
                    command = [sys.executable, "-m", ("research_notes.cad_svg_import" if case["format"] == "svg" else "research_notes.cad_drawing_import"), str(FIXTURES / case["drawing"]),
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
                        truth = json.loads((EVALUATION / "truth.json").read_text())[case["truth_key"]]
                        truth_step = EVALUATION / truth["step"]
                        if hashlib.sha256(truth_step.read_bytes()).hexdigest() != truth["sha256"]:
                            raise ValueError("Truth STEP hash mismatch")
                        stage = "kernel_geometry_evaluation"
                        imported, metrics = evaluate(work / "candidate.step", truth, truth_step)
                        stage = "reprojection_evaluation"
                        projected = project_shape(imported.shape)
                        projection = projection_evaluation(inference["views"], projected)
                        raw_projection = raw_projection_evaluation(inference, projected)
                        trial["raw_projection"] = raw_projection
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
                            max(v["sampled_symmetric_max_mm"] for v in projection.values()) <= .02,
                            max(v["sampled_symmetric_max_mm"] for v in raw_projection.values()) <= .02))
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
                                          "views": inference["views"], "reprojection": projected, "projection_metrics": projection,
                                          "raw_projection_metrics": raw_projection}
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
    paths = [Path(__file__), ROOT / "src/research_notes/cad_drawing_import.py", ROOT / "src/research_notes/cad_svg_report.py",
             ROOT / "src/research_notes/cad_svg_import.py", ROOT / "src/research_notes/svg_drawing_graphics.py",
             ROOT / "experiments/prepare_cad_svg_pairs.py",
             ROOT / "src/research_notes/drawing_to_cad.py", ROOT / "experiments/run_drawing_to_cad.py",
             FIXTURES / "manifest.json", EVALUATION / "truth.json"]
    report = {"study": "Native FreeCAD SVG/DXF equivalence", "schema_version": "1.0.0", "date": "2026-10-22",
              "repeats": repeats, "observations": observations, "passed": all(o["passed"] for o in observations),
              "summary": {"inputs": len(observations), "candidate_inputs": len(positives), "candidate_successes": sum(o["passed"] for o in positives),
                          "withheld_controls": len(negatives), "correct_withholds": sum(o["passed"] for o in negatives),
                          "false_confirmations": sum(any(t.get("interpretation_status") == "candidate" for t in o["trials"]) for o in negatives),
                          "legacy_candidates_on_same_positive_inputs": sum(o["legacy_on_same_input"]["status"] == "candidate" for o in positives)},
              "runtime": {"python": platform.python_version(), "platform": platform.platform(),
                          "ezdxf": importlib.metadata.version("ezdxf"), "cadquery_ocp": importlib.metadata.version("cadquery-ocp"), "package_version": importlib.metadata.version("research-notes")},
              "thresholds": {"dimension_mm": 1e-6, "analytic_volume_mm3": 1e-5, "analytic_area_mm2": 1e-5,
                             "same_kernel_iou_min": 1-1e-8, "sampled_projection_mm": .02},
              "hashes": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
              "ai_model_calls": 0, "claim_boundary": "Own authored FreeCAD exports, one plate family under human priors; not customer drawings, independent-kernel validation or held-out accuracy."}
    report["summary"]["by_format"] = {f: {"inputs": sum(o["format"] == f for o in observations),
        "candidates": sum(o["format"] == f and o["trials"][0].get("interpretation_status") == "candidate" for o in observations),
        "positive_successes": sum(o["format"] == f and o["expected_status"] == "candidate" and o["passed"] for o in observations),
        "withheld": sum(o["format"] == f and o["trials"][0].get("status") == "withheld" for o in observations)} for f in ("dxf", "svg")}
    report["pairs"] = compare_pairs(output, observations)
    report["summary"]["pairs"] = len(report["pairs"])
    report["summary"]["matching_pairs"] = sum(p["passed"] for p in report["pairs"])
    report["passed"] = report["passed"] and all(p["passed"] for p in report["pairs"])
    report["source_exporter"] = {"FreeCAD": "1.1.4", "OCCT": "7.8.1", "claim": "different CAD path and OCCT version; same kernel family"}
    (output / "results.json").write_bytes(json_bytes(report))
    with (output / "pairs.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("pair_id", "svg_status", "dxf_status", "parameter_max_abs_difference_mm", "original_iou", "edited_iou", "passed"))
        for p in report["pairs"]:
            writer.writerow((p["pair_id"], p["statuses"]["svg"], p["statuses"]["dxf"], p.get("parameter_max_abs_difference_mm"),
                             p.get("geometry", {}).get("candidate", {}).get("same_kernel_volume_iou"),
                             p.get("geometry", {}).get("edited", {}).get("same_kernel_volume_iou"), p["passed"]))
    with (output / "summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("id", "expected_status", "observed_status", "reason_code", "passed"))
        for o in observations:
            writer.writerow((o["id"], o["expected_status"], o["trials"][0].get("status"), o["trials"][0].get("reason_code"), o["passed"]))
    from research_notes.cad_svg_report import write_report
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
