#!/usr/bin/env python3
"""Independent253-case audit: old210 unchanged + actual cancel/reset obligations.

Only raw public input/pre/post/tick reconstruct owners, requests, responses,
grants, data/error consumption and completion. No reference/actor/change or
known-issue contents are used as a correctness oracle. Common reset aborts
external jobs explicitly; redirect must return every actually accepted job.
"""
import argparse
from collections import Counter
import itertools
import json
from pathlib import Path
import shutil

from audit_lsq_bus_v2 import pointer, rob, rob_matches, sq
from audit_lsq_memory_v1 import lq, words
from audit_lsq_population_v1 import RAW, events, paths_by_node, replay_metadata, same_raw, validate_row
from audit_sq_initial import ROOT, sha, verify_common


def inspect(path):
    stores, loads, by_sq, by_lq, attempts = [], [], {}, {}, []
    stail = ltail = shead = lhead = sequence = 0
    prior_unc, pending_s2, due_data = [], [], [None]*3
    unc_owned, raw_owned, rar_owned, buffered = set(), [], [], set()
    recovery, recoveries, resets, rollback, rewinds = None, [], [], [], []
    previous, reset_high, counts, visited = None, False, Counter(), set()
    by_tick = {}

    def live(item):
        return not item["complete"] and item["aborted"] is None

    def cancelled(item, red):
        distance = (rob(item["rob"])-rob(red["rob"])) % 640
        assert distance != 320
        return red["valid"] and (0 < distance < 320 or red["flush_self"] and distance == 0)

    def load_by_request(pins):
        matches = [item for item in loads if not item["complete"] and "packet" in item and
                   (item["aborted"] is None or item["uid"] in buffered) and item["packet"]["paddr"] == pins["io_uncache_req_bits_addr"] and
                   item["rob"] == dict(flag=bool(pins["io_uncache_req_bits_robIdx_flag"]),value=pins["io_uncache_req_bits_robIdx_value"],former=bool(pins["io_uncache_req_bits_robIdx_isFormer"])) and
                   (not item["attempts"] or item["attempts"][-1]["consumed"])]
        assert len(matches) == 1, ("uncache original request identity", [item["uid"] for item in matches])
        return matches[0]

    for row in events(path):
        validate_row(row,previous,False)
        assert row["checked"]
        inp, pre, post, tick = row["input"],row["before"],row["after"],row["post_tick"]
        by_tick[tick] = row
        counts["raw_records"] += 1
        assert not inp["release"]["valid"] and not any(q["valid"] for q in inp["queries"])
        if inp["reset"]:
            assert not any(d["valid"] for d in inp["dispatch"]) and not inp["redirect"]["valid"]
            assert not inp["bus"]["ack"] and not inp["bus"]["response"] and not inp["cache_response"]
            if not reset_high:
                victims = [item for item in stores+loads if live(item)]
                if victims:
                    assert any(item["kind"]=="store" for item in victims) and any(item["kind"]=="load" for item in victims)
                    for item in victims:
                        item["aborted"],item["abort_tick"] = "reset",tick
                    jobs = [a for a in attempts if a["response"] is None and not a["reset_aborted"]]
                    for attempt in jobs:
                        attempt["reset_aborted"] = True
                    resets.append(dict(tick=tick,aborted_original_uids=[item["uid"] for item in victims],external_reset_aborted_attempts=[a["uid"] for a in jobs],
                                       already_accepted_external_writes_not_retracted=[a["uid"] for a in attempts if a["owner"]["kind"]=="store" and not a.get("preceded_reset",False)]))
                    for attempt in attempts:
                        attempt["preceded_reset"] = True
                    counts["common_system_active_reset_events"] += 1
                    counts["external_jobs_aborted_by_common_reset_not_returned"] += len(jobs)
                    counts["externally_accepted_store_writes_not_retracted_by_reset"] += sum(a["owner"]["kind"]=="store" for a in jobs)
            assert not pre["io_uncache_req_valid"] and not pre["io_mmioStout_valid"] and not pre["io_replayAllocate"]
            # No resetless output is blanked: s2 is explicitly the old s1.
            for lane,due in enumerate(due_data):
                p=f"io_bypass_{lane}_s2Resp_"
                # Only the very first power-on edge can shift an unknown
                # resetless s1 valid. This never reopens on an active reset.
                if previous is not None:
                    assert post[p+"valid"] == int(due is not None)
                if due:
                    owner,attempt = due
                    response = attempt["response"]
                    assert post[p+"bits_data"] == response["data"]*((1<<64)+1)
                    assert post[p+"bits_derr"] == int(response["error"]) and post[p+"bits_nderr"] == int(response["nderr"])
                    attempt["consumed"] = True
                    counts["actual_resetless_old_s1_data_error_s2_on_reset"] += 1
            stail=ltail=shead=lhead=0
            by_sq,by_lq,unc_owned,raw_owned,rar_owned,buffered = {},{},set(),[],[],set()
            prior_unc,pending_s2,due_data,recovery = [],[],[None]*3,None
            previous,reset_high = row,True
            continue
        reset_high=False
        assert pointer(pre,"io_sqDeqPtr_") == shead % 256
        # Native Wrapper has no fake head/full/ready inputs. Track public ROB
        # progress only after actual execution; Sbuffer completion is separate.
        for item in stores+loads:
            if live(item) and rob(item["rob"]) < rob(inp["pending"]):
                assert item.get("sent",False) if item["kind"]=="load" else item.get("s2_done",False) and "data" in item
        for d in inp["dispatch"]:
            if not d["valid"]:
                continue
            assert recovery is None and not inp["redirect"]["valid"]
            assert not pre["io_toLsqEnqCtrl_lqRecoverStall"] and not pre["io_toLsqEnqCtrl_sqRecoverStall"] and d["flows"]==1
            sequence+=1
            item=dict(uid=sequence,rob=d["rob"],complete=False,aborted=None,attempts=[],sent=False,consumed=set(),grant=None,grants=0,feedbacks=0)
            if d["need_alloc"]==2:
                assert stail not in by_sq or not live(by_sq[stail])
                item.update(kind="store",position=stail)
                stores.append(item)
                by_sq[stail]=item
                stail+=1
                assert sq(d["store_end"])==stail % 256 and stail-shead<=128
            else:
                assert d["need_alloc"]==1 and lq(d["load_start"])==ltail % 240
                assert ltail%240 not in by_lq or not live(by_lq[ltail%240])
                item.update(kind="load",position=ltail)
                loads.append(item)
                by_lq[ltail%240]=item
                ltail+=1
                assert sum(live(load) for load in loads)<=120
        for store,lane,last in pending_s2:
            attr=inp["attributes"][lane]
            assert attr["last"]==last
            if last:
                store.update(attribute=attr,s2_done=True)
        pending_s2=[]
        for lane,address in enumerate(inp["addresses"]):
            if not address["valid"]:
                continue
            pos=shead+(address["slot"]-shead)%64
            store=by_sq[pos]
            assert live(store) and store["rob"]==address["rob"] and not address["tlb_miss"]
            if "address" not in store:
                store["address"]=address
            else:
                assert address["cross_word"] and address["last"] and store["address"]["vaddr"]//16*16+16==address["vaddr"]
            pending_s2.append((store,lane,address["last"]))
        for data in inp["data"]:
            if data["valid"]:
                store=by_sq[sq(data["sq"])]
                assert live(store) and "data" not in store
                store["data"]=data["data"]
        for lane,page in enumerate(inp["second_pages"]):
            if page["valid"] and pre[f"io_sta_unalignQueueReq_{lane}_ready"]:
                store=by_sq[sq(page["sq"])]
                assert live(store) and store["address"]["cross_word"] and "second_page" not in store
                store["second_page"]=page["paddr"]&~4095
                counts["actual_original_uq_second_page_fires"]+=1
        # An Uncache entry is allocated one edge after its original S3. Model
        # capacity with a UID set (no private mid or free-list state reads).
        eligible=[item for item in prior_unc if not cancelled(item,inp["redirect"]) and item["aborted"] is None]
        eligible.sort(key=lambda item:rob(item["rob"]))
        available=16-len(unc_owned)
        accepted,rejected=eligible[:available],eligible[available:]
        unc_owned.update(item["uid"] for item in accepted)
        if rejected:
            item=rejected[0]
            u,p=item["packet"]["execution"]["uop"],"io_nack_rollback_0_"
            assert post[p+"valid"]
            rob_matches(post,p+"bits_robIdx_",item["rob"])
            fields={"ftqIdx_flag":int(u["ftq"]["flag"]),"ftqIdx_value":u["ftq"]["value"],"ftqOffset":u["offset"],
                    "isRVC":int(u["rvc"]),"level":1,"debug_runahead_checkpoint_id":u["checkpoint"]}
            assert all(post[p+"bits_"+key]==value for key,value in fields.items())
            rollback.append(dict(tick=tick,original_uid=item["uid"],rejected_original_uids=[item["uid"] for item in rejected],actual_oldest_rob=item["rob"],occupied=len(unc_owned)))
            counts["actual_capacity_rollback_complete_metadata"]+=1
        else:
            assert not post["io_nack_rollback_0_valid"]
        prior_unc=[]
        for packet in inp["loads"]:
            q=packet["execution"]
            if not q["valid"]:
                continue
            item=by_lq[lq(q["uop"]["lq"])]
            assert live(item) and item["rob"]==q["uop"]["rob"] and packet["fullva"]==q["vaddr"]
            assert packet["paddr"]%4096==packet["fullva"]%4096
            if q["replay_feedback"]:
                assert item["grant"]==q["slot"] and item["packet"]["execution"]["uop"]==q["uop"]
                assert not q["need_replay"] and not q["causes"]
                item["grant"]=None
                item["feedbacks"]+=1
                counts["actual_original_slot_feedbacks"]+=1
            else:
                assert "packet" not in item
                item["packet"]=packet
            if q["causes"]==1:
                assert q["need_replay"] and q["nc"]!=packet["mmio"]
                prior_unc.append(item)
            if not q["need_replay"]:
                assert packet["update_address"] and not item["sent"]
                if item["packet"]["execution"]["causes"]==1:
                    assert item["attempts"] and item["attempts"][-1]["consumed"]
                item["sent"]=True
        raw_owned=[q for q in raw_owned if q["owner"]["aborted"] is None and 0<(q["sq"]-pointer(pre,"io_issuePtrExt_"))%256<128]
        rar_owned=[q for q in rar_owned if q["owner"]["aborted"] is None and q["position"]>lhead]
        for kind,queries,pool in (("raw",inp["raw_queries"],raw_owned),("rar",inp["rar_queries"],rar_owned)):
            for lane,q in enumerate(queries):
                if kind=="rar":
                    assert post[f"io_ldu_rarNukeQuery_{lane}_resp_valid"]==int(q["valid"])
                if not q["valid"]:
                    continue
                matches=[item for item in loads if live(item) and item["rob"]==q["rob"]]
                assert len(matches)==1
                item=matches[0]
                # Cached queries can precede S3, so bind to the subsequently
                # unique same-ROB original packet, also checked at end below.
                item.setdefault("queries",[]).append(q)
                needed=(0<(sq(q["sq"])-pointer(pre,"io_issuePtrExt_"))%256<128) if kind=="raw" else lq(q["lq"])>lhead
                assert pre[f"io_ldu_{kind}NukeQuery_{lane}_req_ready"]
                if needed:
                    pool.append(dict(owner=item,sq=sq(q["sq"]) if kind=="raw" else None,position=lq(q["lq"]) if kind=="rar" else None))
                    counts[f"actual_original_{kind}_pool_query_allocations"]+=1
                if kind=="rar":
                    assert not q["nc"] and not post[f"io_ldu_rarNukeQuery_{lane}_resp_bits_nuke"]
        if pre["io_uncache_req_valid"]:
            if pre["io_uncache_req_bits_cmd"]==0:
                item=load_by_request(pre)
                buffered.add(item["uid"])
            else:
                candidates=[item for item in stores if live(item) and item.get("address",{}).get("paddr")==pre["io_uncache_req_bits_addr"]]
                assert len(candidates)==1
                item=candidates[0]
            if inp["bus"]["ready"]:
                assert not item["attempts"] or item["attempts"][-1]["consumed"]
                mid=pre["io_uncache_req_bits_id"]
                if item["kind"]=="load":
                    assert item["uid"] in unc_owned
                    q=item["packet"]["execution"]
                    expected=dict(vaddr=q["vaddr"],mask=q["mask"],nc=int(q["nc"]),memBackTypeMM=int(item["packet"]["memory_backed"]))
                    if item["packet"]["mmio"]:
                        assert item["rob"]==inp["pending"]
                else:
                    assert item["rob"]==inp["pending"] and item.get("s2_done") and "data" in item
                    expected=dict(vaddr=item["address"]["vaddr"],data=item["data"],mask=255,nc=int(item["attribute"]["nc"]),memBackTypeMM=int(item["attribute"]["memory"]))
                assert all(pre["io_uncache_req_bits_"+key]==value for key,value in expected.items())
                attempt=dict(uid=len(attempts)+1,owner=item,mid=mid,sid=None,response=None,consumed=False,reset_aborted=False,request_tick=tick)
                attempts.append(attempt)
                item["attempts"].append(attempt)
                buffered.discard(item["uid"])
                counts["actual_original_load_bus_fires" if item["kind"]=="load" else "actual_original_store_bus_write_fires"]+=1
        bus=inp["bus"]
        if bus["ack"]:
            matches=[a for a in attempts if not a["reset_aborted"] and a["sid"] is None and a["mid"]==bus["mid"] and (a["owner"]["kind"]=="load")==bus["ack_to_load"]]
            assert len(matches)==1 and not any(a["sid"]==bus["sid"] and a["response"] is None and not a["reset_aborted"] for a in attempts)
            matches[0]["sid"]=bus["sid"]
            counts["actual_original_direction_id_acks"]+=1
        if bus["response"]:
            matches=[a for a in attempts if not a["reset_aborted"] and a["response"] is None and a["sid"]==bus["response_id"] and (a["owner"]["kind"]=="load")==bus["response_to_load"]]
            assert len(matches)==1
            attempt=matches[0]
            attempt["response"]=dict(tick=tick,data=bus["data"],error=bus["error"],nderr=bus["nderr"])
            if attempt["owner"]["aborted"]=="redirect":
                unc_owned.discard(attempt["owner"]["uid"])
            counts["actual_original_sid_responses"]+=1
        for bank in range(3):
            p=f"io_replay_{bank}_"
            if pre[p+"valid"] and inp["replay_ready"][bank]:
                item=by_lq[120*pre[p+"bits_uop_lqIdx_flag"]+pre[p+"bits_uop_lqIdx_value"]]
                assert live(item) and item["grant"] is None and not item["sent"]
                replay_metadata(pre,p+"bits_",item["packet"])
                slot=pre[p+"bits_replayQueueIdx"]
                assert slot%3==bank and slot<120
                if item["packet"]["execution"]["causes"]==1:
                    assert item["attempts"][-1]["response"]
                item.update(grant=slot,grants=item["grants"]+1)
                visited.add(slot)
                counts["actual_original_replay_grants"]+=1
        next_data=[None]*3
        for lane,q in enumerate(inp["bypass"]):
            p=f"io_bypass_{lane}_"
            assert post[p+"s1Resp_valid"]==int(q["valid"])
            if q["valid"]:
                item=by_lq[lq(q["lq"])]
                assert live(item) and item["grant"] is not None
                packet,attempt=item["packet"],item["attempts"][-1]
                assert attempt["response"] is not None and not attempt["consumed"]
                assert q["nc"]==packet["execution"]["nc"] and q["mmio"]==packet["mmio"]
                assert post[p+"s1Resp_bits_paddr"]==packet["paddr"] and post["io_ldExceptionInfo_valid"]
                rob_matches(post,"io_ldExceptionInfo_bits_robIdx_",item["rob"])
                expected=dict(vaddr=packet["fullva"],gpaddr=packet["gpaddr"],isHyper=int(packet["hyper"]),isForVSnonLeafPTE=int(packet["nonleaf"]),
                              exceptionVec_19=int(attempt["response"]["error"]),exceptionVec_5=int(attempt["response"]["nderr"]))
                assert all(post["io_ldExceptionInfo_bits_"+key]==value for key,value in expected.items())
                next_data[lane]=(item,attempt)
                unc_owned.remove(item["uid"])
            due=due_data[lane]
            assert post[p+"s2Resp_valid"]==int(due is not None)
            if due:
                item,attempt=due
                response=attempt["response"]
                assert not attempt["consumed"] and post[p+"s2Resp_bits_data"]==response["data"]*((1<<64)+1)
                assert post[p+"s2Resp_bits_derr"]==int(response["error"]) and post[p+"s2Resp_bits_nderr"]==int(response["nderr"])
                attempt["consumed"]=True
                counts["actual_original_bypass_data_error_consumptions"]+=1
        due_data=next_data
        if inp["redirect"]["valid"]:
            assert recovery is None
            victims=[item for item in stores+loads if live(item) and cancelled(item,inp["redirect"])]
            assert victims
            old_s=[item for item in victims if item["kind"]=="store"]
            old_l=[item for item in victims if item["kind"]=="load"]
            expected_s=min((item["position"] for item in old_s),default=stail)
            expected_l=min((item["position"] for item in old_l),default=ltail)
            assert all(not item["consumed"] for item in old_s)
            for item in victims:
                item["aborted"],item["abort_tick"]="redirect",tick
                if item["uid"] in unc_owned and item["uid"] not in buffered and (not item["attempts"] or item["attempts"][-1]["response"] is not None):
                    unc_owned.remove(item["uid"])
            recovery=dict(tick=tick,victims=[item["uid"] for item in victims],expected_sq=expected_s,expected_lq=expected_l,sq=None,lq=None,
                          retired_unconsumed_store_uids=[item["uid"] for item in stores if live(item) and rob(item["rob"])<rob(inp["pending"]) and not item["consumed"]])
            recoveries.append(recovery)
            prior_unc=[item for item in prior_unc if item["aborted"] is None]
            counts["actual_shared_redirects"]+=1
            counts["actual_both_branch_nonempty_suffix_cancels"]+=int(bool(old_s and old_l))
            for attempt in attempts:
                if attempt["response"] is not None and attempt["response"]["tick"]+2==tick and attempt["owner"] in victims:
                    counts["actual_mid_response_then_next_edge_shared_redirect"]+=1
        if recovery is not None:
            if post["io_toLsqEnqCtrl_lqRedirectPtr_valid"]:
                recovery["lq"]=120*post["io_toLsqEnqCtrl_lqRedirectPtr_bits_flag"]+post["io_toLsqEnqCtrl_lqRedirectPtr_bits_value"]
                assert recovery["lq"]==recovery["expected_lq"]%240
                ltail=recovery["expected_lq"]
            if post["io_toLsqEnqCtrl_sqRedirectPtr_valid"]:
                recovery["sq"]=pointer(post,"io_toLsqEnqCtrl_sqRedirectPtr_bits_")
                assert recovery["sq"]==recovery["expected_sq"]%256
                stail=recovery["expected_sq"]
            if recovery["lq"] is not None and recovery["sq"] is not None and not post["io_toLsqEnqCtrl_lqRecoverStall"] and not post["io_toLsqEnqCtrl_sqRecoverStall"]:
                recovery["settled_tick"]=tick
                recovery=None
                counts["actual_two_branch_recovery_responses_and_settle"]+=1
        if pointer(post,"io_issuePtrExt_")<pointer(pre,"io_issuePtrExt_"):
            assert recoveries and tick-recoveries[-1]["tick"]<=50
            rewinds.append(dict(tick=tick,previous=pointer(pre,"io_issuePtrExt_"),current=pointer(post,"io_issuePtrExt_"),actual_recovery=recoveries[-1]["sq"]))
        for lane in range(2):
            p=f"io_sbuffer_req_{lane}_"
            if pre[p+"valid"] and inp["sbuffer_ready"][lane]:
                item=next(item for item in stores if live(item) and len(item["consumed"])<len(words(item)))
                part=len(item["consumed"])
                va,pa,mask,value=words(item)[part]
                assert item.get("s2_done") and "data" in item and rob(item["rob"])<=rob(inp["pending"])
                assert pre[p+"bits_vaddr"]==va and pre[p+"bits_addr"]==pa and pre[p+"bits_mask"]==mask and not pre[p+"bits_wline"]
                bits=sum(255<<(8*byte) for byte in range(16) if mask>>byte&1)
                assert not ((pre[p+"bits_data"]^value)&bits)
                item["consumed"].add(part)
                item["last_fire"]=tick
                counts["actual_original_store_byte_fragment_fires"]+=1
        delta=(pointer(post,"io_sqDeqPtr_")-shead)%256
        assert delta<=2 and post["io_toLsqEnqCtrl_sqDeq_valid"]==int(bool(delta))
        if delta:
            assert post["io_toLsqEnqCtrl_sqDeq_bits"]==delta
        for pos in range(shead,shead+delta):
            item=by_sq[pos]
            assert live(item) and item["consumed"]==set(range(len(words(item)))) and item["last_fire"]+2==tick
            item["complete"]=True
        shead+=delta
        if post["io_toLsqEnqCtrl_lqDeq_valid"]:
            count=post["io_toLsqEnqCtrl_lqDeq_bits"]
            active=[item for item in loads if live(item)]
            assert 0<count<=len(active)
            for item in active[:count]:
                assert item["sent"] and (not item["attempts"] or item["attempts"][-1]["consumed"])
                item["complete"]=True
            lhead+=count
        assert not pre["io_mmioStout_valid"] and not pre["io_cmoOpReq_valid"]
        previous=row
    assert recovery is None and not unc_owned and not any(due_data)
    assert all(item["complete"] or item["aborted"] is not None for item in stores+loads)
    assert previous["after"]["io_lqEmpty"] and previous["after"]["io_sqEmpty"] and not previous["after"]["io_replayAllocate"] and not previous["after"]["io_uncache_req_valid"]
    for item in loads:
        if item["complete"]:
            assert item["grants"]==item["feedbacks"]
        for q in item.get("queries",[]):
            assert q["paddr"]==item["packet"]["paddr"]
        if item["aborted"]:
            assert any(new["uid"]>item["uid"] and new["position"]%120==item["position"]%120 and new["complete"] for new in loads)
            counts["all_aborted_loads_same_physical_slot_new_uid_completed"]+=1
    for item in stores:
        if item["aborted"]:
            assert any(new["uid"]>item["uid"] and new["position"]%64==item["position"]%64 and new["complete"] for new in stores)
            counts["all_aborted_stores_same_physical_slot_new_uid_completed"]+=1
    for attempt in attempts:
        assert attempt["response"] is not None or attempt["reset_aborted"]
        if attempt["response"] is not None and not attempt["consumed"]:
            assert attempt["owner"]["aborted"] is not None
            counts["real_returned_cancelled_original_attempts_disposed_not_consumed"]+=1
        if attempt["reset_aborted"]:
            assert attempt["owner"]["aborted"]=="reset" and attempt["response"] is None
    for check in events(path.with_name("lsq_checks.jsonl")):
        actual=by_tick[check["tick"]][check["phase"]]
        assert check["passed"] and check["actual"]=={key:actual[key] for key in check["expected"]}
        assert all(not ((actual[key]^value)&check["masks"].get(key,-1)) for key,value in check["expected"].items())
    if "test_both_real_branches_full_query_replay_pools_" in previous["nodeid"]:
        assert counts["actual_original_raw_pool_query_allocations"]>=112 and counts["actual_original_rar_pool_query_allocations"]>=192
        assert visited==set(range(120))
        counts["actual_full_120_replay_same_slots_granted_feedback_completed_cases"]+=1
    return dict(allocated=len(stores)+len(loads),completed=sum(item["complete"] for item in stores+loads),
                cancelled=sum(item["aborted"]=="redirect" for item in stores+loads),reset_aborted=sum(item["aborted"]=="reset" for item in stores+loads),
                attempts=len(attempts),counts=dict(counts),recoveries=recoveries,resets=resets,capacity_rollbacks=rollback,actual_sq_ready_pointer_recovery_rewinds=rewinds,
                actual_mid_next_edge_redirect_witnesses=[dict(mid=a["mid"],response_tick=a["response"]["tick"],redirect_tick=a["owner"]["abort_tick"]) for a in attempts
                                                       if a["response"] and a["owner"]["aborted"]=="redirect" and a["response"]["tick"]+2==a["owner"]["abort_tick"]])


def corrections(current_paths):
    reports=[]
    for name,expected in (("lsq-uncache-recovery-01",5),("lsq-shared-recovery-01",4),("lsq-pending-reset-01",2)):
        root=ROOT/"results"/name
        manifest,_,nodes=verify_common(root)
        originals=paths_by_node(root)
        failed=0
        for node,failed_case in nodes.items():
            if not failed_case:
                same_raw(originals[node],current_paths[node])
                continue
            before=list(events(originals[node]))
            after=events(current_paths[node])
            for old in before:
                new=next(after)
                assert all(old[key]==new[key] for key in RAW)
            assert next(after,None) is not None
            failed+=1
            reports.append(dict(original_run=name,nodeid=node,all_original_native_raw_records_are_unchanged_prefix=len(before),
                                original_trace_sha256=sha(originals[node]),new_trace_sha256=sha(current_paths[node]),
                                original_scope="actor generation ambiguity" if "uncache-recovery" in name else "reference domain/connection/reset phase assumption",
                                dut_or_stimulus_changed_to_bless_failure=False))
        assert failed==expected
    assert len(reports)==11
    return reports


def audit(name):
    run,prior=ROOT/"results"/name,ROOT/"results/lsq-expanded-11"
    manifest,source,nodes=verify_common(run)
    old,_,old_nodes=verify_common(prior)
    assert manifest["tests"]=={"PASS":216,"FAIL":37} and len(nodes)==253
    assert old["tests"]=={"PASS":173,"FAIL":37} and len(old_nodes)==210
    paths,old_paths=paths_by_node(run),paths_by_node(prior)
    assert set(paths)==set(nodes) and set(old_paths)==set(old_nodes)<=set(nodes)
    counts,cases,wake_mid=Counter(),[],set()
    for node,path in sorted(paths.items()):
        if node in old_nodes:
            assert nodes[node]==old_nodes[node]
            records=same_raw(path,old_paths[node])
            detail=dict(all_raw_samples_equal_previous210=records)
            counts["previous210_cases_all_raw_samples_unchanged"]+=1
        else:
            assert not nodes[node]
            detail=inspect(path)
            records=detail["counts"]["raw_records"]
            counts.update(detail["counts"])
            for key in ("allocated","completed","cancelled","reset_aborted"):
                counts["new_"+key]+=detail[key]
            counts["new_cases"]+=1
            if "test_each_real_mid_wakeup_cancel_" in node:
                assert len(detail["actual_mid_next_edge_redirect_witnesses"])==1
                witness=detail["actual_mid_next_edge_redirect_witnesses"][0]
                assert node.endswith(f'[{witness["mid"]}]')
                wake_mid.add(witness["mid"])
        counts["all_continuous_raw_records"]+=records
        cases.append(dict(nodeid=node,journal=str(path.relative_to(run)),sha256=sha(path),result="FAIL" if nodes[node] else "PASS",**detail))
    assert counts["previous210_cases_all_raw_samples_unchanged"]==210 and counts["new_cases"]==43
    assert counts["new_allocated"]==counts["new_completed"]+counts["new_cancelled"]+counts["new_reset_aborted"]
    assert wake_mid==set(range(16)) and counts["actual_full_120_replay_same_slots_granted_feedback_completed_cases"]==4
    assert counts["actual_capacity_rollback_complete_metadata"]==3 and counts["common_system_active_reset_events"]==13
    helper_proofs=corrections(paths)
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    files=(Path(__file__),ROOT/"tools/audit_lsq_population_v1.py",ROOT/"tools/audit_lsq_memory_v1.py",ROOT/"tools/audit_lsq_bus_v2.py",ROOT/"tools/audit_lsq_bus_v3.py")
    for file in files:
        target=dest/file.name
        if target.exists():
            assert sha(target)==sha(file)
        else:
            shutil.copy2(file,target)
    report=dict(run=name,status="NOT_PASS_253_case_shared_recovery_reset_and_external_obligations_audited",tests=manifest["tests"],snapshot_files=len(source),
                counts=dict(counts),all_16_mid_next_response_edge_redirect_witnesses=sorted(wake_mid),helper_corrections_original_raw_prefix_proofs=helper_proofs,
                previous210_history_audit_sha256=sha(prior/"uncache-history-audit-v2.json"),auditors={file.name:sha(dest/file.name) for file in files},cases=cases,
                limits="Exact253 scope: all old210 native raw histories/37FAIL/16 protocol-only probes unchanged. New43 full-cycle-reference cases independently reconstruct original UIDs, two-branch recovery, full120Replay/56RAW/96RAR refill, real bus direction/mid/SID/returns and original bytes/errors; every cancelled/reset Load or Store has same physical slot later UID truly complete. Common reset explicitly aborts external pending jobs; accepted external Store writes are not retracted and are NOT counted as full completion. Late responses across an uncoordinated/local-only reset remain outside this common-reset test contract. Resetless s1/s2 data/error checked at reset, not blanket masked. No full legal mixed random/fair-drain acceptance, fresh elaboration, arbitrary parameter or Backend/ISA claim.")
    output=run/"recovery-history-audit-v1.json"
    if output.exists():
        assert json.loads(output.read_text())==report
    else:
        output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({key:value for key,value in report.items() if key not in ("cases","helper_corrections_original_raw_prefix_proofs")},indent=2,ensure_ascii=False))


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
