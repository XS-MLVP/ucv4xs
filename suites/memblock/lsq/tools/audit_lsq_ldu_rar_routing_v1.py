#!/usr/bin/env python3
"""Independent normal LDU stages, original recovery, Replay and actual effects.

Read raw input/pins/before/after and fixture comparison evidence only. Do not
read reference changes, actor summaries, internal DUT state or known issues.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_lsq_bus_v2 import pointer, rob, rob_matches, sq
from audit_lsq_bus_v3 import differences
from audit_lsq_memory_v1 import lq
from audit_lsq_population_v1 import events, paths_by_node, validate_row
from audit_sq_initial import ROOT, sha, verify_common


def inspect(path, failed):
    future_queries={(row["post_tick"],lane):lq(q["lq"]) for row in events(path)
                    for lane,q in enumerate(row["input"]["rar_queries"]) if q["valid"]}
    owners,bylq,stores=[],{},{}
    head=tail=shead=stail=0
    previous=None
    fwd=[None]*3
    s3=[None]*3
    red_due=None
    store_s2=[]
    counts=Counter()
    stages=[]
    grants={}
    recoveries=[]
    peak_rar=0
    rar_live=set()
    for row in events(path):
        validate_row(row,previous,False)
        i,pre,post,t=row["input"],row["before"],row["after"],row["post_tick"]
        counts["raw_records"]+=1
        counts["checked_records"]+=row["checked"]
        assert not any(pre[p+"valid"] for p in("io_uncache_req_","io_cmoOpReq_","io_mmioStout_"))
        if i["reset"]:
            assert not owners
            previous=row
            continue
        assert pointer(pre,"io_sqDeqPtr_")==shead
        for s in owners:
            if rob(s["rob"])<rob(i["pending"]):
                assert s.get("sent") if s["kind"]=="load" else s.get("s2_done") and "data" in s
        for d in i["dispatch"]:
            if not d["valid"]:continue
            assert d["flows"]==1 and not i["redirect"]["valid"]
            s=dict(uid=len(owners)+1,rob=d["rob"],kind="load" if d["need_alloc"]==1 else "store",sent=False,complete=False,cancelled=False)
            owners.append(s)
            if s["kind"]=="load":
                assert lq(d["load_start"])==tail
                s["position"]=tail
                bylq[tail]=s
                tail+=1
            else:
                s["position"]=stail
                stores[stail]=s
                stail+=1
                assert sq(d["store_end"])==stail
        red=i["redirect"]
        if red["valid"]:
            assert red_due is not None and red["rob"]==red_due["rob"] and not red["flush_self"]
            assert red_due["sent"] and not red_due["cancelled"]
            victims=[s for s in owners if not s["complete"] and not s["cancelled"] and rob(s["rob"])>rob(red["rob"])]
            assert victims and all(s["kind"]=="load" for s in victims)
            for s in victims:
                s["cancelled"]=t
                rar_live.discard(s["uid"])
            recoveries.append(dict(tick=t,original_anchor_UID=red_due["uid"],original_ROB=red["rob"],flush_self=False,
                                   cancelled_UIDs=[s["uid"] for s in victims]))
            counts["original_RAR_flushAfter"]+=1
            red_due=None
        elif red_due is not None:
            raise AssertionError("next-edge original RAR rollback missing")
        for s,lane in store_s2:
            assert i["attributes"][lane]["last"] and i["attributes"][lane]["memory"]
            s["s2_done"]=t
        store_s2=[]
        for lane,a in enumerate(i["addresses"]):
            if a["valid"]:
                s=stores[shead+(a["slot"]-shead)%64]
                assert a["rob"]==s["rob"] and not a["tlb_miss"] and a["last"] and not a["unaligned"]
                s["address"]=a
                store_s2.append((s,lane))
        for d in i["data"]:
            if d["valid"]:
                s=stores[sq(d["sq"])]
                assert "data" not in s
                s["data"]=d["data"]
        next_s3=[None]*3
        for lane,q in enumerate(i["rar_queries"]):
            if not q["valid"]:
                assert not i["raw_queries"][lane]["valid"]
                continue
            s=bylq[lq(q["lq"])]
            assert s["rob"]==q["rob"] and not s["sent"] and not s["cancelled"]
            assert previous is not None and fwd[lane] is not None
            item=fwd[lane]
            assert item["s"] is s and item["S1_tick"]+2==t and item["PA"]==q["paddr"]
            w=i["raw_queries"][lane]
            assert w["valid"] and w["rob"]==q["rob"] and w["paddr"]==q["paddr"] and w["data_valid"]==q["data_valid"]
            assert q["data_valid"] and not q["nc"] and w["mask"]==255
            assert pre[f"io_ldu_rarNukeQuery_{lane}_req_ready"] and pre[f"io_ldu_rawNukeQuery_{lane}_req_ready"]
            for family in("rar","raw"):
                p=f"io_ldu_{family}NukeQuery_{lane}_req_"
                assert row["pins"][p+"valid"] and row["pins"][p+"bits_paddr"]==q["paddr"] and row["pins"][p+"bits_dataValid"]==1
                rob_matches(row["pins"],p+"bits_robIdx_",s["rob"])
            assert post[f"io_ldu_rarNukeQuery_{lane}_resp_valid"]
            next_s3[lane]=dict(s=s,S2_tick=t,RAR_nuke=bool(post[f"io_ldu_rarNukeQuery_{lane}_resp_bits_nuke"]),
                               STA=list(i["addresses"]),PA=q["paddr"],mask=w["mask"],**{k:item[k] for k in("S0_tick","S1_tick")})
            if s["position"]>head:rar_live.add(s["uid"])
            peak_rar=max(peak_rar,len(rar_live))
            counts["normal_S2_RAR_RAW_pairs"]+=1
        for lane,p in enumerate(i["loads"]):
            e,u=p["execution"],p["execution"]["uop"]
            item=s3[lane]
            assert e["valid"]==(item is not None)
            revoke=bool(e["valid"] and e["need_replay"])
            assert i["rar_revoke_last"][lane]==i["raw_revoke_last"][lane]==revoke
            assert not i["rar_revoke_older"][lane] and not i["raw_revoke_older"][lane]
            if item is None:continue
            s=item["s"]
            assert lq(u["lq"])==s["position"] and u["rob"]==s["rob"] and item["S2_tick"]+2==t
            assert not p["mmio"] and not e["nc"] and p["update_address"]
            assert e["causes"] in(0,1<<5,1<<11) and e["need_replay"]==bool(e["causes"])
            if e["replay_feedback"]:
                assert grants.pop(e["slot"]) is s
                counts["original_slot_S3_feedbacks"]+=1
            if e["causes"]==1<<11:
                sta=[a for a in item["STA"] if a["valid"] and not a["tlb_miss"] and rob(a["rob"])<rob(s["rob"])
                     and a["paddr"]//16==item["PA"]//16 and a["mask"]&item["mask"]]
                assert len(sta)==1 and not item["RAR_nuke"]
                counts["C_NK_bound_to_real_older_concurrent_STA"]+=1
            if e["need_replay"]:
                rar_live.discard(s["uid"])
                counts["native_next_edge_same_lane_RAR_RAW_revokes"]+=1
            else:
                assert not s["sent"]
                s["sent"]=t
            if item["RAR_nuke"]:
                assert not e["need_replay"] and not e["causes"]
                red_due=s
            stages.append(dict(original_UID=s["uid"],lane=lane,S0_tick=item["S0_tick"],S1_tick=item["S1_tick"],
                               S2_tick=item["S2_tick"],S3_tick=t,cause=e["causes"],RAR_nuke=item["RAR_nuke"],
                               replay_feedback=e["replay_feedback"],original_slot=e["slot"] if e["replay_feedback"] else None))
            counts["normal_S0_S1_S2_S3_completions_or_replays"]+=1
        for b in range(3):
            p=f"io_replay_{b}_"
            if pre[p+"valid"] and i["replay_ready"][b]:
                s=bylq[120*pre[p+"bits_uop_lqIdx_flag"]+pre[p+"bits_uop_lqIdx_value"]]
                rob_matches(pre,p+"bits_uop_robIdx_",s["rob"])
                slot=pre[p+"bits_replayQueueIdx"]
                assert not s["cancelled"] and slot not in grants and slot%3==b
                grants[slot]=s
                counts["actual_original_replay_grants"]+=1
        for lane in range(2):
            p=f"io_sbuffer_req_{lane}_"
            if pre[p+"valid"] and i["sbuffer_ready"][lane]:
                s=next(s for s in stores.values() if not s.get("fire"))
                a=s["address"]
                assert s.get("s2_done") and "data" in s and rob(s["rob"])<=rob(i["pending"])
                assert pre[p+"bits_vaddr"]==a["vaddr"] and pre[p+"bits_addr"]==a["paddr"] and pre[p+"bits_mask"]==255 and not pre[p+"bits_wline"]
                assert pre[p+"bits_data"]&((1<<64)-1)==s["data"]&((1<<64)-1)
                s["fire"]=t
                counts["original_Store_Sbuffer_consumptions"]+=1
        delta=(pointer(post,"io_sqDeqPtr_")-shead)%256
        for pos in range(shead,shead+delta):
            s=stores[pos]
            assert s["fire"]+2==t and not s["complete"]
            s["complete"]=t
        shead+=delta
        if post["io_toLsqEnqCtrl_lqDeq_valid"]:
            n=post["io_toLsqEnqCtrl_lqDeq_bits"]
            for pos in range(head,head+n):
                s=bylq[pos]
                assert s["sent"] and not s["complete"] and not s["cancelled"]
                s["complete"]=t
            head+=n
        rar_live={uid for uid in rar_live if next(s for s in owners if s["uid"]==uid)["position"]>head}
        if post["io_toLsqEnqCtrl_lqRedirectPtr_valid"]:
            tail=120*post["io_toLsqEnqCtrl_lqRedirectPtr_bits_flag"]+post["io_toLsqEnqCtrl_lqRedirectPtr_bits_value"]
            recoveries[-1]["actual_LQ_recovery"]=tail
        if post["io_toLsqEnqCtrl_sqRedirectPtr_valid"]:
            recoveries[-1]["actual_SQ_recovery"]=pointer(post,"io_toLsqEnqCtrl_sqRedirectPtr_bits_")
        # Current S1 PA belongs to previous S0; its post-edge response is the
        # next cycle's S2 input. Never identify it using a current S3 packet.
        fwd=[None]*3
        if previous is not None:
            for lane,q in enumerate(previous["input"]["queries"]):
                if not q["valid"]:continue
                tr=i["translations"][lane]
                matches=[s for s in owners if s["kind"]=="load" and not s["cancelled"] and not s["sent"]
                         and s.get("VA")==q["vaddr"] and s.get("SQ")==sq(q["sq"])]
                if not matches:
                    # First query provides VA; its original identity is the
                    # only not-yet-executed owner whose later S2 packet binds.
                    future=future_queries[t+2,lane]
                    matches=[bylq[future]]
                assert len(matches)==1 and not tr["kill"] and post[f"io_forward_{lane}_s2Resp_valid"]
                s=matches[0]
                s["VA"],s["SQ"]=q["vaddr"],sq(q["sq"])
                fwd[lane]=dict(s=s,PA=tr["paddr"],S0_tick=previous["post_tick"],S1_tick=t)
        s3=next_s3
        previous=row
    assert previous is not None and bool("error" in previous)==failed
    if failed:
        diff=differences(previous)
        assert not diff["before"] and len(diff["after"])==1
        pin,pair=next(iter(diff["after"].items()))
        assert "rarNukeQuery" in pin and pin.endswith("resp_bits_nuke") and pair==[0,1]
        counts["normal_previous_release_RAR_missed_nuke"]+=1
    else:
        assert all(s["complete"] or s["cancelled"] for s in owners) and not grants and not red_due
        assert previous["after"]["io_lqEmpty"] and previous["after"]["io_sqEmpty"] and not previous["after"]["io_replayAllocate"]
    reuse=[]
    for s in owners:
        if s["cancelled"]:
            witnesses=[n for n in owners if n["uid"]>s["uid"] and n["kind"]==s["kind"] and n["position"]%120==s["position"]%120 and n["complete"]]
            assert witnesses
            reuse.append(dict(cancelled_UID=s["uid"],new_completed_UID=witnesses[0]["uid"],physical_slot=s["position"]%120))
    for key,pred in(("allocated",lambda s:True),("completed",lambda s:bool(s["complete"])),("cancelled",lambda s:bool(s["cancelled"])),
                     ("failed_retained",lambda s:not s["complete"] and not s["cancelled"])):
        counts[key]=sum(pred(s) for s in owners)
    counts["same_physical_slot_new_UID_completion"]=len(reuse)
    assert counts["allocated"]==counts["completed"]+counts["cancelled"]+counts["failed_retained"]
    return dict(counts=dict(counts),original_stages=stages,recoveries=recoveries,same_slot_completion=reuse,
                peak_public_RAR_ownership=peak_rar,terminal_tick=previous["post_tick"],
                actual_terminal_failure=previous.get("error"),full_cycle_reference_compared=True)


def audit(name):
    assert name in("lsq-ldu-rar-routing-01","lsq-ldu-rar-routing-02")
    run=ROOT/"results"/name
    manifest,source,nodes=verify_common(run)
    expected={"PASS":12 if name.endswith("01") else 13,"FAIL":3}
    assert manifest["tests"]==expected
    paths=paths_by_node(run)
    assert set(paths)==set(nodes)
    counts,cases=Counter(),[]
    for node,path in sorted(paths.items()):
        result=inspect(path,nodes[node])
        counts.update(result["counts"])
        if "full_96_RAR" in node:
            assert not nodes[node] and result["peak_public_RAR_ownership"]==96 and result["counts"]["completed"]==97
        cases.append(dict(nodeid=node,journal=str(path.relative_to(run)),sha256=sha(path),pytest_result="FAIL" if nodes[node] else "PASS",**result))
    assert counts["original_RAR_flushAfter"]==3 and counts["same_physical_slot_new_UID_completion"]==3
    assert counts["C_NK_bound_to_real_older_concurrent_STA"]==counts["original_Store_Sbuffer_consumptions"]==3
    assert counts["actual_original_replay_grants"]==counts["original_slot_S3_feedbacks"]==6
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    copy=dest/Path(__file__).name
    if copy.exists():assert sha(copy)==sha(Path(__file__))
    else:shutil.copy2(Path(__file__),copy)
    report=dict(run=name,status="NORMAL_ALIGNED_CACHED_LDU_STAGES_ORIGINAL_EFFECTS_AUDITED_RETAIN_3_RAR_FAILS_NOT_FULL_RANDOM_SIGNOFF",tests=manifest["tests"],
                snapshot_files=len(source),counts=dict(counts),cases=cases,auditor_sha256=sha(copy),
                limits="Source-normal aligned cached subset: S0 Forward/S1 PA/S2 RAR+RAW/S3 same lane+native revoke, original RAR flushAfter with same-slot new UID completion, and real older STA-only C_NK verified from public history. Does not bless old interface RAR-as-C_NK streams, prove all LDU types or full random, narrow half-ring ages, change RTL/reference, or hide 3 strict previous-release failures. Existing coverage bins are not retroactively marked checked by summaries.")
    out=run/"ldu-rar-routing-audit-v1.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="cases"},indent=2,ensure_ascii=False))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("name")
    audit(p.parse_args().name)
