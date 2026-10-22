"""One-pass research demonstrations. No pytest, regression suite or test creation."""
import argparse,copy,csv,datetime,hashlib,importlib.metadata,json,math,platform,shutil,subprocess,sys,tempfile
from pathlib import Path
from research_notes import drawing_machining as dm
from research_notes.step_reconstruction import read_step_input
from research_notes.parametric_features import shape_difference_volume
from research_notes.diagnostic_workspace import shape_snapshot
ROOT=Path(__file__).resolve().parents[1];FIX=ROOT/'fixtures/drawing-machining'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n',encoding='utf-8')
def canonical(p):
    p=copy.deepcopy(p);p['features'].sort(key=lambda f:(f['kind']!='pocket',f.get('axis',''),f.get('u',f.get('x')),f.get('v',f.get('y'))));return p
def analytic(p):
    w,l,t=(p[k] for k in ('width','length','thickness'));v=w*l*t;a=2*(w*l+w*t+l*t)
    pockets=[f for f in p['features'] if f['kind']=='pocket']
    for f in p['features']:
        if f['kind']=='pocket':v-=f['width']*f['length']*f['depth'];a+=2*(f['width']+f['length'])*f['depth'];continue
        r=f['diameter']/2;span=p[dm.SPAN[f['axis']]]
        if f['kind']=='counterbore':
            R=f['counter_diameter']/2;d=f['counter_depth'];v-=math.pi*(r*r*span+(R*R-r*r)*d);a+=2*math.pi*(r*(span-d)+R*d-r*r)
        elif f['extent']=='blind':v-=math.pi*r*r*f['depth'];a+=2*math.pi*r*f['depth']
        else:
            # Contained pocket overlap reduces the material length removed by the through bore.
            length=span-sum(q['depth'] for q in pockets if f['axis']=='z' and q['x']<f['u']<q['x']+q['width'] and q['y']<f['v']<q['y']+q['length'])
            v-=math.pi*r*r*length;a+=2*math.pi*r*length-2*math.pi*r*r
    return v,a
def metrics(step,truth,p):
    actual=read_step_input(step);reference=read_step_input(truth);m=actual.metrics;r=reference.metrics
    delta=shape_difference_volume(actual.shape,reference.shape);total=m.absolute_volume+r.absolute_volume;inter=(total-delta)/2;v,a=analytic(p)
    return actual,dict(valid_solid=m.analyzer_valid and m.solid_count==1,step_read_success=True,
        bounds_error_mm=max(abs(x-y) for x,y in zip((*m.bounds_min,*m.bounds_max),(*r.bounds_min,*r.bounds_max))),
        volume_mm3=m.absolute_volume,area_mm2=m.surface_area,volume_error_mm3=abs(m.absolute_volume-v),area_error_mm2=abs(m.surface_area-a),
        same_kernel_iou=inter/(total-inter),symmetric_difference_mm3=delta)
def execute(args,cwd):
    p=subprocess.run([sys.executable,*map(str,args)],cwd=cwd,capture_output=True,timeout=90)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace')[-1800:])
def run(output):
    output.mkdir(parents=True,exist_ok=False);observations=[]
    for c in json.loads((FIX/'manifest.json').read_text())['cases']:
        folder=output/c['id'];folder.mkdir();inputs=[(FIX/c['drawing'],'drawing.'+c['format']),(FIX/c['context'],'context.json')]
        for src,name in inputs:shutil.copyfile(src,folder/('input.'+c['format'] if name.startswith('drawing.') else name))
        if c['format']=='dxf':shutil.copyfile((FIX/c['drawing']).with_suffix('.svg'),folder/'input.svg')
        o={**c,'ground_truth_supplied_to_worker':False,'worker_inputs':[name for _,name in inputs]};stage='interpretation'
        try:
            with tempfile.TemporaryDirectory(prefix='drawing-machining-') as td:
                td=Path(td)
                for src,name in inputs:shutil.copyfile(src,td/name)
                out=td/'out';execute(['-m','research_notes.drawing_machining',td/('drawing.'+c['format']),td/'context.json','--output-dir',out],td)
                inf=json.loads((out/'inference.json').read_text());save(folder/'inference.json',inf)
                o.update(status=inf['status'],reason=inf.get('reason_code'),detail=inf.get('detail'),failure_stage=inf.get('failure_stage'))
                if inf['status']=='candidate':
                    stage='cad_generation';execute([out/'candidate.py',out/'candidate.step'],td)
                    stage='evaluation';truthdir=FIX/c['truth'];truth=json.loads((truthdir/'truth.json').read_text())
                    original,m=metrics(out/'candidate.step',truthdir/'truth.step',truth['parameters'])
                    changed=dm.edit(inf['parameters']);(out/'edited.py').write_text(dm.recipe(changed,inf['source_sha256']))
                    stage='edit_generation';execute([out/'edited.py',out/'edited.step'],td)
                    stage='evaluation';edited,em=metrics(out/'edited.step',truthdir/'edited-truth.step',truth['edited_parameters'])
                    same=canonical(inf['parameters'])==canonical(truth['parameters'])
                    agreement=same and all(mm['valid_solid'] and mm['same_kernel_iou']>=1-1e-8 and mm['bounds_error_mm']<=1e-6 and mm['volume_error_mm3']<=1e-5 and mm['area_error_mm2']<=1e-5 for mm in (m,em))
                    o.update(parameters_match=same,observed_agreement=agreement,metrics=m,edit_metrics=em,projection_metrics=inf['projection_metrics'])
                    for name in ('candidate.py','candidate.step','edited.py','edited.step','model.json'):shutil.copyfile(out/name,folder/name)
                    save(folder/'comparison.json',dict(parameters=inf['parameters'],truth_parameters=truth['parameters'],edited_parameters=changed,metrics=m,edit_metrics=em))
                    save(folder/'preview.json',dict(original=shape_snapshot(original.shape),edited=shape_snapshot(edited.shape)))
        except Exception as e:o.update(status='failed',failure_stage=stage,detail=type(e).__name__+': '+str(e))
        observations.append(o);print(json.dumps({k:o.get(k) for k in ('id','status','reason','observed_agreement','detail')}),flush=True)
    report=dict(date='2026-10-22',completed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),observations=observations,
        tests=dict(added=False,executed=False,reason='user requested no tests'),repeats=1,stage='development demonstration, not held-out evaluation or regression testing',
        runtime=dict(python=platform.python_version(),platform=platform.platform(),ocp=importlib.metadata.version('cadquery-ocp'),ezdxf=importlib.metadata.version('ezdxf')),
        summary=dict(inputs=len(observations),candidates=sum(o['status']=='candidate' for o in observations),withheld=sum(o['status']=='withheld' for o in observations),
            agreement=sum(o.get('observed_agreement',False) for o in observations),failed=sum(o['status']=='failed' for o in observations)),
        source_sha256={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),ROOT/'src/research_notes/drawing_machining.py',ROOT/'src/research_notes/drawing_machining_evidence.py',ROOT/'src/research_notes/drawing_machining_annotations.py']})
    save(output/'results.json',report)
    with (output/'summary.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(('id','status','reason','observed_agreement'))
        for o in observations:w.writerow((o['id'],o['status'],o.get('reason'),o.get('observed_agreement')))
    print(json.dumps(report['summary']));return report
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output-dir',type=Path,required=True);run(ap.parse_args().output_dir)
