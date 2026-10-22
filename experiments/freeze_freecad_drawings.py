"""Freeze unmodified CAD exports and evaluation-only truth. Run after the macro."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
from research_notes.drawing_to_cad import FAMILY, json_bytes

ROOT=Path(__file__).resolve().parents[1]


def freeze(source,destination):
    if destination.exists():raise ValueError('use a new fixture directory')
    log=json.loads((source/'export-log.json').read_text())
    destination.mkdir(parents=True)
    evaluation=destination/'evaluation';evaluation.mkdir()
    authoring=destination/'authoring';authoring.mkdir()
    shutil.copyfile(source/'export-log.json',authoring/'export-log.json')
    shutil.copyfile(source/'blank.svg',authoring/'blank.svg')
    truth={};cases=[]
    reasons={'no_x':'hole_position_missing','no_thru':'hole_extent_ambiguous','tolerance':'unsupported_annotation'}
    for r in log['records']:
        identifier=r['id'];folder=destination/'inputs'/identifier;folder.mkdir(parents=True)
        for name in ('drawing.svg','drawing.dxf'):shutil.copyfile(source/identifier/name,folder/name)
        shutil.copyfile(source/identifier/'source.FCStd',authoring/(identifier+'.FCStd'))
        shutil.copyfile(source/identifier/'truth.step',evaluation/(identifier+'.step'))
        context=dict(unit='mm',family_assumption=FAMILY,projection=r['projection'],view_roles=dict(top='Top',front='Front',right='Right'))
        (folder/'context.json').write_bytes(json_bytes(context))
        p=r['parameters'];w,l,t=(p[k] for k in ('width','length','thickness'))
        truth[identifier]=dict(parameters=p,step=identifier+'.step',sha256=hashlib.sha256((evaluation/(identifier+'.step')).read_bytes()).hexdigest(),
                               analytic_volume=w*l*t-sum(math.pi*(h['diameter']/2)**2*t for h in p['holes']),
                               analytic_area=2*(w*l+w*t+l*t)+sum(math.pi*h['diameter']*t-2*math.pi*(h['diameter']/2)**2 for h in p['holes']))
        for format in ('dxf','svg'):
            reason='svg_export_graphics_unsupported' if format=='svg' else reasons.get(identifier)
            cases.append(dict(id=identifier+'_'+format,format=format,export_id=identifier,truth_key=identifier,
                              drawing=f'inputs/{identifier}/drawing.{format}',svg=f'inputs/{identifier}/drawing.svg',context=f'inputs/{identifier}/context.json',
                              expected_status='withheld' if reason else 'candidate',expected_reason=reason,
                              control_class='unsupported_format' if format=='svg' else 'negative_drawing' if reason else 'positive_drawing',
                              provenance='unmodified FreeCAD TechDraw export'))
    context=json.loads((destination/'inputs/one/context.json').read_text());context['projection']='first_angle'
    (destination/'inputs/one/wrong-projection.json').write_bytes(json_bytes(context))
    cases.append(dict(id='wrong_projection_dxf',format='dxf',export_id='one',truth_key='one',drawing='inputs/one/drawing.dxf',
                      svg='inputs/one/drawing.svg',context='inputs/one/wrong-projection.json',expected_status='withheld',
                      expected_reason='projection_layout_conflict',control_class='negative_context',provenance='unmodified DXF; intentionally wrong human projection context'))
    for case in cases:
        for key in ('drawing','svg','context'):case[key+'_sha256']=hashlib.sha256((destination/case[key]).read_bytes()).hexdigest()
    (evaluation/'truth.json').write_bytes(json_bytes(truth))
    hashes={str(p.relative_to(destination)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(destination.rglob('*')) if p.is_file()}
    manifest=dict(study='FreeCAD TechDraw exports to parametric CAD',date='2026-10-22',cases=cases,exporter_version=log['version'],
                  exporter_occt=log['occt'],runtime_sha256='f6dc6ba676e5ac96a565ebc8d657232f94c6158e85b4352141bd1a46f6b43434',
                  file_hashes=hashes,authoring_macro_sha256=hashlib.sha256((ROOT/'experiments/export_freecad_drawings.FCMacro').read_bytes()).hexdigest(),
                  license='Own authored models, drawings and blank template: repository PolyForm Noncommercial 1.0.0; FreeCAD runtime not redistributed')
    (destination/'manifest.json').write_bytes(json_bytes(manifest))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('source',type=Path);parser.add_argument('destination',type=Path)
    a=parser.parse_args();freeze(a.source,a.destination)
