"""Reference evidence for scoped topology, dimensional expressions, histories, and assemblies."""
from __future__ import annotations

import math
from dataclasses import asdict, replace
from pathlib import Path

from research_notes.assembly_constraints import AssemblyConstraint
from research_notes.assembly_controls import assembly_controls, slider_assembly
from research_notes.assembly_recompute import (
    AssemblySession, assembly_from_dict, assembly_record, compound_shapes, recompute_assembly,
)
from research_notes.brep_preview import write_shape_previews
from research_notes.brep_runtime import step_round_trip
from research_notes.deterministic_recompute import recompute, single_feature_model
from research_notes.feature_history_editing import (
    Configuration, FeatureHistory, HistoryFeature, apply_configuration, compile_history,
    reorder_features, rollback_history, suppress_feature,
)
from research_notes.modeling_common import measure_shape
from research_notes.modeling_studies import _contract, csv_bytes, handle_fixtures, json_bytes
from research_notes.parameter_expressions import Parameter, bind_model_parameters, evaluate_parameters
from research_notes.parametric_features import PlateSpec, feature_spec
from research_notes.topological_references import (
    advance_reference, reference_relations, select_reference, topology_snapshot,
)


def _fixture(shape, name):
    return step_round_trip(shape, name, writer_uncertainty=1e-7)


def run_topological_references(output: Path, fixtures: Path, *, refresh=False):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
    from OCP.gp import gp_Pnt
    output.mkdir(parents=True, exist_ok=True)
    original = BRepPrimAPI_MakeBox(4., 4., 2.).Shape()
    edited = BRepPrimAPI_MakeBox(6., 4., 3.).Shape()
    imported = _fixture(edited, "reference_edited").imported_shape
    split = BRepAlgoAPI_Cut(original, BRepPrimAPI_MakeBox(gp_Pnt(1.5, -1., -1.), 1., 6., 4.).Shape())
    deleted = BRepAlgoAPI_Cut(original, BRepPrimAPI_MakeBox(gp_Pnt(-1., -1., -1.), 3., 6., 4.).Shape())
    fused = BRepAlgoAPI_Fuse(BRepPrimAPI_MakeBox(2., 4., 2.).Shape(),
                            BRepPrimAPI_MakeBox(gp_Pnt(2., 0., 0.), 2., 4., 2.).Shape()).Shape()
    unify = ShapeUpgrade_UnifySameDomain(fused, True, True, False)
    unify.Build()
    duplicate = compound_shapes((original, BRepBuilderAPI_Copy(original).Shape()))
    controls = (
        ("parameter_edit", original, edited, "normalized_box", None, {"one_to_one": 18}),
        ("step_exchange", edited, imported, "geometry", None, {"one_to_one": 18}),
        ("cut_split", original, split.Shape(), "operation_history", split, {"one_to_one": 10, "split": 8}),
        ("cut_delete", original, deleted.Shape(), "operation_history", deleted, {"one_to_one": 13, "deleted": 5}),
        ("healing_merge", fused, unify.Shape(), "operation_history", unify.History(), {"one_to_one": 10, "merge": 16, "deleted": 4}),
        ("geometric_ambiguity", original, duplicate, "geometry", None, {"ambiguous": 18}),
    )
    rows, relations, payloads, previews = [], [], {}, []
    for name, before, after, mode, history, expected in controls:
        source = topology_snapshot(before, "reference_control", name+"_before")
        target = topology_snapshot(after, "reference_control", name+"_after")
        mapped = reference_relations(source, target, mode=mode, history=history)
        counts = {kind: sum(r.relation == kind for r in mapped) for kind in {r.relation for r in mapped}}
        refused = 0
        for row in mapped:
            reference = select_reference(source, row.kind, row.source_index, name=f"{row.kind}_{row.source_index}")
            try:
                updated = advance_reference(reference, mapped)
                assert updated.reference_id == reference.reference_id
            except ValueError:
                refused += 1
            relations.append({"control_id": name, **asdict(row)})
        rows.append({"control_id": name, "source_count": len(mapped), "relation_counts": str(sorted(counts.items())),
                     "expected_counts": str(sorted(expected.items())), "review_required_count": refused,
                     "checks_pass": counts == expected and refused == len(mapped)-counts.get("one_to_one", 0)})
        for stage, shape in (("before", before), ("after", after)):
            fixture = _fixture(shape, f"{name}_{stage}")
            payloads[fixture.file_name] = fixture.source_bytes
        previews.append((name.replace("_", " "), after))
    payloads["controls.json"] = json_bytes([{"control_id": c[0], "mode": c[3], "expected_counts": c[5]} for c in controls])
    handle_fixtures(fixtures, payloads, refresh=refresh, generator="experiments/run_topological_references.py")
    (output/"topological_references.csv").write_bytes(csv_bytes(rows))
    (output/"topological_reference_relations.json").write_bytes(json_bytes(relations))
    write_shape_previews(output/"topological_references.png", tuple(previews), title="Scoped reference continuity")
    _contract(output, "topological_references", "v0.61.0", rows,
              ["normalized roles qualify unfeatured axis-aligned boxes only",
               "geometry inference is not permanent identity; split, deletion, and merge require operation evidence",
               "ambiguous, split, deleted, and merged selections require explicit review"], relation_count=len(relations))
    return rows


def run_parameter_expressions(output: Path, fixtures: Path, *, refresh=False):
    output.mkdir(parents=True, exist_ok=True)
    accepted = (Parameter("width", "2 * inch"), Parameter("half", "width / 2", "cm"),
                Parameter("ratio", "half / width", "one", 0., 1.), Parameter("angle", "90 * deg", "rad", 0., 4.))
    expected = {"width": 50.8, "half": 25.4, "ratio": .5, "angle": math.pi/2}
    values = evaluate_parameters(accepted)
    rows = [{"control_id": v.name, "decision": "accept", "base_value": v.base_value,
             "expected_base_value": expected[v.name], "reason": "", "checks_pass": abs(v.base_value-expected[v.name]) < 1e-10} for v in values]
    invalid = [
        ("missing_unit", (Parameter("size", "2"),)),
        ("dimension_mismatch", (Parameter("size", "1*mm + 1*deg"),)),
        ("division_zero", (Parameter("size", "1*mm/0"),)),
        ("unknown_name", (Parameter("size", "missing*mm"),)),
        ("call", (Parameter("size", "abs(-1)*mm"),)),
        ("attribute", (Parameter("size", "mm.real"),)),
        ("power", (Parameter("size", "2**8*mm"),)),
        ("overflow", (Parameter("size", "1e999*mm"),)),
        ("out_of_domain", (Parameter("size", "10001*mm"),)),
        ("cycle", (Parameter("a", "b"), Parameter("b", "a"))),
        ("duplicate_name", (Parameter("a", "1*mm"), Parameter("a", "2*mm"))),
        ("reserved_unit", (Parameter("mm", "1*mm"),)),
    ]
    for name, parameters in invalid:
        try:
            evaluate_parameters(parameters)
            reason, passed = "unexpected_accept", False
        except ValueError as exc:
            reason, passed = str(exc), True
        rows.append({"control_id": name, "decision": "reject" if passed else "accept", "base_value": None,
                     "expected_base_value": None, "reason": reason, "checks_pass": passed})
    model = single_feature_model("bound_hole", PlateSpec(), feature_spec("through_hole", x=4., y=5., radius=1.))
    parameters = (Parameter("diameter", "0.3 * cm"), Parameter("radius", "diameter / 2"))
    changed = bind_model_parameters(model, parameters, (("radius", "feature", "radius"),))
    shapes = [("before", recompute(model).current_output().shape), ("bound radius", recompute(changed).current_output().shape)]
    expected_volume = 480.-9*math.pi
    volume = measure_shape(shapes[1][1]).absolute_volume
    rows.append({"control_id": "bound_model", "decision": "accept", "base_value": volume, "expected_base_value": expected_volume,
                 "reason": "3 mm diameter becomes 1.5 mm model radius", "checks_pass": abs(volume-expected_volume) < 1e-7})
    fixture = _fixture(shapes[1][1], "expression_bound_hole")
    payloads = {fixture.file_name: fixture.source_bytes,
                "parameters.json": json_bytes({"accepted": [asdict(p) for p in accepted],
                 "invalid": [{"control_id": n, "parameters": [asdict(p) for p in pset]} for n, pset in invalid],
                 "bound_parameters": [asdict(p) for p in parameters], "bindings": [("radius", "feature", "radius")]})}
    handle_fixtures(fixtures, payloads, refresh=refresh, generator="experiments/run_parameter_expressions.py")
    (output/"parameter_expressions.csv").write_bytes(csv_bytes(rows))
    (output/"parameter_values.json").write_bytes(json_bytes([asdict(v) for v in values]))
    write_shape_previews(output/"parameter_expressions.png", tuple(shapes), title="Unit-aware dimension binding", columns=2)
    _contract(output, "parameter_expressions", "v0.62.0", rows,
              ["bounded arithmetic AST only; no eval, calls, attributes, powers, or implicit unit coercion",
               "base units mm and rad; domains apply in each declared unit; 64 parameters, 256 characters, 96 AST nodes",
               "scalar length bindings drive the existing bounded feature model"])
    return rows


def history_control():
    return FeatureHistory("feature_history", PlateSpec(), (
        HistoryFeature("hole", feature_spec("through_hole", x=3., y=3., radius=1.)),
        HistoryFeature("boss", feature_spec("boss", x=9., y=7., radius=1., height=2.)),
    ))


def run_feature_history_editing(output: Path, fixtures: Path, *, refresh=False):
    output.mkdir(parents=True, exist_ok=True)
    base = history_control()
    suppressed = suppress_feature(base, "hole")
    cases = (
        ("initial", base, 480.-2*math.pi, 416.+10*math.pi),
        ("suppressed", suppressed, 480.+2*math.pi, 416.+4*math.pi),
        ("reactivated", suppress_feature(suppressed, "hole", suppressed=False), 480.-2*math.pi, 416.+10*math.pi),
        ("reordered", reorder_features(base, ("boss", "hole")), 480.-2*math.pi, 416.+10*math.pi),
        ("rollback", rollback_history(base, "hole"), 480.-4*math.pi, 416.+6*math.pi),
        ("wide_configuration", apply_configuration(base, Configuration("wide", (("hole", "radius", 1.5),))), 480.-7*math.pi, 416.+11.5*math.pi),
        ("base_only", rollback_history(base, "base"), 480., 416.),
    )
    rows, records, previews, payloads, previous = [], [], [], {}, None
    for name, history, volume, area in cases:
        model = compile_history(history)
        result = recompute(model, previous)
        current = result.current_output()
        fixture = _fixture(current.shape, "history_"+name)
        imported = measure_shape(fixture.imported_shape)
        errors = [abs(current.metrics.absolute_volume-volume), abs(current.metrics.surface_area-area),
                  abs(imported.absolute_volume-volume), abs(imported.surface_area-area)]
        rows.append({"control_id": name, "revision": history.revision, "active_nodes": "|".join(n.node_id for n in model.nodes),
                     "evaluated_nodes": "|".join(result.evaluated_nodes), "reused_nodes": "|".join(result.reused_nodes),
                     "volume": current.metrics.absolute_volume, "expected_volume": volume,
                     "surface_area": current.metrics.surface_area, "expected_area": area,
                     "max_truth_error": max(errors), "checks_pass": max(errors) < 1e-7})
        records.append({"control_id": name, "history": asdict(history), "model": asdict(model)})
        payloads[fixture.file_name] = fixture.source_bytes
        previews.append((name.replace("_", " "), current.shape))
        previous = result
    payloads["histories.json"] = json_bytes(records)
    handle_fixtures(fixtures, payloads, refresh=refresh, generator="experiments/run_feature_history_editing.py")
    (output/"feature_history_editing.csv").write_bytes(csv_bytes(rows))
    (output/"feature_history_models.json").write_bytes(json_bytes(records))
    write_shape_previews(output/"feature_history_editing.png", tuple(previews), title="Feature history edits", columns=4)
    _contract(output, "feature_history_editing", "v0.63.0", rows,
              ["authored feature sequences and immutable configurations; no inferred history recovery",
               "truth uses two disjoint features; interacting-feature reordering is not qualified",
               "suppression and rollback change active dependencies; unsupported profile order rejects"])
    return rows


def run_assembly_constraints(output: Path, fixtures: Path, *, refresh=False):
    output.mkdir(parents=True, exist_ok=True)
    payloads, records, rows, previews = {}, [], [], []
    for name, document, expected, dof, redundant in assembly_controls():
        payloads[name+".json"] = json_bytes(asdict(document))
        decoded = assembly_from_dict(asdict(document))
        rows.append({"control_id": name, "definition_count": len(document.definitions),
                     "occurrence_count": len(document.occurrences), "constraint_count": len(document.constraints),
                     "shared_definition": len({o.definition_id for o in document.occurrences}) == 1,
                     "expected_solver_status": expected, "expected_freedom": dof, "expected_redundant_equations": redundant,
                     "checks_pass": decoded == document and len(document.definitions) == 1 and len(document.occurrences) == 2})
        records.append({"control_id": name, "document": asdict(document)})
        if name in {"fully_fixed", "rotated_ground", "inch_initial_placement"}:
            result = recompute_assembly(document)
            shape = compound_shapes(s for _, s in result.placed_shapes)
            fixture = _fixture(shape, name)
            payloads[fixture.file_name] = fixture.source_bytes
            previews.append((name.replace("_", " "), shape))
    handle_fixtures(fixtures, payloads, refresh=refresh, generator="experiments/run_assembly_constraints.py")
    (output/"assembly_constraints.csv").write_bytes(csv_bytes(rows))
    (output/"assembly_documents.json").write_bytes(json_bytes(records))
    write_shape_previews(output/"assembly_constraints.png", tuple(previews), title="Definitions, occurrences, and authored mates")
    _contract(output, "assembly_constraints", "v0.64.0", rows,
              ["authored JSON assemblies; no recovery of assembly mates from arbitrary STEP",
               "definitions use mm B-Rep; occurrence/frame units and local datum provenance remain separate",
               "fixed coordinate locks, co-oriented plane coincidence, coaxial axes, and signed axial distance"])
    return rows


def run_assembly_recompute(output: Path, fixtures: Path, *, refresh=False):
    output.mkdir(parents=True, exist_ok=True)
    rows, records, previews, payloads = [], [], [], {}
    for name, document, expected, dof, redundant in assembly_controls():
        result = recompute_assembly(document)
        solution = result.solution
        rows.append({"control_id": name, "status": result.status, "expected_status": expected,
                     "degrees_of_freedom": solution.degrees_of_freedom, "expected_freedom": dof,
                     "redundant_equations": solution.redundant_equations,
                     "pair_state": result.pair_checks[0]["status"] if result.pair_checks else "not_evaluated",
                     "expected_pair_state": "", "checks_pass": result.status == expected
                     and solution.degrees_of_freedom == dof and solution.redundant_equations == redundant})
        records.append({"control_id": name, "result": assembly_record(result)})
    session = AssemblySession(slider_assembly())
    sequence = (("initial", None, None, "fully_constrained", "separated", 3., 1., 0.),
                ("unchanged", None, None, "fully_constrained", "separated", 3., 1., 0.),
                ("contact", "clearance", "0 * mm", "fully_constrained", "contact", 2., 0., 0.),
                ("interference", "clearance", "-1 * mm", "fully_constrained", "interference", 1., 0., 4.),
                ("clearance_restored", "clearance", "1 * mm", "fully_constrained", "separated", 3., 1., 0.),
                ("height_edit", "height", "3 * mm", "fully_constrained", "separated", 4., 1., 0.),
                ("invalid_height", "height", "0.00001 * mm", "component_failed", "not_evaluated", None, None, None),
                ("height_recovered", "height", "3 * mm", "fully_constrained", "separated", 4., 1., 0.))
    for name, parameter, expression, expected, pair_state, height, distance, volume in sequence:
        if parameter:
            session.set_parameter(parameter, expression)
        result = session.recompute()
        pair = result.pair_checks[0] if result.pair_checks else None
        truth_pass = result.status == expected
        if pair:
            pose = result.solution.placements[result.solution.occurrence_order.index("slider")]
            truth_pass &= (pair["status"] == pair_state and abs(pose.translation[2]-height) < 1e-7
                           and abs(pair["minimum_distance_mm"]-distance) < 1e-7
                           and abs(pair["overlap_volume_mm3"]-volume) < 1e-7)
        if name in {"unchanged", "clearance_restored", "height_recovered"}:
            truth_pass &= not result.component_results[0][1].evaluated_nodes
        rows.append({"control_id": "edit_"+name, "status": result.status, "expected_status": expected,
                     "degrees_of_freedom": result.solution.degrees_of_freedom if result.solution else None,
                     "expected_freedom": 0 if result.solution else None,
                     "redundant_equations": result.solution.redundant_equations if result.solution else None,
                     "pair_state": pair["status"] if pair else "not_evaluated", "expected_pair_state": pair_state, "checks_pass": truth_pass})
        records.append({"control_id": "edit_"+name, "result": assembly_record(result)})
        if result.placed_shapes and name in {"initial", "contact", "interference", "height_edit"}:
            shape = compound_shapes(s for _, s in result.placed_shapes)
            previews.append((name+"\n"+pair_state, shape))
            # Interference is a diagnostic fixture, never a session export.
            fixture = _fixture(shape, "assembly_diagnostic_"+name)
            payloads[fixture.file_name] = fixture.source_bytes
        if name in {"initial", "height_recovered"}:
            cold = recompute_assembly(session.document)
            first = _fixture(compound_shapes(s for _, s in result.placed_shapes), "assembly_repeatability")
            second = _fixture(compound_shapes(s for _, s in cold.placed_shapes), "assembly_repeatability")
            rows[-1]["checks_pass"] &= first.source_bytes == second.source_bytes
    payloads["recompute_cases.json"] = json_bytes(records)
    payloads["demo_commands.txt"] = b"open fixtures/assembly-constraints/fully_fixed.json\nrecompute\nreport\nset clearance 0 * mm\nrecompute\nreport\nexport output/assembly-demo/contact.step --overwrite\nset clearance -1 * mm\nrecompute\nreport\nset clearance 1 * mm\nset height 3 * mm\nrecompute\nreport\nexport output/assembly-demo/edited.step --overwrite\nquit\n"
    handle_fixtures(fixtures, payloads, refresh=refresh, generator="experiments/run_assembly_recompute.py")
    (output/"assembly_recompute.csv").write_bytes(csv_bytes(rows))
    (output/"assembly_recompute_states.json").write_bytes(json_bytes(records))
    write_shape_previews(output/"assembly_recompute.png", tuple(previews), title="Assembly contact, interference, and dimension propagation", columns=4)
    _contract(output, "assembly_recompute", "v0.65.0", rows,
              ["local rank/nullspace at one pose; no global motion or nonlinear infeasibility proof",
               "duplicate conflicting right-hand sides prove the declared inconsistent controls; other failure is not_converged",
               "provisional interference observations for under-constrained poses are not motion envelopes",
               "same-kernel common volume and minimum distance; geometry-only STEP export blocks interference and incomplete constraints"],
              solver_control_count=10, edit_event_count=8)
    return rows
