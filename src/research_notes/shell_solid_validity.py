"""Evaluate controlled shell and solid validity from topology and geometry."""

from __future__ import annotations

import hashlib
import importlib.metadata
import math
import re
import tempfile
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from research_notes.geometry_kernel import normalize_ocp_step_bytes


ValidityStage = Literal["constructed", "step_imported"]
Vector3 = tuple[float, float, float]


@dataclass(frozen=True)
class ShellSolidControl:
    """Independent topology and analytic-volume truth for one synthetic case."""

    control_id: str
    condition: str
    origin: Vector3
    shape_class: Literal["solid", "shell"]
    expected_vertex_count: int
    expected_edge_count: int
    expected_face_count: int
    expected_face_component_count: int
    expected_boundary_edge_count: int
    expected_nonmanifold_edge_count: int
    expected_euler_characteristic: int
    expected_closed_by_incidence: bool
    expected_orientable_manifold: bool
    analytic_volume_magnitude: float | None


@dataclass(frozen=True)
class EdgeIncidenceObservation:
    """Face-boundary uses and relative orientation for one unique edge."""

    stage: ValidityStage
    control_id: str
    edge_index: int
    use_count: int
    incident_face_count: int
    incident_face_indices: tuple[int, ...]
    orientations: tuple[str, ...]
    boundary: bool
    manifold_pair: bool
    nonmanifold: bool
    paired_orientations_opposed: bool | None


@dataclass(frozen=True)
class FaceComponentObservation:
    """One connected face component and its local topological invariants."""

    stage: ValidityStage
    control_id: str
    component_index: int
    face_indices: tuple[int, ...]
    vertex_count: int
    edge_count: int
    face_count: int
    euler_characteristic: int
    boundary_edge_count: int
    nonmanifold_edge_count: int
    closed_by_incidence: bool


@dataclass(frozen=True)
class KernelShellObservation:
    """One backend shell check kept separate from whole-shape validity."""

    stage: ValidityStage
    control_id: str
    shell_index: int
    orientation: str
    vertex_count: int
    edge_count: int
    face_count: int
    closed_status: str
    orientation_status: str


@dataclass(frozen=True)
class ShellSolidObservation:
    """Independent graph evidence and backend reports for one controlled shape."""

    stage: ValidityStage
    control_id: str
    condition: str
    observed_shape_type: str
    vertex_count: int
    edge_count: int
    face_count: int
    shell_count: int
    solid_count: int
    face_component_count: int
    boundary_edge_count: int
    boundary_component_count: int
    boundary_degree_violation_count: int
    manifold_pair_edge_count: int
    nonmanifold_edge_count: int
    euler_characteristic: int
    closed_by_incidence: bool
    orientable_manifold: bool
    current_orientation_consistent: bool
    minimum_face_flips: int | None
    closed_oriented_shell_candidate: bool
    topology_matches_control: bool
    kernel_analyzer_valid: bool
    kernel_signed_volume: float
    analytic_volume_magnitude: float | None
    volume_contract_eligible: bool
    volume_magnitude_absolute_error: float | None
    volume_sign: str
    kernel_solid_statuses: tuple[str, ...]


@dataclass(frozen=True)
class ShellSolidFixture:
    """One normalized STEP fixture and exchange-level provenance."""

    control_id: str
    file_name: str
    source_bytes: bytes
    source_sha256: str
    writer_status: str
    reader_status: str
    transferred_roots: int
    step_closed_shell_count: int
    step_open_shell_count: int
    step_manifold_solid_brep_count: int
    step_oriented_closed_shell_count: int


@dataclass(frozen=True)
class ShellSolidProbe:
    """Complete constructed and STEP-imported shell/solid evidence."""

    platform_label: str
    binding_distribution_version: str
    binding_module_version: str
    step_processor: str
    fixtures: tuple[ShellSolidFixture, ...]
    observations: tuple[ShellSolidObservation, ...]
    edge_observations: tuple[EdgeIncidenceObservation, ...]
    component_observations: tuple[FaceComponentObservation, ...]
    shell_observations: tuple[KernelShellObservation, ...]


def shell_solid_controls() -> tuple[ShellSolidControl, ...]:
    """Return the fixed valid, open, misoriented, and nonmanifold controls."""
    return (
        ShellSolidControl(
            "valid_box",
            "closed outward box solid",
            (0.0, 0.0, 0.0),
            "solid",
            8,
            12,
            6,
            1,
            0,
            0,
            2,
            True,
            True,
            120.0,
        ),
        ShellSolidControl(
            "reversed_box",
            "closed box solid with the whole shape reversed",
            (10.0, 0.0, 0.0),
            "solid",
            8,
            12,
            6,
            1,
            0,
            0,
            2,
            True,
            True,
            120.0,
        ),
        ShellSolidControl(
            "open_box",
            "box shell with the top face removed",
            (20.0, 0.0, 0.0),
            "shell",
            8,
            12,
            5,
            1,
            4,
            0,
            1,
            False,
            True,
            120.0,
        ),
        ShellSolidControl(
            "flipped_face_box",
            "closed box shell with one face reversed",
            (30.0, 0.0, 0.0),
            "shell",
            8,
            12,
            6,
            1,
            0,
            0,
            2,
            True,
            True,
            120.0,
        ),
        ShellSolidControl(
            "nonmanifold_fan",
            "three triangular faces sharing one edge",
            (40.0, 0.0, 0.0),
            "shell",
            5,
            7,
            3,
            1,
            6,
            1,
            1,
            False,
            False,
            None,
        ),
        ShellSolidControl(
            "valid_torus",
            "closed genus-one torus solid",
            (55.0, 0.0, 0.0),
            "solid",
            1,
            2,
            1,
            1,
            0,
            0,
            0,
            True,
            True,
            18.0 * math.pi**2,
        ),
        ShellSolidControl(
            "disconnected_faces",
            "one shell container holding two disconnected triangular faces",
            (70.0, 0.0, 0.0),
            "shell",
            6,
            6,
            2,
            2,
            6,
            0,
            2,
            False,
            True,
            None,
        ),
    )


def analytic_box_volume(width: float, depth: float, height: float) -> float:
    """Return independent box-volume truth after strict dimension checks."""
    values = (width, depth, height)
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in values):
        raise TypeError("box dimensions must be real numbers")
    if any(not math.isfinite(float(value)) or float(value) <= 0.0 for value in values):
        raise ValueError("box dimensions must be finite and positive")
    return float(width) * float(depth) * float(height)


def analytic_torus_volume(major_radius: float, minor_radius: float) -> float:
    """Return independent torus-volume truth using Pappus's volume formula."""
    values = (major_radius, minor_radius)
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in values):
        raise TypeError("torus radii must be real numbers")
    major = float(major_radius)
    minor = float(minor_radius)
    if not all(math.isfinite(value) and value > 0.0 for value in (major, minor)):
        raise ValueError("torus radii must be finite and positive")
    if major <= minor:
        raise ValueError("major radius must be greater than minor radius")
    return 2.0 * math.pi**2 * major * minor**2


def euler_characteristic(vertex_count: int, edge_count: int, face_count: int) -> int:
    """Return V - E + F for nonnegative topology counts."""
    values = (vertex_count, edge_count, face_count)
    if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
        raise TypeError("topology counts must be integers")
    if any(value < 0 for value in values):
        raise ValueError("topology counts must be nonnegative")
    return vertex_count - edge_count + face_count


def _orientation_name(value: object) -> str:
    from OCP.TopAbs import TopAbs_FORWARD, TopAbs_REVERSED

    if value == TopAbs_FORWARD:
        return "forward"
    if value == TopAbs_REVERSED:
        return "reversed"
    return str(value).rsplit(".", 1)[-1].lower()


def _status_name(value: object) -> str:
    return str(value).rsplit(".", 1)[-1]


def _shape_type_name(shape: object) -> str:
    return str(shape.ShapeType()).rsplit(".", 1)[-1].removeprefix("TopAbs_").lower()


def _indexed_map(shape: object, shape_type: object) -> object:
    from OCP.TopExp import TopExp
    from OCP.TopTools import TopTools_IndexedMapOfShape

    mapping = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(shape, shape_type, mapping)
    return mapping


def _box_faces(origin: Vector3) -> list[object]:
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    from OCP.gp import gp_Pnt

    shape = BRepPrimAPI_MakeBox(gp_Pnt(*origin), 4.0, 5.0, 6.0).Shape()
    faces: list[object] = []
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        faces.append(TopoDS.Face_s(explorer.Current()))
        explorer.Next()
    return faces


def _face_centroid(face: object) -> Vector3:
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    properties = GProp_GProps()
    BRepGProp.SurfaceProperties_s(face, properties)
    point = properties.CentreOfMass()
    return float(point.X()), float(point.Y()), float(point.Z())


def _make_box_shell(
    origin: Vector3, *, omit_top: bool = False, flip_max_x: bool = False
) -> object:
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS, TopoDS_Shell

    builder = BRep_Builder()
    shell = TopoDS_Shell()
    builder.MakeShell(shell)
    for face in _box_faces(origin):
        centroid = _face_centroid(face)
        if omit_top and math.isclose(centroid[2], origin[2] + 6.0, abs_tol=1.0e-12):
            continue
        if flip_max_x and math.isclose(
            centroid[0], origin[0] + 4.0, abs_tol=1.0e-12
        ):
            face = TopoDS.Face_s(face.Reversed())
        builder.Add(shell, face)
    return shell


def _triangle_face(
    first: Vector3,
    second: Vector3,
    third: Vector3,
    *,
    shared_edge: object | None = None,
    reverse_shared: bool = False,
) -> object:
    from OCP.BRepBuilderAPI import (
        BRepBuilderAPI_MakeEdge,
        BRepBuilderAPI_MakeFace,
        BRepBuilderAPI_MakeWire,
    )
    from OCP.TopoDS import TopoDS
    from OCP.gp import gp_Pnt

    first_edge = (
        BRepBuilderAPI_MakeEdge(gp_Pnt(*first), gp_Pnt(*second)).Edge()
        if shared_edge is None
        else shared_edge
    )
    if reverse_shared:
        first_edge = TopoDS.Edge_s(first_edge.Reversed())
    second_edge = BRepBuilderAPI_MakeEdge(gp_Pnt(*second), gp_Pnt(*third)).Edge()
    third_edge = BRepBuilderAPI_MakeEdge(gp_Pnt(*third), gp_Pnt(*first)).Edge()
    wire = BRepBuilderAPI_MakeWire()
    for edge in (first_edge, second_edge, third_edge):
        wire.Add(edge)
    return BRepBuilderAPI_MakeFace(wire.Wire()).Face()


def _make_nonmanifold_fan(origin: Vector3) -> object:
    from OCP.BRep import BRep_Builder
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    from OCP.TopoDS import TopoDS_Shell
    from OCP.gp import gp_Pnt

    x, y, z = origin
    first = (x, y, z)
    second = (x + 3.0, y, z)
    shared = BRepBuilderAPI_MakeEdge(gp_Pnt(*first), gp_Pnt(*second)).Edge()
    faces = (
        _triangle_face(first, second, (x, y + 2.0, z), shared_edge=shared),
        _triangle_face(
            first,
            second,
            (x, y, z + 2.0),
            shared_edge=shared,
            reverse_shared=True,
        ),
        _triangle_face(first, second, (x, y - 2.0, z), shared_edge=shared),
    )
    builder = BRep_Builder()
    shell = TopoDS_Shell()
    builder.MakeShell(shell)
    for face in faces:
        builder.Add(shell, face)
    return shell


def _make_disconnected_faces(origin: Vector3) -> object:
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Shell

    x, y, z = origin
    faces = (
        _triangle_face((x, y, z), (x + 2.0, y, z), (x, y + 2.0, z)),
        _triangle_face(
            (x + 5.0, y, z),
            (x + 7.0, y, z),
            (x + 5.0, y + 2.0, z),
        ),
    )
    builder = BRep_Builder()
    shell = TopoDS_Shell()
    builder.MakeShell(shell)
    for face in faces:
        builder.Add(shell, face)
    return shell


def _construct_control(control: ShellSolidControl) -> object:
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeTorus
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    if control.control_id == "valid_box":
        return BRepPrimAPI_MakeBox(gp_Pnt(*control.origin), 4.0, 5.0, 6.0).Shape()
    if control.control_id == "reversed_box":
        return BRepPrimAPI_MakeBox(
            gp_Pnt(*control.origin), 4.0, 5.0, 6.0
        ).Shape().Reversed()
    if control.control_id == "open_box":
        return _make_box_shell(control.origin, omit_top=True)
    if control.control_id == "flipped_face_box":
        return _make_box_shell(control.origin, flip_max_x=True)
    if control.control_id == "nonmanifold_fan":
        return _make_nonmanifold_fan(control.origin)
    if control.control_id == "valid_torus":
        axis = gp_Ax2(gp_Pnt(*control.origin), gp_Dir(0.0, 0.0, 1.0))
        return BRepPrimAPI_MakeTorus(axis, 4.0, 1.5).Shape()
    if control.control_id == "disconnected_faces":
        return _make_disconnected_faces(control.origin)
    raise ValueError(f"unsupported shell/solid control: {control.control_id}")


def _edge_uses(shape: object, face_map: object, edge_map: object) -> dict[int, list[tuple[int, str]]]:
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    uses: dict[int, list[tuple[int, str]]] = {
        index: [] for index in range(1, int(edge_map.Extent()) + 1)
    }
    face_explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while face_explorer.More():
        face = TopoDS.Face_s(face_explorer.Current())
        face_index = int(face_map.FindIndex(face))
        edge_explorer = TopExp_Explorer(face, TopAbs_EDGE)
        while edge_explorer.More():
            edge = TopoDS.Edge_s(edge_explorer.Current())
            uses[int(edge_map.FindIndex(edge))].append(
                (face_index, _orientation_name(edge.Orientation()))
            )
            edge_explorer.Next()
        face_explorer.Next()
    return uses


def _face_components(face_count: int, uses: dict[int, list[tuple[int, str]]]) -> tuple[tuple[int, ...], ...]:
    adjacency = {index: set() for index in range(1, face_count + 1)}
    for edge_uses in uses.values():
        faces = sorted({face_index for face_index, _ in edge_uses})
        for left in faces:
            adjacency[left].update(right for right in faces if right != left)
    components: list[tuple[int, ...]] = []
    unseen = set(adjacency)
    while unseen:
        start = min(unseen)
        queue = deque([start])
        component: set[int] = set()
        while queue:
            face_index = queue.popleft()
            if face_index in component:
                continue
            component.add(face_index)
            unseen.discard(face_index)
            queue.extend(sorted(adjacency[face_index] - component))
        components.append(tuple(sorted(component)))
    return tuple(components)


def _orientation_contract(
    face_count: int, uses: dict[int, list[tuple[int, str]]]
) -> tuple[bool, bool, int | None]:
    adjacency: dict[int, list[tuple[int, int]]] = {
        index: [] for index in range(1, face_count + 1)
    }
    contradiction = False
    nonmanifold = False
    current_consistent = True
    for edge_uses in uses.values():
        if len(edge_uses) > 2:
            nonmanifold = True
            current_consistent = False
            continue
        if len(edge_uses) != 2:
            continue
        (left_face, left_orientation), (right_face, right_orientation) = edge_uses
        opposed = left_orientation != right_orientation
        current_consistent &= opposed
        required_xor = 0 if opposed else 1
        if left_face == right_face:
            contradiction |= required_xor == 1
            continue
        adjacency[left_face].append((right_face, required_xor))
        adjacency[right_face].append((left_face, required_xor))

    assignments: dict[int, int] = {}
    minimum_flips = 0
    for start in range(1, face_count + 1):
        if start in assignments:
            continue
        assignments[start] = 0
        queue = deque([start])
        group: list[int] = []
        while queue:
            face_index = queue.popleft()
            group.append(face_index)
            for neighbor, required_xor in adjacency[face_index]:
                expected = assignments[face_index] ^ required_xor
                if neighbor in assignments:
                    contradiction |= assignments[neighbor] != expected
                else:
                    assignments[neighbor] = expected
                    queue.append(neighbor)
        ones = sum(assignments[index] for index in group)
        minimum_flips += min(ones, len(group) - ones)
    orientable = not nonmanifold and not contradiction
    return orientable, current_consistent, minimum_flips if orientable else None


def _boundary_graph(
    edge_map: object,
    vertex_map: object,
    uses: dict[int, list[tuple[int, str]]],
) -> tuple[int, int]:
    from OCP.TopAbs import TopAbs_VERTEX
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    adjacency: dict[int, set[int]] = {}
    degrees: dict[int, int] = {}
    for edge_index, edge_uses in uses.items():
        if len(edge_uses) != 1:
            continue
        edge = TopoDS.Edge_s(edge_map.FindKey(edge_index))
        vertices: list[int] = []
        explorer = TopExp_Explorer(edge, TopAbs_VERTEX)
        while explorer.More():
            index = int(vertex_map.FindIndex(explorer.Current()))
            if index not in vertices:
                vertices.append(index)
            explorer.Next()
        if len(vertices) == 1:
            first = second = vertices[0]
        elif len(vertices) == 2:
            first, second = vertices
        else:
            continue
        adjacency.setdefault(first, set()).add(second)
        adjacency.setdefault(second, set()).add(first)
        degrees[first] = degrees.get(first, 0) + 1
        degrees[second] = degrees.get(second, 0) + 1
    component_count = 0
    unseen = set(adjacency)
    while unseen:
        component_count += 1
        queue = deque([min(unseen)])
        while queue:
            vertex = queue.popleft()
            if vertex not in unseen:
                continue
            unseen.remove(vertex)
            queue.extend(sorted(adjacency[vertex] & unseen))
    degree_violations = sum(degree != 2 for degree in degrees.values())
    return component_count, degree_violations


def _component_observations(
    stage: ValidityStage,
    control: ShellSolidControl,
    face_map: object,
    vertex_map: object,
    uses: dict[int, list[tuple[int, str]]],
    components: tuple[tuple[int, ...], ...],
) -> tuple[FaceComponentObservation, ...]:
    from OCP.TopAbs import TopAbs_VERTEX
    from OCP.TopExp import TopExp_Explorer

    observations: list[FaceComponentObservation] = []
    for component_index, face_indices in enumerate(components, start=1):
        face_set = set(face_indices)
        edge_indices = {
            edge_index
            for edge_index, edge_uses in uses.items()
            if any(face_index in face_set for face_index, _ in edge_uses)
        }
        vertex_indices: set[int] = set()
        for face_index in face_indices:
            face = face_map.FindKey(face_index)
            explorer = TopExp_Explorer(face, TopAbs_VERTEX)
            while explorer.More():
                vertex_indices.add(int(vertex_map.FindIndex(explorer.Current())))
                explorer.Next()
        boundary_count = sum(len(uses[index]) == 1 for index in edge_indices)
        nonmanifold_count = sum(len(uses[index]) > 2 for index in edge_indices)
        observations.append(
            FaceComponentObservation(
                stage,
                control.control_id,
                component_index,
                face_indices,
                len(vertex_indices),
                len(edge_indices),
                len(face_indices),
                euler_characteristic(
                    len(vertex_indices), len(edge_indices), len(face_indices)
                ),
                boundary_count,
                nonmanifold_count,
                bool(edge_indices)
                and boundary_count == 0
                and nonmanifold_count == 0
                and all(len(uses[index]) == 2 for index in edge_indices),
            )
        )
    return tuple(observations)


def _kernel_shell_observations(
    shape: object, stage: ValidityStage, control: ShellSolidControl
) -> tuple[KernelShellObservation, ...]:
    from OCP.BRepCheck import BRepCheck_Shell
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_SHELL, TopAbs_VERTEX
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    observations: list[KernelShellObservation] = []
    explorer = TopExp_Explorer(shape, TopAbs_SHELL)
    shell_index = 0
    while explorer.More():
        shell_index += 1
        shell = TopoDS.Shell_s(explorer.Current())
        checker = BRepCheck_Shell(shell)
        observations.append(
            KernelShellObservation(
                stage,
                control.control_id,
                shell_index,
                _orientation_name(shell.Orientation()),
                int(_indexed_map(shell, TopAbs_VERTEX).Extent()),
                int(_indexed_map(shell, TopAbs_EDGE).Extent()),
                int(_indexed_map(shell, TopAbs_FACE).Extent()),
                _status_name(checker.Closed()),
                _status_name(checker.Orientation()),
            )
        )
        explorer.Next()
    return tuple(observations)


def _kernel_solid_statuses(shape: object) -> tuple[str, ...]:
    from OCP.BRepCheck import BRepCheck_Solid
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    statuses: list[str] = []
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    while explorer.More():
        solid = TopoDS.Solid_s(explorer.Current())
        checker = BRepCheck_Solid(solid)
        checker.Minimum()
        names = sorted({_status_name(status) for status in checker.Status()})
        statuses.append("+".join(names))
        explorer.Next()
    return tuple(statuses)


def _measure_shape(
    shape: object, stage: ValidityStage, control: ShellSolidControl
) -> tuple[
    ShellSolidObservation,
    tuple[EdgeIncidenceObservation, ...],
    tuple[FaceComponentObservation, ...],
    tuple[KernelShellObservation, ...],
]:
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import (
        TopAbs_EDGE,
        TopAbs_FACE,
        TopAbs_SHELL,
        TopAbs_SOLID,
        TopAbs_VERTEX,
    )

    face_map = _indexed_map(shape, TopAbs_FACE)
    edge_map = _indexed_map(shape, TopAbs_EDGE)
    vertex_map = _indexed_map(shape, TopAbs_VERTEX)
    shell_map = _indexed_map(shape, TopAbs_SHELL)
    solid_map = _indexed_map(shape, TopAbs_SOLID)
    uses = _edge_uses(shape, face_map, edge_map)
    components = _face_components(int(face_map.Extent()), uses)
    orientable, current_orientation, minimum_flips = _orientation_contract(
        int(face_map.Extent()), uses
    )
    boundary_edge_count = sum(len(edge_uses) == 1 for edge_uses in uses.values())
    manifold_pair_count = sum(len(edge_uses) == 2 for edge_uses in uses.values())
    nonmanifold_edge_count = sum(len(edge_uses) > 2 for edge_uses in uses.values())
    closed_by_incidence = (
        bool(uses)
        and boundary_edge_count == 0
        and nonmanifold_edge_count == 0
        and manifold_pair_count == len(uses)
    )
    boundary_component_count, boundary_degree_violations = _boundary_graph(
        edge_map, vertex_map, uses
    )
    topology_matches = (
        int(vertex_map.Extent()) == control.expected_vertex_count
        and int(edge_map.Extent()) == control.expected_edge_count
        and int(face_map.Extent()) == control.expected_face_count
        and len(components) == control.expected_face_component_count
        and boundary_edge_count == control.expected_boundary_edge_count
        and nonmanifold_edge_count == control.expected_nonmanifold_edge_count
        and euler_characteristic(
            int(vertex_map.Extent()), int(edge_map.Extent()), int(face_map.Extent())
        )
        == control.expected_euler_characteristic
        and closed_by_incidence == control.expected_closed_by_incidence
        and orientable == control.expected_orientable_manifold
    )

    properties = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, properties)
    signed_volume = float(properties.Mass())
    volume_eligible = (
        closed_by_incidence
        and orientable
        and current_orientation
        and len(components) == 1
        and control.analytic_volume_magnitude is not None
    )
    volume_error = (
        abs(abs(signed_volume) - float(control.analytic_volume_magnitude))
        if volume_eligible
        else None
    )
    if abs(signed_volume) < 1.0e-14:
        volume_sign = "zero"
    else:
        volume_sign = "positive" if signed_volume > 0.0 else "negative"

    edge_observations = tuple(
        EdgeIncidenceObservation(
            stage,
            control.control_id,
            edge_index,
            len(edge_uses),
            len({face_index for face_index, _ in edge_uses}),
            tuple(sorted({face_index for face_index, _ in edge_uses})),
            tuple(orientation for _, orientation in edge_uses),
            len(edge_uses) == 1,
            len(edge_uses) == 2,
            len(edge_uses) > 2,
            (
                edge_uses[0][1] != edge_uses[1][1]
                if len(edge_uses) == 2
                else None
            ),
        )
        for edge_index, edge_uses in sorted(uses.items())
    )
    component_observations = _component_observations(
        stage,
        control,
        face_map,
        vertex_map,
        uses,
        components,
    )
    shell_observations = _kernel_shell_observations(shape, stage, control)
    observation = ShellSolidObservation(
        stage,
        control.control_id,
        control.condition,
        _shape_type_name(shape),
        int(vertex_map.Extent()),
        int(edge_map.Extent()),
        int(face_map.Extent()),
        int(shell_map.Extent()),
        int(solid_map.Extent()),
        len(components),
        boundary_edge_count,
        boundary_component_count,
        boundary_degree_violations,
        manifold_pair_count,
        nonmanifold_edge_count,
        euler_characteristic(
            int(vertex_map.Extent()), int(edge_map.Extent()), int(face_map.Extent())
        ),
        closed_by_incidence,
        orientable,
        current_orientation,
        minimum_flips,
        closed_by_incidence and orientable and current_orientation and len(components) == 1,
        topology_matches,
        bool(BRepCheck_Analyzer(shape).IsValid()),
        signed_volume,
        control.analytic_volume_magnitude,
        volume_eligible,
        volume_error,
        volume_sign,
        _kernel_solid_statuses(shape),
    )
    return observation, edge_observations, component_observations, shell_observations


def _step_processor(source_bytes: bytes) -> str:
    match = re.search(rb"'Open CASCADE STEP processor ([^']+)'", source_bytes)
    return (
        "unreported"
        if match is None
        else f"Open CASCADE STEP processor {match.group(1).decode('ascii')}"
    )


def _entity_count(source_bytes: bytes, entity_name: bytes) -> int:
    return len(re.findall(rb"=\s*" + entity_name + rb"\(", source_bytes))


def probe_shell_solid_validity(
    *, platform_label: str = "linux-x64-reference"
) -> ShellSolidProbe:
    """Evaluate controlled topology before and after normalized STEP exchange."""
    if not isinstance(platform_label, str):
        raise TypeError("platform_label must be a string")
    if not platform_label:
        raise ValueError("platform_label must not be empty")

    import OCP
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_AsIs, STEPControl_Reader, STEPControl_Writer

    fixtures: list[ShellSolidFixture] = []
    observations: list[ShellSolidObservation] = []
    edge_observations: list[EdgeIncidenceObservation] = []
    component_observations: list[FaceComponentObservation] = []
    shell_observations: list[KernelShellObservation] = []
    processor_names: set[str] = set()
    with tempfile.TemporaryDirectory(prefix="research-notes-shell-solid-") as directory:
        root = Path(directory)
        for control in shell_solid_controls():
            shape = _construct_control(control)
            measured = _measure_shape(shape, "constructed", control)
            observations.append(measured[0])
            edge_observations.extend(measured[1])
            component_observations.extend(measured[2])
            shell_observations.extend(measured[3])

            file_name = f"{control.control_id}.step"
            path = root / file_name
            writer = STEPControl_Writer()
            transfer_status = writer.Transfer(shape, STEPControl_AsIs)
            if transfer_status != IFSelect_RetDone:
                raise RuntimeError(
                    f"STEP transfer failed for {control.control_id}: "
                    f"{_status_name(transfer_status)}"
                )
            writer_status = writer.Write(str(path))
            if writer_status != IFSelect_RetDone:
                raise RuntimeError(
                    f"STEP write failed for {control.control_id}: "
                    f"{_status_name(writer_status)}"
                )
            source_bytes = normalize_ocp_step_bytes(path.read_bytes())
            path.write_bytes(source_bytes)
            processor_names.add(_step_processor(source_bytes))

            reader = STEPControl_Reader()
            reader_status = reader.ReadFile(str(path))
            if reader_status != IFSelect_RetDone:
                raise RuntimeError(
                    f"STEP read failed for {control.control_id}: "
                    f"{_status_name(reader_status)}"
                )
            transferred_roots = int(reader.TransferRoots())
            imported_shape = reader.OneShape()
            imported = _measure_shape(imported_shape, "step_imported", control)
            observations.append(imported[0])
            edge_observations.extend(imported[1])
            component_observations.extend(imported[2])
            shell_observations.extend(imported[3])
            fixtures.append(
                ShellSolidFixture(
                    control.control_id,
                    file_name,
                    source_bytes,
                    hashlib.sha256(source_bytes).hexdigest(),
                    _status_name(writer_status),
                    _status_name(reader_status),
                    transferred_roots,
                    _entity_count(source_bytes, b"CLOSED_SHELL"),
                    _entity_count(source_bytes, b"OPEN_SHELL"),
                    _entity_count(source_bytes, b"MANIFOLD_SOLID_BREP"),
                    _entity_count(source_bytes, b"ORIENTED_CLOSED_SHELL"),
                )
            )

    if len(processor_names) != 1:
        raise RuntimeError("controlled fixtures reported inconsistent STEP processors")
    return ShellSolidProbe(
        platform_label,
        importlib.metadata.version("cadquery-ocp"),
        str(OCP.__version__),
        processor_names.pop(),
        tuple(fixtures),
        tuple(observations),
        tuple(edge_observations),
        tuple(component_observations),
        tuple(shell_observations),
    )
