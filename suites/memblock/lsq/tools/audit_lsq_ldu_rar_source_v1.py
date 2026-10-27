import ucv.runtime as ucv_paths
#!/usr/bin/env python3
"""Distinguish LDU STA-nuke replay, RAR rollback and speculative query revoke.

Read only public histories and pinned OPEN producer source. No DUT/model/actor
state, expected/change fields or known-issue oracle supplies semantic answers.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_lsq_bus_v2 import pointer, rob, sq
from audit_lsq_mixed_history_v1 import Timeline
from audit_lsq_population_v1 import events, paths_by_node
from audit_sq_initial import ROOT, sha, verify_common


def inspect(path):
    timeline=Timeline()
    owners,program,bysq,bylq=[],[],{},{}
    sh=st=lh=lt=0
    previous=None
    last_sta=None
    counts=Counter()
    violations=[]
    for row in events(path):
        i,pre,post,tick=row["input"],row["before"],row["after"],row["post_tick"]
        counts["raw_records"]+=1
        if i["reset"]:
            assert not owners
            previous=row
            continue
        head=timeline.decode(i["pending"],True)
        assert pointer(pre,"io_sqDeqPtr_")==sh%256
        for d in i["dispatch"]:
            if not d["valid"]:continue
            assert d["flows"]==1
            s=dict(uid=len(owners)+1,order=timeline.decode(d["rob"],True),rob=d["rob"],kind="load" if d["need_alloc"]==1 else "store",
                   cancelled=False,complete=False,dispatch_tick=tick,query=None,last_packet=None,bypass=None,query_count=0,nuke_count=0,C_NK_count=0)
            owners.append(s)
            program.append(s)
            if s["kind"]=="load":
                s.update(position=lt,sq_boundary=st)
                assert 120*int(d["load_start"]["flag"])+d["load_start"]["value"]==lt%240
                bylq[lt%240]=s
                lt+=1
            else:
                s["position"]=st
                bysq[st]=s
                st+=1
                assert sq(d["store_end"])==st%256
        if any(a["valid"] for a in i["addresses"]):last_sta=tick
        for lane,q in enumerate(i["rar_queries"]):
            if not q["valid"]:continue
            s=bylq[120*int(q["lq"]["flag"])+q["lq"]["value"]]
            assert s["rob"]==q["rob"] and not s["cancelled"]
            assert post[f"io_ldu_rarNukeQuery_{lane}_resp_valid"]
            s["query"]=dict(tick=tick,lane=lane,rar_nuke=bool(post[f"io_ldu_rarNukeQuery_{lane}_resp_bits_nuke"]),
                            PA=q["paddr"],data_valid=q["data_valid"],nc=q["nc"])
            s["query_count"]+=1
            s["nuke_count"]+=s["query"]["rar_nuke"]
            packet=s["last_packet"]
            if s["bypass"] is not None and packet and packet["mmio"] and not packet["execution"]["nc"]:
                violations.append(dict(kind="MMIO_replay_RAR_query_after_own_returned_data_bypass",uid=s["uid"],rob=s["rob"],tick=tick,lane=lane,
                                       original_bypass_tick=s["bypass"],actual_RAR_query=s["query"],
                                       source_rule="NewLoadUnit1089 canNukeQuery=!isMMIOReplay&&!isPrefetch"))
                counts["MMIO_replay_RAR_query_after_bypass"]+=1
        for packet in i["loads"]:
            q,u=packet["execution"],packet["execution"]["uop"]
            if not q["valid"]:continue
            s=bylq[120*int(u["lq"]["flag"])+u["lq"]["value"]]
            assert s["rob"]==u["rob"] and not s["cancelled"]
            s["last_packet"]=packet
            if q["need_replay"] and q["causes"]==1<<11:
                s["C_NK_count"]+=1
                query=s["query"]
                if not(packet["mmio"] or q["nc"]) and query and query["rar_nuke"] and (last_sta is None or tick-last_sta>4):
                    violations.append(dict(kind="cached_RAR_nuke_repeated_as_C_NK_without_nearby_STA",uid=s["uid"],rob=s["rob"],tick=tick,
                                           original_query=query,last_actual_STA_tick=last_sta,S3_causes=q["causes"],actual_pending=i["pending"],
                                           source_rule="RAR nuke is S3 rollback flushAfter; C_NK is S2 concurrent STA nuke, not RAR response"))
                    counts["cached_RAR_nuke_as_C_NK_without_STA"]+=1
            if previous and q["need_replay"]:
                for lane,old in enumerate(previous["input"]["rar_queries"]):
                    if old["valid"] and old["rob"]==u["rob"] and old["lq"]==u["lq"]:
                        counts["actual_previous_edge_RAR_query_then_S3_replay"]+=1
                        if not i["rar_revoke_last"][lane]:
                            violations.append(dict(kind="S3_replay_did_not_revoke_its_previous_edge_RAR_query",uid=s["uid"],rob=s["rob"],tick=tick,
                                                   query_tick=previous["post_tick"],query_lane=lane,S3_causes=q["causes"],
                                                   source_rule="NewLoadUnit1483-1488 s3RevokeReplay=causeOrR -> revokeLastCycle"))
                            counts["missing_required_previous_RAR_revoke"]+=1
        for b in i["bypass"]:
            if b["valid"]:
                s=bylq[120*int(b["lq"]["flag"])+b["lq"]["value"]]
                assert not s["cancelled"]
                s["bypass"]=tick
        red=i["redirect"]
        if red["valid"]:
            cut=timeline.decode(red["rob"])
            for s in program:
                if s["order"]>cut or red["flush_self"] and s["order"]==cut:s["cancelled"]=True
        delta=(pointer(post,"io_sqDeqPtr_")-sh)%256
        for pos in range(sh,sh+delta):bysq[pos]["complete"]=True
        sh+=delta
        if post["io_toLsqEnqCtrl_lqDeq_valid"]:
            n=post["io_toLsqEnqCtrl_lqDeq_bits"]
            for pos in range(lh,lh+n):bylq[pos%240]["complete"]=True
            lh+=n
        if post["io_toLsqEnqCtrl_sqRedirectPtr_valid"]:st=sh+(pointer(post,"io_toLsqEnqCtrl_sqRedirectPtr_bits_")-sh)%256
        if post["io_toLsqEnqCtrl_lqRedirectPtr_valid"]:lt=lh+(120*post["io_toLsqEnqCtrl_lqRedirectPtr_bits_flag"]+post["io_toLsqEnqCtrl_lqRedirectPtr_bits_value"]-lh)%240
        previous=row
    live=[s for s in owners if not s["complete"] and not s["cancelled"]]
    counts["original_UIDs"]=len(owners)
    counts["failed_live_UIDs"]=len(live)
    return dict(counts=dict(counts),violations=violations,remaining=[{k:s[k] for k in("uid","kind","rob","order","position","query_count","nuke_count","C_NK_count","query")} for s in live],
                final_public_head=dict(ROB=previous["input"]["pending"],SQ_deq=sh,LQ_deq=lh,last_STA=last_sta))


def audit(name):
    assert name=="lsq-serialized-mixed-01"
    run=ROOT/"results"/name
    manifest,source,nodes=verify_common(run)
    assert manifest["tests"]=={"FAIL":8}
    ldu=ucv_paths.source_path_for(ROOT) / 'src/main/scala/xiangshan/mem/pipeline/NewLoadUnit.scala'
    text=ldu.read_text()
    bindings=("val canNukeQuery = !isMMIOReplay && !isPrefetch","cause(C_NK) := troubleMaker && nuke",
              "val s3RevokeReplay = causeOrR","val s3RarViolation = rarResp.valid && rarResp.bits.nuke",
              "val rollbackLevel = Mux(matchInvalid, RedirectLevel.flush, RedirectLevel.flushAfter)")
    assert all(s in text for s in bindings)
    counts,cases=Counter(),[]
    for node,path in sorted(paths_by_node(run).items()):
        result=inspect(path)
        counts.update(result["counts"])
        cases.append(dict(nodeid=node,journal=str(path.relative_to(run)),sha256=sha(path),**result))
    target=next(c for c in cases if c["nodeid"].endswith("[28928]"))
    old=next(s for s in target["remaining"] if s["uid"]==97)
    assert old["kind"]=="load" and old["C_NK_count"]>900 and old["nuke_count"]>900 and len(target["remaining"])==18
    assert counts["cached_RAR_nuke_as_C_NK_without_STA"]>900
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    auditor=dest/Path(__file__).name
    if auditor.exists():assert sha(auditor)==sha(Path(__file__))
    else:shutil.copy2(Path(__file__),auditor)
    report=dict(run=name,status="REJECT_FULL_LDU_PRODUCER_ADMISSION_RAR_NUKE_ROUTE_REVOKE_AND_MMIO_QUERY_REVIEW_NOT_NEW_RTL_DEADLOCK",tests_unchanged=manifest["tests"],
                snapshot_files=len(source),counts=dict(counts),cases=cases,producer_source=dict(path=str(ldu),sha256=sha(ldu),bindings=bindings),auditor_sha256=sha(auditor),
                limits="Previous CBO NoSpec/BlockBack and package gates remain true, but are not a complete LDU producer proof. Cached RAR nuke belongs to flushAfter rollback, not fabricated C_NK; Replay cause11 here can spin behind a younger released reader indefinitely. Missing query revoke/MMIO-after-bypass requests are separate source-domain observations. This rejects labeling the fair timeout as a new RTL deadlock. Does not hide any actual FAIL, alter RTL/expected/reference or bless the seven other mixed prefixes as whole-program legal. Real isolated serialized CBO fault/zero directed effects remain separate evidence; new correct LDU pipeline/rollback/revoke/minimal/native/full-domain reruns still required.")
    out=run/"ldu-rar-producer-audit-v1.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="cases"},indent=2,ensure_ascii=False))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("name")
    audit(p.parse_args().name)
