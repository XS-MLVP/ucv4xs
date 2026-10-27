#!/usr/bin/env python3
"""Original public UID effects for the fixed-stage full-domain mixed producer.

No actor/DUT/reference state or known-issue oracle. Pipeline admission is a
separate gate: this audit never calls a returned queue credit semantic success.
"""
from collections import Counter

from audit_lsq_bus_v2 import pointer, rob_matches, sq
from audit_lsq_mixed_history_v1 import Timeline
from audit_lsq_population_v1 import events, replay_metadata, validate_row


def inspect(path, *, passed):
    rows=list(events(path))
    program,stores,loads,jobs,slots,bysq,bylq,valid=[],[],[],[],{},{},{},{}
    sh=st=lh=lt=0
    prev=None
    pending_s2=[]
    bpipe=[None]*3
    cache=rec=None
    timeline=Timeline()
    counts,causes,peaks=Counter(),Counter(),Counter()
    violations,recoveries=[],[]
    def live(s):return not s["complete"] and not s["cancelled"]
    def owner(rob,kind):
        order=timeline.decode(rob)
        found=[s for s in program if s["order"]==order and s["kind"]==kind and not s["rob_cancelled"]]
        assert len(found)==1,("original public ROB epoch",order,[s["uid"] for s in found])
        return found[0]
    def check(condition,obligation,**fields):
        if not condition:violations.append(dict(tick=tick,obligation=obligation,**fields))
    for index,row in enumerate(rows):
        validate_row(row,prev,False)
        i,pre,post,tick=row["input"],row["before"],row["after"],row["post_tick"]
        counts["raw_records"]+=1
        assert row["checked"] or index==len(rows)-1
        if i["reset"]:
            assert not program
            prev=row
            continue
        assert not i["sbuffer_ready"][1] or i["sbuffer_ready"][0]
        assert pointer(pre,"io_sqDeqPtr_")==sh%256
        head=timeline.decode(i["pending"],True)
        red=i["redirect"]
        cut=timeline.decode(red["rob"])+int(not red["flush_self"]) if red["valid"] else None
        assert cut is None or cut>=head and not any(d["valid"] for d in i["dispatch"])
        for s in program:
            if s["rob_cancelled"] or s["order"]>=head:continue
            assert not s["fault"]
            if s["kind"]=="load":assert s["sent"]
            elif s.get("memory")==1:assert s["attempts"] and s["attempts"][-1]["sid"] is not None
            elif s.get("cbo") is not None or s.get("memory",0)&2:assert s["wb"] is not None
            else:assert s.get("s2") and "data" in s
        prepared=[]
        for p in range(lh,lh+8):
            s=valid.get(p)
            if s is None or not s["sent"] or cut is not None and s["order"]>=cut:break
            prepared.append(s)
        for d in i["dispatch"]:
            if not d["valid"]:continue
            assert rec is None and not pre["io_toLsqEnqCtrl_lqRecoverStall"] and not pre["io_toLsqEnqCtrl_sqRecoverStall"] and d["flows"]==1
            order=timeline.decode(d["rob"],True)
            assert order>=head and not any(s["order"]>=order and not s["rob_cancelled"] for s in program)
            s=dict(uid=len(program)+1,order=order,rob=d["rob"],kind="load" if d["need_alloc"]==1 else "store",complete=False,
                   cancelled=False,rob_cancelled=False,fault=False,attempts=[],grant=None,consumed=set(),wb=None,sent=False,dispatch_tick=tick)
            assert d["need_alloc"] in(1,2)
            program.append(s)
            if s["kind"]=="store":
                s["pos"]=st
                assert st not in bysq or not live(bysq[st])
                bysq[st]=s
                stores.append(s)
                st+=1
                assert sq(d["store_end"])==st%256
            else:
                assert 120*int(d["load_start"]["flag"])+d["load_start"]["value"]==lt%240
                s.update(pos=lt,sq_bound=st)
                assert lt%240 not in bylq or not live(bylq[lt%240])
                bylq[lt%240]=valid[lt]=s
                loads.append(s)
                lt+=1
        for s,lane,last in pending_s2:
            a=i["attributes"][lane]
            assert a["last"]==last and not a["exception"]
            if last and live(s):s.update(s2=True,memory=int(a["nc"] or not a["memory"])+2*int(a["mmio"])+4*int(not a["memory"]))
        pending_s2=[]
        for lane,a in enumerate(i["addresses"]):
            if not a["valid"]:continue
            p=sh+(a["slot"]-sh)%64
            s=bysq[p]
            assert live(s) and s["rob"]==a["rob"] and p<min(st,sh+64) and a["vaddr"]%4096==a["paddr"]%4096
            if not a["tlb_miss"]:
                if "address" in s:assert a["cross_word"] and a["last"] and not s.get("s2")
                else:s["address"]=a
                s["cbo"]=a["fu_op"]>>1&7 if a["fu_op"]&1 else None
                pending_s2.append((s,lane,a["last"]))
        for d in i["data"]:
            if not d["valid"]:continue
            p=sh+(sq(d["sq"])-sh)%256
            s=bysq[p]
            assert live(s) and p<sh+64 and "data" not in s
            s["data"]=d["data"]
        for lane,q in enumerate(i["rar_queries"]):
            assert q["valid"]==i["raw_queries"][lane]["valid"]
            if not q["valid"]:continue
            s=owner(q["rob"],"load")
            r=i["raw_queries"][lane]
            assert live(s) and 120*int(q["lq"]["flag"])+q["lq"]["value"]==s["pos"]%240
            assert r["rob"]==q["rob"] and r["paddr"]==q["paddr"] and r["data_valid"]==q["data_valid"] and sq(r["sq"])==s["sq_bound"]%256
            if q["nc"]:assert s["attempts"][-1]["consumed"] and s["packet"]["execution"]["nc"]
            counts["original_RAR_RAW_S2_pairs"]+=1
        for packet in i["loads"]:
            q,u=packet["execution"],packet["execution"]["uop"]
            if not q["valid"]:continue
            s=bylq[120*int(u["lq"]["flag"])+u["lq"]["value"]]
            assert live(s) and s["rob"]==u["rob"] and sq(u["sq"])==s["sq_bound"]%256
            assert packet["fullva"]==q["vaddr"] and packet["paddr"]%4096==q["vaddr"]%4096
            s.setdefault("va",q["vaddr"])
            s.setdefault("pa",packet["paddr"])
            assert s["va"]==q["vaddr"] and s["pa"]==packet["paddr"]
            assert (u["operation"]>>1&7)<4 or q["vector"]
            if q["replay_feedback"]:
                assert s["grant"]==q["slot"] and slots[q["slot"]] is s
                assert {k:v for k,v in u.items() if k!="exceptions"}=={k:v for k,v in s["packet"]["execution"]["uop"].items() if k!="exceptions"}
                s["grant"]=None
                if not q["need_replay"]:del slots[q["slot"]]
                counts["original_slot_feedbacks"]+=1
                if s["packet"]["execution"]["nc"] or s["packet"]["mmio"]:
                    a=s["attempts"][-1]
                    assert a["consumed"]
                    r=a["response"]
                    assert packet["exceptions"]==int(r["error"])<<19|int(r["nderr"])<<5
                    counts["uncache_original_error_S3_propagations"]+=1
            else:
                assert "packet" not in s
                s["packet"]=packet
            if q["need_replay"]:
                assert q["causes"].bit_count()==1 and q["causes"]<1<<12
                causes[str(q["causes"].bit_length()-1)]+=1
            else:
                assert packet["update_address"] and not s["sent"]
                if s["packet"]["execution"]["causes"]==1:assert s["attempts"][-1]["consumed"]
                s["sent"]=True
            s["fault"]|=bool(packet["exceptions"])
            s["last"]=packet
        if pre["io_uncache_req_valid"] and i["bus"]["ready"]:
            kind="load" if pre["io_uncache_req_bits_cmd"]==0 else "store"
            found=[s for s in program if s["kind"]==kind and (not s["rob_cancelled"] or kind=="load") and
                   s.get("pa",s.get("address",{}).get("paddr"))==pre["io_uncache_req_bits_addr"] and
                   (int(s["rob"]["flag"]),s["rob"]["value"],int(s["rob"]["former"]))==
                   (pre["io_uncache_req_bits_robIdx_flag"],pre["io_uncache_req_bits_robIdx_value"],pre["io_uncache_req_bits_robIdx_isFormer"]) and
                   (not s["attempts"] or s["attempts"][-1]["consumed"])]
            assert len(found)==1
            s=found[0]
            if kind=="store":assert s["order"]==head and s.get("s2") and "data" in s and pre["io_uncache_req_bits_data"]==s["data"]&((1<<64)-1)
            else:assert s["last"]["execution"]["causes"]==1
            a=dict(id=len(jobs)+1,owner=s,mid=pre["io_uncache_req_bits_id"],sid=None,response=None,consumed=False,request_tick=tick)
            jobs.append(a)
            s["attempts"].append(a)
            counts[kind+"_bus_fires"]+=1
        bus=i["bus"]
        if bus["ack"]:
            found=[a for a in jobs if a["sid"] is None and a["mid"]==bus["mid"] and (a["owner"]["kind"]=="load")==bus["ack_to_load"]]
            assert len(found)==1 and not any(a["sid"]==bus["sid"] and a["response"] is None for a in jobs)
            found[0]["sid"]=bus["sid"]
            counts["direction_acks"]+=1
        if bus["response"]:
            found=[a for a in jobs if a["response"] is None and a["sid"]==bus["response_id"] and (a["owner"]["kind"]=="load")==bus["response_to_load"]]
            assert len(found)==1
            found[0]["response"]=dict(tick=tick,data=bus["data"],error=bus["error"],nderr=bus["nderr"])
            counts["sid_responses"]+=1
        for bank in range(3):
            p=f"io_replay_{bank}_"
            if not(pre[p+"valid"] and i["replay_ready"][bank]):continue
            s=bylq[120*pre[p+"bits_uop_lqIdx_flag"]+pre[p+"bits_uop_lqIdx_value"]]
            assert live(s) and s["grant"] is None and not s["sent"]
            replay_metadata(pre,p+"bits_",s["last"])
            slot=pre[p+"bits_replayQueueIdx"]
            assert slot%3==bank and (slot not in slots or slots[slot] is s)
            slots[slot],s["grant"]=s,slot
            counts["replay_grants"]+=1
        next_data,consuming=[None]*3,[]
        for lane,q in enumerate(i["bypass"]):
            p=f"io_bypass_{lane}_"
            if q["valid"]:
                s=bylq[120*int(q["lq"]["flag"])+q["lq"]["value"]]
                assert live(s) and s["grant"] is not None and s["attempts"][-1]["response"] is not None
                a=s["attempts"][-1]
                assert not a["consumed"] and q["nc"]==s["packet"]["execution"]["nc"] and q["mmio"]==s["packet"]["mmio"]
                check(post[p+"s1Resp_valid"] and post[p+"s1Resp_bits_paddr"]==s["pa"],"original_bypass_PA",uid=s["uid"])
                next_data[lane]=(s,a)
                consuming.append((s,a))
            if bpipe[lane] is not None:
                s,a=bpipe[lane]
                r=a["response"]
                check(post[p+"s2Resp_valid"] and post[p+"s2Resp_bits_data"]==r["data"]*((1<<64)+1) and
                      post[p+"s2Resp_bits_derr"]==int(r["error"]) and post[p+"s2Resp_bits_nderr"]==int(r["nderr"]),
                      "original_SID_data_error_s2",uid=s["uid"],original_response=r)
                a["consumed"]=True
                s["fault"]|=r["error"] or r["nderr"]
                counts["bypass_consumptions"]+=1
        if consuming:
            s,a=min(consuming,key=lambda x:x[1]["mid"])
            r=a["response"]
            check(post["io_ldExceptionInfo_valid"] and post["io_ldExceptionInfo_bits_exceptionVec_19"]==int(r["error"]) and
                  post["io_ldExceptionInfo_bits_exceptionVec_5"]==int(r["nderr"]),"original_SID_error_s1",uid=s["uid"],response=r)
        bpipe=next_data
        if pre["io_cmoOpReq_valid"] and i["cache_ready"]:
            found=[s for s in stores if live(s) and s["order"]==head and s.get("cbo") is not None and s["address"]["paddr"]==pre["io_cmoOpReq_bits_address"]]
            assert len(found)==1 and cache is None
            cache=found[0]
            assert cache.get("s2") and "data" in cache and cache["cbo"]==pre["io_cmoOpReq_bits_opcode"]
            counts["cache_requests"]+=1
        if i["cache_response"]:
            assert cache is not None and pre["io_cmoOpResp_ready"]
            cache["cache_response"]=dict(tick=tick,denied=i["cache_denied"],corrupt=i["cache_corrupt"])
            cache=None
            counts["cache_responses"]+=1
        for phase,pins in(("before",pre),("after",post)):
            if not pins["io_mmioStout_valid"]:continue
            rob=dict(flag=bool(pins["io_mmioStout_bits_robIdx_flag"]),value=pins["io_mmioStout_bits_robIdx_value"],former=bool(pins["io_mmioStout_bits_robIdx_isFormer"]))
            s=owner(rob,"store")
            assert s["order"]==head
            r=s.get("cache_response",dict(denied=False,corrupt=False))
            check(pins["io_mmioStout_bits_exceptionVec_7"]==int(r["denied"]) and pins["io_mmioStout_bits_exceptionVec_19"]==int(r["corrupt"]),
                  "original_Cache_error_held_WB",uid=s["uid"],phase=phase,response=r,ready=i["writeback_ready"])
            if phase=="before" and i["writeback_ready"]:
                check(s.get("cbo")!=3 or bool(s["consumed"]),"zero_requires_own_transfer",uid=s["uid"])
                s["wb"],s["fault"]=tick,bool(r["denied"] or r["corrupt"])
                counts["WB_fires"]+=1
        for lane in range(2):
            p=f"io_sbuffer_req_{lane}_"
            if not(pre[p+"valid"] and i["sbuffer_ready"][lane]):continue
            s=next(s for s in stores if live(s) and s.get("memory")==0 and s.get("cbo") in(None,3) and len(s["consumed"])<(2 if s["address"]["cross_word"] else 1))
            part,a=len(s["consumed"]),s["address"]
            va,pa,mask,value=a["vaddr"]//16*16+16*part,a["paddr"]//16*16+16*part,0,0
            for byte in range(1<<a["size"]):
                target=a["vaddr"]+byte-va
                if 0<=target<16:
                    mask|=1<<target
                    value|=((s["data"]>>(8*byte))&255)<<(8*target) if s.get("cbo")!=3 else 0
            bits=sum(255<<(8*b) for b in range(16) if mask>>b&1)
            check(pre[p+"bits_vaddr"]==va and pre[p+"bits_addr"]==pa and pre[p+"bits_mask"]==mask and not((pre[p+"bits_data"]^value)&bits) and
                  pre[p+"bits_wline"]==int(s.get("cbo")==3),"original_Sbuffer_bytes_control",uid=s["uid"],part=part)
            assert s.get("s2") and "data" in s and s["order"]<=head
            s["consumed"].add(part)
            s["last_fire"]=tick
            counts["Sbuffer_fragment_fires"]+=1
        for s in prepared:del valid[s["pos"]]
        if cut is not None:
            assert rec is None
            victims=[s for s in program if not s["rob_cancelled"] and s["order"]>=cut]
            vl=[s for s in valid.values() if s["order"]>=cut]
            vs=[s for s in stores if live(s) and s["order"]>=cut]
            assert all(not s["consumed"] and not s["attempts"] for s in vs)
            rec=dict(cutoff=cut,flush_self=red["flush_self"],original_ROB=red["rob"],lq_target=lt-len(vl),sq_target=min((s["pos"] for s in vs),default=st),lq=None,sq=None,tick=tick)
            recoveries.append(rec)
            for s in victims:
                s["rob_cancelled"]=True
                if live(s) and (s["kind"]=="store" or s in vl):
                    s["cancelled"]=True
                    if s["kind"]=="load":valid.pop(s["pos"],None)
            slots={slot:s for slot,s in slots.items() if not s["cancelled"]}
            counts["shared_redirects"]+=1
            counts["actual_flushAfter"]+=not red["flush_self"]
        delta=(pointer(post,"io_sqDeqPtr_")-sh)%256
        assert delta<=2
        for pos in range(sh,sh+delta):
            s=bysq[pos]
            assert live(s) and s.get("s2") and "data" in s
            legal=(len(s["consumed"])==(2 if s["address"]["cross_word"] else 1) and s["last_fire"]+2==tick) if s.get("cbo") is None and s.get("memory")==0 else bool(s["attempts"] and s["attempts"][-1]["sid"] is not None) if s.get("memory")==1 else s["wb"] is not None
            check(legal,"original_complete_SQ_prefix",uid=s["uid"],actual_SQ_release_tick=tick)
            s["complete"]=bool(legal)
            s["released"]=tick
            counts["invalid_SQ_release_not_semantic_completion"]+=not legal
        sh+=delta
        if post["io_toLsqEnqCtrl_lqDeq_valid"]:
            for pos in range(lh,lh+post["io_toLsqEnqCtrl_lqDeq_bits"]):
                s=bylq[pos%240]
                assert live(s) and s["sent"]
                s["complete"]=True
            lh+=post["io_toLsqEnqCtrl_lqDeq_bits"]
        if rec is not None:
            if post["io_toLsqEnqCtrl_lqRedirectPtr_valid"]:
                lt=max(lh,rec["lq_target"])
                rec["lq"]=120*post["io_toLsqEnqCtrl_lqRedirectPtr_bits_flag"]+post["io_toLsqEnqCtrl_lqRedirectPtr_bits_value"]
                assert rec["lq"]==lt%240
            if post["io_toLsqEnqCtrl_sqRedirectPtr_valid"]:
                st=rec["sq_target"]
                rec["sq"]=pointer(post,"io_toLsqEnqCtrl_sqRedirectPtr_bits_")
                assert rec["sq"]==st%256
            if rec["lq"] is not None and rec["sq"] is not None and not post["io_toLsqEnqCtrl_lqRecoverStall"] and not post["io_toLsqEnqCtrl_sqRecoverStall"]:
                rec["settled_tick"]=tick
                rec=None
                counts["both_recovery_responses_settled"]+=1
        assert 0<=lt-lh<=120 and 0<=st-sh<=128
        for key,value in(("LQ",lt-lh),("SQ_virtual",st-sh),("external_unreturned",sum(a["response"] is None for a in jobs))):peaks[key]=max(peaks[key],value)
        if violations:assert index==len(rows)-1,("unstopped original UID violation",violations)
        prev=row
    reuse=[]
    missing=[]
    for s in program:
        if not s["cancelled"]:continue
        width=120 if s["kind"]=="load" else 64
        witnesses=[n for n in program if n["uid"]>s["uid"] and n["kind"]==s["kind"] and n["pos"]%width==s["pos"]%width and n["complete"]]
        if witnesses:reuse.append(dict(cancelled_UID=s["uid"],new_completed_UID=witnesses[0]["uid"],kind=s["kind"],physical_slot=s["pos"]%width))
        else:missing.append(s["uid"])
    counts.update(allocated=len(program),completed=sum(s["complete"] for s in program),cancelled=sum(s["cancelled"] for s in program),failed_live=sum(live(s) for s in program),
                  pending_external_responses=sum(a["response"] is None for a in jobs),returned_unconsumed=sum(a["response"] is not None and not a["consumed"] and a["owner"]["kind"]=="load" for a in jobs),
                  cancelled_same_slot_new_UID_completed=len(reuse),cancelled_same_slot_not_yet_completed=len(missing))
    assert counts["allocated"]==counts["completed"]+counts["cancelled"]+counts["failed_live"]
    if passed:
        assert all(r["checked"] and "error" not in r for r in rows) and not violations and not slots and rec is None
        assert not counts["failed_live"] and not counts["pending_external_responses"] and not missing
        assert rows[-1]["after"]["io_lqEmpty"] and rows[-1]["after"]["io_sqEmpty"] and not rows[-1]["after"]["io_replayAllocate"]
    else:assert "error" in rows[-1] and not rows[-1]["checked"]
    kinds=Counter(("cached" if not s["packet"]["execution"]["nc"] and not s["packet"]["mmio"] else "nc_load" if s["packet"]["execution"]["nc"] else "mmio_load" if s["packet"]["memory_backed"] else "io_load")
                  if s["kind"]=="load" and "packet" in s else "unexecuted_load" if s["kind"]=="load" else "cbo" if s.get("cbo") is not None else "nc_store" if s.get("memory")==1 else "io_store" if s.get("memory",0)&2 else "store" for s in program)
    return dict(counts=dict(counts),peaks=dict(peaks),causes=dict(causes),actual_original_kinds=dict(kinds),independent_terminal_counterexamples=violations,
                terminal_tick=rows[-1]["post_tick"],terminal_runtime_error=rows[-1].get("error"),recoveries=recoveries,same_slot_completion_witnesses=reuse,
                missing_cancelled_same_slot_UIDs=missing,terminal_scope="actual_PASS_original_UID_effects_no_producer_admission_implied" if passed else "retained_real_strict_failure_prefix_no_later_effects_invented")
