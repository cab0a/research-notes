"""Independent, read-only STEP slots for the local revision comparison screen."""
from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import secrets
import tempfile

from research_notes.cad_api import CadAPIError
from research_notes.diagnostic_workspace import shape_snapshot
from research_notes.step_reconstruction import read_step_input

MAX_SOURCE_BYTES = 2_000_000
METRIC_KEYS = ("absolute_volume", "surface_area", "face_count", "edge_count",
               "vertex_count", "shell_count", "solid_count")


class RevisionComparison:
    """Publish complete snapshots only; never reuse the editor's selected model."""

    def __init__(self):
        self.slots = {"old": None, "new": None}
        self.revision_token = secrets.token_urlsafe(24)

    def state(self):
        old, new = self.slots["old"], self.slots["new"]
        delta = {key: new["metrics"][key] - old["metrics"][key] for key in METRIC_KEYS} if old and new else None
        return {"comparison_version": "1.2.0", "revision_token": self.revision_token,
                **self.slots, "metrics_delta": delta,
                "coordinate_policy": "source_coordinates_no_alignment",
                "change_detection": "not_performed"}

    def guard(self, token):
        if token != self.revision_token:
            raise CadAPIError("revision_conflict", "別の画面で比較データが変わりました。最新の状態を確認してください。")

    @staticmethod
    def load(source, file_name):
        if not source or len(source) > MAX_SOURCE_BYTES:
            raise CadAPIError("resource_limit", "STEPは空でない2 MB以下のファイルを選択してください。")
        file_name = file_name.replace("\\", "/").rsplit("/", 1)[-1][:200] or "uploaded.step"
        with tempfile.TemporaryDirectory(prefix="research-cad-comparison-") as directory:
            path = Path(directory) / "source.step"
            path.write_bytes(source)
            imported = read_step_input(path)
            preview = shape_snapshot(imported.shape)
            record = {"file_name": file_name, "source_sha256": imported.source_sha256,
                      "source_bytes": len(source), "length_unit": imported.unit,
                      "metrics": asdict(imported.metrics),
                      **preview}
            # Check the complete HTTP payload before replacing either slot.
            json.dumps(record, allow_nan=False)
            return record

    def open_bytes(self, side, source, file_name, token):
        self.guard(token)
        if side not in self.slots:
            raise CadAPIError("invalid_request", "旧版または新版を指定してください。")
        record = self.load(source, file_name)
        self.slots = {**self.slots, side: record}
        self.revision_token = secrets.token_urlsafe(24)
        return {"status": "loaded", "side": side}

    def action(self, operation, payload):
        self.guard(payload.get("revision_token"))
        if operation == "demo":
            from research_notes.deterministic_recompute import single_feature_model, recompute
            from research_notes.parametric_features import PlateSpec, feature_spec
            from research_notes.step_writer_modes import prepare_step_write
            slots = {}
            for side, radius in (("old", 1.), ("new", 1.3)):
                model = single_feature_model("revision_demo", PlateSpec(),
                                             feature_spec("through_hole", x=6., y=5., radius=radius))
                source, _ = prepare_step_write(source=None, mode="reconstruct",
                                               shape=recompute(model).current_output().shape)
                slots[side] = self.load(source, f"plate-{side}.step")
        elif operation == "swap":
            if not all(self.slots.values()):
                raise CadAPIError("invalid_request", "旧版と新版の両方を開いてください。")
            slots = {"old": self.slots["new"], "new": self.slots["old"]}
        elif operation == "clear":
            side = payload.get("side")
            if side not in self.slots:
                raise CadAPIError("invalid_request", "旧版または新版を指定してください。")
            slots = {**self.slots, side: None}
        else:
            raise CadAPIError("invalid_request", "Unknown comparison operation")
        self.slots = slots
        self.revision_token = secrets.token_urlsafe(24)
        return {"status": "ok", "operation": operation}
