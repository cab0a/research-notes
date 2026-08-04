"""Deterministic AP242 product-path fixtures and staged observations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from research_notes.ap242_paths import (
    AP242PathLimitError,
    AP242PathLimits,
    AP242PathResult,
    DEFAULT_AP242_PATH_LIMITS,
    resolve_ap242_product_paths,
)
from research_notes.step_brep import build_step_brep_fixtures
from research_notes.step_graph import STEPGraphLimitError
from research_notes.step_part21 import Part21ParseError


@dataclass(frozen=True)
class AP242PathFixture:
    """One synthetic AP242 path fixture and its expected decision."""

    fixture: str
    category: str
    condition: str
    file_name: str
    expected_decision: Literal["accept", "quarantine", "reject"]
    expected_reason_code: str
    source_bytes: bytes
    path_limits: AP242PathLimits = DEFAULT_AP242_PATH_LIMITS


@dataclass(frozen=True)
class AP242PathObservation:
    """One staged AP242 semantic-path observation."""

    decision: Literal["accept", "quarantine", "reject"]
    reason_code: str
    product_definition_count: int
    path_count: int
    relation_count: int
    representation_item_count: int
    placement_count: int
    unit_count: int
    diagnostic_count: int
    result: AP242PathResult | None


_AP242_SCHEMA = "AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF"


def _exchange(data_text: str, *, schema: str = _AP242_SCHEMA) -> bytes:
    return f"""ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('Controlled AP242 product path fixture'),'4;3');
FILE_NAME('fixture.step','2026-01-01T00:00:00',('research-notes'),('research-notes'),'','','');
FILE_SCHEMA(('{schema}'));
ENDSEC;
DATA;
{data_text.strip()}
ENDSEC;
END-ISO-10303-21;
""".encode("utf-8")


def _fixture(
    fixture: str,
    category: str,
    condition: str,
    data_text: str,
    *,
    expected_decision: Literal["accept", "quarantine", "reject"] = "accept",
    expected_reason_code: str = "ap242_paths_resolved",
    schema: str = _AP242_SCHEMA,
    path_limits: AP242PathLimits = DEFAULT_AP242_PATH_LIMITS,
) -> AP242PathFixture:
    return AP242PathFixture(
        fixture,
        category,
        condition,
        f"{fixture}.step",
        expected_decision,
        expected_reason_code,
        _exchange(data_text, schema=schema),
        path_limits,
    )


def _shared_prefix() -> str:
    return """#1=APPLICATION_CONTEXT('managed model based 3d engineering');
#2=PRODUCT_CONTEXT('',#1,'mechanical');
#3=PRODUCT('P-001','Controlled block','',(#2));
#4=PRODUCT_DEFINITION_FORMATION('F-001','',#3);
#5=PRODUCT_DEFINITION_CONTEXT('part definition',#1,'design');
#6=PRODUCT_DEFINITION('PD-001','',#4,#5);"""


def _shape_and_context(
    *,
    representation_type: str = "SHAPE_REPRESENTATION",
    item_ids: str = "#30,#31",
    context_id: int = 40,
) -> str:
    return f"""#7=PRODUCT_DEFINITION_SHAPE('','',#6);
#8=SHAPE_DEFINITION_REPRESENTATION(#7,#20);
#20={representation_type}('controlled shape',({item_ids}),#{context_id});
#30=AXIS2_PLACEMENT_3D('',#32,#33,#34);
#31=BLOCK('block',#30,10.,20.,30.);
#32=CARTESIAN_POINT('',(0.,0.,0.));
#33=DIRECTION('',(0.,0.,1.));
#34=DIRECTION('',(1.,0.,0.));
#40=(GEOMETRIC_REPRESENTATION_CONTEXT(3)GLOBAL_UNIT_ASSIGNED_CONTEXT((#41,#42,#43))REPRESENTATION_CONTEXT('model','3D'));
#41=(LENGTH_UNIT()NAMED_UNIT(*)SI_UNIT(.MILLI.,.METRE.));
#42=(NAMED_UNIT(*)PLANE_ANGLE_UNIT()SI_UNIT($,.RADIAN.));
#43=(NAMED_UNIT(*)SI_UNIT($,.STERADIAN.)SOLID_ANGLE_UNIT());"""


def _complete_model(**kwargs: object) -> str:
    return _shared_prefix() + "\n" + _shape_and_context(**kwargs)


def _advanced_brep_model() -> str:
    """Reuse the independently checked v0.21 tetrahedron as an AP242 shape root."""
    tetrahedron = next(
        fixture
        for fixture in build_step_brep_fixtures()
        if fixture.fixture == "closed_tetrahedron"
    )
    text = tetrahedron.step_bytes.decode("utf-8")
    topology = text.split("DATA;\n", 1)[1].split("ENDSEC;", 1)[0].strip()
    product_path = """#101=APPLICATION_CONTEXT('managed model based 3d engineering');
#102=PRODUCT_CONTEXT('',#101,'mechanical');
#103=PRODUCT('P-002','Controlled tetrahedron','',(#102));
#104=PRODUCT_DEFINITION_FORMATION('F-002','',#103);
#105=PRODUCT_DEFINITION_CONTEXT('part definition',#101,'design');
#106=PRODUCT_DEFINITION('PD-002','',#104,#105);
#107=PRODUCT_DEFINITION_SHAPE('','',#106);
#108=SHAPE_DEFINITION_REPRESENTATION(#107,#120);
#120=ADVANCED_BREP_SHAPE_REPRESENTATION('controlled tetrahedron',(#35,#74),#140);
#140=(GEOMETRIC_REPRESENTATION_CONTEXT(3)GLOBAL_UNIT_ASSIGNED_CONTEXT((#141,#142,#143))REPRESENTATION_CONTEXT('model','3D'));
#141=(LENGTH_UNIT()NAMED_UNIT(*)SI_UNIT(.MILLI.,.METRE.));
#142=(NAMED_UNIT(*)PLANE_ANGLE_UNIT()SI_UNIT($,.RADIAN.));
#143=(NAMED_UNIT(*)SI_UNIT($,.STERADIAN.)SOLID_ANGLE_UNIT());"""
    return topology + "\n" + product_path


def build_ap242_path_fixtures() -> tuple[AP242PathFixture, ...]:
    """Build the complete deterministic v0.29 AP242 path corpus."""
    two_paths = _complete_model() + """
#9=SHAPE_DEFINITION_REPRESENTATION(#7,#21);
#21=SHAPE_REPRESENTATION('alternate shape',(#30),#40);"""
    no_units = _complete_model().replace(
        "(GEOMETRIC_REPRESENTATION_CONTEXT(3)GLOBAL_UNIT_ASSIGNED_CONTEXT((#41,#42,#43))REPRESENTATION_CONTEXT('model','3D'))",
        "(GEOMETRIC_REPRESENTATION_CONTEXT(3)REPRESENTATION_CONTEXT('model','3D'))",
    )
    return (
        _fixture(
            "ap242_block_path",
            "resolved_path",
            "one product definition, shape representation, placement, block, and SI context units",
            _complete_model(),
        ),
        _fixture(
            "ap242_advanced_brep_root",
            "representation_subtype",
            "the checked tetrahedron exposed through an advanced B-rep representation root",
            _advanced_brep_model(),
        ),
        _fixture(
            "ap242_multiple_representations",
            "path_multiplicity",
            "one product definition associated with two shape representations",
            two_paths,
        ),
        _fixture(
            "ap214_schema_boundary",
            "schema_boundary",
            "the same entity names declared under an unsupported application schema",
            _complete_model(),
            schema="AUTOMOTIVE_DESIGN",
            expected_decision="quarantine",
            expected_reason_code="unsupported_application_schema",
        ),
        _fixture(
            "no_product_definition",
            "optional_path",
            "an AP242 data section without a product-definition root",
            "#1=APPLICATION_CONTEXT('managed model based 3d engineering');",
            expected_decision="quarantine",
            expected_reason_code="product_definition_not_found",
        ),
        _fixture(
            "product_without_shape",
            "optional_path",
            "a product definition without a product-definition shape",
            _shared_prefix(),
            expected_decision="quarantine",
            expected_reason_code="product_definition_shape_not_found",
        ),
        _fixture(
            "shape_without_representation",
            "optional_path",
            "a product-definition shape without a representation association",
            _shared_prefix() + "\n#7=PRODUCT_DEFINITION_SHAPE('','',#6);",
            expected_decision="quarantine",
            expected_reason_code="shape_representation_not_found",
        ),
        _fixture(
            "unsupported_representation",
            "subset_boundary",
            "a shape association targeting a representation outside the controlled subset",
            _complete_model().replace(
                "SHAPE_REPRESENTATION('controlled shape'",
                "MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION_REPRESENTATION('controlled shape'",
            ),
            expected_decision="quarantine",
            expected_reason_code="representation_type_deferred",
        ),
        _fixture(
            "context_without_units",
            "context_boundary",
            "a geometric representation context without explicit global assigned units",
            no_units,
            expected_decision="quarantine",
            expected_reason_code="global_units_not_available",
        ),
        _fixture(
            "unclassified_item",
            "item_boundary",
            "a representation item type outside the controlled classifier",
            _complete_model(item_ids="#30,#35") + "\n#35=DESCRIPTIVE_REPRESENTATION_ITEM('note','value');",
            expected_decision="quarantine",
            expected_reason_code="representation_item_type_deferred",
        ),
        _fixture(
            "wrong_formation_target",
            "semantic_invalidity",
            "product-definition formation points to a non-product entity",
            _complete_model().replace("#4=PRODUCT_DEFINITION_FORMATION('F-001','',#3);", "#4=PRODUCT_DEFINITION_FORMATION('F-001','',#1);"),
            expected_decision="reject",
            expected_reason_code="unexpected_semantic_target",
        ),
        _fixture(
            "unresolved_formation",
            "semantic_invalidity",
            "product definition points to an absent local formation",
            _complete_model().replace("#6=PRODUCT_DEFINITION('PD-001','',#4,#5);", "#6=PRODUCT_DEFINITION('PD-001','',#404,#5);"),
            expected_decision="reject",
            expected_reason_code="unresolved_semantic_reference",
        ),
        _fixture(
            "product_parameter_count",
            "semantic_invalidity",
            "product encoding omits its frame-of-reference parameter",
            _complete_model().replace("#3=PRODUCT('P-001','Controlled block','',(#2));", "#3=PRODUCT('P-001','Controlled block','');"),
            expected_decision="reject",
            expected_reason_code="semantic_parameter_count_mismatch",
        ),
        _fixture(
            "path_budget",
            "resource_boundary",
            "two valid paths exceed a one-path semantic work budget",
            two_paths,
            expected_decision="quarantine",
            expected_reason_code="ap242_path_limit",
            path_limits=AP242PathLimits(max_paths=1),
        ),
    )


def inspect_ap242_path_fixture(fixture: AP242PathFixture) -> AP242PathObservation:
    """Resolve one fixture and preserve syntax, graph, and semantic decisions."""
    if not isinstance(fixture, AP242PathFixture):
        raise TypeError("fixture must be AP242PathFixture")
    try:
        result = resolve_ap242_product_paths(
            fixture.source_bytes,
            path_limits=fixture.path_limits,
        )
    except Part21ParseError as error:
        return _empty_observation(error.decision, error.reason_code)
    except (STEPGraphLimitError, AP242PathLimitError) as error:
        return _empty_observation("quarantine", error.reason_code)
    return AP242PathObservation(
        result.decision,
        result.reason_code,
        result.product_definition_count,
        result.path_count,
        result.relation_count,
        result.representation_item_count,
        result.placement_count,
        result.unit_count,
        len(result.diagnostics),
        result,
    )


def _empty_observation(
    decision: Literal["quarantine", "reject"], reason_code: str
) -> AP242PathObservation:
    return AP242PathObservation(
        decision, reason_code, 0, 0, 0, 0, 0, 0, 0, None
    )
