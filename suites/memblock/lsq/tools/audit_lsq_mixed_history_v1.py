#!/usr/bin/env python3
"""Independent public-history legality/obligation audit of eight mixed prefixes.

No actor/model/private/issue-manifest imports; no expected/change fields used
as semantic answers. A terminal failing cycle is retained, not marked checked.
Fair drain/reset/coupled capacity remain unclaimed unless truly reached.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_lsq_bus_v2 import rob, rob_matches, sq, pointer
from audit_lsq_population_v1 import events, paths_by_node, replay_metadata, validate_row
from audit_sq_initial import ROOT, sha, verify_common


class Timeline:
    def __init__(self):
        self.anchor = 0

    def decode(self, value, observe=False):
        code = rob(value)
        base = self.anchor//640*640+code
        result = min((base-640, base, base+640), key=lambda n: abs(n-self.anchor))
        assert abs(result-self.anchor) < 320
        if observe:
            self.anchor = max(result, self.anchor)
        return result


def inspect(path):
    rows = list(events(path))
    stores, loads, program, attempts, by_sq, by_lq, lq_valid, slots = [], [], [], [], {}, {}, {}, {}
    lhead = ltail = shead = stail = sequence = 0
    timeline = Timeline()
    previous, s2, query_pipe, data_pipe, recovery, cache = None, [], [None]*3, [None]*3, None, None
    counts, peaks, causes, failures, shared_recoveries = Counter(), Counter(), Counter(), [], []

    def live(s):
        return not s["complete"] and not s["cancelled"]

    def issue(condition, obligation, **evidence):
        if not condition:
            failures.append(dict(post_tick=tick, obligation=obligation, **evidence))

    def find_rob(value, kind, include_cancelled=False):
        order = timeline.decode(value)
        found = [s for s in program if s["kind"] == kind and s["order"] == order and (include_cancelled or not s["rob_cancelled"])]
        assert len(found) == 1, ("public original ROB identity", value, order, [s["uid"] for s in found])
        return found[0]

    for index, row in enumerate(rows):
        validate_row(row, previous, False)
        inp, pre, post, tick = row["input"], row["before"], row["after"], row["post_tick"]
        assert row["checked"] or index == len(rows)-1
        counts["continuous_raw_records"] += 1
        if inp["reset"]:
            assert not program
            previous = row
            continue
        assert not inp["sbuffer_ready"][1] or inp["sbuffer_ready"][0], "illegal reverse-prefix Sbuffer consumer"
        assert pointer(pre, "io_sqDeqPtr_") == shead % 256
        head = timeline.decode(inp["pending"], True)
        # All ROB observations and dispatches are nearby epochs, not low-index
        # sorting. Complete Load/SQ credits and ROB retirement stay distinct.
        for s in program:
            if s["rob_cancelled"] or s["order"] >= head:
                continue
            if s["kind"] == "load":
                assert s["sent"] and not s["fault"]
            elif s.get("memory") == 1:
                assert s["attempts"] and s["attempts"][-1]["sid"] is not None
            elif s.get("cbo") is not None or s.get("memory", 0) & 2:
                assert s["wb"] is not None and not s["fault"]
            else:
                assert s.get("s2_done") and "data" in s
        red = inp["redirect"]
        cutoff = timeline.decode(red["rob"]) if red["valid"] else None
        assert not red["valid"] or not any(d["valid"] for d in inp["dispatch"])
        prepared = []
        for position in range(lhead, lhead+8):
            item = lq_valid.get(position)
            if item is None or not item["sent"] or cutoff is not None and item["order"] >= cutoff:
                break
            prepared.append(item)
        for d in inp["dispatch"]:
            if not d["valid"]:
                continue
            assert recovery is None and not pre["io_toLsqEnqCtrl_lqRecoverStall"] and not pre["io_toLsqEnqCtrl_sqRecoverStall"] and d["flows"] == 1
            order = timeline.decode(d["rob"], True)
            assert order >= head and not any(s["order"] >= order and not s["rob_cancelled"] for s in program)
            sequence += 1
            s = dict(uid=sequence, kind="store" if d["need_alloc"] == 2 else "load", order=order, rob=d["rob"],
                     complete=False, cancelled=False, rob_cancelled=False, fault=False, attempts=[], grant=None, sent=False, consumed=set(), wb=None)
            assert d["need_alloc"] in (1, 2)
            program.append(s)
            if s["kind"] == "store":
                s["position"] = stail
                assert stail not in by_sq or not live(by_sq[stail])
                by_sq[stail] = s
                stores.append(s)
                stail += 1
                assert sq(d["store_end"]) == stail % 256
            else:
                assert 120*int(d["load_start"]["flag"])+d["load_start"]["value"] == ltail % 240
                s.update(position=ltail, sq_boundary=stail)
                assert ltail % 240 not in by_lq or not live(by_lq[ltail % 240])
                by_lq[ltail % 240], lq_valid[ltail] = s, s
                loads.append(s)
                ltail += 1
        for s, lane, last in s2:
            a = inp["attributes"][lane]
            assert a["last"] == last and not a["exception"]
            if last and live(s):
                s["s2_done"] = True
                s["memory"] = int(a["nc"] or not a["memory"])+2*int(a["mmio"])+4*int(not a["memory"])
        s2 = []
        for lane, a in enumerate(inp["addresses"]):
            if a["valid"]:
                pos = shead+(a["slot"]-shead) % 64
                s = by_sq[pos]
                assert live(s) and s["rob"] == a["rob"] and pos < min(stail, shead+64)
                assert a["vaddr"] % 4096 == a["paddr"] % 4096
                if "address" in s and s.get("address_valid"):
                    assert a["cross_word"] and a["last"] and not s.get("s2_done")
                if not a["tlb_miss"]:
                    if "address" not in s or not s.get("address_valid"):
                        s["address"] = a
                    s["address_valid"] = True
                    s["cbo"] = (a["fu_op"] >> 1) & 7 if a["fu_op"] & 1 else None
                    s2.append((s, lane, a["last"]))
        for d in inp["data"]:
            if d["valid"]:
                pos = shead+(sq(d["sq"])-shead) % 256
                s = by_sq[pos]
                assert live(s) and pos < shead+64 and "data" not in s
                s["data"] = d["data"]
        for lane, q in enumerate(inp["rar_queries"]):
            if not q["valid"]:
                continue
            s = find_rob(q["rob"], "load")
            assert live(s) and 120*int(q["lq"]["flag"])+q["lq"]["value"] == s["position"] % 240
            s.setdefault("paddr", q["paddr"])
            assert s["paddr"] == q["paddr"]
            if q["nc"]:
                assert s["attempts"] and s["attempts"][-1]["consumed"] and s["packet"]["execution"]["nc"]
            counts["original_rar_queries"] += 1
            if inp["queries"][lane]["valid"]:
                raw, f = inp["raw_queries"][lane], inp["queries"][lane]
                assert raw["valid"] and raw["rob"] == q["rob"] and raw["paddr"] == q["paddr"] and raw["data_valid"]
                assert sq(raw["sq"]) == sq(f["sq"]) == s["sq_boundary"] % 256
                s.setdefault("vaddr", f["vaddr"])
                assert s["vaddr"] == f["vaddr"] and f["vaddr"] % 4096 == q["paddr"] % 4096
                counts["original_forward_raw_query_pairs"] += 1
        for lane, old in enumerate(query_pipe):
            if old is not None:
                s = old
                tr = inp["translations"][lane]
                assert tr["kill"] or tr["paddr"] == s["paddr"]
        query_pipe = [find_rob(inp["raw_queries"][lane]["rob"], "load") if q["valid"] else None for lane, q in enumerate(inp["queries"])]
        for packet in inp["loads"]:
            q = packet["execution"]
            if not q["valid"]:
                continue
            s = by_lq[120*int(q["uop"]["lq"]["flag"])+q["uop"]["lq"]["value"]]
            assert live(s) and s["rob"] == q["uop"]["rob"] and sq(q["uop"]["sq"]) == s["sq_boundary"] % 256
            assert packet["fullva"] == q["vaddr"] and packet["paddr"] % 4096 == q["vaddr"] % 4096
            s.setdefault("vaddr", q["vaddr"])
            s.setdefault("paddr", packet["paddr"])
            assert s["paddr"] == packet["paddr"] and s["vaddr"] == q["vaddr"]
            if q["replay_feedback"]:
                assert s["grant"] == q["slot"] and slots[q["slot"]] is s and q["uop"] == s["packet"]["execution"]["uop"]
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
                    assert s["attempts"] and s["attempts"][-1]["consumed"]
                s["sent"] = True
            s["last_packet"] = packet
        if pre["io_uncache_req_valid"] and inp["bus"]["ready"]:
            kind = "load" if pre["io_uncache_req_bits_cmd"] == 0 else "store"
            found = [s for s in program if s["kind"] == kind and (not s["rob_cancelled"] or kind == "load") and
                     s.get("paddr", s.get("address", {}).get("paddr")) == pre["io_uncache_req_bits_addr"] and
                     (int(s["rob"]["flag"]), s["rob"]["value"], int(s["rob"]["former"])) ==
                     (pre["io_uncache_req_bits_robIdx_flag"], pre["io_uncache_req_bits_robIdx_value"], pre["io_uncache_req_bits_robIdx_isFormer"]) and
                     (not s["attempts"] or s["attempts"][-1]["consumed"])]
            assert len(found) == 1
            s = found[0]
            if kind == "store":
                assert s["order"] == head and s.get("s2_done") and "data" in s
                assert pre["io_uncache_req_bits_data"] == s["data"] & ((1 << 64)-1)
            else:
                assert s["last_packet"]["execution"]["causes"] == 1
            job = dict(uid=len(attempts)+1, owner=s, mid=pre["io_uncache_req_bits_id"], sid=None, response=None, consumed=False, request_tick=tick)
            attempts.append(job)
            s["attempts"].append(job)
            counts["load_bus_fires" if kind == "load" else "store_bus_fires"] += 1
        bus = inp["bus"]
        if bus["ack"]:
            matches = [a for a in attempts if a["sid"] is None and a["mid"] == bus["mid"] and (a["owner"]["kind"] == "load") == bus["ack_to_load"]]
            assert len(matches) == 1 and not any(a["sid"] == bus["sid"] and a["response"] is None for a in attempts)
            matches[0]["sid"] = bus["sid"]
            counts["original_direction_acks"] += 1
        if bus["response"]:
            matches = [a for a in attempts if a["sid"] == bus["response_id"] and a["response"] is None and (a["owner"]["kind"] == "load") == bus["response_to_load"]]
            assert len(matches) == 1
            matches[0]["response"] = dict(tick=tick, data=bus["data"], error=bus["error"], nderr=bus["nderr"])
            counts["original_sid_responses"] += 1
        for bank in range(3):
            p = f"io_replay_{bank}_"
            if pre[p+"valid"] and inp["replay_ready"][bank]:
                s = by_lq[120*pre[p+"bits_uop_lqIdx_flag"]+pre[p+"bits_uop_lqIdx_value"]]
                assert live(s) and s["grant"] is None and not s["sent"]
                replay_metadata(pre, p+"bits_", s["last_packet"])
                slot = pre[p+"bits_replayQueueIdx"]
                assert slot % 3 == bank and (slot not in slots or slots[slot] is s)
                s["grant"], slots[slot] = slot, s
                counts["original_replay_grants"] += 1
        next_data, consumed = [None]*3, []
        for lane, q in enumerate(inp["bypass"]):
            p = f"io_bypass_{lane}_"
            if q["valid"]:
                s = by_lq[120*int(q["lq"]["flag"])+q["lq"]["value"]]
                assert live(s) and s["grant"] is not None and s["attempts"] and s["attempts"][-1]["response"] is not None
                job = s["attempts"][-1]
                assert not job["consumed"] and q["nc"] == s["packet"]["execution"]["nc"] and q["mmio"] == s["packet"]["mmio"]
                issue(post[p+"s1Resp_valid"] and post[p+"s1Resp_bits_paddr"] == s["paddr"], "original_bypass_PA", uid=s["uid"])
                next_data[lane] = (s, job)
                consumed.append((s, job))
            if data_pipe[lane] is not None:
                s, job = data_pipe[lane]
                response = job["response"]
                actual = post[p+"s2Resp_bits_data"]
                expected = response["data"]*((1 << 64)+1)
                issue(post[p+"s2Resp_valid"] and actual == expected and post[p+"s2Resp_bits_derr"] == int(response["error"]) and post[p+"s2Resp_bits_nderr"] == int(response["nderr"]),
                      "original_returned_SID_data_error_must_survive_until_consumption", uid=s["uid"], attempt=job["uid"], mid=job["mid"], sid=job["sid"],
                      original_response=response, actual_s2_data=actual, expected_original_s2_data=expected,
                      later_same_SID_responses=[dict(attempt=a["uid"], owner_uid=a["owner"]["uid"], response=a["response"]) for a in attempts if a is not job and a["sid"] == job["sid"] and a["response"] and a["response"]["tick"] > response["tick"]])
                job["consumed"] = True
                s["fault"] |= response["error"] or response["nderr"]
                counts["original_data_error_consumptions"] += 1
        if consumed:
            s, job = min(consumed, key=lambda item: item[1]["mid"])
            response = job["response"]
            issue(post["io_ldExceptionInfo_valid"] and post["io_ldExceptionInfo_bits_exceptionVec_19"] == int(response["error"]) and post["io_ldExceptionInfo_bits_exceptionVec_5"] == int(response["nderr"]),
                  "original_returned_SID_exception_must_survive_until_s1", uid=s["uid"], attempt=job["uid"], sid=job["sid"], original_response=response)
        data_pipe = next_data
        if pre["io_cmoOpReq_valid"] and inp["cache_ready"]:
            candidates = [s for s in stores if live(s) and s["order"] == head and s.get("cbo") is not None and s["address"]["paddr"] == pre["io_cmoOpReq_bits_address"]]
            assert len(candidates) == 1 and cache is None
            cache = candidates[0]
            assert cache.get("s2_done") and "data" in cache and pre["io_cmoOpReq_bits_opcode"] == cache["cbo"]
            counts["original_Cache_requests"] += 1
        if inp["cache_response"]:
            assert cache is not None and pre["io_cmoOpResp_ready"]
            cache["cache_response"] = dict(tick=tick, denied=inp["cache_denied"], corrupt=inp["cache_corrupt"])
            cache = None
            counts["original_Cache_responses"] += 1
        if pre["io_mmioStout_valid"]:
            s = find_rob(dict(flag=bool(pre["io_mmioStout_bits_robIdx_flag"]), value=pre["io_mmioStout_bits_robIdx_value"], former=bool(pre["io_mmioStout_bits_robIdx_isFormer"])), "store")
            assert s["order"] == head
            response = s.get("cache_response", dict(denied=False, corrupt=False))
            issue(pre["io_mmioStout_bits_exceptionVec_7"] == int(response["denied"]) and pre["io_mmioStout_bits_exceptionVec_19"] == int(response["corrupt"]),
                  "actual_WB_keeps_original_Cache_errors", uid=s["uid"], response=response, ready=inp["writeback_ready"])
            if inp["writeback_ready"]:
                if s.get("cbo") == 3:
                    issue(bool(s["consumed"]), "zero_WB_requires_its_own_actual_zero_transfer", uid=s["uid"])
                s["wb"] = tick
                s["fault"] |= response["denied"] or response["corrupt"]
                counts["original_WB_fires"] += 1
        for lane in range(2):
            p = f"io_sbuffer_req_{lane}_"
            if pre[p+"valid"] and inp["sbuffer_ready"][lane]:
                candidates = [s for s in stores if live(s) and s.get("memory") == 0 and s.get("cbo") in (None, 3) and
                              len(s["consumed"]) < (2 if s["address"]["cross_word"] else 1)]
                s = min(candidates, key=lambda s: s["position"])
                part = len(s["consumed"])
                va, pa = s["address"]["vaddr"]//16*16+16*part, s["address"]["paddr"]//16*16+16*part
                mask = value = 0
                for byte in range(1 << s["address"]["size"]):
                    target = s["address"]["vaddr"]+byte-va
                    if 0 <= target < 16:
                        mask |= 1 << target
                        value |= ((s["data"] >> (8*byte)) & 255) << (8*target) if s.get("cbo") != 3 else 0
                bits = sum(255 << (8*b) for b in range(16) if mask >> b & 1)
                issue(pre[p+"bits_vaddr"] == va and pre[p+"bits_addr"] == pa and pre[p+"bits_mask"] == mask and not ((pre[p+"bits_data"] ^ value) & bits) and pre[p+"bits_wline"] == int(s.get("cbo") == 3),
                      "actual_original_Sbuffer_PA_bytes_and_control", uid=s["uid"], part=part)
                assert s.get("s2_done") and "data" in s and s["order"] <= head
                s["consumed"].add(part)
                counts["original_Sbuffer_fragment_fires"] += 1
        for item in prepared:
            del lq_valid[item["position"]]
        if red["valid"]:
            assert recovery is None and cutoff >= head and red["flush_self"]
            victims = [s for s in program if not s["rob_cancelled"] and s["order"] >= cutoff]
            killed_lq = [s for s in lq_valid.values() if s["order"] >= cutoff]
            killed_sq = [s for s in stores if live(s) and s["order"] >= cutoff]
            assert all(not s["consumed"] and not s["attempts"] for s in killed_sq)
            recovery = dict(cutoff=cutoff, lq_target=ltail-len(killed_lq), sq_target=min((s["position"] for s in killed_sq), default=stail), lq=None, sq=None, tick=tick)
            shared_recoveries.append(recovery)
            for s in victims:
                s["rob_cancelled"] = True
                if live(s) and (s["kind"] == "store" or s in killed_lq):
                    s["cancelled"] = True
                    if s["kind"] == "load":
                        lq_valid.pop(s["position"], None)
                    if s["grant"] is not None:
                        slots.pop(s["grant"], None)
            counts["shared_redirects"] += 1
        delta = (pointer(post, "io_sqDeqPtr_")-shead) % 256
        assert delta <= 2
        for pos in range(shead, shead+delta):
            s = by_sq[pos]
            assert live(s) and s.get("s2_done") and "data" in s
            complete = bool(s["consumed"]) and len(s["consumed"]) == (2 if s["address"]["cross_word"] else 1) if s.get("cbo") is None and s.get("memory") == 0 else bool(s["attempts"] and s["attempts"][-1]["sid"] is not None) if s.get("memory") == 1 else s["wb"] is not None
            issue(complete, "SQ_release_requires_the_original_complete_prefix", uid=s["uid"])
            s["complete"] = True
        shead += delta
        if post["io_toLsqEnqCtrl_lqDeq_valid"]:
            for pos in range(lhead, lhead+post["io_toLsqEnqCtrl_lqDeq_bits"]):
                s = by_lq[pos % 240]
                assert live(s) and s["sent"]
                s["complete"] = True
            lhead += post["io_toLsqEnqCtrl_lqDeq_bits"]
        if recovery is not None:
            if post["io_toLsqEnqCtrl_lqRedirectPtr_valid"]:
                ltail = max(lhead, recovery["lq_target"])
                recovery["lq"] = 120*post["io_toLsqEnqCtrl_lqRedirectPtr_bits_flag"]+post["io_toLsqEnqCtrl_lqRedirectPtr_bits_value"]
                assert recovery["lq"] == ltail % 240
            if post["io_toLsqEnqCtrl_sqRedirectPtr_valid"]:
                stail = recovery["sq_target"]
                recovery["sq"] = pointer(post, "io_toLsqEnqCtrl_sqRedirectPtr_bits_")
                assert recovery["sq"] == stail % 256
            if recovery["lq"] is not None and recovery["sq"] is not None and not post["io_toLsqEnqCtrl_lqRecoverStall"] and not post["io_toLsqEnqCtrl_sqRecoverStall"]:
                recovery["settled_tick"] = tick
                recovery = None
                counts["both_recovery_responses_settled"] += 1
        assert 0 <= ltail-lhead <= 120 and 0 <= stail-shead <= 128
        for key, value in (("lq", ltail-lhead), ("sq_virtual", stail-shead), ("unreturned_external_jobs", sum(a["response"] is None for a in attempts))):
            peaks[key] = max(peaks[key], value)
        if failures:
            assert index == len(rows)-1, ("earlier independent semantic failure was not stopped", failures)
        previous = row
    assert not rows[-1]["checked"] and "error" in rows[-1]
    counts.update(allocated=len(program), completed=sum(s["complete"] for s in program), cancelled=sum(s["cancelled"] for s in program),
                  failed_live=sum(live(s) for s in program), pending_external_responses=sum(a["response"] is None for a in attempts),
                  returned_not_consumed=sum(a["response"] is not None and not a["consumed"] and a["owner"]["kind"] == "load" for a in attempts))
    assert counts["allocated"] == counts["completed"]+counts["cancelled"]+counts["failed_live"]
    return dict(counts=dict(counts), peaks=dict(peaks), cause_occurrences=dict(causes), independent_terminal_counterexamples=failures,
                terminal_tick=rows[-1]["post_tick"], terminal_runtime_error=rows[-1]["error"], recoveries=shared_recoveries,
                pending_original_job_witnesses=[dict(attempt=a["uid"], uid=a["owner"]["uid"], kind=a["owner"]["kind"], mid=a["mid"], sid=a["sid"]) for a in attempts if a["response"] is None])


def audit(name):
    assert name == "lsq-seeded-mixed-02", "fixed8 corrected seed prefix range"
    run = ROOT/"results"/name
    manifest, source, nodes = verify_common(run)
    assert manifest["tests"] == {"FAIL": 8} and len(source) == 356
    paths = paths_by_node(run)
    assert set(paths) == set(nodes) and len(nodes) == 8 and all(nodes.values())
    counts, cases = Counter(), []
    for node, path in sorted(paths.items()):
        detail = inspect(path)
        counts.update(detail["counts"])
        cases.append(dict(nodeid=node, journal=str(path.relative_to(run)), sha256=sha(path), **detail))
    dest = run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    files = (Path(__file__), ROOT/"tools/audit_lsq_population_v1.py", ROOT/"tools/audit_lsq_bus_v2.py", ROOT/"tools/audit_sq_initial.py")
    for file in files:
        target = dest/file.name
        if target.exists():
            assert sha(target) == sha(file)
        else:
            shutil.copy2(file, target)
    report = dict(run=name, status="NOT_PASS_eight_mixed_seed_prefixes_public_legality_and_original_obligations_audited", tests=manifest["tests"],
                  snapshot_files=len(source), counts=dict(counts), cases=cases, auditors={f.name: sha(dest/f.name) for f in files},
                  limits="Only the actually executed prefixes of eight full-domain fixed seeds. No fair-drain execution, full capacity, active mixed reset, complete cause/ROB wrap domain, same-slot restoration or success is claimed. Failed live UIDs, external responses and unconsumed returned data stay explicit; no reset/redirect exemption erases them. Raw public inputs, accepted original Store/Load/Replay/bus/Cache/Sbuffer identities drive this audit; expected/change/actor/private/known-issues are not semantic answers. Terminal staged-reference/physical failures remain ordinary FAIL, with independent SID data/exception/effect counterexamples where observed.")
    output = run/"mixed-history-audit-v1.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False)+"\n")
    print(json.dumps({k: v for k, v in report.items() if k != "cases"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
