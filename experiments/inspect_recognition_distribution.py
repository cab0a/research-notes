"""Inspect a pinned Quiddity wheel's shipped API contract without importing it."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import zipfile


def inspect(path):
    with zipfile.ZipFile(path) as wheel:
        contract_data = wheel.read('quiddity/capabilities.json')
        contract = json.loads(contract_data)
        metadata_name = next(n for n in wheel.namelist() if n.endswith('.dist-info/METADATA'))
        metadata = wheel.read(metadata_name).decode()
        fields = {}
        for line in metadata.split('\n\n', 1)[0].splitlines():
            if ': ' in line:
                key, value = line.split(': ', 1)
                fields.setdefault(key, []).append(value)
        module = ast.parse(wheel.read('quiddity/__init__.py'))
        exports = {alias.asname or alias.name for node in module.body if isinstance(node, ast.ImportFrom)
                   for alias in node.names}
        families = []
        for family in contract['families']:
            entry_points = [r['entry_point'] for r in family['recognisers']]
            for entry in entry_points:
                assert entry.startswith('quiddity.') and entry.split('.')[1] in exports, entry
            families.append({'id': family['id'], 'status': family['status'],
                             'entry_points': entry_points, 'introduced_in': family['introduced_in'],
                             'records': [{'name': r['name'], 'role': r['role'],
                                          'field_names': sorted(r.get('fields', {}))}
                                         for r in family['records']]})
    return {'wheel': path.name, 'wheel_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'metadata_version': fields['Version'][0], 'license_expression': fields.get('License-Expression'),
            'requires_python': fields.get('Requires-Python'), 'requires_dist': fields.get('Requires-Dist'),
            'contract_member': 'quiddity/capabilities.json',
            'contract_sha256': hashlib.sha256(contract_data).hexdigest(),
            'format_version': contract['format_version'], 'family_count': len(families),
            'families': families, 'package_executed': False,
            'claim': 'Shipped interface/manifest inspection, not measured recognition accuracy or recall.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wheel', type=Path)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    actual = hashlib.sha256(args.wheel.read_bytes()).hexdigest()
    if actual != args.sha256:
        raise ValueError('Wheel digest does not match the pinned source record')
    result = inspect(args.wheel)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, allow_nan=False, indent=2) + '\n')
    print(json.dumps({'version': result['metadata_version'], 'families': result['family_count'],
                      'package_executed': False, 'output': str(args.output)}))


if __name__ == '__main__':
    main()
