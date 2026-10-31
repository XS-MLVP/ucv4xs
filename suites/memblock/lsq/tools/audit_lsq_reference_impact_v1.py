#!/usr/bin/env python3
"""448-case affected-reference regression, preserving all65 prior failures.

Some old leaf journals lack nodeid: explicitly compare a per-family multiset of
canonical raw trace hashes (not a false per-node association). The199 LoadQueue
journals also have exact node identity. No expected/change/issue oracle used.
"""
import argparse
from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path
import shutil

from audit_lsq_population_v1 import events
from audit_sq_initial import ROOT,sha,verify_common


FAMILIES={"raw":("load_queue_raw.jsonl",),"load_uncache":("load_queue_uncache.jsonl",),
          "psq":("physical_store_queue.jsonl","psq_full.jsonl"),"store_queue":("store_queue.jsonl",),"load_queue":("load_queue.jsonl",)}
FIELDS=("pre_tick","post_tick","input","post_input","pins","post_pins","before","after")


def raw_hash(path):
    digest,records=hashlib.sha256(),0
    for row in events(path):
        assert all(key in row for key in ("pre_tick","post_tick","input","before","after"))
        payload={key:row[key] for key in FIELDS if key in row}
        digest.update(json.dumps(payload,sort_keys=True,separators=(",",":")).encode())
        digest.update(b"\n")
        records+=1
    return digest.hexdigest(),records


def family_hashes(run,family):
    result=Counter()
    for filename in FAMILIES[family]:
        for path in (run/"cases").rglob(filename):
            result[raw_hash(path)]+=1
    return result


def audit(name):
    assert name=="lsq-reference-impact-01"
    run=ROOT/"results"/name
    manifest,source,nodes=verify_common(run)
    baseline={family:ROOT/"results"/("lq-expanded-06" if family=="load_queue" else "lsq-progress-regression-06") for family in FAMILIES}
    assert manifest["tests"]=={"PASS":383,"FAIL":65} and len(nodes)==448 and len(source)==346
    previous={}
    for directory in set(baseline.values()):
        previous[directory]=verify_common(directory)[2]
    reports=[]
    total=0
    for family,directory in baseline.items():
        current={node:failed for node,failed in nodes.items() if node.startswith(f"tests/{family}/")}
        old={node:failed for node,failed in previous[directory].items() if node.startswith(f"tests/{family}/")}
        assert current==old
        a,b=family_hashes(directory,family),family_hashes(run,family)
        assert a==b, (family,"changed raw native trace multiset")
        assert sum(b.values())==len(current)
        records=sum(count*length for (_,length),count in b.items())
        total+=records
        reports.append(dict(family=family,prior=directory.name,cases=len(current),tests=dict(Counter("FAIL" if failed else "PASS" for failed in current.values())),
                            actual_raw_records_unchanged=records,raw_trace_canonical_sha256_multiset=[dict(sha256=digest,records=length,count=count) for (digest,length),count in sorted(b.items())]))
    assert {report["family"]:report["cases"] for report in reports}==dict(raw=32,load_uncache=72,psq=66,store_queue=79,load_queue=199)
    wrapper=ROOT/"results/lsq-expanded-13"
    verify_common(wrapper)
    models=('lsqverify/raw/model.py','lsqverify/load_queue/model.py','lsqverify/load_uncache/model.py','lsqverify/psq/model.py')
    assert all(sha(run/"verification-source"/file)==sha(wrapper/"verification-source"/file) for file in models)
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    for file in (Path(__file__),ROOT/"tools/audit_sq_initial.py"):
        target=dest/file.name
        if target.exists():
            assert sha(target)==sha(file)
        else:
            shutil.copy2(file,target)
    report=dict(run=name,status="NOT_PASS_448_affected_reference_cases_native_histories_and_all65_failures_unchanged",tests=manifest["tests"],snapshot_files=len(source),
                native_builds=len({a["build"]["build_id"] for a in manifest["artifacts"] if a["kind"]=="native"}),
                raw_records_unchanged=total,all_case_results_equal_frozen_previous=True,families=reports,
                updated_models_same_as_full253_wrapper_snapshot={file:sha(run/"verification-source"/file) for file in models},auditor_sha256=sha(dest/Path(__file__).name),
                limits="Affected5-DUT/448-case repeat only, not the full36/38-DUT final unified regression or functional acceptance. Every original case and65FAIL retained; per-family multiset of full raw native trace hashes unchanged, explicitly not claiming node mapping for old leaf journals lacking nodeid. No expected/change or issue manifest oracle and no independent-leaf coverage merged into Wrapper.")
    output=run/"reference-impact-audit-v1.json"
    if output.exists():
        assert json.loads(output.read_text())==report
    else:
        output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({**{key:value for key,value in report.items() if key!="families"},"families":[{key:value for key,value in family.items() if key!="raw_trace_canonical_sha256_multiset"} for family in reports]},indent=2,ensure_ascii=False))


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
