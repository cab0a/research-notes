from copy import deepcopy
from dataclasses import asdict
import pytest
from research_notes.representation_learning import fit_representation,predict_representation
from research_notes.change_pair_dataset import leakage_audit


def samples():
    return [{"sample_id":str(i),"lineage_id":str(i),"split":split,"truth":label,"values":[x]} for i,(split,label,x) in enumerate([
        ("train","a",0.),("train","b",4.),("validation","a",.1),("validation","b",3.9),("test","a",.2)])]


def test_test_data_cannot_fit_or_calibrate():
    data=samples();a=fit_representation(data,("x",));changed=deepcopy(data);changed[-1]["values"]=[100000.];changed[-1]["truth"]="b"
    assert asdict(a)==asdict(fit_representation(changed,("x",)))
    assert predict_representation(a,[100000.])["decision"]=="abstain"
    p=predict_representation(a,[.1]);assert p["prediction"]=="a"
    margin=p["ranking"][1]["squared_distance"]-p["ranking"][0]["squared_distance"]
    assert sum(r["winner_vs_runner_distance_margin"] for r in p["influence"])==pytest.approx(margin)


def test_cross_split_lineage_is_rejected():
    data=samples();data[-1]["lineage_id"]=data[0]["lineage_id"]
    with pytest.raises(ValueError,match="leakage"):fit_representation(data,("x",))


def test_pair_derivation_and_identity_leakage():
    data=[{"family":"a","lineage_id":"x","split":"train","before_sha256":"one","after_sha256":"two"},
          {"family":"b","lineage_id":"y","split":"test","before_sha256":"two","after_sha256":"three"}]
    assert not leakage_audit(data)["checks_pass"]
