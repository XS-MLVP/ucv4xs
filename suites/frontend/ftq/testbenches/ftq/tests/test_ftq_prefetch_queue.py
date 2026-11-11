"""FTQ software-prefetch queue on the a0c2a26cb enhanced-iprefetch baseline."""

from __future__ import annotations

import pytest

from suites.frontend.ftq.testbenches.ftq.transactions.cycle import FtqInput
from suites.frontend.ftq.testbenches.ftq.transactions.types import BackendRedirect
from suites.frontend.ftq.testbenches.ftq.transactions.types import SoftPrefetch
from suites.frontend.ftq.testbenches.ftq.model import CallRet
from suites.frontend.ftq.testbenches.ftq.tests.support import allocate
from suites.frontend.ftq.testbenches.ftq.tests.support import resolve

pytestmark = pytest.mark.feature("FTQ-TOP-019")


def start_of(vaddr: int) -> int:
    start = vaddr >> 1
    return start | (1 << 49) if start & (1 << 48) else start


def set_of(start: int) -> int:
    return (start // 32) % 256


async def test_software_prefetch_issues_source_sw_without_moving_the_fdip_pointer(ftq_agent):
    agent = ftq_agent
    vaddr = 0x8000_2400
    await agent.soft_prefetch([SoftPrefetch(vaddr), None, None])
    assert agent.receipt()["frontend"]["prefetch_queue"]["distance"] == 1

    request = agent.prefetch()
    assert request.valid
    assert (request.start, request.next_line) == (start_of(vaddr), 0)
    assert (request.set0, request.set1) == (set_of(start_of(vaddr)), 0)
    assert not request.cross_line
    assert (request.source, request.req1_source) == (1, 0)
    assert (request.index, request.index_flag) == (0, 0)
    assert request.case == 0

    await agent.consumers(prefetch=1)
    await agent.step(1)
    assert agent.pointers().pf[0].value == 0
    assert agent.receipt()["frontend"]["prefetch_queue"]["distance"] == 0
    assert not agent.prefetch().valid


@pytest.mark.parametrize('second_vaddr,expected_case', (
    (0x8000_0010, 1),   # same 64-byte line
    (0x8000_0040, 8),   # interleaved lines on the same page
    (0x8000_2000, 0),   # cross-page pair cannot use 2-prefetch
))
async def test_two_queued_prefetch_requests_report_the_declared_case(
        ftq_agent, second_vaddr, expected_case):
    agent = ftq_agent
    first = 0x8000_0000
    await agent.soft_prefetch([SoftPrefetch(first), SoftPrefetch(second_vaddr), None])
    request = agent.prefetch()
    assert request.valid
    assert request.case == expected_case
    assert (request.source, request.req1_source) == (1, 1)
    assert request.start == start_of(first)
    if expected_case:
        assert request.req1_start == start_of(second_vaddr)
    assert agent.pointers().pf[0].value == 0

    await agent.consumers(prefetch=1)
    await agent.step(1)
    assert agent.pointers().pf[0].value == 0
    assert agent.receipt()["frontend"]["prefetch_queue"]["distance"] == (
        0 if expected_case else 1)


async def test_mixed_prefetch_consumes_one_fdip_and_one_queued_request(ftq_agent):
    agent = ftq_agent
    await allocate(agent, 2, base=0x8000_0000, step=0x20, with_meta=False)
    queued = 0x8000_0020 << 1
    await agent.soft_prefetch([SoftPrefetch(queued), None, None])

    request = agent.prefetch()
    assert request.valid and request.case == 8
    assert (request.start, request.source) == (0x8000_0000, 0)
    assert (request.req1_start, request.req1_source) == (0x8000_0020, 1)
    assert request.req1_index == 1

    await agent.consumers(prefetch=1)
    await agent.step(1)
    assert agent.pointers().pf[0].value == 1
    assert agent.receipt()["frontend"]["prefetch_queue"]["distance"] == 0


async def test_queued_prefetch_wins_when_fdip_runs_past_the_preferred_distance(ftq_agent):
    agent = ftq_agent
    await allocate(agent, 5, base=0x8000_0000, step=0x20, meta_limit=1)
    await agent.consumers(prefetch=1)
    for _ in range(3):
        await agent.step(1)
    assert agent.pointers().pf[0].value == 3

    await agent.consumers(prefetch=0)
    queued = 0x9000_0000
    await agent.soft_prefetch([SoftPrefetch(queued), None, None])
    await agent.consumers(prefetch=1)
    request = agent.prefetch()
    assert request.valid
    assert (request.source, request.req1_source) == (1, 0)
    assert request.start == start_of(queued)

    await agent.step(1)
    assert agent.pointers().pf[0].value == 3
    assert agent.receipt()["frontend"]["prefetch_queue"]["distance"] == 0


async def test_soft_prefetch_queue_capacity_drops_excess_and_keeps_fifo_order(ftq_agent):
    agent = ftq_agent
    offered = [0x8000_0000 + index * 0x40 for index in range(7)]
    dropped = [0x8000_1000, 0x8000_1040]
    for base in (offered[:3], offered[3:6], offered[6:]):
        await agent.soft_prefetch([SoftPrefetch(value) for value in base] + [None] * (3 - len(base)))
    await agent.soft_prefetch([SoftPrefetch(value) for value in dropped] + [None])
    assert agent.receipt()["frontend"]["prefetch_queue"]["distance"] == 7

    await agent.consumers(prefetch=1)
    observed = []
    for _ in range(7):
        request = agent.prefetch()
        if not request.valid:
            break
        observed.append(request.start)
        if request.case:
            observed.append(request.req1_start)
        await agent.step(1)
    assert observed == [start_of(value) for value in offered]
    assert agent.pointers().pf[0].value == 0
    assert agent.receipt()["frontend"]["prefetch_queue"]["distance"] == 0
    assert not agent.prefetch().valid


async def test_enqueue_and_dequeue_on_the_same_edge_keep_queue_order(ftq_agent):
    agent = ftq_agent
    first = 0x8000_2000
    second = 0x8000_3000
    await agent.soft_prefetch([SoftPrefetch(first), None, None])
    await agent.consumers(prefetch=1)
    await agent.soft_prefetch_cycle([SoftPrefetch(second), None, None])
    await agent.soft_prefetch_release()
    assert agent.pointers().pf[0].value == 0
    assert agent.receipt()["frontend"]["prefetch_queue"]["distance"] == 1
    request = agent.prefetch()
    assert request.valid and request.start == start_of(second)

    await agent.step(1)
    assert agent.receipt()["frontend"]["prefetch_queue"]["distance"] == 0


async def test_every_enqueue_pointer_phase_and_lane_subset_is_offered(ftq_agent):
    agent = ftq_agent
    serial = 0

    async def offer(mask: int) -> None:
        nonlocal serial
        lanes = []
        for lane in range(3):
            if mask & (1 << lane):
                lanes.append(SoftPrefetch(0x9000_0000 + serial * 0x100))
                serial += 1
            else:
                lanes.append(None)
        await agent.soft_prefetch(lanes)

    async def drain() -> None:
        await agent.consumers(prefetch=1)
        while agent.frontend.prefetch_queue.distance:
            await agent.step(1)
        await agent.consumers(prefetch=0)

    phase = 0
    for target in range(8):
        while phase != target:
            await offer(1 << 0)
            phase = (phase + 1) % 8
        for mask in (0b111, 0b011, 0b101, 0b110, 0b010, 0b100):
            capacity = 7 - agent.frontend.prefetch_queue.distance
            accepted = min(bin(mask).count('1'), capacity)
            await offer(mask)
            phase = (phase + accepted) % 8
            await drain()
    assert agent.frontend.prefetch_queue.distance == 0


async def test_every_software_prefetch_address_bit_toggles_in_all_lanes(ftq_agent):
    agent = ftq_agent
    await agent.consumers(prefetch=1)
    for value in (0, (1 << 50) - 1):
        for _ in range(8):
            await agent.soft_prefetch([SoftPrefetch(value)] * 3)
            while agent.frontend.prefetch_queue.distance:
                await agent.step(1)
    await agent.consumers(prefetch=0)
    assert agent.frontend.prefetch_queue.distance == 0


async def test_eight_physical_slots_and_pointer_wrap_preserve_fifo_order(ftq_agent):
    agent = ftq_agent
    for serial in range(17):
        vaddr = 0x8000_0000 + serial * 0x40
        await agent.consumers(prefetch=0)
        await agent.soft_prefetch([SoftPrefetch(vaddr), None, None])
        assert agent.frontend.prefetch_queue.distance == 1
        await agent.consumers(prefetch=1)
        request = agent.prefetch()
        assert request.valid
        assert request.start == start_of(vaddr)
        assert request.source == 1
        if request.case:
            assert request.req1_source == 1
        await agent.step(1)
        assert agent.frontend.prefetch_queue.distance == 0
    await agent.consumers(prefetch=0)


async def test_fdip_lane_source_is_zero_and_sw_source_is_one(ftq_agent):
    agent = ftq_agent
    await allocate(agent, 1, base=0x8000_0000, step=0x10)
    request = agent.prefetch()
    assert request.valid and request.case == 0
    assert request.source == 0

    await agent.soft_prefetch([SoftPrefetch(0x8000_0020 << 1), None, None])
    request = agent.prefetch()
    assert request.valid and request.case == 8
    assert (request.source, request.req1_source) == (0, 1)
    assert agent.frontend.prefetch_queue.distance == 1

    await agent.consumers(prefetch=1)
    await agent.step(1)
    assert agent.frontend.prefetch_queue.distance == 0
    await agent.consumers(prefetch=0)


async def _park_fdip_beyond_the_preferred_distance(agent):
    """Keep FDIP one-lane only and advance fetch so the queue is selected."""

    await allocate(agent, 4, base=0x8000_0000, step=0x20, meta_limit=1)
    await agent.consumers(prefetch=0, train=0, mainpipe=1)
    await agent.step(3)
    await agent.consumers(mainpipe=0)


async def test_soft_prefetch_and_backend_resolve_share_one_edge(ftq_agent):
    agent = ftq_agent
    await _park_fdip_beyond_the_preferred_distance(agent)
    vaddr = 0x8000_4000
    frame = FtqInput(
        resolve=(resolve(0, pc=0x8000_0000, offset=1, mispredict=0), None, None),
        soft_prefetch=(SoftPrefetch(vaddr), None, None))
    await agent.cycle(frame)
    assert agent.frontend.prefetch_queue.distance == 1
    await agent.cycle(FtqInput())

    await agent.consumers(prefetch=1, train=1)
    request = agent.prefetch()
    assert request.valid and request.start == start_of(vaddr)
    assert request.source == 1
    for _ in range(8):
        training = agent.training()
        if training is not None:
            break
        await agent.step(1)
    training = agent.training()
    assert training is not None
    assert [branch.position for branch in training.branches] == [1]
    await agent.step(1)
    await agent.consumers(prefetch=0, train=0)


async def test_soft_prefetch_and_callret_commit_share_one_edge(ftq_agent):
    agent = ftq_agent
    await _park_fdip_beyond_the_preferred_distance(agent)
    vaddr = 0x8000_5000
    rows = [CallRet(0, 1)] + [None] * 7
    await agent.cycle(FtqInput(callret=tuple(rows),
                               soft_prefetch=(SoftPrefetch(vaddr), None, None)))
    assert agent.frontend.prefetch_queue.distance == 1
    event = agent.commit_event()
    assert event is not None and event.ras_action == 1
    await agent.cycle(FtqInput())

    await agent.consumers(prefetch=1)
    request = agent.prefetch()
    assert request.valid and request.start == start_of(vaddr)
    assert request.source == 1
    await agent.step(1)
    assert agent.frontend.prefetch_queue.distance == 0
    await agent.consumers(prefetch=0)


async def test_redirect_suppresses_fdip_but_keeps_a_queued_sw_prefetch(ftq_agent):
    agent = ftq_agent
    await allocate(agent, 2, base=0x8000_0000, step=0x20, with_meta=False)
    fdip = agent.prefetch()
    assert fdip.valid and fdip.source == 0

    await agent.soft_prefetch([SoftPrefetch(0x8000_6000), None, None])
    assert agent.frontend.prefetch_queue.distance == 1
    await agent.backend_redirect(BackendRedirect(
        0, pc=0x8000_0000, offset=1, target=0x8000_9000))
    request = agent.prefetch()
    assert request.valid and request.source == 1
    assert request.start == start_of(0x8000_6000)
    await agent.consumers(prefetch=1)
    request = agent.prefetch()
    assert request.source == 1
    await agent.step(1)
    assert agent.frontend.prefetch_queue.distance == 0
    await agent.consumers(prefetch=0)


async def test_reset_clears_a_pending_software_prefetch_queue(ftq_agent):
    agent = ftq_agent
    await agent.soft_prefetch([SoftPrefetch(0x8000_4000), None, None])
    assert agent.receipt()["frontend"]["prefetch_queue"]["distance"] == 1
    await agent.reset()
    assert not agent.prefetch().valid
    assert agent.receipt()["frontend"]["prefetch_queue"]["distance"] == 0

    await agent.soft_prefetch([SoftPrefetch(0x8000_5000), None, None])
    await agent.consumers(prefetch=1)
    request = agent.prefetch()
    assert request.valid and request.start == start_of(0x8000_5000)
    await agent.step(1)
    assert agent.receipt()["frontend"]["prefetch_queue"]["distance"] == 0
