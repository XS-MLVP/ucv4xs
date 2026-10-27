#!/usr/bin/env python3
"""Independent original-UID/full128 endpoint proof, not model predictions."""
import argparse
from collections import Counter
import itertools
import json
from pathlib import Path
import shutil

from audit_lsq_bus_v2 import pointer, rob, sq
from audit_lsq_mixed_history_v1 import Timeline
from audit_lsq_population_v1 import RAW, events, paths_by_node, replay_metadata, validate_row
from audit_sq_initial import ROOT, sha, verify_common


def inspect(path,failed=False):
    stores,load,pipe,pending_s2={},None,[],[]
    st=head=0
    previous,terminal=None,None
    timeline,counts=Timeline(),Counter()
    queries=[]
    for row in events(path):
        validate_row(row,previous,False)
        i,pre,post,tick=row["input"],row["before"],row["after"],row["post_tick"]
        counts["raw_records"]+=1
        assert not i["redirect"]["valid"] and not i["bus"]["ready"] and not i["bus"]["ack"] and not i["bus"]["response"]
        assert not pre["io_uncache_req_valid"] and not pre["io_cmoOpReq_valid"] and not pre["io_mmioStout_valid"]
        if i["reset"]:
            assert not stores and load is None
            previous=row
            continue
        assert pointer(pre,"io_sqDeqPtr_")==head%256
        order=timeline.decode(i["pending"],True)
        for s in stores.values():
            if s["order"]<order:assert s.get("s2") and "data" in s
        for d in i["dispatch"]:
            if not d["valid"]:continue
            assert not pre["io_toLsqEnqCtrl_lqRecoverStall"] and not pre["io_toLsqEnqCtrl_sqRecoverStall"]
            age=timeline.decode(d["rob"],True)
            assert age>=order and d["flows"]==1
            if d["need_alloc"]==2:
                assert load is None and st not in stores and st-head<128
                stores[st]=dict(uid=st+1,position=st,order=age,rob=d["rob"],complete=False,fire=None)
                st+=1
                assert sq(d["store_end"])==st%256
            else:
                assert d["need_alloc"]==1 and load is None and not d["load_start"]["flag"] and d["load_start"]["value"]==0
                load=dict(uid=st+1,rob=d["rob"],order=age,bound=st,sent=False,complete=False,packet=None,slot=None,grant=None)
        assert st-head<=128
        for s,lane in pending_s2:
            a=i["attributes"][lane]
            assert a["last"] and a["memory"] and not(a["exception"] or a["nc"] or a["mmio"])
            s["s2"]=tick
        pending_s2=[]
        for lane,a in enumerate(i["addresses"]):
            if not a["valid"]:continue
            pos=head+(a["slot"]-head)%64
            s=stores[pos]
            assert head<=pos<min(st,head+64) and not s["complete"] and "address" not in s and s["rob"]==a["rob"]
            assert (a["size"],a["mask"],a["fu_op"])==(3,255,6) and a["last"] and not(a["tlb_miss"] or a["cross_word"] or a["wline"])
            s["address"]=a
            pending_s2.append((s,lane))
            counts["actual_current_window_STA"]+=1
        for d in i["data"]:
            if not d["valid"]:continue
            pos=head+(sq(d["sq"])-head)%256
            s=stores[pos]
            assert head<=pos<min(st,head+64) and "data" not in s and d["fu_op"]==6
            s["data"]=d["data"]
        for lane,q,bank in pipe:
            t=i["translations"][lane]
            assert not t["kill"] and t["paddr"]%4096==q["vaddr"]%4096
            p=f"io_forward_{lane}_s2Resp_"
            assert post[p+"valid"] and not any(post[p+"bits_"+name] for name in ("matchInvalid","forwardInvalid","dataInvalid_valid"))
            assert post[p+"bits_addrInvalid_valid"]==int(q["strict"])
            if q["strict"]:assert pointer(post,p+"bits_addrInvalid_bits_")==(load["bound"]-1)%256
            for byte in range(16):
                address=t["paddr"]//16*16+byte
                sources=[s for s in bank if s.get("s2") and s["address"]["paddr"]<=address<s["address"]["paddr"]+8]
                active=q["vaddr"]%16<=byte<q["vaddr"]%16+(1<<q["size"]) and bool(sources)
                assert post[p+f"bits_forwardMask_{byte}"]==int(active)
                if active:
                    s=max(sources,key=lambda s:s["position"])
                    assert "data" in s and post[p+f"bits_forwardData_{byte}"]==s["data"]>>(8*(address-s["address"]["paddr"]))&255
                    counts["original_PA_bytes_checked"]+=1
            queries.append(dict(tick=tick,lane=lane,strict=q["strict"],exclusive_boundary=load["bound"],physical_window=[0,64],load_uid=load["uid"]))
        pipe=[]
        for lane,q in enumerate(i["queries"]):
            if not q["valid"]:continue
            assert load is not None and sq(q["sq"])==load["bound"]==st and head==0 and st in(127,128)
            assert all(stores[pos].get("s2") and "data" in stores[pos] for pos in range(64))
            pipe.append((lane,q,[s.copy() for pos,s in stores.items() if head<=pos<head+64]))
        for packet in i["loads"]:
            q,u=packet["execution"],packet["execution"]["uop"]
            if not q["valid"]:continue
            assert load and load["rob"]==u["rob"] and sq(u["sq"])==load["bound"] and packet["update_address"]
            if q["replay_feedback"]:
                assert load["grant"] is not None and q["slot"]==load["slot"] and u==load["packet"]["execution"]["uop"]
                load["grant"]=load["slot"]=None
                counts["original_replay_slot_feedback"]+=1
            else:
                assert load["packet"] is None
                load["packet"]=packet
            if q["need_replay"]:
                assert u["strict"] and u["load_wait"] and q["causes"]==1<<2 and sq(q["address_sq"])==st-1
                counts["strict_original_replay_allocation"]+=1
            else:
                assert not load["sent"] and head==st
                load["sent"]=tick
        for bank in range(3):
            p=f"io_replay_{bank}_"
            if pre[p+"valid"] and i["replay_ready"][bank]:
                assert load and not load["sent"] and load["grant"] is None and load["slot"] is None
                replay_metadata(pre,p+"bits_",load["packet"])
                load["slot"]=pre[p+"bits_replayQueueIdx"]
                load["grant"]=tick
                assert load["slot"]%3==bank
                counts["actual_original_replay_grant"]+=1
        for lane in range(2):
            p=f"io_sbuffer_req_{lane}_"
            if not(pre[p+"valid"] and i["sbuffer_ready"][lane]):continue
            pos=next(pos for pos,s in stores.items() if s["fire"] is None)
            s=stores[pos]
            a=s["address"]
            assert s.get("s2") and s["order"]<order and not pre[p+"bits_wline"] and pre[p+"bits_mask"]==255
            assert (pre[p+"bits_addr"],pre[p+"bits_vaddr"])==(a["paddr"],a["vaddr"])
            assert pre[p+"bits_data"]&((1<<64)-1)==s["data"]&((1<<64)-1)
            s["fire"]=tick
            counts["actual_original_Sbuffer_fire"]+=1
        delta=(pointer(post,"io_sqDeqPtr_")-head)%256
        assert delta<=2 and post["io_toLsqEnqCtrl_sqDeq_valid"]==int(bool(delta))
        if delta:assert post["io_toLsqEnqCtrl_sqDeq_bits"]==delta
        for pos in range(head,head+delta):
            s=stores[pos]
            assert s["fire"] is not None and s["fire"]+2==tick and not s["complete"]
            s["complete"]=tick
            counts["completed_original_Store"]+=1
        head+=delta
        if post["io_toLsqEnqCtrl_lqDeq_valid"]:
            assert load and load["sent"] and not load["complete"] and post["io_toLsqEnqCtrl_lqDeq_bits"]==1
            load["complete"]=tick
            counts["completed_original_Load"]+=1
        if "error" in row:
            assert failed and st==128 and not row["checked"] and "outside documented SQ age domain" in row["error"]
            terminal=dict(tick=tick,error=row["error"],exclusive_boundary=128,real_before_head=head)
        previous=row
    assert st in(127,128) and load
    if failed:
        assert terminal and not queries and head==0 and not counts["actual_original_Sbuffer_fire"]
    else:
        assert terminal is None and len(queries)==1 and head==st and all(s["complete"] for s in stores.values()) and load["complete"]
        assert previous["after"]["io_lqEmpty"] and previous["after"]["io_sqEmpty"] and load["slot"] is load["grant"] is None
        strict=int(queries[0]["strict"])
        assert counts["strict_original_replay_allocation"]==counts["actual_original_replay_grant"]==counts["original_replay_slot_feedback"]==strict
    return dict(counts=dict(counts),virtual_Store_count=st,queries=queries,old_reference_exception=terminal,
                allocated_original_UIDs=st+1,completed_original_UIDs=counts["completed_original_Store"]+counts["completed_original_Load"])


def audit(name):
    assert name=="lsq-normal-cbo-02"
    run,old=ROOT/"results"/name,ROOT/"results/lsq-sq-endpoint-01"
    manifest,source,nodes=verify_common(run)
    old_manifest,_,old_nodes=verify_common(old)
    assert old_manifest["tests"]=={"PASS":6,"FAIL":6}
    paths,prior=paths_by_node(run),paths_by_node(old)
    cases,counts=[],Counter()
    for node,path in sorted(paths.items()):
        if "test_sq_age_endpoint.py::" not in node:continue
        assert not nodes[node]
        result=inspect(path)
        result["before_correction"]=inspect(prior[node],old_nodes[node])
        prefix=0
        for a,b in itertools.zip_longest(events(prior[node]),events(path)):
            if a is None:break
            assert b is not None and all(a[k]==b[k] for k in RAW)
            prefix+=1
        assert prefix==result["before_correction"]["counts"]["raw_records"]
        if not old_nodes[node]:assert prefix==result["counts"]["raw_records"]
        cases.append(dict(nodeid=node,journal=str(path.relative_to(run)),sha256=sha(path),old_actual_prefix_identical_records=prefix,**result))
        counts.update(result["counts"])
    assert len(cases)==12 and sum(c["allocated_original_UIDs"] for c in cases)==sum(c["completed_original_UIDs"] for c in cases)==1542
    assert counts["actual_original_Sbuffer_fire"]==1530 and counts["completed_original_Load"]==12 and counts["original_replay_slot_feedback"]==6
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    for file in (Path(__file__),ROOT/"tools/check_sq_endpoint_reference_v1.py"):
        target=dest/file.name
        if target.exists():assert sha(file)==sha(target)
        else:shutil.copy2(file,target)
    report=dict(run=name,status="twelve_native127_128_endpoint_original_effects_and_old_actual_prefixes_audited",cases=cases,
                snapshot_files=len(source),counts=dict(counts),allocated_and_completed_original_UIDs=1542,auditor_sha256=sha(dest/Path(__file__).name),
                static_single_operator_scope_report_sha256=sha(ROOT/"results/static/sq-endpoint-reference-v1/report.json"),
                limits="Source-backed anchored full128 end admitted, not129. Six old127 controls retain complete actual raw histories; six old128 ValueError histories retain actual prefixes and now continue to real completion. All1530 original Store fragments and12 original Loads finish; six strict Loads have actual Replay grant/original-slot feedback. No model/actor/private oracle or known-issue filtering. This disjoint directed condition is not full-domain random/STRESS or whole Backend/ISA acceptance.")
    out=run/"sq-endpoint-audit-v1.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="cases"},indent=2,ensure_ascii=False))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("name")
    audit(p.parse_args().name)
