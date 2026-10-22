"""Offline development observations; explicitly no automated-test claim."""
from pathlib import Path
from html import escape
import json
from .drawing_dimension_report import CSS,JS,table
from .drawing_family_report import crops,overlay
from .cad_svg_report import safe_json
LABELS={'pocket_through':'ポケットの底を貫通する穴','blind_z':'上面の平底止まり穴','counterbore':'段付き貫通穴（座ぐり）',
    'side_blind':'側面の平底止まり穴','side_through':'側面の貫通穴','chain_quantity':'連鎖寸法＋同径2穴',
    'toleranced_bore':'公差付き寸法＋止まり穴','missing_depth':'深さの指示がない穴','wrong_quantity':'数量指示と穴数が矛盾','unsupported_fit':'未対応のはめあい記号'}
REASONS={'direction_ambiguous':'複数の加工方向が同じ輪郭を説明します。線種や断面など、開口方向を決める情報を確認してください。',
    'hole_extent_ambiguous':'貫通指示または深さが不足しています。図の見た目から深さを補っていません。',
    'quantity_conflict':'数量指示と同径の円の数が一致しません。指示がどの穴群を対象とするか確認してください。',
    'unsupported_annotation':'今回対応していない注記です。はめあい等を任意の数値公差に置き換えていません。',
    'dimension_label_ambiguous':'寸法線と文字の対応を確定できません。図面の文字位置を確認してください。',
    'projection_conflict':'候補形状の投影と図面が一致しません。対象形状・寸法・線種を確認してください。'}
NAMES={'width':'板幅','length':'板奥行','thickness':'板厚','kind':'種類','axis':'穴軸','u':'位置u','v':'位置v','x':'X位置','y':'Y位置',
    'diameter':'穴径','depth':'深さ','extent':'貫通／止まり','entry':'進入側','opening':'開口','counter_diameter':'座ぐり径','counter_depth':'座ぐり深さ'}
def flat(p):
    r={NAMES[k]:p[k] for k in ('width','length','thickness')}
    for i,f in enumerate(p['features']):
        for k in ('kind','axis','x','y','u','v','width','length','diameter','depth','extent','counter_diameter','counter_depth','entry','opening'):
            if k in f:r[f'加工{i+1} / '+({'width':'幅','length':'奥行'}.get(k,NAMES.get(k,k)))]=f[k]
    return r
def write_report(directory):
    result=json.loads((directory/'results.json').read_text());parts=[];meshes={};pictures={}
    for o in result['observations']:
        key=o['id'];folder=directory/key;inf=json.loads((folder/'inference.json').read_text());source=(folder/'input.svg').read_bytes()
        pictures[key]=crops(source,inf,o['format']);label=LABELS.get(o['part'],o['part'])+' / '+o['format'].upper()
        category='candidate' if o.get('observed_agreement') else 'withheld' if o['status']=='withheld' else 'failed'
        state={'candidate':'今回の実行例で一致','withheld':'保留','failed':'不一致・処理失敗'}[category]
        panel=f'''<section class="panel"><h3>入力図面</h3><div class="toolbar"><label>表示 <select class="view-select"><option value="all">三面図全体</option><option value="top">平面図</option><option value="front">正面図</option><option value="right">右側面図</option></select></label><button class="image-minus">縮小</button><button class="image-plus">拡大</button><span class="image-scale">100%</span></div><div class="drawing-window"><img class="drawing" src="{pictures[key]['all']}" alt="{escape(label)}の図面"></div><p class="caption">{'解析入力はDXF。表示用SVGは同じ作者ページの出力で、復元へは渡していません。' if o['format']=='dxf' else '解析に使ったSVG。表示範囲の切替で三面を確認できます。'}</p></section>'''
        body=''
        if (folder/'preview.json').exists():
            meshes[key]=json.loads((folder/'preview.json').read_text());c=json.loads((folder/'comparison.json').read_text())
            preview='''<section class="panel"><h3>生成した3D CAD</h3><div class="toolbar"><label>モデル <select class="model-select"><option value="original">復元したモデル</option><option value="edited">寸法変更後</option></select></label><button class="reset-camera">視点リセット</button><button class="zoom-out">−</button><button class="zoom-in">＋</button></div><canvas class="preview" width="700" height="420" tabindex="0" aria-label="回転可能な3Dプレビュー"></canvas><p class="caption">ドラッグで回転、ホイールで拡大縮小。側面の穴は回転して確認できます。変更後も視点を保持します。</p></section>'''
            p,t,e=map(flat,(c['parameters'],c['truth_parameters'],c['edited_parameters']))
            body+='<h3>取得した設計パラメータと変更後（mm）</h3><p>Z軸の穴はu=X・v=Y、X軸の穴はu=Y・v=Z。positiveは軸の正側、negativeは負側の面から加工する意味です。公称寸法で形状を生成し、公差は次の表に別途保存しています。</p>'
            body+=table(['項目','作者側の正解','図面から取得','変更後'],[[k,v,p.get(k,'—'),e.get(k,'—')] for k,v in t.items()])
            m,em=c['metrics'],c['edit_metrics']
            body+=table(['この実行例の観測','結果'],[['有効な単一ソリッド / STEP再読込',str(m['valid_solid'])+' / '+str(m['step_read_success'])],
                ['元形状 / 変更後の体積IoU',f'{m["same_kernel_iou"]:.12g} / {em["same_kernel_iou"]:.12g}'],['元形状の外形差 mm',f'{m["bounds_error_mm"]:.6g}'],
                ['解析体積との差 mm³',f'{m["volume_error_mm3"]:.6g}'],['解析面積との差 mm²',f'{m["area_error_mm2"]:.6g}']])
            body+='<h3>入力輪郭と再投影</h3><p class="caption">灰色：図面、青色：復元B-Repの投影。曲線はサンプルによる比較です。</p>'+overlay(inf['raw_views'],inf['reprojection'])
            body+='<nav class="downloads">'+''.join(f'<a href="{key}/{name}" download>{title}</a>' for name,title in
                (('candidate.step','復元STEP'),('edited.step','変更後STEP'),('candidate.py','編集用Python'),('model.json','公差・根拠を含むモデルJSON')) )+'</nav>'
        else:
            reason=inf.get('reason_code','failed');preview=f'<section class="panel withheld-panel"><h3>CAD生成を保留しました</h3><p>{escape(REASONS.get(reason,"根拠JSONの理由と元図面を確認してください。"))}</p><code>{escape(reason)}</code><p>{escape(inf.get("detail") or o.get("detail") or "")}</p><p>正解CADを代わりに表示していません。</p></section>'
        if inf.get('tolerances'):
            body+='<h3>公称寸法と数値公差（元図面）</h3><p>公差は設計条件として保存します。形状誤差の許容値に流用せず、はめあい・公差積上げ・製造合否は判定しません。編集後に適切な公差かどうかは別途確認が必要です。</p>'+table(
                ['図面の文字','公称 mm','下側偏差 mm','上側偏差 mm','元寸法ID'],[[t['source_text'],t['nominal_mm'],t['deviations_mm']['lower'],t['deviations_mm']['upper'],t['dimension_id']] for t in inf['tolerances']])
        if inf.get('bindings'):
            dims={d['id']:d for d in inf['evidence']['dimensions']}
            body+='<details><summary>寸法・数量・連鎖の根拠</summary>'+table(['設計項目','使用した寸法ID','図面にある記載'],[[k,' → '.join(ids),' → '.join(dims[i]['text'] for i in ids if i in dims)] for k,ids in inf['bindings'].items()])+'</details>'
        if inf.get('direction_alternatives'):
            body+='<details><summary>加工方向の候補</summary>'+table(['正側から加工するか（候補順）','輪郭・線種と整合'],[[a['positive_entries'],a['compatible']] for a in inf['direction_alternatives']])+'</details>'
        body+=f'<details><summary>入力条件・記録</summary><p>人が指定：mm、第三角法、3ビューの対応、今回の加工形状の範囲。値は図面から取得し、作者側のSTEPと寸法は評価だけで使用します。</p><p class="digest">SHA-256: {inf["source_sha256"]}</p><a href="{key}/input.{o["format"]}">元入力</a> · <a href="{key}/context.json">入力条件</a> · <a href="{key}/inference.json">解釈JSON</a></details>'
        parts.append(f'<article class="case" data-case="{key}" data-category="{category}"><div class="case-head"><div><span class="case-id">{key}</span><h2>{escape(label)}</h2></div><span class="badge {category}">{state}</span></div><div class="stage-grid">{panel}{preview}</div>{body}</article>')
    s=result['summary'];stats=''.join(f'<div class="stat"><span>{text}</span><strong>{n}</strong></div>' for text,n in (
        ('開発入力の実行例',s['inputs']),('復元・編集が正解と一致',s['agreement']),('理由付き保留',s['withheld'])))
    doc='''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>交差形状・穴の種類・寸法表記の拡張</title><style>'''+CSS+'''</style></head><body><main><header><p class="eyebrow">RESEARCH NOTES · 開発例の実行記録</p><h1>交差形状・穴の種類・寸法表記の拡張</h1><p>ポケットの底を貫通する穴、平底の止まり穴、段付き貫通穴、側面穴を追加しました。連鎖寸法・数量・数値公差の読み取りも実装しています。</p><p class="scope">依頼に従いテストの追加・実行はしていません。このページは自作FreeCAD図面を使った開発中の復元実験です。未調整図面での精度・回帰テスト通過・一般的な対応を示すものではありません。</p></header><div class="stats">'''+stats+'''</div><section class="selection"><label>結果 <select id="filter"><option value="all">すべて</option><option value="candidate">今回の例で一致</option><option value="withheld">保留</option><option value="failed">不一致・処理失敗</option></select></label><label class="case-picker">確認する例 <select id="case-picker"><option value="pocket_through_svg">ポケットの底を貫通する穴</option></select></label><span id="case-count" aria-live="polite"></span></section><p id="empty" hidden>この分類の結果はありません。</p>'''+''.join(parts)+'''<footer><h2>今回の範囲</h2><p>交差形状は矩形ポケット内に完全に収まるZ方向の貫通穴に限定しています。止まり穴は平底、段付き穴は同心の貫通穴＋1段の座ぐり、側面穴は実行例ではX方向です。穴同士の交差、ポケット壁への食い込み、斜め穴、ドリル先端の円錐、任意の段差・自由曲面は対象外です。</p><p>寸法公差は数値の±と上側／下側偏差だけを扱い、公称値とは分けて保存します。H7等のはめあい記号、幾何公差、公差積上げは未対応。連鎖寸法は正面・平面・側面の各軸上で基準へ接続された寸法経路に限定します。</p><p>DXFの線種不足は解消していません。ただし深さの記載と輪郭から候補が1つに絞れる穴は復元します。ポケットの上下方向など複数候補が残る場合は保留します。HTMLは保存結果の閲覧用で、再計算はCLIで行います。</p><p><a href="../../notes/drawing-machining.md">研究ノート</a> · <a href="../../docs/drawing-machining.md">再現・操作手順</a> · <a href="results.json">実行結果JSON</a> · <a href="summary.csv">一覧CSV</a></p></footer></main><script type="application/json" id="meshes">'''+safe_json(meshes)+'''</script><script type="application/json" id="pictures">'''+safe_json(pictures)+'''</script><script>'''+JS.replace('one_third','pocket_through_svg')+'''</script></body></html>'''
    (directory/'report.html').write_text(doc,encoding='utf-8')
if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('directory',type=Path);write_report(ap.parse_args().directory)
