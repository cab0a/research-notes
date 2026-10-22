"""SVG-only reconstruction of bounded native TechDraw graphics.

No paired DXF, source CAD or truth is read by interpret_native_svg.
"""
from __future__ import annotations
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from .drawing_to_cad import DrawingIssue, FAMILY, require, feature_model, candidate_code, json_bytes
from .svg_drawing_graphics import EPS, normalize, circle, samples

NUM = r"[0-9]+(?:\.[0-9]+)?"


def need(condition, code, detail, stage="drawing_conflict"):
    require(condition, code, stage, detail)


def close(a, b):
    return math.dist(a, b) <= EPS


def unit(a, b):
    d = math.dist(a, b)
    need(d > EPS, "svg_degenerate", "nonzero segment required")
    return tuple((b[i]-a[i])/d for i in range(2))


def dot(a, b):
    return sum(x*y for x,y in zip(a,b))


def relative(a, b):
    return tuple(a[i]-b[i] for i in range(2))


def line_distance(p, a, b):
    u = unit(a,b)
    return abs((p[0]-a[0])*u[1]-(p[1]-a[1])*u[0])


def on_segment(p, a, b):
    return line_distance(p,a,b) <= EPS and -EPS <= dot(relative(p,a),unit(a,b)) <= math.dist(a,b)+EPS


def rectangle(path):
    need(len(path) == 4 and all(s[0] == "L" for s in path) and close(path[-1][-1],path[0][1]),
         "svg_profile", "closed four-line profile required", "unsupported_input")
    pts = [s[1] for s in path]
    x,y = min(p[0] for p in pts),min(p[1] for p in pts)
    w,h = max(p[0] for p in pts)-x,max(p[1] for p in pts)-y
    need(min(w,h) > EPS and all(abs(a[0]-b[0]) <= EPS or abs(a[1]-b[1]) <= EPS for _,a,b in path)
         and len({(round(p[0],5),round(p[1],5)) for p in pts}) == 4,
         "svg_profile", "axis-aligned rectangle required", "unsupported_input")
    return (x,y,w,h)


def arrow(path):
    need(len(path) == 3 and all(s[0] == "L" for s in path) and close(path[-1][-1],path[0][1]),
         "svg_arrow", "closed triangular arrow required", "unsupported_input")
    pts = [s[1] for s in path]
    lengths = [math.dist(pts[i],pts[(i+1)%3]) for i in range(3)]
    base = min(range(3),key=lengths.__getitem__)
    tip = pts[(base+2)%3];mid = tuple((pts[base][i]+pts[(base+1)%3][i])/2 for i in range(2))
    sides = [v for i,v in enumerate(lengths) if i != base]
    need(abs(sides[0]-sides[1]) <= EPS and .15 < lengths[base]/max(sides) < .6,
         "svg_arrow", "bounded isosceles arrow required", "unsupported_input")
    return tip,unit(tip,mid)


def interpret_native_svg(source:bytes, context:dict):
    base = dict(schema_version="1.0.0", method="C_native_SVG_graphic_dimension_association", input_format="svg",
                source_sha256=hashlib.sha256(source).hexdigest(), human_context=context, ai_used=False,
                original_authoring_history_recovered=False)
    evidence=[]; inventory={}; curve_evidence=[]
    try:
        need(isinstance(context,dict) and set(context)=={"unit","family_assumption","projection","view_roles","drawing_group"},
             "context_missing","explicit family/unit/projection/group/view paths required","input_ambiguity")
        need(context["unit"]=="mm" and context["family_assumption"]==FAMILY,"unsupported_context","declared mm plate family","unsupported_input")
        need(context["projection"] in ("first_angle","third_angle"),"projection_unknown","explicit projection","input_ambiguity")
        roles=context["view_roles"]
        need(isinstance(roles,dict) and set(roles)=={"front","top","right"} and all(isinstance(v,str) for v in roles.values())
             and len(set(roles.values()))==3,"view_mapping","three distinct outline path references","input_ambiguity")
        records,inventory=normalize(source,context["drawing_group"])
        byid={r["id"]:r for r in records}
        need(all(v in byid for v in roles.values()),"view_mapping","selected path missing","input_ambiguity")
        views={}
        for role,rid in roles.items():
            r=byid[rid]
            need(r["tag"]=="path" and r["style"].get("fill")!="none" and r["style"].get("stroke")=="none"
                 and len(r["paths"])==1,"view_mapping","select the filled rectangular outline","input_ambiguity")
            views[role]=dict(box=rectangle(r["paths"][0]), circles=[], internal=[], dimensions={}, positions={}, diameters={}, raw=[])
        texts=[r for r in records if r["tag"]=="text"];arrows=[];linear=[];lines=[];curves=[];filled_curves=[]
        for r in records:
            if r["tag"]=="text" or r["id"] in roles.values():continue
            paths=r["paths"];style=r["style"];filled=style.get("fill","black")!="none";stroked=style.get("stroke","none")!="none"
            need(filled or stroked,"unsupported_svg","invisible path","unsupported_input")
            if any(s[0]=="C" for p in paths for s in p):
                need(len(paths)==1,"svg_curve","one circular subpath","unsupported_input")
                c=circle(paths[0]);c.update(id=r["id"],record=r)
                curve_evidence.append({k:v for k,v in c.items() if k!="record"})
                (curves if stroked else filled_curves).append(c)
            elif filled:
                need(stroked and len(paths)==1,"svg_profile","unmapped filled profile","unsupported_input")
                tip,direction=arrow(paths[0]);arrows.append(dict(id=r["id"],tip=tip,direction=direction))
            elif len(paths)==3 and all(len(p)==1 and p[0][0]=="L" for p in paths):
                linear.append(r)
            elif len(paths)==1 and len(paths[0])==1 and paths[0][0][0]=="L":
                lines.append(r)
            else:
                raise DrawingIssue("svg_path","unsupported_input","unclassified path topology")
        used_text=set();used_arrows=set()
        def select_text(a,b):
            u=unit(a,b); matches=[]
            for t in texts:
                if t["id"] in used_text:continue
                along=dot(relative(t["origin"],a),u);distance=line_distance(t["origin"],a,b)
                parallel=abs(dot(t["direction"],u))
                # Baseline is above the line, with bounded gap. No glyph-width/OCR inference.
                if parallel>=1-1e-5 and .15*t["height"] <= distance <= .8*t["height"] and -t["height"]<=along<=math.dist(a,b)+t["height"]:
                    matches.append(t)
            need(len(matches)==1,"dimension_label_ambiguous","one parallel nearby text baseline required","input_ambiguity")
            t=matches[0];used_text.add(t["id"]);return t
        def select_arrows(a,b,diameter=False):
            chosen=[]
            for p in (a,b):
                matches=[r for r in arrows if r["id"] not in used_arrows and close(p,r["tip"])]
                need(len(matches)==1,"dimension_arrow_missing","one arrow at each geometric endpoint","input_ambiguity")
                chosen.append(matches[0])
            u=unit(a,b);sign=-1 if diameter else (1 if dot(chosen[0]["direction"],u)>0 else -1)
            need(dot(chosen[0]["direction"],u)*sign>.9999 and dot(chosen[1]["direction"],u)*sign<-.9999,
                 "dimension_arrow_direction","arrow orientation disagrees with dimension")
            used_arrows.update(r["id"] for r in chosen)
            return [r["id"] for r in chosen]
        # Visible and hidden duplicate circles do not create additional holes.
        for c in curves:
            role_matches=[role for role,v in views.items() if
                v["box"][0]+c["radius"]<c["center"][0]<v["box"][0]+v["box"][2]-c["radius"] and
                v["box"][1]+c["radius"]<c["center"][1]<v["box"][1]+v["box"][3]-c["radius"]]
            need(role_matches==["top"],"svg_curve","circle must belong to top view","unsupported_input")
            vw=views["top"]
            if not any(close(c["center"],o["center"]) and abs(c["radius"]-o["radius"])<=EPS for o in vw["circles"]):
                vw["circles"].append(c)
                vw["raw"].append([p for s in c["record"]["paths"][0] for p in samples(s)])
        for c in filled_curves:
            need(any(close(c["center"],o["center"]) and abs(c["radius"]-o["radius"])<=EPS for o in curves),
                 "svg_curve","filled circle has no stroked counterpart","input_ambiguity")
        for c in views["top"]["circles"]:
            need(any(close(c["center"],o["center"]) and abs(c["radius"]-o["radius"])<=EPS
                     and not o["record"]["style"].get("stroke-dasharray") for o in curves),
                 "svg_curve","top circle needs a visible outline","input_ambiguity")
        for r in linear:
            seg=[p[0][1:] for p in r["paths"]];candidates=[]
            for i,(a,b) in enumerate(seg):
                u=unit(a,b)
                if min(abs(u[0]),abs(u[1]))>1e-7:continue
                others=[s for j,s in enumerate(seg) if j!=i]
                anchors=[]; intersections=[]
                axis=0 if abs(u[1])<1e-7 else 1
                for c,d in others:
                    matches=[]
                    endpoint=(c[0],a[1]) if axis==0 else (a[0],c[1])
                    if abs(dot(u,unit(c,d)))>1e-7 or not on_segment(endpoint,c,d) or not on_segment(endpoint,a,b):continue
                    for p in (c,d):
                        for role,v in views.items():
                            x,y,w,h=v["box"]
                            nodes=[(x,y),(x+w,y),(x,y+h),(x+w,y+h)]+[o["center"] for o in v["circles"]]
                            if any(close(p,n) for n in nodes):matches.append((role,p))
                    if len(matches)==1:
                        anchors.append(matches[0]);intersections.append(endpoint)
                if len(anchors)==2 and anchors[0][0]==anchors[1][0]:
                    candidates.append((*intersections,anchors[0][0],[v[1] for v in anchors]))
            need(len(candidates)==1,"dimension_target_ambiguous","extension lines must connect one view","input_ambiguity")
            a,b,role,anchors=candidates[0];arrowids=select_arrows(a,b);t=select_text(a,b)
            need(re.fullmatch(NUM,t["text"]) is not None,"unsupported_annotation",t["text"],"unsupported_input")
            value=float(t["text"]);need(1e-4<value<=1000,"invalid_dimension",t["text"])
            axis=0 if abs(a[1]-b[1])<=EPS else 1;vw=views[role];box=vw["box"]
            endpoints=sorted((a[axis],b[axis]));full=[box[axis],box[axis]+box[axis+2]]
            if close(endpoints,full):
                key={"top":("W","L"),"front":("W","T"),"right":("L","T")}[role][axis]
                need(key not in vw["dimensions"],"dimension_conflict","duplicate overall dimension")
                vw["dimensions"][key]=value;target=key
            else:
                need(role=="top","unsupported_dimension_chain","baseline top hole dimensions only","unsupported_input")
                baseline=box[axis] if axis==0 else box[axis]+box[axis+2]
                found=[i for i,c in enumerate(vw["circles"]) if close(endpoints,sorted((baseline,c["center"][axis])))]
                need(len(found)==1,"dimension_target_ambiguous","one baseline hole target","input_ambiguity")
                i=found[0];key="x" if axis==0 else "y"
                need((i,key) not in vw["positions"],"dimension_conflict","duplicate hole position")
                vw["positions"][i,key]=value;target=vw["circles"][i]["id"]+":"+key
            evidence.append(dict(view=role,dimension_line_id=r["id"],text_id=t["id"],visible_text=t["text"],
                                 value_mm=value,kind="linear",parameter=target,definition_points=anchors,
                                 arrow_ids=arrowids,text_baseline=t["origin"],text_direction=t["direction"]))
        outline={role:[] for role in views}
        for r in lines:
            a,b=r["paths"][0][0][1:];matches=[]
            for role,v in views.items():
                x,y,w,h=v["box"]
                if all(x-EPS<=p[0]<=x+w+EPS and y-EPS<=p[1]<=y+h+EPS for p in (a,b)):
                    matches.append(role)
            if len(matches)==1:
                role=matches[0];vw=views[role];x,y,w,h=vw["box"]
                border=any(all(abs(p[axis]-value)<=EPS for p in (a,b)) for axis,value in ((0,x),(0,x+w),(1,y),(1,y+h)))
                if border:
                    outline[role].append((a,b));continue
                need(role!="top" and abs(a[0]-b[0])<=EPS and abs(min(a[1],b[1])-y)<=EPS
                     and abs(max(a[1],b[1])-y-h)<=EPS and bool(r["style"].get("stroke-dasharray")),
                     "hidden_line_conflict","unexpected interior line or missing hidden line style")
                if not any(close(a,c) and close(b,d) or close(a,d) and close(b,c) for c,d in vw["internal"]):
                    vw["internal"].append((a,b));vw["raw"].append([a,b])
                continue
            need(not r["style"].get("stroke-dasharray"),"svg_path","unclassified dashed line","unsupported_input")
            # A native diameter leader crosses two opposing arrow tips on a circle.
            found=[]
            for i,c in enumerate(views["top"]["circles"]):
                tips=[r for r in arrows if r["id"] not in used_arrows and on_segment(r["tip"],a,b)
                      and abs(math.dist(r["tip"],c["center"])-c["radius"])<=EPS]
                if len(tips)==2 and close(tuple((tips[0]["tip"][j]+tips[1]["tip"][j])/2 for j in range(2)),c["center"]):
                    found.append((i,tips))
            need(len(found)==1,"diameter_target_ambiguous","leader and opposite circle arrows required","input_ambiguity")
            i,tips=found[0];arrowids=select_arrows(tips[0]["tip"],tips[1]["tip"],True);t=select_text(a,b)
            match=re.fullmatch("("+NUM+r")(?:\s+(THRU))?",t["text"])
            need(match is not None,"unsupported_annotation",t["text"],"unsupported_input")
            need(match[2]=="THRU","hole_extent_ambiguous","no explicit through indication","input_ambiguity")
            value=float(match[1]);vw=views["top"]
            need(i not in vw["diameters"],"dimension_conflict","duplicate diameter")
            vw["diameters"][i]=value
            evidence.append(dict(view="top",dimension_line_id=r["id"],text_id=t["id"],visible_text=t["text"],
                                 value_mm=value,kind="diameter",parameter=vw["circles"][i]["id"],
                                 definition_points=[p["tip"] for p in tips],arrow_ids=arrowids,
                                 text_baseline=t["origin"],text_direction=t["direction"]))
        need(len(used_text)==len(texts) and len(used_arrows)==len(arrows),"unassigned_annotation","unassigned text or arrows","input_ambiguity")
        dims={};result_views={};raw_views={};residuals=[]
        for role,v in views.items():
            x,y,w,h=v["box"];corners=[(x,y),(x+w,y),(x+w,y+h),(x,y+h)]
            for a,b in zip(corners,corners[1:]+corners[:1]):
                need(any(close(a,c) and close(b,d) or close(a,d) and close(b,c) for c,d in outline[role]),
                     "svg_profile","filled profile lacks four stroked sides","input_ambiguity")
                v["raw"].append([a,b])
            keys={"top":("W","L"),"front":("W","T"),"right":("L","T")}[role]
            need(set(v["dimensions"])==set(keys),"dimension_missing",role,"input_ambiguity")
            for k,value in v["dimensions"].items():
                need(k not in dims or abs(dims[k]-value)<=1e-6,"dimension_conflict","cross-view dimensions disagree")
                dims[k]=value
            scale=w/v["dimensions"][keys[0]];v["scale"]=scale
            need(abs(h-scale*v["dimensions"][keys[1]])<=EPS,"geometry_dimension_conflict","nonuniform view scale")
            need(.1<=scale<=10,"unsupported_scale","drawing scale outside experiment bounds","unsupported_input")
            convert=lambda p: ((p[0]-x)/scale,(y+h-p[1])/scale)
            result_views[role]={"box":v["box"],"extent_mm":[v["dimensions"][k] for k in keys],
                                "circles":[dict(center=convert(c["center"]),radius=c["radius"]/scale,id=c["id"]) for c in v["circles"]],
                                "hidden_lines":[[convert(p) for p in line] for line in v["internal"]]}
            raw_views[role]=[[convert(p) for p in line] for line in v["raw"]]
        centers={k:(v["box"][0]+v["box"][2]/2,v["box"][1]+v["box"][3]/2) for k,v in views.items()}
        f,t,r=(centers[k] for k in ("front","top","right"));sign=1 if context["projection"]=="third_angle" else -1
        need((f[1]-t[1])*sign>0 and (r[0]-f[0])*sign>0 and abs(f[0]-t[0])<=EPS and abs(f[1]-r[1])<=EPS,
             "projection_layout_conflict","view locations contradict declared projection")
        holes=[];vw=views["top"]
        need(len(vw["circles"])<=3,"unsupported_geometry","at most three holes in this study","unsupported_input")
        for i,c in enumerate(result_views["top"]["circles"]):
            need((i,"x") in vw["positions"] and (i,"y") in vw["positions"],"hole_position_missing","both baseline dimensions required","input_ambiguity")
            need(i in vw["diameters"],"hole_diameter_missing","diameter required","input_ambiguity")
            hole=dict(x=vw["positions"][i,"x"],y=vw["positions"][i,"y"],diameter=vw["diameters"][i])
            residual=max(abs(hole["x"]-c["center"][0]),abs(hole["y"]-c["center"][1]),abs(hole["diameter"]-2*c["radius"]))
            residuals.append(residual)
            need(residual<=EPS/vw["scale"],"annotation_geometry_mismatch","dimension/curve geometry mismatch")
            holes.append(hole)
        for role,key in (("front","x"),("right","y")):
            observed=sorted(line[0][0] for line in result_views[role]["hidden_lines"])
            expected=sorted(h[key]+s*h["diameter"]/2 for h in holes for s in (-1,1))
            need(len(observed)==len(expected) and all(abs(a-b)<=EPS/views[role]["scale"] for a,b in zip(observed,expected)),
                 "hidden_line_conflict","through-hole projections disagree")
        p=dict(width=dims["W"],length=dims["L"],thickness=dims["T"],holes=holes)
        feature_model(p,base["source_sha256"])  # existing plate/feature validity checks
        for i,hole in enumerate(holes):
            need(all(math.hypot(hole["x"]-o["x"],hole["y"]-o["y"])>(hole["diameter"]+o["diameter"])/2+1e-6 for o in holes[i+1:]),
                 "intersecting_holes","separated holes only","unsupported_input")
        return {**base,"status":"candidate","parameters":p,"views":result_views,"raw_drawing_polylines_mm":raw_views,
                "dimension_evidence":evidence,"inventory":inventory,"curve_evidence":curve_evidence,
                "normalization":{"coordinate_system":"sheet millimetres; model coordinates from displayed dimensions",
                  "association_tolerance_sheet_mm":EPS,"max_hole_label_geometry_residual_mm":max(residuals,default=0),
                  "circle_policy":"four quarter cubic approximation checked against controls; exact CAD radius comes from diameter label",
                  "text_policy":"XML characters with transformed baseline; no OCR or font glyph bounding-box recovery",
                  "duplicates":"coincident outlines/circles deduplicated; filled silhouettes require stroked counterparts"},
                "claim_boundary":"Conditional plate candidate from frozen FreeCAD SVG; manual group/view/family/projection, no general drawing claim."}
    except DrawingIssue as error:
        return {**base,"status":"withheld","reason_code":error.code,"failure_stage":error.stage,"detail":str(error),
                "dimension_evidence":evidence,"inventory":inventory,"curve_evidence":curve_evidence}
    except (ValueError,TypeError,KeyError,IndexError,AttributeError,ET.ParseError) as error:
        return {**base,"status":"withheld","reason_code":"invalid_input","failure_stage":"drawing_recognition","detail":str(error),
                "dimension_evidence":evidence,"inventory":inventory}


def main(argv=None):
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("drawing",type=Path);parser.add_argument("context",type=Path);parser.add_argument("--output-dir",type=Path,required=True)
    args=parser.parse_args(argv)
    if args.output_dir.exists() and (not args.output_dir.is_dir() or any(args.output_dir.iterdir())):
        parser.error("use a new or empty output directory")
    with args.drawing.open("rb") as stream:source=stream.read(500001)
    result=interpret_native_svg(source,json.loads(args.context.read_text()))
    args.output_dir.mkdir(parents=True,exist_ok=True)
    (args.output_dir/"inference.json").write_bytes(json_bytes(result))
    if result["status"]=="candidate":
        (args.output_dir/"candidate.py").write_text(candidate_code(result["parameters"],result["source_sha256"]))
        (args.output_dir/"model.json").write_bytes(json_bytes(asdict(feature_model(result["parameters"],result["source_sha256"]))))
    print(json.dumps({"status":result["status"],"reason":result.get("reason_code")}))


if __name__=="__main__":main()
