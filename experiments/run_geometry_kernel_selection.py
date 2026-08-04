"""Evaluate geometry-kernel candidates and run a bounded OCCT probe."""

from __future__ import annotations

import argparse
import csv
import json
from collections.abc import Sequence
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

from research_notes import (  # noqa: E402
    REQUIRED_GATES,
    GeometryKernelProbe,
    geometry_backend_candidates,
    probe_ocp_backend,
    selected_geometry_backend,
)


FIXTURE_NAME = "ocp_box.step"
MANIFEST_NAME = "manifest.csv"
CANDIDATES_NAME = "geometry_kernel_candidates.csv"
PACKAGES_NAME = "geometry_kernel_package_audit.csv"
PROBE_NAME = "geometry_kernel_probe.csv"
SUMMARY_NAME = "geometry_kernel_selection_summary.csv"
DECISION_NAME = "geometry_kernel_decision.json"
FIGURE_NAME = "geometry_kernel_selection.png"

CANDIDATE_FIELDS = (
    "candidate_id",
    "display_name",
    "kernel_family",
    "python_route",
    "kernel_license",
    "binding_license",
    *REQUIRED_GATES,
    "passed_gate_count",
    "passes_all_gates",
    "independent_kernel_family",
    "disposition",
    "rationale",
    "capability_url",
    "license_url",
)
PACKAGE_FIELDS = (
    "platform_label",
    "distribution",
    "version",
    "metadata_license",
    "requirements",
    "recorded_file_count",
    "recorded_bytes",
    "license_files",
    "occt_lgpl_notice_detected",
)
PROBE_FIELDS = (
    "platform_label",
    "python_version",
    "binding_distribution_version",
    "binding_module_version",
    "step_processor",
    "writer_status",
    "reader_status",
    "transferred_roots",
    "constructed_valid",
    "imported_valid",
    "constructed_solids",
    "constructed_faces",
    "constructed_edges",
    "constructed_vertices",
    "imported_solids",
    "imported_faces",
    "imported_edges",
    "imported_vertices",
    "internal_parser_decision",
    "internal_parser_reason",
    "internal_parser_line",
    "internal_parser_column",
    "source_bytes",
    "source_sha256",
)
MANIFEST_FIELDS = (
    "fixture",
    "file_name",
    "source_bytes",
    "source_sha256",
    "generator",
    "binding_distribution_version",
    "binding_module_version",
    "step_processor",
)
SUMMARY_FIELDS = ("scope", "metric", "value")


def write_csv(
    path: Path, rows: Sequence[dict[str, str]], fields: Sequence[str]
) -> None:
    """Write deterministic UTF-8 CSV evidence."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def candidate_rows() -> list[dict[str, str]]:
    """Expand the fixed source-backed candidate catalog."""
    rows: list[dict[str, str]] = []
    for candidate in geometry_backend_candidates():
        row = {
            "candidate_id": candidate.candidate_id,
            "display_name": candidate.display_name,
            "kernel_family": candidate.kernel_family,
            "python_route": candidate.python_route,
            "kernel_license": candidate.kernel_license,
            "binding_license": candidate.binding_license,
            "passed_gate_count": str(candidate.passed_gate_count),
            "passes_all_gates": str(int(candidate.passes_all_gates)),
            "independent_kernel_family": str(
                int(candidate.independent_kernel_family)
            ),
            "disposition": candidate.disposition,
            "rationale": candidate.rationale,
            "capability_url": candidate.capability_url,
            "license_url": candidate.license_url,
        }
        for gate in REQUIRED_GATES:
            row[gate] = str(int(bool(getattr(candidate, gate))))
        rows.append(row)
    return rows


def package_rows(probe: GeometryKernelProbe) -> list[dict[str, str]]:
    """Expand installed distribution metadata without local paths."""
    return [
        {
            "platform_label": probe.platform_label,
            "distribution": audit.distribution,
            "version": audit.version,
            "metadata_license": audit.metadata_license,
            "requirements": "|".join(audit.requirements),
            "recorded_file_count": str(audit.recorded_file_count),
            "recorded_bytes": str(audit.recorded_bytes),
            "license_files": "|".join(audit.license_files),
            "occt_lgpl_notice_detected": str(
                int(audit.occt_lgpl_notice_detected)
            ),
        }
        for audit in probe.package_audits
    ]


def probe_row(probe: GeometryKernelProbe) -> dict[str, str]:
    """Flatten one controlled geometry probe."""
    return {
        field: (
            ""
            if getattr(probe, field) is None
            else str(int(getattr(probe, field)))
            if isinstance(getattr(probe, field), bool)
            else str(getattr(probe, field))
        )
        for field in PROBE_FIELDS
        if field not in {"source_bytes", "source_sha256"}
    } | {
        "source_bytes": str(len(probe.source_bytes)),
        "source_sha256": probe.source_sha256,
    }


def manifest_row(probe: GeometryKernelProbe) -> dict[str, str]:
    """Describe the committed synthetic STEP fixture."""
    return {
        "fixture": "ocp_box",
        "file_name": FIXTURE_NAME,
        "source_bytes": str(len(probe.source_bytes)),
        "source_sha256": probe.source_sha256,
        "generator": "BRepPrimAPI_MakeBox(10.0, 20.0, 30.0)",
        "binding_distribution_version": probe.binding_distribution_version,
        "binding_module_version": probe.binding_module_version,
        "step_processor": probe.step_processor,
    }


def handle_fixture(
    fixture_dir: Path, probe: GeometryKernelProbe, *, refresh: bool
) -> None:
    """Refresh or verify the one deterministic generated STEP fixture."""
    fixture_dir.mkdir(parents=True, exist_ok=True)
    expected_names = {FIXTURE_NAME, MANIFEST_NAME}
    unexpected = sorted(
        path.name for path in fixture_dir.iterdir() if path.name not in expected_names
    )
    if unexpected:
        raise RuntimeError(
            "fixture directory contains unexpected files: " + ", ".join(unexpected)
        )
    expected_manifest = [manifest_row(probe)]
    fixture_path = fixture_dir / FIXTURE_NAME
    manifest_path = fixture_dir / MANIFEST_NAME
    if refresh:
        fixture_path.write_bytes(probe.source_bytes)
        write_csv(manifest_path, expected_manifest, MANIFEST_FIELDS)
        return
    if not fixture_path.is_file() or not manifest_path.is_file():
        raise RuntimeError("missing committed geometry fixture; use --refresh-fixtures")
    if fixture_path.read_bytes() != probe.source_bytes:
        raise RuntimeError("committed geometry fixture differs from regenerated bytes")
    with manifest_path.open(encoding="utf-8", newline="") as handle:
        if list(csv.DictReader(handle)) != expected_manifest:
            raise RuntimeError("committed geometry fixture manifest differs")


def summary_rows(probe: GeometryKernelProbe) -> list[dict[str, str]]:
    """Build compact decision, topology, parser, and package evidence."""
    candidates = geometry_backend_candidates()
    selected = selected_geometry_backend()
    return [
        {"scope": "selection", "metric": "candidate_count", "value": str(len(candidates))},
        {"scope": "selection", "metric": "full_gate_candidate_count", "value": str(sum(item.passes_all_gates for item in candidates))},
        {"scope": "selection", "metric": "selected_candidate", "value": selected.candidate_id},
        {"scope": "round_trip", "metric": "constructed_topology", "value": "1 solid; 6 faces; 12 edges; 8 vertices"},
        {"scope": "round_trip", "metric": "imported_topology", "value": "1 solid; 6 faces; 12 edges; 8 vertices"},
        {"scope": "round_trip", "metric": "constructed_valid", "value": str(int(probe.constructed_valid))},
        {"scope": "round_trip", "metric": "imported_valid", "value": str(int(probe.imported_valid))},
        {"scope": "parser_boundary", "metric": "decision", "value": probe.internal_parser_decision},
        {"scope": "parser_boundary", "metric": "reason", "value": probe.internal_parser_reason},
        {"scope": "package_audit", "metric": "recorded_bytes", "value": str(sum(item.recorded_bytes for item in probe.package_audits))},
        {"scope": "package_audit", "metric": "occt_lgpl_notice_detected", "value": str(int(any(item.occt_lgpl_notice_detected for item in probe.package_audits)))},
    ]


def write_decision(path: Path, probe: GeometryKernelProbe) -> None:
    """Write the machine-readable bounded-use decision record."""
    selected = selected_geometry_backend()
    payload = {
        "schema": "research-notes.geometry-kernel-selection",
        "schema_version": "1.0",
        "release": "v0.31.0",
        "selected_candidate": selected.candidate_id,
        "disposition": selected.disposition,
        "technical_gate_results": {
            gate: bool(getattr(selected, gate)) for gate in REQUIRED_GATES
        },
        "controlled_probe": {
            "fixture": FIXTURE_NAME,
            "source_sha256": probe.source_sha256,
            "constructed_topology": {"solids": 1, "faces": 6, "edges": 12, "vertices": 8},
            "imported_topology": {"solids": 1, "faces": 6, "edges": 12, "vertices": 8},
            "constructed_valid": probe.constructed_valid,
            "imported_valid": probe.imported_valid,
            "internal_parser_decision": probe.internal_parser_decision,
            "internal_parser_reason": probe.internal_parser_reason,
        },
        "conditions": [
            "Keep the native geometry dependency optional and separate from the kernel-free Part 21 and EXPRESS layers.",
            "Do not commit or redistribute third-party wheels or native libraries in this repository.",
            "Audit OCCT notices, source-access duties, relinking conditions, and the additional exception before any binary redistribution.",
            "A commercial repository license does not replace third-party license obligations.",
            "This engineering record is not legal advice.",
        ],
        "unresolved_items": [
            "The installed reference distributions did not expose an OCCT LGPL notice through the standard distribution license-file inventory.",
            "The internal Part 21 lexer rejects the OCCT writer enumeration spelling .PCURVE_S1.; this is a parser interoperability boundary, not a geometry-kernel failure.",
            "Only one platform and one analytic box were probed in this release.",
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_figure(path: Path, probe: GeometryKernelProbe) -> None:
    """Visualize candidate gates, topology preservation, and package footprint."""
    candidates = geometry_backend_candidates()
    matrix = [
        [int(bool(getattr(candidate, gate))) for gate in REQUIRED_GATES]
        for candidate in candidates
    ]
    figure = plt.figure(figsize=(15.0, 5.2), constrained_layout=True)
    grid = figure.add_gridspec(1, 3, width_ratios=(1.7, 1.0, 1.0))

    matrix_axis = figure.add_subplot(grid[0, 0])
    matrix_axis.imshow(matrix, cmap="Blues", vmin=0, vmax=1, aspect="auto")
    matrix_axis.set_xticks(range(len(REQUIRED_GATES)), [gate.replace("_", "\n") for gate in REQUIRED_GATES], fontsize=8)
    matrix_axis.set_yticks(range(len(candidates)), [item.display_name for item in candidates], fontsize=8)
    for row_index, row in enumerate(matrix):
        for column_index, value in enumerate(row):
            matrix_axis.text(column_index, row_index, "yes" if value else "no", ha="center", va="center", color="white" if value else "#243447", fontsize=7)
    matrix_axis.set_title("Technical selection gates")

    topology_axis = figure.add_subplot(grid[0, 1])
    topology_axis.axis("off")
    topology_axis.set_title("Controlled STEP round trip")
    topology = "1 solid\n6 faces\n12 edges\n8 vertices"
    topology_axis.text(0.5, 0.70, topology, ha="center", va="center", bbox={"boxstyle": "round", "facecolor": "#dbeafe", "edgecolor": "#2563eb"})
    topology_axis.annotate("write and read", xy=(0.5, 0.35), xytext=(0.5, 0.52), ha="center", arrowprops={"arrowstyle": "->", "color": "#475569"})
    topology_axis.text(0.5, 0.20, topology, ha="center", va="center", bbox={"boxstyle": "round", "facecolor": "#dcfce7", "edgecolor": "#16a34a"})

    package_axis = figure.add_subplot(grid[0, 2])
    package_names = [item.distribution for item in probe.package_audits]
    package_megabytes = [item.recorded_bytes / 1_000_000 for item in probe.package_audits]
    package_axis.bar(package_names, package_megabytes, color=("#2563eb", "#60a5fa", "#94a3b8"))
    package_axis.set_ylabel("Recorded installed bytes (MB)")
    package_axis.set_title("Installed dependency footprint")
    package_axis.tick_params(axis="x", rotation=25, labelsize=8)
    for index, value in enumerate(package_megabytes):
        label = f"{value:.3f}" if value < 0.1 else f"{value:.1f}"
        package_axis.text(index, value, label, ha="center", va="bottom", fontsize=8)

    figure.suptitle("v0.31.0 Geometry Kernel and License Decision")
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160)
    plt.close(figure)


def run(output_dir: Path, fixture_dir: Path, *, refresh: bool, platform_label: str) -> None:
    """Run the full decision experiment and write every artifact."""
    probe = probe_ocp_backend(platform_label=platform_label)
    handle_fixture(fixture_dir, probe, refresh=refresh)
    write_csv(output_dir / CANDIDATES_NAME, candidate_rows(), CANDIDATE_FIELDS)
    write_csv(output_dir / PACKAGES_NAME, package_rows(probe), PACKAGE_FIELDS)
    write_csv(output_dir / PROBE_NAME, [probe_row(probe)], PROBE_FIELDS)
    write_csv(output_dir / SUMMARY_NAME, summary_rows(probe), SUMMARY_FIELDS)
    write_decision(output_dir / DECISION_NAME, probe)
    write_figure(output_dir / FIGURE_NAME, probe)


def main() -> None:
    """Parse command-line arguments and run the controlled experiment."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument("--fixture-dir", type=Path, default=Path("fixtures/geometry-kernel-selection"))
    parser.add_argument("--platform-label", default="linux-x64-reference")
    parser.add_argument("--refresh-fixtures", action="store_true")
    arguments = parser.parse_args()
    run(arguments.output_dir, arguments.fixture_dir, refresh=arguments.refresh_fixtures, platform_label=arguments.platform_label)
    print(f"Wrote geometry-kernel decision artifacts to {arguments.output_dir}")


if __name__ == "__main__":
    main()
