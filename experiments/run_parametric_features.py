"""Generate v0.57.0 parametric hole, pocket, boss, and rib evidence."""

import argparse
from pathlib import Path

from research_notes.modeling_studies import run_parametric_features


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument("--fixture-dir", type=Path, default=Path("fixtures/parametric-features"))
    parser.add_argument("--refresh-fixtures", action="store_true")
    args = parser.parse_args()
    rows = run_parametric_features(args.output_dir, args.fixture_dir, refresh=args.refresh_fixtures)
    print(f"Verified {len(rows)} parametric feature observations")


if __name__ == "__main__":
    main()
