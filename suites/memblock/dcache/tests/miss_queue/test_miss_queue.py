"""MissQueue UT: MSHR allocation/merge, refill install, release, block and CMO."""
from __future__ import annotations

import pytest

from suites.memblock.dcache.miss_queue.coverage import MissQueueCoverage
from suites.memblock.dcache.miss_queue.env import (
    M_XA_ADD,
    M_XA_SWAP,
    M_XRD,
    M_XWR,
    TL_ACQUIRE_BLOCK,
    TL_ACQUIRE_PERM,
    MissQueueEnv,
    beat_pattern,
    block_addr,
    channel_of,
    dcache_alias,
    first,
    line_from_beats,
)


@pytest.fixture
def mq(dut_factory):
    dut = dut_factory("miss_queue")
    env = MissQueueEnv(dut, MissQueueCoverage())
    env.reset()
    return env


def acquire_of(snaps, channel):
    for snap in snaps:
        if snap["acquire"][channel]["valid"]:
            return snap["acquire"][channel]
    return None


def alloc_of(snaps, port):
    for snap in snaps:
        if snap["alloc"][port]["valid"]:
            return snap["alloc"][port]
    return None


# MQ-FP-001
def test_load_miss_allocates_mshr_and_acquires(mq):
    paddr = 0x8000
    vaddr = 0x1000
    snaps = mq.enqueue(port=0, paddr=paddr, vaddr=vaddr, cmd=M_XRD,
                       source=0, req_id=3)
    acq = acquire_of(snaps, channel_of(paddr))
    assert acq is not None
    assert acq["opcode"] == TL_ACQUIRE_BLOCK
    assert acq["param"] == 0  # NtoB for a load
    assert acq["size"] == 6
    assert acq["address"] == block_addr(paddr)
    assert acq["alias"] == dcache_alias(vaddr)
    assert acq["vaddr"] == vaddr >> 6
    alloc = alloc_of(snaps, 0)
    assert alloc is not None
    assert alloc["paddr"] == block_addr(paddr)
    assert alloc["vaddr"] == vaddr
    assert acq["source"] == alloc["id"]


# MQ-FP-001 / MQ-FP-009
def test_mshr_id_and_channel_selection(mq):
    first_snaps = mq.enqueue(port=0, paddr=0x9000, vaddr=0x2000, cmd=M_XRD)
    a0 = acquire_of(first_snaps, 0)
    assert a0 is not None and a0["source"] == 0
    assert a0["address"] == 0x9000

    second_snaps = mq.enqueue(port=1, paddr=0x9040, vaddr=0x2040, cmd=M_XRD)
    a1 = acquire_of(second_snaps, 1)
    assert a1 is not None
    assert a1["source"] == 1
    assert a1["address"] == 0x9040
    handled = [snap["resp"][0] for snap in second_snaps]
    assert any(item["handled"] == 1 and item["id"] == 1 for item in handled)


# MQ-FP-002
def test_merge_only_before_first_refill_beat(mq):
    paddr = 0xA000
    vaddr = 0x3000
    mq.enqueue(port=0, paddr=paddr, vaddr=vaddr, cmd=M_XRD)
    merged = mq.enqueue(port=1, paddr=paddr, vaddr=vaddr, cmd=M_XRD)
    acquires = [snap["acquire"][0]["valid"] or snap["acquire"][1]["valid"]
                for snap in merged]
    # No second Acquire on the A channel for the merged request.
    assert not any(acquires[1:])
    handled = [snap["resp"][0] for snap in merged]
    assert any(item["handled"] == 1 and item["id"] == 0 for item in handled)
    if mq.coverage is not None:
        mq.coverage.sample_merge(True, True)

    # After the first refill beat the merge window is closed: the same block is
    # rejected (ready low) instead of being merged or re-acquired.
    mq.reset()
    mq.enqueue(port=0, paddr=paddr, vaddr=vaddr, cmd=M_XRD)
    mq.refill(miss_id=0, beat0=beat_pattern(0), beat1=beat_pattern(32))
    rejected = mq.enqueue(port=1, paddr=paddr, vaddr=vaddr, cmd=M_XRD)
    assert all(snap["query_ready"][1] == 0 for snap in rejected)
    assert not any(snap["acquire"][0]["valid"] or snap["acquire"][1]["valid"]
                   for snap in rejected)
    if mq.coverage is not None:
        mq.coverage.sample_merge(False, True)

    # Different alias for the same block is not mergeable.
    mq.reset()
    mq.enqueue(port=0, paddr=paddr, vaddr=vaddr, cmd=M_XRD)
    other = mq.enqueue(port=1, paddr=paddr, vaddr=vaddr, cmd=M_XRD,
                       alias=(dcache_alias(vaddr) + 1) & 0x3)
    assert all(snap["query_ready"][1] == 0 for snap in other)
    if mq.coverage is not None:
        mq.coverage.sample_merge(True, False)


# MQ-FP-003
def test_store_miss_modes(mq):
    line = int.from_bytes(bytes([0x5A] * 64), "little")
    full = mq.enqueue(port=0, paddr=0xB000, vaddr=0x4000, cmd=M_XWR,
                      source=1, store_data=line, store_mask=(1 << 64) - 1,
                      full_overwrite=True)
    acq = acquire_of(full, 0)
    assert acq is not None
    assert acq["opcode"] == TL_ACQUIRE_PERM
    assert acq["param"] == 1  # NtoT
    assert acq["size"] == 6
    assert full[0]["mshr_store_empty"] == 0
    if mq.coverage is not None:
        mq.coverage.sample_store_flag(False)

    mq.reset()
    partial = mq.enqueue(port=0, paddr=0xB040, vaddr=0x4040, cmd=M_XWR,
                         source=1, store_data=0x42, store_mask=0x1,
                         full_overwrite=False)
    acq = acquire_of(partial, 1)
    assert acq is not None
    assert acq["opcode"] == TL_ACQUIRE_BLOCK


# MQ-FP-004
def test_two_beat_refill_installs_line(mq):
    paddr = 0xC000
    vaddr = 0x5000
    mq.enqueue(port=0, paddr=paddr, vaddr=vaddr, cmd=M_XRD)
    beat0 = beat_pattern(0)
    beat1 = beat_pattern(32)
    snaps = mq.refill(miss_id=0, beat0=beat0, beat1=beat1)
    info = first(snaps, "refill_info")
    assert info is not None
    assert info["refill_data"] == line_from_beats(beat0, beat1)
    assert info["refill_mask"] == (1 << 64) - 1
    assert info["refill_param"] == 1  # toB for AcquireBlock
    assert info["refill_denied"] == 0 and info["refill_corrupt"] == 0
    install = first(snaps, "main_pipe_req")
    assert install is not None
    assert install["main_pipe_miss_id"] == 0
    assert install["main_pipe_addr"] == block_addr(paddr)
    assert install["main_pipe_cmd"] == M_XRD
    if mq.coverage is not None:
        mq.coverage.sample_refill("clean")


# MQ-FP-004 / MQ-FP-005
def test_refill_error_flags(mq):
    for denied, corrupt, name in ((True, False, "denied"),
                                  (False, True, "corrupt")):
        mq.reset()
        mq.enqueue(port=0, paddr=0xC040, vaddr=0x5040, cmd=M_XRD)
        snaps = mq.refill(miss_id=0, beat0=beat_pattern(0),
                          beat1=beat_pattern(32), denied=denied,
                          corrupt=corrupt)
        info = first(snaps, "refill_info")
        assert info is not None, name
        assert info["refill_denied"] == (1 if denied else 0), name
        assert info["refill_corrupt"] == (1 if corrupt else 0), name
        assert info["refill_data"] == line_from_beats(beat_pattern(0),
                                                      beat_pattern(32))
        if mq.coverage is not None:
            mq.coverage.sample_refill(name)


# MQ-FP-005
def test_finish_is_returned_for_grant(mq):
    mq.enqueue(port=0, paddr=0xD000, vaddr=0x6000, cmd=M_XRD)
    snaps = mq.refill(miss_id=0, beat0=beat_pattern(0),
                      beat1=beat_pattern(32), sink=9)
    finish = [snap["finish"][0] for snap in snaps if snap["finish"][0]["valid"]]
    assert finish, "Finish must be sent for an AcquireBlock"
    assert finish[0]["sink"] == 9
    if mq.coverage is not None:
        mq.coverage.sample_release(0)


# MQ-FP-006
def test_entry_release_and_slot_reuse(mq):
    mq.enqueue(port=0, paddr=0xE000, vaddr=0x7000, cmd=M_XRD)
    mq.refill(miss_id=0, beat0=beat_pattern(0), beat1=beat_pattern(32))
    mq.complete(miss_id=0, idle=10)
    again = mq.enqueue(port=0, paddr=0xE100, vaddr=0x7100, cmd=M_XRD)
    acq = acquire_of(again, channel_of(0xE100))
    assert acq is not None
    assert acq["source"] == 0, "the released MSHR slot 0 must be reusable"
    assert acq["address"] == block_addr(0xE100)


# MQ-FP-007
def test_probe_and_replace_blocked_by_inflight_mshr(mq):
    paddr = 0xF000
    vaddr = 0x8000
    mq.enqueue(port=0, paddr=paddr, vaddr=vaddr, cmd=M_XRD)
    snaps = mq.refill(miss_id=0, beat0=beat_pattern(0),
                      beat1=beat_pattern(32))
    # Only after the last refill beat does the entry block probe/replace.
    probe_same = mq.check_block(paddr=paddr, vaddr=vaddr)
    assert probe_same["probe_block"] == 1
    assert probe_same["replace_block"] == 1
    probe_other = mq.check_block(paddr=0x9000, vaddr=0x2000)
    assert probe_other["probe_block"] == 0
    assert probe_other["replace_block"] == 0
    probe_alias = mq.check_block(paddr=paddr, vaddr=vaddr ^ 0x1000)
    assert probe_alias["probe_block"] == 0
    if mq.coverage is not None:
        mq.coverage.sample_block(True, True)
        mq.coverage.sample_block(False, False)


# MQ-FP-008 / MQ-FP-009
def test_cmo_ops_map_to_a_channel(mq):
    for opcode, expected, channel in ((0, 12, 0), (1, 13, 1), (2, 14, 0)):
        mq.reset()
        address = 0x8000 + 0x40 * channel
        result = mq.cmo_request(opcode=opcode, address=address)
        acq = result["issued"]["acquire"][channel]
        assert acq["valid"] == 1
        assert acq["opcode"] == expected
        assert acq["size"] == 6
        assert acq["address"] == block_addr(address)
        assert acq["source"] == 17  # nMissEntries + 1
        assert result["channel"] == channel
        assert result["ready"]["cmo_ready"] == 1
        if mq.coverage is not None:
            mq.coverage.sample_cmo(opcode, channel, "ok")


# MQ-FP-008
def test_cmo_response_denied_and_corrupt(mq):
    for denied, corrupt, name in ((True, False, "denied"),
                                  (False, True, "corrupt")):
        mq.reset()
        result = mq.cmo_request(opcode=0, address=0x8000, denied=denied,
                                corrupt=corrupt)
        resp = result["response"]
        assert resp is not None, name
        assert resp["cmo_denied"] == (1 if denied else 0), name
        assert resp["cmo_corrupt"] == (1 if corrupt else 0), name
        if mq.coverage is not None:
            mq.coverage.sample_cmo(0, 0, name)


# MQ-FP-003 / MQ-FP-004
def test_store_miss_refill_merges_store_data(mq):
    # Partial word store: only the masked byte comes from the Sbuffer, the rest
    # of the line is the L2 refill data.
    mq.enqueue(port=0, paddr=0x8000, vaddr=0x1000, cmd=M_XWR, source=1,
               store_data=0xAB, store_mask=0x01)
    snaps = mq.refill(miss_id=0, beat0=0, beat1=0)
    info = first(snaps, "refill_info")
    assert info is not None
    line = info["refill_data"].to_bytes(64, "little")
    assert line[0] == 0xAB
    assert line[1:] == bytes(63)
    install = first(snaps, "main_pipe_req")
    assert install is not None
    assert install["main_pipe_cmd"] == M_XWR
    assert install["main_pipe_source"] == 1
    assert snaps[-1]["mshr_store_empty"] == 0

    # Whole-line store: the refill line is the store data.
    mq.reset()
    line_value = int.from_bytes(bytes([0x55] * 64), "little")
    mq.enqueue(port=0, paddr=0x8040, vaddr=0x1040, cmd=M_XWR, source=1,
               store_data=line_value, store_mask=(1 << 64) - 1,
               full_overwrite=True)
    snaps = mq.refill(miss_id=0, beat0=0, beat1=0)
    info = first(snaps, "refill_info")
    assert info is not None
    assert info["refill_data"] == line_value
    install = first(snaps, "main_pipe_req")
    assert install is not None and install["main_pipe_cmd"] == M_XWR
    if mq.coverage is not None:
        mq.coverage.sample_refill("clean")


# MQ-FP-003
def test_amo_miss_forwards_atomic_fields(mq):
    mq.enqueue(port=0, paddr=0x8080, vaddr=0x1080, cmd=M_XA_SWAP,
               source=2, store_data=0, store_mask=0)
    snaps = mq.refill(miss_id=0, beat0=beat_pattern(0),
                      beat1=beat_pattern(32))
    install = first(snaps, "main_pipe_req")
    assert install is not None
    assert install["main_pipe_cmd"] == M_XA_SWAP
    assert install["main_pipe_source"] == 2
    assert install["main_pipe_occupy"] == 0


# MQ-FP-003 / MQ-FP-001
def test_btot_occupy_way_is_forwarded(mq):
    mq.enqueue(port=0, paddr=0x80C0, vaddr=0x10C0, cmd=M_XWR, source=1,
               store_data=0x11, store_mask=0x1, is_btot=True,
               occupy_way=0b0100)
    snaps = mq.refill(miss_id=0, beat0=beat_pattern(0),
                      beat1=beat_pattern(32))
    install = first(snaps, "main_pipe_req")
    assert install is not None
    assert install["main_pipe_occupy"] == 0b0100


# MQ-FP-001 / MQ-FP-010
def test_store_flag_clears_after_completion(mq):
    assert mq.snapshot()["mshr_store_empty"] == 1
    mq.enqueue(port=0, paddr=0x8100, vaddr=0x1100, cmd=M_XWR, source=1,
               store_data=0x22, store_mask=0x1)
    assert mq.snapshot()["mshr_store_empty"] == 0
    mq.refill(miss_id=0, beat0=beat_pattern(0), beat1=beat_pattern(32))
    assert mq.snapshot()["mshr_store_empty"] == 0
    mq.complete(miss_id=0, idle=10)
    assert mq.snapshot()["mshr_store_empty"] == 1
    if mq.coverage is not None:
        mq.coverage.sample_store_flag(True)
        mq.coverage.sample_store_flag(False)


# MQ-FP-001
def test_loadpipe_ports_and_channel1_amo(mq):
    # LoadPipe ports 1..3 also allocate; channel 1 is selected by block bit6.
    for port, paddr in ((1, 0x8840), (2, 0x88C0), (3, 0x8940)):
        mq.enqueue(port=port, paddr=paddr, vaddr=0x1800 + port * 0x40,
                   cmd=M_XRD, req_id=port)
        assert channel_of(paddr) == 1

    mq.reset()
    mq.enqueue(port=0, paddr=0x8900, vaddr=0x1900, cmd=M_XA_ADD,
               source=2, req_id=5)
    assert mq.snapshot()["acquire"][1]["valid"] == 0  # A fires on the next cycle
    snaps = mq.refill(miss_id=0, beat0=beat_pattern(0),
                      beat1=beat_pattern(32))
    install = first(snaps, "main_pipe_req")
    assert install is not None and install["main_pipe_cmd"] == M_XA_ADD


# MQ-FP-002
def test_merge_after_grant_alias_mismatch(mq):
    paddr = 0x8A00
    vaddr = 0x1A00
    mq.enqueue(port=0, paddr=paddr, vaddr=vaddr, cmd=M_XRD)
    mq.refill(miss_id=0, beat0=beat_pattern(0), beat1=beat_pattern(32))
    other = mq.enqueue(port=1, paddr=paddr, vaddr=vaddr, cmd=M_XRD,
                       alias=(dcache_alias(vaddr) + 2) & 0x3)
    assert all(snap["query_ready"][1] == 0 for snap in other)
    if mq.coverage is not None:
        mq.coverage.sample_merge(False, False)


# MQ-FP-006
def test_release_slots_one_to_three(mq):
    """Releasing entry N must make exactly slot N available again.

    The probe is the next allocation's `source`: slots 0..N-1 are still
    outstanding, so the lowest free slot is N only if N was really released.
    Without the release the allocator would hand out N+1.
    """
    for miss_id in (1, 2, 3):
        mq.reset()
        mq.enqueue(port=0, paddr=0x8B00 + miss_id * 0x40,
                   vaddr=0x1B00 + miss_id * 0x40, cmd=M_XRD)
        # Allocate up to the requested slot: MSHR ids are handed out in order.
        for extra in range(miss_id):
            mq.enqueue(port=1, paddr=0x8C00 + extra * 0x40,
                       vaddr=0x1C00 + extra * 0x40, cmd=M_XRD)
        snaps = mq.refill(miss_id=miss_id, beat0=beat_pattern(0),
                          beat1=beat_pattern(32))
        info = first(snaps, "refill_info")
        assert info is not None, f"slot {miss_id}: refill produced no refill_info"
        assert info["refill_mask"] == (1 << 64) - 1, (miss_id, hex(info["refill_mask"]))
        mq.complete(miss_id=miss_id, idle=8)

        paddr = 0x90000 + miss_id * 0x40
        vaddr = 0x30000 + miss_id * 0x40
        after = mq.enqueue(port=0, paddr=paddr, vaddr=vaddr, cmd=M_XRD)
        acq = acquire_of(after, channel_of(paddr))
        assert acq is not None, f"slot {miss_id}: no Acquire after release"
        assert acq["source"] == miss_id, (
            f"released slot {miss_id} not reused; got source {acq['source']}")
        assert acq["address"] == block_addr(paddr), (miss_id, acq)
        if mq.coverage is not None:
            mq.coverage.sample_release(miss_id)


# MQ-FP-008
def test_cmo_all_opcode_response_pairs(mq):
    for opcode in (0, 1, 2):
        for denied, corrupt in ((False, False), (True, False), (False, True)):
            mq.reset()
            address = 0x8000 if opcode != 1 else 0x8040
            result = mq.cmo_request(opcode=opcode, address=address,
                                    denied=denied, corrupt=corrupt)
            resp = result["response"]
            assert resp is not None
            assert resp["cmo_denied"] == (1 if denied else 0)
            assert resp["cmo_corrupt"] == (1 if corrupt else 0)
            if mq.coverage is not None:
                state = "denied" if denied else "corrupt" if corrupt else "ok"
                mq.coverage.sample_cmo(opcode, result["channel"], state)


# MQ-FP-003 / MQ-FP-009
def test_amo_miss_uses_channel_one(mq):
    paddr = 0x8840  # block bit6 = 1
    assert channel_of(paddr) == 1
    mq.enqueue(port=0, paddr=paddr, vaddr=0x1840, cmd=M_XA_ADD, source=2)
    snaps = mq.refill(miss_id=0, beat0=beat_pattern(0),
                      beat1=beat_pattern(32))
    install = first(snaps, "main_pipe_req")
    assert install is not None
    assert install["main_pipe_cmd"] == M_XA_ADD
    if mq.coverage is not None:
        mq.coverage.sample_alloc(M_XA_ADD, False, 1, 0)


# MQ-FP-001
def test_parallel_enqueue_allocates_three_mshrs(mq):
    requests = [
        dict(port=0, paddr=0x8C00, vaddr=0x1C00),
        dict(port=1, paddr=0x8C40, vaddr=0x1C40),
        dict(port=2, paddr=0x8C80, vaddr=0x1C80),
    ]
    snaps = mq.enqueue_parallel(requests)
    accepts = []
    for snap in snaps:
        for channel in range(2):
            acq = snap["acquire"][channel]
            if acq["valid"]:
                accepts.append((acq["address"], acq["source"]))
    assert [addr for addr, _ in accepts] == [0x8C00, 0x8C40, 0x8C80], accepts
    assert [source for _, source in accepts] == [0, 1, 2], accepts
    allocated = []
    for snap in snaps:
        for port in range(3):
            if snap["alloc"][port]["valid"]:
                allocated.append((snap["alloc"][port]["paddr"],
                                  snap["alloc"][port]["id"]))
    assert (0x8C00, 0) in allocated
    assert (0x8C40, 1) in allocated
    assert (0x8C80, 2) in allocated


# MQ-FP-002
def test_same_cycle_same_block_compresses(mq):
    snaps = mq.enqueue_parallel([
        dict(port=0, paddr=0x8D00, vaddr=0x1D00),
        dict(port=1, paddr=0x8D00, vaddr=0x1D00),
    ])
    responses = [snap["resp"][0] for snap in snaps]
    assert any(item["handled"] == 1 and item["id"] == 0 for item in responses)
    acquires = [(snap["acquire"][ch]["address"], snap["acquire"][ch]["source"])
                for snap in snaps for ch in range(2)
                if snap["acquire"][ch]["valid"]]
    assert acquires == [(0x8D00, 0)], acquires
    if mq.coverage is not None:
        mq.coverage.sample_merge(True, True)


# MQ-FP-006 / MQ-FP-007
def test_wbq_backpressure_blocks_acceptance(mq):
    snaps = mq.enqueue(port=0, paddr=0x8E00, vaddr=0x1E00, cmd=M_XRD,
                       wbq_block=0x1)
    assert all(snap["query_ready"][0] == 0 for snap in snaps)
    assert not any(snap["acquire"][ch]["valid"] for snap in snaps
                   for ch in range(2))
    assert not any(snap["alloc"][0]["valid"] for snap in snaps)

    # Removing the block lets the same request allocate normally.
    mq.set_wbq_block(0)
    snaps = mq.enqueue(port=0, paddr=0x8E00, vaddr=0x1E00, cmd=M_XRD)
    assert any(snap["acquire"][ch]["valid"] for snap in snaps
               for ch in range(2))
    assert any(snap["alloc"][0]["valid"] for snap in snaps)


# MQ-FP-004
def test_mainpipe_feedback_reissues_install(mq):
    mq.enqueue(port=0, paddr=0x8F00, vaddr=0x1F00, cmd=M_XRD)
    mq.refill(miss_id=0, beat0=beat_pattern(0), beat1=beat_pattern(32))
    replay = mq.mainpipe_feedback(miss_id=0, replay=True, cycles=3)
    assert any(snap["main_pipe_req"] for snap in replay)
    assert any(snap["main_pipe_miss_id"] == 0 for snap in replay)

    mq.reset()
    mq.enqueue(port=0, paddr=0x8F40, vaddr=0x1F40, cmd=M_XRD)
    mq.refill(miss_id=0, beat0=beat_pattern(0), beat1=beat_pattern(32))
    evict = mq.mainpipe_feedback(miss_id=0, evict_btot=True, next_way=0b0100,
                                 cycles=3)
    assert any(snap["main_pipe_req"] for snap in evict)
    assert any(snap["main_pipe_occupy"] == 0b0100 for snap in evict)


# MQ-FP-002 / known defect MQ-STORE-MERGE-DATA-PENDING
@pytest.mark.rtl_defect
@pytest.mark.xfail(strict=True,
                   reason="MQ-STORE-MERGE-DATA-PENDING: the second merged store's "
                          "bytes never reach refill_and_store_data; the refill line "
                          "keeps the L2 byte or is zeroed instead of the store byte")
def test_second_store_merge_carries_its_bytes(mq):
    """Two partial stores to one missing line must both survive the refill.

    store1 writes byte0=0xAA (mask 0x01), store2 writes byte1=0xBB (mask 0x02).
    store2 is accepted as a merge (ready=1, handled=1, no second Acquire), so the
    installed line must contain 0xBBAA.  In this RTL the refill line is 0x01AA:
    the second store's mask/data update is gated by
    `miss_req_pipe_reg.merge && req_source == STORE_SOURCE` in MissEntry, which is
    not asserted for a store that merges after the entry has been allocated.
    """
    paddr = 0xE000
    vaddr = 0x7000
    mq.enqueue(port=0, paddr=paddr, vaddr=vaddr, cmd=M_XWR, source=1,
               store_data=0xAA, store_mask=0x01, cycles=2)
    merged = mq.enqueue(port=1, paddr=paddr, vaddr=vaddr, cmd=M_XWR, source=1,
                        store_data=0xBB, store_mask=0x02, cycles=3)
    assert merged[0]["query_ready"][1] == 1, merged[0]
    assert merged[0]["resp"][0]["handled"] == 1, merged[0]
    snaps = mq.refill(miss_id=0, beat0=beat_pattern(0), beat1=beat_pattern(32))
    info = first(snaps, "refill_info")
    assert info is not None
    assert info["refill_data"] & 0xFFFF == 0xBBAA, hex(info["refill_data"] & 0xFFFF)


# MQ-FP-002 / multi-port accounting
def test_parallel_merge_into_one_pipe_reg(mq):
    """Allocate on port 0, then merge two loads in parallel on ports 1 and 2.

    This exercises the multi-port merge accounting (resp_1..resp_3 merge ids and the
    parallel pipe-reg bookkeeping): exactly one Acquire, two handled responses that
    both name MSHR 0, and no third allocation.
    """
    paddr = 0x9A00
    vaddr = 0x2A00
    first = mq.enqueue(port=0, paddr=paddr, vaddr=vaddr, cmd=M_XRD)
    assert acquire_of(first, 0) is not None

    merged = mq.enqueue_parallel([
        dict(port=1, paddr=paddr, vaddr=vaddr),
        dict(port=2, paddr=paddr, vaddr=vaddr),
    ], cycles=4)
    handled = [snap["resp"][:3] for snap in merged]
    named = [item for snap in handled for item in snap
             if item["handled"] == 1]
    assert named, handled
    assert all(item["id"] == 0 for item in named), named
    acquires = [(snap["acquire"][ch]["address"], snap["acquire"][ch]["source"])
                for snap in merged for ch in range(2)
                if snap["acquire"][ch]["valid"]]
    assert acquires == [], acquires
    allocations = [snap["alloc"][port]["valid"] for snap in merged for port in range(3)]
    assert not any(allocations), allocations
    if mq.coverage is not None:
        mq.coverage.sample_merge(True, True)


# MQ-FP-002 / multi-port accounting
def test_parallel_store_merge_accounting(mq):
    """Two store merges presented together must not allocate or re-acquire.

    The store source has a single physical port at the LSU, so this is a structural
    check of the multi-port accounting (accepted, handled, one MSHR) rather than a
    reachable store timing; it is paired with the end-to-end reproducer
    `test_second_store_merge_carries_its_bytes` for the data semantics.
    """
    paddr = 0x9B00
    vaddr = 0x2B00
    mq.enqueue(port=0, paddr=paddr, vaddr=vaddr, cmd=M_XWR, source=1,
               store_data=0x11, store_mask=0x01)
    merged = mq.enqueue_parallel([
        dict(port=1, paddr=paddr, vaddr=vaddr, cmd=M_XWR, source=1,
             store_data=0x22, store_mask=0x02),
        dict(port=2, paddr=paddr, vaddr=vaddr, cmd=M_XWR, source=1,
             store_data=0x44, store_mask=0x04),
    ], cycles=4)
    handled = [item for snap in merged for item in snap["resp"][:3]
               if item["handled"] == 1]
    assert handled, merged[0]
    assert all(item["id"] == 0 for item in handled), handled
    acquires = [(snap["acquire"][ch]["address"], snap["acquire"][ch]["source"])
                for snap in merged for ch in range(2)
                if snap["acquire"][ch]["valid"]]
    assert acquires == [], acquires


# MQ-FP-001 / multi-store stress
def test_eight_consecutive_store_misses(mq):
    """Eight back-to-back store misses each allocate, acquire and refill cleanly.

    This also drives the internal `source_except_load_cnt` / memSetPattern counter
    (MissQueue.scala:1811-1826).  That hint has no port in this independently
    built DUT — it feeds MissEntry's prefetch gate — so the assertions are on the
    observable outcomes: every store gets its own MSHR + AcquireBlock and its
    refill installs.
    """
    mq.reset()
    mq.lq_empty.Set(1)
    for index in range(8):
        paddr = 0x20000 + index * 0x40
        vaddr = 0x10000 + index * 0x40
        snaps = mq.enqueue(port=0, paddr=paddr, vaddr=vaddr, cmd=M_XWR,
                           source=1, store_data=0x5A, store_mask=0x01)
        acq = acquire_of(snaps, channel_of(paddr))
        assert acq is not None, (index, "no Acquire")
        assert acq["opcode"] == TL_ACQUIRE_BLOCK, (index, acq)
        assert acq["address"] == block_addr(paddr), (index, acq)
        miss_id = acq["source"]
        refill = mq.refill(miss_id=miss_id, beat0=beat_pattern(0),
                           beat1=beat_pattern(32))
        info = first(refill, "refill_info")
        assert info is not None, (index, "no refill_info")
        assert info["refill_mask"] == (1 << 64) - 1, (index, hex(info["refill_mask"]))
        install = first(refill, "main_pipe_req")
        assert install is not None, (index, "no install")
        assert install["main_pipe_miss_id"] == miss_id, (index, install)


# MQ-FP-002 / multi-port accounting
def test_three_ports_merge_into_one_entry(mq):
    """Three ports merging into the same allocated entry in one cycle."""
    paddr, vaddr = 0x9C00, 0x2C00
    mq.enqueue(port=0, paddr=paddr, vaddr=vaddr, cmd=M_XRD)
    merged = mq.enqueue_parallel([
        dict(port=1, paddr=paddr, vaddr=vaddr),
        dict(port=2, paddr=paddr, vaddr=vaddr),
        dict(port=3, paddr=paddr, vaddr=vaddr),
    ], cycles=4)
    handled = [item for snap in merged for item in snap["resp"]
               if item["handled"] == 1]
    assert handled, merged[0]
    assert all(item["id"] == 0 for item in handled), handled
    acquires = [(snap["acquire"][ch]["address"], snap["acquire"][ch]["source"])
                for snap in merged for ch in range(2)
                if snap["acquire"][ch]["valid"]]
    assert acquires == [], acquires


# MQ-FP-001 / per-port bookkeeping
def test_store_misses_on_every_query_port(mq):
    """Cycle store misses over all four queryMQ ports.

    Each port has its own arm in the `source_except_load_cnt` priority chain and in
    the `parallel_pipe_regs_N` mshr_id/alloc bookkeeping (MissQueue.scala:1811-1826),
    and directed tests previously used ports 0/1 only.  Every store must still get
    its own MSHR, AcquireBlock and refill install.
    """
    mq.reset()
    mq.lq_empty.Set(1)
    for index in range(8):
        port = index % 4
        paddr = 0x24000 + index * 0x80
        vaddr = 0x14000 + index * 0x80
        snaps = mq.enqueue(port=port, paddr=paddr, vaddr=vaddr, cmd=M_XWR,
                           source=1, store_data=0x11 << (index % 4),
                           store_mask=0x03)
        acq = acquire_of(snaps, channel_of(paddr))
        assert acq is not None, (port, index, "no Acquire")
        assert acq["address"] == block_addr(paddr), (port, index, acq)
        assert acq["opcode"] == TL_ACQUIRE_BLOCK, (port, index, acq)
        refill = mq.refill(miss_id=acq["source"],
                           beat0=beat_pattern(0), beat1=beat_pattern(32))
        assert first(refill, "refill_info") is not None, (port, index)
        install = first(refill, "main_pipe_req")
        assert install is not None and install["main_pipe_miss_id"] == acq["source"], (port, index)


# MQ-FP-001 / capacity
def test_mshr_full_flag_tracks_free_entries(mq):
    """`io_full` must be 0 with a free entry and 1 when all 16 are taken."""
    mq.reset()
    assert mq._val(mq.full) == 0, "16 free entries must not report full"
    for index in range(16):
        paddr = 0x40000 + index * 0x80
        snaps = mq.enqueue(port=0, paddr=paddr, vaddr=0x8000 + index * 0x80,
                           cmd=M_XRD)
        assert acquire_of(snaps, channel_of(paddr)) is not None, index
        if index < 15:
            assert mq._val(mq.full) == 0, (index, "full too early")
    assert mq._val(mq.full) == 1, "all 16 entries taken => full"

    # A 17th miss must be refused (ready=0) while full.
    refused = mq.enqueue(port=0, paddr=0x60000, vaddr=0xA000, cmd=M_XRD)
    assert all(snap["query_ready"][0] == 0 for snap in refused), refused
