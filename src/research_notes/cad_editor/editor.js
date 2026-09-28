'use strict';
const el = id => document.getElementById(id);
const token = document.querySelector('meta[name="cad-token"]').content;
const labels = {plain_plate:'板',through_hole:'貫通穴（切削）',profile_hole:'貫通穴（輪郭から押出）',blind_hole:'止まり穴',boss:'円柱状の突起',pocket:'ポケット',rib:'補強リブ',plate:'板',base:'ベース',feature:'フィーチャー',width:'幅',length:'長さ',thickness:'板厚',radius:'半径',depth:'深さ',height:'高さ',x:'中心 / 位置 X',y:'中心 / 位置 Y',origin_x:'原点 X',origin_y:'原点 Y',origin_z:'原点 Z'};
let state = null, busy = false, localDirty = false;
let yaw = .65, pitch = -.55, selected = 1, kind = 'face', drag = null, drawFrame = null;
function message(text, tone='') {el('message').textContent=text; el('message').className=tone;}
function pending() {return Boolean(state?.snapshot?.transaction?.draft_pending);}
function updateButtons() {
  const model=Boolean(state?.snapshot?.transaction), candidates=state?.snapshot?.candidates || [];
  el('demo').disabled=el('file').disabled=el('refresh').disabled=busy;
  el('upload').disabled=busy || !el('file').files.length;
  el('candidate').disabled=el('confirm').disabled=busy || !candidates.length;
  el('select').disabled=busy || !candidates.length || !el('confirm').checked;
  document.querySelectorAll('#fields input').forEach(input=>input.disabled=busy);
  el('stage').disabled=busy || !model || !localDirty;
  el('recompute').disabled=busy || !model || !pending() || localDirty;
  el('rollback').disabled=busy || !model || !(pending() || localDirty);
  el('compare').disabled=el('export').disabled=busy || !model || pending() || localDirty;
  document.body.classList.toggle('busy',busy);
}
async function request(path, payload, raw=false) {
  const headers={'X-CAD-Token':token};
  if(raw) {headers['X-CAD-Revision']=state.revision_token;headers['X-File-Name']=encodeURIComponent(payload.name);}
  else headers['Content-Type']='application/json';
  const response=await fetch('/api/'+path,{method:'POST',headers,body:raw?payload:JSON.stringify({...payload,revision_token:state.revision_token})});
  if(path==='export' && response.ok) return response.blob();
  const result=await response.json();
  if(result.state) applyState(result.state);
  if(!response.ok) throw new Error(result.error?.detail || '処理に失敗しました。');
  return result;
}
async function run(task) {
  if(busy) return;
  busy=true;updateButtons();message('処理しています…');
  try {await task();} catch(error) {message(error.message || '接続を確認してください。','error');}
  finally {busy=false;updateButtons();}
}
function discardPrompt() {return !(localDirty || pending()) || window.confirm('未確定の変更があります。この操作で変更を破棄しますか？');}
async function refresh() {
  const response=await fetch('/api/state',{headers:{'X-CAD-Token':token}});
  if(!response.ok) throw new Error('状態を取得できません。サーバーを再起動した場合は画面を再読込してください。');
  applyState(await response.json());message('最新の状態を読み込みました。');
}
function applyState(next) {
  state=next;localDirty=false;
  const d=state.snapshot;
  el('source-panel').open=!d;
  el('candidate-panel').open=!d?.transaction;
  const adopted=d?.candidates.find(c=>c.selected);
  el('selected-candidate').hidden=!adopted;
  el('selected-candidate').textContent=adopted?'採用中：'+(labels[adopted.explanation] || adopted.explanation):'';
  el('file-name').textContent=state.file_name || 'ファイル未読込';
  el('empty').hidden=Boolean(d);
  el('geometry-state').textContent=!d?'未読込':pending()?'未確定の変更あり':d.transaction?'確定済み':'読込時の形状';
  el('geometry-state').className='badge'+(pending()?' pending':'');
  el('candidate').replaceChildren();
  (d?.candidates || []).forEach(c=>{const option=document.createElement('option');option.value=c.candidate_id;option.textContent=(labels[c.explanation] || c.explanation)+(c.selected?' · 採用中':'');el('candidate').append(option);if(c.selected) el('candidate').value=c.candidate_id;});
  if(!d?.candidates.length) {const option=document.createElement('option');option.textContent=d?'対応する編集候補がありません':'STEPを開いてください';el('candidate').append(option);}
  el('confirm').checked=false;candidateDetail();
  el('fields').replaceChildren();
  if(!d?.transaction) {const p=document.createElement('p');p.className='hint';p.textContent='候補を採用すると寸法を入力できます。';el('fields').append(p);}
  (d?.nodes || []).filter(n=>n.parameters.length).sort((a,b)=>(a.node_id==='base')-(b.node_id==='base')).forEach(n=>{
    const title=document.createElement('p');title.className='node-title';title.textContent=(labels[n.node_id] || n.node_id)+' · '+(labels[n.operation] || n.operation);el('fields').append(title);
    const advanced=document.createElement('details'),summary=document.createElement('summary');summary.textContent='原点の位置（詳細）';advanced.append(summary);
    n.parameters.forEach(([parameter,value])=>{
      const row=document.createElement('div');row.className='dimension';const label=document.createElement('label'),input=document.createElement('input');
      input.type='number';input.step='any';input.required=true;input.value=value;input.dataset.node=n.node_id;input.dataset.parameter=parameter;input.dataset.initial=String(value);input.id='dimension-'+n.node_id+'-'+parameter;
      label.htmlFor=input.id;label.textContent=labels[parameter] || parameter;
      input.oninput=()=>{localDirty=[...document.querySelectorAll('#fields input')].some(i=>i.value!==i.dataset.initial);updateButtons();message(localDirty?'入力中です。「寸法変更を準備」で反映し、再計算してください。':'寸法入力を元に戻しました。',localDirty?'pending':'');};
      row.append(label,input);(parameter.startsWith('origin_')?advanced:el('fields')).append(row);
    });
    if(advanced.children.length>1)el('fields').append(advanced);
  });
  renderMetrics();renderDiagnostics();elementOptions();draw();updateButtons();
}
function candidateDetail() {
  const c=state?.snapshot?.candidates.find(c=>c.candidate_id===el('candidate').value);
  el('candidate-detail').textContent=c?`幾何適合値 ${c.fit_score.toFixed(4)} · 体積残差 ${c.volume_residual.toExponential(2)} · 根拠の面 ${c.supporting_source_faces.join(', ')}。推定した編集モデルであり、元の設計履歴ではありません。`:'対応する候補が必要です。任意のSTEPの編集には対応していません。';
}
function renderMetrics() {
  el('metrics').replaceChildren();const c=state?.snapshot?.comparison;
  el('compare-status').textContent=!c?'STEPを開くと測定値を確認できます。':pending()?'未確定の変更は比較に含まれません。表示は最後に確定した形状です。':'読込時と最後に確定した形状を比較しています。';
  if(!c) return;
  [['体積 mm³','absolute_volume'],['面積 mm²','surface_area'],['面数','face_count'],['辺数','edge_count']].forEach(([label,key])=>{
    const before=c.before[key],after=c.after[key];if(before===undefined) return;
    const digits=key.endsWith('count')?0:6,diff=Number((after-before).toFixed(digits)),row=document.createElement('tr');
    [label,before.toFixed(digits),after.toFixed(digits),(diff>0?'+':'')+diff.toFixed(digits)].forEach(value=>{const td=document.createElement('td');td.textContent=value;row.append(td);});el('metrics').append(row);
  });
}
function renderDiagnostics() {
  const d=state?.snapshot;el('diagnostics').replaceChildren();
  (d?.nodes || []).forEach(n=>{const row=document.createElement('div');row.className='diagnostic-row';row.textContent=`${n.node_id} · ${n.operation} · ${n.attempt_status}${n.diagnostic?' — '+n.diagnostic:''}`;el('diagnostics').append(row);});
  (d?.constraints || []).forEach(c=>{const row=document.createElement('div');row.className='diagnostic-row';row.textContent=`拘束 ${c.node_id}: ${c.status} / 自由度 ${c.dof ?? '—'}${c.diagnostic?' / '+c.diagnostic:''}`;el('diagnostics').append(row);});
  el('source-hash').textContent=d?'元ファイル SHA-256: '+d.source_sha256:'';el('full-diagnostics').hidden=!d;
}
function elementOptions() {
  el('element-id').replaceChildren();const values=state?.snapshot?.[kind==='face'?'faces':'edges'] || [];
  if(!values.some(v=>v.index===selected)) selected=values[0]?.index || 1;
  values.forEach(v=>{const option=document.createElement('option');option.value=v.index;option.textContent=v.index+' · '+v.support;el('element-id').append(option);});el('element-id').value=String(selected);
}
function draw() {
  if(drawFrame!==null){cancelAnimationFrame(drawFrame);drawFrame=null;}
  const mode=el('view-mode').value;el('original-view').hidden=mode==='current';el('current-view').hidden=mode==='original';el('views').classList.toggle('both',mode==='both');
  const current=state?.snapshot, original=state?.original;
  // Both panes use the same source/current bounds and camera to preserve scale.
  const all=[...(current?.polygons || []),...(original?.polygons || [])].flat();
  if(!all.length){el('viewer').replaceChildren();el('original-viewer').replaceChildren();return;}
  const lo=[0,1,2].map(i=>all.reduce((v,p)=>Math.min(v,p[i]),Infinity)),hi=[0,1,2].map(i=>all.reduce((v,p)=>Math.max(v,p[i]),-Infinity));
  const center=lo.map((v,i)=>(v+hi[i])/2),scale=285/Math.max(...hi.map((v,i)=>v-lo[i]),1e-9);
  function project(p){const [x,y,z]=p.map((v,i)=>v-center[i]),a=x*Math.cos(yaw)-y*Math.sin(yaw),b=x*Math.sin(yaw)+y*Math.cos(yaw);return [380+a*scale,220-(b*Math.cos(pitch)-z*Math.sin(pitch))*scale,b*Math.sin(pitch)+z*Math.cos(pitch)];}
  function pane(id,data,interactive) {
    const svg=el(id);svg.replaceChildren();if(!data)return;
    data.polygons.map((p,i)=>({points:p.map(project),face:data.polygon_face_ids[i]})).sort((a,b)=>a.points.reduce((s,p)=>s+p[2],0)-b.points.reduce((s,p)=>s+p[2],0)).forEach(t=>{
      const p=document.createElementNS('http://www.w3.org/2000/svg','polygon');p.setAttribute('points',t.points.map(x=>x.slice(0,2).join(',')).join(' '));p.setAttribute('fill',interactive&&kind==='face'&&t.face===selected?'#dfa654':`hsl(${186+t.face*5%25} 27% ${53+t.face%4*7}%)`);
      if(interactive){p.dataset.kind='face';p.dataset.index=t.face;}svg.append(p);
    });
    if(kind==='edge')data.edges.forEach(e=>{const p=document.createElementNS('http://www.w3.org/2000/svg','polyline');p.setAttribute('points',e.points.map(project).map(x=>x.slice(0,2).join(',')).join(' '));p.setAttribute('fill','none');p.setAttribute('stroke',interactive&&e.index===selected?'#c64627':'#234757');p.setAttribute('stroke-width',interactive&&e.index===selected?'5':'2');if(interactive){p.dataset.kind='edge';p.dataset.index=e.index;}svg.append(p);});
  }
  pane('viewer',current,true);pane('original-viewer',original,false);
  el('selection').textContent=`${mode==='both'?'左右どちらでもドラッグで両方を回転':'ドラッグで回転'} · 確定形状の${kind==='face'?'面':'辺'} ${selected} を選択中。IDはこの状態内での番号です。`;
}
function rotateDrag(e) {
  if(!drag || e.pointerId!==drag.pointerId)return;
  const dx=e.clientX-drag.x,dy=e.clientY-drag.y;
  if(!drag.moved && Math.hypot(e.clientX-drag.startX,e.clientY-drag.startY)<3)return;
  drag.moved=true;drag.svg.classList.add('dragging');
  yaw+=dx*.008;pitch+=dy*.008;drag.x=e.clientX;drag.y=e.clientY;
  // Coalesce pointer events so both comparison panes are redrawn once per frame.
  if(drawFrame===null)drawFrame=requestAnimationFrame(draw);
}
function endDrag() {
  if(!drag)return;
  const active=drag;drag=null;active.svg.classList.remove('dragging');
  if(active.svg.hasPointerCapture(active.pointerId))active.svg.releasePointerCapture(active.pointerId);
}
['viewer','original-viewer'].forEach(id=>{
  const svg=el(id);
  svg.onpointerdown=e=>{
    if(drag || !e.isPrimary || e.button!==0)return;
    const hit=e.target.closest('[data-kind]');
    drag={svg,pointerId:e.pointerId,startX:e.clientX,startY:e.clientY,x:e.clientX,y:e.clientY,moved:false,
      hit:hit?{kind:hit.dataset.kind,index:Number(hit.dataset.index)}:null};
    // Capture on the stable SVG, not a polygon replaced by draw(). Keep tracking
    // when the pointer crosses the comparison divider or leaves either pane.
    svg.setPointerCapture(e.pointerId);
  };
  svg.onpointermove=e=>{
    if(!drag || e.pointerId!==drag.pointerId)return;
    if(!(e.buttons&1)){endDrag();return;}
    rotateDrag(e);
  };
  svg.onpointerup=e=>{
    if(!drag || e.pointerId!==drag.pointerId)return;
    rotateDrag(e);
    const hit=!drag.moved && drag.hit;endDrag();
    // Pointer capture retargets clicks to the SVG; preserve face/edge picking
    // explicitly, and never pick an element at the end of a rotation.
    if(hit){selected=hit.index;kind=hit.kind;el('kind').value=kind;elementOptions();draw();}
  };
  svg.onpointercancel=e=>{if(drag?.pointerId===e.pointerId)endDrag();};
  svg.onlostpointercapture=e=>{if(e.target===svg && drag?.pointerId===e.pointerId)endDrag();};
});
window.addEventListener('blur',endDrag);
el('kind').onchange=()=>{kind=el('kind').value;elementOptions();draw();};el('element-id').onchange=()=>{selected=Number(el('element-id').value);draw();};el('view-mode').onchange=draw;el('reset').onclick=()=>{yaw=.65;pitch=-.55;draw();};
el('file').onchange=updateButtons;el('confirm').onchange=updateButtons;
el('candidate').onchange=()=>{el('confirm').checked=false;candidateDetail();updateButtons();};
el('demo').onclick=()=>{if(discardPrompt())run(async()=>{await request('demo',{});message('穴付き板を読み込みました。編集候補を確認して採用してください。');});};
el('upload').onclick=()=>{const file=el('file').files[0];if(!file)return;if(file.size>2000000){message('2 MB以下のSTEPを選択してください。','error');return;}if(discardPrompt())run(async()=>{await request('open',file,true);message(state.snapshot.candidates.length?'STEPを読み込みました。編集候補を確認してください。':'STEPを読み込みましたが、対応する編集候補がありません。','');});};
el('select').onclick=()=>{if(discardPrompt())run(async()=>{await request('select',{candidate_id:el('candidate').value,confirm:el('confirm').checked});message('候補を採用しました。寸法を入力できます。');});};
el('dimensions').onsubmit=e=>{e.preventDefault();run(async()=>{const changes=[...document.querySelectorAll('#fields input')].filter(i=>i.value!==i.dataset.initial).map(i=>({node_id:i.dataset.node,parameter:i.dataset.parameter,value:Number(i.value)}));await request('edit',{changes});message('変更を準備しました。「再計算して確定」で形状を更新してください。','pending');});};
el('recompute').onclick=()=>run(async()=>{const response=await request('recompute',{});if(response.result.status==='aborted'){const failed=state.snapshot.nodes.find(n=>n.diagnostic);message('再計算に失敗しました。最後に確定した形状を保持しています。寸法を修正するか、変更を取り消してください。'+(failed?' '+failed.diagnostic:''),'error');}else message('再計算が完了しました。比較を確認し、STEPを保存できます。');});
el('rollback').onclick=()=>run(async()=>{await request('rollback',{});message('未確定の変更を取り消しました。');});
el('compare').onclick=()=>run(async()=>{await request('compare',{});el('view-mode').value='both';draw();message('読込時と確定形状の比較を更新しました。');});
el('export').onclick=()=>run(async()=>{const blob=await request('export',{}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=(state.file_name || 'model.step').replace(/\.(step|stp)$/i,'')+'-edited.step';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);message('確定形状のSTEPをダウンロードしました。');});
el('refresh').onclick=()=>{if(!localDirty || window.confirm('まだ送信していない寸法入力を破棄して、最新の状態を読み込みますか？'))run(refresh);};
window.addEventListener('beforeunload',e=>{if(localDirty || pending()){e.preventDefault();e.returnValue='';}});
run(refresh);
