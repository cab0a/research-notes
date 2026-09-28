"""Alternative reconstruction, conversational proposals and the integrated demo."""
from __future__ import annotations
import hashlib
import json
import tempfile
from pathlib import Path
from research_notes.advanced_geometry_studies import finish_study
from research_notes.modeling_studies import json_bytes
from research_notes.integrated_workflow import IntegratedSession,source_layers
from research_notes.design_proposals import review_reconstructions
from research_notes.step_reconstruction import reconstruct_step
from research_notes.conversational_proposals import parse_request
from research_notes.deterministic_recompute import model_fingerprint

ROOT=Path(__file__).resolve().parents[2]


def selected_session():
    session=IntegratedSession();session.open_step(ROOT/"fixtures/step-reconstruction/through_hole.step")
    candidate=next(c for c in session.inspection.candidates if c.explanation=="through_hole")
    session.select_candidate(candidate.candidate_id,confirm=True)
    return session


def run_design_proposals(output:Path,fixtures:Path,*,refresh=False):
    rows,detail,payloads,previews=[],[],{},[]
    for name,count in (("through_hole",2),("rib",2),("plain_plate",1),("pocket",1),("rotated_plate",0)):
        source=ROOT/"fixtures/step-reconstruction"/(name+".step");inspection=reconstruct_step(source);report=review_reconstructions(inspection)
        stable=all(p["status"]=="requires_human_selection" and p["local_edit_stability"] and all(s["status"]=="valid" for s in p["local_edit_stability"]) for p in report["alternatives"])
        rows.append({"control_id":name,"candidate_count":len(report["alternatives"]),"expected_count":count,"checks_pass":len(report["alternatives"])==count and stable and not report["automatic_selection"]})
        detail.append({"control_id":name,**report});payloads[name+".step"]=source.read_bytes();previews.append((name,inspection.imported.shape))
    return finish_study(output,fixtures,"design_proposals","v0.78.0",rows,detail,payloads,previews,
        ["multiple fitting sketch/feature DAG explanations remain separate with source binding",
         "complexity and +/-5% local dimension stability supplement geometric residuals; no recovered authoring intent",
         "selection is always explicit; rotated and unsupported feature grammars can return no proposal"],refresh)


def run_conversational_proposals(output:Path,fixtures:Path,*,refresh=False):
    rows,detail=[],[]
    session=selected_session();before=model_fingerprint(session.model)
    preview=session.ask("穴の半径を1.3 mmに")
    rows.append({"control_id":"japanese_preview","decision":"preview_only","checks_pass":model_fingerprint(session.model)==before and preview["confirmation_required"]})
    detail.append({"control_id":"japanese_preview",**preview})
    for name,action in (("confirmation_gate",lambda:session.apply(preview["proposal_id"])),
                        ("unbounded_language",lambda:session.ask("全部いい感じにして")),
                        ("code_injection",lambda:session.ask("set feature radius __import__('os').system('id')")),
                        ("invalid_dimension",lambda:session.ask("穴の半径を99 mmに"))):
        try:action();reason="unexpected_accept"
        except (ValueError,RuntimeError) as exc:reason=str(exc)
        rows.append({"control_id":name,"decision":"rejected","checks_pass":reason!="unexpected_accept" and model_fingerprint(session.model)==before});detail.append({"control_id":name,"reason":reason})
    executed=session.apply(preview["proposal_id"],confirm=True)
    rows.append({"control_id":"confirmed_apply","decision":"applied","checks_pass":executed["executed"] and model_fingerprint(session.model)!=before});detail.append(executed)
    try:session.apply(preview["proposal_id"],confirm=True);stale=False
    except ValueError:stale=True
    rows.append({"control_id":"stale_replay","decision":"rejected","checks_pass":stale})
    session.set_material(7800.);query=session.ask("質量を教えて")
    rows.append({"control_id":"mass_query","decision":"read_only","checks_pass":query["result"]["mass_kg"]>0});detail.append(query)
    requests={"supported":["inspect","質量を教えて","候補を見せて","compare","set feature radius 1.3 mm","厚さを0.5 cmに"],"unsupported":["全部いい感じにして","delete everything"]}
    return finish_study(output,fixtures,"conversational_proposals","v0.79.0",rows,detail,{"requests.json":json_bytes(requests)},[("Confirmed conversational edit",session.shape())],
        ["deterministic bounded English/Japanese intent grammar; no LLM service or arbitrary language execution",
         "preview evaluates proposed geometry without mutating the active model; confirmation is bound to source, selection and model fingerprint",
         "unknown requests, unsafe expressions, invalid dimensions and stale/replayed proposals fail closed"],refresh)


DEMO_COMMANDS="""# Run from repository root. A proposal is previewed before each explicit confirmation.
scan fixtures/semantic-pmi/semantic.step
open fixtures/step-reconstruction/through_hole.step
review
rank
analyze
select 2 --confirm
material 7800 kg/m3
ask 穴の半径を1.3 mmに
apply latest --confirm
recompute
mass
compare
export output/integrated-demo/edited.step --overwrite
report
assembly open fixtures/assembly-constraints/fully_fixed.json
assembly recompute
assembly set clearance 0 * mm
assembly recompute
assembly status
assembly report
quit
"""


def run_integrated_workflow(output:Path,fixtures:Path,*,refresh=False):
    session=selected_session();source=session.inspection.imported.source_sha256
    session.set_material(7800.);rank=session.rank();review=session.review()
    preview=session.ask("set feature radius 1.3 mm");session.apply(preview["proposal_id"],confirm=True)
    mass=session.mass();comparison=session.compare();geometry=session.analyze()
    with tempfile.TemporaryDirectory() as directory:
        target=Path(directory)/"edited.step";export=session.export_step(target);payload=target.read_bytes()
        session.report(Path(directory)/"report")
        loaded=IntegratedSession();loaded.open_step(target)
        reimport=loaded.inspection.imported.metrics
    from research_notes.assembly_controls import slider_assembly
    from research_notes.assembly_recompute import AssemblySession,assembly_record
    assembly=AssemblySession(slider_assembly());assembled=assembly.recompute()
    rows=[{"control_id":"syntax_and_semantics","result":session.layers["syntax"]["status"],"checks_pass":session.layers["syntax"]["status"]=="accepted" and session.layers["schema"]["status"]=="not_supplied"},
          {"control_id":"explicit_reconstruction","result":len(review["alternatives"]),"checks_pass":len(review["alternatives"])==2},
          {"control_id":"learned_ranking","result":rank["prediction"],"checks_pass":len(rank["ranking"])==8 and not rank["automatic_selection"]},
          {"control_id":"preview_apply_recompute","result":comparison["volume_change"],"checks_pass":comparison["volume_change"]<0},
          {"control_id":"engineering_mass","result":mass["mass_kg"],"checks_pass":mass["mass_kg"]>0},
          {"control_id":"differential_and_trim_analysis","result":len(geometry["faces"]),"checks_pass":all(f["trimming"]["checks_pass"] for f in geometry["faces"])},
          {"control_id":"verified_step_export","result":export["sha256"],"checks_pass":abs(reimport.absolute_volume-session._current_output().metrics.absolute_volume)<1e-7},
          {"control_id":"assembly_recompute","result":assembled.status,"checks_pass":assembled.status=="fully_constrained"}]
    detail={"source_sha256":source,"layers":session.layers,"reconstruction":review,"ranking":rank,"edit_preview":preview,"mass":mass,"geometry_analysis":geometry,"comparison":comparison,"export":export,
            "assembly":assembly_record(assembled),"source_history_recovered":False}
    return finish_study(output,fixtures,"integrated_workflow","v0.80.0",rows,detail,{"edited.step":payload,"demo_commands.txt":DEMO_COMMANDS.encode(),"api_example.py":API_EXAMPLE.encode()},
        [("Imported STEP",session.inspection.imported.shape),("Confirmed radius edit",session.shape())],
        ["unified API/terminal joins source stages, geometry, reconstruction, learned ranking, preview/confirmation, engineering measures, diagnostics and verified STEP export",
         "schema/application/PMI gaps remain explicit; geometry-only STEP export does not preserve source PMI or authored constraints",
         "authored assembly commands share the terminal; imported arbitrary assembly reconstruction remains outside scope",
         "integration milestone with bounded synthetic evidence, not the stable v1 contract"],refresh)


API_EXAMPLE='''from pathlib import Path
from research_notes.integrated_workflow import IntegratedSession

session = IntegratedSession()
session.open_step(Path("fixtures/step-reconstruction/through_hole.step"))
review = session.review()
proposal = next(p for p in review["alternatives"] if p["explanation"] == "through_hole")
session.select_candidate(proposal["candidate_id"], confirm=True)
session.set_material(7800, "kg/m3")
edit = session.ask("穴の半径を1.3 mmに")
print(edit)  # Inspect the concrete before/after proposal before confirming.
session.apply(edit["proposal_id"], confirm=True)
print(session.mass())
session.export_step(Path("output/integrated-api/edited.step"), overwrite=True)
session.report(Path("output/integrated-api"))
'''
