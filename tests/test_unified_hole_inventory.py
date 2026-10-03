"""v1.11 integration: one snapshot/row schema across API, CLI, HTTP and CSV."""
import csv
import io
import json
from pathlib import Path
import threading

import pytest

from research_notes.cad_api import CadAPIError
from research_notes.hole_inventory import HoleInventory, analyze_step, inventory_csv, inventory_svg, main
from research_notes.public_hole_inventory import scan_circular_through_holes
from research_notes.public_step import read_step_for_inspection
from research_notes.slot_benchmark import BRACKET, control_shapes
from research_notes.slot_inventory import scan_straight_through_slots
from research_notes.step_writer_modes import prepare_step_write


def csv_rows(result):
    return list(csv.DictReader(io.StringIO(inventory_csv(result).decode('utf-8-sig'))))


@pytest.fixture(scope='module')
def bracket_result():
    return analyze_step(BRACKET.read_bytes(), BRACKET.name, inspection=True)


def test_unified_rows_match_each_original_recognizer_and_face_evidence(bracket_result):
    r = bracket_result
    shape = read_step_for_inspection(BRACKET).imported.shape
    circles = scan_circular_through_holes(shape)['holes']
    slots = scan_straight_through_slots(shape)['slots']
    assert r['status'] == 'partial' and r['hole_count'] is None
    assert r['recognized_hole_count'] == 11
    assert r['recognized_circular_hole_count'] == 5 and r['recognized_slot_count'] == 6
    assert len({h['id'] for h in r['holes']}) == 11
    assert r['withheld_cylinders'] == []
    assert r['slot_scan']['recognized_slot_count'] == 6
    assert r['slot_scan']['withheld_candidates'] == []
    for unified, original in zip(r['holes'][:5], circles):
        assert all(unified[k] == v for k,v in original.items())
        assert unified['feature_type'] == 'circular_hole'
        assert unified['width_mm'] is unified['length_mm'] is unified['longitudinal_direction'] is None
    for unified, original in zip(r['holes'][5:], slots):
        assert all(unified[k] == v for k,v in original.items())
        assert unified['feature_type'] == 'straight_slot' and unified['diameter_mm'] is None
        assert unified['faces'] == original['wall_faces']
        assert [unified['x_mm'],unified['y_mm'],unified['entry_z_mm']] == original['entry_center_mm']
        assert unified['axis'] == original['through_direction']
    visible_faces = {f['index'] for f in r['preview']['faces']}
    assert all(set(h['faces']) <= visible_faces for h in r['holes'])
    svg = inventory_svg(r)
    assert all('>'+h['id']+'</text>' in svg for h in r['holes'])


def test_csv_has_11_typed_rows_and_preserves_inapplicable_and_unknown_blanks(bracket_result):
    rows = csv_rows(bracket_result)
    summary, *holes = rows
    assert len(rows) == 12 and summary['record_type'] == 'summary'
    assert summary['recognized_hole_count'] == '11'
    assert summary['recognized_circular_hole_count'] == '5' and summary['recognized_slot_count'] == '6'
    assert all(row['hole_count'] == '' and row['inventory_version'] == '1.13.0' for row in rows)
    for row in holes[:5]:
        assert row['feature_type'] == 'circular_hole' and row['diameter_mm']
        assert all(row[k] == '' for k in ('width_mm','length_mm','long_axis_x','long_axis_y','long_axis_z'))
    for row in holes[5:]:
        assert row['feature_type'] == 'straight_slot' and row['diameter_mm'] == ''
        assert [float(row[k]) for k in ('width_mm','length_mm','depth_mm')] == [4.5,7.5,3]
        assert row['axis_z'] == '-1.0'
        assert row['long_axis_z'] == '0.0'
    escaped = csv_rows({**bracket_result, 'file_name':'=IMPORT().step'})
    assert all(row['file_name'].startswith("'=") for row in escaped)


def test_circular_only_option_retains_earlier_measurement_scope():
    result = analyze_step(BRACKET.read_bytes(), inspection=True, preview=False, include_slots=False)
    assert result['feature_scope'] == 'circular_only'
    assert len(result['holes']) == result['recognized_circular_hole_count'] == 5
    assert result['recognized_slot_count'] == 0 and 'slot_scan' not in result
    assert len(result['withheld_cylinders']) == 12


@pytest.mark.parametrize('name,count', [('through',1), ('blind',0), ('stepped_capsule',0), ('stepped_rectangle',0), ('open_notch',0)])
def test_slot_only_and_negative_models_do_not_depend_on_round_holes(name,count):
    source,_ = prepare_step_write(source=None,mode='reconstruct',shape=control_shapes()[name])
    result = analyze_step(source,name+'.step',inspection=True,preview=False)
    assert result['recognized_slot_count'] == count
    assert result['recognized_circular_hole_count'] == 0
    assert result['recognized_hole_count'] == count and result['hole_count'] is None
    assert result['status'] == ('partial' if count else 'unresolved')


def test_slot_failure_preserves_already_verified_circle_rows(monkeypatch):
    def fail(shape):
        raise RuntimeError('injected slot failure')
    monkeypatch.setattr('research_notes.slot_inventory.scan_straight_through_slots',fail)
    r = analyze_step(BRACKET.read_bytes(),inspection=True,preview=False)
    assert r['status'] == 'partial' and r['recognized_hole_count'] == 5
    assert r['recognized_slot_count'] == 0 and r['hole_count'] is None
    assert 'injected slot failure' in r['slot_scan']['reason']


def test_preview_failure_keeps_both_kinds_and_csv(monkeypatch):
    def fail(shape):
        raise ValueError('injected preview failure')
    monkeypatch.setattr('research_notes.diagnostic_workspace.shape_snapshot', fail)
    r = analyze_step(BRACKET.read_bytes(), inspection=True)
    assert r['preview'] is None and 'preview_reason' in r
    assert r['recognized_hole_count'] == 11 and len(csv_rows(r)) == 12


def test_cli_matches_api_and_preserves_partial_exit_contract(tmp_path,bracket_result):
    assert main([str(BRACKET),'--public','--output-dir',str(tmp_path)]) == 2
    assert json.loads((tmp_path/'inventory.json').read_text()) == json.loads(json.dumps(bracket_result))
    assert (tmp_path/'holes.csv').read_bytes() == inventory_csv(bracket_result)
    assert 'S6</text>' in (tmp_path/'holes.svg').read_text()
    assert main([str(BRACKET),'--public','--circular-only','--output-dir',str(tmp_path/'circles')]) == 2
    circles = json.loads((tmp_path/'circles/inventory.json').read_text())
    assert circles['recognized_hole_count'] == 5 and circles['recognized_slot_count'] == 0


def test_replacing_unified_input_clears_slots_and_guards_stale_download():
    session = HoleInventory()
    session.open_bytes(BRACKET.read_bytes(),BRACKET.name,session.revision_token)
    before, token = session.state(), session.revision_token
    with pytest.raises(CadAPIError):
        session.open_bytes(b'', 'empty.step',token)
    assert session.state() == before
    session.action('demo',{'revision_token':token})
    assert session.result['hole_count'] == 3 and session.result['recognized_slot_count'] == 0
    assert [h['id'] for h in session.result['holes']] == ['H1','H2','H3']
    with pytest.raises(CadAPIError):
        session.action('csv',{'revision_token':token})
    session.open_bytes(b'invalid','bad.step',session.revision_token)
    assert session.result['status'] == 'rejected'
    assert session.result['recognized_hole_count'] == session.result['recognized_slot_count'] == 0
    assert session.result['hole_count'] is None and len(csv_rows(session.result)) == 1


def test_http_upload_and_download_match_unified_api(bracket_result):
    from research_notes.cad_web import EditorServer
    from tests.test_cad_web import call
    with EditorServer(0) as server:
        worker = threading.Thread(target=server.serve_forever,daemon=True)
        worker.start()
        try:
            status,_,response = call(server,'/api/holes/open',raw=BRACKET.read_bytes(),headers={
                'X-CAD-Revision':server.holes.revision_token,'X-File-Name':BRACKET.name})
            assert status == 200 and response['state']['result'] == json.loads(json.dumps(bracket_result))
            status,_,data = call(server,'/api/holes/csv',{'revision_token':server.holes.revision_token})
            assert status == 200 and data == inventory_csv(bracket_result)
            assert server.comparison.slots == {'old':None,'new':None}
        finally:
            server.shutdown()
            worker.join(timeout=5)
