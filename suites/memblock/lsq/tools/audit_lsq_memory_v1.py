#!/usr/bin/env python3
"""Independent raw memory histories for the132-case Wrapper scope.

No imports of DUT reference/actor models, no change/physical/model answer oracle.
Raw dispatch/STA/STD/S2/UQ/S3/replay/redirect/Sbuffer/deq reconstruct identity and
completion; PA bytes, full dependency identity, RAW and RAR are checked anew.
The old69 cases must match the already audited bus baseline bitwise.
"""
import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import shutil

from audit_lsq_bus_v2 import pointer, rob, rob_matches, rows, sq
from audit_lsq_bus_v3 import differences
from audit_sq_initial import ROOT, sha, verify_common


def lq(ptr):
    return 120 * int(ptr["flag"]) + ptr["value"]


def words(store):
    address, data = store["address"], store["data"]
    va, pa, length = address["vaddr"], address["paddr"], 1 << address["size"]
    result = []
    for part in range(2 if va % 16 + length > 16 else 1):
        word_va = va // 16 * 16 + 16 * part
        word_pa = store.get("second_page", pa // 16 * 16 + 16 * part) if part else pa // 16 * 16
        mask = value = 0
        for offset in range(length):
            byte = va + offset - word_va
            if 0 <= byte < 16:
                mask |= 1 << byte
                value |= (data >> (8 * offset) & 255) << (8 * byte)
        result.append((word_va, word_pa, mask, value))
    return result


def raw_payload(pre, prefix, query, address):
    rob_matches(pre, prefix + "robIdx_", query["rob"])
    rob_matches_dummy = (("ftqIdx_flag", int(query["ftq"]["flag"])), ("ftqIdx_value", query["ftq"]["value"]),
                         ("ftqOffset", query["ftq_offset"]), ("isRVC", int(query["is_rvc"])),
                         ("debug_runahead_checkpoint_id", query["checkpoint"]), ("stFtqIdx_flag", int(address["ftq"]["flag"])),
                         ("stFtqIdx_value", address["ftq"]["value"]), ("stFtqOffset", address["ftq_offset"]), ("stIsRVC", int(address["rvc"])))
    assert all(pre[prefix + name] == value for name, value in rob_matches_dummy)


def inspect_memory(trace, failed):
    stores, loads, by_lq, sequence = {}, [], {}, 0
    head = sq_tail = lq_tail = 0
    pending_s2, previous = [], None
    raw_pool, rar_pool, raw_history, rar_history = {}, {}, [[], []], [[], []]
    raw_jobs, forward_jobs, violations, redirects = {}, [], [], []
    recovery = None
    counts = Counter()

    def owner_for_rob(pointer):
        matches = [load for load in loads if not load["cancelled"] and not load["complete"] and load["rob"] == pointer]
        assert len(matches) == 1
        return matches[0]

    for index, row in enumerate(trace):
        inp, pre, post, tick = row["input"], row["before"], row["after"], row["post_tick"]
        assert not inp["reset"] or not stores and not loads
        assert not pre["io_uncache_req_valid"] and not pre["io_mmioStout_valid"] and not pre["io_cmoOpReq_valid"]
        if inp["reset"]:
            previous = row
            continue
        assert pointer(pre, "io_sqDeqPtr_") == head % 256
        # Retirement is legal only after ordinary execution, not necessarily
        # after the still separately accounted Sbuffer side effect.
        for store in stores.values():
            if rob(store["rob"]) < rob(inp["pending"]):
                assert store["data_done"] and store["s2_done"]
        for load in loads:
            if not load["cancelled"] and rob(load["rob"]) < rob(inp["pending"]):
                assert load["sent"]
        if any(d["valid"] for d in inp["dispatch"]):
            assert not pre["io_toLsqEnqCtrl_lqRecoverStall"] and not pre["io_toLsqEnqCtrl_sqRecoverStall"]
            assert recovery is None, "new dispatch before both actual recovery responses"
        for d in inp["dispatch"]:
            if not d["valid"]:
                continue
            if d["need_alloc"] == 2:
                assert 0 < d["flows"] <= 16
                for position in range(sq_tail, sq_tail + d["flows"]):
                    assert position not in stores
                    sequence += 1
                    stores[position] = dict(uid=sequence, position=position, rob=d["rob"], address_ready=False,
                                            data_ready=False, data_done=False, s2_done=False, consumed=set(), complete=False)
                sq_tail += d["flows"]
                assert sq(d["store_end"]) == sq_tail % 256 and sq_tail - head <= 128
                counts["actual_store_virtual_uops"] += 1
            else:
                assert d["need_alloc"] == 1 and d["flows"] == 1 and lq(d["load_start"]) == lq_tail
                assert lq_tail not in by_lq or by_lq[lq_tail]["complete"] or by_lq[lq_tail]["cancelled"]
                sequence += 1
                load = dict(uid=sequence, position=lq_tail, rob=d["rob"], sent=False, complete=False, cancelled=False)
                loads.append(load)
                by_lq[lq_tail] = load
                lq_tail += 1

        # The S1 translation belongs to the previous raw S0 query. Preserve a
        # stable OLD bank, not the new STA/STD writes at the current edge.
        if previous is not None:
            for lane, query in enumerate(previous["input"]["queries"]):
                if not query["valid"]:
                    continue
                translation, p = inp["translations"][lane], f"io_forward_{lane}_s2Resp_"
                if translation["kill"]:
                    assert not post[p + "valid"]
                    counts["actual_killed_forward_responses_suppressed"] += 1
                    continue
                assert post[p + "valid"] and query["vaddr"] % 4096 == translation["paddr"] % 4096
                live_candidates = [load["uid"] for load in loads if not load["complete"] and not load["cancelled"]]
                assert live_candidates
                limit = min((sq(query["sq"]) - head) % 256, 64)
                bank = [copy.deepcopy(stores[pos]) for pos in range(head, head + limit) if pos in stores]
                start, length = query["vaddr"] % 16, 1 << min(query["size"], 4)
                if post[p + "bits_dataInvalid_valid"]:
                    selected = [s for s in bank if s["address_ready"] and
                                s["address"]["vaddr"] < query["vaddr"] + length and
                                query["vaddr"] < s["address"]["vaddr"] + (1 << s["address"]["size"])]
                    assert selected and not selected[-1]["data_ready"]
                    source = selected[-1]
                    actual = pointer(post, p + "bits_dataInvalid_bits_")
                    expected = source["position"] % 256
                    if actual != expected:
                        assert head == 60 and source["position"] == 112 and sq(query["sq"]) == 128
                        violations.append(dict(issue="FWD-SQID-001", tick=tick, lane=lane, source_uid=source["uid"],
                                               expected_complete_sq=expected, actual_complete_sq=actual, raw_query=query,
                                               evidence="actual dependency changes flags, not merely a payload don't-care"))
                    else:
                        counts["independent_full_sq_data_dependency_checks"] += 1
                if post[p + "bits_addrInvalid_valid"]:
                    assert query["wait"] or query["strict"]
                    wanted = sq(query["sq"]) - 1 if query["strict"] else sq(query["wait_sq"])
                    assert pointer(post, p + "bits_addrInvalid_bits_") == wanted % 256
                    assert wanted not in stores or not stores[wanted]["address_ready"]
                    counts["independent_actual_missing_sta_dependency_checks"] += 1
                blocked = any(post[p + "bits_" + flag] for flag in ("forwardInvalid", "matchInvalid", "addrInvalid_valid", "dataInvalid_valid"))
                if blocked:
                    counts["actual_blocked_forward_queries"] += 1
                elif not any(a["valid"] for a in inp["addresses"]) and not any(d["valid"] for d in inp["data"]):
                    physical = {}
                    for store in bank:
                        if not store["address_ready"] or not store["data_ready"]:
                            continue
                        for _, pa, mask, value in words(store):
                            for byte in range(16):
                                if mask >> byte & 1:
                                    physical[pa + byte] = (store["uid"], value >> (8 * byte) & 255)
                    found = False
                    for byte in range(16):
                        if not post[p + f"bits_forwardMask_{byte}"]:
                            continue
                        assert start <= byte < start + length
                        pa = translation["paddr"] // 16 * 16 + byte
                        actual = post[p + f"bits_forwardData_{byte}"]
                        if pa not in physical or actual != physical[pa][1]:
                            issue = "FWD-RANGE-001" if pa not in physical else "FWD-ALIAS-001"
                            violations.append(dict(issue=issue, tick=tick, lane=lane, byte=byte, physical_address=pa,
                                                   original_youngest_producer=None if pa not in physical else physical[pa][0],
                                                   original_expected_byte=None if pa not in physical else physical[pa][1], actual_byte=actual,
                                                   flags_all_unblocked=True, raw_query=query))
                            found = True
                            break
                        counts["independent_original_pa_bytes_forwarded"] += 1
                    if not found:
                        counts["independent_safe_forward_responses"] += 1
                forward_jobs.append(dict(tick=tick, candidates=live_candidates, query=query, translation=translation))

        # Exact public acceptance histories implement the two revoke ages,
        # independent of FreeList/physical slot state.
        raw_revoked = {uid for age, names in ((1, inp["raw_revoke_last"]), (2, inp["raw_revoke_older"]))
                       for lane, active in enumerate(names) if active for uid in raw_history[-age] if uid is not None and uid[0] == lane}
        rar_revoked = {uid for age, names in ((1, inp["rar_revoke_last"]), (2, inp["rar_revoke_older"]))
                       for lane, active in enumerate(names) if active for uid in rar_history[-age] if uid is not None and uid[0] == lane}
        for identity in raw_revoked:
            raw_pool.pop(identity, None)
        for identity in rar_revoked:
            rar_pool.pop(identity, None)
        raw_accept, rar_accept = [], []
        ready_head = pointer(pre, "io_issuePtrExt_")
        for lane, address in enumerate(inp["addresses"]):
            if not address["valid"]:
                continue
            candidates = [item for item in raw_pool.values() if item["query"]["data_valid"] and
                          rob(item["query"]["rob"]) > rob(address["rob"]) and
                          ((item["query"]["paddr"] ^ address["paddr"]) & ((1 << 28) - 1)) >> (6 if address["wline"] else 4) == 0 and
                          item["query"]["mask"] & address["mask"]]
            winner = min(candidates, key=lambda item: rob(item["query"]["rob"]), default=None)
            raw_jobs[(index + 2, lane)] = None if address["tlb_miss"] else (winner, address)
        for lane in range(2):
            expected = raw_jobs.pop((index, lane), None)
            p = f"io_nuke_rollback_{lane}_"
            winner = expected[0] if expected else None
            assert post[p + "valid"] == int(winner is not None)
            if winner is not None:
                raw_payload(post, p + "bits_", winner["query"], expected[1])
                counts["actual_original_raw_rollbacks"] += 1
        emitted = [(lane, post[f"io_nuke_rollback_{lane}_bits_robIdx_value"]) for lane in range(2) if post[f"io_nuke_rollback_{lane}_valid"]]
        assert post["io_mdpTrain_valid"] == int(bool(emitted))
        if emitted:
            lane = min(emitted, key=lambda item: item[1])[0]
            p = f"io_nuke_rollback_{lane}_bits_"
            for out, source in (("ftqIdx_value", "ftqIdx_value"), ("ftqOffset", "ftqOffset"), ("isRVC", "isRVC"),
                                ("stFtqIdx_value", "stFtqIdx_value"), ("stFtqOffset", "stFtqOffset"), ("stIsRVC", "stIsRVC")):
                assert post["io_mdpTrain_bits_" + out] == post[p + source]
            counts["actual_oldest_original_mdp_training"] += 1
        for lane, query in enumerate(inp["raw_queries"]):
            if not query["valid"]:
                continue
            load = owner_for_rob(query["rob"])
            load["raw"] = query
            assert pre[f"io_ldu_rawNukeQuery_{lane}_req_ready"]
            if 0 < (sq(query["sq"]) - ready_head) % 256 < 128:
                identity = (lane, tick)
                raw_pool[identity] = dict(query=query, uid=load["uid"])
                raw_accept.append(identity)
                counts["actual_raw_query_allocations"] += 1
        for lane, query in enumerate(inp["rar_queries"]):
            if not query["valid"]:
                continue
            load = by_lq[lq(query["lq"])]
            assert load["rob"] == query["rob"] and not load["cancelled"]
            load["rar"] = query
            matches = [item for item in rar_pool.values() if rob(item["query"]["rob"]) > rob(query["rob"]) and
                       item["query"]["paddr"] // 64 == query["paddr"] // 64 and item["released"]]
            expected = int(bool(matches))
            p = f"io_ldu_rarNukeQuery_{lane}_resp_"
            assert post[p + "valid"]
            if post[p + "bits_nuke"] != expected:
                assert expected == 1 and post[p + "bits_nuke"] == 0 and len(matches) == 1
                item = matches[0]
                assert item["release_age"] == 1
                violations.append(dict(issue="RAR-REL-001", tick=tick, lane=lane, original_older_load_uid=load["uid"],
                                       original_younger_load_uid=item["uid"], query=query, original_query=item["query"],
                                       release_age_at_allocation=1, expected_nuke=1, actual_nuke=0))
            else:
                counts["independent_rar_original_response_checks"] += 1
            if query["data_valid"]:
                assert pre[f"io_ldu_rarNukeQuery_{lane}_req_ready"] and not query["nc"]
                release_age = next((age for age, packet in ((0, inp), (1, previous["input"]))
                                    if packet["release"]["valid"] and packet["release"]["paddr"] // 64 == query["paddr"] // 64), None)
                identity = (lane, tick)
                rar_pool[identity] = dict(uid=load["uid"], query=query, released=release_age is not None, release_age=release_age)
                rar_accept.append(identity)
                counts["actual_cached_rar_query_allocations"] += 1
        raw_history, rar_history = [raw_history[-1], raw_accept], [rar_history[-1], rar_accept]

        # Source payloads/controls only advance AFTER the old bank queries.
        for position, last in pending_s2:
            attr = inp["attributes"][last[0]]
            assert attr["memory"] and not attr["nc"] and not attr["mmio"] and not attr["exception"]
            if last[1]:
                stores[position]["s2_done"] = True
        pending_s2 = []
        for lane, address in enumerate(inp["addresses"]):
            if not address["valid"]:
                continue
            position = head + (address["slot"] - head) % 64
            store = stores[position]
            assert store["rob"] == address["rob"] and head <= position < min(head + 64, sq_tail)
            if not address["last"] or not address["cross_word"]:
                store["address"] = address
            else:
                assert "address" in store
                assert address["vaddr"] == store["address"]["vaddr"] // 16 * 16 + 16
                if address["paddr"] // 4096 != store["address"]["paddr"] // 4096:
                    assert store.get("second_page") == address["paddr"]
            store["address_ready"] = address["last"] and not address["tlb_miss"]
            if not address["tlb_miss"]:
                pending_s2.append((position, (lane, address["last"])))
        for data in inp["data"]:
            if data["valid"]:
                position = sq(data["sq"])
                assert head <= position < min(head + 64, sq_tail) and not stores[position]["data_done"]
                stores[position].update(data=data["data"], data_ready=True, data_done=True)
        for lane, page in enumerate(inp["second_pages"]):
            if page["valid"] and pre[f"io_sta_unalignQueueReq_{lane}_ready"]:
                position = sq(page["sq"])
                assert position in stores and "second_page" not in stores[position]
                stores[position]["second_page"] = page["paddr"]
                counts["actual_original_uq_second_page_accepts"] += 1
        for packet in inp["loads"]:
            q = packet["execution"]
            if not q["valid"]:
                continue
            load = by_lq[lq(q["uop"]["lq"])]
            assert load["rob"] == q["uop"]["rob"] and not load["cancelled"] and not load["complete"]
            if "s3" in load:
                assert q["uop"] == load["s3"]["execution"]["uop"]
            load["s3"] = packet
            if "raw" in load:
                raw = load["raw"]
                assert packet["paddr"] == raw["paddr"] and q["mask"] == raw["mask"] and q["uop"]["sq"] == raw["sq"]
            if q["replay_feedback"]:
                assert load.get("grant") == q["slot"] and not q["need_replay"]
                counts["actual_original_replay_slot_feedbacks"] += 1
            if not q["need_replay"] and packet["update_address"]:
                assert not load["sent"]
                load["sent"] = True
        for bank in range(3):
            p = f"io_replay_{bank}_"
            if pre[p + "valid"] and inp["replay_ready"][bank]:
                key = 120 * pre[p + "bits_uop_lqIdx_flag"] + pre[p + "bits_uop_lqIdx_value"]
                load = by_lq[key]
                rob_matches(pre, p + "bits_uop_robIdx_", load["rob"])
                assert "s3" in load and load["s3"]["execution"]["need_replay"] and "grant" not in load
                load["grant"] = pre[p + "bits_replayQueueIdx"]
                assert load["grant"] % 3 == bank
                counts["actual_original_load_replay_grants"] += 1
        for lane in range(2):
            p = f"io_sbuffer_req_{lane}_"
            if not (pre[p + "valid"] and inp["sbuffer_ready"][lane]):
                continue
            position, part = next((pos, part) for pos, store in stores.items() for part in range(len(words(store)))
                                  if not store["complete"] and part not in store["consumed"])
            store = stores[position]
            va, pa, mask, value = words(store)[part]
            assert pre[p + "bits_vaddr"] == va and pre[p + "bits_addr"] == pa and pre[p + "bits_mask"] == mask and not pre[p + "bits_wline"]
            byte_mask = sum(255 << (8 * byte) for byte in range(16) if mask >> byte & 1)
            assert not ((pre[p + "bits_data"] ^ value) & byte_mask)
            store["consumed"].add(part)
            store["last_fire"] = tick
            counts["independent_original_sbuffer_fragments_consumed"] += 1
        delta = (pointer(post, "io_sqDeqPtr_") - head) % 256
        assert delta <= 2 and post["io_toLsqEnqCtrl_sqDeq_valid"] == int(bool(delta))
        if delta:
            assert post["io_toLsqEnqCtrl_sqDeq_bits"] == delta
        for position in range(head, head + delta):
            store = stores[position]
            assert not store["complete"] and store["s2_done"] and store["data_done"]
            assert store["consumed"] == set(range(len(words(store)))) and store["last_fire"] + 2 == tick
            store.update(complete=True, address_ready=False, data_ready=False)
            counts["actual_original_store_uids_completed"] += 1
        head += delta
        if inp["redirect"]["valid"]:
            cutoff = rob(inp["redirect"]["rob"])
            assert all(rob(store["rob"]) < cutoff for store in stores.values())
            assert any(post[f"io_nuke_rollback_{lane}_valid"] or (previous is not None and previous["after"][f"io_nuke_rollback_{lane}_valid"]) for lane in range(2))
            victims = [load for load in loads if not load["complete"] and not load["cancelled"] and rob(load["rob"]) >= cutoff]
            assert victims and all(not load["sent"] for load in victims)
            for load in victims:
                load["cancelled"] = True
            recovery = dict(cutoff=cutoff, victims=[v["uid"] for v in victims], lq=None, sq=None)
            redirects.append(recovery)
            counts["actual_cancelled_original_load_uids"] += len(victims)
        if recovery is not None:
            if post["io_toLsqEnqCtrl_lqRedirectPtr_valid"]:
                recovery["lq"] = 120 * post["io_toLsqEnqCtrl_lqRedirectPtr_bits_flag"] + post["io_toLsqEnqCtrl_lqRedirectPtr_bits_value"]
                lq_tail = recovery["lq"]
            if post["io_toLsqEnqCtrl_sqRedirectPtr_valid"]:
                recovery["sq"] = 128 * post["io_toLsqEnqCtrl_sqRedirectPtr_bits_first_flag"] + 64 * post["io_toLsqEnqCtrl_sqRedirectPtr_bits_second_flag"] + post["io_toLsqEnqCtrl_sqRedirectPtr_bits_value"]
                assert recovery["sq"] == sq_tail
            if recovery["lq"] is not None and recovery["sq"] is not None and not post["io_toLsqEnqCtrl_lqRecoverStall"] and not post["io_toLsqEnqCtrl_sqRecoverStall"]:
                counts["actual_both_queue_recovery_responses"] += 1
                recovery = None
        if post["io_toLsqEnqCtrl_lqDeq_valid"]:
            count = post["io_toLsqEnqCtrl_lqDeq_bits"]
            live = [load for load in loads if not load["complete"] and not load["cancelled"]]
            assert 0 < count <= len(live)
            for load in live[:count]:
                assert load["sent"]
                load["complete"] = True
            counts["actual_original_load_uids_completed"] += count
        raw_pool = {identity: entry for identity, entry in raw_pool.items() if (sq(entry["query"]["sq"]) - ready_head) % 256 not in (0,)}
        previous = row

    for job in forward_jobs:
        # Bind the forwarded transaction to retained raw S3 metadata wherever
        # it exists. Failed cases have one unambiguous live dispatched Load.
        candidates = [load for load in loads if load["uid"] in job["candidates"] and ("s3" not in load or
                      load["s3"]["execution"]["vaddr"] == job["query"]["vaddr"] and load["s3"]["execution"]["uop"]["sq"] == job["query"]["sq"])]
        if any("s3" in load for load in candidates):
            candidates = [load for load in candidates if "s3" in load]
        assert len(candidates) == 1
        if "s3" in candidates[0]:
            assert candidates[0]["s3"]["paddr"] == job["translation"]["paddr"]
        counts["actual_forward_queries_bound_to_dispatched_load_uid"] += 1
    for load in loads:
        if load["cancelled"]:
            new = next((new for new in loads if new["uid"] != load["uid"] and new["position"] % 120 == load["position"] % 120 and new["complete"]), None)
            assert new is not None
            counts["cancelled_same_lq_slot_new_uid_actually_completed"] += 1
    remaining = sum(not store["complete"] for store in stores.values()) + sum(not load["complete"] and not load["cancelled"] for load in loads)
    if failed:
        assert len(violations) == 1 and violations[0]["tick"] == trace[-1]["post_tick"] and remaining
        counts["independently_reproduced_" + violations[0]["issue"]] += 1
    else:
        assert not violations and not remaining and recovery is None
        assert trace[-1]["after"]["io_lqEmpty"] and trace[-1]["after"]["io_sqEmpty"] and not trace[-1]["after"]["io_replayAllocate"]
        counts["new_cases_all_original_obligations_drained"] += 1
    counts["new_allocated_original_uids"] += len(stores) + len(loads)
    counts["new_failure_retained_original_uids"] += remaining
    return counts, dict(violations=violations, allocated=len(stores) + len(loads), completed=sum(s["complete"] for s in stores.values()) + sum(l["complete"] for l in loads),
                        cancelled=sum(l["cancelled"] for l in loads), failure_retained=remaining, actual_recoveries=redirects)


def audit(name):
    run, baseline = ROOT / "results" / name, ROOT / "results/lsq-expanded-04"
    manifest, source, nodes = verify_common(run)
    _, _, old_nodes = verify_common(baseline)
    assert manifest["tests"] == {"PASS": 107, "FAIL": 25} and len(nodes) == 132
    old_path = baseline / "bus-history-audit-v3.json"
    old_audit = json.loads(old_path.read_text())
    assert old_audit["tests"] == {"PASS": 59, "FAIL": 10}
    for file, digest in old_audit["auditor_sha256"].items():
        assert sha(baseline / "evidence-auditors" / file) == digest
    old = {case["nodeid"]: baseline / case["journal"] for case in old_audit["cases"]}
    assert set(old) == set(old_nodes)
    counts, cases, seen = Counter(), [], set()
    for path in sorted((run / "cases").rglob("lsq_wrapper.jsonl")):
        trace = rows(path)
        node, last = trace[0]["nodeid"], None
        assert node in nodes and node not in seen and all(row["nodeid"] == node for row in trace)
        seen.add(node)
        by_tick = {}
        for i, row in enumerate(trace):
            tick = row["post_tick"]
            assert row["pre_tick"] + 1 == tick and (last is None or last + 2 == tick)
            assert len(row["pins"]) == 603 and row["pins"] == row["post_pins"] and len(row["before"]) == len(row["after"]) == 458
            assert not row["explicitly_unimplemented_outputs"]
            if nodes[node] and i == len(trace) - 1:
                assert not row["checked"] and "AssertionError" in row["error"]
            else:
                assert row["checked"] and not any(differences(row).values())
            by_tick[tick], last = row, tick
        for check in rows(path.with_name("lsq_checks.jsonl")):
            actual = by_tick[check["tick"]][check["phase"]]
            assert check["passed"] and check["actual"] == {key: actual[key] for key in check["expected"]}
            assert not any((actual[key] ^ value) & check["masks"].get(key, -1) for key, value in check["expected"].items())
        counts["continuous_full_pin_records"] += len(trace)
        detail = {}
        if node in old:
            assert nodes[node] == old_nodes[node]
            base = rows(old[node])
            assert len(trace) == len(base)
            assert all(all(a[key] == b[key] for key in ("pre_tick", "post_tick", "input", "pins", "post_pins", "before", "after")) for a, b in zip(trace, base, strict=True))
            counts["previous_69_cases_all_raw_samples_bitwise_rechecked"] += 1
        else:
            assert node.startswith(("tests/lsq_wrapper/test_forward_memory.py::", "tests/lsq_wrapper/test_nuke_memory.py::"))
            checked, detail = inspect_memory(trace, nodes[node])
            counts.update(checked)
        cases.append(dict(nodeid=node, journal=str(path.relative_to(run)), sha256=sha(path), result="FAIL" if nodes[node] else "PASS", **detail))
    assert seen == set(nodes) and counts["previous_69_cases_all_raw_samples_bitwise_rechecked"] == 69
    assert {issue: counts["independently_reproduced_" + issue] for issue in ("FWD-ALIAS-001", "FWD-RANGE-001", "FWD-SQID-001", "RAR-REL-001")} == {
        "FWD-ALIAS-001": 3, "FWD-RANGE-001": 6, "FWD-SQID-001": 3, "RAR-REL-001": 3}
    assert counts["new_cases_all_original_obligations_drained"] == 48
    assert counts["actual_cancelled_original_load_uids"] == counts["cancelled_same_lq_slot_new_uid_actually_completed"] == 4
    assert counts["actual_both_queue_recovery_responses"] == 2
    assert counts["actual_original_raw_rollbacks"] == 4 and counts["actual_oldest_original_mdp_training"] == 2
    dest = run / "evidence-auditors" / Path(__file__).name
    dest.parent.mkdir(exist_ok=True)
    for file in (Path(__file__), ROOT / "tools/audit_lsq_bus_v2.py", ROOT / "tools/audit_lsq_bus_v3.py"):
        copy_to = dest.parent / file.name
        if copy_to.exists():
            assert sha(copy_to) == sha(file)
        else:
            shutil.copy2(file, copy_to)
    report = dict(run=name, status="NOT_PASS_real_mixed_forward_raw_rar_histories_audited", tests=manifest["tests"], counts=dict(counts),
                  snapshot_files=len(source), previous_69_audit_sha256=sha(old_path),
                  auditor_sha256={file: sha(dest.parent / file) for file in (Path(__file__).name, "audit_lsq_bus_v2.py", "audit_lsq_bus_v3.py")}, cases=cases,
                  limits="Exact new63 directed ordinary cached memory scope plus old69 bitwise baseline, not capacity/full-slot/random/reset/CBO acceptance. Independent PA bytes apply stable banks and unblocked responses, no invented LDU/cache result-data port; full-cycle model comparisons also cover live stages/perf. New RAW uses actual shared STA and actual oldest rollback/shared redirect, four cancelled Load UIDs each have same-LQ new completed UID. RAR cases use cached real Load identities, not a fake NC tag. Blocked forward/control cases are not claimed as successful byte consumption; aliases/range/SQ identity/previous release keep ordinary FAIL. No full Backend/elaboration or architecture damage assertion.")
    output = run / "memory-history-audit-v1.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
