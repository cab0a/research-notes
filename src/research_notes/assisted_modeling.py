"""Bounded import, explicit selection, edit, recompute, comparison, and export."""

from __future__ import annotations

import hashlib
import html
import json
from dataclasses import asdict, replace
from pathlib import Path

from research_notes.brep_preview import write_shape_previews
from research_notes.brep_runtime import step_round_trip
from research_notes.deterministic_recompute import (
    FeatureModel, RecomputeResult, edit_parameter, model_fingerprint, recompute, recompute_record,
)
from research_notes.step_reconstruction import (
    FIT_TOLERANCE, ReconstructionResult, compare_shapes, reconstruct_step, reconstruction_record,
)


class ConfirmationRequired(ValueError):
    """The caller must explicitly choose and confirm a reconstruction proposal."""


class ModelingSession:
    """An in-memory research workspace; every new import clears prior selection."""

    def __init__(self) -> None:
        self.source_path: Path | None = None
        self.inspection: ReconstructionResult | None = None
        self.model: FeatureModel | None = None
        self.result: RecomputeResult | None = None
        self.selected_candidate_id: str | None = None
        self.selected_shape: object | None = None

    def open_step(self, path: Path) -> dict:
        path = Path(path).resolve()
        inspection = reconstruct_step(path)
        # Failed imports leave the existing session intact.
        self.source_path, self.inspection = path, inspection
        self.model = self.result = self.selected_shape = None
        self.selected_candidate_id = None
        return self.inspect()

    def inspect(self) -> dict:
        if self.inspection is None:
            raise ValueError("open a STEP file first")
        return reconstruction_record(self.inspection)

    def select_candidate(self, candidate_id: str, *, confirm: bool = False) -> RecomputeResult:
        if self.inspection is None:
            raise ValueError("open a STEP file first")
        candidate = next((c for c in self.inspection.candidates if c.candidate_id == candidate_id), None)
        if candidate is None:
            raise ValueError("unknown candidate ID")
        if confirm is not True:
            raise ConfirmationRequired("selection replaces the active model with an inferred proposal; explicit confirmation is required")
        model = replace(candidate.model, provenance="user_selected_reconstruction")
        result = recompute(model)
        selected = result.current_output()
        self.model, self.result = model, result
        self.selected_shape, self.selected_candidate_id = selected.shape, candidate_id
        return result

    def edit(self, node_id: str, parameter: str, value: float) -> FeatureModel:
        if self.model is None:
            raise ValueError("select and confirm a candidate before editing")
        self.model = edit_parameter(self.model, node_id, parameter, float(value))
        return self.model

    def recompute(self) -> RecomputeResult:
        if self.model is None:
            raise ValueError("select and confirm a candidate before recomputing")
        self.result = recompute(self.model, self.result)
        return self.result

    def _current_output(self):
        if self.model is None or self.result is None:
            raise ValueError("no confirmed model is available")
        if model_fingerprint(self.model) != self.result.model_fingerprint:
            raise ValueError("dimensions changed; recompute before comparison or export")
        return self.result.current_output()

    def status(self) -> dict:
        return {"source_file": self.inspection.imported.file_name if self.inspection else None,
                "source_sha256": self.inspection.imported.source_sha256 if self.inspection else None,
                "selected_candidate_id": self.selected_candidate_id,
                "model": asdict(self.model) if self.model else None,
                "recompute_required": bool(self.model and (not self.result or model_fingerprint(self.model) != self.result.model_fingerprint)),
                "recompute": recompute_record(self.result) if self.result else None,
                "authoring_history_recovered": False}

    def compare(self) -> dict:
        current = self._current_output()
        source = self.inspection.imported
        return {"source_sha256": source.source_sha256, "model_revision": self.model.revision,
                "selected_candidate_id": self.selected_candidate_id,
                "before": asdict(source.metrics), "after": asdict(current.metrics),
                "volume_change": current.metrics.absolute_volume - source.metrics.absolute_volume,
                "surface_area_change": current.metrics.surface_area - source.metrics.surface_area,
                "comparison": compare_shapes(source.shape, current.shape),
                "authoring_history_recovered": False}

    def write_comparison(self, directory: Path) -> dict:
        report = self.compare()
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        write_shape_previews(directory / "comparison.png", (
            ("Imported STEP", self.inspection.imported.shape),
            ("Confirmed proposal", self.selected_shape),
            (f"Current revision {self.model.revision}", self._current_output().shape),
        ), title="Imported, selected, and edited shapes", columns=3)
        (directory / "comparison.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (directory / "session.json").write_text(json.dumps(self.status(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        rows = "".join(f"<tr><th>{html.escape(label)}</th><td>{report['before'][field]:.6f}</td><td>{report['after'][field]:.6f}</td></tr>"
                       for label, field in (("Volume (mm³)", "absolute_volume"), ("Area (mm²)", "surface_area"), ("Faces", "face_count")))
        page = f"""<!doctype html><html lang="en"><meta charset="utf-8">
<title>Modeling comparison</title><style>body{{font:16px system-ui;margin:32px;max-width:1200px;color:#203246}}table{{border-collapse:collapse}}th,td{{padding:12px;border:1px solid #ccd5df}}img{{width:100%}}</style>
<h1>Imported and edited shape</h1><p>Selected proposal: {html.escape(self.selected_candidate_id)}</p>
<table><tr><th>Measurement</th><th>Imported</th><th>Edited</th></tr>{rows}</table>
<img src="comparison.png" alt="Imported STEP, confirmed reconstruction, and current edited shape">
<p>The selected construction is a confirmed reconstruction proposal. Original CAD authoring history has not been recovered.</p>
<p><a href="comparison.json">Measurements</a> · <a href="session.json">Model and recompute state</a></p></html>"""
        (directory / "comparison.html").write_text(page, encoding="utf-8")
        return report

    def export_step(self, path: Path, *, overwrite: bool = False) -> dict:
        current = self._current_output()
        path = Path(path).resolve()
        if path.suffix.lower() not in {".step", ".stp"}:
            raise ValueError("export path must end with .step or .stp")
        if path == self.source_path or (path.exists() and self.source_path.exists() and path.samefile(self.source_path)):
            raise ValueError("the imported source file is read-only; choose another export path")
        if path.exists() and not overwrite:
            raise FileExistsError("export exists; explicit overwrite is required")
        fixture = step_round_trip(current.shape, "assisted_model", writer_uncertainty=1e-7)
        verification = compare_shapes(current.shape, fixture.imported_shape)
        errors = [verification[name] for name in ("volume_residual", "area_residual", "material_difference_volume", "bounds_residual")]
        if fixture.transferred_roots != 1 or not verification["topology_matches"] or not verification["surface_inventory_matches"] or any(v > FIT_TOLERANCE for v in errors):
            raise RuntimeError("STEP export round-trip failed the declared geometry contract")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb" if overwrite else "xb") as stream:
            stream.write(fixture.source_bytes)
        return {"file_name": path.name, "sha256": hashlib.sha256(fixture.source_bytes).hexdigest(),
                "source_sha256": self.inspection.imported.source_sha256,
                "model_fingerprint": self.result.model_fingerprint, "model_revision": self.model.revision,
                "selected_candidate_id": self.selected_candidate_id, "selection_confirmed": True,
                "preservation_policy": "shape_geometry_only; names, colors, PMI, and constraints are not carried over",
                "round_trip": verification, "authoring_history_recovered": False}
