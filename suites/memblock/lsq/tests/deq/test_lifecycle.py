
from dataclasses import replace
import random

import pytest

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.deq.agent import PsqAgent
from suites.memblock.lsq.deq.types import Inputs, SecondPage, Store
from suites.memblock.lsq.raw.types import SqPtr
from suites.memblock.lsq.vlq.types import RobPtr


def store(va=0x18000, size=8, *, tag=1, **kwargs):
    data = int.from_bytes(bytes((tag * 19 + byte * 23) % 256 for byte in range(16)), "little")
    return Store(vaddr=va, page=0xA123 + tag, byte_mask=(1 << size) - 1, data=data, committed=True,
                 data_valid=True, address_valid=True, cross_word=va % 16 + size > 16, **kwargs)


async def test_full_capacity_overlap_credit_and_drain(deq_full):
    agent = PsqAgent(deq_full)
    uids = [agent.add(store(0x18000 + i * 32, tag=i + 1)) for i in range(6)]
    first = await agent.step(sbuffer_ready=(False, False))
    assert first["read_after"] == 2 and first["head_after"] == 0
    for _ in range(3):
        blocked = await agent.step(sbuffer_ready=(False, False))
        assert blocked["read_after"] == 2 and blocked["head_after"] == 0
    overlap = await agent.step(sbuffer_ready=(True, False))
    assert len(overlap["consumed"]) == 1 and overlap["read_after"] == 3 and not overlap["retired"]
    overlap = await agent.step(sbuffer_ready=(True, True))
    assert len(overlap["consumed"]) == 2 and overlap["read_after"] == 5 and len(overlap["retired"]) == 1
    await agent.drain()
    agent.checked(("DEQ-BACKPRESSURE.capacity", "DEQ-BACKPRESSURE.overlap", "DEQ-BACKPRESSURE.compact", "DEQ-CREDIT.real_fire"), uids)


@pytest.mark.parametrize("cbo", (0, 1, 2, 3))
async def test_full_cbo_all_operations(deq_full, cbo):
    agent = PsqAgent(deq_full)
    item = store(0x54340, cache_operation=True, cbo=cbo, hyper=True)
    if cbo == 3:
        item = replace(item, data=0, byte_mask=0xFFFF)
    uid = agent.add(item, rob=RobPtr.encode(319, former=False))
    for _ in range(7):
        await agent.step(sbuffer_ready=(False, False), sbuffer_empty=False, cache_ready=False, writeback_ready=False)
        assert not agent.completed
    for _ in range(5):
        await agent.step(sbuffer_empty=False, cache_ready=False, writeback_ready=False)
        assert not agent.completed
    for _ in range(5):
        await agent.step(cache_ready=False, writeback_ready=False)
        assert not agent.completed
    await agent.drain()
    names = ("DEQ-CBO." + ("inval", "clean", "flush", "zero")[cbo], "DEQ-CBO.drain", "DEQ-EXCEPTION.identity", "DEQ-IDENTITY.rob_slot")
    agent.checked(names + (("DEQ-CREDIT.zero",) if cbo == 3 else ("DEQ-CBO.request_hold",)), [uid])


@pytest.mark.parametrize("pattern", ((True,), (True, True), (True, False), (False, True), (False, True, False, True, True)))
async def test_full_inactive_prefix_and_mixed(deq_full, pattern):
    agent = PsqAgent(deq_full)
    uids = [agent.add(Store(inactive=True, committed=True) if inactive else store(0x19000 + i * 16, tag=i + 1)) for i, inactive in enumerate(pattern)]
    await agent.drain()
    name = "one" if len(pattern) == 1 else "two" if all(pattern) else "mixed"
    agent.checked(("DEQ-INACTIVE." + name,), uids)


@pytest.mark.parametrize("size", (1, 2, 4, 8, 16))
async def test_full_all_sizes_at_each_byte_offset(deq_full, size):
    agent = PsqAgent(deq_full, base=61)
    uids = []
    for offset in range(16):
        uid = agent.add(store(0x24000 + offset, size, tag=offset + size))
        uids.append(uid)
        await agent.step(sbuffer_ready=(False, False))
        for _ in range(2):
            await agent.step(sbuffer_ready=(False, False))
        await agent.drain()
    agent.checked(("DEQ-BYTE.sizes", "DEQ-BYTE.offset", "DEQ-BYTE.source", "DEQ-CACHE.single", "DEQ-CREDIT.real_fire"), uids)


async def test_full_width_virtual_page_and_sbuffer_payload_roundtrip(deq_full):
    """Move legal 50/36/128-bit store payloads through the real Sbuffer path."""
    agent = PsqAgent(deq_full, base=7)
    item = replace(
        store((1 << 50) - 16, 16, tag=99),
        page=(1 << 36) - 1,
        data=(1 << 128) - 1,
    )
    uid = agent.add(item, rob=RobPtr.encode(159, former=False))
    await agent.drain()
    assert uid in agent.completed and not agent.aborted
    agent.checked(("DEQ-BYTE.offset", "DEQ-BYTE.source", "DEQ-CACHE.single", "DEQ-CREDIT.real_fire"), [uid])


@pytest.mark.parametrize("base", (0, 63, 64, 127, 128, 191, 192, 255))
async def test_full_split_line_page_and_sq_rob_identity(deq_full, base):
    agent = PsqAgent(deq_full, base=base)
    # An unrelated UQ head with same low index but one wrong flag must not
    # redirect an ordinary same-page split. Explicit UNIT-INTERFACE negative.
    uids = [agent.add(store(0x2803C, 8, tag=base + 1))]
    wrong = SecondPage(True, 0xCAFE000, SqPtr.encode(base ^ 64))
    await agent.step(sbuffer_ready=(False, False), second_page=wrong)
    assert not deq_full.pre_observed[P.p_fromUnalignQueue_ready]
    for _ in range(2):
        await agent.step(sbuffer_ready=(False, False))
    await agent.drain()
    uids.append(agent.add(store(0x38FFC, 8, tag=base + 2), second_page=0xABCD000))
    await agent.step(sbuffer_ready=(False, False))
    assert deq_full.pre_observed[P.p_fromUnalignQueue_ready]
    await agent.step(sbuffer_ready=(True, False))
    assert not deq_full.observed[P.p_sqDeqCnt]
    await agent.drain()
    # Exercise the other SQ flag independently at the same low slot.
    uids.append(agent.add(store(0x4800C, 8, tag=base + 3)))
    await agent.step(second_page=SecondPage(True, 0xBEEF000, SqPtr.encode(agent.read ^ 128)))
    assert not deq_full.pre_observed[P.p_fromUnalignQueue_ready]
    await agent.drain()
    for flag in (False, True):
        for former in (False, True):
            uids.append(agent.add(store((1 << 49) + 0x55008, memory_type=2, hyper=former), rob=RobPtr(flag, 159, former)))
            await agent.drain()
    agent.checked(("DEQ-SPLIT.word", "DEQ-SPLIT.line", "DEQ-SPLIT.page", "DEQ-SPLIT.identity", "DEQ-CREDIT.split", "DEQ-IDENTITY.flags", "DEQ-IDENTITY.rob_slot", "DEQ-EXCEPTION.identity"), uids)


@pytest.mark.parametrize("memory_type", (1, 5, 2, 7))
async def test_full_uncache_ack_wb_and_real_psq_finish(deq_full, memory_type):
    agent = PsqAgent(deq_full, base=127)
    uids = [agent.add(store(0x58008, 8, memory_type=memory_type), rob=RobPtr.encode(319, former=False))]
    for _ in range(4):
        await agent.step(uncache_ready=False)
        assert agent.head == agent.read == 127
    await agent.step()
    if memory_type in (1, 5):
        for _ in range(3):
            await agent.step(uncache_ack_valid=True, uncache_ack_to_load=True)
            assert agent.head == agent.read == 127
        ack = await agent.step()
        assert ack["nc_ack_uid"] == uids[0] and ack["read_after"] == 128 and ack["head_after"] == 127
        credit = await agent.step()
        assert credit["retired"] == uids and not credit["wb_uid"]
        names = ("DEQ-NC.memory" if memory_type == 1 else "DEQ-NC.device", "DEQ-NC.direction", "DEQ-NC.hold", "DEQ-CREDIT.nc")
    else:
        for _ in range(3):
            await agent.step(uncache_response=False)
            assert agent.head == agent.read == 127
        await agent.step(writeback_ready=False)
        for _ in range(3):
            await agent.step(writeback_ready=False)
            assert agent.head == agent.read == 127
        wb = await agent.step()
        assert wb["wb_uid"] == uids[0] and wb["read_after"] == 128 and wb["head_after"] == 127
        credit = await agent.step()
        assert credit["retired"] == uids
        names = ("DEQ-MMIO.memory" if memory_type == 2 else "DEQ-MMIO.device", "DEQ-CREDIT.mmio")
    await agent.drain()
    agent.checked(names, uids)


@pytest.mark.parametrize("phase", ("queue", "cache", "uncache", "wb"))
async def test_full_reset_aborts_old_owner_and_same_slot_new_uid_completes(deq_full, phase):
    agent = PsqAgent(deq_full)
    old = agent.add(store(cache_operation=True, cbo=1) if phase in ("cache", "wb") else store(memory_type=2) if phase == "uncache" else store())
    if phase == "queue":
        await agent.step(sbuffer_ready=(False, False))
        await agent.step(sbuffer_ready=(False, False))
        assert deq_full.observed[P.p_writeToSbuffer_req_0_valid]
    elif phase == "uncache":
        await agent.step()
        await agent.step()
        assert agent.pending[0] == "io"
    else:
        for _ in range(3):
            await agent.step(cache_response=False)
        assert agent.pending[0] == "cache" and deq_full.observed[P.p_toDCache_resp_ready]
        if phase == "wb":
            await agent.step(writeback_ready=False)
            assert deq_full.observed[P.p_writeBack_valid]
    assert await agent.reset() == [old]
    new = agent.add(store(0x68000, tag=71))
    await agent.drain()
    assert new != old and old not in agent.completed and old in agent.aborted
    agent.checked(("DEQ-RESET.active" if phase == "queue" else "DEQ-RESET.waiting",), [new])


@pytest.mark.parametrize("denied,corrupt", ((False, False), (True, False), (False, True), (True, True)))
async def test_full_response_faults_and_identity_at_immediate_wb_fire(deq_full, denied, corrupt):
    agent = PsqAgent(deq_full, base=191)
    uid = agent.add(store((1 << 49) + 0x78940, cache_operation=True, cbo=2, hyper=True), rob=RobPtr.encode(319, former=False))
    for _ in range(3):
        await agent.step(cache_response=False)
    await agent.step(cache_denied=denied, cache_corrupt=corrupt)
    wb = await agent.step()
    assert wb["wb_uid"] == uid
    await agent.drain()
    agent.checked(("DEQ-EXCEPTION.response", "DEQ-EXCEPTION.identity"), [uid])


@pytest.mark.parametrize("denied,corrupt", ((True, False), (False, True), (True, True)))
async def test_full_reference_keeps_response_errors_during_wb_stall(deq_full, denied, corrupt):
    agent = PsqAgent(deq_full)
    agent.add(store(cache_operation=True, cbo=1))
    for _ in range(3):
        await agent.step(cache_response=False)
    await agent.step(cache_denied=denied, cache_corrupt=corrupt, writeback_ready=False)
    deq_full.coverage.sample(("DEQ-EXCEPTION.held",), deq_full.last_tick)
    for _ in range(3):
        await agent.step(writeback_ready=False)
    await agent.drain()
    agent.checked(("DEQ-EXCEPTION.held",), [1])


@pytest.mark.parametrize("seed", (0xD301, 0xD302, 0xD303, 0xD304))
@pytest.mark.parametrize("allow_zero", (True, False), ids=("full-domain", "nonzero-cbo-control"))
async def test_full_seeded_mixed_traffic_and_fair_drain(deq_full, seed, allow_zero):
    rng = random.Random(seed)
    agent = PsqAgent(deq_full, base=61)
    target = 400
    uids = []
    reached = False
    for _ in range(64):
        uids.append(agent.add(store(0x80000 + len(uids) * 32, tag=len(uids) + 1)))
    for _ in range(4000):
        for _ in range(rng.randrange(3)):
            if agent.tail - agent.head == 64 or len(uids) == target:
                break
            choice = rng.randrange(10)
            tag = len(uids) + 1
            va = 0x100000 + tag * 8192
            size = rng.choice((1, 2, 4, 8, 16))
            page = None
            if choice == 0:
                item = Store(inactive=True, committed=True)
            elif choice == 1:
                cbo = rng.randrange(4 if allow_zero else 3)
                item = store(va, 16, tag=tag, cache_operation=True, cbo=cbo)
                if cbo == 3:
                    item = replace(item, data=0)
            elif choice < 4:
                size = min(size, 8)
                item = store(va + rng.randrange(8 // size) * size + rng.choice((0, 8)), size, tag=tag, memory_type=rng.choice((1, 5, 2, 7)))
            else:
                offset = rng.choice((rng.randrange(16), 60, 4092))
                item = store(va + offset, size, tag=tag)
                if offset == 4092 and size > 4:
                    page = (0xD000 + tag) * 4096
            uids.append(agent.add(item, rob=RobPtr.encode(tag % 320, former=bool(tag % 2)), second_page=page))
        r0 = rng.random() < 0.7
        change = await agent.step(sbuffer_ready=(r0, r0 and rng.random() < 0.65), uncache_ready=rng.random() < 0.7,
                         cache_ready=rng.random() < 0.7, writeback_ready=rng.random() < 0.6, sbuffer_empty=rng.random() < 0.65,
                         cache_response=rng.random() < 0.5 if agent.pending and agent.pending[0] == "cache" else False,
                         uncache_response=rng.random() < 0.5 if agent.pending and agent.pending[0] == "io" else False,
                          uncache_ack_valid=rng.random() < 0.5 if agent.pending and agent.pending[0] == "nc" else False)
        if not reached and change["read_uids"]:
            deq_full.coverage.sample(("DEQ-CONCURRENT.seeded" if allow_zero else "DEQ-CONCURRENT.controlled",), deq_full.last_tick)
            reached = True
        if len(uids) == target:
            break
    assert len(uids) == target
    await agent.drain(limit=1000)
    assert len(agent.completed) == target and not agent.aborted
    agent.checked(("DEQ-CONCURRENT.seeded" if allow_zero else "DEQ-CONCURRENT.controlled", "DEQ-IDENTITY.flags", "DEQ-CACHE.two"), uids)


async def test_full_virtual_occupancy_all_129_values_and_force_write(deq_full):
    # More than 64 virtual entries can wait while only 64 physical entries are
    # resident. No unallocated rdata payload is granted committed permission.
    counts = (0, 59, 60, 128, 59, 55, 54, 55, *range(129), *range(128, -1, -1))
    force = False
    for count in counts:
        force = count >= 60 or count >= 55 and force
        await deq_full.cycle(Inputs(valid_count=count))
        assert deq_full.observed[P.p_sbufferCtrl_req_forceWrite] == int(force)
        assert not deq_full.observed[P.p_rdataPtrMoveCnt] and not deq_full.observed[P.p_sqDeqCnt]
    names = ("DEQ-DRAIN.force_write", "DEQ-IDLE.disabled", "DEQ-RESET.initial")
    deq_full.coverage.sample(names, deq_full.last_tick)
    deq_full.coverage.sample(names, deq_full.last_tick, checked=True)


@pytest.mark.parametrize("next_cbo", (0, 1, 2, 3))
@pytest.mark.parametrize("committed", (False, True))
async def test_split_second_segment_must_not_inherit_neighbor_zero_wline(deq_full, next_cbo, committed):
    agent = PsqAgent(deq_full)
    first = agent.add(store(0x9400C, 8))
    second = agent.add(replace(store(0x95000, 16, cache_operation=True, cbo=next_cbo), data=0, committed=committed))
    try:
        await agent.step(sbuffer_ready=(False, False))
    finally:
        if next_cbo == 3 and deq_full.observed[P.p_writeToSbuffer_req_1_valid]:
            deq_full.coverage.sample(("DEQ-SPLIT.zero_neighbor",), deq_full.last_tick)
    # Controls still have to drain both owners; not "passed at enqueue".
    if committed:
        await agent.drain(limit=30)
    else:
        await _finish_uncommitted_neighbor(agent, second)
    assert first in agent.completed and second in agent.completed


async def _finish_uncommitted_neighbor(agent, uid):
    for owner in agent.owners.values():
        if owner.uid == uid:
            owner.store = replace(owner.store, committed=True)
            agent.emit("permission", uid=uid, committed=True, tick=agent.env.last_tick)
    await agent.drain()


@pytest.mark.parametrize("va", (0xA003C, 0xA0FFC))
async def test_split_followed_by_inactive_moves_one_sq_read_position(deq_full, va):
    agent = PsqAgent(deq_full)
    first = agent.add(store(va, 8), second_page=0xD012000 if va % 4096 == 4092 else None)
    second = agent.add(Store(committed=True, inactive=True))
    accepted = await agent.step(sbuffer_ready=(False, False))
    assert accepted["read_after"] == 1
    await agent.drain()
    agent.checked(("DEQ-CREDIT.split", "DEQ-INACTIVE.mixed"), [first, second])
