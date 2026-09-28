"""Compare measured artifacts without promising byte-identical floating point."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path


def canonical_evidence(value):
    if isinstance(value, dict):
        return {k: canonical_evidence(v) for k, v in value.items()}
    if isinstance(value, list):
        items = [canonical_evidence(v) for v in value]
        if items and all(isinstance(v, dict) and "solid_index" in v and "unit_density_properties" in v for v in items):
            # Solid indices identify one import, not an identity across imports.
            items = [{k: v for k, v in item.items() if k != "solid_index"} for item in items]
            items.sort(key=lambda r: tuple(round(x, 10) for x in r["unit_density_properties"]["centroid_m"]) +
                       (round(r["unit_density_properties"]["volume_m3"], 15),))
        return items
    return value


def evidence_differences(actual, expected):
    from research_notes.cad_platform import numeric_differences
    return numeric_differences(canonical_evidence(actual), canonical_evidence(expected), relative=1e-6, absolute=1e-9)


def verify_manifest(directory):
    directory = Path(directory)
    rows = list(csv.DictReader((directory / "manifest.csv").read_text(encoding="utf-8").splitlines()))
    assert {r["file_name"] for r in rows} == {p.name for p in directory.iterdir() if p.name != "manifest.csv"}
    for row in rows:
        raw = (directory / row["file_name"]).read_bytes()
        assert len(raw) == int(row["byte_length"]) and hashlib.sha256(raw).hexdigest() == row["sha256"], row["file_name"]


def compare_file(actual, expected):
    actual, expected = Path(actual), Path(expected)
    if actual.name == "manifest.csv":
        verify_manifest(actual.parent)
        verify_manifest(expected.parent)
        a = list(csv.DictReader(actual.read_text(encoding="utf-8").splitlines()))
        b = list(csv.DictReader(expected.read_text(encoding="utf-8").splitlines()))
        assert [(r["file_name"], r["generator"]) for r in a] == [(r["file_name"], r["generator"]) for r in b]
    elif actual.suffix == ".json":
        diff = evidence_differences(json.loads(actual.read_bytes()), json.loads(expected.read_bytes()))
        assert not diff, f"{actual.name}: {diff[:12]}"
    else:
        assert actual.read_bytes() == expected.read_bytes(), actual.name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("expected", type=Path)
    parser.add_argument("actual", type=Path)
    args = parser.parse_args()
    if args.actual.is_dir():
        assert {p.name for p in args.actual.iterdir()} == {p.name for p in args.expected.iterdir()}
        for path in args.actual.iterdir():
            compare_file(path, args.expected / path.name)
    else:
        compare_file(args.actual, args.expected)


if __name__ == "__main__":
    main()
