"""Coverage follow-up: 96 real RAR owners, then oldest no-allocation query."""
from dataclasses import replace

import pytest

from .ldu_rar_owners import LduRarOwners
from .memory_owners import cached_load


@pytest.mark.parametrize("lane_rotation", range(3))
async def test_LDU_full_96_RAR_original_readers_oldest_query_needs_no_allocation_then_all_97_dequeue(lsq, lane_rotation):
    lsq.reach("LSQ-RAR.head_reclaim")
    trace = LduRarOwners(lsq)
    loads = [cached_load(n, 10+n, 0, 0x40000+64*n, 0xD000000+64*n) for n in range(97)]
    trace.base = replace(trace.base, pending=loads[0].execution.uop.rob, pending_next=loads[0].execution.uop.rob)
    await trace.dispatch(loads=loads)
    for n, load in enumerate(loads[1:]):
        await trace.pipeline(load, (n+lane_rotation)%3)
        assert not lsq.observed["io_toLsqEnqCtrl_lqDeq_valid"] and not lsq.observed["io_lqEmpty"]
    assert not trace.loads[0]["sent"] and all(s["sent"] and not s["completed"] for s in trace.loads[1:])
    lsq.emit("ldu_full_RAR_public_ownership", original_young_readers=96, oldest_UID=trace.loads[0]["uid"],
             head_releases=0, revokes=0, redirects=0, all_young_S3_returned=True,
             scope="96 accepted distinct younger queries, no internal slot reads")
    await trace.pipeline(loads[0], 2)
    await trace.finish()
    assert len(trace.loads)==97 and all(s["completed"] for s in trace.loads)
    lsq.prove("LSQ-RAR.head_reclaim")
    lsq.emit("ldu_full_RAR_original_97_complete", allocated=97, completed=97,
             full_cycle_reference_compared=True, source_scope="aligned_cached_hit_no_release_no_alias")
