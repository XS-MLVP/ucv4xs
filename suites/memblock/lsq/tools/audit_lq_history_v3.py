#!/usr/bin/env python3
"""Public-history LSQ branch audit: UID, CAM conflicts, reset/recovery and faults.

No DUT/reference imports. Full UID identity comes from actual dispatch and S3;
RAR/RAW candidates from actual accepted queries. Failed outputs need separate
public counterexamples, never an issue whitelist or changed test expectation.
"""
import argparse
from collections import Counter, deque
import copy
import json
from pathlib import Path
import shutil

from audit_lq_history import lq
from audit_raw_trace import younger, flushed, match, sq_raw
from audit_sq_initial import ROOT, sha, verify_common


def hash_line(address):
    high = 0
    for bit in range(6, 48):
        if address >> bit & 1:
            high ^= 1 << ((bit - 6) % 11)
    low = address // 64 % 32
    for bit in range(5):
        if address >> (11 + bit) & 1:
            low ^= 1 << (4 - bit)
    return high * 32 + low


def differences(row):
    return [dict(phase=phase, pin=pin, actual=row[phase][pin], expected=value, tick=row["post_tick"])
            for phase in ("before", "after") for pin, value in row.get("expected_" + phase, {}).items() if row[phase][pin] != value]


def payload(query, store):
    return dict(robIdx_flag=int(query["rob"]["flag"]), robIdx_value=query["rob"]["value"], robIdx_isFormer=int(query["rob"]["former"]),
                ftqIdx_flag=int(query["ftq"]["flag"]), ftqIdx_value=query["ftq"]["value"], ftqOffset=query["ftq_offset"],
                isRVC=int(query["is_rvc"]), debug_runahead_checkpoint_id=query["checkpoint"], stFtqIdx_flag=int(store["ftq_flag"]),
                stFtqIdx_value=store["ftq_value"], stFtqOffset=store["ftq_offset"], stIsRVC=int(store["is_rvc"]))


def oldest(candidates):
    result = None
    for candidate in candidates:
        if result is None or younger(result["rob"], candidate["rob"]):
            result = candidate
    return result


class Replay:
    def __init__(self):
        self.head = self.tail = self.sequence = 0
        self.live, self.all, self.issued, self.bus, self.responses = {}, {}, {}, {}, {}
        self.done, self.cancelled, self.aborted, self.reuse = set(), set(), set(), {}
        self.done_at, self.expected_data, self.recovery = {}, [], deque()
        self.counts, self.events, self.proofs = Counter(), [], []
        self.rars, self.raws, self.jobs, self.rar_release = [], [], [], set()
        self.rar_history, self.raw_history = deque(((), ()), maxlen=2), deque(((), ()), maxlen=2)
        self.record_sequence = 0
        self.previous_release = None
        self.rp_pairs, self.causes, self.entry_types, self.lq_slots = set(), set(), set(), set()

    def owner(self, pointer):
        return next(owner for position, owner in self.live.items() if position % 240 == lq(pointer))

    def reset(self, tick):
        self.aborted.update(owner["uid"] for owner in self.live.values())
        self.counts["reset_aborted_uid_events"] += len(self.live)
        self.live.clear(); self.issued.clear(); self.bus.clear(); self.responses.clear()
        self.expected_data.clear(); self.recovery.clear()
        self.rars.clear(); self.raws.clear(); self.jobs.clear(); self.rar_release.clear()
        self.rar_history, self.raw_history = deque(((), ()), maxlen=2), deque(((), ()), maxlen=2)
        self.previous_release = None
        self.head = self.tail = 0
        self.done_at[tick] = frozenset(self.done)

    def check_cams(self, row):
        inp, pre, post, tick = row["input"], row["before"], row["after"], row["post_tick"]
        red = inp["redirect"]
        # RAR query responds from the OLD records. New release marking takes
        # its specified history edge; allocation's current/previous window is
        # full-line, not merely hash equal.
        for lane, q in enumerate(inp["rar_queries"]):
            p = f"io_ldu_rarNukeQuery_{lane}_resp_"
            assert post[p + "valid"] == int(q["valid"])
            if q["valid"]:
                candidates = [r for r in self.rars if r["released"] and hash_line(r["q"]["paddr"]) == hash_line(q["paddr"]) and younger(r["q"]["rob"], q["rob"])]
                expected = bool(candidates)
                if post[p + "bits_nuke"] != int(expected):
                    assert expected and post[p + "bits_nuke"] == 0
                    record = candidates[0]
                    assert record["source"] == "previous" and record["allocation_tick"] - record["release_tick"] == 2
                    self.proofs.append(dict(issue="RAR-REL-001", tick=tick, query_lane=lane, allocation_tick=record["allocation_tick"],
                                            release_tick=record["release_tick"], old_query=q, younger_record=record["q"], actual_nuke=0, expected_nuke=1))
                self.counts["independent_rar_query_checks"] += 1
        revoked_raw = {rid for age, key in ((-1, "raw_revoke_last"), (0, "raw_revoke_older")) for lane, rid in enumerate(self.raw_history[age]) if rid is not None and inp[key][lane]}
        for lane, store in enumerate(inp["stores"]):
            if store["valid"]:
                candidates = [r["q"] for r in self.raws if r["rid"] not in revoked_raw and r["q"]["data_valid"] and younger(r["q"]["rob"], store["rob"]) and not flushed(r["q"], red) and match(r["q"], store)]
                self.jobs.append(dict(due=tick + 4, lane=lane, query=oldest(candidates), store=store, canceled=False))
        for job in self.jobs:
            job["canceled"] |= job["query"] is not None and flushed(job["query"], red)
        due = [job for job in self.jobs if job["due"] == tick]
        valid_jobs = []
        for lane in range(2):
            job = next((j for j in due if j["lane"] == lane), None)
            valid = job is not None and job["query"] is not None and not job["canceled"] and not job["store"]["tlb_miss"]
            p = f"io_nuke_rollback_{lane}_"
            assert post[p + "valid"] == int(valid)
            if valid:
                assert all(post[p + "bits_" + key] == value for key, value in payload(job["query"], job["store"]).items())
                self.counts["independent_raw_identity_rollbacks"] += 1
                valid_jobs.append(job)
        assert post["io_mdpTrain_valid"] == int(bool(valid_jobs))
        if valid_jobs:
            winner = next(job for job in valid_jobs if job["query"] == oldest([j["query"] for j in valid_jobs]))
            values = payload(winner["query"], winner["store"])
            for field in ("ftqIdx_value", "ftqOffset", "isRVC", "stFtqIdx_value", "stFtqOffset", "stIsRVC"):
                assert post["io_mdpTrain_bits_" + field] == values[field]
            self.counts["independent_mdp_training_checks"] += 1
        self.jobs = [job for job in self.jobs if job["due"] > tick]
        release = inp["release"]
        pending = {r["rid"] for r in self.rars if release["valid"] and hash_line(release["paddr"]) == hash_line(r["q"]["paddr"])}
        revoked_rar = {rid for age, key in ((-1, "rar_revoke_last"), (0, "rar_revoke_older")) for lane, rid in enumerate(self.rar_history[age]) if rid is not None and inp[key][lane]}
        self.rars = [r for r in self.rars if r["position"] > self.head and not flushed(r["q"], red) and r["rid"] not in revoked_rar]
        self.raws = [r for r in self.raws if 0 < (sq_raw(r["q"]["sq"]) - sq_raw(inp["address_ready"])) % 256 < 128 and not flushed(r["q"], red) and r["rid"] not in revoked_raw]
        rh, wh = [], []
        for lane in range(3):
            q = inp["rar_queries"][lane]
            distance = (lq(q["lq"]) - self.head) % 240
            if q["valid"] and 0 < distance < 120 and not flushed(q, red) and pre[f"io_ldu_rarNukeQuery_{lane}_req_ready"]:
                self.record_sequence += 1
                now = release["valid"] and release["paddr"] // 64 == q["paddr"] // 64
                previous = self.previous_release is not None and self.previous_release["paddr"] // 64 == q["paddr"] // 64
                source = "nc" if q["nc"] else "current" if q["data_valid"] and now else "previous" if q["data_valid"] and previous else "none"
                record = dict(rid=self.record_sequence, q=q, position=self.head + distance, source=source, released=source != "none",
                              allocation_tick=tick, release_tick=self.previous_release["tick"] if source == "previous" else tick)
                self.rars.append(record); rh.append(record["rid"])
            else:
                rh.append(None)
            q = inp["raw_queries"][lane]
            distance = (sq_raw(q["sq"]) - sq_raw(inp["address_ready"])) % 256
            if q["valid"] and 0 < distance < 128 and not flushed(q, red) and pre[f"io_ldu_rawNukeQuery_{lane}_req_ready"]:
                self.record_sequence += 1
                self.raws.append(dict(rid=self.record_sequence, q=q)); wh.append(self.record_sequence)
            else:
                wh.append(None)
        for record in self.rars:
            if record["rid"] in self.rar_release:
                record["released"] = True
        self.rar_release = pending
        self.previous_release = dict(paddr=release["paddr"], tick=tick) if release["valid"] else None
        self.rar_history.append(tuple(rh)); self.raw_history.append(tuple(wh))
        self.counts["peak_simultaneous_rar_records"] = max(self.counts["peak_simultaneous_rar_records"], len(self.rars))
        self.counts["peak_simultaneous_raw_records"] = max(self.counts["peak_simultaneous_raw_records"], len(self.raws))

    def step(self, row):
        inp, pre, post, tick = row["input"], row["before"], row["after"], row["post_tick"]
        if inp["reset"]:
            self.reset(tick)
            return
        self.check_cams(row)
        for bank in range(3):
            p = f"io_replay_{bank}_"
            if not pre[p + "valid"] or not inp["replay_ready"][bank]:
                continue
            owner = self.owner(dict(flag=pre[p + "bits_uop_lqIdx_flag"], value=pre[p + "bits_uop_lqIdx_value"]))
            request, uid = owner["load"]["execution"], owner["uid"]
            assert uid not in self.issued and owner["completed_tick"] is None
            u = request["uop"]
            size = request["aligned_type"] if request["vector"] else u["operation"] // 2 % 8
            scalar_mask = sum(1 << byte for byte in range(16) if request["vaddr"] % 16 <= byte < request["vaddr"] % 16 + (1 << (size % 4)))
            fields = dict(vaddr=request["vaddr"], fullva=request["vaddr"], mask=request["mask"] if request["vector"] else scalar_mask, size=size,
                          uop_fuOpType=u["operation"], uop_pdest=u["destination"], uop_perfDebugInfo_runahead_checkpoint_id=u["checkpoint"],
                          uop_ftqOffset=u["offset"], uop_isRVC=int(u["rvc"]), uop_ftqPtr_flag=int(u["ftq"]["flag"]), uop_ftqPtr_value=u["ftq"]["value"])
            fields.update({"uop_robIdx_" + port: int(owner["rob"][field]) for port, field in (("flag", "flag"), ("value", "value"), ("isFormer", "former"))})
            for port, field in (("rfWen", "integer_write"), ("fpWen", "fp_write"), ("vecWen", "vector_write"), ("v0Wen", "v0_write"),
                                ("storeSetHit", "store_set_hit"), ("loadWaitBit", "load_wait"), ("loadWaitStrict", "strict")):
                fields["uop_" + port] = int(u[field])
            assert all(pre[p + "bits_" + key] == value for key, value in fields.items())
            slot = pre[p + "bits_replayQueueIdx"]
            assert slot < 120 and slot % 3 == bank and slot not in self.issued.values()
            self.issued[uid] = slot
            self.rp_pairs.add((slot, owner["replay_input_lane"]))
            self.events.append(dict(event="replay_fire", tick=tick, uid=uid, slot=slot, bank=bank))
            self.counts["actual_replay_handshakes"] += 1
        for lane, load in enumerate(inp["loads"]):
            request = load["execution"]
            if not request["valid"]:
                continue
            owner = self.owner(request["uop"]["lq"])
            assert owner["rob"] == request["uop"]["rob"] and owner["completed_tick"] is None
            if request["replay_feedback"]:
                assert self.issued.pop(owner["uid"]) == request["slot"]
                self.counts["actual_replay_feedbacks"] += 1
            elif request["need_replay"]:
                owner.setdefault("replay_input_lane", lane)
            if request["need_replay"]:
                self.causes.add(request["causes"].bit_length() - 1)
            owner["load"] = load
            if not request["need_replay"] and load["update_address"]:
                owner["completed_tick"] = tick
        if post["io_lqDeq_valid"]:
            count = post["io_lqDeq_bits"]
            assert 1 <= count <= 8
            for pos in range(self.head, self.head + count):
                owner = self.live.pop(pos)
                uid = owner["uid"]
                assert uid not in self.done and owner["completed_tick"] is not None and owner["completed_tick"] + 4 <= tick
                self.done.add(uid); self.lq_slots.add(pos % 120)
                self.events.append(dict(event="complete", tick=tick, uid=uid, position=pos, completed_input_tick=owner["completed_tick"]))
                for old in self.cancelled | self.aborted:
                    if uid > old and self.all[old]["position"] % 120 == pos % 120:
                        self.reuse.setdefault(old, dict(new_uid=uid, tick=tick, slot=pos % 120))
            self.head += count
        for lane, dispatch in enumerate(inp["dispatch"]):
            if not dispatch["valid"]:
                continue
            assert not inp["redirect"]["valid"] and lq(dispatch["start"]) == self.tail % 240
            for _ in range(dispatch["flows"]):
                self.sequence += 1
                owner = dict(uid=self.sequence, position=self.tail, rob=dispatch["rob"], dispatch_lane=lane, completed_tick=None)
                self.live[self.tail] = self.all[self.sequence] = owner
                self.tail += 1
        if pre["io_uncache_req_valid"] and inp["bus"]["ready"]:
            owner = next(o for o in self.live.values() if "load" in o and o["load"]["paddr"] == pre["io_uncache_req_bits_addr"])
            mid = pre["io_uncache_req_bits_id"]
            assert mid < 16 and mid not in self.bus
            self.bus[mid] = dict(uid=owner["uid"], sid=None, nc=owner["load"]["execution"]["nc"])
            self.entry_types.add((mid, bool(self.bus[mid]["nc"])))
            self.counts["actual_bus_requests"] += 1
        if inp["bus"]["ack"]:
            self.bus[inp["bus"]["mid"]]["sid"] = inp["bus"]["sid"]
        if inp["bus"]["response"]:
            hits = [mid for mid, job in self.bus.items() if job["sid"] == inp["bus"]["response_id"]]
            assert hits
            for mid in hits:
                job = self.bus.pop(mid)
                if job["uid"] not in self.cancelled:
                    assert job["uid"] not in self.responses
                    self.responses[job["uid"]] = dict(uid=job["uid"], tick=tick, sid=inp["bus"]["response_id"],
                                                      data=inp["bus"]["data"], error=int(inp["bus"]["error"]), nderr=int(inp["bus"]["nderr"]))
                else:
                    self.counts["cancelled_external_responses_safely_returned"] += 1
        for lane, query in enumerate(inp["bypass"]):
            p = f"io_bypass_{lane}_"
            if not query["valid"] or not post[p + "s1Resp_valid"]:
                continue
            owner = self.owner(query["lq"])
            response = self.responses.pop(owner["uid"])
            assert post[p + "s1Resp_bits_paddr"] == owner["load"]["paddr"]
            self.expected_data.append(dict(due=tick + 2, lane=lane, **response))
            self.counts["actual_bypass_consumptions"] += 1
        for response in self.expected_data:
            if response["due"] == tick:
                p = f"io_bypass_{response['lane']}_s2Resp_"
                assert post[p + "valid"] and post[p + "bits_data"] == response["data"] * ((1 << 64) + 1)
                assert post[p + "bits_derr"] == response["error"] and post[p + "bits_nderr"] == response["nderr"]
                self.counts["independently_checked_bypass_data_and_errors"] += 1
        if inp["redirect"]["valid"]:
            doomed = [o for o in self.live.values() if flushed(o, inp["redirect"])]
            positions = sorted(o["position"] for o in doomed)
            assert not positions or positions == list(range(positions[0], self.tail))
            self.recovery.append(self.tail - len(doomed))
            for owner in doomed:
                uid = owner["uid"]
                self.cancelled.add(uid); self.live.pop(owner["position"])
                self.issued.pop(uid, None); self.responses.pop(uid, None)
        if post["io_lqRedirect_valid"]:
            expected = max(self.head, self.recovery.popleft())
            assert 120 * post["io_lqRedirect_bits_flag"] + post["io_lqRedirect_bits_value"] == expected % 240
            self.tail = expected
            self.counts["actual_recovery_responses"] += 1
        assert 0 <= self.tail - self.head <= 120
        self.done_at[tick] = frozenset(self.done)


def prove_failure(replay, rows, bad):
    final, tick = rows[-1], rows[-1]["post_tick"]
    inp, post = final["input"], final["after"]
    pins = {d["pin"] for d in bad}
    if all("rarNukeQuery" in pin and "nuke" in pin for pin in pins):
        proof = [p for p in replay.proofs if p["tick"] == tick]
        assert proof
        return proof
    if pins == {"io_replay_0_valid"}:
        assert post["io_replay_0_valid"] and post["io_replay_0_bits_uop_loadWaitStrict"]
        original = next(load["execution"] for row in rows for load in row["input"]["loads"]
                        if load["execution"]["valid"] and load["execution"]["need_replay"] and load["execution"]["uop"]["strict"])
        block = original["address_sq"]
        assert original["causes"] == 4 and not inp["sq_empty"] and sq_raw(inp["address_ready"]) <= sq_raw(block)
        assert inp["address_bits"] >> block["value"] & 1
        assert not any(w["valid"] and w["sq"] == block for row in rows[-3:] for w in row["input"]["address_wakeups"])
        dirty = [(r["post_tick"], lane) for r in rows for lane, load in enumerate(r["input"]["loads"])
                 if not load["execution"]["valid"] and load["execution"]["replay_feedback"] and not load["execution"]["uop"]["strict"]]
        assert dirty
        return [dict(issue="LRQ-STRICT-001", tick=tick, invalid_feedback_edges=dirty, original_request=original,
                     actual_replay_valid=1, expected_blocked=True)]
    assert pins <= {"io_exceptionInfo_bits_exceptionVec_19", "io_exceptionInfo_bits_exceptionVec_5"} and pins
    lane = next(i for i, query in enumerate(inp["bypass"]) if query["valid"])
    owner = replay.owner(inp["bypass"][lane]["lq"])
    original = next(packet for packet in replay.expected_data if packet["uid"] == owner["uid"] and packet["due"] == tick + 2)
    other = [packet for packet in replay.responses.values() if packet["uid"] != owner["uid"] and packet["sid"] == original["sid"] and packet["tick"] > original["tick"]]
    assert other and post["io_exceptionInfo_valid"]
    new = other[-1]
    assert post["io_exceptionInfo_bits_robIdx_value"] == owner["rob"]["value"]
    assert post["io_exceptionInfo_bits_exceptionVec_19"] == new["error"] != original["error"]
    assert post["io_exceptionInfo_bits_exceptionVec_5"] == new["nderr"] != original["nderr"]
    return [dict(issue="LQU-SID-001", tick=tick, old_uid=owner["uid"], old_response=original,
                 new_response=new, actual_old_faults=dict(error=new["error"], nderr=new["nderr"]),
                 violation="returned SID's later response overwrote an unconsumed older load's fault report")]


def audit(name):
    run = ROOT / "results" / name
    manifest, source, nodes = verify_common(run)
    assert all(node.startswith("tests/load_queue/") for node in nodes)
    counts, reports, seen, issues = Counter(), [], set(), Counter()
    pairs, causes, types, slots = set(), set(), set(), set()
    for path in sorted((run / "cases").rglob("load_queue.jsonl")):
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        node, replay, last, bad = rows[0]["nodeid"], Replay(), None, []
        assert node in nodes and node not in seen
        seen.add(node)
        for index, row in enumerate(rows):
            tick = row["post_tick"]
            assert row["pre_tick"] + 1 == tick and (last is None or last + 2 == tick) and row["nodeid"] == node
            assert row["pins"] == row["post_pins"] and len(row["pins"]) == 622 and len(row["before"]) == len(row["after"]) == 266
            difference = differences(row)
            assert row["checked"] == (not difference), (node, tick, row.get("error"))
            if difference:
                assert index == len(rows) - 1 and nodes[node]
                bad.extend(difference)
            replay.step(row)
            last = tick
        assert bool(bad) == nodes[node]
        proof = prove_failure(replay, rows, bad) if bad else []
        assert bool(proof) == nodes[node] and len({p["issue"] for p in proof}) <= 1
        if proof:
            issues[proof[0]["issue"]] += 1
        else:
            assert not replay.live and not replay.issued and not replay.bus and not replay.responses and not replay.recovery
            assert all(packet["due"] <= last for packet in replay.expected_data)
        for event in map(json.loads, path.with_name("lq_actor.jsonl").read_text().splitlines()):
            kind = event["event"]
            if kind in ("complete", "replay_fire"):
                assert {key: value for key, value in event.items() if key != "nodeid"} in replay.events
            elif kind == "checked":
                done = replay.done_at[event["tick"]]
                assert set(event["uids"]) <= done and event["completed"] == sorted(done)
            elif kind == "reuse_completed":
                witness = replay.reuse[event["old_uid"]]
                assert witness == dict(new_uid=event["new_uid"], tick=event["tick"], slot=event["slot"])
            elif kind == "reuse_checked":
                assert all(int(old) in replay.reuse and replay.reuse[int(old)]["new_uid"] == new for old, new in event["witnesses"].items())
            elif kind == "allocate":
                actual = replay.all[event["owner"]["uid"]]
                assert actual["position"] == event["owner"]["position"] and actual["rob"] == event["owner"]["rob"]
        retained = {owner["uid"] for owner in replay.live.values()}
        assert len(replay.all) == len(replay.done) + len(replay.cancelled) + len(replay.aborted) + len(retained)
        assert not (replay.done & (replay.cancelled | replay.aborted)) and not (replay.cancelled & replay.aborted)
        if not nodes[node]:
            assert replay.cancelled | replay.aborted <= set(replay.reuse), (node, "missing same-slot actual new UID completion")
        counts.update(replay.counts)
        counts.update(records=len(rows), allocated=len(replay.all), completed=len(replay.done), cancelled=len(replay.cancelled),
                      reset_aborted=len(replay.aborted), failure_retained=len(retained), same_slot_new_uid_completed=len(replay.reuse))
        pairs.update(replay.rp_pairs); causes.update(replay.causes); types.update(replay.entry_types); slots.update(replay.lq_slots)
        reports.append(dict(nodeid=node, journal=str(path.relative_to(run)), sha256=sha(path), records=len(rows), differences=bad,
                            independent_failures=proof, same_slot_reuse=replay.reuse))
    assert seen == set(nodes) and sum(issues.values()) == manifest["tests"].get("FAIL", 0)
    dest = run / "evidence-auditors" / Path(__file__).name
    dest.parent.mkdir(exist_ok=True)
    if dest.exists():
        assert sha(dest) == sha(Path(__file__))
    else:
        shutil.copy2(Path(__file__), dest)
    report = dict(run=name, status="full_public_uid_cam_recovery_bus_and_real_failure_audit", dut_acceptance="NOT_PASS" if issues else "scoped_PASS_not_complete_LSQ",
                  tests=manifest["tests"], counts=dict(counts), failure_cases_by_issue=dict(issues), actual_replay_slot_input_lane_pairs=len(pairs),
                  actual_causes=sorted(causes), actual_entry_type_pairs=len(types), completed_physical_lq_slots=len(slots),
                  snapshot_files=len(source), manifest_sha256=sha(run / "execution/manifest.json"), auditor_sha256=sha(dest), cases=reports,
                  limits="No DUT/reference imports or internal reads. RAR hash/age and RAW PA/mask/age snapshots independently recomputed; not a second arbitrary arbiter implementation. Full-slot RAR varying-head-PA probes are UNIT-INTERFACE stress, not one software load's architectural path. Every failed case needs a public semantic counterexample. Evidence is not whole-LSQ acceptance or branch/expression exhaustiveness.")
    out = run / "history-audit-v3.json"
    if out.exists():
        assert json.loads(out.read_text()) == report
    else:
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
