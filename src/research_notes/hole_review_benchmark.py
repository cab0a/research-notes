"""Reproduce review explanations and unchanged v1.13 measurements on fixed inputs."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import platform
import statistics
import time

from research_notes.hole_inventory import VERSION, analyze_step, inventory_csv
from research_notes.hole_review import CATALOG, review_csv

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / 'results/hole-numerical-stability'
EXPECTED = {
    'circle_blind': 'opening_pair', 'circle_rectangular_shoulder': 'shoulder_ambiguity',
    'slot_blind': 'opening_pair', 'rectangle': 'slot_boundary',
    'ellipse': 'opening_boundary_unqualified', 'radius_below_gate': 'feature_too_small',
}
EXAMPLES = {'circle_rectangular_shoulder', 'circle_blind', 'ellipse', 'radius_below_gate',
            'build123d_bracket', 'no_holes', 'malformed'}


def fixed_cases(root=ROOT):
    baseline = root / 'results/hole-numerical-stability'
    groups = [('robustness', baseline/'robustness/results.json', root/'fixtures/hole-robustness/sources'),
              ('numerical', baseline/'results.json', root/'fixtures/hole-numerical-stability/sources'),
              ('public', baseline/'public-regression/results.json', root/'fixtures/public-step-corpus/sources')]
    for group, report_path, directory in groups:
        report = json.loads(report_path.read_text(encoding='utf-8'))
        for row in report['records']:
            if row.get('path', 'unified') != 'unified':
                continue
            path = directory / (row['id']+'.step')
            yield {'id': row['id'], 'group': group, 'source': path.read_bytes(), 'file_name': path.name,
                   'source_path': str(path.relative_to(root)), 'baseline_result': row['result'],
                   'baseline_path': str(report_path.relative_to(root)), 'expected_code': EXPECTED.get(row['id'])}
    for name in ('no_holes', 'single'):
        path = root/'fixtures/hole-inventory/sources'/(name+'.step')
        yield {'id': name, 'group': 'certified', 'source': path.read_bytes(), 'file_name': path.name,
               'source_path': str(path.relative_to(root)), 'expected_count': 0 if name == 'no_holes' else 1}
    source = (root/'fixtures/hole-robustness/sources/mixed.step').read_bytes()
    text = source.decode()
    cases = [('malformed', b'invalid', 'input_parse_failed'),
             ('truncated', source[:len(source)//2], 'input_parse_failed'),
             ('missing_unit', text.replace('LENGTH_UNIT', 'UNKNOWN_UNIT').encode(), 'input_units'),
             ('unsupported_unit', text.replace('.MILLI.,.METRE.', '.KILO.,.METRE.').encode(), 'input_units'),
             ('external', text.replace('ENDSEC;\nEND-ISO-10303-21;',
                 "#999999=EXTERNAL_SOURCE('never-read.step');\nENDSEC;\nEND-ISO-10303-21;").encode(), 'external_reference')]
    for name, payload, code in cases:
        yield {'id': name, 'group': 'intake', 'source': payload, 'file_name': name+'.step',
               'source_path': None, 'expected_code': code}


def csv_rows(payload):
    return list(csv.DictReader(io.StringIO(payload.decode('utf-8-sig'))))


def run(output, *, repeats=2, root=ROOT):
    if type(repeats) is not int or not 1 <= repeats <= 10:
        raise ValueError('repeats must be 1..10')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output/'examples').mkdir(exist_ok=True)
    records = []
    for case in fixed_cases(root):
        runs, seconds = [], []
        for _ in range(repeats):
            started = time.perf_counter()
            runs.append(analyze_step(case['source'], case['file_name'], inspection=True, preview=False))
            seconds.append(time.perf_counter()-started)
        result = runs[0]
        items = result['review_items']
        codes = sorted({i['code'] for i in items})
        baseline = case.get('baseline_result')
        unchanged = baseline is None or all(result[k] == baseline[k] for k in ('status', 'hole_count', 'holes'))
        expected = case.get('expected_code')
        checks = {
            'repeat_results_identical': all(r == result for r in runs),
            'prior_measurements_and_count_state_unchanged': unchanged,
            'expected_reason_present': expected is None or expected in codes,
            'actions_and_raw_diagnostics_present': all(i['explanation'] and i['next_action'] and
                (i['raw_reason'] or i['code'] in {'no_qualified_features', 'circular_only_scope'}) for i in items),
            'no_unclassified_known_control': not set(codes) & {'input_unclassified', 'geometry_unclassified'},
            'unknown_counts_not_promoted': result['hole_count'] is None if case['group'] != 'certified' else
                result['status'] == 'complete' and result['hole_count'] == case['expected_count'] and not items,
            'csv_summary_and_observations_match': len(csv_rows(review_csv(result))) == 1+len(items) and
                len(csv_rows(inventory_csv(result))) == 1+len(result['holes']),
            'references_within_input': all(1 <= face <= result['metrics']['face_count']
                for item in items for face in item['face_indices']),
        }
        if case['group'] == 'intake':
            checks['input_rejection_is_unanalysed'] = result['status'] == 'rejected' and codes == [expected]
        records.append({'id': case['id'], 'group': case['group'], 'source_path': case['source_path'],
                        'source_sha256': hashlib.sha256(case['source']).hexdigest(),
                        'baseline_path': case.get('baseline_path'), 'expected_reason_code': expected,
                        'checks': checks, 'passed': all(checks.values()), 'seconds': seconds,
                        'median_seconds': statistics.median(seconds), 'result': {k: result[k] for k in
                        ('status', 'hole_count', 'recognized_hole_count', 'recognized_circular_hole_count',
                         'recognized_slot_count', 'holes', 'review_schema_version', 'review_summary', 'review_items')}})
        if case['id'] in EXAMPLES:
            (output/'examples'/(case['id']+'.review.csv')).write_bytes(review_csv(result))
            (output/'examples'/(case['id']+'.holes.csv')).write_bytes(inventory_csv(result))
    names = ('hole_review_benchmark.py', 'hole_review.py', 'hole_inventory.py', 'public_hole_inventory.py',
             'slot_inventory.py', 'local_material.py', 'public_step.py', 'step_part21.py', 'spatial_workflow.py')
    baseline_paths = {r['baseline_path'] for r in records if r['baseline_path']}
    report = {'version': VERSION, 'passed': all(r['passed'] for r in records), 'inputs': len(records),
              'repeats': repeats, 'catalog_codes': len(CATALOG),
              'summary': {g: {'inputs': sum(r['group'] == g for r in records),
                             'recognized_features': sum(r['result']['recognized_hole_count'] for r in records if r['group'] == g),
                             'review_items': sum(len(r['result']['review_items']) for r in records if r['group'] == g)}
                          for g in ('robustness', 'numerical', 'public', 'certified', 'intake')},
              'runtime': {'python': platform.python_version(), 'platform': platform.platform(),
                          'cadquery_ocp': importlib.metadata.version('cadquery-ocp')},
              'code_sha256': {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in names},
              'baseline_sha256': {path: hashlib.sha256((root/path).read_bytes()).hexdigest() for path in sorted(baseline_paths)},
              'timing_scope': 'STEP intake and recognition plus explanation, without preview; excludes serialization and file writing; first call included.',
              'claim_boundary': 'Explanations describe failed checks, not inferred hole types or a complete census. Fixed development controls and six pinned public inputs; no population accuracy or automatic repair claim.',
              'records': records}
    (output/'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    with (output/'matrix.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        fields = ('id', 'group', 'status', 'hole_count', 'recognized_hole_count', 'count_state',
                  'review_items', 'reason_codes', 'repeat_results_identical', 'measurements_unchanged', 'passed')
        writer = csv.DictWriter(stream, fields, lineterminator='\n')
        writer.writeheader()
        for row in records:
            r = row['result']
            writer.writerow({k: row[k] for k in ('id', 'group', 'passed')} |
                            {k: r[k] for k in ('status', 'hole_count', 'recognized_hole_count')} |
                            {'count_state': r['review_summary']['count_state'], 'review_items': len(r['review_items']),
                             'reason_codes': ' '.join(sorted({i['code'] for i in r['review_items']})),
                             'repeat_results_identical': row['checks']['repeat_results_identical'],
                             'measurements_unchanged': row['checks']['prior_measurements_and_count_state_unchanged']})
    print(json.dumps({k: report[k] for k in ('version', 'passed', 'inputs', 'summary')}, indent=2))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=Path('output/hole-review'))
    parser.add_argument('--repeats', type=int, default=2)
    args = parser.parse_args(argv)
    return 0 if run(args.output_dir, repeats=args.repeats)['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
