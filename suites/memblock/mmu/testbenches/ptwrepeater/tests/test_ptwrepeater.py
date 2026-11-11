"""PTWRepeaterNB UT: single outstanding request, response hold and flush."""
from __future__ import annotations


from suites.memblock.mmu.testbenches.shared.env.execution import execution


async def _respond(env, tag: int, ppn: int, s2: int = 0) -> None:
    await env.ptw_respond(tag, ppn, s2)


# PTWREP-01
async def test_request_to_ptw_and_response_hold(repeater_env):
    env = repeater_env
    async with execution(env):
        await env.reset()
        assert env.request_ready() == 1
        await env.send_request(0x12345, 2)
        # Request accepted, not yet emitted until the next cycle.
        assert env.ptw_request_valid() == 1
        assert env.ptw_request()[0] == 0x12345
        assert env.ptw_request()[1] == 2
        assert env.request_ready() == 0
        if env.coverage is not None:
            env.coverage.sample("accept", 2)
        # PTW handshake clears the request phase.
        await env.accept_ptw()
        assert env.ptw_request_valid() == 0
        assert env.response_ready() == 1
        if env.coverage is not None:
            env.coverage.sample("issue", 2)
        # Response is latched and held while the consumer is not ready.
        await _respond(env, 0x0ABCD, 0x34567, s2=2)
        assert env.response_valid() == 1
        assert env.response_snapshot()["tag"] == 0x0ABCD
        assert env.response_snapshot()["ppn"] == 0x34567
        assert env.response_snapshot()["s2xlate"] == 2
        assert env.response_ready() == 0
        for _ in range(3):
            await env.edge()
        assert env.response_valid() == 1
        if env.coverage is not None:
            env.coverage.sample("response", 2, "held")
        await env.accept_response()
        assert env.response_valid() == 0
        assert env.request_ready() == 1
        if env.coverage is not None:
            env.coverage.sample("response", 2, "released")


# PTWREP-02
async def test_second_request_is_blocked_until_first_completes(repeater_env):
    env = repeater_env
    async with execution(env):
        await env.reset()
        await env.send_request(0x111)
        await env.edge()
        assert env.ptw_request_valid() == 1
        assert env.request_ready() == 0
        # A second request must not be accepted while the first is pending.
        await env.offer_second_request(0x222)
        assert env.ptw_request()[0] == 0x111
        assert env.ptw_request_valid() == 1


# PTWREP-03
async def test_flush_cancels_request_and_response_phases(repeater_env):
    env = repeater_env
    async with execution(env):
        await env.reset()
        # Flush while the request is waiting for PTW.
        await env.send_request(0x333)
        await env.edge()
        assert env.ptw_request_valid() == 1
        await env.pulse_sfence(hold=1, settle=2)
        assert env.ptw_request_valid() == 0
        assert env.request_ready() == 1
        if env.coverage is not None:
            env.coverage.sample("flush", 0)
        # Flush while a response is held.
        await env.send_request(0x444)
        await env.edge()
        await env.accept_ptw()
        await _respond(env, 0x55, 0x66)
        assert env.response_valid() == 1
        await env.pulse_sfence(hold=1, settle=2)
        assert env.response_valid() == 0


# PTWREP-04: all translation-stage encodings pass through the request and
# response paths.
async def test_stage_encodings_pass_through(repeater_env):
    env = repeater_env
    async with execution(env):
        await env.reset()
        for stage in (0, 1, 2, 3):
            await env.send_request(0x700 + stage, stage)
            await env.edge()
            assert env.ptw_request()[1] == stage
            assert env.ptw_request()[0] == 0x700 + stage
            await env.accept_ptw()
            await _respond(env, 0x900 + stage, 0xA00 + stage, s2=stage)
            assert env.response_snapshot()["s2xlate"] == stage
            if env.coverage is not None:
                env.coverage.sample("response", stage)
            await env.accept_response()


# PTWREP-05: all-ones and all-zeros payloads pass through unchanged.
async def test_payload_extremes(repeater_env):
    env = repeater_env
    async with execution(env):
        await env.reset()
        for tag, ppn, s2 in (((1 << 35) - 1, 0x1FFFFFFFFF, 3), (0, 0, 0)):
            await env.send_request(0x810 + s2, s2)
            await env.edge()
            await env.accept_ptw()
            await _respond(env, tag, ppn, s2=s2)
            assert env.response_snapshot()["tag"] == tag
            assert env.response_snapshot()["ppn"] == ppn
            await env.accept_response()


# PTWREP-06: every flush source individually cancels the outstanding request.
async def test_flush_sources(repeater_env):
    env = repeater_env
    async with execution(env):
        await env.reset()
        for index in range(4):
            await env.send_request(0x910)
            await env.edge()
            assert env.ptw_request_valid() == 1
            await env.pulse_csr_change(index)
            assert env.ptw_request_valid() == 0


# PTWREP-07: all interface payload bits toggle in both directions through
# valid transactions. This is interface stress, not a functional bin.
async def test_all_payload_bits_toggle(repeater_env):
    env = repeater_env
    async with execution(env):
        await env.reset()
        for endpoint in (1, 0):
            env.structural_input_sweep(endpoint)
            env.set_ptw_ready(0)
            env.set_resp_ready(1)
            env.begin_request_stream()
            env.stream_request((1 << 38) - 1 if endpoint else 0,
                               3 if endpoint else 0)
            await env.edge()
            await env.end_request_stream()
            # Complete the request phase.
            await env.accept_ptw()
            # Latch a full response payload and release it.
            env.structural_input_sweep(endpoint)
            env.set_resp_ready(1)
            await env.ptw_respond((1 << 35) - 1 if endpoint else 0,
                                  (1 << 41) - 1 if endpoint else 0,
                                  3 if endpoint else 0)
            await env.edge()
            assert env.ptw_request_valid() == 0
            assert env.response_valid() == 0
        # Leave the flush sources at zero.
        env.structural_input_sweep(0)
        await env.edge()
