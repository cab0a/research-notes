"""Bracket-slot dimensions, conservative negatives, API boundaries and evidence."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from research_notes.brep_runtime import step_round_trip
from research_notes.public_step import read_step_for_inspection
from research_notes.slot_benchmark import BRACKET, EXPECTED, boundary_crosscheck, control_shapes
from research_notes.slot_inventory import inspect_slots, main, scan_straight_through_slots


@pytest.fixture(scope='module')
def bracket():
    return read_step_for_inspection(BRACKET).imported.shape


@pytest.fixture(scope='module')
def controls():
    return control_shapes()


def test_six_bracket_slots_have_measured_dimensions_positions_and_directions(bracket):
    result = scan_straight_through_slots(bracket)
    assert result['status'] == 'partial' and result['whole_opening_count'] is None
    assert result['recognized_slot_count'] == 6
    assert result['scanned_faces'] == 42 and result['scanned_solids'] == 1
    assert result['withheld_candidates'] == []
    wall_ids, opening_ids = set(), set()
    for slot, (position, direction) in zip(result['slots'], EXPECTED):
        assert [slot['width_mm'], slot['length_mm'], slot['depth_mm']] == [4.5, 7.5, 3.]
        assert slot['entry_center_mm'] == position
        assert slot['exit_center_mm'] == [*position[:2], 0.]
        assert slot['longitudinal_direction'] == direction
        assert slot['through_direction'] == [0., 0., -1.]
        assert not wall_ids.intersection(slot['wall_faces'])
        wall_ids.update(slot['wall_faces'])
        for edges in slot['opening_edges']:
            assert not opening_ids.intersection(edges)
            opening_ids.update(edges)
    assert len(wall_ids) == 24 and len(opening_ids) == 48
    assert scan_straight_through_slots(bracket) == result


def test_boundary_measurements_agree_without_support_radii(bracket):
    slots = scan_straight_through_slots(bracket)['slots']
    result = boundary_crosscheck(bracket, slots)
    assert result['passed'] and result['observed_four_edge_inner_rims'] == result['matched_rims'] == 12
    assert result['max_length_error_mm'] < 1e-6
    assert result['same_kernel'] and not result['independent_ground_truth']
    wrong = copy.deepcopy(slots)
    wrong[0]['width_mm'] += .1
    assert not boundary_crosscheck(bracket, wrong)['passed']
    wrong = copy.deepcopy(slots)
    wrong[1]['opening_edges'] = wrong[0]['opening_edges']
    assert not boundary_crosscheck(bracket, wrong)['passed']


@pytest.mark.parametrize('name', ['through', 'blind', 'open_notch', 'stepped_capsule', 'stepped_rectangle', 'round_hole', 'boss', 'interrupted'])
@pytest.mark.parametrize('exchange', [False, True])
def test_declared_controls_before_and_after_step_exchange(controls, name, exchange):
    shape = controls[name]
    if exchange:
        shape = step_round_trip(shape, 'slot_test_'+name).imported_shape
    result = scan_straight_through_slots(shape)
    assert result['whole_opening_count'] is None
    if name == 'through':
        assert result['recognized_slot_count'] == 1
        s = result['slots'][0]
        assert [s['width_mm'], s['length_mm'], s['depth_mm']] == [2., 6., 4.]
        assert s['entry_center_mm'] == [7., 5., 4.]
        assert s['longitudinal_direction'] == [1., 0., 0.]
    else:
        assert result['status'] == 'unresolved'
        assert result['recognized_slot_count'] == 0 and result['slots'] == []


def test_rotation_and_translation_keep_source_coordinates(controls):
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec

    transform = gp_Trsf()
    transform.SetRotation(gp_Ax1(gp_Pnt(0,0,0), gp_Dir(1,2,3)), .73)
    transform.SetTranslationPart(gp_Vec(13, -7, 21))
    shape = BRepBuilderAPI_Transform(controls['through'], transform, True).Shape()
    result = scan_straight_through_slots(shape)
    assert result['recognized_slot_count'] == 1
    s = result['slots'][0]
    assert [s['width_mm'], s['length_mm'], s['depth_mm']] == [2., 6., 4.]
    ends = sorted([list(gp_Pnt(7,5,z).Transformed(transform).Coord()) for z in (0,4)], reverse=True)
    assert s['entry_center_mm'] == pytest.approx(ends[0],abs=1e-8)
    assert s['exit_center_mm'] == pytest.approx(ends[1],abs=1e-8)
    expected_long = gp_Dir(1,0,0).Transformed(transform).Coord()
    assert abs(sum(a*b for a,b in zip(s['longitudinal_direction'],expected_long))) == pytest.approx(1,abs=1e-8)
    assert s['through_direction'] == pytest.approx([(b-a)/4 for a,b in zip(*ends)],abs=1e-8)


def test_multiple_solids_keep_separate_local_slots(controls):
    from OCP.BRep import BRep_Builder
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.TopoDS import TopoDS_Compound
    from OCP.gp import gp_Trsf, gp_Vec

    transform = gp_Trsf()
    transform.SetTranslation(gp_Vec(30,0,0))
    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    builder.Add(compound, controls['through'])
    builder.Add(compound, BRepBuilderAPI_Transform(controls['through'], transform, True).Shape())
    result = scan_straight_through_slots(compound)
    assert result['recognized_slot_count'] == 2 and result['whole_opening_count'] is None
    assert [s['solid_index'] for s in result['slots']] == [1,2]
    assert [s['entry_center_mm'] for s in result['slots']] == [[7.,5.,4.],[37.,5.,4.]]


def test_excessive_tolerance_abstains(controls):
    from OCP.BRep import BRep_Builder
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopoDS import TopoDS
    from research_notes.brep_runtime import iter_shapes

    shape = BRepBuilderAPI_Copy(controls['through']).Shape()
    builder = BRep_Builder()
    for f in iter_shapes(shape, TopAbs_FACE):
        builder.UpdateFace(TopoDS.Face_s(f), 2e-5)
    result = scan_straight_through_slots(shape)
    assert result['recognized_slot_count'] == 0
    assert any('tolerance' in c['reason'] for c in result['withheld_candidates'])


def test_face_budget_refuses_before_recognition(monkeypatch, bracket):
    monkeypatch.setattr('research_notes.slot_inventory.MAX_FACES', 10)
    with pytest.raises(ValueError, match='512'):
        scan_straight_through_slots(bracket)


def test_python_and_cli_measure_the_same_snapshot(tmp_path):
    source = BRACKET.read_bytes()
    result = inspect_slots(BRACKET)
    assert result['source_sha256'] == hashlib.sha256(source).hexdigest()
    target = tmp_path/'slots.json'
    assert main([str(BRACKET), '--output', str(target)]) == 0
    assert json.loads(target.read_text()) == result
    assert BRACKET.read_bytes() == source


def test_cli_rejection_and_unresolved_are_not_zero_hole_certificates(tmp_path):
    source = tmp_path/'bad.step'
    source.write_text('invalid')
    output = tmp_path/'result.json'
    assert main([str(source), '--output', str(output)]) == 1
    assert json.loads(output.read_text())['whole_opening_count'] is None
    plain = Path('fixtures/hole-inventory/sources/no_holes.step')
    assert main([str(plain), '--output', str(output)]) == 2
    assert json.loads(output.read_text())['status'] == 'unresolved'


def test_cli_refuses_to_overwrite_source_or_alias(tmp_path):
    source = tmp_path/'input.step'
    source.write_bytes(BRACKET.read_bytes())
    original = source.read_bytes()
    alias = tmp_path/'alias.json'
    alias.hardlink_to(source)
    for target in (source, alias):
        with pytest.raises(SystemExit):
            main([str(source), '--output', str(target)])
        assert source.read_bytes() == original


def test_committed_bracket_evidence_matches_current_measurements(bracket):
    evidence = json.loads(Path('results/bracket-slot-inventory/results.json').read_text())
    current = scan_straight_through_slots(bracket)
    assert {k:v for k,v in evidence['result'].items() if k not in {'source_name','source_sha256'}} == current
    assert evidence['passed'] and evidence['repeats'] == 3 and evidence['repeat_results_identical']
    assert all(c['passed'] for c in evidence['controls'])
