"""Component reuse, placement recompute, and qualified interference diagnostics."""
from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import numpy as np

from research_notes.assembly_constraints import (
    AssemblyConstraint, AssemblyDocument, AssemblySolution, ComponentDefinition,
    DatumFrame, Occurrence, Placement, placement_vector, rotation_matrix,
    solve_placements, unit_scale, validate_assembly,
)
from research_notes.brep_runtime import signed_volume, step_round_trip, topology_counts
from research_notes.deterministic_recompute import RecomputeResult, model_from_dict, recompute, recompute_record
from research_notes.parameter_expressions import Parameter, bind_model_parameters, evaluate_parameters
from research_notes.step_reconstruction import compare_shapes


@dataclass(frozen=True)
class AssemblyResult:
    assembly_id: str
    revision: int
    fingerprint: str
    status: str
    component_results: tuple[tuple[str, RecomputeResult], ...]
    solution: AssemblySolution | None
    pair_checks: tuple[dict, ...]
    placed_shapes: tuple[tuple[str, object], ...]


def assembly_fingerprint(document: AssemblyDocument) -> str:
    return hashlib.sha256(json.dumps(asdict(document), sort_keys=True, allow_nan=False).encode()).hexdigest()


def assembly_from_dict(payload: dict) -> AssemblyDocument:
    if set(payload) != set(AssemblyDocument.__dataclass_fields__):
        raise ValueError("unexpected assembly document fields")
    definitions = tuple(ComponentDefinition(
        d["definition_id"], model_from_dict(d["model"]),
        tuple(DatumFrame(**{**f, "origin": tuple(f["origin"]), "rotation_degrees": tuple(f["rotation_degrees"])}) for f in d["frames"]),
        d["geometry_unit"],
    ) for d in payload["definitions"])
    def pose(p):
        return Placement(tuple(p["translation"]), tuple(p["rotation_degrees"]), p["unit"])
    occurrences = tuple(Occurrence(o["occurrence_id"], o["definition_id"], pose(o["initial"])) for o in payload["occurrences"])
    constraints = tuple(AssemblyConstraint(**{**c, "axes": tuple(c["axes"]), "target": pose(c["target"])}) for c in payload["constraints"])
    result = AssemblyDocument(payload["assembly_id"], definitions, occurrences, constraints,
                              tuple(Parameter(**p) for p in payload["parameters"]),
                              tuple(tuple(b) for b in payload["bindings"]), payload["revision"])
    validate_assembly(result)
    return result


def edit_assembly_parameter(document: AssemblyDocument, name: str, expression: str) -> AssemblyDocument:
    if name not in {p.name for p in document.parameters}:
        raise ValueError("unknown assembly parameter")
    updated = replace(document, revision=document.revision+1,
                      parameters=tuple(replace(p, expression=expression) if p.name == name else p for p in document.parameters))
    validate_assembly(updated)
    return updated


def _local_frame(frame: DatumFrame, plate) -> tuple:
    origin = np.asarray(frame.origin, dtype=float)*unit_scale(frame.unit)
    if frame.anchor != "explicit":
        factor = {"plate_top": 1., "plate_bottom": 0., "plate_center": .5}[frame.anchor]
        origin += np.array((plate.origin_x+plate.width/2, plate.origin_y+plate.length/2,
                            plate.origin_z+plate.thickness*factor))
    rotation = rotation_matrix(np.asarray(frame.rotation_degrees)*np.pi/180)
    return origin, rotation


def transform_shape(shape, placement: Placement):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Trsf
    values = placement_vector(placement)
    # Fixed decimal checkpoints keep native placements repeatable across cold/cache paths.
    t, r = np.round(values[:3], 12)+0., np.round(rotation_matrix(values[3:]), 12)+0.
    transform = gp_Trsf()
    transform.SetValues(*(float(v) for row in range(3) for v in (*r[row], t[row])))
    return BRepBuilderAPI_Transform(shape, transform, True).Shape()


def compound_shapes(shapes):
    from OCP.BRep import BRep_Builder
    from OCP.TopoDS import TopoDS_Compound
    compound, builder = TopoDS_Compound(), BRep_Builder()
    builder.MakeCompound(compound)
    for shape in shapes:
        builder.Add(compound, shape)
    return compound


def pair_interference(first, second) -> dict:
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.TopTools import TopTools_ListOfShape
    args, tools = TopTools_ListOfShape(), TopTools_ListOfShape()
    args.Append(first)
    tools.Append(second)
    operation = BRepAlgoAPI_Common()
    operation.SetArguments(args)
    operation.SetTools(tools)
    operation.SetRunParallel(False)
    operation.SetNonDestructive(True)
    operation.Build()
    if not operation.IsDone():
        raise RuntimeError("assembly intersection calculation failed")
    volume = abs(signed_volume(operation.Shape()))
    distance = BRepExtrema_DistShapeShape(first, second)
    if not distance.IsDone():
        raise RuntimeError("assembly distance calculation failed")
    minimum = float(distance.Value())
    status = "interference" if volume > 1e-7 else "contact" if minimum <= 1e-7 else "separated"
    return {"status": status, "overlap_volume_mm3": volume, "minimum_distance_mm": minimum}


def recompute_assembly(document: AssemblyDocument, previous: AssemblyResult | None = None) -> AssemblyResult:
    validate_assembly(document)
    if previous is not None and previous.assembly_id != document.assembly_id:
        raise ValueError("assembly cache belongs to another document")
    old = dict(previous.component_results) if previous else {}
    components, models = {}, {}
    # Resolve every expression/binding before invoking native geometry.
    for definition in document.definitions:
        bindings = tuple((name, node, field) for identifier, name, node, field in document.bindings if identifier == definition.definition_id)
        models[definition.definition_id] = bind_model_parameters(definition.model, document.parameters, bindings) if bindings else definition.model
    for identifier, model in sorted(models.items()):
        components[identifier] = recompute(model, old.get(identifier))
    fingerprint = assembly_fingerprint(document)
    if any(result.state(result.output_id).status != "valid" for result in components.values()):
        return AssemblyResult(document.assembly_id, document.revision, fingerprint, "component_failed",
                              tuple(components.items()), None, (), ())
    definitions = {d.definition_id: d for d in document.definitions}
    local_frames = {}
    for occurrence in document.occurrences:
        definition = definitions[occurrence.definition_id]
        plate = components[definition.definition_id].current_output().plate
        for frame in definition.frames:
            local_frames[occurrence.occurrence_id, frame.frame_id] = _local_frame(frame, plate)
    solution = solve_placements(document, local_frames)
    if solution.status in {"inconsistent", "not_converged"}:
        return AssemblyResult(document.assembly_id, document.revision, fingerprint, solution.status,
                              tuple(components.items()), solution, (), ())
    occurrences = {o.occurrence_id: o for o in document.occurrences}
    shapes = tuple((key, transform_shape(components[occurrences[key].definition_id].current_output().shape, pose))
                   for key, pose in zip(solution.occurrence_order, solution.placements, strict=True))
    pairs = tuple({"occurrence_a": a, "occurrence_b": b, **pair_interference(first, second),
                   "placement_provisional": solution.degrees_of_freedom > 0}
                  for (a, first), (b, second) in itertools.combinations(shapes, 2))
    return AssemblyResult(document.assembly_id, document.revision, fingerprint, solution.status,
                          tuple(components.items()), solution, pairs, shapes)


def assembly_record(result: AssemblyResult) -> dict:
    return {"assembly_id": result.assembly_id, "revision": result.revision, "fingerprint": result.fingerprint,
            "status": result.status, "solution": asdict(result.solution) if result.solution else None,
            "components": {key: recompute_record(value) for key, value in result.component_results},
            "pair_checks": result.pair_checks,
            "placement_is_local_solution": True, "original_step_assembly_history_recovered": False}


class AssemblySession:
    """Keep last accepted assembly for diagnosis; never export it as a failed revision."""
    def __init__(self, document: AssemblyDocument):
        validate_assembly(document)
        self.document = document
        self.result: AssemblyResult | None = None
        self.last_valid: AssemblyResult | None = None

    def set_parameter(self, name: str, expression: str):
        self.document = edit_assembly_parameter(self.document, name, expression)

    def recompute(self) -> AssemblyResult:
        result = recompute_assembly(self.document, self.result)
        self.result = result
        if result.status == "fully_constrained" and not any(p["status"] == "interference" for p in result.pair_checks):
            self.last_valid = result
        return result

    def current(self) -> AssemblyResult:
        if self.result is None or self.result.fingerprint != assembly_fingerprint(self.document):
            raise ValueError("assembly changed; recompute before reporting or export")
        return self.result

    def export_step(self, path: Path, *, overwrite: bool = False) -> dict:
        result = self.current()
        if result.status != "fully_constrained":
            raise ValueError("export requires a fully constrained current assembly")
        if any(p["status"] == "interference" for p in result.pair_checks):
            raise ValueError("export blocked by assembly interference")
        path = Path(path)
        if path.suffix.lower() not in {".step", ".stp"}:
            raise ValueError("assembly export requires .step or .stp")
        if path.exists() and not overwrite:
            raise FileExistsError("export exists; explicit overwrite is required")
        shape = compound_shapes(s for _, s in result.placed_shapes)
        fixture = step_round_trip(shape, "assembly_result", writer_uncertainty=1e-7)
        verification = compare_shapes(shape, fixture.imported_shape)
        errors = [verification[key] for key in ("volume_residual", "area_residual", "material_difference_volume", "bounds_residual")]
        if not verification["topology_matches"] or not verification["surface_inventory_matches"] or any(v > 1e-7 for v in errors):
            raise RuntimeError("assembly geometry export round-trip failed")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb" if overwrite else "xb") as stream:
            stream.write(fixture.source_bytes)
        return {"file_name": path.name, "sha256": fixture.source_sha256, "assembly_fingerprint": result.fingerprint,
                "round_trip": verification,
                "preservation_policy": "placed_shape_geometry_only; assembly constraints and authored IDs are in JSON, not STEP"}
