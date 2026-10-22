"""Preserve independent authoring truth and drawing-only contexts."""
import argparse,hashlib,json,shutil,datetime
from pathlib import Path
from research_notes.drawing_to_cad import json_bytes
from research_notes.svg_drawing_graphics import normalize
ROOT=Path(__file__).resolve().parents[1];FIX=ROOT/'fixtures/drawing-composites'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def freeze(source,cohort):
    assert not (source/'error.txt').exists(),(source/'error.txt').read_text() if (source/'error.txt').exists() else ''
    log=json.loads((source/'export-log.json').read_text());out=FIX/cohort;out.mkdir(parents=True,exist_ok=False);cases=[]
    for row in log['records']:
        name=row['id'];folder=out/'inputs'/name;folder.mkdir(parents=True)
        for fmt in ('svg','dxf'):shutil.copyfile(source/name/('drawing.'+fmt),folder/('drawing.'+fmt))
        records,_=normalize((folder/'drawing.svg').read_bytes(),'DrawingContent');refs=[];matrices=[]
        for r in records:
            if r['tag']=='path' and r['style'].get('stroke')=='none' and r['matrix'] not in matrices:refs.append(r['id']);matrices.append(r['matrix'])
        assert len(refs)==3
        truthdir=out/'evaluation'/name;truthdir.mkdir(parents=True)
        for f in ('truth.step','edited-truth.step'):shutil.copyfile(source/name/f,truthdir/f)
        (truthdir/'truth.json').write_bytes(json_bytes(dict(parameters=row['p'],edited_parameters=row['edited_parameters'],
            hashes={f:sha(truthdir/f) for f in ('truth.step','edited-truth.step')})))
        au=out/'authoring';au.mkdir(exist_ok=True);shutil.copyfile(source/name/'source.FCStd',au/(name+'.FCStd'))
        for fmt in ('svg','dxf'):
            ctx=dict(unit='mm',projection='third_angle',family_assumption='axis_aligned_machined_plate',view_roles=dict(zip(('front','top','right'),refs if fmt=='svg' else ('Front','Top','Right'))))
            if fmt=='svg':ctx['drawing_group']='DrawingContent'
            cp=folder/('context-'+fmt+'.json');cp.write_bytes(json_bytes(ctx))
            c=dict(id=cohort+'_'+name+'_'+fmt,part=name,cohort=cohort,format=fmt,drawing=str((folder/('drawing.'+fmt)).relative_to(FIX)),context=str(cp.relative_to(FIX)),truth=str(truthdir.relative_to(FIX)),
                expected='candidate' if fmt=='svg' else 'withheld',provenance='Own FreeCAD TechDraw native export; authoring data evaluation-only')
            for k in ('drawing','context'):c[k+'_sha256']=sha(FIX/c[k])
            cases.append(c)
    shutil.copyfile(source/'export-log.json',out/'authoring/export-log.json')
    (out/'manifest.json').write_bytes(json_bytes(dict(cohort=cohort,frozen_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),cases=cases,
        source_sha256=sha(ROOT/'experiments/export_drawing_composites.FCMacro'))))
    return cases
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('cohort',choices=('development','holdout'))
    a=p.parse_args();freeze(a.source,a.cohort)
