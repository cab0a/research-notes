"""Evaluate semantic and geometric preservation across repeated STEP exchange."""

from __future__ import annotations

import hashlib
import importlib.metadata
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from research_notes.brep_runtime import status_name
from research_notes.feature_recognition import build_feature_shapes
from research_notes.modeling_common import ShapeMetrics, measure_shape
from research_notes.primitive_round_trips import build_primitive_shapes


Stage = Literal["source_import", "reexport_import"]
CONTRACT_VERSION = "1.0.0"


@dataclass(frozen=True)
class PreservationControl:
    """Synthetic document truth kept outside the STEP exchange files."""

    control_id: str
    condition: str
    expected_names: tuple[str, ...]
    expected_colors: tuple[tuple[float, float, float], ...]


@dataclass(frozen=True)
class ExchangeFile:
    """One normalized source or re-exported STEP byte sequence."""

    control_id: str
    stage: Stage
    file_name: str
    source_bytes: bytes
    source_sha256: str


@dataclass(frozen=True)
class PreservationObservation:
    """One XCAF import observation with structure and B-Rep measurements."""

    control_id: str
    stage: Stage
    file_name: str
    source_sha256: str
    source_bytes: int
    top_level_shape_count: int
    product_definition_count: int
    advanced_face_count: int
    names: tuple[str, ...]
    colors: tuple[tuple[float, float, float], ...]
    metrics: ShapeMetrics


@dataclass(frozen=True)
class PreservationComparison:
    """Dimension-by-dimension source versus re-export preservation result."""

    control_id: str
    source_semantics_match_truth: bool
    source_attributes_match_truth: bool
    structure_preserved: bool
    semantics_preserved: bool
    geometry_preserved: bool
    topology_preserved: bool
    attributes_preserved: bool
    tolerances_preserved: bool
    normalized_bytes_identical: bool
    file_size_delta: int
    volume_absolute_difference: float
    surface_area_absolute_difference: float
    maximum_tolerance_difference: float


@dataclass(frozen=True)
class PreservationProbe:
    """Complete v0.48.0 repeated-exchange evidence."""

    controls: tuple[PreservationControl, ...]
    files: tuple[ExchangeFile, ...]
    observations: tuple[PreservationObservation, ...]
    comparisons: tuple[PreservationComparison, ...]
    preview_shapes: tuple[tuple[str, object], ...]
    binding_distribution_version: str


def preservation_controls() -> tuple[PreservationControl, ...]:
    """Return controls spanning analytic, trimmed, and free-form geometry."""
    return (
        PreservationControl(
            "named_colored_box",
            "one named red analytic solid",
            ("Controlled Box",),
            ((0.85, 0.15, 0.10),),
        ),
        PreservationControl(
            "named_colored_through_hole",
            "one named green Boolean solid",
            ("Controlled Through Hole",),
            ((0.15, 0.70, 0.25),),
        ),
        PreservationControl(
            "named_colored_bspline",
            "one named blue free-form shell",
            ("Controlled B-Spline Shell",),
            ((0.15, 0.30, 0.85),),
        ),
    )


def _shape_controls() -> dict[str, object]:
    return {
        "named_colored_box": build_primitive_shapes()["primitive_box"],
        "named_colored_through_hole": build_feature_shapes()["through_hole"],
        "named_colored_bspline": build_primitive_shapes()["primitive_bspline_patch"],
    }


def _new_document() -> object:
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDocStd import TDocStd_Document

    return TDocStd_Document(TCollection_ExtendedString("BinXCAF"))


def _document_tools(document: object) -> tuple[object, object]:
    from OCP.XCAFDoc import XCAFDoc_DocumentTool

    main = document.Main()
    return (
        XCAFDoc_DocumentTool.ShapeTool_s(main),
        XCAFDoc_DocumentTool.ColorTool_s(main),
    )


def _build_document(
    control: PreservationControl, shape: object
) -> object:
    from OCP.Quantity import Quantity_Color, Quantity_TOC_RGB
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name
    from OCP.XCAFDoc import XCAFDoc_ColorGen

    document = _new_document()
    shape_tool, color_tool = _document_tools(document)
    label = shape_tool.AddShape(shape, True, True)
    TDataStd_Name.Set_s(
        label, TCollection_ExtendedString(control.expected_names[0])
    )
    red, green, blue = control.expected_colors[0]
    color_tool.SetColor(
        label,
        Quantity_Color(red, green, blue, Quantity_TOC_RGB),
        XCAFDoc_ColorGen,
    )
    return document


def _normalized_step_bytes(path: Path) -> bytes:
    raw_bytes = path.read_bytes()
    normalized, timestamp_replacements = re.subn(
        rb"(FILE_NAME\('[^']*',)'[^']*'",
        rb"\1'2000-01-01T00:00:00'",
        raw_bytes,
        count=1,
    )
    if timestamp_replacements != 1:
        raise ValueError("expected exactly one STEP FILE_NAME timestamp")
    return re.sub(
        rb"(Open CASCADE STEP translator [0-9.]+) [0-9]+",
        rb"\1 1",
        normalized,
    )


def _write_document(document: object, path: Path) -> bytes:
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPCAFControl import STEPCAFControl_Writer

    writer = STEPCAFControl_Writer()
    writer.SetColorMode(True)
    writer.SetNameMode(True)
    if not writer.Transfer(document):
        raise RuntimeError("XCAF-to-STEP transfer failed")
    status = writer.Write(str(path))
    if status != IFSelect_RetDone:
        raise RuntimeError(f"STEP write failed: {status_name(status)}")
    source_bytes = _normalized_step_bytes(path)
    path.write_bytes(source_bytes)
    return source_bytes


def _read_document(path: Path) -> object:
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPCAFControl import STEPCAFControl_Reader

    document = _new_document()
    reader = STEPCAFControl_Reader()
    reader.SetColorMode(True)
    reader.SetNameMode(True)
    status = reader.ReadFile(str(path))
    if status != IFSelect_RetDone:
        raise RuntimeError(f"STEP read failed: {status_name(status)}")
    if not reader.Transfer(document):
        raise RuntimeError("STEP-to-XCAF transfer failed")
    return document


def _label_name(label: object) -> str:
    from OCP.TDataStd import TDataStd_Name

    attribute = TDataStd_Name()
    if not label.FindAttribute(TDataStd_Name.GetID_s(), attribute):
        return ""
    return attribute.Get().ToExtString()


def _document_observation(
    control_id: str,
    stage: Stage,
    file_name: str,
    source_bytes: bytes,
    document: object,
) -> tuple[PreservationObservation, object]:
    from OCP.Quantity import Quantity_Color
    from OCP.TDF import TDF_LabelSequence
    from OCP.XCAFDoc import XCAFDoc_ShapeTool

    shape_tool, color_tool = _document_tools(document)
    labels = TDF_LabelSequence()
    shape_tool.GetFreeShapes(labels)
    names: list[str] = []
    colors: list[tuple[float, float, float]] = []
    shapes: list[object] = []
    for index in range(1, labels.Length() + 1):
        label = labels.Value(index)
        names.append(_label_name(label))
        shapes.append(XCAFDoc_ShapeTool.GetShape_s(label))
    if not shapes:
        raise RuntimeError("XCAF import produced no free shapes")
    color_labels = TDF_LabelSequence()
    color_tool.GetColors(color_labels)
    for index in range(1, color_labels.Length() + 1):
        color = Quantity_Color()
        if color_tool.GetColor_s(color_labels.Value(index), color):
            colors.append((float(color.Red()), float(color.Green()), float(color.Blue())))
    combined = shape_tool.GetOneShape()
    observation = PreservationObservation(
        control_id=control_id,
        stage=stage,
        file_name=file_name,
        source_sha256=hashlib.sha256(source_bytes).hexdigest(),
        source_bytes=len(source_bytes),
        top_level_shape_count=labels.Length(),
        product_definition_count=len(
            re.findall(rb"=\s*PRODUCT_DEFINITION\(", source_bytes)
        ),
        advanced_face_count=len(re.findall(rb"=\s*ADVANCED_FACE\(", source_bytes)),
        names=tuple(names),
        colors=tuple(colors),
        metrics=measure_shape(combined),
    )
    return observation, combined


def _topology(metrics: ShapeMetrics) -> tuple[int, int, int, int, int]:
    return (
        metrics.vertex_count,
        metrics.edge_count,
        metrics.face_count,
        metrics.shell_count,
        metrics.solid_count,
    )


def _maximum_tolerance_difference(
    first: ShapeMetrics, second: ShapeMetrics
) -> float:
    return max(
        abs(a - b)
        for a, b in zip(
            (
                first.maximum_vertex_tolerance,
                first.maximum_edge_tolerance,
                first.maximum_face_tolerance,
            ),
            (
                second.maximum_vertex_tolerance,
                second.maximum_edge_tolerance,
                second.maximum_face_tolerance,
            ),
            strict=True,
        )
    )


def _close_colors(
    first: tuple[tuple[float, float, float], ...],
    second: tuple[tuple[float, float, float], ...],
) -> bool:
    return len(first) == len(second) and all(
        abs(a - b) <= 1.0e-6
        for first_color, second_color in zip(first, second, strict=True)
        for a, b in zip(first_color, second_color, strict=True)
    )


def probe_step_round_trip_preservation() -> PreservationProbe:
    """Run two normalized exchange generations for every control."""
    controls = preservation_controls()
    shapes = _shape_controls()
    files: list[ExchangeFile] = []
    observations: list[PreservationObservation] = []
    comparisons: list[PreservationComparison] = []
    previews: list[tuple[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="research-notes-preservation-") as directory:
        root = Path(directory)
        for control in controls:
            source_name = f"{control.control_id}_source.step"
            reexport_name = f"{control.control_id}_reexport.step"
            source_path = root / source_name
            reexport_path = root / reexport_name
            document = _build_document(control, shapes[control.control_id])
            source_bytes = _write_document(document, source_path)
            source_document = _read_document(source_path)
            source_observation, source_shape = _document_observation(
                control.control_id,
                "source_import",
                source_name,
                source_bytes,
                source_document,
            )
            reexport_bytes = _write_document(source_document, reexport_path)
            reexport_document = _read_document(reexport_path)
            reexport_observation, reexport_shape = _document_observation(
                control.control_id,
                "reexport_import",
                reexport_name,
                reexport_bytes,
                reexport_document,
            )
            files.extend(
                (
                    ExchangeFile(
                        control.control_id,
                        "source_import",
                        source_name,
                        source_bytes,
                        hashlib.sha256(source_bytes).hexdigest(),
                    ),
                    ExchangeFile(
                        control.control_id,
                        "reexport_import",
                        reexport_name,
                        reexport_bytes,
                        hashlib.sha256(reexport_bytes).hexdigest(),
                    ),
                )
            )
            observations.extend((source_observation, reexport_observation))
            first = source_observation.metrics
            second = reexport_observation.metrics
            volume_difference = abs(first.absolute_volume - second.absolute_volume)
            area_difference = abs(first.surface_area - second.surface_area)
            tolerance_difference = _maximum_tolerance_difference(first, second)
            comparisons.append(
                PreservationComparison(
                    control_id=control.control_id,
                    source_semantics_match_truth=(
                        source_observation.names == control.expected_names
                    ),
                    source_attributes_match_truth=_close_colors(
                        source_observation.colors, control.expected_colors
                    ),
                    structure_preserved=(
                        source_observation.top_level_shape_count
                        == reexport_observation.top_level_shape_count
                        and source_observation.product_definition_count
                        == reexport_observation.product_definition_count
                    ),
                    semantics_preserved=(
                        source_observation.names == reexport_observation.names
                    ),
                    geometry_preserved=(
                        volume_difference <= 1.0e-8
                        and area_difference <= 1.0e-8
                        and first.surface_counts == second.surface_counts
                    ),
                    topology_preserved=_topology(first) == _topology(second),
                    attributes_preserved=(
                        _close_colors(
                            source_observation.colors, reexport_observation.colors
                        )
                    ),
                    tolerances_preserved=tolerance_difference <= 1.0e-12,
                    normalized_bytes_identical=source_bytes == reexport_bytes,
                    file_size_delta=len(reexport_bytes) - len(source_bytes),
                    volume_absolute_difference=volume_difference,
                    surface_area_absolute_difference=area_difference,
                    maximum_tolerance_difference=tolerance_difference,
                )
            )
            previews.extend(
                (
                    (f"{control.control_id} source", source_shape),
                    (f"{control.control_id} re-export", reexport_shape),
                )
            )
    return PreservationProbe(
        controls=controls,
        files=tuple(files),
        observations=tuple(observations),
        comparisons=tuple(comparisons),
        preview_shapes=tuple(previews),
        binding_distribution_version=importlib.metadata.version("cadquery-ocp"),
    )
