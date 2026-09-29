"""Build authored STEP revision controls without calling the matching engine.

Normal evaluation reads committed bytes; this explicit command regenerates them.
"""
from pathlib import Path
import hashlib
import json
import math

from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.gp import gp_Ax1, gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf
from research_notes.step_writer_modes import prepare_step_write

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'fixtures/revision-comparison'
BASE = {'holes': [[6., 5., 1.]], 'thickness': 4., 'width': 12., 'length': 10.}


def spec(**kwargs):
    return {**BASE, **kwargs}


def geometry(s):
    if s.get('split_plane'):
        # Adjacent boxes are fused without same-domain simplification.
        a = BRepPrimAPI_MakeBox(6., s['length'], s['thickness']).Shape()
        b = BRepPrimAPI_MakeBox(gp_Pnt(6., 0., 0.), 6., s['length'], s['thickness']).Shape()
        shape = BRepAlgoAPI_Fuse(a, b).Shape()
    else:
        shape = BRepPrimAPI_MakeBox(s['width'], s['length'], s['thickness']).Shape()
    for x, y, radius in s['holes']:
        bottom = s['thickness']/2 if s.get('blind') else -2.
        tool = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y, bottom), gp_Dir(0, 0, 1)),
                                      radius, s['thickness'] + 4.).Shape()
        shape = BRepAlgoAPI_Cut(shape, tool).Shape()
    if s.get('rotate'):
        tr = gp_Trsf()
        tr.SetRotation(gp_Ax1(gp_Pnt(0., 0., 0.), gp_Dir(0, 0, 1)), s['rotate'])
        shape = BRepBuilderAPI_Transform(shape, tr, True).Shape()
    if s.get('shift'):
        from OCP.gp import gp_Vec
        tr = gp_Trsf(); tr.SetTranslation(gp_Vec(*s['shift']))
        shape = BRepBuilderAPI_Transform(shape, tr, True).Shape()
    return shape


def expected(old, new, pairs, statuses, disposition='compared'):
    dims = [{'name': '板厚', 'old': old['thickness'], 'new': new['thickness']}]
    for i, j in pairs:
        a, b = sorted(old['holes'])[i], sorted(new['holes'])[j]
        dims += [{'name': name, 'old': x, 'new': y} for name, x, y in (
            ('穴径', 2*a[2], 2*b[2]), ('穴中心X', a[0], b[0]), ('穴中心Y', a[1], b[1]))]
    for d in dims:
        d['delta'] = d['new'] - d['old']
    return {'disposition': disposition, 'hole_status_counts': statuses, 'dimensions': dims}


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / 'sources').mkdir(exist_ok=True)
    a = spec()
    cases = []
    def add(key, label, b, statuses, pairs=((0, 0),), before=None, disposition='compared', changes=()):
        old = before or a
        truth = expected(old, b, pairs, statuses, disposition)
        if disposition == 'unresolved':
            truth['dimensions'] = []
        cases.append({'id': key, 'label': label, 'kind': 'authored_control', 'old_recipe': old,
            'new_recipe': b, 'known_changes': list(changes), 'expected': truth})
    add('identical_reordered', '同形状・穴の作成順変更', spec(holes=[[9., 5., 1.], [3., 5., .8]]),
        {'unchanged': 2}, ((0, 0), (1, 1)), before=spec(holes=[[3., 5., .8], [9., 5., 1.]]))
    add('diameter', '穴径変更', spec(holes=[[6., 5., 1.3]]), {'changed': 1}, changes=['diameter'])
    add('position', '等体積の穴位置変更', spec(holes=[[7.5, 5.5, 1.]]), {'changed': 1}, changes=['x', 'y'])
    add('thickness', '板厚変更', spec(thickness=5.), {'changed': 1}, changes=['thickness'])
    add('addition', '穴追加', spec(holes=[[3., 5., .8], [9., 5., .8]]), {'unchanged': 1, 'added': 1},
        before=spec(holes=[[3., 5., .8]]), changes=['added_hole'])
    add('deletion', '穴削除', spec(holes=[[3., 5., .8]]), {'unchanged': 1, 'deleted': 1},
        before=spec(holes=[[3., 5., .8], [9., 5., .8]]), changes=['deleted_hole'])
    add('ambiguous', '繰り返し穴の曖昧な対応', spec(holes=[[6., 3., .6], [6., 5., .6]]),
        {'unresolved': 4}, (), before=spec(holes=[[4., 4., .6], [8., 4., .6]]), disposition='partial', changes=['moved_holes'])
    add('distant_move', '検索距離を超える穴移動', spec(holes=[[10., 5., .5]]), {'unresolved': 2}, (),
        before=spec(holes=[[2., 5., .5]]), disposition='partial', changes=['x'])
    add('translated', '板全体の平行移動', spec(shift=[30., 0., 0.]), {}, (), disposition='unresolved')
    add('rotated', '板全体の回転', spec(rotate=math.pi/12), {}, (), disposition='unresolved')
    add('outer_width', '板の外形幅変更', spec(width=13.), {}, (), disposition='unresolved', changes=['outer_width'])
    add('blind_hole', '止まり穴への変更', spec(blind=True), {}, (), disposition='unresolved', changes=['hole_depth'])
    add('within_tolerance', '許容差内の穴径差', spec(holes=[[6., 5., 1.000001]]), {'unchanged': 1})
    add('above_tolerance', '許容差を超える微小な穴径差', spec(holes=[[6., 5., 1.00002]]), {'changed': 1}, changes=['diameter'])
    add('combined', '穴径と位置の同時変更', spec(holes=[[7., 5.5, 1.2]]), {'changed': 1}, changes=['diameter', 'x', 'y'])
    add('split_plane', '同形状・平面分割', spec(holes=[], split_plane=True), {}, (),
        before=spec(holes=[]), disposition='unresolved')
    assets = {}
    for case in cases:
        for side in ('old', 'new'):
            payload, _ = prepare_step_write(source=None, mode='reconstruct', shape=geometry(case[side + '_recipe']))
            name = 'sources/' + case['id'] + '-' + side + '.step'
            path = DEST / name; path.write_bytes(payload)
            case[side] = name
            assets[name] = {'sha256': hashlib.sha256(payload).hexdigest(), 'bytes': len(payload),
                'origin': 'Authored by Inefficiency Lab; independent box/cylinder construction, no matching code',
                'license': 'PolyForm-Noncommercial-1.0.0', 'license_path': '../../LICENSE',
                'generator': 'experiments/build_revision_fixtures.py'}
    public = json.loads((ROOT / 'fixtures/public-step-corpus/manifest.json').read_text())
    for asset in public['assets']:
        if asset['role'] != 'step':
            continue
        name = '../public-step-corpus/' + asset['path']
        provenance = next(s for s in public['samples'] if s['asset_path'] == asset['path'])
        assets[name] = {**asset, 'origin': 'unmodified_external_step',
            **{k: provenance[k] for k in ('attribution', 'license_id', 'license_paths', 'retrieved_utc', 'modifications')},
            'provenance_manifest': '../public-step-corpus/manifest.json'}
        key = Path(asset['path']).stem
        cases.append({'id': key, 'label': key, 'kind': 'external_intake_control',
            'old': name, 'new': name, 'known_changes': [],
            'expected': {'disposition': 'rejected', 'hole_status_counts': {}, 'dimensions': []},
            'expectation_basis': 'Existing v1.5 single-root, explicit-mm, <=24-face input contract; '
                'self-pair tests intake only, not an authentic manufacturer revision or change-detection accuracy.'})
    manifest = {'schema_version': 1, 'version': '1.7.0',
        'selection': '16 authored controls fixed before evaluation plus all 6 previously frozen external STEP files. '
                     'Not a representative industrial corpus or independent learning test set.',
        'tuning': 'v1.5 tolerances and matching rule retained; no thresholds fitted to this corpus.',
        'assets': assets, 'cases': cases}
    (DEST / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(f'Wrote {len(cases)} fixed cases and {len(assets)} assets')


if __name__ == '__main__':
    main()
