"""Record artifact/source hashes without executing reconstruction or test suites."""
import argparse,datetime,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];FIX=ROOT/'fixtures/drawing-machining'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def archive(directory):
    sources=[ROOT/'src/research_notes'/name for name in ('drawing_machining.py','drawing_machining_annotations.py','drawing_machining_evidence.py','drawing_machining_report.py')]
    sources += [ROOT/'experiments'/name for name in ('prepare_drawing_machining.py','export_drawing_machining.FCMacro','freeze_drawing_machining.py','run_drawing_machining.py','archive_drawing_machining.py')]
    record=dict(recorded_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        activity='artifact inventory, not test execution',test_suite_executed=False,
        source_sha256={str(p.relative_to(ROOT)):sha(p) for p in sources},
        fixture_sha256={str(p.relative_to(FIX)):sha(p) for p in FIX.rglob('*') if p.is_file()},
        artifact_sha256={str(p.relative_to(directory)):sha(p) for p in directory.rglob('*') if p.is_file() and p.name!='inventory.json'})
    (directory/'inventory.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({k:len(v) for k,v in record.items() if k.endswith('_sha256')}))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('directory',type=Path);archive(ap.parse_args().directory)
