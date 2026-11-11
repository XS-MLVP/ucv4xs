"""Actual interleaved dispatch gives each Load its exclusive Store prefix."""

from dataclasses import replace
import hashlib

import pytest

from suites.memblock.lsq.testbenches.raw.transactions import SqPtr
from suites.memblock.lsq.testbenches.store_queue.model.store_payload import add_digest
from suites.memblock.lsq.testbenches.store_queue.model.store_prefix import WINDOWS
from suites.memblock.lsq.testbenches.store_queue.model.store_prefix import check_byte_response
from suites.memblock.lsq.testbenches.store_queue.model.store_prefix import lifetime
from suites.memblock.lsq.testbenches.store_queue.model.store_prefix import producer
from suites.memblock.lsq.testbenches.store_queue.model.store_prefix import save_witness
from suites.memblock.lsq.testbenches.vlq.transactions import RobPtr
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.memory_owners import MemoryOwners
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.memory_owners import StoreOwner
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.memory_owners import cached_load


@pytest.mark.parametrize("lane", range(3))
async def test_real_interleaved_Load_prefix_excludes_younger_alias_and_completes(lsq, tmp_path, lane):
    trace, stream, lives, program = MemoryOwners(lsq), hashlib.sha256(), [], 10
    for gen, (start, end) in enumerate(WINDOWS):
        assert trace.sq_head == start
        trace.base = replace(trace.base, pending=RobPtr.encode(program - 1),
                             pending_next=RobPtr.encode(program - 1), sbuffer_ready=(False, False))
        loads = []
        for position in range(start, end):
            va, pa, value = producer(gen, position)
            store = StoreOwner(position, RobPtr.encode(program), va, pa, size=0, value=value)
            load = cached_load(position, program + 1, position + 1, va, pa, size=0)
            # Separate real dispatches preserve program order across ROB wrap;
            # no synthetic SQ feedback and no unowned Forward-only load probes.
            await trace.dispatch(stores=[store])
            await trace.dispatch(loads=[load])
            loads.append(load)
            program += 2
        await trace.write_all(range(start, end))
        assert all(trace.stores[position]["s2_done"] and trace.stores[position]["data_sent"] for position in range(start, end))
        assert trace.sq_head == start
        for position, load in zip(range(start, end), loads):
            assert load.execution.uop.sq == SqPtr.encode(position + 1)
            response = await trace.forward(load, lane)
            expected = producer(gen, position)
            check_byte_response(response, expected)
            add_digest(stream, [gen, position, position + 1, lane, *expected])
            assert trace.sq_head == start
        await trace.execute(loads)
        await trace.finish(pending=RobPtr.encode(program))
        assert trace.sq_head == end
        assert all(trace.stores[position]["completed"] for position in range(start, end))
        assert all(trace.active_loads[load.execution.uop.lq]["completed"] for load in loads)
        for position in range(start, end):
            state = trace.stores[position]
            add_digest(stream, ["real_store_complete", state["uid"], position, state["last_fire"]])
        lives.append(lifetime(gen, end - start, normal_store_completions=end - start,
                    normal_load_completions=end - start, sbuffer_consumed_owners=end - start,
                    query_lane=lane, younger_alias_written_before_first_query=True))
    assert len(trace.stores) == len(trace.loads) == trace.load_released == len(trace.fragments_fired) == 256
    assert not trace.cancelled
    lsq.prove("LSQ-FORWARD.aligned", "LSQ-FORWARD.youngest", "LSQ-FORWARD.sqid", "LSQ-FORWARD.wrap")
    save_witness(tmp_path / "store-prefix-byte-witness.json", "lsq_wrapper", lives, stream,
                 query_lane=lane, completed_store_uids=256, completed_load_uids=256,
                 scope="real interleaved Store/Load dispatch, original SQ/LQ/ROB and S3 completion, actual Sbuffer byte consumption and normal reuse; original full Wrapper reference stays active")
