"""Local browser editor for the bounded CAD API (one workspace per server)."""
from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
import secrets
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

from research_notes.cad_api import CadAPIError, CadWorkspace
from research_notes.cad_revision import RevisionComparison
from research_notes.diagnostic_workspace import PAGE, workspace_snapshot

MAX_SOURCE_BYTES = 2_000_000
ASSETS = Path(__file__).with_name("cad_editor")


def fork_workspace(workspace):
    """Copy mutable session containers; feature models and native caches stay immutable."""
    candidate = copy.copy(workspace)
    candidate._session = copy.copy(workspace._session)
    if workspace._transaction:
        candidate._transaction = copy.copy(workspace._transaction)
        candidate._transaction.checkpoints = dict(workspace._transaction.checkpoints)
    return candidate


class BrowserEditor:
    def __init__(self):
        self.workspace = CadWorkspace()
        self.snapshot = self.original = None
        self.file_name = None
        self.storage = tempfile.TemporaryDirectory(prefix="research-cad-")
        self.acquisition = None

    def close(self):
        if self.acquisition:
            self.acquisition.cleanup()
        self.storage.cleanup()

    def state(self):
        return {"editor_version": "1.7.0", "revision_token": self.workspace.revision_token,
                "file_name": self.file_name, "snapshot": self.snapshot, "original": self.original}

    def guard(self, token):
        if token != self.workspace.revision_token:
            raise CadAPIError("revision_conflict", "別の画面で状態が変わりました。最新の状態を確認して操作してください。")

    def open_bytes(self, source, file_name, token):
        self.guard(token)
        if not source or len(source) > MAX_SOURCE_BYTES:
            raise CadAPIError("resource_limit", "STEPは空でない2 MB以下のファイルを選択してください。")
        # Browser filenames are labels, never filesystem paths.
        file_name = file_name.replace("\\", "/").rsplit("/", 1)[-1][:200] or "uploaded.step"
        incoming = tempfile.TemporaryDirectory(dir=self.storage.name)
        try:
            path = Path(incoming.name) / "source.step"
            path.write_bytes(source)
            candidate = fork_workspace(self.workspace)
            result = candidate.open_step(path, mode="reconstruct")
            snapshot = workspace_snapshot(candidate)
            snapshot["file_name"] = file_name
        except Exception:
            incoming.cleanup()
            raise
        old = self.acquisition
        self.workspace, self.snapshot = candidate, snapshot
        self.original = {key: snapshot[key] for key in ("polygons", "polygon_face_ids", "faces", "edges")}
        self.file_name, self.acquisition = file_name, incoming
        if old:
            old.cleanup()
        return result

    def demo(self, token):
        self.guard(token)
        from research_notes.deterministic_recompute import single_feature_model, recompute
        from research_notes.parametric_features import PlateSpec, feature_spec
        from research_notes.step_writer_modes import prepare_step_write
        model = single_feature_model("browser_demo", PlateSpec(),
                                     feature_spec("through_hole", x=6., y=5., radius=1.))
        source, _ = prepare_step_write(source=None, mode="reconstruct",
                                      shape=recompute(model).current_output().shape)
        return self.open_bytes(source, "through_hole.step", token)

    def action(self, operation, payload):
        self.guard(payload.get("revision_token"))
        if operation == "demo":
            return self.demo(payload["revision_token"])
        candidate = fork_workspace(self.workspace)
        token = lambda: candidate.revision_token
        if operation == "select":
            result = candidate.select(payload.get("candidate_id"), confirm=payload.get("confirm"),
                                      expected_revision=token())
        elif operation == "edit":
            changes = payload.get("changes")
            if not isinstance(changes, list) or not 1 <= len(changes) <= 256:
                raise CadAPIError("invalid_request", "変更する寸法を指定してください。")
            for change in changes:
                if not isinstance(change, dict):
                    raise CadAPIError("invalid_request", "寸法の指定が不正です。")
                value = change.get("value")
                if type(value) not in (int, float) or not math.isfinite(value):
                    raise CadAPIError("invalid_request", "寸法には有限の数値を入力してください。")
                result = candidate.edit(change.get("node_id"), change.get("parameter"), value,
                                        expected_revision=token())
        elif operation == "recompute":
            result = candidate.recompute(expected_revision=token())
        elif operation == "rollback":
            result = candidate.rollback(expected_revision=token())
        elif operation == "compare":
            result = candidate.compare()
        else:
            raise CadAPIError("invalid_request", "Unknown editor operation")
        # A failed batch or preview cannot publish a partially modified session.
        snapshot = workspace_snapshot(candidate)
        snapshot["file_name"] = self.file_name
        self.workspace, self.snapshot = candidate, snapshot
        return result

    def export(self, token):
        self.guard(token)
        with tempfile.TemporaryDirectory(dir=self.storage.name) as directory:
            path = Path(directory) / "edited.step"
            self.workspace.export_step(path, mode="reconstruct")
            return path.read_bytes()


class EditorServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port=8767):
        # This is a local single-user tool, not a remotely exposed web service.
        super().__init__(("127.0.0.1", port), EditorHandler)
        self.editor = BrowserEditor()
        self.comparison = RevisionComparison()
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.RLock()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server_port}"

    def server_close(self):
        super().server_close()
        with self.lock:
            self.editor.close()


class EditorHandler(BaseHTTPRequestHandler):
    server_version = "ResearchCAD/1.7"

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, *_):
        pass

    def send(self, code, data, content_type="application/json; charset=utf-8", *, download=False):
        if isinstance(data, dict):
            data = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
        elif isinstance(data, str):
            data = data.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        if download:
            filename = "edited.step" if download is True else download
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(data)

    def guard_request(self, *, authenticated=False):
        authorities = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        host = self.headers.get("Host")
        origin = self.headers.get("Origin")
        if (host not in authorities or origin is not None and origin != f"http://{host}"
                or self.headers.get("Sec-Fetch-Site") == "cross-site"):
            self.send(403, {"error": {"code": "forbidden", "detail": "Local same-origin requests only"}})
            return False
        if authenticated and not secrets.compare_digest(self.headers.get("X-CAD-Token", ""), self.server.token):
            self.send(403, {"error": {"code": "forbidden", "detail": "Editor session token required"}})
            return False
        return True

    def do_GET(self):
        path = urlsplit(self.path).path
        if not self.guard_request(authenticated=path.startswith("/api/")):
            return
        with self.server.lock:
            if path in ("/", "/revisions"):
                page = (ASSETS / ("index.html" if path == "/" else "revisions.html")).read_text(encoding="utf-8")
                self.send(200, page.replace("__TOKEN__", self.server.token), "text/html; charset=utf-8")
            elif path in ("/editor.js", "/editor.css", "/revisions.js", "/revisions.css"):
                self.send(200, (ASSETS / path[1:]).read_bytes(),
                          "text/javascript; charset=utf-8" if path.endswith(".js") else "text/css; charset=utf-8")
            elif path == "/api/state":
                self.send(200, self.server.editor.state())
            elif path == "/api/revisions/state":
                self.send(200, self.server.comparison.state())
            elif path in ("/diagnostics", "/workspace.json") and self.server.editor.snapshot:
                data = self.server.editor.snapshot
                if path.endswith(".json"):
                    self.send(200, data)
                else:
                    encoded = json.dumps(data, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c").replace("&", "\\u0026")
                    self.send(200, PAGE.replace("__DATA__", encoded), "text/html; charset=utf-8")
            else:
                self.send(404, {"error": {"code": "not_found", "detail": "Not found"}})

    def do_POST(self):
        self.close_connection = True
        if not self.guard_request(authenticated=True):
            return
        path = urlsplit(self.path).path
        revision_route = path.startswith("/api/revisions/")
        upload = path == "/api/open" or path.startswith("/api/revisions/open/")
        limit = MAX_SOURCE_BYTES if upload else 65_536
        try:
            length = int(self.headers.get("Content-Length", "-1"))
            if self.headers.get("Transfer-Encoding") or length < 0:
                raise CadAPIError("invalid_request", "A fixed Content-Length is required")
            if length > limit:
                self.send(413, {"error": {"code": "resource_limit", "detail": "Request body exceeds the editor budget"}})
                return
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise CadAPIError("invalid_request", "Incomplete request body")
            with self.server.lock:
                editor = self.server.editor
                if revision_route:
                    comparison = self.server.comparison
                    if upload:
                        result = comparison.open_bytes(path.removeprefix("/api/revisions/open/"), raw,
                            unquote(self.headers.get("X-File-Name", "uploaded.step")), self.headers.get("X-CAD-Revision"))
                    else:
                        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                            raise CadAPIError("invalid_request", "JSON request required")
                        payload = json.loads(raw)
                        if not isinstance(payload, dict):
                            raise CadAPIError("invalid_request", "JSON object required")
                        if path == "/api/revisions/report":
                            self.send(200, comparison.report(payload), "text/html; charset=utf-8", download="step-comparison.html")
                            return
                        result = comparison.action(path.removeprefix("/api/revisions/"), payload)
                    self.send(200, {"result": result, "state": comparison.state()})
                    return
                elif path == "/api/open":
                    result = editor.open_bytes(raw, unquote(self.headers.get("X-File-Name", "uploaded.step")),
                                               self.headers.get("X-CAD-Revision"))
                else:
                    if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                        raise CadAPIError("invalid_request", "JSON request required")
                    payload = json.loads(raw)
                    if not isinstance(payload, dict):
                        raise CadAPIError("invalid_request", "JSON object required")
                    if path == "/api/export":
                        self.send(200, editor.export(payload.get("revision_token")), "application/step", download=True)
                        return
                    if not path.startswith("/api/"):
                        raise CadAPIError("invalid_request", "Unknown route")
                    result = editor.action(path.removeprefix("/api/"), payload)
                self.send(200, {"result": result.record(), "state": editor.state()})
        except (CadAPIError, ValueError, TypeError, KeyError, OSError, RuntimeError) as error:
            error = error if isinstance(error, CadAPIError) else CadAPIError("invalid_request", str(error))
            with self.server.lock:
                self.send(409 if error.code in {"revision_conflict", "pending_changes"} else 400,
                          {"error": error.record(), "state": (self.server.comparison if revision_route else self.server.editor).state()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8767, help="loopback port (default: 8767; 0 chooses a free port)")
    parser.add_argument("--open-browser", action="store_true")
    args = parser.parse_args()
    with EditorServer(args.port) as server:
        print(f"Research CAD v1.7.0: {server.url} (Ctrl+C to stop)", flush=True)
        print(f"STEP revision comparison: {server.url}/revisions", flush=True)
        if args.open_browser:
            import webbrowser
            webbrowser.open(server.url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
