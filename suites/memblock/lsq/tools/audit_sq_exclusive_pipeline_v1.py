#!/usr/bin/env python3
"""Strict aligned-cached hit/cause10 producer, including actual S3 writeback bits.

Not a widened full LDU model. Unlike old mixed pipeline-v1, never assumes every
Replay is an updateAddrValid completion. No expected/change/actor/private reads.
"""
from collections import Counter

from audit_lsq_bus_v2 import sq
from audit_lsq_population_v1 import events


def inspect(path,*,passed):
    rows=list(events(path))
    p0,p1,p2=([None]*3 for _ in range(3))
    counts=Counter()
    stages=[]
    for row in rows:
        i,pre,post,t=row["input"],row["before"],row["after"],row["post_tick"]
        counts["raw_records"]+=1
        if i["reset"]:
            assert not any((*p0,*p1,*p2))
            continue
        assert not i["redirect"]["valid"] and not any(b["valid"] for b in i["bypass"])
        for lane,item in enumerate(p2):
            packet=i["loads"][lane]
            e=packet["execution"]
            assert e["valid"]==(item is not None)
            if item is None:continue
            assert e["aligned_type"]==3,("native S3 alignedType:=in.size",t,lane,e["aligned_type"])
            assert e["last_beat"]==bool(item["PA"]&64),("native S3 last_beat:=PA bit6",t,lane)
            assert e["vaddr"]==packet["fullva"]==item["VA"] and packet["paddr"]==item["PA"] and e["mask"]==255
            assert e["uop"]["rob"]==item["RAR"]["rob"]==item["RAW"]["rob"] and e["uop"]["lq"]==item["RAR"]["lq"]
            assert e["uop"]["sq"]==item["RAW"]["sq"] and e["uop"]["operation"]==6
            assert not e["nc"] and not packet["mmio"] and packet["memory_backed"] and not packet["exceptions"] and not e["vector"]
            assert not e["uop"]["store_set_hit"] and not e["special_request"] and not e["special_eligible"]
            cause=0 if item["RAW_ready"] else 1<<10
            assert e["causes"]==cause and e["need_replay"]==bool(cause)
            assert packet["update_address"]==(not bool(cause)),("Replay without exception/matchInvalid is not native writeback",t,lane,cause)
            expected=tuple(bool(cause) and n==lane for n in range(3))
            # This endpoint test has one non-overlapped LDU attempt at a time.
            assert tuple(i["rar_revoke_last"])==tuple(i["raw_revoke_last"])==expected
            assert not any((*i["rar_revoke_older"],*i["raw_revoke_older"]))
            assert item["S0_tick"]+6==t and item["S2_tick"]+2==t
            stages.append(dict(lane=lane,S0_tick=item["S0_tick"],S2_tick=item["S2_tick"],S3_tick=t,original_ROB=e["uop"]["rob"],original_LQ=e["uop"]["lq"],cause=10 if cause else None,
                               aligned_type=e["aligned_type"],last_beat=e["last_beat"],update_address=packet["update_address"]))
            counts["native_next_edge_same_lane_feedbacks"]+=1
            counts["native_S3_size_lastBeat_writeback_checks"]+=1
            if cause:counts["checked_actual_S3_cause_10"]+=1
        next2=[None]*3
        for lane,item in enumerate(p1):
            q,w=i["rar_queries"][lane],i["raw_queries"][lane]
            assert q["valid"]==w["valid"]==(item is not None)
            if item is None:continue
            assert q["paddr"]==w["paddr"]==item["PA"] and w["mask"]==255 and q["data_valid"] and w["data_valid"] and not q["nc"]
            assert q["rob"]==w["rob"] and sq(w["sq"])==sq(item["SQ"])
            assert pre[f"io_ldu_rarNukeQuery_{lane}_req_ready"] and post[f"io_ldu_rarNukeQuery_{lane}_resp_valid"] and not post[f"io_ldu_rarNukeQuery_{lane}_resp_bits_nuke"]
            for a in i["addresses"]:
                if a["valid"]:assert a["paddr"]//16!=item["PA"]//16,"this nonalias endpoint cannot manufacture C_NK"
            next2[lane]=dict(**item,RAR=q,RAW=w,RAW_ready=bool(pre[f"io_ldu_rawNukeQuery_{lane}_req_ready"]),S2_tick=t)
            counts["same_lane_S0_PA_S2_RAR_RAW_pairs"]+=1
        next1=[None]*3
        for lane,item in enumerate(p0):
            if item is None:continue
            tr=i["translations"][lane]
            p=f"io_forward_{lane}_s2Resp_"
            assert not tr["kill"] and post[p+"valid"] and tr["paddr"]%4096==item["VA"]%4096
            assert not any(post[p+"bits_"+flag] for flag in("matchInvalid","forwardInvalid","dataInvalid_valid"))
            assert not any(post[p+f"bits_forwardMask_{b}"] for b in range(16))
            for a in i["addresses"]:
                if a["valid"]:assert a["paddr"]//16!=tr["paddr"]//16
            next1[lane]=dict(**item,PA=tr["paddr"])
            counts["original_S0_next_S1_PA_checks"]+=1
        next0=[None]*3
        for lane,q in enumerate(i["queries"]):
            if not q["valid"]:continue
            assert q["size"]==3 and q["vaddr"]%16==0 and not q["strict"] and not q["wait"]
            next0[lane]=dict(VA=q["vaddr"],SQ=q["sq"],S0_tick=t)
            counts["actual_S0_Forward_tickets"]+=1
        p0,p1,p2=next0,next1,next2
    if passed:assert not any((*p0,*p1,*p2))
    return dict(counts=dict(counts),original_S3_stages=stages,terminal_pipeline_tickets=sum(x is not None for x in(*p0,*p1,*p2)),
                limits="Aligned nonalias cached hit/cause10 only; source S3 size/lastBeat/updateAddrValid are mandatory. Not general NC/MMIO/exception/split S4 native LoadUnit simulation or whole-goal signoff.")
