"""Reproduce the scoped bracket-slot measurement and its declared controls."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
import platform
import statistics
import time
from pathlib import Path

from research_notes.brep_runtime import indexed_shapes, iter_shapes, step_round_trip
from research_notes.public_step import read_step_for_inspection
from research_notes.public_step_corpus import CORPUS, verify_corpus
from research_notes.slot_inventory import inspect_slots, scan_straight_through_slots

BRACKET = CORPUS / 'sources/build123d_bracket.step'
EXPECTED = [([10., -14., 3.], [0., 1., 0.]), ([10., 14., 3.], [0., 1., 0.]),
            ([20., -15.5, 3.], [1., 0., 0.]), ([20., 15.5, 3.], [1., 0., 0.]),
            ([30., -14., 3.], [0., 1., 0.]), ([30., 14., 3.], [0., 1., 0.])]


def boundary_crosscheck(shape, slots):
    """Use integrated edge lengths/centroids instead of circle support radii.

    Same OCCT kernel, NOT independent CAD or drawing ground truth. Observe all
    four-edge inner rims before matching IDs; each rim can be used only once.
    """
    from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
    from OCP.BRepGProp import BRepGProp
    from OCP.BRepTools import BRepTools
    from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Line, GeomAbs_Plane
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_WIRE
    from OCP.TopoDS import TopoDS

    edges = indexed_shapes(shape, TopAbs_EDGE)
    observations = {}
    for raw in iter_shapes(shape, TopAbs_FACE):
        face = TopoDS.Face_s(raw)
        if BRepAdaptor_Surface(face).GetType() != GeomAbs_Plane:
            continue
        for wire in iter_shapes(face, TopAbs_WIRE):
            if wire.IsSame(BRepTools.OuterWire_s(face)):
                continue
            members = indexed_shapes(wire, TopAbs_EDGE)
            if members.Extent() != 4:
                continue
            arcs, lines = [], []
            for i in range(1, 5):
                e = TopoDS.Edge_s(members.FindKey(i))
                c = BRepAdaptor_Curve(e)
                props = GProp_GProps()
                BRepGProp.LinearProperties_s(e, props)
                if c.GetType() == GeomAbs_Circle:
                    arcs.append(props.Mass())
                elif c.GetType() == GeomAbs_Line:
                    a, b = c.Value(c.FirstParameter()).Coord(), c.Value(c.LastParameter()).Coord()
                    lines.append((props.Mass(), [(y - x) / props.Mass() for x, y in zip(a, b)]))
            if len(arcs) != 2 or len(lines) != 2:
                continue
            props = GProp_GProps()
            BRepGProp.LinearProperties_s(wire, props)
            width = sum(arcs) / math.pi
            ids = tuple(sorted(edges.FindIndex(members.FindKey(i)) for i in range(1, 5)))
            observations[ids] = {'width_mm': width, 'length_mm': sum(x[0] for x in lines) / 2 + width,
                                 'center_mm': list(props.CentreOfMass().Coord()), 'direction': lines[0][1]}
    matches, used, errors, directions = [], set(), [], []
    for slot in slots:
        ends = []
        for ids, center in zip(slot['opening_edges'], (slot['entry_center_mm'], slot['exit_center_mm'])):
            key = tuple(ids)
            if key in used or key not in observations:
                return {'passed': False, 'reason': 'Missing or duplicate opening boundary.'}
            used.add(key)
            obs = observations[key]
            error = max(abs(obs['width_mm'] - slot['width_mm']), abs(obs['length_mm'] - slot['length_mm']),
                        math.dist(obs['center_mm'], center))
            direction_error = 1 - abs(sum(a * b for a, b in zip(obs['direction'], slot['longitudinal_direction'])))
            errors.append(error)
            directions.append(abs(direction_error))
            matches.append({'slot': slot['id'], 'opening_edges': list(key), **obs, 'max_error_mm': error})
            ends.append(obs['center_mm'])
        displacement = [b - a for a, b in zip(*ends)]
        depth = math.dist(*ends)
        errors.append(abs(depth - slot['depth_mm']))
        directions.append(max(abs(d / depth - a) for d, a in zip(displacement, slot['through_direction'])))
    return {'method': 'Integrated arc lengths / pi, straight-edge lengths, wire centroids and centroid separation',
            'independent_ground_truth': False, 'same_kernel': True,
            'observed_four_edge_inner_rims': len(observations), 'matched_rims': len(used),
            'max_length_error_mm': max(errors, default=None), 'max_direction_error': max(directions, default=None),
            'length_threshold_mm': 1e-6, 'direction_threshold': 1e-7,
            'passed': bool(slots) and max(errors) <= 1e-6 and max(directions) <= 1e-7, 'matches': matches}


def capsule_prism(*, radius=1., z=-1., height=6.):
    """Authored capsule, centres (5,5) and (9,5), for declared regression truth."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeWire
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
    from OCP.GC import GC_MakeArcOfCircle
    from OCP.gp import gp_Pnt, gp_Vec

    p1, p2, p3, p4 = [gp_Pnt(x, y, z) for x, y in ((5, 5-radius), (9, 5-radius), (9, 5+radius), (5, 5+radius))]
    wire = BRepBuilderAPI_MakeWire()
    for edge in (BRepBuilderAPI_MakeEdge(p1, p2).Edge(),
                 BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(p2, gp_Pnt(9+radius, 5, z), p3).Value()).Edge(),
                 BRepBuilderAPI_MakeEdge(p3, p4).Edge(),
                 BRepBuilderAPI_MakeEdge(GC_MakeArcOfCircle(p4, gp_Pnt(5-radius, 5, z), p1).Value()).Edge()):
        wire.Add(edge)
    return BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeFace(wire.Wire()).Face(), gp_Vec(0, 0, height)).Shape()


def control_shapes():
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Pnt, gp_Dir

    plate = BRepPrimAPI_MakeBox(14., 10., 4.).Shape()
    slot = BRepAlgoAPI_Cut(plate, capsule_prism()).Shape()
    return {
        'through': slot,
        'blind': BRepAlgoAPI_Cut(plate, capsule_prism(z=2., height=3.)).Shape(),
        'open_notch': BRepAlgoAPI_Cut(BRepPrimAPI_MakeBox(7., 10., 4.).Shape(), capsule_prism()).Shape(),
        'stepped_capsule': BRepAlgoAPI_Cut(slot, capsule_prism(radius=2., z=2., height=3.)).Shape(),
        'stepped_rectangle': BRepAlgoAPI_Cut(slot, BRepPrimAPI_MakeBox(gp_Pnt(3., 2., 2.), 8., 6., 3.).Shape()).Shape(),
        'round_hole': BRepAlgoAPI_Cut(plate, BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(7,5,-1), gp_Dir(0,0,1)), 1., 6.).Shape()).Shape(),
        'boss': BRepAlgoAPI_Fuse(plate, capsule_prism(z=3., height=3.)).Shape(),
        'interrupted': BRepAlgoAPI_Fuse(slot, BRepPrimAPI_MakeBox(gp_Pnt(6., 0., 1.), 1., 10., 1.).Shape()).Shape(),
    }


def plot_bracket(shape, result, target):
    """Plot measured source curves and numbered slots, never a generated mockup."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopoDS import TopoDS

    fig = plt.figure(figsize=(13, 6.5))
    fig.subplots_adjust(bottom=.14, top=.83, left=.04, right=.98, wspace=.15)
    ax = fig.add_subplot(121, projection='3d')
    plan = fig.add_subplot(122)
    edges = indexed_shapes(shape, TopAbs_EDGE)
    highlight = {e for s in result['slots'] for opening in s['opening_edges'] for e in opening}
    top = {e for s in result['slots'] for e in s['opening_edges'][0]}
    for i in range(1, edges.Extent()+1):
        c = BRepAdaptor_Curve(TopoDS.Edge_s(edges.FindKey(i)))
        pts = [c.Value(c.FirstParameter()+k*(c.LastParameter()-c.FirstParameter())/64).Coord() for k in range(65)]
        xs, ys, zs = zip(*pts)
        ax.plot(xs, ys, zs, color='#d66b24' if i in highlight else '#80929b', lw=1.7 if i in highlight else .65)
        if i in top or (all(abs(z-3) < 1e-6 for z in zs) and i not in highlight):
            plan.plot(xs, ys, color='#d66b24' if i in top else '#80929b', lw=1.8 if i in top else .9)
    for s in result['slots']:
        x,y,z = s['entry_center_mm']
        ax.text(x,y,z+2,s['id'],fontsize=10,color='#8d3610')
        d = s['longitudinal_direction']
        plan.annotate(s['id'], (x,y), xytext=(x,y+(4.8 if abs(d[1])>.5 else 3.2)),
                      ha='center', weight='bold', color='#8d3610')
        plan.arrow(x-d[0],y-d[1],2*d[0],2*d[1],width=.10,head_width=.7,color='#126b70',length_includes_head=True)
    ax.set(xlabel='X (mm)',ylabel='Y (mm)',zlabel='Z (mm)',title='Source bracket: 6 qualified straight through slots')
    ax.set_box_aspect((35,41,51))
    ax.view_init(elev=24,azim=35)
    plan.set(xlabel='X (mm)',ylabel='Y (mm)',title='Entry openings at Z = 3 mm\nWidth 4.5 / overall length 7.5 / through length 3 mm')
    plan.set_aspect('equal')
    plan.grid(alpha=.18)
    fig.suptitle('v1.10.0  |  build123d bracket  |  STEP coordinates retained',fontsize=15)
    fig.text(.5,.025,'Orange: verified slot rims   |   Arrows: long axis   |   Whole-part opening count remains unknown',ha='center',fontsize=10)
    fig.savefig(target,dpi=160)
    plt.close(fig)


def run(output, repeats=3):
    if not 1 <= repeats <= 10:
        raise ValueError('repeats must be between 1 and 10')
    manifest = verify_corpus()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    runs, seconds = [], []
    for _ in range(repeats):
        start = time.perf_counter()
        runs.append(inspect_slots(BRACKET))
        seconds.append(time.perf_counter()-start)
    result = runs[0]
    shape = read_step_for_inspection(BRACKET).imported.shape
    audit = boundary_crosscheck(shape, result['slots'])
    fixed_match = len(result['slots']) == len(EXPECTED) and all(
        s['entry_center_mm'] == c and s['longitudinal_direction'] == d
        and [s['width_mm'], s['length_mm'], s['depth_mm']] == [4.5,7.5,3.]
        and s['through_direction'] == [0.,0.,-1.] for s,(c,d) in zip(result['slots'],EXPECTED))
    controls = []
    for name, solid in control_shapes().items():
        for stage, body in [('constructed', solid), ('step_imported', step_round_trip(solid, 'slot_'+name).imported_shape)]:
            observed = scan_straight_through_slots(body)
            expected = 1 if name == 'through' else 0
            dimensions = name != 'through' or all([s['width_mm'], s['length_mm'], s['depth_mm']] == [2.,6.,4.] for s in observed['slots'])
            controls.append({'name': name, 'stage': stage, 'expected_count': expected,
                             'recognized_slot_count': observed['recognized_slot_count'],
                             'passed': observed['recognized_slot_count'] == expected and dimensions,
                             'result': observed})
    passed = fixed_match and all(r == result for r in runs) and audit['passed'] and all(c['passed'] for c in controls)
    report = {'version': '1.10.0', 'passed': passed, 'selection': 'One fixed public bracket used in development; post-hoc qualification, not held-out accuracy.',
              'expected_bracket_basis': 'Manual inspection of frozen STEP opening geometry; no original engineering drawing. Six expected positions and dimensions fixed in the benchmark, not inferred from recognition output.',
              'source_manifest_sha256': hashlib.sha256((CORPUS/'manifest.json').read_bytes()).hexdigest(),
              'source_asset': next(a for a in manifest['assets'] if a['path']=='sources/build123d_bracket.step'),
              'runtime': {'python': platform.python_version(), 'platform': platform.platform(), 'cadquery_ocp': importlib.metadata.version('cadquery-ocp')},
              'code_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),Path(__file__).with_name('slot_inventory.py'))},
              'repeats': repeats, 'repeat_results_identical': all(r == result for r in runs),
              'seconds': seconds, 'median_seconds': statistics.median(seconds),
              'timing_scope': 'STEP snapshot/import and slot recognition, first run included; excludes controls, cross-check, plotting and file output.',
              'bracket_expectations_match': fixed_match, 'result': result, 'boundary_crosscheck': audit, 'controls': controls}
    (output/'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    fields = ['id','width_mm','length_mm','depth_mm','entry_x_mm','entry_y_mm','entry_z_mm','long_x','long_y','long_z','through_x','through_y','through_z']
    with (output/'bracket-slots.csv').open('w',newline='',encoding='utf-8') as stream:
        writer = csv.writer(stream,lineterminator='\n')
        writer.writerow(fields)
        for s in result['slots']:
            writer.writerow([s['id'],s['width_mm'],s['length_mm'],s['depth_mm'],*s['entry_center_mm'],*s['longitudinal_direction'],*s['through_direction']])
    plot_bracket(shape,result,output/'bracket-slots.png')
    print(json.dumps({'passed':passed,'recognized_slots':result['recognized_slot_count'],'controls_passed':sum(c['passed'] for c in controls),'controls':len(controls),'max_error_mm':audit.get('max_length_error_mm')},indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=Path('output/bracket-slot-inventory'))
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    return 0 if run(args.output_dir, args.repeats)['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
