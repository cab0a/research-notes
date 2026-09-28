"""Reproducible controls for v0.66-v0.70 precision and repair studies."""
from __future__ import annotations
import math
import json
from dataclasses import asdict, replace
from pathlib import Path
import numpy as np

from research_notes.brep_runtime import step_round_trip, indexed_shapes
from research_notes.brep_preview import write_shape_previews
from research_notes.modeling_studies import _contract, json_bytes, csv_bytes, handle_fixtures
from research_notes.semantic_pmi import inspect_pmi
from research_notes.spline_geometry import SplineCurve, kernel_curve, evaluate_curve, quarter_circle, rational_cylinder_patch, curve_record, surface_record
from research_notes.differential_geometry import surface_differential, sampled_continuity
from research_notes.intersection_analysis import curve_curve_intersections, curve_surface_intersections, surface_intersections, inspect_trimming
from research_notes.repair_policies import RepairPolicy, repair_shape


def finish_study(output, fixtures, name, version, rows, detail, payloads, previews, boundaries, refresh):
    output.mkdir(parents=True,exist_ok=True)
    if not payloads:
        payloads = {"controls.json":evidence_bytes(detail)}
    handle_fixtures(fixtures,payloads,refresh=refresh,generator=f"experiments/run_{name}.py")
    (output/f"{name}.csv").write_bytes(csv_bytes(rows))
    (output/f"{name}_evidence.json").write_bytes(evidence_bytes(detail))
    if previews:
        write_shape_previews(output/f"{name}.png",tuple(previews),title=name.replace("_"," ").title(),columns=min(3,len(previews)))
    else:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig,ax = plt.subplots(figsize=(10,max(3,len(rows)*.24)))
        labels=[r["control_id"] for r in rows]
        if name=="representation_learning":
            positions=np.arange(len(rows))
            ax.barh(positions-.17,[r["accuracy"] for r in rows],height=.32,label="Raw accuracy",color="#197a89")
            ax.barh(positions+.17,[r["coverage"] for r in rows],height=.32,label="Decision coverage",color="#e2a547")
            ax.set(yticks=positions,yticklabels=labels,xlim=(0,1.1),xlabel="Observed fraction; failures retained")
            ax.legend(loc="lower right")
        elif name=="semantic_pmi":
            ax.barh(labels,[r["semantic_count"] for r in rows],label="Resolved semantic records",color="#197a89")
            ax.barh(labels,[r["diagnostic_count"] for r in rows],left=[r["semantic_count"] for r in rows],label="Unresolved / rejected",color="#e2a547")
            ax.set(xlabel="Observed record count");ax.legend(loc="lower right")
        else:
            ax.barh(labels,[1 if r["checks_pass"] else 0 for r in rows],color="#197a89")
            ax.set(xlim=(0,1.1),xlabel="Declared control matches expectation")
        ax.set_title(name.replace("_"," ").title())
        fig.tight_layout(); fig.savefig(output/f"{name}.png",dpi=120); plt.close(fig)
    _contract(output,name,version,rows,boundaries,detail_numeric_serialization="9 decimal places; nonzero magnitudes below 1e-6 retain 9 significant digits")
    return rows


def evidence_bytes(value):
    """Keep small SI quantities; do not round microscopic inertia to zero."""
    def normalize(item,preserve_small=False):
        if isinstance(item,float):
            return float(f"{item:.9g}") if preserve_small and 0<abs(item)<1e-6 else round(item,9)+0.
        if isinstance(item,dict):return {k:normalize(v,k in {"inertia_about_centroid_kg_m2","principal_moments_kg_m2","volume_m3","surface_area_m2","mass_kg","centroid_m"}) for k,v in item.items()}
        if isinstance(item,(list,tuple)):return [normalize(v,preserve_small) for v in item]
        return item
    return (json.dumps(normalize(value),sort_keys=True,indent=2,allow_nan=False)+"\n").encode()


def pmi_fixture():
    return b"""ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('Synthetic semantic PMI roles'),'2;1');
FILE_NAME('pmi.step','2000-01-01T00:00:00',('Research'),('Research'),'Research','Research','');
FILE_SCHEMA(('AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF'));
ENDSEC;
DATA;
#1=APPLICATION_CONTEXT('managed model based 3d engineering');
#2=PRODUCT_CONTEXT('',#1,'mechanical');
#3=PRODUCT('part','part','',(#2));
#4=PRODUCT_DEFINITION_FORMATION('','',#3);
#5=PRODUCT_DEFINITION_CONTEXT('part definition',#1,'design');
#6=PRODUCT_DEFINITION('design','',#4,#5);
#7=PRODUCT_DEFINITION_SHAPE('','',#6);
#8=SHAPE_ASPECT('hole','',#7,.T.);
#9=(LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT(.MILLI.,.METRE.));
#10=(LENGTH_MEASURE_WITH_UNIT() MEASURE_REPRESENTATION_ITEM() MEASURE_WITH_UNIT(LENGTH_MEASURE(4.),#9) REPRESENTATION_ITEM('diameter'));
#11=REPRESENTATION_CONTEXT('','');
#12=SHAPE_DIMENSION_REPRESENTATION('',(#10),#11);
#13=DIMENSIONAL_SIZE(#8,'diameter');
#14=DIMENSIONAL_CHARACTERISTIC_REPRESENTATION(#13,#12);
#15=DATUM_FEATURE('base','',#7,.T.);
#16=DATUM('','',#7,.F.,'A');
#17=SHAPE_ASPECT_RELATIONSHIP('','',#15,#16);
#18=LENGTH_MEASURE_WITH_UNIT(LENGTH_MEASURE(0.05),#9);
#19=FLATNESS_TOLERANCE('flatness','',#18,#8);
#20=DATUM_REFERENCE(1,#16);
#21=(GEOMETRIC_TOLERANCE('position','',#18,#8) GEOMETRIC_TOLERANCE_WITH_DATUM_REFERENCE((#20)) POSITION_TOLERANCE());
#22=DESCRIPTIVE_REPRESENTATION_ITEM('display only','Diameter 999 mm');
ENDSEC;
END-ISO-10303-21;
"""


def run_semantic_pmi(output: Path, fixtures: Path, *, refresh=False):
    source = pmi_fixture()
    cases = [("semantic",source,4,0),
             ("display_text_change",source.replace(b"999 mm",b"123 mm"),4,0),
             ("negative_tolerance",source.replace(b"LENGTH_MEASURE(0.05)",b"LENGTH_MEASURE(-0.05)"),2,2),
             ("missing_datum_link",source.replace(b"#15,#16",b"#15,#8"),2,2),
             ("wrong_dimension_target",source.replace(b"DIMENSIONAL_SIZE(#8",b"DIMENSIONAL_SIZE(#3"),3,1),
             ("unsupported_unit",source.replace(b".MILLI.",b".KILO."),1,3),
             ("unsupported_schema",source.replace(b"AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF",b"UNKNOWN"),0,1)]
    rows,detail,payloads = [],[],{}
    for name,data,count,diagnostics in cases:
        report = inspect_pmi(data)
        rows.append({"control_id":name,"semantic_count":len(report["semantic"]),"diagnostic_count":len(report["diagnostics"]),
                     "checks_pass":len(report["semantic"]) == count and len(report["diagnostics"]) == diagnostics})
        detail.append({"control_id":name,**report}); payloads[name+".step"] = data
    return finish_study(output,fixtures,"semantic_pmi","v0.66.0",rows,detail,payloads,[],
        ["controlled AP242 dimension, flatness, position and legacy datum-reference paths only; no full schema or GD&T conformance",
         "presentation text never determines semantic dimensions; source spans and unit links are retained",
         "no face binding inferred from names; geometry attachments and modern datum systems remain deferred"],refresh)


def run_spline_geometry(output: Path, fixtures: Path, *, refresh=False):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace
    from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopoDS import TopoDS
    from OCP.gp import gp_Pnt,gp_Vec
    specs = [("polynomial",SplineCurve(2,((0.,0.,0.),(1.,2.,0.),(2.,0.,0.)),(0.,1.),(3,3),(1.,1.,1.))),
             ("rational_circle",quarter_circle()),
             ("internal_knot",SplineCurve(2,((0.,0.,0.),(1.,2.,0.),(2.,1.,0.),(3.,0.,0.)),(0.,.5,1.),(3,1,3),(1.,1.,1.,1.)))]
    rows,detail,payloads,previews = [],[],{},[]
    for name,spec in specs:
        curve = kernel_curve(spec)
        shape = BRepBuilderAPI_MakeEdge(curve).Shape()
        fixture = step_round_trip(shape,name,writer_uncertainty=1e-7)
        imported = BRepAdaptor_Curve(TopoDS.Edge_s(indexed_shapes(fixture.imported_shape,TopAbs_EDGE).FindKey(1))).BSpline()
        values = []
        for t in np.linspace(0,1,17):
            truth = evaluate_curve(spec,float(t)); p,d = gp_Pnt(),gp_Vec(); curve.D1(float(t),p,d)
            values.append({"parameter":float(t),"point_error":float(np.linalg.norm(np.array(p.Coord())-truth["point"])),
                           "derivative_error":float(np.linalg.norm(np.array(d.Coord())-truth["derivative"])),
                           "exchange_error":p.Distance(imported.Value(float(t)))})
        error = max(max(r[k] for k in ("point_error","derivative_error","exchange_error")) for r in values)
        rows.append({"control_id":name,"samples":len(values),"maximum_error":error,"checks_pass":error < 1e-8})
        detail.append({"control_id":name,"input":asdict(spec),"constructed":curve_record(curve),"imported":curve_record(imported),"samples":values})
        payloads[fixture.file_name] = fixture.source_bytes; previews.append((name,shape))
    surface = rational_cylinder_patch(); shape = BRepBuilderAPI_MakeFace(surface,1e-7).Shape()
    fixture = step_round_trip(shape,"rational_surface",writer_uncertainty=1e-7)
    imported = BRepAdaptor_Surface(TopoDS.Face_s(indexed_shapes(fixture.imported_shape,TopAbs_FACE).FindKey(1))).BSpline()
    values = []
    for u in np.linspace(0,1,7):
        for v in np.linspace(0,1,5):
            point = surface.Value(float(u),float(v)); expected = evaluate_curve(quarter_circle(),float(u))["point"]; expected[2]=3*float(v)
            values.append(max(float(np.linalg.norm(np.array(point.Coord())-expected)),point.Distance(imported.Value(float(u),float(v)))))
    rows.append({"control_id":"rational_surface","samples":len(values),"maximum_error":max(values),"checks_pass":max(values) < 1e-8})
    detail.append({"control_id":"rational_surface","constructed":surface_record(surface),"imported":surface_record(imported),"errors":values})
    payloads[fixture.file_name]=fixture.source_bytes; previews.append(("Rational surface",shape))
    payloads["controls.json"]=json_bytes([asdict(s) for _,s in specs])
    return finish_study(output,fixtures,"spline_geometry","v0.67.0",rows,detail,payloads,previews,
        ["clamped nonperiodic degree 1..5, at most 64 curve poles; positive weights and bounded coordinates",
         "periodicity is recorded on exchange; periodic evaluation is explicitly unsupported",
         "independent curve basis and quarter-cylinder truth; same-parameter exchange observations do not imply universal parameter preservation"],refresh)


def run_differential_geometry(output: Path, fixtures: Path, *, refresh=False):
    from OCP.Geom import Geom_Plane, Geom_SphericalSurface, Geom_CylindricalSurface
    from OCP.gp import gp_Pln,gp_Pnt,gp_Dir,gp_Ax3
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    surfaces = [("plane",Geom_Plane(gp_Pln(gp_Pnt(),gp_Dir(0,0,1))),0.,0.),
                ("sphere",Geom_SphericalSurface(gp_Ax3(),2.),.25,-.5),
                ("cylinder",Geom_CylindricalSurface(gp_Ax3(),2.),0.,-.25),
                ("rational_cylinder",rational_cylinder_patch(),0.,-.25)]
    rows,detail,previews=[],[],[]
    for name,surface,gaussian,mean in surfaces:
        report=surface_differential(surface,.4,.3)
        error=max(abs(report["gaussian_curvature"]-gaussian),abs(report["mean_curvature"]-mean))
        reversed_report=surface_differential(surface,.4,.3,orientation=-1)
        rows.append({"control_id":name,"observed":report["mean_curvature"],"expected":mean,"checks_pass":error < 1e-9 and abs(reversed_report["mean_curvature"]+mean)<1e-9})
        detail.append({"control_id":name,**report,"reversed":reversed_report})
        previews.append((name,BRepBuilderAPI_MakeFace(surface,0.,1.,0.,1.,1e-7).Shape()))
    plane=surfaces[0][1]
    cases=[("same_plane",plane,"G2"),
           ("offset_plane",Geom_Plane(gp_Pln(gp_Pnt(0,0,.01),gp_Dir(0,0,1))),"disconnected"),
           ("tilted_plane",Geom_Plane(gp_Pln(gp_Pnt(),gp_Dir(0,1,1))),"G0")]
    for name,other,expected in cases:
        # Shared world points on the x axis, with explicit parameter pairing.
        report=sampled_continuity(plane,other,[((0.,0.),(0.,0.))])
        rows.append({"control_id":name,"observed":report["status"],"expected":expected,"checks_pass":report["status"]==expected});detail.append({"control_id":name,**report})
    # Two quadratic patches meet at the origin with common tangent plane and
    # different second derivatives: z=u^2 versus z=2u^2.
    from OCP.Geom import Geom_BezierSurface
    from OCP.TColgp import TColgp_Array2OfPnt
    patches=[]
    for curvature in (1.,2.):
        poles=TColgp_Array2OfPnt(1,3,1,2)
        for i,(x,z) in enumerate(((0.,0.),(.5,0.),(1.,curvature)),1):
            for j,y in enumerate((0.,1.),1):poles.SetValue(i,j,gp_Pnt(x,y,z))
        patches.append(Geom_BezierSurface(poles))
    report=sampled_continuity(*patches,[((0.,v),(0.,v)) for v in (0.,.5,1.)])
    rows.append({"control_id":"tangent_curvature_jump","observed":report["status"],"expected":"G1","checks_pass":report["status"]=="G1"});detail.append(report)
    sphere=surfaces[1][1]; report=surface_differential(sphere,0.,math.pi/2)
    rows.append({"control_id":"sphere_pole","observed":report["status"],"expected":"singular","checks_pass":report["status"]=="singular"});detail.append(report)
    return finish_study(output,fixtures,"differential_geometry","v0.68.0",rows,detail,{},previews,
        ["signed curvature uses du cross dv; reversing orientation reverses mean curvature",
         "generalized fundamental-form eigensystem; repeated principal values have nonunique directions",
         "continuity is a sampled positional/normal/curvature-tensor comparison, never a whole-surface proof"],refresh)


def run_intersection_analysis(output: Path, fixtures: Path, *, refresh=False):
    from OCP.Geom import Geom_Line,Geom_Plane,Geom_Circle
    from OCP.gp import gp_Pnt,gp_Dir,gp_Lin,gp_Pln,gp_Ax2
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    plane=Geom_Plane(gp_Pln(gp_Pnt(),gp_Dir(0,0,1)))
    cross=Geom_Line(gp_Lin(gp_Pnt(0,0,-2),gp_Dir(0,0,1)))
    line=Geom_Line(gp_Lin(gp_Pnt(),gp_Dir(1,0,0)))
    skew=Geom_Line(gp_Lin(gp_Pnt(0,0,1),gp_Dir(0,1,0)))
    through=Geom_Line(gp_Lin(gp_Pnt(),gp_Dir(0,1,0)))
    cases=[("curve_surface",curve_surface_intersections(cross,plane,curve_range=(0.,4.),uv_bounds=(-2.,2.,-2.,2.)),"points"),
           ("trimmed_out",curve_surface_intersections(cross,plane,curve_range=(0.,1.),uv_bounds=(-2.,2.,-2.,2.)),"disjoint"),
           ("curve_curve",curve_curve_intersections(line,through,(-2.,2.),(-2.,2.)),"points"),
           ("skew",curve_curve_intersections(line,skew,(-2.,2.),(-2.,2.)),"disjoint"),
           ("coincident",curve_curve_intersections(line,line,(-2.,2.),(-2.,2.)),"parallel_or_coincident_ambiguous"),
           ("surface_surface",surface_intersections(plane,Geom_Plane(gp_Pln(gp_Pnt(),gp_Dir(0,1,0)))),"curves")]
    circle=Geom_Circle(gp_Ax2(gp_Pnt(),gp_Dir(0,1,0)),2.)
    for name,z,count in (("two_crossings",0.,2),("tangent_contact",2.,1),("near_tangent_separated",2.+1e-5,0)):
        report=curve_surface_intersections(circle,Geom_Plane(gp_Pln(gp_Pnt(0,0,z),gp_Dir(0,0,1))),curve_range=(0.,2*math.pi),uv_bounds=(-3.,3.,-3.,3.))
        report["within_tolerance"]=report["within_tolerance"] and report["multiplicity"]==count
        cases.append((name,report,"points" if count else "disjoint"))
    rows=[{"control_id":n,"observed":r["status"],"expected":e,"checks_pass":r["status"]==e and r.get("within_tolerance",True)} for n,r,e in cases]
    detail=[{"control_id":n,**r} for n,r,_ in cases]
    face=BRepBuilderAPI_MakeFace(plane,-2.,2.,-2.,2.,1e-7).Face()
    trim=inspect_trimming(face)
    rows.append({"control_id":"planar_trim","observed":trim["checks_pass"],"expected":True,"checks_pass":trim["checks_pass"]});detail.append(trim)
    fixture=step_round_trip(face,"intersection_trim",writer_uncertainty=1e-7)
    return finish_study(output,fixtures,"intersection_analysis","v0.69.0",rows,detail,{fixture.file_name:fixture.source_bytes,"controls.json":json_bytes(detail)},[("Verified planar trim",face)],
        ["bounded curve extrema classify near-intersections; parallel/coincident cases abstain",
         "surface intersections use natural domains and sampled residuals; tangent multiplicity is not certified",
         "wire closure/orientation and p-curves are checked separately; periodic UV unwrapping is deferred"],refresh)


def run_repair_policies(output: Path, fixtures: Path, *, refresh=False):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
    from OCP.gp import gp_Pnt
    from research_notes.tolerance_sewing_healing import _independent_box_faces,_compound,_connected_box_shell
    first=BRepPrimAPI_MakeBox(2.,2.,2.).Shape()
    joined=BRepAlgoAPI_Fuse(first,BRepPrimAPI_MakeBox(gp_Pnt(2,0,0),2.,2.,2.).Shape()).Shape()
    cases=[("unify",joined,RepairPolicy("unify"),(),"accepted"),
           ("attribute_gate",joined,RepairPolicy("unify"),("face_color",),"rejected_rolled_back"),
           ("attribute_opt_in",joined,RepairPolicy("unify",allow_attribute_loss=True),("face_color",),"accepted"),
           ("sew_gap",_compound(_independent_box_faces(5e-7)),RepairPolicy("sew",tolerance=1e-6,maximum_area_change=1e-4),(),"accepted"),
           ("tolerance_gate",_compound(_independent_box_faces(5e-7)),RepairPolicy("sew",tolerance=1e-6,maximum_tolerance=1e-8),(),"rejected_rolled_back"),
           ("orientation",_connected_box_shell(flip_max_x=True),RepairPolicy("orient"),(),"accepted")]
    from research_notes.parametric_features import PlateSpec,build_plate,apply_feature,feature_spec
    from research_notes.step_reconstruction import face_evidence
    plate=PlateSpec();hole=apply_feature(build_plate(plate).shape,plate,feature_spec("through_hole",x=4.,y=4.,radius=.2)).shape
    selection=tuple(f.face_index for f in face_evidence(hole) if f.surface_type=="cylinder")
    cases.extend((("small_hole_rejected",hole,RepairPolicy("remove_faces",selected_faces=selection),(),"rejected_rolled_back"),
                  ("small_hole_explicit",hole,RepairPolicy("remove_faces",maximum_volume_change=1.,maximum_area_change=10.,selected_faces=selection),(),"accepted")))
    rows,detail,payloads,previews=[],[],{},[]
    for name,shape,policy,attributes,expected in cases:
        result=repair_shape(shape,policy,attributes=attributes)
        rows.append({"control_id":name,"decision":result.audit["status"],"expected":expected,
                     "checks_pass":result.audit["status"]==expected and (not result.audit["reasons"] or result.shape.IsSame(shape))})
        detail.append({"control_id":name,**result.audit})
        fixture=step_round_trip(result.candidate,"repair_"+name,writer_uncertainty=1e-7);payloads[fixture.file_name]=fixture.source_bytes
        previews.append((name.replace("_"," ")+"\n"+result.audit["status"].replace("_"," "),result.shape))
    return finish_study(output,fixtures,"repair_policies","v0.70.0",rows,detail,payloads,previews,
        ["operations run on a deep copy; failed validity/tolerance/volume/area/attribute gates return the original",
         "per-edge/per-face correspondences report unresolved geometry honestly; native history used where available",
         "small-feature removal requires explicit face selections and geometric budgets; no silent repair or Hausdorff claim"],refresh)
