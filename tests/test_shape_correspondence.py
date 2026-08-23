"""Tests for the v0.39 controlled face- and edge-correspondence contract."""

from __future__ import annotations

import importlib.util

import pytest

from research_notes.shape_correspondence import (
    EdgeCandidateObservation,
    EdgeDescriptor,
    _edge_relations,
    correspondence_controls,
    probe_shape_correspondence,
)


HAS_OCP = importlib.util.find_spec("OCP") is not None


@pytest.fixture(scope="module")
def probe() -> object:
    """Run the native correspondence probe once for all tests."""
    if not HAS_OCP:
        pytest.skip("install the geometry extra to run correspondence tests")
    return probe_shape_correspondence()


def test_control_catalog_preregisters_identity_merge_and_ambiguity() -> None:
    """Controls should isolate unique, normalized, merged, and ambiguous cases."""
    controls = correspondence_controls()
    assert [item.control_id for item in controls] == [
        "asymmetric_prism",
        "reversed_box",
        "split_box",
        "coincident_faces",
    ]
    assert [item.expected_constructed_faces for item in controls] == [7, 6, 10, 2]
    assert [item.expected_constructed_edges for item in controls] == [15, 12, 20, 8]
    assert controls[2].expected_healed_faces == 6
    assert controls[2].expected_healed_edges == 12
    assert controls[0].analytic_volume == 98.0


def test_step_round_trip_preserves_controlled_face_counts(probe: object) -> None:
    """All four generated fixtures should retain their controlled face counts."""
    expected = {
        "asymmetric_prism": 7,
        "reversed_box": 6,
        "split_box": 10,
        "coincident_faces": 2,
    }
    for control_id, count in expected.items():
        assert (
            sum(
                item.control_id == control_id and item.stage == "constructed"
                for item in probe.faces
            )
            == count
        )
        assert (
            sum(
                item.control_id == control_id and item.stage == "step_imported"
                for item in probe.faces
            )
            == count
        )


def test_uniquely_identifiable_imported_faces_are_matched(probe: object) -> None:
    """Twenty-three analytically distinguishable source faces should match once."""
    relations = [item for item in probe.relations if item.comparison == "step_import"]
    unique = [item for item in relations if item.relation_kind == "one_to_one"]
    assert len(unique) == 23
    assert all(item.truth_correct for item in unique)
    assert all(item.candidate_count == 1 for item in unique)


def test_indistinguishable_faces_abstain_instead_of_using_indices(
    probe: object,
) -> None:
    """Two coincident faces should retain a two-candidate ambiguity."""
    relations = [
        item
        for item in probe.relations
        if item.control_id == "coincident_faces" and item.comparison == "step_import"
    ]
    assert len(relations) == 2
    assert all(item.relation_kind == "ambiguous" for item in relations)
    assert all(item.candidate_count == 2 for item in relations)
    assert all(not item.target_face_indices for item in relations)
    assert all(item.truth_correct for item in relations)


def test_same_domain_healing_records_four_two_to_one_groups(probe: object) -> None:
    """Eight split side faces should map into four healed target faces."""
    relations = [
        item for item in probe.relations if item.comparison == "same_domain_healing"
    ]
    assert len(relations) == 10
    assert sum(item.relation_kind == "one_to_one" for item in relations) == 2
    merged = [item for item in relations if item.relation_kind == "many_to_one"]
    assert len(merged) == 8
    assert len({item.target_face_indices for item in merged}) == 4
    assert all(item.truth_correct for item in relations)
    assert all(item.history_agrees for item in relations)


def test_merged_relation_groups_conserve_controlled_area(probe: object) -> None:
    """Each selected many-to-one group should conserve its planar face area."""
    source_faces = {
        item.face_index: item
        for item in probe.faces
        if item.control_id == "split_box" and item.stage == "step_imported"
    }
    target_faces = {
        item.face_index: item
        for item in probe.faces
        if item.control_id == "split_box" and item.stage == "healed"
    }
    merged = [
        item
        for item in probe.relations
        if item.comparison == "same_domain_healing"
        and item.relation_kind == "many_to_one"
    ]
    by_target: dict[int, list[int]] = {}
    for relation in merged:
        by_target.setdefault(relation.target_face_indices[0], []).append(
            relation.source_face_index
        )
    assert sorted(len(items) for items in by_target.values()) == [2, 2, 2, 2]
    for target_index, source_indices in by_target.items():
        assert sum(
            source_faces[index].area for index in source_indices
        ) == pytest.approx(target_faces[target_index].area, abs=1.0e-9)


def test_step_edge_correspondence_resolves_unique_edges_and_abstains(
    probe: object,
) -> None:
    """Distinct edges should match once and duplicate coincident edges should abstain."""
    relations = [
        item for item in probe.edge_relations if item.comparison == "step_import"
    ]
    assert len(relations) == 55
    assert sum(item.relation_kind == "one_to_one" for item in relations) == 47
    ambiguous = [item for item in relations if item.relation_kind == "ambiguous"]
    assert len(ambiguous) == 8
    assert all(item.control_id == "coincident_faces" for item in ambiguous)
    assert all(item.candidate_count == 2 for item in ambiguous)
    assert all(not item.target_edge_indices for item in ambiguous)
    assert all(item.truth_correct for item in relations)


def test_edge_candidates_keep_geometry_and_topology_evidence_separate(
    probe: object,
) -> None:
    """Mapped incident faces should corroborate but not replace geometry gates."""
    assert len(probe.edge_candidates) == 79
    assert all(item.curve_type_matches for item in probe.edge_candidates)
    selected = [
        item
        for item in probe.edge_candidates
        if item.comparison == "step_import" and item.selected
    ]
    assert len(selected) == 47
    assert all(item.incident_face_count_matches for item in selected)
    assert all(item.topology_candidate_supports_geometry for item in probe.edge_candidates)
    ambiguous = [
        item
        for item in probe.edge_candidates
        if item.control_id == "coincident_faces"
    ]
    assert len(ambiguous) == 16
    assert all(item.topology_candidate_supports_geometry for item in ambiguous)
    assert all(
        len(item.mapped_source_incident_target_face_indices) == 2
        for item in ambiguous
    )
    assert max(item.length_relative_error for item in selected) < 1.0e-12
    assert max(item.endpoint_pair_max_distance for item in selected) < 1.0e-9
    assert max(item.support_error for item in selected) < 1.0e-9


def test_same_domain_healing_records_modified_merged_and_deleted_edges(
    probe: object,
) -> None:
    """The split box should expose every empirically observed edge relation class."""
    relations = [
        item
        for item in probe.edge_relations
        if item.comparison == "same_domain_healing"
    ]
    assert len(relations) == 20
    assert sum(item.relation_kind == "one_to_one_modified" for item in relations) == 8
    merged = [item for item in relations if item.relation_kind == "many_to_one"]
    deleted = [item for item in relations if item.relation_kind == "deleted"]
    assert len(merged) == 8
    assert len({item.target_edge_indices for item in merged}) == 4
    assert len(deleted) == 4
    assert all(item.inferred_relation_kind == "unmatched" for item in deleted)
    assert all(item.history_removed for item in deleted)
    assert all(not item.target_edge_indices for item in deleted)
    assert all(not item.history_generated_target_indices for item in relations)
    assert sum(item.history_modified_item_count or 0 for item in relations) == 16
    assert sum(item.history_generated_item_count or 0 for item in relations) == 0
    assert sum(bool(item.history_removed) for item in relations) == 4
    assert sum(item.history_unresolved_item_count or 0 for item in relations) == 0
    assert all(item.truth_correct for item in relations)
    assert all(item.history_agrees for item in relations)


def test_correspondence_does_not_imply_direct_topology_identity(probe: object) -> None:
    """No inferred STEP or healing relation should reuse a native edge identity."""
    assert len(probe.edge_relations) == 75
    assert all(item.direct_identity_checked for item in probe.edge_relations)
    assert all(not item.direct_is_same for item in probe.edge_relations)
    assert all(not item.direct_is_partner for item in probe.edge_relations)
    assert all(not item.direct_same_target_indices for item in probe.edge_relations)
    assert all(not item.direct_partner_target_indices for item in probe.edge_relations)


def test_single_candidate_with_target_conflict_is_ambiguous() -> None:
    """A target claimed by two sources should not leave either source unmatched."""
    sources = tuple(
        EdgeDescriptor(
            stage="constructed",
            control_id="target_conflict",
            edge_index=index,
            truth_role=f"source_{index}",
            curve_type="line",
            length=1.0,
            first_point=(0.0, 0.0, 0.0),
            last_point=(1.0, 0.0, 0.0),
            support_direction=(1.0, 0.0, 0.0),
            support_anchor=(0.0, 0.0, 0.0),
            incident_face_count=1,
            incident_face_indices=(1,),
        )
        for index in (1, 2)
    )
    candidates = tuple(
        EdgeCandidateObservation(
            comparison="step_import",
            control_id="target_conflict",
            source_stage="constructed",
            target_stage="step_imported",
            source_edge_index=index,
            target_edge_index=1,
            source_truth_role=f"source_{index}",
            target_truth_role="shared_target",
            curve_type_matches=True,
            support_error=0.0,
            length_relative_error=0.0,
            endpoint_pair_max_distance=0.0,
            source_endpoints_on_target=True,
            source_incident_face_count=1,
            target_incident_face_count=1,
            incident_face_count_matches=True,
            source_incident_face_indices=(1,),
            mapped_source_incident_target_face_indices=(1,),
            target_incident_face_indices=(1,),
            mapped_target_incident_source_face_indices=(1,),
            topology_candidate_supports_geometry=True,
            selected=False,
        )
        for index in (1, 2)
    )
    relations = _edge_relations("step_import", "target_conflict", sources, candidates)
    assert [item.relation_kind for item in relations] == ["ambiguous", "ambiguous"]


def test_merged_edge_groups_conserve_controlled_length(probe: object) -> None:
    """Each pair of collinear source segments should cover one healed edge."""
    source_edges = {
        item.edge_index: item
        for item in probe.edges
        if item.control_id == "split_box" and item.stage == "step_imported"
    }
    target_edges = {
        item.edge_index: item
        for item in probe.edges
        if item.control_id == "split_box" and item.stage == "healed"
    }
    merged = [
        item
        for item in probe.edge_relations
        if item.comparison == "same_domain_healing"
        and item.relation_kind == "many_to_one"
    ]
    by_target: dict[int, list[int]] = {}
    for relation in merged:
        by_target.setdefault(relation.target_edge_indices[0], []).append(
            relation.source_edge_index
        )
    assert sorted(len(items) for items in by_target.values()) == [2, 2, 2, 2]
    for target_index, source_indices in by_target.items():
        assert sum(
            source_edges[index].length for index in source_indices
        ) == pytest.approx(target_edges[target_index].length, abs=1.0e-9)


def test_normalized_fixture_hashes_are_unique(probe: object) -> None:
    """Every committed correspondence fixture should have stable distinct bytes."""
    assert len(probe.fixtures) == 4
    assert len({item.source_sha256 for item in probe.fixtures}) == 4
    assert all(len(item.source_sha256) == 64 for item in probe.fixtures)
