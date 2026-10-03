"""Authored truth for v1.12; no recognizer is used to build expected values."""
from __future__ import annotations

from dataclasses import dataclass, field
import math


@dataclass
class Control:
    identifier: str
    category: str
    description: str
    shape: object
    expected: list[dict] = field(default_factory=list)


def cut(a, b):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    operation = BRepAlgoAPI_Cut(a, b)
    if not operation.IsDone():
        raise RuntimeError('Control construction cut failed.')
    return operation.Shape()


def fuse(a, b):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse
    operation = BRepAlgoAPI_Fuse(a, b)
    if not operation.IsDone():
        raise RuntimeError('Control construction fuse failed.')
    return operation.Shape()


def box(x, y, z, dx, dy, dz):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Pnt
    return BRepPrimAPI_MakeBox(gp_Pnt(x,y,z),dx,dy,dz).Shape()


def cylinder(x=7., y=5., z=-1., radius=1., depth=6.):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x,y,z),gp_Dir(0,0,1)),radius,depth).Shape()


def plate(depth=4., width=14.):
    # The corner notch deliberately puts these controls outside the strict
    # rectangular-plate certificate, so unified inspection uses local rules.
    return cut(box(0.,0.,0.,width,10.,depth),box(-1.,-1.,-1.,3.,3.,depth+2.))


def moved(shape, dx, dy, dz):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Trsf, gp_Vec
    transform = gp_Trsf()
    transform.SetTranslation(gp_Vec(dx,dy,dz))
    return BRepBuilderAPI_Transform(shape,transform,True).Shape()


def compound(*shapes):
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound
    builder, result = BRep_Builder(), TopoDS_Compound()
    builder.MakeCompound(result)
    for shape in shapes:
        builder.Add(result,shape)
    return result


def mixed_control(depth=4.):
    from research_notes.slot_benchmark import capsule_prism
    shape = cut(cut(plate(depth,36.),cylinder(depth=depth+2.)),
                moved(capsule_prism(height=depth+2.),20.,0.,0.))
    return Control('mixed','qualified','Separate round hole and straight through slot.',shape,[
        {'feature_type':'circular_hole','diameter_mm':2.,'depth_mm':depth,
         'ends_mm':[[7.,5.,0.],[7.,5.,depth]],'long_direction':None},
        {'feature_type':'straight_slot','width_mm':2.,'length_mm':6.,'depth_mm':depth,
         'ends_mm':[[27.,5.,0.],[27.,5.,depth]],'long_direction':[1.,0.,0.]}
    ])


def transformed(control, identifier, *, scale=1., angle=0., translation=(0.,0.,0.)):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
    scaling, rotation = gp_Trsf(), gp_Trsf()
    scaling.SetScale(gp_Pnt(0,0,0),scale)
    rotation.SetRotation(gp_Ax1(gp_Pnt(0,0,0),gp_Dir(1,2,3)),angle)
    rotation.SetTranslationPart(gp_Vec(*translation))
    transform = rotation.Multiplied(scaling)
    shape = BRepBuilderAPI_Transform(control.shape,transform,True).Shape()
    expected=[]
    for row in control.expected:
        values={k:(v*scale if k.endswith('_mm') and isinstance(v,(int,float)) else v)
                for k,v in row.items()}
        values['ends_mm']=[list(gp_Pnt(*p).Transformed(transform).Coord()) for p in row['ends_mm']]
        values['long_direction']=(list(gp_Dir(*row['long_direction']).Transformed(rotation).Coord())
                                  if row['long_direction'] else None)
        expected.append(values)
    return Control(identifier,'qualified',f'Uniform scale {scale}, rotation {angle} rad about (1,2,3), translation {translation}.',shape,expected)


def geometry_controls():
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire, BRepBuilderAPI_MakeFace, BRepBuilderAPI_NurbsConvert
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism, BRepPrimAPI_MakeCone, BRepPrimAPI_MakeCylinder
    from OCP.GC import GC_MakeArcOfCircle
    from OCP.BRepFeat import BRepFeat_SplitShape
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopoDS import TopoDS
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt, gp_Vec, gp_Elips
    from research_notes.brep_runtime import iter_shapes, surface_area_and_centroid
    from research_notes.slot_benchmark import capsule_prism

    base=mixed_control()
    controls=[base]
    transforms=[('rotated_30',1.,math.pi/6,(0,0,0)),
                ('rotated_3d',1.,.73,(13,-7,21)),
                ('flipped',1.,math.pi,(0,0,0)),
                ('near_quarter_turn',1.,math.pi/2+1e-9,(0,0,0)),
                ('small_001',.01,0.,(0,0,0)),('small_01',.1,0.,(0,0,0)),
                ('large_10',10.,0.,(0,0,0)),('large_100',100.,0.,(0,0,0)),
                ('translated_1e6',1.,0.,(1e6,-1e6,1e6)),
                ('combined',.1,.73,(1e4,-1e4,1e4)),
                ('large_combined',100.,.73,(1e6,-1e6,1e6)),
                ('radius_above_gate',.00101,0.,(0,0,0))]
    controls.extend(transformed(base,identifier,scale=s,angle=a,translation=t) for identifier,s,a,t in transforms)
    for control in controls:
        if control.identifier in {'large_100','translated_1e6','large_combined'}:
            control.category='stress'
    thin=mixed_control(.00101)
    thin.identifier='depth_above_gate'
    thin.description='Through length 0.00101 mm, above the 100*TOL local gate.'
    controls.append(thin)
    for identifier,s in [('radius_at_gate',.001),('radius_below_gate',.00099)]:
        c=transformed(base,identifier,scale=s)
        c.category='boundary_withheld'
        c.description='Physical openings exist; radius at/below 100*TOL is deliberately withheld.'
        c.expected=[]
        controls.append(c)
    thin=mixed_control(.00099)
    thin.identifier='depth_below_gate';thin.category='boundary_withheld';thin.expected=[]
    thin.description='Physical openings exist; through length below 100*TOL is deliberately withheld.'
    controls.append(thin)

    body=plate()
    circle=cut(body,cylinder())
    slot=cut(body,capsule_prism())
    cone=BRepPrimAPI_MakeCone(gp_Ax2(gp_Pnt(7,5,-1),gp_Dir(0,0,1)),1.,2.,6.).Shape()
    ellipse=gp_Elips(gp_Ax2(gp_Pnt(7,5,-1),gp_Dir(0,0,1)),3.,1.)
    ellipse_wire=BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(ellipse).Edge()).Wire()
    ellipse_tool=BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeFace(ellipse_wire).Face(),gp_Vec(0,0,6)).Shape()
    curved_outer=BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(4,4,-1),gp_Dir(0,0,1)),4.,6.,math.pi/2).Shape()
    curved_tool=cut(curved_outer,cylinder(4,4,-2,2.,8.))
    slanted_tool=BRepPrimAPI_MakePrism(
        BRepBuilderAPI_MakeFace(BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeEdge(ellipse).Edge()).Wire()).Face(),
        gp_Vec(.5,0,6)).Shape()
    uneven_wire=BRepBuilderAPI_MakeWire()
    p1,p2,p3,p4=[gp_Pnt(x,y,-1) for x,y in ((5,4),(9,3.8),(9,6.2),(5,6))]
    for edge in (BRepBuilderAPI_MakeEdge(p1,p2).Edge(),
                 BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(p2,gp_Pnt(10.2,5,-1),p3).Value()).Edge(),
                 BRepBuilderAPI_MakeEdge(p3,p4).Edge(),
                 BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(p4,gp_Pnt(4,5,-1),p1).Value()).Edge()):
        uneven_wire.Add(edge)
    uneven_tool=BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeFace(uneven_wire.Wire()).Face(),gp_Vec(0,0,6)).Shape()
    bottom=min(iter_shapes(capsule_prism(),TopAbs_FACE),key=lambda f:surface_area_and_centroid(TopoDS.Face_s(f))[1][2])
    skew_slot=BRepPrimAPI_MakePrism(TopoDS.Face_s(bottom),gp_Vec(.5,0,6)).Shape()
    split=BRepFeat_SplitShape(circle)
    cylinder_face=next(TopoDS.Face_s(f) for f in iter_shapes(circle,TopAbs_FACE)
                       if BRepAdaptor_Surface(TopoDS.Face_s(f)).GetType()==GeomAbs_Cylinder)
    split.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(6,5,0),gp_Pnt(6,5,4)).Edge(),cylinder_face)
    split.Build()
    if not split.IsDone():
        raise RuntimeError('Split-cylinder control construction failed.')
    negatives=[
        ('circle_blind','Flat-bottom round recess.',cut(body,cylinder(z=2.,depth=3.))),
        ('circle_counterbore','Circular counter-recess around a smaller bore.',cut(circle,cylinder(z=2.,radius=2.,depth=3.))),
        ('circle_rectangular_shoulder','Round bore under a rectangular counter-recess.',cut(circle,box(3,2,2,8,6,3))),
        ('circle_countersink','Conical countersink around a smaller bore.',cut(circle,BRepPrimAPI_MakeCone(gp_Ax2(gp_Pnt(7,5,2),gp_Dir(0,0,1)),1.,3.,3.).Shape())),
        ('circle_edge_notch','Round cut opens onto the outside edge.',cut(body,cylinder(x=14.))),
        ('circle_intersection','Intersecting bores have trimmed cylinders.',cut(circle,cylinder(x=8.))),
        ('circle_boss','Exterior cylinder is material, not a cavity.',fuse(body,cylinder(z=3.,depth=3.))),
        ('circle_internal_void','Cylindrical cavity has neither outer opening.',cut(body,cylinder(z=1.,depth=2.))),
        ('circle_tapered','Conical through passage.',cut(body,cone)),
        ('circle_split_face','Same bore with the cylindrical wall split into faces.',split.Shape()),
        ('circle_spline','Exact bore converted to NURBS supports.',BRepBuilderAPI_NurbsConvert(circle,True).Shape()),
        ('ellipse','Elliptical through opening.',cut(body,ellipse_tool)),
        ('rectangle','Rectangular through opening.',cut(body,box(4,4,-1,6,2,6))),
        ('slanted_ellipse','Elliptical prism skew to its opening plane.',cut(body,slanted_tool)),
        ('washer','Annular outer face is ambiguous with a shoulder.',cut(cylinder(radius=4.,z=0.,depth=4.),cylinder())),
        ('slot_blind','Capsule-shaped blind pocket.',cut(body,capsule_prism(z=2.,height=3.))),
        ('slot_counterbore','Larger capsule counter-recess.',cut(slot,capsule_prism(radius=2.,z=2.,height=3.))),
        ('slot_rectangular_shoulder','Slot under a rectangular counter-recess.',cut(slot,box(3,2,2,8,6,3))),
        ('slot_open_notch','Capsule cut opens onto the outside edge.',cut(plate(width=7.),capsule_prism())),
        ('slot_boss','Exterior capsule protrusion.',fuse(body,capsule_prism(z=3.,height=3.))),
        ('slot_interrupted','Bridge is fused across the passage.',fuse(slot,box(6,0,1,1,10,1))),
        ('slot_curved','Quarter-annular through cut, not a straight capsule.',cut(body,curved_tool)),
        ('slot_unequal_ends','Unequal semicircle radii with non-tangent sides.',cut(body,uneven_tool)),
        ('slot_skew_passage','Capsule extrusion skew to its opening planes.',cut(body,skew_slot)),
        ('slot_spline','Exact capsule converted to NURBS supports.',BRepBuilderAPI_NurbsConvert(slot,True).Shape()),
    ]
    controls.extend(Control(i,'unsupported',d,s) for i,d,s in negatives)
    # Qualified features elsewhere survive an unrelated unsupported pocket.
    controls.append(Control('mixed_with_blind','qualified','One supported circle and slot plus a blind round recess.',
                            cut(base.shape,cylinder(x=18.,z=2.,depth=3.)),base.expected))
    # This deliberately remains a per-component observation, not an assembly
    # clearance certificate. The second solid caps both openings.
    controls.append(Control('assembly_obstructed','known_limit','Separate solids cap the openings; local per-part holes remain qualified.',
                            compound(base.shape,box(4,2,4,28,6,1)),base.expected))
    return controls


def with_tolerance(shape, kind, value):
    from OCP.BRep import BRep_Builder
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy
    from OCP.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX
    from OCP.TopoDS import TopoDS
    from research_notes.brep_runtime import iter_shapes
    clone=BRepBuilderAPI_Copy(shape).Shape()
    builder=BRep_Builder()
    typ,cast,update={'face':(TopAbs_FACE,TopoDS.Face_s,builder.UpdateFace),
                     'edge':(TopAbs_EDGE,TopoDS.Edge_s,builder.UpdateEdge),
                     'vertex':(TopAbs_VERTEX,TopoDS.Vertex_s,builder.UpdateVertex)}[kind]
    for member in iter_shapes(clone,typ):
        update(cast(member),value)
    return clone
