"""Offline evidence viewer for exporter boundaries and frozen configuration holdout."""
from html import escape
from pathlib import Path
import json
from .drawing_dimension_report import CSS,JS,svg_data,table
from .drawing_family_report import crops,flat_params,overlay
from .cad_svg_report import safe_json
COHORTS={'development':'開発・曖昧さの対照','portability':'別CADの書き出し','holdout':'未調整の部品'}
FAMILIES={'plate':'穴付き板','l_bracket':'L字ブラケット','stepped_shaft':'段付き軸','pocket':'矩形ポケット'}
REASONS={
 'opening_ambiguous':'開口が上側か下側かを決める根拠が足りません。線種を保持した図面、または確認済みの断面を追加します。',
 'dimension_text_unavailable':'このLibreCAD出力には寸法文字がありませんでした。出力元DXFに存在する注記が、このSVGへ渡っていません。図面の出力方法から見直す必要があります。',
 'dimension_missing':'復元に必要な寸法を取得できませんでした。図面に値がない場合と、現在の読み取り処理が対応づけできない場合を、入力と詳細で確認します。',
 'dimension_conflict':'寸法とビューの対応を一意に決められません。数値を補完せず保留しました。',
 'dimension_label_ambiguous':'寸法文字と寸法線の対応候補が複数あり、現在の処理では一意に決められません。寸法がないのではなく、対応づけの限界です。',
 'visibility_section_conflict':'候補形状と可視線・隠れ線・断面が一致しません。図面と指定条件を人が確認します。'}
def write_report(directory):
    report=json.loads((directory/'results.json').read_text());meshes={};pictures={};parts=[]
    for o in report['observations']:
        key=o['id'];folder=directory/key;t=o['trials'][0]
        inf=json.loads((folder/'inference.json').read_text()) if (folder/'inference.json').exists() else t
        source=(folder/'input.svg').read_bytes();category=t['status']
        if category=='candidate' and not t['reconstructed_correctly']:category='failed'
        pics=crops(source,inf,o['format']) if o['cohort']!='portability' else dict.fromkeys(('all','front','top','right'),svg_data(source))
        pictures[key]=pics
        label=f"{COHORTS[o['cohort']]}：{o['part']} / {FAMILIES[o['family']]} / {o['format'].upper()}"
        if o.get('resolution'):label+=' / '+o['resolution']
        panel=f'''<section class="panel"><h3>入力図面</h3><div class="toolbar"><label>表示 <select class="view-select"><option value="all">図面全体</option><option value="front">正面</option><option value="top">平面</option><option value="right">右側面</option></select></label><button class="image-minus">縮小</button><button class="image-plus">拡大</button><span class="image-scale">100%</span></div><div class="drawing-window"><img class="drawing" alt="{escape(label)}の入力図面" src="{pics['all']}"></div><p class="caption">{'表示専用の同一ページSVG。復元に渡したのはDXFです。' if o['format']=='dxf' else '復元に入力したSVGそのものです。'}{' 全実線化した派生対照です。' if o.get('derived_style') else ''}</p></section>'''
        body=''
        if (folder/'preview.json').exists():
            meshes[key]=json.loads((folder/'preview.json').read_text())
            preview='''<section class="panel"><h3>STEPから再読込した3D</h3><div class="toolbar"><label>モデル <select class="model-select"><option value="original">復元したモデル</option><option value="edited">寸法変更後</option></select></label><button class="reset-camera">視点リセット</button><button class="zoom-out">−</button><button class="zoom-in">＋</button></div><canvas class="preview" width="700" height="420" tabindex="0" aria-label="回転可能な3Dプレビュー"></canvas><p class="caption">右ドラッグで手前の面が右へ回ります。上下ドラッグで下面側も確認できます。ホイールで拡大縮小。表示は保存結果で、ここではCADを再計算しません。</p></section>'''
            c=json.loads((folder/'comparison.json').read_text());truth=flat_params(c['truth_parameters']);p=flat_params(c['parameters']);ep=flat_params(c['edited_parameters'])
            if inf.get('opening'):body+=f'<p class="edit-note">開口方向：<strong>{"上側" if inf["opening"]=="top" else "下側"}</strong>。{ "上面からの距離を深さとして使用" if inf["opening"]=="top" else "板厚から上面基準距離を引いて深さを算出" }。図面の上面基準距離 {inf["dimension_interpretation"]["top_reference_distance_mm"]} mm → 開口側からの深さ {inf["dimension_interpretation"]["actual_depth_mm"]} mm。</p>'
            body+='<h3>正解設計値との照合と寸法変更</h3>'+table(['寸法 mm','独立した正解','復元値','差','変更後'],[[k,v,p.get(k,'—'),p.get(k,v)-v,ep.get(k,'—')] for k,v in truth.items()])
            m,em=c['metrics'],c['edit_metrics']
            body+=table(['検査','復元時','寸法変更後'],[['有効な単一ソリッド / STEP再読込',m['valid_solid'] and m['step_read_success'],em['valid_solid'] and em['step_read_success']],
                ['体積IoU（同じOCCTで測定）',f'{m["same_kernel_iou"]:.12g}',f'{em["same_kernel_iou"]:.12g}'],
                ['外形の最大誤差 mm',f'{m["bounds_error_mm"]:.5g}',f'{em["bounds_error_mm"]:.5g}'],
                ['解析体積との差 mm³',f'{m["volume_error_mm3"]:.5g}',f'{em["volume_error_mm3"]:.5g}']])
            body+='<h3>入力輪郭とB-Rep再投影</h3><p class="caption">灰：入力、青：復元CAD。ここは全線の比較です。開口の判定には下記の可視線・隠れ線の区別も用います。</p>'+overlay(inf['raw_views'],inf['reprojection'])
            body+='<nav class="downloads">'+''.join(f'<a href="{key}/{name}" download>{label}</a>' for name,label in (('candidate.step','復元STEP'),('edited.step','変更後STEP'),('candidate.py','編集用Python'),('model.json','設計モデル')) )+'</nav>'
        else:
            reason=inf.get('reason_code',t.get('reason','failed'))
            preview=f'<section class="panel withheld-panel"><h3>CAD生成を保留</h3><p>{escape(REASONS.get(reason,"現在の対応範囲では復元できませんでした。入力と詳細を確認してください。"))}</p><code>{escape(reason or "failed")}</code><p>{escape(inf.get("detail") or "")}</p><p>正解値からの補完や、評価後の復元処理の調整はしていません。</p></section>'
        if 'section' in o:
            body+='<h3>追加した断面輪郭</h3><p>実CADのソリッドを切断して得た輪郭です。Xに垂直でポケット中央を通り、Yが右、Zが上、という対応を人が指定しています。断面記号・ハッチングを自動認識した結果ではありません。</p>'
            body+=f'<img class="section-image" src="{svg_data((folder/"section.svg").read_bytes())}" alt="CADから生成した断面輪郭">'
        if inf.get('disambiguation'):
            d=inf['disambiguation'];rows=[]
            for option in d['alternatives']:
                rows.append([option['opening'],option['parameters']['pocket_depth'],str(option['visibility_matches']),option['section_residual_mm'] if option['section_matches'] is not None else '未入力',option['compatible']])
            body+='<details><summary>上開き・下開き候補を比べた根拠</summary><p>宣言した矩形ポケット部品内の2候補だけを比較します。任意の形状の一意性を証明するものではありません。線種判定が利用できない場合、compatible=trueでも確定しません。</p>'+table(['開口','候補の深さ mm','線種一致','断面残差 mm','矛盾なし'],rows)+'</details>'
        old=o['baseline'];b=o.get('baseline_geometry')
        body+=f'<details><summary>変更前の判定と今回の評価条件</summary><p>前の処理：{escape(old["status"])} / {escape(old.get("reason") or old.get("reason_code") or "候補生成")}。'
        if b:body+=f'前の候補の実測IoU：{b["same_kernel_iou"]:.8f}。'
        body+=f'</p><p>人が与えた条件は、部品種別・mm・第三角法・ビュー対応です。寸法値と正解STEPは復元へ渡しません。{report["repeats"]}回の反復結果一致：{o["stable"]}。</p><p class="digest">入力SHA-256: {o["drawing_sha256"]}</p></details>'
        body+=f'<nav class="downloads"><a href="{key}/input.{o["format"]}">解析入力</a><a href="{key}/inference.json">根拠JSON</a><a href="{key}/context.json">人が指定した条件</a></nav>'
        state={'candidate':'復元・編集を照合','withheld':'保留','failed':'評価失敗'}[category]
        parts.append(f'<article class="case" data-case="{key}" data-category="{category}" data-opening="{inf.get("opening","top")}"><div class="case-head"><div><span class="case-id">{key}</span><h2>{escape(label)}</h2></div><span class="badge {category}">{state}</span></div><div class="stage-grid">'+panel+preview+'</div>'+body+'</article>')
    s=report['summary'];h=s['holdout'];tot=sum(v['false_confirmations'] for v in s.values())
    stats=''.join(f'<div class="stat"><span>{label}</span><strong>{value}</strong></div>' for label,value in (
        ('未調整の48入力で復元・編集を照合',f'{h["correct"]} / {h["inputs"]}'),('未調整データで保留',h['withheld']),('今回の観測内での誤確定',tot)))
    cohorts=table(['評価区分','部品 / 入力数','正しく復元','保留','実行失敗'],[[COHORTS[k],f'{v["parts"]} / {v["inputs"]}',v['correct'],v['withheld'],v['failures']] for k,v in s.items()])
    family_rows=[]
    for family,name in FAMILIES.items():
        for fmt in ('svg','dxf'):
            rows=[o for o in report['observations'] if o['cohort']=='holdout' and o['family']==family and o['format']==fmt]
            family_rows.append([name,fmt.upper(),len(rows),sum(o['trials'][0].get('reconstructed_correctly',False) for o in rows),sum(o['trials'][0]['status']=='withheld' for o in rows)])
    families=table(['未調整部品','形式','入力数','復元・編集一致','保留'],family_rows)
    doc='''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>別CAD・図面の曖昧さ・未調整部品の検証</title><style>'''+CSS+'''.section-image{display:block;width:100%;max-height:360px;background:white}td{white-space:normal}.overview{background:white;padding:22px;border-radius:12px;margin-bottom:22px}</style></head><body><main>
<header><p class="eyebrow">RESEARCH NOTES · 2026-10-22 · FROZEN EVALUATION</p><h1>別CAD・図面の曖昧さ・未調整部品の検証</h1><p>図面だけでは決められない向きを保留し、隠れ線や断面があるときに復元できるか。処理を固定してから、寸法の異なる24部品でも確かめました。</p><p class="scope">自作CAD図面と、LibreCADによる再出力の実験です。顧客図面・未知の部品種別・任意のCADへの対応率ではありません。</p></header><div class="stats">'''+stats+'''</div><section class="overview"><h2>今回分かったこと</h2><p>FreeCADのSVGでは上・下のポケットを線種から区別できました。今回のDXFは線種情報が失われるため、断面なしでは保留します。LibreCADのSVGには寸法注記が渡らず、4部品すべてを保留しました。</p>'''+cohorts+f'''<p class="caption">LibreCADは4部品×2出力設定。設定違いでもSVGのSHA-256は同一で、固有の入力は{s['portability']['unique_drawings']}件です。8件の独立した成功・失敗事例とは数えません。反復は各{report['repeats']}回。</p><details><summary>未調整24部品を形式・部品種別ごとに見る</summary>'''+families+'''<p>同じ4種の部品と作図手順で、寸法・縮尺・文字サイズを変えた評価です。復元処理は入力図面の生成前に固定しています。復元可能と期待した入力の保留も、そのまま失敗例として残します。</p></details></section>
<p>未調整入力の保留8件は、DXFの開口方向が決められない6件と、SVGの寸法文字と寸法線を対応づけられない2件です。後者は復元を期待した入力での失敗として残しています。</p>
<section class="selection"><label>結果 <select id="filter"><option value="all">すべて</option><option value="candidate">復元・編集を照合</option><option value="withheld">保留</option><option value="failed">評価失敗</option></select></label><label class="case-picker">確認する入力 <select id="case-picker"><option value="development_bottom_svg">下側ポケット / SVG</option></select></label><span id="case-count" aria-live="polite"></span></section><p id="empty" hidden>この分類の結果はありません。</p>'''+''.join(parts)+'''
<footer><h2>再現と、この結果の限界</h2><p>正解は評価側だけで使用したFreeCADモデルと設計値です。復元は編集可能なPythonレシピとSTEPを生成しますが、元作者の操作履歴は復元しません。体積IoUは同系統のOCCTで計算しており、独立カーネルの検証ではありません。</p><p>全線の輪郭一致だけでは開口方向を保証できません。断面の対応は人の指定が必要で、複合形状・公差・実務PDF・スキャン画像・自動部品分類は未評価です。誤確定ゼロは今回の固定入力に限る観測です。</p><p>このHTMLはオフラインで閲覧できます。ダウンロードには隣接フォルダーが必要です。</p><p><a href="../../notes/drawing-generalization.md">研究ノート</a> · <a href="../../docs/drawing-generalization.md">再現手順</a> · <a href="results.json">全観測JSON</a> · <a href="summary.csv">要約CSV</a> · <a href="verification.json">検証記録</a></p></footer></main><script type="application/json" id="meshes">'''+safe_json(meshes)+'''</script><script type="application/json" id="pictures">'''+safe_json(pictures)+'''</script><script>'''+JS.replace('one_third','development_bottom_svg')+'''</script></body></html>'''
    (directory/'report.html').write_text(doc,encoding='utf-8')
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);write_report(p.parse_args().directory)
