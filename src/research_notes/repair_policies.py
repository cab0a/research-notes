"""Explicit repair transactions with candidate audit and rollback on failed gates."""
from __future__ import annotations
import math
from dataclasses import asdict, dataclass
from research_notes.modeling_common import measure_shape
from research_notes.topological_references import topology_snapshot, reference_relations


@dataclass(frozen=True)
class RepairPolicy:
    operation: str
    tolerance: float = 1e-6
    maximum_tolerance: float = 1e-5
    maximum_volume_change: float = 1e-6
    maximum_area_change: float = 1e-5
    allow_attribute_loss: bool = False
    selected_faces: tuple[int,...] = ()


@dataclass(frozen=True)
class RepairResult:
    shape: object
    candidate: object
    audit: dict


def repair_shape(shape, policy: RepairPolicy, *, attributes=()) -> RepairResult:
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy, BRepBuilderAPI_Sewing
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Defeaturing
    from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
    from OCP.ShapeFix import ShapeFix_Shape
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopoDS import TopoDS
    from research_notes.brep_runtime import indexed_shapes
    if policy.operation not in {"sew", "unify", "orient", "remove_faces"}:
        raise ValueError("unknown explicit repair operation")
    values = (policy.tolerance,policy.maximum_tolerance,policy.maximum_volume_change,policy.maximum_area_change)
    if any(not math.isfinite(v) or v < 0 for v in values) or policy.tolerance <= 0:
        raise ValueError("invalid repair budgets")
    before = measure_shape(shape)
    copy = BRepBuilderAPI_Copy(shape).Shape()
    history = None
    if policy.operation == "sew":
        operation = BRepBuilderAPI_Sewing(policy.tolerance)
        operation.Add(copy); operation.Perform(); candidate = operation.SewedShape()
    elif policy.operation == "unify":
        operation = ShapeUpgrade_UnifySameDomain(copy,True,True,False)
        operation.Build(); candidate = operation.Shape(); history = operation.History()
    elif policy.operation == "orient":
        # ShapeFix is restricted to orientation; general healing is not enabled.
        from OCP.ShapeFix import ShapeFix_Shell
        from OCP.TopAbs import TopAbs_SHELL
        shells = indexed_shapes(copy,TopAbs_SHELL)
        if shells.Extent() != 1:
            raise ValueError("orientation repair requires one shell")
        operation = ShapeFix_Shell(TopoDS.Shell_s(shells.FindKey(1)))
        operation.FixFaceOrientation(TopoDS.Shell_s(shells.FindKey(1)))
        candidate = operation.Shell()
    else:
        faces = indexed_shapes(copy,TopAbs_FACE)
        if not policy.selected_faces or len(set(policy.selected_faces)) != len(policy.selected_faces) or any(type(i) is not int or not 1 <= i <= faces.Extent() for i in policy.selected_faces):
            raise ValueError("explicit unique analysis-local face selections required")
        operation = BRepAlgoAPI_Defeaturing()
        operation.SetShape(copy)
        for i in policy.selected_faces:
            operation.AddFaceToRemove(TopoDS.Face_s(faces.FindKey(i)))
        operation.Build()
        if not operation.IsDone():
            raise RuntimeError("defeaturing failed; original shape retained")
        candidate = operation.Shape(); history = operation
    if candidate.IsNull():
        raise RuntimeError("repair produced null shape; original shape retained")
    after = measure_shape(candidate)
    from OCP.BRep import BRep_Tool
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_VERTEX
    def subshapes(item):
        rows=[]
        for kind,enum,cast in (("vertex",TopAbs_VERTEX,TopoDS.Vertex_s),("edge",TopAbs_EDGE,TopoDS.Edge_s),("face",TopAbs_FACE,TopoDS.Face_s)):
            mapping=indexed_shapes(item,enum)
            for i in range(1,mapping.Extent()+1):
                subshape=cast(mapping.FindKey(i))
                rows.append({"kind":kind,"index":i,"tolerance":BRep_Tool.Tolerance_s(subshape),"orientation":str(subshape.Orientation())})
        return rows
    material_difference=None
    if before.solid_count==1 and after.solid_count==1:
        from research_notes.parametric_features import shape_difference_volume
        material_difference=shape_difference_volume(copy,candidate)
    reasons = []
    if not after.analyzer_valid: reasons.append("invalid_candidate")
    if max(after.maximum_vertex_tolerance,after.maximum_edge_tolerance,after.maximum_face_tolerance) > policy.maximum_tolerance: reasons.append("tolerance_budget")
    if abs(after.absolute_volume-before.absolute_volume) > policy.maximum_volume_change: reasons.append("volume_change_budget")
    if material_difference is not None and material_difference > policy.maximum_volume_change: reasons.append("material_difference_budget")
    if abs(after.surface_area-before.surface_area) > policy.maximum_area_change: reasons.append("area_change_budget")
    # Copies intentionally isolate the input. Only the copy-to-candidate relation
    # uses native history; input-to-copy identity remains scoped by its descriptors.
    source, target = topology_snapshot(copy,"repair","before"), topology_snapshot(candidate,"repair","candidate")
    relations = reference_relations(source,target,mode="operation_history" if history else "geometry",history=history)
    lost = list(attributes) if any(r.relation != "one_to_one" for r in relations) else []
    if lost and not policy.allow_attribute_loss: reasons.append("attribute_loss")
    audit = {"policy":asdict(policy),"status":"rejected_rolled_back" if reasons else "accepted", "reasons":reasons,
             "before":asdict(before),"candidate":asdict(after),"lost_or_unresolved_attributes":lost,
             "subshape_changes":[asdict(r) for r in relations],
             "subshape_tolerances_and_orientations_before":subshapes(copy),"subshape_tolerances_and_orientations_candidate":subshapes(candidate),
             "material_difference_volume":material_difference,
             "volume_change":after.absolute_volume-before.absolute_volume,"area_change":after.surface_area-before.surface_area,
             "deviation_scope":"volume and area budgets; no Hausdorff guarantee", "input_mutated":False}
    return RepairResult(shape if reasons else candidate,candidate,audit)
