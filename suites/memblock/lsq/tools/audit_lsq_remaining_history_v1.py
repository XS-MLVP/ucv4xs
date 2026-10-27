#!/usr/bin/env python3
"""297-case gate: independent public-history replay of the44 gap-driven cases.

No DUT reference/actor imports, no change/outcome/known-issues oracle. Original
UID, grant, slot reuse, bus response, PA byte and completion ledgers are separate.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_lsq_bus_v2 import pointer,rob,rob_matches,sq
from audit_lsq_memory_v1 import lq,raw_payload,words
from audit_lsq_population_v1 import events,paths_by_node,replay_metadata,same_raw,validate_row
from audit_lsq_recovery_history_v1 import inspect as inspect_uncache
from audit_sq_initial import ROOT,sha,verify_common


def check_journal(path):
    previous=None
    for row in events(path):
        validate_row(row,previous,False)
        assert row["checked"]
        previous=row


def inspect_memory(path):
    stores,loads,by_sq,by_lq,slots,raw_pool,jobs=[],[],{},{},{},[],[]
    stail=ltail=shead=sequence=0
    pending_s2,previous,recovery=[],None,None
    counts,alignments,recycled,forwards=Counter(),[],[],[]
    address_wakes=set()
    mode="raw" if "high_raw_select" in next(events(path))["nodeid"] else "strict" if "three_simultaneous_ma" in next(events(path))["nodeid"] else "return"

    def live(item):
        return not item["complete"] and not item["cancelled"]

    def killed(item,red):
        delta=(rob(item["rob"])-rob(red["rob"]))%640
        assert delta!=320
        return red["valid"] and (0<delta<320 or red["flush_self"] and delta==0)

    for row in events(path):
        validate_row(row,previous,False)
        assert row["checked"]
        inp,pre,post,tick=row["input"],row["before"],row["after"],row["post_tick"]
        counts["raw_records"]+=1
        assert not pre["io_uncache_req_valid"] and not pre["io_mmioStout_valid"] and not pre["io_cmoOpReq_valid"]
        if inp["reset"]:
            assert not stores and not loads
            previous=row
            continue
        assert pointer(pre,"io_sqDeqPtr_")==shead%256
        for item in stores+loads:
            if live(item) and rob(item["rob"])<rob(inp["pending"]):
                assert item["sent"] if item["kind"]=="load" else item.get("s2_done") and "data" in item
        for d in inp["dispatch"]:
            if not d["valid"]:
                continue
            assert recovery is None and not inp["redirect"]["valid"] and 0<d["flows"]<=16
            assert not pre["io_toLsqEnqCtrl_lqRecoverStall"] and not pre["io_toLsqEnqCtrl_sqRecoverStall"]
            if d["need_alloc"]==2:
                for pos in range(stail,stail+d["flows"]):
                    sequence+=1
                    item=dict(uid=sequence,kind="store",position=pos,rob=d["rob"],complete=False,cancelled=False,consumed=set())
                    stores.append(item)
                    by_sq[pos]=item
                stail+=d["flows"]
                assert sq(d["store_end"])==stail%256 and stail-shead<=128
            else:
                assert d["need_alloc"]==1 and d["flows"]==1 and lq(d["load_start"])==ltail%240
                assert ltail%240 not in by_lq or not live(by_lq[ltail%240])
                sequence+=1
                item=dict(uid=sequence,kind="load",position=ltail,rob=d["rob"],sent=False,complete=False,cancelled=False,grant=None)
                loads.append(item)
                by_lq[ltail%240]=item
                ltail+=1
                assert sum(live(item) for item in loads)<=120
        for item,lane,last in pending_s2:
            attr=inp["attributes"][lane]
            assert attr["last"]==last and attr["memory"] and not attr["nc"] and not attr["mmio"] and not attr["exception"]
            item["s2_done"]=last
        pending_s2=[]
        # Raw candidates are an OLD allocated snapshot. The parent's natural
        # ready pointer may reclaim on this edge but does not suppress this
        # same-edge original Store selection; actual redirect does suppress it.
        candidates=list(raw_pool)
        for lane,address in enumerate(inp["addresses"]):
            if not address["valid"]:
                continue
            pos=shead+(address["slot"]-shead)%64
            item=by_sq[pos]
            assert live(item) and item["rob"]==address["rob"] and not address["tlb_miss"] and not address["cross_word"]
            assert "address" not in item
            item["address"]=address
            pending_s2.append((item,lane,address["last"]))
            eligible=[entry for entry in candidates if not killed(entry["owner"],inp["redirect"]) and entry["query"]["data_valid"] and
                      rob(entry["owner"]["rob"])>rob(address["rob"]) and
                      ((entry["query"]["paddr"]^address["paddr"])&((1<<28)-1))>>4==0 and entry["query"]["mask"]&address["mask"]]
            winner=min(eligible,key=lambda entry:rob(entry["owner"]["rob"]),default=None)
            jobs.append(dict(due=tick+4,lane=lane,address=address,winner=winner,cancelled=False))
        for data in inp["data"]:
            if data["valid"]:
                item=by_sq[sq(data["sq"])]
                assert live(item) and "data" not in item
                item["data"]=data["data"]
        for wake in inp["address_wakeups"]:
            if wake["valid"]:
                pos=sq(wake["sq"])
                assert pos in by_sq and "address" in by_sq[pos]
                address_wakes.add(pos)
        for lane,q in enumerate(inp["raw_queries"]):
            if not q["valid"]:
                continue
            found=[item for item in loads if live(item) and item["rob"]==q["rob"]]
            assert len(found)==1 and pre[f"io_ldu_rawNukeQuery_{lane}_req_ready"]
            item=found[0]
            assert sq(q["sq"])==56 and 0<(56-pointer(pre,"io_issuePtrExt_"))%256<128
            assert q["data_valid"] and q["mask"]==255
            raw_pool.append(dict(owner=item,query=q))
            item["raw_query"]=q
            counts["actual_original_raw_queries_accepted"]+=1
        for packet in inp["loads"]:
            q=packet["execution"]
            if not q["valid"]:
                continue
            item=by_lq[lq(q["uop"]["lq"])]
            assert live(item) and item["rob"]==q["uop"]["rob"] and packet["fullva"]==q["vaddr"] and packet["paddr"]%4096==q["vaddr"]%4096
            if q["replay_feedback"]:
                assert item["grant"]==q["slot"] and slots[q["slot"]] is item and not q["need_replay"] and not q["causes"]
                assert item["packet"]["execution"]["uop"]==q["uop"]
                del slots[q["slot"]]
                counts["actual_original_slot_feedbacks"]+=1
            else:
                assert "packet" not in item
                item["packet"]=packet
                if "raw_query" in item:
                    assert item["raw_query"]["paddr"]==packet["paddr"] and item["raw_query"]["ftq"]==q["uop"]["ftq"]
            if not q["need_replay"]:
                assert packet["update_address"] and not item["sent"]
                item["sent"]=True
        for bank in range(3):
            p=f"io_replay_{bank}_"
            if pre[p+"valid"] and inp["replay_ready"][bank]:
                item=by_lq[120*pre[p+"bits_uop_lqIdx_flag"]+pre[p+"bits_uop_lqIdx_value"]]
                assert live(item) and item["grant"] is None and item["packet"]["execution"]["need_replay"]
                replay_metadata(pre,p+"bits_",item["packet"])
                slot=pre[p+"bits_replayQueueIdx"]
                assert slot not in slots and slot%3==bank and slot<120
                slots[slot]=item
                item.update(grant=slot,grant_tick=tick)
                counts["actual_original_replay_grants"]+=1
            if post[p+"valid"] and mode=="strict":
                item=by_lq[120*post[p+"bits_uop_lqIdx_flag"]+post[p+"bits_uop_lqIdx_value"]]
                q=item["packet"]["execution"]
                if q["causes"]==4:
                    assert q["uop"]["strict"] and (7 in address_wakes or 0<(pointer(post,"io_issuePtrExt_")-7)%256<128)
                    replay_metadata(post,p+"bits_",item["packet"])
        if previous is not None:
            for lane,query in enumerate(previous["input"]["queries"]):
                if not query["valid"]:
                    continue
                trans,p=inp["translations"][lane],f"io_forward_{lane}_s2Resp_"
                assert not trans["kill"] and post[p+"valid"] and not any(post[p+"bits_"+key] for key in ("forwardInvalid","matchInvalid","addrInvalid_valid","dataInvalid_valid"))
                assert query["vaddr"]%4096==trans["paddr"]%4096
                bank=[item for item in stores if live(item) and item.get("s2_done") and item["position"]<sq(query["sq"])]
                data={}
                for item in bank:
                    for _,pa,mask,value in words(item):
                        for byte in range(16):
                            if mask>>byte&1:
                                data[pa+byte]=(item["uid"],value>>(8*byte)&255)
                length=1<<query["size"]
                for byte in range(16):
                    expected=query["vaddr"]%16<=byte<query["vaddr"]%16+length
                    assert post[p+f"bits_forwardMask_{byte}"]==int(expected)
                    if expected:
                        address=trans["paddr"]//16*16+byte
                        assert address in data and post[p+f"bits_forwardData_{byte}"]==data[address][1]
                forwards.append(dict(vaddr=query["vaddr"],paddr=trans["paddr"],tick=tick))
                counts["actual_replacement_load_forward_original_pa_byte_checks"]+=1
        if inp["redirect"]["valid"]:
            assert recovery is None and not any(d["valid"] for d in inp["dispatch"])
            victims=[item for item in loads if live(item) and killed(item,inp["redirect"])]
            assert victims and not any(killed(item,inp["redirect"]) for item in stores if live(item))
            before_slots={item["grant"] for item in victims if item["grant"] is not None}
            for item in victims:
                item["cancelled"]=True
                item["cancel_tick"]=tick
                if item["grant"] is not None:
                    assert slots.pop(item["grant"]) is item
            if mode=="return":
                assert len(before_slots)==len(victims) and len(before_slots)+len(slots)==120
                recycled.append(dict(tick=tick,cancelled_slots=sorted(before_slots),victim_uids=[item["uid"] for item in victims],surviving_slots=sorted(slots)))
            recovery=dict(expected_lq=min(item["position"] for item in victims),expected_sq=stail,lq=None,sq=None)
            counts["actual_shared_redirects"]+=1
        for job in jobs:
            if job["winner"] is not None and killed(job["winner"]["owner"],inp["redirect"]):
                job["cancelled"]=True
        emitted=[job for job in jobs if job["due"]==tick]
        jobs=[job for job in jobs if job["due"]>tick]
        valid=[job for job in emitted if job["winner"] is not None and not job["cancelled"]]
        for lane in range(2):
            match=next((job for job in valid if job["lane"]==lane),None)
            p=f"io_nuke_rollback_{lane}_"
            assert post[p+"valid"]==int(match is not None)
            if match:
                raw_payload(post,p+"bits_",match["winner"]["query"],match["address"])
                counts["actual_original_complete_raw_rollback_payloads"]+=1
        winner=min(valid,key=lambda job:(rob(job["winner"]["owner"]["rob"]),job["lane"]),default=None)
        assert post["io_mdpTrain_valid"]==int(winner is not None)
        if winner:
            q,a=winner["winner"]["query"],winner["address"]
            expected=dict(ftqIdx_value=q["ftq"]["value"],ftqOffset=q["ftq_offset"],isRVC=int(q["is_rvc"]),
                          stFtqIdx_value=a["ftq"]["value"],stFtqOffset=a["ftq_offset"],stIsRVC=int(a["rvc"]))
            assert all(post["io_mdpTrain_bits_"+key]==value for key,value in expected.items())
        raw_pool=[entry for entry in raw_pool if not entry["owner"]["cancelled"] and 0<(sq(entry["query"]["sq"])-pointer(pre,"io_issuePtrExt_"))%256<128]
        if recovery is not None:
            if post["io_toLsqEnqCtrl_lqRedirectPtr_valid"]:
                recovery["lq"]=120*post["io_toLsqEnqCtrl_lqRedirectPtr_bits_flag"]+post["io_toLsqEnqCtrl_lqRedirectPtr_bits_value"]
                assert recovery["lq"]==recovery["expected_lq"]%240
                ltail=recovery["expected_lq"]
            if post["io_toLsqEnqCtrl_sqRedirectPtr_valid"]:
                recovery["sq"]=pointer(post,"io_toLsqEnqCtrl_sqRedirectPtr_bits_")
                assert recovery["sq"]==stail%256
            if recovery["sq"] is not None and recovery["lq"] is not None and not post["io_toLsqEnqCtrl_lqRecoverStall"] and not post["io_toLsqEnqCtrl_sqRecoverStall"]:
                recovery=None
        for lane in range(2):
            p=f"io_sbuffer_req_{lane}_"
            if pre[p+"valid"] and inp["sbuffer_ready"][lane]:
                item=next(item for item in stores if live(item) and not item["consumed"])
                va,pa,mask,value=words(item)[0]
                assert item.get("s2_done") and rob(item["rob"])<=rob(inp["pending"])
                assert pre[p+"bits_vaddr"]==va and pre[p+"bits_addr"]==pa and pre[p+"bits_mask"]==mask and not pre[p+"bits_wline"]
                bits=sum(255<<(8*byte) for byte in range(16) if mask>>byte&1)
                assert not ((pre[p+"bits_data"]^value)&bits)
                item.update(consumed={0},last_fire=tick)
                counts["actual_original_store_byte_fragments"]+=1
        delta=(pointer(post,"io_sqDeqPtr_")-shead)%256
        assert delta<=2 and post["io_toLsqEnqCtrl_sqDeq_valid"]==int(bool(delta))
        if delta:
            assert post["io_toLsqEnqCtrl_sqDeq_bits"]==delta
        for pos in range(shead,shead+delta):
            item=by_sq[pos]
            assert item["consumed"]=={0} and item["last_fire"]+2==tick and not item["complete"]
            item["complete"]=True
        shead+=delta
        if post["io_toLsqEnqCtrl_lqDeq_valid"]:
            count=post["io_toLsqEnqCtrl_lqDeq_bits"]
            active=[item for item in loads if live(item)]
            assert 0<count<=len(active)
            for item in active[:count]:
                assert item["sent"]
                item["complete"]=True
        previous=row
    assert not slots and not jobs and recovery is None and not raw_pool
    assert all(item["complete"] for item in stores) and all(item["complete"] or item["cancelled"] for item in loads)
    assert previous["after"]["io_lqEmpty"] and previous["after"]["io_sqEmpty"] and not previous["after"]["io_replayAllocate"]
    for item in loads:
        if item["cancelled"]:
            assert any(new["uid"]>item["uid"] and new["position"]%120==item["position"]%120 and new["complete"] for new in loads)
            counts["cancelled_same_lq_physical_slot_new_uid_completed"]+=1
    for return_event in recycled:
        replacements=[item for item in loads if item.get("grant_tick",0)>return_event["tick"] and not item["cancelled"]]
        assert {item["grant"] for item in replacements}==set(return_event["cancelled_slots"])
        assert all(item["complete"] for item in replacements)
        counts["actual_cancelled_replay_slots_exclusively_regranted_completed"]+=len(replacements)
    for query in forwards:
        owners=[item for item in loads if not item["cancelled"] and item["packet"]["execution"]["vaddr"]==query["vaddr"] and item["packet"]["paddr"]==query["paddr"]]
        assert len(owners)==1 and owners[0]["complete"]
    if mode=="strict":
        main=[item for item in loads if item["packet"]["execution"]["causes"]==4]
        assert len(main)==120 and {item["grant"] for item in main}==set(range(120))
        assert all(item["packet"]["execution"]["uop"]["strict"] for item in main) and 7 in address_wakes
        for first in range(0,len(main),3):
            assert len({item["packet"]["execution"]["uop"]["lq"]["value"] for item in main[first:first+3]})==3
        counts["all_120_original_three_ma_strict_owners_granted_feedback_completed"]+=1
    if mode=="raw":
        assert counts["actual_original_raw_queries_accepted"]==56 and len(forwards)==sum(item["cancelled"] for item in loads)
        assert counts["actual_original_complete_raw_rollback_payloads"]>0
    return dict(allocated=len(stores)+len(loads),completed=sum(item["complete"] for item in stores+loads),cancelled=sum(item["cancelled"] for item in loads),
                counts=dict(counts),exclusive_slot_reuse_witnesses=recycled)


def inspect_cbo(path):
    stores,loads,by_sq,by_lq=[],[],{},{}
    stail=ltail=head=sequence=0
    pending_s2,cache,previous=[],None,None
    anchor=None
    visits,encodings,counts=set(),set(),Counter()

    def order(ptr,observe=False):
        nonlocal anchor
        code=rob(ptr)
        if anchor is not None:
            base=anchor//640*640+code
            choices=(base-640,base,base+640)
            code=min(choices,key=lambda n:abs(n-anchor))
            assert abs(code-anchor)<320
        if observe:
            anchor=code if anchor is None else max(anchor,code)
        return code

    for row in events(path):
        validate_row(row,previous,False)
        assert row["checked"]
        inp,pre,post,tick=row["input"],row["before"],row["after"],row["post_tick"]
        counts["raw_records"]+=1
        assert not inp["redirect"]["valid"] and not pre["io_uncache_req_valid"]
        if inp["reset"]:
            assert not stores and not loads
            previous=row
            continue
        assert pointer(pre,"io_sqDeqPtr_")==head%256
        for d in inp["dispatch"]:
            if not d["valid"]:
                continue
            assert d["flows"]==1 and not pre["io_toLsqEnqCtrl_sqRecoverStall"]
            sequence+=1
            item=dict(uid=sequence,rob=d["rob"],order=order(d["rob"],True),complete=False)
            if d["need_alloc"]==2:
                assert stail not in by_sq
                item.update(position=stail,consumed=False,wb=None)
                stores.append(item)
                by_sq[stail]=item
                stail+=1
                assert sq(d["store_end"])==stail%256
            else:
                assert d["need_alloc"]==1 and lq(d["load_start"])==ltail%240
                item.update(position=ltail,sent=False)
                loads.append(item)
                by_lq[ltail%240]=item
                ltail+=1
        for item,lane in pending_s2:
            attr=inp["attributes"][lane]
            assert attr["memory"] and attr["last"] and not attr["exception"] and not attr["nc"] and not attr["mmio"]
            item["s2_done"]=True
        pending_s2=[]
        for lane,address in enumerate(inp["addresses"]):
            if address["valid"]:
                item=by_sq[head+(address["slot"]-head)%64]
                assert item["rob"]==address["rob"] and not item["complete"] and "address" not in item
                assert address["last"] and not address["tlb_miss"] and not address["cross_word"] and address["fu_op"]&1
                item.update(address=address,cbo=address["fu_op"]>>1&7,sta_lane=lane)
                pending_s2.append((item,lane))
                encodings.add(item["position"]%256)
        for data in inp["data"]:
            if data["valid"]:
                item=by_sq[head+(sq(data["sq"])-head)%256]
                assert data["fu_op"]==item["address"]["fu_op"] and "data" not in item
                item["data"]=data["data"]
        for packet in inp["loads"]:
            q=packet["execution"]
            if q["valid"]:
                item=by_lq[lq(q["uop"]["lq"])]
                assert item["rob"]==q["uop"]["rob"] and not item["sent"] and not q["need_replay"] and packet["update_address"]
                item["sent"]=True
        if pre["io_cmoOpReq_valid"] and inp["cache_ready"]:
            item=next(item for item in stores if not item["complete"])
            assert item.get("s2_done") and "data" in item and cache is None and item["cbo"]!=3 and item["rob"]==inp["pending"]
            assert pre["io_cmoOpReq_bits_address"]==item["address"]["paddr"] and pre["io_cmoOpReq_bits_opcode"]==item["cbo"]
            item["cache_req"]=tick
            cache=item
            counts["actual_original_cbo_cache_requests"]+=1
        if inp["cache_response"]:
            assert pre["io_cmoOpResp_ready"] and cache is not None and not inp["cache_denied"] and not inp["cache_corrupt"]
            cache["cache_response"]=tick
            cache=None
            counts["actual_original_cbo_cache_responses"]+=1
        for lane in range(2):
            p=f"io_sbuffer_req_{lane}_"
            if pre[p+"valid"] and inp["sbuffer_ready"][lane]:
                item=next(item for item in stores if not item["complete"])
                assert item["cbo"]==3 and not item["consumed"] and item.get("s2_done") and "data" in item
                va,pa,mask,value=words({**item,"data":0})[0]
                assert pre[p+"bits_vaddr"]==va and pre[p+"bits_addr"]==pa and pre[p+"bits_mask"]==mask and pre[p+"bits_wline"]
                bits=sum(255<<(8*b) for b in range(16) if mask>>b&1)
                assert not pre[p+"bits_data"]&bits
                item["consumed"]=True
                item["zero_fire"]=tick
                counts["actual_original_zero_owner_byte_fires"]+=1
        if pre["io_mmioStout_valid"]:
            item=next(item for item in stores if not item["complete"])
            assert item["rob"]==inp["pending"]
            rob_matches(pre,"io_mmioStout_bits_robIdx_",item["rob"])
            assert pre["io_stExceptionInfo_valid"] and pre["io_stExceptionInfo_bits_vaddr"]==item["address"]["vaddr"]
            assert pre["io_stExceptionInfo_bits_isHyper"]==int(item["address"]["hyper"])
            assert not pre["io_mmioStout_bits_exceptionVec_7"] and not pre["io_mmioStout_bits_exceptionVec_19"]
            if inp["writeback_ready"]:
                assert item["wb"] is None
                assert item["consumed"] if item["cbo"]==3 else item.get("cache_response") is not None
                item["wb"]=tick
                counts["actual_original_cbo_wb_fires"]+=1
        delta=(pointer(post,"io_sqDeqPtr_")-head)%256
        assert delta<=1 and post["io_toLsqEnqCtrl_sqDeq_valid"]==int(bool(delta))
        if delta:
            item=by_sq[head]
            assert item["wb"] is not None and item["wb"]<tick and not item["complete"]
            item["complete"]=True
            visits.add((item["position"]%64,item["cbo"],item["sta_lane"]))
        head+=delta
        if post["io_toLsqEnqCtrl_lqDeq_valid"]:
            count=post["io_toLsqEnqCtrl_lqDeq_bits"]
            active=[item for item in loads if not item["complete"]]
            assert 0<count<=len(active)
            for item in active[:count]:
                assert item["sent"]
                item["complete"]=True
        pending_order=order(inp["pending"])
        assert all(item["wb"] is not None for item in stores if item["order"]<pending_order)
        assert all(item["sent"] for item in loads if item["order"]<pending_order)
        previous=row
    assert len(stores)==len(loads)==256 and all(item["complete"] for item in stores+loads) and cache is None
    assert encodings==set(range(256)) and len(visits)==256
    assert counts["actual_original_cbo_cache_requests"]==counts["actual_original_cbo_cache_responses"]==192
    assert counts["actual_original_zero_owner_byte_fires"]==64 and counts["actual_original_cbo_wb_fires"]==256
    assert previous["after"]["io_sqEmpty"] and previous["after"]["io_lqEmpty"]
    return dict(allocated=512,completed=512,cancelled=0,counts=dict(counts),completed_slot_cbo_sta_witnesses=sorted(visits),actual_complete_sq_encodings=sorted(encodings))


def audit(name):
    assert name=="lsq-expanded-14", "exact297-case scope; add a version for later ranges"
    run,prior=ROOT/"results"/name,ROOT/"results/lsq-expanded-13"
    manifest,source,nodes=verify_common(run)
    old,_,old_nodes=verify_common(prior)
    assert manifest["tests"]=={"PASS":260,"FAIL":37} and len(nodes)==297
    assert old["tests"]=={"PASS":216,"FAIL":37} and len(old_nodes)==253
    paths,old_paths=paths_by_node(run),paths_by_node(prior)
    assert set(paths)==set(nodes) and set(old_paths)==set(old_nodes)<=set(nodes)
    counts,cases,visits=Counter(),[],set()
    for node,path in sorted(paths.items()):
        if node in old_nodes:
            assert nodes[node]==old_nodes[node]
            records=same_raw(path,old_paths[node])
            detail=dict(previous253_all_raw_samples_unchanged=records)
            counts["previous253_all_raw_case_histories_unchanged"]+=1
        else:
            assert not nodes[node] and node.startswith("tests/lsq_wrapper/test_remaining_paths.py::")
            check_journal(path)
            if "each_physical_slot_all_cbo" in node:
                detail=inspect_cbo(path)
                visits.update(tuple(item) for item in detail["completed_slot_cbo_sta_witnesses"])
            elif "uncache" in node or "entry_zero_cancel" in node:
                detail=inspect_uncache(path)
                assert detail["reset_aborted"]==0
            else:
                detail=inspect_memory(path)
            for key in ("allocated","completed","cancelled"):
                counts["new_"+key]+=detail[key]
            counts.update(detail["counts"])
            counts["new_cases"]+=1
            records=detail["counts"]["raw_records"]
        counts["all_continuous_raw_records"]+=records
        cases.append(dict(nodeid=node,journal=str(path.relative_to(run)),sha256=sha(path),result="FAIL" if nodes[node] else "PASS",**detail))
    assert counts["previous253_all_raw_case_histories_unchanged"]==253 and counts["new_cases"]==44
    assert counts["new_allocated"]==7264 and counts["new_completed"]==5120 and counts["new_cancelled"]==2144
    assert visits=={(slot,cbo,lane) for slot in range(64) for cbo in range(4) for lane in range(2)}
    direct=ROOT/"results/lsq-remaining-paths-01"
    alignment=ROOT/"results/lsq-return-alignment-01"
    for directory in (direct,alignment,ROOT/"results/lsq-uncache-return-tail-01"):
        verify_common(directory)
        for node,path in paths_by_node(directory).items():
            same_raw(path,paths[node])
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    files=(Path(__file__),ROOT/"tools/audit_lsq_recovery_history_v1.py",ROOT/"tools/audit_lsq_population_v1.py",ROOT/"tools/audit_lsq_memory_v1.py",ROOT/"tools/audit_lsq_bus_v2.py",ROOT/"tools/audit_lsq_bus_v3.py")
    for file in files:
        target=dest/file.name
        if target.exists():
            assert sha(target)==sha(file)
        else:
            shutil.copy2(file,target)
    report=dict(run=name,status="NOT_PASS_297_case_remaining_paths_original_uid_and_bytes_audited",tests=manifest["tests"],snapshot_files=len(source),
                counts=dict(counts),all_512_slot_cbo_sta_completed_witnesses=len(visits),previous253_audit_sha256=sha(prior/"recovery-history-audit-v2.json"),
                auditors={file.name:sha(dest/file.name) for file in files},cases=cases,
                limits="Exact297 scope: all253 prior raw inputs/pre/post/ticks and37FAIL/16 explicitly protocol-only probes unchanged. New44 strict cases:3MA120x3alignment with real SQ7/second wake, partial issued full Replay recycle only cancelled original slots, actual Uncache prefix/suffix bus returns, high RAW Store selection/MDP/actual shared redirect/new UID PA forwarding, and512 original CBO owners actual Cache/zero/WB/SQ completion+512 real Load completions. No private slots/state or expected/change/issue oracle. Directed capacity/property coverage is not full legal mixed seeded stress/fair-drain acceptance, arbitrary-parameter/fresh elaboration or Backend/ISA signoff.")
    output=run/"remaining-history-audit-v1.json"
    if output.exists():
        assert json.loads(output.read_text())==report
    else:
        output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({key:value for key,value in report.items() if key!="cases"},indent=2,ensure_ascii=False))


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
