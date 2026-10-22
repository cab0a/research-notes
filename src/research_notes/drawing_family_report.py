"""Offline saved results, dimension evidence and nonnumeric human review context."""
from html import escape
import json,xml.etree.ElementTree as ET
from pathlib import Path
from .drawing_dimension_report import CSS,JS,svg_data,table
from .cad_svg_report import safe_json

LABELS={'unseen_small':'未観測設定：縮尺0.85・文字2.5 mm','unseen_large':'未観測設定：縮尺1.2・文字4.2 mm',
'two_holes':'径の異なる2穴','three_shared':'X位置を共有する3穴','quantity_two':'2 × 径6の数量注記',
'l_bracket':'L字ブラケット','stepped_shaft':'段付き軸','pocket':'矩形ポケット',
'l_missing_wall':'L字：壁厚が不足','shaft_missing_small':'段付き軸：小径が不足','pocket_missing_depth':'ポケット：深さが不足',
'arc_circle':'円弧Aの円','quadratic_lines':'直線を二次曲線Qで表記','tspan_text':'tspanの分割文字',
'split_dimensions':'別パスに分かれた寸法線','moved_labels':'寸法値の配置変更','outlined_text':'アウトライン化した文字',
'positioned_tspan':'位置を個別指定したtspan','bad_quantity':'数量と穴数が矛盾','missing_projection':'投影法が未指定','wrong_views':'正面・平面の取り違え'}
REASONS={'dimension_missing':'必要な寸法がありません。下の詳細にある壁厚・小径・深さなどを図面作成者へ確認します。',
'text_unavailable':'文字が図形に変換されており、寸法値を取得できません。元の文字データ、または別途検証した文字認識・人の確認が必要です。',
'svg_text_layout':'文字の部分ごとの位置指定は未対応です。表示上の寸法値と配置を人が確認します。',
'quantity_conflict':'数量注記と同径の円の数が一致しません。どの穴群を指しているかを確認します。',
'projection_unknown':'投影法が未指定です。図面の投影法を確認し、下の条件欄に指定します。',
'dimension_conflict':'寸法またはビュー対応が矛盾しています。正面・平面・側面の指定と寸法を照合します。'}
PARAMS={'width':'幅','length':'奥行','thickness':'厚さ','height':'高さ','base_thickness':'底板厚','wall_thickness':'壁厚',
'length1':'大径部の長さ','length2':'小径部の長さ','diameter1':'大径','diameter2':'小径',
'pocket_x':'ポケットX','pocket_y':'ポケットY','pocket_width':'ポケット幅','pocket_length':'ポケット奥行','pocket_depth':'ポケット深さ'}
ROLES={'front':'正面','top':'平面','right':'右側面'}

def flat_params(p):
    result={PARAMS.get(k,k):v for k,v in p.items() if k!='holes'}
    for i,h in enumerate(sorted(p.get('holes',[]),key=lambda h:(h['x'],h['y']))):
        result.update({f'穴{i+1} '+{'x':'X','y':'Y','diameter':'径'}[k]:v for k,v in h.items()})
    return result

def crops(source,inf,fmt):
    pictures={'all':svg_data(source)}
    root=ET.fromstring(source)
    box=list(map(float,root.get('viewBox').split()))
    page_w,page_h=(float(root.get(k).removesuffix('mm')) for k in ('width','height'))
    sx,sy=box[2]/page_w,box[3]/page_h
    for role,v in (inf.get('evidence') or {}).get('views',{}).items():
        x0,y0,x1,y1=v['bounds']
        # Native SVG is paired display-only for DXF; both were authored on A3.
        top=-y1 if fmt=='svg' else page_h-y1
        root.set('viewBox',f'{box[0]+(x0-24)*sx} {box[1]+(top-24)*sy} {(x1-x0+48)*sx} {(y1-y0+48)*sy}')
        pictures[role]=svg_data(ET.tostring(root))
    for role in ROLES:pictures.setdefault(role,pictures['all'])
    return pictures

def overlay(raw,projected):
    parts=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 300" aria-label="入力輪郭と再投影">']
    for i,role in enumerate(ROLES):
        points=[p for line in raw[role] for p in line]
        w,h=[max(p[j] for p in points) for j in (0,1)];scale=min(250/max(w,1),220/max(h,1))
        parts.append(f'<text x="{i*300+20}" y="25" font-size="16">{ROLES[role]}</text>')
        for lines,color,width in ((raw[role],'#acb7bd',4),(projected[role],'#087d9d',1.2)):
            for line in lines:
                xy=' '.join(f'{i*300+20+p[0]*scale:.4f},{270-p[1]*scale:.4f}' for p in line)
                parts.append(f'<polyline points="{xy}" fill="none" stroke="{color}" stroke-width="{width}"/>')
    return ''.join(parts)+'</svg>'

def review_panel(inf):
    ctx=inf['human_context'];roles=ctx['view_roles']
    controls=''
    for role,label in ROLES.items():
        options=''.join(f'<option value="{escape(ref)}" {"selected" if role==r else ""}>元の{ROLES[r]}：{escape(ref)}</option>' for r,ref in roles.items())
        controls+=f'<label>{label} <select class="role-review" data-role="{role}">{options}</select></label>'
    projection=''.join(f'<option value="{key}" {"selected" if ctx["projection"]==key else ""}>{label}</option>' for key,label in
                       (('unknown','未指定'),('third_angle','第三角法'),('first_angle','第一角法')))
    dims=(inf.get('evidence') or {}).get('dimensions',[])
    options='<option value="">すべての輪郭</option>'+''.join(f'<option value="{i}">{ROLES[d["view"]]} / {escape(d["text"])} / {escape(d["id"])}</option>' for i,d in enumerate(dims))
    return f'''<details class="review-panel"><summary>寸法の根拠と、人が確認する条件</summary>
<p>寸法を選ぶと、その値が参照する形状上の端点を橙色で表示します。図は抽出した輪郭と端点です。寸法線そのものの位置を再現した図ではありません。</p>
<label>根拠の寸法 <select class="dimension-pick">{options}</select></label>
<svg class="evidence-view" viewBox="0 0 900 380" aria-label="寸法端点とビューの対応"></svg><p class="dimension-detail" aria-live="polite"></p>
<h3>ビューの役割を確認</h3><p>保存済みの3ビュー候補を指定し直せます。図面の数値はここから入力しません。部品種別の仮定は <strong>{escape(ctx['family_assumption'])}</strong> です。</p>
<div class="toolbar">{controls}<label>投影法 <select class="projection-review">{projection}</select></label></div>
<p class="review-status" aria-live="polite">保存済みの条件を表示しています。</p>
<textarea class="review-json" rows="10" readonly aria-label="再計算用の確認条件JSON"></textarea>
<button class="save-context" type="button">確認条件JSONを保存</button>
<p>このHTMLは再計算しません。条件を変えても、上の3Dと数値は元の条件による保存結果です。JSONを保存し、再現手順のCLIへ入力してください。</p></details>'''

REVIEW_JS=r'''
const evidenceData=JSON.parse(document.getElementById("evidence-data").textContent);
const svgNS="http://www.w3.org/2000/svg";
document.querySelectorAll("article.case").forEach(article=>{
 const inf=evidenceData[article.dataset.case],panel=article.querySelector(".review-panel"),ev=inf.evidence;
 const plot=panel.querySelector(".evidence-view"),status=panel.querySelector(".review-status"),area=panel.querySelector(".review-json");
 function draw(){
  plot.replaceChildren();
  if(!ev){panel.querySelector(".dimension-detail").textContent="解析が途中で保留になったため、端点の根拠データはありません。入力図面と保留理由を確認してください。";return;}
  const bounds=Object.values(ev.views).map(v=>v.bounds),x0=Math.min(...bounds.map(b=>b[0]))-15,x1=Math.max(...bounds.map(b=>b[2]))+15,y0=Math.min(...bounds.map(b=>b[1]))-15,y1=Math.max(...bounds.map(b=>b[3]))+15;
  const s=Math.min(850/(x1-x0),330/(y1-y0)),xy=p=>[25+(p[0]-x0)*s,355-(p[1]-y0)*s];
  function element(tag,attrs){const e=document.createElementNS(svgNS,tag);Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,v));plot.append(e);return e;}
  for(const [role,v] of Object.entries(ev.views)){
   for(const line of v.raw)element("polyline",{points:line.map(p=>xy(p).join(",")).join(" "),fill:"none",stroke:"#718692","stroke-width":1});
   const a=xy([v.bounds[0],v.bounds[3]]),b=xy([v.bounds[2],v.bounds[1]]);
   element("rect",{x:a[0]-5,y:a[1]-5,width:b[0]-a[0]+10,height:b[1]-a[1]+10,fill:"none",stroke:"#adc8d4","stroke-dasharray":"4 4"});
   element("text",{x:a[0],y:a[1]-9,fill:"#506b7a","font-size":12}).textContent=role+" / "+inf.human_context.view_roles[role];
  }
  const selection=panel.querySelector(".dimension-pick").value;
  const detail=panel.querySelector(".dimension-detail");
  if(selection===""){detail.textContent="寸法を選ぶと、参照先とパラメータへの対応を確認できます。";return;}
  const d=ev.dimensions[Number(selection)],points=d.points.map(xy);
  element("polyline",{points:points.map(p=>p.join(",")).join(" "),fill:"none",stroke:"#ce6a24","stroke-width":3});
  points.forEach(p=>element("circle",{cx:p[0],cy:p[1],r:5,fill:"#ce6a24"}));
  const bindings=Object.entries(inf.bindings||{}).filter(([,ids])=>ids.includes(d.id)).map(([key])=>key);
  detail.textContent=d.view+" / 「"+d.text+"」 → "+d.value+" mm / "+(bindings.length?bindings.join(", "):"整合性検査・保留前の抽出")+" / "+d.id;
 }
 function context(){
  const c=JSON.parse(JSON.stringify(inf.human_context));
  panel.querySelectorAll(".role-review").forEach(s=>{c.view_roles[s.dataset.role]=s.value;});
  c.projection=panel.querySelector(".projection-review").value;return c;
 }
 function update(){
  const c=context(),duplicate=new Set(Object.values(c.view_roles)).size!==3,unknown=c.projection==="unknown";
  const changed=JSON.stringify(c)!==JSON.stringify(inf.human_context);
  status.textContent=duplicate?"ビュー指定が重複しています。3つを別々に指定してください。":unknown?"投影法を確認して指定してください。":changed?"条件変更・未再計算。3Dと数値は元の条件の保存結果です。":"保存済みの条件を表示しています。";
  area.value=JSON.stringify(c,null,2);panel.querySelector(".save-context").disabled=duplicate||unknown;
 }
 panel.querySelectorAll(".role-review,.projection-review").forEach(s=>s.addEventListener("change",update));
 panel.querySelector(".dimension-pick").addEventListener("change",draw);
 panel.querySelector(".save-context").addEventListener("click",()=>{
  const data=JSON.stringify(context(),null,2)+"\n",url=URL.createObjectURL(new Blob([data],{type:"application/json"})),a=document.createElement("a");
  a.href=url;a.download=article.dataset.case+"-reviewed-context.json";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
 });
 draw();update();
});
'''

def write_report(directory):
    report=json.loads((directory/'results.json').read_text());parts=[];meshes={};pictures={};evidence={}
    baseline={o['id']:o for o in report['baseline']['observations']}
    for o in report['observations']:
        key=o['id'];folder=directory/key;inf=json.loads((folder/'inference.json').read_text())
        evidence[key]={k:inf.get(k) for k in ('evidence','human_context','bindings')}
        pictures[key]=crops((folder/'input.svg').read_bytes(),inf,o['format'])
        category='candidate' if o['passed'] and inf['status']=='candidate' else 'withheld' if inf['status']=='withheld' else 'failed'
        label=LABELS.get(o.get('variant',o['part']),key)+' / '+o['format'].upper()
        state={'candidate':'復元・編集を検証','withheld':'保留（理由を確認）','failed':'評価失敗'}[category]
        panel=f'''<section class="panel"><h3>入力図面</h3><div class="toolbar">
<label>表示 <select class="view-select"><option value="all">三面図全体</option><option value="top">平面図</option><option value="front">正面図</option><option value="right">右側面図</option></select></label>
<button class="image-minus" type="button">縮小</button><button class="image-plus" type="button">拡大</button><span class="image-scale">100%</span></div>
<div class="drawing-window"><img class="drawing" alt="{escape(label)}の図面" src="{pictures[key]['all']}"></div>
<p class="caption">{'解析入力はDXF。ここには同じCADページのSVGを書き出して表示しています。SVGは復元処理へ渡していません。' if o['format']=='dxf' else '解析入力そのもののSVG。表示範囲を切り替えて確認できます。'}</p></section>'''
        body=''
        if inf['status']=='candidate' and (folder/'preview.json').exists():
            meshes[key]=json.loads((folder/'preview.json').read_text())
            preview='''<section class="panel"><h3>復元した3D CAD</h3><div class="toolbar"><label>モデル <select class="model-select"><option value="original">復元したモデル</option><option value="edited">寸法変更後</option></select></label><button class="reset-camera" type="button">視点リセット</button><button class="zoom-out" type="button">−</button><button class="zoom-in" type="button">＋</button></div>
<canvas class="preview" width="700" height="420" tabindex="0" aria-label="回転可能な3Dプレビュー"></canvas><p class="caption">ドラッグ・矢印キーで回転、ホイールで拡大縮小。STEPを再読込して得たB-Repの表示です。</p></section>'''
            c=json.loads((folder/'comparison.json').read_text());truth=flat_params(c['truth_parameters']);p=flat_params(c['parameters']);edited=flat_params(c['edited_parameters'])
            body+='<h3>寸法の照合と編集（mm）</h3><p>評価側の正解設計値と、図面から抽出したパラメータを照合しています。元作者のCAD操作履歴を復元したものではありません。</p>'
            body+=table(['項目','評価用の正解','図面から取得','差','寸法変更後'],[[k,v,p[k],p[k]-v,edited[k]] for k,v in truth.items()])
            m,em=c['metrics'],c['edit_metrics'];trial=o['trials'][0]
            body+=table(['検証項目','観測値'],[['有効な単一ソリッド・STEP再読込',str(m['valid_solid'])+' / '+str(m['step_read_success'])],
                ['元形状 / 編集後の体積IoU',f'{m["same_kernel_iou"]:.12g} / {em["same_kernel_iou"]:.12g}'],
                ['元形状の外形実測誤差 mm',f'{m["bounds_error_mm"]:.5g}'],['元形状の解析体積との差 mm³',f'{m["volume_error_mm3"]:.5g}'],
                ['再投影サンプル最大残差 mm',f'{max(v["sampled_symmetric_max_mm"] for v in trial["projection_metrics"].values()):.5g}']])
            body+='<h3>入力輪郭とCADの再投影</h3><p class="caption">灰：入力図形、青：実際のB-Repを投影した線。可視線・隠れ線を合わせて比較しています。</p>'+overlay(inf['raw_views'],inf['reprojection'])
            body+='<nav class="downloads">'+''.join(f'<a href="{key}/{name}" download>{label}</a>' for name,label in
                (('candidate.step','復元STEP'),('edited.step','変更後STEP'),('candidate.py','編集用Python'),('model.json','設計モデルJSON')) )+'</nav>'
        else:
            reason=inf.get('reason_code','failed')
            preview=f'<section class="panel withheld-panel"><h3>CAD生成を保留しました</h3><p>{escape(REASONS.get(reason,"下の記録と図面を確認してください。"))}</p><code>{escape(reason)}</code><p>{escape(inf.get("detail",""))}</p><p>不足する値を、正解データや見た目から補完していません。</p></section>'
        old=baseline[key]
        body+=review_panel(inf)
        body+=f'''<details><summary>固定条件・変更前の判定・出所</summary><p>区分: {escape(o['cohort'])}。{len(o['trials'])}回反復。変更前パーサーの判定: {escape(old['status'])} / {escape(old.get('reason') or '候補生成')}。</p>
<p>人が指定: mm、投影法、3ビュー対応、部品種別。図面に必要な寸法があることを前提とします。縮尺と寸法値は図面から取得します。</p>
<p class="digest">SHA-256: {inf['source_sha256']}</p><a href="{key}/input.{o['format']}">解析した入力</a> · <a href="{key}/inference.json">根拠JSON</a> · <a href="{key}/context.json">元の確認条件</a></details>'''
        parts.append(f'<article class="case" data-case="{key}" data-category="{category}"><div class="case-head"><div><span class="case-id">{key}</span><h2>{escape(label)}</h2></div><span class="badge {category}">{state}</span></div><div class="stage-grid">'+panel+preview+'</div>'+body+'</article>')
    s=report['summary']
    stats=''.join(f'<div class="stat"><span>{label}</span><strong>{value}</strong></div>' for label,value in (
        ('復元・編集を検証',f'{s["positive_passed"]} / {s["positive_inputs"]}'),
        ('理由も一致して保留',f'{s["withheld_passed"]} / {s["withheld_inputs"]}'),('保留対照の誤確定',s['false_confirmations'])))
    pairs=table(['CADページ','SVG / DXF','パラメータ一致','元形状IoU','変更後IoU','検査'],[
        [LABELS[p['part']], ' / '.join(p['formats'].values()),p.get('parameters_equal','保留理由を照合'),
         p.get('geometry',{}).get('candidate',{}).get('iou','—'),p.get('geometry',{}).get('edited',{}).get('iou','—'),p['passed']] for p in report['pairs']])
    document='''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>図面からCADへ：部品形状の拡張</title><style>'''+CSS+'''
.review-panel{background:#f7fafb;padding:18px;margin-top:20px}.review-panel label{font-size:13px}.review-json{display:block;width:100%;max-width:800px;margin:12px 0;font:12px monospace}.evidence-view{display:block;width:100%;max-height:380px;background:white;margin:15px 0}.review-status{padding:9px;border-left:3px solid #c88734;background:#fff4e3}button:disabled{opacity:.5}p{line-height:1.8}
</style></head><body><main><header><p class="eyebrow">RESEARCH NOTES · 2026-10-22</p><h1>図面からCADへ：部品形状の拡張</h1>
<p>実CADから出力した寸法図を使い、穴付き板・L字ブラケット・段付き軸・矩形ポケットの復元と寸法変更を確かめました。</p>
<p class="scope">自作したFreeCAD図面の開発・対照実験です。部品種別とビュー対応は人が指定しています。別CAD・顧客図面・任意形状の精度を示す結果ではありません。</p></header>
<div class="stats">'''+stats+'''</div><section class="selection"><label>結果 <select id="filter"><option value="all">すべて</option><option value="candidate">復元・編集を検証</option><option value="withheld">保留</option><option value="failed">評価失敗</option></select></label><label class="case-picker">確認する例 <select id="case-picker"><option value="l_bracket_svg">L字ブラケット / SVG</option></select></label><span id="case-count" aria-live="polite"></span></section><p id="empty" hidden>この分類の結果はありません。</p>'''+''.join(parts)+'''
<details><summary>同じCADページのSVG / DXF比較（11組）</summary>'''+pairs+'''</details>
<footer><h2>今回の到達点と限界</h2><p>22件の実CAD出力（11ページ×2形式）と10件の派生SVGを各2回検証しています。派生入力は独立した部品ではありません。未観測だった2設定は変更前に評価し、以後は開発データとして扱っています。初回の候補生成は3/4入力で、適応後の結果を未知図面の成功率とは呼びません。</p>
<p>SVGの円弧A、直線相当のQ、単純なtspan等は限定対応です。アウトライン文字・公差・任意の曲線・複合部品は未対応です。隠れ線の線種・見える側の意味の判定や一般的な自動ファミリー選択も行いません。</p>
<p>体積IoUはFreeCADの正解STEPと復元STEPを同じOCCTで再読込して計算しています。独立カーネルによる検証ではありません。HTMLはオフラインで閲覧・条件JSON保存ができ、CAD再計算はCLIで実行します。成果物のダウンロードには隣接フォルダーも必要です。</p>
<p><a href="../../notes/drawing-families.md">研究ノート</a> · <a href="../../docs/drawing-families.md">再計算・再現手順</a> · <a href="results.json">全観測JSON</a> · <a href="summary.csv">要約CSV</a></p></footer></main>
<script type="application/json" id="meshes">'''+safe_json(meshes)+'''</script><script type="application/json" id="pictures">'''+safe_json(pictures)+'''</script><script type="application/json" id="evidence-data">'''+safe_json(evidence)+'''</script><script>'''+JS.replace('one_third','l_bracket_svg')+REVIEW_JS+'''</script></body></html>'''
    document=document.replace('各2回検証',f'各{report["repeats"]}回検証')
    (directory/'report.html').write_text(document,encoding='utf-8')

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);write_report(p.parse_args().directory)
