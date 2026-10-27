"""One absolute ROB timeline and public original-UID/effect ledgers.

No reference/last_change/private signal/known-issue reads. WrapperEnv remains
strict for every cycle. This is a new driver, not an enlargement of the old
two-load bus actor or MemoryOwners' raw encoded ROB ordering.
"""
from collections import Counter
from dataclasses import replace
import random

from lsqverify.forward.types import Query, Translation
from lsqverify.load_queue.types import Bypass, Load
from lsqverify.lsq_wrapper.types import Address, Bus, Data, Dispatch, Inputs
from lsqverify.psq.types import Attributes
from lsqverify.rar.types import Query as RarQuery, Release
from lsqverify.raw.types import Query as RawQuery, SqPtr
from lsqverify.replay.types import Cause, Refill, StoreWakeup, TlbHint
from lsqverify.vlq.types import QueuePtr, Redirect, RobPtr
from .memory_owners import cached_load
from .special_owners import SpecialStore


def rob_pointer(order):
    return RobPtr(bool(order//320 % 2), order//2 % 160, not bool(order % 2))


def sq_number(pins, prefix):
    return 128*pins[prefix+"first_flag"]+64*pins[prefix+"second_flag"]+pins[prefix+"value"]


class MixedOwners:
    KINDS = ("cached", "nc_load", "mmio_load", "io_load", "store", "nc_store", "io_store", "cbo")
    WEIGHTS = (30, 12, 3, 2, 36, 6, 4, 7)

    def __init__(self, env, seed):
        self.env, self.seed, self.rng = env, seed, random.Random(seed)
        self.history, self.program, self.jobs = [], [], []
        self.by_sq, self.by_lq, self.lq_valid = {}, {}, {}
        self.sequence = self.edge = self.rob_tail = 0
        self.sq_head = self.sq_tail = self.lq_head = self.lq_tail = 0
        self.s2, self.qpipe, self.bpipe = [None]*2, [None]*3, [None]*3
        self.recovery = self.redirect_due = self.cache_job = None
        self.settle, self.fair = 0, False
        self.counts, self.peaks, self.kinds, self.causes = Counter(), Counter(), Counter(), Counter()
        env.emit("mixed_seed", seed=seed, full_cycle_reference=True,
                 domain="one_absolute_ROB640_SQ256_LQ240_public_producer",
                 sid_reusable_after_response_not_consumption=True,
                 limits="first mixed implementation; active reset and coupled-capacity are separate required work, not yet claimed")

    @staticmethod
    def live(s):
        return not s["complete"] and s["aborted"] is None

    def active(self, kind=None):
        return [s for s in self.history if self.live(s) and (kind is None or s["kind"] == kind)]

    def pending(self):
        return next((s["order"] for s in self.program if not s["retired"] and not s["rob_cancelled"]), self.rob_tail)

    def chance(self, probability):
        return self.fair or self.rng.random() < probability

    def retired_prefix(self):
        width = 8 if self.fair else self.rng.randrange(5)
        for s in [s for s in self.program if not s["retired"] and not s["rob_cancelled"]][:width]:
            # Leave finite RAW/translation recovery latency before commit.
            # Ordinary execution completion still does not require Sbuffer.
            if s["executed"] is None or self.edge-s["executed"] < 8 or s["fault"]:
                break
            s["retired"] = True
            self.counts["rob_executed_prefix_retired"] += 1

    def executed(self, s):
        if s["executed"] is None:
            s["executed"] = self.edge

    def make(self, kind, *, unique=False):
        r = self.rng
        self.sequence += 1
        uid, order = self.sequence, self.rob_tail
        self.rob_tail += 1
        is_load = kind in self.KINDS[:4]
        size = r.randrange(5) if kind in ("store", "cached") else 3
        offset = r.choice((0, 4, 8, 12)) if size < 4 and kind in ("store", "cached") else 0
        block = uid+32 if unique or kind.endswith("load") else r.randrange(8)
        va, pa = 0x100000+64*block+offset, 0xA100000+64*block+offset
        if not unique and kind in ("store", "cached") and r.randrange(6) == 0:
            va += 0x100000  # A legal VA synonym, never a known-failure filter.
        s = dict(uid=uid, order=order, kind="load" if is_load else "store", subtype=kind,
                 retired=False, rob_cancelled=False, complete=False, aborted=None, executed=None, fault=False,
                 attempts=[], grant=None, admitted_edge=self.edge)
        if is_load:
            pos = self.lq_tail
            self.lq_tail += 1
            load = cached_load(pos, rob_pointer(order), self.sq_tail, va, pa, size=size)
            older = self.active("store")
            wait = bool(older) and not unique and r.randrange(3) == 0
            dependency = SqPtr.encode(r.choice(older)["position"]) if wait else SqPtr()
            uop = replace(load.execution.uop, integer_write=size < 4, vector_write=size == 4,
                          store_set_hit=wait, load_wait=wait, strict=wait and bool(r.randrange(2)),
                          wait_sq=dependency, checkpoint=17*uid, destination=1+uid % 200)
            load = replace(load, execution=replace(load.execution, uop=uop, vector=size == 4, aligned_type=size), hyper=bool(uid & 1), nonleaf=bool(uid & 2),
                           gpaddr=0x201000000+pa % 0x100000)
            extra = None if unique else r.choice((None, None, None, Cause.TLB_MISS, Cause.CACHE_REPLAY, Cause.CACHE_MISS, Cause.WAY_PREDICTION, Cause.BANK_CONFLICT))
            phase = "s3" if extra == Cause.TLB_MISS else "new"
            if kind != "cached":
                load = replace(load, execution=replace(load.execution, nc=kind == "nc_load"), mmio=kind != "nc_load", memory_backed=kind != "io_load")
                extra, phase = Cause.UNCACHE, "s3"
            s.update(position=pos, load=load, sent=False, phase=phase, next_cause=extra if phase == "s3" else None,
                     extra=extra, initial=False, rounds=0, mshr=uid % 16, tlb_id=uid % 16, query_result={})
            key = QueuePtr.encode(pos)
            assert key not in self.by_lq or not self.live(self.by_lq[key])
            self.by_lq[key], self.lq_valid[pos] = s, s
        else:
            pos = self.sq_tail
            self.sq_tail += 1
            cbo = r.randrange(4) if kind == "cbo" else None
            owner = SpecialStore(pos, rob_pointer(order), va, pa, size, r.getrandbits(128),
                                 cbo=cbo, memory={"nc_store": 1, "io_store": 2}.get(kind, 0), hyper=bool(uid & 1))
            s.update(position=pos, owner=owner, address_parts=0, data_sent=False, s2_done=False,
                     consumed=set(), wb=None, cache_req=None, cache_resp=None, last_fire=None, misses=0)
            self.by_sq[pos] = s
        self.history.append(s)
        self.program.append(s)
        self.kinds[kind] += 1
        self.counts["allocated"] += 1
        return s

    def dispatch(self, limit, *, forced=None):
        items, packet = [], [Dispatch()]*8
        for _ in range(limit):
            if self.rob_tail-self.pending() >= 300:
                break
            kind = forced or self.rng.choices(self.KINDS, self.WEIGHTS)[0]
            is_load = kind in self.KINDS[:4]
            if (self.lq_tail-self.lq_head >= 120) if is_load else (self.sq_tail-self.sq_head >= 128):
                break
            items.append(self.make(kind, unique=forced is not None))
        for lane, s in zip(sorted(self.rng.sample(range(8), len(items))), items):
            packet[lane] = Dispatch(True, 1 if s["kind"] == "load" else 2, rob_pointer(s["order"]), 1,
                                    load_start=QueuePtr.encode(s["position"]) if s["kind"] == "load" else QueuePtr(),
                                    store_end=SqPtr.encode(s["position"]+1) if s["kind"] == "store" else SqPtr())
        return tuple(packet), items

    def lookup_rob(self, pins, prefix, kind):
        identity = pins[prefix+"flag"], pins[prefix+"value"], pins[prefix+"isFormer"]
        matches = [s for s in self.history if s["kind"] == kind and not s["rob_cancelled"] and
                   (int(rob_pointer(s["order"]).flag), rob_pointer(s["order"]).value, int(rob_pointer(s["order"]).former)) == identity]
        assert len(matches) == 1, ("public original ROB generation", identity, [s["uid"] for s in matches])
        return matches[0]

    def redirect(self, cutoff, source):
        if self.recovery is not None or self.settle:
            return None
        assert cutoff >= self.pending(), ("redirect before retired ROB head", cutoff, self.pending())
        victims = [s for s in self.program if not s["retired"] and not s["rob_cancelled"] and s["order"] >= cutoff]
        if not victims:
            return None
        assert all(not s["consumed"] and not s["attempts"] and s["cache_req"] is None for s in victims if s["kind"] == "store" and self.live(s))
        cancelled_lq = [s for s in self.lq_valid.values() if s["order"] >= cutoff]
        cancelled_sq = [s for s in victims if s["kind"] == "store" and self.live(s)]
        self.recovery = dict(cutoff=cutoff, source=source, victims=victims, cancelled_lq=cancelled_lq,
                             lq_target=self.lq_tail-len(cancelled_lq), sq_target=min((s["position"] for s in cancelled_sq), default=self.sq_tail),
                             lq=None, sq=None, age=0)
        return Redirect(True, rob_pointer(cutoff), True)

    def plan(self, *, admit=True, execute=True, effects=True, forced=None):
        self.retired_prefix()
        intent = dict(dispatch=[], addresses=[], data=[], queries=[None]*3, loads=[None]*3, bypass=[None]*3)
        ready0, ready1 = (effects and self.chance(.65) for _ in range(2))
        fields = dict(pending=rob_pointer(self.pending()), pending_next=rob_pointer(self.pending()),
                      attributes=tuple(s["owner"].attributes(last=last) if s is not None else Attributes()
                                       for s, last in (x if x is not None else (None, True) for x in self.s2)),
                      sbuffer_ready=(ready0, ready0 and ready1),
                      cache_ready=effects and self.chance(.7), writeback_ready=effects and self.chance(.65))
        red = None
        if self.redirect_due is not None:
            red = self.redirect(*self.redirect_due)
            if red is not None:
                self.redirect_due = None
        elif admit and not self.fair and self.chance(.015):
            candidates = [s for s in self.program if not s["retired"] and not s["rob_cancelled"] and s["order"] > self.pending()]
            if candidates:
                red = self.redirect(self.rng.choice(candidates)["order"], "external_branch")
        if red is not None:
            fields["redirect"] = red
        stalled = self.recovery is not None or self.settle or self.env.observed["io_toLsqEnqCtrl_lqRecoverStall"] or self.env.observed["io_toLsqEnqCtrl_sqRecoverStall"]
        if admit and not stalled and red is None and self.chance(.7):
            fields["dispatch"], intent["dispatch"] = self.dispatch(self.rng.randint(1, 8), forced=forced)
        addresses, data, wakes = [Address()]*2, [Data()]*2, [StoreWakeup()]*2
        if execute and red is None:
            bank = [s for s in self.active("store") if s["admitted_edge"] < self.edge and 0 <= s["position"]-self.sq_head < 64]
            self.rng.shuffle(bank)
            old_s2 = [x[0] for x in self.s2 if x is not None]
            for lane, s in enumerate([s for s in bank if not s["s2_done"] and s not in old_s2][:2]):
                if self.chance(.6):
                    miss = not self.fair and not s["address_parts"] and s["misses"] == 0 and self.chance(.08)
                    address = s["owner"].address(tail=bool(s["address_parts"]), miss=miss)
                    addresses[lane] = address
                    if not miss:
                        wakes[lane] = StoreWakeup(True, SqPtr.encode(s["position"]))
                    intent["addresses"].append((s, lane, address.last, miss))
            for lane, s in enumerate([s for s in bank if not s["data_sent"]][:2]):
                if self.chance(.6):
                    data[lane] = s["owner"].data()
                    intent["data"].append(s)
        fields.update(addresses=tuple(addresses), data=tuple(data), address_wakeups=tuple(wakes))
        fields["translations"] = tuple(Translation(s["load"].paddr, s["aborted"] is not None or bool(red and s["order"] >= self.recovery["cutoff"]))
                                        if s is not None and forward else Translation()
                                        for s, forward in (x if x is not None else (None, False) for x in self.qpipe))
        queries, raw, rar, packets, bypasses = [Query()]*3, [RawQuery()]*3, [RarQuery()]*3, [Load()]*3, [Bypass()]*3
        if execute and red is None:
            candidates = [s for s in self.active("load") if s["admitted_edge"] < self.edge]
            self.rng.shuffle(candidates)
            for lane, s in enumerate([s for s in candidates if s["phase"] in ("new", "retry", "nc_query")][:3]):
                if self.chance(.6):
                    q, u = s["load"].execution, s["load"].execution.uop
                    forward = s["subtype"] == "cached"
                    if forward:
                        queries[lane] = Query(True, q.vaddr, u.sq, (u.operation >> 1) & 7, u.load_wait, u.strict, u.wait_sq)
                        raw[lane] = RawQuery(True, u.rob, u.sq, s["load"].paddr, q.mask, True, u.rvc, u.ftq, u.offset, u.checkpoint)
                    rar[lane] = RarQuery(True, u.rob, u.lq, s["load"].paddr, True, q.nc)
                    intent["queries"][lane] = (s, forward)
            for lane, s in enumerate([s for s in candidates if s["phase"] == "s3"][:3]):
                if self.chance(.7):
                    cause = s["next_cause"]
                    q = replace(s["load"].execution, need_replay=cause is not None, causes=0 if cause is None else 1 << cause,
                                replay_feedback=s["grant"] is not None, slot=s["grant"] or 0, handled=cause == Cause.CACHE_MISS,
                                mshr=s["mshr"], tlb_id=s["tlb_id"], address_sq=s.get("address_sq", s["load"].execution.uop.wait_sq),
                                data_sq=s.get("data_sq", s["load"].execution.uop.wait_sq))
                    packets[lane], intent["loads"][lane] = replace(s["load"], execution=q), s
            for lane, s in enumerate([s for s in candidates if s["phase"] == "bypass"][:3]):
                if self.chance(.65):
                    bypasses[lane] = Bypass(True, s["load"].execution.uop.lq, s["load"].execution.nc, s["load"].mmio)
                    intent["bypass"][lane] = s
        fields.update(queries=tuple(queries), raw_queries=tuple(raw), rar_queries=tuple(rar), loads=tuple(packets), bypass=tuple(bypasses),
                      replay_ready=tuple(execute and red is None and self.chance(.65) for _ in range(3)))
        waiting = [s for s in self.active("load") if s["initial"] and s["phase"] == "wait"]
        misses = [s for s in waiting if s["last_cause"] == Cause.CACHE_MISS]
        tlbs = [s for s in waiting if s["last_cause"] == Cause.TLB_MISS]
        if execute and misses and self.chance(.7):
            fields["refills"] = (Refill(True, self.rng.choice(misses)["mshr"]), Refill())
        if execute and tlbs and self.chance(.7):
            fields["slow_tlb"] = TlbHint(True, self.rng.choice(tlbs)["tlb_id"])
        # Coherence release uses an actual original Load line, not random bits.
        queried = [s for s in self.active("load") if s.get("queried")]
        if execute and queried and not self.fair and self.chance(.08):
            fields["release"] = Release(True, self.rng.choice(queried)["load"].paddr)
        if self.cache_job is not None and effects and self.chance(.35):
            fields.update(cache_response=True, cache_denied=self.cache_job["denied"], cache_corrupt=self.cache_job["corrupt"])
        outstanding = [j for j in self.jobs if j["response"] is None]
        bus = Bus(outstanding=bool(self.seed & 1), ready=effects and len(outstanding) < 16 and self.chance(.7))
        unacked = [j for j in outstanding if j["sid"] is None]
        busy = {j["sid"] for j in outstanding if j["sid"] is not None}
        if effects and unacked and len(busy) < 16 and self.chance(.6):
            job = min(unacked, key=lambda j: j["uid"]) if self.fair else self.rng.choice(unacked)
            bus = replace(bus, ack=True, ack_to_load=job["owner"]["kind"] == "load", mid=job["mid"], sid=self.rng.choice(sorted(set(range(16))-busy)))
        acked = [j for j in outstanding if j["sid"] is not None]
        if effects and acked and self.chance(.35):
            job = min(acked, key=lambda j: j["uid"]) if self.fair else self.rng.choice(acked)
            bus = replace(bus, response=True, response_to_load=job["owner"]["kind"] == "load", response_id=job["sid"],
                          data=job["data"], error=job["error"], nderr=job["nderr"])
        fields["bus"] = bus
        return Inputs(**fields), intent

    async def step(self, **options):
        packet, intent = self.plan(**options)
        assert not packet.sbuffer_ready[1] or packet.sbuffer_ready[0], "actual Sbuffer ready is a prefix"
        self.env.emit("mixed_intent", seed=self.seed, cycle=self.edge, absolute_pending=self.pending(),
                      dispatch=[dict(uid=s["uid"], kind=s["subtype"], position=s["position"], absolute_rob=s["order"]) for s in intent["dispatch"]])
        red, prepared = packet.redirect, []
        for pos in range(self.lq_head, self.lq_head+8):
            s = self.lq_valid.get(pos)
            if s is None or not s["sent"] or red.valid and s["order"] >= self.recovery["cutoff"]:
                break
            prepared.append(s)
        await self.env.cycle(packet)
        pre, post, tick = self.env.pre_observed, self.env.observed, self.env.last_tick
        self.edge += 1
        self.counts["raw_cycles"] += 1
        for s in prepared:
            del self.lq_valid[s["position"]]
        for s, last in (x for x in self.s2 if x is not None):
            if self.live(s) and last:
                s["s2_done"] = True
        self.s2 = [None]*2
        for s, lane, last, miss in intent["addresses"]:
            if miss:
                s["misses"] += 1
            else:
                s["address_parts"] += 1
                self.s2[lane] = (s, last)
        for s in intent["data"]:
            assert not s["data_sent"]
            s["data_sent"] = True
        for s in self.active("store"):
            if s["s2_done"] and s["data_sent"] and s["subtype"] == "store":
                self.executed(s)
        for lane, item in enumerate(self.qpipe):
            if item is None:
                continue
            s, forward = item
            if not self.live(s) or red.valid and s["order"] >= self.recovery["cutoff"]:
                continue
            cause = None
            if forward:
                p = f"io_forward_{lane}_s2Resp_"
                assert post[p+"valid"]
                for flag, reason, field in (("addrInvalid", Cause.ADDRESS_DEPENDENCE, "address_sq"), ("dataInvalid", Cause.FORWARD_FAILURE, "data_sq")):
                    if post[p+"bits_"+flag+"_valid"]:
                        cause = reason
                        s[field] = SqPtr(bool(post[p+"bits_"+flag+"_bits_first_flag"]), bool(post[p+"bits_"+flag+"_bits_second_flag"]), post[p+"bits_"+flag+"_bits_value"])
                        break
                if cause is None and (post[p+"bits_forwardInvalid"] or post[p+"bits_matchInvalid"]):
                    cause = Cause.STORE_MULTI_MATCH
            result = s["query_result"]
            if cause is None:
                cause = Cause.RAR_CAPACITY if result["rar_denied"] else Cause.RAW_CAPACITY if result["raw_denied"] else (Cause.VIOLATION if forward else Cause.UNCACHE) if result["nuke"] else None
            if cause is None and not s["initial"]:
                cause = s["extra"]
            s.update(phase="s3", next_cause=cause)
        self.qpipe = intent["queries"]
        for lane, item in enumerate(self.qpipe):
            if item is not None:
                s, forward = item
                assert post[f"io_ldu_rarNukeQuery_{lane}_resp_valid"]
                s.update(phase="query", queried=True, query_result=dict(raw_denied=forward and not pre[f"io_ldu_rawNukeQuery_{lane}_req_ready"],
                          rar_denied=not pre[f"io_ldu_rarNukeQuery_{lane}_req_ready"], nuke=bool(post[f"io_ldu_rarNukeQuery_{lane}_resp_bits_nuke"])))
                self.counts["original_query_rounds"] += 1
        for lane, s in enumerate(intent["loads"]):
            if s is None:
                continue
            q = packet.loads[lane].execution
            if q.replay_feedback:
                assert s["grant"] == q.slot
                s["grant"] = None
                self.counts["original_slot_feedbacks"] += 1
            else:
                assert not s["initial"]
                s["initial"] = True
            s["rounds"] += 1
            s["last_cause"] = Cause(q.causes.bit_length()-1) if q.need_replay else None
            if q.need_replay:
                self.causes[s["last_cause"].name] += 1
                s["phase"] = "wait"
            else:
                assert not s["sent"]
                if s["subtype"] != "cached":
                    assert s["attempts"][-1]["consumed"]
                s.update(sent=True, phase="finished")
                self.executed(s)
        for bank in range(3):
            p = f"io_replay_{bank}_"
            if pre[p+"valid"] and packet.replay_ready[bank]:
                s = self.by_lq[QueuePtr(bool(pre[p+"bits_uop_lqIdx_flag"]), pre[p+"bits_uop_lqIdx_value"])]
                assert self.live(s) and s["grant"] is None and s["phase"] == "wait"
                s["grant"] = pre[p+"bits_replayQueueIdx"]
                assert s["grant"] % 3 == bank
                s["phase"] = "bypass" if s["last_cause"] == Cause.UNCACHE else "retry"
                if s["phase"] == "bypass":
                    assert s["attempts"][-1]["response"] is not None
                self.counts["original_replay_grants"] += 1
        next_bypass = [None]*3
        for lane, s in enumerate(intent["bypass"]):
            p = f"io_bypass_{lane}_"
            assert post[p+"s1Resp_valid"] == int(s is not None)
            if s is not None:
                job = s["attempts"][-1]
                assert job["response"] is not None and not job["consumed"]
                self.env.expect({p+"s1Resp_bits_paddr": s["load"].paddr}, "mixed original bypass PA")
                next_bypass[lane], s["phase"] = (s, job), "data"
            due = self.bpipe[lane]
            assert post[p+"s2Resp_valid"] == int(due is not None)
            if due is not None:
                old, job = due
                self.env.expect({p+"s2Resp_bits_data": job["data"]*((1 << 64)+1), p+"s2Resp_bits_derr": int(job["error"]), p+"s2Resp_bits_nderr": int(job["nderr"])},
                                "mixed original response bytes/errors, not latest SID owner")
                job["consumed"] = True
                old["fault"] |= job["error"] or job["nderr"]
                if self.live(old):
                    old["phase"] = "nc_query"
                self.counts["original_bypass_consumptions"] += 1
        self.bpipe = next_bypass
        if pre["io_uncache_req_valid"] and packet.bus.ready:
            is_load = pre["io_uncache_req_bits_cmd"] == 0
            matches = []
            for s in self.history:
                ptr = rob_pointer(s["order"])
                if (s["kind"] == "load") != is_load or (s["attempts"] and not s["attempts"][-1]["consumed"]):
                    continue
                if not is_load and not self.live(s):
                    continue  # A cancelled Store cannot leave an elastic read.
                if (int(ptr.flag), ptr.value, int(ptr.former)) != (pre["io_uncache_req_bits_robIdx_flag"], pre["io_uncache_req_bits_robIdx_value"], pre["io_uncache_req_bits_robIdx_isFormer"]):
                    continue
                if (s["load"].paddr if is_load else s["owner"].paddr) == pre["io_uncache_req_bits_addr"]:
                    matches.append(s)
            assert len(matches) == 1, ("original external bus generation", [s["uid"] for s in matches])
            s = matches[0]
            if not is_load:
                assert s["order"] == self.pending() and s["s2_done"] and s["data_sent"]
                self.env.expect({"io_uncache_req_bits_data": s["owner"].value & ((1 << 64)-1)}, "mixed original external Store bytes", before=True)
            job = dict(uid=len(self.jobs)+1, owner=s, mid=pre["io_uncache_req_bits_id"], sid=None, response=None, consumed=False,
                       data=self.rng.getrandbits(64), error=self.rng.randrange(8) == 0, nderr=self.rng.randrange(8) == 0)
            self.jobs.append(job)
            s["attempts"].append(job)
            self.counts["load_bus_fires" if is_load else "store_bus_fires"] += 1
        if packet.bus.ack:
            hits = [j for j in self.jobs if j["sid"] is None and j["mid"] == packet.bus.mid and (j["owner"]["kind"] == "load") == packet.bus.ack_to_load]
            assert len(hits) == 1 and not any(j["sid"] == packet.bus.sid and j["response"] is None for j in self.jobs)
            hits[0]["sid"] = packet.bus.sid
            if hits[0]["owner"]["subtype"] == "nc_store":
                self.executed(hits[0]["owner"])
            self.counts["direction_acks"] += 1
        if packet.bus.response:
            hits = [j for j in self.jobs if j["response"] is None and j["sid"] == packet.bus.response_id and (j["owner"]["kind"] == "load") == packet.bus.response_to_load]
            assert len(hits) == 1
            hits[0]["response"] = tick
            self.counts["sid_responses"] += 1
        if pre["io_cmoOpReq_valid"] and packet.cache_ready:
            matches = [s for s in self.active("store") if s["subtype"] == "cbo" and s["order"] == self.pending() and s["cache_req"] is None and
                       s["owner"].paddr == pre["io_cmoOpReq_bits_address"] and s["owner"].cbo == pre["io_cmoOpReq_bits_opcode"]]
            assert len(matches) == 1 and self.cache_job is None
            s = matches[0]
            assert s["order"] == self.pending() and s["cache_req"] is None and s["s2_done"] and s["data_sent"]
            s["cache_req"] = tick
            self.cache_job = dict(owner=s, denied=self.rng.randrange(4) == 0, corrupt=self.rng.randrange(4) == 0)
            self.counts["cache_requests"] += 1
        if packet.cache_response:
            assert self.cache_job is not None and pre["io_cmoOpResp_ready"]
            self.cache_job["owner"]["cache_resp"] = self.cache_job
            self.cache_job = None
            self.counts["cache_responses"] += 1
        if pre["io_mmioStout_valid"]:
            s = self.lookup_rob(pre, "io_mmioStout_bits_robIdx_", "store")
            assert s["order"] == self.pending() and s["subtype"] in ("cbo", "io_store")
            response = s["cache_resp"] or dict(denied=False, corrupt=False)
            self.env.expect({"io_mmioStout_bits_exceptionVec_7": int(response["denied"]), "io_mmioStout_bits_exceptionVec_19": int(response["corrupt"]),
                             "io_stExceptionInfo_bits_vaddr": s["owner"].vaddr, "io_stExceptionInfo_bits_isHyper": int(s["owner"].hyper)},
                            "mixed actual WB keeps original identity and Cache errors", before=True)
            if packet.writeback_ready:
                assert s["wb"] is None
                if s["owner"].cbo == 3:
                    assert s["consumed"]
                elif s["subtype"] == "cbo":
                    assert s["cache_resp"] is not None
                else:
                    assert s["attempts"][-1]["response"] is not None
                s["wb"], s["fault"] = tick, bool(response["denied"] or response["corrupt"])
                self.executed(s)
                self.counts["store_wb_fires"] += 1
        for lane in range(2):
            p = f"io_sbuffer_req_{lane}_"
            if pre[p+"valid"] and packet.sbuffer_ready[lane]:
                s = next(s for s in self.active("store") if len(s["consumed"]) < len(s["owner"].words()))
                part = len(s["consumed"])
                va, pa, mask, value = s["owner"].words()[part]
                self.env.expect({p+"bits_vaddr": va, p+"bits_addr": pa, p+"bits_mask": mask, p+"bits_data": value, p+"bits_wline": int(s["owner"].cbo == 3)},
                                "mixed original PA bytes/zero owner actually consumed", before=True,
                                masks={p+"bits_data": sum(255 << (8*b) for b in range(16) if mask >> b & 1)})
                assert s["s2_done"] and s["data_sent"] and s["order"] <= self.pending()
                s["consumed"].add(part)
                s["last_fire"] = tick
                self.counts["store_fragment_fires"] += 1
        delta = (sq_number(post, "io_sqDeqPtr_")-self.sq_head) % 256
        assert delta <= 2 and post["io_toLsqEnqCtrl_sqDeq_valid"] == int(bool(delta))
        for pos in range(self.sq_head, self.sq_head+delta):
            s = self.by_sq[pos]
            assert self.live(s) and s["s2_done"] and s["data_sent"]
            if s["subtype"] == "store":
                assert s["consumed"] == set(range(len(s["owner"].words()))) and s["last_fire"]+2 == tick
            elif s["subtype"] == "nc_store":
                assert s["attempts"] and s["attempts"][-1]["sid"] is not None
            else:
                assert s["wb"] is not None and s["wb"] < tick
            s["complete"] = True
            self.counts["completed"] += 1
        self.sq_head += delta
        if post["io_toLsqEnqCtrl_lqDeq_valid"]:
            count = post["io_toLsqEnqCtrl_lqDeq_bits"]
            for pos in range(self.lq_head, self.lq_head+count):
                s = self.by_lq[QueuePtr.encode(pos)]
                assert self.live(s) and s["sent"]
                s["complete"] = True
                self.counts["completed"] += 1
            self.lq_head += count
        if red.valid:
            rec = self.recovery
            for s in rec["victims"]:
                s["rob_cancelled"] = True
                if self.live(s) and (s["kind"] == "store" or s in rec["cancelled_lq"]):
                    s["aborted"] = "redirect"
                    self.counts["cancelled"] += 1
                    if s["kind"] == "load":
                        self.lq_valid.pop(s["position"], None)
            self.rob_tail = rec["cutoff"]
            self.counts["shared_redirects"] += 1
        if self.recovery is not None:
            rec = self.recovery
            rec["age"] += 1
            if post["io_toLsqEnqCtrl_lqRedirectPtr_valid"]:
                rec["lq"] = 120*post["io_toLsqEnqCtrl_lqRedirectPtr_bits_flag"]+post["io_toLsqEnqCtrl_lqRedirectPtr_bits_value"]
                self.lq_tail = max(self.lq_head, rec["lq_target"])
                assert rec["lq"] == self.lq_tail % 240
            if post["io_toLsqEnqCtrl_sqRedirectPtr_valid"]:
                rec["sq"] = sq_number(post, "io_toLsqEnqCtrl_sqRedirectPtr_bits_")
                self.sq_tail = rec["sq_target"]
                assert rec["sq"] == self.sq_tail % 256
            assert rec["age"] < 80
            if rec["sq"] is not None and rec["lq"] is not None and not post["io_toLsqEnqCtrl_lqRecoverStall"] and not post["io_toLsqEnqCtrl_sqRecoverStall"]:
                self.recovery, self.settle = None, 4
                self.counts["both_recovery_responses_settled"] += 1
        elif self.settle:
            self.settle -= 1
        for source in ("io_nuke_rollback_0_", "io_nuke_rollback_1_", "io_nack_rollback_0_"):
            if post[source+"valid"]:
                s = self.lookup_rob(post, source+"bits_robIdx_", "load")
                if self.redirect_due is None or s["order"] < self.redirect_due[0]:
                    self.redirect_due = s["order"], source
        head = next((s for s in self.program if not s["retired"] and not s["rob_cancelled"]), None)
        if head is not None and head["fault"] and head["complete"]:
            self.redirect_due = head["order"], "external_trap_after_original_LSQ_completion"
        for key, value in (("sq_virtual", self.sq_tail-self.sq_head), ("lq", self.lq_tail-self.lq_head),
                           ("external_unreturned", sum(j["response"] is None for j in self.jobs))):
            self.peaks[key] = max(self.peaks[key], value)
        assert 0 <= self.sq_tail-self.sq_head <= 128 and 0 <= self.lq_tail-self.lq_head <= 120

    async def drain(self):
        self.env.reach("LSQ-STRESS.fair_drain")
        self.fair = True
        for _ in range(5000):
            await self.step(admit=False)
            if not self.active() and all(j["response"] is not None for j in self.jobs) and self.recovery is None and self.redirect_due is None:
                break
        else:
            raise AssertionError(("mixed fair drain left original obligations", self.seed, [(s["uid"], s["subtype"], s.get("phase")) for s in self.active()]))
        for _ in range(12):
            await self.step(admit=False)
        assert self.env.observed["io_lqEmpty"] and self.env.observed["io_sqEmpty"] and not self.env.observed["io_replayAllocate"]

    async def restore_cancelled_slots(self):
        for kind, size, forced in (("load", 120, "cached"), ("store", 64, "store")):
            old = [s for s in self.history if s["kind"] == kind and s["aborted"] is not None]
            def missing():
                return [s for s in old if not any(n["uid"] > s["uid"] and n["kind"] == kind and n["position"] % size == s["position"] % size and n["complete"] for n in self.history)]
            # Original mixed phase is never narrowed. This separate cleanup
            # supplies new UID completion witnesses for the cancelled slots.
            for _ in range(size*3):
                if not missing():
                    break
                await self.step(forced=forced)
                await self.drain()
            assert not missing(), ("cancelled physical slots lack new UID completion", kind, [s["uid"] for s in missing()])

    async def run(self, cycles=600):
        self.env.reach("LSQ-STRESS.seeded")
        for _ in range(cycles):
            await self.step()
        await self.drain()
        await self.restore_cancelled_slots()
        assert self.counts["allocated"] == self.counts["completed"]+self.counts["cancelled"]
        self.env.emit("mixed_final", seed=self.seed, counts=dict(self.counts), peaks=dict(self.peaks), kinds=dict(self.kinds), causes=dict(self.causes),
                      scope="mixed first implementation; independent legality/history and full-domain coverage audit still required, no STRESS checked claim")
