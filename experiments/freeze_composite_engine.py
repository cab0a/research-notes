"""Freeze the compound interpreter before exporting any new held-out part."""
from pathlib import Path
import datetime,hashlib,json
from research_notes.drawing_to_cad import json_bytes
from experiments.freeze_drawing_engine import check as previous_check
ROOT=Path(__file__).resolve().parents[1];FIX=ROOT/'fixtures/drawing-composites'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def check():
    previous_check();record=json.loads((FIX/'engine-freeze.json').read_text())
    for p,h in record['sha256'].items():assert sha(ROOT/p)==h,p
    return record
def freeze():
    previous_check();assert not (FIX/'holdout').exists()
    paths=[ROOT/'src/research_notes/drawing_composites.py',ROOT/'src/research_notes/drawing_composite_evidence.py',
        ROOT/'experiments/export_drawing_composites.FCMacro',ROOT/'experiments/prepare_drawing_composites.py',
        FIX/'protocol.json',FIX/'development-specs.json',FIX/'holdout-specs.json',FIX/'development/manifest.json',FIX/'controls/manifest.json']
    paths+=list((FIX/'controls').glob('*/review.json'))
    record=dict(frozen_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        order='Development/negative/review tests complete before held-out CAD drawings generated; no post-holdout inference retuning.',
        inherited_freeze='fixtures/drawing-generalization/engine-freeze.json',sha256={str(p.relative_to(ROOT)):sha(p) for p in paths})
    with (FIX/'engine-freeze.json').open('xb') as stream:stream.write(json_bytes(record))
    print(record['frozen_at_utc'])
if __name__=='__main__':freeze()
