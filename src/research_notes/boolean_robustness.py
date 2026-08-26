"""Evaluate controlled Boolean operations and fuzzy-tolerance behavior."""

from __future__ import annotations

import importlib.metadata
from dataclasses import dataclass
from typing import Literal

from research_notes.brep_runtime import StepRoundTrip, step_round_trip
from research_notes.modeling_common import ShapeMetrics, measure_shape


Operation = Literal["fuse", "common", "cut"]
Stage = Literal["constructed", "step_imported"]
Cuboid = tuple[float, float, float, float, float, float]
CONTRACT_VERSION = "1.0.0"


@dataclass(frozen=True)
class BooleanControl:
    """Two cuboids, one operation, and independent exact-set truth."""

    control_id: str
    operation: Operation
    relationship: str
    first_cuboid: Cuboid
    second_cuboid: Cuboid
    requested_fuzzy_value: float
    expected_solid_count: int
    expected_exact_volume: float
    expected_exact_surface_area: float
    expects_exact_set_measure: bool


@dataclass(frozen=True)
class BooleanDecision:
    """Native outcome and invariants that do not require STEP exchange."""

    control_id: str
    is_done: bool
    applied_fuzzy_value: float
    has_history: bool
    first_operand_unchanged: bool
    second_operand_unchanged: bool
    commutative_invariants_match: bool | None
    reverse_volume_difference: float | None
    reverse_surface_area_difference: float | None


@dataclass(frozen=True)
class BooleanObservation:
    """One Boolean result before or after STEP exchange."""

    stage: Stage
    control_id: str
    source_file: str | None
    source_sha256: str | None
    metrics: ShapeMetrics
    expected_exact_volume: float
    expected_exact_surface_area: float
    volume_exact_set_difference: float
    surface_area_exact_set_difference: float


@dataclass(frozen=True)
class BooleanProbe:
    """Complete v0.46.0 Boolean and tolerance evidence."""

    controls: tuple[BooleanControl, ...]
    decisions: tuple[BooleanDecision, ...]
    fixtures: tuple[StepRoundTrip, ...]
    observations: tuple[BooleanObservation, ...]
    preview_shapes: tuple[tuple[str, object], ...]
    binding_distribution_version: str


def _inside(cuboid: Cuboid, point: tuple[float, float, float]) -> bool:
    x_min, y_min, z_min, x_max, y_max, z_max = cuboid
    x_value, y_value, z_value = point
    return (
        x_min < x_value < x_max
        and y_min < y_value < y_max
        and z_min < z_value < z_max
    )


def exact_axis_aligned_measure(
    first: Cuboid,
    second: Cuboid,
    operation: Operation,
) -> tuple[float, float]:
    """Return independent exact volume and surface area by occupied cells."""
    x_values = sorted({first[0], first[3], second[0], second[3]})
    y_values = sorted({first[1], first[4], second[1], second[4]})
    z_values = sorted({first[2], first[5], second[2], second[5]})
    occupied: set[tuple[int, int, int]] = set()
    for x_index in range(len(x_values) - 1):
        for y_index in range(len(y_values) - 1):
            for z_index in range(len(z_values) - 1):
                midpoint = (
                    (x_values[x_index] + x_values[x_index + 1]) / 2.0,
                    (y_values[y_index] + y_values[y_index + 1]) / 2.0,
                    (z_values[z_index] + z_values[z_index + 1]) / 2.0,
                )
                in_first = _inside(first, midpoint)
                in_second = _inside(second, midpoint)
                selected = {
                    "fuse": in_first or in_second,
                    "common": in_first and in_second,
                    "cut": in_first and not in_second,
                }[operation]
                if selected:
                    occupied.add((x_index, y_index, z_index))

    volume = 0.0
    area = 0.0
    for x_index, y_index, z_index in occupied:
        dx = x_values[x_index + 1] - x_values[x_index]
        dy = y_values[y_index + 1] - y_values[y_index]
        dz = z_values[z_index + 1] - z_values[z_index]
        volume += dx * dy * dz
        for neighbor, face_area in (
            ((x_index - 1, y_index, z_index), dy * dz),
            ((x_index + 1, y_index, z_index), dy * dz),
            ((x_index, y_index - 1, z_index), dx * dz),
            ((x_index, y_index + 1, z_index), dx * dz),
            ((x_index, y_index, z_index - 1), dx * dy),
            ((x_index, y_index, z_index + 1), dx * dy),
        ):
            if neighbor not in occupied:
                area += face_area
    return volume, area


def boolean_controls() -> tuple[BooleanControl, ...]:
    """Return exact overlap, separation, contact, and fuzzy-gap controls."""
    overlap_a: Cuboid = (0.0, 0.0, 0.0, 4.0, 4.0, 4.0)
    overlap_b: Cuboid = (2.0, 1.0, 1.0, 6.0, 5.0, 5.0)
    small_a: Cuboid = (0.0, 0.0, 0.0, 2.0, 2.0, 2.0)
    cases = (
        ("overlap_fuse", "fuse", "volume_overlap", overlap_a, overlap_b, 0.0, 1, True),
        ("overlap_common", "common", "volume_overlap", overlap_a, overlap_b, 0.0, 1, True),
        ("overlap_cut", "cut", "volume_overlap", overlap_a, overlap_b, 0.0, 1, True),
        (
            "disjoint_fuse", "fuse", "positive_gap", small_a,
            (3.0, 0.0, 0.0, 5.0, 2.0, 2.0), 0.0, 2, True,
        ),
        (
            "face_touching_fuse", "fuse", "shared_face", small_a,
            (2.0, 0.0, 0.0, 4.0, 2.0, 2.0), 0.0, 1, True,
        ),
        (
            "near_gap_fuse_default", "fuse", "gap_0.00005", small_a,
            (2.00005, 0.0, 0.0, 4.00005, 2.0, 2.0), 0.0, 2, True,
        ),
        (
            "near_gap_fuse_fuzzy", "fuse", "gap_0.00005", small_a,
            (2.00005, 0.0, 0.0, 4.00005, 2.0, 2.0), 0.0001, 1, False,
        ),
    )
    controls: list[BooleanControl] = []
    for control_id, operation, relationship, first, second, fuzzy, solids, exact in cases:
        volume, area = exact_axis_aligned_measure(first, second, operation)  # type: ignore[arg-type]
        controls.append(
            BooleanControl(
                control_id,
                operation,  # type: ignore[arg-type]
                relationship,
                first,
                second,
                fuzzy,
                solids,
                volume,
                area,
                exact,
            )
        )
    return tuple(controls)


def _make_box(cuboid: Cuboid) -> object:
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt

    x_min, y_min, z_min, x_max, y_max, z_max = cuboid
    return BRepPrimAPI_MakeBox(
        gp_Pnt(x_min, y_min, z_min),
        x_max - x_min,
        y_max - y_min,
        z_max - z_min,
    ).Shape()


def _operate(operation: Operation, first: object, second: object, fuzzy: float) -> tuple[object, object]:
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
    from OCP.TopTools import TopTools_ListOfShape

    builder_class = {
        "fuse": BRepAlgoAPI_Fuse,
        "common": BRepAlgoAPI_Common,
        "cut": BRepAlgoAPI_Cut,
    }[operation]
    arguments = TopTools_ListOfShape()
    arguments.Append(first)
    tools = TopTools_ListOfShape()
    tools.Append(second)
    builder = builder_class()
    builder.SetArguments(arguments)
    builder.SetTools(tools)
    builder.SetRunParallel(False)
    builder.SetNonDestructive(True)
    if fuzzy > 0.0:
        builder.SetFuzzyValue(fuzzy)
    builder.Build()
    if not builder.IsDone():
        raise RuntimeError(f"controlled {operation} operation failed")
    return builder.Shape(), builder


def _topology(metrics: ShapeMetrics) -> tuple[int, int, int, int, int]:
    return (
        metrics.vertex_count,
        metrics.edge_count,
        metrics.face_count,
        metrics.shell_count,
        metrics.solid_count,
    )


def _observe(
    control: BooleanControl,
    stage: Stage,
    shape: object,
    fixture: StepRoundTrip | None,
) -> BooleanObservation:
    metrics = measure_shape(shape)
    return BooleanObservation(
        stage,
        control.control_id,
        None if fixture is None else fixture.file_name,
        None if fixture is None else fixture.source_sha256,
        metrics,
        control.expected_exact_volume,
        control.expected_exact_surface_area,
        abs(metrics.absolute_volume - control.expected_exact_volume),
        abs(metrics.surface_area - control.expected_exact_surface_area),
    )


def probe_boolean_robustness() -> BooleanProbe:
    """Run the complete deterministic v0.46.0 Boolean study."""
    controls = boolean_controls()
    decisions: list[BooleanDecision] = []
    fixtures: list[StepRoundTrip] = []
    observations: list[BooleanObservation] = []
    previews: list[tuple[str, object]] = []
    for control in controls:
        first = _make_box(control.first_cuboid)
        second = _make_box(control.second_cuboid)
        first_before = measure_shape(first)
        second_before = measure_shape(second)
        result, builder = _operate(
            control.operation,
            first,
            second,
            control.requested_fuzzy_value,
        )
        first_after = measure_shape(first)
        second_after = measure_shape(second)
        reverse_match: bool | None = None
        reverse_volume_difference: float | None = None
        reverse_area_difference: float | None = None
        if control.operation in {"fuse", "common"}:
            reverse_result, _ = _operate(
                control.operation,
                second,
                first,
                control.requested_fuzzy_value,
            )
            forward_metrics = measure_shape(result)
            reverse_metrics = measure_shape(reverse_result)
            reverse_volume_difference = abs(
                forward_metrics.absolute_volume - reverse_metrics.absolute_volume
            )
            reverse_area_difference = abs(
                forward_metrics.surface_area - reverse_metrics.surface_area
            )
            reverse_match = (
                _topology(forward_metrics) == _topology(reverse_metrics)
                and forward_metrics.surface_counts == reverse_metrics.surface_counts
                and reverse_volume_difference <= 1.0e-8
                and reverse_area_difference <= 1.0e-8
            )
        decisions.append(
            BooleanDecision(
                control.control_id,
                bool(builder.IsDone()),
                float(builder.FuzzyValue()),
                bool(builder.HasHistory()),
                first_before == first_after,
                second_before == second_after,
                reverse_match,
                reverse_volume_difference,
                reverse_area_difference,
            )
        )
        fixture = step_round_trip(result, control.control_id)
        fixtures.append(fixture)
        observations.append(_observe(control, "constructed", result, None))
        observations.append(_observe(control, "step_imported", fixture.imported_shape, fixture))
        previews.append((control.control_id, fixture.imported_shape))
    return BooleanProbe(
        controls,
        tuple(decisions),
        tuple(fixtures),
        tuple(observations),
        tuple(previews),
        importlib.metadata.version("cadquery-ocp"),
    )
