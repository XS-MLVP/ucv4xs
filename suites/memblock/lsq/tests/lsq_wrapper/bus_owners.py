"""External multi-owner bus actor: no model state or private DUT signals."""
from dataclasses import asdict, replace

from lsqverify.load_queue.types import Bypass, Load
from lsqverify.lsq_wrapper.types import Address, Bus, Data, Dispatch, Inputs
from lsqverify.psq.types import Attributes
from lsqverify.raw.types import SqPtr
from lsqverify.replay.types import Enqueue, Uop
from lsqverify.vlq.types import QueuePtr, RobPtr


class BusOwners:
    def __init__(self, env, *, nc_store=None, lane=0, old_fault=False):
        self.env, self.nc_store, self.lane = env, nc_store, lane
        self.base = Inputs(bus=Bus(outstanding=True), sbuffer_ready=(True, True), writeback_ready=True)
        offset = int(nc_store is not None)
        self.loads = tuple(Load(Enqueue(True, Uop(rob=RobPtr.encode(offset + pos), lq=QueuePtr.encode(pos),
                                                sq=SqPtr.encode(offset), operation=6),
                                       vaddr=0x4000 + 0x100 * pos, mask=255, nc=True, need_replay=True, causes=1),
                                fullva=0xABC04000 + 0x100 * pos, paddr=0xE0104000 + 0x100 * pos, update_address=True) for pos in range(2))
        self.address = Address(True, 0, 6, 0x6000, 0xF0206000, 3, rob=RobPtr.encode(0), mask=255)
        self.store_data = Data(True, SqPtr(), 6, 0x1234FEDC5678BA90)
        self.payload = {f"load{pos}": dict(data=(0x1122334455667788 if pos == 0 else 0xAABBCCDDEEFF0011),
                                          error=old_fault if pos == 0 else not old_fault,
                                          nderr=not old_fault if pos == 0 else old_fault) for pos in range(2)}
        self.requests, self.acks, self.responses, self.grants, self.checked_data, self.feedback = {}, {}, set(), {}, set(), set()
        self.wb, self.load_deq, self.store_deq = 0, 0, 0

    def packet(self, **fields):
        return replace(self.base, **fields)

    def bus(self, **fields):
        return replace(self.base, bus=replace(self.base.bus, **fields))

    def role(self, values):
        if values["io_uncache_req_bits_cmd"] == 1:
            assert self.nc_store is not None and values["io_uncache_req_bits_addr"] == self.address.paddr
            return "store"
        return next(f"load{pos}" for pos, load in enumerate(self.loads) if values["io_uncache_req_bits_addr"] == load.paddr)

    async def step(self, packet=None):
        packet = packet or self.base
        await self.env.cycle(packet)
        pre, post, bus = self.env.pre_observed, self.env.observed, packet.bus
        if pre["io_uncache_req_valid"] and bus.ready:
            role = self.role(pre)
            assert role not in self.requests
            rob = self.address.rob if role == "store" else self.loads[int(role[-1])].execution.uop.rob
            self.env.expect({"io_uncache_req_bits_robIdx_flag": int(rob.flag), "io_uncache_req_bits_robIdx_value": rob.value,
                             "io_uncache_req_bits_robIdx_isFormer": int(rob.former), "io_uncache_req_bits_mask": 255,
                             "io_uncache_req_bits_nc": int(role != "store" or self.nc_store)}, "multi-owner bus request original identity", before=True)
            if role == "store":
                self.env.expect({"io_uncache_req_bits_data": self.store_data.data}, "multi-owner Store original bytes", before=True)
            self.requests[role] = pre["io_uncache_req_bits_id"]
            self.env.emit("multi_bus_fire", role=role, mid=self.requests[role])
        if bus.ack:
            possible = [role for role, mid in self.requests.items() if mid == bus.mid and (role != "store") == bus.ack_to_load and role not in self.acks]
            assert len(possible) == 1
            role = possible[0]
            assert not any(sid == bus.sid and old not in self.responses for old, sid in self.acks.items())
            self.acks[role] = bus.sid
        if bus.response:
            possible = [role for role, sid in self.acks.items() if sid == bus.response_id and (role != "store") == bus.response_to_load and role not in self.responses]
            assert len(possible) == 1
            self.responses.add(possible[0])
        for bank in range(3):
            p = f"io_replay_{bank}_"
            if pre[p + "valid"] and packet.replay_ready[bank]:
                pos = pre[p + "bits_uop_lqIdx_value"]
                assert pos in (0, 1) and f"load{pos}" in self.responses and pos not in self.grants
                self.grants[pos] = pre[p + "bits_replayQueueIdx"]
        for load in packet.loads:
            q = load.execution
            if q.valid and q.replay_feedback:
                pos = q.uop.lq.value
                assert pos in self.grants and self.grants[pos] == q.slot and pos in self.checked_data and pos not in self.feedback
                self.feedback.add(pos)
        if pre["io_mmioStout_valid"] and packet.writeback_ready:
            assert self.nc_store is False and "store" in self.responses and not self.wb
            self.wb += 1
        if post["io_toLsqEnqCtrl_sqDeq_valid"]:
            self.store_deq += post["io_toLsqEnqCtrl_sqDeq_bits"]
            assert self.store_deq == 1 and ("store" in self.acks if self.nc_store else self.wb == 1)
        if post["io_toLsqEnqCtrl_lqDeq_valid"]:
            count = post["io_toLsqEnqCtrl_lqDeq_bits"]
            assert all(pos in self.feedback and pos in self.checked_data for pos in range(self.load_deq, self.load_deq + count))
            self.load_deq += count
            assert self.load_deq <= 2
        assert not any(pre[f"io_sbuffer_req_{lane}_valid"] and packet.sbuffer_ready[lane] for lane in range(2))

    async def allocate(self):
        dispatch = [] if self.nc_store is None else [Dispatch(True, 2, RobPtr.encode(0), 1, store_end=SqPtr.encode(1))]
        dispatch += [Dispatch(True, 1, load.execution.uop.rob, 1, load_start=load.execution.uop.lq) for load in self.loads]
        self.env.emit("allocate_multi_bus", domain="NORMAL-PRODUCER", dispatch=[asdict(d) for d in dispatch],
                      loads=[asdict(load) for load in self.loads], nc_store=self.nc_store, address=asdict(self.address),
                      data=asdict(self.store_data), payload=self.payload)
        await self.step(self.packet(dispatch=tuple(dispatch) + (Dispatch(),) * (8 - len(dispatch))))

    async def execute(self, pos):
        loads = [Load()] * 3
        loads[self.lane] = self.loads[pos]
        await self.step(self.packet(loads=tuple(loads)))

    async def issue_store(self):
        await self.step(self.packet(addresses=(self.address, Address()), data=(Data(), self.store_data)))
        await self.step(self.packet(attributes=(Attributes(nc=self.nc_store, mmio=not self.nc_store), Attributes())))

    async def wait(self, role):
        for _ in range(80):
            if self.env.observed["io_uncache_req_valid"] and self.role(self.env.observed) == role:
                return
            await self.step()
        raise AssertionError(("real original multi-owner request not visible", role))

    async def accept(self, role):
        await self.wait(role)
        await self.step(self.bus(ready=True))
        assert role in self.requests

    async def ack(self, role, sid):
        await self.step(self.bus(ack=True, ack_to_load=role != "store", mid=self.requests[role], sid=sid))

    async def respond(self, role):
        payload = self.payload[role] if role != "store" else dict(data=0xDEAD00000000BEEF, error=True, nderr=True)
        await self.step(self.bus(response=True, response_to_load=role != "store", response_id=self.acks[role], **payload))

    async def consume(self, pos, lane):
        for _ in range(80):
            bank = next((bank for bank in range(3) if self.env.observed[f"io_replay_{bank}_valid"] and
                         self.env.observed[f"io_replay_{bank}_bits_uop_lqIdx_value"] == pos), None)
            if bank is not None:
                break
            await self.step()
        assert bank is not None
        ready = tuple(k == bank for k in range(3))
        await self.step(self.packet(replay_ready=ready))
        queries = [Bypass()] * 3
        queries[lane] = Bypass(True, self.loads[pos].execution.uop.lq, nc=True)
        await self.step(self.packet(bypass=tuple(queries)))
        prefix, load, payload = f"io_bypass_{lane}_", self.loads[pos], self.payload[f"load{pos}"]
        self.env.expect({prefix + "s1Resp_valid": 1, prefix + "s1Resp_bits_paddr": load.paddr,
                         "io_ldExceptionInfo_valid": 1, "io_ldExceptionInfo_bits_vaddr": load.fullva,
                         "io_ldExceptionInfo_bits_robIdx_value": load.execution.uop.rob.value,
                         "io_ldExceptionInfo_bits_exceptionVec_19": int(payload["error"]),
                         "io_ldExceptionInfo_bits_exceptionVec_5": int(payload["nderr"])}, "multi-owner ORIGINAL Load address/faults, not a later SID owner")
        await self.step()
        self.env.expect({prefix + "s2Resp_valid": 1, prefix + "s2Resp_bits_data": payload["data"] * ((1 << 64) + 1),
                         prefix + "s2Resp_bits_derr": int(payload["error"]), prefix + "s2Resp_bits_nderr": int(payload["nderr"])},
                        "multi-owner ORIGINAL Load response bytes/errors")
        self.checked_data.add(pos)
        feedback = replace(load, execution=replace(load.execution, replay_feedback=True, slot=self.grants[pos], need_replay=False, causes=0))
        loads = [Load()] * 3
        loads[self.lane] = feedback
        await self.step(self.packet(loads=tuple(loads)))

    async def finish(self):
        if self.nc_store is False:
            for _ in range(30):
                if self.wb == 1:
                    break
                await self.step()
            assert self.wb == 1
        end = RobPtr.encode(2 + int(self.nc_store is not None))
        self.base = replace(self.base, pending=end, pending_next=end)
        for _ in range(100):
            await self.step()
            if self.load_deq == 2 and self.store_deq == int(self.nc_store is not None) and self.env.observed["io_lqEmpty"] and self.env.observed["io_sqEmpty"]:
                for _ in range(8):
                    await self.step()
                assert set(self.requests) == set(self.acks) == self.responses
                assert self.checked_data == self.feedback == {0, 1} and not self.env.observed["io_replayAllocate"]
                self.env.emit("complete_multi_bus", loads=2, stores=int(self.nc_store is not None))
                return
        raise AssertionError(("original multi-owner obligations not truly drained", self.load_deq, self.store_deq))
