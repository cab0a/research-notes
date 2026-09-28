"""Generate v0.60.0 assisted import/edit/recompute/export workflow evidence."""

import argparse
from pathlib import Path

from research_notes.modeling_studies import run_assisted_modeling


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument("--fixture-dir", type=Path, default=Path("fixtures/assisted-modeling"))
    parser.add_argument("--source-fixture-dir", type=Path, default=Path("fixtures/step-reconstruction"))
    parser.add_argument("--refresh-fixtures", action="store_true")
    args = parser.parse_args()
    rows = run_assisted_modeling(args.output_dir, args.fixture_dir, args.source_fixture_dir, refresh=args.refresh_fixtures)
    print(f"Verified {len(rows)} assisted modeling workflows")


if __name__ == "__main__":
    main()
