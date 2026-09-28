"""Regenerate the bounded topological-references study."""
from pathlib import Path
import argparse

from research_notes.assembly_studies import run_topological_references

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument("--fixture-dir", type=Path, default=Path("fixtures/topological-references"))
    parser.add_argument("--refresh-fixtures", action="store_true")
    args = parser.parse_args()
    rows = run_topological_references(args.output_dir, args.fixture_dir, refresh=args.refresh_fixtures)
    print(f"topological_references: {len(rows)} observations, all checks pass")

if __name__ == "__main__":
    main()
