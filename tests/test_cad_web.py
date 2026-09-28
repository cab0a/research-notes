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
