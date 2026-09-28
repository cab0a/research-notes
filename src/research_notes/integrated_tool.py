"""Unified terminal: python -m research_notes.integrated_tool."""
from __future__ import annotations
import argparse
import shlex
from pathlib import Path
from research_notes.modeling_tool import ModelingShell
from research_notes.integrated_workflow import IntegratedSession,source_layers
from research_notes.assembly_tool import AssemblyShell


class IntegratedShell(ModelingShell):
    prompt="3d> "
    intro="3D research workspace v0.85. Type help. Use semantics PATH or benchmark solver for the new evaluations."
    def __init__(self,output_dir,**kwargs):
        super().__init__(output_dir,**kwargs);self.session=IntegratedSession();self.assembly=AssemblyShell(output_dir/"assembly",stdout=self.stdout)

    def do_scan(self,arg):
        """scan STEP [EXPRESS]: bounded syntax/schema/application inspection without native geometry."""
        args=shlex.split(arg)
        if len(args) not in (1,2):raise ValueError("usage: scan STEP [EXPRESS]")
        self._emit(source_layers(Path(args[0]),schema_path=Path(args[1]) if len(args)==2 else None))

    def do_semantics(self, arg):
        """semantics PATH [DEFINITION_ID=REPRESENTATION_ID ...]: inspect AP roles and explicit shape selection."""
        from research_notes.portable_step import inspect_step_file
        from research_notes.robustness_studies import evidence_bytes
        args = shlex.split(arg)
        if not args:
            raise ValueError("usage: semantics PATH [DEFINITION_ID=REPRESENTATION_ID ...]")
        selections = {}
        for item in args[1:]:
            parts = item.split("=")
            if len(parts) != 2:
                raise ValueError("selection requires DEFINITION_ID=REPRESENTATION_ID")
            key, value = (int(p) for p in parts)
            if key in selections:
                raise ValueError("duplicate definition selection")
            selections[key] = value
        report = inspect_step_file(Path(args[0]), selections=selections)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        destination = self.output_dir / "semantics.json"
        destination.write_bytes(evidence_bytes(report))
        self._emit({"status": report["status"], "schema": report["schema"], "products": report["products"],
                    "diagnostics": report["diagnostics"], "evidence": str(destination)})

    def do_benchmark(self, arg):
        """benchmark solver|references|ap|structure|all: save offline robustness CSV, HTML and detailed evidence."""
        from collections import Counter
        from research_notes.robustness_studies import run_study, STUDIES
        names = {"solver": "solver_robustness", "references": "reference_robustness",
                 "ap": "ap_portability", "structure": "complex_product_structures"}
        requested = arg.strip()
        if requested != "all" and requested not in names:
            raise ValueError("usage: benchmark solver|references|ap|structure|all")
        output = self.output_dir / "benchmarks"
        for name in STUDIES if requested == "all" else (names[requested],):
            rows = run_study(name, output)
            self._emit({"study": name, "cases": len(rows), "contracts_matched": sum(r["checks_pass"] for r in rows),
                        "assessments": dict(Counter(r.get("assessment", r.get("status", "scored")) for r in rows)),
                        "report": str(output / (name + ".html"))})
            if not all(r["checks_pass"] for r in rows):
                raise ValueError("benchmark contract mismatch; inspect the saved report")

    def do_open(self,arg):
        """open PATH [--inspect-only]: inspect public geometry, or infer bounded editable proposals."""
        args=shlex.split(arg)
        if len(args)==2 and args[1]=="--inspect-only":
            self._emit(self.session.open_step_for_inspection(Path(args[0])))
        else:super().do_open(arg)

    def do_export(self,arg):
        """export PATH [--inspection-only] [--overwrite]: verified geometry-only STEP output."""
        args=shlex.split(arg)
        if "--inspection-only" not in args:return super().do_export(arg)
        if len(args) not in (2,3) or args[1:] not in (["--inspection-only"],["--inspection-only","--overwrite"]):
            raise ValueError("usage: export PATH --inspection-only [--overwrite]")
        self._emit(self.session.export_inspected_step(Path(args[0]),overwrite="--overwrite" in args))

    def do_schema(self,arg):
        """schema EXPRESS: validate imported immutable source against a supplied bounded schema."""
        args=shlex.split(arg)
        if len(args)!=1:raise ValueError("usage: schema EXPRESS")
        self._emit(self.session.schema(Path(args[0])))

    def do_review(self,arg):
        """review: compare reconstruction residual, complexity, sketches and local stability."""
        self._emit(self.session.review())

    def do_rank(self,arg):
        """rank: show learned eight-way feature hypotheses with source and descriptor evidence."""
        self._emit(self.session.rank())

    def do_analyze(self,arg):
        """analyze: report per-face curvature, trim residuals and spline parameters."""
        self._emit(self.session.analyze())

    def do_material(self,arg):
        """material DENSITY kg/m3|g/cm3: assign explicit homogeneous density."""
        args=shlex.split(arg)
        if len(args)!=2:raise ValueError("usage: material 7800 kg/m3")
        self._emit(self.session.set_material(float(args[0]),args[1]))

    def do_mass(self,arg):
        """mass: report volume, mass, centroid, inertia and principal axes."""
        self._emit(self.session.mass())

    def do_ask(self,arg):
        """ask REQUEST: inspect, show mass, or preview '穴の半径を1.5 mmに' / 'set feature radius 1.5 mm'."""
        self._emit(self.session.ask(arg))

    def do_apply(self,arg):
        """apply ID|latest --confirm: execute a reviewed, current proposal transaction."""
        args=shlex.split(arg)
        if not 1<=len(args)<=2 or (len(args)==2 and args[1]!="--confirm"):raise ValueError("usage: apply ID --confirm")
        self._emit(self.session.apply(args[0],confirm=len(args)==2))

    def do_report(self,arg):
        """report: save integrated HTML, comparison image and JSON evidence."""
        self._emit(self.session.report(self.output_dir))

    def do_assembly(self,arg):
        """assembly COMMAND: open/set/recompute/status/report/export authored assembly workflow."""
        previous=self.assembly.errors;self.assembly.onecmd(arg)
        if self.assembly.errors>previous:raise ValueError("assembly command failed")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir",type=Path,default=Path("output/integrated-workspace"));parser.add_argument("--script",type=Path)
    args=parser.parse_args();shell=IntegratedShell(args.output_dir)
    if args.script:
        for line in args.script.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.lstrip().startswith("#"):continue
            if shell.onecmd(line):break
            if shell.errors:return 1
    else:shell.cmdloop()
    return int(bool(shell.errors))


if __name__=="__main__":raise SystemExit(main())
