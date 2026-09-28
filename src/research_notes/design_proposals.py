"""Evidence, complexity and local edit stability of alternative reconstruction DAGs."""
from __future__ import annotations
from dataclasses import asdict,replace
from research_notes.deterministic_recompute import recompute,edit_parameter
from research_notes.step_reconstruction import compare_shapes


def review_reconstructions(inspection):
    proposals=[]
    for candidate in inspection.candidates:
        model=candidate.model;built=recompute(model);current=built.current_output()
        node=next((n for n in model.nodes if n.node_id=="feature"),model.nodes[0])
        parameter=next((p for p in ("radius","width","depth","height","thickness") if p in dict(node.parameters)),None)
        stability=[]
        if parameter:
            value=dict(node.parameters)[parameter]
            for factor in (.95,1.05):
                # Evaluate a fresh unconfirmed hypothesis; do not adopt it or
                # relabel it as user-selected merely to measure stability.
                changed=replace(model,revision=model.revision+1,nodes=tuple(
                    replace(n,parameters=tuple((k,value*factor if k==parameter else v) for k,v in n.parameters)) if n.node_id==node.node_id else n for n in model.nodes))
                result=recompute(changed,built)
                try:
                    output=result.current_output();comparison=compare_shapes(current.shape,output.shape)
                    stability.append({"node":node.node_id,"parameter":parameter,"factor":factor,"status":"valid",
                                      "topology_preserved":comparison["topology_matches"],"volume_delta":output.metrics.absolute_volume-current.metrics.absolute_volume})
                except ValueError as exc:stability.append({"node":node.node_id,"parameter":parameter,"factor":factor,"status":"failed","reason":str(exc)})
        proposals.append({"candidate_id":candidate.candidate_id,"explanation":candidate.explanation,"model":asdict(model),
            "source_sha256":inspection.imported.source_sha256,"supporting_faces":candidate.supporting_faces,
            "fit":{"volume_residual":candidate.volume_residual,"area_residual":candidate.area_residual,"material_difference_volume":candidate.material_difference_volume,"bounds_residual":candidate.bounds_residual},
            "complexity":{"nodes":len(model.nodes),"scalar_parameters":sum(len(n.parameters) for n in model.nodes)},
            "sketch_evidence":[{"node_id":s.node_id,"fingerprint":s.sketch_fingerprint} for s in built.states if s.sketch_fingerprint],
            "local_edit_stability":stability,"status":"requires_human_selection","authoring_history_recovered":False})
    return {"source_sha256":inspection.imported.source_sha256,"status":inspection.status,"alternatives":proposals,
            "rejected_hypotheses":inspection.rejected_proposals,"automatic_selection":False,
            "stability_scope":"two local dimension perturbations; no global editability guarantee"}
