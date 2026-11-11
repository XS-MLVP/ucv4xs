"""Directed public PSQ checks; NOT a full PSQ lifecycle reference."""
from dataclasses import replace
import json

from suites.memblock.lsq.testbenches.psq.transactions import Inputs
from suites.memblock.lsq.testbenches.psq.transactions import encode


class PsqProbe:
    def __init__(self, driver, before, after, coverage, journal, checks, nodeid):
        self.driver, self.before, self.after, self.coverage, self.journal, self.checks = driver, before, after, coverage, journal, checks
        self.nodeid, self.controls, self.last_tick = nodeid, Inputs(), -1
        self.pre_observed = self.observed = None
        self.pre_response = self.response = None

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
            self.pre_response = self.driver.ports.observe(self.pre_observed)
            self.response = self.driver.ports.observe(self.observed)
            self.journal.write(json.dumps({"nodeid": self.nodeid, "pre_tick": pre.event.tick, "post_tick": post.event.tick,
                                           "input": pre.value[0], "post_input": post.value[0], "before": pre.value[1], "after": post.value[1]}) + "\n")
            if self.last_tick == edge.tick:
                return self.observed

    @property
    def deq_position(self):
        ptr = self.response.sq_deq_ptr
        return int(ptr.first) * 128 + int(ptr.second) * 64 + ptr.value

    def expect(self, observation, why, *, before=False, bit_masks=None):
        self.expect_object(self.driver.ports.expected(observation), why, bit_masks=bit_masks, before=before)

    def expect_sbuffer_word(self, lane, word, why, *, data_mask=None, bit_masks=None, before=False):
        masks = dict(bit_masks or {})
        if data_mask is not None:
            masks[f"io_writeToSbuffer_req_{lane}_bits_data"] = data_mask
        self.expect_object(self.driver.ports.word_expected(lane, word), why, bit_masks=masks, before=before)

    def expect_forward(self, lane, response, why, *, before=False):
        self.expect_object(self.driver.ports.forward_expected(lane, response), why, before=before)

    def expect_object(self, expected, why, *, bit_masks=None, before=False):
        if not expected:
            raise AssertionError(("empty probe expectation is not a check", self.nodeid, why))
        actual = self.pre_response if before else self.response
        pins = self.pre_observed if before else self.observed
        masks = bit_masks or {}
        diff = {key: [pins[key], value] for key, value in expected.items() if (pins[key] ^ value) & masks.get(key, -1)}
        self.checks.write(json.dumps({"nodeid": self.nodeid, "tick": self.last_tick, "phase": "before" if before else "after", "why": why,
                                     "expected": expected, "bit_masks": masks, "actual": {key: pins[key] for key in expected}, "passed": not diff}) + "\n")
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
