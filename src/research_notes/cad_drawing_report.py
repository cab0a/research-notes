"""Offline viewer for real CAD exports. Rendering has no influence on inference."""
import base64
from html import escape
import io
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from .drawing_dimension_report import CSS, JS, table, overlay_svg, svg_data
from .drawing_to_cad import json_bytes

LABELS={'plain':'無孔プレート','one':'1穴プレート','decimal':'小数寸法のプレート','scaled':'縮尺 1.5 倍',
        'first':'第一角法','no_x':'穴X寸法なし','no_thru':'貫通指示なし','tolerance':'公差付き寸法','wrong_projection':'投影法の誤指定'}
REASONS={'svg_export_graphics_unsupported':'SVGの変換行列・パス・文字配置を正規化する処理は未実装です。対になるDXFから代用していません。',
         'hole_position_missing':'穴中心の位置寸法が不足しています。図形の縮尺から補完しません。',
         'hole_extent_ambiguous':'径だけでは貫通・止まりを確定できません。THRUや深さを確認します。',
         'unsupported_annotation':'公差付き寸法は未対応です。公称値だけを切り出して成功扱いにしません。',
         'projection_layout_conflict':'人が指定した投影法と実際のビュー配置が一致しません。'}

def dxf_preview(source):
    import ezdxf
    from ezdxf.addons.drawing import RenderContext, Frontend, layout, svg, config
    doc=ezdxf.read(io.StringIO(source.decode('utf-8')))
    backend=svg.SVGBackend()
    settings=config.Configuration(background_policy=config.BackgroundPolicy.WHITE,color_policy=config.ColorPolicy.BLACK)
    Frontend(RenderContext(doc),backend,config=settings).draw_layout(doc.modelspace(),finalize=True)
    return backend.get_string(layout.Page(297,210,layout.Units.mm,layout.Margins(12,12,12,12))).encode()

def safe_json(value):
    return json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False).replace('<','\\u003c').replace('&','\\u0026')

def write_report(directory):
    report=json.loads((directory/'results.json').read_text())
    parts=[];meshes={};pictures={};options=[]
    for o in report['observations']:
        key=o['id'];folder=directory/key
        inf=json.loads((folder/'inference.json').read_text())
        trial=o['trials'][0];status=trial.get('status','failed')
        category='candidate' if status=='candidate' and o['passed'] else 'withheld' if status=='withheld' else 'failed'
        title=LABELS.get(key.rsplit('_',1)[0],key)+' / '+o['format'].upper()
        options.append(f'<option value="{key}">{escape(title)}</option>')
        original=(folder/'input.svg').read_bytes()
        # Display is generated only from the same DXF input; paired native SVG is
        # separately labelled and never consulted by the reconstruction worker.
        if o['format']=='dxf':
            preview=dxf_preview((folder/'input.dxf').read_bytes())
            (folder/'dxf-preview.svg').write_bytes(preview)
            pictures[key]={'top':svg_data(preview),'all':svg_data(original)}
            view_options='<option value="top">入力DXFの描画（ezdxf）</option><option value="all">同じCADページの出力SVG</option>'
        else:
            pictures[key]={'top':svg_data(original)}
            view_options='<option value="top">入力SVGそのもの</option>'
        state='復元・編集を検証' if category=='candidate' else '形式未対応' if o['format']=='svg' else '保留' if category=='withheld' else '評価失敗'
        parts.append(f'<article class="case" data-case="{key}" data-category="{category}"><div class="case-head"><div><span class="case-id">{key}</span><h2>{escape(title)}</h2></div><span class="badge {category}">{state}</span></div><div class="stage-grid">')
        parts.append(f'<section class="panel"><h3>実CADからの図面入力</h3><div class="toolbar"><select class="view-select" aria-label="表示する出力形式">{view_options}</select><button class="image-minus">縮小</button><button class="image-plus">拡大</button><span class="image-scale">100%</span></div><div class="drawing-window"><img class="drawing" alt="{escape(title)}の図面" src="{pictures[key]["top"]}"></div><p class="caption">文字が小さい場合は拡大してスクロール。DXFの描画とFreeCAD出力SVGは表示位置・線種等が異なります。</p></section>')
        if (folder/'comparison.json').exists():
            c=json.loads((folder/'comparison.json').read_text());m=c['metrics'];ed=c['edit_metrics']
            meshes[key]=json.loads((folder/'preview.json').read_text())
            parts.append('<section class="panel"><h3>復元STEPの3D</h3><div class="toolbar"><select class="model-select" aria-label="3Dモデル"><option value="original">復元直後</option><option value="edited">寸法変更後</option></select><button class="reset-camera">視点リセット</button><button class="zoom-out">−</button><button class="zoom-in">＋</button></div><canvas class="preview" width="700" height="420" tabindex="0" aria-label="生成したCADの3D表示"></canvas><p class="caption">ドラッグ・矢印キーで回転、ホイールで拡大。実際の生成STEPのメッシュです。</p></section></div>')
            truth=c['truth_parameters'];rec=c['recovered_parameters']
            rows=[[label,truth[k],rec[k],abs(truth[k]-rec[k])] for label,k in [('幅','width'),('奥行','length'),('厚さ','thickness')]]
            actual=sorted(c['measured_holes'],key=lambda h:(h['x_mm'],h['y_mm']))
            for i,h in enumerate(sorted(truth['holes'],key=lambda h:(h['x'],h['y']))):
                for label,k,mk in [('径','diameter','diameter_mm'),('X','x','x_mm'),('Y','y','y_mm')]:
                    value=actual[i][mk];rows.append([f'穴{i+1} {label}',h[k],value,abs(h[k]-value)])
                value=actual[i]['depth_mm'];rows.append([f'穴{i+1} 貫通長',truth['thickness'],value,abs(truth['thickness']-value)])
            parts.append('<h3>復元直後の寸法照合（mm）</h3><p class="caption">外形は抽出値、穴はSTEPの再計測値。正解CADと設計値は評価側だけで読みます。</p>'+table(['項目','評価用の設計値','抽出／測定値','絶対差'],rows))
            parts.append(table(['検証','実測'],[
                ['有効な単一ソリッド / STEP再読込',f'{m["valid_solid"]} / {m["step_read_success"]}'],
                ['FreeCAD正解STEPとの体積IoU（OCCT系列）',m['same_kernel_volume_iou']],
                ['外形の実測最大誤差 mm',f'{m["bounds_max_abs_error_mm"]:.4g}'],
                ['解析式との体積差 mm³',f'{m["volume_vs_analytic_abs_error_mm3"]:.4g}'],
                ['再投影の最大サンプル残差 mm',f'{max(v["sampled_symmetric_max_mm"] for v in c["projection_metrics"].values()):.4g}'],
                ['編集後の有効性 / 穴寸法最大誤差 mm',f'{ed["valid_solid"]} / {ed["hole_max_abs_error_mm"]}']]))
            parts.append('<p class="edit-note">保存した編集結果: 幅+5 mm、厚さ+2 mm、穴があれば径とXを各+1 mm。HTML内での寸法入力・再計算は行いません。</p><h3>入力輪郭とCAD再投影</h3><p class="caption">灰: DXFから取得した輪郭、青: 生成B-RepのHLR。線の可視性分類は評価対象外。</p>'+overlay_svg(c['views'],c['reprojection']))
            parts.append('<nav class="downloads">'+''.join(f'<a href="{key}/{name}" download>{label}</a>' for name,label in [('candidate.step','復元STEP'),('edited.step','編集後STEP'),('candidate.py','編集用Python'),('model.json','設計モデル')])+'</nav>')
        else:
            reason=REASONS.get(inf.get('reason_code'),trial.get('detail',inf.get('detail','要調査')))
            parts.append(f'<section class="panel withheld-panel"><h3>CADは生成していません</h3><p>{escape(reason)}</p><code>{escape(inf.get("reason_code") or trial.get("failure_stage") or "failed")}</code><p class="caption">保留例に正解CADを代わりに表示することはありません。</p></section></div>')
        evidence=inf.get('dimension_evidence',[])
        if evidence:
            parts.append('<details><summary>寸法エンティティと形状の対応根拠</summary>'+table(['ビュー','可視テキスト','値 mm','対象','DXFハンドル','表示ブロック'],
                [[e['view'],e['visible_text'],e['value_mm'],e['parameter'],e['dimension_line_id'],e['text_id']] for e in evidence])+'</details>')
        parts.append('<details><summary>入力条件・形式・出所</summary><p>人の指定: mm、矩形板と分離した貫通丸穴の形状クラス、ビューのレイヤー対応、投影法、原点の取り方。寸法値・縮尺・正解CADは復元に渡しません。</p>')
        parts.append(f'<p>投影法: {escape(inf["human_context"]["projection"])} / 反復: {len(o["trials"])} 回 / 出所: {escape(o["provenance"])}</p><p>前回のSVG処理を実CAD出力SVGへ適用: {escape(o["legacy_on_same_input"]["status"])} / {escape(o["legacy_on_same_input"].get("reason_code") or "")}</p><pre class="digest">{escape(json.dumps(inf.get("inventory",{}),ensure_ascii=False,indent=2))}</pre><p class="digest">入力SHA-256: {inf["source_sha256"]}</p></details>')
        parts.append(f'<nav class="downloads"><a href="{key}/input.{o["format"]}" download>元の{ o["format"].upper() }</a><a href="{key}/inference.json">抽出結果JSON</a><a href="{key}/context.json">人が与えた条件</a></nav></article>')
    s=report['summary'];fmt=s['by_format']
    cards=''.join(f'<div class="stat"><span>{label}</span><strong>{value}</strong></div>' for label,value in [
        ('DXF復元・編集の成功',f'{s["candidate_successes"]} / {s["candidate_inputs"]}'),
        ('DXFの理由付き保留',fmt['dxf']['withheld']),
        ('SVG復元（形式未対応）',f'0 / {fmt["svg"]["inputs"]}')])
    html='''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>実CADのSVG／DXFからの復元</title><style>'''+CSS+'''pre{white-space:pre-wrap}.drawing-window,.preview{height:460px}</style></head><body><main><header><p class="eyebrow">RESEARCH NOTES · FreeCAD 1.1.4 / TechDraw</p><h1>実CADのSVG／DXFから、どこまで復元できたか</h1><p>FreeCADで部品と寸法図を作り、実際に出力したファイルで検証しました。DXFの限定した寸法情報から、編集できるCADとSTEPを生成できました。</p><p class="scope">自作部品を実CADで出力した開発用対照です。顧客図面、他CAD、未知部品の性能ではありません。SVGの自動復元は未対応として記録しています。</p></header><div class="stats">'''+cards+'''</div><section class="selection"><label>結果<select id="filter"><option value="all">すべて</option><option value="candidate">復元・編集を検証</option><option value="withheld">保留／形式未対応</option><option value="failed">評価失敗</option></select></label><label class="case-picker">確認する例<select id="case-picker">'''+''.join(options)+'''</select></label><span id="case-count"></span></section><p id="empty" hidden>該当する結果はありません。</p>'''+''.join(parts)+'''<footer><h2>今回分かったこと</h2><p>DXFのDIMENSIONには値・方向・接続点が残ります。一方、SVGでは変換行列とベジェ曲線の正規化が必要です。DXFでも公差や寸法不足は保留しました。表示形式を変えるだけで全図面を解釈できるわけではありません。</p><p>正解はFreeCAD / OCCT 7.8.1、復元は既存基盤 / OCCT 7.9.3.1。同じカーネル系列のため独立カーネル検証ではありません。人の形状クラス・投影法・ビュー対応の指定は残ります。</p><p>閲覧はHTML単体・オフラインで可能。ダウンロードには隣のケースフォルダーも必要です。外部通信とCAD再計算はありません。</p><p><a href="../../notes/cad-drawing-exports.md">研究ノートと次の計画</a> · <a href="../../docs/cad-drawing-exports.md">再現手順</a> · <a href="../drawing-dimensions/report.html">前回の自作SVG実験</a> · <a href="results.json">全観測JSON</a> · <a href="summary.csv">CSV</a></p></footer></main><script type="application/json" id="meshes">'''+safe_json(meshes)+'''</script><script type="application/json" id="pictures">'''+safe_json(pictures)+'''</script><script>'''+JS.replace('one_third','one_dxf')+'''</script></body></html>'''
    (directory/'report.html').write_text(html,encoding='utf-8')

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);write_report(p.parse_args().directory)
