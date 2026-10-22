"""Self-contained, offline HTML for saved drawing/CAD observations (no solver UI)."""
from __future__ import annotations

import base64
from html import escape
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

LABELS = {
    "plain_third": "無孔プレート", "one_third": "1穴プレート・第三角法", "one_first": "1穴プレート・第一角法",
    "two_third": "2穴プレート", "one_scaled": "図面の縮尺を変更", "one_anonymous": "IDと描画順を変更",
    "decimal_plate": "寸法を変えた小数値のプレート", "two_reordered": "2穴・描画順を変更",
    "missing_position": "穴の位置寸法が不足", "missing_thickness": "厚さ寸法が不足",
    "conflicting_width": "ビュー間で幅が矛盾", "ambiguous_label": "寸法値の対応が曖昧",
    "missing_extension": "補助線が欠落", "wrong_projection": "投影法の指定が不整合",
    "diameter_conflict": "穴径と円が不一致", "ambiguous_extent": "貫通・止まりが不明",
    "unsupported_tolerance": "公差付き寸法（未対応）", "chain_dimension": "連鎖寸法（未対応）",
    "leader_misses_hole": "穴径の引出線が円に接続しない", "unsupported_radius": "半径注記（未対応）",
}
REASONS = {
    "hole_position_missing": ("穴の位置寸法を揃えられませんでした。", "穴中心のX/Y寸法と、その寸法線の接続を確認してください。"),
    "dimension_missing": ("必要な外形寸法が不足しています。", "厚さなど、3D形状を決めるための寸法を追加してください。"),
    "dimension_conflict": ("同じ寸法について一致しない値があります。", "正面・平面・側面の寸法値を照合してください。"),
    "dimension_text_ambiguous": ("1本の寸法線に複数の数値が対応します。", "どの寸法値が有効か、図面上で確認してください。"),
    "extension_missing": ("寸法線から形状へつながる補助線を確認できません。", "補助線の欠落・切れ・今回の対応範囲外の表記を確認してください。"),
    "projection_layout_conflict": ("投影法の指定とビューの配置が一致しません。", "第一角法・第三角法と、各ビューの対応を確認してください。"),
    "annotation_geometry_mismatch": ("注記の穴径・位置と図形が一致しません。", "数値と輪郭を確認し、どちらを採用するか判断してください。"),
    "hole_extent_ambiguous": ("穴の貫通・止まりを確定できません。", "貫通指示や穴の深さを確認してください。図だけから貫通と仮定しません。"),
    "unsupported_annotation": ("この実験では扱わない寸法表記です。", "公差・半径等を、今回扱う公称寸法と区別して確認してください。"),
    "unsupported_dimension_chain": ("この寸法の基準・連鎖を解釈できません。", "今回対応するのは左端・下端から穴中心への基準寸法です。"),
    "leader_target_missing": ("穴径の引出線が円に接続していません。", "引出線がどの穴を指すか確認してください。"),
}


def table(headers, rows):
    head = "".join(f"<th>{escape(str(v))}</th>" for v in headers)
    body = "".join("<tr>"+"".join(f"<td>{escape(str(v))}</td>" for v in row)+"</tr>" for row in rows)
    return f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def svg_data(source):
    return "data:image/svg+xml;base64,"+base64.b64encode(source).decode("ascii")


def drawing_images(source, roles):
    """A data-URL image keeps SVG content outside the report's active DOM."""
    result = {"all": svg_data(source)}
    root = ET.fromstring(source)
    for name, identifier in roles.items():
        group = next(e for e in root if e.get("id") == identifier)
        xs, ys = [], []
        for e in group:
            kind = e.tag.split("}")[-1]
            if kind == "rect":
                x,y,w,h = (float(e.get(k)) for k in ("x", "y", "width", "height"))
                xs.extend((x, x+w)); ys.extend((y, y+h))
            elif kind == "circle":
                x,y,r = (float(e.get(k)) for k in ("cx", "cy", "r"))
                xs.extend((x-r, x+r)); ys.extend((y-r, y+r))
            elif kind == "line":
                xs.extend(float(e.get(k)) for k in ("x1", "x2")); ys.extend(float(e.get(k)) for k in ("y1", "y2"))
            elif kind == "polygon":
                values = list(map(float, e.get("points").replace(",", " ").split()))
                xs.extend(values[::2]); ys.extend(values[1::2])
            elif kind == "text":
                x,y = float(e.get("x")), float(e.get("y"))
                xs.extend((x-3, x+len(e.text or "")*7)); ys.extend((y-15, y+4))
        view = ET.Element("svg", xmlns="http://www.w3.org/2000/svg",
                          viewBox=f"{min(xs)-18} {min(ys)-18} {max(xs)-min(xs)+36} {max(ys)-min(ys)+36}")
        view.append(group)
        result[name] = svg_data(ET.tostring(view))
    return result


def overlay_svg(views, projected):
    from math import cos, sin, tau
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 310" role="img" aria-label="入力輪郭とCAD再投影の比較">']
    for index, (name, label) in enumerate((("front", "正面"), ("top", "平面"), ("right", "右側面"))):
        u,v = views[name]["extent_mm"]
        factor = min(245/u, 220/v)
        def poly(points, color, width, dash=""):
            xy = " ".join(f"{index*300+25+p[0]*factor:.5f},{270-p[1]*factor:.5f}" for p in points)
            return f'<polyline points="{xy}" stroke="{color}" stroke-width="{width}" stroke-dasharray="{dash}" fill="none"/>'
        parts.append(f'<text x="{index*300+25}" y="27" font-size="17" fill="#31434e">{label}</text>')
        drawing = [[[0,0],[u,0],[u,v],[0,v],[0,0]], *views[name]["hidden_lines"]]
        for c in views[name]["circles"]:
            drawing.append([[c["center"][0]+c["radius"]*cos(tau*j/128), c["center"][1]+c["radius"]*sin(tau*j/128)] for j in range(129)])
        parts.extend(poly(line, "#a7b1b9", 4) for line in drawing)
        for visibility in ("visible", "hidden"):
            parts.extend(poly(line, "#087d9d", 1.3, "5 3" if visibility == "hidden" else "") for line in projected[name][visibility])
    return "".join(parts)+"</svg>"


def render_report(report, artifacts):
    summary = report["summary"]
    sections, meshes, pictures = [], {}, {}
    for observation in report["observations"]:
        identifier = observation["id"]
        if not re.fullmatch(r"[a-z0-9_]+", identifier):
            raise ValueError("unsafe case ID")
        artifact = artifacts[identifier]
        inference = artifact["inference"]
        trial = observation["trials"][0]
        status = trial.get("status", "failed")
        category = "candidate" if status == "candidate" and observation["passed"] else "withheld" if status == "withheld" else "failed"
        state = {"candidate": "復元・編集を検証", "withheld": "保留（想定どおり）" if observation["passed"] else "保留（要調査）", "failed": "評価失敗"}[category]
        pictures[identifier] = drawing_images(artifact["source"], inference["human_context"]["view_roles"])
        header = f'<article class="case" data-case="{identifier}" data-category="{category}"><div class="case-head"><div><span class="case-id">{identifier}</span><h2>{escape(LABELS.get(identifier, identifier))}</h2></div><span class="badge {category}">{state}</span></div>'
        projection = "第三角法" if inference["human_context"]["projection"] == "third_angle" else "第一角法"
        input_panel = f'''<section class="panel"><h3>入力図面 <small>{projection} / mm</small></h3>
<div class="toolbar"><label>表示 <select class="view-select" aria-label="図面の表示範囲"><option value="all">三面図全体</option><option value="top" selected>平面図</option><option value="front">正面図</option><option value="right">右側面図</option></select></label><button class="image-minus" type="button">縮小</button><button class="image-plus" type="button">拡大</button><span class="image-scale">100%</span></div>
<div class="drawing-window"><img class="drawing" alt="{escape(LABELS.get(identifier, identifier))}の入力寸法図" src="{pictures[identifier]['top']}"></div><p class="caption">表示範囲を切り替えて三面を確認できます。拡大後はスクロールできます。</p></section>'''
        body = ""
        if artifact.get("comparison") and artifact.get("preview"):
            comparison = artifact["comparison"]
            meshes[identifier] = artifact["preview"]
            preview_panel = '''<section class="panel"><h3>生成STEPの3D表示</h3><div class="toolbar"><label>モデル <select class="model-select" aria-label="3Dモデル"><option value="original">復元したモデル</option><option value="edited">寸法変更後</option></select></label><button class="reset-camera" type="button">視点リセット</button><button class="zoom-out" type="button" aria-label="3Dを縮小">−</button><button class="zoom-in" type="button" aria-label="3Dを拡大">＋</button></div><canvas class="preview" width="700" height="420" aria-label="生成B-Repの回転可能な3Dプレビュー" tabindex="0"></canvas><p class="caption">ドラッグで回転、ホイールで拡大縮小、矢印キーで回転。保存したB-Repの表示です。寸法変更後も視点を維持します。</p></section>'''
            truth, recovered = comparison["truth_parameters"], comparison["recovered_parameters"]
            rows = [[label, truth[k], recovered[k], abs(truth[k]-recovered[k])] for label,k in (("幅", "width"), ("奥行", "length"), ("厚さ", "thickness"))]
            actual = sorted(comparison["measured_holes"], key=lambda h: (h["x_mm"], h["y_mm"]))
            for index, hole in enumerate(sorted(truth["holes"], key=lambda h: (h["x"], h["y"]))):
                for label, key, measured_key in (("径", "diameter", "diameter_mm"), ("X", "x", "x_mm"), ("Y", "y", "y_mm")):
                    value = actual[index][measured_key] if index < len(actual) else "未取得"
                    rows.append([f"穴{index+1} {label}", hole[key], value, abs(hole[key]-value) if isinstance(value, (int,float)) else "不明"])
                depth = actual[index]["depth_mm"] if index < len(actual) else None
                rows.append([f"穴{index+1} 貫通長", truth["thickness"], depth if depth is not None else "未取得",
                             abs(truth["thickness"]-depth) if depth is not None else "不明"])
            m = comparison["metrics"]
            body += '<h3>復元直後の寸法照合（mm）</h3><p class="caption">外形は図面からの抽出値、穴は生成STEPを再計測した値。正解設計値は評価側だけで使用しています。</p>'
            body += table(["項目", "評価用の正解設計値", "抽出値 / STEP測定値", "絶対差"], rows)
            body += '<div class="metrics">'+table(["評価", "観測値"], [
                ["有効な単一ソリッド / STEP再読込", f'{m["valid_solid"]} / {m["step_read_success"]}'],
                ["同じOCCTによる体積IoU", m["same_kernel_volume_iou"]],
                ["解析式との体積差 mm³", f'{m["volume_vs_analytic_abs_error_mm3"]:.4g}'],
                ["外形の実測最大誤差 mm", f'{m["bounds_max_abs_error_mm"]:.4g}'],
                ["再投影のサンプル最大残差 mm", f'{max(p["sampled_symmetric_max_mm"] for p in comparison["projection_metrics"].values()):.4g}'],
                ["寸法変更後の穴寸法最大誤差 mm", comparison["edit_metrics"]["hole_max_abs_error_mm"]]] )+'</div>'
            p = comparison["edited_parameters"]
            body += f'<p class="edit-note">保存した変更: 幅 {truth["width"]} → {p["width"]} mm、厚さ {truth["thickness"]} → {p["thickness"]} mm。穴があれば左端の穴の径とXを各+1 mm。3D表示で「寸法変更後」を選べます。</p>'
            body += '<h3>元図面の輪郭と、生成STEPの再投影</h3><p class="caption">灰色: 入力輪郭 / 青色: 実際のB-RepのHLR。可視線と隠れ線を合わせたサンプル線集合で比較しています。</p>'
            body += overlay_svg(comparison["views"], comparison["reprojection"])
            body += '<nav class="downloads" aria-label="成果物">'+"".join(f'<a href="{identifier}/{name}" download>{label}</a>' for name,label in (
                ("candidate.step", "復元STEP"), ("edited.step", "変更後STEP"), ("candidate.py", "編集用Python"),
                ("model.json", "設計モデルJSON"), ("inference.json", "抽出の根拠JSON")))+'</nav>'
        else:
            reason, next_action = REASONS.get(inference.get("reason_code"), ("この入力から候補を生成できませんでした。", "下の理由と入力図面を確認してください。"))
            preview_panel = f'<section class="panel withheld-panel"><h3>CADは生成していません</h3><p>{escape(reason)}</p><p><strong>次の確認:</strong> {escape(next_action)}</p><code>{escape(inference.get("reason_code") or trial.get("failure_stage") or "failed")}</code><p class="caption">正解モデルを代わりに表示することはありません。</p></section>'
            body += f'<p class="reason-detail">処理の記録: {escape(inference.get("detail") or trial.get("detail") or "")}</p>'
        evidence = inference.get("dimension_evidence", [])
        if evidence:
            body += '<details><summary>寸法値をどの線・形状へ対応付けたか</summary>'+table(
                ["ビュー", "可視テキスト", "取得値 mm", "対象", "寸法線 / 引出線ID", "テキストID"],
                [[e["view"], e["visible_text"], e["value_mm"], e.get("parameter") or e.get("circle_id") or e["kind"],
                  e["dimension_line_id"], e["text_id"]] for e in evidence])+"</details>"
        body += f'<details><summary>条件・対照結果・出所</summary><p>人の指定: {projection}、mm、ビュー対応、矩形板と分離したZ方向貫通丸穴という仮定。反復 {len(observation["trials"])} 回。</p><p>従来の専用注記パーサーを同じ入力に適用: {escape(observation["legacy_on_same_input"]["status"])} / {escape(observation["legacy_on_same_input"].get("reason_code") or "")}</p><p class="digest">入力SHA-256: {escape(inference["source_sha256"])}</p><a href="{identifier}/input.svg" download>元のSVG</a> · <a href="{identifier}/inference.json">解釈JSON</a></details>'
        sections.append(header+'<div class="stage-grid">'+input_panel+preview_panel+'</div>'+body+'</article>')
    def safe_json(value):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).replace("<", "\\u003c").replace("&", "\\u0026")
    cards = "".join(f'<div class="stat"><span>{escape(label)}</span><strong>{value}</strong></div>' for label,value in (
        ("復元・編集を通過した入力", f'{summary["candidate_successes"]} / {summary["candidate_inputs"]}'),
        ("理由付き保留が想定と一致", f'{summary["correct_withholds"]} / {summary["withheld_controls"]}'),
        ("保留対照での誤確定", str(summary["false_confirmations"]))))
    options = "".join(f'<option value="{o["id"]}">{escape(LABELS.get(o["id"],o["id"]))}</option>' for o in report["observations"])
    return '''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>寸法線からのCAD復元 — 実験結果</title><style>'''+CSS+'''</style></head><body><main>
<header><p class="eyebrow">RESEARCH NOTES · 独立した探索研究</p><h1>寸法線からのCAD復元 — 実験結果</h1><p>寸法線・補助線・矢印・数値を結び付け、穴付き板の編集可能なCADを生成できるか確かめました。</p><p class="scope">自作SVGの限定した対照実験です。投影法・部品種別・ビュー対応は人が指定。画像OCRや任意の実務図面の性能ではありません。</p></header>
<div class="stats">'''+cards+'''</div><section class="selection"><label>結果 <select id="filter"><option value="all">すべて</option><option value="candidate">復元・編集を検証</option><option value="withheld">保留</option><option value="failed">評価失敗</option></select></label><label class="case-picker">確認する例 <select id="case-picker">'''+options+'''</select></label><span id="case-count" aria-live="polite"></span></section><p id="empty" hidden>この分類の結果はありません。</p><noscript><p>JavaScriptを有効にすると例の切替・3Dの回転ができます。</p></noscript>'''+"".join(sections)+'''
<footer><h2>この結果をどう読むか</h2><p>同じOCCTから生成した評価用正解と比較しています。合成入力の派生は独立した部品ではなく、未知ファミリーの検証でもありません。STEPに元作者の履歴が復元されるわけではありません。編集には保存したPython / JSONを使います。</p><p>HTML単体で図面・3D・数値を閲覧できます。STEP等のダウンロードには隣接フォルダーも必要です。外部通信やCAD再計算は行いません。</p><p><a href="../../notes/drawing-dimension-lines.md">研究ノートと今後の計画</a> · <a href="../../docs/drawing-dimension-lines.md">再現手順</a> · <a href="results.json">全観測JSON</a> · <a href="summary.csv">要約CSV</a></p></footer>
</main><script type="application/json" id="meshes">'''+safe_json(meshes)+'''</script><script type="application/json" id="pictures">'''+safe_json(pictures)+'''</script><script>'''+JS+'''</script></body></html>'''


def write_report(directory: Path):
    report = json.loads((directory / "results.json").read_text(encoding="utf-8"))
    artifacts = {}
    for o in report["observations"]:
        path = directory / o["id"]
        entry = {"source": (path / "input.svg").read_bytes(),
                 "inference": json.loads((path / "inference.json").read_text(encoding="utf-8"))}
        for key, name in (("comparison", "comparison.json"), ("preview", "preview.json")):
            if (path / name).exists():
                entry[key] = json.loads((path / name).read_text())
        artifacts[o["id"]] = entry
    (directory / "report.html").write_text(render_report(report, artifacts), encoding="utf-8")


CSS = r'''
:root{color-scheme:light;font-family:system-ui,"Yu Gothic",sans-serif;color:#20313e;background:#f3f5f6}*{box-sizing:border-box}body{margin:0}main{max-width:1440px;margin:auto;padding:34px 28px}header{max-width:950px}.eyebrow{font-size:12px;letter-spacing:.1em;color:#526874}h1{font-size:clamp(25px,3vw,36px);line-height:1.5;margin:8px 0}h2{font-size:23px;margin:5px 0}h3{font-size:17px}p{line-height:1.8}.scope,.caption{color:#576975}.scope{font-size:14px}.caption{font-size:12px;margin:8px 0}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:24px 0}.stat,.selection,.case,footer{background:white;border:1px solid #d9e1e5;border-radius:12px}.stat{padding:17px 22px}.stat span{display:block;font-size:13px;color:#566976}.stat strong{display:block;font-size:30px;margin-top:5px}.selection{display:flex;align-items:center;gap:20px;padding:16px;margin-bottom:24px}label{font-size:13px;font-weight:600;display:flex;align-items:center;gap:9px}.case-picker{flex:1}.case-picker select{min-width:180px;width:100%}select,button{font:inherit;border:1px solid #bdcbd3;background:white;border-radius:6px;padding:8px;color:#243d4b}button{cursor:pointer}button:hover{background:#eaf3f6}button:focus-visible,select:focus-visible,canvas:focus-visible{outline:3px solid #259abd;outline-offset:2px}#case-count{font-size:13px;white-space:nowrap}.case{padding:26px;margin-bottom:24px}.case-head{display:flex;justify-content:space-between;gap:18px;align-items:center;margin-bottom:15px}.case-id{font:12px ui-monospace,monospace;color:#677b88}.badge{border-radius:99px;padding:8px 13px;white-space:nowrap;font-size:12px;font-weight:600}.badge.candidate{background:#e0f1ed;color:#176854}.badge.withheld{background:#fff0d6;color:#80530e}.badge.failed{background:#fae4e4;color:#a52d2d}.stage-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}.panel{min-width:0;background:#fafcfd;border:1px solid #e0e7eb;border-radius:9px;padding:15px}.panel h3{margin:0 0 13px}small{font-size:11px;font-weight:400;margin-left:8px;color:#576975}.toolbar{display:flex;gap:7px;align-items:center;flex-wrap:wrap;font-size:12px;min-height:38px}.toolbar label{font-size:12px}.toolbar select,.toolbar button{padding:6px}.image-scale{font-size:11px;color:#607783}.drawing-window{height:420px;overflow:auto;background:white;border:1px solid #edf0f2;margin-top:12px;display:block}.drawing{display:block;width:100%;height:100%;object-fit:contain;max-width:none}.preview{display:block;width:100%;height:420px;touch-action:none;cursor:grab;background:#f0f4f7;border-radius:6px;margin-top:12px}.preview:active{cursor:grabbing}.withheld-panel{background:#fffaf0;padding:28px}.withheld-panel code{display:inline-block;max-width:100%;overflow-wrap:anywhere;color:#815c25}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px;margin:15px 0}th,td{padding:10px 12px;border-bottom:1px solid #e2e8ec;text-align:left;white-space:nowrap}th{background:#f0f4f6;color:#445d6d}.metrics{max-width:850px}.edit-note{background:#eef5f7;border-left:3px solid #3988a0;padding:10px 14px;font-size:13px}.case>svg{width:100%;max-height:350px;display:block}.downloads{display:flex;gap:12px;flex-wrap:wrap;margin:18px 0}.downloads a{padding:9px 13px;border:1px solid #aecbd5;border-radius:6px}a{color:#08748e;text-decoration-thickness:1px;text-underline-offset:3px}details{padding:14px 0;border-top:1px solid #e0e7ec;font-size:13px}summary{cursor:pointer;font-weight:600}.digest{font:11px ui-monospace,monospace;overflow-wrap:anywhere}.reason-detail{font-size:13px}footer{padding:24px;font-size:13px}footer h2{font-size:18px}[hidden]{display:none!important}@media(max-width:900px){main{padding:20px 12px}.stage-grid{grid-template-columns:1fr}.stats{gap:7px}.stat{padding:14px 10px}.stat strong{font-size:25px}.selection{align-items:stretch;flex-direction:column;gap:12px}.case{padding:16px}.case-head{align-items:start;flex-direction:column}.drawing-window,.preview{height:350px}.toolbar{font-size:11px}}@media print{.selection,.toolbar{display:none}.case[hidden]{display:block!important}.case{break-inside:avoid}footer{break-before:page}}
'''

JS = r'''
"use strict";
const meshes=JSON.parse(document.getElementById("meshes").textContent), pictures=JSON.parse(document.getElementById("pictures").textContent);
const articles=[...document.querySelectorAll("article.case")], picker=document.getElementById("case-picker"), filter=document.getElementById("filter");
const states=new Map();
function render(article){
 const id=article.dataset.case, data=meshes[id]; if(!data)return;
 const canvas=article.querySelector("canvas"), ctx=canvas.getContext("2d"), state=states.get(id);
 const ratio=Math.min(window.devicePixelRatio||1,1.5),width=Math.round((canvas.getBoundingClientRect().width||600)*ratio),height=Math.round((canvas.getBoundingClientRect().height||420)*ratio);
 canvas.width=width;canvas.height=height;
 const p=data[article.querySelector(".model-select").value].polygons;
 const scale=Math.min(width*.8,height*.8)/state.extent*state.zoom;
 function project(v){let x=v[0]-state.center[0],y=v[1]-state.center[1],z=v[2]-state.center[2],a=x*Math.cos(state.yaw)-y*Math.sin(state.yaw),b=x*Math.sin(state.yaw)+y*Math.cos(state.yaw);return [width/2+a*scale,height/2+(b*Math.sin(state.pitch)-z*Math.cos(state.pitch))*scale,b*Math.cos(state.pitch)+z*Math.sin(state.pitch)];}
 // A per-pixel depth buffer is necessary: sorting triangle centroids can paint
 // the bottom face over a through-hole even when the CAD mesh is correct.
 const image=ctx.createImageData(width,height),pixels=image.data,depth=new Float64Array(width*height);depth.fill(-Infinity);
 for(let i=0;i<pixels.length;i+=4){pixels[i]=240;pixels[i+1]=244;pixels[i+2]=247;pixels[i+3]=255;}
 const base=article.querySelector(".model-select").value==="edited"?[186,114,60]:[48,122,150];
 p.forEach(original=>{
  const t=original.map(project),a=original[1].map((v,i)=>v-original[0][i]),b=original[2].map((v,i)=>v-original[0][i]),normal=[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]],light=.55+.45*Math.abs(normal[2])/(Math.hypot(...normal)||1),color=base.map(c=>Math.round(c*light));
  const denominator=(t[1][1]-t[2][1])*(t[0][0]-t[2][0])+(t[2][0]-t[1][0])*(t[0][1]-t[2][1]);if(Math.abs(denominator)<1e-12)return;
  const x0=Math.max(0,Math.floor(Math.min(...t.map(v=>v[0])))),x1=Math.min(width-1,Math.ceil(Math.max(...t.map(v=>v[0])))),y0=Math.max(0,Math.floor(Math.min(...t.map(v=>v[1])))),y1=Math.min(height-1,Math.ceil(Math.max(...t.map(v=>v[1]))));
  for(let y=y0;y<=y1;y++)for(let x=x0;x<=x1;x++){
   const u=((t[1][1]-t[2][1])*(x+.5-t[2][0])+(t[2][0]-t[1][0])*(y+.5-t[2][1]))/denominator,v=((t[2][1]-t[0][1])*(x+.5-t[2][0])+(t[0][0]-t[2][0])*(y+.5-t[2][1]))/denominator,w=1-u-v;
   if(u< -1e-8||v< -1e-8||w< -1e-8)continue;const z=u*t[0][2]+v*t[1][2]+w*t[2][2],index=y*width+x;
   if(z>depth[index]){depth[index]=z;const k=index*4;pixels[k]=color[0];pixels[k+1]=color[1];pixels[k+2]=color[2];}
  }
 });
 ctx.putImageData(image,0,0);ctx.fillStyle="#566b79";ctx.font=(12*ratio)+"px system-ui";ctx.fillText("mm · 保存したSTEP由来の表示",14*ratio,height-14*ratio);canvas.dataset.rendered="true";
}
articles.forEach(article=>{
 const id=article.dataset.case,img=article.querySelector("img.drawing"), view=article.querySelector(".view-select");let imageZoom=1;
 function showImage(){img.src=pictures[id][view.value];img.style.width=(imageZoom*100)+"%";img.style.height=(imageZoom*100)+"%";article.querySelector(".image-scale").textContent=Math.round(imageZoom*100)+"%";}
 view.value="top";showImage();
 view.addEventListener("change",()=>{imageZoom=1;showImage();});
 article.querySelector(".image-plus").onclick=()=>{imageZoom=Math.min(4,imageZoom+.5);showImage();};article.querySelector(".image-minus").onclick=()=>{imageZoom=Math.max(1,imageZoom-.5);showImage();};
 if(!meshes[id])return;
 const pts=Object.values(meshes[id]).flatMap(m=>m.polygons.flat()),lo=[0,1,2].map(i=>Math.min(...pts.map(p=>p[i]))),hi=[0,1,2].map(i=>Math.max(...pts.map(p=>p[i])));
 const state={center:lo.map((v,i)=>(v+hi[i])/2),extent:Math.max(...hi.map((v,i)=>v-lo[i])),yaw:.62,pitch:.75,zoom:1};states.set(id,state);
 const canvas=article.querySelector("canvas");let drag=null;
 canvas.addEventListener("pointerdown",e=>{drag=[e.clientX,e.clientY];canvas.setPointerCapture(e.pointerId);});
 canvas.addEventListener("pointermove",e=>{if(!drag)return;state.yaw+=(e.clientX-drag[0])*.009;state.pitch=Math.max(.08,Math.min(1.49,state.pitch+(e.clientY-drag[1])*.009));drag=[e.clientX,e.clientY];render(article);});
 ["pointerup","pointercancel","lostpointercapture"].forEach(name=>canvas.addEventListener(name,()=>{drag=null;}));
 canvas.addEventListener("wheel",e=>{e.preventDefault();state.zoom=Math.max(.4,Math.min(3,state.zoom*Math.exp(-e.deltaY*.001)));render(article);},{passive:false});
 canvas.addEventListener("keydown",e=>{if(!["ArrowLeft","ArrowRight","ArrowUp","ArrowDown"].includes(e.key))return;e.preventDefault();state.yaw+=e.key==="ArrowLeft"?-.15:e.key==="ArrowRight"?.15:0;state.pitch=Math.max(.08,Math.min(1.49,state.pitch+(e.key==="ArrowUp"?.12:e.key==="ArrowDown"?-.12:0)));render(article);});
 article.querySelector(".reset-camera").onclick=()=>{state.yaw=.62;state.pitch=.75;state.zoom=1;render(article);};
 article.querySelector(".zoom-in").onclick=()=>{state.zoom=Math.min(3,state.zoom*1.2);render(article);};article.querySelector(".zoom-out").onclick=()=>{state.zoom=Math.max(.4,state.zoom/1.2);render(article);};article.querySelector(".model-select").onchange=()=>render(article);
});
function choose(){articles.forEach(a=>{a.hidden=a.dataset.case!==picker.value;});const a=articles.find(a=>a.dataset.case===picker.value);if(a)render(a);}
function applyFilter(){const available=articles.filter(a=>filter.value==="all"||a.dataset.category===filter.value),previous=picker.value;picker.replaceChildren(...available.map(a=>{let o=document.createElement("option");o.value=a.dataset.case;o.textContent=a.querySelector("h2").textContent;return o;}));if(available.some(a=>a.dataset.case===previous))picker.value=previous;document.getElementById("case-count").textContent=available.length+" 入力";document.getElementById("empty").hidden=available.length!==0;choose();}
picker.addEventListener("change",choose);filter.addEventListener("change",applyFilter);picker.value=articles.some(a=>a.dataset.case==="one_third")?"one_third":articles[0].dataset.case;applyFilter();window.addEventListener("resize",()=>{const a=articles.find(a=>!a.hidden);if(a)render(a);});
'''


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    write_report(parser.parse_args().directory)
