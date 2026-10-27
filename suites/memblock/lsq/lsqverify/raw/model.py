"""Semantic conflict snapshots and scalar oldest selection, not an RTL age matrix."""
from collections import deque
from copy import copy
from dataclasses import replace

from lsqverify.freelist.model import FreeListModel
from lsqverify.freelist.types import Observation as FreeObservation
from lsqverify.vlq.model import RobTimeline

from .types import Change, Entry, Freed, Outputs, Rollback, Selection, Training


def address_match(load, store):
    shift = 6 if store.wline else 4
    return ((load.paddr ^ store.paddr) & ((1 << 28) - 1)) >> shift == 0


def rollback_for(job):
    item, store = job.winner, job.store
    if item is None or job.canceled or store.tlb_miss:
        return Rollback()
    query = item.query
    return Rollback(True, query.rob, query.ftq, query.ftq_offset, query.is_rvc, query.checkpoint,
                    store.ftq_flag, store.ftq_value, store.ftq_offset, store.is_rvc)


class LoadQueueRawModel:
    def __init__(self, spec, *, allow_head_recovery=False):
        self.spec = spec
        self.allow_head_recovery = allow_head_recovery
        self.edge = self.uid_sequence = self.job_sequence = 0
        self.reset_kind = None
        self.restart()

    def restart(self):
        self.head = 0
        self.entries = {}
        self.free = FreeListModel(self.spec["size"], True, self.spec["query_width"], self.spec["free_width"])
        self.rob = RobTimeline(self.spec["rob_entries"])
        self.accepted_history = deque(((None,) * self.spec["query_width"],) * 2)
        self.pending = []
        self.rollbacks = (Rollback(),) * self.spec["store_width"]
        self.training = Training()
        self.perf = (0, 0)
        self.previous_fire = self.previous_allocations = self.previous_rollback_event = 0

    def context(self, inp):
        size = self.spec["sq_physical_entries"]
        half = size * self.spec["sq_multiple"]
        if not 0 <= inp.head.value < size:
            raise ValueError("address-ready SQ pointer outside physical entries")
        raw = int(inp.head.first) * half + int(inp.head.second) * size + inp.head.value
        delta = (raw - self.head) % (2 * half)
        if delta > half and not self.allow_head_recovery:
            raise ValueError("address-ready SQ pointer moved backwards or outside legal epoch")
        # A standalone monotonic producer is the old leaf-test domain. The
        # actual StoreQueue also rewinds addrReadyPtr on its delayed recovery
        # (NewStoreQueue.scala1883-1887). Parent composition checks that real
        # public-history SQ feedback; use the nearby signed epoch here, not
        # an invented forward trip of nearly256 positions. No record resurrects.
        head = self.head + (delta - 2*half if delta > half else delta)
        timeline = copy(self.rob)
        orders = tuple(timeline.decode(q.rob, observe=True) if q.valid else None for q in inp.queries)
        store_orders = tuple(timeline.decode(s.rob, observe=True) if s.valid else None for s in inp.stores)
        cutoff = timeline.decode(inp.redirect.rob, observe=True) if inp.redirect.valid else None
        def flushed(order):
            return cutoff is not None and (order > cutoff or inp.redirect.flush_self and order == cutoff)
        positions = []
        for query in inp.queries:
            if not query.valid:
                positions.append(None)
                continue
            if not 0 <= query.sq.value < size:
                raise ValueError("query SQ pointer outside physical entries")
            raw_query = int(query.sq.first) * half + int(query.sq.second) * size + query.sq.value
            distance = (raw_query - head) % (2 * half)
            if distance == half:
                raise ValueError("query SQ pointer outside unambiguous legal half-ring")
            positions.append(head + (distance if distance < half else distance - 2 * half))
        needed = tuple(q.valid and positions[lane] > head and not flushed(orders[lane]) for lane, q in enumerate(inp.queries))
        return head, timeline, orders, store_orders, tuple(positions), needed, flushed

    def outputs_for(self, inp):
        if inp.reset:
            ready = (True,) * self.spec["query_width"]
        else:
            _, _, _, _, _, needed, _ = self.context(inp)
            offset, ready = 0, []
            for need in needed:
                ready.append(not need or offset < self.free.offered)
                offset += int(need)
            ready = tuple(ready)
        return Outputs(ready, not self.free.available, self.rollbacks, self.training, *self.perf)

    def advance(self, inp, observed_ready):
        self.edge += 1
        before = tuple(self.entries.values())
        old_available, old_offered, old_head = len(self.free.available), self.free.offered, self.head
        if inp.reset:
            if any(q.valid for q in inp.queries) or any(s.valid for s in inp.stores) or inp.redirect.valid or any((*inp.revoke_last, *inp.revoke_older)):
                raise ValueError("RAW reset requires idle inputs")
            self.reset_kind = self.reset_kind or ("active" if old_available < self.spec["size"] or self.pending else "initial")
            self.restart()
            return Change(before=before, reset_kind=self.reset_kind)
        self.reset_kind = None
        head, timeline, orders, store_orders, positions, needed, flushed = self.context(inp)
        freed, revoked_slots = [], set()
        for item in before:
            causes = []
            if item.sq_position <= head:
                causes.append("head")
            if flushed(item.rob_order):
                causes.append("redirect")
            if any(inp.revoke_last[lane] and self.accepted_history[-1][lane] == item.slot for lane in range(self.spec["query_width"])):
                causes.append("revoke_one")
                revoked_slots.add(item.slot)
            if any(inp.revoke_older[lane] and self.accepted_history[0][lane] == item.slot for lane in range(self.spec["query_width"])):
                causes.append("revoke_two")
                revoked_slots.add(item.slot)
            if causes:
                freed.append(Freed(item, tuple(causes)))
                del self.entries[item.slot]
        created = []
        for lane, store in enumerate(inp.stores):
            if not store.valid:
                continue
            eligible = [item for item in before if item.query.data_valid and item.rob_order > store_orders[lane]
                        and not flushed(item.rob_order) and item.slot not in revoked_slots
                        and address_match(item.query, store) and item.query.mask & store.mask]
            # Equal-identity duplicate loads are legal. Physical slot tie order
            # only chooses between semantically identical recovery payloads.
            winner = min(eligible, key=lambda item: (item.rob_order, -item.slot), default=None)
            self.job_sequence += 1
            created.append(Selection(self.job_sequence, self.edge, self.edge + self.spec["selection_registers"] - 1,
                                     lane, store, store_orders[lane], winner, tuple(item.uid for item in eligible)))
        canceled, pending = [], []
        for job in self.pending:
            if job.winner is not None and not job.canceled and flushed(job.winner.rob_order):
                job = replace(job, canceled=True)
                canceled.append(job.uid)
            pending.append(job)
        pending.extend(created)
        emitted = tuple(job for job in pending if job.due == self.edge)
        self.pending = [job for job in pending if job.due > self.edge]
        assert len({job.lane for job in emitted}) == len(emitted)
        rollbacks = [Rollback()] * self.spec["store_width"]
        for job in emitted:
            rollbacks[job.lane] = rollback_for(job)
        valid_jobs = [job for job in emitted if rollback_for(job).valid]
        train_job = min(valid_jobs, key=lambda job: (job.winner.rob_order, job.lane), default=None)
        training = Training()
        if train_job is not None:
            rb = rollback_for(train_job)
            training = Training(True, rb.ftq.value, rb.ftq_offset, rb.is_rvc,
                                rb.store_ftq_value, rb.store_ftq_offset, rb.store_is_rvc)
        allocated, accepted_slots, accepted_uids = [], [], []
        available = list(self.free.available)
        for lane, query in enumerate(inp.queries):
            if not needed[lane] or not observed_ready[lane]:
                accepted_slots.append(None)
                accepted_uids.append(None)
                continue
            self.uid_sequence += 1
            slot = available[len(allocated)]
            item = Entry(self.uid_sequence, slot, orders[lane], positions[lane], query)
            assert slot not in self.entries, "RAW allocation overwrites an owned slot"
            self.entries[slot] = item
            allocated.append(item)
            accepted_slots.append(slot)
            accepted_uids.append(item.uid)
        confirmation = sum((uid is not None) << lane for lane, uid in enumerate(accepted_uids))
        return_mask = sum(1 << f.item.slot for f in freed)
        free_change = self.free.advance(FreeObservation(False, confirmation, return_mask, (), None, None, None))
        assert free_change.allocated == tuple(item.slot for item in allocated)
        assert set(self.entries) == self.free.owned, "RAW records and free-pool ownership diverged"
        old_fire, old_allocations = self.previous_fire, self.previous_allocations
        self.perf = (old_fire, self.previous_rollback_event)
        self.previous_fire = sum(q.valid and observed_ready[lane] for lane, q in enumerate(inp.queries))
        self.previous_allocations = len(allocated)
        self.previous_rollback_event = int(any(rb.valid for rb in self.rollbacks))
        self.rollbacks, self.training = tuple(rollbacks), training
        self.accepted_history.append(tuple(accepted_slots))
        self.accepted_history.popleft()
        self.rob, self.head = timeline, head
        return Change(before, tuple(allocated), tuple(freed), needed, tuple(accepted_uids), orders, positions,
                      tuple(created), emitted, tuple(canceled), free_change.recycled, old_available,
                      len(self.free.available), old_offered, self.free.offered, old_head, head, old_fire, old_allocations)
