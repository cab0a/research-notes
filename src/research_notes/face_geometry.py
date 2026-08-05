"""Evaluate controlled planar and cylindrical B-Rep face geometry."""

from __future__ import annotations

import hashlib
import importlib.metadata
import math
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from research_notes.geometry_kernel import normalize_ocp_step_bytes


Vector3 = tuple[float, float, float]
UVBounds = tuple[float, float, float, float]
SurfaceKind = Literal["plane", "cylinder"]
FaceStage = Literal["constructed", "step_imported"]


@dataclass(frozen=True)
class FaceControl:
    """Independent input definition for one synthetic analytic face."""

    face_id: str
    surface_type: SurfaceKind
    origin: Vector3
    axis: Vector3
    x_direction: Vector3
    uv_bounds: UVBounds
    constructed_tolerance: float
    reversed: bool
    radius: float | None = None


@dataclass(frozen=True)
class FaceTruth:
    """Analytic truth derived without calling the geometry backend."""

    face_id: str
    surface_type: SurfaceKind
    orientation: Literal["forward", "reversed"]
    area: float
    centroid: Vector3
    uv_bounds: UVBounds
    representative_uv: tuple[float, float]
    representative_point: Vector3
    support_normal: Vector3
    oriented_normal: Vector3
    surface_origin: Vector3
    surface_axis: Vector3
    surface_x_direction: Vector3
    radius: float | None
    constructed_tolerance: float


@dataclass(frozen=True)
class FaceMeasurement:
    """One backend-derived face observation before truth comparison."""

    stage: FaceStage
    surface_type: str
    orientation: str
    area: float
    centroid: Vector3
    uv_bounds: UVBounds
    representative_uv: tuple[float, float]
    representative_point: Vector3
    support_normal: Vector3
    oriented_normal: Vector3
    surface_origin: Vector3
    surface_axis: Vector3
    surface_x_direction: Vector3
    radius: float | None
    face_tolerance: float


@dataclass(frozen=True)
class FaceEvaluation:
    """A matched analytic truth and backend observation with explicit errors."""

    truth: FaceTruth
    measurement: FaceMeasurement
    matched_by: str
    area_absolute_error: float
    centroid_distance: float
    uv_max_absolute_error: float
    representative_point_distance: float
    support_normal_angle_degrees: float
    oriented_normal_angle_degrees: float
    surface_origin_distance: float
    surface_axis_angle_degrees: float
    surface_x_direction_angle_degrees: float
    radius_absolute_error: float | None
    tolerance_delta_from_constructed: float


@dataclass(frozen=True)
class FaceGeometryProbe:
    """Deterministic construction and STEP round-trip evidence."""

    platform_label: str
    binding_distribution_version: str
    binding_module_version: str
    step_processor: str
    writer_status: str
    reader_status: str
    transferred_roots: int
    constructed_valid: bool
    imported_valid: bool
    exported_uncertainty_values: tuple[float, ...]
    source_bytes: bytes
    source_sha256: str
    evaluations: tuple[FaceEvaluation, ...]


def face_controls() -> tuple[FaceControl, ...]:
    """Return the fixed v0.32 planar and cylindrical control catalog."""
    return (
        FaceControl(
            face_id="plane_forward",
            surface_type="plane",
            origin=(0.0, 0.0, 0.0),
            axis=(0.0, 0.0, 1.0),
            x_direction=(1.0, 0.0, 0.0),
            uv_bounds=(-2.0, 3.0, -1.0, 4.0),
            constructed_tolerance=1.0e-4,
            reversed=False,
        ),
        FaceControl(
            face_id="plane_reversed",
            surface_type="plane",
            origin=(20.0, 0.0, 5.0),
            axis=(0.0, 1.0, 0.0),
            x_direction=(1.0, 0.0, 0.0),
            uv_bounds=(-1.0, 2.0, -2.0, 2.0),
            constructed_tolerance=2.0e-4,
            reversed=True,
        ),
        FaceControl(
            face_id="cylinder_forward",
            surface_type="cylinder",
            origin=(10.0, -2.0, 1.0),
            axis=(0.0, 0.0, 1.0),
            x_direction=(1.0, 0.0, 0.0),
            uv_bounds=(0.3, 1.7, -1.0, 4.0),
            constructed_tolerance=3.0e-4,
            reversed=False,
            radius=2.5,
        ),
    )


def _add(left: Vector3, right: Vector3) -> Vector3:
    return tuple(a + b for a, b in zip(left, right, strict=True))  # type: ignore[return-value]


def _subtract(left: Vector3, right: Vector3) -> Vector3:
    return tuple(a - b for a, b in zip(left, right, strict=True))  # type: ignore[return-value]


def _scale(vector: Vector3, scalar: float) -> Vector3:
    return tuple(value * scalar for value in vector)  # type: ignore[return-value]


def _dot(left: Vector3, right: Vector3) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def _cross(left: Vector3, right: Vector3) -> Vector3:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _norm(vector: Vector3) -> float:
    return math.sqrt(_dot(vector, vector))


def _unit(vector: Vector3) -> Vector3:
    magnitude = _norm(vector)
    if magnitude == 0.0:
        raise ValueError("direction vectors must be nonzero")
    return _scale(vector, 1.0 / magnitude)


def _distance(left: Vector3, right: Vector3) -> float:
    return _norm(_subtract(left, right))


def _angle_degrees(left: Vector3, right: Vector3) -> float:
    cosine = max(-1.0, min(1.0, _dot(_unit(left), _unit(right))))
    return math.degrees(math.acos(cosine))


def analytic_face_truth(control: FaceControl) -> FaceTruth:
    """Derive area, centroid, sample point, and normals analytically."""
    if not isinstance(control, FaceControl):
        raise TypeError("control must be a FaceControl")
    u_min, u_max, v_min, v_max = control.uv_bounds
    if not (u_min < u_max and v_min < v_max):
        raise ValueError("UV bounds must be strictly increasing")
    axis = _unit(control.axis)
    x_direction = _unit(control.x_direction)
    if abs(_dot(axis, x_direction)) > 1.0e-12:
        raise ValueError("axis and x_direction must be orthogonal")
    y_direction = _unit(_cross(axis, x_direction))
    u_mid = (u_min + u_max) / 2.0
    v_mid = (v_min + v_max) / 2.0

    if control.surface_type == "plane":
        area = (u_max - u_min) * (v_max - v_min)
        centroid = _add(
            control.origin,
            _add(_scale(x_direction, u_mid), _scale(y_direction, v_mid)),
        )
        representative_point = centroid
        support_normal = axis
    elif control.surface_type == "cylinder":
        if control.radius is None or control.radius <= 0.0:
            raise ValueError("a cylinder control requires a positive radius")
        u_span = u_max - u_min
        area = control.radius * u_span * (v_max - v_min)
        mean_cosine = (math.sin(u_max) - math.sin(u_min)) / u_span
        mean_sine = (math.cos(u_min) - math.cos(u_max)) / u_span
        centroid = _add(
            control.origin,
            _add(
                _scale(x_direction, control.radius * mean_cosine),
                _add(
                    _scale(y_direction, control.radius * mean_sine),
                    _scale(axis, v_mid),
                ),
            ),
        )
        support_normal = _add(
            _scale(x_direction, math.cos(u_mid)),
            _scale(y_direction, math.sin(u_mid)),
        )
        representative_point = _add(
            control.origin,
            _add(_scale(support_normal, control.radius), _scale(axis, v_mid)),
        )
    else:  # pragma: no cover - guarded by the public literal contract
        raise ValueError(f"unsupported surface type: {control.surface_type}")

    oriented_normal = (
        _scale(support_normal, -1.0) if control.reversed else support_normal
    )
    return FaceTruth(
        face_id=control.face_id,
        surface_type=control.surface_type,
        orientation="reversed" if control.reversed else "forward",
        area=area,
        centroid=centroid,
        uv_bounds=control.uv_bounds,
        representative_uv=(u_mid, v_mid),
        representative_point=representative_point,
        support_normal=_unit(support_normal),
        oriented_normal=_unit(oriented_normal),
        surface_origin=control.origin,
        surface_axis=axis,
        surface_x_direction=x_direction,
        radius=control.radius,
        constructed_tolerance=control.constructed_tolerance,
    )


def _gp_xyz(value: object) -> Vector3:
    return (float(value.X()), float(value.Y()), float(value.Z()))


def _construct_shape() -> object:
    from OCP.BRep import BRep_Builder
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.TopoDS import TopoDS, TopoDS_Compound
    from OCP.gp import gp_Ax3, gp_Cylinder, gp_Dir, gp_Pln, gp_Pnt

    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    for control in face_controls():
        axis = gp_Ax3(
            gp_Pnt(*control.origin),
            gp_Dir(*control.axis),
            gp_Dir(*control.x_direction),
        )
        surface = (
            gp_Pln(axis)
            if control.surface_type == "plane"
            else gp_Cylinder(axis, float(control.radius))
        )
        face = BRepBuilderAPI_MakeFace(surface, *control.uv_bounds).Face()
        builder.UpdateFace(face, control.constructed_tolerance)
        if control.reversed:
            face = TopoDS.Face_s(face.Reversed())
        builder.Add(compound, face)
    return compound


def _measure_faces(shape: object, stage: FaceStage) -> tuple[FaceMeasurement, ...]:
    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepGProp import BRepGProp
    from OCP.BRepTools import BRepTools
    from OCP.GProp import GProp_GProps
    from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
    from OCP.TopAbs import TopAbs_FACE, TopAbs_FORWARD, TopAbs_REVERSED
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    from OCP.gp import gp_Pnt, gp_Vec

    observations: list[FaceMeasurement] = []
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        face = TopoDS.Face_s(explorer.Current())
        orientation_value = face.Orientation()
        if orientation_value == TopAbs_FORWARD:
            orientation = "forward"
        elif orientation_value == TopAbs_REVERSED:
            orientation = "reversed"
        else:
            orientation = str(orientation_value).rsplit(".", 1)[-1].lower()

        adaptor = BRepAdaptor_Surface(face, True)
        surface_value = adaptor.GetType()
        if surface_value == GeomAbs_Plane:
            surface_type = "plane"
            surface = adaptor.Plane()
            radius = None
        elif surface_value == GeomAbs_Cylinder:
            surface_type = "cylinder"
            surface = adaptor.Cylinder()
            radius = float(surface.Radius())
        else:
            surface_type = str(surface_value).rsplit(".", 1)[-1].removeprefix(
                "GeomAbs_"
            ).lower()
            raise RuntimeError(f"unexpected controlled surface type: {surface_type}")

        bounds = tuple(float(value) for value in BRepTools.UVBounds_s(face))
        u_mid = (bounds[0] + bounds[1]) / 2.0
        v_mid = (bounds[2] + bounds[3]) / 2.0
        point = gp_Pnt()
        d_u = gp_Vec()
        d_v = gp_Vec()
        adaptor.D1(u_mid, v_mid, point, d_u, d_v)
        support_normal_vector = d_u.Crossed(d_v)
        if support_normal_vector.Magnitude() == 0.0:
            raise RuntimeError("representative surface derivatives are singular")
        support_normal_vector.Normalize()
        oriented_normal_vector = gp_Vec(
            support_normal_vector.X(),
            support_normal_vector.Y(),
            support_normal_vector.Z(),
        )
        if orientation == "reversed":
            oriented_normal_vector.Reverse()

        properties = GProp_GProps()
        BRepGProp.SurfaceProperties_s(face, properties, False, False)
        centroid = properties.CentreOfMass()
        position = surface.Position()
        observations.append(
            FaceMeasurement(
                stage=stage,
                surface_type=surface_type,
                orientation=orientation,
                area=float(properties.Mass()),
                centroid=_gp_xyz(centroid),
                uv_bounds=bounds,  # type: ignore[arg-type]
                representative_uv=(u_mid, v_mid),
                representative_point=_gp_xyz(point),
                support_normal=_gp_xyz(support_normal_vector),
                oriented_normal=_gp_xyz(oriented_normal_vector),
                surface_origin=_gp_xyz(position.Location()),
                surface_axis=_gp_xyz(position.Direction()),
                surface_x_direction=_gp_xyz(position.XDirection()),
                radius=radius,
                face_tolerance=float(BRep_Tool.Tolerance_s(face)),
            )
        )
        explorer.Next()
    return tuple(observations)


def _compare(truth: FaceTruth, measurement: FaceMeasurement) -> FaceEvaluation:
    radius_error = (
        None
        if truth.radius is None or measurement.radius is None
        else abs(measurement.radius - truth.radius)
    )
    return FaceEvaluation(
        truth=truth,
        measurement=measurement,
        matched_by="surface_type_and_nearest_analytic_centroid",
        area_absolute_error=abs(measurement.area - truth.area),
        centroid_distance=_distance(measurement.centroid, truth.centroid),
        uv_max_absolute_error=max(
            abs(observed - expected)
            for observed, expected in zip(
                measurement.uv_bounds, truth.uv_bounds, strict=True
            )
        ),
        representative_point_distance=_distance(
            measurement.representative_point, truth.representative_point
        ),
        support_normal_angle_degrees=_angle_degrees(
            measurement.support_normal, truth.support_normal
        ),
        oriented_normal_angle_degrees=_angle_degrees(
            measurement.oriented_normal, truth.oriented_normal
        ),
        surface_origin_distance=_distance(
            measurement.surface_origin, truth.surface_origin
        ),
        surface_axis_angle_degrees=_angle_degrees(
            measurement.surface_axis, truth.surface_axis
        ),
        surface_x_direction_angle_degrees=_angle_degrees(
            measurement.surface_x_direction, truth.surface_x_direction
        ),
        radius_absolute_error=radius_error,
        tolerance_delta_from_constructed=(
            measurement.face_tolerance - truth.constructed_tolerance
        ),
    )


def _match_measurements(
    measurements: tuple[FaceMeasurement, ...],
) -> tuple[FaceEvaluation, ...]:
    remaining = list(measurements)
    evaluations: list[FaceEvaluation] = []
    for control in face_controls():
        truth = analytic_face_truth(control)
        candidates = [
            item for item in remaining if item.surface_type == truth.surface_type
        ]
        if not candidates:
            raise RuntimeError(f"missing measured {truth.surface_type} face")
        measurement = min(
            candidates, key=lambda item: _distance(item.centroid, truth.centroid)
        )
        remaining.remove(measurement)
        evaluations.append(_compare(truth, measurement))
    if remaining:
        raise RuntimeError("unmatched faces remain after controlled matching")
    return tuple(evaluations)


_UNCERTAINTY_PATTERN = re.compile(
    rb"UNCERTAINTY_MEASURE_WITH_UNIT\(LENGTH_MEASURE\(([0-9.E+-]+)\)"
)
_ASSEMBLY_OCCURRENCE_PATTERN = re.compile(
    rb"(NEXT_ASSEMBLY_USAGE_OCCURRENCE\(')[0-9]+(')"
)


def _normalize_controlled_face_step_bytes(source_bytes: bytes) -> bytes:
    """Normalize the writer fields known to vary for this fixed compound."""
    normalized = normalize_ocp_step_bytes(
        source_bytes, expected_translator_occurrences=8
    )
    occurrence_index = 0

    def replacement(match: re.Match[bytes]) -> bytes:
        nonlocal occurrence_index
        occurrence_index += 1
        return match.group(1) + str(occurrence_index).encode("ascii") + match.group(2)

    normalized = _ASSEMBLY_OCCURRENCE_PATTERN.sub(replacement, normalized)
    if occurrence_index != 3:
        raise ValueError("expected exactly three generated assembly occurrence IDs")
    return normalized


def _status_name(status: object) -> str:
    return str(status).rsplit(".", 1)[-1]


def _step_processor(source_bytes: bytes) -> str:
    match = re.search(rb"'Open CASCADE STEP processor ([^']+)'", source_bytes)
    return (
        "unreported"
        if match is None
        else f"Open CASCADE STEP processor {match.group(1).decode('ascii')}"
    )


def probe_evaluated_face_geometry(
    *, platform_label: str = "linux-x64-reference"
) -> FaceGeometryProbe:
    """Construct, evaluate, exchange, and re-evaluate three analytic faces."""
    if not isinstance(platform_label, str):
        raise TypeError("platform_label must be a string")
    if not platform_label:
        raise ValueError("platform_label must not be empty")

    import OCP
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import (
        STEPControl_AsIs,
        STEPControl_Reader,
        STEPControl_Writer,
    )

    shape = _construct_shape()
    constructed_valid = bool(BRepCheck_Analyzer(shape).IsValid())
    constructed = _measure_faces(shape, "constructed")
    writer_uncertainty = 1.0e-4

    with tempfile.TemporaryDirectory(prefix="research-notes-face-geometry-") as directory:
        raw_path = Path(directory) / "analytic_faces_raw.step"
        normalized_path = Path(directory) / "analytic_faces.step"
        writer = STEPControl_Writer()
        writer.SetTolerance(writer_uncertainty)
        transfer_status = writer.Transfer(shape, STEPControl_AsIs)
        if transfer_status != IFSelect_RetDone:
            raise RuntimeError(
                f"STEP transfer failed: {_status_name(transfer_status)}"
            )
        writer_status = writer.Write(str(raw_path))
        if writer_status != IFSelect_RetDone:
            raise RuntimeError(f"STEP write failed: {_status_name(writer_status)}")
        source_bytes = _normalize_controlled_face_step_bytes(raw_path.read_bytes())
        normalized_path.write_bytes(source_bytes)

        reader = STEPControl_Reader()
        reader_status = reader.ReadFile(str(normalized_path))
        if reader_status != IFSelect_RetDone:
            raise RuntimeError(f"STEP read failed: {_status_name(reader_status)}")
        transferred_roots = int(reader.TransferRoots())
        imported_shape = reader.OneShape()

    imported_valid = bool(BRepCheck_Analyzer(imported_shape).IsValid())
    imported = _measure_faces(imported_shape, "step_imported")
    uncertainty_values = tuple(
        float(match.group(1)) for match in _UNCERTAINTY_PATTERN.finditer(source_bytes)
    )
    evaluations = _match_measurements(constructed) + _match_measurements(imported)
    return FaceGeometryProbe(
        platform_label=platform_label,
        binding_distribution_version=importlib.metadata.version("cadquery-ocp"),
        binding_module_version=str(OCP.__version__),
        step_processor=_step_processor(source_bytes),
        writer_status=_status_name(writer_status),
        reader_status=_status_name(reader_status),
        transferred_roots=transferred_roots,
        constructed_valid=constructed_valid,
        imported_valid=imported_valid,
        exported_uncertainty_values=uncertainty_values,
        source_bytes=source_bytes,
        source_sha256=hashlib.sha256(source_bytes).hexdigest(),
        evaluations=evaluations,
    )
