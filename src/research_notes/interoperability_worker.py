"""Isolated, machine-readable adapter for the pinned portability experiment."""
from __future__ import annotations

from dataclasses import asdict
import importlib.util
import json
from pathlib import Path
import sys


def observe(route, path, parser_root=None):
    if route == "steputils":
        sys.path.insert(0, str(parser_root / "src"))
        from steputils import p21
        parsed = p21.readfile(str(path))
        return {"outcome": "accept", "entity_count": sum(len(section) for section in parsed.data),
                "schema_validation": "not_supported", "geometry": "not_supported"}
    if route == "ifcopenshell_step_file_parser":
        spec = importlib.util.spec_from_file_location("pinned_step_parser", parser_root / "__init__.py",
                                                      submodule_search_locations=[str(parser_root)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        module.parse(filename=str(path), with_tree=False)
        return {"outcome": "accept", "entity_count": None, "mode": "validation_without_tree",
                "schema_validation": "not_supported", "geometry": "not_supported"}
    from OCP.IFSelect import IFSelect_RetDone
    from research_notes.public_step import length_contexts
    from research_notes.step_part21 import parse_part21_document
    from research_notes.modeling_common import measure_shape
    contexts = length_contexts(parse_part21_document(path.read_bytes()))
    if route == "stepcontrol":
        from OCP.STEPControl import STEPControl_Reader
        reader = STEPControl_Reader()
        if reader.ReadFile(str(path)) != IFSelect_RetDone:
            raise ValueError("STEPControl read failed")
        reader.SetSystemLengthUnit(1.)
        roots = reader.NbRootsForTransfer()
        if not 1 <= roots <= 128 or reader.TransferRoots() != roots:
            raise ValueError("partial or excessive root transfer")
        shape = reader.OneShape()
        attributes = {"status": "not_supported", "names": [], "colors": []}
    elif route == "stepcaf":
        from OCP.STEPCAFControl import STEPCAFControl_Reader
        from research_notes.step_round_trip_preservation import _new_document, _document_observation
        reader = STEPCAFControl_Reader()
        reader.SetNameMode(True); reader.SetColorMode(True)
        if reader.ReadFile(str(path)) != IFSelect_RetDone:
            raise ValueError("STEPCAF read failed")
        reader.Reader().SetSystemLengthUnit(1.)
        document = _new_document()
        if not reader.Transfer(document):
            raise ValueError("STEPCAF transfer failed")
        observation, shape = _document_observation("portability", "source", path.name, path.read_bytes(), document)
        roots = observation.top_level_shape_count
        attributes = {"status": "observed", "names": observation.names, "colors": observation.colors,
                      "scope": "free-root names and color table; not complete occurrence-level attribute binding"}
    else:
        raise ValueError("unknown observation route")
    metrics = measure_shape(shape)
    if not metrics.analyzer_valid:
        raise ValueError("native shape is not valid")
    mesh = {"status": "not_eligible", "reason": "not_a_single_closed_solid"}
    if route == "stepcontrol" and metrics.solid_count == 1:
        from research_notes.engineering_analysis import mesh_mass_properties
        if metrics.face_count <= 128:
            try:
                mesh = {"status": "measured", **mesh_mass_properties(shape, deflection=.03, angular_deflection=.15)}
            except ValueError as error:
                mesh = {"status": "not_eligible", "reason": str(error)}
        else:
            mesh = {"status": "not_eligible", "reason": "face_budget"}
    return {"outcome": "accept", "roots": roots, "metrics": asdict(metrics), "attributes": attributes,
            "units": contexts, "mesh_integral": mesh, "geometry_kernel": "OCCT 7.9.3"}


def main():
    route, file_name, *extra = sys.argv[1:]
    try:
        result = observe(route, Path(file_name), Path(extra[0]) if extra else None)
    except (ImportError, OSError, AttributeError, TypeError) as error:
        result = {"outcome": "error", "diagnostic_class": type(error).__name__}
    except Exception as error:
        # External parsers do not share exception classes. Keep their outcome and
        # exception name without leaking path-dependent tracebacks into fixtures.
        result = {"outcome": "reject", "diagnostic_class": type(error).__name__}
    print("INTEROP_RESULT=" + json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
