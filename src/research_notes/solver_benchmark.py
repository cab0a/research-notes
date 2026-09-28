"""Independent geometric truth for small sketch and pose solver stress cases."""
from __future__ import annotations

from dataclasses import asdict, replace
import math
import numpy as np

from research_notes.sketch_constraints import Sketch, SketchEntity, SketchConstraint, solve_sketch
from research_notes.sketch_constraint_study import rectangle_sketch, rectangle_entities, circle_sketch
from research_notes.assembly_constraints import (
    AXES, AssemblyDocument, AssemblyConstraint, ComponentDefinition, DatumFrame,
    Occurrence, Placement, solve_placements, rotation_matrix,
)
from research_notes.deterministic_recompute import single_feature_model
from research_notes.parametric_features import PlateSpec
from research_notes.robustness_studies import evidence_bytes, finish


def sketch_cases():
    """Deterministic inputs and analytic answers; no fitted expected coordinates."""
    for family, original, answer in (
        ("rectangle", rectangle_sketch(), rectangle_entities(12., 8.)),
        ("circle", circle_sketch(), (SketchEntity("circle", "circle", (4., 3., 2.)),)),
    ):
        for scale in (1e-4, 1., 1e4):
            for seed in (0, 1):
                entities = tuple(replace(e, parameters=tuple(v * scale + (0.13 * scale * (i + 1) if seed else 0.)
                    for i, v in enumerate(e.parameters))) for e in original.entities)
                constraints = tuple(replace(c, values=tuple(v * scale for v in c.values)) for c in original.constraints)
                case = replace(original, entities=entities, constraints=constraints)
                truth = [v * scale for e in answer for v in e.parameters]
                yield f"{family}_scale_{scale:g}_seed_{seed}", "coordinate_scale", case, scale, truth, "unique", "ordinary"
    circle = circle_sketch()
    for kind in ("duplicate", "conflict", "free", "translated"):
        if kind in {"duplicate", "conflict"}:
            extra = replace(circle.constraints[1], constraint_id="extra", values=(2. if kind == "duplicate" else 3.,))
            case = replace(circle, constraints=circle.constraints + (extra,))
        elif kind == "free":
            case = replace(circle, constraints=circle.constraints[1:])
        else:
            case = replace(circle, entities=(replace(circle.entities[0], parameters=(100003.5, -99997.6, 1.3)),),
                constraints=(replace(circle.constraints[0], values=(100004., -99997.)), circle.constraints[1]))
        truth = [100004., -99997., 2.] if kind == "translated" else [4., 3., 2.]
        yield "circle_" + kind, kind, case, 1., truth, "none" if kind == "conflict" else "continuous" if kind == "free" else "unique", kind
    for scale in (1e-3, 1., 1e3):
        for height in (1., 1e-3, 1e-6, 0.):
            for seed in (-1, 0, 1):
                entities = (SketchEntity("a", "circle", (-scale, 0., .1 * scale)),
                            SketchEntity("b", "circle", (scale, 0., .1 * scale)),
                            SketchEntity("p", "circle", (.2 * scale, seed * scale, .1 * scale)))
                constraints = (SketchConstraint("a", "fix_point", ("a.center",), (-scale, 0.)),
                               SketchConstraint("b", "fix_point", ("b.center",), (scale, 0.))) + tuple(
                    SketchConstraint("radius_" + key, "radius", (key,), (.1 * scale,)) for key in ("a", "b", "p")) + tuple(
                    SketchConstraint("distance_" + key, "distance", (key + ".center", "p.center"), (scale * math.hypot(1., height),)) for key in ("a", "b"))
                case = Sketch("two_distances", entities, constraints)
                truth = [-scale, 0., .1 * scale, scale, 0., .1 * scale, 0., height * scale, .1 * scale]
                yield f"two_distances_s{scale:g}_h{height:g}_seed{seed}", "initial_near_singular", case, scale, truth, "two_branches" if height else "unique_singular", "difficult"
    # Independent, deterministic sub-nanometre RHS perturbation, not RNG state.
    for delta in (-1e-10, 1e-10):
        case = replace(circle, constraints=(circle.constraints[0], replace(circle.constraints[1], values=(2. + delta,))))
        yield f"circle_rhs_{delta:g}", "numerical_perturbation", case, 1., [4., 3., 2. + delta], "unique", "ordinary"


def assembly_case(scale=1., angle=90., seed=0, perturb=0., mode="ordinary"):
    theta = math.radians(angle)
    # Independent normals for the signed-distance equations. Rotation matrices
    # passed to the solver are authored directly from these analytic bases.
    normals = ((0., 0., 1.), (math.sin(theta), 0., math.cos(theta)), (0., 1., 0.))
    rotations = (np.eye(3), np.array(((math.cos(theta), 0., math.sin(theta)), (0., 1., 0.), (-math.sin(theta), 0., math.cos(theta)))),
                 np.array(((1., 0., 0.), (0., 0., 1.), (0., -1., 0.))))
    definition = ComponentDefinition("part", single_feature_model("part", PlateSpec(2., 2., 2.)),
        (DatumFrame(), DatumFrame("z"), DatumFrame("tilted", rotation_degrees=(0., angle, 0.)), DatumFrame("y", rotation_degrees=(-90., 0., 0.))))
    desired = np.array((scale + perturb, 2. * scale, 3. * scale))
    initial = Placement(tuple(v * scale for v in ((.3, -.2, 2.7) if seed == 0 else (-2., 3., -1.))),
                        (5., -7., 10.) if seed == 0 else (-25., 15., -20.))
    constraints = (AssemblyConstraint("ground", "fixed", "base"),
                   AssemblyConstraint("rotation", "fixed", "moving", axes=AXES[3:])) + tuple(
        AssemblyConstraint("distance_" + name, "distance", "moving", "base", "origin", name,
                           f"{float(desired @ normal):.17g} * mm") for name, normal in zip(("z", "tilted", "y"), normals))
    if mode in {"duplicate", "conflict"}:
        extra = replace(constraints[2], constraint_id="extra",
                        value_expression=constraints[2].value_expression if mode == "duplicate" else f"{3 * scale + scale:g} * mm")
        constraints += (extra,)
    if mode == "free":
        constraints = constraints[:-1]
    document = AssemblyDocument("pose_control", (definition,),
                                (Occurrence("base", "part"), Occurrence("moving", "part", initial)), constraints)
    frames = {(occurrence, name): (np.zeros(3), matrix) for occurrence in ("base", "moving")
              for name, matrix in zip(("z", "tilted", "y"), rotations)}
    frames.update({(occurrence, "origin"): (np.zeros(3), np.eye(3)) for occurrence in ("base", "moving")})
    return document, frames, desired


def _assessment(converged, correct, status, uniqueness):
    if uniqueness == "none":
        return "conflict_detected" if status == "inconsistent" else "missed_conflict"
    if not converged:
        return "not_converged"
    if uniqueness == "continuous":
        return "non_unique" if correct else "satisfied_inaccurate"
    return "correct" if correct else "satisfied_inaccurate"


def evaluate_solver_benchmark():
    """Return classifications plus unrounded observations and reproducible inputs."""
    rows, detail, inputs = [], [], []
    for name, family, sketch, scale, truth, uniqueness, difficulty in sketch_cases():
        result = solve_sketch(sketch)
        values = np.array([v for e in result.entities for v in e.parameters])
        truth = np.array(truth)
        if uniqueness in {"two_branches", "unique_singular"}:
            values[7] = abs(values[7])
        error = float(np.max(np.abs(values - truth))) / scale
        correct = error <= 1e-6
        if uniqueness == "continuous":
            correct = abs(result.entities[0].parameters[2] - 2.) <= 1e-9
        assessment = _assessment(result.satisfied, correct, result.status, uniqueness)
        expected = "conflict_detected" if difficulty == "conflict" else "non_unique" if difficulty == "free" else "correct"
        allowed = {"correct", "satisfied_inaccurate", "not_converged"} if difficulty == "difficult" else {expected}
        checks = assessment in allowed and (result.local_degrees_of_freedom == 2 if difficulty == "free" else True)
        if difficulty == "duplicate":
            checks &= result.dependent_equation_count == 1 and result.satisfied
        rows.append({"control_id": name, "solver": "sketch", "family": family, "status": result.status,
            "converged": result.satisfied, "correct": correct if uniqueness != "none" else False,
            "analytic_uniqueness": uniqueness, "reported_dof": result.local_degrees_of_freedom,
            "assessment": assessment, "checks_pass": bool(checks)})
        detail.append({"control_id": name, "result": asdict(result), "coordinate_error_over_scale": error,
                       "truth": truth.tolist(), "correctness_tolerance_over_scale": 1e-6,
                       "allowed_assessments": sorted(allowed), "rank_is_local": True})
        if uniqueness in {"two_branches", "unique_singular"}:
            point = np.array(result.entities[2].parameters[:2])
            directions = [point - np.array(e.parameters[:2]) for e in result.entities[:2]]
            jacobian = np.array([v / np.linalg.norm(v) for v in directions])
            detail[-1]["analytic_position_jacobian_singular_values"] = np.linalg.svd(jacobian, compute_uv=False).tolist()
        inputs.append({"control_id": name, "sketch": asdict(sketch), "scale_mm": scale, "analytic_uniqueness": uniqueness,
                       "truth": truth.tolist(), "branch_rule": "absolute p.y only for the two-distance system"})
    cases = [(f"pose_s{s:g}_seed{seed}", s, 90., seed, 0., "ordinary") for s in (1e-4, 1., 100.) for seed in (0, 1)]
    cases += [("pose_outside_distance_domain", 1000., 90., 0, 0., "rejected")]
    cases += [(f"pose_near_{a:g}", 1., a, 0, 0., "difficult") for a in (1., .001, .000001, 0.)]
    cases += [("pose_" + mode, 1., 90., 0, 0., mode) for mode in ("duplicate", "conflict", "free")]
    cases += [(f"pose_rhs_{p:g}", 1., 90., 0, p, "ordinary") for p in (-1e-9, 1e-9)]
    for name, scale, angle, seed, perturb, mode in cases:
        document, frames, desired = assembly_case(scale, angle, seed, perturb, mode)
        try:
            result = solve_placements(document, frames)
        except ValueError as error:
            if mode != "rejected":
                raise
            rows.append({"control_id": name, "solver": "assembly", "family": "input_domain", "status": "rejected",
                "converged": False, "correct": False, "analytic_uniqueness": "unique", "reported_dof": "not_evaluated",
                "assessment": "input_rejected", "checks_pass": "outside its inclusive domain" in str(error)})
            detail.append({"control_id": name, "error": str(error), "native_solver_run": False})
            inputs.append({"control_id": name, "document": asdict(document), "scale_mm": scale})
            continue
        placements = dict(zip(result.occurrence_order, result.placements))
        moving, base = placements["moving"], placements["base"]
        position_error = max(float(np.max(np.abs(np.array(moving.translation) - desired))), max(abs(v) for v in base.translation)) / scale
        rotation_error = max(float(np.linalg.norm(rotation_matrix(np.deg2rad(p.rotation_degrees)) - np.eye(3))) for p in (moving, base))
        correct = position_error <= 1e-6 and rotation_error <= 1e-7
        if mode == "free":
            correct = abs(moving.translation[0] - desired[0]) <= 1e-6 and abs(moving.translation[2] - desired[2]) <= 1e-6 and rotation_error <= 1e-7
        if angle == 0.:
            correct = max(abs(moving.translation[i] - desired[i]) for i in (1, 2)) <= 1e-6 and rotation_error <= 1e-7
        converged = result.status in {"fully_constrained", "under_constrained", "redundant"}
        uniqueness = "none" if mode == "conflict" else "continuous" if mode == "free" or angle == 0. else "unique"
        assessment = _assessment(converged, correct, result.status, uniqueness)
        allowed = {"correct", "satisfied_inaccurate", "not_converged", "non_unique"} if mode == "difficult" else {
            "conflict_detected" if mode == "conflict" else "non_unique" if mode == "free" else "correct"}
        checks = assessment in allowed
        if mode == "duplicate":
            checks &= result.redundant_equations == 1 and converged
        if mode == "free":
            checks &= result.degrees_of_freedom == 1
        rows.append({"control_id": name, "solver": "assembly", "family": mode if mode != "ordinary" else "scale_seed_perturbation",
            "status": result.status, "converged": converged, "correct": correct if uniqueness != "none" else False,
            "analytic_uniqueness": uniqueness, "reported_dof": result.degrees_of_freedom,
            "assessment": assessment, "checks_pass": bool(checks)})
        nonzero = [v for v in result.singular_values if v > 0]
        detail.append({"control_id": name, "result": asdict(result), "coordinate_error_over_scale": position_error,
            "rotation_matrix_error": rotation_error, "truth_translation_mm": desired.tolist(),
            "singular_value_ratio": min(nonzero) / max(nonzero) if nonzero else 0., "allowed_assessments": sorted(allowed)})
        inputs.append({"control_id": name, "document": asdict(document), "local_frames": [
            {"occurrence": key[0], "frame": key[1], "origin": p.tolist(), "rotation": r.tolist()} for key, (p, r) in sorted(frames.items())],
            "truth_translation_mm": desired.tolist(), "angle_degrees": angle, "scale_mm": scale})
    return rows, detail, inputs


def run_solver_robustness(output, fixtures, *, refresh=False):
    rows, detail, inputs = evaluate_solver_benchmark()
    return finish(output, fixtures, "solver_robustness", rows, detail, {"controls.json": evidence_bytes(inputs)}, [
        "Existing local solvers are evaluated without changing their stopping tolerances. Convergence, analytic coordinate correctness and uniqueness are separate columns.",
        "Sketch scales: 1e-4..1e4 mm; assembly scale factors: 1e-4..100, plus a 1000 control rejected by the signed-distance domain. Seed, duplicate, conflict and deterministic RHS perturbation cases are included.",
        "Two-distance sketches have two mirror solutions or a singular tangent solution; assembly nearly parallel distance normals test loss of numerical rank.",
        "Difficult controls explicitly permit recorded non-convergence or inaccurate satisfied solutions. A passing case contract is not a robustness guarantee.",
        "Rank/nullity is local and tolerance dependent. Nonlinear failure does not prove inconsistency, and a zero reported DOF does not prove global uniqueness.",
    ], refresh=refresh)
