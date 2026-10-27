from .model import compare
from .types import Request, bitmap


class AgeEnv:
    def __init__(self, key, spec, driver, before, after, model, coverage):
        self.key, self.spec, self.driver = key, spec, driver
        self.before, self.after, self.model, self.coverage = before, after, model, coverage
        self.last_tick = -1
        self.checked_pre = self.checked_post = self.undefined_post_transients = 0

    async def cycle(self, enqueues=(None, None, None), removes=(), ready=(), *, reset=False):
        request = Request(tuple(enqueues), tuple(removes), tuple(ready), reset)
        accepted = await self.driver.send(request)
        while True:
            pre, post = await self.before.recv(), await self.after.recv()
            assert self.last_tick < post.event.tick <= accepted.tick and pre.event.tick + 1 == post.event.tick
            self.last_tick = post.event.tick
            if post.event.tick == accepted.tick:
                expected_pins = (tuple(0 if item is None else 1 << item for item in request.enqueues),
                                 bitmap(request.removes), bitmap(request.ready), request.reset)
                assert (pre.value.enqueue_masks, pre.value.remove_mask, pre.value.ready_mask, pre.value.reset) == expected_pins
            winner = self.check_cycle(pre, post)
            if post.event.tick == accepted.tick:
                return winner

    def check_cycle(self, pre, post):
        change = self.model.advance(pre.value)
        scenes = self.coverage.discover(pre.value, change, self.model)
        self.coverage.sample(scenes, post.event.tick, checked=False)
        pre_winner = compare(pre.value, change.before, phase="before", tick=pre.event.tick)
        self.checked_pre += 1
        post_valid = not post.value.ready_mask & ~bitmap(self.model.order)
        if post_valid:
            post_winner = compare(post.value, self.model.order, phase="after", tick=post.event.tick)
            self.checked_post += 1
        else:
            # The consumer has not yet withdrawn ready for a just-removed ID.
            # This is a specifically delimited don't-care, not valid filtering.
            assert post.value.ready_mask & ~bitmap(self.model.order) & ~pre.value.remove_mask == 0
            self.undefined_post_transients += 1
            post_winner = None
        self.coverage.confirm(scenes, pre.value, post.value, change, self.model,
                              pre_winner, post_winner, post_valid, post.event.tick)
        return pre_winner

    async def reset(self):
        for _ in range(3):
            await self.cycle(reset=True)
        await self.cycle()

    async def drain(self):
        got = []
        while self.model.order:
            ready = tuple(self.model.order)
            winner = await self.cycle(removes=(ready[0],), ready=ready)
            assert winner == ready[0]
            got.append(winner)
        await self.cycle()
        return tuple(got)

    async def insert_order(self, order, *, parallel=False):
        order = tuple(order)
        width = self.spec["enqueue_width"] if parallel else 1
        for i in range(0, len(order), width):
            batch = order[i:i+width]
            await self.cycle(enqueues=(*batch, *(None for _ in range(self.spec["enqueue_width"]-len(batch)))))
