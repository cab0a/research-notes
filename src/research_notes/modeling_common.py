"""Shared deterministic measurements for controlled B-Rep modeling studies."""

from __future__ import annotations

import math
from dataclasses import dataclass

from research_notes.brep_runtime import (
    indexed_shapes,
    maximum_tolerances,
    signed_volume,
    surface_area_and_centroid,
    topology_counts,
)


Vector3 = tuple[float, float, float]


@dataclass(frozen=True)
class ShapeMetrics:
    """Kernel observations that are meaningful across controlled operations."""

    vertex_count: int
    edge_count: int
    face_count: int
    shell_count: int
    solid_count: int
    absolute_volume: float
    surface_area: float
    surface_centroid: Vector3
    bounds_min: Vector3
    bounds_max: Vector3
    maximum_vertex_tolerance: float
    maximum_edge_tolerance: float
    maximum_face_tolerance: float
    surface_counts: tuple[tuple[str, int], ...]
    analyzer_valid: bool


def _surface_type(face: object) -> str:
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import (
        GeomAbs_BSplineSurface,
        GeomAbs_Cone,
        GeomAbs_Cylinder,
        GeomAbs_Plane,
        GeomAbs_Sphere,
        GeomAbs_Torus,
    )

    surface = BRepAdaptor_Surface(face, True)
    return {
        GeomAbs_Plane: "plane",
        GeomAbs_Cylinder: "cylinder",
        GeomAbs_Cone: "cone",
        GeomAbs_Sphere: "sphere",
        GeomAbs_Torus: "torus",
        GeomAbs_BSplineSurface: "bspline",
    }.get(surface.GetType(), "other")


def surface_inventory(shape: object) -> tuple[tuple[str, int], ...]:
    """Return deterministic support-surface counts for unique faces."""
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopoDS import TopoDS

    face_map = indexed_shapes(shape, TopAbs_FACE)
    values = [
        _surface_type(TopoDS.Face_s(face_map.FindKey(index)))
        for index in range(1, face_map.Extent() + 1)
    ]
    order = ("plane", "cylinder", "cone", "sphere", "torus", "bspline", "other")
    return tuple((name, values.count(name)) for name in order if name in values)


def shape_bounds(shape: object) -> tuple[Vector3, Vector3]:
    """Return the axis-aligned bounds in model coordinates."""
    from OCP.BRepBndLib import BRepBndLib
    from OCP.Bnd import Bnd_Box

    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box, False)
    x_min, y_min, z_min, x_max, y_max, z_max = box.Get()
    return (
        (float(x_min), float(y_min), float(z_min)),
        (float(x_max), float(y_max), float(z_max)),
    )


def measure_shape(shape: object) -> ShapeMetrics:
    """Measure one shape without interpreting construction intent."""
    from OCP.BRepCheck import BRepCheck_Analyzer

    topology = topology_counts(shape)
    area, centroid = surface_area_and_centroid(shape)
    bounds_min, bounds_max = shape_bounds(shape)
    tolerances = maximum_tolerances(shape)
    volume = abs(signed_volume(shape)) if topology[4] else 0.0
    return ShapeMetrics(
        *topology,
        volume,
        area,
        centroid,
        bounds_min,
        bounds_max,
        *tolerances,
        surface_inventory(shape),
        bool(BRepCheck_Analyzer(shape).IsValid()),
    )


def support_parameters(shape: object) -> tuple[tuple[str, tuple[float, ...]], ...]:
    """Return selected analytic and B-spline support parameters by face."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import (
        GeomAbs_BSplineSurface,
        GeomAbs_Cone,
        GeomAbs_Cylinder,
        GeomAbs_Sphere,
        GeomAbs_Torus,
    )
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopoDS import TopoDS

    rows: list[tuple[str, tuple[float, ...]]] = []
    face_map = indexed_shapes(shape, TopAbs_FACE)
    for index in range(1, face_map.Extent() + 1):
        face = TopoDS.Face_s(face_map.FindKey(index))
        adaptor = BRepAdaptor_Surface(face, True)
        kind = adaptor.GetType()
        if kind == GeomAbs_Cylinder:
            rows.append(("cylinder", (float(adaptor.Cylinder().Radius()),)))
        elif kind == GeomAbs_Cone:
            cone = adaptor.Cone()
            rows.append(
                (
                    "cone",
                    (float(cone.RefRadius()), float(cone.SemiAngle())),
                )
            )
        elif kind == GeomAbs_Sphere:
            rows.append(("sphere", (float(adaptor.Sphere().Radius()),)))
        elif kind == GeomAbs_Torus:
            torus = adaptor.Torus()
            rows.append(
                (
                    "torus",
                    (float(torus.MajorRadius()), float(torus.MinorRadius())),
                )
            )
        elif kind == GeomAbs_BSplineSurface:
            surface = adaptor.BSpline()
            rows.append(
                (
                    "bspline",
                    (
                        float(surface.UDegree()),
                        float(surface.VDegree()),
                        float(surface.NbUPoles()),
                        float(surface.NbVPoles()),
                    ),
                )
            )
    return tuple(sorted(rows))


def maximum_parameter_difference(
    first: tuple[tuple[str, tuple[float, ...]], ...],
    second: tuple[tuple[str, tuple[float, ...]], ...],
) -> float | None:
    """Compare like-for-like support parameters without reordering duplicates."""
    if tuple(name for name, _ in first) != tuple(name for name, _ in second):
        return None
    differences = [
        abs(a - b)
        for (_, first_values), (_, second_values) in zip(first, second, strict=True)
        for a, b in zip(first_values, second_values, strict=True)
    ]
    return max(differences, default=0.0)


def vector_distance(first: Vector3, second: Vector3) -> float:
    """Return Euclidean distance for three-dimensional evidence."""
    return math.sqrt(
        sum((a - b) ** 2 for a, b in zip(first, second, strict=True))
    )

