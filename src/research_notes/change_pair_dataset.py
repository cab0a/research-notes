"""Provenance-bound parameter edits with construction-family isolated splits."""
from __future__ import annotations
import hashlib
import tempfile
from dataclasses import asdict,replace
from pathlib import Path
from research_notes.deterministic_recompute import single_feature_model,recompute,edit_parameter,model_fingerprint
from research_notes.parametric_features import PlateSpec,feature_spec,analytic_feature_truth
from research_notes.brep_runtime import step_round_trip
from research_notes.face_adjacency_graph import _evaluate_graph
from research_notes.engineering_analysis import mesh_mass_properties
from research_notes.topological_references import topology_snapshot,reference_relations
from research_notes.modeling_studies import json_bytes
from research_notes.advanced_geometry_studies import finish_study
from research_notes.brep_preview import write_shape_previews


FAMILY_SPLITS={"perforated_plate":"train","round_boss":"train","rectangular_pocket":"validation",
               "rectangular_rib":"validation","blind_bore":"test","plate_growth":"test"}


def pair_controls():
    controls=[]
    for index,kind in enumerate(("through_hole","profile_hole","boss","pocket","rib","blind_hole","plate_growth")):
        family={"through_hole":"perforated_plate","profile_hole":"perforated_plate","boss":"round_boss","pocket":"rectangular_pocket",
                "rib":"rectangular_rib","blind_hole":"blind_bore","plate_growth":"plate_growth"}[kind]
        for variant in range(3):
            plate=PlateSpec(12.+variant+index*.2,10.+variant*.4,4.+variant*.2,origin_x=index*20.)
            p={"x":4.+variant*.2,"y":4.5,"radius":.8+variant*.1}
            if kind=="blind_hole":p["depth"]=2.
            if kind=="boss":p["height"]=2.
            if kind in {"pocket","rib"}:p={"x":3.,"y":3.,"width":2.+variant*.2,"length":3.,"depth" if kind=="pocket" else "height":2.}
            feature=None if kind=="plate_growth" else feature_spec(kind,**p)
            parameter="width" if kind in {"plate_growth","pocket","rib"} else "radius"
            node="base" if kind=="plate_growth" else "feature"
            before=plate.width if feature is None else dict(feature.parameters)[parameter]
            controls.append({"pair_id":f"{kind}_{variant}","family":family,"split":FAMILY_SPLITS[family],"plate":plate,"feature":feature,
                             "node":node,"parameter":parameter,"value":before+.3})
    return controls


def leakage_audit(records):
    reasons=[]
    for key in ("family","lineage_id"):
        owners={}
        for row in records:owners.setdefault(row[key],set()).add(row["split"])
        reasons.extend(f"{key}:{key_value}" for key_value,splits in owners.items() if len(splits)>1)
    owners={}
    for row in records:
        for key in ("before_sha256","after_sha256"):
            owners.setdefault(row[key],set()).add(row["split"])
    reasons.extend("source_identity:"+digest for digest,splits in owners.items() if len(splits)>1)
    # Paired derivations always share a row/split; construction grammar aliases
    # through_hole and profile_hole are explicitly the same lineage family.
    return {"checks_pass":not reasons,"cross_split_leaks":reasons,"split_policy":FAMILY_SPLITS,
            "scope":"source identity, declared construction family and derivation lineage; not geometric novelty certification"}


def shape_descriptors(shape,name):
    nodes,edges,graph=_evaluate_graph(name,"constructed",shape,None)
    mesh=mesh_mass_properties(shape,deflection=.1,angular_deflection=.3)
    histogram=dict(graph.surface_histogram)
    graph_values=[graph.node_count,graph.relation_count,graph.mean_degree,graph.curved_area_ratio,
                  histogram.get("plane",0),histogram.get("cylinder",0),graph.boundary_edge_count]
    return {"graph_values":graph_values,"graph":asdict(graph),"faces":[asdict(n) for n in nodes],"edges":[asdict(e) for e in edges],"mesh":mesh}


def run_change_pair_dataset(output:Path,fixtures:Path,*,refresh=False):
    records,rows,payloads,previews=[],[],{},[]
    for control in pair_controls():
        name=control["pair_id"];plate=control["plate"];feature=control["feature"]
        model=single_feature_model(name,plate,feature)
        before=recompute(model);changed=edit_parameter(model,control["node"],control["parameter"],control["value"]);after=recompute(changed,before)
        a,b=before.current_output(),after.current_output()
        expected_before=analytic_feature_truth(plate,feature)
        new_plate=replace(plate,width=control["value"]) if feature is None else plate
        new_feature=feature_spec(feature.kind,**{**dict(feature.parameters),control["parameter"]:control["value"]}) if feature else None
        expected_after=analytic_feature_truth(new_plate,new_feature)
        data=[];states=[]
        for stage,current,expected in (("before",a,expected_before),("after",b,expected_after)):
            fixture=step_round_trip(current.shape,name+"_"+stage,writer_uncertainty=1e-7);payloads[fixture.file_name]=fixture.source_bytes
            descriptors=shape_descriptors(current.shape,name+"_"+stage)
            data.append(fixture);states.append(descriptors)
        relation=reference_relations(topology_snapshot(a.shape,name,"before"),topology_snapshot(b.shape,name,"after"))
        truth_error=max(abs(a.metrics.absolute_volume-expected_before[0]),abs(b.metrics.absolute_volume-expected_after[0]),
                        abs(a.metrics.surface_area-expected_before[1]),abs(b.metrics.surface_area-expected_after[1]))
        geometric=[a.metrics.absolute_volume,b.metrics.absolute_volume,a.metrics.surface_area,b.metrics.surface_area,
                   b.metrics.absolute_volume-a.metrics.absolute_volume,b.metrics.surface_area-a.metrics.surface_area]
        graph=[y-x for x,y in zip(states[0]["graph_values"],states[1]["graph_values"])]
        mesh=[states[1]["mesh"][key]-states[0]["mesh"][key] for key in ("volume","area","triangles")]
        history=[len(changed.nodes),int(feature is None),int(feature is not None and feature.kind in {"boss","rib"}),int(feature is not None and feature.kind not in {"boss","rib"})]
        record={"pair_id":name,"family":control["family"],"lineage_id":control["family"]+f"_{name.rsplit('_',1)[-1]}","split":control["split"],
            "truth":"additive" if expected_after[0]>expected_before[0] else "subtractive", "before_sha256":data[0].source_sha256,"after_sha256":data[1].source_sha256,
            "before_file":data[0].file_name,"after_file":data[1].file_name,"model_before":asdict(model),"model_after":asdict(changed),
            "edit":{"node":control["node"],"parameter":control["parameter"],"value":control["value"]},
            "model_fingerprint_before":model_fingerprint(model),"model_fingerprint_after":model_fingerprint(changed),
            "construction_truth":{"before":expected_before,"after":expected_after},"measurements_before":asdict(a.metrics),"measurements_after":asdict(b.metrics),
            "correspondence":[asdict(r) for r in relation],"representations":{"geometry_table":geometric,"face_graph":graph,"tessellation":mesh,"feature_history":history},
            "states":states,"checks_pass":truth_error<1e-6}
        preview_name=name+"_preview.png"
        with tempfile.TemporaryDirectory() as directory:
            preview_path=Path(directory)/preview_name
            write_shape_previews(preview_path,(("Before",a.shape),("After",b.shape)),title=name.replace("_"," "),columns=2)
            payloads[preview_name]=preview_path.read_bytes()
        record["preview_file"]=preview_name
        records.append(record);rows.append({"control_id":name,"family":control["family"],"split":control["split"],"truth":record["truth"],"maximum_truth_error":truth_error,"checks_pass":record["checks_pass"]})
        if name.endswith("_0"):previews.append((name,b.shape))
    audit=leakage_audit(records)
    if not audit["checks_pass"]:raise RuntimeError("change-pair identity/lineage leakage")
    payloads["pairs.json"]=json_bytes(records)
    detail={"pairs":records,"leakage":audit,"representation_boundary":"feature_history is privileged authored input; geometry-only tests cannot use it"}
    return finish_study(output,fixtures,"change_pair_dataset","v0.75.0",rows,detail,payloads,previews,
        ["21 parameter changes across six declared construction families; through/profile-hole derivations share train split",
         "STEP, model DAG, measurements, scoped topology correspondences and descriptor records share hashes",
         "geometry matches or ambiguity do not recover original design history; family isolation is synthetic only"],refresh)
