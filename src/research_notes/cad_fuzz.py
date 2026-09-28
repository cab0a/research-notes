"""Seeded bounded malformed-input campaign and predicate-preserving reduction."""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
import random
import subprocess
import sys
import time

SEED = 20260928
STEP = b"ISO-10303-21;HEADER;FILE_DESCRIPTION(('fuzz'),'2;1');FILE_NAME('fuzz','2026-01-01',('a'),('o'),'p','s','');FILE_SCHEMA(('FUZZ'));ENDSEC;DATA;#1=POINT('',(1.,2.,3.));ENDSEC;END-ISO-10303-21;"
EXPRESS = b"SCHEMA fuzz; ENTITY point; x: REAL; END_ENTITY; END_SCHEMA;"


def fuzz_cases(seed=SEED):
    rng = random.Random(seed)
    cases = []
    for i in range(4):
        for family, source in (("part21", STEP), ("express", EXPRESS)):
            cut = rng.randrange(1, len(source) - 1)
            cases.append({"id": f"{family}_truncated_{i}", "family": family, "mutation": "truncate",
                          "source_hex": source[:cut].hex(), "expected": "reject"})
            cases.append({"id": f"{family}_invalid_byte_{i}", "family": family, "mutation": "insert_nul",
                          "source_hex": (source[:cut] + b"\0" + source[cut:]).hex(), "expected": "reject"})
            trivia = (b" /* seeded trivia */ " if family == "part21" else b" (* seeded trivia *) ") * (i + 1)
            cases.append({"id": f"{family}_trivia_{i}", "family": family, "mutation": "prefix_comment",
                          "source_hex": (trivia + source).hex(), "expected": "accept"})
    for i in range(4):
        scale = round(rng.uniform(.5, 5.), 6)
        for family, mutations in (("topology", ("reversed", "free_vertex")),
                                  ("trim", ("self_intersecting_wire",)),
                                  ("placement", ("improper_rotation", "out_of_range")),
                                  ("dependency", ("cycle", "missing_reference"))):
            for mutation in mutations:
                cases.append({"id": f"{family}_{mutation}_{i}", "family": family, "mutation": mutation,
                              "scale": scale, "expected": "reject"})
    return cases


def observe_case(case):
    family, mutation = case["family"], case["mutation"]
    try:
        if family == "part21":
            from research_notes.step_part21 import parse_part21_document, STEPParseLimits
            document = parse_part21_document(bytes.fromhex(case["source_hex"]),
                limits=STEPParseLimits(max_file_bytes=32768, max_tokens=4096, max_entities=128, max_nesting_depth=16))
            # The metamorphic oracle checks every byte, including inserted trivia.
            if document.reconstruct_source().encode("utf-8") != bytes.fromhex(case["source_hex"]):
                return {"outcome": "error", "diagnostic": "source_reconstruction_mismatch"}
        elif family == "express":
            from research_notes.express_schema import parse_express_document
            parse_express_document(bytes.fromhex(case["source_hex"]))
        elif family == "topology":
            from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
            from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
            from OCP.gp import gp_Pnt
            from research_notes.assembly_recompute import compound_shapes
            from research_notes.engineering_analysis import closed_solid
            shape = BRepPrimAPI_MakeBox(case["scale"], 2., 3.).Shape()
            shape = shape.Reversed() if mutation == "reversed" else compound_shapes((shape, BRepBuilderAPI_MakeVertex(gp_Pnt(99, 0, 0)).Shape()))
            closed_solid(shape)
        elif family == "trim":
            from OCP.BRepCheck import BRepCheck_Analyzer
            from research_notes.profile_modeling import _polygon_face
            s = case["scale"]
            face = _polygon_face(((0., 0., 0.), (s, 2., 0.), (0., 2., 0.), (s, 0., 0.)))
            if not BRepCheck_Analyzer(face).IsValid():
                return {"outcome": "reject", "diagnostic": "invalid_self_intersecting_trim"}
        elif family == "placement":
            from research_notes.spatial_workflow import BoxOccurrence
            if mutation == "improper_rotation":
                BoxOccurrence("bad", (1., 1., 1.), rotation=((-1., 0., 0.), (0., 1., 0.), (0., 0., 1.))).bounds()
            else:
                BoxOccurrence("bad", (1., 1., 1.), origin=(10001. + case["scale"], 0., 0.)).bounds()
        elif family == "dependency":
            from research_notes.modeling_studies import branching_model
            from research_notes.deterministic_recompute import validate_model
            model = branching_model()
            nodes = tuple(replace(n, dependencies=("result" if mutation == "cycle" else "absent",)) if n.node_id == "feature" else n for n in model.nodes)
            validate_model(replace(model, nodes=nodes))
        else:
            raise KeyError("unknown fuzz family")
        return {"outcome": "accept", "diagnostic": "accepted"}
    except (ValueError, RuntimeError) as error:
        return {"outcome": "reject", "diagnostic": getattr(error, "reason_code", type(error).__name__)}
    except Exception as error:
        return {"outcome": "error", "diagnostic": type(error).__name__}


def minimize_bytes(source, predicate, *, max_calls=64):
    """Bounded deletion reduction; preserves only the caller's exact predicate."""
    if not predicate(source):
        raise ValueError("initial source does not meet the reduction predicate")
    calls, granularity = 1, 2
    while len(source) > 1 and calls < max_calls:
        chunk = max(1, (len(source) + granularity - 1) // granularity)
        reduced = False
        for start in range(0, len(source), chunk):
            candidate = source[:start] + source[start + chunk:]
            if not candidate or calls >= max_calls:
                continue
            calls += 1
            if predicate(candidate):
                source, granularity, reduced = candidate, max(2, granularity - 1), True
                break
        if not reduced:
            if chunk == 1:
                break
            granularity = min(len(source), granularity * 2)
    return source, calls


def run_campaign(*, timeout=15.):
    rows, evidence, timings = [], [], []
    for case in fuzz_cases():
        started = time.perf_counter()
        if case["family"] in {"part21", "express", "placement", "dependency"}:
            observation = observe_case(case)
        else:
            try:
                process = subprocess.run([sys.executable, "-m", "research_notes.cad_fuzz", "--worker", json.dumps(case)],
                                         capture_output=True, text=True, timeout=timeout)
                lines = [line for line in process.stdout.splitlines() if line.startswith("FUZZ_RESULT=")]
                observation = json.loads(lines[0].partition("=")[2]) if process.returncode == 0 and len(lines) == 1 else {"outcome": "error", "diagnostic": "worker_failure"}
            except subprocess.TimeoutExpired:
                observation = {"outcome": "timeout", "diagnostic": "worker_deadline"}
        rows.append({"control_id": case["id"], "family": case["family"], "mutation": case["mutation"],
                     "outcome": observation["outcome"], "expected": case["expected"], "checks_pass": observation["outcome"] == case["expected"]})
        evidence.append({"case": case, "observation": observation})
        timings.append({"control_id": case["id"], "elapsed_seconds": time.perf_counter() - started})
    # Reduce a known malformed lexical input with its original diagnostic class.
    control = next(c for c in fuzz_cases() if c["id"] == "part21_invalid_byte_0")
    expected = observe_case(control)
    def predicate(data):
        return observe_case({**control, "source_hex": data.hex()}) == expected
    minimal, calls = minimize_bytes(bytes.fromhex(control["source_hex"]), predicate)
    reduction = {"original_sha256": hashlib.sha256(bytes.fromhex(control["source_hex"])).hexdigest(),
                 "original_bytes": len(bytes.fromhex(control["source_hex"])), "reduced_hex": minimal.hex(),
                 "reduced_bytes": len(minimal), "predicate": expected, "calls": calls,
                 "scope": "diagnostic-preserving reduction of a known rejection, not a newly discovered parser defect"}
    return rows, {"seed": SEED, "cases": evidence, "reduction": reduction,
        "unexpected_outcomes": [r for r in rows if not r["checks_pass"]]}, timings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", required=True)
    args = parser.parse_args()
    print("FUZZ_RESULT=" + json.dumps(observe_case(json.loads(args.worker)), sort_keys=True))


if __name__ == "__main__":
    main()
