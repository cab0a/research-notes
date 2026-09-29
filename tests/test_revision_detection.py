"""Known changes applied before independent STEP export/import, without history."""
from copy import deepcopy
from functools import lru_cache
from html.parser import HTMLParser
import json
import math

import pytest

from research_notes.cad_revision import RevisionComparison
from research_notes.revision_detection import compare_revisions, LENGTH_TOL
from research_notes.revision_report import render_report
from research_notes.step_writer_modes import prepare_step_write


def imported(shape, name="unlabelled.step"):
    source, _ = prepare_step_write(source=None, mode="reconstruct", shape=shape)
    return RevisionComparison.load(source, name)


@lru_cache(maxsize=40)
def plate(holes=((6., 5., 1.),), thickness=4., shift=0.):
    # Independent fixture construction: tests do not call the recognition grammar.
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCP.gp import gp_Pnt
    shape = BRepPrimAPI_MakeBox(gp_Pnt(shift, 0, 0), 12., 10., thickness).Shape()
    for x, y, radius in holes:
        from OCP.gp import gp_Ax2, gp_Dir
        tool = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x+shift, y, -2), gp_Dir(0, 0, 1)), radius, thickness+4).Shape()
        shape = BRepAlgoAPI_Cut(shape, tool).Shape()
    return imported(shape)


def holes(result):
    return [r for r in result["regions"] if r["id"].startswith("hole-")]


def values(result, name):
    return [d for d in result["dimensions"] if d["name"] == name]


def test_recovers_measured_diameter_and_face_correspondence():
    result = compare_revisions(plate(), plate(((6., 5., 1.4),)))
    assert result["status"] == "compared" and holes(result)[0]["status"] == "changed"
    d = values(result, "穴径")[0]
    assert (d["old"], d["new"], d["delta"]) == pytest.approx((2., 2.8, .8))
    assert len(result["face_relations"]) == 7
    assert set(result["face_status"]["old"].values()) == {"unchanged", "changed"}
    assert all(r["old_faces"] and r["new_faces"] for r in result["face_relations"])


def test_equal_volume_moved_hole_is_a_change_and_position_is_measured():
    before, after = plate(), plate(((7.2, 6., 1.),))
    assert before["metrics"]["absolute_volume"] == pytest.approx(after["metrics"]["absolute_volume"])
    result = compare_revisions(before, after)
    assert holes(result)[0]["status"] == "changed"
    assert values(result, "穴中心X")[0]["delta"] == pytest.approx(1.2)
    assert values(result, "穴中心Y")[0]["delta"] == pytest.approx(1.)
    assert values(result, "穴径")[0]["status"] == "unchanged"
    assert all(r["status"] == "changed" for r in result["face_relations"] if r["role"].startswith("z_"))


def test_thickness_changes_side_and_top_faces_but_not_bottom_trim():
    result = compare_revisions(plate(), plate(thickness=5.))
    assert values(result, "板厚")[0]["delta"] == pytest.approx(1.)
    roles = {r["role"]: r["status"] for r in result["face_relations"]}
    assert roles["z_min"] == "unchanged" and roles["z_max"] == "changed"
    assert roles["x_min"] == "changed"
    assert holes(result)[0]["status"] == "changed"
    assert all(d["status"] == "unchanged" for d in result["dimensions"] if d["name"] != "板厚")


@pytest.mark.parametrize("reverse", [False, True])
def test_addition_and_deletion_leave_the_retained_hole_matched(reverse):
    a, b = plate(((3., 5., .8),)), plate(((3., 5., .8), (9., 5., .8)))
    result = compare_revisions(*( (b, a) if reverse else (a, b) ))
    assert result["status"] == "compared"
    assert sorted(r["status"] for r in holes(result)) == sorted(["unchanged", "deleted" if reverse else "added"])
    assert len(values(result, "穴径")) == 1
    unmatched = next(r for r in holes(result) if r["status"] != "unchanged")
    assert bool(unmatched["old_faces"]) == reverse and bool(unmatched["new_faces"]) != reverse


def test_ambiguous_repeated_holes_do_not_acquire_fake_dimensions_or_add_delete_labels():
    result = compare_revisions(plate(((4., 4., .6), (8., 4., .6))), plate(((6., 3., .6), (6., 5., .6))))
    assert result["status"] == "partial" and len(result["unresolved"]) == 4
    assert {r["status"] for r in holes(result)} == {"unresolved"}
    assert [d["name"] for d in result["dimensions"]] == ["板厚"]
    assert all(r["status"] == "unresolved" for r in result["face_relations"] if r["role"].startswith("z_"))


def test_distant_move_is_held_instead_of_claiming_delete_and_add():
    result = compare_revisions(plate(((2., 5., .5),)), plate(((10., 5., .5),)))
    assert result["status"] == "partial" and len(result["unresolved"]) == 2
    assert not values(result, "穴中心X")


def test_separate_exports_with_reordered_holes_do_not_use_face_ids_as_identity():
    a = plate(((3., 5., .8), (9., 5., 1.)))
    b = plate(((9., 5., 1.), (3., 5., .8)))
    result = compare_revisions(a, b)
    assert result["status"] == "compared"
    assert {r["status"] for r in result["regions"]} == {"unchanged"}
    assert len(values(result, "穴径")) == 2
    assert all(abs(d["delta"]) <= LENGTH_TOL for d in result["dimensions"])


def test_small_changes_remain_measured_but_within_tolerance():
    result = compare_revisions(plate(), plate(((6., 5., 1.000001),)))
    d = values(result, "穴径")[0]
    assert d["status"] == "unchanged" and d["delta"] == pytest.approx(.000002)


def test_move_and_diameter_change_can_be_matched_when_unique():
    result = compare_revisions(plate(), plate(((7., 5., 1.2),)))
    assert result["status"] == "compared"
    assert values(result, "穴径")[0]["delta"] == pytest.approx(.4)
    assert values(result, "穴中心X")[0]["delta"] == pytest.approx(1.)


def test_translation_is_not_silently_treated_as_local_hole_motion():
    result = compare_revisions(plate(), plate(shift=30.))
    assert result["status"] == "unresolved" and result["dimensions"] == []
    assert set(result["face_status"]["new"].values()) == {"unresolved"}


@pytest.mark.parametrize("shape_type", ["sphere", "blind", "rotated"])
def test_unsupported_geometry_is_viewable_but_unresolved(shape_type):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeSphere, BRepPrimAPI_MakeCylinder
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Pnt, gp_Dir, gp_Ax1, gp_Ax2, gp_Trsf
    shape = BRepPrimAPI_MakeBox(12., 10., 4.).Shape()
    if shape_type == "sphere":
        shape = BRepPrimAPI_MakeSphere(3.).Shape()
    elif shape_type == "blind":
        tool = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(6., 5., 2.), gp_Dir(0, 0, 1)), 1., 3.).Shape()
        shape = BRepAlgoAPI_Cut(shape, tool).Shape()
    else:
        tr = gp_Trsf(); tr.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), .3)
        shape = BRepBuilderAPI_Transform(shape, tr, True).Shape()
    data = imported(shape)
    assert data["polygons"] and data["features"]["status"] == "unsupported"
    result = compare_revisions(plate(), data)
    assert result["status"] == "unresolved" and not result["dimensions"] and result["unresolved"]


class ReportParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.tags = []; self.in_data = False; self.data = ""
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs); self.tags.append((tag, attrs))
        if tag == "script" and attrs.get("id") == "comparison-data": self.in_data = True
    def handle_endtag(self, tag):
        if tag == "script": self.in_data = False
    def handle_data(self, text):
        if self.in_data: self.data += text


def test_report_is_offline_self_contained_escaped_and_contains_unresolved_evidence():
    comparison = RevisionComparison()
    old = deepcopy(plate(((4., 4., .6), (8., 4., .6))))
    old["file_name"] = '<script>alert("unsafe")</script>.step'
    comparison.publish({"old": old, "new": plate(((6., 3., .6), (6., 5., .6)))})
    state = comparison.state()
    report = render_report(state, {"yaw": 1., "pitch": -.8, "zoom": 1.5, "edges": True})
    parser = ReportParser(); parser.feed(report)
    assert sum(tag == "svg" for tag, _ in parser.tags) == 2
    assert all("src" not in attrs and "href" not in attrs and not any(k.startswith("on") for k in attrs) for _, attrs in parser.tags)
    assert all(attrs.get("type") == "application/json" for tag, attrs in parser.tags if tag == "script")
    data = json.loads(parser.data)
    assert data["analysis"]["status"] == "partial" and len(data["analysis"]["unresolved"]) == 4
    assert data["old"]["source_sha256"] == old["source_sha256"]
    assert "revision_token" not in data and data["report_camera"]["zoom"] == 1.5
    assert '<script>alert("unsafe")' not in report and '&lt;script&gt;' in report
    assert "判定保留" in report and data["analysis"]["conditions"]["length_tolerance_mm"] == LENGTH_TOL
    assert comparison.state() == state


def test_report_saves_all_matched_measurements_not_only_changed_rows():
    comparison = RevisionComparison(); comparison.publish({"old": plate(), "new": plate(((7., 5., 1.),))})
    report = render_report(comparison.state())
    parser = ReportParser(); parser.feed(report)
    data = json.loads(parser.data)
    assert len(data["analysis"]["dimensions"]) == 4
    assert values(data["analysis"], "穴中心X")[0]["delta"] == pytest.approx(1.)
    assert "穴径" in report and "板厚" in report
