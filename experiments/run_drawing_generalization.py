"""Evaluate the frozen interpreter; low coverage is an observation, not a reason to retune."""
import argparse,csv,datetime,hashlib,importlib.metadata,json,platform,shutil,subprocess,sys,tempfile
from pathlib import Path
from research_notes.drawing_to_cad import json_bytes
from research_notes.drawing_generalization import recipe,export
from research_notes.drawing_families import edit
from research_notes.diagnostic_workspace import shape_snapshot
from experiments.run_drawing_families import metrics,flatten
from experiments.freeze_drawing_engine import check
ROOT=Path(__file__).resolve().parents[1];FIX=ROOT/'fixtures/drawing-generalization'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def execute(args,cwd):
    p=subprocess.run([sys.executable,*map(str,args)],cwd=cwd,capture_output=True,timeout=90)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace')[-1800:])
def run(output,repeats=2):
    assert repeats in (1,2,3)
    frozen=check();output.mkdir(parents=True,exist_ok=False);observations=[]
    for cohort in ('development','portability','holdout'):
        manifest=json.loads((FIX/cohort/'manifest.json').read_text())
        for c in manifest['cases']:
            for k in ('drawing','context','section'):
                if k in c:assert sha(FIX/c[k])==c[k+'_sha256']
            folder=output/c['id'];folder.mkdir()
            for k,name in (('drawing','input.'+c['format']),('context','context.json'),('section','section.svg')):
                if k in c:shutil.copyfile(FIX/c[k],folder/name)
            if c['format']=='dxf':shutil.copyfile((FIX/c['drawing']).with_suffix('.svg'),folder/'input.svg')
            trials=[]
            for i in range(repeats):
                check();stage='interpretation';t=dict(repeat=i,ground_truth_supplied=False,
                    worker_inputs=[c[k] for k in ('drawing','context','section') if k in c])
                try:
                    with tempfile.TemporaryDirectory(prefix='drawing-generalization-') as td:
                        td=Path(td)
                        # No manifest, authoring parameters, family names in filenames or truth copied to worker.
                        for k,name in (('drawing','drawing.'+c['format']),('context','context.json'),('section','section.svg')):
                            if k in c:shutil.copyfile(FIX/c[k],td/name)
                        out=td/'out';args=['-m','research_notes.drawing_generalization',td/('drawing.'+c['format']),td/'context.json','--output-dir',out]
                        if 'section' in c:args+=['--section',td/'section.svg']
                        execute(args,td);inf=json.loads((out/'inference.json').read_text())
                        if i==0:shutil.copyfile(out/'inference.json',folder/'inference.json')
                        t.update(status=inf['status'],reason=inf.get('reason_code'),detail=inf.get('detail'),
                            failure_stage=inf.get('failure_stage'),reconstructed_correctly=False,false_confirmation=False)
                        if inf['status']=='candidate':
                            stage='cad_generation';execute([out/'candidate.py',out/'candidate.step'],td)
                            stage='evaluation';truthdir=FIX/c['truth'];truth=json.loads((truthdir/'truth.json').read_text())
                            for name,digest in truth['hashes'].items():assert sha(truthdir/name)==digest
                            original,m=metrics(out/'candidate.step',truthdir/'truth.step',c['family'],truth['parameters'])
                            a,b=flatten(inf['parameters']),flatten(truth['parameters'])
                            pe=max((abs(x-y) for x,y in zip(a,b)),default=0.)
                            opening_ok=inf.get('opening','top')==truth.get('opening','top')
                            changed=edit(c['family'],inf['parameters']);opening=inf.get('opening','top')
                            (out/'edited.py').write_text(recipe(c['family'],changed,opening,inf['source_sha256']))
                            stage='edit_generation';execute([out/'edited.py',out/'edited.step'],td)
                            stage='evaluation';edited,em=metrics(out/'edited.step',truthdir/'edited-truth.step',c['family'],truth['edited_parameters'])
                            projection_ok=all(v['sampled_symmetric_max_mm']<=.02 for v in inf['projection_metrics'].values())
                            correct=m['passed'] and em['passed'] and len(a)==len(b) and pe<=1e-6 and opening_ok and projection_ok
                            t.update(reconstructed_correctly=correct,metrics=m,edit_metrics=em,parameter_error_mm=pe,
                                opening_correct=opening_ok,projection_metrics=inf['projection_metrics'],
                                false_confirmation=(not correct or c['expected']=='withheld'))
                            if i==0:
                                for name in ('candidate.py','candidate.step','edited.py','edited.step','model.json'):shutil.copyfile(out/name,folder/name)
                                (folder/'comparison.json').write_bytes(json_bytes(dict(parameters=inf['parameters'],truth_parameters=truth['parameters'],
                                    edited_parameters=changed,opening=opening,truth_opening=truth.get('opening','top'),metrics=m,edit_metrics=em)))
                                (folder/'preview.json').write_text(json.dumps(dict(original=shape_snapshot(original.shape),edited=shape_snapshot(edited.shape)),separators=(',',':'))+'\n')
                        t['protocol_satisfied']=t['reconstructed_correctly'] if c['expected']=='candidate' else inf['status']=='withheld'
                except Exception as e:t.update(status='failed',failure_stage=stage,detail=type(e).__name__+': '+str(e),protocol_satisfied=False)
                trials.append(t)
            o={**c,'trials':trials,'stable':len({json.dumps({k:v for k,v in t.items() if k!='repeat'},sort_keys=True) for t in trials})==1}
            # Baseline is evaluated only after reconstruction; nothing flows back into the interpreter.
            if cohort=='development' and c['baseline']['status']=='candidate':
                with tempfile.TemporaryDirectory() as td:
                    step=Path(td)/'baseline.step';export(c['family'],c['baseline']['parameters'],'top',step)
                    truthdir=FIX/c['truth'];truth=json.loads((truthdir/'truth.json').read_text())
                    _,m=metrics(step,truthdir/'truth.step',c['family'],truth['parameters']);o['baseline_geometry']=m
            observations.append(o)
            print(json.dumps(dict(id=c['id'],status=trials[0]['status'],reason=trials[0].get('reason'),correct=trials[0].get('reconstructed_correctly'),detail=trials[0].get('detail'))),flush=True)
    summary={}
    for cohort in ('development','portability','holdout'):
        rows=[o for o in observations if o['cohort']==cohort];ts=[o['trials'][0] for o in rows]
        summary[cohort]=dict(inputs=len(rows),parts=len({o['part'] for o in rows}),unique_drawings=len({o['drawing_sha256'] for o in rows}),
            candidates=sum(t['status']=='candidate' for t in ts),correct=sum(t.get('reconstructed_correctly',False) for t in ts),
            withheld=sum(t['status']=='withheld' for t in ts),failures=sum(t['status']=='failed' for t in ts),
            false_confirmations=sum(t.get('false_confirmation',False) for t in ts),
            eligible_inputs=sum(o['expected']=='candidate' for o in rows),
            eligible_reconstructed=sum(o['expected']=='candidate' and o['trials'][0].get('reconstructed_correctly',False) for o in rows),
            positive_withheld=sum(o['expected']=='candidate' and o['trials'][0]['status']=='withheld' for o in rows))
    report=dict(date='2026-10-22',completed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),observations=observations,summary=summary,
        repeats=repeats,freeze=frozen,complete=all(t['status']!='failed' for o in observations for t in o['trials']),
        repeat_stable=all(o['stable'] for o in observations),
        runtime=dict(python=platform.python_version(),platform=platform.platform(),ocp=importlib.metadata.version('cadquery-ocp'),ezdxf=importlib.metadata.version('ezdxf')),
        source_hashes={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),ROOT/'experiments/run_drawing_families.py',*(FIX.glob('*/manifest.json'))]},
        scope='Parameter holdout within four known families; same FreeCAD authoring. LibreCAD is a 2D re-export, not a native independent 3D design. No post-holdout inference adaptation.')
    check();(output/'results.json').write_bytes(json_bytes(report))
    with (output/'summary.csv').open('w',newline='') as stream:
        w=csv.writer(stream);w.writerow(('id','cohort','format','expected','status','reason','correct','false_confirmation','stable'))
        for o in observations:
            t=o['trials'][0];w.writerow((o['id'],o['cohort'],o['format'],o['expected'],t['status'],t.get('reason'),t.get('reconstructed_correctly'),t.get('false_confirmation'),o['stable']))
    print(json.dumps(summary,indent=2));return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--repeats',type=int,default=2)
    a=p.parse_args();raise SystemExit(0 if run(a.output_dir,a.repeats)['complete'] else 1)
