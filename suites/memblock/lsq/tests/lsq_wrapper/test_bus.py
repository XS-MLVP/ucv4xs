"""Gap supplement: actual one-sided shared-bus lifecycles before competition."""

from dataclasses import asdict, replace

import pytest

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.load_queue.types import Bypass, Load
from suites.memblock.lsq.lsq_wrapper.types import Address, Bus, Data, Dispatch, Inputs
from suites.memblock.lsq.psq.types import Attributes
from suites.memblock.lsq.raw.types import SqPtr
from suites.memblock.lsq.replay.types import Enqueue, Uop
from suites.memblock.lsq.vlq.types import QueuePtr, RobPtr


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
        pre, post, tick = self.env.pre_observed, self.env.observed, self.env.last_tick
        if pre[P.p_uncache_req_valid] and packet.bus.ready:
            self.requests += 1
            assert self.requests == 1
            self.env.expect({P.p_uncache_req_bits_cmd: int(not self.to_load), P.p_uncache_req_bits_addr: self.address,
                             P.p_uncache_req_bits_vaddr: 0x1080, P.p_uncache_req_bits_mask: 255,
                             P.p_uncache_req_bits_nc: int(self.nc), P.p_uncache_req_bits_robIdx_value: 0},
                            "original public UID accepted by shared bus", before=True)
            if not self.to_load:
                self.env.expect({P.p_uncache_req_bits_data: self.value}, "original Store bytes on shared bus", before=True)
            self.env.emit("bus_fire", to_load=self.to_load, nc=self.nc, mid=pre[P.p_uncache_req_bits_id])
        if packet.bus.ack:
            self.acks += 1
            assert self.acks == 1 and self.requests == 1
        if packet.bus.response:
            self.responses += 1
            assert self.responses == self.acks == 1
        if pre[P.p_mmioStout_valid] and packet.writeback_ready:
            self.wb += 1
            assert not self.to_load and not self.nc and self.wb == 1
            self.env.emit("store_writeback", rob=0)
        assert not any(pre[P.io(f"sbuffer_req_{lane}_valid")] and packet.sbuffer_ready[lane] for lane in range(2))
        p = P.p_toLsqEnqCtrl_ + ("lqDeq" if self.to_load else "sqDeq")
        if post[p + "_valid"]:
            self.deq += post[p + "_bits"]
            assert self.deq == 1 and self.responses == 1 if self.to_load or not self.nc else self.deq == 1 and self.acks == 1
            self.env.emit("bus_owner_complete", to_load=self.to_load, nc=self.nc)

    async def transfer(self):
        for _ in range(60):
            if self.env.observed[P.p_uncache_req_valid]:
                break
            await self.cycle()
        assert self.env.observed[P.p_uncache_req_valid]
        mid = self.env.observed[P.p_uncache_req_bits_id]
        for _ in range(3):
            await self.cycle()
            assert self.env.observed[P.p_uncache_req_valid] and self.env.observed[P.p_uncache_req_bits_id] == mid
        await self.cycle(self.bus(ready=True))
        await self.cycle(self.bus(ack=True, mid=mid, sid=7))
        for _ in range(3):
            await self.cycle()
        await self.cycle(self.bus(response=True, response_id=7, data=self.value, error=self.fault, nderr=self.fault))

    async def finish(self):
        self.base = replace(self.base, pending=RobPtr.encode(1), pending_next=RobPtr.encode(1))
        for _ in range(80):
            await self.cycle()
            if self.deq == 1 and self.env.observed[P.p_lqEmpty] and self.env.observed[P.p_sqEmpty]:
                for _ in range(6):
                    await self.cycle()
                assert self.requests == self.acks == self.responses == 1
                assert self.wb == int(not self.to_load and not self.nc)
                assert not self.env.observed[P.p_replayAllocate] and not self.env.observed[P.p_uncache_req_valid]
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
        if lsq.observed[P.p_replay_0_valid]:
            break
        await trace.cycle()
    assert lsq.observed[P.p_replay_0_valid]
    slot = lsq.observed[P.p_replay_0_bits_replayQueueIdx]
    await trace.cycle(replace(trace.base, replay_ready=(True, True, True)))
    queries = (Bypass(), Bypass(), Bypass(True, QueuePtr(), nc, not nc))
    await trace.cycle(replace(trace.base, bypass=queries))
    lsq.expect({P.p_bypass_2_s1Resp_valid: 1, P.p_bypass_2_s1Resp_bits_paddr: trace.address,
                P.p_ldExceptionInfo_valid: 1, P.p_ldExceptionInfo_bits_vaddr: load.fullva,
                P.p_ldExceptionInfo_bits_exceptionVec_19: int(fault), P.p_ldExceptionInfo_bits_exceptionVec_5: int(fault)},
               "same original Load owner address and fault report after shared response")
    await trace.cycle()
    lsq.expect({P.p_bypass_2_s2Resp_valid: 1, P.p_bypass_2_s2Resp_bits_data: trace.value * ((1 << 64) + 1),
                P.p_bypass_2_s2Resp_bits_derr: int(fault), P.p_bypass_2_s2Resp_bits_nderr: int(fault)},
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
