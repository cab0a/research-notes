"""Reproduce authored false-positive, abstention and exception checks (v1.12)."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import io
import json
import math
from pathlib import Path
import platform
import statistics
import time

from research_notes.brep_runtime import maximum_tolerances, step_round_trip, topology_counts
from research_notes.cad_api import CadAPIError
from research_notes.hole_inventory import VERSION, HoleInventory, analyze_step, inventory_csv
from research_notes.hole_robustness_controls import geometry_controls, mixed_control, with_tolerance, compound, box
from research_notes.public_hole_inventory import scan_circular_through_holes
from research_notes.slot_inventory import scan_straight_through_slots

TRUTH_LENGTH_TOL = 1e-5
TRUTH_DIRECTION_TOL = 1e-7


def local_inventory(shape):
    circles=scan_circular_through_holes(shape)
    slots=scan_straight_through_slots(shape)
    rows=[{**h,'feature_type':'circular_hole'} for h in circles['holes']]
    rows.extend({**h,'feature_type':'straight_slot','x_mm':h['entry_center_mm'][0],
                 'y_mm':h['entry_center_mm'][1],'entry_z_mm':h['entry_center_mm'][2],
                 'axis':h['through_direction']} for h in slots['slots'])
    return {'holes':rows,'circle_diagnostics':{k:v for k,v in circles.items() if k!='holes'},
            'slot_diagnostics':{k:v for k,v in slots.items() if k!='slots'}}


def match_truth(rows, expected):
    """One-to-one location/type match; errors and misses remain separate.

    Authored opening ends and dimensions precede recognition. An axis sign or
    choice of opening is not a miss. Each accepted row must match one feature.
    """
    remaining=set(range(len(expected)))
    false_positives=[]
    measurements=[]
    for row in rows:
        entry=[row['x_mm'],row['y_mm'],row['entry_z_mm']]
        matches=[i for i in remaining if expected[i]['feature_type']==row['feature_type']
                 and min(math.dist(entry,p) for p in expected[i]['ends_mm'])<=TRUTH_LENGTH_TOL]
        if len(matches)!=1:
            false_positives.append(row['id'])
            continue
        index=matches[0];remaining.remove(index);truth=expected[index]
        nearest=min(range(2),key=lambda i:math.dist(entry,truth['ends_mm'][i]))
        target_entry=truth['ends_mm'][nearest];target_exit=truth['ends_mm'][1-nearest]
        depth=math.dist(target_entry,target_exit)
        axis=[(b-a)/depth for a,b in zip(target_entry,target_exit)]
        length_errors=[math.dist(entry,target_entry),abs(row['depth_mm']-truth['depth_mm'])]
        fields=['diameter_mm'] if row['feature_type']=='circular_hole' else ['width_mm','length_mm']
        length_errors.extend(abs(row[k]-truth[k]) for k in fields)
        direction_errors=[max(abs(a-b) for a,b in zip(row['axis'],axis))]
        if row['feature_type']=='straight_slot':
            length_errors.append(math.dist(row['exit_center_mm'],target_exit))
            direction_errors.append(min(max(abs(a-sign*b) for a,b in zip(row['longitudinal_direction'],truth['long_direction']))
                                        for sign in (-1,1)))
        measurements.append({'hole_id':row['id'],'truth_index':index,
                             'max_length_error_mm':max(length_errors),'max_direction_error':max(direction_errors),
                             'passed':max(length_errors)<=TRUTH_LENGTH_TOL and max(direction_errors)<=TRUTH_DIRECTION_TOL})
    return {'expected_features':len(expected),'recognized_features':len(rows),'matched_features':len(measurements),
            'false_positives':false_positives,'missed_truth_indices':sorted(remaining),
            'measurement_errors':sum(not m['passed'] for m in measurements),'measurements':measurements,
            'max_length_error_mm':max((m['max_length_error_mm'] for m in measurements),default=None),
            'max_direction_error':max((m['max_direction_error'] for m in measurements),default=None)}


def audit_passed(audit, category):
    # Stress misses are deliberately reported, not hidden by an all-green score.
    return (not audit['false_positives'] and not audit['measurement_errors']
            and (category=='stress' or not audit['missed_truth_indices']))


def tolerance_checks(shape):
    records=[]
    for kind in ('face','edge','vertex'):
        for value in (9e-6,1e-5,1.1e-5):
            body=with_tolerance(shape,kind,value)
            actual=local_inventory(body)
            expected=mixed_control().expected if value<=1e-5 else []
            audit=match_truth(actual['holes'],expected)
            records.append({'kind':kind,'requested_tolerance_mm':value,'stage':'native_mutation_only',
                            'maximum_tolerances_mm':maximum_tolerances(body),'expected_qualified':len(expected),
                            'audit':audit,'passed':audit_passed(audit,'qualified'),'result':actual})
    return records


def exception_checks(source):
    """Exercise source and session boundaries without native crash injection."""
    from OCP.TopAbs import TopAbs_SHELL
    from OCP.TopoDS import TopoDS_Shape, TopoDS_Shell, TopoDS_Solid
    from OCP.BRep import BRep_Builder
    from OCP.TopAbs import TopAbs_FACE
    from research_notes.brep_runtime import iter_shapes
    text=source.decode()
    extra=text.replace('ENDSEC;\nEND-ISO-10303-21;',"#999999=EXTERNAL_SOURCE('not-retrieved.step');\nENDSEC;\nEND-ISO-10303-21;")
    cases=[('empty_request',b'', 'request_error'),
           ('byte_limit',b' '*2_000_001,'request_error'),
           ('malformed',b'invalid','rejected'),
           ('truncated',source[:len(source)//2],'rejected'),
           ('missing_unit',text.replace('LENGTH_UNIT','UNKNOWN_UNIT').encode(),'rejected'),
           ('unsupported_unit',text.replace('.MILLI.,.METRE.','.KILO.,.METRE.').encode(),'rejected'),
           ('external_reference',extra.encode(),'rejected')]
    records=[]
    session=HoleInventory()
    session.open_bytes(source,'mixed.step',session.revision_token)
    for identifier,payload,expected in cases:
        before=session.state()
        try:
            session.open_bytes(payload,identifier+'.step',session.revision_token)
            result=session.result
            row={'id':identifier,'expected':expected,'observed':result['status'],'reason':result['reason'],
                 'whole_count':result['hole_count'],'recognized':result['recognized_hole_count'],
                 'csv_summary_rows':len(list(csv.DictReader(io.StringIO(inventory_csv(result).decode('utf-8-sig')))))}
            row['passed']=(expected=='rejected' and result['status']=='rejected' and result['hole_count'] is None
                           and result['recognized_hole_count']==0 and row['csv_summary_rows']==1)
        except CadAPIError as error:
            row={'id':identifier,'expected':expected,'observed':'request_error','reason':str(error),
                 'previous_state_preserved':session.state()==before,
                 'passed':expected=='request_error' and session.state()==before}
        records.append(row)
    shape=mixed_control().shape
    # Null, empty and shell-only input are lower-level API rejection checks.
    # The 516-face compound is above the explicit face scan limit.
    builder=BRep_Builder();shell=TopoDS_Shell();solid=TopoDS_Solid()
    builder.MakeShell(shell)
    for face in iter_shapes(box(0,0,0,1,1,1),TopAbs_FACE)[:-1]:
        builder.Add(shell,face)
    builder.MakeSolid(solid);builder.Add(solid,shell)
    native_cases=[('null',TopoDS_Shape()),('empty_compound',compound()),('invalid_open_solid',solid),
                  ('shell_only',iter_shapes(shape,TopAbs_SHELL)[0]),
                  ('face_budget_516',compound(*(box(40*i,0,0,1,1,1) for i in range(86))))]
    for identifier,body in native_cases:
        for name,scanner in [('circle',scan_circular_through_holes),('slot',scan_straight_through_slots)]:
            try:
                scanner(body)
                records.append({'id':identifier,'api':name,'expected':'validation_error','observed':'returned','passed':False})
            except ValueError as error:
                records.append({'id':identifier,'api':name,'expected':'validation_error','observed':'validation_error',
                                'reason':str(error),'passed':True})
    return records


def summarize(records, path):
    selected=[r for r in records if r['path']==path]
    audits=[r['audit'] for r in selected]
    return {'executions':len(selected),'expected_features':sum(a['expected_features'] for a in audits),
            'matched_features':sum(a['matched_features'] for a in audits),
            'false_positives':sum(len(a['false_positives']) for a in audits),
            'missed_features':sum(len(a['missed_truth_indices']) for a in audits),
            'measurement_errors':sum(a['measurement_errors'] for a in audits),
            'intended_zero_row_cases':sum(not a['expected_features'] and not a['recognized_features'] for a in audits),
            'max_length_error_mm':max((a['max_length_error_mm'] for a in audits if a['max_length_error_mm'] is not None),default=None),
            'max_direction_error':max((a['max_direction_error'] for a in audits if a['max_direction_error'] is not None),default=None)}


def run(output, *, fixture_dir=Path('fixtures/hole-robustness'), refresh_fixtures=False, repeats=2):
    if type(repeats) is not int or not 1<=repeats<=5:
        raise ValueError('repeats must be an integer between 1 and 5')
    output,fixture_dir=Path(output),Path(fixture_dir)
    output.mkdir(parents=True,exist_ok=True)
    controls=geometry_controls()
    if refresh_fixtures:
        (fixture_dir/'sources').mkdir(parents=True,exist_ok=True)
        manifest={'version':VERSION,'provenance':'Repository-authored synthetic controls; no customer data or external samples.',
                  'license':'Same as research repository; see LICENSING.md.',
                  'truth_basis':'Construction parameters and analytic transformations fixed before recognition. Same OCCT kernel; not independent metrology.',
                  'controls':[]}
        for control in controls:
            fixture=step_round_trip(control.shape,'robustness_'+control.identifier)
            path=fixture_dir/'sources'/f'{control.identifier}.step'
            path.write_bytes(fixture.source_bytes)
            manifest['controls'].append({k:getattr(control,k) for k in ('identifier','category','description','expected')} |
                                        {'source_path':'sources/'+path.name,'source_sha256':fixture.source_sha256,
                                         'source_bytes':len(fixture.source_bytes),'constructed_topology':topology_counts(control.shape)})
        (fixture_dir/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    manifest=json.loads((fixture_dir/'manifest.json').read_text())
    assert [c.identifier for c in controls]==[c['identifier'] for c in manifest['controls']], 'Fixture/control set mismatch.'
    records=[]
    from research_notes.public_step import read_step_for_inspection
    for control,declared in zip(controls,manifest['controls']):
        # Truth in frozen manifest must remain authored, not derived from rows.
        assert json.loads(json.dumps(control.expected))==declared['expected'],control.identifier
        source_path=fixture_dir/declared['source_path']
        source=source_path.read_bytes()
        assert hashlib.sha256(source).hexdigest()==declared['source_sha256'],control.identifier
        imported=read_step_for_inspection(source_path).imported.shape
        for path,shape in [('constructed',control.shape),('step_scanners',imported),('unified',None)]:
            runs=[];seconds=[]
            for _ in range(repeats):
                started=time.perf_counter()
                result=(local_inventory(shape) if shape is not None else analyze_step(source,source_path.name,inspection=True,preview=False))
                seconds.append(time.perf_counter()-started);runs.append(result)
            audit=match_truth(result['holes'],declared['expected'])
            passed=audit_passed(audit,control.category) and all(r==runs[0] for r in runs)
            if path=='unified':
                passed=passed and result['hole_count'] is None and result['status'] in {'partial','unresolved'}
            records.append({'id':control.identifier,'category':control.category,'path':path,
                            'description':control.description,'source_sha256':declared['source_sha256'],
                            'maximum_tolerances_mm':maximum_tolerances(shape if shape is not None else imported),
                            'topology':topology_counts(shape if shape is not None else imported),
                            'audit':audit,'repeat_results_identical':all(r==runs[0] for r in runs),
                            'seconds':seconds,'median_seconds':statistics.median(seconds),'passed':passed,'result':runs[0]})
            if path=='unified':
                (output/'csv').mkdir(exist_ok=True)
                (output/'csv'/f'{control.identifier}.csv').write_bytes(inventory_csv(result))
    tolerance=tolerance_checks(controls[0].shape)
    exceptions=exception_checks((fixture_dir/'sources/mixed.step').read_bytes())
    summaries={p:summarize(records,p) for p in ('constructed','step_scanners','unified')}
    paths=[Path(__file__),Path(__file__).with_name('hole_robustness_controls.py'),Path(__file__).with_name('public_hole_inventory.py'),
           Path(__file__).with_name('slot_inventory.py'),Path(__file__).with_name('hole_inventory.py'),
           Path(__file__).with_name('local_material.py')]
    report={'version':VERSION,'passed':all(r['passed'] for r in records+tolerance+exceptions),
            'pass_definition':'No false accepted features or measurement errors; declared supported controls match truth. Stress misses are retained and reported. Exceptions must preserve request state or emit rejection with unknown count.',
            'all_expected_features_recognized':all(not r['audit']['missed_truth_indices'] for r in records),
            'selection':f'{len(controls)} authored controls, including variants of common base shapes; development regression, not a population accuracy estimate.',
            'controls':len(controls),'repeats':repeats,'summary':summaries,
            'tolerance_cases':len(tolerance),'exceptions':len(exceptions),
            'truth_length_threshold_mm':TRUTH_LENGTH_TOL,'truth_direction_threshold':TRUTH_DIRECTION_TOL,
            'runtime':{'python':platform.python_version(),'platform':platform.platform(),'cadquery_ocp':importlib.metadata.version('cadquery-ocp')},
            'fixture_manifest_sha256':hashlib.sha256((fixture_dir/'manifest.json').read_bytes()).hexdigest(),
            'code_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
            'timing_scope':'Each path: scanner calls, or source import plus unified recognition without preview. Excludes control construction, fixture import for scanner paths, comparison, serialization and output; first call included.',
            'known_limit':'Per-solid recognition still accepts local holes when a separate solid blocks the assembly opening; no assembly clearance certificate.',
            'records':records,'tolerance_checks':tolerance,'exception_checks':exceptions}
    (output/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with (output/'matrix.csv').open('w',newline='',encoding='utf-8-sig') as stream:
        fields=['id','category','path','expected_features','recognized_features','matched_features','false_positives','missed_features','measurement_errors','max_length_error_mm','max_direction_error','passed']
        writer=csv.DictWriter(stream,fields,lineterminator='\n');writer.writeheader()
        for record in records:
            a=record['audit']
            writer.writerow({k:record[k] for k in ('id','category','path','passed')} |
                            {k:a[k] for k in ('expected_features','recognized_features','matched_features','measurement_errors','max_length_error_mm','max_direction_error')} |
                            {'false_positives':len(a['false_positives']),'missed_features':len(a['missed_truth_indices'])})
    print(json.dumps({k:report[k] for k in ('passed','all_expected_features_recognized','controls','summary','tolerance_cases','exceptions')},indent=2))
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=Path('output/hole-robustness'))
    parser.add_argument('--fixture-dir',type=Path,default=Path('fixtures/hole-robustness'))
    parser.add_argument('--refresh-fixtures',action='store_true',help='Regenerate authored fixture files at the explicit destination.')
    parser.add_argument('--repeats',type=int,default=2)
    args=parser.parse_args(argv)
    return 0 if run(args.output_dir,fixture_dir=args.fixture_dir,refresh_fixtures=args.refresh_fixtures,repeats=args.repeats)['passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
