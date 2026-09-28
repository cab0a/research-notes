"""Opt-in, source-preserving interpretation of selected AP203/214/242 roles.

This is a bounded role reader, not an EXPRESS schema validator. In particular,
CONFIG_CONTROL_DESIGN does not enable the AP214/242 assembly placement profile.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
from pathlib import Path

from research_notes.ap242_assembly import (
    _AssemblyResolver, _AssemblyError, DEFAULT_ASSEMBLY_LIMITS,
)
from research_notes.ap242_paths import AP242_SCHEMA_IDENTIFIER
from research_notes.step_graph import build_step_graph
from research_notes.step_part21 import parse_part21_document, DEFAULT_STEP_PARSE_LIMITS


PROFILES = {
    "CONFIG_CONTROL_DESIGN": "AP203 legacy product/shape subset",
    "AUTOMOTIVE_DESIGN": "AP214 product/shape/occurrence subset",
    AP242_SCHEMA_IDENTIFIER: "AP242 MIM product/shape/occurrence subset",
    "AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }": "AP214 product/shape/occurrence subset (explicit OID spelling)",
}
REPRESENTATIONS = {
    "SHAPE_REPRESENTATION", "ADVANCED_BREP_SHAPE_REPRESENTATION",
    "FACETED_BREP_SHAPE_REPRESENTATION", "TESSELLATED_SHAPE_REPRESENTATION",
}
MODELS = {"BLOCK", "MANIFOLD_SOLID_BREP", "BREP_WITH_VOIDS", "FACETED_BREP",
          "SHELL_BASED_SURFACE_MODEL", "GEOMETRIC_SET", "TESSELLATED_SOLID"}
ASSEMBLY_SCHEMAS = ("AUTOMOTIVE_DESIGN", AP242_SCHEMA_IDENTIFIER,
                    "AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }")


class RoleError(ValueError):
    pass


def inspect_step_file(path: Path, **options) -> dict:
    """Bound acquisition before parsing and retain the original byte digest."""
    with Path(path).open("rb") as stream:
        source = stream.read(DEFAULT_STEP_PARSE_LIMITS.max_file_bytes + 1)
    if len(source) > DEFAULT_STEP_PARSE_LIMITS.max_file_bytes:
        raise ValueError("STEP semantic input byte budget exceeded")
    return inspect_step_semantics(source, **options)


def inspect_step_semantics(source: bytes, *, selections: dict[int, int] | None = None,
                           max_links: int = 4096, max_candidates: int = 256) -> dict:
    """Read product structure and select only a unique or caller-named shape.

    Selection IDs are PRODUCT_DEFINITION -> representation. Related shapes
    remain alternatives, not inferred geometric equivalents. No source mutation,
    geometry transfer, external-reference fetch, or metadata-preserving export.
    """
    if not isinstance(source, bytes):
        raise TypeError("source must be immutable bytes")
    if type(max_links) is not int or type(max_candidates) is not int or not 1 <= max_links <= 10000 or not 1 <= max_candidates <= 1024:
        raise ValueError("invalid semantic traversal budget")
    choices = dict(selections or {})
    if any(type(k) is not int or type(v) is not int or k <= 0 or v <= 0 for k, v in choices.items()):
        raise ValueError("selection requires positive integer entity IDs")
    document = parse_part21_document(source, limits=DEFAULT_STEP_PARSE_LIMITS)
    graph = build_step_graph(source)
    entities = {e.entity_id: e for e in document.entities}
    resolver = _AssemblyResolver(document, graph, DEFAULT_ASSEMBLY_LIMITS,
                                 accepted_schemas=ASSEMBLY_SCHEMAS)
    schema = resolver._schema_identifier()
    report = {"source_sha256": hashlib.sha256(source).hexdigest(), "schema": schema,
              "profile": PROFILES.get(schema), "schema_conformance": "not_evaluated",
              "products": [], "representations": [], "relationships": [],
              "assembly": None, "diagnostics": [], "selection_policy": "unique_or_explicit"}

    def diagnostic(code, entity=None, detail=""):
        report["diagnostics"].append({"code": code, "entity_id": entity.entity_id if entity else None,
                                      "source_span": asdict(entity.span) if entity else None, "detail": detail})

    if schema not in PROFILES:
        diagnostic("unsupported_application_schema")
        report["status"] = "unsupported"
        return report

    def record(entity, types, arity=None):
        found = [r for r in entity.records if r.type_name in types]
        if len(found) != 1 or (arity is not None and len(found[0].arguments) != arity):
            raise RoleError("record_or_parameter_count_mismatch")
        return found[0]

    def reference(value, types=None):
        if value.kind != "entity_reference":
            raise RoleError("local_reference_required")
        target = entities.get(int(str(value.value)[1:]))
        if target is None:
            raise RoleError("unresolved_reference")
        if types and not any(r.type_name in types for r in target.records):
            raise RoleError("unexpected_target_type")
        return target

    def string(value, optional=False):
        if optional and value.kind == "omitted":
            return None
        if value.kind != "string":
            raise RoleError("string_required")
        return value.value

    reps, links, direct = {}, [], {}
    for entity in document.entities:
        types = {r.type_name for r in entity.records}
        if not types & REPRESENTATIONS:
            continue
        try:
            rep = record(entity, REPRESENTATIONS, 3)
            if rep.type_name == "TESSELLATED_SHAPE_REPRESENTATION" and schema != AP242_SCHEMA_IDENTIFIER:
                raise RoleError("representation_outside_profile")
            items = rep.arguments[1]
            if items.kind != "list":
                raise RoleError("item_aggregate_required")
            item_entities = [reference(v) for v in items.children]
            unit, unit_edges, context_id = resolver._length_unit_for_representation(entity, "shape")
            context = entities[context_id]
            dimension = record(context, {"GEOMETRIC_REPRESENTATION_CONTEXT"}, 1).arguments[0]
            if dimension.kind != "integer" or dimension.value != 3:
                raise RoleError("only_3d_context_supported")
            row = {"entity_id": entity.entity_id, "type": rep.type_name,
                   "name": string(rep.arguments[0]), "context_id": context_id,
                   "length_unit_id": unit.entity.entity_id, "mm_per_source_unit": unit.scale_to_millimetre,
                   "unit_form": unit.form, "unit_source_edges": [asdict(e.edge) for _, e in unit_edges],
                   "item_ids": [e.entity_id for e in item_entities],
                   "model_ids": [e.entity_id for e in item_entities if any(r.type_name in MODELS for r in e.records)],
                   "source_span": asdict(entity.span)}
            reps[entity.entity_id] = row
        except (RoleError, _AssemblyError) as error:
            diagnostic(getattr(error, "reason_code", str(error)), entity)
    report["representations"] = list(reps.values())

    for entity in document.entities:
        types = {r.type_name for r in entity.records}
        try:
            if "SHAPE_DEFINITION_REPRESENTATION" in types:
                association = record(entity, {"SHAPE_DEFINITION_REPRESENTATION"}, 2)
                pds = reference(association.arguments[0], {"PRODUCT_DEFINITION_SHAPE"})
                definition = reference(record(pds, {"PRODUCT_DEFINITION_SHAPE"}, 3).arguments[2], {"PRODUCT_DEFINITION"})
                rep = reference(association.arguments[1], REPRESENTATIONS)
                direct.setdefault(definition.entity_id, []).append((rep.entity_id, entity.entity_id, pds.entity_id))
            if "SHAPE_REPRESENTATION_RELATIONSHIP" in types:
                relation = record(entity, {"REPRESENTATION_RELATIONSHIP", "SHAPE_REPRESENTATION_RELATIONSHIP"}
                                  if len(entity.records) == 1 else {"REPRESENTATION_RELATIONSHIP"}, 4)
                ends = [reference(v, REPRESENTATIONS).entity_id for v in relation.arguments[2:]]
                transformed = "REPRESENTATION_RELATIONSHIP_WITH_TRANSFORMATION" in types
                row = {"entity_id": entity.entity_id, "representation_ids": ends,
                       "has_transform": transformed, "geometric_equivalence": "not_inferred",
                       "source_span": asdict(entity.span)}
                report["relationships"].append(row)
                # Occurrence transforms relate different products, not shape alternatives.
                if not transformed:
                    links.append(tuple(ends))
                if len(report["relationships"]) > max_links:
                    raise ValueError("representation_relationship_limit")
        except RoleError as error:
            diagnostic(str(error), entity)

    adjacency = {}
    for a, b in links:
        adjacency.setdefault(a, set()).add(b)
        adjacency.setdefault(b, set()).add(a)
    for entity in document.entities:
        if not any(r.type_name == "PRODUCT_DEFINITION" for r in entity.records):
            continue
        try:
            pd = record(entity, {"PRODUCT_DEFINITION"}, 4)
            formation = reference(pd.arguments[2], {"PRODUCT_DEFINITION_FORMATION", "PRODUCT_DEFINITION_FORMATION_WITH_SPECIFIED_SOURCE"})
            f = record(formation, {"PRODUCT_DEFINITION_FORMATION", "PRODUCT_DEFINITION_FORMATION_WITH_SPECIFIED_SOURCE"})
            if len(f.arguments) != (4 if f.type_name.endswith("WITH_SPECIFIED_SOURCE") else 3):
                raise RoleError("formation_parameter_count_mismatch")
            source_kind = f.arguments[3].value if len(f.arguments) == 4 else None
            if len(f.arguments) == 4 and (f.arguments[3].kind != "enumeration" or source_kind not in {"MADE", "BOUGHT", "NOT_KNOWN"}):
                raise RoleError("unsupported_formation_source")
            product = reference(f.arguments[2], {"PRODUCT"})
            p = record(product, {"PRODUCT"}, 4)
            context = reference(pd.arguments[3], {"PRODUCT_DEFINITION_CONTEXT", "DESIGN_CONTEXT"})
            record(context, {"PRODUCT_DEFINITION_CONTEXT", "DESIGN_CONTEXT"}, 3)
            roots = direct.get(entity.entity_id, [])
            if len({root[2] for root in roots}) > 1:
                raise RoleError("duplicate_product_definition_shape")
            visited, pending = set(), [r[0] for r in roots]
            while pending:
                current = pending.pop()
                if current in visited:
                    continue
                visited.add(current)
                if len(visited) > max_candidates:
                    raise ValueError("representation_candidate_limit")
                pending.extend(sorted(adjacency.get(current, ())))
            valid = sorted(visited & reps.keys())
            unknown = sorted(visited - reps.keys())
            selection = choices.pop(entity.entity_id, None)
            if selection is not None and (selection not in valid or unknown):
                raise ValueError("explicit selection is outside qualified candidates")
            selected = selection if selection is not None else valid[0] if len(valid) == 1 and not unknown else None
            state = "explicit" if selection is not None else "unique" if selected else "ambiguous" if len(valid) > 1 else "unresolved"
            if unknown:
                state, selected = "unresolved", None
            report["products"].append({"definition_id": entity.entity_id, "product_id": product.entity_id,
                "identifier": string(p.arguments[0]), "name": string(p.arguments[1]),
                "description": string(p.arguments[2], optional=True), "formation_id": formation.entity_id,
                "formation_type": f.type_name, "formation_source": source_kind, "definition_context_id": context.entity_id,
                "direct_paths": [{"representation_id": r, "association_id": a, "shape_id": s} for r, a, s in roots],
                "candidate_ids": valid, "unqualified_candidate_ids": unknown, "selection": state,
                "selected_representation_id": selected, "source_span": asdict(entity.span)})
        except RoleError as error:
            diagnostic(str(error), entity)
    if choices:
        raise ValueError("selection names an unknown or unresolved product definition")
    if not report["products"]:
        diagnostic("product_definition_path_not_found")
    occurrences = [e for e in document.entities if any(r.type_name == "NEXT_ASSEMBLY_USAGE_OCCURRENCE" for r in e.records)]
    if occurrences:
        if schema in ASSEMBLY_SCHEMAS:
            assembly = resolver.resolve()
            report["assembly"] = {"decision": assembly.decision, "paths": [asdict(p) for p in assembly.paths],
                                  "occurrences": [asdict(o) for o in assembly.occurrences],
                                  "diagnostics": [asdict(d) for d in assembly.diagnostics]}
        else:
            diagnostic("assembly_placement_outside_profile", detail="Legacy AP203 occurrences are retained as syntax; placement is deferred.")
    report["status"] = "partial" if report["diagnostics"] or any(p["selection"] in {"unresolved", "ambiguous"} for p in report["products"]) or (report["assembly"] and report["assembly"]["decision"] != "accept") else "resolved_subset"
    return report
