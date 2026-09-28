"""Synthetic sketch controls with independent coordinate and area truth."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from research_notes.sketch_constraints import (
    Sketch, SketchConstraint, SketchEntity, SketchSolution,
    change_dimension, solve_sketch,
)


@dataclass(frozen=True)
class SketchCase:
    case_id: str
    family: str
    sketch: Sketch
    expected_status: str
    expected_dof: int
    expected_dependent: int
    expected_entities: tuple[SketchEntity, ...] = ()
    expected_area: float | None = None
    parent_case_id: str = ""
    edited_constraint: str = ""
    previous_value: float | None = None
    edited_value: float | None = None


@dataclass(frozen=True)
class SketchObservation:
    case: SketchCase
    solution: SketchSolution
    coordinate_error: float | None
    measured_area: float | None
    area_error: float | None
    checks_pass: bool


def _constraint(name: str, kind: str, *refs: str, values: tuple[float, ...] = ()) -> SketchConstraint:
    return SketchConstraint(name, kind, refs, values)


def rectangle_entities(width: float, height: float) -> tuple[SketchEntity, ...]:
    return (
        SketchEntity("bottom", "line", (0.0, 0.0, width, 0.0)),
        SketchEntity("right", "line", (width, 0.0, width, height)),
        SketchEntity("top", "line", (width, height, 0.0, height)),
        SketchEntity("left", "line", (0.0, height, 0.0, 0.0)),
    )


def rectangle_sketch() -> Sketch:
    # Four independent lines retain explicit endpoint-coincidence equations.
    entities = (
        SketchEntity("bottom", "line", (0.2, -0.3, 10.8, 0.2)),
        SketchEntity("right", "line", (11.1, -0.1, 11.2, 7.2)),
        SketchEntity("top", "line", (10.9, 7.0, -0.2, 7.1)),
        SketchEntity("left", "line", (0.1, 6.8, -0.1, 0.2)),
    )
    constraints = tuple(
        _constraint(f"join_{a}_{b}", "coincident", f"{a}.end", f"{b}.start")
        for a, b in (("bottom", "right"), ("right", "top"), ("top", "left"), ("left", "bottom"))
    ) + (
        _constraint("horizontal_bottom", "horizontal", "bottom"),
        _constraint("vertical_right", "vertical", "right"),
        _constraint("horizontal_top", "horizontal", "top"),
        _constraint("vertical_left", "vertical", "left"),
        _constraint("origin", "fix_point", "bottom.start", values=(0.0, 0.0)),
        _constraint("width", "distance_x", "bottom.start", "bottom.end", values=(12.0,)),
        _constraint("height", "distance_y", "right.start", "right.end", values=(8.0,)),
    )
    return Sketch("rectangle", entities, constraints)


def circle_sketch() -> Sketch:
    return Sketch("circle", (SketchEntity("circle", "circle", (3.5, 2.4, 1.3)),), (
        _constraint("center", "fix_point", "circle.center", values=(4.0, 3.0)),
        _constraint("radius", "radius", "circle", values=(2.0,)),
    ))


def _line_relation_case(kind: str) -> SketchCase:
    reference = SketchEntity("reference", "line", (0.0, 0.0, 4.0, 3.0))
    if kind == "parallel":
        endpoint, seed, angle = (4.0, 5.0), (3.8, 4.7), ()
    elif kind == "perpendicular":
        endpoint, seed, angle = (-3.0, 6.0), (-2.7, 5.8), ()
    else:
        # Rotate the independent (4,3) length-five vector by +90 degrees.
        endpoint, seed, angle = (-3.0, 6.0), (-2.7, 5.8), (math.pi / 2,)
    sketch = Sketch(f"line_{kind}", (reference, SketchEntity("moving", "line", (0.1, 2.1, *seed))), (
        _constraint("reference_start", "fix_point", "reference.start", values=(0.0, 0.0)),
        _constraint("reference_end", "fix_point", "reference.end", values=(4.0, 3.0)),
        _constraint("moving_start", "fix_point", "moving.start", values=(0.0, 2.0)),
        _constraint("length", "distance", "moving.start", "moving.end", values=(5.0,)),
        _constraint("relation", kind, "reference", "moving", values=angle),
    ))
    return SketchCase(sketch.sketch_id, "line_relation", sketch, "fully_constrained", 0, 0,
                      (reference, SketchEntity("moving", "line", (0.0, 2.0, *endpoint))))


def build_sketch_cases() -> tuple[SketchCase, ...]:
    rectangle, circle = rectangle_sketch(), circle_sketch()
    rectangle_truth = rectangle_entities(12.0, 8.0)
    circle_truth = (SketchEntity("circle", "circle", (4.0, 3.0, 2.0)),)
    cases = [
        SketchCase("rectangle_free", "rectangle", replace(rectangle, constraints=rectangle.constraints[:8]), "under_constrained", 4, 0),
        SketchCase("rectangle_anchored", "rectangle", replace(rectangle, constraints=rectangle.constraints[:9]), "under_constrained", 2, 0),
        SketchCase("rectangle_width_only", "rectangle", replace(rectangle, constraints=rectangle.constraints[:10]), "under_constrained", 1, 0),
        SketchCase("rectangle_full", "rectangle", rectangle, "fully_constrained", 0, 0, rectangle_truth, 96.0),
        SketchCase("rectangle_redundant", "rectangle", replace(rectangle, constraints=rectangle.constraints + (
            _constraint("width_duplicate", "distance_x", "bottom.start", "bottom.end", values=(12.0,)),
        )), "over_constrained", 0, 1, rectangle_truth, 96.0),
        SketchCase("rectangle_conflict", "rectangle", replace(rectangle, constraints=rectangle.constraints + (
            _constraint("width_conflict", "distance_x", "bottom.start", "bottom.end", values=(13.0,)),
        )), "inconsistent", 0, 1),
        SketchCase("circle_free", "circle", replace(circle, constraints=()), "under_constrained", 3, 0),
        SketchCase("circle_center_only", "circle", replace(circle, constraints=circle.constraints[:1]), "under_constrained", 1, 0),
        SketchCase("circle_radius_only", "circle", replace(circle, constraints=circle.constraints[1:]), "under_constrained", 2, 0),
        SketchCase("circle_full", "circle", circle, "fully_constrained", 0, 0, circle_truth, 4 * math.pi),
        SketchCase("circle_redundant", "circle", replace(circle, constraints=circle.constraints + (
            _constraint("radius_duplicate", "radius", "circle", values=(2.0,)),
        )), "over_constrained", 0, 1, circle_truth, 4 * math.pi),
        SketchCase("circle_conflict", "circle", replace(circle, constraints=circle.constraints + (
            _constraint("radius_conflict", "radius", "circle", values=(3.0,)),
        )), "inconsistent", 0, 1),
    ]
    for case_id, base, parent_id, dimension, old, new, truth, area in (
        ("rectangle_width_edit", rectangle, "rectangle_full", "width", 12.0, 18.0, rectangle_entities(18.0, 8.0), 144.0),
        ("rectangle_height_edit", rectangle, "rectangle_full", "height", 8.0, 10.0, rectangle_entities(12.0, 10.0), 120.0),
        ("circle_radius_edit", circle, "circle_full", "radius", 2.0, 3.0,
         (SketchEntity("circle", "circle", (4.0, 3.0, 3.0)),), 9 * math.pi),
    ):
        edited = change_dimension(base, dimension, new, solution=solve_sketch(base))
        # The study checkpoints its warm-start input at 12 decimal places;
        # solver and truth checks always retain unrounded floating-point values.
        edited = replace(edited, entities=tuple(replace(e, parameters=tuple(round(v, 12) + 0.0 for v in e.parameters)) for e in edited.entities))
        cases.append(SketchCase(case_id, "circle" if base is circle else "rectangle", edited,
                               "fully_constrained", 0, 0, truth, area, parent_id, dimension, old, new))
    cases.extend(_line_relation_case(kind) for kind in ("parallel", "perpendicular", "angle"))
    tangent = Sketch("line_circle_tangent", (
        SketchEntity("line", "line", (-5.0, 0.0, 5.0, 0.0)),
        SketchEntity("circle", "circle", (0.2, 2.4, 1.7)),
    ), (
        _constraint("line_start", "fix_point", "line.start", values=(-5.0, 0.0)),
        _constraint("line_end", "fix_point", "line.end", values=(5.0, 0.0)),
        _constraint("center_x", "coordinate_x", "circle.center", values=(0.0,)),
        _constraint("radius", "radius", "circle", values=(2.0,)),
        _constraint("tangency", "tangent", "line", "circle", values=(1.0,)),
    ))
    cases.append(SketchCase("line_circle_tangent", "tangency", tangent, "fully_constrained", 0, 0,
                           (tangent.entities[0], SketchEntity("circle", "circle", (0.0, 2.0, 2.0)))))
    arc = Sketch("quarter_arc", (SketchEntity("arc", "arc", (0.2, -0.1, 2.6, 0.1, 1.5)),), (
        _constraint("center", "fix_point", "arc.center", values=(0.0, 0.0)),
        _constraint("radius", "radius", "arc", values=(3.0,)),
        _constraint("start_angle", "arc_start", "arc", values=(0.0,)),
        _constraint("sweep", "arc_sweep", "arc", values=(math.pi / 2,)),
    ))
    arc_truth = SketchEntity("arc", "arc", (0.0, 0.0, 3.0, 0.0, math.pi / 2))
    cases.append(SketchCase("quarter_arc", "arc", arc, "fully_constrained", 0, 0, (arc_truth,)))
    joined = replace(arc, sketch_id="arc_line_coincident", entities=arc.entities + (
        SketchEntity("line", "line", (0.2, 2.8, 3.9, 3.1)),
    ), constraints=arc.constraints + (
        _constraint("join", "coincident", "arc.end", "line.start"),
        _constraint("horizontal", "horizontal", "line"),
        _constraint("width", "distance_x", "line.start", "line.end", values=(4.0,)),
    ))
    cases.append(SketchCase("arc_line_coincident", "arc", joined, "fully_constrained", 0, 0,
                           (arc_truth, SketchEntity("line", "line", (0.0, 3.0, 4.0, 3.0)))))
    unresolved = Sketch("nonlinear_unresolved", (SketchEntity("line", "line", (0.0, 0.0, 3.0, 4.0)),), (
        _constraint("start", "fix_point", "line.start", values=(0.0, 0.0)),
        _constraint("length_a", "distance", "line.start", "line.end", values=(5.0,)),
        _constraint("length_b", "distance", "line.start", "line.end", values=(6.0,)),
    ))
    cases.append(SketchCase("nonlinear_unresolved", "nonlinear_failure", unresolved, "not_converged", 1, 1))
    return tuple(cases)


def observe_sketch_case(case: SketchCase) -> SketchObservation:
    solution = solve_sketch(case.sketch)
    expected = {e.entity_id: e for e in case.expected_entities}
    coordinate_error = None
    if expected:
        coordinate_error = max(abs(a - b) for e in solution.entities
                               for a, b in zip(e.parameters, expected[e.entity_id].parameters, strict=True))
    measured_area = None
    if case.expected_area is not None:
        if case.family == "rectangle":
            # Shoelace area from solved vertices, independent of dimension values.
            vertices = [e.parameters[:2] for e in solution.entities]
            measured_area = abs(sum(a[0] * b[1] - b[0] * a[1]
                                    for a, b in zip(vertices, vertices[1:] + vertices[:1], strict=True))) / 2
        else:
            measured_area = math.pi * solution.entities[0].parameters[2] ** 2
    area_error = None if measured_area is None else abs(measured_area - case.expected_area)
    passed = (solution.status == case.expected_status
              and solution.local_degrees_of_freedom == case.expected_dof
              and solution.dependent_equation_count == case.expected_dependent
              and (coordinate_error is None or coordinate_error <= 1.0e-8)
              and (area_error is None or area_error <= 1.0e-8))
    return SketchObservation(case, solution, coordinate_error, measured_area, area_error, passed)


def probe_sketch_constraints() -> tuple[SketchObservation, ...]:
    return tuple(observe_sketch_case(case) for case in build_sketch_cases())
