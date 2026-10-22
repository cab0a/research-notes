"""Native SVG interpretation contracts; corruption must not become a CAD candidate."""
import copy
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from research_notes.cad_drawing_import import interpret_cad_drawing
from research_notes.cad_svg_import import interpret_native_svg, main
from research_notes.svg_drawing_graphics import transform, point, path_data, normalize
from research_notes.drawing_to_cad import DrawingIssue

ROOT=Path(__file__).resolve().parents[1]
FIX=ROOT/"fixtures/cad-svg-dxf"
CASES=json.loads((FIX/"manifest.json").read_text())["cases"]


def source(name="one"):
    case=next(c for c in CASES if c["id"]==name+"_svg")
    return (FIX/case["drawing"]).read_bytes(),json.loads((FIX/case["context"]).read_text())


def edit_svg(edit):
    data,context=source()
    root=ET.fromstring(data)
    group=next(e for e in root.iter() if e.get("id")=="DrawingContent")
    paths=[e for e in group.iter() if e.tag.endswith("}path")]
    texts=[e for e in group.iter() if e.tag.endswith("}text")]
    parent={child:p for p in root.iter() for child in p}
    selected={role:paths[int(ref.split(":")[1])] for role,ref in context["view_roles"].items()}
    edit(root,group,paths,texts,parent)
    updated=[e for e in group.iter() if e.tag.endswith("}path")]
    context["view_roles"]={role:f"path:{updated.index(e)}" for role,e in selected.items()}
    return ET.tostring(root),context


@pytest.mark.parametrize("case",CASES,ids=lambda c:c["id"])
def test_fixed_native_pair_expectations(case):
    data=(FIX/case["drawing"]).read_bytes()
    context=json.loads((FIX/case["context"]).read_text())
    result=interpret_native_svg(data,context) if case["format"]=="svg" else interpret_cad_drawing(data,context,"dxf")
    assert result["status"]==case["expected_status"]
    assert result.get("reason_code")==case.get("expected_reason")
    if result["status"]=="candidate":
        # Independent labelled drawing values, not coordinates from inferred output.
        expected={"width":52.5,"length":37.25,"thickness":6.5,"holes":[{"x":17.5,"y":13.25,"diameter":5.5}]} if case["pair_id"]=="decimal" else {
            "width":40.,"length":30.,"thickness":8.,"holes":[] if case["pair_id"]=="plain" else [{"x":12.,"y":10.,"diameter":6.}]}
        assert result["parameters"]==expected


@pytest.mark.parametrize("value,expected",[
    ("translate(10 20) scale(2)",(12,24)),
    ("scale(2) translate(10 20)",(22,44)),
    ("rotate(90)",(-2,1)),
    ("rotate(90 3 4)",(5,2)),
    ("matrix(0 -2 2 0 10 20)",(14,18)),
])
def test_transform_composition_against_hand_calculation(value,expected):
    assert point(transform(value),(1,2))==pytest.approx(expected)


@pytest.mark.parametrize("outer,inner",[
    ("translate(13,-21) scale(1.3)",""),
    ("translate(50,70) rotate(32) scale(2)","scale(.5) rotate(-32) translate(-50,-70)"),
    ("rotate(90 100 100)","rotate(-90 100 100)"),
    ("matrix(2,0,0,2,0,0)","scale(.5)"),
])
def test_nested_transform_equivalence(outer,inner):
    def mutate(root,group,paths,texts,parent):
        group.set("transform",outer)
        wrapper=ET.Element(group.tag,transform=inner)
        for child in list(group):
            group.remove(child);wrapper.append(child)
        group.append(wrapper)
    result=interpret_native_svg(*edit_svg(mutate))
    assert result["status"]=="candidate",result
    assert result["parameters"]==interpret_native_svg(*source())["parameters"]


def test_graphic_order_is_not_view_order():
    def mutate(root,group,paths,texts,parent):
        group[:]=list(reversed(group[:]))
    result=interpret_native_svg(*edit_svg(mutate))
    assert result["status"]=="candidate"
    assert result["parameters"]==interpret_native_svg(*source())["parameters"]


def test_relative_path_and_close_commands():
    expected=path_data("M10 20 L20 20 L20 25 L10 25 Z",(1,0,0,1,0,0))
    actual=path_data("m10 20 h10 v5 h-10 z",(1,0,0,1,0,0))
    assert actual==expected
    assert path_data("m0 0 c0 1 1 2 2 2",(1,0,0,1,0,0))==path_data("M0 0 C0 1 1 2 2 2",(1,0,0,1,0,0))


def bad_curve(root,group,paths,texts,parent):
    p=next(p for p in paths if "C" in p.get("d",""))
    p.set("d",p.get("d").replace("66.5685","72.5685"))


def wrong_text_rotation(root,group,paths,texts,parent):
    t=next(t for t in texts if t.text=="30")
    parent[t].set("transform",parent[t].get("transform")+" rotate(17)")


def missing_hidden(root,group,paths,texts,parent):
    # Native front-hole edge, intentionally change its visibility semantics.
    p=next(p for p in paths if p.get("d")=="M-50,40 L-50,-40")
    parent[p].set("stroke-dasharray","")


def missing_arrow(root,group,paths,texts,parent):
    p=next(p for p in paths if p.get("d")=="M0,0 L-35,-5.83333 L-35,5.83333 L0,0")
    parent[p].remove(p)


def wrong_value(root,group,paths,texts,parent):
    for t in texts:
        if t.text=="12":t.text="13"


def misplaced_text(root,group,paths,texts,parent):
    for t in texts:
        if t.text=="12":parent[t].set("transform","translate(0,0)")


def wrong_view_geometry(root,group,paths,texts,parent):
    p=paths[17]
    parent[p].set("transform",parent[p].get("transform")+" scale(1.1)")


def unsupported_arc(root,group,paths,texts,parent):
    p=next(p for p in paths if "C" in p.get("d",""))
    p.set("d","M0 0 A30 30 0 0 0 60 0")


@pytest.mark.parametrize("mutation,reason",[
    (bad_curve,"svg_curve"),
    (wrong_text_rotation,"dimension_label_ambiguous"),
    (missing_hidden,"hidden_line_conflict"),
    (missing_arrow,"dimension_arrow_missing"),
    (wrong_value,"annotation_geometry_mismatch"),
    (misplaced_text,"dimension_label_ambiguous"),
    (wrong_view_geometry,"dimension_target_ambiguous"),
    (unsupported_arc,"svg_path"),
])
def test_corrupted_evidence_is_withheld(mutation,reason):
    result=interpret_native_svg(*edit_svg(mutation))
    assert result["status"]=="withheld"
    assert result["reason_code"]==reason,result


@pytest.mark.parametrize("attribute,value",[
    ("transform","scale(1,1.1)"),("transform","scale(-1,1)"),("transform","skewX(10)"),
    ("transform","scale(0)"),("style","display:none"),("style","opacity:.5"),
    ("clip-path","url(#clip)"),("class","hidden"),("filter","url(#filter)"),
    ("stroke-width","0"),("transform","matrix(1,0,0,1,NaN,0)"),
])
def test_unsupported_rendering_withheld(attribute,value):
    def mutate(root,group,paths,texts,parent):group.set(attribute,value)
    result=interpret_native_svg(*edit_svg(mutate))
    assert result["status"]=="withheld",result


def test_unassigned_text_and_duplicate_dimensions_not_ignored():
    def mutate(root,group,paths,texts,parent):
        parent[texts[0]].append(copy.deepcopy(texts[0]))
    result=interpret_native_svg(*edit_svg(mutate))
    assert result["status"]=="withheld"


def test_curve_approximation_not_reported_as_exact():
    result=interpret_native_svg(*source())
    values=[r["sampled_radial_residual_sheet_mm"] for r in result["curve_evidence"]]
    assert values and all(.0007<v<.0009 for v in values)
    assert result["normalization"]["max_hole_label_geometry_residual_mm"]<1e-6
    assert len(result["raw_drawing_polylines_mm"]["top"][0])==516


def test_no_external_file_access(monkeypatch):
    data,context=source()
    def forbidden(*a,**k):raise AssertionError("Inference must not read truth, paired DXF or files")
    monkeypatch.setattr(Path,"read_bytes",forbidden)
    monkeypatch.setattr(Path,"read_text",forbidden)
    assert interpret_native_svg(data,context)["status"]=="candidate"


def test_numeric_context_cannot_replace_missing_dimensions():
    data,context=source("no_x");context["width"]=40
    assert interpret_native_svg(data,context)["reason_code"]=="context_missing"


def test_withheld_cli_writes_no_cad(tmp_path):
    case=next(c for c in CASES if c["id"]=="no_x_svg")
    out=tmp_path/"worker"
    main([str(FIX/case["drawing"]),str(FIX/case["context"]),"--output-dir",str(out)])
    assert sorted(p.name for p in out.iterdir())==["inference.json"]


@pytest.mark.parametrize("data",[b"",b"<svg>",b"<!DOCTYPE svg><svg/>",b"x"*500001])
def test_invalid_or_unbounded_input(data):
    assert interpret_native_svg(data,source()[1])["status"]=="withheld"


def test_frozen_input_hashes_and_no_original_data_changes():
    for case in CASES:
        for key in ("drawing","svg","context"):
            assert hashlib.sha256((FIX/case[key]).read_bytes()).hexdigest()==case[key+"_sha256"]
