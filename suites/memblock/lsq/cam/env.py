from .model import compare
from .types import Query, Request, Write


class CamEnv:
    def __init__(self, key, spec, driver, before, after, model, coverage):
        self.key, self.spec, self.driver = key, spec, driver
        self.before, self.after, self.model, self.coverage = before, after, model, coverage
        self.last_tick = -1
        self.checked_bits = 0

    async def cycle(self, writes=(), queries=None):
        if isinstance(writes, dict):
            writes = tuple(writes.get(i, Write()) for i in range(self.spec["write_width"]))
        elif not writes:
            writes = (Write(),) * self.spec["write_width"]
        request = Request(tuple(writes), tuple(queries or (Query(),) * len(self.spec["queries"])))
        accepted = await self.driver.send(request)
        while True:
            pre, post = await self.before.recv(), await self.after.recv()
            assert self.last_tick < post.event.tick <= accepted.tick
            assert pre.event.tick + 1 == post.event.tick
            self.last_tick = post.event.tick
            if post.event.tick == accepted.tick:
                assert (pre.value.writes, pre.value.queries) == (request.writes, request.queries), (request, pre.value)
            self.check_cycle(pre, post)
            if post.event.tick == accepted.tick:
                return post.value

    def check_cycle(self, pre, post):
        old = list(self.model.entries)
        commits = self.model.advance(pre.value)
        scenes = self.coverage.discover(pre.value, post.value, old, self.model, commits)
        self.coverage.sample(scenes, post.event.tick, checked=False)
        self.checked_bits += compare(pre.value, old, self.spec, phase="before", tick=pre.event.tick)
        self.checked_bits += compare(post.value, self.model.entries, self.spec, phase="after", tick=post.event.tick)
        self.coverage.confirm(scenes, post.value, self.model, post.event.tick)

    async def idle(self, cycles=1, queries=None):
        result = None
        for _ in range(cycles):
            result = await self.cycle(queries=queries)
        return result

    def queries(self, values, *, line=False):
        values = tuple(values)
        return tuple(Query(values[i % len(values)], line) for i in range(len(self.spec["queries"])))

    async def probe_values(self, values=None):
        if self.spec["kind"] == "byte_mask":
            values = [1 << bit for bit in range(self.spec["width"])]
        elif values is None:
            values = sorted({v for v in self.model.entries if v is not None})
        values = list(values)
        width = len(self.spec["queries"])
        for i in range(0, len(values), width):
            await self.cycle(queries=self.queries(values[i:i+width]))

    async def initialize_pool(self, values=None, *, lane=0):
        if values is None:
            if self.spec["kind"] == "byte_mask":
                patterns = (0, 1, 0x8000, 3, 6, 0xFFFF, 0x5555, 0xAAAA)
                values = [patterns[i % len(patterns)] for i in range(self.spec["size"])]
            else:
                values = [0x4000 + 4 * i for i in range(self.spec["size"])]
        values = list(values)
        assert len(values) == self.spec["size"]
        for address, value in enumerate(values):
            await self.cycle({lane: Write(address, value, True)}, self.queries((value,)))
        await self.idle(self.spec["write_delay"])
        await self.probe_values(values)
        assert self.model.entries == values
        return values
