"""Preserve own native CAD examples and evaluation-only authoring truth."""
import argparse,datetime,hashlib,json,shutil
from pathlib import Path
from research_notes.drawing_to_cad import json_bytes
from research_notes.svg_drawing_graphics import normalize
ROOT=Path(__file__).resolve().parents[1];FIX=ROOT/'fixtures/drawing-machining'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def freeze(source):
    if (source/'error.txt').exists():raise RuntimeError((source/'error.txt').read_text())
    log=json.loads((source/'export-log.json').read_text());cases=[]
    for row in log['records']:
        key=row['id'];folder=FIX/'inputs'/key;folder.mkdir(parents=True,exist_ok=False)
        for fmt in ('svg','dxf'):shutil.copyfile(source/key/('drawing.'+fmt),folder/('drawing.'+fmt))
        records,_=normalize((folder/'drawing.svg').read_bytes(),'DrawingContent');refs=[];matrices=[]
        for r in records:
            if r['tag']=='path' and r['style'].get('stroke')=='none' and r['matrix'] not in matrices:refs.append(r['id']);matrices.append(r['matrix'])
        if len(refs)!=3:raise ValueError('three authoring view frames expected')
        truth=FIX/'evaluation'/key;truth.mkdir(parents=True)
        for name in ('truth.step','edited-truth.step'):shutil.copyfile(source/key/name,truth/name)
        (truth/'truth.json').write_bytes(json_bytes(dict(parameters=row['p'],edited_parameters=row['edited_parameters'],hashes={name:sha(truth/name) for name in ('truth.step','edited-truth.step')})))
        author=FIX/'authoring';author.mkdir(exist_ok=True);shutil.copyfile(source/key/'source.FCStd',author/(key+'.FCStd'))
        for fmt in ('svg','dxf'):
            context=dict(unit='mm',projection='third_angle',family_assumption='bounded_stock_machining',view_roles=dict(zip(('front','top','right'),refs if fmt=='svg' else ('Front','Top','Right'))))
            if fmt=='svg':context['drawing_group']='DrawingContent'
            cp=folder/('context-'+fmt+'.json');cp.write_bytes(json_bytes(context))
            c=dict(id=key+'_'+fmt,part=key,cohort='development',format=fmt,drawing=str((folder/('drawing.'+fmt)).relative_to(FIX)),context=str(cp.relative_to(FIX)),truth=str(truth.relative_to(FIX)),
                category='insufficient_or_unsupported' if key in ('missing_depth','wrong_quantity','unsupported_fit') else 'in_scope_example')
            for name in ('drawing','context'):c[name+'_sha256']=sha(FIX/c[name])
            cases.append(c)
    shutil.copyfile(source/'export-log.json',FIX/'authoring/export-log.json')
    (FIX/'manifest.json').write_bytes(json_bytes(dict(captured_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),cases=cases,
        source_sha256=sha(ROOT/'experiments/export_drawing_machining.FCMacro'),scope='development examples; no held-out or automated tests')))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('source',type=Path);freeze(ap.parse_args().source)
