"""Original-UID special Store actor; can explicitly observe real bad effects.

Strict cases use WrapperEnv. Named protocol probes record a counterexample
through actual fire/release, then FAIL the original semantic obligation. They
do not use model state or silently convert mismatches into passing coverage.
"""
from dataclasses import asdict, dataclass, replace

from suites.memblock.lsq.load_queue.types import Load
from suites.memblock.lsq.lsq_wrapper.types import Address, Bus, Data, Dispatch, Inputs
from suites.memblock.lsq.psq.types import Attributes
from suites.memblock.lsq.raw.types import SqPtr
from suites.memblock.lsq.vlq.types import RobPtr
from .memory_owners import StoreOwner, cached_load


@dataclass(frozen=True)
class SpecialStore(StoreOwner):
    cbo: object = None
    memory: int = 0
    hyper: bool = False

    def address(self, *, tail=False, miss=False):
        address = super().address(tail=tail, miss=miss)
        return replace(address, fu_op=self.cbo * 2 + 1 if self.cbo is not None else address.fu_op, hyper=self.hyper)

    def attributes(self, *, last=True):
        return Attributes(nc=self.memory == 1, mmio=self.memory in (2, 7), memory=self.memory < 4, last=last)

    def words(self):
        if self.memory or self.cbo is not None and self.cbo != 3:
            return []
        return StoreOwner.words(replace(self, value=0)) if self.cbo == 3 else StoreOwner.words(self)


class SpecialOwners:
    def __init__(self, env, owners, *, start=0, load_position=0, initial_head=None):
        self.env, self.owners = env, tuple(owners)
        self.start = start
        assert [owner.position for owner in owners] == list(range(start, start+len(owners)))
        self.by_position = {owner.position: owner for owner in owners}
        self.by_slot = {owner.position % 64: owner for owner in owners}
        head = RobPtr.encode(9) if initial_head is None else initial_head
        self.base = Inputs(pending=head, pending_next=head, bus=Bus(outstanding=False))
        last = max(owners, key=lambda owner: (int(owner.rob.flag) * 160 + owner.rob.value) * 2 + int(not owner.rob.former)).rob
        self.load = cached_load(load_position, int(last.flag) * 160 + last.value + 1, start+len(owners), 0x80000, 0xB080000)
        self.s2, self.load_sent, self.load_deq = (None, None), False, 0
        self.fires, self.wbs, self.cache_requests, self.cache_responses = [], [], [], []
        self.bus_request = self.bus_ack = self.bus_response = None
        self.cache_pending, self.head = None, start
        self.releases, self.effect_errors = [], []

    def activate(self, position):
        rob = self.by_position[position].rob
        self.base = replace(self.base, pending=rob, pending_next=rob)

    async def cycle(self, **fields):
        attrs = tuple(self.by_position[pos].attributes(last=last) if pos is not None else Attributes()
                      for pos, last in (s if s is not None else (None, True) for s in self.s2))
        values = dict(attributes=attrs)
        values.update(fields)
        packet = replace(self.base, **values)
        await self.env.cycle(packet)
        pre, post, tick = self.env.pre_observed, self.env.observed, self.env.last_tick
        self.s2 = tuple((self.by_slot[a.slot].position, a.last) if a.valid and not a.tlb_miss else None for a in packet.addresses)
        if any(load.execution.valid for load in packet.loads):
            assert not self.load_sent and packet.loads[0] == self.load
            self.load_sent = True
        if post["io_toLsqEnqCtrl_lqDeq_valid"]:
            self.load_deq += post["io_toLsqEnqCtrl_lqDeq_bits"]
            assert self.load_sent and self.load_deq == 1
        for lane in range(2):
            p = f"io_sbuffer_req_{lane}_"
            if not (pre[p + "valid"] and packet.sbuffer_ready[lane]):
                continue
            pos, part, word = next((owner.position, part, word) for owner in self.owners for part, word in enumerate(owner.words())
                                   if word[0] == pre[p + "bits_vaddr"] and word[1] == pre[p + "bits_addr"])
            assert not any(fire["position"] == pos and fire["part"] == part for fire in self.fires)
            actual = {key: pre[p + "bits_" + key] for key in ("vaddr", "addr", "mask", "data", "wline")}
            bits = sum(255 << (8 * byte) for byte in range(16) if word[2] >> byte & 1)
            expected = dict(vaddr=word[0], addr=word[1], mask=word[2], data=word[3], wline=int(self.by_position[pos].cbo == 3))
            difference = {key: [actual[key], value] for key, value in expected.items()
                          if (actual[key] ^ value) & (bits if key == "data" else -1)}
            if difference:
                self.effect_errors.append(dict(tick=tick, position=pos, part=part, differences=difference))
            self.fires.append(dict(tick=tick, position=pos, part=part, lane=lane, actual=actual, expected=expected))
            self.env.emit("special_actual_sbuffer_fire", transfer=self.fires[-1])
        if pre["io_cmoOpReq_valid"] and packet.cache_ready:
            owner = next(owner for owner in self.owners if owner.paddr == pre["io_cmoOpReq_bits_address"])
            assert owner.cbo is not None and owner.cbo != 3 and owner.rob == packet.pending and self.cache_pending is None
            assert pre["io_cmoOpReq_bits_opcode"] == owner.cbo
            self.cache_pending = owner.position
            self.cache_requests.append(dict(tick=tick, position=owner.position, opcode=owner.cbo, paddr=owner.paddr))
        if packet.cache_response:
            assert pre["io_cmoOpResp_ready"] and self.cache_pending is not None
            self.cache_responses.append(dict(tick=tick, position=self.cache_pending, denied=packet.cache_denied, corrupt=packet.cache_corrupt))
            self.cache_pending = None
        if pre["io_uncache_req_valid"] and packet.bus.ready:
            owner = next(owner for owner in self.owners if owner.paddr == pre["io_uncache_req_bits_addr"])
            assert owner.memory and owner.rob == packet.pending and self.bus_request is None
            self.env.expect({"io_uncache_req_bits_cmd": 1, "io_uncache_req_bits_data": owner.value,
                             "io_uncache_req_bits_mask": 255, "io_uncache_req_bits_nc": int(owner.memory == 1),
                             "io_uncache_req_bits_memBackTypeMM": int(owner.memory < 4)}, "original special Store accepted by real shared bus", before=True)
            self.bus_request = dict(tick=tick, position=owner.position, mid=pre["io_uncache_req_bits_id"])
        if packet.bus.ack:
            assert self.bus_request is not None and self.bus_ack is None and not packet.bus.ack_to_load
            assert packet.bus.mid == self.bus_request["mid"]
            self.bus_ack = dict(tick=tick, sid=packet.bus.sid)
        if packet.bus.response:
            assert self.bus_ack is not None and self.bus_response is None and not packet.bus.response_to_load
            assert packet.bus.response_id == self.bus_ack["sid"]
            self.bus_response = dict(tick=tick, position=self.bus_request["position"])
        if pre["io_mmioStout_valid"] and packet.writeback_ready:
            rob = RobPtr(bool(pre["io_mmioStout_bits_robIdx_flag"]), pre["io_mmioStout_bits_robIdx_value"], bool(pre["io_mmioStout_bits_robIdx_isFormer"]))
            owner = next(owner for owner in self.owners if owner.rob == rob)
            assert owner.rob == packet.pending and not any(wb["position"] == owner.position for wb in self.wbs)
            wb = dict(tick=tick, position=owner.position, denied=pre["io_mmioStout_bits_exceptionVec_7"],
                      corrupt=pre["io_mmioStout_bits_exceptionVec_19"], rob=asdict(rob),
                      vaddr=pre["io_stExceptionInfo_bits_vaddr"], hyper=pre["io_stExceptionInfo_bits_isHyper"])
            self.wbs.append(wb)
            self.env.emit("special_actual_wb_fire", transfer=wb)
        actual_head = 128 * post["io_sqDeqPtr_first_flag"] + 64 * post["io_sqDeqPtr_second_flag"] + post["io_sqDeqPtr_value"]
        delta = (actual_head - self.head) % 256
        assert delta <= 2 and post["io_toLsqEnqCtrl_sqDeq_valid"] == int(bool(delta))
        if delta:
            assert post["io_toLsqEnqCtrl_sqDeq_bits"] == delta
            self.releases.append(dict(tick=tick, old_head=self.head, new_head=self.head + delta))
        self.head += delta

    async def idle(self, count=1, **fields):
        for _ in range(count):
            await self.cycle(**fields)

    async def allocate(self):
        dispatch = [Dispatch(True, 2, owner.rob, 1, store_end=SqPtr.encode(owner.position + 1)) for owner in self.owners]
        dispatch.append(Dispatch(True, 1, self.load.execution.uop.rob, 1, load_start=self.load.execution.uop.lq))
        self.env.emit("special_allocate_original_owners", stores=[asdict(owner) for owner in self.owners], load=asdict(self.load))
        await self.cycle(dispatch=tuple(dispatch) + (Dispatch(),) * (8 - len(dispatch)))
        await self.cycle(loads=(self.load, Load(), Load()))

    async def write(self, position, *, lane=0):
        owner, addresses, data = self.by_position[position], [Address(), Address()], [Data(), Data()]
        addresses[lane], data[1 - lane] = owner.address(), owner.data()
        await self.cycle(addresses=tuple(addresses), data=tuple(data))
        if owner.address().cross_word:
            addresses[lane] = owner.address(tail=True)
            await self.cycle(addresses=tuple(addresses))
        await self.idle(3)

    async def wait(self, pin, limit=80):
        for _ in range(limit):
            if self.env.observed[pin]:
                return
            await self.cycle()
        raise AssertionError(("real special owner output absent", pin))

    async def cache_roundtrip(self, position, *, denied=False, corrupt=False, hold=0):
        owner = self.by_position[position]
        if owner.cbo == 3:
            self.base = replace(self.base, sbuffer_ready=(True, True))
        else:
            await self.wait("io_cmoOpReq_valid")
            await self.idle(3)
            await self.cycle(cache_ready=True)
            await self.cycle(cache_response=True, cache_denied=denied, cache_corrupt=corrupt)
        await self.wait("io_mmioStout_valid")
        await self.idle(hold)
        await self.cycle(writeback_ready=True)
        assert self.wbs and self.wbs[-1]["position"] == position
        return self.wbs[-1]

    async def bus_accept_ack(self, position):
        await self.wait("io_uncache_req_valid")
        await self.idle(3)
        await self.cycle(bus=replace(self.base.bus, ready=True))
        await self.cycle(bus=replace(self.base.bus, ack=True, ack_to_load=False, mid=self.bus_request["mid"], sid=5))

    async def bus_respond(self):
        await self.cycle(bus=replace(self.base.bus, response=True, response_to_load=False, response_id=self.bus_ack["sid"]))

    def fulfilled(self, owner):
        fragments = [f for f in self.fires if f["position"] == owner.position]
        if owner.cbo is None and not owner.memory:
            return len(fragments) == len(owner.words()) and not any(error["position"] == owner.position for error in self.effect_errors)
        if owner.memory == 1:
            return self.bus_ack is not None
        if not any(wb["position"] == owner.position for wb in self.wbs):
            return False
        if owner.cbo == 3:
            return len(fragments) == 1 and not any(error["position"] == owner.position for error in self.effect_errors)
        return True

    async def finish(self, *, observe_only=False):
        if not observe_only:
            assert all(self.fulfilled(owner) for owner in self.owners)
            last = self.load.execution.uop.rob
            end = RobPtr.encode(int(last.flag) * 160 + last.value + 1)
            self.base = replace(self.base, pending=end, pending_next=end)
        self.base = replace(self.base, sbuffer_ready=(True, True), writeback_ready=True)
        for _ in range(100):
            await self.cycle()
            if self.head == self.start+len(self.owners) and self.load_deq == 1 and self.env.observed["io_sqEmpty"] and self.env.observed["io_lqEmpty"]:
                await self.idle(8)
                assert self.bus_request is None or self.bus_response is not None
                if not observe_only:
                    assert not self.effect_errors and all(self.fulfilled(owner) for owner in self.owners)
                self.env.emit("special_actual_drain", head=self.head, load_deq=self.load_deq,
                              logically_fulfilled=[self.fulfilled(owner) for owner in self.owners], observe_only=observe_only)
                return
        raise AssertionError("real special owners did not actually drain their queue/response obligations")
