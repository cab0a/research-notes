"""Measured CAD contracts across recorded OS environments, with no simulated runners."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

from research_notes.robustness_studies import ROOT, evidence_bytes

PLATFORM_LABELS = ("linux-x64", "windows-x64", "macos-x64", "macos-arm64")


def runtime_digest(root=ROOT):
    """Code/dependency identity excludes generated reports and documentation."""
    digest = hashlib.sha256()
    paths = sorted((root / "src/research_notes").glob("*.py")) + [root / "pyproject.toml"]
    for path in paths:
        digest.update(path.relative_to(root).as_posix().encode() + b"\0" + path.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return digest.hexdigest()


def environment_record(label):
    import numpy
    import OCP
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    return {"label": label, "system": platform.system(), "release": platform.release(),
        "machine": platform.machine(), "python": platform.python_version(), "numpy": numpy.__version__,
        "ocp": OCP.__version__, "cadquery_ocp": importlib.metadata.version("cadquery-ocp"),
        "source_commit": head, "runtime_sha256": runtime_digest(),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"), "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "runner_image": os.environ.get("ImageOS"), "runner_image_version": os.environ.get("ImageVersion")}


def observe_platform(label, output):
    from research_notes.interoperability_benchmark import evaluate_interoperability
    from research_notes.operational_studies import selected_workspace, HOLE
    from research_notes.parametric_features import rectangle_solution, circular_solution
    from research_notes.step_writer_modes import canonical_step
    from research_notes.engineering_analysis import proximity
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    rows, raw, inputs, _ = evaluate_interoperability()
    observations = {"interop_classifications": rows, "inputs": inputs, "geometry": {}}
    for case in raw:
        routes = case["routes"]
        if "stepcontrol" in routes:
            observations["geometry"][case["control_id"]] = {
                route: {"metrics": routes[route].get("metrics"), "attributes": routes[route].get("attributes")}
                for route in ("stepcontrol", "stepcaf")}
    workspace = selected_workspace()
    before = workspace.status().data["transaction"]["committed_fingerprint"]
    workspace.edit("feature", "radius", 1.3, expected_revision=workspace.revision_token)
    committed = workspace.recompute(expected_revision=workspace.revision_token)
    comparison = workspace.compare().data
    with tempfile.TemporaryDirectory() as temporary:
        exported = workspace.export_step(Path(temporary) / "edited.step")
    workspace.edit("feature", "radius", 30., expected_revision=workspace.revision_token)
    aborted = workspace.recompute(expected_revision=workspace.revision_token)
    workspace.rollback(expected_revision=workspace.revision_token)
    observations["modeling"] = {"initial_fingerprint": before, "commit_status": committed.status,
        "abort_status": aborted.status, "comparison": comparison,
        "rollback_pending": workspace.status().data["transaction"]["draft_pending"],
        "export_checks": exported.data["checks"]}
    observations["sketches"] = [{"status": s.status, "satisfied": s.satisfied, "dof": s.local_degrees_of_freedom}
                                for s in (rectangle_solution(12., 10.), circular_solution(3., 3., 1.3))]
    observations["canonical_sha256"] = hashlib.sha256(canonical_step(HOLE.read_bytes())).hexdigest()
    base = BRepPrimAPI_MakeBox(2., 2., 2.).Shape()
    other = BRepPrimAPI_MakeBox(gp_Pnt(2. + 5e-8, 0, 0), 2., 2., 2.).Shape()
    observations["tied_proximity"] = proximity(base, other)
    checks = all(r["checks_pass"] for r in rows) and committed.status == "committed" and aborted.status == "aborted"
    report = {"contract_version": "1.0.0", "environment": environment_record(label), "checks_pass": checks,
              "observations": observations, "numeric_policy": {"relative": 1e-6, "absolute": 1e-7},
              "scope": "declared parser/import/model/sketch/writer/proximity controls; no arbitrary CAD equivalence"}
    (output / "cad_platform.json").write_bytes(evidence_bytes(report))
    return report


def numeric_differences(actual, expected, path="", *, relative=1e-6, absolute=1e-7):
    differences = []
    if isinstance(expected, dict) and isinstance(actual, dict):
        if actual.keys() != expected.keys():
            return [{"path": path, "kind": "keys", "actual": sorted(actual), "expected": sorted(expected)}]
        for key in expected:
            differences.extend(numeric_differences(actual[key], expected[key], path + "/" + key, relative=relative, absolute=absolute))
    elif isinstance(expected, list) and isinstance(actual, list):
        if len(actual) != len(expected):
            return [{"path": path, "kind": "length", "actual": len(actual), "expected": len(expected)}]
        for i, (a, b) in enumerate(zip(actual, expected)):
            differences.extend(numeric_differences(a, b, path + "/" + str(i), relative=relative, absolute=absolute))
    elif isinstance(expected, float) and isinstance(actual, (int, float)) and not isinstance(actual, bool):
        if not math.isfinite(actual) or not math.isclose(actual, expected, rel_tol=relative, abs_tol=absolute):
            differences.append({"path": path, "kind": "numeric", "actual": actual, "expected": expected})
    elif type(actual) is not type(expected) or actual != expected:
        differences.append({"path": path, "kind": "value", "actual": actual, "expected": expected})
    return differences


def aggregate_platforms(paths, *, expected_labels=PLATFORM_LABELS):
    reports = [json.loads(Path(p).read_text(encoding="utf-8")) for p in paths]
    by_label = {}
    for report in reports:
        label = report["environment"]["label"]
        if label in by_label:
            raise ValueError("duplicate platform label")
        by_label[label] = report
    if set(by_label) != set(expected_labels):
        raise ValueError("missing or unexpected measured platform labels")
    baseline = by_label[expected_labels[0]]
    rows = []
    for label in expected_labels:
        report = by_label[label]
        environment = report["environment"]
        expected_system = "Windows" if label.startswith("windows") else "Darwin" if label.startswith("macos") else "Linux"
        expected_machine = {"arm64", "aarch64"} if label.endswith("arm64") else {"x86_64", "amd64"}
        drift = numeric_differences(report["observations"], baseline["observations"])
        same_runtime = environment["runtime_sha256"] == baseline["environment"]["runtime_sha256"]
        real_environment = environment["system"] == expected_system and environment["machine"].lower() in expected_machine
        rows.append({"label": label, "source_commit": environment["source_commit"], "environment": environment,
                     "differences": drift, "same_runtime": same_runtime, "checks_pass": bool(report["checks_pass"] and not drift and same_runtime and real_environment)})
    return {"contract_version": "1.0.0", "expected_labels": list(expected_labels), "checks_pass": all(r["checks_pass"] for r in rows),
            "runtime_sha256": baseline["environment"]["runtime_sha256"], "platforms": rows,
            "scope": baseline["scope"], "numeric_policy": baseline["numeric_policy"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", default="linux-x64")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output/cad-platform")
    parser.add_argument("--aggregate", type=Path)
    args = parser.parse_args()
    if args.aggregate:
        report = aggregate_platforms(sorted(args.aggregate.rglob("cad_platform.json")))
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "cad_platform_matrix.json").write_bytes(evidence_bytes(report))
    else:
        report = observe_platform(args.label, args.output_dir)
    print(json.dumps({"checks_pass": report["checks_pass"], "output_dir": str(args.output_dir)}))
    return int(not report["checks_pass"])


if __name__ == "__main__":
    raise SystemExit(main())
