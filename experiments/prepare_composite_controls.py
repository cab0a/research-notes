"""Promote prior failures to development; preserve negative drawing controls."""
import copy,hashlib,json,shutil,xml.etree.ElementTree as ET
from pathlib import Path
from research_notes.drawing_to_cad import json_bytes
from research_notes.drawing_composites import interpret
ROOT=Path(__file__).resolve().parents[1];FIX=ROOT/'fixtures/drawing-composites'
OLD=ROOT/'fixtures/drawing-generalization'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def convert(p,opening):
    return dict(width=p['width'],length=p['length'],thickness=p['thickness'],features=[dict(kind='pocket',opening=opening,
        x=p['pocket_x'],y=p['pocket_y'],width=p['pocket_width'],length=p['pocket_length'],depth=p['pocket_depth'])])
def prepare():
    out=FIX/'controls';out.mkdir(exist_ok=False);cases=[]
    for name,source,cohort in [
        ('review_pocket_1',OLD/'holdout/inputs/pocket_1','review'),('review_pocket_4',OLD/'holdout/inputs/pocket_4','review'),
        ('missing_depth',OLD/'development/inputs/no_depth','negative'),('visibility_lost',OLD/'development/inputs/no_visibility','negative'),
        ('wrong_views',FIX/'development/inputs/pocket_hole','negative'),('dimension_conflict',FIX/'development/inputs/pocket_hole','negative')]:
        folder=out/name;folder.mkdir();raw=(source/'drawing.svg').read_bytes();ctx=json.loads((source/'context-svg.json').read_text())
        ctx['family_assumption']='axis_aligned_machined_plate'
        if name=='wrong_views':ctx['view_roles']['top'],ctx['view_roles']['front']=ctx['view_roles']['front'],ctx['view_roles']['top']
        if name=='dimension_conflict':
            root=ET.fromstring(raw);count=0
            for e in root.iter():
                if e.tag.split('}')[-1] in ('text','tspan') and e.text and e.text.strip()=='90':e.text='91';count+=1
            assert count>0;raw=ET.tostring(root)
        (folder/'drawing.svg').write_bytes(raw);(folder/'context.json').write_bytes(json_bytes(ctx))
        c=dict(id=name,part=name,cohort=cohort,format='svg',expected='review_then_candidate' if cohort=='review' else 'withheld',
            drawing=str((folder/'drawing.svg').relative_to(FIX)),context=str((folder/'context.json').relative_to(FIX)),
            provenance=str(source.relative_to(ROOT)),original_sha256=sha(source/'drawing.svg'),derived=(name in ('wrong_views','dimension_conflict')))
        if cohort=='review':
            oldtruth=OLD/'holdout/evaluation'/name.removeprefix('review_');truth=json.loads((oldtruth/'truth.json').read_text())
            ev=folder/'evaluation';ev.mkdir()
            for f in ('truth.step','edited-truth.step'):shutil.copyfile(oldtruth/f,ev/f)
            (ev/'truth.json').write_bytes(json_bytes(dict(parameters=convert(truth['parameters'],truth['opening']),
                edited_parameters=convert(truth['edited_parameters'],truth['opening']),hashes={f:sha(ev/f) for f in ('truth.step','edited-truth.step')})))
            c['truth']=str(ev.relative_to(FIX));c['edit_policy']='legacy_single_pocket'
        for k in ('drawing','context'):c[k+'_sha256']=sha(FIX/c[k])
        inf=interpret(raw,ctx,'svg');(folder/'initial-inference.json').write_bytes(json_bytes(inf))
        print(name,inf['status'],inf.get('reason_code'),inf.get('detail'),inf.get('review_request'))
        cases.append(c)
    (out/'manifest.json').write_bytes(json_bytes(dict(cases=cases)))
if __name__=='__main__':prepare()
