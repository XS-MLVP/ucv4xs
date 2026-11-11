from __future__ import annotations

from suites.memblock.lsq.testbenches.freelist.checker import compare
from suites.memblock.lsq.testbenches.freelist.transactions import Request


class FreeListEnv:
    def __init__(self, key, spec, driver, before, after, model, coverage):
        self.key, self.spec = key, spec
        self.driver, self.before, self.after = driver, before, after
        self.model, self.coverage = model, coverage
        self.checked_cycles = 0
        self.last_tick = -1
        self.obligations = []
        # Independent ownership ledger from accepted transaction responses.
        self.available = list(range(spec["size"]))
        self.owned = set()
        self.pending_returns = set()
        self.advertised = len(self.available)
        # Independent return lifecycle: one item per bank is selected each
        # cycle; selected items become available on the following cycle.
        self.waiting = [set() for _ in range(spec.get("banks", 4))]
        self.selected = ()
        self.recycled = ()

    async def cycle(self, allocate=0, returns=(), *, reset=False, confirmation_mask=None):
        request = Request(allocate, tuple(returns), reset, confirmation_mask)
        accepted = await self.driver.send(request)
        # The simulator may run idle edges across pytest's async fixture/test
        # handoff. Consume and CHECK those observations, never discard them or
        # treat one send() as exactly one globally observed cycle.
        while True:
            pre, post = await self.before.recv(), await self.after.recv()
            assert self.last_tick < post.event.tick <= accepted.tick
            assert pre.event.tick + 1 == post.event.tick
            self.last_tick = post.event.tick
            if post.event.tick == accepted.tick:
                actual = pre.value
                assert (actual.reset, actual.confirmation_mask, actual.return_mask) == (
                    request.reset, request.mask, sum(1 << i for i in request.returns)), (
                        "driven beat differs from actual sampled inputs", request, actual,
                        "pre", pre.event, "post", post.event, "accepted", accepted)
            facts = self.check_cycle(pre, post)
            if post.event.tick == accepted.tick:
                return facts

    def check_cycle(self, pre, post):
        actual = pre.value
        old = self.model.expected()
        facts = self.model.advance(actual)
        if actual.reset:
            self._reset_ledger()
        else:
            self._update_ledger(actual)
        self.coverage.sample(facts, post.event.tick, checked=False)
        if actual.reset:
            # Reset cancels an old lifecycle; it cannot fulfil its return proof.
            self.obligations.clear()
        if not actual.reset:
            compare(actual, old, phase="before", tick=pre.event.tick)
            compare(post.value, self.model.expected(), phase="after", tick=post.event.tick)
            completed = []
            for scene in facts.scenarios:
                if scene.startswith(("FL-CONGESTION.", "FL-ORDER.")) or scene in (
                    "FL-RETURN.delayed", "FL-OVERLAP.notify_and_allocate"):
                    # A return notification alone is NOT evidence of correct
                    # eventual ownership/order. Observe its actual reuse first.
                    items = facts.returned
                    if scene == "FL-ORDER.priority_over_notification_age":
                        items = (*self.model.selected, *(i for bank in self.model.waiting for i in bank))
                    assert items, (scene, facts)
                    self.obligations.append((scene, set(items)))
                elif scene in ("FL-WRAP.return_wrap", "FL-OVERLAP.recycle_and_allocate", "FL-PREFETCH.refill_wait"):
                    assert facts.recycled, (scene, facts)
                    self.obligations.append((scene, set(facts.recycled)))
                else:
                    completed.append(scene)
            outstanding = []
            for scene, remaining in self.obligations:
                remaining.difference_update(facts.allocated)
                if remaining:
                    outstanding.append((scene, remaining))
                else:
                    completed.append(scene)
            self.obligations = outstanding
            self.coverage.sample_scenarios(completed, post.event.tick, checked=True)
            self.checked_cycles += 1
        return facts

    @property
    def offered(self):
        available = self.advertised if self.spec["preallocate"] else len(self.available)
        return min(3, available)

    def _reset_ledger(self):
        self.available = list(range(self.spec["size"]))
        self.owned, self.pending_returns = set(), set()
        self.waiting = [set() for _ in range(self.spec.get("banks", 4))]
        self.selected, self.recycled = (), ()
        self.advertised = len(self.available)
        self.last_allocated = ()

    def _update_ledger(self, observation):
        """Maintain ownership from accepted public requests and contract timing.

        Allocated identities come from the sampled pre-edge request slots under
        the accepted confirmation mask; returns come from the sampled return mask.
        The return bank/selection lifecycle is part of the public contract and
        is kept here, never copied from model diagnostic events.
        """
        size = self.spec["size"]
        count = observation.confirmation_mask.bit_count()
        allocated = tuple(observation.slots[:count])
        if len(set(allocated)) != len(allocated):
            raise AssertionError(("duplicate allocated slot in public response", allocated))
        self.last_allocated = allocated
        for slot in allocated:
            if slot not in self.available:
                raise AssertionError(("allocated slot was not advertised as a free slot", slot, self.available))
            self.available.remove(slot)
            self.owned.add(slot)
        remaining_before_recycle = len(self.available)
        # Contract return pipeline: a slot is notified at N, selected from its
        # bank backlog at N+1, and rejoins the available pool at N+2.  The
        # batch selected on the previous edge is exactly the one becoming
        # available now; keeping another staging copy delays it by one cycle.
        returned = self.selected
        self.available.extend(returned)
        for slot in returned:
            self.pending_returns.discard(slot)
        next_batch = []
        for bank in self.waiting:
            if bank:
                item = min(bank)
                bank.remove(item)
                next_batch.append(item)
        self.recycled, self.selected = returned, tuple(next_batch)
        incoming = tuple(slot for slot in range(size) if observation.return_mask >> slot & 1)
        for slot in incoming:
            if slot not in self.owned:
                raise AssertionError(("returned slot is not owned", slot, sorted(self.owned)))
            self.owned.discard(slot)
            self.pending_returns.add(slot)
            self.waiting[slot % len(self.waiting)].add(slot)
        self.advertised = remaining_before_recycle
        self.last_allocated = allocated

    async def reset(self):
        self.available = list(range(self.spec["size"]))
        self.owned = set()
        self.pending_returns = set()
        for _ in range(3):
            await self.cycle(reset=True)
        await self.idle(2)

    async def idle(self, cycles=1):
        for _ in range(cycles):
            await self.cycle()

    async def exhaust(self):
        allocated = []
        while self.available:
            n = self.offered
            if not n:
                await self.cycle()
                continue
            await self.cycle(n)
            allocated.extend(self.last_allocated)
        await self.idle(2)
        return tuple(allocated)

    async def settle_returns(self):
        for _ in range(self.spec["size"] + 4):
            if not self.pending_returns:
                await self.idle(2)
                return
            await self.cycle()
        raise AssertionError("return pipeline did not drain")
