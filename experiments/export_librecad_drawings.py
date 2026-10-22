"""Run the actual second CAD exporter; no inferred feature data is supplied."""
import hashlib,json,os,subprocess,shutil,xml.etree.ElementTree as ET
from pathlib import Path
from research_notes.drawing_to_cad import json_bytes
from research_notes.drawing_families import interpret
ROOT=Path(__file__).resolve().parents[1];FIX=ROOT/'fixtures/drawing-generalization'
def run():
    out=FIX/'portability';out.mkdir(exist_ok=False);cases=[];logs=[]
    binary=ROOT/'output/librecad-runtime/squashfs-root/AppRun'
    for name in ('unseen_small','l_bracket','stepped_shaft','pocket'):
        for size in ('1024x768','1600x1200'):
            key=name+'_'+size;folder=out/key;folder.mkdir()
            source=ROOT/'fixtures/drawing-families/inputs'/name
            shutil.copyfile(source/'drawing.dxf',folder/'source.dxf')
            command=[str(binary),'dxf2svg','-r',size,'-o','drawing.svg',str(folder/'source.dxf')]
            result=subprocess.run(command,env={**os.environ,'QT_QPA_PLATFORM':'xcb'},cwd=ROOT,capture_output=True,timeout=60)
            (folder/'export.log').write_bytes(result.stdout+result.stderr)
            assert result.returncode==0 and (folder/'drawing.svg').is_file(),result.stderr
            ctx=json.loads((source/'context-svg.json').read_text())
            (folder/'context.json').write_bytes(json_bytes(ctx))
            root=ET.fromstring((folder/'drawing.svg').read_bytes());tags={}
            for e in root.iter():tags[e.tag.split('}')[-1]]=tags.get(e.tag.split('}')[-1],0)+1
            baseline=interpret((folder/'drawing.svg').read_bytes(),ctx,'svg')
            c=dict(id='portability_'+key,part=name,cohort='portability',family=ctx['family_assumption'],format='svg',
                   drawing=str((folder/'drawing.svg').relative_to(FIX)),context=str((folder/'context.json').relative_to(FIX)),
                   expected='measure_portability',baseline={k:baseline.get(k) for k in ('status','reason_code','detail')},
                   inventory=dict(tags=tags,root=root.attrib),resolution=size,
                   provenance='Unmodified LibreCAD SVG re-export of existing FreeCAD DXF; no native 3D-CAD drafting claim')
            for k in ('drawing','context'):c[k+'_sha256']=hashlib.sha256((FIX/c[k]).read_bytes()).hexdigest()
            cases.append(c);logs.append(dict(id=c['id'],command=command,returncode=result.returncode))
    artifact=ROOT/'output/librecad-runtime/LibreCAD.AppImage'
    (out/'manifest.json').write_bytes(json_bytes(dict(cases=cases,commands=logs,version='2.2.1.5',qt='5.15.2',
        runtime_url='https://github.com/LibreCAD/LibreCAD/releases/download/v2.2.1.5/LibreCAD-v2.2.1.5-x86_64.AppImage',
        runtime_sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),
        environment_note='Offscreen plugin absent in bundle (startup failed); xcb with existing WSLg display succeeded. CLI export, no UI automation.',
        runtime_distribution='Downloaded official AppImage, extracted only under ignored output; not redistributed')))

if __name__=='__main__':run()
