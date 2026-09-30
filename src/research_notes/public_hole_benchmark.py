"""Repeat the six frozen public STEP inputs and cross-check bracket opening wires."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import statistics
import time
import zipfile

from research_notes.hole_inventory import analyze_step, inventory_csv, inventory_svg
from research_notes.public_step_corpus import CORPUS, verify_corpus


def boundary_crosscheck(shape, holes):
    """Measure rim perimeter and line centroid, without cylinder radius/location.

    This is a second measurement path in the SAME kernel, not independent CAD
    ground truth. Both endpoints must agree; no result is a general accuracy rate.
    """
    from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
    from OCP.BRepGProp import BRepGProp
    from OCP.BRepTools import BRepTools
    from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Plane
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import TopAbs_FACE, TopAbs_WIRE, TopAbs_EDGE
    from OCP.TopoDS import TopoDS
    from research_notes.brep_runtime import indexed_shapes, iter_shapes
    observations=[]
    for raw in iter_shapes(shape,TopAbs_FACE):
        face=TopoDS.Face_s(raw)
        if BRepAdaptor_Surface(face).GetType()!=GeomAbs_Plane:continue
        outer=BRepTools.OuterWire_s(face)
        for wire in iter_shapes(face,TopAbs_WIRE):
            if wire.IsSame(outer):continue
            edges=indexed_shapes(wire,TopAbs_EDGE)
            if edges.Extent()!=1:continue
            curve=BRepAdaptor_Curve(TopoDS.Edge_s(edges.FindKey(1)))
            if curve.GetType()!=GeomAbs_Circle or abs(curve.LastParameter()-curve.FirstParameter()-2*math.pi)>1e-7:continue
            props=GProp_GProps();BRepGProp.LinearProperties_s(wire,props)
            observations.append({'diameter_mm':props.Mass()/math.pi,'center_mm':list(props.CentreOfMass().Coord())})
    errors=[];used=set();matches=[]
    for hole in holes:
        entry=[hole['x_mm'],hole['y_mm'],hole['entry_z_mm']]
        ends=[entry,[v+hole['depth_mm']*d for v,d in zip(entry,hole['axis'])]]
        for end in ends:
            index=min((i for i in range(len(observations)) if i not in used),key=lambda i:math.dist(end,observations[i]['center_mm']))
            used.add(index);obs=observations[index]
            error=max(abs(obs['diameter_mm']-hole['diameter_mm']),math.dist(end,obs['center_mm']))
            errors.append(error);matches.append({'hole':hole['id'],'opening_center_mm':end,**obs,'max_error_mm':error})
    return {'measurement':'Planar inner-wire length / pi and linear centroid, same OCCT kernel',
            'independent_ground_truth':False,'circular_rims':len(observations),'matched_rims':len(used),
            'max_error_mm':max(errors,default=None),'passed':bool(errors) and max(errors)<=1e-6,
            'matches':matches}


def run(output, repeats=3):
    if not 1<=repeats<=10:raise ValueError('repeats must be between 1 and 10')
    manifest=verify_corpus();output=Path(output);output.mkdir(parents=True,exist_ok=True)
    for sub in ('csv','figures'):(output/sub).mkdir(exist_ok=True)
    records=[]
    for sample in manifest['samples']:
        path=CORPUS/sample['asset_path'];runs=[];times=[]
        for _ in range(repeats):
            start=time.perf_counter();result=analyze_step(path.read_bytes(),path.name,inspection=True,include_slots=False)
            times.append(time.perf_counter()-start);runs.append({k:v for k,v in result.items() if k!='preview'})
        records.append({'id':sample['sample_id'],'result':runs[0],'repeat_results_identical':all(r==runs[0] for r in runs),
                        'seconds':times,'median_seconds':statistics.median(times)})
        (output/'csv'/f"{sample['sample_id']}.csv").write_bytes(inventory_csv(result))
        if sample['sample_id']=='build123d_bracket':
            from research_notes.public_step import read_step_for_inspection
            audit=boundary_crosscheck(read_step_for_inspection(path).imported.shape,result['holes'])
            (output/'figures/bracket.svg').write_text(inventory_svg(result))
    paths=[Path(__file__),Path(__file__).with_name('public_hole_inventory.py'),Path(__file__).with_name('hole_inventory.py'),Path(__file__).with_name('public_step.py')]
    report={'version':'1.9.0','selection':'All six frozen public STEP files (five families) used during development; post-hoc verification, not held-out accuracy.',
            'summary':{'inputs':len(records),'repeats':repeats,'imported':sum(r['result']['status']!='rejected' for r in records),
                       'partially_recognized':sum(r['result']['status']=='partial' for r in records),
                       'verified_circular_holes':sum(r['result'].get('recognized_hole_count',0) for r in records),
                       'whole_counts_unknown':sum(r['result']['hole_count'] is None for r in records),
                       'repeat_results_identical':all(r['repeat_results_identical'] for r in records)},
            'timing_scope':'Includes local source read, STEP intake, qualification and optional tessellation; excludes CSV/SVG and cross-check; first run included.',
            'runtime':{'python':platform.python_version(),'platform':platform.platform(),'cadquery_ocp':importlib.metadata.version('cadquery-ocp')},
            'runtime_source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
            'manifest_sha256':hashlib.sha256((CORPUS/'manifest.json').read_bytes()).hexdigest(),
            'boundary_crosscheck':audit,'records':records}
    (output/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    fields=['id','status','solids','faces','recognized_circular_holes','whole_hole_count','preview_available','median_seconds']
    with (output/'results.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fields,lineterminator='\n');writer.writeheader()
        for row in records:
            r=row['result'];m=r['metrics'] or {}
            writer.writerow(dict(zip(fields,[row['id'],r['status'],m.get('solid_count'),m.get('face_count'),r.get('recognized_hole_count'),r['hole_count'],'preview_reason' not in r,row['median_seconds']])))
    with zipfile.ZipFile(output/'samples.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for asset in manifest['assets']:archive.write(CORPUS/asset['path'],asset['path'])
        archive.write(CORPUS/'manifest.json','manifest.json');archive.write(CORPUS/'README.md','README.md')
    print(json.dumps({'summary':report['summary'],'boundary_crosscheck_max_error_mm':audit['max_error_mm']},ensure_ascii=False,indent=2))
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',type=Path,default=Path('output/public-hole-inventory'));parser.add_argument('--repeats',type=int,default=3)
    args=parser.parse_args();report=run(args.output_dir,args.repeats)
    return 0 if report['summary']['imported']==6 and report['summary']['repeat_results_identical'] and report['boundary_crosscheck']['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
