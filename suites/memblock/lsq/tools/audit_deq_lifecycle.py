#!/usr/bin/env python3
"""Independent public-history/UID audit. No reference or internal-DUT imports.

Failures are retained as violations, never converted into DUT acceptance. The
probe cases are explicitly separate from the PSQ lifecycle replay cases.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def position(ptr):
    return int(ptr["first"]) * 128 + int(ptr["second"]) * 64 + ptr["value"]


def lines(path):
    return [json.loads(row) for row in path.read_text().splitlines()]


def segments(owner):
    st = owner["store"]
    result = []
    for part in range(2 if st["cross_word"] else 1):
        va = st["vaddr"] // 16 * 16 + part * 16
        pa = st["page"] * 4096 + st["vaddr"] % 4096 // 16 * 16 + part * 16
        if part and owner["second_page"] is not None:
            pa = owner["second_page"]
        mask = data = 0
        for index in range(16):
            address = st["vaddr"] + index
            if st["byte_mask"] >> index & 1 and va <= address < va + 16:
                byte = address - va
                mask += 1 << byte
                data |= (st["data"] >> (index * 8) & 255) << (byte * 8)
        result.append({"uid": owner["uid"], "part": part, "vaddr": va, "addr": pa, "mask": mask, "data": data,
                       "wline": int(st["cache_operation"] and st["cbo"] == 3)})
    return result


class Replay:
    def __init__(self, base):
        self.head = self.read = self.tail = base
        self.live, self.all = {}, {}
        self.queue = []
        self.read_uids, self.done, self.aborted, self.zero_issued = set(), set(), set(), set()
        self.parts, self.final_fire, self.finished = {}, {}, {}
        self.bus = None
        self.zero_drained = set()
        self.counts = Counter()
        self.violations = []
        self.sq_codes, self.rob_codes, self.reuse = set(), set(), []
        self.aborted_slots = {}

    def allocate(self, owner):
        uid, pos = owner["uid"], owner["position"]
        assert uid not in self.all and pos == self.tail and self.tail - self.head < 64
        self.live[pos] = self.all[uid] = owner
        self.parts[uid] = set()
        self.tail += 1
        self.counts["allocated"] += 1

    def check_queue(self, pins, tick, phase):
        for lane in range(2):
            prefix = f"io_writeToSbuffer_req_{lane}_"
            assert pins[prefix + "valid"] == int(lane < len(self.queue)), (tick, phase, "ordered-valid")
            if lane >= len(self.queue):
                continue
            word = self.queue[lane]
            for field in ("vaddr", "addr", "mask", "data", "wline"):
                mask = sum(255 << (8 * byte) for byte in range(16) if word["mask"] >> byte & 1) if field == "data" else -1
                got, want = pins[prefix + "bits_" + field], word[field]
                if (got ^ want) & mask:
                    assert field == "wline" and got == 1 and want == 0
                    self.violations.append({"issue": "DEQ-SPLIT-WLINE-001", "tick": tick, "phase": phase, "lane": lane,
                                            "uid": word["uid"], "part": word["part"], "actual": got, "expected": want})
            self.counts["valid_byte_observations"] += word["mask"].bit_count()

    def check_wb(self, row, phase):
        pins, inp = row[phase], row["input"]
        if not pins["io_writeBack_valid"]:
            assert not pins["io_exceptionInfo_valid"]
            return
        bus = self.bus
        if bus is None:
            owner = self.live[self.read]
            assert owner["store"]["cache_operation"] and owner["store"]["cbo"] == 3
            assert owner["uid"] in self.zero_drained
            bus = {"owner": owner, "response": True, "kind": "zero", "denied": False, "corrupt": False}
        assert bus["response"] and bus["kind"] in ("cache", "io", "zero")
        owner = bus["owner"]
        assert owner["position"] == self.read
        for prefix in ("io_writeBack_bits_", "io_exceptionInfo_bits_"):
            for field, port in (("flag", "flag"), ("value", "value"), ("former", "isFormer")):
                assert pins[prefix + "robIdx_" + port] == int(owner["rob"][field])
            for bit, field in ((7, "denied"), (19, "corrupt")):
                actual, want = pins[prefix + "exceptionVec_" + str(bit)], int(bus[field])
                if actual != want:
                    assert actual == 0 and want == 1
                    self.violations.append({"issue": "DEQ-WB-001", "tick": row["post_tick"], "phase": phase, "uid": owner["uid"],
                                            "pin": prefix + "exceptionVec_" + str(bit), "actual": actual, "expected": want})
        assert pins["io_exceptionInfo_bits_vaddr"] == owner["store"]["vaddr"]
        assert pins["io_exceptionInfo_bits_isHyper"] == int(owner["store"]["hyper"])
        self.rob_codes.add((owner["rob"]["flag"], owner["rob"]["value"], owner["rob"]["former"]))

    def step(self, row, logged=None):
        inp, before, after, tick = row["input"], row["before"], row["after"], row["post_tick"]
        assert not inp["reset"] and position(inp["read_ptr"]) == self.read % 256
        assert position(inp["dequeue_ptrs"][0]) == self.head % 256
        assert position(inp["dequeue_ptrs"][1]) == (self.head + 1) % 256
        self.sq_codes.update((self.read % 256, self.head % 256))
        for phase in ("before", "after"):
            pins = row[phase]
            for lane, ptr in enumerate(inp["dequeue_ptrs"]):
                value = (position(ptr) + pins["io_sqDeqCnt"]) % 256
                prefix = f"io_deqPtrExtNext_{lane}_"
                assert (pins[prefix + "first_flag"], pins[prefix + "second_flag"], pins[prefix + "value"]) == (value // 128, value // 64 % 2, value % 64)
        for lane, st in enumerate(inp["stores"]):
            owner = self.live.get(self.read + lane)
            if owner:
                for key in ("vaddr", "page", "byte_mask", "data", "memory_type", "cbo", "inactive", "cross_word", "cache_operation"):
                    assert st[key] == owner["store"][key]
                assert not st["committed"] or owner["store"]["committed"]
        self.check_queue(before, tick, "before")
        head_owner = self.live.get(self.read)
        if head_owner and head_owner["uid"] in self.zero_issued and before["io_sbufferCtrl_req_flush"] and inp["sbuffer_empty"] and not self.queue:
            assert self.parts[head_owner["uid"]] == {0}
            self.zero_drained.add(head_owner["uid"])
        self.check_wb(row, "before")
        consumed = []
        for lane in range(2):
            if before[f"io_writeToSbuffer_req_{lane}_valid"] and inp["sbuffer_ready"][lane]:
                assert lane == len(consumed), "Sbuffer consumption must be prefix"
                seg = self.queue[lane]
                uid, part = seg["uid"], seg["part"]
                assert part not in self.parts[uid]
                self.parts[uid].add(part)
                self.final_fire[uid] = tick
                consumed.append(seg)
                self.counts["sbuffer_fires"] += 1
        del self.queue[:len(consumed)]
        for kind, valid, ready in (("cache", before["io_toDCache_req_valid"], inp["cache_ready"]),
                                   ("uncache", before["io_toUncacheBuffer_req_valid"], inp["uncache_ready"])):
            if valid and ready:
                assert head_owner and self.bus is None
                st = head_owner["store"]
                if kind == "uncache":
                    kind = "nc" if st["memory_type"] in (1, 5) else "io"
                    prefix = "io_toUncacheBuffer_req_bits_"
                    assert before[prefix + "id"] == self.read % 64
                    assert before[prefix + "vaddr"] == st["vaddr"] and before[prefix + "addr"] == st["page"] * 4096 + st["vaddr"] % 4096
                    for field, port in (("flag", "flag"), ("value", "value"), ("former", "isFormer")):
                        assert before[prefix + "robIdx_" + port] == int(head_owner["rob"][field])
                    self.rob_codes.add((head_owner["rob"]["flag"], head_owner["rob"]["value"], head_owner["rob"]["former"]))
                    mask = data = 0
                    for index in range(16):
                        address = st["vaddr"] + index
                        if st["byte_mask"] >> index & 1:
                            assert address // 8 == st["vaddr"] // 8
                            mask |= 1 << (address % 8)
                            data |= (st["data"] >> (index * 8) & 255) << (address % 8 * 8)
                    bits = sum(255 << (8 * byte) for byte in range(8) if mask >> byte & 1)
                    assert before[prefix + "mask"] == mask and not ((before[prefix + "data"] ^ data) & bits)
                else:
                    assert before["io_toDCache_req_bits_opcode"] == st["cbo"]
                    assert before["io_toDCache_req_bits_address"] == st["page"] * 4096 + st["vaddr"] % 4096
                self.bus = {"kind": kind, "owner": head_owner, "response": False, "denied": False, "corrupt": False}
                self.counts[kind + "_requests"] += 1
        ack = False
        if self.bus:
            kind = self.bus["kind"]
            if kind == "cache" and inp["cache_response"] and before["io_toDCache_resp_ready"]:
                assert not self.bus["response"]
                self.bus.update(response=True, denied=inp["cache_denied"], corrupt=inp["cache_corrupt"])
            elif kind == "io" and inp["uncache_response"]:
                assert not self.bus["response"]
                self.bus["response"] = True
            elif kind == "nc" and inp["uncache_ack_valid"] and not inp["uncache_ack_to_load"]:
                uid = self.bus["owner"]["uid"]
                self.finished[uid] = tick
                self.bus, ack = None, True
                self.counts["nc_acknowledgements"] += 1
        # After-response WB is still associated with the old head at this edge.
        self.check_wb(row, "after")
        wb = bool(before["io_writeBack_valid"] and inp["writeback_ready"])
        if wb:
            if head_owner["store"]["cache_operation"] and head_owner["store"]["cbo"] == 3:
                assert self.bus is None and head_owner["uid"] in self.zero_drained
            else:
                assert self.bus and self.bus["response"] and head_owner["uid"] == self.bus["owner"]["uid"]
            self.finished[head_owner["uid"]] = tick
            self.bus = None
            self.counts["writeback_fires"] += 1
        moved = []
        for pos in range(self.read, self.read + before["io_rdataPtrMoveCnt"]):
            owner = self.live[pos]
            uid, st = owner["uid"], owner["store"]
            assert st["committed"] and uid not in self.read_uids
            if st["inactive"]:
                pass
            elif st["cache_operation"] or st["memory_type"]:
                assert pos == self.read and (wb or ack) and uid in self.finished
            else:
                self.queue.extend(segments(owner))
            self.read_uids.add(uid)
            moved.append(uid)
        if head_owner and head_owner["store"]["cache_operation"] and head_owner["store"]["cbo"] == 3:
            uid = head_owner["uid"]
            if not before["io_writeToSbuffer_req_0_valid"] and after["io_writeToSbuffer_req_0_valid"] and uid not in self.zero_issued:
                assert not self.queue and head_owner["store"]["data"] == 0
                self.queue.extend(segments(head_owner))
                self.zero_issued.add(uid)
                self.counts["zero_owners_written"] += 1
        self.read += before["io_rdataPtrMoveCnt"]
        self.check_queue(after, tick, "after")
        retired = []
        for pos in range(self.head, self.head + before["io_sqDeqCnt"]):
            owner = self.live[pos]
            uid, st = owner["uid"], owner["store"]
            assert uid in self.read_uids and uid not in self.done
            if st["inactive"]:
                assert not self.parts[uid]
            elif st["cache_operation"] or st["memory_type"]:
                assert uid in self.finished and self.finished[uid] < tick
                if st["cache_operation"] and st["cbo"] == 3:
                    assert self.parts[uid] == {0} and self.final_fire[uid] < self.finished[uid]
            else:
                assert self.parts[uid] == ({0, 1} if st["cross_word"] else {0}) and self.final_fire[uid] + 2 == tick
            self.done.add(uid)
            retired.append(uid)
            del self.live[pos]
            if pos % 64 in self.aborted_slots:
                self.reuse.append({"slot": pos % 64, "old_uid": self.aborted_slots[pos % 64], "new_uid": uid, "completed_tick": tick})
        self.head += before["io_sqDeqCnt"]
        assert self.head <= self.read <= self.tail and len(self.queue) <= 2
        if logged is not None:
            assert (logged["head_after"], logged["read_after"], logged["retired"], logged["read_uids"]) == (self.head, self.read, retired, moved)
            assert [(seg["uid"], seg["part"]) for seg in logged["consumed"]] == [(seg["uid"], seg["part"]) for seg in consumed]
        self.counts["replayed_steps"] += 1


def audit(name):
    run = ROOT / "results" / name
    manifest = json.loads((run / "execution/manifest.json").read_text())
    assert manifest["state"] == "committed" and manifest["cleanup_complete"] and manifest["coverage_complete"]
    for artifact in manifest["artifacts"]:
        assert sha(Path(artifact["path"])) == artifact["sha256"]
        if artifact["kind"] == "native":
            assert all(sha(Path(path)) == digest for path, digest in artifact["build"]["files"].items())
    source = json.loads((run / "source-evidence.json").read_text())["files"]
    assert all(sha(run / "verification-source" / path) == digest for path, digest in source.items())
    end = json.loads((run / "end-source-check.json").read_text())
    assert end["all_current_launch_files_match_snapshot"] and end["files"] == source
    cases = list(ET.parse(run / "pytest.xml").iter("testcase"))
    assert not any(case.find("skipped") is not None or case.find("error") is not None for case in cases)
    nodes = {case.attrib["classname"].replace(".", "/") + ".py::" + case.attrib["name"]: case.find("failure") is not None for case in cases}
    assert len(nodes) == len(cases) and Counter("FAIL" if fail else "PASS" for fail in nodes.values()) == manifest["tests"]
    assert manifest["tests"] == {"PASS": 71, "FAIL": 18} and len(nodes) == 89
    counts, case_reports, seen, failure_counts, all_sq, all_rob = Counter(), [], set(), Counter(), set(), set()
    for path in sorted((run / "cases").rglob("deq*.jsonl")):
        if path.name not in ("deq_full.jsonl", "deq_module.jsonl"):
            continue
        rows = lines(path)
        node, last, force = rows[0]["nodeid"], None, False
        assert node in nodes and node not in seen
        seen.add(node)
        by_tick = {}
        differences = []
        for row in rows:
            tick, inp = row["post_tick"], row["input"]
            assert row["nodeid"] == node and inp == row["post_input"]
            assert row["pre_tick"] + 1 == tick and (last is None or last + 2 == tick)
            last = tick
            by_tick[tick] = row
            assert 0 <= inp["valid_count"] <= 128
            force = False if inp["reset"] else inp["valid_count"] >= 60 or inp["valid_count"] >= 55 and force
            assert row["after"]["io_sbufferCtrl_req_forceWrite"] == int(force)
            counts["continuous_records"] += 1
            if path.name == "deq_full.jsonl":
                bad = []
                for phase in ("before", "after"):
                    for key, want in row.get("expected_" + phase, {}).items():
                        got = row[phase][key]
                        if (got ^ want) & row["masks_" + phase].get(key, -1):
                            bad.append({"pin": key, "actual": got, "expected": want, "phase": phase, "tick": tick})
                assert row["checked"] == (not bad)
                differences.extend(bad)
        replay = None
        if path.name == "deq_full.jsonl":
            events = lines(path.with_name("deq_psq.jsonl"))
            stepped = set()
            for event in events:
                kind = event["event"]
                if kind == "start":
                    assert replay is None
                    replay = Replay(event["base"])
                elif kind == "allocate":
                    replay.allocate(event["owner"])
                elif kind == "permission":
                    owner = replay.all[event["uid"]]
                    owner["store"]["committed"] = event["committed"]
                elif kind == "step":
                    replay.step(by_tick[event["tick"]], event)
                    stepped.add(event["tick"])
                elif kind == "reset":
                    assert event["aborted"] == sorted(owner["uid"] for owner in replay.live.values())
                    assert by_tick[event["tick"]]["input"]["reset"]
                    for owner in replay.live.values():
                        replay.aborted.add(owner["uid"])
                        replay.aborted_slots[owner["position"] % 64] = owner["uid"]
                    replay.live.clear()
                    replay.queue.clear()
                    replay.bus = None
                    replay.head = replay.read = replay.tail = 0
                elif kind == "checked":
                    assert set(event["uids"]) <= replay.done
                    assert event["completed"] == sorted(replay.done) and event["aborted"] == sorted(replay.aborted)
                else:
                    raise AssertionError(kind)
            if replay:
                if rows[-1].get("error") and rows[-1]["post_tick"] not in stepped:
                    replay.step(rows[-1])
                counts.update(replay.counts)
                all_sq.update(replay.sq_codes)
                all_rob.update(replay.rob_codes)
                retained = {owner["uid"] for owner in replay.live.values()}
                assert len(replay.all) == len(replay.done) + len(replay.aborted) + len(retained)
                counts.update({"completed": len(replay.done), "reset_aborted": len(replay.aborted), "failure_retained": len(retained), "reset_same_slot_reuse": len(replay.reuse)})
                if not nodes[node]:
                    assert not replay.live and not replay.queue and replay.bus is None
                assert bool(replay.violations) == nodes[node]
        else:
            for check in lines(path.with_name("deq_checks.jsonl")):
                row = by_tick[check["tick"]]
                actual = row[check["phase"]]
                assert check["actual"] == {key: actual[key] for key in check["expected"]}
                bad = [{"pin": key, "actual": actual[key], "expected": want, "phase": check["phase"], "tick": check["tick"]}
                       for key, want in check["expected"].items() if (actual[key] ^ want) & check["bit_masks"].get(key, -1)]
                assert check["passed"] == (not bad)
                differences.extend(bad)
            if nodes[node] and "actual_split_tail_fire" in node:
                last_row = rows[-1]
                first = next(st for row in rows for st in row["input"]["stores"] if st["committed"] and st["cross_word"])
                expected = segments({"uid": 0, "store": first, "second_page": None})[1]
                pins = last_row["before"]
                assert last_row["input"]["sbuffer_ready"] == [True, True]
                assert pins["io_writeToSbuffer_req_0_valid"] and pins["io_writeToSbuffer_req_1_valid"]
                assert expected["wline"] == 0 and pins["io_writeToSbuffer_req_1_bits_wline"] == 1
                for field in ("addr", "vaddr", "mask", "data"):
                    mask = 0xFFFFFFFF if field == "data" else -1
                    assert not ((pins["io_writeToSbuffer_req_1_bits_" + field] ^ expected[field]) & mask)
                counts["independent_bad_wline_actual_fires"] += 1
            elif nodes[node]:
                arrival = next(row for row in rows if row["input"]["cache_response"] and row["before"]["io_toDCache_resp_ready"])
                bad = rows[-1]
                assert arrival["input"]["stores"] == bad["input"]["stores"]
                for bit, field in ((7, "cache_denied"), (19, "cache_corrupt")):
                    for prefix in ("io_writeBack_bits_exceptionVec_", "io_exceptionInfo_bits_exceptionVec_"):
                        assert arrival["after"][prefix + str(bit)] == int(arrival["input"][field])
                if "delayed_writeback_fire" in node:
                    assert bad["input"]["writeback_ready"] and bad["before"]["io_writeBack_valid"] and bad["before"]["io_rdataPtrMoveCnt"] == 1
                    counts["independent_lost_error_actual_wb_fires"] += 1
        assert bool(differences) == nodes[node], node
        if differences:
            pins = {diff["pin"] for diff in differences}
            if all("exceptionVec_" in pin for pin in pins):
                issue = "DEQ-WB-001"
            else:
                assert pins == {"io_writeToSbuffer_req_1_bits_wline"}
                issue = "DEQ-SPLIT-WLINE-001"
            failure_counts[issue] += 1
        case_reports.append({"nodeid": node, "journal": str(path.relative_to(run)), "sha256": sha(path), "records": len(rows),
                             "kind": "public_psq_lifecycle" if replay else "public_probe_or_occupancy_only", "differences": differences,
                             "lifecycle_violations": replay.violations if replay else [], "same_slot_reset_reuse": replay.reuse if replay else []})
    assert seen == set(nodes)
    assert failure_counts == {"DEQ-WB-001": 9, "DEQ-SPLIT-WLINE-001": 9}
    assert counts["independent_bad_wline_actual_fires"] == 4 and counts["independent_lost_error_actual_wb_fires"] == 3
    assert len(all_sq) == 256 and counts["reset_same_slot_reuse"] == 4
    line_audit = json.loads((run / "line-audit.json").read_text())
    native = line_audit["native"][0]
    assert (native["line_hit"], native["line_total"], native["closure_line_hit"], native["closure_line_total"]) == (46, 46, 124, 124)
    functional = json.loads((run / "execution/functional-coverage.json").read_text())
    groups = {group["instance"]: group for group in functional["groups"]}
    checked = groups["lsq.deq_module.checked"]["points"][0]["counts"]
    reached = groups["lsq.deq_module.reached"]["points"][0]["counts"]
    assert set(key for key, value in checked.items() if not value) == {"DEQ-EXCEPTION.held", "DEQ-SPLIT.zero_neighbor"}
    assert all(reached[key] >= value for key, value in checked.items())
    dest = run / "evidence-auditors" / Path(__file__).name
    dest.parent.mkdir(exist_ok=True)
    if dest.exists():
        assert sha(dest) == sha(Path(__file__))
    else:
        shutil.copy2(Path(__file__), dest)
    report = {"run": name, "status": "public_history_and_lifecycle_audited_failures_retained", "dut_acceptance": "NOT_PASS", "tests": manifest["tests"],
              "counts": dict(counts), "failure_cases_by_issue": dict(failure_counts), "sq_encodings_observed": len(all_sq), "rob_identities_observed": len(all_rob),
              "checked_scenarios": sum(bool(value) for value in checked.values()), "total_scenarios": len(checked), "snapshot_files": len(source),
              "manifest_sha256": sha(run / "execution/manifest.json"), "auditor_sha256": sha(dest), "cases": case_reports,
              "limits": "Leaf Deq retains real EnterSbufferQueue. PSQ is an external actor, not the real parent. wline and WB violations are strict leaf-interface evidence; parent producer reachability and architectural consequences remain unproved. DA is not exhaustive branch/expression coverage."}
    out = run / "lifecycle-audit.json"
    if out.exists():
        assert json.loads(out.read_text()) == report
    else:
        with out.open("x") as stream:
            json.dump(report, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
