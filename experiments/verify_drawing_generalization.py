"""Audit actual trials, frozen inference, fixture hashes, local links and test output."""
import argparse,hashlib,json,re,xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit,unquote
from research_notes.drawing_to_cad import json_bytes
from experiments.freeze_drawing_engine import check
ROOT=Path(__file__).resolve().parents[1];FIX=ROOT/'fixtures/drawing-generalization'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
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
    assert len(report['observations'])==68 and len(trials)==68*report['repeats']
    for o in report['observations']:
        for key in ('drawing','context','section'):
            if key in o:assert sha(FIX/o[key])==o[key+'_sha256']
        assert sha(directory/o['id']/('input.'+o['format']))==o['drawing_sha256']
        for t in o['trials']:
            assert t['ground_truth_supplied'] is False
            assert not t.get('false_confirmation'),o['id']
            if t['status']=='candidate':
                assert t['reconstructed_correctly'] and t['metrics']['passed'] and t['edit_metrics']['passed'],o['id']
            else:assert t['status']=='withheld' and t['reason']
    for truth in FIX.glob('*/evaluation/*/truth.json'):
        for name,digest in json.loads(truth.read_text())['hashes'].items():assert sha(truth.parent/name)==digest
    parser=Links();parser.feed((directory/'report.html').read_text());count=0
    for href in parser.links:
        u=urlsplit(href)
        if u.scheme or not u.path or u.path=='verification.json':continue
        assert (directory/unquote(u.path)).is_file(),href;count+=1
    assert not any(a.startswith(('http:','https:','//')) for a in parser.assets)
    mdlinks=0
    for doc in (ROOT/'notes/drawing-generalization.md',ROOT/'docs/drawing-generalization.md',FIX/'README.md'):
        for href in re.findall(r'\]\(([^)]+)\)',doc.read_text()):
            u=urlsplit(href)
            if u.scheme or not u.path or u.path.endswith('verification.json'):continue
            assert (doc.parent/unquote(u.path)).exists(),(doc,href);mdlinks+=1
    suites=ET.parse(junit).getroot().findall('testsuite');assert suites
    tests={k:sum(int(s.get(k,'0')) for s in suites) for k in ('tests','failures','errors','skipped')}
    assert tests['failures']==tests['errors']==tests['skipped']==0
    tests['seconds']=sum(float(s.get('time','0')) for s in suites)
    ui=json.loads((directory/'browser-check.json').read_text());assert ui['right_drag_observed'] and ui['underside_observed'] and ui['observed_console_errors']==[]
    js=json.loads((directory/'viewer-check.json').read_text());assert js['passed'] and js['assertions']==5
    assert js['source_sha256']==sha(ROOT/'src/research_notes/drawing_dimension_report.py')
    positive=[t for t in trials if t['status']=='candidate']
    audit=dict(date='2026-10-22',pytest=tests,test_xml_sha256=sha(junit),
        test_command='output/venv312/bin/python -m pytest -q --junitxml=output/drawing-generalization-tests.xml',
        inference_frozen_before_holdout=True,no_post_holdout_inference_change=True,repeat_stable=True,
        inputs=len(report['observations']),trials=len(trials),positive_trials=len(positive),
        false_confirmations=0,html_local_links=count,markdown_local_links=mdlinks,external_html_assets=0,
        maxima=dict(parameter_mm=max(t['parameter_error_mm'] for t in positive),bounds_mm=max(t[k]['bounds_error_mm'] for t in positive for k in ('metrics','edit_metrics')),
            volume_mm3=max(t[k]['volume_error_mm3'] for t in positive for k in ('metrics','edit_metrics')),
            area_mm2=max(t[k]['area_error_mm2'] for t in positive for k in ('metrics','edit_metrics')),
            reprojection_mm=max(v['sampled_symmetric_max_mm'] for t in positive for v in t['projection_metrics'].values())),
        minimum_iou=min(t[k]['same_kernel_iou'] for t in positive for k in ('metrics','edit_metrics')),
        not_tested=['customer drawings','held-out part families','independently authored second 3D CAD','native Windows CAD execution','OCR/VLM','automatic section/view semantics','ROI'],
        source_sha256={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),ROOT/'src/research_notes/drawing_generalization_report.py',ROOT/'src/research_notes/drawing_dimension_report.py',
            ROOT/'experiments/check_drawing_viewer.cjs',ROOT/'experiments/freeze_drawing_engine.py',ROOT/'experiments/freeze_drawing_generalization.py',ROOT/'experiments/export_librecad_drawings.py',ROOT/'tests/test_drawing_generalization.py']},
        fixture_sha256={str(p.relative_to(FIX)):sha(p) for p in FIX.rglob('*') if p.is_file()},
        artifact_sha256={str(p.relative_to(directory)):sha(p) for p in directory.rglob('*') if p.is_file() and p.name!='verification.json'})
    (directory/'verification.json').write_bytes(json_bytes(audit))
    print(json.dumps({k:v for k,v in audit.items() if not k.endswith('sha256')},indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--junit',type=Path,required=True)
    a=p.parse_args();verify(a.directory,a.junit)
