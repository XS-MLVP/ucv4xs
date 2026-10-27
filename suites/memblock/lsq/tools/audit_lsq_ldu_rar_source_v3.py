#!/usr/bin/env python3
"""Bind the v2 diagnosis's witness packets to original dispatch UID, not ROB.

V2's pipeline totals used full ROB+LQ, but one explanatory packet list filtered
only ROB and accidentally included a cancelled older ROB incarnation. Preserve
that rejected report; rebuild every witness from public dispatch identity here.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_lsq_ldu_rar_source_v1 import inspect
from audit_lsq_ldu_rar_source_v2 import identity, pipeline_review
from audit_lsq_population_v1 import paths_by_node
from audit_sq_initial import ROOT, sha, verify_common


def bind(rows):
    sequence=0
    active={}
    owners={}
    for row in rows:
        i,t=row["input"],row["post_tick"]
        for d in i["dispatch"]:
            if not d["valid"]:continue
            assert d["flows"]==1
            sequence+=1
            if d["need_alloc"]==1:
                key=identity(d["rob"],d["load_start"])
                owner=dict(uid=sequence,dispatch_tick=t,rob=d["rob"],lq=d["load_start"],queries=[],packets=[])
                active[key]=owners[sequence]=owner
        for lane,q in enumerate(i["rar_queries"]):
            if q["valid"]:
                owner=active[identity(q["rob"],q["lq"])]
                owner["queries"].append(dict(original_UID=owner["uid"],tick=t,lane=lane,**q,
                                             accepted=bool(row["before"][f"io_ldu_rarNukeQuery_{lane}_req_ready"])))
        for lane,p in enumerate(i["loads"]):
            e=p["execution"]
            if e["valid"]:
                owner=active[identity(e["uop"]["rob"],e["uop"]["lq"])]
                owner["packets"].append(dict(original_UID=owner["uid"],tick=t,lane=lane,ROB=owner["rob"],LQ=owner["lq"],
                                             causes=e["causes"],feedback=e["replay_feedback"],slot=e["slot"]))
    return owners


def audit(name):
    assert name=="lsq-serialized-mixed-01"
    run=ROOT/"results"/name
    manifest,source,nodes=verify_common(run)
    assert manifest["tests"]=={"FAIL":8}
    predecessor=json.loads((run/"ldu-rar-producer-audit-v2.json").read_text())
    counts,cases=Counter(),[]
    target=None
    for node,path in sorted(paths_by_node(run).items()):
        result,rows,queries=pipeline_review(path)
        bound=bind(rows)
        counts.update(result["counts"])
        cases.append(dict(nodeid=node,journal=str(path.relative_to(run)),sha256=sha(path),**result))
        if node.endswith("[28928]"):
            old=inspect(path)
            oldest=next(s for s in old["remaining"] if s["uid"]==97)
            line=oldest["query"]["PA"]//64
            candidates=[]
            for s in old["remaining"]:
                if s["kind"]!="load" or s["order"]<=oldest["order"]:continue
                b=bound[s["uid"]]
                history=[q for q in b["queries"] if q["accepted"] and q["paddr"]//64==line and q["data_valid"]]
                if not history:continue
                releases=[r["post_tick"] for r in rows if r["input"]["release"]["valid"]
                          and r["input"]["release"]["paddr"]//64==line and any(q["tick"]<r["post_tick"] for q in history)]
                candidates.append(dict(younger_original_UID=s["uid"],dispatch_tick=b["dispatch_tick"],ROB=s["rob"],LQ=b["lq"],
                                       original_queries=history,S3_packets=b["packets"],same_line_release_ticks=releases))
            assert len(candidates)==1 and candidates[0]["younger_original_UID"]==101
            assert [p["tick"] for p in candidates[0]["S3_packets"]]==[814,940]
            bad=predecessor["seed28928"]["younger_same_line_public_witnesses"][0]["S3_packets"]
            rejected=[p for p in bad if p["tick"] not in {v["tick"] for v in candidates[0]["S3_packets"]}]
            assert len(rejected)==1 and rejected[0]["tick"]==372
            actual_old=next(b for b in bound.values() if any(p["tick"]==372 and b["rob"]==candidates[0]["ROB"] for p in b["packets"]))
            assert actual_old["uid"]!=101 and actual_old["lq"]!=candidates[0]["LQ"]
            target=dict(oldest_remaining=oldest,remaining_original_UIDs=[s["uid"] for s in old["remaining"]],
                        final_public_head=old["final_public_head"],younger_same_line_public_witnesses=candidates,
                        rejected_predecessor_packet=dict(packet=rejected[0],actual_original_UID=actual_old["uid"],actual_LQ=actual_old["lq"],
                                                         reason="same encoded ROB, older cancelled generation; NOT UID101"),
                        attribution="Original UID97/LQ22 repeats 1021 RAR nukes as C_NK and cannot advance the head. Original younger UID101/LQ26 queried at810, misreported Replay at814 without native-edge revoke, then truly returned original-slot S3 at940 after query936. Same-line releases894..1180 leave a released younger reader behind blocked head22. Driver must route RAR violation to original ROB flushAfter, not LRQ. Not a new RTL deadlock.")
    assert counts==Counter(predecessor["counts"]) and cases==predecessor["cases"]
    assert target is not None
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    deps={}
    for filename in (Path(__file__).name,"audit_lsq_ldu_rar_source_v1.py","audit_lsq_ldu_rar_source_v2.py"):
        file=Path(__file__).with_name(filename)
        copy=dest/filename
        if copy.exists():assert sha(copy)==sha(file)
        else:shutil.copy2(file,copy)
        deps[filename]=sha(file)
    report=dict(run=name,status="ORIGINAL_DISPATCH_UID_BOUND_LDU_SOURCE_REJECTION_NOT_NEW_RTL_DEADLOCK",tests=manifest["tests"],snapshot_files=len(source),
                counts=dict(counts),seed28928=target,cases=cases,auditors=deps,
                rejected_predecessor=dict(path="ldu-rar-producer-audit-v2.json",sha256=sha(run/"ldu-rar-producer-audit-v2.json"),
                                          reason="one explanatory S3 packet list used ROB-only identity; v3 preserves exact same full-key pipeline totals but fixes that original-UID witness"),
                limits="No expected/change/private state or actor oracle. Source gates, old FAILs and no-new-deadlock attribution unchanged. Earlier CBO serialization approval is not whole-LDU approval. Correct LDU directed/native and full-domain random evidence remain separate mandatory work.")
    out=run/"ldu-rar-producer-audit-v3.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="cases"},indent=2,ensure_ascii=False))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("name")
    audit(p.parse_args().name)
