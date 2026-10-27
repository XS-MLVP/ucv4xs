#!/usr/bin/env python3
"""Independent raw public-history audit for first mixed pair/real-SQ tests.

Intentionally rejects bus/restore/multi-flow/forward scopes not implemented
here. A scoped successful audit cannot be promoted to full LsqWrapper or LSQ.
No DUT or verification-domain model imports; no change-log answers.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_sq_initial import ROOT, sha, verify_common


def sq(pointer):
    return int(pointer["first"]) * 128 + int(pointer["second"]) * 64 + pointer["value"]


def lq(pointer):
    return int(pointer["flag"]) * 120 + pointer["value"]


def audit(name):
    run = ROOT / "results" / name
    manifest, source, nodes = verify_common(run)
    assert not any(nodes.values()) and all(node.startswith("tests/lsq_wrapper/test_initial.py::") for node in nodes)
    counts, cases, seen, source_lanes, store_ports = Counter(), [], set(), set(), set()
    for path in sorted((run / "cases").rglob("lsq_wrapper.jsonl")):
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        node, last, owners, store, load, replay_fired = rows[0]["nodeid"], None, {}, {}, {}, {}
        assert node in nodes and node not in seen
        seen.add(node)
        sbuffer_ticks, load_done, store_done, data_sent, sta_sent = [], [], [], None, None
        s3_done, old_sta, samples = None, None, {}
        for row in rows:
            inp, pins, pre, post, tick = row["input"], row["pins"], row["before"], row["after"], row["post_tick"]
            assert row["nodeid"] == node and row["pre_tick"] + 1 == tick and (last is None or last + 2 == tick)
            assert pins == row["post_pins"] and len(pins) == 603 and len(pre) == len(post) == 458
            assert row["checked"] and not inp["redirect"]["valid"] and not any(inp["bus"].get(key) for key in ("ready", "ack", "response"))
            assert not any(q["valid"] for q in (*inp["raw_queries"], *inp["rar_queries"], *inp["queries"]))
            for phase in ("before", "after"):
                assert not {pin: [row[phase][pin], value] for pin, value in row["expected_" + phase].items()
                            if (row[phase][pin] ^ value) & row["masks_" + phase].get(pin, -1)}
            if inp["reset"]:
                assert not owners
                last, samples[tick] = tick, row
                continue
            for lane, request in enumerate(inp["dispatch"]):
                if not request["valid"]:
                    continue
                assert request["flows"] == 1 and request["need_alloc"] in (1, 2)
                kind = "load" if request["need_alloc"] == 1 else "store"
                assert kind not in owners
                owners[kind] = request
                source_lanes.add((kind, lane))
                assert pins[f"io_enq_req_{lane}_valid"] == 1 and pins[f"io_enq_needAlloc_{lane}"] == request["need_alloc"]
                if kind == "load":
                    assert lq(request["load_start"]) == 0
                else:
                    assert sq(request["store_end"]) == 1
            if old_sta is not None:
                lane = old_sta
                attr = inp["attributes"][lane]
                assert attr["last"] and not attr["exception"] and not attr["nc"] and not attr["mmio"] and attr["memory"]
            old_sta = None
            for lane, address in enumerate(inp["addresses"]):
                if not address["valid"]:
                    continue
                assert not store and address["slot"] == 0 and address["rob"] == owners["store"]["rob"]
                assert address["size"] == 3 and address["paddr"] % 16 == address["vaddr"] % 16 == 0
                assert address["last"] and not address["cross_word"] and not address["tlb_miss"] and address["fu_op"] == 6
                assert pins[f"io_sta_storeAddrIn_{lane}_bits_paddr"] == address["paddr"]
                store, sta_sent, old_sta = address, tick, lane
                store_ports.add(lane)
            for lane, data in enumerate(inp["data"]):
                if data["valid"]:
                    assert data_sent is None and sq(data["sq"]) == 0 and data["fu_op"] == 6
                    assert pins[f"io_std_storeDataIn_{lane}_bits_data"] == data["data"]
                    data_sent, original_data = tick, data["data"]
                    counts["actual_std_writes"] += 1
            for bank in range(3):
                p = f"io_replay_{bank}_"
                if pre[p + "valid"] and inp["replay_ready"][bank]:
                    assert load and pre[p + "bits_uop_robIdx_value"] == owners["load"]["rob"]["value"]
                    assert pre[p + "bits_uop_lqIdx_value"] == pre[p + "bits_uop_lqIdx_flag"] == 0
                    slot = pre[p + "bits_replayQueueIdx"]
                    assert slot not in replay_fired and slot % 3 == bank
                    cause = load["execution"]["causes"]
                    assert cause in (4, 32) and (sta_sent is not None if cause == 4 else data_sent is not None)
                    replay_fired[slot] = tick
                    counts["actual_replay_handshakes_after_real_store_dependency"] += 1
            for lane, packet in enumerate(inp["loads"]):
                request = packet["execution"]
                if not request["valid"]:
                    continue
                assert request["uop"]["rob"] == owners["load"]["rob"] and lq(request["uop"]["lq"]) == 0
                assert pins[f"io_ldu_ldin_{lane}_bits_paddr"] == packet["paddr"]
                if request["replay_feedback"]:
                    assert request["slot"] in replay_fired and replay_fired.pop(request["slot"]) < tick
                    counts["actual_original_slot_feedbacks"] += 1
                if not request["need_replay"] and packet["update_address"]:
                    assert s3_done is None
                    s3_done = tick
                load = packet
            for lane in range(2):
                p = f"io_sbuffer_req_{lane}_"
                if not pre[p + "valid"] or not inp["sbuffer_ready"][lane]:
                    continue
                assert data_sent is not None and sta_sent is not None and not sbuffer_ticks
                assert pre[p + "bits_addr"] == store["paddr"] and pre[p + "bits_vaddr"] == store["vaddr"]
                assert pre[p + "bits_mask"] == 255 and not pre[p + "bits_wline"]
                assert pre[p + "bits_data"] % (1 << 64) == original_data % (1 << 64)
                sbuffer_ticks.append(tick)
                counts["actual_original_store_sbuffer_fires"] += 1
            if post["io_toLsqEnqCtrl_lqDeq_valid"]:
                assert s3_done is not None and s3_done + 4 <= tick and not load_done
                assert post["io_toLsqEnqCtrl_lqDeq_bits"] == 1
                load_done.append(tick)
            if post["io_toLsqEnqCtrl_sqDeq_valid"]:
                assert len(sbuffer_ticks) == 1 and sbuffer_ticks[0] + 2 == tick and not store_done
                assert post["io_toLsqEnqCtrl_sqDeq_bits"] == 1
                store_done.append(tick)
            ptr = int(post["io_sqDeqPtr_first_flag"]) * 128 + int(post["io_sqDeqPtr_second_flag"]) * 64 + post["io_sqDeqPtr_value"]
            assert ptr == len(store_done)
            assert not post["io_uncache_req_valid"]
            counts["continuous_records"] += 1
            last, samples[tick] = tick, row
        assert owners.keys() == {"load", "store"} and len(load_done) == len(store_done) == len(sbuffer_ticks) == 1
        assert not replay_fired and rows[-1]["after"]["io_lqEmpty"] and rows[-1]["after"]["io_sqEmpty"]
        for event in map(json.loads, path.with_name("lsq_checks.jsonl").read_text().splitlines()):
            actual = samples[event["tick"]][event["phase"]]
            assert event["passed"] and event["actual"] == {key: actual[key] for key in event["expected"]}
            assert all(not ((actual[key] ^ value) & event["masks"].get(key, -1)) for key, value in event["expected"].items())
            counts["independent_directed_expectations"] += 1
        events = [json.loads(line) for line in path.with_name("lsq_actor.jsonl").read_text().splitlines()]
        assert sum(event["event"] == "complete_pair" for event in events) == 1
        assert [event["tick"] for event in events if event["event"] == "load_complete"] == load_done
        assert [event["tick"] for event in events if event["event"] == "store_complete"] == store_done
        assert [event["tick"] for event in events if event["event"] == "sbuffer_fire"] == sbuffer_ticks
        counts.update(actual_load_uid_completed=1, actual_store_uid_completed=1)
        cases.append(dict(nodeid=node, journal=str(path.relative_to(run)), sha256=sha(path),
                          store_effect_tick=sbuffer_ticks[0], store_completion_tick=store_done[0], load_completion_tick=load_done[0]))
    assert seen == set(nodes)
    dest = run / "evidence-auditors" / Path(__file__).name
    dest.parent.mkdir(exist_ok=True)
    if dest.exists():
        assert sha(dest) == sha(Path(__file__))
    else:
        shutil.copy2(Path(__file__), dest)
    report = dict(run=name, status="scoped_real_mixed_pair_and_actual_sq_dependency_audited_not_full_wrapper", tests=manifest["tests"],
                  counts=dict(counts), completed_dispatch_kind_lane_pairs=sorted(source_lanes), exercised_sta_ports=sorted(store_ports),
                  snapshot_files=len(source), manifest_sha256=sha(run / "execution/manifest.json"), auditor_sha256=sha(dest), cases=cases,
                  limits="No DUT or reference imports/internal answers. Only initial one-Load/one-Store normal effects and real-SQ dependency tests. Explicitly no bus arbitration/routing, multi-flow, full pools, RAW/RAR, redirect/reset reuse, complete forward or stress acceptance. Store perf12 still unimplemented in staged checker.")
    output = run / "mixed-history-audit-v1.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
