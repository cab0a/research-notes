"""Exploratory, AI-free reconstruction of a declared three-view SVG plate grammar.

Only visible SVG geometry/text and explicit human context enter interpretation.
No ground-truth STEP, evaluator recipe, OCR or external model is consulted.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

STUDY_SCHEMA = "1.0.0"
FAMILY = "rectangular_plate_with_separated_z_through_holes"
NUM = r"([0-9]+(?:\.[0-9]+)?)"
DIM = re.compile(r"([WLT])=" + NUM)
HOLE = re.compile(r"X=" + NUM + r" Y=" + NUM + r" DIA=" + NUM + r"( THRU)?")
TOL = 1e-6


class DrawingIssue(ValueError):
    def __init__(self, code, stage, detail):
        super().__init__(detail)
        self.code, self.stage = code, stage


def require(condition, code, stage, detail):
    if not condition:
        raise DrawingIssue(code, stage, detail)


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def _float(element, name):
    try:
        value = float(element.attrib[name])
    except (ValueError, KeyError):
        raise DrawingIssue("invalid_svg_number", "drawing_recognition", name)
    require(math.isfinite(value) and abs(value) <= 10000, "invalid_svg_number", "drawing_recognition", name)
    return value


def interpret_svg(source: bytes, context: dict):
    digest = hashlib.sha256(source).hexdigest()
    base = {"schema_version": STUDY_SCHEMA, "source_sha256": digest, "human_context": context,
            "method": "C_vector_geometry_with_explicit_annotation_grammar", "ai_used": False,
            "original_authoring_history_recovered": False}
    try:
        require(0 < len(source) <= 128000 and b"<!DOCTYPE" not in source.upper() and b"<!ENTITY" not in source.upper(),
                "input_format", "drawing_recognition", "bounded SVG without DTD/entities required")
        require(isinstance(context, dict) and set(context) == {"projection", "unit", "family_assumption", "view_roles"},
                "context_missing", "input_ambiguity", "explicit human context required")
        require(context["unit"] == "mm" and context["family_assumption"] == FAMILY,
                "unsupported_context", "unsupported_input", "only the declared millimetre plate grammar is tested")
        require(context["projection"] in ("first_angle", "third_angle"), "projection_unknown", "input_ambiguity", "projection must be explicit")
        roles = context["view_roles"]
        require(isinstance(roles, dict) and set(roles) == {"front", "top", "right"} and all(isinstance(v, str) for v in roles.values())
                and len(set(roles.values())) == 3, "view_mapping", "input_ambiguity", "three distinct human-selected view groups required")
        root = ET.fromstring(source)
        elements = list(root.iter())
        allowed = {"svg", "g", "rect", "circle", "line", "text"}
        require(len(elements) <= 256 and root.tag.split("}")[-1] == "svg", "input_format", "drawing_recognition", "unsupported SVG root/size")
        ids = [e.get("id") for e in elements if e.get("id")]
        require(len(ids) == len(set(ids)), "duplicate_id", "drawing_recognition", "SVG IDs must be unique")
        for e in elements:
            require(e.tag.split("}")[-1] in allowed and not any(k in e.attrib for k in ("transform", "style", "display", "visibility", "opacity", "href")),
                    "unsupported_svg", "unsupported_input", "only flat, visible primitive SVG is implemented")
        groups = {e.get("id"): e for e in root if e.tag.split("}")[-1] == "g"}
        require(all(v in groups for v in roles.values()), "view_mapping", "drawing_recognition", "selected group missing")
        views, dims, evidence, rows = {}, {}, {}, []
        for name, group_id in roles.items():
            group = groups[group_id]
            children = list(group)
            require(not any(e.tag.split("}")[-1] == "g" for e in children), "unsupported_svg", "unsupported_input", "nested geometry groups not implemented")
            rectangles = [e for e in children if e.tag.split("}")[-1] == "rect"]
            require(len(rectangles) == 1, "unsupported_profile", "unsupported_input", "one rectangular outer profile required per view")
            rect = rectangles[0]
            box = [_float(rect, k) for k in ("x", "y", "width", "height")]
            require(box[2] > 0 and box[3] > 0, "degenerate_profile", "drawing_conflict", name)
            local_dims, local_evidence = {}, []
            for text in (e for e in children if e.tag.split("}")[-1] == "text"):
                value = "".join(text.itertext()).strip()
                match = DIM.fullmatch(value)
                hole = HOLE.fullmatch(value)
                if match:
                    key, number = match[1], float(match[2])
                    require(key not in local_dims and 1e-4 < number <= 1000, "dimension_conflict", "drawing_conflict", value)
                    local_dims[key] = number
                    evidence.setdefault(key, []).append({"element_id": text.get("id"), "visible_text": value, "value_mm": number})
                    if key in dims:
                        require(abs(dims[key] - number) <= TOL, "dimension_conflict", "drawing_conflict", value)
                    dims[key] = number
                elif hole:
                    require(name == "top", "view_mapping", "drawing_conflict", "hole table belongs to top view in this grammar")
                    require(hole[4] is not None, "hole_extent_ambiguous", "input_ambiguity", "diameter alone does not specify through/blind/depth")
                    rows.append({"x": float(hole[1]), "y": float(hole[2]), "diameter": float(hole[3]), "text_id": text.get("id"), "visible_text": value})
                elif value.startswith(("W=", "L=", "T=", "X=")):
                    raise DrawingIssue("unsupported_annotation", "drawing_recognition", value)
            required = {"front": {"W", "T"}, "top": {"W", "L"}, "right": {"L", "T"}}[name]
            require(set(local_dims) == required, "dimension_missing", "input_ambiguity", name + " needs " + str(sorted(required)))
            u, v = {"front": ("W", "T"), "top": ("W", "L"), "right": ("L", "T")}[name]
            scale = box[2] / local_dims[u]
            require(abs(box[3] / scale - local_dims[v]) <= TOL, "geometry_dimension_conflict", "drawing_conflict", "uniform scale per view is required")
            circles, lines = [], []
            for e in children:
                tag = e.tag.split("}")[-1]
                if tag == "circle":
                    require(name == "top", "unsupported_geometry", "unsupported_input", "circle in a non-top view")
                    circles.append({"center": [(_float(e, "cx")-box[0])/scale, (box[1]+box[3]-_float(e, "cy"))/scale],
                                    "radius": _float(e, "r")/scale, "id": e.get("id")})
                elif tag == "line":
                    require(bool(e.get("stroke-dasharray")), "unsupported_geometry", "unsupported_input", "only declared hidden lines in this first grammar")
                    lines.append([[(_float(e, "x"+str(i))-box[0])/scale, (box[1]+box[3]-_float(e, "y"+str(i)))/scale] for i in (1, 2)])
            views[name] = {"box": box, "extent_mm": [local_dims[u], local_dims[v]], "circles": circles, "hidden_lines": lines}
        front, top, right = (views[n]["box"] for n in ("front", "top", "right"))
        center = lambda b: (b[0]+b[2]/2, b[1]+b[3]/2)
        f, t, r = map(center, (front, top, right))
        sign = 1 if context["projection"] == "third_angle" else -1
        require((f[1]-t[1])*sign > 0 and (r[0]-f[0])*sign > 0 and abs(f[0]-t[0]) <= TOL and abs(f[1]-r[1]) <= TOL,
                "projection_layout_conflict", "drawing_conflict", "declared projection/view mapping disagrees with sheet placement")
        require(len(rows) == len(views["top"]["circles"]) <= 3, "hole_annotation_missing", "input_ambiguity", "every top circle needs one explicit through-hole row")
        unmatched = list(views["top"]["circles"])
        holes = []
        for row in rows:
            matches = [c for c in unmatched if max(abs(c["center"][0]-row["x"]), abs(c["center"][1]-row["y"]), abs(2*c["radius"]-row["diameter"])) <= TOL]
            require(len(matches) == 1, "annotation_geometry_mismatch", "drawing_conflict", "hole row/circle correspondence is not unique")
            circle = matches[0]
            unmatched.remove(circle)
            holes.append({k: row[k] for k in ("x", "y", "diameter")})
            evidence.setdefault("holes", []).append({"text_id": row["text_id"], "visible_text": row["visible_text"], "circle_id": circle["id"]})
        for name, coordinate in (("front", "x"), ("right", "y")):
            observed = []
            for a, b in views[name]["hidden_lines"]:
                require(abs(a[0]-b[0]) <= TOL and abs(min(a[1], b[1])) <= TOL and abs(max(a[1], b[1])-dims["T"]) <= TOL,
                        "hidden_line_conflict", "drawing_conflict", name)
                observed.append(a[0])
            expected = sorted(h[coordinate]+s*h["diameter"]/2 for h in holes for s in (-1, 1))
            require(len(observed) == len(expected) and all(abs(a-b) <= TOL for a,b in zip(sorted(observed), expected)),
                    "hidden_line_conflict", "drawing_conflict", name)
        require(not views["top"]["hidden_lines"], "unsupported_geometry", "unsupported_input", "top hidden features not implemented")
        parameters = {"width": dims["W"], "length": dims["L"], "thickness": dims["T"], "holes": holes}
        from .parametric_features import PlateSpec, feature_spec, validate_feature
        plate = PlateSpec(**{k: parameters[k] for k in ("width", "length", "thickness")})
        for h in holes:
            validate_feature(plate, feature_spec("through_hole", x=h["x"], y=h["y"], radius=h["diameter"]/2))
        for i, h in enumerate(holes):
            require(all(math.hypot(h["x"]-o["x"], h["y"]-o["y"]) > (h["diameter"]+o["diameter"])/2+TOL for o in holes[i+1:]),
                    "intersecting_holes", "unsupported_input", "separated holes required")
        return {**base, "status": "candidate", "parameters": parameters, "evidence": evidence, "views": views,
                "claim_boundary": "Conditional candidate under human-provided family/view/frame assumptions; not unique general drawing interpretation."}
    except DrawingIssue as error:
        return {**base, "status": "withheld", "failure_stage": error.stage, "reason_code": error.code, "detail": str(error)}
    except (ValueError, ET.ParseError, TypeError) as error:
        return {**base, "status": "withheld", "failure_stage": "drawing_recognition", "reason_code": "invalid_input", "detail": str(error)}


def feature_model(parameters, source_sha256):
    from .deterministic_recompute import FeatureModel, ModelNode, validate_model
    from .parametric_features import PlateSpec
    plate = PlateSpec(**{k: parameters[k] for k in ("width", "length", "thickness")})
    nodes = [ModelNode("plate", "plate", (), tuple(sorted(asdict(plate).items())))]
    previous = "plate"
    for index, hole in enumerate(parameters["holes"], 1):
        identifier = f"hole_{index}"
        nodes.append(ModelNode(identifier, "through_hole", (previous,), tuple(sorted({"x": hole["x"], "y": hole["y"], "radius": hole["diameter"]/2}.items()))))
        previous = identifier
    nodes.append(ModelNode("result", "result", (previous,)))
    model = FeatureModel("svg_plate_candidate", tuple(nodes), "result", provenance="unconfirmed_candidate", source_sha256=source_sha256)
    validate_model(model)
    return model


def build_candidate(parameters, source_sha256):
    from .deterministic_recompute import recompute
    model = feature_model(parameters, source_sha256)
    result = recompute(model)
    return model, result, result.current_output()


def export_candidate(parameters, source_sha256, destination):
    from .step_writer_modes import write_step
    model, result, output = build_candidate(parameters, source_sha256)
    return write_step(Path(destination), source=None, mode="reconstruct", shape=output.shape)


def candidate_code(parameters, source_sha256):
    return ("# Generated bounded CAD recipe; edit PARAMETERS and regenerate. Not recovered authoring history.\n"
            "from research_notes.drawing_to_cad import export_candidate\n"
            f"PARAMETERS = {parameters!r}\nSOURCE_SHA256 = {source_sha256!r}\n"
            "if __name__ == '__main__':\n"
            "    import argparse\n    parser = argparse.ArgumentParser()\n    parser.add_argument('step')\n"
            "    args = parser.parse_args()\n    export_candidate(PARAMETERS, SOURCE_SHA256, args.step)\n")


def project_shape(shape):
    """Actual OCCT hidden-line removal, sampled into projection-plane XY."""
    from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
    from OCP.HLRAlgo import HLRAlgo_Projector
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopoDS import TopoDS
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GeomAbs import GeomAbs_Line
    from .brep_runtime import indexed_shapes
    result = {}
    for name, normal, xaxis in (("front", (0,-1,0), (1,0,0)), ("top", (0,0,1), (1,0,0)), ("right", (1,0,0), (0,1,0))):
        algo = HLRBRep_Algo()
        algo.Add(shape)
        algo.Projector(HLRAlgo_Projector(gp_Ax2(gp_Pnt(0,0,0), gp_Dir(*normal), gp_Dir(*xaxis))))
        algo.Update()
        algo.Hide()
        converted = HLRBRep_HLRToShape(algo)
        groups = {}
        for visibility, compounds in (("visible", (converted.VCompound(), converted.OutLineVCompound())),
                                      ("hidden", (converted.HCompound(), converted.OutLineHCompound()))):
            lines = []
            for compound in compounds:
                if compound.IsNull():
                    continue
                edges = indexed_shapes(compound, TopAbs_EDGE)
                for i in range(1, edges.Extent()+1):
                    curve = BRepAdaptor_Curve(TopoDS.Edge_s(edges.FindKey(i)))
                    low, high = curve.FirstParameter(), curve.LastParameter()
                    count = 2 if curve.GetType() == GeomAbs_Line else 129
                    lines.append([list(curve.Value(low+(high-low)*j/(count-1)).Coord())[:2] for j in range(count)])
            groups[visibility] = lines
        result[name] = groups
    return result


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("svg", type=Path)
    parser.add_argument("context", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output_dir.exists() and (not args.output_dir.is_dir() or any(args.output_dir.iterdir())):
        parser.error("output directory must be new or empty; prior CAD candidates are not reused")
    with args.svg.open("rb") as stream:
        source = stream.read(128001)
    context = json.loads(args.context.read_text())
    report = interpret_svg(source, context)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "inference.json").write_bytes(json_bytes(report))
    if report["status"] == "candidate":
        (args.output_dir / "model.json").write_bytes(json_bytes(asdict(feature_model(report["parameters"], report["source_sha256"]))))
        (args.output_dir / "candidate.py").write_text(candidate_code(report["parameters"], report["source_sha256"]), encoding="utf-8")
    print(json.dumps({"status": report["status"], "reason_code": report.get("reason_code")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
