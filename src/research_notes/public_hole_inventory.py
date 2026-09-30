"""Read public STEP geometry and measure locally verified circular through holes.

Local successes never certify the total number of openings in an arbitrary part.
The original plate grammar remains the only whole-part completeness certificate.
"""
from __future__ import annotations

import math
from pathlib import Path

from research_notes.brep_runtime import indexed_shapes, iter_shapes, surface_area_and_centroid
from research_notes.feature_recognition import _face_geometry
from research_notes.spatial_workflow import WorkBudget

TOL = 1e-5
PUBLIC_BUDGET = WorkBudget(max_bytes=2_000_000, max_geometry=128, max_topology=20_000)


def _distance(a, b):
    return math.sqrt(sum((x-y)**2 for x,y in zip(a,b)))


def circular_inner_rims(shape):
    """Independent boundary observations: planar inner wires, without cylinder supports."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
    from OCP.BRepTools import BRepTools
    from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Plane
    from OCP.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_WIRE
    from OCP.TopoDS import TopoDS

    faces, edges = indexed_shapes(shape, TopAbs_FACE), indexed_shapes(shape, TopAbs_EDGE)
    rims, other_wires = [], []
    for i in range(1, faces.Extent()+1):
        face = TopoDS.Face_s(faces.FindKey(i))
        if BRepAdaptor_Surface(face, True).GetType() != GeomAbs_Plane:
            continue
        outer = BRepTools.OuterWire_s(face)
        outer_edges = indexed_shapes(outer, TopAbs_EDGE)
        circular_outer = outer_edges.Extent() == 1 and BRepAdaptor_Curve(TopoDS.Edge_s(outer_edges.FindKey(1))).GetType() == GeomAbs_Circle
        for wire in iter_shapes(face, TopAbs_WIRE):
            if wire.IsSame(outer):
                continue
            members = indexed_shapes(wire, TopAbs_EDGE)
            row = {'plane_face':i, 'edge_count':members.Extent(), 'circular_outer_boundary':circular_outer}
            if members.Extent() == 1:
                edge = TopoDS.Edge_s(members.FindKey(1))
                curve = BRepAdaptor_Curve(edge)
                if curve.GetType() == GeomAbs_Circle and abs(curve.LastParameter()-curve.FirstParameter()-2*math.pi) <= 1e-7:
                    circle = curve.Circle()
                    rims.append({**row, 'edge':edges.FindIndex(edge), 'center':list(circle.Location().Coord()),
                                 'radius':circle.Radius(), 'normal':list(circle.Axis().Direction().Coord())})
                    continue
            other_wires.append(row)
    return rims, other_wires


def scan_circular_through_holes(shape):
    """Qualify complete inward cylinders ending at two circular inner planar rims.

    A material classifier samples each cylinder on both radial sides and checks
    the axis inside and beyond both openings. Samples supplement, not replace,
    exact support, full-ring, adjacency and area checks. The result is partial.
    """
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.BRepTools import BRepTools
    from OCP.BRep import BRep_Tool
    from OCP.GeomAbs import GeomAbs_Cylinder
    from OCP.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_SOLID, TopAbs_IN, TopAbs_OUT
    from OCP.TopoDS import TopoDS
    from OCP.gp import gp_Pnt

    faces, edges, solids = (indexed_shapes(shape,t) for t in (TopAbs_FACE,TopAbs_EDGE,TopAbs_SOLID))
    if faces.Extent()>512:
        raise ValueError('円形穴の検証は最大512面です。')
    owners={i:[] for i in range(1,faces.Extent()+1)}
    classifiers={}
    for s in range(1,solids.Extent()+1):
        solid=TopoDS.Solid_s(solids.FindKey(s))
        classifiers[s]=BRepClass3d_SolidClassifier(solid)
        for face in iter_shapes(solid,TopAbs_FACE):
            owners[faces.FindIndex(face)].append(s)
    rims, other_wires=circular_inner_rims(shape)
    rim_edges={r['edge']:r for r in rims}
    rows, withheld, convex = [], [], []
    for i in range(1,faces.Extent()+1):
        face=TopoDS.Face_s(faces.FindKey(i));surface=BRepAdaptor_Surface(face,True)
        if surface.GetType()!=GeomAbs_Cylinder:
            continue
        geometry=_face_geometry(face)
        if geometry[7] is not None and geometry[7]>0.5:
            convex.append(i);continue
        try:
            if BRep_Tool.Tolerance_s(face)>TOL or any(BRep_Tool.Tolerance_s(TopoDS.Edge_s(e))>TOL for e in iter_shapes(face,TopAbs_EDGE)):
                raise ValueError('円筒面・境界の許容差が検証許容差を超えています。')
            if len(owners[i])!=1:
                raise ValueError('単一ソリッドに属する円筒面ではありません。')
            if geometry[7] is None or geometry[7]>-0.99:
                raise ValueError('内向きの円筒面を確認できません。')
            if abs(geometry[2]-2*math.pi)>1e-7:
                raise ValueError('円筒が一周していません。長穴・切欠き・面分割などを保留します。')
            boundary={edges.FindIndex(e) for e in iter_shapes(face,TopAbs_EDGE)}
            ends=[rim_edges[e] for e in boundary if e in rim_edges]
            if len(ends)!=2 or ends[0]['plane_face']==ends[1]['plane_face']:
                raise ValueError('両端の平面にある完全な円形の内周を確認できません。止まり穴・段付き穴などを保留します。')
            if any(end['circular_outer_boundary'] for end in ends):
                raise ValueError('円形外周の開口面は段付き穴の内部段差と区別せず保留します。ワッシャー等も対象外です。')
            cylinder=surface.Cylinder();radius=cylinder.Radius();direction=list(cylinder.Axis().Direction().Coord())
            entry,exit=sorted((r['center'] for r in ends),reverse=True)
            depth=_distance(entry,exit)
            if radius<=100*TOL or depth<=100*TOL:
                raise ValueError('半径または深さが検証許容差に近すぎます。')
            axis=[(b-a)/depth for a,b in zip(entry,exit)]
            if abs(sum(a*b for a,b in zip(axis,direction)))<1-1e-8:
                raise ValueError('開口間の方向が円筒軸と一致しません。')
            origin=list(cylinder.Location().Coord())
            for end in ends:
                delta=[v-o for v,o in zip(end['center'],origin)]
                axial=sum(v*d for v,d in zip(delta,direction))
                if math.sqrt(sum((v-axial*d)**2 for v,d in zip(delta,direction)))>TOL or abs(end['radius']-radius)>TOL:
                    raise ValueError('円筒面と開口円の位置・径が一致しません。')
                if abs(sum(a*b for a,b in zip(end['normal'],direction)))<1-1e-8:
                    raise ValueError('開口平面が円筒軸に直交しません。')
            area,_=surface_area_and_centroid(face)
            if abs(area-2*math.pi*radius*depth)>max(1e-7,area*1e-8):
                raise ValueError('円筒面の面積に切欠き・追加境界があります。')
            classifier=classifiers[owners[i][0]]
            def material(point):
                classifier.Perform(gp_Pnt(*point),TOL)
                return classifier.State()
            u0,u1,v0,v1=BRepTools.UVBounds_s(face)
            offset=max(20*TOL,min(radius,depth)*1e-4)
            for fraction in (.2,.5,.8):
                center=[a+fraction*(b-a) for a,b in zip(entry,exit)]
                if material(center)!=TopAbs_OUT:
                    raise ValueError('穴内部に材料または不確定な境界があります。')
                for angle in range(8):
                    point=list(surface.Value(u0+(angle+.37)*(u1-u0)/8,v0+fraction*(v1-v0)).Coord())
                    delta=[v-o for v,o in zip(point,origin)];axial=sum(v*d for v,d in zip(delta,direction))
                    radial=[(v-axial*d)/radius for v,d in zip(delta,direction)]
                    if material([v-offset*r for v,r in zip(point,radial)])!=TopAbs_OUT or material([v+offset*r for v,r in zip(point,radial)])!=TopAbs_IN:
                        raise ValueError('円筒壁の内外の材料状態を確認できません。')
            for point in ([a-offset*d for a,d in zip(entry,axis)],[b+offset*d for b,d in zip(exit,axis)]):
                if material(point)!=TopAbs_OUT:
                    raise ValueError('両端の開口を確認できません。')
            clean=lambda values:[0. if abs(x)<1e-12 else round(float(x),9) for x in values]
            entry,axis=clean(entry),clean(axis)
            rows.append({'kind':'through','diameter_mm':round(2*radius,9),'x_mm':entry[0],'y_mm':entry[1],
                         'entry_z_mm':entry[2],'depth_mm':round(depth,9),'axis':axis,'faces':[i],
                         'solid_index':owners[i][0],'opening_faces':sorted(r['plane_face'] for r in ends),
                         'opening_edges':sorted(r['edge'] for r in ends), 'measurement_basis':'cylinder_support_and_two_inner_circular_rims',
                         'radial_material_samples':48,'axial_void_samples':5})
        except (ValueError,RuntimeError) as error:
            withheld.append({'face_index':i,'reason':str(error)})
    rows.sort(key=lambda h:(h['solid_index'],h['x_mm'],h['y_mm'],h['entry_z_mm'],h['diameter_mm']))
    for index,row in enumerate(rows,1):row['id']=f'H{index}'
    return {'holes':rows,'recognized_hole_count':len(rows),'hole_count':None,
            'status':'partial' if rows else 'unresolved',
            'reason':(f'円形貫通穴{len(rows)}個を局所検証しました。' if rows else '条件を満たす円形貫通穴を確認できませんでした。')+'長穴・複雑な穴を含む全体の穴数は確定していません。',
            'withheld_cylinders':withheld,'external_cylinder_faces':convex,
            'noncircular_planar_inner_wires':other_wires,
            'scanned_faces':faces.Extent(),'scanned_solids':solids.Extent()}


def inspect_holes(path: Path):
    from research_notes.public_step import read_step_for_inspection
    from research_notes.hole_inventory import describe_holes
    inspection=read_step_for_inspection(path,budget=PUBLIC_BUDGET)
    imported=inspection.imported
    if imported.metrics.solid_count==1 and imported.metrics.shell_count==1:
        analysis=describe_holes(imported)
    else:
        analysis={'status':'unresolved','reason':'複数ソリッドまたは非ソリッドを全体の板モデルとして確定しません。'}
    if analysis['status']=='complete':
        analysis['recognized_hole_count']=analysis['hole_count']
    else:
        whole_reason=analysis['reason']
        analysis=scan_circular_through_holes(imported.shape)
        analysis['whole_part_reason']=whole_reason
    return inspection,analysis
