"""Offline transaction-contract self-checks; no native DUT construction."""
from __future__ import annotations

import pytest

from suites.memblock.mmu.testbenches.shared.tests.transaction_helpers import (
    READY_CASES, Signal, _dut, _install_ready_cycle,
)
from suites.memblock.mmu.testbenches.ptwfilter.env.ptw import FilterEnv
from suites.memblock.mmu.testbenches.ptwfilter.transactions import Req

pytestmark = pytest.mark.selftest


async def test_offer_acceptance_is_the_same_cycle_fire():
    """Acceptance follows the pre-edge ready, including both transitions."""
    for env_type, attrs, signal_name in (
            (FilterEnv, ("req_valid", "req_vpn", "req_s2", "req_getgpa"),
             "req_valid"),):
        for before, after in READY_CASES:
            env = env_type.__new__(env_type)
            for name in attrs:
                setattr(env, name, Signal())
            env.req_ready = Signal(before)
            env.dut = _dut()
            fires: list[bool] = []
            _install_ready_cycle(env, getattr(env, signal_name), before, after, fires)
            reported = await env.offer_request(Req(0x20000))
            assert reported is fires[0], (env_type.__name__, before, after)


def test_structural_ptw_response_is_a_named_channel_operation():
    env = FilterEnv.__new__(FilterEnv)
    env.ptw_resp_pins = {name: Signal() for name in
                         ("s2xlate", "s1_entry_tag", "s1_entry_ppn",
                          "s2_entry_tag", "s2_entry_ppn", "s1_entry_asid")}
    env.ptw_resp_valid = Signal()
    env.dut = _dut()
    env.drive_structural_ptw_response(
        s2xlate=3, s1_entry_tag=7, s1_entry_ppn=9, s2_entry_tag=11,
        s2_entry_ppn=13)
    assert env.ptw_resp_pins["s1_entry_asid"].value == 0
    assert {name for name, pin in env.ptw_resp_pins.items() if pin.value} == {
        "s2xlate", "s1_entry_tag", "s1_entry_ppn", "s2_entry_tag",
        "s2_entry_ppn"}
    # Unspecified leaves keep their current stress value; filling selected
    # payload bits must not silently drop the rest of the all-ones endpoint.
    for name in ("s1_entry_asid", "s2xlate", "s1_entry_tag", "s1_entry_ppn",
                 "s2_entry_tag", "s2_entry_ppn"):
        env.ptw_resp_pins[name].Set(1)
    env.drive_structural_ptw_response(s2xlate=0)
    assert env.ptw_resp_pins["s2xlate"].value == 0
    assert all(env.ptw_resp_pins[name].value == 1 for name in
               ("s1_entry_asid", "s1_entry_tag", "s1_entry_ppn",
                "s2_entry_tag", "s2_entry_ppn"))
    # Releasing valid keeps the payload stress levels.
    env.drive_ptw_response_valid(1)
    env.clear_ptw_response()
    assert env.ptw_resp_valid.value == 0
    assert env.ptw_resp_pins["s1_entry_asid"].value == 1
    assert env.ptw_resp_pins["s2_entry_ppn"].value == 1
