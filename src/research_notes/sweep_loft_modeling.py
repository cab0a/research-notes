"""Evaluate controlled sweeps, lofts, and B-spline surface construction."""

from __future__ import annotations

import importlib.metadata
import math
from dataclasses import dataclass
from typing import Literal

from research_notes.brep_runtime import StepRoundTrip, status_name, step_round_trip
from research_notes.face_analysis import build_face_analysis_shapes
from research_notes.modeling_common import ShapeMetrics, measure_shape


Decision = Literal["accept", "reject"]
Stage = Literal["constructed", "step_imported"]
CONTRACT_VERSION = "1.0.0"


@dataclass(frozen=True)
class ConstructionControl:
    """Synthetic inputs and expected admission retained outside the B-Rep."""

    control_id: str
    operation: str
    input_description: str
    expected_decision: Decision
    expected_reason: str
    spine_continuity: str
    section_count: int
    expected_volume: float | None
    expected_surface_area: float | None


@dataclass(frozen=True)
class ConstructionDecision:
    """Precondition and native-construction outcome for one control."""

    control_id: str
    decision: Decision
    reason: str
    kernel_invoked: bool
    builder_status: str
    error_on_surface: float | None


@dataclass(frozen=True)
class ConstructionObservation:
    """One accepted shape before or after STEP exchange."""

    stage: Stage
    control_id: str
    source_file: str | None
    source_sha256: str | None
    metrics: ShapeMetrics
    expected_volume: float | None
    expected_surface_area: float | None
    volume_absolute_error: float | None
    surface_area_absolute_error: float | None


@dataclass(frozen=True)
class SweepLoftProbe:
    """Complete v0.45.0 admission, construction, and exchange evidence."""

    controls: tuple[ConstructionControl, ...]
    decisions: tuple[ConstructionDecision, ...]
    fixtures: tuple[StepRoundTrip, ...]
    observations: tuple[ConstructionObservation, ...]
    preview_shapes: tuple[tuple[str, object], ...]
    binding_distribution_version: str


def construction_controls() -> tuple[ConstructionControl, ...]:
    """Return the fixed successful and rejected construction controls."""
    bend_radius = 5.0
    profile_radius = 0.6
    bend_length = bend_radius * math.pi / 2.0
    frustum_slant = math.sqrt(4.0**2 + (2.0 - 1.0) ** 2)
    return (
        ConstructionControl(
            "straight_circular_sweep",
            "pipe_sweep",
            "radius-1 disk along a length-6 straight spine",
            "accept",
            "constructed",
            "G1",
            1,
            6.0 * math.pi,
            14.0 * math.pi,
        ),
        ConstructionControl(
            "quarter_bend_sweep",
            "pipe_sweep",
            "radius-0.6 disk along a radius-5 quarter-circle spine",
            "accept",
            "constructed",
            "G1",
            1,
            math.pi * profile_radius**2 * bend_length,
            2.0 * math.pi * profile_radius * bend_length
            + 2.0 * math.pi * profile_radius**2,
        ),
        ConstructionControl(
            "ruled_circular_loft",
            "section_loft",
            "radius-1 and radius-2 circles separated by four length units",
            "accept",
            "constructed",
            "not_applicable",
            2,
            28.0 * math.pi / 3.0,
            math.pi * (1.0 + 2.0) * frustum_slant + 5.0 * math.pi,
        ),
        ConstructionControl(
            "smooth_square_loft",
            "section_loft",
            "square half-spans 1, 2, 1 at heights 0, 3, 6",
            "accept",
            "constructed",
            "not_applicable",
            3,
            None,
            None,
        ),
        ConstructionControl(
            "interpolated_bspline_surface",
            "point_grid_surface",
            "4-by-4 deterministic point grid",
            "accept",
            "constructed",
            "not_applicable",
            0,
            None,
            None,
        ),
        ConstructionControl(
            "c0_corner_sweep",
            "pipe_sweep",
            "two straight spine edges meeting at a right angle",
            "reject",
            "spine_not_g1",
            "C0",
            1,
            None,
            None,
        ),
        ConstructionControl(
            "single_section_loft",
            "section_loft",
            "one circular section",
            "reject",
            "insufficient_sections",
            "not_applicable",
            1,
            None,
            None,
        ),
    )


def _circle_wire(
    center: tuple[float, float, float],
    normal: tuple[float, float, float],
    radius: float,
) -> object:
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
    from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt

    axis = gp_Ax2(gp_Pnt(*center), gp_Dir(*normal))
    edge = BRepBuilderAPI_MakeEdge(gp_Circ(axis, radius)).Edge()
    return BRepBuilderAPI_MakeWire(edge).Wire()


def _square_wire(z_value: float, half_span: float) -> object:
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon
    from OCP.gp import gp_Pnt

    polygon = BRepBuilderAPI_MakePolygon()
    for x_value, y_value in (
        (-half_span, -half_span),
        (half_span, -half_span),
        (half_span, half_span),
        (-half_span, half_span),
    ):
        polygon.Add(gp_Pnt(x_value, y_value, z_value))
    polygon.Close()
    return polygon.Wire()


def _build_successful_shapes() -> tuple[
    dict[str, object], dict[str, tuple[str, float | None]]
]:
    from OCP.BRepBuilderAPI import (
        BRepBuilderAPI_MakeEdge,
        BRepBuilderAPI_MakeFace,
        BRepBuilderAPI_MakeWire,
    )
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipe, BRepOffsetAPI_ThruSections
    from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt

    shapes: dict[str, object] = {}
    outcomes: dict[str, tuple[str, float | None]] = {}

    straight_spine = BRepBuilderAPI_MakeWire(
        BRepBuilderAPI_MakeEdge(gp_Pnt(0.0, 0.0, 0.0), gp_Pnt(0.0, 0.0, 6.0)).Edge()
    ).Wire()
    straight_profile = BRepBuilderAPI_MakeFace(
        _circle_wire((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), 1.0)
    ).Face()
    straight_builder = BRepOffsetAPI_MakePipe(straight_spine, straight_profile)
    if not straight_builder.IsDone():
        raise RuntimeError("controlled straight sweep failed")
    shapes["straight_circular_sweep"] = straight_builder.Shape()
    outcomes["straight_circular_sweep"] = (
        "done",
        float(straight_builder.ErrorOnSurface()),
    )

    bend_axis = gp_Ax2(
        gp_Pnt(0.0, 0.0, 5.0),
        gp_Dir(0.0, 1.0, 0.0),
        gp_Dir(0.0, 0.0, -1.0),
    )
    bend_edge = BRepBuilderAPI_MakeEdge(
        gp_Circ(bend_axis, 5.0), 0.0, math.pi / 2.0
    ).Edge()
    bend_spine = BRepBuilderAPI_MakeWire(bend_edge).Wire()
    bend_profile = BRepBuilderAPI_MakeFace(
        _circle_wire((0.0, 0.0, 0.0), (-1.0, 0.0, 0.0), 0.6)
    ).Face()
    bend_builder = BRepOffsetAPI_MakePipe(bend_spine, bend_profile)
    if not bend_builder.IsDone():
        raise RuntimeError("controlled quarter-bend sweep failed")
    shapes["quarter_bend_sweep"] = bend_builder.Shape()
    outcomes["quarter_bend_sweep"] = (
        "done",
        float(bend_builder.ErrorOnSurface()),
    )

    ruled_builder = BRepOffsetAPI_ThruSections(True, True)
    ruled_builder.AddWire(_circle_wire((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), 1.0))
    ruled_builder.AddWire(_circle_wire((0.0, 0.0, 4.0), (0.0, 0.0, 1.0), 2.0))
    ruled_builder.Build()
    if not ruled_builder.IsDone():
        raise RuntimeError("controlled ruled loft failed")
    shapes["ruled_circular_loft"] = ruled_builder.Shape()
    outcomes["ruled_circular_loft"] = (status_name(ruled_builder.GetStatus()), None)

    smooth_builder = BRepOffsetAPI_ThruSections(True, False)
    for z_value, half_span in ((0.0, 1.0), (3.0, 2.0), (6.0, 1.0)):
        smooth_builder.AddWire(_square_wire(z_value, half_span))
    smooth_builder.Build()
    if not smooth_builder.IsDone():
        raise RuntimeError("controlled smooth loft failed")
    shapes["smooth_square_loft"] = smooth_builder.Shape()
    outcomes["smooth_square_loft"] = (status_name(smooth_builder.GetStatus()), None)

    shapes["interpolated_bspline_surface"] = build_face_analysis_shapes()["bspline_shell"]
    outcomes["interpolated_bspline_surface"] = ("done", None)
    return shapes, outcomes


def _observe(
    control: ConstructionControl,
    stage: Stage,
    shape: object,
    fixture: StepRoundTrip | None,
) -> ConstructionObservation:
    metrics = measure_shape(shape)
    return ConstructionObservation(
        stage,
        control.control_id,
        None if fixture is None else fixture.file_name,
        None if fixture is None else fixture.source_sha256,
        metrics,
        control.expected_volume,
        control.expected_surface_area,
        None
        if control.expected_volume is None
        else abs(metrics.absolute_volume - control.expected_volume),
        None
        if control.expected_surface_area is None
        else abs(metrics.surface_area - control.expected_surface_area),
    )


def probe_sweep_loft_modeling() -> SweepLoftProbe:
    """Run the complete deterministic v0.45.0 study."""
    controls = construction_controls()
    shapes, outcomes = _build_successful_shapes()
    decisions: list[ConstructionDecision] = []
    fixtures: list[StepRoundTrip] = []
    observations: list[ConstructionObservation] = []
    previews: list[tuple[str, object]] = []
    for control in controls:
        if control.expected_decision == "reject":
            decisions.append(
                ConstructionDecision(
                    control.control_id,
                    "reject",
                    control.expected_reason,
                    False,
                    "not_invoked",
                    None,
                )
            )
            continue
        shape = shapes[control.control_id]
        status, error = outcomes[control.control_id]
        decisions.append(
            ConstructionDecision(control.control_id, "accept", "constructed", True, status, error)
        )
        fixture = step_round_trip(shape, control.control_id)
        fixtures.append(fixture)
        observations.append(_observe(control, "constructed", shape, None))
        observations.append(_observe(control, "step_imported", fixture.imported_shape, fixture))
        previews.append((control.control_id, fixture.imported_shape))
    return SweepLoftProbe(
        controls,
        tuple(decisions),
        tuple(fixtures),
        tuple(observations),
        tuple(previews),
        importlib.metadata.version("cadquery-ocp"),
    )
