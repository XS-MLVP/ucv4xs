#!/usr/bin/env python3
"""Necessary retained LDU producer contracts from raw stage history, no actor.

DCache/TLB event bits are outside this DUT. Check their allowed outcomes and
all retained causal requirements, not an invented native LoadUnit simulation.
"""
from collections import Counter

from audit_lsq_bus_v2 import rob, sq
from audit_lsq_mixed_history_v1 import Timeline
from audit_lsq_population_v1 import events


def inspect(path, *, passed):
    rows=list(events(path))
    owners=[]
    bylq={}
    timeline=Timeline()
    st=0
    p0,p1,p2,heads=([None]*3 for _ in range(4))
    old_s0=[None]*3
    counts=Counter()
    pending_rollbacks=[]
    stages=[]
    checks=[]
    def bind(item,s):
        assert item["owner"] is None or item["owner"] is s
        item["owner"]=s
        assert sq(item["query"]["sq"])==s["SQ_boundary"]%256
    def nk(item,addresses,s):
        return any(a["valid"] and not a["tlb_miss"] and 0<(rob(s["rob"])-rob(a["rob"]))%640<320 and
                   a["paddr"]>>(6 if a["fu_op"]&1 else 4)==item["PA"]>>(6 if a["fu_op"]&1 else 4) and
                   a["mask"]&item["mask"] for a in addresses)
    def source_requirements(item,packet):
        s,e=item["owner"],packet["execution"]
        u=e["uop"]
        b=item["bypass"]
        mmio=bool(b and b["mmio"])
        nc_replay=bool(b and b["nc"])
        unc=bool(packet["mmio"] or e["nc"])
        exceptions=packet["exceptions"]
        query=item.get("RAR")
        if mmio:
            assert query is None and not item.get("RAW"), "MMIO replay cannot issue RAR/RAW"
            counts["MMIO_replay_no_RAR_RAW"]+=1
        if query is not None:
            assert query["nc"]==nc_replay
            if item["full_forward"] or nc_replay:assert query["data_valid"]
            if unc and b is None:assert query["data_valid"]==item["full_forward"]
            counts["RAR_nc_and_first_uncache_dataValid_checks"]+=1
        flags=item["flags"]
        nuke=nk(item,item["S1_STA"],s) and not item["translation"]["kill"] or nk(item,item["S2_STA"],s)
        rd=bool(query and not item["RAR_ready"])
        wd=bool(query and not item["RAW_ready"])
        required=[]
        if not exceptions and not mmio:
            if unc and (b is None or nc_replay and (flags["data"] or rd or wd or nuke or flags["forward"])):required.append(0)
            if flags["forward"]:required.append(1)
            if u["store_set_hit"] and flags["address"]:required.append(2)
            if flags["data"]:required.append(4)
            if rd:required.append(9)
            if wd:required.append(10)
            if nuke:required.append(11)
        return required,nuke
    for row in rows:
        i,pre,post,t=row["input"],row["before"],row["after"],row["post_tick"]
        counts["raw_records"]+=1
        if i["reset"]:
            assert not owners
            continue
        timeline.decode(i["pending"],True)
        for d in i["dispatch"]:
            if not d["valid"]:continue
            s=dict(uid=len(owners)+1,rob=d["rob"],order=timeline.decode(d["rob"],True),kind="load" if d["need_alloc"]==1 else "store",cancelled=False)
            owners.append(s)
            if s["kind"]=="load":
                s["SQ_boundary"]=st
                bylq[120*int(d["load_start"]["flag"])+d["load_start"]["value"]]=s
            else:
                st+=1
                assert sq(d["store_end"])==st%256
        red=i["redirect"]
        cut=timeline.decode(red["rob"])+int(not red["flush_self"]) if red["valid"] else None
        if cut is not None:
            cleared=[r for r in pending_rollbacks if cut<=r["effective_cut"]]
            for r in cleared:
                r["actual_redirect_tick"]=t
                r["actual_ROB"]=red["rob"]
                r["actual_flush_self"]=red["flush_self"]
                checks.append(r)
            pending_rollbacks=[r for r in pending_rollbacks if r not in cleared]
        for r in pending_rollbacks:assert t-r["S3_tick"]<256,"unserved original LDU rollback"
        # Original S3 output is paired with the preceding same-lane S2 ticket.
        for lane,item in enumerate(p2):
            packet=i["loads"][lane]
            e=packet["execution"]
            if item is None:
                assert not e["valid"]
                continue
            s=item["owner"]
            killed=s is not None and (s["cancelled"] or cut is not None and s["order"]>=cut)
            if killed and not e["valid"]:continue
            if item["cross"] and not item["tail"]:
                assert not e["valid"]
                item["head_S3_tick"]=t
                item["head_revoke"]=i["rar_revoke_last"][lane]
                assert i["rar_revoke_last"][lane]==i["raw_revoke_last"][lane] and not i["rar_revoke_older"][lane] and not i["raw_revoke_older"][lane]
                heads[lane]=item
                counts["split_heads_saved_for_S4"]+=1
                continue
            assert e["valid"],("missing native next-edge S3",t,lane,item["S0_tick"])
            u=e["uop"]
            s=bylq[120*int(u["lq"]["flag"])+u["lq"]["value"]]
            assert s["rob"]==u["rob"]
            bind(item,s)
            head=heads[lane] if item["tail"] else None
            assert not item["tail"] or head is not None
            if head is not None:
                bind(head,s)
                assert head["head_S3_tick"]+2==t
            first=head or item
            assert packet["paddr"]==first["PA"] and e["vaddr"]==first["query"]["vaddr"] and e["mask"]==first["mask"]
            assert e["aligned_type"]==item["query"]["size"] and packet["update_address"]
            assert e["need_replay"]==bool(e["causes"]) and e["causes"].bit_count()<=1 and e["causes"]<1<<12 and e["causes"]!=1<<7
            use_head=bool(head is not None and e["unaligned_head"])
            if head is None:
                assert not e["unaligned_head"]
                assert i["rar_revoke_last"][lane]==i["raw_revoke_last"][lane]==bool(e["need_replay"] or packet["exceptions"])
                assert not i["rar_revoke_older"][lane] and not i["raw_revoke_older"][lane]
            else:
                assert not packet["exceptions"],"this producer emits split cached DCache errors only as a separate future scope"
                assert head["head_revoke"]==use_head
                assert i["rar_revoke_last"][lane]==i["raw_revoke_last"][lane]==bool(e["need_replay"])
                assert i["rar_revoke_older"][lane]==i["raw_revoke_older"][lane]==bool(not use_head and e["need_replay"])
                counts["split_tail_S4_native_revoke_checks"]+=1
            chosen=head if use_head else item
            required,nuke=source_requirements(chosen,packet)
            cause=e["causes"].bit_length()-1 if e["need_replay"] else None
            if packet["exceptions"] or chosen["bypass"] and chosen["bypass"]["mmio"]:
                assert cause is None
            elif cause is None:assert not required,("normal S3 ignores required replay",t,required)
            else:
                assert not required or cause<=min(required)
                if cause in(0,1,2,4,9,10,11):assert cause in required,("cause has no original retained event",t,cause,required)
                if cause==3:assert chosen["translation"]["kill"] or e["special_request"]
                if cause in(6,8) and chosen.get("RAR") is not None and not chosen["full_forward"]:assert not chosen["RAR"]["data_valid"]
                counts[f"checked_actual_S3_cause_{cause}"]+=1
            # Both head and tail query contracts survive head-priority replay.
            if head is not None:
                source_requirements(head,packet)
                source_requirements(item,packet)
            counts["native_next_edge_same_lane_feedbacks"]+=1
            counts["native_S3_revoke_checks"]+=1
            if cause==11:counts["C_NK_bound_to_real_STA"]+=1
            if not packet["exceptions"]:
                match=any(part["flags"]["match"] for part in(first,item))
                rar_nuke=any(part.get("RAR_nuke",False) for part in(first,item))
                if match or rar_nuke:
                    pending_rollbacks.append(dict(uid=s["uid"],original_ROB=s["rob"],S3_tick=t,effective_cut=s["order"]+int(not match),
                                                  cause="matchInvalid_flush" if match else "RAR_nuke_flushAfter"))
            stages.append(dict(uid=s["uid"],lane=lane,S0_tick=first["S0_tick"],S2_tick=first["S2_tick"],S3_tick=t,split=bool(head),
                               bypass=bool(first["bypass"]),cause=cause,exceptions=packet["exceptions"]))
            if head is not None:heads[lane]=None
        next2=[None]*3
        for lane,item in enumerate(p1):
            q,w=i["rar_queries"][lane],i["raw_queries"][lane]
            assert q["valid"]==w["valid"]
            if item is None:
                assert not q["valid"]
                continue
            item["S2_tick"]=t
            item["S2_STA"]=i["addresses"]
            item["RAR"]=q if q["valid"] else None
            item["RAW"]=w if w["valid"] else None
            if q["valid"]:
                s=bylq[120*int(q["lq"]["flag"])+q["lq"]["value"]]
                assert s["rob"]==q["rob"] and w["rob"]==q["rob"] and q["paddr"]==w["paddr"]==item["PA"] and w["mask"]==item["mask"]
                assert w["data_valid"]==q["data_valid"] and sq(w["sq"])==sq(item["query"]["sq"])
                bind(item,s)
                assert q["nc"]==bool(item["bypass"] and item["bypass"]["nc"])
                assert not(item["bypass"] and item["bypass"]["mmio"])
                if q["nc"]:assert q["data_valid"]
                for family in("rar","raw"):
                    prefix=f"io_ldu_{family}NukeQuery_{lane}_req_"
                    assert row["pins"][prefix+"valid"] and row["pins"][prefix+"bits_paddr"]==q["paddr"]
                    assert row["pins"][prefix+"bits_dataValid"]==int(q["data_valid"])
                item["RAR_ready"]=bool(pre[f"io_ldu_rarNukeQuery_{lane}_req_ready"])
                item["RAW_ready"]=bool(pre[f"io_ldu_rawNukeQuery_{lane}_req_ready"])
                item["RAR_nuke"]=bool(post[f"io_ldu_rarNukeQuery_{lane}_resp_bits_nuke"])
                assert post[f"io_ldu_rarNukeQuery_{lane}_resp_valid"]
                counts["same_lane_S0_PA_S2_RAR_RAW_pairs"]+=1
            elif item["bypass"] and item["bypass"]["mmio"]:
                counts["actual_MMIO_replay_S2_no_query"]+=1
            else:
                if item["owner"] is not None and not item["translation"]["kill"]:
                    assert nk(item,item["S1_STA"],item["owner"]),"missing S2 query without source gate"
                counts["S2_no_query_requires_prev_STA_or_cancel_binding"]+=1
            s=item["owner"]
            if not q["valid"] and item.get("S1_redirect_kill") and s is None:
                counts["cancelled_before_S2_identity_visible"]+=1
            elif s is None or not s["cancelled"] and not(cut is not None and s["order"]>=cut):next2[lane]=item
        next1=[None]*3
        for lane,item in enumerate(p0):
            if item is None:continue
            tr=i["translations"][lane]
            p=f"io_forward_{lane}_s2Resp_"
            assert post[p+"valid"]==int(not tr["kill"])
            assert tr["kill"] or tr["paddr"]%4096==item["query"]["vaddr"]%4096
            item["PA"],item["translation"],item["S1_STA"]=tr["paddr"],tr,i["addresses"]
            item["S1_redirect_kill"]=bool(tr["kill"] and red["valid"])
            flags={key:bool(not tr["kill"] and post[p+suffix]) for key,suffix in(("address","bits_addrInvalid_valid"),("data","bits_dataInvalid_valid"),("forward","bits_forwardInvalid"),("match","bits_matchInvalid"))}
            item["flags"]=flags
            mask=sum(post[p+f"bits_forwardMask_{b}"]<<b for b in range(16)) if not tr["kill"] else 0
            item["full_forward"]=not flags["data"] and mask&item["mask"]==item["mask"]
            next1[lane]=item
            counts["original_S0_next_S1_PA_checks"]+=1
        next0=[None]*3
        for lane,q in enumerate(i["queries"]):
            b=i["bypass"][lane]
            assert not b["valid"] or q["valid"]
            if not q["valid"]:continue
            full=((1<<(1<<q["size"]))-1)<<(q["vaddr"]%16)
            old=old_s0[lane]
            tail=bool(old and old["cross"] and not old["tail"] and q["vaddr"]==old["query"]["vaddr"]//16*16+16 and q["sq"]==old["query"]["sq"])
            item=dict(S0_tick=t,query=q,fullmask=full,mask=old["fullmask"]>>16 if tail else full&65535,
                      cross=bool(full>>16),tail=tail,bypass=b if b["valid"] else None,owner=None)
            if b["valid"]:bind(item,bylq[120*int(b["lq"]["flag"])+b["lq"]["value"]])
            next0[lane]=item
            counts["actual_S0_Forward_tickets"]+=1
            counts["actual_S0_Forward_plus_bypass"]+=b["valid"]
        if cut is not None:
            for s in owners:
                if s["order"]>=cut:s["cancelled"]=True
            for lane,item in enumerate(heads):
                if item is not None and item["owner"] is not None and item["owner"]["cancelled"]:heads[lane]=None
        if post["io_toLsqEnqCtrl_sqRedirectPtr_valid"]:
            raw=pointer_sq(post)
            st=st+(raw-st)%256 if (raw-st)%256<128 else st-((st-raw)%256)
        p0,p1,p2,old_s0=next0,next1,next2,next0
    in_flight=sum(item is not None for pipe in(p0,p1,p2,heads) for item in pipe)
    if passed:assert not in_flight and not pending_rollbacks
    return dict(counts=dict(counts),original_S3_stages=stages,served_original_rollbacks=checks,
                pending_original_rollbacks=pending_rollbacks,terminal_pipeline_tickets=in_flight,
                limits="Necessary retained producer contracts only. External DCache/TLB event bits do not exist at Wrapper and are not independently simulated as native LDU. Stopped prefixes retain unbound in-flight tickets; no actor/expected/change oracle. Full-domain correctness and all eight seeds require separate original-effect and complete-run gates.")


def pointer_sq(pins):
    return 128*pins["io_toLsqEnqCtrl_sqRedirectPtr_bits_first_flag"]+64*pins["io_toLsqEnqCtrl_sqRedirectPtr_bits_second_flag"]+pins["io_toLsqEnqCtrl_sqRedirectPtr_bits_value"]
