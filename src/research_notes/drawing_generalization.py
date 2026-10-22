"""Conservative visibility/section disambiguation over the frozen family parser."""
import copy,hashlib,json,math
from pathlib import Path
from . import drawing_families as base
from .drawing_to_cad import DrawingIssue,json_bytes,project_shape
from .cad_svg_import import need
from .drawing_svg_extensions import adapt_svg
from .svg_drawing_graphics import normalize,samples
TOL=.02

def build_shape(family,parameters,opening='top'):
    need(opening in ('top','bottom'),'opening_invalid','top/bottom opening required','unsupported_input')
    shape=base.build_family(family,parameters)
    if family=='pocket' and opening=='bottom':
        from OCP.gp import gp_Trsf,gp_Ax2,gp_Pnt,gp_Dir
        from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
        t=gp_Trsf();t.SetMirror(gp_Ax2(gp_Pnt(0,0,parameters['thickness']/2),gp_Dir(0,0,1)))
        shape=BRepBuilderAPI_Transform(shape,t,True).Shape()
    return shape

def export(family,parameters,opening,path):
    from .step_writer_modes import write_step
    return write_step(Path(path),source=None,mode='reconstruct',shape=build_shape(family,parameters,opening))

def recipe(f,p,opening,digest):
    return ("# Editable reconstruction recipe, not recovered authoring history.\n"
        "from research_notes.drawing_generalization import export\n"
        f"FAMILY={f!r}\nPARAMETERS={p!r}\nOPENING={opening!r}\nSOURCE_SHA256={digest!r}\n"
        "if __name__=='__main__':\n    import sys\n    export(FAMILY,PARAMETERS,OPENING,sys.argv[1])\n")

def distance(a,b):
    if not a and not b:return 0.
    if not a or not b:return None
    return max(base.directed_distance(a,b)[0],base.directed_distance(b,a)[0])

def clean_visibility(groups):
    # Coincident visible edges mask hidden edges in an orthographic view.
    visible=groups['visible'];hidden=[]
    for line in groups['hidden']:
        if not visible or base.directed_distance([line],visible)[0]>TOL:hidden.append(line)
    return dict(visible=visible,hidden=hidden)

def visible_projection(shape):
    result={}
    for role,groups in project_shape(shape).items():
        points=[p for lines in groups.values() for line in lines for p in line]
        low=[min(p[j] for p in points) for j in (0,1)]
        result[role]=clean_visibility({k:[[[p[j]-low[j] for j in (0,1)] for p in line] for line in lines] for k,lines in groups.items()})
    return result

def svg_visibility(source,inf):
    transformed,_,_=adapt_svg(source);records,_=normalize(transformed,inf['human_context']['drawing_group'])
    frames=inf['evidence']['inventory']['frames'];result={r:dict(visible=[],hidden=[]) for r in frames}
    for r in records:
        if r['tag']!='path' or r['style'].get('stroke')=='none':continue
        paths=r['paths']
        # Pocket family contains only orthogonal straight geometric edges.
        if not(len(paths)==1 and len(paths[0])==1 and paths[0][0][0]=='L'):continue
        a,b=paths[0][0][1:]
        if min(abs(a[0]-b[0]),abs(a[1]-b[1]))>.002:continue
        role=next((k for k,m in frames.items() if all(abs(x-y)<1e-8 for x,y in zip(m,r['matrix']))),None)
        if role is None:continue
        bounds=inf['evidence']['views'][role]['bounds'];pts=[(a[0],-a[1]),(b[0],-b[1])]
        if not all(bounds[j]-.002<=p[j]<=bounds[j+2]+.002 for p in pts for j in (0,1)):continue
        width=inf['parameters']['length'] if role=='right' else inf['parameters']['width']
        scale=(bounds[2]-bounds[0])/width
        line=[[(p[j]-bounds[j])/scale for j in (0,1)] for p in pts]
        dash=r['style'].get('stroke-dasharray','none')
        result[role]['visible' if dash in ('none','') else 'hidden'].append(line)
    return {r:clean_visibility(v) for r,v in result.items()}

def dxf_visibility(source,inf):
    # In this exporter, no hidden-type semantic survives; do not invent it.
    import io,ezdxf
    doc=ezdxf.read(io.StringIO(source.decode('utf-8')))
    names={e.dxf.get('linetype','BYLAYER').upper() for e in doc.modelspace() if e.dxftype()=='LINE'}
    layers={l.dxf.linetype.upper() for l in doc.layers}
    return None,dict(entity_line_types=sorted(names),layer_line_types=sorted(layers),
                     supported=False,reason='DXF visibility interpretation not established for this exporter')

def section_input(source,p):
    records,_=normalize(source,'DrawingContent')
    lines=[]
    for r in records:
        need(r['tag']=='path','section_unsupported','section contour only','unsupported_input')
        if r['style'].get('stroke')=='none':continue
        need(r['style'].get('stroke-dasharray','none') in ('none',''),'section_unsupported','section contour must be visible','unsupported_input')
        for path in r['paths']:
            need(all(s[0]=='L' for s in path),'section_unsupported','straight section only','unsupported_input')
            lines.extend([[(s[1][0],-s[1][1]),(s[2][0],-s[2][1])] for s in path])
    need(lines,'section_missing','section contour absent','input_ambiguity')
    points=[p for line in lines for p in line];low=[min(q[j] for q in points) for j in (0,1)]
    high=[max(q[j] for q in points) for j in (0,1)];scale=(high[0]-low[0])/p['length']
    need(.1<=scale<=10 and abs((high[1]-low[1])/scale-p['thickness'])<=TOL,'section_scale_conflict','section aspect ratio')
    return [[[(q[j]-low[j])/scale for j in (0,1)] for q in line] for line in lines]

def section_shape(shape,p):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Section
    from OCP.gp import gp_Pln,gp_Pnt,gp_Dir
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopoDS import TopoDS
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    cut=BRepAlgoAPI_Section(shape,gp_Pln(gp_Pnt(p['pocket_x']+p['pocket_width']/2,0,0),gp_Dir(1,0,0)),False)
    cut.Build();need(cut.IsDone(),'section_kernel_failure','section computation','kernel_calculation')
    lines=[];it=TopExp_Explorer(cut.Shape(),TopAbs_EDGE)
    while it.More():
        curve=BRepAdaptor_Curve(TopoDS.Edge_s(it.Current()));a,b=curve.FirstParameter(),curve.LastParameter()
        points=[curve.Value(a+(b-a)*i/8) for i in range(9)]
        lines.append([[q.Y(),q.Z()] for q in points]);it.Next()
    return lines

def interpret(source,context,format,section=None):
    if format=='svg' and b'DrawingContent' not in source:
        # Report an observed exporter boundary instead of pretending a view mapping is enough.
        import xml.etree.ElementTree as ET
        try:
            root=ET.fromstring(source);tags={}
            for e in root.iter():tags[e.tag.split('}')[-1]]=tags.get(e.tag.split('}')[-1],0)+1
        except ET.ParseError:return base.interpret(source,context,format)
        reason='dimension_text_unavailable' if not tags.get('text') else 'exporter_graphics_unsupported'
        return dict(status='withheld',reason_code=reason,failure_stage='unsupported_input',
            detail='No usable XML dimension text or supported view grouping. Missing annotations cannot be recovered from geometry alone; inspect the source CAD export.',
            source_sha256=hashlib.sha256(source).hexdigest(),human_context=context,input_format=format,inventory=tags)
    inf=base.interpret(source,context,format);inf['policy']='visibility_and_section_v1'
    if inf['status']!='candidate' or inf['family']!='pocket':return inf
    try:
        p=inf['parameters'];vis=svg_visibility(source,inf) if format=='svg' else None
        if format=='dxf':_,inventory=dxf_visibility(source,inf)
        else:inventory=dict(hidden_segments=sum(len(v['hidden']) for v in vis.values()),supported=True)
        available=vis is not None and any(v['hidden'] for v in vis.values())
        section_lines=section_input(section,p) if section is not None else None
        options=[]
        for opening in ('top','bottom'):
            params=copy.deepcopy(p)
            if opening=='bottom':params['pocket_depth']=p['thickness']-p['pocket_depth']
            shape=build_shape('pocket',params,opening);predicted=visible_projection(shape)
            residuals={}
            if available:
                for r in vis:
                    for k in ('visible','hidden'):residuals[r+'_'+k]=distance(vis[r][k],predicted[r][k])
            vr=all(v is not None and v<=TOL for v in residuals.values()) if available else None
            sr=distance(section_lines,section_shape(shape,params)) if section_lines is not None else None
            options.append(dict(opening=opening,parameters=params,visibility_matches=vr,visibility_residuals=residuals,
                section_residual_mm=sr,section_matches=(sr is not None and sr<=TOL) if section is not None else None,
                compatible=(vr is not False and (section is None or (sr is not None and sr<=TOL)))))
        eligible=[o for o in options if o['compatible']]
        inf.update(disambiguation=dict(visibility_available=available,visibility_inventory=inventory,alternatives=options,
            section_supplied=section is not None,section_sha256=hashlib.sha256(section).hexdigest() if section else None,
            section_assumption='single X-normal section through pocket center, Y right/Z up; human-confirmed' if section else None),
            ambiguity_boundary='two top/bottom interpretations inside the declared single rectangular pocket family; not all possible solids')
        need(available or section is not None,'opening_ambiguous','top/bottom candidates remain; hidden-line or section evidence needed','input_ambiguity')
        need(len(eligible)>0,'visibility_section_conflict','neither opening explains the line types/section','drawing_conflict')
        need(len(eligible)==1,'opening_ambiguous','more than one opening explains the evidence','input_ambiguity')
        chosen=eligible[0]
        inf['dimension_interpretation']=dict(top_reference_distance_mm=p['pocket_depth'],
            actual_depth_mm=chosen['parameters']['pocket_depth'],
            depth_derivation='thickness - top_reference_distance' if chosen['opening']=='bottom' else 'top_reference_distance')
        inf['bindings']['top_reference_distance']=inf['bindings']['pocket_depth']
        if chosen['opening']=='bottom':inf['bindings']['pocket_depth']=['derived: thickness - top_reference_distance']
        inf.update(parameters=chosen['parameters'],opening=chosen['opening'])
        inf['projection_metrics'],inf['reprojection']=base.reprojection(inf['raw_views'],build_shape('pocket',chosen['parameters'],chosen['opening']))
        return inf
    except DrawingIssue as e:
        for key in ('parameters','family','reprojection','raw_views','bindings','projection_metrics'):inf.pop(key,None)
        return {**inf,'status':'withheld','reason_code':e.code,'failure_stage':e.stage,'detail':str(e)}
    except Exception as e:
        return dict(status='withheld',reason_code='disambiguation_failure',failure_stage='kernel_or_evidence',
                    detail=type(e).__name__+': '+str(e),source_sha256=hashlib.sha256(source).hexdigest(),human_context=context)

def main(argv=None):
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('drawing',type=Path);p.add_argument('context',type=Path)
    p.add_argument('--section',type=Path);p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args(argv);a.output_dir.mkdir(parents=True,exist_ok=False)
    inf=interpret(a.drawing.read_bytes(),json.loads(a.context.read_text()),a.drawing.suffix[1:],a.section.read_bytes() if a.section else None)
    (a.output_dir/'inference.json').write_bytes(json_bytes(inf))
    if inf['status']=='candidate':
        (a.output_dir/'candidate.py').write_text(recipe(inf['family'],inf['parameters'],inf.get('opening','top'),inf['source_sha256']))
        (a.output_dir/'model.json').write_bytes(json_bytes({k:inf.get(k) for k in ('family','parameters','opening','bindings','source_sha256')}))
if __name__=='__main__':main()
