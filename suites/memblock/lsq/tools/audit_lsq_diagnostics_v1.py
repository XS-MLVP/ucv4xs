#!/usr/bin/env python3
"""Default-OFF native reruns must preserve the entire checked stream digest.

Summaries are not an offline raw replay audit. Equality with an already-audited
native baseline is a logging-impact check, not new semantic coverage/signoff.
"""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

from audit_progress_run_v7 import failures
from audit_sq_initial import ROOT, sha, verify_common


def node_from_object(obj):
    p=subprocess.Popen(["zstd","-q","-d","-c",str(obj)],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    try:
        row=json.loads(p.stdout.readline())
        return row["nodeid"]
    finally:
        p.stdout.close();p.terminate();p.wait()


def catalog(run,selected=None):
    result={}
    index=run/"storage-index-v1.json"
    if index.exists():
        for e in json.loads(index.read_text())["files"]:
            if Path(e["path"]).name!="lsq_wrapper.jsonl":continue
            obj=ROOT/e["object"]
            assert sha(obj)==e["object_SHA256"]
            node=node_from_object(obj)
            if selected is not None and node not in selected:continue
            assert node not in result
            result[node]=dict(SHA256=e["SHA256"],bytes=e["bytes"])
    else:
        for path in(run/"cases").rglob("lsq_wrapper.jsonl"):
            with path.open() as f:node=json.loads(f.readline())["nodeid"]
            if selected is not None and node not in selected:continue
            assert node not in result
            result[node]=dict(SHA256=sha(path),bytes=path.stat().st_size)
    return result


def audit():
    run=ROOT/"results/lsq-diagnostics-default-01"
    m,source,nodes=verify_common(run)
    assert len(nodes)==79 and m["tests"]=={"PASS":78,"FAIL":1}
    assert not list((run/"cases").rglob("*.jsonl")) and not list((run/"cases").rglob("*.fst")) and not list((run/"cases").rglob("*.vcd"))
    policy=json.loads((run/"trace-policy.json").read_text())
    assert not policy["per_cycle_JSON"] and not policy["waveforms"]
    prior=ROOT/"results/lsq-ldu-s4-plain-01"
    old_source=json.loads((prior/"source-evidence.json").read_text())["files"]
    shared={k:v for k,v in old_source.items() if k.startswith('lsqverify/') and k!='lsqverify/native.py'}
    assert all(source[k]==v for k,v in shared.items()),"logging policy must not change models/comparators/UID drivers"
    old=catalog(prior)
    failure_prior=ROOT/"results/lsq-progress-regression-11"
    old.update(catalog(failure_prior,selected=set(nodes)))
    assert set(old)==set(nodes)
    checked=[]
    for path in(run/"cases").rglob("lsq_wrapper.summary.json"):
        summary=json.loads(path.read_text())
        node=summary["nodeid"]
        assert node in nodes and not summary["trace_enabled"] and not summary["trace_truncated"] and summary["saved_trace_bytes"]==0
        assert summary["streamed_SHA256"]==old[node]["SHA256"] and summary["serialized_bytes"]==old[node]["bytes"]
        assert path.stat().st_size<8192
        checked.append(dict(nodeid=node,stream_SHA256=summary["streamed_SHA256"],native_records=summary["records"],avoided_uncompressed_bytes=summary["serialized_bytes"],summary_bytes=path.stat().st_size))
    assert len(checked)==79 and len({c["nodeid"] for c in checked})==79
    now,before=failures(run),failures(failure_prior)
    assert len(now)==1 and all(before[n]==message for n,message in now.items())
    report=dict(status="DEFAULT_OFF_ACTUAL79_NATIVE_STREAMS_EQUAL_PRIOR_FULL_TRACES_NOT_GOAL_SIGNOFF",tests=m["tests"],snapshot_files=len(source),
                per_cycle_JSON_files=0,waveform_files=0,unchanged_shared_reference_files=len(shared),all79_full_stream_SHA256_equal=True,
                old_SID_failure_retained=True,native_records=sum(c["native_records"] for c in checked),
                avoided_raw_bytes=sum(c["avoided_uncompressed_bytes"] for c in checked),summary_bytes=sum(c["summary_bytes"] for c in checked),
                cases=sorted(checked,key=lambda c:c["nodeid"]),auditor_SHA256=sha(Path(__file__)),
                limits="Runtime reference, full output checks and UID assertions still run. Digest equality checks diagnostic implementation impact only. No independent replay from an unretained new trace, no new whole-S4 producer admission or whole-goal success.")
    out=run/"diagnostics-default-audit-v1.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="cases"},indent=2))


if __name__=="__main__":audit()
