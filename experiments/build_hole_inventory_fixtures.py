"""Freeze independent geometry recipes and hole truth before inventory evaluation."""
from pathlib import Path
import hashlib
import json
import math

from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax1, gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
from research_notes.step_writer_modes import prepare_step_write

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT/'fixtures/hole-inventory'


def build(recipe):
    if recipe.get('split'):
        shape = BRepAlgoAPI_Fuse(BRepPrimAPI_MakeBox(6., 10., 4.).Shape(), BRepPrimAPI_MakeBox(gp_Pnt(6., 0., 0.), 6., 10., 4.).Shape()).Shape()
    else:
        shape = BRepPrimAPI_MakeBox(12., 10., 4.).Shape()
    for hole in recipe.get('holes', []):
        x, y, radius, bottom, top = hole
        direction = gp_Dir(0, .3, 1) if recipe.get('tilt') else gp_Dir(0, 0, 1)
        tool = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y, bottom), direction), radius, top-bottom).Shape()
        shape = BRepAlgoAPI_Cut(shape, tool).Shape()
    if recipe.get('boss'):
        shape = BRepAlgoAPI_Fuse(shape, BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(6., 5., 4.), gp_Dir(0,0,1)), 1., 2.).Shape()).Shape()
    if recipe.get('rotate'):
        tr = gp_Trsf(); tr.SetRotation(gp_Ax1(gp_Pnt(0,0,0),gp_Dir(0,0,1)), math.pi/12)
        shape = BRepBuilderAPI_Transform(shape,tr,True).Shape()
    if recipe.get('shift'):
        tr = gp_Trsf(); tr.SetTranslation(gp_Vec(*recipe['shift']))
        shape = BRepBuilderAPI_Transform(shape,tr,True).Shape()
    return shape


def main():
    recipes = [
        ('no_holes', {}, 'complete'),
        ('single', {'holes': [[6.,5.,1.,-1.,5.]]}, 'complete'),
        ('multiple_diameters', {'holes': [[3.,3.,.6,-1.,5.],[6.,5.,1.,-1.,5.],[9.,7.,1.25,-1.,5.]]}, 'complete'),
        ('four_equal', {'holes': [[3.,3.,.6,-1.,5.],[3.,7.,.6,-1.,5.],[9.,3.,.6,-1.,5.],[9.,7.,.6,-1.,5.]]}, 'complete'),
        ('blind_top', {'holes': [[6.,5.,1.,2.,5.]]}, 'complete'),
        ('blind_bottom', {'holes': [[6.,5.,1.,-1.,2.]]}, 'complete'),
        ('mixed', {'holes': [[3.,5.,.8,-1.,5.],[9.,5.,1.,1.,5.]]}, 'complete'),
        ('translated', {'holes': [[6.,5.,1.,-1.,5.]], 'shift': [30.,-20.,7.]}, 'complete'),
        ('rotated', {'holes': [[6.,5.,1.,-1.,5.]], 'rotate': True}, 'unresolved'),
        ('boss', {'boss': True}, 'unresolved'),
        ('intersecting', {'holes': [[5.,5.,1.5,-1.,5.],[6.,5.,1.5,-1.,5.]]}, 'unresolved'),
        ('edge_hole', {'holes': [[1.,5.,1.,-1.,5.]]}, 'unresolved'),
        ('split_plane', {'split': True}, 'unresolved'),
        ('counterbore', {'holes': [[6.,5.,.6,-1.,5.],[6.,5.,1.,2.,5.]]}, 'unresolved'),
        ('tilted_hole', {'holes': [[6.,4.,.6,-1.,5.]], 'tilt': True}, 'unresolved'),
    ]
    (DEST/'sources').mkdir(parents=True,exist_ok=True)
    assets, cases = {}, []
    for key, recipe, status in recipes:
        expected = []
        if status == 'complete':
            shift = recipe.get('shift', [0.,0.,0.])
            for x,y,r,bottom,top in sorted(recipe.get('holes', [])):
                at_top = top >= 4.
                expected.append({'kind': 'through' if bottom<=0 and top>=4 else 'blind',
                    'diameter_mm': 2*r, 'x_mm': x+shift[0], 'y_mm': y+shift[1],
                    'entry_z_mm': (4. if at_top else 0.)+shift[2],
                    'depth_mm': min(4.,top)-max(0.,bottom), 'axis': [0,0,-1 if at_top else 1]})
        data,_ = prepare_step_write(source=None,mode='reconstruct',shape=build(recipe))
        name = 'sources/'+key+'.step'; (DEST/name).write_bytes(data)
        assets[name] = {'sha256': hashlib.sha256(data).hexdigest(), 'bytes':len(data),
            'origin': 'Inefficiency Lab independent box/cylinder construction',
            'license': 'PolyForm-Noncommercial-1.0.0', 'generator': 'experiments/build_hole_inventory_fixtures.py'}
        cases.append({'id':key,'kind':'authored_control','source':name,'recipe':recipe,
                      'expected':{'status':status,'holes':expected,'hole_count':len(expected) if status=='complete' else None}})
    public = json.loads((ROOT/'fixtures/public-step-corpus/manifest.json').read_text())
    for item in public['assets']:
        if item['role'] != 'step':
            continue
        name = '../public-step-corpus/'+item['path']
        provenance = next(s for s in public['samples'] if s['asset_path']==item['path'])
        assets[name] = {**item, **{k:provenance[k] for k in ('attribution','license_id','license_paths','retrieved_utc','modifications')}}
        cases.append({'id':Path(item['path']).stem,'kind':'external_intake_control','source':name,
                      'expected':{'status':'rejected','holes':[],'hole_count':None}})
    manifest = {'schema_version':1,'version':'1.8.0','selection':'15 fixed authored cases and all six frozen external STEP sources; not representative industrial accuracy.',
                'truth_policy':'Analytic recipes frozen before evaluation; recognizer receives only STEP bytes and name.',
                'assets':assets,'cases':cases}
    (DEST/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(f'Wrote {len(cases)} cases and STEP inputs.')


if __name__ == '__main__':
    main()
