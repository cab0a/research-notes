"""Bounded textual callouts attached to native graphical dimensions, nominal/tolerance separated."""
import re
from .cad_svg_import import need
N=r'[0-9]+(?:\.[0-9]+)?'
T=r'(?:(?:±|\+/-)\s*('+N+r')|([+-]'+N+r')\s*/\s*([+-]'+N+r'))'
def callout(text,diameter=False):
    prefix=r'(?:(\d+)\s*[x×]\s*)?' if diameter else ''
    # Depth is nominal, in mm; diameter and linear dimensions can carry numeric deviations.
    pattern=prefix+r'('+N+r')(?:\s*'+T+r')?'+(r'(?:\s+(THRU)|\s+DEPTH\s+('+N+r'))?' if diameter else '')
    m=re.fullmatch(pattern,text.strip())
    need(m is not None,'unsupported_annotation',text,'unsupported_input')
    g=list(m.groups());count=int(g.pop(0) or 1) if diameter else 1
    nominal=float(g[0]);sym,upper,lower=g[1:4]
    tol=None
    if sym is not None:tol=dict(lower=-float(sym),upper=float(sym))
    elif upper is not None:tol=dict(lower=float(lower),upper=float(upper))
    need(0<nominal<=1000 and 1<=count<=3,'invalid_dimension',text)
    if tol:need(tol['lower']<=tol['upper'] and nominal+tol['lower']>0 and max(abs(tol['lower']),abs(tol['upper']))<=100,
                'invalid_tolerance','ordered numeric deviations and positive lower size required','input_ambiguity')
    through=bool(g[4]) if diameter else False;depth=float(g[5]) if diameter and g[5] is not None else None
    if depth is not None:need(0<depth<=1000,'invalid_depth',text)
    return dict(nominal=nominal,count=count,through=through,depth=depth,tolerance=tol)
def annotation(text,diameter=False):
    a=callout(text,diameter);return a['nominal'],a['count'],a['through']
