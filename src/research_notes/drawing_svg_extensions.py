"""Conservative SVG syntax adapter. Original bytes remain the provenance source."""
import math,re,xml.etree.ElementTree as ET
from .svg_drawing_graphics import NUMBER,check,path_data,IDENTITY
from .drawing_to_cad import DrawingIssue

def arc_cubics(a,v):
    rx,ry,rotation,large,sweep,x,y=v;b=(x,y)
    check(rx>0 and abs(rx-ry)<1e-8 and large in (0,1) and sweep in (0,1),
          'svg_arc','only positive circular arcs with binary flags')
    dx,dy=(a[0]-x)/2,(a[1]-y)/2;norm=dx*dx+dy*dy
    check(norm>1e-12 and norm<=rx*rx*(1+1e-10),'svg_arc','no implicit radius correction or coincident endpoints')
    factor=math.sqrt(max(0,(rx*rx-norm)/norm))*(-1 if large==sweep else 1)
    center=((a[0]+x)/2+factor*dy,(a[1]+y)/2-factor*dx)
    t0=math.atan2(a[1]-center[1],a[0]-center[0]);t1=math.atan2(y-center[1],x-center[0])
    delta=(t1-t0)%(2*math.pi) if sweep else -((t0-t1)%(2*math.pi))
    n=max(1,math.ceil(abs(delta)/(math.pi/2)-1e-10));out=[]
    for i in range(n):
        u=t0+delta*i/n;w=t0+delta*(i+1)/n;k=4/3*math.tan((w-u)/4)
        start=(center[0]+rx*math.cos(u),center[1]+rx*math.sin(u));end=(center[0]+rx*math.cos(w),center[1]+rx*math.sin(w))
        c=(start[0]-k*rx*math.sin(u),start[1]+k*rx*math.cos(u))
        d=(end[0]+k*rx*math.sin(w),end[1]-k*rx*math.cos(w))
        out.append('C'+' '.join(f'{q:.12g}' for p in (c,d,end) for q in p))
    return out,b

def expand_path(value):
    pattern=NUMBER+r'|[A-Za-z]';tokens=re.findall(pattern,value)
    check(not re.sub(pattern,'',value).strip(' ,\n\r\t') and len(tokens)<=2048,'svg_path','bounded path')
    arity={'M':2,'L':2,'H':1,'V':1,'C':6,'Q':4,'A':7};i=0;cmd=None;pos=(0.,0.);start=pos;out=[]
    while i<len(tokens):
        if tokens[i].isalpha():
            cmd=tokens[i];i+=1
            check(cmd.upper() in {*arity,'Z'},'svg_path','unsupported path command')
            if cmd.upper()=='Z':out.append('Z');pos=start;cmd=None;continue
        check(cmd is not None,'svg_path','command missing');kind=cmd.upper();n=arity[kind]
        check(i+n<=len(tokens) and not any(t.isalpha() for t in tokens[i:i+n]),'svg_path','coordinates missing')
        v=[float(t) for t in tokens[i:i+n]];i+=n
        check(all(math.isfinite(x) and abs(x)<=1e6 for x in v),'svg_number','bounded finite coordinates')
        rel=cmd.islower()
        if kind in ('M','L','C','Q'):
            pairs=[(v[j]+(pos[0] if rel else 0),v[j+1]+(pos[1] if rel else 0)) for j in range(0,n,2)]
            if kind=='Q':
                q,b=pairs
                # Exact quadratic-to-cubic conversion; noncircle curves remain rejected by the shape grammar.
                c=tuple(pos[j]+2/3*(q[j]-pos[j]) for j in range(2))
                d=tuple(b[j]+2/3*(q[j]-b[j]) for j in range(2))
                if abs((q[0]-pos[0])*(b[1]-pos[1])-(q[1]-pos[1])*(b[0]-pos[0]))<1e-9 and all(min(pos[j],b[j])-1e-9<=q[j]<=max(pos[j],b[j])+1e-9 for j in range(2)):
                    out.append('L'+' '.join(map(str,b)))
                else:out.append('C'+' '.join(str(x) for p in (c,d,b) for x in p))
            else:out.append(kind+' '.join(str(x) for p in pairs for x in p))
            pos=pairs[-1]
            if kind=='M':start=pos;cmd='l' if rel else 'L'
        elif kind in ('H','V'):
            pos=(v[0]+(pos[0] if rel else 0),pos[1]) if kind=='H' else (pos[0],v[0]+(pos[1] if rel else 0))
            out.append('L'+' '.join(map(str,pos)))
        else:
            if rel:v[-2]+=pos[0];v[-1]+=pos[1]
            chunks,pos=arc_cubics(pos,v);out.extend(chunks)
    return ' '.join(out)

def adapt_svg(source):
    check(0<len(source)<=500000 and b'<!DOCTYPE' not in source.upper() and b'<!ENTITY' not in source.upper(),
          'input_format','bounded XML without entities')
    root=ET.fromstring(source);log=[];elements=list(root.iter())
    drawing=next((e for e in elements if e.get('id')=='DrawingContent'),root)
    original_paths=[e for e in drawing.iter() if e.tag.split('}')[-1]=='path']
    check(len(elements)<=5000,'input_format','element limit')
    for e in elements:
        tag=e.tag.split('}')[-1]
        if tag=='text' and len(e):
            check(all(c.tag.split('}')[-1]=='tspan' and not c.attrib and not len(c) for c in e),
                  'svg_text_layout','only unpositioned unstyled tspan runs are supported')
            text=''.join(e.itertext())
            for c in list(e):e.remove(c)
            e.text=text;log.append('plain tspan runs flattened without repositioning')
        if tag=='path' and re.search('[AQaq]',e.get('d','')):
            e.set('d',expand_path(e.get('d')));log.append('circular arcs/quadratics normalized')
    # Retain original parent grouping. Do not infer arbitrary scattered lines as a dimension.
    for g in elements:
        children=list(g)
        if g.tag.split('}')[-1]=='g' and len(children)==3 and all(c.tag.split('}')[-1]=='path' for c in children):
            parsed=[path_data(c.get('d',''),IDENTITY) for c in children]
            if all(len(p)==1 and len(p[0])==1 and p[0][0][0]=='L' for p in parsed) and all(c.attrib.keys()<= {'d','fill-rule','vector-effect'} for c in children):
                children[0].set('d',' '.join(c.get('d') for c in children))
                for c in children[1:]:g.remove(c)
                log.append('three sibling line paths regrouped')
    current=[e for e in drawing.iter() if e.tag.split('}')[-1]=='path']
    mapping={f'path:{i}':f'path:{current.index(e)}' for i,e in enumerate(original_paths) if e in current}
    return ET.tostring(root),log,mapping
