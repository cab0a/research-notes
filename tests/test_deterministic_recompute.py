"""Dependency propagation, cache correctness, and failure recovery."""

from dataclasses import asdict, replace

import pytest

from research_notes.deterministic_recompute import (
    FeatureModel, ModelNode, edit_parameter, model_fingerprint, model_from_dict,
    recompute, single_feature_model, validate_model,
)
from research_notes.modeling_studies import branching_model
from research_notes.parametric_features import PlateSpec, feature_spec


def test_only_affected_branch_recomputes_and_independent_branch_survives_failure():
    model = branching_model()
    initial = recompute(model)
    edited = edit_parameter(model, "feature", "radius", 1.5)
    successful = recompute(edited, initial)
    assert successful.evaluated_nodes == ("feature", "boss", "result")
    assert successful.reused_nodes == ("base", "spare_rib", "spare_result")
    assert successful.state("spare_result").shape.IsSame(initial.state("spare_result").shape)
    invalid = edit_parameter(edited, "feature", "radius", 30.)
    failed = recompute(invalid, successful)
    assert failed.state("feature").status == "failed"
    assert failed.state("boss").status == failed.state("result").status == "stale"
    assert failed.state("spare_result").status == "valid"
    assert failed.state("result").shape.IsSame(successful.current_output().shape)
    assert failed.state("result").last_valid_revision == edited.revision
    with pytest.raises(ValueError, match="not current"):
        failed.current_output()
    recovered = recompute(edit_parameter(invalid, "feature", "radius", 1.5), failed)
    assert recovered.evaluated_nodes == ()
    assert len(recovered.reused_nodes) == 6
    assert recovered.current_output().shape.IsSame(successful.current_output().shape)


def test_upstream_edit_recomputes_all_descendants_and_cold_result_agrees():
    model = branching_model()
    old = recompute(model)
    edited = edit_parameter(model, "base", "width", 14.)
    cached, cold = recompute(edited, old), recompute(edited)
    assert len(cached.evaluated_nodes) == 6
    assert not cached.reused_nodes
    assert cached.current_output().metrics == cold.current_output().metrics
    assert old.current_output().metrics.absolute_volume != cached.current_output().metrics.absolute_volume


def test_input_node_order_does_not_change_schedule_fingerprint_or_output():
    model = branching_model()
    reordered = replace(model, nodes=tuple(reversed(model.nodes)))
    assert validate_model(reordered) == validate_model(model)
    assert model_fingerprint(reordered) == model_fingerprint(model)
    assert recompute(reordered).current_output().metrics == recompute(model).current_output().metrics
    assert model_from_dict(asdict(model)) == model


@pytest.mark.parametrize("model", [
    FeatureModel("cycle", (ModelNode("a", "result", ("b",)), ModelNode("b", "result", ("a",))), "a"),
    FeatureModel("missing", (ModelNode("a", "result", ("missing",)),), "a"),
    replace(branching_model(), nodes=branching_model().nodes * 2),
    replace(branching_model(), output_id="missing"),
    replace(branching_model(), nodes=(ModelNode("bad", "unknown", (), ()),)),
])
def test_structural_defects_are_rejected(model):
    with pytest.raises(ValueError):
        recompute(model)


def test_first_failed_build_has_no_fabricated_last_valid_result():
    model = single_feature_model("invalid", PlateSpec(), feature_spec("through_hole", x=4., y=5., radius=30.))
    result = recompute(model)
    assert result.state("feature").shape is None
    assert result.state("result").shape is None
    assert result.state("result").last_valid_revision is None


def test_unconfirmed_models_cannot_be_edited_or_cross_model_caches_reused():
    model = replace(branching_model(), provenance="unconfirmed_candidate", source_sha256="a" * 64)
    with pytest.raises(ValueError, match="confirm"):
        edit_parameter(model, "feature", "radius", 2.)
    with pytest.raises(ValueError, match="different model"):
        recompute(replace(model, model_id="other"), recompute(model))
