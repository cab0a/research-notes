"""External partial recognition and negative controls; never certify unknown totals."""
import csv
import io
from pathlib import Path

import pytest

from research_notes.hole_inventory import HoleInventory, analyze_step, inventory_csv
from research_notes.public_hole_benchmark import boundary_crosscheck
from research_notes.public_hole_inventory import scan_circular_through_holes
from research_notes.public_step import read_step_for_inspection
from research_notes.public_step_corpus import CORPUS, verify_corpus

CONTROLS=Path(__file__).resolve().parents[1]/'fixtures/hole-inventory/sources'


@pytest.fixture(scope='module')
def results():
    manifest=verify_corpus()
    return {s['sample_id']:analyze_step((CORPUS/s['asset_path']).read_bytes(),s['sample_id']+'.step',inspection=True) for s in manifest['samples']}


def test_all_six_import_with_all_faces_and_unknown_whole_counts(results):
    assert len(results)==6
    for sample in verify_corpus()['samples']:
        r=results[sample['sample_id']]
        assert r['status']!='rejected' and r['hole_count'] is None
        assert r['scanned_faces']==sample['baseline']['faces']
        assert r['scanned_solids']==sample['baseline']['solids']
        if sample['sample_id']!='build123d_bracket':
            assert r['status']=='unresolved' and r['recognized_hole_count']==0


def test_bracket_five_round_openings_and_boundary_measurement_agree(results):
    r=results['build123d_bracket']
    assert r['status']=='partial' and r['recognized_hole_count']==5
    assert [h['diameter_mm'] for h in r['holes']]==pytest.approx([3.3,3.3,32,3.3,3.3])
    assert [(h['y_mm'],h['entry_z_mm']) for h in r['holes']]==[(-15.5,14.5),(-15.5,45.5),(0,30),(15.5,14.5),(15.5,45.5)]
    assert all(h['x_mm']==3 and h['depth_mm']==3 and h['axis']==[-1,0,0] for h in r['holes'])
    assert len(r['withheld_cylinders'])==12  # six slots, two half cylinders per slot
    assert len(r['external_cylinder_faces'])==1
    shape=read_step_for_inspection(CORPUS/'sources/build123d_bracket.step').imported.shape
    audit=boundary_crosscheck(shape,r['holes'])
    assert audit['passed'] and audit['matched_rims']==audit['circular_rims']==10


def test_large_preview_limit_does_not_erase_analysis(results):
    r=results['ublox_emmy']
    assert r['scanned_faces']==399 and r['preview'] is None and r['preview_reason']
    assert r['status']=='unresolved'


def test_session_and_csv_keep_partial_rows_separate_from_unknown_total():
    session=HoleInventory()
    session.open_bytes((CORPUS/'sources/build123d_bracket.step').read_bytes(),'bracket.step',session.revision_token)
    rows=list(csv.DictReader(io.StringIO(inventory_csv(session.result).decode('utf-8-sig'))))
    assert len(rows)==6 and rows[0]['recognized_hole_count']=='5'
    assert all(r['hole_count']=='' and r['result_status']=='partial' for r in rows)
    assert all(r['solid_index']=='1' for r in rows[1:])


@pytest.mark.parametrize('name',['boss','counterbore','intersecting','edge_hole','blind_top','blind_bottom'])
def test_local_scanner_does_not_call_partial_cylinders_or_blind_holes_through(name):
    shape=read_step_for_inspection(CONTROLS/(name+'.step')).imported.shape
    result=scan_circular_through_holes(shape)
    assert result['holes']==[] and result['hole_count'] is None


def test_rotated_hole_is_measured_in_source_coordinates():
    result=analyze_step((CONTROLS/'rotated.step').read_bytes(),inspection=True,preview=False)
    assert result['status']=='partial' and len(result['holes'])==1
    assert result['holes'][0]['diameter_mm']==pytest.approx(2)
    assert result['holes'][0]['depth_mm']==pytest.approx(4)
    assert result['hole_count'] is None


@pytest.mark.parametrize('name,count',[('single',1),('mixed',2),('no_holes',0)])
def test_whole_plate_certification_is_retained(name,count):
    result=analyze_step((CONTROLS/(name+'.step')).read_bytes(),inspection=True,preview=False)
    assert result['status']=='complete' and result['hole_count']==count
