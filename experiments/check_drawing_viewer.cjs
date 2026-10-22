// Execute the actual saved viewer event body and projection function, without a browser mock renderer.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..'),source=fs.readFileSync(path.join(root,'src/research_notes/drawing_dimension_report.py'),'utf8');
const move='(()=>{'+source.match(/canvas\.addEventListener\("pointermove",e=>\{(.*)\}\);/)[1]+'})()';
const key='(()=>{'+source.match(/canvas\.addEventListener\("keydown",e=>\{(.*)\}\);/)[1]+'})()';
const projectBody=source.match(/function project\(v\)\{(.*)\}/)[1];
const ctx={state:{yaw:0,pitch:.75},drag:[0,0],article:{},render:()=>{},e:{clientX:0,clientY:0},width:600,height:420,scale:1};
ctx.state.center=[0,0,0];vm.createContext(ctx);
vm.runInContext('function project(v){'+projectBody+'}',ctx);
const before=vm.runInContext('project([0,10,0])',ctx);
ctx.e={clientX:60,clientY:0};vm.runInContext(move,ctx);
const right=vm.runInContext('project([0,10,0])',ctx);
assert(right[0]>before[0],'The camera-facing +Y point must move right for rightward drag.');
const yaw=ctx.state.yaw;
ctx.drag=null;ctx.e={clientX:100,clientY:0};vm.runInContext(move,ctx);assert.equal(ctx.state.yaw,yaw,'Released pointer must not rotate.');
ctx.drag=[60,0];ctx.e={clientX:0,clientY:0};vm.runInContext(move,ctx);assert.equal(ctx.state.yaw,0,'Reverse drag returns to original orientation.');
ctx.drag=[0,0];ctx.e={clientX:0,clientY:-200};vm.runInContext(move,ctx);assert(ctx.state.pitch<0,'Underside must be reachable.');
ctx.e={key:'ArrowRight',preventDefault:()=>{}};vm.runInContext(key,ctx);assert(ctx.state.yaw<0,'Right arrow agrees with rightward drag.');
const result={runtime:process.version,assertions:5,passed:true,front_point_screen_x_before:before[0],front_point_screen_x_after_right_drag:right[0],
    source_sha256:crypto.createHash('sha256').update(source).digest('hex'),scope:'Actual event/projection functions executed in Node; real browser drag is recorded separately.'};
fs.writeFileSync(path.join(root,'results/drawing-generalization/viewer-check.json'),JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify(result));
