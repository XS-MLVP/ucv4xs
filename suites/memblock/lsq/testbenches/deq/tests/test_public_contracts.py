"""Small semantic oracles, deliberately independent of the existing models."""

from dataclasses import replace

import pytest

from suites.memblock.lsq.testbenches.deq.env.ports import decode_observation
from suites.memblock.lsq.testbenches.deq.transactions import Inputs as DeqInputs
from suites.memblock.lsq.testbenches.deq.transactions import Store
from suites.memblock.lsq.testbenches.deq.transactions import encode as deq_encode


@pytest.mark.parametrize("review_dut", ["deq_module"], indirect=True)
@pytest.mark.parametrize("stall", (0, 3))
@pytest.mark.parametrize("denied,corrupt", ((True, False), (False, True), (True, True)))
async def test_CBO_fault_belongs_to_actual_writeback_fire(review_dut, stall, denied, corrupt):
    e = review_dut
    e.metadata = dict(issue="DEQ-WB-001", stall=stall, denied=denied, corrupt=corrupt,
        domain="Committed CBO Deq public interface; full Backend arbitration reachability is separate")
    owner = Store(vaddr=0x12340, page=0xABC, byte_mask=15, data=0x11223344,
        data_valid=True, address_valid=True, committed=True, cache_operation=True, cbo=0)
    packet = DeqInputs(stores=(owner, Store()), valid_count=1)

    async def cycle(**changes):
        await e.step(deq_encode(replace(packet, **changes)))

    await cycle()
    for _ in range(30):
        if e.snapshot(decode_observation).cache_request is not None:
            break
        await cycle()
    e.check("Cache request offered", int(e.snapshot(decode_observation).cache_request is not None), 1)
    await cycle(cache_ready=True)
    e.check("Cache request actual fire", int(e.snapshot(decode_observation, before=True).cache_request is not None), 1)
    e.check("original CBO PA", e.snapshot(decode_observation, before=True).cache_request.address, owner.paddr)
    e.event("Cache_request_fire", uid=1, PA=owner.paddr, CBO_operation=0, committed=True)
    await cycle(cache_response=True, cache_denied=denied, cache_corrupt=corrupt)
    e.check("Cache response actual fire", int(e.snapshot(decode_observation, before=True).cache_response_ready), 1)
    e.event("Cache_response_fire", uid=1, denied=denied, corrupt=corrupt, writeback_ready=False)
    wanted = dict(valid=1, denied=int(denied), corrupt=int(corrupt))

    def payload(snapshot):
        writeback = snapshot.writeback
        return dict(valid=int(writeback is not None), denied=writeback.access_fault if writeback else None,
                    corrupt=writeback.bus_error if writeback else None)

    e.check("first defined WB error", payload(e.snapshot(decode_observation)), wanted)
    for index in range(stall):
        await cycle()
        e.event("held_writeback", index=index, ready=False, **payload(e.snapshot(decode_observation)))
        e.check("valid WB payload stable under backpressure", payload(e.snapshot(decode_observation)), wanted, fatal=False)
    await cycle(writeback_ready=True)
    e.event("WB_actual_fire", uid=1, ready=True, **payload(e.snapshot(decode_observation, before=True)))
    e.check("WB actual fire remains valid", int(e.snapshot(decode_observation, before=True).writeback is not None), 1)
    e.check("accepted original errors reach WB fire", payload(e.snapshot(decode_observation, before=True)), wanted, fatal=False)
    await e.step(deq_encode(DeqInputs()))
    e.finish()
