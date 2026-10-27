"""Public cancellation capacity traces; no hidden/reference controls."""
import hashlib
import json

from lsqverify.psq.checks import read_ptr
from lsqverify.raw.types import SqPtr
from lsqverify.store_payload import add_digest
from lsqverify.vlq.types import Redirect, RobPtr
from lsqverify.vsq.types import Dispatch
from lsqverify.vsq_recovery import PublicWindow

PROFILES = ((0, 4, 2), (62, 8, 2), (126, 16, 2), (190, 32, 2), (254, 64, 0))


def save(path, dut, profiles, stream, **totals):
    path.write_text(json.dumps(dict(format="lsq-vsq-cancel-capacity-witness-v1", dut=dut, profiles=profiles,
                                  public_lifetime_SHA256=stream.hexdigest(), **totals), indent=2) + "\n")


class LeafProducer:
    def __init__(self, env):
        self.env = env
        self.uid = self.virtual_tail = self.physical_tail = self.physical_deq = 0
        self.next_rob = 10

    async def allocate(self, flows):
        accepted = []
        for start in range(0, len(flows), 8):
            packet, expected = [Dispatch()] * 8, []
            for lane, count in enumerate(flows[start:start + 8]):
                self.uid += 1
                position = self.virtual_tail
                self.virtual_tail += 1; self.physical_tail += count
                record = dict(uid=self.uid, virtual_position=position, rob=self.next_rob,
                              flows=count, physical_end=self.physical_tail)
                packet[lane] = Dispatch(True, True, RobPtr.encode(self.next_rob), count, SqPtr.encode(self.physical_tail))
                expected.append(record); self.next_rob += 1
            change = await self.env.cycle(tuple(packet))
            assert len(change["accepted"]) == len(expected)
            for observed, record in zip(change["accepted"], expected):
                assert (observed["uid"], observed["position"], observed["flows"], observed["end"]) == (
                    record["uid"], record["virtual_position"], record["flows"], record["physical_end"])
            accepted.extend(expected)
        return accepted

    async def drain(self):
        for _ in range(100):
            await self.env.cycle(rob_head=RobPtr.encode(self.next_rob))
            pins = self.env.observed
            if pins["io_empty"] and not pins["io_sqRecoverStall"] and read_ptr(pins, "io_toPhysicalQueue_retiredPtr_") == self.physical_tail % 256:
                break
        else:
            raise AssertionError("actual VSQ public retirement did not converge to external flow tail")
        while self.physical_deq < self.physical_tail:
            self.physical_deq = min(self.physical_deq + 2, self.physical_tail)
            await self.env.cycle(physical_deq=SqPtr.encode(self.physical_deq), consumed=True)
        await self.env.idle(5)
        assert read_ptr(self.env.observed, "io_toPhysicalQueue_retiredPtr_") == self.physical_tail % 256


async def leaf_trace(env, path):
    producer, profiles, stream = LeafProducer(env), [], hashlib.sha256()
    specs = list(PROFILES) + [(318, 128, 0)]
    for profile, (base, count, kept) in enumerate(specs):
        fillers = await producer.allocate([1] * (base - producer.physical_tail))
        if fillers:
            await producer.drain()
        assert producer.physical_tail == producer.physical_deq == base
        flow_counts = [1] * (count + kept) if count < 128 else [index % 2 for index in range(128)]
        assert sum(flow_counts) <= 64
        old = await producer.allocate(flow_counts)
        victims = old[kept:]
        cutoff = old[kept - 1] if kept else old[0]
        cut = old[kept - 1]["physical_end"] if kept else base
        virtual_cut = victims[0]["virtual_position"]
        observation = PublicWindow("virtual_store_queue")
        for tick in range(35):
            await env.cycle(redirect=Redirect(tick == 0, RobPtr.encode(cutoff["rob"]), not kept))
            observation.observe(env.observed, env.last_tick)
            if tick >= 10 and not env.observed["io_sqRecoverStall"]:
                break
        assert tick < 34
        recovery = observation.finish(cut)
        old_uids = {record["uid"] for record in victims}
        assert old_uids <= env.coverage.canceled and not old_uids & env.coverage.completed
        producer.virtual_tail, producer.physical_tail = virtual_cut, cut
        producer.next_rob = cutoff["rob"] + int(bool(kept))
        new = await producer.allocate([record["flows"] for record in victims])
        reuse = [[before["uid"], after["uid"], after["virtual_position"], after["flows"], after["physical_end"]]
                 for before, after in zip(victims, new)]
        assert all(before["virtual_position"] == after["virtual_position"] and before["physical_end"] == after["physical_end"]
                   and after["uid"] > old[-1]["uid"] for before, after in zip(victims, new))
        env.arm("VSQ-REDIRECT.capacity_suffix", [record["uid"] for record in new])
        await producer.drain()
        assert {record["uid"] for record in old[:kept] + new} <= env.coverage.completed
        item = dict(profile=profile, physical_base=base, cancel_uops=count, kept_uops=kept,
                    physical_flows=sum(flow_counts), fillers_completed=len(fillers), actual_recovered_tail=cut % 256,
                    reuse_old_new_virtual_flow_end=reuse, new_completed_uids=[record["uid"] for record in new], recovery=recovery)
        profiles.append(item); add_digest(stream, item)
    assert len(env.coverage.completed) == producer.virtual_tail == 446
    assert len(env.coverage.canceled) == 252 and producer.physical_tail == 382
    save(path, "virtual_store_queue", profiles, stream, normal_virtual_uids=446, cancelled_virtual_uids=252,
         normal_physical_flows=382, exact_virtual_slot_reuses=252, parent_memory_claimed=False)


async def store_trace(env, actor, path, *, head_permit=True):
    profiles, stream = [], hashlib.sha256()
    for profile, (base, count, kept) in enumerate(PROFILES):
        fillers = []
        while actor.tail < base:
            fillers.extend(actor.add().flows)
        if fillers:
            await actor.drain()
        assert actor.head == actor.tail == base and not actor.live
        old = [actor.add() for _ in range(count + kept)]
        hold = {} if head_permit else {"rob_head": RobPtr.encode(old[0].rob_order - 1, former=bool((old[0].rob_order - 1) % 2))}
        for _ in range(100):
            await actor.step(fair=True, advance_rob=False, sbuffer_ready=(False, False), **hold)
            if all(item.dispatched and all(actor.all[uid].s2_done and actor.all[uid].data_sent for uid in item.flows) for item in old):
                break
        assert all(item.dispatched and all(actor.all[uid].s2_done and actor.all[uid].data_sent for uid in item.flows) for item in old)
        assert actor.head == base and all(not actor.parts[uid] for item in old for uid in item.flows)
        cutoff = old[kept - 1] if kept else old[0]
        victims = old[kept:]
        if head_permit:
            cancelled = await actor.cancel(cutoff, flush_self=not kept)
        else:
            observation = PublicWindow("store_queue")
            for index in range(35):
                await actor.step(fair=True, issue=False, dispatch=False, advance_rob=False,
                                 redirect=Redirect(index == 0, cutoff.rob, not kept), sbuffer_ready=(False, False), **hold)
                observation.observe(env.observed, env.last_tick)
                if index >= 10 and not env.observed["io_toLsqEnqCtrl_sqRecoverStall"]:
                    break
            assert index < 34
            observation.finish(base + kept)
            cancelled = [uid for item in victims for uid in item.flows]
            for item in victims:
                assert not item.retired_by_rob
                actor.active_uops.remove(item.uid)
            for uid in cancelled:
                assert uid not in actor.completed and not actor.parts[uid]
                actor.cancelled.add(uid)
                del actor.live[actor.all[uid].position]
            actor.tail = actor.dispatched_tail = base + kept
            actor.next_rob = cutoff.rob_order + int(bool(kept))
            actor.s2 = ((None, True),) * 2
        assert cancelled == [uid for item in victims for uid in item.flows]
        cut = base + kept
        assert actor.tail == cut and actor.head == base
        new = [actor.add() for _ in range(count)]
        reuse = [[before.flows[0], after.flows[0], after.start] for before, after in zip(victims, new)]
        assert all(before.start == after.start and after.flows[0] > old[-1].flows[0] for before, after in zip(victims, new))
        try:
            await actor.drain()
        except BaseException:
            signals = {key: value for key, value in env.pre_observed.items() if key.startswith("io_writeToSbuffer_req_")}
            owners = lambda items: [dict(uid=owner.uid, position=owner.position, vaddr=owner.address.vaddr,
                                         paddr=owner.address.paddr, data=owner.data.data,
                                         parts=sorted(actor.parts[owner.uid])) for owner in items]
            evidence = dict(format="lsq-vsq-cancel-capacity-failure-v1", profile=profile,
                physical_base=base, cancel_uops=count, kept_uops=kept, head_permit_before_redirect=head_permit,
                tick=env.last_tick, actual_public_Sbuffer=signals,
                cancelled_old_owners=owners(actor.all[item.flows[0]] for item in victims),
                replacement_owners=owners(actor.all[item.flows[0]] for item in new),
                limits="Failure-instant public ports and external producer UID records only. Original exception is reraised; no checker/model/RTL comparison is disabled. Upstream legality and head-precommit cancellation are not inferred from this diagnostic alone.")
            path.with_name("vsq-cancel-capacity-failure.json").write_text(json.dumps(evidence, indent=2) + "\n")
            raise
        normal = [uid for item in old[:kept] + new for uid in item.flows]
        assert set(normal) <= actor.completed and all(actor.parts[uid] == {0} for uid in normal)
        assert set(cancelled) <= actor.cancelled and all(not actor.parts[uid] for uid in cancelled)
        actor.checked(("SQ-RECOVER.capacity_suffix", "SQ-REUSE.cancelled"), normal)
        item = dict(profile=profile, physical_base=base, cancel_uops=count, kept_uops=kept, physical_flows=count + kept,
                    fillers_completed=len(fillers), actual_recovered_tail=cut % 256, reuse_old_new_position=reuse,
                    new_completed_uids=[item.flows[0] for item in new], actual_normal_consumed_and_dequeued=len(normal))
        profiles.append(item); add_digest(stream, item)
        for uid in normal:
            add_digest(stream, ["real_bytes_fire_then_dequeue", uid, actor.all[uid].position, actor.finish_ticks[uid]])
    assert actor.head == actor.tail == len(actor.completed) == 318 and len(actor.cancelled) == 124 and not actor.aborted
    save(path, "store_queue", profiles, stream, normal_store_uids=318, cancelled_store_uids=124,
         exact_physical_slot_reuses=124, actual_Sbuffer_fragments=318, head_permit_before_redirect=head_permit)
