"""Evaluate controlled primitive construction and STEP round trips."""

from __future__ import annotations

import importlib.metadata
import math
from dataclasses import dataclass
from typing import Literal

from research_notes.brep_runtime import StepRoundTrip, step_entity_count, step_round_trip
from research_notes.face_analysis import build_face_analysis_shapes
from research_notes.modeling_common import ShapeMetrics, measure_shape, support_parameters


PrimitiveStage = Literal["constructed", "step_imported"]
CONTRACT_VERSION = "1.0.0"


@dataclass(frozen=True)
class PrimitiveControl:
    """Declared construction parameters and independently known measurements."""

    control_id: str
    construction: str
    parameters: tuple[tuple[str, float], ...]
    expected_surface_counts: tuple[tuple[str, int], ...]
    expected_solid_count: int
    expected_volume: float | None
    expected_surface_area: float | None


@dataclass(frozen=True)
class PrimitiveObservation:
    """One constructed or STEP-imported primitive observation."""

    contract_version: str
    stage: PrimitiveStage
    control_id: str
    source_file: str | None
    source_sha256: str | None
    metrics: ShapeMetrics
    support_parameters: tuple[tuple[str, tuple[float, ...]], ...]
    expected_volume: float | None
    expected_surface_area: float | None
    volume_absolute_error: float | None
    surface_area_absolute_error: float | None
    surface_inventory_matches: bool
    solid_count_matches: bool
    step_entity_count: int | None
    step_advanced_face_count: int | None


@dataclass(frozen=True)
class PrimitiveRoundTripProbe:
    """Complete v0.43.0 construction, exchange, and measurement evidence."""

    controls: tuple[PrimitiveControl, ...]
    fixtures: tuple[StepRoundTrip, ...]
    observations: tuple[PrimitiveObservation, ...]
    preview_shapes: tuple[tuple[str, PrimitiveStage, object], ...]
    binding_distribution_version: str


def primitive_controls() -> tuple[PrimitiveControl, ...]:
    """Return the fixed analytic and free-form primitive catalog."""
    cone_slant = math.sqrt((3.0 - 1.0) ** 2 + 4.0**2)
    return (
        PrimitiveControl(
            "primitive_box",
            "axis-aligned box",
            (("length_x", 4.0), ("length_y", 3.0), ("length_z", 2.0)),
            (("plane", 6),),
            1,
            24.0,
            52.0,
        ),
        PrimitiveControl(
            "primitive_cylinder",
            "right circular cylinder",
            (("radius", 2.0), ("height", 5.0)),
            (("plane", 2), ("cylinder", 1)),
            1,
            20.0 * math.pi,
            28.0 * math.pi,
        ),
        PrimitiveControl(
            "primitive_cone",
            "right circular conical frustum",
            (("base_radius", 3.0), ("top_radius", 1.0), ("height", 4.0)),
            (("plane", 2), ("cone", 1)),
            1,
            52.0 * math.pi / 3.0,
            math.pi * (10.0 + 4.0 * cone_slant),
        ),
        PrimitiveControl(
            "primitive_sphere",
            "complete sphere",
            (("radius", 2.5),),
            (("sphere", 1),),
            1,
            4.0 * math.pi * 2.5**3 / 3.0,
            4.0 * math.pi * 2.5**2,
        ),
        PrimitiveControl(
            "primitive_torus",
            "complete ring torus",
            (("major_radius", 4.0), ("minor_radius", 1.0)),
            (("torus", 1),),
            1,
            8.0 * math.pi**2,
            16.0 * math.pi**2,
        ),
        PrimitiveControl(
            "primitive_bspline_patch",
            "bounded bicubic B-spline face in an open shell",
            (("u_poles", 4.0), ("v_poles", 4.0)),
            (("bspline", 1),),
            0,
            None,
            None,
        ),
    )


def build_primitive_shapes() -> dict[str, object]:
    """Construct every deterministic v0.43.0 primitive."""
    from OCP.BRepPrimAPI import (
        BRepPrimAPI_MakeBox,
        BRepPrimAPI_MakeCone,
        BRepPrimAPI_MakeCylinder,
        BRepPrimAPI_MakeSphere,
        BRepPrimAPI_MakeTorus,
    )

    bspline = build_face_analysis_shapes()["bspline_shell"]
    return {
        "primitive_box": BRepPrimAPI_MakeBox(4.0, 3.0, 2.0).Shape(),
        "primitive_cylinder": BRepPrimAPI_MakeCylinder(2.0, 5.0).Shape(),
        "primitive_cone": BRepPrimAPI_MakeCone(3.0, 1.0, 4.0).Shape(),
        "primitive_sphere": BRepPrimAPI_MakeSphere(2.5).Shape(),
        "primitive_torus": BRepPrimAPI_MakeTorus(4.0, 1.0).Shape(),
        "primitive_bspline_patch": bspline,
    }


def _observe(
    control: PrimitiveControl,
    stage: PrimitiveStage,
    shape: object,
    fixture: StepRoundTrip | None,
) -> PrimitiveObservation:
    metrics = measure_shape(shape)
    volume_error = (
        None
        if control.expected_volume is None
        else abs(metrics.absolute_volume - control.expected_volume)
    )
    area_error = (
        None
        if control.expected_surface_area is None
        else abs(metrics.surface_area - control.expected_surface_area)
    )
    return PrimitiveObservation(
        CONTRACT_VERSION,
        stage,
        control.control_id,
        None if fixture is None else fixture.file_name,
        None if fixture is None else fixture.source_sha256,
        metrics,
        support_parameters(shape),
        control.expected_volume,
        control.expected_surface_area,
        volume_error,
        area_error,
        metrics.surface_counts == control.expected_surface_counts,
        metrics.solid_count == control.expected_solid_count,
        None
        if fixture is None
        else step_entity_count(fixture.source_bytes, "PRODUCT_DEFINITION"),
        None
        if fixture is None
        else step_entity_count(fixture.source_bytes, "ADVANCED_FACE"),
    )


def probe_primitive_round_trips() -> PrimitiveRoundTripProbe:
    """Run the complete deterministic v0.43.0 study."""
    controls = primitive_controls()
    shapes = build_primitive_shapes()
    fixtures: list[StepRoundTrip] = []
    observations: list[PrimitiveObservation] = []
    previews: list[tuple[str, PrimitiveStage, object]] = []
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
    return PrimitiveRoundTripProbe(
        controls=controls,
        fixtures=tuple(fixtures),
        observations=tuple(observations),
        preview_shapes=tuple(previews),
        binding_distribution_version=importlib.metadata.version("cadquery-ocp"),
    )

