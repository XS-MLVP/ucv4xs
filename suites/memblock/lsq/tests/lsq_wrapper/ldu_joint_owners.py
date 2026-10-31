"""Legal phased capacity, source-stage LDU and real original-UID effects.

Positive directed conditions supplement, never replace the full eight seeds.
No DUT/reference private reads; all stage transitions inherit the S3 actor.
"""
from dataclasses import replace

from suites.memblock.lsq.forward.types import Query
from suites.memblock.lsq.load_queue.types import Bypass
from suites.memblock.lsq.lsq_wrapper.types import Address, Bus, Data, Dispatch
from suites.memblock.lsq.raw.types import SqPtr
from suites.memblock.lsq.replay.types import StoreWakeup
from suites.memblock.lsq.vlq.types import QueuePtr
from .ldu_s3_owners import LduS3MixedOwners
from .mixed_owners import rob_pointer


class LduJointOwners(LduS3MixedOwners):
    def __init__(self, env, seed, *, sequence=0, response_period=1):
        super().__init__(env, seed)
        self.sequence = sequence
        self.fair = True
        self.rounds = self.launch_cursor = 0
        assert response_period in (1,8)
        self.response_period = response_period
        self._direct = None

    def make(self, kind, *, unique=True):
        s = super().make(kind, unique=True)
        if s["kind"] == "store":
            if kind != "cbo":
                o = s["owner"]
                s["owner"] = replace(o, vaddr=o.vaddr//64*64, paddr=o.paddr//64*64, size=3)
        else:
            load = s["load"]
            va, pa = load.execution.vaddr//64*64, load.paddr//64*64
            u = replace(load.execution.uop, operation=6, integer_write=True, vector_write=False,
                        store_set_hit=False, load_wait=False, strict=False)
            s["load"] = replace(load, execution=replace(load.execution, uop=u, vaddr=va, mask=255,
                                                       vector=False, aligned_type=3), fullva=va, paddr=pa)
            s["extra"] = None
        return s

    def external(self, *, accept=False, ack=False, respond=False):
        bus = Bus(outstanding=True, ready=accept)
        jobs = [j for j in self.jobs if j["response"] is None]
        busy = {j["sid"] for j in jobs if j["sid"] is not None}
        waiting = [j for j in jobs if j["sid"] is None]
        if ack and waiting and len(busy) < 16:
            job = min(waiting, key=lambda j: j["uid"])
            bus = replace(bus, ack=True, ack_to_load=job["owner"]["kind"] == "load",
                          mid=job["mid"], sid=min(set(range(16))-busy))
        assigned = [j for j in jobs if j["sid"] is not None]
        # A separate fixed-cadence positive control, NOT a SID lifetime change.
        # Period1 immediate reuse/collision failures remain required cases.
        if respond and assigned and self.edge % self.response_period == 0:
            job = min(assigned, key=lambda j: j["uid"])
            bus = replace(bus, response=True, response_to_load=job["owner"]["kind"] == "load",
                          response_id=job["sid"], data=job["data"], error=job["error"], nderr=job["nderr"])
        return bus

    def plan(self, **unused):
        options = self._direct
        assert options is not None
        self._direct = None
        # Fixed S1/S2/S3, source metadata, recovery and S2 attributes are retained.
        # Only external admission/issue/service selection is directed here.
        packet, intent = super().plan(admit=False, execute=False, effects=False)
        fields = dict(bus=self.external(accept=options["accept"], ack=options["ack"], respond=options["respond"]),
                      sbuffer_ready=(options["service"],)*2, cache_ready=options["service"],
                      writeback_ready=options["service"], replay_ready=options["replay_ready"])
        if options["service"] and self.cache_job is not None:
            fields.update(cache_response=True, cache_denied=self.cache_job["denied"], cache_corrupt=self.cache_job["corrupt"])
        if options["allocate"]:
            assert not packet.redirect.valid and self.recovery is None and not self.settle
            assert not any(s["subtype"] == "cbo" and not s["retired"] and not s["rob_cancelled"] for s in self.program)
            assert len(options["allocate"]) <= 8
            items = []
            for kind in options["allocate"]:
                assert self.rob_tail-self.pending() < 320
                if kind == "cbo":
                    assert not items and len(options["allocate"]) == 1 and self.pending() == self.rob_tail
                if kind in self.KINDS[:4]:assert self.lq_tail-self.lq_head < 120
                else:assert self.sq_tail-self.sq_head < 128
                items.append(self.make(kind))
            dispatch = [Dispatch()]*8
            for lane, s in zip(sorted(self.rng.sample(range(8), len(items))), items):
                dispatch[lane] = Dispatch(True, 1 if s["kind"] == "load" else 2, rob_pointer(s["order"]), 1,
                                          load_start=QueuePtr.encode(s["position"]) if s["kind"] == "load" else QueuePtr(),
                                          store_end=SqPtr.encode(s["position"]+1) if s["kind"] == "store" else SqPtr())
            fields["dispatch"], intent["dispatch"] = tuple(dispatch), items
        addresses, data, wakes = [Address()]*2, [Data()]*2, [StoreWakeup()]*2
        for index, s in enumerate(options["addresses"]):
            lane = (index+self.rounds) % 2
            assert self.live(s) and 0 <= s["position"]-self.sq_head < 64
            assert not s["address_parts"] and not s["s2_done"]
            addresses[lane] = s["owner"].address()
            wakes[lane] = StoreWakeup(True, SqPtr.encode(s["position"]))
            intent["addresses"].append((s, lane, True, False))
        for index, s in enumerate(options["data"]):
            lane = (index+1+self.rounds) % 2
            assert self.live(s) and 0 <= s["position"]-self.sq_head < 64 and not s["data_sent"]
            data[lane] = s["owner"].data()
            intent["data"].append(s)
        fields.update(addresses=tuple(addresses), data=tuple(data), address_wakeups=tuple(wakes))
        queries, bypass = list(packet.queries), list(packet.bypass)
        for s in options["launch"]:
            assert self.live(s) and s["phase"] in ("ldu_new", "retry", "bypass")
            lane = self.launch_cursor % 3
            self.launch_cursor += 1
            assert not queries[lane].valid and intent["ldu_s0"][lane] is None
            item = self.ticket(s, uncache=s["phase"] == "bypass")
            assert not item["cross"]
            q = s["load"].execution
            queries[lane] = Query(True, item["VA"], q.uop.sq, item["size"], q.uop.load_wait, q.uop.strict, q.uop.wait_sq)
            intent["ldu_s0"][lane] = item
            if item["uncache_replay"]:
                bypass[lane] = Bypass(True, q.uop.lq, q.nc, s["load"].mmio)
                intent["bypass"][lane] = s
        fields.update(queries=tuple(queries), bypass=tuple(bypass))
        self._packet = replace(packet, **fields)
        return self._packet, intent

    async def cycle(self, *, allocate=(), launch=(), addresses=(), data=(), service=False,
                    accept=False, ack=False, respond=False, replay_ready=(False,)*3):
        self._direct = dict(allocate=allocate, launch=launch, addresses=addresses, data=data, service=service,
                            accept=accept or service, ack=ack or service, respond=respond or service,
                            replay_ready=(True,)*3 if service else replay_ready)
        old_jobs = len(self.jobs)
        await super().step()
        # Explicit clean-response positive condition, chosen before any response.
        # Full-domain seeds retain all original random error choices unchanged.
        for job in self.jobs[old_jobs:]:job.update(error=False, nderr=False)
        if self.cache_job is not None:self.cache_job.update(denied=False, corrupt=False)

    async def quiet(self, cycles=8, **options):
        for _ in range(cycles):await self.cycle(**options)

    async def full_first_phase(self):
        self.rounds += 1
        assert not self.active() and self.pending() == self.rob_tail
        assert all(j["response"] is not None for j in self.jobs)
        start = len(self.history)
        kinds = ["nc_load"]*16+["cached"]*40+["store"]*64+["cached"]*64+["store"]*64
        for offset in range(0, len(kinds), 8):await self.cycle(allocate=kinds[offset:offset+8])
        owners = self.history[start:]
        stores = [s for s in owners if s["kind"] == "store"]
        loads = [s for s in owners if s["kind"] == "load"]
        assert len(stores) == 128 and len(loads) == 120
        for offset in range(1, 64, 2):
            batch = stores[offset:min(offset+2, 64)]
            await self.cycle(addresses=batch, data=batch)
        # One source ticket at a time makes the exact capacity edge independent
        # of three-port reservation/preallocation timing; all lanes rotate.
        for s in loads:
            await self.cycle(launch=(s,), accept=True, ack=True)
            await self.quiet(4, accept=True, ack=True)
        for _ in range(100):
            pending = [j for j in self.jobs if j["response"] is None]
            if len(pending) == 16 and all(j["sid"] is not None for j in pending):break
            await self.cycle(accept=True, ack=True)
        else:raise AssertionError("first capacity phase did not really accept/ack16 NC jobs")
        await self.quiet()
        assert not self.redirect_due and not any(self.p0+self.p1+self.p2+self.tails)
        assert self.sq_tail-self.sq_head == 128 and self.lq_tail-self.lq_head == 120
        assert sum(s["sent"] for s in loads) == 96 and sum(s["phase"] == "wait" for s in loads) == 24
        assert not stores[0]["address_parts"] and all(s["s2_done"] and s["data_sent"] for s in stores[1:64])
        assert not any(s["address_parts"] or s["data_sent"] for s in stores[64:])
        self.env.emit("LDU_joint_first_capacity_attempt", round=self.rounds, SQ=128, LQ=120,
                      expected_RAR=96, expected_RAW=56, expected_LRQ=24, unreturned_NC=16,
                      source="expected snapshot; independent raw audit must reconstruct actual counts")
        return stores, loads

    async def transfer_to_replay_full(self, loads):
        old_head = self.lq_head
        for _ in range(400):
            # Only original NC may consume grants here. Capacity waits stay in
            # their original slots until the full-LRQ snapshot is established.
            ready = tuple(bool(self.env.observed[f"io_replay_{bank}_valid"] and
                               self.by_lq[QueuePtr(bool(self.env.observed[f"io_replay_{bank}_bits_uop_lqIdx_flag"]),
                                                   self.env.observed[f"io_replay_{bank}_bits_uop_lqIdx_value"])]["subtype"] == "nc_load") for bank in range(3))
            launch = [s for s in self.active("load") if s["subtype"] == "nc_load" and s["phase"] == "bypass"][:3]
            # RAR full can send a younger NC replay back through Uncache. Its
            # original UID acquires a NEW real external job after consumption;
            # continued fair service must accept/ack it, not just repay old16.
            await self.cycle(launch=launch, accept=True, ack=True, respond=True, replay_ready=ready)
            if all(s["complete"] for s in loads[:16]) and self.lq_head-old_head == 112:break
        else:raise AssertionError("original16 NC response/bypass/slot feedback did not release112 LQ credits")
        assert all(s["complete"] for s in loads if s["sent"])
        assert self.sq_tail-self.sq_head == 128
        before = len(self.history)
        for _ in range(14):await self.cycle(allocate=("cached",)*8)
        added = self.history[before:]
        assert len(added) == 112 and self.rob_tail-self.pending() == 304
        for s in added:
            await self.cycle(launch=(s,))
            await self.quiet(4)
        await self.quiet()
        waiting = self.active("load")
        assert len(waiting) == 120 and all(s["phase"] == "wait" and not s["sent"] for s in waiting)
        assert not any(self.p0+self.p1+self.p2+self.tails)
        self.env.emit("LDU_joint_replay_capacity_attempt", round=self.rounds, original16_NC_completed=True,
                      new_Load_UIDs=112, LQ=120, expected_LRQ=120, old_Store_UIDs_still_pending=128,
                      expected_RAW=56, absolute_ROB_span=304, source="independent raw audit required")

    async def fair_drain(self):
        start = self.edge
        for _ in range(4000):
            bank = [s for s in self.active("store") if 0 <= s["position"]-self.sq_head < 64]
            inflight = [x[0] for x in self.s2 if x is not None]
            addresses = [s for s in bank if not s["address_parts"] and s not in inflight][:2]
            data = [s for s in bank if not s["data_sent"]][:2]
            launch = sorted((s for s in self.active("load") if s["phase"] in ("ldu_new", "retry", "bypass")), key=lambda s:s["uid"])[:3]
            await self.cycle(addresses=addresses, data=data, launch=launch, service=True)
            if not self.active() and all(j["response"] is not None for j in self.jobs) and self.cache_job is None:break
        else:raise AssertionError(("source joint fair drain left obligations", [(s["uid"], s["subtype"], s.get("phase")) for s in self.active()]))
        await self.quiet(16, service=True)
        assert self.pending() == self.rob_tail
        assert self.env.observed["io_lqEmpty"] and self.env.observed["io_sqEmpty"] and not self.env.observed["io_replayAllocate"]
        assert self.counts["original_replay_grants"] == self.counts["original_slot_feedbacks"]
        self.env.emit("LDU_joint_originals_drained", service_cycles=self.edge-start, counts=dict(self.counts))

    async def serial_cbo(self):
        for opcode in range(4):
            assert self.pending() == self.rob_tail
            await self.cycle(allocate=("cbo",))
            s = self.history[-1]
            s["owner"] = replace(s["owner"], cbo=opcode)
            await self.fair_drain()
            assert s["retired"] and s["complete"]
            await self.cycle(allocate=("cached",))
            await self.fair_drain()

    async def cancel_first_phase(self):
        assert len(self.active()) == 248 and sum(j["response"] is None for j in self.jobs) == 16
        self.redirect_due = self.pending(), "LDU_joint_full_external_branch"
        await self.cycle()
        # Fixed external cadence requires at least16 response opportunities;
        # this is a service bound, not permission to invent late responses.
        for _ in range(max(100,16*self.response_period+16)):
            await self.cycle(respond=True)
            if self.recovery is None and not self.settle and all(j["response"] is not None for j in self.jobs):break
        else:raise AssertionError("source joint redirect failed recovery/late original external repayment")
        assert not self.active() and all(not j["consumed"] for j in self.jobs)
        self.env.emit("LDU_joint_cancel_old_responses_repaid", original_UIDs=248, actual_responses=16, fake_consumptions=0)

    async def common_reset(self):
        old, jobs = self.active(), [j for j in self.jobs if j["response"] is None]
        assert len(old) == 248 and len(jobs) == 16 and all(j["sid"] is not None for j in jobs)
        for s in old:s["aborted"] = "common_system_reset"
        for _ in range(4):await self.env.cycle(reset=True)
        self.env.emit("LDU_joint_common_system_reset_abort", old_uids=[s["uid"] for s in old],
                      external_jobs=[dict(uid=j["uid"], owner_uid=j["owner"]["uid"], mid=j["mid"], sid=j["sid"]) for j in jobs],
                      real_responses=0, real_data_consumptions=0,
                      boundary="same reset aborts local and external jobs; not a local-only late-response proof")
        return self.sequence

    def assert_reused(self, old):
        for s in old:
            size = 120 if s["kind"] == "load" else 64
            assert any(n["uid"] > s["uid"] and n["kind"] == s["kind"] and n["position"] % size == s["position"] % size and n["complete"] for n in self.history)
