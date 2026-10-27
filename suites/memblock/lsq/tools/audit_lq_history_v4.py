#!/usr/bin/env python3
"""Versioned public-history audit: real max peaks and buffered cancelled bus.

Keeps v3 and every earlier result unchanged. Reuses ONLY independent audit
helpers, not verification-domain models, DUT reads or an issue whitelist.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_lq_history_v3 import Replay as CamAudit, differences, lq, prove_failure
from audit_raw_trace import flushed
from audit_sq_initial import ROOT, sha, verify_common


def pointer_fields(pointer, kind):
    names = {"rob": (("flag", "flag"), ("value", "value"), ("isFormer", "former")),
             "lq": (("flag", "flag"), ("value", "value")),
             "sq": (("first_flag", "first"), ("second_flag", "second"), ("value", "value"))}
    return {pin: int(pointer[field]) for pin, field in names[kind]}


def bind_identity_pins(row):
    """Bind ledger/semantic identity fields independently to sampled raw pins.

    The separate codec audit covers all 622 fields. This additional boundary
    never trusts an actor's IDs, a reference's internal_feedback or change log.
    """
    inp, pins, checks = row["input"], row["pins"], {}
    def fields(prefix, values):
        checks.update({prefix + key: int(value) for key, value in values.items()})
    def ptr(prefix, value, kind):
        fields(prefix, pointer_fields(value, kind))
    fields("", {"reset": inp["reset"], "io_redirect_valid": inp["redirect"]["valid"],
                "io_redirect_bits_level": inp["redirect"]["flush_self"]})
    ptr("io_redirect_bits_robIdx_", inp["redirect"]["rob"], "rob")
    for lane, dispatch in enumerate(inp["dispatch"]):
        prefix = f"io_enq_req_{lane}_"
        fields(prefix, {"valid": dispatch["valid"], "bits_numLsElem": dispatch["flows"]})
        ptr(prefix + "bits_robIdx_", dispatch["rob"], "rob")
        ptr(prefix + "bits_lqIdx_", dispatch["start"], "lq")
    for lane, load in enumerate(inp["loads"]):
        prefix, request = f"io_ldu_ldin_{lane}_", load["execution"]
        fields(prefix, {"valid": request["valid"], "bits_paddr": load["paddr"], "bits_fullva": load["fullva"],
                       "bits_gpaddr": load["gpaddr"], "bits_updateAddrValid": load["update_address"],
                       "bits_mmio": load["mmio"], "bits_nc": request["nc"], "bits_vaddr": request["vaddr"],
                       "bits_isLoadReplay": request["replay_feedback"], "bits_schedIndex": request["slot"],
                       "bits_rep_info_need_rep": request["need_replay"], "bits_uop_loadWaitStrict": request["uop"]["strict"]})
        ptr(prefix + "bits_uop_robIdx_", request["uop"]["rob"], "rob")
        ptr(prefix + "bits_uop_lqIdx_", request["uop"]["lq"], "lq")
        ptr(prefix + "bits_uop_sqIdx_", request["uop"]["sq"], "sq")
        for bit in range(13):
            fields(prefix, {f"bits_rep_info_cause_{bit}": request["causes"] >> bit & 1})
    for lane, query in enumerate(inp["bypass"]):
        prefix = f"io_bypass_{lane}_s0Req_"
        fields(prefix, {"valid": query["valid"], "bits_isNCReplay": query["nc"], "bits_isMMIOReplay": query["mmio"]})
        ptr(prefix + "bits_lqIdx_", query["lq"], "lq")
    bus = inp["bus"]
    fields("io_uncache_", {"req_ready": bus["ready"], "idResp_valid": bus["ack"], "idResp_bits_mid": bus["mid"],
                           "idResp_bits_sid": bus["sid"], "resp_valid": bus["response"], "resp_bits_id": bus["response_id"],
                           "resp_bits_data": bus["data"], "resp_bits_error": bus["error"], "resp_bits_nderr": bus["nderr"]})
    assert all(pins[pin] == value for pin, value in checks.items())
    return len(checks)


class PublicAudit(CamAudit):
    def __init__(self):
        super().__init__()
        self.bus_requested, self.successful_bypass_tuples = set(), set()
        self.pending_exception = []

    def step(self, row):
        inp, pre, post, tick = row["input"], row["before"], row["after"], row["post_tick"]
        self.counts["raw_identity_pin_bindings"] += bind_identity_pins(row)
        if inp["reset"]:
            self.reset(tick)
            return
        self.check_cams(row)
        assert len(self.rars) <= 96 and len(self.raws) <= 56
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
            fields.update({"uop_robIdx_" + key: value for key, value in pointer_fields(owner["rob"], "rob").items()})
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
            # An entry may have fired to the non-flushing elastic register
            # BEFORE redirect, yet the public bus accepts it AFTER redirect.
            hits = [o for o in self.all.values() if "load" in o and o["load"]["paddr"] == pre["io_uncache_req_bits_addr"]]
            assert len(hits) == 1
            owner, mid = hits[0], pre["io_uncache_req_bits_id"]
            uid, load = owner["uid"], owner["load"]
            assert uid not in self.bus_requested and uid not in self.done and uid not in self.aborted and mid < 16 and mid not in self.bus
            assert owner["position"] in self.live or uid in self.cancelled
            fields = dict(cmd=0, addr=load["paddr"], vaddr=load["execution"]["vaddr"], nc=int(load["execution"]["nc"]),
                          memBackTypeMM=int(load["memory_backed"]), mask=load["execution"]["mask"] >> (8 * (load["paddr"] // 8 % 2)) & 255)
            fields.update({"robIdx_" + key: value for key, value in pointer_fields(owner["rob"], "rob").items()})
            assert all(pre["io_uncache_req_bits_" + key] == value for key, value in fields.items())
            self.bus[mid] = dict(uid=uid, sid=None, nc=load["execution"]["nc"], mid=mid)
            self.bus_requested.add(uid); self.entry_types.add((mid, bool(load["execution"]["nc"])))
            self.counts["actual_bus_requests"] += 1
            self.counts["cancelled_buffered_requests_accepted_after_redirect"] += int(uid in self.cancelled)
        if inp["bus"]["ack"]:
            job = self.bus[inp["bus"]["mid"]]
            assert job["sid"] is None and not any(j["sid"] == inp["bus"]["sid"] for j in self.bus.values())
            job["sid"] = inp["bus"]["sid"]
        if inp["bus"]["response"]:
            hits = [mid for mid, job in self.bus.items() if job["sid"] == inp["bus"]["response_id"]]
            assert len(hits) == 1, "a returned SID has one outstanding external owner, not stale LDU owners"
            job = self.bus.pop(hits[0])
            if job["uid"] not in self.cancelled:
                assert job["uid"] not in self.responses
                self.responses[job["uid"]] = dict(**job, tick=tick, data=inp["bus"]["data"],
                                                  error=int(inp["bus"]["error"]), nderr=int(inp["bus"]["nderr"]))
            else:
                self.counts["cancelled_external_responses_safely_returned"] += 1
        for lane, query in enumerate(inp["bypass"]):
            p = f"io_bypass_{lane}_"
            if not query["valid"] or not post[p + "s1Resp_valid"]:
                continue
            owner = self.owner(query["lq"])
            response = self.responses.pop(owner["uid"])
            assert post[p + "s1Resp_bits_paddr"] == owner["load"]["paddr"]
            assert bool(query["nc"]) == bool(response["nc"]) and bool(query["mmio"]) != bool(response["nc"])
            self.expected_data.append(dict(due=tick + 2, lane=lane, **response))
            self.counts["actual_bypass_consumptions"] += 1
        for response in self.expected_data:
            if response["due"] == tick:
                p = f"io_bypass_{response['lane']}_s2Resp_"
                assert post[p + "valid"] and post[p + "bits_data"] == response["data"] * ((1 << 64) + 1)
                assert post[p + "bits_derr"] == response["error"] and post[p + "bits_nderr"] == response["nderr"]
                self.counts["independently_checked_bypass_data_and_errors"] += 1
                self.successful_bypass_tuples.add((response["mid"], bool(response["nc"]), response["lane"]))
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


def audit(name):
    run = ROOT / "results" / name
    manifest, source, nodes = verify_common(run)
    assert all(node.startswith("tests/load_queue/") for node in nodes)
    counts, peaks, reports, seen, issues = Counter(), Counter(), [], set(), Counter()
    pairs, causes, types, slots, bypass_tuples = set(), set(), set(), set(), set()
    for path in sorted((run / "cases").rglob("load_queue.jsonl")):
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        node, replay, last, bad = rows[0]["nodeid"], PublicAudit(), None, []
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
        assert bool(proof) == nodes[node]
        if proof:
            assert len({p["issue"] for p in proof}) == 1
            issues[proof[0]["issue"]] += 1
        else:
            assert not replay.live and not replay.issued and not replay.bus and not replay.responses and not replay.recovery
            assert all(packet["due"] <= last for packet in replay.expected_data)
        events = [json.loads(line) for line in path.with_name("lq_actor.jsonl").read_text().splitlines()]
        for event in events:
            kind = event["event"]
            if kind in ("complete", "replay_fire"):
                assert {key: value for key, value in event.items() if key != "nodeid"} in replay.events
            elif kind == "checked":
                done = replay.done_at[event["tick"]]
                assert set(event["uids"]) <= done and event["completed"] == sorted(done)
            elif kind == "reuse_completed":
                assert replay.reuse[event["old_uid"]] == dict(new_uid=event["new_uid"], tick=event["tick"], slot=event["slot"])
            elif kind == "reuse_checked":
                assert all(int(old) in replay.reuse and replay.reuse[int(old)]["new_uid"] == new for old, new in event["witnesses"].items())
            elif kind == "allocate":
                actual = replay.all[event["owner"]["uid"]]
                assert actual["position"] == event["owner"]["position"] and actual["rob"] == event["owner"]["rob"]
        retained = {owner["uid"] for owner in replay.live.values()}
        assert len(replay.all) == len(replay.done) + len(replay.cancelled) + len(replay.aborted) + len(retained)
        assert not (replay.done & (replay.cancelled | replay.aborted)) and not (replay.cancelled & replay.aborted)
        if not nodes[node]:
            assert (replay.cancelled | replay.aborted) <= set(replay.reuse)
        for key, value in replay.counts.items():
            if key.startswith("peak_simultaneous_"):
                peaks[key] = max(peaks[key], value)
            else:
                counts[key] += value
        counts.update(records=len(rows), allocated=len(replay.all), completed=len(replay.done), cancelled=len(replay.cancelled),
                      reset_aborted=len(replay.aborted), failure_retained=len(retained), same_slot_new_uid_completed=len(replay.reuse))
        pairs.update(replay.rp_pairs); causes.update(replay.causes); types.update(replay.entry_types); slots.update(replay.lq_slots)
        bypass_tuples.update(replay.successful_bypass_tuples)
        reports.append(dict(nodeid=node, journal=str(path.relative_to(run)), sha256=sha(path), records=len(rows), differences=bad,
                            independent_failures=proof, same_slot_reuse=replay.reuse,
                            per_case_peaks={key: value for key, value in replay.counts.items() if key.startswith("peak_simultaneous_")}))
    assert seen == set(nodes) and sum(issues.values()) == manifest["tests"].get("FAIL", 0)
    dependencies = (Path(__file__), ROOT / "tools/audit_lq_history_v3.py", ROOT / "tools/audit_lq_history.py",
                    ROOT / "tools/audit_raw_trace.py", ROOT / "tools/audit_sq_initial.py", ROOT / "tools/audit_psq_initial.py")
    auditor_hashes = {}
    for path in dependencies:
        dest = run / "evidence-auditors" / path.name
        dest.parent.mkdir(exist_ok=True)
        if dest.exists():
            assert sha(dest) == sha(path)
        else:
            shutil.copy2(path, dest)
        auditor_hashes[path.name] = sha(dest)
    report = dict(run=name, status="public_uid_cam_buffered_cancel_bus_byte_and_failure_audited_v4", dut_acceptance="NOT_PASS" if issues else "scoped_PASS_not_complete_LSQ",
                  tests=manifest["tests"], counts=dict(counts), actual_single_case_peaks=dict(peaks), failure_cases_by_issue=dict(issues),
                  actual_replay_slot_input_lane_pairs=len(pairs), actual_causes=sorted(causes), actual_entry_type_pairs=len(types),
                  completed_physical_lq_slots=len(slots), successful_entry_type_bypass_tuples=sorted(bypass_tuples),
                  snapshot_files=len(source), manifest_sha256=sha(run / "execution/manifest.json"), auditor_sha256=auditor_hashes, cases=reports,
                  limits="Only public pins/input history, no DUT or domain reference imports. v3 peak sum is retained as historical error; v4 uses max and per-case peaks. Buffered old requests may be accepted after redirect, but need original identity and unique response. RAR varying-PA full-slot probes remain UNIT-INTERFACE. No whole-LSQ, arbitrary configuration or branch/expression exhaustiveness claim.")
    out = run / "history-audit-v4.json"
    if out.exists():
        assert json.loads(out.read_text()) == report
    else:
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key not in ("cases", "successful_entry_type_bypass_tuples")}, indent=2, ensure_ascii=False))
    print("successful entry x type x bypass tuples:", len(bypass_tuples))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
