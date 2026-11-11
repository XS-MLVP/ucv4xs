"""Gap supplement: actual one-sided shared-bus lifecycles before competition."""

from dataclasses import asdict, replace

import pytest

from suites.memblock.lsq.testbenches.lsq_wrapper.tests.public import obs, uncache, exception, lane_bypass
from suites.memblock.lsq.testbenches.load_queue.transactions import Bypass
from suites.memblock.lsq.testbenches.load_queue.transactions import Load
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import Address
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import Bus
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import Data
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import Dispatch
from suites.memblock.lsq.testbenches.lsq_wrapper.transactions import Inputs
from suites.memblock.lsq.testbenches.psq.transactions import Attributes
from suites.memblock.lsq.testbenches.raw.transactions import SqPtr
from suites.memblock.lsq.testbenches.replay.transactions import Enqueue
from suites.memblock.lsq.testbenches.replay.transactions import Uop
from suites.memblock.lsq.testbenches.vlq.transactions import QueuePtr
from suites.memblock.lsq.testbenches.vlq.transactions import RobPtr


class BusTrace:
    def __init__(self, env, *, to_load, nc, lane, fault=False, outstanding=False):
        self.env, self.to_load, self.nc, self.lane, self.fault = env, to_load, nc, lane, fault
        self.base = Inputs(pending=RobPtr.encode(0), pending_next=RobPtr.encode(0),
                           bus=Bus(outstanding=outstanding), writeback_ready=True, sbuffer_ready=(True, True))
        self.requests = self.acks = self.responses = self.wb = self.deq = 0
        self.address = 0xA0100080 if to_load else 0xB0200080
        self.value = 0x9988776655443322 if to_load else 0x8877665544332211

    def bus(self, **fields):
        return replace(self.base, bus=replace(self.base.bus, ack_to_load=self.to_load, response_to_load=self.to_load, **fields))

    async def cycle(self, packet=None):
        packet = packet or self.base
        await self.env.cycle(packet)
        pre, post, tick = self.env.pre_response, self.env.response, self.env.last_tick
        if pre.uncache_request is not None and packet.bus.ready:
            self.requests += 1
            assert self.requests == 1
            self.env.expect(obs(uncache_request=uncache(cmd=int(not self.to_load), addr=self.address,
                vaddr=0x1080, mask=255, nc=int(self.nc), rob_value=0)),
                            "original public UID accepted by shared bus", before=True)
            if not self.to_load:
                self.env.expect(obs(uncache_request=uncache(data=self.value)), "original Store bytes on shared bus", before=True)
            self.env.emit("bus_fire", to_load=self.to_load, nc=self.nc, mid=pre.uncache_request.ident)
        if packet.bus.ack:
            self.acks += 1
            assert self.acks == 1 and self.requests == 1
        if packet.bus.response:
            self.responses += 1
            assert self.responses == self.acks == 1
        if pre.mmio_stout is not None and packet.writeback_ready:
            self.wb += 1
            assert not self.to_load and not self.nc and self.wb == 1
            self.env.emit("store_writeback", rob=0)
        assert not any(word is not None and packet.sbuffer_ready[lane]
                       for lane, word in enumerate((pre.sbuffer_word_0, pre.sbuffer_word_1)))
        credit = post.lq_dequeue if self.to_load else post.sq_dequeue
        if credit.valid:
            self.deq += credit.count
            assert self.deq == 1 and self.responses == 1 if self.to_load or not self.nc else self.deq == 1 and self.acks == 1
            self.env.emit("bus_owner_complete", to_load=self.to_load, nc=self.nc)

    async def transfer(self):
        for _ in range(60):
            if self.env.response.uncache_request is not None:
                break
            await self.cycle()
        assert self.env.response.uncache_request is not None
        mid = self.env.response.uncache_request.ident
        for _ in range(3):
            await self.cycle()
            assert self.env.response.uncache_request is not None and self.env.response.uncache_request.ident == mid
        await self.cycle(self.bus(ready=True))
        await self.cycle(self.bus(ack=True, mid=mid, sid=7))
        for _ in range(3):
            await self.cycle()
        await self.cycle(self.bus(response=True, response_id=7, data=self.value, error=self.fault, nderr=self.fault))

    async def finish(self):
        self.base = replace(self.base, pending=RobPtr.encode(1), pending_next=RobPtr.encode(1))
        for _ in range(80):
            await self.cycle()
            if self.deq == 1 and self.env.response.lq_empty and self.env.response.sq_empty:
                for _ in range(6):
                    await self.cycle()
                assert self.requests == self.acks == self.responses == 1
                assert self.wb == int(not self.to_load and not self.nc)
                assert not self.env.response.replay_allocate and self.env.response.uncache_request is None
                return
        raise AssertionError("real shared bus owner did not complete its original obligations")


@pytest.mark.parametrize("nc", (False, True), ids=("mmio", "nc"))
@pytest.mark.parametrize("fault", (False, True))
async def test_real_load_bus_response_internal_wake_bypass_and_final_s3(lsq, nc, fault):
    trace = BusTrace(lsq, to_load=True, nc=nc, lane=2, fault=fault, outstanding=nc)
    request = Dispatch(True, 1, RobPtr.encode(0), 1)
    load = Load(Enqueue(True, Uop(rob=RobPtr.encode(0), lq=QueuePtr(), sq=SqPtr(), operation=6),
                        vaddr=0x1080, mask=255, nc=nc, need_replay=True, causes=1),
                fullva=0xABC01080, paddr=trace.address, mmio=not nc, update_address=True)
    lsq.emit("allocate_bus_owner", to_load=True, load=asdict(load), dispatch=asdict(request), fault=fault)
    await trace.cycle(replace(trace.base, dispatch=(request,) + (Dispatch(),) * 7))
    await trace.cycle(replace(trace.base, loads=(load, Load(), Load())))
    await trace.transfer()
    for _ in range(60):
        if lsq.response.replays[0].valid:
            break
        await trace.cycle()
    assert lsq.response.replays[0].valid
    slot = lsq.response.replays[0].replay_queue_idx
    await trace.cycle(replace(trace.base, replay_ready=(True, True, True)))
    queries = (Bypass(), Bypass(), Bypass(True, QueuePtr(), nc, not nc))
    await trace.cycle(replace(trace.base, bypass=queries))
    lsq.expect(obs(bypass=lane_bypass(2, s1_valid=1, s1_paddr=trace.address),
        ld_exception=exception(valid=1, vaddr=load.fullva, bus_error=int(fault), access_fault=int(fault))),
               "same original Load owner address and fault report after shared response")
    await trace.cycle()
    lsq.expect(obs(bypass=lane_bypass(2, s2_valid=1, s2_data=trace.value * ((1 << 64) + 1),
        s2_derr=int(fault), s2_nderr=int(fault))),
               "same original shared response bytes/errors at actual s2")
    feedback = replace(load, execution=replace(load.execution, replay_feedback=True, slot=slot, need_replay=False, causes=0))
    await trace.cycle(replace(trace.base, loads=(feedback, Load(), Load())))
    await trace.finish()
    lsq.prove("LSQ-BUS.load_only", "LSQ-EXCEPTION.load_fault" if fault else "LSQ-EXCEPTION.load_clean")


@pytest.mark.parametrize("nc", (False, True), ids=("io", "nc"))
@pytest.mark.parametrize("lane", range(2))
async def test_real_store_bus_direction_ack_response_writeback_and_sq_release(lsq, nc, lane):
    trace = BusTrace(lsq, to_load=False, nc=nc, lane=lane, outstanding=nc)
    request = Dispatch(True, 2, RobPtr.encode(0), 1, store_end=SqPtr.encode(1))
    address = Address(True, 0, 6, 0x1080, trace.address, 3, rob=RobPtr.encode(0), mask=255)
    data = Data(True, SqPtr(), 6, trace.value)
    lsq.emit("allocate_bus_owner", to_load=False, address=asdict(address), data=asdict(data), dispatch=asdict(request), nc=nc)
    await trace.cycle(replace(trace.base, dispatch=(request,) + (Dispatch(),) * 7))
    addresses, values = [Address(), Address()], [Data(), Data()]
    addresses[lane], values[lane] = address, data
    await trace.cycle(replace(trace.base, addresses=tuple(addresses), data=tuple(values)))
    attrs = [Attributes(), Attributes()]
    attrs[lane] = Attributes(nc=nc, mmio=not nc)
    await trace.cycle(replace(trace.base, attributes=tuple(attrs)))
    await trace.transfer()
    await trace.finish()
    lsq.prove("LSQ-BUS.store_only", "LSQ-RETIRE.nc" if nc else "LSQ-RETIRE.io")
