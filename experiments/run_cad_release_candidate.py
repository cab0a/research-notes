"""Reproduce the declared release study."""
import sys
from research_notes.release_studies import main

if __name__ == "__main__":
    sys.argv.insert(1, "cad_release_candidate")
    raise SystemExit(main())
