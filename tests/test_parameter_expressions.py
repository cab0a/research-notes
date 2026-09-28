from dataclasses import replace
import math
import pytest

from research_notes.deterministic_recompute import recompute, single_feature_model
from research_notes.parameter_expressions import Parameter, bind_model_parameters, evaluate_parameters
from research_notes.parametric_features import PlateSpec, feature_spec


def test_dimensional_dependencies_conversion_and_source_spelling():
    parameters = (Parameter("width", "2 * inch"), Parameter("half", "width / 2", "cm"),
                  Parameter("ratio", "half / width", "one", 0., 1.),
                  Parameter("angle", "90 * deg", "rad", 0., 4.))
    values = {v.name: v for v in evaluate_parameters(parameters)}
    assert values["width"].base_value == pytest.approx(50.8)
    assert values["width"].expression == "2 * inch"
    assert values["half"].value_in_declared_unit == pytest.approx(2.54)
    assert values["half"].dependencies == ("width",)
    assert values["ratio"].base_value == .5
    assert values["angle"].base_value == pytest.approx(math.pi/2)


@pytest.mark.parametrize("expression,unit,reason", [
    ("2", "mm", "dimension"), ("2 * mm + 3 * deg", "mm", "equal dimensions"),
    ("1 * mm / 0", "mm", "division"), ("missing * mm", "mm", "unknown"),
    ("__import__('os')", "mm", "only"), ("mm.real", "mm", "only"),
    ("[1, 2]", "mm", "only"), ("2 ** 1000", "one", "only"),
    ("1e999 * mm", "mm", "finite"), ("True * mm", "mm", "real numeric"),
    ("10001 * mm", "mm", "domain"),
])
def test_invalid_expressions_are_explicit(expression, unit, reason):
    with pytest.raises(ValueError, match=reason):
        evaluate_parameters((Parameter("size", expression, unit),))


def test_cycle_duplicate_name_and_reserved_unit_reject():
    for parameters in [(Parameter("a", "b"), Parameter("b", "a")),
                       (Parameter("a", "1*mm"), Parameter("a", "2*mm")),
                       (Parameter("mm", "1*mm"),)]:
        with pytest.raises(ValueError):
            evaluate_parameters(parameters)


def test_binding_drives_actual_geometry_and_rejects_unconfirmed_or_angle():
    model = single_feature_model("plate", PlateSpec(), feature_spec("through_hole", x=4., y=5., radius=1.))
    params = (Parameter("diameter", "0.3*cm"), Parameter("radius", "diameter/2"))
    updated = bind_model_parameters(model, params, (("radius", "feature", "radius"),))
    result = recompute(updated).current_output()
    assert result.metrics.absolute_volume == pytest.approx(480.-9*math.pi, abs=1e-7)
    assert dict(model.nodes[1].parameters)["radius"] == 1.
    with pytest.raises(ValueError, match="length"):
        bind_model_parameters(model, (Parameter("angle", "1*rad", "rad"),), (("angle", "feature", "radius"),))
    with pytest.raises(ValueError, match="confirm"):
        bind_model_parameters(replace(model, provenance="unconfirmed_candidate", source_sha256="a"*64), params, ())
