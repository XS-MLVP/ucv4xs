"""PTWRepeaterNB UT: single outstanding request, response hold and flush."""
from __future__ import annotations

from mmuverify.common.runtime import execution


async def _respond(env, tag: int, ppn: int, s2: int = 0) -> None:
    env.ptw_resp_valid.Set(1)
    env.ptw_resp_tag.Set(tag)
    env.ptw_resp_ppn.Set(ppn)
    env.ptw_resp_s2.Set(s2)
    await env.edge()
    env.ptw_resp_valid.Set(0)


# PTWREP-01
async def test_request_to_ptw_and_response_hold(repeater_env):
    env = repeater_env
    async with execution(env.dut):
        await env.reset()
        assert env.read(env.req_ready) == 1
        env.req_valid.Set(1)
        env.req_vpn.Set(0x12345)
        env.req_s2.Set(2)
        await env.edge()
        env.req_valid.Set(0)
        # Request accepted, not yet emitted until the next cycle.
        assert env.read(env.ptw_valid) == 1
        assert env.read(env.ptw_vpn) == 0x12345
        assert env.read(env.ptw_s2) == 2
        assert env.read(env.req_ready) == 0
        if env.coverage is not None:
            env.coverage.sample("accept", 2)
        # PTW handshake clears the request phase.
        env.ptw_ready.Set(1)
        await env.edge()
        env.ptw_ready.Set(0)
        assert env.read(env.ptw_valid) == 0
        assert env.read(env.ptw_resp_ready) == 1
        if env.coverage is not None:
            env.coverage.sample("issue", 2)
        # Response is latched and held while the consumer is not ready.
        await _respond(env, 0x0ABCD, 0x34567, s2=2)
        assert env.read(env.resp_valid) == 1
        assert env.read(env.resp_tag) == 0x0ABCD
        assert env.read(env.resp_ppn) == 0x34567
        assert env.read(env.resp_s2) == 2
        assert env.read(env.ptw_resp_ready) == 0
        for _ in range(3):
            await env.edge()
        assert env.read(env.resp_valid) == 1
        if env.coverage is not None:
            env.coverage.sample("response", 2, "held")
        env.resp_ready.Set(1)
        await env.edge()
        env.resp_ready.Set(0)
        assert env.read(env.resp_valid) == 0
        assert env.read(env.req_ready) == 1
        if env.coverage is not None:
            env.coverage.sample("response", 2, "released")


# PTWREP-02
async def test_second_request_is_blocked_until_first_completes(repeater_env):
    env = repeater_env
    async with execution(env.dut):
        await env.reset()
        env.req_valid.Set(1)
        env.req_vpn.Set(0x111)
        await env.edge()
        env.req_valid.Set(0)
        await env.edge()
        assert env.read(env.ptw_valid) == 1
        assert env.read(env.req_ready) == 0
        # A second request must not be accepted while the first is pending.
        env.req_valid.Set(1)
        env.req_vpn.Set(0x222)
        await env.edge()
        env.req_valid.Set(0)
        assert env.read(env.ptw_vpn) == 0x111
        assert env.read(env.ptw_valid) == 1


# PTWREP-03
async def test_flush_cancels_request_and_response_phases(repeater_env):
    env = repeater_env
    async with execution(env.dut):
        await env.reset()
        # Flush while the request is waiting for PTW.
        env.req_valid.Set(1)
        env.req_vpn.Set(0x333)
        await env.edge()
        env.req_valid.Set(0)
        await env.edge()
        assert env.read(env.ptw_valid) == 1
        env.sfence.Set(1)
        await env.edge()
        env.sfence.Set(0)
        await env.edge()
        await env.edge()
        assert env.read(env.ptw_valid) == 0
        assert env.read(env.req_ready) == 1
        if env.coverage is not None:
            env.coverage.sample("flush", 0)
        # Flush while a response is held.
        env.req_valid.Set(1)
        env.req_vpn.Set(0x444)
        await env.edge()
        env.req_valid.Set(0)
        await env.edge()
        env.ptw_ready.Set(1)
        await env.edge()
        env.ptw_ready.Set(0)
        await _respond(env, 0x55, 0x66)
        assert env.read(env.resp_valid) == 1
        env.sfence.Set(1)
        await env.edge()
        env.sfence.Set(0)
        await env.edge()
        await env.edge()
        assert env.read(env.resp_valid) == 0


# PTWREP-04: all translation-stage encodings pass through the request and
# response paths.
async def test_stage_encodings_pass_through(repeater_env):
    env = repeater_env
    async with execution(env.dut):
        await env.reset()
        for stage in (0, 1, 2, 3):
            env.req_valid.Set(1)
            env.req_vpn.Set(0x700 + stage)
            env.req_s2.Set(stage)
            await env.edge()
            env.req_valid.Set(0)
            await env.edge()
            assert env.read(env.ptw_s2) == stage
            assert env.read(env.ptw_vpn) == 0x700 + stage
            env.ptw_ready.Set(1)
            await env.edge()
            env.ptw_ready.Set(0)
            await _respond(env, 0x900 + stage, 0xA00 + stage, s2=stage)
            assert env.read(env.resp_s2) == stage
            if env.coverage is not None:
                env.coverage.sample("response", stage)
            env.resp_ready.Set(1)
            await env.edge()
            env.resp_ready.Set(0)


# PTWREP-05: all-ones and all-zeros payloads pass through unchanged.
async def test_payload_extremes(repeater_env):
    env = repeater_env
    async with execution(env.dut):
        await env.reset()
        for tag, ppn, s2 in (((1 << 35) - 1, 0x1FFFFFFFFF, 3), (0, 0, 0)):
            env.req_valid.Set(1)
            env.req_vpn.Set(0x810 + s2)
            env.req_s2.Set(s2)
            await env.edge()
            env.req_valid.Set(0)
            await env.edge()
            env.ptw_ready.Set(1)
            await env.edge()
            env.ptw_ready.Set(0)
            await _respond(env, tag, ppn, s2=s2)
            assert env.read(env.resp_tag) == tag
            assert env.read(env.resp_ppn) == ppn
            env.resp_ready.Set(1)
            await env.edge()
            env.resp_ready.Set(0)


# PTWREP-06: every flush source individually cancels the outstanding request.
async def test_flush_sources(repeater_env):
    env = repeater_env
    async with execution(env.dut):
        await env.reset()
        for signal in env.csr_changed:
            env.req_valid.Set(1)
            env.req_vpn.Set(0x910)
            await env.edge()
            env.req_valid.Set(0)
            await env.edge()
            assert env.read(env.ptw_valid) == 1
            signal.Set(1)
            await env.edge()
            signal.Set(0)
            await env.edge()
            await env.edge()
            assert env.read(env.ptw_valid) == 0


def _sweep_inputs(dut, value: int, exclude=("clock", "reset")) -> None:
    for name, signal in vars(dut).items():
        if name in exclude:
            continue
        if not hasattr(signal, "IsInIO"):
            continue
        if signal.IsInIO() and not signal.IsOutIO():
            width = max(1, int(getattr(signal, "mWidth", 1)))
            signal.Set(((1 << width) - 1) if value else 0)


# PTWREP-07: all interface payload bits toggle in both directions through
# valid transactions. This is interface stress, not a functional bin.
async def test_all_payload_bits_toggle(repeater_env):
    env = repeater_env
    async with execution(env.dut):
        await env.reset()
        for endpoint in (1, 0):
            _sweep_inputs(env.dut, endpoint)
            env.req_valid.Set(1)
            env.req_vpn.Set((1 << 38) - 1 if endpoint else 0)
            env.req_s2.Set(3 if endpoint else 0)
            env.ptw_ready.Set(0)
            env.resp_ready.Set(1)
            await env.edge()
            env.req_valid.Set(0)
            await env.edge()
            # Complete the request phase.
            env.ptw_ready.Set(1)
            await env.edge()
            env.ptw_ready.Set(0)
            # Latch a full response payload and release it.
            _sweep_inputs(env.dut, endpoint)
            env.ptw_resp_valid.Set(1)
            env.ptw_resp_s2.Set(3 if endpoint else 0)
            env.ptw_resp_tag.Set((1 << 35) - 1 if endpoint else 0)
            env.ptw_resp_ppn.Set((1 << 41) - 1 if endpoint else 0)
            env.resp_ready.Set(1)
            await env.edge()
            env.ptw_resp_valid.Set(0)
            await env.edge()
            assert env.read(env.ptw_valid) == 0
            assert env.read(env.resp_valid) == 0
        # Leave the flush sources at zero.
        _sweep_inputs(env.dut, 0)
        await env.edge()
