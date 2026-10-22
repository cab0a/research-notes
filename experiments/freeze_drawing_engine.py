"""Freeze inference sources before generating the held-out drawings; never overwrite."""
import hashlib,json,datetime
from pathlib import Path
from research_notes.drawing_to_cad import json_bytes
ROOT=Path(__file__).resolve().parents[1];FIX=ROOT/'fixtures/drawing-generalization'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def check():
    record=json.loads((FIX/'engine-freeze.json').read_text())
    for name,digest in record['sha256'].items():assert sha(ROOT/name)==digest,name
    return record
def freeze():
    assert not (FIX/'holdout').exists(),'holdout must not have been generated'
    paths=[p for p in (ROOT/'src/research_notes').rglob('*.py') if not p.name.endswith('report.py')]
    paths += [FIX/'protocol.json',FIX/'development-specs.json',FIX/'holdout-specs.json',
        ROOT/'experiments/export_drawing_generalization.FCMacro',ROOT/'experiments/export_drawing_families.FCMacro']
    record=dict(frozen_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        order='Development tests passed; frozen before held-out CAD drawings were generated or interpreted.',
        no_retuning=True,sha256={str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)})
    with (FIX/'engine-freeze.json').open('xb') as stream:stream.write(json_bytes(record))
    print(record['frozen_at_utc'],len(paths),'files frozen')
if __name__=='__main__':freeze()
