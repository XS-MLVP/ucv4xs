"""FTQ integration of the ResolveQueue and CommitQueue submodules."""

from __future__ import annotations

import pytest

from suites.frontend.ftq.commit_queue.checker.model import CommitChecker
from suites.frontend.ftq.ftq.transaction.types import IfuRedirect
from suites.frontend.ftq.ftq.transaction.types import Meta
from suites.frontend.ftq.ftq.transaction.types import Prediction
from suites.frontend.ftq.ftq.transaction.types import PredictionSpec
from suites.frontend.ftq.oracle import CallRet
from tests.ftq.support import allocate
from tests.ftq.support import resolve

pytestmark = pytest.mark.feature("FTQ-TOP-015")


async def _drain_training(agent) -> None:
    for _ in range(8):
        if agent.training() is None:
            break
        await agent.consumers(train=1)
        await agent.step(1)
        await agent.consumers(train=0)
        await agent.step(1)


async def test_top_level_backend_lane_matrix_reaches_training(ftq_agent):
    agent = ftq_agent
    await allocate(agent, 28, base=0x8000_8000, step=0x20)
    await agent.consumers(train=0)
    for combo in range(8):
        index = 20 + combo
        pc = 0x8000_8000 + index * 0x20
        lanes = [
            resolve(index, pc=pc, offset=lane + 1, mispredict=0)
            if combo & (1 << lane) else None
            for lane in range(3)
        ]
        if not any(lanes):
            continue
        await agent.resolve_lanes(lanes)
        for _ in range(6):
            if agent.training() is not None:
                break
            await agent.step(1)
        training = agent.training()
        assert training is not None, combo
        assert training.start_pc == pc
        assert [branch.position for branch in training.branches] == [
            lane + 1 for lane in range(3) if combo & (1 << lane)]
        await _drain_training(agent)


async def test_top_level_resolve_stream_fills_all_branch_slots(ftq_agent):
    agent = ftq_agent
    await allocate(agent, 16, base=0x8000_8000, step=0x20)
    await agent.consumers(train=0)
    for entry_index in range(16):
        pc = 0x8000_8000 + entry_index * 0x20
        await agent.resolve_stream([
            [resolve(entry_index, pc=pc, offset=group * 4 + lane,
                     mispredict=0,
                     target=0x9200_0000 + group * 0x1000 + lane * 0x100)
             for lane in range(3)]
            for group in range(2)
        ])
        for _ in range(6):
            if agent.training() is not None:
                break
            await agent.step(1)
        training = agent.training()
        assert training is not None
        assert [branch.position for branch in training.branches] == [
            0, 1, 2, 4, 5, 6]
        await _drain_training(agent)


async def test_top_level_commit_lane_sweep_covers_every_queue_slot(ftq_agent):
    agent = ftq_agent
    specs = [PredictionSpec(0x8000_0000 + index * 0x20,
                            meta=dict(commitMeta_ras_ssp=index & 0xF))
             for index in range(64)]
    await agent.allocate(specs, consume=True)
    for lane in range(8):
        for index in range(64):
            rows = [None] * 8
            rows[lane] = CallRet(index, 1 + (lane % 3))
            await agent.callret_rows(tuple(rows))
            event = agent.commit_event()
            assert event is not None, (lane, index)
            # commitMeta is addressed by the stored FTQ pointer, so the meta
            # field proves the queue returned the intended entry.
            assert (event.ras_action, event.meta_ssp) == (
                1 + (lane % 3), index & 0xF)
    for _ in range(2):
        await agent.callret_rows((None,) * 8)
    assert agent.commit_event() is None


async def test_top_level_branch_slot_and_source_priority_sweep(ftq_agent):
    """Close the top-level ResolveQueue write matrix.

    For every physical slot (enq mod 16), every branch slot (0..7) and every
    source (backend lanes 0..2, IFU), one report must land in that exact slot
    from that exact source.  Reports for one entry are driven one lane per
    cycle so the branch index is deterministic; the final report is delayed
    until the entry already holds the preceding branches.
    """

    agent = ftq_agent
    await allocate(agent, 8, base=0x8000_A000, step=0x20, consume=True)
    await agent.consumers(train=0)
    remaining = {slot: [(slot_branch, source)
                        for slot_branch in range(8)
                        for source in range(4)]
                 for slot in range(16)}
    todo = sum(len(items) for items in remaining.values())
    enqueued = 0
    while todo:
        slot = enqueued % 16
        queue = remaining[slot]
        # The resolve index is the pointer the next prediction will occupy, so
        # an IFU redirect cannot rewind BPU ownership.
        owner = agent.pointers().bpu
        index = owner.value
        flag = owner.flag
        pc = 0x8000_A000 + index * 0x20
        branch_slot, source = (queue.pop(0) if queue else (None, None))
        await agent.predict(Prediction(pc, end_position=3))
        await agent.write_meta(Meta(index, flag=flag))
        if branch_slot is None:
            # Keep the enqueue pointer advancing without duplicating a combo.
            await agent.resolve([resolve(index, pc=pc, offset=0,
                                         mispredict=0, flag=flag)])
            for _ in range(6):
                if agent.training() is not None:
                    break
                await agent.step(1)
            await _drain_training(agent)
            enqueued += 1
            continue

        target = 0xA500_0000 + source * 0x1000 + branch_slot * 0x100
        expected_target = target if source < 3 else target >> 1

        def lane_only(lane, report):
            lanes = [None, None, None]
            lanes[lane] = report
            return lanes

        if source < 3:
            for fill in range(branch_slot):
                await agent.resolve_cycle(lane_only(
                    fill % 3,
                    resolve(index, pc=pc, offset=fill, mispredict=0,
                            flag=flag,
                            target=0x9300_0000 + fill * 0x100)))
            await agent.resolve_cycle(lane_only(source, resolve(
                index, pc=pc, offset=branch_slot, mispredict=0,
                flag=flag, target=target)))
            await agent.resolve_release()
            await agent.step(1)
        else:
            for fill in range(branch_slot - 1):
                await agent.resolve_cycle(lane_only(
                    fill % 3,
                    resolve(index, pc=pc, offset=fill, mispredict=0,
                            flag=flag,
                            target=0x9300_0000 + fill * 0x100)))
            if branch_slot > 0:
                agent.set_resolve_lanes(lane_only(
                    (branch_slot - 1) % 3,
                    resolve(index, pc=pc, offset=branch_slot - 1,
                            mispredict=0, flag=flag,
                            target=0x9300_0000 + (branch_slot - 1) * 0x100)))
                await agent.drive_ifu_redirect(IfuRedirect(
                    index, flag=flag, pc=pc, offset=branch_slot,
                    target=target, branch_type=1, ras_action=0, can_train=1))
                await agent.step(1)
                await agent.resolve_release()
            else:
                await agent.drive_ifu_redirect(IfuRedirect(
                    index, flag=flag, pc=pc, offset=0, target=target,
                    branch_type=1, ras_action=0, can_train=1))
                await agent.step(1)
            await agent.finish_ifu_redirect()

        for _ in range(6):
            if agent.training() is not None:
                break
            await agent.step(1)
        training = agent.training()
        assert training is not None, (slot, branch_slot, source)
        positions = [branch.position for branch in training.branches]
        assert positions == list(range(branch_slot + 1)), (
            slot, branch_slot, source, positions)
        assert training.branches[-1].target == expected_target
        await _drain_training(agent)
        await agent.commit(index, flag=flag)
        enqueued += 1
        todo -= 1
    assert agent.training() is None


async def test_top_level_commit_queue_guard_and_drain(ftq_agent):
    agent = ftq_agent
    specs = [PredictionSpec(0x8000_0000 + index * 0x20,
                            meta=dict(commitMeta_ras_ssp=index & 0xF))
             for index in range(64)]
    await agent.allocate(specs, consume=True)
    checker = CommitChecker()
    ptr = 0
    for _ in range(20):
        rows = []
        for _ in range(8):
            rows.append(CallRet(ptr % 64, 1 + (ptr % 3)))
            ptr += 1
        expected = checker.step(tuple(rows))
        await agent.callret_rows(tuple(rows))
        event = agent.commit_event()
        assert event is not None
        assert (event.ras_action, event.meta_ssp) == (
            expected.ras, expected.ptr & 0xF)
    for _ in range(80):
        expected = checker.step((None,) * 8)
        await agent.callret_rows((None,) * 8)
        if expected is None:
            assert agent.commit_event() is None
            break
        event = agent.commit_event()
        assert event is not None
        assert (event.ras_action, event.meta_ssp) == (
            expected.ras, expected.ptr & 0xF)
    assert checker.depth == 0


@pytest.mark.feature("FTQ-TOP-015")
async def test_ifu_resolve_hits_resident_entry_in_every_physical_slot(ftq_agent):
    agent = ftq_agent
    for slot in range(16):
        await agent.reset()
        # Drain `slot` filler entries so the target lands in that slot.
        for filler in range(slot):
            await agent.predict(Prediction(0x8000_0000 + filler * 0x20,
                                           end_position=3))
            await agent.write_meta(Meta(filler))
            await agent.resolve([resolve(filler, pc=0x8000_0000 + filler * 0x20,
                                         offset=1, mispredict=0)])
            for _ in range(6):
                if agent.training() is not None:
                    break
                await agent.step(1)
            await _drain_training(agent)

        pc = 0x8000_0000 + slot * 0x20
        await agent.predict(Prediction(pc, end_position=3))
        await agent.write_meta(Meta(slot))
        # Backend resolve and IFU redirect land in the same cycle; the IFU
        # resolve is registered one cycle later, which suppresses the handoff
        # until both reports occupy the same entry.
        await agent.resolve_hold([resolve(slot, pc=pc, offset=1, mispredict=0)])
        await agent.drive_ifu_redirect(IfuRedirect(
            slot, pc=pc, offset=2, target=0x8000_9000,
            branch_type=1, ras_action=0, can_train=1))
        await agent.step(1)
        await agent.resolve_release()
        await agent.finish_ifu_redirect()
        for _ in range(6):
            if agent.training() is not None:
                break
            await agent.step(1)
        training = agent.training()
        assert training is not None, slot
        positions = [branch.position for branch in training.branches]
        assert positions == [1, 2], (slot, positions)


@pytest.mark.feature("FTQ-TOP-015")
async def test_same_cycle_same_index_lanes_merge_in_program_order(ftq_agent):
    agent = ftq_agent
    owner = agent.pointers().bpu
    pc = 0x8000_B000 + owner.value * 0x20
    await agent.predict(Prediction(pc, end_position=3))
    await agent.write_meta(Meta(owner.value, flag=owner.flag))
    lanes = [
        resolve(owner.value, flag=owner.flag, pc=pc, offset=lane,
                mispredict=0, target=0x9400_0000 + lane * 0x100)
        for lane in range(3)
    ]
    await agent.resolve_cycle(lanes)
    await agent.resolve_release()
    await agent.step(1)
    for _ in range(6):
        if agent.training() is not None:
            break
        await agent.step(1)
    training = agent.training()
    assert training is not None
    assert [branch.position for branch in training.branches] == [0, 1, 2]
    assert [branch.target for branch in training.branches] == [
        0x9400_0000 + lane * 0x100 for lane in range(3)]


@pytest.mark.feature("FTQ-TOP-015")
async def test_top_level_resolve_guard_limits_admission_and_preserves_order(ftq_agent):
    agent = ftq_agent
    await allocate(agent, 14, base=0x8000_C000, step=0x20)
    await agent.consumers(train=0)
    for index in range(14):
        owner = agent.pointers().bpu
        await agent.resolve([resolve(index, pc=0x8000_C000 + index * 0x20,
                                     offset=index % 32, mispredict=0)])
    assert agent.training() is not None
    drained = []
    for _ in range(16):
        training = agent.training()
        if training is None:
            break
        drained.append(training.start_pc)
        await agent.consumers(train=1)
        await agent.step(1)
        await agent.consumers(train=0)
        await agent.step(1)
    # The 16-entry queue keeps four slots in reserve: twelve entries fit in
    # the queue and the first may already sit in the training cache, so
    # thirteen reports survive and the rest are dropped.
    assert len(drained) == 13, drained
    assert drained == [0x8000_C000 + index * 0x20 for index in range(13)]
