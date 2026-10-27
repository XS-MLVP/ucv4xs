#!/usr/bin/env python3
"""Independent raw StoreQueue UID/byte/actual-fire audit, no domain models.

Audits every public journal and comparison; independently replays all external
actor portions, the first directed flows, and all-slot CBO completion stream.
It deliberately does not relabel every directed probe as a second UID model.
"""
import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import shutil

from audit_psq_initial import ROOT, ptr, rows, sha
from audit_psq_lifecycle import dependency_violations, direct_forward_fault, source_word
from audit_sq_initial import classify, initial_replay, masked_difference, verify_common


def rob(pins, prefix):
    return (pins[prefix + "flag"], pins[prefix + "value"], pins[prefix + "isFormer"])


def owner_rob(owner):
    return (int(owner["rob"]["flag"]), owner["rob"]["value"], int(owner["rob"]["former"]))


class Replay:
    def __init__(self):
        self.head = self.tail = 0
        self.all, self.live, self.uops, self.parts, self.final = {}, {}, {}, {}, {}
        self.dispatched, self.data, self.address, self.s2_done, self.finished, self.done, self.cancelled, self.aborted, self.early = (set() for _ in range(9))
        self.pending_dispatch = []
        self.last_sta = (None, None)
        self.pending = None
        self.redirects, self.violations, self.reuse = [], [], []
        self.old_slots = {"reset": {}, "cancel": {}}
        self.counts = Counter()
        self.last_tick = None

    def allocate(self, event):
        uop = event["uop"]
        assert uop["uid"] not in self.uops and uop["start"] == self.tail
        self.uops[uop["uid"]] = copy.deepcopy(uop)
        self.pending_dispatch.append(uop["uid"])
        assert uop["flows"] == [owner["uid"] for owner in event["owners"]]
        for owner in event["owners"]:
            uid, pos = owner["uid"], owner["position"]
            assert uid not in self.all and pos == self.tail and self.tail - self.head < 128
            self.all[uid] = self.live[pos] = copy.deepcopy(owner)
            self.parts[uid] = set()
            self.tail += 1
        assert self.tail == uop["end"]
        self.counts["allocated_virtual_uops"] += 1
        self.counts["allocated_flow_uids"] += len(event["owners"])

    def word(self, pins, lane, tick, phase):
        p = f"io_writeToSbuffer_req_{lane}_"
        if not pins[p + "valid"]:
            return None
        candidates = [(owner, part) for owner in self.live.values() for part in range(2 if owner["address"]["cross_word"] else 1)
                      if owner["address"]["vaddr"] // 16 * 16 + part * 16 == pins[p + "bits_vaddr"]]
        assert len(candidates) == 1
        owner, part = candidates[0]
        assert owner["uid"] in self.data and owner["uid"] in self.address
        expected = source_word(owner, part)
        for field, want in expected.items():
            mask = sum(255 << (8 * byte) for byte in range(16) if expected["mask"] >> byte & 1) if field == "data" else -1
            actual = pins[p + "bits_" + field]
            if (actual ^ want) & mask:
                assert field == "wline" and actual == 1 and want == 0
                self.violations.append({"issue": "DEQ-SPLIT-WLINE-001", "tick": tick, "phase": phase, "uid": owner["uid"], "part": part})
        self.counts["valid_sbuffer_byte_observations"] += expected["mask"].bit_count()
        return owner, part

    def step(self, row, event=None):
        inp, pre, post, tick = row["input"], row["before"], row["after"], row["post_tick"]
        assert not inp["reset"] and ptr(pre, "io_sqDeqPtr_") == self.head % 256
        for lane, pending in enumerate(self.last_sta):
            if pending is None:
                continue
            uid, last = pending
            attrs, p = self.all[uid]["attributes"], f"io_fromStoreUnit_storeAddrInRe_{lane}_"
            for port, field in (("nc", "nc"), ("mmio", "mmio"), ("memBackTypeMM", "memory"), ("hasException", "exception")):
                assert inp[p + port] == int(attrs[field])
            assert inp[p + "isLastRequest"] == int(last)
            if last:
                self.s2_done.add(uid)
        dispatched = []
        for lane in range(8):
            p = f"io_enq_req_{lane}_"
            if inp[p + "valid"] and inp[p + "bits_needAlloc"]:
                uid = self.pending_dispatch.pop(0)
                uop = self.uops[uid]
                assert rob(inp, p + "bits_uop_robIdx_") == (int(uop["rob"]["flag"]), uop["rob"]["value"], int(uop["rob"]["former"]))
                assert inp[p + "bits_uop_numLsElem"] == len(uop["flows"]) and ptr(inp, p + "bits_reqEndPtr_sqIdx_") == uop["end"] % 256
                assert not inp["io_redirect_valid"]
                self.dispatched.add(uid)
                dispatched.append(uid)
        next_sta = [None, None]
        for lane in range(2):
            p = f"io_fromStoreUnit_storeAddrIn_{lane}_"
            if inp[p + "valid"]:
                pos = self.head + (inp[p + "bits_uop_sqIdx_value"] - self.head) % 64
                owner = self.live[pos]
                address = owner["address"]
                assert inp[p + "bits_uop_fuOpType"] == address["fu_op"] and inp[p + "bits_size"] == address["size"]
                assert inp[p + "bits_isHyper"] == int(address["hyper"])
                last = bool(inp[p + "bits_isLastRequest"])
                tail = address["cross_word"] and last
                va = address["vaddr"] // 16 * 16 + 16 if tail else address["vaddr"]
                pa = (owner["second_page"] if owner["second_page"] is not None else address["paddr"] // 16 * 16 + 16) if tail else address["paddr"]
                assert (inp[p + "bits_vaddr"], inp[p + "bits_paddr"]) == (va, pa)
                if not inp[p + "bits_tlbMiss"]:
                    next_sta[lane] = (owner["uid"], last)
                    self.address.add(owner["uid"])
            p = f"io_storeDataIn_{lane}_"
            if inp[p + "valid"]:
                pos = self.head + (inp[p + "bits_sqIdx_value"] - self.head) % 64
                owner = self.live[pos]
                assert (inp[p + "bits_data"], inp[p + "bits_fuOpType"]) == (owner["data"]["data"], owner["data"]["fu_op"])
                assert owner["uid"] not in self.data
                self.data.add(owner["uid"])
        self.last_sta = tuple(next_sta)
        matched = [self.word(pre, lane, tick, "before") for lane in range(2)]
        consumed = []
        for lane, match in enumerate(matched):
            if match and inp[f"io_writeToSbuffer_req_{lane}_ready"]:
                owner, part = match
                uid = owner["uid"]
                assert part not in self.parts[uid]
                self.parts[uid].add(part)
                self.final[uid] = tick
                consumed.append({"uid": uid, "part": part})
                self.counts["actual_sbuffer_fires"] += 1
        for lane in range(2):
            p = f"io_fromStoreUnit_unalignQueueReq_{lane}_"
            if inp[p + "valid"] and pre[p + "ready"]:
                position = ptr(inp, p + "bits_sqIdx_")
                owner = next(owner for pos, owner in self.live.items() if pos % 256 == position)
                assert owner["second_page"] == inp[p + "bits_paddr"]
                self.counts["actual_uq_accepts"] += 1
        if self.pending:
            kind, uid = self.pending
            if kind == "nc" and inp["io_toUncacheBuffer_idResp_valid"] and not inp["io_toUncacheBuffer_idResp_bits_is2lq"]:
                self.finished.add(uid)
                self.final[uid], self.pending = tick, None
                self.counts["actual_nc_acknowledgements"] += 1
            elif kind == "cache" and inp["io_toDCache_resp_valid"] and pre["io_toDCache_resp_ready"] or kind == "io" and inp["io_toUncacheBuffer_resp_valid"]:
                self.pending = ("wb", uid)
        if pre["io_toDCache_req_valid"] and inp["io_toDCache_req_ready"]:
            assert self.pending is None
            owner = next(owner for owner in self.live.values() if owner["address"]["paddr"] == pre["io_toDCache_req_bits_address"])
            assert owner["address"]["fu_op"] & 1 and pre["io_toDCache_req_bits_opcode"] == owner["address"]["fu_op"] >> 1 & 7
            assert owner_rob(owner) == rob(inp, "io_fromRob_robHeadPtr_")
            self.pending = ("cache", owner["uid"])
            self.counts["actual_cache_requests"] += 1
        if pre["io_toUncacheBuffer_req_valid"] and inp["io_toUncacheBuffer_req_ready"]:
            assert self.pending is None
            owner = next(owner for owner in self.live.values() if owner["address"]["vaddr"] == pre["io_toUncacheBuffer_req_bits_vaddr"])
            p, address = "io_toUncacheBuffer_req_bits_", owner["address"]
            assert rob(pre, p + "robIdx_") == owner_rob(owner) and pre[p + "addr"] == address["paddr"]
            assert pre[p + "id"] == owner["position"] % 64 and pre[p + "nc"] == int(owner["attributes"]["nc"])
            mask = value = 0
            for index in range(1 << address["size"]):
                byte = (address["vaddr"] + index) % 8
                mask |= 1 << byte
                value |= (owner["data"]["data"] >> (8 * index) & 255) << (8 * byte)
            bits = sum(255 << (8 * byte) for byte in range(8) if mask >> byte & 1)
            assert pre[p + "mask"] == mask and not ((pre[p + "data"] ^ value) & bits)
            self.pending = ("nc" if owner["attributes"]["nc"] else "io", owner["uid"])
            self.counts["actual_uncache_requests"] += 1
        if pre["io_writeBack_valid"] and inp["io_writeBack_ready"]:
            owner = next(owner for owner in self.live.values() if owner_rob(owner) == rob(pre, "io_writeBack_bits_" + "robIdx_"))
            uid = owner["uid"]
            zero = owner["address"]["fu_op"] & 1 and owner["address"]["fu_op"] >> 1 & 7 == 3
            assert self.parts[uid] == {0} if zero else self.pending == ("wb", uid)
            assert not pre["io_writeBack_bits_exceptionVec_7"] and not pre["io_writeBack_bits_exceptionVec_19"]
            self.pending = None
            self.finished.add(uid)
            self.final[uid] = tick
            self.counts["actual_wb_fires"] += 1
        for lane in range(2):
            self.word(post, lane, tick, "after")
        delta = (ptr(post, "io_sqDeqPtr_") - self.head) % 256
        assert delta <= 2 and post["io_toLsqEnqCtrl_sqDeq_valid"] == int(bool(delta))
        if delta:
            assert post["io_toLsqEnqCtrl_sqDeq_bits"] == delta
        completed = []
        for pos in range(self.head, self.head + delta):
            owner = self.live[pos]
            uid = owner["uid"]
            assert uid in self.data and uid in self.s2_done and uid not in self.done and not owner["attributes"]["exception"]
            special = owner["address"]["fu_op"] & 1 or owner["attributes"]["nc"] or owner["attributes"]["mmio"]
            if special:
                assert uid in self.finished and self.final[uid] < tick
            elif self.parts[uid] != ({0, 1} if owner["address"]["cross_word"] else {0}) or self.final[uid] + 2 != tick:
                assert any(other["uid"] in self.finished for p, other in self.live.items() if pos < p <= pos + 1)
                self.violations.append({"issue": "DEQ-FINISH-ORDER-001", "tick": tick, "uid": uid, "parts": sorted(self.parts[uid]),
                                        "last_actual_fire": self.final.get(uid), "reason": "head_released_before_own_delayed_credit_because_later_special_finished"})
                self.early.add(uid)
            if uid not in self.early:
                self.done.add(uid)
                completed.append(uid)
                for kind, slots in self.old_slots.items():
                    if pos % 64 in slots:
                        self.reuse.append({"kind": kind, "slot": pos % 64, "old_uid": slots[pos % 64], "new_uid": uid, "tick": tick})
            del self.live[pos]
        self.head += delta
        if inp["io_redirect_valid"]:
            target = rob(inp, "io_redirect_bits_robIdx_")
            uop = next(uop for _, uop in sorted(self.uops.items(), reverse=True) if (int(uop["rob"]["flag"]), uop["rob"]["value"], int(uop["rob"]["former"])) == target)
            cut = uop["start"] if inp["io_redirect_bits_level"] else uop["end"]
            self.redirects.append({"tick": tick, "cut": cut})
        if event:
            assert event["head"] == self.head and event["consumed"] == consumed and event["completed"] == completed and event["dispatched"] == dispatched
            assert (inp["io_fromRob_robHeadPtr_flag"] * 160 + inp["io_fromRob_robHeadPtr_value"]) == event["rob_order"] % 320
        self.counts["independently_replayed_actor_steps"] += 1
        self.last_tick = tick

    def cancel_or_reset(self, event, trace):
        kind = "reset" if event["event"] == "reset" else "cancel"
        doomed = sorted(owner["uid"] for pos, owner in self.live.items() if kind == "reset" or pos >= event["cut"])
        assert doomed == event["aborted" if kind == "reset" else "cancelled"]
        if kind == "cancel":
            assert self.redirects[-1]["cut"] == event["cut"]
            assert event["recovery"] and all(any(row["post_tick"] == record["tick"] and row["after"]["io_toLsqEnqCtrl_sqRedirectPtr_valid"] and
                                                  ptr(row["after"], "io_toLsqEnqCtrl_sqRedirectPtr_bits_") == event["cut"] % 256 for row in trace) for record in event["recovery"])
        else:
            reset = [row for row in trace if (self.last_tick or 0) < row["post_tick"] <= event["tick"] and row["input"]["reset"]]
            assert len(reset) == 4 and all(not row["after"]["io_writeBack_valid"] and not row["after"]["io_writeToSbuffer_req_0_valid"] for row in reset)
        for uid in doomed:
            owner = self.all[uid]
            (self.aborted if kind == "reset" else self.cancelled).add(uid)
            self.old_slots[kind][owner["position"] % 64] = uid
            del self.live[owner["position"]]
        if kind == "reset":
            self.head = self.tail = 0
            self.pending = None
            self.pending_dispatch.clear()
        else:
            self.tail = event["cut"]
        self.last_sta = (None, None)


def cbo_stream(trace):
    owner = None
    completed = fires = cache = wb = zero = 0
    pairs, data_pairs = set(), set()
    for row in trace:
        inp, pre, post, tick = row["input"], row["before"], row["after"], row["post_tick"]
        if inp["reset"]:
            continue
        for lane in range(2):
            p = f"io_fromStoreUnit_storeAddrIn_{lane}_"
            if inp[p + "valid"]:
                assert owner is None
                op = inp[p + "bits_uop_fuOpType"]
                assert op & 1 and inp[p + "bits_uop_sqIdx_value"] == completed % 64
                owner = {"va": inp[p + "bits_vaddr"], "pa": inp[p + "bits_paddr"], "op": op >> 1 & 7, "size": inp[p + "bits_size"], "data": None, "fire": None, "wb": None}
                pairs.add((completed % 64, lane))
        for lane in range(2):
            p = f"io_storeDataIn_{lane}_"
            if inp[p + "valid"]:
                assert owner is not None and owner["data"] is None
                owner["data"] = 0 if owner["op"] == 3 else inp[p + "bits_data"]
                data_pairs.add((completed % 64, lane))
        if pre["io_toDCache_req_valid"] and inp["io_toDCache_req_ready"]:
            assert owner and owner["op"] < 3 and pre["io_toDCache_req_bits_address"] == owner["pa"] and pre["io_toDCache_req_bits_opcode"] == owner["op"]
            cache += 1
        for lane in range(2):
            p = f"io_writeToSbuffer_req_{lane}_"
            if pre[p + "valid"] and inp[p + "ready"]:
                assert owner and owner["op"] == 3 and owner["fire"] is None
                assert pre[p + "bits_vaddr"] == owner["va"] and pre[p + "bits_addr"] == owner["pa"] and pre[p + "bits_wline"] == 1
                assert pre[p + "bits_mask"] == 255 and pre[p + "bits_data"] == 0
                owner["fire"] = tick
                fires += 1
        if pre["io_writeBack_valid"] and inp["io_writeBack_ready"]:
            assert owner and owner["wb"] is None and pre["io_writeBack_bits_robIdx_value"] == (10 + completed) % 160
            if owner["op"] == 3:
                assert owner["fire"] is not None and owner["fire"] < tick
                zero += 1
            owner["wb"] = tick
            wb += 1
        delta = (ptr(post, "io_sqDeqPtr_") - completed) % 256
        assert delta <= 1
        if delta:
            assert owner and owner["wb"] + 2 == tick and post["io_toLsqEnqCtrl_sqDeq_valid"] and post["io_toLsqEnqCtrl_sqDeq_bits"] == 1
            completed += 1
            owner = None
    assert completed == wb == 128 and cache == 96 and zero == fires == 32 and len(pairs) == len(data_pairs) == 128
    return {"cbo_stream_completed_flows": completed, "cbo_stream_cache_requests": cache, "cbo_stream_actual_wb_fires": wb,
            "cbo_stream_actual_zero_fires": zero, "cbo_stream_sta_lane_slot_pairs": len(pairs), "cbo_stream_std_lane_slot_pairs": len(data_pairs)}


def direct_witnesses(trace, path, node):
    result = []
    if "test_cross_word_va_alias" in node or "test_cross_word_store_cannot_supply" in node:
        result.append(direct_forward_fault(trace, node))
    if "test_cache_error_through" in node and "[" in node:
        arrival = next(row for row in trace if row["input"]["io_toDCache_resp_valid"] and row["before"]["io_toDCache_resp_ready"])
        final = trace[-1]
        if final["before"]["io_writeBack_valid"] and final["input"]["io_writeBack_ready"]:
            bad = []
            for bit, field in ((7, "denied"), (19, "corrupt")):
                want = arrival["input"]["io_toDCache_resp_bits_" + field]
                assert arrival["after"][f"io_writeBack_bits_exceptionVec_{bit}"] == want
                if final["before"][f"io_writeBack_bits_exceptionVec_{bit}"] != want:
                    bad.append(bit)
            if bad:
                assert final["post_tick"] > arrival["post_tick"] + 2
                result.append({"issue": "DEQ-WB-001", "tick": final["post_tick"], "actual_fire": True, "lost_exception_bits": bad})
    if "test_retired_split_then_rob_head" in node:
        final = trace[-1]
        p = "io_writeToSbuffer_req_1_"
        if final["before"][p + "valid"] and final["input"][p + "ready"] and final["before"][p + "bits_wline"]:
            assert final["before"][p + "bits_addr"] == 0xABCD010 and final["before"][p + "bits_mask"] == 15 and final["before"][p + "bits_data"] & 0xFFFFFFFF == 0x88776655
            first = next(row for row in trace if row["input"]["io_fromStoreUnit_storeAddrIn_0_valid"] and row["input"]["io_fromStoreUnit_storeAddrIn_0_bits_isLastRequest"])
            cbo = next(row for row in trace if row["input"]["io_fromStoreUnit_storeAddrIn_0_valid"] and row["input"]["io_fromStoreUnit_storeAddrIn_0_bits_uop_fuOpType"] == 7)
            assert first["post_tick"] < cbo["post_tick"] < final["post_tick"] and cbo["input"]["io_fromRob_robHeadPtr_value"] == 11
            result.append({"issue": "DEQ-SPLIT-WLINE-001", "tick": final["post_tick"], "actual_fire": True, "ordinary_last_sta_tick": first["post_tick"], "rob_head_cbo_sta_tick": cbo["post_tick"]})
    zero_path = path.with_name("zero-owner-check.json")
    if zero_path.is_file():
        evidence = json.loads(zero_path.read_text())
        wb = next(row for row in trace if row["post_tick"] == evidence["actual_wb_tick"])
        assert wb["before"]["io_writeBack_valid"] and wb["input"]["io_writeBack_ready"] and wb["before"]["io_writeBack_bits_robIdx_value"] == 11
        fires = []
        for row in trace:
            if row["post_tick"] > wb["post_tick"]:
                continue
            for lane in range(2):
                p = f"io_writeToSbuffer_req_{lane}_"
                if row["before"][p + "valid"] and row["input"][p + "ready"] and row["before"][p + "bits_vaddr"] == 0x20000:
                    assert row["before"][p + "bits_addr"] == 0xDEF000 and row["before"][p + "bits_wline"] == 1 and row["before"][p + "bits_data"] == 0
                    fires.append(row["post_tick"])
        assert len(fires) == evidence["actual_zero_transfers_before_wb"] and trace[-1]["after"]["io_sqEmpty"]
        if evidence["old_queued"]:
            assert not fires and ptr(trace[-1]["after"], "io_sqDeqPtr_") == 2
            result.append({"issue": "DEQ-ZERO-001", "tick": wb["post_tick"], "actual_wb_and_release": True, "zero_transfers": 0})
        else:
            assert len(fires) == 1
    order_path = path.with_name("special-order-check.json")
    if order_path.is_file():
        evidence = json.loads(order_path.read_text())
        assert all(not row["input"][f"io_writeToSbuffer_req_{lane}_ready"] for row in trace for lane in range(2))
        final = trace[-1]
        assert ptr(final["before"], "io_sqDeqPtr_") == 0 and ptr(final["after"], "io_sqDeqPtr_") == 1
        assert final["after"]["io_toLsqEnqCtrl_sqDeq_valid"] and final["after"]["io_toLsqEnqCtrl_sqDeq_bits"] == 1
        assert final["after"]["io_writeToSbuffer_req_0_valid"] and final["after"]["io_writeToSbuffer_req_0_bits_vaddr"] == 0x30000
        request = next(row for row in trace if row["before"]["io_toUncacheBuffer_req_valid"] and row["input"]["io_toUncacheBuffer_req_ready"])
        assert request["before"]["io_toUncacheBuffer_req_bits_addr"] == 0xDEF000 and request["before"]["io_toUncacheBuffer_req_bits_robIdx_value"] == 11
        if evidence["memory_type"] == 1:
            assert any(row["post_tick"] > request["post_tick"] and row["input"]["io_toUncacheBuffer_idResp_valid"] and not row["input"]["io_toUncacheBuffer_idResp_bits_is2lq"] for row in trace)
        else:
            assert any(row["before"]["io_writeBack_valid"] and row["input"]["io_writeBack_ready"] and row["before"]["io_writeBack_bits_robIdx_value"] == 11 for row in trace)
        result.append({"issue": "DEQ-FINISH-ORDER-001", "tick": final["post_tick"], "older_actual_sbuffer_fires": 0, "released_old_owner": True, "memory_type": evidence["memory_type"]})
    return result


def audit(name):
    run = ROOT / "results" / name
    manifest, source, nodes = verify_common(run)
    assert manifest["tests"] == {"PASS": 55, "FAIL": 24} and len(nodes) == 79
    counts, failure_counts, seen, cases = Counter(), Counter(), set(), []
    for path in sorted((run / "cases").rglob("store_queue.jsonl")):
        trace = rows(path)
        node, last, by_tick = trace[0]["nodeid"], None, {}
        assert node in nodes and node not in seen
        seen.add(node)
        differences = []
        for row in trace:
            tick = row["post_tick"]
            assert row["nodeid"] == node and row["input"] == row["post_input"] and row["pre_tick"] + 1 == tick
            assert last is None or last + 2 == tick
            assert len(row["input"]) == 182 and len(row["before"]) == len(row["after"]) == 338
            counts["continuous_records"] += 1
            if "expected_before" in row:
                counts["staged_reference_records"] += 1
                bad = {}
                for phase in ("before", "after"):
                    bad.update(masked_difference(row[phase], row.get("expected_" + phase, {}), row.get("masks_" + phase, {})))
                if row["checked"]:
                    assert not bad and not row.get("error")
                    counts["fully_checked_staged_records"] += 1
                else:
                    assert row.get("error")
                if bad:
                    differences.append(bad)
            by_tick[tick], last = row, tick
        for check in rows(path.with_name("sq_checks.jsonl")):
            pins = by_tick[check["tick"]][check["phase"]]
            assert check["actual"] == {key: pins[key] for key in check["expected"]}
            bad = masked_difference(pins, check["expected"], check["bit_masks"])
            assert check["passed"] == (not bad)
            counts["directed_checks"] += 1
            if bad:
                differences.append(bad)
        witnesses = dependency_violations(trace) + direct_witnesses(trace, path, node)
        replay = None
        events_path = path.with_name("sq_actor.jsonl")
        if events_path.is_file():
            for event in rows(events_path):
                kind = event["event"]
                if kind == "start":
                    assert replay is None
                    replay = Replay()
                elif kind == "allocate":
                    replay.allocate(event)
                elif kind == "step":
                    replay.step(by_tick[event["tick"]], event)
                elif kind == "checked":
                    assert set(event["uids"]) <= replay.done and event["completed"] == sorted(replay.done)
                    assert event["cancelled"] == sorted(replay.cancelled) and event["aborted"] == sorted(replay.aborted)
                elif kind in ("cancel", "reset"):
                    replay.cancel_or_reset(event, trace)
                else:
                    raise AssertionError(kind)
            if replay:
                # Some clipped-query cases deliberately use the actor only
                # for their 60-flow completed prefix, then directed dispatch.
                if trace[-1].get("error") and replay.last_tick is not None and replay.last_tick + 2 == trace[-1]["post_tick"]:
                    replay.step(trace[-1])
                witnesses.extend(replay.violations)
                retained = {owner["uid"] for owner in replay.live.values()}
                assert len(replay.all) == len(replay.done) + len(replay.cancelled) + len(replay.aborted) + len(replay.early) + len(retained)
                if not nodes[node]:
                    assert not retained and not replay.pending_dispatch and replay.pending is None
                counts.update(replay.counts)
                counts.update(actor_completed_flow_uids=len(replay.done), actor_cancelled_flow_uids=len(replay.cancelled), actor_reset_aborted_flow_uids=len(replay.aborted),
                              actor_early_released_failure_uids=len(replay.early), actor_failure_retained_uids=len(retained),
                              actor_reset_same_slot_reuse=sum(item["kind"] == "reset" for item in replay.reuse), actor_cancel_same_slot_reuse=sum(item["kind"] == "cancel" for item in replay.reuse))
        if "test_initial.py" in node:
            first = initial_replay(trace)
            counts.update({"initial_" + key: value for key, value in first.items()})
        if "test_all_cbo_slots_both_sta_lanes" in node:
            counts.update(cbo_stream(trace))
        assert bool(witnesses) == nodes[node], (node, witnesses, differences)
        if nodes[node]:
            issues = {item["issue"] for item in witnesses}
            assert len(issues) == 1, (node, issues)
            failure_counts.update(issues)
        cases.append({"nodeid": node, "journal": str(path.relative_to(run)), "sha256": sha(path), "records": len(trace),
                      "actor_replayed_through_tick": replay.last_tick if replay else None, "same_slot_reuse": replay.reuse if replay else [],
                      "violations": witnesses, "pin_differences": differences})
    assert seen == set(nodes)
    assert failure_counts == {"FWD-ALIAS-001": 3, "FWD-RANGE-001": 6, "FWD-SQID-001": 4, "DEQ-WB-001": 3,
                              "DEQ-SPLIT-WLINE-001": 3, "DEQ-ZERO-001": 1, "DEQ-FINISH-ORDER-001": 4}
    assert counts["actor_reset_same_slot_reuse"] == 4 and counts["actor_cancel_same_slot_reuse"] >= 7
    assert counts["cbo_stream_completed_flows"] == 128 and counts["initial_independent_completed_flows"] == 16
    coverage = json.loads((run / "line-audit.json").read_text())
    native = coverage["native"][0]
    assert (native["line_hit"], native["line_total"], native["closure_line_hit"], native["closure_line_total"]) == (26, 26, 8968, 8968)
    assert all(not dep["uncovered"] for dep in native["dependencies"])
    groups = {group["instance"]: group for group in coverage["functional"]}
    checked, reached = groups["lsq.store_queue.checked"], groups["lsq.store_queue.reached"]
    assert (checked["hit"], reached["hit"], checked["total"]) == (43, 51, 51)
    assert set(checked["missing"]) == {"SQ-CONCURRENT.seeded", "SQ-CREDIT.special_order", "SQ-FORWARD.alias", "SQ-FORWARD.clipped", "SQ-FORWARD.range", "SQ-SPECIAL.error_held", "SQ-SPECIAL.split_wline", "SQ-SPECIAL.zero_owner"}
    # Keep every earlier gap as classified data; final DA emptiness is NOT a
    # proof that there are no remaining functional/branch obligations.
    prior = json.loads((ROOT / "results/sq-expanded-01/line-audit.json").read_text())
    prior["native"][0] = classify(prior["native"][0])
    prior["classification_summary"] = {"missing_scenario_of_existing_feature": 252, "missing_whole_feature": 0, "excluded_or_denominator_removed": 0}
    assert sum(len(dep["uncovered"]) for dep in prior["native"][0]["dependencies"]) == 252
    gap_path = ROOT / "results/sq-expanded-01/line-audit-classified.json"
    if gap_path.exists():
        assert json.loads(gap_path.read_text()) == prior
    else:
        gap_path.write_text(json.dumps(prior, indent=2, ensure_ascii=False) + "\n")
    auditors = {}
    for tool in (Path(__file__), ROOT / "tools/audit_sq_initial.py", ROOT / "tools/audit_psq_initial.py", ROOT / "tools/audit_psq_lifecycle.py", ROOT / "tools/audit_psq_storage.py"):
        dest = run / "evidence-auditors" / tool.name
        dest.parent.mkdir(exist_ok=True)
        if dest.exists():
            assert sha(dest) == sha(tool)
        else:
            shutil.copy2(tool, dest)
        auditors[tool.name] = sha(dest)
    report = {"run": name, "status": "real_vsq_psq_public_histories_and_scoped_UID_bytes_audited", "dut_acceptance": "NOT_PASS", "tests": manifest["tests"],
              "counts": dict(counts), "failure_cases_by_issue": dict(failure_counts), "checked": 43, "reached": 51, "total_scenarios": 51,
              "missing_checked": checked["missing"], "snapshot_files": len(source), "manifest_sha256": sha(run / "execution/manifest.json"), "auditors": auditors, "cases": cases,
              "limits": "All raw public histories/comparisons and true failures audited. UID/byte replay covers external actor portions, first 16 directed normal flows, and the separate 128-owner CBO stream; not every directed probe has a second UID ledger. Real seven-file VSQ/PSQ closure, not Backend/LoadQueue/LsqWrapper. DA full is not branch/expression/arbitrary-configuration exhaustiveness; failures remain normal FAIL and no problem list is an oracle."}
    output = run / "lifecycle-audit.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
