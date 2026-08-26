"""Generate v0.54.0 explainable 3D baseline evidence."""

from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

from research_notes.learned_3d_baselines import (  # noqa: E402
    CONTRACT_VERSION,
    BaselineProbe,
    evaluate_baselines,
    load_dataset,
)


PREDICTIONS_NAME = "learned_3d_predictions.csv"
SUMMARY_NAME = "learned_3d_summary.csv"
CALIBRATION_NAME = "learned_3d_calibration.csv"
ROBUSTNESS_NAME = "learned_3d_robustness.csv"
CONTRACT_NAME = "learned_3d_model_contract.json"
FIGURE_NAME = "learned_3d_baselines.png"


def _csv_bytes(rows: list[dict[str, object]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=tuple(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_csv_bytes(rows))


def prediction_rows(probe: BaselineProbe) -> list[dict[str, object]]:
    return [
        {
            "contract_version": CONTRACT_VERSION,
            **{
                key: (int(value) if isinstance(value, bool) else "" if value is None else format(value, ".17g") if isinstance(value, float) else value)
                for key, value in item.__dict__.items()
            },
        }
        for item in probe.predictions
    ]


def summary_rows(probe: BaselineProbe) -> list[dict[str, object]]:
    rows = []
    for model in probe.models:
        for split in ("train", "validation", "test"):
            selected = [item for item in probe.predictions if item.model_id == model.model_id and item.split == split]
            decided = [item for item in selected if item.decision != "abstain"]
            rows.append(
                {
                    "model_id": model.model_id,
                    "split": split,
                    "sample_count": len(selected),
                    "decided_count": len(decided),
                    "coverage": format(len(decided) / len(selected), ".17g"),
                    "raw_accuracy": format(sum(item.raw_correct for item in selected) / len(selected), ".17g"),
                    "selective_accuracy": "" if not decided else format(sum(bool(item.decided_correct) for item in decided) / len(decided), ".17g"),
                    "brier_score": format(sum((item.supported_probability - (item.truth_label == "supported")) ** 2 for item in selected) / len(selected), ".17g"),
                    "temperature": format(model.temperature, ".17g"),
                    "abstention_threshold": format(model.abstention_threshold, ".17g"),
                }
            )
    return rows


def calibration_rows(probe: BaselineProbe) -> list[dict[str, object]]:
    rows = []
    bins = ((0.5, 0.7), (0.7, 0.85), (0.85, 1.0000001))
    for model in probe.models:
        for split in ("validation", "test"):
            selected = [item for item in probe.predictions if item.model_id == model.model_id and item.split == split]
            for lower, upper in bins:
                members = [item for item in selected if lower <= item.confidence < upper]
                rows.append(
                    {
                        "model_id": model.model_id,
                        "split": split,
                        "confidence_lower": format(lower, ".17g"),
                        "confidence_upper": format(min(upper, 1.0), ".17g"),
                        "sample_count": len(members),
                        "mean_confidence": "" if not members else format(sum(item.confidence for item in members) / len(members), ".17g"),
                        "empirical_accuracy": "" if not members else format(sum(item.raw_correct for item in members) / len(members), ".17g"),
                    }
                )
    return rows


def robustness_rows(probe: BaselineProbe) -> list[dict[str, object]]:
    rows = []
    for model in probe.models:
        for family in sorted({item.family_id for item in probe.samples}):
            members = [item for item in probe.predictions if item.model_id == model.model_id and item.family_id == family]
            rows.append(
                {
                    "model_id": model.model_id,
                    "family_id": family,
                    "split": members[0].split,
                    "sample_count": len(members),
                    "raw_prediction_count": len({item.raw_prediction for item in members}),
                    "decision_count": len({item.decision for item in members}),
                    "raw_prediction_stable": int(len({item.raw_prediction for item in members}) == 1),
                    "decision_stable": int(len({item.decision for item in members}) == 1),
                    "minimum_confidence": format(min(item.confidence for item in members), ".17g"),
                    "maximum_confidence": format(max(item.confidence for item in members), ".17g"),
                }
            )
    return rows


def write_contract(path: Path, probe: BaselineProbe) -> None:
    payload = {
        "contract_version": CONTRACT_VERSION,
        "study_version": "v0.54.0",
        "title": "Learned Baselines and Explainable 3D Assistance",
        "fit_split": "train",
        "calibration_split": "validation",
        "evaluation_split": "test",
        "label": "supported_feature",
        "models": [
            {
                "model_id": item.model_id,
                "model_kind": item.model_kind,
                "feature_names": item.feature_names,
                "means": item.means,
                "scales": item.scales,
                "negative_centroid": item.negative_centroid,
                "positive_centroid": item.positive_centroid,
                "temperature": item.temperature,
                "abstention_threshold": item.abstention_threshold,
            }
            for item in probe.models
        ],
        "claim_boundaries": [
            "the binary target is support by bounded repository rules, not manufacturing feature truth",
            "training and calibration use small synthetic family-isolated partitions",
            "temperature selection on validation is not a guarantee of probability calibration",
            "evidence fields explain descriptor influence rather than causal geometry",
            "test results do not establish performance on industrial CAD or unseen exchange routes",
            "abstention is a local policy and not an uncertainty proof",
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_figure(path: Path, probe: BaselineProbe) -> None:
    summaries = summary_rows(probe)
    test = [item for item in summaries if item["split"] == "test"]
    names = [item["model_id"] for item in test]
    coverage = [float(item["coverage"]) for item in test]
    accuracy = [float(item["selective_accuracy"] or 0.0) for item in test]
    figure, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    axes[0].bar(names, accuracy, color="#4c78a8")
    axes[0].set_ylim(0.0, 1.05)
    axes[0].set_title("Test selective accuracy")
    axes[0].tick_params(axis="x", rotation=25)
    axes[1].bar(names, coverage, color="#f28e2b")
    axes[1].set_ylim(0.0, 1.05)
    axes[1].set_title("Test decision coverage")
    axes[1].tick_params(axis="x", rotation=25)
    figure.suptitle("Explainable binary baselines on held-out construction families")
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160, metadata={"Software": "research-notes"})
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate deterministic explainable 3D baselines.")
    parser.add_argument("--dataset-csv", type=Path, default=Path("results/synthetic_3d_samples.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    args = parser.parse_args()
    probe = evaluate_baselines(load_dataset(args.dataset_csv))
    _write_csv(args.output_dir / PREDICTIONS_NAME, prediction_rows(probe))
    _write_csv(args.output_dir / SUMMARY_NAME, summary_rows(probe))
    _write_csv(args.output_dir / CALIBRATION_NAME, calibration_rows(probe))
    _write_csv(args.output_dir / ROBUSTNESS_NAME, robustness_rows(probe))
    write_contract(args.output_dir / CONTRACT_NAME, probe)
    write_figure(args.output_dir / FIGURE_NAME, probe)
    print(f"Wrote deterministic learned-baseline evidence to {args.output_dir}")


if __name__ == "__main__":
    main()
