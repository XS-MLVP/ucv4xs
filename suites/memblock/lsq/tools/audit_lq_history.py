#!/usr/bin/env python3
"""Independent LoadQueue dispatch/replay/S3/retirement audit, no model imports."""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_sq_initial import ROOT, sha, verify_common


def lq(ptr):
    return 120 * int(ptr["flag"]) + ptr["value"]


def audit(name):
    run = ROOT / "results" / name
    manifest, source, nodes = verify_common(run)
    assert all(n.startswith("tests/load_queue/") for n in nodes) and not any(nodes.values())
    counts, reports, seen = Counter(), [], set()
    for path in sorted((run / "cases").rglob("load_queue.jsonl")):
        rows = [json.loads(row) for row in path.read_text().splitlines()]
        node, head, tail, sequence, last = rows[0]["nodeid"], 0, 0, 0, None
        assert node in nodes and node not in seen
        seen.add(node)
        live, all_uids, issued, done, events, bus, responses = {}, {}, {}, set(), [], {}, {}
        by_tick = {}
        for row in rows:
            tick, inp, pre, post = row["post_tick"], row["input"], row["before"], row["after"]
            assert row["nodeid"] == node and row["pre_tick"] + 1 == tick and (last is None or last + 2 == tick)
            assert row["pins"] == row["post_pins"] and len(row["pins"]) == 622 and len(pre) == len(post) == 266
            assert row["checked"] and not row.get("error")
            for phase in ("before", "after"):
                assert all(row[phase][key] == value for key, value in row["expected_" + phase].items())
            by_tick[tick], last = row, tick
            counts["continuous_records"] += 1
            if inp["reset"]:
                assert not live, "active reset requires a new audit version with explicit abort/reuse proof"
                continue
            for bank in range(3):
                p = f"io_replay_{bank}_"
                if not (pre[p + "valid"] and inp["replay_ready"][bank]):
                    continue
                pointer = 120 * pre[p + "bits_uop_lqIdx_flag"] + pre[p + "bits_uop_lqIdx_value"]
                owner = next(owner for pos, owner in live.items() if pos % 240 == pointer)
                uid = owner["uid"]
                assert uid not in issued and owner["completed_tick"] is None and "load" in owner
                request = owner["load"]["execution"]
                uop = request["uop"]
                for key, field in (("robIdx_flag", "flag"), ("robIdx_value", "value"), ("robIdx_isFormer", "former")):
                    assert pre[p + "bits_uop_" + key] == int(owner["rob"][field])
                payload = dict(vaddr=request["vaddr"], uop_fuOpType=uop["operation"], uop_pdest=uop["destination"],
                               uop_perfDebugInfo_runahead_checkpoint_id=uop["checkpoint"], uop_ftqOffset=uop["offset"],
                               uop_ftqPtr_flag=int(uop["ftq"]["flag"]), uop_ftqPtr_value=uop["ftq"]["value"], uop_isRVC=int(uop["rvc"]))
                assert all(pre[p + "bits_" + key] == value for key, value in payload.items())
                slot = pre[p + "bits_replayQueueIdx"]
                assert slot < 120 and slot % 3 == bank and slot not in issued.values()
                issued[uid] = slot
                events.append(dict(event="replay_fire", uid=uid, tick=tick, slot=slot, bank=bank))
                counts["actual_replay_handshakes"] += 1
            for load in inp["loads"]:
                request = load["execution"]
                if not request["valid"]:
                    continue
                owner = next(owner for pos, owner in live.items() if pos % 240 == lq(request["uop"]["lq"]))
                assert owner["rob"] == request["uop"]["rob"] and owner["completed_tick"] is None
                if request["replay_feedback"]:
                    assert issued.pop(owner["uid"]) == request["slot"]
                    counts["actual_replay_feedbacks"] += 1
                owner["load"] = load
                if not request["need_replay"] and load["update_address"]:
                    owner["completed_tick"] = tick
            # Completion output is synchronous with the real VLQ head update;
            # it must consume old, at-least-two-edge-complete identities.
            if post["io_lqDeq_valid"]:
                count = post["io_lqDeq_bits"]
                assert 1 <= count <= 8
                for pos in range(head, head + count):
                    owner = live.pop(pos)
                    assert owner["uid"] not in done and owner["completed_tick"] is not None and owner["completed_tick"] + 4 <= tick
                    done.add(owner["uid"])
                    events.append(dict(event="complete", uid=owner["uid"], tick=tick, position=pos, completed_input_tick=owner["completed_tick"]))
                    counts["actually_completed_uids"] += 1
                head += count
            for lane, dispatch in enumerate(inp["dispatch"]):
                if not dispatch["valid"]:
                    continue
                assert not inp["redirect"]["valid"] and lq(dispatch["start"]) == tail % 240
                for _ in range(dispatch["flows"]):
                    sequence += 1
                    owner = dict(uid=sequence, position=tail, rob=dispatch["rob"], dispatch_lane=lane, completed_tick=None)
                    live[tail] = all_uids[sequence] = owner
                    events.append(dict(event="allocate", uid=sequence, tick=tick, position=tail, dispatch_lane=lane))
                    tail += 1
                    counts["actual_dispatch_flow_uids"] += 1
            assert 0 <= tail - head <= 120
            if pre["io_uncache_req_valid"] and inp["bus"]["ready"]:
                mid = pre["io_uncache_req_bits_id"]
                owner = next(o for o in live.values() if "load" in o and o["load"]["paddr"] == pre["io_uncache_req_bits_addr"])
                assert mid < 16 and mid not in bus
                bus[mid] = dict(uid=owner["uid"], sid=None)
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
                    expected = responses.pop(owner["uid"])
                    owner["bypass_expected"] = expected
                    owner["bypass_lane"] = lane
                    owner["bypass_tick"] = tick + 2
                    counts["actual_bypass_consumptions"] += 1
            for owner in all_uids.values():
                if owner.get("bypass_tick") == tick:
                    p = f"io_bypass_{owner['bypass_lane']}_s2Resp_"
                    response = owner["bypass_expected"]
                    assert post[p + "valid"] and post[p + "bits_data"] == response["data"] * ((1 << 64) + 1)
                    assert post[p + "bits_derr"] == response["error"] and post[p + "bits_nderr"] == response["nderr"]
                    counts["independently_checked_bypass_data_and_errors"] += 1
        assert not live and not issued and not bus and not responses and len(done) == sequence
        actor = [json.loads(row) for row in path.with_name("lq_actor.jsonl").read_text().splitlines()]
        for event in actor:
            if event["event"] == "allocate":
                want = all_uids[event["owner"]["uid"]]
                assert event["owner"]["position"] == want["position"] and event["owner"]["rob"] == want["rob"]
            elif event["event"] in ("complete", "replay_fire"):
                assert any(all(candidate.get(key) == value for key, value in event.items() if key not in ("nodeid",)) for candidate in events)
            elif event["event"] == "checked":
                assert set(event["uids"]) <= done and event["completed"] == sorted(done)
        reports.append(dict(nodeid=node, journal=str(path.relative_to(run)), sha256=sha(path), records=len(rows), allocated=sequence, completed=len(done)))
    assert seen == set(nodes)
    dest = run / "evidence-auditors" / Path(__file__).name
    dest.parent.mkdir(exist_ok=True)
    if dest.exists():
        assert sha(dest) == sha(Path(__file__))
    else:
        shutil.copy2(Path(__file__), dest)
    report = dict(run=name, status="scoped_public_dispatch_replay_completion_and_bus_byte_audit", tests=manifest["tests"], counts=dict(counts),
                  snapshot_files=len(source), manifest_sha256=sha(run / "execution/manifest.json"), auditor_sha256=sha(dest), cases=reports,
                  limits="Audits implemented passing initial directed cases only; no redirect/reset abort proof yet, no all-slot/cause/seeded claim, not LoadQueue or LSQ acceptance. Current tests' explicit RAR/RAW response checks supplement this UID/bus audit.")
    out = run / "history-audit.json"
    if out.exists():
        assert json.loads(out.read_text()) == report
    else:
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "cases"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
