"""Run the explicitly authored through-hole reconstruction example from the repo root."""
import argparse
import json
from pathlib import Path

from research_notes.cad_api import CadWorkspace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("output/cad-demo"))
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    workspace = CadWorkspace()
    workspace.open_step(Path("fixtures/step-reconstruction/through_hole.step"), mode="reconstruct")
    candidates = workspace.candidates().data["candidates"]
    print(json.dumps({"candidates": [{"candidate_id": c["candidate_id"], "explanation": c["explanation"]} for c in candidates]}, indent=2))
    # This example explicitly chooses the authored through-hole hypothesis.
    candidate = next(c for c in candidates if c["explanation"] == "through_hole")
    workspace.select(candidate["candidate_id"], confirm=True, expected_revision=workspace.revision_token)
    workspace.edit("feature", "radius", 1.3, expected_revision=workspace.revision_token)
    result = workspace.recompute(expected_revision=workspace.revision_token)
    if result.status != "committed":
        print(json.dumps(result.record(), indent=2))
        return 1
    print(json.dumps(workspace.compare().record(), indent=2))
    print(json.dumps(workspace.workspace(args.output_dir).record(), indent=2))
    print(json.dumps(workspace.export_step(args.output_dir / "edited.step", overwrite=args.overwrite).record(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
