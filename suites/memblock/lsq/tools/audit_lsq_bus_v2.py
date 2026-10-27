#!/usr/bin/env python3
"""Independent raw mixed-bus/128-flow audit plus all twelve Store perf paths.

No child reference or change-log imports. Old30 histories must match the
already independently audited baseline bitwise. New scope is deliberately
restricted to the 18 mixed-bus cases and one 128-flow case, no recovery/random.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_sq_initial import ROOT, sha, verify_common


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def sq(ptr):
    return 128 * int(ptr["first"]) + 64 * int(ptr["second"]) + ptr["value"]


def pointer(pins, prefix):
    return 128 * pins[prefix + "first_flag"] + 64 * pins[prefix + "second_flag"] + pins[prefix + "value"]


def rob(ptr):
    return 2 * (160 * int(ptr["flag"]) + ptr["value"]) + int(not ptr["former"])


def rob_matches(pins, prefix, expected):
    assert all(pins[prefix + port] == int(expected[field]) for port, field in (("flag", "flag"), ("value", "value"), ("isFormer", "former")))


def record_checks(trace, path):
    last, by_tick = None, {}
    for row in trace:
        tick = row["post_tick"]
        assert row["pre_tick"] + 1 == tick and (last is None or last + 2 == tick)
        assert len(row["pins"]) == 603 and row["pins"] == row["post_pins"] and len(row["before"]) == len(row["after"]) == 458
        assert row["checked"] and not row["explicitly_unimplemented_outputs"]
        for phase in ("before", "after"):
            assert all(not ((row[phase][key] ^ value) & row["masks_" + phase].get(key, -1)) for key, value in row["expected_" + phase].items())
        assert not row["input"]["redirect"]["valid"]
        by_tick[tick], last = row, tick
    for check in rows(path.with_name("lsq_checks.jsonl")):
        actual = by_tick[check["tick"]][check["phase"]]
        assert check["passed"] and check["actual"] == {key: actual[key] for key in check["expected"]}
        assert all(not ((actual[key] ^ want) & check["masks"].get(key, -1)) for key, want in check["expected"].items())


def store_perf(trace):
    """Rebuild ready prefixes from STA/STD, releases and raw dispatch only.

    Event0 independently cross-checks retained registered OR-busy on cases with
    NC-only Loads (Load MMIO busy is zero). MMIO Load-only cases have no Store
    events. This is not claimed as a second full Deq busy-state implementation.
    """
    assert not any(row["input"]["redirect"]["valid"] for row in trace)
    has_mmio_load = any(load["execution"]["valid"] and load["mmio"] for row in trace for load in row["input"]["loads"])
    has_store_bus = any(row["before"]["io_uncache_req_valid"] and row["before"]["io_uncache_req_bits_cmd"] == 1 for row in trace)
    assert not (has_mmio_load and has_store_bus), "event0 source disambiguation outside audited scope"
    address_flags, data_flags = [False] * 64, [False] * 64
    ap = dp = tail = 0
    events, counts, witnesses = [], Counter(), {lane: {} for lane in range(12)}
    boundaries, spans = set(), []
    for index, row in enumerate(trace):
        inp, pre, post = row["input"], row["before"], row["after"]
        head = pointer(pre, "io_sqDeqPtr_")
        if inp["reset"]:
            assert not any(d["valid"] for d in inp["dispatch"])
            ap = dp = tail = head = 0
            address_flags, data_flags = [False] * 64, [False] * 64
        assert pointer(pre, "io_issuePtrExt_") == ap
        later = dp if 0 < (dp - ap) % 256 < 128 else ap
        physical, virtual = (later - head) % 256, (tail - head) % 256
        # All WB cases in this audited scope are the single original IO Store.
        io_write = has_store_bus and pre["io_mmioStout_valid"]
        event = [post["io_rob_mmioBusy"] if not has_mmio_load else 0,
                 int(bool(pre["io_uncache_req_valid"] and inp["bus"]["ready"] and pre["io_uncache_req_bits_cmd"] == 1 and not pre["io_uncache_req_bits_nc"])),
                 int(bool(io_write and inp["writeback_ready"])), int(bool(io_write and not inp["writeback_ready"])),
                 int(physical < 16), int(16 < physical <= 32), int(32 < physical <= 48), int(physical > 48),
                 int(virtual < 32), int(32 < virtual <= 64), int(64 < virtual <= 96), int(virtual > 96)]
        events.append(event)
        spans.append(dict(tick=row["post_tick"], head=head, address=ap, data=dp, physical=physical, virtual=virtual))
        boundaries.add((physical, virtual))
        for phase, latency in (("before", 6), ("after", 5)):
            if index < latency:
                continue
            for lane, value in enumerate(events[index - latency]):
                pin = f"io_perf_{27 + lane}_value"
                assert row[phase][pin] == value, (row["nodeid"], row["post_tick"], phase, pin, row[phase][pin], value, spans[index - latency])
                counts["independent_store_perf_pin_comparisons"] += 1
                witnesses[lane].setdefault(str(value), dict(tick=row["post_tick"], phase=phase, event_tick=trace[index - latency]["post_tick"]))
        upper = (head + 64) % 256
        def advance_ready(position, flags):
            for _ in range(4):
                if position == upper or not flags[position % 64]:
                    break
                position = (position + 1) % 256
            return position
        next_ap, next_dp = advance_ready(ap, address_flags), advance_ready(dp, data_flags)
        next_head = pointer(post, "io_sqDeqPtr_")
        movement = (next_head - head) % 256
        assert movement <= 2
        for pos in range(head, head + movement):
            address_flags[pos % 64] = data_flags[pos % 64] = False
        for a in inp["addresses"]:
            if a["valid"]:
                assert a["last"] and not a["cross_word"] and not a["tlb_miss"]
                address_flags[a["slot"]] = True
        for d in inp["data"]:
            if d["valid"]:
                data_flags[d["sq"]["value"]] = True
        for d in inp["dispatch"]:
            if d["valid"] and d["need_alloc"] & 2:
                tail = (tail + d["flows"]) % 256
                assert sq(d["store_end"]) == tail
        ap, dp = (0, 0) if inp["reset"] else (next_ap, next_dp)
        assert pointer(post, "io_issuePtrExt_") == ap
    return counts, witnesses, boundaries


def audit_mixed(trace):
    dispatch, original, address, data, attr, s2 = [], None, None, None, None, None
    requests, acks, responses, replay, bypass = {}, {}, {}, None, None
    s3 = wb = checked_data = 0
    completed, serial_owner, counts = set(), None, Counter()
    load_visible, selected_before = False, None
    for row in trace:
        inp, pins, pre, post, tick = row["input"], row["pins"], row["before"], row["after"], row["post_tick"]
        if inp["reset"]:
            assert not dispatch
            continue
        for d in inp["dispatch"]:
            if d["valid"]:
                assert len(dispatch) < 2 and d["flows"] == 1 and d["need_alloc"] in (1, 2)
                dispatch.append(d)
        for lane, a in enumerate(inp["addresses"]):
            if a["valid"]:
                assert address is None and a["slot"] == 0
                address, s2 = a, (tick + 2, lane)
        if s2 is not None and s2[0] == tick:
            attr = inp["attributes"][s2[1]]
        for d in inp["data"]:
            if d["valid"]:
                assert data is None and sq(d["sq"]) == 0
                data = d
        for load in inp["loads"]:
            q = load["execution"]
            if not q["valid"]:
                continue
            if original is None:
                assert q["causes"] == 1 and q["need_replay"] and not q["replay_feedback"]
                original = load
            else:
                assert checked_data == 1 and replay is not None and not s3
                assert q["replay_feedback"] and q["slot"] == replay["slot"] and not q["need_replay"]
                assert q["uop"] == original["execution"]["uop"]
                s3 = tick
        if serial_owner is not None:
            assert not pre["io_uncache_req_valid"], "unrelated ack/response cannot release a serial owner's request exclusion"
            counts["independent_serial_exclusion_edges"] += 1
        if pre["io_uncache_req_valid"]:
            selected = "load" if pre["io_uncache_req_bits_cmd"] == 0 else "store"
            if selected == "load" and not requests and address is None:
                load_visible = True
            if selected_before == "load" and selected == "store" and not requests:
                assert load_visible and address is not None
                counts["actual_older_store_overtakes_unaccepted_load"] += 1
            selected_before = selected
        if pre["io_uncache_req_valid"] and inp["bus"]["ready"]:
            kind = "load" if pre["io_uncache_req_bits_cmd"] == 0 else "store"
            assert kind not in requests and serial_owner is None
            d = next(d for d in dispatch if d["need_alloc"] == (1 if kind == "load" else 2))
            rob_matches(pre, "io_uncache_req_bits_robIdx_", d["rob"])
            if kind == "load":
                assert original is not None and pre["io_uncache_req_bits_addr"] == original["paddr"]
                assert pre["io_uncache_req_bits_vaddr"] == original["execution"]["vaddr"] and pre["io_uncache_req_bits_nc"]
            else:
                assert address is not None and data is not None and attr is not None
                assert address["rob"] == d["rob"] and pre["io_uncache_req_bits_addr"] == address["paddr"]
                assert pre["io_uncache_req_bits_vaddr"] == address["vaddr"] and pre["io_uncache_req_bits_data"] == data["data"]
                assert pre["io_uncache_req_bits_nc"] == int(attr["nc"])
            assert pre["io_uncache_req_bits_mask"] == 255
            requests[kind] = dict(tick=tick, mid=pre["io_uncache_req_bits_id"], nc=bool(pre["io_uncache_req_bits_nc"]))
            counts["actual_original_mixed_" + kind + "_requests"] += 1
            if not (inp["bus"]["outstanding"] and requests[kind]["nc"]):
                serial_owner = kind
            if len(requests) == 2 and not responses:
                counts["both_directions_outstanding_before_any_response"] += 1
        bus = inp["bus"]
        if bus["ack"]:
            kind = "load" if bus["ack_to_load"] else "store"
            assert kind in requests and kind not in acks and bus["mid"] == requests[kind]["mid"]
            assert pins["io_uncache_idResp_bits_is2lq"] == int(kind == "load")
            assert not any(a["sid"] == bus["sid"] for k, a in acks.items() if k not in responses)
            acks[kind] = dict(tick=tick, sid=bus["sid"])
            counts["independent_mixed_direction_acks"] += 1
        if bus["response"]:
            kind = "load" if bus["response_to_load"] else "store"
            assert kind in acks and kind not in responses and acks[kind]["sid"] == bus["response_id"]
            assert pins["io_uncache_resp_bits_is2lq"] == int(kind == "load")
            responses[kind] = dict(tick=tick, data=bus["data"], error=int(bus["error"]), nderr=int(bus["nderr"]))
            if serial_owner == kind:
                serial_owner = None
            counts["independent_mixed_direction_responses"] += 1
        if bus["ack"] and bus["response"] and bus["ack_to_load"] != bus["response_to_load"]:
            counts["opposite_ack_load_resp_store" if bus["ack_to_load"] else "opposite_ack_store_resp_load"] += 1
        for bank in range(3):
            p = f"io_replay_{bank}_"
            if pre[p + "valid"] and inp["replay_ready"][bank]:
                assert "load" in responses and replay is None
                rob_matches(pre, p + "bits_uop_robIdx_", original["execution"]["uop"]["rob"])
                assert pre[p + "bits_vaddr"] == original["execution"]["vaddr"]
                replay = dict(tick=tick, slot=pre[p + "bits_replayQueueIdx"])
                assert replay["slot"] % 3 == bank
        for lane, query in enumerate(inp["bypass"]):
            if query["valid"]:
                assert replay is not None and bypass is None and query["lq"] == original["execution"]["uop"]["lq"]
                p = f"io_bypass_{lane}_s1Resp_"
                assert post[p + "valid"] and post[p + "bits_paddr"] == original["paddr"]
                assert post["io_ldExceptionInfo_valid"] and post["io_ldExceptionInfo_bits_vaddr"] == original["fullva"]
                rob_matches(post, "io_ldExceptionInfo_bits_robIdx_", original["execution"]["uop"]["rob"])
                assert post["io_ldExceptionInfo_bits_exceptionVec_19"] == responses["load"]["error"]
                assert post["io_ldExceptionInfo_bits_exceptionVec_5"] == responses["load"]["nderr"]
                bypass = dict(tick=tick, lane=lane)
        if bypass is not None and tick == bypass["tick"] + 2:
            p = f"io_bypass_{bypass['lane']}_s2Resp_"
            assert post[p + "valid"] and post[p + "bits_data"] == responses["load"]["data"] * ((1 << 64) + 1)
            assert post[p + "bits_derr"] == responses["load"]["error"] and post[p + "bits_nderr"] == responses["load"]["nderr"]
            checked_data += 1
            counts["independent_mixed_original_load_bytes_and_errors"] += 1
        if pre["io_mmioStout_valid"] and inp["writeback_ready"]:
            assert "store" in responses and not requests["store"]["nc"] and not wb
            rob_matches(pre, "io_mmioStout_bits_robIdx_", address["rob"])
            wb = tick
        for kind, short in (("load", "lq"), ("store", "sq")):
            p = "io_toLsqEnqCtrl_" + short + "Deq_"
            if post[p + "valid"]:
                assert post[p + "bits"] == 1 and kind not in completed
                assert (s3 and checked_data == 1) if kind == "load" else ("store" in acks if requests["store"]["nc"] else bool(wb))
                completed.add(kind)
                counts["actual_mixed_" + kind + "_owner_completed"] += 1
                if kind == "store" and kind not in responses:
                    assert requests["store"]["nc"]
                    counts["actual_nc_sq_release_while_external_response_still_owed"] += 1
        assert not any(pre[f"io_sbuffer_req_{lane}_valid"] and inp["sbuffer_ready"][lane] for lane in range(2))
    assert completed == set(requests) == set(acks) == set(responses) == {"load", "store"} and checked_data == 1 and serial_owner is None
    ld, st = (next(d for d in dispatch if d["need_alloc"] == n) for n in (1, 2))
    boundary = ("test_unit_interface_" in trace[0]["nodeid"])
    if not boundary:
        assert 0 < (rob(ld["rob"]) - rob(st["rob"])) % 640 < 320
        # The common ROB head never jumps over an unfinished Load. Store head
        # may stay conservative after its physical release, then move at end.
        allocated_at = next(row["post_tick"] for row in trace if any(d["valid"] for d in row["input"]["dispatch"]))
        for row in trace:
            if row["input"]["reset"] or row["post_tick"] < allocated_at:
                continue
            if not s3 or row["post_tick"] <= s3:
                assert row["input"]["pending"] == st["rob"]
    counts["unit_interface_cases" if boundary else "normal_producer_mixed_bus_cases"] += 1
    return counts, dict(domain="UNIT-INTERFACE" if boundary else "NORMAL-PRODUCER", requests=requests, acks=acks, responses=responses)


def audit_vector(trace):
    owners, consumed, released, pending_attrs = {}, [], [], {}
    tail = head = 0
    counts = Counter()
    for row in trace:
        inp, pre, post, tick = row["input"], row["before"], row["after"], row["post_tick"]
        if inp["reset"]:
            assert not owners
            continue
        assert pointer(pre, "io_sqDeqPtr_") == head % 256
        for d in inp["dispatch"]:
            if d["valid"]:
                assert d["need_alloc"] == 2 and d["flows"] == 16
                for position in range(tail, tail + 16):
                    assert position not in owners
                    owners[position] = dict(rob=d["rob"])
                tail += 16
                assert sq(d["store_end"]) == tail % 256
                counts["vector_virtual_uops"] += 1
        for lane, a in enumerate(inp["addresses"]):
            if a["valid"]:
                position = head + (a["slot"] - head) % 64
                assert head <= position < min(tail, head + 64) and "address" not in owners[position]
                assert owners[position]["rob"] == a["rob"] and a["last"] and a["size"] == 3 and not a["cross_word"]
                owners[position]["address"] = a
                pending_attrs[(tick + 2, lane)] = position
        for lane in range(2):
            if (tick, lane) in pending_attrs:
                attr = inp["attributes"][lane]
                assert attr["memory"] and not attr["nc"] and not attr["mmio"] and not attr["exception"]
        for d in inp["data"]:
            if d["valid"]:
                position = sq(d["sq"])
                assert head <= position < min(tail, head + 64) and "data" not in owners[position]
                owners[position]["data"] = d["data"]
        for lane in range(2):
            p = f"io_sbuffer_req_{lane}_"
            if pre[p + "valid"] and inp["sbuffer_ready"][lane]:
                position = len(consumed)
                owner = owners[position]
                address = owner["address"]
                assert pre[p + "bits_addr"] == address["paddr"] and pre[p + "bits_vaddr"] == address["vaddr"]
                assert pre[p + "bits_mask"] == 255 and pre[p + "bits_data"] % (1 << 64) == owner["data"] and not pre[p + "bits_wline"]
                owner["fire_tick"] = tick
                consumed.append(position)
        delta = (pointer(post, "io_sqDeqPtr_") - head) % 256
        assert delta <= 2 and post["io_toLsqEnqCtrl_sqDeq_valid"] == int(bool(delta))
        if delta:
            assert post["io_toLsqEnqCtrl_sqDeq_bits"] == delta
        for position in range(head, head + delta):
            assert position in consumed and owners[position]["fire_tick"] + 2 == tick
            released.append(position)
        head += delta
    assert consumed == released == list(range(128)) and len(owners) == 128
    counts["actual_vector_original_bytes_consumed"] += len(consumed)
    counts["actual_vector_original_flows_released"] += len(released)
    counts["same_physical_slot_next_sq_generation_completed"] += 64
    return counts


def audit(name):
    run, baseline = ROOT / "results" / name, ROOT / "results/lsq-expanded-02"
    manifest, source, nodes = verify_common(run)
    _, _, base_nodes = verify_common(baseline)
    assert manifest["tests"] == {"PASS": 49} and not any(nodes.values())
    old_audit = baseline / "bus-history-audit-v1.json"
    old_report = json.loads(old_audit.read_text())
    assert old_report["tests"] == {"PASS": 30}
    assert sha(baseline / "evidence-auditors/audit_lsq_bus_v1.py") == old_report["auditor_sha256"]
    original = {p["nodeid"]: baseline / p["journal"] for p in old_report["cases"]}
    assert set(original) == set(base_nodes)
    counts, seen, cases = Counter(), set(), []
    perf_witnesses = {lane: {} for lane in range(12)}
    boundaries = set()
    for path in sorted((run / "cases").rglob("lsq_wrapper.jsonl")):
        trace = rows(path)
        node = trace[0]["nodeid"]
        assert node in nodes and node not in seen and all(row["nodeid"] == node for row in trace)
        seen.add(node)
        record_checks(trace, path)
        counts["continuous_full_pin_records"] += len(trace)
        pc, witness, pairs = store_perf(trace)
        counts.update(pc)
        boundaries.update(pairs)
        for lane, values in witness.items():
            for value, event in values.items():
                perf_witnesses[lane].setdefault(value, dict(nodeid=node, **event))
        detail = {}
        if node in original:
            before = rows(original[node])
            assert len(trace) == len(before)
            assert all(all(a[key] == b[key] for key in ("pre_tick", "post_tick", "input", "pins", "post_pins", "before", "after")) for a, b in zip(trace, before, strict=True))
            counts["previous_30_cases_all_inputs_pre_post_ticks_bitwise_rechecked"] += 1
        elif node.startswith("tests/lsq_wrapper/test_mixed_bus.py::"):
            checked, detail = audit_mixed(trace)
            counts.update(checked)
        else:
            assert node.startswith("tests/lsq_wrapper/test_store_span.py::")
            counts.update(audit_vector(trace))
        assert trace[-1]["after"]["io_lqEmpty"] and trace[-1]["after"]["io_sqEmpty"]
        assert not trace[-1]["after"]["io_replayAllocate"] and not trace[-1]["after"]["io_uncache_req_valid"]
        cases.append(dict(nodeid=node, journal=str(path.relative_to(run)), sha256=sha(path), **detail))
    assert seen == set(nodes) and counts["previous_30_cases_all_inputs_pre_post_ticks_bitwise_rechecked"] == 30
    assert counts["unit_interface_cases"] == 4 and counts["normal_producer_mixed_bus_cases"] == 14
    assert counts["actual_vector_original_flows_released"] == 128
    assert all(set(values) == {"0", "1"} for values in perf_witnesses.values()), perf_witnesses
    assert {(p, 128) for p in (15, 16, 17, 32, 33, 48, 49, 64)} <= boundaries
    dest = run / "evidence-auditors" / Path(__file__).name
    dest.parent.mkdir(exist_ok=True)
    if dest.exists():
        assert sha(dest) == sha(Path(__file__))
    else:
        shutil.copy2(Path(__file__), dest)
    report = dict(run=name, status="audited_mixed_bus_and_vector_spans_not_complete_wrapper", tests=manifest["tests"],
                  counts=dict(counts), snapshot_files=len(source), previous_30_audit_sha256=sha(old_audit), auditor_sha256=sha(dest),
                  manifest_sha256=sha(run / "execution/manifest.json"), store_perf_0_and_1_witnesses=perf_witnesses, cases=cases,
                  limits="Old30 raw histories match audited baseline bitwise. New14 normal and4 UNIT-INTERFACE mixed-bus cases separated; original Load bytes/errors, Store ack/WB/deq and late NC external obligations audited. All12 Store perf compared from raw prefix/dispatch/fire/WB histories at six-edge latency, event0 uses registered OR-busy cross-interface consistency only where Load MMIO busy is absent. No recovery, activity-reset, SID reuse, complete Forward/RAW/RAR, random, full LSQ acceptance or architecture claim.")
    output = run / "bus-history-audit-v2.json"
    if output.exists():
        assert json.loads(output.read_text()) == json.loads(json.dumps(report))
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ("cases", "store_perf_0_and_1_witnesses")}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
