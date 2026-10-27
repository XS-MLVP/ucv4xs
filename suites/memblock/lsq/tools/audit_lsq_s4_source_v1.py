#!/usr/bin/env python3
"""Independent S4 source projection from pre-S0 external stimuli/public pins.

External cache/TLB stimuli are explicit boundary assumptions, NOT observed
native LoadUnit responses. No actor answer/expected/change/private-state reads.
"""
from collections import Counter

from audit_lsq_bus_v2 import rob
from audit_lsq_population_v1 import events


def key(tick,packet):
    u=packet["execution"]["uop"]
    return tick,rob(u["rob"]),120*int(u["lq"]["flag"])+u["lq"]["value"]


def fault(segment):
    assert not segment["mshr_nack"] or not segment["miss"]
    return int(segment["tag_error"])<<5 | int(segment["tl_d_corrupt"])<<19


def cause(segment):
    if fault(segment):return None
    return 5 if segment["mshr_nack"] else 6 if segment["miss"] else None


def inspect_direct(path):
    rows=list(events(path))
    by_tick={r["post_tick"]:r for r in rows}
    stimuli=[r for r in events(path.with_name("lsq_actor.jsonl")) if r["event"]=="S4_external_cache_stimulus_before_S0"]
    counts=Counter()
    expected={}
    witnesses=[]
    for stimulus in stimuli:
        start=stimulus["tick"]+2
        a,b,c,d,e=(by_tick.get(start+2*n) for n in range(5))
        if e is None:
            counts["incomplete_external_attempts"]+=1
            continue
        load=stimulus["load"]
        u=load["execution"]["uop"]
        lane=next(l for l,q in enumerate(a["input"]["queries"]) if q["valid"])
        va,pa=load["execution"]["vaddr"],load["paddr"]
        tv,tp=stimulus["tail_VA"],stimulus["tail_PA"]
        assert stimulus["tick"]<a["pre_tick"] and not stimulus["EnableAccurateLoadError"] and stimulus["CSR_cache_error_enable"]
        assert va%16==12 and tv==va//16*16+16 and tv%4096==tp%4096
        for row,addr,size in ((a,va,3),(b,tv,4)):
            q=row["input"]["queries"][lane]
            assert q["valid"] and q["vaddr"]==addr and q["size"]==size and q["sq"]==u["sq"]
        for row,addr in ((b,pa),(c,tp)):
            tr=row["input"]["translations"][lane]
            assert not tr["kill"] and tr["paddr"]==addr
            p=f"io_forward_{lane}_s2Resp_"
            assert row["after"][p+"valid"] and not any(row["after"][p+f"bits_forwardMask_{n}"] for n in range(16))
            assert not any(row["after"][p+"bits_"+field] for field in ("addrInvalid_valid","dataInvalid_valid","forwardInvalid","matchInvalid"))
        head,tail=stimulus["head"],stimulus["tail"]
        for row,segment,addr,mask in ((c,head,pa,61440),(d,tail,tp,15)):
            rq,wq=row["input"]["rar_queries"][lane],row["input"]["raw_queries"][lane]
            valid=bool(segment["tl_d_corrupt"] or not segment["miss"])
            assert rq["valid"] and wq["valid"] and rq["rob"]==wq["rob"]==u["rob"] and rq["lq"]==u["lq"]
            assert rq["paddr"]==wq["paddr"]==addr and rq["data_valid"]==wq["data_valid"]==valid and not rq["nc"]
            assert wq["sq"]==u["sq"] and wq["mask"]==mask
            assert row["before"][f"io_ldu_rarNukeQuery_{lane}_req_ready"] and row["before"][f"io_ldu_rawNukeQuery_{lane}_req_ready"]
            assert not row["after"][f"io_ldu_rarNukeQuery_{lane}_resp_bits_nuke"]
        hc,tc=cause(head),cause(tail)
        hx,tx=fault(head),fault(tail)
        hr,tr=bool(hx or hc is not None),bool(tx or tc is not None)
        selected_cause=hc if hc is not None else tc
        chosen_fault=hx if hx else tx
        wb=bool(hx or hc is None and (tx or tc is None))
        fullva=load["fullva"] if hx else tv
        gpaddr=stimulus["head_gpaddr"] if hx else stimulus["tail_gpaddr"]
        packet=e["input"]["loads"][lane]
        q=packet["execution"]
        assert q["valid"] and q["uop"]["rob"]==u["rob"] and q["uop"]["lq"]==u["lq"] and q["uop"]["sq"]==u["sq"]
        assert q["uop"]["exceptions"]==packet["exceptions"]==chosen_fault
        assert packet["paddr"]==pa and q["vaddr"]==va and q["mask"]==61440
        assert packet["fullva"]==fullva and packet["gpaddr"]==gpaddr
        assert packet["nonleaf"]==(stimulus["head_nonleaf"] if hx else stimulus["tail_nonleaf"])
        assert packet["hyper"]==stimulus["tail_hyper"]
        assert q["aligned_type"]==4 and q["last_beat"]==bool(pa&64) and not q["vector"] and not q["nc"] and not packet["mmio"]
        assert q["need_replay"]==(selected_cause is not None) and q["causes"]==(0 if selected_cause is None else 1<<selected_cause)
        assert q["unaligned_head"]==(hc is not None) and q["replay_feedback"]==stimulus["feedback"]
        assert q["mshr"]==(stimulus["head_MSHR"] if hc==6 else stimulus["tail_MSHR"])
        assert q["handled"]==(head["miss"] if hc==6 else tail["miss"])
        assert q["tlb_id"]==(stimulus["head_TLB_id"] if hc is not None else stimulus["tail_TLB_id"])
        assert q["tlb_full"]==(stimulus["head_TLB_full"] if hc is not None else stimulus["tail_TLB_full"])
        assert q["special_eligible"]==(selected_cause in (3,5,6)) and packet["update_address"]==wb
        assert not any(p["execution"]["valid"] for p in d["input"]["loads"]),"head S3 is saved, not an early LQ completion"
        for row,one,two in ((d,hr,False),(e,hr or tr,not hr and tr)):
            for family in ("rar","raw"):
                assert row["input"][family+"_revoke_last"]==[one if l==lane else False for l in range(3)]
                assert row["input"][family+"_revoke_older"]==[two if l==lane else False for l in range(3)]
        k=key(e["post_tick"],packet)
        assert k not in expected
        expected[k]=dict(fullva=fullva,gpaddr=gpaddr,exceptions=chosen_fault)
        counts["complete_original_S4_attempts"]+=1
        counts["head_exception_priority"]+=bool(hx)
        counts["tail_exception_selected"]+=bool(not hx and tx)
        counts["exception_WB_despite_tail_Replay"]+=bool(hx and tc is not None)
        counts["head_Replay_tail_exception_no_WB"]+=bool(hc is not None and tx and not wb)
        counts["head_cause_beats_lower_tail_cause"]+=bool(hc is not None and tc is not None and tc<hc)
        counts["MSHR_tail_despite_selected_head_nack"]+=bool(hc==5 and tail["miss"])
        counts["noncontiguous_page_tails"]+=tp!=pa//16*16+16
        counts["real_S4_feedbacks"]+=q["replay_feedback"]
        counts["tail_fullva_even_without_exception"]+=not bool(chosen_fault)
        counts[f"lane_{lane}"]+=1
        witnesses.append(dict(S0_tick=start,S4_tick=e["post_tick"],lane=lane,original_ROB=u["rob"],original_LQ=u["lq"],
                              head_exception=hx,tail_exception=tx,cause=selected_cause,update_address=wb,source_fullva=fullva,source_gpaddr=gpaddr,
                              feedback=q["replay_feedback"],PA=pa,tail_PA=tp))
    return dict(counts=dict(counts),S4_witnesses=witnesses,limits="External inputs frozen before S0, necessary actual LSQ-input source projection plus actual Forward/RAR/RAW checks; not native upstream DCache/TLB/LDU/Backend proof."),expected


def inspect_mixed(path):
    rows=list(events(path))
    declarations=[e for e in events(path.with_name("lsq_actor.jsonl")) if e["event"]=="S4_mixed_external_TLB_input_before_S0"]
    expected={}
    counts=Counter()
    witnesses=[]
    for index,row in enumerate(rows):
        for lane,p in enumerate(row["input"]["loads"]):
            q=p["execution"]
            if not q["valid"] or q["aligned_type"]!=4 or q["uop"]["operation"]!=6:continue
            head,tail=rows[index-4],rows[index-3]
            hq,tq=head["input"]["queries"][lane],tail["input"]["queries"][lane]
            assert hq["valid"] and tq["valid"] and tq["vaddr"]==hq["vaddr"]//16*16+16 and not p["exceptions"]
            hd=[e for e in declarations if not e["tail"] and e["tick"]<head["pre_tick"] and e["VA"]==hq["vaddr"] and e["ROB_absolute"]%640==rob(q["uop"]["rob"])]
            td=[e for e in declarations if e["tail"] and e["tick"]<tail["pre_tick"] and e["VA"]==tq["vaddr"] and e["ROB_absolute"]%640==rob(q["uop"]["rob"])]
            assert hd and td
            hd,td=max(hd,key=lambda e:e["tick"]),max(td,key=lambda e:e["tick"])
            assert td["tick"]>=hd["tick"] and td["gpaddr"]-hd["gpaddr"]==td["PA"]-hd["PA"]
            assert rows[index-3]["input"]["translations"][lane]["paddr"]==hd["PA"]
            assert rows[index-2]["input"]["translations"][lane]["paddr"]==td["PA"]
            assert td["fullva"]==tq["vaddr"] and p["fullva"]==td["fullva"] and p["gpaddr"]==td["gpaddr"]
            assert p["nonleaf"]==td["nonleaf"] and p["hyper"]==td["hyper"] and p["paddr"]==hd["PA"] and q["vaddr"]==hq["vaddr"]
            k=key(row["post_tick"],p)
            expected[k]=dict(fullva=td["fullva"],gpaddr=td["gpaddr"],exceptions=0)
            counts["normal_mixed_S4_TLB_source_checks"]+=1
            witnesses.append(dict(tick=row["post_tick"],lane=lane,head_declaration_tick=hd["tick"],tail_declaration_tick=td["tick"],
                                  original_ROB=q["uop"]["rob"],original_LQ=q["uop"]["lq"],expected_fullva=td["fullva"],expected_gpaddr=td["gpaddr"]))
    return dict(counts=dict(counts),witnesses=witnesses,limits="Low positive normal mixed S4 plus explicit chosen continuous-TLB metadata; no unrecorded old high-address inference or upstream native proof."),expected
