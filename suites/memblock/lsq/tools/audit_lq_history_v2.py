#!/usr/bin/env python3
"""Full public lifecycle replay with time-indexed intermediate checked proofs.

v1's final done set comparison was too narrow for repeated long-stream proof
events. Keep v1 and its reports unchanged. Rebuild done_at_tick from ACTUAL
dispatch/S3/retirement, never from an actor's asserted completed list.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_lq_history import lq
from audit_sq_initial import ROOT, sha, verify_common


def audit(name):
    run = ROOT / "results" / name
    manifest, source, nodes = verify_common(run)
    assert not any(nodes.values()) and all(node.startswith("tests/load_queue/") for node in nodes)
    counts, reports, seen = Counter(), [], set()
    entry_kinds, lq_slots, dispatch_lanes, replay_banks = set(), set(), set(), set()
    for path in sorted((run / "cases").rglob("load_queue.jsonl")):
        rows = [json.loads(row) for row in path.read_text().splitlines()]
        node, head, tail, sequence, last = rows[0]["nodeid"], 0, 0, 0, None
        assert node in nodes and node not in seen
        seen.add(node)
        live, all_uids, issued, done, done_at_tick, bus, responses, expected_data = {}, {}, {}, set(), {}, {}, {}, []
        replay_events, complete_events = [], []
        for row in rows:
            tick, inp, pre, post = row["post_tick"], row["input"], row["before"], row["after"]
            assert row["nodeid"] == node and row["pre_tick"] + 1 == tick and (last is None or last + 2 == tick)
            assert row["pins"] == row["post_pins"] and len(row["pins"]) == 622 and len(pre) == len(post) == 266
            assert row["checked"] and not row.get("error")
            for phase in ("before", "after"):
                assert all(row[phase][pin] == value for pin, value in row["expected_" + phase].items())
            last = tick
            counts["continuous_records"] += 1
            if inp["reset"]:
                assert not live, "active reset/redirect requires explicit new cancellation/reuse audit scope"
                done_at_tick[tick] = frozenset(done)
                continue
            assert not inp["redirect"]["valid"], "no unverified recovery scope accepted by this auditor"
            for bank in range(3):
                p = f"io_replay_{bank}_"
                if not (pre[p + "valid"] and inp["replay_ready"][bank]):
                    continue
                pointer = 120 * pre[p + "bits_uop_lqIdx_flag"] + pre[p + "bits_uop_lqIdx_value"]
                owner = next(o for pos, o in live.items() if pos % 240 == pointer)
                uid, request = owner["uid"], owner["load"]["execution"]
                assert uid not in issued and owner["completed_tick"] is None
                uop = request["uop"]
                assert (pre[p + "bits_uop_robIdx_flag"], pre[p + "bits_uop_robIdx_value"], pre[p + "bits_uop_robIdx_isFormer"]) == tuple(int(owner["rob"][k]) for k in ("flag", "value", "former"))
                fields = dict(vaddr=request["vaddr"], uop_fuOpType=uop["operation"], uop_pdest=uop["destination"],
                              uop_perfDebugInfo_runahead_checkpoint_id=uop["checkpoint"], uop_ftqOffset=uop["offset"],
                              uop_ftqPtr_flag=int(uop["ftq"]["flag"]), uop_ftqPtr_value=uop["ftq"]["value"], uop_isRVC=int(uop["rvc"]))
                assert all(pre[p + "bits_" + key] == value for key, value in fields.items())
                slot = pre[p + "bits_replayQueueIdx"]
                assert slot < 120 and slot % 3 == bank and slot not in issued.values()
                issued[uid] = slot
                replay_banks.add(bank)
                replay_events.append(dict(event="replay_fire", tick=tick, uid=uid, slot=slot, bank=bank))
                counts["actual_replay_handshakes"] += 1
            for load in inp["loads"]:
                request = load["execution"]
                if not request["valid"]:
                    continue
                owner = next(o for pos, o in live.items() if pos % 240 == lq(request["uop"]["lq"]))
                assert owner["completed_tick"] is None and owner["rob"] == request["uop"]["rob"]
                if request["replay_feedback"]:
                    assert issued.pop(owner["uid"]) == request["slot"]
                    counts["actual_replay_feedbacks"] += 1
                owner["load"] = load
                if not request["need_replay"] and load["update_address"]:
                    owner["completed_tick"] = tick
            if post["io_lqDeq_valid"]:
                count = post["io_lqDeq_bits"]
                assert 1 <= count <= 8
                for pos in range(head, head + count):
                    owner = live.pop(pos)
                    assert owner["uid"] not in done and owner["completed_tick"] is not None and owner["completed_tick"] + 4 <= tick
                    done.add(owner["uid"])
                    complete_events.append(dict(event="complete", tick=tick, uid=owner["uid"], position=pos, completed_input_tick=owner["completed_tick"]))
                    lq_slots.add(pos % 120)
                    counts["actually_completed_uids"] += 1
                head += count
            for lane, dispatch in enumerate(inp["dispatch"]):
                if dispatch["valid"]:
                    assert lq(dispatch["start"]) == tail % 240
                    for _ in range(dispatch["flows"]):
                        sequence += 1
                        owner = dict(uid=sequence, position=tail, rob=dispatch["rob"], dispatch_lane=lane, completed_tick=None)
                        live[tail] = all_uids[sequence] = owner
                        tail += 1
                        counts["actual_dispatch_flow_uids"] += 1
                        dispatch_lanes.add(lane)
            assert 0 <= tail - head <= 120
            if pre["io_uncache_req_valid"] and inp["bus"]["ready"]:
                mid = pre["io_uncache_req_bits_id"]
                owner = next(o for o in live.values() if "load" in o and o["load"]["paddr"] == pre["io_uncache_req_bits_addr"])
                request = owner["load"]["execution"]
                assert mid < 16 and mid not in bus and pre["io_uncache_req_bits_nc"] == int(request["nc"])
                bus[mid] = dict(uid=owner["uid"], sid=None)
                entry_kinds.add((mid, bool(request["nc"])))
                counts["actual_bus_requests"] += 1
            if inp["bus"]["ack"]:
                bus[inp["bus"]["mid"]]["sid"] = inp["bus"]["sid"]
            if inp["bus"]["response"]:
                matched = [mid for mid, job in bus.items() if job["sid"] == inp["bus"]["response_id"]]
                assert matched
                for mid in matched:
                    job = bus.pop(mid)
                    assert job["uid"] not in responses
                    responses[job["uid"]] = dict(data=inp["bus"]["data"], error=int(inp["bus"]["error"]), nderr=int(inp["bus"]["nderr"]))
            for lane, query in enumerate(inp["bypass"]):
                p = f"io_bypass_{lane}_"
                if query["valid"] and post[p + "s1Resp_valid"]:
                    owner = next(o for pos, o in live.items() if pos % 240 == lq(query["lq"]))
                    assert owner["uid"] in responses and post[p + "s1Resp_bits_paddr"] == owner["load"]["paddr"]
                    expected_data.append(dict(tick=tick + 2, lane=lane, uid=owner["uid"], **responses.pop(owner["uid"])))
                    counts["actual_bypass_consumptions"] += 1
            for response in expected_data:
                if response["tick"] == tick:
                    p = f"io_bypass_{response['lane']}_s2Resp_"
                    assert post[p + "valid"] and post[p + "bits_data"] == response["data"] * ((1 << 64) + 1)
                    assert post[p + "bits_derr"] == response["error"] and post[p + "bits_nderr"] == response["nderr"]
                    counts["independently_checked_bypass_data_and_errors"] += 1
            done_at_tick[tick] = frozenset(done)
        assert not live and not issued and not bus and not responses and len(done) == sequence
        assert all(response["tick"] <= last for response in expected_data)
        for event in map(json.loads, path.with_name("lq_actor.jsonl").read_text().splitlines()):
            if event["event"] == "allocate":
                owner = all_uids[event["owner"]["uid"]]
                assert owner["position"] == event["owner"]["position"] and owner["rob"] == event["owner"]["rob"]
            elif event["event"] in ("complete", "replay_fire"):
                candidate = {key: value for key, value in event.items() if key != "nodeid"}
                assert candidate in (complete_events if event["event"] == "complete" else replay_events)
            elif event["event"] == "checked":
                then = done_at_tick[event["tick"]]
                assert set(event["uids"]) <= then and event["completed"] == sorted(then)
                counts["time_indexed_actual_completion_proof_events"] += 1
        reports.append(dict(nodeid=node, journal=str(path.relative_to(run)), sha256=sha(path), records=len(rows), allocated=sequence, completed=len(done)))
    assert seen == set(nodes)
    auditors = {}
    for tool in (Path(__file__), ROOT / "tools/audit_lq_history.py", ROOT / "tools/audit_sq_initial.py", ROOT / "tools/audit_psq_initial.py"):
        dest = run / "evidence-auditors" / tool.name
        dest.parent.mkdir(exist_ok=True)
        if dest.exists():
            assert sha(dest) == sha(tool)
        else:
            shutil.copy2(tool, dest)
        auditors[tool.name] = sha(dest)
    report = dict(run=name, status="public_uid_bus_byte_and_time_indexed_completion_audited", tests=manifest["tests"], counts=dict(counts),
                  completed_physical_lq_slots=sorted(lq_slots), dispatch_lanes=sorted(dispatch_lanes), replay_banks=sorted(replay_banks),
                  real_uncache_entry_type_pairs=[dict(entry=mid, nc=nc) for mid, nc in sorted(entry_kinds)], snapshot_files=len(source),
                  manifest_sha256=sha(run / "execution/manifest.json"), auditors=auditors, cases=reports,
                  limits="Passing implemented directed LoadQueue scope only. ALL actual dispatch/S3/replay/retirement and bus/bypass data independently replayed. Intermediate proof events checked against actual done set at THAT tick, not final done set. No reset/redirect/all-cause/hint/random or whole-LSQ acceptance claim.")
    out = run / "history-audit-v2.json"
    if out.exists():
        assert json.loads(out.read_text()) == report
    else:
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ("cases", "real_uncache_entry_type_pairs", "completed_physical_lq_slots")}, indent=2, ensure_ascii=False))
    print("real entry/type pairs:", len(entry_kinds), "; completed physical LQ slots:", len(lq_slots))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
