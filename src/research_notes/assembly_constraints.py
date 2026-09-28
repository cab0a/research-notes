"""Reusable component/occurrence records and a local six-DOF assembly solver."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

import numpy as np

from research_notes.deterministic_recompute import FeatureModel, validate_model
from research_notes.parameter_expressions import Parameter, UNITS, evaluate_parameters


AXES = ("tx", "ty", "tz", "rx", "ry", "rz")
TOLERANCE = 1e-8


@dataclass(frozen=True)
class Placement:
    translation: tuple[float, float, float] = (0., 0., 0.)
    rotation_degrees: tuple[float, float, float] = (0., 0., 0.)
    unit: str = "mm"


@dataclass(frozen=True)
class DatumFrame:
    frame_id: str = "origin"
    origin: tuple[float, float, float] = (0., 0., 0.)
    rotation_degrees: tuple[float, float, float] = (0., 0., 0.)
    unit: str = "mm"
    anchor: str = "explicit"
    provenance: str = "authored_local_datum"


@dataclass(frozen=True)
class ComponentDefinition:
    definition_id: str
    model: FeatureModel
    frames: tuple[DatumFrame, ...] = (DatumFrame(),)
    geometry_unit: str = "mm"


@dataclass(frozen=True)
class Occurrence:
    occurrence_id: str
    definition_id: str
    initial: Placement = Placement()


@dataclass(frozen=True)
class AssemblyConstraint:
    constraint_id: str
    kind: str
    occurrence_a: str
    occurrence_b: str | None = None
    frame_a: str = "origin"
    frame_b: str = "origin"
    value_expression: str = "0 * mm"
    axes: tuple[str, ...] = AXES
    target: Placement = Placement()


@dataclass(frozen=True)
class AssemblyDocument:
    assembly_id: str
    definitions: tuple[ComponentDefinition, ...]
    occurrences: tuple[Occurrence, ...]
    constraints: tuple[AssemblyConstraint, ...]
    parameters: tuple[Parameter, ...] = ()
    # (definition ID, parameter name, model node ID, model field)
    bindings: tuple[tuple[str, str, str, str], ...] = ()
    revision: int = 1


@dataclass(frozen=True)
class AssemblySolution:
    status: str
    occurrence_order: tuple[str, ...]
    placements: tuple[Placement, ...]
    rank: int
    degrees_of_freedom: int
    redundant_equations: int
    equation_count: int
    residuals: tuple[dict, ...]
    remaining_motion: tuple[tuple[float, ...], ...]
    singular_values: tuple[float, ...]
    iterations: int
    conflict_constraints: tuple[str, ...]


def unit_scale(unit: str) -> float:
    if unit not in UNITS or UNITS[unit][1] != (1, 0):
        raise ValueError("placement/frame units must describe length")
    return UNITS[unit][0]


def rotation_matrix(vector) -> np.ndarray:
    v = np.asarray(vector, dtype=float)
    angle = float(np.linalg.norm(v))
    skew = np.array([[0., -v[2], v[1]], [v[2], 0., -v[0]], [-v[1], v[0], 0.]])
    if angle < 1e-10:
        return np.eye(3) + skew + 0.5 * skew @ skew
    return np.eye(3) + math.sin(angle)/angle*skew + (1-math.cos(angle))/angle**2 * skew@skew


def rotation_log(matrix) -> np.ndarray:
    cosine = np.clip((np.trace(matrix)-1)/2, -1., 1.)
    angle = math.acos(cosine)
    vector = np.array([matrix[2, 1]-matrix[1, 2], matrix[0, 2]-matrix[2, 0], matrix[1, 0]-matrix[0, 1]]) / 2
    if angle < 1e-8:
        return vector
    if angle > math.pi - 1e-5:
        raise ValueError("relative rotation near 180 degrees is outside the local solver")
    return vector * angle / math.sin(angle)


def placement_vector(placement: Placement) -> np.ndarray:
    if len(placement.translation) != 3 or len(placement.rotation_degrees) != 3:
        raise ValueError("placements require three translations and a rotation vector")
    values = np.array((*placement.translation, *placement.rotation_degrees), dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("placement must be finite")
    values[:3] *= unit_scale(placement.unit)
    values[3:] *= math.pi/180
    if np.max(np.abs(values[:3])) > 10000 or np.linalg.norm(values[3:]) > math.pi/2:
        raise ValueError("placement exceeds 10000 mm or the 90-degree local rotation domain")
    return values


def validate_assembly(document: AssemblyDocument) -> None:
    if not document.assembly_id or type(document.revision) is not int or document.revision < 1:
        raise ValueError("invalid assembly identity or revision")
    if not 1 <= len(document.definitions) <= 8 or not 1 <= len(document.occurrences) <= 12 or len(document.constraints) > 64:
        raise ValueError("assembly exceeds the definition, occurrence, or constraint budget")
    groups = ([d.definition_id for d in document.definitions], [o.occurrence_id for o in document.occurrences],
              [c.constraint_id for c in document.constraints])
    for keys in groups:
        if len(keys) != len(set(keys)) or any(not re.fullmatch(r"[a-z][a-z0-9_]*", key) for key in keys):
            raise ValueError("invalid or duplicate assembly record ID")
    definitions = {d.definition_id: d for d in document.definitions}
    occurrences = {o.occurrence_id: o for o in document.occurrences}
    if document.parameters:
        evaluate_parameters(document.parameters)
    for definition in document.definitions:
        validate_model(definition.model)
        if definition.model.provenance == "unconfirmed_candidate" or definition.geometry_unit != "mm":
            raise ValueError("components require confirmed millimetre geometry")
        if not 1 <= len(definition.frames) <= 16 or len({f.frame_id for f in definition.frames}) != len(definition.frames):
            raise ValueError("component frames require unique names within the frame budget")
        for f in definition.frames:
            if not re.fullmatch(r"[a-z][a-z0-9_]*", f.frame_id) or f.anchor not in {"explicit", "plate_top", "plate_bottom", "plate_center"}:
                raise ValueError("unsupported datum frame")
            placement_vector(Placement(f.origin, f.rotation_degrees, f.unit))
    for o in document.occurrences:
        if o.definition_id not in definitions:
            raise ValueError("unknown component definition")
        placement_vector(o.initial)
    for c in document.constraints:
        if c.kind not in {"fixed", "coincident", "concentric", "distance"} or c.occurrence_a not in occurrences:
            raise ValueError("unknown constraint kind or occurrence")
        if c.kind == "fixed":
            if c.occurrence_b is not None or not c.axes or len(set(c.axes)) != len(c.axes) or not set(c.axes) <= set(AXES):
                raise ValueError("fixed constraint requires unique pose axes and no second occurrence")
            if c.frame_a != "origin" or c.frame_b != "origin":
                raise ValueError("fixed locks the occurrence pose; use origin frame identifiers")
            placement_vector(c.target)
        elif c.occurrence_b not in occurrences or c.occurrence_a == c.occurrence_b:
            raise ValueError("mate requires two different known occurrences")
        for occurrence, frame in ((c.occurrence_a, c.frame_a), (c.occurrence_b, c.frame_b)):
            if occurrence is not None and frame not in {f.frame_id for f in definitions[occurrences[occurrence].definition_id].frames}:
                raise ValueError("unknown local datum frame")
        if c.kind == "distance":
            distance_value(document, c)
    names = {p.name for p in document.parameters}
    targets = set()
    for definition_id, parameter, node_id, field in document.bindings:
        if definition_id not in definitions or parameter not in names or (definition_id, node_id, field) in targets:
            raise ValueError("invalid or duplicate assembly parameter binding")
        targets.add((definition_id, node_id, field))


def distance_value(document: AssemblyDocument, constraint: AssemblyConstraint) -> float:
    name = "constraint_distance"
    while name in {p.name for p in document.parameters}:
        name += "_x"
    value = evaluate_parameters((*document.parameters, Parameter(name, constraint.value_expression, "mm", -1000., 1000.)))[-1]
    return value.base_value


def _null_modes(jacobian: np.ndarray, rank: int) -> tuple[tuple[float, ...], ...]:
    n = jacobian.shape[1]
    if rank == n:
        return ()
    # Project coordinate axes then Gram-Schmidt: stable ordering even when SVD
    # returns different bases for repeated singular values.
    _, _, vh = np.linalg.svd(jacobian, full_matrices=True)
    null = vh[rank:].T
    projector = null @ null.T
    basis = []
    for i in range(n):
        vector = projector[:, i].copy()
        for previous in basis:
            vector -= np.dot(vector, previous) * previous
        length = np.linalg.norm(vector)
        if length > 1e-7:
            vector /= length
            if vector[np.flatnonzero(np.abs(vector) > 1e-8)[0]] < 0:
                vector = -vector
            basis.append(vector)
        if len(basis) == n-rank:
            break
    return tuple(tuple(float(v) for v in mode) for mode in basis)


def solve_placements(document: AssemblyDocument, local_frames: dict[tuple[str, str], tuple],
                     *, max_iterations: int = 60) -> AssemblySolution:
    """Solve a small local pose system; nullity describes local, not global motion."""
    validate_assembly(document)
    if not 0 <= max_iterations <= 100:
        raise ValueError("invalid iteration budget")
    order = tuple(sorted(o.occurrence_id for o in document.occurrences))
    occurrences = {o.occurrence_id: o for o in document.occurrences}
    index = {key: i for i, key in enumerate(order)}
    constraints = tuple(sorted(document.constraints, key=lambda c: c.constraint_id))
    distances = {c.constraint_id: distance_value(document, c) for c in constraints if c.kind == "distance"}
    x = np.concatenate([placement_vector(occurrences[key].initial) for key in order])
    conflicts = set()
    # Exact duplicate definitions with distinct right-hand sides prove a conflict.
    right_sides = {}
    for c in constraints:
        if c.kind == "distance":
            key = (c.kind, c.occurrence_a, c.frame_a, c.occurrence_b, c.frame_b)
            rhs = (distances[c.constraint_id],)
        elif c.kind == "fixed":
            # Check each fixed coordinate independently, even with different masks.
            target = placement_vector(c.target)
            for axis in c.axes:
                key = ("fixed", c.occurrence_a, axis)
                rhs = (float(target[AXES.index(axis)]),)
                if key in right_sides and not np.allclose(rhs, right_sides[key][1], rtol=0., atol=TOLERANCE):
                    conflicts.update((right_sides[key][0], c.constraint_id))
                right_sides[key] = c.constraint_id, rhs
            continue
        else:
            continue
        if key in right_sides and not np.allclose(rhs, right_sides[key][1], rtol=0., atol=TOLERANCE):
            conflicts.update((right_sides[key][0], c.constraint_id))
        right_sides[key] = c.constraint_id, rhs

    def residual(values, details=False):
        rows, metadata = [], []
        poses = {key: (values[6*i:6*i+3], rotation_matrix(values[6*i+3:6*i+6])) for key, i in index.items()}
        def frame(key, name):
            p, r = poses[key]
            local_p, local_r = local_frames[key, name]
            return p + r @ local_p, r @ local_r
        for c in constraints:
            labels = []
            if c.kind == "fixed":
                p, r = poses[c.occurrence_a]
                desired = placement_vector(c.target)
                # Rotation-vector coordinate locks are explicit partial fixed DOFs.
                pose = values[6*index[c.occurrence_a]:6*index[c.occurrence_a]+6]
                terms = [pose[AXES.index(axis)]-desired[AXES.index(axis)] for axis in c.axes]
                labels = [(axis, "mm" if axis.startswith("t") else "rad") for axis in c.axes]
            else:
                a, ar = frame(c.occurrence_a, c.frame_a)
                b, br = frame(c.occurrence_b, c.frame_b)
                delta = a-b
                if c.kind == "distance":
                    terms = [float(delta @ br[:, 2])-distances[c.constraint_id]]
                    labels = [("signed_axial_distance", "mm")]
                else:
                    # Two independent tangent coordinates avoid counting the
                    # intrinsic redundancy of a three-component cross product.
                    alignment = [float(ar[:, 2] @ br[:, i]) for i in (0, 1)]
                    if c.kind == "coincident":
                        terms = [float(delta @ br[:, 2]), *alignment]
                        labels = [("plane_offset", "mm"), ("normal_x", "unitless"), ("normal_y", "unitless")]
                    else:
                        terms = [float(delta @ br[:, i]) for i in (0, 1)] + alignment
                        labels = [("axis_offset_x", "mm"), ("axis_offset_y", "mm"), ("axis_x", "unitless"), ("axis_y", "unitless")]
            rows.extend(terms)
            metadata.extend({"constraint_id": c.constraint_id, "component": label, "unit": unit, "residual": float(value)}
                            for (label, unit), value in zip(labels, terms, strict=True))
        return (np.asarray(rows, dtype=float), metadata) if details else np.asarray(rows, dtype=float)

    def jacobian(values):
        columns = []
        for i in range(len(values)):
            plus, minus = values.copy(), values.copy()
            plus[i] += 1e-6
            minus[i] -= 1e-6
            columns.append((residual(plus)-residual(minus))/(2e-6))
        return np.column_stack(columns)

    iterations = 0
    for iteration in range(max_iterations):
        r = residual(x)
        if not len(r) or np.max(np.abs(r)) <= TOLERANCE:
            break
        j = jacobian(x)
        step = np.linalg.lstsq(j, -r, rcond=1e-9)[0]
        accepted = False
        for factor in (1., .5, .25, .125, .0625, .03125, .015625, .0078125):
            trial = x + factor*step
            if any(np.linalg.norm(trial[6*i+3:6*i+6]) > math.pi/2 for i in range(len(order))) or np.max(np.abs(trial)) > 10000:
                continue
            if np.linalg.norm(residual(trial)) < np.linalg.norm(r):
                x, accepted = trial, True
                break
        iterations = iteration+1
        if not accepted:
            break
    r, metadata = residual(x, True)
    j = jacobian(x)
    singular = np.linalg.svd(j, compute_uv=False)
    threshold = max(1e-8, max(singular, default=0.)*1e-8)
    rank = int(np.count_nonzero(singular > threshold))
    degrees = len(x)-rank
    redundant = max(0, len(r)-rank)
    satisfied = not len(r) or np.max(np.abs(r)) <= TOLERANCE
    aligned = True
    for c in constraints:
        if c.kind in {"coincident", "concentric"}:
            ia, ib = index[c.occurrence_a], index[c.occurrence_b]
            ar = rotation_matrix(x[6*ia+3:6*ia+6]) @ local_frames[c.occurrence_a, c.frame_a][1]
            br = rotation_matrix(x[6*ib+3:6*ib+6]) @ local_frames[c.occurrence_b, c.frame_b][1]
            aligned &= float(ar[:, 2] @ br[:, 2]) > 0
    status = ("inconsistent" if conflicts else "not_converged" if not satisfied or not aligned else
              "redundant" if redundant else "under_constrained" if degrees else "fully_constrained")
    placements = tuple(Placement(tuple(float(v) for v in x[6*i:6*i+3]),
                                 tuple(float(v*180/math.pi) for v in x[6*i+3:6*i+6])) for i in range(len(order)))
    return AssemblySolution(status, order, placements, rank, degrees, redundant, len(r), tuple(metadata),
                            _null_modes(j, rank), tuple(float(v) for v in singular), iterations, tuple(sorted(conflicts)))
