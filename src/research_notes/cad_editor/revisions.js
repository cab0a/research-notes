'use strict';
const el = id => document.getElementById(id);
const token = document.querySelector('meta[name="cad-token"]').content;
const sides = ['old', 'new'];
let state = null, busy = false, yaw = .65, pitch = -.55, drag = null, frame = null;
let bounds = null;
function message(text, tone='') {el('message').textContent=text;el('message').className=tone;}
function buttons() {
  el('demo').disabled=el('refresh').disabled=busy || !state;
  el('swap').disabled=el('report').disabled=busy || !state?.old || !state?.new;
  el('demo-case').disabled=busy;
  sides.forEach(side=>{
    el('file-'+side).disabled=busy || !state;
    el('upload-'+side).disabled=busy || !state || !el('file-'+side).files.length;
    el('clear-'+side).disabled=busy || !state?.[side];
  });
  document.body.classList.toggle('busy',busy);
}
async function run(task) {
  if(busy)return;
  busy=true;buttons();message('読み込んでいます…');
  try {await task();} catch(error) {message(error.message || '接続を確認してください。','error');}
  finally {busy=false;buttons();}
}
async function request(operation, payload={}, file=null) {
  const headers={'X-CAD-Token':token};
  if(file){headers['X-CAD-Revision']=state.revision_token;headers['X-File-Name']=encodeURIComponent(file.name);}
  else headers['Content-Type']='application/json';
  const response=await fetch('/api/revisions/'+operation,{method:'POST',headers,
    body:file || JSON.stringify({...payload,revision_token:state.revision_token})});
  if(operation==='report' && response.ok)return response.blob();
  const result=await response.json();
  if(result.state)applyState(result.state);
  if(!response.ok)throw new Error(result.error?.detail || '読込に失敗しました。');
}
async function refresh() {
  const response=await fetch('/api/revisions/state',{headers:{'X-CAD-Token':token}});
  if(!response.ok)throw new Error('接続できません。サーバーを再起動した場合は画面を再読込してください。');
  applyState(await response.json());message('最新の比較データを読み込みました。');
}
function applyState(next) {
  state=next;
  const lo=[Infinity,Infinity,Infinity],hi=[-Infinity,-Infinity,-Infinity];
  sides.forEach(side=>{
    const data=state[side];
    el('name-'+side).textContent=data?.file_name || '未読込';
    el('info-'+side).textContent=data?`単位 ${data.length_unit} · ${data.metrics.face_count} 面 / ${data.metrics.edge_count} 辺 · ${(data.source_bytes/1000).toFixed(1)} kB`:'2 MB以下・mm単位・単体ソリッド（最大24面）';
    el('hash-'+side).textContent=data?'SHA-256: '+data.source_sha256:'未読込';
    el('empty-'+side).hidden=Boolean(data);
    (data?.polygons || []).forEach(polygon=>polygon.forEach(p=>p.forEach((v,i)=>{lo[i]=Math.min(lo[i],v);hi[i]=Math.max(hi[i],v);})));
  });
  bounds=Number.isFinite(lo[0])?{center:lo.map((v,i)=>(v+hi[i])/2),span:Math.max(...hi.map((v,i)=>v-lo[i]),1e-9)}:null;
  el('pair-status').textContent=state.old&&state.new?'2ファイルを表示中':state.old||state.new?'片方を読込済み':'未読込';
  renderAnalysis();renderMetrics();draw();buttons();
}
function cells(target, values) {
  const row=document.createElement('tr');
  values.forEach(value=>{const cell=document.createElement('td');if(value instanceof Node)cell.append(value);else cell.textContent=value;row.append(cell);});
  el(target).append(row);return row;
}
function renderAnalysis() {
  const analysis=state.analysis;
  el('legend').replaceChildren();
  Object.entries(state.status_colors).forEach(([status,color])=>{const item=document.createElement('span'),swatch=document.createElement('i');swatch.style.background=color;item.append(swatch,document.createTextNode(state.status_labels[status]));el('legend').append(item);});
  const previous=el('region').value;
  el('region').replaceChildren(new Option('全体','all'));
  el('regions').replaceChildren();
  analysis.regions.forEach(region=>{
    el('region').append(new Option(region.label+' · '+state.status_labels[region.status],region.id));
    const choose=document.createElement('button');choose.className='quiet';choose.textContent=region.label;
    choose.onclick=()=>{el('region').value=region.id;renderDimensions();draw();};
    const badge=document.createElement('span');badge.className='status-chip';badge.style.borderColor=state.status_colors[region.status];badge.textContent=state.status_labels[region.status];
    cells('regions',[choose,badge,(region.old_faces.join(', ')||'—')+' → '+(region.new_faces.join(', ')||'—'),region.reason]);
  });
  if([...el('region').options].some(o=>o.value===previous))el('region').value=previous;
  el('analysis-status').textContent=({waiting:'旧版と新版の両方を開いてください。',compared:'対象範囲内で比較しました。変更候補と寸法差を確認してください。',partial:'一部の穴の対応は判定保留です。確定できた対応だけ寸法差を表示します。',unresolved:'形状または座標条件が判定範囲外です。保留理由を確認してください。'})[analysis.status];
  el('unresolved').hidden=!analysis.unresolved.length;el('unresolved').replaceChildren();
  analysis.unresolved.forEach(reason=>{const p=document.createElement('p');p.textContent=reason;el('unresolved').append(p);});
  const c=analysis.conditions;
  el('conditions').textContent=`長さの比較許容差 ${c.length_tolerance_mm} mm。穴の対応検索距離 ${c.hole_search_distance_mm??'対象外'} mm。${c.position_reference} ${c.matching_policy}`;
  renderDimensions();
}
function renderDimensions() {
  el('dimensions').replaceChildren();
  const region=state.analysis.regions.find(r=>r.id===el('region').value);
  el('region-reason').textContent=region?.reason||'';
  const available=state.analysis.dimensions.filter(d=>!region || d.region_id===region.id);
  const rows=available.filter(d=>el('show-unchanged').checked || d.status==='changed');
  rows.forEach(d=>{const delta=Number(d.delta.toFixed(6));cells('dimensions',[d.label+' / '+d.name,d.old.toFixed(6),d.new.toFixed(6),(delta>0?'+':'')+delta.toFixed(6)]);});
  if(!rows.length){const row=document.createElement('tr'),cell=document.createElement('td');cell.colSpan=4;cell.textContent=available.length?'表示対象の寸法差はありません。「許容差内の寸法も表示」で確認できます。':'この箇所は対応が確認できた新旧の寸法がありません。判定と根拠を確認してください。';row.append(cell);el('dimensions').append(row);}
}
function renderMetrics() {
  const rows=[['単位',d=>d.length_unit,null],['体積 mm³',d=>d.metrics.absolute_volume,'absolute_volume'],
    ['面積 mm²',d=>d.metrics.surface_area,'surface_area'],['面数',d=>d.metrics.face_count,'face_count'],
    ['辺数',d=>d.metrics.edge_count,'edge_count'],['頂点数',d=>d.metrics.vertex_count,'vertex_count']];
  el('metrics').replaceChildren();
  rows.forEach(([label,value,key])=>{
    const digits=key?.endsWith('count')?0:6;
    const format=v=>typeof v==='number'?v.toFixed(digits):v;
    const delta=state.metrics_delta?.[key];
    const rounded=delta===undefined?null:Number(delta.toFixed(digits));
    const cells=[label,...sides.map(side=>state[side]?format(value(state[side])):'—'),
      rounded===null?'—':(rounded>0?'+':'')+rounded.toFixed(digits)];
    const row=document.createElement('tr');
    cells.forEach(text=>{const cell=document.createElement('td');cell.textContent=text;row.append(cell);});
    el('metrics').append(row);
  });
}
function draw() {
  if(frame!==null){cancelAnimationFrame(frame);frame=null;}
  const zoom=Number(el('zoom').value),edges=el('display').value==='edges';
  const scale=bounds?285*zoom/bounds.span:1;
  function project(p) {
    const [x,y,z]=p.map((v,i)=>v-bounds.center[i]);
    const a=x*Math.cos(yaw)-y*Math.sin(yaw),b=x*Math.sin(yaw)+y*Math.cos(yaw);
    return [380+a*scale,220-(b*Math.cos(pitch)-z*Math.sin(pitch))*scale,(b*Math.sin(pitch)+z*Math.cos(pitch))*scale];
  }
  sides.forEach(side=>{
    const svg=el('view-'+side),data=state?.[side];svg.replaceChildren();
    if(!data || !bounds)return;
    const selectedRegion=state.analysis.regions.find(r=>r.id===el('region').value);
    data.polygons.map((p,i)=>({points:p.map(project),face:data.polygon_face_ids[i]})).sort((a,b)=>a.points.reduce((s,p)=>s+p[2],0)-b.points.reduce((s,p)=>s+p[2],0)).forEach(({points,face})=>{
      const a=points[1].map((v,i)=>v-points[0][i]),b=points[2].map((v,i)=>v-points[0][i]);
      const n=[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
      const light=.7+.3*Math.abs(n[2])/(Math.hypot(...n)||1);
      const status=state.analysis.face_status[side][String(face)]||'unresolved';
      const color=state.status_colors[status],rgb=[1,3,5].map(i=>Math.round(parseInt(color.slice(i,i+2),16)*light));
      const polygon=document.createElementNS('http://www.w3.org/2000/svg','polygon');
      polygon.setAttribute('points',points.map(p=>p.slice(0,2).join(',')).join(' '));
      polygon.setAttribute('fill',`rgb(${rgb.join(',')})`);polygon.dataset.face=face;polygon.dataset.status=status;
      if(selectedRegion && !selectedRegion[side+'_faces'].includes(face))polygon.setAttribute('opacity','.28');
      svg.append(polygon);
    });
    if(edges)data.edges.forEach(edge=>{
      const line=document.createElementNS('http://www.w3.org/2000/svg','polyline');
      line.setAttribute('points',edge.points.map(project).map(p=>p.slice(0,2).join(',')).join(' '));
      line.setAttribute('fill','none');line.setAttribute('stroke','#315965');line.setAttribute('stroke-width','1.5');svg.append(line);
    });
    state.analysis.markers[side].forEach(marker=>{
      if(selectedRegion && selectedRegion.id!==marker.region_id)return;
      const [x,y]=project(marker.position),ns='http://www.w3.org/2000/svg';
      const line=document.createElementNS(ns,'line');line.setAttribute('x1',x);line.setAttribute('y1',y);line.setAttribute('x2',x+16);line.setAttribute('y2',y-16);line.setAttribute('stroke','#243b47');
      const circle=document.createElementNS(ns,'circle');circle.setAttribute('cx',x+16);circle.setAttribute('cy',y-16);circle.setAttribute('r','13');circle.setAttribute('fill','white');circle.setAttribute('stroke',state.status_colors[marker.status]);circle.setAttribute('stroke-width','3');
      const label=document.createElementNS(ns,'text');label.setAttribute('x',x+16);label.setAttribute('y',y-12);label.setAttribute('text-anchor','middle');label.setAttribute('font-size','11');label.setAttribute('fill','#243b47');label.textContent=marker.label;
      svg.append(line,circle,label);
    });
  });
}
function move(e) {
  if(!drag || e.pointerId!==drag.id)return;
  if(!drag.moved && Math.hypot(e.clientX-drag.startX,e.clientY-drag.startY)<3)return;
  drag.moved=true;drag.svg.classList.add('dragging');
  yaw+=(e.clientX-drag.x)*.008;pitch+=(e.clientY-drag.y)*.008;drag.x=e.clientX;drag.y=e.clientY;
  if(frame===null)frame=requestAnimationFrame(draw);
}
function endDrag() {
  if(!drag)return;
  const active=drag;drag=null;active.svg.classList.remove('dragging');
  if(active.svg.hasPointerCapture(active.id))active.svg.releasePointerCapture(active.id);
}
sides.forEach(side=>{
  const svg=el('view-'+side);
  svg.onpointerdown=e=>{
    if(drag || !e.isPrimary || e.button!==0 || !bounds)return;
    drag={svg,id:e.pointerId,x:e.clientX,y:e.clientY,startX:e.clientX,startY:e.clientY,moved:false};
    svg.setPointerCapture(e.pointerId);
  };
  svg.onpointermove=e=>{if(drag?.id===e.pointerId){if(!(e.buttons&1)){endDrag();return;}move(e);}};
  svg.onpointerup=e=>{if(drag?.id===e.pointerId){move(e);endDrag();}};
  svg.onpointercancel=e=>{if(drag?.id===e.pointerId)endDrag();};
  svg.onlostpointercapture=e=>{if(e.target===svg && drag?.id===e.pointerId)endDrag();};
  el('file-'+side).onchange=buttons;
  el('upload-'+side).onclick=()=>{
    const file=el('file-'+side).files[0];if(!file)return;
    if(!file.size || file.size>2000000){message('空でない2 MB以下のSTEPを選択してください。','error');return;}
    run(async()=>{await request('open/'+side,{},file);el('file-'+side).value='';message((side==='old'?'旧版':'新版')+'を読み込みました。');});
  };
  el('clear-'+side).onclick=()=>run(async()=>{await request('clear',{side});message((side==='old'?'旧版':'新版')+'を閉じました。');});
});
window.addEventListener('blur',endDrag);
el('display').onchange=draw;el('zoom').onchange=draw;
el('reset').onclick=()=>{endDrag();yaw=.65;pitch=-.55;el('zoom').value='1';draw();};
el('demo').onclick=()=>run(async()=>{const label=el('demo-case').selectedOptions[0].text;await request('demo',{case:el('demo-case').value});message('「'+label+'」のサンプルを別々のSTEPとして読み込み、形状から比較しました。');});
el('region').onchange=()=>{renderDimensions();draw();};el('show-unchanged').onchange=renderDimensions;
el('report').onclick=()=>run(async()=>{
  const blob=await request('report',{camera:{yaw,pitch,zoom:Number(el('zoom').value),edges:el('display').value==='edges'}});
  const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='step-comparison.html';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);
  message('比較図・寸法差・判定保留を含むHTMLレポートを保存しました。');
});
el('swap').onclick=()=>run(async()=>{await request('swap');message('旧版と新版を入れ替えました。差の符号も更新しています。');});
el('refresh').onclick=()=>run(refresh);
run(refresh);
