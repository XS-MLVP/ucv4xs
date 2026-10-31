#!/usr/bin/env python3
"""Correct only v1 import/bootstrap and class-method vs nested-closure inventory.

Preserve v1/v2 failures. RAW AST delta and every archived equivalence gate stay.
"""
import argparse
import ast
from dataclasses import asdict
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from audit_sq_exclusive_model_v1 import typed
from audit_sq_initial import sha, verify_common
from suites.memblock.lsq.raw.model import LoadQueueRawModel
from suites.memblock.lsq.raw.types import Inputs as RawInputs, SqPtr
from suites.memblock.lsq.replay.model import ReplayModel, sq_after
from suites.memblock.lsq.replay.types import Inputs as ReplayInputs
from suites.memblock.lsq.sq_endpoint.model import ExclusiveRawModel, ExclusiveReplayModel


def audit(name):
    run=ROOT/"results"/name
    manifest,source,_=verify_common(run)
    frozen=run/"verification-source"
    old=ast.parse((frozen/'lsqverify/raw/model.py').read_text())
    new=ast.parse((frozen/'lsqverify/sq_endpoint/model.py').read_text())
    original=next(n for n in ast.walk(old) if isinstance(n,ast.FunctionDef) and n.name=="context")
    replacement=next(n for n in ast.walk(new) if isinstance(n,ast.FunctionDef) and n.name=="context")
    loop=next(n for n in original.body if isinstance(n,ast.For))
    guards=[n for n in loop.body if isinstance(n,ast.If) and ast.unparse(n.test)=="distance == half"]
    assert len(guards)==1 and len(guards[0].body)==1 and isinstance(guards[0].body[0],ast.Raise)
    loop.body.remove(guards[0])
    comparisons=[n for n in ast.walk(loop) if isinstance(n,ast.Compare) and ast.unparse(n)=="distance < half"]
    assert len(comparisons)==1
    comparisons[0].ops=[ast.LtE()]
    assert ast.dump(original,include_attributes=False)==ast.dump(replacement,include_attributes=False)
    classes={n.name:n for n in new.body if isinstance(n,ast.ClassDef)}
    assert {name:{n.name for n in cls.body if isinstance(n,ast.FunctionDef)} for name,cls in classes.items()}=={
        "ExclusiveRawModel":{"context"},"ExclusiveReplayModel":{"update_blocked"},"ExclusiveWrapperModel":{"__init__"}}
    assert {n.name for n in ast.walk(new) if isinstance(n,ast.FunctionDef)}=={"context","flushed","update_blocked","__init__"}
    body=ast.unparse(classes["ExclusiveReplayModel"])
    assert "owner.request.causes != 1 << Cause.RAW_CAPACITY" in body and "super().update_blocked(owner, inp)" in body
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
        if key.startswith('lsqverify/'):assert source[key]==digest,("shared reference changed",key)
    assert sha(ROOT/"sq_endpoint/model.py")==source['lsqverify/sq_endpoint/model.py']
    specs=json.loads((frozen/"manifest/duts.json").read_text())["duts"]
    counts,trace_hashes={},{}
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
    hashes={}
    for file in(Path(__file__),ROOT/"tools/audit_sq_exclusive_model_v1.py",ROOT/"tools/audit_sq_exclusive_model_v2.py"):
        target=dest/file.name
        if target.exists():assert sha(target)==sha(file)
        else:shutil.copy2(file,target)
        hashes[file.name]=sha(file)
    report=dict(status="PASS_NARROW_OPT_IN_REFERENCE_IMPACT_NOT_NATIVE_OR_GOAL_SIGNOFF",run=name,tests=manifest["tests"],snapshot_files=len(source),
                general_half_ring_rejections_preserved=rejected,RAW_context_AST_only_delta="remove exact-half ValueError and use <= half for Load-exclusive forward position",Replay_delta="RAW_CAPACITY only; all other causes inherited",counts=counts,
                original_logs_SHA256=trace_hashes,auditors=hashes,preserved_auditor_failures=[
                    'v1 direct script import had no project root on sys.path: ModuleNotFoundError:lsqverify before any gate',
                    "v2 bootstrapped import but v1 ast.walk method inventory omitted the existing nested flushed closure. v3 checks class-level methods and requires the unchanged nested closure explicitly; raw-context exact AST normalization gate retained."],
                limits="Archived old-input pre/post/change equivalence is reference-impact only, not new native DUT execution or an independent semantic oracle. Shared models unchanged; arbitrary half-ring comparisons remain rejected. Parent capacity/random/full goal still need actual native and independent effects gates.")
    out=run/"exclusive-reference-impact-v3.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="original_logs_SHA256"},indent=2,ensure_ascii=False))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("name")
    audit(p.parse_args().name)
