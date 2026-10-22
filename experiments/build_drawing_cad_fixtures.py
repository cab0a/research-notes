"""Author synthetic inputs and independent evaluation truth; never called by inference."""
from pathlib import Path
import hashlib
import json
import math
import xml.etree.ElementTree as ET

from research_notes.drawing_to_cad import FAMILY, json_bytes

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures/drawing-to-cad"


def truth_shape(parameters):
    """Independent direct OCCT recipe (no recovered feature builder or SVG reader)."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
    p = parameters
    shape = BRepPrimAPI_MakeBox(p["width"], p["length"], p["thickness"]).Shape()
    for h in p["holes"]:
        cutter = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(h["x"], h["y"], -1), gp_Dir(0,0,1)), h["diameter"]/2, p["thickness"]+2).Shape()
        operation = BRepAlgoAPI_Cut(shape, cutter)
        operation.Build()
        if not operation.IsDone():
            raise RuntimeError("independent truth authoring failed")
        shape = operation.Shape()
    return shape


def drawing(parameters, projection, scale=4):
    p = parameters
    root = ET.Element("svg", xmlns="http://www.w3.org/2000/svg", width="1100", height="780", viewBox="0 0 1100 780")
    locations = {"third_angle": {"front": (120,340), "top": (120,100), "right": (580,340)},
                 "first_angle": {"front": (580,100), "top": (580,400), "right": (120,100)}}[projection]
    roles = {"front": "panel_a", "top": "panel_b", "right": "panel_c"}
    for name in ("front", "top", "right"):
        group = ET.SubElement(root, "g", id=roles[name])
        x, y = locations[name]
        u, v = {"front": (p["width"], p["thickness"]), "top": (p["width"], p["length"]), "right": (p["length"], p["thickness"])}[name]
        ET.SubElement(group, "rect", id=name+"_outline", x=str(x), y=str(y), width=str(u*scale), height=str(v*scale), fill="none", stroke="black")
        def text(identifier, label, tx, ty):
            e = ET.SubElement(group, "text", id=identifier, x=str(tx), y=str(ty), fill="black", **{"font-size":"13"})
            e.text = label
        text(name+"_label", name.upper()+" (mm)", x, y-18)
        keys = {"front": ("W", "T"), "top": ("W", "L"), "right": ("L", "T")}[name]
        for index, (key, value) in enumerate(zip(keys, (u, v))):
            text(name+"_dim_"+key, f"{key}={value:g}", x, y+v*scale+22+18*index)
        for index, h in enumerate(p["holes"]):
            if name == "top":
                ET.SubElement(group, "circle", id=f"top_circle_{index}", cx=str(x+h["x"]*scale), cy=str(y+(v-h["y"])*scale),
                              r=str(h["diameter"]*scale/2), fill="none", stroke="black")
                # Reverse row order deliberately: inference cannot rely on row/circle order.
                row = p["holes"][-1-index]
                text(f"hole_row_{index}", f'X={row["x"]:g} Y={row["y"]:g} DIA={row["diameter"]:g} THRU', x, y+v*scale+68+18*index)
            else:
                coordinate = h["x"] if name == "front" else h["y"]
                for side in (-1,1):
                    px = x+(coordinate+side*h["diameter"]/2)*scale
                    ET.SubElement(group, "line", id=f"{name}_hidden_{index}_{side}", x1=str(px), x2=str(px), y1=str(y), y2=str(y+v*scale),
                                  stroke="black", **{"stroke-dasharray":"4 3"})
    context = {"projection": projection, "unit": "mm", "family_assumption": FAMILY, "view_roles": roles}
    return root, context


def build():
    from research_notes.step_writer_modes import prepare_step_write
    for folder in ("inputs", "evaluation"):
        (FIXTURES / folder).mkdir(parents=True, exist_ok=True)
    plate = {"width": 40., "length": 30., "thickness": 8., "holes": []}
    one = {**plate, "holes": [{"x":12., "y":10., "diameter":6.}]}
    two = {**plate, "holes": [{"x":10., "y":8., "diameter":4.}, {"x":28., "y":21., "diameter":6.}]}
    specs = [("plain_third",plate,"third_angle",4,None), ("plain_first",plate,"first_angle",4,None),
             ("one_third",one,"third_angle",4,None), ("one_first",one,"first_angle",4,None),
             ("two_third",two,"third_angle",4,None), ("two_scaled",two,"third_angle",2,None),
             ("missing_thickness",one,"third_angle",4,"dimension_missing"),
             ("conflicting_width",one,"third_angle",4,"dimension_conflict"),
             ("wrong_projection",one,"third_angle",4,"projection_layout_conflict"),
             ("swapped_views",one,"third_angle",4,"dimension_missing"),
             ("ambiguous_extent",one,"third_angle",4,"hole_extent_ambiguous"),
             ("missing_hidden_line",one,"third_angle",4,"hidden_line_conflict"),
             ("unsupported_profile",one,"third_angle",4,"unsupported_svg")]
    rows, truth = [], {}
    for identifier, params, projection, scale, expected in specs:
        root, context = drawing(params, projection, scale)
        elements = {e.get("id"): e for e in root.iter()}
        if identifier == "missing_thickness":
            for group in root:
                for e in list(group):
                    if e.get("id", "").endswith("_dim_T"):
                        group.remove(e)
        elif identifier == "conflicting_width":
            e = ET.SubElement(root[0], "text", id="contradictory_dim", x="300", y="410", fill="black")
            e.text = "W=41"
        elif identifier == "wrong_projection":
            context["projection"] = "first_angle"
        elif identifier == "swapped_views":
            context["view_roles"]["front"], context["view_roles"]["right"] = context["view_roles"]["right"], context["view_roles"]["front"]
        elif identifier == "ambiguous_extent":
            for e in root.iter():
                if e.get("id", "").startswith("hole_row"):
                    e.text = e.text.replace(" THRU", "")
            for group in root:
                for e in list(group):
                    if "hidden" in e.get("id", ""):
                        group.remove(e)
        elif identifier == "missing_hidden_line":
            root[0].remove(elements["front_hidden_0_-1"])
        elif identifier == "unsupported_profile":
            ET.SubElement(root[1], "path", id="step_profile", d="M 120 100 L 140 100 L 140 110 Z", stroke="black", fill="none")
        payload = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        svg = FIXTURES / "inputs" / (identifier+".svg")
        ctx = svg.with_suffix(".context.json")
        svg.write_bytes(payload+b"\n")
        ctx.write_bytes(json_bytes(context))
        rows.append({"id":identifier, "svg":"inputs/"+svg.name, "context":"inputs/"+ctx.name,
            "svg_sha256":hashlib.sha256(svg.read_bytes()).hexdigest(), "context_sha256":hashlib.sha256(ctx.read_bytes()).hexdigest(),
            "family_id": "plate-"+str(len(params["holes"]))+"-hole", "expected_status":"withheld" if expected else "candidate",
            "expected_reason": expected, "truth_key": identifier if not expected else None})
        if not expected:
            data, _ = prepare_step_write(source=None, mode="reconstruct", shape=truth_shape(params))
            path = FIXTURES / "evaluation" / (identifier+".step")
            path.write_bytes(data)
            volume = params["width"]*params["length"]*params["thickness"] - sum(math.pi*(h["diameter"]/2)**2*params["thickness"] for h in params["holes"])
            area = 2*(params["width"]*params["length"]+params["width"]*params["thickness"]+params["length"]*params["thickness"])
            area += sum(-2*math.pi*(h["diameter"]/2)**2+math.pi*h["diameter"]*params["thickness"] for h in params["holes"])
            truth[identifier] = {"parameters":params,"analytic_volume":volume,"analytic_area":area,
                "step":path.name,"sha256":hashlib.sha256(data).hexdigest()}
    (FIXTURES / "manifest.json").write_bytes(json_bytes({"study_schema": "1.0.0", "cases": rows,
        "scope":"Authored development controls, not blinded real-drawing performance; variants share families."}))
    (FIXTURES / "evaluation/truth.json").write_bytes(json_bytes(truth))
    print(json.dumps({"inputs":len(rows),"positive":len(truth),"withheld":len(rows)-len(truth)}))


if __name__ == "__main__":
    build()
