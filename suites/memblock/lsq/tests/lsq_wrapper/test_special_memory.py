"""True VSQ special permission plus original Load, actual WB/effect ownership."""

from dataclasses import replace
import json
from pathlib import Path

import pytest

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.vlq.types import RobPtr
from .special_owners import SpecialOwners, SpecialStore


def outcome(trace, kind, **fields):
    report = dict(nodeid=trace.env.nodeid, kind=kind, actual_fires=trace.fires, actual_wbs=trace.wbs,
                  actual_releases=trace.releases, actual_bus_request=trace.bus_request, actual_bus_ack=trace.bus_ack,
                  actual_bus_response=trace.bus_response, actual_head=trace.head, original_load_deq=trace.load_deq, **fields)
    Path(trace.env.journal.name).with_name("special-outcome.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


@pytest.mark.parametrize("cbo", range(4))
async def test_real_cbo_owner_and_younger_cached_load_complete_independent_obligations(lsq, cbo):
    store = SpecialStore(0, RobPtr.encode(10), 0x18000, 0xABC000, value=(1 << 128) - 1, cbo=cbo)
    trace = SpecialOwners(lsq, [store])
    await trace.allocate()
    trace.activate(0)
    await trace.write(0)
    wb = await trace.cache_roundtrip(0, hold=3)
    assert wb["denied"] == wb["corrupt"] == 0
    await trace.finish()
    outcome(trace, "clean_cbo")
    lsq.prove("LSQ-RETIRE.cbo")


@pytest.mark.parametrize("hold", (0, 3))
@pytest.mark.parametrize("denied,corrupt", ((True, False), (False, True), (True, True)))
async def test_actual_cache_wb_fire_keeps_original_fault_despite_backpressure(lsq_probe, hold, denied, corrupt):
    store = SpecialStore(0, RobPtr.encode(10, former=False), (1 << 49) + 0x12340, 0xA12340, cbo=1, hyper=True)
    trace = SpecialOwners(lsq_probe, [store])
    await trace.allocate()
    trace.activate(0)
    await trace.write(0, lane=1)
    lsq_probe.reach("LSQ-EXCEPTION.cache_wb")
    wb = await trace.cache_roundtrip(0, denied=denied, corrupt=corrupt, hold=hold)
    await trace.finish(observe_only=True)
    report = outcome(trace, "cache_fault_actual_wb_fire", expected_denied=denied, expected_corrupt=corrupt, hold=hold)
    assert (wb["denied"], wb["corrupt"]) == (int(denied), int(corrupt)), ("original fault lost at actual WB.fire", report)
    assert wb["vaddr"] == store.vaddr and wb["hyper"]
    lsq_probe.prove("LSQ-EXCEPTION.cache_wb")


@pytest.mark.parametrize("old_queued", (False, True))
async def test_zero_actual_wb_and_sq_release_require_own_zero_transfer(lsq_probe, old_queued):
    old = SpecialStore(0, RobPtr.encode(10), 0x10000, 0xABC000, value=0x1122334455667788)
    zero = SpecialStore(int(old_queued), RobPtr.encode(11), 0x20000, 0xDEF000, value=(1 << 128) - 1, cbo=3)
    trace = SpecialOwners(lsq_probe, [old, zero] if old_queued else [zero])
    await trace.allocate()
    trace.activate(0)
    if old_queued:
        await trace.write(0)
        trace.activate(1)
        await trace.wait(P.p_sbuffer_req_0_valid)
    await trace.write(zero.position, lane=1)
    await trace.idle(10)
    lsq_probe.reach("LSQ-RETIRE.zero_ownership")
    trace.base = replace(trace.base, sbuffer_ready=(True, True), writeback_ready=True)
    await trace.wait(P.p_mmioStout_valid)
    await trace.cycle()
    assert any(wb["position"] == zero.position for wb in trace.wbs)
    await trace.finish(observe_only=True)
    zeros = [fire for fire in trace.fires if fire["position"] == zero.position and fire["actual"]["wline"] and fire["actual"]["data"] == 0]
    report = outcome(trace, "zero_own_actual_transfer", old_queued=old_queued, own_zero_actual_fires=len(zeros))
    assert len(zeros) == 1, ("actual zero WB/SQ release without its own zero write", report)
    assert not trace.effect_errors
    lsq_probe.prove("LSQ-RETIRE.zero_ownership")


@pytest.mark.parametrize("memory", (1, 2, 7))
@pytest.mark.parametrize("old_stalled", (False, True), ids=("consumed-old-control", "stalled-old"))
async def test_actual_special_finish_cannot_release_unconsumed_old_store_prefix(lsq_probe, memory, old_stalled):
    old = SpecialStore(0, RobPtr.encode(10), 0x30000, 0xABC000, value=0x8877665544332211)
    special = SpecialStore(1, RobPtr.encode(11), 0x40000, 0xDEF000, value=0x1111222233334444, memory=memory)
    trace = SpecialOwners(lsq_probe, [old, special])
    await trace.allocate()
    await trace.write(0)
    trace.activate(1)
    await trace.wait(P.p_sbuffer_req_0_valid)
    if not old_stalled:
        trace.base = replace(trace.base, sbuffer_ready=(True, True))
        for _ in range(30):
            await trace.cycle()
            if trace.head == 1:
                break
        assert trace.head == 1 and len(trace.fires) == 1
        trace.base = replace(trace.base, sbuffer_ready=(False, False))
    await trace.write(1, lane=1)
    await trace.bus_accept_ack(1)
    lsq_probe.reach("LSQ-RETIRE.finish_prefix")
    if memory != 1:
        await trace.bus_respond()
        await trace.wait(P.p_mmioStout_valid)
        await trace.cycle(writeback_ready=True)
    for _ in range(5):
        await trace.cycle()
    if old_stalled:
        report = outcome(trace, "finish_prefix", memory=memory, old_stalled=True, old_actual_fires=len(trace.fires))
        assert trace.head == 0, ("later special finish released an unconsumed old owner", report)
    if memory == 1:
        await trace.bus_respond()
    await trace.finish()
    outcome(trace, "finish_prefix_control", memory=memory, old_stalled=old_stalled)
    lsq_probe.prove("LSQ-RETIRE.finish_prefix")


@pytest.mark.parametrize("cbo", (2, 3), ids=("nonzero-control", "neighbor-zero"))
async def test_actual_split_tail_wline_belongs_to_ordinary_owner_not_neighbor_cbo(lsq_probe, cbo):
    old = SpecialStore(0, RobPtr.encode(10), 0x3000C, 0xABC00C, value=0x8877665544332211)
    special = SpecialStore(1, RobPtr.encode(11), 0x40000, 0xDEF000, value=(1 << 128) - 1, cbo=cbo)
    trace = SpecialOwners(lsq_probe, [old, special])
    await trace.allocate()
    await trace.write(0)
    trace.activate(1)
    await trace.write(1, lane=1)
    await trace.wait(P.p_sbuffer_req_0_valid)
    trace.base = replace(trace.base, sbuffer_ready=(True, True))
    for _ in range(30):
        await trace.cycle()
        if sum(fire["position"] == 0 for fire in trace.fires) == 2:
            break
    original = [fire for fire in trace.fires if fire["position"] == 0]
    assert len(original) == 2
    report = outcome(trace, "split_wline_actual_tail", cbo=cbo)
    assert not any(fire["actual"]["wline"] for fire in original), ("actual ordinary tail consumes neighbor CBO.zero wline", report)
    await trace.cache_roundtrip(1, hold=2)
    await trace.finish()
    assert not trace.effect_errors
