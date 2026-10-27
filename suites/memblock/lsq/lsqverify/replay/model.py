"""Replay ownership/dependency specification, independent of DUT internals.

Queue insertion age is a scalar UID. The real three age matrices, allocation
registers and scheduling registers are never read as answers. Producer hints
are retained by arrival time, and the outgoing selection owns a snapshot.
"""
from collections import deque
from dataclasses import asdict, dataclass, replace

from lsqverify.freelist.model import FreeListModel
from lsqverify.freelist.types import Observation
from lsqverify.uncache_entry.model import is_younger
from .types import Cause, Enqueue, Inputs, L2Hint, LqWakeup, Refill, StoreWakeup, TlbHint, Uop


def sq_serial(ptr):
    if not 0 <= ptr.value < 64:
        raise ValueError("SQ pointer outside physical size")
    return int(ptr.first) * 128 + int(ptr.second) * 64 + ptr.value


def sq_after(left, right):
    distance = (sq_serial(left) - sq_serial(right)) % 256
    if distance == 128:
        raise ValueError("ambiguous half-ring SQ age")
    return 0 < distance < 128


def sq_exclusive_after(left, right):
    # SMF owns the Load's EXCLUSIVE SQ boundary, anchored by real dequeue.
    # Full128 older flows are still pending, not an arbitrary half-ring age.
    # LoadQueueReplay.scala853-858/520-523 keeps this owner blocked at full.
    return (sq_serial(left) - sq_serial(right)) % 256 == 128 or sq_after(left, right)


def lq_after(left, right):
    distance = ((120 * int(left.flag) + left.value) - (120 * int(right.flag) + right.value)) % 240
    if distance == 120:
        raise ValueError("ambiguous half-ring LQ age")
    return 0 < distance < 120


def is_canceled(ptr, red):
    return red.valid and (is_younger(ptr, red.rob) or red.flush_self and ptr == red.rob)


@dataclass
class Owner:
    uid: int
    slot: int
    input_lane: int
    request: Enqueue
    version: int = 0
    blocked: bool = True
    scheduled: bool = False
    issued: bool = False
    mshr: int = 0


@dataclass(frozen=True)
class Selection:
    uid: int
    slot: int
    uop: Uop


class ReplayModel:
    def __init__(self):
        self.edge = self.sequence = 0
        self.restart()

    def restart(self):
        self.pool = FreeListModel(120, True)
        self.owners = {}
        self.mshr_history = [0] * 120
        self.selection = [None] * 3
        self.selection_valid = [False] * 3
        self.cooldown = [0] * 3
        self.last_fired = [False] * 3
        self.address_delay = (StoreWakeup(),) * 2
        self.data_delay = (StoreWakeup(),) * 2
        self.refill_history = deque(((Refill(),) * 2,) * 3, maxlen=3)
        self.tlb_history = deque((TlbHint(),) * 2, maxlen=2)
        self.mmio_delay = self.nc_delay = LqWakeup()
        self.last_beat_unlock = set()
        self.perf_delay = self.perf = (0,) * 13
        self.special_count = 0
        self.special_latched = False
        self.special_head = None
        self.previous_head = None
        self.special_output = False

    def visible_owner(self, bank, inp):
        selection = self.selection[bank]
        if not self.selection_valid[bank] or selection is None:
            return None
        owner = self.owners.get(selection.slot)
        if owner is None or owner.uid != selection.uid or is_canceled(selection.uop.rob, inp.redirect):
            return None
        return owner

    def payload(self, bank, owner):
        selection, req = self.selection[bank], owner.request
        u = selection.uop
        size = req.aligned_type if req.vector else (u.operation >> 1) & 7
        byte_count = 1 << (size & 3)
        mask = req.mask if req.vector else (((1 << byte_count) - 1) << (req.vaddr % 16)) & 0xFFFF
        result = {"entrance": 2 if req.causes & ((1 << Cause.CACHE_MISS) | (1 << Cause.UNCACHE)) else 8,
                  "accessType_instrType": 2 if req.vector else 1,
                  "uop_isRVC": int(u.rvc), "uop_ftqPtr_flag": int(u.ftq.flag), "uop_ftqPtr_value": u.ftq.value,
                  "uop_ftqOffset": u.offset, "uop_fuOpType": u.operation, "uop_rfWen": int(u.integer_write), "uop_fpWen": int(u.fp_write),
                  "uop_vecWen": int(u.vector_write), "uop_v0Wen": int(u.v0_write), "uop_pdest": u.destination,
                  "uop_robIdx_flag": int(u.rob.flag), "uop_robIdx_value": u.rob.value, "uop_robIdx_isFormer": int(u.rob.former),
                  "uop_perfDebugInfo_runahead_checkpoint_id": u.checkpoint, "uop_storeSetHit": int(u.store_set_hit),
                  "uop_waitSqIdx_first_flag": int(u.wait_sq.first), "uop_waitSqIdx_second_flag": int(u.wait_sq.second), "uop_waitSqIdx_value": u.wait_sq.value,
                  "uop_loadWaitBit": int(u.load_wait), "uop_loadWaitStrict": int(u.strict),
                  "uop_lqIdx_flag": int(u.lq.flag), "uop_lqIdx_value": u.lq.value,
                  "uop_sqIdx_first_flag": int(u.sq.first), "uop_sqIdx_second_flag": int(u.sq.second), "uop_sqIdx_value": u.sq.value,
                  "vaddr": req.vaddr, "fullva": req.vaddr, "size": size, "mask": mask, "mshrId": owner.mshr, "replayQueueIdx": owner.slot,
                  "forwardDChannel": int(bool(req.causes & 1 << Cause.CACHE_MISS)), "uncacheReplay": int(bool(req.causes & 1 << Cause.UNCACHE)),
                  "ncReplay": int(req.nc and bool(req.causes & 1 << Cause.UNCACHE)),
                  **{f"uop_exceptionVec_{bit}": 0 for bit in (23, 19, 15, 7, 6)}}
        return result

    def expected(self, inp):
        result = {"io_lqFull": int(not self.pool.available), "io_replayAllocate": int(bool(self.owners)), "io_specialMode": int(self.special_output),
                  **{f"io_perf_{i}_value": value for i, value in enumerate(self.perf)}}
        for bank in range(3):
            owner = self.visible_owner(bank, inp)
            prefix = f"io_replay_{bank}_"
            result[prefix + "valid"] = int(owner is not None)
            if owner:
                result.update({prefix + "bits_" + key: value for key, value in self.payload(bank, owner).items()})
        return result

    def choose(self, bank, inp):
        candidates = [owner for slot, owner in self.owners.items() if slot % 3 == bank and not owner.scheduled and
                      (not owner.blocked or owner.request.causes == 1 << Cause.TLB_MISS and inp.fast_tlb.valid and inp.fast_tlb.identity == owner.request.tlb_id)]
        base = int(inp.writeback.flag) * 120 + inp.writeback.value
        head = [owner for owner in candidates if owner.request.uop.lq == inp.writeback]
        near = [owner for owner in candidates if (int(owner.request.uop.lq.flag) * 120 + owner.request.uop.lq.value - base) % 240 in (1, 2, 3)]
        if head or near:
            return min(head or near, key=lambda owner: owner.slot)
        high = [owner for owner in candidates if owner.request.causes & ((1 << Cause.CACHE_MISS) | (1 << Cause.FORWARD_FAILURE) | (1 << Cause.UNCACHE))]
        return min(high or candidates, key=lambda owner: owner.uid, default=None)

    def address_ready(self, req, inp):
        block = req.address_sq
        pointer_ready = sq_after(inp.address_ready, block)
        bit_ready = not req.uop.strict and bool(inp.address_bits >> block.value & 1) and sq_after(inp.upper, block)
        wake_ready = any(w.valid and w.sq == block and (sq_serial(w.sq) - sq_serial(inp.dequeue)) % 256 < 64 for w in self.address_delay)
        return pointer_ready or bit_ready or inp.sq_empty or wake_ready

    def data_ready(self, req, inp):
        block = req.data_sq
        return sq_after(inp.data_ready, block) or bool(inp.data_bits >> block.value & 1) or inp.sq_empty or any(w.valid and w.sq == block for w in self.data_delay)

    def initial_blocked(self, req, inp):
        cause = req.causes.bit_length() - 1
        if cause in (Cause.CACHE_REPLAY, Cause.WAY_PREDICTION, Cause.BANK_CONFLICT, Cause.VIOLATION):
            return False
        if cause == Cause.TLB_MISS:
            slow = self.tlb_history[0]
            older = self.tlb_history[1]
            hit = slow.valid and (slow.replay_all or slow.identity == req.tlb_id)
            hit |= req.unaligned_head and older.valid and (older.replay_all or older.identity == req.tlb_id)
            hit |= inp.fast_tlb.valid and inp.fast_tlb.identity == req.tlb_id
            return not (req.tlb_full or hit or req.special_request and req.uop.rob != inp.head)
        if cause == Cause.CACHE_MISS and req.handled:
            age_limit = 3 if req.unaligned_head else 2
            return not any(w.valid and w.mshr == req.mshr for cycle in list(self.refill_history)[:age_limit] for w in cycle)
        if cause == Cause.FORWARD_FAILURE:
            return not any(w.valid and w.sq == req.data_sq for w in (*self.data_delay, *inp.data_writes))
        return True

    def update_blocked(self, owner, inp):
        req = owner.request
        cause = req.causes.bit_length() - 1
        unblocked = False
        if cause == Cause.ADDRESS_DEPENDENCE:
            unblocked = self.address_ready(req, inp)
        elif cause == Cause.TLB_MISS:
            hint = self.tlb_history[0]
            unblocked = hint.valid and (hint.replay_all or hint.identity == req.tlb_id)
            unblocked |= not owner.scheduled and inp.fast_tlb.valid and inp.fast_tlb.identity == req.tlb_id
        elif cause == Cause.FORWARD_FAILURE:
            unblocked = self.data_ready(req, inp)
        elif cause == Cause.CACHE_MISS:
            unblocked = any(w.valid and w.mshr == owner.mshr for w in self.refill_history[0])
        elif cause == Cause.RAR_CAPACITY:
            unblocked = not inp.rar_full or not lq_after(req.uop.lq, inp.writeback)
        elif cause == Cause.RAW_CAPACITY:
            unblocked = not inp.raw_full or not sq_after(req.uop.sq, inp.address_ready)
        elif cause == Cause.UNCACHE:
            unblocked = any(w.valid and w.lq == req.uop.lq for w in (self.mmio_delay, self.nc_delay))
        elif cause == Cause.STORE_MULTI_MATCH:
            unblocked = not sq_exclusive_after(req.uop.sq, inp.dequeue)
        if (owner.uid, owner.version) in self.last_beat_unlock:
            unblocked = True
        return owner.blocked and not unblocked

    def advance(self, inp):
        self.edge += 1
        before = [asdict(owner) for owner in self.owners.values()]
        if inp.reset:
            self.restart()
            return {"reset": True, "before": before}
        incoming = [req for req in inp.enqueues if req.valid]
        feedback_slots = [req.slot for req in incoming if req.replay_feedback]
        if len(set(feedback_slots)) != len(feedback_slots):
            raise ValueError("multiple feedback inputs target one replay owner")
        for req in incoming:
            if req.need_replay and (req.causes.bit_count() != 1 or req.causes == 1 << 12):
                raise ValueError("unsupported normal cause domain")
            if req.replay_feedback and (req.slot not in self.owners or not self.owners[req.slot].issued):
                raise ValueError("feedback must follow a real output handshake for that live owner")
        need_new = [req.valid and req.need_replay and not req.replay_feedback and not is_canceled(req.uop.rob, inp.redirect) for req in inp.enqueues]
        if sum(need_new) > self.pool.offered:
            raise ValueError("new replay allocation outside actual preallocated capacity")
        visible = [self.visible_owner(bank, inp) for bank in range(3)]
        fired = [owner is not None and inp.ready[bank] for bank, owner in enumerate(visible)]
        chosen = [self.choose(bank, inp) for bank in range(3)]
        picked, fire_uids = [], []
        for bank in range(3):
            selection = self.selection[bank]
            stale = selection is not None and (selection.slot not in self.owners or self.owners[selection.slot].uid != selection.uid)
            canceled = self.selection_valid[bank] and selection is not None and is_canceled(selection.uop.rob, inp.redirect)
            can_take = self.cooldown[bank] < 12 and (not self.selection_valid[bank] or fired[bank]) or stale or canceled
            if fired[bank]:
                visible[bank].issued = True
                fire_uids.append(visible[bank].uid)
            if can_take:
                candidate = chosen[bank]
                self.selection[bank] = Selection(candidate.uid, candidate.slot, replace(candidate.request.uop, exceptions=0)) if candidate else None
                self.selection_valid[bank] = candidate is not None
                if candidate:
                    picked.append(candidate.uid)
            elif fired[bank]:
                self.selection_valid[bank] = False
            self.cooldown[bank] = ((self.cooldown[bank] + 1) % 16) if self.last_fired[bank] and fired[bank] or self.cooldown[bank] >= 12 else 0
        unlock_next, blocked = set(), {}
        for slot, owner in self.owners.items():
            blocked[slot] = self.update_blocked(owner, inp)
            if owner.request.causes == 1 << Cause.CACHE_MISS:
                hits = [hint for hint in inp.l2_hints if hint.valid and hint.mshr == owner.mshr]
                if len(hits) > 1:
                    raise ValueError("two L2 hints hit the same replay MSHR")
                if hits:
                    first = owner.request.last_beat if hits[0].keyword else not owner.request.last_beat
                    if first:
                        blocked[slot] = False
                    else:
                        unlock_next.add((owner.uid, owner.version))
        for slot, owner in self.owners.items():
            owner.blocked = blocked[slot]
            if owner.uid in picked:
                owner.scheduled = True
        freed = {slot for slot, owner in self.owners.items() if is_canceled(owner.request.uop.rob, inp.redirect)}
        completed, updates = [], []
        for lane, req in enumerate(inp.enqueues):
            if not req.valid or not req.replay_feedback:
                continue
            owner = self.owners[req.slot]
            if not req.need_replay:
                freed.add(req.slot)
                completed.append(owner.uid)
            elif not is_canceled(req.uop.rob, inp.redirect):
                owner.request = req
                owner.version += 1
                owner.blocked = self.initial_blocked(req, inp)
                owner.scheduled = owner.issued = False
                if req.handled:
                    owner.mshr = self.mshr_history[req.slot] = req.mshr
                updates.append(owner.uid)
        removed = [asdict(self.owners[slot]) for slot in sorted(freed)]
        for slot in freed:
            del self.owners[slot]
        allocated = []
        offers = self.pool.expected()
        slots = iter(offers.slots)
        for lane, req in enumerate(inp.enqueues):
            if not need_new[lane]:
                continue
            slot = next(slots)
            assert slot not in self.owners
            self.sequence += 1
            if req.handled:
                self.mshr_history[slot] = req.mshr
            owner = Owner(self.sequence, slot, lane, req, blocked=self.initial_blocked(req, inp), mshr=self.mshr_history[slot])
            self.owners[slot] = owner
            allocated.append(asdict(owner))
        self.pool.advance(Observation(False, sum(int(need) << lane for lane, need in enumerate(need_new)), sum(1 << slot for slot in freed), offers.slots, None, None, None))
        assert self.pool.owned == set(self.owners)
        events = (sum(req.valid and not req.replay_feedback for req in inp.enqueues), sum(fired),
                  sum(owner is not None and not inp.ready[bank] for bank, owner in enumerate(visible)), int(not offers.slots),
                  *(sum(req.valid and not req.replay_feedback and bool(req.causes >> cause & 1) for req in inp.enqueues) for cause in (9, 10, 11, 2, 3, 8, 5, 4, 6)))
        # full is pool emptiness before this edge, not "offered slots < 3".
        events = (*events[:3], int(offers.empty), *events[4:])
        self.perf, self.perf_delay = self.perf_delay, tuple(events)
        trigger = any(req.valid and req.special_eligible and req.uop.rob == inp.head and not is_canceled(req.uop.rob, inp.redirect) for req in inp.enqueues)
        self.special_output = self.special_latched and inp.head == self.special_head
        if self.previous_head is not None and inp.head != self.previous_head:
            self.special_count = 0
            self.special_latched = False
        elif not self.special_latched and (trigger or self.special_count):
            if self.special_count == 2047:
                self.special_latched = True
                self.special_head = inp.head
            else:
                self.special_count += 1
        self.previous_head = inp.head
        self.address_delay, self.data_delay = inp.address_wakeups, inp.data_wakeups
        self.refill_history.appendleft(inp.refills)
        self.tlb_history.appendleft(inp.slow_tlb)
        self.mmio_delay, self.nc_delay = inp.mmio, inp.nc
        self.last_beat_unlock = unlock_next
        self.last_fired = fired
        return {"reset": False, "before": before, "allocated": allocated, "freed": removed, "completed": completed,
                "updates": updates, "selected": picked, "fired": fire_uids, "events": events,
                "offered": offers.offered, "cooldown": list(self.cooldown), "special_count": self.special_count}
