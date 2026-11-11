"""IBuffer top-level contract tests over the real VTypeGen submodule.

The queue/vtype expectations come from the independent model in
``testbenches/ibuffer/model.py``.  Every cycle compares the full output surface on both
phases of the clock edge, so a mismatch in an ordering, pointer, exception,
vtype-bypass or flush rule is reported even when the instruction stream looks
plausible.
"""

from __future__ import annotations

import os
import random

import pytest

from suites.frontend.ibuffer.testbenches.ibuffer.checker import check_bypass
from suites.frontend.ibuffer.testbenches.ibuffer.checker import check_dequeue
from suites.frontend.ibuffer.testbenches.ibuffer.checker import check_enqueue
from suites.frontend.ibuffer.testbenches.ibuffer.checker import check_flush
from suites.frontend.ibuffer.testbenches.ibuffer.checker import check_no_head_bubble
from suites.frontend.ibuffer.testbenches.ibuffer.checker import check_not_enqueued
from suites.frontend.ibuffer.testbenches.ibuffer.model import Beat
from suites.frontend.ibuffer.testbenches.ibuffer.model import ExceptionEntry
from suites.frontend.ibuffer.testbenches.ibuffer.model import FetchEntry
from suites.frontend.ibuffer.testbenches.ibuffer.model import Inputs
from suites.frontend.ibuffer.testbenches.ibuffer.model import ZERO_EXCEPTION
from suites.frontend.ibuffer.testbenches.vtype_gen.model import INIT_VTYPE
from suites.frontend.ibuffer.testbenches.vtype_gen.model import VType
from suites.frontend.ibuffer.testbenches.vtype_gen.model import decode_vtype
from suites.frontend.ibuffer.testbenches.vtype_gen.model import encode_vsetvli

DECODE = 8


def entry(index: int) -> FetchEntry:
    """Distinct, non-vset instruction with all observable fields populated."""
    return FetchEntry(inst=0x0200_0000 | (index << 8),
                      is_rvc=index & 1,
                      foldpc=(index * 7) & 0x3FF,
                      pred_taken=(index >> 1) & 1,
                      offset=index & 0x1F,
                      ftq_flag=(index >> 2) & 1,
                      ftq_value=index & 0x3F,
                      triggered=index & 0xF)


def vset_entry(*, vsew: int = 2, vlmul: int = 1, rd: int = 5, rs1: int = 10,
               vma: int = 1, vta: int = 1) -> FetchEntry:
    payload = ((vma & 1) << 7) | ((vta & 1) << 6) | ((vsew & 7) << 3) | (vlmul & 7)
    return FetchEntry(inst=encode_vsetvli(rd, rs1, payload), is_rvc=0)


def entries(count: int, base: int = 0) -> tuple[FetchEntry, ...]:
    return tuple(entry(base + index) for index in range(count))


def random_entry(rng: random.Random) -> FetchEntry:
    return FetchEntry(inst=rng.getrandbits(32),
                      is_rvc=rng.randrange(2),
                      foldpc=rng.getrandbits(10),
                      pred_taken=rng.randrange(2),
                      offset=rng.getrandbits(5),
                      ftq_flag=rng.randrange(2),
                      ftq_value=rng.getrandbits(6),
                      triggered=rng.getrandbits(4))


def valid_lanes(outputs) -> list[int]:
    return [lane.valid for lane in outputs.lanes]


#: SEW/LMUL pairs that DefaultConfig (VLEN=128, ELEN=64) supports.
SUPPORTED_SEW_LMUL = tuple(
    (vsew, vlmul) for vsew in range(8) for vlmul in range(8)
    if decode_vtype(vsew, vlmul)[0])


def backend_vtype(rng: random.Random) -> VType:
    """A vtype that can legally come back from the architectural path."""
    if rng.random() < 0.25:
        return INIT_VTYPE
    vsew, vlmul = rng.choice(SUPPORTED_SEW_LMUL)
    return VType(rng.randrange(2), rng.randrange(2), rng.randrange(2),
                 vsew, vlmul)


# ---------------------------------------------------------------- reset -----
@pytest.mark.feature("IBUF-TOP-002")
@pytest.mark.feature("IBUF-TOP-007")
async def test_reset_is_empty_ready_and_clear(ibuffer_agent):
    agent = ibuffer_agent
    cycle = await agent.cycle(Inputs())
    assert cycle.before.empty == 1
    assert cycle.before.in_ready == 1 and cycle.before.full == 0
    assert valid_lanes(cycle.before) == [0] * DECODE
    assert cycle.before.stall_reason == (0,) * DECODE
    assert agent.occupancy == 0


# ------------------------------------------------------- bypass / window ----
@pytest.mark.feature("IBUF-TOP-005")
async def test_bypass_forwards_a_beat_and_stages_both_phases(ibuffer_agent):
    agent = ibuffer_agent
    beat = Beat(entries=entries(3), decode_can_accept=1)
    cycle = (await agent.play([beat]))[0]
    assert cycle.events.use_bypass == 1
    assert cycle.events.fire == 1 and cycle.events.num_enq == 3
    assert cycle.events.num_out == 3
    assert valid_lanes(cycle.before) == [0] * DECODE
    assert valid_lanes(cycle.after) == [1, 1, 1, 0, 0, 0, 0, 0]
    for lane in range(3):
        assert cycle.after.lanes[lane].instr == entry(lane).inst
        assert cycle.after.lanes[lane].foldpc == entry(lane).foldpc
        assert cycle.after.lanes[lane].is_rvc == entry(lane).is_rvc
        assert cycle.after.lanes[lane].pred_taken == entry(lane).pred_taken
        assert cycle.after.lanes[lane].ftq_value == entry(lane).ftq_value
        assert cycle.after.lanes[lane].ftq_offset == entry(lane).offset
        assert cycle.after.lanes[lane].trigger == entry(lane).triggered
        # Bypassed instructions see the currently speculated configuration.
        assert cycle.after.lanes[lane].vtype == INIT_VTYPE
        assert cycle.after.lanes[lane].specvtype == INIT_VTYPE
    # The queue is empty: the bypassed instructions were consumed directly.
    assert cycle.state_after["occupancy"] == 0
    # Without decode acceptance the staged window is held.
    held = await agent.cycle(Inputs())
    assert held.before.lanes[0].instr == entry(0).inst
    assert valid_lanes(held.before) == [1, 1, 1, 0, 0, 0, 0, 0]


@pytest.mark.feature("IBUF-TOP-005")
async def test_bypass_caps_at_eight_and_queues_the_remainder(ibuffer_agent):
    agent = ibuffer_agent
    batch = entries(12)
    cycle = (await agent.play([Beat(entries=batch, decode_can_accept=1)]))[0]
    assert cycle.events.use_bypass == 1
    assert cycle.events.num_enq == 12
    assert cycle.events.num_out == 8
    assert valid_lanes(cycle.after) == [1] * DECODE
    assert [cycle.after.lanes[lane].instr for lane in range(DECODE)] == \
        [item.inst for item in batch[:DECODE]]
    # Only the first eight positions bypass; the rest is written to the queue.
    assert cycle.state_after["occupancy"] == 4
    later = await agent.play([Beat(in_valid=0, decode_can_accept=1)])
    assert later[0].events.num_out == 4
    assert [later[0].after.lanes[lane].instr for lane in range(4)] == \
        [item.inst for item in batch[8:]]


@pytest.mark.feature("IBUF-TOP-005")
async def test_zero_count_valid_beat_uses_bypass_without_staging(ibuffer_agent):
    agent = ibuffer_agent
    cycle = (await agent.play([Beat(entries=(), in_valid=1,
                                    decode_can_accept=1)]))[0]
    assert cycle.events.fire == 1
    assert cycle.events.num_enq == 0 and cycle.events.num_out == 0
    assert cycle.events.use_bypass == 1
    assert valid_lanes(cycle.after) == [0] * DECODE


@pytest.mark.feature("IBUF-TOP-001")
@pytest.mark.feature("IBUF-TOP-004")
async def test_queued_enqueue_is_dequeued_into_the_window(ibuffer_agent):
    agent = ibuffer_agent
    cycles = await agent.play([
        Beat(entries=entries(4), decode_can_accept=0),
        Beat(in_valid=0, decode_can_accept=1),
    ])
    enqueue, dequeue = cycles
    check_enqueue(enqueue, count=4)
    assert enqueue.state_after["occupancy"] == 4
    check_dequeue(dequeue, count=4)
    check_no_head_bubble(dequeue)
    assert valid_lanes(dequeue.before) == [0] * DECODE
    assert valid_lanes(dequeue.after) == [1, 1, 1, 1, 0, 0, 0, 0]
    for lane in range(4):
        assert dequeue.after.lanes[lane].instr == entry(lane).inst


@pytest.mark.feature("IBUF-TOP-004")
async def test_append_mode_keeps_old_entries_and_appends(ibuffer_agent):
    agent = ibuffer_agent
    first = entries(3, 0)
    second = entries(2, 10)
    cycles = await agent.play([
        Beat(entries=first, decode_can_accept=0),
        Beat(in_valid=0, decode_can_accept=1),      # window = first 3
        Beat(entries=second, decode_can_accept=0),  # queue = second 2
        Beat(in_valid=0, decode_can_accept=0),      # append second 2
    ])
    before = cycles[2].after
    after = cycles[3].after
    assert valid_lanes(before) == [1, 1, 1, 0, 0, 0, 0, 0]
    assert valid_lanes(after) == [1, 1, 1, 1, 1, 0, 0, 0]
    for lane in range(3):
        assert after.lanes[lane].instr == first[lane].inst
    for lane in range(2):
        assert after.lanes[3 + lane].instr == second[lane].inst


@pytest.mark.feature("IBUF-TOP-001")
@pytest.mark.feature("IBUF-TOP-002")
async def test_full_width_payload_reaches_every_queue_position(ibuffer_agent):
    """Random 32-bit payloads in all 48 queue slots, including the wrap slot."""
    agent = ibuffer_agent
    rng = random.Random(20261108)
    first = tuple(random_entry(rng) for _ in range(24))
    second = tuple(random_entry(rng) for _ in range(16))
    third = tuple(random_entry(rng) for _ in range(7))
    wrap = tuple(random_entry(rng) for _ in range(8))

    cycles = await agent.play([
        Beat(entries=first, decode_can_accept=0),     # positions 0..23
        Beat(entries=second, decode_can_accept=0),    # positions 24..39
        Beat(entries=third, decode_can_accept=0),     # positions 40..46
    ])
    # The empty window absorbed positions 0..7 while the second beat arrived.
    assert cycles[2].state_after["occupancy"] == 39
    received = [cycles[2].after.lanes[lane].instr for lane in range(8)]
    # The window is full, so this beat writes the wrap slot 47 and the freed
    # positions 0..6 without draining anything.
    cycles = await agent.play([
        Beat(entries=wrap, decode_can_accept=0),      # positions 47,0..6
    ])
    assert cycles[0].state_after["occupancy"] == 47
    for _ in range(6):
        cycles = await agent.play([Beat(in_valid=0, decode_can_accept=1)])
        received.extend(cycles[0].after.lanes[lane].instr
                        for lane in range(DECODE)
                        if cycles[0].after.lanes[lane].valid)
    expected = ([item.inst for item in first]
                + [item.inst for item in second]
                + [item.inst for item in third]
                + [wrap[0].inst]
                + [item.inst for item in wrap[1:]])
    assert received == expected


@pytest.mark.feature("IBUF-TOP-001")
@pytest.mark.feature("IBUF-TOP-002")
async def test_all_ones_and_all_zeros_payload_toggle_every_queue_bit(ibuffer_agent):
    """Drive both bit directions through every queue slot and input lane."""
    agent = ibuffer_agent
    for fill in (0xFFFF_FFFF, 0x0000_0000):
        await agent.flush()
        value = FetchEntry(inst=fill,
                           is_rvc=fill & 1,
                           foldpc=fill & 0x3FF,
                           pred_taken=fill & 1,
                           offset=fill & 0x1F,
                           ftq_flag=fill & 1,
                           ftq_value=fill & 0x3F,
                           triggered=fill & 0xF)
        cycles = await agent.play([
            Beat(entries=(value,) * 32, decode_can_accept=0),  # positions 0..31
            Beat(entries=(value,) * 15, decode_can_accept=0),  # positions 32..46
        ])
        assert cycles[1].state_after["occupancy"] == 39
        cycles = await agent.play([
            Beat(entries=(value,) * 8, decode_can_accept=0),   # 47, 0..6
        ])
        assert cycles[0].state_after["occupancy"] == 47
        for _ in range(6):
            await agent.play([Beat(in_valid=0, decode_can_accept=1)])


@pytest.mark.feature("IBUF-TOP-001")
@pytest.mark.feature("IBUF-TOP-002")
async def test_fifo_order_survives_pointer_wrap(ibuffer_agent):
    agent = ibuffer_agent
    sent: list[int] = []
    received: list[int] = []
    pointers: list[int] = []
    for round_index in range(16):
        batch = entries(5, round_index * 5)
        sent.extend(item.inst for item in batch)
        cycles = await agent.play([
            Beat(entries=batch, decode_can_accept=0),
            Beat(in_valid=0, decode_can_accept=1),
        ])
        pointers.append(cycles[0].state_after["enq_ptr"])
        dequeue = cycles[1]
        check_dequeue(dequeue, count=5)
        received.extend(dequeue.after.lanes[lane].instr for lane in range(5))
    assert received == sent
    # 16 * 5 = 80 queue positions pass through a 48-entry queue.
    assert any(later < earlier for earlier, later in zip(pointers, pointers[1:]))
    assert agent.occupancy == 0


@pytest.mark.feature("IBUF-TOP-003")
async def test_flow_control_stalls_an_unannounced_fill_and_recovers(ibuffer_agent):
    agent = ibuffer_agent
    big = Beat(entries=entries(32), decode_can_accept=0)
    fill = Beat(entries=entries(15, 100), decode_can_accept=0)
    extra = Beat(entries=entries(8, 200), decode_can_accept=0)
    one = Beat(entries=entries(1, 250), decode_can_accept=0)
    drain = Beat(in_valid=0, decode_can_accept=1)
    refill = Beat(entries=entries(8, 300), decode_can_accept=0)
    cycles = await agent.play([big, fill, extra, one, drain, refill])

    assert cycles[0].events.fire == 1 and cycles[0].events.num_enq == 32
    assert cycles[0].state_after["occupancy"] == 32
    # The empty window absorbs eight entries while the beat is enqueued.
    assert cycles[1].events.fire == 1 and cycles[1].events.num_enq == 15
    assert cycles[1].events.num_out == 8
    assert cycles[1].state_after["occupancy"] == 39
    # The window is now full, so the queue can reach 47.
    assert cycles[2].events.num_out == 0
    assert cycles[2].events.fire == 1 and cycles[2].events.num_enq == 8
    assert cycles[2].state_after["occupancy"] == 47
    # One more instructed slot was announced, but only one slot is free and
    # the ready rule reserves it: the beat stalls.
    check_not_enqueued(cycles[3])
    assert cycles[3].before.in_ready == 0 and cycles[3].before.full == 1
    assert cycles[3].state_after["occupancy"] == 47
    check_dequeue(cycles[4], count=8)
    assert cycles[4].state_after["occupancy"] == 39
    assert cycles[5].before.in_ready == 1
    assert cycles[5].events.fire == 1 and cycles[5].events.num_enq == 8
    assert cycles[5].state_after["occupancy"] == 47


# ---------------------------------------------------------- vtype paths ----
@pytest.mark.feature("IBUF-TOP-005")
async def test_bypass_uses_the_speculated_vtype(ibuffer_agent):
    agent = ibuffer_agent
    spec = VType(illegal=0, vma=1, vta=0, vsew=2, vlmul=0)
    await agent.play([Beat(in_valid=0, walk_vtype_valid=1, walk_vtype=spec)])
    cycle = (await agent.play([Beat(entries=entries(1), decode_can_accept=1)]))[0]
    check_bypass(cycle)
    assert cycle.after.lanes[0].vtype == spec
    assert cycle.after.lanes[0].specvtype == spec


@pytest.mark.feature("IBUF-TOP-006")
async def test_vset_disables_bypass_and_queued_lanes_get_the_new_vtype(ibuffer_agent):
    agent = ibuffer_agent
    new = VType(illegal=0, vma=1, vta=1, vsew=2, vlmul=1)
    cycles = await agent.play([
        Beat(entries=(vset_entry(), entry(1)), decode_can_accept=1),
        Beat(in_valid=0, decode_can_accept=1),
    ])
    first, dequeue = cycles
    # The vset forces the queued path even though the queue was empty.
    assert first.events.use_bypass == 0
    assert first.state_after["occupancy"] == 2
    assert valid_lanes(first.after) == [0] * DECODE
    check_dequeue(dequeue, count=2)
    assert valid_lanes(dequeue.after) == [1, 1, 0, 0, 0, 0, 0, 0]
    # The vset lane and the following lane both carry the generated vtype.
    assert dequeue.after.lanes[0].vtype == new
    assert dequeue.after.lanes[1].vtype == new
    # specvtype is the pre-instruction snapshot.
    assert dequeue.after.lanes[0].specvtype == INIT_VTYPE
    assert dequeue.after.lanes[1].specvtype == new
    # The speculation register absorbed the vset because decode accepted.
    assert agent.snapshot()["vtype"]["vtype_spec"] == new.as_dict()


@pytest.mark.feature("IBUF-TOP-006")
async def test_appended_window_restarts_the_vtype_chain(ibuffer_agent):
    agent = ibuffer_agent
    new = VType(illegal=0, vma=0, vta=1, vsew=3, vlmul=0)
    # Window starts with two ordinary instructions.
    await agent.play([
        Beat(entries=entries(2), decode_can_accept=0),
        Beat(in_valid=0, decode_can_accept=1),
    ])
    # A later vset+instruction pair is appended after the old entries.  The
    # vtype chain numbers the new entries in window coordinates (lanes 2, 3).
    cycles = await agent.play([
        Beat(entries=(vset_entry(vsew=3, vlmul=0, vma=0, vta=1), entry(3)),
             decode_can_accept=0),
        Beat(in_valid=0, decode_can_accept=0),
    ])
    after = cycles[1].after
    assert valid_lanes(after) == [1, 1, 1, 1, 0, 0, 0, 0]
    assert after.lanes[2].vtype == new
    assert after.lanes[3].vtype == new
    assert after.lanes[2].specvtype == INIT_VTYPE
    assert after.lanes[3].specvtype == new


# ------------------------------------------------------------- backend -----
@pytest.mark.feature("IBUF-TOP-009")
async def test_walk_vtype_configures_the_next_dequeued_window(ibuffer_agent):
    agent = ibuffer_agent
    walked = VType(illegal=0, vma=1, vta=1, vsew=1, vlmul=2)
    await agent.play([Beat(in_valid=0, walk_vtype_valid=1, walk_vtype=walked)])
    cycles = await agent.play([
        Beat(entries=entries(2, 20), decode_can_accept=0),
        Beat(in_valid=0, decode_can_accept=1),
    ])
    dequeue = cycles[1]
    for lane in range(2):
        assert dequeue.after.lanes[lane].vtype == walked, lane


@pytest.mark.feature("IBUF-TOP-009")
async def test_commit_then_walk_to_arch_configures_the_window(ibuffer_agent):
    agent = ibuffer_agent
    arch = VType(illegal=0, vma=0, vta=1, vsew=3, vlmul=2)
    await agent.play([Beat(in_valid=0, commit_vtype_valid=1, commit_vtype=arch)])
    await agent.play([Beat(in_valid=0, walk_to_arch_vtype=1)])
    cycles = await agent.play([
        Beat(entries=entries(1, 30), decode_can_accept=0),
        Beat(in_valid=0, decode_can_accept=1),
    ])
    assert cycles[1].after.lanes[0].vtype == arch


@pytest.mark.feature("IBUF-TOP-009")
async def test_resuming_vtype_freezes_the_output_window(ibuffer_agent):
    agent = ibuffer_agent
    await agent.play([
        Beat(entries=entries(3, 40), decode_can_accept=0),
        Beat(in_valid=0, decode_can_accept=1),
    ])
    staged = agent.snapshot()["output_valid"]
    cycle = await agent.play([
        Beat(in_valid=0, decode_can_accept=1, resuming_vtype=1,
             walk_vtype_valid=1, walk_vtype=VType(illegal=0, vma=1, vta=1,
                                                  vsew=0, vlmul=3)),
    ])
    frozen = cycle[0]
    assert frozen.events.num_out == 0
    assert valid_lanes(frozen.before) == staged
    assert frozen.before.lanes == frozen.after.lanes
    # The walk update is still absorbed for the next non-resuming window.
    assert frozen.state_after["vtype"]["vtype_spec"]["vsew"] == 0


# -------------------------------------------------------------- flush ------
@pytest.mark.feature("IBUF-TOP-007")
async def test_flush_discards_queue_window_and_pointers(ibuffer_agent):
    agent = ibuffer_agent
    cycles = await agent.play([
        Beat(entries=entries(4), decode_can_accept=0),
        Beat(in_valid=0, decode_can_accept=1),
        Beat(entries=entries(4, 50), decode_can_accept=1, flush=1),
    ])
    assert valid_lanes(cycles[1].after) == [1, 1, 1, 1, 0, 0, 0, 0]
    flushed = cycles[2]
    check_flush(flushed)
    assert flushed.state_after["allow_enq"] == 1


@pytest.mark.feature("IBUF-TOP-007")
async def test_flush_while_full_restores_ready(ibuffer_agent):
    agent = ibuffer_agent
    cycles = await agent.play([
        Beat(entries=entries(32), decode_can_accept=0),
        Beat(entries=entries(15, 100), decode_can_accept=0),
        Beat(entries=entries(8, 200), decode_can_accept=0),
        Beat(in_valid=0, flush=1),
    ])
    assert cycles[1].state_after["occupancy"] == 39
    assert cycles[2].state_after["occupancy"] == 47
    check_flush(cycles[3])


# ---------------------------------------------------------- exceptions -----
@pytest.mark.feature("IBUF-TOP-008")
async def test_exception_attaches_to_the_first_queued_instruction(ibuffer_agent):
    agent = ibuffer_agent
    exception = ExceptionEntry(exc_type=1, cross_page=1,
                               backend_exception=1, satp_flush=1)
    cycles = await agent.play([
        Beat(entries=entries(3, 60), exception=exception, decode_can_accept=0),
        Beat(in_valid=0, decode_can_accept=1),
    ])
    dequeue = cycles[1]
    head = dequeue.after.lanes[0]
    assert head.exc_page_fault == 1
    assert head.cross_page_ipf_fix == 1
    assert head.backend_exception == 1
    assert head.satp_flush_first_fetch_fault == 1
    for lane in range(1, 3):
        row = dequeue.after.lanes[lane]
        assert (row.exc_page_fault, row.exc_guest_page_fault, row.exc_access_fault,
                row.exc_illegal, row.exc_hardware_error) == (0, 0, 0, 0, 0)
        assert row.cross_page_ipf_fix == 0
        assert row.satp_flush_first_fetch_fault == 0


@pytest.mark.feature("IBUF-TOP-008")
async def test_appended_exception_lands_at_each_staged_position(ibuffer_agent):
    """Append mode must attach the exception at the new window coordinate."""
    agent = ibuffer_agent
    for staged in range(1, 8):
        await agent.flush()
        await agent.play([Beat(entries=entries(staged), decode_can_accept=1)])
        exception = ExceptionEntry(exc_type=4, cross_page=1, satp_flush=1)
        cycles = await agent.play([
            Beat(entries=entries(1, 100), exception=exception,
                 decode_can_accept=0),
            Beat(in_valid=0, decode_can_accept=0),
        ])
        after = cycles[1].after
        assert after.lanes[staged].valid == 1, staged
        assert after.lanes[staged].exc_illegal == 1, staged
        assert after.lanes[staged].cross_page_ipf_fix == 1, staged
        assert after.lanes[staged].satp_flush_first_fetch_fault == 1, staged
        for lane in range(staged):
            assert after.lanes[lane].exc_illegal == 0, (staged, lane)


@pytest.mark.feature("IBUF-TOP-008")
async def test_queued_exception_attaches_at_each_dequeue_offset(ibuffer_agent):
    """The exception belongs to its own instruction, not always to lane 0."""
    agent = ibuffer_agent
    for offset in range(1, 8):
        await agent.flush()
        # Fill the output window so the queue does not auto-drain while the
        # ordinary instructions and then the exception instruction arrive.
        await agent.play([Beat(entries=entries(8, 400), decode_can_accept=1)])
        await agent.play([Beat(entries=entries(offset, 500),
                               decode_can_accept=0)])
        exception = ExceptionEntry(exc_type=1, cross_page=1)
        cycles = await agent.play([
            Beat(entries=entries(1, 900), exception=exception,
                 decode_can_accept=0),
            Beat(in_valid=0, decode_can_accept=1),
        ])
        after = cycles[1].after
        assert after.lanes[offset].valid == 1, offset
        assert after.lanes[offset].exc_page_fault == 1, offset
        assert after.lanes[offset].cross_page_ipf_fix == 1, offset
        for lane in range(DECODE):
            if lane != offset:
                assert after.lanes[lane].exc_page_fault == 0, (offset, lane)


@pytest.mark.feature("IBUF-TOP-008")
async def test_bypass_delivers_the_exception_without_a_queued_copy(ibuffer_agent):
    agent = ibuffer_agent
    exception = ExceptionEntry(exc_type=2, satp_flush=1)
    cycle = (await agent.play([
        Beat(entries=entries(1, 70), exception=exception, decode_can_accept=1),
    ]))[0]
    assert cycle.events.use_bypass == 1
    head = cycle.after.lanes[0]
    assert head.exc_guest_page_fault == 1
    assert head.satp_flush_first_fetch_fault == 1
    # The instruction was consumed by bypass, so the queue is still empty and
    # the exception must not reappear on a later dequeue.
    assert cycle.state_after["occupancy"] == 0
    later = await agent.cycle(Inputs(decode_can_accept=1))
    assert all(row.valid == 0 for row in later.after.lanes)


@pytest.mark.feature("IBUF-TOP-008")
async def test_satp_flush_without_exception_does_not_assert_first_fetch_fault(
        ibuffer_agent):
    agent = ibuffer_agent
    exception = ExceptionEntry(satp_flush=1)
    cycles = await agent.play([
        Beat(entries=entries(1, 80), exception=exception, decode_can_accept=0),
        Beat(in_valid=0, decode_can_accept=1),
    ])
    head = cycles[1].after.lanes[0]
    assert head.satp_flush_first_fetch_fault == 0
    assert head.exc_page_fault == 0


# --------------------------------------------------------- stall reason ----
@pytest.mark.feature("IBUF-TOP-010")
async def test_stall_reason_reports_the_highest_topdown_reason(ibuffer_agent):
    agent = ibuffer_agent
    cycles = await agent.play([
        Beat(entries=entries(3), decode_can_accept=0, topdown_reasons=1 << 20),
        Beat(in_valid=0, decode_can_accept=1),
    ])
    assert cycles[1].after.stall_reason == (0, 0, 0, 20, 20, 20, 20, 20)


@pytest.mark.feature("IBUF-TOP-010")
async def test_stall_reason_falls_back_to_fetch_fragmentation(ibuffer_agent):
    agent = ibuffer_agent
    cycles = await agent.play([
        Beat(entries=entries(3, 10), decode_can_accept=0),
        Beat(in_valid=0, decode_can_accept=1),
    ])
    assert cycles[1].after.stall_reason == (0, 0, 0, 13, 13, 13, 13, 13)


@pytest.mark.feature("IBUF-TOP-010")
async def test_empty_window_reports_zero_stall_reasons(ibuffer_agent):
    agent = ibuffer_agent
    cycle = await agent.cycle(Inputs())
    assert cycle.before.stall_reason == (0,) * DECODE


@pytest.mark.feature("IBUF-TOP-010")
async def test_control_flow_redirect_override_reaches_the_reason_lanes(ibuffer_agent):
    agent = ibuffer_agent
    cycles = await agent.play([
        Beat(entries=entries(3, 20), decode_can_accept=0),
        Beat(in_valid=0, decode_can_accept=1),          # window fills
        Beat(in_valid=0, backend_redirect=1, control_flow_redirect=1,
             tage_miss_bubble=1),
        Beat(in_valid=0),
        Beat(in_valid=0),                               # stage 1 now carries it
    ])
    # Five wasted lanes and the highest active reason (TAGEMissBubble = 3).
    assert cycles[4].before.stall_reason == (0, 0, 0, 3, 3, 3, 3, 3)


# ------------------------------------------------------------- offsets -----
@pytest.mark.feature("IBUF-TOP-003")
async def test_all_four_write_bank_offsets_are_accepted(ibuffer_agent):
    agent = ibuffer_agent
    for index in range(4):
        cycles = await agent.play([
            Beat(entries=entries(1, index), decode_can_accept=0),
            Beat(in_valid=0, decode_can_accept=1),
        ])
        assert cycles[0].events.fire == 1
        assert cycles[1].after.lanes[0].instr == entry(index).inst
        check_no_head_bubble(cycles[1])
    assert agent.occupancy == 0


# -------------------------------------------------------------- random -----
@pytest.mark.feature("IBUF-TOP-001")
@pytest.mark.feature("IBUF-TOP-002")
@pytest.mark.feature("IBUF-TOP-003")
@pytest.mark.feature("IBUF-TOP-004")
@pytest.mark.feature("IBUF-TOP-005")
@pytest.mark.feature("IBUF-TOP-006")
@pytest.mark.feature("IBUF-TOP-007")
@pytest.mark.feature("IBUF-TOP-008")
@pytest.mark.feature("IBUF-TOP-009")
@pytest.mark.feature("IBUF-TOP-010")
async def test_randomized_traffic_against_the_composed_model(ibuffer_agent):
    seed = int(os.environ.get("UCV_SEED", "1"))
    rng = random.Random(seed * 104_729 + 31)
    agent = ibuffer_agent
    for step in range(300):
        offset = agent.next_lane_offset
        room = 32 - offset
        quiet = rng.random() < 0.25
        if quiet:
            count = 0
            beat_entries: tuple[FetchEntry, ...] = ()
        else:
            count = rng.choice((0, 1, 2, 3, 4, 6, 8, 12, 16, min(24, room)))
            count = min(count, room)
            beat_entries = tuple(
                vset_entry(vsew=rng.randrange(4), vlmul=rng.choice((0, 1, 2, 3, 5, 6, 7)),
                           vma=rng.randrange(2), vta=rng.randrange(2),
                           rd=rng.choice((0, 1, 5)), rs1=rng.choice((0, 2, 10)))
                if rng.random() < 0.25 else random_entry(rng)
                for lane in range(count))
        exception = (ExceptionEntry(exc_type=rng.choice((0, 1, 2, 3, 4, 5)),
                                    cross_page=rng.randrange(2),
                                    backend_exception=rng.randrange(2),
                                    satp_flush=rng.randrange(2))
                     if not quiet and rng.random() < 0.10 else ZERO_EXCEPTION)
        beat = Beat(
            entries=beat_entries,
            in_valid=0 if quiet else 1,
            exception=exception,
            decode_can_accept=int(rng.random() < 0.55),
            resuming_vtype=int(rng.random() < 0.05),
            walk_to_arch_vtype=int(rng.random() < 0.08),
            walk_vtype_valid=int(rng.random() < 0.08),
            walk_vtype=backend_vtype(rng),
            vsetvl_vtype=backend_vtype(rng),
            commit_vtype_valid=int(rng.random() < 0.08),
            commit_vtype=backend_vtype(rng),
            commit_has_vsetvl=int(rng.random() < 0.02),
            topdown_reasons=(rng.getrandbits(76) if rng.random() < 0.20 else 0),
            backend_redirect=int(rng.random() < 0.03),
            control_flow_redirect=int(rng.random() < 0.50),
            memory_violation_redirect=int(rng.random() < 0.50),
            tage_miss_bubble=rng.randrange(2),
            ittage_miss_bubble=rng.randrange(2),
            ras_miss_bubble=rng.randrange(2),
            flush=int(rng.random() < 0.02),
        )
        try:
            await agent.play([beat])
        except BaseException:
            print(f"\nibuffer random step {step}\nbeat={beat!r}")
            print(f"state={agent.snapshot()}")
            raise
    await agent.flush()
    assert agent.occupancy == 0
    assert agent.snapshot()["output_valid"] == [0] * DECODE
