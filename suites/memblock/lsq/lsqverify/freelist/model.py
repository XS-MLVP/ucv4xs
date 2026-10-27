"""Independent ownership ledger: no RTL matrix, pointers, or DUT reads."""
from __future__ import annotations

from collections import deque

from .types import Expected, Facts, Observation


class FreeListModel:
    def __init__(self, size: int, preallocate: bool, width: int = 3, banks: int = 4):
        self.size, self.preallocate, self.width, self.banks = size, preallocate, width, banks
        self.reset_pending = None
        self.restart()

    def restart(self):
        self.available = deque(range(self.size))
        self.owned = set()
        self.ownership_order = []
        self.waiting = [set() for _ in range(self.banks)]
        self.selected = ()
        self.advertised = self.size
        self.served = self.recycled = 0
        self.returned_before = set()
        self.previous_allocate = 0
        self.was_empty = False
        self.notification_age = {}
        self.cycle_number = 0

    @property
    def offered(self):
        return min(self.width, self.advertised if self.preallocate else len(self.available))

    def expected(self):
        return Expected(tuple(list(self.available)[:self.width]), self.offered,
                        self.size - len(self.available), not self.available)

    def advance(self, obs: Observation) -> Facts:
        if obs.reset:
            active = len(self.available) < self.size or any(self.waiting) or self.selected
            kind = "active" if active or self.reset_pending == "active" else "initial"
            self.restart()
            self.reset_pending = kind
            return Facts()
        n = obs.confirmation_mask.bit_count()
        incoming = tuple(i for i in range(self.size) if obs.return_mask >> i & 1)
        if n > self.offered:
            raise ValueError(f"illegal allocation: {n} > valid prefix {self.offered}")
        if not set(incoming) <= self.owned:
            raise ValueError(f"return of non-owned slot: {set(incoming)-self.owned}")
        before_free = len(self.available)
        non_fifo_return = incoming and set(incoming) != set(self.ownership_order[:len(incoming)])
        allocated = tuple(self.available.popleft() for _ in range(n))
        remaining_before_recycle = len(self.available)
        recycled = self.selected
        next_batch = []
        priority_over_age = False
        for bank in self.waiting:
            if bank:
                item = min(bank)
                priority_over_age |= any(self.notification_age[other] < self.notification_age[item] for other in bank)
                bank.remove(item)
                next_batch.append(item)
        self.available.extend(recycled)
        self.selected = tuple(next_batch)
        self.owned.update(allocated)
        self.owned.difference_update(incoming)
        self.ownership_order.extend(allocated)
        self.ownership_order = [item for item in self.ownership_order if item not in incoming]
        for item in incoming:
            self.waiting[item % self.banks].add(item)
            self.notification_age[item] = self.cycle_number
        self.advertised = remaining_before_recycle

        scenes = []
        if self.reset_pending:
            scenes.append("FL-RESET." + self.reset_pending)
            self.reset_pending = None
        if n:
            scenes.append("FL-ALLOC." + {1: "single", 2: "partial", 3: "full"}[n])
            if obs.confirmation_mask != (1 << n) - 1:
                scenes.append("FL-ALLOC.sparse")
        elif not incoming and not recycled and not any(self.waiting) and not self.selected:
            scenes.append("FL-IDLE." + ("available" if before_free else "empty"))
        if before_free in (0, 1, 2):
            scenes.append("FL-CAPACITY." + {0: "exhausted", 1: "one_remaining", 2: "two_remaining"}[before_free])
        if before_free == 0:
            self.was_empty = True
        if self.was_empty and self.offered:
            scenes.append("FL-CAPACITY.recovered")
            self.was_empty = False
        if incoming and before_free == 0 and not recycled:
            scenes.append("FL-RETURN.delayed")
        if set(allocated) & self.returned_before:
            scenes.append("FL-RETURN.reused")
        counts = [sum(i % self.banks == bank for i in incoming) for bank in range(self.banks)]
        if max(counts, default=0) > 1:
            scenes.append("FL-CONGESTION.one_bank")
        if sum(bool(c) for c in counts) > 1:
            scenes.append("FL-CONGESTION.multibank")
        if incoming and (recycled or next_batch):
            scenes.append("FL-CONGESTION.continuing_notifications")
        if incoming and n:
            scenes.append("FL-OVERLAP.notify_and_allocate")
        if recycled and n:
            scenes.append("FL-OVERLAP.recycle_and_allocate")
        if self.served // self.size != (self.served + n) // self.size:
            scenes.append("FL-WRAP.allocate_wrap")
        if self.recycled // self.size != (self.recycled + len(recycled)) // self.size:
            scenes.append("FL-WRAP.return_wrap")
        if self.preallocate:
            if n and self.previous_allocate:
                scenes.append("FL-PREFETCH.continuous")
            if n == self.width and self.previous_allocate in (1, 2):
                scenes.append("FL-PREFETCH.after_partial")
            if recycled and before_free == 0 and self.offered == 0:
                scenes.append("FL-PREFETCH.refill_wait")
        if non_fifo_return:
            scenes.append("FL-ORDER.non_fifo_returns")
        if priority_over_age:
            scenes.append("FL-ORDER.priority_over_notification_age")
        self.served += n
        self.recycled += len(recycled)
        self.previous_allocate = n
        self.returned_before.update(incoming)
        self.cycle_number += 1
        self.check_partition()
        return Facts(allocated, incoming, recycled, tuple(scenes))

    def check_partition(self):
        groups = [set(self.available), self.owned, set(self.selected), *self.waiting]
        assert len(self.ownership_order) == len(self.owned) and set(self.ownership_order) == self.owned
        assert len(self.available) == len(set(self.available)), "duplicate available slot"
        assert sum(map(len, groups)) == self.size
        assert set().union(*groups) == set(range(self.size))
        for i, group in enumerate(groups):
            assert all(not group & other for other in groups[:i]), "ownership overlap"
