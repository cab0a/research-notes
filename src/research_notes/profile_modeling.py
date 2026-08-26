"""Evaluate profile-driven extrusion and revolution construction."""

from __future__ import annotations

import importlib.metadata
import math
from dataclasses import dataclass
from typing import Literal

from research_notes.brep_runtime import StepRoundTrip, step_entity_count, step_round_trip
from research_notes.modeling_common import ShapeMetrics, measure_shape


ProfileStage = Literal["constructed", "step_imported"]
CONTRACT_VERSION = "1.0.0"


@dataclass(frozen=True)
class ProfileControl:
    """Synthetic profile and operation truth retained outside the B-Rep."""

    control_id: str
    recompute_family: str
    operation: str
    profile_type: str
    parameters: tuple[tuple[str, float], ...]
    outer_wire_count: int
    inner_wire_count: int
    profile_edge_count: int
    expected_volume: float
    expected_surface_area: float


@dataclass(frozen=True)
class ProfileObservation:
    """One profile-driven result before or after STEP exchange."""

    contract_version: str
    stage: ProfileStage
    control_id: str
    source_file: str | None
    source_sha256: str | None
    metrics: ShapeMetrics
    expected_volume: float
    expected_surface_area: float
    volume_absolute_error: float
    surface_area_absolute_error: float
    step_advanced_face_count: int | None


@dataclass(frozen=True)
class ProfileModelingProbe:
    """Complete v0.44.0 profile, operation, exchange, and recompute evidence."""

    controls: tuple[ProfileControl, ...]
    fixtures: tuple[StepRoundTrip, ...]
    observations: tuple[ProfileObservation, ...]
    preview_shapes: tuple[tuple[str, ProfileStage, object], ...]
    binding_distribution_version: str


def profile_controls() -> tuple[ProfileControl, ...]:
    """Return fixed extrusion, revolution, hole, and recompute controls."""
    return (
        ProfileControl(
            "extruded_rectangle_h5",
            "rectangle_height",
            "linear_extrusion",
            "rectangle",
            (("width", 4.0), ("depth", 3.0), ("height", 5.0)),
            1,
            0,
            4,
            60.0,
            94.0,
        ),
        ProfileControl(
            "extruded_rectangle_h7",
            "rectangle_height",
            "linear_extrusion",
            "rectangle",
            (("width", 4.0), ("depth", 3.0), ("height", 7.0)),
            1,
            0,
            4,
            84.0,
            122.0,
        ),
        ProfileControl(
            "extruded_annulus",
            "annulus_extrusion",
            "linear_extrusion",
            "annulus",
            (("outer_radius", 3.0), ("inner_radius", 1.0), ("height", 4.0)),
            1,
            1,
            2,
            32.0 * math.pi,
            48.0 * math.pi,
        ),
        ProfileControl(
            "revolved_annulus_full",
            "annular_revolution_angle",
            "axis_revolution",
            "radial_rectangle",
            (
                ("inner_radius", 2.0),
                ("outer_radius", 4.0),
                ("height", 3.0),
                ("angle_degrees", 360.0),
            ),
            1,
            0,
            4,
            36.0 * math.pi,
            60.0 * math.pi,
        ),
        ProfileControl(
            "revolved_annulus_half",
            "annular_revolution_angle",
            "axis_revolution",
            "radial_rectangle",
            (
                ("inner_radius", 2.0),
                ("outer_radius", 4.0),
                ("height", 3.0),
                ("angle_degrees", 180.0),
            ),
            1,
            0,
            4,
            18.0 * math.pi,
            30.0 * math.pi + 12.0,
        ),
    )


def _polygon_face(points: tuple[tuple[float, float, float], ...]) -> object:
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
    from OCP.gp import gp_Pnt

    polygon = BRepBuilderAPI_MakePolygon()
    for point in points:
        polygon.Add(gp_Pnt(*point))
    polygon.Close()
    face = BRepBuilderAPI_MakeFace(polygon.Wire())
    if not face.IsDone():
        raise RuntimeError("controlled polygon profile construction failed")
    return face.Face()


def _annulus_face() -> object:
    from OCP.BRepBuilderAPI import (
        BRepBuilderAPI_MakeEdge,
        BRepBuilderAPI_MakeFace,
        BRepBuilderAPI_MakeWire,
    )
    from OCP.TopoDS import TopoDS
    from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt

    axis = gp_Ax2(gp_Pnt(0.0, 0.0, 0.0), gp_Dir(0.0, 0.0, 1.0))
    outer_edge = BRepBuilderAPI_MakeEdge(gp_Circ(axis, 3.0)).Edge()
    inner_edge = BRepBuilderAPI_MakeEdge(gp_Circ(axis, 1.0)).Edge()
    outer_wire = BRepBuilderAPI_MakeWire(outer_edge).Wire()
    inner_wire = BRepBuilderAPI_MakeWire(inner_edge).Wire()
    builder = BRepBuilderAPI_MakeFace(outer_wire)
    builder.Add(TopoDS.Wire_s(inner_wire.Reversed()))
    if not builder.IsDone():
        raise RuntimeError("controlled annulus profile construction failed")
    return builder.Face()


def build_profile_shapes() -> dict[str, object]:
    """Construct every deterministic v0.44.0 profile-driven result."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism, BRepPrimAPI_MakeRevol
    from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Vec

    rectangle = _polygon_face(
        ((0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (4.0, 3.0, 0.0), (0.0, 3.0, 0.0))
    )
    annulus = _annulus_face()
    radial = _polygon_face(
        ((2.0, 0.0, 0.0), (4.0, 0.0, 0.0), (4.0, 0.0, 3.0), (2.0, 0.0, 3.0))
    )
    axis = gp_Ax1(gp_Pnt(0.0, 0.0, 0.0), gp_Dir(0.0, 0.0, 1.0))
    return {
        "extruded_rectangle_h5": BRepPrimAPI_MakePrism(
            rectangle, gp_Vec(0.0, 0.0, 5.0), True, True
        ).Shape(),
        "extruded_rectangle_h7": BRepPrimAPI_MakePrism(
            rectangle, gp_Vec(0.0, 0.0, 7.0), True, True
        ).Shape(),
        "extruded_annulus": BRepPrimAPI_MakePrism(
            annulus, gp_Vec(0.0, 0.0, 4.0), True, True
        ).Shape(),
        "revolved_annulus_full": BRepPrimAPI_MakeRevol(
            radial, axis, 2.0 * math.pi, True
        ).Shape(),
        "revolved_annulus_half": BRepPrimAPI_MakeRevol(
            radial, axis, math.pi, True
        ).Shape(),
    }


def _observe(
    control: ProfileControl,
    stage: ProfileStage,
    shape: object,
    fixture: StepRoundTrip | None,
) -> ProfileObservation:
    metrics = measure_shape(shape)
    return ProfileObservation(
        CONTRACT_VERSION,
        stage,
        control.control_id,
        None if fixture is None else fixture.file_name,
        None if fixture is None else fixture.source_sha256,
        metrics,
        control.expected_volume,
        control.expected_surface_area,
        abs(metrics.absolute_volume - control.expected_volume),
        abs(metrics.surface_area - control.expected_surface_area),
        None
        if fixture is None
        else step_entity_count(fixture.source_bytes, "ADVANCED_FACE"),
    )


def probe_profile_modeling() -> ProfileModelingProbe:
    """Run the complete deterministic v0.44.0 study."""
    controls = profile_controls()
    shapes = build_profile_shapes()
    fixtures: list[StepRoundTrip] = []
    observations: list[ProfileObservation] = []
    previews: list[tuple[str, ProfileStage, object]] = []
    for control in controls:
        constructed = shapes[control.control_id]
        fixture = step_round_trip(constructed, control.control_id)
        fixtures.append(fixture)
        observations.append(_observe(control, "constructed", constructed, None))
        observations.append(
            _observe(control, "step_imported", fixture.imported_shape, fixture)
        )
        previews.extend(
            (
                (control.control_id, "constructed", constructed),
                (control.control_id, "step_imported", fixture.imported_shape),
            )
        )
    return ProfileModelingProbe(
        tuple(controls),
        tuple(fixtures),
        tuple(observations),
        tuple(previews),
        importlib.metadata.version("cadquery-ocp"),
    )
