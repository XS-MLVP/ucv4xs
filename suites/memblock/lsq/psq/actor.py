"""External VSQ/ROB, STA/STD and fair bus actors with an independent UID ledger.

All stimulus decisions use this ledger and public pins. The parent stage model
is never read to decide readiness, permission, responses or completion.
"""
from dataclasses import asdict, dataclass, replace
import json
import random

from suites.memblock.lsq.forward.types import Query, Translation
from suites.memblock.lsq.raw.types import SqPtr
from suites.memblock.lsq.vlq.types import RobPtr
from .checks import read_ptr
from .types import Address, Attributes, Data, SecondPage


@dataclass
class Owner:
    uid: int
    position: int
    address: Address
    data: Data
    attributes: Attributes
    rob: RobPtr
    second_page: object = None
    address_parts: int = 0
    data_sent: bool = False
    s2_done: bool = False
    page_sent: bool = False
    retry: bool = False
    retried: bool = False
    finished: bool = False


class PsqActor:
    def __init__(self, env, *, seed=1):
        self.env, self.rng = env, random.Random(seed)
        self.head = self.tail = self.retired = self.sequence = 0
        self.live, self.all, self.parts, self.finish_ticks = {}, {}, {}, {}
        self.completed, self.cancelled, self.aborted = set(), set(), set()
        self.pending = self.held_page = None
        self.page_reservations = set()
        self.s2 = ((None, True),) * 2
        self.queries = (None,) * 3
        self.emit("start", seed=seed)

    def emit(self, event, **fields):
        self.env.actor_journal.write(json.dumps({"nodeid": self.env.nodeid, "event": event, **fields}) + "\n")

    def add(self, *, size=3, offset=0, memory=0, cbo=None, page=False, exception=False, retry=False):
        assert self.tail - self.head < 128 and memory in (0, 1, 2, 7)
        assert cbo is None or memory == 0
        assert size in range(5) and (memory == 0 or size <= 3 and offset // 8 == (offset + (1 << size) - 1) // 8)
        self.sequence += 1
        uid, position = self.sequence, self.tail
        va = 0x100000 + uid * 8192 + (4092 if page else offset)
        pa = 0xA000000 + uid * 8192 + va % 4096
        cross = va % 16 + (1 << size) > 16
        assert not page or cross
        op = cbo * 2 + 1 if cbo is not None else (0x200 if size == 4 else 0) | size << 1
        value = int.from_bytes(bytes((uid * 19 + byte * 31) % 256 for byte in range(16)), "little")
        address = Address(True, position % 64, op, va, pa, size, hyper=bool(uid % 2), unaligned=bool(va % (1 << size)), cross_word=cross, last=not cross)
        attrs = Attributes(nc=memory == 1, mmio=memory in (2, 7), memory=memory < 4, exception=exception)
        owner = Owner(uid, position, address, Data(True, position % 64, op, value), attrs, RobPtr.encode(uid % 320, former=bool(uid % 2)),
                      (0xD000 + uid) * 4096 if page else None, retry=retry)
        self.live[position] = self.all[uid] = owner
        self.parts[uid] = set()
        self.tail += 1
        self.emit("allocate", owner=asdict(owner))
        return uid

    def rob_controls(self):
        while self.retired < self.tail:
            owner = self.live.get(self.retired)
            assert owner is not None
            ordinary = not owner.address.fu_op & 1 and not owner.attributes.nc and not owner.attributes.mmio
            if not owner.s2_done or not owner.data_sent or owner.attributes.exception or not (ordinary or owner.finished):
                break
            self.retired += 1
        owner = self.live.get(self.retired)
        special = owner and (owner.address.fu_op & 1 or owner.attributes.nc or owner.attributes.mmio)
        permit = bool(special and owner.s2_done and owner.data_sent and not owner.attributes.exception)
        return {"enqueue": SqPtr.encode(self.tail), "retired": SqPtr.encode(self.retired), "precommit_valid": permit,
                "precommit": SqPtr.encode(self.retired + 1 if permit else self.retired), "rob": owner.rob if owner else RobPtr()}

    def prepared(self, *, fair, issue, query):
        rng = self.rng
        controls = self.rob_controls()
        controls.update(addresses=(Address(), Address()), data=(Data(), Data()),
                        attributes=tuple(replace(self.all[uid].attributes, last=last) if uid is not None else Attributes() for uid, last in self.s2),
                        second_pages=(SecondPage(), SecondPage()), queries=(Query(),) * 3,
                        translations=tuple(Translation(pa) if pa is not None else Translation() for pa in self.queries),
                        cache_response=False, uncache_response=False, uncache_ack_valid=False, uncache_ack_to_load=False)
        r0 = fair or rng.random() < 0.7
        controls.update(sbuffer_ready=(r0, r0 and (fair or rng.random() < 0.65)), cache_ready=fair or rng.random() < 0.7,
                        uncache_ready=fair or rng.random() < 0.7, writeback_ready=fair or rng.random() < 0.65,
                        sbuffer_empty=fair or rng.random() < 0.7)
        if self.pending:
            kind, uid = self.pending
            if fair or rng.random() < 0.6:
                controls[{"cache": "cache_response", "io": "uncache_response", "nc": "uncache_ack_valid"}[kind]] = True
        candidates = [owner for pos, owner in sorted(self.live.items()) if pos - self.head < 64]
        addresses, data = [Address(), Address()], [Data(), Data()]
        if issue:
            address_candidates = [owner for owner in candidates if not owner.s2_done and owner.address_parts < (2 if owner.address.cross_word else 1)
                                  and (not owner.address.fu_op & 1 or owner.position <= self.retired)]
            rng.shuffle(address_candidates)
            for lane, owner in enumerate(address_candidates[:2 if fair else rng.randrange(3)]):
                if owner.address_parts and owner.second_page is not None and not owner.page_sent:
                    continue
                addr = owner.address
                if owner.address_parts:
                    addr = replace(addr, vaddr=addr.vaddr // 16 * 16 + 16,
                                   paddr=owner.second_page if owner.second_page is not None else addr.paddr // 16 * 16 + 16, last=True)
                if owner.retry and not owner.retried:
                    addr = replace(addr, tlb_miss=True)
                addresses[lane] = addr
            data_candidates = [owner for owner in candidates if not owner.data_sent and (not owner.address.fu_op & 1 or owner.position <= self.retired)]
            rng.shuffle(data_candidates)
            for lane, owner in enumerate(data_candidates[:2 if fair else rng.randrange(3)]):
                data[lane] = owner.data
            if self.held_page is None and len(self.page_reservations) < 2:
                address_ready = read_ptr(self.env.observed, "io_toLoadQueue_stAddrReadySqPtr_")
                page_owner = next((owner for owner in candidates if owner.second_page is not None and not owner.page_sent and owner.position % 256 == address_ready), None)
                if page_owner:
                    self.held_page = (page_owner.uid, rng.randrange(2))
        if self.held_page:
            uid, lane = self.held_page
            owner = self.all[uid]
            pages = [SecondPage(), SecondPage()]
            pages[lane] = SecondPage(True, SqPtr.encode(owner.position), owner.second_page)
            controls["second_pages"] = tuple(pages)
        if query and self.tail - self.head < 128:
            options = [owner for owner in candidates if owner.s2_done and not owner.address.cross_word]
            if options:
                owner, lane = rng.choice(options), rng.randrange(3)
                queries = [Query()] * 3
                queries[lane] = Query(True, owner.address.vaddr, SqPtr.encode(self.tail), owner.address.size)
                controls["queries"] = tuple(queries)
        controls.update(addresses=tuple(addresses), data=tuple(data))
        return controls

    async def step(self, *, fair=False, issue=True, query=False, **overrides):
        controls = self.prepared(fair=fair, issue=issue, query=query)
        controls.update(overrides)
        old_s2 = self.s2
        await self.env.cycle(**controls)
        inp, pre, post, tick = self.env.controls, self.env.pre_observed, self.env.observed, self.env.last_tick
        assert read_ptr(pre) == self.head % 256
        for uid, last in old_s2:
            if uid is not None and last and uid not in self.cancelled:
                self.all[uid].s2_done = True
        self.s2 = [(None, True), (None, True)]
        for lane, addr in enumerate(inp.addresses):
            if addr.valid:
                owner = next(owner for pos, owner in self.live.items() if pos - self.head < 64 and pos % 64 == addr.slot)
                if addr.tlb_miss:
                    owner.retried = True
                else:
                    owner.address_parts += 1
                    self.s2[lane] = (owner.uid, addr.last)
        for item in inp.data:
            if item.valid:
                owner = next(owner for pos, owner in self.live.items() if pos - self.head < 64 and pos % 64 == item.slot)
                assert not owner.data_sent
                owner.data_sent = True
        if self.held_page:
            uid, lane = self.held_page
            if pre[f"io_fromStoreUnit_unalignQueueReq_{lane}_ready"]:
                self.all[uid].page_sent = True
                self.page_reservations.add(uid)
                self.held_page = None
        if self.pending:
            kind, uid = self.pending
            response = (kind == "cache" and inp.cache_response and pre["io_toDCache_resp_ready"] or kind == "io" and inp.uncache_response or
                        kind == "nc" and inp.uncache_ack_valid and not inp.uncache_ack_to_load)
            if response:
                if kind == "nc":
                    self.all[uid].finished = True
                    self.finish_ticks[uid] = tick
                self.pending = None
        if pre["io_toDCache_req_valid"] and inp.cache_ready:
            assert self.pending is None
            owner = next(owner for owner in self.live.values() if owner.address.paddr == pre["io_toDCache_req_bits_address"])
            self.pending = ("cache", owner.uid)
        if pre["io_toUncacheBuffer_req_valid"] and inp.uncache_ready:
            assert self.pending is None
            owner = next(owner for owner in self.live.values() if owner.address.vaddr == pre["io_toUncacheBuffer_req_bits_vaddr"])
            self.pending = ("nc" if owner.attributes.nc else "io", owner.uid)
        if pre["io_writeBack_valid"] and inp.writeback_ready:
            owner = next(owner for owner in self.live.values() if owner.rob == inp.rob)
            assert not owner.finished
            owner.finished = True
            self.finish_ticks[owner.uid] = tick
        consumed = []
        for lane in range(2):
            prefix = f"io_writeToSbuffer_req_{lane}_"
            if not pre[prefix + "valid"] or not inp.sbuffer_ready[lane]:
                continue
            owner, part = next((owner, part) for owner in self.live.values() for part in range(2 if owner.address.cross_word else 1)
                               if owner.address.vaddr // 16 * 16 + part * 16 == pre[prefix + "bits_vaddr"])
            assert part not in self.parts[owner.uid]
            va = owner.address.vaddr // 16 * 16 + part * 16
            pa = owner.second_page if part and owner.second_page is not None else owner.address.paddr // 16 * 16 + part * 16
            original = 0 if owner.address.fu_op & 1 and owner.address.fu_op >> 1 & 7 == 3 else owner.data.data
            mask = value = 0
            for byte in range(1 << owner.address.size):
                if va <= owner.address.vaddr + byte < va + 16:
                    offset = owner.address.vaddr + byte - va
                    mask |= 1 << offset
                    value |= (original >> (8 * byte) & 255) << (8 * offset)
            bits = sum(255 << (8 * byte) for byte in range(16) if mask >> byte & 1)
            assert pre[prefix + "bits_addr"] == pa and pre[prefix + "bits_mask"] == mask
            assert not ((pre[prefix + "bits_data"] ^ value) & bits)
            assert pre[prefix + "bits_wline"] == int(bool(owner.address.fu_op & 1 and owner.address.fu_op >> 1 & 7 == 3))
            self.parts[owner.uid].add(part)
            self.finish_ticks[owner.uid] = tick
            self.page_reservations.discard(owner.uid)
            consumed.append({"uid": owner.uid, "part": part})
        delta = (read_ptr(post) - self.head) % 256
        assert delta <= 2 and post["io_sqDeq_valid"] == int(bool(delta))
        if delta:
            assert post["io_sqDeq_bits"] == delta
        completed = []
        for pos in range(self.head, self.head + delta):
            owner = self.live[pos]
            uid = owner.uid
            assert uid not in self.completed and owner.s2_done and owner.data_sent and not owner.attributes.exception
            special = owner.address.fu_op & 1 or owner.attributes.nc or owner.attributes.mmio
            if special:
                assert owner.finished
                if owner.address.fu_op & 1 and owner.address.fu_op >> 1 & 7 == 3:
                    assert self.parts[uid] == {0}
                # NC may acknowledge while older ordinary words still drain.
                # handleFinish is only observed when this owner enters the
                # two-head deq window; acknowledgement is not a fixed-latency
                # SQ release. Require no early release and fair eventual drain.
                assert self.finish_ticks[uid] < tick
            else:
                assert self.parts[uid] == ({0, 1} if owner.address.cross_word else {0})
                assert self.finish_ticks[uid] + 2 == tick
            self.completed.add(uid)
            completed.append(uid)
            del self.live[pos]
        self.head += delta
        self.queries = tuple(next((owner.address.paddr for owner in self.all.values() if owner.address.vaddr == q.vaddr), 0) if q.valid else None for q in inp.queries)
        self.emit("step", tick=tick, head=self.head, tail=self.tail, retired=self.retired, consumed=consumed, completed=completed,
                  s1=[asdict(item) for item in inp.addresses], std=[asdict(item) for item in inp.data])
        return completed

    async def drain(self, limit=3000):
        for _ in range(limit):
            await self.step(fair=True)
            if not self.live and self.pending is None:
                for _ in range(4):
                    await self.step(fair=True)
                return
        raise AssertionError("external actor failed fair drain through real PSQ transfers")

    def checked(self, names, uids):
        assert set(uids) <= self.completed
        self.env.begin(names)
        self.env.finish(names)
        self.emit("checked", tick=self.env.last_tick, names=names, uids=list(uids), completed=sorted(self.completed), cancelled=sorted(self.cancelled), aborted=sorted(self.aborted))

    async def reset(self):
        old = sorted(owner.uid for owner in self.live.values())
        for _ in range(4):
            await self.env.cycle(reset=True, addresses=(Address(), Address()), data=(Data(), Data()), attributes=(Attributes(), Attributes()),
                                 second_pages=(SecondPage(), SecondPage()), queries=(Query(),) * 3, translations=(Translation(),) * 3,
                                 enqueue=SqPtr(), retired=SqPtr(), precommit_valid=False, redirect_valid=False,
                                 cache_response=False, uncache_response=False, uncache_ack_valid=False, sbuffer_ready=(False, False), writeback_ready=False)
        self.aborted.update(old)
        self.live.clear()
        self.head = self.tail = self.retired = 0
        self.pending = self.held_page = None
        self.s2, self.queries = ((None, True),) * 2, (None,) * 3
        self.page_reservations.clear()
        await self.env.cycle(reset=False)
        self.emit("reset", tick=self.env.last_tick, aborted=old)
        return old

    async def cancel_suffix(self, cut):
        assert self.head <= self.retired <= cut <= self.tail
        old = sorted(owner.uid for pos, owner in self.live.items() if pos >= cut)
        if self.pending:
            assert self.all[self.pending[1]].position < cut, "cannot cancel a permitted outstanding special store"
        self.tail = cut
        if self.held_page and self.held_page[0] in old:
            self.held_page = None
        for index in range(4):
            await self.step(issue=False, enqueue=SqPtr.encode(cut), redirect_valid=index == 0,
                            redirect=SqPtr.encode(cut), precommit_valid=False)
        for uid in old:
            owner = self.all[uid]
            assert uid not in self.completed
            self.cancelled.add(uid)
            self.page_reservations.discard(uid)
            del self.live[owner.position]
        self.emit("cancel", tick=self.env.last_tick, cut=cut, cancelled=old)
        return old
