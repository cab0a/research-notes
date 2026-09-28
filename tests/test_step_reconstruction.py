"""Proposals must come from geometry and preserve ambiguity and rejection."""

import json
import re
from pathlib import Path

import pytest

from research_notes.deterministic_recompute import recompute
from research_notes.step_reconstruction import read_step_input, reconstruct_step


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures/step-reconstruction"
CONTROLS = json.loads((FIXTURES / "controls.json").read_text())


@pytest.mark.parametrize("control", CONTROLS, ids=lambda c: c["control_id"])
def test_geometry_candidates_match_controlled_expectations(control):
    result = reconstruct_step(FIXTURES / f"{control['control_id']}.step")
    assert sorted(c.explanation for c in result.candidates) == sorted(control["expected_explanations"])
    for candidate in result.candidates:
        assert candidate.status == "unconfirmed"
        assert candidate.model.provenance == "unconfirmed_candidate"
        assert candidate.model.source_sha256 == result.imported.source_sha256
        assert not candidate.authoring_history_recovered
        assert candidate.material_difference_volume < 1e-7
        assert candidate.volume_residual < 1e-7 and candidate.area_residual < 1e-7
        assert candidate.topology_matches and candidate.supporting_faces
        assert 0 < candidate.fit_score <= 1


def test_renaming_input_and_false_sidecar_labels_cannot_change_candidates(tmp_path):
    source = FIXTURES / "through_hole.step"
    renamed = tmp_path / "this_is_a_rib.step"
    renamed.write_bytes(source.read_bytes())
    (tmp_path / "controls.json").write_text('[{"expected_explanations":["rib"]}]')
    first, second = reconstruct_step(source), reconstruct_step(renamed)
    assert first.candidates == second.candidates
    assert first.status == "ambiguous"
    assert {c.model.nodes[1].operation for c in first.candidates} == {"through_hole", "profile_hole"}


def test_translated_source_keeps_world_placement_in_candidate_and_regeneration():
    result = reconstruct_step(FIXTURES / "translated_hole.step")
    for candidate in result.candidates:
        parameters = dict(candidate.model.nodes[0].parameters)
        assert (parameters["origin_x"], parameters["origin_y"], parameters["origin_z"]) == (100., -25., 7.)
        regenerated = recompute(candidate.model).current_output().metrics
        assert regenerated.bounds_min == pytest.approx(result.imported.metrics.bounds_min, abs=1e-7)
        assert regenerated.absolute_volume == pytest.approx(result.imported.metrics.absolute_volume, abs=1e-7)


@pytest.mark.parametrize("source", ["rotated_plate", "unsupported_step"])
def test_unqualified_geometry_abstains(source):
    result = reconstruct_step(FIXTURES / f"{source}.step")
    assert result.status == "unsupported"
    assert not result.candidates


def test_non_millimetre_units_and_oversized_input_are_rejected(tmp_path):
    path = tmp_path / "input.step"
    payload = (FIXTURES / "through_hole.step").read_bytes()
    path.write_bytes(payload.replace(b"SI_UNIT(.MILLI.,.METRE.)", b"SI_UNIT($,.METRE.)"))
    with pytest.raises(ValueError, match="millimetre"):
        read_step_input(path)
    path.write_bytes(b" " * 2_000_001)
    with pytest.raises(ValueError, match="byte input limit"):
        read_step_input(path)


def test_external_references_are_not_resolved():
    with pytest.raises(ValueError, match="external STEP"):
        read_step_input(ROOT / "fixtures/resource-bounded-3d/external_reference.step")


def test_unused_millimetre_declaration_does_not_qualify_the_actual_context(tmp_path):
    payload = (FIXTURES / "through_hole.step").read_bytes()
    changed = re.sub(rb"GLOBAL_UNIT_ASSIGNED_CONTEXT\s*\(\(#[0-9]+,", b"GLOBAL_UNIT_ASSIGNED_CONTEXT((", payload)
    assert changed != payload
    path = tmp_path / "wrong_context.step"
    path.write_bytes(changed)
    with pytest.raises(ValueError, match="context must reference"):
        read_step_input(path)
