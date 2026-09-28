"""Representation and candidate ranking experiments with retained failure evidence."""
from __future__ import annotations
import json
from dataclasses import asdict
from pathlib import Path
from research_notes.advanced_geometry_studies import finish_study
from research_notes.modeling_studies import json_bytes
from research_notes.representation_learning import fit_representation,predict_representation,prediction_metrics
from research_notes.change_pair_dataset import leakage_audit,shape_descriptors
from research_notes.brep_runtime import step_round_trip,indexed_shapes


REPRESENTATION_NAMES={
    "geometry_table":("volume_before","volume_after","area_before","area_after","volume_delta","area_delta"),
    "face_graph":("face_delta","adjacency_delta","mean_degree_delta","curved_area_ratio_delta","plane_delta","cylinder_delta","boundary_delta"),
    "tessellation":("mesh_volume_delta","mesh_area_delta","triangle_count_delta"),
    "feature_history":("node_count","plate_edit","additive_operation","subtractive_operation"),
}


def run_representation_learning(output:Path,fixtures:Path,*,refresh=False):
    pairs=json.loads((Path(__file__).resolve().parents[2]/"fixtures/change-pair-dataset/pairs.json").read_text())
    audit=leakage_audit(pairs)
    if not audit["checks_pass"]:raise ValueError("family or identity leakage")
    rows,detail,models=[],[],{}
    for representation,names in REPRESENTATION_NAMES.items():
        samples=[{"sample_id":p["pair_id"],"lineage_id":p["lineage_id"],"split":p["split"],"truth":p["truth"],"values":p["representations"][representation]} for p in pairs]
        model=fit_representation(samples,names);models[representation]=asdict(model)
        predictions=[{**{k:s[k] for k in ("sample_id","split","truth")},**predict_representation(model,s["values"])} for s in samples]
        for split in ("validation","test"):
            metrics=prediction_metrics([r for r in predictions if r["split"]==split])
            rows.append({"control_id":representation+"_"+split,"accuracy":metrics["accuracy"],"coverage":metrics["coverage"],"brier":metrics["brier"],"checks_pass":all(p["sample_id"] not in model.train_ids+model.validation_ids for p in predictions if p["split"]=="test")})
        detail.append({"representation":representation,"privileged_authored_history":representation=="feature_history","model":asdict(model),"predictions":predictions,
                       "test_metrics":prediction_metrics([r for r in predictions if r["split"]=="test"])})
    test=[p for p in pairs if p["split"]=="test"]
    rule=[("additive" if p["representations"]["geometry_table"][4]>0 else "subtractive")==p["truth"] for p in test]
    majority=max((sum(p["truth"]==label for p in pairs if p["split"]=="train"),label) for label in ("additive","subtractive"))[1]
    for name,accuracy in (("signed_volume_rule",sum(rule)/len(rule)),("training_majority",sum(p["truth"]==majority for p in test)/len(test))):
        rows.append({"control_id":name+"_test","accuracy":accuracy,"coverage":1.,"brier":None,"checks_pass":True})
    return finish_study(output,fixtures,"representation_learning","v0.76.0",rows,{"models":detail,"leakage":audit},
        {"models.json":json_bytes(models),"split_manifest.json":json_bytes([{k:p[k] for k in ("pair_id","family","lineage_id","split","before_sha256","after_sha256")} for p in pairs])},[],
        ["task: additive versus subtractive parametric change, six isolated synthetic construction families",
         "train-only means/scales/centroids; validation-only temperature; test labels never fit model or calibration",
         "signed-volume rule is a strong exact control; authored-history descriptors are privileged, not recovered from STEP",
         "accuracy, Brier score, calibration, abstentions and high-confidence errors retained without a success threshold"],refresh)


RANK_LABELS=("hole","pocket","slot","step","chamfer","fillet","boss","rib")
RANK_FEATURES=("faces","adjacencies","mean_degree","curved_area_ratio","plane_faces","cylinder_faces","boundary_edges",
               "volume_fill_ratio","area_scale_ratio","concave_cylinder_faces","other_curved_faces")


def ranking_shape(label,variant):
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox,BRepPrimAPI_MakeCylinder
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut,BRepAlgoAPI_Fuse
    from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet,BRepFilletAPI_MakeChamfer
    from OCP.gp import gp_Pnt,gp_Ax2,gp_Dir
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopoDS import TopoDS
    from research_notes.parametric_features import PlateSpec,feature_spec,build_plate,apply_feature
    if label not in RANK_LABELS or variant not in range(4):raise ValueError("unsupported ranking control")
    w,length,t=12.+variant*.6,10.+variant*.3,4.+variant*.15
    plate=PlateSpec(w,length,t);base=build_plate(plate).shape;r=.8+variant*.12
    if label in {"hole","boss","pocket","rib"}:
        kind={"hole":"through_hole", "boss":"boss", "pocket":"pocket","rib":"rib"}[label]
        p={"x":4.+variant*.2,"y":4.,"radius":r} if label in {"hole","boss"} else {"x":3.,"y":3.,"width":2.+variant*.2,"length":3.}
        if label in {"boss","rib"}:p["height"]=1.5+variant*.1
        if label=="pocket":p["depth"]=1.5+variant*.1
        return apply_feature(base,plate,feature_spec(kind,**p)).shape
    if label=="step":
        return BRepAlgoAPI_Cut(base,BRepPrimAPI_MakeBox(gp_Pnt(w*.5,0,t*.5),w*.5,length,t*.5).Shape()).Shape()
    if label=="slot":
        cylinder_a=BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(4,5,-1),gp_Dir(0,0,1)),r,t+2).Shape()
        cylinder_b=BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(7,5,-1),gp_Dir(0,0,1)),r,t+2).Shape()
        tool=BRepAlgoAPI_Fuse(cylinder_a,BRepPrimAPI_MakeBox(gp_Pnt(4,5-r,-1),3.,2*r,t+2).Shape()).Shape()
        tool=BRepAlgoAPI_Fuse(tool,cylinder_b).Shape()
        return BRepAlgoAPI_Cut(base,tool).Shape()
    edge=TopoDS.Edge_s(indexed_shapes(base,TopAbs_EDGE).FindKey(1))
    operation=BRepFilletAPI_MakeFillet(base) if label=="fillet" else BRepFilletAPI_MakeChamfer(base)
    operation.Add(.4+variant*.05,edge);operation.Build()
    if not operation.IsDone():raise RuntimeError("ranking control feature construction failed")
    return operation.Shape()


def ranking_descriptor(shape,name="query"):
    from research_notes.face_adjacency_graph import _evaluate_graph
    nodes,edges,graph=_evaluate_graph(name,"constructed",shape,None)
    metrics=graph.metrics;extents=[b-a for a,b in zip(metrics.bounds_min,metrics.bounds_max)];bounds_volume=extents[0]*extents[1]*extents[2]
    h=dict(graph.surface_histogram)
    values=[graph.node_count,graph.relation_count,graph.mean_degree,graph.curved_area_ratio,h.get("plane",0),h.get("cylinder",0),graph.boundary_edge_count,
            metrics.absolute_volume/bounds_volume,metrics.surface_area/(bounds_volume**(2/3)),
            sum(n.surface_type=="cylinder" and n.radial_polarity is not None and n.radial_polarity<0 for n in nodes),
            sum(n.surface_type not in {"plane","cylinder"} for n in nodes)]
    return values,{"faces":[n.analysis_face_index for n in nodes],"edges":[e.analysis_edge_index for e in edges],"scope":"whole-shape aggregate descriptor; candidate localization is not learned"}


def run_candidate_ranking(output:Path,fixtures:Path,*,refresh=False):
    samples,payloads,previews=[],{},[]
    for label in RANK_LABELS:
        for variant in range(4):
            name=f"{label}_design_{variant}";shape=ranking_shape(label,variant);values,support=ranking_descriptor(shape,name)
            fixture=step_round_trip(shape,"ranking_"+name,writer_uncertainty=1e-7);payloads[fixture.file_name]=fixture.source_bytes
            samples.append({"sample_id":name,"lineage_id":name,"split":"train" if variant<2 else "validation" if variant==2 else "test","truth":label,
                            "values":values,"source_sha256":fixture.source_sha256,"support":support,"source_file":fixture.file_name})
            if variant==3:previews.append((label,shape))
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox,BRepPrimAPI_MakeTorus
    for name,shape in (("plain_negative",BRepPrimAPI_MakeBox(12.,10.,4.).Shape()),("torus_unknown",BRepPrimAPI_MakeTorus(4.,1.).Shape())):
        values,support=ranking_descriptor(shape,name);fixture=step_round_trip(shape,"ranking_"+name,writer_uncertainty=1e-7);payloads[fixture.file_name]=fixture.source_bytes
        samples.append({"sample_id":name,"lineage_id":name,"split":"test","truth":"unknown","values":values,"source_sha256":fixture.source_sha256,"support":support,"source_file":fixture.file_name})
        previews.append(("Plain box: false chamfer" if name=="plain_negative" else "Unknown torus: abstained",shape))
    model=fit_representation(samples,RANK_FEATURES)
    predictions=[{**s,**predict_representation(model,s["values"])} for s in samples]
    rows=[]
    for prediction in predictions:
        rows.append({"control_id":prediction["sample_id"],"split":prediction["split"],"truth":prediction["truth"],"prediction":prediction["prediction"],
                     "confidence":prediction["confidence"],"decision":prediction["decision"],"correct":prediction["prediction"]==prediction["truth"],
                     "checks_pass":len(prediction["ranking"])==8 and abs(sum(r["probability"] for r in prediction["ranking"])-1)<1e-12 and bool(prediction["support"]["faces"])})
    detail={"model":asdict(model),"samples":predictions,"test_metrics":prediction_metrics([p for p in predictions if p["split"]=="test"]),
            "baseline":"candidate order is compared to the uniform eight-way prior; ranking is not a dimension extractor"}
    payloads["model.json"]=json_bytes(asdict(model));payloads["samples.json"]=json_bytes(samples)
    return finish_study(output,fixtures,"candidate_ranking","v0.77.0",rows,detail,payloads,previews,
        ["eight authored single-feature labels; 32 independently built dimensional designs plus two unknown/negative controls, with whole design lineages isolated",
         "all labels appear in training; test is bounded dimension generalization, not unseen manufacturing-family validation",
         "scores link source hashes, support faces/edges and per-descriptor distance margins; calibrated confidence can still be wrong",
         "ranks whole-shape candidate hypotheses; does not certify feature intent or recover history"],refresh)
