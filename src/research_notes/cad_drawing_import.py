"""Bounded FreeCAD TechDraw DXF interpretation. No source CAD/truth file access.

DIMENSION definition points and displayed text provide design evidence. The
SVG route records unsupported export graphics, never substitutes the paired DXF.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import hashlib
import io
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from .drawing_to_cad import DrawingIssue, FAMILY, require, interpret_svg, candidate_code, feature_model, json_bytes

EPS = 1e-6  # drawing-coordinate units; not a manufacturing tolerance
NUM = r'[0-9]+(?:\.[0-9]+)?'


def xy(value):
    values = tuple(float(v) for v in value)
    require(len(values) == 3 and all(math.isfinite(v) and abs(v) < 10000 for v in values)
            and abs(values[2]) <= EPS, 'nonplanar_geometry', 'unsupported_input', 'bounded XY drawing required')
    return values[:2]


def near(a,b):
    return math.dist(a,b) <= EPS


def on_border(p, box):
    x,y,u,v=box
    return (x-EPS <= p[0] <= x+u+EPS and y-EPS <= p[1] <= y+v+EPS
            and min(abs(p[0]-x),abs(p[0]-x-u),abs(p[1]-y),abs(p[1]-y-v)) <= EPS)


def same_border(points, box):
    x,y,u,v=box
    return all(on_border(p,box) for p in points) and any(
        all(abs(p[axis]-value)<=EPS for p in points) for axis,value in ((0,x),(0,x+u),(1,y),(1,y+v)))


def geometry(entities, role):
    lines, circles, splines = [], [], []
    for e in entities:
        if e.dxftype() == 'LINE':
            a,b=xy(e.dxf.start),xy(e.dxf.end)
            require(not near(a,b) and (abs(a[0]-b[0])<=EPS or abs(a[1]-b[1])<=EPS),
                    'unsupported_geometry','unsupported_input','nonzero axis-aligned edges required')
            lines.append((a,b,e.dxf.handle))
        elif e.dxftype() == 'CIRCLE':
            c,r=xy(e.dxf.center),float(e.dxf.radius)
            require(role=='top' and math.isfinite(r) and EPS<r<1000,'unsupported_geometry','unsupported_input','top circles only')
            if not any(near(c,o['center']) and abs(r-o['radius'])<=EPS for o in circles):
                circles.append(dict(center=c,radius=r,id=e.dxf.handle))
        elif e.dxftype() == 'SPLINE': splines.append(e)
        else: raise DrawingIssue('unsupported_entity','unsupported_input',e.dxftype())
    require(lines,'unsupported_profile','drawing_recognition',role)
    points=[p for a,b,_ in lines for p in (a,b)]
    x,y=min(p[0] for p in points),min(p[1] for p in points)
    u,v=max(p[0] for p in points)-x,max(p[1] for p in points)-y
    require(u>EPS and v>EPS,'unsupported_profile','drawing_recognition',role)
    box=(x,y,u,v)
    corners=[(x,y),(x+u,y),(x+u,y+v),(x,y+v)]
    for a,b in zip(corners,corners[1:]+corners[:1]):
        require(any((near(a,c) and near(b,d)) or (near(a,d) and near(b,c)) for c,d,_ in lines),
                'unsupported_profile','drawing_recognition','four complete rectangular sides required')
    internal=[]
    for a,b,handle in lines:
        if same_border((a,b),box): continue
        require(role!='top' and abs(a[0]-b[0])<=EPS and abs(min(a[1],b[1])-y)<=EPS
                and abs(max(a[1],b[1])-y-v)<=EPS,'unsupported_geometry','unsupported_input','unclassified interior edge')
        if not any(near(a,c) and near(b,d) or near(a,d) and near(b,c) for c,d,_ in internal):internal.append((a,b,handle))
    for e in splines:
        cp=[xy(p) for p in e.control_points]
        weights=list(e.weights)
        # With positive weights a B-spline lies in its control-point convex hull.
        # Ignore only a curve proven confined to one already present straight edge.
        require(len(cp)>=2 and len(cp)<=256 and same_border(cp,box)
                and all(math.isfinite(w) and w>0 for w in weights),
                'unsupported_spline','unsupported_input','only control hulls on an existing border are covered')
    return dict(box=box,circles=circles,internal=internal,dimensions={},positions={},diameters={},
                discarded_border_splines=[e.dxf.handle for e in splines])


def interpret_cad_drawing(source:bytes, context:dict, format:str):
    base=dict(schema_version='1.0.0',source_sha256=hashlib.sha256(source).hexdigest(),human_context=context,
              method='C_FreeCAD_TechDraw_DXF_dimensions',input_format=format,ai_used=False,original_authoring_history_recovered=False)
    evidence=[]; inventory={}
    try:
        require(isinstance(source,bytes) and 0<len(source)<=500000,'input_format','unsupported_input','bounded input required')
        require(isinstance(context,dict) and set(context)=={'projection','unit','family_assumption','view_roles'},
                'context_missing','input_ambiguity','family, unit, projection and view layers only')
        require(context['unit']=='mm' and context['family_assumption']==FAMILY,'unsupported_context','unsupported_input','declared mm plate family required')
        roles=context['view_roles']
        require(isinstance(roles,dict) and set(roles)=={'top','front','right'} and all(isinstance(v,str) for v in roles.values())
                and len(set(roles.values()))==3,'view_mapping','input_ambiguity','three distinct view layers')
        require(context['projection'] in ('first_angle','third_angle'),'projection_unknown','input_ambiguity','explicit projection required')
        if format=='svg':
            require(b'<!DOCTYPE' not in source.upper() and b'<!ENTITY' not in source.upper(),'input_format','unsupported_input','no entities')
            root=ET.fromstring(source); elements=list(root.iter())
            require(len(elements)<5000 and root.tag.split('}')[-1]=='svg','input_format','unsupported_input','bounded SVG')
            inventory={'tags':dict(Counter(e.tag.split('}')[-1] for e in elements)),
                       'transforms':sum('transform' in e.attrib for e in elements),
                       'cubic_paths':sum('C' in e.get('d','') for e in elements),
                       'visible_text':[''.join(e.itertext()) for e in elements if e.tag.split('}')[-1]=='text']}
            raise DrawingIssue('svg_export_graphics_unsupported','unsupported_input',
                               'Native TechDraw SVG has transformed paths/text; no validated normalizer yet. Paired DXF is not used.')
        require(format=='dxf','input_format','unsupported_input','SVG or DXF required')
        import ezdxf
        # FreeCAD 1.1.4 emits UTF-8 even with ANSI_1252 header. Decode strictly;
        # other encodings are not silently guessed in this bounded experiment.
        try:
            doc=ezdxf.read(io.StringIO(source.decode('utf-8')))
        except (ezdxf.DXFError, UnicodeDecodeError) as error:
            raise DrawingIssue('invalid_dxf','drawing_recognition',str(error)) from error
        require(doc.units==4,'drawing_unit_mismatch','drawing_conflict','DXF $INSUNITS must specify millimetres')
        entities=list(doc.modelspace())
        require(len(entities)<=1024,'input_format','unsupported_input','too many entities')
        inventory={'entities':dict(Counter(e.dxftype() for e in entities)), 'dxf_version_after_read':doc.dxfversion,
                   'encoding_policy':'strict UTF-8; exporter header ANSI_1252 is not trusted',
                   'line_visibility':'exported geometry has no reliable hidden/visible distinction; interpreted under family prior'}
        for e in entities:
            require(e.dxftype() in {'LINE','CIRCLE','SPLINE','DIMENSION'},'unsupported_entity','unsupported_input',e.dxftype())
            layer=doc.layers.get(e.dxf.layer)
            require(not layer.is_off() and not layer.is_frozen() and not e.dxf.get('invisible',0),
                    'hidden_entity','unsupported_input','invisible or disabled layers require review')
            require(e.dxftype()=='DIMENSION' or e.dxf.layer in roles.values(),'unmapped_geometry','input_ambiguity','geometry outside selected views')
            require(near(tuple(e.dxf.get('extrusion',(0,0,1)))[:2],(0,0)) and e.dxf.get('extrusion',(0,0,1))[2]==1,
                    'unsupported_orientation','unsupported_input','default extrusion required')
        views={role:geometry([e for e in entities if e.dxf.layer==layer and e.dxftype()!='DIMENSION'],role) for role,layer in roles.items()}
        for dim in (e for e in entities if e.dxftype()=='DIMENSION'):
            kind=dim.dxf.dimtype & 15; text=dim.dxf.text.strip()
            require(kind in (0,3),'unsupported_dimension_type','unsupported_input',str(kind))
            block=doc.blocks.get(dim.dxf.geometry)
            require(block is not None,'dimension_picture_missing','input_ambiguity','dimension block missing')
            require(not dim.xdata and all(e.dxftype() in {'LINE','TEXT','SOLID'} and not e.dxf.get('invisible',0) for e in block),
                    'unsupported_dimension_picture','unsupported_input','dimension overrides or unsupported picture entities')
            labels=[e.dxf.text.strip() for e in block if e.dxftype()=='TEXT']
            require(labels==[text],'dimension_display_conflict','drawing_conflict','DIMENSION and block text differ')
            pattern=NUM if kind==0 else '('+NUM+r')(?:\s+(THRU))?'
            match=re.fullmatch(pattern,text)
            require(match is not None,'unsupported_annotation','unsupported_input',text)
            value=float(text) if kind==0 else float(match[1])
            require(1e-4<value<=1000,'invalid_dimension','drawing_recognition',text)
            if kind==0:
                angle=dim.dxf.get('angle',0)%180
                require(abs(angle)<=EPS or abs(angle-90)<=EPS,'unsupported_dimension_direction','unsupported_input','X/Y only')
                axis=0 if abs(angle)<=EPS else 1
                a,b=xy(dim.dxf.defpoint2),xy(dim.dxf.defpoint3)
                matches=[]
                for role,vw in views.items():
                    box=vw['box'];x,y,u,v=box
                    anchors=[(x,y),(x+u,y),(x,y+v),(x+u,y+v)]+[c['center'] for c in vw['circles']]
                    if all(any(near(p,q) for q in anchors) for p in (a,b)):matches.append(role)
                require(len(matches)==1,'dimension_target_ambiguous','input_ambiguity','definition points must identify one view')
                role=matches[0];vw=views[role];box=vw['box'];endpoints=sorted((a[axis],b[axis]))
                full=[box[axis],box[axis]+box[axis+2]]
                if near(endpoints,full):
                    key={'top':('W','L'),'front':('W','T'),'right':('L','T')}[role][axis]
                    require(key not in vw['dimensions'],'dimension_conflict','drawing_conflict','duplicate overall dimension')
                    vw['dimensions'][key]=value; target=key
                else:
                    require(role=='top','unsupported_dimension_chain','unsupported_input','only baseline hole positions')
                    targets=[i for i,c in enumerate(vw['circles']) if near(endpoints,sorted((box[axis],c['center'][axis])))]
                    require(len(targets)==1,'dimension_target_ambiguous','input_ambiguity','one baseline hole required')
                    i=targets[0];key='x' if axis==0 else 'y'
                    require((i,key) not in vw['positions'],'dimension_conflict','drawing_conflict','duplicate position')
                    vw['positions'][i,key]=value;target=vw['circles'][i]['id']+':'+key
            else:
                require(match[2]=='THRU','hole_extent_ambiguous','input_ambiguity','no explicit through indication')
                a,b=xy(dim.dxf.defpoint),xy(dim.dxf.defpoint4);center=tuple((p+q)/2 for p,q in zip(a,b));r=math.dist(a,b)/2
                role='top';vw=views[role]
                matches=[i for i,c in enumerate(vw['circles']) if near(center,c['center']) and abs(r-c['radius'])<=EPS]
                require(len(matches)==1,'diameter_target_ambiguous','input_ambiguity','diameter endpoints must match one circle')
                i=matches[0];require(i not in vw['diameters'],'dimension_conflict','drawing_conflict','duplicate diameter')
                vw['diameters'][i]=value;target=vw['circles'][i]['id']
            evidence.append(dict(view=role,dimension_line_id=dim.dxf.handle,text_id=dim.dxf.geometry,
                                 visible_text=text,value_mm=value,kind='linear' if kind==0 else 'diameter',parameter=target,
                                 definition_points=[a,b]))
        canonical=ET.Element('svg')
        for role,vw in views.items():
            required={'top':{'W','L'},'front':{'W','T'},'right':{'L','T'}}[role]
            require(set(vw['dimensions'])==required,'dimension_missing','input_ambiguity',role)
            g=ET.SubElement(canonical,'g',id=roles[role]);x,y,u,v=vw['box']
            ET.SubElement(g,'rect',x=str(x),y=str(-y-v),width=str(u),height=str(v))
            for key,value in vw['dimensions'].items():ET.SubElement(g,'text').text=f'{key}={value:g}'
            for i,c in enumerate(vw['circles']):
                require((i,'x') in vw['positions'] and (i,'y') in vw['positions'],'hole_position_missing','input_ambiguity','both baseline positions required')
                require(i in vw['diameters'],'hole_diameter_missing','input_ambiguity','each circle needs a diameter')
                ET.SubElement(g,'circle',id=c['id'],cx=str(c['center'][0]),cy=str(-c['center'][1]),r=str(c['radius']))
                ET.SubElement(g,'text').text=f"X={vw['positions'][i,'x']:g} Y={vw['positions'][i,'y']:g} DIA={vw['diameters'][i]:g} THRU"
            for a,b,handle in vw['internal']:
                ET.SubElement(g,'line',id=handle,x1=str(a[0]),y1=str(-a[1]),x2=str(b[0]),y2=str(-b[1]),attrib={'stroke-dasharray':'1 1'})
        validated=interpret_svg(ET.tostring(canonical),context)
        return {**validated,**base,'dimension_evidence':evidence,'inventory':inventory,
                'normalization':{'border_splines':{k:v['discarded_border_splines'] for k,v in views.items()},
                                 'duplicates':'coincident geometry deduplicated','visibility':'interior full-height edges treated as hidden under declared family'},
                'claim_boundary':'Conditional candidate from FreeCAD TechDraw DXF development fixtures; no general CAD exporter or held-out accuracy claim.'}
    except DrawingIssue as error:
        return {**base,'status':'withheld','reason_code':error.code,'failure_stage':error.stage,'detail':str(error),
                'dimension_evidence':evidence,'inventory':inventory}
    except (ValueError,TypeError,KeyError,AttributeError,ET.ParseError) as error:
        return {**base,'status':'withheld','reason_code':'invalid_input','failure_stage':'drawing_recognition','detail':str(error),
                'dimension_evidence':evidence,'inventory':inventory}


def main(argv=None):
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('drawing',type=Path);parser.add_argument('context',type=Path);parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args(argv)
    if args.output_dir.exists() and (not args.output_dir.is_dir() or any(args.output_dir.iterdir())):parser.error('use a new or empty output directory')
    with args.drawing.open('rb') as stream:source=stream.read(500001)
    result=interpret_cad_drawing(source,json.loads(args.context.read_text()),args.drawing.suffix[1:].lower())
    args.output_dir.mkdir(parents=True,exist_ok=True)
    (args.output_dir/'inference.json').write_bytes(json_bytes(result))
    if result['status']=='candidate':
        (args.output_dir/'candidate.py').write_text(candidate_code(result['parameters'],result['source_sha256']))
        (args.output_dir/'model.json').write_bytes(json_bytes(asdict(feature_model(result['parameters'],result['source_sha256']))))
    print(json.dumps({'status':result['status'],'reason':result.get('reason_code')}))


if __name__=='__main__':main()
