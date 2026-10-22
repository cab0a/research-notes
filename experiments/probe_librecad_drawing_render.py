"""Observe an alternate LibreCAD rendering route; no OCR or CAD recovery claim."""
import argparse,datetime,hashlib,json,os,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(runtime,output):
    output.mkdir(parents=True,exist_ok=False)
    src=ROOT/'fixtures/drawing-composites/development/inputs/pocket_hole/drawing.dxf'
    shutil.copyfile(src,output/'source.dxf');records=[]
    for fmt in ('png','svg'):
        cmd=[str(runtime.resolve()),'dxf2'+fmt,'-r','1600x1200','-o','drawing.'+fmt,str((output/'source.dxf').resolve())]
        p=subprocess.run(cmd,env={**os.environ,'QT_QPA_PLATFORM':'xcb'},capture_output=True,timeout=60)
        (output/(fmt+'-export.log')).write_bytes(p.stdout+p.stderr)
        records.append(dict(format=fmt,command=cmd,returncode=p.returncode,output_sha256=sha(output/('drawing.'+fmt))))
    (output/'manifest.json').write_text(json.dumps(dict(completed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        source=str(src.relative_to(ROOT)),source_sha256=sha(src),runtime='LibreCAD 2.2.1.5 / Qt 5.15.2',
        environment={'QT_QPA_PLATFORM':'xcb'},records=records,
        scope='2D re-export of the same FreeCAD DXF, not independent 3D CAD. PNG visual inspection only; no OCR or reconstruction.'),indent=2)+'\n')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--runtime',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args();run(a.runtime,a.output_dir)
