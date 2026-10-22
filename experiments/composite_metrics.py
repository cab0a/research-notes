"""Evaluation-only independent shape/analytic measures; never imported by inference."""
import copy,math
from research_notes.step_reconstruction import read_step_input
from research_notes.parametric_features import shape_difference_volume
def canonical(p):
    p=copy.deepcopy(p)
    for f in p['features']:
        if f['kind']!='hole':f.setdefault('opening','top')
    p['features'].sort(key=lambda f:(f['kind']=='hole',f['x'],f['y']))
    return p
def numeric(p):
    return [p[k] for k in ('width','length','thickness')]+[v for f in canonical(p)['features'] for k,v in sorted(f.items()) if k not in ('kind','opening')]
def analytic(p):
    w,l,t=(p[k] for k in ('width','length','thickness'));v=w*l*t;a=2*(w*l+w*t+l*t)
    for f in p['features']:
        if f['kind']=='hole':
            r=f['diameter']/2;v-=math.pi*r*r*t;a+=2*math.pi*r*t-2*math.pi*r*r
        else:
            v-=f['width']*f['length']*f['depth']
            if f['kind']=='pocket':a+=2*f['depth']*(f['width']+f['length'])
            # At a two-boundary corner step, removed external walls equal the new internal walls.
    return v,a
def metrics(step,truth,p):
    actual=read_step_input(step);expected=read_step_input(truth);m=actual.metrics
    delta=shape_difference_volume(actual.shape,expected.shape);total=m.absolute_volume+expected.metrics.absolute_volume;intersection=(total-delta)/2
    v,a=analytic(p);iou=intersection/(total-intersection)
    result=dict(valid_solid=m.analyzer_valid and m.solid_count==1,step_read_success=True,
        bounds_error_mm=max(abs(x-y) for x,y in zip((*m.bounds_min,*m.bounds_max),(*expected.metrics.bounds_min,*expected.metrics.bounds_max))),
        volume_mm3=m.absolute_volume,area_mm2=m.surface_area,volume_error_mm3=abs(m.absolute_volume-v),area_error_mm2=abs(m.surface_area-a),
        same_kernel_iou=iou,symmetric_difference_mm3=delta)
    result['passed']=result['valid_solid'] and result['bounds_error_mm']<=1e-6 and result['volume_error_mm3']<=1e-5 and result['area_error_mm2']<=1e-5 and iou>=1-1e-8
    return actual,result
def edited(p,policy=None):
    if policy=='legacy_single_pocket':
        p=copy.deepcopy(p);p['width']+=5;p['features'][0]['width']+=2;p['features'][0]['depth']+=1;return p
    from research_notes.drawing_composites import edit
    return edit(p)
