"""Bounded geometric dimension association for authored orthographic SVGs.

IDs and drawing order are evidence references only. Interpretation has no file
I/O, truth recipe, scale sidecar, OCR, AI model or CAD-kernel dependency.
"""
from __future__ import annotations

import copy
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from .drawing_to_cad import (
    DrawingIssue, FAMILY, candidate_code, feature_model, interpret_svg,
    json_bytes, require,
)

EPS = 1e-5  # SVG user units, not a manufacturing tolerance.
NUMBER = re.compile(r"[0-9]+(?:\.[0-9]+)?")
DIAMETER = re.compile(r"[⌀Øφ]\s*([0-9]+(?:\.[0-9]+)?)(?:\s+(THRU|貫通))?")


def tag(element):
    return element.tag.split("}")[-1]


def number(element, key):
    value = float(element.attrib[key])
    require(math.isfinite(value) and abs(value) <= 20000,
            "invalid_svg_number", "drawing_recognition", key)
    return value


def point(element, suffix=""):
    return (number(element, "x" + suffix), number(element, "y" + suffix))


def distance(a, b):
    return math.dist(a, b)


def arrow_geometry(element):
    raw = element.get("points", "").replace(",", " ").split()
    require(len(raw) == 6, "unsupported_arrow", "unsupported_input", "triangular arrow required")
    values = list(map(float, raw))
    require(all(math.isfinite(v) and abs(v) <= 20000 for v in values),
            "invalid_svg_number", "drawing_recognition", "arrow points")
    points = list(zip(values[::2], values[1::2]))
    # The short edge is the base, independently of polygon vertex order.
    candidates = []
    for i in range(3):
        tip, a, b = points[i], points[(i + 1) % 3], points[(i + 2) % 3]
        sides = distance(tip, a), distance(tip, b)
        if abs(sides[0] - sides[1]) <= EPS and 0 < distance(a, b) < min(sides):
            candidates.append((tip, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)))
    require(len(candidates) == 1, "unsupported_arrow", "unsupported_input", "narrow isosceles arrow required")
    tip, base = candidates[0]
    length = distance(tip, base)
    require(length > EPS, "unsupported_arrow", "drawing_recognition", "degenerate arrow")
    return {"id": element.get("id"), "tip": tip,
            "direction": ((base[0] - tip[0]) / length, (base[1] - tip[1]) / length)}


def label_for_line(a, b, texts, *, leader=False):
    matches = []
    for text in texts:
        p = point(text)
        size = number(text, "font-size") if "font-size" in text.attrib else 11.
        require(6 <= size <= 20, "unsupported_text_size", "unsupported_input", "font-size 6..20 required")
        if leader:
            near = distance(p, b) <= 2 * size
        else:
            middle = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            near = abs(p[0] - middle[0]) <= 1.5 * size and abs(p[1] - middle[1]) <= 1.5 * size
        if near:
            matches.append(text)
    require(len(matches) == 1, "dimension_text_missing" if not matches else "dimension_text_ambiguous",
            "input_ambiguity", "dimension/leader must have exactly one nearby numeric label")
    return matches[0]


def witness_for(endpoint, axis, lines, anchors):
    """Find a perpendicular extension joining the endpoint to actual geometry.

    A bounded 0..6 SVG-unit gap at the geometric anchor is allowed. Extensions
    must reach the dimension line. This does not support slanted or broken lines.
    """
    other = 1 - axis
    choices = []
    for line in lines:
        a, b = point(line, "1"), point(line, "2")
        if abs(a[axis] - b[axis]) > EPS or abs(a[axis] - endpoint[axis]) > EPS:
            continue
        lo, hi = sorted((a[other], b[other]))
        if not lo - EPS <= endpoint[other] <= hi + EPS:
            continue
        for anchor in anchors:
            if abs(anchor[axis] - endpoint[axis]) > EPS:
                continue
            closest = min((a, b), key=lambda p: distance(p, anchor))
            farthest = max((a, b), key=lambda p: distance(p, anchor))
            if distance(closest, anchor) <= 6 + EPS and (
                (closest[other] - anchor[other]) * (endpoint[other] - anchor[other]) >= -EPS
                and (farthest[other] - anchor[other]) * (endpoint[other] - anchor[other]) > 0
            ):
                choices.append((line, anchor))
    require(bool(choices), "extension_missing", "drawing_recognition", "dimension endpoint has no geometric witness")
    # Shared collinear extensions can originate at different points on the same
    # feature edge. Their measured-axis coordinate is identical. Feature identity
    # is checked separately when the dimension is assigned to a circle/outline.
    line, anchor = min(choices, key=lambda item: distance(item[1], endpoint))
    return line.get("id"), anchor


def _view(group, name):
    children = list(group)
    require(not any(tag(e) == "g" for e in children), "unsupported_svg", "unsupported_input", "flat view groups required")
    rectangles = [e for e in children if tag(e) == "rect"]
    require(len(rectangles) == 1, "unsupported_profile", "unsupported_input", "one rectangular outline per view")
    rect = rectangles[0]
    box = [number(rect, k) for k in ("x", "y", "width", "height")]
    x, y, width, height = box
    require(width > 0 and height > 0, "unsupported_profile", "drawing_recognition", "positive outline required")
    circles = [e for e in children if tag(e) == "circle"]
    require(name == "top" or not circles, "unsupported_geometry", "unsupported_input", "circles only in top view")
    centers = [(number(e, "cx"), number(e, "cy")) for e in circles]
    anchors = [(x, y), (x + width, y), (x, y + height), (x + width, y + height), *centers]
    for cx, cy in centers:
        anchors.extend(((x, cy), (x + width, cy), (cx, y), (cx, y + height)))
    lines = [e for e in children if tag(e) == "line" and not e.get("stroke-dasharray")]
    arrows = [arrow_geometry(e) for e in children if tag(e) == "polygon"]
    numeric = [e for e in children if tag(e) == "text" and re.search(r"[0-9]", "".join(e.itertext()))]
    used_texts, used_arrows, used_lines = set(), set(), set()
    dimensions, evidence, positions, diameters = {}, [], {}, {}
    for line in lines:
        a, b = point(line, "1"), point(line, "2")
        require(distance(a, b) > EPS, "degenerate_line", "drawing_recognition", "zero length line")
        at_a = [i for i, arrow in enumerate(arrows) if distance(arrow["tip"], a) <= EPS]
        at_b = [i for i, arrow in enumerate(arrows) if distance(arrow["tip"], b) <= EPS]
        if not at_a and not at_b:
            continue
        require(len(at_a) <= 1 and len(at_b) <= 1, "arrow_ambiguous", "input_ambiguity", "coincident arrows")
        if not at_a:
            a, b, at_a, at_b = b, a, at_b, at_a
        leader = not at_b
        arrow_ids = at_a + at_b
        require(not (set(arrow_ids) & used_arrows), "arrow_ambiguous", "input_ambiguity", "one arrow belongs to multiple lines")
        used_arrows.update(arrow_ids)
        unit = ((b[0] - a[0]) / distance(a, b), (b[1] - a[1]) / distance(a, b))
        for index, sign in ((at_a[0], 1), *(([(at_b[0], -1)]) if at_b else [])):
            require(sum(arrows[index]["direction"][i] * unit[i] * sign for i in (0, 1)) > .99,
                    "unsupported_arrow_direction", "unsupported_input", "only inward arrows implemented")
        text = label_for_line(a, b, numeric, leader=leader)
        require(id(text) not in used_texts, "dimension_text_ambiguous", "input_ambiguity", "label reused")
        used_texts.add(id(text)); used_lines.add(id(line))
        label = "".join(text.itertext()).strip()
        item = {"view": name, "dimension_line_id": line.get("id"), "text_id": text.get("id"),
                "visible_text": label, "line_points_svg": [a, b],
                "arrow_ids": [arrows[i]["id"] for i in arrow_ids]}
        if leader:
            match = DIAMETER.fullmatch(label)
            require(match is not None, "unsupported_annotation", "unsupported_input", label)
            require(match[2] is not None, "hole_extent_ambiguous", "input_ambiguity", "no explicit through indication")
            targets = [i for i, (circle, center) in enumerate(zip(circles, centers)) if abs(distance(a, center) - number(circle, "r")) <= EPS]
            require(len(targets) == 1, "leader_target_missing" if not targets else "leader_target_ambiguous",
                    "input_ambiguity", "diameter leader must touch exactly one circle")
            index = targets[0]
            require(index not in diameters, "dimension_conflict", "drawing_conflict", "duplicate diameter")
            diameters[index] = float(match[1])
            item.update(kind="hole_diameter", circle_id=circles[index].get("id"), value_mm=float(match[1]))
        else:
            require(NUMBER.fullmatch(label) is not None, "unsupported_annotation", "unsupported_input", label)
            value = float(label)
            require(1e-4 < value <= 1000, "invalid_dimension", "drawing_recognition", label)
            axis = 0 if abs(a[1] - b[1]) <= EPS else 1 if abs(a[0] - b[0]) <= EPS else None
            require(axis is not None, "unsupported_dimension_direction", "unsupported_input", "axis-aligned dimensions required")
            witnesses = [witness_for(p, axis, lines, anchors) for p in (a, b)]
            used_lines.update(id(e) for e in lines if e.get("id") in {w[0] for w in witnesses})
            item.update(extension_ids=[w[0] for w in witnesses], anchor_points_svg=[w[1] for w in witnesses], value_mm=value)
            endpoints = sorted((a[axis], b[axis]))
            full = sorted((box[axis], box[axis] + box[axis + 2]))
            if max(abs(v - w) for v, w in zip(endpoints, full)) <= EPS:
                key = {"front": ("W", "T"), "top": ("W", "L"), "right": ("L", "T")}[name][axis]
                require(key not in dimensions, "dimension_conflict", "drawing_conflict", "duplicate overall dimension")
                dimensions[key] = value
                item.update(kind="overall", parameter=key)
            else:
                require(name == "top", "unsupported_dimension_chain", "unsupported_input", "only top baseline hole positions implemented")
                origin = x if axis == 0 else y + height
                targets = [i for i, center in enumerate(centers) if
                           max(abs(v - w) for v, w in zip(endpoints, sorted((origin, center[axis])))) <= EPS]
                require(len(targets) == 1, "unsupported_dimension_chain" if not targets else "dimension_target_ambiguous",
                        "input_ambiguity", "baseline dimension does not identify one hole")
                index, key = targets[0], "x" if axis == 0 else "y"
                require((index, key) not in positions, "dimension_conflict", "drawing_conflict", "duplicate hole position")
                positions[index, key] = value
                item.update(kind="hole_position", parameter=key, circle_id=circles[index].get("id"))
        evidence.append(item)
    require(len(used_texts) == len(numeric), "unassociated_annotation", "input_ambiguity", "unassociated numeric text")
    require(len(used_arrows) == len(arrows), "arrow_unassociated", "drawing_recognition", "unassociated arrow")
    require(all(id(line) in used_lines for line in lines), "unsupported_geometry", "unsupported_input", "unclassified solid line")
    required = {"front": {"W", "T"}, "top": {"W", "L"}, "right": {"L", "T"}}[name]
    require(set(dimensions) == required, "dimension_missing", "input_ambiguity", name + " overall dimensions missing")
    holes = []
    for index in range(len(circles)):
        require((index, "x") in positions and (index, "y") in positions,
                "hole_position_missing", "input_ambiguity", "each hole needs both baseline position dimensions")
        require(index in diameters, "hole_diameter_missing", "input_ambiguity", "each circle needs a diameter leader")
        holes.append({"x": positions[index, "x"], "y": positions[index, "y"], "diameter": diameters[index]})
    # Only geometry and inferred values enter the established CAD validation path.
    canonical = ET.Element("g", id=group.get("id"))
    for element in children:
        if tag(element) in ("rect", "circle") or tag(element) == "line" and element.get("stroke-dasharray"):
            canonical.append(copy.deepcopy(element))
    for key, value in sorted(dimensions.items()):
        ET.SubElement(canonical, "text").text = f"{key}={value:g}"
    for hole in holes:
        ET.SubElement(canonical, "text").text = f'X={hole["x"]:g} Y={hole["y"]:g} DIA={hole["diameter"]:g} THRU'
    return canonical, evidence


def interpret_dimension_svg(source: bytes, context: dict):
    base = {"schema_version": "1.0.0", "source_sha256": hashlib.sha256(source).hexdigest(),
            "human_context": context, "method": "C_vector_dimension_line_association", "ai_used": False,
            "original_authoring_history_recovered": False}
    evidence = []
    try:
        require(0 < len(source) <= 200000 and b"<!DOCTYPE" not in source.upper() and b"<!ENTITY" not in source.upper(),
                "input_format", "drawing_recognition", "bounded SVG without entities required")
        require(isinstance(context, dict) and set(context) == {"projection", "unit", "family_assumption", "view_roles"},
                "context_missing", "input_ambiguity", "explicit view/family/unit/projection context required")
        require(context["family_assumption"] == FAMILY and context["unit"] == "mm",
                "unsupported_context", "unsupported_input", "declared millimetre plate grammar only")
        roles = context["view_roles"]
        require(isinstance(roles, dict) and set(roles) == {"front", "top", "right"} and
                all(isinstance(v, str) for v in roles.values()) and len(set(roles.values())) == 3,
                "view_mapping", "input_ambiguity", "three distinct human-selected groups required")
        root = ET.fromstring(source)
        elements = list(root.iter())
        require(tag(root) == "svg" and len(elements) <= 512, "input_format", "drawing_recognition", "SVG size/root")
        ids = [e.get("id") for e in elements if e.get("id")]
        require(len(ids) == len(set(ids)) and all(e.get("id") for e in elements if tag(e) != "svg"),
                "element_id", "drawing_recognition", "unique evidence IDs required (names have no semantics)")
        for e in elements:
            require(tag(e) in {"svg", "g", "rect", "circle", "line", "polygon", "text"} and
                    not any(k.split("}")[-1] in {"transform", "style", "display", "visibility", "opacity", "href"}
                            or k.startswith("data-") for k in e.attrib),
                    "unsupported_svg", "unsupported_input", "flat visible primitive grammar only")
        canonical = ET.Element("svg")
        groups = {e.get("id"): e for e in root if tag(e) == "g"}
        require(set(groups) == set(roles.values()) and len(root) == 3,
                "view_mapping", "drawing_recognition", "only the three selected view groups allowed")
        for name in ("front", "top", "right"):
            group, found = _view(groups[roles[name]], name)
            canonical.append(group)
            evidence.extend(found)
        validated = interpret_svg(ET.tostring(canonical), context)
        if validated["status"] == "withheld":
            return {**validated, **base, "dimension_evidence": evidence}
        return {**validated, **base, "dimension_evidence": evidence,
                "claim_boundary": "Authored vector dimension subset with explicit human priors; not OCR, general drafting notation or unique original history."}
    except DrawingIssue as error:
        return {**base, "status": "withheld", "failure_stage": error.stage,
                "reason_code": error.code, "detail": str(error), "dimension_evidence": evidence}
    except (ValueError, TypeError, KeyError, ET.ParseError) as error:
        return {**base, "status": "withheld", "failure_stage": "drawing_recognition",
                "reason_code": "invalid_input", "detail": str(error), "dimension_evidence": evidence}


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("svg", type=Path)
    parser.add_argument("context", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output_dir.exists() and (not args.output_dir.is_dir() or any(args.output_dir.iterdir())):
        parser.error("output directory must be new or empty")
    with args.svg.open("rb") as stream:
        source = stream.read(200001)
    report = interpret_dimension_svg(source, json.loads(args.context.read_text(encoding="utf-8")))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "inference.json").write_bytes(json_bytes(report))
    if report["status"] == "candidate":
        (args.output_dir / "candidate.py").write_text(candidate_code(report["parameters"], report["source_sha256"]), encoding="utf-8")
        (args.output_dir / "model.json").write_bytes(json_bytes(asdict(feature_model(report["parameters"], report["source_sha256"])) ))
    print(json.dumps({"status": report["status"], "reason_code": report.get("reason_code")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
