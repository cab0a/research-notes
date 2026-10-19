"""Bounded local OCCT/SMLib pilot; import and measurement are not hole recognition.

Run with the repository's geometry Python. Alternative interpreters are isolated
environments containing usd-brep==1.0.0 or smlibpy==0.3.5. No production imports,
dependencies, fixtures or recognition rules are replaced by this study.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from dataclasses import asdict
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT/'output/kernel-comparison-2026-10-19'
NATIVE_MODULE = {'occt': 'cadquery-ocp', 'smlibpy': 'smlibpy', 'usd-brep': 'usd-brep'}


def occt_metrics(shape):
    from research_notes.modeling_common import measure_shape
    from research_notes.brep_runtime import indexed_shapes
    from OCP.TopAbs import TopAbs_FACE
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder
    from OCP.TopoDS import TopoDS
    metrics = asdict(measure_shape(shape))
    faces = indexed_shapes(shape, TopAbs_FACE)
    cylinders = []
    for i in range(1, faces.Extent()+1):
        surface = BRepAdaptor_Surface(TopoDS.Face_s(faces.FindKey(i)))
        if surface.GetType() == GeomAbs_Cylinder:
            cylinder = surface.Cylinder()
            cylinders.append({'radius': cylinder.Radius(), 'origin': list(cylinder.Location().Coord()),
                              'axis': list(cylinder.Axis().Direction().Coord())})
    return {'volume': metrics['absolute_volume'], 'area': metrics['surface_area'],
            'bounds_min': metrics['bounds_min'], 'bounds_max': metrics['bounds_max'],
            'faces': metrics['face_count'], 'solids': metrics['solid_count'],
            'valid': metrics['analyzer_valid'], 'cylindrical_supports': cylinders,
            'tolerances': [metrics['maximum_vertex_tolerance'], metrics['maximum_edge_tolerance'], metrics['maximum_face_tolerance']]}


def occt_read(path):
    from OCP.STEPControl import STEPControl_Reader
    from OCP.IFSelect import IFSelect_RetDone
    reader = STEPControl_Reader()
    if reader.ReadFile(str(path)) != IFSelect_RetDone:
        raise ValueError('STEP reader did not return RetDone')
    reader.SetSystemLengthUnit(1.0)
    roots = reader.NbRootsForTransfer()
    if not roots or reader.TransferRoots() != roots or reader.OneShape().IsNull():
        raise ValueError('STEP transfer incomplete or empty')
    return reader.OneShape()


def smpy_metrics(bodies):
    if not bodies:
        raise ValueError('No B-Rep bodies returned')
    details = []
    for body in bodies:
        box = body.bbox()
        cylinders = [{'radius': f.radius, 'origin': list(f.axis.origin), 'axis': list(f.axis.direction)}
                     for f in body.faces().cylinders()]
        details.append({'type': type(body).__name__, 'volume': float(body.volume), 'area': float(body.area),
                        'faces': len(body.faces()), 'valid': bool(body.is_valid()),
                        'bounds_min': list(box.min), 'bounds_max': list(box.max),
                        'cylindrical_supports': cylinders})
    return {'volume': sum(d['volume'] for d in details), 'area': sum(d['area'] for d in details),
            'faces': sum(d['faces'] for d in details), 'solids': len(bodies),
            'valid': all(d['valid'] for d in details),
            'bounds_min': [min(d['bounds_min'][i] for d in details) for i in range(3)],
            'bounds_max': [max(d['bounds_max'][i] for d in details) for i in range(3)],
            'cylindrical_supports': [c for d in details for c in d['cylindrical_supports']],
            'body_details': details,
            'measurement_implementation': 'smlibpy custom integration, not upstream SmBrep default integration'}


def primitive(backend, name):
    # Independent creation through each API, with the same authored dimensions.
    if backend == 'occt':
        from research_notes.hole_robustness_controls import box, cylinder, cut, fuse
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeSphere
        box_at = box
        cyl = lambda x, y, z, r, h: cylinder(x, y, z, r, h)
        sphere = lambda: BRepPrimAPI_MakeSphere(2.).Shape()
    elif backend == 'usd-brep':
        import usd_brep as s
        box_at = lambda x, y, z, a, b, c: s.create_box((x, y, z), a, b, c)
        cyl = lambda x, y, z, r, h: s.create_cylinder((x, y, z), r, h)
        cut, fuse = s.boolean_difference, s.boolean_union
        sphere = lambda: s.create_sphere((0., 0., 0.), 2.)
    else:
        import smlibpy as s
        box_at = lambda x, y, z, a, b, c: s.Box(a, b, c).translate((x+a/2, y+b/2, z+c/2))
        cyl = lambda x, y, z, r, h: s.Cylinder(r, h).translate((x, y, z+h/2))
        cut, fuse = lambda a, b: a-b, lambda a, b: a+b
        sphere = lambda: s.Sphere(2.)
    if name == 'sphere':
        return sphere()
    if name == 'cylinder':
        return cyl(0., 0., 0., 2., 5.)
    shape = box_at(0., 0., 0., 20., 30., 5.)
    if name in {'round_plate', 'mixed_plate'}:
        shape = cut(shape, cyl(5., 6., -1., 2., 7.))
    if name in {'slot_plate', 'mixed_plate'}:
        tool = fuse(cyl(10., 20., -1., 2., 7.), cyl(16., 20., -1., 2., 7.))
        tool = fuse(tool, box_at(10., 18., -1., 6., 4., 7.))
        shape = cut(shape, tool)
    return shape


def truth(name):
    if name == 'sphere':
        return {'volume': 32*math.pi/3, 'area': 16*math.pi}
    if name == 'cylinder':
        return {'volume': 20*math.pi, 'area': 28*math.pi}
    area_removed, perimeter = 0., 0.
    if name in {'round_plate', 'mixed_plate'}:
        area_removed += 4*math.pi
        perimeter += 4*math.pi
    if name in {'slot_plate', 'mixed_plate'}:
        area_removed += 24+4*math.pi
        perimeter += 12+4*math.pi
    return {'volume': 3000-5*area_removed, 'area': 1700-2*area_removed+5*perimeter}


def accurate_occt(shape, metrics):
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    from OCP.gp import gp_Pnt
    origin = [(a+b)/2 for a, b in zip(metrics['bounds_min'], metrics['bounds_max'])]
    rows = []
    for epsilon in (1e-7, 1e-9):
        for method in ('adaptive_gauss', 'gauss_kronrod_spans'):
            volume, area = GProp_GProps(gp_Pnt(*origin)), GProp_GProps(gp_Pnt(*origin))
            error = (BRepGProp.VolumeProperties_s(shape, volume, epsilon, True, False) if method == 'adaptive_gauss' else
                     BRepGProp.VolumePropertiesGK_s(shape, volume, epsilon, True, True, False, False, False))
            area_error = BRepGProp.SurfaceProperties_s(shape, area, epsilon, False)
            rows.append({'method': method, 'epsilon': epsilon, 'volume': volume.Mass(), 'area': area.Mass(),
                         'reported_volume_error': error, 'reported_area_error': area_error, 'integration_origin': origin})
    return rows


def metadata_probe(task):
    path, destination = ROOT/task['source_path'], ROOT/task['export_path']
    if task['backend'] == 'occt':
        from research_notes.step_round_trip_preservation import _read_document, _write_document, _document_observation
        document = _read_document(path)
        first, _ = _document_observation('unicode', 'source_import', path.name, path.read_bytes(), document)
        data = _write_document(document, destination)
        second, _ = _document_observation('unicode', 'reexport_import', destination.name, data, _read_document(destination))
        return {'input': asdict(first), 'output': asdict(second), 'export_path': task['export_path']}
    import smlibpy as s
    def observation(model):
        return {'names': [b.name for b in model.bodies], 'colors': [b.color for b in model.bodies],
                'metrics': smpy_metrics(model.bodies)}
    model = s.read_step(path, heal=False)
    first = observation(model)
    s.export_step(model.bodies, destination)
    return {'input': first, 'output': observation(s.read_step(destination, heal=False)), 'export_path': task['export_path']}


def worker(task):
    # Limits apply before any native import. SIGSEGV/abort/timeouts stay in this child.
    import resource
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_AS, (4*1024**3, 4*1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (30, 31))
    backend = task['backend']
    result = {'backend': backend, 'version': importlib.metadata.version(NATIVE_MODULE[backend]),
              'mode': task['mode'], 'status': 'error'}
    started = time.perf_counter()
    try:
        if task['mode'] == 'metadata':
            result.update(metadata_probe(task))
        elif task['mode'] == 'primitive':
            shape = primitive(backend, task['id'])
            if backend == 'occt':
                result['measurements'] = [{'accuracy': 'OCCT default integration', **occt_metrics(shape)}]
            elif backend == 'smlibpy':
                result['measurements'] = []
                for accuracy in (1e-7, 1e-9):
                    props = shape.mass_properties(accuracy=accuracy)
                    result['measurements'].append({'accuracy': accuracy, 'volume': props.volume, 'area': props.area,
                                                   'valid': shape.is_valid()})
            else:
                result['measurements'] = [{'accuracy': accuracy, 'volume': shape.volume(relative_accuracy=accuracy),
                                           'area': shape.area(relative_accuracy=accuracy), 'valid': shape.is_manifold_solid()}
                                          for accuracy in (1e-3, 1e-9)]
            result['truth'] = truth(task['id'])
            for row in result['measurements']:
                row['relative_errors'] = {k: abs(row[k]-result['truth'][k])/abs(result['truth'][k]) for k in ('volume', 'area')}
        else:
            path = ROOT/task['source_path']
            if backend == 'occt':
                shape = occt_read(path)
                result['import_completed'] = True
                result['metrics'] = occt_metrics(shape)
                if task['mode'] == 'accuracy':
                    result['integrations'] = accurate_occt(shape, result['metrics'])
                if task.get('export_path'):
                    from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
                    from OCP.IFSelect import IFSelect_RetDone
                    writer = STEPControl_Writer()
                    if writer.Transfer(shape, STEPControl_AsIs) != IFSelect_RetDone or writer.Write(str(ROOT/task['export_path'])) != IFSelect_RetDone:
                        raise ValueError('STEP export failed')
                    result['export_path'] = task['export_path']
            else:
                import smlibpy as s
                model = s.read_step(path, heal=task['heal'])
                result['import_completed'] = True
                result['metrics'] = smpy_metrics(model.bodies)
                if task.get('export_path'):
                    s.export_step(model.bodies, ROOT/task['export_path'])
                    result['export_path'] = task['export_path']
        result['status'] = 'ok'
    except Exception as error:
        result.update(error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc()[-3500:])
    result['seconds_inside_worker'] = time.perf_counter()-started
    Path(task['result_path']).write_text(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2)+'\n')


def execute(task, interpreters, work):
    key = task['key']
    task = {**task, 'result_path': str(work/(key+'.result.json'))}
    job = work/(key+'.task.json')
    job.write_text(json.dumps(task))
    command = [str(interpreters[task['backend']]), str(Path(__file__).resolve()), '--worker', str(job)]
    environment = {**os.environ, 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1'}
    started = time.perf_counter()
    payload = Path(task['result_path'])
    payload.unlink(missing_ok=True)
    process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               env=environment, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=40)
        failure = None
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
        failure = 'timeout'
    result = json.loads(payload.read_text()) if payload.exists() and not failure and process.returncode == 0 else {'status': failure or 'process_failed'}
    return {**{k: v for k, v in task.items() if k != 'result_path'}, 'result': result,
            'exit_code': process.returncode, 'process_seconds': time.perf_counter()-started,
            'stdout_tail': stdout.decode(errors='replace')[-1500:], 'stderr_tail': stderr.decode(errors='replace')[-2500:]}


def source_cases():
    from research_notes.hole_review_benchmark import fixed_cases
    for case in fixed_cases():
        if case['source_path']:
            yield {k: case[k] for k in ('id', 'group', 'source_path')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', type=Path)
    parser.add_argument('--output-dir', type=Path, default=ROOT/'results/cad-kernel-choice')
    parser.add_argument('--occt-python', type=Path, default=Path(sys.executable))
    parser.add_argument('--smlibpy-python', type=Path, default=WORK/'smlibpy-env/bin/python')
    parser.add_argument('--usd-brep-python', type=Path, default=WORK/'official-env/bin/python')
    parser.add_argument('--group', choices=('primitives', 'intake', 'roundtrip', 'accuracy', 'metadata'), default='primitives')
    args = parser.parse_args()
    if args.worker:
        worker(json.loads(args.worker.read_text()))
        return
    args.output_dir.mkdir(parents=True, exist_ok=True)
    work = WORK/args.group
    work.mkdir(parents=True, exist_ok=True)
    interpreters = {'occt': args.occt_python, 'smlibpy': args.smlibpy_python, 'usd-brep': args.usd_brep_python}
    tasks = []
    if args.group == 'primitives':
        tasks.extend({'key': f'primitive-{b}-{n}', 'id': n, 'backend': b, 'mode': 'primitive'}
                     for b in interpreters for n in ('box', 'cylinder', 'sphere', 'round_plate', 'slot_plate', 'mixed_plate'))
    if args.group == 'intake':
        for case in source_cases():
            for backend, heal in (('occt', False), ('smlibpy', False), ('smlibpy', True)):
                tasks.append({**case, 'key': f"intake-{case['group']}-{case['id']}-{backend}-heal{int(heal)}",
                              'backend': backend, 'heal': heal, 'mode': 'intake',
                              'source_sha256': hashlib.sha256((ROOT/case['source_path']).read_bytes()).hexdigest()})
    if args.group == 'roundtrip':
        selected = {'build123d_bracket', 'build123d_screw', 'ublox_sam_ap203', 'circle_spline', 'slot_spline', 'single'}
        for case in source_cases():
            if case['id'] not in selected:
                continue
            for backend in ('occt', 'smlibpy'):
                destination = work/(case['id']+'-'+backend+'.step')
                tasks.append({**case, 'key': 'export-'+case['id']+'-'+backend, 'mode': 'intake',
                              'backend': backend, 'heal': False, 'export_path': str(destination.relative_to(ROOT)),
                              'source_sha256': hashlib.sha256((ROOT/case['source_path']).read_bytes()).hexdigest()})
    if args.group == 'accuracy':
        selected = {'circle_spline', 'slot_spline', 'build123d_screw', 'build123d_bracket', 'ublox_sam_ap203'}
        for case in source_cases():
            if case['id'] in selected:
                tasks.append({**case, 'key': 'accuracy-'+case['id']+'-source', 'backend': 'occt', 'mode': 'accuracy'})
                for backend in ('occt', 'smlibpy'):
                    path = WORK/'roundtrip'/(case['id']+'-'+backend+'.step')
                    tasks.append({**case, 'key': 'accuracy-'+case['id']+'-from-'+backend,
                                  'backend': 'occt', 'mode': 'accuracy', 'writer_backend': backend,
                                  'source_path': str(path.relative_to(ROOT))})
    if args.group == 'metadata':
        from research_notes.step_round_trip_preservation import PreservationControl, _build_document, _write_document
        from research_notes.step_round_trip_preservation import _document_tools
        from research_notes.hole_robustness_controls import box
        from OCP.TCollection import TCollection_ExtendedString
        from OCP.TDataStd import TDataStd_Name
        from OCP.TDF import TDF_LabelSequence
        source = args.output_dir/'unicode-input.step'
        control = PreservationControl('unicode', 'named red box', ('穴板_日本語',), ((.85, .15, .1),))
        document = _build_document(control, box(0., 0., 0., 20., 30., 5.))
        shapes, _ = _document_tools(document)
        labels = TDF_LabelSequence()
        shapes.GetFreeShapes(labels)
        # The C-string constructor needs isMultiByte=True for Python's UTF-8.
        TDataStd_Name.Set_s(labels.Value(1), TCollection_ExtendedString(control.expected_names[0], True))
        _write_document(document, source)
        tasks.extend({'key': 'metadata-'+backend, 'id': 'unicode_box', 'backend': backend, 'mode': 'metadata',
                      'source_path': str(source.relative_to(ROOT)), 'expected_name': '穴板_日本語',
                      'export_path': str((args.output_dir/('unicode-'+backend+'.step')).relative_to(ROOT)),
                      'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest()} for backend in ('occt', 'smlibpy'))
    for task in tasks:
        if task.get('source_path') and 'source_sha256' not in task:
            task['source_sha256'] = hashlib.sha256((ROOT/task['source_path']).read_bytes()).hexdigest()
    records = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        for index, row in enumerate(executor.map(lambda t: execute(t, interpreters, work), tasks), 1):
            records.append(row)
            if index % 20 == 0:
                print(f'{index}/{len(tasks)} observations recorded', flush=True)
    if args.group == 'roundtrip':
        reread = []
        for row in records:
            if row['result']['status'] != 'ok':
                continue
            source = ROOT/row['export_path']
            for backend in ('occt', 'smlibpy'):
                reread.append({'key': 'reread-'+row['id']+'-from-'+row['backend']+'-by-'+backend,
                               'id': row['id'], 'mode': 'intake', 'group': 'roundtrip_reread',
                               'writer_backend': row['backend'], 'backend': backend, 'heal': False,
                               'source_path': row['export_path'], 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest()})
        with ThreadPoolExecutor(max_workers=2) as executor:
            records.extend(executor.map(lambda t: execute(t, interpreters, work), reread))
    report = {'date': '2026-10-19', 'group': args.group, 'observations': len(records),
              'python': platform.python_version(), 'platform': platform.platform(),
              'baseline_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
              'probe_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'process_limits': {'address_space_bytes': 4*1024**3, 'cpu_seconds': 30, 'wall_seconds': 40, 'max_workers': 2},
              'limitations': ['Linux/WSL pilot using resource limits; not a Windows-native execution test.',
                              'Pilot observations; one recorded run per task, not general accuracy or a speed benchmark.',
                              'No SMLib hole-recognition port; cylindrical supports are not hole counts.',
                              'Intake paths use native readers and do not include the production Part 21/units/external-reference admission contract.',
                              'OCCT validity and SMLib manifold/positive-volume checks differ.',
                              'smlibpy includes kernel patches and independent integration; it is not the unmodified NVIDIA kernel.'],
              'records': records}
    target = args.output_dir/(args.group+'.json')
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'observations': len(records), 'states': {state: sum(r['result']['status'] == state for r in records)
                       for state in sorted({r['result']['status'] for r in records})}, 'output': str(target)}, indent=2))


if __name__ == '__main__':
    main()
