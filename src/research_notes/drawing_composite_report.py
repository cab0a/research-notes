"""Offline compound CAD results and source-bound dimension-ID review UI."""
from pathlib import Path
from html import escape
import json,xml.etree.ElementTree as ET
from .drawing_dimension_report import CSS,JS,svg_data,table
from .drawing_family_report import crops,overlay
from .cad_svg_report import safe_json
def review_picture(source,request):
    root=ET.fromstring(source);box=list(map(float,root.get('viewBox').split()))
    sx=box[2]/float(root.get('width').removesuffix('mm'));sy=box[3]/float(root.get('height').removesuffix('mm'))
    points=request['dimension_line']+[c['origin'] for c in request['choices']]
    lo=[min(q[j] for q in points)-14 for j in (0,1)];hi=[max(q[j] for q in points)+18 for j in (0,1)]
    root.set('viewBox',f'{box[0]+lo[0]*sx} {box[1]+lo[1]*sy} {(hi[0]-lo[0])*sx} {(hi[1]-lo[1])*sy}')
    ns='{http://www.w3.org/2000/svg}';g=ET.SubElement(root,ns+'g',{'transform':f'translate({box[0]},{box[1]}) scale({sx},{sy})'})
    a,b=request['dimension_line'];ET.SubElement(g,ns+'line',dict(x1=str(a[0]),y1=str(a[1]),x2=str(b[0]),y2=str(b[1]),stroke='#dd3344',**{'stroke-width':'.4','opacity':'.7'}))
    for i,c in enumerate(request['choices']):
        x,y=c['origin'];ET.SubElement(g,ns+'circle',dict(cx=str(x-2),cy=str(y-2),r='1.2',fill='#e89723'))
        label=ET.SubElement(g,ns+'text',dict(x=str(x-5),y=str(y-5),fill='#a95400',**{'font-size':'3'}));label.text=str(i+1)
    return svg_data(ET.tostring(root))

def review_panel(source,inf,key):
    req=inf.get('review_request')
    if not req:return ''
    options='<option value="">未選択</option>'+''.join(f'<option value="{escape(c["id"])}">{i+1}: {escape(c["text"])} / {escape(c["id"])}</option>' for i,c in enumerate(req['choices']))
    return f'''<section class="review-panel" data-review="{key}"><h3>寸法文字の対応を確認</h3><p>赤線に対応する寸法文字を選びます。橙色の点は候補文字の位置です。元の文字IDを選ぶだけで、数値は入力しません。自動探索の候補数：{req.get('automatic_candidate_count','—')}。図は入力SVGの拡大表示です。</p><img class="review-image" src="{review_picture(source,req)}" alt="寸法線と文字候補の拡大図"><div class="toolbar"><label>操作した人 <select class="operator-kind"><option value="unspecified">未指定</option><option value="human">利用者</option><option value="agent">エージェントによる操作確認</option></select></label><button class="review-start">確認を開始</button><label>寸法文字 <select class="label-choice">{options}</select></label><button class="review-save" disabled>選択JSONを保存</button><button class="log-save" disabled>操作記録を保存</button></div><p class="review-status" aria-live="polite">開始ボタンから選択JSONの保存までを計測します。CAD計算・環境準備の時間は含みません。</p><p>保存したJSONをCLIの <code>--review</code> に渡すと再計算できます。このHTMLの3Dは保存済み結果で、選択を変えても再計算しません。操作確認の時間を人の業務短縮率として扱いません。</p></section>'''

REVIEW_JS=r'''
const reviewData=JSON.parse(document.getElementById('review-data').textContent);
document.querySelectorAll('.review-panel').forEach(panel=>{
 const key=panel.dataset.review,inf=reviewData[key],choice=panel.querySelector('.label-choice'),save=panel.querySelector('.review-save'),logButton=panel.querySelector('.log-save'),status=panel.querySelector('.review-status');
 let start=null,measurement=null,events=[];
 function download(name,obj){const u=URL.createObjectURL(new Blob([JSON.stringify(obj,null,2)+'\n'],{type:'application/json'}));const a=document.createElement('a');a.href=u;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),2000);}
 function ready(){save.disabled=start===null||!choice.value;}
 panel.querySelector('.review-start').onclick=()=>{start={iso:new Date().toISOString(),monotonic:performance.now()};events=[];measurement=null;logButton.disabled=true;status.textContent='確認操作を計測中。寸法線と文字を見て選んでください。';ready();};
 choice.onchange=()=>{if(start)events.push({action:'select_label',dimension_id:inf.review_request.dimension_id,text_id:choice.value,elapsed_ms:performance.now()-start.monotonic});ready();};
 save.onclick=()=>{if(save.disabled)return;const labels={[inf.review_request.dimension_id]:choice.value};
  measurement={drawing_sha256:inf.source_sha256,operator_kind:panel.querySelector('.operator-kind').value,started_at:start.iso,elapsed_ms:performance.now()-start.monotonic,events:[...events],scope:'Start button to selection JSON export; excludes setup and CAD computation. Agent checks are not human performance evidence.'};
  download(key+'-review.json',{drawing_sha256:inf.source_sha256,labels});logButton.disabled=false;status.textContent='選択JSONを保存しました。'+events.length+'回の選択操作、'+(measurement.elapsed_ms/1000).toFixed(2)+'秒。再計算はCLIで実行します。';};
 logButton.onclick=()=>{if(measurement)download(key+'-interaction.json',measurement);};
});
'''

def write_review_draft(directory,fixtures):
    directory.mkdir(parents=True,exist_ok=True);data={};panels=[]
    for key in ('review_pocket_1','review_pocket_4'):
        folder=fixtures/'controls'/key;inf=json.loads((folder/'initial-inference.json').read_text());data[key]=inf
        panels.append('<article><h2>'+key+'</h2>'+review_panel((folder/'drawing.svg').read_bytes(),inf,key)+'</article>')
    doc='<!doctype html><html lang="ja"><head><meta charset="utf-8"><title>寸法対応の確認</title><style>'+CSS+'''.review-image{width:100%;max-height:380px;background:white}.review-panel{padding:20px;background:white;margin:20px 0}.review-status{background:#fff0d6;padding:10px}</style></head><body><main><h1>寸法線と文字の対応を確認</h1><p>以前の評価で保留した2入力を、今回の開発用に移しています。自動判定は広げず、選択した文字IDを図面のSHA-256へ結びつけます。</p>'''+''.join(panels)+'</main><script id="review-data" type="application/json">'+safe_json(data)+'</script><script>'+REVIEW_JS+'</script></body></html>'
    (directory/'report.html').write_text(doc,encoding='utf-8')

LABELS={'pocket_hole':'ポケット＋貫通穴','two_pockets':'深さの異なる2ポケット','step_hole':'角の段差＋貫通穴',
    'mixed_pockets':'上面・下面に開く2ポケット','review_pocket_1':'寸法文字を選択して再計算①','review_pocket_4':'寸法文字を選択して再計算②',
    'missing_depth':'深さ寸法が不足','visibility_lost':'線種を失った図面','wrong_views':'正面・平面の取り違え','dimension_conflict':'寸法値と図形の矛盾'}
REASONS={'opening_evidence_missing':'このDXF経路では可視線・隠れ線を区別できず、上面／下面の開口を確定できません。線種が残る図面や確認済み断面が必要です。今回の複合形状処理には断面入力をまだ接続していません。',
    'feature_depth_ambiguous':'各切削形状に対応する深さ寸法を一意に選べません。正面図の寸法と対象の対応を確認してください。',
    'visibility_conflict':'輪郭と可視線・隠れ線をすべて説明する開口方向の組合せがありません。線種と図面の整合性を確認してください。',
    'dimension_label_ambiguous':'自動探索では寸法文字を一意に選べません。候補数は0の場合もあります。元図面の寸法線と文字の対応を確認してください。',
    'dimension_conflict':'ビューの対応または外形寸法が矛盾しています。正面・平面・側面の指定を確認してください。',
    'geometry_dimension_conflict':'図形の長さと記載寸法が整合しません。図面の寸法値を確認してください。'}
def label(o):
    p=o['part'];base=p.rsplit('_',1)[0] if o['cohort']=='holdout' else p
    return ('未調整 '+p.rsplit('_',1)[-1]+'：' if o['cohort']=='holdout' else '')+LABELS.get(base,p)+' / '+o['format'].upper()
def flat(p):
    names={'width':'幅','length':'奥行','thickness':'厚さ','kind':'種類','depth':'深さ','x':'X位置','y':'Y位置','diameter':'穴径','opening':'開口方向'}
    result={'板 / '+names[k]:p[k] for k in ('width','length','thickness')}
    for i,f in enumerate(p['features']):
        f=dict(f)
        if f['kind']!='hole':f.setdefault('opening','top')
        for k in ('kind','x','y','width','length','depth','diameter','opening'):
            if k in f:result[f'形状{i+1} / {names[k]}']=f[k]
    return result
def write_report(directory):
    report=json.loads((directory/'results.json').read_text());parts=[];meshes={};pictures={};reviews={}
    for o in report['observations']:
        key=o['id'];folder=directory/key;inf=json.loads((folder/'inference.json').read_text());trial=o['trials'][0]
        source=(folder/'input.svg').read_bytes();pictures[key]=crops(source,inf,o['format'])
        category='candidate' if trial['reconstructed_correctly'] else 'withheld' if trial['status']=='withheld' else 'failed'
        state={'candidate':'復元・編集を検証','withheld':'保留','failed':'評価失敗'}[category]
        panel=f'''<section class="panel"><h3>入力図面</h3><div class="toolbar"><label>表示 <select class="view-select"><option value="all">三面図全体</option><option value="top">平面図</option><option value="front">正面図</option><option value="right">右側面図</option></select></label><button class="image-minus">縮小</button><button class="image-plus">拡大</button><span class="image-scale">100%</span></div><div class="drawing-window"><img class="drawing" src="{pictures[key]['all']}" alt="{escape(label(o))}の入力図面"></div><p class="caption">{'DXFが解析入力。表示は同じCADページのSVGで、復元処理へは渡していません。' if o['format']=='dxf' else '解析したSVGそのもの。寸法線と記載寸法から復元します。'}</p></section>'''
        body=''
        if category=='candidate':
            meshes[key]=json.loads((folder/'preview.json').read_text());c=json.loads((folder/'comparison.json').read_text())
            preview='''<section class="panel"><h3>復元した3D CAD</h3><div class="toolbar"><label>モデル <select class="model-select"><option value="original">復元したモデル</option><option value="edited">寸法変更後</option></select></label><button class="reset-camera">視点リセット</button><button class="zoom-out">−</button><button class="zoom-in">＋</button></div><canvas class="preview" width="700" height="420" tabindex="0" aria-label="回転可能な3Dプレビュー"></canvas><p class="caption">ドラッグ・矢印キーで回転、ホイールで拡大縮小。モデルを切り替えても視点を維持します。下面のポケットは回転して確認できます。</p></section>'''
            p,t,e=map(flat,(c['parameters'],c['truth_parameters'],c['edited_parameters']))
            rows=[[k,t[k],p[k],p[k]-t[k] if isinstance(p[k],(int,float)) else ('一致' if p[k]==t[k] else '不一致'),e[k]] for k in t]
            body+='<h3>形状ごとの寸法と編集結果</h3><p>stockの幅・奥行・厚さと、各ポケット・穴の位置／寸法を独立したパラメータにしています。数値の単位はmm。topは上面、bottomは下面の開口です。</p>'+table(['項目','評価用の正解','図面から取得','差','変更後'],rows)
            m,em=c['metrics'],c['edit_metrics']
            body+=table(['評価項目','観測値'],[['有効な単一ソリッド・STEP再読込',str(m['valid_solid'])+' / '+str(m['step_read_success'])],
                ['元形状 / 編集後の体積IoU',f'{m["same_kernel_iou"]:.12g} / {em["same_kernel_iou"]:.12g}'],
                ['抽出寸法の最大誤差 mm',f'{trial["parameter_error_mm"]:.6g}'],['外形の最大誤差 mm',f'{m["bounds_error_mm"]:.6g}'],
                ['再投影のサンプル最大残差 mm',f'{max(v["sampled_symmetric_max_mm"] for v in trial["projection_metrics"].values()):.6g}']])
            body+='<h3>元図面とCADの再投影</h3><p class="caption">灰：入力輪郭、青：復元B-Repの投影。線種の照合結果は下の開口候補に記録しています。</p>'+overlay(inf['raw_views'],inf['reprojection'])
            body+='<nav class="downloads">'+''.join(f'<a href="{key}/{name}" download>{text}</a>' for name,text in (('candidate.step','復元STEP'),('edited.step','変更後STEP'),('candidate.py','編集用Python'),('model.json','設計モデルJSON')) )+'</nav>'
        else:
            reason=inf.get('reason_code','failed')
            preview=f'<section class="panel withheld-panel"><h3>CAD生成を保留しました</h3><p>{escape(REASONS.get(reason,"記録と入力条件を確認してください。"))}</p><code>{escape(reason)}</code><p>{escape(inf.get("detail",trial.get("detail") or ""))}</p><p>正解形状を代わりに表示していません。</p></section>'
        if o['cohort']=='review':
            initial=json.loads((folder/'initial-inference.json').read_text());reviews[key]=initial;measurement=o['interaction']
            body=f'<p class="scope">この入力は前回の保留例を今回の開発用へ移したものです。自動探索の文字候補は0件でした。元図面の文字IDを1回選択して再計算した結果を表示しています。エージェント操作確認：{measurement["elapsed_ms"]/1000:.2f}秒（人の作業時間・短縮効果の測定ではありません）。</p>'+review_panel(source,initial,key)+body
            body+=f'<p><a href="{key}/review.json">実際に保存した選択JSON</a> · <a href="{key}/interaction.json">操作記録</a> · <a href="{key}/initial-inference.json">選択前の保留結果</a></p>'
        if inf.get('opening_alternatives'):
            body+='<details><summary>上面／下面の開口候補と線種の照合</summary>'+table(['形状順の開口方向','輪郭・線種と整合','線種別の最大残差 mm'],[[', '.join(a['openings']),a['compatible'],max(v for v in a['visibility_residual_mm'].values() if v is not None)] for a in inf['opening_alternatives']])+'</details>'
        body+=f'<details><summary>固定条件・入力・根拠</summary><p>区分：{o["cohort"]}。{len(o["trials"])}回反復。人が指定した条件：mm、第三角法、3ビュー対応、分離したZ方向切削を持つ板という部品範囲。正解寸法は評価側だけで使用しています。</p><p class="digest">入力SHA-256: {inf["source_sha256"]}</p><a href="{key}/input.{o["format"]}">解析入力</a> · <a href="{key}/inference.json">根拠JSON</a> · <a href="{key}/context.json">確認条件</a></details>'
        parts.append(f'<article class="case" data-case="{key}" data-category="{category}" data-opening="{inf.get("opening","top")}"><div class="case-head"><div><span class="case-id">{key}</span><h2>{escape(label(o))}</h2></div><span class="badge {category}">{state}</span></div><div class="stage-grid">{panel}{preview}</div>{body}</article>')
    s=report['summary'];h=s['holdout']
    stats=''.join(f'<div class="stat"><span>{name}</span><strong>{value}</strong></div>' for name,value in (
        ('未調整の複合部品：SVGで復元・編集',f'{h["correct"]} / {h["eligible_inputs"]}'),('未調整DXF：根拠不足で保留',f'{h["withheld"]} / {h["inputs"]-h["eligible_inputs"]}'),('全入力の誤確定',sum(v['false_confirmations'] for v in s.values()))))
    totals=table(['区分','入力数','復元・編集一致','保留','処理失敗'],[[{'development':'開発','review':'文字ID選択後','negative':'欠落・矛盾対照','holdout':'未調整の部品'}[k],v['inputs'],v['correct'],v['withheld'],v['failures']] for k,v in s.items()])
    doc='''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>図面からCADへ：複合形状の検証</title><style>'''+CSS+'''.review-image{width:100%;max-height:380px;background:white}.review-panel{background:#f7fafb;padding:18px;margin:20px 0}.review-status{background:#fff0d6;padding:10px}button:disabled{opacity:.5}</style></head><body><main><header><p class="eyebrow">RESEARCH NOTES · 独立探索</p><h1>図面からCADへ：複合形状の検証</h1><p>ポケットと穴、深さの異なる2ポケット、角の段差と穴を、寸法図から編集可能なCADに復元しました。入力図面・3D・変更後の寸法・保留理由を確認できます。</p><p class="scope">FreeCADで自作した、互いに離れた切削形状の検証です。未調整9部品も既知の3種類と同じ作図手順の寸法違いです。任意の実務図面や重なり合う形状への対応を意味しません。</p></header><div class="stats">'''+stats+'''</div><section class="selection"><label>結果 <select id="filter"><option value="all">すべて</option><option value="candidate">復元・編集を検証</option><option value="withheld">保留</option><option value="failed">評価失敗</option></select></label><label class="case-picker">確認する例 <select id="case-picker"><option value="development_pocket_hole_svg">ポケット＋穴</option></select></label><span id="case-count" aria-live="polite"></span></section><p id="empty" hidden>この分類の結果はありません。</p>'''+''.join(parts)+'''<details><summary>全入力の集計</summary>'''+totals+f'<p>各{report["repeats"]}回反復。反復の判定と数値は'+('一致しました。' if report['repeat_stable'] else '一致しませんでした。')+'''</p></details><footer><h2>今回の範囲と、次に確かめること</h2><p>矩形の板から、分離した矩形ポケット・左下角の段差・Z方向の貫通丸穴を切り取る構成です。矩形切削は2つまで、全形状は3つまでに制限しています。各ポケットの上／下開口候補を列挙し、寸法・輪郭・可視線／隠れ線が一致する候補が1つの場合だけ採用します。</p><p>STEPの有効性、外形、解析体積・面積、正解STEPとの体積IoU、再投影、編集後の再生成を評価しました。正解作者モデルも復元処理もOCCT系なので、独立カーネルの検証ではありません。編集は生成したPython／JSONから行い、元作者の操作履歴を復元するものではありません。</p><p>DXFの線種不足は未解決です。LibreCADの別出力経路（PNG）も実行しましたが、この環境では寸法線・矢印は見えても寸法文字が表示されませんでした。別CADで情報を保持できる経路を確保できたとは扱いません。交差する加工形状、公差、任意断面、画像OCR、顧客図面、人の作業時間短縮も未評価です。</p><p>HTML内の図面・3D表示と選択JSONの保存はローカルで動作します。CAD再計算はCLIで実行します。ダウンロードには隣接フォルダーが必要です。</p><p><a href="../../notes/drawing-composites.md">研究ノートと今後の計画</a> · <a href="../../docs/drawing-composites.md">再現手順</a> · <a href="results.json">全観測JSON</a> · <a href="summary.csv">要約CSV</a> · <a href="librecad-render/drawing.png">LibreCADのPNG出力</a></p></footer></main><script type="application/json" id="meshes">'''+safe_json(meshes)+'''</script><script type="application/json" id="pictures">'''+safe_json(pictures)+'''</script><script type="application/json" id="review-data">'''+safe_json(reviews)+'''</script><script>'''+JS.replace('one_third','development_pocket_hole_svg')+REVIEW_JS+'''</script></body></html>'''
    if not (directory/'librecad-render/drawing.png').exists():
        doc=doc.replace(' · <a href="librecad-render/drawing.png">LibreCADのPNG出力</a>','')
    (directory/'report.html').write_text(doc,encoding='utf-8')

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);write_report(p.parse_args().directory)
