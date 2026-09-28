"""Staged bounded STEP inspection and lazy authored-box assembly BVH queries."""
from __future__ import annotations
import hashlib
import math
import time
from dataclasses import asdict,dataclass
from pathlib import Path
import numpy as np
from research_notes.step_part21 import STEPParseLimits,parse_part21_document,Part21ParseError


@dataclass(frozen=True)
class WorkBudget:
    max_bytes:int=8_000_000
    max_entities:int=100_000
    max_tokens:int=2_000_000
    max_estimated_memory_bytes:int=256_000_000
    max_seconds:float=30.
    max_geometry:int=128
    max_pairs:int=4096
    max_topology:int=100_000

    def __post_init__(self):
        for key,value in asdict(self).items():
            if not math.isfinite(value) or value<=0 or (key!="max_seconds" and type(value) is not int):raise ValueError("positive finite work budgets required")


def inspect_step_stages(path:Path,budget=WorkBudget(),*,clock=time.monotonic):
    started=clock();path=Path(path)
    with path.open("rb") as stream:source=stream.read(budget.max_bytes+1)
    report={"stage":"bytes","status":"quarantined","byte_count":len(source),"source_sha256":hashlib.sha256(source).hexdigest(),
            "budgets":asdict(budget),"native_security_boundary":False}
    if len(source)>budget.max_bytes:
        report["read_prefix_sha256"]=report["source_sha256"];report["source_sha256"]=None
        report["reason"]="byte_budget";return report,None
    # Heuristic planning estimate, not a measured peak or an OS memory limit.
    estimated=len(source)*32
    report["estimated_parser_memory_bytes"]=estimated
    if estimated>budget.max_estimated_memory_bytes:report["reason"]="estimated_memory_budget";return report,None
    if clock()-started>budget.max_seconds:report["reason"]="time_budget";return report,None
    try:
        document=parse_part21_document(source,limits=STEPParseLimits(max_file_bytes=budget.max_bytes,max_entities=budget.max_entities,max_tokens=budget.max_tokens))
    except Part21ParseError as exc:
        report.update(stage="syntax",reason=exc.reason_code,status="rejected" if exc.decision=="reject" else "quarantined");return report,None
    report.update(stage="syntax",entity_count=len(document.entities),schema_identifiers=list(document.schema_identifiers),geometry_evaluated=False)
    if clock()-started>budget.max_seconds:report["reason"]="time_budget";return report,None
    report.update(status="accepted",reason="syntax_only_geometry_deferred")
    return report,document


@dataclass(frozen=True)
class BoxOccurrence:
    occurrence_id:str
    size:tuple[float,float,float]
    origin:tuple[float,float,float]=(0.,0.,0.)
    rotation:tuple[tuple[float,float,float],...]=((1.,0.,0.),(0.,1.,0.),(0.,0.,1.))

    def bounds(self):
        r=np.array(self.rotation);p=np.array(self.origin);s=np.array(self.size)
        if s.shape!=(3,) or p.shape!=(3,) or r.shape!=(3,3) or not np.isfinite(r).all() or not np.isfinite(s).all() or not np.isfinite(p).all() or np.any(s<=0) or max(np.max(s),np.max(np.abs(p)))>10000:
            raise ValueError("invalid bounded box occurrence")
        if not np.allclose(r.T@r,np.eye(3),atol=1e-10) or abs(np.linalg.det(r)-1)>1e-10:raise ValueError("rigid proper rotation required")
        points=np.array([(x,y,z) for x in (0,s[0]) for y in (0,s[1]) for z in (0,s[2])])@r.T+p
        return points.min(axis=0),points.max(axis=0)


class BoxAssemblyIndex:
    """Exact authored-box bounds; all BVH candidates still need narrow-phase checks."""
    def __init__(self,occurrences,budget=WorkBudget(),*,clock=time.monotonic):
        self.occurrences=tuple(occurrences);self.budget=budget;self.cache={};self.clock=clock
        if not 1<=len(self.occurrences)<=min(budget.max_entities,100000):raise ValueError("occurrence budget")
        if len({o.occurrence_id for o in self.occurrences})!=len(self.occurrences):raise ValueError("duplicate occurrence ID")
        if len(self.occurrences)*1024>budget.max_estimated_memory_bytes:raise ValueError("index memory estimate budget")
        self.bounds=[o.bounds() for o in self.occurrences]
        if len(self.bounds)*1024>budget.max_estimated_memory_bytes:raise ValueError("index memory estimate budget")
        def build(indices):
            low=np.min([self.bounds[i][0] for i in indices],axis=0);high=np.max([self.bounds[i][1] for i in indices],axis=0)
            if len(indices)<=8:return low,high,tuple(indices),None,None
            axis=int(np.argmax(high-low));ordered=sorted(indices,key=lambda i:sum(b[axis] for b in self.bounds[i]));mid=len(ordered)//2
            return low,high,(),build(ordered[:mid]),build(ordered[mid:])
        self.root=build(list(range(len(self.occurrences))))

    def candidate_pairs(self,clearance=0.):
        if not math.isfinite(clearance) or clearance<0:raise ValueError("invalid clearance")
        started=self.clock();pairs=[];visits=0
        def overlaps(a,b):return bool(np.all(a[0]<=b[1]+clearance) and np.all(b[0]<=a[1]+clearance))
        for i,box in enumerate(self.bounds):
            stack=[self.root]
            while stack:
                if self.clock()-started>self.budget.max_seconds:return {"status":"partial","reason":"time_budget","pairs":pairs,"node_visits":visits}
                node=stack.pop();visits+=1
                if not overlaps(box,node[:2]):continue
                if node[2]:
                    for j in node[2]:
                        if j>i and overlaps(box,self.bounds[j]):
                            if len(pairs)>=self.budget.max_pairs:return {"status":"partial","reason":"pair_budget","pairs":pairs,"node_visits":visits}
                            pairs.append((i,j))
                else:stack.extend((node[3],node[4]))
        return {"status":"complete","reason":None,"pairs":sorted(pairs),"node_visits":visits}

    def geometry(self,index):
        if type(index) is not int or not 0<=index<len(self.occurrences):raise ValueError("invalid occurrence index")
        if index in self.cache:return self.cache[index]
        if len(self.cache)>=self.budget.max_geometry or (len(self.cache)+1)*27>self.budget.max_topology:raise ValueError("lazy geometry/topology budget")
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
        from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
        from OCP.gp import gp_Trsf
        o=self.occurrences[index];transform=gp_Trsf()
        transform.SetValues(*(value for row,offset in zip(o.rotation,o.origin) for value in (*row,offset)))
        shape=BRepBuilderAPI_Transform(BRepPrimAPI_MakeBox(*o.size).Shape(),transform,True).Shape()
        self.cache[index]=shape;return shape
