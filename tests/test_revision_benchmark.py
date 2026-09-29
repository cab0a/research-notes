"""Fixed-input evaluation and provenance controls, without online downloads."""
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
import shutil

import pytest

from research_notes.revision_benchmark import verified_assets, analyze_pair, audit, evaluate

CORPUS = Path(__file__).resolve().parents[1] / 'fixtures/revision-comparison'
MANIFEST = json.loads((CORPUS / 'manifest.json').read_text(encoding='utf-8'))


@lru_cache
def inputs():
    return verified_assets(CORPUS)


@pytest.mark.parametrize('case', MANIFEST['cases'], ids=lambda c: c['id'])
def test_frozen_revision_case_contract(case):
    _, payloads = inputs()
    # The analyzer receives only the two byte strings and names, not the truth.
    outcome, state = analyze_pair(payloads, {k: case[k] for k in ('old', 'new')})
    result = audit(outcome, state, case['expected'])
    assert result['contract_pass'], (case['id'], outcome, result)
    if case['id'] == 'position':
        assert state['metrics_delta']['absolute_volume'] == pytest.approx(0, abs=1e-8)


def test_tampered_fixture_is_rejected_before_geometry(tmp_path):
    fixtures = tmp_path / 'fixtures'
    shutil.copytree(CORPUS, fixtures / CORPUS.name)
    shutil.copytree(CORPUS.parent / 'public-step-corpus', fixtures / 'public-step-corpus')
    path = fixtures / CORPUS.name / 'sources/diameter-old.step'
    path.write_bytes(path.read_bytes() + b'\n')
    with pytest.raises(ValueError, match='digest mismatch'):
        verified_assets(fixtures / CORPUS.name)


def test_expected_truth_checks_missing_and_spurious_dimensions():
    _, payloads = inputs()
    case = next(c for c in MANIFEST['cases'] if c['id'] == 'diameter')
    outcome, state = analyze_pair(payloads, case)
    altered = deepcopy(state)
    altered['analysis']['dimensions'].pop()
    assert not audit(outcome, altered, case['expected'])['contract_pass']
    altered = deepcopy(state)
    altered['analysis']['dimensions'].append(dict(altered['analysis']['dimensions'][0]))
    assert not audit(outcome, altered, case['expected'])['contract_pass']


def test_repeated_small_run_writes_truthful_report_and_csv(tmp_path):
    fixtures = tmp_path / 'fixtures'
    shutil.copytree(CORPUS, fixtures / CORPUS.name)
    shutil.copytree(CORPUS.parent / 'public-step-corpus', fixtures / 'public-step-corpus')
    manifest = deepcopy(MANIFEST)
    manifest['cases'] = [next(c for c in manifest['cases'] if c['id'] == 'ambiguous')]
    (fixtures / CORPUS.name / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    report = evaluate(fixtures / CORPUS.name, tmp_path / 'results', repeats=2)
    assert report['summary']['contract_passed'] == 1
    assert report['cases'][0]['repeat_results_identical']
    assert len(report['cases'][0]['elapsed_seconds']) == 2
    html = (tmp_path / 'results/reports/ambiguous.html').read_text(encoding='utf-8')
    assert '判定保留あり' in html and '<svg ' in html and 'revision_token' not in html
    assert (tmp_path / 'results/results.csv').is_file()


def test_public_sources_keep_license_and_origin_identity():
    external = [a for a in MANIFEST['assets'].values() if a['origin'] == 'unmodified_external_step']
    assert len(external) == 6
    assert all(a['license_id'] and a['license_paths'] and a['attribution'] and len(a['revision']) == 40 for a in external)
    assert all(a['modifications'] == 'none; local filename only' for a in external)
