"""Generate v0.58.0 deterministic recompute and failure-isolation evidence."""

import argparse
from pathlib import Path

from research_notes.modeling_studies import run_deterministic_recompute


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument("--fixture-dir", type=Path, default=Path("fixtures/deterministic-recompute"))
    parser.add_argument("--refresh-fixtures", action="store_true")
    args = parser.parse_args()
    rows = run_deterministic_recompute(args.output_dir, args.fixture_dir, refresh=args.refresh_fixtures)
    print(f"Verified {len(rows)} recompute scenarios")


if __name__ == "__main__":
    main()
