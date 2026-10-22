"""Geometric dimension association and conservative failure controls."""
import copy
import hashlib
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from research_notes.drawing_dimensions import interpret_dimension_svg, main
from research_notes.drawing_to_cad import build_candidate, interpret_svg

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures/drawing-dimensions"
CASES = json.loads((FIXTURES / "manifest.json").read_text())["cases"]


def inputs(name):
    case = next(c for c in CASES if c["id"] == name)
    return (FIXTURES / case["svg"]).read_bytes(), json.loads((FIXTURES / case["context"]).read_text())


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_dimension_line_controls_and_reason_codes(case):
    source, context = inputs(case["id"])
    report = interpret_dimension_svg(source, context)
    assert report["status"] == case["expected_status"], report
    assert report.get("reason_code") == case["expected_reason"]
    assert report["source_sha256"] == hashlib.sha256(source).hexdigest()
    assert not report["ai_used"] and not report["original_authoring_history_recovered"]
    if report["status"] == "withheld":
        assert "parameters" not in report
    else:
        assert report["dimension_evidence"]
        assert all(not any(prefix in e["visible_text"] for prefix in ("W=", "L=", "T=", "X=", "Y=")) for e in report["dimension_evidence"])
    assert interpret_svg(source, context)["status"] == "withheld"


def canonical(parameters):
    return {**parameters, "holes": sorted(parameters["holes"], key=lambda h: (h["x"], h["y"]))}


@pytest.mark.parametrize("name", ["one_first", "one_scaled", "one_anonymous"])
def test_projection_scale_and_opaque_ids_do_not_change_parameters(name):
    first = interpret_dimension_svg(*inputs("one_third"))
    after = interpret_dimension_svg(*inputs(name))
    assert canonical(first["parameters"]) == canonical(after["parameters"])


def test_two_hole_order_is_not_feature_identity():
    first = interpret_dimension_svg(*inputs("two_third"))
    after = interpret_dimension_svg(*inputs("two_reordered"))
    assert canonical(first["parameters"]) == canonical(after["parameters"])
    from experiments.run_drawing_to_cad import edit_parameters
    assert canonical(edit_parameters(first["parameters"])) == canonical(edit_parameters(after["parameters"]))


def test_decimal_dimensions_are_not_the_previous_recipe_constants():
    report = interpret_dimension_svg(*inputs("decimal_plate"))
    assert report["parameters"] == {"width": 52.5, "length": 37.25, "thickness": 6.5,
                                    "holes": [{"x": 17.5, "y": 13.25, "diameter": 5.5}]}


def test_interpreter_has_no_truth_file_or_scale_sidecar_access(monkeypatch):
    source, context = inputs("one_third")
    original = io.open
    def guard(path, *args, **kwargs):
        assert "/evaluation/" not in str(path).replace("\\", "/")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(io, "open", guard)
    report = interpret_dimension_svg(source, context)
    assert report["status"] == "candidate"
    extra = {**context, "scale": 4, "truth_width": 40}
    assert interpret_dimension_svg(source, extra)["status"] == "withheld"


def test_all_element_names_can_change_including_group_mapping():
    source, context = inputs("one_third")
    root = ET.fromstring(source)
    mapping = {}
    for i, element in enumerate(root.iter()):
        if element.get("id"):
            mapping[element.get("id")] = f"opaque_{i}"
            element.set("id", f"opaque_{i}")
    context["view_roles"] = {k: mapping[v] for k,v in context["view_roles"].items()}
    changed = interpret_dimension_svg(ET.tostring(root), context)
    assert changed["status"] == "candidate"
    assert changed["parameters"]["holes"][0]["x"] == 12


def test_moving_label_off_line_does_not_fall_back_to_outline_scale():
    source, context = inputs("one_third")
    root = ET.fromstring(source)
    label = next(e for e in root.iter() if e.text == "12")
    label.set("y", str(float(label.get("y"))+100))
    report = interpret_dimension_svg(ET.tostring(root), context)
    assert report["status"] == "withheld" and "parameters" not in report


def test_incorrect_position_value_is_not_replaced_by_circle_measurement():
    source, context = inputs("one_third")
    root = ET.fromstring(source)
    next(e for e in root.iter() if e.text == "12").text = "11"
    report = interpret_dimension_svg(ET.tostring(root), context)
    assert report["status"] == "withheld" and report["reason_code"] == "annotation_geometry_mismatch"


@pytest.mark.parametrize("name", ["plain_third", "one_third", "two_third", "decimal_plate"])
def test_extracted_dimensions_reuse_constrained_feature_graph(name):
    pytest.importorskip("OCP")
    report = interpret_dimension_svg(*inputs(name))
    model, recomputed, output = build_candidate(report["parameters"], report["source_sha256"])
    assert output.metrics.analyzer_valid and output.metrics.solid_count == 1
    assert model.source_sha256 == report["source_sha256"]
    assert all(s.status == "valid" for s in recomputed.states)
    assert all(s.sketch_fingerprint for s in recomputed.states if s.node_id != "result")


def test_withheld_cli_does_not_emit_cad_and_rejects_reused_directory(tmp_path):
    case = next(c for c in CASES if c["id"] == "ambiguous_label")
    args = [str(FIXTURES / case["svg"]), str(FIXTURES / case["context"]), "--output-dir", str(tmp_path)]
    assert main(args) == 0
    assert not (tmp_path / "candidate.py").exists() and not (tmp_path / "model.json").exists()
    with pytest.raises(SystemExit) as error:
        main(args)
    assert error.value.code == 2


def test_html_withheld_result_is_not_a_positive_cad_preview_and_escapes_text():
    from research_notes.drawing_dimension_report import render_report
    source, context = inputs("ambiguous_label")
    inference = interpret_dimension_svg(source, context)
    inference["detail"] = '<img src=x onerror="alert(1)">'
    observation = {"id": "ambiguous_label", "trials": [{"status": "withheld"}], "passed": True,
                   "legacy_on_same_input": {"status": "withheld", "reason_code": "unsupported_svg"}}
    report = {"summary": {"candidate_successes": 0, "candidate_inputs": 0, "correct_withholds": 1,
                          "withheld_controls": 1, "false_confirmations": 0}, "observations": [observation]}
    html = render_report(report, {"ambiguous_label": {"source": source, "inference": inference}})
    assert "CADは生成していません" in html
    assert "<canvas" not in html and 'href="ambiguous_label/candidate.step"' not in html
    assert '&lt;img src=x' in html and '<img src=x' not in html
    class Resources(HTMLParser):
        options = []
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "script":
                assert "src" not in attrs
            if tag == "img":
                assert attrs["src"].startswith("data:image/svg+xml;base64,")
            if tag == "option":
                self.options.append(attrs.get("value"))
    parsed = Resources()
    parsed.feed(html)
    assert {"all", "top", "front", "right"} <= set(parsed.options)
