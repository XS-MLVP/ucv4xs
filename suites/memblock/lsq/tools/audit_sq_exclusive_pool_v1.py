#!/usr/bin/env python3
"""Gap-driven native Replay120 endpoint additions, original public slots/UIDs."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil

from audit_lsq_population_v1 import events, paths_by_node, replay_metadata
from audit_raw_trace import sq_raw
from audit_sq_exclusive_history_v1 import checked_rows
from audit_progress_run_v7 import RAW
from audit_sq_initial import ROOT, sha, verify_common


def inspect(path):
    rows=checked_rows(path)
    reqs,grants={},{}
    feedback=set()
    active=set()
    awake=False
    unlock=None
    start=end=lane0=None
    counts=Counter(raw_records=len(rows))
    wake=None
    for row in rows:
        i,pre,post,t=row["input"],row["before"],row["after"],row["post_tick"]
        if i["reset"]:
            assert not reqs
            continue
        assert not i["redirect"]["valid"] and not i["sq_empty"]
        for lane,q in enumerate(i["enqueues"]):
            if not q["valid"]:continue
            key=120*int(q["uop"]["lq"]["flag"])+q["uop"]["lq"]["value"]
            if not q["replay_feedback"]:
                assert not awake and key not in reqs and q["causes"]==1<<10
                if start is None:
                    start=sq_raw(i["address_ready"])
                    end=(start+128)%256
                    lane0=lane
                assert lane==lane0 and sq_raw(q["uop"]["sq"])==end
                reqs[key]=q
                active.add(key)
                counts["original_RAW_CAPACITY_records"]+=1
            else:
                assert key in grants and key not in feedback and q["slot"]==grants[key] and lane==lane0
                assert q["uop"]==reqs[key]["uop"] and q["vaddr"]==reqs[key]["vaddr"] and not q["need_replay"] and not q["causes"]
                feedback.add(key)
                active.remove(key)
                counts["original_slot_completion_feedbacks"]+=1
        if reqs:
            d=(end-sq_raw(i["address_ready"]))%256
            assert d in(0,128)
            if not awake and (not i["raw_full"] or d==0):
                assert len(reqs)==120
                awake=True
                unlock=t
                wake="pool_credit" if not i["raw_full"] else "address_prefix"
            for phase,pins in(("before",pre),("after",post)):
                for bank in range(3):
                    p=f"io_replay_{bank}_"
                    if not pins[p+"valid"]:continue
                    assert awake and t>=unlock+2
                    key=120*pins[p+"bits_uop_lqIdx_flag"]+pins[p+"bits_uop_lqIdx_value"]
                    assert key in active
                    req=reqs[key]
                    size=req["uop"]["operation"]>>1&7
                    mask=((1<<(1<<(size&3)))-1)<<(req["vaddr"]%16)&65535
                    replay_metadata(pins,p+"bits_",dict(fullva=req["vaddr"],execution={**req,"mask":mask}))
                    slot=pins[p+"bits_replayQueueIdx"]
                    assert slot%3==bank and (key not in grants or grants[key]==slot)
                    if phase=="before" and i["ready"][bank]:
                        assert key not in grants and slot not in grants.values()
                        grants[key]=slot
                        counts["actual_original_grants"]+=1
                        counts[f"actual_bank{bank}_grants"]+=1
            if not awake:
                counts["blocked_edges_without_any_spurious_grant"]+=1
            if len(reqs)==120 and not feedback:assert post["io_lqFull"]
            assert post["io_replayAllocate"]==int(bool(active))
    assert start in(0,255) and lane0 in range(3) and wake in("pool_credit","address_prefix")
    assert set(reqs)==set(grants)==feedback==set(range(120)) and set(grants.values())==set(range(120)) and not active
    assert not rows[-1]["after"]["io_lqFull"] and not rows[-1]["after"]["io_replayAllocate"]
    assert all(counts[f"actual_bank{b}_grants"]==40 for b in range(3))
    return dict(signature=dict(start=start,input_lane=lane0,wake=wake),counts=dict(counts),actual_original_LQ_to_slot=grants,
                leaf_scope="external RAW-full/address-prefix contract, not real Wrapper all-pool capacity or native LDU")


def raw_key(path):
    digest=hashlib.sha256()
    count=0
    for row in events(path):
        digest.update(json.dumps({k:row[k] for k in RAW if k in row},sort_keys=True,separators=(",",":")).encode())
        digest.update(b"\n")
        count+=1
    return digest.hexdigest(),count


def audit(name):
    assert name=="lsq-raw-exclusive-06"
    run=ROOT/"results"/name
    manifest,source,nodes=verify_common(run)
    assert manifest["tests"]=={"PASS":75} and len(nodes)==75 and not any(nodes.values())
    prior=ROOT/"results/lsq-raw-exclusive-05"
    old,old_source,old_nodes=verify_common(prior)
    assert old["tests"]=={"PASS":63} and old_nodes.keys()<=nodes.keys()
    assert all(source[k]==h for k,h in old_source.items()),"old63 launch files changed instead of only adding cases"
    totals=Counter()
    details=[]
    for filename in("load_queue_raw.jsonl","load_queue_replay.jsonl","lsq_wrapper.jsonl"):
        a=Counter(raw_key(p) for p in (prior/"cases").rglob(filename))
        b=Counter(raw_key(p) for p in (run/"cases").rglob(filename))
        assert a<=b
        new=b-a
        assert sum(new.values())==(12 if filename=="load_queue_replay.jsonl" else 0)
        for path in sorted((run/"cases").rglob(filename)):
            if raw_key(path) not in new:continue
            assert filename=="load_queue_replay.jsonl"
            result=inspect(path)
            totals.update(result["counts"])
            details.append(dict(journal=str(path.relative_to(run)),sha256=sha(path),**result))
    assert len(details)==12
    assert {(d["signature"]["start"],d["signature"]["input_lane"],d["signature"]["wake"]) for d in details}=={
        (start,lane,wake) for start in(0,255) for lane in range(3) for wake in("pool_credit","address_prefix")}
    assert totals["original_RAW_CAPACITY_records"]==totals["actual_original_grants"]==totals["original_slot_completion_feedbacks"]==1440
    source_report=json.loads((prior/"ldu-s3-source-audit-v1.json").read_text())
    assert not any(c["violations"] for r in source_report["runs"] if r["run"]==prior.name for c in r["details"])
    for node,path in paths_by_node(run).items():assert raw_key(path)==raw_key(paths_by_node(prior)[node])
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    target=dest/Path(__file__).name
    if target.exists():assert sha(target)==sha(Path(__file__))
    else:shutil.copy2(__file__,target)
    report=dict(run=name,status="75_NATIVE_ENDPOINT_CASES_OLD63_EXACT_AND_1440_NEW_REPLAY_OWNERS_COMPLETE_NOT_GOAL_SIGNOFF",tests=manifest["tests"],snapshot_files=len(source),
                old63_raw_history_multiset_exactly_preserved=True,old6_Wrapper_node_raw_exact=True,old_original_Wrapper_UID_completions_preserved=1110,
                new_full_pool_counts=dict(totals),new_leaf_cases=details,old63_independent_report_SHA256=sha(prior/"exclusive-history-audit-v2.json"),
                old_correct_S3_and_old_domain_rejection_SHA256=sha(prior/"ldu-s3-source-audit-v1.json"),auditor_SHA256=sha(Path(__file__)),
                limits="12 new native Replay leaf cases/1440 original owners and original feedback slots only; no cross-DUT merge. Early leaf journals have no nodeid, so exact raw multiset/public-input signatures, not an invented leaf-node map. Existing6 normal endpoint Wrapper histories and1110 original completions exactly retained. Still not full mixed producer/S3 correction, simultaneous all-pool/CBO stages, old RTL failures or final whole-goal audit.")
    report=json.loads(json.dumps(report))
    out=run/"exclusive-pool-audit-v1.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="new_leaf_cases"},indent=2,ensure_ascii=False))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("name")
    audit(p.parse_args().name)
