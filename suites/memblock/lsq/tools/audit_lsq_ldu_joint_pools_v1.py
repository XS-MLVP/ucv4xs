#!/usr/bin/env python3
"""Public UID/pool reconstruction for legal phased-capacity programs.

Physical record indices are not public. Query signatures/accepted tokens, not
invented internal slots, identify RAR/RAW records. Only quiescent snapshots are
exact pool claims; VLQ's exported credit has latency relative to child reclaim.
"""
from collections import Counter, deque

from audit_lsq_bus_v2 import pointer, rob, sq
from audit_lsq_mixed_history_v1 import Timeline
from audit_lsq_population_v1 import events, replay_metadata, validate_row


def lq(value):
    return 120*int(value["flag"])+value["value"]


class PhasedPools:
    def __init__(self):
        self.history, self.jobs, self.snapshots, self.recoveries, self.reset_windows = [], [], [], [], []
        self.counts, self.codes, self.sources = Counter(), set(), set()
        self.previous, self.epoch, self.resetting = None, 0, False
        self.restart()

    def restart(self):
        self.timeline = Timeline()
        self.sh = self.st = self.lh = self.lt = self.quiet = 0
        self.program, self.bysq, self.bylq = [], {}, {}
        self.rar, self.raw, self.leases, self.slots = {}, {}, {}, {}
        self.accepted = deque([(None,)*3, (None,)*3], maxlen=2)
        self.bpipe, self.recovery = [None]*3, None

    @staticmethod
    def live(s):return s["status"] == "active"

    def owner(self, value, kind):
        code = rob(value)
        found = [s for s in self.program if not s["rob_cancelled"] and s["kind"] == kind and rob(s["rob"]) == code]
        # Completed/retired generations can share an encoded ROB after a wrap.
        # Resolve using the actual current timeline, never by newest UID alone.
        order = self.timeline.decode(value)
        found = [s for s in found if s["order"] == order]
        assert len(found) == 1, ("public original ROB epoch", code, order, [s["uid"] for s in found])
        return found[0]

    def step(self, row):
        validate_row(row, self.previous, False)
        assert row["checked"]
        i, pre, post, tick = row["input"], row["before"], row["after"], row["post_tick"]
        self.counts["raw_records"] += 1
        if i["reset"]:
            if not self.resetting:
                active = [s for s in self.program if self.live(s)]
                pending = [j for j in self.jobs if not j["response"] and not j["aborted"]]
                if active:
                    assert len(active) == 248 and len(pending) == 16
                    assert (len(self.rar),len(self.raw),len(self.leases)) == (96,56,24)
                    assert self.snapshots[-1]["kind"] == "RAR_RAW_Uncache_peak"
                    assert all(not s.get("consumed") for s in active if s["kind"] == "store")
                    for s in active:s["status"],s["rob_cancelled"] = "reset",True
                    for job in pending:
                        assert job["sid"] is not None and not job["consumed"]
                        job["aborted"] = tick
                    self.reset_windows.append(dict(tick=tick,original_UIDs=[s["uid"] for s in active],external_jobs=[j["id"] for j in pending]))
                    self.epoch += 1
                    self.counts["active_common_system_resets"] += 1
                else:assert not pending
                self.restart()
            self.resetting = True
            self.previous = row
            return
        self.resetting = False
        assert pointer(pre,"io_sqDeqPtr_") == self.sh % 256
        head = self.timeline.decode(i["pending"],True)
        red = i["redirect"]
        cut = self.timeline.decode(red["rob"])+int(not red["flush_self"]) if red["valid"] else None
        for d in i["dispatch"]:
            if not d["valid"]:continue
            assert d["flows"] == 1 and d["need_alloc"] in (1,2) and cut is None
            order = self.timeline.decode(d["rob"],True)
            assert head <= order < head+320
            assert not any(s["order"] >= order and not s["rob_cancelled"] for s in self.program)
            s = dict(uid=len(self.history)+1,epoch=self.epoch,order=order,rob=d["rob"],kind="load" if d["need_alloc"]==1 else "store",
                     status="active",rob_cancelled=False,sent=False,attempts=[],grant=None,slot=None,last=None,consumed=set())
            self.history.append(s)
            self.program.append(s)
            self.codes.add(rob(d["rob"]))
            if s["kind"] == "load":
                s.update(pos=self.lt,bound=self.st)
                assert lq(d["load_start"]) == self.lt % 240
                assert self.lt % 240 not in self.bylq or not self.live(self.bylq[self.lt % 240])
                self.bylq[self.lt % 240] = s
                self.lt += 1
            else:
                s["pos"] = self.st
                self.bysq[self.st] = s
                self.st += 1
                assert sq(d["store_end"]) == self.st % 256
        for a in i["addresses"]:
            if not a["valid"]:continue
            pos = self.sh+(a["slot"]-self.sh)%64
            s = self.bysq[pos]
            assert self.live(s) and pos < min(self.st,self.sh+64) and a["rob"] == s["rob"] and "address" not in s
            assert not a["tlb_miss"] and not a["cross_word"] and a["last"]
            cbo = a["fu_op"]>>1&7 if a["fu_op"]&1 else None
            assert a["size"] == (4 if cbo is not None else 3) and a["mask"] == (65535 if cbo is not None else 255)
            s.update(address=a,cbo=cbo)
        for d in i["data"]:
            if not d["valid"]:continue
            pos = self.sh+(sq(d["sq"])-self.sh)%256
            s = self.bysq[pos]
            assert self.live(s) and pos < min(self.st,self.sh+64) and "data" not in s
            s["data"] = d["data"]
        ready_head = self.sh+(pointer(pre,"io_issuePtrExt_")-self.sh)%256
        assert self.sh <= ready_head <= self.sh+64
        self.rar = {k:r for k,r in self.rar.items() if r["pos"] > self.lh}
        self.raw = {k:r for k,r in self.raw.items() if r["bound"] > ready_head}
        for family in ("rar","raw"):
            records = getattr(self,family)
            for depth, field in ((1,"last"),(2,"older")):
                for lane, revoke in enumerate(i[f"{family}_revoke_{field}"]):
                    if revoke:
                        key = self.accepted[-depth][lane]
                        records.pop(key,None)
        accepted = [None]*3
        for lane,q in enumerate(i["rar_queries"]):
            r = i["raw_queries"][lane]
            assert q["valid"] == r["valid"]
            if not q["valid"]:continue
            s = self.owner(q["rob"],"load")
            assert self.live(s) and lq(q["lq"]) == s["pos"] % 240 and sq(r["sq"]) == s["bound"] % 256
            assert r["rob"] == q["rob"] and r["paddr"] == q["paddr"]
            s.setdefault("pa",q["paddr"])
            assert s["pa"] == q["paddr"] and not post[f"io_ldu_rarNukeQuery_{lane}_resp_bits_nuke"]
            key = (tick,lane)
            accepted[lane] = key
            record = dict(uid=s["uid"],pos=s["pos"],bound=s["bound"],PA=q["paddr"],mask=r["mask"],S2_tick=tick,lane=lane)
            if pre[f"io_ldu_rarNukeQuery_{lane}_req_ready"] and s["pos"] > self.lh:self.rar[key] = record
            if pre[f"io_ldu_rawNukeQuery_{lane}_req_ready"] and s["bound"] > ready_head:self.raw[key] = record
            if s["bound"]-ready_head == 128:
                assert ready_head == self.sh and self.st-self.sh == 128
                assert all(old["order"] < s["order"] for old in self.program if old["kind"] == "store" and self.sh <= old["pos"] < s["bound"])
                self.counts["actual_forward_exclusive128_queries"] += 1
            self.sources.add(lane)
        self.accepted.append(tuple(accepted))
        for packet in i["loads"]:
            e,u = packet["execution"],packet["execution"]["uop"]
            if not e["valid"]:continue
            s = self.bylq[lq(u["lq"])]
            assert self.live(s) and s["rob"] == u["rob"] and sq(u["sq"]) == s["bound"] % 256
            assert not packet["exceptions"] and not e["vector"]
            s.setdefault("pa",packet["paddr"])
            if e["replay_feedback"]:
                assert s["grant"] == e["slot"] and self.slots[e["slot"]] is s and self.leases[s["uid"]] is s
                s["grant"] = None
                self.counts["original_slot_feedbacks"] += 1
                if not e["need_replay"]:
                    del self.slots[e["slot"]]
                    del self.leases[s["uid"]]
            else:
                assert s["last"] is None
                if e["need_replay"]:self.leases[s["uid"]] = s
            if e["need_replay"]:
                assert e["causes"].bit_count() == 1 and not packet["update_address"]
            else:
                assert packet["update_address"] and not s["sent"]
                s["sent"] = True
            s["last"] = packet
        if pre["io_uncache_req_valid"] and i["bus"]["ready"]:
            value = dict(flag=bool(pre["io_uncache_req_bits_robIdx_flag"]),value=pre["io_uncache_req_bits_robIdx_value"],former=bool(pre["io_uncache_req_bits_robIdx_isFormer"]))
            s = self.owner(value,"load")
            assert s["pa"] == pre["io_uncache_req_bits_addr"] and s["last"]["execution"]["causes"] == 1
            assert not s["attempts"] or s["attempts"][-1]["consumed"]
            job = dict(id=len(self.jobs)+1,owner=s,mid=pre["io_uncache_req_bits_id"],sid=None,response=None,consumed=False,aborted=None)
            self.jobs.append(job)
            s["attempts"].append(job)
            self.counts["load_bus_requests"] += 1
            self.counts["NC_same_UID_real_new_external_jobs"] += len(s["attempts"]) > 1
        bus = i["bus"]
        if bus["ack"]:
            hits = [j for j in self.jobs if not j["aborted"] and j["sid"] is None and j["mid"] == bus["mid"]]
            assert bus["ack_to_load"] and len(hits) == 1
            assert not any(j["sid"] == bus["sid"] and not j["response"] and not j["aborted"] for j in self.jobs)
            hits[0]["sid"] = bus["sid"]
            self.counts["direction_acks"] += 1
        if bus["response"]:
            hits = [j for j in self.jobs if not j["aborted"] and not j["response"] and j["sid"] == bus["response_id"]]
            assert bus["response_to_load"] and len(hits) == 1 and not bus["error"] and not bus["nderr"]
            hits[0]["response"] = dict(tick=tick,data=bus["data"])
            self.counts["actual_responses"] += 1
        for bank in range(3):
            p = f"io_replay_{bank}_"
            if not(pre[p+"valid"] and i["replay_ready"][bank]):continue
            s = self.bylq[120*pre[p+"bits_uop_lqIdx_flag"]+pre[p+"bits_uop_lqIdx_value"]]
            slot = pre[p+"bits_replayQueueIdx"]
            assert self.live(s) and s["grant"] is None and self.leases[s["uid"]] is s and slot%3 == bank
            replay_metadata(pre,p+"bits_",s["last"])
            assert slot not in self.slots or self.slots[slot] is s
            assert s["slot"] in (None,slot)
            s["slot"],s["grant"],self.slots[slot] = slot,slot,s
            self.counts["actual_replay_grants"] += 1
        next_b = [None]*3
        for lane,b in enumerate(i["bypass"]):
            p = f"io_bypass_{lane}_"
            if b["valid"]:
                s = self.bylq[lq(b["lq"])]
                job = s["attempts"][-1]
                assert s["grant"] is not None and job["response"] and not job["consumed"]
                assert post[p+"s1Resp_valid"] and post[p+"s1Resp_bits_paddr"] == s["pa"]
                next_b[lane] = job
            if self.bpipe[lane] is not None:
                job = self.bpipe[lane]
                assert post[p+"s2Resp_valid"] and post[p+"s2Resp_bits_data"] == job["response"]["data"]*((1<<64)+1)
                assert not post[p+"s2Resp_bits_derr"] and not post[p+"s2Resp_bits_nderr"]
                job["consumed"] = True
                self.counts["actual_data_consumptions"] += 1
        self.bpipe = next_b
        if cut is not None:
            victims = [s for s in self.program if self.live(s) and s["order"] >= cut]
            assert len(victims) == 248 and not self.recovery
            for s in victims:s["status"],s["rob_cancelled"] = "cancelled",True
            self.recovery = dict(tick=tick,LQ=self.lt-120,SQ=self.st-128,lq=None,sq=None)
            self.recoveries.append(self.recovery)
            self.rar,self.raw,self.leases,self.slots = {},{},{},{}
            self.counts["shared_full_redirects"] += 1
        delta = (pointer(post,"io_sqDeqPtr_")-self.sh)%256
        assert delta <= 2
        for pos in range(self.sh,self.sh+delta):
            assert self.live(self.bysq[pos])
            self.bysq[pos]["status"] = "complete"
        self.sh += delta
        if post["io_toLsqEnqCtrl_lqDeq_valid"]:
            count = post["io_toLsqEnqCtrl_lqDeq_bits"]
            for pos in range(self.lh,self.lh+count):
                s = self.bylq[pos%240]
                assert self.live(s) and s["sent"]
                s["status"] = "complete"
            self.lh += count
        if self.recovery:
            rec = self.recovery
            if post["io_toLsqEnqCtrl_lqRedirectPtr_valid"]:
                self.lt = max(self.lh,rec["LQ"])
                assert lq(dict(flag=bool(post["io_toLsqEnqCtrl_lqRedirectPtr_bits_flag"]),value=post["io_toLsqEnqCtrl_lqRedirectPtr_bits_value"])) == self.lt%240
                rec["lq"] = tick
            if post["io_toLsqEnqCtrl_sqRedirectPtr_valid"]:
                self.st = rec["SQ"]
                assert pointer(post,"io_toLsqEnqCtrl_sqRedirectPtr_bits_") == self.st%256
                rec["sq"] = tick
            if rec["lq"] and rec["sq"] and not post["io_toLsqEnqCtrl_lqRecoverStall"] and not post["io_toLsqEnqCtrl_sqRecoverStall"]:
                rec["settled"] = tick
                self.recovery = None
        assert 0 <= self.st-self.sh <= 128 and 0 <= self.lt-self.lh <= 120 and len(self.leases) <= 120
        active = any(q["valid"] for q in (*i["queries"],*i["rar_queries"],*i["raw_queries"],*i["bypass"])) or any(q["execution"]["valid"] for q in i["loads"])
        self.quiet = 0 if active else self.quiet+1
        pending = [j for j in self.jobs if not j["response"] and not j["aborted"]]
        if self.quiet >= 6:
            self.rar = {k:r for k,r in self.rar.items() if r["pos"] > self.lh}
            self.raw = {k:r for k,r in self.raw.items() if r["bound"] > ready_head}
            assert len(self.rar) <= 96 and len(self.raw) <= 56
            capacities = (self.st-self.sh,self.lt-self.lh,len(self.rar),len(self.raw),len(self.leases),len(pending))
            kind = "RAR_RAW_Uncache_peak" if capacities == (128,120,96,56,24,16) else "LRQ_LQ_peak" if capacities == (128,120,0,56,120,0) else None
            if kind:
                key = (self.epoch,self.st,self.lt,kind)
                if not self.snapshots or self.snapshots[-1]["key"] != key:
                    assert not {r["uid"] for r in self.rar.values()} & self.leases.keys()
                    assert ready_head == self.sh and "address" not in self.bysq[self.sh]
                    assert all("address" in self.bysq[p] for p in range(self.sh+1,self.sh+64))
                    assert all("address" not in self.bysq[p] and "data" not in self.bysq[p] for p in range(self.sh+64,self.st))
                    assert not post["io_sqFull"]
                    if kind == "LRQ_LQ_peak":assert head+304 == max(s["order"] for s in self.program)+1
                    self.snapshots.append(dict(key=key,kind=kind,tick=tick,quiet_edges=self.quiet,
                                               capacities=dict(SQ=capacities[0],LQ=capacities[1],RAR=capacities[2],RAW=capacities[3],LRQ=capacities[4],external=capacities[5]),
                                               original_RAR_UIDs=sorted(r["uid"] for r in self.rar.values()),original_RAW_UIDs=sorted(r["uid"] for r in self.raw.values()),
                                               original_LRQ_UIDs=sorted(self.leases),external_jobs=[j["id"] for j in pending]))
        self.previous = row

    def finish(self, *, passed):
        current = [s for s in self.history if s["status"] == "complete"]
        reuse = []
        for old in self.history:
            if old["status"] not in ("cancelled","reset"):continue
            size = 120 if old["kind"] == "load" else 64
            new = next((s for s in current if s["uid"] > old["uid"] and s["kind"] == old["kind"] and s["pos"]%size == old["pos"]%size),None)
            if new:reuse.append(dict(old_UID=old["uid"],new_completed_UID=new["uid"],kind=old["kind"],physical_slot=old["pos"]%size,reason=old["status"]))
            elif passed:raise AssertionError(("missing same-slot new UID completion",old["uid"]))
        pending = [j for j in self.jobs if not j["response"] and not j["aborted"]]
        if passed:
            assert not any(self.live(s) for s in self.history) and not pending and not self.leases and not self.slots and not self.recovery
            assert self.counts["actual_replay_grants"] == self.counts["original_slot_feedbacks"]
            assert len(self.codes) == 640 and self.sources == {0,1,2}
            assert all(j["consumed"] or j["aborted"] or j["owner"]["status"] == "cancelled" for j in self.jobs)
            assert sum(s["kind"] == "LRQ_LQ_peak" for s in self.snapshots) == 3
            assert len(current) == 1104 and self.sh == self.st == 396 and self.lh == self.lt == 708
        self.counts.update(allocated=len(self.history),completed=len(current),cancelled=sum(s["status"]=="cancelled" for s in self.history),reset_aborted=sum(s["status"]=="reset" for s in self.history),
                           pending_external=len(pending),external_reset_aborted=sum(bool(j["aborted"]) for j in self.jobs),same_slot_new_UID_completed=len(reuse))
        return dict(counts=dict(self.counts),snapshots=self.snapshots,shared_recoveries=self.recoveries,common_resets=self.reset_windows,
                    same_slot_completion_witnesses=reuse,ROB_codes=len(self.codes),limits="Quiescent public accepted-query/UID reconstruction; no invented internal RAR/RAW slot. Effects and source-stage gates are separately required. No blanket transient/vector/split unreachable claim.")


def inspect(path, *, passed):
    audit = PhasedPools()
    for row in events(path):audit.step(row)
    return audit.finish(passed=passed)
