"""Observe existing SolidCraft commands on native documents, without STEP conversion.

Requires a separately obtained SolidCraft v0.15.0 CLI. No engine is vendored or
installed. These are small API observations, not a feature-recognition benchmark.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def command(command_id: str, **params: object) -> dict:
    return {"command": command_id, "params": params}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    cli = args.cli.resolve(strict=True)
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    calls: list[dict] = []

    def call(label: str, argv: list[str]) -> object:
        try:
            result = subprocess.run([str(cli), *argv], capture_output=True, text=True, timeout=45, check=False)
            row = {"label": label, "arguments": argv, "exit_code": result.returncode, "stderr": result.stderr}
            try:
                value = json.loads(result.stdout)
            except json.JSONDecodeError:
                value = result.stdout
            row["output"] = value
            row["status"] = "completed" if result.returncode == 0 else "failed"
        except subprocess.TimeoutExpired:
            value = None
            row = {"label": label, "arguments": argv, "status": "timeout"}
        calls.append(row)
        return value

    def run(label: str, steps: list[dict], native_in: Path | None = None, save: bool = False) -> object:
        script = out / f"{label}.json"
        write(script, steps)
        argv = ["run", str(script), "--results"]
        if native_in is not None:
            argv += ["--in", str(native_in)]
        if save:
            saved = out / f"{label}.solidcraft"
            saved.unlink(missing_ok=True)
            argv += ["--save", str(saved)]
        return call(label, argv)

    version = call("version", ["--version"])
    if version != "solidcraft-cli 0.15.0\n":
        raise RuntimeError(f"This probe requires SolidCraft CLI 0.15.0, got {version!r}")
    registry = call("commands", ["commands"])
    if not isinstance(registry, list):
        raise RuntimeError("Existing commands endpoint did not return a registry.")
    box = command("solid.box", length=40, width=30, height=5, body_name="Plate", name="Stock")
    inspection = [command("document.inspect"), command("model.faces", body="Plate")]
    round_steps = [box, command("solid.hole", position=[10, 10, 5], diameter=6, name="Hole_A"),
                   *inspection, command("timeline.inspect", feature="Hole_A")]
    run("round_native", round_steps, save=True)
    native = out / "round_native.solidcraft"
    if native.exists():
        run("round_reopened", [*inspection, command("timeline.inspect", feature="Hole_A")], native_in=native)

    seed_steps = [box, command("sketch.create", plane="XY", offset=5, name="SlotSketch"),
                  command("sketch.slot.center_to_center", p0=[10, 15], p1=[24, 15], width=6)]
    seed = run("slot_seed", seed_steps)
    if not (isinstance(seed, list) and len(seed) >= 2 and isinstance(seed[1], dict) and isinstance(seed[1].get("sketch"), int)):
        raise RuntimeError("Existing sketch.create did not return a sketch ID; inspect its recorded output.")
    slot_steps = [*seed_steps,
                  command("inspect.measure", items=[{"type": "profile", "sketch": seed[1]["sketch"], "index": 0}]),
                  command("sketch.finish"), command("solid.extrude", distance=5, direction="negative", operation="cut", targets=["Plate"], name="SlotCut"),
                  *inspection]
    slot_result = run("slot_native", slot_steps, save=True)
    slot_native = out / "slot_native.solidcraft"
    if slot_native.exists() and isinstance(slot_result, list):
        faces = slot_result[-1].get("faces", [])
        cylindrical = [f for f in faces if f.get("cylinder") is not None]
        if cylindrical:
            # A supplied face selection is intentional. This does not auto-enumerate slots.
            selected = cylindrical[0]
            run("slot_face_reopened", [command("inspect.measure", items=[{"type": "face", "body": "Plate", "index": selected["index"], "point": selected["point"]}]),
                                        command("timeline.inspect", feature="SlotCut")], native_in=slot_native)

    run("compare_native", [command("solid.box", length=10, width=8, height=4, body_name="Old", operation="new"),
                           command("solid.box", length=12, width=8, height=4, body_name="New", operation="new"),
                           command("inspect.compare", a="Old", b="New", tolerance=0.01, spacing=0.5, max_points=100000)])
    relevant = {"solid.hole", "timeline.inspect", "document.inspect", "model.faces", "model.threads", "inspect.measure",
                "inspect.compare", "inspect.continuity", "inspect.clearance", "inspect.draft", "inspect.minimum_radius"}
    registry_digest = hashlib.sha256(json.dumps(registry, sort_keys=True).encode()).hexdigest()
    # Keep the full registry in the working directory; commit only relevant API entries.
    write(out / "command-registry.json", registry)
    for row in calls:
        if row["label"] == "commands":
            row["output"] = {"count": len(registry), "canonical_json_sha256": registry_digest,
                             "relevant_commands": [c for c in registry if c["id"] in relevant]}
    record = {
        "schema": "native-brep-command-observations/1", "investigation_date": "2026-10-19",
        "provider": "SolidCraft", "version_output": version,
        "source_revision": "fa691707c224cae580c42201ed3a22d5e4b8c716",
        "binary_sha256": hashlib.sha256(cli.read_bytes()).hexdigest(),
        "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "command_count": len(registry) if isinstance(registry, list) else None,
        "scope": "Native authored/reopened documents; no STEP import/export; no exhaustive hole or slot inventory.",
        "native_files": [{"name": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size,
                          "members": zipfile.ZipFile(p).namelist()}
                         for p in sorted(out.glob("*.solidcraft"))],
        "calls": calls,
    }
    write(out / "observations.json", record)
    print(json.dumps({"calls": len(calls), "statuses": {s: sum(c["status"] == s for c in calls) for s in ("completed", "failed", "timeout")}}, indent=2))


if __name__ == "__main__":
    main()
