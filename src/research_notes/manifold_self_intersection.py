"""Evaluate vertex manifoldness, pair contact, and aggregate interference."""

from __future__ import annotations

import importlib.metadata
from collections import deque
from dataclasses import dataclass
from typing import Literal

from research_notes.brep_runtime import (
    StepRoundTrip,
    indexed_shapes,
    shape_type_name,
    step_round_trip,
    topology_counts,
)


Stage = Literal["constructed", "step_imported"]
Vector3 = tuple[float, float, float]


@dataclass(frozen=True)
class ManifoldControl:
    """Independent truth for one synthetic topology or shape-pair case."""

    control_id: str
    condition: str
    expected_vertex_count: int
    expected_edge_count: int
    expected_face_count: int
    expected_nonmanifold_vertex_count: int
    expected_nonmanifold_edge_count: int
    expected_contact_dimension: int | None
    expected_measure: float | None
    checker_level: int | None = None
    expected_edge_edge_interference_count: int | None = None
    expected_edge_face_interference_count: int | None = None
    expected_face_face_interference_count: int | None = None
    expected_self_intersection_dimension: int | None = None
    expected_self_intersection_quantity: float | None = None


@dataclass(frozen=True)
class VertexLinkObservation:
    """Combinatorial link evidence for one analysis-local vertex."""

    stage: Stage
    control_id: str
    vertex_index: int
    x: float
    y: float
    z: float
    incident_edge_count: int
    incident_face_count: int
    link_arc_count: int
    link_component_count: int
    degree_one_count: int
    maximum_degree: int
    classification: str


@dataclass(frozen=True)
class PairRelationObservation:
    """Exact common-part and section evidence for one controlled pair."""

    stage: Stage
    control_id: str
    minimum_distance: float
    common_vertex_count: int
    common_edge_count: int
    common_face_count: int
    common_solid_count: int
    common_length: float
    common_area: float
    common_volume: float
    section_edge_count: int
    section_length: float
    section_enclosed_area: float
    contact_dimension: int
    relationship: str
    expected_measure: float
    measure_absolute_error: float


@dataclass(frozen=True)
class SelfIntersectionObservation:
    """Single-argument checker evidence for one aggregate B-Rep."""

    stage: Stage
    control_id: str
    checker_level: int
    checker_has_errors: bool
    checker_has_warnings: bool
    vertex_vertex_interference_count: int
    vertex_edge_interference_count: int
    edge_edge_interference_count: int
    vertex_face_interference_count: int
    edge_face_interference_count: int
    face_face_interference_count: int
    edge_edge_point_count: int
    face_face_curve_count: int
    intersection_dimension: int
    quantity_kind: str
    intersection_quantity: float
    expected_intersection_quantity: float
    quantity_absolute_error: float
    checker_counts_match_control: bool
    dimension_matches_control: bool
    self_intersection_matches_control: bool


@dataclass(frozen=True)
class ManifoldObservation:
    """Whole-shape topology and vertex-link summary."""

    stage: Stage
    control_id: str
    condition: str
    observed_shape_type: str
    vertex_count: int
    edge_count: int
    face_count: int
    shell_count: int
    solid_count: int
    boundary_edge_count: int
    nonmanifold_edge_count: int
    nonmanifold_vertex_count: int
    topology_matches_control: bool
    relationship_matches_control: bool | None
    self_intersection_matches_control: bool | None


@dataclass(frozen=True)
class ManifoldProbe:
    """Complete before-and-after STEP evidence for all controls."""

    platform_label: str
    binding_distribution_version: str
    binding_module_version: str
    fixtures: tuple[StepRoundTrip, ...]
    observations: tuple[ManifoldObservation, ...]
    vertex_links: tuple[VertexLinkObservation, ...]
    pair_relations: tuple[PairRelationObservation, ...]
    self_intersections: tuple[SelfIntersectionObservation, ...]


def manifold_controls() -> tuple[ManifoldControl, ...]:
    """Return fixed polyhedral manifold and contact controls."""
    return (
        ManifoldControl(
            "valid_tetrahedron", "closed tetrahedron shell", 4, 6, 4, 0, 0, None, None
        ),
        ManifoldControl(
            "pinched_tetrahedra",
            "two tetrahedra sharing one topological vertex",
            7,
            12,
            8,
            1,
            0,
            None,
            None,
        ),
        ManifoldControl(
            "nonmanifold_fan",
            "three triangles sharing one edge",
            5,
            7,
            3,
            2,
            1,
            None,
            None,
        ),
        ManifoldControl(
            "separated_edges",
            "two independent edges with positive separation in one aggregate B-Rep",
            4,
            2,
            0,
            0,
            0,
            None,
            None,
            checker_level=2,
            expected_edge_edge_interference_count=0,
            expected_edge_face_interference_count=0,
            expected_face_face_interference_count=0,
            expected_self_intersection_dimension=-1,
            expected_self_intersection_quantity=0.0,
        ),
        ManifoldControl(
            "crossing_edges",
            "two independent edges crossing at one interior point in one aggregate B-Rep",
            4,
            2,
            0,
            0,
            0,
            None,
            None,
            checker_level=2,
            expected_edge_edge_interference_count=1,
            expected_edge_face_interference_count=0,
            expected_face_face_interference_count=0,
            expected_self_intersection_dimension=0,
            expected_self_intersection_quantity=1.0,
        ),
        ManifoldControl(
            "disjoint_boxes",
            "two boxes separated by one unit",
            16,
            24,
            12,
            0,
            0,
            -1,
            1.0,
        ),
        ManifoldControl(
            "vertex_touching_boxes",
            "two boxes touching at one vertex",
            16,
            24,
            12,
            0,
            0,
            0,
            0.0,
        ),
        ManifoldControl(
            "edge_touching_boxes",
            "two boxes touching along one geometric edge",
            16,
            24,
            12,
            0,
            0,
            1,
            4.0,
        ),
        ManifoldControl(
            "face_touching_boxes",
            "two boxes touching on one geometric face",
            16,
            24,
            12,
            0,
            0,
            2,
            16.0,
        ),
        ManifoldControl(
            "overlapping_boxes",
            "two boxes with a nine-unit volumetric overlap",
            16,
            24,
            12,
            0,
            0,
            3,
            9.0,
        ),
        ManifoldControl(
            "separated_faces",
            "two parallel planar faces separated by one unit in one aggregate B-Rep",
            8,
            8,
            2,
            0,
            0,
            -1,
            1.0,
            checker_level=5,
            expected_edge_edge_interference_count=0,
            expected_edge_face_interference_count=0,
            expected_face_face_interference_count=0,
            expected_self_intersection_dimension=-1,
            expected_self_intersection_quantity=0.0,
        ),
        ManifoldControl(
            "crossing_faces",
            "two independent planar faces crossing in one aggregate B-Rep",
            8,
            8,
            2,
            0,
            0,
            1,
            2.0,
            checker_level=5,
            expected_edge_edge_interference_count=0,
            expected_edge_face_interference_count=2,
            expected_face_face_interference_count=1,
            expected_self_intersection_dimension=1,
            expected_self_intersection_quantity=2.0,
        ),
    )


def _make_vertices(points: tuple[Vector3, ...]) -> tuple[object, ...]:
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.gp import gp_Pnt

    return tuple(BRepBuilderAPI_MakeVertex(gp_Pnt(*point)).Vertex() for point in points)


def _triangle_shell(
    points: tuple[Vector3, ...], faces: tuple[tuple[int, int, int], ...]
) -> object:
    from OCP.BRep import BRep_Builder
    from OCP.BRepBuilderAPI import (
        BRepBuilderAPI_MakeEdge,
        BRepBuilderAPI_MakeFace,
        BRepBuilderAPI_MakeWire,
    )
    from OCP.TopoDS import TopoDS, TopoDS_Shell

    vertices = _make_vertices(points)
    edge_cache: dict[tuple[int, int], object] = {}
    builder = BRep_Builder()
    shell = TopoDS_Shell()
    builder.MakeShell(shell)
    for face_vertices in faces:
        wire_builder = BRepBuilderAPI_MakeWire()
        for first, second in zip(face_vertices, face_vertices[1:] + face_vertices[:1]):
            key = tuple(sorted((first, second)))
            edge = edge_cache.get(key)
            if edge is None:
                low, high = key
                edge = BRepBuilderAPI_MakeEdge(vertices[low], vertices[high]).Edge()
                edge_cache[key] = edge
            if (first, second) != key:
                edge = TopoDS.Edge_s(edge.Reversed())
            wire_builder.Add(edge)
        builder.Add(shell, BRepBuilderAPI_MakeFace(wire_builder.Wire()).Face())
    return shell


def _make_tetrahedron() -> object:
    return _triangle_shell(
        ((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0), (0.0, 0.0, 2.0)),
        ((0, 2, 1), (0, 1, 3), (0, 3, 2), (1, 2, 3)),
    )


def _make_pinched_tetrahedra() -> object:
    return _triangle_shell(
        (
            (0.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (0.0, 2.0, 0.0),
            (0.0, 0.0, 2.0),
            (-2.0, 0.0, 0.0),
            (0.0, -2.0, 0.0),
            (0.0, 0.0, -2.0),
        ),
        (
            (0, 2, 1),
            (0, 1, 3),
            (0, 3, 2),
            (1, 2, 3),
            (0, 4, 5),
            (0, 6, 4),
            (0, 5, 6),
            (4, 6, 5),
        ),
    )


def _make_nonmanifold_fan() -> object:
    return _triangle_shell(
        (
            (0.0, 0.0, 0.0),
            (3.0, 0.0, 0.0),
            (0.0, 2.0, 0.0),
            (0.0, 0.0, 2.0),
            (0.0, -2.0, 0.0),
        ),
        ((0, 1, 2), (1, 0, 3), (0, 1, 4)),
    )


def _compound(items: tuple[object, ...]) -> object:
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound

    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    for item in items:
        builder.Add(compound, item)
    return compound


def _make_edge_pair(*, crossing: bool) -> object:
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    from OCP.gp import gp_Pnt

    coordinates = (
        (((-2.0, -2.0, 0.0), (2.0, 2.0, 0.0)), ((-2.0, 2.0, 0.0), (2.0, -2.0, 0.0)))
        if crossing
        else (
            ((-2.0, -1.0, 0.0), (2.0, -1.0, 0.0)),
            ((-2.0, 1.0, 0.0), (2.0, 1.0, 0.0)),
        )
    )
    edges = tuple(
        BRepBuilderAPI_MakeEdge(gp_Pnt(*first), gp_Pnt(*second)).Edge()
        for first, second in coordinates
    )
    return _compound(edges)


def _make_box_pair(second_origin: Vector3) -> object:
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt

    first = BRepPrimAPI_MakeBox(gp_Pnt(0.0, 0.0, 0.0), 4.0, 4.0, 4.0).Shape()
    second = BRepPrimAPI_MakeBox(gp_Pnt(*second_origin), 4.0, 4.0, 4.0).Shape()
    return _compound((first, second))


def _make_crossing_faces() -> object:
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.gp import gp_Dir, gp_Pln, gp_Pnt

    horizontal = BRepBuilderAPI_MakeFace(
        gp_Pln(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), -2, 2, -2, 2
    ).Face()
    vertical = BRepBuilderAPI_MakeFace(
        gp_Pln(gp_Pnt(0, 0, 0), gp_Dir(0, 1, 0)), -1, 1, -1, 1
    ).Face()
    return _compound((horizontal, vertical))


def _make_separated_faces() -> object:
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.gp import gp_Dir, gp_Pln, gp_Pnt

    lower = BRepBuilderAPI_MakeFace(
        gp_Pln(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), -2, 2, -2, 2
    ).Face()
    upper = BRepBuilderAPI_MakeFace(
        gp_Pln(gp_Pnt(0, 0, 1), gp_Dir(0, 0, 1)), -2, 2, -2, 2
    ).Face()
    return _compound((lower, upper))


def construct_manifold_control(control_id: str) -> object:
    """Construct one deterministic synthetic shape."""
    if control_id == "valid_tetrahedron":
        return _make_tetrahedron()
    if control_id == "pinched_tetrahedra":
        return _make_pinched_tetrahedra()
    if control_id == "nonmanifold_fan":
        return _make_nonmanifold_fan()
    if control_id == "separated_edges":
        return _make_edge_pair(crossing=False)
    if control_id == "crossing_edges":
        return _make_edge_pair(crossing=True)
    origins = {
        "disjoint_boxes": (5.0, 0.0, 0.0),
        "vertex_touching_boxes": (4.0, 4.0, 4.0),
        "edge_touching_boxes": (4.0, 4.0, 0.0),
        "face_touching_boxes": (4.0, 0.0, 0.0),
        "overlapping_boxes": (3.0, 1.0, 1.0),
    }
    if control_id in origins:
        return _make_box_pair(origins[control_id])
    if control_id == "separated_faces":
        return _make_separated_faces()
    if control_id == "crossing_faces":
        return _make_crossing_faces()
    raise ValueError(f"unsupported manifold control: {control_id}")


def _point(vertex: object) -> Vector3:
    from OCP.BRep import BRep_Tool
    from OCP.TopoDS import TopoDS

    value = BRep_Tool.Pnt_s(TopoDS.Vertex_s(vertex))
    return float(value.X()), float(value.Y()), float(value.Z())


def _vertex_links(
    shape: object, stage: Stage, control_id: str
) -> tuple[VertexLinkObservation, ...]:
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_VERTEX
    from OCP.TopExp import TopExp_Explorer

    vertex_map = indexed_shapes(shape, TopAbs_VERTEX)
    edge_map = indexed_shapes(shape, TopAbs_EDGE)
    incident_edges = {index: set() for index in range(1, vertex_map.Extent() + 1)}
    incident_faces = {index: set() for index in range(1, vertex_map.Extent() + 1)}
    arcs = {index: [] for index in range(1, vertex_map.Extent() + 1)}
    face_explorer = TopExp_Explorer(shape, TopAbs_FACE)
    face_index = 0
    while face_explorer.More():
        face_index += 1
        face = face_explorer.Current()
        per_vertex: dict[int, set[int]] = {}
        edge_explorer = TopExp_Explorer(face, TopAbs_EDGE)
        while edge_explorer.More():
            edge = edge_explorer.Current()
            edge_index = int(edge_map.FindIndex(edge))
            vertex_explorer = TopExp_Explorer(edge, TopAbs_VERTEX)
            seen: set[int] = set()
            while vertex_explorer.More():
                vertex_index = int(vertex_map.FindIndex(vertex_explorer.Current()))
                if vertex_index and vertex_index not in seen:
                    seen.add(vertex_index)
                    incident_edges[vertex_index].add(edge_index)
                    incident_faces[vertex_index].add(face_index)
                    per_vertex.setdefault(vertex_index, set()).add(edge_index)
                vertex_explorer.Next()
            edge_explorer.Next()
        for vertex_index, edge_indices in per_vertex.items():
            if len(edge_indices) == 2:
                arcs[vertex_index].append(tuple(sorted(edge_indices)))
        face_explorer.Next()

    rows: list[VertexLinkObservation] = []
    for vertex_index in range(1, vertex_map.Extent() + 1):
        nodes = incident_edges[vertex_index]
        adjacency = {node: [] for node in nodes}
        for left, right in arcs[vertex_index]:
            adjacency[left].append(right)
            adjacency[right].append(left)
        unseen = set(nodes)
        components = 0
        while unseen:
            components += 1
            queue = deque([min(unseen)])
            while queue:
                node = queue.popleft()
                if node not in unseen:
                    continue
                unseen.remove(node)
                queue.extend(adjacency[node])
        degrees = [len(adjacency[node]) for node in sorted(nodes)]
        degree_one = sum(degree == 1 for degree in degrees)
        if nodes and components == 1 and all(degree == 2 for degree in degrees):
            classification = "closed_manifold"
        elif (
            nodes
            and components == 1
            and degree_one == 2
            and all(degree in (1, 2) for degree in degrees)
        ):
            classification = "boundary_manifold"
        else:
            classification = "nonmanifold"
        x, y, z = _point(vertex_map.FindKey(vertex_index))
        rows.append(
            VertexLinkObservation(
                stage,
                control_id,
                vertex_index,
                x,
                y,
                z,
                len(nodes),
                len(incident_faces[vertex_index]),
                len(arcs[vertex_index]),
                components,
                degree_one,
                max(degrees, default=0),
                classification,
            )
        )
    return tuple(rows)


def _edge_use_counts(shape: object) -> tuple[int, int]:
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer

    edge_map = indexed_shapes(shape, TopAbs_EDGE)
    uses = {index: 0 for index in range(1, edge_map.Extent() + 1)}
    faces = TopExp_Explorer(shape, TopAbs_FACE)
    while faces.More():
        edges = TopExp_Explorer(faces.Current(), TopAbs_EDGE)
        while edges.More():
            uses[int(edge_map.FindIndex(edges.Current()))] += 1
            edges.Next()
        faces.Next()
    return sum(value == 1 for value in uses.values()), sum(
        value > 2 for value in uses.values()
    )


def _properties(shape: object) -> tuple[float, float, float]:
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    values: list[float] = []
    for method in (
        BRepGProp.LinearProperties_s,
        BRepGProp.SurfaceProperties_s,
        BRepGProp.VolumeProperties_s,
    ):
        props = GProp_GProps()
        method(shape, props)
        values.append(abs(float(props.Mass())))
    return tuple(values)  # type: ignore[return-value]


def _pair_shapes(shape: object, control_id: str) -> tuple[object, object]:
    from OCP.TopAbs import TopAbs_FACE, TopAbs_SOLID

    face_pair_controls = {"separated_faces", "crossing_faces"}
    shape_type = TopAbs_FACE if control_id in face_pair_controls else TopAbs_SOLID
    mapping = indexed_shapes(shape, shape_type)
    if mapping.Extent() != 2:
        raise RuntimeError(f"{control_id} must contain exactly two pair members")
    return mapping.FindKey(1), mapping.FindKey(2)


def _pair_relation(
    shape: object, stage: Stage, control: ManifoldControl
) -> PairRelationObservation:
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Section
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape

    first, second = _pair_shapes(shape, control.control_id)
    distance = BRepExtrema_DistShapeShape(first, second)
    if not distance.IsDone():
        raise RuntimeError(f"distance calculation failed for {control.control_id}")
    common = BRepAlgoAPI_Common(first, second)
    common.Build()
    if not common.IsDone():
        raise RuntimeError(f"common operation failed for {control.control_id}")
    section = BRepAlgoAPI_Section(first, second)
    section.Build()
    if not section.IsDone():
        raise RuntimeError(f"section operation failed for {control.control_id}")
    common_shape = common.Shape()
    section_shape = section.Shape()
    cv, ce, cf, _, cs = topology_counts(common_shape)
    common_length, common_area, common_volume = _properties(common_shape)
    section_length, _, _ = _properties(section_shape)
    _, section_edges, _, _, _ = topology_counts(section_shape)
    section_area = 0.0
    if section_edges >= 3:
        from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeWire
        from OCP.TopAbs import TopAbs_EDGE
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopoDS import TopoDS

        wire_builder = BRepBuilderAPI_MakeWire()
        edge_explorer = TopExp_Explorer(section_shape, TopAbs_EDGE)
        while edge_explorer.More():
            wire_builder.Add(TopoDS.Edge_s(edge_explorer.Current()))
            edge_explorer.Next()
        if wire_builder.IsDone():
            face_builder = BRepBuilderAPI_MakeFace(wire_builder.Wire())
            if face_builder.IsDone():
                _, section_area, _ = _properties(face_builder.Face())
    epsilon = 1.0e-9
    if common_volume > epsilon:
        dimension = 3
        measure = common_volume
    elif max(common_area, section_area) > epsilon:
        dimension = 2
        measure = max(common_area, section_area)
    elif max(common_length, section_length) > epsilon:
        dimension = 1
        measure = max(common_length, section_length)
    elif cv > 0 or float(distance.Value()) <= epsilon:
        dimension = 0
        measure = 0.0
    else:
        dimension = -1
        measure = float(distance.Value())
    names = {
        -1: "disjoint",
        0: "point_contact",
        1: "edge_contact",
        2: "face_contact",
        3: "volume_overlap",
    }
    relationship = (
        "proper_crossing"
        if control.control_id == "crossing_faces"
        else names[dimension]
    )
    expected = float(control.expected_measure)
    return PairRelationObservation(
        stage,
        control.control_id,
        float(distance.Value()),
        cv,
        ce,
        cf,
        cs,
        common_length,
        common_area,
        common_volume,
        section_edges,
        section_length,
        section_area,
        dimension,
        relationship,
        expected,
        abs(measure - expected),
    )


def _self_intersection(
    shape: object,
    stage: Stage,
    control: ManifoldControl,
    pair_relation: PairRelationObservation | None,
) -> SelfIntersectionObservation | None:
    """Run OCCT's single-argument self-interference checker when preregistered."""
    if control.checker_level is None:
        return None
    from OCP.BOPAlgo import BOPAlgo_CheckerSI
    from OCP.TopAbs import TopAbs_VERTEX

    checker = BOPAlgo_CheckerSI()
    checker.SetLevelOfCheck(control.checker_level)
    checker.SetRunParallel(False)
    checker.SetNonDestructive(True)
    checker.AddArgument(shape)
    checker.Perform()
    data = checker.DS()
    edge_edge = tuple(data.InterfEE())
    face_face = tuple(data.InterfFF())
    edge_edge_points = sum(
        row.CommonPart().Type() == TopAbs_VERTEX for row in edge_edge
    )
    face_face_curves = sum(len(row.Curves()) for row in face_face)
    if face_face_curves:
        if pair_relation is None:
            raise RuntimeError(
                f"missing section evidence for face interference: {control.control_id}"
            )
        dimension = 1
        quantity_kind = "section_length"
        quantity = pair_relation.section_length
    elif edge_edge_points:
        dimension = 0
        quantity_kind = "intersection_point_count"
        quantity = float(edge_edge_points)
    else:
        dimension = -1
        quantity_kind = "none"
        quantity = 0.0
    expected_quantity = float(control.expected_self_intersection_quantity)
    expected_counts = (
        control.expected_edge_edge_interference_count,
        control.expected_edge_face_interference_count,
        control.expected_face_face_interference_count,
    )
    observed_counts = (
        len(edge_edge),
        len(data.InterfEF()),
        len(face_face),
    )
    counts_match = observed_counts == expected_counts
    dimension_match = dimension == control.expected_self_intersection_dimension
    quantity_error = abs(quantity - expected_quantity)
    matches = (
        not checker.HasErrors()
        and not checker.HasWarnings()
        and counts_match
        and dimension_match
        and quantity_error < 1.0e-8
    )
    return SelfIntersectionObservation(
        stage,
        control.control_id,
        control.checker_level,
        bool(checker.HasErrors()),
        bool(checker.HasWarnings()),
        len(data.InterfVV()),
        len(data.InterfVE()),
        len(edge_edge),
        len(data.InterfVF()),
        len(data.InterfEF()),
        len(face_face),
        edge_edge_points,
        face_face_curves,
        dimension,
        quantity_kind,
        quantity,
        expected_quantity,
        quantity_error,
        counts_match,
        dimension_match,
        matches,
    )


def _measure(shape: object, stage: Stage, control: ManifoldControl) -> tuple[
    ManifoldObservation,
    tuple[VertexLinkObservation, ...],
    PairRelationObservation | None,
    SelfIntersectionObservation | None,
]:
    vertices, edges, faces, shells, solids = topology_counts(shape)
    links = () if faces == 0 else _vertex_links(shape, stage, control.control_id)
    boundary_edges, nonmanifold_edges = _edge_use_counts(shape)
    nonmanifold_vertices = sum(row.classification == "nonmanifold" for row in links)
    relation = (
        None
        if control.expected_contact_dimension is None
        else _pair_relation(shape, stage, control)
    )
    self_intersection = _self_intersection(shape, stage, control, relation)
    topology_match = (
        vertices,
        edges,
        faces,
        nonmanifold_vertices,
        nonmanifold_edges,
    ) == (
        control.expected_vertex_count,
        control.expected_edge_count,
        control.expected_face_count,
        control.expected_nonmanifold_vertex_count,
        control.expected_nonmanifold_edge_count,
    )
    relation_match = (
        None
        if relation is None
        else relation.contact_dimension == control.expected_contact_dimension
        and relation.measure_absolute_error < 1.0e-8
    )
    return (
        ManifoldObservation(
            stage,
            control.control_id,
            control.condition,
            shape_type_name(shape),
            vertices,
            edges,
            faces,
            shells,
            solids,
            boundary_edges,
            nonmanifold_edges,
            nonmanifold_vertices,
            topology_match,
            relation_match,
            (
                None
                if self_intersection is None
                else self_intersection.self_intersection_matches_control
            ),
        ),
        links,
        relation,
        self_intersection,
    )


def probe_manifold_self_intersection(
    *, platform_label: str = "linux-x64-reference"
) -> ManifoldProbe:
    """Measure all controls before and after deterministic STEP exchange."""
    if not isinstance(platform_label, str):
        raise TypeError("platform_label must be a string")
    if not platform_label:
        raise ValueError("platform_label must not be empty")
    import OCP

    fixtures: list[StepRoundTrip] = []
    observations: list[ManifoldObservation] = []
    links: list[VertexLinkObservation] = []
    relations: list[PairRelationObservation] = []
    self_intersections: list[SelfIntersectionObservation] = []
    for control in manifold_controls():
        shape = construct_manifold_control(control.control_id)
        measured = _measure(shape, "constructed", control)
        observations.append(measured[0])
        links.extend(measured[1])
        if measured[2] is not None:
            relations.append(measured[2])
        if measured[3] is not None:
            self_intersections.append(measured[3])
        fixture = step_round_trip(shape, control.control_id)
        fixtures.append(fixture)
        imported = _measure(fixture.imported_shape, "step_imported", control)
        observations.append(imported[0])
        links.extend(imported[1])
        if imported[2] is not None:
            relations.append(imported[2])
        if imported[3] is not None:
            self_intersections.append(imported[3])
    return ManifoldProbe(
        platform_label,
        importlib.metadata.version("cadquery-ocp"),
        str(OCP.__version__),
        tuple(fixtures),
        tuple(observations),
        tuple(links),
        tuple(relations),
        tuple(self_intersections),
    )
