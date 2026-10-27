"""SbufferData UT: every test is driven by the semantic functional points.

See docs/functional-points-sbuffer-data.md. Each DUT transaction is compared
against an independent byte-accurate model; functional coverage is sampled only
after the comparison succeeds.
"""
from __future__ import annotations

import random

import pytest

from sbufferverify.common.runtime import execution
from sbufferverify.sbuffer_data.env import Op
from sbufferverify.sbuffer_data.model import WriteRequest


def payload(seed: int) -> int:
    """Deterministic 128-bit payload with a distinct value in every byte."""
    return int.from_bytes(bytes(((seed * 37 + byte * 11 + 0xA5) & 0xFF) for byte in range(16)), "little")


# SBD-RESET-01, SBD-STABLE-01
async def test_reset_initializes_masks_and_idle_is_stable(sbuffer_data_env):
    env = sbuffer_data_env
    async with execution(env.dut):
        await env.reset("reset_idle")
        await env.idle(3, "after_reset")


# SBD-WRITE-02, SBD-ARRAY-01
async def test_wline_both_ports_all_lines(sbuffer_data_env):
    env = sbuffer_data_env
    async with execution(env.dut):
        await env.reset()
        # Each line's write buffer must see both wline values, and the 16B lane
        # offset must move high->low so its second bit is exercised both ways.
        for line in range(16):
            await env.issue((WriteRequest(1 << line, 0xFFFF, payload(line), 3, True),))
            await env.issue((WriteRequest(1 << line, 0x0001, payload(line + 32), 0, False),))
        for line in range(16):
            req_high = WriteRequest(1 << line, 0xFFFF, payload(line + 64), 3, True)
            req_low = WriteRequest(1 << line, 0x0001, payload(line + 96), 0, False)
            await env.burst([Op((req_high,), ports=(1,)), Op((req_low,), ports=(1,))])


# SBD-WRITE-01, SBD-WRITE-06
async def test_single_byte_each_lane(sbuffer_data_env):
    env = sbuffer_data_env
    async with execution(env.dut):
        await env.reset()
        for byte in range(16):
            req = WriteRequest(
                wvec=1 << 0, mask=1 << byte, data=payload(byte), vword_offset=2
            )
            await env.issue((req,))
        # A mask with no bits set must not change the stored line either.
        await env.issue((WriteRequest(1 << 0, 0x0000, payload(99), 2),))


# SBD-WRITE-02
async def test_wline_broadcasts_payload_to_whole_line(sbuffer_data_env):
    env = sbuffer_data_env
    async with execution(env.dut):
        await env.reset()
        # wline with zero data and a partial mask: mask must be ignored.
        await env.issue((WriteRequest(1 << 4, 0x0001, 0, 0, True),))
        # Module capability only: the current parent issues wline exclusively
        # for cbo.zero with a zero payload, so this non-zero broadcast is not
        # reachable from the parent. It verifies SbufferData's own broadcast
        # logic and is not counted as parent-behaviour evidence.
        await env.issue((WriteRequest(1 << 9, 0x8000, payload(3), 2, True),))


# SBD-WRITE-03
async def test_vword_offset_selects_low_two_bits_only(sbuffer_data_env):
    env = sbuffer_data_env
    async with execution(env.dut):
        await env.reset()
        await env.issue((WriteRequest(1 << 6, 0xFFFF, payload(4), 1),))
        # High page bits change, low lane bits stay: same 16B window.
        await env.issue((WriteRequest(1 << 6, 0x0001, payload(5), (0x3FF << 2) | 1),))
        # Lane 0 selected through high bits with low two bits zero.
        await env.issue((WriteRequest(1 << 6, 0x0100, payload(6), (0x155 << 2) | 0),))
        # Every high offset bit alone still selects lane 0 (alias semantics).
        for bit in range(2, 44):
            await env.issue((WriteRequest(1 << 6, 0x0001, payload(bit), 1 << bit),))
        await env.issue((WriteRequest(1 << 6, 0x0001, payload(7), 0),))


# SBD-WRITE-04, SBD-FLUSH-02
async def test_wvec_multi_line_broadcast(sbuffer_data_env):
    env = sbuffer_data_env
    async with execution(env.dut):
        await env.reset()
        wvec = (1 << 2) | (1 << 7) | (1 << 13)
        await env.issue((WriteRequest(wvec, 0xF0F0, payload(7), 3),))
        await env.issue(flush=wvec)
        # Seven-line bitmap write, then clean all of them in one request.
        many = (1 << 0) | (1 << 3) | (1 << 5) | (1 << 8) | (1 << 11) | (1 << 14) | (1 << 15)
        await env.issue((WriteRequest(many, 0x5555, payload(8), 0),))
        await env.issue(flush=many)


# SBD-WRITE-08, SBD-FLUSH-01, SBD-FLUSH-02
async def test_all_lines_and_lanes_are_independent(sbuffer_data_env):
    env = sbuffer_data_env
    async with execution(env.dut):
        await env.reset()
        for line in range(16):
            for lane in range(4):
                req = WriteRequest(
                    wvec=1 << line, mask=0xFFFF, data=payload(line * 4 + lane), vword_offset=lane
                )
                await env.issue((req,))
        await env.idle(2, "after_write")
        await env.issue(flush=(1 << 16) - 1)
        await env.idle(2, "after_flush")


# SBD-WRITE-07
async def test_dual_port_combinations(sbuffer_data_env):
    env = sbuffer_data_env
    async with execution(env.dut):
        await env.reset()
        # Different lines in one cycle.
        await env.issue(
            (
                WriteRequest(1 << 1, 0xFFFF, payload(11), 0),
                WriteRequest(1 << 2, 0xFFFF, payload(12), 1),
            )
        )
        # Same line, different lanes.
        await env.issue(
            (
                WriteRequest(1 << 3, 0xFFFF, payload(13), 0),
                WriteRequest(1 << 3, 0xFFFF, payload(14), 1),
            )
        )
        # Same line and lane, disjoint bytes.
        await env.issue(
            (
                WriteRequest(1 << 3, 0x00FF, payload(15), 2),
                WriteRequest(1 << 3, 0xFF00, payload(16), 2),
            )
        )
        # Same line, lane and bytes: port 1 wins on the overlapping bytes.
        await env.issue(
            (
                WriteRequest(1 << 3, 0x000F, payload(17), 3),
                WriteRequest(1 << 3, 0x000F, payload(18), 3),
            )
        )


# SBD-WRITE-08, SBD-WRITE-06
async def test_back_to_back_writes_accumulate(sbuffer_data_env):
    env = sbuffer_data_env
    async with execution(env.dut):
        await env.reset()
        # One request per cycle: the four lanes of a line accumulate.
        await env.burst([Op((WriteRequest(1 << 5, 0xFFFF, payload(20 + lane), lane),)) for lane in range(4)])
        # A later partial write only replaces the bytes it selects.
        await env.issue((WriteRequest(1 << 5, 0x000F, payload(30), 1),))
        # Contiguous high half of a lane is a separate mask shape.
        await env.issue((WriteRequest(1 << 5, 0xFF00, payload(31), 2),))
        await env.issue((WriteRequest(1 << 5, 0x0F0F, payload(32), 3),))


# SBD-FLUSH-01, SBD-FLUSH-02, SBD-FLUSH-04
async def test_flush_single_two_many_all(sbuffer_data_env):
    env = sbuffer_data_env
    async with execution(env.dut):
        await env.reset()
        await env.issue(
            (WriteRequest((1 << 8) | (1 << 12), 0xFFFF, payload(33), 0),)
        )
        await env.issue(flush=1 << 8)                    # single line
        await env.issue(flush=(1 << 12) | (1 << 9))      # two lines
        many = (1 << 0) | (1 << 3) | (1 << 6) | (1 << 10) | (1 << 15)
        await env.issue(flush=many)                      # many lines
        # Invalid flush with a full bitmap changes nothing.
        await env.issue((WriteRequest(1 << 7, 0xFFFF, payload(34), 1),))
        await env.invalid_flush((1 << 16) - 1)


# SBD-FLUSH-03
async def test_flush_and_write_same_cycle(sbuffer_data_env):
    env = sbuffer_data_env
    async with execution(env.dut):
        await env.reset()
        await env.issue((WriteRequest(1 << 8, 0xFFFF, payload(35), 0),))
        # Same line: clean wins for untouched bytes, write keeps its own byte.
        await env.issue((WriteRequest(1 << 8, 0x0020, payload(36), 0),), flush=1 << 8)
        # Other line: flush of line 8 and a write to line 12 are independent.
        await env.issue((WriteRequest(1 << 12, 0xFFFF, payload(37), 1),), flush=1 << 8)
        # Same line again, different lane.
        await env.issue((WriteRequest(1 << 8, 0xFFFF, payload(38), 2),), flush=1 << 8)


# SBD-WRITE-05, SBD-FLUSH-04, SBD-STABLE-01
async def test_invalid_requests_do_nothing(sbuffer_data_env):
    env = sbuffer_data_env
    async with execution(env.dut):
        await env.reset()
        await env.issue((WriteRequest(1 << 10, 0xFFFF, payload(40), 0),))
        # Payload looks like a full-line broadcast but valid is low.
        await env.invalid_write(WriteRequest((1 << 16) - 1, 0xFFFF, payload(41), 0, True))
        await env.idle(2, "after_write")
        # An invalid flush must also leave the masks untouched.
        await env.invalid_flush((1 << 16) - 1)


# SBD-RESET-01
async def test_reset_contexts(sbuffer_data_env):
    env = sbuffer_data_env
    async with execution(env.dut):
        await env.reset("reset_idle")
        await env.issue((WriteRequest(1 << 13, 0xFFFF, payload(42), 0),))
        # Reset while a clean request is being captured: masks all clear.
        await env.reset_with_flush(1 << 13)
        await env.issue((WriteRequest(1 << 14, 0xFFFF, payload(43), 1),))
        # Reset one edge after capture: the pending write must not reappear.
        await env.reset_pending_write(WriteRequest(1 << 14, 0xFFFF, payload(44), 2))
        await env.reset("reset_idle")


# SBD-ARRAY-01: every storage cell and both write ports are independently reachable
async def test_exhaustive_cell_and_port_sweep(sbuffer_data_env):
    env = sbuffer_data_env
    async with execution(env.dut):
        await env.reset()
        full = (1 << 128) - 1
        # One single-byte write per (line, lane, byte) on port 0, then on port 1.
        # The same byte position receives complementary data so every data bit
        # toggles in both directions. Each line burst ends with a full-array check.
        for line in range(16):
            ops = []
            targets = []
            for lane in range(4):
                for byte in range(16):
                    base = payload(line * 64 + lane * 16 + byte)
                    ops.append(
                        Op(
                            (WriteRequest(1 << line, 1 << byte, base, lane | ((byte & 3) << 2)),),
                            ports=(0,),
                        )
                    )
                    targets.append((line,))
                    ops.append(
                        Op(
                            (WriteRequest(1 << line, 1 << byte, base ^ full, lane | ((line & 1) << 4)),),
                            ports=(1,),
                        )
                    )
                    targets.append((line,))
            await env.burst(ops, lines_per_op=targets)
        # Saturate data-bit toggles: every byte cell sees all-zero, all-one and
        # all-zero again, so each data output bit toggles in both directions.
        full = (1 << 128) - 1
        for line in range(16):
            ops = []
            targets = []
            for lane in range(4):
                for value in (0, full, 0):
                    ops.append(Op((WriteRequest(1 << line, 0xFFFF, value, lane),)))
                    targets.append((line,))
            await env.burst(ops, lines_per_op=targets)
        # Clean every line once so each per-line mask-clear path is exercised.
        await env.burst([Op(flush=1 << line) for line in range(16)], lines_per_op=[(line,) for line in range(16)])


# SBD-WRITE-01..08, SBD-FLUSH-01..04: legal random mix
async def test_random_legal_traffic(sbuffer_data_env):
    env = sbuffer_data_env
    rng = random.Random(0x5B0F_2026)
    async with execution(env.dut):
        await env.reset()
        for _ in range(120):
            roll = rng.random()
            if roll < 0.55:
                ports = rng.choice((1, 1, 2))
                writes = []
                for _port in range(ports):
                    line = rng.randrange(16)
                    lane = rng.randrange(4)
                    shape = rng.randrange(4)
                    if shape == 0:
                        mask = 1 << rng.randrange(16)
                    elif shape == 1:
                        low = rng.randrange(16)
                        high = rng.randrange(low, 16)
                        mask = ((1 << (high - low + 1)) - 1) << low
                    elif shape == 2:
                        mask = rng.randrange(1, 0x10000)
                    else:
                        mask = 0xFFFF
                    offset = (rng.getrandbits(44) & ~0x3) | lane
                    writes.append(WriteRequest(1 << line, mask, rng.getrandbits(128), offset, False))
                await env.issue(tuple(writes))
            elif roll < 0.8:
                count = rng.choice((1, 2, 3, 5, 16))
                lines = rng.sample(range(16), count)
                wvec = sum(1 << line for line in lines)
                if rng.random() < 0.4:
                    outside = [line for line in range(16) if line not in lines]
                    line = rng.choice(lines) if (not outside or rng.random() < 0.6) else rng.choice(outside)
                    req = WriteRequest(
                        1 << line,
                        rng.choice((0x00FF, 0xF0F0, 0xFFFF)),
                        rng.getrandbits(128),
                        rng.randrange(4),
                        rng.random() < 0.2,
                    )
                    await env.issue((req,), flush=wvec)
                else:
                    await env.issue(flush=wvec)
            else:
                line = rng.randrange(16)
                lane = rng.randrange(4)
                await env.issue(
                    (WriteRequest(1 << line, 0xFF00, rng.getrandbits(128), lane, True),)
                )
