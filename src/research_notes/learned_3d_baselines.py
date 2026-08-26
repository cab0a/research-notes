"""Evaluate small explainable baselines on the synthetic 3D dataset."""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np


CONTRACT_VERSION = "1.0.0"
ABSTENTION_THRESHOLD = 0.70
TEMPERATURE_GRID = (0.25, 0.5, 1.0, 2.0, 4.0, 8.0)

GRAPH_FEATURES = (
    "face_count",
    "relation_count",
    "plane_face_count",
    "cylinder_face_count",
    "other_curved_face_count",
    "mean_degree",
)
GEOMETRY_FEATURES = (
    "curved_area_ratio",
    "absolute_volume",
    "surface_area",
)
TABULAR_FEATURES = GRAPH_FEATURES + GEOMETRY_FEATURES + (
    "vertex_count",
    "edge_count",
)


@dataclass(frozen=True)
class BaselineSample:
    """One numeric dataset row used by the bounded baseline study."""

    sample_id: str
    family_id: str
    perturbation: str
    split: str
    source_file: str
    source_sha256: str
    supported_feature: bool
    values: tuple[tuple[str, float], ...]

    def value(self, name: str) -> float:
        return dict(self.values)[name]


@dataclass(frozen=True)
class BaselineModel:
    """One deterministic rule or nearest-centroid model contract."""

    model_id: str
    model_kind: str
    feature_names: tuple[str, ...]
    means: tuple[float, ...]
    scales: tuple[float, ...]
    negative_centroid: tuple[float, ...]
    positive_centroid: tuple[float, ...]
    temperature: float
    abstention_threshold: float


@dataclass(frozen=True)
class BaselinePrediction:
    """One source-linked model prediction and selective decision."""

    model_id: str
    sample_id: str
    family_id: str
    perturbation: str
    split: str
    source_file: str
    source_sha256: str
    truth_label: str
    supported_probability: float
    raw_prediction: str
    confidence: float
    decision: str
    raw_correct: bool
    decided_correct: bool | None
    top_evidence_feature: str
    top_evidence_value: float
    evidence_direction: str


@dataclass(frozen=True)
class BaselineProbe:
    """Complete v0.54.0 model, prediction, and calibration evidence."""

    samples: tuple[BaselineSample, ...]
    models: tuple[BaselineModel, ...]
    predictions: tuple[BaselinePrediction, ...]


def load_dataset(path: Path) -> tuple[BaselineSample, ...]:
    """Load only declared numeric features and provenance from the v0.53 CSV."""
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    samples = []
    for row in rows:
        values = tuple((name, float(row[name])) for name in TABULAR_FEATURES)
        samples.append(
            BaselineSample(
                row["sample_id"],
                row["family_id"],
                row["perturbation"],
                row["split"],
                row["source_file"],
                row["source_sha256"],
                row["supported_feature"] == "1",
                values,
            )
        )
    return tuple(samples)


def _matrix(samples: tuple[BaselineSample, ...], names: tuple[str, ...]) -> np.ndarray:
    return np.asarray([[item.value(name) for name in names] for item in samples], dtype=np.float64)


def _sigmoid(value: float) -> float:
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exp_value = math.exp(value)
    return exp_value / (1.0 + exp_value)


def _fit_centroid(model_id: str, feature_names: tuple[str, ...], samples: tuple[BaselineSample, ...]) -> BaselineModel:
    train = tuple(item for item in samples if item.split == "train")
    matrix = _matrix(train, feature_names)
    means = matrix.mean(axis=0)
    scales = matrix.std(axis=0)
    scales[scales < 1.0e-12] = 1.0
    normalized = (matrix - means) / scales
    labels = np.asarray([item.supported_feature for item in train], dtype=bool)
    negative = normalized[~labels].mean(axis=0)
    positive = normalized[labels].mean(axis=0)
    provisional = BaselineModel(
        model_id,
        "nearest_centroid",
        feature_names,
        tuple(float(value) for value in means),
        tuple(float(value) for value in scales),
        tuple(float(value) for value in negative),
        tuple(float(value) for value in positive),
        1.0,
        ABSTENTION_THRESHOLD,
    )
    validation = tuple(item for item in samples if item.split == "validation")
    logits = [_centroid_logit(provisional, item)[0] for item in validation]
    truth = [float(item.supported_feature) for item in validation]
    temperature = min(
        TEMPERATURE_GRID,
        key=lambda value: (
            sum((_sigmoid(logit / value) - target) ** 2 for logit, target in zip(logits, truth, strict=True)) / len(truth),
            value,
        ),
    )
    return BaselineModel(
        provisional.model_id,
        provisional.model_kind,
        provisional.feature_names,
        provisional.means,
        provisional.scales,
        provisional.negative_centroid,
        provisional.positive_centroid,
        temperature,
        provisional.abstention_threshold,
    )


def _centroid_logit(model: BaselineModel, sample: BaselineSample) -> tuple[float, tuple[float, ...]]:
    values = np.asarray([sample.value(name) for name in model.feature_names], dtype=np.float64)
    normalized = (values - np.asarray(model.means)) / np.asarray(model.scales)
    negative = np.asarray(model.negative_centroid)
    positive = np.asarray(model.positive_centroid)
    contributions = (normalized - negative) ** 2 - (normalized - positive) ** 2
    return float(contributions.sum()), tuple(float(value) for value in contributions)


def _rule_probability(sample: BaselineSample) -> tuple[float, str, float]:
    other_curved = sample.value("other_curved_face_count")
    relation_count = sample.value("relation_count")
    face_count = sample.value("face_count")
    cylinder_count = sample.value("cylinder_face_count")
    if other_curved > 0.0:
        return 0.05, "other_curved_face_count", other_curved
    if face_count == 6.0 and relation_count == 12.0 and cylinder_count == 0.0:
        return 0.10, "relation_count", relation_count
    if relation_count >= 14.0 or face_count >= 7.0:
        return 0.90, "relation_count", relation_count
    return 0.50, "face_count", face_count


def _predict(model: BaselineModel, sample: BaselineSample) -> BaselinePrediction:
    if model.model_kind == "bounded_rule":
        probability, evidence, value = _rule_probability(sample)
        direction = "supports_feature" if probability >= 0.5 else "supports_none"
    else:
        logit, contributions = _centroid_logit(model, sample)
        probability = _sigmoid(logit / model.temperature)
        index = max(range(len(contributions)), key=lambda item: abs(contributions[item]))
        evidence = model.feature_names[index]
        value = sample.value(evidence)
        direction = "supports_feature" if contributions[index] >= 0.0 else "supports_none"
    raw = "supported" if probability >= 0.5 else "none"
    confidence = max(probability, 1.0 - probability)
    decision = raw if confidence >= model.abstention_threshold else "abstain"
    truth = "supported" if sample.supported_feature else "none"
    return BaselinePrediction(
        model.model_id,
        sample.sample_id,
        sample.family_id,
        sample.perturbation,
        sample.split,
        sample.source_file,
        sample.source_sha256,
        truth,
        probability,
        raw,
        confidence,
        decision,
        raw == truth,
        None if decision == "abstain" else decision == truth,
        evidence,
        value,
        direction,
    )


def evaluate_baselines(samples: tuple[BaselineSample, ...]) -> BaselineProbe:
    """Fit on train, calibrate on validation, and retain all split predictions."""
    rule = BaselineModel(
        "bounded_rule",
        "bounded_rule",
        (),
        (),
        (),
        (),
        (),
        1.0,
        ABSTENTION_THRESHOLD,
    )
    models = (
        rule,
        _fit_centroid("geometry_centroid", GEOMETRY_FEATURES, samples),
        _fit_centroid("graph_centroid", GRAPH_FEATURES, samples),
        _fit_centroid("tabular_centroid", TABULAR_FEATURES, samples),
    )
    predictions = tuple(_predict(model, sample) for model in models for sample in samples)
    return BaselineProbe(samples, models, predictions)
