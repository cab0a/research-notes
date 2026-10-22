"""Restricted SVG graphics normalization for the frozen TechDraw experiment.

Coordinates are sheet millimetres. This is not a general SVG renderer.
"""
from __future__ import annotations
import math
import re
import xml.etree.ElementTree as ET

from .drawing_to_cad import require

NUMBER = r"[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?"
IDENTITY = (1., 0., 0., 1., 0., 0.)
EPS = .002  # sheet mm: exported decimal rounding/association, not part tolerance
KAPPA = 4*(math.sqrt(2)-1)/3


def check(condition, code, detail):
    require(condition, code, "unsupported_input", detail)


def numbers(value):
    tokens = re.findall(NUMBER, value)
    check(not re.sub(NUMBER, "", value).strip(" ,\t\r\n"), "svg_number", value)
    values = [float(t) for t in tokens]
    check(all(math.isfinite(v) and abs(v) <= 1e6 for v in values), "svg_number", "finite bounded numbers required")
    return values


def multiply(a, b):
    return (a[0]*b[0]+a[2]*b[1], a[1]*b[0]+a[3]*b[1],
            a[0]*b[2]+a[2]*b[3], a[1]*b[2]+a[3]*b[3],
            a[0]*b[4]+a[2]*b[5]+a[4], a[1]*b[4]+a[3]*b[5]+a[5])


def point(m, p):
    q = (m[0]*p[0]+m[2]*p[1]+m[4], m[1]*p[0]+m[3]*p[1]+m[5])
    check(all(math.isfinite(v) and abs(v) < 1e6 for v in q), "svg_number", "transformed point out of bounds")
    return q


def transform(value):
    result = IDENTITY
    pattern = r"(matrix|translate|scale|rotate)\s*\(([^()]*)\)"
    check(not re.sub(pattern, "", value).strip(" ,\t\r\n"), "svg_transform", "matrix/translate/scale/rotate only")
    for kind, body in re.findall(pattern, value):
        v = numbers(body)
        if kind == "matrix":
            check(len(v) == 6, "svg_transform", kind); m = tuple(v)
        elif kind == "translate":
            check(len(v) in (1, 2), "svg_transform", kind); m = (1, 0, 0, 1, v[0], v[1] if len(v) == 2 else 0)
        elif kind == "scale":
            check(len(v) in (1, 2), "svg_transform", kind); m = (v[0], 0, 0, v[-1], 0, 0)
        else:
            check(len(v) in (1, 3), "svg_transform", kind)
            c, s = math.cos(math.radians(v[0])), math.sin(math.radians(v[0]))
            m = (c, s, -s, c, 0, 0)
            if len(v) == 3:
                m = multiply(multiply((1, 0, 0, 1, v[1], v[2]), m), (1, 0, 0, 1, -v[1], -v[2]))
        result = multiply(result, m)
    return result


def similarity(m):
    a, b = math.hypot(m[0], m[1]), math.hypot(m[2], m[3])
    check(1e-6 < a < 1e4 and abs(a-b) <= 1e-5*a and abs(m[0]*m[2]+m[1]*m[3]) <= 1e-5*a*a
          and m[0]*m[3]-m[1]*m[2] > 0, "svg_transform", "positive uniform scale and rotation required")
    return a


def path_data(value, matrix):
    token_pattern = NUMBER + r"|[A-Za-z]"
    tokens = re.findall(token_pattern, value)
    check(not re.sub(token_pattern, "", value).strip(" ,\t\r\n") and len(tokens) <= 2048, "svg_path", "bounded path required")
    paths = []; segments = None; current = (0., 0.); start = current; command = None; i = 0
    arity = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6}
    while i < len(tokens):
        if tokens[i].isalpha():
            command = tokens[i]; i += 1
            check(command.upper() in {*arity, "Z"}, "svg_path", "only M/L/H/V/C/Z paths are covered")
            if command.upper() == "Z":
                check(segments is not None, "svg_path", "close before move")
                if math.dist(current, start) > 1e-12:
                    segments.append(("L", point(matrix, current), point(matrix, start)))
                current = start; command = None; continue
        check(command is not None, "svg_path", "missing command")
        kind = command.upper(); n = arity[kind]
        check(i+n <= len(tokens) and not any(t.isalpha() for t in tokens[i:i+n]), "svg_path", "missing coordinates")
        v = [float(t) for t in tokens[i:i+n]]; i += n
        check(all(math.isfinite(x) and abs(x) <= 1e6 for x in v), "svg_number", "path coordinates")
        relative = command.islower()
        def pair(x, y):
            return (x+current[0], y+current[1]) if relative else (x, y)
        if kind == "M":
            current = pair(*v); start = current; segments = []; paths.append(segments)
            command = "l" if relative else "L"
        else:
            check(segments is not None, "svg_path", "path must start with move")
            if kind == "C":
                pts = [current, pair(*v[:2]), pair(*v[2:4]), pair(*v[4:])]
            else:
                end = pair(*v) if kind == "L" else ((v[0]+current[0] if relative else v[0], current[1]) if kind == "H"
                       else (current[0], v[0]+current[1] if relative else v[0]))
                pts = [current, end]
            segments.append(("C" if kind == "C" else "L", *(point(matrix, p) for p in pts)))
            current = pts[-1]
    check(paths and all(p for p in paths) and sum(map(len, paths)) <= 256, "svg_path", "empty or excessive paths")
    return paths


def samples(segment, count=129):
    if segment[0] == "L":
        return list(segment[1:])
    a, b, c, d = segment[1:]
    return [tuple((1-t)**3*a[j]+3*(1-t)**2*t*b[j]+3*(1-t)*t*t*c[j]+t**3*d[j] for j in range(2))
            for t in (i/(count-1) for i in range(count))]


def circle(path):
    check(len(path) == 4 and all(s[0] == "C" for s in path), "svg_curve", "only four quarter cubic circles are covered")
    ends = [s[1] for s in path]
    center = tuple(sum(p[j] for p in ends)/4 for j in range(2))
    radii = [math.dist(p, center) for p in ends]; radius = sum(radii)/4
    check(radius > EPS and max(radii)-min(radii) <= EPS, "svg_curve", "non-circular endpoints")
    for i, segment in enumerate(path):
        a, b, c, d = segment[1:]
        following = ends[(i+1)%4]
        u, v = tuple(a[j]-center[j] for j in range(2)), tuple(d[j]-center[j] for j in range(2))
        check(math.dist(d, following) <= EPS and abs(sum(u[j]*v[j] for j in range(2))) <= EPS*radius,
              "svg_curve", "quarter endpoints required")
        check(math.dist(b, tuple(a[j]+KAPPA*v[j] for j in range(2))) <= EPS
              and math.dist(c, tuple(d[j]+KAPPA*u[j] for j in range(2))) <= EPS,
              "svg_curve", "nonstandard circle controls")
    radial = max(abs(math.dist(p, center)-radius) for s in path for p in samples(s))
    check(radial <= .00028*radius+EPS, "svg_curve", "cubic residual exceeds circle approximation allowance")
    return {"center": center, "radius": radius, "sampled_radial_residual_sheet_mm": radial}


def normalize(source, drawing_group):
    check(isinstance(source, bytes) and 0 < len(source) <= 500000 and b"<!DOCTYPE" not in source.upper()
          and b"<!ENTITY" not in source.upper(), "input_format", "bounded SVG without DTD/entities")
    root = ET.fromstring(source); elements = list(root.iter())
    check(len(elements) <= 5000 and root.tag.split("}")[-1] == "svg", "input_format", "SVG root required")
    ids = [e.get("id") for e in elements if e.get("id")]
    check(len(ids) == len(set(ids)) and drawing_group in ids, "view_mapping", "unique drawing group required")
    box = numbers(root.get("viewBox", ""))
    check(len(box) == 4 and min(box[2:]) > 0, "svg_viewbox", "explicit viewBox required")
    lengths = []
    for name in ("width", "height"):
        v = root.get(name, "")
        check(re.fullmatch(NUMBER+r"mm", v) is not None, "svg_viewbox", "page size must use mm")
        lengths.append(float(v[:-2]))
    sx, sy = lengths[0]/box[2], lengths[1]/box[3]
    check(sx > 0 and abs(sx-sy) < 1e-10 and root.get("preserveAspectRatio", "xMidYMid meet") in ("xMidYMid meet", "none"),
          "svg_viewbox", "matching page/viewBox aspect ratios required")
    base = (sx, 0, 0, sy, -sx*box[0], -sy*box[1])
    records = []; counts = {"path": 0, "text": 0}; transforms = []
    presentation = {"fill", "fill-rule", "fill-opacity", "stroke", "stroke-width", "stroke-opacity", "stroke-dasharray",
                    "stroke-dashoffset", "stroke-linecap", "stroke-linejoin", "font-family", "font-size", "font-style",
                    "font-weight", "vector-effect"}
    harmless = {"id", "transform", "d", "x", "y", "width", "height", "viewBox", "version", "baseProfile", "preserveAspectRatio"}
    def visit(e, m, inherited, selected=False, depth=0):
        check(depth <= 32, "input_format", "SVG nesting limit")
        tag = e.tag.split("}")[-1]
        check(tag in {"svg", "g", "rect", "path", "text", "title", "desc", "defs"}, "unsupported_svg", tag)
        check(tag != "svg" or e is root, "unsupported_svg", "nested SVG viewport unsupported")
        if tag in {"title", "desc"}: return
        if tag == "defs":
            check(not len(e), "unsupported_svg", "nonempty defs unsupported"); return
        style = dict(inherited)
        for k, v in e.attrib.items():
            if k.startswith("{"):
                check(k == "{http://www.w3.org/XML/1998/namespace}space" or k.startswith("{http://www.inkscape.org/namespaces/inkscape}"),
                      "unsupported_svg", "unsupported namespaced attribute")
                continue
            check(k in presentation | harmless | {"style"}, "unsupported_svg", "unsupported attribute: "+k)
            if k in presentation: style[k] = v
        for declaration in e.get("style", "").split(";"):
            if not declaration.strip(): continue
            k, v = (s.strip() for s in declaration.split(":", 1))
            check(k in presentation, "unsupported_svg", "unsupported CSS: "+k); style[k] = v
        check(all(float(style.get(k, 1)) == 1 for k in ("fill-opacity", "stroke-opacity")),
              "unsupported_svg", "translucency unsupported")
        if style.get("stroke", "none") != "none":
            check(0 < float(style.get("stroke-width", 1)) < 1000, "unsupported_svg", "positive bounded stroke width required")
        if e.get("transform"):
            transforms.append(e.get("transform"))
        m = multiply(m, transform(e.get("transform", ""))); scale = similarity(m)
        selected = selected or e.get("id") == drawing_group
        if e.get("id") == drawing_group:
            check(tag == "g", "view_mapping", "drawing_group must identify a group")
        if tag in {"path", "text"} and selected:
            rid = f"{tag}:{counts[tag]}"; counts[tag] += 1
            record = {"id": rid, "style": style, "matrix": m, "tag": tag}
            if tag == "path":
                record["paths"] = path_data(e.get("d", ""), m)
            else:
                check(not len(e) and style.get("fill", "black") != "none" and style.get("stroke", "none") == "none",
                      "unsupported_svg", "plain visible XML text required")
                x, y = numbers(e.get("x", "")), numbers(e.get("y", ""))
                check(len(x) == len(y) == 1, "unsupported_svg", "single baseline position required")
                height = float(style.get("font-size", "0"))*scale
                check(.5 <= height <= 20, "unsupported_svg", "bounded font height")
                record.update(text=(e.text or "").strip(), origin=point(m, (x[0], y[0])),
                              direction=(m[0]/scale, m[1]/scale), height=height)
            records.append(record)
        elif tag == "rect":
            check(not selected, "unsupported_svg", "only path geometry within selected drawing group")
        elif tag in {"path", "text"}:
            check(False, "unsupported_svg", "unselected path/text; only sheet border rect excluded")
        for child in e: visit(child, m, style, selected, depth+1)
    visit(root, base, {"fill": "black", "stroke": "none"})
    check(len(records) <= 1024 and records, "input_format", "bounded graphics required")
    return records, {"transforms": len(transforms), "paths": counts["path"], "texts": counts["text"],
                     "page_size_mm": lengths, "selection": drawing_group, "association_tolerance_sheet_mm": EPS}
