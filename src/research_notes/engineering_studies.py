"""Analytic, exchange and independent-integration evidence for v0.71-v0.75."""
from __future__ import annotations
import math
from dataclasses import asdict,replace
from pathlib import Path
import numpy as np
from research_notes.advanced_geometry_studies import finish_study
from research_notes.brep_runtime import step_round_trip
from research_notes.modeling_studies import json_bytes
from research_notes.engineering_analysis import mass_properties,proximity,mesh_mass_properties
from research_notes.spatial_workflow import BoxOccurrence,BoxAssemblyIndex,WorkBudget,inspect_step_stages


def run_mass_properties(output:Path,fixtures:Path,*,refresh=False):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox,BRepPrimAPI_MakeSphere,BRepPrimAPI_MakeCylinder
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Pnt,gp_Trsf,gp_Ax1,gp_Dir,gp_Vec
    rho=7800.;box=BRepPrimAPI_MakeBox(2.,3.,4.).Shape();sphere=BRepPrimAPI_MakeSphere(2.).Shape();cylinder=BRepPrimAPI_MakeCylinder(2.,3.).Shape()
    rotation=gp_Trsf();rotation.SetRotation(gp_Ax1(gp_Pnt(),gp_Dir(0,0,1)),.4)
    rotation.SetTranslationPart(gp_Vec(10,20,30))
    moved=BRepBuilderAPI_Transform(box,rotation,True).Shape()
    r=np.array([[rotation.Value(i,j) for j in (1,2,3)] for i in (1,2,3)])
    box_i=24/12*np.diag([25.,20.,13.])
    controls=[("box",box,24.,(1.,1.5,2.),box_i),
              ("sphere",sphere,32*math.pi/3,(0.,0.,0.),np.eye(3)*32*math.pi/3*4*.4),
              ("cylinder",cylinder,12*math.pi,(0.,0.,1.5),np.diag([21*math.pi,21*math.pi,24*math.pi])),
              ("rigid_box",moved,24.,tuple(r@np.array([1.,1.5,2.])+[10,20,30]),r@box_i@r.T)]
    rows,detail,payloads,previews=[],[],{},[]
    for name,shape,volume,center,inertia in controls:
        fixture=step_round_trip(shape,"mass_"+name,writer_uncertainty=1e-7);payloads[fixture.file_name]=fixture.source_bytes;previews.append((name,shape))
        for stage,item in (("constructed",shape),("step_imported",fixture.imported_shape)):
            report=mass_properties(item,density=rho)
            error=max(abs(report["volume_m3"]-volume*1e-9),np.max(np.abs(np.array(report["centroid_m"])-np.array(center)*.001)),
                      np.max(np.abs(np.array(report["inertia_about_centroid_kg_m2"])-inertia*rho*1e-15)))
            rows.append({"control_id":name+"_"+stage,"mass_kg":report["mass_kg"],"expected_mass_kg":volume*rho*1e-9,"checks_pass":bool(error<1e-10)})
            detail.append({"control_id":name,"stage":stage,**report})
    for name,density,unit,shape in (("missing_material",None,"mm",box),("unknown_unit",rho,"unknown",box),("reversed",rho,"mm",box.Reversed())):
        try:mass_properties(shape,density=density,length_unit=unit);reason="unexpected_accept"
        except ValueError as exc:reason=str(exc)
        rows.append({"control_id":name,"mass_kg":None,"expected_mass_kg":None,"checks_pass":reason!="unexpected_accept"});detail.append({"control_id":name,"rejection":reason})
    return finish_study(output,fixtures,"mass_properties","v0.71.0",rows,detail,payloads,previews,
        ["one valid outward closed solid; explicit homogeneous density and length units required",
         "mass and centroid inertia reported in SI; principal axes for repeated eigenvalues are nonunique",
         "synthetic engineering measurements; no heterogeneous material assignment inferred"],refresh)


def run_proximity_analysis(output:Path,fixtures:Path,*,refresh=False):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt
    from research_notes.assembly_recompute import compound_shapes
    base=BRepPrimAPI_MakeBox(2.,2.,2.).Shape()
    controls=[("separation",(3.,0.,0.),(2.,2.,2.),"separated",1.,0.),
              ("contact",(2.,0.,0.),(2.,2.,2.),"touching",0.,0.),
              ("overlap",(1.,0.,0.),(2.,2.,2.),"penetrating",0.,4.),
              ("containment",(.5,.5,.5),(1.,1.,1.),"a_contains_b",0.,1.),
              ("coincident",(0.,0.,0.),(2.,2.,2.),"coincident",0.,8.),
              ("tolerance_contact",(2.+5e-8,0.,0.),(2.,2.,2.),"touching",0.,0.)]
    rows,detail,payloads,previews=[],[],{},[]
    for name,origin,size,expected,distance,volume in controls:
        other=BRepPrimAPI_MakeBox(gp_Pnt(*origin),*size).Shape()
        report=proximity(base,other,required_clearance=.5,transforms={"a_origin":[0,0,0],"b_origin":origin})
        rows.append({"control_id":name,"observed":report["status"],"expected":expected,"distance":report["minimum_distance"],"overlap_volume":report["overlap_volume"],
                     "checks_pass":report["status"]==expected and abs(report["minimum_distance"]-distance)<1e-6 and abs(report["overlap_volume"]-volume)<1e-6})
        detail.append({"control_id":name,**report});shape=compound_shapes((base,other));previews.append((name,shape))
        fixture=step_round_trip(shape,"proximity_"+name,writer_uncertainty=1e-7);payloads[fixture.file_name]=fixture.source_bytes
    return finish_study(output,fixtures,"proximity_analysis","v0.72.0",rows,detail,payloads,previews,
        ["distance and common volume are separate; containment does not become a negative distance",
         "analysis-local support subshapes and witness points are retained with transform provenance",
         "classification uses separate length and volume tolerances; penetration depth is not estimated"],refresh)


def run_spatial_workflow(output:Path,fixtures:Path,*,refresh=False):
    from research_notes.assembly_recompute import compound_shapes
    occurrences=tuple(BoxOccurrence(f"box_{i}",(1.,1.,1.),(i*2.,0.,0.)) for i in range(128))
    index=BoxAssemblyIndex(occurrences)
    query=index.candidate_pairs(1.1)
    expected=[(i,i+1) for i in range(127)]
    rows=[{"control_id":"bvh_clearance","observed":len(query["pairs"]),"expected":127,"checks_pass":query["pairs"]==expected and not index.cache}]
    detail=[{"control_id":"bvh_clearance",**query,"geometry_evaluations":len(index.cache)}]
    index.geometry(0);index.geometry(1);index.geometry(0)
    rows.append({"control_id":"lazy_cache","observed":len(index.cache),"expected":2,"checks_pass":len(index.cache)==2})
    limited=BoxAssemblyIndex(occurrences,replace(WorkBudget(),max_pairs=10)).candidate_pairs(1.1)
    rows.append({"control_id":"partial_pairs","observed":limited["status"],"expected":"partial","checks_pass":limited["status"]=="partial" and len(limited["pairs"])==10});detail.append(limited)
    fixture=step_round_trip(compound_shapes(index.geometry(i) for i in range(64)),"large_box_assembly",writer_uncertainty=1e-7)
    import tempfile
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/fixture.file_name;path.write_bytes(fixture.source_bytes)
        cases=[("staged_syntax",WorkBudget(),"accepted"),
               ("byte_gate",replace(WorkBudget(),max_bytes=1000),"quarantined"),
               ("entity_gate",replace(WorkBudget(),max_entities=100),"quarantined"),
               ("memory_estimate_gate",replace(WorkBudget(),max_estimated_memory_bytes=1000),"quarantined")]
        for name,budget,expected_status in cases:
            report,document=inspect_step_stages(path,budget)
            rows.append({"control_id":name,"observed":report["status"],"expected":expected_status,"checks_pass":report["status"]==expected_status});detail.append({"control_id":name,**report})
    return finish_study(output,fixtures,"spatial_workflow","v0.73.0",rows,detail,{fixture.file_name:fixture.source_bytes,"occurrences.json":json_bytes([asdict(o) for o in occurrences])},[("64 occurrences: overall scale",fixture.imported_shape),("First four occurrences: detail",compound_shapes(index.geometry(i) for i in range(4)))],
        ["64-solid STEP and 128-occurrence index are bounded scale controls, not industrial-size throughput claims",
         "byte stage precedes syntax; geometry remains deferred; memory is an estimate and time checks are cooperative",
         "exact authored-box BVH supports rigid placements; lazy native geometry and pair limits; no native-code sandbox"],refresh)


def run_independent_validation(output:Path,fixtures:Path,*,refresh=False):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox,BRepPrimAPI_MakeSphere
    shapes=[("box",BRepPrimAPI_MakeBox(2.,3.,4.).Shape(),24.),("sphere",BRepPrimAPI_MakeSphere(2.).Shape(),32*math.pi/3)]
    rows,detail,payloads,previews=[],[],{},[]
    for name,shape,truth in shapes:
        native=mass_properties(shape,density=1.,length_unit="m")
        for label,deflection,angle in (("coarse",.3,.6),("fine",.01,.1)):
            mesh=mesh_mass_properties(shape,deflection=deflection,angular_deflection=angle)
            error=abs(mesh["volume"]-truth)/truth
            rows.append({"control_id":name+"_"+label,"mesh_relative_volume_error":error,"native_relative_volume_error":abs(native["volume_m3"]-truth)/truth,
                         "checks_pass":error < (.06 if label=="coarse" else .005) and abs(native["volume_m3"]-truth)<1e-8})
            detail.append({"control_id":name+"_"+label,"analytic_volume":truth,"mesh":mesh,"native":native})
        fixture=step_round_trip(shape,"independent_"+name,writer_uncertainty=1e-7);payloads[fixture.file_name]=fixture.source_bytes;previews.append((name,shape))
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
    from OCP.gp import gp_Pnt,gp_Dir,gp_Lin
    from OCP.Geom import Geom_Line
    from research_notes.repair_policies import RepairPolicy,repair_shape
    from research_notes.modeling_common import measure_shape
    from research_notes.intersection_analysis import curve_curve_intersections
    joined=BRepAlgoAPI_Fuse(BRepPrimAPI_MakeBox(2.,2.,2.).Shape(),BRepPrimAPI_MakeBox(gp_Pnt(2,0,0),2.,2.,2.).Shape()).Shape()
    repaired=repair_shape(joined,RepairPolicy("unify"));metrics=measure_shape(repaired.shape);mesh=mesh_mass_properties(repaired.shape)
    rows.append({"control_id":"repair_box_analytic","mesh_relative_volume_error":abs(mesh["volume"]-16)/16,"native_relative_volume_error":abs(metrics.absolute_volume-16)/16,
                 "checks_pass":metrics.face_count==6 and metrics.edge_count==12 and abs(metrics.surface_area-40)<1e-8 and abs(mesh["volume"]-16)<1e-8})
    detail.append({"control_id":"repair_box_analytic","analytic_dimensions":[4,2,2],"expected_topology":[8,12,6],"repair":repaired.audit,"mesh":mesh})
    intersections=curve_curve_intersections(Geom_Line(gp_Lin(gp_Pnt(-2,0,0),gp_Dir(1,0,0))),Geom_Line(gp_Lin(gp_Pnt(0,-3,0),gp_Dir(0,1,0))),(0.,4.),(0.,6.))
    rows.append({"control_id":"intersection_analytic","mesh_relative_volume_error":None,"native_relative_volume_error":None,
                 "checks_pass":intersections["multiplicity"]==1 and np.linalg.norm(intersections["points"][0]["point"])<1e-8})
    detail.append({"control_id":"intersection_analytic","expected_point":[0,0,0],"observation":intersections})
    return finish_study(output,fixtures,"independent_validation","v0.74.0",rows,detail,payloads,previews,
        ["analytic formulas and signed-tetrahedron integrals are independent arithmetic routes",
         "tessellation still comes from OCCT; this is not an independent native geometry kernel",
         "coarse/fine disagreements are retained; no arbitrary STEP portability or repair equivalence claim"],refresh)
