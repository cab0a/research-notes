"""Author ordinary-looking dimension graphics and evaluation-only truth."""
from __future__ import annotations

import copy
import hashlib
import math
from pathlib import Path
import random
import xml.etree.ElementTree as ET

from experiments.build_drawing_cad_fixtures import truth_shape
from research_notes.drawing_to_cad import FAMILY, json_bytes

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures/drawing-dimensions"


def drawing(parameters, projection="third_angle", scale=4):
    root = ET.Element("svg", xmlns="http://www.w3.org/2000/svg", width="1400", height="950", viewBox="0 0 1400 950")
    positions = {"third_angle": {"front": (280, 560), "top": (280, 220), "right": (880, 560)},
                 "first_angle": {"front": (880, 220), "top": (880, 560), "right": (280, 220)}}[projection]
    refs, roles = {}, {}
    for view_index, name in enumerate(("front", "top", "right")):
        group = ET.SubElement(root, "g", id=f"panel_{view_index}")
        roles[name] = group.get("id")
        def element(kind, **attrs):
            return ET.SubElement(group, kind, id=f"p{view_index}_{len(group):03d}", **{k: str(v) for k, v in attrs.items()})
        def line(a, b):
            return element("line", x1=a[0], y1=a[1], x2=b[0], y2=b[1], stroke="#344650", **{"stroke-width": ".8"})
        def arrow(tip, toward):
            delta = [(toward[i] - tip[i]) / math.dist(tip, toward) for i in (0, 1)]
            base = [tip[i] + 5 * delta[i] for i in (0, 1)]
            points = [tip, (base[0] - 1.7 * delta[1], base[1] + 1.7 * delta[0]),
                      (base[0] + 1.7 * delta[1], base[1] - 1.7 * delta[0])]
            return element("polygon", points=" ".join(f"{a},{b}" for a, b in points), fill="#344650")
        def text(value, x, y):
            e = element("text", x=x, y=y, fill="#182b37", **{"font-size": "11", "font-family": "sans-serif"})
            e.text = value
            return e
        def dimension(first, second, offset, value, axis):
            a, b = list(first), list(second)
            a[1-axis] = b[1-axis] = offset
            members = [line(a, b), arrow(a, b), arrow(b, a)]
            extensions = []
            for anchor, endpoint in ((first, a), (second, b)):
                sign = 1 if offset > anchor[1-axis] else -1
                start, end = list(anchor), list(endpoint)
                start[1-axis] += 2 * sign
                end[1-axis] += 4 * sign
                extensions.append(line(start, end))
            label = text(f"{value:g}", (a[0]+b[0])/2 if axis == 0 else offset-13,
                         offset-7 if axis == 0 else (a[1]+b[1])/2)
            members += extensions + [label]
            return {"members": members, "label": label, "extensions": extensions, "line": members[0]}
        x, y = positions[name]
        u, v = {"front": (parameters["width"], parameters["thickness"]),
                "top": (parameters["width"], parameters["length"]),
                "right": (parameters["length"], parameters["thickness"])}[name]
        w, h = u*scale, v*scale
        element("rect", x=x, y=y, width=w, height=h, stroke="#142d3a", fill="none", **{"stroke-width": "1.8"})
        text(name.upper() + " / mm", x, y-80)
        if name == "top":
            horizontal = dimension((x, y), (x+w, y), y-45, u, 0)
            vertical = dimension((x, y), (x, y+h), x-48, v, 1)
        else:
            horizontal = dimension((x, y+h), (x+w, y+h), y+h+48, u, 0)
            vertical = dimension((x+w, y), (x+w, y+h), x+w+52, v, 1)
        refs[name+"_u"], refs[name+"_v"] = (group, horizontal), (group, vertical)
        for index, hole in enumerate(parameters["holes"]):
            if name == "top":
                cx, cy, radius = x+hole["x"]*scale, y+h-hole["y"]*scale, hole["diameter"]*scale/2
                circle = element("circle", cx=cx, cy=cy, r=radius, stroke="#142d3a", fill="none", **{"stroke-width": "1.8"})
                refs[f"circle_{index}"] = group, circle
                dx = dimension((x, cy), (cx, cy), y+h+48+42*index, hole["x"], 0)
                dy = dimension((cx, y+h), (cx, cy), x-95-42*index, hole["y"], 1)
                refs[f"hole_{index}_x"], refs[f"hole_{index}_y"] = (group, dx), (group, dy)
                tip = (cx+radius/math.sqrt(2), cy-radius/math.sqrt(2))
                end = (x+w+75+80*index, y-50-45*index)
                leader = line(tip, end)
                head = arrow(tip, end)
                label = text(f'⌀{hole["diameter"]:g} THRU', end[0]+7, end[1]-4)
                refs[f"hole_{index}_d"] = group, {"members": [leader, head, label], "line": leader, "arrow": head, "label": label}
            else:
                position = hole["x"] if name == "front" else hole["y"]
                for sign in (-1, 1):
                    px = x+(position+sign*hole["diameter"]/2)*scale
                    e = line((px, y), (px, y+h))
                    e.set("stroke-dasharray", "5 3")
    return root, {"projection": projection, "unit": "mm", "family_assumption": FAMILY, "view_roles": roles}, refs


def build():
    from research_notes.step_writer_modes import prepare_step_write
    for folder in ("inputs", "evaluation"):
        (FIXTURES / folder).mkdir(parents=True, exist_ok=True)
    plain = {"width": 40., "length": 30., "thickness": 8., "holes": []}
    one = {**plain, "holes": [{"x": 12., "y": 10., "diameter": 6.}]}
    two = {**plain, "holes": [{"x": 10., "y": 8., "diameter": 4.}, {"x": 28., "y": 21., "diameter": 6.}]}
    variant = {"width": 52.5, "length": 37.25, "thickness": 6.5,
               "holes": [{"x": 17.5, "y": 13.25, "diameter": 5.5}]}
    positive = [("plain_third", plain, "third_angle", 4), ("one_third", one, "third_angle", 4),
                ("one_first", one, "first_angle", 4), ("two_third", two, "third_angle", 4),
                ("one_scaled", one, "third_angle", 2), ("one_anonymous", one, "third_angle", 4),
                ("decimal_plate", variant, "third_angle", 3), ("two_reordered", two, "third_angle", 4)]
    negatives = ["missing_position", "missing_thickness", "conflicting_width", "ambiguous_label", "missing_extension",
                 "wrong_projection", "diameter_conflict", "ambiguous_extent", "unsupported_tolerance", "chain_dimension",
                 "leader_misses_hole", "unsupported_radius"]
    specs = [(name, p, projection, scale, False) for name, p, projection, scale in positive]
    specs += [(name, two if name == "chain_dimension" else one, "third_angle", 4, True) for name in negatives]
    manifest, truth = [], {}
    reasons = {"missing_position": "hole_position_missing", "missing_thickness": "dimension_missing",
               "conflicting_width": "dimension_conflict", "ambiguous_label": "dimension_text_ambiguous",
               "missing_extension": "extension_missing", "wrong_projection": "projection_layout_conflict",
               "diameter_conflict": "annotation_geometry_mismatch", "ambiguous_extent": "hole_extent_ambiguous",
               "unsupported_tolerance": "unsupported_annotation", "chain_dimension": "unsupported_dimension_chain",
               "leader_misses_hole": "leader_target_missing", "unsupported_radius": "unsupported_annotation"}
    for name, params, projection, scale, negative in specs:
        root, context, refs = drawing(copy.deepcopy(params), projection, scale)
        def remove_dimension(key):
            group, reference = refs[key]
            for e in reference["members"]:
                group.remove(e)
        if name == "missing_position":
            remove_dimension("hole_0_x")
        elif name == "missing_thickness":
            remove_dimension("front_v"); remove_dimension("right_v")
        elif name == "conflicting_width":
            refs["top_u"][1]["label"].text = "41"
        elif name == "ambiguous_label":
            group, reference = refs["front_u"]
            duplicate = copy.deepcopy(reference["label"])
            duplicate.set("id", "another_label")
            duplicate.set("y", str(float(duplicate.get("y"))-5))
            group.append(duplicate)
        elif name == "missing_extension":
            group, reference = refs["front_u"]
            group.remove(reference["extensions"][1])
        elif name == "wrong_projection":
            context["projection"] = "first_angle"
        elif name == "diameter_conflict":
            refs["hole_0_d"][1]["label"].text = "⌀7 THRU"
        elif name == "ambiguous_extent":
            refs["hole_0_d"][1]["label"].text = "⌀6"
        elif name == "unsupported_tolerance":
            refs["front_u"][1]["label"].text = "40 ±0.1"
        elif name == "chain_dimension":
            # Replace the second X datum by the first hole center; keep the
            # visible dimension consistent with that chain, outside our subset.
            group, reference = refs["hole_1_x"]
            target_x = 280+params["holes"][0]["x"]*scale
            old_x = float(reference["line"].get("x1"))
            delta = target_x-old_x
            reference["line"].set("x1", str(target_x))
            for e in reference["members"]:
                if e.tag == "polygon" and e is reference["members"][1]:
                    pairs = [tuple(map(float, p.split(","))) for p in e.get("points").split()]
                    e.set("points", " ".join(f"{a+delta},{b}" for a,b in pairs))
            extension = reference["extensions"][0]
            extension.set("x1", str(target_x)); extension.set("x2", str(target_x))
            extension.set("y1", str(220+params["length"]*scale-params["holes"][0]["y"]*scale+2))
            reference["label"].text = "18"
            reference["label"].set("x", str((target_x+float(reference["line"].get("x2")))/2))
        elif name == "leader_misses_hole":
            _, reference = refs["hole_0_d"]
            reference["line"].set("x1", str(float(reference["line"].get("x1"))+2))
            # Move the entire arrow so the mismatch is at the circle, not at
            # arrow/line association; retain the original leader direction.
            a = (float(reference["line"].get("x1")), float(reference["line"].get("y1")))
            b = (float(reference["line"].get("x2")), float(reference["line"].get("y2")))
            u = [(b[i]-a[i])/math.dist(a,b) for i in (0,1)]
            base = [a[i]+5*u[i] for i in (0,1)]
            reference["arrow"].set("points", f"{a[0]},{a[1]} {base[0]-1.7*u[1]},{base[1]+1.7*u[0]} {base[0]+1.7*u[1]},{base[1]-1.7*u[0]}")
        elif name == "unsupported_radius":
            refs["hole_0_d"][1]["label"].text = "R3"
        if name in ("one_anonymous", "two_reordered"):
            rng = random.Random(742)
            for e in root.iter():
                if e.get("id") and e.tag != "g":
                    e.set("id", f"n{rng.getrandbits(80):020x}")
                if e.tag == "polygon":
                    pts = e.get("points").split(); rng.shuffle(pts); e.set("points", " ".join(pts))
            for group in root:
                children = list(group); rng.shuffle(children); group[:] = children
        payload = ET.tostring(root, encoding="utf-8", xml_declaration=True)+b"\n"
        svg = FIXTURES / "inputs" / f"{name}.svg"
        ctx = svg.with_suffix(".context.json")
        svg.write_bytes(payload); ctx.write_bytes(json_bytes(context))
        manifest.append({"id": name, "svg": "inputs/"+svg.name, "context": "inputs/"+ctx.name,
                         "svg_sha256": hashlib.sha256(payload).hexdigest(), "context_sha256": hashlib.sha256(ctx.read_bytes()).hexdigest(),
                         "family_id": f'plate-{len(params["holes"])}-hole', "expected_status": "withheld" if negative else "candidate",
                         "expected_reason": reasons.get(name), "truth_key": None if negative else name})
        if not negative:
            data, _ = prepare_step_write(source=None, mode="reconstruct", shape=truth_shape(params))
            path = FIXTURES / "evaluation" / f"{name}.step"
            path.write_bytes(data)
            radii = [h["diameter"]/2 for h in params["holes"]]
            w,l,t = (params[k] for k in ("width", "length", "thickness"))
            truth[name] = {"parameters": params, "analytic_volume": w*l*t-sum(math.pi*r*r*t for r in radii),
                           "analytic_area": 2*(w*l+w*t+l*t)+sum(-2*math.pi*r*r+2*math.pi*r*t for r in radii),
                           "step": path.name, "sha256": hashlib.sha256(data).hexdigest()}
    (FIXTURES / "manifest.json").write_bytes(json_bytes({"schema_version": "1.0.0", "cases": manifest,
        "scope": "Authored development controls, ordinary-looking bounded dimension graphics; not standards conformance or held-out real-drawing accuracy."}))
    (FIXTURES / "evaluation/truth.json").write_bytes(json_bytes(truth))
    print({"inputs": len(manifest), "positive": len(truth), "negative": len(manifest)-len(truth)})


if __name__ == "__main__":
    build()
