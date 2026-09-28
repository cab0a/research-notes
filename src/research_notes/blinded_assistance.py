"""Preregistered synthetic holdout evaluation of the unchanged v0.77 checkpoint."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from dataclasses import asdict

from research_notes.robustness_studies import ROOT


def preregistration():
    path = ROOT / "fixtures/blinded-assistance/preregistration.json"
    lock = json.loads(path.read_text())
    for name, expected in lock["files"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise ValueError("preregistered input changed: " + name)
    commit = "4731ab07e08e099cbedf6c5deda5e83c6b9d83ae"
    registered = subprocess.run(["git", "show", commit + ":fixtures/blinded-assistance/protocol.json"],
                                cwd=ROOT, capture_output=True, check=True).stdout
    if hashlib.sha256(registered).hexdigest() != lock["files"]["fixtures/blinded-assistance/protocol.json"]:
        raise ValueError("preregistration commit does not contain the frozen protocol")
    return {**lock, "protocol_commit": commit}


def holdout_shape(family, variant):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeSphere
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
    from OCP.BRepFilletAPI import BRepFilletAPI_MakeChamfer, BRepFilletAPI_MakeFillet
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopoDS import TopoDS
    from OCP.gp import gp_Pnt, gp_Ax2, gp_Dir
    from research_notes.brep_runtime import indexed_shapes
    from research_notes.parametric_features import PlateSpec, build_plate, feature_spec, apply_feature
    plate = PlateSpec(18., 12., 4.)
    shape = build_plate(plate).shape
    def feature(kind, **values):
        nonlocal shape
        shape = apply_feature(shape, plate, feature_spec(kind, **values)).shape
    if family in {"paired_cylindrical_cuts", "paired_cylindrical_additions"}:
        for x, y in ((4., 4.), (13., 8.)):
            if family.endswith("cuts"):
                feature("through_hole", x=x, y=y, radius=1. + variant)
            else:
                feature("boss", x=x, y=y, radius=1. + variant, height=1.5)
    elif family == "paired_rectangular_cuts":
        for x, y in ((3., 3.), (11., 7.)):
            feature("pocket", x=x, y=y, width=3. + variant, length=2., depth=1.5)
    elif family == "long_capsule_cut":
        radius = .8 + variant
        first = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(5, 6, -1), gp_Dir(0, 0, 1)), radius, 6.).Shape()
        last = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(13, 6, -1), gp_Dir(0, 0, 1)), radius, 6.).Shape()
        bridge = BRepPrimAPI_MakeBox(gp_Pnt(5, 6 - radius, -1), 8., 2 * radius, 6.).Shape()
        shape = BRepAlgoAPI_Cut(shape, BRepAlgoAPI_Fuse(BRepAlgoAPI_Fuse(first, bridge).Shape(), last).Shape()).Shape()
    elif family == "two_level_stair_cut":
        shape = BRepAlgoAPI_Cut(shape, BRepPrimAPI_MakeBox(gp_Pnt(6, 0, 3 - variant), 12., 12., 2.).Shape()).Shape()
        shape = BRepAlgoAPI_Cut(shape, BRepPrimAPI_MakeBox(gp_Pnt(12, 0, 2 - variant), 6., 12., 3.).Shape()).Shape()
    elif family in {"multiple_edge_chamfer", "all_edge_rounding"}:
        operation = BRepFilletAPI_MakeChamfer(shape) if family == "multiple_edge_chamfer" else BRepFilletAPI_MakeFillet(shape)
        edges = indexed_shapes(shape, TopAbs_EDGE)
        for index in ((1, 5) if family == "multiple_edge_chamfer" else range(1, edges.Extent() + 1)):
            operation.Add(.25 + variant, TopoDS.Edge_s(edges.FindKey(index)))
        operation.Build()
        if not operation.IsDone():
            raise RuntimeError("held-out authored feature construction failed")
        shape = operation.Shape()
    elif family == "crossed_rectangular_additions":
        feature("rib", x=4., y=6., width=10., length=1. + variant, height=1.5)
        feature("rib", x=8., y=2., width=1. + variant, length=8., height=1.5)
    elif family == "mixed_hole_boss":
        feature("through_hole", x=4., y=4., radius=1. + variant)
        feature("boss", x=13., y=8., radius=1., height=1.5)
    elif family == "sphere_negative":
        shape = BRepPrimAPI_MakeSphere(3. + variant).Shape()
    else:
        raise ValueError("unknown preregistered construction family")
    return shape


def blind_predict(model, features):
    from research_notes.representation_learning import predict_representation
    # The predictor boundary cannot receive labels, recipes, family names or paths.
    allowed = {"sample_id", "values", "source_sha256", "support"}
    if any(set(row) != allowed for row in features):
        raise ValueError("blind prediction input contains non-feature fields")
    return [{**row, **predict_representation(model, row["values"])} for row in features]


def evaluate_blinded():
    from research_notes.representation_learning import RepresentationModel, prediction_metrics
    from research_notes.learning_studies import ranking_descriptor
    from research_notes.brep_runtime import step_round_trip
    from research_notes.modeling_common import measure_shape
    registration = preregistration()
    from research_notes.artifact_contracts import verify_manifest
    from research_notes.cad_platform import numeric_differences
    from research_notes.public_step import read_step_for_inspection
    corpus = ROOT / "fixtures/blinded-assistance-evaluation"
    if (corpus / "manifest.csv").exists():
        verify_manifest(corpus)
    protocol = json.loads((ROOT / "fixtures/blinded-assistance/protocol.json").read_text())
    model = RepresentationModel(**json.loads((ROOT / protocol["training_checkpoint"]).read_text()))
    if model.abstention_threshold != protocol["abstention_threshold"]:
        raise ValueError("model and registered abstention policy differ")
    training_sources = {s["source_sha256"] for s in json.loads((ROOT / protocol["training_samples"]).read_text())}
    features, truths, payloads = [], {}, {}
    for family in protocol["construction_families"]:
        for variant in protocol["variants"]:
            identifier = f"holdout_{len(features):02d}"
            shape = holdout_shape(family["family"], variant)
            if not measure_shape(shape).analyzer_valid:
                raise ValueError("invalid authored holdout shape")
            fixture = step_round_trip(shape, identifier, writer_uncertainty=1e-7)
            payload, imported_shape = fixture.source_bytes, fixture.imported_shape
            fixed = corpus / fixture.file_name
            if fixed.exists():
                frozen = read_step_for_inspection(fixed).imported
                differences = numeric_differences(asdict(measure_shape(imported_shape)), asdict(frozen.metrics))
                if differences:
                    raise ValueError("regenerated holdout geometry differs: " + str(differences[:3]))
                # Native STEP spelling may differ across platforms. Predict the
                # same hash-verified held-out input on every runner.
                payload, imported_shape = frozen.source_bytes, frozen.shape
            source_sha256 = hashlib.sha256(payload).hexdigest()
            if source_sha256 in training_sources:
                raise ValueError("training/test source identity leakage")
            values, support = ranking_descriptor(imported_shape, identifier)
            features.append({"sample_id": identifier, "values": values, "source_sha256": source_sha256, "support": support})
            truths[identifier] = {"truth": family["truth"], "family": family["family"], "variant": variant}
            payloads[fixture.file_name] = payload
    # Truth is joined only after all predictions have been made with frozen parameters.
    predictions = [{**p, **truths[p["sample_id"]]} for p in blind_predict(model, features)]
    rows = [{"control_id": p["sample_id"], "family": p["family"], "truth": p["truth"],
             "prediction": p["prediction"], "decision": p["decision"], "confidence": round(p["confidence"], 8),
             "correct": p["prediction"] == p["truth"], "checks_pass": bool(p["support"]["faces"]) and
                 p["sample_id"] not in model.train_ids + model.validation_ids} for p in predictions]
    detail = {"preregistration": registration, "predictions": predictions, "metrics": prediction_metrics(predictions),
              "checkpoint_unchanged": preregistration()["files"] == registration["files"],
              "evidence_coverage": sum(bool(p["support"]["faces"]) for p in predictions) / len(predictions),
              "scope": protocol["scope"], "threshold_tuned_on_holdout": False}
    return rows, detail, payloads, features, truths
