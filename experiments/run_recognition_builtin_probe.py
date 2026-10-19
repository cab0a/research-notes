"""Observe existing smlibpy recognition/analysis APIs; do not implement a recognizer.

Linux/WSL only. Run with the geometry Python; workers use the isolated smlibpy
0.3.5 environment. Source STEP admission and hole certification are not tested.
"""
from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'output/recognition-catalog-2026-10-19/runtime'
PYTHON = ROOT / 'output/kernel-comparison-2026-10-19/smlibpy-env/bin/python'
SOURCES = {
    'bracket': 'fixtures/public-step-corpus/sources/build123d_bracket.step',
    'spline_bore': 'fixtures/hole-robustness/sources/circle_spline.step',
}


def shape_for(case):
    import smlibpy as s
    if case in SOURCES:
        bodies = s.read_step(ROOT / SOURCES[case], heal=False).bodies
        if len(bodies) != 1:
            raise ValueError(f'Expected one body, got {len(bodies)}')
        return bodies[0]
    if case == 'filleted_box':
        part = s.Box(20, 30, 5)
        return part.fillet(part.edges().parallel_to(s.Z), 2)
    if case == 'folded_sheet':
        part = s.Box(100, 40, 2, align=(s.Align.CENTER, s.Align.CENTER, s.Align.MIN))
        return s.fold(part, s.Axis((20, 0, 2), (0, 1, 0)), 90, radius=2)
    # Independent primitives and dimension formulas already used by the local pilot.
    from run_cad_kernel_probe import primitive
    return primitive('smlibpy', case)


def worker(task):
    import resource
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (20, 21))
    result = {'status': 'error', 'package_version': importlib.metadata.version('smlibpy')}
    start = time.perf_counter()
    try:
        part = shape_for(task['case'])
        faces = list(part.faces())
        result['input_face_count'] = len(faces)
        result['input_surface_types'] = dict(Counter(f.geom_type for f in faces))
        if task['operation'] == 'selectors':
            result['cylindrical_face_count'] = len(part.faces().cylinders())
            result['circular_edge_count'] = len(part.edges().circles())
            result['edge_convexity'] = dict(Counter(e.convexity for e in part.edges()))
            result['note'] = 'Surface/edge counts are not recognized hole or slot counts.'
        elif task['operation'] == 'fillets':
            selected = list(part.faces().fillets())
            result['selected_face_count'] = len(selected)
            result['selected_surface_types'] = dict(Counter(f.geom_type for f in selected))
            result['selected_original_face_indices'] = [faces.index(f) + 1 for f in selected]
        elif task['operation'] == 'bends':
            bends = part.bends()
            result['bend_count'] = len(bends)
            result['bends'] = [
                {'angle_deg': b.angle, 'inside_radius_mm': b.radius, 'thickness_mm': b.thickness,
                 'length_mm': b.length, 'axis_origin': list(b.axis.origin),
                 'axis_direction': list(b.axis.direction), 'k_factor_input': b.k_factor}
                for b in bends
            ]
        elif task['operation'] == 'draft':
            analysis = part.draft_analysis((0, 0, 1), min_angle=1)
            result['pull_direction'] = [0, 0, 1]
            result['face_kinds'] = dict(Counter(f.kind for f in analysis.faces))
            result['angles'] = [{'kind': f.kind, 'min_deg': f.min_angle, 'max_deg': f.max_angle}
                                for f in analysis.faces]
        elif task['operation'] == 'parting_line':
            result['wire_count'] = len(part.parting_line((0, 0, 1)))
            result['pull_direction'] = [0, 0, 1]
        result['status'] = 'ok'
    except Exception as error:
        result.update(error_type=type(error).__name__, error=str(error),
                      traceback=traceback.format_exc()[-1800:])
    result['worker_seconds'] = time.perf_counter() - start
    Path(task['result_path']).write_text(json.dumps(result, allow_nan=False, indent=2) + '\n')


def execute(task, python):
    key = task['case'] + '-' + task['operation']
    destination = WORK / (key + '.result.json')
    destination.unlink(missing_ok=True)
    payload = {**task, 'result_path': str(destination)}
    path = WORK / (key + '.task.json')
    path.write_text(json.dumps(payload))
    start = time.perf_counter()
    child = subprocess.Popen([str(python), str(Path(__file__).resolve()), '--worker', str(path)],
                             cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             start_new_session=True,
                             env={**os.environ, 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1'})
    state = 'process_failed'
    try:
        stdout, stderr = child.communicate(timeout=30)
    except subprocess.TimeoutExpired:
        os.killpg(child.pid, signal.SIGKILL)
        stdout, stderr = child.communicate()
        state = 'timeout'
    result = (json.loads(destination.read_text()) if child.returncode == 0 and destination.exists()
              else {'status': state})
    return {**task, 'result': result, 'exit_code': child.returncode,
            'wall_seconds': time.perf_counter() - start,
            'stdout_tail': stdout.decode(errors='replace')[-800:],
            'stderr_tail': stderr.decode(errors='replace')[-800:]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', type=Path)
    parser.add_argument('--smlibpy-python', type=Path, default=PYTHON)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'results/recognition-catalog')
    args = parser.parse_args()
    if args.worker:
        worker(json.loads(args.worker.read_text()))
        return
    WORK.mkdir(parents=True, exist_ok=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    cases = ('box', 'round_plate', 'slot_plate', 'filleted_box', 'folded_sheet', 'bracket', 'spline_bore')
    tasks = [{'case': case, 'operation': op} for case in cases
             for op in ('selectors', 'fillets', 'bends', 'draft')]
    tasks += [{'case': case, 'operation': 'parting_line'} for case in ('box', 'round_plate')]
    for task in tasks:
        if task['case'] in SOURCES:
            task['source_path'] = SOURCES[task['case']]
            task['source_sha256'] = hashlib.sha256((ROOT / task['source_path']).read_bytes()).hexdigest()
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(lambda t: execute(t, args.smlibpy_python), tasks))
    report = {'date': '2026-10-19', 'python': platform.python_version(), 'platform': platform.platform(),
              'baseline_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
              'probe_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'primitive_helper_sha256': hashlib.sha256((ROOT / 'experiments/run_cad_kernel_probe.py').read_bytes()).hexdigest(),
              'process_limits': {'address_space_bytes': 4*1024**3, 'cpu_seconds_soft': 20,
                                 'cpu_seconds_hard': 21, 'wall_seconds': 30, 'max_workers': 2},
              'observations': len(rows), 'states': dict(Counter(r['result']['status'] for r in rows)),
              'limits': ['One recorded observation per task; not a precision or performance benchmark.',
                         'Only existing smlibpy APIs called; no custom recognizer or production change.',
                         'Selections, draft classes and bends do not certify full manufacturing-feature recognition.',
                         'K-factor is a supplied default, not a recovered material/process property.',
                         'Quiddity and C++ analytic promotion were not executed in this probe.'],
              'records': rows}
    (args.output_dir / 'builtin-probe.json').write_text(json.dumps(report, allow_nan=False, indent=2) + '\n')
    print(json.dumps({'observations': len(rows), 'states': report['states'],
                      'output': str(args.output_dir / 'builtin-probe.json')}, indent=2))


if __name__ == '__main__':
    main()
