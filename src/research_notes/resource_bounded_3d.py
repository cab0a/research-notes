"""Stage resource-bounded STEP and controlled ZIP-container intake."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import time
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Literal


CONTRACT_VERSION = "1.0.0"
Decision = Literal["accept", "quarantine", "reject"]
StageDecision = Literal[
    "continue", "accept", "quarantine", "reject", "timeout", "not_run"
]
STAGES = ("preflight", "parser", "external_policy", "kernel", "tessellation")


@dataclass(frozen=True)
class IntakeLimits:
    """Explicit file, syntax, archive, topology, mesh, and time budgets."""

    max_file_bytes: int = 2_000_000
    max_tokens: int = 250_000
    max_entities: int = 20_000
    max_references: int = 100_000
    max_nesting_depth: int = 32
    max_token_chars: int = 16_384
    max_archive_members: int = 4
    max_archive_expanded_bytes: int = 3_000_000
    max_archive_depth: int = 0
    max_edges: int = 5_000
    max_faces: int = 1_000
    max_triangles: int = 100_000
    parser_timeout_seconds: float = 5.0
    kernel_timeout_seconds: float = 10.0
    mesh_linear_deflection: float = 0.25
    mesh_angular_deflection: float = 0.5
    allow_external_references: bool = False

    def __post_init__(self) -> None:
        for name, value in vars(self).items():
            if name == "allow_external_references":
                continue
            if value <= 0 and name != "max_archive_depth":
                raise ValueError(f"{name} must be positive")
            if name == "max_archive_depth" and value < 0:
                raise ValueError("max_archive_depth must be non-negative")


@dataclass(frozen=True)
class IntakeFixture:
    """One deterministic raw STEP or controlled ZIP-container input."""

    file_name: str
    source_bytes: bytes
    source_sha256: str
    format: Literal["step", "stpz"]


@dataclass(frozen=True)
class IntakeControl:
    """One input, budget set, and declared expected terminal decision."""

    control_id: str
    file_name: str
    condition: str
    expected_decision: Decision
    expected_reason_code: str
    limits: IntakeLimits
    kernel_delay_seconds: float = 0.0


@dataclass(frozen=True)
class IntakeStageObservation:
    """One stage-local decision without machine-dependent duration fields."""

    control_id: str
    stage: str
    decision: StageDecision
    reason_code: str
    observed_value: int | None
    limit_value: int | float | None
    worker_isolated: bool


@dataclass(frozen=True)
class IntakeResult:
    """One terminal intake decision and bounded admitted measurements."""

    control_id: str
    input_sha256: str
    payload_sha256: str | None
    decision: Decision
    reason_code: str
    terminal_stage: str
    expectation_met: bool
    token_count: int | None
    entity_count: int | None
    reference_count: int | None
    external_reference_count: int | None
    edge_count: int | None
    face_count: int | None
    triangle_count: int | None


@dataclass(frozen=True)
class IntakeProbe:
    """Complete v0.50.0 resource-bounded 3D intake evidence."""

    fixtures: tuple[IntakeFixture, ...]
    controls: tuple[IntakeControl, ...]
    stages: tuple[IntakeStageObservation, ...]
    results: tuple[IntakeResult, ...]
    preview_shapes: tuple[tuple[str, object], ...]


def _zip_bytes(entries: tuple[tuple[str, bytes], ...]) -> bytes:
    import io

    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, payload in entries:
            info = zipfile.ZipInfo(name, date_time=(2000, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, payload)
    return stream.getvalue()


def _external_reference_bytes() -> bytes:
    return (
        "ISO-10303-21;\n"
        "HEADER;\n"
        "FILE_DESCRIPTION(('External reference control'),'3;1');\n"
        "FILE_NAME('external_reference.step','2000-01-01T00:00:00',('research-notes'),('research-notes'),'','','');\n"
        "FILE_SCHEMA(('CONTROL_SCHEMA'));\n"
        "ENDSEC;\n"
        "REFERENCE;\n"
        "#10=<https://example.invalid/part.step#shape>;\n"
        "ENDSEC;\n"
        "DATA;\n"
        "#1=USE(#10);\n"
        "ENDSEC;\n"
        "END-ISO-10303-21;\n"
    ).encode("ascii")


def build_intake_fixture_bytes(source_fixture_dir: Path) -> dict[str, bytes]:
    """Build fixed raw and archive samples from committed synthetic STEP files."""
    box = (source_fixture_dir / "named_colored_box_source.step").read_bytes()
    through_hole = (
        source_fixture_dir / "named_colored_through_hole_source.step"
    ).read_bytes()
    inner = _zip_bytes((("model.step", box),))
    return {
        "box.step": box,
        "through_hole.step": through_hole,
        "external_reference.step": _external_reference_bytes(),
        "accepted_archive.stpz": _zip_bytes((("model.step", box),)),
        "expanded_limit.stpz": _zip_bytes(
            (("model.step", box), ("padding.bin", b"A" * 20_000))
        ),
        "nested_archive.stpz": _zip_bytes((("nested.stpz", inner),)),
        "unsafe_member.stpz": _zip_bytes((("../model.step", box),)),
    }


def load_intake_fixtures(fixture_dir: Path) -> tuple[IntakeFixture, ...]:
    """Load every committed input in stable file-name order."""
    fixtures = []
    for path in sorted(item for item in fixture_dir.iterdir() if item.name != "manifest.csv"):
        payload = path.read_bytes()
        fixtures.append(
            IntakeFixture(
                path.name,
                payload,
                hashlib.sha256(payload).hexdigest(),
                "stpz" if path.suffix == ".stpz" else "step",
            )
        )
    return tuple(fixtures)


def intake_controls() -> tuple[IntakeControl, ...]:
    """Return boundary controls with one changed resource policy at a time."""
    default = IntakeLimits()
    return (
        IntakeControl("accepted_step", "box.step", "raw STEP within every budget", "accept", "intake_accepted", default),
        IntakeControl("file_byte_limit", "box.step", "container bytes exceed preflight budget", "reject", "file_byte_limit", IntakeLimits(max_file_bytes=100)),
        IntakeControl("token_limit", "box.step", "tokens exceed parser budget", "quarantine", "token_count_limit", IntakeLimits(max_tokens=100)),
        IntakeControl("entity_limit", "box.step", "entities exceed parser budget", "quarantine", "entity_count_limit", IntakeLimits(max_entities=100)),
        IntakeControl("reference_limit", "box.step", "references exceed parser budget", "quarantine", "reference_count_limit", IntakeLimits(max_references=100)),
        IntakeControl("external_reference_disabled", "external_reference.step", "syntax is accepted but retrieval is disabled", "quarantine", "external_resolution_disabled", default),
        IntakeControl("accepted_archive", "accepted_archive.stpz", "one safe STEP member within expansion budget", "accept", "intake_accepted", default),
        IntakeControl("archive_expanded_limit", "expanded_limit.stpz", "declared expanded bytes exceed budget", "reject", "archive_expanded_byte_limit", IntakeLimits(max_archive_expanded_bytes=10_000)),
        IntakeControl("nested_archive", "nested_archive.stpz", "nested archive exceeds allowed depth", "reject", "archive_depth_limit", default),
        IntakeControl("unsafe_archive_path", "unsafe_member.stpz", "member path escapes logical archive root", "reject", "unsafe_archive_member_path", default),
        IntakeControl("topology_face_limit", "box.step", "transferred face count exceeds budget", "reject", "topology_face_limit", IntakeLimits(max_faces=5)),
        IntakeControl("mesh_triangle_limit", "through_hole.step", "generated triangles exceed budget", "reject", "mesh_triangle_limit", IntakeLimits(max_triangles=10)),
        IntakeControl("kernel_timeout", "box.step", "isolated kernel worker exceeds wall-clock budget", "quarantine", "kernel_timeout", IntakeLimits(kernel_timeout_seconds=0.1), 0.5),
    )


def _not_run(control_id: str, stage: str) -> IntakeStageObservation:
    return IntakeStageObservation(control_id, stage, "not_run", "earlier_stage_stopped", None, None, False)


def _unsafe_member(name: str) -> bool:
    path = PurePosixPath(name.replace("\\", "/"))
    return path.is_absolute() or ".." in path.parts


def _preflight(path: Path, limits: IntakeLimits) -> tuple[IntakeStageObservation, bytes | None]:
    size = path.stat().st_size
    if size > limits.max_file_bytes:
        return IntakeStageObservation("", "preflight", "reject", "file_byte_limit", size, limits.max_file_bytes, False), None
    if path.suffix != ".stpz":
        payload = path.read_bytes()
        return IntakeStageObservation("", "preflight", "continue", "raw_step_admitted", size, limits.max_file_bytes, False), payload
    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            if len(members) > limits.max_archive_members:
                return IntakeStageObservation("", "preflight", "reject", "archive_member_limit", len(members), limits.max_archive_members, False), None
            if any(_unsafe_member(item.filename) for item in members):
                return IntakeStageObservation("", "preflight", "reject", "unsafe_archive_member_path", None, None, False), None
            if limits.max_archive_depth == 0 and any(PurePosixPath(item.filename).suffix.lower() in {".zip", ".stpz"} for item in members):
                return IntakeStageObservation("", "preflight", "reject", "archive_depth_limit", 1, limits.max_archive_depth, False), None
            expanded = sum(item.file_size for item in members)
            if expanded > limits.max_archive_expanded_bytes:
                return IntakeStageObservation("", "preflight", "reject", "archive_expanded_byte_limit", expanded, limits.max_archive_expanded_bytes, False), None
            step_members = [item for item in members if PurePosixPath(item.filename).suffix.lower() in {".step", ".stp"}]
            if len(step_members) != 1:
                return IntakeStageObservation("", "preflight", "reject", "archive_step_member_count", len(step_members), 1, False), None
            payload = archive.read(step_members[0])
    except zipfile.BadZipFile:
        return IntakeStageObservation("", "preflight", "reject", "invalid_archive", None, None, False), None
    if len(payload) > limits.max_file_bytes:
        return IntakeStageObservation("", "preflight", "reject", "expanded_step_byte_limit", len(payload), limits.max_file_bytes, False), None
    return IntakeStageObservation("", "preflight", "continue", "archive_admitted", expanded, limits.max_archive_expanded_bytes, False), payload


def _run_worker(stage: str, source_path: Path, limits: IntakeLimits, delay: float, timeout: float, root: Path) -> tuple[dict[str, object] | None, bool]:
    config_path = root / f"{stage}_config.json"
    result_path = root / f"{stage}_result.json"
    config_path.write_text(json.dumps({"limits": asdict(limits), "delay": delay}), encoding="utf-8")
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "research_notes.resource_bounded_3d", "--worker", stage, str(source_path), str(config_path), str(result_path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None, True
    if completed.returncode != 0 or not result_path.is_file():
        return {"decision": "quarantine", "reason_code": f"{stage}_worker_error"}, False
    return json.loads(result_path.read_text(encoding="utf-8")), False


def _fill_after(stages: list[IntakeStageObservation], control_id: str, terminal_stage: str) -> None:
    terminal_index = STAGES.index(terminal_stage)
    observed = {item.stage for item in stages}
    for stage in STAGES[terminal_index + 1 :]:
        if stage not in observed:
            stages.append(_not_run(control_id, stage))


def probe_resource_bounded_3d(fixture_dir: Path) -> IntakeProbe:
    """Evaluate all controls through isolated syntax and native-code stages."""
    fixtures = load_intake_fixtures(fixture_dir)
    fixture_by_name = {item.file_name: item for item in fixtures}
    controls = intake_controls()
    all_stages: list[IntakeStageObservation] = []
    results: list[IntakeResult] = []
    preview_shapes: list[tuple[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="research-notes-intake-") as directory:
        root = Path(directory)
        for control in controls:
            fixture = fixture_by_name[control.file_name]
            path = fixture_dir / fixture.file_name
            stages: list[IntakeStageObservation] = []
            preflight, payload = _preflight(path, control.limits)
            preflight = IntakeStageObservation(control.control_id, preflight.stage, preflight.decision, preflight.reason_code, preflight.observed_value, preflight.limit_value, False)
            stages.append(preflight)
            values: dict[str, int | None] = {name: None for name in ("token_count", "entity_count", "reference_count", "external_reference_count", "edge_count", "face_count", "triangle_count")}
            payload_sha = None if payload is None else hashlib.sha256(payload).hexdigest()
            terminal_stage = "preflight"
            decision: Decision = "reject"
            reason = preflight.reason_code
            if payload is not None:
                payload_path = root / f"{control.control_id}.step"
                payload_path.write_bytes(payload)
                parsed, timed_out = _run_worker("parser", payload_path, control.limits, 0.0, control.limits.parser_timeout_seconds, root)
                if timed_out:
                    stages.append(IntakeStageObservation(control.control_id, "parser", "timeout", "parser_timeout", None, control.limits.parser_timeout_seconds, True))
                    decision, reason, terminal_stage = "quarantine", "parser_timeout", "parser"
                else:
                    assert parsed is not None
                    for name in ("token_count", "entity_count", "reference_count", "external_reference_count"):
                        value = parsed.get(name)
                        values[name] = value if isinstance(value, int) else None
                    parser_decision = str(parsed["decision"])
                    stages.append(IntakeStageObservation(control.control_id, "parser", parser_decision if parser_decision != "accept" else "continue", str(parsed["reason_code"]), parsed.get("observed_value") if isinstance(parsed.get("observed_value"), int) else values["token_count"], parsed.get("limit_value") if isinstance(parsed.get("limit_value"), (int, float)) else control.limits.max_tokens, True))
                    if parser_decision != "accept":
                        decision = "quarantine" if parser_decision == "quarantine" else "reject"
                        reason, terminal_stage = str(parsed["reason_code"]), "parser"
                    elif values["external_reference_count"] and not control.limits.allow_external_references:
                        stages.append(IntakeStageObservation(control.control_id, "external_policy", "quarantine", "external_resolution_disabled", values["external_reference_count"], 0, False))
                        decision, reason, terminal_stage = "quarantine", "external_resolution_disabled", "external_policy"
                    else:
                        stages.append(IntakeStageObservation(control.control_id, "external_policy", "continue", "external_policy_admitted", values["external_reference_count"], 0, False))
                        native, timed_out = _run_worker("kernel", payload_path, control.limits, control.kernel_delay_seconds, control.limits.kernel_timeout_seconds, root)
                        if timed_out:
                            stages.append(IntakeStageObservation(control.control_id, "kernel", "timeout", "kernel_timeout", None, control.limits.kernel_timeout_seconds, True))
                            decision, reason, terminal_stage = "quarantine", "kernel_timeout", "kernel"
                        else:
                            assert native is not None
                            for name in ("edge_count", "face_count", "triangle_count"):
                                value = native.get(name)
                                values[name] = value if isinstance(value, int) else None
                            kernel_decision = str(native["kernel_decision"])
                            stages.append(IntakeStageObservation(control.control_id, "kernel", kernel_decision if kernel_decision != "accept" else "continue", str(native["kernel_reason"]), values["face_count"], control.limits.max_faces, True))
                            if kernel_decision != "accept":
                                decision, reason, terminal_stage = "reject", str(native["kernel_reason"]), "kernel"
                            else:
                                mesh_decision = str(native["mesh_decision"])
                                stages.append(IntakeStageObservation(control.control_id, "tessellation", mesh_decision, str(native["mesh_reason"]), values["triangle_count"], control.limits.max_triangles, True))
                                terminal_stage = "tessellation"
                                if mesh_decision == "accept":
                                    decision, reason = "accept", "intake_accepted"
                                else:
                                    decision, reason = "reject", str(native["mesh_reason"])
            _fill_after(stages, control.control_id, terminal_stage)
            stage_order = {name: index for index, name in enumerate(STAGES)}
            stages.sort(key=lambda item: stage_order[item.stage])
            all_stages.extend(stages)
            results.append(IntakeResult(control.control_id, fixture.source_sha256, payload_sha, decision, reason, terminal_stage, decision == control.expected_decision and reason == control.expected_reason_code, **values))

        for file_name, label in (("box.step", "accepted box"), ("through_hole.step", "mesh-budget through hole")):
            native_path = fixture_dir / file_name
            from OCP.IFSelect import IFSelect_RetDone
            from OCP.STEPControl import STEPControl_Reader
            reader = STEPControl_Reader()
            if reader.ReadFile(str(native_path)) == IFSelect_RetDone and int(reader.TransferRoots()) > 0:
                preview_shapes.append((label, reader.OneShape()))
    return IntakeProbe(fixtures, controls, tuple(all_stages), tuple(results), tuple(preview_shapes))


def _parser_worker(path: Path, limits: IntakeLimits) -> dict[str, object]:
    from research_notes.step_part21 import Part21ParseError, STEPParseLimits, parse_part21_document

    source = path.read_bytes()
    parser_limits = STEPParseLimits(limits.max_file_bytes, limits.max_tokens, limits.max_entities, limits.max_references, limits.max_nesting_depth, limits.max_token_chars)
    try:
        document = parse_part21_document(source, limits=parser_limits)
    except Part21ParseError as error:
        limit_map = {"token_count_limit": limits.max_tokens, "entity_count_limit": limits.max_entities, "reference_count_limit": limits.max_references, "nesting_depth_limit": limits.max_nesting_depth, "token_length_limit": limits.max_token_chars, "file_byte_limit": limits.max_file_bytes}
        return {"decision": error.decision, "reason_code": error.reason_code, "observed_value": None, "limit_value": limit_map.get(error.reason_code)}
    return {"decision": "accept", "reason_code": "part21_parsed", "token_count": len(document.tokens), "entity_count": len(document.entities), "reference_count": document.reference_count, "external_reference_count": len(document.external_references)}


def _kernel_worker(path: Path, limits: IntakeLimits, delay: float) -> dict[str, object]:
    if delay:
        time.sleep(delay)
    from OCP.BRep import BRep_Tool
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.BRepTools import BRepTools
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS
    from research_notes.brep_runtime import indexed_shapes

    reader = STEPControl_Reader()
    if reader.ReadFile(str(path)) != IFSelect_RetDone or int(reader.TransferRoots()) < 1:
        return {"kernel_decision": "reject", "kernel_reason": "kernel_transfer_failed", "mesh_decision": "not_run", "mesh_reason": "kernel_transfer_failed"}
    shape = reader.OneShape()
    edges = indexed_shapes(shape, TopAbs_EDGE).Extent()
    faces = indexed_shapes(shape, TopAbs_FACE)
    face_count = faces.Extent()
    base = {"edge_count": int(edges), "face_count": int(face_count)}
    if edges > limits.max_edges:
        return {**base, "kernel_decision": "reject", "kernel_reason": "topology_edge_limit", "mesh_decision": "not_run", "mesh_reason": "topology_edge_limit"}
    if face_count > limits.max_faces:
        return {**base, "kernel_decision": "reject", "kernel_reason": "topology_face_limit", "mesh_decision": "not_run", "mesh_reason": "topology_face_limit"}
    BRepTools.Clean_s(shape, True)
    mesher = BRepMesh_IncrementalMesh(shape, limits.mesh_linear_deflection, False, limits.mesh_angular_deflection, False)
    if not mesher.IsDone():
        return {**base, "kernel_decision": "accept", "kernel_reason": "topology_admitted", "mesh_decision": "reject", "mesh_reason": "meshing_failed"}
    triangles = 0
    for index in range(1, face_count + 1):
        triangulation = BRep_Tool.Triangulation_s(TopoDS.Face_s(faces.FindKey(index)), TopLoc_Location())
        if triangulation is not None:
            triangles += int(triangulation.NbTriangles())
    return {**base, "triangle_count": triangles, "kernel_decision": "accept", "kernel_reason": "topology_admitted", "mesh_decision": "accept" if triangles <= limits.max_triangles else "reject", "mesh_reason": "mesh_admitted" if triangles <= limits.max_triangles else "mesh_triangle_limit"}


def _worker_entry(arguments: list[str]) -> int:
    if len(arguments) != 5 or arguments[0] != "--worker":
        return 2
    _, stage, source_name, config_name, result_name = arguments
    config = json.loads(Path(config_name).read_text(encoding="utf-8"))
    limits = IntakeLimits(**config["limits"])
    if stage == "parser":
        result = _parser_worker(Path(source_name), limits)
    elif stage == "kernel":
        result = _kernel_worker(Path(source_name), limits, float(config["delay"]))
    else:
        return 2
    Path(result_name).write_text(json.dumps(result, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(_worker_entry(sys.argv[1:]))
