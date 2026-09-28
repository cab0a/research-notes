"""Standalone interactive snapshot with source-bound face/edge selection."""
from __future__ import annotations

from dataclasses import asdict
import html
import json
import math
from pathlib import Path

import numpy as np

from research_notes.brep_runtime import indexed_shapes
from research_notes.modeling_common import _surface_type
from research_notes.robustness_studies import evidence_bytes


def workspace_snapshot(workspace):
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy
    from OCP.TopAbs import TopAbs_FACE, TopAbs_EDGE
    from OCP.TopoDS import TopoDS
    from research_notes.brep_preview import _mesh_polygons
    from research_notes.cad_api import CadAPIError
    from research_notes.parametric_features import rectangle_solution, circular_solution
    session, tx = workspace._session, workspace._transaction
    if session.inspection is None:
        raise CadAPIError("no_source", "open a STEP file before creating the workspace")
    source = session.inspection.imported
    shape = tx.committed.current_output().shape if tx else source.shape
    faces, edges = indexed_shapes(shape, TopAbs_FACE), indexed_shapes(shape, TopAbs_EDGE)
    if faces.Extent() > 256 or edges.Extent() > 512:
        raise CadAPIError("resource_limit", "workspace snapshot supports at most 256 faces and 512 edges")
    copied = BRepBuilderAPI_Copy(shape, True, False).Shape()
    polygons, face_ids = _mesh_polygons(copied)
    if len(polygons) > 60000:
        raise CadAPIError("resource_limit", "workspace triangle budget exceeded")
    edge_records = []
    for i in range(1, edges.Extent() + 1):
        try:
            curve = BRepAdaptor_Curve(TopoDS.Edge_s(edges.FindKey(i)))
            low, high = curve.FirstParameter(), curve.LastParameter()
            if not all(math.isfinite(v) and abs(v) < 1e20 for v in (low, high)):
                raise ValueError("unbounded edge parameter range")
            points = [curve.Value(float(t)).Coord() for t in np.linspace(low, high, 25)]
            support = str(curve.GetType()).split(".")[-1].removeprefix("GeomAbs_").lower()
            edge_records.append({"index": i, "support": support, "points": points, "status": "sampled"})
        except (ValueError, RuntimeError) as error:
            edge_records.append({"index": i, "support": "unknown", "points": [], "status": "unresolved", "reason": str(error)})
    candidate_rows = [{"candidate_id": c.candidate_id, "explanation": c.explanation,
        "fit_score": c.fit_score, "volume_residual": c.volume_residual,
        "area_residual": c.area_residual, "supporting_source_faces": c.supporting_faces,
        "selected": c.candidate_id == session.selected_candidate_id} for c in session.inspection.candidates]
    nodes, constraints = [], []
    if tx:
        attempt = {s.node_id: s for s in tx.attempt.states} if tx.attempt else {}
        for node in tx.draft.nodes:
            state = attempt.get(node.node_id)
            nodes.append({**asdict(node), "attempt_status": state.status if state else "not_attempted" if tx.dirty else "valid",
                          "diagnostic": state.error if state else ""})
            parameters = dict(node.parameters)
            try:
                if node.operation == "result":
                    continue
                solution = circular_solution(parameters["x"], parameters["y"], parameters["radius"]) if "radius" in parameters else rectangle_solution(parameters["width"], parameters["length"])
                constraints.append({"node_id": node.node_id, "status": solution.status, "dof": solution.local_degrees_of_freedom,
                    "max_residual": solution.max_residual, "satisfied": solution.satisfied,
                    "scope": "profile sketch only; feature containment and 3D validity are separate"})
            except (ValueError, RuntimeError) as error:
                constraints.append({"node_id": node.node_id, "status": "failed", "diagnostic": str(error)})
    before = asdict(source.metrics)
    after = asdict(tx.committed.current_output().metrics) if tx else before
    return {"workspace_contract": "1.0.0", "api_version": "1.0.0", "file_name": source.file_name,
        "source_sha256": source.source_sha256, "revision_token": workspace.revision_token,
        "geometry_state": "retained_committed_not_draft" if tx and tx.dirty else "committed" if tx else "imported_inspection",
        "transaction": tx.record() if tx else None, "nodes": nodes, "constraints": constraints,
        "candidates": candidate_rows, "comparison": {"before": before, "after": after,
            "volume_change_mm3": after["absolute_volume"] - before["absolute_volume"],
            "area_change_mm2": after["surface_area"] - before["surface_area"]},
        "faces": [{"index": i, "support": _surface_type(TopoDS.Face_s(faces.FindKey(i)))} for i in range(1, faces.Extent() + 1)],
        "edges": edge_records, "polygons": polygons, "polygon_face_ids": face_ids,
        "selection_scope": "analysis-local IDs bound to this source digest and revision; no inferred STEP entity or persistent identity",
        "editing_policy": "read-only snapshot; use the Python API or terminal for transactional edits"}


def write_workspace(workspace, directory: Path):
    data = workspace_snapshot(workspace)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "workspace.json").write_bytes(evidence_bytes(data))
    # JSON is data inside a non-executable script; escaping prevents source names
    # containing '</script>' from becoming executable HTML.
    encoded = evidence_bytes(data).decode().replace("<", "\\u003c").replace("&", "\\u0026")
    page = PAGE.replace("__DATA__", encoded)
    (directory / "workspace.html").write_text(page, encoding="utf-8", newline="\n")
    return {"html": str(directory / "workspace.html"), "snapshot": str(directory / "workspace.json"),
            "face_count": len(data["faces"]), "edge_count": len(data["edges"]), "geometry_state": data["geometry_state"]}


PAGE = r'''<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>3D 診断ワークスペース · v1.0</title>
<style>*{box-sizing:border-box}body{margin:0;background:#edf2f6;color:#203449;font:15px system-ui}header{background:#102b42;color:white;padding:22px 30px}h1{font-size:25px;margin:0 0 8px}main{padding:20px;display:grid;grid-template-columns:minmax(0,3fr) minmax(300px,2fr);gap:18px}.card{background:white;border:1px solid #d5e0e8;border-radius:10px;padding:18px;min-width:0}h2{font-size:18px;margin:0 0 12px}svg{width:100%;height:440px;background:#f2f7fa;touch-action:none}button,select,input{font:inherit;padding:8px;margin:3px;border:1px solid #becdd9;border-radius:5px;background:white}button{cursor:pointer}button:focus,select:focus{outline:3px solid #2397b0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;background:#f2f6f9;padding:12px;max-height:300px;overflow:auto}.warning{background:#fff2cc;color:#624700;padding:10px;border-radius:5px}.small{font-size:12px;color:#566b7d;overflow-wrap:anywhere}.scroll{overflow:auto}table{border-collapse:collapse;font-size:13px;width:100%}td,th{text-align:left;padding:8px;border-bottom:1px solid #d6e1e8}.badge{padding:3px 7px;background:#e7f0f4;border-radius:5px}.failed,.stale{color:#9e281f}.full{grid-column:1/-1}a{color:#076b81}@media(max-width:850px){main{grid-template-columns:1fr}svg{height:340px}}</style>
<header><h1>3D 診断ワークスペース</h1><div id="source"></div></header>
<main><section class="card"><h2>面・辺の選択</h2><p id="state" class="warning"></p>
<div><button id="reset">視点を戻す</button><label>表示 <select id="kind"><option value="face">面</option><option value="edge">辺</option></select></label><label>ID <select id="index"></select></label></div>
<svg id="viewer" viewBox="0 0 760 440" role="img" aria-label="回転できる3D形状。面または辺をクリックして選択"></svg>
<p class="small">ドラッグで回転。ID選択でも同じ要素を確認できます。描画は診断用の三角形と曲線サンプルです。</p><pre id="selection" aria-live="polite"></pre></section>
<section class="card"><h2>出所・変更状態</h2><pre id="provenance"></pre><h2>幾何の比較</h2><div id="comparison"></div><p class="small">比較対象は読込時と最後に確定した形状です。未確定の変更は反映しません。</p><a href="workspace.json">再現用JSON</a></section>
<section class="card"><h2>依存関係と再計算</h2><div id="dependencies"></div></section>
<section class="card"><h2>拘束の状態</h2><div id="constraints"></div><p class="small">スケッチの拘束判定です。3D形状の成立や大域的な一意性を保証しません。</p></section>
<section class="card full"><h2>再構成候補の比較</h2><div id="candidates"></div><p class="small">候補の自動採用は行いません。この画面は検査用スナップショットです。編集・再計算はPython APIまたは対話ターミナルで行います。</p></section></main>
<script id="data" type="application/json">__DATA__</script><script>
'use strict';const d=JSON.parse(document.getElementById('data').textContent),el=id=>document.getElementById(id),ns='http://www.w3.org/2000/svg';
el('source').textContent=d.file_name+' · '+d.faces.length+' faces / '+d.edges.length+' edges';
el('state').textContent=d.geometry_state==='retained_committed_not_draft'?'未確定の変更があります。表示は最後に確定した形状です。':'表示状態: '+d.geometry_state;
el('provenance').textContent=JSON.stringify({source_sha256:d.source_sha256,revision_token:d.revision_token,selection_scope:d.selection_scope,transaction:d.transaction?d.transaction.outcome:null},null,2);
function table(target,headers,rows){const box=el(target);box.className='scroll';if(!rows.length){box.textContent='対象なし / 未選択';return}const t=document.createElement('table'),head=document.createElement('tr');headers.forEach(x=>{const th=document.createElement('th');th.textContent=x;head.append(th)});t.append(head);rows.forEach(row=>{const tr=document.createElement('tr');row.forEach(x=>{const td=document.createElement('td');td.textContent=String(x);tr.append(td)});t.append(tr)});box.append(t)}
table('comparison',['項目','読込時','確定形状'],[['体積 mm³',d.comparison.before.absolute_volume.toFixed(6),d.comparison.after.absolute_volume.toFixed(6)],['面積 mm²',d.comparison.before.surface_area.toFixed(6),d.comparison.after.surface_area.toFixed(6)],['面数',d.comparison.before.face_count,d.comparison.after.face_count],['体積差 mm³','—',d.comparison.volume_change_mm3.toFixed(6)]]);
table('dependencies',['ノード','依存元','処理','仮計算状態','診断'],d.nodes.map(n=>[n.node_id,n.dependencies.join(', ')||'root',n.operation,n.attempt_status,n.diagnostic]));
table('constraints',['ノード','判定','自由度','最大残差'],d.constraints.map(c=>[c.node_id,c.status,c.dof??'—',c.max_residual??c.diagnostic]));
table('candidates',['候補','選択','幾何適合値','体積残差','根拠の面（読込時）'],d.candidates.map(c=>[c.explanation,c.selected?'選択済み':'未選択',c.fit_score,c.volume_residual,c.supporting_source_faces.join(', ')]));
let yaw=.65,pitch=-.55,chosen=1,kind='face',drag=null,moved=false;const all=d.polygons.flat(),lo=[0,1,2].map(i=>all.reduce((v,p)=>Math.min(v,p[i]),Infinity)),hi=[0,1,2].map(i=>all.reduce((v,p)=>Math.max(v,p[i]),-Infinity)),center=lo.map((v,i)=>(v+hi[i])/2),scale=290/Math.max(...hi.map((v,i)=>v-lo[i]),1e-9);
function project(p){const [x,y,z]=p.map((v,i)=>v-center[i]),a=x*Math.cos(yaw)-y*Math.sin(yaw),b=x*Math.sin(yaw)+y*Math.cos(yaw),v=b*Math.cos(pitch)-z*Math.sin(pitch),depth=b*Math.sin(pitch)+z*Math.cos(pitch);return [380+a*scale,220-v*scale,depth]}
function select(id){chosen=id;el('index').value=id;const row=(kind==='face'?d.faces:d.edges).find(x=>x.index===id);el('selection').textContent=JSON.stringify({kind,index:id,source_sha256:d.source_sha256,revision_token:d.revision_token,support:row?.support,scope:'このスナップショット内のID。STEPの永続IDではありません。'},null,2);render()}
function render(){const svg=el('viewer');svg.replaceChildren();const tris=d.polygons.map((p,i)=>({points:p.map(project),face:d.polygon_face_ids[i]})).sort((a,b)=>a.points.reduce((s,p)=>s+p[2],0)-b.points.reduce((s,p)=>s+p[2],0));tris.forEach(t=>{const p=document.createElementNS(ns,'polygon');p.setAttribute('points',t.points.map(x=>x.slice(0,2).join(',')).join(' '));p.setAttribute('fill',kind==='face'&&t.face===chosen?'#efa93e':`hsl(${190+t.face*13%70} 35% ${60+t.face%4*5}%)`);p.setAttribute('stroke','none');p.onclick=()=>{if(!moved){kind='face';el('kind').value=kind;options();select(t.face)}};svg.append(p)});if(kind==='edge')d.edges.forEach(e=>{const p=document.createElementNS(ns,'polyline');p.setAttribute('points',e.points.map(project).map(x=>x.slice(0,2).join(',')).join(' '));p.setAttribute('fill','none');p.setAttribute('stroke',e.index===chosen?'#d13e26':'#163a52');p.setAttribute('stroke-width',e.index===chosen?'5':'2');p.onclick=()=>{if(!moved)select(e.index)};svg.append(p)})}
function options(){el('index').replaceChildren();(kind==='face'?d.faces:d.edges).forEach(r=>{const o=document.createElement('option');o.value=r.index;o.textContent=r.index+' · '+r.support;el('index').append(o)})}
el('kind').onchange=()=>{kind=el('kind').value;options();select(1)};el('index').onchange=()=>select(Number(el('index').value));el('reset').onclick=()=>{yaw=.65;pitch=-.55;render()};el('viewer').onpointerdown=e=>{drag=[e.clientX,e.clientY];moved=false};el('viewer').onpointermove=e=>{if(!drag)return;const dx=e.clientX-drag[0],dy=e.clientY-drag[1];if(Math.abs(dx)+Math.abs(dy)>2)moved=true;if(!moved)return;yaw+=dx*.008;pitch+=dy*.008;drag=[e.clientX,e.clientY];render()};el('viewer').onpointerup=()=>{drag=null};el('viewer').onpointerleave=()=>{drag=null};options();select(1);
</script></html>'''
