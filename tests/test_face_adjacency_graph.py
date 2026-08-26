"""Tests for provenance-bound face-adjacency graphs and descriptors."""

import json
from pathlib import Path

import pytest

from research_notes.face_adjacency_graph import probe_face_adjacency_graphs


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def probe():
    return probe_face_adjacency_graphs()


def test_control_corpus_spans_simple_subtractive_stepped_and_fillet_shapes(probe):
    assert [item.control_id for item in probe.controls] == [
        "plain_block",
        "through_hole",
        "stepped_block",
        "fillet_operation",
    ]
    assert len(probe.fixtures) == 4
    assert all(len(item.source_sha256) == 64 for item in probe.fixtures)


def test_plain_block_has_regular_face_graph(probe):
    descriptor = next(item for item in probe.descriptors if item.control_id == "plain_block" and item.stage == "constructed")
    assert (descriptor.node_count, descriptor.relation_count) == (6, 12)
    assert descriptor.degree_histogram == ((4, 6),)
    assert descriptor.surface_histogram == (("plane", 6),)
    assert (descriptor.boundary_edge_count, descriptor.seam_edge_count, descriptor.nonmanifold_edge_count) == (0, 0, 0)


def test_through_hole_separates_seam_from_boundary(probe):
    descriptor = next(item for item in probe.descriptors if item.control_id == "through_hole" and item.stage == "constructed")
    assert (descriptor.node_count, descriptor.relation_count) == (7, 14)
    assert descriptor.surface_histogram == (("cylinder", 1), ("plane", 6))
    assert descriptor.degree_histogram == ((2, 1), (4, 4), (5, 2))
    assert descriptor.boundary_edge_count == 0
    assert descriptor.seam_edge_count == 1


def test_all_graph_structures_survive_controlled_step_round_trip(probe):
    assert len(probe.comparisons) == 4
    boolean_fields = (
        "node_count_matches",
        "relation_count_matches",
        "component_count_matches",
        "boundary_count_matches",
        "seam_count_matches",
        "nonmanifold_count_matches",
        "surface_histogram_matches",
        "degree_histogram_matches",
        "relation_histogram_matches",
        "structural_signature_matches",
        "topology_counts_match",
    )
    assert all(all(getattr(item, field) for field in boolean_fields) for item in probe.comparisons)
    assert max(item.volume_absolute_difference for item in probe.comparisons) < 1.0e-9
    assert max(item.surface_area_absolute_difference for item in probe.comparisons) < 1.0e-9


def test_every_node_and_relation_carries_provenance(probe):
    for item in (*probe.nodes, *probe.relations, *probe.descriptors):
        assert item.topology_provenance
        assert item.geometry_provenance
        assert item.exchange_provenance
    assert all(item.source_file is None and item.source_sha256 is None for item in probe.nodes if item.stage == "constructed")
    assert all(item.source_file and item.source_sha256 for item in probe.nodes if item.stage == "step_imported")


def test_graph_ids_are_explicitly_local_to_each_stage(probe):
    for descriptor in probe.descriptors:
        nodes = [item for item in probe.nodes if item.control_id == descriptor.control_id and item.stage == descriptor.stage]
        relations = [item for item in probe.relations if item.control_id == descriptor.control_id and item.stage == descriptor.stage]
        assert [item.node_id for item in nodes] == [f"f{index}" for index in range(1, len(nodes) + 1)]
        node_ids = {item.node_id for item in nodes}
        assert all(item.first_node_id in node_ids and item.second_node_id in node_ids for item in relations)


def test_committed_contract_assigns_provenance_to_every_csv_field():
    contract = json.loads((ROOT / "results/face_graph_contract.json").read_text(encoding="utf-8"))
    for table in ("node", "relation", "descriptor"):
        mapping = contract["field_provenance"][table]
        assert mapping
        assert all(value in {"contract", "topology", "geometry", "exchange"} for value in mapping.values())
    assert "persistent CAD identifiers" in " ".join(contract["claim_boundaries"])
