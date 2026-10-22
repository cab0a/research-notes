"""Bounded machining reconstruction; graphical dimensions, chain paths and bore callouts."""
import copy,hashlib,itertools,json,math
from pathlib import Path
from .drawing_to_cad import DrawingIssue,json_bytes
from .cad_svg_import import need,close
from .svg_drawing_graphics import EPS
from .drawing_families import unique,reprojection
from .drawing_generalization import visible_projection,distance
from .drawing_composites import visibility
from .drawing_machining_annotations import callout
from .drawing_machining_evidence import svg_evidence,dxf_evidence

AXES={'top':'z','right':'x','front':'y'}
SPAN={'x':'width','y':'length','z':'thickness'}
def cross_size(p,axis):return {'z':(p['width'],p['length']),'x':(p['length'],p['thickness']),'y':(p['width'],p['thickness'])}[axis]
def validate(p):
    need(isinstance(p,dict) and set(p)=={'width','length','thickness','features'},'parameter_schema','stock and features required')
    need(all(type(p[k]) in (int,float) and math.isfinite(p[k]) and .01<p[k]<=1000 for k in SPAN.values()),'invalid_dimension','bounded positive stock')
    fs=p['features'];need(isinstance(fs,list) and 1<=len(fs)<=4,'unsupported_composition','one to four bounded features')
    need(sum(f.get('kind')=='pocket' for f in fs)<=1,'unsupported_composition','one pocket at most')
    for f in fs:
        kind=f.get('kind')
        keys={'kind','x','y','width','length','depth','opening'} if kind=='pocket' else (
            {'kind','axis','u','v','diameter','counter_diameter','counter_depth','entry'} if kind=='counterbore' else
            {'kind','axis','u','v','diameter','extent'}|({'depth','entry'} if f.get('extent')=='blind' else set()))
        need(kind in ('pocket','bore','counterbore') and set(f)==keys,'unsupported_composition','unsupported feature schema','unsupported_input')
        numeric={k:v for k,v in f.items() if k not in ('kind','opening','axis','extent','entry')}
        need(all(type(v) in (int,float) and math.isfinite(v) and 0<v<=1000 for v in numeric.values()),'invalid_dimension','finite positive feature dimensions')
        if kind=='pocket':
            need(f['opening'] in ('top','bottom') and f['x']+f['width']<p['width'] and f['y']+f['length']<p['length'] and f['depth']<p['thickness'],
                 'invalid_dimension','internal blind pocket')
        else:
            need(f['axis'] in SPAN and f.get('entry','positive') in ('positive','negative'),'unsupported_direction','principal axis openings only')
            a,b=cross_size(p,f['axis']);r=f.get('counter_diameter',f['diameter'])/2
            need(r<f['u']<a-r and r<f['v']<b-r,'invalid_dimension','bore inside stock cross-section')
            if kind=='counterbore':need(f['counter_diameter']>f['diameter'] and f['counter_depth']<p[SPAN[f['axis']]],'invalid_depth','larger blind counterbore on through core')
            else:
                need(f['extent'] in ('through','blind'),'hole_extent_ambiguous','THRU or explicit depth required','input_ambiguity')
                if f['extent']=='blind':need(f['depth']<p[SPAN[f['axis']]],'invalid_depth','blind depth must be less than stock span')
    for a,b in itertools.combinations(fs,2):
        if b['kind']=='pocket':a,b=b,a
        if a['kind']=='pocket':
            need(b['axis']=='z','unsupported_intersection','pocket with side bores is not supported','unsupported_input')
            r=b.get('counter_diameter',b['diameter'])/2;x,y=b['u'],b['v']
            separate=x+r<a['x'] or x-r>a['x']+a['width'] or y+r<a['y'] or y-r>a['y']+a['length']
            contained=a['x']+r<x<a['x']+a['width']-r and a['y']+r<y<a['y']+a['length']-r
            need(separate or (contained and b['kind']=='bore' and b['extent']=='through'),
                 'unsupported_intersection','only a Z-through bore fully inside the pocket or separated cuts','unsupported_input')
        else:
            need(a['axis']==b['axis'] and math.hypot(a['u']-b['u'],a['v']-b['v'])>(a.get('counter_diameter',a['diameter'])+b.get('counter_diameter',b['diameter']))/2+1e-6,
                 'unsupported_intersection','separate parallel bores only','unsupported_input')

def build(p):
    validate(p)
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox,BRepPrimAPI_MakeCylinder
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
    from OCP.gp import gp_Pnt,gp_Ax2,gp_Dir
    from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
    s=BRepPrimAPI_MakeBox(p['width'],p['length'],p['thickness']).Shape()
    for f in p['features']:
        if f['kind']=='pocket':tools=[BRepPrimAPI_MakeBox(gp_Pnt(f['x'],f['y'],p['thickness']-f['depth'] if f['opening']=='top' else 0),f['width'],f['length'],f['depth']).Shape()]
        else:
            axis=f['axis'];span=p[SPAN[axis]];positive=f.get('entry','positive')=='positive';v=span if positive else 0
            origin={'z':(f['u'],f['v'],v),'x':(v,f['u'],f['v']),'y':(f['u'],v,f['v'])}[axis]
            direction={'x':(1,0,0),'y':(0,1,0),'z':(0,0,1)}[axis];sign=-1 if positive else 1
            ax=gp_Ax2(gp_Pnt(*origin),gp_Dir(*[q*sign for q in direction]));stages=[(f['diameter'],f.get('depth',span))]
            if f['kind']=='counterbore':stages.append((f['counter_diameter'],f['counter_depth']))
            tools=[BRepPrimAPI_MakeCylinder(ax,d/2,h).Shape() for d,h in stages]
        for tool in tools:
            op=BRepAlgoAPI_Cut(s,tool);op.Build();need(op.IsDone(),'kernel_failure','Boolean cut failed','kernel_calculation');s=op.Shape()
    op=ShapeUpgrade_UnifySameDomain(s,True,True,False);op.Build();return op.Shape()
def export(p,path):
    from .step_writer_modes import write_step
    return write_step(Path(path),source=None,mode='reconstruct',shape=build(p))
def recipe(p,digest):
    return '# Reconstructed nominal geometry; tolerances remain in model.json. Not recovered authoring history.\nfrom research_notes.drawing_machining import export\n'+f'PARAMETERS={p!r}\nSOURCE_SHA256={digest!r}\n'+"if __name__=='__main__':\n    import sys\n    export(PARAMETERS,sys.argv[1])\n"
def edit(p):
    p=copy.deepcopy(p);p['width']+=4;p['thickness']+=2
    for f in p['features']:
        if f['kind']=='pocket':f['depth']+=1
        else:
            f['diameter']+=.5
            if f['kind']=='counterbore':f['counter_diameter']+=.5;f['counter_depth']+=1
            elif f['extent']=='blind':f['depth']+=1
    return p

class DimensionGraph:
    """Signed nominal lengths on a graphical axis; disconnected coordinates stay unknown."""
    def __init__(self,view,dimensions,axis):
        self.edges={};self.positions=unique([view['bounds'][axis],*[q[axis] for d in dimensions if d['kind']=='linear' and d['axis']==axis for q in d['points']]])
        def node(x):return min(range(len(self.positions)),key=lambda i:abs(self.positions[i]-x))
        for d in dimensions:
            if d['kind']!='linear' or d['axis']!=axis:continue
            a,b=(q[axis] for q in d['points']);i,j=node(a),node(b);v=d['value']*(1 if b>a else -1)
            self.edges.setdefault(i,[]).append((j,v,d['id']));self.edges.setdefault(j,[]).append((i,-v,d['id']))
        origin=node(view['bounds'][axis]);self.values={origin:0.};self.paths={origin:[]};queue=[origin]
        while queue:
            i=queue.pop(0)
            for j,v,identifier in self.edges.get(i,[]):
                candidate=self.values[i]+v
                if j in self.values:need(abs(candidate-self.values[j])<=1e-6,'dimension_chain_conflict','nominal dimension cycle disagrees','input_ambiguity')
                else:self.values[j]=candidate;self.paths[j]=self.paths[i]+[identifier];queue.append(j)
    def at(self,x):
        i=min(range(len(self.positions)),key=lambda i:abs(self.positions[i]-x))
        need(abs(self.positions[i]-x)<=EPS and i in self.values,'dimension_chain_missing','no dimension path from stock datum to target','input_ambiguity')
        return self.values[i],self.paths[i]

def internal_rectangles(view):
    lines=view['lines'];bounds=view['bounds'];xs=unique(q[0] for l in lines for q in l);ys=unique(q[1] for l in lines for q in l)
    need(len(xs)<=24 and len(ys)<=24,'unsupported_profile','bounded orthogonal profile','unsupported_input')
    def covered(a,b):
        axis=0 if abs(a[1]-b[1])<=EPS else 1;j=1-axis;end,hi=sorted((a[axis],b[axis]));intervals=[]
        for c,d in lines:
            if abs(c[j]-a[j])<=EPS and abs(d[j]-a[j])<=EPS:intervals.append(sorted((c[axis],d[axis])))
        for start,stop in sorted(intervals):
            if start<=end+EPS:end=max(end,stop)
        return end>=hi-EPS
    result=[]
    for x0,x1 in itertools.combinations(xs,2):
        for y0,y1 in itertools.combinations(ys,2):
            if not(bounds[0]+EPS<x0<x1<bounds[2]-EPS and bounds[1]+EPS<y0<y1<bounds[3]-EPS):continue
            corners=[(x0,y0),(x1,y0),(x1,y1),(x0,y1)]
            if all(covered(a,b) for a,b in zip(corners,corners[1:]+corners[:1])):result.append((x0,y0,x1,y1))
    need(len(result)<=1,'unsupported_profile','one internal rectangle at most','unsupported_input');return result

def interpret(source,context,format):
    out=dict(source_sha256=hashlib.sha256(source).hexdigest(),input_format=format,human_context=context,
        method='machining_dimensions_v1',ai_used=False,original_history_recovered=False)
    try:
        need(isinstance(source,bytes) and 0<len(source)<=500000 and format in ('svg','dxf'),'input_format','bounded SVG/DXF','unsupported_input')
        fields={'unit','projection','family_assumption','view_roles'}|({'drawing_group'} if format=='svg' else set())
        need(isinstance(context,dict) and set(context)==fields,'context_missing','nonnumeric view/family context required','input_ambiguity')
        need(context['unit']=='mm' and context['family_assumption']=='bounded_stock_machining','unsupported_context','bounded machined stock family','unsupported_input')
        need(context['projection'] in ('first_angle','third_angle'),'projection_unknown','projection method required','input_ambiguity')
        roles=context['view_roles'];need(set(roles)=={'front','top','right'} and len(set(roles.values()))==3,'view_mapping','three distinct views required')
        ev=svg_evidence(source,context) if format=='svg' else dxf_evidence(source,context);out['evidence']=ev
        views=ev['views'];dims=ev['dimensions'];bindings={};tolerances=[]
        for d in dims:
            a=callout(d['text'],d['kind']=='diameter');d['callout']=a
            if a['tolerance'] is not None:tolerances.append(dict(dimension_id=d['id'],view=d['view'],nominal_mm=a['nominal'],deviations_mm=a['tolerance'],source_text=d['text']))
        out['tolerances']=tolerances
        def measure(role,axis,a,b,key):
            matches=[d for d in dims if d['kind']=='linear' and d['view']==role and d['axis']==axis and close(sorted(q[axis] for q in d['points']),sorted((a,b)))]
            need(matches,'dimension_missing',key,'input_ambiguity');values=[d['value'] for d in matches]
            need(max(values)-min(values)<=1e-6,'dimension_conflict',key,'input_ambiguity');bindings[key]=[d['id'] for d in matches];return values[0]
        ext={r:[measure(r,j,v['bounds'][j],v['bounds'][j+2],r+'.extent'+str(j)) for j in (0,1)] for r,v in views.items()}
        need(abs(ext['front'][0]-ext['top'][0])<=1e-6 and abs(ext['top'][1]-ext['right'][0])<=1e-6 and abs(ext['front'][1]-ext['right'][1])<=1e-6,'dimension_conflict','stock dimensions disagree','input_ambiguity')
        p=dict(width=ext['top'][0],length=ext['top'][1],thickness=ext['front'][1],features=[]);scales={};raw={}
        for r,v in views.items():
            b=v['bounds'];s=(b[2]-b[0])/ext[r][0];need(.1<=s<=10 and abs((b[3]-b[1])/s-ext[r][1])<=.02,'geometry_dimension_conflict','view scale/aspect','drawing_conflict')
            scales[r]=s;raw[r]=[[[(q[j]-b[j])/s for j in (0,1)] for q in line] for line in v['raw']]
        for d in dims:
            span=abs(d['points'][1][d['axis']]-d['points'][0][d['axis']]) if d['kind']=='linear' else math.dist(*d['points'])
            need(abs(span/scales[d['view']]-d['value'])<=.02,'geometry_dimension_conflict','nominal dimension does not match geometry: '+d['id'],'drawing_conflict')
        centers={r:((v['bounds'][0]+v['bounds'][2])/2,(v['bounds'][1]+v['bounds'][3])/2) for r,v in views.items()}
        a,b,c=(centers[r] for r in ('front','top','right'));sign=1 if context['projection']=='third_angle' else -1
        need((b[1]-a[1])*sign>0 and (c[0]-a[0])*sign>0 and abs(a[0]-b[0])<=EPS and abs(a[1]-c[1])<=EPS,'projection_layout_conflict','view placement disagrees','input_ambiguity')
        graphs={(r,j):DimensionGraph(v,[d for d in dims if d['view']==r],j) for r,v in views.items() for j in (0,1)}
        def coordinate(r,j,x,key):
            value,path=graphs[r,j].at(x);bindings[key]=path;return value
        for x0,y0,x1,y1 in internal_rectangles(views['top']):
            x=coordinate('top',0,x0,'pocket.x');y=coordinate('top',1,y0,'pocket.y')
            w=measure('top',0,x0,x1,'pocket.width');l=measure('top',1,y0,y1,'pocket.length');fb=views['front']['bounds'];matches=[]
            for d in dims:
                if d['kind']!='linear' or d['view']!='front' or d['axis']!=1:continue
                high,low=sorted(d['points'],key=lambda q:q[1],reverse=True);xx=(low[0]-fb[0])/scales['front'];z=(low[1]-fb[1])/scales['front']
                if abs(high[1]-fb[3])<=EPS and EPS<z<p['thickness']-EPS and x-EPS<=xx<=x+w+EPS:matches.append(d)
            need(len(matches)==1,'feature_depth_ambiguous','one pocket depth anchored to front view required','input_ambiguity');d=matches[0]
            bindings['pocket.depth']=[d['id']];p['features'].append(dict(kind='pocket',x=x,y=y,width=w,length=l,depth=d['value'],opening='top'))
        for role,axis in AXES.items():
            circles=views[role]['circles'];assignment={}
            for d in [d for d in dims if d['view']==role and d['kind']=='diameter']:
                circle=next(c for c in circles if c['id']==d['circle_id']);a=d['callout']
                targets=[circle] if a['count']==1 else [c for c in circles if abs(c['radius']-circle['radius'])<=EPS]
                need(len(targets)==a['count'],'quantity_conflict','same-diameter circle count does not match callout','input_ambiguity')
                for target in targets:
                    need(target['id'] not in assignment,'quantity_ambiguous','overlapping diameter/quantity assignments','input_ambiguity');assignment[target['id']]=d
            need(len(assignment)==len(circles),'diameter_missing','every circle needs a diameter callout or unambiguous quantity group','input_ambiguity')
            groups=[]
            for circle in sorted(circles,key=lambda c:(*c['center'],c['radius'])):
                group=next((g for g in groups if close(g[0]['center'],circle['center'])),None)
                if group is None:groups.append([circle])
                else:group.append(circle)
            for g in groups:
                prefix='feature_'+str(len(p['features'])+1);center=g[0]['center'];u=coordinate(role,0,center[0],prefix+'.u');v=coordinate(role,1,center[1],prefix+'.v')
                g.sort(key=lambda c:c['radius']);ds=[assignment[c['id']] for c in g];annotations=[d['callout'] for d in ds]
                for d in ds:bindings.setdefault(prefix+'.callouts',[]).append(d['id'])
                if len(g)==1:
                    a=annotations[0];need(a['through'] or a['depth'] is not None,'hole_extent_ambiguous','THRU or explicit DEPTH required','input_ambiguity')
                    f=dict(kind='bore',axis=axis,u=u,v=v,diameter=a['nominal'],extent='through' if a['through'] else 'blind')
                    if not a['through']:f.update(depth=a['depth'],entry='positive')
                else:
                    need(len(g)==2 and all(a['count']==1 for a in annotations) and annotations[0]['through'] and annotations[1]['depth'] is not None,
                         'stepped_bore_ambiguous','one concentric through core and one larger explicit-depth counterbore required','input_ambiguity')
                    f=dict(kind='counterbore',axis=axis,u=u,v=v,diameter=annotations[0]['nominal'],counter_diameter=annotations[1]['nominal'],counter_depth=annotations[1]['depth'],entry='positive')
                p['features'].append(f)
        validate(p);out.update(bindings=bindings,feature_hypotheses=p['features'],raw_views=raw)
        observed=visibility(source,ev,context,p) if format=='svg' else None
        indices=[i for i,f in enumerate(p['features']) if f['kind']!='bore' or f['extent']=='blind'];options=[];matches=[]
        for signs in itertools.product((True,False),repeat=len(indices)):
            q=copy.deepcopy(p)
            for i,positive in zip(indices,signs):
                f=q['features'][i]
                if f['kind']=='pocket':
                    f['opening']='top' if positive else 'bottom'
                    if not positive:f['depth']=p['thickness']-f['depth']
                else:f['entry']='positive' if positive else 'negative'
            shape=build(q);m,projected=reprojection(raw,shape);vm={}
            if observed is not None:
                pred=visible_projection(shape);vm={r+'_'+k:distance(observed[r][k],pred[r][k]) for r in observed for k in ('visible','hidden')}
            compatible=all(v['sampled_symmetric_max_mm']<=.02 for v in m.values()) and all(v is not None and v<=.02 for v in vm.values())
            options.append(dict(positive_entries=list(signs),projection_metrics=m,visibility_residual_mm=vm,compatible=compatible))
            if compatible:matches.append((q,m,projected,vm))
        out['direction_alternatives']=options
        need(len(matches)==1,'direction_ambiguous' if len(matches)>1 else 'projection_conflict',
             'exactly one direction combination must explain the drawing; DXF line visibility is not assumed','input_ambiguity')
        q,m,projected,vm=matches[0]
        return {**out,'status':'candidate','parameters':q,'projection_metrics':m,'reprojection':projected,'visibility_residual_mm':vm,
            'claim_boundary':'Nominal geometry and numeric deviation metadata; bounded candidate family, not tolerance stack analysis or recovered design history.'}
    except DrawingIssue as e:return {**out,'status':'withheld','reason_code':e.code,'failure_stage':e.stage,'detail':str(e)}
    except Exception as e:return {**out,'status':'withheld','reason_code':'processing_failure','failure_stage':'drawing_or_kernel','detail':type(e).__name__+': '+str(e)}

def main(argv=None):
    import argparse
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('drawing',type=Path);ap.add_argument('context',type=Path);ap.add_argument('--output-dir',type=Path,required=True);a=ap.parse_args(argv)
    a.output_dir.mkdir(parents=True,exist_ok=False)
    with a.drawing.open('rb') as stream:source=stream.read(500001)
    inf=interpret(source,json.loads(a.context.read_text()),a.drawing.suffix[1:]);(a.output_dir/'inference.json').write_bytes(json_bytes(inf))
    if inf['status']=='candidate':
        (a.output_dir/'candidate.py').write_text(recipe(inf['parameters'],inf['source_sha256']))
        (a.output_dir/'model.json').write_bytes(json_bytes({k:inf[k] for k in ('parameters','tolerances','bindings','source_sha256')}))
if __name__=='__main__':main()
