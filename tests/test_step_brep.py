"""Tests for bounded STEP Part 21 and B-Rep topology inspection."""

from __future__ import annotations

import hashlib
import re

import pytest

from research_notes import (
    STEPParseLimits,
    build_step_brep_fixtures,
    inspect_step_brep,
    parse_step_part21,
)


def fixture_map() -> dict[str, object]:
    """Return controlled fixture definitions keyed by stable names."""
    return {fixture.fixture: fixture for fixture in build_step_brep_fixtures()}


def test_controlled_fixture_expectations_are_met() -> None:
    """All six fixtures should reach their declared fail-closed outcomes."""
    fixtures = build_step_brep_fixtures()

    assert len(fixtures) == 6
    for fixture in fixtures:
        result = inspect_step_brep(fixture.step_bytes)
        assert result.decision == fixture.expected_decision
        assert result.reason_code == fixture.expected_reason_code
        assert len(result.faces) == fixture.expected_faces
        assert len(result.edges) == fixture.expected_edges
        assert len(result.shells) == fixture.expected_shells
        assert len(result.solids) == fixture.expected_solids
        assert sum(edge.is_free for edge in result.edges) == (
            fixture.expected_free_edges
        )


def test_closed_tetrahedron_resolves_topology_and_ownership() -> None:
    """Every tetrahedron face should resolve one shell, one solid, and peers."""
    fixture = fixture_map()["closed_tetrahedron"]
    result = inspect_step_brep(fixture.step_bytes)

    assert result.schema_identifiers == ("AUTOMOTIVE_DESIGN",)
    assert result.shells[0].declared_closed
    assert result.shells[0].incidence_closed
    assert result.shells[0].free_edge_count == 0
    assert result.shells[0].parent_solid_ids == (result.solids[0].entity_id,)
    for face in result.faces:
        assert face.parent_shell_ids == (result.shells[0].entity_id,)
        assert face.parent_solid_ids == (result.solids[0].entity_id,)
        assert face.boundary_edge_count == 3
        assert face.free_edge_count == 0
        assert len(face.adjacent_face_indices) == 3


def test_open_tetrahedron_exposes_three_boundary_edges() -> None:
    """Removing one face should expose an open shell through edge incidence."""
    fixture = fixture_map()["open_tetrahedron"]
    result = inspect_step_brep(fixture.step_bytes)

    assert result.shells[0].shell_type == "open_shell"
    assert not result.shells[0].declared_closed
    assert not result.shells[0].incidence_closed
    assert result.shells[0].free_edge_count == 3
    assert sum(edge.is_free for edge in result.edges) == 3
    assert result.solids == ()


def test_declared_shell_type_remains_separate_from_incidence_evidence() -> None:
    """A closed label should not hide an edge-incidence closure mismatch."""
    fixture = fixture_map()["open_tetrahedron"]
    mislabeled = fixture.step_bytes.replace(
        b"OPEN_SHELL", b"CLOSED_SHELL", 1
    )
    result = inspect_step_brep(mislabeled)

    assert result.decision == "accept"
    assert result.shells[0].declared_closed
    assert not result.shells[0].incidence_closed
    assert result.shells[0].free_edge_count == 3


def test_two_solids_keep_disjoint_shell_and_face_ownership() -> None:
    """Disconnected solids should not leak shell ownership or adjacency."""
    fixture = fixture_map()["two_closed_solids"]
    result = inspect_step_brep(fixture.step_bytes)

    assert len(result.solids) == 2
    for solid in result.solids:
        shell = next(
            shell
            for shell in result.shells
            if shell.entity_id == solid.outer_shell_id
        )
        owned_faces = [
            face for face in result.faces if solid.entity_id in face.parent_solid_ids
        ]
        assert len(owned_faces) == 4
        assert {face.entity_id for face in owned_faces} == set(
            shell.face_entity_ids
        )
        assert all(
            set(face.adjacent_face_indices).issubset(
                {owned.face_index for owned in owned_faces}
            )
            for face in owned_faces
        )


def test_surface_catalog_reports_declared_parameters() -> None:
    """Analytic and B-spline surface declarations should remain attributable."""
    fixture = fixture_map()["surface_catalog"]
    result = inspect_step_brep(fixture.step_bytes)
    surfaces = {face.surface_type: face for face in result.faces}

    assert set(surfaces) == {
        "plane",
        "cylinder",
        "cone",
        "sphere",
        "torus",
        "b_spline",
    }
    assert surfaces["plane"].axis == (0.0, 0.0, 1.0)
    assert surfaces["cylinder"].radius == pytest.approx(2.0)
    assert surfaces["cone"].radius == pytest.approx(2.0)
    assert surfaces["cone"].semi_angle == pytest.approx(0.5)
    assert surfaces["sphere"].radius == pytest.approx(3.0)
    assert surfaces["torus"].major_radius == pytest.approx(4.0)
    assert surfaces["torus"].minor_radius == pytest.approx(1.0)
    assert surfaces["b_spline"].u_degree == 1
    assert surfaces["b_spline"].v_degree == 1


def test_broken_references_quarantine_and_duplicate_ids_reject() -> None:
    """Relationship gaps and ambiguous identifiers should fail closed."""
    fixtures = fixture_map()
    unresolved = inspect_step_brep(fixtures["unresolved_reference"].step_bytes)
    duplicate = inspect_step_brep(fixtures["duplicate_entity_id"].step_bytes)

    assert unresolved.decision == "quarantine"
    assert unresolved.reason_code == "unresolved_reference"
    assert unresolved.unresolved_reference_count == 1
    assert duplicate.decision == "reject"
    assert duplicate.reason_code == "duplicate_entity_id"


def test_wrong_topology_entity_types_quarantine() -> None:
    """Resolved references should still satisfy controlled topology types."""
    fixtures = fixture_map()
    oriented_to_point = re.sub(
        rb"(ORIENTED_EDGE\('',\*,\*,)#\d+",
        rb"\g<1>#1",
        fixtures["closed_tetrahedron"].step_bytes,
        count=1,
    )
    solid_with_open_shell = fixtures["closed_tetrahedron"].step_bytes.replace(
        b"CLOSED_SHELL", b"OPEN_SHELL", 1
    )

    wrong_edge = inspect_step_brep(oriented_to_point)
    wrong_shell = inspect_step_brep(solid_with_open_shell)

    assert (wrong_edge.decision, wrong_edge.reason_code) == (
        "quarantine",
        "topology_relationship_incomplete",
    )
    assert (wrong_shell.decision, wrong_shell.reason_code) == (
        "quarantine",
        "topology_relationship_incomplete",
    )


def test_resource_limits_quarantine_before_topology_resolution() -> None:
    """Byte and entity ceilings should produce explicit quarantine reasons."""
    fixture = fixture_map()["closed_tetrahedron"]

    byte_limited = inspect_step_brep(
        fixture.step_bytes,
        limits=STEPParseLimits(max_file_bytes=32),
    )
    entity_limited = inspect_step_brep(
        fixture.step_bytes,
        limits=STEPParseLimits(max_entities=1),
    )

    assert (byte_limited.decision, byte_limited.reason_code) == (
        "quarantine",
        "file_size_limit",
    )
    assert (entity_limited.decision, entity_limited.reason_code) == (
        "quarantine",
        "entity_count_limit",
    )


def test_fixture_generation_and_parsing_are_deterministic() -> None:
    """Repeated construction should preserve exact bytes, hashes, and counts."""
    first = build_step_brep_fixtures()
    second = build_step_brep_fixtures()

    assert [fixture.step_bytes for fixture in first] == [
        fixture.step_bytes for fixture in second
    ]
    assert [hashlib.sha256(fixture.step_bytes).hexdigest() for fixture in first] == [
        hashlib.sha256(fixture.step_bytes).hexdigest() for fixture in second
    ]
    document = parse_step_part21(first[0].step_bytes)
    assert len(document.entities) > 0
    assert document.reference_count > 0


def test_public_input_validation() -> None:
    """Public parsing boundaries should reject invalid types and limits."""
    with pytest.raises(TypeError, match="step_bytes"):
        parse_step_part21("not bytes")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="limits"):
        parse_step_part21(b"", limits=object())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="max_entities"):
        STEPParseLimits(max_entities=0)
