#!/usr/bin/env python3
"""Public-input UID/byte audit, independent of all domain/reference models.

Audits the frozen full PSQ round. A successful evidence audit is NOT a DUT
acceptance: every independently confirmed violation remains a normal FAIL.
"""
import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

from audit_psq_initial import ROOT, ptr, rows, sha
from audit_psq_storage import storage_replay


def masked_difference(pins, expected, masks):
    return {key: [pins[key], want] for key, want in expected.items() if (pins[key] ^ want) & masks.get(key, -1)}


def source_word(owner, part):
    address, data = owner["address"], owner["data"]
    va = address["vaddr"] // 16 * 16 + part * 16
    pa = address["paddr"] // 16 * 16 + part * 16
    if part and owner["second_page"] is not None:
        pa = owner["second_page"]
    zero = bool(address["fu_op"] & 1 and address["fu_op"] >> 1 & 7 == 3)
    original = 0 if zero else data["data"]
    mask = value = 0
    for index in range(1 << address["size"]):
        byte = address["vaddr"] + index - va
        if 0 <= byte < 16:
            mask |= 1 << byte
            value |= (original >> (8 * index) & 255) << (8 * byte)
    return {"vaddr": va, "addr": pa, "mask": mask, "data": value, "wline": int(zero)}


class ActorReplay:
    def __init__(self, node):
        self.node = node
        self.head = self.tail = 0
        self.live, self.all, self.parts, self.final = {}, {}, {}, {}
        self.done, self.cancelled, self.aborted, self.address_sent, self.data_sent, self.s2_done = set(), set(), set(), set(), set(), set()
        self.last_sta = (None, None)
        self.pending = None
        self.finished = set()
        self.violations, self.reuse = [], []
        self.cancelled_slots, self.aborted_slots = {}, {}
        self.counts = Counter()

    def allocate(self, source):
        owner = copy.deepcopy(source)
        uid, pos = owner["uid"], owner["position"]
        assert uid not in self.all and pos == self.tail and self.tail - self.head < 128
        self.live[pos] = self.all[uid] = owner
        self.parts[uid] = set()
        self.tail += 1
        self.counts["allocated_uids"] += 1

    def match_word(self, pins, lane, tick, phase):
        prefix = f"io_writeToSbuffer_req_{lane}_"
        if not pins[prefix + "valid"]:
            return None
        candidates = [(owner, part) for owner in self.live.values() for part in range(2 if owner["address"]["cross_word"] else 1)
                      if owner["address"]["vaddr"] // 16 * 16 + part * 16 == pins[prefix + "bits_vaddr"]]
        assert len(candidates) == 1
        owner, part = candidates[0]
        assert owner["uid"] in self.data_sent and owner["uid"] in self.address_sent
        expected = source_word(owner, part)
        for field, want in expected.items():
            mask = sum(255 << (8 * byte) for byte in range(16) if expected["mask"] >> byte & 1) if field == "data" else -1
            actual = pins[prefix + "bits_" + field]
            if (actual ^ want) & mask:
                assert field == "wline" and actual == 1 and want == 0
                self.violations.append({"issue": "DEQ-SPLIT-WLINE-001", "tick": tick, "phase": phase, "uid": owner["uid"], "part": part, "actual": 1, "expected": 0})
        self.counts["sbuffer_valid_byte_observations"] += expected["mask"].bit_count()
        return owner, part

    def step(self, row, event=None):
        inp, pre, post, tick = row["input"], row["before"], row["after"], row["post_tick"]
        assert not inp["reset"] and ptr(pre, "io_sqDeqPtr_") == self.head % 256
        for lane, pending in enumerate(self.last_sta):
            if pending is None:
                continue
            uid, last = pending
            attrs = self.all[uid]["attributes"]
            prefix = f"io_fromStoreUnit_storeAddrInRe_{lane}_"
            for port, field in (("nc", "nc"), ("mmio", "mmio"), ("memBackTypeMM", "memory"), ("hasException", "exception")):
                assert inp[prefix + port] == int(attrs[field])
            assert inp[prefix + "isLastRequest"] == int(last)
            if last:
                self.s2_done.add(uid)
        next_sta = [None, None]
        for lane in range(2):
            prefix = f"io_fromStoreUnit_storeAddrIn_{lane}_"
            if inp[prefix + "valid"]:
                position = self.head + (inp[prefix + "bits_uop_sqIdx_value"] - self.head) % 64
                owner = self.live[position]
                address = owner["address"]
                assert inp[prefix + "bits_uop_fuOpType"] == address["fu_op"] and inp[prefix + "bits_size"] == address["size"]
                assert inp[prefix + "bits_isHyper"] == int(address["hyper"])
                last = bool(inp[prefix + "bits_isLastRequest"])
                tail = address["cross_word"] and last
                va = address["vaddr"] // 16 * 16 + 16 if tail else address["vaddr"]
                pa = (owner["second_page"] if owner["second_page"] is not None else address["paddr"] // 16 * 16 + 16) if tail else address["paddr"]
                assert (inp[prefix + "bits_vaddr"], inp[prefix + "bits_paddr"]) == (va, pa)
                if not inp[prefix + "bits_tlbMiss"]:
                    next_sta[lane] = (owner["uid"], last)
                    self.address_sent.add(owner["uid"])
            prefix = f"io_storeDataIn_{lane}_"
            if inp[prefix + "valid"]:
                position = self.head + (inp[prefix + "bits_sqIdx_value"] - self.head) % 64
                owner = self.live[position]
                assert (inp[prefix + "bits_data"], inp[prefix + "bits_fuOpType"]) == (owner["data"]["data"], owner["data"]["fu_op"])
                assert owner["uid"] not in self.data_sent
                self.data_sent.add(owner["uid"])
        self.last_sta = tuple(next_sta)
        matched = [self.match_word(pre, lane, tick, "before") for lane in range(2)]
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
            prefix = f"io_fromStoreUnit_unalignQueueReq_{lane}_"
            if inp[prefix + "valid"] and pre[prefix + "ready"]:
                raw = ptr(inp, prefix + "bits_sqIdx_")
                owner = next(owner for pos, owner in self.live.items() if pos % 256 == raw)
                assert owner["second_page"] == inp[prefix + "bits_paddr"]
                self.counts["actual_uq_accepts"] += 1
        if self.pending:
            kind, uid = self.pending
            if kind == "nc" and inp["io_toUncacheBuffer_idResp_valid"] and not inp["io_toUncacheBuffer_idResp_bits_is2lq"]:
                self.finished.add(uid)
                self.final[uid] = tick
                self.pending = None
                self.counts["actual_nc_acknowledgements"] += 1
            elif kind == "cache" and inp["io_toDCache_resp_valid"] and pre["io_toDCache_resp_ready"]:
                self.pending = ("wb", uid)
            elif kind == "io" and inp["io_toUncacheBuffer_resp_valid"]:
                self.pending = ("wb", uid)
        if pre["io_toDCache_req_valid"] and inp["io_toDCache_req_ready"]:
            assert self.pending is None
            owner = next(owner for owner in self.live.values() if owner["address"]["paddr"] == pre["io_toDCache_req_bits_address"])
            assert owner["address"]["fu_op"] & 1 and pre["io_toDCache_req_bits_opcode"] == owner["address"]["fu_op"] >> 1 & 7
            self.pending = ("cache", owner["uid"])
            self.counts["actual_cache_requests"] += 1
        if pre["io_toUncacheBuffer_req_valid"] and inp["io_toUncacheBuffer_req_ready"]:
            assert self.pending is None
            owner = next(owner for owner in self.live.values() if owner["address"]["vaddr"] == pre["io_toUncacheBuffer_req_bits_vaddr"])
            prefix = "io_toUncacheBuffer_req_bits_"
            address, data = owner["address"], owner["data"]["data"]
            assert pre[prefix + "addr"] == address["paddr"] and pre[prefix + "id"] == owner["position"] % 64
            assert pre[prefix + "nc"] == int(owner["attributes"]["nc"]) and pre[prefix + "memBackTypeMM"] == int(owner["attributes"]["memory"])
            mask = value = 0
            for index in range(1 << address["size"]):
                byte = (address["vaddr"] + index) % 8
                mask |= 1 << byte
                value |= (data >> (8 * index) & 255) << (8 * byte)
            bits = sum(255 << (8 * byte) for byte in range(8) if mask >> byte & 1)
            assert pre[prefix + "mask"] == mask and not ((pre[prefix + "data"] ^ value) & bits)
            self.pending = ("nc" if owner["attributes"]["nc"] else "io", owner["uid"])
            self.counts["actual_uncache_requests"] += 1
        if pre["io_writeBack_valid"] and inp["io_writeBack_ready"]:
            raw_rob = (inp["io_fromVirtualStoreQueue_headRobIdx_flag"], inp["io_fromVirtualStoreQueue_headRobIdx_value"], inp["io_fromVirtualStoreQueue_headRobIdx_isFormer"])
            owner = next(owner for owner in self.live.values() if (int(owner["rob"]["flag"]), owner["rob"]["value"], int(owner["rob"]["former"])) == raw_rob)
            uid = owner["uid"]
            zero = owner["address"]["fu_op"] & 1 and owner["address"]["fu_op"] >> 1 & 7 == 3
            if zero:
                assert self.parts[uid] == {0}, "a zero WB cannot borrow an older owner's transfer"
            else:
                assert self.pending == ("wb", uid)
            self.pending = None
            self.finished.add(uid)
            self.final[uid] = tick
            self.counts["actual_wb_fires"] += 1
        for lane in range(2):
            self.match_word(post, lane, tick, "after")
        delta = (ptr(post, "io_sqDeqPtr_") - self.head) % 256
        assert delta <= 2 and post["io_sqDeq_valid"] == int(bool(delta))
        if delta:
            assert post["io_sqDeq_bits"] == delta
        completed = []
        for pos in range(self.head, self.head + delta):
            owner = self.live[pos]
            uid = owner["uid"]
            assert uid not in self.done and uid in self.s2_done and uid in self.data_sent and not owner["attributes"]["exception"]
            special = owner["address"]["fu_op"] & 1 or owner["attributes"]["nc"] or owner["attributes"]["mmio"]
            if special:
                assert uid in self.finished and self.final[uid] < tick
            else:
                assert self.parts[uid] == ({0, 1} if owner["address"]["cross_word"] else {0}) and self.final[uid] + 2 == tick
            self.done.add(uid)
            completed.append(uid)
            del self.live[pos]
            for kind, slots in (("reset", self.aborted_slots), ("cancel", self.cancelled_slots)):
                if pos % 64 in slots:
                    self.reuse.append({"kind": kind, "slot": pos % 64, "old_uid": slots[pos % 64], "new_uid": uid, "tick": tick})
        self.head += delta
        if event:
            assert event["head"] == self.head and event["consumed"] == consumed and event["completed"] == completed
        self.counts["replayed_actor_steps"] += 1


def dependency_violations(trace):
    result = []
    for index in range(1, len(trace)):
        previous, row = trace[index - 1], trace[index]
        for lane in range(3):
            prefix = f"io_forward_{lane}_"
            if not previous["input"][prefix + "s0Req_valid"] or row["input"][prefix + "s1Kill"]:
                continue
            pins = row["after"]
            if not pins[prefix + "s2Resp_valid"] or not pins[prefix + "s2Resp_bits_dataInvalid_valid"]:
                continue
            head = ptr(previous["before"], "io_sqDeqPtr_")
            suffix = prefix + "s2Resp_bits_dataInvalid_bits_"
            actual = ptr(pins, suffix)
            expected = (head + (pins[suffix + "value"] - head) % 64) % 256
            if actual != expected:
                result.append({"issue": "FWD-SQID-001", "tick": row["post_tick"], "lane": lane, "actual_sq": actual, "expected_sq": expected,
                               "s0_deq_sq": head, "s0_upper_sq": ptr(previous["before"], "io_physicalUpperSqIdx_"),
                               "load_sq": ptr(previous["input"], prefix + "s0Req_bits_sqIdx_")})
    return result


def direct_forward_fault(trace, node):
    bank = {}
    for row in trace:
        inp = row["input"]
        for lane in range(2):
            p = f"io_fromStoreUnit_storeAddrIn_{lane}_"
            if inp[p + "valid"] and (not inp[p + "bits_isLastRequest"] or not inp[p + "bits_cross16Byte"]):
                slot = inp[p + "bits_uop_sqIdx_value"]
                bank.setdefault(slot, {}).update(va=inp[p + "bits_vaddr"], pa=inp[p + "bits_paddr"], length=1 << inp[p + "bits_size"])
            p = f"io_storeDataIn_{lane}_"
            if inp[p + "valid"]:
                bank.setdefault(inp[p + "bits_sqIdx_value"], {})["data"] = inp[p + "bits_data"]
    previous, final = trace[-2], trace[-1]
    lane = next(lane for lane in range(3) if previous["input"][f"io_forward_{lane}_s0Req_valid"])
    p, pins = f"io_forward_{lane}_s2Resp_", final["after"]
    assert pins[p + "valid"] and not any(pins[p + "bits_" + key] for key in ("forwardInvalid", "matchInvalid", "addrInvalid_valid", "dataInvalid_valid"))
    word_pa = final["input"][f"io_forward_{lane}_s1Req_paddr"] // 16 * 16
    bad = []
    for byte in range(16):
        if not pins[p + f"bits_forwardMask_{byte}"]:
            continue
        address = word_pa + byte
        sources = [(slot, owner, address - owner["pa"]) for slot, owner in sorted(bank.items()) if 0 <= address - owner["pa"] < owner["length"]]
        actual = pins[p + f"bits_forwardData_{byte}"]
        if not sources:
            bad.append({"byte": byte, "pa": address, "actual": actual, "expected": "no_store_producer"})
        else:
            slot, owner, offset = sources[-1]
            want = owner["data"] >> (8 * offset) & 255
            if actual != want:
                bad.append({"byte": byte, "pa": address, "actual": actual, "expected": want, "newest_slot": slot})
    assert bad
    return {"issue": "FWD-ALIAS-001" if "va_alias" in node else "FWD-RANGE-001", "tick": final["post_tick"], "lane": lane,
            "raw_sources": bank, "bad_forwarded_bytes": bad}


def audit(name):
    run = ROOT / "results" / name
    manifest = json.loads((run / "execution/manifest.json").read_text())
    assert manifest["state"] == "committed" and manifest["coverage_complete"] and manifest["cleanup_complete"]
    assert manifest["tests"] == {"PASS": 45, "FAIL": 18}
    for artifact in manifest["artifacts"]:
        assert sha(Path(artifact["path"])) == artifact["sha256"]
        if artifact["kind"] == "native":
            assert all(sha(Path(path)) == digest for path, digest in artifact["build"]["files"].items())
    source = json.loads((run / "source-evidence.json").read_text())["files"]
    assert all(sha(run / "verification-source" / path) == digest for path, digest in source.items())
    end = json.loads((run / "end-source-check.json").read_text())
    assert end["all_current_launch_files_match_snapshot"] and end["files"] == source
    tests = list(ET.parse(run / "pytest.xml").iter("testcase"))
    assert len(tests) == 63 and all(test.find("error") is None and test.find("skipped") is None for test in tests)
    nodes = {test.attrib["classname"].replace(".", "/") + ".py::" + test.attrib["name"]: test.find("failure") is not None for test in tests}
    counts, failure_counts, reports, seen = Counter(), Counter(), [], set()
    paths = sorted((run / "cases").rglob("physical_store_queue.jsonl")) + sorted((run / "cases").rglob("psq_full.jsonl"))
    for path in paths:
        trace = rows(path)
        node, last = trace[0]["nodeid"], None
        assert node in nodes and node not in seen
        seen.add(node)
        by_tick = {}
        differences = []
        for row in trace:
            tick = row["post_tick"]
            assert row["nodeid"] == node and row["input"] == row["post_input"] and row["pre_tick"] + 1 == tick
            assert last is None or last + 2 == tick
            assert len(row["input"]) == 119 and len(row["before"]) == len(row["after"]) == 333
            by_tick[tick], last = row, tick
            counts["continuous_records"] += 1
            if path.name == "psq_full.jsonl":
                counts["full_reference_records"] += 1
                bad = {}
                for phase in ("before", "after"):
                    bad.update(masked_difference(row[phase], row.get("expected_" + phase, {}), row.get("masks_" + phase, {})))
                if row["checked"]:
                    assert not bad and not row.get("error")
                    counts["full_checked_records"] += 1
                else:
                    assert row.get("error")
                if bad:
                    differences.append(bad)
        witnesses = dependency_violations(trace)
        replay = None
        actor_path = path.with_name("psq_actor.jsonl")
        if actor_path.is_file():
            stepped = set()
            for event in rows(actor_path):
                kind = event["event"]
                if kind == "start":
                    assert replay is None
                    replay = ActorReplay(node)
                elif kind == "allocate":
                    replay.allocate(event["owner"])
                elif kind == "step":
                    replay.step(by_tick[event["tick"]], event)
                    stepped.add(event["tick"])
                elif kind == "checked":
                    assert set(event["uids"]) <= replay.done and event["completed"] == sorted(replay.done)
                    assert event["cancelled"] == sorted(replay.cancelled) and event["aborted"] == sorted(replay.aborted)
                elif kind in ("cancel", "reset"):
                    doomed = sorted(owner["uid"] for pos, owner in replay.live.items() if kind == "reset" or pos >= event["cut"])
                    assert doomed == event["aborted" if kind == "reset" else "cancelled"]
                    for uid in doomed:
                        owner = replay.all[uid]
                        target = replay.aborted if kind == "reset" else replay.cancelled
                        slots = replay.aborted_slots if kind == "reset" else replay.cancelled_slots
                        target.add(uid)
                        slots[owner["position"] % 64] = uid
                        del replay.live[owner["position"]]
                    if kind == "reset":
                        assert any(row["input"]["reset"] for row in trace if row["post_tick"] <= event["tick"])
                        replay.head = replay.tail = 0
                        replay.pending, replay.last_sta = None, (None, None)
                    else:
                        replay.tail = event["cut"]
                elif kind == "directed_check":
                    pins = by_tick[event["tick"]][event["phase"]]
                    assert event["actual"] == {key: pins[key] for key in event["expected"]}
                    assert event["passed"] == (not masked_difference(pins, event["expected"], event["bit_masks"]))
                else:
                    raise AssertionError(kind)
            if replay:
                if trace[-1].get("error") and trace[-1]["post_tick"] not in stepped:
                    replay.step(trace[-1])
                witnesses.extend(replay.violations)
                if differences and set(differences[-1]) == {"io_sbufferCtrl_req_flush"}:
                    final = trace[-1]
                    inp = final["input"]
                    pos = (ptr(inp, "io_fromVirtualStoreQueue_preCommitPtr_bits_") - 1) % 256
                    zero = next(owner for owner in replay.live.values() if owner["position"] % 256 == pos)
                    assert inp["io_fromVirtualStoreQueue_preCommitPtr_valid"] and zero["address"]["fu_op"] == 7
                    assert not replay.parts[zero["uid"]] and final["after"]["io_sbufferCtrl_req_flush"] == 1
                    assert any(final["before"][f"io_writeToSbuffer_req_{lane}_valid"] and inp[f"io_writeToSbuffer_req_{lane}_ready"] and
                               not final["before"][f"io_writeToSbuffer_req_{lane}_bits_wline"] for lane in range(2))
                    witnesses.append({"issue": "DEQ-ZERO-001", "tick": final["post_tick"], "uid": zero["uid"], "proof": "flush_after_old_nonzero_fire_without_own_zero_write"})
                retained = {owner["uid"] for owner in replay.live.values()}
                assert len(replay.all) == len(replay.done) + len(replay.cancelled) + len(replay.aborted) + len(retained)
                if not nodes[node]:
                    assert not retained and replay.pending is None
                counts.update(replay.counts)
                counts.update(actor_completed_uids=len(replay.done), actor_cancelled_uids=len(replay.cancelled), actor_reset_aborted_uids=len(replay.aborted),
                              actor_failure_retained_uids=len(retained), actor_same_slot_reset_reuse=sum(item["kind"] == "reset" for item in replay.reuse),
                              actor_same_slot_cancel_reuse=sum(item["kind"] == "cancel" for item in replay.reuse))
        check_path = path.with_name("psq_checks.jsonl")
        if check_path.is_file():
            for check in rows(check_path):
                pins = by_tick[check["tick"]][check["phase"]]
                assert check["actual"] == {key: pins[key] for key in check["expected"]}
                bad = masked_difference(pins, check["expected"], check["bit_masks"])
                assert check["passed"] == (not bad)
                counts["probe_directed_checks"] += 1
                if bad:
                    differences.append(bad)
        if "test_storage_expanded" in node:
            storage = storage_replay(trace, "test_cbo_all_slots" in node)
            counts["separate_long_stream_completed_uids"] += storage["completed_owners"]
        if "test_forward_safety" in node:
            witnesses.append(direct_forward_fault(trace, node))
        if nodes[node] and "test_real_parent_cache_error" in node:
            arrival = next(row for row in trace if row["input"]["io_toDCache_resp_valid"] and row["before"]["io_toDCache_resp_ready"])
            final = trace[-1]
            assert final["input"]["io_writeBack_ready"] and final["before"]["io_writeBack_valid"]
            for bit, field in ((7, "denied"), (19, "corrupt")):
                want = arrival["input"]["io_toDCache_resp_bits_" + field]
                assert arrival["after"][f"io_writeBack_bits_exceptionVec_{bit}"] == want and final["before"][f"io_writeBack_bits_exceptionVec_{bit}"] == 0
            witnesses.append({"issue": "DEQ-WB-001", "tick": final["post_tick"], "response_tick": arrival["post_tick"], "proof": "actual_WB_fire_loses_accepted_error"})
        if nodes[node] and "test_real_parent_split_tail" in node:
            final = trace[-1]
            pins, inp = final["before"], final["input"]
            assert pins["io_writeToSbuffer_req_1_valid"] and inp["io_writeToSbuffer_req_1_ready"]
            assert (pins["io_writeToSbuffer_req_1_bits_addr"], pins["io_writeToSbuffer_req_1_bits_mask"], pins["io_writeToSbuffer_req_1_bits_data"] & 0xFFFFFFFF,
                    pins["io_writeToSbuffer_req_1_bits_wline"]) == (0xABCD010, 15, 0x88776655, 1)
            witnesses.append({"issue": "DEQ-SPLIT-WLINE-001", "tick": final["post_tick"], "proof": "actual_split_tail_fire_has_neighbor_zero_control"})
        zero_path = path.with_name("zero-owner-check.json")
        if zero_path.is_file():
            evidence = json.loads(zero_path.read_text())
            wb_row = by_tick[evidence["actual_zero_wb_fire"]["tick"]]
            assert wb_row["before"]["io_writeBack_valid"] and wb_row["input"]["io_writeBack_ready"]
            assert wb_row["before"]["io_writeBack_bits_robIdx_value"] == 9
            zero_fires = []
            for row in trace:
                if row["post_tick"] > wb_row["post_tick"]:
                    continue
                for lane in range(2):
                    p = f"io_writeToSbuffer_req_{lane}_"
                    if row["before"][p + "valid"] and row["input"][p + "ready"] and row["before"][p + "bits_vaddr"] == 0x20000:
                        assert row["before"][p + "bits_addr"] == 0xDEF000 and row["before"][p + "bits_wline"] and row["before"][p + "bits_data"] == 0
                        zero_fires.append(row["post_tick"])
            assert len(zero_fires) == evidence["zero_transfers_before_wb"]
            assert ptr(trace[-1]["after"], "io_sqDeqPtr_") == (2 if evidence["old_queued"] else 1)
            if evidence["old_queued"]:
                assert not zero_fires and nodes[node]
                witnesses.append({"issue": "DEQ-ZERO-001", "tick": wb_row["post_tick"], "proof": "actual_zero_WB_and_SQ_release_without_any_own_zero_transfer",
                                  "sq_release_tick": trace[-1]["post_tick"], "zero_transfers": 0})
            else:
                assert len(zero_fires) == 1 and not nodes[node]
        assert bool(witnesses) == nodes[node], (node, witnesses)
        if nodes[node]:
            issues = {witness["issue"] for witness in witnesses}
            assert len(issues) == 1, (node, issues)
            failure_counts.update(issues)
        reports.append({"nodeid": node, "journal": str(path.relative_to(run)), "sha256": sha(path), "records": len(trace),
                        "actor_uid_replay": replay is not None, "violations": witnesses, "recorded_pin_differences": differences,
                        "same_slot_reuse": replay.reuse if replay else []})
    assert seen == set(nodes)
    assert failure_counts == {"FWD-ALIAS-001": 3, "FWD-RANGE-001": 6, "FWD-SQID-001": 1, "DEQ-WB-001": 3, "DEQ-SPLIT-WLINE-001": 3, "DEQ-ZERO-001": 2}
    assert counts["actor_same_slot_reset_reuse"] == 3 and counts["actor_same_slot_cancel_reuse"] == 1
    assert counts["separate_long_stream_completed_uids"] == 384
    native = json.loads((run / "line-audit.json").read_text())["native"][0]
    assert (native["line_hit"], native["line_total"], native["closure_line_hit"], native["closure_line_total"]) == (5396, 5396, 5817, 5817)
    functional = json.loads((run / "execution/functional-coverage.json").read_text())
    groups = {group["instance"]: group for group in functional["groups"]}
    checked = groups["lsq.physical_store_queue.checked"]["points"][0]["counts"]
    reached = groups["lsq.physical_store_queue.reached"]["points"][0]["counts"]
    assert len(checked) == 45 and all(reached[key] >= value for key, value in checked.items())
    missing = [key for key, value in checked.items() if not value]
    assert set(missing) == {"PSQ-CONCURRENT.seeded", "PSQ-FORWARD.alias", "PSQ-FORWARD.range", "PSQ-SPECIAL.split_wline", "PSQ-SPECIAL.wb_error", "PSQ-SPECIAL.zero_owner"}
    assert all(reached.values()), "unreached semantics cannot be declared attempted"
    auditors = {}
    for tool in (Path(__file__), ROOT / "tools/audit_psq_initial.py", ROOT / "tools/audit_psq_storage.py"):
        dest = run / "evidence-auditors" / tool.name
        dest.parent.mkdir(exist_ok=True)
        if dest.exists():
            assert sha(dest) == sha(tool)
        else:
            shutil.copy2(tool, dest)
        auditors[tool.name] = sha(dest)
    report = {"run": name, "status": "full_public_history_and_scoped_independent_UID_byte_audit_failures_retained", "dut_acceptance": "NOT_PASS", "tests": manifest["tests"],
              "counts": dict(counts), "failure_cases_by_issue": dict(failure_counts), "checked": 39, "reached": 45, "total_scenarios": 45, "missing_checked": missing,
              "snapshot_files": len(source), "manifest_sha256": sha(run / "execution/manifest.json"), "auditors": auditors, "cases": reports,
              "limits": "All public histories and recorded comparisons audited. UID replay separately covers external-actor cases and the two 384-owner storage streams, not every directed-probe allocation. Real PSQ retains all real children; actual VSQ/StoreQueue/Backend constraints and architectural outcomes remain unproved. Full-domain random has true failures; controls do not replace it. No DUT acceptance or branch/expression exhaustiveness claim."}
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
