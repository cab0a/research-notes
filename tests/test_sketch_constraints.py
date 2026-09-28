"""Independent geometry, failure, editing, and artifact checks for v0.56.0."""

import csv
import importlib.util
import json
import math
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from research_notes.sketch_constraints import (
    Sketch, SketchConstraint, SketchEntity, change_dimension,
    point_coordinates, sketch_fingerprint, solve_sketch,
)
from research_notes.sketch_constraint_study import (
    build_sketch_cases, circle_sketch, observe_sketch_case,
    rectangle_sketch,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("case", build_sketch_cases(), ids=lambda case: case.case_id)
def test_control_matches_independent_state_and_geometry_truth(case):
    observation = observe_sketch_case(case)
    assert observation.checks_pass
    assert observation.solution.satisfied == (case.expected_status not in {"inconsistent", "not_converged"})


@pytest.mark.parametrize("builder", [rectangle_sketch, circle_sketch])
def test_fully_constrained_solution_is_independent_of_small_seed_changes(builder):
    sketch = builder()
    expected = solve_sketch(sketch)
    rng = np.random.default_rng(56)
    for _ in range(5):
        entities = tuple(replace(e, parameters=tuple(np.asarray(e.parameters) + rng.uniform(-0.2, 0.2, len(e.parameters))))
                         for e in sketch.entities)
        solution = solve_sketch(replace(sketch, entities=entities))
        assert solution.status == "fully_constrained"
        for actual, reference in zip(solution.entities, expected.entities, strict=True):
            assert actual.parameters == pytest.approx(reference.parameters, abs=1e-9)


def test_dimension_edits_preserve_other_parameters_and_do_not_mutate_parent():
    sketch = rectangle_sketch()
    fingerprint = sketch_fingerprint(sketch)
    base = solve_sketch(sketch)
    wider = change_dimension(sketch, "width", 18.0, solution=base)
    solved_wider = solve_sketch(wider)
    taller = change_dimension(wider, "height", 10.0, solution=solved_wider)
    result = solve_sketch(taller)
    assert result.revision == 3
    assert result.status == "fully_constrained"
    assert point_coordinates(result.entities, "right.end") == pytest.approx((18.0, 10.0), abs=1e-9)
    assert point_coordinates(result.entities, "bottom.start") == pytest.approx((0.0, 0.0), abs=1e-9)
    assert sketch_fingerprint(sketch) == fingerprint
    assert sketch.constraints[-2].values == (12.0,)
    with pytest.raises(ValueError, match="exact sketch revision"):
        change_dimension(wider, "height", 10.0, solution=base)


def test_radius_edit_area_ratio_and_center():
    sketch = circle_sketch()
    base = solve_sketch(sketch)
    edited = solve_sketch(change_dimension(sketch, "radius", 3.0, solution=base))
    assert edited.entities[0].parameters[:2] == pytest.approx((4.0, 3.0))
    ratio = edited.entities[0].parameters[2] ** 2 / base.entities[0].parameters[2] ** 2
    assert ratio == pytest.approx(2.25)


def test_dependent_constraints_can_coexist_with_remaining_freedom():
    sketch = circle_sketch()
    radius = sketch.constraints[1]
    sketch = replace(sketch, constraints=(radius, replace(radius, constraint_id="duplicate")))
    result = solve_sketch(sketch)
    assert result.status == "over_constrained"
    assert result.satisfied
    assert result.local_degrees_of_freedom == 2
    assert result.dependent_equation_count == 1


def test_inconsistent_output_is_diagnostic_and_cannot_seed_an_edit():
    case = next(c for c in build_sketch_cases() if c.case_id == "circle_conflict")
    result = solve_sketch(case.sketch)
    assert result.status == "inconsistent"
    assert not result.satisfied
    residuals = {r.constraint_id: r.value for r in result.residuals}
    assert residuals["radius"] == pytest.approx(0.5)
    assert residuals["radius_conflict"] == pytest.approx(-0.5)
    with pytest.raises(ValueError, match="satisfied solution"):
        change_dimension(case.sketch, "radius", 4.0, solution=result)


def test_nonlinear_iteration_exhaustion_does_not_claim_inconsistency():
    case = next(c for c in build_sketch_cases() if c.case_id == "line_angle")
    result = solve_sketch(case.sketch, max_iterations=0)
    assert result.status == "not_converged"
    assert result.termination == "iteration_limit"
    assert not result.satisfied
    assert solve_sketch(case.sketch).status == "fully_constrained"


def test_collapsed_dimension_is_not_accepted_as_a_solved_sketch():
    result = solve_sketch(change_dimension(rectangle_sketch(), "width", 0.0))
    assert result.status == "invalid_geometry"
    assert not result.satisfied


@pytest.mark.parametrize("side", [-1.0, 1.0])
def test_signed_tangency_selects_requested_side(side):
    case = next(c for c in build_sketch_cases() if c.case_id == "line_circle_tangent")
    constraints = tuple(replace(c, values=(side,)) if c.kind == "tangent" else c for c in case.sketch.constraints)
    solution = solve_sketch(replace(case.sketch, constraints=constraints))
    assert solution.status == "fully_constrained"
    circle = solution.entities[1]
    assert circle.parameters == pytest.approx((0.0, side * 2.0, 2.0), abs=1e-8)


def test_arc_endpoints_and_join_use_solved_radius_and_angles():
    case = next(c for c in build_sketch_cases() if c.case_id == "arc_line_coincident")
    result = solve_sketch(case.sketch)
    assert point_coordinates(result.entities, "arc.start") == pytest.approx((3.0, 0.0), abs=1e-8)
    assert point_coordinates(result.entities, "arc.end") == pytest.approx((0.0, 3.0), abs=1e-8)
    assert point_coordinates(result.entities, "line.start") == pytest.approx((0.0, 3.0), abs=1e-8)
    assert point_coordinates(result.entities, "line.end") == pytest.approx((4.0, 3.0), abs=1e-8)


@pytest.mark.parametrize("value", [0.0, -1.0, math.nan, math.inf, 1e7])
def test_invalid_radius_edits_are_rejected(value):
    with pytest.raises(ValueError):
        change_dimension(circle_sketch(), "radius", value)


@pytest.mark.parametrize("constraint", [
    SketchConstraint("unknown", "unknown", ()),
    SketchConstraint("center", "fix_point", ("missing.center",), (0.0, 0.0)),
    SketchConstraint("center", "fix_point", ("circle.start",), (0.0, 0.0)),
    SketchConstraint("radius", "radius", ("circle",), ()),
    SketchConstraint("line", "horizontal", ("circle",)),
])
def test_unsupported_or_unresolved_constraints_are_rejected(constraint):
    with pytest.raises(ValueError):
        solve_sketch(replace(circle_sketch(), constraints=(constraint,)))


@pytest.mark.parametrize("entity", [
    SketchEntity("circle", "circle", (0.0, 0.0, 0.0)),
    SketchEntity("line", "line", (0.0, 0.0, 0.0, 0.0)),
    SketchEntity("arc", "arc", (0.0, 0.0, 1.0, 2.0, 1.0)),
    SketchEntity("circle", "circle", (math.nan, 0.0, 1.0)),
])
def test_invalid_geometry_is_rejected_before_numerical_solving(entity):
    with pytest.raises(ValueError, match="initial geometry"):
        solve_sketch(Sketch("invalid", (entity,), ()))


def test_duplicate_ids_and_unsupported_units_are_rejected():
    sketch = circle_sketch()
    for invalid in (replace(sketch, entities=sketch.entities * 2),
                    replace(sketch, constraints=sketch.constraints * 2),
                    replace(sketch, length_unit="inch")):
        with pytest.raises(ValueError):
            solve_sketch(invalid)
    for constraint_id in ("missing", "center"):
        with pytest.raises(ValueError, match="scalar dimension"):
            change_dimension(sketch, constraint_id, 4.0)


def test_reference_artifacts_regenerate_and_fixture_drift_is_detected(tmp_path):
    path = ROOT / "experiments/run_sketch_constraints.py"
    spec = importlib.util.spec_from_file_location("run_sketch_constraints", path)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    fixtures, output = tmp_path / "fixtures", tmp_path / "results"
    observations = runner.run(output, fixtures, refresh=True)
    assert all(o.checks_pass for o in observations)
    for generated in fixtures.iterdir():
        assert generated.read_bytes() == (ROOT / "fixtures/sketch-constraints" / generated.name).read_bytes()
    for generated in output.iterdir():
        if generated.suffix in {".csv", ".json"}:
            assert generated.read_bytes() == (ROOT / "results" / generated.name).read_bytes()
        else:
            assert generated.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    contract = json.loads((output / "sketch_constraint_contract.json").read_text())
    assert contract["case_count"] == 22
    assert contract["state_counts"]["inconsistent"] == 2
    assert contract["state_counts"]["not_converged"] == 1
    with (output / "sketch_dimension_edits.csv").open() as stream:
        edits = list(csv.DictReader(stream))
    assert [float(row["measured_area_ratio"]) for row in edits] == pytest.approx([1.5, 1.25, 2.25])
    runner.handle_fixtures(fixtures, refresh=False)
    (fixtures / "sketches.json").write_text("{}\n")
    with pytest.raises(RuntimeError, match="fixture differs"):
        runner.handle_fixtures(fixtures, refresh=False)
