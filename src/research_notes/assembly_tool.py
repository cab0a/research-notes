"""Interactive authored-assembly workspace: python -m research_notes.assembly_tool."""
from __future__ import annotations

import argparse
import cmd
import html
import json
import shlex
from dataclasses import asdict, replace
from pathlib import Path

from research_notes.assembly_constraints import validate_assembly
from research_notes.assembly_recompute import AssemblySession, assembly_from_dict, assembly_record, compound_shapes
from research_notes.brep_preview import write_shape_previews


class AssemblyShell(cmd.Cmd):
    prompt = "assembly> "
    intro = "Assembly research workspace. Type help; open the authored JSON demo to begin."

    def __init__(self, output_dir: Path, **kwargs):
        super().__init__(**kwargs)
        self.output_dir = output_dir
        self.session = None
        self.baseline = None
        self.removed_constraints = {}
        self.errors = 0

    def _emit(self, value):
        self.stdout.write(json.dumps(value, indent=2, sort_keys=True) + "\n")

    def onecmd(self, line):
        try:
            return super().onecmd(line)
        except (ValueError, RuntimeError, OSError, KeyError, TypeError) as exc:
            self.errors += 1
            self._emit({"error": str(exc)})
            return False

    def emptyline(self):
        pass

    def default(self, line):
        raise ValueError("unknown command; type help")

    def _session(self):
        if self.session is None:
            raise ValueError("open an assembly JSON first")
        return self.session

    def do_open(self, arg):
        """open PATH: load an authored assembly JSON with explicit definitions and mates."""
        args = shlex.split(arg)
        if len(args) != 1:
            raise ValueError("usage: open PATH")
        with Path(args[0]).open("rb") as stream:
            payload = stream.read(1_000_001)
        if len(payload) > 1_000_000:
            raise ValueError("assembly JSON exceeds 1000000 bytes")
        document = assembly_from_dict(json.loads(payload))
        self.session, self.baseline, self.removed_constraints = AssemblySession(document), None, {}
        self._emit({"assembly_id": document.assembly_id, "definitions": len(document.definitions),
                    "occurrences": len(document.occurrences), "parameters": [asdict(p) for p in document.parameters]})

    def do_inspect(self, arg):
        """inspect: show definitions, occurrences, local frames, parameters, and constraints."""
        self._emit(asdict(self._session().document))

    def do_set(self, arg):
        """set NAME EXPRESSION: edit a dimension, e.g. set clearance 0 * mm."""
        parts = arg.strip().split(maxsplit=1)
        if len(parts) != 2:
            raise ValueError("usage: set NAME EXPRESSION")
        self._session().set_parameter(*parts)
        self._emit({"revision": self.session.document.revision, "recompute_required": True})

    def do_drop(self, arg):
        """drop CONSTRAINT: temporarily remove a mate to inspect remaining freedom."""
        session = self._session()
        key = arg.strip()
        constraint = next((c for c in session.document.constraints if c.constraint_id == key), None)
        if constraint is None:
            raise ValueError("unknown constraint")
        self.removed_constraints[key] = constraint
        session.document = replace(session.document, revision=session.document.revision+1,
                                   constraints=tuple(c for c in session.document.constraints if c.constraint_id != key))
        self._emit({"removed_constraint": key, "recompute_required": True})

    def do_restore(self, arg):
        """restore CONSTRAINT: reactivate a mate removed in this session."""
        session = self._session()
        key = arg.strip()
        if key not in self.removed_constraints:
            raise ValueError("no removed constraint with this name")
        document = replace(session.document, revision=session.document.revision+1,
                           constraints=session.document.constraints+(self.removed_constraints[key],))
        validate_assembly(document)
        session.document = document
        del self.removed_constraints[key]
        self._emit({"restored_constraint": key, "recompute_required": True})

    def do_recompute(self, arg):
        """recompute: rebuild definitions, solve occurrences, report freedom and interference."""
        result = self._session().recompute()
        if self.baseline is None and result.status == "fully_constrained":
            self.baseline = result
        solution = result.solution
        self._emit({"status": result.status, "degrees_of_freedom": solution.degrees_of_freedom if solution else None,
                    "redundant_equations": solution.redundant_equations if solution else None,
                    "conflict_constraints": solution.conflict_constraints if solution else (),
                    "pair_checks": result.pair_checks,
                    "components_evaluated": {key: value.evaluated_nodes for key, value in result.component_results}})

    def do_status(self, arg):
        """status: show current solver residuals, local motion modes, and pair checks."""
        self._emit(assembly_record(self._session().current()))

    def do_report(self, arg):
        """report: save initial/current assembly images and complete diagnostics as HTML/JSON."""
        session = self._session()
        result = session.current()
        output = self.output_dir
        output.mkdir(parents=True, exist_ok=True)
        report = assembly_record(result)
        (output/"assembly.json").write_text(json.dumps(report, indent=2, sort_keys=True)+"\n", encoding="utf-8")
        entries = []
        if self.baseline and self.baseline.placed_shapes:
            entries.append(("Initial constrained assembly", compound_shapes(s for _, s in self.baseline.placed_shapes)))
        if result.placed_shapes:
            label = f"Current: {result.status}; freedom={result.solution.degrees_of_freedom}"
            entries.append((label, compound_shapes(s for _, s in result.placed_shapes)))
        image_markup = ""
        if entries:
            write_shape_previews(output/"assembly.png", tuple(entries), title="Assembly placement comparison", columns=2)
            image_markup = '<img src="assembly.png" alt="Initial and current assembly geometry">'
        dof = result.solution.degrees_of_freedom if result.solution else "unavailable"
        redundancy = result.solution.redundant_equations if result.solution else "unavailable"
        pair_rows = "".join("<tr><td>"+html.escape(p["occurrence_a"]+" / "+p["occurrence_b"])+"</td><td>"+
                            html.escape(p["status"])+f'</td><td>{p["minimum_distance_mm"]:.6f}</td><td>{p["overlap_volume_mm3"]:.6f}</td></tr>'
                            for p in result.pair_checks)
        unavailable = "" if result.placed_shapes else "<p>Current geometry is unavailable. Any initial preview is historical, not this revision.</p>"
        page = f"""<!doctype html><html lang="en"><meta charset="utf-8"><title>Assembly report</title>
<style>body{{font:16px system-ui;max-width:1200px;margin:32px;color:#203246}}table{{border-collapse:collapse}}td,th{{padding:10px;border:1px solid #ccd5df}}img{{width:100%}}</style>
<h1>Assembly recompute</h1><p>Status: <strong>{html.escape(result.status)}</strong> · Remaining local freedom: {dof} · Redundant equations: {redundancy}</p>
<table><tr><th>Occurrences</th><th>Pair status</th><th>Distance (mm)</th><th>Overlap (mm³)</th></tr>{pair_rows}</table>
{unavailable}{image_markup}<p>Motion modes are local numerical observations. Pair checks for under-constrained poses are provisional.</p>
<p><a href="assembly.json">Full residuals, motion modes, provenance, and recompute state</a></p></html>"""
        (output/"assembly.html").write_text(page, encoding="utf-8")
        self._emit({"report": str(output/"assembly.html")})

    def do_export(self, arg):
        """export PATH [--overwrite]: write current fully constrained, noninterfering geometry."""
        args = shlex.split(arg)
        if len(args) not in (1, 2) or (len(args) == 2 and args[1] != "--overwrite"):
            raise ValueError("usage: export PATH [--overwrite]")
        self._emit(self._session().export_step(Path(args[0]), overwrite=len(args) == 2))

    def do_quit(self, arg):
        """quit: leave the assembly workspace."""
        return True

    do_EOF = do_quit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("output/assembly-workspace"))
    parser.add_argument("--script", type=Path)
    args = parser.parse_args()
    shell = AssemblyShell(args.output_dir)
    if args.script:
        for line in args.script.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if shell.onecmd(line):
                break
            if shell.errors:
                return 1
    else:
        shell.cmdloop()
    return 1 if shell.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
