"""Architectural intent of the named performance event, not RTL equivalence.

The original fixed RTL fails the miss case. Keep it a normal FAIL in the
default suite; the hit is a negative control. Do not waive or copy perf3=0
from the implementation into this expected result.
"""
import pytest

from lsuverify.load_s2.env import LoadS2Env
from .test_load_s2 import make, pipe


@pytest.mark.parametrize("miss", [0, 1])
def test_hw_pf_miss_event_counts_a_real_cache_miss(dut_factory, miss):
    dut = dut_factory("load_s2")
    env = LoadS2Env(dut)
    env.reset()
    # package.scala: prefetchHiConf=1<<4. A hardware prefetch has mask=0;
    # no redirect/kill, no forwarding, no replay and no exception.
    env.cycle(make(load=pipe(entrance=0x10, accessType_instrType=4,
                             accessType_pftType=0, mask=0),
                   dcache={"miss": miss}), "hardware prefetch response")
    env.cycle(make(load=pipe()), "two-register performance observation")
    assert int(dut.io_perf_2_value.value) == 1, "prefetch really reached S2"
    assert int(dut.io_perf_3_value.value) == miss, "hw-prefetch miss event"
