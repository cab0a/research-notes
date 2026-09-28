"""Regenerate all four new studies and compare committed machine-readable data."""

from pathlib import Path

import pytest

from research_notes.modeling_studies import (
    run_assisted_modeling, run_deterministic_recompute,
    run_parametric_features, run_step_reconstruction,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("runner,fixture_name,source", [
    (run_parametric_features, "parametric-features", None),
    (run_deterministic_recompute, "deterministic-recompute", None),
    (run_step_reconstruction, "step-reconstruction", "parametric-features"),
    (run_assisted_modeling, "assisted-modeling", "step-reconstruction"),
])
def test_reference_data_and_input_fixtures_regenerate(tmp_path, runner, fixture_name, source):
    output, fixtures = tmp_path / "results", tmp_path / "fixtures"
    args = [output, fixtures] + ([ROOT / "fixtures" / source] if source else [])
    rows = runner(*args, refresh=True)
    assert all(row["checks_pass"] for row in rows)
    for generated in fixtures.iterdir():
        assert generated.read_bytes() == (ROOT / "fixtures" / fixture_name / generated.name).read_bytes()
    for generated in output.iterdir():
        if generated.suffix in {".csv", ".json"}:
            assert generated.read_bytes() == (ROOT / "results" / generated.name).read_bytes(), generated.name
        else:
            assert generated.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
