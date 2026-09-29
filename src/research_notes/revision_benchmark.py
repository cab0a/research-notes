"""Offline, hash-bound evaluation of fixed STEP revision pairs.

Ground truth is read only after geometry analysis. External self-pairs evaluate
intake coverage; they are never counted as authentic design-change revisions.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
from html import escape
import importlib.metadata as metadata
import json
from pathlib import Path
import platform
import statistics
import time

from research_notes.cad_revision import RevisionComparison
from research_notes.cad_api import CadAPIError
from research_notes.public_step_corpus import verify_corpus
from research_notes.revision_report import render_report, preview_svgs, camera_values


def verified_assets(corpus):
    corpus = Path(corpus).resolve()
    manifest = json.loads((corpus / 'manifest.json').read_text(encoding='utf-8'))
    verify_corpus(corpus.parent / 'public-step-corpus')
    payloads = {}
    for relative, item in manifest['assets'].items():
        path = (corpus / relative).resolve()
        # External fixed assets live beside this corpus; never read arbitrary paths.
        if not path.is_relative_to(corpus.parent):
            raise ValueError('asset path escapes fixtures directory')
        data = path.read_bytes()
        if len(data) != item['bytes'] or hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError('corpus digest mismatch: ' + relative)
        payloads[relative] = data
    return manifest, payloads


def analyze_pair(payloads, case):
    comparison = RevisionComparison()
    slots, errors = {}, {}
    started = time.perf_counter()
    for side in ('old', 'new'):
        try:
            slots[side] = comparison.load(payloads[case[side]], Path(case[side]).name)
        except (ValueError, RuntimeError, CadAPIError) as error:
            errors[side] = str(error)
    if errors:
        return {'disposition': 'rejected', 'errors': errors,
                'seconds': time.perf_counter() - started}, None
    comparison.publish(slots)
    state = comparison.state()
    state.pop('revision_token')
    return {'disposition': state['analysis']['status'], 'errors': {},
            'seconds': time.perf_counter() - started}, state


def audit(outcome, state, expected):
    dimensions = state['analysis']['dimensions'] if state else []
    counts = Counter(r['status'] for r in state['analysis']['regions'] if r['id'].startswith('hole-')) if state else Counter()
    actual = sorted((d['name'], d['old'], d['new'], d['delta']) for d in dimensions)
    wanted = sorted((d['name'], d['old'], d['new'], d['delta']) for d in expected['dimensions'])
    errors = [abs(a-b) for row, truth in zip(actual, wanted) for a, b in zip(row[1:], truth[1:])]
    same_rows = len(actual) == len(wanted) and all(a[0] == b[0] for a, b in zip(actual, wanted))
    dimension_pass = same_rows and max(errors, default=0.) <= 1e-6
    return {'contract_pass': outcome['disposition'] == expected['disposition']
                and dict(counts) == expected['hole_status_counts'] and dimension_pass,
            'hole_status_counts': dict(counts), 'dimension_rows': len(actual),
            'max_dimension_error_mm': max(errors, default=0.) if same_rows and actual else None,
            'expected_dimension_rows': len(wanted), 'dimension_contract_pass': dimension_pass}


def comparison_figure(state, title):
    views = preview_svgs(state, camera_values({}))
    # Use the report's measured projection, not an illustrative replacement.
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1540 540" role="img">',
             f'<title>{escape(title)}</title>', '<rect width="1540" height="540" fill="#f6fafb"/>',
             f'<text x="30" y="36" font-family="sans-serif" font-size="25" fill="#243b47">{escape(title)}</text>']
    for side, x in (('old', 10), ('new', 780)):
        parts.append(f'<text x="{x+20}" y="75" font-family="sans-serif" font-size="19" fill="#243b47">{side.upper()}</text>')
        parts.append(views[side].replace('<svg ', f'<svg x="{x}" y="85" width="750" height="435" ', 1))
    parts.append('</svg>')
    return ''.join(parts)


def evaluate(corpus, output, repeats=3):
    if repeats < 1 or repeats > 10:
        raise ValueError('repeats must be between 1 and 10')
    corpus, output = Path(corpus), Path(output)
    manifest, payloads = verified_assets(corpus)
    if output.resolve() == corpus.resolve() or output.resolve().is_relative_to(corpus.resolve()):
        raise ValueError('results must be outside the input corpus')
    output.mkdir(parents=True, exist_ok=True)
    (output / 'reports').mkdir(exist_ok=True)
    (output / 'figures').mkdir(exist_ok=True)
    rows = []
    for case in manifest['cases']:
        observed, states = [], []
        for _ in range(repeats):
            outcome, state = analyze_pair(payloads, case)
            observed.append(outcome); states.append(state)
        outcome, state = observed[-1], states[-1]
        stable = all((o['disposition'], o['errors'], s) == (outcome['disposition'], outcome['errors'], state)
                     for o, s in zip(observed, states))
        result = audit(outcome, state, case['expected'])
        row = {'id': case['id'], 'label': case['label'], 'kind': case['kind'],
               **result, 'disposition': outcome['disposition'], 'repeat_results_identical': stable,
               'elapsed_seconds': [o['seconds'] for o in observed],
               'median_seconds': statistics.median(o['seconds'] for o in observed),
               'input_sha256': {side: manifest['assets'][case[side]]['sha256'] for side in ('old', 'new')},
               'known_changes': case['known_changes'], 'errors': outcome['errors'],
               'unresolved': state['analysis']['unresolved'] if state else [],
               'face_counts': {s: state[s]['metrics']['face_count'] for s in ('old', 'new')} if state else {},
               'dimensions': state['analysis']['dimensions'] if state else [],
               'volume_delta_mm3': state['metrics_delta']['absolute_volume'] if state else None,
               'report': None}
        if state:
            row['report'] = 'reports/' + case['id'] + '.html'
            (output / row['report']).write_text(render_report(state), encoding='utf-8')
            if case['id'] in ('diameter', 'position', 'addition', 'ambiguous', 'split_plane'):
                titles = {'diameter': 'Hole diameter: 2.0 -> 2.6 mm (+0.6 mm)',
                          'position': 'Hole center: X +1.5 mm, Y +0.5 mm (equal volume)',
                          'addition': 'One retained hole and one added candidate',
                          'ambiguous': 'Ambiguous holes: correspondence withheld',
                          'split_plane': 'Same material, split faces: outside current grammar'}
                (output / 'figures' / (case['id'] + '.svg')).write_text(comparison_figure(state, titles[case['id']]), encoding='utf-8')
        rows.append(row)
        print(case['id'], outcome['disposition'], 'PASS' if result['contract_pass'] and stable else 'FAIL', flush=True)
    report = {'version': '1.7.0', 'manifest_sha256': hashlib.sha256((corpus / 'manifest.json').read_bytes()).hexdigest(),
        'source_sha256': {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                          for name in ('revision_benchmark.py', 'revision_detection.py', 'revision_report.py', 'cad_revision.py', 'step_reconstruction.py')},
        'runtime': {'python': platform.python_version(), 'os': platform.platform(), 'architecture': platform.machine(),
                    'cadquery_ocp': metadata.version('cadquery-ocp')},
        'method': {'repeats': repeats, 'timing': 'both STEP imports, qualification, tessellation and matching; '
                    'excludes fixture creation, file reads, report rendering; first run included; no process isolation',
                   'limits': 'Fixed regression corpus; v1.5 rules unchanged; no general precision/recall claim. '
                    'External self-pairs evaluate intake only. Expected values are authored analytic truth, not CAD history.'},
        'summary': {'cases': len(rows), 'contract_passed': sum(r['contract_pass'] and r['repeat_results_identical'] for r in rows),
                    'authored_dispositions': dict(Counter(r['disposition'] for r in rows if r['kind'] == 'authored_control')),
                    'external_dispositions': dict(Counter(r['disposition'] for r in rows if r['kind'] == 'external_intake_control')),
                    'max_dimension_error_mm': max((r['max_dimension_error_mm'] or 0.) for r in rows),
                    'total_measured_seconds': sum(sum(r['elapsed_seconds']) for r in rows)}, 'cases': rows}
    (output / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    with (output / 'results.csv').open('w', encoding='utf-8', newline='') as stream:
        keys = ['id', 'kind', 'disposition', 'contract_pass', 'repeat_results_identical', 'dimension_rows', 'max_dimension_error_mm', 'median_seconds']
        writer = csv.DictWriter(stream, keys, extrasaction='ignore'); writer.writeheader(); writer.writerows(rows)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus-dir', type=Path, default=Path('fixtures/revision-comparison'))
    parser.add_argument('--output-dir', type=Path, default=Path('output/revision-benchmark'))
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    result = evaluate(args.corpus_dir, args.output_dir, args.repeats)
    print(json.dumps(result['summary'], ensure_ascii=False, indent=2))
    return 0 if result['summary']['contract_passed'] == result['summary']['cases'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
