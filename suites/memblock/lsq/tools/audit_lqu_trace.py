#!/usr/bin/env python3
"""Audit LQU evidence and independently reconstruct public transaction lifetimes.

No import from lsqverify. Checks stored cycle comparisons, plus a separate
input/FIFO, bus/SID, wakeup/bypass/exception history. This is not a second DUT
execution or an independent reimplementation of the two-level arbiter.
"""
import argparse
from collections import Counter, deque
from functools import cmp_to_key
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BITS = (23, 21, 19, 15, 13, 7, 6, 5, 4, 3)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rob(inp, prefix):
    return {"flag": bool(inp[prefix + "flag"]), "value": inp[prefix + "value"], "former": bool(inp[prefix + "isFormer"])}


def younger(a, b):
    def serial(p):
        assert 0 <= p["value"] < 160
        return 2 * (p["value"] + 160 * p["flag"]) + (not p["former"])
    distance = (serial(a) - serial(b)) % 640
    assert distance != 320
    return 0 < distance < 320


def flush(q, red):
    return red["valid"] and (younger(q["rob"], red["rob"]) or red["self"] and q["rob"] == red["rob"])


def decode(inp, lane):
    prefix = f"io_req_{lane}_"
    def get(name):
        return inp[prefix + name]
    q = {"valid": True, "rob": rob(inp, prefix + "bits_uop_robIdx_"),
         "lq": {"flag": bool(get("bits_uop_lqIdx_flag")), "value": get("bits_uop_lqIdx_value")},
         **{name: get("bits_" + name) for name in ("vaddr", "fullva", "paddr", "gpaddr", "mask")},
         **{name: bool(get("bits_" + field)) for name, field in (("nc", "nc"), ("mmio", "mmio"), ("memory_backed", "memBackTypeMM"), ("hyper", "isHyper"), ("nonleaf", "isForVSnonLeafPTE"))},
         "exceptions": sum(get(f"bits_uop_exceptionVec_{bit}") << bit for bit in BITS)}
    return {"entry": q, "ftq": {"flag": bool(get("bits_uop_ftqPtr_flag")), "value": get("bits_uop_ftqPtr_value")},
            "offset": get("bits_uop_ftqOffset"), "rvc": bool(get("bits_uop_isRVC")), "checkpoint": get("bits_uop_perfDebugInfo_runahead_checkpoint_id"),
            "need_replay": bool(get("bits_rep_info_need_rep")), "uncache_cause": bool(get("bits_rep_info_cause_0"))}


def bus_fields(q, slot):
    return {"robIdx_flag": int(q["rob"]["flag"]), "robIdx_value": q["rob"]["value"], "robIdx_isFormer": int(q["rob"]["former"]),
            "cmd": 0, "addr": q["paddr"], "vaddr": q["vaddr"], "mask": (q["mask"] >> (8 if q["paddr"] & 8 else 0)) & 255,
            "id": slot, "nc": int(q["nc"]), "memBackTypeMM": int(q["memory_backed"])}


def differences(actual, expected):
    return {key: {"actual": actual[key], "expected": value} for key, value in expected.items() if actual[key] != value}


def audit(name):
    run = ROOT / "results" / name
    manifest_path = run / "execution/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert manifest["state"] == "committed" and manifest["coverage_complete"] and manifest["cleanup_complete"]
    assert manifest["pytest_exitstatus"] == 1, "never certifies DUT acceptance with a known failure"
    for artifact in manifest["artifacts"]:
        assert sha(Path(artifact["path"])) == artifact["sha256"]
        if artifact["kind"] == "native":
            for path, digest in artifact["build"]["files"].items():
                assert sha(Path(path)) == digest
    snapshot = json.loads((run / "source-evidence.json").read_text())
    for path, digest in snapshot["files"].items():
        assert sha(run / "verification-source" / path) == digest
    cases = list(ET.parse(run / "pytest.xml").iter("testcase"))
    assert not any(c.find("error") is not None or c.find("skipped") is not None for c in cases)
    failures = {c.attrib["classname"].replace(".", "/") + ".py::" + c.attrib["name"] for c in cases if c.find("failure") is not None}
    known = {"tests/load_uncache/test_initial_probes.py::test_sid_reused_after_response_preserves_old_unconsumed_data",
             *(f"tests/load_uncache/test_sid_boundaries.py::test_old_{kind}_held_while_new_same_sid_{tail}_arrives[{sid}]"
               for kind, tail in (("data", "response"), ("error", "error")) for sid in (0, 3, 15))}
    known.add("tests/load_uncache/test_timing_boundaries.py::test_multiple_mmio_selectors_interface_priority_not_rob_legality_claim")
    assert failures == known
    assert manifest["tests"] == {"PASS": len(cases) - 8, "FAIL": 8}
    issues = json.loads((run / "verification-source/manifest/known-issues.json").read_text())["issues"]
    sid_issue = next(item for item in issues if item["id"] == "LQU-SID-001")
    boundary_issue = next(item for item in issues if item["id"] == "LQU-MMIO-IF-001")
    assert set(sid_issue["failure_cases"]) | {boundary_issue["nodeid"]} == known
    assert sid_issue["not_a_waiver"] and boundary_issue["not_a_waiver"]
    line_path = run / "line-audit.json"
    native = json.loads(line_path.read_text())["native"][0]
    assert native["dut"] == "load_queue_uncache" and native["line_hit"] == 1120 and native["line_total"] == 1126
    assert native["closure_line_hit"] == 3169 and native["closure_line_total"] == 3175
    assert not any(row["uncovered"] for row in native["dependencies"])
    static = json.loads((run / "static-gap-proof.json").read_text())
    assert static["status"] == "six_guarded_defaults_proven" and not static["remaining_not_proven"]
    assert static["source_sha256"] == native["source_sha256"] and static["line_audit_sha256"] == sha(line_path)
    functional = json.loads((run / "execution/functional-coverage.json").read_text())
    groups = {g["instance"].rsplit(".", 1)[-1]: g for g in functional["groups"]}
    assert set(groups) == {"reached", "checked"}
    for group in groups.values():
        assert group["collection_complete"] and not group["points"][0]["unknown"] and not group["points"][0]["unmatched"]
    reached, checked = (groups[key]["points"][0]["counts"] for key in ("reached", "checked"))
    assert set(reached) == set(checked) and all(reached.values())
    assert all(0 <= checked[key] <= reached[key] for key in reached)
    assert {key for key, count in checked.items() if not count} == {"LQU-ID.returned_sid_reuse", "LQU-ARB.mmio_selector_boundary"}
    journals = sorted((run / "cases").rglob("load_queue_uncache.jsonl"))
    assert len(journals) == len(cases)
    rows, error_rows, entry_type_lane, actual_ids = [], [], set(), set()
    for path in journals:
        owned, jobs, saved, held = {}, {}, [], None
        free_fifo, offered, wait, selected = deque(range(16)), 16, [set() for _ in range(4)], []
        red_hist = [None, None]
        previous_match = [None] * 3
        serial = 0
        last_tick = None
        counters = Counter(records=0, checked=0, reset_edges=0, allocations=0, filtered=0, rejected=0,
                           internal_captures=0, external_accepts=0, id_acks=0, responses=0, response_deliveries=0,
                           wakeups=0, consumptions=0, cancel_releases=0, reset_owners=0, bypass_lane_hits=0,
                           exception_reports=0, s2_lane_results=0, rollback_reports=0)
        records = [json.loads(line) for line in path.read_text().splitlines()]
        for index, record in enumerate(records):
            counters["records"] += 1
            assert record["pre_tick"] + 1 == record["post_tick"]
            if last_tick is not None:
                assert record["post_tick"] == last_tick + 2
            last_tick = record["post_tick"]
            inp, pre, post = record["input"], record["before"], record["after"]
            assert inp == record["post_input"] and record["scope"] == "general_public_pin_reference"
            if inp["reset"]:
                assert not record["checked"] and "error" not in record
                counters["reset_edges"] += 1
                counters["reset_owners"] += len(owned)
                owned, jobs, saved, held = {}, {}, [], None
                free_fifo, offered, wait, selected = deque(range(16)), 16, [set() for _ in range(4)], []
                red_hist, previous_match = [None, None], [None] * 3
                continue
            change = record["change"]
            assert not differences(pre, record["expected_before"])
            post_diff = differences(post, record["expected_after"])
            assert set(tx["uid"] for tx in change["before"]) == {owner["uid"] for owner in owned.values()}
            red = {"valid": bool(inp["io_redirect_valid"]), "rob": rob(inp, "io_redirect_bits_robIdx_"), "self": bool(inp["io_redirect_bits_level"])}
            eligible, rejected_filter = [], []
            for lane, load in saved:
                q = load["entry"]
                reason = ("redirect" if any(flush(q, r) for r in (red, red_hist[0]) if r) else
                          "exception" if q["exceptions"] else "replay" if load["need_replay"] and not load["uncache_cause"] else
                          "type" if not (q["nc"] or q["mmio"]) else None)
                (rejected_filter if reason else eligible).append((lane, load, reason) if reason else (lane, load))
            assert change["filtered"] == [{"lane": lane, "load": load, "reason": why} for lane, load, why in rejected_filter]
            counters["filtered"] += len(rejected_filter)
            accepts, rejected = eligible[:min(3, offered)], eligible[min(3, offered):]
            assert change["rejected"] == [load for lane, load in rejected]
            counters["rejected"] += len(rejected)
            rollback = next((load for lane, load in rejected if not any(flush(load["entry"], r) for r in (red, *red_hist) if r)), None)
            assert change["rollback"] == rollback and post["io_rollback_valid"] == bool(rollback)
            counters["rollback_reports"] += rollback is not None
            original_owned = dict(owned)
            if pre["io_uncache_req_valid"]:
                assert held is not None
                owner = owned[held]
                assert {key: pre["io_uncache_req_bits_" + key] for key in bus_fields(owner["q"], held)} == bus_fields(owner["q"], held)
                if inp["io_uncache_req_ready"]:
                    assert held not in jobs
                    jobs[held] = {"uid": owner["uid"], "sid": None}
                    assert change["external_accept"] == owner["uid"]
                    counters["external_accepts"] += 1
            else:
                assert held is None
            mid = inp["io_uncache_idResp_bits_mid"]
            if inp["io_uncache_idResp_valid"] and mid in owned:
                assert mid in jobs
                jobs[mid]["sid"] = inp["io_uncache_idResp_bits_sid"]
                counters["id_acks"] += 1
            received = set()
            if inp["io_uncache_resp_valid"]:
                counters["responses"] += 1
                received = {slot for slot, job in jobs.items() if job["sid"] == inp["io_uncache_resp_bits_id"]}
            assert set(change["response_uids"]) == {owned[slot]["uid"] for slot in received}
            # Matches use only packets already returned and already woken.
            matches = []
            consumed = set()
            for lane in range(3):
                prefix = f"io_bypass_{lane}_s0Req_"
                hit = []
                if inp[prefix + "valid"]:
                    for slot, owner in owned.items():
                        q = owner["q"]
                        if owner["woke"] and q["lq"] == {"flag": bool(inp[prefix + "bits_lqIdx_flag"]), "value": inp[prefix + "bits_lqIdx_value"]} and inp[prefix + ("bits_isNCReplay" if q["nc"] else "bits_isMMIOReplay")]:
                            hit.append(slot)
                slot = min(hit, default=None)
                matches.append(owned[slot] if slot is not None else None)
                consumed.update(hit)
            expect_post = {}
            for lane, item in enumerate(matches):
                a, b = f"io_bypass_{lane}_s1Resp_", f"io_bypass_{lane}_s2Resp_"
                expect_post[a + "valid"] = int(item is not None)
                expect_post[b + "valid"] = int(previous_match[lane] is not None)
                if item:
                    expect_post[a + "bits_paddr"] = item["q"]["paddr"]
                    counters["bypass_lane_hits"] += 1
                    entry_type_lane.add((item["slot"], item["q"]["nc"], lane))
                if previous_match[lane]:
                    packet = previous_match[lane]["packet"]
                    expect_post.update({b + "bits_data": packet["data"] * ((1 << 64) + 1), b + "bits_derr": packet["error"], b + "bits_nderr": packet["nderr"]})
                    counters["s2_lane_results"] += 1
            expect_post["io_exceptionInfo_valid"] = int(bool(consumed))
            if consumed:
                owner = owned[min(consumed)]
                q, packet = owner["q"], owner["packet"]
                metadata = {"robIdx_flag": q["rob"]["flag"], "robIdx_value": q["rob"]["value"], "robIdx_isFormer": q["rob"]["former"],
                            "vaddr": q["fullva"], "gpaddr": q["gpaddr"] & ((1 << 50) - 1), "isHyper": q["hyper"], "isForVSnonLeafPTE": q["nonleaf"],
                            **{f"exceptionVec_{bit}": (packet["error"] if bit == 19 else packet["nderr"] if bit == 5 else q["exceptions"] >> bit & 1) for bit in BITS}}
                expect_post.update({"io_exceptionInfo_bits_" + key: int(value) for key, value in metadata.items()})
                counters["exception_reports"] += 1
            for key, value in expect_post.items():
                assert record["expected_after"][key] == value, (path, index, key, "stored expected not independently justified")
            independent_diff = differences(post, expect_post)
            if post_diff:
                assert index == len(records) - 1 and "error" in record and not record["checked"]
                if "io_uncache_req_valid" in post_diff:
                    assert not independent_diff and post_diff["io_uncache_req_valid"] == {"actual": 0, "expected": 1}
                    assert all(key.startswith("io_uncache_req_") for key in post_diff)
                    lower = next(owner for owner in owned.values() if owner["uid"] == change["internal_accept"])
                    assert lower["q"]["mmio"] and not lower["launched"] and len(owned) == 1
                    error_rows.append({"journal": str(path.relative_to(run)), "tick": last_tick, "issue": "LQU-MMIO-IF-001",
                                       "domain": "UNIT-INTERFACE boundary, not normal ROB permission traffic", "differences": post_diff})
                else:
                    assert independent_diff == post_diff
                    assert set(post_diff) in ({"io_bypass_0_s2Resp_bits_data"}, {"io_bypass_1_s2Resp_bits_data"}, {"io_exceptionInfo_bits_exceptionVec_19"})
                    reused = [row["input"]["io_uncache_resp_bits_id"] for row in records if row["input"]["io_uncache_resp_valid"]]
                    assert len(reused) == 2 and reused[0] == reused[1] and reused[0] in (0, 3, 15)
                    error_rows.append({"journal": str(path.relative_to(run)), "tick": last_tick, "sid": reused[0], "issue": "LQU-SID-001", "differences": post_diff})
            else:
                assert not independent_diff and record["checked"] and "error" not in record
                counters["checked"] += 1
            # Wakeup is sampled BEFORE this edge; current redirect may still
            # permit the event, but a previous deferred cancel cannot.
            for kind in ("nc", "mmio"):
                candidates = [slot for slot, owner in owned.items() if owner["packet"] is not None and not owner["woke"] and not owner["deferred"] and owner["q"][kind]]
                assert pre[f"io_{kind}Wakeup_valid"] == bool(candidates)
                if candidates:
                    slot = min(candidates)
                    q = owned[slot]["q"]
                    assert pre[f"io_{kind}Wakeup_bits_flag"] == q["lq"]["flag"] and pre[f"io_{kind}Wakeup_bits_value"] == q["lq"]["value"]
                    owned[slot]["woke"] = True
                    counters["wakeups"] += 1
            free = set(consumed)
            for slot, owner in owned.items():
                is_cancel = flush(owner["q"], red)
                if is_cancel:
                    if not owner["launched"] or owner["packet"] is not None or slot in received:
                        free.add(slot)
                    else:
                        owner["deferred"] = True
                if slot in received:
                    assert owner["packet"] is None
                    owner["packet"] = {key: inp["io_uncache_resp_bits_" + key] for key in ("data", "error", "nderr")}
                    if owner["deferred"]:
                        free.add(slot)
                    del jobs[slot]
                    counters["response_deliveries"] += 1
            assert set(change["free"]) == free
            counters["consumptions"] += len(consumed)
            counters["cancel_releases"] += len(free - consumed)
            allocations = []
            for lane, load in accepts:
                slot = free_fifo.popleft()
                serial += 1
                allocations.append({"uid": serial, "load": load, "lane": lane, "slot": slot})
            assert allocations == change["allocated"]
            counters["allocations"] += len(allocations)
            for slot in free:
                del owned[slot]
            for tx in allocations:
                assert tx["slot"] not in owned
                owned[tx["slot"]] = {"uid": tx["uid"], "slot": tx["slot"], "q": tx["load"]["entry"], "packet": None, "woke": False, "launched": False, "deferred": False}
            offered = len(free_fifo)
            free_fifo.extend(selected)
            selected = []
            for bank in wait:
                if bank:
                    item = min(bank)
                    bank.remove(item)
                    selected.append(item)
            for slot in free:
                wait[slot % 4].add(slot)
            partitions = [set(owned), set(free_fifo), set(selected), *wait]
            assert sum(map(len, partitions)) == 16 and set().union(*partitions) == set(range(16))
            # The post-edge bus exposes the elastic buffer. New payloads are
            # justified by original owner identity, not by model arbiter state.
            if pre["io_uncache_req_valid"] and not inp["io_uncache_req_ready"]:
                assert post["io_uncache_req_valid"]
                assert all(pre[key] == post[key] for key in pre if key.startswith("io_uncache_req_bits_") and not key.endswith("_data"))
            else:
                held = None
                if post["io_uncache_req_valid"]:
                    held = post["io_uncache_req_bits_id"]
                    owner = owned[held]
                    assert not owner["launched"]
                    owner["launched"] = True
                    assert change["internal_accept"] == owner["uid"]
                    counters["internal_captures"] += 1
                    actual_ids.add(held)
            if post["io_uncache_req_valid"]:
                owner = owned[held]
                assert {key: post["io_uncache_req_bits_" + key] for key in bus_fields(owner["q"], held)} == bus_fields(owner["q"], held)
            previous_match = matches
            saved = [(lane, decode(inp, lane)) for lane in range(3) if inp[f"io_req_{lane}_valid"]]
            saved.sort(key=cmp_to_key(lambda a, b: 0 if a[1]["entry"]["rob"] == b[1]["entry"]["rob"] else 1 if younger(a[1]["entry"]["rob"], b[1]["entry"]["rob"]) else -1))
            red_hist = [red, red_hist[0]]
        counters["owners_at_end"] = len(owned)
        counters["external_jobs_at_end"] = len(jobs)
        has_error = any("error" in row for row in records)
        if not has_error:
            assert not owned and not jobs and held is None
        assert counters["allocations"] == counters["consumptions"] + counters["cancel_releases"] + counters["reset_owners"] + len(owned)
        rows.append({"journal": str(path.relative_to(run)), "sha256": sha(path), "has_error": has_error, **dict(counters)})
    assert len(error_rows) == 8 and actual_ids == set(range(16))
    assert Counter(row["issue"] for row in error_rows) == Counter({"LQU-SID-001": 7, "LQU-MMIO-IF-001": 1})
    assert entry_type_lane == {(slot, nc, lane) for slot in range(16) for nc in (False, True) for lane in range(3)}
    auditors = {}
    for tool in (Path(__file__), ROOT / "tools/audit_lqu_static.py", ROOT / "tools/coverage_audit.py"):
        dest = run / "evidence-auditors" / tool.name
        dest.parent.mkdir(exist_ok=True)
        if dest.exists():
            assert sha(dest) == sha(tool), "do not overwrite historical auditor"
        else:
            shutil.copy2(tool, dest)
        auditors[str(dest.relative_to(run))] = sha(dest)
    report = {"run": name, "status": "evidence_audited_with_failures", "dut_acceptance": "NOT_PASS", "issues": ["LQU-SID-001", "LQU-MMIO-IF-001"],
              "tests": manifest["tests"], "manifest_sha256": sha(manifest_path), "line_audit_sha256": sha(line_path),
              "source_snapshot_files": len(snapshot["files"]), "reached": sum(bool(v) for v in reached.values()), "checked": sum(bool(v) for v in checked.values()),
              "unpassed_scenarios": [key for key, count in checked.items() if not count], "auditors": auditors,
              "scope": "stored full pre/post comparisons; independently recomputed input/FIFO allocation, bus identity/hold, SID obligations and first response retention, wakeup priority, bypass/exception and conservation; arbitration order relies on separately checked full reference, not claimed second dynamic RTL execution",
              "raw_body": [1120, 1126], "raw_closure": [3169, 3175], "proven_guarded_defaults": 6,
              "entry_type_bypass_lane_tuples": len(entry_type_lane), "totals": {key: sum(row[key] for row in rows) for key in counters},
              "failures": error_rows, "cases": rows}
    output = run / "trace-audit.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key not in ("cases", "failures")}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
