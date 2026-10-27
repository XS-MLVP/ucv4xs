#!/usr/bin/env python3
"""Independent194-case gate: old178 unchanged,1024 Store wraps, Replay gaps.

Only raw public histories drive the additional identity/permission/byte audit.
No DUT/reference/actor imports and no known-issues/outcome/change answers.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_lsq_bus_v2 import pointer, rob, sq
from audit_lsq_memory_v1 import lq, words
from audit_lsq_population_v1 import RAW, events, inspect_replay, paths_by_node, same_raw, validate_row
from audit_sq_initial import ROOT, sha, verify_common


def inspect_store_wrap(path):
    stores, loads, pending_s2, previous = [], [], [], None
    sq_head = lhead = 0
    last_rob, rob_order, head_code, head_order = None, None, 0, 0
    witnesses, sq_codes, rob_flags = set(), set(), set()
    peak, counts = 0, Counter()
    for row in events(path):
        validate_row(row, previous, False)
        inp, pre, post, tick = row["input"], row["before"], row["after"], row["post_tick"]
        assert not inp["redirect"]["valid"] and not pre["io_uncache_req_valid"] and not pre["io_cmoOpReq_valid"] and not pre["io_mmioStout_valid"]
        if inp["reset"]:
            assert not stores and not loads
            previous = row
            continue
        code = rob(inp["pending"])
        delta = (code - head_code) % 640
        assert delta < 320
        head_order += delta
        head_code = code
        for lane, d in enumerate(inp["dispatch"]):
            if not d["valid"]:
                continue
            assert d["flows"] == 1 and d["need_alloc"] in (1, 2)
            code = rob(d["rob"])
            if last_rob is None:
                rob_order = code
            else:
                delta = (code - last_rob) % 640
                assert 0 < delta < 320
                rob_order += delta
            last_rob = code
            if d["need_alloc"] == 2:
                pos = len(stores)
                assert sq(d["store_end"]) == (pos + 1) % 256
                stores.append(dict(position=pos, rob=d["rob"], order=rob_order, lane=lane,
                                   consumed=set(), complete=False, dispatched_tick=tick))
                witnesses.add((pos % 128, lane))
                rob_flags.add((int(d["rob"]["flag"]), int(d["rob"]["former"])))
            else:
                assert lq(d["load_start"]) == len(loads)
                loads.append(dict(rob=d["rob"], order=rob_order, complete=False, sent=False))
        assert 0 <= len(stores) - sq_head <= 128
        peak = max(peak, len(stores) - sq_head)
        for pos, lane in pending_s2:
            attr = inp["attributes"][lane]
            assert attr["memory"] and attr["last"] and not attr["nc"] and not attr["mmio"] and not attr["exception"]
            stores[pos]["s2_done"] = True
        pending_s2 = []
        for lane, address in enumerate(inp["addresses"]):
            if not address["valid"]:
                continue
            pos = sq_head + (address["slot"] - sq_head) % 64
            store = stores[pos]
            assert pos < min(sq_head + 64, len(stores)) and store["rob"] == address["rob"] and "address" not in store
            assert address["last"] and not address["tlb_miss"] and not address["cross_word"] and not address["fu_op"] & 1
            store["address"] = address
            pending_s2.append((pos, lane))
        for data in inp["data"]:
            if data["valid"]:
                pos = sq_head + (sq(data["sq"]) - sq_head) % 256
                assert pos < min(sq_head + 64, len(stores)) and "data" not in stores[pos]
                stores[pos]["data"] = data["data"]
                sq_codes.add(sq(data["sq"]))
        for store in stores:
            if store["order"] < head_order:
                assert "data" in store and store.get("s2_done"), "ROB crossed an unexecuted original Store"
        for packet in inp["loads"]:
            q = packet["execution"]
            if q["valid"]:
                load = loads[lq(q["uop"]["lq"])]
                assert load["rob"] == q["uop"]["rob"] and not load["sent"] and not q["need_replay"] and packet["update_address"]
                assert sq(q["uop"]["sq"]) == len(stores) % 256
                load["sent"] = True
        for lane in range(2):
            p = f"io_sbuffer_req_{lane}_"
            if not (pre[p + "valid"] and inp["sbuffer_ready"][lane]):
                continue
            store = next(s for s in stores if not s["consumed"])
            # NewStoreQueue.scala:1989-2005 permits an all-ready ordinary
            # Store at ROB HEAD via real preCommit as well as a retired one.
            # An actual effect is not itself proof that ROB already retired.
            assert store["order"] <= head_order and store.get("s2_done") and not store["complete"], (store["position"], store["order"], head_order, inp["pending"], tick)
            if store["order"] == head_order:
                counts["actual_ready_ordinary_rob_head_precommit_fires_not_retirement"] += 1
            va, pa, mask, value = words(store)[0]
            assert pre[p + "bits_vaddr"] == va and pre[p + "bits_addr"] == pa and pre[p + "bits_mask"] == mask and not pre[p + "bits_wline"]
            bits = sum(255 << (8 * byte) for byte in range(16) if mask >> byte & 1)
            assert not ((pre[p + "bits_data"] ^ value) & bits)
            store.update(consumed={0}, last_fire=tick)
            counts["actual_original_store_byte_fragments"] += 1
        delta = (pointer(post, "io_sqDeqPtr_") - sq_head) % 256
        assert delta <= 2 and post["io_toLsqEnqCtrl_sqDeq_valid"] == int(bool(delta))
        if delta:
            assert post["io_toLsqEnqCtrl_sqDeq_bits"] == delta
        for pos in range(sq_head, sq_head + delta):
            store = stores[pos]
            assert store["consumed"] == {0} and store["last_fire"] + 2 == tick and not store["complete"]
            store["complete"] = True
        sq_head += delta
        if post["io_toLsqEnqCtrl_lqDeq_valid"]:
            assert post["io_toLsqEnqCtrl_lqDeq_bits"] == 1 and loads[lhead]["sent"] and not loads[lhead]["complete"]
            loads[lhead]["complete"] = True
            lhead += 1
        counts["raw_records"] += 1
        previous = row
    assert len(stores) == sq_head == counts["actual_original_store_byte_fragments"] == 1024
    assert len(loads) == lhead == 8 and peak == 128
    assert witnesses == {(slot, lane) for slot in range(128) for lane in range(8)}
    assert sq_codes == set(range(256)) and rob_flags == {(flag, former) for flag in (0, 1) for former in (0, 1)}
    assert previous["after"]["io_sqEmpty"] and previous["after"]["io_lqEmpty"]
    return dict(allocated=1032, completed=1032, failure_retained=0, actual_store_uop_peak=peak,
                logical_virtual_slot_by_dispatch_lane_witnesses=len(witnesses), actual_data_full_sq_encodings=len(sq_codes),
                actual_rob_flag_former_combinations=len(rob_flags), counts=dict(counts))


def inspect_strict_full_failure(path):
    loads, packets, stores = [], {}, []
    previous, ready_seven, violations = None, False, []
    records = 0
    for row in events(path):
        validate_row(row, previous, False)
        inp, pre, post, tick = row["input"], row["before"], row["after"], row["post_tick"]
        assert not inp["redirect"]["valid"] and not any(w["valid"] for w in inp["address_wakeups"])
        if inp["reset"]:
            assert not loads and not stores
            previous = row
            continue
        for d in inp["dispatch"]:
            if d["valid"]:
                if d["need_alloc"] == 2:
                    assert d["flows"] == 8 and not stores and sq(d["store_end"]) == 8
                    stores.extend(dict(rob=d["rob"], position=pos) for pos in range(8))
                else:
                    assert d["need_alloc"] == 1 and d["flows"] == 1 and lq(d["load_start"]) == len(loads)
                    loads.append(dict(rob=d["rob"], position=len(loads)))
        for packet in inp["loads"]:
            q = packet["execution"]
            if q["valid"]:
                key = lq(q["uop"]["lq"])
                assert key not in packets and q["uop"]["rob"] == loads[key]["rob"]
                assert q["need_replay"] and q["causes"] == 4 and q["uop"]["strict"] and sq(q["address_sq"]) == 7 and sq(q["uop"]["sq"]) == 8
                packets[key] = packet
        for address in inp["addresses"]:
            if address["valid"]:
                assert address["slot"] == 7 and address["rob"] == stores[7]["rob"] and not address["tlb_miss"] and address["last"]
                ready_seven = True
        assert pointer(pre, "io_issuePtrExt_") == pointer(post, "io_issuePtrExt_") == 0
        assert not pre["io_uncache_req_valid"] and not post["io_toLsqEnqCtrl_lqDeq_valid"] and not post["io_toLsqEnqCtrl_sqDeq_valid"]
        for bank in range(3):
            p = f"io_replay_{bank}_"
            assert not (pre[p + "valid"] and inp["replay_ready"][bank])
            if post[p + "valid"]:
                assert ready_seven and len(packets) == len(loads) == 120
                key = 120 * post[p + "bits_uop_lqIdx_flag"] + post[p + "bits_uop_lqIdx_value"]
                assert key in packets and post[p + "bits_uop_loadWaitStrict"] == 1
                violations.append(dict(issue="LRQ-STRICT-001", tick=tick, bank=bank, actual_replay_valid=1,
                                       expected_valid=0, actual_sq_ready_pointer=0, real_ready_slot=7, original_load_lq=key))
        previous = row
        records += 1
    assert len(violations) == 1 and violations[0]["tick"] == previous["post_tick"] and not previous["checked"]
    assert "io_replay_0_valid" in previous["error"] and len(stores) == 8
    return dict(allocated=128, completed=0, failure_retained=128, violations=violations, counts={"raw_records": records})


def audit_head_helper(run, paths, nodes):
    original = ROOT / "results/lsq-replay-gaps-01"
    manifest, _, old_nodes = verify_common(original)
    assert manifest["tests"] == {"PASS": 12, "FAIL": 3}
    old_paths, cases = paths_by_node(original), []
    for node in old_nodes:
        if "test_actual_vlq_head_wins_" not in node:
            assert old_nodes[node] == nodes[node]
            same_raw(old_paths[node], paths[node])
            continue
        assert old_nodes[node] and not nodes[node]
        before = list(events(old_paths[node]))
        after = list(events(paths[node]))
        assert all(a["checked"] for a in before) and len(after) > len(before)
        assert all(all(a[key] == b[key] for key in RAW) for a, b in zip(before, after))
        old = before[-1]
        bank = 1 if "[2]" in node else 2
        assert not old["input"]["replay_ready"][bank] and old["after"][f"io_replay_{bank}_bits_replayQueueIdx"] == bank
        actual = after[len(before)]
        assert actual["input"]["replay_ready"][bank] and actual["before"][f"io_replay_{bank}_bits_replayQueueIdx"] == bank
        assert actual["after"][f"io_replay_{bank}_bits_uop_lqIdx_value"] == 0
        cases.append(dict(nodeid=node, old_raw_samples_exact_prefix=len(before), original_model_and_dut_agreed=True,
                          actual_old_selected_request_fire_tick=actual["post_tick"], actual_next_candidate_is_original_vlq_head=True,
                          original_trace_sha256=sha(old_paths[node]), corrected_trace_sha256=sha(paths[node])))
    assert len(cases) == 2
    return cases


def audit(name):
    run, baseline = ROOT / "results" / name, ROOT / "results/lsq-expanded-09"
    manifest, source, nodes = verify_common(run)
    old, _, old_nodes = verify_common(baseline)
    assert manifest["tests"] == {"PASS": 157, "FAIL": 37} and len(nodes) == 194
    assert old["tests"] == {"PASS": 142, "FAIL": 36} and len(old_nodes) == 178
    paths, old_paths = paths_by_node(run), paths_by_node(baseline)
    assert set(paths) == set(nodes) and set(old_paths) == set(old_nodes) <= set(nodes)
    counts, cases = Counter(), []
    for node, path in sorted(paths.items()):
        if node in old_nodes:
            assert nodes[node] == old_nodes[node]
            records = same_raw(path, old_paths[node])
            counts["previous178_all_raw_samples_bitwise_rechecked"] += 1
            detail = dict(raw_samples_bitwise_equal_previous=records)
        else:
            if node.startswith("tests/lsq_wrapper/test_store_population.py::"):
                assert not nodes[node]
                detail = inspect_store_wrap(path)
                counts["new_store_population_cases"] += 1
            else:
                assert node.startswith("tests/lsq_wrapper/test_replay_gaps.py::")
                if nodes[node]:
                    assert "strict-full-pool" in node
                    detail = inspect_strict_full_failure(path)
                else:
                    detail = inspect_replay(path, False)
                if "test_full_population" in node and not nodes[node] or "test_actual_vlq_head_wins_" in node:
                    assert {slot for slot, _ in detail["slots_by_enqueue_lane"]} == set(range(120))
                counts["new_replay_gap_cases"] += 1
            for key in ("allocated", "completed", "failure_retained"):
                counts["new_" + key] += detail[key]
            records = sum(1 for _ in events(path))
            counts.update(detail["counts"])
        counts["all_continuous_raw_records"] += records
        cases.append(dict(nodeid=node, journal=str(path.relative_to(run)), sha256=sha(path), result="FAIL" if nodes[node] else "PASS", **detail))
    assert counts["previous178_all_raw_samples_bitwise_rechecked"] == 178
    assert counts["new_store_population_cases"] == 1 and counts["new_replay_gap_cases"] == 15
    assert counts["new_failure_retained"] == 128
    helpers = audit_head_helper(run, paths, nodes)
    dest = run / "evidence-auditors"
    dest.mkdir(exist_ok=True)
    files = (Path(__file__), ROOT / "tools/audit_lsq_population_v1.py", ROOT / "tools/audit_lsq_memory_v1.py",
             ROOT / "tools/audit_lsq_bus_v2.py", ROOT / "tools/audit_lsq_bus_v3.py")
    for file in files:
        copy_to = dest / file.name
        if copy_to.exists():
            assert sha(copy_to) == sha(file)
        else:
            shutil.copy2(file, copy_to)
    old_audit = baseline / "nuke-population-history-audit-v1.json"
    assert json.loads(old_audit.read_text())["tests"] == old["tests"]
    report = dict(run=name, status="NOT_PASS_194_case_store_wrap_and_replay_gap_histories_audited", tests=manifest["tests"],
                  snapshot_files=len(source), counts=dict(counts), baseline_nuke_population_audit_sha256=sha(old_audit),
                  head_priority_helper_corrections=helpers, auditor_sha256={f.name: sha(dest / f.name) for f in files}, cases=cases,
                  limits="Exact194 scope. Old178 raw samples unchanged, including16 explicit protocol probes/all36 oldFAIL. New1024 ordinary Store uops+8 Load complete under one circular ROB,128 live virtual uops/all8 dispatch sources/all256 SQ encodings/bothROB flag+former, not8 vector snapshots. New15 Replay cases use distinct singlehot reasons, actual SQ/STA/STD/refill/TLB histories and original-slot feedback; full120 strict ready-bitmap case remains ordinary FAIL with128UID retained. Two backpressure head helper errors preserved: consume original held candidate before next head-priority selection; old samples exact prefixes, other13 Replay results/raw unchanged. No shared active reset/full recovery/NC/random or Backend/elaboration acceptance.")
    output = run / "wrap-history-audit-v1.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key not in ("cases", "head_priority_helper_corrections")}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
