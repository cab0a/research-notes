"""Scoped reference continuity with separate semantic, geometric, and operation evidence."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace

from research_notes.brep_runtime import indexed_shapes


@dataclass(frozen=True)
class SubshapeDescriptor:
    kind: str
    index: int
    support: str
    coordinates: tuple[tuple[float, float, float], ...]
    normalized_coordinates: tuple[tuple[float, float, float], ...]


@dataclass(frozen=True)
class TopologySnapshot:
    owner: str
    stage_id: str
    shape: object
    descriptors: tuple[SubshapeDescriptor, ...]


@dataclass(frozen=True)
class TopologyReference:
    reference_id: str
    owner: str
    stage_id: str
    kind: str
    index: int


@dataclass(frozen=True)
class ReferenceRelation:
    owner: str
    source_stage: str
    target_stage: str
    kind: str
    source_index: int
    target_indices: tuple[int, ...]
    relation: str
    evidence: str
    permanent_kernel_identity: bool = False


def _mapping(shape, kind):
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    return indexed_shapes(shape, TopAbs_FACE if kind == "face" else TopAbs_EDGE)


def _points(shape):
    from OCP.BRep import BRep_Tool
    from OCP.TopAbs import TopAbs_VERTEX
    from OCP.TopoDS import TopoDS
    mapping = indexed_shapes(shape, TopAbs_VERTEX)
    points = []
    for i in range(1, mapping.Extent()+1):
        p = BRep_Tool.Pnt_s(TopoDS.Vertex_s(mapping.FindKey(i)))
        points.append(tuple(round(v, 9)+0. for v in (p.X(), p.Y(), p.Z())))
    return tuple(sorted(set(points)))


def topology_snapshot(shape: object, owner: str, revision: str) -> TopologySnapshot:
    """Describe only planar faces and straight edges; curved evidence is unqualified."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Line, GeomAbs_Plane
    from OCP.TopoDS import TopoDS
    if not owner or not revision:
        raise ValueError("snapshot requires owner and revision")
    points = _points(shape)
    if not points:
        raise ValueError("snapshot has no vertices")
    low = tuple(min(p[i] for p in points) for i in range(3))
    high = tuple(max(p[i] for p in points) for i in range(3))
    descriptors = []
    for kind in ("face", "edge"):
        mapping = _mapping(shape, kind)
        for i in range(1, mapping.Extent()+1):
            item = mapping.FindKey(i)
            coordinates = _points(item)
            if kind == "face":
                adaptor = BRepAdaptor_Surface(TopoDS.Face_s(item))
                support = "plane" if adaptor.GetType() == GeomAbs_Plane else "unsupported"
            else:
                adaptor = BRepAdaptor_Curve(TopoDS.Edge_s(item))
                support = "line" if adaptor.GetType() == GeomAbs_Line else "unsupported"
            normalized = tuple(tuple(round((p[j]-low[j])/(high[j]-low[j]), 9) if high[j] > low[j] else 0.
                                     for j in range(3)) for p in coordinates)
            descriptors.append(SubshapeDescriptor(kind, i, support, coordinates, normalized))
    data = json.dumps([asdict(d) for d in descriptors], sort_keys=True).encode()
    stage = revision + ":" + hashlib.sha256(data).hexdigest()[:16]
    return TopologySnapshot(owner, stage, shape, tuple(descriptors))


def select_reference(snapshot: TopologySnapshot, kind: str, index: int, *, name: str) -> TopologyReference:
    if not name or not any(d.kind == kind and d.index == index for d in snapshot.descriptors):
        raise ValueError("unknown reference selection")
    identity = hashlib.sha256((snapshot.owner + ":" + name).encode()).hexdigest()
    return TopologyReference(identity, snapshot.owner, snapshot.stage_id, kind, index)


def reference_relations(source: TopologySnapshot, target: TopologySnapshot, *,
                        mode: str = "geometry", history: object | None = None) -> tuple[ReferenceRelation, ...]:
    """Operation history can prove splits/merges/deletion; geometric ties abstain."""
    if source.owner != target.owner:
        raise ValueError("reference owner mismatch")
    if mode not in {"geometry", "normalized_box", "operation_history"}:
        raise ValueError("unsupported reference mode")
    if mode == "operation_history" and history is None:
        raise ValueError("operation history is required")
    if mode == "normalized_box":
        # Only an unfeatured rectangular box qualifies for normalized role inference.
        for snapshot in (source, target):
            faces = [d for d in snapshot.descriptors if d.kind == "face"]
            edges = [d for d in snapshot.descriptors if d.kind == "edge"]
            if len(faces) != 6 or len(edges) != 12 or any(d.support == "unsupported" for d in snapshot.descriptors) or any(
                v not in (0., 1.) for d in snapshot.descriptors for p in d.normalized_coordinates for v in p
            ):
                raise ValueError("normalized roles require an axis-aligned unfeatured box")
    matches, removed = {}, {}
    for d in source.descriptors:
        key = d.kind, d.index
        candidates = []
        if mode == "operation_history":
            old = _mapping(source.shape, d.kind).FindKey(d.index)
            mapping = _mapping(target.shape, d.kind)
            evolved = tuple(history.Modified(old))
            for i in range(1, mapping.Extent()+1):
                item = mapping.FindKey(i)
                if old.IsSame(item) or any(item.IsSame(modified) for modified in evolved):
                    candidates.append(i)
            removed[key] = bool(history.IsDeleted(old)) if hasattr(history, "IsDeleted") else bool(history.IsRemoved(old))
        elif d.support != "unsupported":
            coordinates = d.normalized_coordinates if mode == "normalized_box" else d.coordinates
            candidates = [other.index for other in target.descriptors
                          if other.kind == d.kind and other.support == d.support
                          and (other.normalized_coordinates if mode == "normalized_box" else other.coordinates) == coordinates]
        matches[key] = tuple(candidates)
    incoming = {}
    for (kind, _), targets in matches.items():
        for i in targets:
            incoming[kind, i] = incoming.get((kind, i), 0)+1
    rows = []
    for (kind, index), targets in matches.items():
        if not targets:
            relation = "deleted" if removed.get((kind, index)) else "unresolved"
        elif len(targets) > 1:
            relation = "split" if mode == "operation_history" else "ambiguous"
        elif incoming[kind, targets[0]] > 1:
            relation = "merge" if mode == "operation_history" else "ambiguous"
        else:
            relation = "one_to_one"
        rows.append(ReferenceRelation(source.owner, source.stage_id, target.stage_id, kind, index, targets, relation, mode))
    return tuple(rows)


def advance_reference(reference: TopologyReference, relations: tuple[ReferenceRelation, ...],
                      *, accept_merge: bool = False) -> TopologyReference:
    """Preserve a caller's reference ID only after a unique qualified transition."""
    rows = [r for r in relations if r.owner == reference.owner and r.source_stage == reference.stage_id
            and r.kind == reference.kind and r.source_index == reference.index]
    if len(rows) != 1:
        raise ValueError("reference transition is missing or belongs to another snapshot")
    row = rows[0]
    allowed = {"one_to_one", "merge"} if accept_merge else {"one_to_one"}
    if row.relation not in allowed or len(row.target_indices) != 1:
        raise ValueError("reference requires review: " + row.relation)
    return replace(reference, stage_id=row.target_stage, index=row.target_indices[0])
