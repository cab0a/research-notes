from copy import deepcopy
import json

import pytest

from research_notes.cad_platform import aggregate_platforms, numeric_differences, PLATFORM_LABELS
from research_notes.engineering_analysis import ordered_witnesses


def test_tied_witness_order_is_independent_of_native_enumeration():
    witnesses = [{"a_support": {"kind": "vertex", "analysis_local_index": i},
        "b_support": {"kind": "edge", "analysis_local_index": i + 2},
        "a_point": [2., float(i), 0.], "b_point": [2.00000005, float(i), 0.]} for i in (7, 5, 8, 6)]
    assert ordered_witnesses(witnesses) == ordered_witnesses(list(reversed(witnesses)))
    assert sorted(json.dumps(w, sort_keys=True) for w in ordered_witnesses(witnesses)) == sorted(json.dumps(w, sort_keys=True) for w in witnesses)


def reports(tmp_path):
    paths = []
    for label in PLATFORM_LABELS:
        path = tmp_path / (label + ".json")
        system = "Windows" if label.startswith("windows") else "Darwin" if label.startswith("macos") else "Linux"
        report = {"environment": {"label": label, "system": system, "machine": "arm64" if label.endswith("arm64") else "x86_64",
                  "source_commit": "test-only", "runtime_sha256": "test-only"}, "checks_pass": True,
                  "observations": {"volume": 24.0, "count": 6, "status": "valid"}, "scope": "test fixture", "numeric_policy": {}}
        path.write_text(json.dumps(report), encoding="utf-8")
        paths.append(path)
    return paths


def test_platform_aggregation_requires_all_real_named_environments(tmp_path):
    paths = reports(tmp_path)
    assert aggregate_platforms(paths)["checks_pass"]
    with pytest.raises(ValueError, match="missing"):
        aggregate_platforms(paths[:-1])
    with pytest.raises(ValueError, match="duplicate"):
        aggregate_platforms(paths + paths[:1])
    windows = json.loads(paths[1].read_text())
    windows["environment"]["system"] = "Linux"
    paths[1].write_text(json.dumps(windows))
    assert not aggregate_platforms(paths)["checks_pass"]


def test_platform_aggregation_rejects_code_drift(tmp_path):
    paths = reports(tmp_path)
    report = json.loads(paths[1].read_text())
    report["environment"]["runtime_sha256"] = "different"
    paths[1].write_text(json.dumps(report))
    assert not aggregate_platforms(paths)["checks_pass"]


def test_numeric_policy_does_not_erase_classification_or_topology_drift():
    baseline = {"volume": 24., "count": 6, "status": "valid"}
    assert not numeric_differences({**baseline, "volume": 24.000001}, baseline)
    for changed in ({"count": 7}, {"status": "invalid"}, {"volume": 24.001}, {"volume": float("nan")}):
        assert numeric_differences({**baseline, **changed}, baseline)
