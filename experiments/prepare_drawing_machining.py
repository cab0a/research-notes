"""Own CAD examples for bounded intersecting cuts, bore variants and dimension syntax."""
from pathlib import Path
from research_notes.drawing_to_cad import json_bytes
ROOT=Path(__file__).resolve().parents[1];FIX=ROOT/'fixtures/drawing-machining'
def bore(axis,u,v,diameter,extent='through',depth=None,entry='positive'):
    f=dict(kind='bore',axis=axis,u=u,v=v,diameter=diameter,extent=extent)
    if extent=='blind':f.update(depth=depth,entry=entry)
    return f
def prepare():
    FIX.mkdir(parents=True,exist_ok=False)
    def part(key,w,l,t,features,variant=None):
        return dict(id=key,family='machining',p=dict(width=w,length=l,thickness=t,features=features),variant=variant,scale=1,font=2.8)
    pocket=dict(kind='pocket',x=12,y=12,width=32,length=26,depth=6,opening='top')
    counter=dict(kind='counterbore',axis='z',u=28,v=24,diameter=6,counter_diameter=12,counter_depth=5,entry='positive')
    specs=[
        part('pocket_through',90,64,18,[pocket,bore('z',28,25,8)]),
        part('blind_z',72,54,20,[bore('z',26,22,10,'blind',8)]),
        part('counterbore',80,60,18,[counter]),
        part('side_blind',80,60,24,[bore('x',28,12,8,'blind',22)]),
        part('side_through',80,60,24,[bore('x',28,12,8)]),
        part('chain_quantity',84,60,14,[bore('z',20,18,6),bore('z',58,42,6)],'chain_quantity'),
        part('toleranced_bore',72,54,20,[bore('z',26,22,10,'blind',8)],'tolerance'),
        part('missing_depth',72,54,20,[bore('z',26,22,10,'blind',8)],'missing_depth'),
        part('wrong_quantity',84,60,14,[bore('z',20,18,6),bore('z',58,42,6)],'wrong_quantity'),
        part('unsupported_fit',72,54,20,[bore('z',26,22,10,'blind',8)],'fit'),
    ]
    (FIX/'authoring-specs.json').write_bytes(json_bytes(specs))
    (FIX/'protocol.json').write_bytes(json_bytes(dict(base_commit='283384e',date='2026-10-22',
        stage='development demonstrations; no held-out/generalization experiment',
        tests='No test additions or test execution, as requested. One-pass CAD reconstruction demonstrations recorded separately.',
        scope='Internal rectangular pocket containing a Z-through bore; flat-bottom blind, counterbored through and side bores; graphical chain/quantity/numeric tolerances.',
        human_inputs='mm, projection/view mapping, bounded stock-machining family; no numeric shape overrides',
        boundaries=['no interacting side bores','no drill-tip cones','no fit/GD&T interpretation','no tolerance stack analysis','no arbitrary contour or customer-drawing accuracy'])))
if __name__=='__main__':prepare()
