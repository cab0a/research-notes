"""Explain qualified-inventory abstention without inventing feature identities.

Reason codes describe failed checks, not inferred manufacturing feature types.
Unknown native errors use a generic fallback and retain their original detail.
The inventory and its completeness certificate are never modified here.
"""
from __future__ import annotations

import csv
import io

SCHEMA_VERSION = '1.0.0'
CATEGORIES = {
    'input': '入力・読込条件', 'precision': '精度・許容差',
    'scope': '認識条件の範囲', 'geometry': '形状証拠の不一致',
    'processing': '処理の失敗', 'coverage': '全体確認の保留', 'display': '表示の制限',
}

# category, title, explanation, next action. None of these certify a hole type.
CATALOG = {
    'whole_count_unknown': ('coverage', '全体の穴数は未確定です',
        '取得した行は、条件を満たして確認できた穴だけです。未対応形状や見逃しの有無は確定していません。',
        '元CADや図面で部品全体を確認し、取得した一覧と照合してください。'),
    'no_qualified_features': ('coverage', '認識条件を満たす穴を確認できませんでした',
        '取得0件は、この方法で穴を確定できなかった結果です。部品に穴がないことを示しません。',
        '元CADで穴の有無・形状を確認し、今回の丸穴・直線状貫通長孔の対応条件と照合してください。'),
    'circular_only_scope': ('coverage', '長孔の認識は実行していません',
        '丸穴のみを調べる設定です。長孔の有無は、この実行結果から判断できません。',
        '長孔も必要な場合は、丸穴・長孔の統合検証を有効にして再実行してください。'),
    'input_parse_failed': ('input', 'STEPの構文・読込前の条件を確認できません',
        '読込前の検査を通過していないため、穴の解析は完了していません。',
        'ファイルが途中で切れていないか確認し、元CADからSTEPを再出力してください。技術詳細も確認してください。'),
    'input_units': ('input', '長さ単位の条件を確認できません',
        '単位定義が欠けているか、対応する単位・変換条件を満たしていません。寸法を推測していません。',
        '元CADのSTEP出力設定で長さ単位と単位コンテキストを確認してください。'),
    'external_reference': ('input', '外部参照を含むSTEPは対象外です',
        '別ファイルへの参照を取得していないため、この入力を解析していません。',
        '必要な形状を含む単独のSTEPとして出力できるか、データ提供元に確認してください。'),
    'input_limit': ('input', '読込・走査の上限を超えています',
        'ファイル容量、ルート数、面数などの上限により、必要な処理を完了していません。',
        '技術詳細にある上限を確認し、必要な部品を分けた分析用STEPで再実行してください。'),
    'input_io': ('input', 'ファイルを読み書きできませんでした',
        'ファイル処理のエラーがあり、今回の解析を完了していません。',
        'ファイルの存在、アクセス権、保存先を確認してください。'),
    'native_import_failed': ('input', '形状の読込・転送を完了できません',
        'STEPから必要な有効形状を取得できませんでした。取得0件を穴なしとは扱いません。',
        '元CADでSTEPが開けるか確認し、必要なソリッドを含めて再出力してください。'),
    'input_unclassified': ('input', '読込処理を完了できませんでした',
        'このエラーの原因を自動で詳しく分類できていません。元のメッセージを技術詳細に残しています。',
        '元CADで入力を確認し、技術詳細と入力条件を照合してください。'),
    'invalid_solid': ('scope', '有効なソリッドの条件を確認できません',
        '穴の局所検証に必要な有効なソリッドを確認できていません。',
        '元CADでソリッドの状態を確認してください。シェルや開いた形状は同じ条件では扱えません。'),
    'ownership_unconfirmed': ('geometry', '面の所属を一意に確認できません',
        '開口と内壁が同じ一つの部品に属するという条件を確認できていません。',
        '該当面の接続と部品構成を元CADで確認してください。'),
    'tolerance_exceeded': ('precision', '形状の許容差が認識条件を超えています',
        'B-Repが持つ許容差が検証上限を超えています。加工公差や部品不良の判定ではありません。',
        'STEP出力精度と該当面・辺・頂点の状態を確認してください。元データの精度を確かめずに許容差を広げないでください。'),
    'feature_too_small': ('precision', '寸法が判定許容差に近すぎます',
        '半径・深さ・辺の長さなどが小さく、安全に確定する条件を満たしていません。',
        '長さ単位と実際の寸法を元CADで確認し、技術詳細の寸法下限と照合してください。'),
    'coordinate_resolution': ('precision', '座標の桁精度が判定条件に足りません',
        '浮動小数点の座標間隔が材料判定の上限を超えています。内部の平行移動だけでは失われた桁を回復できません。',
        '必要なら、部品の近くを原点にした分析用コピーを元CADから出力し、座標変換を別途記録してください。'),
    'circular_span': ('scope', '円筒が一周する条件を確認できません',
        '円筒の角度範囲が通常の丸い貫通穴の条件を満たしていません。長孔の一部・切欠き・面分割などとの区別は未確定です。',
        '該当する円筒面の角度範囲、分割、切欠きとSTEP出力精度を確認してください。'),
    'opening_pair': ('scope', '両端の開口を確認できません',
        '必要な二つの平面開口と内壁の対応を確認できません。止まり穴や段付き穴と断定した結果ではありません。',
        '穴の入口・出口・底・段差を元CADで確認してください。'),
    'shoulder_ambiguity': ('scope', '段差を含む開口との区別を保留しています',
        '開口の外周や周囲の壁が、単純な貫通穴として確定する条件を満たしていません。',
        '開口付近の段差・ポケット・外周形状を元CADで確認してください。'),
    'slot_boundary': ('scope', '直線状長孔の境界条件を確認できません',
        '半円二つと直線二つからなる、分割のない長孔の開口条件を満たしていません。',
        '半円の角度、端部の半径、直線部分、面・辺の分割とSTEP出力精度を確認してください。'),
    'opening_boundary_unqualified': ('scope', '対応する開口の境界を確認できません',
        '平面の内周を観測しましたが、円形として確認できず、直線状長孔の四つの辺の条件も満たしていません。穴の種類や穴数は断定していません。',
        '該当する平面の内周形状を元CADで確認し、丸穴・直線状貫通長孔の対応条件と照合してください。'),
    'slot_tangency': ('geometry', '長孔の端部と直線の接続を確認できません',
        '端部の向き、接続点、平行性や接線条件が一致していません。',
        '該当する開口の辺と端部を元CADで確認してください。'),
    'topology_unconfirmed': ('geometry', '開口と内壁の接続を確認できません',
        '辺の共有や内壁の数、分割・追加境界が認識条件を満たしていません。',
        '該当面・辺の接続、交差、切欠き、分割を元CADで確認してください。'),
    'axis_mismatch': ('geometry', '開口と穴の方向が一致していません',
        '開口平面・穴の軸・長孔の長手方向などの関係を確認できません。',
        '該当する開口の方向と通路の直進性を元CADで確認してください。'),
    'support_mismatch': ('geometry', '内壁と開口の形状が一致していません',
        '支持面、径、位置、開口寸法などが同じ通路の条件として一致していません。',
        '該当面の径・位置・形状と、入口と出口の寸法を元CADで照合してください。'),
    'area_mismatch': ('geometry', '内壁の面積が認識条件と一致していません',
        '通常の通路として計算した面積と一致せず、切欠き・追加境界などを除外できません。',
        '該当する内壁の切欠き、交差穴、追加境界と出力精度を確認してください。'),
    'material_unconfirmed': ('geometry', '材料と空間の区別を確認できません',
        '穴の内側・壁の外側・両端で必要な材料状態を確認できていません。通路のふさがりと数値判定の不確定さを区別して断定していません。',
        '該当通路と内壁を元CADで確認し、必要に応じて技術詳細の材料判定条件を調べてください。'),
    'geometry_unclassified': ('geometry', '形状の判定理由を詳しく分類できません',
        '認識を保留しました。原因を推測せず、元のメッセージを技術詳細に残しています。',
        '該当面と元のメッセージを確認し、人が形状を判断してください。'),
    'processing_failed': ('processing', '幾何処理を完了できませんでした',
        '処理中のエラーがあり、この検証は完了していません。確認済みの別の穴は保持しています。',
        '元CADで入力を確認してください。再現する場合は、入力条件と技術詳細を記録してください。'),
    'preview_unavailable': ('display', '3D表示を省略しています',
        'プレビューの条件または処理を満たせませんでした。取得済みの測定結果は保持しています。',
        '穴一覧・CSVを確認し、形状の見た目は元CADなどで確認してください。'),
}

# Exact aliases for existing check messages; unknown messages stay unclassified.
# QualificationError captures the code at the failed-check boundary.
ALIASES = {
    'invalid_solid': ['円形穴の検証には有効なソリッドB-Repが必要です。', 'A valid solid B-Rep is required.'],
    'input_limit': ['円形穴の検証は最大512面です。', 'Slot qualification requires 1..512 faces.',
                    'STEP inspection byte budget exceeded', 'STEP root budget exceeded',
                    'STEP topology/solid budget exceeded', 'STEP exceeds the 2000000-byte input limit'],
    'ownership_unconfirmed': ['単一ソリッドに属する円筒面ではありません。', 'Opening face must belong to exactly one solid.', 'Walls/openings have different solid owners.'],
    'support_mismatch': ['内向きの円筒面を確認できません。', '円筒面と開口円の位置・径が一致しません。',
        'Opening size or direction differs.', 'The two openings are not a straight translation.',
        'End wall is not an inward semicylinder of matching radius.', 'Cylinder support does not match its opening arc.', 'Straight side must be planar.'],
    'tolerance_exceeded': ['円筒面・境界の許容差が検証許容差を超えています。', '円筒面・開口面・辺・頂点の許容差が検証許容差を超えています。',
                           'Face/edge/vertex tolerance exceeds the qualification tolerance.'],
    'feature_too_small': ['半径または深さが検証許容差に近すぎます。', 'Length is too close to the qualification tolerance.'],
    'coordinate_resolution': ['World-coordinate resolution is too coarse for the material qualification tolerance.'],
    'circular_span': ['円筒が一周していません。長穴・切欠き・面分割などを保留します。'],
    'opening_pair': ['両端の平面にある完全な円形の内周を確認できません。止まり穴・段付き穴などを保留します。',
                     'Two matching inner openings were not found; blind/stepped/trimmed slots abstain.'],
    'shoulder_ambiguity': ['円形外周の開口面は段付き穴の内部段差と区別せず保留します。ワッシャー等も対象外です。',
        '開口面が周囲の壁より奥にあります。段付き穴・ポケット内の穴として保留します。',
        'Curved outer opening boundary: stepped-slot ambiguity is withheld.',
        'Opening is surrounded by outward-rising walls: recessed shoulder is withheld.'],
    'slot_boundary': ['Opening must have exactly four unsplit edges.', 'Arc is not a semicircle.',
        'Opening contains a non-circular/non-linear edge.', 'Opening needs two semicircles and two straight sides.',
        'Semicircle radii differ or are too small.'],
    'slot_tangency': ['Semicircles must face away from each other.', 'Straight sides are not parallel tangents of the required length.',
        'Ambiguous or disconnected endpoints.', 'Straight side is not tangent to its arc.', 'Side does not connect the two ends.'],
    'topology_unconfirmed': ['Non-manifold opening edges.', 'Opening must adjoin four distinct walls.',
        'A wall has splits, holes or extra trimming.', 'Wall must connect one edge at each opening.',
        'Wall sides do not form an unbroken straight passage.'],
    'axis_mismatch': ['開口間の方向が円筒軸と一致しません。', '開口平面が円筒軸に直交しません。',
                      'Long axis is not perpendicular to passage.', 'Opening plane is not perpendicular to passage.'],
    'area_mismatch': ['円筒面の面積に切欠き・追加境界があります。', 'Wall area differs from the untrimmed capsule passage.'],
    'material_unconfirmed': ['穴内部に材料または不確定な境界があります。', '円筒壁の内外の材料状態を確認できません。',
        '両端の開口を確認できません。', 'Wall material/void samples do not match a cavity.', 'Passage or opening is obstructed.'],
    'processing_failed': ['Could not translate the private material classification solid.',
        'Material classification requires a positive finite tolerance.', 'Material classification requires finite solid bounds.',
        'Material sample coordinates must be finite XYZ values.'],
    'external_reference': ['external STEP references are unsupported; no retrieval is performed'],
    'native_import_failed': ['native STEP reader rejected input', 'partial native root transfer', 'STEP transfer produced no geometry',
        'inspection requires a valid nonempty face-bearing shape', 'STEP reader rejected the input',
        'only a single STEP root is supported', 'STEP transfer produced no shape',
        'input must be one valid solid with one shell and at most 24 faces'],
    'input_units': ['no explicit length unit', 'unit requires a local entity reference', 'missing unit reference',
        'numeric unit value required', 'finite unit value required', 'cyclic or excessive unit conversion chain',
        'conversion base is not a length unit', 'malformed named unit', 'unit dimensional exponents are not length',
        'unsupported SI length unit', 'unsupported SI length prefix', 'conversion unit requires explicit length dimensions',
        'malformed length conversion factor', 'conversion requires a typed length measure',
        'positive unit conversion factor required', 'unsupported length unit form', 'unit scale outside inspection bounds',
        'malformed unit context', 'each representation context must reference exactly one length unit',
        'every shape representation must use a qualified length context', 'mixed length scales are outside the inspection contract',
        'exactly one explicit SI millimetre length unit is required', 'only explicit SI millimetre inputs are supported',
        'exactly one global unit context is required', 'the representation context must reference the millimetre length unit',
        'shape representations must use the qualified millimetre context'],
}
MESSAGE_CODES = {message: code for code, messages in ALIASES.items() for message in messages}
PARSER_LIMIT_CODES = {'file_size_limit', 'token_length_limit', 'token_count_limit',
                      'entity_count_limit', 'reference_count_limit', 'nesting_depth_limit',
                      'reference_conversion_limit', 'number_conversion_limit'}


class QualificationError(ValueError):
    def __init__(self, code, detail):
        super().__init__(detail)
        self.reason_code = code


def qualification_error(message):
    return QualificationError(MESSAGE_CODES.get(message, 'geometry_unclassified'), message)


def error_code(error, *, intake=False):
    if isinstance(error, QualificationError):
        return error.reason_code
    text = str(error)
    if text in MESSAGE_CODES:
        return MESSAGE_CODES[text]
    if intake:
        if isinstance(error, OSError):
            return 'input_io'
        if text.startswith('STEP inspection preflight:'):
            if text.split(':', 1)[1].strip() in PARSER_LIMIT_CODES | {
                    'byte_budget', 'estimated_memory_budget', 'time_budget'}:
                return 'input_limit'
            return 'input_parse_failed'
        if text.startswith('ambiguous or missing unit record:'):
            return 'input_units'
        # The strict importer exposes its parser exception directly.
        from research_notes.step_part21 import Part21ParseError
        if isinstance(error, Part21ParseError):
            return 'input_limit' if error.reason_code in PARSER_LIMIT_CODES else 'input_parse_failed'
        return 'processing_failed' if isinstance(error, RuntimeError) else 'input_unclassified'
    return 'processing_failed' if isinstance(error, RuntimeError) else 'geometry_unclassified'


def _item(code, scope, raw='', *, faces=(), edges=(), severity='review'):
    code = code if code in CATALOG else 'geometry_unclassified'
    category, title, explanation, action = CATALOG[code]
    return {'code': code, 'category': category, 'category_label': CATEGORIES[category],
            'scope': scope, 'severity': severity, 'title': title, 'explanation': explanation,
            'next_action': action, 'face_indices': sorted(set(faces)), 'edge_indices': sorted(set(edges)),
            'raw_reason': raw}


def attach_review(result, failure=None):
    """Add explanations after recognition and preview, keeping every raw observation.

    Items are check observations, never additional holes or a complete feature
    census. One real opening can cause multiple observations on different faces.
    """
    items = []
    if result['status'] == 'rejected':
        items.append(_item(error_code(failure or ValueError(result['reason']), intake=True),
                           'input', result['reason']))
    elif result['hole_count'] is None:
        items.append(_item('whole_count_unknown', 'whole_part', result.get('whole_part_reason', result['reason'])))
        if not result['holes']:
            items.append(_item('no_qualified_features', 'whole_part'))
        for row in result.get('withheld_cylinders', []):
            items.append(_item(row.get('reason_code', 'geometry_unclassified'), 'circular_candidate',
                               row['reason'], faces=[row['face_index']]))
        slot_scan = result.get('slot_scan', {})
        if slot_scan.get('status') == 'unresolved' and 'withheld_candidates' not in slot_scan:
            items.append(_item(slot_scan.get('reason_code', 'processing_failed'), 'slot_scan', slot_scan['reason']))
        for row in slot_scan.get('withheld_candidates', []):
            faces = [*row.get('wall_faces', []), *row.get('opening_faces', [])]
            if 'opening_face' in row:
                faces.append(row['opening_face'])
            items.append(_item(row.get('reason_code', 'geometry_unclassified'), 'slot_candidate',
                               row['reason'], faces=faces, edges=row.get('opening_edges', [])))
        # Single-edge non-circular wires are skipped by the slot scanner. Keep
        # the observed boundary without inventing an ellipse/other hole type.
        for row in result.get('noncircular_planar_inner_wires', []):
            if row['edge_count'] == 1:
                items.append(_item('opening_boundary_unqualified', 'opening_observation',
                    '円形内周として確認できない、単一の辺からなる平面内周を観測しました。',
                    faces=[row['plane_face']]))
    if result.get('feature_scope') == 'circular_only' and result.get('analysis_mode') == 'public_inspection':
        items.append(_item('circular_only_scope', 'settings', severity='notice'))
    if result.get('preview_reason'):
        items.append(_item('preview_unavailable', 'preview', result['preview_reason'], severity='notice'))
    for i, item in enumerate(items, 1):
        item['id'] = f'R{i}'
    count = result['hole_count']
    state = 'unknown' if count is None else 'certified_zero' if count == 0 else 'certified_count'
    headline = ('読込を完了できませんでした。穴の有無は未判定です。' if result['status'] == 'rejected' else
                '認識条件を満たす穴を確認できませんでした。穴がないという判定ではありません。' if count is None and not result['holes'] else
                f"確認できた穴は{len(result['holes'])}か所です。全体の穴数は未確定です。" if count is None else
                f'対応範囲内で穴{count}か所を確認しました。')
    groups = [{'category': key, 'label': label, 'item_count': sum(i['category'] == key for i in items)}
              for key, label in CATEGORIES.items() if any(i['category'] == key for i in items)]
    result['review_schema_version'] = SCHEMA_VERSION
    result['review_items'] = items
    result['review_summary'] = {'count_state': state, 'headline': headline, 'item_count': len(items),
                                'candidate_observation_count': sum(i['scope'] in {'circular_candidate', 'slot_candidate'} for i in items),
                                'manual_review_required': any(i['severity'] == 'review' for i in items),
                                'groups': groups,
                                'item_count_policy': '説明件数は検査の記録数です。同じ開口から複数の記録が生じる場合があり、未取得の穴数や全体の穴数を示しません。'}


REVIEW_FIELDS = ('record_type', 'file_name', 'source_sha256', 'inventory_version', 'review_schema_version',
                 'result_status', 'hole_count', 'recognized_hole_count', 'count_state', 'review_item_count',
                 'review_id', 'reason_code', 'category', 'scope', 'severity', 'title', 'explanation',
                 'next_action', 'face_indices', 'edge_indices', 'raw_reason')


def review_csv(result):
    """Separate summary and check observations; never insert them in holes.csv."""
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, REVIEW_FIELDS, lineterminator='\n')
    writer.writeheader()
    common = {k: result.get(k) for k in ('file_name', 'source_sha256', 'inventory_version', 'review_schema_version',
                                       'hole_count', 'recognized_hole_count')}
    common.update(result_status=result['status'], count_state=result['review_summary']['count_state'],
                  review_item_count=len(result['review_items']))
    def write(row):
        writer.writerow({k: "'"+v if isinstance(v, str) and (v.lstrip().startswith(('=', '+', '-', '@'))
                         or v.startswith(('\t', '\r', '\n'))) else v for k, v in row.items()})
    write({**common, 'record_type': 'summary', 'explanation': result['review_summary']['headline']})
    for item in result['review_items']:
        write({**common, 'record_type': 'review', 'review_id': item['id'], 'reason_code': item['code'],
               **{k: item[k] for k in ('category', 'scope', 'severity', 'title', 'explanation', 'next_action', 'raw_reason')},
               'face_indices': ' '.join(map(str, item['face_indices'])),
               'edge_indices': ' '.join(map(str, item['edge_indices']))})
    return stream.getvalue().encode('utf-8-sig')
