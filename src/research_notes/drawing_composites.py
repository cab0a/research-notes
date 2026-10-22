"""Bounded compound plate reconstruction from graphical dimensions and explicit review."""
import copy,hashlib,itertools,json,math
from pathlib import Path
from .drawing_to_cad import DrawingIssue,json_bytes,project_shape
from .cad_svg_import import need,close
from .drawing_families import unique,reprojection,directed_distance
from .drawing_composite_evidence import svg_evidence,dxf_evidence
from .drawing_svg_extensions import adapt_svg
from .svg_drawing_graphics import normalize,samples,EPS
from .drawing_generalization import clean_visibility,visible_projection,distance

def validate(p):
    need(set(p)=={'width','length','thickness','features'},'parameter_schema','stock and feature list required')
    need(all(type(p[k]) in (int,float) and math.isfinite(p[k]) and .01<p[k]<=1000 for k in ('width','length','thickness')),'invalid_dimension','bounded stock')
    need(isinstance(p['features'],list) and 1<=len(p['features'])<=3,'unsupported_composition','one to three separated cuts','unsupported_input')
    boxes=[];rects=0
    for f in p['features']:
        kind=f.get('kind');keys={'kind','x','y','diameter'} if kind=='hole' else {'kind','x','y','width','length','depth'}
        need(kind in ('hole','pocket','step') and set(f) in (keys,keys|({'opening'} if kind!='hole' else set())),'unsupported_composition','round through hole, rectangular pocket or corner step','unsupported_input')
        need(f.get('opening','top') in ('top','bottom'),'unsupported_composition','Z-axis openings only','unsupported_input')
        need(all(type(v) in (int,float) and math.isfinite(v) and 0<=v<=1000 for k,v in f.items() if k not in ('kind','opening')),'invalid_dimension','finite nonnegative feature dimensions')
        x,y=f['x'],f['y']
        if kind=='hole':
            r=f['diameter']/2;need(r>.001 and r<x<p['width']-r and r<y<p['length']-r,'invalid_dimension','internal hole')
            box=(x-r,y-r,x+r,y+r)
        else:
            rects+=1;a,b,d=f['width'],f['length'],f['depth']
            need(min(a,b,d)>.001 and d<p['thickness'] and x+a<p['width'] and y+b<p['length'],'invalid_dimension','blind cut inside stock envelope')
            need((kind=='pocket' and min(x,y)>0) or (kind=='step' and x==y==0),'unsupported_composition','internal pocket or lower-left corner step only','unsupported_input')
            box=(x,y,x+a,y+b)
        need(all(box[2]<o[0]-1e-6 or o[2]<box[0]-1e-6 or box[3]<o[1]-1e-6 or o[3]<box[1]-1e-6 for o in boxes),
             'intersecting_features','overlapping/touching cut envelopes are not supported','unsupported_input')
        boxes.append(box)
    need(rects<=2,'unsupported_composition','at most two rectangular cuts','unsupported_input')

def build(p):
    validate(p)
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox,BRepPrimAPI_MakeCylinder
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCP.gp import gp_Pnt,gp_Ax2,gp_Dir
    from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
    s=BRepPrimAPI_MakeBox(p['width'],p['length'],p['thickness']).Shape()
    for f in p['features']:
        if f['kind']=='hole':tool=BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(f['x'],f['y'],0),gp_Dir(0,0,1)),f['diameter']/2,p['thickness']).Shape()
        else:tool=BRepPrimAPI_MakeBox(gp_Pnt(f['x'],f['y'],0 if f.get('opening','top')=='bottom' else p['thickness']-f['depth']),f['width'],f['length'],f['depth']).Shape()
        cut=BRepAlgoAPI_Cut(s,tool);cut.Build();need(cut.IsDone(),'kernel_failure','cut failed','kernel_calculation');s=cut.Shape()
    u=ShapeUpgrade_UnifySameDomain(s,True,True,False);u.Build();return u.Shape()

def export(p,path):
    from .step_writer_modes import write_step
    return write_step(Path(path),source=None,mode='reconstruct',shape=build(p))

def recipe(p,digest):
    return ('# Editable reconstructed cuts; not recovered authoring history.\nfrom research_notes.drawing_composites import export\n'
            f'PARAMETERS={p!r}\nSOURCE_SHA256={digest!r}\n'
            "if __name__=='__main__':\n    import sys\n    export(PARAMETERS,sys.argv[1])\n")

def edit(p):
    p=copy.deepcopy(p);p['width']+=4;p['thickness']+=1
    rect=next(f for f in p['features'] if f['kind']!='hole');rect['width']+=1;rect['depth']+=.5
    for f in p['features']:
        if f['kind']=='hole':f['x']+=.5;f['diameter']+=.5
    return p

def rectangles(view):
    lines=view['lines'];bounds=view['bounds'];xs=unique(q[0] for l in lines for q in l);ys=unique(q[1] for l in lines for q in l)
    need(len(xs)<=16 and len(ys)<=16,'unsupported_profile','bounded orthogonal profile','unsupported_input')
    def covered(a,b):
        axis=0 if abs(a[1]-b[1])<=EPS else 1;j=1-axis;lo,hi=sorted((a[axis],b[axis]));intervals=[]
        for c,d in lines:
            if abs(c[j]-a[j])<=EPS and abs(d[j]-a[j])<=EPS:intervals.append(sorted((c[axis],d[axis])))
        end=lo
        for start,stop in sorted(intervals):
            if start>end+EPS:continue
            if stop>end:end=stop
        return end>=hi-EPS
    result=[]
    for x0,x1 in itertools.combinations(xs,2):
        for y0,y1 in itertools.combinations(ys,2):
            rect=(x0,y0,x1,y1)
            if close(rect,bounds):continue
            corners=[(x0,y0),(x1,y0),(x1,y1),(x0,y1)]
            if all(covered(a,b) for a,b in zip(corners,corners[1:]+corners[:1])):result.append(rect)
    need(1<=len(result)<=2,'unsupported_profile','one or two distinct rectangular feature contours required','unsupported_input')
    return sorted(result)

def visibility(source,evidence,context,p):
    converted,_,_=adapt_svg(source);records,_=normalize(converted,context['drawing_group']);frames=evidence['inventory']['frames']
    groups={r:dict(visible=[],hidden=[]) for r in frames}
    for record in records:
        if record['tag']!='path' or record['style'].get('stroke')=='none':continue
        paths=record['paths']
        if len(paths)!=1:continue
        path=paths[0]
        if len(path)==1 and path[0][0]=='L':
            a,b=path[0][1:]
            if min(abs(a[0]-b[0]),abs(a[1]-b[1]))>EPS:continue
            points=[a,b]
        elif all(s[0]=='C' for s in path):points=[q for s in path for q in samples(s)]
        else:continue
        role=next((r for r,m in frames.items() if all(abs(a-b)<1e-8 for a,b in zip(m,record['matrix']))),None)
        if role is None:continue
        b=evidence['views'][role]['bounds'];points=[(q[0],-q[1]) for q in points]
        if not all(b[j]-EPS<=q[j]<=b[j+2]+EPS for q in points for j in (0,1)):continue
        scale=(b[2]-b[0])/p['length' if role=='right' else 'width']
        line=[[(q[j]-b[j])/scale for j in (0,1)] for q in points]
        key='visible' if record['style'].get('stroke-dasharray','none') in ('','none') else 'hidden'
        groups[role][key].append(line)
    return {r:clean_visibility(v) for r,v in groups.items()}

def interpret(source,context,format,review=None):
    digest=hashlib.sha256(source).hexdigest();out=dict(source_sha256=digest,input_format=format,human_context=context,
        method='bounded_compound_plate_graphical_dimensions',ai_used=False,original_history_recovered=False)
    evidence=None
    try:
        need(isinstance(source,bytes) and 0<len(source)<=500000,'input_format','bounded drawing','unsupported_input')
        fields={'unit','projection','family_assumption','view_roles'}|({'drawing_group'} if format=='svg' else set())
        need(isinstance(context,dict) and set(context)==fields,'context_missing','nonnumeric context only','input_ambiguity')
        need(context['unit']=='mm' and context['family_assumption']=='axis_aligned_machined_plate','unsupported_context','declare Z-axis machined plate candidate family','unsupported_input')
        need(context['projection'] in ('first_angle','third_angle'),'projection_unknown','projection required','input_ambiguity')
        roles=context['view_roles'];need(set(roles)=={'front','top','right'} and all(isinstance(v,str) for v in roles.values()) and len(set(roles.values()))==3,'view_mapping','three distinct view IDs','input_ambiguity')
        need(format in ('svg','dxf'),'input_format','SVG/DXF only','unsupported_input')
        choices={}
        if review is not None:
            need(isinstance(review,dict) and set(review)=={'drawing_sha256','labels'} and review['drawing_sha256']==digest,
                 'review_source_mismatch','review must bind this exact drawing','input_ambiguity')
            choices=review['labels'];need(format=='svg' and isinstance(choices,dict) and all(isinstance(k,str) and isinstance(v,str) for k,v in choices.items()),'review_choice_invalid','IDs only; no numeric overrides','input_ambiguity')
        try:evidence=svg_evidence(source,context,choices) if format=='svg' else dxf_evidence(source,context)
        except DrawingIssue:raise
        except Exception as e:raise DrawingIssue('drawing_parse_failure','drawing_recognition',type(e).__name__+': '+str(e)) from e
        views=evidence['views'];dims=evidence['dimensions'];bindings={}
        def measure(role,axis,a,b,key):
            matches=[d for d in dims if d['kind']=='linear' and d['view']==role and d['axis']==axis and close(sorted(q[axis] for q in d['points']),sorted((a,b)))]
            need(matches,'dimension_missing',key+' requires an explicit dimension','input_ambiguity')
            values=[d['value'] for d in matches];need(max(values)-min(values)<=1e-6,'dimension_conflict',key)
            bindings[key]=[d['id'] for d in matches];return values[0]
        def full(role,axis,key):
            b=views[role]['bounds'];return measure(role,axis,b[axis],b[axis+2],key)
        p=dict(width=full('top',0,'width'),length=full('top',1,'length'),thickness=full('front',1,'thickness'),features=[])
        need(abs(full('front',0,'front.width')-p['width'])<1e-6 and abs(full('right',0,'right.length')-p['length'])<1e-6 and abs(full('right',1,'right.thickness')-p['thickness'])<1e-6,'dimension_conflict','envelopes disagree')
        extents={'top':(p['width'],p['length']),'front':(p['width'],p['thickness']),'right':(p['length'],p['thickness'])};scales={};raw={}
        for role,v in views.items():
            b=v['bounds'];s=(b[2]-b[0])/extents[role][0];scales[role]=s
            need(.1<=s<=10 and abs(b[3]-b[1]-extents[role][1]*s)<=EPS,'geometry_dimension_conflict','view aspect/scale')
            raw[role]=[[[(q[j]-b[j])/s for j in (0,1)] for q in line] for line in v['raw']]
        for d in dims:
            span=abs(d['points'][1][d['axis']]-d['points'][0][d['axis']]) if d['kind']=='linear' else math.dist(*d['points'])
            need(abs(span/scales[d['view']]-d['value'])<=EPS/scales[d['view']],'geometry_dimension_conflict','dimension does not explain drawing: '+d['id'])
        centers={r:((v['bounds'][0]+v['bounds'][2])/2,(v['bounds'][1]+v['bounds'][3])/2) for r,v in views.items()}
        a,b,c=(centers[r] for r in ('front','top','right'));sign=1 if context['projection']=='third_angle' else -1
        need((b[1]-a[1])*sign>0 and (c[0]-a[0])*sign>0 and abs(a[0]-b[0])<=EPS and abs(a[1]-c[1])<=EPS,'projection_layout_conflict','view layout disagrees')
        top=views['top'];tb=top['bounds'];fb=views['front']['bounds']
        for i,r in enumerate(rectangles(top)):
            prefix=f'feature_{i+1}.';x0,y0,x1,y1=r
            x=0. if abs(x0-tb[0])<=EPS else measure('top',0,tb[0],x0,prefix+'x')
            y=0. if abs(y0-tb[1])<=EPS else measure('top',1,tb[1],y0,prefix+'y')
            w=measure('top',0,x0,x1,prefix+'width');l=measure('top',1,y0,y1,prefix+'length')
            matches=[]
            for d in dims:
                if d['kind']!='linear' or d['view']!='front' or d['axis']!=1:continue
                high,low=sorted(d['points'],key=lambda q:q[1],reverse=True)
                xx=(low[0]-fb[0])/scales['front'];z=(low[1]-fb[1])/scales['front']
                if abs(high[1]-fb[3])<=EPS and EPS<z<p['thickness']-EPS and x-EPS<=xx<=x+w+EPS:matches.append(d)
            need(len(matches)==1,'feature_depth_ambiguous',prefix+'one depth dimension anchored to this front projection required','input_ambiguity')
            d=matches[0];bindings[prefix+'depth']=[d['id']]
            p['features'].append(dict(kind='step' if x==y==0 else 'pocket',x=x,y=y,width=w,length=l,depth=d['value']))
        for circle in sorted(top['circles'],key=lambda c:tuple(c['center'])):
            prefix=f'feature_{len(p["features"])+1}.'
            matches=[d for d in dims if d['kind']=='diameter' and d['view']=='top' and d['circle_id']==circle['id']]
            need(len(matches)==1 and matches[0]['through'] and matches[0]['count']==1,'hole_extent_ambiguous','one explicit THRU diameter per hole','input_ambiguity')
            d=matches[0];bindings[prefix+'diameter']=[d['id']]
            p['features'].append(dict(kind='hole',x=measure('top',0,tb[0],circle['center'][0],prefix+'x'),
                y=measure('top',1,tb[1],circle['center'][1],prefix+'y'),diameter=d['value']))
        validate(p);out.update(evidence=evidence,bindings=bindings,feature_hypotheses=p['features'],review_selections=choices)
        need(format=='svg','opening_evidence_missing','this DXF route does not establish visible/hidden edge semantics; do not assume top openings','input_ambiguity')
        try:
            observed=visibility(source,evidence,context,p);indices=[i for i,f in enumerate(p['features']) if f['kind']!='hole'];options=[];candidates=[]
            for directions in itertools.product(('top','bottom'),repeat=len(indices)):
                candidate=copy.deepcopy(p)
                for i,opening in zip(indices,directions):
                    f=candidate['features'][i];f['opening']=opening
                    if opening=='bottom':f['depth']=p['thickness']-f['depth']
                shape=build(candidate);m,projected=reprojection(raw,shape);predicted=visible_projection(shape)
                vm={r+'_'+k:distance(observed[r][k],predicted[r][k]) for r in observed for k in ('visible','hidden')}
                compatible=max(v['sampled_symmetric_max_mm'] for v in m.values())<=.02 and all(v is not None and v<=.02 for v in vm.values())
                options.append(dict(openings=list(directions),visibility_residual_mm=vm,compatible=compatible))
                if compatible:candidates.append((candidate,m,projected,vm))
        except DrawingIssue:raise
        except Exception as e:raise DrawingIssue('kernel_failure','kernel_calculation',type(e).__name__+': '+str(e)) from e
        out['opening_alternatives']=options
        need(len(candidates)==1,'visibility_conflict' if not candidates else 'opening_ambiguous','exactly one opening combination must explain all contours and line types','input_ambiguity')
        chosen,m,projected,vm=candidates[0]
        for i,f in enumerate(chosen['features']):
            if f.get('opening')=='bottom':bindings[f'feature_{i+1}.depth']=['derived: thickness - '+v for v in bindings[f'feature_{i+1}.depth']]
        return {**out,'status':'candidate','family':'composite','opening':'bottom' if all(f.get('opening','bottom')=='bottom' for f in chosen['features']) else 'top',
            'parameters':chosen,'raw_views':raw,'reprojection':projected,'projection_metrics':m,'visibility_residual_mm':vm,
            'claim_boundary':'Declared separated Z-axis cuts in a stock plate; manual view/family, not arbitrary complex CAD or authoring history'}
    except DrawingIssue as e:
        return {**out,'status':'withheld','reason_code':e.code,'failure_stage':e.stage,'detail':str(e),'evidence':evidence,
                'review_request':getattr(e,'review_request',None)}
    except Exception as e:return {**out,'status':'withheld','reason_code':'processing_failure','failure_stage':'drawing_or_kernel','detail':type(e).__name__+': '+str(e)}

def main(argv=None):
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('drawing',type=Path);p.add_argument('context',type=Path)
    p.add_argument('--review',type=Path);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args(argv)
    a.output_dir.mkdir(parents=True,exist_ok=False)
    with a.drawing.open('rb') as stream:source=stream.read(500001)
    result=interpret(source,json.loads(a.context.read_text()),a.drawing.suffix[1:].lower(),json.loads(a.review.read_text()) if a.review else None)
    (a.output_dir/'inference.json').write_bytes(json_bytes(result))
    if result['status']=='candidate':
        (a.output_dir/'candidate.py').write_text(recipe(result['parameters'],result['source_sha256']))
        (a.output_dir/'model.json').write_bytes(json_bytes({k:result[k] for k in ('parameters','bindings','source_sha256','review_selections')}))
if __name__=='__main__':main()
