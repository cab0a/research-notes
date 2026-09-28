"""Generate v0.59.0 STEP-to-feature reconstruction proposal evidence."""

import argparse
from pathlib import Path

from research_notes.modeling_studies import run_step_reconstruction


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument("--fixture-dir", type=Path, default=Path("fixtures/step-reconstruction"))
    parser.add_argument("--source-fixture-dir", type=Path, default=Path("fixtures/parametric-features"))
    parser.add_argument("--refresh-fixtures", action="store_true")
    args = parser.parse_args()
    rows = run_step_reconstruction(args.output_dir, args.fixture_dir, args.source_fixture_dir, refresh=args.refresh_fixtures)
    print(f"Verified {len(rows)} STEP reconstruction inputs")


if __name__ == "__main__":
    main()
