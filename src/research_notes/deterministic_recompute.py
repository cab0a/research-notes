"""Deterministic feature-DAG evaluation with explicit failed and stale branches."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, replace

from research_notes.modeling_common import ShapeMetrics
from research_notes.parametric_features import (
    FEATURE_PARAMETERS, FeatureSpec, PlateSpec, apply_feature, build_plate,
)


CONTRACT_VERSION = "1.0.0"
PLATE_PARAMETERS = tuple(PlateSpec.__dataclass_fields__)
PROVENANCE_KINDS = {"authored", "unconfirmed_candidate", "user_selected_reconstruction"}


@dataclass(frozen=True)
class ModelNode:
    node_id: str
    operation: str
    dependencies: tuple[str, ...]
    parameters: tuple[tuple[str, float], ...] = ()


@dataclass(frozen=True)
class FeatureModel:
    model_id: str
    nodes: tuple[ModelNode, ...]
    output_id: str
    revision: int = 1
    provenance: str = "authored"
    source_sha256: str = ""


@dataclass(frozen=True)
class NodeState:
    node_id: str
    status: str
    attempted_fingerprint: str
    last_valid_fingerprint: str
    last_valid_revision: int | None
    shape: object | None
    plate: PlateSpec | None
    metrics: ShapeMetrics | None
    error: str = ""
    sketch_fingerprint: str = ""


@dataclass(frozen=True)
class RecomputeResult:
    model_id: str
    revision: int
    model_fingerprint: str
    output_id: str
    states: tuple[NodeState, ...]
    evaluated_nodes: tuple[str, ...]
    reused_nodes: tuple[str, ...]

    def state(self, node_id: str) -> NodeState:
        for state in self.states:
            if state.node_id == node_id:
                return state
        raise KeyError(node_id)

    def current_output(self) -> NodeState:
        state = self.state(self.output_id)
        if state.status != "valid" or state.shape is None:
            raise ValueError(f"output is {state.status}; retained geometry is not current")
        return state


def _digest(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def model_fingerprint(model: FeatureModel) -> str:
    payload = asdict(model)
    payload["nodes"] = [asdict(node) for node in sorted(model.nodes, key=lambda n: n.node_id)]
    return _digest(payload)


def model_from_dict(payload: dict) -> FeatureModel:
    """Decode the versioned record through the same structural validation gate."""
    if set(payload) != set(FeatureModel.__dataclass_fields__):
        raise ValueError("unexpected model record fields")
    nodes = tuple(ModelNode(n["node_id"], n["operation"], tuple(n["dependencies"]),
                            tuple((key, float(value)) for key, value in n["parameters"])) for n in payload["nodes"])
    model = FeatureModel(**{**payload, "nodes": nodes})
    validate_model(model)
    return model


def validate_model(model: FeatureModel) -> tuple[str, ...]:
    """Return a stable topological order; reject structural defects pre-build."""
    if not model.model_id or not isinstance(model.revision, int) or model.revision < 1:
        raise ValueError("model requires an ID and positive integer revision")
    if model.provenance not in PROVENANCE_KINDS:
        raise ValueError("unsupported model provenance")
    if model.provenance != "authored" and not re.fullmatch(r"[0-9a-f]{64}", model.source_sha256):
        raise ValueError("reconstruction requires a source SHA-256 binding")
    if not 1 <= len(model.nodes) <= 64:
        raise ValueError("model must contain 1..64 nodes")
    nodes = {n.node_id: n for n in model.nodes}
    if len(nodes) != len(model.nodes) or model.output_id not in nodes:
        raise ValueError("duplicate node ID or unresolved output")
    for node in model.nodes:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", node.node_id):
            raise ValueError("node IDs must use lower-case snake case")
        allowed = PLATE_PARAMETERS if node.operation == "plate" else () if node.operation == "result" else FEATURE_PARAMETERS.get(node.operation)
        if allowed is None or len(dict(node.parameters)) != len(node.parameters) or set(dict(node.parameters)) != set(allowed):
            raise ValueError(f"invalid operation parameters: {node.node_id}")
        if any(not isinstance(value, (int, float)) or not math.isfinite(value) for _, value in node.parameters):
            raise ValueError("parameters must be finite numbers")
        if len(node.dependencies) != (0 if node.operation == "plate" else 1):
            raise ValueError("plate nodes have no dependency; operations require exactly one")
        if any(dep not in nodes for dep in node.dependencies):
            raise ValueError("unresolved dependency")
        if node.operation == "profile_hole" and nodes[node.dependencies[0]].operation != "plate":
            raise ValueError("profile_hole must directly depend on a plain plate")
    order: list[str] = []
    remaining = set(nodes)
    while remaining:
        ready = sorted(n for n in remaining if all(dep in order for dep in nodes[n].dependencies))
        if not ready:
            raise ValueError("cyclic feature dependency")
        order.extend(ready)
        remaining.difference_update(ready)
    return tuple(order)


def single_feature_model(
    model_id: str, plate: PlateSpec, feature: FeatureSpec | None = None,
    *, provenance: str = "authored", source_sha256: str = "",
) -> FeatureModel:
    nodes = [ModelNode("base", "plate", (), tuple(sorted(asdict(plate).items())))]
    if feature:
        nodes.append(ModelNode("feature", feature.kind, ("base",), tuple(sorted(feature.parameters))))
    nodes.append(ModelNode("result", "result", ("feature" if feature else "base",)))
    return FeatureModel(model_id, tuple(nodes), "result", provenance=provenance, source_sha256=source_sha256)


def edit_parameter(model: FeatureModel, node_id: str, parameter: str, value: float) -> FeatureModel:
    validate_model(model)
    if model.provenance == "unconfirmed_candidate":
        raise ValueError("confirm candidate selection before editing")
    if not math.isfinite(value):
        raise ValueError("edited value must be finite")
    node = next((n for n in model.nodes if n.node_id == node_id), None)
    if node is None or parameter not in dict(node.parameters):
        raise ValueError("unknown editable node or parameter")
    parameters = tuple((key, float(value) if key == parameter else old) for key, old in node.parameters)
    return replace(model, revision=model.revision + 1,
                   nodes=tuple(replace(n, parameters=parameters) if n.node_id == node_id else n for n in model.nodes))


def recompute(model: FeatureModel, previous: RecomputeResult | None = None) -> RecomputeResult:
    """Evaluate changed nodes in stable order while preserving last valid data.

    A failed node and its stale descendants retain their previous geometry for
    inspection only. Independent branches continue; this is not an atomic
    transaction or persistent topological naming system.
    """
    order = validate_model(model)
    if previous is not None and previous.model_id != model.model_id:
        raise ValueError("cache belongs to a different model")
    nodes = {n.node_id: n for n in model.nodes}
    old = {} if previous is None else {s.node_id: s for s in previous.states}
    states: dict[str, NodeState] = {}
    evaluated, reused = [], []
    for node_id in order:
        node, retained = nodes[node_id], old.get(node_id)
        dependencies = [states[dep] for dep in node.dependencies]
        fingerprint = _digest({"operation": node.operation, "parameters": sorted(node.parameters),
                               "dependencies": [(s.node_id, s.status, s.last_valid_fingerprint) for s in dependencies]})

        def failed_state(status: str, error: str) -> NodeState:
            return NodeState(node_id, status, fingerprint,
                             retained.last_valid_fingerprint if retained else "",
                             retained.last_valid_revision if retained else None,
                             retained.shape if retained else None, retained.plate if retained else None,
                             retained.metrics if retained else None, error,
                             retained.sketch_fingerprint if retained else "")

        if any(s.status != "valid" for s in dependencies):
            states[node_id] = failed_state("stale", "dependency_not_valid")
            continue
        if retained is not None and retained.shape is not None and retained.last_valid_fingerprint == fingerprint:
            states[node_id] = replace(retained, status="valid", attempted_fingerprint=fingerprint, error="")
            reused.append(node_id)
            continue
        evaluated.append(node_id)
        try:
            if node.operation == "plate":
                plate = PlateSpec(**dict(node.parameters))
                built = build_plate(plate)
            elif node.operation == "result":
                dependency = dependencies[0]
                states[node_id] = NodeState(node_id, "valid", fingerprint, fingerprint, model.revision,
                                            dependency.shape, dependency.plate, dependency.metrics,
                                            sketch_fingerprint=dependency.sketch_fingerprint)
                continue
            else:
                dependency = dependencies[0]
                plate = dependency.plate
                built = apply_feature(dependency.shape, plate, FeatureSpec(node.operation, node.parameters))
            states[node_id] = NodeState(node_id, "valid", fingerprint, fingerprint, model.revision,
                                        built.shape, plate, built.metrics, sketch_fingerprint=built.sketch.input_sha256)
        except (ValueError, RuntimeError) as exc:
            states[node_id] = failed_state("failed", str(exc))
    return RecomputeResult(model.model_id, model.revision, model_fingerprint(model), model.output_id,
                           tuple(states[n] for n in order), tuple(evaluated), tuple(reused))


def recompute_record(result: RecomputeResult) -> dict:
    """Serialize observations without pretending that a B-Rep object is JSON."""
    return {
        "model_id": result.model_id, "revision": result.revision,
        "model_fingerprint": result.model_fingerprint, "output_id": result.output_id,
        "evaluated_nodes": result.evaluated_nodes, "reused_nodes": result.reused_nodes,
        "states": [{"node_id": s.node_id, "status": s.status, "error": s.error,
                    "attempted_fingerprint": s.attempted_fingerprint,
                    "last_valid_fingerprint": s.last_valid_fingerprint,
                    "last_valid_revision": s.last_valid_revision,
                    "retained_geometry_available": s.shape is not None,
                    "metrics": asdict(s.metrics) if s.metrics else None,
                    "sketch_fingerprint": s.sketch_fingerprint} for s in result.states],
    }
