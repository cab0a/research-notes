"""Authored assembly controls with independent expected poses and motion counts."""
from dataclasses import replace

from research_notes.assembly_constraints import (
    AssemblyConstraint, AssemblyDocument, ComponentDefinition, DatumFrame, Occurrence, Placement,
)
from research_notes.deterministic_recompute import single_feature_model
from research_notes.parameter_expressions import Parameter
from research_notes.parametric_features import PlateSpec


def slider_assembly() -> AssemblyDocument:
    definition = ComponentDefinition("block", single_feature_model("block", PlateSpec(2., 2., 2.)),
                                     (DatumFrame(), DatumFrame("top", anchor="plate_top"),
                                      DatumFrame("bottom", anchor="plate_bottom")))
    return AssemblyDocument(
        "two_blocks", (definition,),
        (Occurrence("base", "block"), Occurrence("slider", "block", Placement((.3, -.2, 2.7), (5., -7., 10.)))),
        (AssemblyConstraint("ground", "fixed", "base"),
         AssemblyConstraint("coaxial", "concentric", "slider", "base", "bottom", "top"),
         AssemblyConstraint("gap", "distance", "slider", "base", "bottom", "top", "clearance"),
         AssemblyConstraint("twist", "fixed", "slider", axes=("rz",))),
        (Parameter("height", "2 * mm", "mm", .00001, 10.),
         Parameter("clearance", "1 * mm", "mm", -1.5, 5.)),
        (("block", "height", "base", "thickness"),),
    )


def assembly_controls():
    base = slider_assembly()
    by_id = {c.constraint_id: c for c in base.constraints}
    control_list = [
        ("free_pair", (), "under_constrained", 12, 0),
        ("one_grounded", ("ground",), "under_constrained", 6, 0),
        ("concentric", ("ground", "coaxial"), "under_constrained", 2, 0),
        ("axial_distance", ("ground", "coaxial", "gap"), "under_constrained", 1, 0),
        ("fully_fixed", ("ground", "coaxial", "gap", "twist"), "fully_constrained", 0, 0),
    ]
    controls = [(name, replace(base, constraints=tuple(by_id[k] for k in names)), status, dof, redundant)
                for name, names, status, dof, redundant in control_list]
    controls.append(("plane_coincidence", replace(base, constraints=(by_id["ground"],
                     AssemblyConstraint("plane", "coincident", "slider", "base", "bottom", "top"))),
                     "under_constrained", 3, 0))
    controls.append(("redundant_distance", replace(base, constraints=base.constraints+(replace(by_id["gap"], constraint_id="duplicate_gap"),)),
                     "redundant", 0, 1))
    controls.append(("conflicting_distance", replace(base, constraints=base.constraints+(replace(by_id["gap"], constraint_id="conflict", value_expression="clearance + 1 * mm"),)),
                     "inconsistent", 0, 1))
    tilted = replace(base, constraints=tuple(replace(c, target=Placement((4., 5., 1.), (30., 0., 0.))) if c.kind == "fixed" and c.occurrence_a == "base" else c for c in base.constraints))
    controls.append(("rotated_ground", tilted, "fully_constrained", 0, 0))
    converted = replace(base, occurrences=(base.occurrences[0], replace(base.occurrences[1],
                        initial=Placement(tuple(v/25.4 for v in base.occurrences[1].initial.translation),
                                          base.occurrences[1].initial.rotation_degrees, "inch"))))
    controls.append(("inch_initial_placement", converted, "fully_constrained", 0, 0))
    return tuple(controls)
