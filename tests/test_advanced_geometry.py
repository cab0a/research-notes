from dataclasses import replace
import math
import numpy as np
import pytest

from research_notes.advanced_geometry_studies import pmi_fixture
from research_notes.semantic_pmi import inspect_pmi
from research_notes.spline_geometry import quarter_circle,evaluate_curve,kernel_curve
from research_notes.differential_geometry import surface_differential,sampled_continuity
from research_notes.repair_policies import RepairPolicy,repair_shape


def test_pmi_semantics_are_source_linked_and_ignore_display():
    source=pmi_fixture(); report=inspect_pmi(source)
    assert len(report["semantic"])==4,report
    assert not report["diagnostics"]
    dimension=next(r for r in report["semantic"] if r["kind"]=="dimension")
    assert dimension["value_mm"]==4.
    for item in dimension["evidence"]:
        span=item["span"]
        assert source[span["start_byte"]:span["end_byte"]].decode()==item["source"]
    assert inspect_pmi(source.replace(b"999 mm",b"0 mm"))["semantic"][0]["value_mm"]==4.


def test_invalid_datum_invalidates_dependent_tolerance():
    report=inspect_pmi(pmi_fixture().replace(b"#15,#16",b"#15,#8"))
    assert {r["kind"] for r in report["semantic"]}=={"dimension","flatness_tolerance"}
    assert {r["entity_id"] for r in report["diagnostics"]}=={16,21}


def test_small_feature_removal_requires_explicit_budget():
    from research_notes.parametric_features import PlateSpec,feature_spec,build_plate,apply_feature
    from research_notes.step_reconstruction import face_evidence
    from research_notes.modeling_common import measure_shape
    plate=PlateSpec();shape=apply_feature(build_plate(plate).shape,plate,feature_spec("through_hole",x=4.,y=4.,radius=.2)).shape
    selected=tuple(f.face_index for f in face_evidence(shape) if f.surface_type=="cylinder")
    rejected=repair_shape(shape,RepairPolicy("remove_faces",selected_faces=selected))
    assert rejected.shape.IsSame(shape) and rejected.audit["status"]=="rejected_rolled_back"
    accepted=repair_shape(shape,RepairPolicy("remove_faces",maximum_volume_change=1.,maximum_area_change=10.,selected_faces=selected))
    assert accepted.audit["status"]=="accepted"
    assert measure_shape(accepted.shape).absolute_volume==pytest.approx(480.)
    assert accepted.audit["material_difference_volume"]==pytest.approx(math.pi*.2**2*4)


@pytest.mark.parametrize("parameter",[0.,.1,.5,.9,1.])
def test_rational_circle_against_equation_and_derivative(parameter):
    spec=quarter_circle(); result=evaluate_curve(spec,parameter)
    p,d=np.array(result["point"]),np.array(result["derivative"])
    assert np.linalg.norm(p)==pytest.approx(2.,abs=1e-12)
    assert p@d==pytest.approx(0.,abs=1e-12)
    assert kernel_curve(spec).Value(parameter).Distance(__import__("OCP.gp",fromlist=["gp_Pnt"]).gp_Pnt(*p))<1e-12


@pytest.mark.parametrize("changes",[{"periodic":True},{"weights":(1.,0.,1.)},{"multiplicities":(2,3)},{"knots":(1.,0.)}])
def test_spline_domain_rejections(changes):
    with pytest.raises(ValueError): evaluate_curve(replace(quarter_circle(),**changes),.5)


def test_curvature_orientation_and_nonunique_sphere_axes():
    from OCP.Geom import Geom_SphericalSurface
    from OCP.gp import gp_Ax3
    sphere=Geom_SphericalSurface(gp_Ax3(),3.)
    a=surface_differential(sphere,.3,.2);b=surface_differential(sphere,.3,.2,orientation=-1)
    assert a["gaussian_curvature"]==pytest.approx(1/9)
    assert a["mean_curvature"]==pytest.approx(-1/3)
    assert b["mean_curvature"]==pytest.approx(1/3)
    assert not a["principal_directions_unique"]
    assert surface_differential(sphere,0.,math.pi/2)["status"]=="singular"


def test_repair_rejection_retains_original_geometry():
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from research_notes.modeling_common import measure_shape
    shape=BRepPrimAPI_MakeBox(2.,3.,4.).Shape();before=measure_shape(shape)
    result=repair_shape(shape,RepairPolicy("unify",maximum_tolerance=1e-10))
    assert result.audit["status"]=="rejected_rolled_back"
    assert result.shape.IsSame(shape)
    assert measure_shape(shape)==before
