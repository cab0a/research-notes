"""Explicit, bounded plate features driven by the v0.56.0 sketch solver."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from research_notes.modeling_common import ShapeMetrics, measure_shape
from research_notes.profile_modeling import _polygon_face
from research_notes.sketch_constraint_study import circle_sketch, rectangle_sketch
from research_notes.sketch_constraints import SketchSolution, solve_sketch


CONTRACT_VERSION = "1.0.0"
MARGIN = 1.0e-4
FEATURE_PARAMETERS = {
    "through_hole": ("x", "y", "radius"),
    "profile_hole": ("x", "y", "radius"),
    "blind_hole": ("x", "y", "radius", "depth"),
    "pocket": ("x", "y", "width", "length", "depth"),
    "boss": ("x", "y", "radius", "height"),
    "rib": ("x", "y", "width", "length", "height"),
}


@dataclass(frozen=True)
class PlateSpec:
    width: float = 12.0
    length: float = 10.0
    thickness: float = 4.0
    origin_x: float = 0.0
    origin_y: float = 0.0
    origin_z: float = 0.0


@dataclass(frozen=True)
class FeatureSpec:
    kind: str
    parameters: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class FeatureBuild:
    shape: object
    metrics: ShapeMetrics
    sketch: SketchSolution


def feature_spec(kind: str, **parameters: float) -> FeatureSpec:
    return FeatureSpec(kind, tuple(sorted(parameters.items())))


def validate_plate(plate: PlateSpec) -> None:
    for value in (plate.width, plate.length, plate.thickness):
        if not math.isfinite(value) or not MARGIN < value <= 1000.0:
            raise ValueError("plate dimensions must be finite and in (0.0001, 1000] mm")
    if any(not math.isfinite(v) or abs(v) > 10000 for v in (plate.origin_x, plate.origin_y, plate.origin_z)):
        raise ValueError("plate origin must be finite and within 10000 mm")


def validate_feature(plate: PlateSpec, feature: FeatureSpec) -> dict[str, float]:
    validate_plate(plate)
    values = dict(feature.parameters)
    if feature.kind not in FEATURE_PARAMETERS or len(values) != len(feature.parameters):
        raise ValueError("unsupported feature kind or duplicate parameter")
    if set(values) != set(FEATURE_PARAMETERS[feature.kind]):
        raise ValueError(f"{feature.kind} requires {FEATURE_PARAMETERS[feature.kind]}")
    if any(not math.isfinite(v) or not MARGIN < v <= 1000 for v in values.values()):
        raise ValueError("feature parameters must be finite and in (0.0001, 1000] mm")
    if "radius" in values:
        x0, x1 = values["x"] - values["radius"], values["x"] + values["radius"]
        y0, y1 = values["y"] - values["radius"], values["y"] + values["radius"]
    else:
        x0, x1 = values["x"], values["x"] + values["width"]
        y0, y1 = values["y"], values["y"] + values["length"]
    if not (x0 > MARGIN and y0 > MARGIN and x1 < plate.width - MARGIN and y1 < plate.length - MARGIN):
        raise ValueError("feature footprint must remain strictly inside the plate")
    if "depth" in values and values["depth"] >= plate.thickness - MARGIN:
        raise ValueError("blind feature must retain a positive floor")
    return values


def rectangle_solution(width: float, length: float) -> SketchSolution:
    sketch = rectangle_sketch()
    constraints = tuple(replace(c, values=(width,)) if c.constraint_id == "width" else
                        replace(c, values=(length,)) if c.constraint_id == "height" else c
                        for c in sketch.constraints)
    result = solve_sketch(replace(sketch, constraints=constraints))
    if result.status != "fully_constrained":
        raise ValueError(f"rectangle sketch failed: {result.status}")
    return result


def circular_solution(x: float, y: float, radius: float) -> SketchSolution:
    sketch = circle_sketch()
    constraints = tuple(replace(c, values=(x, y)) if c.constraint_id == "center" else
                        replace(c, values=(radius,)) for c in sketch.constraints)
    result = solve_sketch(replace(sketch, constraints=constraints))
    if result.status != "fully_constrained":
        raise ValueError(f"circle sketch failed: {result.status}")
    return result


def _rectangle_profile(solution: SketchSolution, x: float, y: float, z: float) -> object:
    points = tuple((x + round(e.parameters[0], 12), y + round(e.parameters[1], 12), z)
                   for e in solution.entities)
    return _polygon_face(points)


def _extrude(face: object, height: float) -> object:
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.gp import gp_Vec

    operation = BRepPrimAPI_MakePrism(face, gp_Vec(0, 0, height), True, True)
    if not operation.IsDone():
        raise RuntimeError("profile extrusion failed")
    return operation.Shape()


def _checked(shape: object, sketch: SketchSolution) -> FeatureBuild:
    metrics = measure_shape(shape)
    if not metrics.analyzer_valid or metrics.solid_count != 1 or metrics.absolute_volume <= 0:
        raise RuntimeError("feature result must be one valid positive-volume solid")
    return FeatureBuild(shape, metrics, sketch)


def build_plate(plate: PlateSpec) -> FeatureBuild:
    validate_plate(plate)
    sketch = rectangle_solution(plate.width, plate.length)
    face = _rectangle_profile(sketch, plate.origin_x, plate.origin_y, plate.origin_z)
    return _checked(_extrude(face, plate.thickness), sketch)


def boolean_shape(first: object, second: object, *, operation: str) -> object:
    """Use serial, non-destructive Boolean operations so cached inputs survive."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
    from OCP.TopTools import TopTools_ListOfShape

    if operation not in {"cut", "fuse"}:
        raise ValueError("unsupported Boolean operation")
    builder = BRepAlgoAPI_Cut() if operation == "cut" else BRepAlgoAPI_Fuse()
    arguments, tools = TopTools_ListOfShape(), TopTools_ListOfShape()
    arguments.Append(first)
    tools.Append(second)
    builder.SetArguments(arguments)
    builder.SetTools(tools)
    builder.SetNonDestructive(True)
    builder.SetRunParallel(False)
    builder.Build()
    if not builder.IsDone():
        raise RuntimeError(f"Boolean {operation} failed")
    return builder.Shape()


def _perforated_plate(plate: PlateSpec, circle: SketchSolution) -> object:
    """Alternative construction: extrude a profile containing an inner wire."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeWire
    from OCP.BRepTools import BRepTools
    from OCP.TopoDS import TopoDS
    from OCP.gp import gp_Ax2, gp_Circ, gp_Dir, gp_Pnt

    outer = _rectangle_profile(rectangle_solution(plate.width, plate.length), plate.origin_x, plate.origin_y, plate.origin_z)
    x, y, radius = (round(v, 12) for v in circle.entities[0].parameters)
    axis = gp_Ax2(gp_Pnt(plate.origin_x + x, plate.origin_y + y, plate.origin_z), gp_Dir(0, 0, 1))
    wire = BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(gp_Circ(axis, radius)).Edge()).Wire()
    face = BRepBuilderAPI_MakeFace(BRepTools.OuterWire_s(outer))
    face.Add(TopoDS.Wire_s(wire.Reversed()))
    if not face.IsDone():
        raise RuntimeError("perforated profile construction failed")
    return _extrude(face.Face(), plate.thickness)


def apply_feature(base: object, plate: PlateSpec, feature: FeatureSpec) -> FeatureBuild:
    """Apply one declared feature; profile_hole requires an unmodified plate."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    p = validate_feature(plate, feature)
    if "radius" in p:
        sketch = circular_solution(p["x"], p["y"], p["radius"])
        x, y, radius = (round(v, 12) for v in sketch.entities[0].parameters)
        if feature.kind == "profile_hole":
            # Do not discard prior features when this full-profile route is used.
            reference = build_plate(plate).shape
            if shape_difference_volume(base, reference) > 1e-8:
                raise ValueError("profile_hole requires an unmodified plate")
            return _checked(_perforated_plate(plate, sketch), sketch)
        if feature.kind == "through_hole":
            z, height = plate.origin_z - 1.0, plate.thickness + 2.0
        elif feature.kind == "blind_hole":
            z, height = plate.origin_z + plate.thickness - p["depth"], p["depth"] + 1.0
        else:
            z, height = plate.origin_z + plate.thickness, p["height"]
        tool = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(plate.origin_x + x, plate.origin_y + y, z), gp_Dir(0, 0, 1)), radius, height).Shape()
    else:
        sketch = rectangle_solution(p["width"], p["length"])
        z = plate.origin_z + plate.thickness - p.get("depth", 0.0)
        height = p["depth"] + 1.0 if feature.kind == "pocket" else p["height"]
        face = _rectangle_profile(sketch, plate.origin_x + p["x"], plate.origin_y + p["y"], z)
        tool = _extrude(face, height)
    mode = "fuse" if feature.kind in {"boss", "rib"} else "cut"
    return _checked(boolean_shape(base, tool, operation=mode), sketch)


def analytic_feature_truth(plate: PlateSpec, feature: FeatureSpec | None = None) -> tuple[float, float]:
    """Closed-form truth only for one feature on an otherwise plain plate."""
    validate_plate(plate)
    w, length, t = plate.width, plate.length, plate.thickness
    volume, area = w * length * t, 2 * (w * length + w * t + length * t)
    if feature is None:
        return volume, area
    p = validate_feature(plate, feature)
    if "radius" in p:
        disk, perimeter = math.pi * p["radius"] ** 2, 2 * math.pi * p["radius"]
        if feature.kind in {"through_hole", "profile_hole"}:
            return volume - disk * t, area - 2 * disk + perimeter * t
        depth = p.get("depth", p.get("height"))
        return volume + (-1 if feature.kind == "blind_hole" else 1) * disk * depth, area + perimeter * depth
    footprint, perimeter = p["width"] * p["length"], 2 * (p["width"] + p["length"])
    depth = p.get("depth", p.get("height"))
    return volume + (-1 if feature.kind == "pocket" else 1) * footprint * depth, area + perimeter * depth


def shape_difference_volume(first: object, second: object) -> float:
    """Same-kernel bidirectional material difference, not an independent oracle."""
    from research_notes.brep_runtime import signed_volume

    return sum(abs(signed_volume(boolean_shape(a, b, operation="cut"))) for a, b in ((first, second), (second, first)))


def feature_controls() -> tuple[tuple[str, PlateSpec, FeatureSpec], ...]:
    plate = PlateSpec()
    return tuple((f"{kind}_{stage}", plate, feature_spec(kind, **values)) for kind, before, after in (
        ("through_hole", dict(x=4., y=5., radius=1.), dict(x=4., y=5., radius=1.5)),
        ("blind_hole", dict(x=4., y=5., radius=1., depth=1.), dict(x=4., y=5., radius=1., depth=2.)),
        ("pocket", dict(x=3., y=3., width=4., length=3., depth=1.), dict(x=3., y=3., width=4., length=3., depth=2.)),
        ("boss", dict(x=4., y=5., radius=1.5, height=2.), dict(x=4., y=5., radius=1.5, height=3.)),
        ("rib", dict(x=3., y=3., width=1., length=5., height=2.), dict(x=3., y=3., width=1.5, length=5., height=2.)),
    ) for stage, values in (("before", before), ("after", after)))
