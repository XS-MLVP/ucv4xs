"""Semantic RAR records, scalar age timelines and an independently tested free pool."""
from collections import deque
from copy import copy
from dataclasses import replace

from suites.memblock.lsq.freelist.model import FreeListModel
from suites.memblock.lsq.freelist.types import Observation as FreeObservation
from suites.memblock.lsq.vlq.model import RobTimeline

from .types import Change, Entry, Freed, Outputs, Release, Response


def partial_address(address):
    """Fold the line tag in 11-bit chunks, then add the five reverse-fold bits."""
    tag, high = address >> 6, 0
    while tag:
        high ^= tag & 0x7FF
        tag >>= 11
    reversed_five = sum(((address >> (11 + bit)) & 1) << (4 - bit) for bit in range(5))
    return (high << 5) | (((address >> 6) & 31) ^ reversed_five)


class LoadQueueRarModel:
    def __init__(self, spec):
        self.spec = spec
        self.edge = self.uid_sequence = 0
        self.reset_kind = None
        self.restart()

    def restart(self):
        self.head = 0
        self.entries = {}
        self.free = FreeListModel(self.spec["size"], False, self.spec["query_width"], self.spec["free_width"])
        self.rob = RobTimeline(self.spec["rob_entries"])
        self.responses = (Response(),) * self.spec["query_width"]
        self.perf = (0, 0)
        self.previous_fire = self.previous_allocations = self.previous_nuke_responses = 0
        self.previous_release = Release()
        self.release_pending = set()
        self.accepted_history = deque(((None,) * self.spec["query_width"],) * 2)

    def context(self, inp):
        size = self.spec["lq_entries"]
        if not 0 <= inp.head.value < size:
            raise ValueError("ldWbPtr outside configured LQ entries")
        raw = int(inp.head.flag) * size + inp.head.value
        delta = (raw - self.head) % (2 * size)
        if delta > size:
            raise ValueError("ldWbPtr moved backwards or outside an unambiguous epoch")
        head = self.head + delta
        timeline = copy(self.rob)
        orders = tuple(timeline.decode(query.rob, observe=True) if query.valid else None for query in inp.queries)
        cutoff = timeline.decode(inp.redirect.rob, observe=True) if inp.redirect.valid else None
        positions = []
        for query in inp.queries:
            if not query.valid:
                positions.append(None)
                continue
            if not 0 <= query.lq.value < size:
                raise ValueError("query LQ pointer outside configured entries")
            distance = (int(query.lq.flag) * size + query.lq.value - head) % (2 * size)
            if distance == size:
                raise ValueError("query outside the legal LQ half-ring window")
            positions.append(head + (distance if distance < size else distance - 2 * size))
        def flushed(order):
            return cutoff is not None and (order > cutoff or inp.redirect.flush_self and order == cutoff)
        need = tuple(query.valid and positions[i] > head and not flushed(orders[i]) for i, query in enumerate(inp.queries))
        return head, timeline, orders, tuple(positions), need, flushed

    def outputs_for(self, inp):
        if inp.reset:
            ready = (True,) * self.spec["query_width"]
        else:
            _, _, _, _, need, _ = self.context(inp)
            offset, ready = 0, []
            for required in need:
                ready.append(not required or offset < len(self.free.available))
                offset += int(required)
            ready = tuple(ready)
        return Outputs(ready, self.responses, len(self.free.available) < self.spec["replay_free_threshold"], *self.perf)

    def advance(self, inp, observed_ready):
        self.edge += 1
        before = tuple(self.entries.values())
        old_available, old_head = len(self.free.available), self.head
        if inp.reset:
            if any(q.valid for q in inp.queries) or inp.release.valid or inp.redirect.valid or any((*inp.revoke_last, *inp.revoke_older)):
                raise ValueError("RAR reset requires idle inputs")
            self.reset_kind = self.reset_kind or ("active" if old_available < self.spec["size"] else "initial")
            self.restart()
            return Change(before=before, reset_kind=self.reset_kind)
        self.reset_kind = None
        head, timeline, orders, positions, needed, flushed = self.context(inp)
        matches = tuple(tuple(item.uid for item in before
                              if item.key == partial_address(query.paddr) and item.rob_order > orders[i] and item.released)
                        if query.valid else () for i, query in enumerate(inp.queries))
        responses = tuple(Response(query.valid, bool(matches[i])) for i, query in enumerate(inp.queries))
        released_next = {item.slot for item in before if inp.release.valid and item.key == partial_address(inp.release.paddr)}
        freed = []
        for item in before:
            causes = []
            if item.lq_position <= head:
                causes.append("head")
            if flushed(item.rob_order):
                causes.append("redirect")
            if any(inp.revoke_last[i] and self.accepted_history[-1][i] == item.slot for i in range(self.spec["query_width"])):
                causes.append("revoke_one")
            if any(inp.revoke_older[i] and self.accepted_history[0][i] == item.slot for i in range(self.spec["query_width"])):
                causes.append("revoke_two")
            if causes:
                freed.append(Freed(item, tuple(causes)))
                del self.entries[item.slot]
        allocated, accepted_slots, accepted_uids = [], [], []
        available = list(self.free.available)
        for lane, query in enumerate(inp.queries):
            if not needed[lane] or not observed_ready[lane]:
                accepted_slots.append(None)
                accepted_uids.append(None)
                continue
            slot = available[len(allocated)]
            concurrent = inp.release.valid and inp.release.paddr >> 6 == query.paddr >> 6
            previous = self.previous_release.valid and self.previous_release.paddr >> 6 == query.paddr >> 6
            source = "nc" if query.nc else "concurrent" if query.data_valid and concurrent else "previous" if query.data_valid and previous else "none"
            alias = not query.nc and query.data_valid and not concurrent and not previous and any(
                r.valid and partial_address(r.paddr) == partial_address(query.paddr) for r in (inp.release, self.previous_release))
            self.uid_sequence += 1
            item = Entry(self.uid_sequence, slot, orders[lane], positions[lane], query, partial_address(query.paddr),
                         source != "none", source, self.edge if source != "none" else 0, alias)
            if slot in self.entries:
                raise AssertionError("new RAR allocation overwrites an owned slot")
            self.entries[slot] = item
            allocated.append(item)
            accepted_slots.append(slot)
            accepted_uids.append(item.uid)
        marked = []
        for slot in self.release_pending:
            if slot in self.entries and not self.entries[slot].released:
                self.entries[slot] = replace(self.entries[slot], released=True, release_source="late", release_edge=self.edge)
                marked.append(self.entries[slot].uid)
        confirmation = sum((uid is not None) << lane for lane, uid in enumerate(accepted_uids))
        return_mask = sum(1 << f.item.slot for f in freed)
        free_change = self.free.advance(FreeObservation(False, confirmation, return_mask, (), None, None, None))
        assert free_change.allocated == tuple(item.slot for item in allocated)
        assert set(self.entries) == self.free.owned, "RAR records and free-pool ownership diverged"
        old_fire, old_allocations = self.previous_fire, self.previous_allocations
        self.perf = (old_fire, self.previous_nuke_responses)
        self.previous_fire = sum(query.valid and observed_ready[i] for i, query in enumerate(inp.queries))
        self.previous_allocations = len(allocated)
        self.previous_nuke_responses = sum(response.valid and response.nuke for response in self.responses)
        self.responses = responses
        self.previous_release = inp.release if inp.release.valid else Release()
        self.release_pending = released_next
        self.accepted_history.append(tuple(accepted_slots))
        self.accepted_history.popleft()
        self.rob, self.head = timeline, head
        return Change(before, tuple(allocated), tuple(freed), matches, needed, tuple(accepted_uids), orders, positions,
                      tuple(marked), free_change.recycled, old_available, len(self.free.available), old_head, head,
                      old_fire, old_allocations)
