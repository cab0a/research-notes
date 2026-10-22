"""Development fixtures, negative controls, evidence isolation and editable CAD."""
import copy,hashlib,json,math,subprocess,sys
from pathlib import Path
import pytest
from research_notes import drawing_families as df
from research_notes.drawing_to_cad import DrawingIssue
from research_notes.drawing_svg_extensions import expand_path,arc_cubics
from research_notes.drawing_family_evidence import annotation
from research_notes.modeling_common import measure_shape
from experiments.run_drawing_families import analytic,flatten

ROOT=Path(__file__).resolve().parents[1]
FIX=ROOT/'fixtures/drawing-families'
CASES=json.loads((FIX/'manifest.json').read_text())['cases']
def data(case):
    return (FIX/case['drawing']).read_bytes(),json.loads((FIX/case['context']).read_text())
def named(name):
    return next(c for c in CASES if c['id']==name)

@pytest.mark.parametrize('case',CASES,ids=lambda c:c['id'])
def test_fixed_inputs_and_independent_parameters(case):
    source,ctx=data(case)
    assert hashlib.sha256(source).hexdigest()==case['drawing_sha256']
    assert hashlib.sha256((FIX/case['context']).read_bytes()).hexdigest()==case['context_sha256']
    original=copy.deepcopy(ctx)
    result=df.interpret(source,ctx,case['format'])
    assert ctx==original
    assert result['status']==case['expected'],result
    assert result['source_sha256']==case['drawing_sha256']
    if case['expected']=='withheld':
        assert result['reason_code']==case['expected_reason'],result
        assert 'parameters' not in result
    else:
        truth=json.loads((FIX/'evaluation'/case['part']/'truth.json').read_text())
        assert flatten(result['parameters'])==pytest.approx(flatten(truth['parameters']),abs=1e-8)
        assert max(v['sampled_symmetric_max_mm'] for v in result['projection_metrics'].values())<=.02
        ids={d['id'] for d in result['evidence']['dimensions']}
        assert all(ref in ids or ref.startswith('derived:') for refs in result['bindings'].values() for ref in refs)

@pytest.mark.parametrize('part',['unseen_small','l_bracket','stepped_shaft','pocket'])
def test_analytic_geometry_and_edits(part,tmp_path):
    truth=json.loads((FIX/'evaluation'/part/'truth.json').read_text())
    f,p=truth['family'],truth['parameters']
    for params in (p,df.edit(f,p)):
        shape=df.build_family(f,params);m=measure_shape(shape);v,a=analytic(f,params)
        assert m.analyzer_valid and m.solid_count==1
        assert m.absolute_volume==pytest.approx(v,abs=1e-7)
        assert m.surface_area==pytest.approx(a,abs=1e-7)
    assert flatten(df.edit(f,p))==flatten(truth['edited_parameters'])

def test_worker_has_only_copied_drawing_context_and_empty_output(tmp_path):
    case=named('l_bracket_svg');source,ctx=data(case)
    drawing=tmp_path/'arbitrary-name.svg';drawing.write_bytes(source)
    context=tmp_path/'review.json';context.write_text(json.dumps(ctx))
    target=tmp_path/'result'
    r=subprocess.run([sys.executable,'-m','research_notes.drawing_families',str(drawing),str(context),'--output-dir',str(target)],
                     cwd=tmp_path,capture_output=True,timeout=60)
    assert r.returncode==0,r.stderr
    inf=json.loads((target/'inference.json').read_text())
    assert inf['status']=='candidate'
    assert inf['parameters']==dict(width=40.,length=30.,height=24.,wall_thickness=5.,base_thickness=5.)
    assert not any(k in ctx for k in ('width','truth','scale','parameters'))
    import runpy
    recipe=runpy.run_path(str(target/'candidate.py'))
    assert recipe['PARAMETERS']==inf['parameters']
    assert recipe['SOURCE_SHA256']==inf['source_sha256']

def test_review_corrects_view_mapping_without_numeric_dimensions():
    source,ctx=data(named('wrong_views_svg'))
    assert df.interpret(source,ctx,'svg')['reason_code']=='dimension_conflict'
    ctx['view_roles']['front'],ctx['view_roles']['top']=ctx['view_roles']['top'],ctx['view_roles']['front']
    assert df.interpret(source,ctx,'svg')['status']=='candidate'

@pytest.mark.parametrize('mutate,reason',[
    (lambda c:c.update(width=46),'context_missing'),
    (lambda c:c.update(projection='unknown'),'projection_unknown'),
    (lambda c:c.update(unit='inch'),'unsupported_context'),
    (lambda c:c['view_roles'].update(top=c['view_roles']['front']),'view_mapping'),
    (lambda c:c.update(family_assumption='assembly'),'unsupported_context')])
def test_context_cannot_override_design_or_hide_ambiguity(mutate,reason):
    source,ctx=data(named('unseen_small_svg'));mutate(ctx)
    assert df.interpret(source,ctx,'svg')['reason_code']==reason

def test_quantity_and_shared_baseline_have_traceable_bindings():
    source,ctx=data(named('quantity_two_svg'));inf=df.interpret(source,ctx,'svg')
    assert inf['bindings']['hole_1.diameter']==inf['bindings']['hole_2.diameter']
    source,ctx=data(named('three_shared_svg'));inf=df.interpret(source,ctx,'svg')
    assert inf['bindings']['hole_1.x']==inf['bindings']['hole_2.x']
    assert len(inf['parameters']['holes'])==3

@pytest.mark.parametrize('text',['6 ±0.1','6 H7','R6','4 x 6 THRU','2 x 0 THRU','-1','NaN'])
def test_unsupported_or_invalid_diameter_is_not_silently_parsed(text):
    with pytest.raises(DrawingIssue):annotation(text,True)

@pytest.mark.parametrize('args',[
    [3,4,0,0,1,3,3], [3,3,0,2,1,3,3], [3,3,0,0,1,0,0], [1,1,0,0,1,4,0]])
def test_unsupported_arc_requires_hold(args):
    with pytest.raises(DrawingIssue):arc_cubics((0,0),args)

def test_relative_quadratic_normalizes_and_curve_is_not_discarded():
    assert expand_path('M1 2 q 2 2 4 4')=='M1.0 2.0 L5.0 6.0'
    assert 'C' in expand_path('M0 0 Q 1 2 4 0')

@pytest.mark.parametrize('fmt,content',[('svg',b'<svg>'),('dxf',b'not a dxf')])
def test_parse_failures_are_distinct_from_kernel(fmt,content):
    _,ctx=data(named('unseen_small_'+fmt))
    inf=df.interpret(content,ctx,fmt)
    assert inf['status']=='withheld' and inf['failure_stage']=='drawing_recognition'
    assert inf['reason_code']=='drawing_parse_failure'

def test_kernel_failure_has_separate_reason(monkeypatch):
    source,ctx=data(named('l_bracket_svg'))
    def fail(*a):raise RuntimeError('synthetic kernel failure')
    monkeypatch.setattr(df,'build_family',fail)
    inf=df.interpret(source,ctx,'svg')
    assert inf['failure_stage']=='kernel_calculation'
    assert inf['reason_code']=='kernel_failure'

def test_different_shape_cannot_pass_contour_check(monkeypatch):
    source,ctx=data(named('l_bracket_svg'));original=df.build_family
    def wrong(f,p):
        p={**p,'wall_thickness':p['wall_thickness']+2}
        return original(f,p)
    monkeypatch.setattr(df,'build_family',wrong)
    assert df.interpret(source,ctx,'svg')['reason_code']=='reprojection_conflict'

@pytest.mark.parametrize('part,key,value',[
    ('l_bracket','wall_thickness',30),('l_bracket','base_thickness',24),
    ('stepped_shaft','diameter2',17),('stepped_shaft','length1',0),
    ('pocket','pocket_depth',12),('pocket','pocket_width',60),('pocket','pocket_y',float('nan'))])
def test_invalid_parameters_do_not_create_solid(part,key,value):
    truth=json.loads((FIX/'evaluation'/part/'truth.json').read_text())
    with pytest.raises(DrawingIssue):
        df.build_family(truth['family'],{**truth['parameters'],key:value})

def test_baseline_remains_previous_implementation():
    baseline=json.loads((FIX/'baseline.json').read_text())
    for name,digest in baseline['code_hashes'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
    cases=[o for o in baseline['observations'] if o['initial_unseen_setting']]
    assert len(cases)==4 and sum(o['status']=='candidate' for o in cases)==3

def test_report_crop_uses_svg_viewbox_units_not_sheet_millimeters():
    import base64,xml.etree.ElementTree as ET
    from research_notes.drawing_family_report import crops
    source,ctx=data(named('l_bracket_svg'));inf=df.interpret(source,ctx,'svg')
    result=crops(source,inf,'svg')
    svg=ET.fromstring(base64.b64decode(result['right'].split(',')[1]))
    x,y,w,h=map(float,svg.get('viewBox').split())
    # Original SVG stores the right profile at x=3050..3350, y=2000..2240.
    assert x<=3050<3350<=x+w and y<=2000<2240<=y+h
    assert x>1000
