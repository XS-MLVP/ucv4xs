"""Seeded external producer/bus actors, no reference state used to decide work."""

from dataclasses import replace
import random

import pytest

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.load_queue.actor import LoadActor
from suites.memblock.lsq.load_queue.types import Bus, Bypass, Inputs, Load
from suites.memblock.lsq.rar.types import Query as RarQuery
from suites.memblock.lsq.raw.types import Query as RawQuery, SqPtr
from suites.memblock.lsq.replay.types import Cause, L2Hint, Refill, StoreWakeup, TlbHint
from suites.memblock.lsq.vlq.types import QueuePtr, RobPtr


class Traffic:
    def __init__(self, env, seed):
        self.actor, self.rng = LoadActor(env), random.Random(seed)
        self.initial, self.consumed, self.causes, self.types = set(), set(), set(), set()
        self.jobs, self.returned, self.expected = {}, {}, []
        self.cycle = 0

    def configure(self, load):
        cause = -1 if self.rng.random() < 0.25 else self.rng.randrange(12)
        if cause == -1:
            return replace(load, execution=replace(load.execution, uop=replace(load.execution.uop, sq=SqPtr())))
        nc = bool(self.rng.randrange(2)) if cause == 0 else False
        strict = cause == Cause.ADDRESS_DEPENDENCE and bool(self.rng.randrange(2))
        req = replace(load.execution, uop=replace(load.execution.uop, sq=SqPtr() if cause == 1 else SqPtr.encode(10),
                      strict=strict, load_wait=strict, store_set_hit=strict), need_replay=True, causes=1 << cause,
                      nc=nc, tlb_id=self.rng.randrange(16), mshr=self.rng.randrange(16), handled=cause == Cause.CACHE_MISS,
                      data_sq=SqPtr.encode(7), address_sq=SqPtr.encode(7))
        return replace(load, execution=req, mmio=cause == 0 and not nc)

    async def step(self, fair=False):
        actor, rng = self.actor, self.rng
        self.cycle += 1
        chance = lambda probability: fair or rng.random() < probability
        acks = [job for job in self.jobs.values() if job["phase"] == "ack" and job["accepted"] < self.cycle]
        replies = [job for job in self.jobs.values() if job["phase"] == "response" and job["bound"] < self.cycle]
        ack = rng.choice(acks) if acks and chance(0.65) else None
        response = rng.choice(replies) if replies and chance(0.55) else None
        free_sids = sorted(set(range(16)) - {job["sid"] for job in self.jobs.values()})
        # SID is reusable after its response, not after LDU consumption. Do
        # not artificially extend its lifetime to hide the known routing bug.
        bus = Bus(ready=bool(free_sids) and chance(0.7), ack=ack is not None, mid=ack["mid"] if ack else 0,
                  sid=ack["sid"] if ack else 0, response=response is not None, response_id=response["sid"] if response else 0,
                  data=response["data"] if response else 0, error=response["error"] if response else False,
                  nderr=response["nderr"] if response else False)
        candidates = [uid for uid in self.returned if uid in actor.issued and uid not in self.consumed]
        rng.shuffle(candidates)
        bypass_uids = candidates[:3 if fair else rng.randrange(4)]
        bypass = tuple(Bypass(True, actor.owner(uid).load.execution.uop.lq, actor.owner(uid).load.execution.nc,
                              actor.owner(uid).load.mmio) for uid in bypass_uids)
        loads, sending = [], []
        eligible_feedback = [uid for uid in actor.issued if actor.owner(uid).load.execution.causes != 1 or uid in self.consumed]
        rng.shuffle(eligible_feedback)
        for uid in eligible_feedback[:3 if fair else rng.randrange(4)]:
            owner = actor.owner(uid)
            loads.append(replace(owner.load, execution=replace(owner.load.execution, replay_feedback=True,
                                 slot=actor.issued[uid], need_replay=False, causes=0), update_address=True))
        ue_busy = sum(actor.owner(uid).load.execution.causes == 1 and uid not in self.consumed for uid in self.initial if uid not in actor.completed)
        new = [o for o in actor.live.values() if o.uid not in self.initial and
               (o.load.execution.causes != 1 or ue_busy < 12)]
        rng.shuffle(new)
        for owner in new[:3 - len(loads)]:
            if not fair and rng.random() < 0.3:
                continue
            if owner.load.execution.causes == 1 and ue_busy >= 12:
                continue
            loads.append(owner.load)
            sending.append(owner.uid)
            ue_busy += owner.load.execution.causes == 1
        head = actor.live.get(actor.head)
        pending = head.rob if head else RobPtr()
        wake = StoreWakeup(chance(0.35), SqPtr.encode(7))
        # Broadcast TLB and exact all-active MSHR refills are legal external
        # responses; ordinary random cycles also exercise mismatching tags.
        mshr = [rng.randrange(16), rng.randrange(16)]
        cache = [o for o in actor.live.values() if o.uid in self.initial and o.completed_tick is None and o.load.execution.causes == 1 << Cause.CACHE_MISS]
        if cache:
            rng.shuffle(cache)
            mshr[0] = cache[0].load.execution.mshr
            if len(cache) > 1:
                mshr[1] = cache[1].load.execution.mshr
        controls = Inputs(loads=tuple(loads) + (Load(),) * (3 - len(loads)), bypass=bypass + (Bypass(),) * (3 - len(bypass)), bus=bus,
                          pending=pending, pending_next=pending, replay_ready=tuple(chance(0.7) for _ in range(3)),
                          address_bits=(1 << 7) if chance(0.5) else 0, data_bits=(1 << 7) if chance(0.5) else 0,
                          address_wakeups=(wake, StoreWakeup()), data_wakeups=(wake, StoreWakeup()),
                          slow_tlb=TlbHint(chance(0.35), rng.randrange(16), True),
                          refills=tuple(Refill(chance(0.35), identity) for identity in mshr))
        # Normal completed-data queries share actual active identities and PA;
        # they do not directly control RAR full or the internal VLQ head.
        normal = [actor.owner(uid) for uid in sending if not actor.owner(uid).load.execution.need_replay]
        rq = tuple(RarQuery(True, o.rob, QueuePtr.encode(o.position), o.load.paddr, True) for o in normal)
        wq = tuple(RawQuery(True, o.rob, o.load.execution.uop.sq, o.load.paddr, 255, True) for o in normal)
        controls = replace(controls, rar_queries=rq + (RarQuery(),) * (3 - len(rq)), raw_queries=wq + (RawQuery(),) * (3 - len(wq)))
        await actor.step(controls)
        tick, pre, post = actor.env.last_tick, actor.env.pre_observed, actor.env.observed
        if response:
            assert response["uid"] not in self.returned
            self.returned[response["uid"]] = response
            del self.jobs[response["mid"]]
        if ack:
            ack.update(phase="response", bound=self.cycle)
        if pre[P.p_uncache_req_valid] and bus.ready:
            owner = next(o for o in actor.live.values() if o.load.paddr == pre[P.p_uncache_req_bits_addr])
            mid = pre[P.p_uncache_req_bits_id]
            assert mid not in self.jobs
            sid = rng.choice(free_sids)
            self.jobs[mid] = dict(mid=mid, uid=owner.uid, sid=sid, phase="ack", accepted=self.cycle,
                                  data=0x1020304050607000 | owner.uid, error=bool(owner.uid & 1), nderr=bool(owner.uid & 2))
        for uid in sending:
            self.initial.add(uid)
            req = actor.owner(uid).load.execution
            if req.need_replay:
                self.causes.add(req.causes.bit_length() - 1)
            if req.causes == 1:
                self.types.add(req.nc)
        for lane, uid in enumerate(bypass_uids):
            assert post[P.io(f"bypass_{lane}_s1Resp_valid")]
            self.consumed.add(uid)
            self.expected.append(dict(tick=tick + 2, lane=lane, **self.returned.pop(uid)))
        for packet in self.expected:
            if packet["tick"] == tick:
                p = P.io(f"bypass_{packet['lane']}_s2Resp_")
                assert post[p + "valid"] and post[p + "bits_data"] == packet["data"] * ((1 << 64) + 1)
                assert post[p + "bits_derr"] == int(packet["error"]) and post[p + "bits_nderr"] == int(packet["nderr"])


@pytest.mark.parametrize("seed", (88, 20261018))
async def test_seeded_full_cause_bus_replay_shared_s3_and_fair_drain(lq, seed):
    traffic = Traffic(lq, seed)
    actor, rng = traffic.actor, traffic.rng
    uids = []
    for _ in range(700):
        if len(uids) < 180 and actor.tail - actor.head < 90 and rng.random() < 0.55:
            uids.extend(await actor.dispatch((1,) * min(rng.randrange(1, 4), 180 - len(uids)), configure=traffic.configure))
        lq.reach("LQ-CONCURRENT.seeded")
        await traffic.step()
        if len(uids) == 180:
            break
    assert len(uids) == 180
    for _ in range(1000):
        await traffic.step(fair=True)
        if not actor.live and not traffic.jobs and not traffic.returned:
            for _ in range(6):
                await traffic.step(fair=True)
            break
    else:
        raise AssertionError("full-domain external mixed traffic failed fair drain")
    assert traffic.causes == set(range(12)) and traffic.types == {False, True}
    actor.checked(("LQ-CONCURRENT.seeded", "LQ-CONCURRENT.fair_drain"), uids)
