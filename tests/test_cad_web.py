"""Real HTTP controls for browser editing, atomic failures and STEP round trips."""
import http.client
import json
import math
from pathlib import Path
import threading

import pytest

from research_notes.cad_web import EditorServer
from research_notes.step_reconstruction import read_step_input


@pytest.fixture
def server():
    with EditorServer(0) as instance:
        worker = threading.Thread(target=instance.serve_forever, daemon=True)
        worker.start()
        try:
            yield instance
        finally:
            instance.shutdown()
            worker.join(timeout=5)


def call(server, path="/api/state", payload=None, *, method=None, headers=None, raw=None):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=30)
    values = {"X-CAD-Token": server.token, "Content-Type": "application/json"}
    if headers:
        values.update(headers)
    body = raw if raw is not None else json.dumps(payload).encode() if payload is not None else None
    try:
        connection.request(method or ("POST" if body is not None else "GET"), path, body=body, headers=values)
        response = connection.getresponse()
        content = response.read()
        return response.status, dict(response.getheaders()), json.loads(content) if response.getheader("Content-Type", "").startswith("application/json") else content
    finally:
        connection.close()


def act(server, operation, **payload):
    return call(server, "/api/" + operation,
                {"revision_token": server.editor.workspace.revision_token, **payload})


def select_hole(server):
    status, _, response = act(server, "demo")
    assert status == 200
    candidate = next(c for c in response["state"]["snapshot"]["candidates"] if c["explanation"] == "through_hole")
    status, _, response = act(server, "select", candidate_id=candidate["candidate_id"], confirm=True)
    assert status == 200
    return response["state"]


def radius(value):
    return {"node_id": "feature", "parameter": "radius", "value": value}


def test_screen_workflow_exports_reimportable_modified_shape(server, tmp_path):
    state = select_hole(server)
    assert state["snapshot"]["comparison"]["before"]["absolute_volume"] == pytest.approx(480 - 4 * math.pi)
    status, _, response = act(server, "edit", changes=[radius(1.3)])
    assert status == 200 and response["state"]["snapshot"]["transaction"]["draft_pending"]
    assert act(server, "export")[0] == 409
    assert act(server, "compare")[0] == 409
    assert act(server, "recompute")[2]["result"]["status"] == "committed"
    comparison = act(server, "compare")[2]["state"]["snapshot"]["comparison"]
    assert comparison["after"]["absolute_volume"] == pytest.approx(480 - 4 * math.pi * 1.3**2)
    status, headers, data = act(server, "export")
    assert status == 200 and headers["Content-Disposition"].startswith("attachment;")
    output = tmp_path / "edited.step"
    output.write_bytes(data)
    assert read_step_input(output).metrics.absolute_volume == pytest.approx(comparison["after"]["absolute_volume"])
    # Browser upload uses bytes and an untrusted label, never a user-supplied path.
    status, _, response = call(server, "/api/open", raw=data,
        headers={"X-File-Name": "../edited.step", "X-CAD-Revision": server.editor.workspace.revision_token})
    assert status == 200 and response["state"]["file_name"] == "edited.step"
    assert response["state"]["snapshot"]["comparison"]["before"]["absolute_volume"] == pytest.approx(comparison["after"]["absolute_volume"])


def test_failed_recompute_retains_geometry_and_can_recover(server):
    before = select_hole(server)["snapshot"]["comparison"]["after"]
    assert act(server, "edit", changes=[radius(30)])[0] == 200
    response = act(server, "recompute")[2]
    assert response["result"]["status"] == "aborted"
    assert response["state"]["snapshot"]["comparison"]["after"] == before
    assert any(node["diagnostic"] for node in response["state"]["snapshot"]["nodes"])
    assert act(server, "export")[0] == 409
    assert act(server, "rollback")[2]["state"]["snapshot"]["transaction"]["draft_pending"] is False
    assert act(server, "export")[0] == 200


def test_confirmation_revision_and_atomic_batch_guards(server):
    act(server, "demo")
    identifier = server.editor.snapshot["candidates"][0]["candidate_id"]
    assert act(server, "select", candidate_id=identifier, confirm=False)[2]["error"]["code"] == "confirmation_required"
    select_hole(server)
    before = call(server)[2]
    assert act(server, "edit", changes=[radius(1.3), {**radius(2), "parameter": "missing"}])[0] == 400
    assert call(server)[2] == before
    assert act(server, "edit", changes=[radius(1.3)], revision_token="stale")[0] == 409
    assert act(server, "export", revision_token="stale")[0] == 409
    assert call(server)[2] == before
    act(server, "edit", changes=[radius(1.3)])
    assert act(server, "recompute", revision_token=before["revision_token"])[0] == 409


@pytest.mark.parametrize("value", [True, None, "1.3", float("nan"), float("inf")])
def test_bad_dimensions_do_not_change_state(server, value):
    select_hole(server)
    before = call(server)[2]
    assert act(server, "edit", changes=[radius(value)])[0] == 400
    assert call(server)[2] == before


def test_failed_open_does_not_discard_selected_workspace(server):
    select_hole(server)
    before = call(server)[2]
    status, _, _ = call(server, "/api/open", raw=b"not STEP", headers={"X-CAD-Revision": before["revision_token"]})
    assert status == 400 and call(server)[2] == before
    # Reject the declared size before reading/allocating an oversized body.
    assert call(server, "/api/open", raw=b"", headers={"Content-Length": "2000001"})[0] == 413
    assert call(server)[2] == before


@pytest.mark.parametrize("headers", [
    {"X-CAD-Token": "invalid"}, {"Origin": "https://example.invalid"},
    {"Host": "evil.invalid"}, {"Sec-Fetch-Site": "cross-site"},
])
def test_untrusted_request_cannot_read_or_mutate_session(server, headers):
    before = call(server)[2]
    assert call(server, headers=headers)[0] == 403
    assert call(server, "/api/demo", payload={"revision_token": before["revision_token"]}, headers=headers)[0] == 403
    assert call(server)[2] == before


def test_local_assets_and_no_arbitrary_files(server):
    assert b"Research CAD" in call(server, "/")[2]
    assert b"__TOKEN__" not in call(server, "/")[2]
    assert call(server, "/editor.js")[0] == 200
    assert call(server, "/editor.css")[0] == 200
    assert call(server, "/../pyproject.toml")[0] == 404
    assert call(server, "/api/demo", raw=b"[]")[0] == 400
    assert call(server, "/api/demo", raw=b"{")[0] == 400


def test_snapshot_failure_is_atomic(server, monkeypatch):
    import research_notes.cad_web as module
    select_hole(server)
    before = call(server)[2]
    def fail(*args):
        raise RuntimeError("injected preview failure")
    monkeypatch.setattr(module, "workspace_snapshot", fail)
    assert act(server, "edit", changes=[radius(1.3)])[0] == 400
    assert call(server)[2] == before
    assert act(server, "demo")[0] == 400
    assert call(server)[2] == before


@pytest.fixture(scope="module")
def revision_sources():
    from research_notes.deterministic_recompute import single_feature_model, recompute
    from research_notes.parametric_features import PlateSpec, feature_spec
    from research_notes.step_writer_modes import prepare_step_write
    sources = []
    for radius_value in (1., 1.3):
        model = single_feature_model("upload_control", PlateSpec(),
                                     feature_spec("through_hole", x=6., y=5., radius=radius_value))
        source, _ = prepare_step_write(source=None, mode="reconstruct", shape=recompute(model).current_output().shape)
        sources.append(source)
    return sources


def revision_act(server, operation, **payload):
    return call(server, "/api/revisions/" + operation,
                {"revision_token": server.comparison.revision_token, **payload})


def revision_upload(server, side, data, **headers):
    return call(server, "/api/revisions/open/" + side, raw=data,
                headers={"X-CAD-Revision": server.comparison.revision_token, **headers})


def revision_state(server):
    return call(server, "/api/revisions/state")[2]


def test_two_independent_uploads_analytic_measurements_and_swap(server, revision_sources):
    before = revision_state(server)
    assert before["old"] is before["new"] is before["metrics_delta"] is None
    status, _, response = revision_upload(server, "new", revision_sources[1], **{"X-File-Name": "../new.step"})
    assert status == 200 and response["state"]["new"]["file_name"] == "new.step"
    assert response["state"]["old"] is response["state"]["metrics_delta"] is None
    new = response["state"]["new"]
    status, _, response = revision_upload(server, "old", revision_sources[0], **{"X-File-Name": "old.step"})
    assert status == 200
    state = response["state"]
    assert state["new"] == new and state["old"]["source_sha256"] != new["source_sha256"]
    for side, r in (("old", 1.), ("new", 1.3)):
        data = state[side]
        assert data["length_unit"] == "mm" and data["polygons"] and data["edges"]
        assert data["metrics"]["absolute_volume"] == pytest.approx(480 - 4 * math.pi * r**2)
        assert data["metrics"]["surface_area"] == pytest.approx(416 - 2 * math.pi * r**2 + 8 * math.pi * r)
    assert state["metrics_delta"]["absolute_volume"] == pytest.approx(-4 * math.pi * .69)
    assert state["metrics_delta"]["face_count"] == 0
    assert state["change_detection"] == "compared"
    assert state["coordinate_policy"] == "source_coordinates_no_alignment"
    swapped = revision_act(server, "swap")[2]["state"]
    assert swapped["old"] == state["new"] and swapped["new"] == state["old"]
    assert swapped["metrics_delta"]["absolute_volume"] == pytest.approx(-state["metrics_delta"]["absolute_volume"])
    cleared = revision_act(server, "clear", side="old")[2]["state"]
    assert cleared["old"] is cleared["metrics_delta"] is None and cleared["new"] == swapped["new"]
    assert revision_act(server, "swap")[0] == 400


def test_revision_upload_and_editing_are_isolated(server, revision_sources):
    select_hole(server)
    act(server, "edit", changes=[radius(1.6)])
    editor_before = call(server)[2]
    assert revision_upload(server, "old", revision_sources[0])[0] == 200
    assert revision_upload(server, "new", revision_sources[1])[0] == 200
    comparison_before = revision_state(server)
    assert call(server)[2] == editor_before
    assert act(server, "recompute")[0] == 200
    assert act(server, "demo")[0] == 200
    assert revision_state(server) == comparison_before


def test_revision_stale_requests_and_failed_upload_preserve_both_slots(server, revision_sources):
    assert revision_act(server, "demo")[0] == 200
    before = revision_state(server)
    assert revision_upload(server, "old", b"not STEP")[0] == 400
    assert revision_upload(server, "new", b"")[0] == 400
    assert revision_upload(server, "other", revision_sources[0])[0] == 400
    assert revision_upload(server, "new", revision_sources[1], **{"X-CAD-Revision": "stale"})[0] == 409
    for operation in ("demo", "swap", "clear"):
        assert revision_act(server, operation, side="old", revision_token="stale")[0] == 409
    assert revision_state(server) == before
    assert revision_upload(server, "old", revision_sources[1])[0] == 200
    assert revision_upload(server, "new", revision_sources[0], **{"X-CAD-Revision": before["revision_token"]})[0] == 409
    assert revision_state(server)["new"] == before["new"]


def test_comparison_preview_and_pair_demo_publish_atomically(server, revision_sources, monkeypatch):
    import research_notes.cad_revision as module
    revision_act(server, "demo")
    before = revision_state(server)
    original = module.shape_snapshot
    calls = 0
    def fail_second(workspace):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected second preview failure")
        return original(workspace)
    monkeypatch.setattr(module, "shape_snapshot", fail_second)
    assert revision_act(server, "demo")[0] == 400
    assert revision_state(server) == before
    calls = 1
    assert revision_upload(server, "new", revision_sources[1])[0] == 400
    assert revision_state(server) == before


def test_comparison_units_and_request_budget(server, revision_sources):
    revision_upload(server, "old", revision_sources[0])
    before = revision_state(server)
    assert b".MILLI.,.METRE." in revision_sources[0]
    non_mm = revision_sources[0].replace(b".MILLI.,.METRE.", b"$,.METRE.")
    status, _, response = revision_upload(server, "new", non_mm)
    assert status == 400 and "millimetre" in response["error"]["detail"]
    assert revision_upload(server, "new", b"", **{"Content-Length": "2000001"})[0] == 413
    assert revision_state(server) == before


@pytest.mark.parametrize("headers", [
    {"X-CAD-Token": "invalid"}, {"Origin": "https://example.invalid"},
    {"Host": "evil.invalid"}, {"Sec-Fetch-Site": "cross-site"},
])
def test_comparison_enforces_local_request_guards(server, revision_sources, headers):
    before = revision_state(server)
    assert call(server, "/api/revisions/state", headers=headers)[0] == 403
    assert revision_upload(server, "old", revision_sources[0], **headers)[0] == 403
    assert revision_state(server) == before


def test_comparison_assets_and_malformed_actions(server):
    status, _, page = call(server, "/revisions")
    assert status == 200 and b"__TOKEN__" not in page and b"1.7.0" in page
    for asset in ("revisions.js", "revisions.css"):
        assert call(server, "/" + asset)[0] == 200
    before = revision_state(server)
    for raw in (b"[]", b"{", b"null"):
        assert call(server, "/api/revisions/demo", raw=raw)[0] == 400
    assert revision_act(server, "unknown")[0] == 400
    assert revision_act(server, "clear", side="unknown")[0] == 400
    assert revision_state(server) == before


def test_comparison_keeps_source_coordinates_without_assuming_shape_equality(server, revision_sources):
    from research_notes.deterministic_recompute import single_feature_model, recompute
    from research_notes.parametric_features import PlateSpec, feature_spec
    from research_notes.step_writer_modes import prepare_step_write
    model = single_feature_model("translated", PlateSpec(origin_x=30.),
                                 feature_spec("through_hole", x=6., y=5., radius=1.))
    shifted, _ = prepare_step_write(source=None, mode="reconstruct", shape=recompute(model).current_output().shape)
    revision_upload(server, "old", revision_sources[0])
    assert revision_upload(server, "new", shifted)[0] == 200
    state = revision_state(server)
    assert state["metrics_delta"]["absolute_volume"] == pytest.approx(0., abs=1e-8)
    assert state["new"]["metrics"]["bounds_min"][0] - state["old"]["metrics"]["bounds_min"][0] == pytest.approx(30.)
    assert min(p[0] for poly in state["new"]["polygons"] for p in poly) == pytest.approx(30.)
    assert state["change_detection"] == "unresolved"


def test_comparison_reads_sphere_without_editable_candidate(server):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeSphere
    from research_notes.step_writer_modes import prepare_step_write
    source, _ = prepare_step_write(source=None, mode="reconstruct", shape=BRepPrimAPI_MakeSphere(3.).Shape())
    status, _, response = revision_upload(server, "old", source)
    assert status == 200
    assert response["state"]["old"]["metrics"]["absolute_volume"] == pytest.approx(36 * math.pi)
    assert response["state"]["old"]["faces"][0]["support"] == "sphere"
    assert server.editor.workspace._transaction is None


def test_revision_report_http_download_is_guarded_and_preserves_state(server):
    assert revision_act(server, "report")[0] == 400
    revision_act(server, "demo", case="position")
    before = revision_state(server)
    status, headers, report = revision_act(server, "report", camera={"yaw": 1.2, "pitch": -.7, "zoom": 1.5, "edges": True})
    assert status == 200 and headers["Content-Type"].startswith("text/html")
    assert headers["Content-Disposition"] == 'attachment; filename="step-comparison.html"'
    assert "穴中心X" in report.decode() and report.count(b"<svg ") == 2
    assert server.token.encode() not in report and b"/api/" not in report
    assert revision_state(server) == before
    revision_act(server, "swap")
    assert revision_act(server, "report", revision_token=before["revision_token"])[0] == 409


@pytest.mark.parametrize("camera", [None, [], {"zoom": 50}, {"yaw": True}, {"pitch": float("nan")},
                                     {"yaw": float("inf")}, {"edges": "true"}])
def test_report_camera_rejects_invalid_values_without_changing_pair(server, camera):
    revision_act(server, "demo")
    before = revision_state(server)
    assert revision_act(server, "report", camera=camera)[0] == 400
    assert revision_state(server) == before


def test_comparison_failure_does_not_publish_new_slot_or_result(server, revision_sources, monkeypatch):
    import research_notes.cad_revision as module
    revision_act(server, "demo")
    before = revision_state(server)
    def fail(*args):
        raise RuntimeError("injected matching failure")
    monkeypatch.setattr(module, "compare_revisions", fail)
    assert revision_upload(server, "new", revision_sources[0])[0] == 400
    assert revision_act(server, "swap")[0] == 400
    assert revision_act(server, "clear", side="old")[0] == 400
    assert revision_state(server) == before


@pytest.mark.parametrize("case,expected", [("diameter", "compared"), ("position", "compared"),
    ("thickness", "compared"), ("addition", "compared"), ("deletion", "compared"), ("ambiguous", "partial")])
def test_all_comparison_demos_are_reimported_and_analyzed(server, case, expected):
    status, _, response = revision_act(server, "demo", case=case)
    assert status == 200 and response["state"]["analysis"]["status"] == expected
    assert response["state"]["old"]["features"]["status"] == "qualified"
    assert response["state"]["new"]["features"]["status"] == "qualified"
