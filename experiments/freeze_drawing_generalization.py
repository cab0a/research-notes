"""Freeze CAD outputs with explicit cohort, provenance and evaluation-only truth."""
from pathlib import Path
import hashlib,json,shutil,argparse
from research_notes.drawing_to_cad import json_bytes
from research_notes.svg_drawing_graphics import normalize
from research_notes.drawing_families import interpret as baseline
ROOT=Path(__file__).resolve().parents[1];FIX=ROOT/'fixtures/drawing-generalization'
def freeze(source,cohort):
    log=json.loads((source/'export-log.json').read_text());out=FIX/cohort;out.mkdir(exist_ok=True)
    cases=[]
    for row in log['records']:
        name=row['id'];folder=out/'inputs'/name;folder.mkdir(parents=True,exist_ok=True)
        for file in ('drawing.svg','drawing.dxf','section.svg','native-drawing.svg'):
            if (source/name/file).exists():shutil.copyfile(source/name/file,folder/file)
        records,_=normalize((folder/'drawing.svg').read_bytes(),'DrawingContent');selected=[];matrices=[]
        for r in records:
            if r['tag']=='path' and r['style'].get('stroke')=='none' and r['matrix'] not in matrices:
                selected.append(r['id']);matrices.append(r['matrix'])
        assert len(selected)==3
        for fmt in ('svg','dxf'):
            ctx=dict(unit='mm',projection='third_angle',family_assumption=row['family'],
                     view_roles=dict(zip(('front','top','right'),selected if fmt=='svg' else ('Front','Top','Right'))))
            if fmt=='svg':ctx['drawing_group']='DrawingContent'
            (folder/('context-'+fmt+'.json')).write_bytes(json_bytes(ctx))
            case=dict(id=cohort+'_'+name+'_'+fmt,part=name,cohort=cohort,family=row['family'],format=fmt,
                      drawing=str((folder/('drawing.'+fmt)).relative_to(FIX)),context=str((folder/('context-'+fmt+'.json')).relative_to(FIX)),
                      truth=str((out/'evaluation'/name).relative_to(FIX)),opening=row.get('opening','top'),
                      expected='withheld' if name=='no_depth' or (row['family']=='pocket' and (fmt=='dxf' or row.get('solid_lines')) and not row.get('section')) else 'candidate',
                      derived_style=bool(row.get('solid_lines') and fmt=='svg'),
                      original_drawing=str((folder/'native-drawing.svg').relative_to(FIX)) if row.get('solid_lines') and fmt=='svg' else None)
            if row.get('section'):case['section']=str((folder/'section.svg').relative_to(FIX))
            for key in ('drawing','context','section'):
                if key in case:case[key+'_sha256']=hashlib.sha256((FIX/case[key]).read_bytes()).hexdigest()
            inf=baseline((FIX/case['drawing']).read_bytes(),ctx,fmt)
            # Observe the old decision before applying the new semantic policy.
            case['baseline']=dict(status=inf['status'],reason=inf.get('reason_code'),parameters=inf.get('parameters'),detail=inf.get('detail'))
            cases.append(case)
        ev=out/'evaluation'/name;ev.mkdir(parents=True,exist_ok=True)
        for f in ('truth.step','edited-truth.step'):shutil.copyfile(source/name/f,ev/f)
        (ev/'truth.json').write_bytes(json_bytes(dict(family=row['family'],parameters=row['p'],edited_parameters=row['edited_parameters'],
            opening=row.get('opening','top'),hashes={f:hashlib.sha256((ev/f).read_bytes()).hexdigest() for f in ('truth.step','edited-truth.step')})))
        au=out/'authoring';au.mkdir(exist_ok=True);shutil.copyfile(source/name/'source.FCStd',au/(name+'.FCStd'))
    shutil.copyfile(source/'export-log.json',out/'authoring/export-log.json')
    shutil.copyfile(source/'blank.svg',out/'authoring/blank.svg')
    (out/'manifest.json').write_bytes(json_bytes(dict(cases=cases,cohort=cohort,source_sha256=hashlib.sha256((ROOT/'experiments/export_drawing_generalization.FCMacro').read_bytes()).hexdigest())))
    return cases
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('cohort',choices=('development','holdout'))
    a=p.parse_args();freeze(a.source,a.cohort)
