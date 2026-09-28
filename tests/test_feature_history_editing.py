import math
from dataclasses import replace
import pytest

from research_notes.deterministic_recompute import recompute
from research_notes.feature_history_editing import (
    Configuration, FeatureHistory, HistoryFeature, apply_configuration, compile_history,
    reorder_features, rollback_history, suppress_feature,
)
from research_notes.parametric_features import PlateSpec, feature_spec


def example_history():
    return FeatureHistory("history", PlateSpec(), (
        HistoryFeature("hole", feature_spec("through_hole", x=3., y=3., radius=1.)),
        HistoryFeature("boss", feature_spec("boss", x=9., y=7., radius=1., height=2.)),
    ))


def test_suppression_reactivation_order_rollback_and_configuration():
    history = example_history()
    result = recompute(compile_history(history))
    assert result.current_output().metrics.absolute_volume == pytest.approx(480.-2*math.pi, abs=1e-7)
    suppressed = suppress_feature(history, "hole")
    after = recompute(compile_history(suppressed), result)
    assert after.current_output().metrics.absolute_volume == pytest.approx(480.+2*math.pi, abs=1e-7)
    restored = suppress_feature(suppressed, "hole", suppressed=False)
    assert recompute(compile_history(restored), after).current_output().metrics.absolute_volume == pytest.approx(480.-2*math.pi, abs=1e-7)
    reordered = reorder_features(history, ("boss", "hole"))
    assert recompute(compile_history(reordered)).current_output().metrics.absolute_volume == pytest.approx(480.-2*math.pi, abs=1e-7)
    assert compile_history(history).nodes[1].node_id == "hole"
    rollback = rollback_history(history, "hole")
    assert recompute(compile_history(rollback)).current_output().metrics.absolute_volume == pytest.approx(480.-4*math.pi, abs=1e-7)
    changed = apply_configuration(history, Configuration("wide", (("hole", "radius", 1.5),)))
    assert recompute(compile_history(changed)).current_output().metrics.absolute_volume == pytest.approx(480.-7*math.pi, abs=1e-7)
    assert recompute(compile_history(rollback_history(history, "base"))).current_output().metrics.absolute_volume == pytest.approx(480.)


@pytest.mark.parametrize("operation", [
    lambda h: suppress_feature(h, "unknown"),
    lambda h: reorder_features(h, ("hole", "hole")),
    lambda h: rollback_history(h, "unknown"),
    lambda h: apply_configuration(h, Configuration("bad", (("hole", "radius", -1.),))),
    lambda h: apply_configuration(h, Configuration("bad", suppressed=("unknown",))),
])
def test_invalid_history_edits_do_not_change_original(operation):
    history = example_history()
    with pytest.raises(ValueError):
        operation(history)
    assert compile_history(history).nodes[1].node_id == "hole"
