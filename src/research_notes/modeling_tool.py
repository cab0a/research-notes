"""Terminal modeling workspace: python -m research_notes.modeling_tool."""

from __future__ import annotations

import argparse
import cmd
import json
import shlex
from pathlib import Path

from research_notes.assisted_modeling import ModelingSession


class ModelingShell(cmd.Cmd):
    intro = "Research modeling workspace. Type help for commands; inferred proposals require select N --confirm."
    prompt = "model> "

    def __init__(self, output_dir: Path, **kwargs):
        super().__init__(**kwargs)
        self.session = ModelingSession()
        self.output_dir = output_dir
        self.errors = 0

    def _emit(self, value: object) -> None:
        self.stdout.write(json.dumps(value, indent=2, sort_keys=True) + "\n")

    def onecmd(self, line: str) -> bool:
        try:
            return super().onecmd(line)
        except (ValueError, RuntimeError, OSError, KeyError) as exc:
            self.errors += 1
            self._emit({"error": str(exc)})
            return False

    def emptyline(self) -> None:
        pass

    def default(self, line: str) -> None:
        raise ValueError("unknown command; type help")

    def do_open(self, arg: str) -> None:
        """open PATH: inspect one local millimetre STEP file."""
        args = shlex.split(arg)
        if len(args) != 1:
            raise ValueError("usage: open PATH")
        report = self.session.open_step(Path(args[0]))
        self._emit({key: report[key] for key in ("file_name", "source_sha256", "status", "reason", "metrics")})
        self.do_candidates("")

    def do_inspect(self, arg: str) -> None:
        """inspect: show source geometry and evidence for every proposal."""
        self._emit(self.session.inspect())

    def do_candidates(self, arg: str) -> None:
        """candidates: list hypotheses, fit residuals, and editable dimensions."""
        report = self.session.inspect()
        self._emit([{"number": index, **{key: candidate[key] for key in (
            "candidate_id", "explanation", "fit_score", "confidence_kind", "status",
            "volume_residual", "area_residual", "material_difference_volume",
        )}, "nodes": candidate["model"]["nodes"]} for index, candidate in enumerate(report["candidates"], start=1)])

    def do_select(self, arg: str) -> None:
        """select NUMBER_OR_ID --confirm: explicitly adopt one inferred proposal."""
        args = shlex.split(arg)
        if not 1 <= len(args) <= 2 or (len(args) == 2 and args[1] != "--confirm"):
            raise ValueError("usage: select NUMBER_OR_ID --confirm")
        identifier = args[0]
        if identifier.isdecimal():
            candidates = self.session.inspect()["candidates"]
            index = int(identifier) - 1
            if not 0 <= index < len(candidates):
                raise ValueError("candidate number is out of range")
            identifier = candidates[index]["candidate_id"]
        self.session.select_candidate(identifier, confirm=len(args) == 2)
        self._emit({"selected_candidate_id": identifier, "selection_confirmed": True})

    def do_set(self, arg: str) -> None:
        """set NODE PARAMETER VALUE: change one millimetre dimension; recompute next."""
        args = shlex.split(arg)
        if len(args) != 3:
            raise ValueError("usage: set NODE PARAMETER VALUE")
        model = self.session.edit(args[0], args[1], float(args[2]))
        self._emit({"revision": model.revision, "recompute_required": True})

    def do_recompute(self, arg: str) -> None:
        """recompute: evaluate changed dependencies and expose failed/stale nodes."""
        result = self.session.recompute()
        self._emit({"revision": result.revision, "evaluated": result.evaluated_nodes,
                    "reused": result.reused_nodes, "states": {s.node_id: s.status for s in result.states}})

    def do_compare(self, arg: str) -> None:
        """compare: save before/after measurements and a visual comparison report."""
        report = self.session.write_comparison(self.output_dir)
        self._emit({"volume_change": report["volume_change"], "surface_area_change": report["surface_area_change"],
                    "report": str(self.output_dir / "comparison.html")})

    def do_export(self, arg: str) -> None:
        """export PATH [--overwrite]: verify and write current STEP; source is protected."""
        args = shlex.split(arg)
        if not 1 <= len(args) <= 2 or (len(args) == 2 and args[1] != "--overwrite"):
            raise ValueError("usage: export PATH [--overwrite]")
        self._emit(self.session.export_step(Path(args[0]), overwrite=len(args) == 2))

    def do_status(self, arg: str) -> None:
        """status: show selected model, dimensions, and recompute state."""
        self._emit(self.session.status())

    def do_quit(self, arg: str) -> bool:
        """quit: leave the workspace."""
        return True

    do_EOF = do_quit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--script", type=Path, help="run explicit commands from a UTF-8 text file")
    parser.add_argument("--output-dir", type=Path, default=Path("output/modeling-workspace"))
    args = parser.parse_args()
    shell = ModelingShell(args.output_dir)
    if args.script:
        for line in args.script.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if shell.onecmd(line):
                break
            if shell.errors:
                return 1  # Scripts fail closed instead of exporting after an error.
    else:
        shell.cmdloop()
    return 1 if shell.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
