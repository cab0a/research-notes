"""Integrated bounded STEP, semantics, geometry, measurement and proposal workspace."""
from __future__ import annotations
import hashlib
import html
import json
from dataclasses import asdict
from pathlib import Path
from research_notes.assisted_modeling import ModelingSession
from research_notes.spatial_workflow import WorkBudget,inspect_step_stages
from research_notes.semantic_pmi import inspect_pmi
from research_notes.ap242_paths import AP242_SCHEMA_IDENTIFIER,resolve_ap242_product_paths
from research_notes.step_express_validation import inspect_step_express_validation
from research_notes.design_proposals import review_reconstructions
from research_notes.conversational_proposals import parse_request,propose_edit,apply_proposal
from research_notes.engineering_analysis import mass_properties,proximity
from research_notes.representation_learning import RepresentationModel,predict_representation
from research_notes.learning_studies import ranking_descriptor
from research_notes.brep_preview import write_shape_previews
from research_notes.modeling_studies import json_bytes


def source_layers(path:Path,*,schema_path:Path|None=None,budget=WorkBudget()):
    staged,document=inspect_step_stages(path,budget)
    report={"syntax":staged,"schema":{"status":"not_supplied","full_ap_conformance":False},"application_semantics":{"status":"not_reached"}}
    if document is None:return report
    source=document.source_text.encode()
    if schema_path:
        with Path(schema_path).open("rb") as stream:schema=stream.read(2_000_001)
        if len(schema)>2_000_000:raise ValueError("EXPRESS input byte budget")
        report["schema"]={"source_sha256":hashlib.sha256(schema).hexdigest(),"validation":asdict(inspect_step_express_validation(source,schema)),"full_ap_conformance":False}
    report["pmi"]=inspect_pmi(document)
    if document.schema_identifiers==(AP242_SCHEMA_IDENTIFIER,):
        paths=resolve_ap242_product_paths(source)
        report["application_semantics"]={"status":paths.decision,"reason":paths.reason_code,"paths":[asdict(p) for p in paths.paths],"diagnostics":[asdict(d) for d in paths.diagnostics]}
    else:report["application_semantics"]={"status":"unsupported_schema","declared_schemas":list(document.schema_identifiers)}
    return report


class IntegratedSession(ModelingSession):
    def __init__(self):
        super().__init__();self.layers={};self.material=None;self.proposals={};self.latest_proposal=None;self.rank_result=None;self.export_record=None;self.applied_proposals=set()

    def open_step(self,path:Path):
        layers=source_layers(path)
        if layers["syntax"]["status"]!="accepted":raise ValueError("STEP preflight: "+layers["syntax"]["reason"])
        candidate=ModelingSession();candidate.open_step(path)
        if candidate.inspection.imported.source_sha256!=layers["syntax"]["source_sha256"]:raise ValueError("source changed during import")
        self.__dict__.update(candidate.__dict__)
        self.layers=layers;self.material=None;self.proposals={};self.latest_proposal=None;self.rank_result=None;self.export_record=None;self.applied_proposals=set()
        return self.inspect()

    def inspect(self):
        return {**super().inspect(),"layers":self.layers}

    def open_step_for_inspection(self,path:Path):
        """Open broader public geometry without creating editable candidates."""
        from research_notes.public_step import read_step_for_inspection
        from research_notes.step_reconstruction import ReconstructionResult
        layers=source_layers(path)
        inspected=read_step_for_inspection(path)
        if inspected.imported.source_sha256!=layers["syntax"]["source_sha256"]:
            raise ValueError("source changed during import")
        candidate=IntegratedSession()
        candidate.source_path=Path(path).resolve()
        candidate.inspection=ReconstructionResult(inspected.imported,(),(),(),"inspection_only",
            "geometry inspection only; no editable history or assembly constraints inferred")
        candidate.layers=layers
        candidate.layers["native_geometry"]={"transferred_roots":inspected.roots,
            "unit_contexts":list(inspected.unit_contexts),"length_unit":"mm","mode":"inspection_only"}
        self.__dict__.update(candidate.__dict__)
        return self.inspect()

    def export_inspected_step(self,path,*,overwrite=False):
        from research_notes.public_step import export_inspected_geometry
        if self.inspection is None or self.inspection.status!="inspection_only":
            raise ValueError("open with --inspect-only before inspection export")
        self.export_record=export_inspected_geometry(self.inspection.imported,self.source_path,path,overwrite=overwrite)
        return self.export_record

    def select_candidate(self,identifier,*,confirm=False):
        result=super().select_candidate(identifier,confirm=confirm)
        self.rank_result=None;self.export_record=None
        return result

    def edit(self,node_id,parameter,value):
        result=super().edit(node_id,parameter,value)
        self.rank_result=None;self.export_record=None
        return result

    def recompute(self):
        result=super().recompute()
        self.rank_result=None;self.export_record=None
        return result

    def schema(self,path):
        if self.inspection is None:raise ValueError("open a STEP file first")
        # Validate immutable imported bytes, not a later file revision.
        with Path(path).open("rb") as stream:source=stream.read(2_000_001)
        if len(source)>2_000_000:raise ValueError("schema budget")
        self.layers["schema"]={"source_sha256":hashlib.sha256(source).hexdigest(),"validation":asdict(inspect_step_express_validation(self.inspection.imported.source_bytes,source)),"full_ap_conformance":False}
        return self.layers["schema"]

    def shape(self):
        if self.model:return self._current_output().shape
        if self.inspection:return self.inspection.imported.shape
        raise ValueError("open a STEP file first")

    def set_material(self,density,unit="kg/m3"):
        mass_properties(self.shape(),density=density,density_unit=unit)
        self.material=(density,unit)
        return self.mass()

    def mass(self):
        if self.material is None:raise ValueError("set explicit material density first: material 7800 kg/m3")
        return mass_properties(self.shape(),density=self.material[0],density_unit=self.material[1])

    def review(self):
        if self.inspection is None:raise ValueError("open a STEP file first")
        return review_reconstructions(self.inspection)

    def analyze(self):
        if self.inspection is not None and self.inspection.status=="inspection_only":
            from research_notes.public_step import analyze_public_shape
            return analyze_public_shape(self.shape())
        from OCP.BRepAdaptor import BRepAdaptor_Surface
        from OCP.BRepClass import BRepClass_FaceClassifier
        from OCP.gp import gp_Pnt2d
        from OCP.TopAbs import TopAbs_FACE,TopAbs_REVERSED,TopAbs_IN,TopAbs_ON
        from OCP.TopoDS import TopoDS
        from OCP.GeomAbs import GeomAbs_BSplineSurface
        from research_notes.brep_runtime import indexed_shapes
        from research_notes.differential_geometry import surface_differential
        from research_notes.intersection_analysis import inspect_trimming
        from research_notes.spline_geometry import surface_record
        faces=indexed_shapes(self.shape(),TopAbs_FACE);rows=[]
        if faces.Extent()>256:raise ValueError("face analysis budget: 256")
        for i in range(1,faces.Extent()+1):
            face=TopoDS.Face_s(faces.FindKey(i));surface=BRepAdaptor_Surface(face,True)
            u=(surface.FirstUParameter()+surface.LastUParameter())/2;v=(surface.FirstVParameter()+surface.LastVParameter())/2
            classifier=BRepClass_FaceClassifier(face,gp_Pnt2d(u,v),1e-7)
            inside=classifier.State() in {TopAbs_IN,TopAbs_ON}
            row={"face_index":i,"support_type":str(surface.GetType()),"sample_within_trim":inside,
                 "differential":surface_differential(surface,u,v,orientation=-1 if face.Orientation()==TopAbs_REVERSED else 1),"trimming":inspect_trimming(face)}
            if surface.GetType()==GeomAbs_BSplineSurface:row["spline"]=surface_record(surface.BSpline())
            rows.append(row)
        return {"faces":rows,"scope":"support samples outside trims are labeled; differential and sampled trim evidence remain separate"}

    def rank(self):
        if self.inspection is not None and self.inspection.status=="inspection_only":
            return {"decision":"not_evaluated","ranking":[],"automatic_selection":False,
                    "reason":"public inspection shapes are outside the trained synthetic ranking contract"}
        path=Path(__file__).resolve().parents[2]/"fixtures/candidate-ranking/model.json"
        payload=json.loads(path.read_text())
        model=RepresentationModel(**{**payload,"labels":tuple(payload["labels"]),"means":tuple(payload["means"]),"scales":tuple(payload["scales"]),"centroids":tuple(map(tuple,payload["centroids"])),"feature_names":tuple(payload["feature_names"]),"train_ids":tuple(payload["train_ids"]),"validation_ids":tuple(payload["validation_ids"])})
        values,support=ranking_descriptor(self.shape())
        self.rank_result={**predict_representation(model,values),"support":support,"source_sha256":self.inspection.imported.source_sha256,
                          "model_fingerprint":self.result.model_fingerprint if self.model else None,"automatic_selection":False}
        return self.rank_result

    def ask(self,request):
        intent=parse_request(request)
        if intent.action=="inspect":return {"action":"inspect","result":self.inspect()}
        if intent.action=="mass":return {"action":"mass","result":self.mass()}
        if intent.action=="candidates":return {"action":"candidates","result":self.review()}
        if intent.action=="compare":return {"action":"compare","result":self.compare()}
        proposal=propose_edit(self,intent);self.proposals[proposal.proposal_id]=proposal;self.latest_proposal=proposal.proposal_id
        return {"proposal_id":proposal.proposal_id,**proposal.preview}

    def apply(self,identifier,*,confirm=False):
        if identifier=="latest":identifier=self.latest_proposal
        if identifier not in self.proposals:raise ValueError("unknown proposal ID")
        result=apply_proposal(self,self.proposals[identifier],confirm=confirm)
        self.applied_proposals.add(identifier)
        self.rank_result=None;self.export_record=None
        return result

    def export_step(self,path,*,overwrite=False):
        self.export_record=super().export_step(path,overwrite=overwrite)
        self.export_record["pmi_policy"]="geometry only; source semantic PMI must be reviewed and rebound after edits"
        return self.export_record

    def report(self,directory):
        shape=self.shape();directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
        entries=[("Imported STEP",self.inspection.imported.shape)]
        if self.model:entries.append((f"Current revision {self.model.revision}",shape))
        report={"version":"0.81.0","layers":self.layers,"session":self.status(),"material":self.material,"mass":self.mass() if self.material else None,
                "reconstruction":self.review(),"candidate_ranking":self.rank(),"geometry_analysis":self.analyze(),"comparison":self.compare() if self.model else None,
                "proposals":[{"proposal_id":p.proposal_id,"before_fingerprint":p.before_fingerprint,"execution_status":"applied" if p.proposal_id in self.applied_proposals else "unapplied","preview":p.preview} for p in self.proposals.values()],
                "export":self.export_record,"source_history_recovered":False}
        write_shape_previews(directory/"workflow.png",tuple(entries),title="Integrated STEP analysis and modeling",columns=len(entries))
        # SI mass/inertia values can be far smaller than 1e-9; preserve them in the report.
        (directory/"workflow.json").write_text(json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8")
        mass=report["mass"]
        mass_text=f"{mass['mass_kg']:.9g} kg" if mass else "Material density not supplied"
        candidates=report["reconstruction"]["alternatives"]
        candidate_rows="".join(f"<tr><td>{html.escape(c['explanation'].replace('_',' '))}</td><td>{c['complexity']['nodes']}</td><td>{c['fit']['material_difference_volume']:.3g}</td><td>{'Selected in this session' if c['candidate_id']==self.selected_candidate_id else 'Alternative proposal'}</td></tr>" for c in candidates)
        ranking=report["candidate_ranking"]
        ranking_rows="".join(f"<tr><td>{html.escape(r['label'])}</td><td>{r['probability']:.1%}</td></tr>" for r in ranking["ranking"])
        analysis=report["geometry_analysis"]
        analysis_text=(f"Analyzed {analysis['analyzed_face_count']} of {analysis['face_count']} faces; "
                       f"{analysis['omitted_face_count']} omitted by budget; {analysis['trim_check_failures']} sampled trim checks failed. "
                       "A completed analysis is not a validity certificate.") if "analyzed_face_count" in analysis else "Detailed face observations are available in the JSON evidence."
        modeling_text="Inspection only: no editable candidates were inferred." if self.inspection.status=="inspection_only" else "Alternative feature histories can explain the same shape. Original authoring history is not recovered."
        ranking_text=ranking.get("reason","Calibrated on synthetic controls; public generalization is not established.")
        stages=[("STEP syntax",self.layers["syntax"]["status"]),("Schema",self.layers["schema"].get("status",self.layers["schema"].get("validation",{}).get("decision","deferred"))),
                ("Application semantics",self.layers["application_semantics"]["status"]),("Semantic PMI",self.layers["pmi"].get("status","unsupported_schema")),
                ("Model",f"Confirmed revision {self.model.revision}" if self.model else "Inspection only" if self.inspection.status=="inspection_only" else "Awaiting proposal selection")]
        status_labels={"accepted":"Parsed successfully","not_supplied":"Schema not provided","unsupported_schema":"Outside supported AP mapping","no_supported_pmi":"No supported semantic PMI","observed":"Semantic records found","partial":"Partial evidence"}
        cards="".join(f'<div class="card"><span>{html.escape(k)}</span><strong>{html.escape(status_labels.get(str(v),str(v)))}</strong></div>' for k,v in stages)
        page=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>3D analysis workspace</title>
<style>body{{margin:0;background:#f3f6f9;color:#193246;font:16px system-ui}}main{{max-width:1240px;margin:auto;padding:32px}}h1{{font-size:36px;margin:8px 0}}.eyebrow{{color:#187b85;font-weight:700;letter-spacing:2px}}.cards{{display:flex;flex-wrap:wrap;gap:12px;margin:24px 0}}.card,section{{background:white;border:1px solid #d8e2ea;border-radius:12px;padding:20px}}.card{{flex:1;min-width:140px}}.card span{{font-size:13px;color:#647789;display:block}}.card strong{{display:block;margin-top:8px}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}section{{margin:20px 0}}table{{width:100%;border-collapse:collapse}}td,th{{text-align:left;padding:10px;border-bottom:1px solid #e4eaf0}}img{{width:100%}}a{{color:#146d79}}code{{overflow-wrap:anywhere;font-size:12px}}@media(max-width:800px){{.grid{{display:block}}}}</style>
<main><div class="eyebrow">RESEARCH WORKSPACE / v0.81.0</div><h1>3D analysis & modeling</h1><p>{html.escape(self.inspection.imported.file_name)} · Mass: <b>{mass_text}</b></p>
<div class="cards">{cards}</div><section><h2>Geometry comparison</h2><img src="workflow.png" alt="Imported and current B-Rep geometry"><p>{html.escape(analysis_text)}</p></section>
<div class="grid"><section><h2>Editable reconstruction proposals</h2><table><tr><th>Explanation</th><th>Nodes</th><th>Fit residual</th><th>Adoption</th></tr>{candidate_rows}</table><p>{html.escape(modeling_text)}</p></section>
<section><h2>Learned candidate ranking</h2><p>Decision: <b>{html.escape(ranking['decision'])}</b> · {html.escape(ranking_text)}</p><table><tr><th>Candidate</th><th>Score</th></tr>{ranking_rows}</table><p>Ranking does not select or edit a model.</p></section></div>
<section><h2>Evidence and exchange</h2><p>Source SHA-256: <code>{self.inspection.imported.source_sha256}</code></p><p>STEP export preserves verified shape geometry. Source names, PMI and constraints require separate review.</p><a href="workflow.json">Complete source, measurement, proposal and recompute evidence</a></section></main></html>'''
        (directory/"workflow.html").write_text(page,encoding="utf-8")
        return {"report":str(directory/"workflow.html"),"evidence":str(directory/"workflow.json")}
