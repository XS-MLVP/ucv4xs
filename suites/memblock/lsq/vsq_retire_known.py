"""External known-width retirement producers, not private counter readers."""
from dataclasses import asdict
import hashlib
import json

from suites.memblock.lsq.psq.checks import read_ptr
from suites.memblock.lsq.raw.types import SqPtr
from suites.memblock.lsq.store_payload import add_digest
from suites.memblock.lsq.vlq.types import RobPtr
from suites.memblock.lsq.vsq_cancel_capacity import LeafProducer

PROFILES = ((1, 1), (8, 8), (8, 2), (1, 1))


def save(path, dut, profiles, stream, **totals):
    path.write_text(json.dumps(dict(format="lsq-vsq-retire-known-width-witness-v1", dut=dut,
        profiles=profiles, public_lifetime_SHA256=stream.hexdigest(), **totals), indent=2) + "\n")


async def leaf_trace(env, path):
    producer, profiles, stream = LeafProducer(env), [], hashlib.sha256()
    for phase, (uops, flow_count) in enumerate(PROFILES):
        base = producer.physical_tail
        await env.cycle(rob_head=RobPtr.encode(producer.next_rob - 1))
        old = await producer.allocate([flow_count] * uops)
        uids = [item["uid"] for item in old]
        assert read_ptr(env.observed, "io_toPhysicalQueue_retiredPtr_") == base % 256
        assert not set(uids) & env.coverage.completed
        env.arm("VSQ-RETIRE.batch_width", uids)
        transitions = [[env.last_tick, base % 256]]
        for _ in range(50):
            await env.cycle(rob_head=RobPtr.encode(producer.next_rob))
            actual = read_ptr(env.observed, "io_toPhysicalQueue_retiredPtr_")
            if actual != transitions[-1][1]:
                transitions.append([env.last_tick, actual])
            if env.observed["io_empty"] and actual == producer.physical_tail % 256:
                break
        else:
            raise AssertionError("known-width public retirement did not converge")
        assert [row[1] for row in transitions] == [base % 256, (base + uops * flow_count) % 256]
        assert set(uids) <= env.coverage.completed
        while producer.physical_deq < producer.physical_tail:
            producer.physical_deq = min(producer.physical_deq + 2, producer.physical_tail)
            await env.cycle(physical_deq=SqPtr.encode(producer.physical_deq), consumed=True)
        await env.idle(5)
        assert env.observed["io_empty"] and read_ptr(env.observed, "io_toPhysicalQueue_retiredPtr_") == producer.physical_tail % 256
        item = dict(phase=phase, physical_base=base, virtual_uops=uops, flows_per_uop=flow_count,
                    batch_physical_flows=uops * flow_count, normal_uids=uids,
                    actual_retired_ptr_transitions=transitions, actual_completed_uids=uids,
                    actual_physical_tail=producer.physical_deq,
                    allocated_virtual_uops=[dict(rob=asdict(RobPtr.encode(record["rob"])), flows=record["flows"], physical_end=record["physical_end"]) for record in old],
                    retirement_ROB_boundary=asdict(RobPtr.encode(producer.next_rob)))
        profiles.append(item); add_digest(stream, item)
    assert len(env.coverage.completed) == producer.virtual_tail == 18
    assert not env.coverage.canceled and producer.physical_tail == producer.physical_deq == 82
    save(path, "virtual_store_queue", profiles, stream, normal_virtual_uops=18, normal_physical_flows=82,
         parent_memory_claimed=False, resets_between_profiles=0, cancelled_uids=0)


async def store_trace(env, actor, path):
    profiles, stream = [], hashlib.sha256()
    for phase, (count, flows) in enumerate(PROFILES):
        base = actor.tail
        assert actor.head == base and not actor.live
        batch = [actor.add(flows=flows) for _ in range(count)]
        hold = RobPtr.encode(batch[0].rob_order - 1, former=bool((batch[0].rob_order - 1) % 2))
        uids = [uid for uop in batch for uid in uop.flows]
        assert len(uids) == count * flows <= 64
        for _ in range(100):
            await actor.step(fair=True, advance_rob=False, sbuffer_ready=(False, False), rob_head=hold)
            if all(item.dispatched and all(actor.all[uid].s2_done and actor.all[uid].data_sent for uid in item.flows) for item in batch):
                break
        assert all(item.dispatched and all(actor.all[uid].s2_done and actor.all[uid].data_sent for uid in item.flows) for item in batch)
        for _ in range(6):
            await actor.step(fair=True, issue=False, advance_rob=False, sbuffer_ready=(False, False), rob_head=hold)
        assert actor.head == base and all(not actor.parts[uid] for uid in uids)
        assert all(not item.retired_by_rob for item in batch)
        ready_tick = env.last_tick
        await actor.step(fair=True, sbuffer_ready=(False, False))
        assert all(item.retired_by_rob for item in batch)
        boundary = asdict(env.controls.rob_head)
        for _ in range(10):
            await actor.step(fair=True, issue=False, advance_rob=False, sbuffer_ready=(False, False))
        assert not env.observed["io_sqEmpty"] and actor.head == base and all(not actor.parts[uid] for uid in uids)
        await actor.drain()
        assert set(uids) <= actor.completed and all(actor.parts[uid] == {0} for uid in uids)
        actor.checked(("SQ-DISPATCH.multi", "SQ-PERMIT.retired", "SQ-RETIRE.buffered"), uids)
        item = dict(phase=phase, physical_base=base, virtual_uops=count, flows_per_uop=flows,
                    batch_physical_flows=count * flows, normal_uids=uids, actual_completed_uids=uids,
                    actual_physical_tail=actor.head, retirement_ROB_boundary=boundary,
                    allocated_virtual_uops=[dict(rob=asdict(uop.rob), flows=len(uop.flows), physical_end=uop.end) for uop in batch],
                    all_S2_STD_ready_before_permit_tick=ready_tick,
                    zero_consumed_fragments_before_permission=True, actual_Sbuffer_fragments=len(uids))
        profiles.append(item); add_digest(stream, item)
        for uid in uids:
            add_digest(stream, ["actual_original_bytes_fire_then_dequeue", uid, actor.all[uid].position, actor.finish_ticks[uid]])
    assert actor.head == actor.tail == len(actor.completed) == 82 and len(actor.uops) == 18
    assert not actor.cancelled and not actor.aborted
    save(path, "store_queue", profiles, stream, normal_virtual_uops=18, normal_physical_flows=82,
         actual_Sbuffer_fragments=82, resets_between_profiles=0, cancelled_uids=0)
