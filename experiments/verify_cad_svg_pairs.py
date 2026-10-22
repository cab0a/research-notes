"""Audit this study's fixed artifacts and record the actual pytest run.

No CAD is regenerated. Run after the experiment, tests and manual HTML check.
"""
from pathlib import Path
import argparse
import hashlib
from html.parser import HTMLParser
import json
import re
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

from research_notes.drawing_to_cad import json_bytes

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Links(HTMLParser):
    def __init__(self):
        super().__init__();self.links=[];self.external_assets=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if "href" in a:self.links.append(a["href"])
        remote_source=a.get("src","").startswith(("http:","https:"))
        remote_link=tag=="link" and a.get("href","").startswith(("http:","https:"))
        if tag in ("script","img","link") and (remote_source or remote_link):
            self.external_assets.append(a)


def verify(directory,junit):
    report=json.loads((directory/"results.json").read_text())
    assert report["passed"]
    manifest=ROOT/"fixtures/cad-svg-dxf/manifest.json"
    cases=json.loads(manifest.read_text())["cases"]
    checks=0
    for case in cases:
        for key in ("drawing","svg","context"):
            assert sha(manifest.parent/case[key])==case[key+"_sha256"]
            checks+=1
        artifact=directory/case["id"]
        assert sha(artifact/("input."+case["format"]))==case["drawing_sha256"]
        assert sha(artifact/"input.svg")==case["svg_sha256"]
        inference=json.loads((artifact/"inference.json").read_text())
        assert inference["source_sha256"]==case["drawing_sha256"]
        if case["expected_status"]=="withheld":
            assert not any((artifact/p).exists() for p in ("candidate.py","candidate.step","edited.step","model.json"))
    for path,digest in report["hashes"].items():
        assert sha(ROOT/path)==digest,path
    page=Links();page.feed((directory/"report.html").read_text())
    local_links=0
    for href in page.links:
        target=urlsplit(href)
        if target.scheme or not target.path:continue
        assert (directory/unquote(target.path)).exists(),href
        local_links+=1
    assert not page.external_assets
    docs=[ROOT/"README.md",ROOT/"docs/studies.md",ROOT/"docs/reproducibility.md",
          ROOT/"notes/cad-svg-dxf.md",ROOT/"docs/cad-svg-dxf.md",manifest.parent/"README.md",directory/"README.md"]
    md_links=0
    for doc in docs:
        for link in re.findall(r'\]\(([^)]+)\)',doc.read_text()):
            target=urlsplit(link)
            if target.scheme or not target.path:continue
            if target.path=="verification.json" or target.path.endswith("/verification.json"):continue
            assert (doc.parent/unquote(target.path)).exists(),(doc,link)
            md_links+=1
    suite=ET.parse(junit).getroot().find("testsuite")
    assert int(suite.get("failures"))==int(suite.get("errors"))==int(suite.get("skipped"))==0
    positive_trials=[t for o in report["observations"] for t in o["trials"] if o["expected_status"]=="candidate"]
    negative_trials=[t for o in report["observations"] for t in o["trials"] if o["expected_status"]=="withheld"]
    assert all(t["passed"] for t in positive_trials+negative_trials)
    audit={"date":"2026-10-22","base_commit":"a878738d5493a8d8d1eed5423819972f78e03349",
           "test_command":"python -m pytest -q --junitxml=output/cad-svg-tests.xml",
           "pytest":{"tests":int(suite.get("tests")),"failures":0,"errors":0,"skipped":0,"seconds":float(suite.get("time"))},
           "input_hash_checks":checks,"source_hashes_match":True,"positive_trials":len(positive_trials),
           "withheld_trials":len(negative_trials),"html_local_links":local_links,"markdown_local_links":md_links,
           "external_html_assets":0,"new_test_file_sha256":sha(ROOT/"tests/test_cad_svg_pairs.py"),
           "results_sha256":sha(directory/"results.json"),"report_sha256":sha(directory/"report.html"),
           "manual_browser_check":["native SVG visible","STEP 3D visible","edited model selection","arrow-key orbit",
                                   "SVG missing-X withholding","DXF/native-SVG view switch"],
           "not_tested":["native Windows","other CAD exporters","arbitrary curves","customer drawings","AI/OCR"],
           "artifact_sha256":{str(p.relative_to(directory)):sha(p) for p in directory.rglob("*") if p.is_file() and p.name!="verification.json"}}
    (directory/"verification.json").write_bytes(json_bytes(audit))
    print(json.dumps({k:v for k,v in audit.items() if k!="artifact_sha256"},indent=2))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory",type=Path);parser.add_argument("--junit",type=Path,required=True)
    args=parser.parse_args();verify(args.directory,args.junit)
