"""Fixed-corpus parser/importer/geometry comparison with layer-specific claims."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path
import subprocess
import sys

from research_notes.robustness_studies import ROOT, evidence_bytes
from research_notes.step_parser_comparison import external_parser_definitions, verify_external_parser_checkout

CORPUS = (
    ("named_box", "step-round-trip-preservation/named_colored_box_source.step", True, None, "accept"),
    ("named_hole", "step-round-trip-preservation/named_colored_through_hole_source.step", True, None, "accept"),
    ("freeform_shell", "step-round-trip-preservation/named_colored_bspline_source.step", True, None, "accept"),
    ("public_assembly", "public-step-corpus/sources/cadquery_assembly.step", True, None, "accept"),
    ("public_bracket", "public-step-corpus/sources/build123d_bracket.step", True, None, "accept"),
    ("sam_ap203", "public-step-corpus/sources/ublox_sam_ap203.step", True, None, "accept"),
    ("sam_ap214", "public-step-corpus/sources/ublox_sam_ap214.step", True, None, "accept"),
    ("invalid_exponent", "step-part21-conformance/invalid_real_exponent.step", False, None, "reject"),
    ("edition3_anchor", "step-part21-conformance/edition3_anchor.step", False, None, "accept"),
    ("schema_valid", "step-express-validation/scalar_types.step", False, "step-express-validation/scalar_types.exp", "accept"),
    ("schema_invalid", "step-express-validation/wrong_scalar_type.step", False, "step-express-validation/wrong_scalar_type.exp", "accept"),
)


def observe_route(route, path, *, parser_root=None, timeout=30.):
    arguments = [sys.executable, "-m", "research_notes.interoperability_worker", route, str(path)]
    if parser_root:
        arguments.append(str(parser_root))
    try:
        process = subprocess.run(arguments, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return {"outcome": "error", "diagnostic_class": "timeout"}
    lines = [line for line in process.stdout.splitlines() if line.startswith("INTEROP_RESULT=")]
    if process.returncode or len(lines) != 1:
        return {"outcome": "error", "diagnostic_class": "adapter_process_failure", "return_code": process.returncode}
    return json.loads(lines[0].partition("=")[2])


def compare_geometry(first, second):
    """Declared dimensional invariants only; no universal shape equivalence."""
    if first.get("outcome") != "accept" or second.get("outcome") != "accept":
        return {"status": "not_comparable"}
    a, b = first["metrics"], second["metrics"]
    topology = all(a[key] == b[key] for key in ("vertex_count", "edge_count", "face_count", "shell_count", "solid_count"))
    volume = abs(a["absolute_volume"] - b["absolute_volume"])
    area = abs(a["surface_area"] - b["surface_area"])
    bounds = max(abs(x - y) for key in ("bounds_min", "bounds_max") for x, y in zip(a[key], b[key]))
    tolerance_drift = {key: b[key] - a[key] for key in ("maximum_vertex_tolerance", "maximum_edge_tolerance", "maximum_face_tolerance")}
    agrees = topology and volume <= max(1e-6, a["absolute_volume"] * 1e-6) and area <= max(1e-6, a["surface_area"] * 1e-6) and bounds <= 1e-4
    return {"status": "agree_invariants" if agrees else "disagree", "topology_counts_equal": topology,
            "volume_error_mm3": volume, "area_error_mm2": area, "bounds_error_mm": bounds, "tolerance_drift": tolerance_drift,
            "independence": "same_OCCT_kernel_different_transfer_interfaces"}


def evaluate_interoperability(*, external_root=None):
    from research_notes.step_part21 import parse_part21_document, Part21ParseError
    from research_notes.step_express_validation import inspect_step_express_validation
    from research_notes.portable_step import inspect_step_semantics
    external_root = Path(external_root or ROOT / "external")
    parsers = external_parser_definitions(external_root / "steputils", external_root / "ifcopenshell_step_file_parser")
    pins = {}
    for parser in parsers:
        commit = verify_external_parser_checkout(parser)
        dirty = subprocess.run(["git", "-C", str(parser.root), "diff", "--exit-code", "HEAD"], capture_output=True, check=False)
        if dirty.returncode:
            raise ValueError("comparison parser has modified tracked files: " + parser.parser)
        pins[parser.parser] = {"repository": parser.repository, "commit": commit}
    rows, evidence, inputs = [], [], []
    for name, relative, geometry, schema_file, expected_syntax in CORPUS:
        path = ROOT / "fixtures" / relative
        source = path.read_bytes()
        if len(source) > 2_000_000:
            raise ValueError("benchmark source byte budget exceeded")
        digest = hashlib.sha256(source).hexdigest()
        try:
            document = parse_part21_document(source)
            builtin = {"outcome": "accept", "entity_count": len(document.entities), "schemas": document.schema_identifiers}
        except Part21ParseError as error:
            builtin = {"outcome": "reject", "diagnostic_class": error.reason_code}
        observations = {"builtin": builtin}
        for parser in parsers:
            observations[parser.parser] = observe_route(parser.parser, path, parser_root=parser.root)
        syntax_outcomes = {r["outcome"] for r in observations.values()}
        schema = asdict(inspect_step_express_validation(source, (ROOT / "fixtures" / schema_file).read_bytes())) if schema_file else None
        semantics = inspect_step_semantics(source) if builtin["outcome"] == "accept" else None
        comparison = {"status": "not_eligible"}
        if geometry:
            for route in ("stepcontrol", "stepcaf"):
                observations[route] = observe_route(route, path)
            comparison = compare_geometry(observations["stepcontrol"], observations["stepcaf"])
        errors = [route for route, value in observations.items() if value["outcome"] == "error"]
        mesh = observations.get("stepcontrol", {}).get("mesh_integral", {"status": "not_eligible"})
        if mesh["status"] == "measured":
            native = observations["stepcontrol"]["metrics"]["absolute_volume"]
            mesh["volume_relative_error_vs_gprop"] = abs(mesh["volume"] - native) / max(native, 1e-12)
            mesh["comparison"] = "within_budget" if mesh["volume_relative_error_vs_gprop"] <= .001 else "outside_budget"
            mesh["relative_volume_error_budget"] = .001
        truth = None
        if name == "named_box":
            truth = {"volume_mm3": 4. * 3. * 2., "area_mm2": 2. * (4. * 3. + 4. * 2. + 3. * 2.), "oracle": "authored_analytic_box"}
        elif name == "public_assembly":
            import math
            truth = {"volume_mm3": 1000. + 250. * math.pi, "oracle": "authored_upstream_cube_and_cylinder_dimensions"}
        truth_ok = truth is None or (observations.get("stepcontrol", {}).get("outcome") == "accept" and
            abs(observations["stepcontrol"]["metrics"]["absolute_volume"] - truth["volume_mm3"]) < 1e-6)
        if truth and "area_mm2" in truth and truth_ok:
            truth_ok = abs(observations["stepcontrol"]["metrics"]["surface_area"] - truth["area_mm2"]) < 1e-6
        attributes_ok = True
        if name == "named_box":
            attributes = observations.get("stepcaf", {}).get("attributes", {})
            attributes_ok = "Controlled Box" in attributes.get("names", ()) and any(
                max(abs(a - b) for a, b in zip(color, (.85, .15, .10))) < 1e-6 for color in attributes.get("colors", ()))
        external_expected = ("accept", "reject") if name == "invalid_exponent" else ("reject", "reject") if name == "edition3_anchor" else ("accept", "accept")
        external_ok = tuple(observations[parser.parser]["outcome"] for parser in parsers) == external_expected
        schema_ok = schema is None or schema["decision"] == ("accept" if name == "schema_valid" else "reject")
        row = {"control_id": name, "source_sha256": digest, "builtin": builtin["outcome"],
               "steputils": observations["steputils"]["outcome"], "ifcopenshell_parser": observations["ifcopenshell_step_file_parser"]["outcome"],
               "syntax_comparison": "agree" if len(syntax_outcomes) == 1 else "disagree",
               "schema": schema["decision"] if schema else "not_supplied",
               "semantics": semantics["status"] if semantics else "not_reached",
               "geometry_comparison": comparison["status"],
               "attribute_comparison": "capability_gap" if geometry else "not_eligible",
               "mesh_integral": mesh["status"],
               "mesh_comparison": mesh.get("comparison", "not_eligible"),
               "checks_pass": not errors and external_ok and attributes_ok and builtin["outcome"] == expected_syntax and schema_ok and truth_ok and
                   mesh.get("comparison", "within_budget") == "within_budget" and (not geometry or comparison["status"] == "agree_invariants")}
        rows.append(row)
        evidence.append({"control_id": name, "source_sha256": digest, "routes": observations,
                         "schema_validation": schema, "application_semantics": semantics,
                         "geometry_comparison": comparison, "analytic_truth": truth,
                         "adjudication": "declared fixture contracts and analytic truth where supplied; never majority vote"})
        inputs.append({"control_id": name, "path": relative, "sha256": digest, "bytes": len(source),
                       "native_geometry_eligible": geometry, "schema_path": schema_file,
                       "schema_sha256": hashlib.sha256((ROOT / "fixtures" / schema_file).read_bytes()).hexdigest() if schema_file else None,
                       "expected_builtin_syntax": expected_syntax, "expected_external_syntax": external_expected})
    environment = {"python": platform.python_version(), "platform": platform.system(), "release": platform.release(),
        "machine": platform.machine(), "packages": {name: importlib.metadata.version(name) for name in ("cadquery-ocp", "numpy", "lark-parser", "pyparsing", "antlr4-python3-runtime")},
        "external_parsers": pins, "scope": "one recorded environment; no cross-platform guarantee"}
    return rows, evidence, {"corpus": inputs, "parser_pins": pins}, environment
