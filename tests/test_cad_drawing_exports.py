"""Boundary tests for native CAD exports, with adversarial changes to real DXF."""
import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys

import pytest

ezdxf=pytest.importorskip('ezdxf')
from research_notes.cad_drawing_import import interpret_cad_drawing
from research_notes.drawing_dimensions import interpret_dimension_svg

ROOT=Path(__file__).resolve().parents[1]
FIX=ROOT/'fixtures/cad-drawing-exports'
CASES=json.loads((FIX/'manifest.json').read_text())['cases']


def context(name='one'):
    return json.loads((FIX/'inputs'/name/'context.json').read_text())


def document(name='one'):
    return ezdxf.read(io.StringIO((FIX/'inputs'/name/'drawing.dxf').read_text()))


def interpret(doc,ctx=None):
    stream=io.StringIO();doc.write(stream)
    return interpret_cad_drawing(stream.getvalue().encode(),ctx or context(),'dxf')


@pytest.mark.parametrize('case',CASES,ids=lambda c:c['id'])
def test_frozen_case(case):
    source=(FIX/case['drawing']).read_bytes()
    result=interpret_cad_drawing(source,json.loads((FIX/case['context']).read_text()),case['format'])
    assert result['status']==case['expected_status']
    assert result.get('reason_code')==case['expected_reason']
    assert result['source_sha256']==hashlib.sha256(source).hexdigest()
    assert not result['ai_used']
    if result['status']=='withheld':assert 'parameters' not in result


def test_actual_svg_does_not_enter_old_flat_grammar():
    assert interpret_dimension_svg((FIX/'inputs/one/drawing.svg').read_bytes(),context())['status']=='withheld'


def test_scale_and_projection_invariance():
    recovered=[interpret_cad_drawing((FIX/'inputs'/name/'drawing.dxf').read_bytes(),context(name),'dxf')['parameters'] for name in ('one','first','scaled')]
    assert recovered[0]==recovered[1]==recovered[2]


def test_decimal_dimensions_not_constants():
    result=interpret(document('decimal'),context('decimal'))
    assert result['parameters']==dict(width=52.5,length=37.25,thickness=6.5,holes=[dict(x=17.5,y=13.25,diameter=5.5)])


def test_layer_names_and_entity_order_are_not_semantics():
    doc=document();ctx=context()
    for i,(role,layer) in enumerate(ctx['view_roles'].items()):
        new=f'opaque_{i}';doc.layers.get(layer).rename(new);ctx['view_roles'][role]=new
    # Dimension layers and block names are never used for feature identification.
    for i,d in enumerate(doc.modelspace().query('DIMENSION')):
        name='dim_'+str(900-i);doc.layers.get(d.dxf.layer).rename(name)
    for e in reversed(list(doc.modelspace())):
        doc.modelspace().unlink_entity(e);doc.modelspace().add_entity(e)
    result=interpret(doc,ctx)
    assert result['status']=='candidate'
    assert result['parameters']['holes']==[dict(x=12,y=10,diameter=6)]


def test_text_and_picture_must_agree():
    doc=document();d=next(iter(doc.modelspace().query('DIMENSION')));d.dxf.text='41'
    assert interpret(doc)['reason_code']=='dimension_display_conflict'


def test_consistent_wrong_annotation_is_not_replaced_by_scaled_geometry():
    doc=document();d=next(d for d in doc.modelspace().query('DIMENSION') if d.dxf.text=='12')
    d.dxf.text='13'
    for e in doc.blocks[d.dxf.geometry].query('TEXT'):e.dxf.text='13'
    assert interpret(doc)['reason_code']=='annotation_geometry_mismatch'


def test_definition_point_disconnected_from_shape():
    doc=document();d=next(iter(doc.modelspace().query('DIMENSION')))
    d.dxf.defpoint2=(999,999,0)
    assert interpret(doc)['reason_code']=='dimension_target_ambiguous'


def test_missing_interior_edge_withholds():
    doc=document();msp=doc.modelspace()
    edge=next(e for e in msp.query('LINE') if e.dxf.layer=='Front' and abs(e.dxf.start.x-134)<1e-6)
    msp.delete_entity(edge)
    assert interpret(doc)['reason_code']=='hidden_line_conflict'


def test_unknown_interior_curve_not_dropped():
    doc=document();spline=next(iter(doc.modelspace().query('SPLINE')))
    cp=list(spline.control_points);cp[1]=(138,85,0);spline.control_points=cp
    assert interpret(doc)['reason_code']=='unsupported_spline'


def test_extra_shape_outside_views_is_not_ignored():
    doc=document();doc.modelspace().add_line((0,0),(10,0))
    assert interpret(doc)['reason_code']=='unmapped_geometry'


def test_wrong_units():
    doc=document();doc.units=1
    assert interpret(doc)['reason_code']=='drawing_unit_mismatch'


def test_hidden_layer_is_not_interpreted_as_visible():
    doc=document();doc.layers.get('Top').off()
    assert interpret(doc)['reason_code']=='hidden_entity'


@pytest.mark.parametrize('data',[b'garbage',b'\xff',b'0\nSECTION\n2\nENTITIES\n'])
def test_bad_dxf_is_recorded(data):
    assert interpret_cad_drawing(data,context(),'dxf')['status']=='withheld'


def test_no_numeric_context_or_truth_file_access(monkeypatch):
    source=(FIX/'inputs/one/drawing.dxf').read_bytes();ctx=context()
    def forbidden(*a,**k):raise AssertionError('interpreter must not read external paths')
    monkeypatch.setattr(Path,'read_bytes',forbidden);monkeypatch.setattr(Path,'read_text',forbidden)
    assert interpret_cad_drawing(source,ctx,'dxf')['status']=='candidate'
    ctx['width']=40
    assert interpret_cad_drawing(source,ctx,'dxf')['reason_code']=='context_missing'


def test_withheld_cli_has_no_model_and_refuses_reused_directory(tmp_path):
    command=[sys.executable,'-m','research_notes.cad_drawing_import',str(FIX/'inputs/no_x/drawing.dxf'),str(FIX/'inputs/no_x/context.json'),'--output-dir',str(tmp_path)]
    assert subprocess.run(command,capture_output=True).returncode==0
    assert set(p.name for p in tmp_path.iterdir())=={'inference.json'}
    assert subprocess.run(command,capture_output=True).returncode!=0


def test_frozen_inputs_match_authoring_hashes():
    manifest=json.loads((FIX/'manifest.json').read_text())
    for path,digest in manifest['file_hashes'].items():assert hashlib.sha256((FIX/path).read_bytes()).hexdigest()==digest
