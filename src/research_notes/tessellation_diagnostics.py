"""Generate traceable tessellations for controlled STEP-derived B-Rep faces."""

from __future__ import annotations

import importlib.metadata
import math
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from research_notes.brep_runtime import (
    StepRoundTrip,
    indexed_shapes,
    status_name,
    step_round_trip,
    surface_area_and_centroid,
)
from research_notes.face_analysis import build_face_analysis_shapes


Vector2 = tuple[float, float]
Vector3 = tuple[float, float, float]
TriangleVertices = tuple[Vector3, Vector3, Vector3]
TriangleUVs = tuple[Vector2, Vector2, Vector2]
CONTRACT_VERSION = "1.0.0"
SOURCE_MAPPING_METHOD = (
    "XSControl_TransferReader.EntityFromShapeResult(mode=1):"
    "interface_model_position_to_part21_instance"
)


@dataclass(frozen=True)
class MeshCondition:
    """One absolute, single-threaded pair of meshing controls."""

    condition_id: str
    linear_deflection: float
    angular_deflection_radians: float
    linear_level: str
    angular_level: str


@dataclass(frozen=True)
class TessellationControl:
    """One deterministic geometry control with declared topology purpose."""

    control_id: str
    condition: str
    expected_face_count: int
    expected_surface_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class FaceSourceReference:
    """Direct controlled mapping from one local face to one STEP entity."""

    control_id: str
    analysis_face_index: int
    source_entity_id: str | None
    source_entity_type: str | None
    mapping_method: str


@dataclass(frozen=True)
class TessellationTriangle:
    """One triangle with local face, STEP source, and sampled-error evidence."""

    contract_version: str
    control_id: str
    source_file: str
    source_sha256: str
    mesh_condition: str
    requested_linear_deflection: float
    requested_angular_deflection_radians: float
    relative_deflection: bool
    parallel_meshing: bool
    mesher_status_flags: int
    analysis_face_index: int
    source_entity_id: str | None
    source_entity_type: str | None
    source_mapping_method: str
    surface_type: str
    face_orientation: str
    analysis_triangle_index: int
    node_indices: tuple[int, int, int]
    vertices: TriangleVertices
    uv_nodes: TriangleUVs | None
    centroid: Vector3
    oriented_normal: Vector3 | None
    area: float
    is_degenerate: bool
    barycentric_uv: Vector2 | None
    sampled_surface_point: Vector3 | None
    sampled_surface_deviation: float | None


@dataclass(frozen=True)
class TessellationFaceObservation:
    """Per-face mesh inventory and comparison with exact B-Rep surface area."""

    contract_version: str
    control_id: str
    source_file: str
    source_sha256: str
    mesh_condition: str
    requested_linear_deflection: float
    requested_angular_deflection_radians: float
    relative_deflection: bool
    parallel_meshing: bool
    mesher_status_flags: int
    analysis_face_index: int
    source_entity_id: str | None
    source_entity_type: str | None
    source_mapping_method: str
    surface_type: str
    face_orientation: str
    node_count: int
    triangle_count: int
    degenerate_triangle_count: int
    has_uv_nodes: bool
    has_normals: bool
    stored_deflection: float
    exact_surface_area: float
    mesh_surface_area: float
    signed_area_difference: float
    absolute_area_difference: float
    relative_area_difference: float
    maximum_sampled_surface_deviation: float | None
    mean_sampled_surface_deviation: float | None


@dataclass(frozen=True)
class TessellationProbe:
    """Complete v0.42.0 controls, fixtures, provenance, and mesh evidence."""

    controls: tuple[TessellationControl, ...]
    conditions: tuple[MeshCondition, ...]
    fixtures: tuple[StepRoundTrip, ...]
    source_references: tuple[FaceSourceReference, ...]
    faces: tuple[TessellationFaceObservation, ...]
    triangles: tuple[TessellationTriangle, ...]
    binding_distribution_version: str


def mesh_conditions() -> tuple[MeshCondition, ...]:
    """Return the fixed two-by-two absolute deflection design."""
    return (
        MeshCondition("coarse_both", 0.8, 0.7, "coarse", "coarse"),
        MeshCondition("fine_angular", 0.8, 0.25, "coarse", "fine"),
        MeshCondition("fine_linear", 0.05, 0.7, "fine", "coarse"),
        MeshCondition("fine_both", 0.05, 0.25, "fine", "fine"),
    )


def tessellation_controls() -> tuple[TessellationControl, ...]:
    """Return controls for trims, analytic curvature, and free-form curvature."""
    return (
        TessellationControl(
            "meshing_through_hole",
            "Closed solid with planar trims, inner wires, and one cylinder",
            7,
            (("plane", 6), ("cylinder", 1)),
        ),
        TessellationControl(
            "meshing_sphere",
            "Closed periodic analytic surface",
            1,
            (("sphere", 1),),
        ),
        TessellationControl(
            "meshing_bspline_shell",
            "Open shell with one bounded bicubic B-spline face",
            1,
            (("bspline", 1),),
        ),
    )


def build_tessellation_shapes() -> dict[str, object]:
    """Build the three deterministic v0.42.0 geometry controls."""
    existing = build_face_analysis_shapes()
    return {
        "meshing_through_hole": existing["through_hole_solid"],
        "meshing_sphere": existing["spherical_solid"],
        "meshing_bspline_shell": existing["bspline_shell"],
    }


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


def _orientation_name(face: object) -> str:
    from OCP.TopAbs import (
        TopAbs_EXTERNAL,
        TopAbs_FORWARD,
        TopAbs_INTERNAL,
        TopAbs_REVERSED,
    )

    return {
        TopAbs_FORWARD: "forward",
        TopAbs_REVERSED: "reversed",
        TopAbs_INTERNAL: "internal",
        TopAbs_EXTERNAL: "external",
    }.get(face.Orientation(), status_name(face.Orientation()).removeprefix("TopAbs_").lower())


def _source_instance_ids(source_bytes: bytes) -> tuple[str, ...]:
    pattern = re.compile(rb"(?m)^\s*#([0-9]+)\s*=")
    return tuple(
        f"#{match.group(1).decode('ascii')}" for match in pattern.finditer(source_bytes)
    )


def _source_constructor(source_bytes: bytes, instance_id: str) -> str | None:
    pattern = re.compile(
        rb"(?m)^\s*"
        + re.escape(instance_id.encode("ascii"))
        + rb"\s*=\s*([A-Z][A-Z0-9_]*)\s*\("
    )
    match = pattern.search(source_bytes)
    return None if match is None else match.group(1).decode("ascii")


def _model_position(model: object, entity: object) -> int:
    for position in range(1, int(model.NbEntities()) + 1):
        if model.Value(position) == entity:
            return position
    return 0


def _read_fixture_with_source_references(
    fixture: StepRoundTrip,
) -> tuple[object, tuple[FaceSourceReference, ...]]:
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopoDS import TopoDS

    instance_ids = _source_instance_ids(fixture.source_bytes)
    with tempfile.TemporaryDirectory(prefix="research-notes-tessellation-") as directory:
        path = Path(directory) / fixture.file_name
        path.write_bytes(fixture.source_bytes)
        reader = STEPControl_Reader()
        read_status = reader.ReadFile(str(path))
        if read_status != IFSelect_RetDone:
            raise RuntimeError(f"STEP read failed for {fixture.fixture_id}")
        if int(reader.TransferRoots()) < 1:
            raise RuntimeError(f"STEP transfer produced no roots for {fixture.fixture_id}")
        shape = reader.OneShape()
        model = reader.StepModel()
        transfer_reader = reader.WS().TransferReader()
        if len(instance_ids) != int(model.NbEntities()):
            raise RuntimeError("Part 21 instances and interface-model entities diverged")
        face_map = indexed_shapes(shape, TopAbs_FACE)
        references: list[FaceSourceReference] = []
        for face_index in range(1, face_map.Extent() + 1):
            face = TopoDS.Face_s(face_map.FindKey(face_index))
            entity = transfer_reader.EntityFromShapeResult(face, 1)
            if entity is None:
                references.append(
                    FaceSourceReference(
                        fixture.fixture_id,
                        face_index,
                        None,
                        None,
                        "unavailable:transfer_history_has_no_face_result",
                    )
                )
                continue
            position = _model_position(model, entity)
            if position == 0:
                raise RuntimeError("transferred face entity is absent from STEP model")
            instance_id = instance_ids[position - 1]
            constructor = _source_constructor(fixture.source_bytes, instance_id)
            references.append(
                FaceSourceReference(
                    fixture.fixture_id,
                    face_index,
                    instance_id,
                    constructor,
                    SOURCE_MAPPING_METHOD,
                )
            )
    return shape, tuple(references)


def _xyz(point: object) -> Vector3:
    return (float(point.X()), float(point.Y()), float(point.Z()))


def _uv(point: object) -> Vector2:
    return (float(point.X()), float(point.Y()))


def _subtract(first: Vector3, second: Vector3) -> Vector3:
    return tuple(
        first_value - second_value
        for first_value, second_value in zip(first, second, strict=True)
    )  # type: ignore[return-value]


def _cross(first: Vector3, second: Vector3) -> Vector3:
    return (
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    )


def _magnitude(vector: Vector3) -> float:
    return math.sqrt(sum(value * value for value in vector))


def _mean_vectors(vectors: tuple[Vector3, Vector3, Vector3]) -> Vector3:
    return tuple(sum(vector[axis] for vector in vectors) / 3.0 for axis in range(3))  # type: ignore[return-value]


def _distance(first: Vector3, second: Vector3) -> float:
    return _magnitude(_subtract(first, second))


def _mesh_shape(
    shape: object,
    *,
    control: TessellationControl,
    fixture: StepRoundTrip,
    references: tuple[FaceSourceReference, ...],
    condition: MeshCondition,
) -> tuple[tuple[TessellationFaceObservation, ...], tuple[TessellationTriangle, ...]]:
    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.BRepTools import BRepTools
    from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS

    BRepTools.Clean_s(shape, True)
    mesher = BRepMesh_IncrementalMesh(
        shape,
        condition.linear_deflection,
        False,
        condition.angular_deflection_radians,
        False,
    )
    if not mesher.IsDone():
        raise RuntimeError(f"meshing failed for {control.control_id}")
    status_flags = int(mesher.GetStatusFlags())
    face_map = indexed_shapes(shape, TopAbs_FACE)
    reference_by_face = {item.analysis_face_index: item for item in references}
    face_rows: list[TessellationFaceObservation] = []
    triangle_rows: list[TessellationTriangle] = []
    for face_index in range(1, face_map.Extent() + 1):
        face = TopoDS.Face_s(face_map.FindKey(face_index))
        reference = reference_by_face[face_index]
        location = TopLoc_Location()
        triangulation = BRep_Tool.Triangulation_s(face, location)
        if triangulation is None:
            raise RuntimeError(
                f"face {face_index} has no triangulation for {control.control_id}"
            )
        transformation = location.Transformation()
        adaptor = BRepAdaptor_Surface(face, True)
        orientation = _orientation_name(face)
        face_triangles: list[TessellationTriangle] = []
        for triangle_index in range(1, triangulation.NbTriangles() + 1):
            triangle = triangulation.Triangle(triangle_index)
            node_indices = tuple(int(triangle.Value(slot)) for slot in (1, 2, 3))
            vertices = tuple(
                _xyz(triangulation.Node(node_index).Transformed(transformation))
                for node_index in node_indices
            )
            edge_one = _subtract(vertices[1], vertices[0])
            edge_two = _subtract(vertices[2], vertices[0])
            cross = _cross(edge_one, edge_two)
            doubled_area = _magnitude(cross)
            is_degenerate = doubled_area <= 1.0e-15
            normal: Vector3 | None = None
            if not is_degenerate:
                normal = tuple(value / doubled_area for value in cross)  # type: ignore[assignment]
                if face.Orientation() == TopAbs_REVERSED:
                    normal = tuple(-value for value in normal)  # type: ignore[assignment]
            centroid = _mean_vectors(vertices)  # type: ignore[arg-type]
            uv_nodes: TriangleUVs | None = None
            barycentric_uv: Vector2 | None = None
            sampled_surface_point: Vector3 | None = None
            sampled_deviation: float | None = None
            if triangulation.HasUVNodes():
                uv_nodes = tuple(
                    _uv(triangulation.UVNode(node_index))
                    for node_index in node_indices
                )  # type: ignore[assignment]
                barycentric_uv = (
                    sum(item[0] for item in uv_nodes) / 3.0,
                    sum(item[1] for item in uv_nodes) / 3.0,
                )
                sampled_surface_point = _xyz(adaptor.Value(*barycentric_uv))
                sampled_deviation = _distance(
                    centroid, sampled_surface_point
                )
            face_triangles.append(
                TessellationTriangle(
                    CONTRACT_VERSION,
                    control.control_id,
                    fixture.file_name,
                    fixture.source_sha256,
                    condition.condition_id,
                    condition.linear_deflection,
                    condition.angular_deflection_radians,
                    False,
                    False,
                    status_flags,
                    face_index,
                    reference.source_entity_id,
                    reference.source_entity_type,
                    reference.mapping_method,
                    _surface_type(face),
                    orientation,
                    triangle_index,
                    node_indices,  # type: ignore[arg-type]
                    vertices,  # type: ignore[arg-type]
                    uv_nodes,
                    centroid,
                    normal,
                    0.5 * doubled_area,
                    is_degenerate,
                    barycentric_uv,
                    sampled_surface_point,
                    sampled_deviation,
                )
            )
        exact_area, _ = surface_area_and_centroid(face)
        mesh_area = sum(item.area for item in face_triangles)
        signed_difference = mesh_area - exact_area
        deviations = [
            item.sampled_surface_deviation
            for item in face_triangles
            if item.sampled_surface_deviation is not None
        ]
        face_rows.append(
            TessellationFaceObservation(
                CONTRACT_VERSION,
                control.control_id,
                fixture.file_name,
                fixture.source_sha256,
                condition.condition_id,
                condition.linear_deflection,
                condition.angular_deflection_radians,
                False,
                False,
                status_flags,
                face_index,
                reference.source_entity_id,
                reference.source_entity_type,
                reference.mapping_method,
                _surface_type(face),
                orientation,
                int(triangulation.NbNodes()),
                int(triangulation.NbTriangles()),
                sum(item.is_degenerate for item in face_triangles),
                bool(triangulation.HasUVNodes()),
                bool(triangulation.HasNormals()),
                float(triangulation.Deflection()),
                exact_area,
                mesh_area,
                signed_difference,
                abs(signed_difference),
                abs(signed_difference) / exact_area,
                max(deviations, default=None),
                None if not deviations else sum(deviations) / len(deviations),
            )
        )
        triangle_rows.extend(face_triangles)
    return tuple(face_rows), tuple(triangle_rows)


def _surface_counts(
    rows: tuple[TessellationFaceObservation, ...],
) -> tuple[tuple[str, int], ...]:
    order = ("plane", "cylinder", "sphere", "bspline")
    return tuple(
        (surface_type, sum(item.surface_type == surface_type for item in rows))
        for surface_type in order
        if any(item.surface_type == surface_type for item in rows)
    )


def probe_tessellation_diagnostics() -> TessellationProbe:
    """Run the complete deterministic v0.42.0 tessellation experiment."""
    controls = tessellation_controls()
    conditions = mesh_conditions()
    shapes = build_tessellation_shapes()
    fixtures: list[StepRoundTrip] = []
    source_references: list[FaceSourceReference] = []
    face_rows: list[TessellationFaceObservation] = []
    triangle_rows: list[TessellationTriangle] = []
    for control in controls:
        fixture = step_round_trip(shapes[control.control_id], control.control_id)
        imported_shape, references = _read_fixture_with_source_references(fixture)
        fixtures.append(fixture)
        source_references.extend(references)
        if len(references) != control.expected_face_count:
            raise RuntimeError(f"face source inventory changed for {control.control_id}")
        if any(item.source_entity_type != "ADVANCED_FACE" for item in references):
            raise RuntimeError(f"face source mapping changed for {control.control_id}")
        for condition in conditions:
            faces, triangles = _mesh_shape(
                imported_shape,
                control=control,
                fixture=fixture,
                references=references,
                condition=condition,
            )
            if len(faces) != control.expected_face_count:
                raise RuntimeError(f"face inventory changed for {control.control_id}")
            if _surface_counts(faces) != control.expected_surface_counts:
                raise RuntimeError(f"surface inventory changed for {control.control_id}")
            face_rows.extend(faces)
            triangle_rows.extend(triangles)
    return TessellationProbe(
        controls,
        conditions,
        tuple(fixtures),
        tuple(source_references),
        tuple(face_rows),
        tuple(triangle_rows),
        importlib.metadata.version("cadquery-ocp"),
    )
