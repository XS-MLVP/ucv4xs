from __future__ import annotations

from .checker import compare
from .types import Request


class FreeListEnv:
    def __init__(self, key, spec, driver, before, after, model, coverage):
        self.key, self.spec = key, spec
        self.driver, self.before, self.after = driver, before, after
        self.model, self.coverage = model, coverage
        self.checked_cycles = 0
        self.last_tick = -1
        self.obligations = []

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

    async def reset(self):
        for _ in range(3):
            await self.cycle(reset=True)
        await self.idle(2)

    async def idle(self, cycles=1):
        for _ in range(cycles):
            await self.cycle()

    async def exhaust(self):
        allocated = []
        while self.model.available:
            n = self.model.offered
            if not n:
                await self.cycle()
                continue
            allocated.extend((await self.cycle(n)).allocated)
        await self.idle(2)
        return tuple(allocated)

    async def settle_returns(self):
        for _ in range(self.spec["size"] + 4):
            if not any(self.model.waiting) and not self.model.selected:
                await self.idle(2)
                return
            await self.cycle()
        raise AssertionError("return pipeline did not drain")
