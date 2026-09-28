"""Explicitly re-fetch hash-pinned STEP files and license snapshots."""
import argparse
from pathlib import Path
from research_notes.public_step_corpus import fetch_corpus

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    manifest = fetch_corpus(args.destination)
    print(f"Verified {len(manifest['assets'])} unchanged upstream assets")
