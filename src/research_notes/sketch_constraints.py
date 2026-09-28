"""Bounded, local 2D sketch solving for the v0.56.0 research controls.

Lengths use millimetres and angles use radians. Rank is a local numerical
observation, not a proof of global uniqueness or nonlinear infeasibility.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, replace

import numpy as np


CONTRACT_VERSION = "1.0.0"
RESIDUAL_TOLERANCE = 1.0e-9
RANK_RELATIVE_TOLERANCE = 1.0e-7
DIFFERENCE_STEP = 1.0e-6
MIN_GEOMETRY_SIZE = 1.0e-8
MAX_ITERATIONS = 80
ENTITY_SIZES = {"line": 4, "circle": 3, "arc": 5}
DIMENSION_KINDS = {
    "coordinate_x", "coordinate_y", "distance_x", "distance_y", "distance",
    "radius", "angle", "arc_start", "arc_sweep",
}


@dataclass(frozen=True)
class SketchEntity:
    """Line (x1,y1,x2,y2), circle (cx,cy,r), or arc (cx,cy,r,a0,a1)."""

    entity_id: str
    kind: str
    parameters: tuple[float, ...]


@dataclass(frozen=True)
class SketchConstraint:
    """An identified constraint; point references use entity.start/end/center."""

    constraint_id: str
    kind: str
    references: tuple[str, ...]
    values: tuple[float, ...] = ()


@dataclass(frozen=True)
class Sketch:
    sketch_id: str
    entities: tuple[SketchEntity, ...]
    constraints: tuple[SketchConstraint, ...]
    revision: int = 1
    length_unit: str = "mm"


@dataclass(frozen=True)
class ConstraintResidual:
    constraint_id: str
    component: int
    value: float
    unit: str


@dataclass(frozen=True)
class SketchSolution:
    sketch_id: str
    revision: int
    input_sha256: str
    status: str
    termination: str
    satisfied: bool
    affine_system: bool
    variable_count: int
    equation_count: int
    jacobian_rank: int
    local_degrees_of_freedom: int
    dependent_equation_count: int
    max_residual: float
    iterations: int
    entities: tuple[SketchEntity, ...]
    residuals: tuple[ConstraintResidual, ...]


def sketch_fingerprint(sketch: Sketch) -> str:
    payload = json.dumps(asdict(sketch), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _entity_map(entities: tuple[SketchEntity, ...]) -> dict[str, SketchEntity]:
    return {item.entity_id: item for item in entities}


def point_coordinates(entities: tuple[SketchEntity, ...], reference: str) -> tuple[float, float]:
    """Evaluate a named point, including endpoints of a circular arc."""
    entity_id, selector = reference.split(".")
    item = _entity_map(entities)[entity_id]
    p = item.parameters
    if selector == "center":
        return p[0], p[1]
    if item.kind == "line":
        return (p[0], p[1]) if selector == "start" else (p[2], p[3])
    angle = p[3] if selector == "start" else p[4]
    return p[0] + p[2] * math.cos(angle), p[1] + p[2] * math.sin(angle)


def _valid_geometry(entities: tuple[SketchEntity, ...]) -> bool:
    for item in entities:
        p = item.parameters
        if not all(math.isfinite(value) and abs(value) <= 1.0e6 for value in p):
            return False
        if item.kind == "line" and math.hypot(p[2] - p[0], p[3] - p[1]) <= MIN_GEOMETRY_SIZE:
            return False
        if item.kind in {"circle", "arc"} and p[2] <= MIN_GEOMETRY_SIZE:
            return False
        if item.kind == "arc" and not MIN_GEOMETRY_SIZE < p[4] - p[3] < 2 * math.pi:
            return False
    return True


def validate_sketch(sketch: Sketch) -> None:
    """Reject unsupported references, dimensions, and degenerate initial geometry."""
    if not sketch.sketch_id or sketch.revision < 1 or sketch.length_unit != "mm":
        raise ValueError("a named, positive-revision millimetre sketch is required")
    if not 1 <= len(sketch.entities) <= 32 or len(sketch.constraints) > 128:
        raise ValueError("study limits are 1..32 entities and at most 128 constraints")
    entities = _entity_map(sketch.entities)
    if len(entities) != len(sketch.entities):
        raise ValueError("duplicate entity ID")
    for item in sketch.entities:
        if not item.entity_id or "." in item.entity_id or item.kind not in ENTITY_SIZES:
            raise ValueError("unsupported entity kind or ID")
        if len(item.parameters) != ENTITY_SIZES[item.kind]:
            raise ValueError("incorrect entity parameter count")
    if not _valid_geometry(sketch.entities):
        raise ValueError("non-finite, out-of-range, or degenerate initial geometry")
    ids = [item.constraint_id for item in sketch.constraints]
    if len(ids) != len(set(ids)) or any(not item for item in ids):
        raise ValueError("constraint IDs must be nonempty and unique")

    def entity_ref(reference: str, kinds: set[str]) -> None:
        if reference not in entities or entities[reference].kind not in kinds:
            raise ValueError(f"unsupported entity reference: {reference}")

    def point_ref(reference: str) -> None:
        parts = reference.split(".")
        if len(parts) != 2 or parts[0] not in entities:
            raise ValueError(f"unresolved point reference: {reference}")
        allowed = {"line": {"start", "end"}, "circle": {"center"}, "arc": {"center", "start", "end"}}
        if parts[1] not in allowed[entities[parts[0]].kind]:
            raise ValueError(f"unsupported point reference: {reference}")

    signatures = {
        "fix_point": (1, 2), "coincident": (2, 0),
        "coordinate_x": (1, 1), "coordinate_y": (1, 1),
        "distance_x": (2, 1), "distance_y": (2, 1), "distance": (2, 1),
        "horizontal": (1, 0), "vertical": (1, 0),
        "parallel": (2, 0), "perpendicular": (2, 0), "angle": (2, 1),
        "radius": (1, 1), "arc_start": (1, 1), "arc_sweep": (1, 1),
        "tangent": (2, 1),
    }
    for item in sketch.constraints:
        if item.kind not in signatures or (len(item.references), len(item.values)) != signatures[item.kind]:
            raise ValueError(f"unsupported constraint signature: {item.constraint_id}")
        if not all(math.isfinite(v) and abs(v) <= 1.0e6 for v in item.values):
            raise ValueError("non-finite or out-of-range constraint value")
        if item.kind in {"fix_point", "coincident", "coordinate_x", "coordinate_y", "distance_x", "distance_y", "distance"}:
            for reference in item.references:
                point_ref(reference)
        elif item.kind in {"horizontal", "vertical", "parallel", "perpendicular", "angle"}:
            for reference in item.references:
                entity_ref(reference, {"line"})
        elif item.kind == "radius":
            entity_ref(item.references[0], {"circle", "arc"})
        elif item.kind in {"arc_start", "arc_sweep"}:
            entity_ref(item.references[0], {"arc"})
        elif item.kind == "tangent":
            entity_ref(item.references[0], {"line"})
            entity_ref(item.references[1], {"circle"})
            if item.values[0] not in {-1.0, 1.0}:
                raise ValueError("tangency requires an explicit signed side (-1 or +1)")
        if item.kind in {"radius", "distance"} and item.values[0] <= MIN_GEOMETRY_SIZE:
            raise ValueError("radius and distance must be strictly positive")
        if item.kind == "arc_sweep" and not MIN_GEOMETRY_SIZE < item.values[0] < 2 * math.pi:
            raise ValueError("only counterclockwise arcs with sweep strictly between 0 and 2pi are supported")
        if item.kind == "angle" and not -math.pi < item.values[0] < math.pi:
            raise ValueError("directed line angle must be strictly between -pi and pi")


def _affine(sketch: Sketch) -> bool:
    entities = _entity_map(sketch.entities)
    for item in sketch.constraints:
        if item.kind in {"distance", "parallel", "perpendicular", "angle", "tangent"}:
            return False
        for ref in item.references:
            if "." in ref:
                name, selector = ref.split(".")
                if entities[name].kind == "arc" and selector != "center":
                    return False
    return True


def _residuals(sketch: Sketch, entities: tuple[SketchEntity, ...]) -> tuple[ConstraintResidual, ...]:
    lookup = _entity_map(entities)

    def point(ref: str) -> np.ndarray:
        return np.asarray(point_coordinates(entities, ref))

    def direction(ref: str) -> np.ndarray:
        p = lookup[ref].parameters
        delta = np.array((p[2] - p[0], p[3] - p[1]))
        return delta / np.linalg.norm(delta)

    def cross(a: np.ndarray, b: np.ndarray) -> float:
        return float(a[0] * b[1] - a[1] * b[0])

    rows = []
    for item in sketch.constraints:
        refs, target, kind = item.references, item.values, item.kind
        unit = "mm"
        if kind == "fix_point":
            values = point(refs[0]) - np.asarray(target)
        elif kind == "coincident":
            values = point(refs[1]) - point(refs[0])
        elif kind in {"coordinate_x", "coordinate_y"}:
            values = [point(refs[0])[int(kind == "coordinate_y")] - target[0]]
        elif kind in {"distance_x", "distance_y", "distance"}:
            delta = point(refs[1]) - point(refs[0])
            actual = np.linalg.norm(delta) if kind == "distance" else delta[int(kind == "distance_y")]
            values = [actual - target[0]]
        elif kind in {"horizontal", "vertical"}:
            p = lookup[refs[0]].parameters
            values = [p[3] - p[1] if kind == "horizontal" else p[2] - p[0]]
        elif kind in {"parallel", "perpendicular", "angle"}:
            a, b = direction(refs[0]), direction(refs[1])
            unit = "unitless"
            if kind == "parallel":
                values = [cross(a, b)]
            elif kind == "perpendicular":
                values = [float(a @ b)]
            else:
                delta = math.atan2(cross(a, b), float(a @ b)) - target[0]
                values = [math.atan2(math.sin(delta), math.cos(delta))]
                unit = "rad"
        elif kind == "tangent":
            line, circle = lookup[refs[0]].parameters, lookup[refs[1]].parameters
            values = [cross(direction(refs[0]), np.array((circle[0] - line[0], circle[1] - line[1]))) - target[0] * circle[2]]
        else:
            p = lookup[refs[0]].parameters
            actual = p[2] if kind == "radius" else p[3] if kind == "arc_start" else p[4] - p[3]
            values = [actual - target[0]]
            if kind != "radius":
                unit = "rad"
        rows.extend(ConstraintResidual(item.constraint_id, i, float(value), unit) for i, value in enumerate(values))
    return tuple(rows)


def solve_sketch(sketch: Sketch, *, max_iterations: int = MAX_ITERATIONS) -> SketchSolution:
    """Solve affine constraints directly; use local least-squares steps otherwise.

    Only an incompatible affine system is classified inconsistent. Failure of
    the nonlinear iteration remains not_converged, regardless of residual size.
    """
    validate_sketch(sketch)
    if not isinstance(max_iterations, int) or not 0 <= max_iterations <= MAX_ITERATIONS:
        raise ValueError(f"max_iterations must be an integer in 0..{MAX_ITERATIONS}")
    x = np.array([v for item in sketch.entities for v in item.parameters], dtype=float)

    def entities_at(vector: np.ndarray) -> tuple[SketchEntity, ...]:
        offset = 0
        result = []
        for item in sketch.entities:
            size = len(item.parameters)
            result.append(replace(item, parameters=tuple(float(v) for v in vector[offset:offset + size])))
            offset += size
        return tuple(result)

    def residual(vector: np.ndarray) -> np.ndarray:
        return np.array([r.value for r in _residuals(sketch, entities_at(vector))])

    affine = _affine(sketch)

    def jacobian(vector: np.ndarray) -> np.ndarray:
        columns = []
        for i in range(len(vector)):
            h = 1.0 if affine else DIFFERENCE_STEP * max(1.0, abs(vector[i]))
            plus, minus = vector.copy(), vector.copy()
            plus[i] += h
            minus[i] -= h
            columns.append((residual(plus) - residual(minus)) / (2 * h))
        return np.column_stack(columns)

    iterations = 0
    termination = "residual_tolerance"
    r = residual(x)
    if affine and len(r):
        # These residuals are affine by construction; a linear least-squares
        # incompatibility is stronger evidence than nonlinear non-convergence.
        step = np.linalg.lstsq(jacobian(x), -r, rcond=RANK_RELATIVE_TOLERANCE)[0]
        x += step
        iterations = 1
        r = residual(x)
        termination = "affine_least_squares"
    elif not affine:
        termination = "iteration_limit"
        for _ in range(max_iterations):
            if float(np.max(np.abs(r), initial=0)) <= RESIDUAL_TOLERANCE:
                termination = "residual_tolerance"
                break
            j = jacobian(x)
            step = np.linalg.lstsq(j, -r, rcond=RANK_RELATIVE_TOLERANCE)[0]
            accepted = False
            for backtrack in range(24):
                trial = x + step * 0.5**backtrack
                if not _valid_geometry(entities_at(trial)):
                    continue
                trial_r = residual(trial)
                if float(trial_r @ trial_r) < float(r @ r):
                    x, r, accepted = trial, trial_r, True
                    iterations += 1
                    break
            if not accepted:
                termination = "no_descent"
                break
        if float(np.max(np.abs(r), initial=0)) <= RESIDUAL_TOLERANCE:
            termination = "residual_tolerance"

    entities = entities_at(x)
    rows = _residuals(sketch, entities)
    maximum = float(np.max(np.abs(r), initial=0))
    geometry_valid = _valid_geometry(entities)
    # Degenerate output must never be treated as a solved sketch or used in
    # normalized direction residuals on a later edit.
    j = jacobian(x)
    singular_values = np.linalg.svd(j, compute_uv=False)
    cutoff = RANK_RELATIVE_TOLERANCE * max(1.0, float(np.max(singular_values, initial=0)))
    rank = int(np.count_nonzero(singular_values > cutoff))
    dof, dependent = len(x) - rank, len(r) - rank
    satisfied = maximum <= RESIDUAL_TOLERANCE and geometry_valid
    if maximum > RESIDUAL_TOLERANCE:
        status = "inconsistent" if affine else "not_converged"
    elif not geometry_valid:
        status = "invalid_geometry"
    elif dependent:
        status = "over_constrained"
    elif dof:
        status = "under_constrained"
    else:
        status = "fully_constrained"
    return SketchSolution(
        sketch.sketch_id, sketch.revision, sketch_fingerprint(sketch), status,
        termination, satisfied, affine, len(x), len(r), rank, dof, dependent,
        maximum, iterations, entities, rows,
    )


def change_dimension(
    sketch: Sketch, constraint_id: str, value: float, *, solution: SketchSolution | None = None,
) -> Sketch:
    """Create a new revision; an optional matching solved state is the next seed."""
    validate_sketch(sketch)
    matching = [c for c in sketch.constraints if c.constraint_id == constraint_id]
    if not matching or matching[0].kind not in DIMENSION_KINDS:
        raise ValueError("dimension ID must identify one supported scalar dimension")
    entities = sketch.entities
    if solution is not None:
        if solution.input_sha256 != sketch_fingerprint(sketch) or not solution.satisfied:
            raise ValueError("dimension edit requires a satisfied solution of this exact sketch revision")
        entities = solution.entities
    constraints = tuple(replace(c, values=(float(value),)) if c.constraint_id == constraint_id else c for c in sketch.constraints)
    edited = replace(sketch, entities=entities, constraints=constraints, revision=sketch.revision + 1)
    validate_sketch(edited)
    return edited
