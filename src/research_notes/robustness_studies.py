"""Offline reproduction entry point for the v0.82-v0.85 evidence package."""
from __future__ import annotations

import argparse
import csv
import html
import io
import json
from importlib import import_module
from pathlib import Path

from research_notes.modeling_studies import handle_fixtures

ROOT = Path(__file__).resolve().parents[2]
STUDIES = {
    "ap_portability": (82, "semantic_portability_studies"),
    "complex_product_structures": (83, "semantic_portability_studies"),
    "reference_robustness": (84, "reference_benchmark"),
    "solver_robustness": (85, "solver_benchmark"),
}


def evidence_bytes(value):
    # Preserve small residuals and singular values; they are the experiment.
    def normalize(item):
        if isinstance(item, float):
            return float(f"{item:.10g}")
        if isinstance(item, dict):
            return {k: normalize(v) for k, v in item.items()}
        if isinstance(item, (list, tuple)):
            return [normalize(v) for v in item]
        return item
    return (json.dumps(normalize(value), sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def finish(output, fixtures, name, rows, detail, inputs, boundaries, *, refresh=False, version=None):
    output.mkdir(parents=True, exist_ok=True)
    version = version or f"v0.{STUDIES[name][0]}.0"
    handle_fixtures(fixtures, inputs, refresh=refresh, generator=f"experiments/run_{name}.py")
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=tuple(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    (output / f"{name}.csv").write_text(stream.getvalue(), encoding="utf-8", newline="\n")
    (output / f"{name}_evidence.json").write_bytes(evidence_bytes(detail))
    contract = {"version": version, "study": name, "control_count": len(rows),
                "checks_pass": all(r["checks_pass"] for r in rows), "boundaries": boundaries,
                "numeric_evidence": "10 significant digits; tiny residuals retained; classifications are tolerance-based",
                "regression_check": "checks_pass is the declared case contract, not universal solver or CAD success"}
    (output / f"{name}_contract.json").write_bytes(evidence_bytes(contract))
    columns = tuple(rows[0])
    table = "<thead><tr>" + "".join(f"<th>{html.escape(k)}</th>" for k in columns) + "</tr></thead><tbody>"
    for row in rows:
        table += "<tr>" + "".join(f"<td>{html.escape(str(row[k]))}</td>" for k in columns) + "</tr>"
    title = name.replace("_", " ").title()
    page = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{title} — {version}</title><style>body{{font:15px system-ui;margin:2rem;color:#203042;background:#f4f7fa}}h1{{color:#153650}}table{{border-collapse:collapse;background:white}}th,td{{text-align:left;padding:.6rem;border:1px solid #cbd4df}}th{{background:#e2edf3}}.scroll{{overflow:auto}}li{{margin:.5rem}}img{{max-width:100%}}a{{color:#005c80}}</style>
<h1>{title} · {version}</h1><p>Offline, bounded research controls. A passing check may document a failure or an abstention.</p>
<ul>{''.join('<li>'+html.escape(s)+'</li>' for s in boundaries)}</ul><div class="scroll"><table>{table}</tbody></table></div>
<p><a href="{name}_evidence.json">Detailed evidence</a> · <a href="{name}.csv">CSV</a> · <a href="{name}_contract.json">Contract</a></p>
<img src="{name}.png" alt="Control outcomes"></html>'''
    (output / f"{name}.html").write_text(page, encoding="utf-8", newline="\n")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(11, max(4, len(rows) * .22)))
    if name == "reference_robustness":
        ax.barh([r["control_id"] for r in rows], [r["coverage"] for r in rows], label="Asserted coverage", color="#147d92")
        ax.barh([r["control_id"] for r in rows], [r["incorrect_fraction"] for r in rows], label="Incorrect assertions", color="#c94545")
        ax.set(xlim=(0, 1.05), xlabel="Fraction of source face / edge references")
        ax.legend()
    elif name == "solver_robustness":
        from collections import Counter
        plt.close(fig)
        fig, ax = plt.subplots(figsize=(10, 4))
        counts = Counter(r["assessment"] for r in rows)
        ax.bar(list(counts), list(counts.values()), color="#147d92")
        ax.set(ylabel="Cases", xlabel="Independent assessment, distinct from solver status")
        ax.tick_params(axis="x", labelrotation=15)
    else:
        has_products = all("product_count" in row for row in rows)
        ax.barh([r["control_id"] for r in rows], [r["product_count"] if has_products else int(r["checks_pass"]) for r in rows], color="#147d92")
        ax.set(xlabel="Product definitions with an interpreted source path" if has_products else "Declared case contract matched (may include a known limitation)")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(output / f"{name}.png", dpi=120)
    plt.close(fig)
    return rows


def run_study(name, output=None, fixtures=None, *, refresh=False):
    if name not in STUDIES:
        raise ValueError("unknown robustness study")
    module = import_module("research_notes." + STUDIES[name][1])
    return getattr(module, "run_" + name)(Path(output or ROOT / "results"),
        Path(fixtures or ROOT / "fixtures" / name.replace("_", "-")), refresh=refresh)


def main(default=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", choices=tuple(STUDIES), default=default)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results")
    parser.add_argument("--fixture-dir", type=Path)
    parser.add_argument("--refresh-fixtures", action="store_true")
    args = parser.parse_args()
    passed = True
    for name in (args.study,) if args.study else STUDIES:
        directory = args.fixture_dir if args.study else args.fixture_dir / name.replace("_", "-") if args.fixture_dir else None
        rows = run_study(name, args.output_dir, directory, refresh=args.refresh_fixtures)
        matched = sum(bool(r["checks_pass"]) for r in rows)
        print(f"{name}: {matched}/{len(rows)} case contracts matched")
        passed &= matched == len(rows)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
