"""Preregister own compound parts; no authoring parameters enter reconstruction."""
import json,random
from pathlib import Path
from research_notes.drawing_to_cad import json_bytes
ROOT=Path(__file__).resolve().parents[1];FIX=ROOT/'fixtures/drawing-composites'
def specs(w,l,t,kind,shift=0):
    if kind=='pocket_hole':fs=[dict(kind='pocket',x=12+shift,y=12,width=22,length=16,depth=5),dict(kind='hole',x=w-23,y=l-17,diameter=8)]
    elif kind=='two_pockets':fs=[dict(kind='pocket',x=10,y=12,width=20+shift,length=15,depth=5),dict(kind='pocket',x=w-44,y=l-29,width=24,length=18,depth=8)]
    else:fs=[dict(kind='step',x=0,y=0,width=26+shift,length=20,depth=6),dict(kind='hole',x=w-23,y=l-18,diameter=8)]
    return dict(width=w,length=l,thickness=t,features=fs)
def prepare():
    FIX.mkdir(parents=True,exist_ok=False)
    dev=[dict(id=k,family='composite',p=specs(*dims,k),scale=1,font=2.8) for k,dims in
         [('pocket_hole',(90,64,14)),('two_pockets',(108,72,18)),('step_hole',(90,64,16))]]
    mixed=specs(108,72,18,'two_pockets');mixed['features'][1]['opening']='bottom'
    dev.append(dict(id='mixed_pockets',family='composite',p=mixed,scale=1,font=2.8))
    rng=random.Random(2026102205);hold=[]
    for k in ('pocket_hole','two_pockets','step_hole'):
        for i in range(3):
            w=rng.randint(112,130);l=rng.randint(76,86);t=19+i*2
            p=specs(w,l,t,k,2+i)
            for f in p['features']:
                if f['kind']=='hole':f['diameter']+=i*.5;f['x']-=i;f['y']-=i
                else:f['depth']+=.5+i*.5;f['length']+=i
            hold.append(dict(id=k+'_'+str(i+1),family='composite',p=p,scale=(.9,1,1.1)[i],font=(2.8,3,3.2)[i]))
    for name,data in [('development',dev),('holdout',hold)]:
        (FIX/(name+'-specs.json')).write_bytes(json_bytes(data))
    (FIX/'protocol.json').write_bytes(json_bytes(dict(base_commit='4bee4f8',seed=2026102205,
        scope='Z-machined single stock plate, separated rectangular pockets/corner step and Z-through round holes; human view/family assumptions. Compare top/bottom openings.',
        development='3 authored compositions plus a mixed top/bottom pocket control and former holdout pocket_1/4 promoted to development for review.',
        holdout='9 new parameter configurations in 3 known compositions, SVG and DXF; freeze inference before CAD export, no adaptation after evaluation.',
        thresholds=dict(parameter_mm=1e-6,projection_mm=.02,iou=1-1e-8),
        human_measurement='Instrument interaction counts/time; agent-operated browser observations are not human productivity/ROI evidence.')))
if __name__=='__main__':prepare()
