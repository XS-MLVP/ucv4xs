
from dataclasses import asdict, replace
import hashlib

import pytest

from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import Address
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import Data
from suites.memblock.lsq.testbenches.psq.transactions import SecondPage
from suites.memblock.lsq.testbenches.raw.transactions import SqPtr
from suites.memblock.lsq.testbenches.store_queue.model.store_payload import add_digest
from suites.memblock.lsq.testbenches.unalign.model.uq_page_pairs import BASES
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.public import check_first_word
from suites.memblock.lsq.testbenches.unalign.model.uq_page_pairs import record
from suites.memblock.lsq.testbenches.unalign.model.uq_page_pairs import save
from suites.memblock.lsq.testbenches.unalign.model.uq_page_pairs import second_pa
from suites.memblock.lsq.testbenches.vlq.transactions import RobPtr
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.memory_owners import MemoryOwners
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.memory_owners import StoreOwner
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.memory_owners import cached_load


@pytest.mark.parametrize("lane", range(3))
async def test_real_cross_page_pair_high_low_PA_original_Loads_and_Store_fragments(lsq, tmp_path, lane):
    trace, profiles, stream, program, load_position = MemoryOwners(lsq), [], hashlib.sha256(), 10, 0
    for profile, base in enumerate(BASES):
        trace.base = replace(trace.base, pending=RobPtr.encode(program - 1), pending_next=RobPtr.encode(program - 1), sbuffer_ready=(False, False))
        fillers = [StoreOwner(pos, RobPtr.encode(program + offset), 0x600000 + pos * 32,
                             0xB000000 + pos * 32, value=0x1020304050607000 + pos)
                   for offset, pos in enumerate(range(trace.sq_head, base))]
        if fillers:
            await trace.dispatch(stores=fillers)
            program += len(fillers)
            await trace.write_all(owner.position for owner in fillers)
            await trace.finish(pending=RobPtr.encode(program))
        assert trace.sq_head == base
        trace.base = replace(trace.base, pending=RobPtr.encode(program - 1), pending_next=RobPtr.encode(program - 1), sbuffer_ready=(False, False))
        stores, loads = [], []
        for index in range(2):
            va, pa, value = record(profile, index)
            store = StoreOwner(base + index, RobPtr.encode(program), va, pa, size=3, value=value, second_page=second_pa(profile, index))
            load = cached_load(load_position, program + 1, base + index + 1, va, pa, size=2)
            await trace.dispatch(stores=[store]); await trace.dispatch(loads=[load])
            stores.append(store); loads.append(load)
            program += 2; load_position += 1
        for index, store in enumerate(stores):
            await trace.cycle(addresses=tuple(store.address() if source == index else Address() for source in range(2)),
                              data=tuple(store.data() if source == 1 - index else Data() for source in range(2)))
        handshakes = []
        for index, store in enumerate(stores):
            req = SecondPage(True, SqPtr.encode(store.position), store.second_page)
            for _ in range(30):
                await trace.cycle(second_pages=tuple(req if source == index else SecondPage() for source in range(2)))
                if lsq.pre_response.unalign_ready[index]:
                    break
            else:
                raise AssertionError("actual Wrapper UQ page handshake missing")
            event = dict(position=store.position, lane=index, sq=asdict(req.sq), paddr=store.second_page)
            handshakes.append(event); add_digest(stream, ["actual_page_fire", profile, event])
            await trace.cycle(addresses=tuple(store.address(tail=True) if source == index else Address() for source in range(2)))
            await trace.idle(4)
        assert trace.sq_head == base and all(not trace.stores[store.position]["consumed"] for store in stores)
        for index, load in enumerate(loads):
            response = await trace.forward(load, lane)
            check_first_word(response, record(profile, index)[2])
            add_digest(stream, ["actual_first_word_forward", profile, lane, index, record(profile, index)])
        await trace.execute(loads)
        await trace.finish(pending=RobPtr.encode(program))
        assert trace.sq_head == base + 2 and all(trace.stores[store.position]["completed"] for store in stores)
        assert all(trace.active_loads[load.execution.uop.lq]["completed"] for load in loads)
        profiles.append(dict(profile=profile, head_before=base, head_after=base + 2, fillers_completed=len(fillers),
            page_handshakes=handshakes, no_Sbuffer_consumption_before_permission=True,
            cross_page_store_completions=2, actual_Sbuffer_fragments=4, actual_Load_completions=2, query_lane=lane))
        for store in stores:
            add_digest(stream, ["real_two_part_store_complete", store.position, trace.stores[store.position]["last_fire"]])
    assert len(trace.stores) == 256 and len(trace.loads) == trace.load_released == 16
    assert len(trace.fragments_fired) == 272 and not trace.cancelled
    lsq.prove("LSQ-FORWARD.page", "LSQ-FORWARD.sqid", "LSQ-FORWARD.wrap")
    save(tmp_path / "uq-page-pairs-witness.json", "lsq_wrapper", profiles, stream,
         query_lane=lane, completed_store_uids=256, cross_page_store_uids=16, completed_Load_uids=16,
         actual_Sbuffer_fragments=272, scope="real Wrapper Store/Load dispatch, page fire and tail STA, first-word Forward, original Load S3 and both real Store fragments; no hidden/model reads or between-profile reset")
