"""Selected AP role portability and explicit product representation selection."""
from __future__ import annotations

from research_notes.ap242_paths import AP242_SCHEMA_IDENTIFIER
from research_notes.portable_step import inspect_step_semantics, PROFILES
from research_notes.robustness_studies import ROOT, evidence_bytes, finish


def _fixture(directory, name):
    return (ROOT / "fixtures" / directory / (name + ".step")).read_bytes()


def _append(source, records):
    return source.replace(b"ENDSEC;\nEND-ISO-10303-21;", records.encode() + b"\nENDSEC;\nEND-ISO-10303-21;")


def _summary(name, report, passed):
    return {"control_id": name, "schema": report["schema"], "status": report["status"],
            "product_count": len(report["products"]), "representation_count": len(report["representations"]),
            "selected_count": sum(p["selected_representation_id"] is not None for p in report["products"]),
            "assembly_path_count": len(report["assembly"]["paths"]) if report["assembly"] else 0,
            "diagnostic_count": len(report["diagnostics"]), "checks_pass": bool(passed)}


def run_ap_portability(output, fixtures, *, refresh=False):
    base = _fixture("ap242-product-paths", "ap242_block_path")
    assembly = _fixture("ap242-assemblies", "single_translation")
    rows, details, payloads = [], [], {}
    for schema in PROFILES:
        if "{" in schema:
            continue  # The original CadQuery asset below exercises this exact OID spelling.
        label = {"CONFIG_CONTROL_DESIGN": "ap203", "AUTOMOTIVE_DESIGN": "ap214"}.get(schema, "ap242")
        for variant in ("product", "formation_subtype", "metre", "assembly"):
            source = (assembly if variant == "assembly" else base).replace(AP242_SCHEMA_IDENTIFIER.encode(), schema.encode())
            if variant == "formation_subtype":
                source = source.replace(b"PRODUCT_DEFINITION_FORMATION('F-001','',#3)", b"PRODUCT_DEFINITION_FORMATION_WITH_SPECIFIED_SOURCE('F-001','',#3,.MADE.)")
            if variant == "metre":
                source = source.replace(b"SI_UNIT(.MILLI.,.METRE.)", b"SI_UNIT($,.METRE.)")
            name = label + "_" + variant
            report = inspect_step_semantics(source)
            if variant == "assembly":
                ok = report["assembly"]["decision"] == "accept" if label != "ap203" else any(d["code"] == "assembly_placement_outside_profile" for d in report["diagnostics"])
            else:
                ok = len(report["products"]) == 1 and report["products"][0]["name"] == "Controlled block" and report["products"][0]["selected_representation_id"] == 20
                ok &= report["representations"][0]["mm_per_source_unit"] == (1000. if variant == "metre" else 1.)
            rows.append(_summary(name, report, ok)); details.append({"control_id": name, **report}); payloads[name + ".step"] = source
    for name, source, code in (
        ("unknown_schema", base.replace(AP242_SCHEMA_IDENTIFIER.encode(), b"AUTOMOTIVE_DESIGN_FAKE"), "unsupported_application_schema"),
        ("wrong_formation", base.replace(b"'',#4,#5", b"'',#3,#5"), "unexpected_target_type"),
        ("missing_units", base.replace(b"GLOBAL_UNIT_ASSIGNED_CONTEXT((#41,#42,#43))", b""), "global_units_not_available"),
    ):
        report = inspect_step_semantics(source)
        rows.append(_summary(name, report, any(d["code"] == code for d in report["diagnostics"])))
        details.append({"control_id": name, **report}); payloads[name + ".step"] = source
    # Original licensed bytes, not header substitutions, are the external controls.
    for filename in ("ublox_sam_ap203", "ublox_sam_ap214", "cadquery_assembly"):
        source = _fixture("public-step-corpus/sources", filename)
        report = inspect_step_semantics(source)
        ok = bool(report["products"]) and bool(report["representations"]) and report["schema"] in PROFILES
        rows.append(_summary(filename, report, ok)); details.append({"control_id": filename, **report})
    payloads["public_sources.json"] = evidence_bytes({"source": "../public-step-corpus/manifest.json", "samples": [r["control_id"] for r in rows[-3:]]})
    return finish(output, fixtures, "ap_portability", rows, details, payloads, [
        "Explicit schema identifiers enable selected attribute and reference roles; no full AP or EXPRESS conformance claim.",
        "Synthetic cross-profile controls are role probes, not certified AP documents. Original public inputs remain byte-preserved.",
        "Legacy AP203 assembly placement remains deferred. AP214/242 use the existing bounded, source-linked occurrence decoder.",
        "Names are retained source attributes, never evidence of geometric equivalence; legacy AP242 APIs remain unchanged.",
    ], refresh=refresh)


def run_complex_product_structures(output, fixtures, *, refresh=False):
    base = _fixture("ap242-product-paths", "ap242_block_path")
    alternate = _fixture("ap242-product-paths", "ap242_multiple_representations")
    related = _append(base, "#21=SHAPE_REPRESENTATION('related',(#31),#40);\n#90=SHAPE_REPRESENTATION_RELATIONSHIP('','',#20,#21);")
    cyclic = _append(related, "#22=SHAPE_REPRESENTATION('third',(#31),#40);\n#91=SHAPE_REPRESENTATION_RELATIONSHIP('','',#21,#22);\n#92=SHAPE_REPRESENTATION_RELATIONSHIP('','',#22,#20);")
    models = _append(base.replace(b"(#30,#31),#40", b"(#30,#31,#35),#40"), "#35=BLOCK('second model',#30,5.,5.,5.);")
    cases = [
        ("unique", base, None, "unique", 1),
        ("alternative", alternate, None, "ambiguous", 2),
        ("explicit_alternative", alternate, {6: 21}, "explicit", 2),
        ("related_shapes", related, None, "ambiguous", 2),
        ("explicit_related", related, {6: 21}, "explicit", 2),
        ("cyclic_relationships", cyclic, None, "ambiguous", 3),
        ("multiple_models", models, None, "unique", 1),
        ("unqualified_alternative", alternate.replace(b"#21=SHAPE_REPRESENTATION", b"#21=TESSELLATED_SHAPE_REPRESENTATION").replace(b"(#30),#40", b"(#30),#999"), None, "unresolved", 1),
    ]
    rows, details, payloads = [], [], {}
    for name, source, selections, state, count in cases:
        report = inspect_step_semantics(source, selections=selections)
        product = report["products"][0]
        ok = product["selection"] == state and len(product["candidate_ids"]) == count
        if name == "multiple_models":
            ok &= report["representations"][0]["model_ids"] == [31, 35]
        rows.append(_summary(name, report, ok)); details.append({"control_id": name, **report}); payloads[name + ".step"] = source
    for name in ("nested_reuse", "assembly_cycle", "missing_context_dependent_relation", "wrong_representation_order"):
        source = _fixture("ap242-assemblies", name)
        report = inspect_step_semantics(source)
        assembly = report["assembly"]
        if name == "nested_reuse":
            ok = assembly["decision"] == "accept" and len(assembly["paths"]) == 4
            nested = [p for p in assembly["paths"] if p["depth"] == 2]
            ok &= len(nested) == 1 and nested[0]["global_translation_mm"] == (100., 10., 0.)
        else:
            ok = assembly["decision"] != "accept" and bool(assembly["diagnostics"])
        rows.append(_summary(name, report, ok)); details.append({"control_id": name, **report}); payloads[name + ".step"] = source
    return finish(output, fixtures, "complex_product_structures", rows, details, payloads, [
        "Direct associations and non-transformed shape relationships enumerate alternatives; only unique or explicit candidates are selected.",
        "Traversal uses visited IDs and candidate/link budgets, including cycles; related representations are not declared equivalent.",
        "Multiple model items remain separate. Reused definitions retain distinct occurrence paths and composed transforms.",
        "Alternative representations on assembly definitions remain a placement ambiguity; explicit product selection does not silently rewrite assembly paths.",
    ], refresh=refresh)
