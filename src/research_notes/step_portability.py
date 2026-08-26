"""Compare independent STEP parsers and two OCCT import routes."""

from __future__ import annotations

import hashlib
import importlib.metadata
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from research_notes.modeling_common import ShapeMetrics, measure_shape
from research_notes.step_parser_comparison import (
    ExternalParserObservation,
    external_parser_definitions,
    observe_external_parser,
    verify_external_parser_checkout,
)
from research_notes.step_round_trip_preservation import (
    _document_observation,
    _read_document,
)
from research_notes.step_source_model import inspect_part21_source_model


CONTRACT_VERSION = "1.0.0"
ParserOutcome = Literal["accept", "reject", "error", "not_run"]


@dataclass(frozen=True)
class PortabilityFixture:
    """One committed STEP source used by every comparison route."""

    control_id: str
    file_name: str
    source_bytes: bytes
    source_sha256: str


@dataclass(frozen=True)
class ParserObservation:
    """One parser outcome with only parser-supported evidence populated."""

    control_id: str
    parser: str
    implementation_identity: str
    outcome: ParserOutcome
    diagnostic_class: str
    entity_count: int | None
    reference_count: int | None
    exact_source_reconstruction: bool | None


@dataclass(frozen=True)
class ImporterObservation:
    """One kernel import route and its geometric or document evidence."""

    control_id: str
    importer: str
    outcome: Literal["accept", "error"]
    names: tuple[str, ...]
    colors: tuple[tuple[float, float, float], ...]
    metrics: ShapeMetrics


@dataclass(frozen=True)
class ImporterComparison:
    """Route agreement without claiming an independent kernel comparison."""

    control_id: str
    topology_matches: bool
    geometry_matches: bool
    surface_inventory_matches: bool
    shape_only_names_available: bool
    xcaf_names_available: bool
    shape_only_colors_available: bool
    xcaf_colors_available: bool


@dataclass(frozen=True)
class PortabilityProbe:
    """Complete v0.49.0 independent parser and importer evidence."""

    fixtures: tuple[PortabilityFixture, ...]
    parser_observations: tuple[ParserObservation, ...]
    importer_observations: tuple[ImporterObservation, ...]
    comparisons: tuple[ImporterComparison, ...]
    parser_commits: tuple[tuple[str, str], ...]
    kernel_identity: str
    independent_kernel_available: bool
    cross_kernel_conclusion: bool


def load_portability_fixtures(fixture_dir: Path) -> tuple[PortabilityFixture, ...]:
    """Load the fixed analytic, Boolean, and free-form STEP corpus."""
    names = (
        "named_colored_box_source.step",
        "named_colored_through_hole_source.step",
        "named_colored_bspline_source.step",
    )
    fixtures: list[PortabilityFixture] = []
    for name in names:
        path = fixture_dir / name
        source_bytes = path.read_bytes()
        fixtures.append(
            PortabilityFixture(
                control_id=name.removesuffix("_source.step"),
                file_name=name,
                source_bytes=source_bytes,
                source_sha256=hashlib.sha256(source_bytes).hexdigest(),
            )
        )
    return tuple(fixtures)


def _external_row(
    fixture: PortabilityFixture,
    observation: ExternalParserObservation,
    identity: str,
) -> ParserObservation:
    return ParserObservation(
        fixture.control_id,
        observation.parser,
        identity,
        observation.outcome,
        observation.diagnostic_class,
        None,
        None,
        None,
    )


def _shape_only_import(path: Path) -> object:
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader

    reader = STEPControl_Reader()
    if reader.ReadFile(str(path)) != IFSelect_RetDone:
        raise RuntimeError("shape-only STEP read failed")
    if int(reader.TransferRoots()) < 1:
        raise RuntimeError("shape-only STEP transfer produced no roots")
    return reader.OneShape()


def _topology(metrics: ShapeMetrics) -> tuple[int, int, int, int, int]:
    return (
        metrics.vertex_count,
        metrics.edge_count,
        metrics.face_count,
        metrics.shell_count,
        metrics.solid_count,
    )


def probe_step_portability(
    fixture_dir: Path,
    steputils_root: Path,
    ifcopenshell_parser_root: Path,
) -> PortabilityProbe:
    """Run three independent parsers and two import routes on fixed bytes."""
    fixtures = load_portability_fixtures(fixture_dir)
    definitions = external_parser_definitions(
        steputils_root, ifcopenshell_parser_root
    )
    parser_commits = tuple(
        (definition.parser, verify_external_parser_checkout(definition))
        for definition in definitions
    )
    parser_rows: list[ParserObservation] = []
    importer_rows: list[ImporterObservation] = []
    comparisons: list[ImporterComparison] = []
    with tempfile.TemporaryDirectory(prefix="research-notes-portability-") as directory:
        root = Path(directory)
        for fixture in fixtures:
            path = root / fixture.file_name
            path.write_bytes(fixture.source_bytes)
            internal = inspect_part21_source_model(fixture.source_bytes)
            parser_rows.append(
                ParserObservation(
                    fixture.control_id,
                    "research_notes_part21",
                    "repository source at study commit",
                    "accept" if internal.decision == "accept" else "reject",
                    internal.reason_code,
                    internal.entity_count,
                    internal.reference_count,
                    internal.exact_source_reconstruction,
                )
            )
            for definition in definitions:
                external = observe_external_parser(definition, path)
                parser_rows.append(
                    _external_row(
                        fixture,
                        external,
                        f"{definition.repository}@{definition.expected_commit}",
                    )
                )

            shape_only_metrics = measure_shape(_shape_only_import(path))
            shape_only = ImporterObservation(
                fixture.control_id,
                "occt_shape_only",
                "accept",
                (),
                (),
                shape_only_metrics,
            )
            document = _read_document(path)
            xcaf_observation, _ = _document_observation(
                fixture.control_id,
                "source_import",
                fixture.file_name,
                fixture.source_bytes,
                document,
            )
            xcaf = ImporterObservation(
                fixture.control_id,
                "occt_xcaf",
                "accept",
                xcaf_observation.names,
                xcaf_observation.colors,
                xcaf_observation.metrics,
            )
            importer_rows.extend((shape_only, xcaf))
            comparisons.append(
                ImporterComparison(
                    fixture.control_id,
                    _topology(shape_only.metrics) == _topology(xcaf.metrics),
                    abs(shape_only.metrics.absolute_volume - xcaf.metrics.absolute_volume)
                    <= 1.0e-8
                    and abs(shape_only.metrics.surface_area - xcaf.metrics.surface_area)
                    <= 1.0e-8,
                    shape_only.metrics.surface_counts == xcaf.metrics.surface_counts,
                    bool(shape_only.names),
                    bool(xcaf.names),
                    bool(shape_only.colors),
                    bool(xcaf.colors),
                )
            )
    return PortabilityProbe(
        fixtures,
        tuple(parser_rows),
        tuple(importer_rows),
        tuple(comparisons),
        parser_commits,
        f"Open CASCADE Technology via cadquery-ocp {importlib.metadata.version('cadquery-ocp')}",
        False,
        False,
    )
