"""Uncached (MMIO) Store bus errors must reach the original ROB owner.

``UncacheWordResp`` carries bus failures in ``nderr`` (access fault) and
``error`` (hardware error); the DCache producer drives exactly those two and
leaves the legacy ``denied``/``corrupt`` fields undriven, which is what the
load side already reads.  This probe drives the public wrapper pins with the
same shared-bus responses a real MMIO store receives, and pairs every fault
with a benign response on the identical stimulus so the check cannot pass by
inventing an exception.
"""
from dataclasses import replace

import pytest

from suites.memblock.lsq.testbenches.vlq.transactions import RobPtr
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.special_owners import SpecialOwners
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.special_owners import SpecialStore


def outcome(trace, **fields):
    return dict(wbs=trace.wbs, bus_request=trace.bus_request, bus_ack=trace.bus_ack,
                bus_response=trace.bus_response, head=trace.head, load_deq=trace.load_deq, **fields)


async def mmio_store_response(lsq_probe, *, nderr=False, error=False):
    store = SpecialStore(0, RobPtr.encode(10), 0x20000, 0xA020000, value=0x8877665544332211, memory=2)
    trace = SpecialOwners(lsq_probe, [store])
    await trace.allocate()
    trace.activate(0)
    await trace.write(0, lane=1)
    await trace.bus_accept_ack(0)
    await trace.cycle(bus=replace(trace.base.bus, response=True, response_to_load=False,
                                  response_id=trace.bus_ack["sid"], nderr=nderr, error=error))
    for _ in range(12):
        if lsq_probe.response.mmio_stout is not None:
            break
        await trace.cycle()
    report = outcome(trace, nderr=nderr, error=error,
                     wb_valid=lsq_probe.response.mmio_stout is not None,
                     wb_denied=lsq_probe.response.mmio_sample.access_fault,
                     wb_corrupt=lsq_probe.response.mmio_sample.bus_error)
    await trace.finish(observe_only=True)
    return trace, report


@pytest.mark.parametrize("nderr,error", ((False, False), (True, False), (False, True)),
                         ids=("benign-control", "access-fault", "hardware-error"))
async def test_mmio_store_bus_fault_must_reach_original_writeback(lsq_probe, nderr, error):
    trace, report = await mmio_store_response(lsq_probe, nderr=nderr, error=error)
    assert report["wb_valid"], ("MMIO Store never produced the original-owner writeback", report)
    assert report["bus_response"] is not None, report
    if nderr:
        assert report["wb_denied"] == 1, ("MMIO Store access fault from nderr was dropped at writeback", report)
        assert report["wb_corrupt"] == 0, ("access fault was re-labelled as a hardware error", report)
    elif error:
        assert report["wb_corrupt"] == 1, ("MMIO Store hardware error from error was dropped at writeback", report)
        assert report["wb_denied"] == 0, ("hardware error was re-labelled as an access fault", report)
    else:
        assert report["wb_denied"] == 0 and report["wb_corrupt"] == 0, (
            "benign MMIO response invented an exception", report)
