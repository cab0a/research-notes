"""Small deterministic helpers shared by controlled B-Rep studies."""

from __future__ import annotations

import hashlib
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from research_notes.geometry_kernel import normalize_ocp_step_bytes


_ASSEMBLY_OCCURRENCE_ID_PATTERN = re.compile(
    rb"(NEXT_ASSEMBLY_USAGE_OCCURRENCE\(')[0-9]+(')"
)


@dataclass(frozen=True)
class StepRoundTrip:
    """Normalized STEP bytes and the shape produced by reading them back."""

    fixture_id: str
    file_name: str
    source_bytes: bytes
    source_sha256: str
    writer_status: str
    reader_status: str
    transferred_roots: int
    step_processor: str
    imported_shape: object


def status_name(value: object) -> str:
    """Return a stable short name for an OCCT enumeration value."""
    return str(value).rsplit(".", 1)[-1]


def shape_type_name(shape: object) -> str:
    """Return the lower-case OCCT topological shape type."""
    return status_name(shape.ShapeType()).removeprefix("TopAbs_").lower()


def indexed_shapes(shape: object, shape_type: object) -> object:
    """Return the unique subshapes of one requested topological type."""
    from OCP.TopExp import TopExp
    from OCP.TopTools import TopTools_IndexedMapOfShape

    mapping = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(shape, shape_type, mapping)
    return mapping


def shape_count(shape: object, shape_type: object) -> int:
    """Count unique subshapes of one requested topological type."""
    return int(indexed_shapes(shape, shape_type).Extent())


def topology_counts(shape: object) -> tuple[int, int, int, int, int]:
    """Return vertex, edge, face, shell, and solid counts."""
    from OCP.TopAbs import (
        TopAbs_EDGE,
        TopAbs_FACE,
        TopAbs_SHELL,
        TopAbs_SOLID,
        TopAbs_VERTEX,
    )

    return tuple(
        shape_count(shape, shape_type)
        for shape_type in (
            TopAbs_VERTEX,
            TopAbs_EDGE,
            TopAbs_FACE,
            TopAbs_SHELL,
            TopAbs_SOLID,
        )
    )  # type: ignore[return-value]


def iter_shapes(shape: object, shape_type: object) -> tuple[object, ...]:
    """Return subshapes in deterministic explorer order."""
    from OCP.TopExp import TopExp_Explorer

    result: list[object] = []
    explorer = TopExp_Explorer(shape, shape_type)
    while explorer.More():
        result.append(explorer.Current())
        explorer.Next()
    return tuple(result)


def maximum_tolerances(shape: object) -> tuple[float, float, float]:
    """Return maximum vertex, edge, and face tolerances."""
    from OCP.BRep import BRep_Tool
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_VERTEX
    from OCP.TopoDS import TopoDS

    requests = (
        (TopAbs_VERTEX, TopoDS.Vertex_s),
        (TopAbs_EDGE, TopoDS.Edge_s),
        (TopAbs_FACE, TopoDS.Face_s),
    )
    maxima: list[float] = []
    for shape_type, converter in requests:
        values = [
            float(BRep_Tool.Tolerance_s(converter(item)))
            for item in iter_shapes(shape, shape_type)
        ]
        maxima.append(max(values, default=0.0))
    return tuple(maxima)  # type: ignore[return-value]


def signed_volume(shape: object) -> float:
    """Return the kernel-computed signed volume without asserting eligibility."""
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    properties = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, properties)
    return float(properties.Mass())


def surface_area_and_centroid(shape: object) -> tuple[float, tuple[float, float, float]]:
    """Return surface area and centroid for a face or surface collection."""
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    properties = GProp_GProps()
    BRepGProp.SurfaceProperties_s(shape, properties)
    point = properties.CentreOfMass()
    return float(properties.Mass()), (
        float(point.X()),
        float(point.Y()),
        float(point.Z()),
    )


def _step_processor(source_bytes: bytes) -> str:
    match = re.search(rb"'Open CASCADE STEP processor ([^']+)'", source_bytes)
    if match is None:
        return "unreported"
    return f"Open CASCADE STEP processor {match.group(1).decode('ascii')}"


def _normalize_generated_occurrence_ids(source_bytes: bytes) -> bytes:
    """Reset volatile OCCT multi-root occurrence IDs in encounter order."""
    next_id = 0

    def replacement(match: re.Match[bytes]) -> bytes:
        nonlocal next_id
        next_id += 1
        return match.group(1) + str(next_id).encode("ascii") + match.group(2)

    return _ASSEMBLY_OCCURRENCE_ID_PATTERN.sub(replacement, source_bytes)


def step_entity_count(source_bytes: bytes, entity_name: str) -> int:
    """Count exact STEP entity constructors in normalized source bytes."""
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*", entity_name):
        raise ValueError("entity_name must be an upper-case STEP identifier")
    return len(
        re.findall(
            rb"=\s*" + entity_name.encode("ascii") + rb"\(", source_bytes
        )
    )


def step_round_trip(shape: object, fixture_id: str) -> StepRoundTrip:
    """Write, narrowly normalize, and read one synthetic STEP fixture."""
    if not isinstance(fixture_id, str):
        raise TypeError("fixture_id must be a string")
    if not re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", fixture_id):
        raise ValueError("fixture_id must use lower-case snake case")

    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_AsIs, STEPControl_Reader, STEPControl_Writer

    file_name = f"{fixture_id}.step"
    with tempfile.TemporaryDirectory(prefix="research-notes-brep-") as directory:
        path = Path(directory) / file_name
        writer = STEPControl_Writer()
        transfer_status = writer.Transfer(shape, STEPControl_AsIs)
        if transfer_status != IFSelect_RetDone:
            raise RuntimeError(
                f"STEP transfer failed for {fixture_id}: {status_name(transfer_status)}"
            )
        writer_status = writer.Write(str(path))
        if writer_status != IFSelect_RetDone:
            raise RuntimeError(
                f"STEP write failed for {fixture_id}: {status_name(writer_status)}"
            )
        raw_bytes = path.read_bytes()
        translator_occurrences = len(
            re.findall(rb"Open CASCADE STEP translator [0-9.]+ [0-9]+", raw_bytes)
        )
        source_bytes = normalize_ocp_step_bytes(
            raw_bytes,
            expected_translator_occurrences=translator_occurrences,
        )
        source_bytes = _normalize_generated_occurrence_ids(source_bytes)
        path.write_bytes(source_bytes)

        reader = STEPControl_Reader()
        reader_status = reader.ReadFile(str(path))
        if reader_status != IFSelect_RetDone:
            raise RuntimeError(
                f"STEP read failed for {fixture_id}: {status_name(reader_status)}"
            )
        transferred_roots = int(reader.TransferRoots())
        imported_shape = reader.OneShape()

    return StepRoundTrip(
        fixture_id=fixture_id,
        file_name=file_name,
        source_bytes=source_bytes,
        source_sha256=hashlib.sha256(source_bytes).hexdigest(),
        writer_status=status_name(writer_status),
        reader_status=status_name(reader_status),
        transferred_roots=transferred_roots,
        step_processor=_step_processor(source_bytes),
        imported_shape=imported_shape,
    )
