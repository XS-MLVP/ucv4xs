"""Offline transaction-contract self-checks; no native DUT construction."""
from __future__ import annotations

import pytest

from suites.memblock.mmu.testbenches.shared.tests.transaction_helpers import (
    READY_CASES, Signal, _dut, _install_ready_cycle,
)
from suites.memblock.mmu.testbenches.ptwrepeater.env.ptw import RepeaterEnv

pytestmark = pytest.mark.selftest


async def test_offer_acceptance_is_the_same_cycle_fire():
    """0->1 must not report fire and 1->0 must not report a miss.

    The same node also replays the repeater's own request/handshake phase with
    a real ``RepeaterEnv`` over fake signals, so the helper names used by the
    structural-stress case must be actual class methods that drive the frozen
    per-edge levels.
    """
    for env_type, attrs, signal_name in (
            (RepeaterEnv, ("req_valid", "req_vpn", "req_s2"), "req_valid"),):
        for before, after in READY_CASES:
            env = env_type.__new__(env_type)
            for name in attrs:
                setattr(env, name, Signal())
            env.req_ready = Signal(before)
            env.dut = _dut()
            fires: list[bool] = []
            _install_ready_cycle(env, getattr(env, signal_name), before, after, fires)
            reported = await env.offer_second_request(0x20000)
            assert reported is fires[0], (env_type.__name__, before, after)

    for name in ("set_ptw_ready", "begin_request_stream", "stream_request",
                 "end_request_stream"):
        assert callable(getattr(RepeaterEnv, name, None)), (
            f"RepeaterEnv.{name} must be a real method")

    env = RepeaterEnv.__new__(RepeaterEnv)
    env.req_valid = Signal()
    env.req_vpn = Signal()
    env.req_s2 = Signal()
    env.req_ready = Signal(1)
    env.resp_ready = Signal(0)
    env.ptw_ready = Signal(0)
    env.dut = _dut()
    levels: list[tuple[int, int, int]] = []

    async def edge() -> None:
        levels.append((env.ptw_ready.value, env.resp_ready.value,
                       env.req_valid.value))

    env.edge = edge
    for endpoint in (1, 0):
        env.req_valid.Set(endpoint)
        env.set_ptw_ready(0)
        env.set_resp_ready(1)
        env.begin_request_stream()
        env.stream_request((1 << 38) - 1 if endpoint else 0,
                           3 if endpoint else 0)
        await env.edge()
        await env.end_request_stream()
        await env.accept_ptw()
    # Frozen trace rows for each endpoint: request, release, PTW accept.
    assert levels == [(0, 1, 1), (0, 1, 0), (1, 1, 0)] * 2, levels
