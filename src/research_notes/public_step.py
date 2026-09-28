"""Bounded, inspection-only STEP import and measured geometry exchange.

This route deliberately does not infer editable history, material, or mates.
All geometry is transferred into millimetres; AP semantics remain separate.
"""
from __future__ import annotations

import hashlib
import math
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from research_notes.brep_runtime import indexed_shapes, step_round_trip, topology_counts
from research_notes.modeling_common import measure_shape
from research_notes.spatial_workflow import WorkBudget, inspect_step_stages
from research_notes.step_reconstruction import ImportedShape


@dataclass(frozen=True)
class InspectionInput:
    imported: ImportedShape
    roots: int
    unit_contexts: tuple[dict, ...]


def length_contexts(document) -> tuple[dict, ...]:
    """Qualify uniform SI/conversion length contexts, without interpreting AP product semantics."""
    if document.external_references or any(
        r.type_name.startswith("EXTERNAL") for e in document.entities for r in e.records
    ):
        raise ValueError("external STEP references are unsupported; no retrieval is performed")
    entities = {e.entity_id:e for e in document.entities}
    lengths = {e.entity_id:e for e in document.entities if any(r.type_name=="LENGTH_UNIT" for r in e.records)}
    def reference(value):
        if value.kind!="entity_reference" or not str(value.value).startswith("#"):
            raise ValueError("unit requires a local entity reference")
        identifier=int(value.value[1:])
        if identifier not in entities:raise ValueError("missing unit reference")
        return identifier
    def record(identifier,name):
        records=[r for r in entities[identifier].records if r.type_name==name]
        if len(records)!=1:raise ValueError("ambiguous or missing unit record: "+name)
        return records[0]
    def numeric(value):
        if value.kind not in {"integer","real"}:raise ValueError("numeric unit value required")
        number=float(value.value)
        if not math.isfinite(number):raise ValueError("finite unit value required")
        return number
    def decode(identifier,stack=()):
        if identifier in stack or len(stack)>=8:raise ValueError("cyclic or excessive unit conversion chain")
        if identifier not in lengths:raise ValueError("conversion base is not a length unit")
        entity=lengths[identifier]
        si=[r for r in entity.records if r.type_name=="SI_UNIT"]
        conversion=[r for r in entity.records if r.type_name=="CONVERSION_BASED_UNIT"]
        named=record(identifier,"NAMED_UNIT")
        if len(named.arguments)!=1:raise ValueError("malformed named unit")
        if named.arguments[0].kind!="derived":
            dimensions=record(reference(named.arguments[0]),"DIMENSIONAL_EXPONENTS")
            if tuple(numeric(v) for v in dimensions.arguments)!=(1.,0.,0.,0.,0.,0.,0.):
                raise ValueError("unit dimensional exponents are not length")
        if len(si)==1 and not conversion and len(si[0].arguments)==2:
            prefix,unit=si[0].arguments
            if unit.kind!="enumeration" or unit.value!="METRE":raise ValueError("unsupported SI length unit")
            key=None if prefix.kind=="omitted" else prefix.value if prefix.kind=="enumeration" else "invalid"
            scale={None:1000.,"CENTI":10.,"MILLI":1.}.get(key)
            if scale is None:raise ValueError("unsupported SI length prefix")
            chain=[identifier]
        elif len(conversion)==1 and not si and len(conversion[0].arguments)==2:
            if named.arguments[0].kind=="derived":raise ValueError("conversion unit requires explicit length dimensions")
            factor=record(reference(conversion[0].arguments[1]),"LENGTH_MEASURE_WITH_UNIT")
            if len(factor.arguments)!=2:raise ValueError("malformed length conversion factor")
            value,base=factor.arguments
            if value.kind!="typed" or value.value!="LENGTH_MEASURE" or len(value.children)!=1:
                raise ValueError("conversion requires a typed length measure")
            multiplier=numeric(value.children[0])
            if multiplier<=0:raise ValueError("positive unit conversion factor required")
            scale,chain=decode(reference(base),(*stack,identifier))
            scale*=multiplier;chain=[identifier,*chain]
        else:raise ValueError("unsupported length unit form")
        if not math.isfinite(scale) or not 1e-9<=scale<=1e9:raise ValueError("unit scale outside inspection bounds")
        return scale,chain
    if not lengths:
        raise ValueError("no explicit length unit")
    contexts = []
    for entity in document.entities:
        records = [r for r in entity.records if r.type_name == "GLOBAL_UNIT_ASSIGNED_CONTEXT"]
        if not records:
            continue
        if len(records) != 1 or len(records[0].arguments) != 1:
            raise ValueError("malformed unit context")
        refs = [v.value for v in records[0].arguments[0].children if v.kind == "entity_reference"]
        unit_ids=[i for ref in refs for i in lengths if ref==f"#{i}"]
        if len(unit_ids)!=1:
            raise ValueError("each representation context must reference exactly one length unit")
        scale,chain=decode(unit_ids[0])
        contexts.append({"context_id":entity.entity_id,"length_unit_id":unit_ids[0],
                         "millimetres_per_source_unit":scale,"unit_chain":chain})
    # CONTEXT_DEPENDENT_SHAPE_REPRESENTATION relates a representation pair to a
    # product occurrence; its last argument is not a representation context.
    representations = [r for e in document.entities for r in e.records
                       if (r.type_name == "SHAPE_REPRESENTATION" or r.type_name.endswith("_SHAPE_REPRESENTATION"))
                       and r.type_name != "CONTEXT_DEPENDENT_SHAPE_REPRESENTATION"]
    if not contexts or not representations or any(
        not r.arguments or r.arguments[-1].kind != "entity_reference"
        or r.arguments[-1].value not in {f"#{c['context_id']}" for c in contexts} for r in representations
    ):
        raise ValueError("every shape representation must use a qualified length context")
    if any(not math.isclose(c["millimetres_per_source_unit"],contexts[0]["millimetres_per_source_unit"],rel_tol=1e-12) for c in contexts):
        raise ValueError("mixed length scales are outside the inspection contract")
    return tuple(contexts)


def read_step_for_inspection(path: Path, *, budget=WorkBudget()) -> InspectionInput:
    """Snapshot, parse and transfer local geometry without reconstruction limits.

    The budget is cooperative. Native OCCT calls are not sandboxed or timed out.
    Successful transfer is not full schema/AP validation or proof of editability.
    """
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader

    path = Path(path)
    # Keep the exact bytes; source_text is a decoded parser view, not a snapshot.
    with path.open("rb") as stream:
        payload = stream.read(budget.max_bytes + 1)
    if len(payload) > budget.max_bytes:
        raise ValueError("STEP inspection byte budget exceeded")
    with tempfile.TemporaryDirectory(prefix="research-notes-public-step-") as directory:
        snapshot = Path(directory) / "input.step"
        snapshot.write_bytes(payload)
        staged, document = inspect_step_stages(snapshot, budget)
        if document is None:
            raise ValueError("STEP inspection preflight: " + staged["reason"])
        contexts = length_contexts(document)
        reader = STEPControl_Reader()
        if reader.ReadFile(str(snapshot)) != IFSelect_RetDone:
            raise ValueError("native STEP reader rejected input")
        reader.SetSystemLengthUnit(1.0)
        roots = reader.NbRootsForTransfer()
        if not 1 <= roots <= budget.max_geometry:
            raise ValueError("STEP root budget exceeded")
        if reader.TransferRoots() != roots:
            raise ValueError("partial native root transfer")
        shape = reader.OneShape()
    if shape.IsNull():
        raise ValueError("STEP transfer produced no geometry")
    counts = topology_counts(shape)
    if sum(counts) > budget.max_topology or counts[-1] > budget.max_geometry:
        raise ValueError("STEP topology/solid budget exceeded")
    metrics = measure_shape(shape)
    if not metrics.analyzer_valid or metrics.face_count == 0:
        raise ValueError("inspection requires a valid nonempty face-bearing shape")
    imported = ImportedShape(path.name, hashlib.sha256(payload).hexdigest(), payload, shape, metrics, "mm")
    return InspectionInput(imported, roots, contexts)


def analyze_public_shape(shape, *, max_faces=256):
    """Retain per-face failures and an explicit partial result at the face limit."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepClass import BRepClass_FaceClassifier
    from OCP.gp import gp_Pnt2d
    from OCP.TopAbs import TopAbs_FACE, TopAbs_IN, TopAbs_ON, TopAbs_REVERSED
    from OCP.TopoDS import TopoDS
    from research_notes.differential_geometry import surface_differential
    from research_notes.intersection_analysis import inspect_trimming

    if type(max_faces) is not int or not 1 <= max_faces <= 2048:
        raise ValueError("face analysis budget must be 1..2048")
    faces = indexed_shapes(shape, TopAbs_FACE)
    rows = []
    for index in range(1, min(faces.Extent(), max_faces) + 1):
        face = TopoDS.Face_s(faces.FindKey(index))
        row = {"face_index": index}
        try:
            surface = BRepAdaptor_Surface(face, True)
            row["support_type"] = str(surface.GetType())
            u = (surface.FirstUParameter() + surface.LastUParameter()) / 2
            v = (surface.FirstVParameter() + surface.LastVParameter()) / 2
            if not all(math.isfinite(x) and abs(x) < 1e50 for x in (u, v)):
                raise ValueError("unbounded representative parameters")
            classifier = BRepClass_FaceClassifier(face, gp_Pnt2d(u, v), 1e-7)
            row["sample_within_trim"] = classifier.State() in {TopAbs_IN, TopAbs_ON}
            row["differential"] = surface_differential(
                surface, u, v, orientation=-1 if face.Orientation() == TopAbs_REVERSED else 1)
        except (ValueError, RuntimeError) as exc:
            row["differential"] = {"status": "unsupported", "reason": str(exc)}
        try:
            row["trimming"] = inspect_trimming(face)
        except (ValueError, RuntimeError) as exc:
            row["trimming"] = {"checks_pass": False, "status": "unsupported", "reason": str(exc)}
        rows.append(row)
    return {"status": "partial" if faces.Extent() > max_faces else "complete",
            "face_count": faces.Extent(), "analyzed_face_count": len(rows),
            "omitted_face_count": faces.Extent() - len(rows), "max_faces": max_faces,
            "trim_check_failures": sum(not row["trimming"]["checks_pass"] for row in rows),
            "differential_failures": sum(row["differential"]["status"] != "regular" for row in rows),
            "faces": rows,
            "scope": "ordered face samples; complete means visited, not proven valid; trim failures and outside-trim support samples are retained"}


def solid_measurements(shape):
    """Measure each solid using a stated unit-density reference, never a material guess."""
    from OCP.TopAbs import TopAbs_SOLID
    from research_notes.engineering_analysis import mass_properties
    solids = indexed_shapes(shape, TopAbs_SOLID)
    rows = []
    for index in range(1, solids.Extent() + 1):
        try:
            properties = mass_properties(solids.FindKey(index), density=1.0)
            rows.append({"solid_index": index, "status": "measured", "unit_density_properties": properties})
        except ValueError as exc:
            rows.append({"solid_index": index, "status": "unsupported", "reason": str(exc)})
    return {"solids": rows, "material_density_known": False,
            "scope": "each solid separately at 1 kg/m3; no physical material assignment, overlap union, or assembly mass claim"}


def measured_round_trip(shape):
    """Check declared invariants; keep disagreements, do not equate these with full equivalence."""
    before = measure_shape(shape)
    exchange = step_round_trip(shape, "public_inspection", writer_uncertainty=1e-7)
    after = measure_shape(exchange.imported_shape)
    volume_error = abs(after.absolute_volume - before.absolute_volume)
    area_error = abs(after.surface_area - before.surface_area)
    bounds_error = max(abs(a-b) for a,b in zip(before.bounds_min + before.bounds_max, after.bounds_min + after.bounds_max))
    thresholds = {"volume_mm3": max(1e-6, before.absolute_volume * 1e-6),
                  "area_mm2": max(1e-6, before.surface_area * 1e-6), "bounds_mm": 1e-4}
    counts_match = topology_counts(shape) == topology_counts(exchange.imported_shape)
    verified = (before.analyzer_valid and after.analyzer_valid and counts_match
                and volume_error <= thresholds["volume_mm3"] and area_error <= thresholds["area_mm2"]
                and bounds_error <= thresholds["bounds_mm"])
    return exchange, {"status": "verified_invariants" if verified else "disputed",
                      "before": asdict(before), "after": asdict(after), "topology_matches": counts_match,
                      "volume_error_mm3": volume_error, "area_error_mm2": area_error,
                      "bounds_error_mm": bounds_error, "thresholds": thresholds,
                      "source_geometry_units": "mm", "same_kernel": True,
                      "scope": "topology counts, volume, area, axis bounds and native validity; not pointwise or independent-kernel equivalence",
                      "preservation_policy": "geometry only; colors, names, product structure, PMI, materials and mates are not preserved"}


def export_inspected_geometry(imported, source_path, target, *, overwrite=False):
    target = Path(target).resolve()
    source_path = Path(source_path).resolve()
    if target.suffix.lower() not in {".step", ".stp"}:
        raise ValueError("export path must end with .step or .stp")
    if target == source_path or (target.exists() and source_path.exists() and target.samefile(source_path)):
        raise ValueError("the imported source file is read-only")
    if target.exists() and not overwrite:
        raise FileExistsError("export exists; explicit overwrite is required")
    exchange, report = measured_round_trip(imported.shape)
    if report["status"] != "verified_invariants":
        raise ValueError("inspection export disagrees with the measured geometry contract")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb" if overwrite else "xb") as stream:
        stream.write(exchange.source_bytes)
    return {"file_name": target.name, "sha256": exchange.source_sha256,
            "source_sha256": imported.source_sha256, "round_trip": report,
            "mode": "inspection_only", "source_history_recovered": False}
