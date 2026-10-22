"""Declared part families reconstructed from graphical dimensions, never truth CAD."""
from __future__ import annotations
import copy,hashlib,json,math
from pathlib import Path
from .drawing_to_cad import DrawingIssue,json_bytes,project_shape
from .cad_svg_import import need,close
from .drawing_family_evidence import svg_evidence,dxf_evidence
from .svg_drawing_graphics import EPS

FAMILIES={'plate','l_bracket','stepped_shaft','pocket'}

def unique(values):
    out=[]
    for value in sorted(values):
        if not out or abs(value-out[-1])>EPS:out.append(value)
    return out

def validate_parameters(f,p):
    keys={'plate':{'width','length','thickness','holes'},
          'l_bracket':{'width','length','height','base_thickness','wall_thickness'},
          'stepped_shaft':{'length1','length2','diameter1','diameter2'},
          'pocket':{'width','length','thickness','pocket_x','pocket_y','pocket_width','pocket_length','pocket_depth'}}[f]
    need(set(p)==keys,'parameter_schema','incorrect family parameters')
    need(all(type(v) in (float,int) and math.isfinite(v) and 1e-4<v<=1000 for k,v in p.items() if k!='holes'),
         'invalid_dimension','positive bounded family dimensions')
    if f=='l_bracket':
        need(p['base_thickness']<p['height'] and p['wall_thickness']<p['length'],'invalid_dimension','L walls must be thinner than envelope')
    elif f=='stepped_shaft':
        need(p['diameter2']<p['diameter1'],'invalid_dimension','second shaft diameter must be smaller')
    elif f=='pocket':
        need(p['pocket_depth']<p['thickness'] and p['pocket_x']+p['pocket_width']<p['width']
             and p['pocket_y']+p['pocket_length']<p['length'],'invalid_dimension','closed rectangular blind pocket required')
    else:
        from .drawing_to_cad import feature_model
        need(len(p['holes'])<=3,'unsupported_geometry','at most three holes','unsupported_input')
        feature_model(p,hashlib.sha256(json_bytes(p)).hexdigest())
        for h in p['holes']:
            need(set(h)=={'x','y','diameter'} and all(type(v) in (float,int) and math.isfinite(v) and v>0 for v in h.values()),
                 'invalid_dimension','hole schema')
            r=h['diameter']/2
            need(r<h['x']<p['width']-r and r<h['y']<p['length']-r,'invalid_dimension','hole must be internal')
        for i,h in enumerate(p['holes']):
            need(all(math.hypot(h['x']-o['x'],h['y']-o['y'])>(h['diameter']+o['diameter'])/2 for o in p['holes'][i+1:]),
                 'intersecting_holes','separated holes only','unsupported_input')

def build_family(f,p):
    validate_parameters(f,p)
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox,BRepPrimAPI_MakeCylinder
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut,BRepAlgoAPI_Fuse
    from OCP.gp import gp_Pnt,gp_Ax2,gp_Dir
    from OCP.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
    box=lambda w,l,h,origin=(0,0,0):BRepPrimAPI_MakeBox(gp_Pnt(*origin),w,l,h).Shape()
    if f=='plate':
        from .drawing_to_cad import build_candidate
        recipe_digest=hashlib.sha256(json_bytes({'family':f,'parameters':p})).hexdigest()
        return build_candidate(p,recipe_digest)[2].shape
    if f=='l_bracket':
        s=BRepAlgoAPI_Fuse(box(p['width'],p['length'],p['base_thickness']),box(p['width'],p['wall_thickness'],p['height'])).Shape()
    elif f=='stepped_shaft':
        cylinder=lambda x,r,length:BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x,0,0),gp_Dir(1,0,0)),r,length).Shape()
        s=BRepAlgoAPI_Fuse(cylinder(0,p['diameter1']/2,p['length1']),cylinder(p['length1'],p['diameter2']/2,p['length2'])).Shape()
    else:
        s=BRepAlgoAPI_Cut(box(p['width'],p['length'],p['thickness']),box(p['pocket_width'],p['pocket_length'],p['pocket_depth'],
                            (p['pocket_x'],p['pocket_y'],p['thickness']-p['pocket_depth']))).Shape()
    u=ShapeUpgrade_UnifySameDomain(s,True,True,False);u.Build();return u.Shape()

def export_family(f,p,path):
    from .step_writer_modes import write_step
    return write_step(Path(path),source=None,mode='reconstruct',shape=build_family(f,p))

def code(f,p,digest):
    return ("# Editable generated recipe; not recovered original feature history.\n"
            "from research_notes.drawing_families import export_family\n"
            f"FAMILY = {f!r}\nPARAMETERS = {p!r}\nSOURCE_SHA256 = {digest!r}\n"
            "if __name__ == '__main__':\n    import sys\n    export_family(FAMILY, PARAMETERS, sys.argv[1])\n")

def edit(f,p):
    p=copy.deepcopy(p)
    if f=='plate':
        p['width']+=5;p['thickness']+=2
        if p['holes']:
            h=min(p['holes'],key=lambda h:(h['x'],h['y']));h['x']+=1;h['diameter']+=1
    elif f=='l_bracket':p['width']+=5;p['height']+=3;p['base_thickness']+=1
    elif f=='stepped_shaft':p['length1']+=4;p['diameter2']+=1
    else:p['width']+=5;p['pocket_width']+=2;p['pocket_depth']+=1
    return p

def aligned_projection(projected):
    out={}
    for role,groups in projected.items():
        lines=groups['visible']+groups['hidden'];points=[p for line in lines for p in line]
        mins=[min(p[j] for p in points) for j in (0,1)]
        out[role]=[[[p[j]-mins[j] for j in (0,1)] for p in line] for line in lines]
    return out

def reprojection(raw,shape):
    # Shared sampling metric, kept independent of the input/parameter association.
    projected=aligned_projection(project_shape(shape));metrics={}
    for role in raw:
        a=directed_distance(raw[role],projected[role]);b=directed_distance(projected[role],raw[role])
        metrics[role]=dict(sampled_symmetric_max_mm=max(a[0],b[0]),drawing_to_cad_max_mm=a[0],cad_to_drawing_max_mm=b[0])
    return metrics,projected

def directed_distance(first,second):
    """Same point-to-polyline metric as the original experiment; no experiment imports."""
    import numpy as np
    points=np.concatenate([np.asarray(line) for line in first])
    starts=np.concatenate([np.asarray(line[:-1]) for line in second])
    ends=np.concatenate([np.asarray(line[1:]) for line in second]);delta=ends-starts
    length=np.einsum('ij,ij->i',delta,delta);distances=[]
    for block in np.array_split(points,max(1,len(points)//128)):
        relative=block[:,None,:]-starts[None,:,:]
        t=np.clip(np.einsum('nmi,mi->nm',relative,delta)/np.maximum(length,1e-30),0,1)
        distances.extend(np.sqrt(np.sum((relative-t[:,:,None]*delta[None,:,:])**2,axis=2)).min(axis=1))
    return float(max(distances)),float(np.sqrt(np.mean(np.asarray(distances)**2)))

def interpret(source,context,format):
    base=dict(source_sha256=hashlib.sha256(source).hexdigest(),human_context=context,input_format=format,
              ai_used=False,original_history_recovered=False,method='declared_family_graphical_dimensions')
    evidence=None
    try:
        need(isinstance(source,bytes) and 0<len(source)<=500000,'input_format','bounded input','unsupported_input')
        required={'unit','projection','family_assumption','view_roles'}|({'drawing_group'} if format=='svg' else set())
        need(isinstance(context,dict) and set(context)==required,'context_missing','only nonnumeric drawing assumptions allowed','input_ambiguity')
        f=context['family_assumption'];need(f in FAMILIES and context['unit']=='mm','unsupported_context','supported family and mm required','unsupported_input')
        need(context['projection'] in ('first_angle','third_angle'),'projection_unknown','projection required','input_ambiguity')
        roles=context['view_roles'];need(isinstance(roles,dict) and set(roles)=={'front','top','right'} and all(isinstance(v,str) for v in roles.values()) and len(set(roles.values()))==3,
                                       'view_mapping','three distinct view references','input_ambiguity')
        need(format in ('svg','dxf'),'input_format','SVG/DXF only','unsupported_input')
        try:
            evidence=(svg_evidence if format=='svg' else dxf_evidence)(source,context)
        except DrawingIssue:
            raise
        except Exception as error:
            raise DrawingIssue('drawing_parse_failure','drawing_recognition',type(error).__name__+': '+str(error)) from error
        views=evidence['views'];dims=evidence['dimensions'];bindings={}
        def measure(role,axis,a,b,key):
            targets=sorted((a,b))
            matches=[d for d in dims if d['kind']=='linear' and d['view']==role and d['axis']==axis
                     and close(sorted(p[axis] for p in d['points']),targets)]
            need(matches,'dimension_missing',f'{role}: {key} needs an explicit dimension','input_ambiguity')
            values=[d['value'] for d in matches]
            need(max(values)-min(values)<=1e-6,'dimension_conflict',key)
            bindings.setdefault(key,[]).extend(d['id'] for d in matches)
            return values[0]
        def coords(role,axis):
            return unique(p[axis] for line in views[role]['lines'] for p in line)
        def full(role,axis,key):
            b=views[role]['bounds'];return measure(role,axis,b[axis],b[axis+2],key)
        if f in ('plate','pocket','l_bracket'):
            w=full('top',0,'width');l=full('top',1,'length')
            h=full('front',1,'height' if f=='l_bracket' else 'thickness')
            p=dict(width=w,length=l,**({'height':h} if f=='l_bracket' else {'thickness':h}))
            need(abs(full('front',0,'width')-w)<=1e-6 and abs(full('right',0,'length')-l)<=1e-6
                 and abs(full('right',1,'height' if f=='l_bracket' else 'thickness')-h)<=1e-6,'dimension_conflict','cross-view envelope')
            if f=='l_bracket':
                xs,ys=coords('right',0),coords('right',1)
                need(len(xs)==len(ys)==3,'unsupported_profile','six-vertex L section','unsupported_input')
                p.update(wall_thickness=measure('right',0,xs[0],xs[1],'wall_thickness'),
                         base_thickness=measure('right',1,ys[0],ys[1],'base_thickness'))
            elif f=='pocket':
                xs,ys=coords('top',0),coords('top',1);zs=coords('front',1)
                need(len(xs)==len(ys)==4 and len(zs)==3,'unsupported_profile','one closed rectangular pocket','unsupported_input')
                p.update(pocket_x=measure('top',0,xs[0],xs[1],'pocket_x'),pocket_y=measure('top',1,ys[0],ys[1],'pocket_y'),
                         pocket_width=measure('top',0,xs[1],xs[2],'pocket_width'),pocket_length=measure('top',1,ys[1],ys[2],'pocket_length'),
                         pocket_depth=measure('front',1,zs[1],zs[2],'pocket_depth'))
            else:
                holes=[];top=views['top'];b=top['bounds']
                for i,c in enumerate(sorted(top['circles'],key=lambda c:tuple(c['center']))):
                    x=measure('top',0,b[0],c['center'][0],f'hole_{i+1}.x')
                    y=measure('top',1,b[1],c['center'][1],f'hole_{i+1}.y')
                    matches=[]
                    for d in dims:
                        if d['kind']!='diameter' or d['view']!='top':continue
                        if d['circle_id']==c['id']:matches.append(d)
                        elif d['count']>1:
                            selected=next(o for o in top['circles'] if o['id']==d['circle_id'])
                            if abs(selected['radius']-c['radius'])<=EPS:matches.append(d)
                    need(len(matches)==1,'hole_diameter_missing','unique explicit diameter or matching quantity','input_ambiguity')
                    d=matches[0];need(d['through'],'hole_extent_ambiguous','THRU required','input_ambiguity')
                    if d['count']>1:
                        need(sum(abs(o['radius']-c['radius'])<=EPS for o in top['circles'])==d['count'],
                             'quantity_conflict','quantity disagrees with equal-radius circles')
                    bindings[f'hole_{i+1}.diameter']=[d['id']]
                    holes.append(dict(x=x,y=y,diameter=d['value']))
                p['holes']=holes
        else:
            xs,ys=coords('front',0),coords('front',1)
            need(len(xs)==3 and len(ys)==4,'unsupported_profile','two-stage coaxial shaft','unsupported_input')
            total=full('front',0,'total_length');first=measure('front',0,xs[0],xs[1],'length1')
            d=full('front',1,'diameter1');small=measure('front',1,ys[1],ys[2],'diameter2')
            p=dict(length1=first,length2=total-first,diameter1=d,diameter2=small)
            bindings['length2']=['derived: total_length - length1']
            right=views['right']['circles']
            need(len(right)==2 and close(right[0]['center'],right[1]['center']),'unsupported_profile','concentric end circles required','unsupported_input')
            for key,c in zip(('diameter2','diameter1'),sorted(right,key=lambda c:c['radius'])):
                found=[a for a in dims if a['kind']=='diameter' and a['view']=='right' and a['circle_id']==c['id']]
                need(len(found)==1,'dimension_missing','right: '+key,'input_ambiguity')
                need(abs(found[0]['value']-p[key])<=1e-6 and found[0]['count']==1 and not found[0]['through'],
                     'dimension_conflict','shaft diameter evidence')
                bindings[key].append(found[0]['id'])
        validate_parameters(f,p)
        # All annotations, including redundant dimensions, must agree with one scale per view.
        scales={};raw={}
        extents={'front':(p['width'],p.get('height',p.get('thickness'))),'top':(p['width'],p['length']),'right':(p['length'],p.get('height',p.get('thickness')))} if f!='stepped_shaft' else {
            'front':(p['length1']+p['length2'],p['diameter1']),'top':(p['length1']+p['length2'],p['diameter1']),'right':(p['diameter1'],p['diameter1'])}
        for role,v in views.items():
            b=v['bounds'];scale=(b[2]-b[0])/extents[role][0];scales[role]=scale
            need(.1<=scale<=10 and abs(b[3]-b[1]-extents[role][1]*scale)<=EPS,'geometry_dimension_conflict','view scale/envelope mismatch')
            raw[role]=[[[(pt[j]-b[j])/scale for j in (0,1)] for pt in line] for line in v['raw']]
        for d in dims:
            span=abs(d['points'][1][d['axis']]-d['points'][0][d['axis']]) if d['kind']=='linear' else math.dist(*d['points'])
            need(abs(span/scales[d['view']]-d['value'])<=EPS/scales[d['view']],'geometry_dimension_conflict','annotation disagrees with geometry: '+d['id'])
        centers={r:((v['bounds'][0]+v['bounds'][2])/2,(v['bounds'][1]+v['bounds'][3])/2) for r,v in views.items()}
        a,b,c=(centers[r] for r in ('front','top','right'));sign=1 if context['projection']=='third_angle' else -1
        need((b[1]-a[1])*sign>0 and (c[0]-a[0])*sign>0 and abs(a[0]-b[0])<=EPS and abs(a[1]-c[1])<=EPS,
             'projection_layout_conflict','view positions/projection disagree')
        try:
            shape=build_family(f,p);projection,projected=reprojection(raw,shape)
        except DrawingIssue:
            raise
        except Exception as error:
            raise DrawingIssue('kernel_failure','kernel_calculation',type(error).__name__+': '+str(error)) from error
        need(max(v['sampled_symmetric_max_mm'] for v in projection.values())<=.02,'reprojection_conflict','generated family does not explain input contours')
        return {**base,'status':'candidate','family':f,'parameters':p,'evidence':evidence,'bindings':bindings,
                'raw_views':raw,'reprojection':projected,'projection_metrics':projection,
                'claim_boundary':'Declared family and manual view frames; own development drawings; not recovered authoring history'}
    except DrawingIssue as e:
        return {**base,'status':'withheld','reason_code':e.code,'failure_stage':e.stage,'detail':str(e),'evidence':evidence}
    except Exception as e:
        return {**base,'status':'withheld','reason_code':'processing_failure','failure_stage':'drawing_or_kernel',
                'detail':type(e).__name__+': '+str(e),'evidence':evidence}

def main(argv=None):
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('drawing',type=Path);p.add_argument('context',type=Path);p.add_argument('--output-dir',required=True,type=Path)
    a=p.parse_args(argv)
    if a.output_dir.exists() and any(a.output_dir.iterdir()):p.error('new/empty output required')
    with a.drawing.open('rb') as stream:source=stream.read(500001)
    result=interpret(source,json.loads(a.context.read_text()),a.drawing.suffix[1:].lower())
    a.output_dir.mkdir(parents=True,exist_ok=True);(a.output_dir/'inference.json').write_bytes(json_bytes(result))
    if result['status']=='candidate':
        (a.output_dir/'candidate.py').write_text(code(result['family'],result['parameters'],result['source_sha256']))
        (a.output_dir/'model.json').write_bytes(json_bytes({k:result[k] for k in ('family','parameters','bindings','source_sha256')}))
    print(json.dumps(dict(status=result['status'],reason=result.get('reason_code'))))

if __name__=='__main__':main()
