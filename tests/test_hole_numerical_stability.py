"""Translation robustness with authored truth and conservative exceptions."""
import hashlib
import math
from pathlib import Path

import pytest

from research_notes.brep_runtime import maximum_tolerances, step_round_trip, topology_counts
from research_notes.hole_inventory import analyze_step
from research_notes.hole_robustness import local_inventory, match_truth
from research_notes.hole_robustness_controls import (
    box, compound, geometry_controls, mixed_control, transformed, with_tolerance,
)
from research_notes.local_material import LocalMaterialClassifier


@pytest.fixture(scope='module')
def base():
    return mixed_control()


@pytest.fixture(scope='module')
def unsupported():
    return {c.identifier: c for c in geometry_controls()
            if c.category in {'unsupported', 'boundary_withheld'}}


TRANSFORMS = [
    (offset, scale, angle)
    for offset in (1e6, 1e7, 1e8)
    for scale, angle in ((1., 0.), (1., .73), (.01, 0.), (.1, .73))
]


@pytest.mark.parametrize('offset,scale,angle', TRANSFORMS)
@pytest.mark.parametrize('stage', ['constructed', 'step_scanners', 'unified'])
def test_translation_regression_and_retained_step_exchange_limits(base, offset, scale, angle, stage):
    control = transformed(base, 'far', scale=scale, angle=angle,
                          translation=(offset, -offset, offset))
    if stage == 'constructed':
        result = local_inventory(control.shape)
    else:
        fixture = step_round_trip(control.shape, 'far')
        result = (local_inventory(fixture.imported_shape) if stage == 'step_scanners'
                  else analyze_step(fixture.source_bytes, 'far.step', inspection=True, preview=False))
        if stage == 'unified':
            assert result['status'] == ('partial' if result['holes'] else 'unresolved')
            assert result['hole_count'] is None
            assert result['source_sha256'] == hashlib.sha256(fixture.source_bytes).hexdigest()
    audit = match_truth(result['holes'], control.expected)
    assert not audit['false_positives'] and not audit['measurement_errors'], audit
    # STEP's finite coordinate text and import can alter spans/tolerances.
    # Keep the two authored holes as truth, including the retained misses.
    exchange_limit = stage != 'constructed' and (angle != 0 or (scale == .01 and offset > 1e6))
    assert audit['matched_features'] == (0 if exchange_limit else 2), audit
    assert len(audit['missed_truth_indices']) == (2 if exchange_limit else 0), audit


@pytest.mark.parametrize('identifier', [
    'circle_blind', 'circle_counterbore', 'circle_rectangular_shoulder', 'circle_countersink',
    'circle_edge_notch', 'circle_intersection', 'circle_boss', 'circle_internal_void',
    'circle_tapered', 'circle_split_face', 'circle_spline', 'ellipse', 'rectangle',
    'slanted_ellipse', 'washer', 'slot_blind', 'slot_counterbore',
    'slot_rectangular_shoulder', 'slot_boss', 'slot_open_notch', 'slot_interrupted',
    'slot_curved', 'slot_spline', 'slot_unequal_ends', 'slot_skew_passage',
    'radius_at_gate', 'radius_below_gate', 'depth_below_gate',
])
@pytest.mark.parametrize('stage', ['constructed', 'unified'])
def test_unsupported_and_boundary_shapes_stay_withheld_after_far_translation(unsupported, identifier, stage):
    control = transformed(unsupported[identifier], 'far_'+identifier, translation=(1e6, -1e6, 1e6))
    result = (local_inventory(control.shape) if stage == 'constructed' else
              analyze_step(step_round_trip(control.shape, 'far_'+identifier).source_bytes,
                           inspection=True, preview=False))
    assert result['holes'] == []
    if stage == 'unified':
        assert result['hole_count'] is None


@pytest.mark.parametrize('kind', ['face', 'edge', 'vertex'])
@pytest.mark.parametrize('value', [9e-6, 1e-5, 1.1e-5])
def test_local_translation_does_not_reset_original_tolerance_gates(base, kind, value):
    far = transformed(base, 'far', translation=(1e6, -1e6, 1e6)).shape
    shape = with_tolerance(far, kind, value)
    before = maximum_tolerances(shape)
    result = local_inventory(shape)
    assert len(result['holes']) == (2 if value <= 1e-5 else 0)
    assert maximum_tolerances(shape) == before


def test_separated_solids_use_independent_frames_and_keep_original_face_ids(base):
    left = transformed(base, 'left', translation=(-1e6, 1e6, -1e6))
    right = transformed(base, 'right', translation=(1e6, -1e6, 1e6))
    shape = compound(left.shape, right.shape)
    before = topology_counts(shape), maximum_tolerances(shape)
    result = local_inventory(shape)
    audit = match_truth(result['holes'], left.expected + right.expected)
    # The two scanners use independent H/S namespaces, still file-local.
    assert audit['matched_features'] == 4 and not audit['missed_truth_indices'], audit
    assert not audit['false_positives'] and not audit['measurement_errors'], audit
    assert {h['solid_index'] for h in result['holes']} == {1, 2}
    assert (topology_counts(shape), maximum_tolerances(shape)) == before
    # Moving the private classifier must not change the original face evidence.
    reference = local_inventory(base.shape)['holes']
    for measured, original in zip([r for r in result['holes'] if r['solid_index'] == 1], reference):
        key = 'faces' if measured['feature_type'] == 'circular_hole' else 'wall_faces'
        assert measured[key] == original[key]


def test_classifier_material_void_and_boundary_are_distinct_and_world_coordinates_survive():
    from OCP.BRep import BRep_Tool
    from OCP.TopAbs import TopAbs_IN, TopAbs_OUT, TopAbs_ON, TopAbs_VERTEX
    from OCP.TopoDS import TopoDS
    from research_notes.brep_runtime import iter_shapes

    shape = box(1e6, -1e6, 1e6, 4, 6, 8)
    vertices = tuple(iter_shapes(shape, TopAbs_VERTEX))
    before = [BRep_Tool.Pnt_s(TopoDS.Vertex_s(v)).Coord() for v in vertices]
    classifier = LocalMaterialClassifier(shape, 1e-5)
    assert classifier.state([1e6+2, -1e6+3, 1e6+4]) == TopAbs_IN
    assert classifier.state([1e6-1, -1e6+3, 1e6+4]) == TopAbs_OUT
    assert classifier.state([1e6, -1e6+3, 1e6+4]) == TopAbs_ON
    assert [BRep_Tool.Pnt_s(TopoDS.Vertex_s(v)).Coord() for v in vertices] == before


def test_unrepresentable_coordinate_precision_and_nonfinite_samples_are_not_accepted():
    classifier = LocalMaterialClassifier(box(1e10, 0, 0, 4, 6, 8), 1e-5)
    with pytest.raises(ValueError, match='resolution is too coarse'):
        classifier.state([1e10+2, 3, 4])
    ordinary = LocalMaterialClassifier(box(0, 0, 0, 4, 6, 8), 1e-5)
    with pytest.raises(ValueError, match='finite XYZ'):
        ordinary.state([math.inf, 3, 4])


def test_existing_frozen_far_coordinate_regression_now_recognizes_both_features():
    path = Path(__file__).resolve().parents[1] / 'fixtures/hole-robustness/sources/translated_1e6.step'
    result = analyze_step(path.read_bytes(), path.name, inspection=True, preview=False)
    assert result['status'] == 'partial' and result['hole_count'] is None
    assert result['recognized_circular_hole_count'] == result['recognized_slot_count'] == 1
    assert result['conditions']['local_qualification_tolerance_mm'] == 1e-5
