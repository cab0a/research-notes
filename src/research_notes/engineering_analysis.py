"""Gated mass properties, witness-linked proximity, and independent mesh integrals."""
from __future__ import annotations
import math
import numpy as np
from research_notes.brep_runtime import indexed_shapes, signed_volume, surface_area_and_centroid


def closed_solid(shape):
    from OCP.BRepCheck import BRepCheck_Analyzer, BRepCheck_Shell, BRepCheck_NoError
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.TopAbs import TopAbs_SOLID,TopAbs_SHELL,TopAbs_OUT,TopAbs_FACE,TopAbs_EDGE,TopAbs_VERTEX
    from OCP.TopoDS import TopoDS
    if shape.IsNull() or not BRepCheck_Analyzer(shape).IsValid():
        raise ValueError("mass/proximity requires valid geometry")
    solids=indexed_shapes(shape,TopAbs_SOLID)
    if solids.Extent()!=1:
        raise ValueError("exactly one closed solid is required")
    solid=TopoDS.Solid_s(solids.FindKey(1))
    if any(indexed_shapes(shape,kind).Extent()!=indexed_shapes(solid,kind).Extent() for kind in (TopAbs_FACE,TopAbs_EDGE,TopAbs_VERTEX)):
        raise ValueError("free subshapes outside the solid")
    shells=indexed_shapes(solid,TopAbs_SHELL)
    for i in range(1,shells.Extent()+1):
        checker=BRepCheck_Shell(TopoDS.Shell_s(shells.FindKey(i)))
        if checker.Closed()!=BRepCheck_NoError or checker.Orientation()!=BRepCheck_NoError:
            raise ValueError("open or inconsistently oriented shell")
    classifier=BRepClass3d_SolidClassifier(solid)
    classifier.PerformInfinitePoint(1e-7)
    if classifier.State()!=TopAbs_OUT or signed_volume(solid)<=1e-12:
        raise ValueError("outward orientation and positive enclosed volume are required")
    return solid


def mass_properties(shape, *, density: float | None, density_unit="kg/m3", length_unit="mm") -> dict:
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    if density is None or not math.isfinite(density) or not 0 < density <= 1e9:
        raise ValueError("explicit positive finite material density required")
    if density_unit not in {"kg/m3","g/cm3"} or length_unit not in {"mm","cm","m","inch"}:
        raise ValueError("unsupported explicit material or length unit")
    solid=closed_solid(shape)
    scale={"mm":.001,"cm":.01,"m":1.,"inch":.0254}[length_unit]
    rho=density*(1000 if density_unit=="g/cm3" else 1)
    props=GProp_GProps();BRepGProp.VolumeProperties_s(solid,props,True,False,False)
    matrix=props.MatrixOfInertia()
    inertia=np.array([[matrix.Value(i,j) for j in range(1,4)] for i in range(1,4)])*rho*scale**5
    moments,axes=np.linalg.eigh(inertia)
    # Canonical signs improve reproducibility; repeated eigenspaces remain arbitrary.
    for i in range(3):
        if axes[np.argmax(np.abs(axes[:,i])),i]<0: axes[:,i]*=-1
    unique=all(abs(moments[j]-moments[i])>max(abs(moments[-1])*1e-8,1e-30) for i,j in ((0,1),(1,2)))
    area,_=surface_area_and_centroid(solid)
    return {"density_kg_m3":rho,"length_unit":length_unit,"volume_m3":props.Mass()*scale**3,
            "surface_area_m2":area*scale**2,"mass_kg":props.Mass()*rho*scale**3,
            "centroid_m":[v*scale for v in props.CentreOfMass().Coord()],"inertia_about_centroid_kg_m2":inertia.tolist(),
            "principal_moments_kg_m2":moments.tolist(),"principal_axes":axes.T.tolist(),"principal_axes_unique":bool(unique),
            "source":"OCCT analytic-surface integration after closure/orientation gates"}


def proximity(first,second,*,distance_tolerance=1e-7,volume_tolerance=1e-7,required_clearance=0.,transforms=None):
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    from OCP.TopAbs import TopAbs_FACE,TopAbs_EDGE,TopAbs_VERTEX
    for value in (distance_tolerance,volume_tolerance,required_clearance):
        if not math.isfinite(value) or value<0: raise ValueError("invalid proximity tolerance")
    if distance_tolerance==0 or volume_tolerance==0: raise ValueError("positive numeric tolerances required")
    a,b=closed_solid(first),closed_solid(second)
    dist=BRepExtrema_DistShapeShape(a,b);dist.Perform()
    if not dist.IsDone() or dist.NbSolution()==0: raise RuntimeError("distance evaluation failed")
    common=BRepAlgoAPI_Common(a,b)
    if not common.IsDone(): raise RuntimeError("common-volume evaluation failed")
    overlap=abs(signed_volume(common.Shape()));va,vb=abs(signed_volume(a)),abs(signed_volume(b))
    separation=dist.Value()
    if overlap>volume_tolerance:
        full_a,full_b=abs(overlap-va)<=volume_tolerance,abs(overlap-vb)<=volume_tolerance
        status="coincident" if full_a and full_b else "a_contains_b" if full_b else "b_contains_a" if full_a else "penetrating"
    else: status="touching" if separation<=distance_tolerance else "separated"
    def support(shape,item):
        for kind,enum in (("face",TopAbs_FACE),("edge",TopAbs_EDGE),("vertex",TopAbs_VERTEX)):
            index=indexed_shapes(shape,enum).FindIndex(item)
            if index:return {"kind":kind,"analysis_local_index":index}
        return {"kind":"unknown","analysis_local_index":None}
    witnesses=[{"a_point":list(dist.PointOnShape1(i).Coord()),"b_point":list(dist.PointOnShape2(i).Coord()),
                "a_support":support(a,dist.SupportOnShape1(i)),"b_support":support(b,dist.SupportOnShape2(i))}
               for i in range(1,min(dist.NbSolution(),64)+1)]
    # OCCT may enumerate tied witnesses differently across builds/threads. Order
    # by support identity and rounded coordinates without changing measurements.
    witnesses = ordered_witnesses(witnesses)
    return {"status":status,"minimum_distance":separation,"overlap_volume":overlap,
            "required_clearance":required_clearance,"clearance_satisfied":status=="separated" and separation+distance_tolerance>=required_clearance or status=="touching" and required_clearance==0,
            "distance_tolerance":distance_tolerance,"volume_tolerance":volume_tolerance,"witnesses":witnesses,
            "witness_count":dist.NbSolution(),"witnesses_truncated":dist.NbSolution()>64,
            "transform_provenance":transforms,"units":"caller-declared common model units; mm in reference controls",
            "penetration_depth":None}


def ordered_witnesses(witnesses):
    def key(item):
        supports = tuple((item[side]["kind"], item[side]["analysis_local_index"] or 0)
                         for side in ("a_support", "b_support"))
        points = tuple(round(value, 12) for side in ("a_point", "b_point") for value in item[side])
        return supports, points
    return sorted(witnesses, key=key)


def mesh_mass_properties(shape,*,deflection=.05,angular_deflection=.2):
    """Independent signed tetrahedron moments over kernel-produced triangles."""
    from OCP.BRep import BRep_Tool
    from OCP.BRepTools import BRepTools
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopAbs import TopAbs_FACE,TopAbs_REVERSED
    from OCP.TopoDS import TopoDS
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy
    if not all(math.isfinite(v) and 0<v<=1 for v in (deflection,angular_deflection)):raise ValueError("invalid mesh precision")
    source=closed_solid(shape);copy=BRepBuilderAPI_Copy(source).Shape();BRepTools.Clean_s(copy,True)
    mesher=BRepMesh_IncrementalMesh(copy,deflection,False,angular_deflection,False)
    if not mesher.IsDone():raise RuntimeError("mesh failed")
    volume=area=0.; first=np.zeros(3);second=np.zeros((3,3));triangles=0
    faces=indexed_shapes(copy,TopAbs_FACE)
    for i in range(1,faces.Extent()+1):
        face=TopoDS.Face_s(faces.FindKey(i));location=TopLoc_Location();mesh=BRep_Tool.Triangulation_s(face,location)
        if mesh is None:raise RuntimeError("face lacks triangulation")
        for j in range(1,mesh.NbTriangles()+1):
            tri=mesh.Triangle(j)
            points=np.array([mesh.Node(tri.Value(k)).Transformed(location.Transformation()).Coord() for k in (1,2,3)])
            if face.Orientation()==TopAbs_REVERSED:points=points[[0,2,1]]
            a,b,c=points;v=float(np.dot(a,np.cross(b,c)))/6
            total=points.sum(axis=0);volume+=v;first+=v*total/4;second+=v*(points.T@points+np.outer(total,total))/20
            area+=float(np.linalg.norm(np.cross(b-a,c-a)))/2;triangles+=1
            if triangles>1_000_000:raise ValueError("triangle integration budget exceeded")
    if volume<=0:raise ValueError("nonpositive oriented mesh volume")
    center=first/volume;central=second-volume*np.outer(center,center)
    inertia=np.eye(3)*np.trace(central)-central
    return {"volume":volume,"area":area,"centroid":center.tolist(),"unit_density_inertia":inertia.tolist(),"triangles":triangles,
            "independence":"tetrahedron arithmetic independent of GProp; tessellation still uses OCCT"}
