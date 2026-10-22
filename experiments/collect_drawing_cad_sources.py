"""Explicit network-only source capture; the geometry experiment is offline."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
URLS = {
    "ortho_paper": "https://arxiv.org/html/2607.08891v2",
    "drawing2cad_paper": "https://arxiv.org/html/2508.18733v5",
    "drawing_recode_paper": "https://arxiv.org/html/2607.27558v1",
    "ortho_dataset": "https://huggingface.co/api/datasets/AdityaJoglekar/Ortho2CAD_Orthographic_Drawings",
    "ortho_models_search": "https://huggingface.co/api/models?author=AdityaJoglekar&search=Ortho2CAD",
    "drawing2cad_drive": "https://drive.google.com/drive/folders/1t9uO2iFh1eVDXRCKUEonKPBu8WGYA8wU?usp=sharing",
    "cadgenbench_dataset": "https://huggingface.co/api/datasets/HuggingAI4Engineering/cadgenbench-data",
    "cadgenbench_private_gt": "https://huggingface.co/api/datasets/HuggingAI4Engineering/cadgenbench-data-gt",
    "solidworks": "https://help.solidworks.com/2026/English/SolidWorks/sldworks/c_2D_to_3D_Conversion_Overview.htm",
    "drawing_recode_repo_search": "https://api.github.com/search/repositories?q=Drawing-Recode+in:name",
}
REPOS = {"Ortho2CAD": "https://github.com/AdityaJoglekar/Ortho2CAD",
         "Drawing2CAD": "https://github.com/lllssc/Drawing2CAD",
         "cadgenbench": "https://github.com/huggingface/cadgenbench"}


def collect(output, date):
    cache = ROOT / "output/drawing-cad-sources/cache"
    cache.mkdir(parents=True, exist_ok=True)
    def fetch(item):
        name, url = item
        row = {"id": name, "url": url, "retrieved_on": date}
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "research-notes-source-review"})
            with urllib.request.urlopen(request, timeout=40) as response:
                data = response.read(2_000_001)
                row.update(http_status=response.status, resolved_url=response.url,
                           content_type=response.headers.get("Content-Type"), truncated=len(data) > 2_000_000)
            path = cache / (name + ".txt")
            path.write_bytes(data)
            row.update(status="retrieved", bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), cache_path=str(path.relative_to(ROOT)))
            if name.endswith("dataset") or name in ("ortho_models_search", "drawing_recode_repo_search"):
                value = json.loads(data)
                if isinstance(value, dict):
                    row["public_metadata"] = {k: value[k] for k in ("id", "sha", "private", "gated", "cardData", "siblings", "total_count") if k in value}
                    if "siblings" in row["public_metadata"]:
                        names=[s["rfilename"] for s in row["public_metadata"].pop("siblings")]
                        row["public_metadata"].update(file_count=len(names),files_sample=names[:12],
                            file_suffix_counts=dict(Counter(Path(n).suffix for n in names)),
                            description_files=sum(n.endswith("description.yaml") for n in names))
                    if "items" in value:
                        row["search_results"] = [r["full_name"] for r in value["items"]]
                elif isinstance(value, list):
                    row["model_search_ids"] = [v.get("id") for v in value]
        except Exception as error:
            row.update(status="unavailable", error_type=type(error).__name__, detail=str(error))
        return row
    with ThreadPoolExecutor(max_workers=4) as pool:
        sources = list(pool.map(fetch, URLS.items()))
    repos = []
    for name, url in REPOS.items():
        path = ROOT / "output/drawing-cad-sources" / name
        command = lambda *args: subprocess.check_output(["git", "-C", str(path), *args], text=True).strip()
        files = command("ls-files").splitlines()
        selected = [f for f in files if f.endswith((".py", ".sh", ".toml", ".txt", ".md")) or "LICENSE" in f.upper()]
        repos.append({"id": name, "url": url, "commit": command("rev-parse", "HEAD"), "reviewed_on": date,
            "license_files": [f for f in files if Path(f).name.upper().startswith(("LICENSE", "COPYING"))],
            "tracked_weight_files": [f for f in files if f.endswith((".pt", ".pth", ".ckpt", ".safetensors"))],
            "selected_file_sha256": {f: hashlib.sha256((path / f).read_bytes()).hexdigest() for f in selected}})
    report = {"study": "2D Engineering Drawing to Parametric 3D CAD Reconstruction", "date": date,
        "repositories": repos, "sources": sources,
        "scope": "Public source/metadata inspection only. No upstream training/inference or dataset/weight binary download; no API model calls. HTTP metadata access is not proof of runnable data or license compatibility."}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"repos": [{"id": r["id"], "commit": r["commit"], "licenses": r["license_files"], "weights": r["tracked_weight_files"]} for r in repos],
                      "urls": [{"id": s["id"], "status": s["status"]} for s in sources]}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results/drawing-to-cad/source-review.json")
    parser.add_argument("--date", required=True, help="Client research date YYYY-MM-DD")
    args = parser.parse_args()
    collect(args.output, args.date)
