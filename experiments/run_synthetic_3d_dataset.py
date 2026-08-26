"""Generate v0.53.0 synthetic 3D dataset and leakage evidence."""

from __future__ import annotations

import argparse
import csv
import io
import json
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

from research_notes.brep_preview import write_shape_previews  # noqa: E402
from research_notes.synthetic_3d_dataset import (  # noqa: E402
    CONTRACT_VERSION,
    SyntheticDatasetProbe,
    probe_synthetic_dataset,
)


SAMPLES_NAME = "synthetic_3d_samples.csv"
SPLITS_NAME = "synthetic_3d_split_summary.csv"
LEAKAGE_NAME = "synthetic_3d_leakage_checks.csv"
GRAPHS_NAME = "synthetic_3d_graphs.json"
CONTRACT_NAME = "synthetic_3d_dataset_contract.json"
FIGURE_NAME = "synthetic_3d_dataset.png"
SHAPES_NAME = "synthetic_3d_dataset_shapes.png"
MANIFEST_NAME = "manifest.csv"


def _csv_bytes(rows: list[dict[str, object]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=tuple(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_csv_bytes(rows))


def sample_rows(probe: SyntheticDatasetProbe) -> list[dict[str, object]]:
    return [
        {
            "contract_version": CONTRACT_VERSION,
            **{
                key: (int(value) if isinstance(value, bool) else format(value, ".17g") if isinstance(value, float) else value)
                for key, value in item.__dict__.items()
            },
        }
        for item in probe.samples
    ]


def split_rows(probe: SyntheticDatasetProbe) -> list[dict[str, object]]:
    counts = Counter((item.split, item.feature_label) for item in probe.samples)
    return [
        {"split": split, "feature_label": label, "sample_count": count}
        for (split, label), count in sorted(counts.items())
    ]


def leakage_rows(probe: SyntheticDatasetProbe) -> list[dict[str, object]]:
    return [
        {
            "check_id": item.check_id,
            "scope": item.scope,
            "violation_count": item.violation_count,
            "passed": int(item.passed),
            "interpretation": item.interpretation,
        }
        for item in probe.leakage_checks
    ]


def _manifest_bytes(probe: SyntheticDatasetProbe) -> bytes:
    return _csv_bytes(
        [
            {
                "sample_id": item.sample_id,
                "fixture_origin": item.fixture_origin,
                "source_file": item.source_file,
                "source_bytes": item.source_bytes,
                "source_sha256": item.source_sha256,
                "split": item.split,
                "label": item.feature_label,
            }
            for item in probe.samples
        ]
    )


def write_graphs(path: Path, probe: SyntheticDatasetProbe) -> None:
    path.write_text(
        json.dumps({"contract_version": CONTRACT_VERSION, "graphs": probe.graphs}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_contract(path: Path, probe: SyntheticDatasetProbe) -> None:
    payload = {
        "contract_version": CONTRACT_VERSION,
        "study_version": "v0.53.0",
        "title": "Synthetic 3D Dataset and Label Contracts",
        "sample_primary_key": ["sample_id"],
        "group_key": "family_id",
        "split_policy": "construction families are assigned wholly to train, validation, or test",
        "feature_columns": [
            "vertex_count", "edge_count", "face_count", "relation_count",
            "plane_face_count", "cylinder_face_count", "other_curved_face_count",
            "mean_degree", "curved_area_ratio", "absolute_volume", "surface_area",
        ],
        "added_fixtures": {item.file_name: item.source_sha256 for item in probe.added_fixtures},
        "all_leakage_checks_pass": all(item.passed for item in probe.leakage_checks),
        "claim_boundaries": [
            "labels are generated construction truth and not recovered STEP history",
            "the dataset is small, synthetic, and intentionally nonrepresentative",
            "family-isolated splits measure transfer to held-out families rather than random-sample accuracy",
            "graph signatures are coarse descriptors and not persistent topology names",
            "the dataset does not license or redistribute third-party CAD data",
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_figure(path: Path, probe: SyntheticDatasetProbe) -> None:
    splits = ("train", "validation", "test")
    labels = sorted({item.feature_label for item in probe.samples})
    figure, axis = plt.subplots(figsize=(11, 6))
    bottoms = [0] * len(splits)
    for label in labels:
        values = [sum(item.split == split and item.feature_label == label for item in probe.samples) for split in splits]
        axis.bar(splits, values, bottom=bottoms, label=label)
        bottoms = [a + b for a, b in zip(bottoms, values, strict=True)]
    axis.set_ylabel("STEP samples")
    axis.set_title("Family-isolated synthetic 3D dataset splits")
    axis.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0))
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160, metadata={"Software": "research-notes"})
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the deterministic synthetic 3D dataset.")
    parser.add_argument("--source-fixture-dir", type=Path, default=Path("fixtures/feature-recognition-benchmark"))
    parser.add_argument("--fixture-dir", type=Path, default=Path("fixtures/synthetic-3d-dataset"))
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument("--refresh-fixtures", action="store_true")
    args = parser.parse_args()
    probe = probe_synthetic_dataset(args.source_fixture_dir, args.fixture_dir, refresh_added=args.refresh_fixtures)
    _write_csv(args.output_dir / SAMPLES_NAME, sample_rows(probe))
    _write_csv(args.output_dir / SPLITS_NAME, split_rows(probe))
    _write_csv(args.output_dir / LEAKAGE_NAME, leakage_rows(probe))
    write_graphs(args.output_dir / GRAPHS_NAME, probe)
    write_contract(args.output_dir / CONTRACT_NAME, probe)
    write_figure(args.output_dir / FIGURE_NAME, probe)
    write_shape_previews(args.output_dir / SHAPES_NAME, probe.preview_shapes, title="Synthetic 3D dataset baseline families", columns=3)
    (args.fixture_dir / MANIFEST_NAME).write_bytes(_manifest_bytes(probe))
    print(f"Wrote deterministic synthetic 3D dataset evidence to {args.output_dir}")


if __name__ == "__main__":
    main()
