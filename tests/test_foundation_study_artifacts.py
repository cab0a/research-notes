from pathlib import Path
import json
import pytest
from research_notes.foundation_studies import STUDIES,run_study

ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("version,name,module",STUDIES)
def test_foundation_artifacts_reproduce_exactly(tmp_path,version,name,module):
    output=tmp_path/"results";fixtures=tmp_path/"fixtures"
    rows=run_study(name,output,fixtures,refresh=True)
    assert rows and all(r["checks_pass"] for r in rows)
    expected=ROOT/"fixtures"/name.replace("_","-")
    assert {p.name for p in fixtures.iterdir()}=={p.name for p in expected.iterdir()}
    for path in fixtures.iterdir():assert path.read_bytes()==(expected/path.name).read_bytes(),path.name
    for path in output.iterdir():
        if path.suffix in {".csv",".json"}:assert path.read_bytes()==(ROOT/"results"/path.name).read_bytes(),path.name
        else:assert path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_si_inertia_is_not_rounded_to_zero_in_evidence():
    from research_notes.advanced_geometry_studies import evidence_bytes
    record=json.loads(evidence_bytes({"principal_moments_kg_m2":[2.028e-10],"noise":1e-15}))
    assert record["principal_moments_kg_m2"][0]==2.028e-10
    assert record["noise"]==0.


def test_reference_writer_precision_does_not_inherit_previous_study(tmp_path):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from research_notes.brep_runtime import step_round_trip
    step_round_trip(BRepPrimAPI_MakeBox(1.,1.,1.).Shape(),"precision_contaminant",writer_uncertainty=1e-4)
    run_study("spline_geometry",tmp_path/"results",tmp_path/"fixtures",refresh=True)
    assert (tmp_path/"fixtures/polynomial.step").read_bytes()==(ROOT/"fixtures/spline-geometry/polynomial.step").read_bytes()
