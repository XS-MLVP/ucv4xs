#!/usr/bin/env python3
"""Eight corrected mixed prefixes. Preserve v1 and explicit its slot-ledger bug.

A Replay owner keeps its slot across need_rep feedback even while no grant is
outstanding. Redirect frees that lease by original UID, not by grant!=None.
No DUT/reference/actor/known-issues oracle. All unfinished work stays visible.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_lsq_mixed_history_v1 import Timeline
from audit_lsq_bus_v2 import pointer, sq
from audit_lsq_population_v1 import events, paths_by_node, replay_metadata, validate_row
from audit_sq_initial import ROOT, sha, verify_common


def inspect(path,*,outer_failure=None):
    rows = list(events(path))
    program, stores, loads, attempts, slots, bysq, bylq, valid = [], [], [], [], {}, {}, {}, {}
    sh = st = lh = lt = uid = 0
    prev, pending_s2, qpipe, bpipe, cache, rec = None, [], [None]*3, [None]*3, None, None
    timeline, counts, peaks, causes, violations, recoveries = Timeline(), Counter(), Counter(), Counter(), [], []

    def live(s):
        return not s["complete"] and not s["cancelled"]

    def owner(rob, kind):
        order = timeline.decode(rob)
        found = [s for s in program if s["order"] == order and s["kind"] == kind and not s["rob_cancelled"]]
        assert len(found) == 1
        return found[0]

    def check(condition, obligation, **fields):
        if not condition:
            violations.append(dict(tick=tick, obligation=obligation, **fields))

    for index, row in enumerate(rows):
        validate_row(row, prev, False)
        i, pre, post, tick = row["input"], row["before"], row["after"], row["post_tick"]
        counts["raw_records"] += 1
        assert row["checked"] or index == len(rows)-1
        if i["reset"]:
            assert not program
            prev = row
            continue
        assert not i["sbuffer_ready"][1] or i["sbuffer_ready"][0]
        assert pointer(pre, "io_sqDeqPtr_") == sh % 256
        head = timeline.decode(i["pending"], True)
        red = i["redirect"]
        cut = timeline.decode(red["rob"]) if red["valid"] else None
        assert cut is None or cut >= head and red["flush_self"] and not any(d["valid"] for d in i["dispatch"])
        for s in program:
            if s["rob_cancelled"] or s["order"] >= head:
                continue
            assert not s["fault"]
            if s["kind"] == "load":
                assert s["sent"]
            elif s.get("memory") == 1:
                assert s["attempts"] and s["attempts"][-1]["sid"] is not None
            elif s.get("cbo") is not None or s.get("memory", 0) & 2:
                assert s["wb"] is not None
            else:
                assert s.get("s2") and "data" in s
        prepared = []
        for p in range(lh, lh+8):
            s = valid.get(p)
            if s is None or not s["sent"] or cut is not None and s["order"] >= cut:
                break
            prepared.append(s)
        for d in i["dispatch"]:
            if not d["valid"]:
                continue
            assert rec is None and not pre["io_toLsqEnqCtrl_lqRecoverStall"] and not pre["io_toLsqEnqCtrl_sqRecoverStall"] and d["flows"] == 1 and d["need_alloc"] in (1, 2)
            order = timeline.decode(d["rob"], True)
            assert order >= head and not any(s["order"] >= order and not s["rob_cancelled"] for s in program)
            uid += 1
            s = dict(uid=uid, order=order, rob=d["rob"], kind="load" if d["need_alloc"] == 1 else "store", complete=False,
                     cancelled=False, rob_cancelled=False, fault=False, attempts=[], grant=None, consumed=set(), wb=None, sent=False)
            program.append(s)
            if s["kind"] == "store":
                s["pos"] = st
                assert st not in bysq or not live(bysq[st])
                bysq[st] = s
                stores.append(s)
                st += 1
                assert sq(d["store_end"]) == st % 256
            else:
                assert 120*int(d["load_start"]["flag"])+d["load_start"]["value"] == lt % 240
                s.update(pos=lt, sq_bound=st)
                assert lt % 240 not in bylq or not live(bylq[lt % 240])
                bylq[lt % 240], valid[lt] = s, s
                loads.append(s)
                lt += 1
        for s, lane, last in pending_s2:
            a = i["attributes"][lane]
            assert a["last"] == last and not a["exception"]
            if last and live(s):
                s.update(s2=True, memory=int(a["nc"] or not a["memory"])+2*int(a["mmio"])+4*int(not a["memory"]))
        pending_s2 = []
        for lane, a in enumerate(i["addresses"]):
            if a["valid"]:
                p = sh+(a["slot"]-sh) % 64
                s = bysq[p]
                assert live(s) and s["rob"] == a["rob"] and p < min(st, sh+64) and a["vaddr"] % 4096 == a["paddr"] % 4096
                if not a["tlb_miss"]:
                    if "address" in s:
                        assert a["cross_word"] and a["last"] and not s.get("s2")
                    else:
                        s["address"] = a
                    s["cbo"] = a["fu_op"] >> 1 & 7 if a["fu_op"] & 1 else None
                    pending_s2.append((s, lane, a["last"]))
        for d in i["data"]:
            if d["valid"]:
                p = sh+(sq(d["sq"])-sh) % 256
                s = bysq[p]
                assert live(s) and p < sh+64 and "data" not in s
                s["data"] = d["data"]
        for lane, q in enumerate(i["rar_queries"]):
            if not q["valid"]:
                continue
            s = owner(q["rob"], "load")
            assert live(s) and 120*int(q["lq"]["flag"])+q["lq"]["value"] == s["pos"] % 240
            s.setdefault("pa", q["paddr"])
            assert s["pa"] == q["paddr"]
            if q["nc"]:
                assert s["attempts"][-1]["consumed"] and s["packet"]["execution"]["nc"]
            counts["original_rar_queries"] += 1
            if i["queries"][lane]["valid"]:
                r, f = i["raw_queries"][lane], i["queries"][lane]
                assert r["valid"] and r["rob"] == q["rob"] and r["paddr"] == q["paddr"] and r["data_valid"]
                assert sq(r["sq"]) == sq(f["sq"]) == s["sq_bound"] % 256 and f["vaddr"] % 4096 == q["paddr"] % 4096
                s.setdefault("va", f["vaddr"])
                assert s["va"] == f["vaddr"]
                counts["original_forward_raw_pairs"] += 1
        for lane, s in enumerate(qpipe):
            if s is not None:
                assert i["translations"][lane]["kill"] or i["translations"][lane]["paddr"] == s["pa"]
        qpipe = [owner(i["raw_queries"][lane]["rob"], "load") if q["valid"] else None for lane, q in enumerate(i["queries"])]
        for packet in i["loads"]:
            q, u = packet["execution"], packet["execution"]["uop"]
            if not q["valid"]:
                continue
            s = bylq[120*int(u["lq"]["flag"])+u["lq"]["value"]]
            assert live(s) and s["rob"] == u["rob"] and sq(u["sq"]) == s["sq_bound"] % 256
            assert packet["fullva"] == q["vaddr"] and packet["paddr"] % 4096 == q["vaddr"] % 4096
            s.setdefault("va", q["vaddr"])
            s.setdefault("pa", packet["paddr"])
            assert s["va"] == q["vaddr"] and s["pa"] == packet["paddr"]
            assert (u["operation"] >> 1 & 7) < 4 or q["vector"], "16-byte Load must carry vector metadata"
            if q["replay_feedback"]:
                assert s["grant"] == q["slot"] and slots[q["slot"]] is s and u == s["packet"]["execution"]["uop"]
                s["grant"] = None
                if not q["need_replay"]:
                    del slots[q["slot"]]
                counts["original_slot_feedbacks"] += 1
            else:
                assert "packet" not in s
                s["packet"] = packet
            if q["need_replay"]:
                assert q["causes"].bit_count() == 1 and q["causes"] < 1 << 12
                causes[str(q["causes"].bit_length()-1)] += 1
            else:
                assert packet["update_address"] and not s["sent"]
                if s["packet"]["execution"]["causes"] == 1:
                    assert s["attempts"][-1]["consumed"]
                s["sent"] = True
            s["last"] = packet
        if pre["io_uncache_req_valid"] and i["bus"]["ready"]:
            kind = "load" if pre["io_uncache_req_bits_cmd"] == 0 else "store"
            found = [s for s in program if s["kind"] == kind and (not s["rob_cancelled"] or kind == "load") and
                     s.get("pa", s.get("address", {}).get("paddr")) == pre["io_uncache_req_bits_addr"] and
                     (int(s["rob"]["flag"]), s["rob"]["value"], int(s["rob"]["former"])) ==
                     (pre["io_uncache_req_bits_robIdx_flag"], pre["io_uncache_req_bits_robIdx_value"], pre["io_uncache_req_bits_robIdx_isFormer"]) and
                     (not s["attempts"] or s["attempts"][-1]["consumed"])]
            assert len(found) == 1
            s = found[0]
            if kind == "store":
                assert s["order"] == head and s.get("s2") and "data" in s and pre["io_uncache_req_bits_data"] == s["data"] & ((1 << 64)-1)
            else:
                assert s["last"]["execution"]["causes"] == 1
            a = dict(id=len(attempts)+1, owner=s, mid=pre["io_uncache_req_bits_id"], sid=None, response=None, consumed=False)
            attempts.append(a)
            s["attempts"].append(a)
            counts[kind+"_bus_fires"] += 1
        bus = i["bus"]
        if bus["ack"]:
            found = [a for a in attempts if a["sid"] is None and a["mid"] == bus["mid"] and (a["owner"]["kind"] == "load") == bus["ack_to_load"]]
            assert len(found) == 1 and not any(a["sid"] == bus["sid"] and a["response"] is None for a in attempts)
            found[0]["sid"] = bus["sid"]
            counts["direction_acks"] += 1
        if bus["response"]:
            found = [a for a in attempts if a["response"] is None and a["sid"] == bus["response_id"] and (a["owner"]["kind"] == "load") == bus["response_to_load"]]
            assert len(found) == 1
            found[0]["response"] = dict(tick=tick, data=bus["data"], error=bus["error"], nderr=bus["nderr"])
            counts["sid_responses"] += 1
        for bank in range(3):
            p = f"io_replay_{bank}_"
            if pre[p+"valid"] and i["replay_ready"][bank]:
                s = bylq[120*pre[p+"bits_uop_lqIdx_flag"]+pre[p+"bits_uop_lqIdx_value"]]
                assert live(s) and s["grant"] is None and not s["sent"]
                replay_metadata(pre, p+"bits_", s["last"])
                slot = pre[p+"bits_replayQueueIdx"]
                assert slot % 3 == bank and (slot not in slots or slots[slot] is s)
                slots[slot], s["grant"] = s, slot
                counts["replay_grants"] += 1
        next_data, consuming = [None]*3, []
        for lane, q in enumerate(i["bypass"]):
            p = f"io_bypass_{lane}_"
            if q["valid"]:
                s = bylq[120*int(q["lq"]["flag"])+q["lq"]["value"]]
                assert live(s) and s["grant"] is not None and s["attempts"][-1]["response"] is not None
                a = s["attempts"][-1]
                assert not a["consumed"] and q["nc"] == s["packet"]["execution"]["nc"] and q["mmio"] == s["packet"]["mmio"]
                check(post[p+"s1Resp_valid"] and post[p+"s1Resp_bits_paddr"] == s["pa"], "original_bypass_PA", uid=s["uid"])
                next_data[lane] = (s, a)
                consuming.append((s, a))
            if bpipe[lane] is not None:
                s, a = bpipe[lane]
                r, actual = a["response"], post[p+"s2Resp_bits_data"]
                check(post[p+"s2Resp_valid"] and actual == r["data"]*((1 << 64)+1) and post[p+"s2Resp_bits_derr"] == int(r["error"]) and post[p+"s2Resp_bits_nderr"] == int(r["nderr"]),
                      "original_returned_SID_data_error_until_s2", uid=s["uid"], attempt=a["id"], mid=a["mid"], sid=a["sid"], original_response=r, actual_s2_data=actual,
                      later_same_SID_responses=[dict(attempt=b["id"], uid=b["owner"]["uid"], response=b["response"]) for b in attempts if b is not a and b["sid"] == a["sid"] and b["response"] and b["response"]["tick"] > r["tick"]])
                a["consumed"] = True
                s["fault"] |= r["error"] or r["nderr"]
                counts["data_error_consumptions"] += 1
        if consuming:
            s, a = min(consuming, key=lambda x: x[1]["mid"])
            r = a["response"]
            check(post["io_ldExceptionInfo_valid"] and post["io_ldExceptionInfo_bits_exceptionVec_19"] == int(r["error"]) and post["io_ldExceptionInfo_bits_exceptionVec_5"] == int(r["nderr"]),
                  "original_returned_SID_error_until_s1", uid=s["uid"], sid=a["sid"], original_response=r)
        bpipe = next_data
        if pre["io_cmoOpReq_valid"] and i["cache_ready"]:
            candidates = [s for s in stores if live(s) and s["order"] == head and s.get("cbo") is not None and s["address"]["paddr"] == pre["io_cmoOpReq_bits_address"]]
            assert len(candidates) == 1 and cache is None
            cache = candidates[0]
            assert cache.get("s2") and "data" in cache and cache["cbo"] == pre["io_cmoOpReq_bits_opcode"]
            counts["cache_requests"] += 1
        if i["cache_response"]:
            assert cache is not None and pre["io_cmoOpResp_ready"]
            cache["cache_response"] = dict(tick=tick, denied=i["cache_denied"], corrupt=i["cache_corrupt"])
            cache = None
            counts["cache_responses"] += 1
        for phase, pins in (("before", pre), ("after", post)):
            if pins["io_mmioStout_valid"]:
                rob = dict(flag=bool(pins["io_mmioStout_bits_robIdx_flag"]), value=pins["io_mmioStout_bits_robIdx_value"], former=bool(pins["io_mmioStout_bits_robIdx_isFormer"]))
                s = owner(rob, "store")
                assert s["order"] == head
                r = s.get("cache_response", dict(denied=False, corrupt=False))
                check(pins["io_mmioStout_bits_exceptionVec_7"] == int(r["denied"]) and pins["io_mmioStout_bits_exceptionVec_19"] == int(r["corrupt"]),
                      "original_Cache_errors_until_actual_WB_fire", uid=s["uid"], phase=phase, response=r, ready=i["writeback_ready"])
                if phase == "before" and i["writeback_ready"]:
                    check(s.get("cbo") != 3 or bool(s["consumed"]), "zero_requires_own_actual_transfer", uid=s["uid"])
                    s["wb"], s["fault"] = tick, bool(r["denied"] or r["corrupt"])
                    counts["wb_fires"] += 1
        for lane in range(2):
            p = f"io_sbuffer_req_{lane}_"
            if pre[p+"valid"] and i["sbuffer_ready"][lane]:
                s = next(s for s in stores if live(s) and s.get("memory") == 0 and s.get("cbo") in (None, 3) and len(s["consumed"]) < (2 if s["address"]["cross_word"] else 1))
                part, a = len(s["consumed"]), s["address"]
                va, pa, mask, value = a["vaddr"]//16*16+16*part, a["paddr"]//16*16+16*part, 0, 0
                for byte in range(1 << a["size"]):
                    target = a["vaddr"]+byte-va
                    if 0 <= target < 16:
                        mask |= 1 << target
                        value |= ((s["data"] >> (8*byte)) & 255) << (8*target) if s.get("cbo") != 3 else 0
                bits = sum(255 << (8*b) for b in range(16) if mask >> b & 1)
                check(pre[p+"bits_vaddr"] == va and pre[p+"bits_addr"] == pa and pre[p+"bits_mask"] == mask and not ((pre[p+"bits_data"] ^ value) & bits) and pre[p+"bits_wline"] == int(s.get("cbo") == 3), "original_Sbuffer_PA_bytes_control", uid=s["uid"], part=part)
                assert s.get("s2") and "data" in s and s["order"] <= head
                s["consumed"].add(part)
                counts["sbuffer_fragment_fires"] += 1
        for s in prepared:
            del valid[s["pos"]]
        if cut is not None:
            assert rec is None
            victims = [s for s in program if not s["rob_cancelled"] and s["order"] >= cut]
            vl, vs = [s for s in valid.values() if s["order"] >= cut], [s for s in stores if live(s) and s["order"] >= cut]
            assert all(not s["consumed"] and not s["attempts"] for s in vs)
            rec = dict(cutoff=cut, lq_target=lt-len(vl), sq_target=min((s["pos"] for s in vs), default=st), lq=None, sq=None, tick=tick)
            recoveries.append(rec)
            for s in victims:
                s["rob_cancelled"] = True
                if live(s) and (s["kind"] == "store" or s in vl):
                    s["cancelled"] = True
                    if s["kind"] == "load":
                        valid.pop(s["pos"], None)
            # A slot lease survives feedback that requests another replay.
            # It ends on cancel even when no grant is currently outstanding.
            slots = {slot: s for slot, s in slots.items() if not s["cancelled"]}
            counts["shared_redirects"] += 1
        delta = (pointer(post, "io_sqDeqPtr_")-sh) % 256
        assert delta <= 2
        for pos in range(sh, sh+delta):
            s = bysq[pos]
            assert live(s) and s.get("s2") and "data" in s
            complete = len(s["consumed"]) == (2 if s["address"]["cross_word"] else 1) if s.get("cbo") is None and s.get("memory") == 0 else bool(s["attempts"] and s["attempts"][-1]["sid"] is not None) if s.get("memory") == 1 else s["wb"] is not None
            check(complete, "original_complete_SQ_prefix", uid=s["uid"])
            s["complete"] = True
        sh += delta
        if post["io_toLsqEnqCtrl_lqDeq_valid"]:
            for pos in range(lh, lh+post["io_toLsqEnqCtrl_lqDeq_bits"]):
                s = bylq[pos % 240]
                assert live(s) and s["sent"]
                s["complete"] = True
            lh += post["io_toLsqEnqCtrl_lqDeq_bits"]
        if rec is not None:
            if post["io_toLsqEnqCtrl_lqRedirectPtr_valid"]:
                lt = max(lh, rec["lq_target"])
                rec["lq"] = 120*post["io_toLsqEnqCtrl_lqRedirectPtr_bits_flag"]+post["io_toLsqEnqCtrl_lqRedirectPtr_bits_value"]
                assert rec["lq"] == lt % 240
            if post["io_toLsqEnqCtrl_sqRedirectPtr_valid"]:
                st = rec["sq_target"]
                rec["sq"] = pointer(post, "io_toLsqEnqCtrl_sqRedirectPtr_bits_")
                assert rec["sq"] == st % 256
            if rec["lq"] is not None and rec["sq"] is not None and not post["io_toLsqEnqCtrl_lqRecoverStall"] and not post["io_toLsqEnqCtrl_sqRecoverStall"]:
                rec["settled_tick"] = tick
                rec = None
                counts["both_recovery_responses_settled"] += 1
        assert 0 <= lt-lh <= 120 and 0 <= st-sh <= 128
        for key, value in (("lq", lt-lh), ("sq_virtual", st-sh), ("external_unreturned", sum(a["response"] is None for a in attempts))):
            peaks[key] = max(peaks[key], value)
        if violations:
            assert index == len(rows)-1, ("earlier original-UID semantic violation was not stopped", violations)
        prev = row
    if outer_failure is None:
        assert not rows[-1]["checked"] and "error" in rows[-1]
        terminal_error=rows[-1]["error"]
    else:
        assert "mixed fair drain left original obligations" in outer_failure
        assert all(row["checked"] and "error" not in row for row in rows)
        assert not violations
        terminal_error=outer_failure
    counts.update(allocated=len(program), completed=sum(s["complete"] for s in program), cancelled=sum(s["cancelled"] for s in program), failed_live=sum(live(s) for s in program),
                  pending_external_responses=sum(a["response"] is None for a in attempts), returned_unconsumed=sum(a["response"] is not None and not a["consumed"] and a["owner"]["kind"] == "load" for a in attempts))
    assert counts["allocated"] == counts["completed"]+counts["cancelled"]+counts["failed_live"]
    return dict(counts=dict(counts), peaks=dict(peaks), causes=dict(causes), independent_terminal_counterexamples=violations,
                terminal_tick=rows[-1]["post_tick"], terminal_runtime_error=terminal_error, recoveries=recoveries,
                terminal_scope="retained_cycle_failure_prefix" if outer_failure is None else "full_cycle_comparisons_but_outer_fair_bound_FAIL_no_completion_claim")


def audit(name):
    assert name == "lsq-seeded-mixed-03"
    run = ROOT/"results"/name
    manifest, source, nodes = verify_common(run)
    assert manifest["tests"] == {"FAIL": 8} and len(source) == 357
    paths = paths_by_node(run)
    assert set(paths) == set(nodes) and len(nodes) == 8 and all(nodes.values())
    counts, cases = Counter(), []
    for node, path in sorted(paths.items()):
        detail = inspect(path)
        counts.update(detail["counts"])
        cases.append(dict(nodeid=node, journal=str(path.relative_to(run)), sha256=sha(path), **detail))
    dest = run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    files = (Path(__file__), ROOT/"tools/audit_lsq_mixed_history_v1.py", ROOT/"tools/audit_lsq_population_v1.py", ROOT/"tools/audit_lsq_bus_v2.py", ROOT/"tools/audit_sq_initial.py")
    for file in files:
        target = dest/file.name
        if target.exists():
            assert sha(target) == sha(file)
        else:
            shutil.copy2(file, target)
    report = dict(run=name, status="NOT_PASS_eight_corrected_mixed_prefixes_original_public_obligations_audited", tests=manifest["tests"], snapshot_files=len(source),
                  counts=dict(counts), cases=cases, auditors={f.name: sha(dest/f.name) for f in files},
                  preserved_v1_rejection="02 scalar16 metadata is correctly rejected;03 later falsely collided with a cancelled slot lease whose need_rep feedback had cleared grant. v2 frees cancelled lease by original UID, not grant presence; all live-slot/feedback identity checks retained. v1 source preserved, never modified.",
                  limits="Eight actually executed mixed prefixes only. Original UID ROB/queue/window/query/S2/Replay/direction/mid/SID/Cache/Sbuffer legality and effects are reconstructed from public histories. Failures, failed-live UIDs, pending external jobs and returned unconsumed data are not erased or counted as complete. No full random completion, fair-drain execution, coupled full capacity, mixed active reset, full ROB wrap or same-slot restoration acceptance. No DUT/reference/actor/issue oracle, no expected/change semantic answers or weakened probe fixture.")
    out = run/"mixed-history-audit-v2.json"
    if out.exists():
        assert json.loads(out.read_text()) == report
    else:
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False)+"\n")
    print(json.dumps({k: v for k, v in report.items() if k != "cases"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
