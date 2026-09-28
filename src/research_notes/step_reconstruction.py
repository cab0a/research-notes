"""Evidence-bound reconstruction proposals for a small axis-aligned STEP subset."""

from __future__ import annotations

import hashlib
import tempfile
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from research_notes.brep_runtime import indexed_shapes, topology_counts
from research_notes.deterministic_recompute import FeatureModel, recompute, single_feature_model
from research_notes.modeling_common import ShapeMetrics, measure_shape
from research_notes.parametric_features import PlateSpec, feature_spec, shape_difference_volume
from research_notes.step_part21 import STEPParseLimits, parse_part21_document


CONTRACT_VERSION = "1.0.0"
FIT_TOLERANCE = 1.0e-7
MAX_STEP_BYTES = 2_000_000


@dataclass(frozen=True)
class FaceEvidence:
    face_index: int
    surface_type: str
    axis: int | None
    bounds_min: tuple[float, float, float]
    bounds_max: tuple[float, float, float]
    center_x: float | None = None
    center_y: float | None = None
    radius: float | None = None


@dataclass(frozen=True)
class ImportedShape:
    file_name: str
    source_sha256: str
    source_bytes: bytes
    shape: object
    metrics: ShapeMetrics
    unit: str


@dataclass(frozen=True)
class ReconstructionCandidate:
    candidate_id: str
    explanation: str
    model: FeatureModel
    supporting_faces: tuple[int, ...]
    volume_residual: float
    area_residual: float
    material_difference_volume: float
    bounds_residual: float
    topology_matches: bool
    fit_score: float
    confidence_kind: str = "uncalibrated_geometric_fit"
    status: str = "unconfirmed"
    authoring_history_recovered: bool = False


@dataclass(frozen=True)
class ReconstructionResult:
    imported: ImportedShape
    faces: tuple[FaceEvidence, ...]
    candidates: tuple[ReconstructionCandidate, ...]
    rejected_proposals: tuple[tuple[str, str], ...]
    status: str
    reason: str


def read_step_input(path: Path) -> ImportedShape:
    """Read one immutable byte snapshot; reject unqualified units/references.

    This bounded research importer does not provide an OS sandbox or a native
    execution timeout. It only supports local, single-root millimetre input.
    """
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader

    path = Path(path)
    with path.open("rb") as stream:
        payload = stream.read(MAX_STEP_BYTES + 1)
    if len(payload) > MAX_STEP_BYTES:
        raise ValueError("STEP exceeds the 2000000-byte input limit")
    document = parse_part21_document(payload, limits=STEPParseLimits(max_file_bytes=MAX_STEP_BYTES))
    if document.external_references or any(r.type_name.startswith("EXTERNAL") for e in document.entities for r in e.records):
        raise ValueError("external STEP references are unsupported; no retrieval is performed")
    length_entities = [e for e in document.entities if any(r.type_name == "LENGTH_UNIT" for r in e.records)]
    if len(length_entities) != 1:
        raise ValueError("exactly one explicit SI millimetre length unit is required")
    unit_records = [r for r in length_entities[0].records if r.type_name == "SI_UNIT"]
    if len(unit_records) != 1 or tuple(v.value for v in unit_records[0].arguments) != ("MILLI", "METRE"):
        raise ValueError("only explicit SI millimetre inputs are supported")
    contexts = [(e.entity_id, r) for e in document.entities for r in e.records
                if r.type_name == "GLOBAL_UNIT_ASSIGNED_CONTEXT"]
    if len(contexts) != 1:
        raise ValueError("exactly one global unit context is required")
    context_id, unit_context = contexts[0]
    if len(unit_context.arguments) != 1 or not any(
        v.kind == "entity_reference" and v.value == f"#{length_entities[0].entity_id}"
        for v in unit_context.arguments[0].children
    ):
        raise ValueError("the representation context must reference the millimetre length unit")
    representations = [r for e in document.entities for r in e.records
                       if r.type_name == "SHAPE_REPRESENTATION" or r.type_name.endswith("_SHAPE_REPRESENTATION")]
    if not representations or any(not r.arguments or r.arguments[-1].kind != "entity_reference"
                                  or r.arguments[-1].value != f"#{context_id}" for r in representations):
        raise ValueError("shape representations must use the qualified millimetre context")
    with tempfile.TemporaryDirectory(prefix="research-notes-reconstruction-") as directory:
        snapshot = Path(directory) / "input.step"
        snapshot.write_bytes(payload)
        reader = STEPControl_Reader()
        if reader.ReadFile(str(snapshot)) != IFSelect_RetDone:
            raise ValueError("STEP reader rejected the input")
        if reader.NbRootsForTransfer() != 1 or reader.TransferRoots() != 1:
            raise ValueError("only a single STEP root is supported")
        shape = reader.OneShape()
    if shape.IsNull():
        raise ValueError("STEP transfer produced no shape")
    metrics = measure_shape(shape)
    if not metrics.analyzer_valid or metrics.solid_count != 1 or metrics.shell_count != 1 or not 1 <= metrics.face_count <= 24:
        raise ValueError("input must be one valid solid with one shell and at most 24 faces")
    return ImportedShape(path.name, hashlib.sha256(payload).hexdigest(), payload, shape, metrics, "mm")


def _vertices(shape: object) -> tuple[tuple[float, float, float], ...]:
    from OCP.BRep import BRep_Tool
    from OCP.TopAbs import TopAbs_VERTEX
    from OCP.TopoDS import TopoDS

    mapping = indexed_shapes(shape, TopAbs_VERTEX)
    return tuple(tuple(round(float(v), 9) + 0.0 for v in (
        BRep_Tool.Pnt_s(TopoDS.Vertex_s(mapping.FindKey(i))).X(),
        BRep_Tool.Pnt_s(TopoDS.Vertex_s(mapping.FindKey(i))).Y(),
        BRep_Tool.Pnt_s(TopoDS.Vertex_s(mapping.FindKey(i))).Z(),
    )) for i in range(1, mapping.Extent() + 1))


def face_evidence(shape: object) -> tuple[FaceEvidence, ...]:
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopoDS import TopoDS

    mapping = indexed_shapes(shape, TopAbs_FACE)
    evidence = []
    for index in range(1, mapping.Extent() + 1):
        face = TopoDS.Face_s(mapping.FindKey(index))
        adaptor = BRepAdaptor_Surface(face, True)
        vertices = _vertices(face)
        if not vertices:
            raise ValueError("face has no supported bounded vertex representation")
        minima, maxima = tuple(min(p[i] for p in vertices) for i in range(3)), tuple(max(p[i] for p in vertices) for i in range(3))
        kind = adaptor.GetType()
        center_x = center_y = radius = None
        if kind == GeomAbs_Plane:
            surface_type, direction = "plane", adaptor.Plane().Axis().Direction()
        elif kind == GeomAbs_Cylinder:
            cylinder = adaptor.Cylinder()
            surface_type, direction = "cylinder", cylinder.Axis().Direction()
            center_x, center_y, radius = (round(float(v), 9) + 0.0 for v in (cylinder.Location().X(), cylinder.Location().Y(), cylinder.Radius()))
        else:
            raise ValueError("only planar and cylindrical support surfaces are qualified")
        components = (direction.X(), direction.Y(), direction.Z())
        axis = next((i for i, value in enumerate(components) if abs(abs(value) - 1.0) < 1e-10
                     and all(abs(components[j]) < 1e-10 for j in range(3) if j != i)), None)
        if axis is None or (surface_type == "cylinder" and axis != 2):
            raise ValueError("only axis-aligned planes and Z-axis cylinders are qualified")
        evidence.append(FaceEvidence(index, surface_type, axis, minima, maxima, center_x, center_y, radius))
    return tuple(evidence)


def compare_shapes(first: object, second: object) -> dict[str, object]:
    a, b = measure_shape(first), measure_shape(second)
    return {
        "volume_residual": abs(a.absolute_volume - b.absolute_volume),
        "area_residual": abs(a.surface_area - b.surface_area),
        "material_difference_volume": shape_difference_volume(first, second),
        "bounds_residual": max(abs(x - y) for x, y in zip(a.bounds_min + a.bounds_max, b.bounds_min + b.bounds_max, strict=True)),
        "topology_matches": topology_counts(first) == topology_counts(second),
        "surface_inventory_matches": a.surface_counts == b.surface_counts,
    }


def reconstruct_step(path: Path) -> ReconstructionResult:
    """Infer bounded proposals only from source B-Rep measurements, never labels."""
    imported = read_step_input(path)
    try:
        faces = face_evidence(imported.shape)
    except ValueError as exc:
        return ReconstructionResult(imported, (), (), (), "unsupported", str(exc))
    vertices = _vertices(imported.shape)
    low = tuple(min(p[i] for p in vertices) for i in range(3))
    high = tuple(max(p[i] for p in vertices) for i in range(3))
    width, length, thickness = (round(b - a, 9) for a, b in zip(low, high, strict=True))
    base = PlateSpec(width, length, thickness, *low)
    cylinders = [f for f in faces if f.surface_type == "cylinder"]
    if len(cylinders) > 1:
        return ReconstructionResult(imported, faces, (), (), "unsupported", "multiple cylindrical features are outside the candidate grammar")
    proposals: list[tuple[str, PlateSpec, object]] = [("plate_extrusion", base, None)]
    if len(cylinders) == 1:
        cylinder = cylinders[0]
        x, y, radius = cylinder.center_x - low[0], cylinder.center_y - low[1], cylinder.radius
        proposals.extend((route, base, feature_spec(route, x=x, y=y, radius=radius)) for route in ("through_hole", "profile_hole"))
        depth = cylinder.bounds_max[2] - cylinder.bounds_min[2]
        if abs(cylinder.bounds_max[2] - high[2]) < FIT_TOLERANCE and cylinder.bounds_min[2] > low[2] + FIT_TOLERANCE:
            proposals.append(("blind_hole", base, feature_spec("blind_hole", x=x, y=y, radius=radius, depth=depth)))
            boss_base = replace(base, thickness=cylinder.bounds_min[2] - low[2])
            proposals.append(("cylindrical_boss", boss_base, feature_spec("boss", x=x, y=y, radius=radius, height=depth)))
    else:
        floors = [f for f in faces if f.axis == 2 and low[2] + FIT_TOLERANCE < f.bounds_min[2] < high[2] - FIT_TOLERANCE]
        top_faces = [f for f in faces if f.axis == 2 and abs(f.bounds_min[2] - high[2]) < FIT_TOLERANCE]
        for floor in floors:
            x0, y0, z = floor.bounds_min
            x1, y1, _ = floor.bounds_max
            proposals.append(("rectangular_pocket", base, feature_spec("pocket", x=x0-low[0], y=y0-low[1], width=x1-x0, length=y1-y0, depth=high[2]-z)))
            for top in top_faces:
                x0, y0, _ = top.bounds_min
                x1, y1, _ = top.bounds_max
                feature = feature_spec("rib", x=x0-low[0], y=y0-low[1], width=x1-x0, length=y1-y0, height=high[2]-z)
                # Identical geometry can support either semantic label. These
                # are explicitly alternative explanations, not recovered intent.
                proposals.extend((name, replace(base, thickness=z-low[2]), feature)
                                 for name in ("rectangular_rib", "rectangular_boss"))
    candidates, rejected, seen = [], [], set()
    for explanation, plate, feature in proposals:
        identity = repr((explanation, plate, feature))
        if identity in seen:
            continue
        seen.add(identity)
        model = single_feature_model("reconstruction", plate, feature, provenance="unconfirmed_candidate", source_sha256=imported.source_sha256)
        try:
            result = recompute(model)
            shape = result.current_output().shape
            residuals = compare_shapes(imported.shape, shape)
            errors = [residuals[name] for name in ("volume_residual", "area_residual", "material_difference_volume", "bounds_residual")]
            if not residuals["topology_matches"] or not residuals["surface_inventory_matches"] or any(error > FIT_TOLERANCE for error in errors):
                rejected.append((explanation, "geometry_or_topology_residual_exceeds_gate"))
                continue
            # This deterministic score describes fit within one fixed corpus;
            # it is neither calibrated probability nor evidence of history.
            score = 1.0 / (1.0 + max(errors) / FIT_TOLERANCE)
            candidate_id = explanation + "_" + hashlib.sha256((imported.source_sha256 + identity).encode()).hexdigest()[:12]
            candidates.append(ReconstructionCandidate(candidate_id, explanation, model,
                              tuple(f.face_index for f in faces), *errors,
                              residuals["topology_matches"], score))
        except (ValueError, RuntimeError) as exc:
            rejected.append((explanation, str(exc)))
    candidates.sort(key=lambda c: c.candidate_id)
    status = "ambiguous" if len(candidates) > 1 else "candidate_available" if candidates else "unsupported"
    reason = "multiple_equivalent_explanations" if len(candidates) > 1 else "candidate_requires_confirmation" if candidates else "no_proposal_meets_declared_fit_gate"
    return ReconstructionResult(imported, faces, tuple(candidates), tuple(rejected), status, reason)


def reconstruction_record(result: ReconstructionResult) -> dict:
    return {"contract_version": CONTRACT_VERSION, "file_name": result.imported.file_name,
            "source_sha256": result.imported.source_sha256, "length_unit": result.imported.unit,
            "metrics": asdict(result.imported.metrics), "status": result.status, "reason": result.reason,
            "faces": [asdict(f) for f in result.faces],
            "candidates": [asdict(c) for c in result.candidates], "rejected_proposals": result.rejected_proposals}
