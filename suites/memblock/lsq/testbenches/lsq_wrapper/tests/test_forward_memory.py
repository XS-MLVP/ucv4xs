"""Real Store bank to dispatched Load queries, then actual byte/UID completion."""

from dataclasses import replace

import pytest

from suites.memblock.lsq.testbenches.lsq_wrapper import transactions as responses
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.public import lane_forward, obs
from suites.memblock.lsq.testbenches.forward.transactions import Query
from suites.memblock.lsq.testbenches.replay.transactions import Cause
from suites.memblock.lsq.testbenches.vlq.transactions import RobPtr
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.memory_owners import MemoryOwners
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.memory_owners import StoreOwner
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.memory_owners import cached_load


def check_bytes(env, load, stores, lane):
    """Independent immutable PA-byte map, not ForwardModel selection/masks."""
    memory = {}
    for store in stores:
        for _, pa, mask, value in store.words():
            for byte in range(16):
                if mask >> byte & 1:
                    memory[pa + byte] = value >> (8 * byte) & 255
    expected_mask, expected_data = 0, 0
    start = load.execution.vaddr % 16
    size = (load.execution.uop.operation >> 1) & 7
    for byte in range(16):
        address = load.paddr // 16 * 16 + byte
        forwarded = start <= byte < start + (1 << min(size, 4)) and address in memory
        expected_mask |= int(forwarded) << byte
        if forwarded:
            expected_data |= memory[address] << (8 * byte)
    env.expect(obs(forward=lane_forward(lane, valid=1, forward_invalid=0, match_invalid=0,
        addr_invalid=0, data_invalid=0, forward_mask=expected_mask,
        forward_data=expected_data if expected_mask else None)),
        "youngest original physical Store bytes, no fake replay/dependency")


@pytest.mark.parametrize("lane", range(3))
@pytest.mark.parametrize("variant", ("aligned", "youngest", "address_hole", "data_hole", "kill"))
async def test_real_store_readiness_youngest_bytes_and_kill_before_original_load_completion(lsq, lane, variant):
    trace = MemoryOwners(lsq)
    count = 1 if variant in ("aligned", "kill") else 2
    stores = tuple(StoreOwner(pos, RobPtr.encode(10 + pos), 0x11000, 0xA011000,
                              value=0x1122334455667788 if pos == 0 else 0x99AABBCCDDEEFF00) for pos in range(count))
    load = cached_load(0, 10 + count, count, 0x11000, 0xA011000)
    if variant == "address_hole":
        load = replace(load, execution=replace(load.execution, uop=replace(load.execution.uop, load_wait=True, wait_sq=stores[1].data().sq)))
    await trace.dispatch(stores, [load])
    await trace.write(0)
    if count == 2:
        await trace.write(1, lane=1, address=variant != "address_hole", data=variant != "data_hole")
    await trace.idle(5)
    if variant == "address_hole":
        query = Query(True, load.execution.vaddr, load.execution.uop.sq, 3, wait=True, wait_sq=stores[1].data().sq)
        await trace.forward(load, lane, query=query)
        lsq.expect(obs(forward=lane_forward(lane, valid=1, addr_invalid=1,
            addr_invalid_ptr=responses.SqPointerExpectation(value=1))), "missing real STA blocks original dependent Load")
        lsq.reach("LSQ-FORWARD.addr_hole")
        await trace.write(1, address=True, data=False)
        await trace.idle(5)
    elif variant == "data_hole":
        await trace.forward(load, lane)
        lsq.expect(obs(forward=lane_forward(lane, valid=1, data_invalid=1, data_invalid_value=1)),
            "youngest matching real Store without STD cannot fall back to older bytes")
        lsq.reach("LSQ-FORWARD.data_hole", "LSQ-FORWARD.late_std")
        await trace.write(1, address=False, data=True)
        await trace.idle(5)
    elif variant == "kill":
        await trace.forward(load, lane, kill=True)
        lsq.expect(obs(forward=lane_forward(lane, valid=0)), "killed translated Load has no forward response")
        lsq.reach("LSQ-FORWARD.kill")
    await trace.forward(load, lane)
    check_bytes(lsq, load, stores, lane)
    await trace.finish()
    names = ["LSQ-FORWARD.aligned"]
    if count == 2:
        names.append("LSQ-FORWARD.youngest")
    names += {"address_hole": ["LSQ-FORWARD.addr_hole"], "data_hole": ["LSQ-FORWARD.data_hole", "LSQ-FORWARD.late_std"],
              "kill": ["LSQ-FORWARD.kill"]}.get(variant, [])
    lsq.prove(*names)


@pytest.mark.parametrize("lane", range(3))
@pytest.mark.parametrize("alias", (False, True), ids=("same-va-control", "different-va-alias"))
async def test_cross_word_youngest_pa_alias_must_not_return_old_store_bytes(lsq, lane, alias):
    trace = MemoryOwners(lsq)
    old = StoreOwner(0, RobPtr.encode(10), 0x10010, 0xABC010, 2, 0x11111111)
    young = StoreOwner(1, RobPtr.encode(11), 0x2000C if alias else 0x1000C, 0xABC00C, 3, 0x2222222222222222)
    load = cached_load(0, 12, 2, 0x10010, 0xABC010, size=2)
    await trace.dispatch([old, young], [load])
    await trace.write_all()
    lsq.reach("LSQ-FORWARD.alias")
    await trace.forward(load, lane)
    if alias:
        check_bytes(lsq, load, [old, young], lane)
    else:
        # Both VA candidates overlap this following-word query. The fixed
        # implementation conservatively requires multi-match replay; that is
        # a legal block, not a promise of immediate safe forwarding. It must
        # then actually wake via real SQ empty, retain its slot and complete.
        lsq.expect(obs(forward=lane_forward(lane, valid=1, forward_invalid=1)),
                   "same-VA multi-match control is safely blocked rather than returning an unqualified old byte")
        replay = replace(load, execution=replace(load.execution, need_replay=True, causes=1 << Cause.STORE_MULTI_MATCH))
        await trace.execute([replay])
        trace.base = replace(trace.base, pending=RobPtr.encode(12), pending_next=RobPtr.encode(12), sbuffer_ready=(True, True))
        for _ in range(70):
            await trace.cycle()
            if all(state["completed"] for state in trace.stores.values()):
                break
        assert all(state["completed"] for state in trace.stores.values())
        await trace.forward(load, lane)
        check_bytes(lsq, load, [], lane)
        await trace.replay_complete(replay)
    await trace.finish()
    lsq.prove("LSQ-FORWARD.alias")


@pytest.mark.parametrize("lane", range(3))
@pytest.mark.parametrize("word", (0, 1))
@pytest.mark.parametrize("whole_word", (False, True), ids=("written-byte-control", "whole-word-range"))
async def test_cross_word_forward_never_invents_unwritten_physical_bytes(lsq, lane, word, whole_word):
    trace = MemoryOwners(lsq)
    store = StoreOwner(0, RobPtr.encode(10), 0x1000C, 0xABC00C, 3, 0x8877665544332211)
    offset = word * 16 + (0 if whole_word or word else 12)
    load = cached_load(0, 11, 1, 0x10000 + offset, 0xABC000 + offset, size=4 if whole_word else 2)
    await trace.dispatch([store], [load])
    await trace.write_all()
    lsq.reach("LSQ-FORWARD.range")
    await trace.forward(load, lane)
    check_bytes(lsq, load, [store], lane)
    await trace.finish()
    lsq.prove("LSQ-FORWARD.range")


@pytest.mark.parametrize("lane", range(3))
@pytest.mark.parametrize("clipped", (False, True), ids=("within-window-control", "clipped-virtual-dependency"))
async def test_real_nonzero_sq_head_keeps_data_dependency_full_sq_generation(lsq, lane, clipped):
    trace = MemoryOwners(lsq)
    warm = [StoreOwner(pos, RobPtr.encode(10 + pos // 16), 0x80000 + pos * 16,
                       0xA080000 + pos * 16, value=0x1000000000000000 + pos) for pos in range(60)]
    await trace.dispatch(warm)
    await trace.write_all()
    await trace.finish()
    assert trace.sq_head == 60
    trace.base = replace(trace.base, sbuffer_ready=(False, False))
    count = 68 if clipped else 64
    current = [StoreOwner(pos, RobPtr.encode(15 + (pos - 60) // 16), 0x90000 + (pos - 60) * 16,
                          0xB090000 + (pos - 60) * 16, value=0x2000000000000000 + pos) for pos in range(60, 60 + count)]
    source = current[52]  # SQ112/slot48, complete identity0:1:48.
    load = cached_load(0, 20, 60 + count, source.vaddr, source.paddr)
    await trace.dispatch(current, [load])
    await trace.write(source.position, address=True, data=False)
    await trace.idle(5)
    lsq.reach("LSQ-FORWARD.sqid", "LSQ-FORWARD.wrap")
    await trace.forward(load, lane)
    lsq.expect(obs(forward=lane_forward(lane, valid=1, data_invalid=1,
        data_invalid_ptr=responses.SqPointerExpectation(first=0, second=1, value=48))),
               "clipping the age range cannot fabricate the matched Store generation")
    await trace.write_all(range(60, 124))
    await trace.forward(load, lane)
    check_bytes(lsq, load, current, lane)
    if clipped:
        # A repaired DUT must still finish the FULL legal68-flow range, not
        # fail in a helper that tries to issue outside the current64 window.
        trace.base = replace(trace.base, pending=RobPtr.encode(19), pending_next=RobPtr.encode(19), sbuffer_ready=(True, True))
        for _ in range(120):
            await trace.cycle()
            if trace.sq_head == 124:
                break
        assert trace.sq_head == 124
        trace.base = replace(trace.base, sbuffer_ready=(False, False))
        await trace.write_all(range(124, 128))
    await trace.finish()
    lsq.prove("LSQ-FORWARD.sqid", "LSQ-FORWARD.wrap")


@pytest.mark.parametrize("lane", range(3))
async def test_real_unalign_second_page_blocks_forward_then_original_physical_fragments_complete(lsq, lane):
    trace = MemoryOwners(lsq)
    store = StoreOwner(0, RobPtr.encode(10), 0x1FFC, 0xABCFFC, 3, 0x8877665544332211, second_page=0xDEF000)
    load = cached_load(0, 11, 1, 0x2000, 0xDEF000, size=2)
    await trace.dispatch([store], [load])
    await trace.write_all()
    await trace.forward(load, lane)
    lsq.expect(obs(forward=lane_forward(lane, valid=1, forward_invalid=1)),
               "real UQ second-page match requires replay instead of an unsafe first-page forward")
    lsq.reach("LSQ-FORWARD.page")
    trace.base = replace(trace.base, pending=RobPtr.encode(11), pending_next=RobPtr.encode(11), sbuffer_ready=(True, True))
    for _ in range(60):
        await trace.cycle()
        if trace.stores[0]["completed"]:
            break
    assert trace.stores[0]["completed"] and not trace.active_loads[load.execution.uop.lq]["sent"]
    await trace.forward(load, lane)
    check_bytes(lsq, load, [], lane)
    lsq.emit("cache_read_after_prior_store_consumed", lq=0, original_second_page=0xDEF000,
             expected_bytes=0x88776655, boundary="external cached S3 has no retained result-data output")
    await trace.finish()
    lsq.prove("LSQ-FORWARD.page")
