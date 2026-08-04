"""Deterministic AP242 assembly, placement, and unit fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from research_notes.ap242_assembly import (
    DEFAULT_ASSEMBLY_LIMITS,
    AssemblyLimitError,
    AssemblyLimits,
    AssemblyResult,
    evaluate_ap242_assembly,
)
from research_notes.ap242_paths import AP242_SCHEMA_IDENTIFIER
from research_notes.step_graph import STEPGraphLimitError
from research_notes.step_part21 import Part21ParseError


@dataclass(frozen=True)
class AP242AssemblyFixture:
    """One synthetic assembly fixture and its declared evaluation route."""

    fixture: str
    category: str
    condition: str
    file_name: str
    expected_decision: Literal["accept", "quarantine", "reject"]
    expected_reason_code: str
    source_bytes: bytes
    assembly_limits: AssemblyLimits = DEFAULT_ASSEMBLY_LIMITS


@dataclass(frozen=True)
class AP242AssemblyObservation:
    """One bounded observation retaining an evaluated result when available."""

    decision: Literal["accept", "quarantine", "reject"]
    reason_code: str
    occurrence_count: int
    path_count: int
    relation_count: int
    unit_observation_count: int
    distinct_definition_count: int
    reused_definition_count: int
    maximum_depth: int
    diagnostic_count: int
    result: AssemblyResult | None


@dataclass(frozen=True)
class _Part:
    """Internal controlled product-definition specification."""

    key: str
    name: str
    base: int
    unit: Literal["millimetre", "inch", "missing"] = "millimetre"

    @property
    def definition_id(self) -> int:
        return self.base + 2

    @property
    def representation_id(self) -> int:
        return self.base + 5


@dataclass(frozen=True)
class _Occurrence:
    """Internal immediate-occurrence and placement specification."""

    parent: str
    child: str
    reference_designator: str
    base: int
    source_origin: tuple[float, float, float] = (0.0, 0.0, 0.0)
    target_origin: tuple[float, float, float] = (0.0, 0.0, 0.0)
    source_z: tuple[float, float, float] = (0.0, 0.0, 1.0)
    source_x: tuple[float, float, float] = (1.0, 0.0, 0.0)
    target_z: tuple[float, float, float] = (0.0, 0.0, 1.0)
    target_x: tuple[float, float, float] = (1.0, 0.0, 0.0)

    @property
    def source_placement_id(self) -> int:
        return self.base + 5

    @property
    def target_placement_id(self) -> int:
        return self.base + 6


def _format_vector(values: tuple[float, float, float]) -> str:
    return ",".join(f"{value:.9g}" for value in values)


def _exchange(data_text: str) -> bytes:
    return f"""ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('Controlled AP242 assembly fixture'),'4;3');
FILE_NAME('fixture.step','2026-01-01T00:00:00',('research-notes'),('research-notes'),'','','');
FILE_SCHEMA(('{AP242_SCHEMA_IDENTIFIER}'));
ENDSEC;
DATA;
{data_text.strip()}
ENDSEC;
END-ISO-10303-21;
""".encode("utf-8")


def _part_lines(part: _Part, item_ids: tuple[int, ...]) -> list[str]:
    base = part.base
    items = ",".join(f"#{item_id}" for item_id in item_ids)
    if part.unit == "millimetre":
        length_lines = [
            f"#{base + 12}=(LENGTH_UNIT()NAMED_UNIT(*)SI_UNIT(.MILLI.,.METRE.));"
        ]
        context_units = f"#{base + 12},#{base + 13},#{base + 14}"
    elif part.unit == "inch":
        length_lines = [
            f"#{base + 12}=(CONVERSION_BASED_UNIT('inch',#{base + 15})LENGTH_UNIT()NAMED_UNIT(*));",
            f"#{base + 15}=LENGTH_MEASURE_WITH_UNIT(LENGTH_MEASURE(25.4),#{base + 16});",
            f"#{base + 16}=(LENGTH_UNIT()NAMED_UNIT(*)SI_UNIT(.MILLI.,.METRE.));",
        ]
        context_units = f"#{base + 12},#{base + 13},#{base + 14}"
    else:
        length_lines = []
        context_units = f"#{base + 13},#{base + 14}"
    return [
        f"#{base}=PRODUCT('{part.key}','{part.name}','',(#2));",
        f"#{base + 1}=PRODUCT_DEFINITION_FORMATION('{part.key}-F','',#{base});",
        f"#{base + 2}=PRODUCT_DEFINITION('{part.key}-PD','',#{base + 1},#3);",
        f"#{base + 3}=PRODUCT_DEFINITION_SHAPE('','',#{base + 2});",
        f"#{base + 4}=SHAPE_DEFINITION_REPRESENTATION(#{base + 3},#{base + 5});",
        f"#{base + 5}=SHAPE_REPRESENTATION('{part.name}',({items}),#{base + 11});",
        f"#{base + 6}=AXIS2_PLACEMENT_3D('',#{base + 8},#{base + 9},#{base + 10});",
        f"#{base + 7}=BLOCK('{part.name} block',#{base + 6},10.,10.,10.);",
        f"#{base + 8}=CARTESIAN_POINT('',(0.,0.,0.));",
        f"#{base + 9}=DIRECTION('',(0.,0.,1.));",
        f"#{base + 10}=DIRECTION('',(1.,0.,0.));",
        f"#{base + 11}=(GEOMETRIC_REPRESENTATION_CONTEXT(3)GLOBAL_UNIT_ASSIGNED_CONTEXT(({context_units}))REPRESENTATION_CONTEXT('{part.key}','3D'));",
        *length_lines,
        f"#{base + 13}=(NAMED_UNIT(*)PLANE_ANGLE_UNIT()SI_UNIT($,.RADIAN.));",
        f"#{base + 14}=(NAMED_UNIT(*)SI_UNIT($,.STERADIAN.)SOLID_ANGLE_UNIT());",
    ]


def _occurrence_lines(
    occurrence: _Occurrence, parts: dict[str, _Part]
) -> list[str]:
    base = occurrence.base
    parent = parts[occurrence.parent]
    child = parts[occurrence.child]
    return [
        f"#{base}=NEXT_ASSEMBLY_USAGE_OCCURRENCE('O-{base}','{child.name} in {parent.name}','',#{parent.definition_id},#{child.definition_id},'{occurrence.reference_designator}');",
        f"#{base + 1}=PRODUCT_DEFINITION_SHAPE('','',#{base});",
        f"#{base + 2}=CONTEXT_DEPENDENT_SHAPE_REPRESENTATION(#{base + 3},#{base + 1});",
        f"#{base + 3}=(REPRESENTATION_RELATIONSHIP('','',#{child.representation_id},#{parent.representation_id})REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION(#{base + 4})SHAPE_REPRESENTATION_RELATIONSHIP());",
        f"#{base + 4}=ITEM_DEFINED_TRANSFORMATION('','',#{base + 5},#{base + 6});",
        f"#{base + 5}=AXIS2_PLACEMENT_3D('',#{base + 7},#{base + 9},#{base + 10});",
        f"#{base + 6}=AXIS2_PLACEMENT_3D('',#{base + 8},#{base + 11},#{base + 12});",
        f"#{base + 7}=CARTESIAN_POINT('',({_format_vector(occurrence.source_origin)}));",
        f"#{base + 8}=CARTESIAN_POINT('',({_format_vector(occurrence.target_origin)}));",
        f"#{base + 9}=DIRECTION('',({_format_vector(occurrence.source_z)}));",
        f"#{base + 10}=DIRECTION('',({_format_vector(occurrence.source_x)}));",
        f"#{base + 11}=DIRECTION('',({_format_vector(occurrence.target_z)}));",
        f"#{base + 12}=DIRECTION('',({_format_vector(occurrence.target_x)}));",
    ]


def _model(parts: tuple[_Part, ...], occurrences: tuple[_Occurrence, ...]) -> str:
    part_map = {part.key: part for part in parts}
    items: dict[str, list[int]] = {
        part.key: [part.base + 6, part.base + 7] for part in parts
    }
    for occurrence in occurrences:
        items[occurrence.child].append(occurrence.source_placement_id)
        items[occurrence.parent].append(occurrence.target_placement_id)
    lines = [
        "#1=APPLICATION_CONTEXT('managed model based 3d engineering');",
        "#2=PRODUCT_CONTEXT('',#1,'mechanical');",
        "#3=PRODUCT_DEFINITION_CONTEXT('part definition',#1,'design');",
    ]
    for part in parts:
        lines.extend(_part_lines(part, tuple(items[part.key])))
    for occurrence in occurrences:
        lines.extend(_occurrence_lines(occurrence, part_map))
    return "\n".join(lines)


def _fixture(
    fixture: str,
    category: str,
    condition: str,
    data_text: str,
    *,
    expected_decision: Literal["accept", "quarantine", "reject"] = "accept",
    expected_reason_code: str = "assembly_paths_evaluated",
    assembly_limits: AssemblyLimits = DEFAULT_ASSEMBLY_LIMITS,
) -> AP242AssemblyFixture:
    return AP242AssemblyFixture(
        fixture,
        category,
        condition,
        f"{fixture}.step",
        expected_decision,
        expected_reason_code,
        _exchange(data_text),
        assembly_limits,
    )


def build_ap242_assembly_fixtures() -> tuple[AP242AssemblyFixture, ...]:
    """Build the complete deterministic v0.30 assembly corpus."""
    root = _Part("ROOT", "Root assembly", 100)
    child = _Part("CHILD", "Reusable child", 200)
    single = _model(
        (root, child),
        (_Occurrence("ROOT", "CHILD", "C1", 1000, target_origin=(10, 20, 30)),),
    )
    rotated = _model(
        (root, child),
        (_Occurrence("ROOT", "CHILD", "C1", 1000, target_origin=(10, 0, 0), target_x=(0, 1, 0)),),
    )
    source_offset = _model(
        (root, child),
        (_Occurrence("ROOT", "CHILD", "C1", 1000, source_origin=(5, 0, 0), target_origin=(20, 0, 0)),),
    )
    sub = _Part("SUB", "Subassembly", 300)
    bolt = _Part("BOLT", "Reusable bolt", 400)
    nested = _model(
        (root, sub, bolt),
        (
            _Occurrence("ROOT", "SUB", "S1", 1000, target_origin=(100, 0, 0), target_x=(0, 1, 0)),
            _Occurrence("ROOT", "BOLT", "B1", 1100, target_origin=(10, 0, 0)),
            _Occurrence("ROOT", "BOLT", "B2", 1200, target_origin=(20, 0, 0)),
            _Occurrence("SUB", "BOLT", "B3", 1300, target_origin=(10, 0, 0)),
        ),
    )
    inch_child = _Part("INCH", "Inch child", 500, "inch")
    inch = _model(
        (root, inch_child),
        (_Occurrence("ROOT", "INCH", "I1", 1000, source_origin=(1, 0, 0), target_origin=(50.8, 0, 0)),),
    )
    no_occurrence = _model((root,), ())
    missing_shape = "\n".join(
        line for line in single.splitlines() if not line.startswith("#1001=")
    )
    missing_context_relation = "\n".join(
        line for line in single.splitlines() if not line.startswith("#1002=")
    )
    unsupported_transform = single.replace(
        "#1004=ITEM_DEFINED_TRANSFORMATION('','',#1005,#1006);",
        "#1004=FUNCTIONALLY_DEFINED_TRANSFORMATION('unsupported','');",
    )
    missing_length_part = _Part("CHILD", "Reusable child", 200, "missing")
    missing_units = _model(
        (root, missing_length_part),
        (_Occurrence("ROOT", "CHILD", "C1", 1000, target_origin=(10, 0, 0)),),
    )
    depth_model = _model(
        (root, sub, bolt),
        (
            _Occurrence("ROOT", "SUB", "S1", 1000),
            _Occurrence("SUB", "BOLT", "B1", 1100),
        ),
    )
    wrong_order = single.replace(
        "REPRESENTATION_RELATIONSHIP('','',#205,#105)",
        "REPRESENTATION_RELATIONSHIP('','',#105,#205)",
    )
    nonorthogonal = _model(
        (root, child),
        (_Occurrence("ROOT", "CHILD", "C1", 1000, target_x=(1, 0, 1)),),
    )
    unresolved_child = single.replace(
        "#102,#202,'C1'", "#102,#9999,'C1'"
    )
    duplicate_designator = _model(
        (root, child),
        (
            _Occurrence("ROOT", "CHILD", "C1", 1000, target_origin=(10, 0, 0)),
            _Occurrence("ROOT", "CHILD", "C1", 1100, target_origin=(20, 0, 0)),
        ),
    )
    cycle = _model(
        (root, child),
        (
            _Occurrence("ROOT", "CHILD", "C1", 1000),
            _Occurrence("CHILD", "ROOT", "R1", 1100),
        ),
    )
    conversion_cycle = inch.replace(
        "LENGTH_MEASURE(25.4),#516", "LENGTH_MEASURE(25.4),#512"
    )
    return (
        _fixture("single_translation", "accepted_transform", "one millimetre child translated in its parent", single),
        _fixture("rotated_occurrence", "accepted_transform", "one child rotated 90 degrees about the positive z axis", rotated),
        _fixture("source_frame_offset", "accepted_transform", "non-origin source frame distinguishes transform direction", source_offset),
        _fixture("nested_reuse", "accepted_structure", "one subassembly and three occurrences of one reused part", nested),
        _fixture("conversion_based_inch", "accepted_unit", "inch child coordinates normalized into a millimetre parent", inch),
        _fixture("no_assembly_occurrence", "optional_path", "a valid AP242 part without an assembly occurrence", no_occurrence, expected_decision="quarantine", expected_reason_code="assembly_occurrence_not_found"),
        _fixture("missing_occurrence_shape", "optional_path", "an occurrence without a product-definition shape association", missing_shape, expected_decision="quarantine", expected_reason_code="occurrence_shape_not_found"),
        _fixture("missing_context_dependent_relation", "optional_path", "an occurrence shape without a context-dependent relation", missing_context_relation, expected_decision="quarantine", expected_reason_code="context_dependent_shape_representation_not_found"),
        _fixture("unsupported_transform_operator", "subset_boundary", "a transformation operator outside the item-defined subset", unsupported_transform, expected_decision="quarantine", expected_reason_code="transformation_form_deferred"),
        _fixture("missing_length_unit", "subset_boundary", "a child representation context without a length unit", missing_units, expected_decision="quarantine", expected_reason_code="length_unit_not_available"),
        _fixture("assembly_depth_budget", "resource_boundary", "a two-level path evaluated with a one-level traversal budget", depth_model, expected_decision="quarantine", expected_reason_code="assembly_depth_limit", assembly_limits=AssemblyLimits(max_depth=1)),
        _fixture("wrong_representation_order", "semantic_invalidity", "parent and child representations reversed in the relationship", wrong_order, expected_decision="reject", expected_reason_code="assembly_representation_order_mismatch"),
        _fixture("nonorthogonal_placement", "semantic_invalidity", "placement axis and reference direction are not orthogonal", nonorthogonal, expected_decision="reject", expected_reason_code="nonorthogonal_placement_axes"),
        _fixture("unresolved_child_definition", "semantic_invalidity", "the occurrence points to an absent child definition", unresolved_child, expected_decision="reject", expected_reason_code="unresolved_semantic_reference"),
        _fixture("duplicate_reference_designator", "semantic_invalidity", "two children in one parent share a reference designator", duplicate_designator, expected_decision="reject", expected_reason_code="duplicate_reference_designator"),
        _fixture("assembly_cycle", "semantic_invalidity", "two definitions contain each other", cycle, expected_decision="reject", expected_reason_code="assembly_cycle"),
        _fixture("unit_conversion_cycle", "semantic_invalidity", "a conversion-based length unit points back to itself", conversion_cycle, expected_decision="reject", expected_reason_code="unit_conversion_cycle"),
    )


def inspect_ap242_assembly_fixture(
    fixture: AP242AssemblyFixture,
) -> AP242AssemblyObservation:
    """Evaluate one fixture through syntax, graph, semantic, and work limits."""
    if not isinstance(fixture, AP242AssemblyFixture):
        raise TypeError("fixture must be AP242AssemblyFixture")
    try:
        result = evaluate_ap242_assembly(
            fixture.source_bytes, assembly_limits=fixture.assembly_limits
        )
    except Part21ParseError as error:
        return _empty_observation(error.decision, error.reason_code)
    except (STEPGraphLimitError, AssemblyLimitError) as error:
        return _empty_observation("quarantine", error.reason_code)
    return AP242AssemblyObservation(
        result.decision,
        result.reason_code,
        result.occurrence_count,
        result.path_count,
        result.relation_count,
        result.unit_observation_count,
        result.distinct_definition_count,
        result.reused_definition_count,
        result.maximum_depth,
        len(result.diagnostics),
        result,
    )


def _empty_observation(
    decision: Literal["quarantine", "reject"], reason_code: str
) -> AP242AssemblyObservation:
    return AP242AssemblyObservation(
        decision, reason_code, 0, 0, 0, 0, 0, 0, 0, 0, None
    )
