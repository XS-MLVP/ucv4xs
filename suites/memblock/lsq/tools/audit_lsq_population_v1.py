#!/usr/bin/env python3
"""Independent172-case raw audit: old132 bitwise + Replay20 + special Store20.

Only raw dispatch/STA/STD/S2/S3/hints/fire/deq are semantic inputs. No DUT or
reference-model imports, no actor/outcome/change data as a correctness oracle.
The explicit protocol probe never earns a full-cycle-reference comparison.
"""
import argparse
from collections import Counter
import itertools
import json
from pathlib import Path
import shutil

from audit_lsq_bus_v2 import pointer, rob, rob_matches, sq
from audit_lsq_bus_v3 import differences
from audit_lsq_memory_v1 import lq, words
from audit_sq_initial import ROOT, sha, verify_common


RAW = ("pre_tick", "post_tick", "input", "pins", "post_pins", "before", "after")


def events(path):
    with path.open() as stream:
        for line in stream:
            yield json.loads(line)


def paths_by_node(run):
    result = {}
    for filename in ("lsq_wrapper.jsonl", "lsq_probe.jsonl"):
        for path in (run / "cases").rglob(filename):
            node = next(events(path))["nodeid"]
            assert node not in result
            result[node] = path
    return result


def same_raw(first, second):
    count = 0
    for a, b in itertools.zip_longest(events(first), events(second)):
        assert a is not None and b is not None and all(a[key] == b[key] for key in RAW), (first, second, count)
        count += 1
    return count


def validate_row(row, previous, probe):
    assert row["pre_tick"] + 1 == row["post_tick"]
    assert previous is None or previous["post_tick"] + 2 == row["post_tick"]
    assert len(row["pins"]) == 603 and row["pins"] == row["post_pins"]
    assert len(row["before"]) == len(row["after"]) == 458
    if probe:
        assert not row["checked"] and row["full_cycle_reference_compared"] is False
        assert row["scope"] == "explicit_public_protocol_original_uid_probe_not_full_output_reference"
    else:
        assert not row["explicitly_unimplemented_outputs"]
        assert row["checked"] == ("error" not in row)
        if row["checked"]:
            assert not any(differences(row).values())


def replay_metadata(pins, prefix, load):
    q, u = load["execution"], load["execution"]["uop"]
    rob_matches(pins, prefix + "uop_robIdx_", u["rob"])
    assert pointer(pins, prefix + "uop_sqIdx_") == sq(u["sq"])
    assert pointer(pins, prefix + "uop_waitSqIdx_") == sq(u["wait_sq"])
    expected = {"vaddr": q["vaddr"], "fullva": load["fullva"], "mask": q["mask"],
                "uop_lqIdx_flag": int(u["lq"]["flag"]), "uop_lqIdx_value": u["lq"]["value"],
                "uop_ftqPtr_flag": int(u["ftq"]["flag"]), "uop_ftqPtr_value": u["ftq"]["value"],
                "uop_ftqOffset": u["offset"], "uop_isRVC": int(u["rvc"]), "uop_fuOpType": u["operation"],
                "uop_pdest": u["destination"], "uop_rfWen": int(u["integer_write"]), "uop_fpWen": int(u["fp_write"]),
                "uop_vecWen": int(u["vector_write"]), "uop_v0Wen": int(u["v0_write"]),
                "uop_storeSetHit": int(u["store_set_hit"]), "uop_loadWaitBit": int(u["load_wait"]),
                "uop_loadWaitStrict": int(u["strict"]), "uop_perfDebugInfo_runahead_checkpoint_id": u["checkpoint"]}
    expected.update({f"uop_exceptionVec_{bit}": int(bool(u["exceptions"] >> bit & 1)) for bit in (23, 19, 15, 7, 6)})
    assert all(pins[prefix + key] == value for key, value in expected.items())
    if q["handled"]:
        assert pins[prefix + "mshrId"] == q["mshr"]


def inspect_replay(path, failed):
    stores, loads, active, grants = {}, [], {}, set()
    ltail = stail = head = 0
    pending_s2, previous = [], None
    tlb, refill, address_wake = set(), set(), set()
    counter, latched, special_head, last_head = 0, False, None, None
    counts, witnesses, violations = Counter(), set(), []
    trigger_tick = None
    for row in events(path):
        validate_row(row, previous, False)
        inp, pre, post, tick = row["input"], row["before"], row["after"], row["post_tick"]
        assert not inp["redirect"]["valid"] and not pre["io_uncache_req_valid"] and not pre["io_cmoOpReq_valid"] and not pre["io_mmioStout_valid"]
        if inp["reset"]:
            assert not stores and not loads
            counter, latched, last_head = 0, False, None
            previous = row
            continue
        for store in stores.values():
            if rob(store["rob"]) < rob(inp["pending"]):
                assert store.get("s2_done") and "data" in store
        for load in loads:
            if rob(load["rob"]) < rob(inp["pending"]):
                assert load["sent"]
        for lane, d in enumerate(inp["dispatch"]):
            if not d["valid"]:
                continue
            assert not pre["io_toLsqEnqCtrl_lqRecoverStall"] and not pre["io_toLsqEnqCtrl_sqRecoverStall"]
            assert 0 < d["flows"] <= 16
            if d["need_alloc"] == 2:
                for pos in range(stail, stail + d["flows"]):
                    stores[pos] = dict(position=pos, rob=d["rob"], consumed=set(), complete=False)
                stail += d["flows"]
                assert sq(d["store_end"]) == stail % 256 and stail - head <= 128
            else:
                assert d["need_alloc"] == 1 and lq(d["load_start"]) == ltail % 240
                assert sum(not load["complete"] for load in loads) + d["flows"] <= 120
                for pos in range(ltail, ltail + d["flows"]):
                    key = pos % 240
                    assert key not in active or active[key]["complete"]
                    load = dict(position=pos, rob=d["rob"], sent=False, complete=False, lane=lane)
                    loads.append(load)
                    active[key] = load
                ltail += d["flows"]
                counts["actual_load_dispatch_lane_" + str(lane)] += d["flows"]
        for pos, lane, last in pending_s2:
            attr = inp["attributes"][lane]
            assert attr["memory"] and not attr["nc"] and not attr["mmio"] and not attr["exception"]
            if last:
                stores[pos]["s2_done"] = True
        pending_s2 = []
        for lane, address in enumerate(inp["addresses"]):
            if address["valid"]:
                pos = head + (address["slot"] - head) % 64
                assert pos in stores and stores[pos]["rob"] == address["rob"] and not address["cross_word"] and not address["tlb_miss"]
                stores[pos]["address"] = address
                pending_s2.append((pos, lane, address["last"]))
        for data in inp["data"]:
            if data["valid"]:
                pos = sq(data["sq"])
                assert pos in stores and "data" not in stores[pos]
                stores[pos]["data"] = data["data"]
        for hint in (inp["slow_tlb"], inp["fast_tlb"]):
            if hint["valid"]:
                tlb.update(range(16) if hint["replay_all"] else (hint["identity"],))
        refill.update(r["mshr"] for r in inp["refills"] if r["valid"])
        address_wake.update(sq(w["sq"]) for w in inp["address_wakeups"] if w["valid"])
        trigger = False
        for lane, packet in enumerate(inp["loads"]):
            q = packet["execution"]
            if not q["valid"]:
                continue
            load = active[lq(q["uop"]["lq"])]
            assert load["rob"] == q["uop"]["rob"] and not load["complete"]
            if q["replay_feedback"]:
                assert load["grant"] == q["slot"] and not q["need_replay"]
                assert load["packet"]["execution"]["uop"] == q["uop"]
                counts["actual_original_slot_feedbacks"] += 1
            else:
                assert "packet" not in load
                load.update(packet=packet, enqueue_lane=lane)
            if not q["need_replay"] and packet["update_address"]:
                assert not load["sent"]
                load["sent"] = True
            if q["special_eligible"] and q["uop"]["rob"] == inp["pending_next"]:
                trigger = True
                if trigger_tick is None:
                    trigger_tick = tick
        for bank in range(3):
            p = f"io_replay_{bank}_"
            if pre[p + "valid"] and inp["replay_ready"][bank]:
                load = active[120 * pre[p + "bits_uop_lqIdx_flag"] + pre[p + "bits_uop_lqIdx_value"]]
                assert not load["complete"] and "grant" not in load and load["packet"]["execution"]["need_replay"]
                replay_metadata(pre, p + "bits_", load["packet"])
                slot = pre[p + "bits_replayQueueIdx"]
                assert slot < 120 and slot % 3 == bank and slot not in grants
                grants.add(slot)
                witnesses.add((slot, load["enqueue_lane"]))
                load["grant"] = slot
                counts["actual_original_replay_grants"] += 1
            if post[p + "valid"]:
                load = active[120 * post[p + "bits_uop_lqIdx_flag"] + post[p + "bits_uop_lqIdx_value"]]
                q = load["packet"]["execution"]
                if q["causes"] == 4:
                    dep = sq(q["address_sq"])
                    passed = 0 < (pointer(post, "io_issuePtrExt_") - dep) % 256 < 128
                    allowed = passed or dep in address_wake or not q["uop"]["strict"] and "address" in stores[dep]
                    if not allowed:
                        assert q["uop"]["strict"] and pointer(post, "io_issuePtrExt_") == 0 and "address" in stores[1]
                        violations.append(dict(issue="LRQ-STRICT-001", tick=tick, bank=bank, lq=load["position"], dependency=dep,
                                               actual_ready_pointer=0, actual_ready_slot=1, actual_replay_valid=1, expected_valid=0))
                elif q["causes"] == 8:
                    assert q["tlb_id"] in tlb
                elif q["causes"] == 64:
                    assert q["mshr"] in refill
        # Independent public elapsed-head window, including its one-edge output.
        assert post["io_specialMode"] == int(latched and inp["pending_next"] == special_head)
        if post["io_specialMode"]:
            assert trigger_tick is not None and tick >= trigger_tick + 4096
            counts["actual_special_mode_high_samples"] += 1
        if last_head is not None and inp["pending_next"] != last_head:
            counter, latched = 0, False
        elif not latched and (trigger or counter):
            if counter == 2047:
                latched, special_head = True, inp["pending_next"]
            else:
                counter += 1
        last_head = inp["pending_next"]
        for lane in range(2):
            p = f"io_sbuffer_req_{lane}_"
            if pre[p + "valid"] and inp["sbuffer_ready"][lane]:
                store = next(s for s in stores.values() if not s["consumed"])
                va, pa, mask, value = words(store)[0]
                assert pre[p + "bits_vaddr"] == va and pre[p + "bits_addr"] == pa and pre[p + "bits_mask"] == mask and not pre[p + "bits_wline"]
                bits = sum(255 << (8 * byte) for byte in range(16) if mask >> byte & 1)
                assert not ((pre[p + "bits_data"] ^ value) & bits)
                store.update(consumed={0}, last_fire=tick)
                counts["actual_original_store_fragments"] += 1
        delta = (pointer(post, "io_sqDeqPtr_") - head) % 256
        assert delta <= 2 and post["io_toLsqEnqCtrl_sqDeq_valid"] == int(bool(delta))
        if delta:
            assert post["io_toLsqEnqCtrl_sqDeq_bits"] == delta
        for pos in range(head, head + delta):
            store = stores[pos]
            assert store["consumed"] == {0} and store["last_fire"] + 2 == tick and store.get("s2_done")
            store["complete"] = True
        head += delta
        if post["io_toLsqEnqCtrl_lqDeq_valid"]:
            count = post["io_toLsqEnqCtrl_lqDeq_bits"]
            live = [load for load in loads if not load["complete"]]
            assert 0 < count <= len(live)
            for load in live[:count]:
                assert load["sent"]
                load["complete"] = True
        previous = row
        counts["raw_records"] += 1
    complete = sum(s["complete"] for s in stores.values()) + sum(l["complete"] for l in loads)
    allocated = len(stores) + len(loads)
    if failed:
        assert len(violations) == 1 and violations[0]["tick"] == previous["post_tick"] and allocated > complete
        assert not previous["checked"] and previous["error"].startswith("AssertionError")
    else:
        assert not violations and complete == allocated and previous["after"]["io_lqEmpty"] and previous["after"]["io_sqEmpty"]
        assert not previous["after"]["io_replayAllocate"]
    if "test_full_120_" in previous["nodeid"] or "test_real_vlq_head_" in previous["nodeid"]:
        assert grants == set(range(120))
        counts["all_120_slots_really_granted_feedback_drained_cases"] += 1
    if "test_each_dispatch_source_" in previous["nodeid"]:
        assert len(loads) == 960 and all(counts["actual_load_dispatch_lane_" + str(lane)] == 120 for lane in range(8))
        assert {load["position"] % 240 for load in loads} == set(range(240))
        counts["all_8_dispatch_lanes_120_flows_all_lq_flags_completed"] += 1
    return dict(allocated=allocated, completed=complete, failure_retained=allocated - complete, violations=violations,
                slots_by_enqueue_lane=sorted(witnesses), counts=dict(counts))


def inspect_special(path, failed):
    stores, loads, pending_s2 = [], [], []
    head = semantic_head = 0
    previous, cache_pending, bus = None, None, None
    violations, cache, wbs, fragments, releases = [], [], [], [], []
    counts = Counter()

    def ready(store):
        if "attribute" not in store or "address" not in store or "data" not in store:
            return False
        if store["attribute"]["nc"]:
            return store.get("ack") is not None
        if store["attribute"]["mmio"]:
            return store.get("response") is not None and store.get("wb_correct", False)
        if store["address"]["fu_op"] & 1:
            cbo = store["address"]["fu_op"] >> 1 & 7
            return store.get("wb_correct", False) and (store["consumed"] == {0} if cbo == 3 else store.get("cache_response") is not None)
        return store["consumed"] == set(range(len(words(store))))

    for row in events(path):
        probe = path.name == "lsq_probe.jsonl"
        validate_row(row, previous, probe)
        inp, pre, post, tick = row["input"], row["before"], row["after"], row["post_tick"]
        assert not inp["redirect"]["valid"]
        if inp["reset"]:
            assert not stores and not loads
            previous = row
            continue
        for store in stores:
            if rob(store["rob"]) < rob(inp["pending"]):
                assert store.get("s2_done") and "data" in store
                if store["address"]["fu_op"] & 1 or store["attribute"]["nc"] or store["attribute"]["mmio"]:
                    assert ready(store)
        for d in inp["dispatch"]:
            if not d["valid"]:
                continue
            assert d["flows"] == 1
            if d["need_alloc"] == 2:
                stores.append(dict(position=len(stores), rob=d["rob"], consumed=set(), released=False))
                assert sq(d["store_end"]) == len(stores)
            else:
                assert d["need_alloc"] == 1 and lq(d["load_start"]) == len(loads)
                loads.append(dict(rob=d["rob"], sent=False, complete=False))
        for pos, lane, last in pending_s2:
            attr = inp["attributes"][lane]
            assert not attr["exception"] and attr["last"] == last
            stores[pos]["attribute"] = attr
            if last:
                stores[pos]["s2_done"] = True
        pending_s2 = []
        for lane, address in enumerate(inp["addresses"]):
            if address["valid"]:
                store = stores[address["slot"]]
                assert address["rob"] == store["rob"] and not address["tlb_miss"]
                if not address["cross_word"] or not address["last"]:
                    assert "address" not in store
                    store["address"] = address
                else:
                    assert store["address"]["cross_word"] and address["vaddr"] == store["address"]["vaddr"] // 16 * 16 + 16
                pending_s2.append((store["position"], lane, address["last"]))
        for data in inp["data"]:
            if data["valid"]:
                store = stores[sq(data["sq"])]
                assert "data" not in store
                store["data"] = 0 if data["fu_op"] & 1 and (data["fu_op"] >> 1 & 7) == 3 else data["data"]
        for packet in inp["loads"]:
            q = packet["execution"]
            if q["valid"]:
                load = loads[lq(q["uop"]["lq"])]
                assert load["rob"] == q["uop"]["rob"] and not q["need_replay"] and packet["update_address"] and not load["sent"]
                load["sent"] = True
        for lane in range(2):
            p = f"io_sbuffer_req_{lane}_"
            if not (pre[p + "valid"] and inp["sbuffer_ready"][lane]):
                continue
            matches = [(s, part, word) for s in stores if "address" in s and "data" in s
                       for part, word in enumerate(words(s)) if pre[p + "bits_vaddr"] == word[0] and pre[p + "bits_addr"] == word[1]]
            assert len(matches) == 1
            store, part, word = matches[0]
            assert part not in store["consumed"] and store["s2_done"]
            bits = sum(255 << (8 * byte) for byte in range(16) if word[2] >> byte & 1)
            assert pre[p + "bits_mask"] == word[2] and not ((pre[p + "bits_data"] ^ word[3]) & bits)
            zero = bool(store["address"]["fu_op"] & 1) and (store["address"]["fu_op"] >> 1 & 7) == 3
            correct = pre[p + "bits_wline"] == int(zero)
            if correct:
                store["consumed"].add(part)
            else:
                violations.append(dict(issue="DEQ-SPLIT-WLINE-001", tick=tick, position=store["position"], part=part,
                                       actual_wline=pre[p + "bits_wline"], expected_wline=int(zero), actual_fire=True))
            fragments.append(dict(tick=tick, position=store["position"], part=part, lane=lane, correct=correct,
                                  vaddr=word[0], paddr=word[1], data=pre[p + "bits_data"], mask=word[2], wline=pre[p + "bits_wline"]))
        if pre["io_cmoOpReq_valid"] and inp["cache_ready"]:
            store = next(s for s in stores if s["address"]["paddr"] == pre["io_cmoOpReq_bits_address"])
            assert store["rob"] == inp["pending"] and pre["io_cmoOpReq_bits_opcode"] == store["address"]["fu_op"] >> 1 & 7
            assert cache_pending is None
            cache_pending = store
            cache.append(dict(request_tick=tick, position=store["position"], opcode=pre["io_cmoOpReq_bits_opcode"]))
        if inp["cache_response"]:
            assert cache_pending is not None and pre["io_cmoOpResp_ready"]
            cache_pending["cache_response"] = dict(tick=tick, denied=int(inp["cache_denied"]), corrupt=int(inp["cache_corrupt"]))
            cache[-1].update(response_tick=tick, denied=inp["cache_denied"], corrupt=inp["cache_corrupt"])
            cache_pending = None
        if pre["io_uncache_req_valid"] and inp["bus"]["ready"]:
            store = next(s for s in stores if s["address"]["paddr"] == pre["io_uncache_req_bits_addr"])
            assert bus is None and store["rob"] == inp["pending"] and (store["attribute"]["nc"] or store["attribute"]["mmio"])
            rob_matches(pre, "io_uncache_req_bits_robIdx_", store["rob"])
            assert pre["io_uncache_req_bits_cmd"] == 1 and pre["io_uncache_req_bits_data"] == store["data"]
            assert pre["io_uncache_req_bits_nc"] == int(store["attribute"]["nc"]) and pre["io_uncache_req_bits_mask"] == 255
            bus = dict(position=store["position"], mid=pre["io_uncache_req_bits_id"], request_tick=tick)
        if inp["bus"]["ack"]:
            assert bus is not None and not inp["bus"]["ack_to_load"] and bus["mid"] == inp["bus"]["mid"] and "sid" not in bus
            bus.update(sid=inp["bus"]["sid"], ack_tick=tick)
            stores[bus["position"]]["ack"] = tick
        if inp["bus"]["response"]:
            assert bus is not None and "sid" in bus and "response_tick" not in bus
            assert not inp["bus"]["response_to_load"] and bus["sid"] == inp["bus"]["response_id"]
            bus["response_tick"] = tick
            stores[bus["position"]]["response"] = tick
        if pre["io_mmioStout_valid"] and inp["writeback_ready"]:
            store = next(s for s in stores if pre["io_mmioStout_bits_robIdx_value"] == s["rob"]["value"])
            rob_matches(pre, "io_mmioStout_bits_robIdx_", store["rob"])
            assert store["rob"] == inp["pending"] and "wb_correct" not in store
            fault = store.get("cache_response", {"denied": 0, "corrupt": 0})
            actual = [pre["io_mmioStout_bits_exceptionVec_7"], pre["io_mmioStout_bits_exceptionVec_19"]]
            expected = [fault["denied"], fault["corrupt"]]
            store["wb_correct"] = actual == expected
            assert pre["io_stExceptionInfo_bits_vaddr"] == store["address"]["vaddr"]
            assert pre["io_stExceptionInfo_bits_isHyper"] == int(store["address"]["hyper"])
            wbs.append(dict(tick=tick, position=store["position"], actual_exception_7_19=actual, expected_exception_7_19=expected))
            if actual != expected:
                violations.append(dict(issue="DEQ-WB-001", tick=tick, actual=actual, expected=expected, actual_wb_fire=True))
            if store["address"]["fu_op"] & 1 and (store["address"]["fu_op"] >> 1 & 7) == 3 and store["consumed"] != {0}:
                violations.append(dict(issue="DEQ-ZERO-001", tick=tick, position=store["position"], own_zero_fires=0, actual_wb_fire=True))
        delta = (pointer(post, "io_sqDeqPtr_") - head) % 256
        assert delta <= 2 and post["io_toLsqEnqCtrl_sqDeq_valid"] == int(bool(delta))
        if delta:
            assert post["io_toLsqEnqCtrl_sqDeq_bits"] == delta
        for pos in range(head, head + delta):
            stores[pos]["released"] = True
            safe = pos == semantic_head and ready(stores[pos])
            if safe:
                semantic_head += 1
            elif not stores[pos]["address"]["fu_op"] & 1 and not stores[pos]["attribute"]["nc"] and not stores[pos]["attribute"]["mmio"]:
                violations.append(dict(issue="DEQ-FINISH-ORDER-001", tick=tick, released_position=pos,
                                       consumed_fragments=len(stores[pos]["consumed"]), actual_sq_head=head + delta))
            releases.append(dict(tick=tick, position=pos, safe_contiguous_prefix=safe))
        head += delta
        if post["io_toLsqEnqCtrl_lqDeq_valid"]:
            count = post["io_toLsqEnqCtrl_lqDeq_bits"]
            assert count == 1 and len(loads) == 1 and loads[0]["sent"] and not loads[0]["complete"]
            loads[0]["complete"] = True
        previous = row
        counts["raw_records"] += 1
    issues = sorted({v["issue"] for v in violations})
    if failed:
        assert len(issues) == 1
    else:
        assert not issues and semantic_head == len(stores) and all(l["complete"] for l in loads)
        assert previous["after"]["io_lqEmpty"] and previous["after"]["io_sqEmpty"] and (bus is None or "response_tick" in bus)
    return dict(allocated=len(stores) + len(loads), actual_sq_released=head, semantic_store_prefix=semantic_head,
                original_loads_completed=sum(l["complete"] for l in loads),
                external_response_obligations_retained=int(bus is not None and "response_tick" not in bus),
                violations=violations, issues=issues, actual_cache=cache, actual_wbs=wbs, actual_fragments=fragments,
                actual_releases=releases, actual_bus=bus, counts=dict(counts))


def audit(name):
    run, baseline = ROOT / "results" / name, ROOT / "results/lsq-expanded-06"
    manifest, source, nodes = verify_common(run)
    old_manifest, _, old_nodes = verify_common(baseline)
    assert manifest["tests"] == {"PASS": 136, "FAIL": 36} and len(nodes) == 172
    assert old_manifest["tests"] == {"PASS": 107, "FAIL": 25} and len(old_nodes) == 132
    base_audits = {}
    for file in ("memory-history-audit-v1.json", "control-helper-correction-audit-v1.json"):
        value = json.loads((baseline / file).read_text())
        assert value["tests"] == old_manifest["tests"]
        base_audits[file] = sha(baseline / file)
    old_paths, paths = paths_by_node(baseline), paths_by_node(run)
    assert set(paths) == set(nodes) and set(old_paths) == set(old_nodes) <= set(nodes)
    counts, cases, slots, issue_counts = Counter(), [], set(), Counter()
    for node, path in sorted(paths.items()):
        if node in old_nodes:
            assert nodes[node] == old_nodes[node]
            records = same_raw(path, old_paths[node])
            counts["previous132_all_raw_samples_bitwise_rechecked"] += 1
            detail = dict(raw_samples_bitwise_equal_previous=records)
        else:
            if node.startswith("tests/lsq_wrapper/test_replay_population.py::"):
                detail = inspect_replay(path, nodes[node])
                slots.update(tuple(pair) for pair in detail["slots_by_enqueue_lane"])
                counts["new_replay_cases"] += 1
                for key in ("allocated", "completed", "failure_retained"):
                    counts["new_replay_" + key] += detail[key]
                issue_counts.update({v["issue"] for v in detail["violations"]})
            else:
                assert node.startswith("tests/lsq_wrapper/test_special_memory.py::")
                detail = inspect_special(path, nodes[node])
                counts["new_special_cases"] += 1
                counts["new_special_allocated"] += detail["allocated"]
                counts["new_special_actual_sq_released"] += detail["actual_sq_released"]
                counts["new_special_safe_semantic_store_prefix"] += detail["semantic_store_prefix"]
                counts["new_special_original_load_completed"] += detail["original_loads_completed"]
                issue_counts.update(detail["issues"])
            assert bool(detail["violations"]) == nodes[node]
            records = sum(1 for _ in events(path))
            counts.update(detail["counts"])
        counts["all_continuous_raw_records"] += records
        counts["protocol_probe_cases" if path.name == "lsq_probe.jsonl" else "strict_full_cycle_reference_cases"] += 1
        # Directed log comparisons are checked against raw pins, not trusted.
        suffix = "lsq_probe_checks.jsonl" if path.name == "lsq_probe.jsonl" else "lsq_checks.jsonl"
        checks = list(events(path.with_name(suffix)))
        by_tick = {check["tick"]: [] for check in checks}
        for check in checks:
            by_tick[check["tick"]].append(check)
        for row in events(path):
            for check in by_tick.pop(row["post_tick"], []):
                actual = row[check["phase"]]
                assert check["passed"] and check["actual"] == {key: actual[key] for key in check["expected"]}
                assert all(not ((actual[key] ^ value) & check["masks"].get(key, -1)) for key, value in check["expected"].items())
        assert not by_tick
        cases.append(dict(nodeid=node, journal=str(path.relative_to(run)), sha256=sha(path), result="FAIL" if nodes[node] else "PASS", **detail))
    assert counts["previous132_all_raw_samples_bitwise_rechecked"] == 132
    assert counts["new_replay_cases"] == counts["new_special_cases"] == 20
    assert counts["protocol_probe_cases"] == 16 and counts["strict_full_cycle_reference_cases"] == 156
    assert slots == {(slot, lane) for slot in range(120) for lane in range(3)}
    assert issue_counts == {"LRQ-STRICT-001": 3, "DEQ-WB-001": 3, "DEQ-ZERO-001": 1,
                            "DEQ-FINISH-ORDER-001": 3, "DEQ-SPLIT-WLINE-001": 1}
    dest = run / "evidence-auditors"
    dest.mkdir(exist_ok=True)
    files = (Path(__file__), ROOT / "tools/audit_lsq_memory_v1.py", ROOT / "tools/audit_lsq_bus_v2.py", ROOT / "tools/audit_lsq_bus_v3.py")
    for file in files:
        copy_to = dest / file.name
        if copy_to.exists():
            assert sha(copy_to) == sha(file)
        else:
            shutil.copy2(file, copy_to)
    report = dict(run=name, status="NOT_PASS_172_case_population_and_actual_special_effect_histories_audited", tests=manifest["tests"],
                  snapshot_files=len(source), counts=dict(counts), new_issue_case_counts=dict(issue_counts),
                  actual_replay_slot_by_s3_lane_witness_count=len(slots), baseline_audit_sha256=base_audits,
                  auditor_sha256={file.name: sha(dest / file.name) for file in files}, cases=cases,
                  limits="Exact172 cases only: old132 bitwise to independently audited06, new20 Replay population/real SQ strict/special/960 multi-flow, new20 Store special original Load and actual effects. Sixteen protocol-only probe cases explicitly do NOT compare all458 outputs and do not replace strict fixture/random acceptance. WB fault lost, missing own zero write, wrong split wline and unsafe prefix are independently recognized at actual fire/release, not waived by empty. No NC/RAR full-pool, active reset/full recovery/random or Backend/elaboration acceptance; old25 failures and new11 ordinary FAIL remain.")
    output = run / "population-history-audit-v1.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "cases"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
