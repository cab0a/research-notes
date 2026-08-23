"""Evaluate void shells, material regions, compounds, and composite solids."""

from __future__ import annotations

import importlib.metadata
from collections import deque
from dataclasses import dataclass
from typing import Literal

from research_notes.brep_runtime import (
    StepRoundTrip,
    indexed_shapes,
    shape_type_name,
    signed_volume,
    step_entity_count,
    step_round_trip,
    topology_counts,
)


Stage = Literal["constructed", "step_imported"]
Vector3 = tuple[float, float, float]


@dataclass(frozen=True)
class SolidRegionControl:
    """Analytic material-volume truth for one synthetic region container."""

    control_id: str
    condition: str
    expected_vertex_count: int
    expected_edge_count: int
    expected_face_count: int
    expected_shell_count: int
    expected_solid_count: int
    analytic_material_volume: float
    expected_constructed_contract: bool
    expected_shared_face_count: int
    expected_solid_component_count: int


@dataclass(frozen=True)
class ShellRoleObservation:
    """Containment and orientation evidence for one direct solid shell."""

    stage: Stage
    control_id: str
    solid_index: int
    shell_index: int
    signed_volume: float
    volume_magnitude: float
    witness_x: float
    witness_y: float
    witness_z: float
    local_containment_depth: int
    global_containment_depth: int
    inferred_role: str
    expected_volume_sign: str
    observed_volume_sign: str
    orientation_matches_depth: bool


@dataclass(frozen=True)
class ShellContainmentObservation:
    """One directed containment result between two shells."""

    stage: Stage
    control_id: str
    outer_shell_index: int
    inner_shell_index: int
    same_parent_solid: bool
    inner_witness_state: str
    common_volume: float
    inner_volume: float
    full_inner_volume_covered: bool
    contains: bool


@dataclass(frozen=True)
class SolidAdjacencyObservation:
    """Topological face sharing and volumetric overlap for two solids."""

    stage: Stage
    control_id: str
    first_solid_index: int
    second_solid_index: int
    shared_face_count: int
    common_volume: float
    face_adjacent: bool
    interiors_overlap: bool


@dataclass(frozen=True)
class SolidRegionObservation:
    """Whole-container shell, region, and adjacency contract."""

    stage: Stage
    control_id: str
    condition: str
    observed_shape_type: str
    vertex_count: int
    edge_count: int
    face_count: int
    shell_count: int
    solid_count: int
    kernel_signed_volume: float
    analytic_material_volume: float
    volume_absolute_error: float
    shell_signed_volume_sum: float
    shell_orientation_contract: bool
    root_shell_count_matches_solids: bool
    same_depth_shell_overlap_count: int
    shell_overlap_gate_passed: bool
    shared_face_count: int
    expected_shared_face_count: int
    shared_face_count_matches_constructed_control: bool
    solid_component_count: int
    expected_solid_component_count: int
    solid_component_count_matches_constructed_control: bool
    composite_solid_contract: bool | None
    material_region_candidate: bool
    expected_constructed_contract: bool
    material_region_candidate_matches_constructed_control: bool
    kernel_analyzer_valid: bool
    topology_matches_constructed_control: bool


@dataclass(frozen=True)
class SolidRegionFixture:
    """STEP bytes plus entity-level solid-region evidence."""

    round_trip: StepRoundTrip
    manifold_solid_brep_count: int
    brep_with_voids_count: int
    closed_shell_count: int
    oriented_closed_shell_count: int


@dataclass(frozen=True)
class SolidRegionProbe:
    """Complete constructed and STEP-imported solid-region evidence."""

    platform_label: str
    binding_distribution_version: str
    binding_module_version: str
    fixtures: tuple[SolidRegionFixture, ...]
    observations: tuple[SolidRegionObservation, ...]
    shell_roles: tuple[ShellRoleObservation, ...]
    containment: tuple[ShellContainmentObservation, ...]
    adjacency: tuple[SolidAdjacencyObservation, ...]


def solid_region_controls() -> tuple[SolidRegionControl, ...]:
    """Return the fixed outer, void, invalid-shell, and container controls."""
    return (
        SolidRegionControl(
            "single_outer_box", "one outer box shell", 8, 12, 6, 1, 1, 480.0, True, 0, 1
        ),
        SolidRegionControl(
            "centered_void_box",
            "one centered void inside a box",
            16,
            24,
            12,
            2,
            1,
            464.0,
            True,
            0,
            1,
        ),
        SolidRegionControl(
            "two_void_box",
            "two disjoint voids inside a box",
            24,
            36,
            18,
            3,
            1,
            560.0,
            True,
            0,
            1,
        ),
        SolidRegionControl(
            "wrong_void_orientation",
            "inner shell oriented as material",
            16,
            24,
            12,
            2,
            1,
            464.0,
            False,
            0,
            1,
        ),
        SolidRegionControl(
            "outside_void_shell",
            "reversed shell outside the outer shell",
            16,
            24,
            12,
            2,
            1,
            464.0,
            False,
            0,
            1,
        ),
        SolidRegionControl(
            "overlapping_void_shells",
            "two same-depth void shells overlap",
            24,
            36,
            18,
            3,
            1,
            531.0,
            False,
            0,
            1,
        ),
        SolidRegionControl(
            "material_island_compound",
            "material island represented as a second solid inside a void",
            24,
            36,
            18,
            3,
            2,
            392.0,
            True,
            0,
            2,
        ),
        SolidRegionControl(
            "shared_face_compsolid",
            "two cells connected by one shared topological face",
            12,
            20,
            11,
            2,
            2,
            64.0,
            True,
            1,
            1,
        ),
        SolidRegionControl(
            "disconnected_compsolid",
            "composite-solid container with two disconnected solids",
            16,
            24,
            12,
            2,
            2,
            64.0,
            False,
            0,
            2,
        ),
        SolidRegionControl(
            "disjoint_compound",
            "general compound containing two disconnected solids",
            16,
            24,
            12,
            2,
            2,
            64.0,
            True,
            0,
            2,
        ),
    )


def _box(origin: Vector3, dimensions: Vector3) -> object:
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt

    return BRepPrimAPI_MakeBox(gp_Pnt(*origin), *dimensions).Shape()


def _cut(first: object, second: object) -> object:
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut

    operation = BRepAlgoAPI_Cut(first, second)
    operation.Build()
    if not operation.IsDone():
        raise RuntimeError("controlled Boolean cut failed")
    return operation.Shape()


def _first_shell(shape: object) -> object:
    from OCP.TopAbs import TopAbs_SHELL
    from OCP.TopoDS import TopoDS

    mapping = indexed_shapes(shape, TopAbs_SHELL)
    if mapping.Extent() != 1:
        raise RuntimeError("expected exactly one source shell")
    return TopoDS.Shell_s(mapping.FindKey(1))


def _make_solid(shells: tuple[object, ...]) -> object:
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeSolid
    from OCP.TopoDS import TopoDS

    builder = BRepBuilderAPI_MakeSolid()
    for shell in shells:
        builder.Add(TopoDS.Shell_s(shell))
    return builder.Solid()


def _compound(items: tuple[object, ...]) -> object:
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound

    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    for item in items:
        builder.Add(compound, item)
    return compound


def _compsolid(items: tuple[object, ...]) -> object:
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_CompSolid

    builder = BRep_Builder()
    result = TopoDS_CompSolid()
    builder.MakeCompSolid(result)
    for item in items:
        builder.Add(result, item)
    return result


def _shared_face_cells() -> tuple[object, object]:
    from OCP.BOPAlgo import BOPAlgo_Builder
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.TopTools import TopTools_ListOfShape

    arguments = TopTools_ListOfShape()
    arguments.Append(_box((0, 0, 0), (2, 4, 4)))
    arguments.Append(_box((2, 0, 0), (2, 4, 4)))
    builder = BOPAlgo_Builder()
    builder.SetArguments(arguments)
    builder.Perform()
    if builder.HasErrors():
        raise RuntimeError("controlled shared-face construction failed")
    solids = indexed_shapes(builder.Shape(), TopAbs_SOLID)
    if solids.Extent() != 2:
        raise RuntimeError("shared-face construction did not return two solids")
    return solids.FindKey(1), solids.FindKey(2)


def construct_solid_region_control(control_id: str) -> object:
    """Construct one deterministic solid-region control."""
    outer = _box((0, 0, 0), (10, 8, 6))
    centered_void = _box((3, 3, 2), (4, 2, 2))
    if control_id == "single_outer_box":
        return outer
    if control_id == "centered_void_box":
        return _cut(outer, centered_void)
    if control_id == "two_void_box":
        larger = _box((0, 0, 0), (12, 8, 6))
        return _cut(
            _cut(larger, _box((2, 2, 2), (2, 2, 2))), _box((8, 4, 2), (2, 2, 2))
        )
    outer_shell = _first_shell(outer)
    if control_id == "wrong_void_orientation":
        return _make_solid((outer_shell, _first_shell(centered_void)))
    if control_id == "outside_void_shell":
        outside = _first_shell(_box((11, 3, 2), (4, 2, 2))).Reversed()
        return _make_solid((outer_shell, outside))
    if control_id == "overlapping_void_shells":
        larger_shell = _first_shell(_box((0, 0, 0), (12, 8, 6)))
        first = _first_shell(_box((2, 2, 1.5), (3, 3, 3))).Reversed()
        second = _first_shell(_box((4, 2, 1.5), (3, 3, 3))).Reversed()
        return _make_solid((larger_shell, first, second))
    if control_id == "material_island_compound":
        body = _cut(outer, _box((2, 2, 1), (6, 4, 4)))
        island = _box((4, 3, 2), (2, 2, 2))
        return _compound((body, island))
    if control_id == "shared_face_compsolid":
        return _compsolid(_shared_face_cells())
    separated = (_box((0, 0, 0), (2, 4, 4)), _box((6, 0, 0), (2, 4, 4)))
    if control_id == "disconnected_compsolid":
        return _compsolid(separated)
    if control_id == "disjoint_compound":
        return _compound(separated)
    raise ValueError(f"unsupported solid-region control: {control_id}")


def _direct_shells(solid: object) -> tuple[object, ...]:
    from OCP.TopoDS import TopoDS, TopoDS_Iterator

    rows: list[object] = []
    iterator = TopoDS_Iterator(solid)
    while iterator.More():
        child = iterator.Value()
        if shape_type_name(child) == "shell":
            rows.append(TopoDS.Shell_s(child))
        iterator.Next()
    return tuple(sorted(rows, key=lambda shell: -abs(signed_volume(shell))))


def _bbox_witness(shape: object) -> Vector3:
    from OCP.BRepBndLib import BRepBndLib
    from OCP.Bnd import Bnd_Box

    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    xmin, ymin, zmin, xmax, ymax, zmax = map(float, box.Get())
    ratio = 0.173
    return (
        xmin + ratio * (xmax - xmin),
        ymin + ratio * (ymax - ymin),
        zmin + ratio * (zmax - zmin),
    )


def _normalized_shell_solid(shell: object) -> object:
    from OCP.BRepLib import BRepLib
    from OCP.TopoDS import TopoDS

    result = _make_solid((TopoDS.Shell_s(shell),))
    BRepLib.OrientClosedSolid_s(result)
    return result


def _classify(shell: object, point: Vector3) -> str:
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.gp import gp_Pnt

    classifier = BRepClass3d_SolidClassifier(
        _normalized_shell_solid(shell), gp_Pnt(*point), 1.0e-7
    )
    return str(classifier.State()).rsplit(".", 1)[-1].removeprefix("TopAbs_").lower()


def _common_volume(first: object, second: object) -> float:
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common

    operation = BRepAlgoAPI_Common(first, second)
    operation.Build()
    if not operation.IsDone():
        raise RuntimeError("controlled common-volume operation failed")
    return abs(signed_volume(operation.Shape()))


def _solid_adjacency(
    shape: object, stage: Stage, control_id: str
) -> tuple[tuple[SolidAdjacencyObservation, ...], int, int]:
    from OCP.TopAbs import TopAbs_FACE, TopAbs_SOLID

    solids = indexed_shapes(shape, TopAbs_SOLID)
    adjacency = {index: set() for index in range(1, solids.Extent() + 1)}
    rows: list[SolidAdjacencyObservation] = []
    total_shared = 0
    for first_index in range(1, solids.Extent() + 1):
        first = solids.FindKey(first_index)
        first_faces = indexed_shapes(first, TopAbs_FACE)
        for second_index in range(first_index + 1, solids.Extent() + 1):
            second = solids.FindKey(second_index)
            second_faces = indexed_shapes(second, TopAbs_FACE)
            shared = sum(
                first_faces.FindIndex(second_faces.FindKey(index)) > 0
                for index in range(1, second_faces.Extent() + 1)
            )
            common_volume = _common_volume(first, second)
            if shared:
                adjacency[first_index].add(second_index)
                adjacency[second_index].add(first_index)
            total_shared += shared
            rows.append(
                SolidAdjacencyObservation(
                    stage,
                    control_id,
                    first_index,
                    second_index,
                    shared,
                    common_volume,
                    shared > 0,
                    common_volume > 1.0e-8,
                )
            )
    unseen = set(adjacency)
    components = 0
    while unseen:
        components += 1
        queue = deque([min(unseen)])
        while queue:
            index = queue.popleft()
            if index not in unseen:
                continue
            unseen.remove(index)
            queue.extend(adjacency[index])
    return tuple(rows), total_shared, components


def _measure(shape: object, stage: Stage, control: SolidRegionControl) -> tuple[
    SolidRegionObservation,
    tuple[ShellRoleObservation, ...],
    tuple[ShellContainmentObservation, ...],
    tuple[SolidAdjacencyObservation, ...],
]:
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.TopAbs import TopAbs_SOLID

    vertices, edges, faces, shell_count, solid_count = topology_counts(shape)
    solids = indexed_shapes(shape, TopAbs_SOLID)
    shell_records: list[tuple[int, int, object, Vector3, float]] = []
    for solid_index in range(1, solids.Extent() + 1):
        for shell_index, shell in enumerate(
            _direct_shells(solids.FindKey(solid_index)), start=1
        ):
            shell_records.append(
                (
                    solid_index,
                    shell_index,
                    shell,
                    _bbox_witness(shell),
                    signed_volume(shell),
                )
            )
    containment_rows: list[ShellContainmentObservation] = []
    contained_by: dict[int, set[int]] = {
        index: set() for index in range(len(shell_records))
    }
    local_contained_by: dict[int, set[int]] = {
        index: set() for index in range(len(shell_records))
    }
    for outer_index, outer in enumerate(shell_records):
        for inner_index, inner in enumerate(shell_records):
            if outer_index == inner_index:
                continue
            state = _classify(outer[2], inner[3])
            common_volume = _common_volume(
                _normalized_shell_solid(outer[2]),
                _normalized_shell_solid(inner[2]),
            )
            inner_volume = abs(inner[4])
            full_inner_volume_covered = abs(common_volume - inner_volume) < 1.0e-8
            contains = state == "in" and full_inner_volume_covered
            if contains:
                contained_by[inner_index].add(outer_index)
                if outer[0] == inner[0]:
                    local_contained_by[inner_index].add(outer_index)
            containment_rows.append(
                ShellContainmentObservation(
                    stage,
                    control.control_id,
                    outer_index + 1,
                    inner_index + 1,
                    outer[0] == inner[0],
                    state,
                    common_volume,
                    inner_volume,
                    full_inner_volume_covered,
                    contains,
                )
            )
    roles: list[ShellRoleObservation] = []
    for index, (solid_index, shell_index, _, witness, volume) in enumerate(
        shell_records
    ):
        local_depth = len(local_contained_by[index])
        global_depth = len(contained_by[index])
        expected_sign = "positive" if local_depth % 2 == 0 else "negative"
        observed_sign = (
            "positive"
            if volume > 1.0e-10
            else "negative" if volume < -1.0e-10 else "zero"
        )
        roles.append(
            ShellRoleObservation(
                stage,
                control.control_id,
                solid_index,
                shell_index,
                volume,
                abs(volume),
                *witness,
                local_depth,
                global_depth,
                "outer" if local_depth == 0 else "void",
                expected_sign,
                observed_sign,
                expected_sign == observed_sign,
            )
        )
    same_depth_overlap = 0
    for first_index, first in enumerate(shell_records):
        for second_index in range(first_index + 1, len(shell_records)):
            second = shell_records[second_index]
            if first[0] != second[0]:
                continue
            common = _common_volume(
                _normalized_shell_solid(first[2]), _normalized_shell_solid(second[2])
            )
            smaller = min(abs(first[4]), abs(second[4]))
            if common > 1.0e-8 and common < smaller - 1.0e-8:
                same_depth_overlap += 1
    adjacency, shared_faces, solid_components = _solid_adjacency(
        shape, stage, control.control_id
    )
    observed_type = shape_type_name(shape)
    composite_contract = None
    if observed_type == "compsolid":
        composite_contract = (
            solid_count >= 2
            and solid_components == 1
            and all(not row.interiors_overlap for row in adjacency)
        )
    shell_orientation = all(row.orientation_matches_depth for row in roles)
    root_match = sum(row.local_containment_depth == 0 for row in roles) == solid_count
    overlap_gate = same_depth_overlap == 0
    volume = signed_volume(shape)
    volume_error = abs(volume - control.analytic_material_volume)
    candidate = (
        shell_orientation
        and root_match
        and overlap_gate
        and volume_error < 1.0e-8
        and composite_contract is not False
    )
    topology_match = (vertices, edges, faces, shell_count, solid_count) == (
        control.expected_vertex_count,
        control.expected_edge_count,
        control.expected_face_count,
        control.expected_shell_count,
        control.expected_solid_count,
    )
    observation = SolidRegionObservation(
        stage,
        control.control_id,
        control.condition,
        observed_type,
        vertices,
        edges,
        faces,
        shell_count,
        solid_count,
        volume,
        control.analytic_material_volume,
        volume_error,
        sum(row.signed_volume for row in roles),
        shell_orientation,
        root_match,
        same_depth_overlap,
        overlap_gate,
        shared_faces,
        control.expected_shared_face_count,
        shared_faces == control.expected_shared_face_count,
        solid_components,
        control.expected_solid_component_count,
        solid_components == control.expected_solid_component_count,
        composite_contract,
        candidate,
        control.expected_constructed_contract,
        candidate == control.expected_constructed_contract,
        bool(BRepCheck_Analyzer(shape).IsValid()),
        topology_match,
    )
    return observation, tuple(roles), tuple(containment_rows), adjacency


def probe_solid_regions(
    *, platform_label: str = "linux-x64-reference"
) -> SolidRegionProbe:
    """Measure controlled material regions before and after STEP exchange."""
    if not isinstance(platform_label, str):
        raise TypeError("platform_label must be a string")
    if not platform_label:
        raise ValueError("platform_label must not be empty")
    import OCP

    fixtures: list[SolidRegionFixture] = []
    observations: list[SolidRegionObservation] = []
    roles: list[ShellRoleObservation] = []
    containment: list[ShellContainmentObservation] = []
    adjacency: list[SolidAdjacencyObservation] = []
    for control in solid_region_controls():
        shape = construct_solid_region_control(control.control_id)
        measured = _measure(shape, "constructed", control)
        observations.append(measured[0])
        roles.extend(measured[1])
        containment.extend(measured[2])
        adjacency.extend(measured[3])
        round_trip = step_round_trip(shape, control.control_id)
        fixtures.append(
            SolidRegionFixture(
                round_trip,
                step_entity_count(round_trip.source_bytes, "MANIFOLD_SOLID_BREP"),
                step_entity_count(round_trip.source_bytes, "BREP_WITH_VOIDS"),
                step_entity_count(round_trip.source_bytes, "CLOSED_SHELL"),
                step_entity_count(round_trip.source_bytes, "ORIENTED_CLOSED_SHELL"),
            )
        )
        imported = _measure(round_trip.imported_shape, "step_imported", control)
        observations.append(imported[0])
        roles.extend(imported[1])
        containment.extend(imported[2])
        adjacency.extend(imported[3])
    return SolidRegionProbe(
        platform_label,
        importlib.metadata.version("cadquery-ocp"),
        str(OCP.__version__),
        tuple(fixtures),
        tuple(observations),
        tuple(roles),
        tuple(containment),
        tuple(adjacency),
    )
