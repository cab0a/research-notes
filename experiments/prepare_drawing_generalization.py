"""Preregistered inputs for exporter portability, ambiguity and untuned family evaluation."""
from pathlib import Path
import hashlib,json,random
from research_notes.drawing_to_cad import json_bytes
ROOT=Path(__file__).resolve().parents[1];FIX=ROOT/'fixtures/drawing-generalization'
def prepare():
    FIX.mkdir(parents=True,exist_ok=False)
    p=dict(width=60,length=40,thickness=12,pocket_x=12,pocket_y=10,pocket_width=20,pocket_length=14,pocket_depth=4)
    dev=[
        dict(id='top',family='pocket',p=p),
        dict(id='bottom',family='pocket',p={**p,'pocket_depth':8},opening='bottom'),
        dict(id='no_visibility',family='pocket',p=p,solid_lines=True),
        dict(id='section_top',family='pocket',p=p,solid_lines=True,section=True),
        dict(id='section_bottom',family='pocket',p={**p,'pocket_depth':8},opening='bottom',solid_lines=True,section=True),
        dict(id='no_depth',family='pocket',p=p,variant='missing_depth'),
    ]
    rng=random.Random(20261023);hold=[]
    for f in ('plate','l_bracket','stepped_shaft','pocket'):
        for i in range(6):
            if f=='plate':
                w=rng.randint(65,98);l=rng.randint(48,67)
                holes=[dict(x=round(w*.23,2),y=round(l*.26,2),diameter=5+i*.5)]
                if i%3>=1:holes.append(dict(x=round(w*.67,2),y=round(l*.69,2),diameter=7+i*.4))
                if i%3==2:holes.append(dict(x=round(w*.72,2),y=round(l*.27,2),diameter=5))
                params=dict(width=w,length=l,thickness=9+i,holes=holes)
            elif f=='l_bracket':
                params=dict(width=rng.randint(42,77),length=rng.randint(31,57),height=rng.randint(26,48),base_thickness=4+i*.4,wall_thickness=3+i*.5)
            elif f=='stepped_shaft':
                params=dict(length1=rng.randint(25,43),length2=rng.randint(12,23),diameter1=18+i,diameter2=7+i*.6)
            else:
                params=dict(width=rng.randint(65,87),length=rng.randint(44,63),thickness=14+i,
                            pocket_x=10+i*.5,pocket_y=8+i*.5,pocket_width=18+i,pocket_length=12+i,pocket_depth=4+i*.5)
            row=dict(id=f+'_'+str(i+1),family=f,p=params,scale=(.8,1.,1.15)[i%3],font=(2.8,3.2)[i%2])
            if f=='pocket' and i%2:row.update(opening='bottom')
            hold.append(row)
    (FIX/'development-specs.json').write_bytes(json_bytes(dev));(FIX/'holdout-specs.json').write_bytes(json_bytes(hold))
    protocol=dict(date='2026-10-22',base_commit='a32ed76fe513cbc41d3749f3f59de8c6141a77c2',seed=20261023,
        research=['different CAD renderer/exporter','visible/hidden and section ambiguity','24 unadjusted part configurations'],
        development='six pocket configurations and previous authored examples only',
        holdout='24 new parameter configurations, 6/family, SVG and DXF. Freeze engine before export/evaluation. Do not tune after observations.',
        heldout_scope='parameter/configuration holdout within known families and same FreeCAD authoring recipe; not independent customer/family benchmark',
        portability='LibreCAD 2.2.1.5 imports existing FreeCAD DXF and exports SVG; genuine second 2D CAD exporter, not native drafting in CATIA/NX',
        expected={'native_svg':'candidate when unambiguous and supported; failures retained, not adapted',
                  'native_dxf_pocket':'withhold without visibility/section evidence',
                  'other_cad_svg':'measure actual portability, no guaranteed support'},
        measures=['candidate correctness','false confirmation','safe withholding','coverage','dimensions','STEP validity','original/edit IoU','visibility/section residual'],
        thresholds=dict(dimension_mm=1e-6,iou=1-1e-8,projection_mm=.02,section_mm=.02),
        specs_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in FIX.glob('*-specs.json')},
        baseline_code={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                       [ROOT/'src/research_notes/drawing_families.py',ROOT/'src/research_notes/drawing_family_evidence.py',
                        ROOT/'src/research_notes/drawing_svg_extensions.py',ROOT/'src/research_notes/svg_drawing_graphics.py']})
    (FIX/'protocol.json').write_bytes(json_bytes(protocol))
if __name__=='__main__':prepare()
