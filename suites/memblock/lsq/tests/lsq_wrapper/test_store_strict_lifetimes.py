"""Real Store address holes -> Forward -> Replay grant -> original completion."""

from dataclasses import asdict, replace
import hashlib
import json

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.forward.types import Query, Translation
from suites.memblock.lsq.lsq_wrapper.types import Address
from suites.memblock.lsq.raw.types import SqPtr
from suites.memblock.lsq.replay.types import Cause, StoreWakeup
from suites.memblock.lsq.store_payload import add_digest
from suites.memblock.lsq.store_strict import check_response, record
from suites.memblock.lsq.vlq.types import QueuePtr, RobPtr
from .memory_owners import MemoryOwners, StoreOwner, cached_load


async def test_strict_hole_real_replay_wakeup_grant_and_four_lifetimes(lsq, tmp_path):
    trace, lives, stream = MemoryOwners(lsq), [], hashlib.sha256()
    for generation in range(4):
        start, first_rob = generation * 64, 10 + generation * 12
        assert trace.sq_head == start
        trace.base = replace(trace.base, pending=RobPtr.encode(first_rob - 1),
                             pending_next=RobPtr.encode(first_rob - 1), sbuffer_ready=(False, False))
        stores = [StoreOwner(start + slot, RobPtr.encode(first_rob + slot // 16), *record(generation, slot)[:2],
                             value=record(generation, slot)[2]) for slot in range(64)]
        strict, precise = [], []
        for index in range(6):
            load = cached_load(generation * 6 + index, first_rob + 4 + index, start + 64,
                               stores[0].vaddr, stores[0].paddr)
            load = replace(load, execution=replace(load.execution, uop=replace(load.execution.uop,
                           strict=index < 3, load_wait=True, store_set_hit=True, wait_sq=SqPtr.encode(start))))
            (strict if index < 3 else precise).append(load)
        await trace.dispatch(stores, strict + precise)
        # All STD arrive, but the last real address producer is deliberately late.
        for slot in range(64):
            await trace.write(start + slot, lane=slot % 2, address=slot < 63)
        await trace.idle(6)
        expected = record(generation, 0)
        assert lsq.observed[P.p_issuePtrExt_value] == 63
        assert trace.sq_head == start and not any(s["completed"] for s in trace.stores.values() if s["owner"].position >= start)
        responses = dict(strict_blocked=0, precise_unblocked=0, strict_after_STA_unblocked=0)

        async def forward_group(loads, label, blocked):
            queries = tuple(Query(True, load.execution.vaddr, load.execution.uop.sq, 3,
                                  wait=load.execution.uop.load_wait, strict=load.execution.uop.strict,
                                  wait_sq=load.execution.uop.wait_sq) for load in loads)
            await trace.cycle(queries=queries)
            await trace.cycle(translations=tuple(Translation(load.paddr) for load in loads))
            for lane, load in enumerate(loads):
                observed = check_response(lsq.observed, lane, expected, start + 63, blocked=blocked)
                add_digest(stream, [generation, label, lane, asdict(load.execution.uop.lq), observed])
                responses[label] += 1

        await forward_group(strict, "strict_blocked", True)
        replaying = [replace(load, execution=replace(load.execution, need_replay=True,
                     causes=1 << Cause.ADDRESS_DEPENDENCE, address_sq=SqPtr.encode(start + 63))) for load in strict]
        await trace.execute(replaying)
        await forward_group(precise, "precise_unblocked", False)
        await trace.execute(precise)
        for _ in range(6):
            await trace.cycle()
            assert not any(lsq.observed[P.io(f"replay_{bank}_valid")] for bank in range(3))
        assert lsq.observed[P.p_replayAllocate] and trace.sq_head == start
        assert not any(trace.active_loads[load.execution.uop.lq]["completed"] for load in strict + precise)
        lane = generation % 2
        await trace.cycle(addresses=tuple(stores[63].address() if i == lane else Address() for i in range(2)),
                          address_wakeups=tuple(StoreWakeup(True, SqPtr.encode(start + 63)) if i == lane else StoreWakeup() for i in range(2)))
        await trace.idle(6)
        keys = {load.execution.uop.lq: load for load in strict}
        granted = {}
        for _ in range(40):
            for bank in range(3):
                p = P.io(f"replay_{bank}_")
                if not lsq.observed[p + "valid"]:
                    continue
                key = QueuePtr(bool(lsq.observed[p + "bits_uop_lqIdx_flag"]), lsq.observed[p + "bits_uop_lqIdx_value"])
                assert key in keys and key not in granted
                load, slot = keys[key], lsq.observed[p + "bits_replayQueueIdx"]
                u = load.execution.uop
                assert lsq.observed[p + "bits_uop_robIdx_flag"] == int(u.rob.flag)
                assert lsq.observed[p + "bits_uop_robIdx_value"] == u.rob.value
                assert lsq.observed[p + "bits_uop_sqIdx_first_flag"] == int(u.sq.first)
                assert lsq.observed[p + "bits_uop_sqIdx_second_flag"] == int(u.sq.second)
                assert lsq.observed[p + "bits_uop_sqIdx_value"] == u.sq.value
                granted[key] = slot
                add_digest(stream, ["public_replay", generation, bank, slot, asdict(key), asdict(u.sq)])
            await trace.cycle(replay_ready=(True,) * 3)
            if len(granted) == 3:
                break
        assert len(granted) == len(set(granted.values())) == 3
        assert all(trace.active_loads[key]["grant"] == slot for key, slot in granted.items())
        await forward_group(strict, "strict_after_STA_unblocked", False)
        feedback = [replace(load, execution=replace(load.execution, replay_feedback=True,
                    slot=granted[load.execution.uop.lq], need_replay=False, causes=0)) for load in strict]
        await trace.execute(feedback)
        await trace.finish()
        assert trace.sq_head == start + 64 and all(trace.stores[start + slot]["completed"] for slot in range(64))
        assert all(trace.active_loads[load.execution.uop.lq]["completed"] for load in strict + precise)
        assert not lsq.observed[P.p_replayAllocate] and lsq.observed[P.p_lqEmpty] and lsq.observed[P.p_sqEmpty]
        for slot in range(64):
            state = trace.stores[start + slot]
            add_digest(stream, ["actual_store_completed", state["uid"], start + slot, state["last_fire"]])
        lives.append(dict(generation=generation, head_before=start, head_after=trace.sq_head,
                          dependency=asdict(SqPtr.encode(start + 63)), public_slots=list(range(64)), responses=responses,
                          hole_STA_lane=lane, matching_StoreWakeup=True, public_replay_slots=sorted(granted.values()),
                          replay_handshakes=3, original_feedback_completions=3, precise_load_completions=3,
                          sbuffer_consumed_owners=64, normal_completions=64))
    assert len(trace.stores) == 256 and len(trace.loads) == trace.load_released == 24
    assert len(trace.fragments_fired) == 256 and not trace.cancelled
    lsq.prove("LSQ-FORWARD.addr_hole", "LSQ-FORWARD.sqid", "LSQ-FORWARD.wrap", "LSQ-REPLAY.strict", "LSQ-REPLAY.sq_address")
    witness = dict(format="lsq-store-strict-lifetimes-witness-v1", dut="lsq_wrapper", lifetimes=lives,
                   completed_store_uids=256, completed_load_uids=24, checked_forward_responses=36,
                   actual_replay_handshakes=12, payload_and_completion_SHA256=stream.hexdigest(),
                   scope="real mixed dispatch, STA hole, strict/precise Forward, actual Replay grant and same-UID feedback, VLQ and Sbuffer/SQ completion; original full Wrapper model active")
    (tmp_path / "store-strict-lifetimes-witness.json").write_text(json.dumps(witness, indent=2) + "\n")
