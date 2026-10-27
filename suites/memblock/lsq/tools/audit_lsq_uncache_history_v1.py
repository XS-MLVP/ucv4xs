#!/usr/bin/env python3
"""Exact210-case raw audit: old194 unchanged + full Uncache/NC RAR + twoMA.

No DUT/reference/actor imports or change/outcome/known-issues correctness oracle.
External bus attempts, held data, Replay grants, S3, VLQ and Store effects have
separate ledgers. Cancelling a completed-S3-but-not-dequeued Load is not done.
"""
import argparse
from collections import Counter
import itertools
import json
from pathlib import Path
import shutil

from audit_lsq_bus_v2 import pointer, rob, rob_matches, sq
from audit_lsq_memory_v1 import lq, words
from audit_lsq_population_v1 import RAW, events, inspect_replay, paths_by_node, replay_metadata, same_raw, validate_row
from audit_sq_initial import ROOT, sha, verify_common


def rar_key(address):
    tag, folded = address >> 6, 0
    while tag:
        folded ^= tag & 2047
        tag >>= 11
    reverse = sum(((address >> (11 + bit)) & 1) << (4 - bit) for bit in range(5))
    return folded << 5 | ((address >> 6 & 31) ^ reverse)


def inspect_uncache(path):
    loads, by_lq, attempts, rar = [], {}, [], []
    store, previous, pending_s2, due_data = None, None, False, [None] * 3
    tail = public_head = sq_head = 0
    recovery, recoveries, rar_checks, visits = None, [], [], set()
    counts, active_mid_peak = Counter(), 0
    for row in events(path):
        validate_row(row, previous, False)
        assert row["checked"]
        inp, pre, post, tick = row["input"], row["before"], row["after"], row["post_tick"]
        assert not inp["release"]["valid"] and not any(q["valid"] for q in inp["raw_queries"])
        if inp["reset"]:
            assert not loads and store is None
            previous = row
            continue
        for d in inp["dispatch"]:
            if not d["valid"]:
                continue
            assert not inp["redirect"]["valid"] and not pre["io_toLsqEnqCtrl_lqRecoverStall"] and not pre["io_toLsqEnqCtrl_sqRecoverStall"]
            assert recovery is None and d["flows"] == 1
            if d["need_alloc"] == 2:
                assert store is None and sq(d["store_end"]) == 1
                store = dict(rob=d["rob"], consumed=False, complete=False)
            else:
                assert d["need_alloc"] == 1 and lq(d["load_start"]) == tail
                assert tail not in by_lq or by_lq[tail]["cancelled"] or by_lq[tail]["complete"]
                load = dict(uid=len(loads)+1, position=tail, rob=d["rob"], sent=False, complete=False, cancelled=False,
                            attempts=[], grant=None, original_slot=None, grants=0, feedbacks=0, last_nuke=False)
                loads.append(load)
                by_lq[tail] = load
                tail += 1
        if pending_s2:
            attr = inp["attributes"][0]
            assert attr["memory"] and attr["last"] and not attr["nc"] and not attr["mmio"] and not attr["exception"]
            store["s2_done"] = True
        pending_s2 = False
        for address in inp["addresses"]:
            if address["valid"]:
                assert store is not None and address["slot"] == 0 and address["rob"] == store["rob"] and "address" not in store
                assert not address["tlb_miss"] and not address["cross_word"] and address["last"]
                store["address"] = address
                pending_s2 = True
        for data in inp["data"]:
            if data["valid"]:
                assert store is not None and sq(data["sq"]) == 0 and "data" not in store
                store["data"] = data["data"]
        if store is not None and rob(store["rob"]) < rob(inp["pending"]):
            assert store.get("s2_done") and "data" in store
        for load in loads:
            if not load["cancelled"] and rob(load["rob"]) < rob(inp["pending"]):
                assert load["sent"] and load["attempts"][-1]["consumed"]
                response = load["attempts"][-1]["response"]
                assert not response["error"] and not response["nderr"], "ROB moved past a faulted Load without trap/recovery"
        for packet in inp["loads"]:
            q = packet["execution"]
            if not q["valid"]:
                continue
            load = by_lq[lq(q["uop"]["lq"])]
            assert q["uop"]["rob"] == load["rob"] and not load["cancelled"] and not load["complete"]
            assert packet["fullva"] == q["vaddr"] and q["vaddr"] % 4096 == packet["paddr"] % 4096
            assert packet["gpaddr"] % 4096 == packet["paddr"] % 4096 and q["nc"] != packet["mmio"] and sq(q["uop"]["sq"]) == 1
            if "initial" not in load:
                assert not q["replay_feedback"] and q["need_replay"] and q["causes"] == 1
                load["initial"] = packet
            else:
                assert q["uop"] == load["initial"]["execution"]["uop"] and q["replay_feedback"] and load["grant"] == q["slot"]
                load["grant"] = None
                load["feedbacks"] += 1
                if load["last_nuke"]:
                    assert q["need_replay"] and q["causes"] == 1 and q["nc"], "real NC nuke must retry C_UNCACHE, not fake normal/C_NK completion"
                    load["retry_due_to_nuke"] = tick
                    load["last_nuke"] = False
                    counts["real_nc_nuke_same_original_slot_c0_feedbacks"] += 1
                if not q["need_replay"]:
                    assert not load["sent"] and load["attempts"][-1]["consumed"] and packet["update_address"]
                    if "retry_due_to_nuke" in load:
                        assert load["attempts"][-1]["request_tick"] > load["retry_due_to_nuke"]
                    load["sent"] = True
            load["packet"] = packet
        if pre["io_uncache_req_valid"] and inp["bus"]["ready"]:
            assert pre["io_uncache_req_bits_cmd"] == 0
            matches = [load for load in loads if not load["cancelled"] and "packet" in load and not load["sent"] and
                       load["packet"]["paddr"] == pre["io_uncache_req_bits_addr"] and
                       rob(load["rob"]) == 2*(160*pre["io_uncache_req_bits_robIdx_flag"]+pre["io_uncache_req_bits_robIdx_value"])+int(not pre["io_uncache_req_bits_robIdx_isFormer"])]
            assert len(matches) == 1
            load = matches[0]
            packet, mid = load["packet"], pre["io_uncache_req_bits_id"]
            assert packet["execution"]["causes"] == 1 and packet["execution"]["need_replay"]
            assert not load["attempts"] or load["attempts"][-1]["consumed"]
            assert pre["io_uncache_req_bits_vaddr"] == packet["execution"]["vaddr"] and pre["io_uncache_req_bits_mask"] == packet["execution"]["mask"]
            assert pre["io_uncache_req_bits_nc"] == int(packet["execution"]["nc"]) and pre["io_uncache_req_bits_memBackTypeMM"] == int(packet["memory_backed"])
            if packet["mmio"]:
                assert load["rob"] == inp["pending"]
            assert not any(a["mid"] == mid and not a["consumed"] for a in attempts)
            attempt = dict(uid=len(attempts)+1, load_uid=load["uid"], mid=mid, sid=None, request_tick=tick,
                           response=None, consumed=False, packet=packet)
            attempts.append(attempt)
            load["attempts"].append(attempt)
            counts["actual_original_uncache_request_fires"] += 1
            active_mid_peak = max(active_mid_peak, sum(not a["consumed"] for a in attempts))
        bus = inp["bus"]
        if bus["ack"]:
            assert bus["ack_to_load"]
            matches = [a for a in attempts if a["mid"] == bus["mid"] and a["sid"] is None]
            assert len(matches) == 1 and not any(a["sid"] == bus["sid"] and a["response"] is None for a in attempts)
            matches[0].update(sid=bus["sid"], ack_tick=tick)
            counts["actual_direction_bound_id_responses"] += 1
        if bus["response"]:
            assert bus["response_to_load"]
            matches = [a for a in attempts if a["sid"] == bus["response_id"] and a["response"] is None]
            assert len(matches) == 1
            matches[0]["response"] = dict(tick=tick, data=bus["data"], error=bus["error"], nderr=bus["nderr"])
            counts["actual_direction_and_sid_bound_responses"] += 1
        # These are real fires, not speculative valid samples or a model slot.
        for bank in range(3):
            p = f"io_replay_{bank}_"
            if pre[p+"valid"] and inp["replay_ready"][bank]:
                key = 120*pre[p+"bits_uop_lqIdx_flag"] + pre[p+"bits_uop_lqIdx_value"]
                load = by_lq[key]
                assert load["grant"] is None and not load["cancelled"] and not load["sent"] and load["attempts"][-1]["response"]
                replay_metadata(pre, p+"bits_", load["initial"])
                slot = pre[p+"bits_replayQueueIdx"]
                assert slot % 3 == bank and (load["original_slot"] is None or load["original_slot"] == slot)
                load.update(grant=slot, original_slot=slot, grants=load["grants"]+1)
                counts["actual_original_uncache_replay_grants"] += 1
        next_data = [None] * 3
        for lane, query in enumerate(inp["bypass"]):
            p = f"io_bypass_{lane}_"
            assert post[p+"s1Resp_valid"] == int(query["valid"])
            if query["valid"]:
                load = by_lq[lq(query["lq"])]
                packet, attempt = load["initial"], load["attempts"][-1]
                assert load["grant"] is not None and attempt["response"] and not attempt["consumed"]
                assert query["nc"] == packet["execution"]["nc"] and query["mmio"] == packet["mmio"]
                assert post[p+"s1Resp_bits_paddr"] == packet["paddr"] and post["io_ldExceptionInfo_valid"]
                rob_matches(post, "io_ldExceptionInfo_bits_robIdx_", load["rob"])
                expected = {"vaddr": packet["fullva"], "gpaddr": packet["gpaddr"], "isHyper": int(packet["hyper"]),
                            "isForVSnonLeafPTE": int(packet["nonleaf"]), "exceptionVec_19": int(attempt["response"]["error"]),
                            "exceptionVec_5": int(attempt["response"]["nderr"])}
                assert all(post["io_ldExceptionInfo_bits_"+key] == value for key,value in expected.items())
                next_data[lane] = (load, attempt)
            due = due_data[lane]
            assert post[p+"s2Resp_valid"] == int(due is not None)
            if due is not None:
                load, attempt = due
                response = attempt["response"]
                assert not attempt["consumed"] and post[p+"s2Resp_bits_data"] == response["data"]*((1<<64)+1)
                assert post[p+"s2Resp_bits_derr"] == int(response["error"]) and post[p+"s2Resp_bits_nderr"] == int(response["nderr"])
                attempt.update(consumed=True, consume_tick=tick, bypass_lane=lane)
                packet = load["initial"]
                kind = "nc" if packet["execution"]["nc"] else "mmio_memory" if packet["memory_backed"] else "io"
                visits.add((attempt["mid"], kind, lane))
                counts["actual_original_bypass_s2_data_error_consumptions"] += 1
        due_data = next_data
        rar = [entry for entry in rar if entry["position"] > public_head and not entry["owner"]["cancelled"]]
        for lane, query in enumerate(inp["rar_queries"]):
            p = f"io_ldu_rarNukeQuery_{lane}_resp_"
            assert post[p+"valid"] == int(query["valid"])
            if not query["valid"]:
                continue
            load = by_lq[lq(query["lq"])]
            assert query["rob"] == load["rob"] and query["paddr"] == load["initial"]["paddr"]
            assert query["nc"] and query["data_valid"] and load["initial"]["execution"]["nc"] and load["attempts"][-1]["consumed"]
            matches = [entry for entry in rar if rob(entry["owner"]["rob"]) > rob(load["rob"]) and rar_key(entry["paddr"]) == rar_key(query["paddr"])]
            assert post[p+"bits_nuke"] == int(bool(matches))
            load["last_nuke"] = bool(matches)
            rar_checks.append(dict(tick=tick, lane=lane, original_load_uid=load["uid"], latest_bus_attempt=load["attempts"][-1]["uid"],
                                   actual_nuke=int(bool(matches)), matched_original_uids=[entry["owner"]["uid"] for entry in matches]))
            if load["position"] > public_head and pre[f"io_ldu_rarNukeQuery_{lane}_req_ready"]:
                rar.append(dict(owner=load, position=load["position"], paddr=query["paddr"]))
            counts["actual_nc_data_rar_queries"] += 1
        if inp["redirect"]["valid"]:
            assert recovery is None and not any(d["valid"] for d in inp["dispatch"])
            cutoff = rob(inp["redirect"]["rob"])
            victims = [load for load in loads if not load["complete"] and not load["cancelled"] and
                       (rob(load["rob"]) > cutoff or inp["redirect"]["flush_self"] and rob(load["rob"]) == cutoff)]
            assert len(victims) == 1 and victims[0]["sent"] and victims[0]["attempts"][-1]["consumed"]
            assert rob(store["rob"]) < rob(inp["pending"]) < cutoff and not store["consumed"]
            for victim in victims:
                victim["cancelled"] = True
            recovery = dict(tick=tick, victims=[load["uid"] for load in victims], lq=None, sq=None)
            recoveries.append(recovery)
            rar = [entry for entry in rar if not entry["owner"]["cancelled"]]
            counts["actual_cancelled_s3_done_but_not_vlq_completed_loads"] += 1
        if recovery is not None:
            if post["io_toLsqEnqCtrl_lqRedirectPtr_valid"]:
                recovery["lq"] = 120*post["io_toLsqEnqCtrl_lqRedirectPtr_bits_flag"]+post["io_toLsqEnqCtrl_lqRedirectPtr_bits_value"]
                tail = recovery["lq"]
            if post["io_toLsqEnqCtrl_sqRedirectPtr_valid"]:
                recovery["sq"] = pointer(post, "io_toLsqEnqCtrl_sqRedirectPtr_bits_")
            if recovery["lq"] is not None and recovery["sq"] is not None and not post["io_toLsqEnqCtrl_lqRecoverStall"] and not post["io_toLsqEnqCtrl_sqRecoverStall"]:
                assert recovery["lq"] == recovery["sq"] == 1
                recovery["settled_tick"] = tick
                recovery = None
                counts["actual_both_branch_recovery_responses"] += 1
        for lane in range(2):
            p = f"io_sbuffer_req_{lane}_"
            if pre[p+"valid"] and inp["sbuffer_ready"][lane]:
                assert store is not None and not store["consumed"] and store.get("s2_done")
                va,pa,mask,value = words(store)[0]
                assert pre[p+"bits_vaddr"] == va and pre[p+"bits_addr"] == pa and pre[p+"bits_mask"] == mask and not pre[p+"bits_wline"]
                assert not ((pre[p+"bits_data"] ^ value) & ((1<<64)-1))
                store.update(consumed=True, last_fire=tick)
                counts["actual_old_ordinary_store_original_byte_fires"] += 1
        delta = (pointer(post,"io_sqDeqPtr_")-sq_head) % 256
        assert delta <= 1 and post["io_toLsqEnqCtrl_sqDeq_valid"] == int(bool(delta))
        if delta:
            assert sq_head == 0 and store["consumed"] and store["last_fire"]+2 == tick and post["io_toLsqEnqCtrl_sqDeq_bits"] == 1
            store["complete"] = True
        sq_head += delta
        if post["io_toLsqEnqCtrl_lqDeq_valid"]:
            count = post["io_toLsqEnqCtrl_lqDeq_bits"]
            live = [load for load in loads if not load["complete"] and not load["cancelled"]]
            assert 0 < count <= len(live)
            for load in live[:count]:
                assert load["sent"] and all(attempt["consumed"] for attempt in load["attempts"])
                load["complete"] = True
            public_head += count
        assert not pre["io_cmoOpReq_valid"] and not pre["io_mmioStout_valid"]
        previous = row
        counts["raw_records"] += 1
    assert store is not None and store["complete"] and recovery is None and not any(due_data)
    assert all(a["response"] and a["consumed"] for a in attempts)
    assert all(load["complete"] or load["cancelled"] for load in loads)
    assert previous["after"]["io_lqEmpty"] and previous["after"]["io_sqEmpty"] and not previous["after"]["io_replayAllocate"]
    for load in loads:
        assert load["grants"] == load["feedbacks"] == len(load["attempts"])
        if load["cancelled"]:
            assert any(new["uid"] != load["uid"] and new["position"] % 120 == load["position"] % 120 and new["complete"] for new in loads)
            counts["cancelled_same_lq_slot_new_uid_bus_bypass_completed"] += 1
    if "test_all_16_real_" in previous["nodeid"]:
        assert len(loads) == len(attempts) == 32 and not rar_checks
        assert all({a["mid"] for a in attempts[start:start+16]} == set(range(16)) for start in (0,16))
        assert len(visits) == 16
        counts["two_full_16_mid_generations_actually_consumed_cases"] += 1
    if recoveries:
        assert len(recoveries) == 1 and len(loads) == 3 and len(attempts) == 4
        assert [check["actual_nuke"] for check in rar_checks] == [0,1,0]
    elif rar_checks:
        assert len(loads) == len(attempts) == 2 and not any(check["actual_nuke"] for check in rar_checks)
    return dict(allocated=len(loads)+1, completed=1+sum(load["complete"] for load in loads), cancelled=sum(load["cancelled"] for load in loads),
                attempts=len(attempts), public_held_mid_peak=active_mid_peak, actual_mid_kind_bypass_visits=sorted(visits),
                rar_checks=rar_checks, recoveries=recoveries, counts=dict(counts))


def inspect_consumer_correction(run, paths, nodes):
    original = ROOT / "results/lsq-uncache-population-01"
    old, _, old_nodes = verify_common(original)
    assert old["tests"] == {"PASS": 12, "FAIL": 3}
    originals, corrections = paths_by_node(original), []
    for node, failed in old_nodes.items():
        assert not nodes[node]
        if not failed:
            same_raw(originals[node], paths[node])
            continue
        assert "-nc]" in node
        prefix = 0
        for before, after in zip(events(originals[node]),events(paths[node])):
            if all(before[key] == after[key] for key in RAW):
                prefix += 1
                continue
            assert before["post_tick"] == after["post_tick"] and not any(before["input"]["replay_ready"])
            fired = [bank for bank in range(3) if after["input"]["replay_ready"][bank]]
            assert len(fired) == 1 and after["before"][f"io_replay_{fired[0]}_valid"]
            actual_uid = after["before"][f"io_replay_{fired[0]}_bits_uop_lqIdx_value"]
            assert actual_uid == 8
            break
        old_trace = list(events(originals[node]))
        assert all(row["checked"] and "error" not in row for row in old_trace)
        held = {old_trace[-1]["after"][f"io_replay_{bank}_bits_uop_lqIdx_value"] for bank in range(3) if old_trace[-1]["after"][f"io_replay_{bank}_valid"]}
        assert held == {3,4,8} and prefix > 70
        corrections.append(dict(nodeid=node, common_raw_samples_before_fixed_order_wait=prefix, old_held_valid_lq_candidates=sorted(held),
                                corrected_first_additional_legal_grant_lq=actual_uid, original_trace_sha256=sha(originals[node]), corrected_trace_sha256=sha(paths[node])))
    assert len(corrections) == 3
    return corrections


def audit(name):
    run, baseline = ROOT/"results"/name, ROOT/"results/lsq-expanded-10"
    manifest, source, nodes = verify_common(run)
    old, _, old_nodes = verify_common(baseline)
    assert manifest["tests"] == {"PASS":173,"FAIL":37} and len(nodes) == 210
    assert old["tests"] == {"PASS":157,"FAIL":37} and len(old_nodes) == 194
    paths, old_paths = paths_by_node(run), paths_by_node(baseline)
    assert set(paths) == set(nodes) and set(old_paths) == set(old_nodes) <= set(nodes)
    counts, cases, visits = Counter(), [], set()
    for node,path in sorted(paths.items()):
        if node in old_nodes:
            assert nodes[node] == old_nodes[node]
            records = same_raw(path,old_paths[node])
            counts["previous194_all_raw_samples_bitwise_rechecked"] += 1
            detail = dict(raw_samples_bitwise_equal_previous=records)
        else:
            assert not nodes[node]
            if node.startswith("tests/lsq_wrapper/test_uncache_population.py::"):
                detail = inspect_uncache(path)
                visits.update(tuple(item) for item in detail["actual_mid_kind_bypass_visits"])
                counts["new_uncache_cases"] += 1
                counts["new_cancelled_original_uids"] += detail["cancelled"]
            else:
                assert "test_three_lane_two_strict_waits_" in node
                detail = inspect_replay(path,False)
                assert detail["allocated"] == detail["completed"] == 128 and len(detail["slots_by_enqueue_lane"]) == 120
                counts["new_two_ma_full_pool_cases"] += 1
            for key in ("allocated","completed"):
                counts["new_"+key] += detail[key]
            counts.update(detail["counts"])
            records = sum(1 for _ in events(path))
        counts["all_continuous_raw_records"] += records
        cases.append(dict(nodeid=node,journal=str(path.relative_to(run)),sha256=sha(path),result="FAIL" if nodes[node] else "PASS",**detail))
    assert counts["previous194_all_raw_samples_bitwise_rechecked"] == 194 and counts["new_uncache_cases"] == 15 and counts["new_two_ma_full_pool_cases"] == 1
    assert counts["new_allocated"] == 446 and counts["new_completed"] == 443 and counts["new_cancelled_original_uids"] == 3
    assert counts["actual_original_uncache_request_fires"] == counts["actual_direction_bound_id_responses"] == counts["actual_direction_and_sid_bound_responses"] == counts["actual_original_bypass_s2_data_error_consumptions"] == counts["actual_original_uncache_replay_grants"] == 306
    assert counts["two_full_16_mid_generations_actually_consumed_cases"] == 9
    assert counts["actual_cancelled_s3_done_but_not_vlq_completed_loads"] == counts["cancelled_same_lq_slot_new_uid_bus_bypass_completed"] == counts["actual_both_branch_recovery_responses"] == counts["real_nc_nuke_same_original_slot_c0_feedbacks"] == 3
    assert visits == {(mid,kind,lane) for mid in range(16) for kind in ("nc","mmio_memory","io") for lane in range(3)}
    corrections = inspect_consumer_correction(run,paths,nodes)
    dest = run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    files = (Path(__file__),ROOT/"tools/audit_lsq_population_v1.py",ROOT/"tools/audit_lsq_memory_v1.py",ROOT/"tools/audit_lsq_bus_v2.py",ROOT/"tools/audit_lsq_bus_v3.py")
    for file in files:
        copy_to=dest/file.name
        if copy_to.exists():
            assert sha(copy_to) == sha(file)
        else:
            shutil.copy2(file,copy_to)
    previous_audit = baseline/"wrap-history-audit-v1.json"
    assert json.loads(previous_audit.read_text())["tests"] == old["tests"]
    report = dict(run=name,status="NOT_PASS_210_case_full_uncache_nc_rar_and_recovery_histories_audited",tests=manifest["tests"],snapshot_files=len(source),
                  counts=dict(counts),actual_mid_kind_bypass_witnesses=len(visits),consumer_helper_corrections=corrections,
                  previous_wrap_audit_sha256=sha(previous_audit),auditor_sha256={file.name:sha(dest/file.name) for file in files},cases=cases,
                  limits="Exact210 scope: old194 raw histories unchanged, including16 explicitly protocol-only probes/all37FAIL. New15 strict Uncache cases cover real mid0..15 xNC/memoryMMIO/IO x3bypass lanes, two generations, original data/errors/VA/GP/hyper/former,306 external attempts/grants/data consumptions; NC RAR comes from actual returned/bypassed NC data, nuke triggers actual C0 re-read plus independent branch redirect, not an invented RAR-generated redirect. Three already-S3-done young Load UIDs cancel before VLQ completion and each same-LQ new UID completes; old retired Store original bytes consumed. New twoMA+TLB120 pool uses real SQ feedback. SID obligations end at resp.fire, no requirement to keep a SID until data consumption; old SID corruption FAIL not waived. Not full shared reset/all cancellation phases/random/Backend/ISA or fresh elaboration acceptance.")
    output=run/"uncache-history-audit-v1.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({key:value for key,value in report.items() if key not in ("cases","consumer_helper_corrections")},indent=2,ensure_ascii=False))


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
