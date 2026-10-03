"""Single-STEP circular-hole and straight-slot inventory with explicit unknown totals."""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
import hashlib
import io
import json
import math
from pathlib import Path
import secrets
import tempfile

from research_notes.cad_api import CadAPIError
from research_notes.revision_detection import LENGTH_TOL, FIT_REL_TOL

VERSION = "1.12.0"
MAX_SOURCE_BYTES = 2_000_000
STATUS_LABELS = {"complete": "対応範囲内で一覧取得", "partial": "穴を部分確認・全体は保留", "unresolved": "形状の判定保留", "rejected": "読込条件で拒否"}
TYPE_LABELS = {"through": "丸穴・貫通", "blind": "丸穴・平底止まり", "straight_through_slot": "長孔・貫通"}
CONDITIONS = {
    "scope": "軸に平行な長方形の板と、互いに離れたZ方向の円筒貫通穴・平底の止まり穴。単体ソリッド・最大24面。",
    "coordinate_reference": "STEP内の座標系を維持。X/Yは円筒軸、Zは穴の開口平面との交点（mm）。貫通穴は上面を開口として表示。",
    "axis_reference": "開口から穴の内部へ向かう単位ベクトル。貫通穴は-Zを選択。",
    "measurement_scope": "幾何からの測定値。元CADの公称寸法・公差・設計履歴ではありません。",
    "count_policy": "板と穴の再構成が入力と一致した場合のみ全体の穴数を表示。保留・拒否では穴数は不明。",
    "length_tolerance_mm": LENGTH_TOL,
    "fit_relative_tolerance": FIT_REL_TOL,
}


def describe_holes(imported):
    """Certify the complete material grammar before reporting any hole count."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
    from research_notes.modeling_common import measure_shape
    from research_notes.parametric_features import boolean_shape, shape_difference_volume
    from research_notes.step_reconstruction import face_evidence

    try:
        faces = face_evidence(imported.shape)
        metrics = imported.metrics
        if max(metrics.maximum_face_tolerance, metrics.maximum_edge_tolerance, metrics.maximum_vertex_tolerance) > LENGTH_TOL:
            raise ValueError("入力形状の許容差が判定許容差を超えています。")
        low = [min(f.bounds_min[i] for f in faces) for i in range(3)]
        high = [max(f.bounds_max[i] for f in faces) for i in range(3)]
        if any(b-a <= 10*LENGTH_TOL for a, b in zip(low, high)):
            raise ValueError("板の寸法が判定許容差に近すぎます。")
        boundary, holes = {}, []
        for face in faces:
            if face.surface_type == "plane":
                axis = face.axis
                value = face.bounds_min[axis]
                if abs(face.bounds_max[axis] - value) > LENGTH_TOL:
                    raise ValueError("平面の境界位置を確定できません。")
                end = "min" if abs(value-low[axis]) <= LENGTH_TOL else "max" if abs(value-high[axis]) <= LENGTH_TOL else None
                if end is None:
                    if axis != 2:
                        raise ValueError("段差・ポケット・斜面は判定範囲外です。")
                else:
                    role = (axis, end)
                    if role in boundary:
                        raise ValueError("外周平面の分割は判定範囲外です。")
                    boundary[role] = face.face_index
                continue
            x, y, radius = face.center_x, face.center_y, face.radius
            if radius <= LENGTH_TOL or not (low[0]+radius+LENGTH_TOL < x < high[0]-radius-LENGTH_TOL and low[1]+radius+LENGTH_TOL < y < high[1]-radius-LENGTH_TOL):
                raise ValueError("外周に接する穴・突起は判定範囲外です。")
            bottom, top = face.bounds_min[2], face.bounds_max[2]
            at_bottom, at_top = abs(bottom-low[2]) <= LENGTH_TOL, abs(top-high[2]) <= LENGTH_TOL
            if not (at_bottom or at_top) or top-bottom <= 10*LENGTH_TOL:
                raise ValueError("段付き穴・内部空洞・浅すぎる穴は判定範囲外です。")
            kind = "through" if at_bottom and at_top else "blind"
            entry = high[2] if at_top else low[2]
            holes.append({"kind": kind, "diameter_mm": 2*radius, "x_mm": x, "y_mm": y,
                          "entry_z_mm": entry, "depth_mm": top-bottom,
                          "axis": [0, 0, -1 if at_top else 1], "faces": [face.face_index],
                          "_bottom": bottom, "_top": top, "_radius": radius})
        if len(boundary) != 6:
            raise ValueError("長方形の板の6外周平面を確認できません。")
        for i, hole in enumerate(holes):
            if any(math.hypot(hole['x_mm']-other['x_mm'], hole['y_mm']-other['y_mm']) <= hole['_radius']+other['_radius']+LENGTH_TOL for other in holes[i+1:]):
                raise ValueError("穴の交差・同軸の段付き穴・円筒面の分割は判定範囲外です。")
        rebuilt = BRepPrimAPI_MakeBox(gp_Pnt(*low), *(high[i]-low[i] for i in range(3))).Shape()
        for hole in holes:
            bottom = low[2]-1 if hole['_bottom'] <= low[2]+LENGTH_TOL else hole['_bottom']
            top = high[2]+1 if hole['_top'] >= high[2]-LENGTH_TOL else hole['_top']
            tool = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(hole['x_mm'], hole['y_mm'], bottom), gp_Dir(0, 0, 1)), hole['_radius'], top-bottom).Shape()
            rebuilt = boolean_shape(rebuilt, tool, operation="cut")
        rebuilt_metrics = measure_shape(rebuilt)
        residual = shape_difference_volume(imported.shape, rebuilt)
        volume_gate = max(1e-7, metrics.absolute_volume*FIT_REL_TOL)
        area_residual = abs(rebuilt_metrics.surface_area-metrics.surface_area)
        area_gate = max(1e-7, metrics.surface_area*FIT_REL_TOL)
        if not rebuilt_metrics.analyzer_valid or residual > volume_gate or area_residual > area_gate:
            raise ValueError("板と穴で再構成した材料領域・面積が入力と一致しません。")
        holes.sort(key=lambda h: (h['x_mm'], h['y_mm'], h['entry_z_mm'], h['kind']))
        for i, hole in enumerate(holes, 1):
            hole['id'] = f"H{i}"
            for key in ('_bottom', '_top', '_radius'):
                hole.pop(key)
        return {"status": "complete", "reason": "板と円筒穴の再構成を、入力の材料領域・面積と照合しました。",
                "hole_count": len(holes), "holes": holes, "bounds_min": low, "bounds_max": high,
                "material_residual_mm3": residual, "material_gate_mm3": volume_gate,
                "area_residual_mm2": area_residual, "area_gate_mm2": area_gate}
    except (ValueError, RuntimeError) as error:
        return {"status": "unresolved", "reason": str(error), "hole_count": None, "holes": []}


def _merge_slots(analysis, shape):
    """Adapt the v1.10 measurements without changing recognition thresholds.

    The circular rows and H IDs stay intact; slot rows retain their S IDs and
    wall evidence. Partial measurements never upgrade the whole-part count.
    """
    from research_notes.slot_inventory import scan_straight_through_slots

    try:
        slots = scan_straight_through_slots(shape)
    except (ValueError, RuntimeError) as error:
        analysis['slot_scan'] = {'status': 'unresolved', 'reason': str(error), 'recognized_slot_count': 0}
        analysis['reason'] += ' 長孔の判定は保留しました。'+str(error)
        return
    analysis['slot_scan'] = {k: v for k, v in slots.items() if k != 'slots'}
    accepted_faces = set()
    for slot in slots['slots']:
        x, y, z = slot['entry_center_mm']
        analysis['holes'].append({**slot, 'feature_type': 'straight_slot', 'diameter_mm': None,
                                  'x_mm': x, 'y_mm': y, 'entry_z_mm': z,
                                  'axis': slot['through_direction'], 'faces': slot['wall_faces']})
        accepted_faces.update(slot['wall_faces'])
    # A semicylinder accepted as a slot is no longer an unresolved wall.
    analysis['withheld_cylinders'] = [row for row in analysis.get('withheld_cylinders', [])
                                    if row['face_index'] not in accepted_faces]
    circles = sum(h['kind'] != 'straight_through_slot' for h in analysis['holes'])
    analysis['status'] = 'partial' if analysis['holes'] else 'unresolved'
    analysis['hole_count'] = None
    analysis['reason'] = (f"丸穴{circles}か所・長孔{len(slots['slots'])}か所を局所検証しました。"
                          '未対応形状を含む全体の穴数は確定していません。')


def _inventory_rows(result):
    """Use one additive row schema while keeping diameter distinct from slot width."""
    for hole in result['holes']:
        if hole['kind'] != 'straight_through_slot':
            hole.update(feature_type='circular_hole', width_mm=None, length_mm=None,
                        longitudinal_direction=None)
    result['recognized_circular_hole_count'] = sum(h['feature_type'] == 'circular_hole' for h in result['holes'])
    result['recognized_slot_count'] = sum(h['feature_type'] == 'straight_slot' for h in result['holes'])
    result['recognized_hole_count'] = len(result['holes'])


def analyze_step(source, file_name="uploaded.step", *, preview=True, inspection=False, include_slots=True):
    """Inspect one snapshot; public intake includes slots unless explicitly disabled.

    `holes` is the unified row list. `recognized_hole_count` is its size, with
    circular/slot subtotals. `hole_count` is only a whole-plate certificate.
    Strict plate intake (`inspection=False`) retains its original scope.
    """
    from research_notes.step_reconstruction import read_step_input
    if not source or len(source) > MAX_SOURCE_BYTES:
        raise CadAPIError("resource_limit", "STEPは空でない2 MB以下のファイルを選択してください。")
    name = file_name.replace('\\', '/').rsplit('/', 1)[-1][:200] or 'uploaded.step'
    result = {"inventory_version": VERSION, "file_name": name, "source_sha256": hashlib.sha256(source).hexdigest(),
              "source_bytes": len(source), "length_unit": None, "conditions": CONDITIONS,
              "preview": None, "metrics": None, "analysis_mode": "public_inspection" if inspection else "legacy_plate",
              "feature_scope": "circular_and_slots" if inspection and include_slots else "circular_only"}
    try:
        with tempfile.TemporaryDirectory(prefix="research-cad-holes-") as directory:
            path = Path(directory) / 'source.step'
            path.write_bytes(source)
            if inspection:
                from research_notes.public_hole_inventory import inspect_holes
                intake, analysis = inspect_holes(path)
                imported = intake.imported
                result.update(roots=intake.roots, unit_contexts=intake.unit_contexts)
                result['conditions'] = {**CONDITIONS,
                    'scope': '2 MB以下。検査用読込で複数単位定義・複数ソリッドに対応。全体確定は従来の板モデル。その他は両端が平面の丸穴と、条件を満たす直線状の貫通長孔を局所検証（最大512面）。' if include_slots else '2 MB以下・最大512面。丸穴のみを検証。長孔認識は無効です。',
                    'coordinate_reference': 'mmへ変換したSTEP座標。X/Y/開口Zは表示用に選んだ開口中心。局所検証では開口中心の辞書順が大きい側を選択し、加工方向は推定しません。',
                    'axis_reference': '選択した開口から反対の開口（穴内部）へ向かう単位ベクトル。',
                    'count_policy': '全体確定の場合のみhole_countを表示。確認できた穴の行数と丸穴・長孔の内訳を表示し、全体の穴数不明と区別。候補が0件でも穴なしとしません。',
                    'slot_measurements': '長孔の幅は半円の直径、全長は両端の半円を含む長さ。位置は選択した開口の中心。長手方向と貫通方向は別の単位ベクトルです。丸穴の幅・全長・長手方向と、長孔の穴径は該当なし。',
                    'local_qualification_tolerance_mm': 1e-5}
                if include_slots and analysis['status'] != 'complete':
                    _merge_slots(analysis, imported.shape)
            else:
                imported = read_step_input(path)
                analysis = describe_holes(imported)
        result.update(analysis, length_unit=imported.unit, metrics=asdict(imported.metrics))
        if preview:
            from research_notes.diagnostic_workspace import shape_snapshot
            try:
                result['preview'] = shape_snapshot(imported.shape)
            except (CadAPIError, ValueError, RuntimeError) as error:
                result['preview_reason'] = '3D表示を省略しました。測定結果は保持しています。 '+str(error)
    except (ValueError, RuntimeError, OSError) as error:
        result.update(status="rejected", reason=str(error), hole_count=None, holes=[])
    _inventory_rows(result)
    json.dumps(result, allow_nan=False)
    return result


CSV_FIELDS = ('record_type', 'file_name', 'source_sha256', 'result_status', 'hole_count', 'hole_id',
              'hole_type', 'diameter_mm', 'center_x_mm', 'center_y_mm', 'entry_z_mm', 'depth_mm',
              'axis_x', 'axis_y', 'axis_z', 'unit', 'reason', 'recognized_hole_count', 'solid_index',
              'feature_type', 'width_mm', 'length_mm', 'long_axis_x', 'long_axis_y', 'long_axis_z',
              'recognized_circular_hole_count', 'recognized_slot_count', 'inventory_version')


def inventory_csv(result):
    """Always include a summary; unknown counts never become a zero-hole list."""
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, CSV_FIELDS, lineterminator='\n')
    writer.writeheader()
    common = {"file_name": result['file_name'], "source_sha256": result['source_sha256'],
              "result_status": result['status'], "hole_count": result['hole_count'], "unit": result['length_unit'],
              "recognized_hole_count":result.get('recognized_hole_count',result['hole_count']),
              "recognized_circular_hole_count":result.get('recognized_circular_hole_count'),
              "recognized_slot_count":result.get('recognized_slot_count'),
              "inventory_version":result.get('inventory_version', VERSION)}
    # Neutralize spreadsheet formula prefixes in user-supplied names/reasons.
    safe = lambda value: "'"+value if isinstance(value, str) and (value.lstrip().startswith(('=', '+', '-', '@')) or value.startswith(('\t', '\r', '\n'))) else value
    def write(row):
        writer.writerow({key: safe(value) for key, value in row.items()})
    write({**common, 'record_type': 'summary', 'reason': result['reason']})
    for hole in result['holes']:
        write({**common, 'record_type': 'hole', 'hole_id': hole['id'], 'hole_type': hole['kind'],
               'diameter_mm': hole['diameter_mm'], 'center_x_mm': hole['x_mm'], 'center_y_mm': hole['y_mm'],
               'entry_z_mm': hole['entry_z_mm'], 'depth_mm': hole['depth_mm'],
               'solid_index':hole.get('solid_index',1),
               'feature_type':hole.get('feature_type','circular_hole'),
               'width_mm':hole.get('width_mm'), 'length_mm':hole.get('length_mm'),
               **dict(zip(('long_axis_x','long_axis_y','long_axis_z'),hole.get('longitudinal_direction') or (None,)*3)),
               **dict(zip(('axis_x', 'axis_y', 'axis_z'), hole['axis']))})
    return buffer.getvalue().encode('utf-8-sig')


def inventory_svg(result):
    """Reuse the measured, server-side projection for a numbered publication figure."""
    if not result['preview']:
        from html import escape
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 440"><rect width="760" height="440" fill="#f6fafb"/><text x="30" y="100" font-family="sans-serif" font-size="24">'+escape(STATUS_LABELS[result['status']])+' · hole count unknown</text></svg>'
    from research_notes.revision_report import preview_svgs, camera_values
    data = result['preview']
    statuses = {str(face['index']): 'unchanged' for face in data['faces']}
    for hole in result['holes']:
        statuses.update({str(face): 'changed' for face in hole['faces']})
    markers = [{'position': [h['x_mm'], h['y_mm'], h['entry_z_mm']], 'label': h['id'], 'status': 'changed'} for h in result['holes']]
    state = {'old': data, 'new': data, 'analysis': {'face_status': {'old': statuses, 'new': statuses}, 'markers': {'old': markers, 'new': markers}}}
    return preview_svgs(state, camera_values({}))['old']


class HoleInventory:
    def __init__(self):
        self.result = None
        self.revision_token = secrets.token_urlsafe(24)

    def state(self):
        return {'inventory_version': VERSION, 'revision_token': self.revision_token, 'result': self.result}

    def guard(self, token):
        if token != self.revision_token:
            raise CadAPIError('revision_conflict', '別の画面で穴一覧が変わりました。最新の状態を確認してください。')

    def open_bytes(self, source, name, token):
        self.guard(token)
        result = analyze_step(source, name, inspection=True)
        self.result, self.revision_token = result, secrets.token_urlsafe(24)
        return {'status': result['status']}

    def action(self, operation, payload):
        self.guard(payload.get('revision_token'))
        if operation == 'csv':
            if not self.result:
                raise CadAPIError('no_source', 'STEPを開いてください。')
            return inventory_csv(self.result)
        if operation == 'demo':
            from research_notes.revision_detection import plate_shape
            from research_notes.step_writer_modes import prepare_step_write
            shape = plate_shape([0., 0., 0.], [12., 10., 4.], [{'x': x, 'y': y, 'radius': r} for x, y, r in ((3., 3., .6), (6., 5., 1.), (9., 7., 1.25))])
            source, _ = prepare_step_write(source=None, mode='reconstruct', shape=shape)
            return self.open_bytes(source, 'three-holes.step', self.revision_token)
        raise CadAPIError('invalid_request', 'Unknown hole inventory operation')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('step', type=Path)
    parser.add_argument('--output-dir', type=Path, default=Path('output/hole-inventory'))
    parser.add_argument('--public', action='store_true', help='use inspection intake and local circular-hole/straight-slot verification')
    parser.add_argument('--circular-only', action='store_true', help='disable slots for the earlier circular-only measurement scope')
    args = parser.parse_args(argv)
    with args.step.open('rb') as stream:
        source = stream.read(MAX_SOURCE_BYTES+1)
    result = analyze_step(source, args.step.name, inspection=args.public, include_slots=not args.circular_only)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir/'holes.csv').write_bytes(inventory_csv(result))
    (args.output_dir/'inventory.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    svg = inventory_svg(result)
    if svg:
        (args.output_dir/'holes.svg').write_text(svg, encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('status', 'hole_count', 'recognized_hole_count', 'recognized_circular_hole_count', 'recognized_slot_count', 'reason')}, ensure_ascii=False))
    return 0 if result['status'] == 'complete' else 2


if __name__ == '__main__':
    raise SystemExit(main())
