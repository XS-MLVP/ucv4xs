"""Two REAL candidate queues, serial exclusion and independent return directions.

Normal traffic never retires an unfinished Load. Explicit boundary tests for
Load-older/tie arbitration are reported separately from normal producer cases.
"""

from dataclasses import asdict, replace

import pytest

from suites.memblock.lsq.testbenches.lsq_wrapper.tests.public import obs, uncache, writeback, lane_replay, lane_bypass, exception
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


def ages(layout, load_older=False):
    older, younger = ((RobPtr.encode(159), RobPtr.encode(160)) if layout == "wrap" else
                      (RobPtr.encode(9), RobPtr.encode(9, former=False)) if layout == "former" else
                      (RobPtr.encode(0), RobPtr.encode(1)))
    if layout == "tie":
        older = younger = RobPtr.encode(0)
    return (older, younger) if load_older else (younger, older)


class MixedBus:
    """Actor uses ONLY actual public transfers and original immutable owners."""
    def __init__(self, env, *, layout="plain", load_older=False, nc_store=True, outstanding=True):
        self.env, self.nc_store, self.outstanding = env, nc_store, outstanding
        self.lrob, self.srob = ages(layout, load_older)
        self.domain = "UNIT-INTERFACE" if load_older or layout == "tie" else "NORMAL-PRODUCER"
        self.base = Inputs(pending=self.srob, pending_next=self.srob, bus=Bus(outstanding=outstanding),
                           writeback_ready=nc_store, sbuffer_ready=(True, True))
        self.address = Address(True, 0, 6, 0x2080, 0xD0400080, 3, rob=self.srob, mask=255)
        self.data = Data(True, SqPtr(), 6, 0x7766554433221100)
        self.load = Load(Enqueue(True, Uop(rob=self.lrob, lq=QueuePtr(), sq=SqPtr.encode(int(not load_older)), operation=6),
                                 vaddr=0x3280, mask=255, nc=True, need_replay=True, causes=1),
                         fullva=0xABC03280, paddr=0xC0300280, update_address=True)
        self.value, self.fault, self.nderr = 0x1021324354657687, True, False
        self.requests, self.acks, self.responses = {}, {}, {}
        self.deq, self.wb, self.data_checked = dict(load=0, store=0), 0, 0

    def bus(self, **fields):
        return replace(self.base, bus=replace(self.base.bus, **fields))

    async def cycle(self, packet=None):
        packet = packet or self.base
        await self.env.cycle(packet)
        pre, post = self.env.pre_response, self.env.response
        bus = packet.bus
        if pre.uncache_request is not None and bus.ready:
            kind = "load" if pre.uncache_request.cmd == 0 else "store"
            assert kind not in self.requests
            rob = self.lrob if kind == "load" else self.srob
            self.env.expect(obs(uncache_request=uncache(cmd=int(kind == "store"),
                addr=self.load.paddr if kind == "load" else self.address.paddr,
                vaddr=self.load.execution.vaddr if kind == "load" else self.address.vaddr,
                mask=255, nc=int(kind == "load" or self.nc_store), rob_flag=int(rob.flag),
                rob_value=rob.value, rob_former=int(rob.former))), "shared request original owner identity", before=True)
            if kind == "store":
                self.env.expect(obs(uncache_request=uncache(data=self.data.data)), "shared write original bytes", before=True)
            self.requests[kind] = pre.uncache_request.ident
            self.env.emit("mixed_bus_fire", kind=kind, mid=self.requests[kind])
        if bus.ack:
            kind = "load" if bus.ack_to_load else "store"
            assert kind in self.requests and kind not in self.acks and bus.mid == self.requests[kind]
            assert not any(sid == bus.sid and owner not in self.responses for owner, sid in self.acks.items())
            self.acks[kind] = bus.sid
        if bus.response:
            kind = "load" if bus.response_to_load else "store"
            assert kind in self.acks and kind not in self.responses and bus.response_id == self.acks[kind]
            self.responses[kind] = self.env.last_tick
        if pre.mmio_stout is not None and packet.writeback_ready:
            assert not self.nc_store and "store" in self.responses and self.wb == 0
            self.env.expect(obs(mmio_stout=writeback(rob_flag=int(self.srob.flag), rob_value=self.srob.value,
                rob_former=int(self.srob.former))), "original IO store actual WB", before=True)
            self.wb += 1
        assert not any(word is not None and packet.sbuffer_ready[lane]
                       for lane,word in enumerate((pre.sbuffer_word_0,pre.sbuffer_word_1)))
        for kind, credit in (("load", post.lq_dequeue), ("store", post.sq_dequeue)):
            if credit.valid:
                self.deq[kind] += credit.count
                assert self.deq[kind] == 1
                if kind == "load":
                    assert self.data_checked == 1 and "load" in self.responses
                elif self.nc_store:
                    assert "store" in self.acks
                else:
                    assert self.wb == 1
                self.env.emit("mixed_owner_complete", kind=kind, external_response_already_returned=kind in self.responses)

    async def allocate(self):
        dispatch = [Dispatch(True, 1, self.lrob, 1), Dispatch(True, 2, self.srob, 1, store_end=SqPtr.encode(1))]
        # Real lane order follows the shared ROB order, except the documented
        # equal-ROB boundary where neither age relation is asserted.
        if self.domain == "NORMAL-PRODUCER":
            dispatch.reverse()
        self.env.emit("allocate_mixed_bus", domain=self.domain, dispatch=[asdict(d) for d in dispatch],
                      load=asdict(self.load), address=asdict(self.address), data=asdict(self.data), nc_store=self.nc_store,
                      load_data=self.value, load_error=self.fault, load_nderr=self.nderr)
        await self.cycle(replace(self.base, dispatch=tuple(dispatch) + (Dispatch(),) * 6))
        await self.cycle(replace(self.base, loads=(self.load, Load(), Load())))
        await self.wait("load")
        # Establish a real held Load request BEFORE the Store becomes ready.
        for _ in range(3):
            await self.cycle()
            self.env.expect(obs(uncache_request=uncache(valid=1, cmd=0)), "original real Load held before competing Store")

    async def issue_store(self):
        await self.cycle(replace(self.base, addresses=(self.address, Address()), data=(Data(), self.data)))
        await self.cycle(replace(self.base, attributes=(Attributes(nc=self.nc_store, mmio=not self.nc_store), Attributes())))
        for _ in range(12):
            await self.cycle()

    async def wait(self, kind):
        for _ in range(70):
            values = self.env.response.uncache_request
            if values is not None and values.cmd == int(kind == "store"):
                return
            await self.cycle()
        raise AssertionError(("real shared request absent", kind, self.requests, self.acks, self.responses))

    async def accept(self, kind):
        await self.wait(kind)
        await self.cycle(self.bus(ready=True))
        assert kind in self.requests

    async def ack(self, kind, sid):
        await self.cycle(self.bus(ack=True, ack_to_load=kind == "load", mid=self.requests[kind], sid=sid))

    async def respond(self, kind):
        await self.cycle(self.bus(response=True, response_to_load=kind == "load", response_id=self.acks[kind],
                                 data=self.value if kind == "load" else 0xFFEEDDCCBBAA0099,
                                 error=self.fault if kind == "load" else False, nderr=self.nderr if kind == "load" else True))

    async def consume_load(self):
        for _ in range(70):
            if self.env.response.replays[0].valid:
                break
            await self.cycle()
        self.env.expect(obs(replays=lane_replay(0, valid=1, rob_idx_flag=int(self.lrob.flag),
            rob_idx_value=self.lrob.value, rob_idx_former=int(self.lrob.former))), "original Load replay after own response")
        slot = self.env.response.replays[0].replay_queue_idx
        await self.cycle(replace(self.base, replay_ready=(True, True, True)))
        await self.cycle(replace(self.base, bypass=(Bypass(), Bypass(True, QueuePtr(), nc=True), Bypass())))
        self.env.expect(obs(bypass=lane_bypass(1, s1_valid=1, s1_paddr=self.load.paddr), ld_exception=exception(
            valid=1, vaddr=self.load.fullva, rob_flag=int(self.lrob.flag), rob_value=self.lrob.value,
            rob_former=int(self.lrob.former), bus_error=int(self.fault), access_fault=int(self.nderr))),
            "Load own exception, not opposite-direction Store response")
        await self.cycle()
        self.env.expect(obs(bypass=lane_bypass(1, s2_valid=1, s2_data=self.value * ((1 << 64) + 1),
            s2_derr=int(self.fault), s2_nderr=int(self.nderr))),
                        "original response Load bytes/errors after mixed direction returns")
        self.data_checked += 1
        feedback = replace(self.load, execution=replace(self.load.execution, replay_feedback=True, slot=slot, need_replay=False, causes=0))
        await self.cycle(replace(self.base, loads=(feedback, Load(), Load())))

    async def finish(self):
        if not self.nc_store:
            for _ in range(30):
                if self.env.response.mmio_stout is not None:
                    break
                await self.cycle()
            self.env.expect(obs(mmio_stout=writeback(valid=1)), "real IO WB held for perf blocked/success distinction")
            for _ in range(4):
                await self.cycle()
                assert self.wb == self.deq["store"] == 0
            self.base = replace(self.base, writeback_ready=True)
            await self.cycle()
            assert self.wb == 1
        last = self.srob if self.domain == "UNIT-INTERFACE" else self.lrob
        end = RobPtr.encode(int(last.flag) * 160 + last.value + 1)
        self.base = replace(self.base, pending=end, pending_next=end)
        for _ in range(90):
            await self.cycle()
            if self.deq == dict(load=1, store=1) and self.env.response.lq_empty and self.env.response.sq_empty:
                for _ in range(8):
                    await self.cycle()
                assert set(self.requests) == set(self.acks) == set(self.responses) == {"load", "store"}
                assert self.wb == int(not self.nc_store)
                assert not self.env.response.replay_allocate and self.env.response.uncache_request is None
                self.env.emit("complete_mixed_bus", domain=self.domain)
                return
        raise AssertionError(("mixed original owners not drained", self.deq, self.requests, self.acks, self.responses))


@pytest.mark.parametrize("layout", ("plain", "wrap", "former"))
@pytest.mark.parametrize("outstanding", (False, True), ids=("serial", "outstanding"))
@pytest.mark.parametrize("nc_store", (False, True), ids=("io", "nc"))
async def test_normal_older_store_overtakes_held_load_and_routes_returns(lsq, layout, outstanding, nc_store):
    trace = MixedBus(lsq, layout=layout, nc_store=nc_store, outstanding=outstanding)
    await trace.allocate()
    await trace.issue_store()
    lsq.reach("LSQ-BUS.older_store", "LSQ-BUS.backpressure")
    lsq.expect(obs(uncache_request=uncache(valid=1, cmd=1)), "older real Store overtakes held younger NC Load")
    await trace.accept("store")
    await trace.ack("store", 6)
    if outstanding and nc_store:
        await trace.accept("load")
        assert "store" not in trace.responses
        # idResp and resp direction differ on the SAME public edge.
        await trace.cycle(trace.bus(ack=True, ack_to_load=True, mid=trace.requests["load"], sid=7,
                                    response=True, response_to_load=False, response_id=6, data=0xFFEEDDCCBBAA0099, nderr=True))
        await trace.respond("load")
        lsq.reach("LSQ-BUS.nc_outstanding", "LSQ-BUS.ack_route", "LSQ-BUS.resp_route")
    else:
        for _ in range(5):
            await trace.cycle(trace.bus(ready=True))
            lsq.expect(obs(uncache_request=None), "ack alone must not release serial ownership", before=True)
        await trace.respond("store")
        lsq.expect(obs(uncache_request=None), "response edge sees OLD busy, no zero-edge new acceptance", before=True)
        await trace.accept("load")
        await trace.ack("load", 7)
        await trace.respond("load")
        lsq.reach("LSQ-BUS.serial")
    await trace.consume_load()
    await trace.finish()
    names = ["LSQ-BUS.older_store", "LSQ-BUS.backpressure", "LSQ-BUS.ack_route", "LSQ-BUS.resp_route", "LSQ-EXCEPTION.shared_route"]
    names.append("LSQ-BUS.nc_outstanding" if outstanding and nc_store else "LSQ-BUS.serial")
    if layout in ("wrap", "former"):
        names.append("LSQ-BUS." + ("rob_wrap" if layout == "wrap" else "former"))
    lsq.prove(*names)


@pytest.mark.parametrize("layout", ("plain", "wrap", "former", "tie"))
async def test_unit_interface_load_older_or_tie_arbitration_not_normal_retirement(lsq, layout):
    trace = MixedBus(lsq, layout=layout, load_older=layout != "tie", outstanding=False)
    await trace.allocate()
    await trace.issue_store()
    first, second = ("store", "load") if layout == "tie" else ("load", "store")
    lsq.reach("LSQ-BUS.tie" if layout == "tie" else "LSQ-BUS.older_load")
    await trace.accept(first)
    await trace.ack(first, 8)
    for _ in range(4):
        await trace.cycle(trace.bus(ready=True))
        lsq.expect(obs(uncache_request=None), "strict serial interface holds second candidate", before=True)
    await trace.respond(first)
    await trace.accept(second)
    await trace.ack(second, 9)
    await trace.respond(second)
    await trace.consume_load()
    await trace.finish()
    lsq.prove("LSQ-BUS.tie" if layout == "tie" else "LSQ-BUS.older_load")


@pytest.mark.parametrize("nc_store", (False, True), ids=("io", "nc"))
async def test_normal_load_inflight_then_store_ack_and_opposite_load_response_same_edge(lsq, nc_store):
    trace = MixedBus(lsq, nc_store=nc_store, outstanding=True)
    await trace.allocate()
    await trace.accept("load")
    await trace.ack("load", 3)
    await trace.issue_store()
    await trace.accept("store")
    assert not trace.responses
    await trace.cycle(trace.bus(ack=True, ack_to_load=False, mid=trace.requests["store"], sid=4,
                                response=True, response_to_load=True, response_id=3,
                                data=trace.value, error=trace.fault, nderr=trace.nderr))
    lsq.reach("LSQ-BUS.nc_outstanding", "LSQ-BUS.ack_route", "LSQ-BUS.resp_route")
    # An unrelated Load response cannot release a serial Store's obligation.
    # Its own actual response is delayed even if the NC SQ owner has retired.
    for _ in range(10):
        await trace.cycle()
    if nc_store:
        assert trace.deq["store"] == 1 and "store" not in trace.responses
        lsq.emit("nc_sq_released_before_external_response", mid=trace.requests["store"], sid=4)
    await trace.consume_load()
    await trace.respond("store")
    await trace.finish()
    lsq.prove("LSQ-BUS.nc_outstanding", "LSQ-BUS.ack_route", "LSQ-BUS.resp_route", "LSQ-EXCEPTION.shared_route")
