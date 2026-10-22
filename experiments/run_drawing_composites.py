"""Frozen compound interpreter: isolated inference, independent geometry and edit evaluation."""
import argparse,csv,datetime,hashlib,importlib.metadata,json,platform,shutil,subprocess,sys,tempfile
from pathlib import Path
from research_notes.drawing_composites import recipe
from research_notes.diagnostic_workspace import shape_snapshot
from experiments.composite_metrics import canonical,numeric,metrics,edited
from experiments.freeze_composite_engine import check
ROOT=Path(__file__).resolve().parents[1];FIX=ROOT/'fixtures/drawing-composites'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,value):p.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n',encoding='utf-8')
def execute(args,cwd):
    p=subprocess.run([sys.executable,*map(str,args)],cwd=cwd,capture_output=True,timeout=90)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace')[-2000:])
def run(output,repeats=2):
    assert repeats in (1,2,3);frozen=check();output.mkdir(parents=True,exist_ok=False);observations=[]
    for group in ('development','controls','holdout'):
        manifest=json.loads((FIX/group/'manifest.json').read_text())
        for c in manifest['cases']:
            for k in ('drawing','context'):assert sha(FIX/c[k])==c[k+'_sha256']
            folder=output/c['id'];folder.mkdir();review=c['cohort']=='review'
            inputs=[(FIX/c['drawing'],'drawing.'+c['format']),(FIX/c['context'],'context.json')]
            if review:inputs.append(((FIX/c['drawing']).with_name('review.json'),'review.json'))
            for src,name in inputs:shutil.copyfile(src,folder/('input.'+c['format'] if name.startswith('drawing.') else name))
            if c['format']=='dxf':shutil.copyfile((FIX/c['drawing']).with_suffix('.svg'),folder/'input.svg')
            if review:
                for name in ('initial-inference.json','interaction.json'):shutil.copyfile((FIX/c['drawing']).with_name(name),folder/name)
            trials=[]
            for i in range(repeats):
                check();stage='interpretation';t=dict(repeat=i,ground_truth_supplied=False,
                    worker_inputs=[name for _,name in inputs],worker_input_sha256={name:sha(src) for src,name in inputs},
                    reconstructed_correctly=False,false_confirmation=False)
                try:
                    with tempfile.TemporaryDirectory(prefix='drawing-composites-') as td:
                        td=Path(td)
                        # No authoring specs, expected values, manifest or truth files in worker inputs.
                        for src,name in inputs:shutil.copyfile(src,td/name)
                        out=td/'out';args=['-m','research_notes.drawing_composites',td/('drawing.'+c['format']),td/'context.json','--output-dir',out]
                        if review:args+=['--review',td/'review.json']
                        execute(args,td);inf=json.loads((out/'inference.json').read_text())
                        if i==0:save(folder/'inference.json',inf)
                        t.update(status=inf['status'],reason=inf.get('reason_code'),detail=inf.get('detail'),failure_stage=inf.get('failure_stage'))
                        if inf.get('reason_code') in ('processing_failure','kernel_failure'):
                            t['status']='failed'
                        if inf['status']=='candidate':
                            stage='cad_generation';execute([out/'candidate.py',out/'candidate.step'],td)
                            stage='evaluation'
                            if 'truth' not in c:
                                t.update(false_confirmation=True,detail='Candidate produced for negative control without an admissible truth solid.')
                            else:
                                truthdir=FIX/c['truth'];truth=json.loads((truthdir/'truth.json').read_text())
                                for name,digest in truth['hashes'].items():assert sha(truthdir/name)==digest
                                original,m=metrics(out/'candidate.step',truthdir/'truth.step',truth['parameters'])
                                a,b=numeric(inf['parameters']),numeric(truth['parameters']);pe=max((abs(x-y) for x,y in zip(a,b)),default=0.)
                                kinds=lambda p:[(f['kind'],f.get('opening')) for f in canonical(p)['features']]
                                structure=kinds(inf['parameters'])==kinds(truth['parameters'])
                                changed=edited(inf['parameters'],c.get('edit_policy'))
                                (out/'edited.py').write_text(recipe(changed,inf['source_sha256']))
                                stage='edit_generation';execute([out/'edited.py',out/'edited.step'],td)
                                stage='evaluation';changed_shape,em=metrics(out/'edited.step',truthdir/'edited-truth.step',truth['edited_parameters'])
                                projection_ok=all(v['sampled_symmetric_max_mm']<=.02 for v in inf['projection_metrics'].values())
                                correct=m['passed'] and em['passed'] and len(a)==len(b) and pe<=1e-6 and structure and projection_ok
                                t.update(reconstructed_correctly=correct,metrics=m,edit_metrics=em,parameter_error_mm=pe,
                                    feature_types_and_openings_correct=structure,projection_metrics=inf['projection_metrics'],
                                    visibility_residual_mm=inf['visibility_residual_mm'],false_confirmation=(not correct or c['expected']=='withheld'))
                                if i==0:
                                    for name in ('candidate.py','candidate.step','edited.py','edited.step','model.json'):shutil.copyfile(out/name,folder/name)
                                    save(folder/'comparison.json',dict(parameters=inf['parameters'],truth_parameters=truth['parameters'],
                                        edited_parameters=changed,truth_edited_parameters=truth['edited_parameters'],metrics=m,edit_metrics=em))
                                    save(folder/'preview.json',dict(original=shape_snapshot(original.shape),edited=shape_snapshot(changed_shape.shape)))
                        t['protocol_satisfied']=t['reconstructed_correctly'] if c['expected']!='withheld' else t['status']=='withheld'
                except Exception as e:t.update(status='failed',failure_stage=stage,detail=type(e).__name__+': '+str(e),protocol_satisfied=False)
                trials.append(t)
            o={**c,'trials':trials,'stable':len({json.dumps({k:v for k,v in t.items() if k!='repeat'},sort_keys=True) for t in trials})==1}
            if review:o['interaction']=json.loads((folder/'interaction.json').read_text())
            observations.append(o)
            print(json.dumps(dict(id=c['id'],status=trials[0]['status'],reason=trials[0].get('reason'),correct=trials[0]['reconstructed_correctly'],detail=trials[0].get('detail'))),flush=True)
    summary={}
    for cohort in ('development','review','negative','holdout'):
        rows=[o for o in observations if o['cohort']==cohort];ts=[o['trials'][0] for o in rows]
        summary[cohort]=dict(inputs=len(rows),parts=len({o['part'] for o in rows}),candidates=sum(t['status']=='candidate' for t in ts),
            correct=sum(t['reconstructed_correctly'] for t in ts),withheld=sum(t['status']=='withheld' for t in ts),
            failures=sum(t['status']=='failed' for t in ts),false_confirmations=sum(t['false_confirmation'] for t in ts),
            eligible_inputs=sum(o['expected']!='withheld' for o in rows),
            positive_withheld=sum(o['expected']!='withheld' and o['trials'][0]['status']=='withheld' for o in rows))
    report=dict(date='2026-10-22',completed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),observations=observations,summary=summary,
        repeats=repeats,freeze=frozen,complete=all(t['status']!='failed' for o in observations for t in o['trials']),
        repeat_stable=all(o['stable'] for o in observations),runtime=dict(python=platform.python_version(),platform=platform.platform(),
        ocp=importlib.metadata.version('cadquery-ocp'),ezdxf=importlib.metadata.version('ezdxf')),
        source_hashes={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),ROOT/'experiments/composite_metrics.py',*FIX.glob('*/manifest.json')]},
        scope='Separated Z-axis cuts; known FreeCAD family/authoring route, parameter holdout only. Review cases are promoted development data. Agent interaction times are not human ROI evidence.')
    check();save(output/'results.json',report)
    with (output/'summary.csv').open('w',newline='') as stream:
        w=csv.writer(stream);w.writerow(('id','cohort','format','expected','status','reason','correct','false_confirmation','stable'))
        for o in observations:
            t=o['trials'][0];w.writerow((o['id'],o['cohort'],o['format'],o['expected'],t['status'],t.get('reason'),t['reconstructed_correctly'],t['false_confirmation'],o['stable']))
    print(json.dumps(summary,indent=2));return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--repeats',type=int,default=2)
    a=p.parse_args();raise SystemExit(0 if run(a.output_dir,a.repeats)['complete'] else 1)
