"""Independent parameter, geometry, profile, and invalid-input checks."""

import math
from dataclasses import replace

import pytest

from research_notes.brep_runtime import step_round_trip, topology_counts
from research_notes.modeling_common import measure_shape
from research_notes.parametric_features import (
    PlateSpec, analytic_feature_truth, apply_feature, build_plate,
    feature_controls, feature_spec, shape_difference_volume,
)


@pytest.mark.parametrize("name,plate,feature", feature_controls(), ids=[c[0] for c in feature_controls()])
def test_isolated_features_match_analytic_truth_and_round_trip(name, plate, feature):
    result = apply_feature(build_plate(plate).shape, plate, feature)
    volume, area = analytic_feature_truth(plate, feature)
    assert result.metrics.absolute_volume == pytest.approx(volume, abs=1e-8)
    assert result.metrics.surface_area == pytest.approx(area, abs=1e-8)
    assert result.sketch.satisfied and result.sketch.local_degrees_of_freedom == 0
    imported = step_round_trip(result.shape, name).imported_shape
    assert measure_shape(imported).absolute_volume == pytest.approx(volume, abs=1e-8)
    assert measure_shape(imported).surface_area == pytest.approx(area, abs=1e-8)
    assert topology_counts(imported) == topology_counts(result.shape)


def test_changed_plate_dimensions_drive_the_solved_profile_and_extrusion():
    plate = PlateSpec(width=18., length=7., thickness=3., origin_x=100., origin_y=-25., origin_z=7.)
    result = build_plate(plate)
    assert result.sketch.entities[1].parameters[2:] == pytest.approx((18., 7.))
    assert result.metrics.absolute_volume == pytest.approx(378.)
    assert result.metrics.surface_area == pytest.approx(402.)
    assert result.metrics.bounds_min == pytest.approx((100., -25., 7.), abs=2e-7)
    assert result.metrics.bounds_max == pytest.approx((118., -18., 10.), abs=2e-7)


def test_equivalent_hole_routes_do_not_imply_recovered_history():
    plate = PlateSpec()
    base = build_plate(plate).shape
    subtractive = apply_feature(base, plate, feature_spec("through_hole", x=4., y=5., radius=1.)).shape
    profiled = apply_feature(base, plate, feature_spec("profile_hole", x=4., y=5., radius=1.)).shape
    assert shape_difference_volume(subtractive, profiled) < 1e-8
    assert measure_shape(profiled).absolute_volume == pytest.approx(480. - 4 * math.pi)
    assert measure_shape(base).absolute_volume == pytest.approx(480.)
    with pytest.raises(ValueError, match="unmodified plate"):
        apply_feature(subtractive, plate, feature_spec("profile_hole", x=4., y=5., radius=2.))


@pytest.mark.parametrize("feature", [
    feature_spec("through_hole", x=1., y=5., radius=1.),
    feature_spec("through_hole", x=4., y=5., radius=0.),
    feature_spec("blind_hole", x=4., y=5., radius=1., depth=4.),
    feature_spec("pocket", x=3., y=3., width=4., length=3., depth=math.inf),
    feature_spec("boss", x=4., y=5., radius=1., height=-1.),
    feature_spec("rib", x=10., y=3., width=3., length=3., height=1.),
    feature_spec("through_hole", x=4., y=5., radius=1., extra=2.),
])
def test_feature_preconditions_reject_unsupported_dimensions(feature):
    plate = PlateSpec()
    with pytest.raises(ValueError):
        apply_feature(build_plate(plate).shape, plate, feature)


@pytest.mark.parametrize("changes", [{"width": 0.}, {"thickness": -1.}, {"length": math.nan}, {"origin_x": math.inf}])
def test_invalid_plate_fails_before_native_construction(changes):
    with pytest.raises(ValueError):
        build_plate(replace(PlateSpec(), **changes))
