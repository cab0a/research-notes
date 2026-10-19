"""Validate and summarize the bounded 2026-10-19 kernel pilot (stdlib only)."""
from __future__ import annotations

from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'results/cad-kernel-choice'
GROUPS = {'primitives': 18, 'intake': 192, 'roundtrip': 36, 'accuracy': 15, 'metadata': 2}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name):
    return json.loads((DEST / (name + '.json')).read_text(),
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def main():
    reports = {name: load(name) for name in GROUPS}
    archives = json.loads((DEST / 'roundtrip-archive.json').read_text())['files']
    archived_paths = {r['original_path']: ROOT/r['path'] for r in archives}
    for row in archives:
        assert sha(ROOT/row['path']) == row['sha256'], row['path']
    probe_sha = sha(ROOT / 'experiments/run_cad_kernel_probe.py')
    states = {}
    for name, report in reports.items():
        assert report['observations'] == len(report['records']) == GROUPS[name], name
        assert report['probe_sha256'] == probe_sha, name
        states[name] = dict(Counter(r['result']['status'] for r in report['records']))
        for row in report['records']:
            if row.get('source_path'):
                source = ROOT / row['source_path']
                if not source.exists():
                    source = archived_paths[row['source_path']]
                assert sha(source) == row['source_sha256'], row['key']
            assert (row['exit_code'] == 0) == (row['result']['status'] in {'ok', 'error'}), row['key']
    assert states == {'primitives': {'ok': 18}, 'intake': {'ok': 192}, 'roundtrip': {'ok': 36},
                      'accuracy': {'ok': 14, 'process_failed': 1}, 'metadata': {'ok': 2}}, states
    failures = [r for r in reports['accuracy']['records'] if r['result']['status'] != 'ok']
    assert failures[0]['key'] == 'accuracy-build123d_screw-from-smlibpy' and failures[0]['exit_code'] == -24

    by_case = {}
    for row in reports['intake']['records']:
        by_case.setdefault((row['group'], row['id']), {})[(row['backend'], row['heal'])] = row
    assert len(by_case) == 64
    matrix = []
    for (group, identifier), routes in by_case.items():
        base = routes[('occt', False)]['result']['metrics']
        for (backend, heal), row in routes.items():
            metrics = row['result']['metrics']
            dv = abs(metrics['volume'] - base['volume']) / abs(base['volume'])
            db = max(abs(a-b) for key in ('bounds_min', 'bounds_max') for a,b in zip(metrics[key], base[key]))
            matrix.append({'group': group, 'id': identifier, 'backend': backend, 'heal': heal,
                           'source_sha256': row['source_sha256'], 'faces': metrics['faces'],
                           'valid_by_backend': metrics['valid'], 'volume': metrics['volume'],
                           'volume_relative_difference_from_occt_default': dv,
                           'bounds_max_difference_mm_from_occt': db})
    with (DEST / 'intake-matrix.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(matrix[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(matrix)
    differences = []
    for backend, heal in (('smlibpy', False), ('smlibpy', True)):
        rows = [r for r in matrix if r['backend'] == backend and r['heal'] == heal]
        differences.append({'backend': backend, 'heal': heal, 'inputs': len(rows),
                            'volume_difference_gt_1e_minus_6': sum(r['volume_relative_difference_from_occt_default'] > 1e-6 for r in rows),
                            'bounds_difference_gt_1e_minus_4_mm': sum(r['bounds_max_difference_mm_from_occt'] > 1e-4 for r in rows)})
    primitive_errors = []
    for backend in ('occt', 'usd-brep', 'smlibpy'):
        records = [r for r in reports['primitives']['records'] if r['backend'] == backend]
        for index in range(len(records[0]['result']['measurements'])):
            measurements = [r['result']['measurements'][index] for r in records]
            primitive_errors.append({'backend': backend, 'accuracy': measurements[0]['accuracy'],
                                     'maximum_volume_relative_error': max(m['relative_errors']['volume'] for m in measurements),
                                     'maximum_area_relative_error': max(m['relative_errors']['area'] for m in measurements)})
    accurate = []
    for row in reports['accuracy']['records']:
        result = row['result']
        if result['status'] != 'ok':
            continue
        best = next(x for x in result['integrations'] if x['method'] == 'gauss_kronrod_spans' and x['epsilon'] == 1e-9)
        accurate.append({'key': row['key'], 'volume_default': result['metrics']['volume'],
                         'volume_gk_spans_1e_minus_9': best['volume']})
    metadata = []
    for row in reports['metadata']['records']:
        result = row['result']
        metadata.append({'backend': row['backend'], 'expected_name': row['expected_name'],
                         'input_names': result['input']['names'], 'output_names': result['output']['names'],
                         'name_preserved': result['output']['names'] == [row['expected_name']],
                         'note': 'Color channels are recorded but not compared: color-space conventions differ.'})
    summary = {'date': '2026-10-19', 'probe_sha256': probe_sha, 'total_task_observations': sum(GROUPS.values()),
               'states': states, 'input_groups': dict(Counter(group for group, _ in by_case)),
               'intake_diagnostic_differences': differences, 'primitive_maximum_relative_errors': primitive_errors,
               'occt_integration_comparison': accurate, 'unicode_metadata': metadata,
               'failed_observations': [{'key': r['key'], 'exit_code': r['exit_code']} for r in failures],
               'claim_boundaries': ['Read/import observations are not hole recognition or production admission tests.',
                                    'OCCT default mass properties are a comparison route, not ground truth.',
                                    'Difference thresholds only select diagnostics, not correctness acceptance.',
                                    'No universal winner or speed comparison is established.',
                                    'SolidCraft, SolidCore and ClassCAD were source-reviewed, not executed.']}
    (DEST / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, allow_nan=False, indent=2) + '\n')
    print(json.dumps({'states': states, 'input_groups': summary['input_groups'],
                      'validated_observations': summary['total_task_observations'], 'differences': differences}, indent=2))


if __name__ == '__main__':
    main()
