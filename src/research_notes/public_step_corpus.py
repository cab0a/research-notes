"""Offline public STEP regression corpus with pinned provenance and licenses."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from dataclasses import asdict
from pathlib import Path
from urllib.request import Request, urlopen

from research_notes.advanced_geometry_studies import evidence_bytes
from research_notes.brep_preview import write_shape_previews
from research_notes.integrated_workflow import IntegratedSession
from research_notes.modeling_studies import csv_bytes
from research_notes.public_step import measured_round_trip, solid_measurements
from research_notes.step_reconstruction import reconstruct_step

CORPUS = Path(__file__).resolve().parents[2] / "fixtures/public-step-corpus"


def asset_path(root, relative):
    path = Path(relative)
    root = Path(root).resolve()
    if path.is_absolute() or ".." in path.parts or "\\" in relative:
        raise ValueError("invalid corpus asset path")
    target = (root / path).resolve()
    if target == root or not target.is_relative_to(root):
        raise ValueError("corpus path escapes destination")
    return target


def load_manifest(root=CORPUS):
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assets = manifest["assets"]
    by_path = {asset["path"]: asset for asset in assets}
    if manifest["format_version"] != 1 or len(by_path) != len(assets):
        raise ValueError("invalid corpus manifest or duplicate asset")
    for asset in assets:
        asset_path(root, asset["path"])
        if not re.fullmatch(r"[a-f0-9]{40}", asset["revision"]) or not re.fullmatch(r"[a-f0-9]{64}", asset["sha256"]):
            raise ValueError("every upstream revision and digest must be pinned")
        if not re.fullmatch(r"https://github.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", asset["repository"]):
            raise ValueError("unsupported source repository")
        prefix = asset["repository"].replace("https://github.com/", "https://raw.githubusercontent.com/") + "/" + asset["revision"] + "/"
        if asset["download_url"] != prefix + asset["upstream_path"] or ".." in Path(asset["upstream_path"]).parts:
            raise ValueError("download must refer to the exact pinned upstream asset")
        if type(asset["bytes"]) is not int or not 0 < asset["bytes"] <= 8_000_000:
            raise ValueError("asset byte budget exceeded")
    ids = set()
    for sample in manifest["samples"]:
        if sample["sample_id"] in ids or not sample["attribution"] or not sample["license_id"] or not sample["license_paths"]:
            raise ValueError("missing attribution/license or duplicate sample")
        ids.add(sample["sample_id"])
        source = by_path[sample["asset_path"]]
        if source["role"] != "step":
            raise ValueError("sample must reference a STEP asset")
        for relative in sample["license_paths"]:
            license_asset = by_path[relative]
            if license_asset["role"] != "license_notice" or any(license_asset[k] != source[k] for k in ("repository", "revision")):
                raise ValueError("license must belong to the same pinned repository revision")
    return manifest


def verify_corpus(root=CORPUS):
    manifest = load_manifest(root)
    for asset in manifest["assets"]:
        path = asset_path(root, asset["path"])
        with path.open("rb") as stream:
            payload = stream.read(asset["bytes"] + 1)
        if len(payload) != asset["bytes"] or hashlib.sha256(payload).hexdigest() != asset["sha256"]:
            raise ValueError("corpus asset size/hash mismatch: " + asset["path"])
    return manifest


def fetch_corpus(destination, *, manifest_root=CORPUS):
    """Explicit network acquisition only; ordinary studies and tests stay offline."""
    manifest = load_manifest(manifest_root)
    destination = Path(destination)
    metadata = {}
    for name in ("manifest.json", "expectations.json"):
        source = (Path(manifest_root) / name).read_bytes()
        target = asset_path(destination, name)
        if target.exists() and target.read_bytes() != source:
            raise ValueError("refusing to overwrite different destination metadata: " + name)
        metadata[target] = source
    for asset in manifest["assets"]:
        path = asset_path(destination, asset["path"])
        if path.exists():
            with path.open("rb") as stream:
                payload = stream.read(asset["bytes"] + 1)
        else:
            request = Request(asset["download_url"], headers={"User-Agent": "research-notes-public-step/0.81"})
            with urlopen(request, timeout=30) as response:
                payload = response.read(asset["bytes"] + 1)
        if len(payload) != asset["bytes"] or hashlib.sha256(payload).hexdigest() != asset["sha256"]:
            raise ValueError("refusing changed upstream/existing bytes: " + asset["path"])
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
    for target, source in metadata.items():
        target.write_bytes(source)
    return verify_corpus(destination)


def observe_sample(root, sample, asset):
    path = asset_path(root, sample["asset_path"])
    session = IntegratedSession()
    inspection = session.open_step_for_inspection(path)
    shape = session.shape()
    analysis = session.analyze()
    solids = solid_measurements(shape)
    _, exchange = measured_round_trip(shape)
    try:
        editable = reconstruct_step(path)
        reconstruction = {"status": editable.status, "candidates": len(editable.candidates), "reason": editable.reason}
    except ValueError as exc:
        reconstruction = {"status": "unsupported", "candidates": 0, "reason": str(exc)}
    row = {"sample_id": sample["sample_id"], "family_id": sample["family_id"],
           "source_sha256": asset["sha256"], "license_id": sample["license_id"],
           "syntax": inspection["layers"]["syntax"]["status"],
           "application_semantics": inspection["layers"]["application_semantics"]["status"],
           "inspection": inspection["status"], "roots": session.layers["native_geometry"]["transferred_roots"],
           "solid_count": inspection["metrics"]["solid_count"], "face_count": inspection["metrics"]["face_count"],
           "measured_solids": sum(s["status"] == "measured" for s in solids["solids"]),
           "analysis": analysis["status"], "analyzed_faces": analysis["analyzed_face_count"],
           "trim_check_failures": analysis["trim_check_failures"], "differential_failures": analysis["differential_failures"],
           "reconstruction": reconstruction["status"], "editable_candidates": reconstruction["candidates"],
           "round_trip": exchange["status"]}
    evidence = {"sample": sample, "asset": asset, "inspection": inspection,
                "face_analysis": analysis, "solid_measurements": solids,
                "reconstruction": reconstruction, "round_trip": exchange}
    return row, evidence, shape


def run_public_step_corpus(output, *, corpus=CORPUS, check_baseline=True):
    manifest = verify_corpus(corpus)
    assets = {a["path"]: a for a in manifest["assets"]}
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    rows, evidence, previews = [], [], []
    baseline = json.loads((Path(corpus) / "expectations.json").read_text()) if check_baseline else {}
    for sample in manifest["samples"]:
        row, detail, shape = observe_sample(corpus, sample, assets[sample["asset_path"]])
        if check_baseline:
            expected = baseline[sample["sample_id"]]
            row["checks_pass"] = all(row.get(k) == v for k,v in expected.items())
            detail["expected_outcomes"] = expected
        rows.append(row)
        evidence.append(detail)
        previews.append((sample["sample_id"].replace("build123d_", "").replace("cadquery_", ""), shape))
    # Paired formats are compared as measurements, not assumed semantically equal.
    sam = [e for e in evidence if e["sample"]["family_id"] == "ublox_sam"]
    first, second = (e["inspection"]["metrics"] for e in sam)
    paired = {"family_id": "ublox_sam", "sample_ids": [e["sample"]["sample_id"] for e in sam],
              "volume_difference_mm3": abs(first["absolute_volume"] - second["absolute_volume"]),
              "area_difference_mm2": abs(first["surface_area"] - second["surface_area"]),
              "semantic_equivalence_claimed": False}
    (output / "public_step_corpus.csv").write_bytes(csv_bytes(rows))
    (output / "public_step_corpus_evidence.json").write_bytes(evidence_bytes({"samples": evidence, "paired_formats": paired}))
    contract = {"version": "0.81.0", "sample_count": len(rows), "independent_family_count": len({r['family_id'] for r in rows}),
                "geometry_backend": "cadquery-ocp 7.9.3.1.1 (reference environment)",
                "network_required": False, "training_use": False,
                "baseline_kind": "reviewed observations on pinned external inputs; not author-supplied geometric truth",
                "checks_pass_meaning": "matches frozen declared outcomes, including unsupported, partial and disputed outcomes",
                "claim_boundaries": ["six selected files, not representative industrial coverage or full AP conformance",
                    "geometry inspection does not recover editable history, colors, materials, product structure, PMI or mates",
                    "same OCCT kernel imports and exports; measured invariants are not pointwise shape equivalence",
                    "uniform SI metre/centimetre/millimetre or bounded conversion chains, normalized to mm; mixed contexts refused; no OS time/memory sandbox",
                    "differential samples and 17-point wire checks do not certify whole faces; fixed face limit is explicit",
                    "per-solid unit-density integration is not a physical assembly mass or material assignment"]}
    (output / "public_step_corpus_contract.json").write_bytes(evidence_bytes(contract))
    write_shape_previews(output / "public_step_corpus.png", tuple(previews), title="Public STEP: six pinned external samples", columns=3)
    table = "".join("<tr>" + "".join(f"<td>{html.escape(str(row[k]))}</td>" for k in
        ("sample_id", "solid_count", "face_count", "analysis", "trim_check_failures", "round_trip", "reconstruction")) + "</tr>" for row in rows)
    sources = "".join(f'<li><a href="{html.escape(e["asset"]["source_url"],quote=True)}">{html.escape(e["sample"]["sample_id"])}</a> — {html.escape(e["sample"]["attribution"])} · {html.escape(e["sample"]["license_id"])}</li>' for e in evidence)
    page = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Public STEP validation</title><style>body{{font:16px system-ui;background:#f3f6f9;color:#193246;margin:0}}main{{max-width:1250px;margin:auto;padding:32px}}section{{background:white;padding:24px;border-radius:12px;margin:20px 0}}img{{width:100%}}.table{{overflow:auto}}table{{border-collapse:collapse;width:100%}}td,th{{padding:10px;text-align:left;border-bottom:1px solid #ddd}}a{{color:#146d79}}</style>
<main><p>RESEARCH WORKSPACE / v0.81.0</p><h1>Public STEP validation</h1><p>6 byte-preserved files · 3 upstream projects · 5 part families · source and license snapshots pinned</p>
<section><img src="public_step_corpus.png" alt="Six external STEP models rendered with diagnostic face colors; original colors are not reproduced"></section>
<section><h2>Observed coverage</h2><div class="table"><table><tr><th>Sample</th><th>Solids</th><th>Faces</th><th>Face analysis</th><th>Trim failures</th><th>Round trip</th><th>Editing</th></tr>{table}</table></div>
<p>Complete means all faces were visited, not that all checks passed. Partial means the face budget was reached. Disputed means exchange measurements exceeded the declared thresholds.</p>
<p>AP203/AP214 application semantics remain unsupported. Editable authoring histories are not recovered. Native validity and exchange use the same OCCT kernel.</p></section>
<section><h2>Provenance and attribution</h2><ul>{sources}</ul><p>External models retain their upstream licenses. Renderings use diagnostic colors. The AP203/AP214 SAM files are a paired observation, not two independent part families.</p>
<a href="public_step_corpus_evidence.json">Full observations, source hashes and license paths</a> · <a href="public_step_corpus.csv">Coverage CSV</a> · <a href="public_step_corpus_contract.json">Contract and limitations</a></section></main></html>'''
    (output / "public_step_corpus.html").write_text(page, encoding="utf-8")
    if check_baseline and not all(r["checks_pass"] for r in rows):
        raise RuntimeError("public STEP observations differ from the committed baseline; inspect the output")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-dir", type=Path, default=CORPUS)
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    args = parser.parse_args()
    rows = run_public_step_corpus(args.output_dir, corpus=args.corpus_dir)
    print(f"v0.81.0: {len(rows)} public STEP observations match declared outcomes")


if __name__ == "__main__":
    main()
