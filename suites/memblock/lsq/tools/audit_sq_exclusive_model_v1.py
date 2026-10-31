#!/usr/bin/env python3
"""Narrow model-delta gate plus all archived RAW/Replay input-history equivalence.

This is reference-impact evidence, NOT independent native functional signoff.
"""
import ast
from dataclasses import asdict, fields, is_dataclass
import json
from pathlib import Path
import shutil
import typing

from audit_sq_initial import ROOT, sha, verify_common
from suites.memblock.lsq.raw.model import LoadQueueRawModel
from suites.memblock.lsq.raw.types import Inputs as RawInputs, SqPtr
from suites.memblock.lsq.replay.model import ReplayModel, sq_after
from suites.memblock.lsq.replay.types import Inputs as ReplayInputs
from suites.memblock.lsq.sq_endpoint.model import ExclusiveRawModel, ExclusiveReplayModel


def typed(kind, value):
    if is_dataclass(kind):
        hints=typing.get_type_hints(kind)
        return kind(**{f.name:typed(hints[f.name],value[f.name]) for f in fields(kind)})
    if typing.get_origin(kind) is tuple:
        args=typing.get_args(kind)
        return tuple(typed(args[0] if len(args)==2 and args[1] is Ellipsis else args[n],v) for n,v in enumerate(value))
    return value


def audit(name):
    run=ROOT/"results"/name
    manifest,source,nodes=verify_common(run)
    assert set(source)>={'lsqverify/sq_endpoint/model.py',"tests/sq_endpoint/conftest.py"}
    frozen=run/"verification-source"
    old=ast.parse((frozen/'lsqverify/raw/model.py').read_text())
    new=ast.parse((frozen/'lsqverify/sq_endpoint/model.py').read_text())
    context=next(n for n in ast.walk(old) if isinstance(n,ast.FunctionDef) and n.name=="context")
    replacement=next(n for n in ast.walk(new) if isinstance(n,ast.FunctionDef) and n.name=="context")
    loop=next(n for n in context.body if isinstance(n,ast.For))
    guards=[n for n in loop.body if isinstance(n,ast.If) and ast.unparse(n.test)=="distance == half"]
    assert len(guards)==1 and len(guards[0].body)==1 and isinstance(guards[0].body[0],ast.Raise)
    loop.body.remove(guards[0])
    comparisons=[n for n in ast.walk(loop) if isinstance(n,ast.Compare) and ast.unparse(n)=="distance < half"]
    assert len(comparisons)==1
    comparisons[0].ops=[ast.LtE()]
    assert ast.dump(context,include_attributes=False)==ast.dump(replacement,include_attributes=False)
    assert {n.name for n in ast.walk(new) if isinstance(n,ast.FunctionDef)}=={"context","update_blocked","__init__"}
    subclass=next(n for n in new.body if isinstance(n,ast.ClassDef) and n.name=="ExclusiveReplayModel")
    assert len(subclass.body)==1 and subclass.body[0].name=="update_blocked"
    body=ast.unparse(subclass.body[0])
    assert "owner.request.causes != 1 << Cause.RAW_CAPACITY" in body and "super().update_blocked(owner, inp)" in body
    # The general helper remains deliberately undefined at half-ring.
    rejected=0
    for start in range(256):
        try:sq_after(SqPtr.encode(start+128),SqPtr.encode(start))
        except ValueError as exc:
            assert "ambiguous half-ring" in str(exc)
            rejected+=1
        else:raise AssertionError("blanket sq_after relaxation")
    prior=ROOT/"results/lsq-progress-regression-09"
    previous,old_source,_=verify_common(prior)
    assert previous["tests"]=={"PASS":1691,"FAIL":191}
    for key,digest in old_source.items():
        if key.startswith('lsqverify/'):
            assert source[key]==digest,("changed shared reference during isolated domain work",key)
    specs=json.loads((frozen/"manifest/duts.json").read_text())["duts"]
    counts={}
    trace_hashes={}
    for family,filename,kind,legacy,extended in(("RAW","load_queue_raw.jsonl",RawInputs,lambda:LoadQueueRawModel(specs["load_queue_raw"]),lambda:ExclusiveRawModel(specs["load_queue_raw"])),
                                               ("Replay","load_queue_replay.jsonl",ReplayInputs,ReplayModel,ExclusiveReplayModel)):
        files=sorted((prior/"cases").rglob(filename))
        assert len(files)==(32 if family=="RAW" else 131)
        cycles=0
        for path in files:
            a,b=legacy(),extended()
            for text in path.read_text().splitlines():
                row=json.loads(text)
                inp=typed(kind,row["input"])
                if family=="RAW":
                    assert a.outputs_for(inp)==b.outputs_for(inp)
                    ready=tuple(row["before"]["ready"])
                    assert asdict(a.advance(inp,ready))==asdict(b.advance(inp,ready))
                    assert a.outputs_for(inp)==b.outputs_for(inp)
                else:
                    assert a.expected(inp)==b.expected(inp)
                    assert a.advance(inp)==b.advance(inp)
                    assert a.expected(inp)==b.expected(inp)
                cycles+=1
            trace_hashes[str(path.relative_to(ROOT))]=sha(path)
        counts[family]=dict(frozen_logs=len(files),actual_input_cycles_compared=cycles,all_pre_post_and_semantic_changes_equal=True)
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    target=dest/Path(__file__).name
    if target.exists():assert sha(target)==sha(Path(__file__))
    else:shutil.copy2(__file__,target)
    report=dict(status="PASS_NARROW_OPT_IN_REFERENCE_IMPACT_ONLY_NOT_NATIVE_OR_GOAL_SIGNOFF",run=name,tests=manifest["tests"],snapshot_files=len(source),
                general_half_ring_rejections_preserved=rejected,RAW_context_AST_only_delta="delete exact-half ValueError and use <= half for Load-exclusive forward position",Replay_delta="RAW_CAPACITY only; all other causes inherit original branch",counts=counts,
                original_logs_SHA256=trace_hashes,auditor_sha256=sha(Path(__file__)),limits="All old shared models stay identical. Archived input-history model equivalence is not new native DUT execution, not an independent behavioral oracle, and does not grant arbitrary half-ring domains or complete full-Wrapper capacity/random verification.")
    out=run/"exclusive-reference-impact-v1.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="original_logs_SHA256"},indent=2,ensure_ascii=False))


if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("name")
    audit(p.parse_args().name)
