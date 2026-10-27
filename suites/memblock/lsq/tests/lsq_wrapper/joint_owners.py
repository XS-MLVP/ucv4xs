"""Coupled real pools plus a bounded-service external fair scheduler.

Additional directed obligations, NOT a replacement for eight full-domain
random first-failure cases. The original mixed ledger/strict WrapperEnv is
used; there are no private DUT/reference/known-issue reads or probe fixtures.
"""
from dataclasses import replace

from lsqverify.forward.types import Query, Translation
from lsqverify.load_queue.types import Bypass, Load
from lsqverify.lsq_wrapper.types import Address, Bus, Data, Dispatch, Inputs
from lsqverify.psq.types import Attributes
from lsqverify.rar.types import Query as RarQuery
from lsqverify.raw.types import Query as RawQuery, SqPtr
from lsqverify.replay.types import Cause, StoreWakeup
from lsqverify.vlq.types import QueuePtr
from .mixed_owners import MixedOwners, rob_pointer


class JointOwners(MixedOwners):
    def __init__(self, env, seed, *, sequence=0):
        super().__init__(env, seed)
        self.sequence = sequence
        self.rounds = 0
        self.serve_cursor = dict(query=0, s3=0, bypass=0)
        self._prepared = None
        self.pool_checks = []

    def lookup_rob(self, pins, prefix, kind):
        code = 320*pins[prefix+"flag"]+2*pins[prefix+"value"]+int(not pins[prefix+"isFormer"])
        base = self.pending()//640*640+code
        order = min((base-640, base, base+640), key=lambda value: abs(value-self.pending()))
        found = [s for s in self.history if s["order"] == order and s["kind"] == kind and not s["rob_cancelled"]]
        assert len(found) == 1, ("actual nearby ROB generation", order, [s["uid"] for s in found])
        return found[0]

    def make(self, kind, *, unique=True):
        s = super().make(kind, unique=True)
        if s["kind"] == "store":
            # Explicit positive capacity condition; full-domain random cases
            # keep all synonyms/split/control failures independently unchanged.
            o = s["owner"]
            s["owner"] = replace(o, vaddr=o.vaddr//64*64, paddr=o.paddr//64*64, size=3)
        else:
            load = s["load"]
            va, pa = load.execution.vaddr//64*64, load.paddr//64*64
            q = replace(load.execution, vaddr=va, mask=(1 << (1 << ((load.execution.uop.operation >> 1) & 7)))-1)
            s["load"] = replace(load, execution=q, fullva=va, paddr=pa)
        return s

    def plan(self, **unused):
        assert self._prepared is not None
        packet = self._prepared
        self._prepared = None
        return packet

    def fair_select(self, role, candidates, width):
        cursor = self.serve_cursor[role]
        selected = sorted(candidates, key=lambda s: (s["uid"] <= cursor, s["uid"]))[:width]
        if selected:
            self.serve_cursor[role] = selected[-1]["uid"]
        return selected

    def external(self, *, accept=False, ack=False, respond=False):
        bus = Bus(outstanding=True, ready=accept)
        jobs = [j for j in self.jobs if j["response"] is None]
        busy = {j["sid"] for j in jobs if j["sid"] is not None}
        waiting = [j for j in jobs if j["sid"] is None]
        if ack and waiting and len(busy) < 16:
            j = min(waiting, key=lambda job: job["uid"])
            bus = replace(bus, ack=True, ack_to_load=j["owner"]["kind"] == "load", mid=j["mid"], sid=min(set(range(16))-busy))
        assigned = [j for j in jobs if j["sid"] is not None]
        if respond and assigned:
            j = min(assigned, key=lambda job: job["uid"])
            bus = replace(bus, response=True, response_to_load=j["owner"]["kind"] == "load", response_id=j["sid"],
                          data=j["data"], error=j["error"], nderr=j["nderr"])
        return bus

    async def cycle(self, *, allocate=(), addresses=(), data=(), queries=(), s3=(), bypass=(),
                    retire=False, service=False, accept=False, ack=False, respond=False, redirect=False):
        if retire:
            self.retired_prefix()
        intent = dict(dispatch=[], addresses=[], data=[], queries=[None]*3, loads=[None]*3, bypass=[None]*3)
        fields = dict(pending=rob_pointer(self.pending()), pending_next=rob_pointer(self.pending()),
                      attributes=tuple(s["owner"].attributes(last=last) if s is not None else Attributes()
                                       for s, last in (x if x is not None else (None, True) for x in self.s2)),
                      translations=tuple(Translation(s["load"].paddr, s["aborted"] is not None) if s is not None and forward else Translation()
                                         for s, forward in (x if x is not None else (None, False) for x in self.qpipe)),
                      bus=self.external(accept=accept or service, ack=ack or service, respond=respond or service),
                      sbuffer_ready=(service, service), cache_ready=service, writeback_ready=service,
                      replay_ready=(service,)*3)
        if service and self.cache_job is not None:
            fields.update(cache_response=True, cache_denied=self.cache_job["denied"], cache_corrupt=self.cache_job["corrupt"])
        if redirect:
            assert self.redirect_due is not None
            red = self.redirect(*self.redirect_due)
            assert red is not None and not allocate
            fields["redirect"] = red
            self.redirect_due = None
        if allocate:
            assert self.recovery is None and not self.settle and len(allocate) <= 8
            assert not self.env.observed["io_toLsqEnqCtrl_lqRecoverStall"] and not self.env.observed["io_toLsqEnqCtrl_sqRecoverStall"]
            items = [self.make(kind) for kind in allocate]
            lanes, packet = sorted(self.rng.sample(range(8), len(items))), [Dispatch()]*8
            for lane, s in zip(lanes, items):
                packet[lane] = Dispatch(True, 1 if s["kind"] == "load" else 2, rob_pointer(s["order"]), 1,
                                        load_start=QueuePtr.encode(s["position"]) if s["kind"] == "load" else QueuePtr(),
                                        store_end=SqPtr.encode(s["position"]+1) if s["kind"] == "store" else SqPtr())
            fields["dispatch"], intent["dispatch"] = tuple(packet), items
        aa, dd, wake = [Address()]*2, [Data()]*2, [StoreWakeup()]*2
        for index, s in enumerate(addresses):
            lane = (index+self.rounds) % 2
            assert self.live(s) and 0 <= s["position"]-self.sq_head < 64 and not s["s2_done"] and not s["address_parts"]
            aa[lane], wake[lane] = s["owner"].address(), StoreWakeup(True, SqPtr.encode(s["position"]))
            intent["addresses"].append((s, lane, True, False))
        for index, s in enumerate(data):
            lane = (index+1+self.rounds) % 2
            assert self.live(s) and 0 <= s["position"]-self.sq_head < 64 and not s["data_sent"]
            dd[lane] = s["owner"].data()
            intent["data"].append(s)
        fields.update(addresses=tuple(aa), data=tuple(dd), address_wakeups=tuple(wake))
        ff, rr, raw = [Query()]*3, [RarQuery()]*3, [RawQuery()]*3
        for index, s in enumerate(queries):
            lane = (index+self.rounds) % 3
            load, forward = s["load"], s["subtype"] == "cached"
            q, u = load.execution, load.execution.uop
            if forward:
                ff[lane] = Query(True, q.vaddr, u.sq, u.operation >> 1 & 7, u.load_wait, u.strict, u.wait_sq)
                raw[lane] = RawQuery(True, u.rob, u.sq, load.paddr, q.mask, True, u.rvc, u.ftq, u.offset, u.checkpoint)
            rr[lane] = RarQuery(True, u.rob, u.lq, load.paddr, True, q.nc)
            intent["queries"][lane] = (s, forward)
        fields.update(queries=tuple(ff), raw_queries=tuple(raw), rar_queries=tuple(rr))
        packets, bp = [Load()]*3, [Bypass()]*3
        for index, s in enumerate(s3):
            lane = (index+self.rounds) % 3
            cause, load = s["next_cause"], s["load"]
            packets[lane] = replace(load, execution=replace(load.execution, need_replay=cause is not None, causes=0 if cause is None else 1 << cause,
                                       replay_feedback=s["grant"] is not None, slot=s["grant"] or 0,
                                       address_sq=s.get("address_sq", load.execution.uop.wait_sq), data_sq=s.get("data_sq", load.execution.uop.wait_sq)))
            intent["loads"][lane] = s
        for index, s in enumerate(bypass):
            lane = (index+self.rounds) % 3
            bp[lane] = Bypass(True, s["load"].execution.uop.lq, s["load"].execution.nc, s["load"].mmio)
            intent["bypass"][lane] = s
        fields.update(loads=tuple(packets), bypass=tuple(bp))
        self._prepared = (Inputs(**fields), intent)
        before_jobs = len(self.jobs)
        await super().step()
        for j in self.jobs[before_jobs:]:
            # Chosen response payload before any real response, not an answer
            # read from the DUT. Clean is the explicit positive-case contract.
            j.update(error=False, nderr=False)
        if self.cache_job is not None:
            self.cache_job.update(denied=False, corrupt=False)
        for s in self.active("load"):
            if s["grant"] is not None:
                assert s.setdefault("original_slot", s["grant"]) == s["grant"]
        return intent

    async def full(self):
        self.rounds += 1
        start_s, start_l, start_rob = self.sq_tail, self.lq_tail, self.rob_tail
        assert not self.active() and all(j["response"] is not None for j in self.jobs)
        kinds = ["store"]*64+["nc_load"]*16+["cached"]*104
        kinds += ["store"]*48+["nc_store", "io_store", "cbo", "cbo", "cbo", "cbo"]+["store"]*10
        for offset in range(0, len(kinds), 8):
            await self.cycle(allocate=kinds[offset:offset+8])
        stores = [s for s in self.active("store")]
        loads = [s for s in self.active("load")]
        assert len(stores) == 128 and len(loads) == 120 and self.rob_tail-start_rob == 248
        for opcode, s in enumerate([s for s in stores if s["subtype"] == "cbo"]):
            s["owner"] = replace(s["owner"], cbo=opcode)
        for index, s in enumerate(loads[16:]):
            # The last two RAW credits in the 19th three-query group follow
            # input-lane priority, not ascending UID after lane rotation. All
            # members of that group therefore keep the genuine SQ0 wait.
            # Actual accepted records are still exactly56, never57.
            wait = index < 57
            load = s["load"]
            u = replace(load.execution.uop, load_wait=wait, store_set_hit=wait, strict=False, wait_sq=SqPtr.encode(start_s))
            s.update(load=replace(load, execution=replace(load.execution, uop=u)), extra=None, phase="new")
        for offset in range(1, 64, 2):
            batch = stores[offset:min(offset+2,64)]
            await self.cycle(addresses=batch, data=batch)
        for offset in range(0,16,3):
            await self.cycle(s3=loads[offset:min(offset+3,16)], accept=True, ack=True)
        rar_accept = raw_accept = rar_refuse = raw_refuse = 0
        for offset in range(16,120,3):
            batch = loads[offset:min(offset+3,120)]
            await self.cycle(queries=batch, accept=True, ack=True)
            for lane in range(3):
                # Driven lanes follow this public producer's rotation, not
                # an internal allocation oracle or a raw UID sorting rule.
                if lane in {(index+self.rounds) % 3 for index in range(len(batch))}:
                    ra = self.env.pre_observed[f"io_ldu_rarNukeQuery_{lane}_req_ready"]
                    rw = self.env.pre_observed[f"io_ldu_rawNukeQuery_{lane}_req_ready"]
                    rar_accept += bool(ra)
                    raw_accept += bool(rw)
                    rar_refuse += not ra
                    raw_refuse += not rw
        await self.cycle(accept=True, ack=True)
        await self.cycle(accept=True, ack=True)
        for offset in range(16,120,3):
            batch = loads[offset:min(offset+3,120)]
            assert all(s["phase"] == "s3" and s["next_cause"] is not None for s in batch), [(s["uid"],s["phase"],s.get("next_cause")) for s in batch]
            await self.cycle(s3=batch, accept=True, ack=True)
        for _ in range(100):
            if sum(j["response"] is None for j in self.jobs) == 16 and all(j["sid"] is not None for j in self.jobs if j["response"] is None):
                break
            await self.cycle(accept=True, ack=True)
        else:
            raise AssertionError("coupled Uncache16 did not really accept/ack16 original NC requests")
        for _ in range(6):
            await self.cycle()
        assert (rar_accept, raw_accept, rar_refuse, raw_refuse) == (96,56,8,48)
        assert self.sq_tail-self.sq_head == 128 and self.lq_tail-self.lq_head == 120
        assert all(s["initial"] and not s["sent"] and s["phase"] == "wait" for s in loads)
        assert not stores[0]["address_parts"] and all(s["s2_done"] and s["data_sent"] for s in stores[1:64])
        assert not any(s["address_parts"] or s["data_sent"] for s in stores[64:])
        # This retained signal is NOT virtual-tail == head+128. The actual
        # PhysicalStoreQueue.sv16123 expression is registered_count > 128;
        # the current legal128 boundary still drives0. Use original credits
        # and physical issue obligations, never invent a canAccept/full port.
        assert not self.env.observed["io_sqFull"] and not self.env.observed["io_lqEmpty"]
        assert not any(self.env.observed[f"io_replay_{bank}_valid"] for bank in range(3))
        witness = dict(sq_start=start_s, lq_start=start_l, absolute_rob_start=start_rob,
                       sq_virtual=128, sq_window=64, lq=120, replay_pending=120, rar_records=96, raw_records=56,
                       uncache_original_unreturned=16, rar_refused=rar_refuse, raw_refused=raw_refuse)
        self.pool_checks.append(witness)
        self.env.emit("joint_all_pools_simultaneous", **witness)
        self.env.reach("LSQ-STRESS.capacity")
        return stores, loads

    async def fair_drain(self):
        assert self.active()
        self.fair = True
        self.env.reach("LSQ-STRESS.fair_drain")
        start = self.edge
        self.env.emit("joint_fair_service_begin", no_new_dispatch=True,
                      pending_uids=[s["uid"] for s in self.active()], remaining_external=sum(j["response"] is None for j in self.jobs))
        for _ in range(4000):
            bank = [s for s in self.active("store") if 0 <= s["position"]-self.sq_head < 64]
            inflight = [x[0] for x in self.s2 if x is not None]
            addresses = [s for s in bank if not s["s2_done"] and s not in inflight][:2]
            data = [s for s in bank if not s["data_sent"]][:2]
            candidates = self.active("load")
            queries = self.fair_select("query", [s for s in candidates if s["phase"] in ("new", "retry", "nc_query")], 3)
            s3 = self.fair_select("s3", [s for s in candidates if s["phase"] == "s3"], 3)
            bp = self.fair_select("bypass", [s for s in candidates if s["phase"] == "bypass"], 3)
            await self.cycle(addresses=addresses, data=data, queries=queries, s3=s3, bypass=bp, retire=True, service=True)
            if not self.active() and all(j["response"] is not None for j in self.jobs) and self.cache_job is None:
                break
        else:
            raise AssertionError(("coupled actual fair service failed original obligations", [(s["uid"], s["subtype"], s.get("phase")) for s in self.active()]))
        for _ in range(16):
            await self.cycle(retire=True, service=True)
        assert self.pending() == self.rob_tail
        assert self.env.observed["io_lqEmpty"] and self.env.observed["io_sqEmpty"] and not self.env.observed["io_replayAllocate"]
        assert all(j["response"] is not None and (j["owner"]["kind"] != "load" or j["consumed"] or j["owner"]["aborted"] is not None) for j in self.jobs)
        assert self.counts["original_replay_grants"] == self.counts["original_slot_feedbacks"]
        self.env.emit("joint_fair_originals_fully_drained", service_cycles=self.edge-start, counts=dict(self.counts),
                      scope="positive coupled directed obligations only; full-domain eight random FAILs and all three STRESS unchecked remain")

    async def cancel_full(self):
        assert self.sq_tail-self.sq_head == 128 and self.lq_tail-self.lq_head == 120
        self.redirect_due = self.pending(), "coupled_full_external_branch"
        await self.cycle(redirect=True)
        for _ in range(100):
            await self.cycle(respond=True)
            if self.recovery is None and not self.settle and all(j["response"] is not None for j in self.jobs):
                break
        else:
            raise AssertionError("shared full cancel failed actual recovery/old external responses")
        assert not self.active() and all(not j["consumed"] for j in self.jobs)
        self.env.emit("joint_cancelled_old_jobs_repaid", cancelled_uids=[s["uid"] for s in self.history if s["aborted"]],
                      original_external_responses=len(self.jobs), fabricated_consumptions=0)

    async def common_reset(self):
        old = [s for s in self.active()]
        jobs = [j for j in self.jobs if j["response"] is None]
        assert len(old) == 248 and len(jobs) == 16 and all(j["sid"] is not None for j in jobs)
        # Do not mutate response=None into fictitious completion. Archive the
        # old actor and explicitly terminate these jobs at the system boundary.
        for s in old:
            s["aborted"] = "common_system_reset"
        for _ in range(4):
            await self.env.cycle(reset=True)
        self.env.emit("joint_common_system_reset_abort", old_uids=[s["uid"] for s in old],
                      external_jobs=[dict(uid=j["uid"], owner_uid=j["owner"]["uid"], mid=j["mid"], sid=j["sid"]) for j in jobs],
                      real_responses=0, real_data_consumptions=0,
                      boundary="same reset aborts local and external unreturned jobs; no late pre-reset response claim; accepted Store writes would not be reversible")
        return self.sequence

    def assert_reused(self, old):
        for s in old:
            size = 120 if s["kind"] == "load" else 64
            assert any(n["uid"] > s["uid"] and n["kind"] == s["kind"] and n["position"] % size == s["position"] % size and n["complete"] for n in self.history)
