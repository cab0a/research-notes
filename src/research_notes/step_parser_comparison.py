"""Isolated adapters for reproducible external Part 21 parser comparisons."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


STEPUTILS_REPOSITORY = "https://github.com/mozman/steputils.git"
STEPUTILS_COMMIT = "547860b349a36cf24c564d6c87ffd8f60484f6fb"
IFCOPENSHELL_PARSER_REPOSITORY = (
    "https://github.com/IfcOpenShell/step-file-parser.git"
)
IFCOPENSHELL_PARSER_COMMIT = "9400d243d880dace57490949d74ab1932ce99a09"


@dataclass(frozen=True)
class ExternalPart21Parser:
    """One pinned public parser checkout used as a comparison point."""

    parser: Literal["steputils", "ifcopenshell_step_file_parser"]
    repository: str
    expected_commit: str
    root: Path


@dataclass(frozen=True)
class ExternalParserObservation:
    """One isolated process outcome without normalizing parser semantics."""

    parser: str
    outcome: Literal["accept", "reject", "error", "not_run"]
    return_code: int | None
    diagnostic_class: str


def verify_external_parser_checkout(parser: ExternalPart21Parser) -> str:
    """Return the checkout commit and fail if it differs from the pin."""
    if not isinstance(parser, ExternalPart21Parser):
        raise TypeError("parser must be ExternalPart21Parser")
    if not parser.root.is_dir():
        raise RuntimeError(f"missing external parser checkout: {parser.root}")
    completed = subprocess.run(
        ["git", "-C", str(parser.root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    commit = completed.stdout.strip()
    if completed.returncode != 0 or commit != parser.expected_commit:
        raise RuntimeError(
            f"{parser.parser} checkout must be {parser.expected_commit}"
        )
    return commit


def observe_external_parser(
    parser: ExternalPart21Parser,
    fixture_path: Path,
    *,
    timeout_seconds: float = 10.0,
) -> ExternalParserObservation:
    """Run one parser in a child process and retain its coarse outcome."""
    verify_external_parser_checkout(parser)
    if not fixture_path.is_file():
        raise RuntimeError(f"missing fixture: {fixture_path}")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    if parser.parser == "steputils":
        code = (
            "import sys\n"
            "from steputils import p21\n"
            "try:\n"
            "    p21.readfile(sys.argv[1])\n"
            "except Exception as error:\n"
            "    print(type(error).__name__, file=sys.stderr)\n"
            "    raise SystemExit(1)\n"
        )
        extra_path = parser.root / "src"
    elif parser.parser == "ifcopenshell_step_file_parser":
        code = (
            "import importlib.util\n"
            "import pathlib\n"
            "import sys\n"
            "root = pathlib.Path(sys.argv[1])\n"
            "spec = importlib.util.spec_from_file_location(\n"
            "    'ifcopenshell_step_file_parser',\n"
            "    root / '__init__.py',\n"
            "    submodule_search_locations=[str(root)],\n"
            ")\n"
            "module = importlib.util.module_from_spec(spec)\n"
            "sys.modules[spec.name] = module\n"
            "spec.loader.exec_module(module)\n"
            "try:\n"
            "    module.parse(filename=sys.argv[2], with_tree=False)\n"
            "except Exception as error:\n"
            "    print(type(error).__name__, file=sys.stderr)\n"
            "    raise SystemExit(1)\n"
        )
        extra_path = parser.root.parent
    else:  # pragma: no cover - guarded by the dataclass Literal
        raise ValueError(f"unknown parser: {parser.parser}")

    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(
        part
        for part in (str(extra_path), environment.get("PYTHONPATH", ""))
        if part
    )
    arguments = [sys.executable, "-c", code]
    if parser.parser == "ifcopenshell_step_file_parser":
        arguments.append(str(parser.root))
    arguments.append(str(fixture_path))
    try:
        completed = subprocess.run(
            arguments,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=environment,
        )
    except subprocess.TimeoutExpired:
        return ExternalParserObservation(
            parser.parser, "error", None, "TimeoutExpired"
        )
    diagnostic = _last_nonempty_line(completed.stderr, completed.stdout)
    if completed.returncode == 0:
        outcome: Literal["accept", "reject", "error", "not_run"] = "accept"
    elif completed.returncode == 1:
        outcome = "reject"
    else:
        outcome = "error"
    return ExternalParserObservation(
        parser.parser,
        outcome,
        completed.returncode,
        diagnostic,
    )


def external_parser_definitions(
    steputils_root: Path,
    ifcopenshell_parser_root: Path,
) -> tuple[ExternalPart21Parser, ...]:
    """Return the two pinned parser definitions in stable order."""
    return (
        ExternalPart21Parser(
            "steputils", STEPUTILS_REPOSITORY, STEPUTILS_COMMIT, steputils_root
        ),
        ExternalPart21Parser(
            "ifcopenshell_step_file_parser",
            IFCOPENSHELL_PARSER_REPOSITORY,
            IFCOPENSHELL_PARSER_COMMIT,
            ifcopenshell_parser_root,
        ),
    )


def _last_nonempty_line(*streams: str) -> str:
    for stream in streams:
        lines = [line.strip() for line in stream.splitlines() if line.strip()]
        if lines:
            return lines[-1][:160]
    return "none"
