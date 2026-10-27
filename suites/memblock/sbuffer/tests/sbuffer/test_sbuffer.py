"""Sbuffer top-level UT driven by the semantic functional points.

See docs/functional-points-sbuffer.md. The reference model tracks physical-tag
lines and merged bytes; requests are matched to a unique live line by payload,
so PLRU slot choice is not over-specified.
"""
from __future__ import annotations

from sbufferverify.common.runtime import execution
from sbufferverify.sbuffer.model import Enq


def data(byte_value: int) -> int:
    return int.from_bytes(bytes([(byte_value + index) & 0xFF for index in range(16)]), "little")


# SBT-RESET-01
async def test_reset_and_idle(sbuffer_env):
    env = sbuffer_env
    async with execution(env.dut):
        await env.reset("idle")
        await env.settle(3)
        assert env.read(env.sbempty) == 1
        assert env.read(env.sbfull) == 0
        assert env.read(env.req_valid) == 0


# SBT-ENQ-01, SBT-FWD-01
async def test_merge_and_forward(sbuffer_env):
    env = sbuffer_env
    env.timeout.Set(0x3FFFFF)
    async with execution(env.dut):
        await env.reset()
        line = Enq(ptag=5, vtag=9, lane=1, mask=0x000F, data=data(0x10))
        await env.enqueue([line])
        await env.settle(3)
        await env.enqueue([Enq(ptag=5, vtag=9, lane=1, mask=0x0F00, data=data(0x20))])
        await env.settle(3)

        vaddr = (9 << 6) | 0x10
        paddr = (5 << 6) | 0x10
        f0 = await env.forward(0, vaddr, paddr)
        assert f0["mask"] == 0x0F0F
        assert f0["invalid"] == 0
        f1 = await env.forward(1, vaddr, paddr)
        assert f1["mask"] == 0x0F0F
        # Different vtag: no forward data but virtual/physical mismatch warning.
        f2 = await env.forward(2, (10 << 6) | 0x10, paddr)
        assert f2["mask"] == 0 and f2["invalid"] == 1
        # Same vtag, different ptag: data returned but mismatch warning.
        await env.forward(0, vaddr, (6 << 6) | 0x10)
        # Kill suppresses the warning.
        await env.forward(1, vaddr, paddr, kill=True)
        # No match in an empty lane of the same line.
        empty = await env.forward(2, (11 << 6) | 0x20, (6 << 6) | 0x20)
        assert empty["mask"] == 0

        # Query the other three 16B lanes (no data, but lane decode must be right).
        for lane in range(4):
            await env.forward(lane % 3, (12 << 6) | (lane << 4), (7 << 6) | (lane << 4))


# SBT-ENQ-01
async def test_dual_port_enqueue(sbuffer_env):
    env = sbuffer_env
    env.timeout.Set(0x3FFFFF)
    async with execution(env.dut):
        await env.reset()
        # Same physical line, two lanes in one cycle: one line, merged mask.
        await env.enqueue(
            [
                Enq(ptag=20, vtag=30, lane=0, mask=0x00FF, data=data(0x30)),
                Enq(ptag=20, vtag=30, lane=0, mask=0xFF00, data=data(0x40)),
            ],
            expect_ready=[1, 1],
        )
        await env.settle(3)
        merged = await env.forward(0, (30 << 6) | 0x00, (20 << 6) | 0x00)
        assert merged["mask"] == 0xFFFF

        # Same byte from both ports: port 1 wins.
        await env.enqueue(
            [
                Enq(ptag=21, vtag=31, lane=1, mask=0x000F, data=data(0x50)),
                Enq(ptag=21, vtag=31, lane=1, mask=0x000F, data=data(0x60)),
            ],
            expect_ready=[1, 1],
        )
        await env.settle(3)
        conflict = await env.forward(1, (31 << 6) | 0x10, (21 << 6) | 0x10)
        expected = data(0x60)
        for byte in range(4):
            assert conflict["data"][byte] == (expected >> (8 * byte)) & 0xFF

        # Different physical lines in one cycle.
        await env.enqueue(
            [
                Enq(ptag=22, vtag=32, lane=2, mask=0xFFFF, data=data(0x70)),
                Enq(ptag=23, vtag=33, lane=3, mask=0xFFFF, data=data(0x80)),
            ],
            expect_ready=[1, 1],
        )
        await env.settle(3)
        await env.forward(0, (32 << 6) | 0x20, (22 << 6) | 0x20)
        await env.forward(1, (33 << 6) | 0x30, (23 << 6) | 0x30)


# SBT-DRAIN-01
async def test_timeout_writeout_all_lanes(sbuffer_env):
    env = sbuffer_env
    async with execution(env.dut):
        await env.reset()
        env.timeout.Set(3)
        for lane in range(4):
            await env.enqueue([Enq(ptag=40 + lane, vtag=50 + lane, lane=lane, mask=0xFFFF, data=data(0x90 + lane))])
        await env.settle(3)
        drained = 0
        while env.model.lines:
            snap = await env.wait_req("timeout")
            await env.accept(snap, "timeout")
            await env.hit(snap)
            drained += 1
            if drained > 8:
                raise AssertionError("timeout writeout did not finish")
        await env.settle(3)
        assert env.read(env.sbempty) == 1


# SBT-DRAIN-01
async def test_replay_resends_same_line(sbuffer_env):
    env = sbuffer_env
    async with execution(env.dut):
        await env.reset()
        env.timeout.Set(2)
        await env.enqueue([Enq(ptag=60, vtag=70, lane=0, mask=0x00FF, data=data(0xA0))])
        first = await env.wait_req("timeout")
        await env.accept(first, "timeout")
        # Only the inflight copy still matches this virtual line: forwarding
        # must return its data without an active-line override.
        inflight_hit = await env.forward(0, first.vaddr, first.addr)
        assert inflight_hit["mask"] != 0
        await env.replay(first)
        retry = await env.wait_req("replay", max_cycles=40, allow_inflight=True)
        assert retry.id == first.id, "replay must re-send the same line slot"
        assert (retry.addr, retry.vaddr, retry.mask, retry.data) == (
            first.addr, first.vaddr, first.mask, first.data
        )
        if env.coverage is not None:
            env.coverage.sample_replay("retry_req")
        await env.accept(retry, "replay_retry")
        await env.hit(retry)
        if env.coverage is not None:
            env.coverage.sample_replay("final_hit")
        await env.settle(3)
        assert env.read(env.sbempty) == 1


# SBT-FLUSH-01/02: fence-level empty requires the whole store path (incl. SQ)
async def test_fence_flush_empty_requires_sqempty(sbuffer_env):
    env = sbuffer_env
    env.timeout.Set(0x3FFFFF)
    async with execution(env.dut):
        await env.reset()
        for index in range(3):
            await env.enqueue([Enq(ptag=80 + index, vtag=90 + index, lane=index, mask=0xFFFF, data=data(0xB0 + index))])
        await env.settle(2)
        drained = await env.flush_and_finish(cmo=False, sqempty=1)
        assert len(drained) == 3

        # A fence must not report empty while the store queue still holds stores.
        for index in range(2):
            await env.enqueue([Enq(ptag=84 + index, vtag=94 + index, lane=index, mask=0xFFFF, data=data(0xC0 + index))])
        await env.settle(2)
        await env.start_flush(cmo=False, sqempty=0)
        await env.drain_requests("drain_flush")
        await env.settle(4)
        # Sbuffer itself is drained ...
        assert env.read(env.sbempty) == 1, "sbempty must assert after all sbuffer lines are drained"
        # ... but the fence-level signal must wait until the store queue is empty.
        assert env.read(env.flush_empty) == 0, "flush.empty must wait for sqempty"
        if env.coverage is not None:
            env.coverage.sample_flush("normal", "sqempty_hold")
        env.sqempty.Set(1)
        await env.settle(2)
        assert env.read(env.flush_empty) == 1
        env.flush_valid.Set(0)
        await env.edge()


# SBT-FLUSH-01: CMO completion is Sbuffer-level empty, not fence-level empty
async def test_cmo_completion_uses_sbempty_without_sqempty(sbuffer_env):
    env = sbuffer_env
    env.timeout.Set(0x3FFFFF)
    async with execution(env.dut):
        await env.reset()
        for index in range(2):
            await env.enqueue([Enq(ptag=100 + index, vtag=110 + index, lane=index, mask=0xFFFF, data=data(0xD0 + index))])
        await env.settle(2)
        await env.start_flush(cmo=True, sqempty=0, mshr=0)
        await env.drain_requests("drain_flush")
        await env.settle(4)
        # A store miss is still outstanding in the MSHR: the CMO must wait.
        assert env.read(env.sbempty) == 0, "CMO must wait for store misses in MSHR"
        env.mshr_empty.Set(1)
        await env.settle(2)
        # This is the condition the CBO FSM consumes (sbempty). It must assert
        # even though the CBO's own store-queue entry keeps sqempty low: a CBO
        # executes at the SQ head and dequeues only at writeback, so requiring
        # sqempty here would deadlock.
        assert env.read(env.sbempty) == 1, "CMO needs sbuffer-level empty, not SQ empty"
        # flush.empty is the fence-level signal and intentionally still waits.
        assert env.read(env.flush_empty) == 0, "flush.empty is gated by sqempty"
        if env.coverage is not None:
            env.coverage.sample_flush("cmo", "cmo_ignores_sq")
        env.sqempty.Set(1)
        await env.settle(2)
        assert env.read(env.flush_empty) == 1
        env.flush_valid.Set(0)
        await env.edge()


# SBT-DRAIN-03
async def test_uarch_drain_on_vtag_mismatch_merge(sbuffer_env):
    env = sbuffer_env
    env.timeout.Set(0x3FFFFF)
    async with execution(env.dut):
        await env.reset()
        await env.enqueue([Enq(ptag=120, vtag=130, lane=0, mask=0x000F, data=data(0xE0))])
        await env.settle(2)
        await env.enqueue([Enq(ptag=120, vtag=131, lane=0, mask=0x00F0, data=data(0xF0))])
        # do_uarch_drain is registered 1-2 cycles after the merge; wait until
        # the public ready actually drops before asserting the block.
        for _ in range(6):
            await env.edge()
            if env.read(env.in_ready[0]) == 0:
                break
        assert env.read(env.in_ready[0]) == 0, "uarch drain must block new enqueues"
        await env.enqueue(
            [Enq(ptag=121, vtag=132, lane=0, mask=0xFFFF, data=data(0x11))],
            expect_ready=[0],
        )
        await env.drain_uarch()
        await env.settle(3)
        assert env.read(env.sbempty) == 1
        # After the drain the buffer accepts stores again.
        await env.enqueue([Enq(ptag=122, vtag=133, lane=0, mask=0xFFFF, data=data(0x12))], expect_ready=[1])


# SBT-ENQ-02, SBT-REQ-01
async def test_capacity_full_and_resume(sbuffer_env):
    env = sbuffer_env
    env.force_write.Set(1)
    env.timeout.Set(0x3FFFFF)
    async with execution(env.dut):
        await env.reset()
        # Hold DCache ready low: one line becomes inflight, the rest stay
        # active, so the valid count can actually reach 16.
        env.req_ready.Set(0)
        for index in range(16):
            await env.enqueue([Enq(ptag=140 + index, vtag=160 + index, lane=index % 4, mask=0xFFFF, data=data(0x20 + index))])
        await env.settle(4)
        assert env.read(env.sbfull) == 1, "16 valid lines must assert sbFull"
        if env.coverage is not None:
            env.coverage.sample_capacity("full")
        await env.enqueue(
            [Enq(ptag=200, vtag=220, lane=0, mask=0xFFFF, data=data(0x33))],
            expect_ready=[0],
        )
        stalled = await env.wait_req("capacity_replace")
        await env.accept(stalled, "capacity_replace")
        await env.hit(stalled)
        await env.settle(3)
        assert env.read(env.sbfull) == 0
        await env.enqueue(
            [Enq(ptag=201, vtag=221, lane=1, mask=0xFFFF, data=data(0x34))],
            expect_ready=[1],
        )
        if env.coverage is not None:
            env.coverage.sample_capacity("resumed")


# SBT-REQ-01, SBT-FWD-01
async def test_sameblock_serialization(sbuffer_env):
    env = sbuffer_env
    async with execution(env.dut):
        await env.reset()
        env.timeout.Set(3)
        await env.enqueue([Enq(ptag=240, vtag=250, lane=0, mask=0x000F, data=data(0x40))])
        first = await env.wait_req("timeout")
        await env.accept(first, "timeout")
        # A second store to the same physical line allocates a new line because
        # the first one is inflight; it must not be written out yet.
        await env.enqueue([Enq(ptag=240, vtag=250, lane=1, mask=0x00F0, data=data(0x50))])
        await env.settle(3)
        # Forward sees both the active new line and the inflight old line.
        fwd = await env.forward(0, (250 << 6) | 0x10, (240 << 6) | 0x10)
        assert fwd["mask"] == 0x00F0
        await env.no_req_for(8, "sameblock")
        if env.coverage is not None:
            env.coverage.sample_sameblock("request_blocked")
        await env.hit(first)
        await env.settle(3)
        second = await env.wait_req("sameblock release")
        await env.accept(second, "timeout")
        await env.hit(second)
        await env.settle(3)
        assert env.read(env.sbempty) == 1
        if env.coverage is not None:
            env.coverage.sample_sameblock("released")


# SBT-RESET-01
async def test_reset_with_entries(sbuffer_env):
    env = sbuffer_env
    env.timeout.Set(0x3FFFFF)
    async with execution(env.dut):
        await env.reset("idle")
        for index in range(3):
            await env.enqueue([Enq(ptag=180 + index, vtag=190 + index, lane=index, mask=0xFFFF, data=data(0x60 + index))])
        await env.settle(2)
        await env.reset("with_entries")
        await env.settle(3)
        assert env.read(env.sbempty) == 1
        assert env.read(env.req_valid) == 0


# SBT-ENQ-01, SBT-WRITE-01: both ports into the same fresh slot, all 16 slots
async def test_port1_same_tag_fills_all_slots(sbuffer_env):
    env = sbuffer_env
    env.timeout.Set(0x3FFFFF)
    async with execution(env.dut):
        await env.reset()
        # For each slot, create the line with port 0 + port 1 on the same fresh
        # tag, then merge all four lanes. Masks alternate which port owns the
        # low/high byte half so both ports' per-slot write buffers are used.
        for line in range(16):
            for lane in range(4):
                low, high = (0x00FF, 0xFF00) if lane % 2 == 0 else (0xFF00, 0x00FF)
                first = Enq(
                    ptag=0x180 + line, vtag=0x1A0 + line, lane=lane,
                    mask=low, data=data(0x10 + line * 4 + lane),
                )
                second = Enq(
                    ptag=first.ptag, vtag=first.vtag, lane=lane,
                    mask=high, data=data(0x80 + line * 4 + lane),
                )
                await env.enqueue([first, second], expect_ready=[1, 1])
        await env.settle(3)
        for line in range(16):
            for lane in range(4):
                result = await env.forward(
                    lane % 3,
                    ((0x1A0 + line) << 6) | (lane << 4),
                    ((0x180 + line) << 6) | (lane << 4),
                )
                assert result["mask"] == 0xFFFF, f"line {line} lane {lane} mask {result['mask']:#06x}"
        await env.flush_and_finish(cmo=False, sqempty=1)


# SBT-WRITE-02: replay every slot id
async def test_replay_each_line_slot(sbuffer_env):
    env = sbuffer_env
    env.force_write.Set(1)
    async with execution(env.dut):
        await env.reset()
        env.timeout.Set(2)
        for line in range(16):
            await env.enqueue(
                [Enq(ptag=0x1C0 + line, vtag=0x1E0 + line, lane=line % 4, mask=0xFFFF, data=data(0x30 + line))]
            )
        await env.settle(3)
        replayed = {}
        pending_retry = None
        for _ in range(160):
            if len(replayed) == 16:
                break
            snap = await env.wait_req("replay sweep", max_cycles=60, allow_inflight=True)
            if pending_retry is not None and snap.id == pending_retry.id:
                # Retry of the replayed line: accept and release it.
                await env.accept(snap, "replay_retry")
                await env.hit(snap)
                if env.coverage is not None:
                    env.coverage.sample_replay("final_hit")
                pending_retry = None
                continue
            if snap.line.inflight:
                # An unrelated line is already inflight (e.g. a previously
                # accepted retry); serve it so the output is not blocked.
                await env.accept(snap, "replay_retry")
                await env.hit(snap)
                continue
            await env.accept(snap, "timeout")
            await env.replay(snap)
            replayed[snap.id] = replayed.get(snap.id, 0) + 1
            pending_retry = snap
        assert len(replayed) == 16, f"only replayed slots {sorted(replayed)}"
        # Finish the last replayed line's retry before flushing.
        for _ in range(40):
            if pending_retry is None:
                break
            snap = await env.wait_req("final retry", max_cycles=60, allow_inflight=True)
            await env.accept(snap, "replay_retry")
            await env.hit(snap)
            if snap.id == pending_retry.id:
                pending_retry = None
        assert pending_retry is None
        env.flush_valid.Set(1)
        await env.drain_requests("drain_flush")
        await env.settle(3)
        env.flush_valid.Set(0)
        await env.edge()


# SBT-WRITE-01: cbo.zero shape (wline with zero payload, mask ignored)
async def test_wline_zero_all_lines(sbuffer_env):
    env = sbuffer_env
    env.timeout.Set(0x3FFFFF)
    async with execution(env.dut):
        await env.reset()
        # Fill all 16 slots so every slot's wline path is exercised. DCache
        # ready is low, so at most one line becomes inflight and the rest stay
        # available for the forward checks. The parent generates wline only for
        # cbo.zero and always with a zero payload: NewStoreQueue sets
        # wline := isCbo && isCboZero, and cbo.zero forces store data to zero.
        # A non-zero wline payload is outside the reachable request domain.
        for line in range(16):
            req = Enq(
                ptag=0x200 + line, vtag=0x220 + line, lane=line % 4,
                mask=0x0001, data=0, wline=True,
            )
            await env.enqueue([req], expect_ready=[1])
        await env.settle(3)
        for line in range(16):
            for lane in range(4):
                result = await env.forward(
                    lane % 3,
                    ((0x220 + line) << 6) | (lane << 4),
                    ((0x200 + line) << 6) | (lane << 4),
                )
                assert result["mask"] == 0xFFFF, f"wline {line} lane {lane} mask {result['mask']:#06x}"
                assert all(byte == 0 for byte in result["data"]), f"wline {line} lane {lane} is not zero"
        # A full buffer may already start capacity replacement; the CBO flush
        # then drains whatever remains. Either way the stored lines are zero.
        await env.flush_and_finish(cmo=True, sqempty=1)


# SBT-FWD-01: per-line/lane merge and three-port forwarding with byte checks
async def test_each_lane_merge_and_forward(sbuffer_env):
    env = sbuffer_env
    env.timeout.Set(0x3FFFFF)
    async with execution(env.dut):
        await env.reset()
        for line in range(8):
            await env.enqueue(
                [Enq(ptag=0x240 + line, vtag=0x260 + line, lane=0, mask=0x000F, data=data(line))]
            )
        await env.settle(2)
        for line in range(8):
            for lane in range(4):
                # Port 0 writes lane, port 1 writes the next lane of the same
                # line so both ports' per-lane buffers are used.
                first = Enq(ptag=0x240 + line, vtag=0x260 + line, lane=lane, mask=0xFFFF, data=data(line * 4 + lane))
                second = Enq(ptag=0x240 + line, vtag=0x260 + line, lane=(lane + 1) % 4, mask=0xFFFF, data=data(line * 4 + lane + 0x40))
                await env.enqueue([first, second], expect_ready=[1, 1])
        await env.settle(2)
        for line in range(8):
            for lane in range(4):
                for load in range(3):
                    result = await env.forward(
                        load,
                        ((0x260 + line) << 6) | (lane << 4),
                        ((0x240 + line) << 6) | (lane << 4),
                    )
                    assert result["mask"] == 0xFFFF
        env.flush_valid.Set(1)
        await env.drain_requests("drain_flush")
        await env.settle(3)
        env.flush_valid.Set(0)
        await env.edge()



# SBT-WRITE-01: data-bit toggle saturation for the first eight slots
async def test_data_bit_saturation(sbuffer_env):
    env = sbuffer_env
    env.timeout.Set(0x3FFFFF)
    zero = 0
    ones = (1 << 128) - 1
    async with execution(env.dut):
        await env.reset()
        for line in range(8):
            await env.enqueue([Enq(ptag=0x300 + line, vtag=0x320 + line, lane=0, mask=0x0001, data=zero)])
        await env.settle(2)
        for line in range(8):
            for lane in range(4):
                for value in (zero, ones):
                    await env.enqueue(
                        [Enq(ptag=0x300 + line, vtag=0x320 + line, lane=lane, mask=0xFFFF, data=value)]
                    )
        # Write zeros again so every data output bit toggles 1->0.
        for line in range(8):
            for lane in range(4):
                await env.enqueue(
                    [Enq(ptag=0x300 + line, vtag=0x320 + line, lane=lane, mask=0xFFFF, data=zero)]
                )
        await env.flush_and_finish(cmo=False, sqempty=1)
