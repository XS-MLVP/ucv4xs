#!/usr/bin/env python3
"""Widened Deq producer domain: independent UID/byte replay and failure proof.

Reuses the immutable, model-independent public replay helper, not DeqModel.
Unlike the old 89-case audit this accepts no failed reference-phase mismatch:
each failed case must have an independently reconstructed safety violation.
The failing edge is kept separate from successfully retired ownership.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_deq_lifecycle import Replay, lines, position, segments
from audit_sq_initial import ROOT, sha, verify_common


def differences(row):
    result = []
    for phase in ("before", "after"):
        for pin, want in row.get("expected_" + phase, {}).items():
            got = row[phase][pin]
            if (got ^ want) & row["masks_" + phase].get(pin, -1):
                result.append(dict(pin=pin, actual=got, expected=want, phase=phase, tick=row["post_tick"]))
    return result


def independent_failure(replay, row, bad):
    """Prove the failing property directly from owners and actual transfers."""
    pins = {d["pin"] for d in bad}
    tick, inp, pre, post = row["post_tick"], row["input"], row["before"], row["after"]
    if "io_sqDeqCnt" in pins:
        assert bad[0]["phase"] == "before", "post-edge phase disagreements are NOT an RTL proof"
        owner = replay.live[replay.head]
        uid, st = owner["uid"], owner["store"]
        assert st["committed"] and not st["inactive"] and not st["memory_type"] and not st["cache_operation"]
        required = {0, 1} if st["cross_word"] else {0}
        # Even a consumption on THIS edge cannot provide a registered credit
        # on its pre-edge. No copying of RTL's two finish bits/PopCount.
        assert replay.parts[uid] != required and pre["io_sqDeqCnt"] > 0
        younger = replay.live[replay.head + 1]
        assert younger["uid"] in replay.finished and replay.finished[younger["uid"]] < tick
        assert inp["dequeue_controls"][1]["finished"] and not inp["dequeue_controls"][0]["finished"]
        return dict(issue="DEQ-FINISH-ORDER-001", tick=tick, old_uid=uid, younger_uid=younger["uid"],
                    old_consumed_parts=sorted(replay.parts[uid]), required_parts=sorted(required),
                    younger_finish_tick=replay.finished[younger["uid"]], actual_attempted_credit=pre["io_sqDeqCnt"],
                    input_sbuffer_ready=inp["sbuffer_ready"], failing_edge_not_counted_as_successful_retirement=True)
    if "io_sbufferCtrl_req_flush" in pins:
        owner = replay.live[replay.read]
        uid, st = owner["uid"], owner["store"]
        assert st["cache_operation"] and st["cbo"] == 3 and st["data"] == 0
        own_fires = set(replay.parts[uid])
        current_fires = []
        for lane, seg in enumerate(replay.queue):
            if pre[f"io_writeToSbuffer_req_{lane}_valid"] and inp["sbuffer_ready"][lane]:
                current_fires.append(dict(uid=seg["uid"], part=seg["part"], wline=seg["wline"]))
                if seg["uid"] == uid:
                    own_fires.add(seg["part"])
        assert not own_fires and current_fires and all(fire["uid"] != uid for fire in current_fires)
        assert not pre["io_sbufferCtrl_req_flush"] and post["io_sbufferCtrl_req_flush"]
        return dict(issue="DEQ-ZERO-001", tick=tick, zero_uid=uid, own_zero_consumed_parts=[],
                    current_actual_sbuffer_fires=current_fires, violation="flush began after somebody else's transfer; own zero never fired")
    if all("exceptionVec_" in pin for pin in pins):
        bus = replay.bus
        assert bus and bus["kind"] == "cache" and bus["response"] and (bus["denied"] or bus["corrupt"])
        for diff in bad:
            bit = int(diff["pin"].split("_")[-1])
            assert diff["actual"] == 0 and diff["expected"] == int(bus["denied" if bit == 7 else "corrupt"]) == 1
        return dict(issue="DEQ-WB-001", tick=tick, uid=bus["owner"]["uid"], accepted_response=dict(denied=bus["denied"], corrupt=bus["corrupt"]), differences=bad)
    assert pins == {"io_writeToSbuffer_req_1_bits_wline"}, pins
    st = inp["stores"][0]
    assert st["cross_word"] and not st["cache_operation"]
    expected = segments(dict(uid=replay.live[replay.read]["uid"], store=st, second_page=None))[1]
    assert expected["wline"] == 0 and post["io_writeToSbuffer_req_1_valid"] and post["io_writeToSbuffer_req_1_bits_wline"] == 1
    for field in ("vaddr", "mask", "data"):
        mask = sum(255 << (8 * b) for b in range(16) if expected["mask"] >> b & 1) if field == "data" else -1
        assert not ((post["io_writeToSbuffer_req_1_bits_" + field] ^ expected[field]) & mask)
    return dict(issue="DEQ-SPLIT-WLINE-001", tick=tick, uid=expected["uid"], expected_wline=0, actual_wline=1)


def audit(name):
    run = ROOT / "results" / name
    manifest, source, all_nodes = verify_common(run)
    nodes = {n: failed for n, failed in all_nodes.items() if n.startswith("tests/deq/")}
    assert len(nodes) == 92
    counts, reports, seen, violations = Counter(), [], set(), Counter()
    for path in sorted((run / "cases").rglob("deq*.jsonl")):
        if path.name not in ("deq_full.jsonl", "deq_module.jsonl"):
            continue
        trace = lines(path)
        node, by_tick, bad = trace[0]["nodeid"], {}, []
        assert node in nodes and node not in seen
        seen.add(node)
        last, force = None, False
        for row in trace:
            tick, inp = row["post_tick"], row["input"]
            assert row["nodeid"] == node and inp == row["post_input"] and row["pre_tick"] + 1 == tick
            assert last is None or last + 2 == tick
            last = tick
            by_tick[tick] = row
            assert 0 <= inp["valid_count"] <= 128
            force = False if inp["reset"] else inp["valid_count"] >= 60 or inp["valid_count"] >= 55 and force
            assert row["after"]["io_sbufferCtrl_req_forceWrite"] == int(force)
            counts["continuous_records"] += 1
            if path.name == "deq_full.jsonl":
                diff = differences(row)
                assert row["checked"] == (not diff)
                bad.extend(diff)
        proof, replay, stepped = None, None, set()
        if path.name == "deq_full.jsonl":
            for event in lines(path.with_name("deq_psq.jsonl")):
                kind = event["event"]
                if kind == "start":
                    assert replay is None
                    replay = Replay(event["base"])
                elif kind == "allocate":
                    replay.allocate(event["owner"])
                elif kind == "permission":
                    replay.all[event["uid"]]["store"]["committed"] = event["committed"]
                elif kind == "step":
                    assert by_tick[event["tick"]]["checked"]
                    replay.step(by_tick[event["tick"]], event)
                    stepped.add(event["tick"])
                elif kind == "checked":
                    assert set(event["uids"]) <= replay.done and event["completed"] == sorted(replay.done)
                elif kind == "reset":
                    assert event["aborted"] == sorted(o["uid"] for o in replay.live.values())
                    for owner in replay.live.values():
                        replay.aborted.add(owner["uid"])
                        replay.aborted_slots[owner["position"] % 64] = owner["uid"]
                    replay.live.clear()
                    replay.queue.clear()
                    replay.bus = None
                    replay.head = replay.read = replay.tail = 0
                else:
                    raise AssertionError(kind)
            if nodes[node]:
                assert replay is not None and bad and trace[-1]["post_tick"] not in stepped
                proof = independent_failure(replay, trace[-1], bad)
                # Preserve the bad terminal edge, never call it completed.
                counts["independently_proven_bad_terminal_edges"] += 1
            else:
                assert not bad and (replay is None or not replay.live and not replay.queue and replay.bus is None)
            if replay:
                assert not replay.violations
                retained = {owner["uid"] for owner in replay.live.values()}
                assert len(replay.all) == len(replay.done) + len(replay.aborted) + len(retained)
                counts.update(replay.counts)
                counts.update(completed=len(replay.done), reset_aborted=len(replay.aborted), failure_retained=len(retained), reset_same_slot_reuse=len(replay.reuse))
        else:
            for check in lines(path.with_name("deq_checks.jsonl")):
                actual = by_tick[check["tick"]][check["phase"]]
                assert check["actual"] == {key: actual[key] for key in check["expected"]}
                diff = [dict(pin=k, actual=actual[k], expected=v, phase=check["phase"], tick=check["tick"])
                        for k, v in check["expected"].items() if (actual[k] ^ v) & check["bit_masks"].get(k, -1)]
                assert check["passed"] == (not diff)
                bad.extend(diff)
            if nodes[node]:
                row = trace[-1]
                if "split_tail" in node:
                    st = next(st for r in trace for st in r["input"]["stores"] if st["committed"] and st["cross_word"])
                    expected = segments(dict(uid=0, store=st, second_page=None))[1]
                    assert row["input"]["sbuffer_ready"] == [True, True] and row["before"]["io_writeToSbuffer_req_1_valid"]
                    for field in ("addr", "vaddr", "mask", "data"):
                        mask = 0xFFFFFFFF if field == "data" else -1
                        assert not ((row["before"]["io_writeToSbuffer_req_1_bits_" + field] ^ expected[field]) & mask)
                    assert row["before"]["io_writeToSbuffer_req_1_bits_wline"] == 1 and expected["wline"] == 0
                    proof = dict(issue="DEQ-SPLIT-WLINE-001", tick=row["post_tick"], actual_sbuffer_tail_fire=True)
                else:
                    arrival = next(r for r in trace if r["input"]["cache_response"] and r["before"]["io_toDCache_resp_ready"])
                    assert arrival["input"]["stores"] == row["input"]["stores"]
                    for bit, field in ((7, "cache_denied"), (19, "cache_corrupt")):
                        assert arrival["after"]["io_writeBack_bits_exceptionVec_" + str(bit)] == int(arrival["input"][field])
                    assert all("exceptionVec_" in d["pin"] and d["actual"] == 0 and d["expected"] == 1 for d in bad)
                    proof = dict(issue="DEQ-WB-001", tick=row["post_tick"], accepted_response_tick=arrival["post_tick"],
                                 actual_wb_fire=bool(row["before"]["io_writeBack_valid"] and row["input"]["writeback_ready"]))
        assert bool(bad) == nodes[node] and bool(proof) == nodes[node], node
        if proof:
            violations[proof["issue"]] += 1
        reports.append(dict(nodeid=node, journal=str(path.relative_to(run)), records=len(trace), sha256=sha(path),
                            differences=bad, independent_failure=proof, same_slot_reset_reuse=replay.reuse if replay else []))
    assert seen == set(nodes) and sum(violations.values()) == sum(nodes.values())
    assert counts["reset_same_slot_reuse"] == 4
    functional = json.loads((run / "execution/functional-coverage.json").read_text())
    groups = {g["instance"]: g["points"][0]["counts"] for g in functional["groups"]}
    reached, checked = (groups["lsq.deq_module." + kind] for kind in ("reached", "checked"))
    assert all(reached.values()) and all(reached[key] >= value for key, value in checked.items())
    auditors = {}
    for tool in (Path(__file__), ROOT / "tools/audit_deq_lifecycle.py", ROOT / "tools/audit_sq_initial.py", ROOT / "tools/audit_psq_initial.py"):
        dest = run / "evidence-auditors" / tool.name
        dest.parent.mkdir(exist_ok=True)
        if dest.exists():
            assert sha(dest) == sha(tool)
        else:
            shutil.copy2(tool, dest)
        auditors[tool.name] = sha(dest)
    report = dict(run=name, status="widened_domain_public_uid_and_byte_audit_with_real_failures", dut_acceptance="NOT_PASS",
                  tests=dict(Counter("FAIL" if v else "PASS" for v in nodes.values())), counts=dict(counts),
                  failure_cases_by_issue=dict(violations), checked_scenarios=sum(bool(c) for c in checked.values()), total_scenarios=len(checked),
                  missing_checked=[key for key, count in checked.items() if not count], snapshot_files=len(source), auditors=auditors,
                  manifest_sha256=sha(run / "execution/manifest.json"), cases=reports,
                  limits="92 Deq leaf cases, actual parent-permitted special/ordinary overlap. Successful edges replayed independently; a bad terminal edge is not retired in the UID ledger. Leaf post-edge transient credit is not ownership permission. No architecture proof; old 89-case evidence unchanged.")
    out = run / "lifecycle-audit-v2.json"
    if out.exists():
        assert json.loads(out.read_text()) == report
    else:
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "cases"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
