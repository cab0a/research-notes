"""Reference tracking benchmark with explicit operation or analytic role truth."""
from __future__ import annotations

from dataclasses import asdict
import math

from research_notes.brep_runtime import indexed_shapes, step_round_trip
from research_notes.topological_references import topology_snapshot, reference_relations
from research_notes.robustness_studies import evidence_bytes, finish


def _map(shape, kind):
    from OCP.TopAbs import TopAbs_FACE, TopAbs_EDGE
    return indexed_shapes(shape, TopAbs_FACE if kind == "face" else TopAbs_EDGE)


def _identity_truth(before, after, operation=None):
    """Oracle is OCCT ancestry, separately enumerated without descriptor matching."""
    truth = {}
    for kind in ("face", "edge"):
        source, target = _map(before, kind), _map(after, kind)
        for i in range(1, source.Extent() + 1):
            old = source.FindKey(i)
            evolved = [old] + (list(operation.Modified(old)) if operation is not None else [])
            truth[kind, i] = tuple(j for j in range(1, target.Extent() + 1)
                                   if any(s.IsSame(target.FindKey(j)) for s in evolved))
    return truth


def _box_roles(shape, dimensions):
    """Label by area/length centroid on authored box planes, not vertex signatures."""
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    roles = {}
    for kind in ("face", "edge"):
        mapping = _map(shape, kind)
        for i in range(1, mapping.Extent() + 1):
            props = GProp_GProps()
            operation = BRepGProp.SurfaceProperties_s if kind == "face" else BRepGProp.LinearProperties_s
            operation(mapping.FindKey(i), props)
            center = props.CentreOfMass().Coord()
            role = tuple((axis, side) for axis in range(3) for side in (0, 1)
                         if abs(center[axis] - side * dimensions[axis]) <= max(dimensions) * 1e-8)
            if len(role) != (1 if kind == "face" else 2):
                raise ValueError("analytic box role is not unique")
            roles[kind, i] = role
    return roles


def _role_truth(before, after, before_dimensions, after_dimensions):
    source, target = _box_roles(before, before_dimensions), _box_roles(after, after_dimensions)
    return {key: tuple(j for (kind, j), role in target.items() if kind == key[0] and role == value)
            for key, value in source.items()}


def score_relations(relations, truth):
    """Count wrong asserted target sets; abstention is neither a match nor an error."""
    if {(r.kind, r.source_index) for r in relations} != set(truth):
        raise ValueError("oracle must cover every source reference")
    asserted = [r for r in relations if r.relation in {"one_to_one", "split", "merge", "deleted"}]
    incorrect = [r for r in asserted if tuple(sorted(r.target_indices)) != tuple(sorted(truth[r.kind, r.source_index]))]
    count = len(relations)
    return {"source_count": count, "asserted": len(asserted), "incorrect": len(incorrect),
            "abstained": count - len(asserted), "split": sum(r.relation == "split" for r in relations),
            "merge": sum(r.relation == "merge" for r in relations), "deleted": sum(r.relation == "deleted" for r in relations),
            "coverage": len(asserted) / count, "incorrect_fraction": len(incorrect) / count}


def reference_cases():
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy, BRepBuilderAPI_Transform
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.gp import gp_Pnt, gp_Ax1, gp_Dir, gp_Trsf
    from research_notes.assembly_recompute import compound_shapes
    before = BRepPrimAPI_MakeBox(4., 3., 2.).Shape()
    for scale in (.001, 1000.):
        tr = gp_Trsf(); tr.SetScale(gp_Pnt(0., 0., 0.), scale)
        operation = BRepBuilderAPI_Transform(before, tr, True)
        after = operation.Shape()
        yield f"scale_{scale:g}", "scale", before, after, "normalized_box", None, _identity_truth(before, after, operation), "kernel_transform_history", {"asserted": 18, "incorrect": 0}
    for degrees, symmetric in ((37., False), (90., True)):
        source = BRepPrimAPI_MakeBox(4., 4., 2.).Shape() if symmetric else before
        tr = gp_Trsf(); tr.SetRotation(gp_Ax1(gp_Pnt(2., 2. if symmetric else 1.5, 1.), gp_Dir(0., 0., 1.)), math.radians(degrees))
        operation = BRepBuilderAPI_Transform(source, tr, True); after = operation.Shape()
        truth = _identity_truth(source, after, operation)
        yield f"rotation_{degrees:g}_geometry", "rotation", source, after, "geometry", None, truth, "kernel_transform_history", {"asserted": 18 if symmetric else 0, "incorrect": 16 if symmetric else 0}
        if not symmetric:
            yield "rotation_37_history", "rotation", source, after, "operation_history", operation, truth, "kernel_transform_history", {"asserted": 18, "incorrect": 0}
    after = BRepPrimAPI_MakeBox(6., 3., 2.).Shape()
    yield "width_feature_edit", "feature_edit", before, after, "normalized_box", None, _role_truth(before, after, (4., 3., 2.), (6., 3., 2.)), "analytic_box_centroid_roles", {"asserted": 18, "incorrect": 0}
    # Reorder face storage without a geometric edit or solid-validity claim.
    faces = _map(before, "face")
    after = compound_shapes(tuple(faces.FindKey(i) for i in range(faces.Extent(), 0, -1)))
    yield "face_reordering", "reordering", before, after, "geometry", None, _identity_truth(before, after), "native_subshape_identity", {"asserted": 18, "incorrect": 0}
    for name, cutter in (("split", BRepPrimAPI_MakeBox(gp_Pnt(1.5, -1., -1.), 1., 6., 4.).Shape()),
                         ("delete", BRepPrimAPI_MakeBox(gp_Pnt(-1., -1., -1.), 3., 6., 4.).Shape())):
        operation = BRepAlgoAPI_Cut(before, cutter); after = operation.Shape()
        expected = {"asserted": 18, "incorrect": 0, "split": 8} if name == "split" else {"asserted": 18, "incorrect": 0, "deleted": 5}
        yield "boolean_" + name, "boolean", before, after, "operation_history", operation, _identity_truth(before, after, operation), "kernel_boolean_history", expected
    fused = BRepAlgoAPI_Fuse(BRepPrimAPI_MakeBox(2., 3., 2.).Shape(), BRepPrimAPI_MakeBox(gp_Pnt(2., 0., 0.), 2., 3., 2.).Shape()).Shape()
    unify = ShapeUpgrade_UnifySameDomain(fused, True, True, False); unify.Build()
    yield "repair_merge", "repair", fused, unify.Shape(), "operation_history", unify.History(), _identity_truth(fused, unify.Shape(), unify.History()), "kernel_repair_history", {"asserted": 30, "incorrect": 0, "merge": 16, "deleted": 4}
    meshed = BRepBuilderAPI_Copy(before).Shape()
    BRepMesh_IncrementalMesh(meshed, .05, False, .3, False)
    yield "tessellation_cache", "tessellation", before, meshed, "geometry", None, _role_truth(before, meshed, (4., 3., 2.), (4., 3., 2.)), "analytic_box_centroid_roles", {"asserted": 18, "incorrect": 0}
    exchanged = step_round_trip(before, "reference_benchmark_exchange", writer_uncertainty=1e-7).imported_shape
    yield "step_exchange", "step_exchange", before, exchanged, "geometry", None, _role_truth(before, exchanged, (4., 3., 2.), (4., 3., 2.)), "analytic_box_centroid_roles", {"asserted": 18, "incorrect": 0}
    duplicate = compound_shapes((before, BRepBuilderAPI_Copy(before).Shape()))
    yield "coincident_duplicates", "ambiguity", before, duplicate, "geometry", None, _role_truth(before, duplicate, (4., 3., 2.), (4., 3., 2.)), "analytic_multiple_candidates", {"asserted": 0, "incorrect": 0}


def run_reference_robustness(output, fixtures, *, refresh=False):
    rows, detail, controls = [], [], []
    for name, family, before, after, mode, history, truth, oracle, expected in reference_cases():
        source, target = topology_snapshot(before, "benchmark", name + "_before"), topology_snapshot(after, "benchmark", name + "_after")
        relations = reference_relations(source, target, mode=mode, history=history)
        score = score_relations(relations, truth)
        rows.append({"control_id": name, "family": family, "mode": mode, **score,
                     "checks_pass": all(score[k] == v for k, v in expected.items())})
        detail.append({"control_id": name, "oracle": oracle, "relations": [asdict(r) for r in relations],
                       "truth": [{"kind": kind, "source_index": i, "target_indices": ids} for (kind, i), ids in truth.items()]})
        controls.append({"control_id": name, "family": family, "oracle": oracle, "expected": expected, "mode": mode})
    return finish(output, fixtures, "reference_robustness", rows, detail, {"controls.json": evidence_bytes(controls)}, [
        "Face and edge relations are scored by perturbation family, including incorrect assertions and abstentions; no permanent kernel identity is claimed.",
        "Truth is authored box centroid roles for edit/exchange/cache cases, or native identity/operation ancestry. Kernel history is a scoped oracle, not an independent CAD implementation.",
        "A 90-degree rotation of a symmetric box is a deliberate geometric false-match control. Matching the occupied geometry does not prove feature identity.",
        "Tessellation tests the retained B-Rep mesh cache, not triangle-to-B-Rep reconstruction. Curved topology and arbitrary edits remain outside this benchmark.",
    ], refresh=refresh)
