from collections import deque
from dataclasses import asdict, dataclass
import json

from suites.memblock.lsq.testbenches.rar.checker import compare
from suites.memblock.lsq.testbenches.rar.transactions import Inputs
from suites.memblock.lsq.testbenches.rar.transactions import Query
from suites.memblock.lsq.testbenches.rar.transactions import QueuePtr
from suites.memblock.lsq.testbenches.rar.transactions import Redirect
from suites.memblock.lsq.testbenches.rar.transactions import Release
from suites.memblock.lsq.testbenches.rar.transactions import RobPtr


@dataclass(frozen=True)
class OwnedRecord:
    """Request-owned RAR lifecycle, never a reference-model event."""

    uid: int
    slot: int
    rob_order: int
    lq_position: int
    query: Query


@dataclass(frozen=True)
class ReturnedRecord:
    item: OwnedRecord
    causes: tuple[str, ...]


@dataclass(frozen=True)
class OwnershipChange:
    allocated: tuple[OwnedRecord, ...] = ()
    freed: tuple[ReturnedRecord, ...] = ()
    needed: tuple[bool, ...] = ()


class RarEnv:
    def __init__(self, key, spec, driver, before, after, model, coverage, trace):
        self.key, self.spec, self.driver = key, spec, driver
        self.before, self.after, self.model, self.coverage, self.trace = before, after, model, coverage, trace
        self.last_tick = -1
        self.checked_cycles = 0
        self.head_input = 0
        self.next_rob_entry = 2
        self.observed = None
        # Independent request-only ownership.  Slot identities come from the
        # contract's free-pool sequence (notify N, select N+1, free N+2); the
        # reference model is consulted only by the comparison/coverage path.
        self.entries = {}
        self.available = list(range(spec["size"]))
        self.free_slots = self.available
        self.free_count = len(self.available)
        self.waiting = [set() for _ in range(spec["free_width"])]
        self.selected = ()
        self.uid_sequence = 0
        self.accepted_history = deque(((None,) * spec["query_width"],) * 2)
        self.rob_anchor = None

    def _rob_decode(self, pointer, *, observe=False):
        """Unwrap an encoded ROB slot into a nearby program-order timeline."""
        if not 0 <= pointer.value < self.spec["rob_entries"]:
            raise ValueError("ROB value outside configured entries")
        raw = 2 * (int(pointer.flag) * self.spec["rob_entries"] + pointer.value) + int(not pointer.former)
        period = 4 * self.spec["rob_entries"]
        if self.rob_anchor is None:
            value = raw
        else:
            base = (self.rob_anchor - raw) // period
            choices = [raw + period * n for n in (base, base + 1)]
            distance = min(abs(item - self.rob_anchor) for item in choices)
            closest = [item for item in choices if abs(item - self.rob_anchor) == distance]
            if len(closest) != 1:
                raise ValueError("ambiguous ROB half-ring age outside legal domain")
            value = closest[0]
        if observe:
            self.rob_anchor = value if self.rob_anchor is None else max(self.rob_anchor, value)
        return value

    async def cycle(self, queries=(), *, head=None, release=Release(), redirect=Redirect(), revoke_last=(), revoke_older=(), reset=False):
        if isinstance(queries, dict):
            queries = tuple(queries.get(i, Query()) for i in range(self.spec["query_width"]))
        elif not queries:
            queries = (Query(),) * self.spec["query_width"]
        if head is not None:
            self.head_input = head
        width = self.spec["query_width"]
        inp = Inputs(tuple(queries), tuple(i in revoke_last for i in range(width)), tuple(i in revoke_older for i in range(width)),
                     QueuePtr.encode(self.head_input), redirect, release, reset)
        accepted = await self.driver.send(inp)
        while True:
            pre, post = await self.before.recv(), await self.after.recv()
            assert self.last_tick < post.event.tick <= accepted.tick and pre.event.tick + 1 == post.event.tick
            self.last_tick = post.event.tick
            if post.event.tick == accepted.tick:
                assert pre.value[0] == inp, ("requested/observed RAR input mismatch", inp, pre.value[0])
            change = self.check_cycle(pre, post)
            if post.event.tick == accepted.tick:
                return change

    def check_cycle(self, pre, post):
        inp, actual_before = pre.value
        post_input, actual_after = post.value
        record = {"pre_tick": pre.event.tick, "post_tick": post.event.tick, "input": asdict(inp),
                  "post_input": asdict(post_input), "before": asdict(actual_before), "after": asdict(actual_after), "checked": False}
        try:
            assert inp == post_input, "sampling phase must precede the driver's return to idle"
            old = self.model.outputs_for(inp)
            record["expected_before"] = asdict(old)
            if not inp.reset:
                compare(actual_before, old, phase="before", tick=pre.event.tick)
            change = self.model.advance(inp, actual_before.ready)
            expected = self.model.outputs_for(post_input)
            record.update(expected_after=asdict(expected), change=asdict(change))
            scenes = self.coverage.discover(inp, change, self.model, actual_before, actual_after)
            self.coverage.sample(scenes, post.event.tick, checked=False)
            if not inp.reset:
                compare(actual_after, expected, phase="after", tick=post.event.tick)
                self.coverage.confirm(scenes, inp, change, self.model, actual_before, actual_after, post.event.tick)
                self.checked_cycles += 1
                record["checked"] = True
            self.observed = actual_after
            return self._update_ledger(inp, actual_before)
        except BaseException as error:
            record["error"] = repr(error)
            raise
        finally:
            self.trace.write(json.dumps(record, ensure_ascii=False) + "\n")
            if not record["checked"]:
                self.trace.flush()

    def _context(self, inp):
        """Unwrap public RAR pointers with the documented half-ring contracts."""
        size = self.spec["lq_entries"]
        if not 0 <= inp.head.value < size:
            raise ValueError("ldWbPtr outside configured LQ entries")
        raw = int(inp.head.flag) * size + inp.head.value
        delta = (raw - self.head_input) % (2 * size)
        if delta > size:
            raise ValueError("ldWbPtr moved backwards or outside an unambiguous epoch")
        head = self.head_input + delta
        orders = tuple(self._rob_decode(query.rob, observe=True) if query.valid else None
                       for query in inp.queries)
        cutoff = self._rob_decode(inp.redirect.rob, observe=True) if inp.redirect.valid else None
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
            return cutoff is not None and (order > cutoff or
                                           inp.redirect.flush_self and order == cutoff)

        needed = tuple(query.valid and positions[i] > head and not flushed(orders[i])
                       for i, query in enumerate(inp.queries))
        return head, orders, tuple(positions), needed, flushed

    def _reset_ledger(self):
        self.entries.clear()
        self.available = list(range(self.spec["size"]))
        self.free_slots = self.available
        self.free_count = len(self.available)
        self.waiting = [set() for _ in range(self.spec["free_width"])]
        self.selected = ()
        self.accepted_history = deque(((None,) * self.spec["query_width"],) * 2)
        self.rob_anchor = None

    def _update_ledger(self, inp, actual_before):
        """Stimulus ledger from sampled requests and contract-timed ownership."""
        if inp.reset:
            self._reset_ledger()
            self.head_input = 0
            return OwnershipChange()
        head, orders, positions, needed, flushed = self._context(inp)
        width = self.spec["query_width"]
        accepted_slots = [None] * width
        freed = []
        for slot, item in self.entries.items():
            causes = tuple(reason for reason, active in (
                ("head", item.lq_position <= head), ("redirect", flushed(item.rob_order)),
                ("revoke_one", any(inp.revoke_last[lane] and self.accepted_history[-1][lane] == slot for lane in range(width))),
                ("revoke_two", any(inp.revoke_older[lane] and self.accepted_history[0][lane] == slot for lane in range(width)))) if active)
            if causes:
                freed.append(ReturnedRecord(item, causes))
        accepting = tuple(lane for lane in range(width) if needed[lane] and actual_before.ready[lane])
        if len(accepting) > len(self.available):
            raise AssertionError(("allocation outside independently advertised prefix", accepting,
                                  len(self.available)))
        for released in freed:
            del self.entries[released.item.slot]
        allocated = []
        for lane in accepting:
            slot = self.available.pop(0)
            assert slot not in self.entries, ("allocated slot still owned", slot)
            self.uid_sequence += 1
            self.entries[slot] = OwnedRecord(self.uid_sequence, slot, orders[lane],
                                              positions[lane], inp.queries[lane])
            allocated.append(self.entries[slot])
            accepted_slots[lane] = slot
        returned = self.selected
        next_batch = []
        for bank in self.waiting:
            if bank:
                item = min(bank)
                bank.remove(item)
                next_batch.append(item)
        self.available.extend(returned)
        self.selected = tuple(next_batch)
        # Notifications enter the bank backlog after this edge's selection,
        # so they become selectable on the following edge (N, N+1, N+2).
        for released in freed:
            slot = released.item.slot
            self.waiting[slot % len(self.waiting)].add(slot)
        self.free_slots = self.available
        self.free_count = len(self.available)
        self.accepted_history.append(tuple(accepted_slots))
        self.accepted_history.popleft()
        groups = [set(self.available), set(self.entries), set(self.selected), *self.waiting]
        assert sum(map(len, groups)) == self.spec["size"], (groups, self.spec["size"])
        assert len(set().union(*groups)) == self.spec["size"]
        for index, group in enumerate(groups):
            assert all(not group & other for other in groups[:index]), "RAR ownership overlap"
        self.head_input = head
        return OwnershipChange(tuple(allocated), tuple(freed), needed)

    async def reset(self):
        self.head_input = 0
        self.next_rob_entry = 2
        for _ in range(6):
            await self.cycle(reset=True)
        await self.idle(3)

    async def idle(self, cycles=1):
        return [await self.cycle() for _ in range(cycles)]

    def request(self, position, address, *, rob=None, nc=True, data=True):
        if rob is None:
            rob = RobPtr.encode(self.next_rob_entry)
            self.next_rob_entry += 1
        return Query(True, rob, QueuePtr.encode(position), address, data, nc)

    async def probe(self, addresses, *, rob=None, lanes=None, expect=None):
        addresses = tuple(addresses)
        lanes = tuple(range(len(addresses))) if lanes is None else tuple(lanes)
        if rob is None:
            oldest = min((item.rob_order for item in self.entries.values()), default=2 * self.next_rob_entry)
            rob = RobPtr.encode(oldest // 2 - 1)
        queries = {lane: Query(True, rob, QueuePtr.encode(self.head_input), address) for lane, address in zip(lanes, addresses, strict=True)}
        change = await self.cycle(queries)
        if expect is not None:
            for lane, wanted in zip(lanes, expect, strict=True):
                assert self.observed.responses[lane].valid and self.observed.responses[lane].nuke == wanted
        return change

    async def advance_head(self, target):
        if target < self.head_input:
            raise ValueError("head must not move backwards")
        changes = []
        while self.head_input < target:
            changes.append(await self.cycle(head=min(target, self.head_input + 8)))
        return changes

    async def settle_free(self):
        for _ in range(self.spec["size"] + 6):
            if not any(self.waiting) and not self.selected:
                await self.idle(3)
                return
            await self.cycle()
        raise AssertionError("RAR return pipeline did not settle")
