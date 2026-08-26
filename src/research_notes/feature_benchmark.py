"""Benchmark bounded B-Rep feature rules under controlled perturbations."""

from __future__ import annotations

import importlib.metadata
import math
from dataclasses import dataclass

from research_notes.brep_runtime import StepRoundTrip, step_round_trip
from research_notes.feature_recognition import (
    FeatureControl,
    _measure_graph,
    _recognize,
    build_feature_shapes,
    feature_controls,
)


CONTRACT_VERSION = "1.0.0"


@dataclass(frozen=True)
class BenchmarkCase:
    """One shape family and perturbation with independent construction truth."""

    case_id: str
    source_control_id: str
    perturbation: str
    expected_type: str | None
    expected_subtype: str | None
    scale_factor: float
    rotation_degrees: float
    assigned_tolerance: float
    healing_applied: bool


@dataclass(frozen=True)
class BenchmarkObservation:
    """One rule outcome before or after STEP exchange."""

    case_id: str
    source_control_id: str
    perturbation: str
    stage: str
    expected_label: str
    observed_label: str
    candidate_count: int
    decision: str
    reason: str
    classification_correct: bool
    dimensions_correct: bool
    source_file: str | None
    source_sha256: str | None


@dataclass(frozen=True)
class FeatureBenchmarkProbe:
    """Complete v0.52.0 robustness benchmark evidence."""

    cases: tuple[BenchmarkCase, ...]
    fixtures: tuple[StepRoundTrip, ...]
    observations: tuple[BenchmarkObservation, ...]
    preview_shapes: tuple[tuple[str, object], ...]
    binding_distribution_version: str


_CONTROL_IDS = (
    "plain_block",
    "through_hole",
    "blind_hole",
    "stepped_block",
    "through_slot",
    "chamfer_operation",
    "fillet_operation",
    "cylindrical_boss",
)


def _case_catalog() -> tuple[BenchmarkCase, ...]:
    controls = {item.control_id: item for item in feature_controls()}
    variants = (
        ("baseline", 1.0, 0.0, 1.0e-7, False),
        ("small_scale", 0.5, 0.0, 1.0e-7, False),
        ("rotated_z_30", 1.0, 30.0, 1.0e-7, False),
        ("tolerance_healed", 1.0, 0.0, 1.0e-3, True),
    )
    rows: list[BenchmarkCase] = []
    for control_id in _CONTROL_IDS:
        control = controls[control_id]
        expected_type = control.expected_candidate_types[0] if control.expected_candidate_types else None
        expected_subtype = control.expected_subtypes[0] if control.expected_subtypes else None
        for perturbation, scale, rotation, tolerance, healed in variants:
            rows.append(
                BenchmarkCase(
                    f"{control_id}_{perturbation}",
                    control_id,
                    perturbation,
                    expected_type,
                    expected_subtype,
                    scale,
                    rotation,
                    tolerance,
                    healed,
                )
            )
    return tuple(rows)


def benchmark_cases() -> tuple[BenchmarkCase, ...]:
    """Return the preregistered 32-case robustness corpus."""
    return _case_catalog()


def _transform_shape(source: object, case: BenchmarkCase) -> object:
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.ShapeFix import ShapeFix_Shape, ShapeFix_ShapeTolerance
    from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf

    shape = source
    if case.scale_factor != 1.0:
        transform = gp_Trsf()
        transform.SetScale(gp_Pnt(0.0, 0.0, 0.0), case.scale_factor)
        shape = BRepBuilderAPI_Transform(shape, transform, True).Shape()
    if case.rotation_degrees:
        transform = gp_Trsf()
        transform.SetRotation(
            gp_Ax1(gp_Pnt(0.0, 0.0, 0.0), gp_Dir(0.0, 0.0, 1.0)),
            math.radians(case.rotation_degrees),
        )
        shape = BRepBuilderAPI_Transform(shape, transform, True).Shape()
    if case.healing_applied:
        tolerance = ShapeFix_ShapeTolerance()
        tolerance.SetTolerance(shape, case.assigned_tolerance)
        healer = ShapeFix_Shape(shape)
        healer.Perform()
        shape = healer.Shape()
    return shape


def _scaled_control(case: BenchmarkCase, source: FeatureControl) -> FeatureControl:
    scale = case.scale_factor
    return FeatureControl(
        case.case_id,
        source.condition,
        source.expected_candidate_types,
        source.expected_subtypes,
        source.history_label,
        None if source.expected_primary_size is None else source.expected_primary_size * scale,
        None if source.expected_secondary_size is None else source.expected_secondary_size * scale,
        None if source.expected_depth is None else source.expected_depth * scale,
        source.expected_angle_degrees,
    )


def _label(candidate: object) -> str:
    return f"{candidate.candidate_type}:{candidate.subtype}"


def _observe(
    case: BenchmarkCase,
    source_control: FeatureControl,
    stage: str,
    shape: object,
    fixture: StepRoundTrip | None,
) -> BenchmarkObservation:
    faces, _ = _measure_graph(case.case_id, stage, shape)
    candidates = _recognize(_scaled_control(case, source_control), stage, faces)
    labels = tuple(sorted(_label(item) for item in candidates))
    observed = "none" if not labels else "|".join(labels)
    expected = (
        "none"
        if case.expected_type is None
        else f"{case.expected_type}:{case.expected_subtype}"
    )
    classification_correct = observed == expected
    dimensions_correct = classification_correct and all(
        item.dimension_matches_truth for item in candidates
    )
    if expected == "none" and not candidates:
        decision = "reject"
        reason = (
            "external_cylinder_not_hole"
            if case.source_control_id == "cylindrical_boss"
            else "no_supported_feature_pattern"
        )
    elif classification_correct and dimensions_correct:
        decision = "accept"
        reason = "matched_feature_and_dimensions"
    elif not candidates:
        decision = "abstain"
        reason = (
            "orientation_outside_axis_aligned_rule"
            if case.rotation_degrees
            else "supported_pattern_not_found"
        )
    elif not classification_correct:
        decision = "incorrect"
        reason = "unexpected_candidate_inventory"
    else:
        decision = "incorrect"
        reason = "dimension_residual_exceeds_contract"
    return BenchmarkObservation(
        case.case_id,
        case.source_control_id,
        case.perturbation,
        stage,
        expected,
        observed,
        len(candidates),
        decision,
        reason,
        classification_correct,
        dimensions_correct,
        None if fixture is None else fixture.file_name,
        None if fixture is None else fixture.source_sha256,
    )


def probe_feature_benchmark() -> FeatureBenchmarkProbe:
    """Evaluate every case before and after deterministic STEP exchange."""
    controls = {item.control_id: item for item in feature_controls()}
    source_shapes = build_feature_shapes()
    cases = benchmark_cases()
    fixtures: list[StepRoundTrip] = []
    observations: list[BenchmarkObservation] = []
    previews: list[tuple[str, object]] = []
    for case in cases:
        shape = _transform_shape(source_shapes[case.source_control_id], case)
        fixture = step_round_trip(shape, f"benchmark_{case.case_id}")
        fixtures.append(fixture)
        source_control = controls[case.source_control_id]
        observations.append(_observe(case, source_control, "constructed", shape, None))
        observations.append(
            _observe(case, source_control, "step_imported", fixture.imported_shape, fixture)
        )
        if case.perturbation == "baseline":
            previews.append((case.source_control_id, fixture.imported_shape))
    return FeatureBenchmarkProbe(
        cases,
        tuple(fixtures),
        tuple(observations),
        tuple(previews),
        importlib.metadata.version("cadquery-ocp"),
    )
