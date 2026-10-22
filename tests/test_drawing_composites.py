"""Compound development controls, review provenance and independent original/edit solids."""
import copy,hashlib,json,subprocess,sys
from pathlib import Path
import pytest
from research_notes import drawing_composites as dc
from research_notes.drawing_to_cad import DrawingIssue
from experiments.composite_metrics import canonical,metrics,edited
ROOT=Path(__file__).resolve().parents[1];FIX=ROOT/'fixtures/drawing-composites'
DEV=json.loads((FIX/'development/manifest.json').read_text())['cases']
CONTROLS=json.loads((FIX/'controls/manifest.json').read_text())['cases']
def infer(c,review=None):return dc.interpret((FIX/c['drawing']).read_bytes(),json.loads((FIX/c['context']).read_text()),c['format'],review)
def review(c):return json.loads((FIX/c['drawing']).with_name('review.json').read_text())
@pytest.mark.parametrize('c',DEV,ids=lambda c:c['id'])
def test_native_development_and_opening_combinations(c,tmp_path):
    r=infer(c);assert r['status']==c['expected'],r
    if r['status']=='withheld':assert r['reason_code']=='opening_evidence_missing';return
    truth=json.loads((FIX/c['truth']/'truth.json').read_text())
    assert canonical(r['parameters'])==canonical(truth['parameters'])
    assert sum(a['compatible'] for a in r['opening_alternatives'])==1
    for p,name,key in ((r['parameters'],'truth.step','parameters'),(dc.edit(r['parameters']),'edited-truth.step','edited_parameters')):
        dc.export(p,tmp_path/name);_,m=metrics(tmp_path/name,FIX/c['truth']/name,truth[key]);assert m['passed'],m

@pytest.mark.parametrize('c',[c for c in CONTROLS if c['cohort']=='review'],ids=lambda c:c['id'])
def test_browser_selected_id_repairs_old_failure_without_numeric_override(c,tmp_path):
    initial=infer(c);assert initial['reason_code']=='dimension_label_ambiguous'
    assert initial['review_request']['automatic_candidate_count']==0
    r=infer(c,review(c));assert r['status']=='candidate',r
    truth=json.loads((FIX/c['truth']/'truth.json').read_text())
    assert canonical(r['parameters'])==canonical(truth['parameters'])
    for p,name,key in ((r['parameters'],'truth.step','parameters'),(edited(r['parameters'],c['edit_policy']),'edited-truth.step','edited_parameters')):
        dc.export(p,tmp_path/name);_,m=metrics(tmp_path/name,FIX/c['truth']/name,truth[key]);assert m['passed'],m
    interaction=json.loads((FIX/c['drawing']).with_name('interaction.json').read_text())
    assert interaction['operator_kind']=='agent' and len(interaction['events'])==1

@pytest.mark.parametrize('c',[c for c in CONTROLS if c['cohort']=='negative'],ids=lambda c:c['id'])
def test_negative_drawings_are_withheld(c):
    r=infer(c);assert r['status']=='withheld' and 'parameters' not in r
    assert r['reason_code']=={'missing_depth':'feature_depth_ambiguous','visibility_lost':'visibility_conflict','wrong_views':'dimension_conflict','dimension_conflict':'geometry_dimension_conflict'}[c['id']]

@pytest.mark.parametrize('mutation,reason',[
    (lambda r:r.update(drawing_sha256='0'*64),'review_source_mismatch'),
    (lambda r:r['labels'].update({'path:45':'text:7'}),'review_choice_invalid'),
    (lambda r:r['labels'].update({'path:999':'text:5'}),'review_choice_invalid'),
    (lambda r:r.update(parameters={'width':81}),'review_source_mismatch')])
def test_review_cannot_substitute_values_or_another_source(mutation,reason):
    c=next(c for c in CONTROLS if c['id']=='review_pocket_1');v=review(c);mutation(v)
    assert infer(c,v)['reason_code']==reason

@pytest.mark.parametrize('change',[
    lambda p:p['features'][1].update(x=20,y=20),
    lambda p:p['features'][0].update(depth=p['thickness']),
    lambda p:p['features'][0].update(opening='side'),
    lambda p:p['features'][0].update(kind='fillet'),
    lambda p:p['features'][0].update(width=float('nan'))])
def test_unsupported_interaction_and_invalid_dimensions_do_not_build(change):
    p=json.loads((FIX/'development/evaluation/pocket_hole/truth.json').read_text())['parameters'];change(p)
    with pytest.raises(DrawingIssue):dc.build(p)

def test_reconstruction_worker_uses_only_copied_drawing_context_and_ids(tmp_path):
    c=next(c for c in CONTROLS if c['id']=='review_pocket_4')
    for src,name in ((FIX/c['drawing'],'drawing.svg'),(FIX/c['context'],'context.json'),(FIX/c['drawing']).with_name('review.json') and ((FIX/c['drawing']).with_name('review.json'),'review.json')):
        (tmp_path/name).write_bytes(src.read_bytes())
    args=[sys.executable,'-m','research_notes.drawing_composites',str(tmp_path/'drawing.svg'),str(tmp_path/'context.json'),'--review',str(tmp_path/'review.json'),'--output-dir',str(tmp_path/'out')]
    r=subprocess.run(args,cwd=tmp_path,capture_output=True,timeout=60);assert r.returncode==0,r.stderr
    result=json.loads((tmp_path/'out/inference.json').read_text());assert result['status']=='candidate'
    assert result['parameters']['features'][0]['opening']=='bottom'
