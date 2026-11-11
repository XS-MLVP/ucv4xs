"""Cross-module interaction probes derived from the Scala contracts.

Two windows that the existing suite never asks about:

1. ``IWL-UQ-SECOND-PAGE`` (upstream #6822).  ``NewStoreQueue.scala:1299`` releases
   the UnalignQueue second page on ``writeSbufferWire.head.fire``, i.e. when the
   *first* 16B fragment is accepted by Sbuffer.  Both fragments then live in
   ``EnterSbufferQueue`` and drain independently, so between the first accept and
   the second accept the older store's second-page bytes are in neither Sbuffer
   nor UnalignQueue.  ``ForwardModule`` learns the page hazard only from
   ``unalignQueue.forwardEntries`` (``:1632``), so a younger Load to the second
   page must still be blocked per the spec but is not.

2. ``IWL-NC-CROSS16B``.  ``NewStoreQueue.scala:1448`` asserts that an uncached
   request never crosses 16B, but the request builder (``:1071-1080``) emits a
   single 8-byte mask.  The assertion is dropped from the generated RTL
   (``$fatal`` count is 0), so the combination silently writes half the store.

Both probes read public pins only.  Each carries a legal control so a failure
cannot be produced by a broken stimulus.
"""
from dataclasses import replace

import pytest

from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import Address
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import Data
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import Dispatch
from suites.memblock.lsq.testbenches.psq.transactions import Attributes
from suites.memblock.lsq.testbenches.psq.transactions import SecondPage
from suites.memblock.lsq.testbenches.raw.transactions import SqPtr
from suites.memblock.lsq.testbenches.vlq.transactions import RobPtr
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.memory_owners import MemoryOwners
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.memory_owners import StoreOwner
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.memory_owners import cached_load


@pytest.mark.parametrize("lane", range(3))
@pytest.mark.parametrize("phase", ("uq_held", "uq_released"))
async def test_second_page_must_stay_blocked_until_the_store_leaves_the_queue(lsq, lane, phase):
    trace = MemoryOwners(lsq)
    store = StoreOwner(0, RobPtr.encode(10), 0x1FFC, 0xABCFFC, 3, 0x8877665544332211, second_page=0xDEF000)
    load = cached_load(0, 11, 1, 0x2000, 0xDEF000, size=2)
    await trace.dispatch([store], [load])
    await trace.dispatch(stores=[], loads=[])

    # First 16B fragment plus data, then accept the second page in UnalignQueue.
    await trace.cycle(addresses=(store.address(), Address()), data=(Data(), store.data()))
    for _ in range(40):
        await trace.cycle(second_pages=(SecondPage(True, SqPtr.encode(0), store.second_page), SecondPage()))
        if lsq.pre_response.unalign_ready[0]:
            break
    else:
        raise AssertionError("real UQ never accepted the second physical page")
    await trace.cycle(addresses=(store.address(tail=True), Address()))
    await trace.idle(4)

    if phase == "uq_released":
        # ROB head reaches the store so it becomes committed, then let Sbuffer
        # accept the first fragment while port 1 stays back-pressured.  The Scala
        # releases the UnalignQueue entry on writeSbufferWire.head.fire (:1299).
        trace.base = replace(trace.base, pending=RobPtr.encode(10), pending_next=RobPtr.encode(10))
        for _ in range(40):
            await trace.cycle()
            if lsq.pre_response.sbuffer_word_0 is not None:
                break
        else:
            raise AssertionError("cross-16B head never presented to Sbuffer port 0")
        for _ in range(20):
            await trace.cycle(sbuffer_ready=(True, False))
            if lsq.pre_response.sbuffer_word_0 is not None:
                break
        else:
            raise AssertionError("cross-16B head never accepted on Sbuffer port 0")
        await trace.idle(2)
        # Evidence that the window is real: after the first fragment was accepted,
        # EnterSbufferQueue still holds at least one fragment (it is presented on
        # port 0 again because the FIFO output is compacted), so the older store's
        # second-page bytes are neither in Sbuffer nor (after :1299) in UnalignQueue.
        pending_second = lsq.pre_response.sbuffer_word_0 is not None or lsq.pre_response.sbuffer_word_1 is not None
    else:
        pending_second = False

    response = await trace.forward(load, lane)
    blocked = any((response.forward_invalid,response.match_invalid,response.addr_invalid,response.data_invalid))
    forwarded_ok = response.forward_mask >> 2 & 1 == 1 and response.forward_data >> 16 & 255 == 0x55
    report = dict(nodeid=lsq.nodeid, phase=phase, lane=lane, blocked=blocked, forwarded_ok=forwarded_ok,
                  second_fragment_still_pending=pending_second,
                  forward_mask=[response.forward_mask >> b & 1 for b in range(16)])
    if phase == "uq_released":
        assert pending_second, ("probe did not actually create the window: the second "
                                "fragment had already reached Sbuffer", report)
    # Spec: the older store's second-page bytes are not yet in Sbuffer, so the
    # younger Load must be blocked (or receive the right bytes).  Clean acceptance
    # with no forwarded bytes is the stale-read window.
    assert blocked or forwarded_ok, (
        "younger Load accepted with no block and no forwarded bytes while the older "
        "cross-page store's second fragment has not reached Sbuffer", report)


@pytest.mark.parametrize("case", ("nc_aligned", "nc_misaligned_with_upstream_exception"))
async def test_uncached_store_respects_upstream_misalign_exception(lsq_probe, case):
    """``NewStoreUnit.scala:633`` raises ``storeAddrMisaligned`` for a misaligned
    scalar NC store, so LSQ's ``uncacheCanHandle`` (which requires
    ``!hasException``) must never see that combination clean.

    An earlier version of this probe drove a misaligned NC store with
    ``hasException=0`` and reported the single-8-byte mask as a defect.  That was
    illegal stimulus: upstream always sets the exception first.  The corrected
    probe checks the two legal inputs.
    """
    from suites.memblock.lsq.testbenches.lsq_wrapper.tests.special_owners import SpecialOwners
    from suites.memblock.lsq.testbenches.lsq_wrapper.tests.special_owners import SpecialStore

    if case == "nc_aligned":
        store = SpecialStore(0, RobPtr.encode(10), 0x30008, 0xABC008,
                             value=0x8877665544332211, memory=1)
        expect_request = True
    else:
        # offset 12 with an 8-byte store is misaligned AND crosses 16B; upstream
        # marks it storeAddrMisaligned, which is what ``exception=True`` models.
        store = SpecialStore(0, RobPtr.encode(10), 0x3000C, 0xABC00C,
                             value=0x8877665544332211, memory=1, exception=True)
        expect_request = False
    assert store.address().cross_word is (case != "nc_aligned")

    trace = SpecialOwners(lsq_probe, [store])
    await trace.allocate()
    trace.activate(0)
    await trace.write(0, lane=1)

    seen = False
    for _ in range(40):
        await trace.cycle()
        if lsq_probe.pre_response.uncache_request is not None:
            seen = True
            break
    report = dict(nodeid=lsq_probe.nodeid, case=case, has_exception=store.exception,
                  request_seen=seen,
                  req_mask=hex(lsq_probe.pre_response.uncache_sample.mask))
    if expect_request:
        assert seen, ("legal aligned NC store never reached the shared bus", report)
        mask = lsq_probe.pre_response.uncache_request.mask
        assert bin(mask).count("1") == 8, (
            "an aligned 8-byte uncached store must cover all eight bytes", report)
    else:
        assert not seen, (
            "LSQ issued an uncached request for a store that upstream marked "
            "storeAddrMisaligned; hasException must suppress the uncache FSM", report)
    # No drain: the exception case never completes by design, and the aligned case
    # has already been observed at the bus request.  Both leave the queue populated,
    # which is the honest end state of this probe.
