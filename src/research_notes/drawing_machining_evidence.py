"""Versioned machining extension: native dimension geometry with bounded depth/tolerance syntax.

The historical parser is kept byte-identical for replay of its frozen experiment.
"""
import io,math,re,xml.etree.ElementTree as ET
from .drawing_to_cad import DrawingIssue
from .cad_svg_import import need,close,unit,dot,relative,on_segment,line_distance,arrow
from .svg_drawing_graphics import normalize,circle,samples,EPS
from .drawing_svg_extensions import adapt_svg

from .drawing_machining_annotations import annotation

def finish(views,dimensions,inventory):
    for name,v in views.items():
        pts=[p for line in v['lines'] for p in line]
        pts += [(c['center'][0]+s*c['radius'],c['center'][1]+t*c['radius']) for c in v['circles'] for s,t in ((-1,0),(1,0),(0,-1),(0,1))]
        need(pts,'view_mapping','empty view: '+name,'input_ambiguity')
        v['bounds']=[min(p[0] for p in pts),min(p[1] for p in pts),max(p[0] for p in pts),max(p[1] for p in pts)]
    return dict(views=views,dimensions=dimensions,inventory=inventory)

def dxf_evidence(source,context):
    import ezdxf
    from .cad_drawing_import import xy
    doc=ezdxf.read(io.StringIO(source.decode('utf-8')))
    need(doc.units==4,'drawing_unit_mismatch','DXF unit must be mm')
    entities=list(doc.modelspace());need(len(entities)<=1024,'input_format','entity limit','unsupported_input')
    roles=context['view_roles'];views={r:dict(lines=[],circles=[],raw=[],anchors=[]) for r in roles};dimensions=[]
    for e in entities:
        layer=doc.layers.get(e.dxf.layer)
        need(not layer.is_off() and not layer.is_frozen() and not e.dxf.get('invisible',0),'hidden_entity','disabled geometry','unsupported_input')
        need(tuple(e.dxf.get('extrusion',(0,0,1)))==(0,0,1),'unsupported_orientation','XY drawing only','unsupported_input')
        if e.dxftype()=='DIMENSION':continue
        role=next((r for r,n in roles.items() if n==e.dxf.layer),None)
        need(role is not None,'unmapped_geometry',e.dxf.layer,'input_ambiguity');v=views[role]
        if e.dxftype()=='LINE':a,b=xy(e.dxf.start),xy(e.dxf.end);v['lines'].append([a,b]);v['raw'].append([a,b]);v['anchors'] += [a,b]
        elif e.dxftype()=='CIRCLE':
            c=xy(e.dxf.center);r=float(e.dxf.radius);need(0<r<1000,'unsupported_geometry','circle radius','unsupported_input')
            if not any(close(c,o['center']) and abs(r-o['radius'])<=EPS for o in v['circles']):
                v['circles'].append(dict(center=c,radius=r,id=e.dxf.handle))
                v['anchors'].append(c);v['raw'].append([(c[0]+r*math.cos(i*math.pi/64),c[1]+r*math.sin(i*math.pi/64)) for i in range(129)])
        elif e.dxftype()=='SPLINE':
            points=[xy(p) for p in e.control_points]
            need(2<=len(points)<=256 and all(math.isfinite(w) and w>0 for w in e.weights),'unsupported_spline','spline control hull','unsupported_input')
            a,b=max(((a,b) for a in points for b in points),key=lambda p:math.dist(*p))
            need(all(on_segment(p,a,b) for p in points),'unsupported_spline','only collinear splines','unsupported_input')
            v['lines'].append([a,b]);v['raw'].append([a,b]);v['anchors'] += [a,b]
        else:raise DrawingIssue('unsupported_entity','unsupported_input',e.dxftype())
    for e in entities:
        if e.dxftype()!='DIMENSION':continue
        kind=e.dxf.dimtype&15;need(kind in (0,3),'unsupported_dimension_type',str(kind),'unsupported_input')
        block=doc.blocks.get(e.dxf.geometry)
        need(block is not None and not e.xdata and all(a.dxftype() in ('TEXT','LINE','SOLID') and not a.dxf.get('invisible',0) for a in block),
             'unsupported_dimension_picture','dimension picture/overrides','unsupported_input')
        text=e.dxf.text.strip();need([a.dxf.text.strip() for a in block if a.dxftype()=='TEXT']==[text],'dimension_display_conflict','dimension and rendered text disagree')
        value,count,through=annotation(text,kind==3)
        if kind==0:
            angle=e.dxf.get('angle',0)%180;need(min(abs(angle),abs(angle-90))<1e-6,'unsupported_dimension_direction','XY dimensions','unsupported_input')
            a,b=xy(e.dxf.defpoint2),xy(e.dxf.defpoint3);axis=0 if abs(angle)<1e-6 else 1
            matches=[r for r,v in views.items() if all(any(close(p,q) for q in v['anchors']) for p in (a,b))]
            need(len(matches)==1,'dimension_target_ambiguous','definition points must match one view','input_ambiguity')
            role=matches[0];extra=dict(axis=axis)
        else:
            a,b=xy(e.dxf.defpoint),xy(e.dxf.defpoint4);c=tuple((a[j]+b[j])/2 for j in range(2));radius=math.dist(a,b)/2
            matches=[(r,o) for r,v in views.items() for o in v['circles'] if close(c,o['center']) and abs(radius-o['radius'])<=EPS]
            need(len(matches)==1,'diameter_target_ambiguous','diameter endpoints must match circle','input_ambiguity')
            role,o=matches[0];extra=dict(circle_id=o['id'])
        dimensions.append(dict(view=role,kind='linear' if kind==0 else 'diameter',points=[a,b],value=value,count=count,through=through,
                               id=e.dxf.handle,text_id=e.dxf.geometry,text=text,**extra))
    return finish(views,dimensions,dict(format='dxf',encoding='strict UTF-8',geometry_visibility='not evaluated'))

def svg_evidence(source,context,choices=None):
    choices=choices or {};used_choices=set()
    normalized,changes,mapping=adapt_svg(source)
    need(any(e.tag.split('}')[-1]=='text' for e in ET.fromstring(normalized).iter()),'text_unavailable',
         'no XML dimension text; outline glyphs need human transcription or separately evaluated OCR','input_ambiguity')
    records,inventory=normalize(normalized,context['drawing_group']);byid={r['id']:r for r in records}
    roles={r:mapping.get(ref,ref) for r,ref in context['view_roles'].items()}
    need(all(ref in byid and byid[ref]['tag']=='path' for ref in roles.values()),'view_mapping','view representative missing','input_ambiguity')
    matrices={r:byid[ref]['matrix'] for r,ref in roles.items()}
    need(len(set(matrices.values()))==3,'view_mapping','three distinct view frames required','input_ambiguity')
    views={r:dict(lines=[],circles=[],raw=[],anchors=[]) for r in roles}
    texts=[r for r in records if r['tag']=='text'];arrows=[];linear=[];leaders=[];dimensions=[];fills=[]
    need(texts,'text_unavailable','no XML dimension text; outline glyphs need human transcription or separately evaluated OCR','input_ambiguity')
    flip=lambda p:(p[0],-p[1])
    for r in records:
        if r['tag']=='text':continue
        paths=r['paths'];style=r['style']
        if len(paths)==2 and all(len(p)==1 and p[0][0]=='L' for p in paths):
            a,b=paths[0][0][1:];c,d=paths[1][0][1:]
            if close(b,c) and on_segment(b,a,d) and on_segment(c,a,d):
                paths=[[('L',a,d)]];r['paths']=paths
                changes.append('connected collinear leader subpaths joined')
        if style.get('fill')!='none' and style.get('stroke')!='none':
            need(len(paths)==1,'svg_arrow','triangle only','unsupported_input')
            tip,direction=arrow(paths[0]);arrows.append(dict(id=r['id'],tip=tip,direction=direction));continue
        role=next((k for k,m in matrices.items() if all(abs(a-b)<1e-8 for a,b in zip(m,r['matrix']))),None)
        need(role is not None,'view_mapping','graphic outside selected view frames','input_ambiguity')
        v=views[role]
        if style.get('stroke')=='none':
            fills.append((role,r));continue
        if len(paths)==3 and all(len(p)==1 and p[0][0]=='L' for p in paths):
            linear.append((role,r));continue
        if len(paths)==1 and all(s[0]=='C' for s in paths[0]):
            c=circle(paths[0]);center=flip(c['center']);radius=c['radius']
            if not any(close(center,o['center']) and abs(radius-o['radius'])<=EPS for o in v['circles']):
                v['circles'].append(dict(center=center,radius=radius,id=r['id']))
                v['anchors'].append(center);v['raw'].append([flip(p) for s in paths[0] for p in samples(s)])
        elif len(paths)==1 and len(paths[0])==1 and paths[0][0][0]=='L':
            a,b=paths[0][0][1:]
            if min(abs(a[0]-b[0]),abs(a[1]-b[1]))>EPS:
                leaders.append((role,r));continue
            v['lines'].append([flip(a),flip(b)]);v['raw'].append([flip(a),flip(b)]);v['anchors'] += [flip(a),flip(b)]
        else:raise DrawingIssue('svg_path','unsupported_input','unclassified curve/profile')
    # Filled surface paths may have several subpaths (pocket walls, annuli).
    # Every segment must have a matching stroked geometric edge.
    for role,r in fills:
        v=views[role]
        for path in r['paths']:
            if all(s[0]=='C' for s in path):
                c=circle(path)
                need(any(close(flip(c['center']),o['center']) and abs(c['radius']-o['radius'])<=EPS for o in v['circles']),
                     'svg_profile','filled circle has no matching edge','input_ambiguity')
            else:
                for s in path:
                    need(s[0]=='L','svg_curve','mixed curved fill','unsupported_input')
                    a,b=map(flip,s[1:])
                    need(any(on_segment(a,c,d) and on_segment(b,c,d) for c,d in v['lines']),
                         'svg_profile','filled surface segment lacks matching edge','input_ambiguity')
    used_text=set();used_arrows=set()
    def label(a,b,dimension_id,role):
        u=unit(a,b);matches=[];review_candidates=[]
        for t in texts:
            along=dot(relative(t['origin'],a),u);gap=line_distance(t['origin'],a,b)
            if t['id'] not in used_text and abs(dot(t['direction'],u))>1-1e-5 and .1*t['height']<=gap<=1.2*t['height'] and -t['height']<=along<=math.dist(a,b)+t['height']:
                matches.append(t)
            if t['id'] not in used_text and abs(dot(t['direction'],u))>1-1e-5 and .1*t['height']<=gap<=1.2*t['height'] and -4*t['height']<=along<=math.dist(a,b)+4*t['height']:
                review_candidates.append(t)
        if dimension_id in choices:
            selected=[t for t in review_candidates if t['id']==choices[dimension_id]]
            need(len(selected)==1,'review_choice_invalid','selected text is not an available geometric candidate','input_ambiguity')
            matches=selected;used_choices.add(dimension_id)
        if len(matches)!=1:
            error=DrawingIssue('dimension_label_ambiguous','input_ambiguity','choose a compatible text ID, without entering a numeric value')
            error.review_request=dict(dimension_id=dimension_id,view=role,dimension_line=[a,b],automatic_candidate_count=len(matches),
                policy='Manual choice may extend up to four text heights beyond endpoints; parallel baseline/gap and later dimension/geometry checks remain required.',
                choices=[{k:t[k] for k in ('id','text','origin','height','direction')} for t in review_candidates])
            raise error
        t=matches[0];used_text.add(t['id']);return t
    def endpoints(a,b,diameter=False):
        chosen=[]
        for p in (a,b):
            found=[r for r in arrows if r['id'] not in used_arrows and close(p,r['tip'])]
            need(len(found)==1,'dimension_arrow_missing','arrow at dimension endpoint','input_ambiguity');chosen.append(found[0])
        u=unit(a,b);sign=-1 if diameter else (1 if dot(chosen[0]['direction'],u)>0 else -1)
        need(dot(chosen[0]['direction'],u)*sign>.9999 and dot(chosen[1]['direction'],u)*sign<-.9999,
             'dimension_arrow_direction','opposing consistent arrows required')
        used_arrows.update(r['id'] for r in chosen)
        return [r['id'] for r in chosen]
    for role,r in linear:
        lines=[p[0][1:] for p in r['paths']];found=[]
        for i,(a,b) in enumerate(lines):
            u=unit(a,b)
            if min(abs(u[0]),abs(u[1]))>1e-7:continue
            intersections=[];anchors=[];axis=0 if abs(u[1])<1e-7 else 1
            for c,d in (s for j,s in enumerate(lines) if j!=i):
                q=(c[0],a[1]) if axis==0 else (a[0],c[1])
                if abs(dot(u,unit(c,d)))>1e-7 or not on_segment(q,a,b) or not on_segment(q,c,d):continue
                candidates=[p for p in (c,d) if any(close(flip(p),x) for x in views[role]['anchors'])]
                if len(candidates)==1:anchors.append(candidates[0]);intersections.append(q)
            if len(anchors)==2:found.append((axis,anchors,intersections))
        need(len(found)==1,'dimension_target_ambiguous','extension lines must connect geometry','input_ambiguity')
        axis,anchors,(a,b)=found[0];arrowids=endpoints(a,b);t=label(a,b,r['id'],role)
        value,count,through=annotation(t['text'])
        dimensions.append(dict(view=role,kind='linear',axis=axis,points=[flip(p) for p in anchors],value=value,
                               count=count,through=through,id=r['id'],text_id=t['id'],text=t['text'],arrow_ids=arrowids))
    for role,r in leaders:
        a,b=r['paths'][0][0][1:];found=[]
        for c in views[role]['circles']:
            tips=[ar for ar in arrows if ar['id'] not in used_arrows and on_segment(ar['tip'],a,b)
                  and abs(math.dist(flip(ar['tip']),c['center'])-c['radius'])<=EPS]
            if len(tips)==2 and close(tuple((flip(tips[0]['tip'])[j]+flip(tips[1]['tip'])[j])/2 for j in range(2)),c['center']):
                found.append((c,tips))
        need(len(found)==1,'diameter_target_ambiguous','leader and circle arrows','input_ambiguity')
        c,tips=found[0];arrowids=endpoints(tips[0]['tip'],tips[1]['tip'],True);t=label(a,b,r['id'],role)
        value,count,through=annotation(t['text'],True)
        dimensions.append(dict(view=role,kind='diameter',circle_id=c['id'],points=[flip(t['tip']) for t in tips],
                               value=value,count=count,through=through,id=r['id'],text_id=t['id'],text=t['text'],arrow_ids=arrowids))
    need(len(used_text)==len(texts) and len(used_arrows)==len(arrows),'unassigned_annotation','text or arrows remain unassigned','input_ambiguity')
    need(set(choices)==used_choices,'review_choice_invalid','unused or stale label selection','input_ambiguity')
    inventory.update(format='svg',extensions=changes,original_to_normalized_paths=mapping,frames=matrices)
    return finish(views,dimensions,inventory)
