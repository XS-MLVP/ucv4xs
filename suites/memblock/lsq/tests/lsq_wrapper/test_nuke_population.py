"""Capacity dependencies produced/reclaimed by real SQ and VLQ, not test pins."""
from dataclasses import replace

import pytest

from lsqverify.rar.types import Query as RarQuery
from lsqverify.raw.types import Query as RawQuery
from lsqverify.replay.types import Cause
from lsqverify.vlq.types import RobPtr
from .memory_owners import MemoryOwners, StoreOwner, cached_load
from .test_nuke_memory import raw_query


async def blocked(trace, target):
    for _ in range(8):
        await trace.cycle(replay_ready=(True, True, True))
        assert "grant" not in trace.active_loads[target.execution.uop.lq]
        assert not any(trace.env.observed[f"io_replay_{bank}_valid"] for bank in range(3))


async def finish_target(trace, target):
    await trace.execute([s["load"] for s in trace.loads if not s["sent"] and s["load"].execution.uop.lq != target.execution.uop.lq])
    await trace.replay_complete(target)
    await trace.finish()


@pytest.mark.parametrize("lane", range(3))
async def test_real_cached_rar_96_records_wait_for_actual_vlq_head_then_replay_uid_completes(lsq, lane):
    trace = MemoryOwners(lsq)
    loads = [cached_load(pos, 10 + pos, 0, 0x100000 + pos * 64, 0x80100000 + pos * 64) for pos in range(120)]
    target = replace(loads[-1], execution=replace(loads[-1].execution, need_replay=True, causes=1 << Cause.RAR_CAPACITY))
    await trace.dispatch(loads=loads[:-1] + [target])
    for load in loads[1:97]:
        queries = [RarQuery()] * 3
        queries[lane] = RarQuery(True, load.execution.uop.rob, load.execution.uop.lq, load.paddr, True)
        await trace.cycle(rar_queries=tuple(queries))
        assert lsq.pre_observed[f"io_ldu_rarNukeQuery_{lane}_req_ready"]
    # Actual execution is allowed out of order, not virtual retirement over
    # the unfinished oldest Load. Its real VLQ head still pins all96 records.
    await trace.execute(loads[1:97])
    assert trace.load_released == 0
    queries = [RarQuery()] * 3
    queries[lane] = RarQuery(True, target.execution.uop.rob, target.execution.uop.lq, target.paddr, True)
    await trace.cycle(rar_queries=tuple(queries))
    assert not lsq.pre_observed[f"io_ldu_rarNukeQuery_{lane}_req_ready"]
    await trace.execute([target])
    lsq.reach("LSQ-RAR.head_reclaim", "LSQ-STRESS.capacity")
    await blocked(trace, target)
    await trace.execute([loads[0]])
    # Only the real S3 completion above can move the hidden VLQ head and
    # therefore free RAR. No head/full feedback exists on LsqWrapper Inputs.
    await finish_target(trace, target)
    assert all(s["completed"] for s in trace.loads) and trace.load_released == 120
    lsq.prove("LSQ-RAR.head_reclaim", "LSQ-ALLOC.lq_capacity")


@pytest.mark.parametrize("lane", range(3))
async def test_real_raw_56_records_wait_for_actual_sta_pointer_then_replay_uid_completes(lsq, lane):
    trace = MemoryOwners(lsq)
    stores = [StoreOwner(pos, RobPtr.encode(10), 0x20000 + pos * 16, 0xA020000 + pos * 16,
                         value=0x1122334455667700 + pos) for pos in range(8)]
    loads = [cached_load(pos, 11 + pos, 8, 0x100000 + pos * 64, 0x80100000 + pos * 64) for pos in range(120)]
    target = replace(loads[-1], execution=replace(loads[-1].execution, need_replay=True, causes=1 << Cause.RAW_CAPACITY))
    await trace.dispatch(stores, loads[:-1] + [target])
    for load in loads[:56]:
        queries = [RawQuery()] * 3
        queries[lane] = raw_query(load)
        await trace.cycle(raw_queries=tuple(queries))
        assert lsq.pre_observed[f"io_ldu_rawNukeQuery_{lane}_req_ready"]
    await trace.execute(loads[:56])
    queries = [RawQuery()] * 3
    queries[lane] = raw_query(target)
    await trace.cycle(raw_queries=tuple(queries))
    assert not lsq.pre_observed[f"io_ldu_rawNukeQuery_{lane}_req_ready"]
    await trace.execute([target])
    lsq.reach("LSQ-STRESS.capacity")
    await blocked(trace, target)
    assert trace.load_released == 56
    # Real non-overlapping Store addresses affect both PSQ and RAW. They
    # neither invent rollback nor fake a ready pointer on the Load branch.
    await trace.write_all()
    lsq.expect({"io_issuePtrExt_value": 8, "io_nuke_rollback_0_valid": 0, "io_nuke_rollback_1_valid": 0},
               "actual STA prefix crosses exclusive SQ8 and reclaims the real RAW pool without false conflict")
    await finish_target(trace, target)
    assert trace.load_released == 120 and all(s["completed"] for s in trace.stores.values())
    # This is a non-overlapping-PA control, NOT a byte-mask negative or a
    # complete mixed stress/capacity acceptance claim.
    lsq.prove("LSQ-ALLOC.lq_capacity")
