"""External dispatch/ROB/execution/bus actor, separate from both references.

Virtual uops own physical-flow UIDs. Every control decision uses this ledger
or real public ports, never the reference model or a hidden DUT hierarchy.
"""
from dataclasses import asdict, dataclass, fields, replace
import json
import random

from lsqverify.forward.types import Query, Translation
from lsqverify.psq.actor import Owner
from lsqverify.psq.checks import read_ptr
from lsqverify.psq.types import Address, Attributes, Data, SecondPage
from lsqverify.raw.types import SqPtr
from lsqverify.vlq.types import Redirect, RobPtr
from lsqverify.vsq.types import Dispatch
from .types import Inputs


@dataclass
class Uop:
    uid: int
    rob_order: int
    rob: RobPtr
    flows: tuple
    start: int
    end: int
    lane: object = None
    dispatched: bool = False
    retired_by_rob: bool = False


class StoreActor:
    def __init__(self, env, *, seed=1):
        self.env, self.rng = env, random.Random(seed)
        self.head = self.tail = self.dispatched_tail = self.sequence = self.uop_sequence = 0
        self.next_rob, self.rob_order = 10, 10
        self.live, self.all, self.uops, self.flow_uop = {}, {}, {}, {}
        self.active_uops, self.pending_dispatch = [], []
        self.parts, self.finish_ticks = {}, {}
        self.completed, self.cancelled, self.aborted = set(), set(), set()
        self.pending = self.held_page = None
        self.pages = set()
        self.s2, self.query_pa = ((None, True),) * 2, (None,) * 3
        self.emit("start", seed=seed)

    def emit(self, event, **fields):
        self.env.actor_journal.write(json.dumps({"nodeid": self.env.nodeid, "event": event, **fields}) + "\n")

    def add(self, *, flows=1, lane=None, size=3, offset=0, memory=0, cbo=None, page=False, retry=False, exception=False):
        assert 0 <= flows <= 16 and self.tail - self.head + flows <= 128
        assert memory in (0, 1, 2, 7) and (cbo is None or flows == 1 and memory == 0)
        assert lane is None or lane in range(8)
        assert size in range(5) and (memory == 0 or size <= 3 and offset // 8 == (offset + (1 << size) - 1) // 8)
        self.uop_sequence += 1
        rob = RobPtr.encode(self.next_rob, former=bool(self.next_rob % 2))
        uop = Uop(self.uop_sequence, self.next_rob, rob, (), self.tail, self.tail + flows, lane)
        self.next_rob += 1
        owners = []
        for _ in range(flows):
            self.sequence += 1
            uid, position = self.sequence, self.tail
            va = 0x100000 + uid * 8192 + (4092 if page else offset)
            pa = 0xA000000 + uid * 8192 + va % 4096
            cross = va % 16 + (1 << size) > 16
            assert not page or cross
            op = cbo * 2 + 1 if cbo is not None else (0x200 if size == 4 else 0) | size << 1
            value = int.from_bytes(bytes((uid * 19 + byte * 31) % 256 for byte in range(16)), "little")
            address = Address(True, position % 64, op, va, pa, size, hyper=bool(uid % 2), unaligned=bool(va % (1 << size)), cross_word=cross, last=not cross)
            owner = Owner(uid, position, address, Data(True, position % 64, op, value),
                          Attributes(nc=memory == 1, mmio=memory in (2, 7), memory=memory < 4, exception=exception), rob,
                          (0xD000 + uid) * 4096 if page else None, retry=retry)
            self.live[position] = self.all[uid] = owner
            self.parts[uid], self.flow_uop[uid] = set(), uop.uid
            self.tail += 1
            owners.append(owner)
        uop.flows = tuple(owner.uid for owner in owners)
        self.uops[uop.uid] = uop
        self.active_uops.append(uop.uid)
        self.pending_dispatch.append(uop.uid)
        self.emit("allocate", uop=asdict(uop), owners=[asdict(owner) for owner in owners])
        return uop

    def rob_pointer(self, advance):
        moved = 0
        for uid in self.active_uops:
            uop = self.uops[uid]
            if uop.retired_by_rob:
                continue
            owners = [self.all[flow] for flow in uop.flows]
            ready = uop.dispatched and all(owner.s2_done and owner.data_sent and not owner.attributes.exception and
                      (not owner.address.fu_op & 1 and not owner.attributes.nc and not owner.attributes.mmio or owner.finished) for owner in owners)
            if advance and ready and moved < 8:
                uop.retired_by_rob = True
                self.rob_order = uop.rob_order + 1
                moved += 1
            else:
                self.rob_order = uop.rob_order
                return uop.rob
        return RobPtr.encode(self.rob_order, former=bool(self.rob_order % 2))

    def prepared(self, *, fair, issue, query, dispatch, advance_rob):
        rng = self.rng
        rob = self.rob_pointer(advance_rob)
        controls = {"dispatch": (Dispatch(),) * 8, "rob_head": rob, "redirect": Redirect(),
                    "addresses": (Address(), Address()), "data": (Data(), Data()),
                    "attributes": tuple(replace(self.all[uid].attributes, last=last) if uid is not None else Attributes() for uid, last in self.s2),
                    "second_pages": (SecondPage(), SecondPage()), "queries": (Query(),) * 3,
                    "translations": tuple(Translation(pa) if pa is not None else Translation() for pa in self.query_pa),
                    "cache_response": False, "uncache_response": False, "uncache_ack_valid": False, "uncache_ack_to_load": False}
        ready0 = fair or rng.random() < 0.7
        controls.update(sbuffer_ready=(ready0, ready0 and (fair or rng.random() < 0.65)), cache_ready=fair or rng.random() < 0.7,
                        uncache_ready=fair or rng.random() < 0.7, writeback_ready=fair or rng.random() < 0.65, sbuffer_empty=fair or rng.random() < 0.7)
        if self.pending and (fair or rng.random() < 0.6):
            controls[{"cache": "cache_response", "io": "uncache_response", "nc": "uncache_ack_valid"}[self.pending[0]]] = True
        if dispatch and self.pending_dispatch and not self.env.observed["io_toLsqEnqCtrl_sqRecoverStall"]:
            requests, last_lane = [Dispatch()] * 8, -1
            for uid in self.pending_dispatch[:8 if fair else rng.randrange(1, 9)]:
                uop = self.uops[uid]
                lane = uop.lane if uop.lane is not None else last_lane + 1
                if lane <= last_lane:
                    break
                requests[lane] = Dispatch(True, True, uop.rob, len(uop.flows), SqPtr.encode(uop.end))
                last_lane = lane
            controls["dispatch"] = tuple(requests)
        candidates = [owner for pos, owner in sorted(self.live.items()) if pos - self.head < 64 and self.uops[self.flow_uop[owner.uid]].dispatched]
        if issue:
            addresses, data = [Address(), Address()], [Data(), Data()]
            address_candidates = [owner for owner in candidates if not owner.s2_done and owner.address_parts < (2 if owner.address.cross_word else 1)
                                  and (not owner.address.fu_op & 1 or owner.rob == rob)]
            rng.shuffle(address_candidates)
            for lane, owner in enumerate(address_candidates[:2 if fair else rng.randrange(3)]):
                address = owner.address
                if owner.address_parts:
                    if owner.second_page is not None and not owner.page_sent:
                        continue
                    address = replace(address, vaddr=address.vaddr // 16 * 16 + 16,
                                      paddr=owner.second_page if owner.second_page is not None else address.paddr // 16 * 16 + 16, last=True)
                if owner.retry and not owner.retried:
                    address = replace(address, tlb_miss=True)
                addresses[lane] = address
            data_candidates = [owner for owner in candidates if not owner.data_sent and (not owner.address.fu_op & 1 or owner.rob == rob)]
            rng.shuffle(data_candidates)
            for lane, owner in enumerate(data_candidates[:2 if fair else rng.randrange(3)]):
                data[lane] = owner.data
            controls.update(addresses=tuple(addresses), data=tuple(data))
            if self.held_page is None and len(self.pages) < 2:
                address_ready = read_ptr(self.env.observed, "io_toLoadQueue_stAddrReadySqPtr_")
                owner = next((owner for owner in candidates if owner.second_page is not None and not owner.page_sent and owner.position % 256 == address_ready), None)
                if owner:
                    self.held_page = (owner.uid, rng.randrange(2))
        if self.held_page:
            uid, lane = self.held_page
            pages = [SecondPage(), SecondPage()]
            owner = self.all[uid]
            pages[lane] = SecondPage(True, SqPtr.encode(owner.position), owner.second_page)
            controls["second_pages"] = tuple(pages)
        if query and self.dispatched_tail - self.head < 128:
            options = [owner for owner in candidates if owner.s2_done and not owner.address.cross_word]
            if options:
                owner, lane = rng.choice(options), rng.randrange(3)
                queries = [Query()] * 3
                queries[lane] = Query(True, owner.address.vaddr, SqPtr.encode(self.dispatched_tail), owner.address.size)
                controls["queries"] = tuple(queries)
        return controls

    async def step(self, *, fair=False, issue=True, query=False, dispatch=True, advance_rob=True, **overrides):
        controls = self.prepared(fair=fair, issue=issue, query=query, dispatch=dispatch, advance_rob=advance_rob)
        controls.update(overrides)
        old_s2 = self.s2
        await self.env.cycle(**controls)
        inp, pre, post, tick = self.env.controls, self.env.pre_observed, self.env.observed, self.env.last_tick
        assert read_ptr(pre) == self.head % 256
        dispatched = []
        for req in inp.dispatch:
            if req.valid and req.need_alloc:
                uid = self.pending_dispatch.pop(0)
                uop = self.uops[uid]
                assert req.rob == uop.rob and req.end == SqPtr.encode(uop.end) and req.flows == len(uop.flows)
                uop.dispatched, self.dispatched_tail = True, uop.end
                dispatched.append(uid)
        for uid, last in old_s2:
            if uid is not None and last:
                self.all[uid].s2_done = True
        self.s2 = [(None, True), (None, True)]
        for lane, address in enumerate(inp.addresses):
            if address.valid:
                owner = self.live[self.head + (address.slot - self.head) % 64]
                assert self.uops[self.flow_uop[owner.uid]].dispatched
                if address.tlb_miss:
                    owner.retried = True
                else:
                    owner.address_parts += 1
                    self.s2[lane] = (owner.uid, address.last)
        for data in inp.data:
            if data.valid:
                owner = self.live[self.head + (data.slot - self.head) % 64]
                assert not owner.data_sent
                owner.data_sent = True
        if self.held_page:
            uid, lane = self.held_page
            if pre[f"io_fromStoreUnit_unalignQueueReq_{lane}_ready"]:
                self.all[uid].page_sent = True
                self.pages.add(uid)
                self.held_page = None
        if self.pending:
            kind, uid = self.pending
            if (kind == "cache" and inp.cache_response and pre["io_toDCache_resp_ready"] or kind == "io" and inp.uncache_response or
                    kind == "nc" and inp.uncache_ack_valid and not inp.uncache_ack_to_load):
                if kind == "nc":
                    self.all[uid].finished = True
                    self.finish_ticks[uid] = tick
                self.pending = None
        if pre["io_toDCache_req_valid"] and inp.cache_ready:
            assert self.pending is None
            owner = next(owner for owner in self.live.values() if owner.address.paddr == pre["io_toDCache_req_bits_address"])
            assert owner.rob == inp.rob_head and owner.address.fu_op & 1
            self.pending = ("cache", owner.uid)
        if pre["io_toUncacheBuffer_req_valid"] and inp.uncache_ready:
            assert self.pending is None
            owner = next(owner for owner in self.live.values() if owner.address.vaddr == pre["io_toUncacheBuffer_req_bits_vaddr"])
            self.pending = ("nc" if owner.attributes.nc else "io", owner.uid)
        if pre["io_writeBack_valid"] and inp.writeback_ready:
            rob = RobPtr(bool(pre["io_writeBack_bits_robIdx_flag"]), pre["io_writeBack_bits_robIdx_value"], bool(pre["io_writeBack_bits_robIdx_isFormer"]))
            owner = next(owner for owner in self.live.values() if owner.rob == rob and not owner.finished)
            assert owner.rob == inp.rob_head
            owner.finished = True
            self.finish_ticks[owner.uid] = tick
        consumed = []
        for lane in range(2):
            prefix = f"io_writeToSbuffer_req_{lane}_"
            if not pre[prefix + "valid"] or not inp.sbuffer_ready[lane]:
                continue
            owner, part = next((owner, part) for owner in self.live.values() for part in range(2 if owner.address.cross_word else 1)
                               if owner.address.vaddr // 16 * 16 + part * 16 == pre[prefix + "bits_vaddr"])
            uid = owner.uid
            assert part not in self.parts[uid]
            va = owner.address.vaddr // 16 * 16 + part * 16
            pa = owner.second_page if part and owner.second_page is not None else owner.address.paddr // 16 * 16 + part * 16
            zero = bool(owner.address.fu_op & 1 and owner.address.fu_op >> 1 & 7 == 3)
            original = 0 if zero else owner.data.data
            mask = value = 0
            for index in range(1 << owner.address.size):
                byte = owner.address.vaddr + index - va
                if 0 <= byte < 16:
                    mask |= 1 << byte
                    value |= (original >> (8 * index) & 255) << (8 * byte)
            bits = sum(255 << (8 * byte) for byte in range(16) if mask >> byte & 1)
            assert pre[prefix + "bits_addr"] == pa and pre[prefix + "bits_mask"] == mask and pre[prefix + "bits_wline"] == int(zero)
            assert not ((pre[prefix + "bits_data"] ^ value) & bits)
            self.parts[uid].add(part)
            self.finish_ticks[uid] = tick
            self.pages.discard(uid)
            consumed.append({"uid": uid, "part": part})
        delta = (read_ptr(post) - self.head) % 256
        assert delta <= 2 and post["io_toLsqEnqCtrl_sqDeq_valid"] == int(bool(delta))
        if delta:
            assert post["io_toLsqEnqCtrl_sqDeq_bits"] == delta
        completed = []
        for pos in range(self.head, self.head + delta):
            owner = self.live[pos]
            uid = owner.uid
            assert uid not in self.completed and owner.s2_done and owner.data_sent and not owner.attributes.exception
            special = owner.address.fu_op & 1 or owner.attributes.nc or owner.attributes.mmio
            if special:
                assert owner.finished and self.finish_ticks[uid] < tick
                if owner.address.fu_op & 1 and owner.address.fu_op >> 1 & 7 == 3:
                    assert self.parts[uid] == {0}
            else:
                assert self.parts[uid] == ({0, 1} if owner.address.cross_word else {0}) and self.finish_ticks[uid] + 2 == tick
            self.completed.add(uid)
            completed.append(uid)
            del self.live[pos]
        self.head += delta
        self.query_pa = tuple(next((owner.address.paddr for owner in self.all.values() if owner.address.vaddr == query.vaddr), 0) if query.valid else None for query in inp.queries)
        self.emit("step", tick=tick, dispatched=dispatched, head=self.head, tail=self.tail, rob_order=self.rob_order, consumed=consumed, completed=completed)
        return completed

    async def drain(self, limit=3000):
        for _ in range(limit):
            await self.step(fair=True)
            if not self.live and not self.pending_dispatch and self.pending is None and self.env.observed["io_sqEmpty"]:
                for _ in range(4):
                    await self.step(fair=True)
                return
        raise AssertionError("real StoreQueue did not fairly drain both flow side effects and virtual ownership")

    def checked(self, names, uids):
        assert set(uids) <= self.completed
        self.env.begin(names)
        self.env.finish(names)
        self.emit("checked", tick=self.env.last_tick, names=names, uids=list(uids), completed=sorted(self.completed), cancelled=sorted(self.cancelled), aborted=sorted(self.aborted))

    async def reset(self):
        old = sorted(owner.uid for owner in self.live.values())
        defaults = Inputs(reset=True)
        for _ in range(4):
            await self.env.cycle(**{field.name: getattr(defaults, field.name) for field in fields(Inputs)})
        self.aborted.update(old)
        self.live.clear()
        self.active_uops.clear()
        self.pending_dispatch.clear()
        self.head = self.tail = self.dispatched_tail = 0
        self.next_rob = self.rob_order = 10
        self.pending = self.held_page = None
        self.pages.clear()
        self.s2, self.query_pa = ((None, True),) * 2, (None,) * 3
        await self.env.idle(4, reset=False)
        self.emit("reset", tick=self.env.last_tick, aborted=old)
        return old

    async def cancel(self, uop, *, flush_self=False):
        assert all(self.uops[uid].dispatched for uid in self.active_uops)
        doomed = [self.uops[uid] for uid in self.active_uops if self.uops[uid].rob_order > uop.rob_order or flush_self and uid == uop.uid]
        assert all(not item.retired_by_rob for item in doomed)
        cut = uop.start if flush_self else uop.end
        assert self.head <= cut <= self.tail
        old = sorted(uid for item in doomed for uid in item.flows)
        if self.pending:
            assert self.pending[1] not in old
        self.held_page = None
        seen = []
        for index in range(35):
            await self.step(issue=False, dispatch=False, advance_rob=False,
                            redirect=Redirect(index == 0, uop.rob, flush_self), sbuffer_ready=(False, False))
            if self.env.observed["io_toLsqEnqCtrl_sqRedirectPtr_valid"]:
                actual = read_ptr(self.env.observed, "io_toLsqEnqCtrl_sqRedirectPtr_bits_")
                assert actual == cut % 256
                seen.append({"tick": self.env.last_tick, "end": actual})
            if index >= 8 and not self.env.observed["io_toLsqEnqCtrl_sqRecoverStall"]:
                break
        assert seen and index < 34
        for item in doomed:
            self.active_uops.remove(item.uid)
        for uid in old:
            assert uid not in self.completed
            self.cancelled.add(uid)
            self.pages.discard(uid)
            del self.live[self.all[uid].position]
        self.s2 = ((None, True),) * 2
        self.tail = self.dispatched_tail = cut
        self.next_rob = uop.rob_order + int(not flush_self)
        self.emit("cancel", tick=self.env.last_tick, cut=cut, cancelled=old, recovery=seen)
        return old
