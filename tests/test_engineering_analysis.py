from dataclasses import replace
import math
import numpy as np
import pytest
from research_notes.engineering_analysis import mass_properties,mesh_mass_properties,proximity
from research_notes.spatial_workflow import BoxOccurrence,BoxAssemblyIndex,WorkBudget,inspect_step_stages


def test_si_mass_inertia_and_density_conversion():
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    shape=BRepPrimAPI_MakeBox(2.,3.,4.).Shape()
    r=mass_properties(shape,density=7.8,density_unit="g/cm3")
    assert r["mass_kg"]==pytest.approx(24*7800*1e-9)
    assert np.array(r["inertia_about_centroid_kg_m2"])==pytest.approx(np.diag([50,40,26])*7800*1e-15)
    assert r["centroid_m"]==pytest.approx([.001,.0015,.002])
    with pytest.raises(ValueError):mass_properties(shape.Reversed(),density=7800)
    with pytest.raises(ValueError):mass_properties(shape,density=None)


def test_mesh_integrals_are_independent_and_translation_invariant():
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt
    r=mesh_mass_properties(BRepPrimAPI_MakeBox(gp_Pnt(5,7,9),2.,3.,4.).Shape())
    assert r["volume"]==pytest.approx(24)
    assert r["centroid"]==pytest.approx([6,8.5,11])
    assert np.array(r["unit_density_inertia"])==pytest.approx(np.diag([50,40,26]))


def test_containment_is_distinct_from_touching_and_separation():
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt
    outer=BRepPrimAPI_MakeBox(4.,4.,4.).Shape();inner=BRepPrimAPI_MakeBox(gp_Pnt(1,1,1),1.,1.,1.).Shape()
    r=proximity(outer,inner)
    assert r["status"]=="a_contains_b" and not r["clearance_satisfied"]
    assert r["overlap_volume"]==pytest.approx(1)
    assert r["witnesses"]


def test_bvh_matches_brute_force_and_lazy_budget():
    items=tuple(BoxOccurrence(str(i),(1.,1.,1.),(i*.8,(i%2)*.1,0.)) for i in range(25))
    index=BoxAssemblyIndex(items,replace(WorkBudget(),max_geometry=1))
    expected=[(i,j) for i,a in enumerate(index.bounds) for j,b in enumerate(index.bounds) if j>i and np.all(a[0]<=b[1]+.2) and np.all(b[0]<=a[1]+.2)]
    assert index.candidate_pairs(.2)["pairs"]==expected
    assert not index.cache
    assert index.geometry(0) is index.geometry(0)
    with pytest.raises(ValueError):index.geometry(1)
    partial=BoxAssemblyIndex(items,replace(WorkBudget(),max_pairs=2)).candidate_pairs(.2)
    assert partial["status"]=="partial" and len(partial["pairs"])==2


def test_staged_parser_time_and_memory_gates(tmp_path):
    from research_notes.advanced_geometry_studies import pmi_fixture
    path=tmp_path/"input.step";path.write_bytes(pmi_fixture())
    report,doc=inspect_step_stages(path,replace(WorkBudget(),max_estimated_memory_bytes=100))
    assert report["reason"]=="estimated_memory_budget" and doc is None
    ticks=iter((0.,31.))
    report,doc=inspect_step_stages(path,clock=lambda:next(ticks))
    assert report["reason"]=="time_budget"
    report,doc=inspect_step_stages(path,replace(WorkBudget(),max_bytes=100))
    assert report["source_sha256"] is None and report["read_prefix_sha256"]


def test_mass_rejects_free_geometry_outside_closed_solid():
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
    from OCP.gp import gp_Pnt
    from research_notes.assembly_recompute import compound_shapes
    shape=compound_shapes((BRepPrimAPI_MakeBox(2.,3.,4.).Shape(),BRepBuilderAPI_MakeVertex(gp_Pnt(99,0,0)).Shape()))
    with pytest.raises(ValueError,match="free subshapes"):mass_properties(shape,density=7800)
