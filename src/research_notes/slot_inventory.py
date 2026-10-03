"""Locally qualify straight, constant-width capsule through slots (v1.10).

The result is never a certificate of all openings in a part. The dedicated API
and CLI are also used by the unified hole inventory introduced in v1.11.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from research_notes.brep_runtime import indexed_shapes, iter_shapes, surface_area_and_centroid
from research_notes.feature_recognition import _face_geometry
from research_notes.local_material import LocalMaterialClassifier
from research_notes.public_hole_inventory import PUBLIC_BUDGET, TOL

ANGLE_TOL = 1e-7
MAX_FACES = 512


def _sub(a, b):
    return [x - y for x, y in zip(a, b)]


def _add(a, b, scale=1.0):
    return [x + scale * y for x, y in zip(a, b)]


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _unit(a):
    length = math.sqrt(_dot(a, a))
    if length <= 100 * TOL:
        raise ValueError('Length is too close to the qualification tolerance.')
    return [x / length for x in a], length


def _clean(a):
    return [0.0 if abs(x) < 1e-12 else round(float(x), 9) for x in a]


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _capsule(wire, edges):
    """Qualify an unsplit four-edge capsule in any plane, including tangency."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Line
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopoDS import TopoDS

    members = indexed_shapes(wire, TopAbs_EDGE)
    _require(members.Extent() == 4, 'Opening must have exactly four unsplit edges.')
    arcs, lines = [], []
    for i in range(1, 5):
        edge = TopoDS.Edge_s(members.FindKey(i))
        c = BRepAdaptor_Curve(edge)
        item = {'edge': edges.FindIndex(edge), 'curve': c,
                'ends': [list(c.Value(u).Coord()) for u in (c.FirstParameter(), c.LastParameter())]}
        if c.GetType() == GeomAbs_Circle:
            _require(abs(c.LastParameter() - c.FirstParameter() - math.pi) <= ANGLE_TOL,
                     'Arc is not a semicircle.')
            item.update(center=list(c.Circle().Location().Coord()), radius=c.Circle().Radius())
            arcs.append(item)
        elif c.GetType() == GeomAbs_Line:
            lines.append(item)
        else:
            raise ValueError('Opening contains a non-circular/non-linear edge.')
    _require(len(arcs) == len(lines) == 2, 'Opening needs two semicircles and two straight sides.')
    # Quantized ordering avoids tiny coordinate noise deciding an axis sign.
    arcs.sort(key=lambda a: _clean(a['center']))
    direction, spacing = _unit(_sub(arcs[1]['center'], arcs[0]['center']))
    radius = arcs[0]['radius']
    _require(radius > 100 * TOL and abs(radius - arcs[1]['radius']) <= TOL,
             'Semicircle radii differ or are too small.')
    center = _add(arcs[0]['center'], direction, spacing / 2)
    for arc, sign in zip(arcs, (-1, 1)):
        c = arc['curve']
        mid = list(c.Value((c.FirstParameter() + c.LastParameter()) / 2).Coord())
        _require(math.dist(mid, _add(arc['center'], direction, sign * radius)) <= TOL,
                 'Semicircles must face away from each other.')
    # Each side joins one endpoint on each arc; all four endpoints occur once.
    used = set()
    for line in lines:
        d, length = _unit(_sub(*line['ends']))
        _require(abs(length - spacing) <= TOL and abs(_dot(d, direction)) >= 1 - ANGLE_TOL,
                 'Straight sides are not parallel tangents of the required length.')
        matched_arcs = set()
        for p in line['ends']:
            matches = [(a, e) for a, arc in enumerate(arcs) for e, q in enumerate(arc['ends'])
                       if math.dist(p, q) <= TOL]
            _require(len(matches) == 1 and matches[0] not in used, 'Ambiguous or disconnected endpoints.')
            a, e = matches[0]
            used.add((a, e))
            matched_arcs.add(a)
            _require(abs(_dot(_sub(p, arcs[a]['center']), direction)) <= TOL,
                     'Straight side is not tangent to its arc.')
        _require(len(matched_arcs) == 2, 'Side does not connect the two ends.')
    return {'center': center, 'direction': direction, 'spacing': spacing, 'radius': radius,
            'arcs': arcs, 'lines': lines, 'edges': {a['edge'] for a in arcs + lines}}


def scan_straight_through_slots(shape):
    """Measure qualified slots in a valid millimetre B-Rep, preserving coordinates.

    Requires two planar inner capsule wires, four common untrimmed walls, one
    solid owner, matching support geometry and material/void sample checks.
    Face/edge IDs are local to this input only. Unsupported candidates abstain.
    """
    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepTools import BRepTools
    from OCP.GeomAbs import GeomAbs_Plane, GeomAbs_Line, GeomAbs_Cylinder
    from OCP.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX, TopAbs_WIRE, TopAbs_SOLID, TopAbs_IN, TopAbs_OUT
    from OCP.TopoDS import TopoDS

    _require(not shape.IsNull(), 'A valid solid B-Rep is required.')
    faces, edges, solids = (indexed_shapes(shape, t) for t in (TopAbs_FACE, TopAbs_EDGE, TopAbs_SOLID))
    _require(0 < faces.Extent() <= MAX_FACES, 'Slot qualification requires 1..512 faces.')
    _require(solids.Extent() > 0 and BRepCheck_Analyzer(shape).IsValid(), 'A valid solid B-Rep is required.')
    face_edges, edge_faces, owners = {}, {}, {i: set() for i in range(1, faces.Extent() + 1)}
    classifiers = {}
    for i in owners:
        face_edges[i] = {edges.FindIndex(e) for e in iter_shapes(faces.FindKey(i), TopAbs_EDGE)}
        for e in face_edges[i]:
            edge_faces.setdefault(e, set()).add(i)
    for s in range(1, solids.Extent() + 1):
        solid = TopoDS.Solid_s(solids.FindKey(s))
        classifiers[s] = LocalMaterialClassifier(solid, TOL)
        for f in iter_shapes(solid, TopAbs_FACE):
            owners[faces.FindIndex(f)].add(s)

    rims, withheld = [], []
    for i in owners:
        face = TopoDS.Face_s(faces.FindKey(i))
        surface = BRepAdaptor_Surface(face, True)
        if surface.GetType() != GeomAbs_Plane:
            continue
        outer = BRepTools.OuterWire_s(face)
        for wire in iter_shapes(face, TopAbs_WIRE):
            if wire.IsSame(outer):
                continue
            # Single-ring round holes are outside this API, not failed slots.
            members = indexed_shapes(wire, TopAbs_EDGE)
            if members.Extent() == 1:
                continue
            ids = sorted(edges.FindIndex(e) for e in iter_shapes(wire, TopAbs_EDGE))
            try:
                rim = _capsule(wire, edges)
                _require(len(owners[i]) == 1, 'Opening face must belong to exactly one solid.')
                # Curved exterior loops can be internal shoulders (stepped slots).
                _require(all(BRepAdaptor_Curve(TopoDS.Edge_s(e)).GetType() == GeomAbs_Line
                             for e in iter_shapes(outer, TopAbs_EDGE)),
                         'Curved outer opening boundary: stepped-slot ambiguity is withheld.')
                outer_neighbors = set().union(*(edge_faces[edges.FindIndex(e)] - {i}
                                                for e in iter_shapes(outer, TopAbs_EDGE)))
                normal = _face_geometry(face)[1]
                _require(outer_neighbors and not all(_dot(_sub(
                    surface_area_and_centroid(TopoDS.Face_s(faces.FindKey(f)))[1], rim['center']), normal) > TOL
                    for f in outer_neighbors),
                    'Opening is surrounded by outward-rising walls: recessed shoulder is withheld.')
                _require(all(len(edge_faces[e]) == 2 for e in rim['edges']), 'Non-manifold opening edges.')
                walls = set().union(*(edge_faces[e] - {i} for e in rim['edges']))
                _require(len(walls) == 4, 'Opening must adjoin four distinct walls.')
                rims.append({**rim, 'plane_face': i, 'walls': walls,
                             'normal': list(surface.Plane().Axis().Direction().Coord())})
            except (ValueError, RuntimeError) as exc:
                withheld.append({'opening_face': i, 'opening_edges': ids, 'reason': str(exc)})

    groups = {}
    for rim in rims:
        groups.setdefault(tuple(sorted(rim['walls'])), []).append(rim)
    rows = []
    for walls, ends in sorted(groups.items()):
        try:
            _require(len(ends) == 2 and ends[0]['plane_face'] != ends[1]['plane_face'],
                     'Two matching inner openings were not found; blind/stepped/trimmed slots abstain.')
            entry, exit = sorted(ends, key=lambda r: _clean(r['center']), reverse=True)
            axis, depth = _unit(_sub(exit['center'], entry['center']))
            radius, spacing = entry['radius'], entry['spacing']
            direction = entry['direction']
            _require(abs(_dot(axis, direction)) <= ANGLE_TOL, 'Long axis is not perpendicular to passage.')
            for end in ends:
                _require(abs(_dot(axis, end['normal'])) >= 1 - ANGLE_TOL,
                         'Opening plane is not perpendicular to passage.')
                _require(abs(end['radius'] - radius) <= TOL and abs(end['spacing'] - spacing) <= TOL
                         and abs(_dot(end['direction'], direction)) >= 1 - ANGLE_TOL,
                         'Opening size or direction differs.')
            for arc in entry['arcs']:
                predicted = _add(arc['center'], axis, depth)
                _require(any(math.dist(predicted, a['center']) <= TOL for a in exit['arcs']),
                         'The two openings are not a straight translation.')
            participating = set(walls) | {e['plane_face'] for e in ends}
            solid = next(iter(owners[entry['plane_face']]))
            _require(all(owners[f] == {solid} for f in participating), 'Walls/openings have different solid owners.')
            for f in participating:
                face = TopoDS.Face_s(faces.FindKey(f))
                _require(BRep_Tool.Tolerance_s(face) <= TOL and all(
                    BRep_Tool.Tolerance_s(TopoDS.Edge_s(e)) <= TOL for e in iter_shapes(face, TopAbs_EDGE)) and all(
                    BRep_Tool.Tolerance_s(TopoDS.Vertex_s(v)) <= TOL for v in iter_shapes(face, TopAbs_VERTEX)),
                    'Face/edge/vertex tolerance exceeds the qualification tolerance.')
            classifier = classifiers[solid]

            material = classifier.state

            offset = max(20 * TOL, min(radius, spacing, depth) * 1e-4)
            material_samples = 0
            for wall in walls:
                face = TopoDS.Face_s(faces.FindKey(wall))
                surface = BRepAdaptor_Surface(face, True)
                boundary = face_edges[wall]
                _require(len(boundary) == 4 and len(tuple(iter_shapes(face, TopAbs_WIRE))) == 1,
                         'A wall has splits, holes or extra trimming.')
                a = boundary & entry['edges']
                b = boundary & exit['edges']
                _require(len(a) == len(b) == 1, 'Wall must connect one edge at each opening.')
                lateral = boundary - a - b
                for edge_id in lateral:
                    c = BRepAdaptor_Curve(TopoDS.Edge_s(edges.FindKey(edge_id)))
                    d, length = _unit(_sub(c.Value(c.LastParameter()).Coord(), c.Value(c.FirstParameter()).Coord()))
                    _require(c.GetType() == GeomAbs_Line and abs(length - depth) <= TOL
                             and abs(_dot(d, axis)) >= 1 - ANGLE_TOL
                             and len(edge_faces[edge_id]) == 2 and edge_faces[edge_id] <= set(walls),
                             'Wall sides do not form an unbroken straight passage.')
                edge_id = next(iter(a))
                arc = next((a for a in entry['arcs'] if a['edge'] == edge_id), None)
                c = BRepAdaptor_Curve(TopoDS.Edge_s(edges.FindKey(edge_id)))
                if arc:
                    g = _face_geometry(face)
                    _require(surface.GetType() == GeomAbs_Cylinder and g[7] is not None and g[7] < -.99
                             and abs(g[2] - math.pi) <= ANGLE_TOL and abs(g[6] - radius) <= TOL
                             and abs(_dot(g[5], axis)) >= 1 - ANGLE_TOL,
                             'End wall is not an inward semicylinder of matching radius.')
                    delta = _sub(arc['center'], g[4])
                    _require(math.sqrt(sum(v*v for v in _add(delta, axis, -_dot(delta, axis)))) <= TOL,
                             'Cylinder support does not match its opening arc.')
                    expected_area = math.pi * radius * depth
                else:
                    _require(surface.GetType() == GeomAbs_Plane, 'Straight side must be planar.')
                    expected_area = spacing * depth
                area, _ = surface_area_and_centroid(face)
                _require(abs(area - expected_area) <= max(1e-7, expected_area * 1e-8),
                         'Wall area differs from the untrimmed capsule passage.')
                for u in (.2, .5, .8):
                    point = list(c.Value(c.FirstParameter() + u * (c.LastParameter() - c.FirstParameter())).Coord())
                    if arc:
                        outward = [v / radius for v in _sub(point, arc['center'])]
                    else:
                        delta = _sub(point, entry['center'])
                        outward = [v / radius for v in _add(delta, direction, -_dot(delta, direction))]
                    for t in (.2, .5, .8):
                        p = _add(point, axis, t * depth)
                        _require(material(_add(p, outward, -offset)) == TopAbs_OUT
                                 and material(_add(p, outward, offset)) == TopAbs_IN,
                                 'Wall material/void samples do not match a cavity.')
                        material_samples += 2
            void_samples = 0
            for along in (-spacing / 2, 0, spacing / 2):
                p = _add(entry['center'], direction, along)
                for distance in (-offset, .2 * depth, .5 * depth, .8 * depth, depth + offset):
                    _require(material(_add(p, axis, distance)) == TopAbs_OUT, 'Passage or opening is obstructed.')
                    void_samples += 1
            rows.append({'kind': 'straight_through_slot', 'width_mm': round(2 * radius, 9),
                         'length_mm': round(spacing + 2 * radius, 9), 'depth_mm': round(depth, 9),
                         'entry_center_mm': _clean(entry['center']), 'exit_center_mm': _clean(exit['center']),
                         'longitudinal_direction': _clean(direction), 'through_direction': _clean(axis),
                         'solid_index': solid, 'wall_faces': list(walls),
                         'opening_faces': [entry['plane_face'], exit['plane_face']],
                         'opening_edges': [sorted(entry['edges']), sorted(exit['edges'])],
                         'wall_material_samples': material_samples, 'passage_void_samples': void_samples,
                         'measurement_basis': 'two_inner_capsule_rims_and_four_untrimmed_walls'})
        except (ValueError, RuntimeError) as exc:
            withheld.append({'wall_faces': list(walls), 'opening_faces': sorted(e['plane_face'] for e in ends),
                             'reason': str(exc)})
    rows.sort(key=lambda r: (r['solid_index'], r['entry_center_mm'], r['width_mm'], r['length_mm']))
    for index, row in enumerate(rows, 1):
        row['id'] = f'S{index}'
    return {'schema_version': '1.10.0', 'status': 'partial' if rows else 'unresolved',
            'recognized_slot_count': len(rows), 'whole_opening_count': None, 'slots': rows,
            'withheld_candidates': withheld, 'scanned_faces': faces.Extent(), 'scanned_solids': solids.Extent(),
            'length_tolerance_mm': TOL, 'angular_tolerance': ANGLE_TOL,
            'reason': 'Locally verified slots only; no whole-part opening count or absence certificate.'}


def inspect_slots(path: str | Path):
    """Import a STEP locally with the existing bounded, mm-normalizing reader."""
    from research_notes.public_step import read_step_for_inspection

    path = Path(path)
    inspection = read_step_for_inspection(path, budget=PUBLIC_BUDGET)
    result = scan_straight_through_slots(inspection.imported.shape)
    result.update(source_name=path.name, source_sha256=inspection.imported.source_sha256)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('step', type=Path)
    parser.add_argument('--output', type=Path, help='Save the JSON result here (otherwise stdout).')
    args = parser.parse_args(argv)
    if args.output and (args.output.resolve() == args.step.resolve() or (
            args.output.exists() and args.step.exists() and args.output.samefile(args.step))):
        parser.error('The STEP input is read-only; choose a separate JSON output path.')
    try:
        result = inspect_slots(args.step)
    except (ValueError, RuntimeError, OSError) as exc:
        result = {'schema_version': '1.10.0', 'status': 'rejected', 'reason': str(exc),
                  'recognized_slot_count': 0, 'whole_opening_count': None, 'slots': []}
    payload = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding='utf-8')
    else:
        print(payload, end='')
    # Success means local measurement, not a complete inventory.
    return 0 if result['status'] == 'partial' else 2 if result['status'] == 'unresolved' else 1


if __name__ == '__main__':
    raise SystemExit(main())
