"""Discriminating native controls for the Sbuffer public transaction contract."""
from dataclasses import replace

import pytest

from suites.memblock.sbuffer.execution import execution
from suites.memblock.sbuffer.sbuffer.model import Enq


async def test_active_bytes_override_inflight_with_old_byte_fallback(sbuffer_env):
    env = sbuffer_env
    env.configure(timeout_cycles=2)
    async with execution(env):
        await env.reset()
        await env.enqueue([Enq(4, 6, 0, 15, 0x11111111)])
        old = await env.wait_req('old bytes')
        await env.accept(old, 'timeout')
        await env.enqueue([Enq(4, 6, 0, 3, 0x2222)])
        await env.settle(3)
        for lane in range(3):
            response = await env.forward(lane, 6 << 6, 4 << 6)
            assert response.mask == 15
            assert response.data[:4] == (0x22, 0x22, 0x11, 0x11)
        await env.hit(old)
        fresh = await env.wait_req('new bytes')
        await env.accept(fresh, 'timeout')
        await env.hit(fresh)
        await env.settle(3)
        assert env.status().empty


async def test_kill_suppresses_a_real_virtual_physical_mismatch(sbuffer_env):
    env = sbuffer_env
    env.configure(timeout_cycles=0x3FFFFF)
    async with execution(env):
        await env.reset()
        await env.enqueue([Enq(4, 6, 0, 15, 0x11111111)])
        await env.settle(3)
        for lane in range(3):
            normal = await env.forward(lane, 6 << 6, 9 << 6)
            killed = await env.forward(lane, 6 << 6, 9 << 6, kill=True)
            assert normal.invalid and not killed.invalid
            assert killed.mask == normal.mask == 15
            assert killed.data[:4] == normal.data[:4] == (0x11,) * 4


async def test_cmo_exit_does_not_leave_a_fence_drain_with_sq_nonempty(sbuffer_env):
    env = sbuffer_env
    env.configure(timeout_cycles=0x3FFFFF)
    async with execution(env):
        await env.reset()
        await env.enqueue([Enq(10, 12, 0, 15, 0x11111111)])
        await env.settle(3)
        await env.start_flush(cmo=True, sqempty=0, mshr=1)
        assert len(await env.drain_requests('drain_flush')) == 1
        # Return the CMO source at the first registered sbempty, then model the
        # CBO-state and MemBlock RegNext return latency. Arbitrarily holding the
        # level flush for four extra cycles can re-enter drain_all while idle;
        # dropping isCmo at that arbitrary phase is not this producer sequence.
        for _ in range(8):
            await env.edge()
            if env.status().empty:
                break
        assert env.status().empty and not env.status().flush_complete
        await env.settle(2)
        await env.end_flush()
        await env.settle(3)
        await env.enqueue([Enq(11, 13, 0, 15, 0x22222222)])
        # Contract-specific control: high timeout, low occupancy, no flush/replay.
        # It is not a general ISA claim that a store may never write out early.
        await env.no_req_for(12, 'CMO classification must not leave drain_all')


async def test_two_outstanding_requests_can_complete_in_reverse_order(sbuffer_env):
    env = sbuffer_env
    env.configure(timeout_cycles=2)
    async with execution(env):
        await env.reset()
        await env.enqueue([Enq(20, 24, 1, 15, 0x11111111), Enq(21, 25, 2, 15, 0x22222222)])
        first = await env.wait_req('first')
        await env.accept(first, 'timeout')
        second = await env.wait_req('second')
        await env.accept(second, 'timeout')
        assert first.id != second.id and first.uid != second.uid
        assert {(first.addr, first.vaddr), (second.addr, second.vaddr)} == {
            (20 << 6, 24 << 6), (21 << 6, 25 << 6)}
        await env.hit(second)
        await env.hit(first)
        await env.settle(3)
        assert env.status().empty
        assert [(event.uid, event.kind) for event in env.ledger.events if event.kind == 'hit'] == [
            (second.uid, 'hit'), (first.uid, 'hit')]


async def test_replayed_attempt_and_reset_cancel_reject_stale_handles(sbuffer_env):
    env = sbuffer_env
    env.configure(timeout_cycles=2)
    async with execution(env):
        await env.reset()
        await env.enqueue([Enq(30, 32, 3, 15, 0x33333333)])
        first = await env.wait_req('first')
        await env.accept(first, 'timeout')
        await env.replay(first)
        retry = await env.wait_req('retry', max_cycles=60)
        assert retry.uid == first.uid and retry.attempt == first.attempt + 1
        await env.accept(retry, 'replay_retry')
        with pytest.raises(AssertionError, match='stale or unaccepted'):
            await env.hit(first)
        with pytest.raises(AssertionError, match='stale or unaccepted'):
            await env.hit(replace(retry, uid=retry.uid + 100))
        await env.reset('with_entries')
        with pytest.raises(AssertionError, match='stale or unaccepted'):
            await env.hit(retry)
        await env.no_req_for(4, 'reset removes old work')


async def test_identical_younger_store_cannot_steal_an_inflight_retry_identity(sbuffer_env):
    env = sbuffer_env
    env.configure(timeout_cycles=2)
    request = Enq(40, 44, 0, 15, 0x55555555)
    async with execution(env):
        await env.reset()
        await env.enqueue([request])
        old = await env.wait_req('old identical data')
        await env.accept(old, 'timeout')
        await env.enqueue([request])
        await env.replay(old)
        retry = await env.wait_req('old retry', max_cycles=60)
        assert retry.uid == old.uid and retry.attempt == 2
        await env.accept(retry, 'replay_retry')
        await env.hit(retry)
        fresh = await env.wait_req('younger identical data')
        assert fresh.uid != old.uid
        assert (fresh.addr, fresh.vaddr, fresh.mask, fresh.data) == (
            old.addr, old.vaddr, old.mask, old.data)
        await env.accept(fresh, 'timeout')
        await env.hit(fresh)
        await env.settle(3)
        assert env.status().empty


async def test_new_sameblock_store_during_output_backpressure_gets_its_own_identity(sbuffer_env):
    env = sbuffer_env
    env.configure(timeout_cycles=2)
    async with execution(env):
        await env.reset()
        await env.enqueue([Enq(50, 54, 0, 15, 0x11111111)])
        offered = await env.wait_req('not yet accepted')
        await env.enqueue([Enq(50, 54, 0, 3, 0x2222)])
        await env.settle(3)
        result = await env.forward(0, 54 << 6, 50 << 6)
        assert result.data[:4] == (0x22, 0x22, 0x11, 0x11)
        assert not env.ledger.pending  # a visible offer is not an external fire
        await env.accept(offered, 'timeout')
        await env.hit(offered)
        fresh = await env.wait_req('new input identity')
        assert fresh.uid != offered.uid and fresh.mask == 3
        await env.accept(fresh, 'timeout')
        await env.hit(fresh)
        await env.settle(3)
        assert env.status().empty
