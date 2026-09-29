"""Self-contained, script-free HTML comparison reports with server-rendered SVG."""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import json
import math

from research_notes.cad_api import CadAPIError
from research_notes.revision_detection import COLORS, STATUS_LABELS


def camera_values(camera):
    if not isinstance(camera, dict):
        raise CadAPIError("invalid_request", "表示条件の指定が不正です。")
    values = {"yaw": camera.get("yaw", .65), "pitch": camera.get("pitch", -.55), "zoom": camera.get("zoom", 1.)}
    if any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 1e6 for v in values.values()):
        raise CadAPIError("invalid_request", "視点には有限の数値を指定してください。")
    if values["zoom"] not in (.5, 1., 1.5, 2.):
        raise CadAPIError("invalid_request", "拡大率の指定が不正です。")
    edges = camera.get("edges", False)
    if type(edges) is not bool:
        raise CadAPIError("invalid_request", "辺表示の指定が不正です。")
    return {**values, "edges": edges}


def preview_svgs(state, camera):
    points = [p for side in ("old", "new") for poly in state[side]["polygons"] for p in poly]
    low = [min(p[i] for p in points) for i in range(3)]
    high = [max(p[i] for p in points) for i in range(3)]
    center = [(a+b)/2 for a, b in zip(low, high)]
    scale = 285 * camera["zoom"] / max(*(b-a for a, b in zip(low, high)), 1e-9)
    yaw, pitch = camera["yaw"], camera["pitch"]
    def project(p):
        x, y, z = [v-c for v, c in zip(p, center)]
        a, b = x*math.cos(yaw)-y*math.sin(yaw), x*math.sin(yaw)+y*math.cos(yaw)
        return (380+a*scale, 220-(b*math.cos(pitch)-z*math.sin(pitch))*scale,
                (b*math.sin(pitch)+z*math.cos(pitch))*scale)
    def coordinates(points):
        return " ".join(f"{p[0]:.5f},{p[1]:.5f}" for p in points)
    result = {}
    for side in ("old", "new"):
        data = state[side]
        triangles = [(list(map(project, p)), face) for p, face in zip(data["polygons"], data["polygon_face_ids"])]
        parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 440" role="img" aria-label="{side} comparison">']
        for pts, face in sorted(triangles, key=lambda item: sum(p[2] for p in item[0])):
            a, b = [[pts[j][i]-pts[0][i] for i in range(3)] for j in (1, 2)]
            n = (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
            light = .7+.3*abs(n[2])/(math.hypot(*n) or 1)
            status = state["analysis"]["face_status"][side].get(str(face), "unresolved")
            color = COLORS[status]
            rgb = [math.floor(int(color[i:i+2], 16)*light+.5) for i in (1, 3, 5)]
            parts.append(f'<polygon points="{coordinates(pts)}" fill="rgb({rgb[0]},{rgb[1]},{rgb[2]})"/>')
        if camera["edges"]:
            for edge in data["edges"]:
                parts.append(f'<polyline points="{coordinates(map(project, edge["points"]))}" fill="none" stroke="#315965" stroke-width="1.5"/>')
        for marker in state["analysis"]["markers"][side]:
            x, y, _ = project(marker["position"])
            parts.append(f'<line x1="{x}" y1="{y}" x2="{x+16}" y2="{y-16}" stroke="#243b47"/>')
            parts.append(f'<circle cx="{x+16}" cy="{y-16}" r="13" fill="white" stroke="{COLORS[marker["status"]]}" stroke-width="3"/>')
            parts.append(f'<text x="{x+16}" y="{y-12}" text-anchor="middle" font-size="11" fill="#243b47">{escape(marker["label"])}</text>')
        result[side] = "".join(parts) + "</svg>"
    return result


def render_report(state, camera=None):
    if not state["old"] or not state["new"]:
        raise CadAPIError("no_source", "旧版と新版の両方を開いてからレポートを保存してください。")
    camera = camera_values({} if camera is None else camera)
    analysis = state["analysis"]
    e = lambda value: escape(str(value), quote=True)
    number = lambda value: f"{value:.6f}"
    def table(headers, rows):
        head = "".join(f"<th>{e(x)}</th>" for x in headers)
        body = "".join("<tr>" + "".join(f"<td>{e(x)}</td>" for x in row) + "</tr>" for row in rows)
        return f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'
    def status_text(status):
        return STATUS_LABELS[status]
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    svg = preview_svgs(state, camera)
    legend = " ".join(f'<span class="legend"><i style="background:{c}"></i>{e(STATUS_LABELS[s])}</span>' for s, c in COLORS.items())
    names = {side: e(state[side]["file_name"]) for side in ("old", "new")}
    sources = table(["項目", "旧版", "新版"], [
        ["ファイル名", state["old"]["file_name"], state["new"]["file_name"]],
        ["SHA-256", state["old"]["source_sha256"], state["new"]["source_sha256"]],
        ["単位", state["old"]["length_unit"], state["new"]["length_unit"]]])
    metric_rows = []
    for label, key in (("体積 mm³", "absolute_volume"), ("面積 mm²", "surface_area"), ("面数", "face_count"), ("辺数", "edge_count")):
        values = [state[side]["metrics"][key] for side in ("old", "new")]
        metric_rows.append([label, *map(number, values), number(values[1]-values[0])])
    metrics = table(["項目", "旧版", "新版", "差（新版 − 旧版）"], metric_rows)
    dimensions = table(["対応箇所", "測定寸法", "旧値 mm", "新値 mm", "差 mm", "判定"],
        [[d["label"], d["name"], number(d["old"]), number(d["new"]), number(d["delta"]), status_text(d["status"])] for d in analysis["dimensions"]])
    if not analysis["dimensions"]:
        dimensions = "<p>対応が確認できた寸法はありません。判定保留の理由を確認してください。</p>"
    regions = table(["箇所", "判定", "旧版の面", "新版の面", "根拠・保留理由"],
        [[r["label"], status_text(r["status"]), ", ".join(map(str, r["old_faces"])) or "—",
          ", ".join(map(str, r["new_faces"])) or "—", r["reason"]] for r in analysis["regions"]])
    face_relations = table(["面の対応", "旧版の面", "新版の面", "判定"],
        [[r["role"], r["old_faces"], r["new_faces"], status_text(r["status"])] for r in analysis["face_relations"]])
    unresolved = "<ul>" + "".join(f"<li>{e(reason)}</li>" for reason in analysis["unresolved"]) + "</ul>" if analysis["unresolved"] else "<p>今回の限定した比較条件内では、判定保留の箇所はありません。</p>"
    conditions = analysis["conditions"]
    condition_rows = [["ソフトウェア", "Research CAD " + state["comparison_version"]], ["作成時刻 UTC", now],
        ["長さの比較許容差 mm", conditions["length_tolerance_mm"]],
        ["形状再構成の相対許容差", conditions["fit_relative_tolerance"]],
        ["穴の対応検索距離 mm", conditions["hole_search_distance_mm"] if conditions["hole_search_distance_mm"] is not None else "対象外"],
        ["位置の基準", conditions["position_reference"]], ["対応付け", conditions["matching_policy"]],
        ["視点（yaw, pitch, zoom）", f"{camera['yaw']}, {camera['pitch']}, {camera['zoom']}"],
        ["対象", "軸に平行な長方形の板と、互いに離れたZ軸方向の貫通穴。自動位置合わせなし。"]]
    for side, label in (("old", "旧版"), ("new", "新版")):
        descriptor = state[side]["features"]
        condition_rows.append([label + "の形状確認", descriptor["reason"]])
        if descriptor["status"] == "qualified":
            condition_rows.append([label + "の材料差 / 閾値 mm³", f"{descriptor['material_residual_mm3']:.9g} / {descriptor['material_gate_mm3']:.9g}"])
    condition_table = table(["比較条件", "内容"], condition_rows)
    # All embedded data is non-executable and source labels never become markup.
    data = {k: v for k, v in state.items() if k != "revision_token"}
    data["report_camera"] = camera
    encoded = json.dumps(data, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c").replace("&", "\\u0026")
    title = "判定保留あり" if analysis["unresolved"] else "限定した対象範囲で比較完了"
    return f'''<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>STEP確認レポート · Research CAD {e(state['comparison_version'])}</title>
<style>body{{font:14px system-ui;margin:0;background:#f2f5f7;color:#243b47}}main{{max-width:1200px;margin:auto;padding:24px}}h1{{font-size:25px}}h2{{font-size:19px}}section{{background:white;padding:22px;margin:18px 0;border:1px solid #dce5e9;border-radius:8px;break-inside:avoid}}p,li{{line-height:1.8}}.pair{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}svg{{width:100%;background:#f6fafb;border:1px solid #dce5e9}}table{{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}}th,td{{text-align:left;padding:10px;border-bottom:1px solid #dde7eb;overflow-wrap:anywhere}}th{{background:#edf3f5}}.scroll{{overflow:auto}}.legend{{display:inline-flex;gap:6px;align-items:center;margin:5px 12px 5px 0}}i{{display:inline-block;width:13px;height:13px;border-radius:3px}}.name{{overflow-wrap:anywhere}}@media(max-width:700px){{.pair{{grid-template-columns:1fr}}main{{padding:12px}}}}@media print{{body{{background:white}}main{{padding:0}}section{{border:0;padding:10px 0}}}}</style></head><body><main>
<h1>STEP確認レポート</h1><p>Research CAD {e(state['comparison_version'])} · {e(title)} · {e(now)}</p>
<p>{e(conditions['measurement_scope'])} 許容差内という表示は、設計履歴や属性の同一性を意味しません。</p>
<section><h2>比較図</h2><div>{legend}</div><div class="pair"><div><h3 class="name">旧版: {names['old']}</h3>{svg['old']}</div><div><h3 class="name">新版: {names['new']}</h3>{svg['new']}</div></div><p>保存時の視点と共通縮尺で描画した診断用の三角形表示です。色は面全体の分類で、変更された材料領域の厳密な境界ではありません。</p></section>
<section><h2>寸法差</h2>{dimensions}</section><section><h2>変更候補・追加・削除と根拠</h2>{regions}</section>
<section><h2>判定保留</h2>{unresolved}</section><section><h2>全体の測定値</h2>{metrics}<p>体積や面積の一致だけでは、形状一致と判断しません。</p></section>
<section><h2>面の対応</h2>{face_relations}</section><section><h2>入力ファイル</h2>{sources}</section>
<section><h2>比較条件</h2>{condition_table}<p>このHTMLには比較図と結果を内包しています。サーバー停止後も外部接続なしで閲覧できます。</p></section>
<script id="comparison-data" type="application/json">{encoded}</script></main></body></html>'''
