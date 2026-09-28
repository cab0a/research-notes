"""Reproducible evidence for the bounded v0.57.0 through v0.60.0 workflow."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import tempfile
from dataclasses import asdict, replace
from pathlib import Path

from research_notes.brep_preview import write_shape_previews
from research_notes.brep_runtime import step_round_trip, topology_counts
from research_notes.deterministic_recompute import (
    FeatureModel, ModelNode, edit_parameter, recompute, recompute_record,
    single_feature_model, validate_model,
)
from research_notes.modeling_common import measure_shape
from research_notes.parametric_features import (
    PlateSpec, analytic_feature_truth, apply_feature, boolean_shape, build_plate,
    feature_controls, feature_spec,
)


def rounded(value):
    if isinstance(value, float):
        return round(value, 9) + 0.0
    if isinstance(value, dict):
        return {key: rounded(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [rounded(item) for item in value]
    return value


def json_bytes(value: object) -> bytes:
    return (json.dumps(rounded(value), indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def csv_bytes(rows: list[dict]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=tuple(rows[0]), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: f"{round(value, 9) + 0.0:.9f}" if isinstance(value, float) else
                         int(value) if isinstance(value, bool) else value for key, value in row.items()})
    return stream.getvalue().encode()


def handle_fixtures(directory: Path, payloads: dict[str, bytes], *, refresh: bool, generator: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    payloads = dict(payloads)
    payloads["manifest.csv"] = csv_bytes([
        {"file_name": name, "byte_length": len(payload), "sha256": hashlib.sha256(payload).hexdigest(), "generator": generator}
        for name, payload in sorted(payloads.items())
    ])
    if set(p.name for p in directory.iterdir()) - payloads.keys():
        raise RuntimeError(f"unexpected files in {directory}")
    for name, payload in payloads.items():
        path = directory / name
        if refresh:
            path.write_bytes(payload)
        elif not path.exists() or path.read_bytes() != payload:
            raise RuntimeError(f"fixture differs; use --refresh-fixtures: {path}")


def _contract(output: Path, name: str, version: str, rows: list[dict], boundaries: list[str], **extra) -> None:
    output.mkdir(parents=True, exist_ok=True)
    passed = all(bool(row["checks_pass"]) for row in rows)
    payload = {"contract_version": "1.0.0", "study_version": version,
               "all_checks_pass": passed, "observation_count": len(rows),
               "numeric_serialization": "9 decimal places; checks use unrounded values",
               "claim_boundaries": boundaries, **extra}
    (output / f"{name}_contract.json").write_bytes(json_bytes(payload))
    if not passed:
        raise RuntimeError(f"{version} control failed; inspect observations")


def run_parametric_features(output: Path, fixtures: Path, *, refresh: bool = False) -> list[dict]:
    output.mkdir(parents=True, exist_ok=True)
    rows, payloads, previews = [], {}, []
    for name, plate, feature in feature_controls():
        built = apply_feature(build_plate(plate).shape, plate, feature)
        expected_volume, expected_area = analytic_feature_truth(plate, feature)
        fixture = step_round_trip(built.shape, name, writer_uncertainty=1e-7)
        payloads[fixture.file_name] = fixture.source_bytes
        topology_match = topology_counts(built.shape) == topology_counts(fixture.imported_shape)
        for stage, shape in (("constructed", built.shape), ("step_imported", fixture.imported_shape)):
            metrics = measure_shape(shape)
            volume_error, area_error = abs(metrics.absolute_volume - expected_volume), abs(metrics.surface_area - expected_area)
            rows.append({"control_id": name, "stage": stage, "operation": feature.kind,
                         "parameters_json": json.dumps(dict(feature.parameters), sort_keys=True),
                         "expected_volume": expected_volume, "volume": metrics.absolute_volume,
                         "expected_area": expected_area, "surface_area": metrics.surface_area,
                         "volume_error": volume_error, "area_error": area_error,
                         "face_count": metrics.face_count, "edge_count": metrics.edge_count,
                         "analyzer_valid": metrics.analyzer_valid, "sketch_state": built.sketch.status,
                         "sketch_fingerprint": built.sketch.input_sha256, "topology_round_trip_matches": topology_match,
                         "source_sha256": fixture.source_sha256,
                         "checks_pass": metrics.analyzer_valid and metrics.solid_count == 1 and topology_match
                         and volume_error < 1e-7 and area_error < 1e-7 and built.sketch.status == "fully_constrained"})
        previews.append((name.replace("_", " "), fixture.imported_shape))
    rejected = []
    for name, feature in (
        ("touching_outer_boundary", feature_spec("through_hole", x=1., y=5., radius=1.)),
        ("oversized_radius", feature_spec("through_hole", x=4., y=5., radius=8.)),
        ("blind_floor_removed", feature_spec("blind_hole", x=4., y=5., radius=1., depth=4.)),
        ("negative_boss_height", feature_spec("boss", x=4., y=5., radius=1., height=-1.)),
        ("rib_outside_plate", feature_spec("rib", x=10., y=3., width=3., length=5., height=2.)),
    ):
        try:
            apply_feature(build_plate(PlateSpec()).shape, PlateSpec(), feature)
            reason, passed = "unexpected_accept", False
        except ValueError as exc:
            reason, passed = str(exc), True
        rejected.append({"control_id": name, "decision": "reject" if passed else "accept", "reason": reason, "checks_pass": passed})
    payloads["parameters.json"] = json_bytes([{"control_id": name, "plate": asdict(plate), "feature": asdict(feature)} for name, plate, feature in feature_controls()])
    handle_fixtures(fixtures, payloads, refresh=refresh, generator="experiments/run_parametric_features.py")
    (output / "parametric_features.csv").write_bytes(csv_bytes(rows))
    (output / "parametric_feature_rejections.csv").write_bytes(csv_bytes(rejected))
    write_shape_previews(output / "parametric_features.png", tuple(previews[::2] + previews[1::2]),
                         title="Parameter-driven features: before (top) and after (bottom)", columns=5)
    _contract(output, "parametric_features", "v0.57.0", rows + rejected, [
        "five feature families on one axis-aligned plate; no arbitrary placement or interacting-feature guarantee",
        "plate and tool profiles use the v0.56.0 sketch solver; coordinates are checkpointed at 12 decimal places",
        "closed-form truth applies to one isolated interior feature; Boolean operations use one pinned OCCT route",
        "STEP preserves the tested geometry and topology counts, not sketch constraints or authoring history",
    ], shape_count=10, stage_observation_count=20, rejection_count=5)
    return rows


def branching_model() -> FeatureModel:
    model = single_feature_model("branching_plate", PlateSpec(), feature_spec("through_hole", x=3., y=3., radius=1.))
    nodes = list(model.nodes[:-1])
    nodes.extend((
        ModelNode("boss", "boss", ("feature",), feature_spec("boss", x=9., y=7., radius=1., height=2.).parameters),
        ModelNode("result", "result", ("boss",)),
        ModelNode("spare_rib", "rib", ("base",), feature_spec("rib", x=3., y=3., width=1., length=5., height=2.).parameters),
        ModelNode("spare_result", "result", ("spare_rib",)),
    ))
    return replace(model, nodes=tuple(nodes))


def run_deterministic_recompute(output: Path, fixtures: Path, *, refresh: bool = False) -> list[dict]:
    output.mkdir(parents=True, exist_ok=True)
    initial = branching_model()
    edited = edit_parameter(initial, "feature", "radius", 1.5)
    invalid = edit_parameter(edited, "feature", "radius", 30.0)
    recovered = edit_parameter(invalid, "feature", "radius", 1.5)
    resized = edit_parameter(recovered, "base", "width", 14.0)
    events = (("initial", initial), ("unchanged", initial), ("radius_edit", edited),
              ("invalid_radius", invalid), ("recovered", recovered), ("base_width_edit", resized))
    rows, traces, records, payloads, previews = [], [], [], {}, []
    previous = None
    for event, model in events:
        result = recompute(model, previous)
        failed = tuple(s.node_id for s in result.states if s.status == "failed")
        stale = tuple(s.node_id for s in result.states if s.status == "stale")
        expected_failed = ("feature",) if event == "invalid_radius" else ()
        expected_stale = ("boss", "result") if event == "invalid_radius" else ()
        expected_evaluated = {"initial": 6, "unchanged": 0, "radius_edit": 3, "invalid_radius": 1, "recovered": 0, "base_width_edit": 6}[event]
        expected_reused = {"initial": 0, "unchanged": 6, "radius_edit": 3, "invalid_radius": 3, "recovered": 6, "base_width_edit": 0}[event]
        truth_error = 0.0
        byte_replay_matches = True
        if not failed and not stale:
            state = result.current_output()
            width = dict(next(n for n in model.nodes if n.node_id == "base").parameters)["width"]
            radius = dict(next(n for n in model.nodes if n.node_id == "feature").parameters)["radius"]
            expected = width * 10 * 4 - math.pi * radius**2 * 4 + math.pi * 2
            truth_error = abs(state.metrics.absolute_volume - expected)
            fixture = step_round_trip(state.shape, "recompute_" + event, writer_uncertainty=1e-7)
            cold = recompute(model).current_output().shape
            replay = step_round_trip(cold, "recompute_" + event, writer_uncertainty=1e-7)
            byte_replay_matches = fixture.source_bytes == replay.source_bytes
            if event in {"initial", "radius_edit", "base_width_edit"}:
                payloads[fixture.file_name] = fixture.source_bytes
                previews.append((event.replace("_", " "), fixture.imported_shape))
        retained = all(s.shape is not None for s in result.states)
        passed = (failed == expected_failed and stale == expected_stale and
                  len(result.evaluated_nodes) == expected_evaluated and len(result.reused_nodes) == expected_reused
                  and truth_error < 1e-7 and byte_replay_matches and retained)
        rows.append({"event": event, "revision": model.revision, "evaluated_count": len(result.evaluated_nodes),
                     "reused_count": len(result.reused_nodes), "failed_nodes": "|".join(failed), "stale_nodes": "|".join(stale),
                     "all_last_valid_shapes_retained": retained, "volume_truth_error": truth_error,
                     "cold_vs_cached_step_bytes_match": byte_replay_matches if not failed else "",
                     "checks_pass": passed})
        traces.extend({"event": event, "revision": model.revision, "node_id": s.node_id, "state": s.status,
                       "evaluated": s.node_id in result.evaluated_nodes, "reused": s.node_id in result.reused_nodes,
                       "last_valid_revision": s.last_valid_revision, "error": s.error,
                       "attempted_fingerprint": s.attempted_fingerprint, "last_valid_fingerprint": s.last_valid_fingerprint}
                      for s in result.states)
        records.append({"event": event, "model": asdict(model), "recompute": recompute_record(result)})
        previous = result
    payloads["models.json"] = json_bytes([{"event": event, "model": asdict(model)} for event, model in events])
    handle_fixtures(fixtures, payloads, refresh=refresh, generator="experiments/run_deterministic_recompute.py")
    (output / "deterministic_recompute.csv").write_bytes(csv_bytes(rows))
    (output / "recompute_node_states.csv").write_bytes(csv_bytes(traces))
    (output / "recompute_models.json").write_bytes(json_bytes(records))
    write_shape_previews(output / "deterministic_recompute.png", tuple(previews), title="Dependency-aware parameter recompute", columns=3)
    _contract(output, "deterministic_recompute", "v0.58.0", rows, [
        "executable specialization of the feature-graph concept; it does not recover STEP history or persistent face identity",
        "failed/stale nodes retain last-valid geometry for inspection only; current_output refuses it",
        "serial deterministic traversal and fingerprint caching; independent branches continue, without atomic transactions",
        "six event controls with one disjoint two-feature branch and one independent branch are not arbitrary CAD robustness evidence",
    ], event_count=6, node_observation_count=len(traces))
    return rows


def reconstruction_inputs(source: Path) -> tuple[dict[str, bytes], dict[str, tuple[str, ...]]]:
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf

    payloads = {f"{kind}.step": (source / f"{kind}_before.step").read_bytes()
                for kind in ("through_hole", "blind_hole", "pocket", "boss", "rib")}
    plain = build_plate(PlateSpec()).shape
    translated = PlateSpec(origin_x=100., origin_y=-25., origin_z=7.)
    moved = apply_feature(build_plate(translated).shape, translated, feature_spec("through_hole", x=4., y=5., radius=1.)).shape
    transform = gp_Trsf()
    transform.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), math.pi / 6)
    rotated = BRepBuilderAPI_Transform(plain, transform, True).Shape()
    step = boolean_shape(plain, BRepPrimAPI_MakeBox(gp_Pnt(6, 0, 2), 6, 10, 2).Shape(), operation="cut")
    for name, shape in (("plain_plate", plain), ("translated_hole", moved), ("rotated_plate", rotated), ("unsupported_step", step)):
        fixture = step_round_trip(shape, name, writer_uncertainty=1e-7)
        payloads[fixture.file_name] = fixture.source_bytes
    expected = {
        "through_hole": ("profile_hole", "through_hole"), "blind_hole": ("blind_hole",),
        "pocket": ("rectangular_pocket",), "boss": ("cylindrical_boss",),
        "rib": ("rectangular_boss", "rectangular_rib"), "plain_plate": ("plate_extrusion",),
        "translated_hole": ("profile_hole", "through_hole"), "rotated_plate": (), "unsupported_step": (),
    }
    payloads["controls.json"] = json_bytes([{"control_id": name, "expected_explanations": values} for name, values in expected.items()])
    return payloads, expected


def run_step_reconstruction(output: Path, fixtures: Path, source: Path, *, refresh: bool = False) -> list[dict]:
    from research_notes.step_reconstruction import reconstruct_step, reconstruction_record

    output.mkdir(parents=True, exist_ok=True)
    payloads, expected = reconstruction_inputs(source)
    handle_fixtures(fixtures, payloads, refresh=refresh, generator="experiments/run_step_reconstruction.py")
    rows, candidate_rows, records, previews = [], [], [], []
    for name, explanations in expected.items():
        result = reconstruct_step(fixtures / f"{name}.step")
        actual = tuple(sorted(c.explanation for c in result.candidates))
        expected_state = "ambiguous" if len(explanations) > 1 else "candidate_available" if explanations else "unsupported"
        passed = actual == tuple(sorted(explanations)) and result.status == expected_state
        rows.append({"control_id": name, "status": result.status, "reason": result.reason,
                     "source_sha256": result.imported.source_sha256, "candidate_count": len(result.candidates),
                     "expected_explanations": "|".join(explanations), "observed_explanations": "|".join(actual),
                     "authoring_history_recovered": False, "checks_pass": passed})
        candidate_rows.extend({"control_id": name, "candidate_id": c.candidate_id,
                               "explanation": c.explanation, "state": c.status,
                               "supporting_faces": "|".join(map(str, c.supporting_faces)),
                               "volume_residual": c.volume_residual, "area_residual": c.area_residual,
                               "material_difference_volume": c.material_difference_volume,
                               "bounds_residual": c.bounds_residual, "topology_matches": c.topology_matches,
                               "fit_score": c.fit_score, "confidence_kind": c.confidence_kind,
                               "authoring_history_recovered": c.authoring_history_recovered} for c in result.candidates)
        records.append({"control_id": name, **reconstruction_record(result)})
        previews.append((f"{name.replace('_', ' ')}\n{len(result.candidates)} proposal(s)", result.imported.shape))
    (output / "step_reconstruction.csv").write_bytes(csv_bytes(rows))
    (output / "reconstruction_candidates.csv").write_bytes(csv_bytes(candidate_rows))
    (output / "step_reconstruction.json").write_bytes(json_bytes(records))
    write_shape_previews(output / "step_reconstruction.png", tuple(previews), title="STEP reconstruction: proposals and explicit abstention", columns=3)
    _contract(output, "step_reconstruction", "v0.59.0", rows, [
        "candidate generation reads source bytes and measured B-Rep faces, not fixture names, expected labels, or sidecar truth",
        "single-root, single-shell millimetre solids; axis-aligned planes and at most one Z-axis cylinder, with bounded sizes",
        "all proposals remain unconfirmed; equivalent construction routes and semantic labels remain explicit alternatives",
        "fit_score is an uncalibrated residual score, not a probability of correct design intent",
        "bidirectional material difference uses the same kernel; face IDs are analysis-local, not persistent STEP/CAD identities",
        "bounded parsing and topology gates do not provide an OS sandbox or native-code timeout",
    ], input_count=len(rows), candidate_count=len(candidate_rows), fit_tolerance=1e-7,
       source_coordinate_checkpoint="9 decimal places; candidates are rechecked against unrounded source geometry")
    return rows


def _session_guard_observations(source: Path, directory: Path) -> list[dict]:
    from research_notes.assisted_modeling import ModelingSession

    session = ModelingSession()
    session.open_step(source / "through_hole.step")
    candidate_id = next(c.candidate_id for c in session.inspection.candidates if c.explanation == "through_hole")
    rows = []

    def rejected(name, action):
        try:
            action()
            passed, reason = False, "unexpected_accept"
        except (ValueError, FileExistsError) as exc:
            passed, reason = True, str(exc)
        rows.append({"control_id": name, "decision": "reject" if passed else "accept", "reason": reason, "checks_pass": passed})

    target = directory / "guard_output.step"
    rejected("edit_before_selection", lambda: session.edit("feature", "radius", 1.5))
    rejected("selection_without_confirmation", lambda: session.select_candidate(candidate_id))
    rejected("export_before_selection", lambda: session.export_step(target))
    session.select_candidate(candidate_id, confirm=True)
    session.edit("feature", "radius", 1.5)
    rejected("export_before_recompute", lambda: session.export_step(target))
    rejected("compare_before_recompute", session.compare)
    session.recompute()
    session.export_step(target)
    rejected("overwrite_without_permission", lambda: session.export_step(target))
    rejected("source_overwrite", lambda: session.export_step(source / "through_hole.step", overwrite=True))
    session.edit("feature", "radius", 30.)
    result = session.recompute()
    rejected("export_stale_result", lambda: session.export_step(directory / "stale.step"))
    rejected("compare_stale_result", session.compare)
    session.edit("feature", "radius", 1.5)
    recovered = session.recompute()
    rows.append({"control_id": "failed_edit_recovery", "decision": "recover",
                 "reason": "last_valid_geometry_reused",
                 "checks_pass": result.state("feature").status == "failed" and result.state("result").status == "stale"
                 and recovered.current_output().status == "valid" and not recovered.evaluated_nodes})
    session.open_step(source / "pocket.step")
    rows.append({"control_id": "new_import_clears_selection", "decision": "reset", "reason": "new_source_requires_selection",
                 "checks_pass": session.model is None and session.result is None and session.selected_candidate_id is None})
    return rows


def run_assisted_modeling(output: Path, fixtures: Path, source: Path, *, refresh: bool = False) -> list[dict]:
    from research_notes.assisted_modeling import ModelingSession

    output.mkdir(parents=True, exist_ok=True)
    rows, sessions, payloads, before_previews, after_previews = [], [], {}, [], []
    controls = {name: (plate, feature) for name, plate, feature in feature_controls()}
    with tempfile.TemporaryDirectory(prefix="research-notes-assisted-") as directory:
        temporary = Path(directory)
        for kind, explanation, parameter, value in (
            ("through_hole", "through_hole", "radius", 1.5),
            ("blind_hole", "blind_hole", "depth", 2.),
            ("pocket", "rectangular_pocket", "depth", 2.),
            ("boss", "cylindrical_boss", "height", 3.),
            ("rib", "rectangular_rib", "width", 1.5),
        ):
            path = source / f"{kind}.step"
            original = path.read_bytes()
            session = ModelingSession()
            session.open_step(path)
            candidate = next(c for c in session.inspection.candidates if c.explanation == explanation)
            session.select_candidate(candidate.candidate_id, confirm=True)
            session.edit("feature", parameter, value)
            result = session.recompute()
            comparison = session.compare()
            destination = temporary / f"edited_{kind}.step"
            exported = session.export_step(destination)
            payloads[destination.name] = destination.read_bytes()
            plate, feature = controls[f"{kind}_after"]
            expected_volume, expected_area = analytic_feature_truth(plate, feature)
            metrics = result.current_output().metrics
            volume_error, area_error = abs(metrics.absolute_volume - expected_volume), abs(metrics.surface_area - expected_area)
            source_unchanged = original == path.read_bytes()
            passed = (volume_error < 1e-7 and area_error < 1e-7 and source_unchanged
                      and exported["round_trip"]["topology_matches"] and exported["selection_confirmed"])
            rows.append({"control_id": kind, "selected_explanation": explanation, "selection_confirmed": True,
                         "parameter": parameter, "edited_value": value, "model_revision": session.model.revision,
                         "before_volume": comparison["before"]["absolute_volume"], "after_volume": metrics.absolute_volume,
                         "expected_volume": expected_volume, "volume_error": volume_error,
                         "expected_area": expected_area, "area_error": area_error,
                         "volume_change": comparison["volume_change"], "source_unchanged": source_unchanged,
                         "source_sha256": session.inspection.imported.source_sha256,
                         "export_sha256": exported["sha256"], "round_trip_topology_matches": exported["round_trip"]["topology_matches"],
                         "checks_pass": passed})
            sessions.append({"control_id": kind, "session": session.status(), "comparison": comparison, "export": exported})
            before_previews.append((f"{kind.replace('_', ' ')} | imported", session.inspection.imported.shape))
            after_previews.append((f"{parameter} = {value:g} mm | edited", result.current_output().shape))
            if kind == "through_hole":
                session.write_comparison(temporary / "example")
                (output / "assisted_modeling_example.png").write_bytes((temporary / "example/comparison.png").read_bytes())
        guards = _session_guard_observations(source, temporary)
    payloads["workflow.json"] = json_bytes([{key: row[key] for key in ("control_id", "selected_explanation", "parameter", "edited_value", "source_sha256")} for row in rows])
    # This script is also exercised through the real terminal tool in tests.
    payloads["demo_commands.txt"] = (
        "open fixtures/step-reconstruction/through_hole.step\n"
        "candidates\nselect 2 --confirm\nset feature radius 1.5\nrecompute\ncompare\n"
        "export output/modeling-demo/edited.step --overwrite\nstatus\nquit\n"
    ).encode()
    handle_fixtures(fixtures, payloads, refresh=refresh, generator="experiments/run_assisted_modeling.py")
    (output / "assisted_modeling.csv").write_bytes(csv_bytes(rows))
    (output / "assisted_modeling_guards.csv").write_bytes(csv_bytes(guards))
    (output / "assisted_modeling_sessions.json").write_bytes(json_bytes(sessions))
    write_shape_previews(output / "assisted_modeling.png", tuple(before_previews + after_previews),
                         title="Import, confirm, edit, recompute, compare, and export", columns=5)
    _contract(output, "assisted_modeling", "v0.60.0", rows + guards, [
        "focused Python API and terminal workspace for the v0.59.0 qualified input grammar, not a general CAD editor",
        "inferred proposals require explicit confirmation before model replacement or editing; no original authoring history is claimed",
        "dirty, failed, and stale outputs cannot be compared as current or exported; source files cannot be overwritten",
        "STEP export is shape-only: names, colors, PMI, constraints, and proprietary history are not preserved by this route",
        "session.json is an inspection record, not a persistent session restore or crash-recovery format",
        "input parsing is bounded but native import and geometry work are not an OS security sandbox",
    ], workflow_count=5, guard_count=len(guards), terminal_entry_point="python -m research_notes.modeling_tool")
    return rows
