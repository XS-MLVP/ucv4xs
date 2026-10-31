"""Opt-in full128 Load-exclusive domain, not a generic circular-age relaxation.

The RAW context below differs from the frozen legacy context only by accepting
distance==half as the forward exclusive tail. All allocation, selection, perf,
free-pool latency, comparison/knownness and physical-byte safety stay inherited.
Admission requires the producer contract docs/contracts/lsq-raw-exclusive-endpoint.md.
"""
from copy import copy

from suites.memblock.lsq.lsq_wrapper.model import WrapperModel
from suites.memblock.lsq.raw.model import LoadQueueRawModel
from suites.memblock.lsq.replay.model import ReplayModel, sq_exclusive_after
from suites.memblock.lsq.replay.types import Cause


class ExclusiveRawModel(LoadQueueRawModel):
    def context(self, inp):
        size = self.spec["sq_physical_entries"]
        half = size * self.spec["sq_multiple"]
        if not 0 <= inp.head.value < size:
            raise ValueError("address-ready SQ pointer outside physical entries")
        raw = int(inp.head.first) * half + int(inp.head.second) * size + inp.head.value
        delta = (raw - self.head) % (2 * half)
        if delta > half and not self.allow_head_recovery:
            raise ValueError("address-ready SQ pointer moved backwards or outside legal epoch")
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
            # A Load owns the end AFTER all allocated older Store flows, not a
            # physical Store slot. Full128 pending older flows is a legal end.
            positions.append(head + (distance if distance <= half else distance - 2 * half))
        needed = tuple(q.valid and positions[lane] > head and not flushed(orders[lane]) for lane, q in enumerate(inp.queries))
        return head, timeline, orders, store_orders, tuple(positions), needed, flushed


class ExclusiveReplayModel(ReplayModel):
    def update_blocked(self, owner, inp):
        if owner.request.causes != 1 << Cause.RAW_CAPACITY:
            return super().update_blocked(owner, inp)
        unblocked = not inp.raw_full or not sq_exclusive_after(owner.request.uop.sq, inp.address_ready)
        if (owner.uid, owner.version) in self.last_beat_unlock:
            unblocked = True
        return owner.blocked and not unblocked


class ExclusiveWrapperModel(WrapperModel):
    def __init__(self):
        super().__init__()
        self.load.raw = ExclusiveRawModel(self.load.raw.spec, allow_head_recovery=True)
        self.load.replay = ExclusiveReplayModel()
