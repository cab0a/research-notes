"""Generate the v0.38 void-shell and composite-solid evidence."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

from research_notes.solid_regions import (  # noqa: E402
    SolidRegionProbe,
    probe_solid_regions,
    solid_region_controls,
)


OBSERVATIONS_NAME = "solid_region_observations.csv"
SHELL_ROLES_NAME = "shell_role_observations.csv"
CONTAINMENT_NAME = "shell_containment_relations.csv"
ADJACENCY_NAME = "solid_adjacency_observations.csv"
SUMMARY_NAME = "solid_region_summary.csv"
CONTRACT_NAME = "solid_region_contract.json"
FIGURE_NAME = "solid_regions.png"
SHAPES_NAME = "solid_region_shapes.png"
MANIFEST_NAME = "manifest.csv"


def _value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(int(value))
    if isinstance(value, float):
        return format(value, ".17g")
    return str(value)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("CSV rows must not be empty")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(
            {key: _value(value) for key, value in row.items()} for row in rows
        )


def _fixture_rows(probe: SolidRegionProbe) -> list[dict[str, object]]:
    return [
        {
            "control_id": item.round_trip.fixture_id,
            "file_name": item.round_trip.file_name,
            "source_bytes": len(item.round_trip.source_bytes),
            "source_sha256": item.round_trip.source_sha256,
            "binding_distribution_version": probe.binding_distribution_version,
            "binding_module_version": probe.binding_module_version,
            "step_processor": item.round_trip.step_processor,
            "writer_status": item.round_trip.writer_status,
            "reader_status": item.round_trip.reader_status,
            "transferred_roots": item.round_trip.transferred_roots,
            "manifold_solid_brep_count": item.manifold_solid_brep_count,
            "brep_with_voids_count": item.brep_with_voids_count,
            "closed_shell_count": item.closed_shell_count,
            "oriented_closed_shell_count": item.oriented_closed_shell_count,
        }
        for item in probe.fixtures
    ]


def _handle_fixtures(
    directory: Path, probe: SolidRegionProbe, *, refresh: bool
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    expected = {item.round_trip.file_name for item in probe.fixtures} | {MANIFEST_NAME}
    unexpected = sorted(
        path.name for path in directory.iterdir() if path.name not in expected
    )
    if unexpected:
        raise RuntimeError("unexpected fixture files: " + ", ".join(unexpected))
    rows = _fixture_rows(probe)
    if refresh:
        for item in probe.fixtures:
            (directory / item.round_trip.file_name).write_bytes(
                item.round_trip.source_bytes
            )
        _write_csv(directory / MANIFEST_NAME, rows)
        return
    for item in probe.fixtures:
        path = directory / item.round_trip.file_name
        if not path.is_file() or path.read_bytes() != item.round_trip.source_bytes:
            raise RuntimeError(
                f"committed fixture differs: {item.round_trip.file_name}"
            )
    with (directory / MANIFEST_NAME).open(encoding="utf-8", newline="") as handle:
        if list(csv.DictReader(handle)) != [
            {key: _value(value) for key, value in row.items()} for row in rows
        ]:
            raise RuntimeError("committed fixture manifest differs")


def _summary_rows(probe: SolidRegionProbe) -> list[dict[str, object]]:
    constructed = [row for row in probe.observations if row.stage == "constructed"]
    imported = [row for row in probe.observations if row.stage == "step_imported"]
    return [
        {
            "scope": "corpus",
            "metric": "control_count",
            "value": len(solid_region_controls()),
        },
        {
            "scope": "corpus",
            "metric": "stage_observation_count",
            "value": len(probe.observations),
        },
        {
            "scope": "constructed",
            "metric": "material_region_candidates",
            "value": sum(row.material_region_candidate for row in constructed),
        },
        {
            "scope": "constructed",
            "metric": "candidate_contract_matches",
            "value": sum(
                row.material_region_candidate_matches_constructed_control
                for row in constructed
            ),
        },
        {
            "scope": "constructed",
            "metric": "shared_face_count_matches",
            "value": sum(
                row.shared_face_count_matches_constructed_control for row in constructed
            ),
        },
        {
            "scope": "constructed",
            "metric": "solid_component_count_matches",
            "value": sum(
                row.solid_component_count_matches_constructed_control
                for row in constructed
            ),
        },
        {
            "scope": "step_imported",
            "metric": "material_region_candidates",
            "value": sum(row.material_region_candidate for row in imported),
        },
        {
            "scope": "constructed",
            "metric": "kernel_valid_but_contract_false",
            "value": sum(
                row.kernel_analyzer_valid and not row.material_region_candidate
                for row in constructed
            ),
        },
        {
            "scope": "step_imported",
            "metric": "kernel_valid_but_contract_false",
            "value": sum(
                row.kernel_analyzer_valid and not row.material_region_candidate
                for row in imported
            ),
        },
        {
            "scope": "step_exchange",
            "metric": "container_type_changes",
            "value": sum(
                next(
                    row for row in imported if row.control_id == source.control_id
                ).observed_shape_type
                != source.observed_shape_type
                for source in constructed
            ),
        },
        {
            "scope": "step_exchange",
            "metric": "maximum_volume_absolute_error",
            "value": max(row.volume_absolute_error for row in imported),
        },
    ]


def _plot_summary(path: Path, probe: SolidRegionProbe) -> None:
    controls = solid_region_controls()
    constructed = {
        row.control_id: row for row in probe.observations if row.stage == "constructed"
    }
    imported = {
        row.control_id: row
        for row in probe.observations
        if row.stage == "step_imported"
    }
    labels = [row.control_id.replace("_", "\n") for row in controls]
    x = list(range(len(labels)))
    fig, axes = plt.subplots(
        2, 1, figsize=(14, 8), gridspec_kw={"height_ratios": [2, 1]}
    )
    width = 0.36
    axes[0].bar(
        [value - width / 2 for value in x],
        [constructed[row.control_id].kernel_signed_volume for row in controls],
        width,
        label="Constructed",
        color="#2563eb",
    )
    axes[0].bar(
        [value + width / 2 for value in x],
        [imported[row.control_id].kernel_signed_volume for row in controls],
        width,
        label="STEP imported",
        color="#f59e0b",
    )
    axes[0].plot(
        x,
        [row.analytic_material_volume for row in controls],
        "ko",
        label="Analytic material volume",
    )
    axes[0].set_ylabel("Signed volume")
    axes[0].set_xticks(x, labels, fontsize=8)
    axes[0].legend(frameon=False, ncol=3)
    axes[0].set_title("A numeric volume is not a shell-validity proof")
    axes[1].bar(
        [value - width / 2 for value in x],
        [constructed[row.control_id].shell_count for row in controls],
        width,
        color="#64748b",
        label="Shells",
    )
    axes[1].bar(
        [value + width / 2 for value in x],
        [constructed[row.control_id].solid_count for row in controls],
        width,
        color="#10b981",
        label="Solids",
    )
    axes[1].set_ylabel("Count")
    axes[1].set_xticks(x, labels, fontsize=8)
    axes[1].legend(frameon=False)
    fig.suptitle("Void shells and composite-solid contracts", fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _draw_region(
    axis: object,
    title: str,
    voids: list[tuple[float, float, float, float]],
    islands: list[tuple[float, float, float, float]] | None = None,
    outside: list[tuple[float, float, float, float]] | None = None,
) -> None:
    axis.add_patch(
        Rectangle((0, 0), 10, 6, facecolor="#bfdbfe", edgecolor="#1d4ed8", linewidth=2)
    )
    for x, y, width, height in voids:
        axis.add_patch(
            Rectangle(
                (x, y),
                width,
                height,
                facecolor="white",
                edgecolor="#dc2626",
                hatch="//",
                linewidth=1.5,
            )
        )
    for x, y, width, height in islands or []:
        axis.add_patch(
            Rectangle(
                (x, y),
                width,
                height,
                facecolor="#86efac",
                edgecolor="#15803d",
                linewidth=1.5,
            )
        )
    for x, y, width, height in outside or []:
        axis.add_patch(
            Rectangle(
                (x, y),
                width,
                height,
                facecolor="white",
                edgecolor="#dc2626",
                linestyle="--",
                linewidth=1.5,
            )
        )
    axis.set_title(title)
    axis.set_xlim(-1, 16)
    axis.set_ylim(-1, 7)
    axis.set_aspect("equal")
    axis.set_axis_off()


def _plot_shapes(path: Path) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(13, 6))
    _draw_region(axes[0, 0], "Outer shell", [])
    _draw_region(axes[0, 1], "Centered void", [(3, 2, 4, 2)])
    _draw_region(axes[0, 2], "Two disjoint voids", [(2, 2, 2, 2), (7, 2, 2, 2)])
    _draw_region(axes[1, 0], "Outside reversed shell", [], outside=[(11, 2, 4, 2)])
    _draw_region(
        axes[1, 1], "Overlapping void shells", [(2, 1.5, 3, 3), (4, 1.5, 3, 3)]
    )
    _draw_region(
        axes[1, 2], "Material island in a void", [(2, 1, 6, 4)], islands=[(4, 2, 2, 2)]
    )
    fig.suptitle(
        "Synthetic solid-region controls (cross-section schematic)", fontweight="bold"
    )
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def run(output_dir: Path, fixture_dir: Path, *, refresh_fixtures: bool) -> None:
    """Run the study and write deterministic evidence."""
    output_dir.mkdir(parents=True, exist_ok=True)
    probe = probe_solid_regions()
    _handle_fixtures(fixture_dir, probe, refresh=refresh_fixtures)
    _write_csv(
        output_dir / OBSERVATIONS_NAME,
        [
            {"platform_label": probe.platform_label, **asdict(row)}
            for row in probe.observations
        ],
    )
    _write_csv(
        output_dir / SHELL_ROLES_NAME,
        [
            {"platform_label": probe.platform_label, **asdict(row)}
            for row in probe.shell_roles
        ],
    )
    _write_csv(
        output_dir / CONTAINMENT_NAME,
        [
            {"platform_label": probe.platform_label, **asdict(row)}
            for row in probe.containment
        ],
    )
    _write_csv(
        output_dir / ADJACENCY_NAME,
        [
            {"platform_label": probe.platform_label, **asdict(row)}
            for row in probe.adjacency
        ],
    )
    summary = _summary_rows(probe)
    _write_csv(output_dir / SUMMARY_NAME, summary)
    contract = {
        "schema_version": "v0.38.0",
        "platform_label": probe.platform_label,
        "binding_distribution_version": probe.binding_distribution_version,
        "binding_module_version": probe.binding_module_version,
        "controls": [asdict(control) for control in solid_region_controls()],
        "summary": summary,
    }
    (output_dir / CONTRACT_NAME).write_text(
        json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _plot_summary(output_dir / FIGURE_NAME, probe)
    _plot_shapes(output_dir / SHAPES_NAME)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate controlled void shells and composite-solid contracts."
    )
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument(
        "--fixture-dir", type=Path, default=Path("fixtures/solid-regions")
    )
    parser.add_argument("--refresh-fixtures", action="store_true")
    args = parser.parse_args()
    run(args.output_dir, args.fixture_dir, refresh_fixtures=args.refresh_fixtures)
    print(f"Wrote v0.38 evidence to {args.output_dir}")


if __name__ == "__main__":
    main()
