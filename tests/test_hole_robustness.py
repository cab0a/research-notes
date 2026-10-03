"""Authored truth, conservative abstention and regression fixes for v1.12."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from research_notes.hole_inventory import analyze_step
from research_notes.hole_robustness import local_inventory, match_truth, audit_passed, exception_checks
from research_notes.hole_robustness_controls import geometry_controls, mixed_control, with_tolerance
from research_notes.public_step import read_step_for_inspection

FIXTURES=Path(__file__).resolve().parents[1]/'fixtures/hole-robustness'
DECLARED=json.loads((FIXTURES/'manifest.json').read_text())['controls']
IDS=[r['identifier'] for r in DECLARED]


@pytest.fixture(scope='module')
def controls():
    return {c.identifier:c for c in geometry_controls()}


@pytest.mark.parametrize('identifier',IDS)
@pytest.mark.parametrize('stage',['constructed','step_scanners','unified'])
def test_authored_truth_without_false_positives_or_hidden_stress_misses(identifier,stage,controls):
    control=controls[identifier]
    declared=next(c for c in DECLARED if c['identifier']==identifier)
    source=(FIXTURES/declared['source_path']).read_bytes()
    assert hashlib.sha256(source).hexdigest()==declared['source_sha256']
    assert control.expected==declared['expected']
    if stage=='unified':
        result=analyze_step(source,identifier+'.step',inspection=True,preview=False)
        assert result['hole_count'] is None and result['status'] in {'partial','unresolved'}
        assert len(result['holes'])==result['recognized_circular_hole_count']+result['recognized_slot_count']
    else:
        shape=control.shape if stage=='constructed' else read_step_for_inspection(FIXTURES/declared['source_path']).imported.shape
        result=local_inventory(shape)
    audit=match_truth(result['holes'],declared['expected'])
    assert not audit['false_positives'],audit
    assert audit['measurement_errors']==0,audit
    # Exploratory extreme coordinates/scales retain physical-feature truth;
    # misses are counted rather than changing the labels to zero openings.
    if control.category!='stress':
        assert not audit['missed_truth_indices'],audit


@pytest.mark.parametrize('kind',['face','edge','vertex'])
@pytest.mark.parametrize('value',[9e-6,1e-5,1.1e-5])
def test_face_edge_vertex_tolerance_boundary_is_conservative(kind,value,controls):
    result=local_inventory(with_tolerance(controls['mixed'].shape,kind,value))
    assert len(result['holes'])==(2 if value<=1e-5 else 0)
    if value>1e-5:
        circle=result['circle_diagnostics']['withheld_cylinders']
        slots=result['slot_diagnostics']['withheld_candidates']
        assert any('許容差' in c['reason'] for c in circle)
        assert any('tolerance' in c['reason'] for c in slots)


def test_rectangular_recess_is_withheld_with_specific_reason(controls):
    result=local_inventory(controls['circle_rectangular_shoulder'].shape)
    assert result['holes']==[]
    assert any('ポケット内' in c['reason'] for c in result['circle_diagnostics']['withheld_cylinders'])


def test_unknown_count_and_previous_state_on_source_and_native_exceptions():
    results=exception_checks((FIXTURES/'sources/mixed.step').read_bytes())
    assert len(results)==17
    assert all(r['passed'] for r in results),results
    assert {r['id'] for r in results if r.get('previous_state_preserved')}=={'empty_request','byte_limit'}


def test_truth_matching_detects_bad_dimensions_duplicate_rows_and_missing_features(controls):
    rows=local_inventory(controls['mixed'].shape)['holes']
    truth=controls['mixed'].expected
    wrong=copy.deepcopy(rows)
    wrong[0]['diameter_mm']+=.1
    audit=match_truth(wrong,truth)
    assert audit['measurement_errors']==1 and not audit_passed(audit,'qualified')
    wrong=copy.deepcopy(rows)+[copy.deepcopy(rows[0])]
    assert len(match_truth(wrong,truth)['false_positives'])==1
    audit=match_truth(rows[:1],truth)
    assert audit['missed_truth_indices']==[1]
    assert not audit_passed(audit,'qualified') and audit_passed(audit,'stress')
    assert not audit_passed(match_truth(wrong,truth),'stress')


def test_separate_blocking_component_is_an_explicit_local_scope_limit(controls):
    result=local_inventory(controls['assembly_obstructed'].shape)
    assert len(result['holes'])==2
    assert all(h['solid_index']==1 for h in result['holes'])
    assert result['circle_diagnostics']['scanned_solids']==2
    assert result['slot_diagnostics']['whole_opening_count'] is None
