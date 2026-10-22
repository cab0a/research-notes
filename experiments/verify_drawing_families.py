"""Audit frozen drawing-family inputs, numerical evidence, test run and artifacts."""
import argparse,hashlib,json,re,xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit,unquote
from experiments.verify_cad_svg_pairs import Links
from experiments.run_drawing_families import metrics,flatten
from research_notes.drawing_to_cad import json_bytes
ROOT=Path(__file__).resolve().parents[1]
FIX=ROOT/'fixtures/drawing-families'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def verify(directory,junit):
    report=json.loads((directory/'results.json').read_text());manifest=json.loads((FIX/'manifest.json').read_text())
    assert report['passed'] and report['repeats']==2
    assert report['summary']==dict(inputs=32,positive_inputs=21,positive_passed=21,withheld_inputs=11,withheld_passed=11,false_confirmations=0)
    assert len(report['pairs'])==11 and all(p['passed'] for p in report['pairs'])
    trials=[t for o in report['observations'] for t in o['trials']]
    assert len(trials)==64 and all(t['passed'] and not t['ground_truth_supplied'] for t in trials)
    assert sha(ROOT/'experiments/export_drawing_families.FCMacro')==manifest['authoring_macro_sha256']
    for case in manifest['cases']:
        folder=directory/case['id'];inf=json.loads((folder/'inference.json').read_text())
        for key in ('drawing','context'):assert sha(FIX/case[key])==case[key+'_sha256']
        assert sha(folder/('input.'+case['format']))==case['drawing_sha256']==inf['source_sha256']
        assert sha(folder/'context.json')==case['context_sha256']
        assert inf['status']==case['expected']
        if case['expected']=='withheld':
            assert inf['reason_code']==case['expected_reason']
            assert not any((folder/f).exists() for f in ('candidate.py','candidate.step','edited.step','model.json','preview.json'))
        else:
            truth=json.loads((FIX/'evaluation'/case['part']/'truth.json').read_text())
            assert flatten(truth['parameters'])==flatten(inf['parameters'])
            for f,digest in truth['hashes'].items():assert sha(FIX/'evaluation'/case['part']/f)==digest
    for name,digest in report['code_input_hashes'].items():assert sha(ROOT/name)==digest,name
    for name,digest in report['baseline']['code_hashes'].items():assert sha(ROOT/name)==digest,name
    page=Links();page.feed((directory/'report.html').read_text())
    links=0
    for href in page.links:
        t=urlsplit(href)
        if t.scheme or not t.path:continue
        assert (directory/unquote(t.path)).exists(),href
        links+=1
    assert not page.external_assets
    docs=[ROOT/'README.md',ROOT/'docs/studies.md',ROOT/'docs/reproducibility.md',ROOT/'notes/drawing-families.md',
          ROOT/'docs/drawing-families.md',FIX/'README.md',directory/'README.md']
    mdlinks=0
    for doc in docs:
        for href in re.findall(r'\]\(([^)]+)\)',doc.read_text()):
            t=urlsplit(href)
            if t.scheme or not t.path or t.path.endswith('verification.json'):continue
            assert (doc.parent/unquote(t.path)).exists(),(doc,href)
            mdlinks+=1
    suite=ET.parse(junit).getroot().find('testsuite')
    assert int(suite.get('failures'))==int(suite.get('errors'))==int(suite.get('skipped'))==0
    ui=json.loads((directory/'browser-check.json').read_text())
    assert ui['downloaded_context_used_in_cli'] and ui['observed_console_errors']==[]
    corrected=directory/'review-correction'
    assert sha(corrected/'input.svg')==sha(FIX/'variants/wrong_views/drawing.svg')
    before=json.loads((FIX/'variants/wrong_views/context.json').read_text());after=json.loads((corrected/'context.json').read_text())
    before['view_roles']['front'],before['view_roles']['top']=before['view_roles']['top'],before['view_roles']['front']
    assert before==after
    inf=json.loads((corrected/'regenerated/inference.json').read_text())
    truthdir=FIX/'evaluation/unseen_small';truth=json.loads((truthdir/'truth.json').read_text())
    assert inf['status']=='candidate' and flatten(inf['parameters'])==flatten(truth['parameters'])
    _,review_metrics=metrics(corrected/'regenerated/candidate.step',truthdir/'truth.step','plate',truth['parameters'])
    assert review_metrics['passed']
    positive=[t for t in trials if t['status']=='candidate']
    audit=dict(date='2026-10-22',base_commit='c95aeca568b0f77127479198cb4e13b2522e0ac2',
        pytest=dict(tests=int(suite.get('tests')),failures=0,errors=0,skipped=0,seconds=float(suite.get('time'))),
        test_command='python -m pytest -q --junitxml=output/drawing-families-tests.xml',
        test_xml_sha256=sha(junit),test_source_sha256=sha(ROOT/'tests/test_drawing_families.py'),
        positive_trials=len(positive),withheld_trials=len(trials)-len(positive),pairs=11,
        maxima=dict(parameter_mm=max(t['parameter_error_mm'] for t in positive),
            bounds_mm=max(t[k]['bounds_error_mm'] for t in positive for k in ('metrics','edit_metrics')),
            volume_mm3=max(t[k]['volume_error_mm3'] for t in positive for k in ('metrics','edit_metrics')),
            area_mm2=max(t[k]['area_error_mm2'] for t in positive for k in ('metrics','edit_metrics')),
            reprojection_mm=max(m['sampled_symmetric_max_mm'] for t in positive for m in t['projection_metrics'].values())),
        minimum_iou=min(t[k]['same_kernel_iou'] for t in positive for k in ('metrics','edit_metrics')),
        source_input_truth_hashes_match=True,html_local_links=links,markdown_local_links=mdlinks,external_html_assets=0,
        reviewed_context_cli_metrics=review_metrics,
        not_tested=['other CAD exporters','native Windows','customer drawings','held-out families','AI/OCR','browser CAD recomputation','operator ROI'],
        supplemental_source_hashes={str(p.relative_to(ROOT)):sha(p) for p in
            [ROOT/'experiments/freeze_drawing_families.py',ROOT/'experiments/derive_drawing_family_controls.py',Path(__file__),ROOT/'pyproject.toml']},
        fixture_sha256={str(p.relative_to(FIX)):sha(p) for p in FIX.rglob('*') if p.is_file()},
        artifact_sha256={str(p.relative_to(directory)):sha(p) for p in directory.rglob('*') if p.is_file() and p.name!='verification.json'})
    (directory/'verification.json').write_bytes(json_bytes(audit))
    print(json.dumps({k:v for k,v in audit.items() if k not in ('artifact_sha256','fixture_sha256')},indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--junit',type=Path,required=True)
    a=p.parse_args();verify(a.directory,a.junit)
