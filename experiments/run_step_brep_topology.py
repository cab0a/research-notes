"""Evaluate bounded STEP Part 21 and B-Rep topology inspection."""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

from research_notes import (  # noqa: E402
    STEPBRepFixture,
    build_step_brep_fixtures,
    inspect_step_brep,
)


MANIFEST_NAME = "manifest.csv"
OBSERVATIONS_NAME = "step_brep_topology_observations.csv"
FACES_NAME = "step_brep_faces.csv"
EDGES_NAME = "step_brep_edges.csv"
SHELLS_NAME = "step_brep_shells.csv"
SOLIDS_NAME = "step_brep_solids.csv"
SUMMARY_NAME = "step_brep_topology_summary.csv"
FIGURE_NAME = "step_brep_topology.png"

MANIFEST_FIELDS = (
    "fixture",
    "condition",
    "expected_decision",
    "expected_reason_code",
    "expected_faces",
    "expected_edges",
    "expected_shells",
    "expected_solids",
    "expected_free_edges",
    "source_bytes",
    "source_sha256",
)
OBSERVATION_FIELDS = (
    "fixture",
    "condition",
    "expected_decision",
    "observed_decision",
    "expectation_met",
    "expected_reason_code",
    "reason_code",
    "schema_identifiers",
    "entity_count",
    "reference_count",
    "unresolved_reference_count",
    "face_count",
    "edge_count",
    "shell_count",
    "solid_count",
    "free_edge_count",
    "nonmanifold_edge_count",
    "source_bytes",
    "source_sha256",
)
FACE_FIELDS = (
    "fixture",
    "face_index",
    "entity_id",
    "parent_shell_ids",
    "parent_solid_ids",
    "surface_entity_id",
    "surface_type",
    "same_sense",
    "outer_bound_count",
    "inner_bound_count",
    "boundary_edge_count",
    "free_edge_count",
    "nonmanifold_edge_count",
    "adjacent_face_indices",
    "origin",
    "axis",
    "reference_direction",
    "radius",
    "semi_angle",
    "major_radius",
    "minor_radius",
    "u_degree",
    "v_degree",
)
EDGE_FIELDS = (
    "fixture",
    "edge_index",
    "entity_id",
    "start_vertex_id",
    "end_vertex_id",
    "curve_entity_id",
    "curve_type",
    "same_sense",
    "oriented_use_count",
    "incident_face_count",
    "incident_face_indices",
    "is_free",
    "is_nonmanifold",
)
SHELL_FIELDS = (
    "fixture",
    "shell_index",
    "entity_id",
    "shell_type",
    "face_entity_ids",
    "face_count",
    "edge_count",
    "free_edge_count",
    "nonmanifold_edge_count",
    "declared_closed",
    "incidence_closed",
    "parent_solid_ids",
)
SOLID_FIELDS = (
    "fixture",
    "solid_index",
    "entity_id",
    "solid_type",
    "name",
    "outer_shell_id",
    "face_count",
    "edge_count",
)
SUMMARY_FIELDS = ("scope", "metric", "value")


def write_csv(
    path: Path,
    rows: Sequence[dict[str, str]],
    fieldnames: Sequence[str],
    *,
    allow_empty: bool = False,
) -> None:
    """Write deterministic UTF-8 CSV rows."""
    if not rows and not allow_empty:
        raise ValueError("rows must not be empty")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(fieldnames), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def fixture_manifest_rows(
    fixtures: Sequence[STEPBRepFixture],
) -> list[dict[str, str]]:
    """Describe the controlled fixture bytes and expected outcomes."""
    return [
        {
            "fixture": fixture.fixture,
            "condition": fixture.condition,
            "expected_decision": fixture.expected_decision,
            "expected_reason_code": fixture.expected_reason_code,
            "expected_faces": str(fixture.expected_faces),
            "expected_edges": str(fixture.expected_edges),
            "expected_shells": str(fixture.expected_shells),
            "expected_solids": str(fixture.expected_solids),
            "expected_free_edges": str(fixture.expected_free_edges),
            "source_bytes": str(len(fixture.step_bytes)),
            "source_sha256": hashlib.sha256(fixture.step_bytes).hexdigest(),
        }
        for fixture in fixtures
    ]


def refresh_fixture_corpus(
    fixture_dir: Path, fixtures: Sequence[STEPBRepFixture]
) -> None:
    """Write the complete deterministic fixture corpus and its manifest."""
    fixture_dir.mkdir(parents=True, exist_ok=True)
    expected_names = {f"{fixture.fixture}.step" for fixture in fixtures}
    existing_names = {path.name for path in fixture_dir.glob("*.step")}
    unexpected = sorted(existing_names - expected_names)
    if unexpected:
        raise RuntimeError(
            "fixture directory contains unexpected STEP files: "
            + ", ".join(unexpected)
        )
    for fixture in fixtures:
        (fixture_dir / f"{fixture.fixture}.step").write_bytes(
            fixture.step_bytes
        )
    write_csv(
        fixture_dir / MANIFEST_NAME,
        fixture_manifest_rows(fixtures),
        MANIFEST_FIELDS,
    )


def load_fixture_corpus(
    fixture_dir: Path, fixtures: Sequence[STEPBRepFixture]
) -> tuple[STEPBRepFixture, ...]:
    """Load committed fixtures after verifying manifest and exact bytes."""
    manifest_path = fixture_dir / MANIFEST_NAME
    if not manifest_path.is_file():
        raise RuntimeError(
            f"missing fixture manifest: {manifest_path}; use --refresh-fixtures"
        )
    with manifest_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if rows != fixture_manifest_rows(fixtures):
        raise RuntimeError("committed fixture manifest does not match definitions")

    loaded = []
    for fixture in fixtures:
        path = fixture_dir / f"{fixture.fixture}.step"
        if not path.is_file():
            raise RuntimeError(f"missing STEP fixture: {path}")
        step_bytes = path.read_bytes()
        if step_bytes != fixture.step_bytes:
            raise RuntimeError(f"STEP fixture differs from definition: {path.name}")
        loaded.append(
            STEPBRepFixture(
                fixture.fixture,
                fixture.condition,
                fixture.expected_decision,
                fixture.expected_reason_code,
                fixture.expected_faces,
                fixture.expected_edges,
                fixture.expected_shells,
                fixture.expected_solids,
                fixture.expected_free_edges,
                step_bytes,
            )
        )
    return tuple(loaded)


def _join(values: Sequence[object]) -> str:
    return "|".join(str(value) for value in values)


def _optional(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, tuple):
        return _join(f"{item:.6f}" for item in value)
    if isinstance(value, bool):
        return str(int(value))
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def collect_results(fixtures: Sequence[STEPBRepFixture]) -> dict[str, object]:
    """Inspect fixtures and return deterministic artifact rows."""
    observations: list[dict[str, str]] = []
    faces: list[dict[str, str]] = []
    edges: list[dict[str, str]] = []
    shells: list[dict[str, str]] = []
    solids: list[dict[str, str]] = []
    results = {}

    for fixture in fixtures:
        result = inspect_step_brep(fixture.step_bytes)
        results[fixture.fixture] = result
        free_edges = sum(edge.is_free for edge in result.edges)
        nonmanifold_edges = sum(edge.is_nonmanifold for edge in result.edges)
        expectation_met = (
            result.decision == fixture.expected_decision
            and result.reason_code == fixture.expected_reason_code
            and len(result.faces) == fixture.expected_faces
            and len(result.edges) == fixture.expected_edges
            and len(result.shells) == fixture.expected_shells
            and len(result.solids) == fixture.expected_solids
            and free_edges == fixture.expected_free_edges
        )
        observations.append(
            {
                "fixture": fixture.fixture,
                "condition": fixture.condition,
                "expected_decision": fixture.expected_decision,
                "observed_decision": result.decision,
                "expectation_met": str(int(expectation_met)),
                "expected_reason_code": fixture.expected_reason_code,
                "reason_code": result.reason_code,
                "schema_identifiers": _join(result.schema_identifiers),
                "entity_count": str(result.entity_count),
                "reference_count": str(result.reference_count),
                "unresolved_reference_count": str(
                    result.unresolved_reference_count
                ),
                "face_count": str(len(result.faces)),
                "edge_count": str(len(result.edges)),
                "shell_count": str(len(result.shells)),
                "solid_count": str(len(result.solids)),
                "free_edge_count": str(free_edges),
                "nonmanifold_edge_count": str(nonmanifold_edges),
                "source_bytes": str(len(fixture.step_bytes)),
                "source_sha256": hashlib.sha256(
                    fixture.step_bytes
                ).hexdigest(),
            }
        )
        for face in result.faces:
            faces.append(
                {
                    "fixture": fixture.fixture,
                    "face_index": str(face.face_index),
                    "entity_id": str(face.entity_id),
                    "parent_shell_ids": _join(face.parent_shell_ids),
                    "parent_solid_ids": _join(face.parent_solid_ids),
                    "surface_entity_id": str(face.surface_entity_id),
                    "surface_type": face.surface_type,
                    "same_sense": _optional(face.same_sense),
                    "outer_bound_count": str(face.outer_bound_count),
                    "inner_bound_count": str(face.inner_bound_count),
                    "boundary_edge_count": str(face.boundary_edge_count),
                    "free_edge_count": str(face.free_edge_count),
                    "nonmanifold_edge_count": str(
                        face.nonmanifold_edge_count
                    ),
                    "adjacent_face_indices": _join(
                        face.adjacent_face_indices
                    ),
                    "origin": _optional(face.origin),
                    "axis": _optional(face.axis),
                    "reference_direction": _optional(
                        face.reference_direction
                    ),
                    "radius": _optional(face.radius),
                    "semi_angle": _optional(face.semi_angle),
                    "major_radius": _optional(face.major_radius),
                    "minor_radius": _optional(face.minor_radius),
                    "u_degree": _optional(face.u_degree),
                    "v_degree": _optional(face.v_degree),
                }
            )
        for edge in result.edges:
            edges.append(
                {
                    "fixture": fixture.fixture,
                    "edge_index": str(edge.edge_index),
                    "entity_id": str(edge.entity_id),
                    "start_vertex_id": str(edge.start_vertex_id),
                    "end_vertex_id": str(edge.end_vertex_id),
                    "curve_entity_id": str(edge.curve_entity_id),
                    "curve_type": edge.curve_type,
                    "same_sense": _optional(edge.same_sense),
                    "oriented_use_count": str(edge.oriented_use_count),
                    "incident_face_count": str(edge.incident_face_count),
                    "incident_face_indices": _join(
                        edge.incident_face_indices
                    ),
                    "is_free": str(int(edge.is_free)),
                    "is_nonmanifold": str(int(edge.is_nonmanifold)),
                }
            )
        for shell in result.shells:
            shells.append(
                {
                    "fixture": fixture.fixture,
                    "shell_index": str(shell.shell_index),
                    "entity_id": str(shell.entity_id),
                    "shell_type": shell.shell_type,
                    "face_entity_ids": _join(shell.face_entity_ids),
                    "face_count": str(shell.face_count),
                    "edge_count": str(shell.edge_count),
                    "free_edge_count": str(shell.free_edge_count),
                    "nonmanifold_edge_count": str(
                        shell.nonmanifold_edge_count
                    ),
                    "declared_closed": str(int(shell.declared_closed)),
                    "incidence_closed": str(int(shell.incidence_closed)),
                    "parent_solid_ids": _join(shell.parent_solid_ids),
                }
            )
        for solid in result.solids:
            solids.append(
                {
                    "fixture": fixture.fixture,
                    "solid_index": str(solid.solid_index),
                    "entity_id": str(solid.entity_id),
                    "solid_type": solid.solid_type,
                    "name": solid.name,
                    "outer_shell_id": str(solid.outer_shell_id),
                    "face_count": str(solid.face_count),
                    "edge_count": str(solid.edge_count),
                }
            )

    validate_results(observations, results)
    return {
        "observations": observations,
        "faces": faces,
        "edges": edges,
        "shells": shells,
        "solids": solids,
        "results": results,
    }


def validate_results(
    observations: Sequence[dict[str, str]], results: dict[str, object]
) -> None:
    """Enforce the preregistered controlled-corpus expectations."""
    if len(observations) != 6:
        raise RuntimeError("expected six STEP fixtures")
    if any(row["expectation_met"] != "1" for row in observations):
        raise RuntimeError("a STEP topology expectation failed")
    decisions = Counter(row["observed_decision"] for row in observations)
    if decisions != {"accept": 4, "quarantine": 1, "reject": 1}:
        raise RuntimeError(f"unexpected decision totals: {dict(decisions)}")

    closed = results["closed_tetrahedron"]
    if any(
        face.free_edge_count != 0 or len(face.adjacent_face_indices) != 3
        for face in closed.faces
    ):
        raise RuntimeError("closed tetrahedron adjacency is inconsistent")
    opened = results["open_tetrahedron"]
    if opened.shells[0].incidence_closed or opened.shells[0].free_edge_count != 3:
        raise RuntimeError("open tetrahedron boundary was not detected")
    catalog_types = Counter(
        face.surface_type for face in results["surface_catalog"].faces
    )
    if catalog_types != {
        "plane": 1,
        "cylinder": 1,
        "cone": 1,
        "sphere": 1,
        "torus": 1,
        "b_spline": 1,
    }:
        raise RuntimeError(f"unexpected surface catalog: {dict(catalog_types)}")


def summarize(collected: dict[str, object]) -> list[dict[str, str]]:
    """Build concise corpus-level and fixture-level evidence rows."""
    observations = collected["observations"]
    faces = collected["faces"]
    decision_counts = Counter(
        row["observed_decision"] for row in observations
    )
    surface_counts = Counter(row["surface_type"] for row in faces)
    rows = [
        {"scope": "corpus", "metric": "fixture_count", "value": "6"},
        {
            "scope": "corpus",
            "metric": "expectation_rate",
            "value": "1.000000",
        },
    ]
    rows.extend(
        {
            "scope": "corpus",
            "metric": f"decision_{decision}",
            "value": str(decision_counts.get(decision, 0)),
        }
        for decision in ("accept", "quarantine", "reject")
    )
    rows.extend(
        {
            "scope": "accepted_faces",
            "metric": f"surface_{surface_type}",
            "value": str(surface_counts.get(surface_type, 0)),
        }
        for surface_type in (
            "plane",
            "cylinder",
            "cone",
            "sphere",
            "torus",
            "b_spline",
        )
    )
    for row in observations:
        for metric in (
            "face_count",
            "edge_count",
            "shell_count",
            "solid_count",
            "free_edge_count",
            "nonmanifold_edge_count",
        ):
            rows.append(
                {
                    "scope": row["fixture"],
                    "metric": metric,
                    "value": row[metric],
                }
            )
    return rows


def plot_results(collected: dict[str, object], output_path: Path) -> None:
    """Visualize topology counts, boundaries, surfaces, and decisions."""
    observations = collected["observations"]
    faces = collected["faces"]
    accepted = [
        row for row in observations if row["observed_decision"] == "accept"
    ]
    labels = [row["fixture"].replace("_", "\n") for row in accepted]
    x_positions = np.arange(len(labels))
    figure, axes = plt.subplots(2, 2, figsize=(13.5, 9.0))

    for offset, metric, color in zip(
        (-0.27, -0.09, 0.09, 0.27),
        ("face_count", "edge_count", "shell_count", "solid_count"),
        ("#457b9d", "#2a9d8f", "#e9c46a", "#e76f51"),
        strict=True,
    ):
        axes[0, 0].bar(
            x_positions + offset,
            [int(row[metric]) for row in accepted],
            width=0.18,
            label=metric.removesuffix("_count"),
            color=color,
        )
    axes[0, 0].set_xticks(x_positions, labels)
    axes[0, 0].set_ylabel("Topology elements")
    axes[0, 0].set_title("Controlled topology inventory")
    axes[0, 0].legend(ncols=2)
    axes[0, 0].grid(axis="y", alpha=0.25)

    axes[0, 1].bar(
        labels,
        [int(row["free_edge_count"]) for row in accepted],
        color="#e76f51",
        label="free edges",
    )
    axes[0, 1].bar(
        labels,
        [int(row["nonmanifold_edge_count"]) for row in accepted],
        bottom=[int(row["free_edge_count"]) for row in accepted],
        color="#6d597a",
        label="nonmanifold edges",
    )
    axes[0, 1].set_ylabel("Edge count")
    axes[0, 1].set_title("Incidence exposes the open shell")
    axes[0, 1].legend()
    axes[0, 1].grid(axis="y", alpha=0.25)

    surface_order = (
        "plane",
        "cylinder",
        "cone",
        "sphere",
        "torus",
        "b_spline",
    )
    surface_counts = Counter(
        row["surface_type"]
        for row in faces
        if row["fixture"] == "surface_catalog"
    )
    axes[1, 0].barh(
        surface_order,
        [surface_counts[name] for name in surface_order],
        color="#264653",
    )
    axes[1, 0].set_xlabel("Faces")
    axes[1, 0].set_title("Declared surface families are classified")
    axes[1, 0].set_xticks((0, 1))
    axes[1, 0].grid(axis="x", alpha=0.25)

    decisions = ("accept", "quarantine", "reject")
    decision_counts = Counter(
        row["observed_decision"] for row in observations
    )
    axes[1, 1].bar(
        decisions,
        [decision_counts[decision] for decision in decisions],
        color=("#2a9d8f", "#e9c46a", "#e76f51"),
    )
    axes[1, 1].set_ylabel("Fixtures")
    axes[1, 1].set_title("Malformed relationships fail closed")
    axes[1, 1].grid(axis="y", alpha=0.25)

    figure.suptitle(
        "Bounded STEP Part 21 and B-Rep Topology Inspection",
        fontsize=14,
        fontweight="bold",
    )
    figure.text(
        0.5,
        0.012,
        "Synthetic fixtures demonstrate a controlled subset, not general "
        "STEP conformance.",
        ha="center",
        fontsize=9,
    )
    figure.tight_layout(rect=(0, 0.035, 1, 0.96))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=150)
    plt.close(figure)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Evaluate bounded STEP Part 21 and B-Rep topology inspection."
    )
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=Path("fixtures/step-brep-topology"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument("--refresh-fixtures", action="store_true")
    return parser.parse_args()


def main() -> None:
    """Run the controlled experiment and write deterministic artifacts."""
    args = parse_args()
    fixture_definitions = build_step_brep_fixtures()
    if args.refresh_fixtures:
        refresh_fixture_corpus(args.fixture_dir, fixture_definitions)
    fixtures = load_fixture_corpus(args.fixture_dir, fixture_definitions)
    collected = collect_results(fixtures)
    write_csv(
        args.output_dir / OBSERVATIONS_NAME,
        collected["observations"],
        OBSERVATION_FIELDS,
    )
    write_csv(
        args.output_dir / FACES_NAME,
        collected["faces"],
        FACE_FIELDS,
    )
    write_csv(
        args.output_dir / EDGES_NAME,
        collected["edges"],
        EDGE_FIELDS,
    )
    write_csv(
        args.output_dir / SHELLS_NAME,
        collected["shells"],
        SHELL_FIELDS,
    )
    write_csv(
        args.output_dir / SOLIDS_NAME,
        collected["solids"],
        SOLID_FIELDS,
    )
    write_csv(
        args.output_dir / SUMMARY_NAME,
        summarize(collected),
        SUMMARY_FIELDS,
    )
    plot_results(collected, args.output_dir / FIGURE_NAME)
    print(
        f"Wrote {len(collected['observations'])} STEP observations, "
        f"{len(collected['faces'])} face rows, "
        f"{len(collected['edges'])} edge rows, "
        f"{len(collected['shells'])} shell rows, and "
        f"{len(collected['solids'])} solid rows to {args.output_dir}"
    )


if __name__ == "__main__":
    main()
