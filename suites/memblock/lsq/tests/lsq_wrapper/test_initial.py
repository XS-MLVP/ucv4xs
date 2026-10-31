"""First REAL mixed execution/commit and actual SQ-to-Replay dependencies."""

from dataclasses import asdict, replace

import pytest

from suites.memblock.lsq.legacy_pins import P
from suites.memblock.lsq.load_queue.types import Load
from suites.memblock.lsq.lsq_wrapper.types import Address, Data, Dispatch, Inputs
from suites.memblock.lsq.replay.types import Cause, Enqueue, Uop
from suites.memblock.lsq.raw.types import SqPtr
from suites.memblock.lsq.vlq.types import QueuePtr, RobPtr


def pair(store_lane=0):
    load_lane = (store_lane + 1) % 8
    srob, lrob = (RobPtr.encode(int(store_lane > load_lane)), RobPtr.encode(int(load_lane > store_lane)))
    requests = [Dispatch()] * 8
    requests[store_lane] = Dispatch(True, 2, srob, 1, store_end=SqPtr.encode(1))
    requests[load_lane] = Dispatch(True, 1, lrob, 1)
    address = Address(True, 0, 6, 0x1000, 0x80001000, 3, rob=srob, mask=255)
    data = Data(True, SqPtr(), 6, 0x8877665544332211)
    load = Load(Enqueue(True, Uop(rob=lrob, lq=QueuePtr(), sq=SqPtr.encode(1), operation=6),
                        vaddr=0x2000, mask=255), fullva=0x2000, paddr=0x90002000, update_address=True)
    return tuple(requests), address, data, load


class Trace:
    """Only actual public consumption; not reference/change-log answers."""
    def __init__(self, env, address, data):
        self.env, self.address, self.data = env, address, data
        self.load_count = self.store_count = self.sbuffer = 0

    async def cycle(self, inp=None):
        inp = inp or Inputs()
        await self.env.cycle(inp)
        pre, post = self.env.pre_observed, self.env.observed
        for lane in range(2):
            p = P.io(f"sbuffer_req_{lane}_")
            if pre[p + "valid"] and inp.sbuffer_ready[lane]:
                assert self.sbuffer == 0
                self.env.expect({p + "bits_addr": self.address.paddr, p + "bits_vaddr": self.address.vaddr,
                                 p + "bits_mask": 255, p + "bits_data": self.data.data, p + "bits_wline": 0},
                                "original store UID actually consumed by Sbuffer", before=True, masks={p + "bits_data": (1 << 64) - 1})
                self.sbuffer += 1
                self.env.emit("sbuffer_fire", store_uid=1, lane=lane)
        if post[P.p_toLsqEnqCtrl_lqDeq_valid]:
            self.load_count += post[P.p_toLsqEnqCtrl_lqDeq_bits]
            assert self.load_count == 1
            self.env.emit("load_complete", load_uid=2)
        if post[P.p_toLsqEnqCtrl_sqDeq_valid]:
            self.store_count += post[P.p_toLsqEnqCtrl_sqDeq_bits]
            assert self.store_count == self.sbuffer == 1
            self.env.emit("store_complete", store_uid=1)

    async def drain(self):
        base = Inputs(pending=RobPtr.encode(2), pending_next=RobPtr.encode(2), sbuffer_ready=(True, True))
        for _ in range(60):
            await self.cycle(base)
            if self.store_count == self.load_count == self.sbuffer == 1 and self.env.observed[P.p_lqEmpty] and self.env.observed[P.p_sqEmpty]:
                for _ in range(6):
                    await self.cycle(base)
                assert not self.env.observed[P.p_replayAllocate] and not self.env.observed[P.p_uncache_req_valid]
                self.env.emit("complete_pair", load_uid=2, store_uid=1)
                return
        raise AssertionError("real mixed Load/Store owners did not complete their own effects and deq")


@pytest.mark.parametrize("store_lane", range(8))
@pytest.mark.parametrize("data_first", (False, True))
async def test_mixed_dispatch_both_real_branches_complete_original_owners(lsq, store_lane, data_first):
    requests, address, data, load = pair(store_lane)
    trace = Trace(lsq, address, data)
    lsq.emit("allocate_pair", dispatch=[asdict(d) for d in requests], address=asdict(address), data=asdict(data), load=asdict(load))
    await trace.cycle(Inputs(dispatch=requests))
    if data_first:
        await trace.cycle(Inputs(data=(data, Data())))
        await trace.cycle(Inputs(addresses=(address, Address())))
    else:
        await trace.cycle(Inputs(addresses=(address, Address())))
        await trace.cycle(Inputs(data=(data, Data())))
    await trace.cycle(Inputs(loads=(load, Load(), Load())))
    # Both ordinary instructions executed; advance one global ROB past both,
    # but hold real Sbuffer backpressure to distinguish retirement from effect.
    held = Inputs(pending=RobPtr.encode(2), pending_next=RobPtr.encode(2))
    for _ in range(8):
        await trace.cycle(held)
        assert trace.store_count == trace.sbuffer == 0
    assert trace.load_count == 1 and not lsq.observed[P.p_sqEmpty]
    await trace.drain()
    lsq.prove("LSQ-RESET.initial", "LSQ-ALLOC.filters", "LSQ-ALLOC.sparse", "LSQ-RETIRE.ordinary", "LSQ-RETIRE.rob_before_sbuffer")


@pytest.mark.parametrize("kind", ("address", "data", "same_std"))
@pytest.mark.parametrize("store_lane", range(2))
async def test_real_store_readiness_and_std_write_unblock_load_replay(lsq, kind, store_lane):
    requests, address, data, load = pair()
    trace = Trace(lsq, address, data)
    lsq.emit("allocate_pair", dispatch=[asdict(d) for d in requests], address=asdict(address), data=asdict(data), load=asdict(load))
    await trace.cycle(Inputs(dispatch=requests))
    for _ in range(3):
        await trace.cycle()
    if kind == "address":
        values = [Data(), Data()]; values[store_lane] = data
        await trace.cycle(Inputs(data=tuple(values)))
    else:
        values = [Address(), Address()]; values[store_lane] = address
        await trace.cycle(Inputs(addresses=tuple(values)))
        for _ in range(3):
            await trace.cycle()
    cause = Cause.ADDRESS_DEPENDENCE if kind == "address" else Cause.FORWARD_FAILURE
    load = replace(load, execution=replace(load.execution, need_replay=True, causes=1 << cause, address_sq=SqPtr(), data_sq=SqPtr()))
    packet = Inputs(loads=(load, Load(), Load()))
    if kind == "same_std":
        values = [Data(), Data()]; values[store_lane] = data
        packet = replace(packet, data=tuple(values))
    await trace.cycle(packet)
    if kind != "same_std":
        for _ in range(5):
            await trace.cycle()
            assert not any(lsq.observed[P.io(f"replay_{bank}_valid")] for bank in range(3)) and trace.load_count == 0
        if kind == "address":
            values = [Address(), Address()]; values[store_lane] = address
            await trace.cycle(Inputs(addresses=tuple(values)))
        else:
            values = [Data(), Data()]; values[store_lane] = data
            await trace.cycle(Inputs(data=tuple(values)))
    for _ in range(40):
        if lsq.observed[P.p_replay_0_valid]:
            break
        await trace.cycle()
    assert lsq.observed[P.p_replay_0_valid] and lsq.observed[P.p_replay_0_bits_uop_robIdx_value] == load.execution.uop.rob.value
    slot = lsq.observed[P.p_replay_0_bits_replayQueueIdx]
    await trace.cycle(Inputs(replay_ready=(True, True, True)))
    assert lsq.pre_observed[P.p_replay_0_valid]
    feedback = replace(load, execution=replace(load.execution, replay_feedback=True, slot=slot, need_replay=False, causes=0))
    await trace.cycle(Inputs(loads=(feedback, Load(), Load())))
    await trace.drain()
    name = "sq_address" if kind == "address" else "sq_data" if kind == "data" else "std_write"
    lsq.prove("LSQ-REPLAY." + name)
