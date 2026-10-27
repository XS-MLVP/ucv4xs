#!/usr/bin/env python3
"""Old six green joint cases: first raw quiescent snapshot violates LDU revoke.

No actor/expected/change oracle. A RAR+LRQ owner overlap with no in-flight LDU
cannot be evidence of the source-valid steady capacity program used here.
"""
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_lsq_cbo_serialization_v2 import inspect as serialization
from audit_lsq_bus_v2 import rob, sq
from audit_lsq_population_v1 import events, paths_by_node
from audit_sq_initial import ROOT, sha, verify_common


def inspect(path):
    owners={}
    rar={}
    replay=set()
    queries={}
    s3={}
    sequence=loads=stores=external=quiet=0
    counts=Counter()
    for row in events(path):
        i,pre,post,t=row["input"],row["before"],row["after"],row["post_tick"]
        counts["prefix_raw_records"]+=1
        if i["reset"]:
            assert not owners
            continue
        assert not i["redirect"]["valid"],"initial snapshot must precede branch/reset recovery"
        assert not post["io_toLsqEnqCtrl_lqDeq_valid"] and not post["io_toLsqEnqCtrl_sqDeq_valid"]
        for d in i["dispatch"]:
            if not d["valid"]:continue
            assert d["flows"]==1
            sequence+=1
            if d["need_alloc"]==1:
                pos=120*int(d["load_start"]["flag"])+d["load_start"]["value"]
                assert pos==loads
                owners[pos]=dict(uid=sequence,rob=d["rob"],position=pos)
                loads+=1
            else:
                stores+=1
                assert sq(d["store_end"])==stores
        for lane,q in enumerate(i["rar_queries"]):
            if not q["valid"]:continue
            pos=120*int(q["lq"]["flag"])+q["lq"]["value"]
            s=owners[pos]
            assert s["rob"]==q["rob"]
            queries[s["uid"]]=dict(tick=t,lane=lane)
            if pre[f"io_ldu_rarNukeQuery_{lane}_req_ready"] and pos>0:
                assert s["uid"] not in rar
                rar[s["uid"]]=s
        for lane,p in enumerate(i["loads"]):
            e=p["execution"]
            if not e["valid"]:continue
            pos=120*int(e["uop"]["lq"]["flag"])+e["uop"]["lq"]["value"]
            s=owners[pos]
            assert s["rob"]==e["uop"]["rob"] and e["need_replay"] and not e["replay_feedback"]
            replay.add(s["uid"])
            original=queries.get(s["uid"])
            if original is None:counts["S3_without_any_original_S2_query"]+=1
            elif original["tick"]+2!=t or original["lane"]!=lane:counts["S3_not_native_next_edge_same_lane"]+=1
            if not i["rar_revoke_last"][lane]:counts["Replay_S3_without_native_RAR_revoke"]+=1
            s3[s["uid"]]=dict(tick=t,lane=lane,cause=e["causes"],native_revoke=i["rar_revoke_last"][lane])
        assert not any((*i["rar_revoke_last"],*i["rar_revoke_older"])),"this rejection relies on actual absent revokes"
        if pre["io_uncache_req_valid"] and i["bus"]["ready"]:external+=1
        if i["bus"]["response"]:external-=1
        active=any(q["valid"] for q in(*i["queries"],*i["rar_queries"],*i["raw_queries"],*i["bypass"])) or any(q["execution"]["valid"] for q in i["loads"])
        quiet=0 if active else quiet+1
        if loads==120 and stores==128 and len(rar)==96 and len(replay)==120 and external==16 and quiet>=6:
            overlap=sorted(set(rar)&replay)
            assert len(overlap)==96
            assert all(uid in s3 and not s3[uid]["native_revoke"] for uid in overlap)
            return dict(counts=dict(counts),actual_snapshot=dict(tick=t,quiet_edges=quiet,SQ=128,LQ=120,RAR_record_UIDs=96,LRQ_owner_UIDs=120,
                                                               unreturned_external_jobs=16,RAR_and_LRQ_overlapping_original_UIDs=len(overlap)),
                        overlapping_UIDs=overlap,witnesses=[dict(original_UID=uid,original_S2=queries[uid],actual_Replay_S3=s3[uid]) for uid in overlap[:4]],
                        normal_producer_admission="REJECT_QUIESCENT_RAR_RECORDS_NOT_REVOKED_BY_THEIR_ORIGINAL_REPLAY")
    raise AssertionError("no complete raw initial snapshot; do not accept actor summary as evidence")


def audit():
    run=ROOT/"results/lsq-joint-capacity-04"
    manifest,source,nodes=verify_common(run)
    assert manifest["tests"]=={"PASS":6}
    cases=[]
    totals=Counter()
    for node,path in sorted(paths_by_node(run).items()):
        result=inspect(path)
        permission=serialization(path)
        assert permission["violations"]
        totals.update(result["counts"])
        cases.append(dict(nodeid=node,raw_SHA256=sha(path),journal=str(path.relative_to(run)),**result,CBO_source_permission=permission))
    assert len(cases)==6
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    target=dest/Path(__file__).name
    if target.exists():assert sha(target)==sha(Path(__file__))
    else:shutil.copy2(__file__,target)
    report=dict(run=run.name,status="SIX_OLD_PASS_OUTCOMES_KEPT_BUT_NORMAL_JOINT_CAPACITY_PRODUCER_REJECTED",actual_tests=manifest["tests"],snapshot_files=len(source),counts=dict(totals),cases=cases,
                auditor_SHA256=sha(Path(__file__)),
                source_relation="For these scalar aligned requests at a quiescent boundary, a replaying Load withdraws its own RAR query at native S3.96 original RAR identities simultaneously overlap120 LRQ identities only because the old stream delayed S3 and omitted revoke. Old snapshots/UID effects are real interface evidence, not a source-valid steady normal capacity witness.",
                next_required_program="Keep each capacity peak and real UID obligations, but stage legal RAR96/RAW56/LQ120/Uncache16 with LRQ24, then real returned NC bypass/VLQ progress and newly admitted original loads establish LRQ120 while RAR reclaims. CBO intent follows real empty ROB and BlockBack, not preallocated inside the full program. No smaller legal capacities or replacement of eight full-domain random failures.",
                limits="Rechecks initial raw snapshots only, not all22 historical actor snapshots as normal. Old6 PASS/5456 UID effects/DA and original failures unchanged; NoSpec/BlockBack and S3 producer violations are separate from RTL faults. Not a blanket unreachable proof for all vector/split/transient configurations or a change to overall completion criteria.")
    out=run/"joint-producer-audit-v1.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="cases"},indent=2,ensure_ascii=False))


if __name__=="__main__":audit()
