"""Native drawing family experiments: isolated workers, independent truth, edits."""
import argparse,hashlib,json,math,platform,subprocess,sys,tempfile,csv,importlib.metadata
from pathlib import Path
from research_notes.drawing_to_cad import json_bytes
from research_notes.drawing_families import code,edit
from research_notes.diagnostic_workspace import shape_snapshot
from research_notes.step_reconstruction import read_step_input
from research_notes.parametric_features import shape_difference_volume
ROOT=Path(__file__).resolve().parents[1]
FIX=ROOT/'fixtures/drawing-families'

def analytic(f,p):
    if f=='plate':
        return (p['width']*p['length']-sum(math.pi*(h['diameter']/2)**2 for h in p['holes']))*p['thickness'], 2*(p['width']*p['length']+p['width']*p['thickness']+p['length']*p['thickness'])+sum(math.pi*h['diameter']*p['thickness']-2*math.pi*(h['diameter']/2)**2 for h in p['holes'])
    if f=='l_bracket':
        a=p['length']*p['base_thickness']+p['wall_thickness']*(p['height']-p['base_thickness'])
        return p['width']*a,2*a+2*p['width']*(p['length']+p['height'])
    if f=='stepped_shaft':
        r,s=p['diameter1']/2,p['diameter2']/2
        return math.pi*(r*r*p['length1']+s*s*p['length2']),2*math.pi*(r*p['length1']+s*p['length2']+r*r)
    w,l,t,a,b,d=(p[k] for k in ('width','length','thickness','pocket_width','pocket_length','pocket_depth'))
    return w*l*t-a*b*d,2*(w*l+w*t+l*t)+2*d*(a+b)

def metrics(path,truth_path,f,p):
    measured=read_step_input(path);truth=read_step_input(truth_path);m=measured.metrics
    delta=shape_difference_volume(measured.shape,truth.shape)
    total=m.absolute_volume+truth.metrics.absolute_volume;intersection=(total-delta)/2
    vol,area=analytic(f,p)
    result=dict(valid_solid=m.analyzer_valid and m.solid_count==1,step_read_success=True,
        bounds_error_mm=max(abs(a-b) for a,b in zip((*m.bounds_min,*m.bounds_max),(*truth.metrics.bounds_min,*truth.metrics.bounds_max))),
        volume_mm3=m.absolute_volume,area_mm2=m.surface_area,volume_error_mm3=abs(m.absolute_volume-vol),area_error_mm2=abs(m.surface_area-area),
        same_kernel_iou=intersection/(total-intersection),symmetric_difference_mm3=delta)
    result['passed']=result['valid_solid'] and result['bounds_error_mm']<=1e-6 and result['volume_error_mm3']<=1e-5 and result['area_error_mm2']<=1e-5 and result['same_kernel_iou']>=1-1e-8
    return measured,result

def flatten(p):
    values=[float(v) for k,v in sorted(p.items()) if k!='holes']
    for h in sorted(p.get('holes',[]),key=lambda h:(h['x'],h['y'])):
        values += [float(v) for _,v in sorted(h.items())]
    return values

def run(output,repeats=2):
    if repeats not in (1,2,3):raise ValueError('repeats 1..3')
    output.mkdir(parents=True,exist_ok=False)
    manifest=json.loads((FIX/'manifest.json').read_text());observations=[]
    for case in manifest['cases']:
        for key in ('drawing','context'):
            assert hashlib.sha256((FIX/case[key]).read_bytes()).hexdigest()==case[key+'_sha256']
        folder=output/case['id'];folder.mkdir()
        (folder/('input.'+case['format'])).write_bytes((FIX/case['drawing']).read_bytes())
        # Paired page is display-only on DXF cases.
        (folder/'input.svg').write_bytes((FIX/case['drawing']).read_bytes() if case['format']=='svg' else (FIX/'inputs'/case['part']/'drawing.svg').read_bytes())
        (folder/'context.json').write_bytes((FIX/case['context']).read_bytes())
        trials=[]
        for repeat in range(repeats):
            trial=dict(repeat=repeat,passed=False,worker_inputs=[case['drawing'],case['context']],ground_truth_supplied=False);stage='interpretation'
            try:
                with tempfile.TemporaryDirectory(prefix='drawing-families-') as temp:
                    temp=Path(temp)
                    worker=subprocess.run([sys.executable,'-m','research_notes.drawing_families',str(FIX/case['drawing']),str(FIX/case['context']),'--output-dir',str(temp)],cwd=temp,capture_output=True,timeout=60)
                    if worker.returncode:raise RuntimeError(worker.stderr.decode(errors='replace')[-1500:])
                    inf=json.loads((temp/'inference.json').read_text())
                    trial.update(status=inf['status'],reason=inf.get('reason_code'),detail=inf.get('detail'))
                    if repeat==0:(folder/'inference.json').write_bytes(json_bytes(inf))
                    if inf['status']=='withheld':
                        trial['passed']=case['expected']=='withheld' and inf['reason_code']==case['expected_reason']
                    else:
                        stage='cad_generation'
                        result=subprocess.run([sys.executable,str(temp/'candidate.py'),str(temp/'candidate.step')],cwd=temp,capture_output=True,timeout=60)
                        if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace')[-1500:])
                        # Only now open independent CAD authoring truth.
                        stage='evaluation'
                        truthdir=FIX/'evaluation'/case['part'];truth=json.loads((truthdir/'truth.json').read_text())
                        for file,digest in truth['hashes'].items():assert hashlib.sha256((truthdir/file).read_bytes()).hexdigest()==digest
                        original,m=metrics(temp/'candidate.step',truthdir/'truth.step',case['family'],truth['parameters'])
                        a,b=flatten(inf['parameters']),flatten(truth['parameters'])
                        param_error=max((abs(x-y) for x,y in zip(a,b)),default=0)
                        trial.update(metrics=m,parameter_error_mm=param_error,projection_metrics=inf['projection_metrics'])
                        changed=edit(case['family'],inf['parameters']);(temp/'edited.py').write_text(code(case['family'],changed,inf['source_sha256']))
                        stage='edit_generation'
                        result=subprocess.run([sys.executable,str(temp/'edited.py'),str(temp/'edited.step')],cwd=temp,capture_output=True,timeout=60)
                        if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace')[-1500:])
                        edited,em=metrics(temp/'edited.step',truthdir/'edited-truth.step',case['family'],truth['edited_parameters'])
                        trial.update(edit_metrics=em,passed=case['expected']=='candidate' and m['passed'] and em['passed'] and len(a)==len(b) and param_error<=1e-6)
                        if repeat==0:
                            for name in ('candidate.py','candidate.step','model.json','edited.py','edited.step'):(folder/name).write_bytes((temp/name).read_bytes())
                            (folder/'comparison.json').write_bytes(json_bytes(dict(truth_parameters=truth['parameters'],parameters=inf['parameters'],
                                edited_parameters=changed,edited_truth_parameters=truth['edited_parameters'],metrics=m,edit_metrics=em)))
                            (folder/'preview.json').write_text(json.dumps(dict(original=shape_snapshot(original.shape),edited=shape_snapshot(edited.shape)),separators=(',',':'))+'\n')
            except Exception as error:trial.update(status='failed',failure_stage=stage,detail=type(error).__name__+': '+str(error))
            trials.append(trial)
        observation={**case,'trials':trials,'passed':all(t['passed'] for t in trials)};observations.append(observation)
        print(json.dumps(dict(id=case['id'],passed=observation['passed'],status=trials[0].get('status'),reason=trials[0].get('reason'),detail=trials[0].get('detail'))),flush=True)
    pairs=[]
    for part in sorted({c['part'] for c in observations if c['cohort']!='derived_representation'}):
        native=[c for c in observations if c['part']==part and c['cohort']!='derived_representation']
        row=dict(part=part,passed=all(o['passed'] for o in native),formats={o['format']:o['trials'][0].get('status') for o in native})
        if all(o['trials'][0].get('status')=='candidate' and o['passed'] for o in native):
            inf=[json.loads((output/o['id']/'inference.json').read_text()) for o in native]
            row['parameters_equal']=inf[0]['parameters']==inf[1]['parameters']
            row['geometry']={}
            for name in ('candidate','edited'):
                models=[read_step_input(output/o['id']/(name+'.step')) for o in native]
                difference=shape_difference_volume(models[0].shape,models[1].shape)
                total=sum(m.metrics.absolute_volume for m in models);intersection=(total-difference)/2
                row['geometry'][name]=dict(iou=intersection/(total-intersection),difference_mm3=difference)
            row['passed'] &= row['parameters_equal'] and all(v['iou']>=1-1e-8 for v in row['geometry'].values())
        elif all(o['trials'][0].get('status')=='withheld' for o in native):
            row['reason_equal']=len({o['trials'][0].get('reason') for o in native})==1;row['passed'] &= row['reason_equal']
        pairs.append(row)
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [
        Path(__file__),ROOT/'src/research_notes/drawing_families.py',ROOT/'src/research_notes/drawing_family_evidence.py',
        ROOT/'src/research_notes/drawing_svg_extensions.py',ROOT/'src/research_notes/drawing_family_report.py',
        FIX/'manifest.json',FIX/'baseline.json']}
    report=dict(date='2026-10-22',study='Drawing families and review workflow',observations=observations,pairs=pairs,repeats=repeats,
        passed=all(o['passed'] for o in observations) and all(p['passed'] for p in pairs),code_input_hashes=hashes,
        runtime=dict(python=platform.python_version(),platform=platform.platform(),ocp=importlib.metadata.version('cadquery-ocp'),ezdxf=importlib.metadata.version('ezdxf')),
        thresholds=dict(dimension_mm=1e-6,volume_mm3=1e-5,area_mm2=1e-5,iou=1-1e-8,reprojection_mm=.02,graphic_sheet_mm=.002),
        baseline=json.loads((FIX/'baseline.json').read_text()),claim_boundary='Same exporter, own development families, manual view/family assumptions; no other-CAD/customer/held-out/ROI claim')
    report['summary']=dict(inputs=len(observations),positive_inputs=sum(o['expected']=='candidate' for o in observations),
        positive_passed=sum(o['expected']=='candidate' and o['passed'] for o in observations),
        withheld_inputs=sum(o['expected']=='withheld' for o in observations),withheld_passed=sum(o['expected']=='withheld' and o['passed'] for o in observations),
        false_confirmations=sum(o['expected']=='withheld' and any(t.get('status')=='candidate' for t in o['trials']) for o in observations))
    (output/'results.json').write_bytes(json_bytes(report))
    with (output/'summary.csv').open('w',newline='') as stream:
        w=csv.writer(stream);w.writerow(('id','cohort','expected','observed','reason','passed'))
        for o in observations:w.writerow((o['id'],o['cohort'],o['expected'],o['trials'][0].get('status'),o['trials'][0].get('reason'),o['passed']))
    from research_notes.drawing_family_report import write_report
    write_report(output)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--repeats',type=int,default=2)
    a=p.parse_args();raise SystemExit(0 if run(a.output_dir,a.repeats)['passed'] else 1)
