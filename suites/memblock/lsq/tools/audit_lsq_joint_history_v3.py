#!/usr/bin/env python3
"""Rebuild coupled pools, epochs, actual fair service and original effects, v3.

Semantic answers use only public input/pre/post histories, never the actor,
model, change/expected dictionaries, private probes or issue manifest. The
standard row validator separately confirms continuous strict fixture checks.
Directed positive conditions do not replace full-domain random failures.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_lsq_bus_v2 import pointer, rob, rob_matches, sq
from audit_lsq_mixed_history_v1 import Timeline
from audit_lsq_population_v1 import RAW, events, paths_by_node, replay_metadata, same_raw, validate_row
from audit_sq_initial import ROOT, sha, verify_common


def lq(value):
    return 120*int(value["flag"])+value["value"]


class JointAudit:
    def __init__(self):
        self.history, self.jobs, self.snapshots, self.fair_periods = [], [], [], []
        self.counts, self.codes, self.query_sources, self.sta_sources = Counter(), set(), set(), set()
        self.previous, self.epoch, self.resetting = None, 0, False
        self.reset_windows, self.recoveries = [], []
        self.fair = None
        self.restart()

    def restart(self):
        self.timeline = Timeline()
        self.sh = self.st = self.lh = self.lt = 0
        self.program, self.bysq, self.bylq, self.valid = [], {}, {}, {}
        self.rar, self.raw, self.leases, self.slots = [], [], {}, {}
        self.s2, self.qpipe, self.bpipe, self.report_next = [], [None]*3, [None]*3, []
        self.cache = self.recovery = None

    @staticmethod
    def live(s):
        return s["status"] == "active"

    def owner(self, value, kind):
        order = self.timeline.decode(value)
        found = [s for s in self.program if s["order"] == order and s["kind"] == kind and not s["rob_cancelled"]]
        assert len(found) == 1, ("public nearby ROB generation", self.epoch, order, kind)
        return found[0]

    def active(self, kind=None):
        return [s for s in self.history if self.live(s) and (kind is None or s["kind"] == kind)]

    def step(self, row):
        validate_row(row, self.previous, False)
        assert row["checked"]
        i, pre, post, tick = row["input"], row["before"], row["after"], row["post_tick"]
        self.counts["raw_records"] += 1
        if i["reset"]:
            assert not any(d["valid"] for d in i["dispatch"]) and not any(a["valid"] for a in i["addresses"])
            assert not i["bus"]["ack"] and not i["bus"]["response"] and not i["cache_response"]
            if not self.resetting:
                live, unfinished = self.active(), [j for j in self.jobs if not j["response"] and not j["aborted"]]
                if live:
                    assert len(live) == 248 and len(unfinished) == 16 and len(self.rar) == 96 and len(self.raw) == 56 and len(self.leases) == 120
                    assert not self.fair and all(j["owner"]["kind"] == "load" and j["sid"] is not None for j in unfinished)
                    for s in live:
                        s["status"], s["rob_cancelled"] = "reset", True
                    for j in unfinished:
                        j["aborted"] = tick
                    self.reset_windows.append(dict(start_tick=tick, epochs=[self.epoch,self.epoch+1],
                                                   local_original_uids=[s["uid"] for s in live],
                                                   external_original_jobs=[j["uid"] for j in unfinished], samples=[]))
                    self.epoch += 1
                    self.counts["active_common_system_resets"] += 1
                else:
                    assert not unfinished
                self.restart()
            self.resetting = True
            if self.reset_windows and tick <= self.reset_windows[-1]["start_tick"]+6:
                w = self.reset_windows[-1]
                offset = (tick-w["start_tick"])//2
                assert post["io_perf_17_value"] == int(offset >= 3) and post["io_perf_24_value"] == int(offset < 3), "resetless four-edge perf history must survive async full predicate reset"
                w["samples"].append(dict(tick=tick, full_mask000=post["io_perf_17_value"], full_mask111=post["io_perf_24_value"]))
            self.previous = row
            return
        self.resetting = False
        assert not i["sbuffer_ready"][1] or i["sbuffer_ready"][0]
        assert pointer(pre,"io_sqDeqPtr_") == self.sh % 256
        head = self.timeline.decode(i["pending"], True)
        for s in self.program:
            if s["rob_cancelled"] or s["order"] >= head:
                continue
            assert not s["fault"]
            if s["kind"] == "load":
                assert s["sent"], "ROB must not pass an unfinished original Load"
            elif s.get("memory") == 1:
                assert s["attempts"] and s["attempts"][-1]["sid"] is not None
            elif s.get("cbo") is not None or s.get("memory",0) & 2:
                assert s["wb"] is not None
            else:
                assert s.get("s2") and "data" in s
        red = i["redirect"]
        cut = self.timeline.decode(red["rob"]) if red["valid"] else None
        assert cut is None or cut >= head and red["flush_self"] and not self.recovery and not any(d["valid"] for d in i["dispatch"])
        prepared = []
        for pos in range(self.lh,self.lh+8):
            s = self.valid.get(pos)
            if s is None or not s["sent"] or cut is not None and s["order"] >= cut:
                break
            prepared.append(s)
        for lane,d in enumerate(i["dispatch"]):
            if not d["valid"]:
                continue
            assert self.fair is None and self.recovery is None and not pre["io_toLsqEnqCtrl_lqRecoverStall"] and not pre["io_toLsqEnqCtrl_sqRecoverStall"]
            assert d["flows"] == 1 and d["need_alloc"] in (1,2)
            order = self.timeline.decode(d["rob"],True)
            assert order >= head and not any(s["order"] >= order and not s["rob_cancelled"] for s in self.program)
            s = dict(uid=len(self.history)+1, epoch=self.epoch, order=order, rob=d["rob"], kind="load" if d["need_alloc"]==1 else "store",
                     status="active", rob_cancelled=False, sent=False, attempts=[], fault=False, grant=None, slot=None, consumed=set(), wb=None, packet=None)
            self.history.append(s)
            self.program.append(s)
            self.codes.add(rob(d["rob"]))
            if s["kind"] == "store":
                s["pos"] = self.st
                assert self.st not in self.bysq or not self.live(self.bysq[self.st])
                self.bysq[self.st] = s
                self.st += 1
                assert sq(d["store_end"]) == self.st % 256
            else:
                s.update(pos=self.lt, sq_bound=self.st)
                assert lq(d["load_start"]) == self.lt % 240 and (self.lt % 240 not in self.bylq or not self.live(self.bylq[self.lt % 240]))
                self.bylq[self.lt % 240],self.valid[self.lt] = s,s
                self.lt += 1
        # All child pool leases are derived from accepted PUBLIC queries and
        # actual public queue/address prefix progress, not a reference change.
        ready_head = self.sh+(pointer(pre,"io_issuePtrExt_")-self.sh) % 256
        assert self.sh <= ready_head <= self.sh+64
        self.rar = [r for r in self.rar if r["pos"] > self.lh]
        self.raw = [r for r in self.raw if r["bound"] > ready_head]
        for s,lane in self.s2:
            a = i["attributes"][lane]
            assert a["last"] and not a["exception"]
            s.update(s2=True,memory=int(a["nc"] or not a["memory"])+2*int(a["mmio"])+4*int(not a["memory"]))
        self.s2 = []
        for lane,a in enumerate(i["addresses"]):
            if not a["valid"]:
                continue
            pos = self.sh+(a["slot"]-self.sh) % 64
            s = self.bysq[pos]
            assert self.live(s) and pos < min(self.st,self.sh+64) and s["rob"] == a["rob"] and "address" not in s
            assert not a["tlb_miss"] and not a["cross_word"] and a["last"] and a["vaddr"] % 64 == a["paddr"] % 64 == 0
            assert a["size"] == 3 and a["mask"] == 255
            s.update(address=a,cbo=(a["fu_op"]>>1 & 7) if a["fu_op"] & 1 else None)
            self.s2.append((s,lane))
            self.sta_sources.add((pos % 64,lane))
        for d in i["data"]:
            if d["valid"]:
                pos = self.sh+(sq(d["sq"])-self.sh) % 256
                s = self.bysq[pos]
                assert self.live(s) and pos < self.sh+64 and "data" not in s and sq(d["sq"]) == pos % 256
                s["data"] = d["data"]
        for lane,w in enumerate(i["address_wakeups"]):
            if w["valid"]:
                a = i["addresses"][lane]
                assert a["valid"] and w["sq"]["value"] == a["slot"]
        for lane,old in enumerate(self.qpipe):
            if old is None:
                continue
            s,forward,rar_denied,raw_denied = old
            if forward:
                assert i["translations"][lane]["paddr"] == s["pa"] and not i["translations"][lane]["kill"]
                p = f"io_forward_{lane}_s2Resp_"
                assert post[p+"valid"]
                # Disjoint PA/VA positive condition: no original older Store
                # owns any queried byte, irrespective of replay blockage.
                assert not any(post[p+f"bits_forwardMask_{b}"] for b in range(16))
                if post[p+"bits_addrInvalid_valid"]:
                    cause = 2
                    dep = pointer(post,p+"bits_addrInvalid_bits_")
                    s["address_dependency"] = dep
                elif post[p+"bits_dataInvalid_valid"]:
                    cause = 4
                elif post[p+"bits_forwardInvalid"] or post[p+"bits_matchInvalid"]:
                    cause = 1
                else:
                    cause = None
            else:
                cause = None
            if cause is None:
                cause = 9 if rar_denied else 10 if raw_denied else None
            s["query_cause"] = cause
        next_q = [None]*3
        for lane,q in enumerate(i["rar_queries"]):
            if not q["valid"]:
                continue
            s = self.owner(q["rob"],"load")
            assert self.live(s) and lq(q["lq"]) == s["pos"] % 240 and q["data_valid"]
            s.setdefault("pa",q["paddr"])
            assert s["pa"] == q["paddr"] and post[f"io_ldu_rarNukeQuery_{lane}_resp_valid"] and not post[f"io_ldu_rarNukeQuery_{lane}_resp_bits_nuke"]
            rar_ok = pre[f"io_ldu_rarNukeQuery_{lane}_req_ready"]
            if s["pos"] > self.lh and rar_ok:
                self.rar.append(dict(uid=s["uid"],pos=s["pos"],order=s["order"]))
            self.counts["rar_queries"] += 1
            self.counts["rar_refusals"] += not rar_ok
            forward = i["queries"][lane]["valid"]
            raw_ok = True
            if forward:
                r,f = i["raw_queries"][lane],i["queries"][lane]
                assert r["valid"] and r["rob"] == s["rob"] and r["paddr"] == s["pa"] and r["data_valid"]
                assert sq(r["sq"]) == sq(f["sq"]) == s["sq_bound"] % 256
                assert f["vaddr"] % 4096 == s["pa"] % 4096
                s.setdefault("va",f["vaddr"])
                assert s["va"] == f["vaddr"]
                s.setdefault("wait",(f["wait"],f["strict"],f["wait_sq"]))
                assert s["wait"] == (f["wait"],f["strict"],f["wait_sq"])
                raw_ok = pre[f"io_ldu_rawNukeQuery_{lane}_req_ready"]
                if s["sq_bound"] > ready_head and raw_ok:
                    self.raw.append(dict(uid=s["uid"],bound=s["sq_bound"],order=s["order"]))
                self.counts["forward_raw_pairs"] += 1
                self.counts["raw_refusals"] += not raw_ok
            else:
                assert not i["raw_queries"][lane]["valid"] and s["attempts"][-1]["consumed"]
                assert q["nc"] == s["packet"]["execution"]["nc"]
            next_q[lane] = (s,forward,not rar_ok,not raw_ok)
            self.query_sources.add(lane)
        self.qpipe = next_q
        for lane,packet in enumerate(i["loads"]):
            q,u = packet["execution"],packet["execution"]["uop"]
            if not q["valid"]:
                continue
            s = self.bylq[lq(u["lq"])]
            assert self.live(s) and s["rob"] == u["rob"] and sq(u["sq"]) == s["sq_bound"] % 256
            assert packet["fullva"] == q["vaddr"] and packet["paddr"] % 4096 == q["vaddr"] % 4096
            s.setdefault("pa",packet["paddr"])
            s.setdefault("va",q["vaddr"])
            assert (s["pa"],s["va"]) == (packet["paddr"],q["vaddr"])
            assert q["vector"] == bool(u["vector_write"]) and ((u["operation"]>>1 & 7)<4 or q["vector"])
            if q["replay_feedback"]:
                assert s["grant"] == q["slot"] and self.slots[q["slot"]] is s and self.leases[s["uid"]] is s, "original Replay slot feedback identity"
                assert u == s["packet"]["execution"]["uop"]
                s["grant"] = None
                self.counts["original_slot_feedbacks"] += 1
                if not q["need_replay"]:
                    del self.slots[q["slot"]]
                    del self.leases[s["uid"]]
            else:
                assert s["packet"] is None and q["need_replay"] and s["uid"] not in self.leases
                s["packet"],self.leases[s["uid"]] = packet,s
                self.counts["initial_replay_leases"] += 1
            if "wait" in s:
                assert s["wait"] == (u["load_wait"],u["strict"],u["wait_sq"])
            if q["need_replay"]:
                assert q["causes"].bit_count() == 1 and q["causes"] < 1<<12
                cause = q["causes"].bit_length()-1
                assert cause == 0 and (q["nc"] or packet["mmio"]) or cause == s.get("query_cause"), "S3 replay reason must come from original query/real Uncache obligation"
                if cause == 2:
                    assert sq(q["address_sq"]) == s["address_dependency"]
            else:
                assert not s["sent"] and packet["update_address"] and not q["causes"] and s.get("query_cause") is None
                if s["packet"]["execution"]["causes"] == 1:
                    assert s["attempts"][-1]["consumed"]
                s["sent"] = True
            s["last"] = packet
        if pre["io_uncache_req_valid"] and i["bus"]["ready"]:
            kind = "load" if pre["io_uncache_req_bits_cmd"] == 0 else "store"
            found = [s for s in self.history if s["epoch"] == self.epoch and s["kind"] == kind and s.get("pa",s.get("address",{}).get("paddr")) == pre["io_uncache_req_bits_addr"] and
                     (int(s["rob"]["flag"]),s["rob"]["value"],int(s["rob"]["former"])) == (pre["io_uncache_req_bits_robIdx_flag"],pre["io_uncache_req_bits_robIdx_value"],pre["io_uncache_req_bits_robIdx_isFormer"]) and
                     (not s["attempts"] or s["attempts"][-1]["consumed"])]
            assert len(found) == 1
            s = found[0]
            if kind == "load":
                assert self.live(s) and s["last"]["execution"]["causes"] == 1
            else:
                assert self.live(s) and s["order"] == head and s.get("s2") and "data" in s
                assert pre["io_uncache_req_bits_data"] == s["data"] & ((1<<64)-1)
            mid = pre["io_uncache_req_bits_id"]
            assert kind != "load" or not any(j["mid"]==mid and j["owner"]["kind"]==kind and not j["consumed"] and not j["aborted"] and j["owner"]["status"]!="cancelled" for j in self.jobs)
            j = dict(uid=len(self.jobs)+1,owner=s,mid=mid,sid=None,response=None,consumed=False,aborted=None,request_tick=tick)
            self.jobs.append(j)
            s["attempts"].append(j)
            self.counts[kind+"_bus_requests"] += 1
        b = i["bus"]
        if b["ack"]:
            matches = [j for j in self.jobs if j["sid"] is None and not j["aborted"] and j["mid"]==b["mid"] and (j["owner"]["kind"]=="load")==b["ack_to_load"]]
            assert len(matches)==1 and not any(j["sid"]==b["sid"] and not j["response"] and not j["aborted"] for j in self.jobs)
            matches[0].update(sid=b["sid"],ack_tick=tick)
            self.counts["direction_acks"] += 1
        if b["response"]:
            matches = [j for j in self.jobs if j["sid"]==b["response_id"] and not j["response"] and not j["aborted"] and (j["owner"]["kind"]=="load")==b["response_to_load"]]
            assert len(matches)==1 and not b["error"] and not b["nderr"]
            matches[0]["response"] = dict(tick=tick,data=b["data"],error=b["error"],nderr=b["nderr"])
            self.counts["actual_original_responses"] += 1
        for bank in range(3):
            p = f"io_replay_{bank}_"
            if pre[p+"valid"] and i["replay_ready"][bank]:
                s = self.bylq[120*pre[p+"bits_uop_lqIdx_flag"]+pre[p+"bits_uop_lqIdx_value"]]
                slot = pre[p+"bits_replayQueueIdx"]
                assert self.live(s) and not s["sent"] and s["grant"] is None and self.leases[s["uid"]] is s and slot % 3==bank
                replay_metadata(pre,p+"bits_",s["last"])
                assert (slot not in self.slots or self.slots[slot] is s) and (s["slot"] is None or s["slot"]==slot)
                s["grant"],s["slot"],self.slots[slot] = slot,slot,s
                self.counts["actual_replay_grants"] += 1
        next_b = [None]*3
        for lane,q in enumerate(i["bypass"]):
            p = f"io_bypass_{lane}_"
            if q["valid"]:
                s = self.bylq[lq(q["lq"])]
                assert self.live(s) and s["grant"] is not None
                j = s["attempts"][-1]
                assert j["response"] and not j["consumed"] and not j["aborted"]
                assert post[p+"s1Resp_valid"] and post[p+"s1Resp_bits_paddr"]==s["pa"]
                assert post["io_ldExceptionInfo_valid"] and not post["io_ldExceptionInfo_bits_exceptionVec_19"] and not post["io_ldExceptionInfo_bits_exceptionVec_5"]
                next_b[lane] = s,j
            if self.bpipe[lane] is not None:
                s,j = self.bpipe[lane]
                r = j["response"]
                assert post[p+"s2Resp_valid"] and post[p+"s2Resp_bits_data"]==r["data"]*((1<<64)+1) and not post[p+"s2Resp_bits_derr"] and not post[p+"s2Resp_bits_nderr"], "original returned SID bytes, not a later SID owner"
                j["consumed"] = True
                self.counts["actual_original_load_data_consumptions"] += 1
        self.bpipe = next_b
        if pre["io_cmoOpReq_valid"] and i["cache_ready"]:
            matches = [s for s in self.active("store") if s["order"]==head and s.get("cbo") is not None and s["address"]["paddr"]==pre["io_cmoOpReq_bits_address"]]
            assert len(matches)==1 and self.cache is None
            s = matches[0]
            assert s.get("s2") and "data" in s and s["cbo"]==pre["io_cmoOpReq_bits_opcode"], "original CBO opcode"
            s["cache_request"] = tick
            self.cache = s
            self.counts["cache_requests"] += 1
        if i["cache_response"]:
            assert self.cache is not None and pre["io_cmoOpResp_ready"] and not i["cache_denied"] and not i["cache_corrupt"]
            self.cache["cache_response"] = tick
            self.cache = None
            self.counts["cache_responses"] += 1
        if pre["io_mmioStout_valid"] and i["writeback_ready"]:
            s = self.owner(dict(flag=bool(pre["io_mmioStout_bits_robIdx_flag"]),value=pre["io_mmioStout_bits_robIdx_value"],former=bool(pre["io_mmioStout_bits_robIdx_isFormer"])),"store")
            assert self.live(s) and s["order"]==head and s["wb"] is None
            assert pre["io_stExceptionInfo_bits_vaddr"]==s["address"]["vaddr"] and pre["io_stExceptionInfo_bits_isHyper"]==int(s["address"]["hyper"])
            assert not pre["io_mmioStout_bits_exceptionVec_7"] and not pre["io_mmioStout_bits_exceptionVec_19"]
            if s.get("cbo")==3:
                assert s["consumed"]=={0}, "zero WB requires its own actual original zero transfer"
            elif s.get("cbo") is not None:
                assert "cache_response" in s
            else:
                assert s["attempts"][-1]["response"]
            s["wb"] = tick
            self.counts["actual_original_WB_fires"] += 1
        for lane in range(2):
            p = f"io_sbuffer_req_{lane}_"
            if pre[p+"valid"] and i["sbuffer_ready"][lane]:
                s = next(s for s in self.active("store") if s.get("memory")==0 and s.get("cbo") in (None,3) and not s["consumed"])
                a = s["address"]
                assert s.get("s2") and "data" in s and s["order"]<=head
                assert pre[p+"bits_addr"]==a["paddr"] and pre[p+"bits_vaddr"]==a["vaddr"] and pre[p+"bits_mask"]==255 and pre[p+"bits_wline"]==int(s.get("cbo")==3)
                expected = 0 if s.get("cbo")==3 else s["data"] & ((1<<64)-1)
                assert pre[p+"bits_data"] & ((1<<64)-1)==expected, "actual original Sbuffer/zero bytes"
                s["consumed"],s["last_fire"] = {0},tick
                self.counts["actual_original_Sbuffer_fragments"] += 1
        for s in prepared:
            del self.valid[s["pos"]]
        if cut is not None:
            vl = [s for s in self.valid.values() if s["order"]>=cut]
            vs = [s for s in self.active("store") if s["order"]>=cut]
            assert len(vl)==120 and len(vs)==128 and all(not s["consumed"] and not s["attempts"] for s in vs)
            self.recovery = dict(start_tick=tick,lq_target=self.lt-len(vl),sq_target=min(s["pos"] for s in vs),lq=None,sq=None)
            self.recoveries.append(self.recovery)
            for s in self.program:
                if s["order"]>=cut and not s["rob_cancelled"]:
                    s["rob_cancelled"] = True
                    if self.live(s):
                        s["status"] = "cancelled"
                        self.valid.pop(s["pos"],None) if s["kind"]=="load" else None
            self.rar,self.raw,self.leases,self.slots = [],[],{},{}
            self.counts["shared_full_redirects"] += 1
        delta = (pointer(post,"io_sqDeqPtr_")-self.sh) % 256
        assert delta<=2 and post["io_toLsqEnqCtrl_sqDeq_valid"]==int(bool(delta))
        assert not delta or post["io_toLsqEnqCtrl_sqDeq_bits"]==delta
        for pos in range(self.sh,self.sh+delta):
            s = self.bysq[pos]
            assert self.live(s) and s.get("s2") and "data" in s
            if s.get("cbo") is None and s.get("memory")==0:
                assert s["consumed"]=={0} and s["last_fire"]+2==tick, "original complete SQ prefix, not younger effects"
            elif s.get("memory")==1:
                assert s["attempts"][-1]["sid"] is not None
            else:
                assert s["wb"] is not None and s["wb"]<tick
            s["status"] = "complete"
        self.sh += delta
        count = post["io_toLsqEnqCtrl_lqDeq_bits"] if post["io_toLsqEnqCtrl_lqDeq_valid"] else 0
        assert count==len(self.report_next), "actual VLQ credits must equal previously prepared original prefix"
        for s in self.report_next:
            assert self.live(s) and s["sent"] and s["pos"]==self.lh
            s["status"] = "complete"
            self.lh += 1
        self.report_next = prepared
        if self.recovery:
            r = self.recovery
            if post["io_toLsqEnqCtrl_lqRedirectPtr_valid"]:
                self.lt = max(self.lh,r["lq_target"])
                r["lq"] = 120*post["io_toLsqEnqCtrl_lqRedirectPtr_bits_flag"]+post["io_toLsqEnqCtrl_lqRedirectPtr_bits_value"]
                assert r["lq"]==self.lt % 240
            if post["io_toLsqEnqCtrl_sqRedirectPtr_valid"]:
                self.st = r["sq_target"]
                r["sq"] = pointer(post,"io_toLsqEnqCtrl_sqRedirectPtr_bits_")
                assert r["sq"]==self.st % 256
            if r["lq"] is not None and r["sq"] is not None and not post["io_toLsqEnqCtrl_lqRecoverStall"] and not post["io_toLsqEnqCtrl_sqRecoverStall"]:
                r["settled_tick"] = tick
                self.recovery = None
        assert len(self.rar)<=96 and len(self.raw)<=56 and len(self.leases)<=120
        assert 0<=self.st-self.sh<=128 and 0<=self.lt-self.lh<=120
        external = [j for j in self.jobs if not j["response"] and not j["aborted"]]
        assert len(external)<=16
        if (self.st-self.sh,self.lt-self.lh,len(self.rar),len(self.raw),len(self.leases),len(external))==(128,120,96,56,120,16) and all(j["sid"] is not None for j in external):
            # A redirect can reuse exactly the same queue tails and ROBs in
            # the same epoch. Snapshot identity must include ORIGINAL UID
            # generation, not just low/absolute queue pointers.
            key = (self.epoch,self.st,self.lt,len(self.history))
            if not self.snapshots or self.snapshots[-1]["key"]!=key:
                assert not self.fair and not any(s["consumed"] or s["sent"] for s in self.active()) and post["io_sqFull"]==0
                assert len({j["mid"] for j in external})==len({j["sid"] for j in external})==16
                assert ready_head==self.sh and all("address" in self.bysq[p] for p in range(self.sh+1,self.sh+64)) and "address" not in self.bysq[self.sh]
                assert all("address" not in self.bysq[p] and "data" not in self.bysq[p] for p in range(self.sh+64,self.st))
                self.snapshots.append(dict(key=key,tick=tick,capacities=dict(sq_virtual=128,sq_physical_window=64,lq=120,rar=96,raw=56,replay=120,uncache=16,unreturned_jobs=16),
                                           uids=[s["uid"] for s in self.active()],jobs=[j["uid"] for j in external]))
        service = all(i["replay_ready"]) and all(i["sbuffer_ready"]) and i["cache_ready"] and i["writeback_ready"]
        if service and self.fair is None and self.active():
            assert not any(d["valid"] for d in i["dispatch"]) and self.snapshots
            assert self.snapshots[-1]["uids"]==[s["uid"] for s in self.active()], "fair stage must name this full generation, not cancelled old UIDs"
            self.fair = dict(start_tick=tick,snapshot_tick=self.snapshots[-1]["tick"],uids=[s["uid"] for s in self.active()],cycles=0)
        if self.fair:
            assert service and not any(d["valid"] for d in i["dispatch"]) and cut is None
            self.fair["cycles"] += 1
            if not self.active() and not external and self.cache is None and not any(self.bpipe) and not any(self.qpipe):
                self.fair["all_original_obligations_done_tick"] = tick
                self.fair_periods.append(self.fair)
                self.fair = None
        self.previous = row

    def finish(self):
        assert not self.active() and not self.leases and not self.slots and self.cache is None and not self.fair and not self.recovery
        assert self.previous["after"]["io_lqEmpty"] and self.previous["after"]["io_sqEmpty"] and not self.previous["after"]["io_replayAllocate"]
        assert len(self.fair_periods)==3 and len(self.codes)==640
        current = [s for s in self.history if s["status"]=="complete"]
        assert len(current)==744 and {s["pos"] % 256 for s in current if s["kind"]=="store"}==set(range(256))
        assert {s["pos"] % 240 for s in current if s["kind"]=="load"}==set(range(240))
        reuse = []
        for old in self.history:
            if old["status"] not in ("cancelled","reset"):
                continue
            size = 120 if old["kind"]=="load" else 64
            new = next(s for s in current if s["uid"]>old["uid"] and s["kind"]==old["kind"] and s["pos"] % size==old["pos"] % size)
            reuse.append(dict(old_uid=old["uid"],new_completed_uid=new["uid"],kind=old["kind"],physical_slot=old["pos"] % size,old_terminal=old["status"]))
        for j in self.jobs:
            assert bool(j["response"]) != bool(j["aborted"]), "external obligations must end in REAL response or explicit system reset abort"
            if j["owner"]["kind"]=="load" and not j["aborted"]:
                assert j["consumed"] or j["owner"]["status"]=="cancelled"
        self.counts.update(allocated=len(self.history),completed=744,cancelled=sum(s["status"]=="cancelled" for s in self.history),
                           reset_aborted=sum(s["status"]=="reset" for s in self.history),same_physical_slot_new_uid_complete=len(reuse),
                           external_reset_aborted=sum(bool(j["aborted"]) for j in self.jobs),
                           cancelled_original_responses_discarded=sum(bool(j["response"]) and not j["consumed"] and j["owner"]["status"]=="cancelled" for j in self.jobs))
        assert self.counts["allocated"]==self.counts["completed"]+self.counts["cancelled"]+self.counts["reset_aborted"]
        assert self.counts["actual_replay_grants"]==self.counts["original_slot_feedbacks"]
        assert self.counts["load_bus_requests"]+self.counts["store_bus_requests"]==self.counts["actual_original_responses"]+self.counts["external_reset_aborted"]
        assert self.query_sources=={0,1,2} and {lane for slot,lane in self.sta_sources}=={0,1}
        for group in self.fair_periods:
            owners = [s for s in current if s["uid"] in group["uids"] and s["kind"]=="load"]
            assert len(owners)==120 and {s["slot"] for s in owners}==set(range(120))
        assert all(len(w["samples"])==4 for w in self.reset_windows)
        return dict(counts=dict(self.counts),joint_simultaneous_snapshots=self.snapshots,fair_periods=self.fair_periods,reset_windows=self.reset_windows,
                    shared_recoveries=self.recoveries,same_slot_completed_witnesses=reuse,distinct_full_ROB_codes=len(self.codes),
                    scope="three actual directed full-capacity/fair completion generations per case, clean disjoint condition only; no full-domain random/STRESS checked acceptance")


def inspect(path):
    audit = JointAudit()
    for row in events(path):
        audit.step(row)
    return audit.finish()


def audit(name):
    assert name in ("lsq-joint-capacity-04","lsq-expanded-16")
    run = ROOT/"results"/name
    manifest,source,nodes = verify_common(run)
    full = name=="lsq-expanded-16"
    assert manifest["tests"]==({"PASS":269,"FAIL":48} if full else {"PASS":6})
    paths = paths_by_node(run)
    joint = {n:p for n,p in paths.items() if "test_joint_capacity.py::" in n}
    assert len(joint)==6 and not any(nodes[n] for n in joint)
    prior = paths_by_node(ROOT/"results/lsq-joint-capacity-03")
    totals,cases = Counter(),[]
    for node,path in sorted(joint.items()):
        result = inspect(path)
        # Reference mask correction cannot alter input or actual DUT behavior.
        old = list(events(prior[node]))
        new = events(path)
        prefix = 0
        for a,b in zip(old,new):
            assert all(a[k]==b[k] for k in RAW), (node,"03 actual prefix changed",prefix)
            prefix += 1
        assert prefix==len(old)
        if "common_reset" not in node:
            assert same_raw(path,prior[node])==prefix
        result["prior03_raw_prefix_unchanged_records"] = prefix
        totals.update(result["counts"])
        cases.append(dict(nodeid=node,journal=str(path.relative_to(run)),sha256=sha(path),**result))
    assert totals["allocated"]==5456 and totals["completed"]==4464 and totals["cancelled"]==totals["reset_aborted"]==496
    assert totals["same_physical_slot_new_uid_complete"]==992 and totals["external_reset_aborted"]==32
    assert sum(len(c["joint_simultaneous_snapshots"]) for c in cases)==22
    dest = run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    files = (Path(__file__),ROOT/"tools/audit_lsq_joint_history_v1.py",ROOT/"tools/audit_lsq_joint_history_v2.py",ROOT/"tools/audit_lsq_population_v1.py",ROOT/"tools/audit_lsq_mixed_history_v1.py",ROOT/"tools/audit_lsq_bus_v2.py",ROOT/"tools/audit_sq_initial.py")
    for f in files:
        target = dest/f.name
        if target.exists():
            assert sha(target)==sha(f)
        else:
            shutil.copy2(f,target)
    report = dict(run=name,status="six_joint_directed_cases_real_simultaneous_pools_fair_effects_and_same_slot_recovery_audited_not_full_STRESS_acceptance",tests=manifest["tests"],
                  snapshot_files=len(source),counts=dict(totals),cases=cases,auditors={f.name:sha(dest/f.name) for f in files},
                  simultaneous_original_generation_snapshots=22,actual_fair_complete_stages=18,
                  preserved_v1_rejection="v1 incorrectly hardcoded cause MA=3, MM=5, RAR=2, RAW=1. Public LoadQueueReplay.scala47-67 specifies MA=2, MM=1, RAR=9, RAW=10. v2 corrects decoder constants, does not change stimuli/reference/RTL or relax original-cause validation; v1 source is retained unchanged.",
                  preserved_v2_scope_correction="v2 correctly audited effects/leases but deduplicated two redirect snapshots by reused queue tails. v3 adds original UID generation to each snapshot key and requires fair owners equal its own snapshot owners, not the cancelled old generation. v2 report/source preserved; raw histories and tests unchanged.",
                  limits="Strict original native Wrapper53-file hierarchy. Actual full128/120/96/56/120/16 capacities coexist, not leaf unions. Eighteen fair stages stop admission and finish all original obligations; reset preserves unreset perf history while explicitly aborting32 old external reads, shared redirect repays32 old reads. All992 cancelled/reset original physical slots have newer genuinely completed witnesses. Three ROB/SQ/LQ generations execute, no raw-age sorting. Clean disjoint positive conditions do not replace eight failing full-domain random seeds or all required STRESS semantics. No known-issue/model/actor/private oracle, no DUT/denominator change or overall acceptance.")
    out = run/"joint-history-audit-v3.json"
    if out.exists():
        assert json.loads(out.read_text())==report
    else:
        out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="cases"},indent=2,ensure_ascii=False))


if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
