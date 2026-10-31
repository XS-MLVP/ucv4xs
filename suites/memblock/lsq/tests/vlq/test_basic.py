"""Initial timing measurements before reviewing the native coverage gaps."""
from suites.memblock.lsq.vlq.types import QueuePtr


async def test_empty_idle(vlq):
    await vlq.idle(6)
    assert vlq.observed.empty
    assert vlq.observed.head == QueuePtr()
    assert not vlq.observed.dequeue_valid and not vlq.observed.recovery_valid


async def test_single_flow_completion_pipeline(vlq):
    await vlq.cycle(dispatch=vlq.build_dispatch((1,)))
    await vlq.idle(2)
    assert not vlq.observed.empty and vlq.observed.head == QueuePtr()
    await vlq.cycle(writebacks={0: vlq.wb(0)})
    assert vlq.observed.head == QueuePtr() and not vlq.observed.dequeue_valid
    await vlq.cycle()
    assert vlq.observed.head == QueuePtr() and not vlq.observed.dequeue_valid
    await vlq.cycle()
    assert vlq.observed.head == QueuePtr.encode(1)
    assert vlq.observed.dequeue_valid and vlq.observed.dequeue_count == 1
    assert not vlq.observed.empty
    await vlq.cycle()
    assert vlq.observed.empty and not vlq.observed.dequeue_valid


async def test_short_intervals_on_sparse_dispatch_lanes(vlq):
    result = await vlq.cycle(dispatch=vlq.build_dispatch((2, 1), lanes=(1, 7)))
    assert tuple(item.position for item in result.allocated) == (0, 1, 2)
    assert await vlq.complete_and_drain() == (0, 1, 2)
    assert vlq.observed.head == QueuePtr.encode(3) and vlq.observed.empty
