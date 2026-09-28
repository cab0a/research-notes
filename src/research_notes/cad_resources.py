"""Measured scaling and explicit resource outcomes for bounded CAD workloads."""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
import json
import math
from pathlib import Path
import subprocess
import sys
import time
import tracemalloc


@dataclass(frozen=True)
class ResourceLimits:
    bytes: int = 2_000_000
    entities: int = 20_000
    references: int = 100_000
    tokens: int = 250_000
    faces: int = 256
    edges: int = 512
    triangles: int = 60_000
    model_nodes: int = 64
    sketch_entities: int = 32
    sketch_constraints: int = 128
    estimated_memory_bytes: int = 256_000_000
    seconds: float = 30.

    def __post_init__(self):
        for name, value in asdict(self).items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0 or name != "seconds" and type(value) is not int:
                raise ValueError("resource budgets must be positive finite counters")


class ResourceExhausted(ValueError):
    def __init__(self, counter, observed, limit):
        super().__init__(f"{counter} budget exceeded")
        self.counter, self.observed, self.limit = counter, observed, limit


def require_budget(counter, value, limits):
    maximum = getattr(limits, counter)
    if value > maximum:
        raise ResourceExhausted(counter, value, maximum)


def syntax_payload(count):
    from research_notes.cad_fuzz import STEP
    declarations = [f"#{i}=NODE({('#' + str(i - 1)) if i > 1 else '$'});" for i in range(1, count + 1)]
    return STEP.replace(b"#1=POINT('',(1.,2.,3.));", "".join(declarations).encode())


def workload(spec, limits):
    kind, count = spec["kind"], spec.get("count", 1)
    if type(count) is not int or not 1 <= count <= 4096:
        raise ValueError("workload count is outside 1..4096")
    if kind == "syntax":
        from research_notes.step_part21 import STEPParseLimits, parse_part21_document
        source = syntax_payload(count)
        require_budget("bytes", len(source), limits)
        require_budget("estimated_memory_bytes", len(source) * 32, limits)
        doc = parse_part21_document(source, limits=STEPParseLimits(max_file_bytes=limits.bytes,
            max_entities=limits.entities, max_references=limits.references, max_tokens=limits.tokens))
        return {"bytes": len(source), "entities": len(doc.entities), "references": doc.reference_count, "tokens": len(doc.tokens)}
    if kind == "model":
        from research_notes.deterministic_recompute import single_feature_model, ModelNode, recompute
        from research_notes.parametric_features import PlateSpec
        require_budget("model_nodes", count, limits)
        model = single_feature_model("scale_model", PlateSpec())
        nodes = [model.nodes[0]]
        for i in range(1, count):
            nodes.append(ModelNode(f"node_{i}", "result", (nodes[-1].node_id,)))
        model = replace(model, nodes=tuple(nodes), output_id=nodes[-1].node_id)
        result = recompute(model)
        return {"nodes": len(result.states), "valid": all(s.status == "valid" for s in result.states), "volume": result.current_output().metrics.absolute_volume}
    if kind == "sketch":
        from research_notes.sketch_constraints import Sketch, SketchEntity, SketchConstraint, solve_sketch
        require_budget("sketch_entities", count, limits)
        entities = tuple(SketchEntity(f"circle_{i}", "circle", (float(i), 0., 1.)) for i in range(count))
        constraints = tuple(c for i in range(count) for c in (
            SketchConstraint(f"center_{i}", "fix_point", (f"circle_{i}.center",), (float(i), 0.)),
            SketchConstraint(f"radius_{i}", "radius", (f"circle_{i}",), (1.,))))
        require_budget("sketch_constraints", len(constraints), limits)
        solved = solve_sketch(Sketch("scale_sketch", entities, constraints))
        return {"entities": count, "constraints": len(constraints), "status": solved.status, "dof": solved.local_degrees_of_freedom}
    if kind == "mesh":
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeSphere
        from research_notes.engineering_analysis import mesh_mass_properties
        from research_notes.modeling_common import measure_shape
        shape = BRepPrimAPI_MakeSphere(3.).Shape()
        metrics = measure_shape(shape)
        require_budget("faces", metrics.face_count, limits)
        require_budget("edges", metrics.edge_count, limits)
        result = mesh_mass_properties(shape, deflection=spec["deflection"], angular_deflection=.2)
        require_budget("triangles", result["triangles"], limits)
        return {"faces": metrics.face_count, "edges": metrics.edge_count, "triangles": result["triangles"], "volume": result["volume"]}
    if kind == "topology":
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
        from research_notes.modeling_common import measure_shape
        metrics = measure_shape(BRepPrimAPI_MakeBox(2., 3., 4.).Shape())
        require_budget("faces", metrics.face_count, limits)
        require_budget("edges", metrics.edge_count, limits)
        return {"faces": metrics.face_count, "edges": metrics.edge_count}
    if kind == "deadline_control":
        time.sleep(.25)
        return {"completed": True}
    raise ValueError("unknown bounded workload")


def run_workload(spec, limits=ResourceLimits()):
    started = time.perf_counter()
    try:
        process = subprocess.run([sys.executable, "-m", "research_notes.cad_resources", "--worker", json.dumps(spec),
            "--limits", json.dumps(asdict(limits))], capture_output=True, text=True, timeout=limits.seconds)
        records = [s for s in process.stdout.splitlines() if s.startswith("RESOURCE_RESULT=")]
        result = json.loads(records[0].partition("=")[2]) if process.returncode == 0 and len(records) == 1 else {"status": "error", "reason": "worker_failure"}
    except subprocess.TimeoutExpired:
        result = {"status": "resource_exhausted", "counter": "seconds", "limit": limits.seconds, "observed": None,
                  "reason": "child_process_deadline", "python_peak_bytes": None, "compute_seconds": None}
    return {**result, "wall_seconds": time.perf_counter() - started,
            "memory_scope": "tracemalloc Python allocation peak during workload; excludes native OCCT/NumPy allocations; memory admission is estimated"}


def resource_cases():
    cases = [(f"syntax_{n}", {"kind": "syntax", "count": n}, ResourceLimits(), "ok") for n in (16, 128, 1024)]
    cases += [(f"model_{n}", {"kind": "model", "count": n}, ResourceLimits(), "ok") for n in (4, 16, 64)]
    cases += [(f"sketch_{n}", {"kind": "sketch", "count": n}, ResourceLimits(), "ok") for n in (1, 8, 32)]
    cases += [(f"mesh_{i}", {"kind": "mesh", "deflection": d}, ResourceLimits(), "ok") for i, d in enumerate((.2, .05))]
    for name, spec, counter, limit in (
        ("bytes_gate", {"kind": "syntax", "count": 32}, "bytes", 128),
        ("entities_gate", {"kind": "syntax", "count": 32}, "entities", 16),
        ("references_gate", {"kind": "syntax", "count": 32}, "references", 16),
        ("tokens_gate", {"kind": "syntax", "count": 32}, "tokens", 16),
        ("memory_estimate_gate", {"kind": "syntax", "count": 32}, "estimated_memory_bytes", 1000),
        ("nodes_gate", {"kind": "model", "count": 65}, "model_nodes", 64),
        ("sketch_entities_gate", {"kind": "sketch", "count": 33}, "sketch_entities", 32),
        ("constraints_gate", {"kind": "sketch", "count": 8}, "sketch_constraints", 8),
        ("faces_gate", {"kind": "topology"}, "faces", 5),
        ("edges_gate", {"kind": "topology"}, "edges", 11),
        ("triangles_gate", {"kind": "mesh", "deflection": .2}, "triangles", 10),
        ("deadline_gate", {"kind": "deadline_control"}, "seconds", .02)):
        cases.append((name, spec, replace(ResourceLimits(), **{counter: limit}), "resource_exhausted"))
    return cases


def evaluate_resources():
    rows, evidence, observations = [], [], []
    for name, spec, limits, expected in resource_cases():
        result = run_workload(spec, limits)
        rows.append({"control_id": name, "workload": spec["kind"], "scale": spec.get("count", 1),
                     "outcome": result["status"], "expected": expected, "checks_pass": result["status"] == expected})
        evidence.append({"control_id": name, "spec": spec, "limits": asdict(limits),
                         "result": {k: v for k, v in result.items() if k not in {"wall_seconds", "compute_seconds", "python_peak_bytes"}}})
        observations.append({"control_id": name, **result})
    return rows, evidence, observations


def main():
    from research_notes.step_part21 import Part21ParseError
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", required=True)
    parser.add_argument("--limits", required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    tracemalloc.start()
    try:
        result = {"status": "ok", "measurements": workload(json.loads(args.worker), ResourceLimits(**json.loads(args.limits)))}
    except ResourceExhausted as error:
        result = {"status": "resource_exhausted", "counter": error.counter, "observed": error.observed, "limit": error.limit}
    except Part21ParseError as error:
        result = {"status": "resource_exhausted" if error.decision == "quarantine" else "invalid", "reason": error.reason_code}
    except Exception as error:
        result = {"status": "error", "reason": type(error).__name__, "detail": str(error)}
    result.update(compute_seconds=time.perf_counter() - started, python_peak_bytes=tracemalloc.get_traced_memory()[1])
    tracemalloc.stop()
    print("RESOURCE_RESULT=" + json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
