"""Offline SVG -> editable recipe -> STEP -> HLR/geometry evaluation experiment."""
from __future__ import annotations

import argparse
import copy
import csv
from dataclasses import asdict
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

import numpy as np
import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt

from research_notes.drawing_to_cad import json_bytes, candidate_code, feature_model, project_shape
from research_notes.modeling_common import measure_shape
from research_notes.parametric_features import shape_difference_volume
from research_notes.step_reconstruction import read_step_input
from research_notes.hole_inventory import analyze_step

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures/drawing-to-cad"
GEOMETRY_TOL = 1e-6
PROJECTION_TOL = .02


def drawing_polylines(view):
    u, v = view["extent_mm"]
    lines = [[[0,0],[u,0]], [[u,0],[u,v]], [[u,v],[0,v]], [[0,v],[0,0]], *view["hidden_lines"]]
    for circle in view["circles"]:
        cx, cy = circle["center"]
        lines.append([[cx+circle["radius"]*np.cos(a), cy+circle["radius"]*np.sin(a)] for a in np.linspace(0,2*np.pi,129)])
    return lines


def directed_distance(first, second):
    points = np.concatenate([np.asarray(line) for line in first])
    starts = np.concatenate([np.asarray(line[:-1]) for line in second])
    ends = np.concatenate([np.asarray(line[1:]) for line in second])
    delta = ends-starts
    length = np.einsum("ij,ij->i", delta, delta)
    distances = []
    for block in np.array_split(points, max(1, len(points)//128)):
        relative = block[:,None,:]-starts[None,:,:]
        t = np.clip(np.einsum("nmi,mi->nm", relative, delta) / np.maximum(length,1e-30),0,1)
        distances.extend(np.sqrt(np.sum((relative-t[:,:,None]*delta[None,:,:])**2,axis=2)).min(axis=1))
    return float(max(distances)), float(np.sqrt(np.mean(np.asarray(distances)**2)))


def projection_evaluation(views, projected):
    observations = {}
    for name in ("front", "top", "right"):
        drawing = drawing_polylines(views[name])
        cad = projected[name]["visible"]+projected[name]["hidden"]
        forward = directed_distance(drawing, cad)
        reverse = directed_distance(cad, drawing)
        observations[name] = {"drawing_to_cad_max_mm":forward[0], "cad_to_drawing_max_mm":reverse[0],
            "drawing_to_cad_rms_mm":forward[1], "cad_to_drawing_rms_mm":reverse[1],
            "sampled_symmetric_max_mm":max(forward[0],reverse[0])}
    return observations


def compare_figure(views, projected, output, title):
    fig, axes = plt.subplots(1,3,figsize=(12,4),layout="constrained")
    for name, ax in zip(("front","top","right"),axes):
        for line in drawing_polylines(views[name]):
            xy=np.asarray(line);ax.plot(xy[:,0],xy[:,1],color="#98a5ab",linewidth=3,alpha=.6)
        for visibility, style in (("visible","-"),("hidden","--")):
            for line in projected[name][visibility]:
                xy=np.asarray(line);ax.plot(xy[:,0],xy[:,1],style,color="#146b8c",linewidth=1)
        ax.set_title(name.title());ax.set_aspect("equal");ax.set_xlabel("mm");ax.set_ylabel("mm");ax.margins(.15)
    fig.suptitle(title+" | grey: input geometry, blue: actual OCCT HLR reprojection")
    fig.savefig(output,dpi=160)
    plt.close(fig)


def evaluate(step_path, truth, truth_step):
    imported = read_step_input(step_path)
    reference = read_step_input(truth_step)
    measured = imported.metrics
    difference = shape_difference_volume(imported.shape, reference.shape)
    intersection = (measured.absolute_volume+reference.metrics.absolute_volume-difference)/2
    union = measured.absolute_volume+reference.metrics.absolute_volume-intersection
    inventory = analyze_step(step_path.read_bytes(), step_path.name, inspection=True, preview=False)
    actual = sorted(inventory["holes"],key=lambda h:(h["x_mm"],h["y_mm"]))
    expected = sorted(truth["parameters"]["holes"],key=lambda h:(h["x"],h["y"]))
    errors = []
    for h, target in zip(actual,expected):
        errors.extend(abs(h[k]-value) for k,value in (("x_mm",target["x"]),("y_mm",target["y"]),
            ("diameter_mm",target["diameter"]),("depth_mm",truth["parameters"]["thickness"])))
    bounds = [measured.bounds_max[i]-measured.bounds_min[i] for i in range(3)]
    bounds_error = max(abs(a-truth["parameters"][k]) for a,k in zip(bounds,("width","length","thickness")))
    result = {"valid_solid":measured.analyzer_valid and measured.solid_count==1,"step_read_success":True,
        "volume_mm3":measured.absolute_volume,"surface_area_mm2":measured.surface_area,
        "volume_vs_analytic_abs_error_mm3":abs(measured.absolute_volume-truth["analytic_volume"]),
        "area_vs_analytic_abs_error_mm2":abs(measured.surface_area-truth["analytic_area"]),
        "bounds_max_abs_error_mm":bounds_error,"material_symmetric_difference_mm3":difference,
        "same_kernel_volume_iou":intersection/union,"hole_count_matches_truth":inventory["hole_count"]==len(expected),
        "hole_dimension_max_abs_error_mm":max(errors,default=0.),"hole_dimensions_compared":len(actual)==len(expected)}
    return imported, result


def edit_parameters(parameters, target="leftmost"):
    values=copy.deepcopy(parameters)
    values["width"]+=5
    values["thickness"]+=2
    if values["holes"]:
        index = 0 if target == "sequence_first" else min(range(len(values["holes"])),key=lambda i:(values["holes"][i]["x"],values["holes"][i]["y"]))
        values["holes"][index]["diameter"]+=1
        values["holes"][index]["x"]+=1
    return values


def run(output: Path, repeats=2, *, edit_target="leftmost", case_ids=None):
    if type(repeats) is not int or not 1<=repeats<=3 or edit_target not in ("leftmost","sequence_first"):
        raise ValueError("invalid repeat count or edit target")
    output.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((FIXTURES/"manifest.json").read_text())
    observations=[]
    for case in manifest["cases"]:
        if case_ids is not None and case["id"] not in case_ids:
            continue
        for relative,key in ((case["svg"],"svg_sha256"),(case["context"],"context_sha256")):
            if hashlib.sha256((FIXTURES/relative).read_bytes()).hexdigest()!=case[key]:
                raise ValueError("Input changed: "+relative)
        trials=[]
        artifact=output/case["id"]
        artifact.mkdir(exist_ok=True)
        for repeat in range(repeats):
            # Worker receives only drawing, human context and an empty working directory.
            with tempfile.TemporaryDirectory(prefix="drawing-cad-worker-") as directory:
                work=Path(directory)
                command=[sys.executable,"-m","research_notes.drawing_to_cad",str(FIXTURES/case["svg"]),str(FIXTURES/case["context"]),"--output-dir",str(work)]
                inference_run=subprocess.run(command,cwd=work,capture_output=True,timeout=60)
                trial={"repeat":repeat,"interpretation_exit":inference_run.returncode,
                    "worker_inputs":[case["svg"],case["context"]],"ground_truth_supplied_to_worker":False}
                if inference_run.returncode!=0:
                    trial.update(status="failed",failure_stage="drawing_recognition",detail=inference_run.stderr.decode(errors="replace")[-2000:])
                    trials.append(trial);continue
                inference=json.loads((work/"inference.json").read_text())
                trial.update(status=inference["status"],reason_code=inference.get("reason_code"),failure_stage=inference.get("failure_stage"))
                if repeat==0:
                    (artifact/"inference.json").write_bytes(json_bytes(inference))
                if inference["status"]=="withheld":
                    trials.append(trial);continue
                code_run=subprocess.run([sys.executable,str(work/"candidate.py"),str(work/"candidate.step")],cwd=work,capture_output=True,timeout=60)
                trial["cad_code_exit"]=code_run.returncode
                if code_run.returncode!=0:
                    trial.update(status="failed",failure_stage="cad_generation",detail=code_run.stderr.decode(errors="replace")[-2000:])
                    trials.append(trial);continue
                evaluation_stage="ground_truth_validation"
                try:
                    # Evaluation-only files are opened only after drawing interpretation/code execution.
                    truth=json.loads((FIXTURES/"evaluation/truth.json").read_text())[case["truth_key"]]
                    truth_path=FIXTURES/"evaluation"/truth["step"]
                    if hashlib.sha256(truth_path.read_bytes()).hexdigest()!=truth["sha256"]:
                        raise ValueError("Evaluation STEP hash mismatch")
                    evaluation_stage="kernel_geometry_evaluation"
                    imported,metrics=evaluate(work/"candidate.step",truth,truth_path)
                    evaluation_stage="reprojection_evaluation"
                    projected=project_shape(imported.shape)
                    projection=projection_evaluation(inference["views"],projected)
                    trial.update(metrics=metrics,projection=projection)
                    edited=edit_parameters(inference["parameters"],edit_target)
                    (work/"edited.py").write_text(candidate_code(edited,inference["source_sha256"]),encoding="utf-8")
                    evaluation_stage="cad_edit_generation"
                    edit_run=subprocess.run([sys.executable,str(work/"edited.py"),str(work/"edited.step")],cwd=work,capture_output=True,timeout=60)
                    trial["edit_code_exit"]=edit_run.returncode
                    if edit_run.returncode!=0:
                        raise RuntimeError("edited CAD code failed: "+edit_run.stderr.decode(errors="replace")[-1500:])
                    edit_imported=read_step_input(work/"edited.step")
                    # Independent analytic check uses the evaluation recipe with the declared edit policy.
                    expected_edit=edit_parameters(truth["parameters"],edit_target)
                    v=expected_edit["width"]*expected_edit["length"]*expected_edit["thickness"]-sum(np.pi*(h["diameter"]/2)**2*expected_edit["thickness"] for h in expected_edit["holes"])
                    trial["edit_valid_solid"]=edit_imported.metrics.analyzer_valid and edit_imported.metrics.solid_count==1
                    trial["edit_volume_vs_analytic_abs_error_mm3"]=abs(edit_imported.metrics.absolute_volume-v)
                    edit_inventory=analyze_step((work/"edited.step").read_bytes(),"edited.step",inspection=True,preview=False)
                    edit_rows=sorted(edit_inventory["holes"],key=lambda h:(h["x_mm"],h["y_mm"]))
                    edit_truth=sorted(expected_edit["holes"],key=lambda h:(h["x"],h["y"]))
                    edit_errors=[abs(h[k]-value) for h,target in zip(edit_rows,edit_truth) for k,value in (
                        ("x_mm",target["x"]),("y_mm",target["y"]),("diameter_mm",target["diameter"]),("depth_mm",expected_edit["thickness"]))]
                    trial["edit_hole_count_matches_truth"]=edit_inventory["hole_count"]==len(edit_truth)
                    trial["edit_hole_max_abs_error_mm"]=max(edit_errors,default=0.)
                    initial_passed=all((metrics["valid_solid"],metrics["hole_count_matches_truth"],metrics["hole_dimensions_compared"],
                        metrics["bounds_max_abs_error_mm"]<=GEOMETRY_TOL, metrics["hole_dimension_max_abs_error_mm"]<=GEOMETRY_TOL,
                        metrics["volume_vs_analytic_abs_error_mm3"]<=1e-5, metrics["area_vs_analytic_abs_error_mm2"]<=1e-5,
                        metrics["same_kernel_volume_iou"]>=1-1e-8,
                        max(p["sampled_symmetric_max_mm"] for p in projection.values())<=PROJECTION_TOL))
                    trial["initial_reconstruction_passed"]=initial_passed
                    trial["passed"]=all((initial_passed,trial["edit_valid_solid"],trial["edit_volume_vs_analytic_abs_error_mm3"]<=1e-5,
                        trial["edit_hole_count_matches_truth"],trial["edit_hole_max_abs_error_mm"]<=GEOMETRY_TOL))
                    if not trial["passed"]:
                        trial["failure_stage"]="edit_evaluation" if initial_passed else "reconstruction_evaluation"
                    if repeat==0:
                        for name in ("candidate.py","model.json","candidate.step","edited.py","edited.step"):
                            (artifact/name).write_bytes((work/name).read_bytes())
                        (artifact/"edited-parameters.json").write_bytes(json_bytes(edited))
                        (artifact/"reprojection.json").write_bytes(json_bytes(projected))
                        if case["id"] in ("one_third","two_third"):
                            compare_figure(inference["views"],projected,artifact/"comparison.png",case["id"])
                except Exception as error:
                    trial.update(status="failed",failure_stage=evaluation_stage,error_type=type(error).__name__,detail=str(error))
                trials.append(trial)
        positive=case["expected_status"]=="candidate"
        passed=all(t.get("passed",False) if positive else t["status"]=="withheld" and t["reason_code"]==case["expected_reason"] for t in trials)
        observations.append({"id":case["id"],"family_id":case["family_id"],"expected_status":case["expected_status"],
                             "trials":trials,"passed":passed})
        print(json.dumps({"case":case["id"],"passed":passed,"status":trials[0]["status"]}),flush=True)
    positive=[o for o in observations if o["expected_status"]=="candidate"]
    withheld=[o for o in observations if o["expected_status"]=="withheld"]
    if not observations:
        raise ValueError("no matching cases")
    report={"study":"2D Engineering Drawing to Parametric 3D CAD Reconstruction","schema_version":"1.0.0","date":"2026-10-22",
        "edit_target_policy":edit_target,
        "method":"AI-free bounded SVG geometry + explicit annotation grammar","observations":observations,"repeats":repeats,
        "summary":{"planned_inputs":len(observations),"candidate_inputs":len(positive),"withheld_controls":len(withheld),
            "candidate_successes":sum(o["passed"] for o in positive),"correct_withholds":sum(o["passed"] for o in withheld),
            "false_confirmations_on_withheld_controls":sum(any(t["status"]=="candidate" for t in o["trials"]) for o in withheld)},
        "runtime":{"python":platform.python_version(),"platform":platform.platform(),"cadquery_ocp":importlib.metadata.version("cadquery-ocp"),
                   "package_version":importlib.metadata.version("research-notes")},
        "thresholds":{"dimension_mm":GEOMETRY_TOL,"analytic_volume_mm3":1e-5,"analytic_area_mm2":1e-5,"volume_iou_min":1-1e-8,"sampled_projection_mm":PROJECTION_TOL},
        "hashes":{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (FIXTURES/"manifest.json",FIXTURES/"evaluation/truth.json",Path(__file__),ROOT/"src/research_notes/drawing_to_cad.py")},
        "passed":all(o["passed"] for o in observations),"ai_model_calls":0,"external_datasets_redistributed":False,
        "claim_boundary":"Authored development controls under explicit human family/view/unit assumptions, not general drawing reconstruction, recovered original history, AI comparison or real-drawing accuracy."}
    (output/"results.json").write_bytes(json_bytes(report))
    with (output/"summary.csv").open("w",newline="",encoding="utf-8") as stream:
        writer=csv.DictWriter(stream,fieldnames=("id","family_id","expected_status","observed_status","reason_code","passed"))
        writer.writeheader()
        for o in observations:
            writer.writerow({k:o[k] for k in ("id","family_id","expected_status","passed")} | {"observed_status":o["trials"][0]["status"],"reason_code":o["trials"][0].get("reason_code")})
    print(json.dumps(report["summary"],indent=2))
    return report


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir",type=Path,default=ROOT/"results/drawing-to-cad")
    parser.add_argument("--repeats",type=int,default=2)
    parser.add_argument("--edit-target",choices=("leftmost","sequence_first"),default="leftmost")
    parser.add_argument("--case",action="append",dest="case_ids")
    args=parser.parse_args()
    if not 1<=args.repeats<=3:
        parser.error("repeats must be 1..3")
    raise SystemExit(0 if run(args.output_dir,args.repeats,edit_target=args.edit_target,case_ids=args.case_ids)["passed"] else 1)
