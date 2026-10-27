#!/usr/bin/env python3
"""Versioned raw mixed-history audit, correct C_FF=4 mask and all-row count.

The first auditor confused cause index 4 with index 5 (mask32). Keep it and
its explicit rejection record unchanged. No DUT/model imports or waivers.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_sq_initial import ROOT, sha, verify_common


def pointer(value, size):
    if size == 120:
        return int(value["flag"]) * size + value["value"]
    return int(value["first"]) * 128 + int(value["second"]) * 64 + value["value"]


def audit(name):
    run = ROOT / "results" / name
    manifest, source, nodes = verify_common(run)
    assert all(node.startswith("tests/lsq_wrapper/test_initial.py::") for node in nodes) and not any(nodes.values())
    totals, cases, seen, source_lanes, sta_lanes = Counter(), [], set(), set(), set()
    for path in sorted((run / "cases").rglob("lsq_wrapper.jsonl")):
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        node, last, owners, store, load, issued = rows[0]["nodeid"], None, {}, None, None, {}
        assert node in nodes and node not in seen
        seen.add(node)
        sta_tick = std_tick = s3_tick = previous_sta = None
        sb_ticks, ld_ticks, sq_ticks, at_tick = [], [], [], {}
        for row in rows:
            inp, pins, pre, post, tick = row["input"], row["pins"], row["before"], row["after"], row["post_tick"]
            assert row["nodeid"] == node and row["pre_tick"] + 1 == tick and (last is None or last + 2 == tick)
            assert pins == row["post_pins"] and len(pins) == 603 and len(pre) == len(post) == 458 and row["checked"]
            assert not inp["redirect"]["valid"] and not any(inp["bus"][key] for key in ("ready", "ack", "response"))
            assert not any(q["valid"] for q in (*inp["raw_queries"], *inp["rar_queries"], *inp["queries"]))
            assert tuple(row["explicitly_unimplemented_outputs"]) == tuple(f"io_perf_{lane}_value" for lane in range(27, 39))
            for phase in ("before", "after"):
                assert all(not ((row[phase][pin] ^ value) & row["masks_" + phase].get(pin, -1))
                           for pin, value in row["expected_" + phase].items())
            last, at_tick[tick] = tick, row
            totals["continuous_records"] += 1
            if inp["reset"]:
                assert not owners
                continue
            for lane, request in enumerate(inp["dispatch"]):
                if request["valid"]:
                    assert request["flows"] == 1 and request["need_alloc"] in (1, 2)
                    kind = "load" if request["need_alloc"] == 1 else "store"
                    assert kind not in owners
                    owners[kind] = request
                    source_lanes.add((kind, lane))
                    assert pins[f"io_enq_req_{lane}_valid"] == 1 and pins[f"io_enq_needAlloc_{lane}"] == request["need_alloc"]
                    assert pointer(request["load_start"], 120) == 0 if kind == "load" else pointer(request["store_end"], 64) == 1
            if previous_sta is not None:
                attr = inp["attributes"][previous_sta]
                assert attr["last"] and not attr["exception"] and not attr["nc"] and not attr["mmio"] and attr["memory"]
            previous_sta = None
            for lane, address in enumerate(inp["addresses"]):
                if not address["valid"]:
                    continue
                assert store is None and address["slot"] == 0 and address["rob"] == owners["store"]["rob"]
                assert address["size"] == 3 and address["paddr"] % 16 == address["vaddr"] % 16 == 0
                assert address["last"] and not address["cross_word"] and not address["tlb_miss"] and address["fu_op"] == 6
                assert pins[f"io_sta_storeAddrIn_{lane}_bits_paddr"] == address["paddr"]
                store, sta_tick, previous_sta = address, tick, lane
                sta_lanes.add(lane)
            for lane, data in enumerate(inp["data"]):
                if data["valid"]:
                    assert std_tick is None and pointer(data["sq"], 64) == 0 and data["fu_op"] == 6
                    assert pins[f"io_std_storeDataIn_{lane}_bits_data"] == data["data"]
                    std_tick, original_data = tick, data["data"]
                    totals["actual_std_writes"] += 1
            for bank in range(3):
                p = f"io_replay_{bank}_"
                if not pre[p + "valid"] or not inp["replay_ready"][bank]:
                    continue
                assert load is not None
                for pin, field in (("flag", "flag"), ("value", "value"), ("isFormer", "former")):
                    assert pre[p + "bits_uop_robIdx_" + pin] == int(owners["load"]["rob"][field])
                assert pre[p + "bits_uop_lqIdx_value"] == pre[p + "bits_uop_lqIdx_flag"] == 0
                assert pre[p + "bits_vaddr"] == load["execution"]["vaddr"]
                slot, cause = pre[p + "bits_replayQueueIdx"], load["execution"]["causes"]
                assert slot not in issued and slot % 3 == bank
                # Pinned source C_MA=2, C_FF=4. Neither branch reads a model.
                assert cause in (1 << 2, 1 << 4)
                assert sta_tick is not None if cause == 1 << 2 else std_tick is not None
                issued[slot] = tick
                totals["actual_replay_handshakes_after_real_store_dependency"] += 1
            for lane, packet in enumerate(inp["loads"]):
                request = packet["execution"]
                if not request["valid"]:
                    continue
                assert request["uop"]["rob"] == owners["load"]["rob"] and pointer(request["uop"]["lq"], 120) == 0
                assert pins[f"io_ldu_ldin_{lane}_bits_paddr"] == packet["paddr"]
                if request["replay_feedback"]:
                    assert request["slot"] in issued and issued.pop(request["slot"]) < tick
                    totals["actual_original_slot_feedbacks"] += 1
                if not request["need_replay"] and packet["update_address"]:
                    assert s3_tick is None
                    s3_tick = tick
                load = packet
            for lane in range(2):
                p = f"io_sbuffer_req_{lane}_"
                if pre[p + "valid"] and inp["sbuffer_ready"][lane]:
                    assert std_tick is not None and sta_tick is not None and not sb_ticks
                    assert pre[p + "bits_addr"] == store["paddr"] and pre[p + "bits_vaddr"] == store["vaddr"]
                    assert pre[p + "bits_mask"] == 255 and not pre[p + "bits_wline"]
                    assert pre[p + "bits_data"] % (1 << 64) == original_data % (1 << 64)
                    sb_ticks.append(tick)
                    totals["actual_original_store_sbuffer_fires"] += 1
            if post["io_toLsqEnqCtrl_lqDeq_valid"]:
                assert s3_tick is not None and s3_tick + 4 <= tick and not ld_ticks
                assert post["io_toLsqEnqCtrl_lqDeq_bits"] == 1
                ld_ticks.append(tick)
            if post["io_toLsqEnqCtrl_sqDeq_valid"]:
                assert len(sb_ticks) == 1 and sb_ticks[0] + 2 == tick and not sq_ticks
                assert post["io_toLsqEnqCtrl_sqDeq_bits"] == 1
                sq_ticks.append(tick)
            actual_head = post["io_sqDeqPtr_first_flag"] * 128 + post["io_sqDeqPtr_second_flag"] * 64 + post["io_sqDeqPtr_value"]
            assert actual_head == len(sq_ticks) and not post["io_uncache_req_valid"]
        assert set(owners) == {"load", "store"} and len(ld_ticks) == len(sq_ticks) == len(sb_ticks) == 1 and not issued
        assert rows[-1]["after"]["io_lqEmpty"] and rows[-1]["after"]["io_sqEmpty"]
        for event in map(json.loads, path.with_name("lsq_checks.jsonl").read_text().splitlines()):
            actual = at_tick[event["tick"]][event["phase"]]
            assert event["passed"] and event["actual"] == {key: actual[key] for key in event["expected"]}
            assert all(not ((actual[key] ^ value) & event["masks"].get(key, -1)) for key, value in event["expected"].items())
            totals["independent_directed_expectations"] += 1
        events = [json.loads(line) for line in path.with_name("lsq_actor.jsonl").read_text().splitlines()]
        assert sum(event["event"] == "complete_pair" for event in events) == 1
        for event, expected in (("load_complete", ld_ticks), ("store_complete", sq_ticks), ("sbuffer_fire", sb_ticks)):
            assert [row["tick"] for row in events if row["event"] == event] == expected
        totals.update(actual_load_uid_completed=1, actual_store_uid_completed=1)
        cases.append(dict(nodeid=node, journal=str(path.relative_to(run)), sha256=sha(path), store_effect_tick=sb_ticks[0],
                          store_completion_tick=sq_ticks[0], load_completion_tick=ld_ticks[0]))
    assert seen == set(nodes)
    out = run / "mixed-history-audit-v2.json"
    auditors = {}
    for file in (Path(__file__), ROOT / "tools/audit_lsq_initial.py"):
        dest = run / "evidence-auditors" / file.name
        dest.parent.mkdir(exist_ok=True)
        if dest.exists():
            assert sha(dest) == sha(file)
        else:
            shutil.copy2(file, dest)
        auditors[file.name] = sha(dest)
    report = dict(run=name, status="scoped_public_mixed_pair_real_sq_dependencies_audited_v2_not_full_LSQ", tests=manifest["tests"],
                  counts=dict(totals), completed_dispatch_kind_lane_pairs=sorted(source_lanes), exercised_sta_ports=sorted(sta_lanes),
                  snapshot_files=len(source), manifest_sha256=sha(run / "execution/manifest.json"), auditor_sha256=auditors, cases=cases,
                  previous_rejection_sha256=sha(run / "audit-v1-rejection.json") if (run / "audit-v1-rejection.json").exists() else None,
                  limits="No DUT or verification-model imports. Initial one-Load/one-Store normal effects and real-SQ/STD dependencies only. v1's cause32 assertion was wrong; v2 requires actual C_FF mask16, does not skip data dependency. No bus arbitration/routing, multi-flow, full pools, RAW/RAR, recovery/reset reuse, full forward or stress acceptance. Store perf12 still explicitly unimplemented.")
    if out.exists():
        assert json.loads(out.read_text()) == report
    else:
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
