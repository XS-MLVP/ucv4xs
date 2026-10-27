"""Directed public PSQ checks; NOT a full PSQ lifecycle reference."""
from dataclasses import replace
import json

from .types import Inputs, encode


class PsqProbe:
    def __init__(self, driver, before, after, coverage, journal, checks, nodeid):
        self.driver, self.before, self.after, self.coverage, self.journal, self.checks = driver, before, after, coverage, journal, checks
        self.nodeid, self.controls, self.last_tick = nodeid, Inputs(), -1
        self.pre_observed = self.observed = None

    async def cycle(self, **controls):
        self.controls = replace(self.controls, **controls)
        edge = await self.driver.send(self.controls)
        while True:
            pre, post = await self.before.recv(), await self.after.recv()
            assert pre.event.tick + 1 == post.event.tick and self.last_tick < post.event.tick <= edge.tick
            if self.last_tick >= 0:
                assert self.last_tick + 2 == post.event.tick, "unobserved real PSQ cycle"
            self.last_tick = post.event.tick
            assert pre.value[0] == post.value[0]
            if self.last_tick == edge.tick:
                assert pre.value[0] == encode(self.controls)
            self.pre_observed, self.observed = pre.value[1], post.value[1]
            self.journal.write(json.dumps({"nodeid": self.nodeid, "pre_tick": pre.event.tick, "post_tick": post.event.tick,
                                           "input": pre.value[0], "post_input": post.value[0], "before": pre.value[1], "after": post.value[1]}) + "\n")
            if self.last_tick == edge.tick:
                return self.observed

    def expect(self, expected, why, *, before=False, bit_masks=None):
        actual = self.pre_observed if before else self.observed
        masks = bit_masks or {}
        diff = {key: [actual[key], value] for key, value in expected.items() if (actual[key] ^ value) & masks.get(key, -1)}
        self.checks.write(json.dumps({"nodeid": self.nodeid, "tick": self.last_tick, "phase": "before" if before else "after", "why": why,
                                     "expected": expected, "bit_masks": masks, "actual": {key: actual[key] for key in expected}, "passed": not diff}) + "\n")
        assert not diff, ("real-psq-public-directed", self.last_tick, why, diff)

    def begin(self, names):
        self.coverage.sample(names, self.last_tick)

    def finish(self, names):
        self.coverage.sample(names, self.last_tick, checked=True)

    async def idle(self, count=1, **controls):
        return [await self.cycle(**controls) for _ in range(count)]

    async def boot(self):
        for _ in range(4):
            await self.cycle(reset=True)
        for _ in range(4):
            await self.cycle(reset=False)
