"""Bounded intersections and independent p-curve/loop residual observations."""
from __future__ import annotations
import math
import numpy as np


def curve_surface_intersections(curve, surface, *, curve_range, uv_bounds, tolerance=1e-7):
    from OCP.GeomAPI import GeomAPI_IntCS
    if not math.isfinite(tolerance) or tolerance <= 0 or len(uv_bounds) != 4 or len(curve_range) != 2 or not all(math.isfinite(x) for x in (*curve_range,*uv_bounds)):
        raise ValueError("invalid intersection domain")
    if curve_range[0] >= curve_range[1] or uv_bounds[0] >= uv_bounds[1] or uv_bounds[2] >= uv_bounds[3]:
        raise ValueError("empty intersection domain")
    operation = GeomAPI_IntCS(curve, surface)
    if not operation.IsDone():
        raise RuntimeError("intersection failed")
    points = []
    for i in range(1,operation.NbPoints()+1):
        u,v,t = operation.Parameters(i)
        if not (curve_range[0]-tolerance <= t <= curve_range[1]+tolerance and uv_bounds[0]-tolerance <= u <= uv_bounds[1]+tolerance and uv_bounds[2]-tolerance <= v <= uv_bounds[3]+tolerance):
            continue
        residual = curve.Value(t).Distance(surface.Value(u,v))
        points.append({"point": list(operation.Point(i).Coord()), "curve_parameter": t, "uv": [u,v], "residual": residual})
    return {"status": "overlap_or_tangent_segment" if operation.NbSegments() else "points" if points else "disjoint",
            "points": points, "coincident_segments": operation.NbSegments(), "multiplicity": len(points),
            "within_tolerance": all(p["residual"] <= tolerance for p in points)}


def curve_curve_intersections(first, second, first_range, second_range, *, tolerance=1e-7):
    from OCP.GeomAPI import GeomAPI_ExtremaCurveCurve
    if not math.isfinite(tolerance) or tolerance <= 0 or any(len(r) != 2 or not all(math.isfinite(v) for v in r) or r[0] >= r[1] for r in (first_range,second_range)):
        raise ValueError("invalid curve interval or tolerance")
    operation = GeomAPI_ExtremaCurveCurve(first,second,*first_range,*second_range)
    if operation.IsParallel():
        return {"status": "parallel_or_coincident_ambiguous", "points": [], "multiplicity": None}
    rows = []
    for i in range(1,operation.NbExtrema()+1):
        a,b = operation.Parameters(i)
        distance = first.Value(a).Distance(second.Value(b))
        if distance <= tolerance:
            rows.append({"first_parameter": a,"second_parameter": b,"residual": distance,"point": list(first.Value(a).Coord())})
    return {"status": "points" if rows else "disjoint", "points": rows, "multiplicity": len(rows)}


def surface_intersections(first, second, *, sample_parameters=(-1.,0.,1.), tolerance=1e-7):
    from OCP.GeomAPI import GeomAPI_IntSS, GeomAPI_ProjectPointOnSurf
    values = tuple(sample_parameters)
    if not 1 <= len(values) <= 64 or not all(math.isfinite(x) for x in values) or not math.isfinite(tolerance) or tolerance <= 0:
        raise ValueError("invalid surface intersection budget")
    operation = GeomAPI_IntSS(first,second,tolerance)
    if not operation.IsDone():
        raise RuntimeError("surface intersection failed")
    rows = []
    for i in range(1,operation.NbLines()+1):
        line = operation.Line(i)
        for t in values:
            if not line.FirstParameter() <= t <= line.LastParameter():
                continue
            point = line.Value(t)
            residuals = []
            for surface in (first,second):
                projection = GeomAPI_ProjectPointOnSurf(point,surface)
                if projection.NbPoints() == 0:
                    raise RuntimeError("intersection projection unavailable")
                residuals.append(projection.LowerDistance())
            rows.append({"line_index":i,"parameter":t,"point":list(point.Coord()),"residuals":residuals})
    return {"status":"curves" if operation.NbLines() else "no_curve_or_coincident_ambiguous", "curve_count":operation.NbLines(),
            "samples":rows,"within_tolerance":all(max(r["residuals"]) <= tolerance for r in rows),
            "scope":"natural surface domains; bounded samples, not trimmed-solid intersection"}


def inspect_trimming(face, *, samples=17, tolerance=1e-6):
    from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
    from OCP.BRep import BRep_Tool
    from OCP.BRepCheck import BRepCheck_Analyzer, BRepCheck_Wire, BRepCheck_NoError
    from OCP.BRepTools import BRepTools_WireExplorer
    from OCP.TopAbs import TopAbs_WIRE, TopAbs_REVERSED
    from OCP.TopoDS import TopoDS
    from research_notes.brep_runtime import indexed_shapes
    if type(samples) is not int or not 3 <= samples <= 257 or not math.isfinite(tolerance) or tolerance <= 0:
        raise ValueError("invalid trimming budget")
    surface, rows = BRepAdaptor_Surface(face), []
    wires = indexed_shapes(face,TopAbs_WIRE)
    for i in range(1,wires.Extent()+1):
        wire = TopoDS.Wire_s(wires.FindKey(i))
        checker = BRepCheck_Wire(wire)
        explorer = BRepTools_WireExplorer(wire,face)
        points, uv_points, residuals = [], [], []
        while explorer.More():
            edge = explorer.Current()
            if not BRep_Tool.Degenerated_s(edge):
                curve = BRepAdaptor_Curve(edge)
                pcurve = BRep_Tool.CurveOnSurface_s(edge,face,0.,0.)
                if pcurve is None:
                    raise ValueError("edge lacks a usable p-curve")
                times = np.linspace(curve.FirstParameter(),curve.LastParameter(),samples)
                if edge.Orientation() == TopAbs_REVERSED:
                    times = times[::-1]
                edge_points = []
                for t in times:
                    uv = pcurve.Value(float(t)); p = curve.Value(float(t))
                    residuals.append(p.Distance(surface.Value(uv.X(),uv.Y())))
                    uv_points.append((uv.X(),uv.Y())); edge_points.append(np.array(p.Coord()))
                points.append((edge_points[0],edge_points[-1]))
            explorer.Next()
        gaps = [float(np.linalg.norm(a[1]-b[0])) for a,b in zip(points,points[1:]+points[:1])]
        area = sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(uv_points,uv_points[1:]+uv_points[:1]))/2
        rows.append({"wire_index":i,"closed":checker.Closed() == BRepCheck_NoError,
                     "orientation_valid":checker.Orientation(face) == BRepCheck_NoError,
                     "maximum_endpoint_gap":max(gaps,default=0.), "maximum_pcurve_residual":max(residuals,default=0.),
                     "sampled_signed_uv_area":area})
    return {"analyzer_valid":BRepCheck_Analyzer(face).IsValid(), "wires":rows,
            "checks_pass":bool(rows) and all(r["closed"] and r["orientation_valid"] and max(r["maximum_endpoint_gap"],r["maximum_pcurve_residual"]) <= tolerance for r in rows),
            "scope":"sampled p-curve agreement and kernel wire checks; UV area assumes no periodic seam unwrap"}
