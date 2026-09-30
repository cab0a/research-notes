'use strict';
const el=id=>document.getElementById(id),token=document.querySelector('meta[name="cad-token"]').content;
let state=null,busy=false,yaw=.65,pitch=-.55,drag=null,frame=null,displayedSource=null;
const types={through:'丸穴・貫通',blind:'丸穴・平底止まり',straight_through_slot:'長孔・貫通'};
const statuses={complete:'対応範囲内で一覧取得',partial:'穴を部分確認・全体は保留',unresolved:'形状の判定保留',rejected:'読込条件で拒否'};
const number=value=>Number.isFinite(value)?Number(value.toFixed(6)).toString():'—';
const direction=value=>Array.isArray(value)?value.map(v=>Number(v.toFixed(6))).join(', '):'—';
const featureColor=h=>h.feature_type==='straight_slot'?'#169b9c':'#e4a13b';
function message(text,error=false){el('message').textContent=text;el('message').className=error?'error':'';}
function buttons(){['demo','refresh','file'].forEach(id=>el(id).disabled=busy||!state);el('upload').disabled=busy||!state||!el('file').files.length;el('csv').disabled=busy||!state?.result;}
async function request(operation,payload={},file=null){
  const response=await fetch('/api/holes/'+operation,{method:'POST',headers:{'X-CAD-Token':token,'Content-Type':file?'application/step':'application/json',...(file?{'X-File-Name':encodeURIComponent(file.name),'X-CAD-Revision':state.revision_token}:{})},body:file||JSON.stringify({...payload,revision_token:state.revision_token})});
  if(response.ok&&operation==='csv')return response.blob();
  const data=await response.json();if(data.state){state=data.state;render();}if(!response.ok)throw new Error(data.error?.detail||'処理に失敗しました。');return data;
}
async function run(action){busy=true;buttons();try{await action();}catch(error){message(error.message,true);}finally{busy=false;buttons();}}
async function refresh(){const response=await fetch('/api/holes/state',{headers:{'X-CAD-Token':token}});if(!response.ok)throw new Error('ローカルサーバーに接続できません。');state=await response.json();render();message(state.result?'最新の穴一覧を読み込みました。':'STEPを開くと穴の一覧を表示します。');}
function render(){
  const r=state.result,previous=r?.source_sha256===displayedSource?el('hole').value:'all';displayedSource=r?.source_sha256||null;el('hole').replaceChildren(new Option('全体','all'));
  el('name').textContent=r?.file_name||'未読込';el('status').textContent=r?statuses[r.status]:'未読込';
  el('summary').textContent=!r?'STEPを開いてください。':r.hole_count===null?`確認できた穴 ${r.recognized_hole_count} か所（丸穴 ${r.recognized_circular_hole_count}・長孔 ${r.recognized_slot_count}）。全体の穴数は不明です。`:`穴 ${r.hole_count} か所（丸穴・貫通 ${r.holes.filter(h=>h.kind==='through').length}、丸穴・平底止まり ${r.holes.filter(h=>h.kind==='blind').length}）`;
  el('reason').textContent=r?.reason||'';el('preview-reason').textContent=r?.preview_reason||'';el('rows').replaceChildren();
  (r?.holes||[]).forEach(h=>{
    el('hole').add(new Option(h.id+' · '+types[h.kind],h.id));const tr=document.createElement('tr');tr.dataset.hole=h.id;tr.onclick=()=>chooseHole(h.id);
    const first=document.createElement('td'),button=document.createElement('button');button.textContent=h.id;button.className='quiet';first.append(button);tr.append(first);
    [h.solid_index||1,types[h.kind],...[h.diameter_mm,h.width_mm,h.length_mm,h.x_mm,h.y_mm,h.entry_z_mm,h.depth_mm].map(number),direction(h.axis),direction(h.longitudinal_direction)].forEach(text=>{const td=document.createElement('td');td.textContent=text;tr.append(td);});el('rows').append(tr);
  });
  if(!r?.holes.length){const tr=document.createElement('tr'),td=document.createElement('td');td.colSpan=12;td.textContent=!r?'STEP未読込':r.hole_count===0?'対応範囲内で穴0個を確認しました。':'穴一覧を確定できません。穴数は不明です。';tr.append(td);el('rows').append(tr);}
  if(Array.from(el('hole').options).some(o=>o.value===previous))el('hole').value=previous;
  el('conditions').replaceChildren();if(r)Object.entries(r.conditions).forEach(([,value])=>{const p=document.createElement('p');p.textContent=typeof value==='number'?`判定条件値: ${value}`:value;el('conditions').append(p);});
  el('hash').textContent=r?'入力SHA-256: '+r.source_sha256:'';select();buttons();
}
function select(){
  document.querySelectorAll('#rows tr').forEach(row=>row.classList.toggle('selected',row.dataset.hole===el('hole').value));
  const h=state?.result?.holes.find(row=>row.id===el('hole').value);
  el('selected-detail').textContent=h?`${h.id} · ${types[h.kind]} · ${h.feature_type==='straight_slot'?`幅 ${number(h.width_mm)} / 全長 ${number(h.length_mm)}`:`穴径 ${number(h.diameter_mm)}`} / 深さ・貫通長 ${number(h.depth_mm)} mm · 開口中心 (${[h.x_mm,h.y_mm,h.entry_z_mm].map(number).join(', ')}) mm${h.feature_type==='straight_slot'?` · 長手方向 (${direction(h.longitudinal_direction)})`:''} · 貫通・深さ方向 (${direction(h.axis)})`:'全体を表示しています。穴番号・対応する内壁・一覧の行から選択できます。';
  draw();
}
function chooseHole(id){if(!state?.result?.holes.some(h=>h.id===id))return;el('hole').value=id;select();}
function draw(){
  if(frame!==null){cancelAnimationFrame(frame);frame=null;}
  const svg=el('viewer'),r=state?.result,data=r?.preview;svg.replaceChildren();if(!data)return;
  const bounds=data.polygons.reduce((b,poly)=>{poly.forEach(p=>p.forEach((v,i)=>{b[0][i]=Math.min(b[0][i],v);b[1][i]=Math.max(b[1][i],v);}));return b;},[[Infinity,Infinity,Infinity],[-Infinity,-Infinity,-Infinity]]),[low,high]=bounds,center=low.map((v,i)=>(v+high[i])/2),scale=285*Number(el('zoom').value)/Math.max(...high.map((v,i)=>v-low[i]),1e-9);
  const ns='http://www.w3.org/2000/svg',create=(tag,attrs)=>{const node=document.createElementNS(ns,tag);Object.entries(attrs).forEach(([k,v])=>node.setAttribute(k,v));return node;};
  const project=p=>{const [x,y,z]=p.map((v,i)=>v-center[i]),a=x*Math.cos(yaw)-y*Math.sin(yaw),b=x*Math.sin(yaw)+y*Math.cos(yaw);return [380+a*scale,220-(b*Math.cos(pitch)-z*Math.sin(pitch))*scale,b*Math.sin(pitch)+z*Math.cos(pitch)];};
  const selected=r.holes.find(h=>h.id===el('hole').value),holeFaces=new Map(r.holes.flatMap(h=>h.faces.map(face=>[face,h])));
  data.polygons.map((p,i)=>({p:p.map(project),face:data.polygon_face_ids[i]})).sort((a,b)=>a.p.reduce((s,p)=>s+p[2],0)-b.p.reduce((s,p)=>s+p[2],0)).forEach(({p,face})=>{
    const hole=holeFaces.get(face),a=p[1].map((v,i)=>v-p[0][i]),b=p[2].map((v,i)=>v-p[0][i]),n=[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]],light=.7+.3*Math.abs(n[2])/(Math.hypot(...n)||1),color=hole?featureColor(hole):r.status==='complete'?'#99b0b8':'#9981bd',rgb=[1,3,5].map(i=>Math.round(parseInt(color.slice(i,i+2),16)*light));
    svg.append(create('polygon',{points:p.map(v=>v.slice(0,2).join(',')).join(' '),fill:`rgb(${rgb.join(',')})`,opacity:selected&&!selected.faces.includes(face)?'.22':'1','data-face':face,...(hole?{'data-hole':hole.id}:{})}));
  });
  if(el('display').value==='edges')data.edges.forEach(edge=>svg.append(create('polyline',{points:edge.points.map(project).map(p=>p.slice(0,2).join(',')).join(' '),fill:'none',stroke:'#315965','stroke-width':'1.5'})));
  r.holes.filter(h=>!selected||h.id===selected.id).forEach(h=>{const [x,y]=project([h.x_mm,h.y_mm,h.entry_z_mm]),group=create('g',{'data-hole':h.id,role:'button',tabindex:0,'aria-label':h.id+' · '+types[h.kind]}),text=create('text',{x:x+16,y:y-12,'text-anchor':'middle','font-size':'11',fill:'#243b47'});text.textContent=h.id;group.append(create('line',{x1:x,y1:y,x2:x+16,y2:y-16,stroke:'#243b47'}),create('circle',{cx:x+16,cy:y-16,r:13,fill:'white',stroke:featureColor(h),'stroke-width':3}),text);svg.append(group);});
}
function endDrag(){if(!drag)return;const active=drag;drag=null;el('viewer').classList.remove('dragging');if(el('viewer').hasPointerCapture(active.id))el('viewer').releasePointerCapture(active.id);}
el('viewer').onpointerdown=e=>{if(drag||!e.isPrimary||e.button!==0||!state?.result?.preview)return;drag={id:e.pointerId,x:e.clientX,y:e.clientY,startX:e.clientX,startY:e.clientY,moved:false,hole:e.target.closest('[data-hole]')?.dataset.hole};el('viewer').setPointerCapture(e.pointerId);el('viewer').classList.add('dragging');};
el('viewer').onpointermove=e=>{if(!drag||drag.id!==e.pointerId)return;if(!(e.buttons&1)){endDrag();return;}drag.moved||=Math.hypot(e.clientX-drag.startX,e.clientY-drag.startY)>4;if(!drag.moved)return;yaw+=(e.clientX-drag.x)*.008;pitch+=(e.clientY-drag.y)*.008;drag.x=e.clientX;drag.y=e.clientY;if(frame===null)frame=requestAnimationFrame(draw);};
el('viewer').onpointerup=e=>{if(!drag||drag.id!==e.pointerId)return;const id=!drag.moved&&drag.hole;endDrag();if(id)chooseHole(id);};el('viewer').onpointercancel=endDrag;el('viewer').onlostpointercapture=endDrag;window.addEventListener('blur',endDrag);
el('viewer').onkeydown=e=>{const id=e.target.closest('[data-hole]')?.dataset.hole;if(id&&['Enter',' '].includes(e.key)){e.preventDefault();chooseHole(id);el('viewer').querySelector(`[role="button"][data-hole="${id}"]`)?.focus();}};
el('reset').onclick=()=>{endDrag();yaw=.65;pitch=-.55;el('zoom').value='1';draw();};el('display').onchange=draw;el('zoom').onchange=draw;el('hole').onchange=select;el('file').onchange=buttons;
el('demo').onclick=()=>run(async()=>{await request('demo');message('3穴のサンプルを読み込みました。');});
el('upload').onclick=()=>run(async()=>{const file=el('file').files[0];if(!file)return;if(!file.size||file.size>2000000)throw new Error('空でない2 MB以下のSTEPを選択してください。');await request('open',{},file);el('file').value='';message(state.result.status==='complete'?'穴一覧を取得しました。':state.result.status==='partial'?'穴を部分確認しました。丸穴・長孔の内訳と全体数不明を確認してください。':'一覧を確定できません。判定理由を確認してください。',state.result.status==='rejected');});
el('csv').onclick=()=>run(async()=>{const blob=await request('csv'),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='hole-inventory.csv';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),30000);message('判定状態と穴一覧のCSVダウンロードを開始しました。');});
el('refresh').onclick=()=>run(refresh);run(refresh);
