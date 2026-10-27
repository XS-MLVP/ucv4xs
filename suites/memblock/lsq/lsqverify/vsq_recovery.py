"""External release/walk schedules; only public ports and producer UID ledgers."""
from dataclasses import replace
import hashlib
import json

from lsqverify.psq.checks import read_ptr
from lsqverify.raw.types import SqPtr
from lsqverify.store_payload import add_digest
from lsqverify.vlq.types import Redirect, RobPtr
from lsqverify.vsq.types import Dispatch

WINDOWS = ((0, 1), (62, 8), (126, 9), (190, 59))


class PublicWindow:
    def __init__(self, dut):
        self.dut, self.stream = dut, hashlib.sha256()
        self.cycles = self.sq_stall = self.lq_stall = 0
        self.sq_responses, self.lq_responses = [], []

    def observe(self, pins, tick):
        self.cycles += 1
        if self.dut == "virtual_store_queue":
            stall, response = "io_sqRecoverStall", "io_toPhysicalQueue_redirectPtr_"
        else:
            stall, response = "io_toLsqEnqCtrl_sqRecoverStall", "io_toLsqEnqCtrl_sqRedirectPtr_"
        self.sq_stall += int(pins[stall])
        row = [tick, int(pins[stall])]
        if pins[response + "valid"]:
            value = read_ptr(pins, response + "bits_")
            self.sq_responses.append(value)
            row.append(["sq_tail", value])
        if self.dut == "lsq_wrapper":
            self.lq_stall += int(pins["io_toLsqEnqCtrl_lqRecoverStall"])
            if pins["io_toLsqEnqCtrl_lqRedirectPtr_valid"]:
                value = 120 * pins["io_toLsqEnqCtrl_lqRedirectPtr_bits_flag"] + pins["io_toLsqEnqCtrl_lqRedirectPtr_bits_value"]
                self.lq_responses.append(value)
                row.append(["lq_tail", value])
        add_digest(self.stream, row)

    def finish(self, cut, lq=None):
        assert self.sq_responses == [cut % 256] and self.sq_stall > 0
        if lq is not None:
            assert self.lq_responses == [lq % 240] and self.lq_stall > 0
        return dict(cycles=self.cycles, sq_stall_cycles=self.sq_stall, lq_stall_cycles=self.lq_stall,
                    actual_sq_responses=self.sq_responses, actual_lq_responses=self.lq_responses,
                    public_recovery_SHA256=self.stream.hexdigest())


def save(path, dut, delay, profiles, stream, **fields):
    report = dict(format="lsq-vsq-release-walk-witness-v1", dut=dut, redirect_extra_idle=delay,
                  profiles=profiles, public_lifetimes_SHA256=stream.hexdigest(), **fields)
    path.write_text(json.dumps(report, indent=2) + "\n")


async def store_windows(env, actor, delay, path):
    profiles, stream = [], hashlib.sha256()
    for profile, (base, prefix) in enumerate(WINDOWS):
        assert not actor.live and actor.head == actor.tail <= base
        fillers = []
        while actor.tail < base:
            fillers.extend(actor.add().flows)
        if fillers:
            await actor.drain()
        uops = [actor.add() for _ in range(prefix + 5)]
        for _ in range(100):
            await actor.step(fair=True, advance_rob=False, sbuffer_ready=(False, False))
            if all(item.dispatched and all(actor.all[uid].s2_done and actor.all[uid].data_sent for uid in item.flows) for item in uops):
                break
        assert all(item.dispatched and all(actor.all[uid].s2_done and actor.all[uid].data_sent for uid in item.flows) for item in uops)
        assert actor.head == base and all(not actor.parts[uid] for item in uops for uid in item.flows)
        for item in uops[:prefix]:
            item.retired_by_rob = True
        actor.rob_order = uops[prefix].rob_order
        for _ in range(delay + 1):
            await actor.step(fair=True, issue=False, dispatch=False, advance_rob=False,
                             rob_head=uops[prefix].rob, sbuffer_ready=(False, False))
        cutoff, cut = uops[prefix + 1], base + prefix + 2
        victims = uops[prefix + 2:]
        old = [uid for item in victims for uid in item.flows]
        observation = PublicWindow("store_queue")
        for index in range(36):
            if index == 1:
                uops[prefix].retired_by_rob = True
                actor.rob_order = cutoff.rob_order
            await actor.step(fair=True, issue=False, dispatch=False, advance_rob=False,
                             rob_head=uops[prefix].rob if index == 0 else cutoff.rob,
                             redirect=Redirect(index == 0, cutoff.rob, False), sbuffer_ready=(False, False))
            observation.observe(env.observed, env.last_tick)
            if index >= 10 and not env.observed["io_toLsqEnqCtrl_sqRecoverStall"]:
                break
        assert index < 35 and actor.head == base
        recovery = observation.finish(cut)
        for item in victims:
            assert not item.retired_by_rob
            actor.active_uops.remove(item.uid)
        for uid in old:
            assert uid not in actor.completed and not actor.parts[uid]
            actor.cancelled.add(uid)
            del actor.live[actor.all[uid].position]
        actor.tail = actor.dispatched_tail = cut
        actor.next_rob = cutoff.rob_order + 1
        actor.s2 = ((None, True),) * 2
        actor.emit("release_walk_public_cancel", cut=cut, cancelled=old, recovery=recovery)
        new = [actor.add() for _ in range(3)]
        assert [actor.all[item.flows[0]].position for item in new] == list(range(cut, cut + 3))
        await actor.drain()
        kept = [uid for item in uops[:prefix + 2] for uid in item.flows]
        replacements = [uid for item in new for uid in item.flows]
        assert set(kept + replacements) <= actor.completed and set(old) <= actor.cancelled
        assert all(actor.parts[uid] == {0} for uid in kept + replacements)
        assert actor.head == base + prefix + 5 and not actor.live
        actor.checked(("SQ-RECOVER.prefix_windows", "SQ-RECOVER.release_walk", "SQ-REUSE.cancelled"), kept + replacements)
        item = dict(profile=profile, base=base, retired_prefix=prefix, old_store_uids=len(uops),
                    fillers_completed=len(fillers), actual_sq_cut=cut % 256,
                    cancelled_store_uids=old, replacement_store_uids=replacements,
                    retained_store_completions=len(kept), new_store_completions=3, recovery=recovery)
        profiles.append(item); add_digest(stream, item)
        for uid in kept + replacements:
            add_digest(stream, ["actual_original_bytes_fire_then_dequeue", uid, actor.all[uid].position, actor.finish_ticks[uid]])
    assert actor.head == actor.tail == len(actor.completed) == 254
    assert len(actor.cancelled) == 12 and len(actor.all) == 266 and not actor.aborted
    save(path, "store_queue", delay, profiles, stream, normal_store_completions=254, cancelled_store_uids=12,
         scope="actual public dispatch/ROB/redirect; old retained and new same-position UID bytes, Sbuffer fire and normal dequeue checked; no shared actor/model changes or between-window reset")


class LeafProducers:
    def __init__(self, env):
        self.env, self.uid, self.rob, self.end = env, 0, 10, 0
        self.physical_deq = 0

    async def dispatch(self, count):
        result = []
        for start in range(0, count, 8):
            requests, batch = [Dispatch()] * 8, []
            for lane in range(min(8, count - start)):
                self.uid += 1
                ptr = RobPtr.encode(self.rob)
                self.end += 1
                requests[lane] = Dispatch(True, True, ptr, 1, SqPtr.encode(self.end))
                batch.append(dict(uid=self.uid, rob=self.rob, end=self.end))
                self.rob += 1
            change = await self.env.cycle(tuple(requests))
            assert [item["uid"] for item in change["accepted"]] == [item["uid"] for item in batch]
            result.extend(batch)
        return result

    async def drain(self):
        for _ in range(90):
            await self.env.cycle(rob_head=RobPtr.encode(self.rob))
            pins = self.env.observed
            if pins["io_empty"] and not pins["io_sqRecoverStall"] and read_ptr(pins, "io_toPhysicalQueue_retiredPtr_") == self.end % 256:
                break
        else:
            raise AssertionError("public VSQ retirement did not converge to producer flow end")
        # Only after the public retired end is visible does the emulated PSQ
        # report its real external consumption. It is never fabricated early.
        old = read_ptr(self.env.observed, "io_toPhysicalQueue_retiredPtr_")
        while self.physical_deq < self.end:
            self.physical_deq = min(self.physical_deq + 2, self.end)
            await self.env.cycle(physical_deq=SqPtr.encode(self.physical_deq), consumed=True)
        await self.env.idle(5)
        assert read_ptr(self.env.observed, "io_toPhysicalQueue_retiredPtr_") == old


async def leaf_windows(env, delay, path):
    producer, stream, profiles = LeafProducers(env), hashlib.sha256(), []
    for profile, (base, prefix) in enumerate(WINDOWS):
        assert producer.end <= base
        fillers = await producer.dispatch(base - producer.end)
        if fillers:
            await producer.drain()
        old = await producer.dispatch(prefix + 5)
        cutoff, cut = old[prefix + 1], base + prefix + 2
        kept = old[:prefix + 2]
        env.arm("VSQ-WALK.prefix_windows", [item["uid"] for item in kept])
        await env.idle(delay + 1, rob_head=RobPtr.encode(old[prefix]["rob"]))
        observation = PublicWindow("virtual_store_queue")
        for index in range(36):
            await env.cycle(rob_head=RobPtr.encode(old[prefix]["rob"] if index == 0 else cutoff["rob"]),
                            redirect=Redirect(index == 0, RobPtr.encode(cutoff["rob"]), False))
            observation.observe(env.observed, env.last_tick)
            if index >= 10 and not env.observed["io_sqRecoverStall"]:
                break
        assert index < 35
        recovery = observation.finish(cut)
        victims = [item["uid"] for item in old[prefix + 2:]]
        assert set(victims) <= env.coverage.canceled
        assert read_ptr(env.observed, "io_toPhysicalQueue_physicalQueueEnqPtr_") == cut % 256
        producer.end, producer.rob = cut, cutoff["rob"] + 1
        new = await producer.dispatch(3)
        assert [item["end"] for item in new] == [cut + 1, cut + 2, cut + 3]
        env.arm("VSQ-WALK.prefix_windows", [item["uid"] for item in new])
        await producer.drain()
        assert {item["uid"] for item in kept + new} <= env.coverage.completed
        item = dict(profile=profile, base=base, retired_prefix=prefix, old_store_uids=len(old),
                    fillers_completed=len(fillers), actual_sq_cut=cut % 256,
                    cancelled_store_uids=victims, replacement_store_uids=[item["uid"] for item in new],
                    retained_store_completions=len(kept), new_store_completions=3, recovery=recovery)
        add_digest(stream, item); profiles.append(item)
    assert producer.end == len(env.coverage.completed) == 254
    assert producer.uid == 266 and len(env.coverage.canceled) == 12
    save(path, "virtual_store_queue", delay, profiles, stream, normal_virtual_completions=254, cancelled_virtual_uids=12,
         scope="external compact dispatch end/ROB ledger and actual public retired/redirect/empty/stall; leaf does not claim real parent memory completion; no reference/internal state reads for controls")
