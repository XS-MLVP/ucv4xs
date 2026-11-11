
from dataclasses import asdict, replace
import hashlib

from suites.memblock.lsq.testbenches.store_queue.model.store_payload import add_digest
from suites.memblock.lsq.testbenches.vlq.transactions import RobPtr
from suites.memblock.lsq.testbenches.vsq.model.vsq_retire_known import PROFILES
from suites.memblock.lsq.testbenches.vsq.model.vsq_retire_known import save
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.memory_owners import MemoryOwners
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.memory_owners import StoreOwner
from suites.memblock.lsq.testbenches.lsq_wrapper.tests.memory_owners import cached_load


async def test_known_64_then_small_multi_flow_batches_with_original_Loads(lsq, tmp_path):
    trace, profiles, stream, program = MemoryOwners(lsq), [], hashlib.sha256(), 10
    for phase, (count, flows) in enumerate(PROFILES):
        base = trace.sq_head
        hold = RobPtr.encode(program - 1)
        trace.base = replace(trace.base, pending=hold, pending_next=hold, sbuffer_ready=(False, False))
        stores = [StoreOwner(base + index, RobPtr.encode(program + index // flows),
                             0x800000 + (base + index) * 64, 0xD000000 + (base + index) * 64,
                             value=0x1020304050000000 | (base + index) * 0x101)
                  for index in range(count * flows)]
        load = cached_load(phase, program + count, base + len(stores), stores[-1].vaddr, stores[-1].paddr)
        await trace.dispatch(stores=stores, loads=[load])
        await trace.write_all(item.position for item in stores)
        uids = [trace.stores[item.position]["uid"] for item in stores]
        assert trace.sq_head == base and all(not trace.stores[item.position]["consumed"] for item in stores)
        response = await trace.forward(load, phase % 3)
        assert response.valid == 1 and not any((response.forward_invalid,response.match_invalid,
            response.addr_invalid,response.data_invalid)),("retire-known-width-original-Load-bytes",response)
        assert response.forward_mask == 0xFF,("retire-known-width-original-Load-bytes",response)
        for byte in range(8):
            assert response.forward_data >> (8*byte) & 255 == stores[-1].value >> (8*byte) & 255,("retire-known-width-original-Load-bytes",byte,response)
        await trace.execute([load]); await trace.idle(8)
        assert trace.active_loads[load.execution.uop.lq]["completed"]
        boundary = RobPtr.encode(program + count)
        ready_tick = lsq.last_tick
        trace.base = replace(trace.base, pending=boundary, pending_next=boundary)
        await trace.idle(10)
        assert not lsq.response.sq_empty and trace.sq_head == base
        assert all(not trace.stores[item.position]["consumed"] for item in stores)
        await trace.finish(pending=boundary)
        assert all(trace.stores[item.position]["completed"] and trace.stores[item.position]["consumed"] == {0} for item in stores)
        item = dict(phase=phase, physical_base=base, virtual_uops=count, flows_per_uop=flows,
                    batch_physical_flows=count * flows, normal_uids=uids, actual_completed_uids=uids,
                    actual_physical_tail=trace.sq_head, retirement_ROB_boundary=asdict(boundary),
                    allocated_virtual_uops=[dict(rob=asdict(RobPtr.encode(program + index)), flows=flows,
                                                 physical_end=base + (index + 1) * flows) for index in range(count)],
                    all_S2_STD_ready_before_permit_tick=ready_tick,
                    zero_consumed_fragments_before_permission=True, actual_Sbuffer_fragments=len(uids),
                    original_Load_uid=trace.active_loads[load.execution.uop.lq]["uid"],
                    original_Load_S3_completed=True, original_Load_PA_bytes_checked=True)
        profiles.append(item); add_digest(stream, item)
        for store in stores:
            state = trace.stores[store.position]
            add_digest(stream, ["actual_original_bytes_fire_then_dequeue", state["uid"], store.position, state["last_fire"]])
        program += count + 1
    assert trace.sq_head == len(trace.stores) == len(trace.fragments_fired) == 82
    assert trace.load_released == 4 and not trace.cancelled
    lsq.prove("LSQ-ALLOC.multi_flow", "LSQ-RETIRE.multi_flow", "LSQ-FORWARD.aligned")
    save(tmp_path / "vsq-retire-known-width-witness.json", "lsq_wrapper", profiles, stream,
         normal_virtual_uops=18, normal_physical_flows=82, actual_Sbuffer_fragments=82,
         normal_Load_uids=4, resets_between_profiles=0, cancelled_uids=0)
