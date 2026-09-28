"""Regression artifacts plus independent semantic and solver failure controls."""
from collections import Counter
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path

import numpy as np
import pytest

from research_notes.ap242_paths import resolve_ap242_product_paths
from research_notes.portable_step import inspect_step_file, inspect_step_semantics
from research_notes.robustness_studies import ROOT, STUDIES, run_study, evidence_bytes


def sample(directory, name):
    return (ROOT / "fixtures" / directory / (name + ".step")).read_bytes()


def assert_numeric_evidence(actual, expected):
    if isinstance(expected, dict):
        assert actual.keys() == expected.keys()
        for key in expected:
            assert_numeric_evidence(actual[key], expected[key])
    elif isinstance(expected, list):
        assert len(actual) == len(expected)
        for a, b in zip(actual, expected):
            assert_numeric_evidence(a, b)
    elif isinstance(expected, float):
        assert actual == pytest.approx(expected, rel=1e-5, abs=1e-10)
    else:
        assert actual == expected


@pytest.mark.parametrize("name", STUDIES)
def test_robustness_artifacts_reproduce(tmp_path, name):
    output, fixtures = tmp_path / "results", tmp_path / "fixtures"
    rows = run_study(name, output, fixtures, refresh=True)
    assert all(r["checks_pass"] for r in rows)
    reference = ROOT / "fixtures" / name.replace("_", "-")
    assert {p.name for p in fixtures.iterdir()} == {p.name for p in reference.iterdir()}
    for path in fixtures.iterdir():
        assert path.read_bytes() == (reference / path.name).read_bytes()
    for path in output.iterdir():
        if path.suffix == ".png":
            assert path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        elif name == "solver_robustness" and path.name.endswith("_evidence.json"):
            # Finite-difference residuals depend on the BLAS/platform arithmetic.
            assert_numeric_evidence(json.loads(path.read_text()), json.loads((ROOT / "results" / path.name).read_text()))
        else:
            assert path.read_bytes() == (ROOT / "results" / path.name).read_bytes()


@pytest.mark.parametrize("schema", ["CONFIG_CONTROL_DESIGN", "AUTOMOTIVE_DESIGN", "AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF"])
def test_portability_retains_raw_sources_and_explicit_roles(schema):
    raw = sample("ap242-product-paths", "ap242_block_path").replace(b"AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF", schema.encode())
    result = inspect_step_semantics(raw)
    assert result["source_sha256"] == hashlib.sha256(raw).hexdigest()
    product = result["products"][0]
    assert product["name"] == "Controlled block"
    assert product["selected_representation_id"] == 20
    span = product["source_span"]
    assert raw[span["start_byte"]:span["end_byte"]].startswith(b"#6=PRODUCT_DEFINITION(")
    assert result["representations"][0]["mm_per_source_unit"] == 1.
    assert result["schema_conformance"] == "not_evaluated"
    if schema != "AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF":
        assert resolve_ap242_product_paths(raw).decision == "quarantine"


def test_profile_name_prefix_is_not_schema_authorization():
    raw = sample("ap-portability", "unknown_schema")
    result = inspect_step_semantics(raw)
    assert result["status"] == "unsupported"
    assert not result["products"] and not result["representations"]


def test_ambiguous_shapes_require_known_explicit_selection():
    raw = sample("complex-product-structures", "alternative")
    before = hashlib.sha256(raw).hexdigest()
    result = inspect_step_semantics(raw)
    assert result["products"][0]["candidate_ids"] == [20, 21]
    assert result["products"][0]["selected_representation_id"] is None
    assert inspect_step_semantics(raw, selections={6: 21})["products"][0]["selected_representation_id"] == 21
    assert hashlib.sha256(raw).hexdigest() == before
    for choices in ({6: 999}, {999: 20}, {True: 21}, {6: "21"}):
        with pytest.raises(ValueError):
            inspect_step_semantics(raw, selections=choices)


def test_unqualified_alternative_cannot_be_hidden_by_selection():
    raw = sample("complex-product-structures", "unqualified_alternative")
    assert inspect_step_semantics(raw)["products"][0]["selection"] == "unresolved"
    with pytest.raises(ValueError, match="outside qualified"):
        inspect_step_semantics(raw, selections={6: 20})


def test_relationship_cycle_is_bounded_and_exposes_all_alternatives():
    raw = sample("complex-product-structures", "cyclic_relationships")
    assert inspect_step_semantics(raw)["products"][0]["candidate_ids"] == [20, 21, 22]
    with pytest.raises(ValueError, match="candidate_limit"):
        inspect_step_semantics(raw, max_candidates=2)
    with pytest.raises(ValueError, match="relationship_limit"):
        inspect_step_semantics(raw, max_links=1)


@pytest.mark.parametrize("old,new,diagnostic", [
    (b"#4,#5", b"#3,#5", "unexpected_target_type"),
    (b"SI_UNIT(.MILLI.,.METRE.)", b"SI_UNIT(.MILLI.,.SECOND.)", "unsupported_si_length_unit"),
    (b"GEOMETRIC_REPRESENTATION_CONTEXT(3)", b"GEOMETRIC_REPRESENTATION_CONTEXT(2)", "only_3d_context_supported"),
])
def test_bad_product_or_unit_roles_never_select_geometry(old, new, diagnostic):
    raw = sample("ap242-product-paths", "ap242_block_path").replace(old, new)
    result = inspect_step_semantics(raw)
    assert result["status"] == "partial"
    assert diagnostic in [d["code"] for d in result["diagnostics"]]
    assert not any(p["selected_representation_id"] for p in result["products"])


def test_duplicate_shape_definition_is_reported():
    raw = sample("ap242-product-paths", "ap242_block_path")
    raw = raw.replace(b"ENDSEC;\nEND-ISO", b"#50=PRODUCT_DEFINITION_SHAPE('','',#6);\n#51=SHAPE_DEFINITION_REPRESENTATION(#50,#20);\nENDSEC;\nEND-ISO")
    result = inspect_step_semantics(raw)
    assert "duplicate_product_definition_shape" in [d["code"] for d in result["diagnostics"]]
    assert not result["products"]


def test_reused_definition_has_distinct_occurrence_paths():
    result = inspect_step_semantics(sample("ap242-assemblies", "nested_reuse"))
    assembly = result["assembly"]
    assert assembly["decision"] == "accept"
    paths = assembly["paths"]
    bolts = [p for p in paths if p["leaf_product_definition_entity_id"] == 402]
    assert len(bolts) == 3
    assert len({p["occurrence_entity_ids"] for p in bolts}) == 3
    assert {p["global_translation_mm"] for p in bolts} == {(10., 0., 0.), (20., 0., 0.), (100., 10., 0.)}


def test_file_acquisition_has_a_byte_limit(tmp_path):
    path = tmp_path / "large.step"
    path.write_bytes(b" " * 2_000_001)
    with pytest.raises(ValueError, match="byte budget"):
        inspect_step_file(path)


def test_reference_scorer_detects_wrong_assertions_and_keeps_abstentions():
    from research_notes.reference_benchmark import score_relations
    from research_notes.topological_references import ReferenceRelation
    good = ReferenceRelation("a", "b", "c", "face", 1, (2,), "one_to_one", "test")
    assert score_relations((good,), {("face", 1): (2,)})["incorrect"] == 0
    assert score_relations((replace(good, target_indices=(3,)),), {("face", 1): (2,)})["incorrect"] == 1
    abstain = replace(good, target_indices=(), relation="unresolved")
    result = score_relations((abstain,), {("face", 1): (2,)})
    assert result["abstained"] == 1 and result["incorrect"] == 0 and result["coverage"] == 0.


def test_symmetric_rotation_is_a_frozen_false_match_control():
    import csv
    rows = list(csv.DictReader((ROOT / "results/reference_robustness.csv").open()))
    row = next(r for r in rows if r["control_id"] == "rotation_90_geometry")
    assert (int(row["asserted"]), int(row["incorrect"])) == (18, 16)


def test_two_distance_solutions_are_locally_fixed_but_globally_nonunique():
    from research_notes.solver_benchmark import sketch_cases
    from research_notes.sketch_constraints import solve_sketch
    candidates = [c for c in sketch_cases() if c[0] in {"two_distances_s1_h1_seed-1", "two_distances_s1_h1_seed1"}]
    results = [solve_sketch(c[2]) for c in candidates]
    assert all(r.satisfied and r.local_degrees_of_freedom == 0 for r in results)
    assert results[0].entities[-1].parameters[1] == pytest.approx(-1., abs=1e-8)
    assert results[1].entities[-1].parameters[1] == pytest.approx(1., abs=1e-8)


def test_near_singular_residual_success_is_not_coordinate_correctness():
    from research_notes.solver_benchmark import sketch_cases
    from research_notes.sketch_constraints import solve_sketch
    case = next(c for c in sketch_cases() if c[0] == "two_distances_s1_h0_seed1")
    result = solve_sketch(case[2])
    assert result.satisfied and result.max_residual <= 1e-9
    assert abs(result.entities[-1].parameters[1]) > 1e-6  # Analytic tangent solution has y = 0.


def test_zero_iteration_budget_does_not_prove_nonlinear_inconsistency():
    from research_notes.solver_benchmark import sketch_cases
    from research_notes.sketch_constraints import solve_sketch
    case = next(c for c in sketch_cases() if c[0] == "two_distances_s1_h1_seed1")
    result = solve_sketch(case[2], max_iterations=0)
    assert result.status == "not_converged" and not result.satisfied


def test_small_numerical_evidence_is_never_rounded_to_zero():
    assert json.loads(evidence_bytes({"singular_value": 2e-14}))["singular_value"] == 2e-14


def test_terminal_semantics_and_benchmark_are_usable(tmp_path):
    from research_notes.integrated_tool import IntegratedShell
    stream = io.StringIO()
    shell = IntegratedShell(tmp_path, stdout=stream)
    path = ROOT / "fixtures/complex-product-structures/alternative.step"
    shell.onecmd(f'semantics "{path}" 6=21')
    assert shell.errors == 0
    assert json.loads((tmp_path / "semantics.json").read_text())["products"][0]["selection"] == "explicit"
    shell.onecmd("benchmark solver")
    assert shell.errors == 0 and (tmp_path / "benchmarks/solver_robustness.html").is_file()
    assert shell.session.inspection is None  # Reading semantics never silently adopts editable geometry.
    shell.onecmd(f'semantics "{path}" 6=20 6=21')
    assert shell.errors == 1
