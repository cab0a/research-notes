"""Repeat the fixed public corpus through the v1.11 circular/slot inventory."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import statistics
import time

from research_notes.hole_inventory import VERSION, analyze_step, inventory_csv, inventory_svg
from research_notes.public_hole_benchmark import boundary_crosscheck as circle_crosscheck
from research_notes.public_step import read_step_for_inspection
from research_notes.public_step_corpus import CORPUS, verify_corpus
from research_notes.slot_benchmark import boundary_crosscheck as slot_crosscheck
from research_notes.slot_inventory import scan_straight_through_slots


def run(output, repeats=3):
    if type(repeats) is not int or not 1 <= repeats <= 10:
        raise ValueError('repeats must be an integer between 1 and 10')
    output = Path(output)
    (output/'csv').mkdir(parents=True, exist_ok=True)
    manifest = verify_corpus()
    records = []
    for sample in manifest['samples']:
        path = CORPUS/sample['asset_path']
        runs, seconds = [], []
        for _ in range(repeats):
            start = time.perf_counter()
            result = analyze_step(path.read_bytes(), path.name, inspection=True)
            seconds.append(time.perf_counter()-start)
            runs.append({k:v for k,v in result.items() if k != 'preview'})
        expected = (5,6) if sample['sample_id'] == 'build123d_bracket' else (0,0)
        passed = (result['status'] == ('partial' if sum(expected) else 'unresolved')
                  and result['hole_count'] is None and result['recognized_hole_count'] == sum(expected)
                  and (result['recognized_circular_hole_count'],result['recognized_slot_count']) == expected
                  and result['scanned_faces'] == sample['baseline']['faces']
                  and all(r == runs[0] for r in runs))
        records.append({'id':sample['sample_id'],'passed':passed,'repeat_results_identical':all(r==runs[0] for r in runs),
                        'seconds':seconds,'median_seconds':statistics.median(seconds),'result':runs[0]})
        (output/'csv'/f"{sample['sample_id']}.csv").write_bytes(inventory_csv(result))
        if sample['sample_id'] == 'build123d_bracket':
            shape = read_step_for_inspection(path).imported.shape
            circle_audit = circle_crosscheck(shape,[h for h in result['holes'] if h['feature_type']=='circular_hole'])
            slot_audit = slot_crosscheck(shape,[h for h in result['holes'] if h['feature_type']=='straight_slot'])
            adapted_slots = [{k:h[k] for k in original} for h,original in zip(result['holes'][5:],scan_straight_through_slots(shape)['slots'])]
            slot_rows_match = adapted_slots == scan_straight_through_slots(shape)['slots']
            (output/'bracket.svg').write_text(inventory_svg(result),encoding='utf-8')
    code_paths = [Path(__file__),Path(__file__).with_name('hole_inventory.py'),Path(__file__).with_name('slot_inventory.py'),
                  Path(__file__).with_name('public_hole_inventory.py'),Path(__file__).with_name('local_material.py'),
                  Path(__file__).parent/'cad_editor/holes.js']
    report = {'version':VERSION,'repeats':repeats,'passed':all(r['passed'] for r in records) and circle_audit['passed'] and slot_audit['passed'] and slot_rows_match,
              'selection':'Same six frozen files (five families), used in development; integration regression, not held-out recognition accuracy.',
              'summary':{'inputs':len(records),'imported':sum(r['result']['status']!='rejected' for r in records),
                         'verified_circular_holes':sum(r['result']['recognized_circular_hole_count'] for r in records),
                         'verified_slots':sum(r['result']['recognized_slot_count'] for r in records),
                         'unknown_whole_counts':sum(r['result']['hole_count'] is None for r in records)},
              'timing_scope':'Input read, import, both recognition paths and optional preview, first run included; excludes CSV/SVG and cross-checks. EMMY has no preview.',
              'runtime':{'python':platform.python_version(),'platform':platform.platform(),'cadquery_ocp':importlib.metadata.version('cadquery-ocp')},
              'source_manifest_sha256':hashlib.sha256((CORPUS/'manifest.json').read_bytes()).hexdigest(),
              'code_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in code_paths},
              'slot_measurements_unchanged_from_standalone':slot_rows_match,
              'circular_boundary_crosscheck':circle_audit,'slot_boundary_crosscheck':slot_audit,'records':records}
    (output/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':report['passed'],**report['summary']},indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=Path('output/unified-hole-inventory'))
    parser.add_argument('--repeats',type=int,default=3)
    args = parser.parse_args()
    return 0 if run(args.output_dir,args.repeats)['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
