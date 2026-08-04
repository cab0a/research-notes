"""Source-backed geometry-kernel selection and optional OCCT runtime probe."""

from __future__ import annotations

import hashlib
import importlib.metadata
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from research_notes.step_part21 import Part21ParseError, parse_part21_document


GeometryBackendDisposition = Literal[
    "selected_bounded_research",
    "alternate_same_kernel",
    "application_runtime_reference",
    "meshing_reference",
    "computational_geometry_reference",
    "watch",
    "mesh_complement",
    "commercial_reference_only",
]

REQUIRED_GATES = (
    "step_exchange",
    "analytic_brep",
    "modeling",
    "python_api",
    "headless",
    "pip_reference_install",
)


@dataclass(frozen=True)
class GeometryBackendCandidate:
    """One source-backed backend or integration route."""

    candidate_id: str
    display_name: str
    kernel_family: str
    python_route: str
    kernel_license: str
    binding_license: str
    step_exchange: bool
    analytic_brep: bool
    modeling: bool
    python_api: bool
    headless: bool
    pip_reference_install: bool
    independent_kernel_family: bool
    disposition: GeometryBackendDisposition
    rationale: str
    capability_url: str
    license_url: str

    @property
    def passed_gate_count(self) -> int:
        """Return the number of v0.31 technical gates satisfied."""
        return sum(bool(getattr(self, gate)) for gate in REQUIRED_GATES)

    @property
    def passes_all_gates(self) -> bool:
        """Return whether every v0.31 technical gate is satisfied."""
        return self.passed_gate_count == len(REQUIRED_GATES)


@dataclass(frozen=True)
class InstalledPackageAudit:
    """Installed distribution metadata without machine-specific paths."""

    distribution: str
    version: str
    metadata_license: str
    requirements: tuple[str, ...]
    recorded_file_count: int
    recorded_bytes: int
    license_files: tuple[str, ...]
    occt_lgpl_notice_detected: bool


@dataclass(frozen=True)
class GeometryKernelProbe:
    """One headless synthetic box and STEP round-trip observation."""

    platform_label: str
    python_version: str
    binding_distribution_version: str
    binding_module_version: str
    step_processor: str
    writer_status: str
    reader_status: str
    transferred_roots: int
    constructed_valid: bool
    imported_valid: bool
    constructed_solids: int
    constructed_faces: int
    constructed_edges: int
    constructed_vertices: int
    imported_solids: int
    imported_faces: int
    imported_edges: int
    imported_vertices: int
    internal_parser_decision: Literal["accept", "quarantine", "reject"]
    internal_parser_reason: str
    internal_parser_line: int | None
    internal_parser_column: int | None
    source_bytes: bytes
    source_sha256: str
    package_audits: tuple[InstalledPackageAudit, ...]


def geometry_backend_candidates() -> tuple[GeometryBackendCandidate, ...]:
    """Return the fixed v0.31 comparison catalog and explicit dispositions."""
    return (
        GeometryBackendCandidate(
            "cadquery_ocp",
            "CadQuery OCP with OCCT",
            "OCCT",
            "cadquery-ocp",
            "LGPL-2.1 with OCCT additional exception",
            "Apache-2.0",
            True,
            True,
            True,
            True,
            True,
            True,
            False,
            "selected_bounded_research",
            "Only route that satisfies every reference-environment gate; binary redistribution remains a separate notice and compliance decision.",
            "https://pypi.org/project/cadquery-ocp/",
            "https://dev.opencascade.org/resources/licensing",
        ),
        GeometryBackendCandidate(
            "pythonocc_core",
            "pythonocc-core with OCCT",
            "OCCT",
            "pythonocc-core",
            "LGPL-2.1 with OCCT additional exception",
            "LGPL-3.0",
            True,
            True,
            True,
            True,
            True,
            False,
            False,
            "alternate_same_kernel",
            "Broad OCCT access and STEP support, but the documented reference installation is Conda rather than this project's pinned pip workflow.",
            "https://github.com/tpaviot/pythonocc-core",
            "https://github.com/tpaviot/pythonocc-core/blob/master/LICENSE",
        ),
        GeometryBackendCandidate(
            "freecad",
            "FreeCAD Python runtime",
            "OCCT",
            "FreeCAD Python API",
            "LGPL-2.1 with OCCT additional exception",
            "LGPL-2.1-or-later",
            True,
            True,
            True,
            True,
            True,
            False,
            False,
            "application_runtime_reference",
            "Capable application runtime with a broad Python API, but not the minimal library and pip dependency sought for the parser research stack.",
            "https://github.com/FreeCAD/FreeCAD",
            "https://www.freecad.org/contributing.php?lang=eng",
        ),
        GeometryBackendCandidate(
            "gmsh",
            "Gmsh OpenCASCADE API",
            "OCCT",
            "gmsh Python API",
            "LGPL-2.1 with OCCT additional exception",
            "GPL-2.0-or-later with linking exception",
            True,
            False,
            True,
            True,
            True,
            True,
            False,
            "meshing_reference",
            "Provides STEP manipulation and meshing through OCCT, but it is not the selected direct face-geometry inspection layer.",
            "https://gmsh.info/doc/texinfo/",
            "https://gmsh.info/?lang=en",
        ),
        GeometryBackendCandidate(
            "cgal",
            "CGAL",
            "CGAL",
            "No project-selected Python binding",
            "Package-specific GPL-3.0-or-later or LGPL-3.0-or-later; commercial licenses available",
            "not selected",
            False,
            False,
            True,
            False,
            True,
            False,
            True,
            "computational_geometry_reference",
            "Valuable computational-geometry library, but no direct project-qualified STEP-to-analytic-B-Rep Python route.",
            "https://www.cgal.org/",
            "https://doc.cgal.org/latest/Manual/license.html",
        ),
        GeometryBackendCandidate(
            "truck",
            "Truck",
            "Truck",
            "No maintained project-qualified Python binding",
            "Apache-2.0",
            "not selected",
            True,
            True,
            True,
            False,
            False,
            False,
            True,
            "watch",
            "Independent Rust B-Rep direction with STEP modules, but no Python route and the current user book does not claim official Linux support.",
            "https://truckkernel.com/",
            "https://github.com/ricosjp/truck/blob/master/LICENSE",
        ),
        GeometryBackendCandidate(
            "manifold",
            "Manifold",
            "Manifold",
            "manifold3d",
            "Apache-2.0",
            "Apache-2.0",
            False,
            False,
            True,
            True,
            True,
            True,
            True,
            "mesh_complement",
            "Strong triangle-mesh Boolean complement, not an analytic STEP B-Rep replacement.",
            "https://github.com/elalish/manifold",
            "https://github.com/elalish/manifold/blob/master/LICENSE",
        ),
        GeometryBackendCandidate(
            "parasolid",
            "Parasolid",
            "Parasolid",
            "Commercial SDK",
            "proprietary commercial terms",
            "proprietary commercial terms",
            False,
            True,
            True,
            False,
            True,
            False,
            True,
            "commercial_reference_only",
            "Technically relevant commercial reference, but no publicly reproducible Python and package route is available to this study.",
            "https://www.siemens.com/en-us/products/plm-components/parasolid/",
            "https://www.siemens.com/en-us/products/plm-components/parasolid/",
        ),
    )


def selected_geometry_backend() -> GeometryBackendCandidate:
    """Return the one backend selected for bounded research probes."""
    selected = tuple(
        candidate
        for candidate in geometry_backend_candidates()
        if candidate.disposition == "selected_bounded_research"
    )
    if len(selected) != 1:
        raise RuntimeError("exactly one bounded research backend must be selected")
    if not selected[0].passes_all_gates:
        raise RuntimeError("selected backend must satisfy every technical gate")
    return selected[0]


def audit_installed_distribution(name: str) -> InstalledPackageAudit:
    """Read installed distribution records without exporting absolute paths."""
    if not isinstance(name, str):
        raise TypeError("name must be a string")
    distribution = importlib.metadata.distribution(name)
    files = tuple(
        path
        for path in (distribution.files or ())
        if path.name != "REQUESTED"
    )
    license_files = tuple(
        sorted(
            str(path)
            for path in files
            if any(
                marker in str(path).lower()
                for marker in ("license", "copying", "notice")
            )
        )
    )
    notice_detected = False
    for relative_path in license_files:
        resolved = distribution.locate_file(relative_path)
        try:
            text = resolved.read_text(encoding="utf-8", errors="ignore")
        except (OSError, UnicodeError):
            continue
        lowered = text.lower()
        if "lesser general public license" in lowered and "open cascade" in lowered:
            notice_detected = True
    metadata = distribution.metadata
    return InstalledPackageAudit(
        distribution=name,
        version=distribution.version,
        metadata_license=(
            metadata.get("License-Expression") or metadata.get("License") or ""
        ),
        requirements=tuple(distribution.requires or ()),
        recorded_file_count=len(files),
        recorded_bytes=sum(path.size or 0 for path in files),
        license_files=license_files,
        occt_lgpl_notice_detected=notice_detected,
    )


def _shape_count(shape: object, kind: object) -> int:
    from OCP.TopExp import TopExp
    from OCP.TopTools import TopTools_IndexedMapOfShape

    shapes = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(shape, kind, shapes)
    return int(shapes.Extent())


def _shape_counts(shape: object) -> tuple[int, int, int, int]:
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_SOLID, TopAbs_VERTEX

    return tuple(
        _shape_count(shape, kind)
        for kind in (TopAbs_SOLID, TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX)
    )  # type: ignore[return-value]


_TIMESTAMP_PATTERN = re.compile(
    rb"(FILE_NAME\('Open CASCADE Shape Model',)'[^']*'"
)
_TRANSLATOR_COUNTER_PATTERN = re.compile(
    rb"(Open CASCADE STEP translator [0-9.]+) [0-9]+"
)
_NORMALIZED_TIMESTAMP = b"2000-01-01T00:00:00"


def normalize_ocp_step_bytes(source_bytes: bytes) -> bytes:
    """Replace the writer timestamp and process counter, retaining other bytes."""
    if not isinstance(source_bytes, bytes):
        raise TypeError("source_bytes must be bytes")
    normalized, replacements = _TIMESTAMP_PATTERN.subn(
        rb"\1'" + _NORMALIZED_TIMESTAMP + b"'", source_bytes, count=1
    )
    if replacements != 1:
        raise ValueError("expected exactly one Open CASCADE FILE_NAME timestamp")
    normalized, counter_replacements = _TRANSLATOR_COUNTER_PATTERN.subn(
        rb"\1 1", normalized
    )
    if counter_replacements != 2:
        raise ValueError("expected exactly two Open CASCADE translator counters")
    return normalized


def _status_name(status: object) -> str:
    return str(status).rsplit(".", 1)[-1]


def _step_processor(source_bytes: bytes) -> str:
    match = re.search(rb"'Open CASCADE STEP processor ([^']+)'", source_bytes)
    if match is None:
        return "unreported"
    return f"Open CASCADE STEP processor {match.group(1).decode('ascii')}"


def _internal_parser_observation(
    source_bytes: bytes,
) -> tuple[Literal["accept", "quarantine", "reject"], str, int | None, int | None]:
    try:
        parse_part21_document(source_bytes)
    except Part21ParseError as error:
        span = error.span
        return (
            error.decision,
            error.reason_code,
            None if span is None else span.start_line,
            None if span is None else span.start_column,
        )
    return "accept", "part21_parsed", None, None


def probe_ocp_backend(
    *, platform_label: str = "linux-x64-reference"
) -> GeometryKernelProbe:
    """Construct, export, normalize, and re-import one synthetic OCCT box."""
    if not isinstance(platform_label, str):
        raise TypeError("platform_label must be a string")
    if not platform_label:
        raise ValueError("platform_label must not be empty")

    import OCP
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import (
        STEPControl_AsIs,
        STEPControl_Reader,
        STEPControl_Writer,
    )

    shape = BRepPrimAPI_MakeBox(10.0, 20.0, 30.0).Shape()
    constructed_counts = _shape_counts(shape)
    constructed_valid = bool(BRepCheck_Analyzer(shape).IsValid())

    with tempfile.TemporaryDirectory(prefix="research-notes-ocp-") as directory:
        raw_path = Path(directory) / "ocp_box_raw.step"
        normalized_path = Path(directory) / "ocp_box.step"
        writer = STEPControl_Writer()
        transfer_status = writer.Transfer(shape, STEPControl_AsIs)
        if transfer_status != IFSelect_RetDone:
            raise RuntimeError(f"STEP transfer failed: {_status_name(transfer_status)}")
        writer_status = writer.Write(str(raw_path))
        if writer_status != IFSelect_RetDone:
            raise RuntimeError(f"STEP write failed: {_status_name(writer_status)}")
        source_bytes = normalize_ocp_step_bytes(raw_path.read_bytes())
        normalized_path.write_bytes(source_bytes)

        reader = STEPControl_Reader()
        reader_status = reader.ReadFile(str(normalized_path))
        if reader_status != IFSelect_RetDone:
            raise RuntimeError(f"STEP read failed: {_status_name(reader_status)}")
        transferred_roots = int(reader.TransferRoots())
        imported_shape = reader.OneShape()

    imported_counts = _shape_counts(imported_shape)
    imported_valid = bool(BRepCheck_Analyzer(imported_shape).IsValid())
    parser_decision, parser_reason, parser_line, parser_column = (
        _internal_parser_observation(source_bytes)
    )
    package_audits = tuple(
        audit_installed_distribution(name)
        for name in ("cadquery-ocp", "cadquery-ocp-proxy", "vtk")
    )
    return GeometryKernelProbe(
        platform_label=platform_label,
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
        binding_distribution_version=importlib.metadata.version("cadquery-ocp"),
        binding_module_version=str(OCP.__version__),
        step_processor=_step_processor(source_bytes),
        writer_status=_status_name(writer_status),
        reader_status=_status_name(reader_status),
        transferred_roots=transferred_roots,
        constructed_valid=constructed_valid,
        imported_valid=imported_valid,
        constructed_solids=constructed_counts[0],
        constructed_faces=constructed_counts[1],
        constructed_edges=constructed_counts[2],
        constructed_vertices=constructed_counts[3],
        imported_solids=imported_counts[0],
        imported_faces=imported_counts[1],
        imported_edges=imported_counts[2],
        imported_vertices=imported_counts[3],
        internal_parser_decision=parser_decision,
        internal_parser_reason=parser_reason,
        internal_parser_line=parser_line,
        internal_parser_column=parser_column,
        source_bytes=source_bytes,
        source_sha256=hashlib.sha256(source_bytes).hexdigest(),
        package_audits=package_audits,
    )
