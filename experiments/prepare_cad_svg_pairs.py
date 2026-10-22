"""Freeze human view selections and references to unchanged native CAD exports.

Run once into a new directory. Selections are manually reviewed outline paths;
their order is not inferred as front/top/right by the reconstruction algorithm.
"""
from pathlib import Path
import hashlib
import json

from research_notes.drawing_to_cad import json_bytes

ROOT=Path(__file__).resolve().parents[1]
# Ordinals within DrawingContent path elements, verified against the source page.
SELECTIONS={name:{"front":"path:0","top":"path:17","right":"path:44"}
            for name in ("one","decimal","scaled","first","no_thru","tolerance")}
SELECTIONS.update(plain={"front":"path:0","top":"path:15","right":"path:30"},
                  no_x={"front":"path:0","top":"path:17","right":"path:41"})


def prepare(destination):
    if destination.exists():
        raise ValueError("new fixture directory required")
    destination.mkdir(parents=True)
    old=ROOT/"fixtures/cad-drawing-exports"
    previous=json.loads((old/"manifest.json").read_text())
    cases=[]
    for case in previous["cases"]:
        if case["format"]!="dxf":continue
        name=case["id"].removesuffix("_dxf")
        source_name="one" if name=="wrong_projection" else name
        for format in ("dxf","svg"):
            context=json.loads((old/case["context"]).read_text())
            if format=="svg":
                context.update(drawing_group="DrawingContent",view_roles=SELECTIONS[source_name])
            context_file=destination/(name+"_"+format+".json")
            context_file.write_bytes(json_bytes(context))
            drawing=old/"inputs"/source_name/("drawing."+format)
            svg=old/"inputs"/source_name/"drawing.svg"
            relative=lambda p: "../cad-drawing-exports/"+str(p.relative_to(old))
            cases.append({**case,"id":name+"_"+format,"pair_id":name,"format":format,
                          "drawing":relative(drawing),"drawing_sha256":hashlib.sha256(drawing.read_bytes()).hexdigest(),
                          "svg":relative(svg),"svg_sha256":hashlib.sha256(svg.read_bytes()).hexdigest(),
                          "context":context_file.name,"context_sha256":hashlib.sha256(context_file.read_bytes()).hexdigest(),
                          "provenance":"Unchanged own-authored FreeCAD 1.1.4 TechDraw export; manually selected SVG outline paths or DXF layers"})
    (destination/"manifest.json").write_bytes(json_bytes({
        "study":"Native SVG and DXF paired reconstruction","cases":cases,
        "license":"Own authored inputs, repository PolyForm-Noncommercial-1.0.0; original source/runtime provenance retained in cad-drawing-exports",
        "human_input":"mm, family, projection, drawing group and three SVG outline path references; no dimensions or scale",
        "selection_reference":"experiments/prepare_cad_svg_pairs.py; manually reviewed path ordinals",
        "evaluation":"../cad-drawing-exports/evaluation; not supplied to interpretation workers"}))


if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("destination",type=Path)
    prepare(p.parse_args().destination)
