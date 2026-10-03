"""Reproduce the v1.13 material-frame fix and retained STEP exchange limits."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import statistics
import subprocess
import time

from research_notes.brep_runtime import maximum_tolerances, step_round_trip
from research_notes.hole_inventory import VERSION, analyze_step, inventory_csv
from research_notes.hole_robustness import local_inventory, match_truth, summarize
from research_notes.hole_robustness_controls import mixed_control, transformed
from research_notes.public_step import read_step_for_inspection

BASELINE = '5182f09b53fa824f119bf8fd51ab855d5824d212'
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURES = ROOT / 'fixtures/hole-numerical-stability'


def controls():
    base = mixed_control()
    rows = []
    for offset in (1e6, 1e7, 1e8):
        for scale, angle in ((1., 0.), (1., .73), (.01, 0.), (.1, .73)):
            name = f'offset_{int(offset):d}_scale_{str(scale).replace(".", "_")}'
            if angle:
                name += '_rotated'
            control = transformed(base, name, scale=scale, angle=angle,
                                  translation=(offset, -offset, offset))
            # Two authored features remain truth even when STEP exchange changes
            # angular spans, tolerances or the opening evidence enough to abstain.
            control.category = ('exchange_limit' if angle or (scale == .01 and offset > 1e6)
                                else 'qualified')
            rows.append(control)
    return rows


def _rows_with_scanners(shape, circle_scanner, slot_scanner):
    circles = circle_scanner(shape)
    slots = slot_scanner(shape)
    rows = [{**h, 'feature_type': 'circular_hole'} for h in circles['holes']]
    rows.extend({**h, 'feature_type': 'straight_slot', 'x_mm': h['entry_center_mm'][0],
                 'y_mm': h['entry_center_mm'][1], 'entry_z_mm': h['entry_center_mm'][2],
                 'axis': h['through_direction']} for h in slots['slots'])
    return {'holes': rows, 'circle_diagnostics': {k: v for k, v in circles.items() if k != 'holes'},
            'slot_diagnostics': {k: v for k, v in slots.items() if k != 'slots'}}


def before_after():
    """Old scanner sources on the same frozen input and current shared runtime."""
    functions, hashes = {}, {}
    for module, function in [('public_hole_inventory', 'scan_circular_through_holes'),
                             ('slot_inventory', 'scan_straight_through_slots')]:
        path = 'src/research_notes/' + module + '.py'
        source = subprocess.run(['git', 'show', BASELINE + ':' + path], cwd=ROOT,
                                check=True, capture_output=True).stdout
        hashes[path] = hashlib.sha256(source).hexdigest()
        namespace = {'__name__': '_baseline_' + module}
        exec(compile(source.decode('utf-8'), path, 'exec'), namespace)
        functions[module] = namespace[function]
    path = ROOT / 'fixtures/hole-robustness/sources/translated_1e6.step'
    expected = transformed(mixed_control(), 'far', translation=(1e6, -1e6, 1e6)).expected
    imported = read_step_for_inspection(path).imported.shape
    native = transformed(mixed_control(), 'far', translation=(1e6, -1e6, 1e6)).shape
    records = []
    for stage, shape in [('constructed', native), ('step_scanners', imported)]:
        old = _rows_with_scanners(shape, functions['public_hole_inventory'], functions['slot_inventory'])
        new = local_inventory(shape)
        old_audit, new_audit = match_truth(old['holes'], expected), match_truth(new['holes'], expected)
        records.append({'path': stage, 'before': old, 'after': new,
                        'before_audit': old_audit, 'after_audit': new_audit,
                        'passed': old_audit['matched_features'] == 0 and new_audit['matched_features'] == 2
                                  and not new_audit['false_positives'] and not new_audit['measurement_errors']})
    return {'baseline_commit': BASELINE, 'baseline_scanner_sha256': hashes,
            'source_path': str(path.relative_to(ROOT)), 'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'comparison_scope': 'Pinned v1.12 scanner sources with unchanged shared geometry helpers in the current runtime; not a recreation of the entire historical environment.',
            'records': records, 'passed': all(r['passed'] for r in records)}


def run(output, *, fixture_dir=DEFAULT_FIXTURES, refresh_fixtures=False, repeats=2):
    if type(repeats) is not int or not 1 <= repeats <= 5:
        raise ValueError('repeats must be an integer between 1 and 5')
    output, fixture_dir = Path(output), Path(fixture_dir)
    output.mkdir(parents=True, exist_ok=True)
    authored = controls()
    if refresh_fixtures:
        (fixture_dir / 'sources').mkdir(parents=True, exist_ok=True)
        manifest = {'version': VERSION, 'provenance': 'Repository-authored translated synthetic controls.',
                    'license': 'Same as research repository; see LICENSING.md.',
                    'truth_basis': 'Construction dimensions and analytic rigid/scale transforms; same OCCT, not independent metrology.',
                    'controls': []}
        for control in authored:
            fixture = step_round_trip(control.shape, control.identifier)
            path = fixture_dir / 'sources' / fixture.file_name
            path.write_bytes(fixture.source_bytes)
            manifest['controls'].append({k: getattr(control, k) for k in ('identifier', 'category', 'description', 'expected')} |
                                        {'source_path': 'sources/' + path.name, 'source_sha256': fixture.source_sha256,
                                         'source_bytes': len(fixture.source_bytes)})
        (fixture_dir / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    manifest = json.loads((fixture_dir / 'manifest.json').read_text())
    assert [c.identifier for c in authored] == [r['identifier'] for r in manifest['controls']]
    records = []
    for control, declared in zip(authored, manifest['controls']):
        assert control.expected == declared['expected'] and control.category == declared['category']
        path = fixture_dir / declared['source_path']
        source = path.read_bytes()
        assert hashlib.sha256(source).hexdigest() == declared['source_sha256']
        imported = read_step_for_inspection(path).imported.shape
        for stage, shape in [('constructed', control.shape), ('step_scanners', imported), ('unified', None)]:
            runs, seconds = [], []
            for _ in range(repeats):
                start = time.perf_counter()
                result = (local_inventory(shape) if shape is not None else
                          analyze_step(source, path.name, inspection=True, preview=False))
                seconds.append(time.perf_counter() - start)
                runs.append(result)
            audit = match_truth(result['holes'], declared['expected'])
            required = stage == 'constructed' or control.category == 'qualified'
            passed = (not audit['false_positives'] and not audit['measurement_errors']
                      and (not required or not audit['missed_truth_indices'])
                      and all(r == runs[0] for r in runs))
            if stage == 'unified':
                passed = passed and result['hole_count'] is None and result['status'] in {'partial', 'unresolved'}
                (output / 'csv').mkdir(exist_ok=True)
                (output / 'csv' / (control.identifier + '.csv')).write_bytes(inventory_csv(result))
            records.append({'id': control.identifier, 'category': control.category, 'path': stage,
                            'source_sha256': declared['source_sha256'], 'required_full_match': required,
                            'maximum_tolerances_mm': maximum_tolerances(shape if shape is not None else imported),
                            'audit': audit, 'repeat_results_identical': all(r == runs[0] for r in runs),
                            'seconds': seconds, 'median_seconds': statistics.median(seconds),
                            'passed': passed, 'result': result})
    comparison = before_after()
    code = [Path(__file__), Path(__file__).with_name('local_material.py'),
            Path(__file__).with_name('public_hole_inventory.py'), Path(__file__).with_name('slot_inventory.py'),
            Path(__file__).with_name('hole_inventory.py'), Path(__file__).with_name('hole_robustness_controls.py'),
            Path(__file__).with_name('hole_robustness.py')]
    report = {'version': VERSION, 'passed': comparison['passed'] and all(r['passed'] for r in records),
              'all_expected_features_recognized': all(not r['audit']['missed_truth_indices'] for r in records),
              'pass_definition': 'Original far-coordinate regression fixed; no false accepted rows or measurement errors; required paths fully match truth. STEP exchange limits retain two-feature truth and reported misses.',
              'controls': len(authored), 'repeats': repeats,
              'summary': {p: summarize(records, p) for p in ('constructed', 'step_scanners', 'unified')},
              'runtime': {'python': platform.python_version(), 'platform': platform.platform(),
                          'cadquery_ocp': importlib.metadata.version('cadquery-ocp')},
              'fixture_manifest_sha256': hashlib.sha256((fixture_dir / 'manifest.json').read_bytes()).hexdigest(),
              'code_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in code},
              'timing_scope': 'Individual scanners, or STEP import and unified recognition without preview; excludes fixture creation and audit/serialization.',
              'records': records}
    (output / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (output / 'before-after.json').write_text(json.dumps(comparison, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    with (output / 'matrix.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        fields = ['id', 'category', 'path', 'required_full_match', 'expected_features', 'matched_features',
                  'false_positives', 'missed_features', 'measurement_errors', 'max_length_error_mm',
                  'max_direction_error', 'passed']
        writer = csv.DictWriter(stream, fields, lineterminator='\n')
        writer.writeheader()
        for r in records:
            a = r['audit']
            writer.writerow({k: r[k] for k in ('id', 'category', 'path', 'required_full_match', 'passed')} |
                            {k: a[k] for k in ('expected_features', 'matched_features', 'measurement_errors',
                                              'max_length_error_mm', 'max_direction_error')} |
                            {'false_positives': len(a['false_positives']), 'missed_features': len(a['missed_truth_indices'])})
    print(json.dumps({k: report[k] for k in ('passed', 'all_expected_features_recognized', 'controls', 'summary')}, indent=2))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=Path('output/hole-numerical-stability'))
    parser.add_argument('--fixture-dir', type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument('--refresh-fixtures', action='store_true', help='Freeze controls at the explicitly selected destination.')
    parser.add_argument('--repeats', type=int, default=2)
    args = parser.parse_args(argv)
    return 0 if run(args.output_dir, fixture_dir=args.fixture_dir,
                    refresh_fixtures=args.refresh_fixtures, repeats=args.repeats)['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
