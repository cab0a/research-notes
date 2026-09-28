"""Deterministic English/Japanese intent grammar with immutable edit proposals."""
from __future__ import annotations
import hashlib
import json
import re
from dataclasses import asdict,dataclass
from research_notes.deterministic_recompute import FeatureModel,edit_parameter,model_fingerprint,recompute
from research_notes.parameter_expressions import Parameter,evaluate_parameters
from research_notes.step_reconstruction import compare_shapes
from research_notes.assisted_modeling import ConfirmationRequired


@dataclass(frozen=True)
class EditIntent:
    action:str
    node_id:str=""
    parameter:str=""
    expression:str=""


def parse_request(request:str)->EditIntent:
    if not isinstance(request,str) or not 1<=len(request)<=256:raise ValueError("request exceeds bounded grammar length")
    text=request.strip().rstrip("。!")
    queries={"inspect":"inspect","検査":"inspect","形状を検査":"inspect","show mass":"mass","質量を教えて":"mass","質量":"mass",
             "show candidates":"candidates","候補を見せて":"candidates","候補":"candidates","compare":"compare","比較":"compare"}
    if text.lower() in queries:return EditIntent(queries[text.lower()])
    match=re.fullmatch(r"set\s+([a-z][a-z0-9_]*)\s+([a-z][a-z0-9_]*)\s+(.+)",text,re.I)
    if match:
        node,parameter,expression=match.groups()
    else:
        match=re.fullmatch(r"(穴の半径|半径|厚さ|幅|穴の深さ)を\s*(.+?)\s*(?:に変更|にする|に)",text)
        if not match:raise ValueError("unsupported request; use 'set feature radius 1.5 mm' or '穴の半径を1.5 mmに'")
        label,expression=match.groups();node,parameter={"穴の半径":("feature","radius"),"半径":("feature","radius"),"厚さ":("base","thickness"),"幅":("base","width"),"穴の深さ":("feature","depth")}[label]
    # A single literal plus explicit unit is shorthand for the existing safe AST.
    literal=re.fullmatch(r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(mm|cm|m|inch)",expression.strip())
    if literal:expression=f"{literal[1]} * {literal[2]}"
    evaluate_parameters((Parameter("requested",expression),))
    return EditIntent("edit",node.lower(),parameter.lower(),expression)


@dataclass(frozen=True)
class EditProposal:
    proposal_id:str
    source_sha256:str
    selected_candidate_id:str
    before_fingerprint:str
    intent:EditIntent
    model_after:FeatureModel
    preview:dict


def propose_edit(session,intent:EditIntent)->EditProposal:
    if intent.action!="edit":raise ValueError("expected edit intent")
    before=session._current_output()
    value=evaluate_parameters((Parameter("requested",intent.expression),))[0].base_value
    changed=edit_parameter(session.model,intent.node_id,intent.parameter,value)
    result=recompute(changed,session.result);after=result.current_output()
    fingerprint=model_fingerprint(session.model)
    source=session.inspection.imported.source_sha256
    token=hashlib.sha256(json.dumps([source,session.selected_candidate_id,fingerprint,asdict(intent),model_fingerprint(changed)],sort_keys=True).encode()).hexdigest()[:20]
    preview={"selected_node":intent.node_id,"selected_parameter":intent.parameter,"expression":intent.expression,"value_mm":value,
             "before":asdict(before.metrics),"after":asdict(after.metrics),"comparison":compare_shapes(before.shape,after.shape),
             "expected_volume_delta":after.metrics.absolute_volume-before.metrics.absolute_volume,
             "supporting_faces":next(c.supporting_faces for c in session.inspection.candidates if c.candidate_id==session.selected_candidate_id),
             "assumptions":["selected reconstruction is user-approved","explicit length expression normalized to millimetres"],
             "recomputed_nodes":result.evaluated_nodes,"reused_nodes":result.reused_nodes,"executed":False,"confirmation_required":True}
    return EditProposal(token,source,session.selected_candidate_id,fingerprint,intent,changed,preview)


def apply_proposal(session,proposal:EditProposal,*,confirm=False):
    if confirm is not True:raise ConfirmationRequired("review the concrete proposal and explicitly confirm its ID")
    if session.inspection is None or session.model is None or session.inspection.imported.source_sha256!=proposal.source_sha256 or session.selected_candidate_id!=proposal.selected_candidate_id or model_fingerprint(session.model)!=proposal.before_fingerprint:
        raise ValueError("stale proposal: input, selection or model changed")
    session._current_output()
    # Rebuild only the frozen proposed model; failure cannot mutate the session.
    result=recompute(proposal.model_after,session.result);result.current_output()
    session.model=proposal.model_after;session.result=result
    return {"proposal_id":proposal.proposal_id,"executed":True,"model_revision":session.model.revision,
            "model_fingerprint":result.model_fingerprint,"checks_pass":True}
