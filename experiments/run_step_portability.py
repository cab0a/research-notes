"""Generate v0.49.0 independent parser and importer portability evidence."""

from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

from research_notes.step_portability import (  # noqa: E402
    CONTRACT_VERSION,
    PortabilityProbe,
    probe_step_portability,
)


PARSER_NAME = "step_parser_portability.csv"
IMPORTER_NAME = "step_importer_portability.csv"
SUMMARY_NAME = "step_portability_summary.csv"
MANIFEST_NAME = "step_portability_manifest.csv"
CONTRACT_NAME = "step_portability_contract.json"
FIGURE_NAME = "step_portability.png"


def _float(value: float) -> str:
    return format(value, ".17g")


def _csv_bytes(rows: list[dict[str, object]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=tuple(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_csv_bytes(rows))


def parser_rows(probe: PortabilityProbe) -> list[dict[str, object]]:
    return [
        {
            "contract_version": CONTRACT_VERSION,
            "control_id": item.control_id,
            "parser": item.parser,
            "implementation_identity": item.implementation_identity,
            "outcome": item.outcome,
            "diagnostic_class": item.diagnostic_class,
            "entity_count": "" if item.entity_count is None else item.entity_count,
            "reference_count": "" if item.reference_count is None else item.reference_count,
            "exact_source_reconstruction": "" if item.exact_source_reconstruction is None else int(item.exact_source_reconstruction),
        }
        for item in probe.parser_observations
    ]


def importer_rows(probe: PortabilityProbe) -> list[dict[str, object]]:
    comparisons = {item.control_id: item for item in probe.comparisons}
    return [
        {
            "contract_version": CONTRACT_VERSION,
            "control_id": item.control_id,
            "importer": item.importer,
            "kernel_identity": probe.kernel_identity,
            "outcome": item.outcome,
            "vertex_count": item.metrics.vertex_count,
            "edge_count": item.metrics.edge_count,
            "face_count": item.metrics.face_count,
            "shell_count": item.metrics.shell_count,
            "solid_count": item.metrics.solid_count,
            "absolute_volume": _float(item.metrics.absolute_volume),
            "surface_area": _float(item.metrics.surface_area),
            "surface_counts": "|".join(f"{name}:{count}" for name, count in item.metrics.surface_counts),
            "names": "|".join(item.names),
            "colors": "|".join(",".join(_float(channel) for channel in color) for color in item.colors),
            "topology_matches_other_route": int(comparisons[item.control_id].topology_matches),
            "geometry_matches_other_route": int(comparisons[item.control_id].geometry_matches),
            "surface_inventory_matches_other_route": int(comparisons[item.control_id].surface_inventory_matches),
        }
        for item in probe.importer_observations
    ]


def summary_rows(probe: PortabilityProbe) -> list[dict[str, object]]:
    return [
        {"scope": "corpus", "metric": "step_files", "value": len(probe.fixtures)},
        {"scope": "parser", "metric": "implementations", "value": 3},
        {"scope": "parser", "metric": "accepted_observations", "value": sum(item.outcome == "accept" for item in probe.parser_observations)},
        {"scope": "importer", "metric": "routes", "value": 2},
        {"scope": "importer", "metric": "topology_agreements", "value": sum(item.topology_matches for item in probe.comparisons)},
        {"scope": "importer", "metric": "geometry_agreements", "value": sum(item.geometry_matches for item in probe.comparisons)},
        {"scope": "document", "metric": "xcaf_name_inventories", "value": sum(item.xcaf_names_available for item in probe.comparisons)},
        {"scope": "document", "metric": "xcaf_color_inventories", "value": sum(item.xcaf_colors_available for item in probe.comparisons)},
        {"scope": "kernel", "metric": "independent_kernels", "value": int(probe.independent_kernel_available)},
        {"scope": "claim", "metric": "cross_kernel_conclusion", "value": int(probe.cross_kernel_conclusion)},
    ]


def manifest_rows(probe: PortabilityProbe) -> list[dict[str, object]]:
    return [
        {
            "control_id": item.control_id,
            "file_name": item.file_name,
            "source_bytes": len(item.source_bytes),
            "source_sha256": item.source_sha256,
            "source_fixture": f"fixtures/step-round-trip-preservation/{item.file_name}",
        }
        for item in probe.fixtures
    ]


def write_contract(path: Path, probe: PortabilityProbe) -> None:
    payload = {
        "contract_version": CONTRACT_VERSION,
        "study_version": "v0.49.0",
        "title": "Independent Parser and Kernel Portability",
        "fixed_corpus": {item.file_name: item.source_sha256 for item in probe.fixtures},
        "parser_commits": dict(probe.parser_commits),
        "kernel_identity": probe.kernel_identity,
        "independent_kernel_available": probe.independent_kernel_available,
        "cross_kernel_conclusion": probe.cross_kernel_conclusion,
        "claim_boundaries": [
            "parser acceptance does not imply schema validity or geometric correctness",
            "the shape-only and XCAF routes share one OCCT kernel implementation",
            "document attribute availability is not comparable to a shape-only API that does not expose document labels",
            "three synthetic files do not establish general STEP portability",
            "cross-kernel portability remains untested until an independent kernel is selected",
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_figure(path: Path, probe: PortabilityProbe) -> None:
    parser_names = ("research_notes_part21", "steputils", "ifcopenshell_step_file_parser")
    accepted = [sum(item.parser == name and item.outcome == "accept" for item in probe.parser_observations) for name in parser_names]
    names = ["internal", "STEPutils", "IfcOpenShell\nparser"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    axes[0].bar(names, accepted, color=("#4472c4", "#70ad47", "#ed7d31"))
    axes[0].set_ylim(0, len(probe.fixtures) + 0.4)
    axes[0].set_ylabel("Accepted fixed fixtures")
    axes[0].set_title("Independent parser outcomes")
    agreements = [sum(item.topology_matches for item in probe.comparisons), sum(item.geometry_matches for item in probe.comparisons)]
    axes[1].bar(("Topology", "Geometry"), agreements, color=("#5b9bd5", "#a5a5a5"))
    axes[1].set_ylim(0, len(probe.fixtures) + 0.4)
    axes[1].set_ylabel("Agreements across import routes")
    axes[1].set_title("One-kernel route comparison")
    fig.suptitle("STEP portability evidence and explicit kernel gap")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160, metadata={"Software": "research-notes"})
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the deterministic STEP portability study.")
    parser.add_argument("--fixture-dir", type=Path, default=Path("fixtures/step-round-trip-preservation"))
    parser.add_argument("--steputils-root", type=Path, default=Path("external/steputils"))
    parser.add_argument("--ifcopenshell-parser-root", type=Path, default=Path("external/ifcopenshell_step_file_parser"))
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    args = parser.parse_args()
    probe = probe_step_portability(args.fixture_dir, args.steputils_root, args.ifcopenshell_parser_root)
    _write_csv(args.output_dir / PARSER_NAME, parser_rows(probe))
    _write_csv(args.output_dir / IMPORTER_NAME, importer_rows(probe))
    _write_csv(args.output_dir / SUMMARY_NAME, summary_rows(probe))
    _write_csv(args.output_dir / MANIFEST_NAME, manifest_rows(probe))
    write_contract(args.output_dir / CONTRACT_NAME, probe)
    write_figure(args.output_dir / FIGURE_NAME, probe)
    print(f"Wrote deterministic STEP portability evidence to {args.output_dir}")


if __name__ == "__main__":
    main()
