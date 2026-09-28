"""Immutable feature histories and named, explicitly authored configurations."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace

from research_notes.deterministic_recompute import FeatureModel, ModelNode, validate_model
from research_notes.parametric_features import FeatureSpec, PlateSpec, validate_feature, validate_plate


@dataclass(frozen=True)
class HistoryFeature:
    feature_id: str
    feature: FeatureSpec
    suppressed: bool = False


@dataclass(frozen=True)
class FeatureHistory:
    history_id: str
    plate: PlateSpec
    features: tuple[HistoryFeature, ...]
    revision: int = 1
    rollback_after: str | None = None


@dataclass(frozen=True)
class Configuration:
    name: str
    overrides: tuple[tuple[str, str, float], ...] = ()
    suppressed: tuple[str, ...] = ()
    order: tuple[str, ...] = ()
    rollback_after: str | None = None


def validate_history(history: FeatureHistory) -> None:
    import re
    validate_plate(history.plate)
    if not history.history_id or type(history.revision) is not int or history.revision < 1 or len(history.features) > 62:
        raise ValueError("invalid history identity, revision, or feature budget")
    identifiers = [f.feature_id for f in history.features]
    if len(set(identifiers)) != len(identifiers) or any(
        not re.fullmatch(r"[a-z][a-z0-9_]*", i) or i in {"base", "result"} for i in identifiers
    ):
        raise ValueError("invalid or duplicate history feature ID")
    if history.rollback_after not in (None, "base", *identifiers):
        raise ValueError("unknown rollback target")
    for f in history.features:
        if type(f.suppressed) is not bool:
            raise ValueError("suppression must be boolean")
        validate_feature(history.plate, f.feature)


def suppress_feature(history: FeatureHistory, feature_id: str, *, suppressed: bool = True) -> FeatureHistory:
    validate_history(history)
    if feature_id not in {f.feature_id for f in history.features} or type(suppressed) is not bool:
        raise ValueError("unknown feature or invalid suppression")
    return replace(history, revision=history.revision + 1,
                   features=tuple(replace(f, suppressed=suppressed) if f.feature_id == feature_id else f for f in history.features))


def reorder_features(history: FeatureHistory, order: tuple[str, ...]) -> FeatureHistory:
    validate_history(history)
    by_id = {f.feature_id: f for f in history.features}
    if len(order) != len(by_id) or set(order) != set(by_id):
        raise ValueError("order must contain each feature exactly once")
    result = replace(history, features=tuple(by_id[key] for key in order), revision=history.revision+1)
    compile_history(result)  # Reject unsupported dependency order before adoption.
    return result


def rollback_history(history: FeatureHistory, after: str | None) -> FeatureHistory:
    result = replace(history, rollback_after=after, revision=history.revision+1)
    validate_history(result)
    return result


def apply_configuration(history: FeatureHistory, configuration: Configuration) -> FeatureHistory:
    validate_history(history)
    if not configuration.name:
        raise ValueError("configuration requires a name")
    identifiers = {f.feature_id for f in history.features}
    if len(set(configuration.suppressed)) != len(configuration.suppressed) or not set(configuration.suppressed) <= identifiers:
        raise ValueError("invalid configuration suppression")
    by_id = {f.feature_id: replace(f, suppressed=f.feature_id in configuration.suppressed) for f in history.features}
    seen = set()
    for feature_id, field, value in configuration.overrides:
        if feature_id not in by_id or field not in dict(by_id[feature_id].feature.parameters) or (feature_id, field) in seen:
            raise ValueError("unknown or duplicate configuration dimension")
        seen.add((feature_id, field))
        item = by_id[feature_id]
        spec = replace(item.feature, parameters=tuple((k, value if k == field else v) for k, v in item.feature.parameters))
        by_id[feature_id] = replace(item, feature=spec)
    result = replace(history, revision=history.revision+1,
                     features=tuple(by_id[f.feature_id] for f in history.features),
                     rollback_after=configuration.rollback_after)
    if configuration.order:
        result = reorder_features(result, configuration.order)
    compile_history(result)
    return result


def compile_history(history: FeatureHistory) -> FeatureModel:
    validate_history(history)
    nodes = [ModelNode("base", "plate", (), tuple(sorted(asdict(history.plate).items())))]
    previous = "base"
    if history.rollback_after != "base":
        for item in history.features:
            if not item.suppressed:
                nodes.append(ModelNode(item.feature_id, item.feature.kind, (previous,), item.feature.parameters))
                previous = item.feature_id
            if item.feature_id == history.rollback_after:
                break
    nodes.append(ModelNode("result", "result", (previous,)))
    model = FeatureModel(history.history_id, tuple(nodes), "result", history.revision)
    validate_model(model)
    return model
