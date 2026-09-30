"""Offline evaluation of frozen, independently authored hole inventories."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import statistics
import time

from research_notes.hole_inventory import analyze_step, inventory_csv, inventory_svg
from research_notes.revision_benchmark import verified_assets


def audit(result, expected):
    errors = []
    rows_match = len(result['holes']) == len(expected['holes'])
    for actual, truth in zip(result['holes'], expected['holes']):
        rows_match &= actual['kind'] == truth['kind'] and actual['axis'] == truth['axis']
        errors.extend(abs(actual[key]-truth[key]) for key in ('diameter_mm','x_mm','y_mm','entry_z_mm','depth_mm'))
    return {'contract_pass': result['status']==expected['status'] and result['hole_count']==expected['hole_count'] and rows_match and max(errors,default=0.)<=1e-6,
            'dimension_values':len(errors),'max_dimension_error_mm':max(errors) if errors else None}


def run(corpus, output, repeats=3):
    if type(repeats) is not int or not 1<=repeats<=10:
        raise ValueError('repeats must be an integer between 1 and 10')
    manifest,payloads = verified_assets(corpus)
    output = Path(output); output.mkdir(parents=True,exist_ok=True)
    (output/'csv').mkdir(exist_ok=True); (output/'figures').mkdir(exist_ok=True)
    records = []
    for case in manifest['cases']:
        runs, times = [], []
        for _ in range(repeats):
            started = time.perf_counter()
            result = analyze_step(payloads[case['source']],Path(case['source']).name)
            times.append(time.perf_counter()-started)
            runs.append({k:v for k,v in result.items() if k!='preview'})
        assessment = audit(runs[0],case['expected'])
        same = all(r==runs[0] for r in runs)
        records.append({'id':case['id'],'kind':case['kind'],'source':case['source'],
                        'result':runs[0],**assessment,'repeat_results_identical':same,
                        'seconds':times,'median_seconds':statistics.median(times)})
        (output/'csv'/f"{case['id']}.csv").write_bytes(inventory_csv(result))
        if case['id'] in ('no_holes','multiple_diameters','mixed','blind_bottom','boss','counterbore'):
            svg = inventory_svg(result)
            if svg:
                (output/'figures'/f"{case['id']}.svg").write_text(svg,encoding='utf-8')
    complete = [r for r in records if r['result']['status']=='complete']
    summary = {'cases':len(records),'repeats':repeats,
               'expected_handling_passed':sum(r['contract_pass'] and r['repeat_results_identical'] for r in records),
               'authored':dict(Counter(r['result']['status'] for r in records if r['kind']=='authored_control')),
               'external':dict(Counter(r['result']['status'] for r in records if r['kind']=='external_intake_control')),
               'complete_holes':sum(r['result']['hole_count'] for r in complete),
               'max_reported_dimension_error_mm':max((r['max_dimension_error_mm'] or 0.) for r in records),
               'general_accuracy_claim':False}
    source_paths = [Path(__file__),Path(__file__).with_name('hole_inventory.py'),Path(__file__).with_name('step_reconstruction.py'),Path(__file__).with_name('revision_detection.py')]
    report = {'version':'1.8.0','summary':summary,'selection':manifest['selection'],
              'runtime':{'python':platform.python_version(),'platform':platform.platform(),'cadquery_ocp':importlib.metadata.version('cadquery-ocp')},
              'timing_scope':'STEP parsing/import, qualification and preview tessellation; excludes reading fixed input bytes, CSV/SVG output and fixture construction. First run included.',
              'runtime_source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths},
              'manifest_sha256':hashlib.sha256((Path(corpus)/'manifest.json').read_bytes()).hexdigest(),'records':records}
    (output/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with (output/'results.csv').open('w',encoding='utf-8',newline='') as stream:
        fields=['id','kind','status','hole_count','contract_pass','repeat_results_identical','max_dimension_error_mm','median_seconds']
        writer = csv.DictWriter(stream,fields,lineterminator='\n'); writer.writeheader()
        for r in records:
            writer.writerow({k:r[k] for k in fields if k not in ('status','hole_count')}|{'status':r['result']['status'],'hole_count':r['result']['hole_count']})
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return report


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus-dir',type=Path,default=root/'fixtures/hole-inventory')
    parser.add_argument('--output-dir',type=Path,default=Path('output/hole-inventory-benchmark'))
    parser.add_argument('--repeats',type=int,default=3)
    args = parser.parse_args()
    result = run(args.corpus_dir,args.output_dir,args.repeats)
    return 0 if result['summary']['expected_handling_passed']==result['summary']['cases'] else 1


if __name__=='__main__':
    raise SystemExit(main())
