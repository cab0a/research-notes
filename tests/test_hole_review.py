"""Review explanations preserve evidence, count semantics and download guards."""
import copy
import csv
import io
import json
from pathlib import Path
import threading

import pytest

from research_notes.cad_api import CadAPIError
from research_notes.hole_inventory import HoleInventory, analyze_step, inventory_csv, main
from research_notes.hole_review import CATALOG, attach_review, error_code, review_csv
from research_notes.hole_robustness_controls import geometry_controls, with_tolerance
from research_notes.public_hole_inventory import scan_circular_through_holes
from research_notes.slot_inventory import scan_straight_through_slots
from research_notes.local_material import LocalMaterialClassifier

ROOT = Path(__file__).resolve().parents[1]
CONTROLS = ROOT / 'fixtures/hole-robustness/sources'
BRACKET = ROOT / 'fixtures/public-step-corpus/sources/build123d_bracket.step'
DECLARED = json.loads((CONTROLS.parent / 'manifest.json').read_text())['controls']


def rows(payload):
    return list(csv.DictReader(io.StringIO(payload.decode('utf-8-sig'))))


def codes(result):
    return {item['code'] for item in result['review_items']}


@pytest.fixture(scope='module')
def results():
    return {c['identifier']: analyze_step((CONTROLS / (c['identifier']+'.step')).read_bytes(),
                                         c['identifier']+'.step', inspection=True, preview=False)
            for c in DECLARED}


@pytest.mark.parametrize('identifier', [c['identifier'] for c in DECLARED])
def test_all_frozen_controls_have_explanations_without_promoting_counts(results, identifier):
    r = results[identifier]
    summary, items = r['review_summary'], r['review_items']
    assert r['review_schema_version'] == '1.0.0'
    assert r['hole_count'] is None and summary['count_state'] == 'unknown'
    assert summary['manual_review_required'] and 'whole_count_unknown' in codes(r)
    assert summary['item_count'] == len(items) == sum(g['item_count'] for g in summary['groups'])
    assert len({item['id'] for item in items}) == len(items)
    assert all(item['code'] in CATALOG and item['explanation'] and item['next_action'] for item in items)
    assert not any(item['code'] == 'geometry_unclassified' for item in items), items
    assert summary['candidate_observation_count'] == len(r['withheld_cylinders']) + len(r['slot_scan']['withheld_candidates'])
    if not r['holes']:
        assert 'no_qualified_features' in codes(r)
        assert '穴がないという判定ではありません' in summary['headline']
    review = rows(review_csv(r))
    assert len(review) == 1 + len(items) and review[0]['record_type'] == 'summary'
    assert all(row['hole_count'] == '' for row in review)
    assert all(row['record_type'] == 'review' for row in review[1:])
    assert len(rows(inventory_csv(r))) == 1 + len(r['holes'])
    for item in items:
        assert all(1 <= i <= r['metrics']['face_count'] for i in item['face_indices'])


@pytest.mark.parametrize('identifier,code,category', [
    ('circle_blind', 'opening_pair', 'scope'),
    ('circle_rectangular_shoulder', 'shoulder_ambiguity', 'scope'),
    ('slot_blind', 'opening_pair', 'scope'),
    ('rectangle', 'slot_boundary', 'scope'),
    ('ellipse', 'opening_boundary_unqualified', 'scope'),
    ('radius_below_gate', 'feature_too_small', 'precision'),
])
def test_actual_geometry_explains_failed_check_without_claiming_feature_identity(results, identifier, code, category):
    items = [item for item in results[identifier]['review_items'] if item['code'] == code]
    assert items and all(item['category'] == category for item in items)
    assert all(item['raw_reason'] and item['face_indices'] for item in items)
    if code == 'opening_pair':
        assert all('断定した結果ではありません' in item['explanation'] for item in items)


@pytest.mark.parametrize('count,filename', [(0, 'no_holes.step'), (1, 'single.step')])
def test_certified_plate_count_remains_separate_from_unconfirmed_zero(count, filename):
    path = ROOT / 'fixtures/hole-inventory/sources' / filename
    r = analyze_step(path.read_bytes(), filename, inspection=True, preview=False)
    assert r['status'] == 'complete' and r['hole_count'] == count
    assert r['review_summary']['count_state'] == ('certified_zero' if count == 0 else 'certified_count')
    assert r['review_items'] == [] and not r['review_summary']['manual_review_required']
    assert rows(review_csv(r))[0]['hole_count'] == str(count)


def test_bracket_has_only_whole_count_review_and_no_false_pending_slot_walls():
    r = analyze_step(BRACKET.read_bytes(), BRACKET.name, inspection=True, preview=False)
    assert r['recognized_hole_count'] == 11 and r['hole_count'] is None
    assert codes(r) == {'whole_count_unknown'}
    assert r['review_summary']['candidate_observation_count'] == 0


def test_review_artifacts_reproduce_from_frozen_controls(results):
    import hashlib
    from research_notes.hole_review_benchmark import fixed_cases
    directory = ROOT / 'results/hole-review'
    report = json.loads((directory/'results.json').read_text(encoding='utf-8'))
    assert report['passed'] and report['inputs'] == 69 and report['repeats'] == 2
    assert len(list(fixed_cases())) == 69
    records = {row['id']: row for row in report['records'] if row['group'] == 'robustness'}
    assert set(records) == set(results)
    for identifier, result in results.items():
        row = records[identifier]
        assert row['passed'] and all(row['checks'].values())
        assert all(value == result[key] for key, value in row['result'].items())
        assert row['source_sha256'] == hashlib.sha256((CONTROLS/(identifier+'.step')).read_bytes()).hexdigest()
    for relative, digest in report['baseline_sha256'].items():
        assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest() == digest
    for path in (directory/'examples').glob('*.review.csv'):
        identifier = path.name.removesuffix('.review.csv')
        if identifier in results:
            assert path.read_bytes() == review_csv(results[identifier])


@pytest.mark.parametrize('variant,expected', [('syntax', 'input_parse_failed'), ('truncated', 'input_parse_failed'),
    ('missing_unit', 'input_units'), ('unsupported_unit', 'input_units'), ('external', 'external_reference')])
def test_input_rejection_is_explained_as_unanalysed_instead_of_no_holes(variant, expected):
    source = (CONTROLS / 'mixed.step').read_bytes()
    text = source.decode()
    payload = {'syntax': b'invalid', 'truncated': source[:len(source)//2],
        'missing_unit': text.replace('LENGTH_UNIT', 'UNKNOWN_UNIT').encode(),
        'unsupported_unit': text.replace('.MILLI.,.METRE.', '.KILO.,.METRE.').encode(),
        'external': text.replace('ENDSEC;\nEND-ISO-10303-21;', "#999999=EXTERNAL_SOURCE('never-read.step');\nENDSEC;\nEND-ISO-10303-21;").encode()}[variant]
    r = analyze_step(payload, variant+'.step', inspection=True)
    assert r['status'] == 'rejected' and r['hole_count'] is None and r['holes'] == []
    assert codes(r) == {expected} and r['review_items'][0]['category'] == 'input'
    assert '未判定' in r['review_summary']['headline']
    assert r['review_items'][0]['raw_reason'] == r['reason']
    assert len(rows(inventory_csv(r))) == 1 and len(rows(review_csv(r))) == 2


def test_tolerance_and_coordinate_precision_have_specific_codes():
    shape = geometry_controls()[0].shape
    circles = scan_circular_through_holes(with_tolerance(shape, 'vertex', 1.1e-5))
    slots = scan_straight_through_slots(with_tolerance(shape, 'face', 1.1e-5))
    assert any(row['reason_code'] == 'tolerance_exceeded' for row in circles['withheld_cylinders'])
    assert any(row['reason_code'] == 'tolerance_exceeded' for row in slots['withheld_candidates'])
    classifier = LocalMaterialClassifier(shape, 1e-5)
    with pytest.raises(ValueError) as error:
        classifier.state([1e10, 0, 0])
    assert error_code(error.value) == 'coordinate_resolution'


def test_actual_parser_budget_is_not_reported_as_broken_syntax():
    from research_notes.step_part21 import STEPParseLimits, Part21ParseError, parse_part21_document
    source = (CONTROLS / 'mixed.step').read_bytes()
    with pytest.raises(Part21ParseError) as error:
        parse_part21_document(source, limits=STEPParseLimits(max_tokens=5))
    assert error.value.reason_code == 'token_count_limit'
    assert error_code(error.value, intake=True) == 'input_limit'
    assert error_code(ValueError('STEP inspection preflight: '+error.value.reason_code), intake=True) == 'input_limit'


def test_native_failure_fallback_keeps_measurements_and_does_not_guess_from_words(monkeypatch):
    def fail(shape):
        raise RuntimeError('blind hole? custom failure <script>unknown</script>')
    monkeypatch.setattr('research_notes.slot_inventory.scan_straight_through_slots', fail)
    r = analyze_step(BRACKET.read_bytes(), inspection=True, preview=False)
    assert r['recognized_circular_hole_count'] == 5 and r['recognized_slot_count'] == 0
    item = next(item for item in r['review_items'] if item['scope'] == 'slot_scan')
    assert item['code'] == 'processing_failed' and item['raw_reason'].startswith('blind hole?')
    assert error_code(ValueError('blind hole? unfamiliar condition')) == 'geometry_unclassified'
    assert error_code(ValueError('new unsupported import condition'), intake=True) == 'input_unclassified'


def test_preview_failure_is_notice_and_cannot_revoke_certified_count(monkeypatch):
    def fail(shape):
        raise RuntimeError('injected preview error')
    monkeypatch.setattr('research_notes.diagnostic_workspace.shape_snapshot', fail)
    r = analyze_step((ROOT/'fixtures/hole-inventory/sources/single.step').read_bytes(), inspection=True)
    assert r['hole_count'] == 1 and r['status'] == 'complete'
    assert codes(r) == {'preview_unavailable'}
    assert r['review_items'][0]['severity'] == 'notice'
    assert not r['review_summary']['manual_review_required']


def test_circular_only_setting_and_formula_escaping_are_explicit():
    r = analyze_step(BRACKET.read_bytes(), '=RUN().step', inspection=True, preview=False, include_slots=False)
    assert 'circular_only_scope' in codes(r) and r['recognized_hole_count'] == 5
    r = copy.deepcopy(r)
    r['review_items'][0]['raw_reason'] = '\t=RUN()'
    csv_rows = rows(review_csv(r))
    assert all(row['file_name'] == "'=RUN().step" for row in csv_rows)
    assert csv_rows[1]['raw_reason'] == "'\t=RUN()"


def test_cli_and_python_review_files_match_and_keep_partial_exit(tmp_path, results):
    path = CONTROLS/'circle_rectangular_shoulder.step'
    assert main([str(path), '--public', '--output-dir', str(tmp_path)]) == 2
    actual = json.loads((tmp_path/'inventory.json').read_text())
    expected = analyze_step(path.read_bytes(), path.name, inspection=True)
    assert actual == json.loads(json.dumps(expected))
    assert (tmp_path/'review.csv').read_bytes() == review_csv(expected)
    assert (tmp_path/'holes.csv').read_bytes() == inventory_csv(expected)


def test_review_download_guards_empty_inputs_and_replacement():
    session = HoleInventory()
    with pytest.raises(CadAPIError):
        session.action('review-csv', {'revision_token': session.revision_token})
    session.open_bytes((CONTROLS/'circle_blind.step').read_bytes(), 'blind.step', session.revision_token)
    token, before = session.revision_token, session.state()
    for payload in (b'', b' '*2_000_001):
        with pytest.raises(CadAPIError):
            session.open_bytes(payload, 'bad.step', token)
        assert session.state() == before
    session.action('demo', {'revision_token': token})
    assert session.result['review_items'] == []
    with pytest.raises(CadAPIError):
        session.action('review-csv', {'revision_token': token})


def test_http_review_download_matches_snapshot_and_enforces_revision_and_token():
    from research_notes.cad_web import EditorServer
    from tests.test_cad_web import call
    with EditorServer(0) as server:
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            original = server.holes.revision_token
            status, _, response = call(server, '/api/holes/open', raw=(CONTROLS/'circle_blind.step').read_bytes(),
                                      headers={'X-CAD-Revision': original, 'X-File-Name': 'blind.step'})
            assert status == 200
            result = response['state']['result']
            status, headers, data = call(server, '/api/holes/review-csv', {'revision_token': server.holes.revision_token})
            assert status == 200 and data == review_csv(result)
            assert headers['Content-Disposition'] == 'attachment; filename="hole-review.csv"'
            assert call(server, '/api/holes/review-csv', {'revision_token': original})[0] == 409
            assert call(server, '/api/holes/review-csv', {'revision_token': server.holes.revision_token},
                        headers={'X-CAD-Token': 'wrong'})[0] == 403
        finally:
            server.shutdown()
            worker.join(timeout=5)
