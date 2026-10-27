"""Independent public ordinary-memory actor for true mixed Wrapper cases.

Immutable byte producers, global ROB order, actual Sbuffer fragments, Load S3,
replay grants and cancel/reuse are separate obligations. No reference reads.
"""
from dataclasses import asdict, dataclass, replace
from itertools import groupby

from lsqverify.forward.types import Query, Translation
from lsqverify.load_queue.types import Load
from lsqverify.lsq_wrapper.types import Address, Data, Dispatch, Inputs
from lsqverify.psq.types import Attributes, SecondPage
from lsqverify.raw.types import FtqPtr, SqPtr
from lsqverify.replay.types import Enqueue, Uop
from lsqverify.vlq.types import QueuePtr, Redirect, RobPtr


def rob_number(rob):
    return 2 * (160 * int(rob.flag) + rob.value) + int(not rob.former)


@dataclass(frozen=True)
class StoreOwner:
    position: int
    rob: RobPtr
    vaddr: int
    paddr: int
    size: int = 3
    value: int = 0x8877665544332211
    second_page: object = None

    def address(self, *, tail=False, miss=False):
        cross = self.vaddr % 16 + (1 << self.size) > 16
        va = self.vaddr // 16 * 16 + 16 if tail else self.vaddr
        pa = (self.second_page if self.second_page is not None else self.paddr // 16 * 16 + 16) if tail else self.paddr
        return Address(True, self.position % 64, (0x200 if self.size == 4 else 0) | self.size << 1,
                       va, pa, self.size, tlb_miss=miss, unaligned=bool(self.vaddr % (1 << self.size)),
                       cross_word=cross, last=not cross or tail, rob=self.rob,
                       ftq=FtqPtr(bool(self.position % 2), 17 + self.position % 16),
                       ftq_offset=5 + self.position % 8, rvc=bool(self.position % 2),
                       mask=((1 << (1 << self.size)) - 1) << (self.vaddr % 16) & 65535)

    def data(self):
        return Data(True, SqPtr.encode(self.position), self.address().fu_op, self.value)

    def words(self):
        words = []
        parts = 2 if self.address().cross_word else 1
        for part in range(parts):
            va = self.vaddr // 16 * 16 + 16 * part
            pa = self.second_page if part and self.second_page is not None else self.paddr // 16 * 16 + 16 * part
            mask = value = 0
            for offset in range(1 << self.size):
                byte = self.vaddr + offset - va
                if 0 <= byte < 16:
                    mask |= 1 << byte
                    value |= (self.value >> (8 * offset) & 255) << (8 * byte)
            words.append((va, pa, mask, value))
        return words


def cached_load(position, rob, sq, va, pa, *, size=3):
    return Load(Enqueue(True, Uop(rob=RobPtr.encode(rob) if isinstance(rob, int) else rob,
                                 lq=QueuePtr.encode(position), sq=SqPtr.encode(sq), operation=size << 1,
                                 ftq=FtqPtr(bool(position % 2), 37 + position % 16),
                                 offset=7 + position % 8, rvc=bool(position % 2), checkpoint=0x5000 + position),
                        vaddr=va, mask=((1 << (1 << size)) - 1) << (va % 16) & 65535),
                fullva=va, paddr=pa, update_address=True)


class MemoryOwners:
    def __init__(self, env):
        self.env = env
        self.base = Inputs(pending=RobPtr.encode(9), pending_next=RobPtr.encode(9))
        self.stores, self.loads, self.active_loads, self.program = {}, [], {}, []
        self.sq_head, self.sequence, self.load_released = 0, 0, 0
        self.pending_s2 = (None, None)
        self.fragment_order, self.fragments_fired, self.cancelled = [], [], []

    async def cycle(self, **fields):
        attrs = tuple(Attributes(last=last) if uid is not None else Attributes() for uid, last in
                      (item if item is not None else (None, True) for item in self.pending_s2))
        options = dict(attributes=attrs)
        options.update(fields)
        packet = replace(self.base, **options)
        old_s2 = self.pending_s2
        await self.env.cycle(packet)
        pre, post, tick = self.env.pre_observed, self.env.observed, self.env.last_tick
        for item in old_s2:
            if item is not None and item[1]:
                self.stores[item[0]]["s2_done"] = True
        self.pending_s2 = [None, None]
        for lane, address in enumerate(packet.addresses):
            if address.valid:
                pos = self.sq_head + (address.slot - self.sq_head) % 64
                state = self.stores[pos]
                assert address.rob == state["owner"].rob and state["dispatched"]
                if not address.tlb_miss:
                    state["address_parts"] += 1
                    self.pending_s2[lane] = (pos, address.last)
        for data in packet.data:
            if data.valid:
                pos = self.sq_head + (data.sq.value - self.sq_head) % 64
                state = self.stores[pos]
                assert data.sq == SqPtr.encode(pos) and not state["data_sent"]
                state["data_sent"] = True
        for load in packet.loads:
            q = load.execution
            if q.valid:
                state = self.active_loads[q.uop.lq]
                assert state["load"].execution.uop == q.uop
                if q.replay_feedback:
                    assert state.get("grant") == q.slot and not q.need_replay
                if not q.need_replay and load.update_address:
                    assert not state["sent"]
                    state["sent"] = True
        for bank in range(3):
            p = f"io_replay_{bank}_"
            if pre[p + "valid"] and packet.replay_ready[bank]:
                key = QueuePtr(bool(pre[p + "bits_uop_lqIdx_flag"]), pre[p + "bits_uop_lqIdx_value"])
                state = self.active_loads[key]
                assert "grant" not in state
                state["grant"] = pre[p + "bits_replayQueueIdx"]
        for lane in range(2):
            p = f"io_sbuffer_req_{lane}_"
            if pre[p + "valid"] and packet.sbuffer_ready[lane]:
                pos, part = self.fragment_order[len(self.fragments_fired)]
                state = self.stores[pos]
                va, pa, mask, value = state["owner"].words()[part]
                bits = sum(255 << (8 * b) for b in range(16) if mask >> b & 1)
                self.env.expect({p + "bits_vaddr": va, p + "bits_addr": pa, p + "bits_mask": mask,
                                 p + "bits_data": value, p + "bits_wline": 0}, "original ordinary Store PA bytes actually consumed", before=True,
                                masks={p + "bits_data": bits})
                assert part not in state["consumed"]
                state["consumed"].add(part)
                state["last_fire"] = tick
                self.fragments_fired.append((pos, part))
                self.env.emit("memory_sbuffer_fire", uid=state["uid"], sq_position=pos, part=part, lane=lane)
        actual_head = 128 * post["io_sqDeqPtr_first_flag"] + 64 * post["io_sqDeqPtr_second_flag"] + post["io_sqDeqPtr_value"]
        delta = (actual_head - self.sq_head) % 256
        assert delta <= 2 and post["io_toLsqEnqCtrl_sqDeq_valid"] == int(bool(delta))
        if delta:
            assert post["io_toLsqEnqCtrl_sqDeq_bits"] == delta
        for pos in range(self.sq_head, self.sq_head + delta):
            state = self.stores[pos]
            assert state["s2_done"] and state["data_sent"] and not state["completed"]
            assert state["consumed"] == set(range(len(state["owner"].words()))) and state["last_fire"] + 2 == tick
            state["completed"] = True
            self.env.emit("memory_store_complete", uid=state["uid"], sq_position=pos)
        self.sq_head += delta
        if post["io_toLsqEnqCtrl_lqDeq_valid"]:
            count = post["io_toLsqEnqCtrl_lqDeq_bits"]
            live = [state for state in self.loads if not state["completed"] and not state["cancelled"]]
            assert 0 < count <= len(live)
            for state in live[:count]:
                assert state["sent"]
                state["completed"] = True
                self.load_released += 1
                self.env.emit("memory_load_complete", uid=state["uid"], lq=asdict(state["load"].execution.uop.lq))
        assert not pre["io_uncache_req_valid"] and not pre["io_mmioStout_valid"] and not pre["io_cmoOpReq_valid"]

    async def idle(self, count=1, **fields):
        for _ in range(count):
            await self.cycle(**fields)

    async def dispatch(self, stores=(), loads=(), *, load_lane=None, store_lane=None):
        items, store_ranges = [], {}
        assert load_lane is None or store_lane is None
        for owner in stores:
            assert owner.position not in self.stores
            self.sequence += 1
            state = dict(uid=self.sequence, owner=owner, dispatched=False, address_parts=0, data_sent=False,
                         s2_done=False, consumed=set(), completed=False)
            self.stores[owner.position] = state
            self.fragment_order.extend((owner.position, part) for part in range(len(owner.words())))
        for rob, group in groupby(stores, key=lambda s: s.rob):
            group = list(group)
            assert len(group) <= 16 and [s.position for s in group] == list(range(group[0].position, group[-1].position + 1))
            item = Dispatch(True, 2, rob, len(group), store_end=SqPtr.encode(group[-1].position + 1))
            items.append(item)
            store_ranges[item] = tuple(owner.position for owner in group)
        for load in loads:
            key = load.execution.uop.lq
            assert key not in self.active_loads or self.active_loads[key]["cancelled"] or self.active_loads[key]["completed"]
            self.sequence += 1
            state = dict(uid=self.sequence, load=load, sent=False, completed=False, cancelled=False)
            self.loads.append(state)
            self.active_loads[key] = state
        for rob, group in groupby(loads, key=lambda load: load.execution.uop.rob):
            group = list(group)
            assert 0 < len(group) <= 16
            items.append(Dispatch(True, 1, rob, len(group), load_start=group[0].execution.uop.lq))
        items.sort(key=lambda item: rob_number(item.rob))
        self.program.extend(item.rob for item in items)
        self.env.emit("memory_allocate", domain="NORMAL-PUBLIC-PRODUCER", stores=[asdict(s) for s in stores],
                      loads=[asdict(load) for load in loads], dispatch=[asdict(d) for d in items])
        for first in range(0, len(items), 8):
            batch = items[first:first + 8]
            for item in batch:
                if item.need_alloc == 2:
                    # Keep the producer's absolute generation, not the raw
                    # modulo256 SQ encoding after multiple complete wraps.
                    for pos in store_ranges[item]:
                        self.stores[pos]["dispatched"] = True
            if load_lane is None and store_lane is None:
                packet = tuple(batch) + (Dispatch(),) * (8 - len(batch))
            else:
                lane = load_lane if load_lane is not None else store_lane
                assert len(items) == 1 and items[0].need_alloc == (1 if load_lane is not None else 2) and lane in range(8)
                packet = tuple(batch[0] if source == lane else Dispatch() for source in range(8))
            await self.cycle(dispatch=packet)

    async def write(self, position, *, lane=0, address=True, data=True, miss=False):
        state, addresses, values = self.stores[position], [Address(), Address()], [Data(), Data()]
        owner = state["owner"]
        if address:
            addresses[lane] = owner.address(miss=miss)
        if data:
            values[1 - lane] = owner.data()
        await self.cycle(addresses=tuple(addresses), data=tuple(values))
        if address and not miss and owner.address().cross_word:
            if owner.second_page is not None:
                pages = [SecondPage(), SecondPage()]
                pages[lane] = SecondPage(True, SqPtr.encode(position), owner.second_page)
                for _ in range(40):
                    await self.cycle(second_pages=tuple(pages))
                    if self.env.pre_observed[f"io_sta_unalignQueueReq_{lane}_ready"]:
                        break
                else:
                    raise AssertionError("real UQ did not accept original second physical page")
            tails = [Address(), Address()]
            tails[lane] = owner.address(tail=True)
            await self.cycle(addresses=tuple(tails))

    async def write_all(self, positions=None):
        for position in sorted(self.stores) if positions is None else positions:
            state = self.stores[position]
            if not state["completed"] and (not state["address_parts"] or not state["data_sent"]):
                assert 0 <= position - self.sq_head < 64
                await self.write(position, lane=position % 2, address=not state["address_parts"], data=not state["data_sent"])
        await self.idle(5)

    async def forward(self, load, lane, *, query=None, kill=False):
        u = load.execution.uop
        query = query or Query(True, load.execution.vaddr, u.sq, (u.operation >> 1) & 7,
                               wait=u.load_wait, strict=u.strict, wait_sq=u.wait_sq)
        queries, translations = [Query()] * 3, [Translation()] * 3
        queries[lane], translations[lane] = query, Translation(load.paddr, kill)
        await self.cycle(queries=tuple(queries))
        await self.cycle(translations=tuple(translations))
        return self.env.observed

    async def execute(self, loads):
        for first in range(0, len(loads), 3):
            batch = list(loads[first:first + 3])
            await self.cycle(loads=tuple(batch) + (Load(),) * (3 - len(batch)))

    async def replay_complete(self, load):
        key = load.execution.uop.lq
        for _ in range(50):
            bank = next((b for b in range(3) if self.env.observed[f"io_replay_{b}_valid"] and
                         self.env.observed[f"io_replay_{b}_bits_uop_lqIdx_value"] == key.value), None)
            if bank is not None:
                break
            await self.cycle()
        assert bank is not None
        await self.cycle(replay_ready=tuple(b == bank for b in range(3)))
        slot = self.active_loads[key]["grant"]
        feedback = replace(load, execution=replace(load.execution, need_replay=False, causes=0, replay_feedback=True, slot=slot))
        await self.execute([feedback])

    async def recover_load_suffix(self, cutoff):
        victims = [state for state in self.loads if not state["completed"] and not state["cancelled"] and
                   rob_number(state["load"].execution.uop.rob) >= rob_number(cutoff)]
        assert victims and all(rob_number(state["owner"].rob) < rob_number(cutoff) for state in self.stores.values())
        await self.cycle(redirect=Redirect(True, cutoff, True))
        for state in victims:
            assert not state["sent"]
            state["cancelled"] = True
            self.cancelled.append(state)
        lq = None
        for _ in range(30):
            await self.cycle()
            if self.env.observed["io_toLsqEnqCtrl_lqRedirectPtr_valid"]:
                lq = QueuePtr(bool(self.env.observed["io_toLsqEnqCtrl_lqRedirectPtr_bits_flag"]),
                              self.env.observed["io_toLsqEnqCtrl_lqRedirectPtr_bits_value"])
            if lq is not None and not self.env.observed["io_toLsqEnqCtrl_lqRecoverStall"] and not self.env.observed["io_toLsqEnqCtrl_sqRecoverStall"]:
                await self.idle(4)
                self.env.emit("memory_cancelled", uids=[state["uid"] for state in victims], actual_lq_recovery=asdict(lq))
                return lq
        raise AssertionError("real shared recovery did not return both branches to dispatch permission")

    async def finish(self, *, pending=None):
        live = [s for s in self.loads if not s["cancelled"] and not s["sent"]]
        await self.execute([s["load"] for s in live])
        assert all(state["completed"] or state["s2_done"] and state["data_sent"] for state in self.stores.values())
        if pending is None:
            last = max(self.program, key=rob_number)
            pending = RobPtr.encode(160 * int(last.flag) + last.value + 1)
        self.base = replace(self.base, pending=pending, pending_next=pending, sbuffer_ready=(True, True))
        for _ in range(500):
            await self.cycle()
            if all(s["completed"] for s in self.stores.values()) and all(s["completed"] or s["cancelled"] for s in self.loads):
                if self.env.observed["io_lqEmpty"] and self.env.observed["io_sqEmpty"]:
                    await self.idle(8)
                    assert not self.env.observed["io_uncache_req_valid"] and not self.env.observed["io_replayAllocate"]
                    for old in self.cancelled:
                        assert any(new["uid"] != old["uid"] and new["completed"] and
                                   new["load"].execution.uop.lq.value == old["load"].execution.uop.lq.value for new in self.loads)
                    self.env.emit("memory_fully_completed", stores=len(self.stores), loads=sum(s["completed"] for s in self.loads),
                                  cancelled=len(self.cancelled), fragments=len(self.fragments_fired))
                    return
        raise AssertionError("original mixed memory owners did not really complete all effects/credits")
