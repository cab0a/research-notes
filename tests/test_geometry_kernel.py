"""Tests for the v0.31 geometry-kernel and license decision record."""

from __future__ import annotations

import importlib.util

import pytest

from research_notes.geometry_kernel import (
    REQUIRED_GATES,
    audit_installed_distribution,
    geometry_backend_candidates,
    normalize_ocp_step_bytes,
    probe_ocp_backend,
    selected_geometry_backend,
)


def test_candidate_catalog_has_one_explicit_selection() -> None:
    """One technically complete route should be selected without hiding gaps."""
    candidates = geometry_backend_candidates()

    assert len(candidates) == 8
    assert len({candidate.candidate_id for candidate in candidates}) == len(candidates)
    selected = selected_geometry_backend()
    assert selected.candidate_id == "cadquery_ocp"
    assert selected.passes_all_gates
    assert selected.passed_gate_count == len(REQUIRED_GATES)


def test_independent_candidates_are_not_mislabeled_as_occt_alternatives() -> None:
    """Kernel-family independence must remain separate from wrapper choice."""
    candidates = {item.candidate_id: item for item in geometry_backend_candidates()}

    assert not candidates["pythonocc_core"].independent_kernel_family
    assert not candidates["freecad"].independent_kernel_family
    assert candidates["truck"].independent_kernel_family
    assert candidates["manifold"].independent_kernel_family
    assert candidates["parasolid"].independent_kernel_family


def test_timestamp_normalization_is_narrow_and_deterministic() -> None:
    """Only known generated header and product values should be normalized."""
    source = (
        b"FILE_NAME('Open CASCADE Shape Model','2026-08-04T00:00:00',('A'));"
        b"PRODUCT('Open CASCADE STEP translator 7.9 8',"
        b"'Open CASCADE STEP translator 7.9 8')"
    )

    normalized = normalize_ocp_step_bytes(source)

    assert normalized == (
        b"FILE_NAME('Open CASCADE Shape Model','2000-01-01T00:00:00',('A'));"
        b"PRODUCT('Open CASCADE STEP translator 7.9 1',"
        b"'Open CASCADE STEP translator 7.9 1')"
    )
    with pytest.raises(ValueError, match="exactly one"):
        normalize_ocp_step_bytes(b"FILE_NAME('other','2026-08-04T00:00:00')")
    with pytest.raises(TypeError, match="source_bytes"):
        normalize_ocp_step_bytes("bad")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="expected_translator_occurrences"):
        normalize_ocp_step_bytes(source, expected_translator_occurrences=2.0)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="must be positive"):
        normalize_ocp_step_bytes(source, expected_translator_occurrences=0)


@pytest.mark.skipif(
    importlib.util.find_spec("OCP") is None,
    reason="install the geometry extra to run the native probe",
)
def test_ocp_box_round_trip_preserves_controlled_topology() -> None:
    """The selected backend should pass one headless synthetic STEP round trip."""
    probe = probe_ocp_backend()

    assert probe.writer_status == "IFSelect_RetDone"
    assert probe.reader_status == "IFSelect_RetDone"
    assert probe.transferred_roots == 1
    assert probe.constructed_valid
    assert probe.imported_valid
    assert (
        probe.constructed_solids,
        probe.constructed_faces,
        probe.constructed_edges,
        probe.constructed_vertices,
    ) == (1, 6, 12, 8)
    assert (
        probe.imported_solids,
        probe.imported_faces,
        probe.imported_edges,
        probe.imported_vertices,
    ) == (1, 6, 12, 8)
    assert b"2000-01-01T00:00:00" in probe.source_bytes
    assert b"research-notes-ocp-" not in probe.source_bytes


@pytest.mark.skipif(
    importlib.util.find_spec("OCP") is None,
    reason="install the geometry extra to run the native probe",
)
def test_ocp_probe_is_byte_deterministic_and_is_accepted_by_current_parser() -> None:
    """Repeated writes should match after timestamp normalization."""
    first = probe_ocp_backend()
    second = probe_ocp_backend()

    assert first.source_bytes == second.source_bytes
    assert first.source_sha256 == second.source_sha256
    assert (first.internal_parser_decision, first.internal_parser_reason) == (
        "accept",
        "part21_parsed",
    )
    assert (first.internal_parser_line, first.internal_parser_column) == (None, None)


@pytest.mark.skipif(
    importlib.util.find_spec("OCP") is None,
    reason="install the geometry extra to audit the installed distribution",
)
def test_package_audit_keeps_wrapper_and_kernel_notice_questions_separate() -> None:
    """Package metadata must not be mistaken for the native kernel license."""
    audit = audit_installed_distribution("cadquery-ocp")

    assert audit.version == "7.9.3.1.1"
    assert audit.metadata_license == "Apache-2.0"
    assert any("cadquery_ocp/LICENSE" == path for path in audit.license_files)
    assert not audit.occt_lgpl_notice_detected
    assert all(not path.startswith(("/", "\\")) for path in audit.license_files)
    assert audit.recorded_file_count == 728


def test_public_inputs_fail_predictably() -> None:
    """Public helpers should reject wrong or empty argument values."""
    with pytest.raises(TypeError, match="name"):
        audit_installed_distribution(1)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="platform_label"):
        probe_ocp_backend(platform_label=1)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="must not be empty"):
        probe_ocp_backend(platform_label="")
