#!/usr/bin/env python3
"""Add actual query/S3 latency, lane and revoke evidence to frozen v1 review.

This is an admission audit, not a new reference or a FAIL-to-PASS conversion.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_lsq_ldu_rar_source_v1 import inspect
from audit_lsq_population_v1 import events, paths_by_node
from audit_sq_initial import ROOT, sha, verify_common


def identity(rob, lq):
    return (bool(rob["flag"]), rob["value"], bool(rob["former"]), bool(lq["flag"]), lq["value"])


def pipeline_review(path):
    rows=list(events(path))
    byt={r["post_tick"]:r for r in rows}
    last={}
    counts=Counter()
    examples=[]
    query_history=[]
    for row in rows:
        i,t=row["input"],row["post_tick"]
        for d in i["dispatch"]:
            if d["valid"] and d["need_alloc"]==1:
                assert d["flows"]==1
                last.pop(identity(d["rob"],d["load_start"]),None)
        for lane,q in enumerate(i["rar_queries"]):
            if q["valid"]:
                item=dict(tick=t,lane=lane,**q,accepted=bool(row["before"][f"io_ldu_rarNukeQuery_{lane}_req_ready"]))
                last[identity(q["rob"],q["lq"])]=item
                query_history.append(item)
        for lane,p in enumerate(i["loads"]):
            e=p["execution"]
            if not e["valid"]:continue
            query=last.get(identity(e["uop"]["rob"],e["uop"]["lq"]))
            if query is None:continue
            counts["queried_original_S3_packets"]+=1
            gap=(t-query["tick"])//2
            counts[f"S2_query_to_reported_S3_gap_{gap}_edges"]+=1
            counts["S3_lane_differs_from_original_query_lane"]+=lane!=query["lane"]
            native_s3=byt[query["tick"]+2]["input"]
            revoke=bool(native_s3["rar_revoke_last"][query["lane"]])
            if e["need_replay"]:
                counts["queried_original_S3_replays"]+=1
                counts["replay_query_native_next_edge_RAR_revoke_absent"]+=not revoke
                counts["replay_query_native_next_edge_RAW_revoke_absent"]+=not native_s3["raw_revoke_last"][query["lane"]]
            if len(examples)<12 and (gap!=1 or lane!=query["lane"] or e["need_replay"] and not revoke):
                examples.append(dict(query=query,reported_S3_tick=t,reported_S3_lane=lane,causes=e["causes"],
                                     native_S3_tick=query["tick"]+2,actual_native_S3_revokeRAR=revoke,
                                     actual_reported_S3_revokeRAR=i["rar_revoke_last"][lane]))
    return dict(counts=dict(counts),examples=examples),rows,query_history


def audit(name):
    assert name=="lsq-serialized-mixed-01"
    run=ROOT/"results"/name
    manifest,source,nodes=verify_common(run)
    assert manifest["tests"]=={"FAIL":8}
    counts,cases=Counter(),[]
    target=None
    for node,path in sorted(paths_by_node(run).items()):
        old=inspect(path)
        new,rows,queries=pipeline_review(path)
        counts.update(new["counts"])
        cases.append(dict(nodeid=node,journal=str(path.relative_to(run)),sha256=sha(path),**new))
        if node.endswith("[28928]"):
            old97=next(s for s in old["remaining"] if s["uid"]==97)
            line=old97["query"]["PA"]//64
            younger=[s for s in old["remaining"] if s["kind"]=="load" and s["order"]>old97["order"]
                     and s["query"] and s["query"]["PA"]//64==line and s["query"]["data_valid"]]
            witnesses=[]
            for s in younger:
                history=[q for q in queries if q["rob"]==s["rob"] and q["accepted"] and q["paddr"]//64==line]
                releases=[r["post_tick"] for r in rows if r["input"]["release"]["valid"]
                          and r["input"]["release"]["paddr"]//64==line
                          and any(q["tick"]<r["post_tick"] for q in history)]
                packets=[]
                for r in rows:
                    for lane,p in enumerate(r["input"]["loads"]):
                        e=p["execution"]
                        if e["valid"] and e["uop"]["rob"]==s["rob"]:
                            packets.append(dict(tick=r["post_tick"],lane=lane,causes=e["causes"],feedback=e["replay_feedback"]))
                witnesses.append(dict(younger_original_UID=s["uid"],ROB=s["rob"],LQ_absolute_position=s["position"],
                                      original_queries=history,same_line_release_ticks=releases,S3_packets=packets))
            assert old97["C_NK_count"]==old97["nuke_count"]==1021 and len(younger)==1 and witnesses[0]["younger_original_UID"]==101
            assert witnesses[0]["same_line_release_ticks"] and old["final_public_head"]["LQ_deq"]==22
            target=dict(oldest_remaining=old97,remaining_original_UIDs=[s["uid"] for s in old["remaining"]],
                        final_public_head=old["final_public_head"],younger_same_line_public_witnesses=witnesses,
                        attribution="Oldest UID97 loops on RAR nuke while younger UID101 remains behind LQ head22; UID101's first query was later reported as Replay without the source-required native next-edge revoke. After original younger feedback it remains a released same-line reader until head advances. Driver routes older nuke to LRQ instead of required flushAfter. This is concrete producer-level circular waiting, not proof of a new RTL deadlock.")
    assert target is not None and counts["replay_query_native_next_edge_RAR_revoke_absent"]>1000
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    for file in (Path(__file__),Path(__file__).with_name("audit_lsq_ldu_rar_source_v1.py")):
        copy=dest/file.name
        if copy.exists():assert sha(copy)==sha(file)
        else:shutil.copy2(file,copy)
    report=dict(run=name,status="SOURCE_LDU_PIPELINE_ADMISSION_REJECTED_ALL_EIGHT_FAILS_UNCHANGED_NOT_RTL_DEADLOCK",tests=manifest["tests"],
                snapshot_files=len(source),counts=dict(counts),seed28928=target,cases=cases,
                auditor_sha256=sha(Path(__file__)),dependency_v1_sha256=sha(Path(__file__).with_name("audit_lsq_ldu_rar_source_v1.py")),
                limits="V1's immediate-previous-edge counter alone was not a complete revoke audit: the old producer reported S3 two or more edges after its query, often on another lane. This v2 explicitly inspects the fixed native S3 edge. No expected/change/private actor or DUT state used; no result, RTL or reference edit. Minimal correct LDU directed and new full-domain random/coverage/recovery evidence still required.")
    out=run/"ldu-rar-producer-audit-v2.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="cases"},indent=2,ensure_ascii=False))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("name")
    audit(p.parse_args().name)
