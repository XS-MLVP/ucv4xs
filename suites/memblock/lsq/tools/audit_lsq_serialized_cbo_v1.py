#!/usr/bin/env python3
"""Serialized CBO normal producer plus real original WB/zero effects."""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_lsq_bus_v2 import pointer, rob, rob_matches, sq
from audit_lsq_cbo_serialization_v2 import inspect as serialization
from audit_lsq_normal_cbo_v3 import packages
from audit_lsq_population_v1 import events, paths_by_node, validate_row
from audit_lsq_remaining_history_v1 import inspect_cbo
from audit_sq_initial import ROOT, sha, verify_common


def effects(path):
    rows=events(path)
    node=next(events(path))["nodeid"]
    fault="actual_fault_WB" in node
    probe="protocol_only" in node or fault
    stores={}
    tail=head=0
    s2=[]
    cache=response=previous=None
    wbs,fires,releases=[],[],[]
    flush=[]
    for row in rows:
        validate_row(row,previous,probe)
        i,pre,post,tick=row["input"],row["before"],row["after"],row["post_tick"]
        assert not i["redirect"]["valid"] and not pre["io_uncache_req_valid"] and not any(p["execution"]["valid"] for p in i["loads"])
        if i["reset"]:
            assert not stores
            previous=row
            continue
        assert pointer(pre,"io_sqDeqPtr_")==head
        for s in stores.values():
            if rob(s["rob"])<rob(i["pending"]):assert s.get("s2") and "data" in s, "normal ROB cannot pass unexecuted Store"
        for d in i["dispatch"]:
            if not d["valid"]:continue
            assert d["need_alloc"]==2 and d["flows"]==1 and tail not in stores
            stores[tail]=dict(position=tail,rob=d["rob"],fires=[],released=False)
            tail+=1
            assert sq(d["store_end"])==tail
        for s,lane in s2:
            a=i["attributes"][lane]
            assert a["memory"] and a["last"] and not(a["mmio"] or a["nc"] or a["exception"])
            s["s2"]=tick
        s2=[]
        for lane,a in enumerate(i["addresses"]):
            if not a["valid"]:continue
            s=stores[head+(a["slot"]-head)%64]
            assert s["rob"]==a["rob"] and "address" not in s and not a["tlb_miss"] and a["last"]
            s["address"]=a
            s["cbo"]=(a["fu_op"]>>1&7) if a["fu_op"]&1 else None
            s2.append((s,lane))
        for d in i["data"]:
            if d["valid"]:
                s=stores[sq(d["sq"])]
                assert "data" not in s and d["fu_op"]==s["address"]["fu_op"]
                s["data"]=d["data"]
        if pre["io_cmoOpReq_valid"] and i["cache_ready"]:
            assert fault and cache is None
            s=next(s for s in stores.values() if s.get("cbo") is not None)
            assert s["rob"]==i["pending"] and s.get("s2") and "data" in s
            assert pre["io_cmoOpReq_bits_opcode"]==s["cbo"] and pre["io_cmoOpReq_bits_address"]==s["address"]["paddr"]
            cache=dict(owner=s,tick=tick)
        if i["cache_response"]:
            assert cache is not None and response is None and pre["io_cmoOpResp_ready"]
            response=dict(denied=int(i["cache_denied"]),corrupt=int(i["cache_corrupt"]),tick=tick,owner=cache["owner"])
        for lane in range(2):
            p=f"io_sbuffer_req_{lane}_"
            if not(pre[p+"valid"] and i["sbuffer_ready"][lane]):continue
            s=next(s for s in stores.values() if s.get("address",{}).get("paddr")==pre[p+"bits_addr"])
            a=s["address"]
            assert not s["fires"] and s.get("s2") and "data" in s
            iszero=s["cbo"]==3
            assert pre[p+"bits_vaddr"]==a["vaddr"] and pre[p+"bits_mask"]==(65535 if iszero else 255) and pre[p+"bits_wline"]==int(iszero)
            bits=(1<<(128 if iszero else 64))-1
            assert pre[p+"bits_data"]&bits==(0 if iszero else s["data"]&bits)
            fire=dict(tick=tick,position=s["position"],cbo=s["cbo"],zero16=iszero)
            s["fires"].append(fire)
            fires.append(fire)
        if pre["io_mmioStout_valid"] and i["writeback_ready"]:
            s=next(s for s in stores.values() if s.get("cbo") is not None)
            assert s["rob"]==i["pending"] and not wbs
            rob_matches(pre,"io_mmioStout_bits_robIdx_",s["rob"])
            wbs.append(dict(tick=tick,position=s["position"],denied=pre["io_mmioStout_bits_exceptionVec_7"],corrupt=pre["io_mmioStout_bits_exceptionVec_19"],
                            original_zero16_before_WB=sum(f["zero16"] for f in s["fires"])))
        delta=(pointer(post,"io_sqDeqPtr_")-head)%256
        assert delta<=2
        for pos in range(head,head+delta):
            s=stores[pos]
            assert not s["released"]
            s["released"]=tick
            releases.append(dict(tick=tick,position=pos,own_actual_fires=len(s["fires"]),cbo=s["cbo"]))
        head+=delta
        if pre["io_flushSbuffer_valid"]!=post["io_flushSbuffer_valid"]:
            flush.append(dict(tick=tick,before=pre["io_flushSbuffer_valid"],after=post["io_flushSbuffer_valid"]))
        previous=row
    violation=None
    if fault:
        assert cache and response and len(wbs)==1
        want={k:response[k] for k in("denied","corrupt")}
        actual={k:wbs[0][k] for k in want}
        if want!=actual:violation=dict(kind="normal_serialized_CBO_original_fault_lost_at_real_WB_fire",expected_from_original_response=want,actual=actual,tick=wbs[0]["tick"])
    elif wbs and wbs[0]["original_zero16_before_WB"]!=1:
        violation=dict(kind="normal_serialized_zero_real_WB_without_own_zero16",WB=wbs[0],actual_releases=releases)
    elif "error" in previous:
        assert not probe and "io_flushSbuffer_valid" in previous["error"]
        violation=dict(kind="normal_serialized_zero_strict_flush_phase_only",tick=previous["post_tick"],error=previous["error"],
                       scope="NO later zero WB/release is invented for this strict stopped prefix")
    return dict(protocol_only=probe,full_cycle_reference_compared=not probe,violation=violation,actual_WB=wbs,actual_fires=fires,
                actual_releases=releases,flush_transitions=flush,original_response=None if response is None else {k:response[k] for k in("tick","denied","corrupt")})


def audit(name):
    assert name=="lsq-serialized-cbo-01"
    run=ROOT/"results"/name
    manifest,source,nodes=verify_common(run)
    assert len(nodes)==12
    paths=paths_by_node(run)
    cases,counts,visits=[],Counter(),set()
    for node,path in sorted(paths.items()):
        legality=serialization(path)
        assert not legality["violations"], "new serialized cases must obey real NoSpec AND BlockBack"
        metadata=packages(path)
        counts.update(legality["counts"])
        counts["actual_CBO_STA_packages_bound_to_pins"]+=metadata
        if "all_physical_slots" in node:
            assert not nodes[node] and metadata==256
            detail=inspect_cbo(path)
            visits.update(tuple(v) for v in detail["completed_slot_cbo_sta_witnesses"])
            counts["clean_original_UIDs_completed"]+=detail["completed"]
        else:
            detail=effects(path)
            assert bool(detail["violation"])==nodes[node]
            counts["actual_normal_fault_WB_counterexamples"]+=bool(detail["violation"] and "fault_lost" in detail["violation"]["kind"])
            counts["actual_normal_zero_WB_counterexamples"]+=bool(detail["violation"] and "real_WB_without" in detail["violation"]["kind"])
            counts["strict_normal_zero_phase_counterexamples"]+=bool(detail["violation"] and "phase_only" in detail["violation"]["kind"])
        cases.append(dict(nodeid=node,journal=str(path.relative_to(run)),sha256=sha(path),pytest_result="FAIL" if nodes[node] else "PASS",
                          real_serialization=legality,original_effects=detail))
    assert visits=={(slot,cbo,lane) for slot in range(64) for cbo in range(4) for lane in range(2)}
    assert counts["clean_original_UIDs_completed"]==1024
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    for file in(Path(__file__),ROOT/"tools/audit_lsq_cbo_serialization_v2.py",ROOT/"tools/audit_lsq_remaining_history_v1.py"):
        target=dest/file.name
        if target.exists():assert sha(file)==sha(target)
        else:shutil.copy2(file,target)
    report=dict(run=name,status="NORMAL_SERIALIZED_CBO_METADATA_AND_NoSpec_BlockBack_AND_ORIGINAL_EFFECTS_AUDITED_RETAIN_FAILS",
                tests=manifest["tests"],snapshot_files=len(source),counts=dict(counts),completed_slot_opcode_STA_combinations=len(visits),cases=cases,
                auditor_sha256=sha(dest/Path(__file__).name),
                limits="Real source-backed NoSpec empty-ROB and BlockBack younger-admission requirements checked from original public dispatch/STA/ROB epochs, not actor names.512 clean serialized CBOs+512 younger Loads really finish; fault and zero failures retained at actual effects with independent identities. Protocol-only probes explicitly checked=false/full_cycle_reference_compared=false, strict zero phase-only failure distinct from real later protocol WB/release. Legal retired older Store can remain in Sbuffer during isolated CBO; no read==head restriction. Native RTL/Chisel unchanged. This directed scope does not finish original8 full random types/seeds, capacity/fair/recovery or final goal signoff.")
    out=run/"serialized-cbo-audit-v1.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="cases"},indent=2,ensure_ascii=False))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("name")
    audit(p.parse_args().name)
