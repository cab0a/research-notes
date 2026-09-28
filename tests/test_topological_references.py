from dataclasses import replace
import pytest

from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
from OCP.gp import gp_Pnt

from research_notes.assembly_recompute import compound_shapes
from research_notes.brep_runtime import step_round_trip
from research_notes.topological_references import (
    advance_reference, reference_relations, select_reference, topology_snapshot,
)


def test_named_reference_survives_box_edit_and_step_exchange():
    before = topology_snapshot(BRepPrimAPI_MakeBox(4., 4., 2.).Shape(), "plate", "r1")
    after = topology_snapshot(BRepPrimAPI_MakeBox(6., 4., 3.).Shape(), "plate", "r2")
    rows = reference_relations(before, after, mode="normalized_box")
    assert len(rows) == 18
    assert {r.relation for r in rows} == {"one_to_one"}
    ref = select_reference(before, "face", 1, name="selected_side")
    moved = advance_reference(ref, rows)
    assert moved.reference_id == ref.reference_id and moved.stage_id != ref.stage_id
    fixture = step_round_trip(after.shape, "reference_box", writer_uncertainty=1e-7)
    imported = topology_snapshot(fixture.imported_shape, "plate", "step")
    mapped = advance_reference(moved, reference_relations(after, imported))
    assert mapped.reference_id == ref.reference_id
    assert all(not r.permanent_kernel_identity for r in rows)
    with pytest.raises(ValueError, match="snapshot"):
        advance_reference(replace(ref, owner="another"), rows)


def test_operation_history_proves_split_and_deletion():
    box = BRepPrimAPI_MakeBox(4., 4., 2.).Shape()
    before = topology_snapshot(box, "plate", "r1")
    for name, x, width, expected in (("split", 1.5, 1., "split"), ("delete", -1., 3., "deleted")):
        tool = BRepPrimAPI_MakeBox(gp_Pnt(x, -1., -1.), width, 6., 4.).Shape()
        operation = BRepAlgoAPI_Cut(box, tool)
        after = topology_snapshot(operation.Shape(), "plate", name)
        rows = reference_relations(before, after, mode="operation_history", history=operation)
        assert any(r.relation == expected and r.kind == "face" for r in rows)
        assert any(r.relation == expected and r.kind == "edge" for r in rows)
        row = next(r for r in rows if r.relation == expected)
        ref = select_reference(before, row.kind, row.source_index, name="review")
        with pytest.raises(ValueError, match="review"):
            advance_reference(ref, rows)


def test_same_domain_healing_reports_merge_and_requires_acceptance():
    a = BRepPrimAPI_MakeBox(2., 4., 2.).Shape()
    b = BRepPrimAPI_MakeBox(gp_Pnt(2., 0., 0.), 2., 4., 2.).Shape()
    split = BRepAlgoAPI_Fuse(a, b).Shape()
    unify = ShapeUpgrade_UnifySameDomain(split, True, True, False)
    unify.Build()
    before, after = topology_snapshot(split, "plate", "split"), topology_snapshot(unify.Shape(), "plate", "healed")
    rows = reference_relations(before, after, mode="operation_history", history=unify.History())
    row = next(r for r in rows if r.kind == "face" and r.relation == "merge")
    ref = select_reference(before, "face", row.source_index, name="merged_face")
    with pytest.raises(ValueError, match="review"):
        advance_reference(ref, rows)
    assert advance_reference(ref, rows, accept_merge=True).reference_id == ref.reference_id


def test_geometric_ties_are_not_resolved_by_index():
    box = BRepPrimAPI_MakeBox(4., 4., 2.).Shape()
    twin = BRepBuilderAPI_Copy(box).Shape()
    before = topology_snapshot(box, "plate", "single")
    after = topology_snapshot(compound_shapes((box, twin)), "plate", "duplicate")
    rows = reference_relations(before, after)
    assert {r.relation for r in rows} == {"ambiguous"}
    with pytest.raises(ValueError, match="review"):
        advance_reference(select_reference(before, "face", 1, name="side"), rows)
