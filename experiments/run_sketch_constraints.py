"""Generate v0.56.0 sketch constraints, dimension edits, and visual evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402
from matplotlib.patches import Circle  # noqa: E402

from research_notes.sketch_constraints import (  # noqa: E402
    CONTRACT_VERSION, DIFFERENCE_STEP, MAX_ITERATIONS, MIN_GEOMETRY_SIZE,
    RANK_RELATIVE_TOLERANCE, RESIDUAL_TOLERANCE,
)
from research_notes.sketch_constraint_study import (  # noqa: E402
    SketchObservation, build_sketch_cases, observe_sketch_case,
)


def _json(payload: object) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def _csv(rows: list[dict[str, object]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=tuple(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _number(value: float | None) -> str:
    # The evidence is a quantized view; every pass/fail gate uses raw values.
    return "" if value is None else f"{round(value, 10) + 0.0:.10f}"


def _rounded(payload: object) -> object:
    if isinstance(payload, float):
        return round(payload, 10) + 0.0
    if isinstance(payload, dict):
        return {key: _rounded(value) for key, value in payload.items()}
    if isinstance(payload, (tuple, list)):
        return [_rounded(value) for value in payload]
    return payload


def fixture_payloads() -> dict[str, bytes]:
    payload = _json({"contract_version": CONTRACT_VERSION, "cases": [asdict(c) for c in build_sketch_cases()]})
    return {
        "sketches.json": payload,
        "manifest.csv": _csv([{
            "file_name": "sketches.json", "byte_length": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(), "case_count": len(build_sketch_cases()),
            "generator": "experiments/run_sketch_constraints.py",
            "provenance": "synthetic authored constraints and independent analytic truth; no STEP inference",
        }]),
    }


def handle_fixtures(directory: Path, *, refresh: bool) -> str:
    payloads = fixture_payloads()
    directory.mkdir(parents=True, exist_ok=True)
    unexpected = {p.name for p in directory.iterdir()} - payloads.keys()
    if unexpected:
        raise RuntimeError(f"unexpected sketch fixtures: {sorted(unexpected)}")
    for name, payload in payloads.items():
        path = directory / name
        if refresh:
            path.write_bytes(payload)
        elif not path.exists() or path.read_bytes() != payload:
            raise RuntimeError(f"fixture differs; rerun with --refresh-fixtures: {path}")
    return hashlib.sha256(payloads["sketches.json"]).hexdigest()


def observation_rows(observations: tuple[SketchObservation, ...]) -> list[dict[str, object]]:
    return [{
        "contract_version": CONTRACT_VERSION, "case_id": o.case.case_id, "family": o.case.family,
        "sketch_revision": o.solution.revision, "input_sha256": o.solution.input_sha256,
        "expected_status": o.case.expected_status, "status": o.solution.status,
        "satisfied": int(o.solution.satisfied), "affine_system": int(o.solution.affine_system),
        "variable_count": o.solution.variable_count, "equation_count": o.solution.equation_count,
        "jacobian_rank": o.solution.jacobian_rank,
        "local_degrees_of_freedom": o.solution.local_degrees_of_freedom,
        "dependent_equation_count": o.solution.dependent_equation_count,
        "max_residual": _number(o.solution.max_residual),
        "termination": o.solution.termination, "iterations": o.solution.iterations,
        "coordinate_max_error": _number(o.coordinate_error),
        "expected_area_mm2": _number(o.case.expected_area),
        "measured_area_mm2": _number(o.measured_area), "area_error_mm2": _number(o.area_error),
        "checks_pass": int(o.checks_pass),
    } for o in observations]


def residual_rows(observations: tuple[SketchObservation, ...]) -> list[dict[str, object]]:
    return [{
        "case_id": o.case.case_id, "constraint_id": r.constraint_id, "component": r.component,
        "unit": r.unit, "residual": _number(r.value),
        "within_tolerance": int(abs(r.value) <= RESIDUAL_TOLERANCE),
    } for o in observations for r in o.solution.residuals]


def edit_rows(observations: tuple[SketchObservation, ...]) -> list[dict[str, object]]:
    lookup = {o.case.case_id: o for o in observations}
    return [{
        "case_id": o.case.case_id, "parent_case_id": o.case.parent_case_id,
        "constraint_id": o.case.edited_constraint, "before_mm": _number(o.case.previous_value),
        "after_mm": _number(o.case.edited_value),
        "before_area_mm2": _number(lookup[o.case.parent_case_id].measured_area),
        "after_area_mm2": _number(o.measured_area),
        "expected_area_ratio": _number(o.case.expected_area / lookup[o.case.parent_case_id].case.expected_area),
        "measured_area_ratio": _number(o.measured_area / lookup[o.case.parent_case_id].measured_area),
        "status": o.solution.status, "checks_pass": int(o.checks_pass),
    } for o in observations if o.case.parent_case_id]


def write_figures(directory: Path, observations: tuple[SketchObservation, ...]) -> None:
    colors = {"under_constrained": "#277da8", "fully_constrained": "#2a9d70",
              "over_constrained": "#cf8b17", "inconsistent": "#cd4a4a", "not_converged": "#7b5ba7"}
    figure, axis = plt.subplots(figsize=(12, 8), layout="constrained")
    axis.axis("off")
    rows = [[o.case.case_id, o.solution.status.replace("_", " "),
             o.solution.equation_count, o.solution.jacobian_rank,
             o.solution.local_degrees_of_freedom, o.solution.dependent_equation_count]
            for o in observations]
    table = axis.table(cellText=rows, colLabels=["Control", "State", "Equations", "Rank", "Local DoF", "Dependent"],
                       colWidths=[0.29, 0.25, 0.12, 0.09, 0.12, 0.13], cellLoc="left", bbox=[0, 0.03, 1, 0.91])
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor("#e2e6ec")
        if row == 0:
            cell.set_facecolor("#183249")
            cell.set_text_props(color="white", weight="bold")
        else:
            cell.set_facecolor("#f2f5f8" if row % 2 else "white")
            if col == 1:
                cell.set_text_props(color=colors[observations[row - 1].solution.status], weight="bold")
    axis.set_title("2D sketch constraints | 22 controlled cases", loc="left", fontsize=17, pad=12)
    figure.text(0.02, 0.008, "Rank and DoF are local. Redundancy and conflict are separate. Nonlinear failure is not an infeasibility proof.", fontsize=10)
    figure.savefig(directory / "sketch_constraints.png", dpi=160, metadata={"Software": "research-notes"})
    plt.close(figure)

    lookup = {o.case.case_id: o for o in observations}
    edits = [o for o in observations if o.case.parent_case_id]
    figure, axes = plt.subplots(1, 3, figsize=(13, 4.5), layout="constrained")
    for axis, observation in zip(axes, edits, strict=True):
        for source, color, style, label in (
            (lookup[observation.case.parent_case_id], "#277da8", "--", "Before"),
            (observation, "#e88026", "-", "After"),
        ):
            for index, entity in enumerate(source.solution.entities):
                p = entity.parameters
                entity_label = label if index == 0 else None
                if entity.kind == "line":
                    axis.plot((p[0], p[2]), (p[1], p[3]), color=color, linestyle=style, linewidth=2, label=entity_label)
                elif entity.kind == "circle":
                    axis.add_patch(Circle(p[:2], p[2], fill=False, color=color, linestyle=style, linewidth=2, label=entity_label))
        axis.autoscale_view()
        axis.margins(0.18)
        axis.set_aspect("equal", adjustable="box")
        axis.grid(alpha=0.2)
        axis.set_xlabel("x (mm)")
        axis.set_ylabel("y (mm)")
        axis.legend(loc="upper right", fontsize=9)
        c = observation.case
        ratio = c.expected_area / lookup[c.parent_case_id].case.expected_area
        axis.set_title(f"{c.edited_constraint.title()}: {c.previous_value:g} → {c.edited_value:g} mm\nArea ratio {ratio:g} | fully constrained", fontsize=11)
    figure.suptitle("Dimension edits preserve the remaining sketch constraints", fontsize=16)
    figure.savefig(directory / "sketch_dimension_edits.png", dpi=160, metadata={"Software": "research-notes"})
    plt.close(figure)


def run(output: Path, fixtures: Path, *, refresh: bool = False) -> tuple[SketchObservation, ...]:
    fixture_digest = handle_fixtures(fixtures, refresh=refresh)
    observations = tuple(observe_sketch_case(case) for case in build_sketch_cases())
    output.mkdir(parents=True, exist_ok=True)
    for name, rows in (
        ("sketch_constraint_observations.csv", observation_rows(observations)),
        ("sketch_constraint_residuals.csv", residual_rows(observations)),
        ("sketch_dimension_edits.csv", edit_rows(observations)),
    ):
        (output / name).write_bytes(_csv(rows))
    (output / "sketch_constraint_solutions.json").write_bytes(_json({
        "contract_version": CONTRACT_VERSION,
        "solutions": [{"case_id": o.case.case_id, **_rounded(asdict(o.solution))} for o in observations],
    }))
    (output / "sketch_constraint_contract.json").write_bytes(_json({
        "contract_version": CONTRACT_VERSION, "study_version": "v0.56.0",
        "title": "Two-Dimensional Sketches and Geometric Constraints",
        "fixture_sha256": fixture_digest, "case_count": len(observations),
        "state_counts": dict(sorted(Counter(o.solution.status for o in observations).items())),
        "all_checks_pass": all(o.checks_pass for o in observations),
        "solver": "NumPy least squares; direct affine solve or backtracked local Gauss-Newton",
        "residual_tolerance": RESIDUAL_TOLERANCE, "rank_relative_tolerance": RANK_RELATIVE_TOLERANCE,
        "difference_step": DIFFERENCE_STEP, "maximum_nonlinear_iterations": MAX_ITERATIONS,
        "minimum_geometry_size_mm": MIN_GEOMETRY_SIZE,
        "units": {"length": "mm", "angle": "rad", "normalized_direction": "unitless"},
        "serialization": "result floats rounded to 10 decimal places; all gates use unrounded values; sub-resolution values display as zero",
        "edit_seed": "matching satisfied parent solution checkpointed at 12 decimal places",
        "claim_boundaries": [
            "synthetic authored sketches; no STEP import, inference, B-Rep construction, or graph recompute",
            "Jacobian rank, freedom, and dependent rows are local first-order observations, not global uniqueness or redundancy proofs",
            "over_constrained denotes satisfied dependent equations and can coexist with remaining freedom",
            "inconsistent is reported only for incompatible affine equations; nonlinear failure remains not_converged",
            "line dimensions are signed x/y differences; general distance is positive Euclidean length",
            "tangency is signed infinite-line to full-circle support tangency, not finite-segment or arc tangency",
            "arcs are counterclockwise with sweep strictly between zero and 2pi; angle branches and seeds are explicit",
            "fixed mm/rad residual scaling and bounded examples do not establish robustness across coordinate scales or singularities",
            "geometry domain: positive radii, nonzero lines, finite parameter magnitudes at most 1e6; at most 32 entities and 128 constraints",
            "inconsistent, invalid_geometry, and not_converged outputs are diagnostic iterates, never accepted solved sketches",
        ],
    }))
    write_figures(output, observations)
    if not all(o.checks_pass for o in observations):
        raise RuntimeError("sketch control failed; inspect generated observations")
    return observations


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-dir", type=Path, default=Path("fixtures/sketch-constraints"))
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument("--refresh-fixtures", action="store_true")
    args = parser.parse_args()
    observations = run(args.output_dir, args.fixture_dir, refresh=args.refresh_fixtures)
    print(f"Wrote {len(observations)} sketch controls and 3 dimension edits to {args.output_dir}; all checks pass")


if __name__ == "__main__":
    main()
