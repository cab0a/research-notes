"""Measured controls for complete counts, unknown results, coordinates and CSV."""
import csv
import io
import json
from pathlib import Path

import pytest

from research_notes.cad_api import CadAPIError
from research_notes.hole_inventory import HoleInventory, analyze_step, inventory_csv, inventory_svg
from research_notes.hole_inventory_benchmark import audit
from research_notes.revision_benchmark import verified_assets

CORPUS = Path(__file__).resolve().parents[1]/'fixtures/hole-inventory'
MANIFEST = json.loads((CORPUS/'manifest.json').read_text())


@pytest.fixture(scope='module')
def evaluated():
    manifest,payloads = verified_assets(CORPUS)
    return {case['id']:analyze_step(payloads[case['source']],Path(case['source']).name) for case in manifest['cases']}


@pytest.mark.parametrize('case',MANIFEST['cases'],ids=lambda c:c['id'])
def test_fixed_shape_inventory_matches_independent_truth(evaluated,case):
    result = evaluated[case['id']]
    assert audit(result,case['expected'])['contract_pass']
    rows = list(csv.DictReader(io.StringIO(inventory_csv(result).decode('utf-8-sig'))))
    assert rows[0]['record_type']=='summary'
    assert len(rows)==1+len(case['expected']['holes'])
    if result['status']!='complete':
        assert rows[0]['hole_count']=='' and rows[0]['result_status']!='complete'


def test_zero_holes_is_distinct_from_unknown_and_position_is_not_recentred(evaluated):
    assert evaluated['no_holes']['hole_count']==0
    assert evaluated['boss']['hole_count'] is None
    translated = evaluated['translated']['holes'][0]
    assert (translated['x_mm'],translated['y_mm'],translated['entry_z_mm'])==pytest.approx((36,-15,11))
    bottom = evaluated['blind_bottom']['holes'][0]
    assert bottom['entry_z_mm']==0 and bottom['axis']==[0,0,1]


def test_numbered_figure_and_safe_csv_preserve_measurements(evaluated):
    result = {**evaluated['multiple_diameters'],'file_name':'=RUN().step'}
    rows = list(csv.DictReader(io.StringIO(inventory_csv(result).decode('utf-8-sig'))))
    assert rows[0]['file_name']=="'=RUN().step"
    assert [float(r['diameter_mm']) for r in rows[1:]]==pytest.approx([1.2,2,2.5])
    svg = inventory_svg(result)
    assert all(f'>{name}</text>' in svg for name in ('H1','H2','H3'))
    assert '<script' not in svg and 'http' in svg


def test_stale_csv_and_failed_request_do_not_replace_inventory():
    session = HoleInventory(); old = session.revision_token
    session.action('demo',{'revision_token':old})
    state = session.state()
    with pytest.raises(CadAPIError,match='穴一覧'):
        session.action('csv',{'revision_token':old})
    with pytest.raises(CadAPIError):
        session.open_bytes(b'', 'empty.step', session.revision_token)
    assert session.state()==state
    session.open_bytes(b'not STEP', 'bad.step',session.revision_token)
    assert session.result['status']=='rejected' and session.result['hole_count'] is None
    assert session.result['file_name']=='bad.step'


def test_missing_and_spurious_holes_fail_audit(evaluated):
    case = next(c for c in MANIFEST['cases'] if c['id']=='single')
    assert not audit(evaluated['no_holes'],case['expected'])['contract_pass']
    assert not audit(evaluated['multiple_diameters'],case['expected'])['contract_pass']


def test_http_workflow_downloads_real_csv_and_enforces_origin_and_revision():
    import threading
    from research_notes.cad_web import EditorServer
    from tests.test_cad_web import call
    with EditorServer(0) as server:
        worker = threading.Thread(target=server.serve_forever,daemon=True); worker.start()
        try:
            status, _, page = call(server,'/holes')
            assert status==200 and b'__TOKEN__' not in page and b'/holes.js' in page
            for asset in ('holes.js','holes.css'):
                assert call(server,'/'+asset)[0]==200
            original = server.holes.revision_token
            status,_,response = call(server,'/api/holes/demo',{'revision_token':original})
            assert status==200 and response['state']['result']['hole_count']==3
            assert server.comparison.slots=={'old':None,'new':None}
            status,headers,data = call(server,'/api/holes/csv',{'revision_token':server.holes.revision_token})
            rows = list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))
            assert status==200 and len(rows)==4
            assert headers['Content-Disposition']=='attachment; filename="hole-inventory.csv"'
            assert call(server,'/api/holes/csv',{'revision_token':original})[0]==409
            assert call(server,'/api/holes/state',headers={'Origin':'http://example.com'})[0]==403
            assert call(server,'/api/holes/state',headers={'X-CAD-Token':'wrong'})[0]==403
            status,_,response = call(server,'/api/holes/open',raw=b'not STEP',headers={'X-CAD-Revision':server.holes.revision_token,'X-File-Name':'../bad.step'})
            assert status==200 and response['state']['result']['file_name']=='bad.step'
            assert response['state']['result']['hole_count'] is None
            csv_response = call(server,'/api/holes/csv',{'revision_token':server.holes.revision_token})
            assert b'rejected' in csv_response[2]
        finally:
            server.shutdown(); worker.join(timeout=5)
