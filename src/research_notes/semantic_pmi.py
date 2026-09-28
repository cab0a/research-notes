"""Source-linked AP242 PMI paths; a declared subset, not a GD&T verifier."""
from __future__ import annotations

import hashlib
import math
from dataclasses import asdict

from research_notes.ap242_paths import AP242_SCHEMA_IDENTIFIER
from research_notes.step_part21 import Part21Document, parse_part21_document


def inspect_pmi(source: bytes | Part21Document) -> dict:
    document = parse_part21_document(source) if isinstance(source, bytes) else source
    digest = hashlib.sha256(document.source_text.encode()).hexdigest()
    result = {"source_sha256": digest, "schema_status": "controlled_roles_only",
              "full_schema_validation": False, "semantic": [], "presentation": [], "diagnostics": []}
    if document.schema_identifiers != (AP242_SCHEMA_IDENTIFIER,):
        result["diagnostics"].append({"entity_id": None, "reason": "unsupported_schema"})
        result["status"] = "unsupported_schema"
        return result
    entities = {e.entity_id: e for e in document.entities}

    def record(identifier, kind, count=None):
        entity = entities.get(identifier)
        records = [r for r in entity.records if r.type_name == kind] if entity else []
        if len(records) != 1 or (count is not None and len(records[0].arguments) != count):
            raise ValueError(f"expected {kind} at #{identifier}")
        return records[0]

    def ref(value):
        if value.kind != "entity_reference":
            raise ValueError("expected an explicit internal entity reference")
        target = int(str(value.value)[1:])
        if target not in entities:
            raise ValueError(f"unresolved #{target}")
        return target

    def text(value):
        if value.kind != "string":
            raise ValueError("expected string")
        return value.value

    def aspect(identifier, kind="SHAPE_ASPECT"):
        args = record(identifier, kind, 5 if kind == "DATUM" else 4).arguments
        text(args[0])
        if args[3].kind != "enumeration" or args[3].value != ("F" if kind == "DATUM" else "T"):
            raise ValueError("unsupported product_definitional logical")
        shape_id = ref(args[2])
        record(shape_id, "PRODUCT_DEFINITION_SHAPE", 3)
        return shape_id

    def measure(identifier):
        ent = entities[identifier]
        kind = "LENGTH_MEASURE_WITH_UNIT" if any(r.type_name == "LENGTH_MEASURE_WITH_UNIT" and len(r.arguments) == 2 for r in ent.records) else "MEASURE_WITH_UNIT"
        if kind == "MEASURE_WITH_UNIT":
            record(identifier, "LENGTH_MEASURE_WITH_UNIT", 0)
        args = record(identifier, kind, 2).arguments
        value = args[0]
        if value.kind != "typed" or value.value != "LENGTH_MEASURE" or len(value.children) != 1:
            raise ValueError("expected explicit LENGTH_MEASURE")
        number = value.children[0]
        if number.kind not in {"integer", "real"} or not math.isfinite(number.value) or number.value < 0:
            raise ValueError("magnitude must be finite and nonnegative")
        unit_id = ref(args[1])
        record(unit_id, "LENGTH_UNIT", 0)
        unit = record(unit_id, "SI_UNIT", 2).arguments
        prefix, name = (v.value for v in unit)
        prefix = None if unit[0].kind == "omitted" else prefix
        if name != "METRE" or prefix not in {None, "MILLI", "CENTI"}:
            raise ValueError("unsupported PMI length unit")
        scale = {None: 1000., "MILLI": 1., "CENTI": 10.}[prefix]
        return float(number.value)*scale, unit_id

    def evidence(ids):
        return [{"entity_id": i, "span": asdict(entities[i].span),
                 "source": document.source_slice(entities[i].span)} for i in dict.fromkeys(ids)]

    def datum_evidence(identifier):
        shape_id = aspect(identifier, "DATUM")
        args = record(identifier, "DATUM", 5).arguments
        if text(args[0]) != "":
            raise ValueError("datum name must be empty")
        links = []
        for other in document.entities:
            for r in other.records:
                if r.type_name == "SHAPE_ASPECT_RELATIONSHIP" and len(r.arguments) == 4 and r.arguments[3].value == f"#{identifier}":
                    feature_id = ref(r.arguments[2])
                    if aspect(feature_id, "DATUM_FEATURE") != shape_id:
                        raise ValueError("cross-product datum feature")
                    links.extend((other.entity_id, feature_id))
        if len(links) != 2:
            raise ValueError("datum requires exactly one establishing feature")
        return shape_id, links

    for entity in document.entities:
        kinds = {r.type_name for r in entity.records}
        identifier = entity.entity_id
        try:
            if "DIMENSIONAL_CHARACTERISTIC_REPRESENTATION" in kinds:
                link = record(identifier, "DIMENSIONAL_CHARACTERISTIC_REPRESENTATION", 2).arguments
                dim_id, rep_id = map(ref, link)
                dim = record(dim_id, "DIMENSIONAL_SIZE", 2).arguments
                aspect_id = ref(dim[0])
                shape_id = aspect(aspect_id)
                rep = record(rep_id, "SHAPE_DIMENSION_REPRESENTATION", 3).arguments
                record(ref(rep[2]), "REPRESENTATION_CONTEXT", 2)
                if rep[1].kind != "list" or len(rep[1].children) != 1:
                    raise ValueError("exactly one dimension measure item is supported")
                measure_id = ref(rep[1].children[0])
                value, unit_id = measure(measure_id)
                result["semantic"].append({"entity_id": identifier, "kind": "dimension", "name": text(dim[1]),
                    "value_mm": value, "shape_aspect_id": aspect_id, "product_shape_id": shape_id,
                    "evidence": evidence((identifier, dim_id, aspect_id, shape_id, rep_id, measure_id, unit_id))})
            elif kinds & {"FLATNESS_TOLERANCE", "POSITION_TOLERANCE"}:
                allowed = ({"FLATNESS_TOLERANCE"}, {"POSITION_TOLERANCE"},
                           {"FLATNESS_TOLERANCE", "GEOMETRIC_TOLERANCE"},
                           {"POSITION_TOLERANCE", "GEOMETRIC_TOLERANCE", "GEOMETRIC_TOLERANCE_WITH_DATUM_REFERENCE"})
                if kinds not in allowed:
                    raise ValueError("unsupported tolerance modifiers or mapping")
                kind = "FLATNESS_TOLERANCE" if "FLATNESS_TOLERANCE" in kinds else "POSITION_TOLERANCE"
                geom = next((r for r in entity.records if r.type_name == "GEOMETRIC_TOLERANCE"), None)
                args = record(identifier, "GEOMETRIC_TOLERANCE" if geom else kind, 4).arguments
                aspect_id, measure_id = ref(args[3]), ref(args[2])
                shape_id = aspect(aspect_id)
                value, unit_id = measure(measure_id)
                datum_ids = []
                if "GEOMETRIC_TOLERANCE_WITH_DATUM_REFERENCE" in kinds:
                    ds = record(identifier, "GEOMETRIC_TOLERANCE_WITH_DATUM_REFERENCE", 1).arguments[0]
                    if ds.kind != "list" or not ds.children:
                        raise ValueError("empty datum reference system")
                    precedences = []
                    for child in ds.children:
                        datum_ref_id = ref(child)
                        dr = record(datum_ref_id, "DATUM_REFERENCE", 2).arguments
                        if dr[0].kind != "integer" or dr[0].value <= 0:
                            raise ValueError("invalid datum precedence")
                        precedences.append(dr[0].value)
                        datum_id = ref(dr[1])
                        datum_shape, establishing = datum_evidence(datum_id)
                        if datum_shape != shape_id:
                            raise ValueError("cross-product datum reference")
                        datum_ids.extend((datum_ref_id, datum_id, *establishing))
                    if len(set(precedences)) != len(precedences):
                        raise ValueError("duplicate datum precedence")
                result["semantic"].append({"entity_id": identifier, "kind": kind.lower(), "name": text(args[0]),
                    "value_mm": value, "shape_aspect_id": aspect_id, "datum_reference_ids": datum_ids,
                    "evidence": evidence((identifier, aspect_id, shape_id, measure_id, unit_id, *datum_ids))})
            elif "DATUM" in kinds:
                shape_id, links = datum_evidence(identifier)
                args = record(identifier, "DATUM", 5).arguments
                result["semantic"].append({"entity_id": identifier, "kind": "datum", "identification": text(args[4]),
                    "evidence": evidence((identifier, shape_id, *links))})
            elif kinds & {"DRAUGHTING_CALLOUT", "ANNOTATION_TEXT_OCCURRENCE", "DESCRIPTIVE_REPRESENTATION_ITEM"}:
                result["presentation"].append({"entity_id": identifier, "types": sorted(kinds),
                    "semantic_value_inferred": False, "evidence": evidence((identifier,))})
            elif any("TOLERANCE" in k or "DIMENSIONAL_" in k for k in kinds) and not kinds <= {"DIMENSIONAL_SIZE"}:
                result["diagnostics"].append({"entity_id": identifier, "reason": "unsupported_pmi_form"})
        except (ValueError, TypeError) as exc:
            result["diagnostics"].append({"entity_id": identifier, "reason": str(exc)})
    result["status"] = "partial" if result["diagnostics"] else "observed" if result["semantic"] else "no_supported_pmi"
    return result
