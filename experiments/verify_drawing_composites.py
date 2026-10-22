"""Audit frozen inference, independent truth, saved UI evidence and actual test results."""
import argparse,hashlib,json,re,xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit,unquote
from experiments.freeze_composite_engine import check
ROOT=Path(__file__).resolve().parents[1];FIX=ROOT/'fixtures/drawing-composites'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.assets=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='a' and 'href' in a:self.links.append(a['href'])
        if tag in ('img','script') and 'src' in a:self.assets.append(a['src'])
def verify(directory,junit):
    frozen=check();report=json.loads((directory/'results.json').read_text())
    assert report['freeze']==frozen and report['complete'] and report['repeat_stable']
    for name,digest in report['source_hashes'].items():assert sha(ROOT/name)==digest,name
    trials=[t for o in report['observations'] for t in o['trials']]
    assert len(report['observations'])==32 and len(trials)==32*report['repeats']
    for o in report['observations']:
        for key in ('drawing','context'):assert sha(FIX/o[key])==o[key+'_sha256']
        folder=directory/o['id'];assert sha(folder/('input.'+o['format']))==o['drawing_sha256']
        assert sha(folder/'context.json')==o['context_sha256']
        for t in o['trials']:
            assert not t['ground_truth_supplied'] and not t['false_confirmation']
            assert set(t['worker_inputs'])=={'drawing.'+o['format'],'context.json'}|({'review.json'} if o['cohort']=='review' else set())
            for name,digest in t['worker_input_sha256'].items():
                assert sha(folder/('input.'+o['format'] if name.startswith('drawing.') else name))==digest
            if t['status']=='candidate':assert t['reconstructed_correctly'] and t['metrics']['passed'] and t['edit_metrics']['passed']
            else:assert t['status']=='withheld' and t['reason'] and not (folder/'candidate.step').exists()
        if o['cohort']=='review':
            assert sha(folder/'review.json')==sha((FIX/o['drawing']).with_name('review.json'))
            assert json.loads((folder/'interaction.json').read_text())==o['interaction']
            assert o['interaction']['operator_kind']=='agent'
    for truth in FIX.rglob('truth.json'):
        for name,digest in json.loads(truth.read_text())['hashes'].items():assert sha(truth.parent/name)==digest
    parser=Links();parser.feed((directory/'report.html').read_text());count=0
    for href in parser.links:
        u=urlsplit(href)
        if u.scheme or not u.path:continue
        assert (directory/unquote(u.path)).is_file(),href;count+=1
    assert not any(a.startswith(('http:','https:','//')) for a in parser.assets)
    mdlinks=0
    for doc in (ROOT/'notes/drawing-composites.md',ROOT/'docs/drawing-composites.md',FIX/'README.md'):
        for href in re.findall(r'\]\(([^)]+)\)',doc.read_text()):
            u=urlsplit(href)
            if u.scheme or not u.path or u.path.endswith(('verification.json','inventory.json')):continue
            assert (doc.parent/unquote(u.path)).exists(),(doc,href);mdlinks+=1
    suites=ET.parse(junit).getroot().findall('testsuite');assert suites
    tests={k:sum(int(s.get(k,'0')) for s in suites) for k in ('tests','failures','errors','skipped')}
    assert tests['failures']==tests['errors']==tests['skipped']==0
    tests['seconds']=sum(float(s.get('time','0')) for s in suites)
    ui=json.loads((directory/'browser-check.json').read_text());assert ui['reviewDownloadMatches'] and not ui['consoleWarningsAndErrors']
    fixture_inventory={str(p.relative_to(FIX)):sha(p) for p in FIX.rglob('*') if p.is_file() and p.name!='inventory.json'}
    inventory_path=FIX/'inventory.json'
    if inventory_path.exists():assert json.loads(inventory_path.read_text())==fixture_inventory,'fixture payload changed'
    else:save(inventory_path,fixture_inventory)
    positive=[t for t in trials if t['status']=='candidate']
    audit=dict(date='2026-10-22',pytest=tests,test_xml_sha256=sha(junit),
        test_command='output/venv312/bin/python -m pytest -q --junitxml=output/drawing-composites-full-tests.xml',
        inference_freeze_sha256=sha(FIX/'engine-freeze.json'),no_post_holdout_inference_change=True,
        inputs=32,trials=len(trials),positive_trials=len(positive),repeat_stable=True,false_confirmations=0,
        html_local_links=count,markdown_local_links=mdlinks,external_html_assets=0,
        maxima=dict(parameter_mm=max(t['parameter_error_mm'] for t in positive),
            bounds_mm=max(t[k]['bounds_error_mm'] for t in positive for k in ('metrics','edit_metrics')),
            volume_mm3=max(t[k]['volume_error_mm3'] for t in positive for k in ('metrics','edit_metrics')),
            area_mm2=max(t[k]['area_error_mm2'] for t in positive for k in ('metrics','edit_metrics')),
            reprojection_mm=max(v['sampled_symmetric_max_mm'] for t in positive for v in t['projection_metrics'].values()),
            visibility_mm=max(v for t in positive for v in t['visibility_residual_mm'].values())),
        minimum_iou=min(t[k]['same_kernel_iou'] for t in positive for k in ('metrics','edit_metrics')),
        not_tested=['intersecting/touching features','three-feature CAD fixtures','held-out mixed openings','first-angle compound CAD export',
            'customer drawings','independent second 3D CAD','native Windows execution','OCR/VLM','human productivity/ROI'],
        source_sha256={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),ROOT/'src/research_notes/drawing_composite_report.py',
            ROOT/'src/research_notes/drawing_dimension_report.py',ROOT/'experiments/freeze_composite_engine.py',
            ROOT/'experiments/freeze_drawing_composites.py',ROOT/'experiments/prepare_composite_controls.py',
            ROOT/'experiments/probe_librecad_drawing_render.py',ROOT/'tests/test_drawing_composites.py']},
        fixture_inventory_sha256=sha(inventory_path),
        artifact_sha256={str(p.relative_to(directory)):sha(p) for p in directory.rglob('*') if p.is_file() and p.name!='verification.json'})
    save(directory/'verification.json',audit)
    print(json.dumps({k:v for k,v in audit.items() if not k.endswith('sha256')},indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--junit',type=Path,required=True)
    a=p.parse_args();verify(a.directory,a.junit)
