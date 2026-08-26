"""Tests for independent STEP parser and importer portability evidence."""

from pathlib import Path

import pytest

from research_notes.step_portability import (
    load_portability_fixtures,
    probe_step_portability,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def probe():
    return probe_step_portability(
        ROOT / "fixtures/step-round-trip-preservation",
        ROOT / "external/steputils",
        ROOT / "external/ifcopenshell_step_file_parser",
    )


def test_fixed_corpus_has_analytic_boolean_and_free_form_controls():
    fixtures = load_portability_fixtures(
        ROOT / "fixtures/step-round-trip-preservation"
    )
    assert [item.control_id for item in fixtures] == [
        "named_colored_box",
        "named_colored_through_hole",
        "named_colored_bspline",
    ]
    assert all(len(item.source_sha256) == 64 for item in fixtures)


def test_generated_curve_transition_enumeration_is_in_parser_coverage():
    from research_notes.step_part21 import lex_part21

    _, tokens = lex_part21(b".PCURVE_S1.")
    assert [(item.kind, item.value) for item in tokens] == [
        ("ENUMERATION", "PCURVE_S1")
    ]


def test_all_three_parsers_accept_each_fixed_fixture(probe):
    assert len(probe.parser_observations) == 9
    assert {item.parser for item in probe.parser_observations} == {
        "research_notes_part21",
        "steputils",
        "ifcopenshell_step_file_parser",
    }
    assert all(item.outcome == "accept" for item in probe.parser_observations)


def test_internal_parser_preserves_exact_source_and_reports_counts(probe):
    rows = [
        item
        for item in probe.parser_observations
        if item.parser == "research_notes_part21"
    ]
    assert all(item.exact_source_reconstruction is True for item in rows)
    assert all(item.entity_count and item.entity_count > 0 for item in rows)
    assert all(item.reference_count and item.reference_count > 0 for item in rows)


def test_import_routes_agree_on_geometry_and_topology(probe):
    assert len(probe.importer_observations) == 6
    assert all(item.topology_matches for item in probe.comparisons)
    assert all(item.geometry_matches for item in probe.comparisons)
    assert all(item.surface_inventory_matches for item in probe.comparisons)


def test_document_attributes_are_route_specific(probe):
    assert not any(item.shape_only_names_available for item in probe.comparisons)
    assert not any(item.shape_only_colors_available for item in probe.comparisons)
    assert all(item.xcaf_names_available for item in probe.comparisons)
    assert sum(item.xcaf_colors_available for item in probe.comparisons) == 2


def test_cross_kernel_claim_remains_false(probe):
    assert probe.independent_kernel_available is False
    assert probe.cross_kernel_conclusion is False
    assert probe.kernel_identity.startswith("Open CASCADE Technology")
