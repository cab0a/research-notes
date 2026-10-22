"""Derived syntax/ambiguity controls, explicitly not additional native CAD exports."""
from pathlib import Path
import copy,hashlib,json,re,xml.etree.ElementTree as ET
from research_notes.drawing_to_cad import json_bytes,FAMILY
from research_notes.svg_drawing_graphics import path_data,circle,IDENTITY
from research_notes.cad_svg_import import interpret_native_svg

ROOT=Path(__file__).resolve().parents[1]
FIX=ROOT/'fixtures/drawing-families'

def generate():
    manifest=json.loads((FIX/'manifest.json').read_text());baseline=json.loads((FIX/'baseline.json').read_text())
    variants={'arc_circle':'candidate','quadratic_lines':'candidate','tspan_text':'candidate','split_dimensions':'candidate',
              'moved_labels':'candidate','outlined_text':'withheld','positioned_tspan':'withheld','bad_quantity':'withheld',
              'missing_projection':'withheld','wrong_views':'withheld'}
    for name,expected in variants.items():
        parent='quantity_two' if name=='bad_quantity' else 'unseen_small'
        data=(FIX/'inputs'/parent/'drawing.svg').read_bytes()
        ctx=json.loads((FIX/'inputs'/parent/'context-svg.json').read_text())
        root=ET.fromstring(data);ns='{http://www.w3.org/2000/svg}'
        group=next(e for e in root.iter() if e.get('id')=='DrawingContent')
        paths=[e for e in group.iter() if e.tag==ns+'path']
        selected={role:paths[int(ref.split(':')[1])] for role,ref in ctx['view_roles'].items()}
        parents={c:p for p in group.iter() for c in p}
        texts=[e for e in group.iter() if e.tag==ns+'text']
        if name=='arc_circle':
            for e in paths:
                if 'C' not in e.get('d',''):continue
                parsed=path_data(e.get('d'),IDENTITY);c=circle(parsed[0]);r=c['radius']
                start=parsed[0][0][1];d=f'M{start[0]} {start[1]}'
                for s in parsed[0]:d+=f' A{r} {r} 0 0 1 {s[-1][0]} {s[-1][1]}'
                e.set('d',d)
        elif name=='quadratic_lines':
            for e in paths:
                if 'C' in e.get('d',''):continue
                parsed=path_data(e.get('d'),IDENTITY);d=[]
                for path in parsed:
                    d.append('M'+' '.join(map(str,path[0][1])))
                    for _,a,b in path:d.append('Q'+' '.join(map(str,((a[0]+b[0])/2,(a[1]+b[1])/2,*b))))
                e.set('d',' '.join(d))
        elif name in ('tspan_text','positioned_tspan'):
            for e in texts:
                value=e.text;e.text=''
                a=ET.SubElement(e,ns+'tspan');a.text=value[:1]
                b=ET.SubElement(e,ns+'tspan');b.text=value[1:]
                if name=='positioned_tspan':b.set('dx','10')
        elif name=='split_dimensions':
            for e in paths:
                chunks=re.findall(r'M[^M]+',e.get('d',''))
                if len(chunks)==3:
                    p=parents[e]
                    for d in chunks:
                        new=copy.deepcopy(e);new.set('d',d);p.append(new)
                    p.remove(e)
        elif name=='moved_labels':
            for e in texts:e.set('y',str(float(e.get('y'))-float(e.get('font-size'))*.55))
        elif name=='outlined_text':
            from matplotlib.textpath import TextPath
            from matplotlib.font_manager import FontProperties
            for e in texts:
                glyph=TextPath((0,0),e.text,size=float(e.get('font-size')),prop=FontProperties(family='DejaVu Sans'))
                chunks=[]
                for v,kind in glyph.iter_segments(curves=True,simplify=False):
                    if kind==79:chunks.append('Z')
                    else:chunks.append({1:'M',2:'L',3:'Q',4:'C'}[kind]+' '.join(map(str,v)))
                replacement=ET.Element(ns+'path',d=' '.join(chunks),fill=e.get('fill','#212529'),stroke='none',
                                       transform=f"translate({e.get('x')},{e.get('y')}) scale(1,-1)")
                p=parents[e];p.insert(list(p).index(e),replacement);p.remove(e)
        elif name=='bad_quantity':
            next(e for e in texts if '2 x' in (e.text or '')).text='3 x 6 THRU'
        elif name=='missing_projection':ctx['projection']='unknown'
        elif name=='wrong_views':ctx['view_roles']['front'],ctx['view_roles']['top']=ctx['view_roles']['top'],ctx['view_roles']['front']
        if name!='wrong_views':
            updated=[e for e in group.iter() if e.tag==ns+'path']
            ctx['view_roles']={r:'path:'+str(updated.index(e)) for r,e in selected.items()}
        folder=FIX/'variants'/name;folder.mkdir(parents=True,exist_ok=False)
        svg=folder/'drawing.svg';svg.write_bytes(ET.tostring(root,encoding='utf-8',xml_declaration=True))
        context=folder/'context.json';context.write_bytes(json_bytes(ctx))
        old=interpret_native_svg(svg.read_bytes(),{**ctx,'family_assumption':FAMILY})
        baseline['observations'].append(dict(id=name+'_svg',status=old['status'],reason=old.get('reason_code'),detail=old.get('detail'),initial_unseen_setting=False))
        reason={'outlined_text':'text_unavailable','positioned_tspan':'svg_text_layout','bad_quantity':'quantity_conflict',
                'missing_projection':'projection_unknown','wrong_views':'dimension_conflict'}.get(name)
        manifest['cases'].append(dict(id=name+'_svg',part=parent,format='svg',family='plate',expected=expected,expected_reason=reason,cohort='derived_representation',
             variant=name,drawing=str(svg.relative_to(FIX)),context=str(context.relative_to(FIX)),
             drawing_sha256=hashlib.sha256(svg.read_bytes()).hexdigest(),context_sha256=hashlib.sha256(context.read_bytes()).hexdigest(),
             provenance='Derived from '+parent+' native SVG; outlined_text uses substituted DejaVu Sans glyphs; not a new CAD export'))
    (FIX/'manifest.json').write_bytes(json_bytes(manifest));(FIX/'baseline.json').write_bytes(json_bytes(baseline))

if __name__=='__main__':generate()
