'use strict';
const el = id => document.getElementById(id);
const token = document.querySelector('meta[name="cad-token"]').content;
const sides = ['old', 'new'];
let state = null, busy = false, yaw = .65, pitch = -.55, drag = null, frame = null;
let bounds = null;
function message(text, tone='') {el('message').textContent=text;el('message').className=tone;}
function buttons() {
  el('demo').disabled=el('refresh').disabled=busy || !state;
  el('swap').disabled=busy || !state?.old || !state?.new;
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
  renderMetrics();draw();buttons();
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
    // Neutral shading shows the source surfaces; it is not a change heatmap.
    data.polygons.map(p=>p.map(project)).sort((a,b)=>a.reduce((s,p)=>s+p[2],0)-b.reduce((s,p)=>s+p[2],0)).forEach(points=>{
      const a=points[1].map((v,i)=>v-points[0][i]),b=points[2].map((v,i)=>v-points[0][i]);
      const n=[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
      const shade=43+30*Math.abs(n[2])/(Math.hypot(...n)||1);
      const polygon=document.createElementNS('http://www.w3.org/2000/svg','polygon');
      polygon.setAttribute('points',points.map(p=>p.slice(0,2).join(',')).join(' '));
      polygon.setAttribute('fill',`hsl(191 25% ${shade}%)`);svg.append(polygon);
    });
    if(edges)data.edges.forEach(edge=>{
      const line=document.createElementNS('http://www.w3.org/2000/svg','polyline');
      line.setAttribute('points',edge.points.map(project).map(p=>p.slice(0,2).join(',')).join(' '));
      line.setAttribute('fill','none');line.setAttribute('stroke','#315965');line.setAttribute('stroke-width','1.5');svg.append(line);
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
el('demo').onclick=()=>run(async()=>{await request('demo');message('サンプル2件を読み込みました。板は12 × 10 × 4 mm。旧版は穴半径1 mm、新版は1.3 mmで作成した別々のSTEPです。');});
el('swap').onclick=()=>run(async()=>{await request('swap');message('旧版と新版を入れ替えました。差の符号も更新しています。');});
el('refresh').onclick=()=>run(refresh);
run(refresh);
