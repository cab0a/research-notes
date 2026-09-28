"""Transactional terminal for the stable bounded Python CAD API."""
from __future__ import annotations

import argparse
import cmd
import json
from pathlib import Path
import shlex

from research_notes.cad_api import CadWorkspace, CadAPIError


class CadShell(cmd.Cmd):
    prompt = "cad> "
    intro = "Transactional CAD workspace v1.0 · API 1.0. Type help for commands."

    def __init__(self, output_dir, **kwargs):
        super().__init__(**kwargs)
        self.workspace = CadWorkspace()
        self.output_dir, self.errors = Path(output_dir), 0

    def _emit(self, result):
        self.stdout.write(json.dumps(result.record() if hasattr(result, "record") else result, indent=2, sort_keys=True) + "\n")

    def onecmd(self, line):
        try:
            return super().onecmd(line)
        except (CadAPIError, ValueError, OSError) as error:
            self.errors += 1
            self._emit(error.record() if isinstance(error, CadAPIError) else {"status": "error", "detail": str(error)})
            return False

    def emptyline(self):
        pass

    def default(self, line):
        raise ValueError("unknown command; type help")

    def do_open(self, arg):
        """open PATH [--inspect-only]: import immutable source; preserve current state on failure."""
        args = shlex.split(arg)
        if len(args) not in (1, 2) or len(args) == 2 and args[1] != "--inspect-only":
            raise ValueError("usage: open PATH [--inspect-only]")
        report = self.workspace.open_step(Path(args[0]), mode="inspect" if len(args) == 2 else "reconstruct")
        self._emit({"api_version": report.api_version, "status": report.status, "revision_token": report.revision_token,
                    "source": self.workspace.status().data})
        self.do_candidates("")

    def do_candidates(self, arg):
        """candidates: show reconstruction alternatives without adopting them."""
        result = self.workspace.candidates()
        self._emit({"status": result.status, "candidates": [
            {"number": i, "candidate_id": c["candidate_id"], "explanation": c["explanation"], "fit_score": c["fit_score"]}
            for i, c in enumerate(result.data["candidates"], 1)]})

    def do_select(self, arg):
        """select NUMBER_OR_ID --confirm: explicitly choose an editable reconstruction."""
        args = shlex.split(arg)
        if len(args) != 2 or args[1] != "--confirm":
            raise ValueError("usage: select NUMBER_OR_ID --confirm")
        identifier = args[0]
        if identifier.isdigit():
            candidates = self.workspace.candidates().data["candidates"]
            number = int(identifier)
            if not 1 <= number <= len(candidates):
                raise ValueError("candidate number is outside the displayed list")
            identifier = candidates[number - 1]["candidate_id"]
        self._emit(self.workspace.select(identifier, confirm=True, expected_revision=self.workspace.revision_token))

    def do_set(self, arg):
        """set NODE PARAMETER VALUE: stage a dimension; committed geometry stays available."""
        args = shlex.split(arg)
        if len(args) != 3:
            raise ValueError("usage: set NODE PARAMETER VALUE")
        self._emit(self.workspace.edit(args[0], args[1], float(args[2]), expected_revision=self.workspace.revision_token))

    def do_recompute(self, arg):
        """recompute: publish all feature nodes only if the whole candidate passes."""
        self._emit(self.workspace.recompute(expected_revision=self.workspace.revision_token))

    def do_rollback(self, arg):
        """rollback [CHECKPOINT]: restore the last committed or named checkpoint."""
        args = shlex.split(arg)
        if len(args) > 1:
            raise ValueError("usage: rollback [CHECKPOINT]")
        self._emit(self.workspace.rollback(args[0] if args else None, expected_revision=self.workspace.revision_token))

    def do_status(self, arg):
        """status: show draft, committed and last attempted states."""
        self._emit(self.workspace.status())

    def do_compare(self, arg):
        """compare: compare imported and committed geometry; pending drafts are refused."""
        self._emit(self.workspace.compare())

    def do_workspace(self, arg):
        """workspace: save an interactive, read-only diagnostic snapshot."""
        self._emit(self.workspace.workspace(self.output_dir))

    def do_export(self, arg):
        """export PATH preserve|canonical|reconstruct [--overwrite]: explicit writer policy."""
        args = shlex.split(arg)
        if len(args) not in (2, 3) or len(args) == 3 and args[2] != "--overwrite":
            raise ValueError("usage: export PATH preserve|canonical|reconstruct [--overwrite]")
        self._emit(self.workspace.export_step(Path(args[0]), mode=args[1], overwrite=len(args) == 3))

    def do_quit(self, arg):
        return True

    do_EOF = do_quit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("output/cad-workspace"))
    parser.add_argument("--script", type=Path)
    args = parser.parse_args()
    shell = CadShell(args.output_dir)
    if args.script:
        for line in args.script.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.lstrip().startswith("#"):
                if shell.onecmd(line) or shell.errors:
                    break
    else:
        shell.cmdloop()
    return int(bool(shell.errors))


if __name__ == "__main__":
    raise SystemExit(main())
