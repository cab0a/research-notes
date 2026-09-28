from dataclasses import asdict, replace

import numpy as np
import pytest

from research_notes.assembly_constraints import AssemblyConstraint, Placement, validate_assembly
from research_notes.assembly_controls import assembly_controls, slider_assembly
from research_notes.assembly_recompute import AssemblySession, assembly_from_dict, recompute_assembly


@pytest.mark.parametrize("name,document,status,dof,redundant", assembly_controls())
def test_declared_motion_and_constraint_states(name, document, status, dof, redundant):
    result = recompute_assembly(document)
    assert result.status == status
    assert result.solution.degrees_of_freedom == dof
    assert result.solution.redundant_equations == redundant
    assert len(result.solution.remaining_motion) == dof
    if status not in {"inconsistent", "not_converged"}:
        assert max((abs(r["residual"]) for r in result.solution.residuals), default=0.) < 1e-8
    if name in {"fully_fixed", "inch_initial_placement"}:
        assert result.solution.placements[1].translation == pytest.approx((0., 0., 3.), abs=1e-7)
        assert result.pair_checks[0]["minimum_distance_mm"] == pytest.approx(1., abs=1e-7)
    if name == "rotated_ground":
        assert result.solution.placements[1].translation == pytest.approx((4., 3.5, 1.+3*np.sqrt(3)/2), abs=1e-7)
    if status == "inconsistent":
        assert set(result.solution.conflict_constraints) == {"conflict", "gap"}
        assert not result.placed_shapes


def test_reuse_definition_recompute_and_contact_interference(tmp_path):
    session = AssemblySession(slider_assembly())
    baseline = session.recompute()
    assert len(baseline.component_results) == 1
    assert len(baseline.placed_shapes) == 2
    assert not baseline.placed_shapes[0][1].IsSame(baseline.placed_shapes[1][1])
    assert baseline.pair_checks[0]["status"] == "separated"
    assert not session.recompute().component_results[0][1].evaluated_nodes
    session.set_parameter("clearance", "0 * mm")
    with pytest.raises(ValueError, match="recompute"):
        session.export_step(tmp_path/"dirty.step")
    contact = session.recompute()
    assert contact.pair_checks[0]["status"] == "contact"
    session.export_step(tmp_path/"contact.step")
    session.set_parameter("clearance", "-1 * mm")
    overlap = session.recompute()
    assert overlap.pair_checks[0]["status"] == "interference"
    assert overlap.pair_checks[0]["overlap_volume_mm3"] == pytest.approx(4., abs=1e-7)
    with pytest.raises(ValueError, match="interference"):
        session.export_step(tmp_path/"overlap.step")
    session.set_parameter("clearance", "1 * mm")
    session.set_parameter("height", "3 * mm")
    changed = session.recompute()
    assert changed.solution.placements[1].translation == pytest.approx((0., 0., 4.), abs=1e-7)
    assert changed.pair_checks[0]["minimum_distance_mm"] == pytest.approx(1., abs=1e-7)
    session.export_step(tmp_path/"changed.step")
    session.set_parameter("height", "0.00001 * mm")
    failed = session.recompute()
    assert failed.status == "component_failed"
    assert session.last_valid is changed
    with pytest.raises(ValueError, match="fully constrained"):
        session.export_step(tmp_path/"failed.step")
    session.set_parameter("height", "3 * mm")
    recovered = session.recompute()
    assert recovered.status == "fully_constrained"
    assert not recovered.component_results[0][1].evaluated_nodes


def test_json_round_trip_and_invalid_references():
    document = slider_assembly()
    assert assembly_from_dict(asdict(document)) == document
    with pytest.raises(ValueError, match="duplicate"):
        validate_assembly(replace(document, occurrences=document.occurrences*2))
    with pytest.raises(ValueError, match="unknown component"):
        validate_assembly(replace(document, occurrences=(replace(document.occurrences[0], definition_id="missing"),)))
    with pytest.raises(ValueError, match="datum"):
        validate_assembly(replace(document, constraints=(replace(document.constraints[1], frame_a="missing"),)))
    with pytest.raises(ValueError, match="length"):
        validate_assembly(replace(document, occurrences=(replace(document.occurrences[0], initial=Placement(unit="deg")),)))
    with pytest.raises(ValueError, match="rotation domain"):
        validate_assembly(replace(document, occurrences=(replace(document.occurrences[0], initial=Placement(rotation_degrees=(100., 0., 0.))),)))


def test_free_motion_and_redundancy_block_unqualified_export(tmp_path):
    for name, document, status, dof, redundant in assembly_controls():
        if status == "fully_constrained":
            continue
        session = AssemblySession(document)
        result = session.recompute()
        with pytest.raises(ValueError, match="fully constrained"):
            session.export_step(tmp_path/(name+".step"))
        if result.pair_checks and dof:
            assert result.pair_checks[0]["placement_provisional"]
