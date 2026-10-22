"""Freeze actual CAD exports and measure the unchanged c95aeca-era baseline."""
from pathlib import Path
import hashlib,json,shutil
from research_notes.drawing_to_cad import FAMILY,json_bytes
from research_notes.svg_drawing_graphics import normalize
from research_notes.cad_svg_import import interpret_native_svg
from research_notes.cad_drawing_import import interpret_cad_drawing

ROOT=Path(__file__).resolve().parents[1]

def freeze(source,destination):
    destination.mkdir(parents=True,exist_ok=False)
    log=json.loads((source/'export-log.json').read_text());cases=[];baseline=[]
    for row in log['records']:
        name=row['id'];folder=destination/'inputs'/name;folder.mkdir(parents=True)
        svg=(source/name/'drawing.svg').read_bytes();records,_=normalize(svg,'DrawingContent')
        selected=[];matrices=[]
        for r in records:
            if r['tag']=='path' and r['style'].get('stroke')=='none' and r['matrix'] not in matrices:
                selected.append(r['id']);matrices.append(r['matrix'])
        assert len(selected)==3,(name,selected)
        for fmt in ('svg','dxf'):
            raw=folder/('drawing.'+fmt);shutil.copyfile(source/name/raw.name,raw)
            ctx=dict(unit='mm',projection='third_angle',family_assumption=row['family'],
                     view_roles=dict(zip(('front','top','right'),selected if fmt=='svg' else ('Front','Top','Right'))))
            if fmt=='svg':ctx['drawing_group']='DrawingContent'
            context=folder/('context-'+fmt+'.json');context.write_bytes(json_bytes(ctx))
            oldctx={**ctx,'family_assumption':FAMILY if row['family']=='plate' else row['family']}
            result=interpret_native_svg(raw.read_bytes(),oldctx) if fmt=='svg' else interpret_cad_drawing(raw.read_bytes(),oldctx,fmt)
            baseline.append(dict(id=name+'_'+fmt,status=result['status'],reason=result.get('reason_code'),detail=result.get('detail'),
                                 initial_unseen_setting=name.startswith('unseen_')))
            cases.append(dict(id=name+'_'+fmt,part=name,format=fmt,family=row['family'],
                              drawing=str(raw.relative_to(destination)),context=str(context.relative_to(destination)),
                              drawing_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),context_sha256=hashlib.sha256(context.read_bytes()).hexdigest(),
                              cohort='initial_unseen_settings' if name.startswith('unseen_') else 'development',
                              expected='withheld' if 'missing' in name else 'candidate',
                              expected_reason='dimension_missing' if 'missing' in name else None))
        ev=destination/'evaluation'/name;ev.mkdir(parents=True)
        for file in ('truth.step','edited-truth.step'):shutil.copyfile(source/name/file,ev/file)
        (ev/'truth.json').write_bytes(json_bytes(dict(family=row['family'],parameters=row['p'],edited_parameters=row['edited_parameters'],
                                                    cad_volume=row['truth_volume'],cad_area=row['truth_area'],
                                                    hashes={file:hashlib.sha256((ev/file).read_bytes()).hexdigest() for file in ('truth.step','edited-truth.step')})))
        au=destination/'authoring';au.mkdir(exist_ok=True);shutil.copyfile(source/name/'source.FCStd',au/(name+'.FCStd'))
    shutil.copyfile(source/'export-log.json',destination/'authoring/export-log.json')
    shutil.copyfile(source/'blank.svg',destination/'authoring/blank.svg')
    (destination/'manifest.json').write_bytes(json_bytes(dict(cases=cases,license='PolyForm-Noncommercial-1.0.0',
        provenance='Own-authored FreeCAD 1.1.4 TechDraw exports, raw bytes unchanged',
        authoring_macro_sha256=hashlib.sha256((ROOT/'experiments/export_drawing_families.FCMacro').read_bytes()).hexdigest())))
    (destination/'baseline.json').write_bytes(json_bytes(dict(base_commit='c95aeca568b0f77127479198cb4e13b2522e0ac2',observations=baseline,
        code_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['src/research_notes/cad_svg_import.py','src/research_notes/cad_drawing_import.py','src/research_notes/svg_drawing_graphics.py']},
        warning='Initial unseen settings are now observed development data; later adapted results are not held-out accuracy.')))

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('destination',type=Path)
    a=p.parse_args();freeze(a.source,a.destination)
