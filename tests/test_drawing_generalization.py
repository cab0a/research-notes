"""Development controls; frozen holdout measurements live separately in results."""
import copy,hashlib,json,subprocess,sys
from pathlib import Path
import pytest
from research_notes import drawing_generalization as dg
from research_notes.drawing_families import edit
from experiments.run_drawing_families import metrics,flatten
ROOT=Path(__file__).resolve().parents[1]
FIX=ROOT/'fixtures/drawing-generalization'
CASES=json.loads((FIX/'development/manifest.json').read_text())['cases']
def named(name):return next(c for c in CASES if c['id']=='development_'+name)
def inference(c):
    return dg.interpret((FIX/c['drawing']).read_bytes(),json.loads((FIX/c['context']).read_text()),c['format'],
        (FIX/c['section']).read_bytes() if c.get('section') else None)

@pytest.mark.parametrize('case',CASES,ids=lambda c:c['id'])
def test_development_dimensions_visibility_and_sections(case):
    inf=inference(case)
    assert inf['status']==case['expected'],inf
    if inf['status']=='candidate':
        truth=json.loads((FIX/case['truth']/'truth.json').read_text())
        assert flatten(inf['parameters'])==pytest.approx(flatten(truth['parameters']),abs=1e-8)
        assert inf['opening']==truth['opening']
        if inf['opening']=='bottom':
            assert inf['dimension_interpretation']['depth_derivation']=='thickness - top_reference_distance'
    else:
        assert inf['reason_code']==('dimension_missing' if case['part']=='no_depth' else 'opening_ambiguous')
        assert 'parameters' not in inf

@pytest.mark.parametrize('name',['top_svg','bottom_svg','section_bottom_dxf'])
def test_actual_step_and_edited_shape_match_independent_cad(name,tmp_path):
    c=named(name);inf=inference(c);truthdir=FIX/c['truth'];truth=json.loads((truthdir/'truth.json').read_text())
    for changed,filename,key in ((inf['parameters'],'truth.step','parameters'),(edit('pocket',inf['parameters']),'edited-truth.step','edited_parameters')):
        step=tmp_path/filename;dg.export('pocket',changed,inf['opening'],step)
        _,m=metrics(step,truthdir/filename,'pocket',truth[key]);assert m['passed'],m

def test_contradictory_section_returns_to_review():
    c=named('top_svg');section=FIX/named('section_bottom_svg')['section']
    inf=dg.interpret((FIX/c['drawing']).read_bytes(),json.loads((FIX/c['context']).read_text()),'svg',section.read_bytes())
    assert inf['status']=='withheld' and inf['reason_code']=='visibility_section_conflict'

def test_section_with_wrong_aspect_is_not_used():
    c=named('section_top_svg');source=(FIX/c['section']).read_bytes()
    # Known part length changed only in the section evaluator: aspect mismatch must reject it.
    with pytest.raises(Exception,match='section aspect ratio'):dg.section_input(source,{'length':80,'thickness':12})

def test_old_top_default_has_wrong_3d_geometry_for_bottom_drawing(tmp_path):
    c=named('bottom_svg');truthdir=FIX/c['truth'];truth=json.loads((truthdir/'truth.json').read_text())
    dg.export('pocket',c['baseline']['parameters'],'top',tmp_path/'old.step')
    _,m=metrics(tmp_path/'old.step',truthdir/'truth.step','pocket',truth['parameters'])
    assert not m['passed'] and m['same_kernel_iou']<.9

def test_librecad_absent_annotations_are_not_treated_as_dimensions():
    manifest=json.loads((FIX/'portability/manifest.json').read_text())
    for c in manifest['cases']:
        inf=inference(c)
        assert inf['reason_code']=='dimension_text_unavailable' and 'parameters' not in inf

def test_malformed_svg_is_a_parse_failure():
    c=named('top_svg');ctx=json.loads((FIX/c['context']).read_text())
    assert dg.interpret(b'<svg>',ctx,'svg')['reason_code']=='drawing_parse_failure'

def test_copied_worker_needs_no_truth_or_dimensions_in_context(tmp_path):
    c=named('section_bottom_dxf')
    for key,name in (('drawing','drawing.dxf'),('context','context.json'),('section','section.svg')):
        (tmp_path/name).write_bytes((FIX/c[key]).read_bytes())
    r=subprocess.run([sys.executable,'-m','research_notes.drawing_generalization',str(tmp_path/'drawing.dxf'),str(tmp_path/'context.json'),
        '--section',str(tmp_path/'section.svg'),'--output-dir',str(tmp_path/'out')],cwd=tmp_path,capture_output=True,timeout=60)
    assert r.returncode==0,r.stderr
    inf=json.loads((tmp_path/'out/inference.json').read_text())
    assert inf['status']=='candidate' and inf['opening']=='bottom' and inf['parameters']['pocket_depth']==8
